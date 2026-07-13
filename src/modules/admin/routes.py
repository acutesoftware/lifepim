from datetime import datetime
import json

from flask import Blueprint, abort, render_template, request, redirect, url_for

from common import data as db
from common import config as cfg
from common import media_migration
from common import note_search_index
from common import settings as settings_mod
from common.utils import get_tabs, get_side_tabs, ensure_user_log_schema, lg_usr, paginate_total, build_pagination
from modules.calendar.services import calendar_index
from core import security


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
    security.require_role("admin")
    message = request.args.get("message", "")
    active_admin_tab = (request.args.get("tab") or request.form.get("tab") or "security").strip().lower()
    if active_admin_tab not in {"security", "folder_mapping", "folders", "migration"}:
        active_admin_tab = "security"

    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "rebuild":
            active_admin_tab = "folder_mapping"
            conn.executescript(_REBUILD_SQL)
            conn.commit()
            message = "Rebuilt folder cache."
        elif active_admin_tab == "migration":
            image_where = request.form.get("image_where", "")
            audio_where = request.form.get("audio_where", "")
            try:
                settings_mod.set_setting(
                    cfg.CONFIG_SETTING_PREFIX + "FILELIST_IMAGE_WHERE",
                    cfg.serialize_config_value(image_where),
                    "Config",
                    "FILELIST_IMAGE_WHERE",
                    conn,
                )
                settings_mod.set_setting(
                    cfg.CONFIG_SETTING_PREFIX + "FILELIST_AUDIO_WHERE",
                    cfg.serialize_config_value(audio_where),
                    "Config",
                    "FILELIST_AUDIO_WHERE",
                    conn,
                )
                cfg.refresh_config_overrides()
                if action == "migrate_images":
                    result = media_migration.migrate_images_from_filelist(where_clause=image_where, conn=conn)
                    message = (
                        f"Media migrated from {result['source_table']} and {result['video_source_table']}: "
                        f"{result['total_inserted']} rows ({result['inserted']} images, "
                        f"{result['video_inserted']} videos)."
                    )
                elif action == "migrate_audio":
                    result = media_migration.migrate_audio_from_filelist(where_clause=audio_where, conn=conn)
                    message = f"Audio migrated from {result['source_table']}: {result['inserted']} rows."
                elif action == "save_media_filters":
                    message = "Media migration filters saved."
            except Exception as exc:
                message = f"Media migration failed: {exc}"

    per_page = 200
    page = request.args.get("page", type=int) or 1
    unmapped_only = request.args.get("unmapped") == "1"
    rules = []
    folders = []
    counts = {}
    rules_total = 0
    folders_total = 0
    page_data = paginate_total(0, 1, per_page)
    pagination = build_pagination(url_for, "admin.admin_mapping_route", {"tab": active_admin_tab}, 1, 1)
    try:
        counts["map_folder_project"] = conn.execute("SELECT COUNT(1) FROM map_folder_project").fetchone()[0]
        counts["map_project_folder"] = conn.execute("SELECT COUNT(1) FROM map_project_folder").fetchone()[0]
        counts["dim_folder"] = conn.execute("SELECT COUNT(1) FROM dim_folder").fetchone()[0]
        if active_admin_tab == "folder_mapping":
            rules_total = counts["map_folder_project"]
            page_data = paginate_total(rules_total, page, per_page)
            offset = (page_data["page"] - 1) * per_page
            rules = conn.execute(
                """
                SELECT map_id, path_prefix, tab, grp, project, tags, confidence, priority, is_primary, is_enabled
                FROM map_folder_project
                ORDER BY tab, grp, path_prefix
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            ).fetchall()
            pagination = build_pagination(
                url_for,
                "admin.admin_mapping_route",
                {"tab": "folder_mapping"},
                page_data["page"],
                page_data["total_pages"],
            )
        if active_admin_tab == "folders" and unmapped_only:
            folders_total = conn.execute(
                """
                SELECT COUNT(1)
                FROM dim_folder f
                LEFT JOIN map_project_folder mpf
                  ON mpf.folder_id = f.folder_id
                 AND mpf.is_primary = 1
                 AND mpf.is_enabled = 1
                WHERE mpf.folder_id IS NULL
                """
            ).fetchone()[0]
            page_data = paginate_total(folders_total, page, per_page)
            offset = (page_data["page"] - 1) * per_page
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
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            ).fetchall()
            pagination = build_pagination(
                url_for,
                "admin.admin_mapping_route",
                {"tab": "folders", "unmapped": 1},
                page_data["page"],
                page_data["total_pages"],
            )
        elif active_admin_tab == "folders":
            folders_total = counts["dim_folder"]
            page_data = paginate_total(folders_total, page, per_page)
            offset = (page_data["page"] - 1) * per_page
            folders = conn.execute(
                """
                SELECT folder_id, folder_path, is_active, last_seen_at
                FROM dim_folder
                ORDER BY folder_path
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            ).fetchall()
            pagination = build_pagination(
                url_for,
                "admin.admin_mapping_route",
                {"tab": "folders"},
                page_data["page"],
                page_data["total_pages"],
            )
    except Exception:
        rules = []
        folders = []
        counts = {}
        rules_total = 0
        folders_total = 0

    filelist_image_where = media_migration.default_image_where() or cfg._CONFIG_DEFAULTS.get("FILELIST_IMAGE_WHERE", "")
    filelist_audio_where = media_migration.default_audio_where() or cfg._CONFIG_DEFAULTS.get("FILELIST_AUDIO_WHERE", "")

    return render_template(
        "admin_mapping.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin",
        content_html="",
        active_admin_tab=active_admin_tab,
        message=message,
        rules=rules,
        folders=folders,
        rules_total=rules_total,
        folders_total=folders_total,
        page=page_data["page"],
        total_pages=page_data["total_pages"],
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        counts=counts,
        db_file=cfg.DB_FILE,
        filelist_db=cfg.FILELIST_DB,
        filelist_image_where=filelist_image_where,
        filelist_audio_where=filelist_audio_where,
        notes_sync_root=_notes_live_root(conn),
        unmapped_only=unmapped_only,
        now=datetime.now(),
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings_route():
    security.require_role("admin")
    message = request.args.get("message", "")
    active_settings_tab = (request.args.get("tab") or request.form.get("tab") or "calendar").strip().lower()
    if active_settings_tab not in {"calendar", "media", "audio", "files", "notes", "general", "config"}:
        active_settings_tab = "calendar"

    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    settings_mod.ensure_settings_schema(conn)
    calendar_index.ensure_calendar_schema(conn)

    if request.method == "POST":
        if active_settings_tab == "calendar":
            action = request.form.get("action", "")
            if action == "save_calendar_sources":
                calendar_index.save_calendar_sources(request.form, conn)
                sources = {
                    "events": request.form.get("show_events") == "1",
                    "files": request.form.get("show_files") == "1",
                    "usage": request.form.get("show_usage") == "1",
                    "thumbnail_size": request.form.get("thumbnail_size"),
                    "thumbnail_limit": request.form.get("thumbnail_limit"),
                }
                settings_mod.save_calendar_view_settings(sources, conn)
                message = "Calendar source settings saved."
            elif action == "rebuild_calendar_source":
                source_key = request.form.get("source_key", "")
                result = calendar_index.refresh_calendar_source(source_key, conn=conn, full_rebuild=True)
                message = f"Rebuilt {source_key}: {result.status}, {result.rows_inserted} rows."
            elif action == "rebuild_calendar_all":
                results = calendar_index.refresh_all_calendar_sources(enabled_only=True, conn=conn)
                message = f"Rebuilt {len(results)} enabled calendar sources."
            elif action == "rebuild_calendar_item_days":
                calendar_index.rebuild_calendar_item_days(conn=conn)
                message = "Rebuilt calendar item-day index."
            elif action == "rebuild_calendar_stats":
                count = calendar_index.rebuild_calendar_day_stats(conn=conn)
                message = f"Rebuilt calendar daily stats: {count} rows."
            else:
                sources = {
                    "events": request.form.get("show_events") == "1",
                    "files": request.form.get("show_files") == "1",
                    "usage": request.form.get("show_usage") == "1",
                    "thumbnail_size": request.form.get("thumbnail_size"),
                    "thumbnail_limit": request.form.get("thumbnail_limit"),
                }
                settings_mod.save_calendar_view_settings(sources, conn)
                message = "Calendar settings saved."
        elif active_settings_tab == "general":
            settings_mod.save_general_settings(
                {
                    "freeze_headers": request.form.get("freeze_headers") == "1",
                    "map_names_english": request.form.get("map_names_english") == "1",
                },
                conn,
            )
            message = "General settings saved."
        elif active_settings_tab == "audio":
            settings_mod.save_audio_settings(
                {
                    "visualization": request.form.get("visualization"),
                },
                conn,
            )
            message = "Audio settings saved."
        elif active_settings_tab == "notes":
            action = request.form.get("action", "")
            if action == "rebuild_note_search_index":
                try:
                    result = note_search_index.rebuild_index(conn)
                    message = (
                        "Rebuilt note search index: "
                        f"{result['indexed']} indexed, {result['missing']} missing, "
                        f"{result['skipped']} skipped."
                    )
                except Exception as exc:
                    message = f"Note search index rebuild failed: {exc}"
        elif active_settings_tab == "config":
            names = request.form.getlist("config_name")
            existing_override_names = {
                item["name"]
                for item in cfg.list_config_settings(conn)
                if item.get("has_override")
            }
            saved_count = 0
            reset_count = 0
            errors = []
            for name in names:
                if name not in cfg._CONFIG_DEFAULTS:
                    continue
                key = f"{cfg.CONFIG_SETTING_PREFIX}{name}"
                if request.form.get(f"reset_{name}") == "1" or request.form.get(f"use_override_{name}") != "1":
                    settings_mod.delete_setting(key, conn)
                    if name in existing_override_names or request.form.get(f"reset_{name}") == "1":
                        reset_count += 1
                    continue
                raw_value = request.form.get(f"value_{name}", "")
                try:
                    parsed_value = cfg.parse_config_value(name, raw_value)
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
                    continue
                settings_mod.set_setting(
                    key,
                    cfg.serialize_config_value(parsed_value),
                    "Config",
                    name,
                    conn,
                )
                saved_count += 1
            cfg.refresh_config_overrides()
            if errors:
                message = "Some config settings were not saved: " + "; ".join(errors[:3])
            else:
                message = f"Config settings saved ({saved_count} updated, {reset_count} reset)."
        elif active_settings_tab == "media":
            action = request.form.get("action", "")
            if action == "save_media_display":
                settings_mod.save_media_settings(
                    {
                        "thumbnail_size": request.form.get("thumbnail_size"),
                        "padding_size": request.form.get("padding_size"),
                    },
                    conn,
                )
                message = "Media display settings saved."
            elif action == "rebuild_media_events":
                try:
                    from modules.media import routes as media_routes

                    media_routes._ensure_schema()
                    created = media_routes._rebuild_events(conn, gap_hours=2.0, split_on_day=True)
                    message = f"Rebuilt {created} media events."
                except Exception as exc:
                    message = f"Media event rebuild failed: {exc}"

    calendar_view = settings_mod.get_calendar_view_settings(conn)
    calendar_sources = calendar_index.fetch_calendar_sources(conn)
    media_settings = settings_mod.get_media_settings(conn)
    audio_settings = settings_mod.get_audio_settings(conn)
    general_settings = settings_mod.get_general_settings(conn)
    config_settings = cfg.list_config_settings(conn)
    all_settings = settings_mod.list_settings(conn)
    try:
        note_search_index.ensure_schema(conn)
        note_index_count = conn.execute("SELECT COUNT(1) FROM lp_note_search_index").fetchone()[0]
    except Exception:
        note_index_count = 0

    return render_template(
        "admin_settings.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Settings",
        content_html="",
        message=message,
        active_settings_tab=active_settings_tab,
        calendar_view=calendar_view,
        calendar_sources=calendar_sources,
        media_settings=media_settings,
        audio_settings=audio_settings,
        general_settings=general_settings,
        config_settings=config_settings,
        all_settings=all_settings,
        note_index_count=note_index_count,
        notes_sync_root=_notes_live_root(conn),
        now=datetime.now(),
    )


def _notes_live_root(conn):
    try:
        rows = conn.execute(
            "SELECT path, COUNT(1) AS cnt FROM lp_notes "
            "WHERE COALESCE(path, '') != '' "
            "GROUP BY path ORDER BY cnt DESC"
        ).fetchall()
    except Exception:
        return ""
    root_counts = {}
    root_display = {}
    for row in rows:
        path = (row["path"] or "").strip().replace("/", "\\")
        parts = [part for part in path.split("\\") if part]
        for idx in range(len(parts) - 1):
            if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
                root = "\\".join(parts[: idx + 2])
                key = root.lower()
                root_display.setdefault(key, root)
                root_counts[key] = root_counts.get(key, 0) + int(row["cnt"] or 0)
                break
    if not root_counts:
        return ""
    best_key = max(root_counts, key=root_counts.get)
    return root_display.get(best_key, "")


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
    security.require_role("admin")
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


@admin_bp.route("/users")
def users_route():
    security.require_role("admin")
    return render_template(
        "admin_users.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Users",
        content_html="",
        users=security.list_users(),
        message=request.args.get("message", ""),
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
def new_user_route():
    security.require_role("admin")
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        if not username or not display_name or not password:
            error = "Username, display name, and password are required."
        else:
            try:
                user_id = security.create_user(username, display_name, password, role=role, is_active=True)
                return redirect(url_for("admin.users_route", message=f"Created user {username}."))
            except Exception as exc:
                error = f"User creation failed: {exc}"
    return render_template(
        "admin_user_form.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="New User",
        content_html="",
        user=None,
        error=error,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
def edit_user_route(user_id):
    security.require_role("admin")
    row = security.get_user_by_id(user_id)
    if not row:
        abort(404)
    error = ""
    if request.method == "POST":
        try:
            security.update_user(
                user_id,
                request.form.get("username", ""),
                request.form.get("display_name", ""),
                request.form.get("role", "user"),
                request.form.get("is_active") == "1",
            )
            return redirect(url_for("admin.users_route", message="User updated."))
        except Exception as exc:
            error = f"User update failed: {exc}"
    return render_template(
        "admin_user_form.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit User",
        content_html="",
        user=dict(row),
        error=error,
    )


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
def reset_password_route(user_id):
    security.require_role("admin")
    row = security.get_user_by_id(user_id)
    if not row:
        abort(404)
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not password or password != confirm:
            error = "Passwords do not match."
        else:
            security.reset_user_password(user_id, password, revoke_devices=True)
            return redirect(url_for("admin.users_route", message="Password reset and trusted devices revoked."))
    return render_template(
        "admin_reset_password.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Reset Password",
        content_html="",
        user=dict(row),
        error=error,
    )


@admin_bp.route("/trusted-devices", methods=["GET", "POST"])
def trusted_devices_route():
    security.require_role("admin")
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "revoke":
            security.revoke_trusted_device(request.form.get("trusted_device_id"))
        elif action == "revoke_user":
            security.logout_all_devices(request.form.get("user_id"))
        return redirect(url_for("admin.trusted_devices_route", message="Trusted device settings updated."))
    raw_token = request.cookies.get(security.TRUSTED_DEVICE_COOKIE)
    current_token_hash = security._hash_trusted_token(raw_token) if raw_token else ""
    return render_template(
        "admin_trusted_devices.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Trusted Devices",
        content_html="",
        devices=security.get_trusted_devices(),
        current_token_hash=current_token_hash,
        message=request.args.get("message", ""),
    )
