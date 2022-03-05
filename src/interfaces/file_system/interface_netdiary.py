#!/usr/bin/python3
# coding: utf-8
# interface_netdiary.py
# This module is for importing data files from Acute Softwares Diary
# into the standard LifePIM database.
import os
import sys
import time 
import glob
import sqlite3

import aikif.lib.cls_filelist as mod_fl

path_root =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." ) 
sys.path.append(str(path_root))

import config as mod_cfg


path_diary = r"U:\acute\netDiary\data"
output_folder = mod_cfg.user_folder
db_name = mod_cfg.db_name

def TEST():
    load_diary_to_raw_tables()
    ETL_raw_diary()
    query_diary()


def query_diary():
    db = DataBase(db_name)

    # Reference = [('Edit', 464261), ('PCFile', 358052), ('', 13469), ('View', 11530), ('Autobackup', 2640), ('general', 1164), ('Note', 776), ('Meeting', 144), ('Public', 82),
    sql = 'select Reference, count(*) , max(date) from diary_raw GROUP BY Reference  having count(*) > 3 ORDER BY 2 desc'

    # ActionID = [('PCFile', 404636), ('Usage', 313051), ('', 13768), ('Batch', 2349), ('General Reminder', 343), ('Timer', 49), ('General Multiday Event', 38),
    sql = 'select ActionID, count(*) from diary_raw GROUP BY ActionID  having count(*) > 3 ORDER BY 2 desc'

    # Year = [('2005', 142451), ('2007', 132632), ('2006', 109286), ('2003', 94206), ('2002', 90337), ('2004', 88333),
    sql = 'select substr(date, 1,4) as YR, count(*) from diary_raw GROUP BY substr(date, 1,4)  having count(*) > 3 ORDER BY 1 desc'

    # ContactID = [('', 373435), ('C:\\Program Files\\acute\\autobackupPro\\events.log', 1376), ('C:\\Program Files\\acute\\autobackupPro\\copied.txt', 1068), 
    sql = 'select ContactID, count(*) from diary_raw GROUP BY ContactID ORDER BY 2 desc limit 10'

    # UrlID = [('', 852734),
    sql = 'select UrlID, count(*) from diary_raw GROUP BY UrlID ORDER BY 2 desc limit 10'

    # JobToDoID = [('', 850723), ('20020422', 24), ('20020421', 18), ('20020425', 18), 
    sql = 'select JobToDoID, count(*) from diary_raw GROUP BY JobToDoID ORDER BY 2 desc limit 10'

    # Priority = [('', 734419), ('1', 67), ('3', 6), ('2', 4), 
    sql = 'select Priority, count(*) from diary_raw GROUP BY Priority ORDER BY 2 desc limit 10'

    # status = [('', 733203), ('Private', 842), ('Public', 367), ('Completed', 85), 
    sql = 'select status, count(*) from diary_raw GROUP BY status ORDER BY 2 desc limit 10'

    # ActionToPerform = [('', 733978), ('Multiday Reminder', 245), ('Multiday Event', 153), ('Home Office', 21), 
    sql = 'select ActionToPerform, count(*) from diary_raw GROUP BY ActionToPerform ORDER BY 2 desc limit 10'

    #sql = "select * from diary_raw WHERE reference = 'PCFile' and length(ContactID) < 2 limit 10"

    # Run the SQL
    db.exec(sql)
    print(db.cur.fetchall())

def load_diary_to_raw_tables():    
    """
    imports data from Acute Softwares Network Diary
    """
    print('reading diary files from = ' + path_diary)
    print('saving output to         = ' + db_name)

    # read the source files
    fles = NetDiaryCollection(path_diary)
    fles.get_diary_file_list()

    # setup database for output
    db = DataBase(db_name)
    for diary_file in fles.diary_files:
        print('Processing ' + diary_file)
        diary_data = NetDiaryFile(diary_file)
        diary_data.read_to_list()
        if len(diary_data.raw_data) > 0:
            diary_data.save_data_to_lifepim(db)

    
    print(fles)

def ETL_raw_diary():
    """
    uses the raw table in the database to populate dimensions and facts
    for space saving, and to split info into appropriate tables for lifepim.
    This reads from the DIARY_RAW table and populates the tables below:

    diary_file_usage (id, date,  time, ContactID, details)
    diary_pc_usage (id, date,  time, length, details)
    """
    db = DataBase(db_name)
    db.exec('''DELETE FROM diary_pc_usage''')
    db.exec('''INSERT INTO diary_pc_usage SELECT 'na', date, time, length, details FROM diary_raw WHERE ActionID = 'Usage' ''')

    db.exec('''DELETE FROM diary_file_usage''')
    db.exec('''INSERT INTO diary_file_usage SELECT 'na', date, time, UrlID, details FROM diary_raw WHERE ActionID = 'PCFile' ''')
 
    db.exec('''DELETE FROM diary_events''')
    db.exec('''INSERT INTO diary_events SELECT * FROM diary_raw WHERE ActionID NOT IN ('PCFile', 'Usage') ''')


 
    print('================================== PC USAGE ========================')
    db.exec('SELECT * FROM diary_pc_usage LIMIT 10')
    print(db.cur.fetchall())

    print('================================== FILE USAGE ========================')
    db.exec('SELECT * FROM diary_file_usage LIMIT 10')
    print(db.cur.fetchall())

    print('================================== General Events ========================')
    db.exec('SELECT * FROM diary_events LIMIT 10')
    print(db.cur.fetchall())



class DataBase(object):
    def __init__(self, dbname):
        self.dbname = dbname
        self.con = sqlite3.connect(self.dbname)
        self.cur = self.con.cursor()

    def exec(self, sql_text):
        self.cur.execute(sql_text)
        self.con.commit()
        
    def close(self):
        self.con.close()




class NetDiaryCollection(object):
    """
    manages a folder containing a number of diary files
    """
    def __init__(self, fldr_name):
        self.fldr_name = fldr_name
        self.diary_files = []
    
    def __str__(self):
        return str(len(self.diary_files)) + ' Diary Files in ' + self.fldr_name

    def get_diary_file_list(self):
        """
        refresh the list of files in the folder
        """
        self.diary_files = glob.glob(os.path.join(self.fldr_name,'D*.dat'))

class NetDiaryFile(object):
    """
    manages a single diary file in a collection
    """        
    def __init__(self, fname):
        self.fname = fname
        self.raw_data =[]

    def __str__(self):
        return self.fname

    def read_to_list(self):
        """
        reads in the diary file as a list
        """
        self.raw_data =[]
        col_data = []
        try:
            with open(self.fname, 'r',encoding="utf8") as fip:
                for line in fip:
                    line = line.strip('\n')
                    col_data = line.split(chr(31))
                    #print(col_data)
                    self.raw_data.append(col_data[:-1])   # 
        except Exception as ex:
            print(self.fname + ' couldnt be read : ' + str(ex))

    def save_data_to_lifepim(self, db):
        """
        the raw file has been read into this object, and this 
        saves to the passed database object 'db' which needs
        the standard table name diary_raw to exist
        (make sure you run init_lifepim from src before this)
        """

        #print(self.raw_data[0:1])
        try:
            db.cur.executemany("insert into diary_raw values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", self.raw_data)
            db.exec('commit')
        except Exception as ex:
            print(self.fname + ' couldnt be loaded : ' + str(ex))



def lg(tpe, txt):
    with open(os.path.join(output_folder, 'filelist.log'), 'a') as f:
        f.write(dte() + ',' + tpe + ',' + txt + '\n')

def dte():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

if __name__ == '__main__':
    TEST()


