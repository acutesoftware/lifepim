from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import calendar as py_calendar
import json
import sqlite3
from typing import Iterable

from common import data as db


EVENT_COLUMNS = {
    "title": "TEXT NOT NULL DEFAULT ''",
    "content": "TEXT",
    "start_date": "TEXT",
    "start_time": "TEXT",
    "end_date": "TEXT",
    "end_time": "TEXT",
    "all_day": "INTEGER NOT NULL DEFAULT 1",
    "blocks_time": "INTEGER NOT NULL DEFAULT 0",
    "event_type": "TEXT NOT NULL DEFAULT 'event'",
    "category": "TEXT",
    "project": "TEXT NOT NULL DEFAULT 'General'",
    "status": "TEXT NOT NULL DEFAULT 'active'",
    "color": "TEXT",
    "text_color": "TEXT",
    "icon": "TEXT",
    "location": "TEXT",
    "recurrence_rule": "TEXT",
    "recurrence_start_date": "TEXT",
    "recurrence_end_date": "TEXT",
    "recurrence_count": "INTEGER",
    "remind_date": "TEXT",
    "source": "TEXT NOT NULL DEFAULT 'manual'",
    "source_ref": "TEXT",
    "event_date": "TEXT",
    "user_name": "TEXT",
    "rec_extract_date": "TEXT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
}


SOURCE_SEEDS = [
    ("manual", "Manual Events", "event", "immediate", None, None, "#1f77b4", "#ffffff", "calendar", 10, 1, 1),
    ("recurring", "Recurring Events", "generated", "rebuild", 730, 3650, "#9467bd", "#ffffff", "repeat", 20, 1, 1),
    ("birthdays", "Birthdays", "generated", "rebuild", 0, 7300, "#e377c2", "#ffffff", "cake", 30, 1, 1),
    ("holidays_au", "Australian Public Holidays", "imported", "rebuild", 1825, 3650, "#2ca02c", "#ffffff", "flag", 40, 1, 1),
    ("holidays_sa", "South Australian Public Holidays", "imported", "rebuild", 1825, 3650, "#17becf", "#ffffff", "flag", 41, 1, 1),
    ("tasks", "Task Deadlines", "linked", "incremental", None, None, "#d62728", "#ffffff", "deadline", 50, 1, 0),
    ("files", "File Activity", "metadata", "incremental", None, None, "#7f7f7f", "#ffffff", "file", 100, 0, 0),
    ("media", "Photos and Videos", "metadata", "incremental", None, None, "#ff7f0e", "#ffffff", "image", 90, 0, 0),
    ("audio", "Audio", "metadata", "incremental", None, None, "#bcbd22", "#111111", "music", 90, 0, 0),
    ("usage", "Usage", "log", "incremental", None, None, "#8c564b", "#ffffff", "activity", 100, 0, 0),
]


@dataclass
class RefreshResult:
    source_key: str
    started_at: str
    completed_at: str | None = None
    status: str = "running"
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_deleted: int = 0
    message: str = ""


