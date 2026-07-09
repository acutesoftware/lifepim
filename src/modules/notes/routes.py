import os
import re
import hashlib
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import Blueprint, render_template, request, redirect, url_for, make_response, send_file, abort, jsonify

from common import data
from utils import importer
from utils import markdown_utils
from utils import hex_utils
from common.utils import get_tabs, get_side_tabs, get_table_def, paginate_total, build_pagination, lg_usr
from common import config as cfg
import etl_folder_mapping as folder_etl
from common import projects as projects_mod

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')

INVALID_TITLE_CHARS = re.compile(r'[<>:"/\\|?*]')
WHITESPACE_RE = re.compile(r"\s+")
NOTE_TITLE_MAX_LEN = 80


def _normalize_project_param(project):
    project = (project or "").strip()
    if project in ("any", "All", "all", "ALL", "spacer"):
        return ""
    return project


def _normalize_note_path(path_value):
    """Normalize a notes path without applying global mirror/NAS aliases."""
    path_value = (path_value or "").strip().strip('"').strip()
    if not path_value:
        return ""
    path_value = path_value.replace("/", "\\")
    if len(path_value) >= 2 and path_value[1] == ":":
        path_value = path_value[0].upper() + path_value[1:]
    if len(path_value) > 3 and path_value.endswith("\\"):
        path_value = path_value.rstrip("\\")
    return path_value


def _path_startswith(path_value, prefix):
    path_value = _normalize_note_path(path_value)
    prefix = _normalize_note_path(prefix)
    return bool(prefix and (path_value.lower() == prefix.lower() or path_value.lower().startswith(prefix.lower() + "\\")))


def _replace_path_prefix(path_value, old_prefix, new_prefix):
    path_norm = _normalize_note_path(path_value)
    old_norm = _normalize_note_path(old_prefix)
    new_norm = _normalize_note_path(new_prefix)
    if not old_norm or not _path_startswith(path_norm, old_norm):
        return path_norm
    return new_norm + path_norm[len(old_norm):]


def _notes_root_from_path(path_value):
    path_norm = _normalize_note_path(path_value)
    parts = [part for part in path_norm.split("\\") if part]
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            return "\\".join(parts[: idx + 2])
    return ""


def _alias_counterpart_roots(path_value):
    path_norm = _normalize_note_path(path_value)
    roots = []
    for src, dst in getattr(cfg, "PATH_ALIASES", []):
        src_norm = _normalize_note_path(src)
        dst_norm = _normalize_note_path(dst)
        if src_norm and _path_startswith(path_norm, src_norm):
            roots.append(dst_norm + path_norm[len(src_norm):])
        if dst_norm and _path_startswith(path_norm, dst_norm):
            roots.append(src_norm + path_norm[len(dst_norm):])
    return [_normalize_note_path(root) for root in roots if root]


def _sanitize_title(title):
    cleaned = INVALID_TITLE_CHARS.sub("", (title or "").strip())
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > NOTE_TITLE_MAX_LEN:
        cleaned = cleaned[:NOTE_TITLE_MAX_LEN].rstrip()
    return cleaned or "Untitled"


def _validate_note_filename(raw_title):
    name = (raw_title or "").strip()
    if not name:
        raise ValueError("Title is required.")
    if INVALID_TITLE_CHARS.search(name):
        raise ValueError("Title contains invalid filename characters.")
    if name.endswith(" ") or name.endswith("."):
        raise ValueError("Title cannot end with a space or period.")
    if "/" in name or "\\" in name:
        raise ValueError("Title must be a file name only.")
    return name


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
        norm_path = _normalize_note_path(path_prefix)
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
    full_path = os.path.join(folder_path, base_name)
    with open(full_path, "x", encoding="utf-8") as handle:
        handle.write(content)
    return base_name, full_path


def _create_note_file(folder_path, title, sidebar_label):
    folder_norm = _normalize_note_path(folder_path)
    folder_path = folder_norm or folder_path
    if not folder_path:
        raise ValueError("Missing folder path")
    os.makedirs(folder_path, exist_ok=True)
    raw_title = _validate_note_filename(title)
    root_name, ext = os.path.splitext(raw_title)
    file_name = raw_title if ext else f"{raw_title}.md"
    title_base = root_name if ext.lower() == ".md" else raw_title
    title_clean = _sanitize_title(title_base)
    created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = _note_template(title_clean, created_utc, sidebar_label)
    file_name, full_path = _write_note_file(folder_path, file_name, content)
    return {
        "file_name": file_name,
        "full_path": full_path,
        "folder_path": folder_path,
        "created_utc": created_utc,
        "title": title_clean,
    }


def _normalize_project(project):
    if project in ("any", "All", "all", "ALL", "spacer"):
        return None
    return project


def _normalize_folder_filter(folder_path):
    folder_path = (folder_path or "").strip()
    if not folder_path:
        return None
    return _normalize_note_path(folder_path) or folder_path


def _note_folder_match_expr():
    return "COALESCE(NULLIF(rtrim(replace(t.path, '/', '\\')), ''), df.folder_path)"


def _note_path_expr():
    return "rtrim(replace(t.path, '/', '\\'))"


