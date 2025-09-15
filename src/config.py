#!/usr/bin/python3
# coding: utf-8
# config.py

import os

# ----------------------------------------------------------------------------
# Folder Locations
# 

user_folder = r'\\FANGORN\user\duncan\LifePIM_Data'

logon_file = os.path.join(user_folder, 'configuration', 'lifepim.par')
data_folder = os.path.join(user_folder, 'DATA')
index_folder = os.path.join(user_folder, 'index')
calendar_folder = os.path.join(user_folder, 'calendar')
folder_list_file =  os.path.join(user_folder, 'configuration', 'folders.lis')


# ----------------------------------------------------------------------------
# Interface configuration

# Project list default
proj_list = ['Dev','Design','Fun','Games','Family','Car',
             'Business','Web','Home','Study','Health','Work',
             'RasbPI','AI','Support','Pers']


toolbar_definition_OLD =  [  # [icon, name, function, comments]
    ['🏠', 'home',     'tb_home',         '🏠📰 This is the overview page'],
    ['🕐', 'calendar', 'tb_calendar', '⌚📅 🕐 Project overview showing current list of tasks being worked on'],
    ['☑',  'tasks',    'tb_tasks',    '☑✔📎🔨✘☑ ⛏ ☹     💻 💹 Tasks'],
    ['📝', 'notes',    'tb_notes',    '🗒✎📝 ✏ 🗊Team wiki page - ultra simple'], #
    ['👤', 'contacts', 'tb_contacts',     '☎👱  👤  Contacts view'],
    ['🌏️', 'places',   'tb_places',    '🌏🛰️⛟ ⌖ ⛰    💻 💹Locations - maps, people finder'],
    ['▦',  'data',     'tb_data',    '▧🗒 🗊data tables'],
    ['🏆', 'badges',   'tb_badges',     '★ ⛤ ✵ ✭ ⚜'],
    ['💲', 'money',    'tb_money',      ''],
    ['♬',  'music',    'tb_music',     '🗒 🗊music'],
    ['🖼',  'images',  'tb_images',      '🗒 🗊images'],
    ['🎮', 'apps',     'tb_apps',     '👍 👎 '],
    ['📂',  'files',   'tb_files',     '🗒 🗊images and files'],
    ['⚿',  'admin',   'tb_admin',      'passwords'],
    ['⚙',  'options', 'tb_options',     'Options for LifePIM'],
    ['⚙',  'about',   'tb_about',    'About LifePIM']
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


sub_menus = [
    {'root':'notes', 'name':'Ideas'},
    {'root':'notes', 'name':'Meeting Notes'},
    {'root':'notes', 'name':'Project Info'},
    {'root':'notes', 'name':'Research'},
    {'root':'tasks', 'name':'Today'},
    {'root':'tasks', 'name':'This Week'},
    {'root':'tasks', 'name':'This Month'},
    {'root':'tasks', 'name':'Completed'},
    {'root':'calendar', 'name':'Appointments'},
    {'root':'calendar', 'name':'Events'},
    {'root':'calendar', 'name':'Reminders'},
    {'root':'data', 'name':'Databases'},
    {'root':'data', 'name':'Spreadsheets'},
    {'root':'data', 'name':'Checklists'},
    {'root':'files', 'name':'Documents'},
    {'root':'files', 'name':'PDFs'},
    {'root':'files', 'name':'Presentations'},
    {'root':'images', 'name':'Photos'},
    {'root':'images', 'name':'Screenshots'},
    {'root':'images', 'name':'Drawings'},
    {'root':'music', 'name':'Songs'},
    {'root':'music', 'name':'Albums'},
    {'root':'music', 'name':'Playlists'},
    {'root':'video', 'name':'Movies'},
    {'root':'video', 'name':'Clips'},
    {'root':'video', 'name':'Recordings'},
]

filters = [
      ['notes', 'type', ['Idea', 'Meeting Note', 'Project Info', 'Research']],
        ['tasks', 'status', ['Not Started', 'In Progress', 'Completed', 'Deferred', 'Waiting on someone else']],
        ['tasks', 'priority', ['Low', 'Medium', 'High', 'Urgent']],
        ['calendar', 'type', ['Appointment', 'Event', 'Reminder']],
        ['data', 'type', ['Database', 'Spreadsheet', 'Checklist']],
        ['files', 'type', ['Document', 'PDF', 'Presentation']],
        ['images', 'type', ['Photo', 'Screenshot', 'Drawing']],
        ['music', 'type', ['Song', 'Album', 'Playlist']],
        ['video', 'type', ['Movie', 'Clip', 'Recording']], 
]   

for tab in TABS:
    sub_menus.append({'root':tab['id'], 'name':'Add'})
	

ui_actions = []    # these are the clickable links that appear per tab / submenu
for tab in TABS:
    ui_actions.append([tab['id'], 'Add', 'fn_' + tab['id'] + '_add'])
    #ui_actions.append([tab['id'], 'Import', 'fn_' + tab['id'] + '_import'])
    #ui_actions.append([tab['id'], 'Generate', 'fn_' + tab['id'] + '_gen'])



api_routes = [
    '/',
    '/notes',
    '/notes/<id>',
    '/tasks',
    '/tasks/<id>',
    '/calendar',
    '/calendar/<id>',
    '/files',
    '/files/<filename>',
    '/options',
]


current_index_list = [
    r'\\FANGORN\user\duncan\LifePIM\Data',
    r'\\FANGORN\user\duncan\C\user\docs',
    r'\\FANGORN\user\duncan\C\user\dev',
    r'\\FANGORN\user\duncan\C\user\AIKIF',
    r'\\FANGORN\user\duncan\C\user\acute',
    r'\\FANGORN\user\DATA\photos',
    r'\\FANGORN\user\DATA\eBooks',
    r'\\FANGORN\user\DATA\3D',
    r'\\FANGORN\photo',
    r'\\FANGORN\music',
    r'D:\docs\Unreal Projects',
    r'D:\dev\src',
]


port_num=9741           # port to browse to, eg. http://127.0.0.1:9741/
WEB_VERSION = "DEV"     # to show debug lines in web server
base_url = 'https://www.lifepim.com'    # testing, point to live site for API
base_url = '127.0.0.1:5000'             # running local (default)


# --------------------------------------------------------
# Functions


def get_conn_str():
	conn_str = {}
	with open(logon_file, 'r') as f:
		conn_str['host'] = f.readline().strip(' ').strip('\n')
		conn_str['user'] = f.readline().strip(' ').strip('\n')
		conn_str['pass'] = f.readline().strip(' ').strip('\n')
		conn_str['db'] = f.readline().strip(' ').strip('\n')

	return conn_str
