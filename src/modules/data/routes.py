import os
import sqlite3
import json

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for

from common import config as cfg
from common import data as db
from common.utils import build_form_fields, build_pagination, get_side_tabs, get_table_def, get_tabs, paginate_items
from modules.data import catalogue


data_bp = Blueprint("data", __name__, url_prefix="/data", template_folder="templates", static_folder="static")
catalogue.ensure_schema()


def _ctx(title):
    return {
        "active_tab": "data",
        "tabs": get_tabs(),
        "side_tabs": get_side_tabs(),
        "content_title": title,
        "content_html": "",
    }


def _get_tbl():
    return get_table_def("data")


def _load_item(item_id):
    tbl = _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    return dict(rows[0]) if rows else None


def _is_sqlite(path_value):
    if not path_value or not os.path.exists(path_value):
        return False
    try:
        conn = catalogue.sqlite_readonly_connection(path_value)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


def _list_sqlite_tables(path_value):
    conn = catalogue.sqlite_readonly_connection(path_value)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    conn.close()
    return [row[0] for row in rows]


def _fetch_table_preview(path_value, table_name):
    conn = catalogue.sqlite_readonly_connection(path_value)
    safe_name = table_name.replace('"', '""')
    cols = conn.execute(f'PRAGMA table_info("{safe_name}")').fetchall()
    col_names = [col[1] for col in cols]
    rows = conn.execute(f'SELECT * FROM "{safe_name}" LIMIT 10').fetchall()
    conn.close()
    return col_names, rows


@data_bp.route("/")
def overview_route():
    return render_template(
        "data_overview.html",
        **_ctx("Data Workbench"),
        counts=catalogue.overview_counts(),
        recent=catalogue.recent_activity(),
        attention=catalogue.attention_items(),
    )


@data_bp.route("/sources")
def sources_route():
    return redirect(url_for("data.database_sources_route"))


@data_bp.route("/sources/databases")
def database_sources_route():
    return render_template(
        "data_sources.html",
        **_ctx("Database Sources"),
        section="databases",
        sources=catalogue.source_list("DATABASE"),
    )


@data_bp.route("/sources/files")
def file_sources_route():
    return render_template(
        "data_sources.html",
        **_ctx("File Sources"),
        section="files",
        sources=catalogue.source_list("FILE_SOURCE"),
    )


@data_bp.route("/sources/database/new", methods=["GET", "POST"])
def database_source_new_route():
    return _source_form(None, "DATABASE")


@data_bp.route("/sources/database/browse-sqlite")
def database_source_browse_sqlite_route():
    try:
        import tkinter as tk
        from tkinter import filedialog

        source_type = (request.args.get("type") or "SQLITE").upper()
        if source_type == "CSV":
            title = "Select CSV data file"
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        elif source_type == "EXCEL":
            title = "Select Excel workbook"
            filetypes = [("Excel workbooks", "*.xls *.xlsx *.xlsm"), ("All files", "*.*")]
        else:
            title = "Select SQLite database"
            filetypes = [("SQLite databases", "*.db *.sqlite *.sqlite3"), ("All files", "*.*")]
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title=title,
            filetypes=filetypes,
        )
        root.destroy()
        return jsonify({"path": path or ""})
    except Exception as exc:
        return jsonify({"path": "", "error": str(exc)}), 500


@data_bp.route("/sources/file/new", methods=["GET", "POST"])
def file_source_new_route():
    return _source_form(None, "FILE_SOURCE")


@data_bp.route("/sources/database/<int:source_id>/edit", methods=["GET", "POST"])
def database_source_edit_route(source_id):
    return _source_form(source_id, "DATABASE")


@data_bp.route("/sources/file/<int:source_id>/edit", methods=["GET", "POST"])
def file_source_edit_route(source_id):
    return _source_form(source_id, "FILE_SOURCE")


def _source_form(source_id, kind):
    source = catalogue.source_get(source_id) if source_id else None
    error = ""
    if request.method == "POST":
        form = _prepare_database_source_form(request.form) if kind == "DATABASE" else request.form
        source_type = (form.get("source_type") or "").upper()
        if kind == "DATABASE" and source_type in {"SQLITE", "CSV", "EXCEL"}:
            data_path = form.get("root_path") or form.get("database_name") or ""
            if not data_path or not os.path.isfile(data_path):
                error = f"Select a valid {source_type.replace('_', ' ')} file before saving."
                return render_template(
                    "data_source_form.html",
                    **_ctx("Add Database Source" if not source_id else "Edit Database Source"),
                    source=source,
                    kind=kind,
                    source_types=catalogue.DB_SOURCE_TYPES,
                    error=error,
                    submitted=form,
                )
        new_id = catalogue.save_source(source_id, form, kind)
        if kind == "DATABASE" and source_type in {"SQLITE", "CSV", "EXCEL"}:
            catalogue.scan_source(new_id)
        endpoint = "data.database_source_detail_route" if kind == "DATABASE" else "data.file_source_detail_route"
        return redirect(url_for(endpoint, source_id=new_id))
    title = ("Edit " if source_id else "Add ") + ("Database Source" if kind == "DATABASE" else "File Source")
    return render_template(
        "data_source_form.html",
        **_ctx(title),
        source=source,
        kind=kind,
        source_types=catalogue.DB_SOURCE_TYPES if kind == "DATABASE" else catalogue.FILE_SOURCE_TYPES,
        error=error,
        submitted={},
    )