def _derived_project_expr():
    folder_expr = _note_folder_match_expr()
    path_expr = _note_path_expr()
    best_prefix_len_expr = (
        "("
        "SELECT MAX(LENGTH(pf_len.path_prefix)) "
        "FROM lp_project_folders pf_len "
        "WHERE pf_len.is_enabled = 1 "
        "  AND pf_len.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf_len.path_prefix) || '%'"
        ")"
    )
    named_child_expr = (
        "("
        "SELECT pf.project_id "
        "FROM lp_project_folders pf "
        "LEFT JOIN lp_projects p ON p.project_id = pf.project_id "
        "WHERE pf.is_enabled = 1 "
        "  AND pf.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf.path_prefix) || '%' "
        "  AND instr(pf.project_id, '/') > 0 "
        f"  AND lower({path_expr}) LIKE '%' || lower(COALESCE(p.project_name, '')) || '%' "
        f"  AND LENGTH(pf.path_prefix) = {best_prefix_len_expr} "
        "ORDER BY LENGTH(pf.path_prefix) DESC, CASE pf.folder_role "
        "  WHEN 'default' THEN 0 "
        "  WHEN 'include' THEN 1 "
        "  WHEN 'output' THEN 2 "
        "  WHEN 'archive' THEN 3 "
        "  ELSE 9 END, pf.sort_order, "
        "  (LENGTH(pf.project_id) - LENGTH(REPLACE(pf.project_id, '/', ''))) ASC, "
        "  LENGTH(pf.project_id) ASC, pf.project_id, pf.path_prefix "
        "LIMIT 1"
        ")"
    )
    normal_expr = (
        "("
        "SELECT pf.project_id "
        "FROM lp_project_folders pf "
        "WHERE pf.is_enabled = 1 "
        "  AND pf.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf.path_prefix) || '%' "
        "ORDER BY LENGTH(pf.path_prefix) DESC, CASE pf.folder_role "
        "  WHEN 'default' THEN 0 "
        "  WHEN 'include' THEN 1 "
        "  WHEN 'output' THEN 2 "
        "  WHEN 'archive' THEN 3 "
        "  ELSE 9 END, pf.sort_order, "
        "  (LENGTH(pf.project_id) - LENGTH(REPLACE(pf.project_id, '/', ''))) ASC, "
        "  LENGTH(pf.project_id) ASC, pf.project_id, pf.path_prefix "
        "LIMIT 1"
        ")"
    )
    return f"COALESCE({named_child_expr}, {normal_expr})"


def _project_scope_ids(project):
    project = (project or "").strip()
    if not project or project.lower() == "unmapped":
        return []
    conn = data._get_conn()
    projects_mod.ensure_projects_schema(conn)
    project_lower = project.lower()
    ids = []

    exact = projects_mod.project_get(project, conn=conn)
    if exact:
        rows = conn.execute(
            "SELECT project_id FROM lp_projects "
            "WHERE status = 'active' "
            "AND (lower(project_id) = lower(?) OR lower(project_id) LIKE lower(?) || '/%') "
            "ORDER BY LENGTH(project_id), project_id",
            (project, project),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT project_id FROM lp_projects "
            "WHERE status = 'active' "
            "AND (lower(project_id) LIKE lower(?) || '/%' "
            "     OR lower(tab) = ? "
            "     OR lower(group_name) = ? "
            "     OR lower(project_id) = ?) "
            "ORDER BY LENGTH(project_id), project_id",
            (project, project_lower, project_lower, f"{project_lower}.{project_lower}.{project_lower}"),
        ).fetchall()

    for row in rows:
        project_id = (row["project_id"] or "").strip()
        if project_id and project_id not in ids:
            ids.append(project_id)
    return ids or [project]


def _notes_base_condition(project, folder_path=None):
    params = []
    folder_expr = _note_folder_match_expr()
    if project and project.lower() == "unmapped":
        condition = (
            "NOT EXISTS ("
            "  SELECT 1 FROM lp_project_folders pf "
            "  WHERE pf.is_enabled = 1 "
            "    AND pf.folder_role IN ('default','include','archive','output') "
            f"    AND {folder_expr} IS NOT NULL "
            f"    AND lower({folder_expr}) LIKE lower(pf.path_prefix) || '%'"
            ")"
        )
    elif project:
        scope_ids = _project_scope_ids(project)
        placeholders = ", ".join(["?"] * len(scope_ids))
        condition = f"{_derived_project_expr()} IN ({placeholders})"
        params.extend(scope_ids)
    else:
        condition = "1=1"
    if folder_path:
        condition = f"({condition}) AND lower(rtrim(replace(t.path, '/', '\\'))) = lower(?)"
        params.append(folder_path)
    return condition, params


def _count_notes(project, folder_path=None):
    tbl = get_table_def("notes")
    if not tbl:
        return 0
    projects_mod.ensure_projects_schema(data._get_conn())
    condition, params = _notes_base_condition(project, folder_path)
    row = data._get_conn().execute(
        f"SELECT COUNT(1) AS cnt FROM {tbl['name']} t "
        "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
        f"WHERE {condition}",
        params,
    ).fetchone()
    return row["cnt"] if row else 0


def _notes_url_args(project=None, folder_path=None, **extra):
    args = {}
    if project:
        args["proj"] = project
    if folder_path:
        args["folder"] = folder_path
    for key, value in extra.items():
        if value not in (None, "", False):
            args[key] = value
    return args


def _notes_root_path(project=None):
    tbl = get_table_def("notes")
    if not tbl:
        return None
    projects_mod.ensure_projects_schema(data._get_conn())
    condition, params = _notes_base_condition(project)
    sql = (
        f"SELECT rtrim(t.path) AS path "
        f"FROM {tbl['name']} t "
        "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
        f"WHERE {condition} "
        "AND lower(replace(t.path, '/', '\\')) LIKE '%\\data\\notes%' "
        "ORDER BY LENGTH(t.path) ASC "
        "LIMIT 1"
    )
    row = data._get_conn().execute(sql, params).fetchone()
    if not row:
        return None
    parts = [part for part in _normalize_folder_filter(row["path"]).split("\\") if part]
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            return "\\".join(parts[: idx + 2])
    return None


def _note_folder_breadcrumb(folder_path, project=None):
    folder_path = _normalize_folder_filter(folder_path)
    if not folder_path:
        root_path = _notes_root_path(project)
        if root_path:
            return [
                {
                    "label": "notes",
                    "url": url_for(
                        "notes.list_notes_table_route",
                        **_notes_url_args(folder_path=root_path),
                    ),
                }
            ]
        return [{"label": "notes", "url": url_for("notes.list_notes_table_route")}]
    parts = [part for part in folder_path.replace("/", "\\").split("\\") if part]
    root_idx = None
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            root_idx = idx + 1
            break
    if root_idx is None:
        return []

    root_parts = parts[: root_idx + 1]
    rel_parts = parts[root_idx + 1 :]
    current = "\\".join(root_parts)
    crumbs = [
        {
            "label": "notes",
            "url": url_for(
                "notes.list_notes_table_route",
                **_notes_url_args(folder_path=current),
            ),
        }
    ]
    for part in rel_parts:
        current = current + "\\" + part
        crumbs.append(
            {
                "label": part,
                "url": url_for(
                    "notes.list_notes_table_route",
                    **_notes_url_args(folder_path=current),
                ),
            }
        )
    return crumbs


