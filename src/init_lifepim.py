#!/usr/bin/python3
# coding: utf-8
# init_lifepim.py

import config as mod_cfg
import sqlite3

cols_diary_raw = [
    'id',
    'date',
    'reference',
    'time',
    'details',
    'length',
    'ActionID',
    'ContactID',
    'UrlID',
    'JobToDoID',
    'RemindDate',
    'RemindTime',
    'Priority',
    'status',
    'ActionToPerform'
]

# initialise database

con = sqlite3.connect(mod_cfg.db_name)
cur = con.cursor()


cur.execute('drop table if exists diary_raw')
cur.execute('''CREATE TABLE diary_raw (id text, date text, reference text, time text, length text, ActionID text, ContactID text, UrlID text, JobToDoID text, RemindDate text, RemindTime text, Priority text, status text, ActionToPerform text, details text)''')

cur.execute('drop table if exists diary_file_usage')
cur.execute('''CREATE TABLE diary_file_usage (id text, date text,  time text, ContactID text, details text)''')

cur.execute('drop table if exists diary_pc_usage')
cur.execute('''CREATE TABLE diary_pc_usage (id text, date text,  time text, length text, details text)''')

cur.execute('drop table if exists diary_events')
cur.execute('''CREATE TABLE diary_events (id text, date text, reference text, time text, length text, ActionID text, ContactID text, UrlID text, JobToDoID text, RemindDate text, RemindTime text, Priority text, status text, ActionToPerform text, details text)''')


