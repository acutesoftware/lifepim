#!/usr/bin/python3
# coding: utf-8
# data.py - common data access functions

from datetime import datetime
import os
import sqlite3
import sys

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
        _dbg(f"INSERT {tbl_name} cols={cols}")
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
        conn = _get_conn() if conn is None else conn
        _dbg(f"UPDATE {tbl_name} id={record_id} cols={col_list}")
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
        conn = _get_conn() if conn is None else conn
        _dbg(f"DELETE {tbl_name} id={record_id}")
        conn.execute(sql, [record_id])
        conn.commit()
        return True
    except Exception as exc:
        _log_error(conn, f"delete_record failed: {exc}")
        return False


conn = None
