import json

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from common.utils import build_pagination, get_side_tabs, get_tabs, lg_usr, paginate_total, request_area_param
from common import config as cfg
from modules.apps import schema as apps_model
from modules.tasks import schema as tasks_model
from modules.apps.importers import (
    AppImportCandidate,
    DesktopAppImporter,
    DevFolderAppImporter,
    TaskbarAppImporter,
    import_selected_candidates,
    mark_candidate_duplicates,
)


apps_bp = Blueprint(
    "apps",
    __name__,
    url_prefix="/apps",
    template_folder="templates",
    static_folder="static",
)


SAVED_VIEWS = (
    ("all", "All"),
    ("favorites", "Favorites"),
    ("recent", "Recent"),
    ("projects", "Projects"),
    ("scripts", "Scripts"),
    ("applications", "Applications"),
)


def _area():
    return request_area_param(include_form=True, include_id=True) or None


def _args_with(**updates):
    values = {
        "area": _area(),
        "saved_view": request.values.get("saved_view", "all"),
        "mode": request.values.get("mode", "grid"),
        "q": request.values.get("q", ""),
        "sort": request.values.get("sort", ""),
        "dir": request.values.get("dir", ""),
        "page": request.values.get("page", ""),
        "message": request.values.get("message", ""),
    }
    values.update(updates)
    return {key: value for key, value in values.items() if value not in (None, "")}


def _form_values(form, area):
    area_ids = form.getlist("area_ids")
    if not area_ids and area:
        area_ids = [area]
    return {
        "title": form.get("title", "").strip(),
        "kind": form.get("kind", "").strip(),
        "description": form.get("description", "").strip(),
        "icon": form.get("icon", "").strip(),
        "favorite": form.get("favorite"),
        "enabled": form.get("enabled", "1"),
        "path": form.get("path", "").strip(),
        "repository_url": form.get("repository_url", "").strip(),
        "website_url": form.get("website_url", "").strip(),
        "language": form.get("language", "").strip(),
        "version": form.get("version", "").strip(),
        "tags": form.get("tags", "").strip(),
        "comments": form.get("comments", "").strip(),
        "area_ids": area_ids,
        "actions": _action_values(form),
    }


def _action_values(form):
    rows = []
    default_idx = form.get("default_action_idx", "")
    ids = form.getlist("app_action_id")
    names = form.getlist("action_name")
    types = form.getlist("action_type")
    commands = form.getlist("action_command")
    workdirs = form.getlist("action_working_directory")
    args = form.getlist("action_arguments")
    agent_allowed = set(form.getlist("action_agent_allowed"))
    requires_confirmation = set(form.getlist("action_requires_confirmation"))
    for idx, name in enumerate(names):
        rows.append(
            {
                "app_action_id": ids[idx] if idx < len(ids) else "",
                "action_name": name,
                "action_type": types[idx] if idx < len(types) else "",
                "command": commands[idx] if idx < len(commands) else "",
                "working_directory": workdirs[idx] if idx < len(workdirs) else "",
                "arguments": args[idx] if idx < len(args) else "",
                "parameter_schema_json": _parameter_schema_from_action_form(form, idx),
                "agent_allowed": str(idx) in agent_allowed,
                "requires_confirmation": str(idx) in requires_confirmation,
                "sort_order": idx * 10,
                "is_default": str(idx) == str(default_idx),
            }
        )
    return rows


def _parameter_schema_from_action_form(form, idx):
    parameters = []
    names = form.getlist(f"param_name_{idx}")
    labels = form.getlist(f"param_label_{idx}")
    types = form.getlist(f"param_type_{idx}")
    defaults = form.getlist(f"param_default_{idx}")
    options = form.getlist(f"param_options_{idx}")
    required = set(form.getlist(f"param_required_{idx}"))
    for param_idx, name in enumerate(names):
        if not (name or "").strip():
            continue
        parameters.append(
            {
                "name": name,
                "label": labels[param_idx] if param_idx < len(labels) else "",
                "type": types[param_idx] if param_idx < len(types) else "text",
                "required": str(param_idx) in required,
                "default": defaults[param_idx] if param_idx < len(defaults) else "",
                "options": options[param_idx] if param_idx < len(options) else "",
            }
        )
    return {"version": 1, "parameters": parameters}


