from __future__ import annotations

from typing import Any

from logger.ingest.base_importer import pick
from logger.schema import utc_now


def insert_raw_record(conn, parsed, process_run_id: int, process_file_id: int, source_path: str, file_hash: str | None) -> int:
    cur = conn.execute(
        """
        INSERT INTO raw_logger_record(
            process_run_id, process_file_id, source_path, source_file_hash, source_record_index,
            record_type, observed_at_utc, device_id, raw_json, imported_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            process_run_id,
            process_file_id,
            source_path,
            file_hash or "",
            parsed.index,
            parsed.record_type,
            parsed.observed_at_utc,
            parsed.device_id,
            parsed.raw_json,
            utc_now(),
        ),
    )
    return int(cur.lastrowid)


def route_record(conn, parsed, raw_logger_record_id: int, process_run_id: int, process_file_id: int, source_path: str) -> str:
    if parsed.record_type == "app_usage":
        _insert_app_usage(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path)
        return "app_usage"
    if parsed.record_type == "installed_application":
        _insert_installed_application(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path)
        return "installed_application"
    if parsed.record_type == "location":
        _insert_location(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path)
        return "location"
    if parsed.record_type == "device_state":
        _insert_device_state(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path)
        return "device_state"
    _insert_unknown(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path)
    return "unknown"


def _insert_app_usage(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path) -> None:
    for record in _expand_apps(parsed.record):
        conn.execute(
            """
            INSERT INTO raw_mobile_app_usage(
                raw_logger_record_id, process_run_id, process_file_id, source_path, source_record_index,
                observed_at_utc, device_id, package_name, application_name, activity_name, screen_state,
                event_type, raw_json, imported_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_logger_record_id,
                process_run_id,
                process_file_id,
                source_path,
                parsed.index,
                parsed.observed_at_utc,
                parsed.device_id,
                pick(record, "package_name", "packageName", "package", "app"),
                pick(record, "application_name", "app_name", "appName", "label", "name"),
                pick(record, "activity_name", "activity", "className"),
                pick(record, "screen_state", "screenState"),
                pick(record, "event_type", "eventType", "event", "type"),
                parsed.raw_json,
                utc_now(),
            ),
        )


def _insert_installed_application(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path) -> None:
    conn.execute(
        """
        INSERT INTO raw_installed_application(
            raw_logger_record_id, process_run_id, process_file_id, source_path, source_record_index,
            observed_at_utc, device_id, package_name, application_name, raw_json, imported_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_logger_record_id,
            process_run_id,
            process_file_id,
            source_path,
            parsed.index,
            parsed.observed_at_utc,
            parsed.device_id,
            pick(parsed.record, "package_name", "packageName", "package", "application_identifier"),
            pick(parsed.record, "application_name", "app_name", "appName", "label", "name"),
            parsed.raw_json,
            utc_now(),
        ),
    )


def _insert_location(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path) -> None:
    conn.execute(
        """
        INSERT INTO raw_location_sample(
            raw_logger_record_id, process_run_id, process_file_id, source_path, source_record_index,
            observed_at_utc, device_id, latitude, longitude, accuracy_meters, provider, raw_json, imported_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_logger_record_id,
            process_run_id,
            process_file_id,
            source_path,
            parsed.index,
            parsed.observed_at_utc,
            parsed.device_id,
            _float_value(pick(parsed.record, "latitude", "lat")),
            _float_value(pick(parsed.record, "longitude", "lon", "lng")),
            _float_value(pick(parsed.record, "accuracy", "accuracy_meters", "accuracyMeters")),
            pick(parsed.record, "provider"),
            parsed.raw_json,
            utc_now(),
        ),
    )


def _insert_device_state(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path) -> None:
    conn.execute(
        """
        INSERT INTO raw_device_state(
            raw_logger_record_id, process_run_id, process_file_id, source_path, source_record_index,
            observed_at_utc, device_id, screen_state, battery_percent, network_type, raw_json, imported_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_logger_record_id,
            process_run_id,
            process_file_id,
            source_path,
            parsed.index,
            parsed.observed_at_utc,
            parsed.device_id,
            pick(parsed.record, "screen_state", "screenState", "event", "type"),
            _float_value(pick(parsed.record, "battery_percent", "batteryPercent", "battery")),
            pick(parsed.record, "network_type", "networkType"),
            parsed.raw_json,
            utc_now(),
        ),
    )


def _insert_unknown(conn, parsed, raw_logger_record_id, process_run_id, process_file_id, source_path) -> None:
    conn.execute(
        """
        INSERT INTO raw_unknown_record(
            raw_logger_record_id, process_run_id, process_file_id, source_path, source_record_index,
            observed_at_utc, device_id, record_type_hint, raw_json, imported_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            raw_logger_record_id,
            process_run_id,
            process_file_id,
            source_path,
            parsed.index,
            parsed.observed_at_utc,
            parsed.device_id,
            parsed.record_type,
            parsed.raw_json,
            utc_now(),
        ),
    )


def _expand_apps(record: dict[str, Any]) -> list[dict[str, Any]]:
    apps = record.get("apps")
    if not isinstance(apps, list):
        return [record]
    base = {key: value for key, value in record.items() if key != "apps"}
    rows = []
    for app in apps:
        if isinstance(app, dict):
            merged = dict(base)
            merged.update(app)
            rows.append(merged)
    return rows or [record]


def _float_value(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
