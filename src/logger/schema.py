from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


CURRENT_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS logger_schema_version (
    schema_version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS ingest_file (
    ingest_file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    device_id TEXT,
    source_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size_bytes INTEGER,
    source_modified_at_utc TEXT,
    first_record_at_utc TEXT,
    last_record_at_utc TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    import_status TEXT NOT NULL,
    imported_at_utc TEXT,
    error_message TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    UNIQUE(source_path)
);

CREATE TABLE IF NOT EXISTS processing_run (
    processing_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT,
    run_status TEXT NOT NULL,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    files_imported INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    files_failed INTEGER NOT NULL DEFAULT 0,
    records_imported INTEGER NOT NULL DEFAULT 0,
    sessions_created INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS application_catalog (
    application_catalog_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    application_identifier TEXT NOT NULL,
    application_name TEXT,
    package_name TEXT,
    process_name TEXT,
    executable_path TEXT,
    first_seen_at_utc TEXT,
    last_seen_at_utc TEXT,
    source_type TEXT,
    metadata_json TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    UNIQUE(platform, application_identifier)
);

CREATE TABLE IF NOT EXISTS mobile_app_usage_sample (
    mobile_app_usage_sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingest_file_id INTEGER NOT NULL,
    source_record_index INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    package_name TEXT,
    application_name TEXT,
    activity_name TEXT,
    screen_state TEXT,
    event_type TEXT,
    extra_json TEXT,
    FOREIGN KEY (ingest_file_id) REFERENCES ingest_file(ingest_file_id) ON DELETE CASCADE,
    UNIQUE(ingest_file_id, source_record_index)
);

CREATE TABLE IF NOT EXISTS desktop_window_sample (
    desktop_window_sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingest_file_id INTEGER NOT NULL,
    source_record_index INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    observed_at_utc TEXT NOT NULL,
    process_name TEXT,
    application_name TEXT,
    executable_path TEXT,
    window_title TEXT,
    is_idle INTEGER,
    extra_json TEXT,
    FOREIGN KEY (ingest_file_id) REFERENCES ingest_file(ingest_file_id) ON DELETE CASCADE,
    UNIQUE(ingest_file_id, source_record_index)
);

CREATE TABLE IF NOT EXISTS activity_session (
    activity_session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    device_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    application_identifier TEXT,
    application_name TEXT,
    activity_title TEXT,
    start_at_utc TEXT NOT NULL,
    end_at_utc TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    source_record_count INTEGER NOT NULL,
    confidence_score REAL,
    first_source_record_id INTEGER,
    last_source_record_id INTEGER,
    session_hash TEXT NOT NULL,
    generated_at_utc TEXT NOT NULL,
    UNIQUE(session_hash)
);

CREATE INDEX IF NOT EXISTS ix_ingest_file_status ON ingest_file(import_status);
CREATE INDEX IF NOT EXISTS ix_mobile_app_usage_device_time ON mobile_app_usage_sample(device_id, observed_at_utc);
CREATE INDEX IF NOT EXISTS ix_mobile_app_usage_package_time ON mobile_app_usage_sample(package_name, observed_at_utc);
CREATE INDEX IF NOT EXISTS ix_desktop_window_device_time ON desktop_window_sample(device_id, observed_at_utc);
CREATE INDEX IF NOT EXISTS ix_desktop_window_process_time ON desktop_window_sample(process_name, observed_at_utc);
CREATE INDEX IF NOT EXISTS ix_activity_session_time ON activity_session(start_at_utc, end_at_utc);
CREATE INDEX IF NOT EXISTS ix_activity_session_device_time ON activity_session(device_id, start_at_utc);
CREATE INDEX IF NOT EXISTS ix_activity_session_application_time ON activity_session(application_identifier, start_at_utc);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute(
            "SELECT MAX(schema_version) AS version FROM logger_schema_version"
        ).fetchone()
        if not row or int(row["version"] or 0) < CURRENT_SCHEMA_VERSION:
            conn.execute(
                "INSERT OR IGNORE INTO logger_schema_version (schema_version, applied_at_utc, description) VALUES (?, ?, ?)",
                (CURRENT_SCHEMA_VERSION, utc_now(), "Initial logger processing schema"),
            )


def schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(schema_version) AS version FROM logger_schema_version").fetchone()
        return int(row["version"] or 0) if row else 0
    except sqlite3.Error:
        return 0
