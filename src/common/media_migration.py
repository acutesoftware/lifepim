"""Import media and audio rows from the filelister SQLite database."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

import etl_folder_mapping as folder_etl
from common import config as cfg
from common import data as db
from common.media_schema import ensure_media_schema


IMAGE_SOURCE_TABLE = "u_image_files"
VIDEO_SOURCE_TABLE = "fl_video"
VIDEO_SOURCE_SQL = (
    "SELECT vid.filepath, vid.duration, vid.width, vid.height, vid.file_size, vid.title, "
    "vid.frame_rate, vid.size, vid.basename, vid.path, fl.folder_name, fl.modified, "
    "fl.created, fl.file_type, fl.hash "
    "FROM fl_video vid "
    "LEFT JOIN filelist_output fl ON fl.file_path = vid.filepath"
)
AUDIO_SOURCE_TABLE = "fl_audio"
AUDIO_SOURCE_SQL = (
    "SELECT aud.filepath, aud.size, aud.basename, aud.path, aud.title, aud.artist, aud.album, aud.date, aud.duration, "
    "fl.folder_name "
    "FROM fl_audio aud "
    "LEFT JOIN filelist_output fl ON fl.file_path = aud.filepath"
)
BATCH_SIZE = 1000
LEGACY_IMAGE_WHERE = r"WHERE (replace(path, '/', '\') LIKE '%\photo\%' OR replace(path, '/', '\') LIKE '%\photo')"
LEGACY_AUDIO_WHERE = r"WHERE (replace(path, '/', '\') LIKE '%\music\Music\%' OR replace(path, '/', '\') LIKE '%\music\Music')"


def default_image_where() -> str:
    return _upgrade_legacy_where(getattr(cfg, "FILELIST_IMAGE_WHERE", ""), "image")


def default_audio_where() -> str:
    return _upgrade_legacy_where(getattr(cfg, "FILELIST_AUDIO_WHERE", ""), "audio")


def migrate_images_from_filelist(
    filelist_db: Optional[str] = None,
    where_clause: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Replace LifePIM image/video media rows from the filelister database."""
    target = db._get_conn() if conn is None else conn
    source_path = _resolve_filelist_db(filelist_db)
    source_where = _validated_where_clause(where_clause if where_clause is not None else default_image_where())
    ensure_media_schema(target)
    _ensure_folder_support(target, "lp_media")
    _require_source_table(source_path, IMAGE_SOURCE_TABLE)
    _require_source_table(source_path, VIDEO_SOURCE_TABLE)
    _require_source_table(source_path, "filelist_output")

    target.execute("PRAGMA foreign_keys = OFF")
    _clear_media_tables(target)

    inserted = 0
    meta_inserted = 0
    video_inserted = 0
    video_meta_inserted = 0
    folder_cache: Dict[str, Optional[int]] = {}
    now_utc = _utc_now()

    source = _source_conn(source_path)
    try:
        rows = source.execute(
            "SELECT filepath, image_size, basename, path, filelist_size, modified, created, hash, "
            "width, height, format, lat, lon, cam_make, cam_model, exif_datetime, "
            "cam_date_digitized, thumb_sha1, phash, ahash "
            f"FROM {IMAGE_SOURCE_TABLE} {source_where}"
        )
        media_batch: List[tuple] = []
        meta_batch: List[tuple] = []
        for row in rows:
            filepath = _clean(row["filepath"])
            filename = _clean(row["basename"]) or os.path.basename(filepath)
            folder_path = _clean(row["path"]) or os.path.dirname(filepath)
            if not filepath or not filename:
                continue
            ext = _extension(filename or filepath, _clean(row["format"]))
            taken_utc = _normalize_datetime(row["exif_datetime"]) or _normalize_datetime(row["cam_date_digitized"])
            mtime_utc = _normalize_datetime(row["modified"]) or now_utc
            ctime_utc = _normalize_datetime(row["created"]) or mtime_utc
            folder_id = _folder_id(target, folder_path, folder_cache)
            media_batch.append(
                (
                    filepath,
                    filename,
                    ext,
                    "image",
                    _int_value(row["filelist_size"], _int_value(row["image_size"], 0)),
                    mtime_utc,
                    ctime_utc,
                    _first_text(row["hash"], row["thumb_sha1"], row["phash"], row["ahash"]),
                    folder_id,
                )
            )
            meta_batch.append(
                (
                    filepath,
                    taken_utc,
                    _int_value(row["width"]),
                    _int_value(row["height"]),
                    _float_value(row["lat"]),
                    _float_value(row["lon"]),
                    _clean(row["cam_make"]),
                    _clean(row["cam_model"]),
                )
            )
            if len(media_batch) >= BATCH_SIZE:
                inserted += _insert_media_batch(target, media_batch)
                meta_inserted += _insert_media_meta_batch(target, meta_batch)
                media_batch.clear()
                meta_batch.clear()
        inserted += _insert_media_batch(target, media_batch)
        meta_inserted += _insert_media_meta_batch(target, meta_batch)

        rows = source.execute(
            "SELECT filepath, duration, width, height, file_size, title, frame_rate, "
            "size, basename, path, folder_name, modified, created, file_type, hash "
            f"FROM ({VIDEO_SOURCE_SQL}) video_src {source_where}"
        )
        media_batch = []
        video_meta_batch: List[tuple] = []
        for row in rows:
            filepath = _clean(row["filepath"])
            filename = _clean(row["basename"]) or os.path.basename(filepath)
            folder_path = _clean(row["path"]) or os.path.dirname(filepath)
            if not filepath or not filename:
                continue
            ext = _extension(filename or filepath, _clean(row["file_type"]))
            mtime_utc = _normalize_datetime(row["modified"]) or now_utc
            ctime_utc = _normalize_datetime(row["created"]) or mtime_utc
            folder_id = _folder_id(target, folder_path, folder_cache)
            media_batch.append(
                (
                    filepath,
                    filename,
                    ext,
                    "video",
                    _int_value(row["file_size"], _int_value(row["size"], 0)),
                    mtime_utc,
                    ctime_utc,
                    _clean(row["hash"]) or None,
                    folder_id,
                )
            )
            video_meta_batch.append(
                (
                    filepath,
                    _int_value(row["width"]),
                    _int_value(row["height"]),
                    _float_value(row["duration"]),
                    _float_value(row["frame_rate"]),
                )
            )
            if len(media_batch) >= BATCH_SIZE:
                video_inserted += _insert_media_batch(target, media_batch)
                video_meta_inserted += _insert_video_meta_batch(target, video_meta_batch)
                media_batch.clear()
                video_meta_batch.clear()
        video_inserted += _insert_media_batch(target, media_batch)
        video_meta_inserted += _insert_video_meta_batch(target, video_meta_batch)
    finally:
        source.close()

    target.commit()
    return {
        "source_db": source_path,
        "source_table": IMAGE_SOURCE_TABLE,
        "video_source_table": VIDEO_SOURCE_TABLE,
        "where_clause": source_where,
        "inserted": inserted,
        "meta_inserted": meta_inserted,
        "video_inserted": video_inserted,
        "video_meta_inserted": video_meta_inserted,
        "total_inserted": inserted + video_inserted,
    }


