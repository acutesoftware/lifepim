import json
import re
import sqlite3
from datetime import datetime, timezone

from common import data as db
from common import areas as areas_mod


CODE_RE = re.compile(r"^[A-Z0-9_]+$")

OBJECT_TYPE_CODES = [
    "NOTE",
    "TASK",
    "PROJECT",
    "LIST",
    "EVENT",
    "HOWTO",
    "PERSON",
    "PLACE",
    "OBJECT",
    "FILE",
    "MEDIA",
    "AUDIO",
    "DATA",
    "MONEY",
    "APP",
    "GOAL",
    "LOG",
    "COLLECTION",
]
TAB_CODES = ["NOTES", "GOALS", "HOW", "FILES", "PEOPLE", "PLACES", "DATA", "3D", "MONEY", "APPS", "CALENDAR", "MEDIA", "AUDIO"]
DATE_BEHAVIOUR_CODES = ["NONE", "CREATED", "OCCURRED", "DUE", "START_END", "RECURRING", "MEASUREMENT"]
MAPPING_STATUS_CODES = ["CONFIRMED", "NEEDS_TEMPLATE", "NEEDS_VIEW", "NEEDS_OBJECT", "EXTERNAL_SYSTEM", "DO_NOT_STORE", "UNDECIDED"]
TEMPLATE_TYPE_CODES = ["NOTE", "PROJECT", "LIST", "EVENT", "HOWTO", "OBJECT", "MULTI_OBJECT"]
VIEW_TYPE_CODES = ["TABLE", "LIST", "TIMELINE", "CALENDAR", "BOARD", "GALLERY", "MAP", "TREE", "DASHBOARD", "DETAIL"]
NO_TAB_CODE = "__NO_TAB__"
UNASSIGNED_AREA_ID = "__UNASSIGNED__"
ROOT_KIND_CODES = {"NOTE", "TASK", "PROJECT", "LIST", "EVENT", "HOWTO", "PERSON", "PLACE", "OBJECT", "FILE", "DATA_ITEM", "MONEY_ITEM", "APP_ITEM", "MEDIA_ITEM", "AUDIO_ITEM", "LOG_ENTRY", "COLLECTION"}
CONTENT_CATALOG_SAMPLE_SEED_VERSION = 1
CONTENT_CATALOG_SAMPLE_SEED_KEY = "sample_seed_version"
CONTENT_CATALOG_SCHEMA_VERSION_KEY = "content_catalog_schema_version"
CONTENT_CATALOG_SCHEMA_VERSION = 2


