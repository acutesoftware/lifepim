from __future__ import annotations

from dataclasses import asdict, is_dataclass

from common import localtime


def logger_status_view(status):
    data = asdict(status) if is_dataclass(status) else dict(status or {})
    for key in ("last_refresh", "last_rebuild_sessions", "last_rebuild_database"):
        data[key] = _run_view(data.get(key))
    data["first_activity_at"] = localtime.display_log_time(data.get("first_activity_at_utc"))
    data["last_activity_at"] = localtime.display_log_time(data.get("last_activity_at_utc"))
    return data


def processing_runs_view(rows):
    return [_run_view(row) for row in rows]


def activity_sessions_view(rows):
    out = []
    for row in rows or []:
        item = dict(row)
        item["start_at"] = localtime.display_log_time(item.get("start_at_utc"))
        item["end_at"] = localtime.display_log_time(item.get("end_at_utc"))
        out.append(item)
    return out


def failed_files_view(rows):
    out = []
    for row in rows or []:
        item = dict(row)
        item["updated_at"] = localtime.display_log_time(item.get("updated_at_utc"))
        out.append(item)
    return out


def _run_view(row):
    if not row:
        return None
    item = dict(row)
    item["started_at"] = localtime.display_log_time(item.get("started_at_utc"))
    item["completed_at"] = localtime.display_log_time(item.get("completed_at_utc"))
    return item
