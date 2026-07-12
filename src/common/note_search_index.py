"""Cached markdown note content search index."""

from __future__ import annotations

from datetime import datetime
import os
import sqlite3

from common import data


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_note_search_index (
    note_id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    file_mtime REAL,
    file_size INTEGER,
    title TEXT,
    content_text TEXT,
    indexed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lp_note_search_index_title
ON lp_note_search_index(title);
"""


def ensure_schema(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    conn = data._get_conn() if conn is None else conn
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def note_full_path(note: dict) -> str:
    file_name = (note.get("file_name") or "").strip()
    folder_path = (note.get("path") or "").strip()
    if folder_path and file_name:
        return os.path.join(folder_path, file_name)
    if file_name and os.path.isabs(file_name):
        return file_name
    return folder_path or file_name


def read_note_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def rebuild_index(conn: sqlite3.Connection | None = None) -> dict:
    conn = ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT id, file_name, path, size, date_modified, project
        FROM lp_notes
        WHERE COALESCE(file_name, '') != ''
        """
    ).fetchall()
    indexed = missing = skipped = 0
    conn.execute("DELETE FROM lp_note_search_index")
    indexed_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for row in rows:
        note = dict(row)
        note_path = note_full_path(note)
        if not note_path or not note_path.lower().endswith(".md"):
            skipped += 1
            continue
        if not os.path.isfile(note_path):
            missing += 1
            continue
        try:
            stat = os.stat(note_path)
        except OSError:
            missing += 1
            continue
        content = read_note_text(note_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO lp_note_search_index
            (note_id, file_path, file_mtime, file_size, title, content_text, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note["id"],
                note_path,
                stat.st_mtime,
                stat.st_size,
                note.get("file_name") or "",
                content,
                indexed_at,
            ),
        )
        indexed += 1
    conn.commit()
    return {
        "scanned": len(rows),
        "indexed": indexed,
        "missing": missing,
        "skipped": skipped,
    }

