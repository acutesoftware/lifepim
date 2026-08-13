from datetime import datetime
import json
import os
import sqlite3

from flask import Blueprint, abort, jsonify, render_template, request, redirect, url_for
from flask_login import current_user

from common import data as db
from common import config as cfg
from common import media_migration
from common import localtime
from common import network_log
from common import note_search_index
from common import settings as settings_mod
from common import content_catalog as catalog_mod
from common import user_paths
from common.utils import get_tabs, get_side_tabs, ensure_user_log_schema, lg_usr
from data.processes import ProcessService
from modules.calendar.services import calendar_index
from modules.pocket_api import routes as pocket_api
from modules.logger_api import routes as logger_api
from logger.admin import view_model as logger_view_model
from logger.exceptions import LoggerBusyError
from logger.service import LoggerService
from core import security


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="templates",
    static_folder="static",
)


@admin_bp.route("/content-catalog")
def content_catalog_route():
    security.require_role("admin")
    conn = db._get_conn()
    catalog_mod.ensure_content_catalog_schema(conn)
    mode = (request.args.get("mode") or "matrix").strip().lower()
    if mode not in {"matrix", "report", "editor"}:
        mode = "matrix"
    return render_template(
        "admin_content_catalog.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Content Catalog",
        content_html="",
        catalog_mode=mode,
        catalog_config=catalog_mod.get_admin_config(conn),
        summary=catalog_mod.catalog_summary(conn),
    )


def _catalog_payload():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict(flat=False)
        payload = {key: value if len(value) > 1 else value[0] for key, value in payload.items()}
    return payload or {}


def _catalog_error(exc, status=400):
    return jsonify({"ok": False, "error": str(exc)}), status


@admin_bp.route("/content-catalog/api/config")
def content_catalog_config_api():
    security.require_role("admin")
    conn = db._get_conn()
    return jsonify({"ok": True, "config": catalog_mod.get_admin_config(conn), "summary": catalog_mod.catalog_summary(conn)})


@admin_bp.route("/content-catalog/api/matrix")
def content_catalog_matrix_api():
    security.require_role("admin")
    conn = db._get_conn()
    try:
        matrix = catalog_mod.content_catalog_matrix(request.args, conn=conn)
        return jsonify({"ok": True, "matrix": matrix})
    except Exception as exc:
        return _catalog_error(exc)


@admin_bp.route("/content-catalog/api/cell")
def content_catalog_cell_api():
    security.require_role("admin")
    conn = db._get_conn()
    try:
        rows = catalog_mod.content_catalog_cell_details(
            request.args.get("area_id") or catalog_mod.UNASSIGNED_AREA_ID,
            request.args.get("tab_code") or catalog_mod.NO_TAB_CODE,
            filters=request.args,
            conn=conn,
        )
        return jsonify({"ok": True, "rows": rows})
    except Exception as exc:
        return _catalog_error(exc)


@admin_bp.route("/content-catalog/api/report")
def content_catalog_report_api():
    security.require_role("admin")
    conn = db._get_conn()
    try:
        report = catalog_mod.content_catalog_report(
            request.args.get("group") or "by-tab",
            filters=request.args,
            conn=conn,
        )
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        return _catalog_error(exc)


@admin_bp.route("/content-catalog/api/<entity>")
def content_catalog_list_api(entity):
    security.require_role("admin")
    conn = db._get_conn()
    try:
        if entity == "content-kinds":
            rows = catalog_mod.list_content_kinds(conn=conn, include_inactive=True, filters=request.args)
            return jsonify({"ok": True, "rows": rows, "summary": catalog_mod.catalog_summary(conn)})
        if entity == "patterns":
            return jsonify({"ok": True, "rows": catalog_mod.list_content_patterns(conn=conn, include_inactive=True)})
        if entity == "templates":
            return jsonify({"ok": True, "rows": catalog_mod.list_templates(conn=conn, include_inactive=True)})
        if entity == "views":
            return jsonify({"ok": True, "rows": catalog_mod.list_content_views(conn=conn, include_inactive=True)})
    except Exception as exc:
        return _catalog_error(exc)
    abort(404)


