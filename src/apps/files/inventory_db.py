"""SQLite schema and repository helpers for File Inventory."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from common import config as cfg


DDL = """
CREATE TABLE IF NOT EXISTS lp_file_source (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    provider_checkpoint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lp_file (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    fullfilename TEXT NOT NULL,
    path TEXT NOT NULL,
    xtn TEXT NOT NULL,
    name TEXT NOT NULL,
    date_modified TEXT NOT NULL,
    date_created TEXT NOT NULL,
    date_accessed TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    first_seen_scan_id INTEGER,
    last_seen_scan_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    parent_relative_path TEXT NOT NULL,
    normalized_relative_path TEXT NOT NULL,
    normalized_path TEXT NOT NULL,
    scan_status TEXT,
    UNIQUE(source_id, normalized_relative_path)
);

CREATE TABLE IF NOT EXISTS lp_file_scan (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    scope_path TEXT NOT NULL,
    scan_mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    files_seen INTEGER NOT NULL DEFAULT 0,
    files_new INTEGER NOT NULL DEFAULT 0,
    files_changed INTEGER NOT NULL DEFAULT 0,
    files_unchanged INTEGER NOT NULL DEFAULT 0,
    files_deleted INTEGER NOT NULL DEFAULT 0,
    files_reactivated INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    error_text TEXT,
    change_provider TEXT,
    provider_checkpoint_before TEXT,
    provider_checkpoint_after TEXT
);

CREATE TABLE IF NOT EXISTS lp_file_change (
    file_change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_file_source_deleted ON lp_file(source_id, is_deleted);
CREATE INDEX IF NOT EXISTS ix_lp_file_xtn ON lp_file(xtn);
CREATE INDEX IF NOT EXISTS ix_lp_file_last_seen_scan ON lp_file(last_seen_scan_id);
CREATE INDEX IF NOT EXISTS ix_lp_file_parent ON lp_file(source_id, parent_relative_path);
CREATE INDEX IF NOT EXISTS ix_lp_file_scan_source_status ON lp_file_scan(source_id, status, scan_id);
CREATE INDEX IF NOT EXISTS ix_lp_file_change_scan_type ON lp_file_change(scan_id, change_type);
CREATE INDEX IF NOT EXISTS ix_lp_file_change_file ON lp_file_change(file_id);
"""


def default_db_path() -> str:
    value = getattr(cfg, "FILE_INVENTORY_DB", "")
    if value:
        return value
    return os.path.join(getattr(cfg, "user_folder", os.getcwd()), "files.db")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    db_path = os.path.abspath(db_path or default_db_path())
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_or_update_source(conn: sqlite3.Connection, name: str, root_path: str, enabled: bool = True) -> int:
    ensure_schema(conn)
    now = utc_now()
    root_path = normalize_root_path(root_path)
    row = conn.execute(
        "SELECT source_id FROM lp_file_source WHERE lower(root_path) = lower(?)",
        (root_path,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE lp_file_source SET name = ?, root_path = ?, enabled = ?, updated_at = ? WHERE source_id = ?",
            (name, root_path, 1 if enabled else 0, now, row["source_id"]),
        )
        conn.commit()
        return int(row["source_id"])
    cur = conn.execute(
        "INSERT INTO lp_file_source (name, root_path, enabled, provider_checkpoint, created_at, updated_at) "
        "VALUES (?, ?, ?, '', ?, ?)",
        (name, root_path, 1 if enabled else 0, now, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_source(conn: sqlite3.Connection, source_id: int):
    return conn.execute(
        "SELECT * FROM lp_file_source WHERE source_id = ?",
        (int(source_id),),
    ).fetchone()


def list_sources(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM lp_file_source ORDER BY enabled DESC, lower(name)").fetchall()


def last_successful_scan(conn: sqlite3.Connection, source_id: int):
    return conn.execute(
        "SELECT * FROM lp_file_scan WHERE source_id = ? AND status = 'SUCCESS' ORDER BY scan_id DESC LIMIT 1",
        (int(source_id),),
    ).fetchone()


def changed_files_for_scan(conn: sqlite3.Connection, scan_id: int, extensions: Iterable[str] | None = None):
    params = [int(scan_id)]
    where = [
        "c.scan_id = ?",
        "c.change_type IN ('NEW', 'CHANGED', 'REACTIVATED')",
        "f.is_deleted = 0",
    ]
    if extensions:
        cleaned = [str(ext).lower().lstrip(".") for ext in extensions if str(ext).strip()]
        if cleaned:
            where.append("f.xtn IN (" + ",".join(["?"] * len(cleaned)) + ")")
            params.extend(cleaned)
    return conn.execute(
        "SELECT f.*, c.change_type "
        "FROM lp_file_change c JOIN lp_file f ON f.file_id = c.file_id "
        "WHERE " + " AND ".join(where) + " ORDER BY f.normalized_relative_path",
        params,
    ).fetchall()


def normalize_root_path(path_value: str) -> str:
    text = os.path.abspath(os.path.expanduser(os.path.expandvars((path_value or "").strip().strip('"'))))
    text = text.replace("/", os.sep)
    return os.path.normpath(text)
