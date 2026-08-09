from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for

from common import config as cfg
from common import projects as projects_mod
from common.utils import build_pagination, get_side_tabs, get_tabs, paginate_total, request_area_param
from modules.apps import schema as apps_model
from modules.tasks import schema as tasks_model
from utils import importer


tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks", template_folder="templates", static_folder="static")

TASK_VIEWS = (
    ("all", "All"),
    ("today", "Today"),
    ("upcoming", "Upcoming"),
    ("templates", "Templates"),
    ("completed", "Completed"),
)


def _area():
    return request_area_param(include_form=True, include_id=True) or None


def _args_with(**updates):
    values = {
        "area": _area(),
        "view": request.values.get("view", "all"),
        "q": request.values.get("q", ""),
        "page": request.values.get("page", ""),
        "message": request.values.get("message", ""),
    }
    values.update(updates)
    return {key: value for key, value in values.items() if value not in (None, "")}


def _form_task_values(form, existing=None):
    action_id = form.get("app_action_id", type=int)
    action = apps_model.app_action_get(action_id) if action_id else None
    parameter_values = {}
    if action:
        parameter_values = apps_model.parameter_values_from_form(form, action.get("parameter_schema_json"), prefix="param_")
    return {
        "title": form.get("title", "").strip(),
        "content": form.get("content", "").strip(),
        "area": request_area_param(existing.get("area") if existing else "", include_form=True) or "",
        "start_date": form.get("start_date", "").strip(),
        "due_date": form.get("due_date", "").strip(),
        "status": form.get("status", (existing or {}).get("status") or "open"),
        "task_kind": form.get("task_kind", (existing or {}).get("task_kind") or "task"),
        "app_action_id": action_id,
        "parameter_values": parameter_values,
    }


def _selected_action_context(task=None, selected_action_id=None):
    action_id = selected_action_id or (task or {}).get("app_action_id")
    action = apps_model.app_action_get(action_id) if action_id else None
    existing_values = (task or {}).get("parameter_values") or {}
    schema_json = action.get("parameter_schema_json") if action else ""
    return {
        "selected_action": action,
        "parameter_schema": apps_model.parameter_schema_from_json(schema_json),
        "parameter_values": apps_model.default_parameter_values(schema_json, existing_values),
    }


def _render_edit(task, area, error="", selected_action_id=None):
    context = _selected_action_context(task, selected_action_id)
    return render_template(
        "tasks_edit.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Task" if task else "Add Task",
        content_html="",
        task=task,
        area=area,
        error=error,
        status_options=tasks_model.TASK_STATUSES,
        kind_options=tasks_model.TASK_KINDS,
        action_options=apps_model.app_action_options(),
        selected_action=context["selected_action"],
        parameter_schema=context["parameter_schema"],
        parameter_values=context["parameter_values"],
        project_options=projects_mod.project_list(statuses=("planned", "active")),
        record_projects=projects_mod.record_projects("task", task["id"]) if task else [],
    )


