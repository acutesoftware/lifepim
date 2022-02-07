#!/usr/bin/python3
# coding: utf-8
# lp_screen.py 
# Icons for QT5 are stored
# C:\Python37-32\Lib\site-packages\PyQt5\Qt5\qml\QtQuick3D\designer\images
# C:\Python37-32\Lib\site-packages\PyQt5\Qt5\qml\QtQuick\Controls\Styles\Base\images
# C:\Python37-32\Lib\site-packages\PyQt5\Qt5\qml\QtQuick\Controls.2\designer\images
# C:\Python37-32\Lib\site-packages\PyQt5\Qt5\qml\QtQuick3D\designer\images
# N:\DATA\3D\PURCHASED\GUI_user_interface\humble_bundle_2021_GUI\guiiconspack1\icon set 700\icon (80 Х 80)\101-200
import os 
import sys

from views.home import home as home
from views.calendar import calendar as calendar
from views.tasks import tasks as tasks
from views.notes import notes as notes
from views.contacts import contacts as contacts
from views.places import places as places
from views.data import data as data
from views.badges import badges as badges
from views.money import money as money
from views.music import music as music
from views.images import images as images
from views.apps import apps as apps
from views.files import files as files
from views.admin import admin as admin
from views.options import options as options
from views.about import about as about

import config as mod_cfg



def init_screen(app):
    """
    High level function called to build the main GUI in tkinter
    """
    icon_files_djm = load_theme_icons('theme_djm.txt')
    print(get_theme_icon(icon_files_djm, 'exit'))
    build_main_layout(app)
    screen_build_menu(app)

    
def donothing():
   filewin = Toplevel(app)
   button = Button(filewin, text="Do nothing button")
   button.pack()

def load_theme_icons(theme_name):
    icons = {}
    with open(theme_name, 'r') as fip:
        for line in fip:
            #print(' line = ' + line)
            if line.strip() != '':
                if line[0:1] != '#':
                    nme, icon = line.strip('\n').split('=')
                    #print('nme=' + nme + ', icon = ' + icon)
                    icons[nme] = icon
    #print('loaded theme : ' + theme_name)
    #print(icons)
    return icons

def get_theme_icon(theme_list, icon_name):
    try:
        return theme_list[icon_name]
    except:
        #print('Icon ' + icon_name + ' does not exist in theme' )
        return ''


def screen_build_menu(app):

    ##############################################################################
    ## MENU 
    pass

    ##############################################################################

def build_main_layout_OLD(app):
    # create all of the main containers
    n = []
    """
    n.add(tab1, text='   ❗   ')
    n.add(tab2, text='   ➀   ')
    n.add(tab3, text='   ✔   ')
    n.add(tab4, text='   ✍   ')
    n.add(tab5, text='   ✉   ')
    n.add(tab6, text='   ✈   ')
    n.add(tab7, text='   ▦   ')
    n.add(tab8, text='   ✮   ')
    n.add(tab9, text='   $   ')
    n.add(tab10, text='   ♬   ')
    n.add(tab11, text='   ✾   ')
    n.add(tab12, text='   ☑   ')
    n.add(tab13, text='   F   ')
    n.add(tab14, text='   ✋   ')
    n.add(tab15, text='   ⚙   ')
    n.add(tab16, text='   ?   ')

    # Note that there is probably no point having a dynamic list
    # of tabs because each tab has specific code that needs to 
    # work with other tabs.
    home.build_screen(tab1)
    calendar.build_screen(tab2)
    tasks.build_screen(tab3)
    notes.build_screen(tab4)
    contacts.build_screen(tab5)
    places.build_screen(tab6)
    data.build_screen(tab7)
    badges.build_screen(tab8)
    money.build_screen(tab9)
    music.build_screen(tab10)
    images.build_screen(tab11)
    apps.build_screen(tab12)
    files.build_screen(tab13)
    admin.build_screen(tab14)
    options.build_screen(tab15)
    about.build_screen(tab16)
    

    #build_screen_home(tab1)
    #build_screen_calendar(tab2)

    """
