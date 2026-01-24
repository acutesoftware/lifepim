import os
import re
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, redirect, url_for, make_response, send_file, abort, jsonify

from common import data
from utils import importer
from utils import markdown_utils
from utils import hex_utils
from common.utils import get_tabs, get_side_tabs, get_table_def, paginate_total, build_pagination
from common import config as cfg
import etl_folder_mapping as folder_etl

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')

INVALID_TITLE_CHARS = re.compile(r'[<>:"/\\|?*]')
WHITESPACE_RE = re.compile(r"\s+")
NOTE_TITLE_MAX_LEN = 80


def _sanitize_title(title):
    cleaned = INVALID_TITLE_CHARS.sub("", (title or "").strip())
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > NOTE_TITLE_MAX_LEN:
        cleaned = cleaned[:NOTE_TITLE_MAX_LEN].rstrip()
    return cleaned or "Untitled"


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    return {row[1] for row in rows}


def _query_write_root_candidates(conn, tab_label):
    if not tab_label:
        return []
    if _table_exists(conn, "map_project_folder"):
        columns = _table_columns(conn, "map_project_folder")
        path_col = "path_prefix" if "path_prefix" in columns else None
        if path_col:
            enabled_col = "is_enabled" if "is_enabled" in columns else ("enabled" if "enabled" in columns else None)
            tags_col = "tags" if "tags" in columns else None
            conf_col = "confidence" if "confidence" in columns else None
            notes_col = "notes" if "notes" in columns else None
            tags_expr = tags_col or "''"
            conf_expr = conf_col or "1.0"
            notes_expr = notes_col or "''"
            where = ["tab = ?"]
            params = [tab_label]
            if enabled_col:
                where.append(f"{enabled_col} = 1")
            if tags_col:
                where.append("lower(tags) LIKE '%canonical%'")
                where.append("lower(tags) LIKE '%write_root%'")
            sql = (
                f"SELECT {path_col} as path_prefix, tab, "
                f"{tags_expr} as tags, "
                f"{conf_expr} as confidence, "
                f"{notes_expr} as notes "
                "FROM map_project_folder "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY confidence DESC, LENGTH(path_prefix) ASC, path_prefix ASC"
            )
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    if _table_exists(conn, "map_folder_project"):
        columns = _table_columns(conn, "map_folder_project")
        if "path_prefix" not in columns or "tab" not in columns:
            return []
        enabled_col = "is_enabled" if "is_enabled" in columns else ("enabled" if "enabled" in columns else None)
        tags_col = "tags" if "tags" in columns else None
        conf_col = "confidence" if "confidence" in columns else None
        notes_col = "notes" if "notes" in columns else None
        tags_expr = tags_col or "''"
        conf_expr = conf_col or "1.0"
        notes_expr = notes_col or "''"
        where = ["tab = ?"]
        params = [tab_label]
        if enabled_col:
            where.append(f"{enabled_col} = 1")
        if tags_col:
            where.append("lower(tags) LIKE '%canonical%'")
            where.append("lower(tags) LIKE '%write_root%'")
        sql = (
            "SELECT path_prefix, tab, "
            f"{tags_expr} as tags, "
            f"{conf_expr} as confidence, "
            f"{notes_expr} as notes "
            "FROM map_folder_project "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY confidence DESC, LENGTH(path_prefix) ASC, path_prefix ASC"
        )
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    if _table_exists(conn, "map_project_folder"):
        columns = _table_columns(conn, "map_project_folder")
        path_col = "matched_prefix" if "matched_prefix" in columns else None
        if not path_col:
            return []
        enabled_col = "is_enabled" if "is_enabled" in columns else ("enabled" if "enabled" in columns else None)
        tags_col = "tags" if "tags" in columns else None
        conf_col = "confidence" if "confidence" in columns else None
        notes_col = "notes" if "notes" in columns else None
        tags_expr = tags_col or "''"
        conf_expr = conf_col or "1.0"
        notes_expr = notes_col or "''"
        where = ["tab = ?"]
        params = [tab_label]
        if enabled_col:
            where.append(f"{enabled_col} = 1")
        if tags_col:
            where.append("lower(tags) LIKE '%canonical%'")
            where.append("lower(tags) LIKE '%write_root%'")
        sql = (
            f"SELECT {path_col} as path_prefix, tab, "
            f"{tags_expr} as tags, "
            f"{conf_expr} as confidence, "
            f"{notes_expr} as notes "
            "FROM map_project_folder "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY confidence DESC, LENGTH(path_prefix) ASC, path_prefix ASC"
        )
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    return []


