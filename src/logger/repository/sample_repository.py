from __future__ import annotations


def sample_counts(conn) -> dict:
    def count(table):
        try:
            return int(conn.execute(f"SELECT COUNT(1) AS cnt FROM {table}").fetchone()["cnt"] or 0)
        except Exception:
            return 0

    return {
        "source_files": count("ingest_file"),
        "failed_source_files": int(conn.execute("SELECT COUNT(1) AS cnt FROM ingest_file WHERE import_status = 'failed'").fetchone()["cnt"] or 0),
        "mobile_usage_samples": count("mobile_app_usage_sample"),
        "desktop_samples": count("desktop_window_sample"),
        "activity_sessions": count("activity_session"),
    }
