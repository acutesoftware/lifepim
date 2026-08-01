from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_LOG_TIMEZONE = "Australia/Adelaide"


def log_timezone_name():
    return os.getenv("LIFEPIM_LOG_TIMEZONE") or DEFAULT_LOG_TIMEZONE


def log_timezone():
    try:
        return ZoneInfo(log_timezone_name())
    except ZoneInfoNotFoundError:
        if log_timezone_name() == DEFAULT_LOG_TIMEZONE:
            return timezone(timedelta(hours=9, minutes=30), "ACST")
        return timezone.utc


def now_log_iso():
    return datetime.now(log_timezone()).isoformat(timespec="seconds")


def display_log_time(value):
    raw = "" if value is None else str(value).strip()
    if not raw:
        return ""
    parsed = _parse_log_time(raw)
    if parsed is None:
        return raw
    return parsed.astimezone(log_timezone()).strftime("%Y-%m-%d %H:%M:%S %Z")


def _parse_log_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")
    if " " in text and "T" not in text:
        candidates.append(text.replace(" ", "T", 1))
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return None
