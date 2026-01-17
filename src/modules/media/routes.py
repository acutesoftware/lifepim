import mimetypes
import os

from flask import Blueprint, render_template, request, url_for, send_file, abort

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs


media_bp = Blueprint(
    "media",
    __name__,
    url_prefix="/media",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("media")


def _media_condition():
    tbl = _get_tbl()
    if not tbl or "file_type" not in tbl["col_list"]:
        return "1=1", []
    return "(lower(file_type) like '%image%' OR lower(file_type) like '%video%')", []


def _fetch_media(project=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    condition, params = '1=1', [] # _media_condition()
    if project:
        condition = f"({condition}) AND project = ?"
        params = params + [project]
    rows = db.get_data(db.conn, tbl["name"], cols, condition, params)
    return [dict(row) for row in rows]


def _sort_items(items, sort_col, sort_dir):
    reverse = sort_dir == "desc"
    return sorted(items, key=lambda i: (i.get(sort_col) or ""), reverse=reverse)


def _build_media_path(item):
    file_name = item.get("file_name") or ""
    path = item.get("path") or ""
    full_path = path
    if file_name:
        full_path = os.path.join(path, file_name)
    return full_path


@media_bp.route("/")
def list_media_route():
    return list_media_table_route()


@media_bp.route("/table")
def list_media_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    items = _fetch_media(project)
    items = _sort_items(items, sort_col, sort_dir)
    tbl = _get_tbl()
    col_list = tbl["col_list"] if tbl else []
    return render_template(
        "media_list_table.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Media ({project or 'All'})",
        content_html="",
        items=items,
        col_list=col_list,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
    )


@media_bp.route("/list")
def list_media_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    items = _fetch_media(project)
    return render_template(
        "media_list_list.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Media ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
    )


@media_bp.route("/grid")
def list_media_grid_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    page_size = 10
    items = _fetch_media(project)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = []
    for item in items[start:end]:
        media_url = url_for("media.media_file_route", item_id=item.get("id"))
        ext = os.path.splitext(_build_media_path(item))[1].lower()
        is_video = ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        item["media_url"] = media_url
        item["is_video"] = is_video
        page_items.append(item)
    return render_template(
        "media_list_grid.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Media ({project or 'All'})",
        content_html="",
        items=page_items,
        project=project,
        page=page,
        has_next=end < len(items),
    )


@media_bp.route("/import", methods=["GET", "POST"])
def import_media_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    if request.method == "POST" and tbl:
        folder_path = request.form.get("media_folder", "").strip()
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
                    project,
                ]
                record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    count += 1
            imported = count
    return render_template(
        "media_import.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Media Folder",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )


@media_bp.route("/view/<int:item_id>")
def view_media_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return list_media_table_route()
    full_path = _build_media_path(item)
    ext = os.path.splitext(full_path)[1].lower()
    media_url = url_for("media.media_file_route", item_id=item_id)
    is_video = ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    return render_template(
        "media_view.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("file_name", "Media"),
        content_html="",
        item=item,
        project=project,
        media_url=media_url,
        is_video=is_video,
        file_exists=os.path.exists(full_path),
    )


@media_bp.route("/file/<int:item_id>")
def media_file_route(item_id):
    tbl = _get_tbl()
    if not tbl:
        abort(404)
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if not rows:
        abort(404)
    item = dict(rows[0])
    full_path = _build_media_path(item)
    if not os.path.exists(full_path):
        abort(404)
    mime_type, _ = mimetypes.guess_type(full_path)
    return send_file(full_path, mimetype=mime_type or "application/octet-stream")
