from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for

from common import data
from common.utils import get_tabs, get_side_tabs, get_table_def

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')


@notes_bp.route('/')
def list_notes_route():
    project = request.args.get("proj")
    tbl = get_table_def("notes")
    if not tbl:
        notes = []
    else:
        cols = ["id"] + tbl["col_list"] + ["rec_extract_date as updated"]
        condition = "1=1"
        params = []
        if project:
            condition = "project = ?"
            params = [project]
        rows = data.get_data(data.conn, tbl["name"], cols, condition, params)
        notes = [dict(row) for row in rows]
        for note in notes:
            note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    return render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
    )

@notes_bp.route('/view/<int:note_id>')
def view_note_route(note_id):
    tbl = get_table_def("notes")
    note = None
    if tbl:
        rows = data.get_data(
            data.conn,
            tbl["name"],
            ["id"] + tbl["col_list"] + ["rec_extract_date as updated"],
            "id = ?",
            [note_id],
        )
        if rows:
            note = dict(rows[0])
            note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    if not note:
        return redirect(url_for("notes.list_notes_route"))
    return render_template(
        "note_view.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title=note["title"],
        content_html="",
    )

@notes_bp.route('/add', methods=["GET", "POST"])
def add_note_route():
    tbl = get_table_def("notes")
    if request.method == "POST" and tbl:
        values = [
            request.form.get("title", "").strip(),
            request.form.get("content", "").strip(),
            request.form.get("project", "General").strip() or "General",
        ]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("notes.list_notes_route"))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Note",
        note=None,
    )

@notes_bp.route('/edit/<int:note_id>', methods=["GET", "POST"])
def edit_note_route(note_id):
    tbl = get_table_def("notes")
    note = None
    if tbl:
        rows = data.get_data(
            data.conn,
            tbl["name"],
            ["id"] + tbl["col_list"] + ["rec_extract_date as updated"],
            "id = ?",
            [note_id],
        )
        if rows:
            note = dict(rows[0])
            note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    if request.method == "POST" and tbl:
        values = [
            request.form.get("title", "").strip(),
            request.form.get("content", "").strip(),
            request.form.get("project", "General").strip() or "General",
        ]
        data.update_record(data.conn, tbl["name"], note_id, tbl["col_list"], values)
        return redirect(url_for("notes.view_note_route", note_id=note_id))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title=f"Edit: {note['title']}" if note else "Edit Note",
    )

@notes_bp.route('/delete/<int:note_id>')
def delete_note_route(note_id):
    tbl = get_table_def("notes")
    if tbl:
        data.delete_record(data.conn, tbl["name"], note_id)
    return redirect(url_for("notes.list_notes_route"))


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None
