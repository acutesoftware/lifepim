#!/usr/bin/python3
# coding: utf-8
# test_data_tables.py
#
# Informational database dump for LifePIM SQLite files. This intentionally does
# not assert on table contents; it prints row counts and column lists for quick
# inspection during development.

import os
import sqlite3
import sys
import unittest
from urllib.parse import quote


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import config as cfg


def _sqlite_readonly_uri(db_path):
    abs_path = os.path.abspath(db_path).replace("\\", "/")
    return "file:" + quote(abs_path, safe="/:") + "?mode=ro"


def _connect_readonly(db_path):
    conn = sqlite3.connect(_sqlite_readonly_uri(db_path), uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _quote_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _is_sqlite_file(db_path):
    if not db_path or not os.path.isfile(db_path):
        return False
    try:
        conn = _connect_readonly(db_path)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        conn.close()
        return True
    except sqlite3.Error:
        return False


def _table_rows(conn):
    return conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    ).fetchall()


def _table_columns(conn, table_name):
    return conn.execute(f"PRAGMA table_info({_quote_ident(table_name)})").fetchall()


def _row_count(conn, table_name, table_type):
    if table_type != "table":
        return "view"
    try:
        row = conn.execute(f"SELECT COUNT(1) AS cnt FROM {_quote_ident(table_name)}").fetchone()
        return row["cnt"] if row else 0
    except sqlite3.Error as exc:
        return f"ERROR: {exc}"


def _config_database_paths():
    paths = []
    for name in dir(cfg):
        if name.startswith("_"):
            continue
        if "db" not in name.lower():
            continue
        try:
            value = getattr(cfg, name)
        except Exception:
            continue
        if isinstance(value, str) and value.lower().endswith((".db", ".sqlite", ".sqlite3")):
            paths.append((f"config.{name}", value))
    return paths


def _life_pim_data_database_paths(main_db_path):
    if not _is_sqlite_file(main_db_path):
        return []
    conn = _connect_readonly(main_db_path)
    try:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_data'"
        ).fetchone()
        if not table:
            return []
        rows = conn.execute(
            "SELECT id, name, tbl_name FROM lp_data "
            "WHERE lower(tbl_name) LIKE '%.db' "
            "OR lower(tbl_name) LIKE '%.sqlite' "
            "OR lower(tbl_name) LIKE '%.sqlite3' "
            "ORDER BY name, tbl_name"
        ).fetchall()
        return [
            (f"lp_data id={row['id']} name={row['name']}", row["tbl_name"])
            for row in rows
            if row["tbl_name"]
        ]
    finally:
        conn.close()


def _discover_database_paths():
    discovered = []
    seen = set()

    def add(label, path):
        if not path:
            return
        abs_path = os.path.abspath(path)
        key = os.path.normcase(abs_path)
        if key in seen:
            return
        seen.add(key)
        discovered.append((label, abs_path))

    for label, path in _config_database_paths():
        add(label, path)

    main_db_path = getattr(cfg, "DB_FILE", getattr(cfg, "db_name", ""))
    for label, path in _life_pim_data_database_paths(main_db_path):
        add(label, path)

    return discovered


def _dump_database(label, db_path):
    print("")
    print("=" * 100)
    print(f"DATABASE: {label}")
    print(f"PATH:     {db_path}")

    if not os.path.exists(db_path):
        print("STATUS:   missing")
        return
    if not _is_sqlite_file(db_path):
        print("STATUS:   not a readable SQLite database")
        return

    conn = _connect_readonly(db_path)
    try:
        table_rows = _table_rows(conn)
        print(f"STATUS:   readable")
        print(f"OBJECTS:  {len(table_rows)} tables/views")

        for table in table_rows:
            table_name = table["name"]
            table_type = table["type"]
            count = _row_count(conn, table_name, table_type)
            columns = _table_columns(conn, table_name)
            print("")
            print(f"{table_type.upper()}: {table_name}")
            print(f"ROWS:  {count}")
            print("COLUMNS:")
            for col in columns:
                pk = " PK" if col["pk"] else ""
                required = " NOT NULL" if col["notnull"] else ""
                default = f" DEFAULT {col['dflt_value']}" if col["dflt_value"] is not None else ""
                print(f"  - {col['name']} {col['type']}{required}{default}{pk}".rstrip())
    finally:
        conn.close()


class TestDataTables(unittest.TestCase):
    def test_dump_database_table_info(self):
        database_paths = _discover_database_paths()
        print("")
        print("LifePIM database table info")
        print(f"Discovered database files: {len(database_paths)}")

        for label, db_path in database_paths:
            _dump_database(label, db_path)

        if not database_paths:
            print("No configured database files discovered.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
