from common import data
from common import links as link_model
from common.search import parse_search_terms
from common.utils import get_table_def
from modules.contacts import dao as contacts_dao


def search_records(query, types=None, limit=20):
    terms = parse_search_terms(query)
    if not terms:
        return []
    terms = [term.lower() for term in terms]
    types = [link_model._norm_type_id(t) for t in (types or []) if t]
    if not types:
        types = ["note", "task", "event", "how", "file", "media", "audio", "person", "place", "money", "album", "app", "3d"]
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
        _extend(_search_notes(terms, remaining))
    if "task" in types:
        _extend(_search_tasks(terms, remaining))
    if "event" in types:
        _extend(_search_events(terms, remaining))
    if "how" in types:
        _extend(_search_howtos(terms, remaining))
    if "file" in types:
        _extend(_search_files(terms, remaining))
    if "media" in types:
        _extend(_search_media(terms, remaining))
    if "audio" in types:
        _extend(_search_audio(terms, remaining))
    if "person" in types or "contact" in types:
        _extend(_search_contacts(terms, remaining))
    if "place" in types:
        _extend(_search_places(terms, remaining))
    if "money" in types:
        _extend(_search_money(terms, remaining))
    if "album" in types:
        _extend(_search_albums(terms, remaining))
    if "app" in types:
        _extend(_search_apps(terms, remaining))
    if "3d" in types:
        _extend(_search_generic_config_table("3d", "3d", terms, remaining))
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
    if type_id == "money":
        return _money_summary(record_id)
    tbl = _table_for_type(type_id)
    if not tbl:
        return None
    id_col = tbl.get("pk") or "id"
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
    if type_id == "how":
        return {"name": "lp_howto", "pk": "howto_id"}
    if type_id == "file":
        return get_table_def("files")
    if type_id == "media":
        return {"name": "lp_media", "pk": "media_id"}
    if type_id == "audio":
        return get_table_def("audio")
    if type_id == "place":
        return get_table_def("places")
    if type_id == "album":
        return {"name": "lp_albums", "pk": "album_id"}
    if type_id == "app":
        return {"name": "lp_app", "pk": "app_id"}
    if type_id == "3d":
        return get_table_def("3d")
    if type_id == "project":
        return {"name": "lp_project_workspaces", "pk": "project_id"}
    return None


def _search_notes(terms, limit):
    tbl = get_table_def("notes")
    if not tbl:
        return []
    cols = ["id", "file_name", "path"]
    rows = _search_table(tbl["name"], cols, ["file_name", "path"], terms, limit)
    return [
        _summary_from_values("note", row["id"], row.get("file_name"), row.get("path"))
        for row in rows
    ]


def _search_tasks(terms, limit):
    tbl = get_table_def("tasks")
    if not tbl:
        return []
    cols = ["id", "title", "content", "due_date", "area"]
    rows = _search_table(tbl["name"], cols, ["title", "content"], terms, limit)
    return [
        _summary_from_values(
            "task",
            row["id"],
            row.get("title"),
            row.get("due_date") or row.get("area"),
        )
        for row in rows
    ]


def _search_events(terms, limit):
    tbl = get_table_def("calendar")
    if not tbl:
        return []
    cols = ["id", "title", "content", "event_date", "area"]
    rows = _search_table(tbl["name"], cols, ["title", "content"], terms, limit)
    return [
        _summary_from_values(
            "event",
            row["id"],
            row.get("title"),
            row.get("event_date") or row.get("area"),
        )
        for row in rows
    ]


def _search_howtos(terms, limit):
    conn = data._get_conn()
    if not _table_exists(conn, "lp_howto"):
        return []
    cols = ["howto_id", "title", "summary", "area_id", "status"]
    rows = _search_table("lp_howto", cols, ["title", "summary", "markdown_full_content"], terms, limit)
    return [
        _summary_from_values(
            "how",
            row["howto_id"],
            row.get("title"),
            row.get("area_id") or row.get("status"),
        )
        for row in rows
    ]


