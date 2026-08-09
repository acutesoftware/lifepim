import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from common import config as cfg
from common.media_schema import ensure_media_schema


APP_ICON_MEDIA_DIR = Path("Media") / "imported" / "icons"


def materialize_app_icon_value(icon_value, conn=None):
    source_path = _source_path_for_icon_value(icon_value)
    if not source_path or not source_path.is_file():
        return icon_value or ""
    destination = _copy_icon_to_media(source_path)
    media_id = _upsert_icon_media_row(destination, conn=conn)
    return f"/media/file/{media_id}" if media_id else (icon_value or "")


def _source_path_for_icon_value(icon_value):
    text = (icon_value or "").strip()
    if not text:
        return None
    if text.startswith("/static/"):
        src_root = Path(__file__).resolve().parents[3]
        return src_root / text.lstrip("/").replace("/", os.sep)
    if text.startswith("static/"):
        src_root = Path(__file__).resolve().parents[3]
        return src_root / text.replace("/", os.sep)
    path = Path(os.path.expandvars(os.path.expanduser(text.strip('"'))))
    return path if path.is_absolute() else None


def _copy_icon_to_media(source_path):
    digest = _file_sha256(source_path)
    suffix = source_path.suffix.lower() or ".ico"
    destination_dir = Path(_data_folder()) / APP_ICON_MEDIA_DIR
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{digest[:24]}{suffix}"
    if not destination.exists() or destination.stat().st_size != source_path.stat().st_size:
        shutil.copy2(source_path, destination)
    return destination


def _data_folder():
    return Path(cfg.data_folder)


def _upsert_icon_media_row(icon_path, conn=None):
    if conn is None:
        from common import data as db

        conn = db._get_conn()
    ensure_media_schema(conn)
    stat = icon_path.stat()
    filename = icon_path.name
    ext = icon_path.suffix.lower().lstrip(".") or "ico"
    path_text = str(icon_path)
    mtime_utc = _timestamp_utc(stat.st_mtime)
    ctime_utc = _timestamp_utc(stat.st_ctime)
    digest = _file_sha256(icon_path)
    row = conn.execute("SELECT media_id FROM lp_media WHERE path = ?", (path_text,)).fetchone()
    if row:
        media_id = row["media_id"] if hasattr(row, "keys") else row[0]
        conn.execute(
            "UPDATE lp_media SET filename = ?, ext = ?, media_type = ?, size_bytes = ?, "
            "mtime_utc = ?, ctime_utc = ?, hash = ? WHERE media_id = ?",
            (filename, ext, "image", stat.st_size, mtime_utc, ctime_utc, digest, media_id),
        )
        return media_id
    cur = conn.execute(
        "INSERT INTO lp_media (path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (path_text, filename, ext, "image", stat.st_size, mtime_utc, ctime_utc, digest),
    )
    return cur.lastrowid


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp_utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
