#!/usr/bin/python3
# coding: utf-8
# import_tools.py - helper functions for bulk imports

import csv
import os
import sqlite3
from datetime import datetime, timezone

from common import config as cfg

try:
    from lifepim.importer import run_import, csv_source, sqlite_source
    from lifepim.importer import mapping as mapping_mod
except Exception:  # pragma: no cover - allows use without importer package
    run_import = None
    csv_source = None
    sqlite_source = None
    mapping_mod = None


def parse_dt_utc(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            continue
    return text


TRANSFORMS = {
    "parse_dt_utc": parse_dt_utc,
    "strip": lambda v: v.strip() if isinstance(v, str) else v,
    "lower": lambda v: v.lower() if isinstance(v, str) else v,
    "upper": lambda v: v.upper() if isinstance(v, str) else v,
    "to_int": lambda v: int(v) if v not in (None, "") else None,
    "to_float": lambda v: float(v) if v not in (None, "") else None,
}


def load_csv(
    *,
    tbl,
    fname,
    map=None,
    db_path=None,
    run_name=None,
    key=None,
    mode="snapshot",
    tombstone=False,
    source_system=None,
    batch_size=1000,
    dry_run=False,
    progress_every=1000,
    encoding="utf-8",
    delimiter=",",
    use_importer=None,
):
    """Load CSV rows into a target table/domain."""
    mapping = _normalize_mapping(map or {})
    target = _target_from_tbl(tbl)
    if _use_importer(target, use_importer):
        if not run_import:
            raise RuntimeError("Importer package is not available")
        if not mapping:
            raise ValueError("mapping is required for importer targets")
        key_field = key or _infer_key(mapping)
        source = csv_source(fname, encoding=encoding, delimiter=delimiter)
        run_name = run_name or f"import_{target}"
        with run_import(run_name, db_path=_resolve_db_path(db_path), progress_every=progress_every) as run:
            return run.load(
                target=target,
                source=source,
                mapping=mapping,
                key=key_field,
                mode=mode,
                tombstone=tombstone,
                source_system=source_system,
                batch_size=batch_size,
                dry_run=dry_run,
            )
    return _load_csv_direct(
        tbl=tbl,
        fname=fname,
        mapping=mapping,
        db_path=_resolve_db_path(db_path),
        batch_size=batch_size,
        dry_run=dry_run,
        encoding=encoding,
        delimiter=delimiter,
    )


def load_sqlite(
    *,
    tbl,
    src_db,
    sql,
    map=None,
    db_path=None,
    run_name=None,
    key=None,
    mode="snapshot",
    tombstone=False,
    source_system=None,
    batch_size=1000,
    dry_run=False,
    progress_every=1000,
    params=None,
    use_importer=None,
):
    """Load SQLite query results into a target table/domain using importer mode."""
    mapping = _normalize_mapping(map or {})
    target = _target_from_tbl(tbl)
    if not _use_importer(target, use_importer):
        raise ValueError("load_sqlite uses the importer; use load_tbl for raw table copies")
    if not run_import:
        raise RuntimeError("Importer package is not available")
    if not mapping:
        raise ValueError("mapping is required for importer targets")
    key_field = key or _infer_key(mapping)
    source = sqlite_source(src_db, sql=sql, params=params or ())
    run_name = run_name or f"import_{target}"
    with run_import(run_name, db_path=_resolve_db_path(db_path), progress_every=progress_every) as run:
        return run.load(
            target=target,
            source=source,
            mapping=mapping,
            key=key_field,
            mode=mode,
            tombstone=tombstone,
            source_system=source_system,
            batch_size=batch_size,
            dry_run=dry_run,
        )


def load_tbl(
    *,
    tbl,
    src_db,
    src_tbl=None,
    cols_to_insert=None,
    select_named=None,
    db_path=None,
    batch_size=1000,
    dry_run=False,
):
    """Copy rows from a SQLite table/query into a target table (raw insert)."""
    if not cols_to_insert:
        raise ValueError("cols_to_insert is required")
    select_sql = _build_select_sql(select_named, src_tbl, cols_to_insert)
    return _load_sqlite_direct(
        tbl=tbl,
        src_db=src_db,
        select_sql=select_sql,
        cols_to_insert=list(cols_to_insert),
        db_path=_resolve_db_path(db_path),
        batch_size=batch_size,
        dry_run=dry_run,
    )


def load_tbl_mapped(
    *,
    tbl,
    src_db,
    src_tbl=None,
    select_named=None,
    map=None,
    db_path=None,
    batch_size=1000,
    dry_run=False,
):
    """Copy rows from SQLite with optional column mapping/transforms."""
    mapping = _normalize_mapping(map or {})
    if not mapping:
        raise ValueError("mapping is required for load_tbl_mapped")
    select_sql = _build_select_sql_mapped(select_named, src_tbl, mapping)
    return _load_sqlite_direct_mapped(
        tbl=tbl,
        src_db=src_db,
        select_sql=select_sql,
        mapping=mapping,
        db_path=_resolve_db_path(db_path),
        batch_size=batch_size,
        dry_run=dry_run,
    )


def _resolve_db_path(db_path):
    if db_path:
        return db_path
    return getattr(cfg, "DB_FILE", getattr(cfg, "db_name", "lifepim.db"))


def _target_from_tbl(tbl):
    name = (tbl or "").strip()
    if name.startswith("lp_"):
        return name[3:]
    return name


def _use_importer(target, use_importer):
    if use_importer is not None:
        return use_importer
    return target in {"contacts", "files", "media"}


def _infer_key(mapping):
    for candidate in ("source_uid", "sha256", "entity_id"):
        if candidate in mapping:
            return candidate
    if mapping:
        raise ValueError("key is required when source_uid/sha256/entity_id are not mapped")
    raise ValueError("key is required")


def _normalize_mapping(mapping):
    normalized = {}
    for target, spec in mapping.items():
        if isinstance(spec, list):
            spec = tuple(spec)
        if isinstance(spec, tuple) and len(spec) == 2:
            source_cols, transform = spec
            if isinstance(transform, str):
                transform_fn = TRANSFORMS.get(transform)
                if not transform_fn:
                    raise ValueError(f"Unknown transform: {transform}")
                transform = transform_fn
            if isinstance(source_cols, list):
                source_cols = tuple(source_cols)
            normalized[target] = (source_cols, transform)
        else:
            normalized[target] = spec
    return normalized


def _load_csv_direct(
    *,
    tbl,
    fname,
    mapping,
    db_path,
    batch_size,
    dry_run,
    encoding,
    delimiter,
):
    if not os.path.exists(fname):
        raise FileNotFoundError(fname)
    with open(fname, newline="", encoding=encoding) as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if mapping:
            insert_cols = list(mapping.keys())
        else:
            insert_cols = reader.fieldnames or []
            mapping = {col: col for col in insert_cols}
        if not insert_cols:
            raise ValueError("No columns available for insert")
        return _insert_rows(
            tbl=tbl,
            db_path=db_path,
            insert_cols=insert_cols,
            rows_iter=_iter_mapped_rows(reader, mapping),
            batch_size=batch_size,
            dry_run=dry_run,
        )


def _load_sqlite_direct(
    *,
    tbl,
    src_db,
    select_sql,
    cols_to_insert,
    db_path,
    batch_size,
    dry_run,
):
    if not os.path.exists(src_db):
        raise FileNotFoundError(src_db)
    conn_src = sqlite3.connect(src_db)
    conn_src.row_factory = sqlite3.Row
    cur = conn_src.execute(select_sql)
    col_count = len(cur.description or [])
    if col_count != len(cols_to_insert):
        conn_src.close()
        raise ValueError("cols_to_insert length must match select columns")

    def row_iter():
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield list(row)

    result = _insert_rows(
        tbl=tbl,
        db_path=db_path,
        insert_cols=cols_to_insert,
        rows_iter=row_iter(),
        batch_size=batch_size,
        dry_run=dry_run,
    )
    conn_src.close()
    return result


def _load_sqlite_direct_mapped(
    *,
    tbl,
    src_db,
    select_sql,
    mapping,
    db_path,
    batch_size,
    dry_run,
):
    if not os.path.exists(src_db):
        raise FileNotFoundError(src_db)
    conn_src = sqlite3.connect(src_db)
    conn_src.row_factory = sqlite3.Row
    cur = conn_src.execute(select_sql)

    def row_iter():
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                try:
                    yield dict(row)
                except Exception:
                    yield row

    insert_cols = list(mapping.keys())
    result = _insert_rows(
        tbl=tbl,
        db_path=db_path,
        insert_cols=insert_cols,
        rows_iter=_iter_mapped_rows_from_dicts(row_iter(), mapping),
        batch_size=batch_size,
        dry_run=dry_run,
    )
    conn_src.close()
    return result


def _build_select_sql(select_named, src_tbl, cols_to_insert):
    if select_named:
        lower = select_named.strip().lower()
        if " from " in lower:
            return select_named.strip()
        if lower.startswith("select "):
            select_named = select_named.strip()[7:].strip()
        if not src_tbl:
            raise ValueError("src_tbl is required when select_named has no FROM")
        return f"SELECT {select_named} FROM {src_tbl}"
    if not src_tbl:
        raise ValueError("src_tbl is required when select_named is not provided")
    return f"SELECT {', '.join(cols_to_insert)} FROM {src_tbl}"


def _build_select_sql_mapped(select_named, src_tbl, mapping):
    if select_named:
        return _build_select_sql(select_named, src_tbl, [])
    if not src_tbl:
        raise ValueError("src_tbl is required when select_named is not provided")
    source_cols = _extract_source_columns(mapping)
    if not source_cols:
        raise ValueError("mapping must reference at least one source column")
    return f"SELECT {', '.join(source_cols)} FROM {src_tbl}"


def _extract_source_columns(mapping):
    if mapping_mod:
        cols = mapping_mod.extract_source_columns(mapping)
    else:
        cols = []
        for value in mapping.values():
            if isinstance(value, str):
                cols.append(value)
            elif isinstance(value, tuple) and len(value) == 2:
                source_cols = value[0]
                if isinstance(source_cols, (tuple, list)):
                    cols.extend([str(col) for col in source_cols])
                else:
                    cols.append(str(source_cols))
    unique = []
    for col in cols:
        if col not in unique:
            unique.append(col)
    return unique


def _iter_mapped_rows(reader, mapping: dict):
    if not mapping_mod:
        for row in reader:
            yield [row.get(col) for col in mapping.keys()]
        return
    for row in reader:
        mapped, errors = mapping_mod.apply_mapping(row, mapping)
        if errors:
            continue
        yield [mapped.get(col) for col in mapping.keys()]


def _iter_mapped_rows_from_dicts(rows_iter, mapping):
    if not mapping_mod:
        for row in rows_iter:
            yield [row.get(col) for col in mapping.keys()]
        return
    for row in rows_iter:
        mapped, errors = mapping_mod.apply_mapping(row, mapping)
        if errors:
            continue
        yield [mapped.get(col) for col in mapping.keys()]


def _insert_rows(*, tbl, db_path, insert_cols, rows_iter, batch_size, dry_run):
    conn = sqlite3.connect(db_path)
    table_cols = _get_table_columns(conn, tbl)
    missing = [col for col in insert_cols if col not in table_cols]
    if missing:
        conn.close()
        raise ValueError(f"Target table {tbl} missing columns: {', '.join(missing)}")

    insert_cols = list(insert_cols)
    add_user = "user_name" in table_cols and "user_name" not in insert_cols
    add_extract = "rec_extract_date" in table_cols and "rec_extract_date" not in insert_cols
    if add_user:
        insert_cols.append("user_name")
    if add_extract:
        insert_cols.append("rec_extract_date")

    placeholders = ", ".join(["?"] * len(insert_cols))
    sql = f"INSERT INTO {tbl} ({', '.join(insert_cols)}) VALUES ({placeholders})"

    inserted = 0
    batch = []
    for row in rows_iter:
        values = list(row)
        if add_user:
            values.append(_current_user())
        if add_extract:
            values.append(_now_str())
        inserted += 1
        if dry_run:
            continue
        batch.append(tuple(values))
        if len(batch) >= batch_size:
            conn.executemany(sql, batch)
            conn.commit()
            batch = []
    if batch and not dry_run:
        conn.executemany(sql, batch)
        conn.commit()
    conn.close()
    return {"inserted": inserted, "dry_run": dry_run}


def _get_table_columns(conn, tbl):
    rows = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
    return [row[1] for row in rows]


def _current_user():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
