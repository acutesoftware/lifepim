from datetime import datetime
import sqlite3

from common import data as db


SETTINGS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sys_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'General',
    label TEXT NOT NULL DEFAULT '',
    updated_utc TEXT NOT NULL
);
"""


CALENDAR_VIEW_DEFAULTS = {
    "calendar.view.events": ("1", "Calendar", "Show events"),
    "calendar.view.files": ("0", "Calendar", "Show files/images"),
    "calendar.view.usage": ("0", "Calendar", "Show usage"),
    "calendar.media.thumbnail_size": ("small", "Calendar", "Thumbnail size"),
    "calendar.media.thumbnail_limit": ("5", "Calendar", "Thumbnails per day"),
}

CALENDAR_THUMBNAIL_SIZES = {"small", "medium", "large"}
CALENDAR_THUMBNAIL_LIMIT_DEFAULT = 5
CALENDAR_THUMBNAIL_LIMIT_MAX = 20


GENERAL_DEFAULTS = {
    "general.freeze_headers": ("0", "General", "Freeze headers"),
    "general.map_names_english": ("1", "General", "Map names English"),
}

_SCHEMA_READY_CONN_IDS = set()


def ensure_settings_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("settings schema requires a sqlite3.Connection")
    conn_id = id(conn)
    if conn_id in _SCHEMA_READY_CONN_IDS:
        return

    conn.executescript(SETTINGS_SCHEMA_SQL)
    _ensure_settings_columns(conn)
    now = _utc_now()
    for key, (value, category, label) in {
        **CALENDAR_VIEW_DEFAULTS,
        **GENERAL_DEFAULTS,
    }.items():
        conn.execute(
            "INSERT OR IGNORE INTO sys_settings "
            "(setting_key, setting_value, category, label, updated_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, value, category, label, now),
        )
    conn.commit()
    _SCHEMA_READY_CONN_IDS.add(conn_id)


def _ensure_settings_columns(conn):
    rows = conn.execute("PRAGMA table_info(sys_settings)").fetchall()
    existing = {_row_value(row, "name", 1).lower() for row in rows}
    columns = {
        "setting_value": "TEXT NOT NULL DEFAULT ''",
        "category": "TEXT NOT NULL DEFAULT 'General'",
        "label": "TEXT NOT NULL DEFAULT ''",
        "updated_utc": "TEXT NOT NULL DEFAULT ''",
    }
    for name, col_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE sys_settings ADD COLUMN {name} {col_type}")


def get_setting(key, default="", conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    row = conn.execute(
        "SELECT setting_value FROM sys_settings WHERE setting_key = ?",
        (key,),
    ).fetchone()
    return _row_value(row, "setting_value", 0) if row else default


def set_setting(key, value, category="General", label="", conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    conn.execute(
        "INSERT INTO sys_settings (setting_key, setting_value, category, label, updated_utc) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(setting_key) DO UPDATE SET "
        "setting_value=excluded.setting_value, "
        "category=excluded.category, "
        "label=excluded.label, "
        "updated_utc=excluded.updated_utc",
        (key, str(value), category, label, _utc_now()),
    )
    conn.commit()


def delete_setting(key, conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    conn.execute("DELETE FROM sys_settings WHERE setting_key = ?", (key,))
    conn.commit()


def get_calendar_view_settings(conn=None):
    return {
        "events": _as_bool(get_setting("calendar.view.events", "1", conn)),
        "files": _as_bool(get_setting("calendar.view.files", "0", conn)),
        "usage": _as_bool(get_setting("calendar.view.usage", "0", conn)),
        "thumbnail_size": normalize_calendar_thumbnail_size(
            get_setting("calendar.media.thumbnail_size", "small", conn)
        ),
        "thumbnail_limit": normalize_calendar_thumbnail_limit(
            get_setting("calendar.media.thumbnail_limit", str(CALENDAR_THUMBNAIL_LIMIT_DEFAULT), conn)
        ),
    }


def get_general_settings(conn=None):
    return {
        "freeze_headers": _as_bool(get_setting("general.freeze_headers", "0", conn)),
        "map_names_english": _as_bool(get_setting("general.map_names_english", "1", conn)),
    }


def save_general_settings(values, conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    updates = {
        "general.freeze_headers": ("1" if values.get("freeze_headers") else "0", "Freeze headers"),
        "general.map_names_english": ("1" if values.get("map_names_english") else "0", "Map names English"),
    }
    for key, (value, label) in updates.items():
        set_setting(key, value, "General", label, conn)


def save_calendar_view_settings(sources, conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    updates = {
        "calendar.view.events": ("1" if sources.get("events") else "0", "Calendar", "Show events"),
        "calendar.view.files": ("1" if sources.get("files") else "0", "Calendar", "Show files/images"),
        "calendar.view.usage": ("1" if sources.get("usage") else "0", "Calendar", "Show usage"),
    }
    if "thumbnail_size" in sources:
        updates["calendar.media.thumbnail_size"] = (
            normalize_calendar_thumbnail_size(sources.get("thumbnail_size")),
            "Calendar",
            "Thumbnail size",
        )
    if "thumbnail_limit" in sources:
        updates["calendar.media.thumbnail_limit"] = (
            str(normalize_calendar_thumbnail_limit(sources.get("thumbnail_limit"))),
            "Calendar",
            "Thumbnails per day",
        )
    now = _utc_now()
    for key, (value, category, label) in updates.items():
        conn.execute(
            "INSERT INTO sys_settings (setting_key, setting_value, category, label, updated_utc) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(setting_key) DO UPDATE SET "
            "setting_value=excluded.setting_value, "
            "category=excluded.category, "
            "label=excluded.label, "
            "updated_utc=excluded.updated_utc",
            (key, value, category, label, now),
        )
    conn.commit()


def list_settings(conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    rows = conn.execute(
        "SELECT setting_key, setting_value, category, label, updated_utc "
        "FROM sys_settings ORDER BY category, setting_key"
    ).fetchall()
    return [dict(row) for row in rows]


def _row_value(row, key, index):
    if hasattr(row, "keys"):
        return row[key]
    return row[index]


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_calendar_thumbnail_size(value):
    normalized = str(value or "small").strip().lower()
    return normalized if normalized in CALENDAR_THUMBNAIL_SIZES else "small"


def normalize_calendar_thumbnail_limit(value):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = CALENDAR_THUMBNAIL_LIMIT_DEFAULT
    return max(1, min(CALENDAR_THUMBNAIL_LIMIT_MAX, limit))


def _utc_now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