def _prepare_database_source_form(form):
    values = form.to_dict(flat=True) if hasattr(form, "to_dict") else dict(form)
    source_type = (values.get("source_type") or "").strip().upper()
    connection_string = (values.get("db_connection_string") or "").strip()
    local_path = (values.get("local_database_path") or "").strip()

    if source_type in {"SQLITE", "DUCKDB", "CSV", "EXCEL"} and local_path:
        values["root_path"] = local_path
        if not values.get("database_name"):
            values["database_name"] = os.path.basename(local_path)
        if not values.get("source_name"):
            values["source_name"] = os.path.splitext(os.path.basename(local_path))[0]

    if source_type == "FABRIC_SQL" and connection_string:
        values["connection_options_json"] = json.dumps({"connection_string": connection_string})
        if not values.get("source_name"):
            values["source_name"] = _connection_string_value(connection_string, "Database") or "Fabric SQL endpoint"
        if not values.get("database_name"):
            values["database_name"] = _connection_string_value(connection_string, "Database")
        if not values.get("host_name"):
            values["host_name"] = _connection_string_value(connection_string, "Server")

    if source_type == "ODBC" and connection_string and not values.get("connection_options_json"):
        values["connection_options_json"] = json.dumps({"connection_string": connection_string})
    if source_type == "ODBC":
        values["host_name"] = values.get("odbc_host_name") or values.get("host_name") or ""
        values["database_name"] = values.get("odbc_database_name") or values.get("database_name") or ""
        if values.get("odbc_connection_string"):
            values["connection_options_json"] = json.dumps({"connection_string": values["odbc_connection_string"]})

    if not values.get("source_name"):
        values["source_name"] = values.get("database_name") or values.get("host_name") or source_type or "Database source"
    return values


def _connection_string_value(connection_string, key):
    key_lower = key.lower()
    for part in connection_string.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip().lower() == key_lower:
            return value.strip()
    return ""


@data_bp.route("/object/<int:object_id>/data")
def object_data_route(object_id):
    obj = catalogue.object_get(object_id)
    if not obj:
        return redirect(url_for("data.objects_route"))
    preview = {"columns": [], "rows": []}
    error = ""
    try:
        preview = catalogue.preview_object_rows(object_id, limit=200)
    except Exception as exc:
        error = str(exc)
    return render_template(
        "data_object_data.html",
        **_ctx(f"Data Preview: {obj.get('display_name') or obj['object_name']}"),
        obj=obj,
        preview=preview,
        error=error,
    )


@data_bp.route("/sources/database/<int:source_id>")
def database_source_detail_route(source_id):
    return _source_detail(source_id, "DATABASE")


@data_bp.route("/sources/file/<int:source_id>")
def file_source_detail_route(source_id):
    return _source_detail(source_id, "FILE_SOURCE")


def _source_detail(source_id, kind):
    source = catalogue.source_get(source_id)
    if not source:
        return redirect(url_for("data.database_sources_route" if kind == "DATABASE" else "data.file_sources_route"))
    objects = catalogue.object_list({"source_id": str(source_id)})
    recent_tasks = [task for task in catalogue.tasks(limit=50) if task.get("data_source_id") == source_id][:10]
    return render_template("data_source_detail.html", **_ctx(source["source_name"]), source=source, objects=objects, tasks=recent_tasks)


@data_bp.route("/sources/<int:source_id>/delete", methods=["POST"])
def source_delete_route(source_id):
    source = catalogue.source_get(source_id)
    catalogue.delete_source(source_id)
    if source and source["source_kind"] == "FILE_SOURCE":
        return redirect(url_for("data.file_sources_route"))
    return redirect(url_for("data.database_sources_route"))


@data_bp.route("/sources/<int:source_id>/test", methods=["POST"])
def source_test_route(source_id):
    task_id = catalogue.test_database_connection(source_id)
    return redirect(url_for("data.task_detail_route", task_id=task_id))


