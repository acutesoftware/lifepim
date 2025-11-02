
from common import data

from flask import Blueprint, render_template, request, redirect, url_for
from common.utils import get_tabs, get_side_tabs


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
    task_list = data.get_table_list("tasks") # (project)
    return render_template(
        "tasks_list.html",
        active_tab="tasks",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Tasks ({project or 'All'})",
        content_html="this is a task list",
        dta = task_list
    )


def get_tasks(project=None):
    if project:
        return data.query_table('tasks', f"project='{project}'")
    else:
        return data.get_table_list('tasks')