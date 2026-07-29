import os
import subprocess
import sys

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from common import areas as areas_mod
from common import config as cfg
from common.utils import get_side_tabs, get_tabs, normalize_area_param
from core import security

areas_bp = Blueprint("areas", __name__, url_prefix="/areas", template_folder="templates")


def _next_url(area_id):
    return request.form.get("next") or request.args.get("next") or url_for(
        "notes.list_notes_route", area=area_id
    )


def _sidebar_rows_from_form(form):
    rows = []
    ids = form.getlist("area_id")
    original_ids = form.getlist("original_area_id")
    labels = form.getlist("area_name")
    icons = form.getlist("icon")
    groups = form.getlist("group_name")
    row_types = form.getlist("row_type")
    system_flags = form.getlist("is_system")
    delete_flags = form.getlist("delete_area")
    max_len = max(
        len(ids),
        len(original_ids),
        len(labels),
        len(icons),
        len(groups),
        len(row_types),
        len(system_flags),
        len(delete_flags),
    )
    for idx in range(max_len):
        is_system = int(system_flags[idx] or 0) if idx < len(system_flags) else 0
        delete_area = (delete_flags[idx].strip() if idx < len(delete_flags) else "0") == "1"
        if delete_area and not is_system:
            continue
        area_id = ids[idx].strip() if idx < len(ids) else ""
        area_name = labels[idx].strip() if idx < len(labels) else ""
        if not area_id or not area_name:
            continue
        row_type = row_types[idx] if idx < len(row_types) else "area"
        rows.append(
            {
                "area_id": area_id,
                "original_area_id": original_ids[idx].strip() if idx < len(original_ids) else area_id,
                "area_name": area_name,
                "icon": icons[idx] if idx < len(icons) else "",
                "group_name": groups[idx] if idx < len(groups) else "",
                "is_header": 1 if row_type == "header" else 0,
                "is_system": is_system,
                "status": "active",
                "sort_order": idx * 10,
            }
        )
    new_type = (form.get("new_row_type") or "area").strip()
    new_id = (form.get("new_area_id") or "").strip()
    new_label = (form.get("new_area_name") or "").strip()
    if new_id and new_label:
        rows.append(
            {
                "area_id": new_id,
                "original_area_id": "",
                "area_name": new_label,
                "icon": form.get("new_icon") or "",
                "group_name": form.get("new_group_name") or "",
                "is_header": 1 if new_type == "header" else 0,
                "is_system": 0,
                "status": "active",
                "sort_order": len(rows) * 10,
            }
        )
    return rows


@areas_bp.route("/edit", methods=["GET", "POST"])
def edit_areas_route():
    security.require_login()
    message = request.args.get("message", "")
    error = ""
    if request.method == "POST":
        action = request.form.get("action", "save")
        try:
            if action == "reset":
                count = areas_mod.seed_default_areas_for_user(current_user.user_id, replace=True)
                return redirect(url_for("areas.edit_areas_route", message=f"Reset {count} area rows."))
            rows = _sidebar_rows_from_form(request.form)
            areas_mod.save_user_sidebar_rows(rows, owner_user_id=current_user.user_id)
            return redirect(url_for("areas.edit_areas_route", message="Areas saved."))
        except Exception as exc:
            error = f"Areas were not saved: {exc}"
    rows = areas_mod.areas_side_tabs(owner_user_id=current_user.user_id, seed=True)
    schema_sql_file = os.path.abspath(os.path.join(os.path.dirname(areas_mod.__file__), os.pardir, "schema_areas.sql"))
    return render_template(
        "areas_edit.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Areas",
        content_html="",
        area_rows=rows,
        message=message,
        error=error,
        db_file=getattr(cfg, "DB_FILE", ""),
        area_tables=["lp_areas", "lp_area_folders"],
        schema_sql_file=schema_sql_file,
        schema_source_file=os.path.abspath(areas_mod.__file__),
        area_doc_file=os.path.abspath(os.path.join(os.path.dirname(areas_mod.__file__), os.pardir, os.pardir, "doc", "Area.md")),
    )


