import json
import os
import tempfile

from common import config as cfg
from common import data as db
from common import projects as projects_mod
from modules.how.parser import normalize_name, parse_markdown, slug_key
from modules.how.schema import ensure_how_schema, utc_now


ALL_PROJECT_VALUES = {"", "any", "all", "ALL", "All", "spacer"}


def get_conn(conn=None):
    conn = db._get_conn() if conn is None else conn
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lp_howto'"
    ).fetchone()
    if not exists:
        ensure_how_schema(conn)
    return conn


def normalize_project(project):
    project = (project or "").strip()
    return "" if project in ALL_PROJECT_VALUES else project


def _dict(row):
    return dict(row) if row else None


def unique_howto_key(title, conn=None, exclude_howto_id=None):
    conn = get_conn(conn)
    base = slug_key(title)
    candidate = base
    suffix = 2
    params = [candidate]
    condition = "howto_key = ?"
    if exclude_howto_id:
        condition += " AND howto_id != ?"
        params.append(exclude_howto_id)
    while conn.execute(f"SELECT 1 FROM lp_howto WHERE {condition}", params).fetchone():
        candidate = f"{base}-{suffix}"
        suffix += 1
        params = [candidate]
        if exclude_howto_id:
            params.append(exclude_howto_id)
    return candidate


def _project_id_from_metadata(metadata, conn):
    project_id = (metadata.get("project_id") or "").strip()
    if project_id:
        if not projects_mod.project_get(project_id, conn=conn):
            return project_id, f"Unknown project_id '{project_id}'."
        return project_id, ""
    project_name = (metadata.get("project") or "").strip()
    if not project_name:
        return "", ""
    rows = conn.execute(
        "SELECT project_id FROM lp_projects "
        "WHERE lower(project_id) = lower(?) OR lower(project_name) = lower(?) "
        "ORDER BY LENGTH(project_id), project_id",
        (project_name, project_name),
    ).fetchall()
    if len(rows) == 1:
        return rows[0]["project_id"], ""
    if not rows:
        return "", f"Unknown project '{project_name}'."
    return "", f"Ambiguous project '{project_name}'."


def project_options(selected_project=""):
    conn = get_conn()
    selected_project = normalize_project(selected_project)
    options = []
    seen = set()
    for row in projects_mod.projects_side_tabs(conn=conn):
        project_id = (row.get("id") or row.get("proj") or "").strip()
        if not project_id or project_id in ALL_PROJECT_VALUES or row.get("is_header"):
            continue
        if project_id.lower() in {"unmapped", "spacer"}:
            continue
        if project_id in seen:
            continue
        seen.add(project_id)
        options.append(
            {
                "project_id": project_id,
                "label": row.get("label") or project_id,
                "folder": how_save_folder(project_id),
                "selected": project_id == selected_project,
            }
        )
    if selected_project and selected_project not in seen:
        options.insert(
            0,
            {
                "project_id": selected_project,
                "label": selected_project,
                "folder": how_save_folder(selected_project),
                "selected": True,
            },
        )
    if options and not any(opt["selected"] for opt in options):
        options[0]["selected"] = True
    return options


def _resolve_catalog_item(conn, table, id_col, key_col, name_col, item, project_id):
    key = getattr(item, key_col.replace("_key", "_key"), "") or ""
    if key:
        row = conn.execute(f"SELECT {id_col} FROM {table} WHERE {key_col} = ?", (key,)).fetchone()
        if row:
            item.resolution = "existing"
            item.matched_id = row[id_col]
        else:
            item.resolution = "new"
        return
    name = normalize_name(getattr(item, "name", "") or getattr(item, "instruction", ""))
    if not name:
        item.resolution = "invalid"
        return
    candidates = conn.execute(
        f"SELECT {id_col} FROM {table} "
        f"WHERE lower(trim({name_col})) = ? "
        "AND (project_id IS NULL OR project_id = '' OR project_id = ? OR ? = '')",
        (name, project_id, project_id),
    ).fetchall()
    if len(candidates) == 1:
        item.resolution = "existing"
        item.matched_id = candidates[0][id_col]
    elif len(candidates) == 0:
        item.resolution = "new"
    else:
        item.resolution = "ambiguous"


