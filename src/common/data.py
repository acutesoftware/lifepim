#!/usr/bin/python3
# coding: utf-8
# data.py - common data access functions

from datetime import datetime
import os
import sqlite3
import sys

import etl_folder_mapping as folder_etl

from . import config as cfg
from . import if_sqlite as mod_sql

DB_FILE = os.getenv("LIFEPIM_DB_FILE") or getattr(cfg, "DB_FILE", getattr(cfg, "db_name", "lifepim.db"))
if not os.path.isabs(DB_FILE):
    DB_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), DB_FILE))


def _current_user():
    return os.getenv("USERNAME", "") or os.getenv("USER", "")


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _dbg(msg):
    print(f"[data] {msg}", file=sys.stderr, flush=True)



def _set_row_factory(db_conn):
    db_conn.row_factory = sqlite3.Row


def _get_conn():
    global conn
    if conn is None:
        _dbg(f"Opening sqlite connection to {DB_FILE}")
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        _set_row_factory(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            pass
        _dbg("SQLite connection ready")
    return conn


def _log_error(conn, message):
    try:
        mod_sql.lg(conn, mod_sql.LOG_ERROR, message)
    except Exception:
        pass


def get_data(conn, tbl_name, col_list, condition="1=1", params=None):
    """
    Fetch rows from a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param col_list: list of cols to retrieve
    :param condition: where clause, if None use 1=1
    :param params: query params
    """
    if not col_list:
        col_clause = "*"
    else:
        col_clause = ", ".join(col_list)
    if not condition:
        condition = "1=1"
    sql = f"SELECT {col_clause} FROM {tbl_name} WHERE {condition}"
    conn = _get_conn() if conn is None else conn
    _dbg(f"SELECT {tbl_name} WHERE {condition} params={params or []}")
    cur = conn.execute(sql, params or [])
    return cur.fetchall()


def add_column_if_missing(conn, tbl_name, col_name, col_type):
    conn = _get_conn() if conn is None else conn
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tbl_name,),
    ).fetchone()
    if not table_row:
        return
    rows = conn.execute(f"PRAGMA table_info({tbl_name})").fetchall()
    existing = {row[1].lower() for row in rows}
    if col_name.lower() in existing:
        return
    conn.execute(f"ALTER TABLE {tbl_name} ADD COLUMN {col_name} {col_type}")


def _quote_ident(identifier):
    return '"' + str(identifier).replace('"', '""') + '"'


def _table_column_names(conn, tbl_name):
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({_quote_ident(tbl_name)})").fetchall()]
    except Exception:
        return []


def _table_exists(conn, tbl_name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (tbl_name,),
    ).fetchone() is not None


def _normalize_area_value(value):
    text = "" if value is None else str(value).strip()
    if text in {"proj", "project"}:
        return "area"
    if text.startswith("proj/"):
        return "area/" + text[5:]
    if text.startswith("project/"):
        return "area/" + text[8:]
    if text.startswith("proj."):
        return "area." + text[5:]
    if text.startswith("project."):
        return "area." + text[8:]
    if text == "All Projects":
        return "All Areas"
    return value


def _normalize_area_values(conn, tbl_name):
    table_sql = _quote_ident(tbl_name)
    try:
        conn.execute(f"UPDATE {table_sql} SET area = 'area' WHERE area = 'proj'")
        conn.execute(
            f"UPDATE {table_sql} SET area = 'area/' || substr(area, 6) WHERE area LIKE 'proj/%'"
        )
        conn.execute(
            f"UPDATE {table_sql} SET area = 'area/' || substr(area, 9) WHERE area LIKE 'project/%'"
        )
        conn.execute(
            f"UPDATE {table_sql} SET area = 'area.' || substr(area, 6) WHERE area LIKE 'proj.%'"
        )
        conn.execute(
            f"UPDATE {table_sql} SET area = 'area.' || substr(area, 9) WHERE area LIKE 'project.%'"
        )
        conn.execute(f"UPDATE {table_sql} SET area = 'area' WHERE area = 'project'")
        conn.execute(
            f"UPDATE {table_sql} SET area = 'All Areas' WHERE area = 'All Projects'"
        )
    except Exception:
        pass


