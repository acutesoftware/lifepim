from common import data
from common.utils import get_table_def


def _build_snippet(value, query_lower, max_len=80):
    text = value or ""
    text_lower = text.lower()
    idx = text_lower.find(query_lower)
    if idx == -1:
        return text[:max_len] + ("..." if len(text) > max_len else "")
    start = max(0, idx - 20)
    end = min(len(text), idx + len(query_lower) + 20)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def _find_match_field(item, query_lower, columns):
    for col in columns:
        value = (item.get(col) or "").lower()
        if query_lower in value:
            return col
    return ""


def _search_table(route_name, query_lower, columns, view_route, id_param):
    tbl = get_table_def(route_name)
    if not tbl:
        return []
    available_cols = [col for col in columns if col in tbl["col_list"]]
    if not available_cols:
        return []
    cols = ["id"] + tbl["col_list"]
    like_value = f"%{query_lower}%"
    condition = " OR ".join([f"lower({col}) LIKE ?" for col in available_cols])
    rows = data.get_data(data.conn, tbl["name"], cols, f"({condition})", [like_value] * len(available_cols))
    results = []
    for row in rows:
        item = dict(row)
        match_field = _find_match_field(item, query_lower, available_cols)
        match_value = item.get(match_field) or ""
        results.append(
            {
                "table": tbl.get("display_name") or route_name.title(),
                "route": tbl.get("route") or route_name,
                "id": item.get("id"),
                "project": item.get("project") or "",
                "match_field": match_field,
                "match_value": match_value,
                "match_snippet": _build_snippet(match_value, query_lower),
                "view_route": view_route,
                "id_param": id_param,
            }
        )
    return results


def search_all(query, project=None, route=None):
    query = (query or "").strip()
    if not query:
        return {"primary": [], "secondary": []}
    query_lower = query.lower()
    results = []
    results += _search_table(
        "notes",
        query_lower,
        ["file_name", "path"],
        "notes.view_note_route",
        "note_id",
    )
    results += _search_table(
        "data",
        query_lower,
        ["name", "description", "tbl_name", "col_list"],
        "data.view_data_route",
        "item_id",
    )
    results += _search_table(
        "audio",
        query_lower,
        ["file_name", "path", "artist", "album", "song"],
        "audio.view_audio_route",
        "item_id",
    )
    results += _search_table(
        "media",
        query_lower,
        ["file_name", "path", "file_type"],
        "media.view_media_route",
        "item_id",
    )
    results += _search_table(
        "how",
        query_lower,
        ["title", "description"],
        "how.view_how_route",
        "item_id",
    )
    results += _search_table(
        "calendar",
        query_lower,
        ["title", "content", "event_date"],
        "calendar.view_event_route",
        "event_id",
    )
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
