from datetime import datetime
import json

from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common import config as cfg
from common.utils import get_tabs, get_side_tabs, ensure_user_log_schema, lg_usr


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
    static_folder="static",
)


_REBUILD_SQL = """
DELETE FROM map_project_folder;

INSERT INTO map_project_folder (
  folder_id, tab, grp, project, tags, confidence,
  matched_prefix, rule_map_id, is_primary, is_enabled, updated_at
)
SELECT
  f.folder_id,
  r.tab,
  r.grp,
  COALESCE(r.project,''),
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
      WHERE r2.is_enabled=1
        AND r2.is_primary=1
        AND lower(f.folder_path) LIKE lower(r2.path_prefix) || '%'
      ORDER BY LENGTH(r2.path_prefix) DESC,
               r2.priority DESC,
               r2.confidence DESC,
               r2.map_id DESC
      LIMIT 1
  );
"""


@admin_bp.route("/", methods=["GET", "POST"])
def admin_mapping_route():
    message = ""
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "rebuild":
            conn = db.conn if db.conn is not None else None
            conn = db._get_conn() if conn is None else conn
            conn.executescript(_REBUILD_SQL)
            conn.commit()
            message = "Rebuilt folder cache."

    unmapped_only = request.args.get("unmapped") == "1"
    rules = []
    folders = []
    counts = {}
    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    try:
        counts["map_folder_project"] = conn.execute("SELECT COUNT(1) FROM map_folder_project").fetchone()[0]
        counts["map_project_folder"] = conn.execute("SELECT COUNT(1) FROM map_project_folder").fetchone()[0]
        counts["dim_folder"] = conn.execute("SELECT COUNT(1) FROM dim_folder").fetchone()[0]
        rules = conn.execute(
            """
            SELECT map_id, path_prefix, tab, grp, project, tags, confidence, priority, is_primary, is_enabled
            FROM map_folder_project
            ORDER BY tab, grp, path_prefix
            """
        ).fetchall()
        if unmapped_only:
            folders = conn.execute(
                """
                SELECT f.folder_id, f.folder_path, f.is_active, f.last_seen_at
                FROM dim_folder f
                LEFT JOIN map_project_folder mpf
                  ON mpf.folder_id = f.folder_id
                 AND mpf.is_primary = 1
                 AND mpf.is_enabled = 1
                WHERE mpf.folder_id IS NULL
                ORDER BY f.folder_path
                """
            ).fetchall()
        else:
            folders = conn.execute(
                """
                SELECT folder_id, folder_path, is_active, last_seen_at
                FROM dim_folder
                ORDER BY folder_path
                """
            ).fetchall()
    except Exception:
        rules = []
        folders = []
        counts = {}

    return render_template(
        "admin_mapping.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin - Folder Mapping",
        content_html="",
        message=message,
        rules=rules,
        folders=folders,
        counts=counts,
        db_file=cfg.DB_FILE,
        unmapped_only=unmapped_only,
        now=datetime.now(),
    )


def _load_json(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _fetch_row(conn, table, record_id, id_col="id"):
    if not table or record_id is None:
        return None
    row = conn.execute(
        f"SELECT * FROM {table} WHERE {id_col} = ?",
        [record_id],
    ).fetchone()
    return dict(row) if row else None


def _record_exists(conn, table, record_id, id_col="id"):
    if not table or record_id is None:
        return False
    row = conn.execute(
        f"SELECT 1 FROM {table} WHERE {id_col} = ? LIMIT 1",
        [record_id],
    ).fetchone()
    return row is not None


def _insert_row(conn, table, row_dict):
    if not table or not isinstance(row_dict, dict) or not row_dict:
        return False
    cols = [col for col in row_dict.keys() if col]
    if not cols:
        return False
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    values = [row_dict.get(col) for col in cols]
    conn.execute(sql, values)
    return True


def _update_row(conn, table, row_dict, id_col="id"):
    if not table or not isinstance(row_dict, dict) or not row_dict:
        return False
    record_id = row_dict.get(id_col)
    if record_id is None:
        return False
    cols = [col for col in row_dict.keys() if col and col != id_col]
    if not cols:
        return False
    set_clause = ", ".join([f"{col} = ?" for col in cols])
    sql = f"UPDATE {table} SET {set_clause} WHERE {id_col} = ?"
    values = [row_dict.get(col) for col in cols] + [record_id]
    cur = conn.execute(sql, values)
    return cur.rowcount > 0


def _is_undoable(entry):
    action = (entry.get("action") or "").lower()
    if action in {"add", "update", "delete", "link_create", "link_update", "link_delete"}:
        return True
    return False


def _undo_log_entry(conn, entry):
    action = (entry.get("action") or "").lower()
    entity_type = entry.get("entity_type") or ""
    entity_id = entry.get("entity_id")
    before = _load_json(entry.get("before_json"))
    after = _load_json(entry.get("after_json"))
    before_state = None
    after_state = None

    try:
        if entity_type == "lp_links":
            link_id = entity_id
            if isinstance(after, dict) and after.get("link_id") is not None:
                link_id = after.get("link_id")
            if isinstance(before, dict) and before.get("link_id") is not None:
                link_id = before.get("link_id")
            if link_id is None:
                return False, "Missing link id."
            before_state = _fetch_row(conn, "lp_links", link_id, id_col="link_id")
            if action == "link_create":
                conn.execute("DELETE FROM lp_links WHERE link_id = ?", [link_id])
            elif action == "link_delete":
                if not isinstance(before, dict):
                    return False, "Missing link snapshot."
                _insert_row(conn, "lp_links", before)
            elif action == "link_update":
                if not isinstance(before, dict):
                    return False, "Missing link snapshot."
                if _record_exists(conn, "lp_links", link_id, id_col="link_id"):
                    _update_row(conn, "lp_links", before, id_col="link_id")
                else:
                    _insert_row(conn, "lp_links", before)
            else:
                return False, "Undo not supported for this link action."
            after_state = _fetch_row(conn, "lp_links", link_id, id_col="link_id")
        else:
            record_id = entity_id
            if isinstance(after, dict) and after.get("id") is not None:
                record_id = after.get("id")
            if isinstance(before, dict) and before.get("id") is not None:
                record_id = before.get("id")
            if record_id is None:
                return False, "Missing record id."
            before_state = _fetch_row(conn, entity_type, record_id, id_col="id")
            if action == "add":
                conn.execute(f"DELETE FROM {entity_type} WHERE id = ?", [record_id])
            elif action == "delete":
                if not isinstance(before, dict):
                    return False, "Missing record snapshot."
                _insert_row(conn, entity_type, before)
            elif action == "update":
                if not isinstance(before, dict):
                    return False, "Missing record snapshot."
                if _record_exists(conn, entity_type, record_id, id_col="id"):
                    _update_row(conn, entity_type, before, id_col="id")
                else:
                    _insert_row(conn, entity_type, before)
            else:
                return False, "Undo not supported for this action."
            after_state = _fetch_row(conn, entity_type, record_id, id_col="id")
        conn.commit()
        lg_usr(
            action=f"undo_{action}",
            entity_type=entity_type,
            entity_id=entity_id,
            before=before_state,
            after=after_state,
            context_type="user_history",
            context_id=str(entry.get("id")),
            conn=conn,
        )
        return True, f"Undid {action} for {entity_type}."
    except Exception as exc:
        return False, f"Undo failed: {exc}"


@admin_bp.route("/user-history", methods=["GET", "POST"])
def user_history_route():
    message = ""
    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    ensure_user_log_schema(conn)
    sort_col = request.args.get("sort") or "id"
    dir_param = request.args.get("dir")
    if not dir_param:
        sort_dir = "desc"
    else:
        sort_dir = "desc" if dir_param.lower() == "desc" else "asc"
    order_map = {
        "id": "id",
        "log_date": "log_date",
        "user_name": "user_name",
        "action": "action",
        "entity_type": "entity_type",
        "entity_id": "entity_id",
        "context_type": "context_type",
        "context_id": "context_id",
    }
    order_by = order_map.get(sort_col, "id")
    if request.method == "POST":
        action = request.form.get("action", "")
        log_id = request.form.get("log_id", "")
        if action == "undo" and log_id:
            row = conn.execute(
                "SELECT id, log_date, user_name, action, entity_type, entity_id, before_json, after_json, "
                "context_type, context_id, details "
                "FROM sys_user_log WHERE id = ?",
                [log_id],
            ).fetchone()
            if row:
                ok, msg = _undo_log_entry(conn, dict(row))
                message = msg
            else:
                message = "Log entry not found."
    limit = request.args.get("limit", type=int) or 200
    rows = conn.execute(
        "SELECT id, log_date, user_name, action, entity_type, entity_id, before_json, after_json, "
        "context_type, context_id, details "
        f"FROM sys_user_log ORDER BY {order_by} {sort_dir} LIMIT ?",
        [limit],
    ).fetchall()
    entries = [dict(row) for row in rows]
    for entry in entries:
        entry["undoable"] = _is_undoable(entry)

    return render_template(
        "admin_user_history.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin - User History",
        content_html="",
        message=message,
        entries=entries,
        limit=limit,
        sort_col=sort_col,
        sort_dir=sort_dir,
        now=datetime.now(),
    )
