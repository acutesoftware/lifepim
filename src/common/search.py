from common import config as cfg
from common import data
from common import note_search_index
from common.utils import get_table_def, get_tabs


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    cols = set()
    for row in rows:
        try:
            cols.add(row["name"])
        except (TypeError, KeyError, IndexError):
            cols.add(row[1])
    return cols


def _current_search_user():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return current_user
    except Exception:
        return None
    return None


def _visible_table_condition(conn, table_name, alias):
    columns = _table_columns(conn, table_name)
    prefix = f"{alias}." if alias else ""
    user = _current_search_user()
    if table_name == "lp_media":
        if user is not None:
            return "1=1", []
        if "is_public" in columns:
            return f"{prefix}is_public = 1", []
        return "1=0", []
    if not {"owner_user_id", "visibility", "is_public"}.issubset(columns):
        return "1=1", []
    if user is not None:
        return f"({prefix}owner_user_id = ? OR {prefix}visibility = 'family' OR {prefix}is_public = 1)", [user.user_id]
    return f"{prefix}is_public = 1", []


def _visible_search_routes():
    try:
        return {tab.get("id") for tab in get_tabs()}
    except Exception:
        return set()

ROUTE_RECORD_TYPE = {
    "notes": "note",
    "tasks": "task",
    "calendar": "event",
    "files": "file",
    "media": "media",
    "contacts": "person",
    "places": "place",
}

ROUTE_TITLE_FIELD = {
    "notes": "file_name",
    "tasks": "title",
    "calendar": "title",
    "files": "filelist_name",
    "media": "filename",
    "contacts": "display_name",
    "places": "name",
}

SEARCH_SPECS = {
    "notes": {
        "columns": ["file_name", "path"],
        "view_route": "notes.view_note_route",
        "id_param": "note_id",
    },
    "audio": {
        "columns": ["file_name", "path", "artist", "album", "song"],
        "view_route": "audio.view_audio_route",
        "id_param": "item_id",
    },
    "media": {
        "columns": ["filename", "path", "ext", "media_type"],
        "view_route": "media.view_media_route",
        "id_param": "media_id",
    },
    "how": {
        "columns": ["title", "summary", "outcome", "markdown_full_content", "tags"],
        "view_route": "how.view_how_route",
        "id_param": "item_id",
    },
    "calendar": {
        "columns": ["title", "content", "event_date"],
        "view_route": "calendar.view_event_route",
        "id_param": "event_id",
    },
}

DEFAULT_SEARCH_ORDER = ["notes", "audio", "media", "how", "calendar"]


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


def _search_table(route_name, terms, columns, view_route, id_param, limit=None):
    tbl = get_table_def(route_name)
    if not tbl:
        return [], False
    conn = data._get_conn()
    table_cols = _table_columns(conn, tbl["name"])
    if not table_cols:
        return [], False
    available_cols = [col for col in columns if col in tbl["col_list"] and col in table_cols]
    if not available_cols or not terms:
        return [], False
    cols = [col for col in ["id"] + tbl["col_list"] if col in table_cols]
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        condition = " OR ".join([f"lower(r.{col}) LIKE ?" for col in available_cols])
        term_conditions.append(f"({condition})")
        params.extend([like_value] * len(available_cols))
    where_clause = " AND ".join(term_conditions)
    visibility_clause, visibility_params = _visible_table_condition(conn, tbl["name"], "r")
    params.extend(visibility_params)
    fetch_limit = int(limit) + 1 if limit else None
    sql = f"SELECT {', '.join(cols)} FROM {tbl['name']} r WHERE ({where_clause}) AND ({visibility_clause})"
    if fetch_limit:
        sql += " LIMIT ?"
        params.append(fetch_limit)
    rows = conn.execute(sql, params).fetchall()
    has_more = bool(fetch_limit and len(rows) > limit)
    if has_more:
        rows = rows[:limit]
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
    return results, has_more


