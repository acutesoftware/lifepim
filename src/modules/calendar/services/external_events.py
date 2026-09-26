from __future__ import annotations

from datetime import date, datetime, time, timedelta
import hashlib
import re

from dateutil.rrule import rrulestr

from common import data as db
from modules.calendar.services import calendar_index


def parse_ics_file(path: str, start_year: int | None = None, end_year: int | None = None) -> tuple[str, list[dict]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
        return parse_ics(handle.read(), start_year, end_year)


def parse_ics(text: str, start_year: int | None = None, end_year: int | None = None) -> tuple[str, list[dict]]:
    lines = _unfold(text)
    calendar_name = ""
    events = []
    current = None
    for line in lines:
        if line.upper() == "BEGIN:VEVENT":
            current = {}
            continue
        if line.upper() == "END:VEVENT":
            if current is not None:
                event = _normalise_event(current, len(events) + 1)
                events.extend(_expand_event(event, current, start_year, end_year))
            current = None
            continue
        if ":" not in line:
            continue
        raw_key, value = line.split(":", 1)
        key = raw_key.split(";", 1)[0].upper()
        if current is None:
            if key == "X-WR-CALNAME":
                calendar_name = _unescape(value)
            continue
        current.setdefault(key, []).append((raw_key, value))
    return calendar_name, events


def replace_external_events(
    events: list[dict],
    source_name: str,
    conn=None,
) -> dict:
    conn = db._get_conn() if conn is None else conn
    calendar_index.ensure_calendar_schema(conn)
    source_name = (source_name or "External calendar").strip() or "External calendar"
    import_key = hashlib.sha256(source_name.casefold().encode("utf-8")).hexdigest()[:20]
    source_key = "external_events"
    source_id = calendar_index._source_id(conn, source_key)
    deleted = inserted = 0
    conn.execute("SAVEPOINT external_event_import")
    try:
        deleted = calendar_index.delete_imported_calendar_items(
            source_key, source_sub_id=import_key, conn=conn
        )
        for index, raw_event in enumerate(events, 1):
            event = dict(raw_event)
            event["source_sub_id"] = import_key
            uid = event.get("uid") or f"row-{index}"
            occurrence_key = f"external:{import_key}:{uid}:{event['start_date']}:{event.get('start_time') or ''}"
            event["id"] = uid
            calendar_index._upsert_item(conn, source_id, source_key, event, occurrence_key, "external", None)
            inserted += 1
        message = f"Imported {inserted} events from {source_name}."
        calendar_index._touch_source(conn, source_key, "current", inserted, message)
        conn.execute("RELEASE SAVEPOINT external_event_import")
        conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT external_event_import")
        conn.execute("RELEASE SAVEPOINT external_event_import")
        raise
    return {"inserted": inserted, "deleted": deleted, "source_name": source_name, "import_key": import_key}


def _unfold(text: str) -> list[str]:
    unfolded = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)
    return unfolded


def _normalise_event(values: dict, index: int) -> dict:
    start_raw_key, start_raw = _first(values, "DTSTART")
    if not start_raw:
        raise ValueError(f"Event {index} has no DTSTART value.")
    start_date, start_time, all_day = _parse_ics_datetime(start_raw_key, start_raw)
    end_raw_key, end_raw = _first(values, "DTEND")
    if end_raw:
        end_date, end_time, end_all_day = _parse_ics_datetime(end_raw_key, end_raw)
        if all_day and end_all_day:
            end_date = (datetime.strptime(end_date, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
            if end_date < start_date:
                end_date = start_date
    else:
        end_date, end_time = start_date, start_time
    _, uid = _first(values, "UID")
    _, summary = _first(values, "SUMMARY")
    _, description = _first(values, "DESCRIPTION")
    _, location = _first(values, "LOCATION")
    _, status = _first(values, "STATUS")
    return {
        "uid": _unescape(uid) or f"event-{index}",
        "title": _unescape(summary) or "Untitled event",
        "content": _unescape(description),
        "start_date": start_date,
        "start_time": start_time,
        "end_date": end_date,
        "end_time": end_time,
        "all_day": int(all_day),
        "blocks_time": 0,
        "event_type": "external",
        "category": "External",
        "area": "General",
        "status": "cancelled" if status.upper() == "CANCELLED" else "active",
        "location": _unescape(location),
        "source": "external_events",
    }


def _expand_event(event: dict, values: dict, start_year: int | None, end_year: int | None) -> list[dict]:
    _, rule = _first(values, "RRULE")
    if not rule:
        return [event]
    today_year = date.today().year
    start_year = int(start_year if start_year is not None else today_year - 1)
    end_year = int(end_year if end_year is not None else today_year + 5)
    if not (1 <= start_year <= end_year <= 9999):
        raise ValueError("Enter a valid recurrence year range.")
    start_dt = _event_datetime(event["start_date"], event.get("start_time"))
    end_dt = _event_datetime(event["end_date"], event.get("end_time"), end_of_day=bool(event["all_day"]))
    duration = max(end_dt - start_dt, timedelta(0))
    window_start = datetime(start_year, 1, 1)
    window_end = datetime(end_year, 12, 31, 23, 59, 59)
    try:
        occurrences = rrulestr(rule, dtstart=start_dt, ignoretz=True).between(window_start, window_end, inc=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported iCalendar recurrence rule: {rule}") from exc
    excluded = _excluded_datetimes(values)
    expanded = []
    for occurrence in occurrences:
        occurrence = occurrence.replace(tzinfo=None)
        if occurrence in excluded:
            continue
        item = dict(event)
        item["start_date"] = occurrence.date().isoformat()
        item["start_time"] = "" if event["all_day"] else occurrence.strftime("%H:%M")
        occurrence_end = occurrence + duration
        item["end_date"] = occurrence_end.date().isoformat()
        item["end_time"] = "" if event["all_day"] else occurrence_end.strftime("%H:%M")
        expanded.append(item)
    return expanded


def _event_datetime(date_value: str, time_value: str | None, end_of_day=False) -> datetime:
    parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    if time_value:
        parsed_time = datetime.strptime(time_value, "%H:%M").time()
    else:
        parsed_time = time.max if end_of_day else time.min
    return datetime.combine(parsed_date, parsed_time)


def _excluded_datetimes(values: dict) -> set[datetime]:
    excluded = set()
    for raw_key, raw_values in values.get("EXDATE") or []:
        for raw_value in raw_values.split(","):
            date_value, time_value, all_day = _parse_ics_datetime(raw_key, raw_value)
            excluded.add(_event_datetime(date_value, "" if all_day else time_value))
    return excluded


def _first(values, key):
    entries = values.get(key) or []
    return entries[0] if entries else ("", "")


def _parse_ics_datetime(raw_key: str, raw_value: str):
    value = raw_value.strip()
    is_date = "VALUE=DATE" in raw_key.upper() or bool(re.fullmatch(r"\d{8}", value))
    if is_date:
        parsed = datetime.strptime(value[:8], "%Y%m%d")
        return parsed.date().isoformat(), "", True
    cleaned = value.rstrip("Z")
    parsed = None
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            break
        except ValueError:
            pass
    if parsed is None:
        raise ValueError(f"Unsupported iCalendar date/time: {raw_value}")
    return parsed.date().isoformat(), parsed.strftime("%H:%M"), False


def _unescape(value: str) -> str:
    return (
        (value or "")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )
