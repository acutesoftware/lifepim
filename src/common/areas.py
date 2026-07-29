import os
import sqlite3
from datetime import datetime, timezone

from common import data as db
from common import config as cfg
from common import user_paths

AREAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lp_areas (
    owner_user_id   INTEGER,
    area_id      TEXT NOT NULL,
    icon            TEXT,
    tab             TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    area_name    TEXT NOT NULL,
    is_header       INTEGER NOT NULL DEFAULT 0,
    is_system       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    tags            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    pinned          INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_utc     TEXT NOT NULL,
    updated_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, area_id)
);

CREATE INDEX IF NOT EXISTS idx_lp_areas_tab_group
ON lp_areas (owner_user_id, tab, group_name, sort_order, area_name);

CREATE INDEX IF NOT EXISTS idx_lp_areas_status
ON lp_areas (owner_user_id, status);

CREATE TABLE IF NOT EXISTS lp_area_folders (
    area_folder_id    INTEGER PRIMARY KEY,
    owner_user_id        INTEGER,
    area_id           TEXT NOT NULL,
    path_prefix          TEXT NOT NULL,
    folder_role          TEXT NOT NULL,
    create_type          TEXT NOT NULL DEFAULT 'none',
    is_write_enabled     INTEGER NOT NULL DEFAULT 0,
    confidence           REAL NOT NULL DEFAULT 1.0,
    tags                 TEXT,
    notes                TEXT,
    sort_order           INTEGER NOT NULL DEFAULT 100,
    is_enabled           INTEGER NOT NULL DEFAULT 1,
    created_utc          TEXT NOT NULL,
    updated_utc          TEXT NOT NULL,
    UNIQUE (owner_user_id, area_id, path_prefix)
);

CREATE INDEX IF NOT EXISTS idx_lp_area_folders_area
ON lp_area_folders (owner_user_id, area_id, folder_role, sort_order);