def _path_prefix_value(folder_path):
    folder_path = _normalize_folder_filter(folder_path)
    if not folder_path:
        return None
    return folder_path + "\\%"


def _fetch_note_subfolders(project, folder_path=None):
    folder_path = _normalize_folder_filter(folder_path)
    if not folder_path:
        return []
    tbl = get_table_def("notes")
    if not tbl:
        return []
    projects_mod.ensure_projects_schema(data._get_conn())
    condition, params = _notes_base_condition(project)
    sql = (
        f"SELECT DISTINCT rtrim(t.path) AS path "
        f"FROM {tbl['name']} t "
        "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
        f"WHERE {condition} "
        "AND lower(rtrim(replace(t.path, '/', '\\'))) LIKE lower(?)"
    )
    params.append(_path_prefix_value(folder_path))
    rows = data._get_conn().execute(sql, params).fetchall()
    base = folder_path.rstrip("\\")
    base_lower = base.lower()
    subfolders = {}
    for row in rows:
        path = _normalize_folder_filter(row["path"])
        if not path or path.lower() == base_lower:
            continue
        prefix = base + "\\"
        if not path.lower().startswith(prefix.lower()):
            continue
        child = path[len(prefix) :].split("\\", 1)[0].strip()
        if not child:
            continue
        child_path = prefix + child
        subfolders[child.lower()] = {
            "label": child,
            "path": child_path,
            "url": url_for("notes.list_notes_table_route", **_notes_url_args(folder_path=child_path)),
        }
    return [subfolders[key] for key in sorted(subfolders)]


def _fetch_notes(project, sort_col=None, sort_dir=None, limit=None, offset=None, folder_path=None):
    tbl = get_table_def("notes")
    if not tbl:
        return []
    projects_mod.ensure_projects_schema(data._get_conn())
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
    select_cols.append(f"{_derived_project_expr()} as derived_project")
    condition, params = _notes_base_condition(project, folder_path)
    sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {tbl['name']} t "
        "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
        f"WHERE {condition} "
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



def _get_note_record(note_id):
    tbl = get_table_def("notes")
    if not tbl:
        return None, None
    rows = data.get_data(
        data.conn,
        tbl["name"],
        ["id"] + tbl["col_list"] + ["rec_extract_date as updated"],
        "id = ?",
        [note_id],
    )
    if not rows:
        return None, tbl
    note = dict(rows[0])
    note["updated"] = _parse_datetime(note.get("updated")) or datetime.now()
    return note, tbl