@data_bp.route("/sources/<int:source_id>/scan", methods=["POST"])
def source_scan_route(source_id):
    task_id = catalogue.scan_source(source_id)
    return redirect(url_for("data.task_detail_route", task_id=task_id))


@data_bp.route("/objects")
def objects_route():
    filters = {
        key: request.args.get(key, "")
        for key in [
            "q",
            "source_id",
            "object_type",
            "catalogue_level",
            "environment",
            "profile_status",
            "quality_status",
            "favourite",
            "hidden",
            "active",
        ]
    }
    return render_template(
        "data_objects.html",
        **_ctx("Data Objects"),
        objects=catalogue.object_list(filters),
        filters=filters,
        sources=catalogue.source_list(),
        object_types=catalogue.OBJECT_TYPES,
        catalogue_levels=catalogue.CATALOGUE_LEVELS,
        environments=catalogue.distinct_values("d_data_source", "environment"),
    )


@data_bp.route("/object/<int:object_id>", methods=["GET", "POST"])
def object_detail_route(object_id):
    if request.method == "POST":
        catalogue.save_object_metadata(object_id, request.form)
        return redirect(url_for("data.object_detail_route", object_id=object_id))
    obj = catalogue.object_get(object_id)
    if not obj:
        return redirect(url_for("data.objects_route"))
    related_sql = [
        item
        for item in catalogue.sql_list()
        if str(object_id) in [str(related_id) for related_id in catalogue.sql_get(item["saved_sql_id"]).get("related_object_ids", [])]
    ]
    return render_template(
        "data_object_detail.html",
        **_ctx(obj.get("display_name") or obj["object_name"]),
        obj=obj,
        columns=catalogue.object_columns(object_id),
        related_sql=related_sql,
        levels=catalogue.CATALOGUE_LEVELS,
    )


@data_bp.route("/object/<int:object_id>/level/<level>", methods=["POST"])
def object_level_route(object_id, level):
    catalogue.update_object_level(object_id, level.upper())
    return redirect(url_for("data.object_detail_route", object_id=object_id))


@data_bp.route("/object/<int:object_id>/toggle/<flag>", methods=["POST"])
def object_toggle_route(object_id, flag):
    allowed = {"favourite": "is_favourite", "hidden": "is_hidden"}
    obj = catalogue.object_get(object_id)
    if obj and flag in allowed:
        col = allowed[flag]
        catalogue.update_object_flags(object_id, **{col: 0 if obj.get(col) else 1})
    return redirect(url_for("data.object_detail_route", object_id=object_id))


@data_bp.route("/object/<int:object_id>/profile", methods=["POST"])
def object_profile_route(object_id):
    task_id = catalogue.create_task("Profile object", "PROFILE_OBJECT", object_id=object_id, params={"object_id": object_id})
    catalogue.start_task(task_id)
    catalogue.finish_task(task_id, "COMPLETED_WITH_WARNINGS", result_summary="Profile action placeholder created. Profiling is not implemented in Phase 1.")
    return redirect(url_for("data.task_detail_route", task_id=task_id))


@data_bp.route("/sql")
def sql_route():
    filters = {"q": request.args.get("q", ""), "source_id": request.args.get("source_id", ""), "favourite": request.args.get("favourite", "")}
    return render_template(
        "data_sql_list.html",
        **_ctx("Saved SQL"),
        sql_items=catalogue.sql_list(filters),
        filters=filters,
        sources=catalogue.source_list("DATABASE"),
    )


@data_bp.route("/sql/new", methods=["GET", "POST"])
def sql_new_route():
    return _sql_form(None)


@data_bp.route("/sql/<int:sql_id>/edit", methods=["GET", "POST"])
def sql_edit_route(sql_id):
    return _sql_form(sql_id)


def _sql_form(sql_id):
    item = catalogue.sql_get(sql_id) if sql_id else None
    if request.method == "POST":
        new_id = catalogue.save_sql(sql_id, request.form)
        return redirect(url_for("data.sql_detail_route", sql_id=new_id))
    return render_template(
        "data_sql_form.html",
        **_ctx("Edit Saved SQL" if sql_id else "Add Saved SQL"),
        item=item,
        sources=catalogue.source_list("DATABASE"),
        objects=catalogue.object_list({}),
    )


@data_bp.route("/sql/<int:sql_id>")
def sql_detail_route(sql_id):
    item = catalogue.sql_get(sql_id)
    if not item:
        return redirect(url_for("data.sql_route"))
    return render_template(
        "data_sql_detail.html",
        **_ctx(item["sql_name"]),
        item=item,
        related_objects=catalogue.sql_related_objects(sql_id),
    )


