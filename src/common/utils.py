from datetime import datetime
import json
import math
import common.config as mod_cfg
from common import data as db

def format_date(dt):
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M")


def get_tabs():
    return mod_cfg.TABS


def _fetch_mapping_tabs():
    try:
        rows = db.get_data(
            db.conn,
            "map_folder_project",
            ["tab"],
            "is_enabled = 1 AND is_primary = 1",
            [],
        )
    except Exception:
        return []
    tabs = []
    for row in rows:
        tab = (row["tab"] or "").strip()
        if tab and tab not in tabs:
            tabs.append(tab)
    return tabs


def _norm_tab_value(value):
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _tab_leaf(value, group_tokens):
    text = (value or "").strip()
    if not text:
        return ""
    if ">" in text:
        return text.split(">")[-1].strip()
    if "/" in text:
        return text.split("/")[-1].strip()
    parts = text.split()
    if len(parts) > 1 and parts[0].upper() in group_tokens:
        return " ".join(parts[1:]).strip()
    return text


def get_side_tabs():
    return list(mod_cfg.SIDE_TABS)

def get_table_def(route_id):
    for tbl in mod_cfg.table_def:
        if tbl.get("route") == route_id:
            return tbl
    return None


def build_form_fields(col_list):
    fields = []
    for col in col_list:
        col_lower = col.lower()
        input_type = "text"
        is_textarea = False
        if "date" in col_lower:
            input_type = "date"
        if col_lower in ("description", "content", "col_list", "path"):
            is_textarea = True
        fields.append(
            {
                "name": col,
                "label": col.replace("_", " ").title(),
                "input_type": input_type,
                "is_textarea": is_textarea,
            }
        )
    return fields


def paginate_items(items, page, per_page):
    per_page = max(1, int(per_page or 1))
    total = len(items)
    total_pages = max(1, int(math.ceil(total / per_page))) if total else 1
    page = int(page or 1)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "total_pages": total_pages,
        "page_numbers": list(range(1, total_pages + 1)),
        "total": total,
    }


def paginate_total(total, page, per_page):
    per_page = max(1, int(per_page or 1))
    total_pages = max(1, int(math.ceil(total / per_page))) if total else 1
    page = int(page or 1)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    return {
        "page": page,
        "total_pages": total_pages,
        "page_numbers": list(range(1, total_pages + 1)),
        "total": total,
    }


def build_pagination(url_for_fn, route_name, base_args, page, total_pages):
    pages = []
    for num in range(1, total_pages + 1):
        args = dict(base_args)
        args["page"] = num
        pages.append({"num": num, "url": url_for_fn(route_name, **args), "current": num == page})
    first_args = dict(base_args)
    first_args["page"] = 1
    last_args = dict(base_args)
    last_args["page"] = total_pages
    return {
        "pages": pages,
        "first_url": url_for_fn(route_name, **first_args),
        "last_url": url_for_fn(route_name, **last_args),
    }


_USER_LOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sys_user_log (
    id INTEGER PRIMARY KEY,
    log_date TEXT NOT NULL,
    user_name TEXT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    context_type TEXT,
    context_id TEXT,
    details TEXT
);
"""


def _ensure_user_log_schema(conn):
    conn.execute(_USER_LOG_SCHEMA_SQL)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_sys_user_log_entity "
        "ON sys_user_log(entity_type, entity_id)"
    )


def ensure_user_log_schema(conn=None):
    conn = db._get_conn() if conn is None else conn
    _ensure_user_log_schema(conn)


def _json_blob(value):
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=True, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=True)


def lg_usr(
    action,
    entity_type,
    entity_id=None,
    before=None,
    after=None,
    context_type=None,
    context_id=None,
    extra=None,
    conn=None,
    user_name=None,
):
    conn = db._get_conn() if conn is None else conn
    _ensure_user_log_schema(conn)
    payload = _json_blob(extra)
    conn.execute(
        (
            "INSERT INTO sys_user_log "
            "(log_date, user_name, action, entity_type, entity_id, before_json, after_json, "
            "context_type, context_id, details) "
            "VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            user_name or db._current_user(),
            (action or "").strip(),
            (entity_type or "").strip(),
            None if entity_id is None else str(entity_id),
            _json_blob(before),
            _json_blob(after),
            context_type,
            context_id,
            payload,
        ),
    )
    conn.commit()

