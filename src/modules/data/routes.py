import os
import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common.utils import build_form_fields, get_side_tabs, get_table_def, get_tabs, paginate_items, build_pagination
from common import config as cfg


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


def _is_sqlite(path_value):
    if not path_value or not os.path.exists(path_value):
        return False
    try:
        conn = sqlite3.connect(path_value)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


def _list_sqlite_tables(path_value):
    conn = sqlite3.connect(path_value)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    conn.close()
    return [row[0] for row in rows]


def _fetch_table_preview(path_value, table_name):
    conn = sqlite3.connect(path_value)
    safe_name = table_name.replace('"', '""')
    cols = conn.execute(f'PRAGMA table_info("{safe_name}")').fetchall()
    col_names = [col[1] for col in cols]
    rows = conn.execute(f'SELECT * FROM "{safe_name}" LIMIT 10').fetchall()
    conn.close()
    return col_names, rows


@data_bp.route("/")
def list_data_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "Data"
    sort_col = ""
    sort_dir = "asc"
    if tbl:
        col_list = tbl["col_list"]
        default_sort = "name" if "name" in col_list else (col_list[0] if col_list else "")
        sort_col = request.args.get("sort") or default_sort
        sort_dir = "desc" if (request.args.get("dir") or "").lower() == "desc" else "asc"
        if sort_col not in col_list:
            sort_col = default_sort
        cols = ["id"] + col_list
        condition = "1=1"
        params = []
        if project and "project" in col_list:
            condition = "lower(project) = lower(?)"
            params = [project]
        rows = db.get_data(db.conn, tbl["name"], cols, condition, params)
        items = [dict(row) for row in rows]
        if sort_col:
            reverse = sort_dir == "desc"
            def _sort_key(item):
                value = item.get(sort_col)
                if value is None:
                    return (1, "")
                if isinstance(value, (int, float)):
                    return (0, value)
                return (0, str(value).lower())
            items = sorted(items, key=_sort_key, reverse=reverse)
        content_title = f"{tbl['display_name']} ({project or 'All'})"
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(items, page, cfg.RECS_PER_PAGE)
    items = page_data["items"]
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "data.list_data_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
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
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )


@data_bp.route("/view/<int:item_id>")
def view_data_route(item_id):
    project = request.args.get("proj")
    table_name = request.args.get("table")
    item = _load_item(item_id)
    if not item:
        return redirect(url_for("data.list_data_route", proj=project))
    db_tables = []
    db_preview_cols = []
    db_preview_rows = []
    is_sqlite = _is_sqlite(item.get("tbl_name"))
    if is_sqlite:
        db_tables = _list_sqlite_tables(item.get("tbl_name"))
        if table_name and table_name in db_tables:
            db_preview_cols, db_preview_rows = _fetch_table_preview(item.get("tbl_name"), table_name)
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
        db_tables=db_tables,
        db_preview_cols=db_preview_cols,
        db_preview_rows=db_preview_rows,
        selected_table=table_name,
        is_sqlite=is_sqlite,
    )


@data_bp.route("/add", methods=["GET", "POST"])
def add_data_route():
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


@data_bp.route("/import-db", methods=["GET", "POST"])
def import_data_db_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    if request.method == "POST" and tbl:
        raw_paths = request.form.get("db_paths", "").strip()
        if not raw_paths:
            error = "No file paths provided."
        else:
            count = 0
            for line in raw_paths.splitlines():
                path_value = line.strip()
                if not path_value or not path_value.lower().endswith(".db"):
                    continue
                short_name = os.path.splitext(os.path.basename(path_value))[0]
                values = [
                    short_name,
                    "SQLite database",
                    path_value,
                    "",
                    project,
                ]
                record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    count += 1
            imported = count
    return render_template(
        "data_import_db.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import SQLite Databases",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )


@data_bp.route("/import-db-folder", methods=["POST"])
def import_data_db_folder_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = _get_tbl()
    imported = None
    error = ""
    folder_path = request.form.get("db_folder", "").strip()
    if not folder_path:
        error = "No folder provided."
    elif not os.path.isdir(folder_path):
        error = "Folder not found."
    elif not tbl:
        error = "Data table not found."
    else:
        count = 0
        for root, _, files in os.walk(folder_path):
            for name in files:
                if not name.lower().endswith(".db"):
                    continue
                full_path = os.path.join(root, name)
                if not os.path.isfile(full_path):
                    continue
                short_name = os.path.splitext(os.path.basename(full_path))[0]
                values = [
                    short_name,
                    "SQLite database",
                    full_path,
                    "",
                    project,
                ]
                record_id = db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    count += 1
        imported = count
    return render_template(
        "data_import_db.html",
        active_tab="data",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import SQLite Databases",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )
