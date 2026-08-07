import os
import json
from pathlib import Path

from flask import Blueprint, Response, jsonify, redirect, render_template, request, url_for

from common.utils import get_side_tabs, get_tabs, request_area_param
from common import config as app_config
from data.processes import ProcessService
from data.processes.process_repository import default_logger_config
from modules.data import catalogue


data_bp = Blueprint("data", __name__, url_prefix="/data", template_folder="templates", static_folder="static")
catalogue.ensure_schema()
ProcessService()


def _ctx(title):
    return {
        "active_tab": "data",
        "tabs": get_tabs(),
        "side_tabs": get_side_tabs(),
        "content_title": title,
        "content_html": "",
    }


def _area_options():
    options = []
    seen = set()
    for item in get_side_tabs():
        if not isinstance(item, dict):
            continue
        area_id = (item.get("area") or item.get("id") or "").strip()
        label = (item.get("label") or area_id).strip()
        if not area_id or area_id.lower() in {"any", "all", "spacer"}:
            continue
        key = area_id.lower()
        if key in seen:
            continue
        seen.add(key)
        options.append({"id": area_id, "label": label})
    return options


def _request_area(default=""):
    return request_area_param(default)


def _with_area(**kwargs):
    area = _request_area()
    if area:
        kwargs["area"] = area
    return kwargs


@data_bp.route("/")
def overview_route():
    area = _request_area()
    process_service = ProcessService()
    return render_template(
        "data_overview.html",
        **_ctx("Data Workbench"),
        area=area,
        counts=catalogue.overview_counts(area=area),
        recent=catalogue.recent_activity(area=area),
        attention=catalogue.attention_items(),
        process_summary=_process_overview(process_service),
    )


def _process_overview(service):
    processes = service.list_processes()
    logger_process = next((item for item in processes if item.get("process_type") == "logger_json_import"), None)
    latest = service.list_runs(process_id=logger_process["process_id"], limit=1) if logger_process else []
    return {
        "enabled_count": sum(1 for item in processes if item.get("is_enabled")),
        "logger_process": logger_process,
        "latest_logger_run": latest[0] if latest else None,
    }


@data_bp.route("/sources")
def sources_route():
    return redirect(url_for("data.database_sources_route"))


@data_bp.route("/processes")
def processes_route():
    service = ProcessService()
    process_id = request.args.get("process_id", type=int)
    processes = service.list_processes()
    selected = service.get_process(process_id) if process_id else (processes[0] if processes else None)
    latest_details = None
    recent_messages = []
    if selected:
        latest = service.list_runs(process_id=selected["process_id"], limit=1)
        if latest:
            latest_details = service.get_run_details(latest[0]["process_run_id"])
            recent_messages = latest_details["messages"][-8:]
    return render_template(
        "data_processes.html",
        **_ctx("Processes"),
        processes=processes,
        selected=selected,
        latest_details=latest_details,
        recent_messages=recent_messages,
        process_types=service.list_process_types(),
    )


@data_bp.route("/processes/new", methods=["GET", "POST"])
def process_new_route():
    return _process_form(None)


@data_bp.route("/processes/<int:process_id>/edit", methods=["GET", "POST"])
def process_edit_route(process_id):
    return _process_form(process_id)


def _process_form(process_id):
    service = ProcessService()
    process = service.get_process(process_id) if process_id else None
    config = dict((process or {}).get("configuration") or default_logger_config())
    errors = []
    if request.method == "POST":
        values = _process_form_values(request.form, process)
        if request.form.get("action") == "validate":
            temp_id = process_id
            if process_id:
                service.update_process(process_id, values)
            else:
                temp_id = service.create_process(values)
            validation = service.validate_process(temp_id)
            if validation.valid:
                return redirect(url_for("data.process_edit_route", process_id=temp_id, validated="1"))
            errors = validation.messages
            process = service.get_process(temp_id)
            config = process.get("configuration") or config
        else:
            new_id = service.update_process(process_id, values) if process_id else service.create_process(values)
            if request.form.get("action") == "save_run":
                try:
                    service.run_process(new_id)
                except Exception as exc:
                    return redirect(url_for("data.processes_route", process_id=new_id, error=str(exc)))
                latest = service.list_runs(process_id=new_id, limit=1)
                if latest:
                    return redirect(url_for("data.process_run_detail_route", run_id=latest[0]["process_run_id"]))
            return redirect(url_for("data.processes_route", process_id=new_id))
    return render_template(
        "data_process_form.html",
        **_ctx("Edit Process" if process_id else "New Process"),
        process=process,
        config=config,
        errors=errors,
        validated=request.args.get("validated") == "1",
    )