@tasks_bp.route("/", methods=["GET", "POST"])
def list_tasks_route():
    area = _area()
    if request.method == "POST":
        title = request.form.get("quick_title", "").strip()
        if title:
            task_id = tasks_model.quick_add(title, area=area or "")
            return redirect(url_for("tasks.edit_task_route", task_id=task_id, message="Task added."))
    tasks_model.ensure_tasks_schema()
    view_filter = request.values.get("view", "all")
    if view_filter not in {view_id for view_id, _ in TASK_VIEWS}:
        view_filter = "all"
    query = request.values.get("q", "").strip()
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = tasks_model.task_count(area_id=area, view_filter=view_filter, query=query)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    tasks = tasks_model.task_list(
        area_id=area,
        view_filter=view_filter,
        query=query,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    pagination = build_pagination(
        url_for,
        "tasks.list_tasks_route",
        {"area": area, "view": view_filter, "q": query},
        page,
        page_data["total_pages"],
    )
    resp = make_response(
        render_template(
            "tasks_list.html",
            active_tab="tasks",
            tabs=get_tabs(),
            side_tabs=get_side_tabs(),
            content_title=f"Tasks ({area or 'All'})",
            content_html="",
            tasks=tasks,
            area=area,
            task_views=TASK_VIEWS,
            view_filter=view_filter,
            query=query,
            message=request.values.get("message", ""),
            page=page,
            total_pages=page_data["total_pages"],
            pages=pagination["pages"],
            first_url=pagination["first_url"],
            last_url=pagination["last_url"],
        )
    )
    return resp


@tasks_bp.route("/add", methods=["GET", "POST"])
def add_task_route():
    area = _area() or ""
    preselect_action_id = request.args.get("app_action_id", type=int)
    error = ""
    if request.method == "POST":
        try:
            values = _form_task_values(request.form)
            task_id = tasks_model.create_task(values)
            project_id = request.form.get("project_id", type=int)
            if project_id:
                projects_mod.assign_item_to_project(
                    project_id,
                    "task",
                    task_id,
                    item_title=values["title"],
                    is_primary=1 if request.form.get("project_is_primary") == "1" else 0,
                )
            return redirect(url_for("tasks.edit_task_route", task_id=task_id, message="Task saved."))
        except Exception as exc:
            error = str(exc)
            preselect_action_id = request.form.get("app_action_id", type=int)
    return _render_edit(None, area, error=error, selected_action_id=preselect_action_id)


@tasks_bp.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task_route(task_id):
    task = tasks_model.task_get(task_id)
    if not task:
        abort(404)
    selected_action_id = request.args.get("app_action_id", type=int)
    error = ""
    if request.method == "POST":
        try:
            values = _form_task_values(request.form, existing=task)
            tasks_model.update_task(task_id, values)
            project_id = request.form.get("project_id", type=int)
            if project_id:
                projects_mod.assign_item_to_project(
                    project_id,
                    "task",
                    task_id,
                    item_title=values["title"],
                    is_primary=1 if request.form.get("project_is_primary") == "1" else 0,
                )
            return redirect(url_for("tasks.edit_task_route", task_id=task_id, message="Task saved."))
        except Exception as exc:
            error = str(exc)
            task = tasks_model.task_get(task_id) or task
            return _render_edit(task, task.get("area") or "", error=error, selected_action_id=request.form.get("app_action_id", type=int))
    return _render_edit(task, task.get("area") or "", error=error, selected_action_id=selected_action_id)


@tasks_bp.route("/delete/<int:task_id>", methods=["POST", "GET"])
def delete_task_route(task_id):
    tasks_model.delete_task(task_id)
    return redirect(url_for("tasks.list_tasks_route", **_args_with()))


@tasks_bp.route("/done/<int:task_id>", methods=["POST"])
def mark_done_route(task_id):
    tasks_model.set_status(task_id, "done")
    return redirect(request.referrer or url_for("tasks.list_tasks_route", **_args_with(message="Task marked done.")))


@tasks_bp.route("/reopen/<int:task_id>", methods=["POST"])
def reopen_task_route(task_id):
    tasks_model.set_status(task_id, "open")
    return redirect(request.referrer or url_for("tasks.list_tasks_route", **_args_with(message="Task reopened.")))


@tasks_bp.route("/run/<int:task_id>", methods=["POST"])
def run_task_route(task_id):
    try:
        action = tasks_model.run_task(task_id)
        message = f"{action.get('action_name') or 'App Action'} launched."
        return redirect(url_for("tasks.edit_task_route", task_id=task_id, message=message))
    except Exception as exc:
        return redirect(url_for("tasks.edit_task_route", task_id=task_id, message=str(exc)))


@tasks_bp.route("/template/<int:template_id>/create", methods=["POST", "GET"])
def create_from_template_route(template_id):
    try:
        task_id = tasks_model.create_task_from_template(template_id)
        return redirect(url_for("tasks.edit_task_route", task_id=task_id, message="Task created from template."))
    except Exception as exc:
        return redirect(url_for("tasks.list_tasks_route", **_args_with(view="templates", message=str(exc))))


@tasks_bp.route("/import", methods=["GET", "POST"])
def import_tasks_route():
    area = _area() or ""
    csv_path = ""
    headers = []
    mappings = {}
    imported = None
    error = "Task import still uses the generic CSV mapper; imported rows become open human Tasks unless mapped otherwise."
    if request.method == "POST":
        csv_path = request.form.get("csv_path", "").strip()
        upload = request.files.get("csv_file")
        if upload and upload.filename:
            csv_path = importer.save_upload(upload)
        headers = importer.read_csv_headers(csv_path)
    return render_template(
        "tasks_import.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Tasks",
        content_html="",
        area=area,
        table_def={"col_list": [col for col in tasks_model.TASK_COLUMNS if col not in {"id", "owner_user_id", "user_name", "rec_extract_date"}]},
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
    )