def _lookup_tab_group(conn, tab_label):
    label = (tab_label or "").strip()
    if not label:
        return ""
    if _table_exists(conn, "map_folder_project"):
        columns = _table_columns(conn, "map_folder_project")
        if "grp" in columns and "tab" in columns:
            enabled_col = "is_enabled" if "is_enabled" in columns else ("enabled" if "enabled" in columns else None)
            where = ["lower(tab) = lower(?)"]
            params = [label]
            if enabled_col:
                where.append(f"{enabled_col} = 1")
            sql = (
                "SELECT grp FROM map_folder_project "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY confidence DESC, LENGTH(path_prefix) DESC"
            )
            row = conn.execute(sql, params).fetchone()
            return (row["grp"] or "").strip() if row else ""
    if _table_exists(conn, "map_project_folder"):
        columns = _table_columns(conn, "map_project_folder")
        if "grp" in columns and "tab" in columns:
            enabled_col = "is_enabled" if "is_enabled" in columns else ("enabled" if "enabled" in columns else None)
            where = ["lower(tab) = lower(?)"]
            params = [label]
            if enabled_col:
                where.append(f"{enabled_col} = 1")
            sql = (
                "SELECT grp FROM map_project_folder "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY confidence DESC"
            )
            row = conn.execute(sql, params).fetchone()
            return (row["grp"] or "").strip() if row else ""
    return ""


def _dedupe_candidates(rows):
    results = []
    seen = set()
    for row in rows or []:
        path_prefix = (row.get("path_prefix") or "").strip()
        norm_path = folder_etl.norm_path(path_prefix)
        if not norm_path:
            continue
        key = norm_path.lower()
        if key in seen:
            continue
        row["path_prefix"] = norm_path
        row["notes"] = (row.get("notes") or "").strip()
        row["tags"] = (row.get("tags") or "").strip()
        try:
            row["confidence"] = float(row.get("confidence") or 0)
        except Exception:
            row["confidence"] = 0
        results.append(row)
        seen.add(key)
    return results


def _parent_section(label):
    if not label or ">" not in label:
        return ""
    return label.split(">", 1)[0].strip()


def _select_write_root_candidates(sidebar_label):
    label = (sidebar_label or "").strip()
    conn = data._get_conn()
    if label:
        rows = _dedupe_candidates(_query_write_root_candidates(conn, label))
        if rows:
            return rows, label
        if ">" in label:
            normalized = " ".join(label.replace(">", " ").split())
            if normalized and normalized != label:
                rows = _dedupe_candidates(_query_write_root_candidates(conn, normalized))
                if rows:
                    return rows, normalized
    parent = _parent_section(label)
    if parent:
        rows = _dedupe_candidates(_query_write_root_candidates(conn, parent))
        if rows:
            return rows, parent
    if label:
        grp = _lookup_tab_group(conn, label)
        if grp:
            rows = _dedupe_candidates(_query_write_root_candidates(conn, grp))
            if rows:
                return rows, grp
    rows = _dedupe_candidates(_query_write_root_candidates(conn, "All Projects"))
    if rows:
        return rows, "All Projects"
    return [], label or parent or "All Projects"


def _note_template(title, created_utc, sidebar_label):
    title_value = (title or "").replace('"', '\\"')
    lines = [
        "---",
        f'title: "{title_value}"',
        f'created_utc: "{created_utc}"',
    ]
    if sidebar_label:
        sidebar_value = (sidebar_label or "").replace('"', '\\"')
        lines.append(f'sidebar_tab: "{sidebar_value}"')
    lines.append("tags: []")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def _write_note_file(folder_path, base_name, content):
    for idx in range(1, 1000):
        if idx == 1:
            file_name = f"{base_name}.md"
        else:
            file_name = f"{base_name} ({idx}).md"
        full_path = os.path.join(folder_path, file_name)
        try:
            with open(full_path, "x", encoding="utf-8") as handle:
                handle.write(content)
            return file_name, full_path
        except FileExistsError:
            continue
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    file_name = f"{stamp} {base_name}.md"
    full_path = os.path.join(folder_path, file_name)
    with open(full_path, "x", encoding="utf-8") as handle:
        handle.write(content)
    return file_name, full_path


