# coding: utf-8
# web_data.py    written by Duncan Murray 26/5/2014
# functions to convert data to HTML, etc for web dev
import csv
import os
import fnmatch
import time
import datetime
import pymysql
pymysql.install_as_MySQLdb()
import MySQLdb


all_tables = [
    {'nme':'as_folder',
    'cols':['id','folder'],
    'imp_cols':['folder'],
    'col_types':['id','Text'],
    'search_col':['folder'],
    'url':'folders',
    'page_function':'page_folders',
    },
    {'nme':'as_event',
     'cols':['id','dateevent_str','timeevent', 'details','event_type', 'folder'],
     'imp_cols':['dateevent_str','details'],
     'col_types':['id','Date','Time','Note','Text','List'],
     'search_col':['details','dateevent_str'],
     'url':'calendar',
       'page_function':'page_calendar',
     },
    {'nme':'as_note',  #      'cols':['id','title','pinned', 'important', 'content','folder','is_archived','is_private','is_encrypted','due_date', 'color'],
     'cols':['id','title','pinned', 'important','is_archived', 'color', 'content','folder'], #,'is_encrypted'],
     'imp_cols':['folder','title','content'],
     'col_types':['id','Text','Checkbox','Checkbox','Checkbox','Color', 'Note','List'], #'Checkbox'], #,'Checkbox','Checkbox','Checkbox', 'Date', 'Text'],
     'search_col':['title','content'],
     'url':'notes',
     'page_function':'page_notes',
    },
    {'nme':'as_task',
    'cols':['id','Title','Pinned', 'Important', 'Notes','folder','Done'],   # , 'due_date'
    'imp_cols':['folder','title','notes', 'Date'],
    'col_types':['id','Text','Checkbox','Checkbox', 'Note','List','Checkbox'],
     'search_col':['title','notes'],
    'url':'tasks',
    'page_function':'page_tasks',
    },

    {'nme':'as_task_project',
    'cols':['id','category', 'title','folder'],   # , 'due_date'
    'imp_cols':['title'],
    'col_types':['id','Number','Text','List'],
    'search_col':['title'],
    'url':'projects',
    'page_function':'page_projects',
    },
    {'nme':'as_goal',
    'cols':['id','goal_area','goal_name','goal_note'],
    'imp_cols':['goal_area','goal_name','goal_note'],
    'col_types':['id','Text','Text','Text'],
     'search_col':['goal_area','goal_name','goal_note'],
    'url':'goals',
    'page_function':'page_goals',
    },
    {'nme':'as_place',
     'cols':['id','nme'],
     'imp_cols':['nme'],
     'col_types':['id','Text'],
     'search_col':[],
     'url':'places',
     'page_function':'page_places',
    },
    {'nme':'as_money',
     'cols':['id','nme'],
     'imp_cols':['nme'],
     'col_types':['id','Text'],
     'search_col':[],
     'url':'money',
     'page_function':'page_money',
    },
    {'nme':'ref_badges',
     'cols':['badge_area', 'badge_name', 'badge_desc'],
     'imp_cols':['badge_name'],
     'col_types':['Text','Text','Text'],
     'search_col':[],
     'url':'badges',
     'page_function':'page_badges',
    },
    {'nme':'as_music',
     'cols':['id','nme'],
     'imp_cols':['nme'],
     'col_types':['id','Text'],
     'search_col':[],
     'url':'music',
     'page_function':'page_music',
    },
    {'nme':'as_images',
     'cols':['id','nme'],
     'imp_cols':['nme'],
     'col_types':['id','Text'],
     'search_col':[],
     'url':'images',
     'page_function':'page_images',
    },
    {'nme':'as_files',
     'cols':['id','nme'],
     'imp_cols':['nme'],
     'col_types':['id','Text'],
     'search_col':[],
     'url':'files',
     'page_function':'page_files',
    },
    {'nme':'as_apps',
    'cols':['id','folder','app_name','app_desc','app_launch_url', 'app_notes'],
    'imp_cols':['app_name','app_desc','app_launch_url','app_notes','folder'],
    'col_types':['id','Text','Text','Text','Text', 'Note'],
     'search_col':['app_name','app_desc','app_launch_url'],
    'url':'apps',
    'page_function':'page_apps',
    },
    {'nme':'as_data_tables', #    'cols':['id','table_name','color','folder','num_rows','num_cols', 'table_desc'],
    'cols':['id','table_name','color','folder', 'table_desc'],
    'imp_cols':['table_name','table_desc'],
    'col_types':['id','Text','Color','List','Text','Text','Text'],
     'search_col':['table_name', 'table_desc'],
    'url':'data_tables',
    'page_function':'page_data',
    },
    {'nme':'as_data_values',
    'cols':['id','table_id', 'is_header','is_hdr_short_name','is_col_type_def', 'is_default_values', 'is_row_data',
            'col1','col2','col3','col4','col5','col6','col7','col8','col9' ],
    'imp_cols':['col1','col2','col3','col4','col5','col6','col7','col8','col9'],
    'col_types':['id','Hidden','Hidden','Hidden','Hidden','Hidden','Hidden','Text','Text','Text','Text','Text','Text','Text'],
     'search_col':['col1','col2','col3','col4','col5','col6','col7','col8','col9'],
    'url':'data_values',
    'page_function':'page_data_values',
    },
    ]