@areas_bp.route("/api/default-folder")
def area_default_folder_route():
    area_id = normalize_area_param(
        request.args.get("area_id")
        or request.args.get("project_id")
        or request.args.get("area")
        or request.args.get("proj")
        or request.args.get("project")
        or ""
    )
    if not area_id:
        return jsonify({"error": "Area is required."}), 400
    try:
        path_prefix = areas_mod.area_default_folder_get(area_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"area_id": area_id, "path_prefix": path_prefix})


@areas_bp.route("/api/folders", methods=["POST"])
def area_folder_add_api():
    payload = request.get_json(silent=True) or {}
    area_id = normalize_area_param(
        payload.get("area_id") or payload.get("project_id") or payload.get("area") or payload.get("project") or ""
    )
    path_prefix = (payload.get("path_prefix") or "").strip()
    folder_role = (payload.get("folder_role") or "include").strip()
    create_type = (payload.get("create_type") or "none").strip()
    if not area_id or not path_prefix:
        return jsonify({"error": "Area and path are required."}), 400
    try:
        folder_id = areas_mod.area_folder_add(
            area_id,
            path_prefix,
            folder_role=folder_role,
            create_type=create_type,
            is_write_enabled=1 if folder_role == "default" else 0,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    folder = areas_mod.area_folder_get(folder_id)
    return jsonify({"folder": folder})


@areas_bp.route("/api/folders/<int:area_folder_id>/set-default", methods=["POST"])
def area_folder_set_default_api(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if not folder:
        return jsonify({"error": "Folder not found."}), 404
    areas_mod.area_folder_set_default(folder["area_id"], area_folder_id)
    folder = areas_mod.area_folder_get(area_folder_id)
    return jsonify({"folder": folder})


@areas_bp.route("/folders/add", methods=["POST"])
def area_folder_add_route():
    area_id = normalize_area_param(
        request.form.get("area_id") or request.form.get("project_id") or request.form.get("area") or request.form.get("project") or ""
    )
    path_prefix = (request.form.get("path_prefix") or "").strip()
    folder_role = (request.form.get("folder_role") or "include").strip()
    create_type = (request.form.get("create_type") or "none").strip()
    if not area_id or not path_prefix:
        return redirect(_next_url(area_id))
    try:
        folder_id = areas_mod.area_folder_add(
            area_id,
            path_prefix,
            folder_role=folder_role,
            create_type=create_type,
            is_write_enabled=1 if folder_role == "default" else 0,
        )
    except ValueError:
        return redirect(_next_url(area_id))
    return redirect(_next_url(area_id))


@areas_bp.route("/folders/<int:area_folder_id>/set-default", methods=["POST"])
def area_folder_set_default_route(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if folder:
        areas_mod.area_folder_set_default(folder["area_id"], area_folder_id)
        return redirect(_next_url(folder["area_id"]))
    return redirect(_next_url(""))


@areas_bp.route("/folders/<int:area_folder_id>/open", methods=["POST"])
def area_folder_open_route(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if not folder:
        abort(404)
    folder_path = (folder.get("path_prefix") or "").strip()
    if not folder_path or not os.path.isdir(folder_path):
        abort(404)
    if sys.platform.startswith("win"):
        os.startfile(folder_path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder_path])
    else:
        subprocess.Popen(["xdg-open", folder_path])
    return redirect(_next_url(folder["area_id"]))


@areas_bp.route("/folders/<int:area_folder_id>/toggle", methods=["POST"])
def area_folder_toggle_route(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if not folder:
        return redirect(_next_url(""))
    if int(folder.get("is_enabled") or 0) == 1:
        areas_mod.area_folder_disable(area_folder_id)
    else:
        areas_mod.area_folder_enable(area_folder_id)
    return redirect(_next_url(folder["area_id"]))


@areas_bp.route("/folders/<int:area_folder_id>/remove", methods=["POST"])
def area_folder_remove_route(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if folder:
        areas_mod.area_folder_remove(area_folder_id)
        return redirect(_next_url(folder["area_id"]))
    return redirect(_next_url(""))
