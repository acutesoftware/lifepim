from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, make_response

from common import data
from utils import importer
from common.utils import get_tabs, get_side_tabs, get_table_def
from common import config as cfg

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')

def _fetch_notes(project):
    tbl = get_table_def("notes")
    if not tbl:
        return []
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
    return notes


@notes_bp.route('/')
def list_notes_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    view_pref = request.cookies.get("notes_view")
    if view_pref in ("list", "cards"):
        return redirect(url_for(f"notes.list_notes_{view_pref}_route", proj=project))
    sort_col = request.args.get("sort") or request.cookies.get("notes_sort_col") or "updated"
    sort_dir = request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc"
    notes = _sort_notes(_fetch_notes(project), sort_col, sort_dir)
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name="notes.list_notes_table_route",
    )
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/table')
def list_notes_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or request.cookies.get("notes_sort_col") or "updated"
    sort_dir = request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc"
    notes = _sort_notes(_fetch_notes(project), sort_col, sort_dir)
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name="notes.list_notes_table_route",
    )
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/list')
def list_notes_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    notes = _fetch_notes(project)
    resp = make_response(
        render_template(
        "notes_list_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
    )
    )
    resp.set_cookie("notes_view", "list")
    return resp


@notes_bp.route('/cards')
def list_notes_cards_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    notes = _fetch_notes(project)
    card_values = [
        [n.get("title"), n.get("content"), url_for("notes.view_note_route", note_id=n.get("id"))]
        for n in notes
    ]
    resp = make_response(
        render_template(
        "notes_list_cards.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        card_values=card_values,
        project=project,
        note_card_bg=cfg.NOTE_CARD_DEF_BG_COL,
    )
    )
    resp.set_cookie("notes_view", "cards")
    return resp

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
    project = request.args.get("proj") or "General"
    if request.method == "POST" and tbl:
        values = [
            request.form.get("title", "").strip(),
            request.form.get("content", "").strip(),
            request.form.get("project", "").strip() or project,
        ]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("notes.list_notes_route", proj=project))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Note",
        note=None,
        project=project,
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


@notes_bp.route('/import', methods=["GET", "POST"])
def import_notes_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = get_table_def("notes")
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
        "notes_import.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Notes",
        content_html="",
        project=project,
        table_def=tbl,
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
    )


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


def _sort_notes(notes, sort_col, sort_dir):
    key_map = {
        "title": lambda n: (n.get("title") or "").lower(),
        "project": lambda n: (n.get("project") or "").lower(),
        "updated": lambda n: n.get("updated") or datetime.min,
    }
    key_fn = key_map.get(sort_col, key_map["updated"])
    reverse = sort_dir == "desc"
    return sorted(notes, key=key_fn, reverse=reverse)
