from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common.utils import build_form_fields, get_side_tabs, get_table_def, get_tabs


how_bp = Blueprint(
    "how",
    __name__,
    url_prefix="/how",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("how")


def _load_item(item_id):
    tbl = _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if rows:
        return dict(rows[0])
    return None


@how_bp.route("/")
def list_how_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "How"
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
        "how_list.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=content_title,
        content_html="",
        items=items,
        col_list=col_list,
        project=project,
    )


@how_bp.route("/view/<int:item_id>")
def view_how_route(item_id):
    project = request.args.get("proj")
    item = _load_item(item_id)
    if not item:
        return redirect(url_for("how.list_how_route", proj=project))
    return render_template(
        "how_view.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("title", "How"),
        content_html="",
        item=item,
        col_list=_get_tbl()["col_list"],
        project=project,
    )


@how_bp.route("/add", methods=["GET", "POST"])
def add_how_route():
    project = request.args.get("proj") or "General"
    tbl = _get_tbl()
    if request.method == "POST" and tbl:
        values = []
        for col in tbl["col_list"]:
            if col == "project":
                values.append(request.form.get(col, "").strip() or project)
            else:
                values.append(request.form.get(col, "").strip())
        db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("how.list_how_route", proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "how_edit.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add How",
        item=None,
        fields=fields,
        project=project,
    )


@how_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_how_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = _load_item(item_id)
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("how.view_how_route", item_id=item_id, proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "how_edit.html",
        active_tab="how",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit How",
        item=item,
        fields=fields,
        project=project,
    )


@how_bp.route("/delete/<int:item_id>")
def delete_how_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("how.list_how_route", proj=project))
