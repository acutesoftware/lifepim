# table_definitions.py
# written by Duncan Murray 2025-11-08



def_lp_tables = [ # [table_name, description, grain_cols, col_list, cols_INT, cols_REAL, cols_BLOB]
    # CREATED AUTOMATICALLY ['s_filelist_raw', 'List of Raw files', 'fullFilename', 'fullFilename, name, path, size, date, dummy', ['size'], [], []],
    ['c_filelist_paths', 'List of file Paths', 'path', 'path, tot_size, num_files', ['tot_size', 'num_files'], [], []],
    ['c_filelist_xtns', 'List of file Extentions', 'xtn', 'xtn, tot_size, num_files, type, area', ['tot_size', 'num_files'], [], []],
    ['c_filelist_files', 'List of files', 'file_name, path', 'file_name, path, size, date, xtn, type, area, is_master', ['size'], [], []],
    ['c_filelist_audio', 'Audio files', 'file_name, path', 'file_name, path, size, date, author, album, track, length', ['size'], [], []],
    ['c_filelist_image', 'Photos List', 'file_name, path', 'file_name, path, size, date, width, length, GPS, thumbnail', ['size', 'width', 'length'], [], ['thumbnail']],
    ['c_filelist_text', 'Text Files', 'file_name, path', 'file_name, path, size, date, content, lines, preview', ['size', 'lines'], [], ['content']],
    ['c_filelist_user', 'User Files', 'file_name, path', 'file_name, path, size, date, tags, preview', ['size'], [], []],

]

def_lp_jobs = [ # proj_id, job_num, job_id, details
    ['FL', 1, 'LOAD_RAW_FILELIST', 'Loads raw filelist from CSV'],
    ['FL', 2, 'AGG_FILE_PATHS', 'Creates Path dimension from raw filelist'],

]