def migrate_audio_from_filelist(
    filelist_db: Optional[str] = None,
    where_clause: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Replace LifePIM audio rows from filelister.fl_audio."""
    target = db._get_conn() if conn is None else conn
    source_path = _resolve_filelist_db(filelist_db)
    source_where = _validated_where_clause(where_clause if where_clause is not None else default_audio_where())
    _ensure_audio_table(target)
    _ensure_folder_support(target, "lp_audio")
    _require_source_table(source_path, AUDIO_SOURCE_TABLE)
    _require_source_table(source_path, "filelist_output")

    _execute_if_table_exists(target, "DELETE FROM lp_audio_playlist_items")
    target.execute("DELETE FROM lp_audio")

    inserted = 0
    folder_cache: Dict[str, Optional[int]] = {}
    user_name = db._current_user()
    extract_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    source = _source_conn(source_path)
    try:
        rows = source.execute(
            "SELECT filepath, size, basename, path, title, artist, album, date, duration, folder_name "
            f"FROM ({AUDIO_SOURCE_SQL}) audio_src {source_where}"
        )
        batch: List[tuple] = []
        for row in rows:
            filepath = _clean(row["filepath"])
            filename = _clean(row["basename"]) or os.path.basename(filepath)
            folder_path = _clean(row["path"]) or os.path.dirname(filepath)
            if not filepath or not filename:
                continue
            folder_id = _folder_id(target, folder_path, folder_cache)
            batch.append(
                (
                    filename,
                    folder_path,
                    folder_id,
                    _extension(filename or filepath),
                    str(_int_value(row["size"], 0)),
                    _date_value(row["date"]),
                    _clean(row["duration"]),
                    _clean(row["artist"]),
                    _clean(row["album"]),
                    _clean(row["title"]) or os.path.splitext(filename)[0],
                    "",
                    user_name,
                    extract_date,
                )
            )
            if len(batch) >= BATCH_SIZE:
                inserted += _insert_audio_batch(target, batch)
                batch.clear()
        inserted += _insert_audio_batch(target, batch)
    finally:
        source.close()

    target.commit()
    return {"source_db": source_path, "source_table": AUDIO_SOURCE_TABLE, "where_clause": source_where, "inserted": inserted}


def _resolve_filelist_db(filelist_db: Optional[str]) -> str:
    path = filelist_db or getattr(cfg, "FILELIST_DB", "")
    path = os.path.abspath(path) if path else ""
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Filelister database not found: {path or '(not configured)'}")
    return path


def _source_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _validated_where_clause(value: str) -> str:
    clause = _clean(value)
    if not clause:
        return ""
    if ";" in clause:
        raise ValueError("Source WHERE clause must not contain semicolons.")
    if not clause.lower().startswith("where "):
        raise ValueError("Source filter must start with WHERE.")
    return clause


def _upgrade_legacy_where(value: str, source_type: str) -> str:
    clause = _clean(value)
    if source_type == "image" and clause == LEGACY_IMAGE_WHERE:
        return cfg._CONFIG_DEFAULTS.get("FILELIST_IMAGE_WHERE", clause)
    if source_type == "audio" and clause == LEGACY_AUDIO_WHERE:
        return cfg._CONFIG_DEFAULTS.get("FILELIST_AUDIO_WHERE", clause)
    return clause


def _require_source_table(path: str, table_name: str) -> None:
    conn = _source_conn(path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name=?",
            (table_name,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise RuntimeError(f"Source table {table_name} not found in {path}")


def _clear_media_tables(conn: sqlite3.Connection) -> None:
    for sql in (
        "DELETE FROM lp_event_items",
        "DELETE FROM lp_events",
        "DELETE FROM lp_album_items",
        "UPDATE lp_albums SET cover_media_id = NULL",
        "DELETE FROM lp_media_tags",
        "DELETE FROM lp_media_meta",
        "DELETE FROM lp_media",
    ):
        _execute_if_table_exists(conn, sql)

def _execute_if_table_exists(conn: sqlite3.Connection, sql: str) -> None:
    try:
        conn.execute(sql)
    except sqlite3.OperationalError:
        pass


def _ensure_audio_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lp_audio ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "file_name TEXT, path TEXT, folder_id TEXT, file_type TEXT, size TEXT, "
        "date_modified TEXT, duration TEXT, artist TEXT, album TEXT, song TEXT, project TEXT, "
        "user_name TEXT, rec_extract_date TEXT)"
    )
    db.add_column_if_missing(conn, "lp_audio", "duration", "TEXT")


def _ensure_folder_support(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(folder_etl.DDL_CREATE_NO_FK)
    db.add_column_if_missing(conn, table_name, "folder_id", "INTEGER")
    conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{table_name}_folder_id ON {table_name}(folder_id)")


def _insert_media_batch(conn: sqlite3.Connection, batch: Iterable[tuple]) -> int:
    batch = list(batch)
    if not batch:
        return 0
    cur = conn.executemany(
        "INSERT OR IGNORE INTO lp_media "
        "(path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash, folder_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        batch,
    )
    return cur.rowcount if cur.rowcount != -1 else len(batch)


def _insert_media_meta_batch(conn: sqlite3.Connection, batch: Iterable[tuple]) -> int:
    batch = list(batch)
    if not batch:
        return 0
    cur = conn.executemany(
        "INSERT OR IGNORE INTO lp_media_meta "
        "(media_id, taken_utc, width, height, gps_lat, gps_lon, camera_make, camera_model) "
        "SELECT media_id, ?, ?, ?, ?, ?, ?, ? FROM lp_media WHERE path = ?",
        [(item[1], item[2], item[3], item[4], item[5], item[6], item[7], item[0]) for item in batch],
    )
    return cur.rowcount if cur.rowcount != -1 else len(batch)


def _insert_video_meta_batch(conn: sqlite3.Connection, batch: Iterable[tuple]) -> int:
    batch = list(batch)
    if not batch:
        return 0
    cur = conn.executemany(
        "INSERT OR IGNORE INTO lp_media_meta "
        "(media_id, width, height, duration_sec, fps) "
        "SELECT media_id, ?, ?, ?, ? FROM lp_media WHERE path = ?",
        [(item[1], item[2], item[3], item[4], item[0]) for item in batch],
    )
    return cur.rowcount if cur.rowcount != -1 else len(batch)


def _insert_audio_batch(conn: sqlite3.Connection, batch: Iterable[tuple]) -> int:
    batch = list(batch)
    if not batch:
        return 0
    cur = conn.executemany(
        "INSERT INTO lp_audio "
        "(file_name, path, folder_id, file_type, size, date_modified, duration, artist, album, song, project, user_name, rec_extract_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        batch,
    )
    return cur.rowcount if cur.rowcount != -1 else len(batch)


def _folder_id(conn: sqlite3.Connection, folder_path: str, cache: Dict[str, Optional[int]]) -> Optional[int]:
    folder_path = _clean(folder_path)
    if not folder_path:
        return None
    if folder_path not in cache:
        cache[folder_path] = db.upsert_dim_folder(conn, folder_path)
    return cache[folder_path]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return None


def _extension(filename: str, fallback: str = "") -> str:
    ext = os.path.splitext(filename or "")[1].lower().lstrip(".")
    if ext:
        return ext
    return _clean(fallback).lower().lstrip(".")


def _int_value(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float_value(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_value(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    normalized = _normalize_datetime(text)
    if normalized:
        return normalized[:10]
    return text


def _normalize_datetime(value: Any) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None
    formats = (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y",
    )
    for fmt in formats:
        try:
            parsed = datetime.strptime(text[: len(datetime.now().strftime(fmt))], fmt)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
