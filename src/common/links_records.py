from common import data
from common import links as link_model
from common.utils import get_table_def
from modules.contacts import dao as contacts_dao


def search_records(query, types=None, limit=20):
    query = (query or "").strip()
    if not query:
        return []
    query_lower = query.lower()
    types = [link_model._norm_type_id(t) for t in (types or []) if t]
    if not types:
        types = ["note", "task", "event", "file", "person", "place"]
    results = []
    remaining = max(1, int(limit or 20))

    def _extend(rows):
        nonlocal remaining
        if remaining <= 0:
            return
        for row in rows[:remaining]:
            results.append(row)
        remaining = max(0, remaining - len(rows))

    if "note" in types:
        _extend(_search_notes(query_lower, remaining))
    if "task" in types:
        _extend(_search_tasks(query_lower, remaining))
    if "event" in types:
        _extend(_search_events(query_lower, remaining))
    if "file" in types:
        _extend(_search_files(query_lower, remaining))
    if "person" in types or "contact" in types:
        _extend(_search_contacts(query_lower, remaining))
    if "place" in types:
        _extend(_search_places(query_lower, remaining))
    return results


def get_record_summary(type_id, record_id):
    type_id = link_model._norm_type_id(type_id)
    record_id = str(record_id)
    if type_id in {"person", "contact"}:
        try:
            contact_id = int(record_id)
        except (TypeError, ValueError):
            contact_id = record_id
        contact = contacts_dao.get_contact(contact_id)
        if not contact:
            return None
        return _summary_from_values(
            type_id,
            record_id,
            contact.get("display_name"),
            contact.get("normalized_name"),
        )
    tbl = _table_for_type(type_id)
    if not tbl:
        return None
    id_col = "id"
    sql = f"SELECT * FROM {tbl['name']} WHERE {id_col} = ?"
    row = data._get_conn().execute(sql, [record_id]).fetchone()
    if not row:
        return None
    values = dict(row)
    title, subtitle = _summary_fields(type_id, values)
    if not title:
        desc = link_model.get_record_type(type_id) or {}
        primary_field = desc.get("primary_label_field")
        if primary_field:
            title = values.get(primary_field) or title
    return _summary_from_values(type_id, record_id, title, subtitle)


def _summary_from_values(type_id, record_id, title, subtitle):
    desc = link_model.get_record_type(type_id) or {}
    return {
        "type": type_id,
        "id": str(record_id),
        "title": title or "",
        "subtitle": subtitle or "",
        "icon": desc.get("icon") or "",
        "open_url": link_model.build_open_route(type_id, record_id),
    }


def _table_for_type(type_id):
    if type_id == "note":
        return get_table_def("notes")
    if type_id == "task":
        return get_table_def("tasks")
    if type_id == "event":
        return get_table_def("calendar")
    if type_id == "file":
        return get_table_def("files")
    if type_id == "place":
        return get_table_def("places")
    return None


def _search_notes(query_lower, limit):
    tbl = get_table_def("notes")
    if not tbl:
        return []
    cols = ["id", "file_name", "path"]
    rows = _search_table(tbl["name"], cols, ["file_name", "path"], query_lower, limit)
    return [
        _summary_from_values("note", row["id"], row.get("file_name"), row.get("path"))
        for row in rows
    ]


def _search_tasks(query_lower, limit):
    tbl = get_table_def("tasks")
    if not tbl:
        return []
    cols = ["id", "title", "content", "due_date", "project"]
    rows = _search_table(tbl["name"], cols, ["title", "content"], query_lower, limit)
    return [
        _summary_from_values(
            "task",
            row["id"],
            row.get("title"),
            row.get("due_date") or row.get("project"),
        )
        for row in rows
    ]


def _search_events(query_lower, limit):
    tbl = get_table_def("calendar")
    if not tbl:
        return []
    cols = ["id", "title", "content", "event_date", "project"]
    rows = _search_table(tbl["name"], cols, ["title", "content"], query_lower, limit)
    return [
        _summary_from_values(
            "event",
            row["id"],
            row.get("title"),
            row.get("event_date") or row.get("project"),
        )
        for row in rows
    ]


def _search_files(query_lower, limit):
    tbl = get_table_def("files")
    if not tbl:
        return []
    cols = ["id", "filelist_name", "path", "project"]
    rows = _search_table(tbl["name"], cols, ["filelist_name", "path"], query_lower, limit)
    return [
        _summary_from_values(
            "file",
            row["id"],
            row.get("filelist_name"),
            row.get("path") or row.get("project"),
        )
        for row in rows
    ]


def _search_places(query_lower, limit):
    tbl = get_table_def("places")
    if not tbl:
        return []
    cols = ["id", "name", "desc", "suburb", "state", "country"]
    rows = _search_table(tbl["name"], cols, ["name", "desc", "suburb", "state", "country"], query_lower, limit)
    return [
        _summary_from_values(
            "place",
            row["id"],
            row.get("name"),
            row.get("suburb") or row.get("state") or row.get("country"),
        )
        for row in rows
    ]


def _search_contacts(query_lower, limit):
    conn = data._get_conn()
    sql = (
        "SELECT contact_id, display_name, normalized_name "
        "FROM lp_contacts "
        "WHERE lower(display_name) LIKE ? OR lower(normalized_name) LIKE ? "
        "ORDER BY display_name "
        "LIMIT ?"
    )
    like_value = f"%{query_lower}%"
    rows = conn.execute(sql, [like_value, like_value, int(limit or 20)]).fetchall()
    return [
        _summary_from_values(
            "person",
            row["contact_id"],
            row["display_name"],
            row["normalized_name"],
        )
        for row in rows
    ]


def _summary_fields(type_id, row):
    if type_id == "note":
        return row.get("file_name"), row.get("path")
    if type_id == "task":
        return row.get("title"), row.get("due_date") or row.get("project")
    if type_id == "event":
        return row.get("title"), row.get("event_date") or row.get("project")
    if type_id == "file":
        return row.get("filelist_name"), row.get("path")
    if type_id == "place":
        subtitle = row.get("suburb") or row.get("state") or row.get("country")
        return row.get("name"), subtitle
    return "", ""


def _search_table(tbl_name, cols, search_cols, query_lower, limit):
    if not search_cols:
        return []
    like_value = f"%{query_lower}%"
    condition = " OR ".join([f"lower({col}) LIKE ?" for col in search_cols])
    sql = f"SELECT {', '.join(cols)} FROM {tbl_name} WHERE {condition} LIMIT ?"
    params = [like_value] * len(search_cols) + [int(limit or 20)]
    rows = data._get_conn().execute(sql, params).fetchall()
    return [dict(row) for row in rows]