@admin_bp.route("/content-catalog/api/<entity>", methods=["POST"])
def content_catalog_create_api(entity):
    security.require_role("admin")
    conn = db._get_conn()
    payload = _catalog_payload()
    try:
        if entity == "content-kinds":
            record_id = catalog_mod.create_content_kind(payload, conn=conn)
            return jsonify({"ok": True, "id": record_id, "row": catalog_mod.get_content_kind(record_id, conn=conn)})
        if entity == "patterns":
            record_id = catalog_mod.create_content_pattern(payload, conn=conn)
            row = next(row for row in catalog_mod.list_content_patterns(conn=conn, include_inactive=True) if row["content_pattern_id"] == record_id)
            return jsonify({"ok": True, "id": record_id, "row": row})
        if entity == "templates":
            record_id = catalog_mod.create_template(payload, conn=conn)
            row = next(row for row in catalog_mod.list_templates(conn=conn, include_inactive=True) if row["template_id"] == record_id)
            return jsonify({"ok": True, "id": record_id, "row": row})
        if entity == "views":
            record_id = catalog_mod.create_content_view(payload, conn=conn)
            row = next(row for row in catalog_mod.list_content_views(conn=conn, include_inactive=True) if row["content_view_id"] == record_id)
            return jsonify({"ok": True, "id": record_id, "row": row})
    except sqlite3.IntegrityError:
        conn.rollback()
        return _catalog_error("Code must be unique.")
    except Exception as exc:
        conn.rollback()
        return _catalog_error(exc)
    abort(404)


@admin_bp.route("/content-catalog/api/<entity>/<int:record_id>", methods=["PUT", "POST"])
def content_catalog_update_api(entity, record_id):
    security.require_role("admin")
    conn = db._get_conn()
    payload = _catalog_payload()
    try:
        if payload.get("action") in {"delete", "delete_permanently"}:
            if entity == "content-kinds":
                result = catalog_mod.remove_content_kind(record_id, conn=conn)
            elif entity == "patterns":
                result = catalog_mod.remove_content_pattern(record_id, conn=conn)
            elif entity == "templates":
                result = catalog_mod.remove_template(record_id, conn=conn)
            elif entity == "views":
                result = catalog_mod.remove_content_view(record_id, conn=conn)
            else:
                abort(404)
            return jsonify({"ok": True, **result})
        if payload.get("action") in {"remove", "deactivate"}:
            if entity == "content-kinds":
                result = catalog_mod.remove_content_kind(record_id, conn=conn)
                return jsonify({"ok": True, **result})
            elif entity == "patterns":
                catalog_mod.deactivate_content_pattern(record_id, conn=conn)
            elif entity == "templates":
                catalog_mod.deactivate_template(record_id, conn=conn)
            elif entity == "views":
                catalog_mod.deactivate_content_view(record_id, conn=conn)
            else:
                abort(404)
            return jsonify({"ok": True, "removed": False, "deactivated": True})
        elif entity == "content-kinds":
            catalog_mod.update_content_kind(record_id, payload, conn=conn)
        elif entity == "patterns":
            catalog_mod.update_content_pattern(record_id, payload, conn=conn)
        elif entity == "templates":
            catalog_mod.update_template(record_id, payload, conn=conn)
        elif entity == "views":
            catalog_mod.update_content_view(record_id, payload, conn=conn)
        else:
            abort(404)
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        conn.rollback()
        return _catalog_error("Code must be unique.")
    except Exception as exc:
        conn.rollback()
        return _catalog_error(exc)


SYNC_PUSH_PATH_SUFFIXES = (
    "/sync/push",
    "/sync/upload",
    "/sync/uploads",
    "/sync/mobile",
    "/sync/mobile-to-desktop",
    "/push",
)


def _tail_text_lines(path, limit):
    if not path or not os.path.exists(path):
        return []
    from collections import deque

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return list(deque(handle, maxlen=max(int(limit or 0), 1)))
    except OSError:
        return []


def _parse_network_log_line(line):
    text = (line or "").strip()
    if not text:
        return None
    parts = text.split(" ", 2)
    if len(parts) < 2:
        return None
    payload = {}
    if len(parts) == 3 and parts[2].strip():
        try:
            payload = json.loads(parts[2])
        except Exception:
            payload = {"raw": parts[2]}
    return {"log_date": parts[0], "display_log_date": localtime.display_log_time(parts[0]), "event": parts[1], "fields": payload}


def _is_push_path(path):
    clean = (path or "").rstrip("/")
    return any(clean.endswith(suffix) for suffix in SYNC_PUSH_PATH_SUFFIXES)


def _is_sync_network_entry(entry):
    event = entry.get("event") or ""
    fields = entry.get("fields") or {}
    path = fields.get("path") or ""
    if event.startswith("pocket_push") or event.startswith("pocket_manifest"):
        return True
    if event in {"pocket_payload_too_large", "pocket_auth_ok"} and ("/sync/manifest" in path or _is_push_path(path)):
        return True
    if event in {"request_start", "request_finish", "request_exception"} and ("/sync/manifest" in path or _is_push_path(path)):
        return True
    return False


def _sync_direction(entry):
    event = entry.get("event") or ""
    path = (entry.get("fields") or {}).get("path") or ""
    if event.startswith("pocket_push") or _is_push_path(path) or event == "pocket_payload_too_large":
        return "Mobile -> Desktop"
    if event.startswith("pocket_manifest") or "/sync/manifest" in path:
        return "Desktop -> Mobile"
    return "Sync"


