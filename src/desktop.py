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

import config

def main():
    print('starting desktop via ' + config.base_url)
    #app = simpleapp_tk(None)
    app = tk.Tk()
    app.title('LifePIM Desktop')
    app.geometry('750x500')
    app.tk.call('encoding', 'system', 'unicode')

    """
    # Toolbar (works- IFF you dont use the tabs notebook below
    toolbar_frame = Frame(app, bg='gray', width=9350, height=20, pady=1)
    toolbar_frame.grid(row=0, sticky="ew")
    # populate the toolbar
    add_toolbar_buttons(toolbar_frame)
    """


    # create all of the main containers
    left_frame = Frame(app, bg='gray14', width=80, height=600)
    mid_frame = Frame(app, bg='gray10', width=350, height=600, padx=1, pady=1)
    right_frame = Frame(app, bg='gray14', width=250, height=600, padx=1, pady=1)
    status_frame = Frame(app, bg='gray', width=450, height=20, pady=1)

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
    status_label = Label(status_frame, text='Status Bar')
    status_label.grid(row=1, column=0)







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

    n.add(tab1, text='  ❗  ')
    n.add(tab2, text='  ➀  ')
    n.add(tab3, text='  ✔  ')
    n.add(tab4, text='  ✍  ')
    n.add(tab5, text='  ✉  ')
    n.add(tab6, text='  ✈  ')
    n.add(tab7, text='  ▦  ')
    n.add(tab8, text='  ✮  ')
    n.add(tab9, text='  $  ')
    n.add(tab10, text='  ♬  ')
    n.add(tab11, text='  ✾  ')
    n.add(tab12, text='  ☑  ')
    n.add(tab13, text='    ')
    n.add(tab14, text='  ✋  ')
    n.add(tab15, text='  ⚙  ')
    n.add(tab16, text='  ?  ')




    build_screen_calendar(tab2)


    #build_screen_home(tab1)
    #build_screen_calendar(tab2)

    app.mainloop()


    """  NOTE - code below works, see https://stackoverflow.com/questions/34276663/tkinter-gui-layout-using-frames-and-grid
    # create all of the main containers
    top_frame = Frame(app, bg='cyan', width=450, height=50, pady=3)
    center = Frame(app, bg='gray2', width=50, height=40, padx=3, pady=3)
    btm_frame = Frame(app, bg='white', width=450, height=45, pady=3)
    btm_frame2 = Frame(app, bg='lavender', width=450, height=60, pady=3)

    # layout all of the main containers
    app.grid_rowconfigure(1, weight=1)
    app.grid_columnconfigure(0, weight=1)

    top_frame.grid(row=0, sticky="ew")
    center.grid(row=1, sticky="nsew")
    btm_frame.grid(row=3, sticky="ew")
    btm_frame2.grid(row=4, sticky="ew")

    # create the widgets for the top frame
    model_label = Label(top_frame, text='Model Dimensions')
    width_label = Label(top_frame, text='Width:')
    length_label = Label(top_frame, text='Length:')
    entry_W = Entry(top_frame, background="pink")
    entry_L = Entry(top_frame, background="orange")
    # layout the widgets in the top frame
    model_label.grid(row=0, columnspan=3)
    width_label.grid(row=1, column=0)
    length_label.grid(row=1, column=2)
    entry_W.grid(row=1, column=1)
    entry_L.grid(row=1, column=3)

    # create the center widgets
    center.grid_rowconfigure(0, weight=1)
    center.grid_columnconfigure(1, weight=1)

    ctr_left = Frame(center, bg='blue', width=100, height=190)
    ctr_mid = Frame(center, bg='yellow', width=250, height=190, padx=3, pady=3)
    ctr_right = Frame(center, bg='green', width=100, height=190, padx=3, pady=3)

    ctr_left.grid(row=0, column=0, sticky="ns")
    ctr_mid.grid(row=0, column=1, sticky="nsew")
    ctr_right.grid(row=0, column=2, sticky="ns")
    """



class wCalendar(object):
    def __init__(self, top):
        #self.master = master
        #top = tk.Toplevel(master)
        cal = Calendar(top, selectmode='none')
        date = cal.datetime.today() + cal.timedelta(days=2)
        cal.calevent_create(date, 'Hello World', 'message')
        cal.calevent_create(date, 'Reminder 2', 'reminder')
        cal.calevent_create(date + cal.timedelta(days=-2), 'Reminder 1', 'reminder')
        cal.calevent_create(date + cal.timedelta(days=3), 'Message', 'message')

        cal.tag_config('reminder', background='red', foreground='yellow')
        cal.pack(fill="both", expand=True)
        #cal.pack(fill="none", expand=False)
        #ttk.Label(top, text="Hover over the events.").pack()



def build_screen_calendar(root):
    cal_frame = Frame(root, bg='blue', width=300, height=390)
    cal = wCalendar(cal_frame)
    cal_frame.grid(row=0, column=0)