def _search_media(terms, limit=None):
    tbl = get_table_def("media")
    if not tbl:
        return [], False
    if not terms:
        return [], False
    conn = data._get_conn()
    try:
        table_cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({tbl['name']})").fetchall()}
    except Exception:
        return [], False
    required_cols = {"media_id", "filename", "path", "ext", "media_type"}
    if not required_cols.issubset(table_cols):
        return [], False
    search_cols = ["filename", "path", "ext", "media_type"]
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        condition = " OR ".join([f"lower(m.{col}) LIKE ?" for col in search_cols])
        term_conditions.append(f"({condition})")
        params.extend([like_value] * len(search_cols))
    where_clause = " AND ".join(term_conditions)
    visibility_clause, visibility_params = _visible_table_condition(conn, tbl["name"], "m")
    params.extend(visibility_params)
    fetch_limit = int(limit) + 1 if limit else None
    sql = (
        "SELECT media_id as id, filename, path, ext, media_type "
        f"FROM {tbl['name']} m WHERE ({where_clause}) AND ({visibility_clause})"
    )
    if fetch_limit:
        sql += " LIMIT ?"
        params.append(fetch_limit)
    rows = conn.execute(sql, params).fetchall()
    has_more = bool(fetch_limit and len(rows) > limit)
    if has_more:
        rows = rows[:limit]
    results = []
    for row in rows:
        item = dict(row)
        match_field = _find_match_field(item, terms, search_cols)
        match_value = item.get(match_field) or ""
        results.append(
            {
                "table": tbl.get("display_name") or "Media",
                "route": "media",
                "id": item.get("id"),
                "project": "",
                "match_field": match_field,
                "match_value": match_value,
                "match_snippet": _build_snippet(match_value, terms),
                "view_route": "media.view_media_route",
                "id_param": "media_id",
                "record_type": ROUTE_RECORD_TYPE.get("media", ""),
                "title": item.get("filename") or "",
            }
        )
    return results, has_more


def _search_note_content_index(terms, project=None, route=None, limit=None):
    note_search_index.ensure_schema()
    conn = data._get_conn()
    fetch_limit = int(limit) + 1 if limit else None
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        term_conditions.append("lower(idx.content_text) LIKE ?")
        params.append(like_value)
    where_clause = " AND ".join(term_conditions) or "1=1"
    visibility_clause, visibility_params = _visible_table_condition(conn, "lp_notes", "n")
    params.extend(visibility_params)
    sql = (
        "SELECT idx.note_id, idx.title, idx.content_text, idx.file_path, n.project "
        "FROM lp_note_search_index idx "
        "LEFT JOIN lp_notes n ON n.id = idx.note_id "
        f"WHERE ({where_clause}) AND ({visibility_clause}) "
        "ORDER BY idx.title"
    )
    if fetch_limit:
        sql += " LIMIT ?"
        params.append(fetch_limit)
    rows = conn.execute(sql, params).fetchall()
    has_more = bool(fetch_limit and len(rows) > limit)
    if has_more:
        rows = rows[:limit]
    results = []
    for row in rows:
        item = dict(row)
        snippet_len = getattr(cfg, "SEARCH_CONTENT_SNIPPET_LEN", 200)
        snippet = _build_snippet(item.get("content_text") or "", terms, max_len=snippet_len)
        results.append(
            {
                "table": "Notes",
                "route": "notes",
                "id": item.get("note_id"),
                "project": item.get("project") or "",
                "match_field": "content",
                "match_value": snippet,
                "match_snippet": snippet,
                "view_route": "notes.view_note_route",
                "id_param": "note_id",
                "record_type": ROUTE_RECORD_TYPE.get("notes", ""),
                "title": item.get("title") or "",
            }
        )
    return results, has_more


