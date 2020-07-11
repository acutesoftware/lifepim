#!/usr/bin/python3
# -*- coding: utf-8 -*-
# web_server.py


import os
import sys
import time
import datetime
from datetime import timedelta
from flask import Flask
from flask import request
from flask import Response
from flask import render_template
from flask import session
from flask import g
from flask import redirect
from flask import url_for
from flask import abort
from flask import flash
from flask import send_from_directory

import logging
from logging.handlers import RotatingFileHandler

import web_data as web
import config as mod_cfg

LifePIM_VERSION_NUM = "version 0.1 Last updated 12th-Jun-2020"
LifePIM_WEB_VERSION = "Alpha"


app = Flask(__name__)

app.secret_key = "KLr4757375fdjhshjSDFHDHFVS"


app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

app.permanent_session_lifetime = datetime.timedelta(days=365)

def start_server():
    app.run(threaded=True, host='0.0.0.0', port=9741) 


def get_run_location_DEBUG():
    """
    quick way to determine if you are working on the data
    in the public DEV version, or prod version
    """
    if mod_cfg.user_folder == r'D:\dev\src\lifepim\lifepim\SAMPLE_DATA':
        return 'DEV', ''
    else:
        return 'PROD', mod_cfg.user_folder

#########################################################
# Routes 

@app.route('/login', methods=['GET', 'POST'])
def login():

    error = None
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
        except:
            pass
        if verify_login(username, password) == False:
            error = 'Invalid username or password'
            flash('invalid login')

        else:
            flash('You are logged in')

            return redirect(url_for('page_home'))

    nav_title, nav_warn = get_run_location_DEBUG()
    return render_template('login.html',
                            menu_list=[],
                            menu_selected = 'About',
                            nav_title = nav_title, 
                            nav_warn =  nav_warn,
                            error=error)

def verify_login(username, password):
    """
    checks credentials against database
    """
    user_info = mod_cfg.get_conn_str()

    if user_info['user'] != username:
        flash('Invalid username')
    elif user_info['pass'] != password:
        flash('wrong password')

        # need a delay here
        import time
        time.sleep(3)


    else:
        session['user_id'] = username
        session['logged_in'] = True
        session['username'] = username
        session['time_offset_hours'] =  10.5
        
        return True
    
    return False


@app.route('/logout')
def logout():
    #app.logger.info('logout from ' + session['username'])
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('cur_folder', None)
    flash('You were logged out')
    return redirect(url_for('page_home'))


@app.route("/", methods=['GET'])
def page_home():
    return show_page('home', 'Home', [])

@app.route("/notes", methods=['GET'])
def page_notes():
    notes_list = load_notes_from_folders(mod_cfg.data_folder)


    return show_page('notes', 'Notes', notes_list)

def load_notes_from_folders(fldr):
    """
    reads all text files in a folder on the NAS and converts 
    them into notes list
    """
    #aikif_fl = mod_fl.FileList([mod_cfg.data_folder], ['*.*'], [], filelist )
    #aikif_fl.save_filelist(filelist, ["name", "path", "size", "date"])
    res = []

    files = web.get_file_list([fldr], '*.txt', shortNameOnly='N')
    #print('files found = ', files)
    for fname in files[0]:
        #print('reading note, ', fname)
        res.append(extract_note_summary(fname))

    return res

def extract_note_summary(fname):
    """
    takes a single file on the NAS and builds a list
    of the required parameters. At first these are default
    but later this will be held in a local lifepim database
    (or perhaps from metadata or business rules?)
    [id, title, pinned, important, is_archived, color, content, folder]
    """

    id, title, pinned, important, is_archived, color, folder = get_note_metadata(fname)
    content = 'todo - read first 200 chars'
    return [id, title, pinned, important, is_archived, color, content, folder]


def get_note_metadata(fname):
    """
    reads the metadata
    """
    id = fname.replace('/', '|').replace('\\','|').replace(':','=')
    title = fname.replace(mod_cfg.data_folder, '')
    pinned = 'N'
    important = 'N'
    is_archived = ''
    color = 'Green'
    folder = fname

    return id, title, pinned, important, is_archived, color, folder



