from __future__ import annotations

import os
import re
import shutil
import sys
import uuid
import hashlib
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from common import config as cfg
from common import data
from common import settings as settings_mod
from common.network_log import log_network


logger_api_bp = Blueprint("logger_api", __name__, url_prefix="/api/logger/v1")

ALLOWED_LOG_TYPES = {"movement", "phone_usage", "device", "service"}
LOGGER_PATH_RE = re.compile(r"^(movement|phone_usage|device|service)/(\d{4}-\d{2}-\d{2})\.jsonl$")


def _utc_now_sql():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _client_ip():
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    return forwarded or request.remote_addr or ""


def _json_error(error, status_code=400, relative_path=""):
    payload = {"status": "error", "stored": False, "error": error}
    if relative_path:
        payload["relative_path"] = relative_path
    return jsonify(payload), status_code


def ensure_logger_schema(conn=None):
    conn = data._get_conn() if conn is None else conn
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lp_logger_device (
            logger_device_id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_uuid TEXT NOT NULL UNIQUE,
            device_name TEXT NOT NULL DEFAULT '',
            device_folder TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_sync_at TEXT,
            app_version TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lp_logger_sync_run (
            logger_sync_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_run_uuid TEXT,
            logger_device_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            files_attempted INTEGER NOT NULL DEFAULT 0,
            files_succeeded INTEGER NOT NULL DEFAULT 0,
            files_failed INTEGER NOT NULL DEFAULT 0,
            bytes_received INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            message TEXT,
            remote_address TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lp_logger_sync_file (
            logger_sync_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            logger_sync_run_id INTEGER NOT NULL,
            logger_device_id INTEGER NOT NULL,
            relative_path TEXT NOT NULL,
            log_type TEXT NOT NULL,
            file_date TEXT,
            destination_path TEXT,
            file_size INTEGER NOT NULL DEFAULT 0,
            last_modified INTEGER,
            received_at TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_logger_run_device_started
            ON lp_logger_sync_run(logger_device_id, started_at DESC);
        CREATE INDEX IF NOT EXISTS ix_logger_file_path
            ON lp_logger_sync_file(logger_device_id, relative_path, received_at DESC);
        """
    )
    conn.commit()


def _settings(conn=None, user_id=None, username=None):
    return settings_mod.get_logger_settings(conn, user_id=user_id, username=username)


def logger_raw_root(settings=None, conn=None, user_id=None, username=None):
    settings = settings or _settings(conn, user_id=user_id, username=username)
    root = settings.get("raw_data_root") or "admin/logged_data/raw"
    if os.path.isabs(root):
        return os.path.abspath(root)
    return os.path.abspath(os.path.join(getattr(cfg, "user_folder", os.getcwd()), root))


def safe_device_folder(device_name, device_uuid, conn=None):
    base = re.sub(r"[^a-z0-9]+", "-", (device_name or "logger-device").lower()).strip("-")
    base = base[:80] or "logger-device"
    conn = data._get_conn() if conn is None else conn
    existing = conn.execute(
        "SELECT device_uuid FROM lp_logger_device WHERE device_folder = ? AND device_uuid != ?",
        (base, device_uuid),
    ).fetchone()
    if existing:
        short_uuid = re.sub(r"[^a-fA-F0-9]", "", device_uuid or "")[:8] or uuid.uuid4().hex[:8]
        return f"{base}-{short_uuid}"
    return base


def _validate_relative_path(relative_path):
    text = (relative_path or "").replace("\\", "/").strip()
    if os.path.isabs(text) or ".." in text.split("/"):
        raise ValueError("Invalid log path")
    match = LOGGER_PATH_RE.match(text)
    if not match:
        raise ValueError("Invalid log path")
    return text, match.group(1), match.group(2)


def _destination_for(relative_path, device_folder, settings=None):
    safe_relative, log_type, file_date = _validate_relative_path(relative_path)
    root = logger_raw_root(settings)
    destination = os.path.abspath(os.path.join(root, device_folder, safe_relative))
    allowed_root = os.path.abspath(root)
    if os.path.commonpath([allowed_root, destination]) != allowed_root:
        raise ValueError("Invalid destination")
    return destination, log_type, file_date


def _require_auth(conn=None):
    conn = data._get_conn() if conn is None else conn
    settings = _settings(conn)
    if not settings.get("enabled"):
        return None, _json_error("logger_api_disabled", 403), settings
    expected = (settings.get("sync_token") or "").strip()
    auth_header = request.headers.get("Authorization") or ""
    raw_token = auth_header[len("Bearer ") :].strip() if auth_header.startswith("Bearer ") else ""
    device_uuid = (request.headers.get("X-LifePIM-Logger-Device-ID") or request.form.get("device_id") or "").strip()
    device_name = (request.headers.get("X-LifePIM-Logger-Device-Name") or request.form.get("device_name") or "").strip()
    if not raw_token or not device_uuid:
        log_network("logger_auth_failed", device_id=device_uuid, remote_addr=_client_ip(), path=request.path)
        return None, _json_error("unauthorized", 401), settings
    if expected and raw_token != expected and not _valid_pocket_device_token(conn, device_uuid, raw_token):
        log_network("logger_auth_failed", device_id=device_uuid, remote_addr=_client_ip(), path=request.path)
        return None, _json_error("unauthorized", 401), settings
    if not expected and not _valid_pocket_device_token(conn, device_uuid, raw_token):
        log_network("logger_auth_failed", device_id=device_uuid, remote_addr=_client_ip(), path=request.path)
        return None, _json_error("unauthorized", 401), settings
    device = _upsert_device(device_uuid, device_name or "Logger Device", conn)
    log_network("logger_auth_ok", device_id=device_uuid, device_name=device.get("device_name"), remote_addr=_client_ip(), path=request.path)
    return device, None, settings


def _valid_pocket_device_token(conn, device_uuid, raw_token):
    try:
        row = conn.execute(
            """
            SELECT 1 FROM pocket_devices
            WHERE device_id = ? AND token_hash = ? AND revoked_at IS NULL
            """,
            (device_uuid, hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()),
        ).fetchone()
        return bool(row)
    except Exception:
        return False


def _upsert_device(device_uuid, device_name, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    now = _utc_now_sql()
    row = conn.execute("SELECT * FROM lp_logger_device WHERE device_uuid = ?", (device_uuid,)).fetchone()
    if row:
        folder = row["device_folder"] or safe_device_folder(device_name, device_uuid, conn)
        conn.execute(
            """
            UPDATE lp_logger_device
               SET device_name = ?, device_folder = ?, last_seen_at = ?, updated_at = ?, is_active = 1
             WHERE device_uuid = ?
            """,
            (device_name, folder, now, now, device_uuid),
        )
    else:
        folder = safe_device_folder(device_name, device_uuid, conn)
        conn.execute(
            """
            INSERT INTO lp_logger_device
            (device_uuid, device_name, device_folder, first_seen_at, last_seen_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (device_uuid, device_name, folder, now, now, now, now),
        )
    conn.commit()
    return dict(conn.execute("SELECT * FROM lp_logger_device WHERE device_uuid = ?", (device_uuid,)).fetchone())


def _get_or_create_run(device, sync_run_uuid, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    now = _utc_now_sql()
    sync_run_uuid = (sync_run_uuid or "").strip()
    if sync_run_uuid:
        row = conn.execute(
            "SELECT * FROM lp_logger_sync_run WHERE sync_run_uuid = ? AND logger_device_id = ?",
            (sync_run_uuid, device["logger_device_id"]),
        ).fetchone()
        if row:
            return dict(row)
    conn.execute(
        """
        INSERT INTO lp_logger_sync_run
        (sync_run_uuid, logger_device_id, started_at, status, remote_address, created_at)
        VALUES (?, ?, ?, 'running', ?, ?)
        """,
        (sync_run_uuid, device["logger_device_id"], now, _client_ip(), now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM lp_logger_sync_run WHERE logger_sync_run_id = last_insert_rowid()").fetchone())


def _update_run(logger_sync_run_id, status, message="", bytes_received=0, succeeded=False, failed=False, conn=None):
    conn = data._get_conn() if conn is None else conn
    now = _utc_now_sql()
    conn.execute(
        """
        UPDATE lp_logger_sync_run
           SET finished_at = ?,
               files_attempted = files_attempted + 1,
               files_succeeded = files_succeeded + ?,
               files_failed = files_failed + ?,
               bytes_received = bytes_received + ?,
               message = ?
         WHERE logger_sync_run_id = ?
        """,
        (now, 1 if succeeded else 0, 1 if failed else 0, int(bytes_received or 0), message, logger_sync_run_id),
    )
    row = conn.execute(
        "SELECT files_succeeded, files_failed FROM lp_logger_sync_run WHERE logger_sync_run_id = ?",
        (logger_sync_run_id,),
    ).fetchone()
    if row and row["files_succeeded"] and row["files_failed"]:
        status = "partial"
    elif row and row["files_failed"]:
        status = "failed"
    elif row and row["files_succeeded"]:
        status = "success"
    conn.execute(
        "UPDATE lp_logger_sync_run SET status = ? WHERE logger_sync_run_id = ?",
        (status, logger_sync_run_id),
    )
    conn.commit()


def _write_uploaded_file(upload, destination, expected_size=None):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    tmp_path = destination + ".part"
    try:
        with open(tmp_path, "wb") as handle:
            shutil.copyfileobj(upload.stream, handle)
            handle.flush()
            os.fsync(handle.fileno())
        bytes_received = os.path.getsize(tmp_path)
        if expected_size is not None and int(expected_size) >= 0 and bytes_received != int(expected_size):
            raise ValueError("Received byte count does not match file_size")
        replaced = os.path.exists(destination)
        os.replace(tmp_path, destination)
        return bytes_received, "replaced" if replaced else "stored"
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def _record_file(run, device, relative_path, log_type, file_date, destination, file_size, last_modified, status, error="", conn=None):
    conn = data._get_conn() if conn is None else conn
    now = _utc_now_sql()
    conn.execute(
        """
        INSERT INTO lp_logger_sync_file
        (logger_sync_run_id, logger_device_id, relative_path, log_type, file_date, destination_path,
         file_size, last_modified, received_at, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run["logger_sync_run_id"],
            device["logger_device_id"],
            relative_path,
            log_type,
            file_date,
            destination,
            int(file_size or 0),
            int(last_modified or 0) if str(last_modified or "").strip() else None,
            now,
            status,
            error,
            now,
        ),
    )
    if status in {"stored", "replaced"}:
        conn.execute(
            "UPDATE lp_logger_device SET last_sync_at = ?, updated_at = ? WHERE logger_device_id = ?",
            (now, now, device["logger_device_id"]),
        )
    conn.commit()


@logger_api_bp.route("/status", methods=["GET"])
def status_route():
    conn = data._get_conn()
    ensure_logger_schema(conn)
    device, error, settings = _require_auth(conn)
    if error:
        return error
    return jsonify(
        {
            "status": "ok",
            "service": "lifepim-logger-sync",
            "api_version": 1,
            "desktop_name": "LifePIM Desktop",
            "upload_available": bool(settings.get("enabled")),
        }
    )


@logger_api_bp.route("/upload", methods=["POST"])
def upload_route():
    conn = data._get_conn()
    ensure_logger_schema(conn)
    device, error, settings = _require_auth(conn)
    if error:
        return error
    max_bytes = int(settings.get("max_upload_mb") or 50) * 1024 * 1024
    if request.content_length and request.content_length > max_bytes:
        return _json_error("file_too_large", 413, request.form.get("relative_path") or "")

    relative_path = (request.form.get("relative_path") or "").strip().replace("\\", "/")
    sync_run_uuid = request.form.get("sync_run_uuid") or ""
    run = _get_or_create_run(device, sync_run_uuid, conn)
    try:
        destination, log_type, file_date = _destination_for(relative_path, device["device_folder"], settings)
        uploaded_file = request.files.get("file")
        if uploaded_file is None:
            raise ValueError("Missing file")
        form_log_type = (request.form.get("log_type") or log_type).strip()
        if form_log_type != log_type or log_type not in ALLOWED_LOG_TYPES:
            raise ValueError("Invalid log path")
        file_size = int(request.form.get("file_size") or 0)
        bytes_received, file_status = _write_uploaded_file(uploaded_file, destination, file_size if file_size else None)
        _record_file(
            run,
            device,
            relative_path,
            log_type,
            file_date,
            destination,
            bytes_received,
            request.form.get("last_modified") or "",
            file_status,
            conn=conn,
        )
        _update_run(run["logger_sync_run_id"], "success", "File stored.", bytes_received, succeeded=True, conn=conn)
        log_network(
            "logger_upload_success",
            device_id=device["device_uuid"],
            device_name=device["device_name"],
            relative_path=relative_path,
            destination_path=destination,
            bytes_received=bytes_received,
            remote_addr=_client_ip(),
        )
        return jsonify(
            {
                "status": "ok",
                "relative_path": relative_path,
                "stored": True,
                "bytes_received": bytes_received,
                "stored_at": _utc_now_sql(),
            }
        )
    except Exception as exc:
        error_message = str(exc) or type(exc).__name__
        try:
            log_type = request.form.get("log_type") or ""
            file_date = request.form.get("file_date") or ""
            _record_file(
                run,
                device,
                relative_path,
                log_type,
                file_date,
                "",
                int(request.form.get("file_size") or 0),
                request.form.get("last_modified") or "",
                "rejected" if isinstance(exc, ValueError) else "failed",
                error_message,
                conn,
            )
            _update_run(run["logger_sync_run_id"], "failed", error_message, 0, failed=True, conn=conn)
        except Exception:
            conn.rollback()
        log_network(
            "logger_upload_failed",
            device_id=device.get("device_uuid"),
            relative_path=relative_path,
            error=error_message,
            remote_addr=_client_ip(),
        )
        return _json_error(error_message, 400, relative_path)


def logger_summary(conn=None, settings=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    settings = settings or _settings(conn)
    root = logger_raw_root(settings)
    files = list_raw_files(conn=conn, settings=settings)
    today = datetime.now().strftime("%Y-%m-%d")
    last_success = conn.execute(
        "SELECT MAX(finished_at) AS value FROM lp_logger_sync_run WHERE status = 'success'"
    ).fetchone()["value"]
    devices = conn.execute("SELECT COUNT(1) AS cnt FROM lp_logger_device WHERE is_active = 1").fetchone()["cnt"]
    return {
        "enabled": settings.get("enabled"),
        "raw_folder": root,
        "devices": devices,
        "last_successful_sync": last_success or "",
        "files_received_today": sum(1 for item in files if (item.get("received_at") or "").startswith(today)),
        "stored_files": len(files),
        "raw_data_size": sum(item.get("size") or 0 for item in files),
    }


def recent_sync_runs(limit=100, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    rows = conn.execute(
        """
        SELECT r.*, d.device_name, d.device_uuid
        FROM lp_logger_sync_run r
        JOIN lp_logger_device d ON d.logger_device_id = r.logger_device_id
        ORDER BY r.started_at DESC
        LIMIT ?
        """,
        (int(limit or 100),),
    ).fetchall()
    return [dict(row) for row in rows]


def run_files(logger_sync_run_id, conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    rows = conn.execute(
        """
        SELECT f.*, d.device_name, d.device_uuid
        FROM lp_logger_sync_file f
        JOIN lp_logger_device d ON d.logger_device_id = f.logger_device_id
        WHERE f.logger_sync_run_id = ?
        ORDER BY f.created_at, f.relative_path
        """,
        (logger_sync_run_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def list_devices(conn=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    rows = conn.execute(
        "SELECT * FROM lp_logger_device ORDER BY last_seen_at DESC, device_name"
    ).fetchall()
    return [dict(row) for row in rows]


def list_raw_files(filters=None, conn=None, settings=None):
    conn = data._get_conn() if conn is None else conn
    ensure_logger_schema(conn)
    filters = filters or {}
    root = logger_raw_root(settings)
    metadata_rows = conn.execute(
        """
        SELECT f.*
        FROM lp_logger_sync_file f
        JOIN (
            SELECT logger_device_id, relative_path, MAX(logger_sync_file_id) AS max_id
            FROM lp_logger_sync_file
            GROUP BY logger_device_id, relative_path
        ) latest ON latest.max_id = f.logger_sync_file_id
        """
    ).fetchall()
    meta_by_key = {(row["logger_device_id"], row["relative_path"]): dict(row) for row in metadata_rows}
    devices = list_devices(conn)
    devices_by_folder = {row["device_folder"]: row for row in devices}
    items = []
    if not os.path.isdir(root):
        return items
    for device_folder in sorted(os.listdir(root)):
        device_root = os.path.join(root, device_folder)
        if not os.path.isdir(device_root):
            continue
        device = devices_by_folder.get(device_folder, {"device_name": device_folder, "logger_device_id": None})
        for log_type in sorted(ALLOWED_LOG_TYPES):
            type_root = os.path.join(device_root, log_type)
            if not os.path.isdir(type_root):
                continue
            for filename in sorted(os.listdir(type_root), reverse=True):
                relative_path = f"{log_type}/{filename}"
                try:
                    _validate_relative_path(relative_path)
                except ValueError:
                    continue
                full_path = os.path.join(type_root, filename)
                if not os.path.isfile(full_path):
                    continue
                stat = os.stat(full_path)
                meta = meta_by_key.get((device.get("logger_device_id"), relative_path), {})
                item = {
                    "file_date": filename[:10],
                    "device": device.get("device_name") or device_folder,
                    "device_folder": device_folder,
                    "log_type": log_type,
                    "filename": filename,
                    "relative_path": relative_path,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "received_at": meta.get("received_at") or "",
                    "status": meta.get("status") or "stored",
                    "full_path": full_path,
                }
                if filters.get("device") and filters["device"] not in {device_folder, item["device"]}:
                    continue
                if filters.get("log_type") and filters["log_type"] != log_type:
                    continue
                if filters.get("file_date") and filters["file_date"] != item["file_date"]:
                    continue
                if filters.get("filename") and filters["filename"].lower() not in filename.lower():
                    continue
                items.append(item)
    items.sort(key=lambda row: (row["file_date"], row["log_type"], row["filename"]), reverse=True)
    return items


def resolve_raw_file(device_folder, relative_path, settings=None):
    settings = settings or _settings()
    destination, _log_type, _file_date = _destination_for(relative_path, device_folder, settings)
    root = logger_raw_root(settings)
    if os.path.commonpath([root, destination]) != root or not os.path.isfile(destination):
        return ""
    return destination


def open_path_in_file_browser(path):
    if sys.platform.startswith("win"):
        os.startfile(path)
    elif sys.platform == "darwin":
        import subprocess

        subprocess.Popen(["open", path])
    else:
        import subprocess

        subprocess.Popen(["xdg-open", path])
