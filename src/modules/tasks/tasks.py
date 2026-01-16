
from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common.utils import get_tabs, get_side_tabs, get_table_def


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
    tbl = get_table_def("tasks")
    if not tbl:
        task_list = []
    else:
        cols = ["id"] + tbl["col_list"]
        condition = "1=1"
        params = []
        if project:
            condition = "project = ?"
            params = [project]
        rows = data.get_data(data.conn, tbl["name"], cols, condition, params)
        task_list = [dict(row) for row in rows]
    return render_template(
        "tasks_list.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Tasks ({project or 'All'})",
        content_html="",
        tasks=task_list,
        project=project,
    )


@tasks_bp.route('/add', methods=["GET", "POST"])
def add_task_route():
    tbl = get_table_def("tasks")
    project = request.args.get("proj") or "General"
    if request.method == "POST" and tbl:
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
