from __future__ import annotations

import fnmatch
import os
import shutil
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data.processes.process_models import ProcessRunResult, ProcessTypeDefinition, ValidationResult
from data.processes.process_repository import default_logger_config
from logger.database import connect, replace_database
from logger.ingest.file_hash import sha256_file
from logger.logger_file_parser import inspect_logger_file, iter_logger_records
from logger.logger_record_router import insert_raw_record, route_record
from logger.schema import ensure_schema


class LoggerJsonImportHandler:
    process_type = "logger_json_import"

    def get_definition(self) -> ProcessTypeDefinition:
        return ProcessTypeDefinition(
            process_type=self.process_type,
            display_name="Import LifePIM Logger JSON",
            description="Load raw JSON files from the mobile logger into a separate logger SQLite database.",
            supports_preview=True,
            supports_incremental=True,
            supports_rebuild=True,
            default_configuration=default_logger_config(),
        )

    def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        result = ValidationResult()
        source = str(config.get("source_folder") or "").strip()
        database_path = str(config.get("database_path") or "").strip()
        if not source:
            result.add("error", "source_folder", "Source folder is required.", "SOURCE_FOLDER_REQUIRED")
        elif not Path(_resolve_path(source)).is_dir():
            result.add("error", "source_folder", "Source folder does not exist.", "SOURCE_FOLDER_MISSING")
        if not database_path:
            result.add("error", "database_path", "Logger database path is required.", "DATABASE_PATH_REQUIRED")
        if config.get("successful_file_action") == "move" and not str(config.get("processed_folder") or "").strip():
            result.add("error", "processed_folder", "Processed folder is required when successful files are moved.", "PROCESSED_FOLDER_REQUIRED")
        if str(config.get("duplicate_detection") or "") not in {"metadata", "metadata_and_hash", "hash"}:
            result.add("error", "duplicate_detection", "Duplicate detection mode is invalid.", "DUPLICATE_MODE_INVALID")
        return result

    def preview(self, config: dict[str, Any], context) -> ProcessRunResult:
        context.info("SOURCE_SCAN_STARTED", "Scanning configured logger source folder.")
        files = _discover_files(config)
        counts = Counter()
        record_types = Counter()
        for path in files:
            info = _file_info(path, calculate_hash=bool(config.get("calculate_hash_during_preview")))
            process_file_id = context.register_file({**info, "status": "discovered"})
            duplicate = _duplicate_reason(context.repository, context.process_id, info, config)
            inspection = inspect_logger_file(path)
            if inspection.invalid:
                counts["invalid"] += 1
                context.add_run_file(process_file_id, str(path), "failed", {"records_failed": 1}, inspection.error_message)
                context.warning("INVALID_JSON", f"{path.name} could not be parsed.", {"source_path": str(path)})
                continue
            for record_type in inspection.detected_record_types:
                record_types[record_type] += inspection.records_read
            status = "skipped" if duplicate else "discovered"
            counts[status] += 1
            context.add_run_file(
                process_file_id,
                str(path),
                status,
                {"records_read": inspection.records_read, "records_skipped": inspection.records_read if duplicate else 0},
                duplicate or "Would import file.",
            )
        summary = _preview_summary(len(files), counts, record_types)
        return ProcessRunResult(
            status="warning" if counts["invalid"] else "success",
            summary=summary,
            files_found=len(files),
            files_processed=0,
            files_skipped=counts["skipped"],
            files_failed=counts["invalid"],
            records_read=sum(record_types.values()),
            records_skipped=0,
        )

    def run(self, config: dict[str, Any], context) -> ProcessRunResult:
        return self._import(config, context, rebuild=False)

    def rebuild(self, config: dict[str, Any], context) -> ProcessRunResult:
        target = Path(_resolve_path(config.get("database_path") or ""))
        temp_path = target.with_suffix(target.suffix + ".rebuild")
        _remove_sqlite_files(temp_path)
        try:
            result = self._import(config, context, rebuild=True, database_path=temp_path)
            if result.status in {"success", "warning"}:
                with closing(connect(temp_path)) as conn:
                    conn.execute("PRAGMA wal_checkpoint(FULL)")
                replace_database(temp_path, target)
                _remove_sqlite_files(temp_path)
                context.info("REBUILD_REPLACED_DATABASE", "Replaced logger database with rebuilt copy.", {"database_path": str(target)})
            return result
        except Exception:
            _remove_sqlite_files(temp_path)
            raise

    def _import(self, config: dict[str, Any], context, *, rebuild: bool = False, database_path: Path | None = None) -> ProcessRunResult:
        files = _discover_files(config)
        target_path = database_path or Path(_resolve_path(config.get("database_path") or ""))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        totals = Counter(files_found=len(files))
        if not files:
            context.info("NO_MATCHING_FILES", "No matching logger JSON files were found.")
            return ProcessRunResult(status="success", summary="No matching files found.", files_found=0)
        context.info("SOURCE_SCAN_FINISHED", f"Found {len(files)} matching logger JSON file(s).")
        with closing(connect(target_path)) as logger_conn:
            ensure_schema(logger_conn)
            for path in files:
                started_at = context.repository.__class__.__dict__.get("utc_now", None)
                del started_at
                file_counts = Counter(source_path=str(path))
                process_file_id = None
                try:
                    file_info = _file_info(path, calculate_hash=True)
                    process_file_id = context.register_file({**file_info, "status": "discovered"})
                    if not rebuild:
                        duplicate = _duplicate_reason(context.repository, context.process_id, file_info, config)
                        if duplicate:
                            file_counts["records_skipped"] = 0
                            totals["files_skipped"] += 1
                            context.update_file_result(process_file_id, "skipped", file_counts, duplicate)
                            context.info("DUPLICATE_FILE", f"Skipped duplicate file {path.name}.", {"source_path": str(path)})
                            continue
                    detected_types = Counter()
                    with logger_conn:
                        for parsed in iter_logger_records(path):
                            file_counts["records_read"] += 1
                            detected_types[parsed.record_type] += 1
                            raw_id = insert_raw_record(logger_conn, parsed, context.process_run_id, process_file_id, str(path), file_info.get("file_hash"))
                            routed = route_record(logger_conn, parsed, raw_id, context.process_run_id, process_file_id, str(path))
                            if routed == "unknown" and not config.get("allow_unknown_record_types", True):
                                raise ValueError(f"Unknown record type in {path.name}.")
                            if routed == "unknown":
                                detected_types["unknown"] += 1
                                file_counts["records_skipped"] += 1
                            else:
                                file_counts["records_written"] += 1
                    status = "warning" if detected_types.get("unknown") else "imported"
                    message = "Imported with unknown records." if status == "warning" else "Imported file."
                    if status == "warning":
                        totals["files_warning"] += 1
                    totals["files_processed"] += 1
                    totals["records_read"] += file_counts["records_read"]
                    totals["records_written"] += file_counts["records_written"]
                    totals["records_skipped"] += file_counts["records_skipped"]
                    context.update_file_result(process_file_id, status, file_counts, message, ",".join(sorted(detected_types)))
                    context.info("FILE_IMPORTED", f"Imported {path.name}.", {"source_path": str(path), "records": file_counts["records_written"]})
                    if config.get("successful_file_action") == "move" and not rebuild:
                        try:
                            _move_successful_file(path, config)
                        except Exception as exc:
                            context.warning("MOVE_AFTER_SUCCESS_FAILED", f"Imported {path.name}, but moving it failed: {exc}", {"source_path": str(path)})
                            totals["files_failed"] += 1
                            context.update_file_result(process_file_id, "warning", file_counts, f"Move after import failed: {exc}", ",".join(sorted(detected_types)))
                except Exception as exc:
                    logger_conn.rollback()
                    file_counts["records_failed"] += max(1, file_counts["records_read"])
                    totals["files_failed"] += 1
                    totals["records_failed"] += file_counts["records_failed"]
                    message = str(exc)
                    if process_file_id:
                        context.update_file_result(process_file_id, "failed", file_counts, message)
                    else:
                        context.add_run_file(None, str(path), "failed", file_counts, message)
                    context.error("FILE_IMPORT_FAILED", f"{path.name} could not be imported.", {"source_path": str(path), "error": message})
                    if config.get("stop_on_file_error"):
                        break
        status = "failed" if totals["files_processed"] == 0 and totals["files_failed"] else "warning" if totals["files_failed"] or totals["files_warning"] else "success"
        summary = (
            f"Found {totals['files_found']} file(s); imported {totals['files_processed']}, "
            f"skipped {totals['files_skipped']}, failed {totals['files_failed']}; "
            f"records written {totals['records_written']}."
        )
        return ProcessRunResult(
            status=status,
            summary=summary,
            files_found=totals["files_found"],
            files_processed=totals["files_processed"],
            files_skipped=totals["files_skipped"],
            files_failed=totals["files_failed"],
            records_read=totals["records_read"],
            records_written=totals["records_written"],
            records_skipped=totals["records_skipped"],
            records_failed=totals["records_failed"],
            error_message="" if status != "failed" else summary,
        )


