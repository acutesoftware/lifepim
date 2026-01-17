import mimetypes
import os

from flask import Blueprint, render_template, request, url_for, send_file, abort

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs


audio_bp = Blueprint(
    "audio",
    __name__,
    url_prefix="/audio",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("audio")


def _fetch_audio(project=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    condition = "1=1"
    params = []
    if project:
        condition = "project = ?"
        params = [project]
    rows = db.get_data(db.conn, tbl["name"], cols, condition, params)
    return [dict(row) for row in rows]


def _sort_items(items, sort_col, sort_dir):
    reverse = sort_dir == "desc"
    return sorted(items, key=lambda i: (i.get(sort_col) or ""), reverse=reverse)


@audio_bp.route("/")
def list_audio_route():
    return list_audio_table_route()


@audio_bp.route("/table")
def list_audio_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    items = _fetch_audio(project)
    items = _sort_items(items, sort_col, sort_dir)
    tbl = _get_tbl()
    col_list = tbl["col_list"] if tbl else []
    return render_template(
        "audio_list_table.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Audio ({project or 'All'})",
        content_html="",
        items=items,
        col_list=col_list,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
    )


@audio_bp.route("/list")
def list_audio_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    items = _fetch_audio(project)
    return render_template(
        "audio_list_list.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Audio ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
    )


@audio_bp.route("/import", methods=["GET", "POST"])
def import_audio_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    if request.method == "POST" and tbl:
        folder_path = request.form.get("audio_folder", "").strip()
        if not folder_path:
            error = "No folder provided."
        elif not os.path.isdir(folder_path):
            error = "Folder not found."
        else:
            count = 0
            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                if not os.path.isfile(full_path):
                    continue
                ext = os.path.splitext(name)[1].lower()
                file_type = ext.lstrip(".")
                values = [
                    name,
                    folder_path,
                    file_type,
                    "",
                    "",
                    "",
                    "",
                    "",
                    project,
                ]
                record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    count += 1
            imported = count
    return render_template(
        "audio_import.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Audio Folder",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )


@audio_bp.route("/view/<int:item_id>")
def view_audio_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return list_audio_table_route()
    full_path = os.path.join(item.get("path") or "", item.get("file_name") or "")
    audio_url = url_for("audio.audio_file_route", item_id=item_id)
    return render_template(
        "audio_view.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("file_name", "Audio"),
        content_html="",
        item=item,
        project=project,
        audio_url=audio_url,
        file_exists=os.path.exists(full_path),
    )


@audio_bp.route("/file/<int:item_id>")
def audio_file_route(item_id):
    tbl = _get_tbl()
    if not tbl:
        abort(404)
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if not rows:
        abort(404)
    item = dict(rows[0])
    full_path = os.path.join(item.get("path") or "", item.get("file_name") or "")
    if not os.path.exists(full_path):
        abort(404)
    mime_type, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime_type or "application/octet-stream")
