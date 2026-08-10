import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone

from common import areas as areas_mod
from common import collections as collections_mod
from common import data as db
from common import utils as utils_mod


APP_KIND_OPTIONS = (
    "Application",
    "Development Project",
    "Repository",
    "Script",
    "Executable",
    "Command",
    "Web App",
    "Website",
    "Database",
    "SQL Script",
    "Development Environment",
    "Service",
    "Connection",
    "Utility",
    "Other",
)

ACTION_TYPE_OPTIONS = (
    "EXECUTABLE",
    "COMMAND",
    "OPEN_FILE",
    "OPEN_FOLDER",
    "OPEN_URL",
    "SYSTEM_DEFAULT",
)

PARAMETER_TYPE_OPTIONS = (
    "text",
    "integer",
    "number",
    "boolean",
    "file",
    "folder",
    "select",
)

PARAMETER_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

PROJECT_KINDS = {"Development Project", "Repository"}
SCRIPT_KINDS = {"Script", "Command", "SQL Script", "Utility"}
APPLICATION_KINDS = {"Application", "Executable", "Development Environment", "Service"}

APPS_SCHEMA_SQL = """
DROP TABLE IF EXISTS lp_apps;

CREATE TABLE IF NOT EXISTS lp_app (
    app_id          INTEGER PRIMARY KEY,
    owner_user_id   INTEGER,
    title           TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'Other',
    description     TEXT,
    icon            TEXT,
    favorite        INTEGER NOT NULL DEFAULT 0,
    enabled         INTEGER NOT NULL DEFAULT 1,
    path            TEXT,
    repository_url  TEXT,
    website_url     TEXT,
    language        TEXT,
    version         TEXT,
    tags            TEXT,
    comments        TEXT,
    import_source   TEXT,
    import_source_path TEXT,
    imported_date   TEXT,
    import_metadata TEXT,
    last_used_date  TEXT,
    usage_count     INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL,
    modified_date   TEXT NOT NULL,
    user_name       TEXT,
    rec_extract_date TEXT
);

CREATE INDEX IF NOT EXISTS ix_lp_app_owner_title
ON lp_app (owner_user_id, enabled, lower(title));

CREATE INDEX IF NOT EXISTS ix_lp_app_owner_kind
ON lp_app (owner_user_id, kind);

CREATE INDEX IF NOT EXISTS ix_lp_app_recent
ON lp_app (owner_user_id, last_used_date);

CREATE TABLE IF NOT EXISTS lp_app_area (
    app_area_id INTEGER PRIMARY KEY,
    owner_user_id INTEGER,
    app_id      INTEGER NOT NULL,
    area_id     TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 100,
    created_utc TEXT NOT NULL,
    UNIQUE (owner_user_id, app_id, area_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_app_area_app
ON lp_app_area (owner_user_id, app_id, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_app_area_area
ON lp_app_area (owner_user_id, area_id);

CREATE TABLE IF NOT EXISTS lp_app_action (
    app_action_id    INTEGER PRIMARY KEY,
    owner_user_id    INTEGER,
    app_id           INTEGER NOT NULL,
    action_name      TEXT NOT NULL,
    action_type      TEXT NOT NULL,
    command          TEXT,
    working_directory TEXT,
    arguments        TEXT,
    parameter_schema_json TEXT,
    agent_allowed    INTEGER NOT NULL DEFAULT 0,
    requires_confirmation INTEGER NOT NULL DEFAULT 1,
    sort_order       INTEGER NOT NULL DEFAULT 100,
    is_default       INTEGER NOT NULL DEFAULT 0,
    created_utc      TEXT NOT NULL,
    updated_utc      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_app_action_app
ON lp_app_action (owner_user_id, app_id, is_default DESC, sort_order);
"""

_APPS_SCHEMA_READY_CONN_IDS = set()


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


def _current_user_name():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _clean_int(value, default=None):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_truthy(value):
    return value in (1, True, "1", "true", "on", "yes", "Y", "y")


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


def ensure_apps_schema(conn=None):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _APPS_SCHEMA_READY_CONN_IDS and _apps_schema_is_current(conn):
        ensure_file_inventory_app(conn)
        return
    areas_mod.ensure_areas_schema(conn)
    collections_mod.ensure_collections_schema(conn)
    conn.executescript(APPS_SCHEMA_SQL)
    _migrate_apps_schema(conn)
    ensure_file_inventory_app(conn)
    conn.commit()
    _APPS_SCHEMA_READY_CONN_IDS.add(conn_id)


def _apps_schema_is_current(conn):
    return (
        {"app_id", "title", "kind", "favorite", "last_used_date", "import_source", "import_source_path", "imported_date", "import_metadata"}.issubset(_table_columns(conn, "lp_app"))
        and {"app_id", "area_id"}.issubset(_table_columns(conn, "lp_app_area"))
        and {"app_id", "action_name", "action_type", "is_default", "parameter_schema_json", "agent_allowed", "requires_confirmation"}.issubset(_table_columns(conn, "lp_app_action"))
        and not _table_exists(conn, "lp_apps")
    )


