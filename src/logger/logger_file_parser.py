from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logger.ingest.base_importer import iter_json_records, parse_utc, pick, utc_string


@dataclass
class ParsedLoggerRecord:
    index: int
    record: dict[str, Any]
    record_type: str
    observed_at_utc: str | None
    device_id: str
    raw_json: str


@dataclass
class LoggerFileInspection:
    detected_file_type: str = "json"
    detected_record_types: set[str] = field(default_factory=set)
    records_read: int = 0
    invalid: bool = False
    error_message: str = ""


def inspect_logger_file(path: Path, *, max_records: int | None = None) -> LoggerFileInspection:
    inspection = LoggerFileInspection()
    try:
        for parsed in iter_logger_records(path):
            inspection.records_read += 1
            inspection.detected_record_types.add(parsed.record_type)
            if max_records and inspection.records_read >= max_records:
                break
    except Exception as exc:
        inspection.invalid = True
        inspection.error_message = str(exc)
    return inspection


def iter_logger_records(path: Path):
    for index, record in iter_json_records(path):
        record_type = detect_record_type(record, path)
        observed = utc_string(
            parse_utc(
                pick(
                    record,
                    "observed_at_utc",
                    "timestamp_utc",
                    "capturedAt",
                    "capturedAtMillis",
                    "eventTimeMillis",
                    "lastTimeUsedMillis",
                    "observed_at",
                    "timestamp",
                    "time",
                    "ts",
                    "date",
                )
            )
        )
        device_id = str(pick(record, "device_id", "device", "deviceId") or _device_from_path(path) or "unknown").strip() or "unknown"
        yield ParsedLoggerRecord(
            index=index,
            record=record,
            record_type=record_type,
            observed_at_utc=observed,
            device_id=device_id,
            raw_json=json.dumps(record, ensure_ascii=True, sort_keys=True, default=str),
        )


def detect_record_type(record: dict[str, Any], path: Path | None = None) -> str:
    explicit_type = str(pick(record, "record_type", "type", "event_type", "event") or "").lower()
    keys = {str(key).lower() for key in record.keys()}
    path_text = str(path or "").lower()

    if explicit_type in {"installed_app", "app_catalog", "application_inventory", "mobile_app_inventory"}:
        return "installed_application"
    if explicit_type in {"location", "location_sample", "gps"} or {"latitude", "longitude"}.issubset(keys) or {"lat", "lon"}.issubset(keys):
        return "location"
    if explicit_type in {"device_state", "phone_usage_event", "screen_off", "screen_on"}:
        return "device_state"
    if explicit_type in {"app_usage_event", "activity_resumed", "activity_paused", "mobile_app_usage"}:
        return "app_usage"
    if "apps" in keys and ("snapshot" in explicit_type or "usage" in path_text):
        return "app_usage"
    if any(key in keys for key in {"package_name", "packagename", "package", "packagename", "appname", "package_name"}):
        if "catalog" in path_text or "inventory" in path_text or "installed" in path_text:
            return "installed_application"
        return "app_usage"
    if any(key in keys for key in {"screen_state", "battery_percent", "battery", "network_type"}):
        return "device_state"
    return explicit_type or "unknown"


def _device_from_path(path: Path) -> str:
    parts = path.parts
    for marker in ("mobile", "logger", "raw"):
        lower_parts = [part.lower() for part in parts]
        if marker in lower_parts:
            idx = lower_parts.index(marker)
            if idx + 1 < len(parts):
                return parts[idx + 1]
    if len(parts) >= 2:
        return parts[-2]
    return ""