def _resolve_step(conn, step, project_id):
    if step.step_key:
        row = conn.execute("SELECT step_id FROM lp_howto_steps WHERE step_key = ?", (step.step_key,)).fetchone()
        if row:
            step.resolution = "existing"
            step.matched_id = row["step_id"]
        else:
            step.resolution = "new"
    else:
        # Safe first pass: inline steps are document-scoped unless explicitly keyed.
        step.resolution = "new"
    if step.child_howto_ref:
        row = conn.execute("SELECT howto_id FROM lp_howto WHERE howto_key = ?", (step.child_howto_ref,)).fetchone()
        if row:
            step.child_howto_id = row["howto_id"]
            step.child_resolution = "existing"
        else:
            step.child_resolution = "missing"


def build_preview_model(markdown, conn=None, title=None, project_id=None):
    conn = get_conn(conn)
    title = (title or "").strip()
    project_id = normalize_project(project_id)
    parsed = parse_markdown(markdown, default_title=title)
    if title:
        parsed.title = title
        parsed.metadata.pop("title", None)
        parsed.diagnostics = [d for d in parsed.diagnostics if d.code != "TITLE_REQUIRED"]
    if project_id:
        parsed.metadata["project_id"] = project_id
        parsed.metadata.pop("project", None)
    project_id, project_warning = _project_id_from_metadata(parsed.metadata, conn)
    if project_warning:
        parsed.diagnostics.append(type(parsed.diagnostics[0])("WARNING", project_warning) if parsed.diagnostics else _diag(project_warning))
    parsed.metadata["resolved_project_id"] = project_id
    for part in parsed.parts:
        _resolve_catalog_item(conn, "lp_howto_parts", "part_id", "part_key", "part_name", part, project_id)
    for tool in parsed.tools:
        _resolve_catalog_item(conn, "lp_howto_tools_needed", "tool_id", "tool_key", "tool_name", tool, project_id)
    for step in parsed.steps:
        _resolve_step(conn, step, project_id)
        if step.child_howto_ref and step.child_howto_ref == (parsed.metadata.get("key") or ""):
            parsed.diagnostics.append(_diag("Direct self-reference is not allowed.", step.source_line, "SELF_REFERENCE", "ERROR"))
        elif step.child_resolution == "missing":
            parsed.diagnostics.append(_diag(f"Linked How-to '{step.child_howto_ref}' does not exist.", step.source_line, "CHILD_MISSING", "WARNING"))
        if step.child_mode and step.child_mode not in {"linked", "reference"}:
            parsed.diagnostics.append(_diag(f"Unknown child mode '{step.child_mode}' stored without special behavior.", step.source_line, "MODE_UNKNOWN", "WARNING"))
    fatal = any(d.severity == "ERROR" for d in parsed.diagnostics)
    status = "ERROR" if fatal else ("WARNING" if parsed.diagnostics else "OK")
    return {"status": status, "parsed": parsed.to_dict()}


def _diag(message, source_line=None, code="", severity="WARNING"):
    from modules.how.parser import Diagnostic

    return Diagnostic(severity, message, source_line, code)


def _preview_has_blockers(preview):
    diagnostics = preview["parsed"].get("diagnostics", [])
    if any(d.get("severity") == "ERROR" for d in diagnostics):
        return True
    for group in ("parts", "tools", "steps"):
        if any(item.get("resolution") in {"ambiguous", "invalid"} for item in preview["parsed"].get(group, [])):
            return True
    return False


def _default_how_root():
    return os.path.join(getattr(cfg, "data_folder", getattr(cfg, "user_folder", ".")), "how")


def _safe_file_name(title_or_key, slug=True):
    base = slug_key(title_or_key) if slug else _sanitize_file_stem(title_or_key)
    return f"{base}.md"


