#!/usr/bin/python3
# coding: utf-8
# INIT_ALL_DATA.py
import os
import sys  
import pandas as pd
import sqlite3
import unicodedata

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "..")

"""
INIT_ALL_DATA Instructions:
This script initializes all necessary data structures in the database.
It creates required tables and populates them with initial metadata.

MAKE SURE you backup your database first.
USAGE:
    python INIT_ALL_DATA.py <database_file>


STEPS:
1. Check paths and locations for databases, backup first if needed
2. run metadata file collection MANUALLY  (python ./filelister.py)
3. runs the ETL for new databases
4. ETL loads the filelist CSVs and builds aggregates
5. adds tables for UI for Lifepim (widgets, tabs, side_tabs)

"""

sample_data = 'Y'
short_dbname = 'lifepim.db'

if sample_data == 'Y':
    op_folder = root_folder + os.sep + 'data'
else:
    op_folder = r'\\FANGORN\user\duncan\LifePIM_Data\DATA\SQL'

db_file = os.path.join(op_folder, short_dbname)

print('Output folder set to: ' + op_folder)
print('Database file set to: ' + db_file)


################################ LOCAL IMPORTS #######################################

#root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_folder = os.path.join(root_folder, 'src', 'common')
sys.path.insert(0, src_folder)

import if_sqlite
import table_definitions as mod_tbl_defs

################################ DEFINITIONS #######################################

db_file = r'C:\DATA\LifePIM_cache\lifepim_etl.db'
db_img = r'C:\DATA\LifePIM_cache\lp_images.db'

#db_file = r'N:\duncan\LifePIM_Data\DATA\SQL\lifepim_etl.db'
#db_img = r'N:\duncan\LifePIM_Data\DATA\SQL\lp_images.db'

def main():
    
    #rebuild_lifepim_etl()
    #rebuild_images_db()
    fix_paths()
    show_summary()
    print('ALL DONE')



def fix_paths():
    """
    Fix paths in the database to be normalized
    """
    import time
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    sql = "SELECT id, path FROM c_filelist_files WHERE path NOT LIKE 'C:%'"
    cur.execute(sql)
    rows = cur.fetchall()
    total = len(rows)

    print(f"Found {total} paths to normalize.")

    processed = 0
    failed = 0

    for i, (rec_id, path) in enumerate(rows, start=1):
        norm_path = normalize_path(path)

        try:
            cur.execute("UPDATE c_filelist_files SET path = ? WHERE id = ?", (norm_path, rec_id))
        except Exception as ex:
            failed += 1
            print(f"Failed {i}/{total}: {path} — {ex}")
            continue

        processed += 1
        if processed % 500 == 0:
            conn.commit()
            print(f"{processed}/{total} paths committed...")

    conn.commit()
    cur.close()
    conn.close()

def normalize_path(p):
    # Normalize Unicode
    p = unicodedata.normalize('NFC', p)
    # Collapse multiple spaces
    p = ' '.join(p.split())
    return p


def show_summary():
    conn = sqlite3.connect(db_file)
    sql_tbls = "SELECT name FROM sqlite_master WHERE type='table'"
    res = if_sqlite.get_data(conn, sql_tbls, '')
    tbl_stats = []
    for tbl in res:
        if tbl[0]:
            sql = "SELECT '" + tbl[0] + "' as table_name, count(*) as num_recs FROM " +  tbl[0]
            tmp_res = if_sqlite.get_data(conn, sql, '')
            tbl_stats.append(tmp_res)

    for t in tbl_stats:
        print(t)

def rebuild_lifepim_etl():

    print('WARNING - this takes 10-15 minutes if building over NAS - press Enter to continue or <CTL><BRK> to cancel')
    x = input()
    
    try:
        os.remove(db_file)
    except:
        pass
    if_sqlite.create_database(db_file)
    conn = sqlite3.connect(db_file)
    setup_tables(conn)
    define_jobs(conn)
    run_etl(conn)


def rebuild_images_db():
    """
    This recreates the filelist database and copies basic
    images table from main database, so you can then
    populate the thumbnails using "img_add_thumbnails"
    """
    import time
    img_tbl =     ['c_filelist_image', 'Photos List', 'file_name, path', 'file_name, path, size, date, width, length, GPS, thumbnail', ['size', 'width', 'length'], [], ['thumbnail']]
    try:
        os.remove(db_img)
    except:
        pass
    if_sqlite.create_database(db_img)
    conn_img = sqlite3.connect(db_img)
    if_sqlite.init_metadata_tables(conn_img)
    if_sqlite.create_table_from_definition(conn_img, img_tbl)
    conn_img.close()
    print('Created images database : ' + db_img)
    time.sleep(1)

    src_conn = sqlite3.connect(db_file)

    src_conn.execute("ATTACH DATABASE ? AS db2", (db_img,))
    sql_copy = "INSERT INTO db2.c_filelist_image SELECT * FROM main.c_filelist_image WHERE path NOT like 'C:%'"
    src_conn.execute(sql_copy)
    src_conn.commit()
    src_conn.close

    print('Copied data images to new database : ' + db_img)
    print('To add thumbnails and ML tagging, run img_add_thumnails.py')


def setup_tables(conn):
    if_sqlite.init_metadata_tables(conn)  # defines the table definitions

    for tbl in mod_tbl_defs.def_lp_tables:
        if_sqlite.create_table_from_definition(conn, tbl)


def define_jobs(conn):
    if_sqlite.lg(conn, if_sqlite.LOG_DATA, 'defining jobs')
    for job in mod_tbl_defs.def_lp_jobs:
        if_sqlite.job_create(conn, job[0], job[1], job[2], job[3])

    for step in mod_tbl_defs.def_lp_job_steps:  # job_id, step_num, job_type, src_tbl, dest_tbl, details, sql_to_run
        #print('adding step = ' + str(step))
        if_sqlite.job_add_step(conn, step[0],step[1],step[2],step[3],step[4], step[5], step[6], step[7], step[8])

def run_etl(conn):
    if_sqlite.lg(conn, if_sqlite.LOG_DATA, 'running ETL jobs')

    if_sqlite.run_all_jobs(conn)




if __name__ == '__main__':
    main()
