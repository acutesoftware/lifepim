from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from common import data
from common import user_paths
from common.network_log import log_network
from common.utils import get_table_def, lg_usr, normalize_area_param
from core import security
from modules.notes import routes as notes_routes


pocket_api_bp = Blueprint("pocket_api", __name__, url_prefix="/api/pocket/v1")

ITEM_NAMESPACE = uuid.UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f")
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')
PAIRING_CODE_TTL = timedelta(minutes=5)
PAIRING_CODE_MAX_ACTIVE_PER_USER = 5
REGISTRATION_FAILURE_LIMIT = 5
REGISTRATION_FAILURE_WINDOW = timedelta(minutes=15)
POCKET_MAX_SYNC_PAYLOAD_BYTES = int(os.getenv("LIFEPIM_POCKET_MAX_SYNC_PAYLOAD_BYTES", str(100 * 1024 * 1024)))
POCKET_MAX_ATTACHMENT_BYTES = int(os.getenv("LIFEPIM_POCKET_MAX_ATTACHMENT_BYTES", str(25 * 1024 * 1024)))
POCKET_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
POCKET_FRONT_MATTER_READ_LIMIT = 128 * 1024
POCKET_MANIFEST_FRONT_MATTER_LIMIT = int(os.getenv("LIFEPIM_POCKET_MANIFEST_FRONT_MATTER_LIMIT", "100"))


def _utc_now():
    return datetime.now(timezone.utc)


def _utc_now_sql():
    return _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def _token_hash(raw_token):
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    return {row[1] for row in rows}


