import argparse
import csv
import os
import sqlite3
from typing import Dict, Optional

from common import config as cfg

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


def get_int(d: Dict[str, str], key: str, default: int = 0) -> int:
    v = (d.get(key) or "").strip()
    if v == "":
        return default
    return int(float(v))


def get_float(d: Dict[str, str], key: str, default: float = 1.0) -> float:
    v = (d.get(key) or "").strip()
    if v == "":
        return default
    return float(v)


def get_text(d: Dict[str, str], key: str, default: str = "") -> str:
    v = d.get(key)
    return default if v is None else str(v).strip()


def clean_tab_label(value: str) -> str:
    cleaned = []
    for ch in (value or ""):
        if ch.isalnum() or ch in (" ", "/", "-", "_"):
            cleaned.append(ch)
    return " ".join("".join(cleaned).split())


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

DROP TABLE IF EXISTS map_folder_project;

CREATE TABLE IF NOT EXISTS map_folder_project (
  map_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  path_prefix  TEXT NOT NULL,
  tab          TEXT NOT NULL,
  grp          TEXT NOT NULL,

  -- IMPORTANT: project is NOT NULL, blank means "no project"
  project      TEXT NOT NULL DEFAULT '',

  tags         TEXT NOT NULL DEFAULT '',
  confidence   REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  priority     INTEGER NOT NULL DEFAULT 0,
  is_primary   INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
  notes        TEXT NOT NULL DEFAULT '',
  is_enabled   INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0,1)),
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at   TEXT NULL
);

-- Unique rule identity (project blank is valid)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mfp_rule
ON map_folder_project(path_prefix, tab, grp, project, is_primary);

CREATE INDEX IF NOT EXISTS ix_mfp_prefix ON map_folder_project(path_prefix);
CREATE INDEX IF NOT EXISTS ix_mfp_tab ON map_folder_project(tab);
CREATE INDEX IF NOT EXISTS ix_mfp_project ON map_folder_project(project);

CREATE TRIGGER IF NOT EXISTS trg_map_folder_project_updated
AFTER UPDATE ON map_folder_project
FOR EACH ROW
BEGIN
  UPDATE map_folder_project
  SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
  WHERE map_id = NEW.map_id;
END;

DROP TABLE IF EXISTS map_project_folder;

CREATE TABLE IF NOT EXISTS map_project_folder (
  folder_id       INTEGER NOT NULL,
  tab             TEXT NOT NULL,
  grp             TEXT NOT NULL,

  -- IMPORTANT: project is NOT NULL, blank means "no project"
  project         TEXT NOT NULL DEFAULT '',

  tags            TEXT NOT NULL DEFAULT '',
  confidence      REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
  matched_prefix  TEXT NOT NULL,
  rule_map_id     INTEGER NOT NULL,
  is_primary      INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
  is_enabled      INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0,1)),
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

  -- No COALESCE needed
  PRIMARY KEY (folder_id, tab, grp, project, is_primary),

  FOREIGN KEY(folder_id) REFERENCES dim_folder(folder_id),
  FOREIGN KEY(rule_map_id) REFERENCES map_folder_project(map_id)
);

CREATE INDEX IF NOT EXISTS ix_mpf_folder ON map_project_folder(folder_id);
CREATE INDEX IF NOT EXISTS ix_mpf_tab ON map_project_folder(tab);
CREATE INDEX IF NOT EXISTS ix_mpf_grp ON map_project_folder(grp);
CREATE INDEX IF NOT EXISTS ix_mpf_project ON map_project_folder(project);
CREATE INDEX IF NOT EXISTS ix_mpf_rule ON map_project_folder(rule_map_id);

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