@notes_bp.route('/')
def list_notes_route():
    project = _normalize_project(request.args.get("proj"))
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    project_info, project_folders = _project_context(project)
    project_label = project_info["project_name"] if project_info else project
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
            project_info=project_info,
            project_folders=project_folders,
            project=project,
            folder_filter=folder_filter,
            note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
            note_subfolders=_fetch_note_subfolders(project, folder_filter),
            total_notes=0,
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
        return redirect(url_for(f"notes.list_notes_{view_pref}_route", **_notes_url_args(project, folder_filter)))
    sort_col = request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified"
    sort_dir = request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc"
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = _count_notes(project, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    route_name = "notes.list_notes_table_route"
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(project, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project_label or 'All'})",
        content_html="",
        notes=notes,
        project_info=project_info,
        project_folders=project_folders,
        project=project,
        folder_filter=folder_filter,
        note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
        note_subfolders=_fetch_note_subfolders(project, folder_filter),
        total_notes=total,
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
    project = _normalize_project(request.args.get("proj"))
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    project_info, project_folders = _project_context(project)
    project_label = project_info["project_name"] if project_info else project
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
            project_info=project_info,
            project_folders=project_folders,
            project=project,
            folder_filter=folder_filter,
            note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
            note_subfolders=_fetch_note_subfolders(project, folder_filter),
            total_notes=0,
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
    total = _count_notes(project, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    route_name = "notes.list_notes_table_route"
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(project, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project_label or 'All'})",
        content_html="",
        notes=notes,
        project_info=project_info,
        project_folders=project_folders,
        project=project,
        folder_filter=folder_filter,
        note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
        note_subfolders=_fetch_note_subfolders(project, folder_filter),
        total_notes=total,
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
    project = _normalize_project(request.args.get("proj"))
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    project_info, project_folders = _project_context(project)
    project_label = project_info["project_name"] if project_info else project
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
            project_info=project_info,
            project_folders=project_folders,
            project=project,
            folder_filter=folder_filter,
            note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
            note_subfolders=_fetch_note_subfolders(project, folder_filter),
            total_notes=0,
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_list_route"),
            last_url=url_for("notes.list_notes_list_route"),
        )
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = _count_notes(project, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "notes.list_notes_list_route",
        _notes_url_args(project, folder_filter),
        page,
        total_pages,
    )
    resp = make_response(
        render_template(
        "notes_list_list.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title=f"Notes ({project_label or 'All'})",
        content_html="",
        notes=notes,
        project_info=project_info,
        project_folders=project_folders,
        project=project,
        folder_filter=folder_filter,
        note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
        note_subfolders=_fetch_note_subfolders(project, folder_filter),
        total_notes=total,
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
    project = _normalize_project(request.args.get("proj"))
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    project_info, project_folders = _project_context(project)
    project_label = project_info["project_name"] if project_info else project
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
            project_info=project_info,
            project_folders=project_folders,
            project=project,
            folder_filter=folder_filter,
            note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
            note_subfolders=_fetch_note_subfolders(project, folder_filter),
            total_notes=0,
            note_card_bg=cfg.NOTE_CARD_DEF_BG_COL,
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for("notes.list_notes_cards_route"),
            last_url=url_for("notes.list_notes_cards_route"),
        )
    page = request.args.get("page", type=int) or 1
    per_page = cfg.RECS_PER_PAGE
    total = _count_notes(project, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(project, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        "notes.list_notes_cards_route",
        _notes_url_args(project, folder_filter),
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
        content_title=f"Notes ({project_label or 'All'})",
        content_html="",
        notes=notes,
        card_values=card_values,
        project_info=project_info,
        project_folders=project_folders,
        project=project,
        folder_filter=folder_filter,
        note_breadcrumb=_note_folder_breadcrumb(folder_filter, project),
        note_subfolders=_fetch_note_subfolders(project, folder_filter),
        total_notes=total,
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
    projects_mod.ensure_projects_schema(data._get_conn())
    if tbl:
        select_cols = [f"t.{col}" for col in (["id"] + tbl["col_list"])]
        select_cols.append("t.rec_extract_date as updated")
        select_cols.append(f"{_derived_project_expr()} as derived_project")
        sql = (
            f"SELECT {', '.join(select_cols)} "
            f"FROM {tbl['name']} t "
            "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
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
    note_folder = _normalize_folder_filter(note.get("path"))
    breadcrumb_project = note.get("derived_project") or note.get("project")
    file_exists = note_path and os.path.isfile(note_path)
    note_text = ""
    if file_exists:
        note_text = _read_note_file(note_path)
    content_html = ""
    hex_rows = []
    if render_mode == "markdown":
        def _asset_url(asset_name):
            return url_for("notes.note_asset_route", note_id=note_id, asset_path=asset_name)

        display_text = _without_duplicate_title_heading(note_text, note.get("file_name"))
        content_html = markdown_utils.render_markdown(display_text, asset_resolver=_asset_url)
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
        note_breadcrumb=_note_folder_breadcrumb(note_folder, breadcrumb_project),
        active_projects=projects_mod.projects_list_sidebar(),
        message=request.args.get("message", ""),
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


def _note_title_from_filename(file_name):
    stem, _ = os.path.splitext((file_name or "").strip())
    return stem or "Untitled"


def _unique_file_path(folder_path, file_name):
    candidate = os.path.join(folder_path, file_name)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(file_name)
    idx = 2
    while True:
        candidate = os.path.join(folder_path, f"{stem}_{idx}{ext}")
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def _safe_project_short_name(project_id):
    raw = (project_id or "note").strip().split("/")[-1].split(".")[-1]
    cleaned = INVALID_TITLE_CHARS.sub("", raw)
    cleaned = WHITESPACE_RE.sub("_", cleaned).strip("._ ")
    return cleaned or "note"


def _update_note_title_content(note_path, old_title, new_title):
    try:
        text = _read_note_file(note_path)
    except OSError:
        return
    if not text:
        return
    updated = text
    escaped_title = (new_title or "").replace('"', '\\"')
    if updated.startswith("---"):
        updated = re.sub(
            r'(?m)^title:\s*".*?"\s*$',
            f'title: "{escaped_title}"',
            updated,
            count=1,
        )
    lines = updated.splitlines(keepends=True)
    start_idx = 0
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                start_idx = idx + 1
                break
    for idx, line in enumerate(lines[start_idx:], start=start_idx):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^(#{1,6}\s+)(.+?)(\s*#*\s*)$", stripped)
        if match:
            current_title = match.group(2).strip()
            if current_title.lower() in {old_title.lower(), old_title.lower() + ".md"}:
                newline = "\n" if line.endswith("\n") else ""
                lines[idx] = f"{match.group(1)}{new_title}{match.group(3)}{newline}"
            updated = "".join(lines)
        break
    if updated != text:
        _write_note_file_content(note_path, updated)


def _update_note_file_metadata(note_id, note, file_name, folder_path, project=None):
    tbl = get_table_def("notes")
    if not tbl:
        return False
    note_path = os.path.join(folder_path, file_name)
    try:
        stat = os.stat(note_path)
        size = str(stat.st_size)
        date_modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        size = note.get("size") or ""
        date_modified = note.get("date_modified") or ""
    values_map = {col: note.get(col, "") for col in tbl["col_list"]}
    values_map.update(
        {
            "file_name": file_name,
            "path": folder_path,
            "size": size,
            "date_modified": date_modified,
        }
    )
    if project is not None:
        values_map["project"] = project
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    ok = data.update_record(data._get_conn(), tbl["name"], note_id, tbl["col_list"], values)
    if ok:
        _set_note_folder_id(data._get_conn(), tbl["name"], note_id, folder_path)
    return ok


def _rename_note(note_id, new_title):
    note, _ = _get_note_record(note_id)
    if not note:
        raise ValueError("Note not found.")
    note_path = _build_note_path(note)
    if not note_path or not os.path.isfile(note_path):
        raise ValueError("Note file not found.")
    title = _validate_note_filename(new_title)
    stem, ext = os.path.splitext(title)
    file_name = title if ext else f"{title}.md"
    if not file_name.lower().endswith(".md"):
        file_name += ".md"
    folder_path = _normalize_note_path(note.get("path"))
    target_path = os.path.join(folder_path, file_name)
    if os.path.exists(target_path) and os.path.abspath(target_path).lower() != os.path.abspath(note_path).lower():
        raise ValueError("A note with that name already exists in this folder.")
    old_title = _note_title_from_filename(note.get("file_name"))
    new_stem = _note_title_from_filename(file_name)
    if os.path.abspath(target_path).lower() != os.path.abspath(note_path).lower():
        os.replace(note_path, target_path)
    _update_note_title_content(target_path, old_title, new_stem)
    _update_note_file_metadata(note_id, note, file_name, folder_path)
    return file_name


def _move_note_to_project(note_id, project_id):
    note, _ = _get_note_record(note_id)
    if not note:
        raise ValueError("Note not found.")
    note_path = _build_note_path(note)
    if not note_path or not os.path.isfile(note_path):
        raise ValueError("Note file not found.")
    project_id = (project_id or "").strip()
    if not project_id:
        raise ValueError("Project is required.")
    target_folder = projects_mod.project_default_folder_get(project_id)
    if not target_folder:
        raise ValueError("Selected project has no default folder.")
    target_folder = _normalize_note_path(target_folder)
    os.makedirs(target_folder, exist_ok=True)
    file_name = note.get("file_name") or os.path.basename(note_path)
    source_folder = _normalize_note_path(note.get("path")) or os.path.dirname(note_path)
    if source_folder.lower() == target_folder.lower():
        target_path = os.path.join(target_folder, file_name)
    else:
        target_path = _unique_file_path(target_folder, file_name)
        shutil.move(note_path, target_path)
    moved_name = os.path.basename(target_path)
    _update_note_file_metadata(note_id, note, moved_name, target_folder, project=project_id)
    return target_path


def _derived_project_for_note_id(note_id):
    tbl = get_table_def("notes")
    if not tbl:
        return ""
    try:
        row = data._get_conn().execute(
            f"SELECT {_derived_project_expr()} AS derived_project "
            f"FROM {tbl['name']} t "
            "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
            "WHERE t.id = ?",
            (note_id,),
        ).fetchone()
    except Exception:
        return ""
    return (row["derived_project"] or "") if row else ""


def _archive_and_delete_note(note_id):
    note, tbl = _get_note_record(note_id)
    if not note or not tbl:
        raise ValueError("Note not found.")
    note_path = _build_note_path(note)
    archived_path = ""
    if note_path and os.path.isfile(note_path):
        note_folder = _normalize_note_path(note.get("path")) or os.path.dirname(note_path)
        notes_root = _notes_root_from_path(note_folder) or note_folder
        deleted_folder = os.path.join(notes_root, "deleted")
        os.makedirs(deleted_folder, exist_ok=True)
        project_id = note.get("project") or _derived_project_for_note_id(note_id)
        short_project = _safe_project_short_name(project_id)
        stem = _note_title_from_filename(note.get("file_name"))
        safe_stem = INVALID_TITLE_CHARS.sub("", stem)
        safe_stem = WHITESPACE_RE.sub("_", safe_stem).strip("._ ") or "note"
        stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        archive_name = f"{short_project}__{safe_stem}_{stamp}.md"
        archived_path = _unique_file_path(deleted_folder, archive_name)
        shutil.move(note_path, archived_path)
    data.delete_record(data._get_conn(), tbl["name"], note_id)
    return archived_path


def _open_note_folder(note):
    note_path = _build_note_path(note)
    folder_path = os.path.dirname(note_path) if note_path else _normalize_note_path(note.get("path"))
    if not folder_path or not os.path.isdir(folder_path):
        raise ValueError("Folder not found.")
    if sys.platform.startswith("win"):
        if note_path and os.path.isfile(note_path):
            subprocess.Popen(["explorer", f"/select,{note_path}"])
        else:
            os.startfile(folder_path)
    elif sys.platform == "darwin":
        if note_path and os.path.isfile(note_path):
            subprocess.Popen(["open", "-R", note_path])
        else:
            subprocess.Popen(["open", folder_path])
    else:
        subprocess.Popen(["xdg-open", folder_path])


@notes_bp.route('/rename/<int:note_id>', methods=["POST"])
def rename_note_route(note_id):
    try:
        _rename_note(note_id, request.form.get("new_title", ""))
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Rename failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id))


@notes_bp.route('/move/<int:note_id>', methods=["POST"])
def move_note_route(note_id):
    try:
        _move_note_to_project(note_id, request.form.get("project_id", ""))
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Move failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id))


@notes_bp.route('/archive-delete/<int:note_id>', methods=["POST"])
def archive_delete_note_route(note_id):
    try:
        _archive_and_delete_note(note_id)
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Delete failed: {exc}"))
    return redirect(url_for("notes.list_notes_route"))


@notes_bp.route('/open-folder/<int:note_id>', methods=["POST"])
def open_note_folder_route(note_id):
    note, _ = _get_note_record(note_id)
    if not note:
        abort(404)
    try:
        _open_note_folder(note)
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Open folder failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id))


