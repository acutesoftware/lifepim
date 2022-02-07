#!/usr/bin/python3
# coding: utf-8
# config.py

import os

user_folder = r'\\FANGORN\user\duncan\LifePIM_Data'
#user_folder = r'D:\docs\LIFEPIM_DATA_CACHE'
#user_folder = r'D:\dev\src\lifepim\lifepim\SAMPLE_DATA'


port_num=9741           # port to browse to, eg. http://127.0.0.1:9741/
WEB_VERSION = "DEV"     # to show debug lines in web server

logon_file = os.path.join(user_folder, 'configuration', 'lifepim.par')
data_folder = os.path.join(user_folder, 'DATA')
index_folder = os.path.join(user_folder, 'index')
calendar_folder = os.path.join(user_folder, 'calendar')
folder_list_file =  os.path.join(user_folder, 'configuration', 'folders.lis')

local_folder_theme = os.path.join(os.getcwd(), 'interfaces')

base_url = 'https://www.lifepim.com'    # testing, point to live site for API
base_url = '127.0.0.1:5000'             # running local (default)

image_xtn_list = ['*.jpg', '*.JPG', '*.PNG', '*.png']

toolbar_definition =  [  # [icon, name, function, comments]
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


file_startup_path = r"D:\dev\src\worldbuild"
file_startup_path = r"D:\dev\src\lifepim\lifepim\SAMPLE_DATA"

def get_conn_str():
	conn_str = {}
	with open(logon_file, 'r') as f:
		conn_str['host'] = f.readline().strip(' ').strip('\n')
		conn_str['user'] = f.readline().strip(' ').strip('\n')
		conn_str['pass'] = f.readline().strip(' ').strip('\n')
		conn_str['db'] = f.readline().strip(' ').strip('\n')

	return conn_str

def get_index_filename_from_path(fldr):
    """
    mod_cfg.get_index_filename_from_path
    """
    clean_name =  fldr.replace('\\', '_').replace(':',';')
    return os.path.join(user_folder, 'index', 'raw_filelist_' + clean_name + '.csv')

def get_path_from_index_filename(fname):
    """
    mod_cfg.get_path_from_index_filename
    """
    clean_name =  fname.replace('_', '\\').replace(';', ':',)
    display_name = clean_name[len(index_folder)+14:][:-4]
    return display_name


def read_user_setting(setting):
    with open('settings.cfg', 'r') as fip:
        for line in fip:
            if setting == line[0:len(setting)]:
                return line.strip('\n')[len(setting)+1:]


