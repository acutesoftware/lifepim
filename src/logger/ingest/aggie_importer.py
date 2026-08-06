from __future__ import annotations

from .base_importer import ImportResult, LoggerSourceFile, extra_json, iter_json_records, parse_utc, pick, read_csv_records, utc_string


class AggieImporter:
    source_type = "aggie_window_usage"

    def can_import(self, source_file: LoggerSourceFile) -> bool:
        return source_file.source_type == self.source_type

    def import_file(self, connection, ingest_file_id: int, source_file: LoggerSourceFile) -> ImportResult:
        iterator = iter_json_records(source_file.source_path) if source_file.source_path.suffix.lower() in {".json", ".jsonl"} else read_csv_records(source_file.source_path)
        rows = []
        first = last = None
        known = {
            "timestamp", "timestamp_utc", "observed_at", "observed_at_utc", "time", "datetime", "date", "ts",
            "device_id", "device", "process", "process_name", "processname", "exe", "application_name",
            "app_name", "application", "executable_path", "path", "window_title", "title", "is_idle", "idle",
        }
        for index, record in iterator:
            observed = parse_utc(pick(record, "observed_at_utc", "timestamp_utc", "observed_at", "timestamp", "datetime", "time", "date", "ts"))
            if observed is None:
                raise ValueError(f"record {index} has no timestamp")
            device_id = str(pick(record, "device_id", "device") or source_file.device_id or "desktop").strip() or "desktop"
            idle_value = pick(record, "is_idle", "idle")
            is_idle = 1 if str(idle_value).strip().lower() in {"1", "true", "yes", "idle"} else 0 if idle_value not in (None, "") else None
            rows.append(
                (
                    ingest_file_id,
                    index,
                    device_id,
                    utc_string(observed),
                    pick(record, "process_name", "processName", "process", "exe"),
                    pick(record, "application_name", "app_name", "application"),
                    pick(record, "executable_path", "path"),
                    pick(record, "window_title", "title"),
                    is_idle,
                    extra_json(record, known),
                )
            )
            first = observed if first is None or observed < first else first
            last = observed if last is None or observed > last else last
        connection.executemany(
            """
            INSERT INTO desktop_window_sample
            (ingest_file_id, source_record_index, device_id, observed_at_utc, process_name,
             application_name, executable_path, window_title, is_idle, extra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return ImportResult(record_count=len(rows), first_record_at_utc=first, last_record_at_utc=last)
