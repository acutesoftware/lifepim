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


SIDE_TABS_GROUPS = [  # for possible sub folders
    { 'icon': '*', 'id': 'ALL', 'sub_list': 'All Projects'},
    { 'icon': '🔒', 'id': 'PERS', 'sub_list': 'Pers,Health,Home,Car,Family,Food'},
    { 'icon': '🎉', 'id': 'FUN', 'sub_list': 'games, travel, Music, movies, Books, Hobbies'},
    { 'icon': '💼', 'id': 'WORK', 'sub_list': 'Work,Business,Side Gigs,Commision'},
    { 'icon': '🛠️', 'id': 'MAKE', 'sub_list': 'Dev,Design,Web,RasbPI,AI,PC Support'},
    { 'icon': '👩🏻‍🎓', 'id': 'LEARN', 'sub_list': 'Study, Skills, Languages, Courses'},
]

SIDE_TABS = [  # Tabs down left side of LifePIM - any project goes into one of these groups
    { 'icon': '*', 'id': 'any', 'label': 'Any Project Areas'},

    { 'icon': '🔒', 'id': 'pers', 'label': 'Personal'},
    { 'icon': '💊', 'id': 'health', 'label': 'Health'}, 
    { 'icon': '👪', 'id': 'family', 'label': 'Family'}, 
    { 'icon': '🏈', 'id': 'sport', 'label': 'Sport'}, 
    { 'icon': '🏚️', 'id': 'house', 'label': 'House'}, 
    { 'icon': '🍕', 'id': 'food', 'label': 'Food'}, 
    { 'icon': '🚗', 'id': 'car', 'label': 'Car'}, 
    { 'icon': '🎉', 'id': 'fun', 'label': 'Fun'},  # note that top tabs separate movies,
    { 'icon': '🕹️', 'id': 'games', 'label': 'Games'}, 

    { 'icon': '🖥️', 'id': 'dev', 'label': 'Dev'}, 
    { 'icon': '🖥️', 'id': 'dev/UE5', 'label': 'UE5'}, 
    { 'icon': '🖥️', 'id': 'dev/Python', 'label': 'Python'}, 
    { 'icon': '📐', 'id': 'design', 'label': 'Design'}, 
    { 'icon': '📐', 'id': 'design/write', 'label': 'Writing'}, 
    { 'icon': '📐', 'id': 'design/programs', 'label': 'Program Design'}, 
    { 'icon': '📻', 'id': 'make', 'label': 'Make'}, 
    { 'icon': '📻', 'id': 'make/rasbpi', 'label': 'RasbPI'}, 
    { 'icon': '📻', 'id': 'make/pc', 'label': 'PC'}, 

    { 'icon': '💼', 'id': 'work', 'label': 'Work'}, 
    { 'icon': '💼', 'id': 'work/business', 'label': 'Business'}, 
    { 'icon': '💼', 'id': 'work/side', 'label': 'Side Gigs'}, 

    { 'icon': '👩🏻‍🎓', 'id': 'learn', 'label': 'Learn'}, 
    { 'icon': '🕵', 'id': 'ai', 'label': 'AI'}, 
    { 'icon': '🧰', 'id': 'support', 'label': 'Support'},
    
]



