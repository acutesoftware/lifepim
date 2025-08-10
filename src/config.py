#!/usr/bin/python3
# coding: utf-8
# config.py

import os


# ----------------------------------------------------------------------------
# FILE: config.py
# ----------------------------------------------------------------------------

toolbar_definition = [
    # [icon, name, function, comments, hide(optional)]
    ['🏠', 'home',     'tb_home',         'Overview'],
    ['🕐', 'calendar', 'tb_calendar',     'Calendar'],
    ['☑',  'tasks',   'tb_tasks',        'Tasks'],
    ['📝', 'notes',   'tb_notes',        'Notes'],
    ['👤', 'contacts','tb_contacts',     'Contacts', 'N'],
    ['🌏', 'places',  'tb_places',       'Places',   'N'],
    ['⚙',  'options', 'tb_options',      'Options',  'N'],
    ['⚙',  'about',   'tb_about',        'About',    'N']
]

# Tabs configuration - order, label, view module path (importable) and ability to hide if new column 'hide' == 'Y'
TABS = [
    { 'id': 'home', 'label': 'Overview', 'module': 'views.home', 'class': 'HomeView' },
    { 'id': 'calendar', 'label': 'Calendar', 'module': 'views.calendar', 'class': 'CalendarView' },
    { 'id': 'tasks', 'label': 'Tasks', 'module': 'views.tasks', 'class': 'TasksView' },
    { 'id': 'notes', 'label': 'Notes', 'module': 'views.notes', 'class': 'NotesView' },
]

# Project list default
proj_list = ['Dev','Design','Fun','Games','Family','Car',
             'Business','Web','Home','Study','Health','Work',
             'RasbPI','AI','Support','Pers']

# Favorites
FAV_FOLDERS = [r"D:\dev\src\LIFEPIM_WEB\USER_DATA\duncan\notes", 
               r"N:\duncan\LifePIM_Data"]

# Cache file
CACHE_FILE = 'life_pim_cache.pickle'

# Visual density settings - very compact
UI = {
    'font_family': 'TkDefaultFont',
    'font_size': 9,
    'padding': 2,
    'toolbar_button_padx': 3,
    'toolbar_button_pady': 2,
}