@app.route("/note/<id_to_update>", methods=['GET'])
def page_note(id_to_update):
    res = load_notes_from_folders(mod_cfg.data_folder)
    #res = load_single_note(id_to_update)
    fname = id_to_update.replace('|', '\\').replace('=', ':')
    id, title, pinned, important, is_archived, color, folder = get_note_metadata(fname)

    print('reading note = ', fname)
    content = ''
    with open(fname, 'r') as fip:
        for line in fip:
            content += line + '\n'

    headers = []
    record = [id, title, pinned, important, is_archived, color, content, folder]

    #print('VIEWING NOTE - record = ', record)

    return render_template('note.html',
                        footer=get_footer(),
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(),
                        headers = headers,
                        record = record,
                        id_to_update=id_to_update,
                        id=id_to_update,  # duplicate var, needed to hide NEW button - FIX THIS
                        menu_selected = 'note',
                        listname='notes',
                        username=get_user()
                        )




@app.route("/edit/<id_to_update>/<listname>", methods=['GET'])
def edit_value(id_to_update, listname):
    return 'todo = edit this item'

@app.route("/files", methods=['GET'])
def page_files():
    print('getting files...')
    #from views.files import files as mod_files

    fldr_list = web.get_folder_list(mod_cfg.folder_list_file)
    #print(fldr_list)
    return show_page('files', 'Files', fldr_list)

@app.route("/filefind/<fname>", methods=['GET'])
def page_file_find(fname):
    print('searching for file ' + fname)
    #from views.files import files as mod_files



@app.route("/file/<fname>", methods=['GET'])
def page_file_view(fname):
    print('viewing file ' + fname)
    #from views.files import files as mod_files


    files = web.get_file_list([fname], ['*.*'])

    #print('files = ', files)

    return show_page('files', 'Files', files)


@app.route('/images')
def page_images():
    fldr_list = web.get_folder_list(mod_cfg.folder_list_file)
    files = web.get_file_list(fldr_list, mod_cfg.image_xtn_list, shortNameOnly='N')

    #print('image list = ')
    #print(files)
    return show_page_file('images', 'Images', fldr_list[0][0:10], files[0][0:6])

@app.route('/images/<fname>')
def page_images_view(fname):

    fullname = os.path.join(mod_cfg.data_folder,fname)
    with open(fullname, 'rb') as f:
        bindata = f.read()
    return 'viewing file ' + fname + '     full path = ' + fullname + ' size is ' + str(len(bindata))

@app.route('/img_view/<filename>')
def send_file(filename):
    """
    returns the users image they selected OR a public image from blog
    """
    MY_UPLOAD_FOLDER = mod_cfg.data_folder
    return send_from_directory(MY_UPLOAD_FOLDER, filename)



@app.route("/calendar", methods=['GET'])
def page_calendar():
    curr_date = get_today_date_str() 
    return show_page_calendar( 'calendar' , curr_date, [])

@app.route("/calendar", methods=['POST'])
def page_calendar_jump_to_date():
    #lst = web.get_table_as_list('id, dateevent, dateevent_str, details', 'as_event', '1=1', conn_str)

    # first get the hidden form values put there by javascript that defines
    # current_display, today, prev date, next date
    # date_now


    dte_curr = request.form['date_curr']  # this works looking at selected date by prev/next/today, but NOT jump to date
    try:
        dte_curr = request.form['date_selected']  # this works looking at selected date by prev/next/today, but NOT jump to date
    except:
        pass

    try:	# need to check here, in case user clicks 'x' on datepicker to choose invalid date
        dte_curr_as_date = datetime.datetime.strptime(dte_curr, "%Y-%m-%d")
    except:
        dte_curr_as_date = get_today_date()
    try:
        res = request.form['btn_goto_date']
        dte = request.form['date_selected']
    except:
        pass

    try:
        res = request.form['btn_today']
        dte = request.form['date_now']
        dte_curr = get_today_date()
    except:
        pass

    try:
        res = request.form['btn_prev']
        dte = request.form['date_prev']
        dte_curr = dte_curr_as_date + datetime.timedelta(days=-1*calendar_get_numdays(calendar_get_type()))
    except:
        pass

    try:
        res = request.form['btn_next']
        dte = request.form['date_next']
        dte_curr = dte_curr_as_date + datetime.timedelta(days=calendar_get_numdays(calendar_get_type()))
    except:
        pass


    # Check for Day/Week/Month switches (will need to reload data)
    try:
        res = request.form['btn_day']
        if res:	# use clicked the view by days
            calendar_set_type('Day')
    except:
        pass
    try:
        res = request.form['btn_week']
        if res:	# use clicked the view by weeks
            calendar_set_type('Week')
    except:
        pass
    try:
        res = request.form['btn_month']
        if res:	# use clicked the view by months
            calendar_set_type('Month')
    except:
        pass

    try:
        res = request.form['btn_year']
        if res:	# use clicked the view by months
            calendar_set_type('Year')
    except:
        pass

    if type(dte_curr) is str:
        selected_date_as_str = dte_curr
    else:
        selected_date_as_str = dte_curr.strftime('%Y-%m-%d')

    fltr_sql, fltr_prm = get_glb_filter()
    #import as_calendar
    #lst = as_calendar.get_events(get_user_id(), selected_date_as_str, calendar_get_type(), get_folder(), fltr_sql, fltr_prm, conn_str, web)
    lst = []
    return show_page_calendar( 'calendar' , dte_curr, lst)


