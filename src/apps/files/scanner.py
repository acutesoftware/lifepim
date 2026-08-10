"""File Inventory scanner orchestration."""

from __future__ import annotations

import os
import sqlite3
import traceback

from apps.files import inventory_db
from apps.files.change_detector import classify_change
from apps.files.providers.full_scan import FullScanProvider, normalize_scope, scoped_root
from apps.files.providers.ntfs_usn import WindowsNtfsUsnProvider
from apps.files.scan_models import ScanResult


class FileInventoryScanner:
    def __init__(self, db_path: str | None = None, conn: sqlite3.Connection | None = None):
        self._external_conn = conn
        self.conn = conn or inventory_db.connect(db_path)
        inventory_db.ensure_schema(self.conn)
        self.full_provider = FullScanProvider()
        self.usn_provider = WindowsNtfsUsnProvider()

    def close(self):
        if not self._external_conn:
            self.conn.close()

    def scan(self, source_id: int, scope: str = "/", mode: str = "AUTO") -> ScanResult:
        source = inventory_db.get_source(self.conn, source_id)
        mode = (mode or "AUTO").upper()
        if mode not in {"AUTO", "FULL", "INCREMENTAL", "SCOPED"}:
            raise ValueError(f"Unknown scan mode: {mode}")
        if not source:
            raise ValueError(f"File source not found: {source_id}")
        if not int(source["enabled"] or 0):
            raise ValueError(f"File source is disabled: {source_id}")

        root_path = source["root_path"]
        scan_scope = normalize_scope(scope)
        actual_mode, provider_name = self._choose_mode(source, scan_scope, mode)
        result = ScanResult(
            scan_id=None,
            source_id=int(source_id),
            scope=scan_scope or "/",
            requested_mode=mode,
            scan_mode=actual_mode,
            provider=provider_name,
        )

        try:
            target_root = scoped_root(root_path, scan_scope)
            if not os.path.isdir(root_path):
                raise FileNotFoundError(f"Source root not found: {root_path}")
            if not os.path.isdir(target_root):
                raise FileNotFoundError(f"Scan scope not found: {target_root}")
        except Exception as exc:
            scan_id = self._start_scan(source, scan_scope, actual_mode, provider_name)
            result.scan_id = scan_id
            result.status = "FAILED"
            result.errors = 1
            result.error_messages.append(str(exc))
            self._finish_scan(result, error_text=str(exc))
            return result

        scan_id = self._start_scan(source, scan_scope, actual_mode, provider_name)
        result.scan_id = scan_id
        seen = set()
        try:
            for record in self.full_provider.iter_files(root_path, scan_scope):
                seen.add(record.normalized_relative_path)
                self._reconcile_record(record, result)
            if self.full_provider.errors:
                result.errors += len(self.full_provider.errors)
                result.error_messages.extend(self.full_provider.errors[:20])
            self._mark_missing_deleted(source_id, scan_scope, scan_id, seen, result)
            result.status = "SUCCESS"
            self._finish_scan(result)
            return result
        except Exception as exc:
            self.conn.rollback()
            result.status = "FAILED"
            result.errors += 1
            result.error_messages.append(str(exc))
            self._finish_scan(result, error_text="\n".join(result.error_messages + [traceback.format_exc(limit=3)]))
            return result

    def _choose_mode(self, source, scan_scope: str, requested_mode: str):
        if scan_scope:
            return "SCOPED", self.full_provider.name
        if requested_mode == "FULL":
            return "FULL", self.full_provider.name
        last_scan = inventory_db.last_successful_scan(self.conn, source["source_id"])
        if requested_mode == "AUTO" and not last_scan:
            return "FULL", self.full_provider.name
        if requested_mode in {"AUTO", "INCREMENTAL"} and self.usn_provider.is_available(source, source["provider_checkpoint"]):
            return "INCREMENTAL", self.usn_provider.name
        return ("FULL" if requested_mode == "AUTO" else requested_mode), self.full_provider.name

    def _start_scan(self, source, scan_scope: str, scan_mode: str, provider_name: str) -> int:
        now = inventory_db.utc_now()
        cur = self.conn.execute(
            "INSERT INTO lp_file_scan "
            "(source_id, scope_path, scan_mode, started_at, status, change_provider, provider_checkpoint_before) "
            "VALUES (?, ?, ?, ?, 'RUNNING', ?, ?)",
            (source["source_id"], scan_scope or "/", scan_mode, now, provider_name, source["provider_checkpoint"] or ""),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _reconcile_record(self, record, result: ScanResult) -> None:
        now = inventory_db.utc_now()
        existing = self.conn.execute(
            "SELECT * FROM lp_file WHERE source_id = ? AND normalized_relative_path = ?",
            (result.source_id, record.normalized_relative_path),
        ).fetchone()
        change_type = classify_change(existing, record)
        if change_type == "NEW":
            file_id = self._insert_file(record, result.scan_id, now, result.source_id)
            result.files_new += 1
            self._insert_change(result.scan_id, file_id, "NEW", now)
        else:
            file_id = int(existing["file_id"])
            self._update_file(record, result.scan_id, now, file_id, change_type == "REACTIVATED")
            if change_type == "CHANGED":
                result.files_changed += 1
                self._insert_change(result.scan_id, file_id, "CHANGED", now)
            elif change_type == "REACTIVATED":
                result.files_reactivated += 1
                self._insert_change(result.scan_id, file_id, "REACTIVATED", now)
            else:
                result.files_unchanged += 1
        result.files_seen += 1

    def _insert_file(self, record, scan_id: int, now: str, source_id: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO lp_file "
            "(source_id, fullfilename, path, xtn, name, date_modified, date_created, date_accessed, size, "
            "is_deleted, deleted_at, first_seen_at, last_seen_at, first_seen_scan_id, last_seen_scan_id, "
            "created_at, updated_at, relative_path, parent_relative_path, normalized_relative_path, normalized_path, scan_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT')",
            (
                source_id,
                record.fullfilename,
                record.path,
                record.xtn,
                record.name,
                record.date_modified,
                record.date_created,
                record.date_accessed,
                record.size,
                now,
                now,
                scan_id,
                scan_id,
                now,
                now,
                record.relative_path,
                record.parent_relative_path,
                record.normalized_relative_path,
                record.normalized_path,
            ),
        )
        return int(cur.lastrowid)

    def _update_file(self, record, scan_id: int, now: str, file_id: int, reactivated: bool) -> None:
        self.conn.execute(
            "UPDATE lp_file SET fullfilename = ?, path = ?, xtn = ?, name = ?, date_modified = ?, "
            "date_created = ?, date_accessed = ?, size = ?, is_deleted = 0, deleted_at = NULL, "
            "last_seen_at = ?, last_seen_scan_id = ?, updated_at = ?, relative_path = ?, "
            "parent_relative_path = ?, normalized_path = ?, scan_status = ? WHERE file_id = ?",
            (
                record.fullfilename,
                record.path,
                record.xtn,
                record.name,
                record.date_modified,
                record.date_created,
                record.date_accessed,
                record.size,
                now,
                scan_id,
                now,
                record.relative_path,
                record.parent_relative_path,
                record.normalized_path,
                "REACTIVATED" if reactivated else "CURRENT",
                file_id,
            ),
        )

    def _mark_missing_deleted(self, source_id: int, scan_scope: str, scan_id: int, seen: set[str], result: ScanResult) -> None:
        now = inventory_db.utc_now()
        params = [int(source_id)]
        where = ["source_id = ?", "is_deleted = 0"]
        if scan_scope:
            prefix = scan_scope.replace("\\", "/").strip("/").lower()
            where.append("(normalized_relative_path = ? OR normalized_relative_path LIKE ?)")
            params.extend([prefix, prefix + "/%"])
        rows = self.conn.execute(
            "SELECT file_id, normalized_relative_path FROM lp_file WHERE " + " AND ".join(where),
            params,
        ).fetchall()
        for row in rows:
            if row["normalized_relative_path"] in seen:
                continue
            self.conn.execute(
                "UPDATE lp_file SET is_deleted = 1, deleted_at = ?, updated_at = ?, scan_status = 'DELETED' WHERE file_id = ?",
                (now, now, row["file_id"]),
            )
            self._insert_change(scan_id, row["file_id"], "DELETED", now)
            result.files_deleted += 1

    def _insert_change(self, scan_id: int, file_id: int, change_type: str, detected_at: str) -> None:
        self.conn.execute(
            "INSERT INTO lp_file_change (scan_id, file_id, change_type, detected_at) VALUES (?, ?, ?, ?)",
            (scan_id, file_id, change_type, detected_at),
        )

    def _finish_scan(self, result: ScanResult, error_text: str = "") -> None:
        completed = inventory_db.utc_now()
        self.conn.execute(
            "UPDATE lp_file_scan SET completed_at = ?, status = ?, files_seen = ?, files_new = ?, "
            "files_changed = ?, files_unchanged = ?, files_deleted = ?, files_reactivated = ?, "
            "errors = ?, error_text = ?, provider_checkpoint_after = provider_checkpoint_before "
            "WHERE scan_id = ?",
            (
                completed,
                result.status,
                result.files_seen,
                result.files_new,
                result.files_changed,
                result.files_unchanged,
                result.files_deleted,
                result.files_reactivated,
                result.errors,
                error_text,
                result.scan_id,
            ),
        )
        self.conn.commit()


def scan_files(source_id: int, scope: str = "/", mode: str = "AUTO", db_path: str | None = None) -> ScanResult:
    scanner = FileInventoryScanner(db_path=db_path)
    try:
        return scanner.scan(source_id, scope=scope, mode=mode)
    finally:
        scanner.close()
