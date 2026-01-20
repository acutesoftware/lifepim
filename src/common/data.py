#!/usr/bin/python3
# coding: utf-8
# data.py - common data access functions

from datetime import datetime
import os
import sqlite3
import sys

import etl_folder_mapping as folder_etl

from . import config as cfg
from . import if_sqlite as mod_sql


DB_FILE = getattr(cfg, "DB_FILE", getattr(cfg, "db_name", "lifepim.db"))
if not os.path.isabs(DB_FILE):
    DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), DB_FILE))


def _current_user():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _dbg(msg):
    print(f"[data] {msg}", file=sys.stderr, flush=True)



def _set_row_factory(db_conn):
    db_conn.row_factory = sqlite3.Row


def _get_conn():
    global conn
    if conn is None:
        _dbg(f"Opening sqlite connection to {DB_FILE}")
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        _set_row_factory(conn)
        _dbg("SQLite connection ready")
    return conn


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
    conn = _get_conn() if conn is None else conn
    _dbg(f"SELECT {tbl_name} WHERE {condition} params={params or []}")
    cur = conn.execute(sql, params or [])
    return cur.fetchall()


def add_column_if_missing(conn, tbl_name, col_name, col_type):
    conn = _get_conn() if conn is None else conn
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tbl_name,),
    ).fetchone()
    if not table_row:
        return
    rows = conn.execute(f"PRAGMA table_info({tbl_name})").fetchall()
    existing = {row[1].lower() for row in rows}
    if col_name.lower() in existing:
        return
    conn.execute(f"ALTER TABLE {tbl_name} ADD COLUMN {col_name} {col_type}")


def ensure_folder_schema(conn=None):
    conn = _get_conn() if conn is None else conn
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(folder_etl.DDL_CREATE_NO_FK)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    folder_tables = [
        "lp_notes",
        "lp_media",
        "lp_audio",
        "lp_3d",
        "lp_files",
        "lp_apps",
    ]
    for tbl_name in folder_tables:
        add_column_if_missing(conn, tbl_name, "folder_id", "INTEGER")
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{tbl_name}_folder_id ON {tbl_name}(folder_id)")
    conn.commit()


def upsert_dim_folder(conn, folder_path):
    conn = _get_conn() if conn is None else conn
    fp = folder_etl.norm_path(folder_path)
    if not fp:
        return None
    conn.execute("INSERT OR IGNORE INTO dim_folder(folder_path) VALUES (?)", (fp,))
    conn.execute(
        "UPDATE dim_folder SET last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), is_active=1 WHERE folder_path=?",
        (fp,),
    )
    row = conn.execute("SELECT folder_id FROM dim_folder WHERE folder_path = ?", (fp,)).fetchone()
    return row["folder_id"] if row else None


def _normalize_folder_path(path_value):
    return folder_etl.norm_path(path_value)


def _derive_folder_path(route_name, values_map):
    if route_name == "apps":
        file_path = values_map.get("file_path") or ""
        return os.path.dirname(file_path) if file_path else ""
    if route_name == "notes":
        path_value = (values_map.get("path") or "").strip()
        file_name = (values_map.get("file_name") or "").strip()
        full_path = ""
        if file_name and os.path.isabs(file_name):
            full_path = file_name
        elif path_value and file_name:
            full_path = os.path.join(path_value, file_name)
        else:
            full_path = path_value or file_name
        if os.path.splitext(full_path)[1]:
            return os.path.dirname(full_path)
        return path_value or os.path.dirname(full_path)
    if route_name in ("media", "audio", "3d"):
        path_value = (values_map.get("path") or "").strip()
        file_name = (values_map.get("file_name") or "").strip()
        if path_value:
            return path_value
        if file_name and os.path.isabs(file_name):
            return os.path.dirname(file_name)
        return os.path.dirname(os.path.join(path_value, file_name)) if file_name else ""
    if route_name == "files":
        return (values_map.get("path") or "").strip()
    return ""


def update_folder_id_for_record(conn, tbl_name, route_name, record_id, values_map):
    conn = _get_conn() if conn is None else conn
    folder_path = _derive_folder_path(route_name, values_map)
    folder_path = _normalize_folder_path(folder_path)
    if not folder_path:
        return
    folder_id = upsert_dim_folder(conn, folder_path)
    if not folder_id:
        return
    conn.execute(f"UPDATE {tbl_name} SET folder_id = ? WHERE id = ?", (folder_id, record_id))
    conn.commit()


def _qualify_cols(col_list, table_alias="t"):
    cols = []
    for col in col_list:
        col_str = col.strip()
        lower = col_str.lower()
        if col_str == "*":
            cols.append(col_str)
        elif " as " in lower or "(" in col_str or "." in col_str:
            cols.append(col_str)
        else:
            cols.append(f"{table_alias}.{col_str}")
    return ", ".join(cols) if cols else "*"


