import os
import re
import hashlib
import shutil
import subprocess
import sys
import tempfile
from difflib import SequenceMatcher
from datetime import datetime, timezone
from urllib.parse import urlencode, unquote

from flask import Blueprint, render_template, request, redirect, url_for, make_response, send_file, abort, jsonify
from flask_login import current_user

from common import data
from common import note_search_index
from common import settings as settings_mod
from utils import importer
from utils import markdown_utils
from utils import hex_utils
from common.utils import (
    get_tabs,
    get_side_tabs,
    get_table_def,
    paginate_total,
    build_pagination,
    lg_usr,
    normalize_area_param as utils_normalize_area_param,
    request_area_param,
)
from common import config as cfg
from common import areas as areas_mod
from common import projects as projects_mod
from common import collections as collections_mod
from common import user_paths
from core import security
from modules.how import service as how_service

notes_bp = Blueprint("notes", __name__, url_prefix="/notes",
                     template_folder='templates', static_folder='static')

INVALID_TITLE_CHARS = re.compile(r'[<>:"/\\|?*]')
WHITESPACE_RE = re.compile(r"\s+")
NOTE_TITLE_MAX_LEN = 80
NOTE_FRONT_MATTER_READ_LIMIT = 128 * 1024
DEFAULT_NOTE_COLOR = "#FFF7CC"
NOTES_PER_PAGE = 50
NOTE_CARD_MAX_CHARS = 50
NOTE_CARD_TITLE_FONT_SIZE = 18
NOTE_CARD_PREVIEW_CHARS = 300
NOTE_CARD_DEFAULT_MODE = "grid"
NOTE_COLOR_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
NOTE_COLOR_NAMES = {
    "yellow": "#ffff93",
    "aqua": "#ccffee",
    "blue": "#81ecec",
    "green": "#b8e994",
    "orange": "#eccc68",
    "red": "#fab1a0",
    "pink": "#ff9ff3",
    "purple": "#e056fd",
    "brown": "#deb887",
    "grey": "#dfe6e9",
    "gray": "#dfe6e9",
    "white": "#f1f2f6",
}
NOTE_COLOR_OPTIONS = [
    ("Yellow", NOTE_COLOR_NAMES["yellow"]),
    ("Aqua", NOTE_COLOR_NAMES["aqua"]),
    ("Blue", NOTE_COLOR_NAMES["blue"]),
    ("Green", NOTE_COLOR_NAMES["green"]),
    ("Orange", NOTE_COLOR_NAMES["orange"]),
    ("Red", NOTE_COLOR_NAMES["red"]),
    ("Pink", NOTE_COLOR_NAMES["pink"]),
    ("Purple", NOTE_COLOR_NAMES["purple"]),
    ("Brown", NOTE_COLOR_NAMES["brown"]),
    ("Grey", NOTE_COLOR_NAMES["grey"]),
    ("White", NOTE_COLOR_NAMES["white"]),
]
NOTE_VIEW_MODES = {"text", "markdown", "hex", "sample", "metadata"}
NOTE_WIKI_LINK_RE = re.compile(r"(?<!!)\[\[([^\]\n]+)\]\]")
NOTE_WIKI_TARGET_ID_RE = re.compile(r"(?i)^note:(\d+)$")
NOTE_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")
NOTE_LIST_SORT_OPTIONS = [
    ("title", "Title"),
    ("size", "Size"),
    ("color", "Color"),
    ("area", "Area"),
    ("date_created", "Date Created"),
    ("date_modified", "Date Modified"),
    ("folder", "Folder"),
]
NOTE_LIST_VIEW_OPTIONS = [
    ("list", "List"),
    ("table", "Table"),
    ("grid", "Grid"),
    ("preview", "Preview"),
    ("collections", "Notebooks"),
    ("names", "Names only"),
]
NOTE_TABLE_SORT_COLUMNS = [
    ("filename", "Filename", "title"),
    ("color", "Color", "color"),
    ("area", "Area", "area"),
    ("size", "Size", "size"),
    ("date_created", "Date Created", "date_created"),
    ("date_modified", "Date Modified", "date_modified"),
]
_NOTE_AREA_MATERIALIZED_KEYS = set()
NOTE_ATTACHMENT_FOLDER = os.path.join("00-META", "08-Attachments")
NOTE_LEGACY_IMAGE_FOLDERS = [
    NOTE_ATTACHMENT_FOLDER,
    os.path.join("_img", "orig_lifepim"),
]
NOTE_IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


def _ensure_notes_schema(conn=None):
    conn = data._get_conn() if conn is None else conn
    try:
        data.ensure_notes_schema(conn)
        _ensure_note_links_schema(conn)
        _ensure_note_areas_materialized(conn)
    except Exception:
        pass


