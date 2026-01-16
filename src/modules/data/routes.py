from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common.utils import build_form_fields, get_side_tabs, get_table_def, get_tabs


data_bp = Blueprint(
    "data",
    __name__,
    url_prefix="/data",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("data")


def _load_item(item_id):
    tbl = _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if rows:
        return dict(rows[0])
    return None


@data_bp.route("/")
def list_data_route():
    project = request.args.get("proj")
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "Data"
    if tbl:
        col_list = tbl["col_list"]
        cols = ["id"] + col_list
        condition = "1=1"
        params = []
        if project and "project" in col_list:
            condition = "project = ?"
            params = [project]
        rows = db.get_data(db.conn, tbl["name"], cols, condition, params)
        items = [dict(row) for row in rows]
        content_title = f"{tbl['display_name']} ({project or 'All'})"
    return render_template(
        "data_list.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=content_title,
        content_html="",
        items=items,
        col_list=col_list,
        project=project,
    )


@data_bp.route("/view/<int:item_id>")
def view_data_route(item_id):
    project = request.args.get("proj")
    item = _load_item(item_id)
    if not item:
        return redirect(url_for("data.list_data_route", proj=project))
    return render_template(
        "data_view.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("name", "Data"),
        content_html="",
        item=item,
        col_list=_get_tbl()["col_list"],
        project=project,
    )


@data_bp.route("/add", methods=["GET", "POST"])
def add_data_route():
    project = request.args.get("proj")
    tbl = _get_tbl()
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("data.list_data_route", proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "data_edit.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Data",
        item=None,
        fields=fields,
        project=project,
    )


@data_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_data_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = _load_item(item_id)
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("data.view_data_route", item_id=item_id, proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "data_edit.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Data",
        item=item,
        fields=fields,
        project=project,
    )


@data_bp.route("/delete/<int:item_id>")
def delete_data_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("data.list_data_route", proj=project))
