from __future__ import annotations

import json

from logger.schema import utc_now

from .base_importer import ImportResult, LoggerSourceFile, iter_json_records, parse_utc, pick, utc_string


class MobileAppInventoryImporter:
    source_type = "mobile_app_inventory"

    def can_import(self, source_file: LoggerSourceFile) -> bool:
        return source_file.source_type == self.source_type

    def import_file(self, connection, ingest_file_id: int, source_file: LoggerSourceFile) -> ImportResult:
        rows = []
        first = last = None
        now = utc_string(parse_utc(source_file.modified_at_utc)) or utc_now()
        for index, record in iter_json_records(source_file.source_path):
            package = pick(record, "package_name", "packageName", "package", "application_identifier")
            if not package:
                continue
            observed = parse_utc(
                pick(
                    record,
                    "observed_at_utc",
                    "timestamp_utc",
                    "capturedAt",
                    "capturedAtMillis",
                    "observed_at",
                    "timestamp",
                    "time",
                    "ts",
                    "date",
                )
            )
            observed_s = utc_string(observed) or now
            name = pick(record, "application_name", "app_name", "appName", "label", "name")
            rows.append(
                (
                    "android",
                    str(package),
                    name,
                    str(package),
                    self.source_type,
                    json.dumps(record, ensure_ascii=True, sort_keys=True, default=str),
                    observed_s,
                    observed_s,
                )
            )
            if observed:
                first = observed if first is None or observed < first else first
                last = observed if last is None or observed > last else last
        connection.executemany(
            """
            INSERT INTO application_catalog
            (platform, application_identifier, application_name, package_name, source_type,
             metadata_json, first_seen_at_utc, last_seen_at_utc, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, application_identifier) DO UPDATE SET
                application_name = COALESCE(excluded.application_name, application_catalog.application_name),
                package_name = COALESCE(excluded.package_name, application_catalog.package_name),
                last_seen_at_utc = excluded.last_seen_at_utc,
                metadata_json = excluded.metadata_json,
                updated_at_utc = excluded.updated_at_utc
            """,
            [row + (row[6], row[7]) for row in rows],
        )
        return ImportResult(record_count=len(rows), first_record_at_utc=first, last_record_at_utc=last)