def _render_apps_index(area, item=None, launch_error="", message=""):
    message = message or request.values.get("message", "")
    apps_model.ensure_apps_schema()
    saved_view = request.values.get("saved_view", "all")
    mode = request.values.get("mode", "grid")
    query = request.values.get("q", "").strip()
    sort_col = request.args.get("sort") or "title"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = apps_model.app_count(area_id=area, view_filter=saved_view, query=query)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    offset = (page - 1) * per_page
    items = apps_model.app_list(
        area_id=area,
        view_filter=saved_view,
        query=query,
        sort_col=sort_col,
        sort_dir=sort_dir,
        limit=per_page,
        offset=offset,
    )
    if not item and items:
        item = items[0]
    related_tasks = tasks_model.related_tasks_for_app(item["app_id"]) if item else []
    pagination = build_pagination(
        url_for,
        "apps.list_apps_table_route",
        {
            "area": area,
            "saved_view": saved_view,
            "mode": mode,
            "q": query,
            "sort": sort_col,
            "dir": sort_dir,
        },
        page,
        page_data["total_pages"],
    )
    return render_template(
        "apps_index.html",
        active_tab="apps",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Apps ({area or 'All'})",
        content_html="",
        area=area,
        items=items,
        total=total,
        selected_app=item,
        saved_views=SAVED_VIEWS,
        saved_view=saved_view,
        mode=mode,
        query=query,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=page_data["total_pages"],
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        launch_error=launch_error,
        message=message,
        related_tasks=related_tasks,
    )


def _import_source_choices():
    return (
        ("dev_folders", "Dev Folders"),
        ("taskbar", "Taskbar"),
        ("desktop", "Desktop"),
    )


def _default_import_area(source, area):
    if area and area.lower() not in {"all", "all areas", "any", "unmapped"}:
        return area
    if source == "dev_folders":
        for option in apps_model.area_options():
            option_id = (option.get("area_id") or "").strip()
            label = (option.get("label") or "").strip().lower()
            if option_id.lower() in {"dev", "development"} or label == "development":
                return option_id
    return ""


def _scan_import_candidates(source, form):
    default_area = (form.get("default_area_id") or "").strip()
    if source == "dev_folders":
        importer = DevFolderAppImporter(
            form.get("root_folder", ""),
            default_area_id=default_area,
            default_kind=form.get("default_kind") or "Development Project",
        )
    elif source == "taskbar":
        importer = TaskbarAppImporter(default_area_id=default_area)
    else:
        importer = DesktopAppImporter(default_area_id=default_area)
    scan_result = importer.scan()
    mark_candidate_duplicates(scan_result.candidates)
    _log_import_errors(source, scan_result.errors)
    return scan_result


def _candidate_json(candidates):
    return json.dumps([candidate.as_dict() for candidate in candidates], sort_keys=True)


def _candidates_from_form(form):
    try:
        rows = json.loads(form.get("candidates_json") or "[]")
    except json.JSONDecodeError:
        rows = []
    candidates = [AppImportCandidate.from_dict(row) for row in rows]
    selected = set(form.getlist("candidate_selected"))
    kinds = dict(zip(form.getlist("candidate_id"), form.getlist("candidate_kind")))
    areas = dict(zip(form.getlist("candidate_id"), form.getlist("candidate_area_id")))
    for candidate in candidates:
        candidate.selected = candidate.candidate_id in selected
        if candidate.candidate_id in kinds:
            candidate.kind = kinds[candidate.candidate_id]
        if candidate.candidate_id in areas:
            candidate.area_id = areas[candidate.candidate_id]
    return candidates


def _render_import(source=None, candidates=None, scan_messages=None, scan_errors=None, import_result=None, error=""):
    area = _area()
    source = source or request.values.get("source") or "dev_folders"
    if source not in {choice[0] for choice in _import_source_choices()}:
        source = "dev_folders"
    default_area = request.values.get("default_area_id") or _default_import_area(source, area)
    default_kind = request.values.get("default_kind") or "Development Project"
    root_folder = request.values.get("root_folder") or ""
    candidates = candidates or []
    selected_area_ids = [default_area] + [candidate.area_id for candidate in candidates if candidate.area_id]
    new_count = sum(1 for candidate in candidates if candidate.status == "NEW")
    selected_count = sum(1 for candidate in candidates if candidate.status == "NEW" and candidate.selected)
    return render_template(
        "apps_import.html",
        active_tab="apps",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Apps > Import",
        content_html="",
        area=area,
        source=source,
        source_choices=_import_source_choices(),
        root_folder=root_folder,
        default_area=default_area,
        default_kind=default_kind,
        kind_options=apps_model.APP_KIND_OPTIONS,
        area_options=apps_model.area_options(selected_area_ids),
        candidates=candidates,
        candidates_json=_candidate_json(candidates),
        scan_messages=scan_messages or [],
        scan_errors=scan_errors or [],
        import_result=import_result,
        error=error,
        new_count=new_count,
        selected_count=selected_count,
    )