def _sanitize_file_stem(value):
    text = (value or "").strip()
    text = os.path.splitext(text)[0]
    cleaned = "".join(ch if ch.isalnum() or ch in {" ", "-", "_"} else "-" for ch in text)
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned or "Untitled How-to"


def how_save_folder(project_id):
    project_id = normalize_project(project_id)
    if project_id:
        try:
            default_folder = projects_mod.project_default_folder_get(project_id)
            if default_folder:
                return default_folder
        except Exception:
            pass
    folder_project = project_id.replace("/", os.sep) if project_id else "all"
    return os.path.join(_default_how_root(), folder_project)


def _source_path_for(parsed, source_filepath=None, blueprint_name=None):
    source_filepath = (source_filepath or "").strip()
    if source_filepath:
        return source_filepath
    project_id = parsed["metadata"].get("resolved_project_id") or ""
    folder = how_save_folder(project_id)
    return os.path.join(folder, _safe_file_name(blueprint_name or parsed["title"], slug=False))


def _atomic_write(path, content):
    folder = os.path.dirname(path)
    if not folder:
        folder = os.getcwd()
        path = os.path.join(folder, path)
    os.makedirs(folder, exist_ok=True)
    temp_path = None
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=folder, prefix=".how.", suffix=".tmp", delete=False) as handle:
        temp_path = handle.name
        handle.write(content)
    os.replace(temp_path, path)


def _upsert_howto(conn, parsed, source_filepath):
    now = utc_now()
    metadata = parsed["metadata"]
    howto_key = metadata.get("key") or slug_key(parsed["title"])
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    row = conn.execute("SELECT howto_id FROM lp_howto WHERE howto_key = ?", (howto_key,)).fetchone()
    values = (
        howto_key,
        parsed["title"],
        metadata.get("resolved_project_id") or "",
        parsed.get("summary") or "",
        parsed.get("outcome") or "",
        parsed.get("check_content") or "",
        parsed.get("notes_content") or "",
        parsed.get("markdown_full_content") or "",
        source_filepath,
        "markdown",
        metadata.get("status") or "draft",
        json.dumps(tags, ensure_ascii=True),
        metadata.get("estimated_minutes"),
        metadata.get("difficulty") or "",
        metadata.get("last_verified") or "",
        utc_now(),
        utc_now(),
        parsed.get("parse_status") or "OK",
        parsed.get("parse_message") or "",
        now,
    )
    if row:
        howto_id = row["howto_id"]
        conn.execute(
            "UPDATE lp_howto SET howto_key=?, title=?, project_id=?, summary=?, outcome=?, "
            "check_content=?, notes_content=?, markdown_full_content=?, source_filepath=?, source_type=?, "
            "status=?, tags=?, estimated_minutes=?, difficulty=?, last_verified=?, source_modified=?, "
            "parsed_at=?, parse_status=?, parse_message=?, updated_at=? WHERE howto_id=?",
            values + (howto_id,),
        )
    else:
        cur = conn.execute(
            "INSERT INTO lp_howto (howto_key, title, project_id, summary, outcome, check_content, notes_content, "
            "markdown_full_content, source_filepath, source_type, status, tags, estimated_minutes, difficulty, "
            "last_verified, source_modified, parsed_at, parse_status, parse_message, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            values + (now,),
        )
        howto_id = cur.lastrowid
    return howto_id


def _upsert_part(conn, part, project_id):
    if part.get("matched_id"):
        return part["matched_id"]
    now = utc_now()
    key = part.get("part_key") or None
    cur = conn.execute(
        "INSERT INTO lp_howto_parts (part_key, project_id, part_name, default_unit, description, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '', '', ?, ?)",
        (key, project_id, part["name"], part.get("unit") or "", now, now),
    )
    return cur.lastrowid


def _upsert_tool(conn, tool, project_id):
    if tool.get("matched_id"):
        return tool["matched_id"]
    now = utc_now()
    key = tool.get("tool_key") or None
    cur = conn.execute(
        "INSERT INTO lp_howto_tools_needed (tool_key, project_id, tool_name, description, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, '', '', ?, ?)",
        (key, project_id, tool["name"], now, now),
    )
    return cur.lastrowid