def _create_note_file(folder_path, title, sidebar_label):
    folder_norm = folder_etl.norm_path(folder_path)
    folder_path = folder_norm or folder_path
    if not folder_path:
        raise ValueError("Missing folder path")
    os.makedirs(folder_path, exist_ok=True)
    title_clean = _sanitize_title(title)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    base_name = f"{date_prefix} {title_clean}".strip().rstrip(". ")
    created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = _note_template(title_clean, created_utc, sidebar_label)
    file_name, full_path = _write_note_file(folder_path, base_name, content)
    return {
        "file_name": file_name,
        "full_path": full_path,
        "folder_path": folder_path,
        "created_utc": created_utc,
        "title": title_clean,
    }

def _fetch_notes(project, sort_col=None, sort_dir=None, limit=None, offset=None):
    tbl = get_table_def("notes")
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    order_map = {
        "file_name": "t.file_name",
        "path": "t.path",
        "folder_id": "t.folder_id",
        "size": "t.size",
        "project": "t.project",
        "date_modified": "t.date_modified",
        "updated": "t.rec_extract_date",
        "derived_project": "derived_project",
    }
    sort_key = order_map.get(sort_col or "updated", "t.rec_extract_date")
    sort_dir = sort_dir or "desc"
    order_by = f"{sort_key} {sort_dir}"
    select_cols = [f"t.{col}" for col in cols]
    select_cols.append("t.rec_extract_date as updated")
    select_cols.append("MAX(mpf.tab) as derived_project")
    params = []
    if project and project.lower() == "unmapped":
        condition = "mpf.folder_id IS NULL"
    elif project:
        condition = "lower(mpf.tab) = lower(?)"
        params.append(project)
    else:
        condition = "1=1"
    sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {tbl['name']} t "
        "LEFT JOIN map_project_folder mpf "
        "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
        f"WHERE {condition} "
        "GROUP BY t.id "
        f"ORDER BY {order_by}"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    rows = data._get_conn().execute(sql, params).fetchall()
    notes = [dict(row) for row in rows]
    for note in notes:
        note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
        note["date_modified_dt"] = _parse_datetime(note.get("date_modified")) or note["updated"]
    return notes


@notes_bp.route('/')
def list_notes_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = get_table_def("notes")
    if not tbl:
        return render_template(
            "notes_list.html",
            active_tab="notes",
            tabs=get_tabs(),
            side_tabs=get_side_tabs(),
            content_title="Notes",
            content_html="",
            notes=[],
            project=project,
            sort_col="date_modified",
            sort_dir="desc",
            route_name="notes.list_notes_table_route",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_table_route"),
            last_url=url_for("notes.list_notes_table_route"),
        )
    view_pref = request.cookies.get("notes_view")
    if view_pref in ("list", "cards"):
        return redirect(url_for(f"notes.list_notes_{view_pref}_route", proj=project))
    sort_col = request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified"
    sort_dir = request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = data.count_mapped_rows(data.conn, tbl["name"], tab=project)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    route_name = "notes.list_notes_table_route"
    pagination = build_pagination(
        url_for,
        route_name,
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/table')
def list_notes_table_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = get_table_def("notes")
    if not tbl:
        return render_template(
            "notes_list.html",
            active_tab="notes",
            tabs=get_tabs(),
            side_tabs=get_side_tabs(),
            content_title="Notes",
            content_html="",
            notes=[],
            project=project,
            sort_col="date_modified",
            sort_dir="desc",
            route_name="notes.list_notes_table_route",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_table_route"),
            last_url=url_for("notes.list_notes_table_route"),
        )
    sort_col = request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified"
    sort_dir = request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = data.count_mapped_rows(data.conn, tbl["name"], tab=project)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, sort_col, sort_dir, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    route_name = "notes.list_notes_table_route"
    pagination = build_pagination(
        url_for,
        route_name,
        {"proj": project, "sort": sort_col, "dir": sort_dir},
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/list')
def list_notes_list_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = get_table_def("notes")
    if not tbl:
        return render_template(
            "notes_list_list.html",
            active_tab="notes",
            tabs=get_tabs(),
            side_tabs=get_side_tabs(),
            content_title="Notes",
            content_html="",
            notes=[],
            project=project,
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_list_route"),
            last_url=url_for("notes.list_notes_list_route"),
        )
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = data.count_mapped_rows(data.conn, tbl["name"], tab=project)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "notes.list_notes_list_route",
        {"proj": project},
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        project=project,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )
    )
    resp.set_cookie("notes_view", "list")
    return resp


