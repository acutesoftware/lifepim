import argparse
import csv
import os
import sqlite3
from typing import Dict, Optional

from common import config as cfg

"""
Folder cache maintenance for file-backed LifePIM records.

Original intent:
    This script used to do two jobs:
    1. cache known hard-drive folders in dim_folder; and
    2. map those folders to left-hand-side Areas through legacy mapping tables.

Current intent:
    Area-to-folder mapping is now stored in lp_area_folders and managed from the
    Notes folder panel, with bulk bootstrap import handled by
    common.areas.import_area_mappings_csv(). This script only maintains
    dim_folder and backfills folder_id values on file-backed tables.

Run it when folder metadata has been refreshed and records need folder_id
backfill. Do not run it to repair Notes Area membership; use Settings > Notes >
Materialize note areas for that.
"""

# ----------------------------
# Helpers
# ----------------------------
def norm_path(p: str) -> str:
    """Normalize Windows-ish paths for stable prefix matching."""
    p = (p or "").strip().strip('"').strip()
    if not p:
        return p
    p = p.replace("/", "\\")
    for src, dst in getattr(cfg, "PATH_ALIASES", []):
        src_norm = src.replace("/", "\\")
        dst_norm = dst.replace("/", "\\")
        if p.lower().startswith(src_norm.lower()):
            p = dst_norm + p[len(src_norm):]
            break
    # Uppercase drive letter if present
    if len(p) >= 2 and p[1] == ":":
        p = p[0].upper() + p[1:]
    # Strip trailing backslash (except root like 'C:\')
    if len(p) > 3 and p.endswith("\\"):
        p = p.rstrip("\\")
    return p


def _strip_drop_tables(ddl_text: str) -> str:
    lines = []
    for line in ddl_text.splitlines():
        if line.strip().upper().startswith("DROP TABLE"):
            continue
        lines.append(line)
    return "\n".join(lines)


# ----------------------------
# DDL
# ----------------------------

DDL_RESET = """PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS dim_folder;

CREATE TABLE IF NOT EXISTS dim_folder (
  folder_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  folder_path     TEXT NOT NULL UNIQUE,
  is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
  first_seen_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  last_seen_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  replaced_by_folder_id INTEGER NULL,
  FOREIGN KEY(replaced_by_folder_id) REFERENCES dim_folder(folder_id)
);

"""
DDL_CREATE = _strip_drop_tables(DDL_RESET)
DDL_RESET_NO_FK = DDL_RESET.replace("PRAGMA foreign_keys = ON;\n\n", "")
DDL_CREATE_NO_FK = DDL_CREATE.replace("PRAGMA foreign_keys = ON;\n\n", "")

# ----------------------------
# ETL Steps
# ----------------------------
def upsert_dim_folder(conn: sqlite3.Connection, folder_path: str) -> None:
    fp = norm_path(folder_path)
    if not fp:
        return
    conn.execute("INSERT OR IGNORE INTO dim_folder(folder_path) VALUES (?)", (fp,))
    conn.execute(
        "UPDATE dim_folder SET last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), is_active=1 WHERE folder_path=?",
        (fp,),
    )


