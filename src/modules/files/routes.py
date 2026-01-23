import os
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for

from common import data as db
from common.utils import build_form_fields, get_side_tabs, get_table_def, get_tabs, paginate_total, build_pagination
from common import config as cfg


files_bp = Blueprint(
    "files",
    __name__,
    url_prefix="/files",
    template_folder="templates",
    static_folder="static",
)


def _get_tbl():
    return get_table_def("files")


def _load_item(item_id):
    tbl = _get_tbl()
    if not tbl:
        return None
    rows = db.get_data(db.conn, tbl["name"], ["id"] + tbl["col_list"], "id = ?", [item_id])
    if rows:
        return dict(rows[0])
    return None


def _list_drives():
    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        path = f"{letter}:\\"
        if os.path.exists(path):
            drives.append(path)
    return drives


def _build_tree(base_path, rel_path="", max_depth=3):
    full_path = _safe_join(base_path, rel_path) if rel_path else base_path
    if max_depth < 0 or not os.path.isdir(full_path):
        return []
    nodes = []
    try:
        with os.scandir(full_path) as it:
            for entry in it:
                if entry.is_dir():
                    child_rel = os.path.join(rel_path, entry.name) if rel_path else entry.name
                    nodes.append(
                        {
                            "name": entry.name,
                            "rel_path": child_rel,
                            "children": _build_tree(base_path, child_rel, max_depth - 1),
                        }
                    )
    except Exception:
        return []
    nodes.sort(key=lambda row: row["name"].lower())
    return nodes


def _list_folders(base_path):
    if not base_path:
        return [], "No path provided."
    if not os.path.isdir(base_path):
        return [], f"Path not found: {base_path}"
    try:
        tree = _build_tree(base_path)
    except Exception as exc:
        return [], f"Unable to read directory: {exc}"
    return tree, ""