TABS = [  #Tabs across top of LifePIM
    { 'icon': '🏠', 'id': 'home', 'label': 'Overview'},

    { 'icon': '📝', 'id': 'notes', 'label': 'Notes'},
    { 'icon': '☑️', 'id': 'plan', 'label': 'Goals /Plans (WHY)'},
    { 'icon': '🕐', 'id': 'calendar', 'label': 'Calendar (WHEN)'},
    { 'icon': '📘', 'id': 'how', 'label': '(HOW):Blueprint/task template/process/job'},
    { 'icon': '📝', 'id': 'tasks', 'label': 'Tasks (actual list of things to do)'},
    
    { 'icon': '📰', 'id': 'news', 'label': 'News, reddit, twitter, RSS feeds'},
    { 'icon': '📩', 'id': 'comms', 'label': 'Mail, Chat, Social, Messages  📱📲'},
    
    { 'icon': '🗄️', 'id': 'data', 'label': 'Data'},
    { 'icon': '🎮', 'id': 'apps', 'label': 'Apps'},
   
    { 'icon': '📂', 'id': 'files', 'label': 'Files'},
    { 'icon': '🖼️', 'id': 'images', 'label': 'Images'},
    { 'icon': '🎵', 'id': 'music', 'label': 'Music'},
    { 'icon': '🎥', 'id': 'video', 'label': 'Video', },

    { 'icon': '🧱', 'id': '3d', 'label': 'Objects / 3D / Things', },

    { 'icon': '🏆', 'id': 'badges', 'label': 'Badges'},
    { 'icon': '💲', 'id': 'money', 'label': 'Money'},
    { 'icon': '👤', 'id': 'contacts', 'label': 'Contacts (WHO)'},
    { 'icon': '🌏', 'id': 'places', 'label': 'Places (WHERE - real life, URL or virt location)'},
    
    { 'icon': '💻', 'id': 'etl', 'label': 'ETL  🔣'},
    { 'icon': '⌚', 'id': 'jobs', 'label': 'Scheduled Jobs (NO - this should be a recurr event of type:ETL )'},
    
    { 'icon': '📜', 'id': 'logs', 'label': 'Journal / Logs'},
    { 'icon': '⚙', 'id': 'admin', 'label': 'Admin'},
    { 'icon': '🤖', 'id': 'agent', 'label': 'Agent'},

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
    ['calendar', 'type', ['Appointment', 'Event', 'Reminder', 'Logs']],
    ['calendar', 'view', ['Life', 'Year', 'Quarter', 'Month', 'Fortnight', 'Week', 'Day']],
    ['data', 'type', ['Database', 'Spreadsheet', 'Checklist']],
    ['files', 'type', ['Document', 'PDF', 'Presentation']],
    ['files', 'year', ['1980-1989','1990-1999','2000-2009','2010-2019','2020-2029']],
    ['images', 'type', ['Photo', 'Screenshot', 'Drawing']],
    ['images', 'year', ['1980-1989','1990-1999','2000-2009','2010-2019','2020-2029']],
    ['music', 'type', ['Song', 'Album', 'Playlist']],
    ['music', 'genre', ['Rock', 'Techno', 'Classidal', 'Jazz', 'Pop', 'Folk', 'Other']],
    ['music', 'year', ['1980-1989','1990-1999','2000-2009','2010-2019','2020-2029']],
    ['video', 'type', ['Movie', 'Clip', 'Recording']], 
    ['video', 'year', ['1980-1989','1990-1999','2000-2009','2010-2019','2020-2029']],
]   

ui_actions = []    # these are the clickable links that appear per tab / submenu
for tab in TABS:
    if tab['id'] in ['notes','tasks','contacts','etl','calendar','data','files','images','music','video']:
        ui_actions.append([tab['id'], 'Add', 'fn_' + tab['id'] + '_add'])
        sub_menus.append({'root':tab['id'], 'name':'Add'})
    #ui_actions.append([tab['id'], 'Import', 'fn_' + tab['id'] + '_import'])
    #ui_actions.append([tab['id'], 'Generate', 'fn_' + tab['id'] + '_gen'])


project_specific_tables = [
    'car_service_records',
    'car_fuel_logs',
    'health_medical_info',
    'home_utilities',
    'home_repairs',
    'games_collection',
    'work_meetings',
    'shopping_receipts',
    'family_birthdays',
    'food_recipes',
    'admin_warranties',
    'pers_journal',
    'study_courses',
    'design_inspiration',
    'fun_hobbies',
    'web_bookmarks',    
    'business_invoices',
    'dev_bugs',
    'rasbpi_projects',
    'support_warranties',
    'ai_projects',
]

print('TODO - make sure every single CSV file and database table can be mapped to a submenu/project')



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