@app.route('/calendar/<date>', methods=['POST'])
def page_calendar_date_jump(date):
    # If user is already looking  at other dates and clicks POST
    # this means they have clicked on other buttons on the form to
    # navigate to another date, so we recreate page_calendar_jump_to_date
    #('jump from date = ', date)
    # doesnt work return redirect(url_for(page_calendar_jump_to_date))
    dte_curr = request.form['date_curr']  # this works looking at selected date by prev/next/today, but NOT jump to date
    try:
        dte_curr = request.form['date_selected']  # this works looking at selected date by prev/next/today, but NOT jump to date
    except:
        pass

    try:	# need to check here, in case user clicks 'x' on datepicker to choose invalid date
        dte_curr_as_date = datetime.datetime.strptime(dte_curr, "%Y-%m-%d")
    except:
        dte_curr_as_date = get_today_date()
    try:
        res = request.form['btn_goto_date']
        dte = request.form['date_selected']
    except:
        pass

    try:
        res = request.form['btn_today']
        dte = request.form['date_now']
        dte_curr = get_today_date()
    except:
        pass

    try:
        res = request.form['btn_prev']
        dte = request.form['date_prev']
        dte_curr = dte_curr_as_date + datetime.timedelta(days=-1*calendar_get_numdays(calendar_get_type()))
    except:
        pass

    try:
        res = request.form['btn_next']
        dte = request.form['date_next']
        dte_curr = dte_curr_as_date + datetime.timedelta(days=calendar_get_numdays(calendar_get_type()))
    except:
        pass


    # Check for Day/Week/Month switches (will need to reload data)
    try:
        res = request.form['btn_day']
        if res:	# use clicked the view by days
            calendar_set_type('Day')
    except:
        pass
    try:
        res = request.form['btn_week']
        if res:	# use clicked the view by weeks
            calendar_set_type('Week')
    except:
        pass
    try:
        res = request.form['btn_month']
        if res:	# use clicked the view by months
            calendar_set_type('Month')
    except:
        pass

    try:
        res = request.form['btn_year']
        if res:	# use clicked the view by months
            calendar_set_type('Year')
    except:
        pass

    if type(dte_curr) is str:
        selected_date_as_str = dte_curr
    else:
        selected_date_as_str = dte_curr.strftime('%Y-%m-%d')

    return redirect(url_for('page_calendar_date', date=selected_date_as_str))



@app.route('/calendar/<date>', methods=['GET'])
def page_calendar_date(date):
    """

    """
    import as_calendar
    fltr_sql, fltr_prm = get_glb_filter()

    selected_date_as_str = date
    #lst = as_calendar.get_events(get_user_id(), selected_date_as_str, calendar_get_type(), get_folder(), fltr_sql, fltr_prm, conn_str, web)
    lst = []
    
    return show_page_calendar( 'calendar', date, lst)



def calendar_get_numdays(view_type):
    """
    get_next_date_str(dte, view_type) in as_calendar for future stuff
    """
    if view_type == 'Day':
        return 1
    elif view_type == 'Week':
        return 7
    elif view_type == 'Month':
        return 31
    elif view_type == 'Year':
        return 365
    else:
        return 7

