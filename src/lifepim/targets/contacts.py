"""Contacts import writer."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List


TABLE_NAME = "lp_contacts"


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
        display_name = row.get("display_name") or ""
        normalized_name = _normalize_name(display_name)
        entity_id = _contact_entity_id(ctx.source_system, source_uid)
        if not entity_id:
            ctx.add_error("missing source_uid for contact")
            continue
        entity_ids.append(entity_id)
        values.append(
            (
                entity_id,
                display_name,
                normalized_name,
                row.get("email"),
                row.get("phone"),
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
        "INSERT INTO lp_contacts "
        "(entity_id, display_name, normalized_name, email, phone, source_system, source_uid, imported_run_id, imported_utc, is_deleted, deleted_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(entity_id) DO UPDATE SET "
        "display_name=excluded.display_name, "
        "normalized_name=excluded.normalized_name, "
        "email=excluded.email, "
        "phone=excluded.phone, "
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


def _contact_entity_id(source_system: str, source_uid) -> str:
    source_uid = str(source_uid or "").strip()
    if not source_uid:
        return ""
    source_system = (source_system or "").strip()
    return f"contact:src:{source_system}:{source_uid}"


def _normalize_name(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())
