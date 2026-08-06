from __future__ import annotations

from logger.schema import utc_now


def start_run(conn, run_type: str) -> int:
    cur = conn.execute(
        "INSERT INTO processing_run (run_type, started_at_utc, run_status) VALUES (?, ?, 'running')",
        (run_type, utc_now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def complete_run(conn, run_id: int, status: str, **fields) -> None:
    allowed = {
        "files_scanned", "files_imported", "files_skipped", "files_failed",
        "records_imported", "sessions_created", "message", "error_message",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    updates["completed_at_utc"] = utc_now()
    updates["run_status"] = status
    assignments = ", ".join([f"{key} = ?" for key in updates])
    conn.execute(
        f"UPDATE processing_run SET {assignments} WHERE processing_run_id = ?",
        [*updates.values(), run_id],
    )
    conn.commit()


def latest_run(conn, run_type: str | None = None, successful: bool = False):
    where = []
    params = []
    if run_type:
        where.append("run_type = ?")
        params.append(run_type)
    if successful:
        where.append("run_status = 'completed'")
    sql = "SELECT * FROM processing_run"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY started_at_utc DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def is_running(conn) -> bool:
    row = conn.execute("SELECT 1 FROM processing_run WHERE run_status = 'running' LIMIT 1").fetchone()
    return bool(row)

