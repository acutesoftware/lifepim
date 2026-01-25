from flask import Blueprint, jsonify, redirect, request, url_for

from common import projects as projects_mod

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


def _next_url(project_id):
    return request.form.get("next") or request.args.get("next") or url_for(
        "notes.list_notes_route", proj=project_id
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
