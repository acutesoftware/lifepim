#!/usr/bin/python3
# coding: utf-8
# lp_screen.py 

import os 
import sys
import tkinter as tk
from tkinter import ttk
from tkcalendar import Calendar, DateEntry
from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

from tkinter import Menu


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



def init_screen(app):
    """
    High level function called to build the main GUI in tkinter
    """
    build_main_layout(app)
    print('finished building layout')
    #screen_build_menu(app)
    
def donothing():
   filewin = Toplevel(app)
   button = Button(filewin, text="Do nothing button")
   button.pack()


def screen_build_menu(app):

    ##############################################################################
    ## MENU 

    menubar = Menu(app)
    filemenu = Menu(menubar, tearoff=0)
    filemenu.add_command(label="New", command=donothing)
    filemenu.add_command(label="Open", command=donothing)
    filemenu.add_command(label="Save", command=donothing)
    filemenu.add_command(label="Save as...", command=donothing)
    filemenu.add_command(label="Close", command=donothing)

    filemenu.add_separator()

    filemenu.add_command(label="Exit", command=app.quit)
    menubar.add_cascade(label="File", menu=filemenu)
    editmenu = Menu(menubar, tearoff=0)
    editmenu.add_command(label="Undo", command=donothing)

    editmenu.add_separator()

    editmenu.add_command(label="Cut", command=donothing)
    editmenu.add_command(label="Copy", command=donothing)
    editmenu.add_command(label="Paste", command=donothing)
    editmenu.add_command(label="Delete", command=donothing)
    editmenu.add_command(label="Select All", command=donothing)

    menubar.add_cascade(label="Edit", menu=editmenu)
    helpmenu = Menu(menubar, tearoff=0)
    helpmenu.add_command(label="Help Index", command=donothing)
    helpmenu.add_command(label="About...", command=donothing)
    menubar.add_cascade(label="Help", menu=helpmenu)

    app.config(menu=menubar)
    app.configure(menu = menubar)

    ##############################################################################

def build_main_layout(app):

    

    # create all of the main containers
    left_frame = Frame(app, bg='gray14', width=80, height=600)
    mid_frame = Frame(app, bg='gray10', width=350, height=600, padx=1, pady=1)
    right_frame = Frame(app, bg='gray14', width=250, height=600, padx=1, pady=1)
    status_frame = Frame(app, bg='deep sky blue', width=455, height=20, pady=1)

    # layout all of the main containers
    app.grid_rowconfigure(0, weight=100)
    app.grid_rowconfigure(1, weight=0)

    app.grid_columnconfigure(0, weight=0)
    app.grid_columnconfigure(1, weight=100)
    app.grid_columnconfigure(2, weight=0)


    left_frame.grid(row=0, column=0, sticky="ns")
    mid_frame.grid(row=0, column=1, sticky="nsew")
    right_frame.grid(row=0, column=2, sticky="ns")
    status_frame.grid(row=1, sticky="ew")
    status_label = Label(status_frame, text='Status Bar',  bg='deep sky blue')
    status_label.grid(row=1, column=0)

    folder_label = Label(left_frame, text='Folder list')
    folder_label.grid(row=1, column=0)






    n = ttk.Notebook(mid_frame)
    n.pack(expand=1, fill='both')

    tab1 = ttk.Frame(n)   # first page, which would get widgets gridded into it
    tab2 = ttk.Frame(n)   # second page
    tab3 = ttk.Frame(n)   
    tab4 = ttk.Frame(n)   
    tab5 = ttk.Frame(n)   
    tab6 = ttk.Frame(n)   
    tab7 = ttk.Frame(n)   
    tab8 = ttk.Frame(n)   
    tab9 = ttk.Frame(n)   
    tab10 = ttk.Frame(n)   
    tab11 = ttk.Frame(n)   
    tab12 = ttk.Frame(n)   
    tab13 = ttk.Frame(n)   
    tab14 = ttk.Frame(n)   
    tab15 = ttk.Frame(n)   
    tab16 = ttk.Frame(n)   

    tab1.grid(row=0, sticky="nsew")
    tab2.grid(row=0, sticky="nsew")
    tab3.grid(row=0, sticky="nsew")
    tab4.grid(row=0, sticky="nsew")
    tab5.grid(row=0, sticky="nsew")
    tab6.grid(row=0, sticky="nsew")
    tab7.grid(row=0, sticky="nsew")
    tab8.grid(row=0, sticky="nsew")
    tab9.grid(row=0, sticky="nsew")
    tab10.grid(row=0, sticky="nsew")
    tab11.grid(row=0, sticky="nsew")
    tab12.grid(row=0, sticky="nsew")
    tab13.grid(row=0, sticky="nsew")
    tab14.grid(row=0, sticky="nsew")
    tab15.grid(row=0, sticky="nsew")
    tab16.grid(row=0, sticky="nsew")

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
    n.add(tab13, text='      ')
    n.add(tab14, text='   ✋   ')
    n.add(tab15, text='   ⚙   ')
    n.add(tab16, text='   ?   ')



    print('init finished, about to build the tabs')
    
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

