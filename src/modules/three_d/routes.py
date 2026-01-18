import os
from datetime import datetime

from flask import Blueprint, render_template, request, url_for
from flask import redirect

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination
from common import config as cfg
from common import config as cfg


three_d_bp = Blueprint(
    "three_d",
    __name__,
    url_prefix="/3d",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("3d")


def _fetch_items(project=None, sort_col=None, sort_dir=None, limit=None, offset=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {
        "file_name": "t.file_name",
        "path": "t.path",
        "size": "t.size",
        "date_modified": "t.date_modified",
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


@three_d_bp.route("/")
def list_3d_route():
    return list_3d_table_route()


@three_d_bp.route("/table")
def list_3d_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    sort_col = request.args.get("sort") or "file_name"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_items(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "three_d.list_3d_table_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    tbl = _get_tbl()
    col_list = tbl["col_list"] if tbl else []
    return render_template(
        "three_d_list_table.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"3D ({project or 'All'})",
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


@three_d_bp.route("/list")
def list_3d_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_items(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "three_d.list_3d_list_route",
        {"proj": project},
        page,
        total_pages,
    )
    return render_template(
        "three_d_list_list.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"3D ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@three_d_bp.route("/cards")
def list_3d_cards_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = db.count_mapped_rows(db.conn, _get_tbl()["name"], tab=project)
    offset = (page - 1) * per_page
    items = _fetch_items(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "three_d.list_3d_cards_route",
        {"proj": project},
        page,
        total_pages,
    )
    card_values = [[i.get("file_name"), i.get("path"), url_for("three_d.view_3d_route", item_id=i.get("id"))] for i in items]
    return render_template(
        "three_d_list_cards.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"3D ({project or 'All'})",
        content_html="",
        items=items,
        card_values=card_values,
        project=project,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@three_d_bp.route("/view/<int:item_id>")
def view_3d_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return list_3d_table_route()
    return render_template(
        "three_d_view.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("file_name", "3D"),
        content_html="",
        item=item,
        project=project,
    )


@three_d_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_3d_route(item_id):
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
        return redirect(url_for("three_d.view_3d_route", item_id=item_id, proj=project))
    return render_template(
        "three_d_edit.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit 3D",
        content_html="",
        item=item,
        project=project,
        col_list=tbl["col_list"] if tbl else [],
    )


@three_d_bp.route("/delete/<int:item_id>")
def delete_3d_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("three_d.list_3d_table_route", proj=project))


@three_d_bp.route("/import", methods=["GET", "POST"])
def import_3d_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    if request.method == "POST" and tbl:
        folder_path = request.form.get("blend_folder", "").strip()
        if not folder_path:
            error = "No folder provided."
        elif not os.path.isdir(folder_path):
            error = "Folder not found."
        else:
            count = 0
            for root, _, files in os.walk(folder_path):
                for name in files:
                    if not name.lower().endswith(".blend"):
                        continue
                    full_path = os.path.join(root, name)
                    if not os.path.isfile(full_path):
                        continue
                    size = str(os.path.getsize(full_path))
                    mtime = os.path.getmtime(full_path)
                    date_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    values = [
                        name,
                        root,
                        size,
                        date_modified,
                        project,
                    ]
                    record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                    if record_id:
                        count += 1
            imported = count
    return render_template(
        "three_d_import.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import .blend Folder",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )
