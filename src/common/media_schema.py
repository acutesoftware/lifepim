"""Media Explorer schema helpers."""

from __future__ import annotations

import sqlite3


MEDIA_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_media (
    media_id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    ext TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_utc TEXT NOT NULL,
    ctime_utc TEXT,
    hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_lp_media_type ON lp_media (media_type);
CREATE INDEX IF NOT EXISTS idx_lp_media_mtime ON lp_media (mtime_utc);
CREATE INDEX IF NOT EXISTS idx_lp_media_filename ON lp_media (filename);

CREATE TABLE IF NOT EXISTS lp_media_meta (
    media_id INTEGER PRIMARY KEY,
    taken_utc TEXT,
    width INTEGER,
    height INTEGER,
    duration_sec REAL,
    fps REAL,
    codec TEXT,
    camera_make TEXT,
    camera_model TEXT,
    gps_lat REAL,
    gps_lon REAL,
    FOREIGN KEY (media_id) REFERENCES lp_media (media_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lp_media_meta_taken ON lp_media_meta (taken_utc);

CREATE TABLE IF NOT EXISTS lp_tags (
    tag_id INTEGER PRIMARY KEY,
    tag TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_lp_tags_tag ON lp_tags (tag);

CREATE TABLE IF NOT EXISTS lp_media_tags (
    media_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_utc TEXT NOT NULL,
    created_by TEXT NOT NULL,
    PRIMARY KEY (media_id, tag_id),
    FOREIGN KEY (media_id) REFERENCES lp_media (media_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES lp_tags (tag_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lp_media_tags_tag ON lp_media_tags (tag_id);
CREATE INDEX IF NOT EXISTS idx_lp_media_tags_media ON lp_media_tags (media_id);

CREATE TABLE IF NOT EXISTS lp_albums (
    album_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    cover_media_id INTEGER,
    album_type TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL,
    FOREIGN KEY (cover_media_id) REFERENCES lp_media (media_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_lp_albums_title ON lp_albums (title);

CREATE TABLE IF NOT EXISTS lp_album_items (
    album_id INTEGER NOT NULL,
    media_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 100,
    added_utc TEXT NOT NULL,
    added_by TEXT NOT NULL,
    PRIMARY KEY (album_id, media_id),
    FOREIGN KEY (album_id) REFERENCES lp_albums (album_id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES lp_media (media_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lp_album_items_album ON lp_album_items (album_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_lp_album_items_media ON lp_album_items (media_id);

CREATE TABLE IF NOT EXISTS lp_smart_views (
    smart_view_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    filter_json TEXT NOT NULL,
    sort_json TEXT,
    created_utc TEXT NOT NULL,
    updated_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lp_smart_views_title ON lp_smart_views (title);

CREATE TABLE IF NOT EXISTS lp_events (
    event_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    location_label TEXT,
    event_source TEXT NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lp_events_start ON lp_events (start_utc);

CREATE TABLE IF NOT EXISTS lp_event_items (
    event_id INTEGER NOT NULL,
    media_id INTEGER NOT NULL,
    confidence REAL,
    PRIMARY KEY (event_id, media_id),
    FOREIGN KEY (event_id) REFERENCES lp_events (event_id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES lp_media (media_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lp_event_items_event ON lp_event_items (event_id);
CREATE INDEX IF NOT EXISTS idx_lp_event_items_media ON lp_event_items (media_id);
"""


def ensure_media_schema(conn: sqlite3.Connection) -> None:
    """Ensure the Media Explorer tables exist."""
    conn.executescript(MEDIA_SCHEMA_SQL)
    _ensure_media_fts(conn)
    conn.commit()


def _ensure_media_fts(conn: sqlite3.Connection) -> None:
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS lp_media_fts USING fts5("
            "media_id UNINDEXED, path, filename, ext, camera_make, camera_model, tags_text)"
        )
    except sqlite3.OperationalError:
        # FTS5 may be unavailable in some SQLite builds.
        pass
