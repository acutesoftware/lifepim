import sqlite3
from datetime import datetime, timezone

from common import data as db
from common import areas as areas_mod
from common import utils as utils_mod


PROJECT_STATUSES = ("planned", "active", "completed", "archived", "cancelled")
PROJECT_STATUS_LABELS = {
    "planned": "Planned",
    "active": "Active",
    "completed": "Completed",
    "archived": "Archived",
    "cancelled": "Cancelled",
}

PROJECTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_project_workspaces (
    project_id        INTEGER PRIMARY KEY,
    owner_user_id     INTEGER,
    name              TEXT NOT NULL,
    project_type      TEXT,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'planned',
    start_date        TEXT,
    end_date          TEXT,
    parent_project_id INTEGER,
    icon              TEXT,
    comments          TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 100,
    pinned            INTEGER NOT NULL DEFAULT 0,
    created_utc       TEXT NOT NULL,
    updated_utc       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_project_workspaces_owner_status
ON lp_project_workspaces (owner_user_id, status, pinned, sort_order, name);

CREATE INDEX IF NOT EXISTS ix_lp_project_workspaces_parent
ON lp_project_workspaces (owner_user_id, parent_project_id);

CREATE TABLE IF NOT EXISTS lp_project_areas (
    project_area_id INTEGER PRIMARY KEY,
    owner_user_id   INTEGER,
    project_id      INTEGER NOT NULL,
    area_id         TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    created_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, project_id, area_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_project_areas_project
ON lp_project_areas (owner_user_id, project_id, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_project_areas_area
ON lp_project_areas (owner_user_id, area_id);

CREATE TABLE IF NOT EXISTS lp_project_items (
    project_item_id INTEGER PRIMARY KEY,
    owner_user_id   INTEGER,
    project_id      INTEGER NOT NULL,
    item_type       TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    item_title      TEXT,
    section         TEXT,
    pinned          INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    is_primary      INTEGER NOT NULL DEFAULT 0,
    created_utc     TEXT NOT NULL,
    updated_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, project_id, item_type, item_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_project_items_project
ON lp_project_items (owner_user_id, project_id, pinned, section, item_type, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_project_items_item
ON lp_project_items (owner_user_id, item_type, item_id, is_primary);
"""


_PROJECTS_SCHEMA_READY_CONN_IDS = set()


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_conn(conn=None):
    conn = db._get_conn() if conn is None else conn
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    return conn


def _current_owner_user_id():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "user_id", None)
    except Exception:
        pass
    return None


def _owner_user_id(owner_user_id=None):
    return _current_owner_user_id() if owner_user_id is None else owner_user_id


def _table_columns(conn, table_name):
    try:
        return {row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    except Exception:
        return set()


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def ensure_projects_schema(conn=None):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _PROJECTS_SCHEMA_READY_CONN_IDS and _projects_schema_is_current(conn):
        return
    conn.executescript(PROJECTS_SCHEMA_SQL)
    _migrate_projects_schema(conn)
    conn.commit()
    _PROJECTS_SCHEMA_READY_CONN_IDS.add(conn_id)


def _projects_schema_is_current(conn):
    return (
        {"project_id", "name", "status", "comments"}.issubset(_table_columns(conn, "lp_project_workspaces"))
        and {"project_id", "area_id"}.issubset(_table_columns(conn, "lp_project_areas"))
        and {"project_id", "item_type", "item_id", "is_primary"}.issubset(_table_columns(conn, "lp_project_items"))
    )


def _migrate_projects_schema(conn):
    if _table_exists(conn, "lp_project_workspaces"):
        cols = _table_columns(conn, "lp_project_workspaces")
        additions = {
            "owner_user_id": "INTEGER",
            "project_type": "TEXT",
            "description": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'planned'",
            "start_date": "TEXT",
            "end_date": "TEXT",
            "parent_project_id": "INTEGER",
            "icon": "TEXT",
            "comments": "TEXT",
            "sort_order": "INTEGER NOT NULL DEFAULT 100",
            "pinned": "INTEGER NOT NULL DEFAULT 0",
            "created_utc": "TEXT",
            "updated_utc": "TEXT",
        }
        for col_name, col_type in additions.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE lp_project_workspaces ADD COLUMN {col_name} {col_type}")
        now = _utc_now()
        conn.execute("UPDATE lp_project_workspaces SET status = 'planned' WHERE COALESCE(status, '') = ''")
        conn.execute("UPDATE lp_project_workspaces SET created_utc = ? WHERE COALESCE(created_utc, '') = ''", (now,))
        conn.execute("UPDATE lp_project_workspaces SET updated_utc = ? WHERE COALESCE(updated_utc, '') = ''", (now,))
    if _table_exists(conn, "lp_project_items"):
        cols = _table_columns(conn, "lp_project_items")
        additions = {
            "owner_user_id": "INTEGER",
            "item_title": "TEXT",
            "section": "TEXT",
            "pinned": "INTEGER NOT NULL DEFAULT 0",
            "sort_order": "INTEGER NOT NULL DEFAULT 100",
            "is_primary": "INTEGER NOT NULL DEFAULT 0",
            "created_utc": "TEXT",
            "updated_utc": "TEXT",
        }
        for col_name, col_type in additions.items():
            if col_name not in cols:
                conn.execute(f"ALTER TABLE lp_project_items ADD COLUMN {col_name} {col_type}")
        now = _utc_now()
        conn.execute("UPDATE lp_project_items SET created_utc = ? WHERE COALESCE(created_utc, '') = ''", (now,))
        conn.execute("UPDATE lp_project_items SET updated_utc = ? WHERE COALESCE(updated_utc, '') = ''", (now,))


def normalize_status(value):
    status = (value or "").strip().lower()
    return status if status in PROJECT_STATUSES else "planned"


def _clean_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_item_type(value):
    text = _clean_text(value).lower()
    aliases = {
        "notes": "note",
        "tasks": "task",
        "calendar": "event",
        "events": "event",
        "people": "person",
        "contacts": "person",
        "places": "place",
        "files": "file",
        "howto": "how",
        "how-to": "how",
        "howtos": "how",
        "images": "media",
        "video": "media",
        "videos": "media",
        "music": "audio",
        "money_record": "money",
    }
    return aliases.get(text, text)


def status_options():
    return [{"value": value, "label": PROJECT_STATUS_LABELS[value]} for value in PROJECT_STATUSES]


def area_options(selected_area_ids=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    areas_mod.ensure_areas_schema(conn)
    selected = set(selected_area_ids or [])
    options = []
    seen = set()
    for row in areas_mod.areas_list_sidebar(conn=conn, owner_user_id=owner_user_id):
        area_id = _clean_text(row.get("area_id"))
        if not area_id or area_id.lower() == "unmapped":
            continue
        seen.add(area_id)
        options.append(
            {
                "area_id": area_id,
                "label": row.get("area_name") or area_id,
                "icon": row.get("icon") or "",
                "selected": area_id in selected,
            }
        )
    for area_id in sorted(selected - seen):
        options.insert(
            0,
            {"area_id": area_id, "label": area_id, "icon": "", "selected": True},
        )
    return options


def project_list(
    statuses=None,
    area_id=None,
    include_archived=False,
    conn=None,
    owner_user_id=None,
    limit=None,
):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["p.owner_user_id IS ?"]
    if statuses:
        normalized_statuses = [normalize_status(status) for status in statuses if status]
        if normalized_statuses:
            where.append("p.status IN (" + ",".join(["?"] * len(normalized_statuses)) + ")")
            params.extend(normalized_statuses)
    elif not include_archived:
        where.append("p.status != 'archived'")
    area_id = _clean_text(area_id)
    if area_id and area_id.lower() not in {"all", "all areas", "any", "unmapped"}:
        where.append(
            "EXISTS ("
            "SELECT 1 FROM lp_project_areas pa "
            "WHERE pa.owner_user_id IS ? AND pa.project_id = p.project_id "
            "AND (lower(pa.area_id) = lower(?) "
            "OR lower(pa.area_id) LIKE lower(?) || '/%' "
            "OR lower(?) LIKE lower(pa.area_id) || '/%'))"
        )
        params.extend([owner_user_id, area_id, area_id, area_id])
    sql = (
        "SELECT p.*, "
        "(SELECT COUNT(1) FROM lp_project_items i WHERE i.owner_user_id IS p.owner_user_id AND i.project_id = p.project_id) AS item_count "
        "FROM lp_project_workspaces p "
        "WHERE " + " AND ".join(where) + " "
        "ORDER BY p.pinned DESC, "
        "CASE p.status WHEN 'active' THEN 0 WHEN 'planned' THEN 1 WHEN 'completed' THEN 2 WHEN 'cancelled' THEN 3 ELSE 4 END, "
        "p.sort_order, lower(p.name), p.project_id"
    )
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    projects = [_project_row(row, conn=conn, owner_user_id=owner_user_id) for row in rows]
    return projects


def sidebar_projects(area_id=None, conn=None, owner_user_id=None, limit=12):
    return project_list(
        statuses=("active", "planned"),
        area_id=area_id,
        conn=conn,
        owner_user_id=owner_user_id,
        limit=limit,
    )


def parent_project_options(current_project_id=None, conn=None, owner_user_id=None):
    rows = project_list(include_archived=True, conn=conn, owner_user_id=owner_user_id)
    current_project_id = _clean_int(current_project_id)
    return [row for row in rows if row.get("project_id") != current_project_id]


def project_get(project_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT p.*, "
        "(SELECT COUNT(1) FROM lp_project_items i WHERE i.owner_user_id IS p.owner_user_id AND i.project_id = p.project_id) AS item_count "
        "FROM lp_project_workspaces p WHERE p.project_id = ? AND p.owner_user_id IS ?",
        (project_id, owner_user_id),
    ).fetchone()
    return _project_row(row, conn=conn, owner_user_id=owner_user_id) if row else None


def create_project(values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    name = _clean_text(values.get("name"))
    if not name:
        raise ValueError("Project name is required.")
    now = _utc_now()
    cur = conn.execute(
        "INSERT INTO lp_project_workspaces "
        "(owner_user_id, name, project_type, description, status, start_date, end_date, "
        "parent_project_id, icon, comments, sort_order, pinned, created_utc, updated_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            owner_user_id,
            name,
            _clean_text(values.get("project_type")),
            _clean_text(values.get("description")),
            normalize_status(values.get("status")),
            _clean_text(values.get("start_date")),
            _clean_text(values.get("end_date")),
            _clean_int(values.get("parent_project_id")),
            _clean_text(values.get("icon")),
            _clean_text(values.get("comments")),
            _clean_int(values.get("sort_order"), 100) or 100,
            1 if values.get("pinned") in (1, True, "1", "true", "on", "yes") else 0,
            now,
            now,
        ),
    )
    project_id = cur.lastrowid
    set_project_areas(project_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    _log_project_change(conn, "project_add", project_id, after=project_get(project_id, conn=conn, owner_user_id=owner_user_id))
    return project_id


def update_project(project_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = project_get(project_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    parent_project_id = _clean_int(values.get("parent_project_id"))
    if parent_project_id == int(project_id):
        parent_project_id = None
    name = _clean_text(values.get("name"))
    if not name:
        raise ValueError("Project name is required.")
    now = _utc_now()
    conn.execute(
        "UPDATE lp_project_workspaces SET name = ?, project_type = ?, description = ?, status = ?, "
        "start_date = ?, end_date = ?, parent_project_id = ?, icon = ?, comments = ?, "
        "sort_order = ?, pinned = ?, updated_utc = ? "
        "WHERE project_id = ? AND owner_user_id IS ?",
        (
            name,
            _clean_text(values.get("project_type")),
            _clean_text(values.get("description")),
            normalize_status(values.get("status")),
            _clean_text(values.get("start_date")),
            _clean_text(values.get("end_date")),
            parent_project_id,
            _clean_text(values.get("icon")),
            _clean_text(values.get("comments")),
            _clean_int(values.get("sort_order"), 100) or 100,
            1 if values.get("pinned") in (1, True, "1", "true", "on", "yes") else 0,
            now,
            project_id,
            owner_user_id,
        ),
    )
    set_project_areas(project_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    conn.commit()
    after = project_get(project_id, conn=conn, owner_user_id=owner_user_id)
    _log_project_change(conn, "project_update", project_id, before=before, after=after)
    return True


def set_project_areas(project_id, area_ids, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    now = _utc_now()
    cleaned = []
    seen = set()
    for area_id in area_ids or []:
        area_id = _clean_text(area_id)
        if not area_id or area_id in seen:
            continue
        seen.add(area_id)
        cleaned.append(area_id)
    conn.execute(
        "DELETE FROM lp_project_areas WHERE project_id = ? AND owner_user_id IS ?",
        (project_id, owner_user_id),
    )
    for idx, area_id in enumerate(cleaned):
        conn.execute(
            "INSERT OR IGNORE INTO lp_project_areas "
            "(owner_user_id, project_id, area_id, sort_order, created_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (owner_user_id, project_id, area_id, idx * 10, now),
        )
    conn.commit()


def list_project_areas(project_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT pa.project_area_id, pa.owner_user_id, pa.project_id, pa.area_id, pa.sort_order, pa.created_utc, "
        "a.area_name, a.icon "
        "FROM lp_project_areas pa "
        "LEFT JOIN lp_areas a ON a.owner_user_id IS pa.owner_user_id AND lower(a.area_id) = lower(pa.area_id) "
        "WHERE pa.owner_user_id IS ? AND pa.project_id = ? "
        "ORDER BY pa.sort_order, lower(COALESCE(a.area_name, pa.area_id))",
        (owner_user_id, project_id),
    ).fetchall()
    return [dict(row) for row in rows]


def add_project_item(
    project_id,
    item_type,
    item_id,
    item_title=None,
    *,
    section="",
    pinned=0,
    sort_order=None,
    is_primary=0,
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if not project_get(project_id, conn=conn, owner_user_id=owner_user_id):
        raise ValueError("Project not found.")
    item_type = _normalize_item_type(item_type)
    item_id = _clean_text(item_id)
    if not item_type or not item_id:
        raise ValueError("Item type and id are required.")
    if not item_title:
        summary = _record_summary(item_type, item_id)
        item_title = (summary or {}).get("title") or (summary or {}).get("subtitle") or ""
    if sort_order is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order "
            "FROM lp_project_items WHERE owner_user_id IS ? AND project_id = ?",
            (owner_user_id, project_id),
        ).fetchone()
        sort_order = row["next_order"] if row else 100
    now = _utc_now()
    if is_primary:
        _clear_primary_project(conn, owner_user_id, item_type, item_id)
    try:
        cur = conn.execute(
            "INSERT INTO lp_project_items "
            "(owner_user_id, project_id, item_type, item_id, item_title, section, pinned, sort_order, "
            "is_primary, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_user_id,
                project_id,
                item_type,
                item_id,
                _clean_text(item_title),
                _clean_text(section),
                1 if pinned else 0,
                _clean_int(sort_order, 100) or 100,
                1 if is_primary else 0,
                now,
                now,
            ),
        )
        project_item_id = cur.lastrowid
        created = True
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE lp_project_items SET item_title = COALESCE(NULLIF(?, ''), item_title), "
            "section = COALESCE(NULLIF(?, ''), section), pinned = CASE WHEN ? THEN 1 ELSE pinned END, "
            "is_primary = CASE WHEN ? THEN 1 ELSE is_primary END, updated_utc = ? "
            "WHERE owner_user_id IS ? AND project_id = ? AND item_type = ? AND item_id = ?",
            (
                _clean_text(item_title),
                _clean_text(section),
                1 if pinned else 0,
                1 if is_primary else 0,
                now,
                owner_user_id,
                project_id,
                item_type,
                item_id,
            ),
        )
        row = conn.execute(
            "SELECT project_item_id FROM lp_project_items "
            "WHERE owner_user_id IS ? AND project_id = ? AND item_type = ? AND item_id = ?",
            (owner_user_id, project_id, item_type, item_id),
        ).fetchone()
        project_item_id = row["project_item_id"] if row else None
        created = False
    conn.commit()
    _log_project_change(
        conn,
        "project_item_add" if created else "project_item_update",
        project_item_id,
        after=get_project_item(project_item_id, conn=conn, owner_user_id=owner_user_id) if project_item_id else None,
    )
    return {"project_item_id": project_item_id, "created": created}


def _clear_primary_project(conn, owner_user_id, item_type, item_id):
    conn.execute(
        "UPDATE lp_project_items SET is_primary = 0, updated_utc = ? "
        "WHERE owner_user_id IS ? AND item_type = ? AND item_id = ?",
        (_utc_now(), owner_user_id, item_type, item_id),
    )


def get_project_item(project_item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT * FROM lp_project_items WHERE project_item_id = ? AND owner_user_id IS ?",
        (project_item_id, owner_user_id),
    ).fetchone()
    return dict(row) if row else None


def list_project_items(project_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT * FROM lp_project_items WHERE owner_user_id IS ? AND project_id = ? "
        "ORDER BY pinned DESC, COALESCE(section, ''), item_type, sort_order, project_item_id",
        (owner_user_id, project_id),
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        summary = _record_summary(item["item_type"], item["item_id"])
        if summary:
            item["summary"] = summary
            if not item.get("item_title"):
                item["item_title"] = summary.get("title") or ""
        else:
            item["summary"] = {
                "type": item["item_type"],
                "id": item["item_id"],
                "title": item.get("item_title") or f"{item['item_type']} {item['item_id']}",
                "subtitle": "",
                "icon": item["item_type"][:1].upper(),
                "open_url": "",
            }
        items.append(item)
    return items


def grouped_project_items(project_id, group_by="type", conn=None, owner_user_id=None):
    items = list_project_items(project_id, conn=conn, owner_user_id=owner_user_id)
    group_by = (group_by or "type").strip().lower()
    groups = []
    lookup = {}
    for item in items:
        if group_by == "section":
            key = item.get("section") or "Unsectioned"
        elif group_by == "none":
            key = "Contents"
        else:
            key = _type_label(item.get("item_type"))
        if key not in lookup:
            lookup[key] = {"label": key, "items": []}
            groups.append(lookup[key])
        lookup[key]["items"].append(item)
    return groups


def update_project_item(project_item_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = get_project_item(project_item_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    is_primary = 1 if values.get("is_primary") in (1, True, "1", "true", "on", "yes") else 0
    if is_primary:
        _clear_primary_project(conn, owner_user_id, before["item_type"], before["item_id"])
    conn.execute(
        "UPDATE lp_project_items SET item_title = ?, section = ?, pinned = ?, sort_order = ?, "
        "is_primary = ?, updated_utc = ? WHERE project_item_id = ? AND owner_user_id IS ?",
        (
            _clean_text(values.get("item_title")) or before.get("item_title") or "",
            _clean_text(values.get("section")),
            1 if values.get("pinned") in (1, True, "1", "true", "on", "yes") else 0,
            _clean_int(values.get("sort_order"), before.get("sort_order") or 100) or 100,
            is_primary,
            _utc_now(),
            project_item_id,
            owner_user_id,
        ),
    )
    conn.commit()
    _log_project_change(
        conn,
        "project_item_update",
        project_item_id,
        before=before,
        after=get_project_item(project_item_id, conn=conn, owner_user_id=owner_user_id),
    )
    return True


def move_project_item(project_item_id, direction, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    item = get_project_item(project_item_id, conn=conn, owner_user_id=owner_user_id)
    if not item:
        return False
    comparison = "<" if direction == "up" else ">"
    sort_dir = "DESC" if direction == "up" else "ASC"
    other = conn.execute(
        "SELECT project_item_id, sort_order FROM lp_project_items "
        "WHERE owner_user_id IS ? AND project_id = ? "
        f"AND sort_order {comparison} ? "
        f"ORDER BY sort_order {sort_dir}, project_item_id {sort_dir} LIMIT 1",
        (owner_user_id, item["project_id"], item["sort_order"]),
    ).fetchone()
    if not other:
        return False
    now = _utc_now()
    conn.execute(
        "UPDATE lp_project_items SET sort_order = ?, updated_utc = ? WHERE project_item_id = ?",
        (other["sort_order"], now, item["project_item_id"]),
    )
    conn.execute(
        "UPDATE lp_project_items SET sort_order = ?, updated_utc = ? WHERE project_item_id = ?",
        (item["sort_order"], now, other["project_item_id"]),
    )
    conn.commit()
    return True


def remove_project_item(project_item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = get_project_item(project_item_id, conn=conn, owner_user_id=owner_user_id)
    cur = conn.execute(
        "DELETE FROM lp_project_items WHERE project_item_id = ? AND owner_user_id IS ?",
        (project_item_id, owner_user_id),
    )
    conn.commit()
    if cur.rowcount:
        _log_project_change(conn, "project_item_remove", project_item_id, before=before, after=None)
    return cur.rowcount > 0


def remove_item_from_project(project_id, item_type, item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    item_type = _normalize_item_type(item_type)
    item_id = _clean_text(item_id)
    row = conn.execute(
        "SELECT project_item_id FROM lp_project_items "
        "WHERE owner_user_id IS ? AND project_id = ? AND item_type = ? AND item_id = ?",
        (owner_user_id, project_id, item_type, item_id),
    ).fetchone()
    if not row:
        return False
    return remove_project_item(row["project_item_id"], conn=conn, owner_user_id=owner_user_id)


def record_projects(item_type, item_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    item_type = _normalize_item_type(item_type)
    item_id = _clean_text(item_id)
    rows = conn.execute(
        "SELECT i.project_item_id, i.is_primary, p.project_id, p.name, p.icon, p.status "
        "FROM lp_project_items i "
        "JOIN lp_project_workspaces p ON p.owner_user_id IS i.owner_user_id AND p.project_id = i.project_id "
        "WHERE i.owner_user_id IS ? AND i.item_type = ? AND i.item_id = ? "
        "ORDER BY i.is_primary DESC, p.pinned DESC, p.sort_order, lower(p.name)",
        (owner_user_id, item_type, item_id),
    ).fetchall()
    return [dict(row) for row in rows]


def assign_item_to_project(project_id, item_type, item_id, item_title=None, is_primary=0, conn=None, owner_user_id=None):
    return add_project_item(
        project_id,
        item_type,
        item_id,
        item_title=item_title,
        is_primary=is_primary,
        conn=conn,
        owner_user_id=owner_user_id,
    )


def project_delete(project_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_projects_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = project_get(project_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    conn.execute("DELETE FROM lp_project_items WHERE owner_user_id IS ? AND project_id = ?", (owner_user_id, project_id))
    conn.execute("DELETE FROM lp_project_areas WHERE owner_user_id IS ? AND project_id = ?", (owner_user_id, project_id))
    cur = conn.execute("DELETE FROM lp_project_workspaces WHERE owner_user_id IS ? AND project_id = ?", (owner_user_id, project_id))
    conn.commit()
    if cur.rowcount:
        _log_project_change(conn, "project_delete", project_id, before=before, after=None)
    return cur.rowcount > 0


def project_archive(project_id, conn=None, owner_user_id=None):
    project = project_get(project_id, conn=conn, owner_user_id=owner_user_id)
    if not project:
        return False
    values = dict(project)
    values["status"] = "archived"
    values["area_ids"] = [row["area_id"] for row in project.get("areas", [])]
    return update_project(project_id, values, conn=conn, owner_user_id=owner_user_id)


def _project_row(row, conn=None, owner_user_id=None):
    if not row:
        return None
    project = dict(row)
    project["status_label"] = PROJECT_STATUS_LABELS.get(project.get("status"), project.get("status") or "")
    project["areas"] = list_project_areas(project["project_id"], conn=conn, owner_user_id=owner_user_id)
    project["area_ids"] = [area["area_id"] for area in project["areas"]]
    return project


def _record_summary(item_type, item_id):
    try:
        from common import links_records

        return links_records.get_record_summary(item_type, item_id)
    except Exception:
        return None


def _type_label(item_type):
    labels = {
        "note": "Notes",
        "task": "Tasks",
        "event": "Calendar events",
        "how": "How-tos",
        "list": "Lists",
        "file": "Files",
        "media": "Media",
        "audio": "Audio",
        "person": "People",
        "place": "Places",
        "money": "Money records",
        "collection": "Collections",
        "app": "Apps",
        "3d": "3D",
        "album": "Albums",
    }
    return labels.get(_normalize_item_type(item_type), (_normalize_item_type(item_type) or "Items").title())


def _log_project_change(conn, action, entity_id, before=None, after=None):
    try:
        utils_mod.lg_usr(
            action=action,
            entity_type="lp_project_workspaces" if action.startswith("project_") and "item" not in action else "lp_project_items",
            entity_id=entity_id,
            before=before,
            after=after,
            context_type="projects",
            context_id=str(entity_id) if entity_id is not None else None,
            conn=conn,
        )
    except Exception:
        pass
