import mimetypes
import os

from flask import Blueprint, render_template, request, url_for, send_file, abort, redirect

from common import data as db
from common import config as cfg
from common.utils import get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination


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


def _fetch_media(project=None, sort_col=None, sort_dir=None, limit=None, offset=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {
        "file_name": "t.file_name",
        "path": "t.path",
        "file_type": "t.file_type",
        "size": "t.size",
        "date_modified": "t.date_modified",
        "width": "t.width",
        "length": "t.length",
        "project": "t.project",
    }
    sort_key = order_map.get(sort_col or "file_name", "t.file_name")
    sort_dir = sort_dir or "asc"
    order_by = f"{sort_key} {sort_dir}"
    rows = db.get_mapped_rows(
        db.conn,
        tbl["name"],
        cols,
        tab=project,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )
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
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_media(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "media.list_media_table_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
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
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@media_bp.route("/list")
def list_media_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_media(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "media.list_media_list_route",
        {"proj": project},
        page,
        total_pages,
    )
    return render_template(
        "media_list_list.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Media ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@media_bp.route("/grid")
def list_media_grid_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_media(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "media.list_media_grid_route",
        {"proj": project},
        page,
        total_pages,
    )
    page_items = []
    for item in items:
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
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
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
            for root, _, files in os.walk(folder_path):
                for name in files:
                    full_path = os.path.join(root, name)
                    if not os.path.isfile(full_path):
                        continue
                    ext = os.path.splitext(name)[1].lower()
                    file_type = ext.lstrip(".")
                    values = [
                        name,
                        root,
                        "",
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


@media_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_media_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("media.view_media_route", item_id=item_id, proj=project))
    return render_template(
        "media_edit.html",
        active_tab="media",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Media",
        content_html="",
        item=item,
        project=project,
        col_list=tbl["col_list"] if tbl else [],
    )


@media_bp.route("/delete/<int:item_id>")
def delete_media_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("media.list_media_table_route", proj=project))


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