@notes_bp.route('/api/new-note-options')
def new_note_options_route():
    project_id = (request.args.get("project_id") or request.args.get("proj") or "").strip()
    if not project_id:
        return jsonify({"error": "Project is required."}), 400
    project = projects_mod.project_get(project_id)
    if not project:
        return jsonify({"error": "Project not found."}), 404
    folders = projects_mod.project_folders_list(project_id, include_disabled=False)
    default_folder = None
    try:
        default_path = projects_mod.project_default_folder_get(project_id)
        if default_path:
            default_folder = {"path_prefix": default_path}
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({
        "project": project,
        "default_folder": default_folder,
        "folders": folders,
    })


@notes_bp.route('/api/create-note', methods=["POST"])
def create_note_route():
    payload = request.get_json(silent=True) or {}
    project_id = (payload.get("project_id") or "").strip()
    title = (payload.get("title") or "").strip()
    path_prefix = (payload.get("path_prefix") or "").strip()
    if not project_id:
        return jsonify({"error": "Project is required."}), 400
    if not projects_mod.project_get(project_id):
        return jsonify({"error": "Project not found."}), 404
    if not title:
        return jsonify({"error": "Title is required."}), 400
    try:
        default_path = projects_mod.project_default_folder_get(project_id) or ""
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    if not default_path:
        return jsonify({"error": "No default folder set for this project."}), 400
    if path_prefix:
        if _normalize_note_path(path_prefix).lower() != _normalize_note_path(default_path).lower():
            return jsonify({"error": "Notes can only be created in the default folder for this project."}), 400
    path_prefix = default_path
    if not path_prefix:
        return jsonify({"error": "Folder path is required."}), 400
    try:
        created = _create_note_file(path_prefix, title, project_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
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
        "project": project_id,
    }
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    note_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
    if not note_id:
        try:
            os.remove(created["full_path"])
        except Exception:
            pass
        return jsonify({"error": "Unable to insert note record."}), 500
    _set_note_folder_id(data._get_conn(), tbl["name"], note_id, created["folder_path"])
    return jsonify({
        "note_id": note_id,
        "file_name": created["file_name"],
        "path": created["folder_path"],
        "full_path": created["full_path"],
        "open_url": url_for("notes.edit_note_route", note_id=note_id),
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
    note, tbl = _get_note_record(note_id)
    if request.method == "POST":
        content = request.form.get("content")
        if content is not None and note:
            note_path = _build_note_path(note)
            if note_path and not os.path.isdir(note_path):
                try:
                    _write_note_file_content(note_path, content)
                except OSError:
                    pass
        return redirect(url_for("notes.edit_note_route", note_id=note_id))
    note_text = ""
    note_state = None
    note_path = _build_note_path(note) if note else ""
    file_exists = bool(note_path and os.path.isfile(note_path))
    if file_exists:
        note_text = _read_note_file(note_path)
        note_state = _note_file_state(note_path)
        if note_state:
            note["size"] = note_state["size"]
            note["date_modified"] = note_state["date_modified"]
    note_folder = _normalize_folder_filter(note.get("path")) if note else ""
    breadcrumb_project = note.get("derived_project") or note.get("project") if note else None
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        note_text=note_text,
        file_exists=file_exists,
        note_path=note_path,
        note_state=note_state,
        note_breadcrumb=_note_folder_breadcrumb(note_folder, breadcrumb_project),
        content_title=f"Edit: {note.get('file_name')}" if note else "Edit Note",
    )

@notes_bp.route('/api/save/<int:note_id>', methods=["POST"])
def save_note_route(note_id):
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    if content is None:
        return jsonify({"error": "Missing content."}), 400
    note, tbl = _get_note_record(note_id)
    if not note:
        return jsonify({"error": "Note not found."}), 404
    note_path = _build_note_path(note)
    if not note_path or os.path.isdir(note_path):
        return jsonify({"error": "Note path is invalid."}), 400
    base_mtime_ns = payload.get("base_mtime_ns")
    base_hash = payload.get("base_hash") or ""
    current_state = _note_file_state(note_path)
    if base_mtime_ns not in (None, ""):
        if not current_state or str(current_state.get("mtime_ns")) != str(base_mtime_ns):
            if base_hash and current_state and current_state.get("sha256") == base_hash:
                pass
            else:
                return jsonify({
                    "error": "The note changed on disk after this editor loaded. Reload before saving to avoid overwriting another edit.",
                    "conflict": True,
                    "size": current_state.get("size") if current_state else "",
                    "date_modified": current_state.get("date_modified") if current_state else "",
                    "mtime_ns": current_state.get("mtime_ns") if current_state else "",
                    "sha256": current_state.get("sha256") if current_state else "",
                }), 409
    try:
        saved_state = _write_note_file_content(note_path, content)
    except OSError as exc:
        return jsonify({"error": f"Unable to save note: {exc}"}), 500
    if saved_state:
        size = saved_state["size"]
        date_modified = saved_state["date_modified"]
        mtime_ns = saved_state["mtime_ns"]
        sha256 = saved_state["sha256"]
    else:
        size = note.get("size") or ""
        date_modified = note.get("date_modified") or ""
        mtime_ns = ""
        sha256 = ""

    if tbl:
        values_map = {col: note.get(col, "") for col in tbl["col_list"]}
        if "size" in values_map:
            values_map["size"] = size
        if "date_modified" in values_map:
            values_map["date_modified"] = date_modified
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        data.update_record(data.conn, tbl["name"], note_id, tbl["col_list"], values)

    return jsonify({
        "ok": True,
        "size": size,
        "date_modified": date_modified,
        "mtime_ns": mtime_ns,
        "sha256": sha256,
    })

@notes_bp.route('/delete/<int:note_id>')
def delete_note_route(note_id):
    try:
        _archive_and_delete_note(note_id)
    except Exception:
        pass
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
    project = _normalize_project_param(request.args.get("proj") or "")
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
            rows = _collect_note_import_rows(folder_path, project)
            imported = _insert_note_import_rows(tbl, rows)
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


def _collect_note_import_rows(folder_path, project):
    rows = []
    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            full_path = os.path.join(root, name)
            if not os.path.isfile(full_path):
                continue
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            rows.append(
                {
                    "file_name": name,
                    "path": root,
                    "size": str(stat.st_size),
                    "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "project": project,
                }
            )
    return rows


def _insert_note_import_rows(tbl, rows):
    count = 0
    conn = data._get_conn()
    for values_map in rows:
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        record_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        if record_id:
            _set_note_folder_id(conn, tbl["name"], record_id, values_map.get("path", ""))
            count += 1
    return count


def _note_full_path_key(folder_path, file_name):
    folder_path = _normalize_note_path(folder_path)
    file_name = (file_name or "").strip()
    if not folder_path or not file_name:
        return ""
    return os.path.join(folder_path, file_name).replace("/", "\\").lower()


def _note_folder_id_matches(conn, folder_id, folder_path):
    if folder_id in (None, "", "0", 0):
        return False
    try:
        row = conn.execute(
            "SELECT folder_path FROM dim_folder WHERE folder_id = ?",
            (folder_id,),
        ).fetchone()
    except Exception:
        return False
    if not row:
        return False
    return _normalize_note_path(row["folder_path"]).lower() == _normalize_note_path(folder_path).lower()


def _sync_note_rows(folder_path):
    folder_path = _normalize_note_path(folder_path)
    tbl = get_table_def("notes")
    if not tbl:
        raise ValueError("Notes table not found.")
    if not folder_path:
        raise ValueError("No folder provided.")
    if not os.path.isdir(folder_path):
        raise ValueError("Folder not found.")

    conn = data._get_conn()
    root_lower = folder_path.rstrip("\\").lower()
    existing = {}
    duplicates = 0
    rows = conn.execute(
        f"SELECT id, {', '.join(tbl['col_list'])} FROM {tbl['name']} "
        "WHERE COALESCE(path, '') != ''"
    ).fetchall()
    for row in rows:
        row_dict = dict(row)
        row_path = _normalize_note_path(row_dict.get("path"))
        if not row_path:
            continue
        row_path_lower = row_path.lower()
        if row_path_lower != root_lower and not row_path_lower.startswith(root_lower + "\\"):
            continue
        key = _note_full_path_key(row_path, row_dict.get("file_name"))
        if not key:
            continue
        if key in existing:
            duplicates += 1
            continue
        existing[key] = row_dict

    scanned = inserted = updated = unchanged = 0
    seen = set()
    for root, _, files in os.walk(folder_path):
        root_norm = _normalize_note_path(root)
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            full_path = os.path.join(root_norm, name)
            if not os.path.isfile(full_path):
                continue
            try:
                stat = os.stat(full_path)
            except OSError:
                continue
            scanned += 1
            size = str(stat.st_size)
            date_modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            key = _note_full_path_key(root_norm, name)
            seen.add(key)
            current = existing.get(key)
            if current:
                values_map = {col: current.get(col, "") for col in tbl["col_list"]}
                values_map.update(
                    {
                        "file_name": name,
                        "path": root_norm,
                        "size": size,
                        "date_modified": date_modified,
                    }
                )
                needs_update = (
                    (current.get("file_name") or "") != name
                    or _normalize_note_path(current.get("path")).lower() != root_norm.lower()
                    or str(current.get("size") or "") != size
                    or str(current.get("date_modified") or "") != date_modified
                    or not _note_folder_id_matches(conn, current.get("folder_id"), root_norm)
                )
                if needs_update:
                    values = [values_map.get(col, "") for col in tbl["col_list"]]
                    if data.update_record(conn, tbl["name"], current["id"], tbl["col_list"], values):
                        _set_note_folder_id(conn, tbl["name"], current["id"], root_norm)
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    unchanged += 1
            else:
                values_map = {
                    "file_name": name,
                    "path": root_norm,
                    "folder_id": "",
                    "size": size,
                    "date_modified": date_modified,
                    "project": "",
                }
                values = [values_map.get(col, "") for col in tbl["col_list"]]
                record_id = data.add_record(conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    _set_note_folder_id(conn, tbl["name"], record_id, root_norm)
                    inserted += 1

    missing = len([key for key in existing.keys() if key not in seen])
    return {
        "folder_path": folder_path,
        "scanned": scanned,
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "missing": missing,
        "duplicates": duplicates,
    }


def _sync_notes_message(result):
    return (
        f"Synced notes folder {result['folder_path']}: scanned {result['scanned']}, "
        f"inserted {result['inserted']}, updated {result['updated']}, "
        f"unchanged {result['unchanged']}, missing on disk {result['missing']}, "
        f"duplicate DB rows ignored {result['duplicates']}."
    )


@notes_bp.route('/sync', methods=["POST"])
def sync_notes_route():
    folder_path = request.form.get("notes_folder", "").strip()
    if not folder_path:
        folder_path = _notes_root_path() or ""
    try:
        result = _sync_note_rows(folder_path)
        msg = _sync_notes_message(result)
    except Exception as exc:
        msg = f"Notes sync failed: {exc}"
    return redirect(url_for("admin.settings_route", tab="notes", message=msg))


@notes_bp.route('/sync-folder/<int:project_folder_id>', methods=["POST"])
def sync_project_folder_route(project_folder_id):
    folder = projects_mod.project_folder_get(project_folder_id)
    if not folder:
        abort(404)
    try:
        result = _sync_note_rows(folder.get("path_prefix") or "")
        msg = _sync_notes_message(result)
    except Exception as exc:
        msg = f"Notes folder sync failed: {exc}"
    next_url = request.form.get("next") or url_for("notes.list_notes_route", proj=folder.get("project_id"))
    sep = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{sep}{urlencode({'message': msg})}")


def _upsert_note_dim_folder(conn, folder_path):
    folder_path = _normalize_note_path(folder_path)
    if not folder_path:
        return None
    conn.execute("INSERT OR IGNORE INTO dim_folder(folder_path) VALUES (?)", (folder_path,))
    conn.execute(
        "UPDATE dim_folder SET last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), is_active=1 WHERE folder_path=?",
        (folder_path,),
    )
    row = conn.execute("SELECT folder_id FROM dim_folder WHERE folder_path = ?", (folder_path,)).fetchone()
    return row["folder_id"] if row else None


def _set_note_folder_id(conn, tbl_name, record_id, folder_path):
    folder_id = _upsert_note_dim_folder(conn, folder_path)
    if not folder_id:
        return
    conn.execute(f"UPDATE {tbl_name} SET folder_id = ? WHERE id = ?", (folder_id, record_id))
    conn.commit()


def _count_note_links(conn):
    if not _table_exists(conn, "lp_links"):
        return 0
    row = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_links "
        "WHERE lower(src_type) IN ('note', 'notes') OR lower(dst_type) IN ('note', 'notes')"
    ).fetchone()
    return row["cnt"] if row else 0


def _delete_note_links(conn):
    if not _table_exists(conn, "lp_links"):
        return 0
    cur = conn.execute(
        "DELETE FROM lp_links "
        "WHERE lower(src_type) IN ('note', 'notes') OR lower(dst_type) IN ('note', 'notes')"
    )
    return cur.rowcount if cur.rowcount is not None else 0


def _clear_notes_table(conn, tbl_name):
    if not _table_exists(conn, tbl_name):
        return 0
    row = conn.execute(f"SELECT COUNT(1) AS cnt FROM {tbl_name}").fetchone()
    before_count = row["cnt"] if row else 0
    conn.execute(f"DELETE FROM {tbl_name}")
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (tbl_name,))
    except Exception:
        pass
    return before_count