def _list_files(folder_path):
    if not folder_path:
        return [], "No folder selected."
    if not os.path.isdir(folder_path):
        return [], f"Path not found: {folder_path}"
    entries = []
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_file():
                    info = entry.stat()
                    entries.append(
                        {
                            "name": entry.name,
                            "full_path": entry.path,
                            "size": info.st_size,
                            "modified": datetime.fromtimestamp(info.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
    except Exception as exc:
        return [], f"Unable to read files: {exc}"
    entries.sort(key=lambda row: row["name"].lower())
    return entries, ""


def _safe_join(base_path, rel_path):
    if not rel_path:
        return base_path
    cleaned = rel_path.replace("/", os.sep).replace("\\", os.sep)
    return os.path.normpath(os.path.join(base_path, cleaned))


def _normalize_drive(drive_value):
    if not drive_value:
        return ""
    if len(drive_value) == 2 and drive_value[1] == ":":
        return f"{drive_value}\\"
    return drive_value


def _drive_root(path_value):
    if not path_value:
        return ""
    drive, _ = os.path.splitdrive(path_value)
    if not drive:
        return ""
    return _normalize_drive(drive)


def _rel_path(base_path, full_path):
    try:
        return os.path.relpath(full_path, base_path)
    except ValueError:
        return ""


@files_bp.route("/tree")
def tree_view_route():
    base_path = _normalize_drive(request.args.get("drive") or "")
    rel_dir = request.args.get("dir") or ""
    if not base_path:
        return {"nodes": [], "error": "No drive selected."}
    folder_path = _safe_join(base_path, rel_dir)
    if not os.path.isdir(folder_path):
        return {"nodes": [], "error": f"Path not found: {folder_path}"}
    nodes = []
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                if entry.is_dir():
                    nodes.append(
                        {
                            "name": entry.name,
                            "rel_path": _rel_path(base_path, entry.path),
                        }
                    )
    except Exception as exc:
        return {"nodes": [], "error": f"Unable to read directory: {exc}"}
    nodes.sort(key=lambda row: row["name"].lower())
    return {"nodes": nodes, "error": ""}


@files_bp.route("/list")
def file_list_route():
    base_path = _normalize_drive(request.args.get("base") or "")
    rel_dir = request.args.get("dir") or ""
    if not base_path:
        return {"files": [], "error": "No base path provided."}
    folder_path = _safe_join(base_path, rel_dir)
    files, error = _list_files(folder_path)
    return {"files": files, "error": error}


@files_bp.route("/")
def list_files_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = _get_tbl()
    items = []
    col_list = []
    content_title = "Files"
    sort_col = request.args.get("sort") or "id"
    dir_param = request.args.get("dir")
    if not dir_param:
        sort_dir = "desc"
    else:
        sort_dir = "desc" if dir_param.lower() == "desc" else "asc"
    page = request.args.get("page", type=int) or 1
    total_pages = 1
    pagination = build_pagination(
        url_for,
        "files.list_files_route",
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        1,
        1,
    )
    if tbl:
        col_list = tbl["col_list"]
        allowed_sort = {"id"} | set(col_list)
        if sort_col not in allowed_sort:
            sort_col = "id"
        order_key = "t.id" if sort_col == "id" else f"t.{sort_col}"
        order_by = f"{order_key} {sort_dir}"
        cols = ["id"] + col_list
        per_page = cfg.RECS_PER_PAGE
        total = db.count_mapped_rows(db.conn, tbl["name"], tab=project)
        offset = (page - 1) * per_page
        rows = db.get_mapped_rows(
            db.conn,
            tbl["name"],
            cols,
            tab=project,
            limit=per_page,
            offset=offset,
            order_by=order_by,
        )
        items = [dict(row) for row in rows]
        content_title = f"{tbl['display_name']} ({project or 'All'})"
        page_data = paginate_total(total, page, per_page)
        page = page_data["page"]
        total_pages = page_data["total_pages"]
        pagination = build_pagination(
            url_for,
            "files.list_files_route",
            {"proj": project, "sort": sort_col, "dir": sort_dir},
            page,
            total_pages,
        )
    return render_template(
        "files_list.html",
        active_tab="files",
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


@files_bp.route("/view/<int:item_id>")
def view_file_route(item_id):
    project = request.args.get("proj")
    selected_dir = request.args.get("dir") or ""
    drive = _normalize_drive(request.args.get("drive"))
    item = _load_item(item_id)
    if not item:
        return redirect(url_for("files.list_files_route", proj=project))
    item_path = item.get("path", "") or ""
    if not drive:
        drive = _drive_root(item_path)
        if drive and not selected_dir and item_path:
            rel_path = _rel_path(drive, item_path)
            selected_dir = "" if rel_path in (".", "") else rel_path
    base_path = drive or item_path
    drives = _list_drives()
    selected_path = _safe_join(base_path, selected_dir)
    files, files_error = _list_files(selected_path)
    explorer_error = files_error
    return render_template(
        "files_view.html",
        active_tab="files",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=item.get("filelist_name", "File List"),
        content_html="",
        item=item,
        col_list=_get_tbl()["col_list"],
        project=project,
        file_list=files,
        explorer_error=explorer_error,
        selected_dir=selected_dir,
        base_path=base_path,
        drives=drives,
        selected_drive=drive,
    )


@files_bp.route("/add", methods=["GET", "POST"])
def add_file_route():
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
        return redirect(url_for("files.list_files_route", proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "files_edit.html",
        active_tab="files",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add File",
        item=None,
        fields=fields,
        project=project,
    )


@files_bp.route("/edit/<int:item_id>", methods=["GET", "POST"])
def edit_file_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    item = _load_item(item_id)
    if request.method == "POST" and tbl:
        values = [request.form.get(col, "").strip() for col in tbl["col_list"]]
        db.update_record(db.conn, tbl["name"], item_id, tbl["col_list"], values)
        return redirect(url_for("files.view_file_route", item_id=item_id, proj=project))
    fields = build_form_fields(tbl["col_list"]) if tbl else []
    return render_template(
        "files_edit.html",
        active_tab="files",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Edit File",
        item=item,
        fields=fields,
        project=project,
    )


@files_bp.route("/delete/<int:item_id>")
def delete_file_route(item_id):
    project = request.args.get("proj")
    tbl = _get_tbl()
    if tbl:
        db.delete_record(db.conn, tbl["name"], item_id)
    return redirect(url_for("files.list_files_route", proj=project))
