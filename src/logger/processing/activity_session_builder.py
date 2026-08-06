from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from logger.schema import utc_now
from .application_resolver import (
    desktop_display_name,
    mobile_display_name,
    normalize_desktop_identifier,
)


@dataclass
class _OpenSession:
    platform: str
    device_id: str
    source_type: str
    application_identifier: str
    application_name: str
    activity_title: str
    start_at: datetime
    last_at: datetime
    first_id: int
    last_id: int
    count: int = 1


def rebuild_activity_sessions(conn, gap_seconds=60, minimum_seconds=3) -> int:
    gap_seconds = max(1, int(gap_seconds or 60))
    minimum_seconds = max(0, int(minimum_seconds or 0))
    rows = []
    rows.extend(_build_mobile_sessions(conn, gap_seconds, minimum_seconds))
    rows.extend(_build_desktop_sessions(conn, gap_seconds, minimum_seconds))
    now = utc_now()
    with conn:
        conn.execute("DELETE FROM activity_session")
        conn.executemany(
            """
            INSERT INTO activity_session
            (platform, device_id, source_type, application_identifier, application_name, activity_title,
             start_at_utc, end_at_utc, duration_seconds, source_record_count, confidence_score,
             first_source_record_id, last_source_record_id, session_hash, generated_at_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [row + (now,) for row in rows],
        )
    return len(rows)


def _build_mobile_sessions(conn, gap_seconds, minimum_seconds):
    sample_rows = conn.execute(
        """
        SELECT * FROM mobile_app_usage_sample
        ORDER BY device_id, observed_at_utc, mobile_app_usage_sample_id
        """
    ).fetchall()
    out = []
    current = None
    for row in sample_rows:
        observed = _parse(row["observed_at_utc"])
        screen_state = (row["screen_state"] or "").lower()
        event_type = (row["event_type"] or "").lower()
        terminates = screen_state in {"off", "screen_off", "locked"} or event_type in {"screen_off", "stop", "inactive"}
        package = row["package_name"] or "unknown-mobile-application"
        app_name = mobile_display_name(conn, package, row["application_name"])
        if terminates:
            if current:
                _finish(out, current, gap_seconds, minimum_seconds)
                current = None
            continue
        if not current or current.device_id != row["device_id"] or current.application_identifier != package or _gap(current.last_at, observed) > gap_seconds:
            if current:
                _finish(out, current, gap_seconds, minimum_seconds)
            current = _OpenSession(
                "android",
                row["device_id"],
                "mobile_app",
                package,
                app_name,
                app_name,
                observed,
                observed,
                row["mobile_app_usage_sample_id"],
                row["mobile_app_usage_sample_id"],
            )
        else:
            current.last_at = observed
            current.last_id = row["mobile_app_usage_sample_id"]
            current.count += 1
            current.application_name = app_name or current.application_name
            current.activity_title = app_name or current.activity_title
    if current:
        _finish(out, current, gap_seconds, minimum_seconds)
    return out


def _build_desktop_sessions(conn, gap_seconds, minimum_seconds):
    sample_rows = conn.execute(
        """
        SELECT * FROM desktop_window_sample
        ORDER BY device_id, observed_at_utc, desktop_window_sample_id
        """
    ).fetchall()
    out = []
    current = None
    for row in sample_rows:
        observed = _parse(row["observed_at_utc"])
        if row["is_idle"]:
            if current:
                _finish(out, current, gap_seconds, minimum_seconds)
                current = None
            continue
        identifier = normalize_desktop_identifier(row["process_name"], row["executable_path"], row["application_name"])
        app_name = desktop_display_name(row["process_name"], row["executable_path"], row["application_name"])
        title = row["window_title"] or app_name
        if not current or current.device_id != row["device_id"] or current.application_identifier != identifier or _gap(current.last_at, observed) > gap_seconds:
            if current:
                _finish(out, current, gap_seconds, minimum_seconds)
            current = _OpenSession(
                "windows",
                row["device_id"],
                "desktop_window",
                identifier,
                app_name,
                title,
                observed,
                observed,
                row["desktop_window_sample_id"],
                row["desktop_window_sample_id"],
            )
        else:
            current.last_at = observed
            current.last_id = row["desktop_window_sample_id"]
            current.count += 1
            if title:
                current.activity_title = title
    if current:
        _finish(out, current, gap_seconds, minimum_seconds)
    return out


def _finish(out, session: _OpenSession, gap_seconds: int, minimum_seconds: int) -> None:
    # Treat the final sample as covering one more observed interval, capped by
    # the session gap. For 1-second samples this produces the expected interval.
    interval = 1
    end_at = session.last_at + timedelta(seconds=min(interval, gap_seconds))
    duration = max(0, int((end_at - session.start_at).total_seconds()))
    if duration < minimum_seconds:
        return
    start_s = _format(session.start_at)
    end_s = _format(end_at)
    digest = hashlib.sha256(
        "|".join(
            [
                session.platform,
                session.device_id,
                session.source_type,
                session.application_identifier,
                start_s,
                end_s,
            ]
        ).encode("utf-8")
    ).hexdigest()
    out.append(
        (
            session.platform,
            session.device_id,
            session.source_type,
            session.application_identifier,
            session.application_name,
            session.activity_title,
            start_s,
            end_s,
            duration,
            session.count,
            0.9,
            session.first_id,
            session.last_id,
            digest,
        )
    )


def _parse(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _gap(left: datetime, right: datetime) -> int:
    return int((right - left).total_seconds())