def _process_form_values(form, process=None):
    existing = dict((process or {}).get("configuration") or default_logger_config())
    config = dict(existing)
    config.update(
        {
            "source_folder": form.get("source_folder", "").strip(),
            "file_pattern": form.get("file_pattern", "*.json").strip() or "*.json",
            "include_subfolders": form.get("include_subfolders") == "1",
            "database_path": form.get("database_path", "").strip(),
            "create_database_if_missing": form.get("create_database_if_missing") == "1",
            "create_tables_if_missing": form.get("create_tables_if_missing") == "1",
            "duplicate_detection": form.get("duplicate_detection", "metadata_and_hash"),
            "allow_unknown_record_types": form.get("allow_unknown_record_types") == "1",
            "stop_on_file_error": form.get("stop_on_file_error") == "1",
            "successful_file_action": form.get("successful_file_action", "leave"),
            "processed_folder": form.get("processed_folder", "").strip() or None,
        }
    )
    return {
        "process_name": form.get("process_name", "").strip() or "Import LifePIM Logger JSON",
        "process_type": (process or {}).get("process_type") or form.get("process_type") or "logger_json_import",
        "description": form.get("description", "").strip(),
        "is_enabled": form.get("is_enabled") == "1",
        "configuration": config,
    }


@data_bp.route("/processes/<int:process_id>/<action>", methods=["POST"])
def process_action_route(process_id, action):
    service = ProcessService()
    if action == "toggle":
        process = service.get_process(process_id)
        values = {
            "process_name": process["process_name"],
            "description": process.get("description") or "",
            "is_enabled": not bool(process.get("is_enabled")),
            "configuration": process.get("configuration") or {},
        }
        service.update_process(process_id, values)
        return redirect(url_for("data.processes_route", process_id=process_id))
    try:
        if action == "preview":
            result = service.preview_process(process_id)
        elif action == "run":
            result = service.run_process(process_id)
        elif action == "rebuild":
            result = service.rebuild_process(process_id)
        else:
            return redirect(url_for("data.processes_route", process_id=process_id))
    except Exception as exc:
        return redirect(url_for("data.processes_route", process_id=process_id, error=str(exc)))
    return redirect(url_for("data.process_run_detail_route", run_id=result.process_run_id))


@data_bp.route("/processes/<int:process_id>/open/<target>", methods=["POST"])
def process_open_route(process_id, target):
    service = ProcessService()
    process = service.get_process(process_id)
    if not process:
        return redirect(url_for("data.processes_route"))
    config = process.get("configuration") or {}
    path_value = config.get("source_folder") if target == "source" else config.get("database_path")
    path = Path(_resolve_process_path(path_value or ""))
    if target == "database":
        path = path.parent
    if path:
        try:
            if target == "database":
                path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(path))
        except Exception:
            pass
    return redirect(url_for("data.processes_route", process_id=process_id))


@data_bp.route("/processes/<int:process_id>/view-logger-tables", methods=["POST"])
def process_view_logger_tables_route(process_id):
    service = ProcessService()
    process = service.get_process(process_id)
    if not process:
        return redirect(url_for("data.processes_route"))
    db_path = _resolve_process_path((process.get("configuration") or {}).get("database_path") or "")
    if not db_path or not os.path.isfile(db_path):
        return redirect(url_for("data.processes_route", process_id=process_id))
    existing = next((source for source in catalogue.source_list("DATABASE") if os.path.normcase(os.path.abspath(source.get("root_path") or "")) == os.path.normcase(os.path.abspath(db_path))), None)
    if existing:
        source_id = existing["data_source_id"]
    else:
        source_id = catalogue.save_source(
            None,
            {
                "source_name": "Logger SQLite",
                "source_type": "SQLITE",
                "root_path": db_path,
                "database_name": os.path.basename(db_path),
                "environment": "logger",
                "area": "",
                "scan_views": "on",
                "scan_columns": "on",
                "is_active": "on",
            },
            "DATABASE",
        )
    catalogue.scan_source(source_id)
    return redirect(url_for("data.database_source_detail_route", source_id=source_id))


def _resolve_process_path(value):
    text = str(value or "").strip()
    db_file = Path(getattr(app_config, "DB_FILE", "") or "").expanduser()
    db_dir = str(db_file.parent) if str(db_file) else ""
    data_folder = getattr(app_config, "data_folder", "") or getattr(app_config, "user_folder", ".")
    return str(Path(text.replace("<LIFEPIM_DB_DIR>", db_dir).replace("<LIFEPIM_DATA>", data_folder)).expanduser())