def ensure_pocket_schema(conn=None):
    conn = data._get_conn() if conn is None else conn
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS pocket_devices (
            device_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            device_name TEXT,
            platform TEXT,
            username TEXT,
            user_id INTEGER,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            revoked_at TEXT,
            last_ip TEXT,
            user_agent TEXT
        );
        CREATE TABLE IF NOT EXISTS pocket_item_map (
            item_uuid TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            UNIQUE(entity_type, entity_id)
        );
        CREATE TABLE IF NOT EXISTS pocket_item_state (
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            file_path TEXT,
            file_size INTEGER,
            file_mtime_ns INTEGER,
            sha256 TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(entity_type, entity_id)
        );
        CREATE TABLE IF NOT EXISTS pocket_client_item_map (
            device_id TEXT NOT NULL,
            client_item_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY(device_id, client_item_id)
        );
        CREATE TABLE IF NOT EXISTS pocket_mobile_files (
            mobile_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_user_id INTEGER NOT NULL,
            device_id TEXT,
            relative_path TEXT NOT NULL,
            kind TEXT NOT NULL,
            operation TEXT NOT NULL DEFAULT 'UPSERT',
            file_path TEXT,
            content_sha256 TEXT,
            file_size INTEGER NOT NULL DEFAULT 0,
            modified_at TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            UNIQUE(owner_user_id, relative_path)
        );
        CREATE TABLE IF NOT EXISTS pocket_user_settings (
            user_id INTEGER PRIMARY KEY,
            default_note_folder TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pocket_pairing_codes (
            pairing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pairing_code_hash TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_ip TEXT
        );
        CREATE TABLE IF NOT EXISTS pocket_registration_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempted_at TEXT NOT NULL,
            was_successful INTEGER NOT NULL CHECK (was_successful IN (0, 1)),
            ip_address TEXT,
            username TEXT,
            pairing_code_hash TEXT,
            device_id TEXT,
            reason TEXT,
            user_agent TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pocket_devices_token_hash ON pocket_devices(token_hash);
        CREATE INDEX IF NOT EXISTS idx_pocket_item_map_entity ON pocket_item_map(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_pocket_client_item_entity ON pocket_client_item_map(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_pocket_mobile_files_owner_path
            ON pocket_mobile_files(owner_user_id, relative_path);
        CREATE INDEX IF NOT EXISTS idx_pocket_pairing_user_active ON pocket_pairing_codes(user_id, used_at, expires_at);
        CREATE INDEX IF NOT EXISTS idx_pocket_registration_attempts_lookup
            ON pocket_registration_attempts(attempted_at, was_successful, ip_address, username, pairing_code_hash, device_id);
        """
    )
    _add_column_if_missing(conn, "pocket_devices", "username", "TEXT")
    _add_column_if_missing(conn, "pocket_devices", "user_id", "INTEGER")
    for column_name, column_type in (
        ("device_id", "TEXT"),
        ("operation", "TEXT NOT NULL DEFAULT 'UPSERT'"),
        ("file_size", "INTEGER NOT NULL DEFAULT 0"),
        ("modified_at", "TEXT"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("deleted_at", "TEXT"),
    ):
        _add_column_if_missing(conn, "pocket_mobile_files", column_name, column_type)
    conn.commit()


def _add_column_if_missing(conn, table_name, column_name, column_type):
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def get_user_pocket_settings(user_id, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_pocket_schema(conn)
    row = conn.execute(
        "SELECT user_id, default_note_folder, updated_at FROM pocket_user_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return {"user_id": user_id, "default_note_folder": ""}
    result = dict(row)
    result["default_note_folder"] = notes_routes._normalize_note_path(result.get("default_note_folder") or "")
    return result


def set_user_default_note_folder(user_id, folder_path, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_pocket_schema(conn)
    folder_path = notes_routes._normalize_note_path((folder_path or "").strip())
    if not folder_path:
        conn.execute("DELETE FROM pocket_user_settings WHERE user_id = ?", (user_id,))
        conn.commit()
        return ""
    if not os.path.isabs(folder_path):
        raise ValueError("Pocket default note folder must be an absolute path.")
    conn.execute(
        """
        INSERT INTO pocket_user_settings(user_id, default_note_folder, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            default_note_folder = excluded.default_note_folder,
            updated_at = excluded.updated_at
        """,
        (user_id, folder_path, _utc_now_sql()),
    )
    conn.commit()
    return folder_path


def _lookup_user_id(username):
    username = (username or "").strip()
    if not username:
        return None
    try:
        row = data._get_conn().execute(
            "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
    except Exception:
        return None
    return row["user_id"] if row else None


def _lookup_active_user(user_id):
    try:
        row = data._get_conn().execute(
            "SELECT user_id, username, display_name, is_active FROM users WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
    except Exception:
        return None
    return dict(row) if row else None


def _pairing_code_hash(pairing_code):
    normalized = re.sub(r"[^A-Za-z0-9]", "", pairing_code or "").upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _generate_pairing_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))


def create_pocket_pairing_code(user_id, created_ip=""):
    ensure_pocket_schema()
    user = _lookup_active_user(user_id)
    if not user:
        raise ValueError("Pocket pairing requires an active user.")
    now = _utc_now()
    now_sql = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    active_count = data._get_conn().execute(
        """
        SELECT COUNT(1) AS cnt
        FROM pocket_pairing_codes
        WHERE user_id = ? AND used_at IS NULL AND expires_at > ?
        """,
        (user["user_id"], now_sql),
    ).fetchone()["cnt"]
    if active_count >= PAIRING_CODE_MAX_ACTIVE_PER_USER:
        raise ValueError("Too many active Pocket pairing codes for this user.")
    for _ in range(10):
        raw_code = _generate_pairing_code()
        code_hash = _pairing_code_hash(raw_code)
        try:
            data._get_conn().execute(
                """
                INSERT INTO pocket_pairing_codes(pairing_code_hash, user_id, created_at, expires_at, created_ip)
                VALUES (?, ?, ?, ?, ?)
                """,
                (code_hash, user["user_id"], now_sql, (now + PAIRING_CODE_TTL).strftime("%Y-%m-%dT%H:%M:%SZ"), created_ip or ""),
            )
            data._get_conn().commit()
            log_network("pocket_pairing_code_created", user_id=user["user_id"], username=user["username"], created_ip=created_ip or "")
            return {"pairing_code": raw_code, "expires_at": (now + PAIRING_CODE_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")}
        except Exception:
            continue
    raise RuntimeError("Could not create a unique Pocket pairing code.")


def list_pocket_devices(conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_pocket_schema(conn)
    rows = conn.execute(
        """
        SELECT device_id, device_name, platform, username, user_id, created_at, last_seen_at,
               revoked_at, last_ip, user_agent
        FROM pocket_devices
        ORDER BY revoked_at IS NOT NULL, last_seen_at DESC, created_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def revoke_pocket_device(device_id, conn=None):
    device_id = (device_id or "").strip()
    if not device_id:
        return False
    conn = data._get_conn() if conn is None else conn
    ensure_pocket_schema(conn)
    cur = conn.execute(
        "UPDATE pocket_devices SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL",
        (_utc_now_sql(), device_id),
    )
    conn.commit()
    return bool(cur.rowcount)


def _json_error(error, status_code):
    return jsonify({"error": error}), status_code


@pocket_api_bp.before_request
def _reject_oversized_pocket_payload():
    max_bytes = int(current_app.config.get("LIFEPIM_POCKET_MAX_SYNC_PAYLOAD_BYTES", POCKET_MAX_SYNC_PAYLOAD_BYTES))
    push_paths = (
        "/sync/push",
        "/sync/upload",
        "/sync/uploads",
        "/sync/mobile",
        "/sync/mobile-to-desktop",
        "/push",
    )
    is_push_path = any(request.path.rstrip("/").endswith(path) for path in push_paths)
    if is_push_path:
        log_network(
            "pocket_push_connect",
            path=request.path,
            method=request.method,
            content_length=request.content_length,
            remote_addr=_client_ip(),
            has_authorization=bool(request.headers.get("Authorization")),
            has_device_id=bool(request.headers.get("X-LifePIM-Device-ID")),
        )
    if is_push_path and request.content_length and request.content_length > max_bytes:
        log_network(
            "pocket_payload_too_large",
            path=request.path,
            content_length=request.content_length,
            max_bytes=max_bytes,
            remote_addr=_client_ip(),
        )
        return _json_error("payload_too_large", 413)
    return None


def _client_ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or request.remote_addr or ""


def _user_agent():
    return (request.headers.get("User-Agent") or "")[:500]


def _record_registration_attempt(was_successful, username="", pairing_code_hash="", device_id="", reason="", user_id=None):
    ensure_pocket_schema()
    data._get_conn().execute(
        """
        INSERT INTO pocket_registration_attempts
        (attempted_at, was_successful, ip_address, username, pairing_code_hash, device_id, reason, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_utc_now_sql(), 1 if was_successful else 0, _client_ip(), username or "", pairing_code_hash or "", device_id or "", reason or "", _user_agent()),
    )
    data._get_conn().commit()
    log_network(
        "pocket_registration_attempt",
        was_successful=bool(was_successful),
        username=username or "",
        user_id=user_id,
        device_id=device_id or "",
        reason=reason or "",
        remote_addr=_client_ip(),
    )


def _registration_rate_limited(username="", pairing_code_hash="", device_id=""):
    cutoff = (_utc_now() - REGISTRATION_FAILURE_WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = data._get_conn().execute(
        """
        SELECT COUNT(1) AS cnt
        FROM pocket_registration_attempts
        WHERE was_successful = 0
          AND attempted_at >= ?
          AND (
                ip_address = ?
             OR (username != '' AND lower(username) = lower(?))
             OR (pairing_code_hash != '' AND pairing_code_hash = ?)
             OR (device_id != '' AND device_id = ?)
          )
        """,
        (cutoff, _client_ip(), username or "", pairing_code_hash or "", device_id or ""),
    ).fetchone()
    return bool(row and row["cnt"] >= REGISTRATION_FAILURE_LIMIT)


def _auth_device():
    ensure_pocket_schema()
    auth_header = request.headers.get("Authorization") or ""
    prefix = "Bearer "
    if not auth_header.startswith(prefix):
        log_network(
            "pocket_auth_failed",
            reason="missing_bearer",
            path=request.path,
            device_id=request.headers.get("X-LifePIM-Device-ID"),
            remote_addr=_client_ip(),
        )
        return None
    raw_token = auth_header[len(prefix) :].strip()
    device_id = (request.headers.get("X-LifePIM-Device-ID") or "").strip()
    if not raw_token or not device_id:
        log_network(
            "pocket_auth_failed",
            reason="missing_token_or_device",
            path=request.path,
            device_id=device_id,
            remote_addr=_client_ip(),
        )
        return None
    row = data._get_conn().execute(
        """
        SELECT * FROM pocket_devices
        WHERE device_id = ? AND token_hash = ? AND revoked_at IS NULL
        """,
        (device_id, _token_hash(raw_token)),
    ).fetchone()
    if not row:
        log_network(
            "pocket_auth_failed",
            reason="token_not_found_or_revoked",
            path=request.path,
            device_id=device_id,
            remote_addr=_client_ip(),
        )
        return None
    row_dict = dict(row)
    if not row_dict.get("user_id") and row_dict.get("username"):
        user_id = _lookup_user_id(row_dict.get("username"))
        if user_id:
            data._get_conn().execute(
                "UPDATE pocket_devices SET user_id = ? WHERE device_id = ?",
                (user_id, device_id),
            )
            data._get_conn().commit()
            row_dict["user_id"] = user_id
    data._get_conn().execute(
        "UPDATE pocket_devices SET last_seen_at = ?, last_ip = ?, user_agent = ? WHERE device_id = ?",
        (_utc_now_sql(), _client_ip(), _user_agent(), device_id),
    )
    data._get_conn().commit()
    log_network(
        "pocket_auth_ok",
        path=request.path,
        device_id=device_id,
        username=row_dict.get("username"),
        user_id=row_dict.get("user_id"),
        remote_addr=_client_ip(),
    )
    return row_dict


def require_pocket_auth():
    device = _auth_device()
    if not device:
        return None, _json_error("unauthorized", 401)
    return device, None


def require_bound_pocket_user(device):
    if device and device.get("user_id"):
        return None
    log_network(
        "pocket_user_binding_missing",
        device_id=device.get("device_id") if device else None,
        username=device.get("username") if device else None,
        path=request.path,
    )
    return _json_error("device_not_bound_to_user", 403)


def _note_table():
    notes_routes._ensure_notes_schema()
    tbl = get_table_def("notes")
    if not tbl:
        raise RuntimeError("Notes table not found.")
    return tbl


def _note_rows(user_id=None):
    tbl = _note_table()
    columns = _table_columns(data._get_conn(), tbl["name"])
    select_cols = ["id"] + [col for col in tbl["col_list"] if col in columns]
    if "owner_user_id" in columns:
        select_cols.append("owner_user_id")
    if "visibility" in columns:
        select_cols.append("visibility")
    if "is_public" in columns:
        select_cols.append("is_public")
    if "rec_extract_date" in columns:
        select_cols.append("rec_extract_date")
    for optional_col in (
        "title",
        "name",
        "source_note_id",
        "lifepim_com_note_id",
        "note_id",
        "date_created",
        "created",
        "created_at",
        "created_utc",
        "important",
        "is_important",
        "color",
        "colour",
    ):
        if optional_col in columns and optional_col not in select_cols:
            select_cols.append(optional_col)
    where = "1=1"
    params = []
    if user_id is not None:
        if "owner_user_id" not in columns:
            log_network("pocket_note_security_missing_owner_column", table=tbl["name"])
            return []
        where = _note_owner_or_legacy_filter()
        params.append(user_id)
    rows = data._get_conn().execute(
        f"SELECT {', '.join(select_cols)} FROM {tbl['name']} WHERE {where} ORDER BY id",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _note_owner_or_legacy_filter():
    return "(owner_user_id = ? OR owner_user_id IS NULL OR owner_user_id = '' OR owner_user_id = 0)"


def _effective_note_owner_user_id(note, user_id=None):
    owner_user_id = note.get("owner_user_id") if note else None
    if owner_user_id in (None, "", 0, "0"):
        return user_id
    return owner_user_id


def _cached_item_sha(entity_type, entity_id):
    try:
        row = data._get_conn().execute(
            """
            SELECT sha256 FROM pocket_item_state
            WHERE entity_type = ? AND entity_id = ?
            """,
            (entity_type, entity_id),
        ).fetchone()
    except Exception:
        return ""
    return (row["sha256"] or "") if row else ""


def _cached_note_sha_map(note_ids):
    note_ids = [int(note_id) for note_id in note_ids if note_id is not None]
    if not note_ids:
        return {}
    placeholders = ", ".join("?" for _ in note_ids)
    try:
        rows = data._get_conn().execute(
            f"""
            SELECT entity_id, sha256 FROM pocket_item_state
            WHERE entity_type = 'note' AND entity_id IN ({placeholders})
            """,
            note_ids,
        ).fetchall()
    except Exception:
        return {}
    return {int(row["entity_id"]): (row["sha256"] or "") for row in rows}


def _mobile_file_rows(user_id=None, include_deleted=False):
    ensure_pocket_schema()
    where = "1=1"
    params = []
    if user_id is not None:
        where += " AND owner_user_id = ?"
        params.append(user_id)
    if not include_deleted:
        where += " AND deleted_at IS NULL"
    rows = data._get_conn().execute(
        f"""
        SELECT mobile_file_id, owner_user_id, device_id, relative_path, kind, operation,
               file_path, content_sha256, file_size, modified_at, version, updated_at, deleted_at
        FROM pocket_mobile_files
        WHERE {where}
        ORDER BY relative_path COLLATE NOCASE, mobile_file_id
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _mobile_file_row_by_id(mobile_file_id, user_id=None, include_deleted=False):
    ensure_pocket_schema()
    where = "mobile_file_id = ?"
    params = [mobile_file_id]
    if user_id is not None:
        where += " AND owner_user_id = ?"
        params.append(user_id)
    if not include_deleted:
        where += " AND deleted_at IS NULL"
    row = data._get_conn().execute(
        f"""
        SELECT mobile_file_id, owner_user_id, device_id, relative_path, kind, operation,
               file_path, content_sha256, file_size, modified_at, version, updated_at, deleted_at
        FROM pocket_mobile_files
        WHERE {where}
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def _cached_mobile_file_sha_map(mobile_file_ids):
    mobile_file_ids = [int(row_id) for row_id in mobile_file_ids if row_id is not None]
    if not mobile_file_ids:
        return {}
    placeholders = ", ".join("?" for _ in mobile_file_ids)
    try:
        rows = data._get_conn().execute(
            f"""
            SELECT entity_id, sha256 FROM pocket_item_state
            WHERE entity_type = 'mobile_file' AND entity_id IN ({placeholders})
            """,
            mobile_file_ids,
        ).fetchall()
    except Exception:
        return {}
    return {int(row["entity_id"]): (row["sha256"] or "") for row in rows}


def _upsert_item_state(entity_type, entity_id, note_path, state):
    if not state:
        return
    ensure_pocket_schema()
    data._get_conn().execute(
        """
        INSERT INTO pocket_item_state
        (entity_type, entity_id, file_path, file_size, file_mtime_ns, sha256, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_type, entity_id) DO UPDATE SET
            file_path = excluded.file_path,
            file_size = excluded.file_size,
            file_mtime_ns = excluded.file_mtime_ns,
            sha256 = excluded.sha256,
            updated_at = excluded.updated_at
        """,
        (
            entity_type,
            entity_id,
            note_path,
            int(state.get("size") or 0),
            int(state.get("mtime_ns") or 0),
            state.get("sha256") or "",
            _utc_now_sql(),
        ),
    )
    data._get_conn().commit()


def _note_file_metadata(note_path):
    try:
        stat = os.stat(note_path)
    except OSError:
        return None
    state = {
        "size": str(stat.st_size),
        "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "mtime_ns": stat.st_mtime_ns,
    }
    return _state_with_file_created_at(state, stat)


def _state_with_file_created_at(state, stat_or_path):
    if not state:
        return state
    stat = stat_or_path
    if isinstance(stat_or_path, str):
        try:
            stat = os.stat(stat_or_path)
        except OSError:
            return state
    created_at = _file_created_at(stat)
    if created_at:
        state = dict(state)
        state["date_created"] = created_at
        state["created_at"] = _iso_from_note_value(created_at)
    return state


def _file_created_at(stat):
    created = getattr(stat, "st_birthtime", None)
    if created is None:
        created = getattr(stat, "st_ctime", None)
    if created is None:
        return ""
    return datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")


def _strip_yaml_scalar(value):
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _read_note_front_matter(note_path):
    if not note_path:
        return {}
    try:
        with open(note_path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read(POCKET_FRONT_MATTER_READ_LIMIT)
    except OSError:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in ("---", "..."):
            break
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        if not key:
            continue
        values[key] = _strip_yaml_scalar(raw_value)
    return values


def _front_matter_bool(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return value if value not in (None, "") else None


def _first_front_matter_value(front_matter, keys):
    for key in keys:
        value = front_matter.get(key)
        if value not in (None, ""):
            return value
    return ""


def _metadata_from_front_matter(front_matter):
    title = _first_front_matter_value(front_matter, ("title", "name"))
    source_note_id = _first_front_matter_value(front_matter, ("source_note_id", "lifepim_com_note_id", "note_id"))
    created = _first_front_matter_value(front_matter, ("date_created", "created", "created_at", "created_utc"))
    modified = _first_front_matter_value(front_matter, ("date_modified", "date_updated", "modified", "updated", "updated_at", "updated_utc"))
    important = _first_front_matter_value(front_matter, ("important", "is_important"))
    color = _first_front_matter_value(front_matter, ("color", "colour"))
    metadata = {
        "title": "",
        "source_note_id": "",
        "note_id": "",
        "date_created": "",
        "created_at": "",
        "date_modified": "",
        "front_matter_modified_at": "",
        "important": False,
        "color": "",
    }
    if title:
        metadata["title"] = title
    if source_note_id:
        metadata["source_note_id"] = source_note_id
        metadata["note_id"] = source_note_id
    if created:
        metadata["date_created"] = created
        metadata["created_at"] = _iso_from_note_value(created)
    if modified:
        metadata["date_modified"] = modified
        metadata["front_matter_modified_at"] = _iso_from_note_value(modified)
    if important not in (None, ""):
        metadata["important"] = _front_matter_bool(important)
    if color:
        metadata["color"] = color
    return metadata


def _empty_note_metadata():
    return {
        "title": "",
        "source_note_id": "",
        "note_id": "",
        "date_created": "",
        "created_at": "",
        "date_modified": "",
        "front_matter_modified_at": "",
        "important": False,
        "color": "",
    }


def _metadata_from_note_columns(note):
    metadata = _empty_note_metadata()
    title = note.get("title") or note.get("name") or ""
    source_note_id = note.get("source_note_id") or note.get("lifepim_com_note_id") or note.get("note_id") or ""
    created = note.get("date_created") or note.get("created") or note.get("created_at") or note.get("created_utc") or ""
    modified = note.get("date_modified") or note.get("modified") or note.get("modified_at") or note.get("date_updated") or ""
    important = note.get("important") if "important" in note else note.get("is_important")
    color = note.get("color") or note.get("colour") or ""
    if title:
        metadata["title"] = title
    if source_note_id:
        metadata["source_note_id"] = source_note_id
        metadata["note_id"] = source_note_id
    if created:
        metadata["date_created"] = created
        metadata["created_at"] = _iso_from_note_value(created)
    if modified:
        metadata["date_modified"] = modified
        metadata["front_matter_modified_at"] = _iso_from_note_value(modified)
    if important not in (None, ""):
        metadata["important"] = _front_matter_bool(important)
    if color:
        metadata["color"] = color
    return metadata


def _metadata_from_note_row(note):
    size_value = note.get("size") or 0
    try:
        size_value = int(size_value)
    except (TypeError, ValueError):
        size_value = 0
    modified_at = _iso_from_note_value(note.get("date_modified") or note.get("rec_extract_date") or "")
    mtime_ns = 0
    if modified_at:
        try:
            mtime_ns = int(datetime.fromisoformat(modified_at.replace("Z", "+00:00")).timestamp() * 1_000_000_000)
        except ValueError:
            mtime_ns = 0
    result = {
        "size": str(size_value),
        "date_modified": note.get("date_modified") or note.get("rec_extract_date") or "",
        "modified_at": modified_at,
        "mtime_ns": mtime_ns,
    }
    date_created = note.get("date_created") or note.get("created_at") or note.get("created_utc") or ""
    if date_created:
        result["date_created"] = date_created
        result["created_at"] = _iso_from_note_value(date_created)
    return result


def _payload_area(payload_item):
    if not isinstance(payload_item, dict):
        return ""
    candidate_sources = [payload_item]
    metadata = payload_item.get("metadata")
    if isinstance(metadata, dict):
        candidate_sources.append(metadata)
    for source in candidate_sources:
        for key in ("area", "area_id", "project", "project_id", "proj"):
            value = source.get(key)
            if value is not None and str(value).strip():
                return normalize_area_param(str(value).strip())
    return ""


def _iso_from_note_value(value):
    if not value:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            continue
    return value


def _note_row_by_id(note_id, user_id=None):
    tbl = _note_table()
    columns = _table_columns(data._get_conn(), tbl["name"])
    where = "id = ?"
    params = [note_id]
    if user_id is not None:
        if "owner_user_id" not in columns:
            log_network("pocket_note_security_missing_owner_column", table=tbl["name"])
            return None
        where += f" AND {_note_owner_or_legacy_filter()}"
        params.append(user_id)
    row = data._get_conn().execute(f"SELECT * FROM {tbl['name']} WHERE {where}", params).fetchone()
    return dict(row) if row else None


def _item_uuid_for_note(note_id, user_id=None):
    conn = data._get_conn()
    if user_id is None:
        row = conn.execute("SELECT owner_user_id FROM lp_notes WHERE id = ?", (note_id,)).fetchone()
        if row and "owner_user_id" in row.keys():
            user_id = row["owner_user_id"]
    item_uuid = str(uuid.uuid5(ITEM_NAMESPACE, f"user:{user_id}:note:{int(note_id)}"))
    row = conn.execute("SELECT entity_id FROM pocket_item_map WHERE item_uuid = ?", (item_uuid,)).fetchone()
    if row:
        return item_uuid
    now = _utc_now_sql()
    conn.execute(
        """
        INSERT INTO pocket_item_map(item_uuid, entity_type, entity_id, created_at, last_seen_at)
        VALUES (?, 'note', ?, ?, ?)
        ON CONFLICT(entity_type, entity_id) DO UPDATE SET
            item_uuid = excluded.item_uuid,
            last_seen_at = excluded.last_seen_at
        """,
        (item_uuid, note_id, now, now),
    )
    conn.commit()
    return item_uuid


def _item_uuid_map_for_notes(notes, user_id=None):
    now = _utc_now_sql()
    note_ids = []
    expected = {}
    existing = {}
    item_ids = {}
    for note in notes:
        note_id = int(note["id"])
        note_ids.append(note_id)
        item_owner_user_id = _effective_note_owner_user_id(note, user_id=user_id)
        item_uuid = str(uuid.uuid5(ITEM_NAMESPACE, f"user:{item_owner_user_id}:note:{note_id}"))
        expected[note_id] = item_uuid
        item_ids[note_id] = item_uuid
    if note_ids:
        placeholders = ", ".join("?" for _ in note_ids)
        try:
            rows = data._get_conn().execute(
                f"""
                SELECT entity_id, item_uuid
                FROM pocket_item_map
                WHERE entity_type = 'note' AND entity_id IN ({placeholders})
                """,
                note_ids,
            ).fetchall()
            existing = {int(row["entity_id"]): (row["item_uuid"] or "") for row in rows}
        except Exception:
            existing = {}
    values = [
        (item_uuid, note_id, now, now)
        for note_id, item_uuid in expected.items()
        if existing.get(note_id) != item_uuid
    ]
    if values:
        conn = data._get_conn()
        conn.executemany(
            """
            INSERT INTO pocket_item_map(item_uuid, entity_type, entity_id, created_at, last_seen_at)
            VALUES (?, 'note', ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                item_uuid = excluded.item_uuid,
                last_seen_at = excluded.last_seen_at
            """,
            values,
        )
    return item_ids


def _item_uuid_for_mobile_file(mobile_file_id, user_id=None):
    conn = data._get_conn()
    if user_id is None:
        row = conn.execute(
            "SELECT owner_user_id FROM pocket_mobile_files WHERE mobile_file_id = ?",
            (mobile_file_id,),
        ).fetchone()
        user_id = row["owner_user_id"] if row else None
    item_uuid = str(uuid.uuid5(ITEM_NAMESPACE, f"user:{user_id}:mobile_file:{int(mobile_file_id)}"))
    now = _utc_now_sql()
    conn.execute(
        """
        INSERT INTO pocket_item_map(item_uuid, entity_type, entity_id, created_at, last_seen_at)
        VALUES (?, 'mobile_file', ?, ?, ?)
        ON CONFLICT(entity_type, entity_id) DO UPDATE SET
            item_uuid = excluded.item_uuid,
            last_seen_at = excluded.last_seen_at
        """,
        (item_uuid, mobile_file_id, now, now),
    )
    conn.commit()
    return item_uuid


def _item_uuid_map_for_mobile_files(rows):
    now = _utc_now_sql()
    expected = {}
    mobile_file_ids = []
    for row in rows:
        mobile_file_id = int(row["mobile_file_id"])
        mobile_file_ids.append(mobile_file_id)
        expected[mobile_file_id] = str(
            uuid.uuid5(ITEM_NAMESPACE, f"user:{row.get('owner_user_id')}:mobile_file:{mobile_file_id}")
        )
    existing = {}
    if mobile_file_ids:
        placeholders = ", ".join("?" for _ in mobile_file_ids)
        try:
            mapped = data._get_conn().execute(
                f"""
                SELECT entity_id, item_uuid
                FROM pocket_item_map
                WHERE entity_type = 'mobile_file' AND entity_id IN ({placeholders})
                """,
                mobile_file_ids,
            ).fetchall()
            existing = {int(row["entity_id"]): (row["item_uuid"] or "") for row in mapped}
        except Exception:
            existing = {}
    values = [
        (item_uuid, mobile_file_id, now, now)
        for mobile_file_id, item_uuid in expected.items()
        if existing.get(mobile_file_id) != item_uuid
    ]
    if values:
        data._get_conn().executemany(
            """
            INSERT INTO pocket_item_map(item_uuid, entity_type, entity_id, created_at, last_seen_at)
            VALUES (?, 'mobile_file', ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                item_uuid = excluded.item_uuid,
                last_seen_at = excluded.last_seen_at
            """,
            values,
        )
        data._get_conn().commit()
    return expected


def _note_id_for_item(item_id):
    ensure_pocket_schema()
    item_id = (item_id or "").strip()
    if not item_id:
        return None
    row = data._get_conn().execute(
        "SELECT entity_id FROM pocket_item_map WHERE item_uuid = ? AND entity_type = 'note'",
        (item_id,),
    ).fetchone()
    if row:
        return int(row["entity_id"])
    try:
        return int(item_id)
    except (TypeError, ValueError):
        return None


def _mobile_file_id_for_item(item_id):
    ensure_pocket_schema()
    item_id = (item_id or "").strip()
    if not item_id:
        return None
    row = data._get_conn().execute(
        "SELECT entity_id FROM pocket_item_map WHERE item_uuid = ? AND entity_type = 'mobile_file'",
        (item_id,),
    ).fetchone()
    return int(row["entity_id"]) if row else None


def _note_id_for_client_item(device_id, client_item_id):
    ensure_pocket_schema()
    device_id = (device_id or "").strip()
    client_item_id = (client_item_id or "").strip()
    if not device_id or not client_item_id:
        return None
    row = data._get_conn().execute(
        """
        SELECT entity_id
        FROM pocket_client_item_map
        WHERE device_id = ? AND client_item_id = ? AND entity_type = 'note'
        """,
        (device_id, client_item_id),
    ).fetchone()
    return int(row["entity_id"]) if row else None


def _mobile_file_id_for_client_item(device_id, client_item_id):
    ensure_pocket_schema()
    device_id = (device_id or "").strip()
    client_item_id = (client_item_id or "").strip()
    if not device_id or not client_item_id:
        return None
    row = data._get_conn().execute(
        """
        SELECT entity_id
        FROM pocket_client_item_map
        WHERE device_id = ? AND client_item_id = ? AND entity_type = 'mobile_file'
        """,
        (device_id, client_item_id),
    ).fetchone()
    return int(row["entity_id"]) if row else None


def _mobile_file_id_for_relative_path(user_id, relative_path, include_deleted=False):
    ensure_pocket_schema()
    relative_path = (relative_path or "").strip()
    if user_id is None or not relative_path:
        return None
    row = data._get_conn().execute(
        """
        SELECT mobile_file_id
        FROM pocket_mobile_files
        WHERE owner_user_id = ? AND relative_path = ?
          AND (? OR deleted_at IS NULL)
        """,
        (user_id, relative_path, 1 if include_deleted else 0),
    ).fetchone()
    return int(row["mobile_file_id"]) if row else None


def _mobile_backup_root_for_user(user_id):
    conn = data._get_conn()
    paths = user_paths.get_user_paths(conn, user_id)
    root = notes_routes._normalize_note_path(paths.get("file_root_path") or "")
    if not root:
        default_folder = _default_note_folder_for_user(user_id)
        if default_folder:
            root = os.path.dirname(default_folder)
    if not root:
        paths = user_paths.get_or_create_user_paths(conn, user_id, create_dirs=False)
        root = notes_routes._normalize_note_path(paths.get("file_root_path") or "")
    if not root:
        root = getattr(data, "DB_FILE", "") and os.path.dirname(getattr(data, "DB_FILE", ""))
    root = notes_routes._normalize_note_path(root or os.getcwd())
    backup_root = os.path.abspath(os.path.join(root, "pocket_mobile"))
    os.makedirs(backup_root, exist_ok=True)
    return backup_root


def _mobile_file_path_for_payload(payload_item, user_id):
    backup_root = _mobile_backup_root_for_user(user_id)
    relative_path = _safe_mobile_relative_path(payload_item)
    target_path = os.path.abspath(os.path.join(backup_root, relative_path.replace("/", os.sep)))
    if target_path != backup_root and not target_path.startswith(backup_root + os.sep):
        raise ValueError("invalid_mobile_path")
    return relative_path, target_path


def _write_mobile_file_bytes(target_path, content_bytes, modified_at=""):
    parent = os.path.dirname(target_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temp_path = f"{target_path}.tmp"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(content_bytes)
        os.replace(temp_path, target_path)
        source_ts = _parse_payload_modified_at({"modified_at": modified_at})
        if source_ts is not None:
            os.utime(target_path, (source_ts, source_ts))
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
    return notes_routes._note_file_state(target_path)


def _find_mobile_file_id(payload_item, device):
    item_id = _payload_id(payload_item)
    mobile_file_id = _mobile_file_id_for_item(item_id)
    if mobile_file_id is not None:
        return mobile_file_id
    mobile_file_id = _mobile_file_id_for_client_item(device.get("device_id"), item_id)
    if mobile_file_id is not None:
        return mobile_file_id
    relative_path = _safe_mobile_relative_path(payload_item)
    return _mobile_file_id_for_relative_path(device.get("user_id"), relative_path)


def _log_pocket_user_change(action, entity_type, entity_id, before=None, after=None, extra=None, device=None):
    try:
        lg_usr(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            context_type="pocket_sync",
            context_id=device.get("device_id") if device else None,
            extra=extra,
            conn=data._get_conn(),
            user_name=device.get("username") if device else None,
        )
    except Exception:
        pass


def _delete_mobile_file_from_payload(payload_item, device):
    mobile_file_id = _find_mobile_file_id(payload_item, device)
    client_item_id = _payload_id(payload_item)
    if mobile_file_id is None:
        return {
            "id": client_item_id,
            "client_change_id": _payload_client_change_id(payload_item),
            "server_item_id": "",
            "ok": True,
            "deleted": True,
            "missing": True,
        }
    before = _mobile_file_row_by_id(mobile_file_id, user_id=device.get("user_id"), include_deleted=True)
    if not before:
        return {"id": client_item_id, "ok": False, "error": "not_found", "debug": _payload_debug(payload_item)}
    if before.get("file_path") and os.path.exists(before["file_path"]):
        try:
            os.remove(before["file_path"])
        except OSError:
            pass
    now = _utc_now_sql()
    data._get_conn().execute(
        """
        UPDATE pocket_mobile_files
        SET operation = 'DELETE',
            version = COALESCE(version, 0) + 1,
            updated_at = ?,
            deleted_at = ?
        WHERE mobile_file_id = ? AND owner_user_id = ?
        """,
        (now, now, mobile_file_id, device.get("user_id")),
    )
    data._get_conn().commit()
    if client_item_id:
        _upsert_client_item_map(device.get("device_id"), client_item_id, "mobile_file", mobile_file_id)
    item_uuid = _item_uuid_for_mobile_file(mobile_file_id, device.get("user_id"))
    _log_pocket_user_change(
        "sync_mobile_file_delete",
        "pocket_mobile_files",
        mobile_file_id,
        before=before,
        after=_mobile_file_row_by_id(mobile_file_id, user_id=device.get("user_id"), include_deleted=True),
        extra={"relative_path": before.get("relative_path"), "kind": before.get("kind")},
        device=device,
    )
    return {
        "id": item_uuid,
        "client_change_id": _payload_client_change_id(payload_item),
        "server_item_id": item_uuid,
        "ok": True,
        "deleted": True,
    }


def _upsert_mobile_file_from_payload(payload_item, device):
    content_bytes = _payload_content_bytes(payload_item)
    if content_bytes is None:
        return {"id": _payload_id(payload_item), "ok": False, "error": "missing_content", "debug": _payload_debug(payload_item)}
    supplied_sha = str(payload_item.get("sha256") or "").strip().lower()
    actual_sha = hashlib.sha256(content_bytes).hexdigest()
    if supplied_sha and supplied_sha != actual_sha:
        return {"id": _payload_id(payload_item), "ok": False, "error": "hash_mismatch", "debug": _payload_debug(payload_item)}
    relative_path, target_path = _mobile_file_path_for_payload(payload_item, device.get("user_id"))
    kind = _payload_kind(payload_item)
    modified_at = payload_item.get("modified_at") or payload_item.get("modifiedAt") or ""
    state = _write_mobile_file_bytes(target_path, content_bytes, modified_at=modified_at)
    existing_id = _mobile_file_id_for_relative_path(device.get("user_id"), relative_path, include_deleted=True)
    before = _mobile_file_row_by_id(existing_id, user_id=device.get("user_id"), include_deleted=True) if existing_id else None
    now = _utc_now_sql()
    if existing_id:
        version = int(before.get("version") or 0) + 1 if before else 1
        data._get_conn().execute(
            """
            UPDATE pocket_mobile_files
            SET device_id = ?,
                kind = ?,
                operation = 'UPSERT',
                file_path = ?,
                content_sha256 = ?,
                file_size = ?,
                modified_at = ?,
                version = ?,
                updated_at = ?,
                deleted_at = NULL
            WHERE mobile_file_id = ? AND owner_user_id = ?
            """,
            (
                device.get("device_id"),
                kind,
                target_path,
                actual_sha,
                int(state.get("size") or len(content_bytes)) if state else len(content_bytes),
                modified_at or (state or {}).get("date_modified") or now,
                version,
                now,
                existing_id,
                device.get("user_id"),
            ),
        )
        mobile_file_id = existing_id
        created = False
    else:
        cur = data._get_conn().execute(
            """
            INSERT INTO pocket_mobile_files
            (owner_user_id, device_id, relative_path, kind, operation, file_path, content_sha256,
             file_size, modified_at, version, updated_at, deleted_at)
            VALUES (?, ?, ?, ?, 'UPSERT', ?, ?, ?, ?, 1, ?, NULL)
            """,
            (
                device.get("user_id"),
                device.get("device_id"),
                relative_path,
                kind,
                target_path,
                actual_sha,
                int(state.get("size") or len(content_bytes)) if state else len(content_bytes),
                modified_at or (state or {}).get("date_modified") or now,
                now,
            ),
        )
        mobile_file_id = cur.lastrowid
        created = True
    data._get_conn().commit()
    client_item_id = _payload_id(payload_item)
    if client_item_id:
        _upsert_client_item_map(device.get("device_id"), client_item_id, "mobile_file", mobile_file_id)
    _upsert_item_state("mobile_file", mobile_file_id, target_path, state or {"size": len(content_bytes), "sha256": actual_sha})
    item = _serialize_mobile_file_item(
        _mobile_file_row_by_id(mobile_file_id, user_id=device.get("user_id")),
        include_content=False,
        item_uuid=_item_uuid_for_mobile_file(mobile_file_id, device.get("user_id")),
        state_override=state,
    )
    _log_pocket_user_change(
        "sync_mobile_file_add" if created else "sync_mobile_file_update",
        "pocket_mobile_files",
        mobile_file_id,
        before=before,
        after=_mobile_file_row_by_id(mobile_file_id, user_id=device.get("user_id")),
        extra={"relative_path": relative_path, "kind": kind},
        device=device,
    )
    log_network(
        "pocket_push_mobile_file_saved",
        device_id=device.get("device_id"),
        username=device.get("username"),
        user_id=device.get("user_id"),
        mobile_file_id=mobile_file_id,
        relative_path=relative_path,
        kind=kind,
        size=len(content_bytes),
        created=created,
    )
    return {
        "id": item["id"],
        "client_change_id": _payload_client_change_id(payload_item),
        "server_item_id": item["id"],
        "ok": True,
        "created": created,
        "item": item,
    }


def _mapped_note_id_for_item(item_id):
    ensure_pocket_schema()
    item_id = (item_id or "").strip()
    if not item_id:
        return None
    row = data._get_conn().execute(
        "SELECT entity_id FROM pocket_item_map WHERE item_uuid = ? AND entity_type = 'note'",
        (item_id,),
    ).fetchone()
    return int(row["entity_id"]) if row else None


def _delete_note_from_mobile(payload_item, device):
    item_id = _payload_id(payload_item)
    note_id = _mapped_note_id_for_item(item_id)
    if note_id is None:
        note_id = _note_id_for_client_item(device.get("device_id"), item_id)
    if note_id is None:
        return {
            "id": item_id,
            "client_change_id": _payload_client_change_id(payload_item),
            "server_item_id": "",
            "ok": True,
            "deleted": True,
            "missing": True,
        }
    note = _note_row_by_id(note_id, user_id=device.get("user_id"))
    if not note:
        return {
            "id": item_id,
            "client_change_id": _payload_client_change_id(payload_item),
            "server_item_id": item_id,
            "ok": True,
            "deleted": True,
            "missing": True,
        }
    before = dict(note)
    archived_path = notes_routes._archive_and_delete_note(note_id)
    data._get_conn().execute(
        "DELETE FROM pocket_item_state WHERE entity_type = 'note' AND entity_id = ?",
        (note_id,),
    )
    data._get_conn().execute(
        "DELETE FROM pocket_item_map WHERE entity_type = 'note' AND entity_id = ?",
        (note_id,),
    )
    data._get_conn().execute(
        "DELETE FROM pocket_client_item_map WHERE entity_type = 'note' AND entity_id = ?",
        (note_id,),
    )
    data._get_conn().commit()
    _log_pocket_user_change(
        "sync_note_delete",
        "lp_notes",
        note_id,
        before=before,
        after=None,
        extra={"archived_path": archived_path, "relative_path": _payload_relative_path(payload_item)},
        device=device,
    )
    log_network(
        "pocket_push_note_deleted",
        device_id=device.get("device_id"),
        username=device.get("username"),
        user_id=device.get("user_id"),
        note_id=note_id,
        archived_path=archived_path,
    )
    return {
        "id": item_id,
        "client_change_id": _payload_client_change_id(payload_item),
        "server_item_id": item_id,
        "ok": True,
        "deleted": True,
    }


def _upsert_client_item_map(device_id, client_item_id, entity_type, entity_id):
    device_id = (device_id or "").strip()
    client_item_id = (client_item_id or "").strip()
    if not device_id or not client_item_id:
        return
    now = _utc_now_sql()
    data._get_conn().execute(
        """
        INSERT INTO pocket_client_item_map(device_id, client_item_id, entity_type, entity_id, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id, client_item_id) DO UPDATE SET
            entity_type = excluded.entity_type,
            entity_id = excluded.entity_id,
            last_seen_at = excluded.last_seen_at
        """,
        (device_id, client_item_id, entity_type, entity_id, now, now),
    )
    data._get_conn().commit()


def _notes_root(user_id=None, notes=None):
    roots = []
    for note in (notes if notes is not None else _note_rows(user_id=user_id)):
        try:
            path_value = notes_routes._normalize_note_path(note.get("path"))
        except Exception:
            path_value = ""
        if path_value:
            roots.append(path_value)
    if not roots:
        return ""
    try:
        common_root = os.path.commonpath(roots)
    except ValueError:
        return ""
    return notes_routes._normalize_note_path(common_root)


def _relative_note_path(note, root=None):
    full_path = notes_routes._build_note_path(note)
    if not full_path:
        return ""
    try:
        full_path = notes_routes._normalize_note_path(full_path)
    except Exception:
        return os.path.basename(full_path)
    root = root if root is not None else _notes_root()
    try:
        if root and os.path.commonpath([root, full_path]).lower() == root.lower():
            return os.path.relpath(full_path, root).replace("\\", "/")
    except (OSError, ValueError):
        pass
    return os.path.basename(full_path)


def _matching_area_folder_rows(note, owner_user_id):
    conn = data._get_conn()
    try:
        table_names = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "lp_area_folders" not in table_names:
            return []
    except Exception:
        return []
    try:
        folder_path = notes_routes._normalize_note_path(note.get("path")) or os.path.dirname(notes_routes._build_note_path(note))
    except Exception:
        folder_path = os.path.dirname(notes_routes._build_note_path(note))
    if not folder_path:
        return []
    try:
        full_path = notes_routes._normalize_note_path(notes_routes._build_note_path(note))
    except Exception:
        full_path = notes_routes._build_note_path(note)
    folder_columns = _table_columns(conn, "lp_area_folders")
    if not {"area_id", "path_prefix"}.issubset(folder_columns):
        return []
    area_join = ""
    area_name_expr = "'' AS area_name"
    if "lp_areas" in table_names:
        area_columns = _table_columns(conn, "lp_areas")
        if {"owner_user_id", "area_id", "area_name"}.issubset(area_columns):
            area_join = (
                "LEFT JOIN lp_areas p "
                "ON p.owner_user_id IS pf.owner_user_id "
                "AND p.area_id = pf.area_id"
            )
            area_name_expr = "COALESCE(p.area_name, '') AS area_name"
    owner_condition = "pf.owner_user_id IS ?" if "owner_user_id" in folder_columns else "? IS NULL"
    enabled_condition = "AND pf.is_enabled = 1" if "is_enabled" in folder_columns else ""
    role_condition = (
        "AND pf.folder_role IN ('default','include','archive','output')" if "folder_role" in folder_columns else ""
    )
    folder_role_expr = "pf.folder_role" if "folder_role" in folder_columns else "'default'"
    sort_order_expr = "pf.sort_order" if "sort_order" in folder_columns else "100"

    def _rows_for_owner(owner_value):
        try:
            rows = conn.execute(
                f"""
                SELECT pf.area_id, pf.path_prefix, {folder_role_expr} AS folder_role,
                       {sort_order_expr} AS sort_order, {area_name_expr}
                FROM lp_area_folders pf
                {area_join}
                WHERE {owner_condition}
                  {enabled_condition}
                  {role_condition}
                """,
                (owner_value,),
            ).fetchall()
        except Exception:
            return []
        matched = []
        folder_lower = folder_path.lower()
        for row in rows:
            try:
                path_prefix = notes_routes._normalize_note_path(row["path_prefix"])
            except Exception:
                continue
            if not path_prefix:
                continue
            if folder_lower.startswith(path_prefix.lower()):
                item = dict(row)
                item["path_prefix"] = path_prefix
                item["full_path"] = full_path
                matched.append(item)
        return matched

    owner_rows = _rows_for_owner(owner_user_id) if owner_user_id is not None else []
    return owner_rows or _rows_for_owner(None)


def _area_folder_rows_for_manifest(owner_user_id):
    conn = data._get_conn()
    try:
        table_names = {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    except Exception:
        return []
    if "lp_area_folders" not in table_names:
        return []
    folder_columns = _table_columns(conn, "lp_area_folders")
    if not {"area_id", "path_prefix"}.issubset(folder_columns):
        return []
    area_join = ""
    area_name_expr = "'' AS area_name"
    if "lp_areas" in table_names:
        area_columns = _table_columns(conn, "lp_areas")
        if {"owner_user_id", "area_id", "area_name"}.issubset(area_columns):
            area_join = (
                "LEFT JOIN lp_areas p "
                "ON p.owner_user_id IS pf.owner_user_id "
                "AND p.area_id = pf.area_id"
            )
            area_name_expr = "COALESCE(p.area_name, '') AS area_name"
    owner_condition = "pf.owner_user_id IS ?" if "owner_user_id" in folder_columns else "? IS NULL"
    enabled_condition = "AND pf.is_enabled = 1" if "is_enabled" in folder_columns else ""
    role_condition = (
        "AND pf.folder_role IN ('default','include','archive','output')" if "folder_role" in folder_columns else ""
    )
    folder_role_expr = "pf.folder_role" if "folder_role" in folder_columns else "'default'"
    sort_order_expr = "pf.sort_order" if "sort_order" in folder_columns else "100"
    rows = []
    for owner_value in (owner_user_id, None):
        if owner_value is None and owner_user_id is None:
            continue
        try:
            fetched = conn.execute(
                f"""
                SELECT pf.area_id, pf.path_prefix, {folder_role_expr} AS folder_role,
                       {sort_order_expr} AS sort_order, {area_name_expr}
                FROM lp_area_folders pf
                {area_join}
                WHERE {owner_condition}
                  {enabled_condition}
                  {role_condition}
                """,
                (owner_value,),
            ).fetchall()
        except Exception:
            continue
        for row in fetched:
            try:
                path_prefix = notes_routes._normalize_note_path(row["path_prefix"])
            except Exception:
                continue
            if not path_prefix:
                continue
            item = dict(row)
            item["path_prefix"] = path_prefix
            item["_manifest_owner_user_id"] = owner_value
            rows.append(item)
    return rows


def _matching_area_folder_rows_from_cache(note, owner_user_id, area_folder_rows):
    if area_folder_rows is None:
        return _matching_area_folder_rows(note, owner_user_id)
    try:
        folder_path = notes_routes._normalize_note_path(note.get("path")) or os.path.dirname(notes_routes._build_note_path(note))
    except Exception:
        folder_path = os.path.dirname(notes_routes._build_note_path(note))
    if not folder_path:
        return []
    try:
        full_path = notes_routes._normalize_note_path(notes_routes._build_note_path(note))
    except Exception:
        full_path = notes_routes._build_note_path(note)
    folder_lower = folder_path.lower()

    def _matches(owner_value):
        matched = []
        for row in area_folder_rows:
            if row.get("_manifest_owner_user_id") != owner_value:
                continue
            path_prefix = row.get("path_prefix") or ""
            if folder_lower.startswith(path_prefix.lower()):
                item = dict(row)
                item["full_path"] = full_path
                matched.append(item)
        return matched

    owner_rows = _matches(owner_user_id) if owner_user_id is not None else []
    return owner_rows or _matches(None)


def _derived_area_for_note(note, owner_user_id=None, area_folder_rows=None):
    fallback = note.get("area") or ""
    owner_user_id = owner_user_id if owner_user_id is not None else note.get("owner_user_id")
    rows = _matching_area_folder_rows_from_cache(note, owner_user_id, area_folder_rows)
    if not rows:
        return fallback
    best_prefix_len = max(len(row.get("path_prefix") or "") for row in rows)
    best_rows = [row for row in rows if len(row.get("path_prefix") or "") == best_prefix_len]
    role_order = {"default": 0, "include": 1, "output": 2, "archive": 3}

    def _sort_key(row):
        area_id = row.get("area_id") or ""
        return (
            -len(row.get("path_prefix") or ""),
            role_order.get(row.get("folder_role") or "", 9),
            area_id.count("/"),
            len(area_id),
            area_id,
            row.get("path_prefix") or "",
        )

    named_child_rows = []
    for row in best_rows:
        area_id = row.get("area_id") or ""
        area_name = row.get("area_name") or ""
        if "/" in area_id and area_name and area_name.lower() in (row.get("full_path") or "").lower():
            named_child_rows.append(row)
    if named_child_rows:
        return sorted(named_child_rows, key=_sort_key)[0].get("area_id") or fallback
    return sorted(best_rows, key=_sort_key)[0].get("area_id") or fallback


def _iso_from_state_or_note(state, note, allow_file_stat=True):
    if state and state.get("modified_at"):
        return state.get("modified_at")
    note_modified = _iso_from_note_value(note.get("date_modified") or note.get("rec_extract_date") or "")
    if note_modified:
        return note_modified
    state_modified = _iso_from_note_value(state.get("date_modified") if state else "")
    if state_modified:
        return state_modified
    if state and allow_file_stat:
        full_path = notes_routes._build_note_path(note)
        try:
            return datetime.fromtimestamp(os.path.getmtime(full_path), timezone.utc).isoformat()
        except OSError:
            pass
    return ""


def _item_kind(note, content=None):
    text = content if content is not None else ""
    if not text:
        note_path = notes_routes._build_note_path(note)
        text = notes_routes._read_note_file(note_path)
    return "LIST" if "- [ ]" in text or "- [x]" in text.lower() else "NOTE"


def _version_from_state(state):
    if not state:
        return 0
    try:
        return int(state.get("mtime_ns") or 0)
    except (TypeError, ValueError):
        return 0


def _serialize_note_item(
    note,
    include_content=False,
    root=None,
    state_override=None,
    note_path_override=None,
    user_id=None,
    include_front_matter=True,
    item_uuid=None,
    cached_sha="",
    area_folder_rows=None,
    allow_file_stat=True,
):
    note_path = note_path_override or notes_routes._build_note_path(note)
    if include_content:
        state = _state_with_file_created_at(notes_routes._note_file_state(note_path), note_path)
        _upsert_item_state("note", note["id"], note_path, state)
    else:
        state = state_override or _note_file_metadata(note_path)
    content = notes_routes._read_note_file(note_path) if include_content else None
    front_matter = _read_note_front_matter(note_path) if include_front_matter else {}
    front_matter_metadata = (
        _metadata_from_front_matter(front_matter)
        if include_front_matter
        else _metadata_from_note_columns(note)
    )
    if include_front_matter:
        column_metadata = _metadata_from_note_columns(note)
        for key in (
            "title",
            "source_note_id",
            "note_id",
            "date_created",
            "created_at",
            "date_modified",
            "front_matter_modified_at",
            "color",
        ):
            if not front_matter_metadata.get(key) and column_metadata.get(key):
                front_matter_metadata[key] = column_metadata.get(key)
        if not any(key in front_matter for key in ("important", "is_important")) and column_metadata.get("important") not in (None, ""):
            front_matter_metadata["important"] = column_metadata.get("important")
    if state and not front_matter_metadata.get("date_created") and state.get("date_created"):
        front_matter_metadata["date_created"] = state.get("date_created") or ""
        front_matter_metadata["created_at"] = state.get("created_at") or _iso_from_note_value(state.get("date_created") or "")
    derived_area = _derived_area_for_note(note, owner_user_id=user_id, area_folder_rows=area_folder_rows)
    item_owner_user_id = _effective_note_owner_user_id(note, user_id=user_id)
    item = {
        "id": item_uuid or _item_uuid_for_note(note["id"], item_owner_user_id),
        "relative_path": _relative_note_path(note, root=root) or "",
        "kind": _item_kind(note, content=content) if include_content else "NOTE",
        "ownership": "DESKTOP_MASTER",
        "sha256": state.get("sha256") if state and state.get("sha256") else (cached_sha or _cached_item_sha("note", note["id"]) or ""),
        "version": _version_from_state(state),
        "modified_at": _iso_from_state_or_note(state, note, allow_file_stat=allow_file_stat) or "",
        "area": derived_area or "",
        "area_id": derived_area or "",
        "project": derived_area or "",
        "project_id": derived_area or "",
        "derived_area": derived_area or "",
    }
    item.update(front_matter_metadata)
    item["area"] = derived_area or ""
    item["area_id"] = derived_area or ""
    item["project"] = derived_area or ""
    item["project_id"] = derived_area or ""
    item["derived_area"] = derived_area or ""
    item["metadata"] = dict(front_matter_metadata)
    item["metadata"]["area"] = derived_area or ""
    item["metadata"]["area_id"] = derived_area or ""
    item["metadata"]["project"] = derived_area or ""
    item["metadata"]["project_id"] = derived_area or ""
    item["metadata"]["derived_area"] = derived_area or ""
    if include_content:
        item["content"] = content
    return item


def _mobile_file_state(row):
    file_path = row.get("file_path") if row else ""
    if file_path and os.path.exists(file_path):
        return notes_routes._note_file_state(file_path)
    return {
        "size": str(row.get("file_size") or 0),
        "sha256": row.get("content_sha256") or "",
        "date_modified": row.get("modified_at") or row.get("updated_at") or "",
        "modified_at": row.get("modified_at") or row.get("updated_at") or "",
        "mtime_ns": 0,
    }


def _serialize_mobile_file_item(row, include_content=False, item_uuid=None, state_override=None, cached_sha=""):
    state = state_override or _mobile_file_state(row)
    mobile_file_id = int(row["mobile_file_id"])
    item = {
        "id": item_uuid or _item_uuid_for_mobile_file(mobile_file_id, row.get("owner_user_id")),
        "relative_path": row.get("relative_path") or "",
        "kind": (row.get("kind") or "NOTE").upper(),
        "ownership": "MOBILE_MASTER",
        "sha256": row.get("content_sha256") or (state.get("sha256") if state else "") or cached_sha or "",
        "version": int(row.get("version") or _version_from_state(state)),
        "modified_at": row.get("modified_at") or (state.get("modified_at") if state else "") or _iso_from_note_value(row.get("updated_at") or ""),
        "deleted": bool(row.get("deleted_at")),
    }
    if include_content and not item["deleted"]:
        file_path = row.get("file_path") or ""
        if item["kind"] == "MEDIA" or "base64" in str(row.get("operation") or "").lower():
            try:
                with open(file_path, "rb") as handle:
                    item["content_base64"] = base64.b64encode(handle.read()).decode("ascii")
                    item["content_encoding"] = "base64"
            except OSError:
                item["content_base64"] = ""
                item["content_encoding"] = "base64"
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
                    item["content"] = handle.read()
            except OSError:
                item["content"] = ""
    return item


def _update_note_metadata(note_id, note, state, area_override=""):
    tbl = _note_table()
    values_map = {col: note.get(col, "") for col in tbl["col_list"]}
    note_path = notes_routes._build_note_path(note)
    metadata = notes_routes._note_metadata_from_file(note_path, fallback_area=area_override or note.get("area") or "")
    if state:
        values_map["size"] = state.get("size", values_map.get("size", ""))
        values_map["date_modified"] = state.get("date_modified", values_map.get("date_modified", ""))
    values_map["title"] = metadata.get("title") or values_map.get("title", "")
    values_map["color"] = metadata.get("color") or values_map.get("color", "")
    values_map["date_created"] = metadata.get("date_created") or values_map.get("date_created", "")
    values_map["area"] = metadata.get("area") or values_map.get("area", "")
    values_map["important"] = metadata.get("important") or values_map.get("important", "")
    values_map["source_note_id"] = metadata.get("source_note_id") or values_map.get("source_note_id", "")
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    return data.update_record(data._get_conn(), tbl["name"], note_id, tbl["col_list"], values)


def _default_note_folder_for_user(user_id):
    settings = get_user_pocket_settings(user_id)
    configured = settings.get("default_note_folder")
    if configured:
        return configured
    tbl = _note_table()
    columns = _table_columns(data._get_conn(), tbl["name"])
    if "owner_user_id" not in columns:
        return ""
    rows = data._get_conn().execute(
        f"""
        SELECT path, COUNT(1) AS cnt
        FROM {tbl["name"]}
        WHERE owner_user_id = ? AND COALESCE(path, '') != ''
        GROUP BY path
        ORDER BY cnt DESC, LENGTH(path) ASC
        LIMIT 1
        """,
        (user_id,),
    ).fetchall()
    if not rows:
        paths = user_paths.get_or_create_user_paths(data._get_conn(), user_id, create_dirs=False)
        notes_root = notes_routes._normalize_note_path(paths.get("notes_root_path") or "")
        if notes_root:
            os.makedirs(notes_root, exist_ok=True)
        return notes_root
    return notes_routes._normalize_note_path(rows[0]["path"])


def _safe_mobile_file_name(payload_item):
    raw_path = (
        payload_item.get("relative_path")
        or payload_item.get("path")
        or payload_item.get("file_name")
        or payload_item.get("title")
        or "Mobile note.md"
    )
    raw_name = os.path.basename(str(raw_path).replace("\\", "/")).strip()
    if not raw_name:
        raw_name = "Mobile note.md"
    name, ext = os.path.splitext(raw_name)
    name = INVALID_FILENAME_CHARS.sub("", name).strip().strip(".")
    if not name:
        name = "Mobile note"
    if not ext:
        ext = ".md"
    if ext.lower() != ".md":
        ext = ".md"
    return f"{name}{ext}"


def _payload_relative_path(payload_item):
    raw_path = (
        payload_item.get("relative_path")
        or payload_item.get("relativePath")
        or payload_item.get("path")
        or payload_item.get("file_name")
        or payload_item.get("fileName")
        or payload_item.get("title")
        or ""
    )
    return str(raw_path or "").replace("\\", "/").strip()


def _payload_kind(payload_item):
    value = (payload_item.get("kind") or payload_item.get("type") or "").strip().upper()
    if value:
        return value
    relative_path = _payload_relative_path(payload_item)
    if relative_path.startswith("Media/"):
        return "MEDIA"
    if relative_path.startswith("Lists/"):
        return "LIST"
    if relative_path == "_LifePIM/projects.json":
        return "PROJECTS"
    if relative_path == "_LifePIM/settings.json":
        return "SETTINGS"
    return "NOTE"


def _payload_operation(payload_item):
    return (payload_item.get("operation") or payload_item.get("op") or "UPSERT").strip().upper()


def _is_mobile_file_payload(payload_item):
    kind = _payload_kind(payload_item)
    relative_path = _payload_relative_path(payload_item)
    return kind in {"LIST", "MEDIA", "PROJECTS", "SETTINGS"} or relative_path.startswith(("Lists/", "Media/", "_LifePIM/"))


def _safe_mobile_relative_path(payload_item):
    relative_path = _payload_relative_path(payload_item)
    kind = _payload_kind(payload_item)
    if not relative_path:
        default_name = {
            "MEDIA": "Media/mobile-file",
            "LIST": "Lists/mobile-list.md",
            "PROJECTS": "_LifePIM/projects.json",
            "SETTINGS": "_LifePIM/settings.json",
        }.get(kind, "mobile-file")
        relative_path = default_name
    relative_path = relative_path.replace("\\", "/").strip().lstrip("/")
    cleaned_parts = []
    for part in relative_path.split("/"):
        part = part.strip()
        if not part or part in {".", ".."}:
            continue
        stem, ext = os.path.splitext(part)
        stem = INVALID_FILENAME_CHARS.sub("_", stem).strip(" ._")
        ext = INVALID_FILENAME_CHARS.sub("", ext).strip()
        if ext and not ext.startswith("."):
            ext = "." + ext.lstrip(".")
        cleaned = f"{stem}{ext}" if stem else ext
        if cleaned:
            cleaned_parts.append(cleaned)
    if not cleaned_parts:
        cleaned_parts = ["mobile-file"]
    return "/".join(cleaned_parts)


def _payload_content(payload_item):
    for key in (
        "content",
        "markdown",
        "markdown_content",
        "markdownContent",
        "body",
        "text",
        "contents",
        "file_content",
        "fileContent",
    ):
        if key in payload_item and payload_item.get(key) is not None:
            return payload_item.get(key)
    return None


def _payload_content_bytes(payload_item):
    encoded = (
        payload_item.get("content_base64")
        or payload_item.get("contentBase64")
        or payload_item.get("base64")
        or payload_item.get("data")
        or ""
    )
    encoded = str(encoded).strip()
    if encoded:
        if encoded.lower().startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        return base64.b64decode(encoded, validate=True)
    content = _payload_content(payload_item)
    if content is None:
        return None
    return str(content).encode("utf-8")


def _payload_id(payload_item):
    for key in ("id", "item_id", "itemId", "server_item_id", "serverItemId", "server_id", "serverId", "uuid"):
        value = payload_item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _payload_client_change_id(payload_item):
    value = payload_item.get("client_change_id") or payload_item.get("clientChangeId") or ""
    return str(value).strip() if value is not None else ""


def _content_sha256(content):
    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def _parse_payload_modified_at(payload_item):
    value = payload_item.get("modified_at") or payload_item.get("modifiedAt") or ""
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def _state_timestamp(state, note_path):
    if state and state.get("mtime_ns"):
        try:
            return int(state.get("mtime_ns")) / 1_000_000_000
        except (TypeError, ValueError):
            pass
    try:
        return os.path.getmtime(note_path)
    except OSError:
        return None


def _payload_debug(payload_item):
    keys = sorted([str(key) for key in payload_item.keys()])
    content_key = ""
    content_len = None
    for key in keys:
        if key in {"content", "markdown", "markdown_content", "markdownContent", "body", "text", "contents", "file_content", "fileContent"}:
            value = payload_item.get(key)
            if value is not None:
                content_key = key
                content_len = len(str(value))
                break
    return {
        "keys": keys,
        "content_key": content_key,
        "content_len": content_len,
        "relative_path": payload_item.get("relative_path") or payload_item.get("path") or payload_item.get("file_name"),
        "attachment_count": len(_payload_attachments(payload_item)),
    }


def _payload_attachments(payload_item):
    attachments = payload_item.get("attachments") or payload_item.get("files") or payload_item.get("media") or []
    return attachments if isinstance(attachments, list) else []


def _safe_attachment_file_name(attachment):
    raw_name = (
        attachment.get("file_name")
        or attachment.get("filename")
        or attachment.get("name")
        or attachment.get("relative_path")
        or attachment.get("path")
        or ""
    )
    raw_name = os.path.basename(str(raw_name).replace("\\", "/")).strip()
    stem, ext = os.path.splitext(raw_name)
    ext = ext.lower()
    if ext not in POCKET_ATTACHMENT_EXTENSIONS:
        raise ValueError("unsupported_attachment_type")
    stem = INVALID_FILENAME_CHARS.sub("", stem).strip().strip(".")
    if not stem:
        raise ValueError("invalid_attachment_name")
    return f"{stem}{ext}"


def _attachment_content_bytes(attachment):
    encoded = (
        attachment.get("content_base64")
        or attachment.get("contentBase64")
        or attachment.get("base64")
        or attachment.get("data")
        or ""
    )
    encoded = str(encoded).strip()
    if encoded.lower().startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    if not encoded:
        raise ValueError("missing_attachment_content")
    content = base64.b64decode(encoded, validate=True)
    if len(content) > POCKET_MAX_ATTACHMENT_BYTES:
        raise ValueError("attachment_too_large")
    supplied_sha = (attachment.get("sha256") or "").strip().lower()
    actual_sha = hashlib.sha256(content).hexdigest()
    if supplied_sha and supplied_sha != actual_sha:
        raise ValueError("attachment_hash_mismatch")
    return content, actual_sha


def _write_payload_attachments(payload_item, note_path):
    attachments = _payload_attachments(payload_item)
    if not attachments:
        return {"saved": 0, "skipped": 0, "errors": []}
    base_dir = os.path.abspath(os.path.dirname(note_path or ""))
    if not base_dir:
        return {"saved": 0, "skipped": 0, "errors": ["invalid_note_folder"]}
    os.makedirs(base_dir, exist_ok=True)
    saved = 0
    skipped = 0
    errors = []
    for attachment in attachments:
        try:
            if not isinstance(attachment, dict):
                raise ValueError("invalid_attachment")
            file_name = _safe_attachment_file_name(attachment)
            content, actual_sha = _attachment_content_bytes(attachment)
            target_path = os.path.abspath(os.path.join(base_dir, file_name))
            if not target_path.startswith(base_dir + os.sep):
                raise ValueError("invalid_attachment_path")
            status = _write_attachment_file(target_path, content, actual_sha, attachment)
            if status == "saved":
                saved += 1
            else:
                skipped += 1
        except Exception as exc:
            errors.append(f"{attachment.get('file_name') if isinstance(attachment, dict) else 'attachment'}: {exc}")
    return {"saved": saved, "skipped": skipped, "errors": errors}


def _write_attachment_file(target_path, content, actual_sha, attachment):
    if os.path.exists(target_path):
        try:
            with open(target_path, "rb") as handle:
                if hashlib.sha256(handle.read()).hexdigest() == actual_sha:
                    return "same"
        except OSError:
            pass
        source_ts = _parse_payload_modified_at({"modified_at": attachment.get("modified_at") or attachment.get("modifiedAt")})
        try:
            dest_ts = os.path.getmtime(target_path)
        except OSError:
            dest_ts = None
        if source_ts is not None and dest_ts is not None and source_ts <= dest_ts:
            return "destination_newer"
    temp_path = f"{target_path}.tmp"
    try:
        with open(temp_path, "wb") as handle:
            handle.write(content)
        os.replace(temp_path, target_path)
        source_ts = _parse_payload_modified_at({"modified_at": attachment.get("modified_at") or attachment.get("modifiedAt")})
        if source_ts is not None:
            os.utime(target_path, (source_ts, source_ts))
        return "saved"
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _unique_note_path(folder_path, file_name):
    base, ext = os.path.splitext(file_name)
    candidate = file_name
    idx = 2
    while os.path.exists(os.path.join(folder_path, candidate)):
        candidate = f"{base} {idx}{ext}"
        idx += 1
    return candidate, os.path.join(folder_path, candidate)


def _note_by_mobile_file_name(payload_item, device):
    folder_path = _default_note_folder_for_user(device.get("user_id"))
    if not folder_path:
        return None
    file_name = _safe_mobile_file_name(payload_item)
    tbl = _note_table()
    columns = _table_columns(data._get_conn(), tbl["name"])
    if "owner_user_id" not in columns:
        return None
    row = data._get_conn().execute(
        f"""
        SELECT *
        FROM {tbl["name"]}
        WHERE owner_user_id = ?
          AND file_name = ?
          AND lower(path) = lower(?)
        ORDER BY id DESC
        LIMIT 1
        """,
        (device.get("user_id"), file_name, folder_path),
    ).fetchone()
    return dict(row) if row else None


def _create_note_from_mobile(payload_item, device):
    content = _payload_content(payload_item)
    if content is None:
        return {"id": _payload_id(payload_item), "ok": False, "error": "missing_content", "debug": _payload_debug(payload_item)}
    folder_path = _default_note_folder_for_user(device.get("user_id"))
    if not folder_path:
        return {"id": payload_item.get("id") or "", "ok": False, "error": "no_default_note_folder"}
    os.makedirs(folder_path, exist_ok=True)
    file_name, note_path = _unique_note_path(folder_path, _safe_mobile_file_name(payload_item))
    state = notes_routes._write_note_file_content(note_path, str(content))
    attachment_result = _write_payload_attachments(payload_item, note_path)
    front_matter = notes_routes._parse_note_front_matter_text(str(content))
    content_metadata = _metadata_from_front_matter(front_matter)
    payload_area = _payload_area(payload_item)
    file_metadata = notes_routes._note_metadata_from_file(note_path, fallback_area=payload_area)

    tbl = _note_table()
    table_columns = _table_columns(data._get_conn(), tbl["name"])
    values_map = {
        "file_name": file_name,
        "path": folder_path,
        "folder_id": "",
        "size": state.get("size", "") if state else "",
        "title": (
            payload_item.get("title")
            or content_metadata.get("title")
            or file_metadata.get("title")
            or os.path.splitext(file_name)[0]
        ),
        "color": payload_item.get("color") or content_metadata.get("color") or file_metadata.get("color") or "",
        "date_created": (
            payload_item.get("date_created")
            or payload_item.get("dateCreated")
            or payload_item.get("created_at")
            or content_metadata.get("date_created")
            or file_metadata.get("date_created")
            or ""
        ),
        "date_modified": state.get("date_modified", "") if state else "",
        "area": payload_area or file_metadata.get("area") or "",
        "important": (
            notes_routes._front_matter_bool_text(payload_item.get("important"))
            if payload_item.get("important") is not None
            else file_metadata.get("important", "")
        ),
        "source_note_id": (
            payload_item.get("source_note_id")
            or payload_item.get("lifepim_com_note_id")
            or payload_item.get("note_id")
            or content_metadata.get("source_note_id")
            or ""
        ),
        "owner_user_id": device.get("user_id"),
        "visibility": "private",
        "is_public": 0,
        "show_in_blog": 0,
    }
    cols = [col for col in list(tbl["col_list"]) + ["owner_user_id", "visibility", "is_public", "show_in_blog"] if col in table_columns]
    record_id = data.add_record(data._get_conn(), tbl["name"], cols, [values_map.get(col, "") for col in cols])
    if not record_id:
        return {"id": payload_item.get("id") or "", "ok": False, "error": "create_failed"}
    client_item_id = _payload_id(payload_item)
    _upsert_client_item_map(device.get("device_id"), client_item_id, "note", record_id)
    _upsert_item_state("note", record_id, note_path, state)
    note = _note_row_by_id(record_id, user_id=device.get("user_id"))
    item = _serialize_note_item(
        note,
        include_content=False,
        state_override=state,
        note_path_override=note_path,
        user_id=device.get("user_id"),
    )
    log_network(
        "pocket_push_create_note",
        device_id=device.get("device_id"),
        username=device.get("username"),
        user_id=device.get("user_id"),
        note_id=record_id,
        file_name=file_name,
        folder_path=folder_path,
        client_id=client_item_id,
        attachments_saved=attachment_result["saved"],
        attachment_errors=attachment_result["errors"],
    )
    return {
        "id": item["id"],
        "client_change_id": _payload_client_change_id(payload_item),
        "server_item_id": item["id"],
        "ok": True,
        "created": True,
        "item": item,
        "attachments_saved": attachment_result["saved"],
        "attachment_errors": attachment_result["errors"],
    }


def _save_pocket_device(device_id, raw_token, device_name, platform, username, user_id):
    now = _utc_now_sql()
    data._get_conn().execute(
        """
        INSERT INTO pocket_devices
        (device_id, token_hash, device_name, platform, username, user_id, created_at, last_seen_at, last_ip, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            token_hash = excluded.token_hash,
            device_name = excluded.device_name,
            platform = excluded.platform,
            username = excluded.username,
            user_id = excluded.user_id,
            last_seen_at = excluded.last_seen_at,
            revoked_at = NULL,
            last_ip = excluded.last_ip,
            user_agent = excluded.user_agent
        """,
        (
            device_id,
            _token_hash(raw_token),
            device_name,
            platform,
            username,
            user_id,
            now,
            now,
            _client_ip(),
            _user_agent(),
        ),
    )
    data._get_conn().commit()


@pocket_api_bp.route("/health", methods=["GET"])
def health_route():
    ensure_pocket_schema()
    return jsonify({"ok": True, "service": "lifepim-pocket", "version": 1})


@pocket_api_bp.route("/auth/pairing-codes", methods=["POST"])
def create_pairing_code_route():
    ensure_pocket_schema()
    if not current_user.is_authenticated:
        return _json_error("unauthorized", 401)
    user_id = getattr(current_user, "user_id", None)
    try:
        pairing = create_pocket_pairing_code(user_id, created_ip=_client_ip())
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(pairing)


@pocket_api_bp.route("/auth/register-device", methods=["POST"])
def register_device_route():
    ensure_pocket_schema()
    payload = request.get_json(silent=True) or {}
    device_id = (payload.get("device_id") or "").strip() or str(uuid.uuid4())
    device_name = (payload.get("device_name") or payload.get("name") or "").strip()
    platform = (payload.get("platform") or "").strip()
    username = (payload.get("username") or payload.get("user_name") or "").strip()
    pairing_code = payload.get("pairing_code") or payload.get("pairingCode") or ""
    code_hash = _pairing_code_hash(pairing_code)
    if _registration_rate_limited(username=username, pairing_code_hash=code_hash, device_id=device_id):
        _record_registration_attempt(False, username=username, pairing_code_hash=code_hash, device_id=device_id, reason="rate_limited")
        return _json_error("authentication_failed", 429)
    if not code_hash:
        _record_registration_attempt(False, username=username, device_id=device_id, reason="missing_pairing_code")
        return _json_error("authentication_failed", 401)
    now = _utc_now_sql()
    row = data._get_conn().execute(
        """
        SELECT p.*, u.username, u.display_name, u.is_active
        FROM pocket_pairing_codes p
        JOIN users u ON u.user_id = p.user_id
        WHERE p.pairing_code_hash = ?
        """,
        (code_hash,),
    ).fetchone()
    if not row or row["used_at"] or row["expires_at"] <= now or not row["is_active"]:
        _record_registration_attempt(False, username=username, pairing_code_hash=code_hash, device_id=device_id, reason="invalid_pairing_code")
        return _json_error("authentication_failed", 401)
    if username and username.lower() != (row["username"] or "").lower():
        _record_registration_attempt(False, username=username, pairing_code_hash=code_hash, device_id=device_id, reason="username_mismatch")
        return _json_error("authentication_failed", 401)
    user_id = row["user_id"]
    username = row["username"]
    raw_token = secrets.token_urlsafe(48)
    claimed = data._get_conn().execute(
        """
        UPDATE pocket_pairing_codes
        SET used_at = ?
        WHERE pairing_id = ? AND used_at IS NULL AND expires_at > ?
        """,
        (now, row["pairing_id"], now),
    )
    if not claimed.rowcount:
        data._get_conn().commit()
        _record_registration_attempt(False, username=username, pairing_code_hash=code_hash, device_id=device_id, reason="pairing_code_already_used")
        return _json_error("authentication_failed", 401)
    _save_pocket_device(device_id, raw_token, device_name, platform, username, user_id)
    _record_registration_attempt(True, username=username, pairing_code_hash=code_hash, device_id=device_id, reason="paired", user_id=user_id)
    log_network(
        "pocket_register_device",
        device_id=device_id,
        device_name=device_name,
        platform=platform,
        username=username,
        user_id=user_id,
        remote_addr=_client_ip(),
        user_agent=_user_agent(),
    )
    return jsonify(
        {
            "device_id": device_id,
            "device_token": raw_token,
            "token_type": "Bearer",
            "username": username,
            "display_name": row["display_name"],
        }
    )


@pocket_api_bp.route("/auth/login", methods=["POST"])
def password_login_route():
    ensure_pocket_schema()
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or payload.get("user_name") or "").strip()
    password = payload.get("password") or ""
    device_id = (payload.get("device_id") or "").strip() or str(uuid.uuid4())
    device_name = (payload.get("device_name") or payload.get("name") or "").strip()
    platform = (payload.get("platform") or "").strip()
    user = security.authenticate_user(username, password)
    if not user:
        log_network("pocket_password_login_failed", username=username, device_id=device_id, remote_addr=_client_ip())
        return _json_error("authentication_failed", 401)
    raw_token = secrets.token_urlsafe(48)
    _save_pocket_device(device_id, raw_token, device_name, platform, user.username, user.user_id)
    log_network(
        "pocket_password_login",
        device_id=device_id,
        device_name=device_name,
        platform=platform,
        username=user.username,
        user_id=user.user_id,
        remote_addr=_client_ip(),
    )
    return jsonify(
        {
            "device_id": device_id,
            "device_token": raw_token,
            "token_type": "Bearer",
            "username": user.username,
            "display_name": user.display_name,
        }
    )


@pocket_api_bp.route("/auth/logout-device", methods=["POST"])
def logout_device_route():
    device, error = require_pocket_auth()
    if error:
        return error
    data._get_conn().execute(
        "UPDATE pocket_devices SET revoked_at = ? WHERE device_id = ?",
        (_utc_now_sql(), device["device_id"]),
    )
    data._get_conn().commit()
    log_network("pocket_logout_device", device_id=device["device_id"], username=device.get("username"))
    return jsonify({"ok": True})


@pocket_api_bp.route("/sync/manifest", methods=["GET"])
def sync_manifest_route():
    device, error = require_pocket_auth()
    if error:
        return error
    user_error = require_bound_pocket_user(device)
    if user_error:
        return user_error
    log_network("pocket_manifest_start", device_id=device["device_id"], username=device.get("username"), user_id=device.get("user_id"))
    items = []
    skipped = 0
    errors = []
    error_count = 0
    rows = _note_rows(user_id=device.get("user_id"))
    mobile_rows = _mobile_file_rows(user_id=device.get("user_id"))
    total_records = len(rows) + len(mobile_rows)
    root = _notes_root(user_id=device.get("user_id"), notes=rows)
    include_front_matter = str(request.args.get("include_metadata") or "").strip().lower() in {"1", "true", "yes"}
    if not include_front_matter:
        include_front_matter = len(rows) <= int(current_app.config.get("LIFEPIM_POCKET_MANIFEST_FRONT_MATTER_LIMIT", POCKET_MANIFEST_FRONT_MATTER_LIMIT))
    include_file_dates = include_front_matter or str(request.args.get("include_file_dates") or "").strip().lower() in {"1", "true", "yes"}
    item_uuid_map = _item_uuid_map_for_notes(rows, user_id=device.get("user_id"))
    cached_sha_map = _cached_note_sha_map([note.get("id") for note in rows])
    mobile_item_uuid_map = _item_uuid_map_for_mobile_files(mobile_rows)
    mobile_cached_sha_map = _cached_mobile_file_sha_map([row.get("mobile_file_id") for row in mobile_rows])
    area_folder_rows = _area_folder_rows_for_manifest(device.get("user_id"))
    processed_count = 0
    for idx, note in enumerate(rows, start=1):
        processed_count += 1
        try:
            note_path = notes_routes._build_note_path(note)
            state = _metadata_from_note_row(note)
            if include_file_dates:
                state = _state_with_file_created_at(state, note_path)
            if not note_path:
                skipped += 1
                error_count += 1
                errors.append({"note_id": note.get("id"), "error": "missing_note_path"})
                continue
            items.append(
                _serialize_note_item(
                    note,
                    include_content=False,
                    root=root,
                    state_override=state,
                    note_path_override=note_path,
                    user_id=device.get("user_id"),
                    include_front_matter=include_front_matter,
                    item_uuid=item_uuid_map.get(int(note["id"])),
                    cached_sha=cached_sha_map.get(int(note["id"]), ""),
                    area_folder_rows=area_folder_rows,
                    allow_file_stat=include_file_dates,
                )
            )
        except Exception as exc:
            skipped += 1
            error_count += 1
            error_info = {
                "note_id": note.get("id"),
                "file_name": note.get("file_name") or "",
                "path": note.get("path") or "",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            if len(errors) < 25:
                errors.append(error_info)
            log_network(
                "pocket_manifest_item_error",
                device_id=device["device_id"],
                user_id=device.get("user_id"),
                username=device.get("username"),
                **error_info,
            )
            continue
        if idx % 500 == 0:
            log_network(
                "pocket_manifest_progress",
                device_id=device["device_id"],
                processed_count=processed_count,
                total_count=total_records,
                item_count=len(items),
                skipped_count=skipped,
            )
    for mobile_row in mobile_rows:
        processed_count += 1
        try:
            mobile_file_id = int(mobile_row["mobile_file_id"])
            items.append(
                _serialize_mobile_file_item(
                    mobile_row,
                    include_content=False,
                    item_uuid=mobile_item_uuid_map.get(mobile_file_id),
                    cached_sha=mobile_cached_sha_map.get(mobile_file_id, ""),
                )
            )
        except Exception as exc:
            skipped += 1
            error_count += 1
            error_info = {
                "mobile_file_id": mobile_row.get("mobile_file_id"),
                "relative_path": mobile_row.get("relative_path") or "",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            if len(errors) < 25:
                errors.append(error_info)
            log_network(
                "pocket_manifest_mobile_file_error",
                device_id=device["device_id"],
                user_id=device.get("user_id"),
                username=device.get("username"),
                **error_info,
            )
        if processed_count % 500 == 0:
            log_network(
                "pocket_manifest_progress",
                device_id=device["device_id"],
                processed_count=processed_count,
                total_count=total_records,
                item_count=len(items),
                skipped_count=skipped,
            )
    data._get_conn().commit()
    log_network(
        "pocket_manifest_finish",
        device_id=device["device_id"],
        username=device.get("username"),
        user_id=device.get("user_id"),
        item_count=len(items),
        skipped_count=skipped,
        error_count=error_count,
        total_count=total_records,
        note_count=len(rows),
        mobile_file_count=len(mobile_rows),
        root=root,
        front_matter_included=include_front_matter,
        file_dates_included=include_file_dates,
    )
    payload = {
        "generated_at": _utc_now().isoformat(),
        "items": items,
        "skipped_count": skipped,
        "error_count": error_count,
        "front_matter_included": include_front_matter,
        "file_dates_included": include_file_dates,
    }
    if errors:
        payload["errors"] = errors
    return jsonify(payload)


@pocket_api_bp.route("/items/<item_id>", methods=["GET"])
def item_route(item_id):
    device, error = require_pocket_auth()
    if error:
        return error
    user_error = require_bound_pocket_user(device)
    if user_error:
        return user_error
    note_id = _note_id_for_item(item_id)
    note = _note_row_by_id(note_id, user_id=device.get("user_id")) if note_id is not None else None
    if not note:
        mobile_file_id = _mobile_file_id_for_item(item_id)
        mobile_file = (
            _mobile_file_row_by_id(mobile_file_id, user_id=device.get("user_id"))
            if mobile_file_id is not None
            else None
        )
        if not mobile_file:
            log_network("pocket_item_not_found_or_forbidden", device_id=device["device_id"], user_id=device.get("user_id"), item_id=item_id, note_id=note_id)
            return _json_error("not_found", 404)
        log_network(
            "pocket_mobile_file_download",
            device_id=device["device_id"],
            user_id=device.get("user_id"),
            item_id=item_id,
            mobile_file_id=mobile_file_id,
            relative_path=mobile_file.get("relative_path"),
            kind=mobile_file.get("kind"),
        )
        return jsonify(_serialize_mobile_file_item(mobile_file, include_content=True, item_uuid=item_id))
    note_path = notes_routes._build_note_path(note)
    if not note_path or not os.path.isfile(note_path):
        log_network("pocket_item_file_missing", device_id=device["device_id"], item_id=item_id, note_id=note_id, note_path=note_path)
        return _json_error("not_found", 404)
    state = notes_routes._note_file_state(note_path)
    _upsert_item_state("note", note_id, note_path, state)
    log_network(
        "pocket_item_download",
        device_id=device["device_id"],
        item_id=item_id,
        note_id=note_id,
        relative_path=_relative_note_path(note),
        size=state.get("size") if state else None,
    )
    return jsonify(_serialize_note_item(note, include_content=True, user_id=device.get("user_id")))


def _push_one_item(payload_item, device):
    if _payload_operation(payload_item) == "DELETE":
        if _is_mobile_file_payload(payload_item):
            return _delete_mobile_file_from_payload(payload_item, device)
        return _delete_note_from_mobile(payload_item, device)
    if _is_mobile_file_payload(payload_item):
        return _upsert_mobile_file_from_payload(payload_item, device)
    item_id = _payload_id(payload_item)
    note_id = _note_id_for_item(item_id)
    if note_id is None:
        note_id = _note_id_for_client_item(device.get("device_id"), item_id)
    note = _note_row_by_id(note_id, user_id=device.get("user_id")) if note_id is not None else None
    if not note:
        note = _note_by_mobile_file_name(payload_item, device)
        if note and item_id:
            _upsert_client_item_map(device.get("device_id"), item_id, "note", note["id"])
    if not note:
        if _payload_content(payload_item) is not None:
            return _create_note_from_mobile(payload_item, device)
        return {"id": item_id, "ok": False, "error": "not_found", "debug": _payload_debug(payload_item)}
    note_id = note["id"]
    note_path = notes_routes._build_note_path(note)
    if not note_path:
        return {"id": item_id, "ok": False, "error": "invalid_note_path"}
    current_state = notes_routes._note_file_state(note_path)
    base_sha = (payload_item.get("base_sha256") or payload_item.get("sha256") or "").strip()
    content = _payload_content(payload_item)
    if content is None:
        return {"id": item_id, "ok": False, "error": "missing_content", "debug": _payload_debug(payload_item)}
    next_content_hash = _content_sha256(content)
    if base_sha and current_state and current_state.get("sha256") != base_sha and current_state.get("sha256") != next_content_hash:
        payload_ts = _parse_payload_modified_at(payload_item)
        server_ts = _state_timestamp(current_state, note_path)
        mobile_is_newer = payload_ts is not None and server_ts is not None and payload_ts > server_ts
        if not mobile_is_newer:
            return {
                "id": item_id,
                "client_change_id": _payload_client_change_id(payload_item),
                "server_item_id": _item_uuid_for_note(note_id, device.get("user_id")),
                "ok": False,
                "conflict": True,
                "error": "conflict",
                "server": _serialize_note_item(note, include_content=True, user_id=device.get("user_id")),
            }
        log_network(
            "pocket_push_mobile_newer_overwrite",
            device_id=device.get("device_id"),
            username=device.get("username"),
            user_id=device.get("user_id"),
            item_id=item_id,
            note_id=note_id,
            payload_modified_at=payload_item.get("modified_at") or payload_item.get("modifiedAt"),
            server_mtime=server_ts,
        )
    elif base_sha and current_state and current_state.get("sha256") != base_sha and current_state.get("sha256") == next_content_hash:
        if item_id:
            _upsert_client_item_map(device.get("device_id"), item_id, "note", note_id)
        _upsert_item_state("note", note_id, note_path, current_state)
        return {
            "id": item_id or _item_uuid_for_note(note_id, device.get("user_id")),
            "client_change_id": _payload_client_change_id(payload_item),
            "server_item_id": _item_uuid_for_note(note_id, device.get("user_id")),
            "ok": True,
            "item": _serialize_note_item(
                note,
                include_content=False,
                state_override=current_state,
                note_path_override=note_path,
                user_id=device.get("user_id"),
            ),
        }
    next_state = notes_routes._write_note_file_content(note_path, str(content))
    attachment_result = _write_payload_attachments(payload_item, note_path)
    if item_id:
        _upsert_client_item_map(device.get("device_id"), item_id, "note", note_id)
    _upsert_item_state("note", note_id, note_path, next_state)
    _update_note_metadata(note_id, note, next_state, area_override=_payload_area(payload_item))
    updated_note = _note_row_by_id(note_id, user_id=device.get("user_id"))
    item = _serialize_note_item(updated_note, include_content=False, user_id=device.get("user_id"))
    return {
        "id": item_id or item["id"],
        "client_change_id": _payload_client_change_id(payload_item),
        "server_item_id": item["id"],
        "ok": True,
        "item": item,
        "attachments_saved": attachment_result["saved"],
        "attachment_errors": attachment_result["errors"],
    }


@pocket_api_bp.route("/sync/push", methods=["POST"], strict_slashes=False)
@pocket_api_bp.route("/sync/upload", methods=["POST"], strict_slashes=False)
@pocket_api_bp.route("/sync/uploads", methods=["POST"], strict_slashes=False)
@pocket_api_bp.route("/sync/mobile", methods=["POST"], strict_slashes=False)
@pocket_api_bp.route("/sync/mobile-to-desktop", methods=["POST"], strict_slashes=False)
@pocket_api_bp.route("/push", methods=["POST"], strict_slashes=False)
def sync_push_route():
    device, error = require_pocket_auth()
    if error:
        return error
    user_error = require_bound_pocket_user(device)
    if user_error:
        return user_error
    payload = request.get_json(silent=True) or {}
    incoming_items = None
    for key in ("items", "changes", "uploads", "notes", "dirty_items", "dirtyItems", "local_items", "localItems"):
        if key in payload:
            incoming_items = payload.get(key) or []
            break
    if incoming_items is None:
        incoming_items = [payload]
    if not isinstance(incoming_items, list):
        log_network("pocket_push_invalid", device_id=device["device_id"], reason="invalid_items", payload_keys=sorted(payload.keys()))
        return _json_error("invalid_items", 400)
    log_network(
        "pocket_push_start",
        device_id=device["device_id"],
        username=device.get("username"),
        user_id=device.get("user_id"),
        path=request.path,
        content_length=request.content_length,
        item_count=len(incoming_items),
        payload_keys=sorted(payload.keys()),
        item_debug=[_payload_debug(item or {}) for item in incoming_items[:5]],
    )
    results = [_push_one_item(item or {}, device) for item in incoming_items]
    for result in results:
        if not result.get("ok"):
            log_network(
                "pocket_push_item_error",
                device_id=device["device_id"],
                username=device.get("username"),
                item_id=result.get("id"),
                error=result.get("error"),
                conflict=bool(result.get("conflict")),
                debug=result.get("debug"),
            )
    status = 409 if any(result.get("conflict") for result in results) else (400 if any(not result.get("ok") for result in results) else 200)
    log_network(
        "pocket_push_finish",
        device_id=device["device_id"],
        username=device.get("username"),
        user_id=device.get("user_id"),
        path=request.path,
        item_count=len(incoming_items),
        ok_count=len([result for result in results if result.get("ok")]),
        conflict_count=len([result for result in results if result.get("conflict")]),
        error_count=len([result for result in results if not result.get("ok") and not result.get("conflict")]),
        status_code=status,
    )
    accepted = []
    for result in results:
        if not result.get("ok"):
            continue
        item = result.get("item") or {}
        accepted.append(
            {
                "client_change_id": result.get("client_change_id") or "",
                "server_item_id": result.get("server_item_id") or item.get("id") or result.get("id") or "",
                "version": item.get("version") or 0,
                "sha256": item.get("sha256") or "",
            }
        )
    return jsonify({"ok": all(result.get("ok") for result in results), "results": results, "accepted": accepted}), status