def _ensure_note_links_schema(conn=None):
    conn = data._get_conn() if conn is None else conn
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lp_note_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            src_note_id INTEGER NOT NULL,
            target_note_id INTEGER NOT NULL,
            link_text TEXT NOT NULL,
            link_title TEXT,
            created_utc TEXT NOT NULL,
            updated_utc TEXT NOT NULL,
            UNIQUE (src_note_id, target_note_id, link_text)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_note_links_src ON lp_note_links(src_note_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_note_links_target ON lp_note_links(target_note_id)")
    conn.commit()


def _file_created_at(stat):
    created = getattr(stat, "st_birthtime", None)
    if created is None:
        created = getattr(stat, "st_ctime", None)
    if created is None:
        return ""
    return datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")


def _strip_front_matter_scalar(value):
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _try_read_note_front_matter(note_path):
    if not note_path:
        return None
    try:
        with open(note_path, "r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read(NOTE_FRONT_MATTER_READ_LIMIT)
    except OSError:
        return None
    return _parse_note_front_matter_text(text)


def _read_note_front_matter(note_path):
    return _try_read_note_front_matter(note_path) or {}


def _parse_note_front_matter_text(text):
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in ("---", "..."):
            break
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        if key:
            values[key] = _strip_front_matter_scalar(raw_value)
    return values


def _front_matter_block_text(text):
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for idx, line in enumerate(lines[1:], 1):
        if line.strip() in ("---", "..."):
            return "\n".join(lines[: idx + 1])
    return ""


def _front_matter_scalar_text(value):
    value = str(value or "").strip()
    if not value:
        return '""'
    if value.startswith("#") or any(ch in value for ch in ('"', "'", ":", "\r", "\n")):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _set_note_front_matter_field(note_path, key, value, aliases=None):
    aliases = {key.lower(), *{alias.lower() for alias in (aliases or [])}}
    text = _read_note_file(note_path)
    value_line = f"{key}: {_front_matter_scalar_text(value)}\n"
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        end_idx = None
        for idx, line in enumerate(lines[1:], 1):
            if line.strip() in ("---", "..."):
                end_idx = idx
                break
        if end_idx is not None:
            for idx in range(1, end_idx):
                if ":" not in lines[idx]:
                    continue
                field_name = lines[idx].split(":", 1)[0].strip().lower().replace(" ", "_")
                if field_name in aliases:
                    newline = "\r\n" if lines[idx].endswith("\r\n") else "\n"
                    lines[idx] = value_line.rstrip("\n") + newline
                    return _write_note_file_content(note_path, "".join(lines))
            lines.insert(end_idx, value_line)
            return _write_note_file_content(note_path, "".join(lines))
    updated = "---\n" + value_line + "---\n\n" + text
    return _write_note_file_content(note_path, updated)


def _front_matter_value(front_matter, keys):
    for key in keys:
        value = front_matter.get(key)
        if value not in (None, ""):
            return value
    return ""


def _front_matter_bool_text(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return "true"
    if normalized in {"0", "false", "no", "n", "off"}:
        return "false"
    return ""


def _note_color_style(value):
    color = (value or "").strip()
    if NOTE_COLOR_HEX_RE.match(color):
        return color
    return NOTE_COLOR_NAMES.get(color.lower(), "")


def _apply_note_display_fields(note):
    if note is not None:
        note["color_style"] = _note_color_style(note.get("color"))
        note["list_color_style"] = note["color_style"] or NOTE_COLOR_NAMES["yellow"]
    return note


def _note_color_options(current_color=""):
    options = [
        {"value": label, "label": label, "style": style}
        for label, style in NOTE_COLOR_OPTIONS
    ]
    current = (current_color or "").strip()
    if current and not any(option["value"].lower() == current.lower() for option in options):
        current_style = _note_color_style(current)
        if current_style:
            options.insert(0, {"value": current, "label": current, "style": current_style})
    return options


def _normalize_note_view_mode(value):
    value = (value or "").strip().lower()
    if value in {"md", "rendered"}:
        value = "markdown"
    return value if value in NOTE_VIEW_MODES else "markdown"


def _sample_note_text(note_text, sample_lines):
    lines = (note_text or "").splitlines()
    line_count = len(lines)
    sample_lines = settings_mod.normalize_note_sample_lines(sample_lines)
    if line_count <= sample_lines * 2:
        return note_text or ""
    omitted = line_count - (sample_lines * 2)
    sample = lines[:sample_lines]
    sample.extend(["", f"... {omitted} lines omitted ...", ""])
    sample.extend(lines[-sample_lines:])
    return "\n".join(sample)


def _note_metadata_rows(note, note_path, file_exists):
    updated = note.get("updated")
    if hasattr(updated, "strftime"):
        updated = updated.strftime("%Y-%m-%d %H:%M")
    return [
        ("File", note.get("file_name") or ""),
        ("Full path", note_path or ""),
        ("Folder", note.get("path") or ""),
        ("Folder ID", note.get("folder_id") or ""),
        ("File exists", "Yes" if file_exists else "No"),
        ("Size", note.get("size") or ""),
        ("Title", note.get("title") or ""),
        ("Color", note.get("color") or ""),
        ("Date created", note.get("date_created") or ""),
        ("Date modified", note.get("date_modified") or ""),
        ("Area", note.get("area") or ""),
        ("Derived area", note.get("derived_area") or ""),
        ("Important", note.get("important") or ""),
        ("Source note ID", note.get("source_note_id") or ""),
        ("Updated", updated or ""),
    ]


def _note_metadata_from_file(note_path, stat=None, fallback_area=""):
    file_name = os.path.basename(note_path or "")
    title_from_file, _ = os.path.splitext(file_name)
    front_matter = _read_note_front_matter(note_path)
    if stat is None and note_path:
        try:
            stat = os.stat(note_path)
        except OSError:
            stat = None
    date_modified = (
        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if stat is not None
        else ""
    )
    date_created = _front_matter_value(
        front_matter,
        ("date_created", "created", "created_at", "created_utc", "file_created_at", "birthtime"),
    )
    if not date_created and stat is not None:
        date_created = _file_created_at(stat)
    area = _front_matter_value(
        front_matter,
        ("area", "area_id", "folder", "sidebar_tab", "project", "project_id", "proj"),
    ) or fallback_area
    area = utils_normalize_area_param(area)
    if area.lower() in {"all", "all notes", "all areas", "all projects", "untitled"}:
        area = ""
    return {
        "title": _front_matter_value(front_matter, ("title", "name")) or title_from_file,
        "color": _front_matter_value(front_matter, ("color", "colour")),
        "date_created": date_created,
        "date_modified": date_modified,
        "area": area,
        "important": _front_matter_bool_text(_front_matter_value(front_matter, ("important", "is_important"))),
        "source_note_id": _front_matter_value(front_matter, ("source_note_id", "lifepim_com_note_id", "note_id")),
    }


def _normalize_area_param(area):
    return utils_normalize_area_param(area)


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


def _note_allowed_asset_roots(note, note_path=None):
    note_path = note_path or _build_note_path(note)
    base_dir = os.path.dirname(note_path) if note_path else ""
    roots = []
    if base_dir:
        roots.append(os.path.abspath(base_dir))
    notes_root = _notes_root_from_path(note_path or note.get("path") or "")
    if not notes_root:
        notes_root = _notes_root_path(note.get("area") or note.get("derived_area"), create_dirs=False) or ""
    if notes_root:
        roots.append(os.path.abspath(notes_root))
    seen = set()
    unique_roots = []
    for root in roots:
        key = os.path.normcase(root)
        if key and key not in seen:
            seen.add(key)
            unique_roots.append(root)
    return unique_roots


def _path_is_within(path_value, root):
    try:
        return os.path.commonpath([os.path.abspath(path_value), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def _resolve_note_asset_path(note, asset_path, note_path=None):
    asset_path = (asset_path or "").replace("\\", os.sep).replace("/", os.sep).strip()
    if not asset_path or os.path.isabs(asset_path) or "\x00" in asset_path:
        return ""
    normalized_asset = os.path.normpath(asset_path)
    if normalized_asset == "." or normalized_asset.startswith(".." + os.sep) or normalized_asset == "..":
        return ""

    roots = _note_allowed_asset_roots(note, note_path=note_path)
    notes_root = _notes_root_from_path(note_path or note.get("path") or "")
    if not notes_root:
        notes_root = _notes_root_path(note.get("area") or note.get("derived_area"), create_dirs=False) or ""
    notes_root = os.path.abspath(notes_root) if notes_root else ""
    candidates = []

    def add_candidate(root, *parts):
        if not root:
            return
        full_path = os.path.abspath(os.path.join(root, *parts))
        if _path_is_within(full_path, root) and full_path not in candidates:
            candidates.append(full_path)

    if roots:
        add_candidate(roots[0], normalized_asset)

    media_basename = os.path.basename(normalized_asset)
    has_folder = os.sep in normalized_asset
    if media_basename and not has_folder and notes_root:
        for folder in NOTE_LEGACY_IMAGE_FOLDERS:
            add_candidate(notes_root, folder, media_basename)

    for root in roots[1:]:
        full_path = os.path.abspath(os.path.join(root, normalized_asset))
        if _path_is_within(full_path, root):
            candidates.append(full_path)

    if normalized_asset.lower().startswith("media" + os.sep) and media_basename and roots:
        add_candidate(roots[0], media_basename)

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


def _safe_note_attachment_filename(filename):
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")
    if not stem:
        stem = "image"
    stem = stem[:80]
    if ext not in NOTE_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image type.")
    return stem + ext


def _unique_attachment_path(folder_path, filename):
    candidate = os.path.join(folder_path, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    index = 2
    while True:
        candidate = os.path.join(folder_path, f"{stem}-{index}{ext}")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _note_attachment_target(note, note_path=None):
    note_path = note_path or _build_note_path(note)
    base_dir = os.path.dirname(note_path) if note_path else ""
    notes_root = _notes_root_from_path(note_path or note.get("path") or "")
    if notes_root:
        return os.path.join(notes_root, NOTE_ATTACHMENT_FOLDER), NOTE_ATTACHMENT_FOLDER.replace("\\", "/")
    if base_dir:
        return os.path.join(base_dir, "attachments"), "attachments"
    return "", ""


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


def _note_template(title, created_utc, sidebar_label):
    title_value = (title or "").replace("\n", " ").replace("\r", " ").strip()
    escaped_title = title_value.replace('"', '\\"')
    area_value = (sidebar_label or "").replace("\n", " ").replace("\r", " ").strip()
    lines = [
        "---",
        f'title: "{escaped_title}"',
        f"color: {DEFAULT_NOTE_COLOR}",
        f"area: {area_value}",
        f"date_created: {created_utc}",
        f"date_modified: {created_utc}",
    ]
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
    created_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    content = _note_template(title_clean, created_utc, sidebar_label)
    file_name, full_path = _write_note_file(folder_path, file_name, content)
    return {
        "file_name": file_name,
        "full_path": full_path,
        "folder_path": folder_path,
        "created_utc": created_utc,
        "title": title_clean,
    }


def _normalize_area(area):
    return utils_normalize_area_param(area) or None


def _normalize_folder_filter(folder_path):
    folder_path = (folder_path or "").strip()
    if not folder_path:
        return None
    return _normalize_note_path(folder_path) or folder_path


def _note_folder_match_expr():
    return "COALESCE(NULLIF(rtrim(replace(t.path, '/', '\\')), ''), df.folder_path)"


def _note_path_expr():
    return "rtrim(replace(t.path, '/', '\\'))"


def _current_owner_user_id():
    try:
        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "user_id", None)
    except Exception:
        return None
    return None


def _current_username():
    try:
        if getattr(current_user, "is_authenticated", False):
            return (getattr(current_user, "username", "") or "").strip()
    except Exception:
        return ""
    return ""


def _uses_area_folder_mapping():
    username = _current_username()
    return not username or username.lower() == "duncan"


def _area_folder_owner_sql(alias):
    if not _uses_area_folder_mapping():
        return "1 = 0"
    owner_user_id = _current_owner_user_id()
    if owner_user_id is None:
        return f"{alias}.owner_user_id IS NULL"
    return f"{alias}.owner_user_id = {int(owner_user_id)}"


def _derived_area_expr():
    folder_expr = _note_folder_match_expr()
    path_expr = _note_path_expr()
    best_prefix_len_expr = (
        "("
        "SELECT MAX(LENGTH(pf_len.path_prefix)) "
        "FROM lp_area_folders pf_len "
        f"WHERE {_area_folder_owner_sql('pf_len')} "
        "  AND pf_len.is_enabled = 1 "
        "  AND pf_len.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf_len.path_prefix) || '%'"
        ")"
    )
    named_child_expr = (
        "("
        "SELECT pf.area_id "
        "FROM lp_area_folders pf "
        "LEFT JOIN lp_areas p ON p.owner_user_id IS pf.owner_user_id AND p.area_id = pf.area_id "
        f"WHERE {_area_folder_owner_sql('pf')} "
        "  AND pf.is_enabled = 1 "
        "  AND pf.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf.path_prefix) || '%' "
        "  AND instr(pf.area_id, '/') > 0 "
        f"  AND lower({path_expr}) LIKE '%' || lower(COALESCE(p.area_name, '')) || '%' "
        f"  AND LENGTH(pf.path_prefix) = {best_prefix_len_expr} "
        "ORDER BY LENGTH(pf.path_prefix) DESC, CASE pf.folder_role "
        "  WHEN 'default' THEN 0 "
        "  WHEN 'include' THEN 1 "
        "  WHEN 'output' THEN 2 "
        "  WHEN 'archive' THEN 3 "
        "  ELSE 9 END, pf.sort_order, "
        "  (LENGTH(pf.area_id) - LENGTH(REPLACE(pf.area_id, '/', ''))) ASC, "
        "  LENGTH(pf.area_id) ASC, pf.area_id, pf.path_prefix "
        "LIMIT 1"
        ")"
    )
    normal_expr = (
        "("
        "SELECT pf.area_id "
        "FROM lp_area_folders pf "
        f"WHERE {_area_folder_owner_sql('pf')} "
        "  AND pf.is_enabled = 1 "
        "  AND pf.folder_role IN ('default','include','archive','output') "
        f"  AND {folder_expr} IS NOT NULL "
        f"  AND lower({folder_expr}) LIKE lower(pf.path_prefix) || '%' "
        "ORDER BY LENGTH(pf.path_prefix) DESC, CASE pf.folder_role "
        "  WHEN 'default' THEN 0 "
        "  WHEN 'include' THEN 1 "
        "  WHEN 'output' THEN 2 "
        "  WHEN 'archive' THEN 3 "
        "  ELSE 9 END, pf.sort_order, "
        "  (LENGTH(pf.area_id) - LENGTH(REPLACE(pf.area_id, '/', ''))) ASC, "
        "  LENGTH(pf.area_id) ASC, pf.area_id, pf.path_prefix "
        "LIMIT 1"
        ")"
    )
    return f"COALESCE({named_child_expr}, {normal_expr}, NULLIF(t.area, ''))"


def _area_scope_ids(area):
    area = (area or "").strip()
    if not area or area.lower() == "unmapped":
        return []
    conn = data._get_conn()
    areas_mod.ensure_areas_schema(conn)
    area_lower = area.lower()
    owner_user_id = _current_owner_user_id()
    ids = []

    exact = areas_mod.area_get(area, conn=conn, owner_user_id=owner_user_id)
    if exact:
        rows = conn.execute(
            "SELECT area_id, area_name FROM lp_areas "
            "WHERE owner_user_id IS ? AND status = 'active' "
            "AND (lower(area_id) = lower(?) OR lower(area_id) LIKE lower(?) || '/%') "
            "ORDER BY LENGTH(area_id), area_id",
            (owner_user_id, area, area),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT area_id, area_name FROM lp_areas "
            "WHERE owner_user_id IS ? AND status = 'active' "
            "AND (lower(area_id) LIKE lower(?) || '/%' "
            "     OR lower(area_name) = ? "
            "     OR lower(tab) = ? "
            "     OR lower(group_name) = ? "
            "     OR lower(area_id) = ?) "
            "ORDER BY LENGTH(area_id), area_id",
            (owner_user_id, area, area_lower, area_lower, area_lower, f"{area_lower}.{area_lower}.{area_lower}"),
        ).fetchall()

    seen = {area.lower()}
    ids.append(area)
    for row in rows:
        area_id = (row["area_id"] or "").strip()
        if area_id and area_id.lower() not in seen:
            ids.append(area_id)
            seen.add(area_id.lower())
        area_name = (row["area_name"] or "").strip()
        if area_name and area_name.lower() not in seen:
            ids.append(area_name)
            seen.add(area_name.lower())
    if exact:
        area_name = (exact.get("area_name") or "").strip()
        if area_name and area_name.lower() not in seen:
            ids.append(area_name)
            seen.add(area_name.lower())
    return ids or [area]


def _direct_area_condition(scope_ids):
    placeholders = ", ".join(["?"] * len(scope_ids))
    return f"t.area COLLATE NOCASE IN ({placeholders})"


def _unmapped_area_condition():
    return (
        "("
        "COALESCE(TRIM(t.area), '') = '' "
        "OR NOT EXISTS ("
        "  SELECT 1 FROM lp_areas a "
        "  WHERE a.owner_user_id IS ? "
        "    AND a.status = 'active' "
        "    AND COALESCE(a.is_header, 0) = 0 "
        "    AND COALESCE(a.is_system, 0) = 0 "
        "    AND ("
        "      lower(a.area_id) = lower(TRIM(t.area)) "
        "      OR lower(a.area_name) = lower(TRIM(t.area))"
        "    )"
        ")"
        ")"
    )


def _notes_base_condition(area, folder_path=None):
    params = []
    if area and area.lower() == "unmapped":
        condition = _unmapped_area_condition()
        params.append(_current_owner_user_id())
    elif area:
        scope_ids = _area_scope_ids(area)
        condition = _direct_area_condition(scope_ids)
        params.extend(scope_ids)
    else:
        condition = "1=1"
    if folder_path:
        condition = f"({condition}) AND lower(rtrim(replace(t.path, '/', '\\'))) = lower(?)"
        params.append(folder_path)
    visibility_condition, visibility_params = security.visible_record_condition("t", current_user)
    condition = f"({condition}) AND {visibility_condition}"
    params.extend(visibility_params)
    return condition, params


def _count_notes(area, folder_path=None):
    _ensure_notes_schema()
    tbl = get_table_def("notes")
    if not tbl:
        return 0
    areas_mod.ensure_areas_schema(data._get_conn())
    condition, params = _notes_base_condition(area, folder_path)
    row = data._get_conn().execute(
        f"SELECT COUNT(1) AS cnt FROM {tbl['name']} t WHERE {condition}",
        params,
    ).fetchone()
    return row["cnt"] if row else 0


def _notes_url_args(area=None, folder_path=None, **extra):
    args = {}
    if area:
        args["area"] = area
    if folder_path:
        args["folder"] = folder_path
    for key, value in extra.items():
        if value not in (None, "", False):
            args[key] = value
    return args


def _normalize_note_list_view(value):
    value = (value or "").strip().lower()
    if value == "card":
        return "grid"
    if value == "cards":
        return "grid"
    if value in {"list", "table", "grid", "preview", "collections", "names"}:
        return value
    return "table"


def _normalize_note_sort_col(value):
    value = (value or "").strip().lower()
    aliases = {
        "file": "title",
        "file_name": "title",
        "filename": "title",
        "path": "folder",
        "folder_id": "folder",
        "modified": "date_modified",
        "created": "date_created",
    }
    value = aliases.get(value, value)
    allowed = {key for key, _label in NOTE_LIST_SORT_OPTIONS}
    return value if value in allowed else "date_modified"


def _normalize_note_sort_dir(value):
    return "asc" if (value or "").strip().lower() == "asc" else "desc"


def _notes_route_for_view(view_mode):
    view_mode = _normalize_note_list_view(view_mode)
    if view_mode == "list":
        return "notes.list_notes_list_route"
    if view_mode == "names":
        return "notes.list_notes_names_route"
    if view_mode in {"grid", "preview"}:
        return "notes.list_notes_cards_route"
    if view_mode == "collections":
        return "notes.notes_collections_route"
    return "notes.list_notes_table_route"


def _notes_view_url(view_mode, area, folder_filter, sort_col, sort_dir):
    view_mode = _normalize_note_list_view(view_mode)
    args = _notes_url_args(area, folder_filter, sort=sort_col, dir=sort_dir)
    if view_mode in {"grid", "preview"}:
        args["mode"] = "preview" if view_mode == "preview" else "grid"
    return url_for(_notes_route_for_view(view_mode), **args)


def _notes_view_options(area, folder_filter, sort_col, sort_dir, active_view):
    active_view = _normalize_note_list_view(active_view)
    return [
        {
            "value": _notes_view_url(view, area, folder_filter, sort_col, sort_dir),
            "label": label,
            "active": view == active_view,
        }
        for view, label in NOTE_LIST_VIEW_OPTIONS
    ]


def _notes_table_sort_headers(area, folder_filter, route_name, sort_col, sort_dir, card_mode=None):
    sort_col = _normalize_note_sort_col(sort_col)
    sort_dir = _normalize_note_sort_dir(sort_dir)
    headers = {}
    for key, label, column in NOTE_TABLE_SORT_COLUMNS:
        next_dir = "desc" if sort_col == column and sort_dir == "asc" else "asc"
        args = _notes_url_args(area, folder_filter, sort=column, dir=next_dir)
        if card_mode:
            args["mode"] = card_mode
        headers[key] = {
            "label": label,
            "sort_col": column,
            "active": sort_col == column,
            "dir": sort_dir if sort_col == column else "",
            "next_dir": next_dir,
            "url": url_for(route_name, **args),
        }
    return headers


def _notes_page_title(area_label):
    return f"Notes ({area_label})" if area_label else "Notes"


def _note_bulk_area_options(active_areas=None):
    areas = active_areas if active_areas is not None else areas_mod.areas_list_sidebar()
    return [
        {
            "id": area.get("area_id") or "",
            "label": area.get("area_name") or area.get("area_id") or "",
        }
        for area in areas
        if area.get("area_id")
    ]


def _note_bulk_color_options():
    return [
        {"value": label, "label": label, "style": style}
        for label, style in NOTE_COLOR_OPTIONS
    ]


def _normalize_note_card_mode(value):
    return "preview" if value == "preview" else NOTE_CARD_DEFAULT_MODE


def _note_display_settings():
    try:
        return settings_mod.get_note_display_settings(data._get_conn())
    except Exception:
        return {
            "card_width_chars": NOTE_CARD_MAX_CHARS,
            "title_font_size": NOTE_CARD_TITLE_FONT_SIZE,
            "preview_chars": NOTE_CARD_PREVIEW_CHARS,
            "sample_lines": settings_mod.NOTE_SAMPLE_LINES_DEFAULT,
            "notes_per_page": NOTES_PER_PAGE,
        }


def _note_body_text(markdown_text, file_name="", title=""):
    text = markdown_text or ""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        for idx, line in enumerate(lines[1:], 1):
            if line.strip() in ("---", "..."):
                return _without_duplicate_title_heading("".join(lines[idx + 1 :]), file_name, title)
    return _without_duplicate_title_heading(text, file_name, title)


def _preview_text(value, max_chars=NOTE_CARD_PREVIEW_CHARS):
    value = value or ""
    max_chars = max(1, int(max_chars or NOTE_CARD_PREVIEW_CHARS))
    return value if len(value) <= max_chars else value[:max_chars]


def _note_preview_from_cached_text(note, cached_text, max_chars=NOTE_CARD_PREVIEW_CHARS):
    return _preview_text(_note_body_text(cached_text or "", note.get("file_name"), note.get("title")), max_chars)


def _prepare_note_card_previews(notes, max_chars=NOTE_CARD_PREVIEW_CHARS, render_html=True):
    note_ids = [note.get("id") for note in notes or [] if note.get("id")]
    cached = {}
    if note_ids:
        try:
            conn = data._get_conn()
            note_search_index.ensure_schema(conn)
            placeholders = ", ".join(["?"] * len(note_ids))
            rows = conn.execute(
                f"SELECT note_id, content_text FROM lp_note_search_index WHERE note_id IN ({placeholders})",
                note_ids,
            ).fetchall()
            cached = {row["note_id"]: row["content_text"] or "" for row in rows}
        except Exception:
            cached = {}
    for note in notes or []:
        preview = _note_preview_from_cached_text(note, cached.get(note.get("id"), ""), max_chars)
        note["preview_text"] = preview
        if render_html:
            note["preview_html"] = markdown_utils.render_markdown(
                preview,
                asset_resolver=lambda asset_name, note_id=note.get("id"): url_for(
                    "notes.note_asset_route",
                    note_id=note_id,
                    asset_path=asset_name,
                ),
                allow_html=False,
            )
        else:
            note["preview_html"] = ""
    return notes


def _current_user_notes_root(create_dirs=False):
    try:
        if getattr(current_user, "is_authenticated", False):
            paths = user_paths.get_or_create_user_paths(
                data._get_conn(),
                current_user.user_id,
                username=getattr(current_user, "username", None),
                create_dirs=False,
            )
            notes_root = _normalize_note_path(paths.get("notes_root_path") or "")
            if create_dirs and notes_root:
                os.makedirs(notes_root, exist_ok=True)
            return notes_root
    except Exception:
        return ""
    return ""


def _notes_root_path(area=None, *, create_dirs=False):
    tbl = get_table_def("notes")
    if not tbl:
        return None
    areas_mod.ensure_areas_schema(data._get_conn())
    condition, params = _notes_base_condition(area)
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
        return _current_user_notes_root(create_dirs=create_dirs) or None
    parts = [part for part in _normalize_folder_filter(row["path"]).split("\\") if part]
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            return "\\".join(parts[: idx + 2])
    return _current_user_notes_root(create_dirs=create_dirs) or None


def _note_folder_breadcrumb(folder_path, area=None):
    folder_path = _normalize_folder_filter(folder_path)
    if not folder_path:
        root_path = _notes_root_path(area)
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


def _fetch_note_subfolders(area, folder_path=None):
    folder_path = _normalize_folder_filter(folder_path)
    if not folder_path:
        return []
    tbl = get_table_def("notes")
    if not tbl:
        return []
    areas_mod.ensure_areas_schema(data._get_conn())
    condition, params = _notes_base_condition(area)
    sql = (
        f"SELECT DISTINCT rtrim(t.path) AS path "
        f"FROM {tbl['name']} t "
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
            "url": url_for("notes.list_notes_table_route", **_notes_url_args(area, child_path)),
        }
    return [subfolders[key] for key in sorted(subfolders)]


def _folder_label(path_value):
    path_value = _normalize_note_path(path_value)
    if not path_value:
        return "Folder"
    parts = [part for part in path_value.split("\\") if part]
    if len(parts) >= 2:
        return "\\".join(parts[-2:])
    return parts[-1] if parts else path_value


def _note_folder_panel_items(area, folder_filter, area_folders, view_mode, sort_col, sort_dir):
    items = []
    seen = set()

    def add_item(label, path_value):
        path_value = _normalize_note_path(path_value)
        if not path_value:
            return
        key = path_value.lower()
        if key in seen:
            return
        seen.add(key)
        items.append({
            "label": label or _folder_label(path_value),
            "path": path_value,
            "url": _notes_view_url(view_mode, area, path_value, sort_col, sort_dir),
        })

    if folder_filter:
        for folder in _fetch_note_subfolders(area, folder_filter):
            add_item(folder.get("label"), folder.get("path"))
        return items

    return []


def _sqlite_int_text_expr(value_expr):
    trimmed = f"trim(COALESCE({value_expr}, ''))"
    return (
        f"CASE WHEN {trimmed} != '' AND {trimmed} NOT GLOB '*[^0-9]*' "
        f"THEN CAST({trimmed} AS INTEGER) ELSE NULL END"
    )


def _notes_list_context(
    *,
    area,
    folder_filter,
    area_info,
    area_folders,
    area_label,
    total,
    sort_col,
    sort_dir,
    route_name,
    view_mode,
    page,
    total_pages,
    pages,
    first_url,
    last_url,
    card_mode=None,
    note_settings=None,
):
    active_areas = areas_mod.areas_list_sidebar()
    view_mode = _normalize_note_list_view(view_mode)
    sort_col = _normalize_note_sort_col(sort_col)
    sort_dir = _normalize_note_sort_dir(sort_dir)
    return {
        "active_tab": "notes",
        "tabs": get_tabs(),
        "side_tabs": get_side_tabs(),
        "content_title": _notes_page_title(area_label),
        "content_html": "",
        "area_info": area_info,
        "area_folders": area_folders,
        "area": area,
        "folder_filter": folder_filter,
        "note_breadcrumb": _note_folder_breadcrumb(folder_filter, area),
        "note_folder_panel_items": _note_folder_panel_items(
            area,
            folder_filter,
            area_folders,
            view_mode,
            sort_col,
            sort_dir,
        ),
        "total_notes": total,
        "sort_col": sort_col,
        "sort_dir": sort_dir,
        "sort_options": NOTE_LIST_SORT_OPTIONS,
        "table_sort_headers": _notes_table_sort_headers(
            area,
            folder_filter,
            route_name,
            sort_col,
            sort_dir,
            card_mode,
        ),
        "view_options": _notes_view_options(area, folder_filter, sort_col, sort_dir, view_mode),
        "notes_view_mode": view_mode,
        "route_name": route_name,
        "card_mode": card_mode,
        "note_card_max_chars": (note_settings or {}).get("card_width_chars", NOTE_CARD_MAX_CHARS),
        "note_card_title_font_size": (note_settings or {}).get("title_font_size", NOTE_CARD_TITLE_FONT_SIZE),
        "active_areas": active_areas,
        "bulk_area_options": _note_bulk_area_options(active_areas),
        "bulk_color_options": _note_bulk_color_options(),
        "page": page,
        "total_pages": total_pages,
        "pages": pages,
        "first_url": first_url,
        "last_url": last_url,
    }


def _fetch_notes(area, sort_col=None, sort_dir=None, limit=None, offset=None, folder_path=None, include_derived=False):
    _ensure_notes_schema()
    tbl = get_table_def("notes")
    if not tbl:
        return []
    areas_mod.ensure_areas_schema(data._get_conn())
    cols = ["id"] + tbl["col_list"]
    order_map = {
        "file_name": "t.file_name",
        "path": "t.path",
        "folder": "t.path",
        "folder_id": "t.folder_id",
        "size": _sqlite_int_text_expr("t.size"),
        "title": "lower(COALESCE(NULLIF(t.title, ''), t.file_name, ''))",
        "color": "t.color",
        "date_created": "t.date_created",
        "area": "t.area",
        "important": "t.important",
        "source_note_id": "t.source_note_id",
        "date_modified": "t.date_modified",
        "updated": "t.rec_extract_date",
        "derived_area": "derived_area",
    }
    sort_col = sort_col or "updated"
    sort_key = order_map.get(sort_col, "t.rec_extract_date")
    sort_dir = sort_dir or "desc"
    if sort_col == "size":
        order_by = f"CASE WHEN ({sort_key}) IS NULL THEN 1 ELSE 0 END ASC, ({sort_key}) {sort_dir}"
    else:
        order_by = f"{sort_key} {sort_dir}"
    select_cols = [f"t.{col}" for col in cols]
    select_cols.append("t.rec_extract_date as updated")
    if include_derived:
        select_cols.append(f"{_derived_area_expr()} as derived_area")
    else:
        select_cols.append("COALESCE(NULLIF(t.area, ''), '') as derived_area")
    condition, params = _notes_base_condition(area, folder_path)
    join_sql = "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id " if include_derived else ""
    sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM {tbl['name']} t "
        f"{join_sql}"
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
        _apply_note_display_fields(note)
    return notes



def _get_note_record(note_id):
    _ensure_notes_schema()
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
    _apply_note_display_fields(note)
    return note, tbl


def _note_title_match_expr(alias="t"):
    prefix = f"{alias}." if alias else ""
    return (
        f"CASE WHEN COALESCE({prefix}title, '') != '' THEN {prefix}title "
        f"WHEN lower(COALESCE({prefix}file_name, '')) LIKE '%.md' "
        f"THEN substr({prefix}file_name, 1, length({prefix}file_name) - 3) "
        f"ELSE COALESCE({prefix}file_name, '') END"
    )


def _note_display_title(row):
    return (row.get("title") or os.path.splitext(row.get("file_name") or "")[0] or row.get("file_name") or "").strip()


def _parse_note_wiki_link_value(value):
    parts = [part.strip() for part in (value or "").split("|")]
    title = parts[0] if parts else ""
    target_note_id = None
    for part in parts[1:]:
        match = NOTE_WIKI_TARGET_ID_RE.match(part or "")
        if match:
            target_note_id = int(match.group(1))
            break
    if not title:
        for part in parts:
            if not NOTE_WIKI_TARGET_ID_RE.match(part or ""):
                title = part
                break
    return title, target_note_id


def _note_link_syntax(title, target_note_id):
    title = (title or "").strip()
    if not title or not target_note_id:
        return ""
    escaped = title.replace("]", "").replace("|", " ")
    return f"[[{escaped}|note:{int(target_note_id)}]]"


def _markdown_link_destination(path_value):
    path_value = (path_value or "").replace("\\", "/")
    if not path_value:
        return ""
    if any(ch.isspace() for ch in path_value) or any(ch in path_value for ch in "()"):
        return "<" + path_value.replace("<", "%3C").replace(">", "%3E") + ">"
    return path_value


def _relative_markdown_note_link(current_note, target_note):
    label = _note_display_title(target_note)
    target_path = _build_note_path(target_note)
    current_path = _build_note_path(current_note) if current_note else ""
    current_dir = os.path.dirname(current_path) if current_path else ""
    if not label or not target_path or not current_dir:
        return ""
    try:
        relative_path = os.path.relpath(target_path, start=current_dir)
    except ValueError:
        notes_root = _notes_root_from_path(target_path) or ""
        relative_path = target_path[len(notes_root):].lstrip("\\/") if notes_root else target_path
    return f"[{label}]({_markdown_link_destination(relative_path)})"


def _normalize_wiki_note_path(value):
    value = (value or "").strip().strip("/\\")
    if not value:
        return ""
    value = value.replace("/", "\\")
    value = re.sub(r"\\+", r"\\", value)
    return value.lower()


def _wiki_path_candidates(title):
    normalized = _normalize_wiki_note_path(title)
    if not normalized or "\\" not in normalized:
        return []
    candidates = [normalized]
    if not normalized.endswith(".md"):
        candidates.append(normalized + ".md")
    return candidates


def _wiki_db_path_candidates(title):
    candidates = _wiki_path_candidates(title)
    if not candidates:
        return []
    notes_root = _notes_root_path(create_dirs=False) or ""
    notes_root = _normalize_wiki_note_path(notes_root)
    if not notes_root:
        return candidates
    expanded = list(candidates)
    for candidate in candidates:
        if os.path.isabs(candidate):
            continue
        expanded.append(_normalize_wiki_note_path(os.path.join(notes_root, candidate)))
    seen = set()
    unique = []
    for candidate in expanded:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _markdown_note_link_target_parts(target):
    target = unquote((target or "").strip())
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.replace("/", "\\")
    if not target or "\x00" in target:
        return "", ""
    path_part, hash_sep, fragment = target.partition("#")
    path_part = path_part.split("?", 1)[0].strip().strip("/\\")
    if not path_part:
        return "", ""
    _stem, ext = os.path.splitext(path_part)
    if ext.lower() != ".md":
        return "", ""
    fragment = (hash_sep + fragment) if hash_sep and fragment else ""
    return os.path.normpath(path_part), fragment


def _markdown_note_link_candidates(current_note, target):
    path_part, fragment = _markdown_note_link_target_parts(target)
    if not path_part:
        return [], ""
    current_path = _build_note_path(current_note)
    current_folder = os.path.dirname(current_path) if current_path else _normalize_note_path(current_note.get("path") or "")
    notes_root = _notes_root_from_path(current_path or current_note.get("path") or "")
    candidates = []
    if current_folder:
        candidates.append(_normalize_wiki_note_path(os.path.join(current_folder, path_part)))
    if notes_root:
        candidates.append(_normalize_wiki_note_path(os.path.join(notes_root, path_part)))
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique, fragment


def _resolve_markdown_note_link(current_note, target):
    path_candidates, fragment = _markdown_note_link_candidates(current_note, target)
    if not path_candidates:
        return None
    tbl = get_table_def("notes")
    if not tbl:
        return {"status": "broken"}
    condition, params = security.visible_record_condition("t", current_user)
    placeholders = ", ".join(["?"] * len(path_candidates))
    rows = data._get_conn().execute(
        f"SELECT t.id, t.file_name, t.title, t.path "
        f"FROM {tbl['name']} t "
        f"WHERE {condition} "
        f"AND lower(replace(rtrim(COALESCE(t.path, '') || '\\' || COALESCE(t.file_name, '')), '/', '\\')) "
        f"IN ({placeholders}) "
        f"ORDER BY LENGTH(COALESCE(t.path, '') || '\\' || COALESCE(t.file_name, '')), t.id ",
        [*params, *path_candidates],
    ).fetchall()
    if not rows:
        return {"status": "broken"}
    if len(rows) > 1:
        return {"status": "ambiguous", "count": len(rows)}
    row = rows[0]
    return {
        "status": "resolved",
        "url": url_for("notes.view_note_route", note_id=row["id"]) + fragment,
        "title": _note_display_title(dict(row)) or target,
        "target_note_id": row["id"],
    }


def _visible_note_by_id(note_id):
    try:
        note_id = int(note_id)
    except (TypeError, ValueError):
        return None
    if not security.can_view_note(note_id, current_user):
        return None
    note, _tbl = _get_note_record(note_id)
    return note


def _resolve_note_wiki_link(title, target_note_id=None):
    title = (title or "").strip()
    if target_note_id:
        note = _visible_note_by_id(target_note_id)
        if note:
            return {
                "status": "resolved",
                "url": url_for("notes.view_note_route", note_id=note["id"]),
                "title": _note_display_title(note) or title,
                "target_note_id": note["id"],
            }
        return {"status": "broken"}
    if not title:
        return {"status": "broken"}
    tbl = get_table_def("notes")
    if not tbl:
        return {"status": "broken"}
    condition, params = security.visible_record_condition("t", current_user)
    path_candidates = _wiki_db_path_candidates(title)
    if path_candidates:
        placeholders = ", ".join(["?"] * len(path_candidates))
        rows = data._get_conn().execute(
            f"SELECT t.id, t.file_name, t.title, t.path "
            f"FROM {tbl['name']} t "
            f"WHERE {condition} "
            f"AND lower(replace(rtrim(COALESCE(t.path, '') || '\\' || COALESCE(t.file_name, '')), '/', '\\')) "
            f"IN ({placeholders}) "
            f"ORDER BY LENGTH(COALESCE(t.path, '') || '\\' || COALESCE(t.file_name, '')), t.id ",
            [*params, *path_candidates],
        ).fetchall()
        if len(rows) == 1:
            row = rows[0]
            return {
                "status": "resolved",
                "url": url_for("notes.view_note_route", note_id=row["id"]),
                "title": _note_display_title(dict(row)) or title,
                "target_note_id": row["id"],
            }
        if len(rows) > 1:
            return {"status": "ambiguous", "count": len(rows)}

    title_expr = _note_title_match_expr("t")
    rows = data._get_conn().execute(
        f"SELECT t.id, t.file_name, t.title, t.path "
        f"FROM {tbl['name']} t "
        f"WHERE {condition} AND lower({title_expr}) = lower(?) "
        f"ORDER BY lower(COALESCE(NULLIF(t.title, ''), t.file_name, '')), t.path, t.id ",
        [*params, title],
    ).fetchall()
    if not rows:
        return {"status": "broken"}
    if len(rows) > 1:
        return {"status": "ambiguous", "count": len(rows)}
    row = rows[0]
    return {
        "status": "resolved",
        "url": url_for("notes.view_note_route", note_id=row["id"]),
        "title": _note_display_title(dict(row)) or title,
        "target_note_id": row["id"],
    }


def _visible_note_rows(limit=None):
    _ensure_notes_schema()
    tbl = get_table_def("notes")
    if not tbl:
        return []
    condition, params = security.visible_record_condition("t", current_user)
    sql = (
        f"SELECT t.id, t.file_name, t.title, t.path, t.area, t.date_modified "
        f"FROM {tbl['name']} t "
        f"WHERE {condition} "
        "ORDER BY lower(COALESCE(NULLIF(t.title, ''), t.file_name, ''))"
    )
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    rows = data._get_conn().execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _fuzzy_note_score(query, row):
    query = (query or "").strip().lower()
    title = _note_display_title(row).lower()
    file_name = (row.get("file_name") or "").lower()
    path = (row.get("path") or "").lower()
    haystack = " ".join([title, file_name, path])
    if not query:
        return 1.0
    if query == title:
        return 4.0
    if title.startswith(query):
        return 3.5
    if query in title:
        return 3.0
    if query in haystack:
        return 2.0
    return SequenceMatcher(None, query, title or file_name).ratio()


def _search_wiki_notes(query, exclude_note_id=None, limit=20):
    current_note = _visible_note_by_id(exclude_note_id) if exclude_note_id else None
    rows = _visible_note_rows()
    scored = []
    for row in rows:
        if exclude_note_id and str(row.get("id")) == str(exclude_note_id):
            continue
        score = _fuzzy_note_score(query, row)
        if query and score < 0.35:
            continue
        scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], _note_display_title(item[1]).lower(), item[1].get("id") or 0))
    results = []
    for score, row in scored[: max(1, int(limit or 20))]:
        title = _note_display_title(row)
        results.append(
            {
                "id": row["id"],
                "title": title,
                "file_name": row.get("file_name") or "",
                "path": row.get("path") or "",
                "area": row.get("area") or "",
                "score": round(score, 3),
                "wiki_link": _note_link_syntax(title, row["id"]),
                "markdown_link": _relative_markdown_note_link(current_note, row),
                "open_url": url_for("notes.view_note_route", note_id=row["id"]),
            }
        )
    return results


def _iter_note_wiki_links(content):
    for match in NOTE_WIKI_LINK_RE.finditer(content or ""):
        title, target_note_id = _parse_note_wiki_link_value(match.group(1))
        if title:
            yield title, target_note_id, match.group(0)


def _iter_note_markdown_links(content, current_note):
    if not current_note:
        return
    for match in NOTE_MARKDOWN_LINK_RE.finditer(content or ""):
        label = (match.group(1) or "").strip()
        target = (match.group(2) or "").strip()
        if not label or not target:
            continue
        resolved = _resolve_markdown_note_link(current_note, target)
        if resolved and resolved.get("status") == "resolved" and resolved.get("target_note_id"):
            yield label, int(resolved["target_note_id"]), match.group(0), resolved


def _sync_note_links(note_id, content):
    _ensure_note_links_schema()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = {}
    for title, target_note_id, link_text in _iter_note_wiki_links(content):
        resolved = _resolve_note_wiki_link(title, target_note_id=target_note_id)
        if resolved.get("status") != "resolved" or not resolved.get("target_note_id"):
            continue
        target_id = int(resolved["target_note_id"])
        if int(note_id) == target_id:
            continue
        rows[(int(note_id), target_id, link_text)] = (
            int(note_id),
            target_id,
            link_text,
            title,
            now,
            now,
        )
    current_note, _tbl = _get_note_record(note_id)
    for label, target_id, link_text, resolved in _iter_note_markdown_links(content, current_note):
        if int(note_id) == target_id:
            continue
        rows[(int(note_id), target_id, link_text)] = (
            int(note_id),
            target_id,
            link_text,
            resolved.get("title") or label,
            now,
            now,
        )
    conn = data._get_conn()
    conn.execute("DELETE FROM lp_note_links WHERE src_note_id = ?", (int(note_id),))
    conn.executemany(
        "INSERT OR REPLACE INTO lp_note_links "
        "(src_note_id, target_note_id, link_text, link_title, created_utc, updated_utc) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        list(rows.values()),
    )
    conn.commit()
    return len(rows)

@notes_bp.route('/')
def list_notes_route():
    area = _normalize_area(request_area_param())
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    note_settings = _note_display_settings()
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    tbl = get_table_def("notes")
    route_name = "notes.list_notes_table_route"
    if not tbl:
        context = _notes_list_context(
            area=area,
            folder_filter=folder_filter,
            area_info=area_info,
            area_folders=area_folders,
            area_label=area_label,
            total=0,
            sort_col="date_modified",
            sort_dir="desc",
            route_name=route_name,
            view_mode="table",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for(route_name),
            last_url=url_for(route_name),
            note_settings=note_settings,
        )
        context["notes"] = []
        return render_template("notes_list.html", **context)
    view_pref = request.cookies.get("notes_view")
    if view_pref in ("list", "cards", "grid", "preview", "collections", "names"):
        return redirect(_notes_view_url(view_pref, area, folder_filter, request.cookies.get("notes_sort_col") or "date_modified", request.cookies.get("notes_sort_dir") or "desc"))
    sort_col = _normalize_note_sort_col(request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified")
    sort_dir = _normalize_note_sort_dir(request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc")
    page = request.args.get("page", type=int) or 1
    per_page = note_settings["notes_per_page"]
    total = _count_notes(area, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(area, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(area, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    context = _notes_list_context(
        area=area,
        folder_filter=folder_filter,
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=total,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        view_mode="table",
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        note_settings=note_settings,
    )
    context["notes"] = notes
    resp = make_response(
        render_template("notes_list.html", **context)
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/table')
def list_notes_table_route():
    area = _normalize_area(request_area_param())
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    note_settings = _note_display_settings()
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    tbl = get_table_def("notes")
    route_name = "notes.list_notes_table_route"
    if not tbl:
        context = _notes_list_context(
            area=area,
            folder_filter=folder_filter,
            area_info=area_info,
            area_folders=area_folders,
            area_label=area_label,
            total=0,
            sort_col="date_modified",
            sort_dir="desc",
            route_name=route_name,
            view_mode="table",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for(route_name),
            last_url=url_for(route_name),
            note_settings=note_settings,
        )
        context["notes"] = []
        return render_template("notes_list.html", **context)
    sort_col = _normalize_note_sort_col(request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified")
    sort_dir = _normalize_note_sort_dir(request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc")
    page = request.args.get("page", type=int) or 1
    per_page = note_settings["notes_per_page"]
    total = _count_notes(area, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(area, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(area, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    context = _notes_list_context(
        area=area,
        folder_filter=folder_filter,
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=total,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        view_mode="table",
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        note_settings=note_settings,
    )
    context["notes"] = notes
    resp = make_response(
        render_template("notes_list.html", **context)
    )
    resp.set_cookie("notes_view", "table")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/list')
def list_notes_list_route():
    area = _normalize_area(request_area_param())
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    note_settings = _note_display_settings()
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    tbl = get_table_def("notes")
    route_name = "notes.list_notes_list_route"
    if not tbl:
        context = _notes_list_context(
            area=area,
            folder_filter=folder_filter,
            area_info=area_info,
            area_folders=area_folders,
            area_label=area_label,
            total=0,
            sort_col="date_modified",
            sort_dir="desc",
            route_name=route_name,
            view_mode="list",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for(route_name),
            last_url=url_for(route_name),
            note_settings=note_settings,
        )
        context["notes"] = []
        return render_template("notes_list_list.html", **context)
    sort_col = _normalize_note_sort_col(request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified")
    sort_dir = _normalize_note_sort_dir(request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc")
    page = request.args.get("page", type=int) or 1
    per_page = note_settings["notes_per_page"]
    total = _count_notes(area, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(area, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter, include_derived=False)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(area, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    context = _notes_list_context(
        area=area,
        folder_filter=folder_filter,
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=total,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        view_mode="list",
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        note_settings=note_settings,
    )
    context["notes"] = notes
    resp = make_response(
        render_template("notes_list_list.html", **context)
    )
    resp.set_cookie("notes_view", "list")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/names')
def list_notes_names_route():
    area = _normalize_area(request_area_param())
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    note_settings = _note_display_settings()
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    tbl = get_table_def("notes")
    route_name = "notes.list_notes_names_route"
    if not tbl:
        context = _notes_list_context(
            area=area,
            folder_filter=folder_filter,
            area_info=area_info,
            area_folders=area_folders,
            area_label=area_label,
            total=0,
            sort_col="date_modified",
            sort_dir="desc",
            route_name=route_name,
            view_mode="names",
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for(route_name),
            last_url=url_for(route_name),
            note_settings=note_settings,
        )
        context["notes"] = []
        return render_template("notes_list_names.html", **context)
    sort_col = _normalize_note_sort_col(request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified")
    sort_dir = _normalize_note_sort_dir(request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc")
    page = request.args.get("page", type=int) or 1
    per_page = note_settings["notes_per_page"]
    total = _count_notes(area, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(area, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter, include_derived=False)
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(area, folder_filter, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    context = _notes_list_context(
        area=area,
        folder_filter=folder_filter,
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=total,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        view_mode="names",
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        note_settings=note_settings,
    )
    context["notes"] = notes
    resp = make_response(render_template("notes_list_names.html", **context))
    resp.set_cookie("notes_view", "names")
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


@notes_bp.route('/cards')
def list_notes_cards_route():
    area = _normalize_area(request_area_param())
    folder_filter = _normalize_folder_filter(request.args.get("folder"))
    note_settings = _note_display_settings()
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    card_mode = _normalize_note_card_mode(request.args.get("mode") or request.cookies.get("notes_card_mode"))
    view_mode = "preview" if card_mode == "preview" else "grid"
    route_name = "notes.list_notes_cards_route"
    tbl = get_table_def("notes")
    if not tbl:
        context = _notes_list_context(
            area=area,
            folder_filter=folder_filter,
            area_info=area_info,
            area_folders=area_folders,
            area_label=area_label,
            total=0,
            sort_col="date_modified",
            sort_dir="desc",
            route_name=route_name,
            view_mode=view_mode,
            card_mode=card_mode,
            page=1,
            total_pages=1,
            pages=[],
            first_url=url_for(route_name, **_notes_url_args(area, folder_filter, mode=card_mode)),
            last_url=url_for(route_name, **_notes_url_args(area, folder_filter, mode=card_mode)),
            note_settings=note_settings,
        )
        context["notes"] = []
        context["card_values"] = []
        context["note_card_bg"] = cfg.NOTE_CARD_DEF_BG_COL
        return render_template("notes_list_cards.html", **context)
    sort_col = _normalize_note_sort_col(request.args.get("sort") or request.cookies.get("notes_sort_col") or "date_modified")
    sort_dir = _normalize_note_sort_dir(request.args.get("dir") or request.cookies.get("notes_sort_dir") or "desc")
    page = request.args.get("page", type=int) or 1
    per_page = note_settings["notes_per_page"]
    total = _count_notes(area, folder_filter)
    offset = (page - 1) * per_page
    notes = _fetch_notes(area, sort_col, sort_dir, limit=per_page, offset=offset, folder_path=folder_filter, include_derived=False)
    _prepare_note_card_previews(
        notes,
        max_chars=note_settings["preview_chars"],
        render_html=(card_mode == "preview"),
    )
    page_data = paginate_total(total, page, per_page)
    page = page_data["page"]
    total_pages = page_data["total_pages"]
    pagination = build_pagination(
        url_for,
        route_name,
        _notes_url_args(area, folder_filter, mode=card_mode, sort=sort_col, dir=sort_dir),
        page,
        total_pages,
    )
    card_values = [
        [n.get("file_name"), n.get("path"), url_for("notes.view_note_route", note_id=n.get("id"))]
        for n in notes
    ]
    context = _notes_list_context(
        area=area,
        folder_filter=folder_filter,
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=total,
        sort_col=sort_col,
        sort_dir=sort_dir,
        route_name=route_name,
        view_mode=view_mode,
        card_mode=card_mode,
        page=page,
        total_pages=total_pages,
        pages=pagination["pages"],
        first_url=pagination["first_url"],
        last_url=pagination["last_url"],
        note_settings=note_settings,
    )
    context["notes"] = notes
    context["card_values"] = card_values
    context["note_card_bg"] = cfg.NOTE_CARD_DEF_BG_COL
    resp = make_response(
        render_template("notes_list_cards.html", **context)
    )
    resp.set_cookie("notes_view", view_mode)
    resp.set_cookie("notes_card_mode", card_mode)
    resp.set_cookie("notes_sort_col", sort_col)
    resp.set_cookie("notes_sort_dir", sort_dir)
    return resp


def _notebook_form_values(form, area=""):
    selected_area_ids = form.getlist("area_ids")
    if not selected_area_ids and area:
        selected_area_ids = [area]
    return {
        "collection_name": form.get("collection_name", "").strip(),
        "collection_domain": "notes",
        "collection_type": form.get("collection_type", "notebook").strip() or "notebook",
        "description": form.get("description", "").strip(),
        "icon": form.get("icon", "").strip(),
        "status": form.get("status", "active").strip() or "active",
        "visibility": form.get("visibility", "private").strip() or "private",
        "area_ids": selected_area_ids,
        "project_ids": form.getlist("project_ids"),
    }


def _collection_note_ids(collection_items):
    ids = []
    for item in collection_items or []:
        if item.get("entry_kind") == "item" and item.get("item_type") == "note":
            note_id = _safe_int(item.get("item_id"))
            if note_id is not None:
                ids.append(note_id)
    return ids


def _note_source_options(area, collection_items, query=""):
    existing = set(_collection_note_ids(collection_items))
    notes = _fetch_notes(area, "date_modified", "desc", limit=50, offset=0)
    query = (query or "").strip().lower()
    options = []
    for note in notes:
        title = note.get("file_name") or note.get("title") or f"Note {note.get('id')}"
        haystack = f"{title} {note.get('path') or ''}".lower()
        if query and query not in haystack:
            continue
        options.append(
            {
                "id": note.get("id"),
                "title": title,
                "subtitle": note.get("path") or note.get("area") or "",
                "already_present": note.get("id") in existing,
            }
        )
    return options


def _notebook_continuous_entries(collection_items):
    entries = []
    for item in collection_items or []:
        if item.get("entry_kind") == "item" and item.get("item_type") == "note" and item.get("is_visible", True):
            summary = item.get("summary") or {}
            note_id = _safe_int(item.get("item_id"))
            note = _load_note_by_id(note_id) if note_id is not None else None
            text = ""
            if note:
                note_path = _build_note_path(note)
                if note_path and os.path.isfile(note_path):
                    text = _note_body_text(_read_note_file(note_path), note.get("file_name"), note.get("title"))
            entries.append(
                {
                    "title": item.get("display_title") or summary.get("title") or f"Note {item.get('item_id')}",
                    "text": text,
                    "open_url": summary.get("open_url") or "",
                }
            )
    return entries


def _load_note_by_id(note_id):
    tbl = get_table_def("notes")
    if not tbl:
        return None
    cols = ["id"] + tbl["col_list"]
    row = data._get_conn().execute(
        f"SELECT {', '.join(cols)} FROM {tbl['name']} WHERE id = ?",
        (note_id,),
    ).fetchone()
    return dict(row) if row else None


def _safe_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


@notes_bp.route('/notebooks', methods=["GET", "POST"])
def notes_collections_route():
    _ensure_notes_schema()
    collections_mod.ensure_collections_schema(data._get_conn())
    area = _normalize_area(request_area_param())
    area_info, area_folders = _area_context(area)
    area_label = area_info["area_name"] if area_info else area
    message = request.args.get("message", "")
    error = ""

    if request.method == "POST":
        action = request.form.get("action", "create")
        collection_id = request.form.get("collection_id", type=int)
        try:
            if action == "create":
                collection_id = collections_mod.create_collection(_notebook_form_values(request.form, area))
                message = "Notebook created."
            elif action == "save" and collection_id:
                collections_mod.update_collection(collection_id, _notebook_form_values(request.form, area))
                message = "Notebook saved."
            elif action == "archive" and collection_id:
                collections_mod.archive_collection(collection_id)
                message = "Notebook archived."
            elif action == "restore" and collection_id:
                collections_mod.restore_collection(collection_id)
                message = "Notebook restored."
            elif action == "delete" and collection_id:
                collections_mod.delete_collection(collection_id)
                return redirect(url_for("notes.notes_collections_route", area=area, message="Notebook deleted."))
            elif action == "add_note" and collection_id:
                collections_mod.add_item_to_collection(collection_id, "note", request.form.get("note_id"))
                message = "Note added."
            elif action == "add_heading" and collection_id:
                collections_mod.add_heading_to_collection(collection_id, request.form.get("title_override"))
                message = "Heading added."
            elif action == "add_divider" and collection_id:
                collections_mod.add_divider_to_collection(collection_id)
                message = "Divider added."
            elif action == "remove_entry":
                collections_mod.remove_item_from_collection(request.form.get("collection_item_id", type=int))
                message = "Entry removed."
            elif action in {"move_up", "move_down"}:
                collections_mod.move_collection_item(
                    request.form.get("collection_item_id", type=int),
                    direction="up" if action == "move_up" else "down",
                )
                message = "Entry moved."
        except ValueError as exc:
            error = str(exc)
        args = {"area": area, "message": message}
        if collection_id:
            args["collection_id"] = collection_id
        if error:
            args["error"] = error
        return redirect(url_for("notes.notes_collections_route", **args))

    error = request.args.get("error", "")
    active_status = (request.args.get("status") or "").strip().lower()
    include_archived = active_status == "all"
    collection_type = request.args.get("type") or ""
    selected_collection_id = request.args.get("collection_id", type=int)
    notebooks = collections_mod.get_collection_list(
        domain="notes",
        collection_type=collection_type or None,
        area_id=area,
        include_archived=include_archived,
    )
    selected = None
    if selected_collection_id:
        selected = collections_mod.get_collection(selected_collection_id)
    collection_items = collections_mod.get_collection_items(selected["collection_id"]) if selected else []
    source_query = request.args.get("q", "")
    reading_mode = request.args.get("read") == "1"
    context = _notes_list_context(
        area=area,
        folder_filter="",
        area_info=area_info,
        area_folders=area_folders,
        area_label=area_label,
        total=len(notebooks),
        sort_col="date_modified",
        sort_dir="desc",
        route_name="notes.notes_collections_route",
        view_mode="collections",
        page=1,
        total_pages=1,
        pages=[],
        first_url=url_for("notes.notes_collections_route", area=area),
        last_url=url_for("notes.notes_collections_route", area=area),
        note_settings=_note_display_settings(),
    )
    context.update(
        {
            "content_title": f"Notebooks ({area_label or 'All Areas'})",
            "collections": notebooks,
            "selected_collection": selected,
            "collection_items": collection_items,
            "source_notes": _note_source_options(area, collection_items, source_query) if selected else [],
            "continuous_entries": _notebook_continuous_entries(collection_items) if selected and reading_mode else [],
            "reading_mode": reading_mode,
            "message": message,
            "error": error,
            "active_status": active_status,
            "type_options": collections_mod.collection_type_options("notes"),
            "area_options": collections_mod.area_options(selected.get("area_ids") if selected else ([area] if area else [])),
            "project_options": collections_mod.project_options(selected.get("project_ids") if selected else []),
            "source_query": source_query,
        }
    )
    resp = make_response(render_template("notes_collections.html", **context))
    resp.set_cookie("notes_view", "collections")
    return resp

@notes_bp.route('/view/<int:note_id>')
def view_note_route(note_id):
    if not security.can_view_note(note_id, current_user):
        abort(404)
    render_mode = _normalize_note_view_mode(request.args.get("format") or request.args.get("view"))
    note_settings = _note_display_settings()
    _ensure_notes_schema()
    tbl = get_table_def("notes")
    note = None
    areas_mod.ensure_areas_schema(data._get_conn())
    if tbl:
        select_cols = [f"t.{col}" for col in (["id"] + tbl["col_list"])]
        select_cols.append("t.rec_extract_date as updated")
        select_cols.append(f"{_derived_area_expr()} as derived_area")
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
            _apply_note_display_fields(note)
    if not note:
        return redirect(url_for("notes.list_notes_route"))
    note_path = _build_note_path(note)
    note_folder = _normalize_folder_filter(note.get("path"))
    file_exists = note_path and os.path.isfile(note_path)
    note_text = ""
    if file_exists:
        note_text = _read_note_file(note_path)
        note_state = _note_file_state(note_path)
        if note_state:
            note["size"] = note_state["size"]
            note["date_modified"] = note_state["date_modified"]
        note_metadata = _note_metadata_from_file(note_path, fallback_area=note.get("area") or "")
        for key in ("title", "color", "date_created", "area", "important", "source_note_id"):
            if note_metadata.get(key):
                note[key] = note_metadata.get(key)
        _apply_note_display_fields(note)
    breadcrumb_area = note.get("area") or note.get("derived_area")
    note_body_text = _note_body_text(note_text, note.get("file_name"), note.get("title"))
    front_matter_raw = _front_matter_block_text(note_text)
    front_matter = _parse_note_front_matter_text(note_text) if front_matter_raw else {}
    content_html = ""
    hex_rows = []
    sample_text = ""
    if render_mode == "markdown":
        def _asset_url(asset_name):
            return url_for("notes.note_asset_route", note_id=note_id, asset_path=asset_name)

        content_html = markdown_utils.render_markdown(
            note_body_text,
            asset_resolver=_asset_url,
            wiki_link_resolver=_resolve_note_wiki_link,
            link_resolver=lambda target, current_note=note: _resolve_markdown_note_link(current_note, target),
        )
    elif render_mode == "hex":
        hex_rows = hex_utils.hex_dump(note_text)
    elif render_mode == "sample":
        sample_text = _sample_note_text(note_body_text, note_settings["sample_lines"])
    active_areas = areas_mod.areas_list_sidebar()
    selected_area = note.get("area") or note.get("derived_area") or ""
    if selected_area and not any(area.get("area_id") == selected_area for area in active_areas):
        active_areas.insert(
            0,
            {
                "area_id": selected_area,
                "area_name": selected_area,
            },
        )
    return render_template(
        "note_view.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        note=note,
        content_title="Notes",
        content_html="",
        render_mode=render_mode,
        content_html_rendered=content_html,
        hex_rows=hex_rows,
        note_text=note_text,
        note_body_text=note_body_text,
        sample_text=sample_text,
        file_exists=file_exists,
        note_path=note_path,
        note_breadcrumb=_note_folder_breadcrumb(note_folder, breadcrumb_area),
        active_areas=active_areas,
        selected_area=selected_area,
        color_options=_note_color_options(note.get("color")),
        view_modes=[
            ("text", "Text"),
            ("markdown", "Markdown"),
            ("hex", "Hex"),
            ("sample", "Sample"),
            ("metadata", "Metadata"),
        ],
        note_metadata_rows=_note_metadata_rows(note, note_path, file_exists),
        front_matter_items=list(front_matter.items()),
        front_matter_raw=front_matter_raw,
        sample_lines=note_settings["sample_lines"],
        message=request.args.get("message", ""),
        project_options=projects_mod.project_list(statuses=("planned", "active")),
        record_projects=projects_mod.record_projects("note", note_id),
    )


@notes_bp.route('/asset/<int:note_id>/<path:asset_path>')
def note_asset_route(note_id, asset_path):
    if not security.can_view_note(note_id, current_user):
        abort(404)
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
    full_path = _resolve_note_asset_path(note, asset_path, note_path=note_path)
    if not full_path:
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


def _safe_area_short_name(area_id):
    raw = (area_id or "note").strip().split("/")[-1].split(".")[-1]
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
            r'(?m)^title:\s*(?:"(?:\\"|[^"])*"|[^\r\n]*)\s*$',
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


def _update_note_file_metadata(note_id, note, file_name, folder_path, area=None, content=None):
    tbl = get_table_def("notes")
    if not tbl:
        return False
    _ensure_notes_schema()
    note_path = os.path.join(folder_path, file_name)
    try:
        stat = os.stat(note_path)
        size = str(stat.st_size)
        date_modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        stat = None
        size = note.get("size") or ""
        date_modified = note.get("date_modified") or ""
    metadata = _note_metadata_from_file(note_path, stat=stat, fallback_area=area or note.get("area") or "")
    values_map = {col: note.get(col, "") for col in tbl["col_list"]}
    values_map.update(
        {
            "file_name": file_name,
            "path": folder_path,
            "size": size,
            "title": metadata.get("title") or values_map.get("title") or os.path.splitext(file_name)[0],
            "color": metadata.get("color") or values_map.get("color", ""),
            "date_created": metadata.get("date_created") or values_map.get("date_created", ""),
            "date_modified": date_modified,
            "area": metadata.get("area") or values_map.get("area", ""),
            "important": metadata.get("important") or values_map.get("important", ""),
            "source_note_id": metadata.get("source_note_id") or values_map.get("source_note_id", ""),
        }
    )
    if area is not None:
        values_map["area"] = area
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    ok = data.update_record(data._get_conn(), tbl["name"], note_id, tbl["col_list"], values)
    if ok:
        _set_note_folder_id(data._get_conn(), tbl["name"], note_id, folder_path)
        try:
            note_search_index.upsert_note(
                note_id,
                note_path,
                title=values_map.get("title") or file_name,
                content=content,
                conn=data._get_conn(),
            )
        except Exception:
            pass
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


def _move_note_to_area(note_id, area_id):
    note, _ = _get_note_record(note_id)
    if not note:
        raise ValueError("Note not found.")
    note_path = _build_note_path(note)
    if not note_path or not os.path.isfile(note_path):
        raise ValueError("Note file not found.")
    area_id = (area_id or "").strip()
    if not area_id:
        raise ValueError("Area is required.")
    target_folder = areas_mod.area_default_folder_get(area_id)
    if not target_folder:
        raise ValueError("Selected area has no default folder.")
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
    _update_note_file_metadata(note_id, note, moved_name, target_folder, area=area_id)
    return target_path


def _assign_note_area(note_id, area_id):
    note, tbl = _get_note_record(note_id)
    if not note or not tbl:
        raise ValueError("Note not found.")
    area_id = utils_normalize_area_param(area_id)
    if not area_id:
        raise ValueError("Area is required.")
    owner_user_id = _current_owner_user_id()
    if not areas_mod.area_get(area_id, owner_user_id=owner_user_id):
        raise ValueError("Selected area was not found.")

    note_path = _build_note_path(note)
    folder_path = _normalize_note_path(note.get("path")) or (os.path.dirname(note_path) if note_path else "")
    file_name = note.get("file_name") or (os.path.basename(note_path) if note_path else "")
    content = None
    if note_path and os.path.isfile(note_path):
        _set_note_front_matter_field(note_path, "area", area_id, aliases=["area_id", "folder", "sidebar_tab", "project", "project_id", "proj"])
        content = _read_note_file(note_path)
        if folder_path and file_name:
            return _update_note_file_metadata(note_id, note, file_name, folder_path, area=area_id, content=content)

    values_map = {col: note.get(col, "") for col in tbl["col_list"]}
    values_map["area"] = area_id
    values = [values_map.get(col, "") for col in tbl["col_list"]]
    return data.update_record(data._get_conn(), tbl["name"], note_id, tbl["col_list"], values)


def _set_note_color(note_id, color):
    note, _ = _get_note_record(note_id)
    if not note:
        raise ValueError("Note not found.")
    note_path = _build_note_path(note)
    if not note_path or not os.path.isfile(note_path):
        raise ValueError("Note file not found.")
    color = (color or "").strip()
    allowed = {label.lower() for label, _style in NOTE_COLOR_OPTIONS}
    if color.lower() not in allowed and not NOTE_COLOR_HEX_RE.match(color):
        raise ValueError("Select a valid note color.")
    updated_state = _set_note_front_matter_field(note_path, "color", color, aliases=["colour"])
    folder_path = _normalize_note_path(note.get("path")) or os.path.dirname(note_path)
    file_name = note.get("file_name") or os.path.basename(note_path)
    content = _read_note_file(note_path)
    _update_note_file_metadata(note_id, note, file_name, folder_path, content=content)
    return updated_state


def _derived_area_for_note_id(note_id):
    tbl = get_table_def("notes")
    if not tbl:
        return ""
    try:
        row = data._get_conn().execute(
            f"SELECT {_derived_area_expr()} AS derived_area "
            f"FROM {tbl['name']} t "
            "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
            "WHERE t.id = ?",
            (note_id,),
        ).fetchone()
    except Exception:
        return ""
    return (row["derived_area"] or "") if row else ""


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
        area_id = note.get("area") or _derived_area_for_note_id(note_id)
        short_area = _safe_area_short_name(area_id)
        stem = _note_title_from_filename(note.get("file_name"))
        safe_stem = INVALID_TITLE_CHARS.sub("", stem)
        safe_stem = WHITESPACE_RE.sub("_", safe_stem).strip("._ ") or "note"
        stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        archive_name = f"{short_area}__{safe_stem}_{stamp}.md"
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
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    render_mode = _normalize_note_view_mode(request.form.get("return_format"))
    try:
        _rename_note(note_id, request.form.get("new_title", ""))
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode, message=f"Rename failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode))


@notes_bp.route('/move/<int:note_id>', methods=["POST"])
def move_note_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    render_mode = _normalize_note_view_mode(request.form.get("return_format"))
    area_id = utils_normalize_area_param(
        request.form.get("area_id") or request.form.get("project_id") or request.form.get("area") or request.form.get("project") or ""
    )
    action = (request.form.get("action") or "assign").strip()
    try:
        if action == "move_file":
            _move_note_to_area(note_id, area_id)
            message = "Moved note file to selected Area."
        else:
            _assign_note_area(note_id, area_id)
            message = "Assigned note to selected Area."
    except Exception as exc:
        label = "Move" if action == "move_file" else "Assign"
        return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode, message=f"{label} failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode, message=message))


@notes_bp.route('/color/<int:note_id>', methods=["POST"])
def update_note_color_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    render_mode = _normalize_note_view_mode(request.form.get("return_format"))
    try:
        _set_note_color(note_id, request.form.get("color", ""))
    except Exception as exc:
        return redirect(url_for(
            "notes.view_note_route",
            note_id=note_id,
            format=render_mode,
            message=f"Color update failed: {exc}",
        ))
    return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode))


@notes_bp.route('/archive-delete/<int:note_id>', methods=["POST"])
def archive_delete_note_route(note_id):
    if not security.can_delete_note(note_id, current_user):
        abort(403)
    try:
        _archive_and_delete_note(note_id)
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Delete failed: {exc}"))
    return redirect(url_for("notes.list_notes_route"))


@notes_bp.route('/api/delete-selected', methods=["POST"])
def delete_selected_notes_route():
    payload = request.get_json(silent=True) or {}
    note_ids = []
    for raw_id in payload.get("note_ids") or []:
        try:
            note_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    note_ids = list(dict.fromkeys(note_ids))
    if not note_ids:
        return jsonify({"deleted": 0, "deleted_ids": [], "errors": []})
    deleted = 0
    deleted_ids = []
    errors = []
    for note_id in note_ids:
        if not security.can_delete_note(note_id, current_user):
            errors.append({"note_id": note_id, "error": "forbidden"})
            continue
        try:
            _archive_and_delete_note(note_id)
            deleted += 1
            deleted_ids.append(note_id)
        except Exception as exc:
            errors.append({"note_id": note_id, "error": str(exc)})
    status = 207 if errors and deleted else (403 if errors else 200)
    return jsonify({"deleted": deleted, "deleted_ids": deleted_ids, "errors": errors}), status


@notes_bp.route('/api/move-selected', methods=["POST"])
def move_selected_notes_route():
    payload = request.get_json(silent=True) or {}
    area_id = utils_normalize_area_param(
        payload.get("area_id") or payload.get("project_id") or payload.get("area") or payload.get("project") or ""
    )
    note_ids = []
    for raw_id in payload.get("note_ids") or []:
        try:
            note_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    note_ids = list(dict.fromkeys(note_ids))
    if not note_ids:
        return jsonify({"moved": 0, "moved_ids": [], "errors": []})
    moved = 0
    moved_ids = []
    errors = []
    for note_id in note_ids:
        if not security.can_edit_note(note_id, current_user):
            errors.append({"note_id": note_id, "error": "forbidden"})
            continue
        try:
            _move_note_to_area(note_id, area_id)
            moved += 1
            moved_ids.append(note_id)
        except Exception as exc:
            errors.append({"note_id": note_id, "error": str(exc)})
    status = 207 if errors and moved else (403 if errors else 200)
    return jsonify({"moved": moved, "moved_ids": moved_ids, "errors": errors}), status


@notes_bp.route('/api/color-selected', methods=["POST"])
def color_selected_notes_route():
    payload = request.get_json(silent=True) or {}
    color = (payload.get("color") or "").strip()
    note_ids = []
    for raw_id in payload.get("note_ids") or []:
        try:
            note_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    note_ids = list(dict.fromkeys(note_ids))
    if not note_ids:
        return jsonify({"updated": 0, "updated_ids": [], "errors": []})
    updated = 0
    updated_ids = []
    errors = []
    for note_id in note_ids:
        if not security.can_edit_note(note_id, current_user):
            errors.append({"note_id": note_id, "error": "forbidden"})
            continue
        try:
            _set_note_color(note_id, color)
            updated += 1
            updated_ids.append(note_id)
        except Exception as exc:
            errors.append({"note_id": note_id, "error": str(exc)})
    status = 207 if errors and updated else (403 if errors else 200)
    return jsonify({"updated": updated, "updated_ids": updated_ids, "errors": errors}), status


@notes_bp.route('/convert-to-howto/<int:note_id>', methods=["POST"])
def convert_note_to_howto_route(note_id):
    if not security.can_delete_note(note_id, current_user):
        abort(403)
    note, tbl = _get_note_record(note_id)
    if not note or not tbl:
        return redirect(url_for("notes.list_notes_route"))
    note_path = _build_note_path(note)
    markdown = _read_note_file(note_path) if note_path else ""
    if not markdown:
        markdown = ""
    title = os.path.splitext(note.get("file_name") or "")[0] or "Converted Note"
    area_id = note.get("area") or ""
    conn = data._get_conn()
    try:
        conn.execute("BEGIN")
        howto_id = how_service.create_howto_from_markdown(
            title,
            markdown,
            area_id=area_id,
            source_filepath=note_path,
            conn=conn,
        )
        conn.execute(f"DELETE FROM {tbl['name']} WHERE id = ?", (note_id,))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return redirect(url_for("notes.view_note_route", note_id=note_id, message=f"Convert to HOWTO failed: {exc}"))
    return redirect(url_for("how.view_how_route", item_id=howto_id, area=area_id))


@notes_bp.route('/open-folder/<int:note_id>', methods=["POST"])
def open_note_folder_route(note_id):
    if not security.can_view_note(note_id, current_user):
        abort(403)
    render_mode = _normalize_note_view_mode(request.form.get("return_format"))
    note, _ = _get_note_record(note_id)
    if not note:
        abort(404)
    try:
        _open_note_folder(note)
    except Exception as exc:
        return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode, message=f"Open folder failed: {exc}"))
    return redirect(url_for("notes.view_note_route", note_id=note_id, format=render_mode))


@notes_bp.route('/api/new-note-options')
def new_note_options_route():
    area_id = request_area_param(include_id=True)
    area = areas_mod.area_get(area_id) if area_id else None
    if area_id and not area:
        return jsonify({"error": "Area not found."}), 404
    folders = areas_mod.area_folders_list(area_id, include_disabled=False)
    default_folder = None
    try:
        default_path = areas_mod.area_default_folder_get(area_id)
        if default_path:
            default_folder = {"path_prefix": default_path}
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    if not default_folder and not _uses_area_folder_mapping():
        notes_root = _current_user_notes_root(create_dirs=False)
        if notes_root:
            default_folder = {"path_prefix": notes_root, "is_user_notes_root": True}
    if not default_folder and not area_id:
        notes_root = _current_user_notes_root(create_dirs=False)
        if notes_root:
            default_folder = {"path_prefix": notes_root, "is_user_notes_root": True}
    return jsonify({
        "area": area,
        "default_folder": default_folder,
        "folders": folders,
    })


def _note_create_target_folder(area_id, path_prefix=""):
    area_id = (area_id or "").strip()
    path_prefix = _normalize_note_path(path_prefix)
    if not area_id or area_id.lower() == "unmapped":
        return _current_user_notes_root(create_dirs=True), ""
    owner_user_id = _current_owner_user_id()
    if not areas_mod.area_get(area_id, owner_user_id=owner_user_id):
        raise ValueError("Area not found.")
    try:
        default_path = areas_mod.area_default_folder_get(area_id, owner_user_id=owner_user_id) or ""
    except ValueError:
        raise
    if default_path:
        default_path = _normalize_note_path(default_path)
        if path_prefix and path_prefix.lower() != default_path.lower():
            raise ValueError("Notes can only be created in the default folder for this area.")
        return default_path, area_id
    if _uses_area_folder_mapping():
        raise ValueError("No default folder set for this area.")
    return _current_user_notes_root(create_dirs=True), area_id


@notes_bp.route('/api/create-note', methods=["POST"])
def create_note_route():
    payload = request.get_json(silent=True) or {}
    area_id = utils_normalize_area_param(
        payload.get("area_id") or payload.get("project_id") or payload.get("area") or payload.get("project") or ""
    )
    title = (payload.get("title") or "").strip()
    path_prefix = (payload.get("path_prefix") or "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400
    try:
        path_prefix, area_id = _note_create_target_folder(area_id, path_prefix)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not path_prefix:
        return jsonify({"error": "Folder path is required."}), 400
    try:
        created = _create_note_file(path_prefix, title, area_id)
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
        stat = os.stat(created["full_path"])
        date_modified = datetime.fromtimestamp(
            stat.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        size = ""
        stat = None
        date_modified = ""
    metadata = _note_metadata_from_file(created["full_path"], stat=stat, fallback_area=area_id)

    values_map = {
        "file_name": created["file_name"],
        "path": created["folder_path"],
        "folder_id": "",
        "size": size,
        "title": metadata.get("title") or created["title"],
        "color": metadata.get("color") or DEFAULT_NOTE_COLOR,
        "date_created": metadata.get("date_created") or created["created_utc"],
        "date_modified": date_modified,
        "area": metadata.get("area") or area_id,
        "important": metadata.get("important") or "",
        "source_note_id": metadata.get("source_note_id") or "",
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
    _ensure_notes_schema()
    tbl = get_table_def("notes")
    area = request_area_param("General") or "General"
    if request.method == "POST" and tbl:
        form_values = {col: request.form.get(col, "").strip() for col in tbl["col_list"]}
        if not form_values.get("area"):
            form_values["area"] = area
        note_path = _build_note_path(form_values)
        if note_path and os.path.isfile(note_path):
            try:
                stat = os.stat(note_path)
            except OSError:
                stat = None
            metadata = _note_metadata_from_file(note_path, stat=stat, fallback_area=form_values.get("area") or area)
            for key in ("title", "color", "date_created", "area", "important", "source_note_id"):
                if not form_values.get(key):
                    form_values[key] = metadata.get(key) or ""
            if not form_values.get("size"):
                form_values["size"] = str(stat.st_size) if stat is not None else str(os.path.getsize(note_path))
            if not form_values.get("date_modified"):
                form_values["date_modified"] = datetime.fromtimestamp(
                    stat.st_mtime if stat is not None else os.path.getmtime(note_path)
                ).strftime("%Y-%m-%d %H:%M:%S")
        values = [form_values.get(col, "") for col in tbl["col_list"]]
        data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        return redirect(url_for("notes.list_notes_route", area=area))
    return render_template(
        "note_edit.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Add Note",
        note=None,
        area=area,
    )

@notes_bp.route('/edit/<int:note_id>', methods=["GET", "POST"])
def edit_note_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    note, tbl = _get_note_record(note_id)
    if request.method == "POST":
        content = request.form.get("content")
        if content is not None and note:
            note_path = _build_note_path(note)
            if note_path and not os.path.isdir(note_path):
                try:
                    _write_note_file_content(note_path, content)
                    _update_note_file_metadata(
                        note_id,
                        note,
                        note.get("file_name") or os.path.basename(note_path),
                        _normalize_note_path(note.get("path")) or os.path.dirname(note_path),
                        content=content,
                    )
                    _sync_note_links(note_id, content)
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
        note_metadata = _note_metadata_from_file(note_path, fallback_area=note.get("area") or "")
        for key in ("title", "color", "date_created", "area", "important", "source_note_id"):
            if note_metadata.get(key):
                note[key] = note_metadata.get(key)
        _apply_note_display_fields(note)
    note_folder = _normalize_folder_filter(note.get("path")) if note else ""
    breadcrumb_area = note.get("derived_area") or note.get("area") if note else None
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
        note_breadcrumb=_note_folder_breadcrumb(note_folder, breadcrumb_area),
        content_title=f"Edit: {note.get('file_name')}" if note else "Edit Note",
        project_options=projects_mod.project_list(statuses=("planned", "active")) if note else [],
        record_projects=projects_mod.record_projects("note", note_id) if note else [],
    )

@notes_bp.route('/api/save/<int:note_id>', methods=["POST"])
def save_note_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
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
        _update_note_file_metadata(
            note_id,
            note,
            note.get("file_name") or os.path.basename(note_path),
            _normalize_note_path(note.get("path")) or os.path.dirname(note_path),
            content=content,
        )
    link_count = _sync_note_links(note_id, content)

    return jsonify({
        "ok": True,
        "size": size,
        "date_modified": date_modified,
        "mtime_ns": mtime_ns,
        "sha256": sha256,
        "link_count": link_count,
    })


@notes_bp.route('/api/upload-image/<int:note_id>', methods=["POST"])
def upload_note_image_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    note, _ = _get_note_record(note_id)
    if not note:
        return jsonify({"error": "Note not found."}), 404
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return jsonify({"error": "No image selected."}), 400
    try:
        filename = _safe_note_attachment_filename(upload.filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    note_path = _build_note_path(note)
    folder_path, relative_folder = _note_attachment_target(note, note_path=note_path)
    if not folder_path or not relative_folder:
        return jsonify({"error": "Note attachment folder is unavailable."}), 400
    try:
        os.makedirs(folder_path, exist_ok=True)
        target_path = _unique_attachment_path(folder_path, filename)
        upload.save(target_path)
    except OSError as exc:
        return jsonify({"error": f"Unable to save image: {exc}"}), 500
    link_path = relative_folder.rstrip("/") + "/" + os.path.basename(target_path)
    link_path = link_path.replace("\\", "/")
    return jsonify({
        "ok": True,
        "path": link_path,
        "markdown": f"![image]({link_path})",
        "obsidian": f"![[{link_path}]]",
    })


@notes_bp.route('/api/wiki-search')
def wiki_search_route():
    query = request.args.get("q", "")
    exclude_note_id = request.args.get("exclude_id", type=int)
    limit = request.args.get("limit", type=int) or 20
    return jsonify({"results": _search_wiki_notes(query, exclude_note_id=exclude_note_id, limit=limit)})


@notes_bp.route('/api/wiki-preview/<int:note_id>', methods=["POST"])
def wiki_preview_route(note_id):
    if not security.can_edit_note(note_id, current_user):
        abort(403)
    payload = request.get_json(silent=True) or {}
    content = payload.get("content") or ""
    note, _tbl = _get_note_record(note_id)
    if not note:
        return jsonify({"error": "Note not found."}), 404

    def _asset_url(asset_name):
        return url_for("notes.note_asset_route", note_id=note_id, asset_path=asset_name)

    html_rendered = markdown_utils.render_markdown(
        content,
        asset_resolver=_asset_url,
        wiki_link_resolver=_resolve_note_wiki_link,
        link_resolver=lambda target, current_note=note: _resolve_markdown_note_link(current_note, target),
    )
    return jsonify({"html": html_rendered})

@notes_bp.route('/delete/<int:note_id>')
def delete_note_route(note_id):
    if not security.can_delete_note(note_id, current_user):
        abort(403)
    try:
        _archive_and_delete_note(note_id)
    except Exception:
        pass
    return redirect(url_for("notes.list_notes_route"))


@notes_bp.route('/import', methods=["GET", "POST"])
def import_notes_route():
    area = request_area_param() or ""
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
                if choice == "{curr_area_selected}":
                    choice = area
                map_list.append(choice)
            try:
                importer.set_token("curr_area_selected", area)
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
        area=area,
        table_def=tbl,
        csv_path=csv_path,
        csv_headers=headers,
        mappings=mappings,
        imported=imported,
        error=error,
    )


@notes_bp.route('/import-folder', methods=["GET", "POST"])
def import_notes_folder_route():
    area = request_area_param() or ""
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
            rows = _collect_note_import_rows(folder_path, area)
            imported = _insert_note_import_rows(tbl, rows)
    return render_template(
        "notes_import_folder.html",
        active_tab="notes",
        tabs=get_tabs(),
        side_tabs=get_side_tabs(),
        content_title="Import Notes Folder",
        content_html="",
        area=area,
        imported=imported,
        error=error,
    )


def _collect_note_import_rows(folder_path, area):
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
            metadata = _note_metadata_from_file(full_path, stat=stat, fallback_area=area)
            rows.append(
                {
                    "file_name": name,
                    "path": root,
                    "size": str(stat.st_size),
                    "title": metadata.get("title") or os.path.splitext(name)[0],
                    "color": metadata.get("color") or "",
                    "date_created": metadata.get("date_created") or "",
                    "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "area": metadata.get("area") or area,
                    "important": metadata.get("important") or "",
                    "source_note_id": metadata.get("source_note_id") or "",
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


def _sync_area_fallbacks(conn, owner_user_id=None):
    try:
        areas_mod.ensure_areas_schema(conn)
        rows = conn.execute(
            "SELECT area_id, path_prefix, folder_role, sort_order "
            "FROM lp_area_folders "
            "WHERE owner_user_id IS ? "
            "AND is_enabled = 1 "
            "AND folder_role IN ('default','include','archive','output')",
            (owner_user_id,),
        ).fetchall()
    except Exception:
        return []
    priority = {"default": 0, "include": 1, "output": 2, "archive": 3}
    fallbacks = []
    for row in rows:
        path_prefix = _normalize_note_path(row["path_prefix"])
        area_id = (row["area_id"] or "").strip()
        if not path_prefix or not area_id:
            continue
        fallbacks.append(
            {
                "area_id": area_id,
                "path_prefix": path_prefix,
                "folder_role": row["folder_role"] or "",
                "sort_order": row["sort_order"] or 100,
            }
        )
    fallbacks.sort(
        key=lambda item: (
            -len(item["path_prefix"]),
            priority.get(item["folder_role"], 9),
            item["sort_order"],
            item["area_id"],
        )
    )
    return fallbacks


def _sync_area_for_path(folder_path, fallbacks):
    folder_path = _normalize_note_path(folder_path)
    for item in fallbacks or []:
        if _path_startswith(folder_path, item["path_prefix"]):
            return item["area_id"]
    return ""


def _note_owner_filter(owner_user_id, table_columns):
    if "owner_user_id" not in table_columns:
        return "", []
    if owner_user_id is None:
        return " AND t.owner_user_id IS NULL", []
    return " AND t.owner_user_id = ?", [owner_user_id]


def materialize_note_areas(conn=None, owner_user_id=None, force=False):
    conn = data._get_conn() if conn is None else conn
    data.ensure_notes_schema(conn)
    tbl = get_table_def("notes")
    if not tbl or not _table_exists(conn, tbl["name"]):
        return {"scanned": 0, "updated": 0}
    table_columns = _table_columns(conn, tbl["name"])
    fallbacks = _sync_area_fallbacks(conn, owner_user_id)
    if not fallbacks:
        return {"scanned": 0, "updated": 0}
    where = ["1=1"]
    params = []
    if not force:
        where.append("COALESCE(t.area, '') = ''")
    owner_sql, owner_params = _note_owner_filter(owner_user_id, table_columns)
    if owner_sql:
        where.append(owner_sql[5:])
        params.extend(owner_params)
    has_dim_folder = _table_exists(conn, "dim_folder")
    folder_select = "df.folder_path" if has_dim_folder else "NULL AS folder_path"
    folder_join = "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id " if has_dim_folder else ""
    sql = (
        f"SELECT t.id, t.path, t.folder_id, t.area, {folder_select} "
        f"FROM {tbl['name']} t "
        f"{folder_join}"
        f"WHERE {' AND '.join(where)}"
    )
    rows = conn.execute(sql, params).fetchall()
    updates = []
    for row in rows:
        note_path = _normalize_note_path(row["path"] or row["folder_path"] or "")
        area_id = _sync_area_for_path(note_path, fallbacks)
        if area_id and (force or not (row["area"] or "").strip()):
            updates.append((area_id, row["id"]))
    if updates:
        conn.executemany(f"UPDATE {tbl['name']} SET area = ? WHERE id = ?", updates)
        conn.commit()
    return {"scanned": len(rows), "updated": len(updates)}


def refresh_note_color_metadata(conn=None, owner_user_id=None, only_blank=True):
    conn = data._get_conn() if conn is None else conn
    data.ensure_notes_schema(conn)
    tbl = get_table_def("notes")
    if not tbl or not _table_exists(conn, tbl["name"]):
        return {"scanned": 0, "updated": 0, "missing": 0, "no_color": 0, "invalid": 0}
    table_columns = _table_columns(conn, tbl["name"])
    if "color" not in table_columns:
        return {"scanned": 0, "updated": 0, "missing": 0, "no_color": 0, "invalid": 0}

    where = ["COALESCE(t.file_name, '') != ''"]
    params = []
    if only_blank:
        where.append("COALESCE(trim(t.color), '') = ''")
    owner_sql, owner_params = _note_owner_filter(owner_user_id, table_columns)
    if owner_sql:
        where.append(owner_sql[5:])
        params.extend(owner_params)

    has_dim_folder = _table_exists(conn, "dim_folder") and "folder_id" in table_columns
    folder_select = "df.folder_path AS folder_path" if has_dim_folder else "NULL AS folder_path"
    folder_join = "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id " if has_dim_folder else ""
    rows = conn.execute(
        f"SELECT t.id, t.file_name, t.path, t.color, {folder_select} "
        f"FROM {tbl['name']} t "
        f"{folder_join}"
        f"WHERE {' AND '.join(where)}",
        params,
    ).fetchall()

    updates = []
    missing = 0
    no_color = 0
    invalid = 0
    for row in rows:
        file_name = (row["file_name"] or "").strip()
        folder_path = _normalize_note_path(row["path"] or row["folder_path"] or "")
        if os.path.isabs(file_name):
            note_path = file_name
        elif folder_path and file_name:
            note_path = os.path.join(folder_path, file_name)
        else:
            note_path = folder_path or file_name
        front_matter = _try_read_note_front_matter(note_path)
        if front_matter is None:
            missing += 1
            continue
        color = _front_matter_value(front_matter, ("color", "colour")).strip()
        if not color:
            no_color += 1
            continue
        if not _note_color_style(color):
            invalid += 1
            continue
        if color != (row["color"] or "").strip():
            updates.append((color, row["id"]))

    if updates:
        conn.executemany(f"UPDATE {tbl['name']} SET color = ? WHERE id = ?", updates)
        conn.commit()
    return {
        "scanned": len(rows),
        "updated": len(updates),
        "missing": missing,
        "no_color": no_color,
        "invalid": invalid,
    }


def _ensure_note_areas_materialized(conn):
    owner_user_id = _current_owner_user_id()
    key = (id(conn), owner_user_id)
    if key in _NOTE_AREA_MATERIALIZED_KEYS:
        return {"scanned": 0, "updated": 0}
    result = materialize_note_areas(conn=conn, owner_user_id=owner_user_id, force=False)
    _NOTE_AREA_MATERIALIZED_KEYS.add(key)
    return result


def _sync_note_rows(folder_path, fallback_area=""):
    _ensure_notes_schema()
    folder_path = _normalize_note_path(folder_path)
    tbl = get_table_def("notes")
    if not tbl:
        raise ValueError("Notes table not found.")
    if not folder_path:
        raise ValueError("No folder provided.")
    if not os.path.isdir(folder_path):
        raise ValueError("Folder not found.")

    conn = data._get_conn()
    area_fallbacks = [] if fallback_area else _sync_area_fallbacks(conn, _current_owner_user_id())
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
            row_area = fallback_area or _sync_area_for_path(root_norm, area_fallbacks)
            metadata = _note_metadata_from_file(full_path, stat=stat, fallback_area=row_area)
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
                        "title": metadata.get("title") or os.path.splitext(name)[0],
                        "color": metadata.get("color") or current.get("color", ""),
                        "date_created": metadata.get("date_created") or current.get("date_created", ""),
                        "date_modified": date_modified,
                        "area": metadata.get("area") or current.get("area", ""),
                        "important": metadata.get("important") or current.get("important", ""),
                        "source_note_id": metadata.get("source_note_id") or current.get("source_note_id", ""),
                    }
                )
                needs_update = (
                    (current.get("file_name") or "") != name
                    or _normalize_note_path(current.get("path")).lower() != root_norm.lower()
                    or str(current.get("size") or "") != size
                    or str(current.get("title") or "") != str(values_map.get("title") or "")
                    or str(current.get("color") or "") != str(values_map.get("color") or "")
                    or str(current.get("date_created") or "") != str(values_map.get("date_created") or "")
                    or str(current.get("date_modified") or "") != date_modified
                    or str(current.get("area") or "") != str(values_map.get("area") or "")
                    or str(current.get("important") or "") != str(values_map.get("important") or "")
                    or str(current.get("source_note_id") or "") != str(values_map.get("source_note_id") or "")
                    or not _note_folder_id_matches(conn, current.get("folder_id"), root_norm)
                )
                if needs_update:
                    values = [values_map.get(col, "") for col in tbl["col_list"]]
                    if data.update_record(conn, tbl["name"], current["id"], tbl["col_list"], values):
                        _set_note_folder_id(conn, tbl["name"], current["id"], root_norm)
                        try:
                            note_search_index.upsert_note(
                                current["id"],
                                full_path,
                                title=values_map.get("title") or name,
                                conn=conn,
                                commit=False,
                            )
                        except Exception:
                            pass
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    try:
                        note_search_index.upsert_note(
                            current["id"],
                            full_path,
                            title=values_map.get("title") or name,
                            conn=conn,
                            commit=False,
                        )
                    except Exception:
                        pass
                    unchanged += 1
            else:
                values_map = {
                    "file_name": name,
                    "path": root_norm,
                    "folder_id": "",
                    "size": size,
                    "title": metadata.get("title") or os.path.splitext(name)[0],
                    "color": metadata.get("color") or "",
                    "date_created": metadata.get("date_created") or "",
                    "date_modified": date_modified,
                    "area": metadata.get("area") or "",
                    "important": metadata.get("important") or "",
                    "source_note_id": metadata.get("source_note_id") or "",
                }
                values = [values_map.get(col, "") for col in tbl["col_list"]]
                record_id = data.add_record(conn, tbl["name"], tbl["col_list"], values)
                if record_id:
                    _set_note_folder_id(conn, tbl["name"], record_id, root_norm)
                    try:
                        note_search_index.upsert_note(
                            record_id,
                            full_path,
                            title=values_map.get("title") or name,
                            conn=conn,
                            commit=False,
                        )
                    except Exception:
                        pass
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
        folder_path = _notes_root_path(create_dirs=True) or ""
    try:
        result = _sync_note_rows(folder_path)
        msg = _sync_notes_message(result)
    except Exception as exc:
        msg = f"Notes sync failed: {exc}"
    return redirect(url_for("admin.settings_route", tab="notes", message=msg))


@notes_bp.route('/sync-folder/<int:area_folder_id>', methods=["POST"])
def sync_area_folder_route(area_folder_id):
    folder = areas_mod.area_folder_get(area_folder_id)
    if not folder:
        abort(404)
    try:
        result = _sync_note_rows(folder.get("path_prefix") or "", fallback_area=folder.get("area_id") or "")
        msg = _sync_notes_message(result)
    except Exception as exc:
        msg = f"Notes folder sync failed: {exc}"
    next_url = request.form.get("next") or url_for("notes.list_notes_route", area=folder.get("area_id"))
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


def _rewrite_lp_area_folder_paths(conn, old_root, new_root):
    if not _table_exists(conn, "lp_area_folders"):
        return 0
    updated = 0
    rows = conn.execute(
        "SELECT area_folder_id, area_id, path_prefix FROM lp_area_folders "
        f"WHERE {_area_folder_owner_sql('lp_area_folders')} "
        "AND (lower(path_prefix) = lower(?) OR lower(path_prefix) LIKE lower(?))",
        (_normalize_note_path(old_root), _normalize_note_path(old_root) + "\\%"),
    ).fetchall()
    for row in rows:
        next_path = _replace_path_prefix(row["path_prefix"], old_root, new_root)
        if not next_path or next_path.lower() == (row["path_prefix"] or "").lower():
            continue
        try:
            conn.execute(
                "UPDATE lp_area_folders SET path_prefix = ?, updated_utc = ? WHERE area_folder_id = ?",
                (next_path, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), row["area_folder_id"]),
            )
            updated += 1
        except Exception:
            conflict = conn.execute(
                "SELECT area_folder_id FROM lp_area_folders "
                f"WHERE {_area_folder_owner_sql('lp_area_folders')} AND area_id = ? AND path_prefix = ?",
                (row["area_id"], next_path),
            ).fetchone()
            if conflict:
                conn.execute(
                    "DELETE FROM lp_area_folders WHERE area_folder_id = ?",
                    (row["area_folder_id"],),
                )
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
        rewritten += _rewrite_lp_area_folder_paths(conn, old_root, new_root)
    return rewritten


@notes_bp.route('/migrate-source', methods=["POST"])
def migrate_notes_source_route():
    folder_path = request.form.get("notes_folder", "").strip()
    folder_path = _normalize_note_path(folder_path)
    area = request_area_param(include_form=True)
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
        rows = _collect_note_import_rows(folder_path, area)
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
                    "area": area,
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
    return redirect(url_for("admin.admin_mapping_route", tab="migration", message=msg))


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


def _resolve_area_for_context(area_id):
    area_id = (area_id or "").strip()
    if not area_id:
        return None
    owner_user_id = _current_owner_user_id()
    area = areas_mod.area_get(area_id, owner_user_id=owner_user_id)
    if area:
        return area
    conn = data._get_conn()
    areas_mod.ensure_areas_schema(conn)
    row = conn.execute(
        "SELECT owner_user_id, area_id, icon, tab, group_name, area_name, "
        "is_header, is_system, status, tags, "
        "sort_order, pinned, notes, created_utc, updated_utc "
        "FROM lp_areas "
        "WHERE owner_user_id IS ? AND status = 'active' AND is_header = 0 "
        "AND (lower(area_id) = lower(?) OR lower(area_name) = lower(?)) "
        "ORDER BY CASE WHEN lower(area_id) = lower(?) THEN 0 ELSE 1 END, LENGTH(area_id), area_id "
        "LIMIT 1",
        (owner_user_id, area_id, area_id, area_id),
    ).fetchone()
    return dict(row) if row else None


def _area_context(area_id):
    if not area_id or area_id.lower() == "unmapped":
        return None, []
    area = _resolve_area_for_context(area_id)
    if not area:
        return None, []
    folders = areas_mod.area_folders_list(
        area["area_id"],
        include_disabled=True,
        owner_user_id=area.get("owner_user_id"),
    )
    return area, folders


def _sort_notes(notes, sort_col, sort_dir):
    if sort_col == "size":
        reverse = sort_dir == "desc"
        keyed = [(note, _parse_size(note.get("size"))) for note in notes]
        valid = [(note, size) for note, size in keyed if size is not None]
        invalid = [note for note, size in keyed if size is None]
        return [note for note, _size in sorted(valid, key=lambda item: item[1], reverse=reverse)] + invalid
    key_map = {
        "file_name": lambda n: (n.get("file_name") or "").lower(),
        "path": lambda n: (n.get("path") or "").lower(),
        "size": lambda n: _parse_size(n.get("size")) or 0,
        "title": lambda n: (n.get("title") or n.get("file_name") or "").lower(),
        "color": lambda n: (n.get("color") or "").lower(),
        "date_created": lambda n: _parse_datetime(n.get("date_created")) or datetime.min,
        "area": lambda n: (n.get("area") or "").lower(),
        "important": lambda n: (n.get("important") or "").lower(),
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


def _without_duplicate_title_heading(note_text, file_name, title=""):
    file_title = (file_name or "").strip()
    metadata_title = (title or "").strip()
    if not file_title and not metadata_title:
        return note_text
    title_stem, _ = os.path.splitext(file_title)
    title_values = {file_title.lower()}
    if title_stem:
        title_values.add(title_stem.lower())
    if metadata_title:
        title_values.add(metadata_title.lower())
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
        return None
    try:
        text = str(value).strip()
        return int(text) if text and text.isdigit() else None
    except (TypeError, ValueError):
        return None