@notes_bp.route('/cards')
def list_notes_cards_route():
    project = request.args.get("proj")
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = None
    tbl = get_table_def("notes")
    if not tbl:
        return render_template(
            "notes_list_cards.html",
            active_tab="notes",
            tabs=get_tabs(),
            side_tabs=get_side_tabs(),
            content_title="Notes",
            content_html="",
            notes=[],
            card_values=[],
            project=project,
            note_card_bg=cfg.NOTE_CARD_DEF_BG_COL,
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_cards_route"),
            last_url=url_for("notes.list_notes_cards_route"),
        )
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = data.count_mapped_rows(data.conn, tbl["name"], tab=project)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, limit=per_page, offset=offset)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "notes.list_notes_cards_route",
        {"proj": project},
        page,
        total_pages,
    )
    card_values = [
        [n.get("file_name"), n.get("path"), url_for("notes.view_note_route", note_id=n.get("id"))]
        for n in notes
    ]
    resp = make_response(
        render_template(
        "notes_list_cards.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project or 'All'})",
        content_html="",
        notes=notes,
        card_values=card_values,
        project=project,
        note_card_bg=cfg.NOTE_CARD_DEF_BG_COL,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
    )
    )
    resp.set_cookie("notes_view", "cards")
    return resp

@notes_bp.route('/view/<int:note_id>')
def view_note_route(note_id):
    render_mode = request.args.get("format") or "markdown"
    tbl = get_table_def("notes")
    note = None
    if tbl:
        select_cols = [f"t.{col}" for col in (["id"] + tbl["col_list"])]
        select_cols.append("t.rec_extract_date as updated")
        select_cols.append("MAX(mpf.tab) as derived_project")
        sql = (
            f"SELECT {', '.join(select_cols)} "
            f"FROM {tbl['name']} t "
            "LEFT JOIN map_project_folder mpf "
            "ON mpf.folder_id = t.folder_id AND mpf.is_primary=1 AND mpf.is_enabled=1 "
            "WHERE t.id = ? "
            "GROUP BY t.id"
        )
        rows = data._get_conn().execute(sql, [note_id]).fetchall()
        if rows:
            note = dict(rows[0])
            note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    if not note:
        return redirect(url_for("notes.list_notes_route"))
    note_path = _build_note_path(note)
    file_exists = note_path and os.path.isfile(note_path)
    note_text = ""
    if file_exists:
        note_text = _read_note_file(note_path)
    content_html = ""
    hex_rows = []
    if render_mode == "markdown":
        def _asset_url(asset_name):
            return url_for("notes.note_asset_route", note_id=note_id, asset_path=asset_name)

        content_html = markdown_utils.render_markdown(note_text, asset_resolver=_asset_url)
    elif render_mode == "hex":
        hex_rows = hex_utils.hex_dump(note_text)
    return render_template(
        "note_view.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title=note.get("file_name") or "Note",
        content_html="",
        render_mode=render_mode,
        content_html_rendered=content_html,
        hex_rows=hex_rows,
        note_text=note_text,
        file_exists=file_exists,
        note_path=note_path,
    )


@notes_bp.route('/asset/<int:note_id>/<path:asset_path>')
def note_asset_route(note_id, asset_path):
    tbl = get_table_def("notes")
    if not tbl:
        abort(404)
    rows = data.get_data(
        data.conn,
        tbl["name"],
        ["id"] + tbl["col_list"],
        "id = ?",
        [note_id],
    )
    if not rows:
        abort(404)
    note = dict(rows[0])
    note_path = _build_note_path(note)
    base_dir = os.path.dirname(note_path) if note_path else ""
    if not base_dir or os.path.isabs(asset_path):
        abort(404)
    full_path = os.path.abspath(os.path.join(base_dir, asset_path))
    base_dir = os.path.abspath(base_dir)
    if not full_path.startswith(base_dir + os.sep):
        abort(404)
    if not os.path.isfile(full_path):
        abort(404)
    return send_file(full_path)


