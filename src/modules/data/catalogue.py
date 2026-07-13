import fnmatch
import json
import os
import sqlite3
from datetime import datetime
from urllib.parse import quote

import pandas as pd

from common import data as db


DB_SOURCE_TYPES = ["SQLITE", "CSV", "EXCEL", "DUCKDB", "SQL_SERVER", "ORACLE", "FABRIC_SQL", "ODBC"]
FILE_SOURCE_TYPES = ["CSV", "PARQUET", "TEXT", "JSON", "SPREADSHEET", "MIXED", "OTHER"]
CATALOGUE_LEVELS = ["DISCOVERED", "REGISTERED", "MANAGED"]
OBJECT_TYPES = [
    "TABLE",
    "VIEW",
    "CSV_TABLE",
    "EXCEL_SHEET",
    "CSV_FILE",
    "PARQUET_FILE",
    "JSON_FILE",
    "TEXT_FILE",
    "SPREADSHEET",
    "FILE",
    "FOLDER_DATASET",
    "OTHER",
]
TASK_TYPES = [
    "TEST_DATABASE_CONNECTION",
    "SCAN_DATABASE_METADATA",
    "SCAN_FILE_SOURCE",
    "REFRESH_OBJECT_METADATA",
    "PROFILE_OBJECT",
    "RUN_SAVED_SQL",
]
CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin1"]