def ensure_area_columns(conn=None, table_names=None):
    conn = _get_conn() if conn is None else conn
    if table_names is None:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        table_names = [row["name"] if isinstance(row, sqlite3.Row) else row[0] for row in rows]
    for tbl_name in table_names:
        if not tbl_name or not _table_exists(conn, tbl_name):
            continue
        cols = _table_column_names(conn, tbl_name)
        col_set = set(cols)
        table_sql = _quote_ident(tbl_name)
        if "project" in col_set and "area" not in col_set:
            try:
                conn.execute(f"ALTER TABLE {table_sql} RENAME COLUMN project TO area")
                col_set.discard("project")
                col_set.add("area")
            except Exception:
                try:
                    conn.execute(f"ALTER TABLE {table_sql} ADD COLUMN area TEXT")
                    conn.execute(f"UPDATE {table_sql} SET area = project WHERE COALESCE(area, '') = ''")
                    col_set.add("area")
                except Exception:
                    pass
        elif "project" in col_set and "area" in col_set:
            try:
                conn.execute(
                    f"UPDATE {table_sql} SET area = project "
                    "WHERE COALESCE(area, '') = '' AND COALESCE(project, '') != ''"
                )
            except Exception:
                pass
        if "area" in col_set:
            _normalize_area_values(conn, tbl_name)
    conn.commit()


def _normalize_area_write_columns(conn, tbl_name, cols, vals):
    table_cols = set(_table_column_names(conn, tbl_name))
    normalized = []
    for col, val in zip(cols, vals):
        next_col = "area" if col == "project" and "area" in table_cols else col
        next_val = _normalize_area_value(val) if next_col == "area" else val
        normalized.append((next_col, next_val))
    return normalized, table_cols


NOTE_SCHEMA_COLUMNS = {
    "file_name": "TEXT",
    "path": "TEXT",
    "folder_id": "INTEGER",
    "size": "TEXT",
    "title": "TEXT",
    "color": "TEXT",
    "date_created": "TEXT",
    "date_modified": "TEXT",
    "area": "TEXT",
    "important": "TEXT",
    "source_note_id": "TEXT",
}

PLACE_SCHEMA_COLUMNS = {
    "name": "TEXT",
    "desc": "TEXT",
    "address_street": "TEXT",
    "suburb": "TEXT",
    "postcode": "TEXT",
    "state": "TEXT",
    "country": "TEXT",
    "gps_lat": "TEXT",
    "gps_long": "TEXT",
    "place_type": "TEXT",
    "virtual_world": "TEXT",
    "coord_x": "TEXT",
    "coord_y": "TEXT",
    "coord_z": "TEXT",
    "coord_region": "TEXT",
    "coord_notes": "TEXT",
    "url": "TEXT",
    "area": "TEXT",
}

_NOTES_SCHEMA_READY_CONN_IDS = set()
_PLACES_SCHEMA_READY_CONN_IDS = set()