@notes_bp.route('/api/new-note-options')
def new_note_options_route():
    sidebar_label = (request.args.get("sidebar_label") or request.args.get("proj") or "").strip()
    options, resolved_label = _select_write_root_candidates(sidebar_label)
    return jsonify({
        "sidebar_label": resolved_label,
        "options": options,
    })


@notes_bp.route('/api/create-note', methods=["POST"])
def create_note_route():
    payload = request.get_json(silent=True) or {}
    sidebar_label = (payload.get("sidebar_label") or "").strip()
    title = (payload.get("title") or "").strip()
    path_prefix = (payload.get("path_prefix") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400
    if not path_prefix:
        options, resolved_label = _select_write_root_candidates(sidebar_label)
        if not options:
            return jsonify({"error": "No canonical write root found."}), 400
        path_prefix = options[0].get("path_prefix") or ""
        if not sidebar_label:
            sidebar_label = resolved_label
    if not path_prefix:
        return jsonify({"error": "Folder path is required."}), 400
    try:
        created = _create_note_file(path_prefix, title, sidebar_label)
    except OSError as exc:
        return jsonify({"error": f"Unable to create note file: {exc}"}), 500
    except Exception as exc:
        return jsonify({"error": f"Unable to create note file: {exc}"}), 500

    tbl = get_table_def("notes")
    if not tbl:
        try:
            os.remove(created["full_path"])
        except Exception:
            pass
        return jsonify({"error": "Notes table not found."}), 500

    try:
        size = str(os.path.getsize(created["full_path"]))
        date_modified = datetime.fromtimestamp(
            os.path.getmtime(created["full_path"])
        ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        size = ""
        date_modified = ""

    values_map = {
        "file_name": created["file_name"],
        "path": created["folder_path"],
        "folder_id": "",
        "size": size,
        "date_modified": date_modified,
        "project": sidebar_label,
    }
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    note_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
    if not note_id:
        try:
            os.remove(created["full_path"])
        except Exception:
            pass
        return jsonify({"error": "Unable to insert note record."}), 500
    return jsonify({
        "note_id": note_id,
        "file_name": created["file_name"],
        "path": created["folder_path"],
        "full_path": created["full_path"],
        "open_url": url_for("notes.view_note_route", note_id=note_id),
    })

@notes_bp.route('/add', methods=["GET", "POST"])
def add_note_route():
    tbl = get_table_def("notes")
    project = request.args.get("proj") or "General"
    if request.method == "POST" and tbl:
        form_values = {col: request.form.get(col, "").strip() for col in tbl["col_list"]}
        if not form_values.get("project"):
            form_values["project"] = project
        note_path = _build_note_path(form_values)
        if note_path and os.path.isfile(note_path):
            if not form_values.get("size"):
                form_values["size"] = str(os.path.getsize(note_path))
            if not form_values.get("date_modified"):
                form_values["date_modified"] = datetime.fromtimestamp(
                    os.path.getmtime(note_path)
                ).strftime("%Y-%m-%d %H:%M:%S")
        values = [form_values.get(col, "") for col in tbl["col_list"]]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("notes.list_notes_route", proj=project))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Note",
        note=None,
        project=project,
    )

@notes_bp.route('/edit/<int:note_id>', methods=["GET", "POST"])
def edit_note_route(note_id):
    tbl = get_table_def("notes")
    note = None
    if tbl:
        rows = data.get_data(
            data.conn,
            tbl["name"],
            ["id"] + tbl["col_list"] + ["rec_extract_date as updated"],
            "id = ?",
            [note_id],
        )
        if rows:
            note = dict(rows[0])
            note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    if request.method == "POST" and tbl:
        form_values = {col: request.form.get(col, "").strip() for col in tbl["col_list"]}
        if not form_values.get("project"):
            form_values["project"] = "General"
        note_path = _build_note_path(form_values)
        if note_path and os.path.isfile(note_path):
            if not form_values.get("size"):
                form_values["size"] = str(os.path.getsize(note_path))
            if not form_values.get("date_modified"):
                form_values["date_modified"] = datetime.fromtimestamp(
                    os.path.getmtime(note_path)
                ).strftime("%Y-%m-%d %H:%M:%S")
        values = [form_values.get(col, "") for col in tbl["col_list"]]
        data.update_record(data.conn, tbl["name"], note_id, tbl["col_list"], values)
        return redirect(url_for("notes.view_note_route", note_id=note_id))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title=f"Edit: {note.get('file_name')}" if note else "Edit Note",
    )