def _log_import_errors(source, errors):
    for error in errors or []:
        try:
            lg_usr(
                action="app_import_error",
                entity_type="lp_app",
                context_type="apps_import",
                context_id=source,
                extra={"error": error},
            )
        except Exception:
            pass


@apps_bp.route("/")
def list_apps_route():
    return list_apps_table_route()


@apps_bp.route("/table")
def list_apps_table_route():
    return _render_apps_index(_area())


@apps_bp.route("/list")
def list_apps_list_route():
    return redirect(url_for("apps.list_apps_table_route", **_args_with(mode="list")))


@apps_bp.route("/cards")
def list_apps_cards_route():
    return redirect(url_for("apps.list_apps_table_route", **_args_with(mode="grid")))


@apps_bp.route("/view/<int:item_id>")
def view_app_route(item_id):
    area = _area()
    item = apps_model.app_get(item_id)
    if not item:
        abort(404)
    return _render_apps_index(area, item=item)


@apps_bp.route("/launch/<int:item_id>")
def launch_app_route(item_id):
    area = _area()
    try:
        item = apps_model.app_get(item_id)
        action = (item or {}).get("default_action")
        if action and apps_model.action_has_parameters(action):
            return _render_run(item, action)
        apps_model.launch_action(item_id)
    except Exception as exc:
        item = apps_model.app_get(item_id)
        return _render_apps_index(area, item=item, launch_error=str(exc))
    return redirect(url_for("apps.view_app_route", item_id=item_id, **_args_with()))


@apps_bp.route("/action/<int:action_id>/launch/<int:item_id>")
def launch_app_action_route(item_id, action_id):
    area = _area()
    try:
        action = apps_model.app_action_get(action_id)
        if action and apps_model.action_has_parameters(action):
            return _render_run(apps_model.app_get(item_id), action)
        apps_model.launch_action(item_id, action_id=action_id)
    except Exception as exc:
        item = apps_model.app_get(item_id)
        return _render_apps_index(area, item=item, launch_error=str(exc))
    return redirect(url_for("apps.view_app_route", item_id=item_id, **_args_with()))


@apps_bp.route("/add", methods=["GET", "POST"])
def add_app_route():
    area = _area()
    error = ""
    if request.method == "POST":
        try:
            app_id = apps_model.create_app(_form_values(request.form, area))
            return redirect(url_for("apps.view_app_route", item_id=app_id, area=area))
        except Exception as exc:
            error = str(exc)
    return _render_edit(None, area, error=error)


def _render_edit(item, area, error=""):
    selected_area_ids = item.get("area_ids", []) if item else ([area] if area else [])
    actions = list(item.get("actions", [])) if item else []
    for action in actions:
        action["parameter_schema"] = apps_model.parameter_schema_from_json(action.get("parameter_schema_json"))
    for _ in range(3):
        actions.append({"parameter_schema": {"version": 1, "parameters": []}})
    return render_template(
        "apps_edit.html",
        active_tab="apps",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit App" if item else "Add App",
        content_html="",
        item=item,
        area=area,
        error=error,
        kind_options=apps_model.APP_KIND_OPTIONS,
        action_type_options=apps_model.ACTION_TYPE_OPTIONS,
        area_options=apps_model.area_options(selected_area_ids),
        actions=actions,
        parameter_type_options=apps_model.PARAMETER_TYPE_OPTIONS,
    )


def _render_run(item, action, error=""):
    schema = apps_model.parameter_schema_from_json(action.get("parameter_schema_json"))
    values = apps_model.default_parameter_values(action.get("parameter_schema_json"))
    return render_template(
        "apps_run.html",
        active_tab="apps",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Run: {action.get('action_name') or item.get('title')}",
        content_html="",
        item=item,
        action=action,
        parameter_schema=schema,
        parameter_values=values,
        error=error,
        area=_area(),
    )


