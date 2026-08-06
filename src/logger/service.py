from __future__ import annotations

import os
import threading
from contextlib import closing
from pathlib import Path

from logger.config import LoggerConfig, load_logger_config
from logger.database import connect, database_size, replace_database
from logger.exceptions import LoggerBusyError
from logger.ingest.aggie_importer import AggieImporter
from logger.ingest.file_discovery import discover_logger_files
from logger.ingest.file_hash import sha256_file
from logger.ingest.mobile_app_inventory_importer import MobileAppInventoryImporter
from logger.ingest.mobile_app_usage_importer import MobileAppUsageImporter
from logger.processing.activity_session_builder import rebuild_activity_sessions
from logger.processing.application_resolver import rebuild_application_catalog
from logger.repository import ingest_repository, processing_repository, sample_repository, session_repository
from logger.schema import CURRENT_SCHEMA_VERSION, ensure_schema, schema_version
from logger.status import LoggerRunSummary, LoggerStatus


_PROCESSING_LOCK = threading.Lock()


class LoggerService:
    def __init__(self, config: LoggerConfig | None = None, *, main_conn=None, user_id=None, username=None):
        self.config = config or load_logger_config(main_conn, user_id=user_id, username=username)
        self.importers = [
            MobileAppUsageImporter(),
            MobileAppInventoryImporter(),
            AggieImporter(),
        ]

    def get_status(self) -> LoggerStatus:
        with closing(self._connect()) as conn:
            counts = sample_repository.sample_counts(conn)
            ingest_counts = {
                row["import_status"]: row["count"]
                for row in conn.execute(
                    "SELECT import_status, COUNT(1) AS count FROM ingest_file GROUP BY import_status"
                ).fetchall()
            }
            activity = conn.execute(
                """
                SELECT COUNT(1) AS count, MIN(start_at_utc) AS first_at, MAX(end_at_utc) AS last_at
                FROM activity_session
                """
            ).fetchone()
            return LoggerStatus(
                main_database_path=str(self.config.main_database_path or ""),
                database_path=str(self.config.database_path),
                database_exists=self.config.database_path.exists(),
                database_size_bytes=database_size(self.config.database_path),
                schema_version=schema_version(conn),
                mobile_source_path=str(self.config.mobile_source_path or ""),
                aggie_source_path=str(self.config.aggie_source_path or ""),
                session_gap_seconds=self.config.session_gap_seconds,
                minimum_session_seconds=self.config.minimum_session_seconds,
                is_running=processing_repository.is_running(conn),
                last_refresh=processing_repository.latest_run(conn, "refresh", successful=True),
                last_rebuild_sessions=processing_repository.latest_run(conn, "rebuild_sessions", successful=True),
                last_rebuild_database=processing_repository.latest_run(conn, "rebuild_database", successful=True),
                sample_counts=counts,
                ingest_counts=ingest_counts,
                activity_session_count=int(activity["count"] or 0),
                first_activity_at_utc=activity["first_at"] or "",
                last_activity_at_utc=activity["last_at"] or "",
            )

    def recent_sessions(
        self,
        limit: int = 100,
        device_id: str | None = None,
        platform: str | None = None,
        application_identifier: str | None = None,
        date: str | None = None,
    ) -> list[dict]:
        with closing(self._connect()) as conn:
            return session_repository.recent_sessions(
                conn,
                limit=limit,
                device_id=device_id,
                platform=platform,
                application_identifier=application_identifier,
                date=date,
            )

    def get_recent_sessions(
        self,
        limit: int = 100,
        device_id: str | None = None,
        platform: str | None = None,
        application_identifier: str | None = None,
        date: str | None = None,
    ) -> list[dict]:
        return self.recent_sessions(
            limit=limit,
            device_id=device_id,
            platform=platform,
            application_identifier=application_identifier,
            date=date,
        )

    def recent_processing_runs(self, limit: int = 50) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM processing_run
                ORDER BY started_at_utc DESC, processing_run_id DESC
                LIMIT ?
                """,
                (max(1, int(limit or 1)),),
            ).fetchall()
            return [dict(row) for row in rows]

    def failed_files(self, limit: int = 25) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT source_type, device_id, source_path, file_name, error_message, updated_at_utc
                FROM ingest_file
                WHERE import_status = 'failed'
                ORDER BY updated_at_utc DESC, ingest_file_id DESC
                LIMIT ?
                """,
                (max(1, int(limit or 1)),),
            ).fetchall()
            return [dict(row) for row in rows]

    def refresh(self) -> LoggerRunSummary:
        if not _PROCESSING_LOCK.acquire(blocking=False):
            raise LoggerBusyError("Logger processing is already running.")
        try:
            with closing(self._connect()) as conn:
                run_id = processing_repository.start_run(conn, "refresh")
                try:
                    stats = self._import_all(conn)
                    sessions_created = 0
                    if stats["files_imported"] > 0:
                        with conn:
                            rebuild_application_catalog(conn)
                        sessions_created = rebuild_activity_sessions(
                            conn,
                            self.config.session_gap_seconds,
                            self.config.minimum_session_seconds,
                        )
                    status = "completed_with_errors" if stats["files_failed"] else "completed"
                    processing_repository.complete_run(
                        conn,
                        run_id,
                        status,
                        **stats,
                        sessions_created=sessions_created,
                        message=_run_message(stats, sessions_created),
                    )
                    return LoggerRunSummary(status=status, run_type="refresh", **stats, sessions_created=sessions_created)
                except Exception as exc:
                    processing_repository.complete_run(conn, run_id, "failed", error_message=str(exc))
                    raise
        finally:
            _PROCESSING_LOCK.release()

    def rebuild_sessions(self) -> LoggerRunSummary:
        if not _PROCESSING_LOCK.acquire(blocking=False):
            raise LoggerBusyError("Logger processing is already running.")
        try:
            with closing(self._connect()) as conn:
                run_id = processing_repository.start_run(conn, "rebuild_sessions")
                try:
                    with conn:
                        rebuild_application_catalog(conn)
                    sessions_created = rebuild_activity_sessions(
                        conn,
                        self.config.session_gap_seconds,
                        self.config.minimum_session_seconds,
                    )
                    processing_repository.complete_run(
                        conn,
                        run_id,
                        "completed",
                        sessions_created=sessions_created,
                        message=f"Rebuilt {sessions_created} activity sessions.",
                    )
                    return LoggerRunSummary(
                        status="completed",
                        run_type="rebuild_sessions",
                        sessions_created=sessions_created,
                    )
                except Exception as exc:
                    processing_repository.complete_run(conn, run_id, "failed", error_message=str(exc))
                    raise
        finally:
            _PROCESSING_LOCK.release()

    def rebuild_database(self) -> LoggerRunSummary:
        if not _PROCESSING_LOCK.acquire(blocking=False):
            raise LoggerBusyError("Logger processing is already running.")
        temp_path = self.config.database_path.with_suffix(self.config.database_path.suffix + ".rebuild")
        try:
            self._remove_sqlite_files(temp_path)
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            rebuild_config = LoggerConfig(
                database_path=temp_path,
                mobile_source_path=self.config.mobile_source_path,
                aggie_source_path=self.config.aggie_source_path,
                session_gap_seconds=self.config.session_gap_seconds,
                minimum_session_seconds=self.config.minimum_session_seconds,
            )
            with closing(connect(temp_path)) as conn:
                ensure_schema(conn)
                run_id = processing_repository.start_run(conn, "rebuild_database")
                try:
                    stats = self._import_all(conn)
                    with conn:
                        rebuild_application_catalog(conn)
                    sessions_created = rebuild_activity_sessions(
                        conn,
                        rebuild_config.session_gap_seconds,
                        rebuild_config.minimum_session_seconds,
                    )
                    self._validate(conn)
                    status = "completed_with_errors" if stats["files_failed"] else "completed"
                    processing_repository.complete_run(
                        conn,
                        run_id,
                        status,
                        **stats,
                        sessions_created=sessions_created,
                        message=_run_message(stats, sessions_created),
                    )
                except Exception as exc:
                    processing_repository.complete_run(conn, run_id, "failed", error_message=str(exc))
                    raise
                conn.execute("PRAGMA wal_checkpoint(FULL)")
            replace_database(temp_path, self.config.database_path)
            self._remove_sqlite_files(temp_path)
            return LoggerRunSummary(
                status=status,
                run_type="rebuild_database",
                **stats,
                sessions_created=sessions_created,
            )
        except Exception as exc:
            self._record_failed_rebuild(str(exc))
            self._remove_sqlite_files(temp_path)
            raise
        finally:
            _PROCESSING_LOCK.release()

    def _connect(self):
        self.config.database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = connect(self.config.database_path)
        ensure_schema(conn)
        return conn

    def _import_all(self, conn) -> dict:
        files = discover_logger_files(self.config.mobile_source_path, self.config.aggie_source_path)
        stats = {
            "files_scanned": len(files),
            "files_imported": 0,
            "files_skipped": 0,
            "files_failed": 0,
            "records_imported": 0,
        }
        for source_file in files:
            file_hash = sha256_file(source_file.source_path)
            existing = ingest_repository.get_by_path(conn, source_file.source_path)
            if existing and existing.get("file_hash") == file_hash and existing.get("import_status") == "imported":
                stats["files_skipped"] += 1
                continue
            duplicate = ingest_repository.get_imported_by_hash(conn, file_hash)
            if duplicate and str(duplicate.get("source_path")) != str(source_file.source_path):
                with conn:
                    ingest_repository.create_superseded_duplicate(conn, source_file, file_hash, duplicate.get("source_path") or "")
                stats["files_skipped"] += 1
                continue
            try:
                with conn:
                    if existing:
                        ingest_repository.delete_by_path(conn, source_file.source_path)
                    ingest_file_id = ingest_repository.create_importing(conn, source_file, file_hash)
                    importer = self._importer_for(source_file)
                    result = importer.import_file(conn, ingest_file_id, source_file)
                    ingest_repository.mark_imported(conn, ingest_file_id, result)
                stats["files_imported"] += 1
                stats["records_imported"] += int(result.record_count or 0)
            except Exception as exc:
                conn.rollback()
                stats["files_failed"] += 1
                try:
                    with conn:
                        if existing:
                            ingest_repository.delete_by_path(conn, source_file.source_path)
                        ingest_file_id = ingest_repository.create_importing(conn, source_file, file_hash)
                        ingest_repository.mark_failed(conn, ingest_file_id, str(exc))
                except Exception:
                    conn.rollback()
        return stats

    def _importer_for(self, source_file):
        for importer in self.importers:
            if importer.can_import(source_file):
                return importer
        raise ValueError(f"No logger importer for source type {source_file.source_type}")

    def _validate(self, conn) -> None:
        if schema_version(conn) != CURRENT_SCHEMA_VERSION:
            raise ValueError("Logger database schema version is not current.")
        bad_sessions = conn.execute(
            """
            SELECT COUNT(1) AS count
            FROM activity_session
            WHERE duration_seconds < 0
               OR end_at_utc < start_at_utc
               OR COALESCE(device_id, '') = ''
               OR COALESCE(source_type, '') = ''
            """
        ).fetchone()
        if int(bad_sessions["count"] or 0):
            raise ValueError("Logger database contains invalid activity sessions.")
        duplicates = conn.execute(
            """
            SELECT COUNT(1) AS count
            FROM (
                SELECT session_hash FROM activity_session GROUP BY session_hash HAVING COUNT(1) > 1
            )
            """
        ).fetchone()
        if int(duplicates["count"] or 0):
            raise ValueError("Logger database contains duplicate activity session hashes.")
        orphans = conn.execute(
            """
            SELECT
                (SELECT COUNT(1)
                   FROM mobile_app_usage_sample s
                   LEFT JOIN ingest_file f ON f.ingest_file_id = s.ingest_file_id
                  WHERE f.ingest_file_id IS NULL)
              + (SELECT COUNT(1)
                   FROM desktop_window_sample s
                   LEFT JOIN ingest_file f ON f.ingest_file_id = s.ingest_file_id
                  WHERE f.ingest_file_id IS NULL) AS count
            """
        ).fetchone()
        if int(orphans["count"] or 0):
            raise ValueError("Logger database contains samples without ingest files.")
        activity_range = conn.execute(
            "SELECT MIN(start_at_utc) AS first_at, MAX(end_at_utc) AS last_at FROM activity_session"
        ).fetchone()
        if activity_range["first_at"] and activity_range["last_at"] and activity_range["first_at"] > activity_range["last_at"]:
            raise ValueError("Logger database contains an invalid activity time range.")
        mismatches = conn.execute(
            """
            SELECT COUNT(1) AS count
            FROM ingest_file f
            WHERE f.import_status = 'imported'
              AND f.source_type IN ('mobile_app_usage', 'aggie_window_usage')
              AND f.record_count != CASE f.source_type
                  WHEN 'mobile_app_usage' THEN (
                      SELECT COUNT(1) FROM mobile_app_usage_sample s WHERE s.ingest_file_id = f.ingest_file_id
                  )
                  WHEN 'aggie_window_usage' THEN (
                      SELECT COUNT(1) FROM desktop_window_sample s WHERE s.ingest_file_id = f.ingest_file_id
                  )
              END
            """
        ).fetchone()
        if int(mismatches["count"] or 0):
            raise ValueError("Logger database contains imported file record-count mismatches.")

    def _record_failed_rebuild(self, error_message: str) -> None:
        try:
            with closing(self._connect()) as conn:
                run_id = processing_repository.start_run(conn, "rebuild_database")
                processing_repository.complete_run(conn, run_id, "failed", error_message=error_message)
        except Exception:
            pass

    @staticmethod
    def _remove_sqlite_files(path: Path) -> None:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(path) + suffix)
            try:
                if candidate.exists():
                    os.remove(candidate)
            except OSError:
                pass


def _run_message(stats: dict, sessions_created: int) -> str:
    return (
        f"Scanned {stats.get('files_scanned', 0)} files; "
        f"imported {stats.get('files_imported', 0)}, skipped {stats.get('files_skipped', 0)}, "
        f"failed {stats.get('files_failed', 0)}; "
        f"records {stats.get('records_imported', 0)}; sessions {sessions_created}."
    )