def _upsert_step(conn, step, project_id):
    if step.get("matched_id"):
        return step["matched_id"]
    now = utc_now()
    key = step.get("step_key") or None
    cur = conn.execute(
        "INSERT INTO lp_howto_steps (step_key, project_id, step_type, step_title, instruction, expected_result, "
        "warning, image_filepath, default_optional, child_howto_ref, child_howto_id, child_mode, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            key,
            project_id,
            step.get("step_type") or "instruction",
            step.get("step_title") or "",
            step.get("instruction") or "",
            step.get("expected_result") or "",
            step.get("warning") or "",
            step.get("image_filepath") or "",
            1 if step.get("optional") else 0,
            step.get("child_howto_ref") or "",
            step.get("child_howto_id"),
            step.get("child_mode") or "linked",
            step.get("notes") or "",
            now,
            now,
        ),
    )
    return cur.lastrowid


def apply_markdown(markdown, source_filepath=None, conn=None, title=None, project_id=None, blueprint_name=None):
    conn = get_conn(conn)
    preview = build_preview_model(markdown, conn, title=title, project_id=project_id)
    if _preview_has_blockers(preview):
        raise ValueError("Cannot save while fatal parse errors or ambiguous references remain.")
    parsed = preview["parsed"]
    parsed["parse_status"] = preview["status"]
    parsed["parse_message"] = _parse_message(parsed)
    source_filepath = _source_path_for(parsed, source_filepath, blueprint_name=blueprint_name or title)
    started = not conn.in_transaction
    if started:
        conn.execute("BEGIN")
    try:
        howto_id = _upsert_howto(conn, parsed, source_filepath)
        conn.execute("DELETE FROM lp_howto_part_links WHERE howto_id = ?", (howto_id,))
        conn.execute("DELETE FROM lp_howto_tool_links WHERE howto_id = ?", (howto_id,))
        conn.execute("DELETE FROM lp_howto_step_links WHERE howto_id = ?", (howto_id,))
        conn.execute("DELETE FROM lp_howto_parse_messages WHERE howto_id = ?", (howto_id,))
        project_id = parsed["metadata"].get("resolved_project_id") or ""
        for idx, part in enumerate(parsed.get("parts", []), start=1):
            part_id = _upsert_part(conn, part, project_id)
            conn.execute(
                "INSERT INTO lp_howto_part_links (howto_id, part_id, item_order, quantity, unit, optional, notes, source_line) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (howto_id, part_id, idx, part.get("quantity"), part.get("unit") or "", 1 if part.get("optional") else 0, part.get("notes") or "", part.get("source_line")),
            )
        for idx, tool in enumerate(parsed.get("tools", []), start=1):
            tool_id = _upsert_tool(conn, tool, project_id)
            conn.execute(
                "INSERT INTO lp_howto_tool_links (howto_id, tool_id, item_order, optional, notes, source_line) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (howto_id, tool_id, idx, 1 if tool.get("optional") else 0, tool.get("notes") or "", tool.get("source_line")),
            )
        for step in parsed.get("steps", []):
            step_id = _upsert_step(conn, step, project_id)
            conn.execute(
                "INSERT INTO lp_howto_step_links (howto_id, step_id, step_order, optional_override, title_override, notes_override, source_line) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (howto_id, step_id, step.get("order"), 1 if step.get("optional") else 0, step.get("step_title") or "", step.get("notes") or "", step.get("source_line")),
            )
        for diag in parsed.get("diagnostics", []):
            conn.execute(
                "INSERT INTO lp_howto_parse_messages (howto_id, severity, code, message, source_line, source_column, created_at) "
                "VALUES (?, ?, ?, ?, ?, NULL, ?)",
                (howto_id, diag.get("severity"), diag.get("code") or "", diag.get("message"), diag.get("source_line"), utc_now()),
            )
        _atomic_write(source_filepath, markdown)
        if started:
            conn.commit()
    except Exception:
        if started:
            conn.rollback()
        raise
    return howto_id


