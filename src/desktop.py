#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys
import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar, DateEntry
from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

#from tkinter import Menu

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

from interfaces import lp_screen

import config

def main():
    print('starting desktop via ' + config.base_url)
    #app = simpleapp_tk(None)
    app = tk.Tk()
    app.title('LifePIM Desktop')
    app.geometry('950x600')
    app.tk.call('encoding', 'system', 'unicode')


    print('starting desktop...')


    lp_screen.init_screen(app)



    app.mainloop()





if __name__ == '__main__':  
    main()        