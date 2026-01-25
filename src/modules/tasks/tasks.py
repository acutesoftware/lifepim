
from flask import Blueprint, render_template, request, redirect, url_for, make_response

from common import data
from common import projects as projects_mod
from utils import importer
from common.utils import get_tabs, get_side_tabs, get_table_def, paginate_items, build_pagination
from common import config as cfg


tasks_bp = Blueprint('tasks', __name__, url_prefix="/tasks",
                     template_folder='templates', static_folder='static')


"""
@tasks_bp.route('/')
def list_tasks():
    items = data.get_table_list('tasks')
    print('hello tasks!')
    return render_template('tasks_list.html', column_names=['Name', 'Detail'], col_values=items)
"""


@tasks_bp.route('/')
def list_tasks_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or request.cookies.get("tasks_sort_col") or "title"
    sort_dir = request.args.get("dir") or request.cookies.get("tasks_sort_dir") or "asc"
    tbl = get_table_def("tasks")
    if not tbl:
        task_list = []
        col_list = []
    else:
        cols = ["id"] + tbl["col_list"]
        col_list = tbl["col_list"]
        condition = "1=1"
        params = []
        if project:
            condition = "lower(project) = lower(?)"
            params = [project]
        rows = data.get_data(data.conn, tbl["name"], cols, condition, params)
        task_list = [dict(row) for row in rows]
    task_list = _sort_tasks(task_list, sort_col, sort_dir)
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(task_list, page, cfg.RECS_PER_PAGE)
    task_list = page_data["items"]
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "tasks.list_tasks_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "tasks_list.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Tasks ({project or 'All'})",
        content_html="",
        tasks=task_list,
        project=project,
        col_list=col_list,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )
    )
    resp.set_cookie("tasks_sort_col", sort_col)
    resp.set_cookie("tasks_sort_dir", sort_dir)
    return resp


@tasks_bp.route('/add', methods=["GET", "POST"])
def add_task_route():
    tbl = get_table_def("tasks")
    project = (request.args.get("proj") or "").strip()
    error = ""
    if project:
        try:
            if not projects_mod.project_default_folder_get(project):
                error = "No default folder set for this project. Set a default folder before creating tasks."
        except ValueError as exc:
            error = str(exc)
    if request.method == "POST" and tbl:
        if error:
            return render_template(
                "tasks_edit.html",
                active_tab="tasks",
                tabs=get_tabs(),
                side_tabs=get_side_tabs(),
                content_title="Add Task",
                task=None,
                project=project,
                error=error,
            )
        values = [
            request.form.get("title", "").strip(),
            request.form.get("content", "").strip(),
            request.form.get("project", "").strip() or project,
            request.form.get("start_date", "").strip(),
            request.form.get("due_date", "").strip(),
        ]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("tasks.list_tasks_route", proj=project))
    return render_template(
        "tasks_edit.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Task",
        task=None,
        project=project,
        error=error,
    )


@tasks_bp.route('/edit/<int:task_id>', methods=["GET", "POST"])
def edit_task_route(task_id):
    tbl = get_table_def("tasks")
    task = None
    if tbl:
        rows = data.get_data(data.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [task_id])
        if rows:
            task = dict(rows[0])
    if request.method == "POST" and tbl:
        values = [
            request.form.get("title", "").strip(),
            request.form.get("content", "").strip(),
            request.form.get("project", "General").strip() or "General",
            request.form.get("start_date", "").strip(),
            request.form.get("due_date", "").strip(),
        ]
        data.update_record(data.conn, tbl["name"], task_id, tbl["col_list"], values)
        return redirect(url_for("tasks.list_tasks_route"))
    return render_template(
        "tasks_edit.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Task",
        task=task,
    )


@tasks_bp.route('/delete/<int:task_id>')
def delete_task_route(task_id):
    tbl = get_table_def("tasks")
    if tbl:
        data.delete_record(data.conn, tbl["name"], task_id)
    return redirect(url_for("tasks.list_tasks_route"))


def _sort_tasks(tasks, sort_col, sort_dir):
    if not sort_col:
        return tasks
    reverse = sort_dir == "desc"
    return sorted(tasks, key=lambda t: (t.get(sort_col) or ""), reverse=reverse)


@tasks_bp.route('/import', methods=["GET", "POST"])
def import_tasks_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = get_table_def("tasks")
    csv_path = ""
    headers = []
    mappings = {}
    imported = None
    error = ""
    if request.method == "POST":
        csv_path = request.form.get("csv_path", "").strip()
        upload = request.files.get("csv_file")
        if upload and upload.filename:
            csv_path = importer.save_upload(upload)
        action = request.form.get("action", "load")
        headers = importer.read_csv_headers(csv_path)
        if action == "import" and tbl:
            mappings = {col: request.form.get(f"map_{col}", "") for col in tbl["col_list"]}
            map_list = []
            for col in tbl["col_list"]:
                choice = mappings.get(col, "")
                if choice == "{curr_project_selected}":
                    choice = project
                map_list.append(choice)
            try:
                importer.set_token("curr_project_selected", project)
                imported = importer.import_to_table(tbl["name"], csv_path, map_list)
            except Exception as exc:
                error = str(exc)
        else:
            mappings = {col: "" for col in (tbl["col_list"] if tbl else [])}
    return render_template(
        "tasks_import.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Tasks",
        content_html="",
        project=project,
        table_def=tbl,
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
    )
