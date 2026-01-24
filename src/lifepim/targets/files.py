"""Files import writer."""

from __future__ import annotations

from typing import Dict, List


TABLE_NAME = "lp_files"


def begin(ctx):
    if ctx.is_snapshot:
        ctx.snapshot_purge(TABLE_NAME, source_system=ctx.source_system)


def finish(ctx):
    if ctx.needs_tombstone:
        return ctx.tombstone_missing(TABLE_NAME)
    return 0


def upsert_many(rows: List[Dict[str, object]], ctx):
    if not rows:
        return {"upserted": 0}

    entity_ids: List[str] = []
    values = []
    for row in rows:
        source_uid = row.get("source_uid")
        sha256 = _norm_hash(row.get("sha256"))
        entity_id = _file_entity_id(ctx.source_system, source_uid, sha256)
        if not entity_id:
            ctx.add_error("missing sha256/source_uid for file")
            continue
        entity_ids.append(entity_id)
        values.append(
            (
                entity_id,
                row.get("path"),
                row.get("size"),
                row.get("mtime_utc"),
                sha256,
                row.get("file_type"),
                ctx.source_system,
                source_uid,
                ctx.run_id,
                ctx.imported_utc,
                0,
                None,
            )
        )

    if ctx.dry_run:
        ctx.record_entity_ids(entity_ids)
        return {"upserted": len(values)}

    sql = (
        "INSERT INTO lp_files "
        "(entity_id, path, size, mtime_utc, sha256, file_type, source_system, source_uid, imported_run_id, imported_utc, is_deleted, deleted_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(entity_id) DO UPDATE SET "
        "path=excluded.path, "
        "size=excluded.size, "
        "mtime_utc=excluded.mtime_utc, "
        "sha256=excluded.sha256, "
        "file_type=excluded.file_type, "
        "source_system=excluded.source_system, "
        "source_uid=excluded.source_uid, "
        "imported_run_id=excluded.imported_run_id, "
        "imported_utc=excluded.imported_utc, "
        "is_deleted=0, "
        "deleted_utc=NULL"
    )
    ctx.conn.executemany(sql, values)
    ctx.conn.commit()
    ctx.record_entity_ids(entity_ids)
    return {"upserted": len(values)}


def _file_entity_id(source_system: str, source_uid, sha256: str) -> str:
    if sha256:
        return f"file:sha256:{sha256}"
    source_uid = str(source_uid or "").strip()
    if not source_uid:
        return ""
    source_system = (source_system or "").strip()
    return f"file:src:{source_system}:{source_uid}"


def _norm_hash(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()
