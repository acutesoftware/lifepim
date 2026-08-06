from __future__ import annotations

from .base_importer import ImportResult, LoggerSourceFile, extra_json, iter_json_records, parse_utc, pick, utc_string


class MobileAppUsageImporter:
    source_type = "mobile_app_usage"

    def can_import(self, source_file: LoggerSourceFile) -> bool:
        return source_file.source_type == self.source_type

    def import_file(self, connection, ingest_file_id: int, source_file: LoggerSourceFile) -> ImportResult:
        result = ImportResult()
        first = last = None
        rows = []
        known = {
            "timestamp", "timestamp_utc", "observed_at", "observed_at_utc", "time", "ts", "date",
            "device_id", "device", "package_name", "packagename", "package", "app",
            "application_name", "app_name", "label", "name", "activity_name", "activity",
            "screen_state", "screenstate", "event_type", "event", "type",
            "capturedat", "capturedatmillis", "packagename", "appname", "classname",
            "eventtimemillis", "eventtype", "androideventtype", "apps",
        }
        for index, record in iter_json_records(source_file.source_path):
            for expanded_index, sample in enumerate(_expand_usage_record(record)):
                package_name = pick(sample, "package_name", "packageName", "package", "app")
                event_type = pick(sample, "event_type", "eventType", "event", "type")
                observed = parse_utc(
                    pick(
                        sample,
                        "observed_at_utc",
                        "timestamp_utc",
                        "eventTimeMillis",
                        "lastTimeUsedMillis",
                        "capturedAt",
                        "capturedAtMillis",
                        "observed_at",
                        "timestamp",
                        "time",
                        "ts",
                        "date",
                    )
                )
                if observed is None:
                    if package_name:
                        raise ValueError(f"record {index} has no timestamp")
                    continue
                device_id = str(pick(sample, "device_id", "device") or source_file.device_id or "unknown").strip() or "unknown"
                if not package_name and str(event_type or "").lower() not in {"screen_off", "off", "locked"}:
                    continue
                application_name = pick(sample, "application_name", "app_name", "appName", "label", "name")
                rows.append(
                    (
                        ingest_file_id,
                        index * 1000 + expanded_index,
                        device_id,
                        utc_string(observed),
                        package_name,
                        application_name,
                        pick(sample, "activity_name", "activity", "className"),
                        pick(sample, "screen_state", "screenState"),
                        event_type,
                        extra_json(sample, known),
                    )
                )
                first = observed if first is None or observed < first else first
                last = observed if last is None or observed > last else last
        connection.executemany(
            """
            INSERT INTO mobile_app_usage_sample
            (ingest_file_id, source_record_index, device_id, observed_at_utc, package_name,
             application_name, activity_name, screen_state, event_type, extra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        result.record_count = len(rows)
        result.first_record_at_utc = first
        result.last_record_at_utc = last
        return result


def _expand_usage_record(record: dict) -> list[dict]:
    apps = record.get("apps")
    if isinstance(apps, list):
        expanded = []
        base = {key: value for key, value in record.items() if key != "apps"}
        for app in apps:
            if isinstance(app, dict):
                merged = dict(base)
                merged.update(app)
                expanded.append(merged)
        return expanded
    return [record]
