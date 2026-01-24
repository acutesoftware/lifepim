"""Media import writer."""

from __future__ import annotations

from typing import Dict, List


TABLE_NAME = "lp_media"


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
        sha256 = _norm_hash(row.get("sha256"))
        entity_id = _media_entity_id(sha256)
        if not entity_id:
            ctx.add_error("missing sha256 for media")
            continue
        entity_ids.append(entity_id)
        values.append(
            (
                entity_id,
                sha256,
                row.get("labels_json"),
                row.get("faces"),
                row.get("dominant_colors"),
                ctx.source_system,
                row.get("source_uid"),
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
        "INSERT INTO lp_media "
        "(entity_id, sha256, labels_json, faces, dominant_colors, source_system, source_uid, imported_run_id, imported_utc, is_deleted, deleted_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(entity_id) DO UPDATE SET "
        "sha256=excluded.sha256, "
        "labels_json=excluded.labels_json, "
        "faces=excluded.faces, "
        "dominant_colors=excluded.dominant_colors, "
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


def _media_entity_id(sha256: str) -> str:
    sha256 = _norm_hash(sha256)
    if not sha256:
        return ""
    return f"media:sha256:{sha256}"


def _norm_hash(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()