def _migrate_apps_schema(conn):
    now = _utc_now()
    app_cols = _table_columns(conn, "lp_app")
    additions = {
        "owner_user_id": "INTEGER",
        "description": "TEXT",
        "icon": "TEXT",
        "favorite": "INTEGER NOT NULL DEFAULT 0",
        "enabled": "INTEGER NOT NULL DEFAULT 1",
        "path": "TEXT",
        "repository_url": "TEXT",
        "website_url": "TEXT",
        "language": "TEXT",
        "version": "TEXT",
        "tags": "TEXT",
        "comments": "TEXT",
        "import_source": "TEXT",
        "import_source_path": "TEXT",
        "imported_date": "TEXT",
        "import_metadata": "TEXT",
        "last_used_date": "TEXT",
        "usage_count": "INTEGER NOT NULL DEFAULT 0",
        "created_date": "TEXT",
        "modified_date": "TEXT",
        "user_name": "TEXT",
        "rec_extract_date": "TEXT",
    }
    for col_name, col_type in additions.items():
        if col_name not in app_cols:
            conn.execute(f"ALTER TABLE lp_app ADD COLUMN {col_name} {col_type}")
    conn.execute("UPDATE lp_app SET kind = 'Other' WHERE COALESCE(kind, '') = ''")
    conn.execute("UPDATE lp_app SET enabled = 1 WHERE enabled IS NULL")
    conn.execute("UPDATE lp_app SET favorite = 0 WHERE favorite IS NULL")
    conn.execute("UPDATE lp_app SET usage_count = 0 WHERE usage_count IS NULL")
    conn.execute("UPDATE lp_app SET created_date = ? WHERE COALESCE(created_date, '') = ''", (now,))
    conn.execute("UPDATE lp_app SET modified_date = ? WHERE COALESCE(modified_date, '') = ''", (now,))
    if _table_exists(conn, "lp_app_action"):
        action_cols = _table_columns(conn, "lp_app_action")
        action_additions = {
            "parameter_schema_json": "TEXT",
            "agent_allowed": "INTEGER NOT NULL DEFAULT 0",
            "requires_confirmation": "INTEGER NOT NULL DEFAULT 1",
        }
        for col_name, col_type in action_additions.items():
            if col_name not in action_cols:
                conn.execute(f"ALTER TABLE lp_app_action ADD COLUMN {col_name} {col_type}")
        conn.execute("UPDATE lp_app_action SET agent_allowed = 0 WHERE agent_allowed IS NULL")
        conn.execute("UPDATE lp_app_action SET requires_confirmation = 1 WHERE requires_confirmation IS NULL")


