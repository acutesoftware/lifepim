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

LifePIM_VERSION_NUM = "version 0.1 Last updated 9th-Jun-2020"
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

@app.route("/", methods=['GET'])
def page_home():
    return show_page('home', 'Home', [])


@app.route("/notes", methods=['GET'])
def page_notes():
    return show_page('notes', 'Notes', [])

@app.route("/options", methods=['GET'])
def page_options():
    return show_page('options', 'Options', [])

@app.route("/about", methods=['GET'])
def page_about():
    return show_page('about', 'About', [])

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


if __name__ == '__main__':
    start_server()