@data_bp.route("/process-runs")
def process_runs_route():
    service = ProcessService()
    filters = {
        "process_id": request.args.get("process_id", ""),
        "status": request.args.get("status", ""),
        "run_mode": request.args.get("run_mode", ""),
    }
    return render_template(
        "data_process_runs.html",
        **_ctx("Process Runs"),
        runs=service.list_runs(filters=filters, limit=200),
        processes=service.list_processes(),
        filters=filters,
    )


@data_bp.route("/process-runs/<int:run_id>")
def process_run_detail_route(run_id):
    service = ProcessService()
    details = service.get_run_details(run_id)
    return render_template(
        "data_process_run_detail.html",
        **_ctx("Process Run"),
        run=details["run"],
        files=details["files"],
        messages=details["messages"],
    )


@data_bp.route("/sources/databases")
def database_sources_route():
    area = _request_area()
    return render_template(
        "data_sources.html",
        **_ctx("Database Sources"),
        section="databases",
        area=area,
        sources=catalogue.source_list("DATABASE", {"area": area} if area else None),
    )


@data_bp.route("/sources/files")
def file_sources_route():
    area = _request_area()
    return render_template(
        "data_sources.html",
        **_ctx("File Sources"),
        section="files",
        area=area,
        sources=catalogue.source_list("FILE_SOURCE", {"area": area} if area else None),
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
                    area_options=_area_options(),
                    error=error,
                    submitted=form,
                )
        new_id = catalogue.save_source(source_id, form, kind)
        if kind == "DATABASE" and source_type in {"SQLITE", "CSV", "EXCEL"}:
            catalogue.scan_source(new_id)
        endpoint = "data.database_source_detail_route" if kind == "DATABASE" else "data.file_source_detail_route"
        return redirect(url_for(endpoint, source_id=new_id, **_with_area()))
    title = ("Edit " if source_id else "Add ") + ("Database Source" if kind == "DATABASE" else "File Source")
    return render_template(
        "data_source_form.html",
        **_ctx(title),
        source=source,
        kind=kind,
        source_types=catalogue.DB_SOURCE_TYPES if kind == "DATABASE" else catalogue.FILE_SOURCE_TYPES,
        area_options=_area_options(),
        error=error,
        submitted={"area": _request_area()} if not source else {},
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
    return render_template("data_source_detail.html", **_ctx(source["source_name"]), area=_request_area(), source=source, objects=objects, tasks=recent_tasks)


@data_bp.route("/sources/<int:source_id>/delete", methods=["POST"])
def source_delete_route(source_id):
    source = catalogue.source_get(source_id)
    catalogue.delete_source(source_id)
    if source and source["source_kind"] == "FILE_SOURCE":
        return redirect(url_for("data.file_sources_route", **_with_area()))
    return redirect(url_for("data.database_sources_route", **_with_area()))


@data_bp.route("/sources/<int:source_id>/test", methods=["POST"])
def source_test_route(source_id):
    task_id = catalogue.test_database_connection(source_id)
    return redirect(url_for("data.task_detail_route", task_id=task_id, **_with_area()))


@data_bp.route("/sources/<int:source_id>/scan", methods=["POST"])
def source_scan_route(source_id):
    task_id = catalogue.scan_source(source_id)
    return redirect(url_for("data.task_detail_route", task_id=task_id, **_with_area()))


@data_bp.route("/objects")
def objects_route():
    area = _request_area()
    filters = {
        key: request.args.get(key, "")
        for key in [
            "q",
            "source_id",
            "object_type",
            "catalogue_level",
            "environment",
            "area",
            "profile_status",
            "quality_status",
            "favourite",
            "hidden",
            "active",
        ]
    }
    if area and not filters.get("area"):
        filters["area"] = area
    return render_template(
        "data_objects.html",
        **_ctx("Data Objects"),
        objects=catalogue.object_list(filters),
        filters=filters,
        area=area,
        sources=catalogue.source_list(None, {"area": area} if area else None),
        object_types=catalogue.OBJECT_TYPES,
        catalogue_levels=catalogue.CATALOGUE_LEVELS,
        environments=catalogue.distinct_values("d_data_source", "environment"),
        area_options=_area_options(),
    )


@data_bp.route("/object/<int:object_id>", methods=["GET", "POST"])
def object_detail_route(object_id):
    if request.method == "POST":
        catalogue.save_object_metadata(object_id, request.form)
        return redirect(url_for("data.object_detail_route", object_id=object_id, **_with_area()))
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
        area_options=_area_options(),
        area=_request_area(),
    )