@data_bp.route("/sql/<int:sql_id>/delete", methods=["POST"])
def sql_delete_route(sql_id):
    catalogue.delete_sql(sql_id)
    return redirect(url_for("data.sql_route"))


@data_bp.route("/sql/<int:sql_id>/download")
def sql_download_route(sql_id):
    item = catalogue.sql_get(sql_id)
    if not item:
        return redirect(url_for("data.sql_route"))
    filename = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in item["sql_name"]).strip("_") or "query"
    return Response(
        item["sql_text"],
        mimetype="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}.sql"'},
    )


@data_bp.route("/sql/<int:sql_id>/run", methods=["POST"])
def sql_run_route(sql_id):
    task_id = catalogue.create_task("Run saved SQL", "RUN_SAVED_SQL", sql_id=sql_id, params={"saved_sql_id": sql_id})
    catalogue.start_task(task_id)
    catalogue.finish_task(task_id, "COMPLETED_WITH_WARNINGS", result_summary="Runner task placeholder created. SQL execution is not implemented in Phase 1.")
    return redirect(url_for("data.task_detail_route", task_id=task_id))


@data_bp.route("/tasks")
def tasks_route():
    return render_template("data_tasks.html", **_ctx("Data Tasks"), tasks=catalogue.tasks())


@data_bp.route("/task/<int:task_id>")
def task_detail_route(task_id):
    task = catalogue.task_get(task_id)
    if not task:
        return redirect(url_for("data.tasks_route"))
    return render_template("data_task_detail.html", **_ctx(task["task_name"]), task=task)


@data_bp.route("/legacy")
def list_data_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "Legacy Data"
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
            items = sorted(items, key=lambda item: str(item.get(sort_col) or "").lower(), reverse=sort_dir == "desc")
        content_title = f"Legacy {tbl['display_name']} ({project or 'All'})"
    page = request.args.get("page", type=int) or 1
    page_data = paginate_items(items, page, cfg.RECS_PER_PAGE)
    pagination = build_pagination(
        url_for,
        "data.list_data_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page_data["page"],
        page_data["total_pages"],
    )
    return render_template(
        "data_list.html",
        **_ctx(content_title),
        items=page_data["items"],
        col_list=col_list,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page_data["page"],
        total_pages=page_data["total_pages"],
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
        **_ctx(item.get("name", "Legacy Data")),
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
        values = [request.form.get(col, "").strip() or (project if col == "project" else "") for col in tbl["col_list"]]
        db.add_record(db.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("data.list_data_route", proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template("data_edit.html", **_ctx("Add Legacy Data"), item=None, fields=fields, project=project)


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
    return render_template("data_edit.html", **_ctx("Edit Legacy Data"), item=item, fields=fields, project=project)


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
    imported = None
    error = ""
    if request.method == "POST":
        raw_paths = request.form.get("db_paths", "").strip()
        if not raw_paths:
            error = "No file paths provided."
        else:
            count = 0
            for line in raw_paths.splitlines():
                path_value = line.strip()
                if not path_value:
                    continue
                form_data = {
                    "source_name": os.path.splitext(os.path.basename(path_value))[0],
                    "source_type": "SQLITE",
                    "root_path": path_value,
                    "database_name": os.path.basename(path_value),
                    "environment": project,
                    "scan_views": "on",
                    "scan_columns": "on",
                    "is_active": "on",
                }
                catalogue.save_source(None, form_data, "DATABASE")
                count += 1
            imported = count
    return render_template("data_import_db.html", **_ctx("Import SQLite Databases"), project=project, imported=imported, error=error)


@data_bp.route("/import-db-folder", methods=["POST"])
def import_data_db_folder_route():
    folder_path = request.form.get("db_folder", "").strip()
    project = request.args.get("proj") or ""
    imported = 0
    error = ""
    if not folder_path:
        error = "No folder provided."
    elif not os.path.isdir(folder_path):
        error = "Folder not found."
    else:
        for root, _, files in os.walk(folder_path):
            for name in files:
                if name.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    path_value = os.path.join(root, name)
                    catalogue.save_source(
                        None,
                        {
                            "source_name": os.path.splitext(name)[0],
                            "source_type": "SQLITE",
                            "root_path": path_value,
                            "database_name": name,
                            "environment": project,
                            "scan_views": "on",
                            "scan_columns": "on",
                            "is_active": "on",
                        },
                        "DATABASE",
                    )
                    imported += 1
    return render_template("data_import_db.html", **_ctx("Import SQLite Databases"), project=project, imported=imported, error=error)
