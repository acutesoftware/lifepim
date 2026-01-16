#!/usr/bin/python3
# coding: utf-8
# data.py - common data access functions

from datetime import datetime
import os
import sqlite3

from . import config as cfg
from . import if_sqlite as mod_sql


DB_FILE = getattr(cfg, "DB_FILE", getattr(cfg, "db_name", "lifepim.db"))
if not os.path.isabs(DB_FILE):
    DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), DB_FILE))


def _current_user():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _parse_event_datetime(value):
    if not value:
        return "", ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d"), parsed.strftime("%H:%M")
        except (ValueError, TypeError):
            continue
    return value[:10], ""


def _ensure_database(db_file):
    if not os.path.exists(db_file):
        reset_database(db_file)


def _set_row_factory(db_conn):
    db_conn.row_factory = sqlite3.Row


def _log_error(conn, message):
    try:
        mod_sql.lg(conn, mod_sql.LOG_ERROR, message)
    except Exception:
        pass


def get_data(conn, tbl_name, col_list, condition="1=1", params=None):
    """
    Fetch rows from a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param col_list: list of cols to retrieve
    :param condition: where clause, if None use 1=1
    :param params: query params
    """
    if not col_list:
        col_clause = "*"
    else:
        col_clause = ", ".join(col_list)
    if not condition:
        condition = "1=1"
    sql = f"SELECT {col_clause} FROM {tbl_name} WHERE {condition}"
    cur = conn.execute(sql, params or [])
    return cur.fetchall()


def add_record(conn, tbl_name, col_list, value_list):
    """
    Insert a row into a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param col_list: list of cols to set
    :param value_list: list of values to populate
    returns inserted row id or None for failure
    """
    cols = list(col_list)
    vals = list(value_list)
    cols.extend(["user_name", "rec_extract_date"])
    vals.extend([_current_user(), _now_str()])
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {tbl_name} ({', '.join(cols)}) VALUES ({placeholders})"
    try:
        cur = conn.execute(sql, vals)
        conn.commit()
        return cur.lastrowid
    except Exception as exc:
        _log_error(conn, f"add_record failed: {exc}")
        return None


def update_record(conn, tbl_name, record_id, col_list, value_list):
    """
    Update a row in a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param record_id: the id of the record to update
    :param col_list: list of cols to set
    :param value_list: list of values to update
    returns True for success or False for failure
    """
    cols = list(col_list)
    vals = list(value_list)
    cols.append("rec_extract_date")
    vals.append(_now_str())
    set_clause = ", ".join([f"{col} = ?" for col in cols])
    sql = f"UPDATE {tbl_name} SET {set_clause} WHERE id = ?"
    vals.append(record_id)
    try:
        conn.execute(sql, vals)
        conn.commit()
        return True
    except Exception as exc:
        _log_error(conn, f"update_record failed: {exc}")
        return False


def delete_record(conn, tbl_name, record_id):
    """
    Delete a row from a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param record_id: the id of the record to delete
    returns True for success or False for failure
    """
    sql = f"DELETE FROM {tbl_name} WHERE id = ?"
    try:
        conn.execute(sql, [record_id])
        conn.commit()
        return True
    except Exception as exc:
        _log_error(conn, f"delete_record failed: {exc}")
        return False


##############################
## NOTES

def get_notes(conn, project=None):
    condition = "1=1"
    params = []
    if project:
        condition = "project = ?"
        params = [project]
    rows = get_data(
        conn,
        "lp_notes",
        ["id", "title", "content", "project", "rec_extract_date as updated"],
        condition,
        params,
    )
    notes = []
    for row in rows:
        note = dict(row)
        note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
        notes.append(note)
    return notes


def get_note_by_id(conn, note_id):
    rows = get_data(
        conn,
        "lp_notes",
        ["id", "title", "content", "project", "rec_extract_date as updated"],
        "id = ?",
        [note_id],
    )
    if not rows:
        return None
    note = dict(rows[0])
    note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    return note


def add_note(conn, title, content, project="General"):
    note_id = add_record(conn, "lp_notes", ["title", "content", "project"], [title, content, project])
    if note_id is None:
        return None
    return get_note_by_id(conn, note_id)


def update_note(conn, note_id, title, content, project="General"):
    return update_record(conn, "lp_notes", note_id, ["title", "content", "project"], [title, content, project])


def delete_note(conn, note_id):
    return delete_record(conn, "lp_notes", note_id)


##############################
## TASKS

def get_tasks(conn, project=None):
    condition = "1=1"
    params = []
    if project:
        condition = "project = ?"
        params = [project]
    rows = get_data(
        conn,
        "lp_tasks",
        ["id", "title", "content", "project", "start_date", "due_date", "rec_extract_date as updated"],
        condition,
        params,
    )
    tasks = []
    for row in rows:
        task = dict(row)
        task["updated"] = _parse_datetime(task.get("updated")) or datetime.now()
        tasks.append(task)
    return tasks


