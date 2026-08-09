import json
import os
import sqlite3
from datetime import date, datetime, timezone

from common import data as db
from common import links as links_mod
from common import projects as projects_mod
from common import utils as utils_mod
from modules.apps import schema as apps_model


TASK_STATUSES = ("open", "done", "cancelled")
TASK_KINDS = ("task", "template")

TASK_COLUMNS = [
    "id",
    "owner_user_id",
    "title",
    "content",
    "area",
    "start_date",
    "due_date",
    "status",
    "task_kind",
    "app_action_id",
    "parameters_json",
    "completed_date",
    "user_name",
    "rec_extract_date",
]

TASKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER,
    title TEXT NOT NULL,
    content TEXT,
    area TEXT,
    start_date TEXT,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    task_kind TEXT NOT NULL DEFAULT 'task',
    app_action_id INTEGER,
    parameters_json TEXT,
    completed_date TEXT,
    user_name TEXT,
    rec_extract_date TEXT
);

CREATE INDEX IF NOT EXISTS ix_lp_tasks_owner_status
ON lp_tasks (owner_user_id, task_kind, status, due_date);

CREATE INDEX IF NOT EXISTS ix_lp_tasks_app_action
ON lp_tasks (owner_user_id, app_action_id);

CREATE INDEX IF NOT EXISTS ix_lp_tasks_area
ON lp_tasks (owner_user_id, area);
"""

_TASKS_SCHEMA_READY_CONN_IDS = set()


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today():
    return date.today().isoformat()


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


def _current_user_name():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _clean_text(value):
    return "" if value is None else str(value).strip()


def _clean_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def _table_columns(conn, table_name):
    try:
        return {row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    except Exception:
        return set()


def ensure_tasks_schema(conn=None):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _TASKS_SCHEMA_READY_CONN_IDS and _tasks_schema_is_current(conn):
        return
    if _table_exists(conn, "lp_tasks") and not _tasks_schema_is_current(conn):
        _replace_old_tasks_schema(conn)
    conn.executescript(TASKS_SCHEMA_SQL)
    _migrate_tasks_schema(conn)
    conn.commit()
    _TASKS_SCHEMA_READY_CONN_IDS.add(conn_id)


def _tasks_schema_is_current(conn):
    cols = _table_columns(conn, "lp_tasks")
    return {"id", "title", "status", "task_kind", "app_action_id", "parameters_json", "completed_date"}.issubset(cols)


def _replace_old_tasks_schema(conn):
    old_ids = []
    try:
        if "id" in _table_columns(conn, "lp_tasks"):
            old_ids = [str(row["id"]) for row in conn.execute("SELECT id FROM lp_tasks").fetchall()]
    except Exception:
        old_ids = []
    if old_ids:
        placeholders = ",".join(["?"] * len(old_ids))
        if _table_exists(conn, "lp_links"):
            conn.execute(
                f"DELETE FROM lp_links WHERE (src_type = 'task' AND src_id IN ({placeholders})) "
                f"OR (dst_type = 'task' AND dst_id IN ({placeholders}))",
                old_ids + old_ids,
            )
        if _table_exists(conn, "lp_project_items"):
            conn.execute(
                f"DELETE FROM lp_project_items WHERE item_type = 'task' AND item_id IN ({placeholders})",
                old_ids,
            )
        if _table_exists(conn, "lp_collection_item"):
            conn.execute(
                f"DELETE FROM lp_collection_item WHERE item_type = 'task' AND item_id IN ({placeholders})",
                old_ids,
            )
    conn.execute("DROP TABLE lp_tasks")


def _migrate_tasks_schema(conn):
    cols = _table_columns(conn, "lp_tasks")
    additions = {
        "owner_user_id": "INTEGER",
        "content": "TEXT",
        "area": "TEXT",
        "start_date": "TEXT",
        "due_date": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'open'",
        "task_kind": "TEXT NOT NULL DEFAULT 'task'",
        "app_action_id": "INTEGER",
        "parameters_json": "TEXT",
        "completed_date": "TEXT",
        "user_name": "TEXT",
        "rec_extract_date": "TEXT",
    }
    for col_name, col_type in additions.items():
        if col_name not in cols:
            conn.execute(f"ALTER TABLE lp_tasks ADD COLUMN {col_name} {col_type}")
    now = _utc_now()
    conn.execute("UPDATE lp_tasks SET status = 'open' WHERE COALESCE(status, '') = ''")
    conn.execute("UPDATE lp_tasks SET task_kind = 'task' WHERE COALESCE(task_kind, '') = ''")
    conn.execute("UPDATE lp_tasks SET rec_extract_date = ? WHERE COALESCE(rec_extract_date, '') = ''", (now,))


def normalize_status(value):
    status = _clean_text(value).lower()
    return status if status in TASK_STATUSES else "open"


def normalize_task_kind(value):
    task_kind = _clean_text(value).lower()
    return task_kind if task_kind in TASK_KINDS else "task"


def parse_parameter_values(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def task_list(area_id=None, view_filter="all", query="", limit=None, offset=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["t.owner_user_id IS ?"]
    _append_filters(where, params, owner_user_id, area_id, view_filter, query)
    sql = _task_select_sql() + " WHERE " + " AND ".join(where) + " ORDER BY " + _task_order(view_filter)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    return [_task_row(row) for row in conn.execute(sql, params).fetchall()]


def task_count(area_id=None, view_filter="all", query="", conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["t.owner_user_id IS ?"]
    _append_filters(where, params, owner_user_id, area_id, view_filter, query)
    row = conn.execute("SELECT COUNT(1) AS cnt FROM lp_tasks t WHERE " + " AND ".join(where), params).fetchone()
    return row["cnt"] if row else 0


def _append_filters(where, params, owner_user_id, area_id, view_filter, query):
    area_id = _clean_text(area_id)
    if area_id and area_id.lower() not in {"all", "all areas", "any", "unmapped"}:
        where.append(
            "(lower(t.area) = lower(?) OR lower(t.area) LIKE lower(?) || '/%' OR lower(?) LIKE lower(t.area) || '/%')"
        )
        params.extend([area_id, area_id, area_id])
    elif area_id.lower() == "unmapped":
        where.append("COALESCE(t.area, '') = ''")

    view_filter = (_clean_text(view_filter) or "all").lower()
    today = _today()
    if view_filter == "templates":
        where.append("t.task_kind = 'template'")
    elif view_filter == "completed":
        where.append("t.task_kind = 'task'")
        where.append("t.status IN ('done', 'cancelled')")
    elif view_filter == "today":
        where.append("t.task_kind = 'task'")
        where.append("t.status = 'open'")
        where.append("COALESCE(t.due_date, '') <= ? AND COALESCE(t.due_date, '') != ''")
        params.append(today)
    elif view_filter == "upcoming":
        where.append("t.task_kind = 'task'")
        where.append("t.status = 'open'")
        where.append("COALESCE(t.due_date, '') > ?")
        params.append(today)
    else:
        where.append("t.task_kind = 'task'")
        where.append("t.status = 'open'")

    terms = [_clean_text(part).lower() for part in query.split() if _clean_text(part)]
    for term in terms:
        like_value = f"%{term}%"
        where.append("(lower(COALESCE(t.title, '')) LIKE ? OR lower(COALESCE(t.content, '')) LIKE ? OR lower(COALESCE(t.area, '')) LIKE ?)")
        params.extend([like_value, like_value, like_value])


def _task_select_sql():
    return (
        "SELECT t.*, ax.action_name, ax.parameter_schema_json, ax.app_id, a.title AS app_title "
        "FROM lp_tasks t "
        "LEFT JOIN lp_app_action ax ON ax.owner_user_id IS t.owner_user_id AND ax.app_action_id = t.app_action_id "
        "LEFT JOIN lp_app a ON a.owner_user_id IS ax.owner_user_id AND a.app_id = ax.app_id"
    )


def _task_order(view_filter):
    if (_clean_text(view_filter) or "").lower() == "completed":
        return "COALESCE(t.completed_date, t.rec_extract_date) DESC, lower(t.title)"
    return "(COALESCE(t.due_date, '') = '') ASC, t.due_date ASC, lower(t.title), t.id"


def task_get(task_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(_task_select_sql() + " WHERE t.id = ? AND t.owner_user_id IS ?", (task_id, owner_user_id)).fetchone()
    return _task_row(row) if row else None


def quick_add(title, area="", conn=None, owner_user_id=None):
    return create_task({"title": title, "area": area, "task_kind": "task", "status": "open"}, conn=conn, owner_user_id=owner_user_id)


def create_task(values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    cleaned = _normalize_task_values(values, conn=conn, owner_user_id=owner_user_id)
    now = _utc_now()
    cur = conn.execute(
        "INSERT INTO lp_tasks "
        "(owner_user_id, title, content, area, start_date, due_date, status, task_kind, app_action_id, parameters_json, "
        "completed_date, user_name, rec_extract_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            owner_user_id,
            cleaned["title"],
            cleaned["content"],
            cleaned["area"],
            cleaned["start_date"],
            cleaned["due_date"],
            cleaned["status"],
            cleaned["task_kind"],
            cleaned["app_action_id"],
            cleaned["parameters_json"],
            cleaned["completed_date"],
            _current_user_name(),
            now,
        ),
    )
    task_id = cur.lastrowid
    conn.commit()
    _log_task_change(conn, "task_add", task_id, after=task_get(task_id, conn=conn, owner_user_id=owner_user_id))
    return task_id


def update_task(task_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = task_get(task_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    cleaned = _normalize_task_values(values, existing=before, conn=conn, owner_user_id=owner_user_id)
    now = _utc_now()
    conn.execute(
        "UPDATE lp_tasks SET title = ?, content = ?, area = ?, start_date = ?, due_date = ?, status = ?, "
        "task_kind = ?, app_action_id = ?, parameters_json = ?, completed_date = ?, rec_extract_date = ? "
        "WHERE id = ? AND owner_user_id IS ?",
        (
            cleaned["title"],
            cleaned["content"],
            cleaned["area"],
            cleaned["start_date"],
            cleaned["due_date"],
            cleaned["status"],
            cleaned["task_kind"],
            cleaned["app_action_id"],
            cleaned["parameters_json"],
            cleaned["completed_date"],
            now,
            task_id,
            owner_user_id,
        ),
    )
    conn.commit()
    _log_task_change(conn, "task_update", task_id, before=before, after=task_get(task_id, conn=conn, owner_user_id=owner_user_id))
    return True


def _normalize_task_values(values, existing=None, conn=None, owner_user_id=None):
    values = values or {}
    title = _clean_text(values.get("title"))
    if not title:
        raise ValueError("Task title is required.")
    status = normalize_status(values.get("status") if "status" in values else (existing or {}).get("status"))
    task_kind = normalize_task_kind(values.get("task_kind") if "task_kind" in values else (existing or {}).get("task_kind"))
    completed_date = _clean_text((existing or {}).get("completed_date"))
    if status == "done" and not completed_date:
        completed_date = _utc_now()
    elif status != "done":
        completed_date = ""
    app_action_id = _clean_int(values.get("app_action_id"))
    parameter_values = parse_parameter_values(values.get("parameters_json") or values.get("parameter_values"))
    parameters_json = ""
    if app_action_id:
        action = apps_model.app_action_get(app_action_id, conn=conn, owner_user_id=owner_user_id)
        if not action:
            raise ValueError("Selected App Action was not found.")
        parameter_values = apps_model.validate_parameter_values(action.get("parameter_schema_json"), parameter_values)
        parameters_json = json.dumps(parameter_values, ensure_ascii=True, separators=(",", ":")) if parameter_values else ""
    return {
        "title": title,
        "content": _clean_text(values.get("content")),
        "area": _clean_text(values.get("area")),
        "start_date": _clean_text(values.get("start_date")),
        "due_date": _clean_text(values.get("due_date")),
        "status": status,
        "task_kind": task_kind,
        "app_action_id": app_action_id,
        "parameters_json": parameters_json,
        "completed_date": completed_date,
    }


def delete_task(task_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = task_get(task_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    conn.execute("DELETE FROM lp_tasks WHERE id = ? AND owner_user_id IS ?", (task_id, owner_user_id))
    conn.commit()
    _log_task_change(conn, "task_delete", task_id, before=before, after=None)
    return True


def set_status(task_id, status, conn=None, owner_user_id=None):
    task = task_get(task_id, conn=conn, owner_user_id=owner_user_id)
    if not task:
        return False
    values = dict(task)
    values["status"] = normalize_status(status)
    values["parameter_values"] = task.get("parameter_values") or {}
    return update_task(task_id, values, conn=conn, owner_user_id=owner_user_id)


def run_task(task_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    task = task_get(task_id, conn=conn, owner_user_id=owner_user_id)
    if not task:
        raise ValueError("Task not found.")
    if not task.get("app_action_id"):
        raise ValueError("This is a human Task and has no App Action to run.")
    if task.get("missing_app_action"):
        raise ValueError("The App Action linked to this Task is missing.")
    action = apps_model.launch_action(
        task["app_id"],
        action_id=task["app_action_id"],
        parameter_values=task.get("parameter_values") or {},
        conn=conn,
        owner_user_id=owner_user_id,
    )
    return action


def create_task_from_template(template_id, overrides=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    template = task_get(template_id, conn=conn, owner_user_id=owner_user_id)
    if not template or template.get("task_kind") != "template":
        raise ValueError("Task Template not found.")
    values = {
        "title": template["title"],
        "content": template.get("content"),
        "area": template.get("area"),
        "start_date": "",
        "due_date": "",
        "status": "open",
        "task_kind": "task",
        "app_action_id": template.get("app_action_id"),
        "parameter_values": template.get("parameter_values") or {},
    }
    values.update(overrides or {})
    task_id = create_task(values, conn=conn, owner_user_id=owner_user_id)
    _copy_template_links(template_id, task_id, conn)
    return task_id


def related_tasks_for_action(action_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        _task_select_sql() + " WHERE t.owner_user_id IS ? AND t.app_action_id = ? ORDER BY lower(t.title)",
        (owner_user_id, action_id),
    ).fetchall()
    return [_task_row(row) for row in rows]


def related_tasks_for_app(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_tasks_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        _task_select_sql()
        + " WHERE t.owner_user_id IS ? AND ax.app_id = ? ORDER BY t.task_kind DESC, lower(t.title)",
        (owner_user_id, app_id),
    ).fetchall()
    return [_task_row(row) for row in rows]


def _copy_template_links(template_id, task_id, conn):
    if not _table_exists(conn, "lp_links"):
        return
    links_mod.ensure_links_schema(conn)
    for link in links_mod.list_outgoing(conn, "task", template_id):
        payload = dict(link)
        payload["src_id"] = str(task_id)
        payload.pop("link_id", None)
        payload["created_utc"] = _utc_now()
        try:
            links_mod.create_link(conn, payload)
        except Exception:
            pass


def _task_row(row):
    if not row:
        return None
    task = dict(row)
    task["parameter_values"] = parse_parameter_values(task.get("parameters_json"))
    task["missing_app_action"] = bool(task.get("app_action_id") and not task.get("action_name"))
    task["run_with_label"] = "None - human task"
    if task["missing_app_action"]:
        task["run_with_label"] = "Missing App Action"
    elif task.get("app_action_id"):
        task["run_with_label"] = f"{task.get('app_title') or 'App'} -> {task.get('action_name') or 'Action'}"
    return task


def _log_task_change(conn, action, task_id, before=None, after=None):
    try:
        projects = projects_mod.record_projects("task", task_id, conn=conn)
        utils_mod.lg_usr(
            action=action,
            entity_type="lp_tasks",
            entity_id=task_id,
            before=before,
            after=after,
            context_type="tasks",
            context_id=str(task_id),
            extra={"projects": projects} if projects else None,
            conn=conn,
        )
    except Exception:
        pass
