#!/usr/bin/python3
# coding: utf-8
# init_database.py - rebuilds the local sqlite database from table_def

import os, sys, sqlite3, subprocess
import etl_folder_mapping as folder_etl
import common.config as cfg
from common import projects as projects_mod
from common.media_schema import ensure_media_schema
from lifepim.importer.schema import ensure_import_schema
def main():
    reset_database(cfg.DB_FILE)
    _run_load_testing()
    _run_folder_mapping()
    _run_projects_import()
    print(f"Initialized database at {cfg.DB_FILE}")



##############################
## INIT DATABASE

def reset_database(db_file):
    """
    DROPS and recreates the SQLite database 'db_file'
    Then creates all tables from config.py : table_def
    """
    if os.path.exists(db_file):
        os.remove(db_file)
    db_conn = sqlite3.connect(db_file)
    for tbl in cfg.table_def:
        if tbl.get("name") == "lp_media":
            continue
        create_table(db_conn, tbl)
    db_conn.executescript(folder_etl.DDL_RESET)
    projects_mod.ensure_projects_schema(db_conn)
    _run_sql_script(db_conn, os.path.join(os.path.dirname(__file__), "schema_contacts.sql"))
    _run_sql_script(db_conn, os.path.join(os.path.dirname(__file__), "schema_links.sql"))
    _run_sql_script(db_conn, os.path.join(os.path.dirname(__file__), "schema_money.sql"))
    ensure_media_schema(db_conn)
    ensure_import_schema(db_conn)
    db_conn.commit()
    db_conn.close()


def create_table(db_conn, tbl):
    # {'name':'lp_notes', 'display_name':'Notes', 'col_list':['file_name','path','size','date_modified','project']},
    # also include standard columns
    col_defs = []
    for col in tbl["col_list"]:
        col_type = "TEXT"
        if "date" in col.lower():
            col_type = "TEXT"
        col_defs.append(f"{col} {col_type}")

    col_defs.extend(["user_name TEXT", "rec_extract_date TEXT"])
    sql = (
        f"CREATE TABLE IF NOT EXISTS {tbl['name']} ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        f"{', '.join(col_defs)})"
    )
    db_conn.execute(sql)
    if tbl.get("route") in {"notes", "media", "audio", "3d", "files", "apps"}:
        db_conn.execute(
            f"CREATE INDEX IF NOT EXISTS ix_{tbl['name']}_folder_id ON {tbl['name']}(folder_id)"
        )


def _run_sql_script(db_conn, script_path):
    if not os.path.exists(script_path):
        print(f"SQL script not found: {script_path}")
        return
    with open(script_path, "r", encoding="utf-8") as handle:
        script = handle.read()
    if script.strip():
        db_conn.executescript(script)


def _run_load_testing():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(repo_root, "tests", "LOAD_TESTING.py")
    if not os.path.exists(script_path):
        print(f"LOAD_TESTING.py not found: {script_path}")
        return
    print("Running load testing script...")
    subprocess.check_call([sys.executable, script_path])


def _run_folder_mapping():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(repo_root, "src", "etl_folder_mapping.py")
    if not os.path.exists(script_path):
        print(f"etl_folder_mapping.py not found: {script_path}")
        return
    folders_csv = getattr(cfg, "etl_folders_csv", "")
    rules_csv = getattr(cfg, "etl_rules_csv", "")
    if not os.path.exists(folders_csv):
        print(f"Folders CSV not found: {folders_csv}")
        return
    if not os.path.exists(rules_csv):
        print(f"Rules CSV not found: {rules_csv}")
        return
    print("Running folder mapping ETL...")
    subprocess.check_call(
        [
            sys.executable,
            script_path,
            "--db",
            cfg.DB_FILE,
            "--folders_csv",
            folders_csv,
            "--rules_csv",
            rules_csv,
        ]
    )


def _run_projects_import():
    rules_csv = getattr(cfg, "etl_rules_csv", "")
    if not rules_csv or not os.path.exists(rules_csv):
        print(f"Project rules CSV not found: {rules_csv}")
        return
    print("Importing projects + project folders...")
    try:
        projects_mod.import_project_mappings_csv(rules_csv)
        updated = projects_mod.assign_defaults_if_missing()
        if updated:
            print(f"Assigned default folders for {updated} projects.")
        issues = projects_mod.diagnose_projects()
        missing = issues.get("missing_default") or []
        if missing:
            print(f"Projects missing default folder: {len(missing)}")
        disabled = issues.get("disabled_default") or []
        if disabled:
            print(f"Projects with disabled default folder: {len(disabled)}")
        multi = issues.get("multiple_default") or []
        if multi:
            print(f"Projects with multiple default folders: {len(multi)}")
    except Exception as exc:
        print(f"Project import failed: {exc}")


if __name__ == "__main__":
    main()
