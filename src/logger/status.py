from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LoggerRunSummary:
    status: str
    run_type: str
    files_scanned: int = 0
    files_imported: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    records_imported: int = 0
    sessions_created: int = 0
    message: str = ""
    error_message: str = ""


@dataclass
class LoggerStatus:
    main_database_path: str
    database_path: str
    database_exists: bool
    database_size_bytes: int
    schema_version: int
    mobile_source_path: str
    aggie_source_path: str
    session_gap_seconds: int
    minimum_session_seconds: int
    is_running: bool
    last_refresh: dict | None = None
    last_rebuild_sessions: dict | None = None
    last_rebuild_database: dict | None = None
    sample_counts: dict = field(default_factory=dict)
    ingest_counts: dict = field(default_factory=dict)
    activity_session_count: int = 0
    first_activity_at_utc: str = ""
    last_activity_at_utc: str = ""