def _sync_summary(entry):
    event = entry.get("event") or ""
    fields = entry.get("fields") or {}
    if event == "pocket_manifest_finish":
        return (
            f"{fields.get('item_count', 0)} manifest items; "
            f"{fields.get('skipped_count', 0)} skipped; {fields.get('error_count', 0)} errors"
        )
    if event == "pocket_manifest_progress":
        return f"{fields.get('processed_count', 0)}/{fields.get('total_count', 0)} manifest items"
    if event == "pocket_push_start":
        return f"{fields.get('item_count', 0)} incoming items; {fields.get('content_length', '')} bytes"
    if event == "pocket_push_connect":
        return f"{fields.get('method', '')} {fields.get('path', '')}; {fields.get('content_length', '')} bytes"
    if event == "pocket_push_finish":
        return (
            f"{fields.get('ok_count', 0)}/{fields.get('item_count', 0)} accepted; "
            f"{fields.get('conflict_count', 0)} conflicts; {fields.get('error_count', 0)} errors; "
            f"HTTP {fields.get('status_code', '')}"
        )
    if event == "pocket_push_mobile_file_saved":
        return f"{fields.get('kind', '')} {fields.get('relative_path', '')}; {fields.get('size', 0)} bytes"
    if event == "pocket_push_note_deleted":
        return f"deleted note {fields.get('note_id', '')}"
    if event == "pocket_push_item_error":
        return f"{fields.get('item_id', '')}: {fields.get('error', '')}"
    if event == "pocket_payload_too_large":
        return f"{fields.get('content_length', '')} bytes exceeded {fields.get('max_bytes', '')}"
    if event == "request_finish":
        return f"HTTP {fields.get('status_code', '')}; {fields.get('duration_ms', '')} ms"
    if event == "request_exception":
        return f"{fields.get('error_type', '')}: {fields.get('error', '')}"
    if event == "request_start":
        return f"{fields.get('method', '')} {fields.get('path', '')}"
    if event == "pocket_auth_ok":
        return f"authenticated {fields.get('username', '')}"
    return event


def _network_fields_preview(fields):
    if not fields:
        return ""
    keep = {}
    for key in (
        "path",
        "method",
        "username",
        "user_id",
        "device_id",
        "remote_addr",
        "status_code",
        "duration_ms",
        "item_count",
        "ok_count",
        "conflict_count",
        "error_count",
        "total_count",
        "skipped_count",
        "relative_path",
        "kind",
        "size",
        "has_device_id",
    ):
        if key in fields:
            keep[key] = fields.get(key)
    return json.dumps(keep or fields, ensure_ascii=True, default=str, sort_keys=True)


def _sync_log_entries(limit):
    entries = []
    for line in _tail_text_lines(network_log.network_log_path(), max(int(limit or 0) * 8, 200)):
        entry = _parse_network_log_line(line)
        if not entry or not _is_sync_network_entry(entry):
            continue
        entry["direction"] = _sync_direction(entry)
        entry["summary"] = _sync_summary(entry)
        entry["details"] = _network_fields_preview(entry.get("fields") or {})
        entries.append(entry)
    return entries[-int(limit or 0) :]


def _user_log_entries(conn, limit):
    ensure_user_log_schema(conn)
    rows = conn.execute(
        "SELECT id, log_date, user_name, action, entity_type, entity_id, context_type, context_id, details "
        "FROM sys_user_log ORDER BY id DESC LIMIT ?",
        [int(limit or 0)],
    ).fetchall()
    entries = []
    for row in rows:
        item = dict(row)
        item["display_log_date"] = localtime.display_log_time(item.get("log_date"))
        entries.append(item)
    return entries