def _current_note_roots(conn, tbl_name):
    roots = set()
    if not _table_exists(conn, tbl_name):
        return []
    for row in conn.execute(f"SELECT DISTINCT path FROM {tbl_name} WHERE COALESCE(path, '') != ''").fetchall():
        root = _notes_root_from_path(row["path"])
        if root:
            roots.add(root)
    return sorted(roots)


def _rewrite_lp_project_folder_paths(conn, old_root, new_root):
    if not _table_exists(conn, "lp_project_folders"):
        return 0
    updated = 0
    rows = conn.execute(
        "SELECT project_folder_id, project_id, path_prefix FROM lp_project_folders "
        "WHERE lower(path_prefix) = lower(?) OR lower(path_prefix) LIKE lower(?)",
        (_normalize_note_path(old_root), _normalize_note_path(old_root) + "\\%"),
    ).fetchall()
    for row in rows:
        next_path = _replace_path_prefix(row["path_prefix"], old_root, new_root)
        if not next_path or next_path.lower() == (row["path_prefix"] or "").lower():
            continue
        try:
            conn.execute(
                "UPDATE lp_project_folders SET path_prefix = ?, updated_utc = ? WHERE project_folder_id = ?",
                (next_path, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), row["project_folder_id"]),
            )
            updated += 1
        except Exception:
            conflict = conn.execute(
                "SELECT project_folder_id FROM lp_project_folders WHERE project_id = ? AND path_prefix = ?",
                (row["project_id"], next_path),
            ).fetchone()
            if conflict:
                conn.execute(
                    "DELETE FROM lp_project_folders WHERE project_folder_id = ?",
                    (row["project_folder_id"],),
                )
                updated += 1
    return updated