def _search_files(terms, limit):
    tbl = get_table_def("files")
    if not tbl:
        return []
    cols = ["id", "filelist_name", "path", "area"]
    rows = _search_table(tbl["name"], cols, ["filelist_name", "path"], terms, limit)
    return [
        _summary_from_values(
            "file",
            row["id"],
            row.get("filelist_name"),
            row.get("path") or row.get("area"),
        )
        for row in rows
    ]


def _search_media(terms, limit):
    conn = data._get_conn()
    if not _table_exists(conn, "lp_media"):
        return []
    cols = ["media_id", "filename", "path", "media_type", "mtime_utc"]
    rows = _search_table("lp_media", cols, ["filename", "path", "media_type"], terms, limit)
    return [
        _summary_from_values(
            "media",
            row["media_id"],
            row.get("filename"),
            row.get("media_type") or row.get("mtime_utc"),
        )
        for row in rows
    ]


def _search_audio(terms, limit):
    tbl = get_table_def("audio")
    if not tbl:
        return []
    cols = ["id", "file_name", "path", "artist", "album", "song"]
    rows = _search_table(tbl["name"], cols, ["file_name", "path", "artist", "album", "song"], terms, limit)
    return [
        _summary_from_values(
            "audio",
            row["id"],
            row.get("song") or row.get("file_name"),
            row.get("artist") or row.get("album") or row.get("path"),
        )
        for row in rows
    ]


def _search_places(terms, limit):
    tbl = get_table_def("places")
    if not tbl:
        return []
    cols = ["id", "name", "desc", "suburb", "state", "country"]
    rows = _search_table(tbl["name"], cols, ["name", "desc", "suburb", "state", "country"], terms, limit)
    return [
        _summary_from_values(
            "place",
            row["id"],
            row.get("name"),
            row.get("suburb") or row.get("state") or row.get("country"),
        )
        for row in rows
    ]


def _search_money(terms, limit):
    conn = data._get_conn()
    results = []
    for section in getattr(__import__("common.config", fromlist=["MONEY_SECTIONS"]), "MONEY_SECTIONS", []):
        if len(results) >= limit:
            break
        table_name = section.get("table")
        pk = section.get("pk")
        if not table_name or not pk or not _table_exists(conn, table_name):
            continue
        columns = [col["name"] for col in section.get("columns", [])]
        search_cols = [col["name"] for col in section.get("columns", []) if col.get("type") in ("text", "textarea", "select")]
        if not search_cols:
            continue
        cols = [pk] + columns
        rows = _search_table(table_name, cols, search_cols, terms, max(1, limit - len(results)))
        title_col = _money_title_column(section)
        for row in rows:
            results.append(
                _summary_from_values(
                    "money",
                    f"{section['id']}:{row[pk]}",
                    row.get(title_col) or section.get("label"),
                    section.get("label"),
                )
            )
    return results


def _search_albums(terms, limit):
    conn = data._get_conn()
    if not _table_exists(conn, "lp_albums"):
        return []
    rows = _search_table("lp_albums", ["album_id", "title", "description", "album_type"], ["title", "description", "album_type"], terms, limit)
    return [
        _summary_from_values("album", row["album_id"], row.get("title"), row.get("album_type"))
        for row in rows
    ]


def _search_apps(terms, limit):
    conn = data._get_conn()
    if not _table_exists(conn, "lp_app"):
        return []
    cols = ["app_id", "title", "kind", "path", "repository_url", "website_url", "language", "tags"]
    rows = _search_table(
        "lp_app",
        cols,
        ["title", "kind", "description", "path", "repository_url", "website_url", "language", "tags"],
        terms,
        limit,
    )
    return [
        _summary_from_values(
            "app",
            row["app_id"],
            row.get("title"),
            row.get("kind") or row.get("path") or row.get("website_url"),
        )
        for row in rows
    ]