@admin_bp.route("/", methods=["GET", "POST"])
def admin_mapping_route():
    security.require_role("admin")
    message = request.args.get("message", "")
    active_admin_tab = (request.args.get("tab") or request.form.get("tab") or "security").strip().lower()
    if active_admin_tab not in {"security", "migration"}:
        active_admin_tab = "security"

    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn

    if request.method == "POST":
        action = request.form.get("action", "")
        if active_admin_tab == "migration":
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
                    stats_result = calendar_index.refresh_calendar_source("media", conn=conn, full_rebuild=True)
                    message = (
                        f"Media migrated from {result['source_table']} and {result['video_source_table']}: "
                        f"{result['total_inserted']} rows ({result['inserted']} images, "
                        f"{result['video_inserted']} videos). "
                        f"Calendar media stats rebuilt: {stats_result.rows_inserted} rows."
                    )
                elif action == "migrate_audio":
                    result = media_migration.migrate_audio_from_filelist(where_clause=audio_where, conn=conn)
                    stats_result = calendar_index.refresh_calendar_source("audio", conn=conn, full_rebuild=True)
                    message = (
                        f"Audio migrated from {result['source_table']}: {result['inserted']} rows. "
                        f"Calendar audio stats rebuilt: {stats_result.rows_inserted} rows."
                    )
                elif action == "save_media_filters":
                    message = "Media migration filters saved."
            except Exception as exc:
                message = f"Media migration failed: {exc}"

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
        db_file=cfg.DB_FILE,
        filelist_db=cfg.FILELIST_DB,
        filelist_image_where=filelist_image_where,
        filelist_audio_where=filelist_audio_where,
        notes_sync_root=_notes_live_root(conn),
        now=datetime.now(),
    )


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings_route():
    security.require_role("admin")
    message = request.args.get("message", "")
    active_settings_tab = (request.args.get("tab") or request.form.get("tab") or "calendar").strip().lower()
    if active_settings_tab not in {"calendar", "media", "audio", "files", "notes", "places", "logger", "general", "config"}:
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
                results = calendar_index.rebuild_calendar_day_stat_baselines(conn=conn)
                count = sum(result.rows_inserted for result in results)
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
                    "mobile_font_size": request.form.get("mobile_font_size"),
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
            if action == "save_note_display":
                settings_mod.save_note_display_settings(
                    {
                        "card_width_chars": request.form.get("card_width_chars"),
                        "title_font_size": request.form.get("title_font_size"),
                        "preview_chars": request.form.get("preview_chars"),
                        "sample_lines": request.form.get("sample_lines"),
                        "notes_per_page": request.form.get("notes_per_page"),
                    },
                    conn,
                )
                message = "Note display settings saved."
            elif action == "materialize_note_areas":
                try:
                    from modules.notes import routes as notes_routes

                    result = notes_routes.materialize_note_areas(conn=conn, owner_user_id=getattr(current_user, "user_id", None))
                    message = (
                        "Materialized note areas: "
                        f"{result['updated']} updated from {result['scanned']} blank-area rows."
                    )
                except Exception as exc:
                    message = f"Note area materialization failed: {exc}"
            elif action == "refresh_note_colors":
                try:
                    from modules.notes import routes as notes_routes

                    result = notes_routes.refresh_note_color_metadata(conn=conn, owner_user_id=getattr(current_user, "user_id", None))
                    skipped = []
                    if result["missing"]:
                        skipped.append(f"{result['missing']} missing files")
                    if result["no_color"]:
                        skipped.append(f"{result['no_color']} without color")
                    if result["invalid"]:
                        skipped.append(f"{result['invalid']} invalid colors")
                    message = (
                        "Refreshed note colors: "
                        f"{result['updated']} updated from {result['scanned']} blank-color rows."
                    )
                    if skipped:
                        message += " Skipped " + ", ".join(skipped) + "."
                except Exception as exc:
                    message = f"Note color refresh failed: {exc}"
            elif action == "rebuild_note_search_index":
                try:
                    result = note_search_index.rebuild_index(conn)
                    message = (
                        "Rebuilt note search index: "
                        f"{result['indexed']} indexed, {result['missing']} missing, "
                        f"{result['skipped']} skipped."
                    )
                except Exception as exc:
                    message = f"Note search index rebuild failed: {exc}"
        elif active_settings_tab == "places":
            settings_mod.save_places_settings(
                {
                    "virtual_worlds": request.form.get("virtual_worlds", ""),
                },
                conn,
            )
            message = "Places settings saved."
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
                    cfg.delete_bootstrap_config_override(name)
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
                cfg.save_bootstrap_config_override(name, cfg.serialize_config_value(parsed_value))
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
        elif active_settings_tab == "logger":
            token_value = request.form.get("logger_sync_token", "")
            logger_values = {
                "enabled": request.form.get("logger_sync_enabled") == "1",
                "raw_data_root": request.form.get("logger_raw_data_root"),
                "sync_token": token_value if token_value else None,
                "max_upload_mb": request.form.get("logger_max_upload_mb"),
                "keep_sync_logs": request.form.get("logger_keep_sync_logs") == "1",
                "database_path": request.form.get("logger_database_path"),
                "mobile_source_path": request.form.get("logger_mobile_source_path"),
                "aggie_source_path": request.form.get("logger_aggie_source_path"),
                "session_gap_seconds": request.form.get("logger_session_gap_seconds"),
                "minimum_session_seconds": request.form.get("logger_minimum_session_seconds"),
            }
            settings_mod.save_logger_settings(logger_values, conn)
            message = "Mobile Logger settings saved."

    calendar_view = settings_mod.get_calendar_view_settings(conn)
    calendar_sources = calendar_index.fetch_calendar_sources(conn)
    media_settings = settings_mod.get_media_settings(conn)
    audio_settings = settings_mod.get_audio_settings(conn)
    general_settings = settings_mod.get_general_settings(conn)
    places_settings = settings_mod.get_places_settings(conn)
    note_settings = settings_mod.get_note_display_settings(conn)
    logger_settings = settings_mod.get_logger_settings(
        conn,
        user_id=getattr(current_user, "user_id", None),
        username=getattr(current_user, "username", None),
    )
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
        places_settings=places_settings,
        note_settings=note_settings,
        logger_settings=logger_settings,
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
        entry["display_log_date"] = localtime.display_log_time(entry.get("log_date"))

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


