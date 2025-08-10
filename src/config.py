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


TABS = [
    { 'icon': '🏠', 'id': 'home', 'label': 'Overview', 'module': 'views.home', 'class': 'HomeView'},
    { 'icon': '📝', 'id': 'notes', 'label': 'Notes', 'module': 'views.notes', 'class': 'NotesView'},
    { 'icon': '☑', 'id': 'tasks', 'label': 'Tasks', 'module': 'views.tasks', 'class': 'TasksView'},
    { 'icon': '🕐', 'id': 'calendar', 'label': 'Calendar', 'module': 'views.calendar', 'class': 'CalendarView'},
    { 'icon': '▦', 'id': 'data', 'label': 'Data', 'module': 'views.data', 'class': 'DataView'},
    { 'icon': '📂', 'id': 'files', 'label': 'Files', 'module': 'views.files', 'class': 'FileView'},
    { 'icon': '🖼️', 'id': 'images', 'label': 'Images', 'module': 'views.images', 'class': 'ImagesView'},
    { 'icon': '♬', 'id': 'music', 'label': 'Music', 'module': 'views.music', 'class': 'MusicView'},
    { 'icon': '🎥', 'id': 'video', 'label': 'Video', 'module': 'views.video', 'class': 'VideoView'},
    { 'icon': '🏆', 'id': 'badges', 'label': 'Badges', 'module': 'views.badges', 'class': 'BadgesView'},
    { 'icon': '💲', 'id': 'money', 'label': 'Money', 'module': 'views.money', 'class': 'MoneyView'},
    { 'icon': '👤', 'id': 'contacts', 'label': 'Contacts', 'module': 'views.contacts', 'class': 'ContactsView'},
    { 'icon': '🌏', 'id': 'places', 'label': 'Places', 'module': 'views.places', 'class': 'PlacesView'},
    { 'icon': '💻', 'id': 'system', 'label': 'System', 'module': 'views.system', 'class': 'SystemView'},
    { 'icon': '🎮', 'id': 'apps', 'label': 'Apps', 'module': 'views.apps', 'class': 'AppsView'},
    { 'icon': '⚙', 'id': 'etl', 'label': 'ETL', 'module': 'views.etl', 'class': 'EtlView'},
    { 'icon': '📜', 'id': 'journal', 'label': 'Journal / Logs', 'module': 'views.journal', 'class': 'JournalView'},
    { 'icon': '⚿', 'id': 'admin', 'label': 'Admin', 'module': 'views.admin', 'class': 'AdminView'},
    { 'icon': '🤖', 'id': 'agent', 'label': 'Agent', 'module': 'views.agent', 'class': 'AgentView'},


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
    'font_size': 9,  # was 9 , 11 looks ok as well
    'padding': 2,
    'toolbar_button_padx': 3,
    'toolbar_button_pady': 2,
}

style_name = 'clam'  # 'clam' for light mode, 'dark' for dark mode


# large icons
tab_font_name = 'Segoe UI Emoji'
tab_font_size = 14
tab_font_bold = 'bold'

# medium icons
tab_font_name = 'Segoe UI Emoji'
tab_font_size = 10
tab_font_bold = ''


# ----------------------------------------------------------------------------


