from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from common import data
from common import projects as projects_mod
from common import links_records
from common.utils import get_side_tabs, get_tabs, request_area_param


projects_bp = Blueprint("projects", __name__, template_folder="templates")


def _ensure_schema():
    projects_mod.ensure_projects_schema(data._get_conn())


def _next_url(default=""):
    return request.form.get("next") or request.args.get("next") or request.referrer or default or url_for("projects.list_projects_route")


def _project_form_values(form):
    return {
        "name": form.get("name", "").strip(),
        "project_type": form.get("project_type", "").strip(),
        "description": form.get("description", "").strip(),
        "status": form.get("status", "planned").strip(),
        "start_date": form.get("start_date", "").strip(),
        "end_date": form.get("end_date", "").strip(),
        "parent_project_id": form.get("parent_project_id", "").strip(),
        "icon": form.get("icon", "").strip(),
        "comments": form.get("comments", "").strip(),
        "sort_order": form.get("sort_order", "100").strip(),
        "pinned": form.get("pinned") == "1",
        "area_ids": form.getlist("area_ids"),
    }


def _render_project_form(project=None, error="", message=""):
    _ensure_schema()
    area = request_area_param() or ""
    selected_area_ids = project.get("area_ids", []) if project else ([area] if area else [])
    group_by = request.args.get("group_by") or "type"
    return render_template(
        "projects_edit.html",
        active_tab="projects",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=("Project: " + project["name"]) if project else "Add Project",
        content_html="",
        project=project,
        area=area,
        error=error,
        message=message or request.args.get("message", ""),
        status_options=projects_mod.status_options(),
        area_options=projects_mod.area_options(selected_area_ids=selected_area_ids),
        parent_projects=projects_mod.parent_project_options(project.get("project_id") if project else None),
        content_groups=projects_mod.grouped_project_items(project["project_id"], group_by=group_by) if project else [],
        group_by=group_by,
    )


@projects_bp.route("/")
def list_projects_route():
    _ensure_schema()
    area = request_area_param() or ""
    status = (request.args.get("status") or "").strip().lower()
    statuses = [status] if status and status != "all" else None
    projects = projects_mod.project_list(
        statuses=statuses,
        area_id=area,
        include_archived=(status == "all"),
    )
    return render_template(
        "projects_list.html",
        active_tab="projects",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Projects ({area or 'All Areas'})",
        content_html="",
        projects=projects,
        area=area,
        active_status=status,
        status_options=projects_mod.status_options(),
    )


@projects_bp.route("/add", methods=["GET", "POST"])
def add_project_route():
    _ensure_schema()
    if request.method == "POST":
        try:
            project_id = projects_mod.create_project(_project_form_values(request.form))
        except ValueError as exc:
            return _render_project_form(project=None, error=str(exc))
        return redirect(url_for("projects.view_project_route", project_id=project_id, message="Project created."))
    return _render_project_form(project=None)


@projects_bp.route("/<int:project_id>", methods=["GET", "POST"])
@projects_bp.route("/edit/<int:project_id>", methods=["GET", "POST"])
def view_project_route(project_id):
    _ensure_schema()
    project = projects_mod.project_get(project_id)
    if not project:
        return redirect(url_for("projects.list_projects_route", message="Project not found."))
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "archive":
            projects_mod.project_archive(project_id)
            return redirect(url_for("projects.list_projects_route", message="Project archived."))
        if action == "delete":
            projects_mod.project_delete(project_id)
            return redirect(url_for("projects.list_projects_route", message="Project deleted."))
        try:
            projects_mod.update_project(project_id, _project_form_values(request.form))
        except ValueError as exc:
            project = projects_mod.project_get(project_id)
            return _render_project_form(project=project, error=str(exc))
        return redirect(url_for("projects.view_project_route", project_id=project_id, message="Project saved."))
    return _render_project_form(project=project)


@projects_bp.route("/items/add", methods=["POST"])
def add_project_item_route():
    _ensure_schema()
    project_id = request.form.get("project_id", type=int)
    if project_id:
        projects_mod.add_project_item(
            project_id,
            request.form.get("item_type"),
            request.form.get("item_id"),
            item_title=request.form.get("item_title"),
            section=request.form.get("section", ""),
            pinned=1 if request.form.get("pinned") == "1" else 0,
            is_primary=1 if request.form.get("is_primary") == "1" else 0,
        )
    return redirect(_next_url(url_for("projects.view_project_route", project_id=project_id) if project_id else ""))


@projects_bp.route("/assign", methods=["POST"])
def assign_project_route():
    _ensure_schema()
    project_id = request.form.get("project_id", type=int)
    item_type = request.form.get("item_type", "")
    item_id = request.form.get("item_id", "")
    if project_id and item_type and item_id:
        projects_mod.assign_item_to_project(
            project_id,
            item_type,
            item_id,
            item_title=request.form.get("item_title", ""),
            is_primary=1 if request.form.get("is_primary") == "1" else 0,
        )
    return redirect(_next_url())


@projects_bp.route("/items/<int:project_item_id>/update", methods=["POST"])
def update_project_item_route(project_item_id):
    _ensure_schema()
    projects_mod.update_project_item(project_item_id, request.form)
    return redirect(_next_url())


@projects_bp.route("/items/<int:project_item_id>/move", methods=["POST"])
def move_project_item_route(project_item_id):
    _ensure_schema()
    projects_mod.move_project_item(project_item_id, request.form.get("direction"))
    return redirect(_next_url())


@projects_bp.route("/items/<int:project_item_id>/remove", methods=["POST"])
def remove_project_item_route(project_item_id):
    _ensure_schema()
    projects_mod.remove_project_item(project_item_id)
    return redirect(_next_url())


@projects_bp.route("/api/<int:project_id>/items", methods=["POST"])
def add_project_items_api(project_id):
    _ensure_schema()
    payload = request.get_json(silent=True) or {}
    raw_items = payload.get("items") or []
    if not raw_items and payload.get("item_type") and payload.get("item_id"):
        raw_items = [payload]
    results = []
    for item in raw_items:
        try:
            results.append(
                projects_mod.add_project_item(
                    project_id,
                    item.get("type") or item.get("item_type"),
                    item.get("id") or item.get("item_id"),
                    item_title=item.get("title") or item.get("item_title"),
                    section=payload.get("section") or item.get("section") or "",
                    is_primary=1 if item.get("is_primary") else 0,
                )
            )
        except ValueError as exc:
            results.append({"created": False, "error": str(exc)})
    return jsonify({"results": results})


@projects_bp.route("/api/search")
def project_record_search_api():
    query = request.args.get("q", "")
    types_param = request.args.get("types", "")
    types = [part.strip() for part in types_param.split(",") if part.strip()]
    limit = request.args.get("limit", type=int) or 30
    return jsonify({"results": links_records.search_records(query, types=types, limit=limit)})