def build_screen_home(root):






    console_frame = Frame(ctr_left, bg='black', width=250, height=250, pady=1)
    console_frame.grid(row=1, column=0, sticky="nw")


    # add labels (just to indicate how to attach things)
    event_label = Label(ctr_left, text='Events goes here')
    event_label.grid(row=2, column=0)
    note_label = Label(ctr_mid, text='Notes go here')
    note_label.grid(row=1, column=0)

    folder_label = Label(ctr_right, text='Folder list')
    folder_label.grid(row=1, column=0)
    txt = 'duncan@TREEBEARD:~/dev/src/python/LifePIM/src$ ls -l\ntotal 0\nduncan@TREEBEARD:~/dev/src/python/LifePIM/src$\n'
    txt = '$pwd\n~/dev/src/python/LifePIM/src/new\nls -l\ntotal 0\n$\n'
    console_label = Label(console_frame, text=txt, bg='black', foreground='green', justify=LEFT)
    console_label.grid(row=1, column=0)
    console_entry = Entry(console_frame,  bg='gray12', foreground='green')
    console_entry.grid(row=2, column=0, sticky="ew")




def add_toolbar_buttons(window):
    # LifePIM Toolbar definitions for Tkinter
    tb_font = font.Font(family='Helvetica', size=30, weight='bold')

    btn1 = Button(window, text='❗', command=button_click_tb_home)
    btn1.font = tb_font
    btn1.grid(column=0, row=0)

    btn2 = Button(window, text='➀', command=button_click_tb_calendar)
    btn2.font = tb_font
    btn2.grid(column=1, row=0)

    btn3 = Button(window, text='✔', command=button_click_tb_tasks)
    btn3.font = tb_font
    btn3.grid(column=2, row=0)

    btn4 = Button(window, text='✍', command=button_click_tb_notes)
    btn4.font = tb_font
    btn4.grid(column=3, row=0)

    btn5 = Button(window, text='✉', command=button_click_tb_contacts)
    btn5.font = tb_font
    btn5.grid(column=4, row=0)

    btn6 = Button(window, text='✈', command=button_click_tb_places)
    btn6.font = tb_font
    btn6.grid(column=5, row=0)

    btn7 = Button(window, text='▦', command=button_click_tb_data)
    btn7.font = tb_font
    btn7.grid(column=6, row=0)

    btn8 = Button(window, text='✮', command=button_click_tb_badges)
    btn8.font = tb_font
    btn8.grid(column=7, row=0)

    btn9 = Button(window, text='$', command=button_click_tb_money)
    btn9.font = tb_font
    btn9.grid(column=8, row=0)

    btn10 = Button(window, text='♬', command=button_click_tb_music)
    btn10.font = tb_font
    btn10.grid(column=9, row=0)

    btn11 = Button(window, text='✾', command=button_click_tb_images)
    btn11.font = tb_font
    btn11.grid(column=10, row=0)

    btn12 = Button(window, text='☑', command=button_click_tb_apps)
    btn12.font = tb_font
    btn12.grid(column=11, row=0)

    btn13 = Button(window, text='', command=button_click_tb_files)
    btn13.font = tb_font
    btn13.grid(column=12, row=0)

    btn14 = Button(window, text='✋', command=button_click_tb_admin)
    btn14.font = tb_font
    btn14.grid(column=13, row=0)

    btn15 = Button(window, text='⚙', command=button_click_tb_options)
    btn15.font = tb_font
    btn15.grid(column=14, row=0)

    btn16 = Button(window, text='?', command=button_click_tb_about)
    btn16.font = tb_font
    btn16.grid(column=15, row=0)

# Function handling for LifePIM Toolbar clicks
def button_click_tb_home():
    """ user clicked toolbar home"""
    print('user clicked toolbar home')

def button_click_tb_calendar():
    """ user clicked toolbar calendar"""
    print('user clicked toolbar calendar')

def button_click_tb_tasks():
    """ user clicked toolbar tasks"""
    print('user clicked toolbar tasks')

def button_click_tb_notes():
    """ user clicked toolbar notes"""
    print('user clicked toolbar notes')

def button_click_tb_contacts():
    """ user clicked toolbar contacts"""
    print('user clicked toolbar contacts')

def button_click_tb_places():
    """ user clicked toolbar places"""
    print('user clicked toolbar places')

def button_click_tb_data():
    """ user clicked toolbar data"""
    print('user clicked toolbar data')

def button_click_tb_badges():
    """ user clicked toolbar badges"""
    print('user clicked toolbar badges')

def button_click_tb_money():
    """ user clicked toolbar money"""
    print('user clicked toolbar money')

def button_click_tb_music():
    """ user clicked toolbar music"""
    print('user clicked toolbar music')

def button_click_tb_images():
    """ user clicked toolbar images"""
    print('user clicked toolbar images')

def button_click_tb_apps():
    """ user clicked toolbar apps"""
    print('user clicked toolbar apps')

def button_click_tb_files():
    """ user clicked toolbar files"""
    print('user clicked toolbar files')

def button_click_tb_admin():
    """ user clicked toolbar admin"""
    print('user clicked toolbar admin')

def button_click_tb_options():
    """ user clicked toolbar options"""
    print('user clicked toolbar options')

def button_click_tb_about():
    """ user clicked toolbar about"""
    print('user clicked toolbar about')





if __name__ == '__main__':  
    main()        