def load_folder_list_csv(conn: sqlite3.Connection, folder_list_csv: str, col: str = "folder_path") -> int:
    n = 0
    with open(folder_list_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if col not in reader.fieldnames:
            raise ValueError(f"Folder list CSV must include column '{col}'. Found: {reader.fieldnames}")
        for row in reader:
            upsert_dim_folder(conn, row.get(col, ""))
            n += 1
    return n


def _table_has_column(conn: sqlite3.Connection, tbl_name: str, col_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({tbl_name})").fetchall()
    return any(row[1].lower() == col_name.lower() for row in rows)


def _derive_folder_path(route_name: str, row: sqlite3.Row) -> str:
    if route_name == "apps":
        file_path = row["file_path"] or ""
        return os.path.dirname(file_path) if file_path else ""
    if route_name == "notes":
        path_value = (row["path"] or "").strip()
        file_name = (row["file_name"] or "").strip()
        full_path = ""
        if file_name and os.path.isabs(file_name):
            full_path = file_name
        elif path_value and file_name:
            full_path = os.path.join(path_value, file_name)
        else:
            full_path = path_value or file_name
        if os.path.splitext(full_path)[1]:
            return os.path.dirname(full_path)
        return path_value or os.path.dirname(full_path)
    if route_name in ("media", "audio", "3d"):
        path_value = (row["path"] or "").strip()
        file_name = (row["file_name"] or "").strip()
        if path_value:
            return path_value
        if file_name and os.path.isabs(file_name):
            return os.path.dirname(file_name)
        return os.path.dirname(os.path.join(path_value, file_name)) if file_name else ""
    if route_name == "files":
        return (row["path"] or "").strip()
    return ""


def backfill_folder_ids(conn: sqlite3.Connection) -> int:
    conn.row_factory = sqlite3.Row
    file_tables = [
        ("lp_notes", "notes", ["id", "folder_id", "path", "file_name"]),
        ("lp_media", "media", ["id", "folder_id", "path", "file_name"]),
        ("lp_audio", "audio", ["id", "folder_id", "path", "file_name"]),
        ("lp_3d", "3d", ["id", "folder_id", "path", "file_name"]),
        ("lp_files", "files", ["id", "folder_id", "path"]),
        ("lp_apps", "apps", ["id", "folder_id", "file_path"]),
    ]
    updated = 0
    path_to_id = {}
    id_to_path = {}
    for row in conn.execute("SELECT folder_id, folder_path FROM dim_folder").fetchall():
        raw_path = row["folder_path"] or ""
        norm = norm_path(raw_path)
        if not norm or norm != raw_path:
            continue
        key = norm.lower()
        path_to_id[key] = row["folder_id"]
        id_to_path[row["folder_id"]] = key

    def _is_missing_folder_id(value) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() in ("", "0")
        try:
            return int(value) == 0
        except (TypeError, ValueError):
            return True

    def _coerce_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _get_folder_id(folder_path: str) -> Optional[int]:
        key = folder_path.lower()
        folder_id = path_to_id.get(key)
        if folder_id:
            return folder_id
        upsert_dim_folder(conn, folder_path)
        row = conn.execute(
            "SELECT folder_id FROM dim_folder WHERE folder_path = ?",
            (folder_path,),
        ).fetchone()
        if not row:
            return None
        folder_id = row["folder_id"]
        path_to_id[key] = folder_id
        id_to_path[folder_id] = key
        return folder_id

    for tbl_name, route_name, cols in file_tables:
        if not _table_has_column(conn, tbl_name, "folder_id"):
            continue
        cols_sql = ", ".join(cols)
        rows = conn.execute(f"SELECT {cols_sql} FROM {tbl_name}").fetchall()
        for row in rows:
            folder_path = norm_path(_derive_folder_path(route_name, row))
            if not folder_path:
                continue
            folder_id = _get_folder_id(folder_path)
            if not folder_id:
                continue
            current_id = row["folder_id"]
            current_id_int = _coerce_int(current_id)
            needs_update = False
            if _is_missing_folder_id(current_id):
                needs_update = True
            else:
                current_key = id_to_path.get(current_id_int) if current_id_int is not None else None
                if current_key is None or current_key != folder_path.lower():
                    needs_update = True
            if needs_update and current_id_int != folder_id:
                conn.execute(
                    f"UPDATE {tbl_name} SET folder_id = ? WHERE id = ?",
                    (folder_id, row["id"]),
                )
                updated += 1
    return updated


def folder_id_stats(conn: sqlite3.Connection) -> Dict[str, int]:
    stats = {}
    file_tables = [
        "lp_notes",
        "lp_media",
        "lp_audio",
        "lp_3d",
        "lp_files",
        "lp_apps",
    ]
    for tbl_name in file_tables:
        if not _table_has_column(conn, tbl_name, "folder_id"):
            continue
        total = conn.execute(f"SELECT COUNT(1) FROM {tbl_name}").fetchone()[0]
        with_folder = conn.execute(
            f"SELECT COUNT(1) FROM {tbl_name} WHERE folder_id IS NOT NULL AND folder_id != 0 AND folder_id != ''"
        ).fetchone()[0]
        stats[f"{tbl_name}_with_folder_id"] = with_folder
        stats[f"{tbl_name}_total"] = total
    return stats


# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="LifePIM folder cache ETL (dim_folder + folder_id backfill).")
    ap.add_argument("--db", required=True, help="SQLite DB file path (e.g., lifepim.db)")
    ap.add_argument("--folders_csv", required=True, help="CSV containing folders. Must have column 'folder_path' by default.")
    ap.add_argument("--folders_col", default="folder_path", help="Column name in folders_csv for folder paths (default: folder_path)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)

    conn = sqlite3.connect(args.db)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(DDL_RESET_NO_FK)

        conn.execute("BEGIN")
        n_folders = load_folder_list_csv(conn, args.folders_csv, col=args.folders_col)
        n_backfilled = backfill_folder_ids(conn)
        conn.commit()

        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

        stats = folder_id_stats(conn)
        print(
            f"OK: folders_seen={n_folders}, folder_ids_updated={n_backfilled}"
        )
        for key in sorted(stats.keys()):
            print(f"{key}={stats[key]}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