CREATE INDEX IF NOT EXISTS idx_lp_area_folders_path
ON lp_area_folders (path_prefix);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lp_area_default_folder
ON lp_area_folders (owner_user_id, area_id)
WHERE folder_role = 'default' AND is_enabled = 1;
"""


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_conn(conn=None):
    if conn is None:
        conn = db._get_conn()
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    return conn


_AREAS_SCHEMA_READY_CONN_IDS = set()


def ensure_areas_schema(conn=None):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _AREAS_SCHEMA_READY_CONN_IDS:
        try:
            if _areas_schema_is_current(conn):
                return
        except Exception:
            pass
        _AREAS_SCHEMA_READY_CONN_IDS.discard(conn_id)
    _migrate_legacy_area_tables(conn)
    _migrate_areas_schema(conn)
    _migrate_area_folders_schema(conn)
    conn.executescript(AREAS_SCHEMA)
    _migrate_legacy_area_ids(conn)
    conn.commit()
    _AREAS_SCHEMA_READY_CONN_IDS.add(conn_id)


def _areas_schema_is_current(conn):
    area_cols = {row["name"] for row in _table_columns(conn, "lp_areas")}
    folder_cols = {row["name"] for row in _table_columns(conn, "lp_area_folders")}
    return (
        {"owner_user_id", "area_id", "status"}.issubset(area_cols)
        and {"owner_user_id", "area_id", "path_prefix"}.issubset(folder_cols)
    )


def _table_columns(conn, table_name):
    try:
        return [dict(row) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    except Exception:
        return []


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def normalize_area_id(value):
    text = (value or "").strip()
    if text in {"proj", "project"}:
        return "area"
    if text.startswith("proj/"):
        return "area/" + text[5:]
    if text.startswith("project/"):
        return "area/" + text[8:]
    if text.startswith("proj."):
        return "area." + text[5:]
    if text.startswith("project."):
        return "area." + text[8:]
    return text


def _legacy_area_label(value):
    text = value if value is not None else ""
    if text == "PROJECTS":
        return "AREAS"
    if text == "Projects":
        return "Areas"
    if text == "All Projects":
        return "All Areas"
    return text


def _row_value(row, primary, legacy=None, default=""):
    keys = row.keys()
    if primary in keys:
        return row[primary]
    if legacy and legacy in keys:
        return row[legacy]
    return default


def _unused_legacy_table_name(conn, table_name):
    candidate = f"{table_name}_legacy"
    suffix = 2
    while _table_exists(conn, candidate):
        candidate = f"{table_name}_legacy_{suffix}"
        suffix += 1
    return candidate


def _migrate_legacy_area_tables(conn):
    if _table_exists(conn, "lp_projects"):
        conn.executescript(AREAS_SCHEMA)
        rows = conn.execute("SELECT * FROM lp_projects").fetchall()
        for row in rows:
            area_id = normalize_area_id(_row_value(row, "area_id", "project_id"))
            area_name = _legacy_area_label(_row_value(row, "area_name", "project_name", area_id))
            tab = _legacy_area_label(_row_value(row, "tab", default="Areas"))
            group_name = _legacy_area_label(_row_value(row, "group_name", default=tab))
            conn.execute(
                "INSERT OR IGNORE INTO lp_areas "
                "(owner_user_id, area_id, icon, tab, group_name, area_name, is_header, is_system, "
                "status, tags, sort_order, pinned, notes, created_utc, updated_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _row_value(row, "owner_user_id", default=None),
                    area_id,
                    _row_value(row, "icon", default=""),
                    tab,
                    group_name,
                    area_name,
                    _row_value(row, "is_header", default=0),
                    _row_value(row, "is_system", default=0),
                    _row_value(row, "status", default="active") or "active",
                    _row_value(row, "tags", default=None),
                    _row_value(row, "sort_order", default=100) or 100,
                    _row_value(row, "pinned", default=0) or 0,
                    _row_value(row, "notes", default=None),
                    _row_value(row, "created_utc", default=_utc_now()) or _utc_now(),
                    _row_value(row, "updated_utc", default=_utc_now()) or _utc_now(),
                ),
            )
        conn.execute(f"ALTER TABLE lp_projects RENAME TO {_unused_legacy_table_name(conn, 'lp_projects')}")

    if _table_exists(conn, "lp_project_folders"):
        conn.executescript(AREAS_SCHEMA)
        rows = conn.execute("SELECT * FROM lp_project_folders").fetchall()
        for row in rows:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO lp_area_folders "
                    "(area_folder_id, owner_user_id, area_id, path_prefix, folder_role, create_type, "
                    "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        _row_value(row, "area_folder_id", "project_folder_id"),
                        _row_value(row, "owner_user_id", default=None),
                        normalize_area_id(_row_value(row, "area_id", "project_id")),
                        _row_value(row, "path_prefix", default=""),
                        _row_value(row, "folder_role", default="include") or "include",
                        _row_value(row, "create_type", default="none") or "none",
                        _row_value(row, "is_write_enabled", default=0) or 0,
                        _row_value(row, "confidence", default=1.0) or 1.0,
                        _row_value(row, "tags", default=None),
                        _row_value(row, "notes", default=None),
                        _row_value(row, "sort_order", default=100) or 100,
                        _row_value(row, "is_enabled", default=1) or 1,
                        _row_value(row, "created_utc", default=_utc_now()) or _utc_now(),
                        _row_value(row, "updated_utc", default=_utc_now()) or _utc_now(),
                    ),
                )
            except sqlite3.IntegrityError:
                pass
        conn.execute(
            f"ALTER TABLE lp_project_folders RENAME TO {_unused_legacy_table_name(conn, 'lp_project_folders')}"
        )


def _migrate_areas_schema(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lp_areas'"
    ).fetchone()
    if not exists:
        return
    columns = _table_columns(conn, "lp_areas")
    column_names = {row["name"] for row in columns}
    area_id_is_pk = any(row["name"] == "area_id" and int(row.get("pk") or 0) for row in columns)
    required = {"owner_user_id", "icon", "is_header", "is_system"}
    if required.issubset(column_names) and not area_id_is_pk:
        return
    conn.execute("ALTER TABLE lp_areas RENAME TO lp_areas_legacy")
    conn.executescript(AREAS_SCHEMA)
    legacy_cols = {row["name"] for row in _table_columns(conn, "lp_areas_legacy")}
    select_expr = {
        "owner_user_id": "owner_user_id" if "owner_user_id" in legacy_cols else "NULL",
        "area_id": "area_id" if "area_id" in legacy_cols else "project_id",
        "icon": "icon" if "icon" in legacy_cols else "''",
        "tab": "tab",
        "group_name": "group_name",
        "area_name": "area_name" if "area_name" in legacy_cols else "project_name",
        "is_header": "is_header" if "is_header" in legacy_cols else "0",
        "is_system": "is_system" if "is_system" in legacy_cols else "0",
        "status": "status",
        "tags": "tags",
        "sort_order": "sort_order",
        "pinned": "pinned",
        "notes": "notes",
        "created_utc": "created_utc",
        "updated_utc": "updated_utc",
    }
    insert_cols = ", ".join(select_expr.keys())
    select_cols = ", ".join(select_expr.values())
    conn.execute(
        f"INSERT OR IGNORE INTO lp_areas ({insert_cols}) SELECT {select_cols} FROM lp_areas_legacy"
    )
    conn.execute("DROP TABLE lp_areas_legacy")
    conn.commit()


def _duncan_user_id(conn):
    try:
        row = conn.execute(
            "SELECT user_id FROM users WHERE lower(username) = 'duncan' ORDER BY user_id LIMIT 1"
        ).fetchone()
    except Exception:
        return None
    return row["user_id"] if row else None


def _single_area_owner(conn, area_id):
    try:
        rows = conn.execute(
            "SELECT DISTINCT owner_user_id FROM lp_areas WHERE area_id = ?",
            (area_id,),
        ).fetchall()
    except Exception:
        return None
    owners = [row["owner_user_id"] for row in rows if row["owner_user_id"] is not None]
    return owners[0] if len(owners) == 1 else None


def _migrate_area_folders_schema(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lp_area_folders'"
    ).fetchone()
    if not exists:
        return
    columns = _table_columns(conn, "lp_area_folders")
    column_names = {row["name"] for row in columns}
    if "owner_user_id" in column_names:
        return
    legacy_rows = conn.execute("SELECT * FROM lp_area_folders").fetchall()
    conn.execute("ALTER TABLE lp_area_folders RENAME TO lp_area_folders_legacy")
    for index_name in (
        "idx_lp_area_folders_area",
        "idx_lp_area_folders_path",
        "ux_lp_area_default_folder",
    ):
        conn.execute(f"DROP INDEX IF EXISTS {index_name}")
    conn.executescript(AREAS_SCHEMA)
    duncan_user_id = _duncan_user_id(conn)
    for row in legacy_rows:
        owner_user_id = duncan_user_id
        if owner_user_id is None:
            owner_user_id = _single_area_owner(conn, row["area_id"])
        try:
            conn.execute(
                "INSERT OR IGNORE INTO lp_area_folders "
                "(area_folder_id, owner_user_id, area_id, path_prefix, folder_role, create_type, "
                "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["area_folder_id"],
                    owner_user_id,
                    row["area_id"],
                    row["path_prefix"],
                    row["folder_role"],
                    row["create_type"],
                    row["is_write_enabled"],
                    row["confidence"],
                    row["tags"],
                    row["notes"],
                    row["sort_order"],
                    row["is_enabled"],
                    row["created_utc"],
                    row["updated_utc"],
                ),
            )
        except sqlite3.IntegrityError:
            pass
    conn.execute("DROP TABLE lp_area_folders_legacy")
    conn.commit()


def _migrate_legacy_area_ids(conn):
    for table_name, column_name in (
        ("lp_areas", "area_id"),
        ("lp_area_folders", "area_id"),
    ):
        if not _table_exists(conn, table_name):
            continue
        columns = {row["name"] for row in _table_columns(conn, table_name)}
        if column_name not in columns:
            continue
        rows = conn.execute(
            f"SELECT rowid, {column_name} FROM {table_name} "
            f"WHERE {column_name} IN ('proj', 'project') "
            f"OR {column_name} LIKE 'proj/%' OR {column_name} LIKE 'project/%' "
            f"OR {column_name} LIKE 'proj.%' OR {column_name} LIKE 'project.%'"
        ).fetchall()
        for row in rows:
            next_id = normalize_area_id(row[column_name])
            if next_id == row[column_name]:
                continue
            try:
                conn.execute(
                    f"UPDATE {table_name} SET {column_name} = ? WHERE rowid = ?",
                    (next_id, row["rowid"]),
                )
            except sqlite3.IntegrityError:
                pass
    if _table_exists(conn, "lp_areas"):
        conn.execute("UPDATE lp_areas SET tab = 'AREAS' WHERE tab = 'PROJECTS'")
        conn.execute("UPDATE lp_areas SET group_name = 'AREAS' WHERE group_name = 'PROJECTS'")
        conn.execute("UPDATE lp_areas SET area_name = 'AREAS' WHERE area_name = 'PROJECTS'")
        conn.execute("UPDATE lp_areas SET area_name = 'All Areas' WHERE area_name = 'All Projects'")


def _current_owner_user_id():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "user_id", None)
    except Exception:
        return None
    return None


def _current_username():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return (getattr(current_user, "username", "") or "").strip()
    except Exception:
        return ""
    return ""


def _owner_user_id(owner_user_id=None):
    return _current_owner_user_id() if owner_user_id is None else owner_user_id


def _owner_condition(column="owner_user_id", owner_user_id=None):
    return f"{column} IS ?", [_owner_user_id(owner_user_id)]


def _int_value(value, default=0):
    if value is None or value == "":
        return default
    return int(value)


def normalize_path_prefix(path_value):
    normalized = (path_value or "").strip().strip('"').strip()
    if not normalized:
        return ""
    normalized = normalized.replace("/", "\\")
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = normalized[0].upper() + normalized[1:]
    if not os.path.isabs(normalized):
        raise ValueError("Path prefix must be an absolute path.")
    normalized = os.path.abspath(normalized)
    if len(normalized) > 3 and normalized.endswith("\\"):
        normalized = normalized.rstrip("\\")
    return normalized


def areas_list_sidebar(status="active", conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    params = [_owner_user_id(owner_user_id)]
    condition = "owner_user_id IS ? AND is_header = 0 AND is_system = 0"
    if status:
        condition += " AND status = ?"
        params.append(status)
    sql = (
        "SELECT owner_user_id, area_id, icon, tab, group_name, area_name, "
        "is_header, is_system, status, tags, "
        "sort_order, pinned, notes, created_utc, updated_utc "
        "FROM lp_areas "
        f"WHERE {condition} "
        "ORDER BY tab, group_name, pinned DESC, sort_order, area_name"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def areas_sidebar_tree(status="active", conn=None, owner_user_id=None):
    rows = areas_list_sidebar(status=status, conn=conn, owner_user_id=owner_user_id)
    tabs = {}
    for row in rows:
        tab = row.get("tab") or ""
        group_name = row.get("group_name") or ""
        tab_entry = tabs.get(tab)
        if not tab_entry:
            tab_entry = {"tab": tab, "groups": {}}
            tabs[tab] = tab_entry
        groups = tab_entry["groups"]
        group_entry = groups.get(group_name)
        if not group_entry:
            group_entry = {"group_name": group_name, "areas": []}
            groups[group_name] = group_entry
        group_entry["areas"].append(row)
    ordered = []
    for tab in sorted(tabs.keys()):
        tab_entry = tabs[tab]
        groups = []
        for group_name in sorted(tab_entry["groups"].keys()):
            group_entry = tab_entry["groups"][group_name]
            groups.append(group_entry)
        ordered.append({"tab": tab, "groups": groups})
    return ordered


SIMPLE_SIDE_TABS = [
    {"icon": "🏠", "id": "home", "label": "Home"},
    {"icon": "💼", "id": "work", "label": "Work"},
    {"icon": "👪", "id": "family", "label": "Family"},
    {"icon": "🎉", "id": "fun", "label": "Fun"},
]


def _username_for_owner(conn, owner_user_id):
    if owner_user_id is None:
        return _current_username()
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if not exists:
            return "duncan"
        row = conn.execute("SELECT username FROM users WHERE user_id = ?", (owner_user_id,)).fetchone()
    except Exception:
        return _current_username()
    return (row["username"] or "").strip() if row else _current_username()


def _owner_is_duncan(conn, owner_user_id):
    return _username_for_owner(conn, owner_user_id).lower() == "duncan"


def _default_sidebar_source(conn, owner_user_id):
    return cfg.SIDE_TABS if _owner_is_duncan(conn, owner_user_id) or owner_user_id is None else SIMPLE_SIDE_TABS


def _default_sidebar_rows(owner_user_id=None, source_rows=None):
    rows = []
    current_group = "Areas"
    for idx, entry in enumerate(source_rows or cfg.SIDE_TABS):
        entry_id = (entry.get("id") or "").strip()
        label = (entry.get("label") or entry_id).strip()
        icon = entry.get("icon") or ""
        if not entry_id:
            continue
        lower_id = entry_id.lower()
        is_system = 1 if lower_id in {"all", "any", "unmapped"} else 0
        is_header = 1 if lower_id == "spacer" or (not icon and label and label.upper() == label) else 0
        if is_header:
            current_group = label
            area_id = entry_id if lower_id != "spacer" else f"header-{idx}"
            tab = label
            area_name = label
        else:
            area_id = entry_id
            tab = current_group
            area_name = label
        rows.append(
            {
                "owner_user_id": owner_user_id,
                "area_id": area_id,
                "icon": icon,
                "tab": tab,
                "group_name": current_group,
                "area_name": area_name,
                "is_header": is_header,
                "is_system": is_system,
                "status": "active",
                "sort_order": idx * 10,
            }
        )
    return rows


def _sidebar_looks_like_source(conn, owner_user_id, source_rows):
    expected = {
        (row["area_id"], row["area_name"], int(row["is_header"] or 0), int(row["is_system"] or 0))
        for row in _default_sidebar_rows(owner_user_id, source_rows=source_rows)
    }
    rows = conn.execute(
        "SELECT area_id, area_name, is_header, is_system FROM lp_areas WHERE owner_user_id IS ?",
        (owner_user_id,),
    ).fetchall()
    actual = {
        (row["area_id"], row["area_name"], int(row["is_header"] or 0), int(row["is_system"] or 0))
        for row in rows
    }
    return bool(actual) and actual == expected


def _sidebar_looks_like_flat_legacy(conn, owner_user_id):
    row = conn.execute(
        """
        SELECT COUNT(1) AS cnt,
               SUM(CASE WHEN COALESCE(icon, '') != '' THEN 1 ELSE 0 END) AS icon_count,
               SUM(CASE WHEN COALESCE(is_header, 0) = 1 THEN 1 ELSE 0 END) AS header_count,
               SUM(CASE WHEN COALESCE(is_system, 0) = 1 THEN 1 ELSE 0 END) AS system_count,
               COUNT(DISTINCT sort_order) AS sort_count
        FROM lp_areas
        WHERE owner_user_id IS ?
        """,
        (owner_user_id,),
    ).fetchone()
    if not row or int(row["cnt"] or 0) == 0:
        return False
    return (
        int(row["icon_count"] or 0) == 0
        and int(row["header_count"] or 0) == 0
        and int(row["system_count"] or 0) == 0
        and int(row["sort_count"] or 0) <= 1
    )


def seed_default_areas_for_user(owner_user_id=None, conn=None, replace=False):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    source_rows = _default_sidebar_source(conn, owner_user_id)
    existing = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_areas WHERE owner_user_id IS ?",
        (owner_user_id,),
    ).fetchone()
    if existing and int(existing["cnt"] or 0) and not replace:
        if _sidebar_looks_like_flat_legacy(conn, owner_user_id):
            replace = True
        elif owner_user_id is not None and not _owner_is_duncan(conn, owner_user_id) and _sidebar_looks_like_source(conn, owner_user_id, cfg.SIDE_TABS):
            replace = True
        else:
            return 0
    legacy = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_areas WHERE owner_user_id IS NULL"
    ).fetchone()
    if (
        not replace
        and owner_user_id is not None
        and legacy
        and int(legacy["cnt"] or 0)
        and _current_username().lower() == "duncan"
    ):
        if _sidebar_looks_like_flat_legacy(conn, None):
            conn.execute("DELETE FROM lp_areas WHERE owner_user_id IS NULL")
            conn.commit()
            replace = True
        else:
            conn.execute("UPDATE lp_areas SET owner_user_id = ? WHERE owner_user_id IS NULL", (owner_user_id,))
            claim_legacy_area_folders_for_user(owner_user_id, conn=conn)
            conn.commit()
            return int(legacy["cnt"] or 0)
    if existing and int(existing["cnt"] or 0) and not replace:
        return 0
    if replace:
        conn.execute("DELETE FROM lp_areas WHERE owner_user_id IS ?", (owner_user_id,))
        conn.commit()
    count = 0
    for row in _default_sidebar_rows(owner_user_id, source_rows=source_rows):
        area_upsert(row, conn=conn, owner_user_id=owner_user_id)
        count += 1
    return count


def claim_legacy_area_folders_for_user(owner_user_id, conn=None):
    if owner_user_id is None:
        return 0
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    cur = conn.execute(
        """
        UPDATE lp_area_folders
        SET owner_user_id = ?
        WHERE owner_user_id IS NULL
          AND area_id IN (
              SELECT area_id FROM lp_areas WHERE owner_user_id IS ?
          )
        """,
        (owner_user_id, owner_user_id),
    )
    conn.commit()
    return cur.rowcount if cur.rowcount is not None else 0


def areas_side_tabs(owner_user_id=None, conn=None, seed=True):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if owner_user_id is None:
        return list(cfg.SIDE_TABS)
    if seed:
        seed_default_areas_for_user(owner_user_id, conn=conn, replace=False)
    rows = conn.execute(
        "SELECT area_id, icon, group_name, area_name, is_header, is_system, status, sort_order "
        "FROM lp_areas WHERE owner_user_id IS ? AND status = 'active' "
        "ORDER BY sort_order, area_name",
        (owner_user_id,),
    ).fetchall()
    side_tabs = []
    for row in rows:
        side_tabs.append(
            {
                "icon": row["icon"] or "",
                "id": row["area_id"],
                "area": "" if str(row["area_id"]).startswith("header-") else row["area_id"],
                "label": row["area_name"],
                "group_name": row["group_name"],
                "is_header": int(row["is_header"] or 0),
                "is_system": int(row["is_system"] or 0),
            }
        )
    return side_tabs or list(cfg.SIDE_TABS)


def _quote_identifier(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def _table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [row["name"] for row in rows]


def _rename_area_references(conn, old_area_id, new_area_id, owner_user_id=None):
    old_area_id = (old_area_id or "").strip()
    new_area_id = (new_area_id or "").strip()
    if not old_area_id or not new_area_id or old_area_id == new_area_id:
        return 0
    owner_user_id = _owner_user_id(owner_user_id)
    changed = 0

    cur = conn.execute(
        "UPDATE lp_area_folders SET area_id = ?, updated_utc = ? "
        "WHERE owner_user_id IS ? AND area_id = ?",
        (new_area_id, _utc_now(), owner_user_id, old_area_id),
    )
    changed += cur.rowcount if cur.rowcount is not None else 0

    for table_name in _table_names(conn):
        if table_name in {"lp_areas", "lp_area_folders"}:
            continue
        columns = {row["name"] for row in _table_columns(conn, table_name)}
        owner_clause = ""
        params_suffix = []
        if "owner_user_id" in columns:
            owner_clause = " AND owner_user_id IS ?"
            params_suffix.append(owner_user_id)
        for column_name in ("area", "area_id"):
            if column_name not in columns:
                continue
            cur = conn.execute(
                f"UPDATE {_quote_identifier(table_name)} "
                f"SET {_quote_identifier(column_name)} = ? "
                f"WHERE {_quote_identifier(column_name)} = ?{owner_clause}",
                [new_area_id, old_area_id] + params_suffix,
            )
            changed += cur.rowcount if cur.rowcount is not None else 0
    return changed


def save_user_sidebar_rows(rows, owner_user_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if owner_user_id is None:
        raise ValueError("A logged-in user is required.")
    now = _utc_now()
    seen_area_ids = set()
    rename_pairs = []
    normalized_rows = []
    for row in rows:
        area_id = (row.get("area_id") or "").strip()
        area_name = (row.get("area_name") or "").strip()
        if not area_id or not area_name:
            continue
        key = area_id.lower()
        if key in seen_area_ids:
            raise ValueError(f"Duplicate area id: {area_id}")
        seen_area_ids.add(key)
        normalized = dict(row)
        normalized["area_id"] = area_id
        normalized["area_name"] = area_name
        normalized_rows.append(normalized)
        original_area_id = (row.get("original_area_id") or "").strip()
        if original_area_id and original_area_id != area_id:
            rename_pairs.append((original_area_id, area_id))
    for old_area_id, new_area_id in rename_pairs:
        _rename_area_references(conn, old_area_id, new_area_id, owner_user_id=owner_user_id)
    conn.execute("DELETE FROM lp_areas WHERE owner_user_id IS ?", (owner_user_id,))
    for idx, row in enumerate(normalized_rows):
        area_id = (row.get("area_id") or "").strip()
        area_name = (row.get("area_name") or "").strip()
        if not area_id or not area_name:
            continue
        is_header = int(row.get("is_header") or 0)
        is_system = int(row.get("is_system") or 0)
        group_name = (row.get("group_name") or "").strip()
        if is_header:
            group_name = area_name
        if not group_name:
            group_name = "Areas"
        tab = group_name
        conn.execute(
            "INSERT INTO lp_areas "
            "(owner_user_id, area_id, icon, tab, group_name, area_name, is_header, is_system, "
            "status, tags, sort_order, pinned, notes, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                area_id,
                row.get("icon") or "",
                tab,
                group_name,
                area_name,
                is_header,
                is_system,
                row.get("status") or "active",
                row.get("tags"),
                _int_value(row.get("sort_order"), idx * 10),
                _int_value(row.get("pinned"), 0),
                row.get("notes"),
                now,
                now,
            ),
        )
    conn.commit()


def area_get(area_id, conn=None, owner_user_id=None):
    if not area_id:
        return None
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT owner_user_id, area_id, icon, tab, group_name, area_name, "
        "is_header, is_system, status, tags, "
        "sort_order, pinned, notes, created_utc, updated_utc "
        "FROM lp_areas WHERE area_id = ? AND owner_user_id IS ?",
        (area_id, owner_user_id),
    ).fetchone()
    return dict(row) if row else None


def area_upsert(area, conn=None, owner_user_id=None):
    if not area:
        raise ValueError("Missing area data.")
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(area.get("owner_user_id", owner_user_id))
    area_id = (area.get("area_id") or "").strip()
    if not area_id:
        raise ValueError("area_id is required.")
    tab = (area.get("tab") or "").strip()
    group_name = (area.get("group_name") or "").strip()
    area_name = (area.get("area_name") or "").strip()
    if not tab or not group_name or not area_name:
        raise ValueError("tab, group_name, and area_name are required.")
    icon = area.get("icon") or ""
    is_header = int(area.get("is_header") or 0)
    is_system = int(area.get("is_system") or 0)
    status = (area.get("status") or "active").strip()
    tags = area.get("tags")
    sort_order = _int_value(area.get("sort_order"), 100)
    pinned = _int_value(area.get("pinned"), 0)
    notes = area.get("notes")
    now = _utc_now()
    existing = area_get(area_id, conn=conn, owner_user_id=owner_user_id)
    if existing:
        conn.execute(
            "UPDATE lp_areas SET icon = ?, tab = ?, group_name = ?, area_name = ?, "
            "is_header = ?, is_system = ?, status = ?, tags = ?, sort_order = ?, pinned = ?, notes = ?, "
            "updated_utc = ? WHERE area_id = ? AND owner_user_id IS ?",
            (
                icon,
                tab,
                group_name,
                area_name,
                is_header,
                is_system,
                status,
                tags,
                sort_order,
                pinned,
                notes,
                now,
                area_id,
                owner_user_id,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO lp_areas "
            "(owner_user_id, area_id, icon, tab, group_name, area_name, is_header, is_system, status, tags, sort_order, "
            "pinned, notes, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                area_id,
                icon,
                tab,
                group_name,
                area_name,
                is_header,
                is_system,
                status,
                tags,
                sort_order,
                pinned,
                notes,
                now,
                now,
            ),
        )
    conn.commit()
    return area_id


def area_set_status(area_id, status, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    conn.execute(
        "UPDATE lp_areas SET status = ?, updated_utc = ? WHERE area_id = ? AND owner_user_id IS ?",
        ((status or "active").strip(), _utc_now(), area_id, owner_user_id),
    )
    conn.commit()


def area_folders_list(area_id, include_disabled=False, conn=None, owner_user_id=None):
    if not area_id:
        return []
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_condition, owner_params = _owner_condition("owner_user_id", owner_user_id)
    params = owner_params + [area_id]
    condition = f"{owner_condition} AND area_id = ?"
    if not include_disabled:
        condition += " AND is_enabled = 1"
    sql = (
        "SELECT area_folder_id, owner_user_id, area_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, "
        "created_utc, updated_utc "
        f"FROM lp_area_folders WHERE {condition} "
        "ORDER BY CASE folder_role "
        "WHEN 'default' THEN 0 "
        "WHEN 'include' THEN 1 "
        "WHEN 'output' THEN 2 "
        "WHEN 'archive' THEN 3 "
        "ELSE 9 END, sort_order, path_prefix"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def area_folder_add(
    area_id,
    path_prefix,
    folder_role="include",
    create_type="none",
    is_write_enabled=0,
    confidence=1.0,
    tags=None,
    notes=None,
    sort_order=100,
    is_enabled=1,
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    if not area_id:
        raise ValueError("area_id is required.")
    owner_user_id = _owner_user_id(owner_user_id)
    normalized = normalize_path_prefix(path_prefix)
    now = _utc_now()
    wants_default = folder_role == "default"
    insert_role = "include" if wants_default else folder_role
    insert_write = 0 if wants_default else int(is_write_enabled)
    existing = conn.execute(
        "SELECT area_folder_id FROM lp_area_folders "
        "WHERE owner_user_id IS ? AND area_id = ? AND path_prefix = ?",
        (owner_user_id, area_id, normalized),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE lp_area_folders SET folder_role = ?, create_type = ?, "
            "is_write_enabled = ?, confidence = ?, tags = ?, notes = ?, sort_order = ?, "
            "is_enabled = ?, updated_utc = ? WHERE area_folder_id = ?",
            (
                insert_role,
                create_type,
                insert_write,
                float(confidence),
                tags,
                notes,
                int(sort_order),
                int(is_enabled),
                now,
                existing["area_folder_id"],
            ),
        )
        folder_id = existing["area_folder_id"]
    else:
        try:
            conn.execute(
                "INSERT INTO lp_area_folders "
                "(owner_user_id, area_id, path_prefix, folder_role, create_type, is_write_enabled, "
                "confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_user_id,
                    area_id,
                    normalized,
                    insert_role,
                    create_type,
                    insert_write,
                    float(confidence),
                    tags,
                    notes,
                    int(sort_order),
                    int(is_enabled),
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError:
            conn.execute(
                "UPDATE lp_area_folders SET folder_role = ?, create_type = ?, "
                "is_write_enabled = ?, confidence = ?, tags = ?, notes = ?, sort_order = ?, "
                "is_enabled = ?, updated_utc = ? WHERE owner_user_id IS ? AND area_id = ? AND path_prefix = ?",
                (
                    insert_role,
                    create_type,
                    insert_write,
                    float(confidence),
                    tags,
                    notes,
                    int(sort_order),
                    int(is_enabled),
                    now,
                    owner_user_id,
                    area_id,
                    normalized,
                ),
            )
        row = conn.execute(
            "SELECT area_folder_id FROM lp_area_folders "
            "WHERE owner_user_id IS ? AND area_id = ? AND path_prefix = ?",
            (owner_user_id, area_id, normalized),
        ).fetchone()
        folder_id = row["area_folder_id"] if row else None
    conn.commit()
    if wants_default and folder_id:
        area_folder_set_default(area_id, folder_id, conn=conn, owner_user_id=owner_user_id)
    return folder_id


def area_folder_set_default(area_id, area_folder_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    selected = conn.execute(
        "SELECT area_folder_id FROM lp_area_folders "
        "WHERE area_folder_id = ? AND owner_user_id IS ? AND area_id = ?",
        (area_folder_id, owner_user_id, area_id),
    ).fetchone()
    if not selected:
        return False
    now = _utc_now()
    conn.execute("BEGIN")
    conn.execute(
        "UPDATE lp_area_folders SET folder_role = 'include', is_write_enabled = 0, updated_utc = ? "
        "WHERE owner_user_id IS ? AND area_id = ? AND folder_role = 'default'",
        (now, owner_user_id, area_id),
    )
    conn.execute(
        "UPDATE lp_area_folders SET folder_role = 'default', is_write_enabled = 1, "
        "is_enabled = 1, updated_utc = ? "
        "WHERE area_folder_id = ? AND owner_user_id IS ? AND area_id = ?",
        (now, area_folder_id, owner_user_id, area_id),
    )
    conn.commit()
    return True


def area_folder_disable(area_folder_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    conn.execute(
        "UPDATE lp_area_folders SET is_enabled = 0, is_write_enabled = 0, updated_utc = ? "
        "WHERE area_folder_id = ? AND owner_user_id IS ?",
        (_utc_now(), area_folder_id, owner_user_id),
    )
    conn.commit()


def area_folder_enable(area_folder_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    folder = area_folder_get(area_folder_id, conn=conn, owner_user_id=owner_user_id)
    if not folder:
        return
    if folder.get("folder_role") == "default":
        area_folder_set_default(
            folder["area_id"],
            area_folder_id,
            conn=conn,
            owner_user_id=folder.get("owner_user_id"),
        )
        return
    conn.execute(
        "UPDATE lp_area_folders SET is_enabled = 1, updated_utc = ? "
        "WHERE area_folder_id = ? AND owner_user_id IS ?",
        (_utc_now(), area_folder_id, owner_user_id),
    )
    conn.commit()


def area_folder_remove(area_folder_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    conn.execute(
        "DELETE FROM lp_area_folders WHERE area_folder_id = ? AND owner_user_id IS ?",
        (area_folder_id, owner_user_id),
    )
    conn.commit()


def area_folder_get(area_folder_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT area_folder_id, owner_user_id, area_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc "
        "FROM lp_area_folders WHERE area_folder_id = ? AND owner_user_id IS ?",
        (area_folder_id, owner_user_id),
    ).fetchone()
    return dict(row) if row else None


def area_default_folder_get(area_id, conn=None, owner_user_id=None):
    if not area_id:
        return None
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT path_prefix FROM lp_area_folders "
        "WHERE owner_user_id IS ? AND area_id = ? AND folder_role = 'default' AND is_enabled = 1",
        (owner_user_id, area_id),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise ValueError("Multiple default folders found.")
    return rows[0]["path_prefix"]


def area_folder_scope(area_id, conn=None, owner_user_id=None):
    if not area_id:
        return []
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT area_folder_id, owner_user_id, area_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc "
        "FROM lp_area_folders "
        "WHERE owner_user_id IS ? AND area_id = ? AND is_enabled = 1 "
        "AND folder_role IN ('default','include','archive','output') "
        "ORDER BY CASE folder_role WHEN 'default' THEN 0 WHEN 'include' THEN 1 "
        "WHEN 'output' THEN 2 WHEN 'archive' THEN 3 ELSE 9 END, sort_order, path_prefix",
        (owner_user_id, area_id),
    ).fetchall()
    return [dict(row) for row in rows]


def diagnose_areas(conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    issues = {
        "missing_default": [],
        "disabled_default": [],
        "multiple_default": [],
    }
    rows = conn.execute(
        "SELECT area_id, area_name FROM lp_areas WHERE owner_user_id IS ? AND status = 'active'",
        (owner_user_id,),
    ).fetchall()
    for row in rows:
        area_id = row["area_id"]
        defaults = conn.execute(
            "SELECT area_folder_id, is_enabled FROM lp_area_folders "
            "WHERE owner_user_id IS ? AND area_id = ? AND folder_role = 'default'",
            (owner_user_id, area_id),
        ).fetchall()
        if not defaults:
            issues["missing_default"].append(area_id)
            continue
        enabled = [d for d in defaults if int(d["is_enabled"] or 0) == 1]
        if not enabled:
            issues["disabled_default"].append(area_id)
        if len(enabled) > 1:
            issues["multiple_default"].append(area_id)
    return issues


def assign_defaults_if_missing(conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT area_id FROM lp_areas WHERE owner_user_id IS ? AND status = 'active'",
        (owner_user_id,),
    ).fetchall()
    updated = 0
    for row in rows:
        area_id = row["area_id"]
        defaults = conn.execute(
            "SELECT area_folder_id FROM lp_area_folders "
            "WHERE owner_user_id IS ? AND area_id = ? AND folder_role = 'default' AND is_enabled = 1",
            (owner_user_id, area_id),
        ).fetchall()
        if defaults:
            continue
        candidate = conn.execute(
            "SELECT area_folder_id FROM lp_area_folders "
            "WHERE owner_user_id IS ? AND area_id = ? AND is_enabled = 1 "
            "ORDER BY sort_order, path_prefix LIMIT 1",
            (owner_user_id, area_id),
        ).fetchone()
        if candidate:
            area_folder_set_default(
                area_id,
                candidate["area_folder_id"],
                conn=conn,
                owner_user_id=owner_user_id,
            )
            updated += 1
    return updated


def import_area_mappings_csv(
    csv_path,
    *,
    default_flag_columns=None,
    conn=None,
    owner_user_id=None,
):
    import csv

    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    default_flag_columns = default_flag_columns or ["is_default", "default", "folder_role"]

    def _slug(value):
        text = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or ""))
        text = "-".join([seg for seg in text.split("-") if seg])
        return text or "unnamed"

    def _build_side_tab_map():
        mapping = {}
        current_group = ""

        def _is_group_header(entry_id, label):
            if not entry_id:
                return False
            if entry_id.lower() == "spacer":
                return True
            if "/" in entry_id:
                return False
            if entry_id.lower() in ("all", "any", "unmapped"):
                return False
            return bool(label) and label.upper() == label

        for entry in cfg.SIDE_TABS:
            if isinstance(entry, dict):
                entry_id = (entry.get("id") or "").strip()
                label = (entry.get("label") or "").strip()
                if _is_group_header(entry_id, label):
                    current_group = label or current_group
                    continue
                if not entry_id:
                    continue
                if entry_id.lower() in ("all", "any", "unmapped"):
                    continue
                key = entry_id.lower()
                mapping[key] = {
                    "area_id": entry_id,
                    "tab": current_group or entry_id.split("/")[0].upper(),
                    "group_name": current_group or entry_id.split("/")[0].upper(),
                    "area_name": label or entry_id,
                }
            elif isinstance(entry, str):
                entry_id = entry.strip()
                if not entry_id:
                    continue
                key = entry_id.lower()
                mapping[key] = {
                    "area_id": entry_id,
                    "tab": current_group or entry_id.split("/")[0].upper(),
                    "group_name": current_group or entry_id.split("/")[0].upper(),
                    "area_name": entry_id,
                }
        return mapping

    side_tab_map = _build_side_tab_map()

    def _pretty_name(value):
        text = (value or "").strip()
        if not text:
            return ""
        if "/" in text or ">" in text:
            for sep in [">", "/"]:
                text = text.replace(sep, " ")
        text = " ".join([seg for seg in text.replace("_", " ").replace("-", " ").split() if seg])
        return text.title() if text else ""

    def _fallback_group_area(tab_value):
        raw = (tab_value or "").strip()
        if not raw:
            return "", ""
        if ">" in raw:
            parts = [p.strip() for p in raw.split(">") if p.strip()]
        elif "/" in raw:
            parts = [p.strip() for p in raw.split("/") if p.strip()]
        else:
            parts = [raw]
        tab_key = parts[0].lower() if parts else raw.lower()
        tab_label = {"area": "AREAS"}.get(tab_key, parts[0].upper() if parts else raw.upper())
        if len(parts) >= 2:
            group_name = _pretty_name(parts[1])
        else:
            group_name = _pretty_name(tab_label) or tab_label
        area_name = _pretty_name(parts[-1]) if parts else group_name
        return tab_label, group_name, area_name

    def _derive_area_id(tab, group_name, area_name):
        return ".".join([_slug(tab), _slug(group_name), _slug(area_name)])

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            area_id = None
            tab = (row.get("tab") or "").strip()
            group_name = (row.get("group") or row.get("grp") or "").strip()
            area_name = (row.get("area") or "").strip()
            if not tab:
                continue
            tab_key = tab.lower()
            if tab_key in side_tab_map:
                mapped = side_tab_map[tab_key]
                area_id = mapped["area_id"]
                tab = mapped["tab"]
                group_name = mapped["group_name"]
                area_name = mapped["area_name"]
            elif not group_name or not area_name:
                fallback_tab, fallback_group, fallback_area = _fallback_group_area(tab)
                if not group_name:
                    group_name = fallback_group
                if not area_name:
                    area_name = fallback_area
                tab = fallback_tab or tab
            if not group_name or not area_name:
                continue
            if not area_id:
                area_id = _derive_area_id(tab, group_name, area_name)
            area_upsert(
                {
                    "area_id": area_id,
                    "tab": tab,
                    "group_name": group_name,
                    "area_name": area_name,
                    "status": "active",
                    "tags": row.get("tags"),
                    "notes": row.get("notes"),
                },
                conn=conn,
                owner_user_id=owner_user_id,
            )
            path_prefix = row.get("path_prefix") or ""
            folder_role = "include"
            is_write_enabled = 0
            for col in default_flag_columns:
                value = (row.get(col) or "").strip().lower()
                if value in ("1", "true", "yes", "default"):
                    folder_role = "default"
                    is_write_enabled = 1
                    break
                if col == "folder_role" and value in ("default", "include", "archive", "output"):
                    folder_role = value
                    is_write_enabled = 1 if value == "default" else 0
            area_folder_add(
                area_id,
                path_prefix,
                folder_role=folder_role,
                is_write_enabled=is_write_enabled,
                confidence=float(row.get("confidence") or 1.0),
                tags=row.get("tags"),
                notes=row.get("notes"),
                conn=conn,
                owner_user_id=owner_user_id,
            )


def ensure_default_area_folders_for_user(owner_user_id, username=None, conn=None, create_dirs=True):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    if owner_user_id is None:
        return 0
    paths = user_paths.get_or_create_user_paths(
        conn,
        owner_user_id,
        username=username,
        create_dirs=create_dirs,
    )
    notes_root = user_paths.normalize_path(paths.get("notes_root_path") or "")
    if not notes_root:
        return 0
    if create_dirs:
        for key in ("file_root_path", "notes_root_path", "areas_root_path", "lists_root_path"):
            path_value = paths.get(key)
            if path_value:
                os.makedirs(path_value, exist_ok=True)
    rows = areas_list_sidebar(conn=conn, owner_user_id=owner_user_id)
    created = 0
    for row in rows:
        if int(row.get("is_header") or 0) or int(row.get("is_system") or 0):
            continue
        area_id = row.get("area_id") or ""
        if not area_id:
            continue
        if area_default_folder_get(area_id, conn=conn, owner_user_id=owner_user_id):
            continue
        folder_name = user_paths.safe_area_folder_name(area_id, row.get("area_name") or "")
        folder_path = user_paths.normalize_path(os.path.join(notes_root, folder_name))
        if create_dirs:
            os.makedirs(folder_path, exist_ok=True)
        area_folder_add(
            area_id,
            folder_path,
            folder_role="default",
            create_type="markdown",
            is_write_enabled=1,
            tags="user_default",
            notes="Default per-user notes folder",
            conn=conn,
            owner_user_id=owner_user_id,
        )
        created += 1
    return created


def ensure_default_area_folder_for_area(
    area_id,
    area_name="",
    owner_user_id=None,
    username=None,
    conn=None,
    create_dirs=True,
):
    conn = _get_conn(conn)
    ensure_areas_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if owner_user_id is None:
        raise ValueError("A logged-in user is required.")
    area_id = (area_id or "").strip()
    if not area_id:
        return 0
    row = area_get(area_id, conn=conn, owner_user_id=owner_user_id)
    if not row:
        return 0
    if int(row.get("is_header") or 0) or int(row.get("is_system") or 0):
        return 0
    if area_default_folder_get(area_id, conn=conn, owner_user_id=owner_user_id):
        return 0

    paths = user_paths.get_or_create_user_paths(
        conn,
        owner_user_id,
        username=username,
        create_dirs=create_dirs,
    )
    notes_root = user_paths.normalize_path(paths.get("notes_root_path") or "")
    if not notes_root:
        return 0
    if create_dirs:
        for key in ("file_root_path", "notes_root_path", "areas_root_path", "lists_root_path"):
            path_value = paths.get(key)
            if path_value:
                os.makedirs(path_value, exist_ok=True)
    folder_name = user_paths.safe_area_folder_name(area_id, area_name or row.get("area_name") or "")
    folder_path = user_paths.normalize_path(os.path.join(notes_root, folder_name))
    if create_dirs:
        os.makedirs(folder_path, exist_ok=True)
    folder_id = area_folder_add(
        area_id,
        folder_path,
        folder_role="default",
        create_type="markdown",
        is_write_enabled=1,
        tags="user_default",
        notes="Default per-user notes folder",
        conn=conn,
        owner_user_id=owner_user_id,
    )
    return 1 if folder_id else 0