def calendar_set_type(view_type):
    if view_type in ['Day','Week','Month', 'Year']:
        session['cal_view_type'] = view_type
        return redirect(url_for(page_calendar_jump_to_date))
    return redirect(url_for(page_calendar))


def calendar_get_type():
    view_type = 'Week'
    try:
        view_type = session['cal_view_type']
    except:
        pass
    return view_type





@app.route("/tasks", methods=['GET'])
def page_tasks():
    return show_page('tasks', 'Tasks', [])



@app.route("/task_done/<id>", methods=['GET','POST'])
def page_task_done(id):
    web.update_row(get_user_id(), 'tasks', id, ['Done'], ['Y'], conn_str)
    lst = get_data_for_tasks()
    return show_page('tasks', 'tasks', lst)

@app.route("/task_uncomplete/<id>", methods=['GET','POST'])
def page_task_uncomplete(id):
    web.update_row(get_user_id(), 'tasks', id, ['Done'], [''], conn_str)
    lst = get_data_for_tasks()
    return show_page('tasks', 'tasks', lst)  # 'should not refresh page' #


@app.route("/projects")
def page_projects():
    lst = web.get_table_as_list(get_user_id(), 'id, title, folder', 'as_task_project', 'category < 9', [], conn_str)
    return show_page('projects', 'projects', lst)

@app.route("/task_templates")
def page_task_templates():
    lst = web.get_table_as_list(get_user_id(), 'id, title, folder', 'as_task_project', 'category = 9', [], conn_str)
    return show_page('task_templates', 'projects', lst)

@app.route("/goals")
def page_goals():
    lst = get_data_for_list('goals')
    return show_page('goals', 'goals', lst)



@app.route('/upload_process_file/<listname>', methods=['POST'])
def upload_process_file(listname):
    """
    we get here if user selected a file to be
    uploaded to the UPLOADS folder
    """
    file_to_upload = request.files['file']
    upload_folder = mod_cfg.data_folder
    filename = web.secure_filename(file_to_upload.filename)
    dest_file = os.path.join(upload_folder, filename)
    try:
        file_to_upload.save(dest_file)
    except Exception as ex:
        flash('Cant access the file - is it open in Excel?  (' + dest_file + ')     ' + str(ex))
        return render_template('upload.html',
                            is_authenticated = logged_in(),
                            listname = listname
                    )

    flash('Successfully Uploaded ' + file_to_upload.filename )

    if listname == 'images':
            flash('You can link to this image in your Notes with [img]' + file_to_upload.filename + '[/img]')
            return redirect(url_for('page_images'))

    nav_title, nav_warn = get_run_location_DEBUG()
    
    return render_template('upload.html',
                        footer=get_footer(),
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(get_user_id(), conn_str),
                        menu_selected = 'Upload',
                        filelist = as_user.get_users_uploaded_files(mod_cfg, get_user()),
                        username=get_user(),
                        nav_title = nav_title, 
                        nav_warn =  nav_warn,
                        listname = listname
                        )



@app.route("/options", methods=['GET'])
def page_options():
    return show_page('options', 'Options', [])