@apps_bp.route("/action/<int:action_id>/run/<int:item_id>", methods=["GET", "POST"])
def run_app_action_route(item_id, action_id):
    item = apps_model.app_get(item_id)
    action = apps_model.app_action_get(action_id)
    if not item or not action or action.get("app_id") != item_id:
        abort(404)
    if request.method == "POST":
        try:
            values = apps_model.parameter_values_from_form(request.form, action.get("parameter_schema_json"), prefix="param_")
            apps_model.launch_action(item_id, action_id=action_id, parameter_values=values)
            return redirect(url_for("apps.view_app_route", item_id=item_id, **_args_with(message=f"{action.get('action_name') or 'App Action'} launched.")))
        except Exception as exc:
            schema = apps_model.parameter_schema_from_json(action.get("parameter_schema_json"))
            values = apps_model.default_parameter_values(
                action.get("parameter_schema_json"),
                apps_model.parameter_values_from_form(request.form, action.get("parameter_schema_json"), prefix="param_"),
            )
            return render_template(
                "apps_run.html",
                active_tab="apps",
                tabs=get_tabs(),
                side_tabs=get_side_tabs(),
                content_title=f"Run: {action.get('action_name') or item.get('title')}",
                content_html="",
                item=item,
                action=action,
                parameter_schema=schema,
                parameter_values=values,
                error=str(exc),
                area=_area(),
            )
    return _render_run(item, action)


@apps_bp.route("/browse-path")
def browse_path_route():
    try:
        import tkinter as tk
        from tkinter import filedialog

        target = (request.args.get("target") or "file").lower()
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if target == "folder":
            path = filedialog.askdirectory(title="Select folder")
        else:
            path = filedialog.askopenfilename(
                title="Select app target",
                filetypes=[
                    ("Launchable files", "*.exe *.bat *.cmd *.ps1 *.py *.pyw *.sql *.db *.sqlite *.sqlite3 *.lnk *.html *.htm"),
                    ("Python files", "*.py *.pyw"),
                    ("Executables", "*.exe *.bat *.cmd *.lnk"),
                    ("All files", "*.*"),
                ],
            )
        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as exc:
        return jsonify({"path": "", "error": str(exc)}), 500


@apps_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_app_route(item_id):
    area = _area()
    item = apps_model.app_get(item_id)
    if not item:
        abort(404)
    error = ""
    if request.method == "POST":
        try:
            apps_model.update_app(item_id, _form_values(request.form, area))
            return redirect(url_for("apps.view_app_route", item_id=item_id, area=area))
        except Exception as exc:
            error = str(exc)
            item = apps_model.app_get(item_id) or item
    return _render_edit(item, area, error=error)


@apps_bp.route("/delete/<int:item_id>", methods=["GET", "POST"])
def delete_app_route(item_id):
    try:
        apps_model.delete_app(item_id)
    except Exception as exc:
        item = apps_model.app_get(item_id)
        return _render_apps_index(_area(), item=item, launch_error=str(exc))
    return redirect(url_for("apps.list_apps_table_route", **_args_with()))


@apps_bp.route("/refresh-icons", methods=["POST"])
def refresh_icons_route():
    updated = apps_model.refresh_missing_executable_icons()
    return redirect(url_for("apps.list_apps_table_route", **_args_with(message=f"{updated} app icons refreshed.")))


@apps_bp.route("/import", methods=["GET", "POST"])
def import_apps_route():
    source = request.values.get("source") or "dev_folders"
    if request.method == "POST":
        intent = request.form.get("intent") or "scan"
        if intent == "scan":
            scan_result = _scan_import_candidates(source, request.form)
            return _render_import(
                source=source,
                candidates=scan_result.candidates,
                scan_messages=scan_result.messages,
                scan_errors=scan_result.errors,
            )
        if intent == "import":
            candidates = _candidates_from_form(request.form)
            result = import_selected_candidates(candidates)
            mark_candidate_duplicates(candidates)
            _log_import_errors(source, result.errors)
            return _render_import(
                source=source,
                candidates=candidates,
                import_result=result,
                scan_errors=result.errors,
            )
    return _render_import(source=source)