def _parse_message(parsed):
    return f"Parsed {len(parsed.get('parts', []))} Parts, {len(parsed.get('tools', []))} Tools, and {len(parsed.get('steps', []))} Steps."


def list_howtos(project_id=""):
    conn = get_conn()
    project_id = normalize_project(project_id)
    params = []
    where = "1=1"
    if project_id:
        where = "project_id = ?"
        params.append(project_id)
    rows = conn.execute(
        "SELECT h.*, "
        "(SELECT COUNT(1) FROM lp_howto_step_links l WHERE l.howto_id = h.howto_id) AS step_count, "
        "(SELECT COUNT(1) FROM lp_howto_step_links l JOIN lp_howto_steps s ON s.step_id = l.step_id "
        " WHERE l.howto_id = h.howto_id AND s.step_type = 'howto') AS child_count "
        f"FROM lp_howto h WHERE {where} ORDER BY updated_at DESC, title",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def create_howto_from_markdown(title, markdown, project_id="", source_filepath="", conn=None):
    conn = get_conn(conn)
    title = (title or "").strip() or "Untitled How-to"
    project_id = normalize_project(project_id)
    now = utc_now()
    key = unique_howto_key(title, conn=conn)
    cur = conn.execute(
        "INSERT INTO lp_howto (howto_key, title, project_id, summary, outcome, check_content, notes_content, "
        "markdown_full_content, source_filepath, source_type, status, tags, estimated_minutes, difficulty, "
        "last_verified, source_modified, parsed_at, parse_status, parse_message, created_at, updated_at) "
        "VALUES (?, ?, ?, '', '', '', '', ?, ?, 'markdown', 'draft', '[]', NULL, '', '', ?, NULL, 'NOT_PARSED', "
        "'Converted from Note. Open and Preview to parse.', ?, ?)",
        (key, title, project_id, markdown or "", source_filepath or None, now, now, now),
    )
    return cur.lastrowid


def _unique_path(folder, file_name):
    stem, ext = os.path.splitext(file_name)
    candidate = os.path.join(folder, file_name)
    suffix = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem}-{suffix}{ext}")
        suffix += 1
    return candidate