@admin_bp.route("/logs")
def logs_route():
    security.require_role("admin")
    conn = db.conn if db.conn is not None else None
    conn = db._get_conn() if conn is None else conn
    first_load = not request.args
    include_sync_logs = request.args.get("sync_logs") == "1" or first_load
    include_user_logs = request.args.get("user_logs") == "1" or first_load
    limit = request.args.get("limit", type=int) or 200
    limit = max(10, min(limit, 1000))
    sync_entries = _sync_log_entries(limit) if include_sync_logs else []
    user_entries = _user_log_entries(conn, limit) if include_user_logs else []
    return render_template(
        "admin_logs.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin - Logs",
        content_html="",
        include_sync_logs=include_sync_logs,
        include_user_logs=include_user_logs,
        limit=limit,
        sync_entries=sync_entries,
        user_entries=user_entries,
        network_log_file=network_log.network_log_path(),
        log_timezone=localtime.log_timezone_name(),
        db_file=getattr(cfg, "DB_FILE", ""),
    )


def _read_raw_log_preview(path, byte_limit=5 * 1024 * 1024, line_limit=20000):
    lines = []
    bytes_read = 0
    truncated = False
    try:
        with open(path, "rb") as handle:
            for raw_line in handle:
                if len(lines) >= line_limit or bytes_read + len(raw_line) > byte_limit:
                    truncated = True
                    break
                bytes_read += len(raw_line)
                lines.append(raw_line.decode("utf-8", errors="replace"))
    except OSError as exc:
        return "", f"Unable to read file: {exc}", True
    try:
        truncated = truncated or os.path.getsize(path) > bytes_read
    except OSError:
        pass
    notice = ""
    if truncated:
        notice = "This file is larger than the built-in viewer limit. Only the first 20,000 lines or 5 MB are shown."
    return "".join(lines), notice, truncated