CONTENT_CATALOG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_template (
    template_id          INTEGER PRIMARY KEY,
    template_code        TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    description          TEXT,
    template_type_code   TEXT NOT NULL,
    target_object_type   TEXT,
    target_tab_code      TEXT,
    template_content     TEXT,
    template_config      TEXT,
    is_active            INTEGER NOT NULL DEFAULT 1,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lp_content_view (
    content_view_id      INTEGER PRIMARY KEY,
    view_code            TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    description          TEXT,
    tab_code             TEXT,
    view_type_code       TEXT NOT NULL,
    view_config          TEXT,
    is_active            INTEGER NOT NULL DEFAULT 1,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lp_content_kind (
    content_kind_id INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    area_id         TEXT,
    tab_code        TEXT,
    comment         TEXT
);

CREATE TABLE IF NOT EXISTS lp_content_kind_area (
    content_kind_area_id  INTEGER PRIMARY KEY,
    content_kind_id       INTEGER NOT NULL,
    area_id               TEXT NOT NULL,
    is_default            INTEGER NOT NULL DEFAULT 0,
    display_name_override TEXT,
    sort_order            INTEGER NOT NULL DEFAULT 0,
    notes                 TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (content_kind_id) REFERENCES lp_content_kind(content_kind_id),
    UNIQUE (content_kind_id, area_id)
);

CREATE TABLE IF NOT EXISTS lp_content_kind_template (
    content_kind_template_id INTEGER PRIMARY KEY,
    content_kind_id          INTEGER NOT NULL,
    template_id              INTEGER NOT NULL,
    is_default               INTEGER NOT NULL DEFAULT 0,
    sort_order               INTEGER NOT NULL DEFAULT 0,
    notes                    TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    FOREIGN KEY (content_kind_id) REFERENCES lp_content_kind(content_kind_id),
    FOREIGN KEY (template_id) REFERENCES lp_template(template_id),
    UNIQUE (content_kind_id, template_id)
);

CREATE TABLE IF NOT EXISTS lp_content_kind_view (
    content_kind_view_id INTEGER PRIMARY KEY,
    content_kind_id      INTEGER NOT NULL,
    content_view_id      INTEGER NOT NULL,
    is_default           INTEGER NOT NULL DEFAULT 0,
    sort_order           INTEGER NOT NULL DEFAULT 0,
    notes                TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    FOREIGN KEY (content_kind_id) REFERENCES lp_content_kind(content_kind_id),
    FOREIGN KEY (content_view_id) REFERENCES lp_content_view(content_view_id),
    UNIQUE (content_kind_id, content_view_id)
);

CREATE TABLE IF NOT EXISTS lp_content_pattern (
    content_pattern_id  INTEGER PRIMARY KEY,
    pattern_code        TEXT NOT NULL UNIQUE,
    content_kind_id     INTEGER NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    default_area_id     TEXT,
    default_template_id INTEGER,
    default_view_id     INTEGER,
    creation_config     TEXT,
    view_filter_config  TEXT,
    is_active           INTEGER NOT NULL DEFAULT 1,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (content_kind_id) REFERENCES lp_content_kind(content_kind_id),
    FOREIGN KEY (default_template_id) REFERENCES lp_template(template_id),
    FOREIGN KEY (default_view_id) REFERENCES lp_content_view(content_view_id)
);

CREATE TABLE IF NOT EXISTS lp_content_catalog_meta (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_content_kind_area_area ON lp_content_kind_area(area_id);
CREATE INDEX IF NOT EXISTS ix_lp_content_pattern_kind ON lp_content_pattern(content_kind_id);
"""

_READY_CONN_IDS = set()


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_conn(conn=None):
    conn = db._get_conn() if conn is None else conn
    if conn.row_factory is None:
        conn.row_factory = sqlite3.Row
    return conn


CONTENT_KIND_V2_COLUMNS = ["content_kind_id", "name", "area_id", "tab_code", "comment"]


def ensure_content_catalog_schema(conn=None, seed=True):
    conn = _get_conn(conn)
    conn_id = id(conn)
    if conn_id in _READY_CONN_IDS and not _content_catalog_schema_is_current(conn):
        _READY_CONN_IDS.discard(conn_id)
    if conn_id not in _READY_CONN_IDS:
        areas_mod.ensure_areas_schema(conn)
        conn.executescript(CONTENT_CATALOG_SCHEMA_SQL)
        _migrate_content_kind_v2_if_needed(conn)
        _create_content_kind_v2_indexes(conn)
        _set_catalog_schema_version(conn)
        _dedupe_default_links(conn)
        _migrate_canonical_table_names(conn)
        _create_default_link_indexes(conn)
        conn.commit()
        _READY_CONN_IDS.add(conn_id)


def _content_catalog_schema_is_current(conn):
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('lp_content_kind','lp_content_kind_area','lp_content_pattern','lp_template','lp_content_kind_template','lp_content_view','lp_content_kind_view','lp_content_catalog_meta')"
        ).fetchall()
    except Exception:
        return False
    if len(rows) != 8:
        return False
    try:
        return _content_kind_schema_state(conn) == "new"
    except Exception:
        return False


def _table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return []
    columns = []
    for row in rows:
        try:
            columns.append(row["name"])
        except (TypeError, KeyError, IndexError):
            columns.append(row[1])
    return columns


def _content_kind_schema_state(conn):
    columns = _table_columns(conn, "lp_content_kind")
    if not columns:
        return "missing"
    column_set = set(columns)
    if "kind_code" in column_set:
        return "old"
    if columns == CONTENT_KIND_V2_COLUMNS:
        return "new"
    if column_set == set(CONTENT_KIND_V2_COLUMNS):
        return "new"
    raise RuntimeError(f"Unrecognised lp_content_kind schema: {', '.join(columns)}")


def _migrate_content_kind_v2_if_needed(conn):
    state = _content_kind_schema_state(conn)
    if state == "new":
        return False
    if state != "old":
        raise RuntimeError("Cannot migrate lp_content_kind because the schema is neither old nor new.")
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;

        CREATE TABLE lp_content_kind_legacy_v1 AS
        SELECT *
        FROM lp_content_kind;

        CREATE TABLE lp_content_kind_new (
            content_kind_id INTEGER PRIMARY KEY,
            name            TEXT NOT NULL,
            area_id         TEXT,
            tab_code        TEXT,
            comment         TEXT
        );

        INSERT INTO lp_content_kind_new (
            content_kind_id,
            name,
            area_id,
            tab_code,
            comment
        )
        SELECT
            ck.content_kind_id,
            TRIM(ck.name),
            (
                SELECT cka.area_id
                FROM lp_content_kind_area cka
                WHERE cka.content_kind_id = ck.content_kind_id
                ORDER BY
                    cka.is_default DESC,
                    cka.sort_order,
                    cka.content_kind_area_id
                LIMIT 1
            ) AS area_id,
            NULLIF(TRIM(ck.canonical_tab_code), '') AS tab_code,
            NULLIF(
                TRIM(
                    COALESCE(NULLIF(TRIM(ck.description), ''), '')
                    ||
                    CASE
                        WHEN NULLIF(TRIM(ck.description), '') IS NOT NULL
                         AND NULLIF(TRIM(ck.notes), '') IS NOT NULL
                         AND TRIM(ck.description) <> TRIM(ck.notes)
                        THEN CHAR(10)
                        ELSE ''
                    END
                    ||
                    CASE
                        WHEN NULLIF(TRIM(ck.notes), '') IS NOT NULL
                         AND (
                             NULLIF(TRIM(ck.description), '') IS NULL
                             OR TRIM(ck.notes) <> TRIM(ck.description)
                         )
                        THEN TRIM(ck.notes)
                        ELSE ''
                    END
                ),
                ''
            ) AS comment
        FROM lp_content_kind ck
        WHERE NULLIF(TRIM(ck.name), '') IS NOT NULL;

        DROP TABLE lp_content_kind;

        ALTER TABLE lp_content_kind_new
        RENAME TO lp_content_kind;

        CREATE INDEX ix_lp_content_kind_area
            ON lp_content_kind(area_id);

        CREATE INDEX ix_lp_content_kind_tab
            ON lp_content_kind(tab_code);

        CREATE INDEX ix_lp_content_kind_name
            ON lp_content_kind(name);

        PRAGMA foreign_keys = ON;
        """
    )
    failures = conn.execute("PRAGMA foreign_key_check").fetchall()
    if failures:
        raise RuntimeError(f"Content Catalog migration failed foreign_key_check with {len(failures)} error(s).")
    return True


def _create_content_kind_v2_indexes(conn):
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_content_kind_area ON lp_content_kind(area_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_content_kind_tab ON lp_content_kind(tab_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_content_kind_name ON lp_content_kind(name)")


def _set_catalog_schema_version(conn):
    conn.execute(
        "INSERT INTO lp_content_catalog_meta(key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (CONTENT_CATALOG_SCHEMA_VERSION_KEY, str(CONTENT_CATALOG_SCHEMA_VERSION), _utc_now()),
    )


def _dedupe_default_links(conn):
    for table_name, target_col in [
        ("lp_content_kind_template", "template_id"),
        ("lp_content_kind_view", "content_view_id"),
    ]:
        rows = conn.execute(
            f"SELECT content_kind_id, MIN({target_col}) AS keep_id, COUNT(1) AS cnt "
            f"FROM {table_name} WHERE is_default = 1 GROUP BY content_kind_id HAVING cnt > 1"
        ).fetchall()
        for row in rows:
            conn.execute(
                f"UPDATE {table_name} SET is_default = CASE WHEN {target_col} = ? THEN 1 ELSE 0 END "
                "WHERE content_kind_id = ? AND is_default = 1",
                (row["keep_id"], row["content_kind_id"]),
            )


def _create_default_link_indexes(conn):
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_kind_default_template "
        "ON lp_content_kind_template(content_kind_id) WHERE is_default = 1"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_content_kind_default_view "
        "ON lp_content_kind_view(content_kind_id) WHERE is_default = 1"
    )


def _migrate_canonical_table_names(conn):
    if "canonical_table_name" not in set(_table_columns(conn, "lp_content_kind")):
        return
    conn.execute(
        "UPDATE lp_content_kind SET canonical_table_name = 'lp_calendar_events', updated_at = ? "
        "WHERE canonical_table_name = 'lp_cal_events'",
        (_utc_now(),),
    )


def _sample_seed_version(conn):
    row = conn.execute("SELECT value FROM lp_content_catalog_meta WHERE key = ?", (CONTENT_CATALOG_SAMPLE_SEED_KEY,)).fetchone()
    if not row:
        return 0
    try:
        return int(row["value"])
    except (TypeError, ValueError):
        return 0


def _set_sample_seed_version(conn, version=CONTENT_CATALOG_SAMPLE_SEED_VERSION):
    conn.execute(
        "INSERT INTO lp_content_catalog_meta(key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (CONTENT_CATALOG_SAMPLE_SEED_KEY, str(int(version)), _utc_now()),
    )


def _sample_seed_needed(conn):
    if _sample_seed_version(conn) >= CONTENT_CATALOG_SAMPLE_SEED_VERSION:
        return False
    existing = conn.execute("SELECT 1 FROM lp_content_kind LIMIT 1").fetchone()
    if existing:
        _set_sample_seed_version(conn)
        conn.commit()
        return False
    return True


def normalize_code(value):
    return (value or "").strip().upper().replace(" ", "_").replace("-", "_")


def code_from_name(value):
    text = "".join(ch.upper() if ch.isalnum() else "_" for ch in (value or "").strip())
    text = "_".join([part for part in text.split("_") if part])
    return text


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _clean_optional(value):
    text = _clean_text(value)
    return text or None


def _bool_int(value):
    return 1 if value in (1, True, "1", "true", "TRUE", "on", "yes", "YES") else 0


def _truthy(value):
    return value in (1, True, "1", "true", "TRUE", "on", "yes", "YES")


def _int_or_none(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_value(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_code(value, field_name="Code"):
    code = (value or "").strip().upper()
    if not code:
        raise ValueError(f"{field_name} is required.")
    if not CODE_RE.match(code):
        raise ValueError(f"{field_name} must use only A-Z, 0-9, and underscores.")
    return code


def validate_json_text(value, field_name):
    text = _clean_text(value)
    if not text:
        return None
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} contains invalid JSON: {exc.msg}.")
    return text


def _require_name(values):
    name = _clean_text(values.get("name"))
    if not name:
        raise ValueError("Name is required.")
    return name


def _kind_id_by_code(conn, code):
    if not code:
        return None
    row = conn.execute("SELECT content_kind_id FROM lp_content_kind WHERE kind_code = ?", (normalize_code(code),)).fetchone()
    return row["content_kind_id"] if row else None


def _template_id_by_code(conn, code):
    if not code:
        return None
    row = conn.execute("SELECT template_id FROM lp_template WHERE template_code = ?", (normalize_code(code),)).fetchone()
    return row["template_id"] if row else None


def _view_id_by_code(conn, code):
    if not code:
        return None
    row = conn.execute("SELECT content_view_id FROM lp_content_view WHERE view_code = ?", (normalize_code(code),)).fetchone()
    return row["content_view_id"] if row else None


def _area_id_by_name_or_id(conn, value):
    text = _clean_text(value)
    if not text:
        return None
    row = conn.execute(
        "SELECT area_id FROM lp_areas WHERE lower(area_id) = lower(?) AND is_header = 0 ORDER BY owner_user_id IS NOT NULL LIMIT 1",
        (text,),
    ).fetchone()
    if row:
        return row["area_id"]
    row = conn.execute(
        "SELECT area_id FROM lp_areas WHERE lower(area_name) = lower(?) AND is_header = 0 ORDER BY owner_user_id IS NOT NULL LIMIT 1",
        (text,),
    ).fetchone()
    return row["area_id"] if row else None


def area_options(conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    rows = conn.execute(
        "SELECT area_id, area_name, icon FROM lp_areas WHERE is_header = 0 AND is_system = 0 AND status = 'active' "
        "GROUP BY area_id ORDER BY lower(area_name), lower(area_id)"
    ).fetchall()
    return [dict(row) for row in rows]


def content_kind_options(conn=None):
    rows = list_content_kinds(conn=conn)
    return [{"value": row["content_kind_id"], "label": row["name"]} for row in rows]


def template_options(conn=None):
    rows = list_templates(conn=conn, include_inactive=True)
    return [{"value": row["template_id"], "label": f"{row['template_code']} - {row['name']}", "code": row["template_code"]} for row in rows]


def view_options(conn=None):
    rows = list_content_views(conn=conn, include_inactive=True)
    return [{"value": row["content_view_id"], "label": f"{row['view_code']} - {row['name']}", "code": row["view_code"]} for row in rows]


def get_admin_config(conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn)
    return {
        "objectTypeCodes": OBJECT_TYPE_CODES,
        "tabCodes": TAB_CODES,
        "templateTypeCodes": TEMPLATE_TYPE_CODES,
        "viewTypeCodes": VIEW_TYPE_CODES,
        "areas": area_options(conn),
        "contentKinds": content_kind_options(conn),
        "templates": template_options(conn),
        "views": view_options(conn),
        "noTabCode": NO_TAB_CODE,
        "unassignedAreaId": UNASSIGNED_AREA_ID,
    }


def create_content_kind(values, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    name = _require_name(values)
    area_id = _validated_area_id(values.get("area_id"), conn)
    tab_code = _validated_tab_code(values.get("tab_code"))
    with conn:
        cur = conn.execute(
            "INSERT INTO lp_content_kind (name, area_id, tab_code, comment) VALUES (?, ?, ?, ?)",
            (name, area_id, tab_code, _clean_optional(values.get("comment"))),
        )
    return cur.lastrowid


def update_content_kind(content_kind_id, values, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    content_kind_id = int(content_kind_id)
    name = _require_name(values)
    area_id = _validated_area_id(values.get("area_id"), conn)
    tab_code = _validated_tab_code(values.get("tab_code"))
    with conn:
        conn.execute(
            "UPDATE lp_content_kind SET name = ?, area_id = ?, tab_code = ?, comment = ? WHERE content_kind_id = ?",
            (name, area_id, tab_code, _clean_optional(values.get("comment")), content_kind_id),
        )
    return True


def deactivate_content_kind(content_kind_id, conn=None):
    return remove_content_kind(content_kind_id, conn=conn)


def remove_content_kind(content_kind_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    content_kind_id = int(content_kind_id)
    pattern = conn.execute(
        "SELECT name FROM lp_content_pattern WHERE content_kind_id = ? LIMIT 1",
        (content_kind_id,),
    ).fetchone()
    if pattern:
        raise ValueError(f"Cannot delete this catalog item because it is used by pattern '{pattern['name']}'.")
    with conn:
        conn.execute("DELETE FROM lp_content_kind_area WHERE content_kind_id = ?", (content_kind_id,))
        conn.execute("DELETE FROM lp_content_kind_template WHERE content_kind_id = ?", (content_kind_id,))
        conn.execute("DELETE FROM lp_content_kind_view WHERE content_kind_id = ?", (content_kind_id,))
        conn.execute("DELETE FROM lp_content_kind WHERE content_kind_id = ?", (content_kind_id,))
    return {"removed": True, "deactivated": False}


def _validated_tab_code(value):
    text = normalize_code(value)
    if not text:
        return None
    if text not in TAB_CODES:
        raise ValueError("Tab is invalid.")
    return text


def _validated_area_id(value, conn):
    text = _clean_text(value)
    if not text:
        return None
    row = conn.execute(
        "SELECT 1 FROM lp_areas WHERE area_id = ? AND is_header = 0 LIMIT 1",
        (text,),
    ).fetchone()
    if not row:
        raise ValueError("Area is invalid.")
    return text


def set_content_kind_areas(content_kind_id, area_ids, default_area_id=None, conn=None):
    conn = _get_conn(conn)
    now = _utc_now()
    cleaned = []
    seen = set()
    for area_id in area_ids or []:
        text = _clean_text(area_id)
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    default_area_id = _clean_text(default_area_id)
    if default_area_id and default_area_id not in cleaned:
        cleaned.append(default_area_id)
    conn.execute("DELETE FROM lp_content_kind_area WHERE content_kind_id = ?", (int(content_kind_id),))
    for idx, area_id in enumerate(cleaned):
        conn.execute(
            "INSERT INTO lp_content_kind_area "
            "(content_kind_id, area_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (int(content_kind_id), area_id, 1 if default_area_id and area_id == default_area_id else 0, idx * 10, now, now),
        )
    conn.execute(
        "UPDATE lp_content_kind_area SET is_default = CASE WHEN area_id = ? THEN 1 ELSE 0 END, updated_at = ? WHERE content_kind_id = ?",
        (default_area_id, now, int(content_kind_id)),
    )


def mark_content_kind_area_default(content_kind_id, area_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    with conn:
        conn.execute("UPDATE lp_content_kind_area SET is_default = 0, updated_at = ? WHERE content_kind_id = ?", (now, int(content_kind_id)))
        conn.execute(
            "UPDATE lp_content_kind_area SET is_default = 1, updated_at = ? WHERE content_kind_id = ? AND area_id = ?",
            (now, int(content_kind_id), _clean_text(area_id)),
        )


def _kind_area_rows(conn, visible_area_ids=None):
    visible_area_ids = list(visible_area_ids or [])
    label_map = _area_label_map(conn)
    params = []
    where = ""
    if visible_area_ids:
        where = "WHERE cka.area_id IN (" + ",".join(["?"] * len(visible_area_ids)) + ") "
        params = visible_area_ids
    rows = conn.execute(
        "SELECT cka.content_kind_id, cka.area_id, cka.is_default "
        "FROM lp_content_kind_area cka "
        f"{where}"
        "ORDER BY cka.sort_order, lower(cka.area_id)",
        params,
    ).fetchall()
    by_kind = {}
    for row in rows:
        item = dict(row)
        item["area_name"] = label_map.get(item["area_id"], item["area_id"])
        by_kind.setdefault(row["content_kind_id"], []).append(item)
    return by_kind


def list_content_kinds(conn=None, filters=None, include_inactive=False, visible_area_ids=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    filters = filters or {}
    where = []
    params = []
    tab_filter = filters.get("tab_code") or filters.get("canonical_tab_code")
    if tab_filter not in (None, "", "all"):
        if tab_filter == NO_TAB_CODE:
            where.append("COALESCE(ck.tab_code, '') = ''")
        else:
            where.append("ck.tab_code = ?")
            params.append(tab_filter)
    if filters.get("area_id"):
        if filters.get("area_id") == UNASSIGNED_AREA_ID:
            where.append("COALESCE(ck.area_id, '') = ''")
        else:
            where.append("lower(ck.area_id) = lower(?)")
            params.append(filters["area_id"])
    if filters.get("q"):
        q = f"%{filters['q'].strip()}%"
        where.append("(ck.name LIKE ? OR COALESCE(ck.comment,'') LIKE ?)")
        params.extend([q, q])
    sql = "SELECT ck.* FROM lp_content_kind ck "
    if where:
        sql += "WHERE " + " AND ".join(where) + " "
    sql += "ORDER BY ck.content_kind_id"
    rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    label_map = _area_label_map(conn)
    for row in rows:
        area_id = row.get("area_id") or ""
        row["area_name"] = label_map.get(area_id, area_id)
        row["areas"] = [{"area_id": area_id, "area_name": row["area_name"], "is_default": 1}] if area_id else []
        row["area_ids"] = [area_id] if area_id else []
        row["default_area_id"] = area_id
    return rows


def get_content_kind(content_kind_id, conn=None):
    rows = list_content_kinds(conn=conn, filters={}, include_inactive=True)
    for row in rows:
        if int(row["content_kind_id"]) == int(content_kind_id):
            return row
    return None


def _create_or_update_template(values, template_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    name = _require_name(values)
    code = validate_code(values.get("template_code") or code_from_name(name), "Template code")
    template_config = validate_json_text(values.get("template_config"), "Template config")
    now = _utc_now()
    data = (
        code,
        name,
        _clean_optional(values.get("description")),
        normalize_code(values.get("template_type_code") or "NOTE"),
        _clean_optional(normalize_code(values.get("target_object_type"))),
        _clean_optional(normalize_code(values.get("target_tab_code"))),
        values.get("template_content") or None,
        template_config,
        _bool_int(values.get("is_active", 1)),
        _int_value(values.get("sort_order"), 0),
        _clean_optional(values.get("notes")),
        now,
    )
    with conn:
        if template_id:
            conn.execute(
                "UPDATE lp_template SET template_code = ?, name = ?, description = ?, template_type_code = ?, "
                "target_object_type = ?, target_tab_code = ?, template_content = ?, template_config = ?, is_active = ?, "
                "sort_order = ?, notes = ?, updated_at = ? WHERE template_id = ?",
                data + (int(template_id),),
            )
            result_id = int(template_id)
        else:
            cur = conn.execute(
                "INSERT INTO lp_template "
                "(template_code, name, description, template_type_code, target_object_type, target_tab_code, template_content, "
                "template_config, is_active, sort_order, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                data[:-1] + (now, now),
            )
            result_id = cur.lastrowid
        set_template_content_kinds(result_id, values.get("content_kind_ids") or [], values.get("default_content_kind_id"), conn=conn)
    return result_id


def create_template(values, conn=None):
    return _create_or_update_template(values, None, conn)


def update_template(template_id, values, conn=None):
    return _create_or_update_template(values, template_id, conn)


def deactivate_template(template_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    with conn:
        conn.execute("UPDATE lp_template SET is_active = 0, updated_at = ? WHERE template_id = ?", (_utc_now(), int(template_id)))


def remove_template(template_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    template_id = int(template_id)
    with conn:
        conn.execute("UPDATE lp_content_pattern SET default_template_id = NULL, updated_at = ? WHERE default_template_id = ?", (_utc_now(), template_id))
        conn.execute("DELETE FROM lp_content_kind_template WHERE template_id = ?", (template_id,))
        conn.execute("DELETE FROM lp_template WHERE template_id = ?", (template_id,))
    return {"removed": True, "deactivated": False}


def set_template_content_kinds(template_id, content_kind_ids, default_content_kind_id=None, conn=None):
    conn = _get_conn(conn)
    now = _utc_now()
    cleaned = []
    seen = set()
    for item_id in content_kind_ids or []:
        item_id = _int_or_none(item_id)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        cleaned.append(item_id)
    default_content_kind_id = _int_or_none(default_content_kind_id)
    if default_content_kind_id and default_content_kind_id not in cleaned:
        cleaned.append(default_content_kind_id)
    conn.execute("DELETE FROM lp_content_kind_template WHERE template_id = ?", (int(template_id),))
    if default_content_kind_id:
        conn.execute(
            "UPDATE lp_content_kind_template SET is_default = 0, updated_at = ? "
            "WHERE content_kind_id = ? AND template_id <> ?",
            (now, default_content_kind_id, int(template_id)),
        )
    for idx, content_kind_id in enumerate(cleaned):
        conn.execute(
            "INSERT INTO lp_content_kind_template "
            "(content_kind_id, template_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (content_kind_id, int(template_id), 1 if default_content_kind_id == content_kind_id else 0, idx * 10, now, now),
        )


def set_content_kind_templates(content_kind_id, template_ids, default_template_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    cleaned = []
    seen = set()
    for template_id in template_ids or []:
        template_id = _int_or_none(template_id)
        if not template_id or template_id in seen:
            continue
        seen.add(template_id)
        cleaned.append(template_id)
    default_template_id = _int_or_none(default_template_id)
    if default_template_id and default_template_id not in cleaned:
        cleaned.append(default_template_id)
    with conn:
        conn.execute("DELETE FROM lp_content_kind_template WHERE content_kind_id = ?", (int(content_kind_id),))
        for idx, template_id in enumerate(cleaned):
            conn.execute(
                "INSERT INTO lp_content_kind_template "
                "(content_kind_id, template_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (int(content_kind_id), template_id, 1 if default_template_id == template_id else 0, idx * 10, now, now),
            )


def mark_content_kind_template_default(content_kind_id, template_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    with conn:
        conn.execute("UPDATE lp_content_kind_template SET is_default = 0, updated_at = ? WHERE content_kind_id = ?", (now, int(content_kind_id)))
        conn.execute(
            "UPDATE lp_content_kind_template SET is_default = 1, updated_at = ? WHERE content_kind_id = ? AND template_id = ?",
            (now, int(content_kind_id), int(template_id)),
        )


def list_templates(conn=None, include_inactive=False):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    where = "" if include_inactive else "WHERE t.is_active = 1"
    rows = [dict(row) for row in conn.execute(f"SELECT t.* FROM lp_template t {where} ORDER BY t.sort_order, lower(t.name), t.template_id").fetchall()]
    mapping_rows = conn.execute(
        "SELECT ckt.template_id, ckt.content_kind_id, ckt.is_default, ck.name "
        "FROM lp_content_kind_template ckt JOIN lp_content_kind ck ON ck.content_kind_id = ckt.content_kind_id "
        "ORDER BY ckt.sort_order, lower(ck.name)"
    ).fetchall()
    by_template = {}
    for row in mapping_rows:
        by_template.setdefault(row["template_id"], []).append(dict(row))
    for row in rows:
        links = by_template.get(row["template_id"], [])
        row["content_kinds"] = links
        row["content_kind_ids"] = [link["content_kind_id"] for link in links]
        default = next((link["content_kind_id"] for link in links if int(link.get("is_default") or 0)), "")
        row["default_content_kind_id"] = default
    return rows


def _create_or_update_view(values, content_view_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    name = _require_name(values)
    code = validate_code(values.get("view_code") or code_from_name(name), "View code")
    view_config = validate_json_text(values.get("view_config"), "View config")
    now = _utc_now()
    data = (
        code,
        name,
        _clean_optional(values.get("description")),
        _clean_optional(normalize_code(values.get("tab_code"))),
        normalize_code(values.get("view_type_code") or "LIST"),
        view_config,
        _bool_int(values.get("is_active", 1)),
        _int_value(values.get("sort_order"), 0),
        _clean_optional(values.get("notes")),
        now,
    )
    with conn:
        if content_view_id:
            conn.execute(
                "UPDATE lp_content_view SET view_code = ?, name = ?, description = ?, tab_code = ?, view_type_code = ?, "
                "view_config = ?, is_active = ?, sort_order = ?, notes = ?, updated_at = ? WHERE content_view_id = ?",
                data + (int(content_view_id),),
            )
            result_id = int(content_view_id)
        else:
            cur = conn.execute(
                "INSERT INTO lp_content_view "
                "(view_code, name, description, tab_code, view_type_code, view_config, is_active, sort_order, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                data[:-1] + (now, now),
            )
            result_id = cur.lastrowid
        set_view_content_kinds(result_id, values.get("content_kind_ids") or [], values.get("default_content_kind_id"), conn=conn)
    return result_id


def create_content_view(values, conn=None):
    return _create_or_update_view(values, None, conn)


def update_content_view(content_view_id, values, conn=None):
    return _create_or_update_view(values, content_view_id, conn)


def deactivate_content_view(content_view_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    with conn:
        conn.execute("UPDATE lp_content_view SET is_active = 0, updated_at = ? WHERE content_view_id = ?", (_utc_now(), int(content_view_id)))


def remove_content_view(content_view_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    content_view_id = int(content_view_id)
    with conn:
        conn.execute("UPDATE lp_content_pattern SET default_view_id = NULL, updated_at = ? WHERE default_view_id = ?", (_utc_now(), content_view_id))
        conn.execute("DELETE FROM lp_content_kind_view WHERE content_view_id = ?", (content_view_id,))
        conn.execute("DELETE FROM lp_content_view WHERE content_view_id = ?", (content_view_id,))
    return {"removed": True, "deactivated": False}


def set_view_content_kinds(content_view_id, content_kind_ids, default_content_kind_id=None, conn=None):
    conn = _get_conn(conn)
    now = _utc_now()
    cleaned = []
    seen = set()
    for item_id in content_kind_ids or []:
        item_id = _int_or_none(item_id)
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        cleaned.append(item_id)
    default_content_kind_id = _int_or_none(default_content_kind_id)
    if default_content_kind_id and default_content_kind_id not in cleaned:
        cleaned.append(default_content_kind_id)
    conn.execute("DELETE FROM lp_content_kind_view WHERE content_view_id = ?", (int(content_view_id),))
    if default_content_kind_id:
        conn.execute(
            "UPDATE lp_content_kind_view SET is_default = 0, updated_at = ? "
            "WHERE content_kind_id = ? AND content_view_id <> ?",
            (now, default_content_kind_id, int(content_view_id)),
        )
    for idx, content_kind_id in enumerate(cleaned):
        conn.execute(
            "INSERT INTO lp_content_kind_view "
            "(content_kind_id, content_view_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (content_kind_id, int(content_view_id), 1 if default_content_kind_id == content_kind_id else 0, idx * 10, now, now),
        )


def set_content_kind_views(content_kind_id, content_view_ids, default_view_id=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    cleaned = []
    seen = set()
    for content_view_id in content_view_ids or []:
        content_view_id = _int_or_none(content_view_id)
        if not content_view_id or content_view_id in seen:
            continue
        seen.add(content_view_id)
        cleaned.append(content_view_id)
    default_view_id = _int_or_none(default_view_id)
    if default_view_id and default_view_id not in cleaned:
        cleaned.append(default_view_id)
    with conn:
        conn.execute("DELETE FROM lp_content_kind_view WHERE content_kind_id = ?", (int(content_kind_id),))
        for idx, content_view_id in enumerate(cleaned):
            conn.execute(
                "INSERT INTO lp_content_kind_view "
                "(content_kind_id, content_view_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (int(content_kind_id), content_view_id, 1 if default_view_id == content_view_id else 0, idx * 10, now, now),
            )


def mark_content_kind_view_default(content_kind_id, content_view_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    with conn:
        conn.execute("UPDATE lp_content_kind_view SET is_default = 0, updated_at = ? WHERE content_kind_id = ?", (now, int(content_kind_id)))
        conn.execute(
            "UPDATE lp_content_kind_view SET is_default = 1, updated_at = ? WHERE content_kind_id = ? AND content_view_id = ?",
            (now, int(content_kind_id), int(content_view_id)),
        )


def list_content_views(conn=None, include_inactive=False):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    where = "" if include_inactive else "WHERE v.is_active = 1"
    rows = [dict(row) for row in conn.execute(f"SELECT v.* FROM lp_content_view v {where} ORDER BY v.sort_order, lower(v.name), v.content_view_id").fetchall()]
    mapping_rows = conn.execute(
        "SELECT ckv.content_view_id, ckv.content_kind_id, ckv.is_default, ck.name "
        "FROM lp_content_kind_view ckv JOIN lp_content_kind ck ON ck.content_kind_id = ckv.content_kind_id "
        "ORDER BY ckv.sort_order, lower(ck.name)"
    ).fetchall()
    by_view = {}
    for row in mapping_rows:
        by_view.setdefault(row["content_view_id"], []).append(dict(row))
    for row in rows:
        links = by_view.get(row["content_view_id"], [])
        row["content_kinds"] = links
        row["content_kind_ids"] = [link["content_kind_id"] for link in links]
        default = next((link["content_kind_id"] for link in links if int(link.get("is_default") or 0)), "")
        row["default_content_kind_id"] = default
    return rows


def _pattern_payload(values, conn):
    name = _require_name(values)
    code = validate_code(values.get("pattern_code") or code_from_name(name), "Pattern code")
    content_kind_id = _int_or_none(values.get("content_kind_id"))
    if not content_kind_id:
        raise ValueError("Content kind is required.")
    return (
        code,
        content_kind_id,
        name,
        _clean_optional(values.get("description")),
        _clean_optional(values.get("default_area_id")),
        _int_or_none(values.get("default_template_id")),
        _int_or_none(values.get("default_view_id")),
        validate_json_text(values.get("creation_config"), "Creation config"),
        validate_json_text(values.get("view_filter_config"), "View filter config"),
        _bool_int(values.get("is_active", 1)),
        _int_value(values.get("sort_order"), 0),
        _clean_optional(values.get("notes")),
    )


def create_content_pattern(values, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    now = _utc_now()
    payload = _pattern_payload(values, conn)
    with conn:
        cur = conn.execute(
            "INSERT INTO lp_content_pattern "
            "(pattern_code, content_kind_id, name, description, default_area_id, default_template_id, default_view_id, "
            "creation_config, view_filter_config, is_active, sort_order, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            payload + (now, now),
        )
    return cur.lastrowid


def update_content_pattern(content_pattern_id, values, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    payload = _pattern_payload(values, conn)
    with conn:
        conn.execute(
            "UPDATE lp_content_pattern SET pattern_code = ?, content_kind_id = ?, name = ?, description = ?, "
            "default_area_id = ?, default_template_id = ?, default_view_id = ?, creation_config = ?, view_filter_config = ?, "
            "is_active = ?, sort_order = ?, notes = ?, updated_at = ? WHERE content_pattern_id = ?",
            payload + (_utc_now(), int(content_pattern_id)),
        )
    return True


def deactivate_content_pattern(content_pattern_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    with conn:
        conn.execute("UPDATE lp_content_pattern SET is_active = 0, updated_at = ? WHERE content_pattern_id = ?", (_utc_now(), int(content_pattern_id)))


def remove_content_pattern(content_pattern_id, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    with conn:
        conn.execute("DELETE FROM lp_content_pattern WHERE content_pattern_id = ?", (int(content_pattern_id),))
    return {"removed": True, "deactivated": False}


def list_content_patterns(conn=None, include_inactive=False):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    where = "" if include_inactive else "WHERE p.is_active = 1"
    label_map = _area_label_map(conn)
    rows = conn.execute(
        "SELECT p.*, ck.content_kind_id, ck.name AS content_kind_name, t.template_code, t.name AS template_name, "
        "v.view_code, v.name AS view_name "
        "FROM lp_content_pattern p "
        "JOIN lp_content_kind ck ON ck.content_kind_id = p.content_kind_id "
        "LEFT JOIN lp_template t ON t.template_id = p.default_template_id "
        "LEFT JOIN lp_content_view v ON v.content_view_id = p.default_view_id "
        f"{where} ORDER BY p.sort_order, lower(p.name), p.content_pattern_id"
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["default_area_name"] = label_map.get(item.get("default_area_id"), item.get("default_area_id"))
        result.append(item)
    return result


def catalog_summary(conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    total = conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind").fetchone()["cnt"]
    complete = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_content_kind WHERE COALESCE(TRIM(area_id), '') != '' AND COALESCE(TRIM(tab_code), '') != ''"
    ).fetchone()["cnt"]
    missing_area = conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind WHERE COALESCE(TRIM(area_id), '') = ''").fetchone()["cnt"]
    missing_tab = conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind WHERE COALESCE(TRIM(tab_code), '') = ''").fetchone()["cnt"]
    missing_both = conn.execute(
        "SELECT COUNT(1) AS cnt FROM lp_content_kind WHERE COALESCE(TRIM(area_id), '') = '' AND COALESCE(TRIM(tab_code), '') = ''"
    ).fetchone()["cnt"]
    return {
        "total": total,
        "complete": complete,
        "missing_area": missing_area,
        "missing_tab": missing_tab,
        "missing_both": missing_both,
    }


def _catalog_filter_where(filters=None, alias="ck"):
    filters = filters or {}
    where = []
    params = []
    tab_filter = filters.get("tab_code") or filters.get("canonical_tab_code")
    if tab_filter:
        if tab_filter == NO_TAB_CODE:
            where.append(f"COALESCE({alias}.tab_code, '') = ''")
        else:
            where.append(f"{alias}.tab_code = ?")
            params.append(tab_filter)
    if filters.get("area_id"):
        if filters.get("area_id") == UNASSIGNED_AREA_ID:
            where.append(f"COALESCE({alias}.area_id, '') = ''")
        else:
            where.append(f"{alias}.area_id = ?")
            params.append(filters.get("area_id"))
    if filters.get("q"):
        q = f"%{_clean_text(filters.get('q'))}%"
        where.append(f"({alias}.name LIKE ? OR COALESCE({alias}.comment,'') LIKE ?)")
        params.extend([q, q])
    return where, params


def _visible_matrix_areas(conn, include_inactive_areas=False):
    # Keep the matrix aligned with the normal sidebar. This excludes stale rows for
    # other owners and legacy areas that are not part of the active navigation.
    sidebar_rows = areas_mod.areas_side_tabs(conn=conn, seed=False)
    rows = []
    seen = set()
    for row in sidebar_rows:
        area_id = _clean_text(row.get("area") or row.get("id") or row.get("area_id"))
        if not area_id or area_id.lower() in {"any", "all", "all areas", "spacer", "unmapped"}:
            continue
        if int(row.get("is_header") or 0) or int(row.get("is_system") or 0):
            continue
        if area_id in seen:
            continue
        seen.add(area_id)
        rows.append(
            {
                "area_id": area_id,
                "label": row.get("label") or row.get("area_name") or area_id,
            }
        )
    if include_inactive_areas:
        db_rows = conn.execute(
            "SELECT area_id, COALESCE(NULLIF(area_name, ''), area_id) AS area_name "
            "FROM lp_areas WHERE is_header = 0 AND is_system = 0 GROUP BY area_id ORDER BY lower(area_name), lower(area_id)"
        ).fetchall()
        for row in db_rows:
            if row["area_id"] not in seen:
                seen.add(row["area_id"])
                rows.append({"area_id": row["area_id"], "label": row["area_name"]})
    return rows


def _area_label_map(conn, visible_areas=None):
    labels = {UNASSIGNED_AREA_ID: "Unassigned"}
    for row in visible_areas if visible_areas is not None else _visible_matrix_areas(conn):
        labels[row["area_id"]] = row["label"]
    try:
        rows = conn.execute(
            "SELECT area_id, COALESCE(NULLIF(area_name, ''), area_id) AS area_name "
            "FROM lp_areas WHERE is_header = 0 GROUP BY area_id"
        ).fetchall()
    except Exception:
        rows = []
    for row in rows:
        labels.setdefault(row["area_id"], row["area_name"])
    return labels


def content_catalog_matrix(filters=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    filters = filters or {}
    where, params = _catalog_filter_where(filters, "ck")
    visible_areas = _visible_matrix_areas(conn, include_inactive_areas=_truthy(filters.get("include_inactive_areas")))
    visible_area_ids = [row["area_id"] for row in visible_areas]
    area_join_condition = ""
    area_join_params = []
    if visible_area_ids:
        area_join_condition = "AND cka.area_id IN (" + ",".join(["?"] * len(visible_area_ids)) + ")"
        area_join_params = visible_area_ids
    where_sql = "WHERE " + " AND ".join(where) if where else ""
    tab_order = TAB_CODES + [NO_TAB_CODE]
    tab_labels = {code: _tab_label(code) for code in TAB_CODES}
    tab_labels[NO_TAB_CODE] = "No Tab"
    sql = f"""
        SELECT
            COALESCE(NULLIF(ck.area_id, ''), ?) AS area_id,
            COALESCE(NULLIF(ck.tab_code, ''), ?) AS tab_code,
            COUNT(1) AS total_count
        FROM lp_content_kind ck
        {where_sql}
        GROUP BY area_id, tab_code
    """
    rows = conn.execute(sql, [UNASSIGNED_AREA_ID, NO_TAB_CODE] + params).fetchall()
    label_map = _area_label_map(conn, visible_areas)
    area_ids = [row["area_id"] for row in visible_areas]
    if UNASSIGNED_AREA_ID not in area_ids:
        area_ids.append(UNASSIGNED_AREA_ID)
    for row in rows:
        if row["area_id"] not in area_ids:
            area_ids.append(row["area_id"])
    cells = {}
    row_totals = {area_id: 0 for area_id in area_ids}
    column_totals = {tab_code: 0 for tab_code in tab_order}
    matrix_placements = 0
    assigned_area_mappings = 0
    unassigned_kind_placements = 0
    for row in rows:
        area_id = row["area_id"]
        tab_code = row["tab_code"]
        total_count = int(row["total_count"] or 0)
        cell = {
            "area_id": area_id,
            "tab_code": tab_code,
            "total": total_count,
            "items": _cell_item_names(conn, area_id, tab_code, filters),
        }
        cells[f"{area_id}|{tab_code}"] = cell
        row_totals[area_id] = row_totals.get(area_id, 0) + cell["total"]
        column_totals[tab_code] = column_totals.get(tab_code, 0) + cell["total"]
        matrix_placements += cell["total"]
        if area_id == UNASSIGNED_AREA_ID:
            unassigned_kind_placements += total_count
        else:
            assigned_area_mappings += total_count
    unique_sql = f"SELECT COUNT(1) AS cnt FROM lp_content_kind ck {where_sql}"
    unique_total = conn.execute(unique_sql, params).fetchone()["cnt"]
    return {
        "tabs": [{"code": code, "label": tab_labels.get(code, code), "total": column_totals.get(code, 0)} for code in tab_order],
        "areas": [{"area_id": area_id, "label": label_map.get(area_id, area_id), "total": row_totals.get(area_id, 0)} for area_id in area_ids],
        "cells": cells,
        "totals": {
            "unique_kinds": unique_total,
            "area_tab_mappings": assigned_area_mappings,
            "assigned_area_mappings": assigned_area_mappings,
            "unassigned_kind_placements": unassigned_kind_placements,
            "matrix_placements": matrix_placements,
            "columns": column_totals,
            "rows": row_totals,
        },
    }


def _template_view_maps(conn):
    template_rows = conn.execute(
        "SELECT ckt.content_kind_id, ckt.is_default, t.template_code, t.name "
        "FROM lp_content_kind_template ckt JOIN lp_template t ON t.template_id = ckt.template_id "
        "ORDER BY ckt.is_default DESC, ckt.sort_order, lower(t.name)"
    ).fetchall()
    view_rows = conn.execute(
        "SELECT ckv.content_kind_id, ckv.is_default, v.view_code, v.name "
        "FROM lp_content_kind_view ckv JOIN lp_content_view v ON v.content_view_id = ckv.content_view_id "
        "ORDER BY ckv.is_default DESC, ckv.sort_order, lower(v.name)"
    ).fetchall()
    templates = {}
    views = {}
    for row in template_rows:
        item = {"code": row["template_code"], "name": row["name"], "is_default": int(row["is_default"] or 0)}
        templates.setdefault(row["content_kind_id"], []).append(item)
    for row in view_rows:
        item = {"code": row["view_code"], "name": row["name"], "is_default": int(row["is_default"] or 0)}
        views.setdefault(row["content_kind_id"], []).append(item)
    return templates, views


def detailed_content_kinds(filters=None, conn=None):
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    filters = filters or {}
    visible_areas = _visible_matrix_areas(conn, include_inactive_areas=_truthy(filters.get("include_inactive_areas")))
    visible_area_ids = [row["area_id"] for row in visible_areas]
    rows = list_content_kinds(conn=conn, filters=filters, include_inactive=True, visible_area_ids=visible_area_ids)
    templates, views = _template_view_maps(conn)
    result = []
    for row in rows:
        item = dict(row)
        item["templates"] = templates.get(row["content_kind_id"], [])
        item["views"] = views.get(row["content_kind_id"], [])
        item["default_template"] = next((t for t in item["templates"] if t["is_default"]), None)
        item["default_view"] = next((v for v in item["views"] if v["is_default"]), None)
        result.append(item)
    return result


def _table_exists(conn, table_name):
    if not table_name:
        return True
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def content_catalog_cell_details(area_id, tab_code, filters=None, conn=None):
    filters = dict(filters or {})
    filters["area_id"] = area_id or UNASSIGNED_AREA_ID
    filters["tab_code"] = tab_code or NO_TAB_CODE
    return detailed_content_kinds(filters=filters, conn=conn)


def content_catalog_report(group="by-tab", filters=None, conn=None):
    conn = _get_conn(conn)
    rows = detailed_content_kinds(filters=filters, conn=conn)
    group = (group or "by-tab").strip().lower()
    if group == "by-area":
        sections = {}
        for row in rows:
            areas = row.get("areas") or [{"area_id": UNASSIGNED_AREA_ID, "area_name": "Unassigned"}]
            for area in areas:
                area_label = area.get("area_name") or area.get("area_id") or "Unassigned"
                tab_label = _tab_label(row.get("tab_code")) if row.get("tab_code") else "No Tab"
                area_section = sections.setdefault(area_label, {})
                area_section.setdefault(tab_label, []).append(row)
        return {"group": group, "sections": [{"label": label, "tabs": [{"label": tab, "items": items} for tab, items in sorted(tabs.items())]} for label, tabs in sorted(sections.items())]}
    sections = {}
    for row in rows:
        tab_label = _tab_label(row.get("tab_code")) if row.get("tab_code") else "No Tab"
        area_label = row.get("area_name") or row.get("area_id") or "Unassigned"
        sections.setdefault(tab_label, {}).setdefault(area_label, []).append(row)
    return {
        "group": "by-tab",
        "sections": [
            {"label": tab, "areas": [{"label": area, "items": items} for area, items in sorted(areas.items())]}
            for tab, areas in sorted(sections.items())
        ],
    }


def _tab_label(tab_code):
    if tab_code == "GOALS":
        return "Goals / Tasks"
    return tab_code or ""


def _cell_item_names(conn, area_id, tab_code, filters=None):
    filters = dict(filters or {})
    filters["area_id"] = area_id
    filters["tab_code"] = tab_code
    rows = list_content_kinds(conn=conn, filters=filters)
    return [row["name"] for row in rows[:5]]


ROOT_TABLES = {
    "NOTE": "lp_notes",
    "TASK": "lp_tasks",
    "PROJECT": "lp_project_workspaces",
    "LIST": "lp_project_workspaces",
    "EVENT": "lp_calendar_events",
    "HOWTO": "lp_howto",
    "PERSON": "lp_contacts",
    "PLACE": "lp_places",
    "FILE": "lp_files",
    "DATA_ITEM": "lp_data_objects",
    "APP_ITEM": "lp_apps",
    "MEDIA_ITEM": "lp_media",
    "AUDIO_ITEM": "lp_audio",
}


SAMPLE_CONTENT_KINDS = [
    ("NOTE", "Note", None, "NOTE", "NOTES", None, "CREATED", "CONFIRMED"),
    ("TASK", "Task", None, "TASK", "GOALS", None, "DUE", "CONFIRMED"),
    ("PROJECT", "Project", None, "PROJECT", "GOALS", None, "START_END", "CONFIRMED"),
    ("LIST", "List", None, "LIST", "GOALS", None, "CREATED", "CONFIRMED"),
    ("EVENT", "Event", None, "EVENT", "CALENDAR", None, "START_END", "CONFIRMED"),
    ("HOWTO", "How-to", None, "HOWTO", "HOW", None, "CREATED", "CONFIRMED"),
    ("PERSON", "Person", None, "PERSON", "PEOPLE", None, "CREATED", "CONFIRMED"),
    ("PLACE", "Place", None, "PLACE", "PLACES", None, "CREATED", "CONFIRMED"),
    ("OBJECT", "Object", None, "OBJECT", "3D", None, "CREATED", "NEEDS_OBJECT"),
    ("FILE", "File", None, "FILE", "FILES", None, "CREATED", "CONFIRMED"),
    ("DATA_ITEM", "Data Item", None, "DATA", "DATA", None, "CREATED", "CONFIRMED"),
    ("MONEY_ITEM", "Money Item", None, "MONEY", "MONEY", None, "CREATED", "UNDECIDED"),
    ("APP_ITEM", "Application Item", None, "APP", "APPS", None, "CREATED", "CONFIRMED"),
    ("MEDIA_ITEM", "Media Item", None, "MEDIA", "MEDIA", None, "CREATED", "CONFIRMED"),
    ("AUDIO_ITEM", "Audio Item", None, "AUDIO", "AUDIO", None, "CREATED", "CONFIRMED"),
    ("LOG_ENTRY", "Log Entry", None, "LOG", "DATA", None, "MEASUREMENT", "NEEDS_OBJECT"),
    ("COLLECTION", "Collection", None, "COLLECTION", None, None, "CREATED", "CONFIRMED"),
    ("IDEA", "Idea", "NOTE", "NOTE", "NOTES", "IDEA", "CREATED", "CONFIRMED"),
    ("JOURNAL_ENTRY", "Journal Entry", "NOTE", "NOTE", "NOTES", "JOURNAL", "OCCURRED", "NEEDS_VIEW"),
    ("MEETING_NOTE", "Meeting Note", "NOTE", "NOTE", "NOTES", "MEETING", "OCCURRED", "NEEDS_TEMPLATE"),
    ("DECISION_NOTE", "Decision", "NOTE", "NOTE", "NOTES", "DECISION", "OCCURRED", "NEEDS_TEMPLATE"),
    ("RESEARCH_NOTE", "Research Note", "NOTE", "NOTE", "NOTES", "RESEARCH", "CREATED", "NEEDS_TEMPLATE"),
    ("CODE_REVIEW_NOTE", "Code Review", "NOTE", "NOTE", "NOTES", "CODE_REVIEW", "OCCURRED", "NEEDS_TEMPLATE"),
    ("BOOK_NOTE", "Book Note", "NOTE", "NOTE", "NOTES", "BOOK", "CREATED", "NEEDS_TEMPLATE"),
    ("PERSON_NOTE", "Person Note", "NOTE", "NOTE", "NOTES", "PERSON", "OCCURRED", "CONFIRMED"),
    ("ANNUAL_REVIEW", "Annual Review", "NOTE", "NOTE", "NOTES", "REVIEW", "OCCURRED", "NEEDS_TEMPLATE"),
    ("TECHNICAL_DESIGN", "Technical Design Note", "NOTE", "NOTE", "NOTES", "TECHNICAL_DESIGN", "CREATED", "NEEDS_TEMPLATE"),
    ("REPAIR_PROJECT", "Repair Project", "PROJECT", "PROJECT", "GOALS", "REPAIR", "START_END", "NEEDS_TEMPLATE"),
    ("RENOVATION_PROJECT", "Renovation Project", "PROJECT", "PROJECT", "GOALS", "RENOVATION", "START_END", "NEEDS_TEMPLATE"),
    ("SOFTWARE_PROJECT", "Software Project", "PROJECT", "PROJECT", "GOALS", "SOFTWARE", "START_END", "NEEDS_TEMPLATE"),
    ("TRAVEL_PROJECT", "Travel Project", "PROJECT", "PROJECT", "GOALS", "TRAVEL", "START_END", "NEEDS_TEMPLATE"),
    ("PURCHASE_PROJECT", "Major Purchase Project", "PROJECT", "PROJECT", "GOALS", "PURCHASE", "START_END", "NEEDS_TEMPLATE"),
    ("ADMIN_PROJECT", "Administration Project", "PROJECT", "PROJECT", "GOALS", "ADMIN", "START_END", "NEEDS_TEMPLATE"),
    ("ERRAND_TASK", "Errand", "TASK", "TASK", "GOALS", "ERRAND", "DUE", "CONFIRMED"),
    ("FOLLOW_UP_TASK", "Follow-up", "TASK", "TASK", "GOALS", "FOLLOW_UP", "DUE", "CONFIRMED"),
    ("MAINTENANCE_TASK", "Maintenance Task", "TASK", "TASK", "GOALS", "MAINTENANCE", "DUE", "CONFIRMED"),
    ("SHOPPING_LIST", "Shopping List", "LIST", "LIST", "GOALS", "SHOPPING", "CREATED", "CONFIRMED"),
    ("PACKING_LIST", "Packing List", "LIST", "LIST", "GOALS", "PACKING", "CREATED", "NEEDS_TEMPLATE"),
    ("CHECKLIST", "Checklist", "LIST", "LIST", "GOALS", "CHECKLIST", "CREATED", "CONFIRMED"),
    ("WATCHLIST", "Watchlist", "LIST", "LIST", "GOALS", "WATCHLIST", "CREATED", "CONFIRMED"),
    ("QUESTIONS_LIST", "Questions List", "LIST", "LIST", "GOALS", "QUESTIONS", "CREATED", "CONFIRMED"),
    ("APPOINTMENT", "Appointment", "EVENT", "EVENT", "CALENDAR", "APPOINTMENT", "START_END", "CONFIRMED"),
    ("MEETING", "Meeting", "EVENT", "EVENT", "CALENDAR", "MEETING", "START_END", "CONFIRMED"),
    ("BIRTHDAY", "Birthday", "EVENT", "EVENT", "CALENDAR", "BIRTHDAY", "RECURRING", "NEEDS_VIEW"),
    ("ANNIVERSARY", "Anniversary", "EVENT", "EVENT", "CALENDAR", "ANNIVERSARY", "RECURRING", "NEEDS_VIEW"),
    ("PUBLIC_HOLIDAY", "Public Holiday", "EVENT", "EVENT", "CALENDAR", "HOLIDAY", "RECURRING", "CONFIRMED"),
    ("DEADLINE", "Deadline", "EVENT", "EVENT", "CALENDAR", "DEADLINE", "DUE", "CONFIRMED"),
    ("PAYDAY", "Payday", "EVENT", "EVENT", "CALENDAR", "PAYDAY", "RECURRING", "CONFIRMED"),
    ("BILL_DUE_DATE", "Bill Due Date", "EVENT", "EVENT", "CALENDAR", "BILL_DUE", "RECURRING", "CONFIRMED"),
    ("WARRANTY_EXPIRY", "Warranty Expiry", "EVENT", "EVENT", "CALENDAR", "WARRANTY", "DUE", "NEEDS_VIEW"),
    ("MEDICAL_APPOINTMENT", "Medical Appointment", "EVENT", "EVENT", "CALENDAR", "MEDICAL", "START_END", "CONFIRMED"),
    ("TRAVEL_BOOKING", "Travel Booking", "EVENT", "EVENT", "CALENDAR", "TRAVEL", "START_END", "CONFIRMED"),
]

SAMPLE_CONTENT_KINDS.extend(
    [
        (code, name, parent, obj, tab, subtype, "CREATED", status)
        for code, name, parent, obj, tab, subtype, status in [
            ("RECIPE", "Recipe", "HOWTO", "HOWTO", "HOW", "RECIPE", "CONFIRMED"),
            ("REPAIR_GUIDE", "Repair Guide", "HOWTO", "HOWTO", "HOW", "REPAIR", "CONFIRMED"),
            ("SOFTWARE_RUNBOOK", "Software Runbook", "HOWTO", "HOWTO", "HOW", "SOFTWARE", "CONFIRMED"),
            ("BACKUP_PROCEDURE", "Backup Procedure", "HOWTO", "HOWTO", "HOW", "BACKUP", "CONFIRMED"),
            ("RESTORE_PROCEDURE", "Restore Procedure", "HOWTO", "HOWTO", "HOW", "RESTORE", "CONFIRMED"),
            ("DEPLOYMENT_PROCEDURE", "Deployment Procedure", "HOWTO", "HOWTO", "HOW", "DEPLOYMENT", "CONFIRMED"),
            ("EMERGENCY_PROCEDURE", "Emergency Procedure", "HOWTO", "HOWTO", "HOW", "EMERGENCY", "CONFIRMED"),
            ("CLEANING_PROCEDURE", "Cleaning Procedure", "HOWTO", "HOWTO", "HOW", "CLEANING", "CONFIRMED"),
            ("FAMILY_MEMBER", "Family Member", "PERSON", "PERSON", "PEOPLE", "FAMILY", "CONFIRMED"),
            ("FRIEND", "Friend", "PERSON", "PERSON", "PEOPLE", "FRIEND", "CONFIRMED"),
            ("PROFESSIONAL_CONTACT", "Professional Contact", "PERSON", "PERSON", "PEOPLE", "PROFESSIONAL", "CONFIRMED"),
            ("MEDICAL_CONTACT", "Medical Contact", "PERSON", "PERSON", "PEOPLE", "MEDICAL", "CONFIRMED"),
            ("TRADESPERSON", "Tradesperson", "PERSON", "PERSON", "PEOPLE", "TRADESPERSON", "CONFIRMED"),
            ("ORGANISATION", "Organisation", "PERSON", "PERSON", "PEOPLE", "ORGANISATION", "CONFIRMED"),
            ("EMERGENCY_CONTACT", "Emergency Contact", "PERSON", "PERSON", "PEOPLE", "EMERGENCY", "CONFIRMED"),
            ("EARTH_PLACE", "Earth Place", "PLACE", "PLACE", "PLACES", "EARTH", "CONFIRMED"),
            ("FICTIONAL_PLACE", "Fictional Place", "PLACE", "PLACE", "PLACES", "FICTIONAL", "CONFIRMED"),
            ("GAME_WORLD_PLACE", "Game World Place", "PLACE", "PLACE", "PLACES", "GAME_WORLD", "CONFIRMED"),
            ("HOME_LOCATION", "Home Location", "PLACE", "PLACE", "PLACES", "HOME", "CONFIRMED"),
            ("BUSINESS_LOCATION", "Business Location", "PLACE", "PLACE", "PLACES", "BUSINESS", "CONFIRMED"),
            ("TRAVEL_DESTINATION", "Travel Destination", "PLACE", "PLACE", "PLACES", "TRAVEL", "CONFIRMED"),
            ("ROUTE", "Route", "PLACE", "PLACE", "PLACES", "ROUTE", "NEEDS_VIEW"),
            ("PHYSICAL_ASSET", "Physical Asset", "OBJECT", "OBJECT", "3D", "PHYSICAL", "NEEDS_OBJECT"),
            ("FURNITURE", "Furniture", "PHYSICAL_ASSET", "OBJECT", "3D", "FURNITURE", "NEEDS_OBJECT"),
            ("APPLIANCE", "Appliance", "PHYSICAL_ASSET", "OBJECT", "3D", "APPLIANCE", "NEEDS_OBJECT"),
            ("VEHICLE", "Vehicle", "PHYSICAL_ASSET", "OBJECT", "3D", "VEHICLE", "NEEDS_OBJECT"),
            ("DEVICE", "Device", "PHYSICAL_ASSET", "OBJECT", "3D", "DEVICE", "NEEDS_OBJECT"),
            ("TOOL", "Tool", "PHYSICAL_ASSET", "OBJECT", "3D", "TOOL", "NEEDS_OBJECT"),
            ("BLENDER_MODEL", "Blender Model", "OBJECT", "OBJECT", "3D", "BLENDER_MODEL", "CONFIRMED"),
            ("UE_OBJECT", "Unreal Engine Object", "OBJECT", "OBJECT", "3D", "UE_OBJECT", "CONFIRMED"),
            ("THREE_D_SCENE", "3D Scene", "OBJECT", "OBJECT", "3D", "SCENE", "CONFIRMED"),
            ("GAME_OBJECT", "Game Object", "OBJECT", "OBJECT", "3D", "GAME_OBJECT", "CONFIRMED"),
            ("FICTIONAL_OBJECT", "Fictional Object", "OBJECT", "OBJECT", "3D", "FICTIONAL", "CONFIRMED"),
            ("OBJECT_COMPONENT", "Object Component", "OBJECT", "OBJECT", "3D", "COMPONENT", "NEEDS_OBJECT"),
            ("DESIGN_CONCEPT", "Design Concept", "OBJECT", "OBJECT", "3D", "CONCEPT", "CONFIRMED"),
            ("THREE_D_SCAN", "3D Scan", "OBJECT", "OBJECT", "3D", "SCAN", "CONFIRMED"),
            ("DOCUMENT_FILE", "Document", "FILE", "FILE", "FILES", "DOCUMENT", "CONFIRMED"),
            ("RECEIPT_FILE", "Receipt", "FILE", "FILE", "FILES", "RECEIPT", "CONFIRMED"),
            ("MANUAL_FILE", "Manual", "FILE", "FILE", "FILES", "MANUAL", "CONFIRMED"),
            ("WARRANTY_FILE", "Warranty Document", "FILE", "FILE", "FILES", "WARRANTY", "CONFIRMED"),
            ("CONTRACT_FILE", "Contract", "FILE", "FILE", "FILES", "CONTRACT", "CONFIRMED"),
            ("CERTIFICATE_FILE", "Certificate", "FILE", "FILE", "FILES", "CERTIFICATE", "CONFIRMED"),
            ("SOURCE_CODE_FILE", "Source Code File", "FILE", "FILE", "FILES", "SOURCE_CODE", "CONFIRMED"),
            ("ARCHIVE_FILE", "Archive File", "FILE", "FILE", "FILES", "ARCHIVE", "CONFIRMED"),
            ("DATASET", "Dataset", "DATA_ITEM", "DATA", "DATA", "DATASET", "CONFIRMED"),
            ("DATABASE", "Database", "DATA_ITEM", "DATA", "DATA", "DATABASE", "CONFIRMED"),
            ("TABLE_DEFINITION", "Table Definition", "DATA_ITEM", "DATA", "DATA", "TABLE", "CONFIRMED"),
            ("SAVED_QUERY", "Saved Query", "DATA_ITEM", "DATA", "DATA", "QUERY", "CONFIRMED"),
            ("MEASUREMENT_LOG", "Measurement Log", "LOG_ENTRY", "LOG", "DATA", "MEASUREMENT", "NEEDS_OBJECT"),
            ("ACTIVITY_LOG", "Activity Log", "LOG_ENTRY", "LOG", "DATA", "ACTIVITY", "NEEDS_OBJECT"),
            ("IMPORT_DEFINITION", "Import Definition", "DATA_ITEM", "DATA", "DATA", "IMPORT", "CONFIRMED"),
            ("ACCOUNT", "Financial Account", "MONEY_ITEM", "MONEY", "MONEY", "ACCOUNT", "NEEDS_OBJECT"),
            ("BUDGET", "Budget", "MONEY_ITEM", "MONEY", "MONEY", "BUDGET", "NEEDS_OBJECT"),
            ("TRANSACTION", "Transaction", "MONEY_ITEM", "MONEY", "MONEY", "TRANSACTION", "NEEDS_OBJECT"),
            ("BILL", "Bill", "MONEY_ITEM", "MONEY", "MONEY", "BILL", "NEEDS_OBJECT"),
            ("SUBSCRIPTION", "Subscription", "MONEY_ITEM", "MONEY", "MONEY", "SUBSCRIPTION", "NEEDS_OBJECT"),
            ("INSURANCE_POLICY", "Insurance Policy", "MONEY_ITEM", "MONEY", "MONEY", "INSURANCE", "NEEDS_OBJECT"),
            ("FINANCIAL_FORECAST", "Financial Forecast", "MONEY_ITEM", "MONEY", "MONEY", "FORECAST", "NEEDS_VIEW"),
            ("DESKTOP_APPLICATION", "Desktop Application", "APP_ITEM", "APP", "APPS", "DESKTOP", "CONFIRMED"),
            ("MOBILE_APPLICATION", "Mobile Application", "APP_ITEM", "APP", "APPS", "MOBILE", "CONFIRMED"),
            ("WEB_APPLICATION", "Web Application", "APP_ITEM", "APP", "APPS", "WEB", "CONFIRMED"),
            ("COMMAND_LINE_TOOL", "Command-line Tool", "APP_ITEM", "APP", "APPS", "CLI", "CONFIRMED"),
            ("ONLINE_SERVICE", "Online Service", "APP_ITEM", "APP", "APPS", "SERVICE", "CONFIRMED"),
            ("SOFTWARE_LICENSE", "Software Licence", "APP_ITEM", "APP", "APPS", "LICENCE", "CONFIRMED"),
            ("PHOTO", "Photo", "MEDIA_ITEM", "MEDIA", "MEDIA", "PHOTO", "CONFIRMED"),
            ("VIDEO", "Video", "MEDIA_ITEM", "MEDIA", "MEDIA", "VIDEO", "CONFIRMED"),
            ("SCREENSHOT", "Screenshot", "MEDIA_ITEM", "MEDIA", "MEDIA", "SCREENSHOT", "CONFIRMED"),
            ("ALBUM", "Album", "COLLECTION", "COLLECTION", "MEDIA", "ALBUM", "CONFIRMED"),
            ("MEDIA_EVENT", "Media Event", "MEDIA_ITEM", "MEDIA", "MEDIA", "EVENT", "CONFIRMED"),
            ("MUSIC_TRACK", "Music Track", "AUDIO_ITEM", "AUDIO", "AUDIO", "MUSIC", "CONFIRMED"),
            ("PODCAST_EPISODE", "Podcast Episode", "AUDIO_ITEM", "AUDIO", "AUDIO", "PODCAST", "CONFIRMED"),
            ("AUDIO_RECORDING", "Audio Recording", "AUDIO_ITEM", "AUDIO", "AUDIO", "RECORDING", "CONFIRMED"),
            ("PLAYLIST", "Playlist", "COLLECTION", "COLLECTION", "AUDIO", "PLAYLIST", "CONFIRMED"),
        ]
    ]
)

SAMPLE_TEMPLATES = [
    ("BLANK_NOTE", "Blank Note", "NOTE", "NOTE", "NOTES", "# {{title}}\n"),
    ("IDEA_NOTE", "Idea", "NOTE", "NOTE", "NOTES", "# {{title}}\n\n## Idea\n\n## Why it may be useful\n\n## Next step\n"),
    ("JOURNAL_ENTRY", "Journal Entry", "NOTE", "NOTE", "NOTES", "# {{date}}\n\n## What happened\n\n## Thoughts\n\n## Worth remembering\n"),
    ("MEETING_NOTE", "Meeting Note", "NOTE", "NOTE", "NOTES", "# {{title}}\n\n**Date:** {{date}}\n\n## Attendees\n\n## Discussion\n\n## Decisions\n\n## Actions\n"),
    ("DECISION_NOTE", "Decision", "NOTE", "NOTE", "NOTES", "# {{title}}\n\n## Decision\n\n## Context\n\n## Options considered\n\n## Reason\n\n## Consequences\n\n## Review date\n"),
    ("CODE_REVIEW_NOTE", "Code Review", "NOTE", "NOTE", "NOTES", "# Code Review - {{title}}\n\n## Purpose\n\n## Files or components reviewed\n\n## Findings\n\n## Bugs or risks\n\n## Suggested changes\n\n## Verification\n"),
    ("SMALL_HOME_REPAIR", "Small Home Repair", "PROJECT", "PROJECT", "GOALS", "# {{title}}\n\n## Problem\n\n## Desired result\n\n## Photos and measurements\n\n## Tools and parts\n\n## Tasks\n\n- [ ] Inspect the problem\n- [ ] Decide whether it is DIY or requires a tradesperson\n- [ ] Obtain tools or parts\n- [ ] Complete the repair\n- [ ] Test the result\n- [ ] Record cost and final notes\n"),
    ("CAR_REPAIR", "Car Repair", "PROJECT", "PROJECT", "GOALS", "# {{title}}\n\n## Vehicle\n\n## Problem or symptom\n\n## Diagnosis\n\n## Quotes\n\n## Parts\n\n## Tasks\n\n- [ ] Record symptoms\n- [ ] Take photos if useful\n- [ ] Obtain diagnosis\n- [ ] Approve or perform repair\n- [ ] Record cost\n- [ ] Record work completed\n- [ ] Add future maintenance date\n"),
    ("REPLACE_ENSUITE", "Replace Ensuite", "MULTI_OBJECT", "PROJECT", "GOALS", "# Replace Ensuite\n\n## Requirements\n\n## Measurements\n\n## Budget\n\n## Design decisions\n\n## Quotes and contractors\n\n## Fixtures and materials\n\n## Work stages\n\n- [ ] Finalise requirements\n- [ ] Measure existing room\n- [ ] Prepare budget\n- [ ] Obtain quotes\n- [ ] Select contractor\n- [ ] Select fixtures\n- [ ] Demolition\n- [ ] Plumbing\n- [ ] Electrical\n- [ ] Waterproofing\n- [ ] Tiling\n- [ ] Installation\n- [ ] Inspection\n- [ ] Record warranties and receipts\n- [ ] Take final photos\n"),
    ("SOFTWARE_CHANGE", "Software Change", "PROJECT", "PROJECT", "GOALS", "# {{title}}\n\n## Problem or goal\n\n## Current behaviour\n\n## Desired behaviour\n\n## Acceptance criteria\n\n## Design notes\n\n## Implementation tasks\n\n## Test plan\n\n## Documentation\n\n## Release and verification\n"),
    ("TRIP_PROJECT", "Trip", "MULTI_OBJECT", "PROJECT", "GOALS", "# {{destination}} - {{dates}}\n\n## Purpose\n\n## Dates\n\n## Budget\n\n## Bookings\n\n## Itinerary\n\n## Packing\n\n## Home preparation\n\n## Documents\n\n## Places to visit\n\n## Journal and photos\n\n## Lessons for next time\n"),
    ("FOOD_SHOPPING_LIST", "Food Shopping", "LIST", "LIST", "GOALS", "## Fruit and vegetables\n\n## Bread and bakery\n\n## Fridge\n\n## Freezer\n\n## Pantry\n\n## Household\n"),
    ("RECIPE", "Recipe", "HOWTO", "HOWTO", "HOW", "# {{title}}\n\n## Serves\n\n## Preparation time\n\n## Ingredients\n\n## Equipment\n\n## Steps\n\n## Notes and variations\n"),
    ("BACKUP_PROCEDURE", "Backup Procedure", "HOWTO", "HOWTO", "HOW", "# {{title}}\n\n## Purpose\n\n## Systems covered\n\n## Backup destination\n\n## Schedule\n\n## Steps\n\n## Verification\n\n## Restore test\n\n## Failure handling\n"),
]

SAMPLE_VIEWS = [
    ("RECENT_NOTES", "Recent Notes", "NOTES", "LIST", {"sort": "updated_at DESC"}),
    ("JOURNAL_TIMELINE", "Journal Timeline", "NOTES", "TIMELINE", {"date_field": "occurred_at", "sort": "occurred_at DESC", "group_by": "month"}),
    ("DECISION_REGISTER", "Decision Register", "NOTES", "TABLE", {"filter": {"subtype": "DECISION"}, "sort": "occurred_at DESC"}),
    ("ACTIVE_PROJECTS", "Active Projects", "GOALS", "BOARD", {"filter": {"status": "ACTIVE"}, "group_by": "area"}),
    ("ACTIVE_SHOPPING_LISTS", "Active Shopping Lists", "GOALS", "LIST", {"filter": {"subtype": "SHOPPING", "status": "ACTIVE"}}),
    ("BIRTHDAY_CALENDAR", "Birthday Calendar", "CALENDAR", "CALENDAR", {"filter": {"event_type": "BIRTHDAY"}, "calendar_mode": "YEAR"}),
    ("UPCOMING_EXPIRIES", "Upcoming Expiries", "CALENDAR", "LIST", {"filter": {"event_type": ["WARRANTY", "INSURANCE", "SUBSCRIPTION"]}, "sort": "event_date ASC"}),
    ("PEOPLE_DIRECTORY", "People Directory", "PEOPLE", "TABLE", {"sort": "name ASC"}),
    ("PLACES_MAP", "Places Map", "PLACES", "MAP", {"group_by": "source"}),
    ("PHYSICAL_ASSETS", "Physical Assets", "3D", "TABLE", {"filter": {"object_subtype": "PHYSICAL"}, "group_by": "area"}),
    ("THREE_D_MODELS", "3D Models", "3D", "GALLERY", {"filter": {"object_subtype": ["BLENDER_MODEL", "UE_OBJECT", "SCAN"]}}),
    ("DATASET_WORKSPACES", "Dataset Workspaces", "DATA", "TABLE", {"filter": {"subtype": "DATASET"}}),
    ("ACCOUNTS_AND_BUDGETS", "Accounts and Budgets", "MONEY", "DASHBOARD", {"include": ["ACCOUNT", "BUDGET"]}),
    ("APPLICATION_INVENTORY", "Application Inventory", "APPS", "TABLE", {"sort": "name ASC"}),
    ("MEDIA_TIMELINE", "Media Timeline", "MEDIA", "TIMELINE", {"date_field": "captured_at", "group_by": "month"}),
    ("AUDIO_PLAYLISTS", "Audio Playlists", "AUDIO", "LIST", {"filter": {"collection_type": "PLAYLIST"}}),
]

KIND_TEMPLATE_LINKS = [
    ("NOTE", "BLANK_NOTE", 1), ("IDEA", "IDEA_NOTE", 1), ("JOURNAL_ENTRY", "JOURNAL_ENTRY", 1),
    ("MEETING_NOTE", "MEETING_NOTE", 1), ("DECISION_NOTE", "DECISION_NOTE", 1), ("CODE_REVIEW_NOTE", "CODE_REVIEW_NOTE", 1),
    ("REPAIR_PROJECT", "SMALL_HOME_REPAIR", 1), ("REPAIR_PROJECT", "CAR_REPAIR", 0), ("RENOVATION_PROJECT", "REPLACE_ENSUITE", 1),
    ("SOFTWARE_PROJECT", "SOFTWARE_CHANGE", 1), ("TRAVEL_PROJECT", "TRIP_PROJECT", 1), ("SHOPPING_LIST", "FOOD_SHOPPING_LIST", 1),
    ("RECIPE", "RECIPE", 1), ("BACKUP_PROCEDURE", "BACKUP_PROCEDURE", 1),
]

KIND_VIEW_LINKS = [
    ("NOTE", "RECENT_NOTES", 1), ("JOURNAL_ENTRY", "JOURNAL_TIMELINE", 1), ("DECISION_NOTE", "DECISION_REGISTER", 1),
    ("PROJECT", "ACTIVE_PROJECTS", 1), ("SHOPPING_LIST", "ACTIVE_SHOPPING_LISTS", 1), ("BIRTHDAY", "BIRTHDAY_CALENDAR", 1),
    ("WARRANTY_EXPIRY", "UPCOMING_EXPIRIES", 1), ("PERSON", "PEOPLE_DIRECTORY", 1), ("PLACE", "PLACES_MAP", 1),
    ("PHYSICAL_ASSET", "PHYSICAL_ASSETS", 1), ("BLENDER_MODEL", "THREE_D_MODELS", 1), ("DATASET", "DATASET_WORKSPACES", 1),
    ("ACCOUNT", "ACCOUNTS_AND_BUDGETS", 1), ("BUDGET", "ACCOUNTS_AND_BUDGETS", 1), ("APP_ITEM", "APPLICATION_INVENTORY", 1),
    ("MEDIA_ITEM", "MEDIA_TIMELINE", 1), ("PLAYLIST", "AUDIO_PLAYLISTS", 1),
]

AREA_MAPPINGS = {
    "Personal": ["IDEA", "JOURNAL_ENTRY", "ANNUAL_REVIEW", "APPOINTMENT", "CHECKLIST", "DOCUMENT_FILE"],
    "Family": ["FAMILY_MEMBER", "BIRTHDAY", "ANNIVERSARY", "EMERGENCY_CONTACT", "PHOTO", "TRAVEL_PROJECT"],
    "Friends": ["FRIEND", "BIRTHDAY", "MEETING"],
    "House": ["REPAIR_PROJECT", "RENOVATION_PROJECT", "SHOPPING_LIST", "MAINTENANCE_TASK", "FURNITURE", "APPLIANCE", "TOOL", "REPAIR_GUIDE", "WARRANTY_FILE", "WARRANTY_EXPIRY"],
    "Food": ["SHOPPING_LIST", "RECIPE", "CHECKLIST", "APPLIANCE"],
    "Health": ["MEDICAL_APPOINTMENT", "MEDICAL_CONTACT", "MEASUREMENT_LOG", "JOURNAL_ENTRY", "QUESTIONS_LIST", "DOCUMENT_FILE"],
    "Vehicles": ["VEHICLE", "REPAIR_PROJECT", "MAINTENANCE_TASK", "RECEIPT_FILE", "WARRANTY_FILE", "APPOINTMENT"],
    "Travel": ["TRAVEL_PROJECT", "TRAVEL_DESTINATION", "TRAVEL_BOOKING", "PACKING_LIST", "PHOTO", "JOURNAL_ENTRY", "ROUTE"],
    "Work": ["MEETING_NOTE", "MEETING", "TASK", "PROJECT", "TECHNICAL_DESIGN", "PROFESSIONAL_CONTACT", "DATASET", "SAVED_QUERY"],
    "LifePIM": ["SOFTWARE_PROJECT", "CODE_REVIEW_NOTE", "TECHNICAL_DESIGN", "SOFTWARE_RUNBOOK", "DEPLOYMENT_PROCEDURE", "SOURCE_CODE_FILE", "DATABASE", "TABLE_DEFINITION", "MOBILE_APPLICATION", "DESKTOP_APPLICATION"],
    "Computers": ["DEVICE", "SOFTWARE_PROJECT", "BACKUP_PROCEDURE", "RESTORE_PROCEDURE", "SOFTWARE_RUNBOOK", "DESKTOP_APPLICATION", "COMMAND_LINE_TOOL", "SOFTWARE_LICENSE"],
    "Design": ["BLENDER_MODEL", "THREE_D_SCENE", "DESIGN_CONCEPT", "UE_OBJECT", "THREE_D_SCAN", "PHOTO", "SOURCE_CODE_FILE"],
    "Alrona": ["FICTIONAL_PLACE", "FICTIONAL_OBJECT", "GAME_OBJECT", "THREE_D_SCENE", "DESIGN_CONCEPT"],
    "Warcraft": ["GAME_WORLD_PLACE", "GAME_OBJECT", "FICTIONAL_OBJECT", "SCREENSHOT", "ROUTE"],
    "Finance": ["ACCOUNT", "BUDGET", "TRANSACTION", "BILL", "SUBSCRIPTION", "INSURANCE_POLICY", "FINANCIAL_FORECAST", "DOCUMENT_FILE"],
    "Garden": ["REPAIR_PROJECT", "MAINTENANCE_TASK", "PHOTO", "MEASUREMENT_LOG", "SHOPPING_LIST"],
}

SAMPLE_PATTERNS = [
    ("PERSONAL_DAILY_JOURNAL", "Personal Daily Journal", "JOURNAL_ENTRY", "Personal", "JOURNAL_ENTRY", "JOURNAL_TIMELINE"),
    ("WORK_MEETING", "Work Meeting", "MEETING_NOTE", "Work", "MEETING_NOTE", "RECENT_NOTES"),
    ("LIFEPIM_CODE_REVIEW", "LifePIM Code Review", "CODE_REVIEW_NOTE", "LifePIM", "CODE_REVIEW_NOTE", "RECENT_NOTES"),
    ("FOOD_SHOPPING", "Food Shopping", "SHOPPING_LIST", "Food", "FOOD_SHOPPING_LIST", "ACTIVE_SHOPPING_LISTS"),
    ("HOUSE_SHOPPING", "Household Shopping", "SHOPPING_LIST", "House", "FOOD_SHOPPING_LIST", "ACTIVE_SHOPPING_LISTS"),
    ("SMALL_HOUSE_REPAIR", "Small House Repair", "REPAIR_PROJECT", "House", "SMALL_HOME_REPAIR", "ACTIVE_PROJECTS"),
    ("CAR_REPAIR", "Car Repair", "REPAIR_PROJECT", "Vehicles", "CAR_REPAIR", "ACTIVE_PROJECTS"),
    ("REPLACE_ENSUITE", "Replace Ensuite", "RENOVATION_PROJECT", "House", "REPLACE_ENSUITE", "ACTIVE_PROJECTS"),
    ("LIFEPIM_SOFTWARE_CHANGE", "LifePIM Software Change", "SOFTWARE_PROJECT", "LifePIM", "SOFTWARE_CHANGE", "ACTIVE_PROJECTS"),
    ("HOLIDAY_TRIP", "Holiday Trip", "TRAVEL_PROJECT", "Travel", "TRIP_PROJECT", "ACTIVE_PROJECTS"),
    ("FAMILY_BIRTHDAY", "Family Birthday", "BIRTHDAY", "Family", None, "BIRTHDAY_CALENDAR"),
    ("FRIEND_BIRTHDAY", "Friend Birthday", "BIRTHDAY", "Friends", None, "BIRTHDAY_CALENDAR"),
    ("HOME_APPLIANCE", "Home Appliance", "APPLIANCE", "House", None, "PHYSICAL_ASSETS"),
    ("HOME_FURNITURE", "Home Furniture", "FURNITURE", "House", None, "PHYSICAL_ASSETS"),
    ("BLENDER_DESIGN_ASSET", "Blender Design Asset", "BLENDER_MODEL", "Design", None, "THREE_D_MODELS"),
    ("ALRONA_WORLD_OBJECT", "Alrona World Object", "FICTIONAL_OBJECT", "Alrona", None, "THREE_D_MODELS"),
    ("WARCRAFT_LOCATION", "Warcraft Location", "GAME_WORLD_PLACE", "Warcraft", None, "PLACES_MAP"),
    ("HEALTH_MEASUREMENT", "Health Measurement", "MEASUREMENT_LOG", "Health", None, None),
    ("MONTHLY_BUDGET", "Monthly Budget", "BUDGET", "Finance", None, "ACCOUNTS_AND_BUDGETS"),
    ("SOFTWARE_INVENTORY_ITEM", "Installed Software", "DESKTOP_APPLICATION", "Computers", None, "APPLICATION_INVENTORY"),
]


def seed_content_catalog(conn=None, force=False):
    # Retired with Content Catalog V2. Catalog items are now user-entered
    # planning rows, not a generated ontology.
    return
    conn = _get_conn(conn)
    ensure_content_catalog_schema(conn, seed=False)
    if not force and _sample_seed_version(conn) >= CONTENT_CATALOG_SAMPLE_SEED_VERSION:
        return
    now = _utc_now()
    with conn:
        for idx, (code, name, parent, object_type, tab, subtype, date_behaviour, status) in enumerate(SAMPLE_CONTENT_KINDS):
            if _kind_id_by_code(conn, code):
                continue
            parent_id = _kind_id_by_code(conn, parent)
            conn.execute(
                "INSERT INTO lp_content_kind "
                "(kind_code, parent_content_kind_id, name, object_type_code, canonical_tab_code, canonical_table_name, subtype_code, "
                "date_behaviour_code, mapping_status_code, is_active, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (code, parent_id, name, object_type, tab, ROOT_TABLES.get(code) or ROOT_TABLES.get(parent), subtype, date_behaviour, status, idx * 10, now, now),
            )
        for idx, (code, name, template_type, target_object, target_tab, content) in enumerate(SAMPLE_TEMPLATES):
            if _template_id_by_code(conn, code):
                continue
            conn.execute(
                "INSERT INTO lp_template "
                "(template_code, name, template_type_code, target_object_type, target_tab_code, template_content, is_active, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (code, name, template_type, target_object, target_tab, content, idx * 10, now, now),
            )
        for idx, (code, name, tab, view_type, config) in enumerate(SAMPLE_VIEWS):
            if _view_id_by_code(conn, code):
                continue
            conn.execute(
                "INSERT INTO lp_content_view "
                "(view_code, name, tab_code, view_type_code, view_config, is_active, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (code, name, tab, view_type, json.dumps(config, ensure_ascii=True, indent=2), idx * 10, now, now),
            )
        for kind_code, template_code, is_default in KIND_TEMPLATE_LINKS:
            kind_id = _kind_id_by_code(conn, kind_code)
            template_id = _template_id_by_code(conn, template_code)
            if not kind_id or not template_id:
                continue
            has_default = conn.execute(
                "SELECT 1 FROM lp_content_kind_template WHERE content_kind_id = ? AND is_default = 1",
                (kind_id,),
            ).fetchone()
            next_default = int(is_default and not has_default)
            conn.execute(
                "INSERT OR IGNORE INTO lp_content_kind_template "
                "(content_kind_id, template_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
                (kind_id, template_id, next_default, now, now),
            )
        for kind_code, view_code, is_default in KIND_VIEW_LINKS:
            kind_id = _kind_id_by_code(conn, kind_code)
            view_id = _view_id_by_code(conn, view_code)
            if not kind_id or not view_id:
                continue
            has_default = conn.execute(
                "SELECT 1 FROM lp_content_kind_view WHERE content_kind_id = ? AND is_default = 1",
                (kind_id,),
            ).fetchone()
            next_default = int(is_default and not has_default)
            conn.execute(
                "INSERT OR IGNORE INTO lp_content_kind_view "
                "(content_kind_id, content_view_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
                (kind_id, view_id, next_default, now, now),
            )
        for area_name, kind_codes in AREA_MAPPINGS.items():
            area_id = _area_id_by_name_or_id(conn, area_name)
            if not area_id:
                continue
            for kind_code in kind_codes:
                kind_id = _kind_id_by_code(conn, kind_code)
                if not kind_id:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO lp_content_kind_area "
                    "(content_kind_id, area_id, is_default, sort_order, created_at, updated_at) VALUES (?, ?, 0, 0, ?, ?)",
                    (kind_id, area_id, now, now),
                )
        for idx, (pattern_code, name, kind_code, area_name, template_code, view_code) in enumerate(SAMPLE_PATTERNS):
            row = conn.execute("SELECT content_pattern_id FROM lp_content_pattern WHERE pattern_code = ?", (pattern_code,)).fetchone()
            if row:
                continue
            kind_id = _kind_id_by_code(conn, kind_code)
            if not kind_id:
                continue
            conn.execute(
                "INSERT INTO lp_content_pattern "
                "(pattern_code, content_kind_id, name, default_area_id, default_template_id, default_view_id, is_active, sort_order, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (pattern_code, kind_id, name, _area_id_by_name_or_id(conn, area_name), _template_id_by_code(conn, template_code), _view_id_by_code(conn, view_code), idx * 10, now, now),
            )
        _set_sample_seed_version(conn)
