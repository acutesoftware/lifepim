"""Importer run context and orchestration."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lifepim.importer import mapping as mapping_mod
from lifepim.importer.registry import get_writer
from lifepim.importer.schema import ensure_import_schema


MODES = {"snapshot", "authoritative", "merge"}


def run_import(run_name: str, *, db_path: Optional[str] = None, progress_every: int = 1000):
    return ImportRun(run_name, db_path=db_path, progress_every=progress_every)


class ImportRun:
    def __init__(self, run_name: str, *, db_path: Optional[str], progress_every: int = 1000):
        self.run_name = run_name
        self.db_path = db_path or _default_db_path()
        self.progress_every = progress_every
        self.conn: Optional[sqlite3.Connection] = None
        self.run_id: Optional[int] = None
        self.stats: Dict[str, Any] = {
            "read": 0,
            "mapped": 0,
            "upserted": 0,
            "deleted": 0,
            "errors": 0,
            "targets": {},
        }
        self.error_samples: List[str] = []
        self._status = "running"

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        ensure_import_schema(self.conn)
        self.run_id = self._create_run_row()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self._status = "failed"
            self._set_error_text(str(exc))
        else:
            self._status = "success"
        self._finalize_run()
        if self.conn:
            self.conn.close()
        return False

    def load(
        self,
        *,
        target: str,
        source,
        mapping: Dict[str, Any],
        key,
        mode: str,
        tombstone: bool = False,
        source_system: Optional[str] = None,
        batch_size: int = 1000,
        dry_run: bool = False,
    ):
        if not self.conn or not self.run_id:
            raise RuntimeError("ImportRun must be used as a context manager.")
        mode = (mode or "").lower()
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}")
        writer = get_writer(target)
        key_fields = _normalize_key_fields(key)
        for key_field in key_fields:
            if key_field not in mapping:
                raise ValueError(f"Key field '{key_field}' must exist in mapping.")

        source_system = (source_system or source.source_system or target).strip()
        ctx = ImportContext(
            conn=self.conn,
            run_id=self.run_id,
            target=target,
            mode=mode,
            tombstone=tombstone,
            source_system=source_system,
            key_fields=key_fields,
            mapping_fields=list(mapping.keys()),
            dry_run=dry_run,
            progress_every=self.progress_every,
        )

        missing_cols = _missing_source_columns(source, mapping)
        if missing_cols:
            ctx.add_error(f"Missing source columns: {', '.join(sorted(missing_cols))}")

        if hasattr(writer, "begin"):
            writer.begin(ctx)

        batch: List[Dict[str, Any]] = []
        for row in source.iter_rows():
            ctx.stats["read"] += 1
            mapped, errors = mapping_mod.apply_mapping(row, mapping)
            if errors:
                for err in errors:
                    ctx.add_error(f"map:{err}")
                continue
            if not _row_has_keys(mapped, key_fields):
                ctx.add_error("missing key value")
                continue
            ctx.stats["mapped"] += 1
            batch.append(mapped)
            if len(batch) >= batch_size:
                _flush_batch(writer, batch, ctx)
                batch = []
            if self.progress_every and ctx.stats["read"] % self.progress_every == 0:
                print(f"[import] {target}: read {ctx.stats['read']} mapped {ctx.stats['mapped']}")

        if batch:
            _flush_batch(writer, batch, ctx)

        if hasattr(writer, "finish"):
            deleted = writer.finish(ctx) or 0
            ctx.stats["deleted"] += int(deleted)

        self._merge_stats(target, ctx)
        self._update_run_row()
        return dict(ctx.stats)

    def reset_domain(self, target: str, source_system: Optional[str] = None, dry_run: bool = False):
        if not self.conn or not self.run_id:
            raise RuntimeError("ImportRun must be used as a context manager.")
        writer = get_writer(target)
        source_system = source_system.strip() if source_system else None
        ctx = ImportContext(
            conn=self.conn,
            run_id=self.run_id,
            target=target,
            mode="snapshot",
            tombstone=False,
            source_system=source_system or target,
            key_fields=(),
            mapping_fields=[],
            dry_run=dry_run,
            progress_every=self.progress_every,
        )
        if hasattr(writer, "reset"):
            writer.reset(ctx)
        elif hasattr(writer, "TABLE_NAME"):
            if not dry_run:
                ctx.snapshot_purge(writer.TABLE_NAME, source_system=source_system)

    def _create_run_row(self) -> int:
        started = _utc_now()
        cur = self.conn.execute(
            "INSERT INTO lp_import_runs (run_name, started_utc, status, stats_json) VALUES (?, ?, ?, ?)",
            (self.run_name, started, "running", json.dumps(self.stats)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def _update_run_row(self):
        stats_json = json.dumps(self.stats)
        self.conn.execute(
            "UPDATE lp_import_runs SET stats_json = ? WHERE run_id = ?",
            (stats_json, self.run_id),
        )
        self.conn.commit()

    def _set_error_text(self, message: str):
        if not self.conn:
            return
        self.conn.execute(
            "UPDATE lp_import_runs SET error_text = ? WHERE run_id = ?",
            (message, self.run_id),
        )
        self.conn.commit()

    def _finalize_run(self):
        if not self.conn:
            return
        ended = _utc_now()
        self.conn.execute(
            "UPDATE lp_import_runs SET ended_utc = ?, status = ?, stats_json = ? WHERE run_id = ?",
            (ended, self._status, json.dumps(self.stats), self.run_id),
        )
        self.conn.commit()

    def _merge_stats(self, target: str, ctx):
        for key in ("read", "mapped", "upserted", "deleted", "errors"):
            self.stats[key] += int(ctx.stats.get(key, 0))
        if ctx.error_samples:
            self.error_samples.extend(ctx.error_samples)
            self.stats["errors"] = int(self.stats.get("errors", 0))
        self.stats["targets"][target] = dict(ctx.stats)


def _normalize_key_fields(key) -> Tuple[str, ...]:
    if isinstance(key, (tuple, list)):
        return tuple(key)
    return (key,)


def _row_has_keys(mapped: Dict[str, Any], key_fields: Iterable[str]) -> bool:
    for field in key_fields:
        value = mapped.get(field)
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
    return True


def _missing_source_columns(source, mapping: Dict[str, Any]):
    source_cols = {col for col in (source.get_columns() or [])}
    missing = set()
    for col in mapping_mod.extract_source_columns(mapping):
        if col not in source_cols:
            missing.add(col)
    return missing


def _flush_batch(writer, batch: List[Dict[str, Any]], ctx):
    if not batch:
        return
    result = writer.upsert_many(batch, ctx) or {}
    ctx.stats["upserted"] += int(result.get("upserted", 0))
    ctx.stats["deleted"] += int(result.get("deleted", 0))


class ImportContext:
    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        run_id: int,
        target: str,
        mode: str,
        tombstone: bool,
        source_system: str,
        key_fields: Tuple[str, ...],
        mapping_fields: List[str],
        dry_run: bool,
        progress_every: int,
    ):
        self.conn = conn
        self.run_id = run_id
        self.target = target
        self.mode = mode
        self.tombstone = tombstone
        self.source_system = source_system
        self.key_fields = key_fields
        self.mapping_fields = mapping_fields
        self.dry_run = dry_run
        self.progress_every = progress_every
        self.stats = {"read": 0, "mapped": 0, "upserted": 0, "deleted": 0, "errors": 0}
        self.error_samples: List[str] = []
        self.imported_utc = _utc_now()
        self._temp_table = None

    def add_error(self, message: str):
        self.stats["errors"] += 1
        if len(self.error_samples) < 20:
            self.error_samples.append(message)

    @property
    def needs_tombstone(self) -> bool:
        return self.mode == "authoritative" and self.tombstone

    @property
    def is_snapshot(self) -> bool:
        return self.mode == "snapshot"

    def snapshot_purge(self, table_name: str, source_system: Optional[str] = None):
        if self.dry_run:
            return 0
        if source_system is None:
            self.conn.execute(
                f"UPDATE {table_name} SET is_deleted = 1, deleted_utc = ?",
                (self.imported_utc,),
            )
        else:
            self.conn.execute(
                f"UPDATE {table_name} SET is_deleted = 1, deleted_utc = ? WHERE source_system = ?",
                (self.imported_utc, source_system),
            )
        self.conn.commit()
        return self.conn.total_changes

    def record_entity_ids(self, entity_ids: Iterable[str]):
        if not self.needs_tombstone:
            return
        if not self._temp_table:
            safe_target = "".join(ch for ch in self.target if ch.isalnum() or ch == "_")
            self._temp_table = f"tmp_import_keys_{safe_target}_{self.run_id}"
            self.conn.execute(f"DROP TABLE IF EXISTS {self._temp_table}")
            self.conn.execute(f"CREATE TEMP TABLE {self._temp_table} (entity_id TEXT PRIMARY KEY)")
        rows = [(entity_id,) for entity_id in entity_ids if entity_id]
        if not rows:
            return
        self.conn.executemany(
            f"INSERT OR IGNORE INTO {self._temp_table} (entity_id) VALUES (?)",
            rows,
        )
        if not self.dry_run:
            self.conn.commit()

    def tombstone_missing(self, table_name: str) -> int:
        if not self.needs_tombstone:
            return 0
        if not self._temp_table:
            return 0
        if self.dry_run:
            return 0
        cur = self.conn.execute(
            f"UPDATE {table_name} "
            "SET is_deleted = 1, deleted_utc = ? "
            f"WHERE source_system = ? AND entity_id NOT IN (SELECT entity_id FROM {self._temp_table})",
            (self.imported_utc, self.source_system),
        )
        self.conn.commit()
        return cur.rowcount


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_db_path() -> str:
    try:
        from common import config as cfg

        return getattr(cfg, "DB_FILE", getattr(cfg, "db_name", "lifepim.db"))
    except Exception:
        return os.path.abspath("lifepim.db")