def search_note_content(query, project=None, route=None, limit=100):
    terms = parse_search_terms(query)
    if not terms:
        return {"primary": [], "secondary": [], "more": []}
    terms = [term.lower() for term in terms]
    results, has_more = _search_note_content_index(terms, project=project, route=route, limit=limit)
    primary = []
    secondary = []
    for result in results:
        matches_project = bool(project) and result.get("project") == project
        matches_route = bool(route) and result.get("route") == route
        if matches_project or matches_route:
            primary.append(result)
        else:
            secondary.append(result)
    more = []
    if has_more:
        more.append({"route": "notes", "table": "Notes content"})
    return {"primary": primary, "secondary": secondary, "more": more}


def _search_route(route_name, terms, limit):
    if route_name == "how":
        return _search_how(terms, limit=limit)
    spec = SEARCH_SPECS.get(route_name)
    if not spec:
        return [], False
    if route_name == "media":
        return _search_media(terms, limit=limit)
    return _search_table(
        route_name,
        terms,
        spec["columns"],
        spec["view_route"],
        spec["id_param"],
        limit=limit,
    )


def _search_how(terms, limit=None):
    if not terms:
        return [], False
    conn = data._get_conn()
    try:
        from modules.how.schema import ensure_how_schema

        ensure_how_schema(conn)
    except Exception:
        return [], False
    search_cols = ["title", "summary", "outcome", "markdown_full_content", "tags"]
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        term_conditions.append("(" + " OR ".join([f"lower(h.{col}) LIKE ?" for col in search_cols]) + ")")
        params.extend([like_value] * len(search_cols))
    fetch_limit = int(limit) + 1 if limit else None
    sql = (
        "SELECT h.howto_id AS id, h.title, h.project_id AS project, h.summary, h.outcome, "
        "h.markdown_full_content, h.tags FROM lp_howto h "
        f"WHERE {' AND '.join(term_conditions)}"
    )
    if fetch_limit:
        sql += " LIMIT ?"
        params.append(fetch_limit)
    rows = conn.execute(sql, params).fetchall()
    has_more = bool(fetch_limit and len(rows) > limit)
    if has_more:
        rows = rows[:limit]
    results = []
    for row in rows:
        item = dict(row)
        match_field = _find_match_field(item, terms, search_cols)
        match_value = item.get(match_field) or ""
        results.append(
            {
                "table": "How",
                "route": "how",
                "id": item.get("id"),
                "project": item.get("project") or "",
                "match_field": match_field,
                "match_value": match_value,
                "match_snippet": _build_snippet(match_value, terms),
                "view_route": "how.view_how_route",
                "id_param": "item_id",
                "record_type": "howto",
                "title": item.get("title") or "",
            }
        )
    return results, has_more


def search_all(query, project=None, route=None, primary_limit=100, secondary_limit=20):
    terms = parse_search_terms(query)
    if not terms:
        return {"primary": [], "secondary": [], "more": []}
    terms = [term.lower() for term in terms]
    primary = []
    secondary = []
    more = []
    visible_routes = _visible_search_routes()
    search_order = [route_name for route_name in DEFAULT_SEARCH_ORDER if not visible_routes or route_name in visible_routes]
    current_route = route if route in SEARCH_SPECS else ""
    if current_route and current_route in search_order:
        search_order.remove(current_route)
        search_order.insert(0, current_route)
    elif current_route:
        current_route = ""
    for route_name in search_order:
        limit = primary_limit if route_name == current_route else secondary_limit
        route_results, has_more = _search_route(route_name, terms, limit)
        if has_more:
            spec = SEARCH_SPECS[route_name]
            tbl = get_table_def(route_name)
            more.append(
                {
                    "route": route_name,
                    "table": (tbl.get("display_name") if tbl else None) or route_name.title(),
                    "view_route": spec["view_route"],
                }
            )
        for result in route_results:
            matches_project = bool(project) and result.get("project") == project
            matches_route = bool(route) and (result.get("route") == route)
            if matches_project or matches_route:
                primary.append(result)
            else:
                secondary.append(result)
    return {
        "primary": primary,
        "secondary": secondary,
        "more": more,
    }
