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
    return render_template('login.html',
                            menu_list=[],
                            menu_selected = 'About',
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
    return show_page('notes', 'Notes', [])

@app.route("/calendar", methods=['GET'])
def page_calendar():
    curr_date = get_today_date_str() 
    return show_page_calendar( 'calendar' , curr_date, [])



@app.route("/tasks", methods=['GET'])
def page_tasks():
    return show_page('tasks', 'Tasks', [])

@app.route("/options", methods=['GET'])
def page_options():
    return show_page('options', 'Options', [])

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
                        footer=get_footer())


def show_page_calendar(listname, curr_date, lst, fltr='All'):
    #import as_calendar
    #calendar_html = as_calendar.get_calendar_with_data(get_user_id(), curr_date, web, conn_str)
    calendar_html = 'todo'
    display_name = get_user()

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
                        footer=get_footer())



if __name__ == '__main__':
    start_server()