def convert_howto_to_note(howto_id, conn=None):
    from common.utils import get_table_def

    conn = get_conn(conn)
    howto = get_howto(howto_id, conn=conn)
    if not howto:
        raise ValueError("How-to not found.")
    tbl = get_table_def("notes")
    if not tbl:
        raise ValueError("Notes table not found.")
    markdown = howto.get("markdown_full_content") or ""
    if not markdown and howto.get("source_filepath"):
        try:
            with open(howto["source_filepath"], "r", encoding="utf-8", errors="replace") as handle:
                markdown = handle.read()
        except OSError:
            markdown = ""
    project_id = howto.get("project_id") or ""
    folder = ""
    if project_id:
        try:
            folder = projects_mod.project_default_folder_get(project_id) or ""
        except Exception:
            folder = ""
    if not folder and howto.get("source_filepath"):
        folder = os.path.dirname(howto["source_filepath"])
    if not folder:
        folder = _default_how_root()
    os.makedirs(folder, exist_ok=True)
    source_name = os.path.basename(howto.get("source_filepath") or "")
    file_name = source_name if source_name.lower().endswith(".md") else _safe_file_name(howto.get("title"), slug=False)
    note_path = os.path.join(folder, file_name)
    if os.path.exists(note_path):
        try:
            with open(note_path, "r", encoding="utf-8", errors="replace") as handle:
                existing = handle.read()
        except OSError:
            existing = None
        if existing != markdown:
            note_path = _unique_path(folder, file_name)
    _atomic_write(note_path, markdown)
    stat = os.stat(note_path)
    folder_id = db.upsert_note_dim_folder(conn, folder)
    values = {
        "file_name": os.path.basename(note_path),
        "path": folder,
        "folder_id": folder_id or "",
        "size": str(stat.st_size),
        "date_modified": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "project": project_id,
    }
    table_cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({tbl['name']})").fetchall()}
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            values["owner_user_id"] = current_user.user_id
    except Exception:
        pass
    if "visibility" in table_cols:
        values["visibility"] = "private"
    if "is_public" in table_cols:
        values["is_public"] = 0
    if "show_in_blog" in table_cols:
        values["show_in_blog"] = 0
    cols = [col for col in list(tbl["col_list"]) + ["owner_user_id", "visibility", "is_public", "show_in_blog"] if col in values and col in table_cols]
    placeholders = ", ".join(["?"] * (len(cols) + 2))
    cur = conn.execute(
        f"INSERT INTO {tbl['name']} ({', '.join(cols)}, user_name, rec_extract_date) VALUES ({placeholders})",
        [values[col] for col in cols] + [db._current_user(), __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    )
    note_id = cur.lastrowid
    conn.execute("DELETE FROM lp_howto WHERE howto_id = ?", (howto_id,))
    conn.commit()
    return note_id


def get_howto(howto_id, conn=None):
    conn = get_conn(conn)
    row = conn.execute("SELECT * FROM lp_howto WHERE howto_id = ?", (howto_id,)).fetchone()
    return _dict(row)


def get_howto_detail(howto_id, conn=None):
    conn = get_conn(conn)
    howto = get_howto(howto_id, conn=conn)
    if not howto:
        return None
    parts = conn.execute(
        "SELECT l.*, p.part_name, p.part_key FROM lp_howto_part_links l JOIN lp_howto_parts p ON p.part_id = l.part_id "
        "WHERE l.howto_id = ? ORDER BY l.item_order",
        (howto_id,),
    ).fetchall()
    tools = conn.execute(
        "SELECT l.*, t.tool_name, t.tool_key FROM lp_howto_tool_links l JOIN lp_howto_tools_needed t ON t.tool_id = l.tool_id "
        "WHERE l.howto_id = ? ORDER BY l.item_order",
        (howto_id,),
    ).fetchall()
    steps = conn.execute(
        "SELECT l.*, s.* FROM lp_howto_step_links l JOIN lp_howto_steps s ON s.step_id = l.step_id "
        "WHERE l.howto_id = ? ORDER BY l.step_order",
        (howto_id,),
    ).fetchall()
    parents = conn.execute(
        "SELECT DISTINCT h.howto_id, h.title, h.howto_key FROM lp_howto h "
        "JOIN lp_howto_step_links l ON l.howto_id = h.howto_id "
        "JOIN lp_howto_steps s ON s.step_id = l.step_id "
        "WHERE s.child_howto_id = ? OR s.child_howto_ref = ? ORDER BY h.title",
        (howto_id, howto.get("howto_key") or ""),
    ).fetchall()
    return {
        "howto": howto,
        "parts": [dict(row) for row in parts],
        "tools": [dict(row) for row in tools],
        "steps": [dict(row) for row in steps],
        "parents": [dict(row) for row in parents],
    }


def list_catalog(kind, project_id="", conn=None):
    conn = get_conn(conn)
    project_id = normalize_project(project_id)
    specs = {
        "tools": ("lp_howto_tools_needed", "tool_id", "tool_name", "lp_howto_tool_links", "tool_id"),
        "parts": ("lp_howto_parts", "part_id", "part_name", "lp_howto_part_links", "part_id"),
        "steps": ("lp_howto_steps", "step_id", "step_title", "lp_howto_step_links", "step_id"),
    }
    table, pk, name_col, link_table, link_fk = specs[kind]
    where = "1=1"
    params = []
    if project_id:
        where = "(project_id = ? OR project_id IS NULL OR project_id = '')"
        params.append(project_id)
    order_expr = {
        "tools": "lower(tool_name)",
        "parts": "lower(part_name)",
        "steps": "lower(COALESCE(step_title, instruction, ''))",
    }[kind]
    rows = conn.execute(
        f"SELECT c.*, (SELECT COUNT(1) FROM {link_table} l WHERE l.{link_fk}=c.{pk}) AS used_by_count "
        f"FROM {table} c WHERE {where} ORDER BY {order_expr}",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_catalog(kind, form, item_id=None):
    conn = get_conn()
    now = utc_now()
    if kind == "tools":
        table, pk, cols = "lp_howto_tools_needed", "tool_id", ["tool_key", "project_id", "tool_name", "description", "notes"]
    elif kind == "parts":
        table, pk, cols = "lp_howto_parts", "part_id", ["part_key", "project_id", "part_name", "default_unit", "description", "notes"]
    else:
        table, pk, cols = "lp_howto_steps", "step_id", ["step_key", "project_id", "step_type", "step_title", "instruction", "expected_result", "warning", "default_optional", "child_howto_ref", "child_mode", "notes"]
    values = [form.get(col, "").strip() for col in cols]
    if item_id:
        conn.execute(
            f"UPDATE {table} SET {', '.join(col + '=?' for col in cols)}, updated_at=? WHERE {pk}=?",
            values + [now, item_id],
        )
    else:
        conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}, created_at, updated_at) VALUES ({', '.join(['?'] * len(cols))}, ?, ?)",
            values + [now, now],
        )
    conn.commit()


