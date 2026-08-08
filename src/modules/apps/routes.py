from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from common.utils import build_pagination, get_side_tabs, get_tabs, paginate_total, request_area_param
from common import config as cfg
from modules.apps import schema as apps_model


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
    names = form.getlist("action_name")
    types = form.getlist("action_type")
    commands = form.getlist("action_command")
    workdirs = form.getlist("action_working_directory")
    args = form.getlist("action_arguments")
    for idx, name in enumerate(names):
        rows.append(
            {
                "action_name": name,
                "action_type": types[idx] if idx < len(types) else "",
                "command": commands[idx] if idx < len(commands) else "",
                "working_directory": workdirs[idx] if idx < len(workdirs) else "",
                "arguments": args[idx] if idx < len(args) else "",
                "sort_order": idx * 10,
                "is_default": str(idx) == str(default_idx),
            }
        )
    return rows


def _render_apps_index(area, item=None, launch_error="", message=""):
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
    )


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
        apps_model.launch_action(item_id)
    except Exception as exc:
        item = apps_model.app_get(item_id)
        return _render_apps_index(area, item=item, launch_error=str(exc))
    return redirect(url_for("apps.view_app_route", item_id=item_id, **_args_with()))


@apps_bp.route("/action/<int:action_id>/launch/<int:item_id>")
def launch_app_action_route(item_id, action_id):
    area = _area()
    try:
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
    for _ in range(3):
        actions.append({})
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
    )


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
    area = _area()
    apps_model.delete_app(item_id)
    return redirect(url_for("apps.list_apps_table_route", area=area))


@apps_bp.route("/import", methods=["GET", "POST"])
def import_apps_route():
    return add_app_route()