@data_bp.route("/object/<int:object_id>/level/<level>", methods=["POST"])
def object_level_route(object_id, level):
    catalogue.update_object_level(object_id, level.upper())
    return redirect(url_for("data.object_detail_route", object_id=object_id, **_with_area()))


@data_bp.route("/object/<int:object_id>/toggle/<flag>", methods=["POST"])
def object_toggle_route(object_id, flag):
    allowed = {"favourite": "is_favourite", "hidden": "is_hidden"}
    obj = catalogue.object_get(object_id)
    if obj and flag in allowed:
        col = allowed[flag]
        catalogue.update_object_flags(object_id, **{col: 0 if obj.get(col) else 1})
    return redirect(url_for("data.object_detail_route", object_id=object_id, **_with_area()))


@data_bp.route("/object/<int:object_id>/profile", methods=["POST"])
def object_profile_route(object_id):
    task_id = catalogue.create_task("Profile object", "PROFILE_OBJECT", object_id=object_id, params={"object_id": object_id})
    catalogue.start_task(task_id)
    catalogue.finish_task(task_id, "COMPLETED_WITH_WARNINGS", result_summary="Profile action placeholder created. Profiling is not implemented in Phase 1.")
    return redirect(url_for("data.task_detail_route", task_id=task_id, **_with_area()))


@data_bp.route("/sql")
def sql_route():
    area = _request_area()
    filters = {
        "q": request.args.get("q", ""),
        "source_id": request.args.get("source_id", ""),
        "area": _request_area(),
        "favourite": request.args.get("favourite", ""),
    }
    if area and not filters.get("area"):
        filters["area"] = area
    return render_template(
        "data_sql_list.html",
        **_ctx("Saved SQL"),
        sql_items=catalogue.sql_list(filters),
        filters=filters,
        area=area,
        sources=catalogue.source_list("DATABASE", {"area": area} if area else None),
        area_options=_area_options(),
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
        return redirect(url_for("data.sql_detail_route", sql_id=new_id, **_with_area()))
    area = _request_area()
    return render_template(
        "data_sql_form.html",
        **_ctx("Edit Saved SQL" if sql_id else "Add Saved SQL"),
        item=item,
        sources=catalogue.source_list("DATABASE", {"area": area} if area else None),
        objects=catalogue.object_list({"area": area} if area else {}),
        area_options=_area_options(),
        area=area,
        submitted={"area": area} if not item else {},
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
        area=_request_area(),
    )


@data_bp.route("/sql/<int:sql_id>/delete", methods=["POST"])
def sql_delete_route(sql_id):
    catalogue.delete_sql(sql_id)
    return redirect(url_for("data.sql_route", **_with_area()))


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
    return redirect(url_for("data.task_detail_route", task_id=task_id, **_with_area()))


@data_bp.route("/tasks")
def tasks_route():
    area = _request_area()
    return render_template("data_tasks.html", **_ctx("Data Tasks"), area=area, tasks=catalogue.tasks(filters={"area": area} if area else None))


@data_bp.route("/task/<int:task_id>")
def task_detail_route(task_id):
    task = catalogue.task_get(task_id)
    if not task:
        return redirect(url_for("data.tasks_route"))
    return render_template("data_task_detail.html", **_ctx(task["task_name"]), task=task)


@data_bp.route("/import-db", methods=["GET", "POST"])
def import_data_db_route():
    area = request_area_param(include_form=True) if request.method == "POST" else _request_area()
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
                    "environment": area,
                    "area": area,
                    "scan_views": "on",
                    "scan_columns": "on",
                    "is_active": "on",
                }
                catalogue.save_source(None, form_data, "DATABASE")
                count += 1
            imported = count
    return render_template(
        "data_import_db.html",
        **_ctx("Import SQLite Databases"),
        area=area,
        area_options=_area_options(),
        imported=imported,
        error=error,
    )


@data_bp.route("/import-db-folder", methods=["POST"])
def import_data_db_folder_route():
    folder_path = request.form.get("db_folder", "").strip()
    area = request_area_param(include_form=True) or _request_area()
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
                            "environment": area,
                            "area": area,
                            "scan_views": "on",
                            "scan_columns": "on",
                            "is_active": "on",
                        },
                        "DATABASE",
                    )
                    imported += 1
    return render_template(
        "data_import_db.html",
        **_ctx("Import SQLite Databases"),
        area=area,
        area_options=_area_options(),
        imported=imported,
        error=error,
    )