@app.route("/page_options_settings", methods=['GET', 'POST'])
def page_options_settings():
    """
    <input type="checkbox" class="form-group" name="tab_calendar" checked>Calendar<BR>
    <input type="checkbox" class="form-group" name="tab_staff">Staff<BR>
    <input type="checkbox" class="form-group" name="tab_tasks" checked>Tasks<BR>
    <input type="checkbox" class="form-group" name="tab_notes" checked>Notes<BR>
    <input type="checkbox" class="form-group" name="tab_files">Files<BR>
    <input type="checkbox" class="form-group" name="tab_images" checked>Media<BR>
    <input type="checkbox" class="form-group" name="tab_apps">Apps<BR>
    <input type="checkbox" class="form-group" name="tab_badges">Badges<BR>
    <input class="form-group" type="submit" value="Save Settings"><BR>

        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_calendar', request.form['tab_calendar'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_staff', request.form['tab_staff'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_notes', request.form['tab_notes'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_tasks', request.form['tab_tasks'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_files', request.form['tab_files'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_images', request.form['tab_images'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_apps', request.form['tab_apps'])
        web.save_config(get_user_id(), conn_str, 'display_tab', 'tab_badges', request.form['tab_badges'])


    """
    if request.method == 'POST':


        visible_tabs = '|'  # this is the string that will contain the list of tabs

        col_names = []
        col_data = []
        for field in request.form:
            cur_text_data = request.form[field]
            if str(field)[0:4] != 'btn_':
                col_names.append(str(field))
                col_data.append(cur_text_data)
                #print("request.form['" + field + "'] = ", cur_text_data)
                visible_tabs += field.replace('tab_', '') + '|'

        #web.save_config(get_user_id(), conn_str, 'display', 'tabs', visible_tabs)

        flash('TODO - Save settings - visible tabs are : ' + visible_tabs)
        return redirect(url_for('page_options'))

    # If we are here, then it is a GET so we need to read settings and pass to Options page
    visible_tabs = web.load_config(get_user_id(), conn_str, 'display', 'tabs')
    lst_tabs = visible_tabs.split('|')
    #print('visible_tabs as list = ', lst_tabs)
    return show_page('options', 'Options', lst_tabs)


@app.route("/folders")
def page_folders():

    lst = get_data_for_list('folders')
    return show_page('folders', 'folders', lst)

@app.route("/folders/<listname>/<fltr>")
def page_folders_filtered(listname, fltr):
    """
    we get here if user selects a FILTER on from the page
    """
    session['cur_folder'] = fltr

    if listname in ('Overview', 'About'):
        return show_home_page(fltr)
    elif listname in ('images'):
        return redirect(url_for('page_images'))

    else:
        lst = get_data_for_list(listname)
        url_name = web.get_function_name(listname)
        if url_name:
            return redirect(url_for(url_name))
        else:
            return show_home_page(fltr)


@app.route("/about", methods=['GET'])
def page_about():
    return show_page('about', 'About', [])



@app.route("/view/<listname>/<view_as>")
def view(listname, view_as):
    # dont log unicode, may cause issue app.logger.info('view as = ', str(view_as))
    if view_as == '☷':
        session['view_as'] = '☷' # 'View as Cards'
    elif view_as == '▤':
        session['view_as'] = '▤' # 'View as List' ▤  ☰
    elif view_as == '⛏':
        session['view_as'] = '⛏' # 'View Zoomed'
    else:
        session['view_as'] = '▤' # 'View as List'

    return redirect(url_for(web.get_function_name(listname)))


@app.route('/add/<listname>', methods=['POST'])
def add_new_record(listname):
    return 'todo - posting data so save it somewhere'

@app.route('/add/<listname>', methods=['GET'])
def add(listname):
    return 'todo show edit form to add a record'



@app.route('/search', methods=['POST'])
def search_list():
    # first check to see if this is a login request

    search_text = request.form['search_text']
    import index 

    search_results, files_found = index.search(search_text)
    #print('SEARCH RESULTS - NOTES ONLY')
    #print(search_results)
    nav_title, nav_warn = get_run_location_DEBUG()

    return render_template('search.html',
                        search_text = search_text,
                        search_results = search_results,
                        files_found = files_found,
                        num_results = len(search_results),
                        num_files_found = len(files_found),
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(),
                        menu_selected = 'About',
                        view_as = get_cur_viewas(),
                        all_folders=get_folder_list(),
                        cur_folder=get_cur_folder(),
                        username=get_user(),
                        nav_title = nav_title, 
                        nav_warn =  nav_warn,
                        footer=get_footer())






#########################################################
# Web server functions

def logged_in():
    try:
        if session['logged_in']  == True:
            return 'Y'
    except:
        pass
    return 'N'

def get_user():
    try:
        user = session['username']
    except:
        user = ''
    return user

def get_user_id():
    try:
        user_id = session['user_id']
    except:
        user_id = -1
    return user_id


def get_cur_folder():
    try:
        fldr = session['cur_folder']
    except:
        fldr = 'All'
    return fldr

def get_cur_viewas():
    try:
        view_as = session['view_as']
    except:
        view_as = '☷'   # ⛏
    return view_as