def get_task_by_id(conn, task_id):
    rows = get_data(
        conn,
        "lp_tasks",
        ["id", "title", "content", "project", "start_date", "due_date", "rec_extract_date as updated"],
        "id = ?",
        [task_id],
    )
    if not rows:
        return None
    task = dict(rows[0])
    task["updated"] = _parse_datetime(task.get("updated")) or datetime.now()
    return task


def add_task(conn, title, content="", project="General", start_date="", due_date=""):
    task_id = add_record(
        conn,
        "lp_tasks",
        ["title", "content", "project", "start_date", "due_date"],
        [title, content, project, start_date, due_date],
    )
    if task_id is None:
        return None
    return get_task_by_id(conn, task_id)


def update_task(conn, task_id, title, content, project, start_date, due_date):
    return update_record(
        conn,
        "lp_tasks",
        task_id,
        ["title", "content", "project", "start_date", "due_date"],
        [title, content, project, start_date, due_date],
    )


def delete_task(conn, task_id):
    return delete_record(conn, "lp_tasks", task_id)


##############################
## CALENDAR EVENTS

def _calendar_match_project(project, event_project):
    if not project or project in ("any", "spacer"):
        return True
    return (event_project or "").lower() == project.lower()


def get_calendar_events(conn, year=None, month=None, project=None):
    condition_parts = ["1=1"]
    params = []
    if project and project not in ("any", "spacer"):
        condition_parts.append("project = ?")
        params.append(project)
    if year and month:
        condition_parts.append("event_date LIKE ?")
        params.append(f"{year:04d}-{month:02d}%")
    condition = " AND ".join(condition_parts)
    rows = get_data(
        conn,
        "lp_events",
        ["id", "title", "content", "event_date", "project", "rec_extract_date as updated"],
        condition,
        params,
    )
    events = []
    for row in rows:
        evt = dict(row)
        date_str, time_str = _parse_event_datetime(evt.get("event_date"))
        evt["date"] = date_str
        evt["time"] = time_str
        evt["detail"] = evt.get("content", "")
        evt["updated"] = _parse_datetime(evt.get("updated")) or datetime.now()
        events.append(evt)
    return sorted(events, key=lambda e: (e.get("date", ""), e.get("time", ""), e.get("id", 0)))


def get_calendar_event_by_id(conn, event_id):
    rows = get_data(
        conn,
        "lp_events",
        ["id", "title", "content", "event_date", "project", "rec_extract_date as updated"],
        "id = ?",
        [event_id],
    )
    if not rows:
        return None
    evt = dict(rows[0])
    date_str, time_str = _parse_event_datetime(evt.get("event_date"))
    evt["date"] = date_str
    evt["time"] = time_str
    evt["detail"] = evt.get("content", "")
    evt["updated"] = _parse_datetime(evt.get("updated")) or datetime.now()
    return evt


def add_calendar_event(conn, title, date_str, time_str="", detail="", project="General"):
    event_date = date_str
    if time_str:
        event_date = f"{date_str} {time_str}"
    event_id = add_record(
        conn,
        "lp_events",
        ["title", "content", "event_date", "remind_date", "project"],
        [title, detail, event_date, "", project or "General"],
    )
    if event_id is None:
        return None
    return get_calendar_event_by_id(conn, event_id)


def update_calendar_event(conn, event_id, title, date_str, time_str, detail, project):
    event_date = date_str
    if time_str:
        event_date = f"{date_str} {time_str}"
    return update_record(
        conn,
        "lp_events",
        event_id,
        ["title", "content", "event_date", "remind_date", "project"],
        [title, detail, event_date, "", project or "General"],
    )


def delete_calendar_event(conn, event_id):
    return delete_record(conn, "lp_events", event_id)


##############################
## INIT DATABASE

def reset_database(db_file):
    """
    DROPS and recreates the SQLite database 'db_file'
    Then creates all tables from config.py : table_def
    """
    if os.path.exists(db_file):
        os.remove(db_file)
    db_conn = sqlite3.connect(db_file)
    for tbl in cfg.table_def:
        create_table(db_conn, tbl)
    db_conn.commit()
    db_conn.close()


def create_table(db_conn, tbl):
    # {'name':'lp_notes', 'display_name':'Notes', 'col_list':['title','content', 'project']},
    # also include standard columns
    col_defs = []
    for col in tbl["col_list"]:
        col_type = "TEXT"
        if "date" in col.lower():
            col_type = "TEXT"
        col_defs.append(f"{col} {col_type}")
    col_defs.extend(["user_name TEXT", "rec_extract_date TEXT"])
    sql = (
        f"CREATE TABLE IF NOT EXISTS {tbl['name']} ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        f"{', '.join(col_defs)})"
    )
    db_conn.execute(sql)


_ensure_database(DB_FILE)
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
_set_row_factory(conn)