@notes_bp.route('/delete/<int:note_id>')
def delete_note_route(note_id):
    tbl = get_table_def("notes")
    if tbl:
        data.delete_record(data.conn, tbl["name"], note_id)
    return redirect(url_for("notes.list_notes_route"))


@notes_bp.route('/import', methods=["GET", "POST"])
def import_notes_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = get_table_def("notes")
    csv_path = ""
    headers = []
    mappings = {}
    imported = None
    error = ""
    if request.method == "POST":
        csv_path = request.form.get("csv_path", "").strip()
        upload = request.files.get("csv_file")
        if upload and upload.filename:
            csv_path = importer.save_upload(upload)
        action = request.form.get("action", "load")
        headers = importer.read_csv_headers(csv_path)
        if action == "import" and tbl:
            mappings = {col: request.form.get(f"map_{col}", "") for col in tbl["col_list"]}
            map_list = []
            for col in tbl["col_list"]:
                choice = mappings.get(col, "")
                if choice == "{curr_project_selected}":
                    choice = project
                map_list.append(choice)
            try:
                importer.set_token("curr_project_selected", project)
                imported = importer.import_to_table(tbl["name"], csv_path, map_list)
            except Exception as exc:
                error = str(exc)
        else:
            mappings = {col: "" for col in (tbl["col_list"] if tbl else [])}
    return render_template(
        "notes_import.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Notes",
        content_html="",
        project=project,
        table_def=tbl,
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
    )


@notes_bp.route('/import-folder', methods=["GET", "POST"])
def import_notes_folder_route():
    project = request.args.get("proj") or ""
    if project in ("any", "All", "all", "ALL", "spacer"):
        project = ""
    tbl = get_table_def("notes")
    imported = None
    error = ""
    if request.method == "POST":
        folder_path = request.form.get("notes_folder", "").strip()
        if not folder_path:
            error = "No folder provided."
        elif not os.path.isdir(folder_path):
            error = "Folder not found."
        elif not tbl:
            error = "Notes table not found."
        else:
            count = 0
            for root, _, files in os.walk(folder_path):
                for name in files:
                    if not name.lower().endswith(".md"):
                        continue
                    full_path = os.path.join(root, name)
                    if not os.path.isfile(full_path):
                        continue
                    values_map = {
                        "file_name": name,
                        "path": root,
                        "size": str(os.path.getsize(full_path)),
                        "date_modified": datetime.fromtimestamp(os.path.getmtime(full_path)).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "project": project,
                    }
                    values = [values_map.get(col, "") for col in tbl["col_list"]]
                    record_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
                    if record_id:
                        count += 1
            imported = count
    return render_template(
        "notes_import_folder.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Notes Folder",
        content_html="",
        project=project,
        imported=imported,
        error=error,
    )


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _sort_notes(notes, sort_col, sort_dir):
    key_map = {
        "file_name": lambda n: (n.get("file_name") or "").lower(),
        "path": lambda n: (n.get("path") or "").lower(),
        "size": lambda n: _parse_size(n.get("size")),
        "project": lambda n: (n.get("project") or "").lower(),
        "date_modified": lambda n: n.get("date_modified_dt") or datetime.min,
        "updated": lambda n: n.get("updated") or datetime.min,
    }
    key_fn = key_map.get(sort_col, key_map["updated"])
    reverse = sort_dir == "desc"
    return sorted(notes, key=key_fn, reverse=reverse)


def _build_note_path(note):
    file_name = (note.get("file_name") or "").strip()
    path = (note.get("path") or "").strip()
    if path and file_name:
        return os.path.join(path, file_name)
    if file_name and os.path.isabs(file_name):
        return file_name
    return path or file_name


def _read_note_file(note_path):
    try:
        with open(note_path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def _parse_size(value):
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
