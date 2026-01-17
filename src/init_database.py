#!/usr/bin/python3
# coding: utf-8
# init_database.py - rebuilds the local sqlite database from table_def

import os, sys, sqlite3
import common.config as cfg
def main():
    reset_database(cfg.DB_FILE)
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
        create_table(db_conn, tbl)
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


if __name__ == "__main__":
    main()
