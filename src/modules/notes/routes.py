from flask import Blueprint, render_template, request, redirect, url_for
from common import data
from common.utils import get_tabs, get_side_tabs

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')


@notes_bp.route('/')
def list_notes_route():
    project = request.args.get("proj")
    notes = data.get_notes(data.conn, project)
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
    note = data.get_note_by_id(data.conn, note_id)
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
    if request.method == "POST":
        data.add_note(
            data.conn,
            request.form["title"],
            request.form.get("content", ""),
            request.form.get("project", "General"),
        )
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
    note = data.get_note_by_id(data.conn, note_id)
    if request.method == "POST":
        data.update_note(
            data.conn,
            note_id,
            request.form["title"],
            request.form.get("content", ""),
            request.form.get("project", "General"),
        )
        return redirect(url_for("notes.view_note_route", note_id=note_id))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title=f"Edit: {note['title']}",
    )

@notes_bp.route('/delete/<int:note_id>')
def delete_note_route(note_id):
    data.delete_note(data.conn, note_id)
    return redirect(url_for("notes.list_notes_route"))