def_lp_job_steps = [ # job_id, job_num, step_num, job_type, details, sql_to_run
    

    [ 'LOAD_REF', 0, 1, 'CSV', r'N:\duncan\LifePIM_Data\configuration\r_map_xtn.csv', '', 'Load ref file CSV files into own tables', '', ''],
    [ 'LOAD_REF', 0, 2, 'CSV', r'N:\duncan\LifePIM_Data\configuration\r_xtn_filetype.csv', '', 'Load file type descriptions', '', ''],
    [ 'LOAD_REF', 0, 3, 'CSV', r'N:\duncan\LifePIM_Data\configuration\r_map_fav_folders.csv', '', 'Load Fav Folder descriptions', '', ''],
    [ 'LOAD_REF', 0, 4, 'CSV', r'N:\duncan\LifePIM_Data\configuration\ontology.csv', '', 'Ref Ontology', '', ''],

    [ 'LOAD_REF', 0, 5, 'CSV', r'N:\duncan\C\user\dev\src\python\AIKIF\aikif\data\ref\map_pc_usage.csv', '', 'Map PC Usage (old)', '', ''],
    [ 'LOAD_REF', 0, 6, 'CSV', r'N:\duncan\C\user\dev\src\python\AIKIF\aikif\data\ref\rules_columns_maps.csv', '', 'Column mapping rules (old)', '', ''],
    [ 'LOAD_REF', 0, 7, 'CSV', r'N:\duncan\C\user\dev\src\python\AIKIF\aikif\data\ref\toolbox.csv', '', 'AIKIF Toolbox (old)', '', ''],

    [ 'LOAD_REF', 0, 8, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\ui_tabs.csv', '', 'UI Top Tabs', '', ''],
    [ 'LOAD_REF', 0, 9, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\ui_sidetabs.csv', '', 'UI Side Tabs', '', ''],
    [ 'LOAD_REF', 0, 10, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\sys_lp_cat_widgets.csv', '', 'Widgets', '', ''],
    [ 'LOAD_REF', 0, 11, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\sys_lp_cols.csv', '', 'LifePIM Cols', '', ''],

    [ 'LOAD_REF', 0, 12, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\ref_project.csv', '', 'Projects Ref', '', ''],
    [ 'LOAD_REF', 0, 13, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\d_apps.csv', '', 'data - apps', '', ''],
    [ 'LOAD_REF', 0, 14, 'CSV', r'N:\duncan\C\user\dev\src\python\LifePIM_public\data\d_note.csv', '', 'data - notes', '', ''],


    [ 'LOAD_RAW_FILELIST', 1, 1, 'CSV', r'N:\duncan\LifePIM_Data\index\raw_treebeard_*.csv', '', 'Load multiple CSV files into own tables', '', ''],
    [ 'LOAD_RAW_FILELIST', 1, 2, 'CREATE_FROM_MULT', 'raw_treebeard_%', 's_filelist_raw', 'Create table from  multiple tables', '', ''],

    [ 'LOAD_FILE_MASTER', 2, 1, 'DEL', '', 'c_filelist_files', 'clean dest table', 'DELETE FROM c_filelist_files', ''],
    [ 'LOAD_FILE_MASTER', 2, 2, 'INS', 's_filelist_raw', 'c_filelist_files', 'agg path list', 'INSERT INTO c_filelist_files (file_name, path, size, date) SELECT name, path, size, date FROM s_filelist_raw', ''],
    [ 'LOAD_FILE_MASTER', 2, 3, 'UPD', '', 'c_filelist_files', 'get XTN from filename', "UPDATE c_filelist_files SET xtn = substr(file_name, instr(file_name, '.')+1, 17)", ''],
    [ 'LOAD_FILE_MASTER', 2, 4, 'UPD', '', 'c_filelist_files', 'file XTN for multiple .', "UPDATE c_filelist_files SET xtn = substr(xtn, -3) where xtn like '%.%'", ''],

    [ 'LOAD_FILE_MASTER', 2, 5, 'UPD', '', 'c_filelist_files', 'classify file types', 'UPDATE c_filelist_files set type = (SELECT r_map_xtn.maps_to FROM r_map_xtn where r_map_xtn.xtn = c_filelist_files.xtn)', ''],


    [ 'AGG_FILE_XTN', 3, 1, 'DEL', '', 'c_filelist_xtns', 'clean dest table', 'DELETE FROM c_filelist_xtns', ''],
    [ 'AGG_FILE_XTN', 3, 2, 'INS', 'c_filelist_files', 'c_filelist_xtns', 'agg xtn list', "INSERT INTO c_filelist_xtns (xtn, tot_size, num_files) SELECT xtn, sum(size) as tot_size, count(*) as num_files FROM c_filelist_files group by xtn", ''],

    [ 'AGG_FILE_PATHS', 4, 1, 'DEL', '', 'c_filelist_paths', 'clean dest table', 'DELETE FROM c_filelist_paths', ''],
    [ 'AGG_FILE_PATHS', 4, 2, 'INS', 's_filelist_raw', 'c_filelist_paths', 'agg path list', 'INSERT INTO c_filelist_paths (path, tot_size, num_files) SELECT path, sum(size) as tot_size, count(*) as num_files FROM s_filelist_raw group by path', ''],

    [ 'AGG_FILE_IMAGE', 5, 1, 'DEL', '', 'c_filelist_image', 'clean dest table', 'DELETE FROM c_filelist_image', ''],
    [ 'AGG_FILE_IMAGE', 5, 2, 'INS', 'c_filelist_files', 'c_filelist_image', 'agg list audio', 'INSERT INTO c_filelist_image (file_name, path, size, date) SELECT file_name, path, size, date FROM c_filelist_files WHERE type = ?', '''I'''],

    [ 'AGG_FILE_AUDIO', 6, 1, 'DEL', '', 'c_filelist_audio', 'clean dest table', 'DELETE FROM c_filelist_audio', ''],
    [ 'AGG_FILE_AUDIO', 6, 2, 'INS', 'c_filelist_files', 'c_filelist_audio', 'agg list audio', '''INSERT INTO c_filelist_audio (file_name, path, size, date) SELECT file_name, path, size, date FROM c_filelist_files WHERE type = ?''', '''A'''],

    [ 'AGG_FILE_TEXT', 6, 1, 'DEL', '', 'c_filelist_text', 'clean dest table', 'DELETE FROM c_filelist_text', ''],
    [ 'AGG_FILE_TEXT', 6, 2, 'INS', 'c_filelist_files', 'c_filelist_text', 'agg list Text from Text', '''INSERT INTO c_filelist_text (file_name, path, size, date) SELECT file_name, path, size, date FROM c_filelist_files WHERE type = ?''', '''T'''],
    [ 'AGG_FILE_TEXT', 6, 3, 'INS', 'c_filelist_files', 'c_filelist_text', 'agg list Text from Code', '''INSERT INTO c_filelist_text (file_name, path, size, date) SELECT file_name, path, size, date FROM c_filelist_files WHERE type = ?''', '''C'''],


]



sql_create_sys_log = """ CREATE TABLE IF NOT EXISTS sys_log (
                                        id integer PRIMARY KEY,
                                        log_date text,
                                        log_level integer,
                                        details text NOT NULL
                                        
                                    ); """

sql_create_sys_meta_tables = """ CREATE TABLE IF NOT EXISTS sys_meta_tables (
                                        id integer PRIMARY KEY,
                                        table_name text NOT NULL,
                                        description text,
                                        grain_cols text,
                                        col_list text,
                                        rec_extract_date text
                                        
                                    ); """

sql_create_sys_meta_table_columns = """ CREATE TABLE IF NOT EXISTS sys_meta_table_columns (
                                        id integer PRIMARY KEY,
                                        table_name text NOT NULL,
                                        col_num INTEGER,
                                        col_name text,
                                        col_type text,
                                        description text,
                                        rec_extract_date text
                                        
                                    ); """

# The above 3 core tables do not need to be added to the table list, and can be created
# from SQL above FIRST, so that in the init function, the metadata is inserted anyway.

def_tables = [ # [table_name, description, grain_cols, col_list, cols_INT, cols_REAL, cols_BLOB]
    ['sys_meta_tables', 'Table definitions for database', 'table_name', 'table_name, description, grain_cols, col_list', [], [], []],
    ['sys_meta_table_columns', 'Column definitions for database', 'table_name, col_num, col_name', 'table_name, col_name, col_type, description', ['col_num'], [], []],
    ['sys_log', 'Main logfile for database', 'log_date', 'log_date, log_level, details', ['log_level'], [], []],
    ['sys_usage', 'Usage log', 'log_date', 'log_date, details', [], [], []],
    ['sys_proj', 'Project Details', 'id', 'proj_id, details', [], [], []],
    ['sys_jobs', 'ETL Job to run', 'proj_id, job_id', 'proj_id, job_num, job_id, details', ['job_num'], [], []],
    ['sys_job_steps', 'SQL to run for step of a job', 'job_id, step_num', 'job_id, job_num, step_num, job_type, src_tbl, dest_tbl, details, sql_to_run, params', ['step_num', 'job_num'], [], []],
    ['sys_todo', 'Dev notes on things to do, bugs to fix', 'todo_id', 'todo_id, date_added, date_done, tpe, details', [], [], []],
    
]


sql_view_file_xtn = """CREATE VIEW V_FILE_XTN AS 
    SELECT replace(name, rtrim(name, replace(name, '.', '')), '') as xtn, 
            sum(size) as tot_size, count(*) as num_files 
    FROM s_filelist_raw 
    group by replace(name, rtrim(name, replace(name, '.', '')), '');
"""