def _rewrite_map_folder_project_paths(conn, old_root, new_root):
    if not _table_exists(conn, "map_folder_project"):
        return 0
    updated = 0
    rows = conn.execute(
        "SELECT map_id, path_prefix, tab, grp, project, is_primary FROM map_folder_project "
        "WHERE lower(path_prefix) = lower(?) OR lower(path_prefix) LIKE lower(?)",
        (_normalize_note_path(old_root), _normalize_note_path(old_root) + "\\%"),
    ).fetchall()
    for row in rows:
        next_path = _replace_path_prefix(row["path_prefix"], old_root, new_root)
        if not next_path or next_path.lower() == (row["path_prefix"] or "").lower():
            continue
        try:
            conn.execute(
                "UPDATE map_folder_project SET path_prefix = ? WHERE map_id = ?",
                (next_path, row["map_id"]),
            )
            updated += 1
        except Exception:
            conflict = conn.execute(
                "SELECT map_id FROM map_folder_project "
                "WHERE path_prefix = ? AND tab = ? AND grp = ? AND project = ? AND is_primary = ?",
                (next_path, row["tab"], row["grp"], row["project"], row["is_primary"]),
            ).fetchone()
            if conflict:
                conn.execute("DELETE FROM map_folder_project WHERE map_id = ?", (row["map_id"],))
                updated += 1
    return updated


