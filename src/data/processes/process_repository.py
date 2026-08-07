from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common import config as app_config
from common import data as main_data


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def default_logger_database_path() -> str:
    db_file = Path(getattr(main_data, "DB_FILE", "") or getattr(app_config, "DB_FILE", "") or "").expanduser()
    db_dir = db_file.parent if str(db_file) else Path(getattr(app_config, "data_folder", ".")).expanduser()
    return str(db_dir / "logger.sqlite")


def default_logger_config() -> dict[str, Any]:
    return {
        "source_folder": "",
        "file_pattern": "*.json;*.jsonl",
        "include_subfolders": True,
        "database_path": "<LIFEPIM_DB_DIR>\\logger.sqlite",
        "import_mode": "incremental",
        "duplicate_detection": "metadata_and_hash",
        "successful_file_action": "leave",
        "processed_folder": None,
        "invalid_file_action": "leave",
        "failed_folder": None,
        "hash_algorithm": "sha256",
        "calculate_hash_during_preview": False,
        "create_database_if_missing": True,
        "create_tables_if_missing": True,
        "allow_unknown_record_types": True,
        "stop_on_file_error": False,
    }


class ProcessRepository:
    def __init__(self, connection: sqlite3.Connection | None = None):
        self.conn = connection or main_data._get_conn()
        self.conn.row_factory = sqlite3.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lp_process (
                process_id INTEGER PRIMARY KEY,
                process_name TEXT NOT NULL,
                process_type TEXT NOT NULL,
                description TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                configuration_json TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS lp_process_run (
                process_run_id INTEGER PRIMARY KEY,
                process_id INTEGER NOT NULL,
                started_at_utc TEXT NOT NULL,
                finished_at_utc TEXT,
                status TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                run_mode TEXT NOT NULL,
                files_found INTEGER NOT NULL DEFAULT 0,
                files_processed INTEGER NOT NULL DEFAULT 0,
                files_skipped INTEGER NOT NULL DEFAULT 0,
                files_failed INTEGER NOT NULL DEFAULT 0,
                records_read INTEGER NOT NULL DEFAULT 0,
                records_written INTEGER NOT NULL DEFAULT 0,
                records_skipped INTEGER NOT NULL DEFAULT 0,
                records_failed INTEGER NOT NULL DEFAULT 0,
                summary TEXT,
                error_message TEXT,
                FOREIGN KEY (process_id) REFERENCES lp_process(process_id)
            );

            CREATE TABLE IF NOT EXISTS lp_process_run_message (
                process_run_message_id INTEGER PRIMARY KEY,
                process_run_id INTEGER NOT NULL,
                message_time_utc TEXT NOT NULL,
                message_level TEXT NOT NULL,
                message_code TEXT,
                message_text TEXT NOT NULL,
                context_json TEXT,
                FOREIGN KEY (process_run_id) REFERENCES lp_process_run(process_run_id)
            );

            CREATE TABLE IF NOT EXISTS lp_process_file (
                process_file_id INTEGER PRIMARY KEY,
                process_id INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                source_path_normalised TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size_bytes INTEGER,
                file_modified_at_utc TEXT,
                file_hash TEXT,
                first_seen_at_utc TEXT NOT NULL,
                last_seen_at_utc TEXT NOT NULL,
                last_processed_at_utc TEXT,
                last_process_run_id INTEGER,
                status TEXT NOT NULL,
                detected_file_type TEXT,
                detected_record_types TEXT,
                records_read INTEGER NOT NULL DEFAULT 0,
                records_written INTEGER NOT NULL DEFAULT 0,
                records_skipped INTEGER NOT NULL DEFAULT 0,
                records_failed INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                FOREIGN KEY (process_id) REFERENCES lp_process(process_id),
                FOREIGN KEY (last_process_run_id) REFERENCES lp_process_run(process_run_id)
            );

            CREATE TABLE IF NOT EXISTS lp_process_run_file (
                process_run_file_id INTEGER PRIMARY KEY,
                process_run_id INTEGER NOT NULL,
                process_file_id INTEGER,
                source_path TEXT NOT NULL,
                status TEXT NOT NULL,
                records_read INTEGER NOT NULL DEFAULT 0,
                records_written INTEGER NOT NULL DEFAULT 0,
                records_skipped INTEGER NOT NULL DEFAULT 0,
                records_failed INTEGER NOT NULL DEFAULT 0,
                started_at_utc TEXT,
                finished_at_utc TEXT,
                message TEXT,
                FOREIGN KEY (process_run_id) REFERENCES lp_process_run(process_run_id),
                FOREIGN KEY (process_file_id) REFERENCES lp_process_file(process_file_id)
            );

            CREATE INDEX IF NOT EXISTS ix_lp_process_type ON lp_process(process_type);
            CREATE INDEX IF NOT EXISTS ix_lp_process_enabled ON lp_process(is_enabled);
            CREATE INDEX IF NOT EXISTS ix_lp_process_run_process ON lp_process_run(process_id, started_at_utc DESC);
            CREATE INDEX IF NOT EXISTS ix_lp_process_run_status ON lp_process_run(status);
            CREATE INDEX IF NOT EXISTS ix_lp_process_file_process ON lp_process_file(process_id);
            CREATE INDEX IF NOT EXISTS ix_lp_process_file_identity ON lp_process_file(process_id, source_path_normalised, file_size_bytes, file_modified_at_utc);
            CREATE INDEX IF NOT EXISTS ix_lp_process_file_hash ON lp_process_file(process_id, file_hash);
            CREATE INDEX IF NOT EXISTS ix_lp_process_run_file_run ON lp_process_run_file(process_run_id);
            """
        )
        self.seed_default_logger_process()
        self.conn.commit()

    def seed_default_logger_process(self) -> None:
        row = self.conn.execute(
            """
            SELECT process_id FROM lp_process
            WHERE process_type = 'logger_json_import'
              AND process_name = 'Import LifePIM Logger JSON'
            """
        ).fetchone()
        if row:
            return
        ts = utc_now()
        self.conn.execute(
            """
            INSERT INTO lp_process(process_name, process_type, description, is_enabled, configuration_json, created_at_utc, updated_at_utc)
            VALUES (?, 'logger_json_import', ?, 1, ?, ?, ?)
            """,
            (
                "Import LifePIM Logger JSON",
                "Load raw JSON files created by the LifePIM Logger mobile app into the separate logger database.",
                json.dumps(default_logger_config(), ensure_ascii=True, sort_keys=True),
                ts,
                ts,
            ),
        )

    def list_processes(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT p.*,
                   r.process_run_id AS last_process_run_id,
                   r.started_at_utc AS last_started_at_utc,
                   r.finished_at_utc AS last_finished_at_utc,
                   r.status AS last_status,
                   r.summary AS last_summary
            FROM lp_process p
            LEFT JOIN lp_process_run r ON r.process_run_id = (
                SELECT process_run_id
                FROM lp_process_run pr
                WHERE pr.process_id = p.process_id
                ORDER BY pr.started_at_utc DESC, pr.process_run_id DESC
                LIMIT 1
            )
            ORDER BY p.is_enabled DESC, p.process_name
            """
        ).fetchall()
        return [self._process_dict(row) for row in rows]

    def get_process(self, process_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM lp_process WHERE process_id = ?", (process_id,)).fetchone()
        return self._process_dict(row) if row else None

    def first_process_by_type(self, process_type: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM lp_process WHERE process_type = ? ORDER BY is_enabled DESC, process_id LIMIT 1",
            (process_type,),
        ).fetchone()
        return self._process_dict(row) if row else None

    def save_process(self, process_id: int | None, values: dict[str, Any]) -> int:
        ts = utc_now()
        config_json = json.dumps(values.get("configuration", {}), ensure_ascii=True, sort_keys=True)
        if process_id:
            self.conn.execute(
                """
                UPDATE lp_process
                SET process_name = ?, description = ?, is_enabled = ?, configuration_json = ?, updated_at_utc = ?
                WHERE process_id = ?
                """,
                (
                    values.get("process_name") or "Untitled process",
                    values.get("description") or "",
                    1 if values.get("is_enabled") else 0,
                    config_json,
                    ts,
                    process_id,
                ),
            )
            self.conn.commit()
            return process_id
        cur = self.conn.execute(
            """
            INSERT INTO lp_process(process_name, process_type, description, is_enabled, configuration_json, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                values.get("process_name") or "Untitled process",
                values.get("process_type") or "logger_json_import",
                values.get("description") or "",
                1 if values.get("is_enabled") else 0,
                config_json,
                ts,
                ts,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def create_run(self, process_id: int, trigger_type: str, run_mode: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO lp_process_run(process_id, started_at_utc, status, trigger_type, run_mode)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (process_id, utc_now(), trigger_type, run_mode),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def mark_run_running(self, run_id: int) -> None:
        self.conn.execute("UPDATE lp_process_run SET status = 'running' WHERE process_run_id = ?", (run_id,))
        self.conn.commit()

    def finalise_run(self, run_id: int, result) -> None:
        self.conn.execute(
            """
            UPDATE lp_process_run
            SET finished_at_utc = ?, status = ?, files_found = ?, files_processed = ?,
                files_skipped = ?, files_failed = ?, records_read = ?, records_written = ?,
                records_skipped = ?, records_failed = ?, summary = ?, error_message = ?
            WHERE process_run_id = ?
            """,
            (
                utc_now(),
                result.status,
                int(result.files_found or 0),
                int(result.files_processed or 0),
                int(result.files_skipped or 0),
                int(result.files_failed or 0),
                int(result.records_read or 0),
                int(result.records_written or 0),
                int(result.records_skipped or 0),
                int(result.records_failed or 0),
                result.summary or "",
                result.error_message or "",
                run_id,
            ),
        )
        self.conn.commit()

    def add_message(self, run_id: int, level: str, code: str, text: str, context: dict | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO lp_process_run_message(process_run_id, message_time_utc, message_level, message_code, message_text, context_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, utc_now(), level, code or "", text, json.dumps(context or {}, ensure_ascii=True, sort_keys=True)),
        )
        self.conn.commit()

    def upsert_process_file(self, process_id: int, file_info: dict[str, Any]) -> int:
        now = utc_now()
        row = self.conn.execute(
            """
            SELECT * FROM lp_process_file
            WHERE process_id = ? AND source_path_normalised = ?
              AND COALESCE(file_size_bytes, -1) = COALESCE(?, -1)
              AND COALESCE(file_modified_at_utc, '') = COALESCE(?, '')
            ORDER BY process_file_id DESC LIMIT 1
            """,
            (
                process_id,
                file_info.get("source_path_normalised"),
                file_info.get("file_size_bytes"),
                file_info.get("file_modified_at_utc"),
            ),
        ).fetchone()
        if row:
            process_file_id = int(row["process_file_id"])
            self.conn.execute(
                """
                UPDATE lp_process_file
                SET source_path = ?, file_name = ?, file_hash = COALESCE(?, file_hash),
                    last_seen_at_utc = ?, detected_file_type = COALESCE(?, detected_file_type),
                    detected_record_types = COALESCE(?, detected_record_types)
                WHERE process_file_id = ?
                """,
                (
                    file_info.get("source_path"),
                    file_info.get("file_name"),
                    file_info.get("file_hash"),
                    now,
                    file_info.get("detected_file_type"),
                    file_info.get("detected_record_types"),
                    process_file_id,
                ),
            )
        else:
            cur = self.conn.execute(
                """
                INSERT INTO lp_process_file(
                    process_id, source_path, source_path_normalised, file_name, file_size_bytes,
                    file_modified_at_utc, file_hash, first_seen_at_utc, last_seen_at_utc, status,
                    detected_file_type, detected_record_types
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    process_id,
                    file_info.get("source_path"),
                    file_info.get("source_path_normalised"),
                    file_info.get("file_name"),
                    file_info.get("file_size_bytes"),
                    file_info.get("file_modified_at_utc"),
                    file_info.get("file_hash"),
                    now,
                    now,
                    file_info.get("status") or "discovered",
                    file_info.get("detected_file_type"),
                    file_info.get("detected_record_types"),
                ),
            )
            process_file_id = int(cur.lastrowid)
        self.conn.commit()
        return process_file_id

    def find_imported_by_hash(self, process_id: int, file_hash: str) -> dict | None:
        if not file_hash:
            return None
        row = self.conn.execute(
            """
            SELECT * FROM lp_process_file
            WHERE process_id = ? AND file_hash = ? AND status IN ('imported', 'warning')
            ORDER BY process_file_id LIMIT 1
            """,
            (process_id, file_hash),
        ).fetchone()
        return dict(row) if row else None

    def find_imported_by_metadata(self, process_id: int, normalised_path: str, size: int | None, modified_at: str | None) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM lp_process_file
            WHERE process_id = ? AND source_path_normalised = ?
              AND COALESCE(file_size_bytes, -1) = COALESCE(?, -1)
              AND COALESCE(file_modified_at_utc, '') = COALESCE(?, '')
              AND status IN ('imported', 'warning')
            ORDER BY process_file_id DESC LIMIT 1
            """,
            (process_id, normalised_path, size, modified_at),
        ).fetchone()
        return dict(row) if row else None

    def update_file_result(self, process_file_id: int, run_id: int, status: str, counts: dict[str, Any], message: str = "", detected_types: str = "") -> None:
        self.conn.execute(
            """
            UPDATE lp_process_file
            SET status = ?, last_processed_at_utc = ?, last_process_run_id = ?,
                records_read = ?, records_written = ?, records_skipped = ?, records_failed = ?,
                error_message = ?, detected_record_types = COALESCE(NULLIF(?, ''), detected_record_types)
            WHERE process_file_id = ?
            """,
            (
                status,
                utc_now(),
                run_id,
                int(counts.get("records_read") or 0),
                int(counts.get("records_written") or 0),
                int(counts.get("records_skipped") or 0),
                int(counts.get("records_failed") or 0),
                message or "",
                detected_types or "",
                process_file_id,
            ),
        )
        self.conn.commit()

    def add_run_file(self, run_id: int, process_file_id: int | None, source_path: str, status: str, counts: dict[str, Any], message: str = "", started_at: str | None = None) -> None:
        self.conn.execute(
            """
            INSERT INTO lp_process_run_file(
                process_run_id, process_file_id, source_path, status, records_read, records_written,
                records_skipped, records_failed, started_at_utc, finished_at_utc, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                process_file_id,
                source_path,
                status,
                int(counts.get("records_read") or 0),
                int(counts.get("records_written") or 0),
                int(counts.get("records_skipped") or 0),
                int(counts.get("records_failed") or 0),
                started_at or utc_now(),
                utc_now(),
                message or "",
            ),
        )
        self.conn.commit()

    def list_runs(self, process_id: int | None = None, limit: int = 100, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        clauses = []
        params: list[Any] = []
        if process_id:
            clauses.append("r.process_id = ?")
            params.append(process_id)
        for key, col in [("status", "r.status"), ("run_mode", "r.run_mode")]:
            if filters.get(key):
                clauses.append(f"{col} = ?")
                params.append(filters[key])
        if filters.get("process_id"):
            clauses.append("r.process_id = ?")
            params.append(int(filters["process_id"]))
        where = " AND ".join(clauses) if clauses else "1=1"
        rows = self.conn.execute(
            f"""
            SELECT r.*, p.process_name, p.process_type
            FROM lp_process_run r
            JOIN lp_process p ON p.process_id = r.process_id
            WHERE {where}
            ORDER BY r.started_at_utc DESC, r.process_run_id DESC
            LIMIT ?
            """,
            params + [max(1, int(limit or 1))],
        ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: int) -> dict | None:
        row = self.conn.execute(
            """
            SELECT r.*, p.process_name, p.process_type
            FROM lp_process_run r
            JOIN lp_process p ON p.process_id = r.process_id
            WHERE r.process_run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_run_messages(self, run_id: int) -> list[dict]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT * FROM lp_process_run_message WHERE process_run_id = ? ORDER BY process_run_message_id",
                (run_id,),
            ).fetchall()
        ]

    def list_run_files(self, run_id: int) -> list[dict]:
        return [
            dict(row)
            for row in self.conn.execute(
                """
                SELECT rf.*, pf.file_name, pf.detected_file_type, pf.detected_record_types
                FROM lp_process_run_file rf
                LEFT JOIN lp_process_file pf ON pf.process_file_id = rf.process_file_id
                WHERE rf.process_run_id = ?
                ORDER BY rf.process_run_file_id
                """,
                (run_id,),
            ).fetchall()
        ]

    def has_running_process(self, process_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM lp_process_run WHERE process_id = ? AND status IN ('pending', 'running') LIMIT 1",
            (process_id,),
        ).fetchone()
        return bool(row)

    def recover_stale_running_runs(self, older_than_hours: int = 24) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        cur = self.conn.execute(
            """
            UPDATE lp_process_run
            SET status = 'failed', finished_at_utc = ?, error_message = 'Recovered stale running process run.'
            WHERE status IN ('pending', 'running') AND started_at_utc < ?
            """,
            (utc_now(), cutoff),
        )
        self.conn.commit()
        return int(cur.rowcount or 0)

    @staticmethod
    def parse_config(process: dict) -> dict[str, Any]:
        try:
            return json.loads(process.get("configuration_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}

    def _process_dict(self, row) -> dict:
        item = dict(row)
        item["configuration"] = self.parse_config(item)
        return item
