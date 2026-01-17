import os
from datetime import datetime

from flask import Blueprint, render_template, request, url_for
from flask import redirect

from common import data as db
from common.utils import get_side_tabs, get_table_def, get_tabs


three_d_bp = Blueprint(
    "three_d",
    __name__,
    url_prefix="/3d",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("3d")


def _fetch_items(project=None):
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
    items = _fetch_items(project)
    items = _sort_items(items, sort_col, sort_dir)
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
    )


@three_d_bp.route("/list")
def list_3d_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    items = _fetch_items(project)
    return render_template(
        "three_d_list_list.html",
        active_tab="3d",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"3D ({project or 'All'})",
        content_html="",
        items=items,
        project=project,
    )


@three_d_bp.route("/cards")
def list_3d_cards_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    items = _fetch_items(project)
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
            for name in os.listdir(folder_path):
                if not name.lower().endswith(".blend"):
                    continue
                full_path = os.path.join(folder_path, name)
                if not os.path.isfile(full_path):
                    continue
                size = str(os.path.getsize(full_path))
                mtime = os.path.getmtime(full_path)
                date_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                values = [
                    name,
                    folder_path,
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