# new tabs = music ♬  ☢ ☕  ☑  ✉ ⚿ 🌏 🎮 🏠 🏢     🏫  🏭 🐈 💲 📂
# badges = ✪ ✨ ✰ ✯ ✹ ❂     🏆

menu_list_ALL = [  # [route, display(nme), page]
    ['/',         '🏠',   'home',     '🏠📰 This is the main / logon page of the diary - if logged it shows overview'],
    ['/staff',    '👤',  'staff',    '☎👱  👤  Staff view - shows staff, where they are, when they are free'],
    ['/tasks',    '☑',  'tasks',    '☑✔📎🔨✘☑ ⛏ ☹     💻 💹 Tasks for staff'],
    ['/places',    '🌏️',  'places',    '🌏🛰️⛟ ⌖ ⛰    💻 💹Locations - maps, people finder'],
    ['/calendar', '🕐', 'calendar', '⌚📅 🕐 Project overview showing current list of tasks being worked on'],
    ['/notes',    '📝',  'notes',    '🗒✎📝 ✏ 🗊Team wiki page - ultra simple'], #
    ['/data',    '▦',  'data',    '▧🗒 🗊data tables'],
    ['/badges',    '🏆',  'badges',    '★ ⛤ ✵ ✭ ⚜'],
    ['/money',    '💲',  'money',    ''],
    ['/music',    '♬',  'music',    '🗒 🗊music'],
    ['/images',    '🖼',  'images',    '🗒 🗊images'],
    ['/apps',    '🎮',  'apps',    '👍 👎 '],

    ['/files',    '📂',  'files',    '🗒 🗊images and files'],
    ['/admin',    '⚿',  'admin',    'passwords'],
    ['/options',    '⚙',  'options',    'Options for LifePIM'],
    ['/about',    '⚙',  'about',    'About LifePIM']
    ]

menu_list = [  # [route, display(nme), page]
    ['/',         '🏠',   'home',     '🏠📰 This is the main / logon page of the diary - if logged it shows overview'],
    ['/calendar', '🕐', 'calendar', '⌚📅 🕐 Project overview showing current list of tasks being worked on'],
    #['/staff',    '👤',  'staff',    '☎👱  👤  Staff view - shows staff, where they are, when they are free'],
    ['/tasks',    '☑',  'tasks',    '☑✔📎🔨✘☑ ⛏ ☹ ▤    💻 💹 Tasks for staff'],
    ['/notes',    '📝',  'notes',    '🗒✎📝 ✏ 🗊Team wiki page - ultra simple'], #
    ['/images',    '🖼',  'images',    '🗒 🗊images'],
    ['/files',    '📂',  'files',    '🗒 🗊images and files'],
    ['/options',    '⚙',  'options',    'Options for LifePIM']
    ]

def get_menu_list():
    """
    Gets the menu list that the user has chosen to show
    """
    return menu_list


def tbl_default_col(tbl):
    for t in all_tables:
        if t['url'] == tbl:
            return [t['search_col'][0]]

def tbl_get_cols_as_select(tbl):
    for t in all_tables:
        if t['url'] == tbl:
            return ', '.join([c for c in t['cols']])

def tbl_get_import_cols_as_select(tbl):
    for t in all_tables:
        if t['url'] == tbl:
            return ', '.join([c for c in t['imp_cols']])


def tbl_get_cols_as_list(tbl):
    for t in all_tables:
        if t['url'] == tbl:
            return t['cols']

def tbl_get_cols_types_as_list(tbl):
    for t in all_tables:
        if t['url'] == tbl:
            return t['col_types']


def get_tbl_name(listname):
    for t in all_tables:
        if t['url'] == listname:
            return t['nme']


def get_function_name(listname):
    for t in all_tables:
        if t['url'] == listname:
            return t['page_function']
    return all_tables[3]['page_function']



def tbl_get_colval_by_name(tbl, col_data, col_name):
    """
    WARNING - this DOESNT WORK, as checkboxes are in odd orders
    """
    print('WARNING - tbl_get_colval_by_name DOESNT WORK')
    for ndx, t in enumerate(all_tables):
        if t['url'] == tbl:
            return col_data[ndx]


def get_db_conn(conn_str):
    """
    Root function that returns a DB object

    """
    return MySQLdb.connect(conn_str["host"] ,
                         user=conn_str["user"],
                         password=conn_str["pass"],
                         db=conn_str["db"],
                         charset='utf8')


def get_folder_list(fname):
    """
    returns the default list of folders
    """
    res = []
    with open(fname, 'r') as f:
        for line in f:
            if line != '':
                if line[0:1] != '#':
                    res.append(line.strip('\n'))
    return res

def get_file_list(rootPaths, lstXtn, shortNameOnly='Y'):
    """
    builds a list of files and returns as a list
    """
    numFiles = 0
    opFileList = []
    op_folder_list = []
    for rootPath in rootPaths:
        for root, dirs, files in os.walk(rootPath):
            op_folder_list.append(root)
            for basename in files:
                for xtn in lstXtn:
                    if fnmatch.fnmatch(basename, xtn):
                        filename = os.path.join(root, basename)
                        numFiles = numFiles + 1
                        if shortNameOnly == 'Y':
                            opFileList.append( os.path.basename(filename))
                        else:
                            opFileList.append(filename)

    return sorted(opFileList), sorted(op_folder_list)

def get_user():
    try:
        user = session['username']
    except:
        user = ''
    return user


def today_as_string():
    """
    returns current date and time like oracle
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def today_as_string_web():
    """
    current date and time with underscores for web filename
    """
    return time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime())

def get_date_from_str(datestring):
    """
    find a date from string
    """

    import dateutil.parser
    return dateutil.parser.parse(datestring)


def read_csv_to_list2(filename):
    """
    reads a CSV file to a list
    """
    import csv

    rows_to_load = []
    with open(filename, 'r', encoding='cp1252') as csvfile: # sort of works with , encoding='cp65001'
        #csvreader = csv.reader(csvfile, delimiter = ',' )

        reader = csv.reader(csvfile)

        rows_to_load = list(reader)
    return rows_to_load[1:]

def read_csv_to_list(filename):
    """
    reads a CSV file to a list
    """

    rows_to_load = []
    with open(filename, 'r', encoding='utf-8', errors='replace') as csvfile: 
        csvreader = csv.reader(csvfile, delimiter = ',' )

        reader = csv.reader(csvfile)

        rows_to_load = list(reader)
    return rows_to_load

def secure_filename(filename):
    """
    strips out path componants
    """
    return filename.strip('../').strip('..\\')



def get_table_as_list(user_id, cols, tbl, where_clause, params_as_list, conn_str, order_by="1", maxrows='20000'):
    """
    This should be the ONLY place that selects for the network diary
    """
    res = []

    return res

def get_ref_table_as_list(cols, tbl, conn_str, order_by="1", maxrows='2000'):
    """
    Straight select from a reference table, no user passed where clauses
    SELECT username,  DATE_FORMAT(join_date, '%Y-%m-%d') FROM sys_user ORDER BY join_date desc  LIMIT 5

    """

    res = []
    return res


def get_record_and_header(user_id, listname, id, conn_str):
    """
    For edit functionality - returns the list of columns and the single record data
    """
    if user_id < 1:
        print('ERROR trying to access data id#' + str(id) + ' with invalid user_id ', user_id, ' into table ', listname)
        return [], []

    tbl = get_tbl_name(listname)
    cols = tbl_get_cols_as_list(listname)
    cols_str = tbl_get_cols_as_select(listname)
    #print('returns tbl = ', tbl, ' cols = ', cols)

    res = get_table_as_list(user_id, cols_str, tbl, "id = %s ", [id] , conn_str)
    #print('get_record_and_header res = ', res)
    #record[4] = record[4].replace('\n', '<BR>')

    rec = []
    #if res == []:    # happens when you archive a note
    #    return [],[]
    #print('acute_web_data : res = ', res)
    if res:
        for r in res[0]:
            if type(r) == str:
                rec.append(r)#.replace('\n', '<BR>'))
            else:
                rec.append(r)

    return cols, rec