def load_map_folder_project_csv(conn: sqlite3.Connection, rules_csv: str, clear_first: bool = True) -> int:
    """
    Expects columns (at minimum):
      path_prefix, tab, group OR grp
    Optional:
      project, tags, confidence, priority, is_primary, is_enabled, notes
    """
    if clear_first:
        conn.execute("DELETE FROM map_folder_project")

    n = 0
    with open(rules_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        # Support both "group" and "grp"
        fieldnames = set(reader.fieldnames or [])
        if "grp" not in fieldnames and "group" not in fieldnames:
            raise ValueError("Rules CSV must include 'grp' or 'group' column.")

        for row in reader:
            path_prefix = norm_path(get_text(row, "path_prefix"))
            tab = clean_tab_label(get_text(row, "tab"))
            grp = get_text(row, "grp") or get_text(row, "group")
            project = get_text(row, "project")
            tags = get_text(row, "tags", "")
            confidence = get_float(row, "confidence", 1.0)
            priority = get_int(row, "priority", 0)
            is_primary = get_int(row, "is_primary", 1)
            is_enabled = get_int(row, "is_enabled", 1)
            notes = get_text(row, "notes", "")

            if not path_prefix or not tab or not grp:
                # Skip malformed line
                continue

            conn.execute(
                """
                INSERT OR REPLACE INTO map_folder_project
                (path_prefix, tab, grp, project, tags, confidence, priority, is_primary, notes, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (path_prefix, tab, grp, project, tags, confidence, priority, is_primary, notes, is_enabled),
            )
            n += 1
    return n


def rebuild_map_project_folder(conn: sqlite3.Connection, only_active_folders: bool = False) -> int:
    conn.execute("DELETE FROM map_project_folder")

    where_active = "WHERE f.is_active = 1" if only_active_folders else ""

    cur = conn.execute(
        f"""
        INSERT INTO map_project_folder (
            folder_id, tab, grp, project, tags, confidence,
            matched_prefix, rule_map_id, is_primary, is_enabled, updated_at
        )
        SELECT
            f.folder_id,
            r.tab,
            r.grp,
            COALESCE(r.project, ''),
            r.tags,
            r.confidence,
            r.path_prefix,
            r.map_id,
            r.is_primary,
            r.is_enabled,
            strftime('%Y-%m-%dT%H:%M:%fZ','now')
        FROM dim_folder f
        JOIN map_folder_project r
          ON r.map_id = (
                SELECT r2.map_id
                FROM map_folder_project r2
                WHERE r2.is_enabled = 1
                  AND r2.is_primary = 1
                  AND lower(f.folder_path) LIKE lower(r2.path_prefix) || '%'
                ORDER BY
                  LENGTH(r2.path_prefix) DESC,
                  r2.priority DESC,
                  r2.confidence DESC,
                  r2.map_id DESC
                LIMIT 1
            )
        {where_active};
        """
    )
    return cur.rowcount if cur.rowcount != -1 else 0


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
    ap = argparse.ArgumentParser(description="LifePIM folder mapping ETL (dim_folder + map_folder_project + map_project_folder).")
    ap.add_argument("--db", required=True, help="SQLite DB file path (e.g., lifepim.db)")
    ap.add_argument("--folders_csv", required=True, help="CSV containing folders. Must have column 'folder_path' by default.")
    ap.add_argument("--folders_col", default="folder_path", help="Column name in folders_csv for folder paths (default: folder_path)")
    ap.add_argument("--rules_csv", required=True, help="CSV mapping rules (path_prefix, tab, grp/group, ...)")
    ap.add_argument("--no_clear_rules", action="store_true", help="Do not clear map_folder_project before insert (default clears)")
    ap.add_argument("--only_active", action="store_true", help="Only map active folders when building map_project_folder")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)

    conn = sqlite3.connect(args.db)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(DDL_RESET_NO_FK)

        conn.execute("BEGIN")
        n_folders = load_folder_list_csv(conn, args.folders_csv, col=args.folders_col)
        n_rules = load_map_folder_project_csv(conn, args.rules_csv, clear_first=(not args.no_clear_rules))
        n_backfilled = backfill_folder_ids(conn)
        n_mapped = rebuild_map_project_folder(conn, only_active_folders=args.only_active)
        conn.commit()

        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

        stats = folder_id_stats(conn)
        print(
            f"OK: folders_seen={n_folders}, rules_loaded={n_rules}, "
            f"folder_ids_updated={n_backfilled}, folders_mapped={n_mapped}"
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
