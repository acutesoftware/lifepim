from flask import Blueprint, render_template
from common import data

tasks_bp = Blueprint('tasks_bp', __name__, template_folder='templates')

@tasks_bp.route('/')
def list_tasks():
    items = data.get_table_list('tasks')
    return render_template('tasks_list.html', column_names=['Name', 'Detail'], col_values=items)