def _has_project_col(col_list):
    for col in col_list or []:
        col_name = col.strip()
        col_lower = col_name.lower()
        if " as " in col_lower:
            col_name = col_name[: col_lower.index(" as ")].strip()
            col_lower = col_name.lower()
        if "." in col_name:
            col_name = col_name.split(".")[-1].strip()
            col_lower = col_name.lower()
        if col_lower == "project":
            return True
    return False


def _table_has_project(conn, tbl_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({tbl_name})").fetchall()
    except Exception:
        return False
    col_names = []
    for row in rows:
        try:
            col_names.append(row[1])
        except Exception:
            continue
    return _has_project_col(col_names)


def get_mapped_rows(conn, tbl_name, col_list, tab=None, limit=None, offset=None, order_by=None):
    conn = _get_conn() if conn is None else conn
    cols = _qualify_cols(col_list, "t")
    params = []
    order_clause = order_by or "t.id DESC"
    if tab and tab.lower() == "unmapped":
        sql = (
            f"SELECT {cols} FROM {tbl_name} t "
            "LEFT JOIN map_project_folder mpf "
            "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
            "WHERE mpf.folder_id IS NULL "
            f"ORDER BY {order_clause}"
        )
    elif tab:
        if _has_project_col(col_list):
            sql = (
                f"SELECT {cols} FROM {tbl_name} t "
                "LEFT JOIN map_project_folder mpf "
                "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
                "WHERE lower(mpf.tab) = lower(?) OR lower(t.project) = lower(?) "
                f"ORDER BY {order_clause}"
            )
            params.extend([tab, tab])
        else:
            sql = (
                f"SELECT {cols} FROM {tbl_name} t "
                "JOIN map_project_folder mpf ON mpf.folder_id = t.folder_id "
                "WHERE mpf.is_primary=1 AND mpf.is_enabled=1 AND lower(mpf.tab) = lower(?) "
                f"ORDER BY {order_clause}"
            )
            params.append(tab)
    else:
        sql = f"SELECT {cols} FROM {tbl_name} t ORDER BY {order_clause}"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    _dbg(f"SELECT {tbl_name} tab={tab} limit={limit} offset={offset}")
    return conn.execute(sql, params).fetchall()


def count_mapped_rows(conn, tbl_name, tab=None):
    conn = _get_conn() if conn is None else conn
    params = []
    if tab and tab.lower() == "unmapped":
        sql = (
            f"SELECT COUNT(1) as cnt FROM {tbl_name} t "
            "LEFT JOIN map_project_folder mpf "
            "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
            "WHERE mpf.folder_id IS NULL"
        )
    elif tab:
        if _table_has_project(conn, tbl_name):
            sql = (
                f"SELECT COUNT(1) as cnt FROM {tbl_name} t "
                "LEFT JOIN map_project_folder mpf "
                "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
                "WHERE lower(mpf.tab) = lower(?) OR lower(t.project) = lower(?)"
            )
            params.extend([tab, tab])
        else:
            sql = (
                f"SELECT COUNT(1) as cnt FROM {tbl_name} t "
                "JOIN map_project_folder mpf ON mpf.folder_id = t.folder_id "
                "WHERE mpf.is_primary=1 AND mpf.is_enabled=1 AND lower(mpf.tab) = lower(?)"
            )
            params.append(tab)
    else:
        sql = f"SELECT COUNT(1) as cnt FROM {tbl_name} t"
    row = conn.execute(sql, params).fetchone()
    return row["cnt"] if row else 0


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
        conn = _get_conn() if conn is None else conn
        #_dbg(f"INSERT {tbl_name} cols={cols}")
        cur = conn.execute(sql, vals)
        conn.commit()
        record_id = cur.lastrowid
        _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id)
        return record_id
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
        conn = _get_conn() if conn is None else conn
        _dbg(f"UPDATE {tbl_name} id={record_id} cols={col_list}")
        conn.execute(sql, vals)
        conn.commit()
        _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id)
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
        conn = _get_conn() if conn is None else conn
        _dbg(f"DELETE {tbl_name} id={record_id}")
        conn.execute(sql, [record_id])
        conn.commit()
        return True
    except Exception as exc:
        _log_error(conn, f"delete_record failed: {exc}")
        return False


conn = None


def _route_for_table(tbl_name):
    for tbl in cfg.table_def:
        if tbl.get("name") == tbl_name:
            return tbl.get("route")
    return None


def _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id):
    route_name = _route_for_table(tbl_name)
    if route_name not in {"notes", "media", "audio", "3d", "files", "apps"}:
        return
    values_map = dict(zip(col_list, value_list))
    update_folder_id_for_record(conn, tbl_name, route_name, record_id, values_map)