@admin_bp.route("/logs/logger", methods=["GET", "POST"])
def logger_logs_route():
    security.require_role("admin")
    conn = db._get_conn()
    logger_settings = settings_mod.get_logger_settings(
        conn,
        user_id=getattr(current_user, "user_id", None),
        username=getattr(current_user, "username", None),
    )
    message = ""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "open_raw_folder":
            raw_folder = logger_api.logger_raw_root(logger_settings)
            try:
                os.makedirs(raw_folder, exist_ok=True)
                logger_api.open_path_in_file_browser(raw_folder)
                message = "Opened raw data folder."
            except Exception as exc:
                message = f"Unable to open raw data folder: {exc}"
        elif action == "save_raw_folder":
            logger_values = dict(logger_settings)
            logger_values["raw_data_root"] = request.form.get("logger_raw_data_root")
            logger_values["sync_token"] = None
            settings_mod.save_logger_settings(logger_values, conn)
            logger_settings = settings_mod.get_logger_settings(
                conn,
                user_id=getattr(current_user, "user_id", None),
                username=getattr(current_user, "username", None),
            )
            message = "Logger raw data folder saved."
        elif action in {"preview_logger_import", "refresh_logger_data", "rebuild_logger_sessions", "rebuild_logger_database"}:
            try:
                if action in {"preview_logger_import", "refresh_logger_data", "rebuild_logger_database"}:
                    process_service = ProcessService(conn)
                    process = process_service.get_default_logger_process()
                    if not process:
                        message = "No logger import process has been configured."
                    elif action == "preview_logger_import":
                        result = process_service.preview_process(process["process_id"], trigger_type="admin_shortcut")
                        message = f"Logger import preview: {result.summary}"
                    elif action == "refresh_logger_data":
                        result = process_service.run_process(process["process_id"], trigger_type="admin_shortcut")
                        message = f"Logger JSON loaded to database: {result.files_processed} imported, {result.files_skipped} skipped, {result.files_failed} failed."
                    else:
                        if request.form.get("confirm_rebuild_database") != "1":
                            message = "Tick the confirmation box before rebuilding the logger database."
                        else:
                            result = process_service.rebuild_process(process["process_id"], trigger_type="admin_shortcut")
                            message = f"Logger database rebuilt: {result.files_processed} imported, {result.files_failed} failed."
                elif action == "rebuild_logger_sessions":
                    service = LoggerService(
                        main_conn=conn,
                        user_id=getattr(current_user, "user_id", None),
                        username=getattr(current_user, "username", None),
                    )
                    result = service.rebuild_sessions()
                    message = f"Logger activity sessions rebuilt: {result.sessions_created} sessions."
            except LoggerBusyError as exc:
                message = str(exc)
            except Exception as exc:
                message = f"Logger processing failed: {exc}"
    filters = {
        "device": request.args.get("device", ""),
        "log_type": request.args.get("log_type", ""),
        "file_date": request.args.get("file_date", ""),
        "filename": request.args.get("filename", ""),
    }
    session_filters = {
        "device": request.args.get("session_device", ""),
        "platform": request.args.get("session_platform", ""),
        "application": request.args.get("session_application", ""),
        "date": request.args.get("session_date", ""),
    }
    files = logger_api.list_raw_files(filters=filters, conn=conn, settings=logger_settings)
    log_types = sorted(set(logger_api.ALLOWED_LOG_TYPES) | {row.get("log_type", "") for row in files if row.get("log_type")})
    selected_run_id = request.args.get("run_id", type=int)
    logger_service = LoggerService(
        main_conn=conn,
        user_id=getattr(current_user, "user_id", None),
        username=getattr(current_user, "username", None),
    )
    try:
        process_service = ProcessService(conn)
        logger_process = process_service.get_default_logger_process()
        latest_process_runs = process_service.list_runs(process_id=logger_process["process_id"], limit=5) if logger_process else []
        processing_status = logger_view_model.logger_status_view(logger_service.get_status())
        processing_runs = logger_view_model.processing_runs_view(logger_service.recent_processing_runs(25))
        failed_files = logger_view_model.failed_files_view(logger_service.failed_files(25))
        activity_sessions = logger_view_model.activity_sessions_view(
            logger_service.get_recent_sessions(
                100,
                device_id=session_filters["device"] or None,
                platform=session_filters["platform"] or None,
                application_identifier=session_filters["application"] or None,
                date=session_filters["date"] or None,
            )
        )
    except Exception as exc:
        logger_process = None
        latest_process_runs = []
        processing_status = {"error": str(exc)}
        processing_runs = []
        failed_files = []
        activity_sessions = []
    return render_template(
        "admin_logger.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Admin - Logs - Logger",
        content_html="",
        message=message,
        summary=logger_api.logger_summary(conn, settings=logger_settings, files=files),
        runs=logger_api.recent_sync_runs(100, conn),
        run_files=logger_api.run_files(selected_run_id, conn) if selected_run_id else [],
        selected_run_id=selected_run_id,
        logger_settings=logger_settings,
        raw_files=files,
        devices=logger_api.list_devices(conn),
        filters=filters,
        session_filters=session_filters,
        log_types=log_types,
        processing_status=processing_status,
        processing_runs=processing_runs,
        failed_files=failed_files,
        activity_sessions=activity_sessions,
        logger_process=logger_process,
        latest_process_runs=latest_process_runs,
    )


@admin_bp.route("/logs/logger/file")
def logger_file_view_route():
    security.require_role("admin")
    conn = db._get_conn()
    logger_settings = settings_mod.get_logger_settings(
        conn,
        user_id=getattr(current_user, "user_id", None),
        username=getattr(current_user, "username", None),
    )
    device_folder = request.args.get("device_folder", "")
    relative_path = request.args.get("relative_path", "")
    path = logger_api.resolve_raw_file(device_folder, relative_path, settings=logger_settings)
    if not path:
        abort(404)
    text, notice, truncated = _read_raw_log_preview(path)
    stat = os.stat(path)
    return render_template(
        "admin_logger_file.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Logger Raw File",
        content_html="",
        device_folder=device_folder,
        relative_path=relative_path,
        file_path=path,
        file_size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        text=text,
        notice=notice,
        truncated=truncated,
    )


@admin_bp.route("/logs/logger/file/open", methods=["POST"])
def logger_file_open_route():
    security.require_role("admin")
    conn = db._get_conn()
    logger_settings = settings_mod.get_logger_settings(
        conn,
        user_id=getattr(current_user, "user_id", None),
        username=getattr(current_user, "username", None),
    )
    device_folder = request.form.get("device_folder", "")
    relative_path = request.form.get("relative_path", "")
    path = logger_api.resolve_raw_file(device_folder, relative_path, settings=logger_settings)
    if not path:
        abort(404)
    logger_api.open_path_in_file_browser(path)
    return redirect(url_for("admin.logger_file_view_route", device_folder=device_folder, relative_path=relative_path))


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


def _table_exists(conn, table_name):
    try:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone())
    except Exception:
        return False


def _table_columns(conn, table_name):
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except Exception:
        return set()


