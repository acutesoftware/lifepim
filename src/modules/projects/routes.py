import os
import subprocess
import sys

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from common import projects as projects_mod
from common.utils import get_side_tabs, get_tabs
from core import security

projects_bp = Blueprint("projects", __name__, url_prefix="/projects", template_folder="templates")


def _next_url(project_id):
    return request.form.get("next") or request.args.get("next") or url_for(
        "notes.list_notes_route", proj=project_id
    )


def _sidebar_rows_from_form(form):
    rows = []
    ids = form.getlist("project_id")
    labels = form.getlist("project_name")
    icons = form.getlist("icon")
    groups = form.getlist("group_name")
    row_types = form.getlist("row_type")
    system_flags = form.getlist("is_system")
    max_len = max(len(ids), len(labels), len(icons), len(groups), len(row_types), len(system_flags))
    for idx in range(max_len):
        project_id = ids[idx].strip() if idx < len(ids) else ""
        project_name = labels[idx].strip() if idx < len(labels) else ""
        if not project_id or not project_name:
            continue
        row_type = row_types[idx] if idx < len(row_types) else "project"
        rows.append(
            {
                "project_id": project_id,
                "project_name": project_name,
                "icon": icons[idx] if idx < len(icons) else "",
                "group_name": groups[idx] if idx < len(groups) else "",
                "is_header": 1 if row_type == "header" else 0,
                "is_system": int(system_flags[idx] or 0) if idx < len(system_flags) else 0,
                "status": "active",
                "sort_order": idx * 10,
            }
        )
    new_type = (form.get("new_row_type") or "project").strip()
    new_id = (form.get("new_project_id") or "").strip()
    new_label = (form.get("new_project_name") or "").strip()
    if new_id and new_label:
        rows.append(
            {
                "project_id": new_id,
                "project_name": new_label,
                "icon": form.get("new_icon") or "",
                "group_name": form.get("new_group_name") or "",
                "is_header": 1 if new_type == "header" else 0,
                "is_system": 0,
                "status": "active",
                "sort_order": len(rows) * 10,
            }
        )
    return rows


@projects_bp.route("/edit", methods=["GET", "POST"])
def edit_projects_route():
    security.require_login()
    message = request.args.get("message", "")
    error = ""
    if request.method == "POST":
        action = request.form.get("action", "save")
        try:
            if action == "reset":
                count = projects_mod.seed_default_projects_for_user(current_user.user_id, replace=True)
                return redirect(url_for("projects.edit_projects_route", message=f"Reset {count} project rows."))
            rows = _sidebar_rows_from_form(request.form)
            projects_mod.save_user_sidebar_rows(rows, owner_user_id=current_user.user_id)
            return redirect(url_for("projects.edit_projects_route", message="Projects saved."))
        except Exception as exc:
            error = f"Projects were not saved: {exc}"
    rows = projects_mod.projects_side_tabs(owner_user_id=current_user.user_id, seed=True)
    return render_template(
        "projects_edit.html",
        active_tab="admin",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Projects",
        content_html="",
        project_rows=rows,
        message=message,
        error=error,
    )


@projects_bp.route("/api/default-folder")
def project_default_folder_route():
    project_id = (request.args.get("project_id") or request.args.get("proj") or "").strip()
    if not project_id:
        return jsonify({"error": "Project is required."}), 400
    try:
        path_prefix = projects_mod.project_default_folder_get(project_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"project_id": project_id, "path_prefix": path_prefix})


@projects_bp.route("/api/folders", methods=["POST"])
def project_folder_add_api():
    payload = request.get_json(silent=True) or {}
    project_id = (payload.get("project_id") or "").strip()
    path_prefix = (payload.get("path_prefix") or "").strip()
    folder_role = (payload.get("folder_role") or "include").strip()
    create_type = (payload.get("create_type") or "none").strip()
    if not project_id or not path_prefix:
        return jsonify({"error": "Project and path are required."}), 400
    try:
        folder_id = projects_mod.project_folder_add(
            project_id,
            path_prefix,
            folder_role=folder_role,
            create_type=create_type,
            is_write_enabled=1 if folder_role == "default" else 0,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    folder = projects_mod.project_folder_get(folder_id)
    return jsonify({"folder": folder})


@projects_bp.route("/api/folders/<int:project_folder_id>/set-default", methods=["POST"])
def project_folder_set_default_api(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
    if not folder:
        return jsonify({"error": "Folder not found."}), 404
    projects_mod.project_folder_set_default(folder["project_id"], project_folder_id)
    folder = projects_mod.project_folder_get(project_folder_id)
    return jsonify({"folder": folder})


@projects_bp.route("/folders/add", methods=["POST"])
def project_folder_add_route():
    project_id = (request.form.get("project_id") or "").strip()
    path_prefix = (request.form.get("path_prefix") or "").strip()
    folder_role = (request.form.get("folder_role") or "include").strip()
    create_type = (request.form.get("create_type") or "none").strip()
    if not project_id or not path_prefix:
        return redirect(_next_url(project_id))
    try:
        folder_id = projects_mod.project_folder_add(
            project_id,
            path_prefix,
            folder_role=folder_role,
            create_type=create_type,
            is_write_enabled=1 if folder_role == "default" else 0,
        )
    except ValueError:
        return redirect(_next_url(project_id))
    return redirect(_next_url(project_id))


@projects_bp.route("/folders/<int:project_folder_id>/set-default", methods=["POST"])
def project_folder_set_default_route(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
    if folder:
        projects_mod.project_folder_set_default(folder["project_id"], project_folder_id)
        return redirect(_next_url(folder["project_id"]))
    return redirect(_next_url(""))


@projects_bp.route("/folders/<int:project_folder_id>/open", methods=["POST"])
def project_folder_open_route(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
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
    return redirect(_next_url(folder["project_id"]))


@projects_bp.route("/folders/<int:project_folder_id>/toggle", methods=["POST"])
def project_folder_toggle_route(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
    if not folder:
        return redirect(_next_url(""))
    if int(folder.get("is_enabled") or 0) == 1:
        projects_mod.project_folder_disable(project_folder_id)
    else:
        projects_mod.project_folder_enable(project_folder_id)
    return redirect(_next_url(folder["project_id"]))


@projects_bp.route("/folders/<int:project_folder_id>/remove", methods=["POST"])
def project_folder_remove_route(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
    if folder:
        projects_mod.project_folder_remove(project_folder_id)
        return redirect(_next_url(folder["project_id"]))
    return redirect(_next_url(""))
