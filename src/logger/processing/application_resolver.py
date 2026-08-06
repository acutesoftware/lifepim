from __future__ import annotations

import os
from pathlib import Path

from logger.schema import utc_now


def normalize_desktop_identifier(process_name=None, executable_path=None, application_name=None) -> str:
    path = str(executable_path or "").strip()
    if path:
        return os.path.normcase(os.path.normpath(path)).lower()
    process = str(process_name or "").strip()
    if process:
        return process.lower()
    app = str(application_name or "").strip()
    if app:
        return app.lower()
    return "unknown-desktop-application"


def desktop_display_name(process_name=None, executable_path=None, application_name=None) -> str:
    if application_name:
        return str(application_name)
    if process_name:
        return str(process_name)
    if executable_path:
        return Path(str(executable_path)).name
    return "Unknown desktop application"


def mobile_display_name(conn, package_name=None, application_name=None) -> str:
    package = str(package_name or "").strip()
    if package:
        row = conn.execute(
            "SELECT application_name FROM application_catalog WHERE platform = 'android' AND application_identifier = ?",
            (package,),
        ).fetchone()
        if row and row["application_name"]:
            return row["application_name"]
    return str(application_name or package or "Unknown mobile application")


def upsert_mobile_catalog(conn) -> None:
    now = utc_now()
    rows = conn.execute(
        """
        SELECT package_name AS identifier, MAX(application_name) AS app_name,
               MIN(observed_at_utc) AS first_seen, MAX(observed_at_utc) AS last_seen
        FROM mobile_app_usage_sample
        WHERE COALESCE(package_name, '') != ''
        GROUP BY package_name
        """
    ).fetchall()
    conn.executemany(
        """
        INSERT INTO application_catalog
        (platform, application_identifier, application_name, package_name, first_seen_at_utc,
         last_seen_at_utc, source_type, created_at_utc, updated_at_utc)
        VALUES ('android', ?, ?, ?, ?, ?, 'mobile_app_usage', ?, ?)
        ON CONFLICT(platform, application_identifier) DO UPDATE SET
            application_name = COALESCE(application_catalog.application_name, excluded.application_name),
            package_name = excluded.package_name,
            last_seen_at_utc = excluded.last_seen_at_utc,
            updated_at_utc = excluded.updated_at_utc
        """,
        [
            (
                row["identifier"],
                row["app_name"],
                row["identifier"],
                row["first_seen"],
                row["last_seen"],
                now,
                now,
            )
            for row in rows
        ],
    )


def upsert_desktop_catalog(conn) -> None:
    now = utc_now()
    rows = conn.execute(
        """
        SELECT process_name, executable_path, MAX(application_name) AS app_name,
               MIN(observed_at_utc) AS first_seen, MAX(observed_at_utc) AS last_seen
        FROM desktop_window_sample
        WHERE COALESCE(process_name, '') != '' OR COALESCE(executable_path, '') != '' OR COALESCE(application_name, '') != ''
        GROUP BY COALESCE(NULLIF(executable_path, ''), lower(process_name), lower(application_name))
        """
    ).fetchall()
    values = []
    for row in rows:
        identifier = normalize_desktop_identifier(row["process_name"], row["executable_path"], row["app_name"])
        values.append(
            (
                identifier,
                desktop_display_name(row["process_name"], row["executable_path"], row["app_name"]),
                row["process_name"],
                row["executable_path"],
                row["first_seen"],
                row["last_seen"],
                now,
                now,
            )
        )
    conn.executemany(
        """
        INSERT INTO application_catalog
        (platform, application_identifier, application_name, process_name, executable_path,
         first_seen_at_utc, last_seen_at_utc, source_type, created_at_utc, updated_at_utc)
        VALUES ('windows', ?, ?, ?, ?, ?, ?, 'aggie_window_usage', ?, ?)
        ON CONFLICT(platform, application_identifier) DO UPDATE SET
            application_name = COALESCE(application_catalog.application_name, excluded.application_name),
            process_name = COALESCE(excluded.process_name, application_catalog.process_name),
            executable_path = COALESCE(excluded.executable_path, application_catalog.executable_path),
            last_seen_at_utc = excluded.last_seen_at_utc,
            updated_at_utc = excluded.updated_at_utc
        """,
        values,
    )


def rebuild_application_catalog(conn) -> None:
    upsert_mobile_catalog(conn)
    upsert_desktop_catalog(conn)