def _delete_by_column_if_exists(conn, table_name, column_name, value):
    if _table_exists(conn, table_name) and column_name in _table_columns(conn, table_name):
        conn.execute(f"DELETE FROM {table_name} WHERE {column_name} = ?", (value,))


def _user_note_delete_plan(conn, user_id):
    if not _table_exists(conn, "lp_notes"):
        return {"note_record_count": 0, "note_file_count": 0, "note_ids": [], "note_file_paths": []}
    columns = _table_columns(conn, "lp_notes")
    if "owner_user_id" not in columns:
        return {"note_record_count": 0, "note_file_count": 0, "note_ids": [], "note_file_paths": []}
    select_cols = ["id"]
    if "path" in columns:
        select_cols.append("path")
    if "file_name" in columns:
        select_cols.append("file_name")
    rows = conn.execute(
        f"SELECT {', '.join(select_cols)} FROM lp_notes WHERE owner_user_id = ?",
        (user_id,),
    ).fetchall()
    note_ids = [row["id"] for row in rows]
    note_file_paths = []
    seen_paths = set()
    for row in rows:
        file_name = (row["file_name"] if "file_name" in row.keys() else "") or ""
        path = (row["path"] if "path" in row.keys() else "") or ""
        full_path = ""
        if path and file_name:
            full_path = os.path.join(path, file_name)
        elif file_name and os.path.isabs(file_name):
            full_path = file_name
        elif path:
            full_path = path
        if full_path and os.path.isfile(full_path):
            key = os.path.normcase(os.path.abspath(full_path))
            if key not in seen_paths:
                seen_paths.add(key)
                note_file_paths.append(full_path)
    return {
        "note_record_count": len(note_ids),
        "note_file_count": len(note_file_paths),
        "note_ids": note_ids,
        "note_file_paths": note_file_paths,
    }


def _delete_user_and_owned_notes(conn, user_id):
    user = security.get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found.")
    if getattr(current_user, "is_authenticated", False) and int(getattr(current_user, "user_id", 0) or 0) == int(user_id):
        raise ValueError("You cannot delete the user you are currently logged in as.")
    plan = _user_note_delete_plan(conn, user_id)
    for note_path in plan["note_file_paths"]:
        if os.path.isfile(note_path):
            os.remove(note_path)
    note_ids = plan["note_ids"]
    if note_ids:
        placeholders = ", ".join(["?"] * len(note_ids))
        if _table_exists(conn, "lp_links"):
            conn.execute(
                f"DELETE FROM lp_links WHERE (src_type = 'note' AND src_id IN ({placeholders})) "
                f"OR (dst_type = 'note' AND dst_id IN ({placeholders}))",
                note_ids + note_ids,
            )
        if _table_exists(conn, "pocket_item_map"):
            conn.execute(
                f"DELETE FROM pocket_item_map WHERE entity_type = 'note' AND entity_id IN ({placeholders})",
                note_ids,
            )
        if _table_exists(conn, "pocket_item_state"):
            conn.execute(
                f"DELETE FROM pocket_item_state WHERE entity_type = 'note' AND entity_id IN ({placeholders})",
                note_ids,
            )
        if _table_exists(conn, "pocket_client_item_map"):
            conn.execute(
                f"DELETE FROM pocket_client_item_map WHERE entity_type = 'note' AND entity_id IN ({placeholders})",
                note_ids,
            )
    _delete_by_column_if_exists(conn, "lp_notes", "owner_user_id", user_id)
    _delete_by_column_if_exists(conn, "lp_area_folders", "owner_user_id", user_id)
    _delete_by_column_if_exists(conn, "lp_areas", "owner_user_id", user_id)
    _delete_by_column_if_exists(conn, "pocket_user_settings", "user_id", user_id)
    _delete_by_column_if_exists(conn, "pocket_pairing_codes", "user_id", user_id)
    _delete_by_column_if_exists(conn, "pocket_devices", "user_id", user_id)
    _delete_by_column_if_exists(conn, "auth_trusted_devices", "user_id", user_id)
    _delete_by_column_if_exists(conn, "auth_login_attempts", "user_id", user_id)
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    return plan


def _requested_username(default="username"):
    return (request.form.get("username") or request.args.get("username") or default).strip() or default


def _resolve_username_segment(path_value, username):
    path_value = user_paths.normalize_path(path_value)
    username = (username or "").strip()
    if not path_value or not username or username.lower() == "username":
        return path_value
    parts = path_value.split("\\")
    changed = False
    safe_username = user_paths.safe_path_segment(username)
    for idx, part in enumerate(parts):
        if part.lower() == "username":
            parts[idx] = safe_username
            changed = True
    return "\\".join(parts) if changed else path_value


