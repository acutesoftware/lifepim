import os

from common import config as cfg
from common import data
from common.utils import get_table_def

ROUTE_RECORD_TYPE = {
    "notes": "note",
    "tasks": "task",
    "calendar": "event",
    "files": "file",
    "contacts": "person",
    "places": "place",
}

ROUTE_TITLE_FIELD = {
    "notes": "file_name",
    "tasks": "title",
    "calendar": "title",
    "files": "filelist_name",
    "contacts": "display_name",
    "places": "name",
}


def parse_search_terms(query):
    query = (query or "").strip()
    if not query:
        return []
    terms = []
    buf = []
    in_quote = False
    for ch in query:
        if ch == '"':
            segment = "".join(buf).strip()
            buf = []
            if in_quote:
                if segment:
                    terms.append(segment)
                in_quote = False
            else:
                if segment:
                    terms.extend(segment.split())
                in_quote = True
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        terms.extend(tail.split())
    return [term for term in terms if term]


def _build_snippet(value, terms, max_len=80):
    text = value or ""
    text_lower = text.lower()
    if not terms:
        return text[:max_len] + ("..." if len(text) > max_len else "")
    best_idx = None
    best_term = ""
    for term in terms:
        idx = text_lower.find(term)
        if idx != -1 and (best_idx is None or idx < best_idx):
            best_idx = idx
            best_term = term
    if best_idx is None:
        return text[:max_len] + ("..." if len(text) > max_len else "")
    term_len = len(best_term)
    if max_len <= term_len + 1:
        start = max(0, best_idx)
        end = min(len(text), best_idx + term_len)
    else:
        context_len = max_len - term_len
        left_len = context_len // 2
        right_len = context_len - left_len
        start = max(0, best_idx - left_len)
        end = min(len(text), best_idx + term_len + right_len)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _find_match_field(item, terms, columns):
    for col in columns:
        value = (item.get(col) or "").lower()
        for term in terms:
            if term in value:
                return col
    return ""


def _search_table(route_name, terms, columns, view_route, id_param):
    tbl = get_table_def(route_name)
    if not tbl:
        return []
    available_cols = [col for col in columns if col in tbl["col_list"]]
    if not available_cols or not terms:
        return []
    cols = ["id"] + tbl["col_list"]
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        condition = " OR ".join([f"lower({col}) LIKE ?" for col in available_cols])
        term_conditions.append(f"({condition})")
        params.extend([like_value] * len(available_cols))
    where_clause = " AND ".join(term_conditions)
    rows = data.get_data(data.conn, tbl["name"], cols, f"({where_clause})", params)
    results = []
    for row in rows:
        item = dict(row)
        match_field = _find_match_field(item, terms, available_cols)
        match_value = item.get(match_field) or ""
        results.append(
            {
                "table": tbl.get("display_name") or route_name.title(),
                "route": tbl.get("route") or route_name,
                "id": item.get("id"),
                "project": item.get("project") or "",
                "match_field": match_field,
                "match_value": match_value,
                "match_snippet": _build_snippet(match_value, terms),
                "view_route": view_route,
                "id_param": id_param,
                "record_type": ROUTE_RECORD_TYPE.get(route_name, ""),
                "title": item.get(ROUTE_TITLE_FIELD.get(route_name, "")) or "",
            }
        )
    return results


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


def _search_note_content(terms, existing_ids=None):
    tbl = get_table_def("notes")
    if not tbl:
        return []
    cols = ["id"] + tbl["col_list"]
    rows = data.get_data(data.conn, tbl["name"], cols)
    results = []
    existing_ids = existing_ids or set()
    for row in rows:
        item = dict(row)
        note_id = item.get("id")
        if note_id in existing_ids:
            continue
        note_path = _build_note_path(item)
        if not note_path:
            continue
        if not note_path.lower().endswith(".md"):
            continue
        if not os.path.isfile(note_path):
            continue
        note_text = _read_note_file(note_path)
        if not note_text:
            continue
        note_text_lower = note_text.lower()
        if not all(term in note_text_lower for term in terms):
            continue
        snippet_len = getattr(cfg, "SEARCH_CONTENT_SNIPPET_LEN", 200)
        snippet = _build_snippet(note_text, terms, max_len=snippet_len)
        results.append(
            {
                "table": tbl.get("display_name") or "Notes",
                "route": tbl.get("route") or "notes",
                "id": note_id,
                "project": item.get("project") or "",
                "match_field": "content",
                "match_value": snippet,
                "match_snippet": snippet,
                "view_route": "notes.view_note_route",
                "id_param": "note_id",
                "record_type": ROUTE_RECORD_TYPE.get("notes", ""),
                "title": item.get("file_name") or "",
            }
        )
    return results


def search_all(query, project=None, route=None, include_note_content=False):
    terms = parse_search_terms(query)
    if not terms:
        return {"primary": [], "secondary": []}
    terms = [term.lower() for term in terms]
    results = []
    results += _search_table(
        "notes",
        terms,
        ["file_name", "path"],
        "notes.view_note_route",
        "note_id",
    )
    results += _search_table(
        "data",
        terms,
        ["name", "description", "tbl_name", "col_list"],
        "data.view_data_route",
        "item_id",
    )
    results += _search_table(
        "audio",
        terms,
        ["file_name", "path", "artist", "album", "song"],
        "audio.view_audio_route",
        "item_id",
    )
    results += _search_table(
        "media",
        terms,
        ["file_name", "path", "file_type"],
        "media.view_media_route",
        "item_id",
    )
    results += _search_table(
        "how",
        terms,
        ["title", "description"],
        "how.view_how_route",
        "item_id",
    )
    results += _search_table(
        "calendar",
        terms,
        ["title", "content", "event_date"],
        "calendar.view_event_route",
        "event_id",
    )
    if include_note_content:
        note_ids = {result.get("id") for result in results if result.get("route") == "notes" and result.get("id")}
        results += _search_note_content(terms, existing_ids=note_ids)
    primary = []
    secondary = []
    for result in results:
        matches_project = bool(project) and result.get("project") == project
        matches_route = bool(route) and (result.get("route") == route)
        if matches_project or matches_route:
            primary.append(result)
        else:
            secondary.append(result)
    return {"primary": primary, "secondary": secondary}