def _discover_files(config: dict[str, Any]) -> list[Path]:
    root = Path(_resolve_path(config.get("source_folder") or ""))
    patterns = _file_patterns(config.get("file_pattern") or "*.json;*.jsonl")
    include_subfolders = bool(config.get("include_subfolders", True))
    if not root.is_dir():
        return []
    paths = []
    if include_subfolders:
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if _matches_any_pattern(filename, patterns):
                    paths.append(Path(dirpath) / filename)
    else:
        paths = [path for path in root.iterdir() if path.is_file() and _matches_any_pattern(path.name, patterns)]
    return sorted(paths, key=lambda item: str(item).lower())


def _file_patterns(value: str) -> list[str]:
    text = str(value or "").replace(",", ";").replace("\n", ";")
    patterns = [item.strip() for item in text.split(";") if item.strip()]
    return patterns or ["*.json", "*.jsonl"]


def _matches_any_pattern(filename: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)


def _file_info(path: Path, *, calculate_hash: bool) -> dict[str, Any]:
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    normalised = os.path.normcase(os.path.abspath(str(path)))
    return {
        "source_path": str(path),
        "source_path_normalised": normalised,
        "file_name": path.name,
        "file_size_bytes": stat.st_size,
        "file_modified_at_utc": modified,
        "file_hash": sha256_file(path) if calculate_hash else "",
        "detected_file_type": "json",
    }