def conn():
    return db._get_conn()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(connection=None):
    c = connection or conn()
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS d_data_source (
            data_source_id INTEGER PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_type TEXT NOT NULL,
            host_name TEXT,
            port INTEGER,
            database_name TEXT,
            default_schema TEXT,
            root_path TEXT,
            environment TEXT,
            project TEXT,
            credential_reference TEXT,
            connection_options_json TEXT,
            recursive_scan INTEGER NOT NULL DEFAULT 1,
            include_patterns TEXT,
            exclude_patterns TEXT,
            archive_rules TEXT,
            ignore_rules TEXT,
            scan_views INTEGER NOT NULL DEFAULT 1,
            scan_columns INTEGER NOT NULL DEFAULT 1,
            collect_row_counts INTEGER NOT NULL DEFAULT 0,
            row_count_mode TEXT,
            infer_schemas INTEGER NOT NULL DEFAULT 1,
            extract_text_metadata INTEGER NOT NULL DEFAULT 0,
            collect_hashes INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_scan_started_at TEXT,
            last_scan_completed_at TEXT,
            last_scan_status TEXT,
            last_scan_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS d_data_object (
            data_object_id INTEGER PRIMARY KEY,
            data_source_id INTEGER NOT NULL,
            object_name TEXT NOT NULL,
            display_name TEXT,
            object_type TEXT NOT NULL,
            database_name TEXT,
            schema_name TEXT,
            parent_path TEXT,
            project TEXT,
            full_name TEXT,
            full_path TEXT,
            catalogue_level TEXT NOT NULL DEFAULT 'DISCOVERED',
            row_count INTEGER,
            row_count_is_estimate INTEGER NOT NULL DEFAULT 0,
            column_count INTEGER,
            size_bytes INTEGER,
            profile_status TEXT,
            quality_status TEXT,
            description TEXT,
            purpose TEXT,
            notes TEXT,
            is_favourite INTEGER NOT NULL DEFAULT 0,
            is_canonical INTEGER NOT NULL DEFAULT 0,
            is_sensitive INTEGER NOT NULL DEFAULT 0,
            is_hidden INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            profile_mode TEXT NOT NULL DEFAULT 'NONE',
            content_index_mode TEXT NOT NULL DEFAULT 'METADATA',
            refresh_policy TEXT NOT NULL DEFAULT 'MANUAL',
            first_seen_at TEXT,
            last_seen_at TEXT,
            last_scanned_at TEXT,
            last_profiled_at TEXT,
            last_used_at TEXT,
            source_modified_at TEXT,
            source_created_at TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (data_source_id) REFERENCES d_data_source(data_source_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_column (
            data_column_id INTEGER PRIMARY KEY,
            data_object_id INTEGER NOT NULL,
            column_name TEXT NOT NULL,
            ordinal_position INTEGER,
            data_type TEXT,
            source_data_type TEXT,
            is_nullable INTEGER,
            is_primary_key INTEGER NOT NULL DEFAULT 0,
            is_unique INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            notes TEXT,
            null_count INTEGER,
            distinct_count INTEGER,
            minimum_value TEXT,
            maximum_value TEXT,
            mean_value REAL,
            sample_value TEXT,
            profile_status TEXT,
            last_profiled_at TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (data_object_id) REFERENCES d_data_object(data_object_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_saved_sql (
            saved_sql_id INTEGER PRIMARY KEY,
            sql_name TEXT NOT NULL,
            data_source_id INTEGER,
            project TEXT,
            default_database TEXT,
            default_schema TEXT,
            sql_text TEXT NOT NULL,
            purpose TEXT,
            notes TEXT,
            parameter_json TEXT,
            output_type TEXT,
            linked_file_path TEXT,
            authoritative_location TEXT NOT NULL DEFAULT 'DATABASE',
            is_favourite INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT,
            last_run_status TEXT,
            last_result_path TEXT,
            last_error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (data_source_id) REFERENCES d_data_source(data_source_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_object_sql (
            data_object_id INTEGER NOT NULL,
            saved_sql_id INTEGER NOT NULL,
            relationship_type TEXT,
            notes TEXT,
            PRIMARY KEY (data_object_id, saved_sql_id),
            FOREIGN KEY (data_object_id) REFERENCES d_data_object(data_object_id),
            FOREIGN KEY (saved_sql_id) REFERENCES d_data_saved_sql(saved_sql_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_object_relationship (
            relationship_id INTEGER PRIMARY KEY,
            from_object_id INTEGER NOT NULL,
            to_object_id INTEGER NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL,
            is_manual INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (from_object_id) REFERENCES d_data_object(data_object_id),
            FOREIGN KEY (to_object_id) REFERENCES d_data_object(data_object_id)
        );

        CREATE TABLE IF NOT EXISTS d_tag (
            tag_id INTEGER PRIMARY KEY,
            tag_name TEXT NOT NULL UNIQUE,
            tag_group TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS d_data_source_tag (
            data_source_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (data_source_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_object_tag (
            data_object_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (data_object_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_saved_sql_tag (
            saved_sql_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (saved_sql_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS d_data_task (
            data_task_id INTEGER PRIMARY KEY,
            task_name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            data_source_id INTEGER,
            data_object_id INTEGER,
            saved_sql_id INTEGER,
            status TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            parameters_json TEXT,
            log_output TEXT,
            result_summary TEXT,
            result_file_path TEXT,
            error_message TEXT,
            started_at TEXT,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_data_source_kind ON d_data_source(source_kind);
        CREATE INDEX IF NOT EXISTS idx_data_source_environment ON d_data_source(environment);
        CREATE INDEX IF NOT EXISTS idx_data_object_source ON d_data_object(data_source_id);
        CREATE INDEX IF NOT EXISTS idx_data_object_catalogue_level ON d_data_object(catalogue_level);
        CREATE INDEX IF NOT EXISTS idx_data_object_type ON d_data_object(object_type);
        CREATE INDEX IF NOT EXISTS idx_data_object_last_seen ON d_data_object(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_data_column_object ON d_data_column(data_object_id);
        CREATE INDEX IF NOT EXISTS idx_saved_sql_source ON d_data_saved_sql(data_source_id);
        CREATE INDEX IF NOT EXISTS idx_data_task_status ON d_data_task(status);
        """
    )
    _ensure_column(c, "d_data_source", "project", "TEXT")
    _ensure_column(c, "d_data_object", "project", "TEXT")
    _ensure_column(c, "d_data_saved_sql", "project", "TEXT")
    c.execute(
        """
        UPDATE d_data_saved_sql
        SET project = (
            SELECT s.project FROM d_data_source s
            WHERE s.data_source_id = d_data_saved_sql.data_source_id
        )
        WHERE COALESCE(project, '') = ''
          AND data_source_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM d_data_source s
              WHERE s.data_source_id = d_data_saved_sql.data_source_id
                AND COALESCE(s.project, '') != ''
          )
        """
    )
    c.commit()


def _ensure_column(connection, table_name, column_name, column_type):
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({_quote_ident(table_name)})").fetchall()
    }
    if column_name not in existing:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def scalar(sql, params=()):
    row = conn().execute(sql, params).fetchone()
    return row[0] if row else 0


def rows(sql, params=()):
    return [dict(row) for row in conn().execute(sql, params).fetchall()]


def row(sql, params=()):
    result = conn().execute(sql, params).fetchone()
    return dict(result) if result else None


def parse_tags(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def tag_string(entity_type, entity_id):
    table, id_col = {
        "source": ("d_data_source_tag", "data_source_id"),
        "object": ("d_data_object_tag", "data_object_id"),
        "sql": ("d_data_saved_sql_tag", "saved_sql_id"),
    }[entity_type]
    values = rows(
        f"""
        SELECT t.tag_name
        FROM {table} jt
        JOIN d_tag t ON t.tag_id = jt.tag_id
        WHERE jt.{id_col} = ?
        ORDER BY t.tag_name
        """,
        (entity_id,),
    )
    return ", ".join(item["tag_name"] for item in values)


def set_tags(entity_type, entity_id, tag_text):
    table, id_col = {
        "source": ("d_data_source_tag", "data_source_id"),
        "object": ("d_data_object_tag", "data_object_id"),
        "sql": ("d_data_saved_sql_tag", "saved_sql_id"),
    }[entity_type]
    c = conn()
    c.execute(f"DELETE FROM {table} WHERE {id_col} = ?", (entity_id,))
    for tag_name in parse_tags(tag_text):
        c.execute(
            "INSERT OR IGNORE INTO d_tag(tag_name, created_at) VALUES (?, ?)",
            (tag_name, now()),
        )
        tag_id = c.execute("SELECT tag_id FROM d_tag WHERE tag_name = ?", (tag_name,)).fetchone()["tag_id"]
        c.execute(f"INSERT OR IGNORE INTO {table}({id_col}, tag_id) VALUES (?, ?)", (entity_id, tag_id))
    c.commit()


def source_list(kind=None, filters=None):
    filters = filters or {}
    params = []
    clauses = []
    if kind:
        clauses.append("s.source_kind = ?")
        params.append(kind)
    if filters.get("project"):
        clauses.append("s.project = ?")
        params.append(filters["project"])
    where = " AND ".join(clauses) if clauses else "1=1"
    items = rows(
        f"""
        SELECT s.*,
               COUNT(o.data_object_id) AS object_count,
               GROUP_CONCAT(DISTINCT t.tag_name) AS tags
        FROM d_data_source s
        LEFT JOIN d_data_object o ON o.data_source_id = s.data_source_id
        LEFT JOIN d_data_source_tag st ON st.data_source_id = s.data_source_id
        LEFT JOIN d_tag t ON t.tag_id = st.tag_id
        WHERE {where}
        GROUP BY s.data_source_id
        ORDER BY s.is_active DESC, s.source_name
        """,
        params,
    )
    for item in items:
        item["tags"] = item.get("tags") or ""
    return items


def source_get(source_id):
    item = row("SELECT * FROM d_data_source WHERE data_source_id = ?", (source_id,))
    if item:
        item["tags"] = tag_string("source", source_id)
    return item


def save_source(source_id, form, kind):
    c = conn()
    ts = now()
    values = _source_values(form, kind)
    if source_id:
        set_clause = ", ".join([f"{key} = ?" for key in values])
        c.execute(
            f"UPDATE d_data_source SET {set_clause}, updated_at = ? WHERE data_source_id = ?",
            list(values.values()) + [ts, source_id],
        )
        new_id = source_id
    else:
        values["created_at"] = ts
        values["updated_at"] = ts
        cols = list(values.keys())
        c.execute(
            f"INSERT INTO d_data_source ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
            list(values.values()),
        )
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()
    set_tags("source", new_id, form.get("tags", ""))
    return new_id


def _source_values(form, kind):
    return {
        "source_name": form.get("source_name", "").strip(),
        "source_kind": kind,
        "source_type": form.get("source_type", "").strip(),
        "host_name": form.get("host_name", "").strip(),
        "port": _int_or_none(form.get("port")),
        "database_name": form.get("database_name", "").strip(),
        "default_schema": form.get("default_schema", "").strip(),
        "root_path": form.get("root_path", "").strip(),
        "environment": form.get("environment", "").strip(),
        "project": form.get("project", "").strip(),
        "credential_reference": form.get("credential_reference", "").strip(),
        "connection_options_json": form.get("connection_options_json", "").strip(),
        "recursive_scan": _checked(form, "recursive_scan", default=True),
        "include_patterns": form.get("include_patterns", "").strip(),
        "exclude_patterns": form.get("exclude_patterns", "").strip(),
        "archive_rules": form.get("archive_rules", "").strip(),
        "ignore_rules": form.get("ignore_rules", "").strip(),
        "scan_views": _checked(form, "scan_views", default=True),
        "scan_columns": _checked(form, "scan_columns", default=True),
        "collect_row_counts": _checked(form, "collect_row_counts"),
        "row_count_mode": form.get("row_count_mode", "").strip(),
        "infer_schemas": _checked(form, "infer_schemas", default=True),
        "extract_text_metadata": _checked(form, "extract_text_metadata"),
        "collect_hashes": _checked(form, "collect_hashes"),
        "notes": form.get("notes", "").strip(),
        "is_active": _checked(form, "is_active", default=True),
    }


def delete_source(source_id):
    c = conn()
    object_ids = [item["data_object_id"] for item in rows("SELECT data_object_id FROM d_data_object WHERE data_source_id = ?", (source_id,))]
    for object_id in object_ids:
        c.execute("DELETE FROM d_data_object_sql WHERE data_object_id = ?", (object_id,))
        c.execute("DELETE FROM d_data_object_tag WHERE data_object_id = ?", (object_id,))
        c.execute("DELETE FROM d_data_column WHERE data_object_id = ?", (object_id,))
        c.execute("DELETE FROM d_data_object_relationship WHERE from_object_id = ? OR to_object_id = ?", (object_id, object_id))
    c.execute("DELETE FROM d_data_object WHERE data_source_id = ?", (source_id,))
    c.execute("DELETE FROM d_data_source_tag WHERE data_source_id = ?", (source_id,))
    c.execute("UPDATE d_data_saved_sql SET data_source_id = NULL WHERE data_source_id = ?", (source_id,))
    c.execute("UPDATE d_data_task SET data_source_id = NULL WHERE data_source_id = ?", (source_id,))
    c.execute("DELETE FROM d_data_source WHERE data_source_id = ?", (source_id,))
    c.commit()


def object_list(filters):
    clauses = []
    params = []
    q = (filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        clauses.append(
            """(
            o.object_name LIKE ? OR o.display_name LIKE ? OR o.full_name LIKE ? OR
            o.full_path LIKE ? OR o.description LIKE ? OR o.purpose LIKE ? OR
            o.notes LIKE ? OR s.source_name LIKE ? OR EXISTS (
                SELECT 1 FROM d_data_column c
                WHERE c.data_object_id = o.data_object_id AND c.column_name LIKE ?
            ) OR EXISTS (
                SELECT 1 FROM d_data_object_tag ot
                JOIN d_tag tg ON tg.tag_id = ot.tag_id
                WHERE ot.data_object_id = o.data_object_id AND tg.tag_name LIKE ?
            ))"""
        )
        params.extend([like] * 10)
    for key, col in [
        ("source_id", "o.data_source_id"),
        ("object_type", "o.object_type"),
        ("catalogue_level", "o.catalogue_level"),
        ("environment", "s.environment"),
        ("project", "o.project"),
        ("profile_status", "o.profile_status"),
        ("quality_status", "o.quality_status"),
    ]:
        value = filters.get(key)
        if value:
            clauses.append(f"{col} = ?")
            params.append(value)
    for key, col in [("favourite", "o.is_favourite"), ("hidden", "o.is_hidden"), ("active", "o.is_active")]:
        value = filters.get(key)
        if value in ("0", "1"):
            clauses.append(f"{col} = ?")
            params.append(int(value))
    where = " AND ".join(clauses) if clauses else "1=1"
    return rows(
        f"""
        SELECT o.*, s.source_name, s.source_kind, s.source_type, s.environment, s.project AS source_project,
               GROUP_CONCAT(DISTINCT t.tag_name) AS tags
        FROM d_data_object o
        JOIN d_data_source s ON s.data_source_id = o.data_source_id
        LEFT JOIN d_data_object_tag ot ON ot.data_object_id = o.data_object_id
        LEFT JOIN d_tag t ON t.tag_id = ot.tag_id
        WHERE {where}
        GROUP BY o.data_object_id
        ORDER BY o.is_favourite DESC,
                 CASE o.catalogue_level WHEN 'MANAGED' THEN 0 WHEN 'REGISTERED' THEN 1 ELSE 2 END,
                 COALESCE(o.last_used_at, o.last_seen_at, o.updated_at) DESC
        LIMIT 500
        """,
        params,
    )


def object_get(object_id):
    item = row(
        """
        SELECT o.*, s.source_name, s.source_kind, s.source_type, s.environment, s.project AS source_project
        FROM d_data_object o
        JOIN d_data_source s ON s.data_source_id = o.data_source_id
        WHERE o.data_object_id = ?
        """,
        (object_id,),
    )
    if item:
        item["tags"] = tag_string("object", object_id)
    return item


def object_columns(object_id):
    return rows("SELECT * FROM d_data_column WHERE data_object_id = ? ORDER BY ordinal_position, column_name", (object_id,))


def save_object_metadata(object_id, form):
    c = conn()
    c.execute(
        """
        UPDATE d_data_object
        SET display_name = ?, catalogue_level = ?, description = ?, purpose = ?, notes = ?,
            project = ?,
            is_favourite = ?, is_canonical = ?, is_sensitive = ?, is_hidden = ?, is_active = ?,
            profile_mode = ?, content_index_mode = ?, refresh_policy = ?, updated_at = ?
        WHERE data_object_id = ?
        """,
        (
            form.get("display_name", "").strip(),
            form.get("catalogue_level", "DISCOVERED"),
            form.get("description", "").strip(),
            form.get("purpose", "").strip(),
            form.get("notes", "").strip(),
            form.get("project", "").strip(),
            _checked(form, "is_favourite"),
            _checked(form, "is_canonical"),
            _checked(form, "is_sensitive"),
            _checked(form, "is_hidden"),
            _checked(form, "is_active", default=True),
            form.get("profile_mode", "NONE"),
            form.get("content_index_mode", "METADATA"),
            form.get("refresh_policy", "MANUAL"),
            now(),
            object_id,
        ),
    )
    c.commit()
    set_tags("object", object_id, form.get("tags", ""))


def update_object_flags(object_id, **flags):
    if not flags:
        return
    c = conn()
    set_clause = ", ".join([f"{key} = ?" for key in flags])
    c.execute(
        f"UPDATE d_data_object SET {set_clause}, updated_at = ? WHERE data_object_id = ?",
        list(flags.values()) + [now(), object_id],
    )
    c.commit()


def update_object_level(object_id, level):
    if level in CATALOGUE_LEVELS:
        update_object_flags(object_id, catalogue_level=level)


def sql_list(filters=None):
    filters = filters or {}
    clauses = []
    params = []
    q = (filters.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        clauses.append("(ss.sql_name LIKE ? OR ss.purpose LIKE ? OR ss.notes LIKE ? OR ss.sql_text LIKE ?)")
        params.extend([like] * 4)
    if filters.get("source_id"):
        clauses.append("ss.data_source_id = ?")
        params.append(filters["source_id"])
    if filters.get("project"):
        clauses.append("ss.project = ?")
        params.append(filters["project"])
    if filters.get("favourite") in ("0", "1"):
        clauses.append("ss.is_favourite = ?")
        params.append(int(filters["favourite"]))
    where = " AND ".join(clauses) if clauses else "1=1"
    return rows(
        f"""
        SELECT ss.*, s.source_name, s.source_type, s.environment, s.project AS source_project,
               GROUP_CONCAT(DISTINCT t.tag_name) AS tags
        FROM d_data_saved_sql ss
        LEFT JOIN d_data_source s ON s.data_source_id = ss.data_source_id
        LEFT JOIN d_data_saved_sql_tag st ON st.saved_sql_id = ss.saved_sql_id
        LEFT JOIN d_tag t ON t.tag_id = st.tag_id
        WHERE {where}
        GROUP BY ss.saved_sql_id
        ORDER BY ss.is_favourite DESC, ss.updated_at DESC, ss.sql_name
        """,
        params,
    )


def sql_get(sql_id):
    item = row(
        """
        SELECT ss.*, s.source_name, s.source_type, s.environment, s.project AS source_project
        FROM d_data_saved_sql ss
        LEFT JOIN d_data_source s ON s.data_source_id = ss.data_source_id
        WHERE ss.saved_sql_id = ?
        """,
        (sql_id,),
    )
    if item:
        item["tags"] = tag_string("sql", sql_id)
        item["related_object_ids"] = [
            str(r["data_object_id"])
            for r in rows("SELECT data_object_id FROM d_data_object_sql WHERE saved_sql_id = ?", (sql_id,))
        ]
    return item


def save_sql(sql_id, form):
    c = conn()
    ts = now()
    values = {
        "sql_name": form.get("sql_name", "").strip(),
        "data_source_id": _int_or_none(form.get("data_source_id")),
        "project": form.get("project", "").strip(),
        "default_database": form.get("default_database", "").strip(),
        "default_schema": form.get("default_schema", "").strip(),
        "sql_text": form.get("sql_text", "").strip(),
        "purpose": form.get("purpose", "").strip(),
        "notes": form.get("notes", "").strip(),
        "parameter_json": form.get("parameter_json", "").strip(),
        "output_type": form.get("output_type", "").strip(),
        "linked_file_path": form.get("linked_file_path", "").strip(),
        "authoritative_location": form.get("authoritative_location", "DATABASE"),
        "is_favourite": _checked(form, "is_favourite"),
        "is_active": _checked(form, "is_active", default=True),
    }
    if not values["project"] and values["data_source_id"]:
        source = source_get(values["data_source_id"])
        values["project"] = source.get("project", "") if source else ""
    if sql_id:
        set_clause = ", ".join([f"{key} = ?" for key in values])
        c.execute(
            f"UPDATE d_data_saved_sql SET {set_clause}, updated_at = ? WHERE saved_sql_id = ?",
            list(values.values()) + [ts, sql_id],
        )
        new_id = sql_id
    else:
        values["created_at"] = ts
        values["updated_at"] = ts
        cols = list(values.keys())
        c.execute(
            f"INSERT INTO d_data_saved_sql ({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
            list(values.values()),
        )
        new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.execute("DELETE FROM d_data_object_sql WHERE saved_sql_id = ?", (new_id,))
    related_objects = form.getlist("related_objects") if hasattr(form, "getlist") else form.get("related_objects", [])
    if isinstance(related_objects, str):
        related_objects = [related_objects]
    for object_id in related_objects:
        object_id = _int_or_none(object_id)
        if object_id:
            c.execute(
                "INSERT OR IGNORE INTO d_data_object_sql(data_object_id, saved_sql_id, relationship_type) VALUES (?, ?, ?)",
                (object_id, new_id, "USES"),
            )
    c.commit()
    set_tags("sql", new_id, form.get("tags", ""))
    return new_id


def delete_sql(sql_id):
    c = conn()
    c.execute("DELETE FROM d_data_object_sql WHERE saved_sql_id = ?", (sql_id,))
    c.execute("DELETE FROM d_data_saved_sql_tag WHERE saved_sql_id = ?", (sql_id,))
    c.execute("UPDATE d_data_task SET saved_sql_id = NULL WHERE saved_sql_id = ?", (sql_id,))
    c.execute("DELETE FROM d_data_saved_sql WHERE saved_sql_id = ?", (sql_id,))
    c.commit()


def sql_related_objects(sql_id):
    return rows(
        """
        SELECT o.*, os.relationship_type
        FROM d_data_object_sql os
        JOIN d_data_object o ON o.data_object_id = os.data_object_id
        WHERE os.saved_sql_id = ?
        ORDER BY o.object_name
        """,
        (sql_id,),
    )


def tasks(limit=None, filters=None):
    filters = filters or {}
    clauses = []
    params = []
    if filters.get("project"):
        clauses.append(
            "(s.project = ? OR o.project = ? OR ss.project = ?)"
        )
        params.extend([filters["project"]] * 3)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = """
        SELECT t.*, s.source_name, s.project AS source_project,
               o.object_name, o.project AS object_project,
               ss.sql_name, ss.project AS sql_project
        FROM d_data_task t
        LEFT JOIN d_data_source s ON s.data_source_id = t.data_source_id
        LEFT JOIN d_data_object o ON o.data_object_id = t.data_object_id
        LEFT JOIN d_data_saved_sql ss ON ss.saved_sql_id = t.saved_sql_id
        {where}
        ORDER BY COALESCE(t.started_at, t.created_at) DESC
    """.format(where=where)
    if limit:
        sql += " LIMIT ?"
        return rows(sql, params + [limit])
    return rows(sql, params)


def task_get(task_id):
    return row(
        """
        SELECT t.*, s.source_name, o.object_name, ss.sql_name
        FROM d_data_task t
        LEFT JOIN d_data_source s ON s.data_source_id = t.data_source_id
        LEFT JOIN d_data_object o ON o.data_object_id = t.data_object_id
        LEFT JOIN d_data_saved_sql ss ON ss.saved_sql_id = t.saved_sql_id
        WHERE t.data_task_id = ?
        """,
        (task_id,),
    )


def create_task(task_name, task_type, source_id=None, object_id=None, sql_id=None, params=None):
    c = conn()
    ts = now()
    cur = c.execute(
        """
        INSERT INTO d_data_task(
            task_name, task_type, data_source_id, data_object_id, saved_sql_id,
            status, progress, parameters_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, 'QUEUED', 0, ?, ?, ?)
        """,
        (task_name, task_type, source_id, object_id, sql_id, json.dumps(params or {}), ts, ts),
    )
    c.commit()
    return cur.lastrowid


def finish_task(task_id, status, progress=100, result_summary="", error_message="", log_output=""):
    ts = now()
    conn().execute(
        """
        UPDATE d_data_task
        SET status = ?, progress = ?, result_summary = ?, error_message = ?,
            log_output = ?, finished_at = ?, updated_at = ?
        WHERE data_task_id = ?
        """,
        (status, progress, result_summary, error_message, log_output, ts, ts, task_id),
    )
    conn().commit()


def start_task(task_id):
    ts = now()
    conn().execute(
        "UPDATE d_data_task SET status = 'RUNNING', progress = 5, started_at = ?, updated_at = ? WHERE data_task_id = ?",
        (ts, ts, task_id),
    )
    conn().commit()


def test_database_connection(source_id):
    source = source_get(source_id)
    task_id = create_task("Test database connection", "TEST_DATABASE_CONNECTION", source_id=source_id)
    start_task(task_id)
    try:
        if not source or source["source_type"] != "SQLITE":
            raise ValueError("Only SQLite connection tests are implemented in Phase 1.")
        path = source.get("root_path") or source.get("database_name")
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(path or "No SQLite file path configured.")
        test_conn = sqlite_readonly_connection(path)
        test_conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        test_conn.close()
        finish_task(task_id, "COMPLETED", result_summary="SQLite database opened successfully.")
    except Exception as exc:
        finish_task(task_id, "FAILED", result_summary="Connection test failed.", error_message=str(exc))
    return task_id


def scan_source(source_id):
    source = source_get(source_id)
    if not source:
        return None
    if source["source_kind"] == "DATABASE":
        if source["source_type"] == "SQLITE":
            return scan_sqlite_source(source_id)
        if source["source_type"] in {"CSV", "EXCEL"}:
            return scan_tabular_file_source(source_id)
        return scan_sqlite_source(source_id)
    return scan_file_source(source_id)


def scan_sqlite_source(source_id):
    source = source_get(source_id)
    task_id = create_task("Scan database metadata", "SCAN_DATABASE_METADATA", source_id=source_id)
    start_task(task_id)
    started = now()
    c = conn()
    c.execute(
        "UPDATE d_data_source SET last_scan_started_at = ?, last_scan_status = 'RUNNING' WHERE data_source_id = ?",
        (started, source_id),
    )
    try:
        if source["source_type"] != "SQLITE":
            raise ValueError("Only SQLite metadata scans are implemented in Phase 1.")
        path = source.get("root_path") or source.get("database_name")
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(path or "No SQLite file path configured.")
        source_conn = sqlite_readonly_connection(path)
        source_conn.row_factory = sqlite3.Row
        table_rows = source_conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()
        count = 0
        for table in table_rows:
            table_name = table["name"]
            object_type = "VIEW" if table["type"] == "view" else "TABLE"
            columns = source_conn.execute(f"PRAGMA table_info({_quote_ident(table_name)})").fetchall()
            row_count = None
            if object_type == "TABLE":
                try:
                    row_count = source_conn.execute(f"SELECT COUNT(1) AS cnt FROM {_quote_ident(table_name)}").fetchone()["cnt"]
                except sqlite3.Error:
                    row_count = None
            object_id = upsert_object(
                source_id,
                object_name=table_name,
                object_type=object_type,
                database_name=source.get("database_name") or os.path.basename(path),
                schema_name=source.get("default_schema") or "",
                project=source.get("project") or "",
                full_name=table_name,
                full_path="",
                row_count=row_count,
                column_count=len(columns),
                size_bytes=None,
                metadata={"sqlite_type": table["type"]},
            )
            c.execute("DELETE FROM d_data_column WHERE data_object_id = ?", (object_id,))
            for col in columns:
                upsert_column(object_id, col)
            count += 1
        source_conn.close()
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'COMPLETED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, f"Scanned {count} SQLite objects.", completed, source_id),
        )
        c.commit()
        finish_task(task_id, "COMPLETED", result_summary=f"Scanned {count} SQLite objects.")
    except Exception as exc:
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'FAILED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, str(exc), completed, source_id),
        )
        c.commit()
        finish_task(task_id, "FAILED", result_summary="Metadata scan failed.", error_message=str(exc))
    return task_id


def scan_tabular_file_source(source_id):
    source = source_get(source_id)
    task_id = create_task("Scan file-backed data source", "SCAN_DATABASE_METADATA", source_id=source_id)
    start_task(task_id)
    started = now()
    c = conn()
    c.execute(
        "UPDATE d_data_source SET last_scan_started_at = ?, last_scan_status = 'RUNNING' WHERE data_source_id = ?",
        (started, source_id),
    )
    try:
        path = source.get("root_path") or ""
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(path or "No data file path configured.")
        source_type = source.get("source_type")
        stat = os.stat(path)
        if source_type == "CSV":
            count = _scan_csv_source(source_id, source, path, stat)
        elif source_type == "EXCEL":
            count = _scan_excel_source(source_id, source, path, stat)
        else:
            raise ValueError(f"Unsupported file-backed data source type: {source_type}")
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'COMPLETED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, f"Scanned {count} data object(s).", completed, source_id),
        )
        c.commit()
        finish_task(task_id, "COMPLETED", result_summary=f"Scanned {count} data object(s).")
    except Exception as exc:
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'FAILED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, str(exc), completed, source_id),
        )
        c.commit()
        finish_task(task_id, "FAILED", result_summary="File-backed data source scan failed.", error_message=str(exc))
    return task_id


def _scan_csv_source(source_id, source, path, stat):
    frame, encoding = _read_csv_frame(path, nrows=200)
    row_count = _csv_row_count(path)
    object_id = upsert_object(
        source_id,
        object_name=os.path.basename(path),
        object_type="CSV_TABLE",
        database_name=source.get("database_name") or os.path.basename(path),
        schema_name="",
        parent_path=os.path.dirname(path),
        project=source.get("project") or "",
        full_name=os.path.basename(path),
        full_path=os.path.abspath(path),
        row_count=row_count,
        column_count=len(frame.columns),
        size_bytes=stat.st_size,
        source_modified_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        source_created_at=datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        metadata={"file_type": "csv", "encoding": encoding, "sampled_rows_for_schema": len(frame.index)},
    )
    _replace_dataframe_columns(object_id, frame)
    return 1


def _scan_excel_source(source_id, source, path, stat):
    workbook = pd.ExcelFile(path)
    count = 0
    for sheet_name in workbook.sheet_names:
        frame = pd.read_excel(workbook, sheet_name=sheet_name, nrows=200)
        object_id = upsert_object(
            source_id,
            object_name=sheet_name,
            object_type="EXCEL_SHEET",
            database_name=source.get("database_name") or os.path.basename(path),
            schema_name="",
            parent_path=os.path.dirname(path),
            project=source.get("project") or "",
            full_name=f"{os.path.basename(path)}::{sheet_name}",
            full_path=os.path.abspath(path),
            row_count=len(frame.index),
            column_count=len(frame.columns),
            size_bytes=stat.st_size,
            source_modified_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            source_created_at=datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            metadata={"file_type": "excel", "sheet_name": sheet_name, "sampled_rows_for_schema": len(frame.index)},
        )
        _replace_dataframe_columns(object_id, frame)
        count += 1
    return count


def _replace_dataframe_columns(object_id, frame):
    c = conn()
    c.execute("DELETE FROM d_data_column WHERE data_object_id = ?", (object_id,))
    ts = now()
    for idx, column_name in enumerate(frame.columns, start=1):
        series = frame[column_name]
        c.execute(
            """
            INSERT INTO d_data_column(
                data_object_id, column_name, ordinal_position, data_type, source_data_type,
                is_nullable, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                object_id,
                str(column_name),
                idx,
                str(series.dtype),
                str(series.dtype),
                1 if series.isna().any() else 0,
                ts,
                ts,
            ),
        )
    c.commit()


def _csv_row_count(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            line_count = sum(1 for _ in handle)
        return max(0, line_count - 1)
    except OSError:
        return None


def _read_csv_frame(path, nrows=None):
    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(path, nrows=nrows, encoding=encoding)
            return frame, encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    frame = pd.read_csv(path, nrows=nrows)
    return frame, ""


def object_can_preview(obj):
    return obj and obj.get("source_type") in {"SQLITE", "CSV", "EXCEL"} and obj.get("object_type") in {"TABLE", "VIEW", "CSV_TABLE", "EXCEL_SHEET"}


def preview_object_rows(object_id, limit=200):
    obj = object_get(object_id)
    if not object_can_preview(obj):
        raise ValueError("This object type does not support row preview yet.")
    limit = max(1, min(int(limit or 200), 200))
    source = source_get(obj["data_source_id"])
    path = source.get("root_path") or source.get("database_name") or obj.get("full_path")
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(path or "No source file path configured.")
    if source["source_type"] == "SQLITE":
        return preview_sqlite_rows(path, obj["object_name"], limit)
    if source["source_type"] == "CSV":
        frame, _encoding = _read_csv_frame(path, nrows=limit)
        return dataframe_preview(frame)
    if source["source_type"] == "EXCEL":
        frame = pd.read_excel(path, sheet_name=obj["object_name"], nrows=limit)
        return dataframe_preview(frame)
    raise ValueError(f"Preview is not implemented for {source['source_type']}.")


def preview_sqlite_rows(path, table_name, limit=200):
    source_conn = sqlite_readonly_connection(path)
    safe_name = _quote_ident(table_name)
    rows_out = source_conn.execute(f"SELECT * FROM {safe_name} LIMIT ?", (limit,)).fetchall()
    col_names = [desc[0] for desc in source_conn.execute(f"SELECT * FROM {safe_name} LIMIT 0").description]
    source_conn.close()
    return {"columns": col_names, "rows": [[_preview_value(row[col]) for col in col_names] for row in rows_out]}


def dataframe_preview(frame):
    frame = frame.fillna("")
    columns = [str(col) for col in frame.columns]
    data_rows = []
    for _, row_data in frame.iterrows():
        data_rows.append([_preview_value(row_data[col]) for col in frame.columns])
    return {"columns": columns, "rows": data_rows}


def _preview_value(value):
    if value is None:
        return ""
    return str(value)


def scan_file_source(source_id):
    source = source_get(source_id)
    task_id = create_task("Scan file source", "SCAN_FILE_SOURCE", source_id=source_id)
    start_task(task_id)
    started = now()
    c = conn()
    c.execute(
        "UPDATE d_data_source SET last_scan_started_at = ?, last_scan_status = 'RUNNING' WHERE data_source_id = ?",
        (started, source_id),
    )
    try:
        root = source.get("root_path") or ""
        if not root or not os.path.isdir(root):
            raise FileNotFoundError(root or "No root path configured.")
        include_patterns = parse_patterns(source.get("include_patterns")) or default_patterns_for_type(source.get("source_type"))
        exclude_patterns = parse_patterns(source.get("exclude_patterns")) + parse_patterns(source.get("ignore_rules"))
        recursive = bool(source.get("recursive_scan"))
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            if not recursive:
                dirnames[:] = []
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)
                rel_norm = rel_path.replace("\\", "/")
                if not _matches_any(filename, rel_norm, include_patterns):
                    continue
                if exclude_patterns and _matches_any(filename, rel_norm, exclude_patterns):
                    continue
                try:
                    stat = os.stat(full_path)
                except OSError:
                    continue
                upsert_object(
                    source_id,
                    object_name=filename,
                    object_type=object_type_for_file(filename),
                    database_name="",
                    schema_name="",
                    parent_path=dirpath,
                    project=source.get("project") or "",
                    full_name=rel_norm,
                    full_path=os.path.abspath(full_path),
                    row_count=None,
                    column_count=None,
                    size_bytes=stat.st_size,
                    source_modified_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    source_created_at=datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                    metadata={"extension": os.path.splitext(filename)[1].lower()},
                )
                count += 1
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'COMPLETED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, f"Scanned {count} files.", completed, source_id),
        )
        c.commit()
        finish_task(task_id, "COMPLETED", result_summary=f"Scanned {count} files.")
    except Exception as exc:
        completed = now()
        c.execute(
            """
            UPDATE d_data_source
            SET last_scan_completed_at = ?, last_scan_status = 'FAILED',
                last_scan_message = ?, updated_at = ?
            WHERE data_source_id = ?
            """,
            (completed, str(exc), completed, source_id),
        )
        c.commit()
        finish_task(task_id, "FAILED", result_summary="File scan failed.", error_message=str(exc))
    return task_id


def upsert_object(source_id, object_name, object_type, database_name="", schema_name="", parent_path="", project="", full_name="", full_path="", row_count=None, column_count=None, size_bytes=None, source_modified_at=None, source_created_at=None, metadata=None):
    c = conn()
    ts = now()
    if full_path and object_type == "EXCEL_SHEET":
        existing = row(
            """
            SELECT data_object_id FROM d_data_object
            WHERE data_source_id = ? AND lower(full_path) = lower(?)
              AND object_name = ? AND object_type = ?
            """,
            (source_id, os.path.abspath(full_path), object_name, object_type),
        )
    elif full_path:
        existing = row(
            "SELECT data_object_id FROM d_data_object WHERE data_source_id = ? AND lower(full_path) = lower(?)",
            (source_id, os.path.abspath(full_path)),
        )
    else:
        existing = row(
            """
            SELECT data_object_id FROM d_data_object
            WHERE data_source_id = ? AND COALESCE(database_name, '') = COALESCE(?, '')
              AND COALESCE(schema_name, '') = COALESCE(?, '')
              AND object_name = ? AND object_type = ?
            """,
            (source_id, database_name, schema_name, object_name, object_type),
        )
    metadata_json = json.dumps(metadata or {}, sort_keys=True)
    if existing:
        object_id = existing["data_object_id"]
        c.execute(
            """
            UPDATE d_data_object
            SET database_name = ?, schema_name = ?, parent_path = ?, full_name = ?, full_path = ?,
                project = CASE WHEN COALESCE(project, '') = '' THEN ? ELSE project END,
                row_count = ?, column_count = ?, size_bytes = ?, last_seen_at = ?,
                last_scanned_at = ?, source_modified_at = ?, source_created_at = ?,
                metadata_json = ?, updated_at = ?
            WHERE data_object_id = ?
            """,
            (
                database_name,
                schema_name,
                parent_path,
                full_name,
                os.path.abspath(full_path) if full_path else "",
                project,
                row_count,
                column_count,
                size_bytes,
                ts,
                ts,
                source_modified_at,
                source_created_at,
                metadata_json,
                ts,
                object_id,
            ),
        )
    else:
        cur = c.execute(
            """
            INSERT INTO d_data_object(
                data_source_id, object_name, display_name, object_type, database_name, schema_name,
                parent_path, project, full_name, full_path, row_count, column_count, size_bytes,
                first_seen_at, last_seen_at, last_scanned_at, source_modified_at,
                source_created_at, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                object_name,
                object_name,
                object_type,
                database_name,
                schema_name,
                parent_path,
                project,
                full_name,
                os.path.abspath(full_path) if full_path else "",
                row_count,
                column_count,
                size_bytes,
                ts,
                ts,
                ts,
                source_modified_at,
                source_created_at,
                metadata_json,
                ts,
                ts,
            ),
        )
        object_id = cur.lastrowid
    c.commit()
    return object_id


def upsert_column(object_id, col):
    c = conn()
    ts = now()
    c.execute(
        """
        INSERT INTO d_data_column(
            data_object_id, column_name, ordinal_position, data_type, source_data_type,
            is_nullable, is_primary_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            object_id,
            col["name"],
            col["cid"] + 1,
            col["type"],
            col["type"],
            0 if col["notnull"] else 1,
            1 if col["pk"] else 0,
            ts,
            ts,
        ),
    )
    c.commit()


def overview_counts(project=None):
    source_project = " AND project = ?" if project else ""
    object_project = " AND project = ?" if project else ""
    sql_project = " AND project = ?" if project else ""
    source_params = (project,) if project else ()
    object_params = (project,) if project else ()
    sql_params = (project,) if project else ()
    return {
        "database_sources": scalar(f"SELECT COUNT(1) FROM d_data_source WHERE source_kind = 'DATABASE'{source_project}", source_params),
        "file_sources": scalar(f"SELECT COUNT(1) FROM d_data_source WHERE source_kind = 'FILE_SOURCE'{source_project}", source_params),
        "discovered_objects": scalar(f"SELECT COUNT(1) FROM d_data_object WHERE catalogue_level = 'DISCOVERED'{object_project}", object_params),
        "registered_objects": scalar(f"SELECT COUNT(1) FROM d_data_object WHERE catalogue_level = 'REGISTERED'{object_project}", object_params),
        "managed_objects": scalar(f"SELECT COUNT(1) FROM d_data_object WHERE catalogue_level = 'MANAGED'{object_project}", object_params),
        "saved_sql": scalar(f"SELECT COUNT(1) FROM d_data_saved_sql WHERE is_active = 1{sql_project}", sql_params),
        "problem_tasks": scalar(
            """
            SELECT COUNT(1)
            FROM d_data_task t
            LEFT JOIN d_data_source s ON s.data_source_id = t.data_source_id
            LEFT JOIN d_data_object o ON o.data_object_id = t.data_object_id
            LEFT JOIN d_data_saved_sql ss ON ss.saved_sql_id = t.saved_sql_id
            WHERE t.status IN ('FAILED', 'RUNNING', 'QUEUED')
            """
            + (" AND (s.project = ? OR o.project = ? OR ss.project = ?)" if project else ""),
            ([project, project, project] if project else []),
        ),
        "stale_sources": scalar(
            f"""
            SELECT COUNT(1)
            FROM d_data_source
            WHERE is_active = 1
              AND (last_scan_completed_at IS NULL OR last_scan_completed_at < datetime('now', '-30 days'))
              {source_project}
            """,
            source_params,
        ),
    }


def attention_items():
    return {
        "failing_sources": rows(
            """
            SELECT * FROM d_data_source
            WHERE is_active = 0 OR last_scan_status = 'FAILED'
            ORDER BY updated_at DESC LIMIT 10
            """
        ),
        "missing_file_sources": rows(
            """
            SELECT * FROM d_data_source
            WHERE source_kind = 'FILE_SOURCE' AND COALESCE(root_path, '') != ''
            ORDER BY updated_at DESC
            """
        ),
        "failed_tasks": rows("SELECT * FROM d_data_task WHERE status = 'FAILED' ORDER BY updated_at DESC LIMIT 10"),
    }


def recent_activity(project=None):
    source_filter = {"project": project} if project else None
    object_filter = {"project": project} if project else {}
    sql_filter = {"project": project} if project else {}
    return {
        "sources": source_list(None, source_filter)[:8],
        "objects": object_list(object_filter)[:8],
        "sql": sql_list(sql_filter)[:8],
        "tasks": tasks(limit=8, filters={"project": project} if project else None),
    }


def distinct_values(table, column):
    return [r[column] for r in rows(f"SELECT DISTINCT {column} FROM {table} WHERE COALESCE({column}, '') != '' ORDER BY {column}")]


def _checked(form, key, default=False):
    if key in form:
        return 1
    return 1 if default and form.get("_existing") != "1" else 0


def _int_or_none(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except ValueError:
        return None


def _quote_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def sqlite_readonly_connection(path):
    abs_path = os.path.abspath(path).replace("\\", "/")
    uri = "file:" + quote(abs_path, safe="/:") + "?mode=ro"
    sqlite_conn = sqlite3.connect(uri, uri=True)
    sqlite_conn.row_factory = sqlite3.Row
    return sqlite_conn


def parse_patterns(value):
    patterns = []
    for line in (value or "").replace(",", "\n").splitlines():
        line = line.strip()
        if line:
            patterns.append(line)
    return patterns


def default_patterns_for_type(source_type):
    mapping = {
        "CSV": ["*.csv"],
        "PARQUET": ["*.parquet"],
        "TEXT": ["*.txt", "*.md"],
        "JSON": ["*.json"],
        "SPREADSHEET": ["*.xlsx", "*.xls", "*.ods"],
    }
    return mapping.get(source_type or "", ["*.csv", "*.parquet", "*.txt", "*.json", "*.xlsx", "*.xls"])


def _matches_any(filename, rel_path, patterns):
    if not patterns:
        return True
    return any(fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern) for pattern in patterns)


def object_type_for_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return {
        ".csv": "CSV_FILE",
        ".parquet": "PARQUET_FILE",
        ".json": "JSON_FILE",
        ".txt": "TEXT_FILE",
        ".md": "TEXT_FILE",
        ".xlsx": "SPREADSHEET",
        ".xls": "SPREADSHEET",
        ".ods": "SPREADSHEET",
    }.get(ext, "FILE")