def build_tree(howto_id, max_depth=20, conn=None):
    conn = get_conn(conn)
    root = get_howto(howto_id, conn=conn)
    if not root:
        return None
    return _tree_node(conn, root, [], "1", 0, max_depth)


def create_child_stub(parent_id, child_key, conn=None):
    conn = get_conn(conn)
    parent = get_howto(parent_id, conn=conn)
    if not parent:
        raise ValueError("Parent How-to not found.")
    child_key = slug_key(child_key)
    existing = conn.execute("SELECT howto_id FROM lp_howto WHERE howto_key = ?", (child_key,)).fetchone()
    if existing:
        return existing["howto_id"]
    title = " ".join(word.capitalize() for word in child_key.split("-"))
    project_line = f"project_id: {parent.get('project_id')}\n" if parent.get("project_id") else ""
    markdown = (
        "---\n"
        f"key: {child_key}\n"
        f"title: {title}\n"
        f"{project_line}"
        "status: outline\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Summary\n\nTODO\n\n"
        "## Outcome\n\nTODO\n\n"
        "## Steps\n\n1. TODO\n"
    )
    return apply_markdown(markdown, conn=conn)


def _tree_node(conn, howto, path_keys, number, depth, max_depth):
    key = howto.get("howto_key") or str(howto["howto_id"])
    node = {"howto": howto, "number": number, "steps": [], "cycle": False}
    if key in path_keys:
        node["cycle"] = True
        node["cycle_path"] = path_keys + [key]
        return node
    if depth >= max_depth:
        node["max_depth"] = True
        return node
    rows = conn.execute(
        "SELECT l.step_order, s.* FROM lp_howto_step_links l JOIN lp_howto_steps s ON s.step_id = l.step_id "
        "WHERE l.howto_id = ? ORDER BY l.step_order",
        (howto["howto_id"],),
    ).fetchall()
    next_path = path_keys + [key]
    for idx, row in enumerate(rows, start=1):
        step = dict(row)
        step_number = f"{number}.{idx}" if number else str(idx)
        entry = {"number": step_number, "step": step}
        child_id = step.get("child_howto_id")
        if not child_id and step.get("child_howto_ref"):
            child = conn.execute("SELECT * FROM lp_howto WHERE howto_key = ?", (step["child_howto_ref"],)).fetchone()
            child_id = child["howto_id"] if child else None
        if child_id:
            child = conn.execute("SELECT * FROM lp_howto WHERE howto_id = ?", (child_id,)).fetchone()
            if child:
                entry["child"] = _tree_node(conn, dict(child), next_path, step_number, depth + 1, max_depth)
        elif step.get("child_howto_ref"):
            entry["unresolved_child"] = step["child_howto_ref"]
        node["steps"].append(entry)
    return node
