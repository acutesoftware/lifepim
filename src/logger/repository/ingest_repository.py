from __future__ import annotations

from pathlib import Path

from logger.schema import utc_now


def get_by_path(conn, source_path: str | Path):
    row = conn.execute("SELECT * FROM ingest_file WHERE source_path = ?", (str(source_path),)).fetchone()
    return dict(row) if row else None


def get_imported_by_hash(conn, file_hash: str):
    row = conn.execute(
        "SELECT * FROM ingest_file WHERE file_hash = ? AND import_status = 'imported' ORDER BY ingest_file_id LIMIT 1",
        (file_hash,),
    ).fetchone()
    return dict(row) if row else None


def delete_by_path(conn, source_path: str | Path) -> None:
    conn.execute("DELETE FROM ingest_file WHERE source_path = ?", (str(source_path),))


def create_importing(conn, source_file, file_hash: str) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT INTO ingest_file
        (source_type, device_id, source_path, file_name, file_hash, file_size_bytes,
         source_modified_at_utc, import_status, created_at_utc, updated_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'importing', ?, ?)
        """,
        (
            source_file.source_type,
            source_file.device_id,
            str(source_file.source_path),
            source_file.source_path.name,
            file_hash,
            source_file.file_size_bytes,
            _dt_s(source_file.modified_at_utc),
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def create_superseded_duplicate(conn, source_file, file_hash: str, original_path: str) -> int:
    now = utc_now()
    cur = conn.execute(
        """
        INSERT OR REPLACE INTO ingest_file
        (source_type, device_id, source_path, file_name, file_hash, file_size_bytes,
         source_modified_at_utc, import_status, record_count, error_message, created_at_utc, updated_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'superseded', 0, ?, ?, ?)
        """,
        (
            source_file.source_type,
            source_file.device_id,
            str(source_file.source_path),
            source_file.source_path.name,
            file_hash,
            source_file.file_size_bytes,
            _dt_s(source_file.modified_at_utc),
            f"Duplicate content already imported from {original_path}",
            now,
            now,
        ),
    )
    return int(cur.lastrowid)


def mark_imported(conn, ingest_file_id: int, result) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE ingest_file
           SET import_status = 'imported',
               imported_at_utc = ?,
               first_record_at_utc = ?,
               last_record_at_utc = ?,
               record_count = ?,
               error_message = '',
               updated_at_utc = ?
         WHERE ingest_file_id = ?
        """,
        (
            now,
            _dt_s(result.first_record_at_utc),
            _dt_s(result.last_record_at_utc),
            int(result.record_count or 0),
            now,
            ingest_file_id,
        ),
    )


def mark_failed(conn, ingest_file_id: int, error_message: str) -> None:
    now = utc_now()
    conn.execute(
        "UPDATE ingest_file SET import_status = 'failed', error_message = ?, updated_at_utc = ? WHERE ingest_file_id = ?",
        (error_message, now, ingest_file_id),
    )


def _dt_s(value):
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

