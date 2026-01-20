from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common import config as cfg
from common.utils import build_form_fields, get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination


places_bp = Blueprint(
    "places",
    __name__,
    url_prefix="/places",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("places")


def _normalize_project(project):
    if project in ("any", "All", "all", "ALL", "spacer"):
        return None
    return project


def _build_condition(project, tbl):
    if project and "project" in (tbl["col_list"] if tbl else []):
        return "lower(project) = lower(?)", [project]
    return "1=1", []


def _fetch_places(project=None, sort_col=None, sort_dir=None, limit=None, offset=None):
    tbl = _get_tbl()
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {col: f"t.{col}" for col in tbl["col_list"]}
    sort_key = order_map.get(sort_col or "name", "t.name")
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    condition, params = _build_condition(project, tbl)
    sql = (
        f"SELECT {', '.join([f't.{col}' for col in cols])} "
        f"FROM {tbl['name']} t "
        f"WHERE {condition} "
        f"ORDER BY {sort_key} {sort_dir}"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    rows = db._get_conn().execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _count_places(project=None):
    tbl = _get_tbl()
    if not tbl:
        return 0
    condition, params = _build_condition(project, tbl)
    row = db._get_conn().execute(
        f"SELECT COUNT(1) as cnt FROM {tbl['name']} t WHERE {condition}",
        params,
    ).fetchone()
    return row["cnt"] if row else 0


def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_fields(col_list):
    fields = build_form_fields(col_list)
    for field in fields:
        if field["name"] == "desc":
            field["is_textarea"] = True
        if field["name"] in ("gps_lat", "gps_long"):
            field["input_type"] = "number"
            field["step"] = "any"
    return fields


@places_bp.route("/")
def list_places_route():
    return list_places_table_route()


@places_bp.route("/table")
def list_places_table_route():
    project = _normalize_project(request.args.get("proj"))
    sort_col = request.args.get("sort") or "name"
    sort_dir = request.args.get("dir") or "asc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = _count_places(project)
    offset = (page - 1) * per_page
    items = _fetch_places(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "places.list_places_table_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    tbl = _get_tbl()
    col_list = tbl["col_list"] if tbl else []
    return render_template(
        "places_list_table.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Places ({project or 'All'})",
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


@places_bp.route("/map")
def list_places_map_route():
    project = _normalize_project(request.args.get("proj"))
    items = _fetch_places(project, sort_col="name", sort_dir="asc")
    markers = []
    for item in items:
        lat = _parse_float(item.get("gps_lat"))
        lon = _parse_float(item.get("gps_long"))
        if lat is None or lon is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        markers.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "lat": lat,
                "lon": lon,
                "url": url_for("places.view_place_route", place_id=item.get("id"), proj=project),
            }
        )
    return render_template(
        "places_list_map.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Places Map ({project or 'All'})",
        content_html="",
        items=items,
        markers=markers,
        project=project,
    )


@places_bp.route("/view/<int:place_id>")
def view_place_route(place_id):
    project = _normalize_project(request.args.get("proj"))
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [place_id])
        if rows:
            item = dict(rows[0])
    if not item:
        return redirect(url_for("places.list_places_table_route", proj=project))
    return render_template(
        "places_view.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("name", "Place"),
        content_html="",
        item=item,
        col_list=tbl["col_list"] if tbl else [],
        project=project,
    )


@places_bp.route("/add", methods=["GET", "POST"])
def add_place_route():
    project = _normalize_project(request.args.get("proj")) or "General"
    tbl = _get_tbl()
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("places.list_places_table_route", proj=project))
    fields = _build_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "places_edit.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Place",
        item=None,
        fields=fields,
        project=project,
    )


@places_bp.route("/edit/<int:place_id>", methods=["GET", "POST"])
def edit_place_route(place_id):
    project = _normalize_project(request.args.get("proj"))
    tbl = _get_tbl()
    item = None
    if tbl:
        rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [place_id])
        if rows:
            item = dict(rows[0])
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], place_id, tbl["col_list"], values)
        return redirect(url_for("places.view_place_route", place_id=place_id, proj=project))
    fields = _build_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "places_edit.html",
        active_tab="places",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit Place",
        item=item,
        fields=fields,
        project=project,
    )


@places_bp.route("/delete/<int:place_id>")
def delete_place_route(place_id):
    project = _normalize_project(request.args.get("proj"))
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], place_id)
    return redirect(url_for("places.list_places_table_route", proj=project))