def get_cur_view_desc():
    try:
        view_as = session['view_as']
    except:
        pass

    if view_as == '▤':
        return 'View as List'
    elif view_as == '☷':
        return 'View as Card'
    elif view_as == '⛏':
        return 'View as Birds Eye'
    else:
        return '⛏'




# session['view_as']

def get_folder_list():
    return ['blogs', 'ideas', 'recipes', 'work']

def get_today_date_str():
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    ## TODO - session['time_offset_hours']
    session['time_now'] = today
    return today

def get_tomorrow_date_str():
    today = (datetime.datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%d')
    session['time_tomorrow'] = today
    ## TODO - session['time_offset_hours']
    return today

def get_today_date():
    today = datetime.datetime.utcnow()
    ## TODO - session['time_offset_hours']
    return today

def get_tomorrow_date():
    today = datetime.datetime.utcnow() + timedelta(days=2) # wrong
    ## TODO - session['time_offset_hours']
    return today

def get_today_date_display():
    #'Fri 15th Dec, 2017'
    ## TODO - session['time_offset_hours']

    return datetime.datetime.utcnow().strftime('%a, %d-%b-%Y')

def get_footer(pge=''):
    txt = ''
    txt += pge
    txt += LifePIM_WEB_VERSION + ':' + LifePIM_VERSION_NUM + '\n'
    return txt

def show_page(page_name, listname, lst, fltr='All'):
    """
    points the correct render_template to the correct page
    """

    users_folder = ''  
    display_name = get_user()

    if page_name == 'images':
        viewas = '▤'
    else:
        viewas = get_cur_viewas()

    print('showing page ' + page_name)
    nav_title, nav_warn = get_run_location_DEBUG()

    return render_template(page_name + '.html',
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(),
                        menu_selected = page_name,
                        col_types = web.tbl_get_cols_types_as_list(listname),
                        listname = listname,
                        groups = [],
                        current_group='All Groups',
                        today = get_today_date_str(), 
                        view_as = viewas,
                        lst = lst,
                        users_folder = users_folder,
                        num_recs = len(lst),
                        all_folders=get_folder_list(),
                        cur_folder=get_cur_folder(),
                        username=get_user(),
                        display_name = display_name,
                        nav_title = nav_title, 
                        nav_warn =  nav_warn,
                        footer=get_footer())



def show_page_file(page_name, listname, folder_name, lst, fltr='All'):
    """
    show image
    """

    users_folder = ''  
    display_name = get_user()

    viewas = get_cur_viewas()

    print('showing page ' + page_name)
    nav_title, nav_warn = get_run_location_DEBUG()

    return render_template(page_name + '.html',
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(),
                        menu_selected = page_name,
                        col_types = web.tbl_get_cols_types_as_list(listname),
                        listname = listname,
                        fullnames = lst,
                        groups = [],
                        current_group='All Groups',
                        today = get_today_date_str(), 
                        view_as = viewas,
                        lst = lst,
                        users_folder = users_folder,
                        num_recs = len(lst),
                        all_folders=get_folder_list(),
                        cur_folder=get_cur_folder(),
                        username=get_user(),
                        display_name = display_name,
                        nav_title = nav_title, 
                        nav_warn =  nav_warn,
                        footer=get_footer())


def show_page_calendar(listname, curr_date, lst, fltr='All'):
    #import as_calendar
    #calendar_html = as_calendar.get_calendar_with_data(get_user_id(), curr_date, web, conn_str)
    calendar_html = 'todo'
    display_name = get_user()
    nav_title, nav_warn = get_run_location_DEBUG()

    return render_template('calendar.html',
                        is_authenticated = logged_in(),
                        menu_list=web.get_menu_list(),
                        menu_selected = 'calendar',
                        col_types = web.tbl_get_cols_types_as_list(listname),
                        listname = listname,
                        selected_date = curr_date,
                        view_as = get_cur_viewas(),
                        view_type = '', # calendar_get_type(),
                        today = get_today_date_str(),
                        lst = lst,
                        num_recs = len(lst),
                        calendar_html = calendar_html,
                        all_folders=get_folder_list(),
                        cur_folder=get_cur_folder(),
                        username=get_user(),
                        display_name=display_name,
                        nav_title = nav_title, 
                        nav_warn =  nav_warn,
                        footer=get_footer())



if __name__ == '__main__':
    start_server()
