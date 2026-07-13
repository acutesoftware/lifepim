import os
import sqlite3
from datetime import datetime, timezone

from common import data as db
from common import config as cfg

PROJECTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lp_projects (
    owner_user_id   INTEGER,
    project_id      TEXT NOT NULL,
    icon            TEXT,
    tab             TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    project_name    TEXT NOT NULL,
    is_header       INTEGER NOT NULL DEFAULT 0,
    is_system       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    tags            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    pinned          INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_utc     TEXT NOT NULL,
    updated_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_lp_projects_tab_group
ON lp_projects (owner_user_id, tab, group_name, sort_order, project_name);

CREATE INDEX IF NOT EXISTS idx_lp_projects_status
ON lp_projects (owner_user_id, status);

CREATE TABLE IF NOT EXISTS lp_project_folders (
    project_folder_id    INTEGER PRIMARY KEY,
    project_id           TEXT NOT NULL,
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
    UNIQUE (project_id, path_prefix)
);

CREATE INDEX IF NOT EXISTS idx_lp_project_folders_project
ON lp_project_folders (project_id, folder_role, sort_order);

CREATE INDEX IF NOT EXISTS idx_lp_project_folders_path
ON lp_project_folders (path_prefix);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lp_project_default_folder
ON lp_project_folders (project_id)
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


def ensure_projects_schema(conn=None):
    conn = _get_conn(conn)
    _migrate_projects_schema(conn)
    conn.executescript(PROJECTS_SCHEMA)
    conn.commit()


def _table_columns(conn, table_name):
    try:
        return [dict(row) for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    except Exception:
        return []


def _migrate_projects_schema(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lp_projects'"
    ).fetchone()
    if not exists:
        return
    columns = _table_columns(conn, "lp_projects")
    column_names = {row["name"] for row in columns}
    project_id_is_pk = any(row["name"] == "project_id" and int(row.get("pk") or 0) for row in columns)
    required = {"owner_user_id", "icon", "is_header", "is_system"}
    if required.issubset(column_names) and not project_id_is_pk:
        return
    conn.execute("ALTER TABLE lp_projects RENAME TO lp_projects_legacy")
    conn.executescript(PROJECTS_SCHEMA)
    legacy_cols = {row["name"] for row in _table_columns(conn, "lp_projects_legacy")}
    select_expr = {
        "owner_user_id": "owner_user_id" if "owner_user_id" in legacy_cols else "NULL",
        "project_id": "project_id",
        "icon": "icon" if "icon" in legacy_cols else "''",
        "tab": "tab",
        "group_name": "group_name",
        "project_name": "project_name",
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
        f"INSERT OR IGNORE INTO lp_projects ({insert_cols}) SELECT {select_cols} FROM lp_projects_legacy"
    )
    conn.execute("DROP TABLE lp_projects_legacy")
    conn.commit()


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


def projects_list_sidebar(status="active", conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    params = [_owner_user_id(owner_user_id)]
    condition = "owner_user_id IS ? AND is_header = 0 AND is_system = 0"
    if status:
        condition += " AND status = ?"
        params.append(status)
    sql = (
        "SELECT owner_user_id, project_id, icon, tab, group_name, project_name, "
        "is_header, is_system, status, tags, "
        "sort_order, pinned, notes, created_utc, updated_utc "
        "FROM lp_projects "
        f"WHERE {condition} "
        "ORDER BY tab, group_name, pinned DESC, sort_order, project_name"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def projects_sidebar_tree(status="active", conn=None, owner_user_id=None):
    rows = projects_list_sidebar(status=status, conn=conn, owner_user_id=owner_user_id)
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
            group_entry = {"group_name": group_name, "projects": []}
            groups[group_name] = group_entry
        group_entry["projects"].append(row)
    ordered = []
    for tab in sorted(tabs.keys()):
        tab_entry = tabs[tab]
        groups = []
        for group_name in sorted(tab_entry["groups"].keys()):
            group_entry = tab_entry["groups"][group_name]
            groups.append(group_entry)
        ordered.append({"tab": tab, "groups": groups})
    return ordered


def _default_sidebar_rows(owner_user_id=None):
    rows = []
    current_group = "Projects"
    for idx, entry in enumerate(cfg.SIDE_TABS):
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
            project_id = entry_id if lower_id != "spacer" else f"header-{idx}"
            tab = label
            project_name = label
        else:
            project_id = entry_id
            tab = current_group
            project_name = label
        rows.append(
            {
                "owner_user_id": owner_user_id,
                "project_id": project_id,
                "icon": icon,
                "tab": tab,
                "group_name": current_group,
                "project_name": project_name,
                "is_header": is_header,
                "is_system": is_system,
                "status": "active",
                "sort_order": idx * 10,
            }
        )
    return rows


def _sidebar_looks_like_flat_legacy(conn, owner_user_id):
    row = conn.execute(
        """
        SELECT COUNT(1) AS cnt,
               SUM(CASE WHEN COALESCE(icon, '') != '' THEN 1 ELSE 0 END) AS icon_count,
               SUM(CASE WHEN COALESCE(is_header, 0) = 1 THEN 1 ELSE 0 END) AS header_count,
               SUM(CASE WHEN COALESCE(is_system, 0) = 1 THEN 1 ELSE 0 END) AS system_count,
               COUNT(DISTINCT sort_order) AS sort_count
        FROM lp_projects
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


def seed_default_projects_for_user(owner_user_id=None, conn=None, replace=False):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    existing = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_projects WHERE owner_user_id IS ?",
        (owner_user_id,),
    ).fetchone()
    if existing and int(existing["cnt"] or 0) and not replace:
        if _sidebar_looks_like_flat_legacy(conn, owner_user_id):
            replace = True
        else:
            return 0
    legacy = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_projects WHERE owner_user_id IS NULL"
    ).fetchone()
    if (
        not replace
        and owner_user_id is not None
        and legacy
        and int(legacy["cnt"] or 0)
        and _current_username().lower() == "duncan"
    ):
        if _sidebar_looks_like_flat_legacy(conn, None):
            conn.execute("DELETE FROM lp_projects WHERE owner_user_id IS NULL")
            conn.commit()
            replace = True
        else:
            conn.execute("UPDATE lp_projects SET owner_user_id = ? WHERE owner_user_id IS NULL", (owner_user_id,))
            conn.commit()
            return int(legacy["cnt"] or 0)
    if existing and int(existing["cnt"] or 0) and not replace:
        return 0
    if replace:
        conn.execute("DELETE FROM lp_projects WHERE owner_user_id IS ?", (owner_user_id,))
        conn.commit()
    count = 0
    for row in _default_sidebar_rows(owner_user_id):
        project_upsert(row, conn=conn, owner_user_id=owner_user_id)
        count += 1
    return count


def projects_side_tabs(owner_user_id=None, conn=None, seed=True):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if owner_user_id is None:
        return list(cfg.SIDE_TABS)
    if seed:
        seed_default_projects_for_user(owner_user_id, conn=conn, replace=False)
    rows = conn.execute(
        "SELECT project_id, icon, group_name, project_name, is_header, is_system, status, sort_order "
        "FROM lp_projects WHERE owner_user_id IS ? AND status = 'active' "
        "ORDER BY sort_order, project_name",
        (owner_user_id,),
    ).fetchall()
    side_tabs = []
    for row in rows:
        side_tabs.append(
            {
                "icon": row["icon"] or "",
                "id": row["project_id"],
                "proj": "" if str(row["project_id"]).startswith("header-") else row["project_id"],
                "label": row["project_name"],
                "group_name": row["group_name"],
                "is_header": int(row["is_header"] or 0),
                "is_system": int(row["is_system"] or 0),
            }
        )
    return side_tabs or list(cfg.SIDE_TABS)


def save_user_sidebar_rows(rows, owner_user_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if owner_user_id is None:
        raise ValueError("A logged-in user is required.")
    now = _utc_now()
    conn.execute("DELETE FROM lp_projects WHERE owner_user_id IS ?", (owner_user_id,))
    for idx, row in enumerate(rows):
        project_id = (row.get("project_id") or "").strip()
        project_name = (row.get("project_name") or "").strip()
        if not project_id or not project_name:
            continue
        is_header = int(row.get("is_header") or 0)
        is_system = int(row.get("is_system") or 0)
        group_name = (row.get("group_name") or "").strip()
        if is_header:
            group_name = project_name
        if not group_name:
            group_name = "Projects"
        tab = group_name
        conn.execute(
            "INSERT INTO lp_projects "
            "(owner_user_id, project_id, icon, tab, group_name, project_name, is_header, is_system, "
            "status, tags, sort_order, pinned, notes, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                project_id,
                row.get("icon") or "",
                tab,
                group_name,
                project_name,
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


def project_get(project_id, conn=None, owner_user_id=None):
    if not project_id:
        return None
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT owner_user_id, project_id, icon, tab, group_name, project_name, "
        "is_header, is_system, status, tags, "
        "sort_order, pinned, notes, created_utc, updated_utc "
        "FROM lp_projects WHERE project_id = ? AND owner_user_id IS ?",
        (project_id, owner_user_id),
    ).fetchone()
    return dict(row) if row else None


def project_upsert(project, conn=None, owner_user_id=None):
    if not project:
        raise ValueError("Missing project data.")
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(project.get("owner_user_id", owner_user_id))
    project_id = (project.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required.")
    tab = (project.get("tab") or "").strip()
    group_name = (project.get("group_name") or "").strip()
    project_name = (project.get("project_name") or "").strip()
    if not tab or not group_name or not project_name:
        raise ValueError("tab, group_name, and project_name are required.")
    icon = project.get("icon") or ""
    is_header = int(project.get("is_header") or 0)
    is_system = int(project.get("is_system") or 0)
    status = (project.get("status") or "active").strip()
    tags = project.get("tags")
    sort_order = _int_value(project.get("sort_order"), 100)
    pinned = _int_value(project.get("pinned"), 0)
    notes = project.get("notes")
    now = _utc_now()
    existing = project_get(project_id, conn=conn, owner_user_id=owner_user_id)
    if existing:
        conn.execute(
            "UPDATE lp_projects SET icon = ?, tab = ?, group_name = ?, project_name = ?, "
            "is_header = ?, is_system = ?, status = ?, tags = ?, sort_order = ?, pinned = ?, notes = ?, "
            "updated_utc = ? WHERE project_id = ? AND owner_user_id IS ?",
            (
                icon,
                tab,
                group_name,
                project_name,
                is_header,
                is_system,
                status,
                tags,
                sort_order,
                pinned,
                notes,
                now,
                project_id,
                owner_user_id,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO lp_projects "
            "(owner_user_id, project_id, icon, tab, group_name, project_name, is_header, is_system, status, tags, sort_order, "
            "pinned, notes, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                project_id,
                icon,
                tab,
                group_name,
                project_name,
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
    return project_id


def project_set_status(project_id, status, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    conn.execute(
        "UPDATE lp_projects SET status = ?, updated_utc = ? WHERE project_id = ? AND owner_user_id IS ?",
        ((status or "active").strip(), _utc_now(), project_id, owner_user_id),
    )
    conn.commit()


def project_folders_list(project_id, include_disabled=False, conn=None):
    if not project_id:
        return []
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    params = [project_id]
    condition = "project_id = ?"
    if not include_disabled:
        condition += " AND is_enabled = 1"
    sql = (
        "SELECT project_folder_id, project_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, "
        "created_utc, updated_utc "
        f"FROM lp_project_folders WHERE {condition} "
        "ORDER BY CASE folder_role "
        "WHEN 'default' THEN 0 "
        "WHEN 'include' THEN 1 "
        "WHEN 'output' THEN 2 "
        "WHEN 'archive' THEN 3 "
        "ELSE 9 END, sort_order, path_prefix"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def project_folder_add(
    project_id,
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
):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    if not project_id:
        raise ValueError("project_id is required.")
    normalized = normalize_path_prefix(path_prefix)
    now = _utc_now()
    wants_default = folder_role == "default"
    insert_role = "include" if wants_default else folder_role
    insert_write = 0 if wants_default else int(is_write_enabled)
    try:
        conn.execute(
            "INSERT INTO lp_project_folders "
            "(project_id, path_prefix, folder_role, create_type, is_write_enabled, "
            "confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
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
            "UPDATE lp_project_folders SET folder_role = ?, create_type = ?, "
            "is_write_enabled = ?, confidence = ?, tags = ?, notes = ?, sort_order = ?, "
            "is_enabled = ?, updated_utc = ? WHERE project_id = ? AND path_prefix = ?",
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
                project_id,
                normalized,
            ),
        )
    conn.commit()
    row = conn.execute(
        "SELECT project_folder_id FROM lp_project_folders WHERE project_id = ? AND path_prefix = ?",
        (project_id, normalized),
    ).fetchone()
    folder_id = row["project_folder_id"] if row else None
    if wants_default and folder_id:
        project_folder_set_default(project_id, folder_id, conn=conn)
    return folder_id


def project_folder_set_default(project_id, project_folder_id, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    now = _utc_now()
    conn.execute("BEGIN")
    conn.execute(
        "UPDATE lp_project_folders SET folder_role = 'include', is_write_enabled = 0, updated_utc = ? "
        "WHERE project_id = ? AND folder_role = 'default'",
        (now, project_id),
    )
    conn.execute(
        "UPDATE lp_project_folders SET folder_role = 'default', is_write_enabled = 1, "
        "is_enabled = 1, updated_utc = ? WHERE project_folder_id = ? AND project_id = ?",
        (now, project_folder_id, project_id),
    )
    conn.commit()


def project_folder_disable(project_folder_id, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    conn.execute(
        "UPDATE lp_project_folders SET is_enabled = 0, is_write_enabled = 0, updated_utc = ? "
        "WHERE project_folder_id = ?",
        (_utc_now(), project_folder_id),
    )
    conn.commit()


def project_folder_enable(project_folder_id, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    folder = project_folder_get(project_folder_id, conn=conn)
    if not folder:
        return
    if folder.get("folder_role") == "default":
        project_folder_set_default(folder["project_id"], project_folder_id, conn=conn)
        return
    conn.execute(
        "UPDATE lp_project_folders SET is_enabled = 1, updated_utc = ? "
        "WHERE project_folder_id = ?",
        (_utc_now(), project_folder_id),
    )
    conn.commit()


def project_folder_remove(project_folder_id, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    conn.execute("DELETE FROM lp_project_folders WHERE project_folder_id = ?", (project_folder_id,))
    conn.commit()


def project_folder_get(project_folder_id, conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    row = conn.execute(
        "SELECT project_folder_id, project_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc "
        "FROM lp_project_folders WHERE project_folder_id = ?",
        (project_folder_id,),
    ).fetchone()
    return dict(row) if row else None


def project_default_folder_get(project_id, conn=None):
    if not project_id:
        return None
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    rows = conn.execute(
        "SELECT path_prefix FROM lp_project_folders "
        "WHERE project_id = ? AND folder_role = 'default' AND is_enabled = 1",
        (project_id,),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise ValueError("Multiple default folders found.")
    return rows[0]["path_prefix"]


def project_folder_scope(project_id, conn=None):
    if not project_id:
        return []
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    rows = conn.execute(
        "SELECT project_folder_id, project_id, path_prefix, folder_role, create_type, "
        "is_write_enabled, confidence, tags, notes, sort_order, is_enabled, created_utc, updated_utc "
        "FROM lp_project_folders "
        "WHERE project_id = ? AND is_enabled = 1 "
        "AND folder_role IN ('default','include','archive','output') "
        "ORDER BY CASE folder_role WHEN 'default' THEN 0 WHEN 'include' THEN 1 "
        "WHEN 'output' THEN 2 WHEN 'archive' THEN 3 ELSE 9 END, sort_order, path_prefix",
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def diagnose_projects(conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    issues = {
        "missing_default": [],
        "disabled_default": [],
        "multiple_default": [],
    }
    rows = conn.execute(
        "SELECT project_id, project_name FROM lp_projects WHERE status = 'active'"
    ).fetchall()
    for row in rows:
        project_id = row["project_id"]
        defaults = conn.execute(
            "SELECT project_folder_id, is_enabled FROM lp_project_folders "
            "WHERE project_id = ? AND folder_role = 'default'",
            (project_id,),
        ).fetchall()
        if not defaults:
            issues["missing_default"].append(project_id)
            continue
        enabled = [d for d in defaults if int(d["is_enabled"] or 0) == 1]
        if not enabled:
            issues["disabled_default"].append(project_id)
        if len(enabled) > 1:
            issues["multiple_default"].append(project_id)
    return issues


def assign_defaults_if_missing(conn=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    rows = conn.execute(
        "SELECT project_id FROM lp_projects WHERE status = 'active'"
    ).fetchall()
    updated = 0
    for row in rows:
        project_id = row["project_id"]
        defaults = conn.execute(
            "SELECT project_folder_id FROM lp_project_folders "
            "WHERE project_id = ? AND folder_role = 'default' AND is_enabled = 1",
            (project_id,),
        ).fetchall()
        if defaults:
            continue
        candidate = conn.execute(
            "SELECT project_folder_id FROM lp_project_folders "
            "WHERE project_id = ? AND is_enabled = 1 "
            "ORDER BY sort_order, path_prefix LIMIT 1",
            (project_id,),
        ).fetchone()
        if candidate:
            project_folder_set_default(project_id, candidate["project_folder_id"], conn=conn)
            updated += 1
    return updated


def import_project_mappings_csv(
    csv_path,
    *,
    default_flag_columns=None,
    conn=None,
):
    import csv

    conn = _get_conn(conn)
    ensure_projects_schema(conn)
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
                    "project_id": entry_id,
                    "tab": current_group or entry_id.split("/")[0].upper(),
                    "group_name": current_group or entry_id.split("/")[0].upper(),
                    "project_name": label or entry_id,
                }
            elif isinstance(entry, str):
                entry_id = entry.strip()
                if not entry_id:
                    continue
                key = entry_id.lower()
                mapping[key] = {
                    "project_id": entry_id,
                    "tab": current_group or entry_id.split("/")[0].upper(),
                    "group_name": current_group or entry_id.split("/")[0].upper(),
                    "project_name": entry_id,
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

    def _fallback_group_project(tab_value):
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
        tab_label = {"proj": "PROJECTS"}.get(tab_key, parts[0].upper() if parts else raw.upper())
        if len(parts) >= 2:
            group_name = _pretty_name(parts[1])
        else:
            group_name = _pretty_name(tab_label) or tab_label
        project_name = _pretty_name(parts[-1]) if parts else group_name
        return tab_label, group_name, project_name

    def _derive_project_id(tab, group_name, project_name):
        return ".".join([_slug(tab), _slug(group_name), _slug(project_name)])

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            project_id = None
            tab = (row.get("tab") or "").strip()
            group_name = (row.get("group") or row.get("grp") or "").strip()
            project_name = (row.get("project") or "").strip()
            if not tab:
                continue
            tab_key = tab.lower()
            if tab_key in side_tab_map:
                mapped = side_tab_map[tab_key]
                project_id = mapped["project_id"]
                tab = mapped["tab"]
                group_name = mapped["group_name"]
                project_name = mapped["project_name"]
            elif not group_name or not project_name:
                fallback_tab, fallback_group, fallback_project = _fallback_group_project(tab)
                if not group_name:
                    group_name = fallback_group
                if not project_name:
                    project_name = fallback_project
                tab = fallback_tab or tab
            if not group_name or not project_name:
                continue
            if not project_id:
                project_id = _derive_project_id(tab, group_name, project_name)
            project_upsert(
                {
                    "project_id": project_id,
                    "tab": tab,
                    "group_name": group_name,
                    "project_name": project_name,
                    "status": "active",
                    "tags": row.get("tags"),
                    "notes": row.get("notes"),
                },
                conn=conn,
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
            project_folder_add(
                project_id,
                path_prefix,
                folder_role=folder_role,
                is_write_enabled=is_write_enabled,
                confidence=float(row.get("confidence") or 1.0),
                tags=row.get("tags"),
                notes=row.get("notes"),
                conn=conn,
            )