def _default_or_submitted_user_paths(username):
    defaults = user_paths.default_paths_for_username(username or "username")
    if request.method != "POST":
        return defaults
    file_root = _resolve_username_segment(
        request.form.get("file_root_path", "").strip() or defaults.get("file_root_path") or "",
        username,
    )
    derived = user_paths.paths_from_root(file_root)
    return {
        "file_root_path": user_paths.normalize_path(file_root),
        "notes_root_path": _resolve_username_segment(
            request.form.get("notes_root_path", "").strip() or derived.get("notes_root_path") or defaults.get("notes_root_path")
            or "",
            username,
        ),
        "areas_root_path": _resolve_username_segment(
            request.form.get("areas_root_path", "").strip()
            or derived.get("areas_root_path")
            or defaults.get("areas_root_path")
            or "",
            username,
        ),
        "lists_root_path": _resolve_username_segment(
            request.form.get("lists_root_path", "").strip() or derived.get("lists_root_path") or defaults.get("lists_root_path")
            or "",
            username,
        ),
    }


@admin_bp.route("/users/new", methods=["GET", "POST"])
def new_user_route():
    security.require_role("admin")
    error = ""
    form_username = _requested_username()
    form_paths = _default_or_submitted_user_paths(form_username)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        form_username = username or form_username
        form_paths = _default_or_submitted_user_paths(form_username)
        pocket_default_note_folder = _resolve_username_segment(
            request.form.get("pocket_default_note_folder", "").strip(),
            form_username,
        )
        if not username or not display_name or not password:
            error = "Username, display name, and password are required."
        else:
            try:
                user_id = security.create_user(
                    username,
                    display_name,
                    password,
                    role=role,
                    is_active=True,
                    file_paths=form_paths,
                )
                paths = user_paths.get_or_create_user_paths(db._get_conn(), user_id, username=username, create_dirs=True)
                pocket_api.set_user_default_note_folder(
                    user_id,
                    pocket_default_note_folder or paths.get("notes_root_path") or "",
                )
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
        pocket_settings={
            "default_note_folder": request.form.get("pocket_default_note_folder", "") or form_paths.get("notes_root_path", "")
        },
        user_paths=form_paths,
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
            paths = _default_or_submitted_user_paths(request.form.get("username", row["username"]))
            user_paths.set_user_paths(db._get_conn(), user_id, paths, create_dirs=True)
            pocket_default_note_folder = _resolve_username_segment(
                request.form.get("pocket_default_note_folder", ""),
                request.form.get("username", row["username"]),
            )
            pocket_api.set_user_default_note_folder(user_id, pocket_default_note_folder)
            return redirect(url_for("admin.users_route", message="User updated."))
        except Exception as exc:
            error = f"User update failed: {exc}"
    pocket_settings = pocket_api.get_user_pocket_settings(user_id)
    paths = user_paths.get_or_create_user_paths(db._get_conn(), user_id, username=row["username"], create_dirs=False)
    if request.method == "POST" and error:
        pocket_settings["default_note_folder"] = request.form.get("pocket_default_note_folder", "")
    return render_template(
        "admin_user_form.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit User",
        content_html="",
        user=dict(row),
        pocket_settings=pocket_settings,
        user_paths=paths,
        error=error,
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["GET", "POST"])
def delete_user_route(user_id):
    security.require_role("admin")
    row = security.get_user_by_id(user_id)
    if not row:
        abort(404)
    conn = db._get_conn()
    error = ""
    plan = _user_note_delete_plan(conn, user_id)
    if request.method == "POST":
        try:
            _delete_user_and_owned_notes(conn, user_id)
            return redirect(url_for("notes.list_notes_route"))
        except Exception as exc:
            error = f"User delete failed: {exc}"
            plan = _user_note_delete_plan(conn, user_id)
    return render_template(
        "admin_delete_user_confirm.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Delete User",
        content_html="",
        user=dict(row),
        note_record_count=plan["note_record_count"],
        note_file_count=plan["note_file_count"],
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
    pairing = None
    message = request.args.get("message", "")
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "revoke":
            security.revoke_trusted_device(request.form.get("trusted_device_id"))
        elif action == "revoke_user":
            security.logout_all_devices(request.form.get("user_id"))
        elif action == "revoke_mobile":
            pocket_api.revoke_pocket_device(request.form.get("device_id"))
        elif action == "create_mobile_pairing":
            try:
                pairing = pocket_api.create_pocket_pairing_code(request.form.get("user_id"), created_ip=request.remote_addr or "")
                message = "Pocket pairing code created."
            except ValueError as exc:
                message = str(exc)
        if action != "create_mobile_pairing":
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
        mobile_devices=pocket_api.list_pocket_devices(),
        users=security.list_users(),
        pairing=pairing,
        current_token_hash=current_token_hash,
        message=message,
    )