def _search_generic_config_table(route_id, type_id, terms, limit):
    tbl = get_table_def(route_id)
    if not tbl:
        return []
    title_col = "title" if "title" in tbl["col_list"] else ("file_name" if "file_name" in tbl["col_list"] else tbl["col_list"][0])
    subtitle_col = "path" if "path" in tbl["col_list"] else ("area" if "area" in tbl["col_list"] else "")
    search_cols = [col for col in [title_col, subtitle_col] if col]
    rows = _search_table(tbl["name"], ["id"] + tbl["col_list"], search_cols, terms, limit)
    return [
        _summary_from_values(type_id, row["id"], row.get(title_col), row.get(subtitle_col) if subtitle_col else "")
        for row in rows
    ]


def _search_contacts(terms, limit):
    conn = data._get_conn()
    if not _table_exists(conn, "lp_contacts"):
        return []
    existing_cols = _table_columns(conn, "lp_contacts")
    if not {"contact_id", "display_name", "normalized_name"}.issubset(existing_cols):
        return []
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        term_conditions.append("(lower(display_name) LIKE ? OR lower(normalized_name) LIKE ?)")
        params.extend([like_value, like_value])
    where_clause = " AND ".join(term_conditions) if term_conditions else "1=1"
    sql = (
        "SELECT contact_id, display_name, normalized_name "
        "FROM lp_contacts "
        f"WHERE {where_clause} "
        "ORDER BY display_name "
        "LIMIT ?"
    )
    params.append(int(limit or 20))
    rows = conn.execute(sql, params).fetchall()
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
        return row.get("title"), row.get("due_date") or row.get("area")
    if type_id == "event":
        return row.get("title"), row.get("event_date") or row.get("area")
    if type_id == "how":
        return row.get("title"), row.get("area_id") or row.get("status")
    if type_id == "file":
        return row.get("filelist_name"), row.get("path")
    if type_id == "media":
        return row.get("filename"), row.get("media_type") or row.get("path")
    if type_id == "audio":
        return row.get("song") or row.get("file_name"), row.get("artist") or row.get("album") or row.get("path")
    if type_id == "place":
        subtitle = row.get("suburb") or row.get("state") or row.get("country")
        return row.get("name"), subtitle
    if type_id == "album":
        return row.get("title"), row.get("album_type") or row.get("description")
    if type_id == "app":
        return row.get("title"), row.get("kind") or row.get("path") or row.get("website_url")
    if type_id == "3d":
        return row.get("file_name"), row.get("path")
    if type_id == "project":
        return row.get("name"), row.get("status")
    return "", ""


def _search_table(tbl_name, cols, search_cols, terms, limit):
    if not search_cols or not terms:
        return []
    conn = data._get_conn()
    if not _table_exists(conn, tbl_name):
        return []
    existing_cols = _table_columns(conn, tbl_name)
    cols = [col for col in cols if col in existing_cols]
    search_cols = [col for col in search_cols if col in existing_cols]
    if not cols or not search_cols:
        return []
    term_conditions = []
    params = []
    for term in terms:
        like_value = f"%{term}%"
        condition = " OR ".join([f"lower({col}) LIKE ?" for col in search_cols])
        term_conditions.append(f"({condition})")
        params.extend([like_value] * len(search_cols))
    where_clause = " AND ".join(term_conditions)
    sql = f"SELECT {', '.join(cols)} FROM {tbl_name} WHERE {where_clause} LIMIT ?"
    params.append(int(limit or 20))
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _table_exists(conn, table_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def _table_columns(conn, table_name):
    try:
        return {row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    except Exception:
        return set()


def _money_title_column(section):
    preferred = ("name", "item", "supplier", "source", "symbol", "company_name", "institution", "domain")
    columns = [col["name"] for col in section.get("columns", [])]
    for col_name in preferred:
        if col_name in columns:
            return col_name
    return columns[0] if columns else section.get("pk")


def _money_summary(record_id):
    if ":" not in str(record_id):
        return None
    section_id, raw_id = str(record_id).split(":", 1)
    from modules.money import dao as money_dao

    section = money_dao.section(section_id)
    record = money_dao.get_record(section_id, raw_id)
    if not record:
        return None
    title_col = _money_title_column(section)
    return _summary_from_values(
        "money",
        record_id,
        record.get(title_col) or section.get("label"),
        section.get("label"),
    )