def _duplicate_reason(repository, process_id: int, file_info: dict[str, Any], config: dict[str, Any]) -> str:
    mode = config.get("duplicate_detection") or "metadata_and_hash"
    if mode in {"metadata", "metadata_and_hash"}:
        match = repository.find_imported_by_metadata(
            process_id,
            file_info["source_path_normalised"],
            file_info["file_size_bytes"],
            file_info["file_modified_at_utc"],
        )
        if match:
            return "Previously imported matching file metadata."
    if mode in {"hash", "metadata_and_hash"} and file_info.get("file_hash"):
        match = repository.find_imported_by_hash(process_id, file_info["file_hash"])
        if match:
            return f"Duplicate content already imported from {match.get('source_path') or 'another file'}."
    return ""


def _resolve_path(value: str) -> str:
    from common import config as app_config

    text = str(value or "").strip()
    db_file = Path(getattr(app_config, "DB_FILE", "") or "").expanduser()
    db_dir = str(db_file.parent) if str(db_file) else ""
    data_folder = getattr(app_config, "data_folder", "") or getattr(app_config, "user_folder", ".")
    text = text.replace("<LIFEPIM_DB_DIR>", db_dir).replace("<LIFEPIM_DATA>", data_folder)
    return str(Path(text).expanduser())


def _preview_summary(file_count: int, counts: Counter, record_types: Counter) -> str:
    type_text = ", ".join(f"{name}: {count}" for name, count in sorted(record_types.items())) or "none detected"
    return (
        f"Matching files: {file_count}; new files: {counts['discovered']}; "
        f"previously imported: {counts['skipped']}; invalid files: {counts['invalid']}; "
        f"detected records: {type_text}."
    )


def _move_successful_file(path: Path, config: dict[str, Any]) -> None:
    target_dir = Path(_resolve_path(config.get("processed_folder") or ""))
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = target_dir / f"{path.stem}.{stamp}{path.suffix}"
    shutil.move(str(path), str(target))


def _remove_sqlite_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass
