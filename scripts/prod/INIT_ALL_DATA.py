#!/usr/bin/python3
# coding: utf-8
# INIT_ALL_DATA.py
import os
import sys  

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "..")

"""
INIT_ALL_DATA Instructions:
This script initializes all necessary data structures in the database.
It creates required tables and populates them with initial metadata.

MAKE SURE you backup your database first.
USAGE:
    python INIT_ALL_DATA.py <database_file>


STEPS:
1. create a new blank database
2. runs metadata file collection (skip this step if CSV's already collected)    
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


################################ IMPORTS #######################################

#root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_folder = os.path.join(root_folder, 'src', 'common')
sys.path.insert(0, src_folder)

import if_sqlite as mod_sqlite

def main():
    # REMEMBER - comment out bits you don't need to run again
    print("INIT_ALL_DATA started")
    step_01_create_db(db_file)
    # step_02_collect_filelist()   # already done

def step_01_create_db(db_file):
    print("STEP 01: Create DB and core tables if not exist")
    conn = mod_sqlite.create_connection(db_file)
    if conn is not None:
        mod_sqlite.init_core_tables(conn)
        print("Core tables created or already exist.")
    else:
        print("Error! cannot create the database connection.")

def step_02_collect_filelist():
    import filelister
    filelister.collect_raw_filelists()

def step_03_run_etl(db_file):
    print("STEP 03: Run ETL process to populate database")
    import etl_process
    etl_process.run_etl(db_file)    



if __name__ == '__main__':
    main()