def ensure_notes_schema(conn=None):
    conn = _get_conn() if conn is None else conn
    conn_id = id(conn)
    if conn_id in _NOTES_SCHEMA_READY_CONN_IDS:
        try:
            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_notes'"
            ).fetchone()
            if table_row:
                rows = conn.execute("PRAGMA table_info(lp_notes)").fetchall()
                existing = {row[1].lower() for row in rows}
                expected = {col.lower() for col in NOTE_SCHEMA_COLUMNS}
                if expected.issubset(existing):
                    return
        except Exception:
            pass
        _NOTES_SCHEMA_READY_CONN_IDS.discard(conn_id)
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_notes'"
    ).fetchone()
    if not table_row:
        return
    ensure_area_columns(conn, ["lp_notes"])
    rows = conn.execute("PRAGMA table_info(lp_notes)").fetchall()
    existing = {row[1].lower() for row in rows}
    for col_name, col_type in NOTE_SCHEMA_COLUMNS.items():
        if col_name.lower() not in existing:
            conn.execute(f"ALTER TABLE lp_notes ADD COLUMN {col_name} {col_type}")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_folder_id ON lp_notes(folder_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_area ON lp_notes(area)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_area_nocase ON lp_notes(area COLLATE NOCASE)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_path ON lp_notes(path)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_date_modified ON lp_notes(date_modified)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_notes_rec_extract_date ON lp_notes(rec_extract_date)")
    conn.commit()
    _NOTES_SCHEMA_READY_CONN_IDS.add(conn_id)


def ensure_places_schema(conn=None):
    conn = _get_conn() if conn is None else conn
    conn_id = id(conn)
    if conn_id in _PLACES_SCHEMA_READY_CONN_IDS:
        try:
            rows = conn.execute("PRAGMA table_info(lp_places)").fetchall()
            existing = {row[1].lower() for row in rows}
            expected = {col.lower() for col in PLACE_SCHEMA_COLUMNS}
            if expected.issubset(existing):
                return
        except Exception:
            pass
        _PLACES_SCHEMA_READY_CONN_IDS.discard(conn_id)
    table_row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_places'"
    ).fetchone()
    if not table_row:
        return
    rows = conn.execute("PRAGMA table_info(lp_places)").fetchall()
    existing = {row[1].lower() for row in rows}
    for col_name, col_type in PLACE_SCHEMA_COLUMNS.items():
        if col_name.lower() not in existing:
            conn.execute(f"ALTER TABLE lp_places ADD COLUMN {col_name} {col_type}")

    # A LifePIM Place is somewhere the user can navigate to. The active type
    # determines whether the addressing system is Earth, virtual, or Internet.
    conn.execute(
        """
        UPDATE lp_places
           SET place_type = CASE
               WHEN COALESCE(url, '') != '' THEN 'url'
               WHEN COALESCE(virtual_world, '') != ''
                 OR COALESCE(coord_x, '') != ''
                 OR COALESCE(coord_y, '') != ''
                 OR COALESCE(coord_z, '') != ''
                 OR COALESCE(coord_region, '') != '' THEN 'virtual'
               ELSE 'address'
           END
         WHERE COALESCE(place_type, '') = ''
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_lp_places_type ON lp_places(place_type, virtual_world)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_lp_places_area ON lp_places(area)")
    conn.commit()
    _PLACES_SCHEMA_READY_CONN_IDS.add(conn_id)


def _infer_place_type(values_map):
    if (values_map.get("url") or "").strip():
        return "url"
    if any((values_map.get(col) or "").strip() for col in ("virtual_world", "coord_x", "coord_y", "coord_z", "coord_region")):
        return "virtual"
    return "address"


def _normalize_place_write_values(tbl_name, table_cols, cols, vals):
    if tbl_name != "lp_places" or "place_type" not in table_cols:
        return cols, vals
    values_map = dict(zip(cols, vals))
    place_type = (values_map.get("place_type") or "").strip().lower()
    if place_type not in {"address", "url", "virtual"}:
        place_type = _infer_place_type(values_map)
    if "place_type" in cols:
        vals = [place_type if col == "place_type" else val for col, val in zip(cols, vals)]
    else:
        cols.append("place_type")
        vals.append(place_type)
    return cols, vals


def ensure_folder_schema(conn=None):
    conn = _get_conn() if conn is None else conn
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(folder_etl.DDL_CREATE_NO_FK)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    folder_tables = [
        "lp_notes",
        "lp_media",
        "lp_audio",
        "lp_3d",
        "lp_files",
    ]
    for tbl_name in folder_tables:
        add_column_if_missing(conn, tbl_name, "folder_id", "INTEGER")
        conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{tbl_name}_folder_id ON {tbl_name}(folder_id)")
    ensure_notes_schema(conn)
    conn.commit()


def upsert_dim_folder(conn, folder_path):
    conn = _get_conn() if conn is None else conn
    fp = folder_etl.norm_path(folder_path)
    if not fp:
        return None
    conn.execute("INSERT OR IGNORE INTO dim_folder(folder_path) VALUES (?)", (fp,))
    conn.execute(
        "UPDATE dim_folder SET last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), is_active=1 WHERE folder_path=?",
        (fp,),
    )
    row = conn.execute("SELECT folder_id FROM dim_folder WHERE folder_path = ?", (fp,)).fetchone()
    return row["folder_id"] if row else None


def upsert_note_dim_folder(conn, folder_path):
    conn = _get_conn() if conn is None else conn
    fp = _normalize_note_folder_path(folder_path)
    if not fp:
        return None
    conn.execute("INSERT OR IGNORE INTO dim_folder(folder_path) VALUES (?)", (fp,))
    conn.execute(
        "UPDATE dim_folder SET last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'), is_active=1 WHERE folder_path=?",
        (fp,),
    )
    row = conn.execute("SELECT folder_id FROM dim_folder WHERE folder_path = ?", (fp,)).fetchone()
    return row["folder_id"] if row else None


def _normalize_folder_path(path_value):
    return folder_etl.norm_path(path_value)


def _normalize_note_folder_path(path_value):
    path_value = (path_value or "").strip().strip('"').strip()
    if not path_value:
        return ""
    path_value = path_value.replace("/", "\\")
    if len(path_value) >= 2 and path_value[1] == ":":
        path_value = path_value[0].upper() + path_value[1:]
    if len(path_value) > 3 and path_value.endswith("\\"):
        path_value = path_value.rstrip("\\")
    return path_value


def _derive_folder_path(route_name, values_map):
    if route_name == "notes":
        path_value = (values_map.get("path") or "").strip()
        file_name = (values_map.get("file_name") or "").strip()
        full_path = ""
        if file_name and os.path.isabs(file_name):
            full_path = file_name
        elif path_value and file_name:
            full_path = os.path.join(path_value, file_name)
        else:
            full_path = path_value or file_name
        if os.path.splitext(full_path)[1]:
            return os.path.dirname(full_path)
        return path_value or os.path.dirname(full_path)
    if route_name in ("media", "audio", "3d"):
        path_value = (values_map.get("path") or "").strip()
        file_name = (values_map.get("file_name") or "").strip()
        if path_value:
            return path_value
        if file_name and os.path.isabs(file_name):
            return os.path.dirname(file_name)
        return os.path.dirname(os.path.join(path_value, file_name)) if file_name else ""
    if route_name == "files":
        return (values_map.get("path") or "").strip()
    return ""


def update_folder_id_for_record(conn, tbl_name, route_name, record_id, values_map):
    conn = _get_conn() if conn is None else conn
    folder_path = _derive_folder_path(route_name, values_map)
    if route_name == "notes":
        folder_path = _normalize_note_folder_path(folder_path)
    else:
        folder_path = _normalize_folder_path(folder_path)
    if not folder_path:
        return
    if route_name == "notes":
        folder_id = upsert_note_dim_folder(conn, folder_path)
    else:
        folder_id = upsert_dim_folder(conn, folder_path)
    if not folder_id:
        return
    conn.execute(f"UPDATE {tbl_name} SET folder_id = ? WHERE id = ?", (folder_id, record_id))
    conn.commit()


def _qualify_cols(col_list, table_alias="t"):
    cols = []
    for col in col_list:
        col_str = col.strip()
        lower = col_str.lower()
        if col_str == "*":
            cols.append(col_str)
        elif " as " in lower or "(" in col_str or "." in col_str:
            cols.append(col_str)
        else:
            cols.append(f"{table_alias}.{col_str}")
    return ", ".join(cols) if cols else "*"


def _has_area_col(col_list):
    for col in col_list or []:
        col_name = col.strip()
        col_lower = col_name.lower()
        if " as " in col_lower:
            col_name = col_name[: col_lower.index(" as ")].strip()
            col_lower = col_name.lower()
        if "." in col_name:
            col_name = col_name.split(".")[-1].strip()
            col_lower = col_name.lower()
        if col_lower == "area":
            return True
    return False


def _table_has_area(conn, tbl_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({tbl_name})").fetchall()
    except Exception:
        return False
    col_names = []
    for row in rows:
        try:
            col_names.append(row[1])
        except Exception:
            continue
    return _has_area_col(col_names)


def _current_owner_user_id():
    try:
        from flask_login import current_user

        if getattr(current_user, "is_authenticated", False):
            return getattr(current_user, "user_id", None)
    except Exception:
        return None
    return None


def _area_folder_owner_sql(alias="pf"):
    owner_user_id = _current_owner_user_id()
    if owner_user_id is None:
        return f"{alias}.owner_user_id IS NULL"
    return f"{alias}.owner_user_id = {int(owner_user_id)}"


def get_mapped_rows(conn, tbl_name, col_list, tab=None, limit=None, offset=None, order_by=None):
    conn = _get_conn() if conn is None else conn
    cols = _qualify_cols(col_list, "t")
    params = []
    order_clause = order_by or "t.id DESC"
    route_name = _route_for_table(tbl_name)
    if route_name in {"notes", "media", "audio", "3d", "files"}:
        from common import areas as areas_mod

        areas_mod.ensure_areas_schema(conn)
        if tab and tab.lower() == "unmapped":
            sql = (
                f"SELECT {cols} FROM {tbl_name} t "
                "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM lp_area_folders pf "
                f"  WHERE {_area_folder_owner_sql('pf')} "
                "    AND pf.is_enabled = 1 "
                "    AND pf.folder_role IN ('default','include','archive','output') "
                "    AND df.folder_path IS NOT NULL "
                "    AND lower(df.folder_path) LIKE lower(pf.path_prefix) || '%'"
                ") "
                f"ORDER BY {order_clause}"
            )
        elif tab:
            sql = (
                f"SELECT {cols} FROM {tbl_name} t "
                "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
                "WHERE EXISTS ("
                "  SELECT 1 FROM lp_area_folders pf "
                f"  WHERE {_area_folder_owner_sql('pf')} "
                "    AND pf.area_id = ? AND pf.is_enabled = 1 "
                "    AND pf.folder_role IN ('default','include','archive','output') "
                "    AND df.folder_path IS NOT NULL "
                "    AND lower(df.folder_path) LIKE lower(pf.path_prefix) || '%'"
                ") "
                f"ORDER BY {order_clause}"
            )
            params.append(tab)
        else:
            sql = f"SELECT {cols} FROM {tbl_name} t ORDER BY {order_clause}"
    else:
        if tab:
            if _has_area_col(col_list):
                sql = (
                    f"SELECT {cols} FROM {tbl_name} t "
                    "WHERE lower(t.area) = lower(?) "
                    f"ORDER BY {order_clause}"
                )
                params.append(tab)
            else:
                sql = f"SELECT {cols} FROM {tbl_name} t ORDER BY {order_clause}"
        else:
            sql = f"SELECT {cols} FROM {tbl_name} t ORDER BY {order_clause}"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
        if offset:
            sql += " OFFSET ?"
            params.append(int(offset))
    _dbg(f"SELECT {tbl_name} tab={tab} limit={limit} offset={offset}")
    return conn.execute(sql, params).fetchall()


def count_mapped_rows(conn, tbl_name, tab=None):
    conn = _get_conn() if conn is None else conn
    params = []
    route_name = _route_for_table(tbl_name)
    if route_name in {"notes", "media", "audio", "3d", "files"}:
        from common import areas as areas_mod

        areas_mod.ensure_areas_schema(conn)
        if tab and tab.lower() == "unmapped":
            sql = (
                f"SELECT COUNT(1) as cnt FROM {tbl_name} t "
                "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM lp_area_folders pf "
                f"  WHERE {_area_folder_owner_sql('pf')} "
                "    AND pf.is_enabled = 1 "
                "    AND pf.folder_role IN ('default','include','archive','output') "
                "    AND df.folder_path IS NOT NULL "
                "    AND lower(df.folder_path) LIKE lower(pf.path_prefix) || '%'"
                ")"
            )
        elif tab:
            sql = (
                f"SELECT COUNT(1) as cnt FROM {tbl_name} t "
                "LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
                "WHERE EXISTS ("
                "  SELECT 1 FROM lp_area_folders pf "
                f"  WHERE {_area_folder_owner_sql('pf')} "
                "    AND pf.area_id = ? AND pf.is_enabled = 1 "
                "    AND pf.folder_role IN ('default','include','archive','output') "
                "    AND df.folder_path IS NOT NULL "
                "    AND lower(df.folder_path) LIKE lower(pf.path_prefix) || '%'"
                ")"
            )
            params.append(tab)
        else:
            sql = f"SELECT COUNT(1) as cnt FROM {tbl_name} t"
    else:
        if tab:
            if _table_has_area(conn, tbl_name):
                sql = f"SELECT COUNT(1) as cnt FROM {tbl_name} t WHERE lower(t.area) = lower(?)"
                params.append(tab)
            else:
                sql = f"SELECT COUNT(1) as cnt FROM {tbl_name} t"
        else:
            sql = f"SELECT COUNT(1) as cnt FROM {tbl_name} t"
    row = conn.execute(sql, params).fetchone()
    return row["cnt"] if row else 0


def add_record(conn, tbl_name, col_list, value_list):
    """
    Insert a row into a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param col_list: list of cols to set
    :param value_list: list of values to populate
    returns inserted row id or None for failure
    """
    cols = list(col_list)
    vals = list(value_list)
    conn = _get_conn() if conn is None else conn
    table_cols = None
    try:
        ensure_area_columns(conn, [tbl_name])
        normalized, table_cols = _normalize_area_write_columns(conn, tbl_name, cols, vals)
        cols = [col for col, _ in normalized]
        vals = [val for _, val in normalized]
        cols, vals = _normalize_place_write_values(tbl_name, table_cols, cols, vals)
        if "owner_user_id" in table_cols and "owner_user_id" not in cols:
            from flask_login import current_user

            if getattr(current_user, "is_authenticated", False):
                cols.append("owner_user_id")
                vals.append(current_user.user_id)
    except Exception:
        pass
    if table_cols:
        filtered = [(col, val) for col, val in zip(cols, vals) if col in table_cols]
        cols = [col for col, _ in filtered]
        vals = [val for _, val in filtered]
    standard_cols = ["user_name", "rec_extract_date"]
    standard_vals = [_current_user(), _now_str()]
    for col, val in zip(standard_cols, standard_vals):
        if table_cols is None or col in table_cols:
            cols.append(col)
            vals.append(val)
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO {tbl_name} ({', '.join(cols)}) VALUES ({placeholders})"
    try:
        #_dbg(f"INSERT {tbl_name} cols={cols}")
        cur = conn.execute(sql, vals)
        conn.commit()
        record_id = cur.lastrowid
        try:
            _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id)
        except Exception as exc:
            _log_error(conn, f"folder maintenance after add_record failed: {exc}")
        _log_user_change(conn, "add", tbl_name, record_id, before=None, after=_fetch_row_by_id(conn, tbl_name, record_id))
        return record_id
    except Exception as exc:
        _log_error(conn, f"add_record failed: {exc}")
        return None


def update_record(conn, tbl_name, record_id, col_list, value_list):
    """
    Update a row in a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param record_id: the id of the record to update
    :param col_list: list of cols to set
    :param value_list: list of values to update
    returns True for success or False for failure
    """
    cols = list(col_list)
    vals = list(value_list)
    try:
        conn = _get_conn() if conn is None else conn
        ensure_area_columns(conn, [tbl_name])
        normalized, table_cols = _normalize_area_write_columns(conn, tbl_name, cols, vals)
        cols = [col for col, _ in normalized]
        vals = [val for _, val in normalized]
        cols, vals = _normalize_place_write_values(tbl_name, table_cols, cols, vals)
        filtered = [(col, val) for col, val in zip(cols, vals) if col in table_cols]
        cols = [col for col, _ in filtered]
        vals = [val for _, val in filtered]
        if "rec_extract_date" in table_cols:
            cols.append("rec_extract_date")
            vals.append(_now_str())
        if not cols:
            return False
        set_clause = ", ".join([f"{col} = ?" for col in cols])
        sql = f"UPDATE {tbl_name} SET {set_clause} WHERE id = ?"
        vals.append(record_id)
        before = _fetch_row_by_id(conn, tbl_name, record_id)
        _dbg(f"UPDATE {tbl_name} id={record_id} cols={col_list}")
        conn.execute(sql, vals)
        conn.commit()
        _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id)
        after = _fetch_row_by_id(conn, tbl_name, record_id)
        _log_user_change(conn, "update", tbl_name, record_id, before=before, after=after)
        return True
    except Exception as exc:
        _log_error(conn, f"update_record failed: {exc}")
        return False


def delete_record(conn, tbl_name, record_id):
    """
    Delete a row from a table.

    :param conn: connection object to database
    :param tbl_name: name of the table (lp_events, lp_notes, ...)
    :param record_id: the id of the record to delete
    returns True for success or False for failure
    """
    sql = f"DELETE FROM {tbl_name} WHERE id = ?"
    try:
        conn = _get_conn() if conn is None else conn
        before = _fetch_row_by_id(conn, tbl_name, record_id)
        _dbg(f"DELETE {tbl_name} id={record_id}")
        conn.execute(sql, [record_id])
        conn.commit()
        if before is not None:
            _log_user_change(conn, "delete", tbl_name, record_id, before=before, after=None)
        return True
    except Exception as exc:
        _log_error(conn, f"delete_record failed: {exc}")
        return False


conn = None


def _route_for_table(tbl_name):
    for tbl in cfg.table_def:
        if tbl.get("name") == tbl_name:
            return tbl.get("route")
    return None


def _fetch_row_by_id(conn, tbl_name, record_id):
    try:
        row = conn.execute(f"SELECT * FROM {tbl_name} WHERE id = ?", [record_id]).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return dict(row)
    except Exception:
        return row


def _log_user_change(conn, action, tbl_name, record_id, before=None, after=None):
    try:
        from common import utils as utils_mod

        utils_mod.lg_usr(
            action=action,
            entity_type=tbl_name,
            entity_id=record_id,
            before=before,
            after=after,
            conn=conn,
        )
    except Exception:
        pass


def _update_folder_id_from_values(conn, tbl_name, col_list, value_list, record_id):
    route_name = _route_for_table(tbl_name)
    if route_name not in {"notes", "media", "audio", "3d", "files"}:
        return
    values_map = dict(zip(col_list, value_list))
    update_folder_id_for_record(conn, tbl_name, route_name, record_id, values_map)
