from datetime import datetime
import sqlite3


LINK_TYPE_VOCAB = [
    "related",
    "mentions",
    "attachment",
    "about",
    "assigned_to",
    "calls",
    "emails",
    "located_at",
    "depends_on",
]

LINK_FIELDS = [
    "link_id",
    "src_type",
    "src_id",
    "dst_type",
    "dst_id",
    "link_type",
    "label",
    "sort_order",
    "created_utc",
    "created_by",
    "context_type",
    "context_id",
]

LINKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_links (
    link_id INTEGER PRIMARY KEY,
    src_type TEXT NOT NULL,
    src_id TEXT NOT NULL,
    dst_type TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    label TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_utc TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'ui',
    context_type TEXT,
    context_id TEXT,
    UNIQUE (src_type, src_id, dst_type, dst_id, link_type)
);
"""

RECORD_TYPES = {
    "note": {
        "type": "note",
        "icon": "note",
        "display_name_singular": "Note",
        "display_name_plural": "Notes",
        "primary_label_field": "file_name",
        "open_route": lambda rid: f"/notes/view/{rid}",
    },
    "task": {
        "type": "task",
        "icon": "task",
        "display_name_singular": "Task",
        "display_name_plural": "Tasks",
        "primary_label_field": "title",
        "open_route": lambda rid: f"/tasks/edit/{rid}",
    },
    "event": {
        "type": "event",
        "icon": "event",
        "display_name_singular": "Event",
        "display_name_plural": "Events",
        "primary_label_field": "title",
        "open_route": lambda rid: f"/calendar/view/{rid}",
    },
    "file": {
        "type": "file",
        "icon": "file",
        "display_name_singular": "File",
        "display_name_plural": "Files",
        "primary_label_field": "filelist_name",
        "open_route": lambda rid: f"/files/view/{rid}",
        "is_file": True,
    },
    "person": {
        "type": "person",
        "icon": "person",
        "display_name_singular": "Person",
        "display_name_plural": "People",
        "primary_label_field": "display_name",
        "open_route": lambda rid: f"/contacts/view/{rid}",
        "can_be_assigned_to": True,
    },
    "contact": {
        "type": "contact",
        "icon": "person",
        "display_name_singular": "Contact",
        "display_name_plural": "Contacts",
        "primary_label_field": "display_name",
        "open_route": lambda rid: f"/contacts/view/{rid}",
        "can_be_assigned_to": True,
    },
    "place": {
        "type": "place",
        "icon": "place",
        "display_name_singular": "Place",
        "display_name_plural": "Places",
        "primary_label_field": "name",
        "open_route": lambda rid: f"/places/view/{rid}",
        "is_location": True,
    },
    "email": {
        "type": "email",
        "icon": "email",
        "display_name_singular": "Email",
        "display_name_plural": "Emails",
        "primary_label_field": "subject",
        "open_route": lambda rid: f"/email/view/{rid}",
    },
}

CONTEXT_DEFAULTS = {
    "task_detail": {
        "task": "depends_on",
        "person": "assigned_to",
        "file": "attachment",
        "place": "located_at",
        "email": "emails",
        "else": "related",
    },
    "note_detail": {
        "task": "related",
        "person": "mentions",
        "file": "attachment",
        "place": "about",
        "email": "related",
        "else": "mentions",
    },
    "event_detail": {
        "task": "related",
        "person": "related",
        "file": "attachment",
        "place": "located_at",
        "email": "emails",
        "else": "related",
    },
    "file_detail": {
        "task": "attachment",
        "person": "related",
        "file": "related",
        "place": "related",
        "email": "related",
        "else": "related",
    },
    "person_detail": {
        "task": "assigned_to",
        "person": "related",
        "file": "related",
        "place": "located_at",
        "email": "emails",
        "else": "related",
    },
    "place_detail": {
        "task": "related",
        "person": "related",
        "file": "related",
        "place": "related",
        "email": "related",
        "else": "related",
    },
    "email_detail": {
        "task": "related",
        "person": "emails",
        "file": "attachment",
        "place": "related",
        "email": "related",
        "else": "emails",
    },
}

FALLBACK_CONTEXTS = {"links_drawer_add", "list_bulk_link", "link_picker"}


def register_record_type(descriptor):
    if not descriptor or "type" not in descriptor:
        raise ValueError("Record type descriptor must include 'type'.")
    type_id = _norm_type_id(descriptor["type"])
    normalized = dict(descriptor)
    normalized["type"] = type_id
    RECORD_TYPES[type_id] = normalized


def get_record_type(type_id):
    return RECORD_TYPES.get(_norm_type_id(type_id))


def list_record_types():
    return list(RECORD_TYPES.values())


def build_open_route(type_id, record_id):
    desc = get_record_type(_norm_type_id(type_id)) or {}
    route = desc.get("open_route")
    if callable(route):
        return route(record_id)
    if isinstance(route, str):
        try:
            return route.format(id=record_id)
        except Exception:
            return route
    return ""


def ensure_links_schema(conn):
    conn.executescript(LINKS_SCHEMA_SQL)


def allowed_link_types(src_type, dst_type):
    src_type = _norm_type_id(src_type)
    dst_type = _norm_type_id(dst_type)
    allowed = {"related"}
    if src_type in {"note", "task", "event"}:
        allowed.add("mentions")
    if src_type in {"note", "event"}:
        allowed.add("about")
    if _is_file(src_type) or _is_file(dst_type):
        allowed.add("attachment")
    if src_type == "task" and dst_type == "task":
        allowed.add("depends_on")
    if src_type == "task" and _is_person(dst_type):
        allowed.add("assigned_to")
    if _is_place(dst_type) and (src_type in {"event", "task"} or _is_person(src_type)):
        allowed.add("located_at")
    if _is_email(src_type) or _is_email(dst_type) or (_is_person(src_type) and _is_person(dst_type)):
        allowed.add("emails")
    if (_is_person(src_type) and _is_person(dst_type)) or (src_type == "task" and _is_person(dst_type)):
        allowed.add("calls")
    return [link_type for link_type in LINK_TYPE_VOCAB if link_type in allowed]


def resolve_link_type(context_type, src_type, dst_type, explicit_type=None, drop_zone_type=None):
    context_type = _norm_context(context_type)
    if context_type == "editor_mention":
        return "mentions"
    if drop_zone_type:
        return drop_zone_type
    if explicit_type:
        return explicit_type
    return default_link_type(context_type, src_type, dst_type)


def default_link_type(context_type, src_type, dst_type):
    context_type = _norm_context(context_type)
    src_type = _norm_type_id(src_type)
    dst_type = _norm_type_id(dst_type)
    if not context_type or context_type in FALLBACK_CONTEXTS:
        return _fallback_link_type(src_type, dst_type)
    defaults = CONTEXT_DEFAULTS.get(context_type)
    if not defaults:
        return _fallback_link_type(src_type, dst_type)
    category = _dst_category(dst_type)
    return defaults.get(category, defaults["else"])


def create_link(conn, payload):
    values = _normalize_link_payload(payload)
    sql = (
        "INSERT INTO lp_links "
        "(src_type, src_id, dst_type, dst_id, link_type, label, sort_order, created_utc, created_by, context_type, context_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = [
        values["src_type"],
        values["src_id"],
        values["dst_type"],
        values["dst_id"],
        values["link_type"],
        values.get("label"),
        values["sort_order"],
        values["created_utc"],
        values["created_by"],
        values.get("context_type"),
        values.get("context_id"),
    ]
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        link_id = cur.lastrowid
        _log_user_link_change(conn, "link_create", link_id, before=None, after=get_link(conn, link_id))
        return {"created": True, "duplicate": False, "link_id": link_id}
    except sqlite3.IntegrityError:
        existing = _find_existing_link_id(
            conn,
            values["src_type"],
            values["src_id"],
            values["dst_type"],
            values["dst_id"],
            values["link_type"],
        )
        return {"created": False, "duplicate": True, "link_id": existing}


def list_outgoing(conn, src_type, src_id):
    sql = (
        "SELECT "
        + ", ".join(LINK_FIELDS)
        + " FROM lp_links "
        "WHERE src_type = ? AND src_id = ? "
        "ORDER BY link_type, sort_order, link_id"
    )
    rows = conn.execute(sql, [_norm_type_id(src_type), str(src_id)]).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_incoming(conn, dst_type, dst_id):
    sql = (
        "SELECT "
        + ", ".join(LINK_FIELDS)
        + " FROM lp_links "
        "WHERE dst_type = ? AND dst_id = ? "
        "ORDER BY link_type, sort_order, link_id"
    )
    rows = conn.execute(sql, [_norm_type_id(dst_type), str(dst_id)]).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_link(conn, link_id):
    sql = "SELECT " + ", ".join(LINK_FIELDS) + " FROM lp_links WHERE link_id = ?"
    row = conn.execute(sql, [link_id]).fetchone()
    return _row_to_dict(row) if row else None


def update_link(conn, link_id, patch):
    patch = patch or {}
    fields = {k: patch.get(k) for k in ("link_type", "label", "sort_order") if k in patch}
    if not fields:
        return False
    before = get_link(conn, link_id)
    set_clause = ", ".join([f"{field} = ?" for field in fields])
    params = list(fields.values())
    params.append(link_id)
    sql = f"UPDATE lp_links SET {set_clause} WHERE link_id = ?"
    cur = conn.execute(sql, params)
    conn.commit()
    if cur.rowcount > 0:
        after = get_link(conn, link_id)
        _log_user_link_change(conn, "link_update", link_id, before=before, after=after)
    return cur.rowcount > 0


def delete_link(conn, link_id):
    before = get_link(conn, link_id)
    cur = conn.execute("DELETE FROM lp_links WHERE link_id = ?", [link_id])
    conn.commit()
    if cur.rowcount > 0:
        _log_user_link_change(conn, "link_delete", link_id, before=before, after=None)
    return cur.rowcount > 0


def _normalize_link_payload(payload):
    if not payload:
        raise ValueError("Link payload is required.")
    required = ["src_type", "src_id", "dst_type", "dst_id", "link_type"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValueError(f"Missing link fields: {', '.join(missing)}")
    values = dict(payload)
    values["src_type"] = _norm_type_id(values["src_type"])
    values["dst_type"] = _norm_type_id(values["dst_type"])
    values["src_id"] = str(values["src_id"])
    values["dst_id"] = str(values["dst_id"])
    if not values.get("sort_order") and values.get("sort_order") != 0:
        values["sort_order"] = 100
    if not values.get("created_utc"):
        values["created_utc"] = _utc_now()
    if not values.get("created_by"):
        values["created_by"] = "ui"
    return values


def _utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _find_existing_link_id(conn, src_type, src_id, dst_type, dst_id, link_type):
    sql = (
        "SELECT link_id FROM lp_links "
        "WHERE src_type = ? AND src_id = ? AND dst_type = ? AND dst_id = ? AND link_type = ?"
    )
    row = conn.execute(sql, [src_type, src_id, dst_type, dst_id, link_type]).fetchone()
    if not row:
        return None
    if isinstance(row, sqlite3.Row):
        return row["link_id"]
    return row[0]


def _row_to_dict(row):
    if row is None:
        return None
    try:
        return dict(row)
    except Exception:
        return {col: row[idx] for idx, col in enumerate(LINK_FIELDS)}


def _is_file(type_id):
    desc = get_record_type(_norm_type_id(type_id)) or {}
    return bool(desc.get("is_file"))


def _is_person(type_id):
    desc = get_record_type(_norm_type_id(type_id)) or {}
    return bool(desc.get("can_be_assigned_to"))


def _is_place(type_id):
    desc = get_record_type(_norm_type_id(type_id)) or {}
    return bool(desc.get("is_location"))


def _is_email(type_id):
    return _norm_type_id(type_id) == "email"


def _dst_category(dst_type):
    dst_type = _norm_type_id(dst_type)
    if dst_type == "task":
        return "task"
    if _is_person(dst_type):
        return "person"
    if _is_file(dst_type):
        return "file"
    if _is_place(dst_type):
        return "place"
    if _is_email(dst_type):
        return "email"
    return "else"


def _fallback_link_type(src_type, dst_type):
    src_type = _norm_type_id(src_type)
    dst_type = _norm_type_id(dst_type)
    if _is_file(dst_type):
        return "attachment"
    if src_type == "task" and dst_type == "task":
        return "depends_on"
    if _is_person(dst_type) and src_type == "task":
        return "assigned_to"
    if _is_place(dst_type) and (src_type in {"event", "task"} or _is_person(src_type)):
        return "located_at"
    if _is_email(dst_type) or src_type == "email":
        return "emails"
    if src_type == "note":
        return "mentions"
    return "related"


def _norm_context(context_type):
    return (context_type or "").strip().lower()


def _norm_type_id(type_id):
    value = (type_id or "").strip().lower()
    aliases = {
        "notes": "note",
        "tasks": "task",
        "events": "event",
        "calendar": "event",
        "files": "file",
        "places": "place",
        "people": "person",
        "persons": "person",
        "contacts": "contact",
    }
    return aliases.get(value, value)


def _log_user_link_change(conn, action, link_id, before=None, after=None):
    try:
        from common import utils as utils_mod

        context_type = None
        context_id = None
        sample = after or before or {}
        if isinstance(sample, dict):
            context_type = sample.get("context_type")
            context_id = sample.get("context_id")
        utils_mod.lg_usr(
            action=action,
            entity_type="lp_links",
            entity_id=link_id,
            before=before,
            after=after,
            context_type=context_type,
            context_id=context_id,
            conn=conn,
        )
    except Exception:
        pass