def ensure_calendar_schema(conn: sqlite3.Connection | None = None, force: bool = False) -> None:
    conn = db._get_conn() if conn is None else conn
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    if not force and _schema_ready(conn):
        return
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lp_calendar_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL UNIQUE,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            visible_by_default INTEGER NOT NULL DEFAULT 1,
            default_color TEXT,
            default_text_color TEXT,
            default_icon TEXT,
            default_priority INTEGER NOT NULL DEFAULT 100,
            refresh_mode TEXT NOT NULL DEFAULT 'incremental',
            horizon_past_days INTEGER,
            horizon_future_days INTEGER,
            last_refresh_at TEXT,
            last_refresh_status TEXT,
            last_refresh_message TEXT,
            last_refresh_count INTEGER NOT NULL DEFAULT 0,
            config_json TEXT,
            user_name TEXT,
            rec_extract_date TEXT
        );

        CREATE TABLE IF NOT EXISTS lp_calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        );

        CREATE TABLE IF NOT EXISTS lp_calendar_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            source_record_id TEXT,
            source_sub_id TEXT,
            occurrence_key TEXT,
            recurrence_parent_id INTEGER,
            item_kind TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            start_date TEXT NOT NULL,
            start_time TEXT,
            end_date TEXT NOT NULL,
            end_time TEXT,
            all_day INTEGER NOT NULL DEFAULT 1,
            blocks_time INTEGER NOT NULL DEFAULT 0,
            event_type TEXT,
            category TEXT,
            project TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            color TEXT,
            text_color TEXT,
            icon TEXT,
            location TEXT,
            sort_priority INTEGER NOT NULL DEFAULT 100,
            is_visible INTEGER NOT NULL DEFAULT 1,
            target_route TEXT,
            target_id TEXT,
            source_modified_at TEXT,
            projected_at TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES lp_calendar_sources(id)
        );

        CREATE TABLE IF NOT EXISTS lp_calendar_item_days (
            calendar_item_id INTEGER NOT NULL,
            item_date TEXT NOT NULL,
            day_number INTEGER NOT NULL DEFAULT 1,
            total_days INTEGER NOT NULL DEFAULT 1,
            is_first_day INTEGER NOT NULL DEFAULT 0,
            is_last_day INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (calendar_item_id, item_date),
            FOREIGN KEY (calendar_item_id) REFERENCES lp_calendar_items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS lp_calendar_day_stats (
            stat_date TEXT NOT NULL,
            source_key TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            item_count INTEGER,
            metric_value REAL,
            summary_text TEXT,
            projected_at TEXT NOT NULL,
            PRIMARY KEY (stat_date, source_key, metric_key)
        );
        """
    )
    for col, col_type in EVENT_COLUMNS.items():
        _add_column_if_missing(conn, "lp_calendar_events", col, col_type)
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_calendar_items_start_date ON lp_calendar_items(start_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_end_date ON lp_calendar_items(end_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_date_range ON lp_calendar_items(start_date, end_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_source_date ON lp_calendar_items(source_key, start_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_project_date ON lp_calendar_items(project, start_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_type_date ON lp_calendar_items(event_type, start_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_status_date ON lp_calendar_items(status, start_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_items_source_record ON lp_calendar_items(source_key, source_record_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_calendar_items_occurrence
            ON lp_calendar_items(source_key, occurrence_key)
            WHERE occurrence_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_calendar_item_days_date ON lp_calendar_item_days(item_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_item_days_date_item ON lp_calendar_item_days(item_date, calendar_item_id);
        CREATE INDEX IF NOT EXISTS idx_calendar_day_stats_date ON lp_calendar_day_stats(stat_date);
        CREATE INDEX IF NOT EXISTS idx_calendar_day_stats_source_date ON lp_calendar_day_stats(source_key, stat_date);

        CREATE VIEW IF NOT EXISTS v_calendar_upcoming AS
        SELECT * FROM lp_calendar_items
        WHERE is_visible = 1 AND status != 'cancelled' AND end_date >= date('now');

        CREATE VIEW IF NOT EXISTS v_calendar_today AS
        SELECT ci.*
        FROM lp_calendar_item_days cid
        JOIN lp_calendar_items ci ON ci.id = cid.calendar_item_id
        WHERE cid.item_date = date('now') AND ci.is_visible = 1;

        CREATE VIEW IF NOT EXISTS v_calendar_source_summary AS
        SELECT cs.source_key, cs.source_name, cs.enabled, cs.last_refresh_at, cs.last_refresh_status,
               COUNT(ci.id) AS item_count, MIN(ci.start_date) AS min_date, MAX(ci.end_date) AS max_date
        FROM lp_calendar_sources cs
        LEFT JOIN lp_calendar_items ci ON ci.source_key = cs.source_key
        GROUP BY cs.source_key, cs.source_name, cs.enabled, cs.last_refresh_at, cs.last_refresh_status;

        CREATE VIEW IF NOT EXISTS v_calendar_event_type_summary AS
        SELECT event_type, COUNT(*) AS item_count, MIN(start_date) AS first_date, MAX(end_date) AS last_date
        FROM lp_calendar_items
        WHERE is_visible = 1
        GROUP BY event_type;
        """
    )
    seed_calendar_sources(conn)
    migrate_existing_calendar_events(conn)
    conn.commit()
    _mark_schema_ready(conn)


