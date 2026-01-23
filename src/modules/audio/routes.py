import mimetypes
import os

from flask import Blueprint, render_template, request, url_for, send_file, abort, redirect

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination
from common import config as cfg


audio_bp = Blueprint(
    "audio",
    __name__,
    url_prefix="/audio",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("audio")


def _fetch_audio(project=None, sort_col=None, sort_dir=None, limit=None, offset=None):
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
        "artist": "t.artist",
        "album": "t.album",
        "song": "t.song",
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
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_audio(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "audio.list_audio_table_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
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
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@audio_bp.route("/list")
def list_audio_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_audio(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "audio.list_audio_list_route",
        {"proj": project},
        page,
        total_pages,
    )
    return render_template(
        "audio_list_list.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Audio ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@audio_bp.route("/player")
def audio_player_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    limit = request.args.get("limit", type=int) or 200
    start_id = request.args.get("id", type=int)
    items = _fetch_audio(project, sort_col, sort_dir, limit=limit, offset=0)
    tracks = []
    for item in items:
        audio_url = url_for("audio.audio_file_route", item_id=item.get("id"))
        tracks.append(
            {
                "id": item.get("id"),
                "title": item.get("song") or item.get("file_name") or "",
                "artist": item.get("artist") or "",
                "album": item.get("album") or "",
                "path": item.get("path") or "",
                "url": audio_url,
            }
        )
    return render_template(
        "audio_player.html",
        tracks=tracks,
        project=project,
        start_id=start_id,
        sort_col=sort_col,
        sort_dir=sort_dir,
        limit=limit,
        show_freq_bar=(getattr(cfg, "AUDIO_SHOW_FREQ_BAR", "Y") or "Y").upper() == "Y",
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


@audio_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_audio_route(item_id):
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
        return redirect(url_for("audio.view_audio_route", item_id=item_id, proj=project))
    return render_template(
        "audio_edit.html",
        active_tab="audio",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Audio",
        content_html="",
        item=item,
        project=project,
        col_list=tbl["col_list"] if tbl else [],
    )


@audio_bp.route("/delete/<int:item_id>")
def delete_audio_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("audio.list_audio_table_route", proj=project))


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
