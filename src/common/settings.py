from datetime import datetime

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
}


def ensure_settings_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    conn.executescript(SETTINGS_SCHEMA_SQL)
    now = _utc_now()
    for key, (value, category, label) in CALENDAR_VIEW_DEFAULTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO sys_settings "
            "(setting_key, setting_value, category, label, updated_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, value, category, label, now),
        )
    conn.commit()


def get_setting(key, default="", conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    row = conn.execute(
        "SELECT setting_value FROM sys_settings WHERE setting_key = ?",
        (key,),
    ).fetchone()
    return row["setting_value"] if row else default


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


def get_calendar_view_settings(conn=None):
    return {
        "events": _as_bool(get_setting("calendar.view.events", "1", conn)),
        "files": _as_bool(get_setting("calendar.view.files", "0", conn)),
        "usage": _as_bool(get_setting("calendar.view.usage", "0", conn)),
    }


def save_calendar_view_settings(sources, conn=None):
    conn = db._get_conn() if conn is None else conn
    ensure_settings_schema(conn)
    updates = {
        "calendar.view.events": ("1" if sources.get("events") else "0", "Calendar", "Show events"),
        "calendar.view.files": ("1" if sources.get("files") else "0", "Calendar", "Show files/images"),
        "calendar.view.usage": ("1" if sources.get("usage") else "0", "Calendar", "Show usage"),
    }
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


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _utc_now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
