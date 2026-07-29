from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common.utils import (
    build_form_fields,
    get_side_tabs,
    get_table_def,
    get_tabs,
    paginate_items,
    build_pagination,
    request_area_param,
)
from common import config as cfg


goals_bp = Blueprint(
    "goals",
    __name__,
    url_prefix="/goals",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("goals")


def _load_item(item_id):
    tbl = _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if rows:
        return dict(rows[0])
    return None


@goals_bp.route("/")
def list_goals_route():
    area = request_area_param() or None
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "Goals"
    if tbl:
        col_list = tbl["col_list"]
        cols = ["id"] + col_list
        condition = "1=1"
        params = []
        if area and "area" in col_list:
            condition = "lower(area) = lower(?)"
            params = [area]
        rows = db.get_data(db.conn, tbl["name"], cols, condition, params)
        items = [dict(row) for row in rows]
        content_title = f"{tbl['display_name']} ({area or 'All'})"
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(items, page, cfg.RECS_PER_PAGE)
    items = page_data["items"]
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "goals.list_goals_route",
        {"area": area},
        page,
        total_pages,
    )
    return render_template(
        "goals_list.html",
        active_tab="goals",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=content_title,
        content_html="",
        items=items,
        col_list=col_list,
        area=area,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@goals_bp.route("/view/<int:item_id>")
def view_goal_route(item_id):
    area = request_area_param() or None
    item = _load_item(item_id)
    if not item:
        return redirect(url_for("goals.list_goals_route", area=area))
    return render_template(
        "goals_view.html",
        active_tab="goals",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("title", "Goal"),
        content_html="",
        item=item,
        col_list=_get_tbl()["col_list"],
        area=area,
    )


@goals_bp.route("/add", methods=["GET", "POST"])
def add_goal_route():
    area = request_area_param("General") or "General"
    tbl = _get_tbl()
    if request.method == "POST" and tbl:
        values = []
        for col in tbl["col_list"]:
            if col == "area":
                values.append(request_area_param(area, include_form=True) or area)
            else:
                values.append(request.form.get(col, "").strip())
        db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("goals.list_goals_route", area=area))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "goals_edit.html",
        active_tab="goals",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Goal",
        item=None,
        fields=fields,
        area=area,
    )


@goals_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_goal_route(item_id):
    area = request_area_param() or None
    tbl = _get_tbl()
    item = _load_item(item_id)
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("goals.view_goal_route", item_id=item_id, area=area))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "goals_edit.html",
        active_tab="goals",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Goal",
        item=item,
        fields=fields,
        area=area,
    )


@goals_bp.route("/delete/<int:item_id>")
def delete_goal_route(item_id):
    area = request_area_param() or None
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("goals.list_goals_route", area=area))
