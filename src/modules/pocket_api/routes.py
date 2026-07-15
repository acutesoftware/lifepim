from __future__ import annotations

import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from common import data
from common.network_log import log_network
from common.utils import get_table_def
from modules.notes import routes as notes_routes


pocket_api_bp = Blueprint("pocket_api", __name__, url_prefix="/api/pocket/v1")

ITEM_NAMESPACE = uuid.UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f")
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


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
        CREATE TABLE IF NOT EXISTS pocket_user_settings (
            user_id INTEGER PRIMARY KEY,
            default_note_folder TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pocket_devices_token_hash ON pocket_devices(token_hash);
        CREATE INDEX IF NOT EXISTS idx_pocket_item_map_entity ON pocket_item_map(entity_type, entity_id);
        """
    )
    _add_column_if_missing(conn, "pocket_devices", "username", "TEXT")
    _add_column_if_missing(conn, "pocket_devices", "user_id", "INTEGER")
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


def _client_ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or request.remote_addr or ""


def _user_agent():
    return (request.headers.get("User-Agent") or "")[:500]


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
    where = "1=1"
    params = []
    if user_id is not None:
        if "owner_user_id" not in columns:
            log_network("pocket_note_security_missing_owner_column", table=tbl["name"])
            return []
        where = "owner_user_id = ?"
        params.append(user_id)
    rows = data._get_conn().execute(
        f"SELECT {', '.join(select_cols)} FROM {tbl['name']} WHERE {where} ORDER BY id",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


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
    return {
        "size": str(stat.st_size),
        "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "mtime_ns": stat.st_mtime_ns,
    }


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
    return {
        "size": str(size_value),
        "date_modified": note.get("date_modified") or note.get("rec_extract_date") or "",
        "modified_at": modified_at,
        "mtime_ns": mtime_ns,
    }


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
        where += " AND owner_user_id = ?"
        params.append(user_id)
    row = data._get_conn().execute(f"SELECT * FROM {tbl['name']} WHERE {where}", params).fetchone()
    return dict(row) if row else None


def _item_uuid_for_note(note_id):
    conn = data._get_conn()
    row = conn.execute(
        "SELECT item_uuid FROM pocket_item_map WHERE entity_type = 'note' AND entity_id = ?",
        (note_id,),
    ).fetchone()
    now = _utc_now_sql()
    if row:
        return row["item_uuid"]
    item_uuid = str(uuid.uuid5(ITEM_NAMESPACE, f"note:{int(note_id)}"))
    conn.execute(
        """
        INSERT OR IGNORE INTO pocket_item_map(item_uuid, entity_type, entity_id, created_at, last_seen_at)
        VALUES (?, 'note', ?, ?, ?)
        """,
        (item_uuid, note_id, now, now),
    )
    return item_uuid


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


def _notes_root(user_id=None):
    roots = []
    for note in _note_rows(user_id=user_id):
        path_value = notes_routes._normalize_note_path(note.get("path"))
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
    full_path = notes_routes._normalize_note_path(full_path)
    root = root if root is not None else _notes_root()
    try:
        if root and os.path.commonpath([root, full_path]).lower() == root.lower():
            return os.path.relpath(full_path, root).replace("\\", "/")
    except (OSError, ValueError):
        pass
    return os.path.basename(full_path)


def _iso_from_state_or_note(state, note):
    if state and state.get("modified_at"):
        return state.get("modified_at")
    if state:
        full_path = notes_routes._build_note_path(note)
        try:
            return datetime.fromtimestamp(os.path.getmtime(full_path), timezone.utc).isoformat()
        except OSError:
            pass
    return _iso_from_note_value(note.get("date_modified") or note.get("rec_extract_date") or "")


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


def _serialize_note_item(note, include_content=False, root=None, state_override=None, note_path_override=None):
    note_path = note_path_override or notes_routes._build_note_path(note)
    if include_content:
        state = notes_routes._note_file_state(note_path)
        _upsert_item_state("note", note["id"], note_path, state)
    else:
        state = state_override or _note_file_metadata(note_path)
    content = notes_routes._read_note_file(note_path) if include_content else None
    item = {
        "id": _item_uuid_for_note(note["id"]),
        "relative_path": _relative_note_path(note, root=root),
        "kind": _item_kind(note, content=content) if include_content else "NOTE",
        "ownership": "DESKTOP_MASTER",
        "sha256": state.get("sha256") if state and state.get("sha256") else _cached_item_sha("note", note["id"]),
        "version": _version_from_state(state),
        "modified_at": _iso_from_state_or_note(state, note),
    }
    if include_content:
        item["content"] = content
    return item


def _update_note_metadata(note_id, note, state):
    tbl = _note_table()
    values_map = {col: note.get(col, "") for col in tbl["col_list"]}
    if state:
        values_map["size"] = state.get("size", values_map.get("size", ""))
        values_map["date_modified"] = state.get("date_modified", values_map.get("date_modified", ""))
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
        return ""
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


def _payload_id(payload_item):
    for key in ("id", "item_id", "itemId", "server_id", "serverId", "uuid"):
        value = payload_item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


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
    }


def _unique_note_path(folder_path, file_name):
    base, ext = os.path.splitext(file_name)
    candidate = file_name
    idx = 2
    while os.path.exists(os.path.join(folder_path, candidate)):
        candidate = f"{base} {idx}{ext}"
        idx += 1
    return candidate, os.path.join(folder_path, candidate)


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

    tbl = _note_table()
    table_columns = _table_columns(data._get_conn(), tbl["name"])
    values_map = {
        "file_name": file_name,
        "path": folder_path,
        "folder_id": "",
        "size": state.get("size", "") if state else "",
        "date_modified": state.get("date_modified", "") if state else "",
        "project": payload_item.get("project") or "",
        "owner_user_id": device.get("user_id"),
        "visibility": "private",
        "is_public": 0,
        "show_in_blog": 0,
    }
    cols = [col for col in list(tbl["col_list"]) + ["owner_user_id", "visibility", "is_public", "show_in_blog"] if col in table_columns]
    record_id = data.add_record(data._get_conn(), tbl["name"], cols, [values_map.get(col, "") for col in cols])
    if not record_id:
        return {"id": payload_item.get("id") or "", "ok": False, "error": "create_failed"}
    _upsert_item_state("note", record_id, note_path, state)
    note = _note_row_by_id(record_id, user_id=device.get("user_id"))
    item = _serialize_note_item(note, include_content=False, state_override=state, note_path_override=note_path)
    log_network(
        "pocket_push_create_note",
        device_id=device.get("device_id"),
        username=device.get("username"),
        user_id=device.get("user_id"),
        note_id=record_id,
        file_name=file_name,
        folder_path=folder_path,
        client_id=payload_item.get("id"),
    )
    return {"id": _payload_id(payload_item) or item["id"], "ok": True, "created": True, "item": item}


@pocket_api_bp.route("/health", methods=["GET"])
def health_route():
    ensure_pocket_schema()
    return jsonify({"ok": True, "service": "lifepim-pocket", "version": 1})


@pocket_api_bp.route("/auth/register-device", methods=["POST"])
def register_device_route():
    ensure_pocket_schema()
    payload = request.get_json(silent=True) or {}
    device_id = (payload.get("device_id") or "").strip() or str(uuid.uuid4())
    device_name = (payload.get("device_name") or payload.get("name") or "").strip()
    platform = (payload.get("platform") or "").strip()
    username = (payload.get("username") or payload.get("user_name") or "").strip()
    user_id = _lookup_user_id(username)
    raw_token = secrets.token_urlsafe(48)
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
    return jsonify({"device_id": device_id, "device_token": raw_token, "token_type": "Bearer"})


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
    root = _notes_root(user_id=device.get("user_id"))
    items = []
    skipped = 0
    rows = _note_rows(user_id=device.get("user_id"))
    for idx, note in enumerate(rows, start=1):
        note_path = notes_routes._build_note_path(note)
        state = _metadata_from_note_row(note)
        if not note_path:
            skipped += 1
            continue
        items.append(_serialize_note_item(note, include_content=False, root=root, state_override=state, note_path_override=note_path))
        if idx % 500 == 0:
            log_network(
                "pocket_manifest_progress",
                device_id=device["device_id"],
                processed_count=idx,
                total_count=len(rows),
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
        total_count=len(rows),
        root=root,
    )
    return jsonify({"generated_at": _utc_now().isoformat(), "items": items})


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
        log_network("pocket_item_not_found_or_forbidden", device_id=device["device_id"], user_id=device.get("user_id"), item_id=item_id, note_id=note_id)
        return _json_error("not_found", 404)
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
    return jsonify(_serialize_note_item(note, include_content=True))


def _push_one_item(payload_item, device):
    item_id = _payload_id(payload_item)
    note_id = _note_id_for_item(item_id)
    note = _note_row_by_id(note_id, user_id=device.get("user_id")) if note_id is not None else None
    if not note:
        if _payload_content(payload_item) is not None:
            return _create_note_from_mobile(payload_item, device)
        return {"id": item_id, "ok": False, "error": "not_found", "debug": _payload_debug(payload_item)}
    note_path = notes_routes._build_note_path(note)
    if not note_path:
        return {"id": item_id, "ok": False, "error": "invalid_note_path"}
    current_state = notes_routes._note_file_state(note_path)
    base_sha = (payload_item.get("base_sha256") or payload_item.get("sha256") or "").strip()
    if base_sha and current_state and current_state.get("sha256") != base_sha:
        return {
            "id": item_id,
            "ok": False,
            "conflict": True,
            "error": "conflict",
            "server": _serialize_note_item(note, include_content=True),
        }
    content = _payload_content(payload_item)
    if content is None:
        return {"id": item_id, "ok": False, "error": "missing_content", "debug": _payload_debug(payload_item)}
    next_state = notes_routes._write_note_file_content(note_path, str(content))
    _upsert_item_state("note", note_id, note_path, next_state)
    _update_note_metadata(note_id, note, next_state)
    updated_note = _note_row_by_id(note_id)
    return {"id": item_id, "ok": True, "item": _serialize_note_item(updated_note, include_content=False)}


@pocket_api_bp.route("/sync/push", methods=["POST"])
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
        item_count=len(incoming_items),
        ok_count=len([result for result in results if result.get("ok")]),
        conflict_count=len([result for result in results if result.get("conflict")]),
        error_count=len([result for result in results if not result.get("ok") and not result.get("conflict")]),
        status_code=status,
    )
    return jsonify({"ok": all(result.get("ok") for result in results), "results": results}), status