def seed_calendar_sources(conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    now = _now()
    conn.executemany(
        """
        INSERT INTO lp_calendar_sources (
            source_key, source_name, source_type, refresh_mode, horizon_past_days,
            horizon_future_days, default_color, default_text_color, default_icon,
            default_priority, enabled, visible_by_default, rec_extract_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            source_name = excluded.source_name,
            source_type = excluded.source_type
        """,
        [seed + (now,) for seed in SOURCE_SEEDS],
    )


def migrate_existing_calendar_events(conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    rows = conn.execute(
        "SELECT id, event_date, start_date, start_time, end_date, end_time, all_day, project, source, created_at "
        "FROM lp_calendar_events"
    ).fetchall()
    now = _now()
    for row in rows:
        values = dict(row)
        event_date = values.get("event_date")
        start_date, start_time, all_day = _parse_legacy_event_date(event_date)
        if not start_date:
            continue
        updates = {}
        if not values.get("start_date"):
            updates["start_date"] = start_date
        if values.get("start_time") in (None, "") and start_time:
            updates["start_time"] = start_time
        if not values.get("end_date"):
            updates["end_date"] = start_date
        if values.get("end_time") in (None, "") and start_time:
            updates["end_time"] = start_time
        if values.get("all_day") is None:
            updates["all_day"] = all_day
        if not values.get("project"):
            updates["project"] = "General"
        if not values.get("source"):
            updates["source"] = "manual"
        if not values.get("created_at"):
            updates["created_at"] = now
        if updates:
            assignments = ", ".join([f"{col} = ?" for col in updates])
            conn.execute(
                f"UPDATE lp_calendar_events SET {assignments} WHERE id = ?",
                [*updates.values(), values["id"]],
            )


def run_calendar_migration(conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn, force=True)
    project_all_manual_events(conn)
    refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
    refresh_calendar_source("holidays_au", conn=conn, full_rebuild=True)
    refresh_calendar_source("holidays_sa", conn=conn, full_rebuild=True)
    rebuild_calendar_day_stats(conn=conn)
    conn.commit()


def project_manual_event(event_id: int, conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    row = conn.execute("SELECT * FROM lp_calendar_events WHERE id = ?", [event_id]).fetchone()
    if not row:
        delete_projected_event(event_id, conn)
        return
    event = dict(row)
    if event.get("recurrence_rule"):
        delete_projected_event(event_id, conn)
        refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
        return
    if (event.get("source") or "manual") != "manual":
        return
    source_id = _source_id(conn, "manual")
    occurrence_key = f"manual:{event_id}"
    _upsert_item(conn, source_id, "manual", event, occurrence_key, "event", recurrence_parent_id=None)
    _touch_source(conn, "manual", "current", 1, "Projected manual event.")
    conn.commit()


def project_all_manual_events(conn: sqlite3.Connection | None = None) -> int:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    rows = conn.execute(
        "SELECT id FROM lp_calendar_events "
        "WHERE COALESCE(source, 'manual') = 'manual' AND COALESCE(recurrence_rule, '') = ''"
    ).fetchall()
    for row in rows:
        project_manual_event(row["id"], conn)
    return len(rows)


def delete_projected_event(event_id: int, conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    conn.execute(
        "DELETE FROM lp_calendar_items WHERE source_key IN ('manual', 'recurring') AND source_record_id = ?",
        [str(event_id)],
    )
    conn.commit()


def rebuild_calendar_item_days(calendar_item_id: int | None = None, conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    params = []
    where = ""
    if calendar_item_id is not None:
        where = "WHERE id = ?"
        params.append(calendar_item_id)
    rows = conn.execute(f"SELECT id, start_date, end_date FROM lp_calendar_items {where}", params).fetchall()
    if calendar_item_id is None:
        conn.execute("DELETE FROM lp_calendar_item_days")
    else:
        conn.execute("DELETE FROM lp_calendar_item_days WHERE calendar_item_id = ?", [calendar_item_id])
    for row in rows:
        _insert_item_days(conn, row["id"], row["start_date"], row["end_date"])
    conn.commit()


def refresh_all_calendar_sources(enabled_only: bool = True, conn: sqlite3.Connection | None = None) -> list[RefreshResult]:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    where = "WHERE enabled = 1" if enabled_only else ""
    rows = conn.execute(f"SELECT source_key FROM lp_calendar_sources {where} ORDER BY default_priority").fetchall()
    return [refresh_calendar_source(row["source_key"], conn=conn, full_rebuild=True) for row in rows]


def refresh_calendar_source(
    source_key: str,
    from_date: str | None = None,
    to_date: str | None = None,
    full_rebuild: bool = False,
    conn: sqlite3.Connection | None = None,
) -> RefreshResult:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    started = _now()
    result = RefreshResult(source_key=source_key, started_at=started)
    try:
        if source_key == "manual":
            result.rows_inserted = project_all_manual_events(conn)
        elif source_key == "recurring":
            result = _refresh_recurring(conn, result)
        elif source_key == "birthdays":
            result = _refresh_birthdays(conn, result)
        elif source_key in {"holidays_au", "holidays_sa"}:
            result = _refresh_holidays(conn, source_key, result)
        elif source_key in {"files", "media", "audio", "usage"}:
            deleted = _delete_day_stats(conn, source_key, from_date, to_date) if full_rebuild else 0
            inserted = rebuild_calendar_day_stats(source_key, from_date, to_date, conn)
            result.rows_deleted = deleted
            result.rows_inserted = inserted
        else:
            result.message = "No adapter for source."
        result.status = "current"
    except Exception as exc:
        result.status = "failed"
        result.message = str(exc)
    result.completed_at = _now()
    _touch_source(conn, source_key, result.status, result.rows_inserted + result.rows_updated, result.message)
    conn.commit()
    return result


def rebuild_calendar_day_stats(
    source_key: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    inserted = 0
    keys = [source_key] if source_key else ["files", "media", "audio"]
    for key in keys:
        if key == "files":
            inserted += _stats_files(conn, from_date, to_date)
        elif key == "media":
            inserted += _stats_media(conn, from_date, to_date)
        elif key == "audio":
            inserted += _stats_audio(conn, from_date, to_date)
        elif key == "usage":
            _touch_source(conn, "usage", "current", 0, "No usage adapter available.")
    conn.commit()
    return inserted


def fetch_calendar_items_for_days(
    start_date: date | str,
    end_date: date | str,
    sources: Iterable[str] | None = None,
    project: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    start_s = _date_s(start_date)
    end_s = _date_s(end_date)
    params: list = [start_s, end_s]
    where = [
        "cid.item_date >= ?",
        "cid.item_date < ?",
        "ci.is_visible = 1",
        "cs.enabled = 1",
        "ci.status != 'cancelled'",
    ]
    source_list = [s for s in (sources or []) if s]
    if source_list:
        where.append("ci.source_key IN (" + ",".join(["?"] * len(source_list)) + ")")
        params.extend(source_list)
    if project:
        if project.lower() == "unmapped":
            where.append("(COALESCE(ci.project, '') = '' OR lower(ci.project) = lower(?))")
            params.append(project)
        else:
            where.append(
                "(lower(COALESCE(ci.project, '')) = lower(?) OR lower(COALESCE(ci.project, '')) LIKE lower(?) || '/%')"
            )
            params.extend([project, project])
    rows = conn.execute(
        """
        SELECT ci.*, cid.item_date, cid.day_number, cid.total_days, cid.is_first_day, cid.is_last_day,
               cs.source_name, cs.default_color, cs.default_text_color, cs.default_icon
        FROM lp_calendar_item_days cid
        JOIN lp_calendar_items ci ON ci.id = cid.calendar_item_id
        JOIN lp_calendar_sources cs ON cs.source_key = ci.source_key
        WHERE """ + " AND ".join(where) + """
        ORDER BY cid.item_date, ci.all_day DESC, ci.start_time, ci.sort_priority, ci.title
        """,
        params,
    ).fetchall()
    return [_item_to_event(dict(row)) for row in rows]


def fetch_calendar_day_stats(
    start_date: date | str,
    end_date: date | str,
    sources: Iterable[str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    params: list = [_date_s(start_date), _date_s(end_date)]
    where = ["stat_date >= ?", "stat_date < ?"]
    source_list = [s for s in (sources or []) if s]
    if source_list:
        where.append("source_key IN (" + ",".join(["?"] * len(source_list)) + ")")
        params.extend(source_list)
    rows = conn.execute(
        "SELECT * FROM lp_calendar_day_stats WHERE " + " AND ".join(where) + " ORDER BY stat_date, source_key, metric_key",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_calendar_sources(conn: sqlite3.Connection | None = None) -> list[dict]:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    rows = conn.execute("SELECT * FROM lp_calendar_sources ORDER BY default_priority, source_name").fetchall()
    return [dict(row) for row in rows]


def save_calendar_sources(form, conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    keys = [row["source_key"] for row in conn.execute("SELECT source_key FROM lp_calendar_sources").fetchall()]
    for key in keys:
        conn.execute(
            """
            UPDATE lp_calendar_sources
            SET enabled = ?, visible_by_default = ?, default_color = ?, default_icon = ?, default_priority = ?,
                horizon_past_days = ?, horizon_future_days = ?
            WHERE source_key = ?
            """,
            (
                1 if form.get(f"enabled_{key}") == "1" else 0,
                1 if form.get(f"visible_{key}") == "1" else 0,
                form.get(f"color_{key}") or None,
                form.get(f"icon_{key}") or None,
                _int(form.get(f"priority_{key}"), 100),
                _nullable_int(form.get(f"past_{key}")),
                _nullable_int(form.get(f"future_{key}")),
                key,
            ),
        )
    conn.commit()


def create_calendar_event(values: dict, conn: sqlite3.Connection | None = None) -> int:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    normalized = normalize_event_values(values)
    now = _now()
    normalized.setdefault("source", "manual")
    normalized.setdefault("created_at", now)
    normalized["updated_at"] = now
    cols = [col for col in EVENT_COLUMNS if col in normalized and col != "id"]
    cur = conn.execute(
        f"INSERT INTO lp_calendar_events ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
        [normalized.get(col) for col in cols],
    )
    event_id = cur.lastrowid
    if normalized.get("recurrence_rule"):
        refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
    else:
        project_manual_event(event_id, conn)
    conn.commit()
    return event_id


def update_calendar_event(event_id: int, values: dict, conn: sqlite3.Connection | None = None) -> None:
    conn = db._get_conn() if conn is None else conn
    ensure_calendar_schema(conn)
    normalized = normalize_event_values(values)
    normalized["updated_at"] = _now()
    cols = [col for col in EVENT_COLUMNS if col in normalized and col != "id"]
    conn.execute(
        f"UPDATE lp_calendar_events SET {', '.join([f'{col} = ?' for col in cols])} WHERE id = ?",
        [normalized.get(col) for col in cols] + [event_id],
    )
    delete_projected_event(event_id, conn)
    if normalized.get("recurrence_rule"):
        refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
    else:
        project_manual_event(event_id, conn)
    conn.commit()


def normalize_event_values(values: dict) -> dict:
    start_date = (values.get("start_date") or values.get("date") or "").strip()
    start_time = (values.get("start_time") or values.get("time") or "").strip()
    end_date = (values.get("end_date") or start_date).strip()
    end_time = (values.get("end_time") or start_time).strip()
    all_day = 1 if values.get("all_day") in (True, "1", "on", "yes", 1) or not start_time else 0
    event_date = values.get("event_date") or (f"{start_date} {start_time}" if start_time else start_date)
    recurrence_rule = _normalize_rrule(values)
    return {
        "title": (values.get("title") or "").strip(),
        "content": (values.get("content") or values.get("detail") or "").strip(),
        "start_date": start_date,
        "start_time": start_time or None,
        "end_date": end_date or start_date,
        "end_time": end_time or None,
        "all_day": all_day,
        "blocks_time": 1 if values.get("blocks_time") in (True, "1", "on", "yes", 1) else 0,
        "event_type": values.get("event_type") or "event",
        "category": values.get("category") or None,
        "project": (values.get("project") if values.get("project") is not None else "General").strip(),
        "status": values.get("status") or "active",
        "color": values.get("color") or None,
        "text_color": values.get("text_color") or None,
        "icon": values.get("icon") or None,
        "location": values.get("location") or None,
        "recurrence_rule": recurrence_rule,
        "recurrence_start_date": values.get("recurrence_start_date") or start_date,
        "recurrence_end_date": values.get("recurrence_end_date") or None,
        "recurrence_count": _nullable_int(values.get("recurrence_count")),
        "remind_date": values.get("remind_date") or "",
        "source": values.get("source") or "manual",
        "source_ref": values.get("source_ref") or None,
        "event_date": event_date,
    }


def _refresh_recurring(conn: sqlite3.Connection, result: RefreshResult) -> RefreshResult:
    deleted = conn.execute("DELETE FROM lp_calendar_items WHERE source_key = 'recurring'").rowcount
    source_id = _source_id(conn, "recurring")
    source = _source_row(conn, "recurring")
    start_horizon, end_horizon = _horizon(source)
    rows = conn.execute(
        "SELECT * FROM lp_calendar_events WHERE COALESCE(recurrence_rule, '') != '' AND COALESCE(status, 'active') != 'cancelled'"
    ).fetchall()
    count = 0
    messages = []
    for row in rows:
        event = dict(row)
        try:
            for occ_date in generate_occurrences(event, start_horizon, end_horizon):
                occurrence_key = f"recurring:{event['id']}:{occ_date.isoformat()}"
                occ_event = dict(event)
                duration = _date_diff_days(event.get("start_date"), event.get("end_date"))
                occ_event["start_date"] = occ_date.isoformat()
                occ_event["end_date"] = (occ_date + timedelta(days=duration)).isoformat()
                _upsert_item(conn, source_id, "recurring", occ_event, occurrence_key, "event", event["id"])
                count += 1
        except Exception as exc:
            messages.append(f"{event.get('id')}: {exc}")
    result.rows_deleted = deleted
    result.rows_inserted = count
    result.message = "; ".join(messages[:5])
    return result


def generate_occurrences(event: dict, start_horizon: date, end_horizon: date) -> list[date]:
    rule = _parse_rrule(event.get("recurrence_rule"))
    if not rule:
        return []
    freq = rule.get("FREQ", "").upper()
    interval = max(1, _int(rule.get("INTERVAL"), 1))
    start = _parse_date(event.get("recurrence_start_date") or event.get("start_date"))
    if not start:
        return []
    until = _parse_date(event.get("recurrence_end_date")) or _parse_date(rule.get("UNTIL")) or end_horizon
    until = min(until, end_horizon)
    count_limit = _nullable_int(event.get("recurrence_count")) or _nullable_int(rule.get("COUNT"))
    byday = [part.strip().upper() for part in (rule.get("BYDAY") or "").split(",") if part.strip()]
    bymonthday = _nullable_int(rule.get("BYMONTHDAY"))
    bymonth = _nullable_int(rule.get("BYMONTH"))
    out = []
    produced = 0
    current = start
    while current <= until and produced < 5000:
        if _matches_rule(current, start, freq, interval, byday, bymonthday, bymonth):
            produced += 1
            if current >= start_horizon:
                out.append(current)
            if count_limit and produced >= count_limit:
                break
        current += timedelta(days=1)
    return out


def _matches_rule(current: date, start: date, freq: str, interval: int, byday: list[str], bymonthday: int | None, bymonth: int | None) -> bool:
    if bymonth and current.month != bymonth:
        return False
    if bymonthday and current.day != bymonthday:
        return False
    has_ordinal_byday = byday and any(code[0].isdigit() or code[0] == "-" for code in byday)
    if byday and not has_ordinal_byday and _weekday_code(current) not in byday:
        return False
    delta_days = (current - start).days
    if freq == "DAILY":
        return delta_days >= 0 and delta_days % interval == 0
    if freq == "WEEKLY":
        weeks = delta_days // 7
        if weeks < 0 or weeks % interval != 0:
            return False
        return _weekday_code(current) in (byday or [_weekday_code(start)])
    if freq == "MONTHLY":
        months = (current.year - start.year) * 12 + current.month - start.month
        if months < 0 or months % interval != 0:
            return False
        if has_ordinal_byday:
            return _matches_ordinal_weekday(current, byday)
        return current.day == (bymonthday or start.day)
    if freq == "YEARLY":
        years = current.year - start.year
        return years >= 0 and years % interval == 0 and current.month == (bymonth or start.month) and current.day == (bymonthday or start.day)
    return False


def _matches_ordinal_weekday(current: date, byday: list[str]) -> bool:
    for token in byday:
        code = token[-2:]
        ordinal_s = token[:-2]
        if code != _weekday_code(current):
            continue
        ordinal = _int(ordinal_s, 0)
        if ordinal > 0 and ((current.day - 1) // 7) + 1 == ordinal:
            return True
        if ordinal < 0:
            last_day = py_calendar.monthrange(current.year, current.month)[1]
            reverse_ordinal = -(((last_day - current.day) // 7) + 1)
            return reverse_ordinal == ordinal
    return False


def _refresh_birthdays(conn: sqlite3.Connection, result: RefreshResult) -> RefreshResult:
    deleted = conn.execute("DELETE FROM lp_calendar_items WHERE source_key = 'birthdays'").rowcount
    source_id = _source_id(conn, "birthdays")
    source = _source_row(conn, "birthdays")
    start_horizon, end_horizon = _horizon(source)
    rows = conn.execute(
        "SELECT * FROM lp_calendar_events WHERE event_type = 'birthday' AND COALESCE(status, 'active') != 'cancelled'"
    ).fetchall()
    count = 0
    for row in rows:
        event = dict(row)
        start = _parse_date(event.get("start_date") or event.get("event_date"))
        if not start:
            continue
        for year in range(start_horizon.year, end_horizon.year + 1):
            occ = _birthday_date(year, start.month, start.day)
            if occ < start_horizon or occ > end_horizon:
                continue
            occurrence_key = f"birthday:event:{event['id']}:{year}"
            occ_event = dict(event)
            occ_event["start_date"] = occ.isoformat()
            occ_event["end_date"] = occ.isoformat()
            _upsert_item(conn, source_id, "birthdays", occ_event, occurrence_key, "event", event["id"])
            count += 1
    result.rows_deleted = deleted
    result.rows_inserted = count
    if _table_exists(conn, "lp_people"):
        result.message = "People birthday adapter is not enabled for this schema yet; event birthdays projected."
    return result


def _refresh_holidays(conn: sqlite3.Connection, source_key: str, result: RefreshResult) -> RefreshResult:
    deleted = conn.execute("DELETE FROM lp_calendar_items WHERE source_key = ?", [source_key]).rowcount
    source_id = _source_id(conn, source_key)
    source = _source_row(conn, source_key)
    start_horizon, end_horizon = _horizon(source)
    jurisdiction = "AU-SA" if source_key == "holidays_sa" else "AU"
    count = 0
    for year in range(start_horizon.year, end_horizon.year + 1):
        for holiday_date, name in _holidays_for_year(year, jurisdiction):
            if holiday_date < start_horizon or holiday_date > end_horizon:
                continue
            occurrence_key = f"holiday:{jurisdiction}:{holiday_date.isoformat()}:{name}"
            event = {
                "id": occurrence_key,
                "title": name,
                "content": jurisdiction,
                "start_date": holiday_date.isoformat(),
                "end_date": holiday_date.isoformat(),
                "all_day": 1,
                "blocks_time": 0,
                "event_type": "holiday",
                "category": jurisdiction,
                "project": "General",
                "status": "active",
                "source": source_key,
            }
            _upsert_item(conn, source_id, source_key, event, occurrence_key, "holiday", None)
            count += 1
    result.rows_deleted = deleted
    result.rows_inserted = count
    return result


def _holidays_for_year(year: int, jurisdiction: str) -> list[tuple[date, str]]:
    easter = _easter_sunday(year)
    holidays = [
        (_observed(date(year, 1, 1)), "New Year's Day"),
        (_observed(date(year, 1, 26)), "Australia Day"),
        (easter - timedelta(days=2), "Good Friday"),
        (easter + timedelta(days=1), "Easter Monday"),
        (date(year, 4, 25), "Anzac Day"),
        (_first_monday(year, 10), "Labour Day"),
        (date(year, 12, 25), "Christmas Day"),
        (date(year, 12, 26), "Boxing Day"),
    ]
    if jurisdiction == "AU-SA":
        holidays.extend(
            [
                (_second_monday(year, 3), "Adelaide Cup Day"),
                (easter + timedelta(days=1), "Easter Monday (SA)"),
                (_second_monday(year, 6), "King's Birthday"),
                (date(year, 12, 24), "Christmas Eve (SA)"),
                (date(year, 12, 31), "New Year's Eve (SA)"),
            ]
        )
    return sorted(set(holidays), key=lambda item: (item[0], item[1]))


def _upsert_item(
    conn: sqlite3.Connection,
    source_id: int,
    source_key: str,
    event: dict,
    occurrence_key: str,
    item_kind: str,
    recurrence_parent_id: int | None,
) -> int:
    now = _now()
    source_record_id = str(event.get("id") or event.get("source_ref") or occurrence_key)
    start_date = event.get("start_date") or _parse_legacy_event_date(event.get("event_date"))[0]
    end_date = event.get("end_date") or start_date
    item = {
        "source_id": source_id,
        "source_key": source_key,
        "source_record_id": source_record_id,
        "source_sub_id": None,
        "occurrence_key": occurrence_key,
        "recurrence_parent_id": recurrence_parent_id,
        "item_kind": item_kind,
        "title": event.get("title") or "",
        "content": event.get("content") or "",
        "start_date": start_date,
        "start_time": event.get("start_time"),
        "end_date": end_date,
        "end_time": event.get("end_time"),
        "all_day": _int(event.get("all_day"), 1),
        "blocks_time": _int(event.get("blocks_time"), 0),
        "event_type": event.get("event_type") or "event",
        "category": event.get("category"),
        "project": event.get("project") if event.get("project") is not None else "General",
        "status": event.get("status") or "active",
        "color": event.get("color"),
        "text_color": event.get("text_color"),
        "icon": event.get("icon"),
        "location": event.get("location"),
        "sort_priority": _source_priority(conn, source_key),
        "is_visible": 0 if event.get("status") == "cancelled" else 1,
        "target_route": "calendar.view_event_route" if source_key in {"manual", "recurring", "birthdays"} else None,
        "target_id": source_record_id if source_key in {"manual", "recurring", "birthdays"} else None,
        "source_modified_at": event.get("updated_at") or event.get("rec_extract_date"),
        "projected_at": now,
    }
    cols = list(item.keys())
    conn.execute(
        f"""
        INSERT INTO lp_calendar_items ({', '.join(cols)})
        VALUES ({', '.join(['?'] * len(cols))})
        ON CONFLICT(source_key, occurrence_key) WHERE occurrence_key IS NOT NULL DO UPDATE SET
            source_id = excluded.source_id,
            source_record_id = excluded.source_record_id,
            recurrence_parent_id = excluded.recurrence_parent_id,
            item_kind = excluded.item_kind,
            title = excluded.title,
            content = excluded.content,
            start_date = excluded.start_date,
            start_time = excluded.start_time,
            end_date = excluded.end_date,
            end_time = excluded.end_time,
            all_day = excluded.all_day,
            blocks_time = excluded.blocks_time,
            event_type = excluded.event_type,
            category = excluded.category,
            project = excluded.project,
            status = excluded.status,
            color = excluded.color,
            text_color = excluded.text_color,
            icon = excluded.icon,
            location = excluded.location,
            sort_priority = excluded.sort_priority,
            is_visible = excluded.is_visible,
            target_route = excluded.target_route,
            target_id = excluded.target_id,
            source_modified_at = excluded.source_modified_at,
            projected_at = excluded.projected_at
        """,
        [item[col] for col in cols],
    )
    row = conn.execute(
        "SELECT id FROM lp_calendar_items WHERE source_key = ? AND occurrence_key = ?",
        [source_key, occurrence_key],
    ).fetchone()
    item_id = row["id"]
    conn.execute("DELETE FROM lp_calendar_item_days WHERE calendar_item_id = ?", [item_id])
    _insert_item_days(conn, item_id, start_date, end_date)
    return item_id


def _insert_item_days(conn: sqlite3.Connection, item_id: int, start_s: str, end_s: str) -> None:
    start = _parse_date(start_s)
    end = _parse_date(end_s) or start
    if not start:
        return
    if end < start:
        end = start
    total = (end - start).days + 1
    rows = []
    for offset in range(total):
        day = start + timedelta(days=offset)
        rows.append((item_id, day.isoformat(), offset + 1, total, 1 if offset == 0 else 0, 1 if offset == total - 1 else 0))
    conn.executemany(
        """
        INSERT OR REPLACE INTO lp_calendar_item_days
        (calendar_item_id, item_date, day_number, total_days, is_first_day, is_last_day)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def _item_to_event(item: dict) -> dict:
    item["date"] = item.get("item_date") or item.get("start_date")
    item["time"] = item.get("start_time") or ""
    item["detail"] = item.get("content") or ""
    item["can_edit"] = bool(item.get("target_id"))
    item["id"] = item.get("target_id") or item.get("id")
    return item


def _stats_files(conn, from_date, to_date) -> int:
    if not _table_has_cols(conn, "lp_files", {"mtime_utc"}):
        return 0
    date_expr = "substr(mtime_utc, 1, 10)"
    where, params = _stats_date_where(date_expr, from_date, to_date)
    if _table_has_cols(conn, "lp_files", {"is_deleted"}):
        where.append("COALESCE(is_deleted, 0) = 0")
    rows = conn.execute(
        f"SELECT {date_expr} AS stat_date, COUNT(1) AS cnt FROM lp_files WHERE {' AND '.join(where)} GROUP BY {date_expr}",
        params,
    ).fetchall()
    return _upsert_stats(conn, "files", "files_modified", rows, "files modified")


def _stats_media(conn, from_date, to_date) -> int:
    if not _table_has_cols(conn, "lp_media", {"mtime_utc", "media_type"}):
        return 0
    date_expr = "substr(mtime_utc, 1, 10)"
    where, params = _stats_date_where(date_expr, from_date, to_date)
    rows = conn.execute(
        f"SELECT {date_expr} AS stat_date, lower(media_type) AS media_type, COUNT(1) AS cnt "
        f"FROM lp_media WHERE {' AND '.join(where)} GROUP BY {date_expr}, lower(media_type)",
        params,
    ).fetchall()
    inserted = 0
    for row in rows:
        metric = "videos_taken" if row["media_type"] == "video" else "photos_taken"
        inserted += _upsert_stats(conn, "media", metric, [row], metric.replace("_", " "))
    return inserted


def _stats_audio(conn, from_date, to_date) -> int:
    if not _table_has_cols(conn, "lp_audio", {"date_modified"}):
        return 0
    date_expr = "substr(date_modified, 1, 10)"
    where, params = _stats_date_where(date_expr, from_date, to_date)
    rows = conn.execute(
        f"SELECT {date_expr} AS stat_date, COUNT(1) AS cnt FROM lp_audio WHERE {' AND '.join(where)} GROUP BY {date_expr}",
        params,
    ).fetchall()
    return _upsert_stats(conn, "audio", "tracks_added", rows, "tracks added")


def _upsert_stats(conn, source_key, metric_key, rows, label) -> int:
    now = _now()
    count = 0
    for row in rows:
        stat_date = row["stat_date"]
        if not stat_date:
            continue
        item_count = int(row["cnt"] or 0)
        conn.execute(
            """
            INSERT INTO lp_calendar_day_stats
                (stat_date, source_key, metric_key, item_count, metric_value, summary_text, projected_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT(stat_date, source_key, metric_key) DO UPDATE SET
                item_count = excluded.item_count,
                metric_value = excluded.metric_value,
                summary_text = excluded.summary_text,
                projected_at = excluded.projected_at
            """,
            (stat_date, source_key, metric_key, item_count, f"{item_count} {label}", now),
        )
        count += 1
    return count


def _delete_day_stats(conn, source_key, from_date, to_date) -> int:
    where = ["source_key = ?"]
    params = [source_key]
    if from_date:
        where.append("stat_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("stat_date < ?")
        params.append(to_date)
    return conn.execute("DELETE FROM lp_calendar_day_stats WHERE " + " AND ".join(where), params).rowcount


def _stats_date_where(expr, from_date, to_date):
    where = [f"{expr} IS NOT NULL", f"{expr} != ''"]
    params = []
    if from_date:
        where.append(f"{expr} >= ?")
        params.append(from_date)
    if to_date:
        where.append(f"{expr} < ?")
        params.append(to_date)
    return where, params


def _parse_legacy_event_date(value) -> tuple[str, str, int]:
    if not value:
        return "", "", 1
    value = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M"), 0
        except ValueError:
            pass
    try:
        parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d"), "", 1
    except ValueError:
        return "", "", 1


def _parse_rrule(value) -> dict:
    if not value:
        return {}
    if str(value).lower() == "yearly":
        return {"FREQ": "YEARLY"}
    parts = {}
    for chunk in str(value).split(";"):
        if "=" not in chunk:
            continue
        key, val = chunk.split("=", 1)
        parts[key.strip().upper()] = val.strip()
    return parts


def _normalize_rrule(values: dict) -> str:
    raw = (values.get("recurrence_rule") or "").strip()
    if raw:
        if raw.lower() == "weekdays":
            return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        if raw.lower() == "fortnightly":
            return "FREQ=WEEKLY;INTERVAL=2"
        if raw.lower() in {"daily", "weekly", "monthly", "yearly"}:
            return f"FREQ={raw.upper()}"
        return raw
    recurrence = (values.get("recurrence") or "").strip().lower()
    if not recurrence or recurrence == "none":
        return ""
    if recurrence == "weekdays":
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    if recurrence == "fortnightly":
        return "FREQ=WEEKLY;INTERVAL=2"
    if recurrence in {"daily", "weekly", "monthly", "yearly"}:
        return f"FREQ={recurrence.upper()}"
    return ""


def _source_id(conn, source_key):
    row = _source_row(conn, source_key)
    if row:
        return row["id"]
    seed_calendar_sources(conn)
    return _source_row(conn, source_key)["id"]


def _source_row(conn, source_key):
    return conn.execute("SELECT * FROM lp_calendar_sources WHERE source_key = ?", [source_key]).fetchone()


def _source_priority(conn, source_key):
    row = _source_row(conn, source_key)
    return row["default_priority"] if row else 100


def _touch_source(conn, source_key, status, count, message):
    conn.execute(
        """
        UPDATE lp_calendar_sources
        SET last_refresh_at = ?, last_refresh_status = ?, last_refresh_message = ?, last_refresh_count = ?
        WHERE source_key = ?
        """,
        (_now(), status, message or "", int(count or 0), source_key),
    )


def _horizon(source_row) -> tuple[date, date]:
    today = date.today()
    past = source_row["horizon_past_days"] if source_row and source_row["horizon_past_days"] is not None else 730
    future = source_row["horizon_future_days"] if source_row and source_row["horizon_future_days"] is not None else 3650
    return today - timedelta(days=int(past)), today + timedelta(days=int(future))


def _date_diff_days(start_s, end_s):
    start = _parse_date(start_s)
    end = _parse_date(end_s) or start
    if not start or not end or end < start:
        return 0
    return (end - start).days


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _date_s(value) -> str:
    return value.isoformat() if isinstance(value, date) else str(value)


def _weekday_code(value: date) -> str:
    return ["MO", "TU", "WE", "TH", "FR", "SA", "SU"][value.weekday()]


def _birthday_date(year, month, day):
    if month == 2 and day == 29 and not py_calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, month, day)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed(value: date) -> date:
    if value.weekday() == 5:
        return value + timedelta(days=2)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _first_monday(year, month):
    day = date(year, month, 1)
    while day.weekday() != 0:
        day += timedelta(days=1)
    return day


def _second_monday(year, month):
    return _first_monday(year, month) + timedelta(days=7)


def _add_column_if_missing(conn, table, column, col_type):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _table_exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone() is not None


def _table_has_cols(conn, table, cols):
    if not _table_exists(conn, table):
        return False
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return set(cols).issubset(existing)


def _schema_ready(conn):
    return conn.execute(
        "SELECT 1 FROM sqlite_temp_master WHERE type = 'table' AND name = 'lp_calendar_schema_ready'"
    ).fetchone() is not None


def _mark_schema_ready(conn):
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS lp_calendar_schema_ready (ready INTEGER)")


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _nullable_int(value):
    if value in (None, ""):
        return None
    return _int(value)


def _now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