def ensure_file_inventory_app(conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    now = _utc_now()
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "apps", "files", "scan.py"))
    workdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    schema = {
        "version": 1,
        "parameters": [
            {"name": "source_id", "label": "Source ID", "type": "integer", "required": True, "default": "1"},
            {"name": "scope", "label": "Scope", "type": "text", "required": False, "default": "/"},
            {
                "name": "mode",
                "label": "Mode",
                "type": "select",
                "required": True,
                "default": "AUTO",
                "options": ["AUTO", "FULL", "INCREMENTAL", "SCOPED"],
            },
        ],
    }
    row = conn.execute(
        "SELECT app_id FROM lp_app WHERE owner_user_id IS ? AND import_source = 'lifepim_builtin' "
        "AND import_source_path = 'apps.files.scan'",
        (owner_user_id,),
    ).fetchone()
    values = (
        owner_user_id,
        "LifePIM File Inventory Scanner",
        "Script",
        "Scans configured filesystem sources into the LifePIM File Inventory database.",
        "F",
        0,
        1,
        script_path,
        "",
        "",
        "Python",
        "",
        "files,file-inventory,scanner",
        "Built-in replacement for the legacy FileLister batch process.",
        "lifepim_builtin",
        "apps.files.scan",
        now,
        "{}",
        now,
        now,
        _current_user_name(),
        now,
    )
    if row:
        app_id = int(row["app_id"])
        conn.execute(
            "UPDATE lp_app SET owner_user_id = ?, title = ?, kind = ?, description = ?, icon = ?, "
            "favorite = ?, enabled = ?, path = ?, repository_url = ?, website_url = ?, language = ?, "
            "version = ?, tags = ?, comments = ?, import_source = ?, import_source_path = ?, "
            "imported_date = ?, import_metadata = ?, modified_date = ?, rec_extract_date = ? "
            "WHERE app_id = ?",
            values[:18] + (now, now, app_id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO lp_app "
            "(owner_user_id, title, kind, description, icon, favorite, enabled, path, repository_url, "
            "website_url, language, version, tags, comments, import_source, import_source_path, "
            "imported_date, import_metadata, created_date, modified_date, user_name, rec_extract_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values,
        )
        app_id = int(cur.lastrowid)
    action_values = (
        "Run File Scan",
        "EXECUTABLE",
        sys.executable,
        workdir,
        '-m apps.files.scan --source-id {source_id} --scope "{scope}" --mode {mode} --json',
        normalize_parameter_schema(schema),
        1,
        1,
        0,
        1,
        now,
    )
    action_row = conn.execute(
        "SELECT app_action_id FROM lp_app_action WHERE owner_user_id IS ? AND app_id = ? AND action_name = 'Run File Scan'",
        (owner_user_id, app_id),
    ).fetchone()
    if action_row:
        conn.execute(
            "UPDATE lp_app_action SET action_name = ?, action_type = ?, command = ?, working_directory = ?, "
            "arguments = ?, parameter_schema_json = ?, agent_allowed = ?, requires_confirmation = ?, "
            "sort_order = ?, is_default = ?, updated_utc = ? "
            "WHERE app_action_id = ?",
            action_values + (action_row["app_action_id"],),
        )
    else:
        conn.execute(
            "INSERT INTO lp_app_action "
            "(owner_user_id, app_id, action_name, action_type, command, working_directory, arguments, "
            "parameter_schema_json, agent_allowed, requires_confirmation, sort_order, is_default, created_utc, updated_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_user_id, app_id) + action_values[:-1] + (now, now),
        )
    conn.commit()
    return app_id


def normalize_kind(value):
    text = _clean_text(value)
    return text if text in APP_KIND_OPTIONS else "Other"


def normalize_action_type(value):
    text = _clean_text(value).upper()
    return text if text in ACTION_TYPE_OPTIONS else "SYSTEM_DEFAULT"


def normalize_parameter_schema(value):
    if isinstance(value, dict):
        raw = value
    else:
        text = _clean_text(value)
        if not text:
            return ""
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Parameter schema is not valid JSON: {exc.msg}.")
    if not isinstance(raw, dict):
        raise ValueError("Parameter schema must be a JSON object.")
    params = raw.get("parameters") or []
    if not isinstance(params, list):
        raise ValueError("Parameter schema parameters must be a list.")
    seen = set()
    cleaned = []
    for idx, param in enumerate(params, start=1):
        if not isinstance(param, dict):
            raise ValueError(f"Parameter {idx} must be an object.")
        name = _clean_text(param.get("name"))
        if not name:
            continue
        if not PARAMETER_NAME_RE.match(name):
            raise ValueError(f"Parameter name '{name}' must be a simple identifier.")
        if name in seen:
            raise ValueError(f"Parameter name '{name}' is duplicated.")
        seen.add(name)
        param_type = _clean_text(param.get("type")).lower() or "text"
        if param_type not in PARAMETER_TYPE_OPTIONS:
            raise ValueError(f"Parameter '{name}' has unsupported type '{param_type}'.")
        options = param.get("options") or []
        if isinstance(options, str):
            options = [part.strip() for part in options.replace("\n", ",").split(",") if part.strip()]
        if param_type == "select":
            if not isinstance(options, list) or not options:
                raise ValueError(f"Select parameter '{name}' must define options.")
            options = [_clean_text(option) for option in options if _clean_text(option)]
            if not options:
                raise ValueError(f"Select parameter '{name}' must define options.")
        else:
            options = []
        cleaned.append(
            {
                "name": name,
                "label": _clean_text(param.get("label")) or name.replace("_", " ").title(),
                "type": param_type,
                "required": 1 if _is_truthy(param.get("required")) else 0,
                "default": "" if param.get("default") is None else str(param.get("default")),
                "options": options,
            }
        )
    if not cleaned:
        return ""
    return json.dumps({"version": 1, "parameters": cleaned}, ensure_ascii=True, separators=(",", ":"))


def parameter_schema_from_json(value):
    normalized = normalize_parameter_schema(value)
    return json.loads(normalized) if normalized else {"version": 1, "parameters": []}


def action_has_parameters(action):
    try:
        return bool(parameter_schema_from_json(action.get("parameter_schema_json")).get("parameters"))
    except Exception:
        return bool(_clean_text(action.get("parameter_schema_json")))


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
        options.insert(0, {"area_id": area_id, "label": area_id, "icon": "", "selected": True})
    return options


def collection_options(selected_collection_ids=None, area_id=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    collections_mod.ensure_collections_schema(conn)
    selected = {int(value) for value in selected_collection_ids or [] if _clean_int(value) is not None}
    rows = collections_mod.get_collection_list(domain="apps", area_id=area_id, include_archived=False, conn=conn, owner_user_id=owner_user_id)
    return [
        {
            "collection_id": row["collection_id"],
            "label": row.get("collection_name") or "",
            "icon": row.get("icon") or "",
            "type_label": row.get("type_label") or "",
            "selected": int(row["collection_id"]) in selected,
        }
        for row in rows
    ]


def app_list(
    area_id=None,
    view_filter="all",
    query="",
    collection_id=None,
    sort_col="title",
    sort_dir="asc",
    limit=None,
    offset=None,
    conn=None,
    owner_user_id=None,
):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["a.owner_user_id IS ?", "a.enabled = 1"]
    _append_scope_filters(where, params, owner_user_id, area_id, view_filter, query, collection_id)
    order_by = _app_order_by(sort_col, sort_dir, view_filter)
    sql = _app_select_sql() + " WHERE " + " AND ".join(where) + " " + order_by
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    rows = conn.execute(sql, params).fetchall()
    return [_app_row(row, conn=conn, owner_user_id=owner_user_id) for row in rows]


def app_count(area_id=None, view_filter="all", query="", collection_id=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    params = [owner_user_id]
    where = ["a.owner_user_id IS ?", "a.enabled = 1"]
    _append_scope_filters(where, params, owner_user_id, area_id, view_filter, query, collection_id)
    row = conn.execute("SELECT COUNT(1) AS cnt FROM lp_app a WHERE " + " AND ".join(where), params).fetchone()
    return row["cnt"] if row else 0


def _append_scope_filters(where, params, owner_user_id, area_id, view_filter, query, collection_id):
    area_id = _clean_text(area_id)
    if area_id and area_id.lower() not in {"all", "all areas", "any", "unmapped"}:
        where.append(
            "EXISTS ("
            "SELECT 1 FROM lp_app_area aa "
            "WHERE aa.owner_user_id IS ? AND aa.app_id = a.app_id "
            "AND (lower(aa.area_id) = lower(?) "
            "OR lower(aa.area_id) LIKE lower(?) || '/%' "
            "OR lower(?) LIKE lower(aa.area_id) || '/%'))"
        )
        params.extend([owner_user_id, area_id, area_id, area_id])
    elif area_id.lower() == "unmapped":
        where.append(
            "NOT EXISTS (SELECT 1 FROM lp_app_area aa WHERE aa.owner_user_id IS ? AND aa.app_id = a.app_id)"
        )
        params.append(owner_user_id)

    view_filter = (_clean_text(view_filter) or "all").lower()
    if view_filter == "favorites":
        where.append("a.favorite = 1")
    elif view_filter == "recent":
        where.append("COALESCE(a.last_used_date, '') != ''")
    elif view_filter == "projects":
        where.append("a.kind IN (" + ",".join(["?"] * len(PROJECT_KINDS)) + ")")
        params.extend(sorted(PROJECT_KINDS))
    elif view_filter == "scripts":
        where.append("a.kind IN (" + ",".join(["?"] * len(SCRIPT_KINDS)) + ")")
        params.extend(sorted(SCRIPT_KINDS))
    elif view_filter == "applications":
        where.append("a.kind IN (" + ",".join(["?"] * len(APPLICATION_KINDS)) + ")")
        params.extend(sorted(APPLICATION_KINDS))

    terms = [_clean_text(part).lower() for part in query.split() if _clean_text(part)]
    for term in terms:
        like_value = f"%{term}%"
        where.append(
            "("
            "lower(COALESCE(a.title, '')) LIKE ? OR "
            "lower(COALESCE(a.description, '')) LIKE ? OR "
            "lower(COALESCE(a.kind, '')) LIKE ? OR "
            "lower(COALESCE(a.path, '')) LIKE ? OR "
            "lower(COALESCE(a.repository_url, '')) LIKE ? OR "
            "lower(COALESCE(a.website_url, '')) LIKE ? OR "
            "lower(COALESCE(a.language, '')) LIKE ? OR "
            "lower(COALESCE(a.tags, '')) LIKE ? OR "
            "EXISTS (SELECT 1 FROM lp_app_action ax WHERE ax.owner_user_id IS a.owner_user_id "
            "AND ax.app_id = a.app_id AND (lower(COALESCE(ax.command, '')) LIKE ? "
            "OR lower(COALESCE(ax.arguments, '')) LIKE ? "
            "OR lower(COALESCE(ax.action_name, '')) LIKE ?))"
            ")"
        )
        params.extend([like_value] * 11)

    collection_id = _clean_int(collection_id)
    if collection_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM lp_collection_item ci "
            "WHERE ci.owner_user_id IS ? AND ci.collection_id = ? "
            "AND ci.entry_kind = 'item' AND ci.item_type = 'app' AND ci.item_id = CAST(a.app_id AS TEXT))"
        )
        params.extend([owner_user_id, collection_id])


def _app_select_sql():
    return (
        "SELECT a.*, "
        "(SELECT COUNT(1) FROM lp_app_action x WHERE x.owner_user_id IS a.owner_user_id AND x.app_id = a.app_id) AS action_count "
        "FROM lp_app a"
    )


def _app_order_by(sort_col, sort_dir, view_filter):
    sort_dir = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    if (_clean_text(view_filter) or "").lower() == "recent":
        return "ORDER BY a.last_used_date DESC, lower(a.title)"
    allowed = {
        "title": "lower(a.title)",
        "kind": "a.kind",
        "last_used_date": "a.last_used_date",
        "favorite": "a.favorite",
        "usage_count": "a.usage_count",
    }
    return f"ORDER BY {allowed.get(sort_col, 'lower(a.title)')} {sort_dir}, a.app_id"


def app_get(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(_app_select_sql() + " WHERE a.app_id = ? AND a.owner_user_id IS ?", (app_id, owner_user_id)).fetchone()
    return _app_row(row, conn=conn, owner_user_id=owner_user_id) if row else None


def create_app(values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    title = _clean_text(values.get("title"))
    if not title:
        raise ValueError("App name is required.")
    now = _utc_now()
    cur = conn.execute(
        "INSERT INTO lp_app "
        "(owner_user_id, title, kind, description, icon, favorite, enabled, path, repository_url, website_url, "
        "language, version, tags, comments, import_source, import_source_path, imported_date, import_metadata, "
        "usage_count, created_date, modified_date, user_name, rec_extract_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
        (
            owner_user_id,
            title,
            normalize_kind(values.get("kind")),
            _clean_text(values.get("description")),
            _clean_text(values.get("icon")),
            1 if _is_truthy(values.get("favorite")) else 0,
            1 if _is_truthy(values.get("enabled", "1")) else 0,
            _clean_text(values.get("path")),
            _clean_text(values.get("repository_url")),
            _clean_text(values.get("website_url")),
            _clean_text(values.get("language")),
            _clean_text(values.get("version")),
            _clean_text(values.get("tags")),
            _clean_text(values.get("comments")),
            _clean_text(values.get("import_source")),
            _clean_text(values.get("import_source_path")),
            _clean_text(values.get("imported_date")),
            _clean_text(values.get("import_metadata")),
            now,
            now,
            _current_user_name(),
            now,
        ),
    )
    app_id = cur.lastrowid
    set_app_areas(app_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    set_app_actions(app_id, values.get("actions") or [], conn=conn, owner_user_id=owner_user_id)
    if "collection_ids" in values:
        set_app_collections(app_id, values.get("collection_ids") or [], conn=conn, owner_user_id=owner_user_id)
    conn.commit()
    _log_app_change(conn, "app_add", app_id, after=app_get(app_id, conn=conn, owner_user_id=owner_user_id))
    return app_id


def update_app(app_id, values, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = app_get(app_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    title = _clean_text(values.get("title"))
    if not title:
        raise ValueError("App name is required.")
    now = _utc_now()
    conn.execute(
        "UPDATE lp_app SET title = ?, kind = ?, description = ?, icon = ?, favorite = ?, enabled = ?, "
        "path = ?, repository_url = ?, website_url = ?, language = ?, version = ?, tags = ?, comments = ?, "
        "modified_date = ?, rec_extract_date = ? WHERE app_id = ? AND owner_user_id IS ?",
        (
            title,
            normalize_kind(values.get("kind")),
            _clean_text(values.get("description")),
            _clean_text(values.get("icon")),
            1 if _is_truthy(values.get("favorite")) else 0,
            1 if _is_truthy(values.get("enabled", "1")) else 0,
            _clean_text(values.get("path")),
            _clean_text(values.get("repository_url")),
            _clean_text(values.get("website_url")),
            _clean_text(values.get("language")),
            _clean_text(values.get("version")),
            _clean_text(values.get("tags")),
            _clean_text(values.get("comments")),
            now,
            now,
            app_id,
            owner_user_id,
        ),
    )
    set_app_areas(app_id, values.get("area_ids") or [], conn=conn, owner_user_id=owner_user_id)
    set_app_actions(app_id, values.get("actions") or [], conn=conn, owner_user_id=owner_user_id)
    if "collection_ids" in values:
        set_app_collections(app_id, values.get("collection_ids") or [], conn=conn, owner_user_id=owner_user_id)
    conn.commit()
    after = app_get(app_id, conn=conn, owner_user_id=owner_user_id)
    _log_app_change(conn, "app_update", app_id, before=before, after=after)
    return True


def delete_app(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    before = app_get(app_id, conn=conn, owner_user_id=owner_user_id)
    if not before:
        return False
    usage_count = task_count_for_app(app_id, conn=conn, owner_user_id=owner_user_id)
    if usage_count:
        raise ValueError(
            f"This App has actions used by {usage_count} Tasks and cannot be deleted. "
            "Remove or change those Task bindings first."
        )
    for entry in collections_mod.record_collections("app", app_id, domain="apps", conn=conn, owner_user_id=owner_user_id):
        collections_mod.remove_item_from_collection(entry["collection_item_id"], conn=conn, owner_user_id=owner_user_id)
    conn.execute("DELETE FROM lp_app_action WHERE owner_user_id IS ? AND app_id = ?", (owner_user_id, app_id))
    conn.execute("DELETE FROM lp_app_area WHERE owner_user_id IS ? AND app_id = ?", (owner_user_id, app_id))
    conn.execute("DELETE FROM lp_app WHERE owner_user_id IS ? AND app_id = ?", (owner_user_id, app_id))
    conn.commit()
    _log_app_change(conn, "app_delete", app_id, before=before, after=None)
    return True


def refresh_missing_executable_icons(conn=None, owner_user_id=None):
    from modules.apps.importers.exe_icons import get_executable_icon_value
    from modules.apps.importers.icon_media import materialize_app_icon_value
    from modules.apps.importers.windows_shortcuts import resolve_shortcut

    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT a.app_id, a.path, a.icon, "
        "(SELECT ax.command FROM lp_app_action ax WHERE ax.owner_user_id IS a.owner_user_id "
        "AND ax.app_id = a.app_id ORDER BY ax.is_default DESC, ax.sort_order, ax.app_action_id LIMIT 1) AS command, "
        "(SELECT ax.action_type FROM lp_app_action ax WHERE ax.owner_user_id IS a.owner_user_id "
        "AND ax.app_id = a.app_id ORDER BY ax.is_default DESC, ax.sort_order, ax.app_action_id LIMIT 1) AS action_type "
        "FROM lp_app a "
        "WHERE a.owner_user_id IS ? AND a.enabled = 1 "
        "AND (COALESCE(a.icon, '') = '' OR a.icon LIKE '/static/app_icons/%' OR a.icon LIKE 'static/app_icons/%')",
        (owner_user_id,),
    ).fetchall()
    updated = 0
    now = _utc_now()
    for row in rows:
        current_icon = _clean_text(row["icon"])
        icon = ""
        if current_icon:
            media_icon = materialize_app_icon_value(current_icon, conn=conn)
            if media_icon != current_icon or current_icon.startswith(("/media/", "media/")):
                icon = media_icon
        if not icon:
            target = _clean_text(row["command"]) or _clean_text(row["path"])
            action_type = _clean_text(row["action_type"]).upper()
            exe_path = ""
            if target.lower().endswith(".exe"):
                exe_path = target
            elif target.lower().endswith(".lnk"):
                info = resolve_shortcut(target)
                if info.is_valid and (info.target or "").lower().endswith(".exe"):
                    exe_path = info.target
            elif action_type == "EXECUTABLE":
                exe_path = target
            if not exe_path:
                continue
            extracted = get_executable_icon_value(exe_path)
            icon = materialize_app_icon_value(extracted, conn=conn) if extracted else ""
            if not icon:
                continue
        if icon == current_icon:
            continue
        cur = conn.execute(
            "UPDATE lp_app SET icon = ?, modified_date = ?, rec_extract_date = ? "
            "WHERE owner_user_id IS ? AND app_id = ?",
            (icon, now, now, owner_user_id, row["app_id"]),
        )
        updated += max(cur.rowcount or 0, 0)
    conn.commit()
    return updated


def set_app_areas(app_id, area_ids, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
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
    conn.execute("DELETE FROM lp_app_area WHERE owner_user_id IS ? AND app_id = ?", (owner_user_id, app_id))
    for idx, area_id in enumerate(cleaned):
        conn.execute(
            "INSERT OR IGNORE INTO lp_app_area (owner_user_id, app_id, area_id, sort_order, created_utc) VALUES (?, ?, ?, ?, ?)",
            (owner_user_id, app_id, area_id, idx * 10, now),
        )


def set_app_actions(app_id, actions, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    now = _utc_now()
    current_rows = conn.execute(
        "SELECT * FROM lp_app_action WHERE owner_user_id IS ? AND app_id = ?",
        (owner_user_id, app_id),
    ).fetchall()
    current_ids = {int(row["app_action_id"]) for row in current_rows}
    cleaned = []
    for idx, action in enumerate(actions or []):
        name = _clean_text(action.get("action_name"))
        command = _clean_text(action.get("command"))
        if not name and not command:
            continue
        action_id = _clean_int(action.get("app_action_id"))
        cleaned.append(
            {
                "app_action_id": action_id if action_id in current_ids else None,
                "action_name": name or "Open",
                "action_type": normalize_action_type(action.get("action_type")),
                "command": command,
                "working_directory": _clean_text(action.get("working_directory")),
                "arguments": _clean_text(action.get("arguments")),
                "parameter_schema_json": normalize_parameter_schema(action.get("parameter_schema_json") or action.get("parameter_schema")),
                "agent_allowed": 1 if _is_truthy(action.get("agent_allowed")) else 0,
                "requires_confirmation": 0 if action.get("requires_confirmation") in (0, False, "0", "false", "off", "no") else 1,
                "sort_order": _clean_int(action.get("sort_order"), idx * 10) or idx * 10,
                "is_default": 1 if _is_truthy(action.get("is_default")) else 0,
            }
        )
    if cleaned and not any(action["is_default"] for action in cleaned):
        cleaned[0]["is_default"] = 1
    submitted_ids = {action["app_action_id"] for action in cleaned if action.get("app_action_id")}
    delete_ids = current_ids - submitted_ids
    for action_id in sorted(delete_ids):
        usage_count = task_count_for_action(action_id, conn=conn, owner_user_id=owner_user_id)
        if usage_count:
            raise ValueError(
                f"This action is used by {usage_count} Tasks and cannot be deleted. "
                "Remove or change those Task bindings first."
            )
        conn.execute(
            "DELETE FROM lp_app_action WHERE owner_user_id IS ? AND app_id = ? AND app_action_id = ?",
            (owner_user_id, app_id, action_id),
        )
    for action in cleaned:
        if action.get("app_action_id"):
            conn.execute(
                "UPDATE lp_app_action SET action_name = ?, action_type = ?, command = ?, working_directory = ?, "
                "arguments = ?, parameter_schema_json = ?, agent_allowed = ?, requires_confirmation = ?, "
                "sort_order = ?, is_default = ?, updated_utc = ? "
                "WHERE owner_user_id IS ? AND app_id = ? AND app_action_id = ?",
                (
                    action["action_name"],
                    action["action_type"],
                    action["command"],
                    action["working_directory"],
                    action["arguments"],
                    action["parameter_schema_json"],
                    action["agent_allowed"],
                    action["requires_confirmation"],
                    action["sort_order"],
                    action["is_default"],
                    now,
                    owner_user_id,
                    app_id,
                    action["app_action_id"],
                ),
            )
        else:
            conn.execute(
                "INSERT INTO lp_app_action "
                "(owner_user_id, app_id, action_name, action_type, command, working_directory, arguments, "
                "parameter_schema_json, agent_allowed, requires_confirmation, sort_order, is_default, created_utc, updated_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    owner_user_id,
                    app_id,
                    action["action_name"],
                    action["action_type"],
                    action["command"],
                    action["working_directory"],
                    action["arguments"],
                    action["parameter_schema_json"],
                    action["agent_allowed"],
                    action["requires_confirmation"],
                    action["sort_order"],
                    action["is_default"],
                    now,
                    now,
                ),
            )


def set_app_collections(app_id, collection_ids, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    collections_mod.ensure_collections_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    selected = {_clean_int(value) for value in collection_ids or []}
    selected.discard(None)
    current = collections_mod.record_collections("app", app_id, domain="apps", conn=conn, owner_user_id=owner_user_id)
    for entry in current:
        if int(entry["collection_id"]) not in selected:
            collections_mod.remove_item_from_collection(entry["collection_item_id"], conn=conn, owner_user_id=owner_user_id)
    current_ids = {int(entry["collection_id"]) for entry in current}
    for collection_id in selected - current_ids:
        collections_mod.add_item_to_collection(collection_id, "app", app_id, conn=conn, owner_user_id=owner_user_id)


def list_app_areas(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT aa.*, ar.area_name, ar.icon "
        "FROM lp_app_area aa "
        "LEFT JOIN lp_areas ar ON ar.owner_user_id IS aa.owner_user_id AND lower(ar.area_id) = lower(aa.area_id) "
        "WHERE aa.owner_user_id IS ? AND aa.app_id = ? "
        "ORDER BY aa.sort_order, lower(COALESCE(ar.area_name, aa.area_id))",
        (owner_user_id, app_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_app_actions(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT * FROM lp_app_action WHERE owner_user_id IS ? AND app_id = ? ORDER BY is_default DESC, sort_order, app_action_id",
        (owner_user_id, app_id),
    ).fetchall()
    return [dict(row) for row in rows]


def app_action_get(action_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    row = conn.execute(
        "SELECT ax.*, a.title AS app_title, a.kind AS app_kind "
        "FROM lp_app_action ax "
        "JOIN lp_app a ON a.owner_user_id IS ax.owner_user_id AND a.app_id = ax.app_id "
        "WHERE ax.owner_user_id IS ? AND ax.app_action_id = ?",
        (owner_user_id, action_id),
    ).fetchone()
    return dict(row) if row else None


def app_action_options(conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT ax.app_action_id, ax.action_name, ax.parameter_schema_json, a.app_id, a.title AS app_title "
        "FROM lp_app_action ax "
        "JOIN lp_app a ON a.owner_user_id IS ax.owner_user_id AND a.app_id = ax.app_id "
        "WHERE ax.owner_user_id IS ? AND a.enabled = 1 "
        "ORDER BY lower(a.title), ax.is_default DESC, ax.sort_order, lower(ax.action_name)",
        (owner_user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def task_count_for_action(action_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if not _table_exists(conn, "lp_tasks") or "app_action_id" not in _table_columns(conn, "lp_tasks"):
        return 0
    params = [action_id]
    where = "app_action_id = ?"
    if "owner_user_id" in _table_columns(conn, "lp_tasks"):
        where += " AND owner_user_id IS ?"
        params.append(owner_user_id)
    row = conn.execute(f"SELECT COUNT(1) AS cnt FROM lp_tasks WHERE {where}", params).fetchone()
    return row["cnt"] if row else 0


def task_count_for_app(app_id, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    if not _table_exists(conn, "lp_tasks") or "app_action_id" not in _table_columns(conn, "lp_tasks"):
        return 0
    params = [owner_user_id, app_id]
    owner_clause = ""
    if "owner_user_id" in _table_columns(conn, "lp_tasks"):
        owner_clause = "AND t.owner_user_id IS ?"
        params.append(owner_user_id)
    row = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_tasks t "
        "JOIN lp_app_action ax ON ax.app_action_id = t.app_action_id "
        "WHERE ax.owner_user_id IS ? AND ax.app_id = ? " + owner_clause,
        params,
    ).fetchone()
    return row["cnt"] if row else 0


def area_counts(conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    rows = conn.execute(
        "SELECT area_id, COUNT(1) AS item_count FROM lp_app_area aa "
        "WHERE aa.owner_user_id IS ? "
        "AND EXISTS (SELECT 1 FROM lp_app a WHERE a.owner_user_id IS aa.owner_user_id AND a.app_id = aa.app_id AND a.enabled = 1) "
        "GROUP BY area_id",
        (owner_user_id,),
    ).fetchall()
    return {row["area_id"]: row["item_count"] for row in rows}


def launch_action(app_id, action_id=None, parameter_values=None, conn=None, owner_user_id=None):
    conn = _get_conn(conn)
    ensure_apps_schema(conn)
    owner_user_id = _owner_user_id(owner_user_id)
    app = app_get(app_id, conn=conn, owner_user_id=owner_user_id)
    if not app:
        raise ValueError("App not found.")
    action = None
    for candidate in app.get("actions", []):
        if action_id and candidate["app_action_id"] == action_id:
            action = candidate
            break
        if not action_id and candidate.get("is_default"):
            action = candidate
    if not action and app.get("actions"):
        action = app["actions"][0]
    if not action:
        raise ValueError("No launch action is configured.")
    action = dict(action)
    action["arguments"] = render_argument_template(
        action.get("arguments"),
        action.get("parameter_schema_json"),
        parameter_values or {},
    )
    _execute_action(action)
    now = _utc_now()
    conn.execute(
        "UPDATE lp_app SET last_used_date = ?, usage_count = COALESCE(usage_count, 0) + 1, modified_date = ? "
        "WHERE owner_user_id IS ? AND app_id = ?",
        (now, now, owner_user_id, app_id),
    )
    conn.commit()
    return action


def validate_parameter_values(parameter_schema_json, values):
    schema = parameter_schema_from_json(parameter_schema_json)
    values = values or {}
    cleaned = {}
    for param in schema.get("parameters", []):
        name = param["name"]
        raw_value = values.get(name)
        if raw_value in (None, ""):
            raw_value = param.get("default", "")
        if param.get("required") and raw_value in (None, ""):
            raise ValueError(f"Parameter '{param.get('label') or name}' is required.")
        param_type = param.get("type") or "text"
        if param_type == "boolean":
            cleaned[name] = bool(_is_truthy(raw_value))
            continue
        if raw_value in (None, ""):
            cleaned[name] = ""
            continue
        if param_type == "integer":
            try:
                cleaned[name] = int(raw_value)
            except (TypeError, ValueError):
                raise ValueError(f"Parameter '{param.get('label') or name}' must be an integer.")
        elif param_type == "number":
            try:
                cleaned[name] = float(raw_value)
            except (TypeError, ValueError):
                raise ValueError(f"Parameter '{param.get('label') or name}' must be a number.")
        elif param_type == "select":
            text = str(raw_value)
            if text not in (param.get("options") or []):
                raise ValueError(f"Parameter '{param.get('label') or name}' must be one of: {', '.join(param.get('options') or [])}.")
            cleaned[name] = text
        else:
            cleaned[name] = str(raw_value)
    return cleaned


def default_parameter_values(parameter_schema_json, existing_values=None):
    schema = parameter_schema_from_json(parameter_schema_json)
    existing_values = existing_values or {}
    values = {}
    for param in schema.get("parameters", []):
        name = param["name"]
        values[name] = existing_values[name] if name in existing_values else param.get("default", "")
    return values


def parameter_values_from_form(form, parameter_schema_json, prefix="param_"):
    schema = parameter_schema_from_json(parameter_schema_json)
    values = {}
    for param in schema.get("parameters", []):
        name = param["name"]
        field_name = prefix + name
        if param.get("type") == "boolean":
            values[name] = 1 if form.get(field_name) else 0
        else:
            values[name] = form.get(field_name, "")
    return values


def render_argument_template(arguments, parameter_schema_json, parameter_values):
    arguments = _clean_text(arguments)
    schema = parameter_schema_from_json(parameter_schema_json)
    if not schema.get("parameters") and not parameter_values:
        return arguments
    if not arguments:
        validate_parameter_values(parameter_schema_json, parameter_values)
        return ""
    values = validate_parameter_values(parameter_schema_json, parameter_values)
    allowed = {param["name"] for param in schema.get("parameters", [])}
    placeholders = set(PLACEHOLDER_RE.findall(arguments))
    unknown = sorted(placeholders - allowed)
    if unknown:
        raise ValueError(f"Unknown argument placeholder(s): {', '.join(unknown)}.")

    def replace(match):
        value = values.get(match.group(1), "")
        return str(value)

    return PLACEHOLDER_RE.sub(replace, arguments)


def split_arguments(arguments):
    parts = shlex.split(_clean_text(arguments), posix=False) if _clean_text(arguments) else []
    stripped = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in {"'", '"'}:
            stripped.append(part[1:-1])
        else:
            stripped.append(part)
    return stripped


def _execute_action(action):
    action_type = normalize_action_type(action.get("action_type"))
    target = _clean_text(action.get("command"))
    arguments = _clean_text(action.get("arguments"))
    cwd = _clean_text(action.get("working_directory")) or None
    if not target:
        raise ValueError("Action target is empty.")
    if action_type == "OPEN_URL":
        webbrowser.open(target)
        return
    if action_type == "OPEN_FOLDER":
        if not os.path.isdir(target):
            raise ValueError(f"Folder not found: {target}")
        os.startfile(target)
        return
    if action_type == "OPEN_FILE":
        if _is_web_url(target):
            webbrowser.open(target)
            return
        if not os.path.exists(target):
            raise ValueError(f"File not found: {target}")
        os.startfile(target)
        return
    if action_type == "EXECUTABLE":
        cmd = [target] + split_arguments(arguments)
        subprocess.Popen(cmd, cwd=cwd or None)
        return
    if action_type == "COMMAND":
        command = target if not arguments else f"{target} {arguments}"
        subprocess.Popen(command, cwd=cwd or None, shell=True)
        return
    if _is_web_url(target):
        webbrowser.open(target)
        return
    if not os.path.exists(target) and arguments:
        subprocess.Popen([target] + split_arguments(arguments), cwd=cwd or None)
        return
    os.startfile(target)


def _is_web_url(value):
    return value.lower().startswith(("http://", "https://"))


def _app_row(row, conn=None, owner_user_id=None):
    if not row:
        return None
    app = dict(row)
    app["id"] = app["app_id"]
    app["icon_image_url"] = _icon_image_url(app.get("icon"))
    app["kind_icon"] = "" if app["icon_image_url"] else (app.get("icon") or _default_icon(app.get("kind")))
    app["areas"] = list_app_areas(app["app_id"], conn=conn, owner_user_id=owner_user_id)
    app["area_ids"] = [area["area_id"] for area in app["areas"]]
    app["area_label"] = ", ".join(area.get("area_name") or area.get("area_id") or "" for area in app["areas"])
    app["actions"] = list_app_actions(app["app_id"], conn=conn, owner_user_id=owner_user_id)
    app["default_action"] = next((action for action in app["actions"] if action.get("is_default")), app["actions"][0] if app["actions"] else None)
    app["collections"] = collections_mod.record_collections("app", app["app_id"], domain="apps", conn=conn, owner_user_id=owner_user_id)
    app["collection_ids"] = [entry["collection_id"] for entry in app["collections"]]
    return app


def _icon_image_url(icon):
    text = _clean_text(icon)
    if text.startswith("/static/") or text.startswith("/media/"):
        return text
    if text.startswith("static/") or text.startswith("media/"):
        return "/" + text
    return ""


def _default_icon(kind):
    return {
        "Application": "A",
        "Development Project": "P",
        "Repository": "R",
        "Script": "S",
        "Executable": "E",
        "Command": ">",
        "Web App": "W",
        "Website": "W",
        "Database": "DB",
        "SQL Script": "SQL",
        "Development Environment": "IDE",
        "Service": "SV",
        "Connection": "CN",
        "Utility": "U",
    }.get(kind, "App")


def _log_app_change(conn, action, app_id, before=None, after=None):
    try:
        utils_mod.lg_usr(
            action=action,
            entity_type="lp_app",
            entity_id=app_id,
            before=before,
            after=after,
            context_type="apps",
            context_id=str(app_id),
            conn=conn,
        )
    except Exception:
        pass