def _migrate_notes_mapping_roots(conn, new_root, old_roots):
    new_root = _normalize_note_path(new_root)
    rewritten = 0
    candidate_roots = set()
    for root in old_roots or []:
        root = _normalize_note_path(root)
        if root and root.lower() != new_root.lower():
            candidate_roots.add(root)
    for alias_root in _alias_counterpart_roots(new_root):
        alias_notes_root = _notes_root_from_path(alias_root) or alias_root
        if alias_notes_root.lower() != new_root.lower():
            candidate_roots.add(alias_notes_root)
    for old_root in sorted(candidate_roots, key=len, reverse=True):
        rewritten += _rewrite_lp_project_folder_paths(conn, old_root, new_root)
        rewritten += _rewrite_map_folder_project_paths(conn, old_root, new_root)
    try:
        rewritten += folder_etl.rebuild_map_project_folder(conn)
    except Exception:
        pass
    return rewritten


@notes_bp.route('/migrate-source', methods=["POST"])
def migrate_notes_source_route():
    folder_path = request.form.get("notes_folder", "").strip()
    folder_path = _normalize_note_path(folder_path)
    project = _normalize_project_param(request.form.get("project", ""))
    confirmed = request.form.get("confirm_migrate") == "1"
    tbl = get_table_def("notes")
    if not confirmed:
        msg = "Migration not run: confirmation checkbox is required."
    elif not folder_path:
        msg = "Migration not run: no notes folder provided."
    elif not os.path.isdir(folder_path):
        msg = "Migration not run: folder not found."
    elif not tbl:
        msg = "Migration not run: notes table not found."
    else:
        rows = _collect_note_import_rows(folder_path, project)
        if not rows:
            msg = "Migration not run: no markdown files found in the selected folder."
        else:
            conn = data._get_conn()
            new_root = _notes_root_from_path(folder_path) or folder_path
            old_roots = _current_note_roots(conn, tbl["name"])
            notes_before = conn.execute(f"SELECT COUNT(1) AS cnt FROM {tbl['name']}").fetchone()["cnt"]
            links_before = _count_note_links(conn)
            links_deleted = _delete_note_links(conn)
            notes_deleted = _clear_notes_table(conn, tbl["name"])
            mappings_rewritten = _migrate_notes_mapping_roots(conn, new_root, old_roots)
            conn.commit()
            imported = _insert_note_import_rows(tbl, rows)
            lg_usr(
                action="notes_migrate_source",
                entity_type=tbl["name"],
                before={"notes": notes_before, "note_links": links_before},
                after={"notes": imported, "note_links": 0},
                context_type="notes_migrate_source",
                context_id=folder_path,
                extra={
                    "folder_path": folder_path,
                    "project": project,
                    "notes_deleted": notes_deleted,
                    "note_links_deleted": links_deleted,
                    "notes_imported": imported,
                    "mappings_rewritten": mappings_rewritten,
                },
                conn=conn,
            )
            msg = (
                f"Migrated notes source. Deleted {notes_deleted} old notes and "
                f"{links_deleted} note links, updated {mappings_rewritten} folder mappings, "
                f"then imported {imported} notes."
            )
    return redirect(url_for("admin.settings_route", tab="notes", message=msg))


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


def _project_context(project_id):
    if not project_id or project_id.lower() == "unmapped":
        return None, []
    project = projects_mod.project_get(project_id)
    if not project:
        return None, []
    folders = projects_mod.project_folders_list(project_id, include_disabled=True)
    return project, folders


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


def _without_duplicate_title_heading(note_text, file_name):
    title = (file_name or "").strip()
    if not title:
        return note_text
    title_stem, _ = os.path.splitext(title)
    title_values = {title.lower()}
    if title_stem:
        title_values.add(title_stem.lower())
    lines = note_text.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", stripped)
        if not match:
            return note_text
        heading = match.group(1).strip().lower()
        if heading in title_values:
            return "".join(lines[:idx] + lines[idx + 1 :])
        return note_text
    return note_text


def _note_file_state(note_path):
    try:
        stat = os.stat(note_path)
        digest = hashlib.sha256()
        with open(note_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return {
        "size": str(stat.st_size),
        "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


def _write_note_file_content(note_path, content):
    dir_name = os.path.dirname(note_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    temp_dir = dir_name or "."
    base_name = os.path.basename(note_path) or "note"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=temp_dir,
            prefix=f".{base_name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = handle.name
            handle.write(content)
        os.replace(temp_path, note_path)
        return _note_file_state(note_path)
    except OSError:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise


def _parse_size(value):
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
