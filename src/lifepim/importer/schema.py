"""Schema helpers for importer."""

from __future__ import annotations

import sqlite3
from typing import Iterable


def ensure_import_schema(conn_or_path):
    conn, should_close = _ensure_conn(conn_or_path)
    try:
        _ensure_import_runs(conn)
        _ensure_contacts_columns(conn)
        _ensure_files_columns(conn)
        _ensure_media_columns(conn)
        conn.commit()
    finally:
        if should_close:
            conn.close()


def _ensure_conn(conn_or_path):
    if isinstance(conn_or_path, sqlite3.Connection):
        return conn_or_path, False
    conn = sqlite3.connect(conn_or_path)
    return conn, True


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _add_column_if_missing(conn, table_name: str, column_name: str, column_type: str):
    if not _table_exists(conn, table_name):
        return
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {row[1].lower() for row in rows}
    if column_name.lower() in existing:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _ensure_import_runs(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lp_import_runs ("
        "run_id INTEGER PRIMARY KEY,"
        "run_name TEXT NOT NULL,"
        "started_utc TEXT NOT NULL,"
        "ended_utc TEXT,"
        "status TEXT NOT NULL,"
        "stats_json TEXT,"
        "error_text TEXT"
        ")"
    )


def _ensure_contacts_columns(conn):
    for name, col_type in _import_columns():
        _add_column_if_missing(conn, "lp_contacts", name, col_type)
    _add_column_if_missing(conn, "lp_contacts", "email", "TEXT")
    _add_column_if_missing(conn, "lp_contacts", "phone", "TEXT")
    _ensure_unique_entity(conn, "lp_contacts")


def _ensure_files_columns(conn):
    for name, col_type in _import_columns():
        _add_column_if_missing(conn, "lp_files", name, col_type)
    _add_column_if_missing(conn, "lp_files", "size", "INTEGER")
    _add_column_if_missing(conn, "lp_files", "mtime_utc", "TEXT")
    _add_column_if_missing(conn, "lp_files", "sha256", "TEXT")
    _ensure_unique_entity(conn, "lp_files")


def _ensure_media_columns(conn):
    for name, col_type in _import_columns():
        _add_column_if_missing(conn, "lp_media", name, col_type)
    _add_column_if_missing(conn, "lp_media", "sha256", "TEXT")
    _add_column_if_missing(conn, "lp_media", "labels_json", "TEXT")
    _add_column_if_missing(conn, "lp_media", "faces", "TEXT")
    _add_column_if_missing(conn, "lp_media", "dominant_colors", "TEXT")
    _ensure_unique_entity(conn, "lp_media")


def _ensure_unique_entity(conn, table_name: str):
    if not _table_exists(conn, table_name):
        return
    idx_name = f"ux_{table_name}_entity_id"
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} ON {table_name}(entity_id)"
    )


def _import_columns() -> Iterable[tuple[str, str]]:
    return [
        ("entity_id", "TEXT"),
        ("source_system", "TEXT"),
        ("source_uid", "TEXT"),
        ("imported_run_id", "INTEGER"),
        ("imported_utc", "TEXT"),
        ("is_deleted", "INTEGER NOT NULL DEFAULT 0"),
        ("deleted_utc", "TEXT"),
    ]
