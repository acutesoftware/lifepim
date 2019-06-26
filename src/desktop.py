#!/usr/bin/python3
# coding: utf-8
# desktop.py 

import os 
import sys
import tkinter as tk
import tkinter as ttk
from tkcalendar import Calendar, DateEntry
from tkinter import Frame, Label, Entry, Button

import config

def main():
    print('starting desktop via ' + config.base_url)
    app = simpleapp_tk(None)
    app.title('MDM Desktop')
    app.geometry('750x500')
    build_screen_home(app)

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


class simpleapp_tk(tk.Tk):
    def __init__(self,parent):
        tk.Tk.__init__(self,parent)
        self.parent = parent
        self.screenWidth = 999 # self.winfo_screenwidth()
        self.screenHeight = 666 # self.winfo_screenheight()
        self.appWidth = 870
        self.appHeight = 525
        
        self.initialize()

    def initialize(self):
        #top = tk.Toplevel(self.master)  # wrong - this makes a new window

        #btn = tk.Button(self, text="Click Me", bg="orange", fg="red")   
        #btn.grid(column=1, row=0) 
        pass
 

    def do_popup(self):
        # display the popup menu
        self.popup.post(self.screenWidth - self.appWidth + 60, self.screenHeight - self.appHeight - 95)

    def cmd_infolink_help(self):
        print('help')

    def cmd_infolink_home(self):
        print('home')

    def cmd_infolink_exit(self):
        # shutting down logging
        print('exiting...')
        sys.exit(0)




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


def build_screen_home(root):
    """
    builds the GUI using the home functionality
    """
    # create all of the main containers
    toolbar_frame = Frame(root, bg='cyan', width=450, height=30, pady=3)
    center = Frame(root, bg='gray2', width=50, height=40, padx=3, pady=3)
    btm_frame = Frame(root, bg='black', width=450, height=45, pady=3)
    status_frame = Frame(root, bg='gray2', width=450, height=20, pady=3)

    # layout all of the main containers
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)

    toolbar_frame.grid(row=0, sticky="ew")
    center.grid(row=1, sticky="nsew")
    btm_frame.grid(row=3, sticky="ew")
    status_frame.grid(row=4, sticky="ew")


    # create the center widgets
    center.grid_rowconfigure(0, weight=1)
    center.grid_columnconfigure(1, weight=1)

    ctr_left = Frame(center, bg='blue', width=200, height=390)
    ctr_mid = Frame(center, bg='yellow', width=250, height=390, padx=3, pady=3)
    ctr_right = Frame(center, bg='green', width=100, height=390, padx=3, pady=3)

    ctr_left.grid(row=0, column=0, sticky="ns")
    ctr_mid.grid(row=0, column=1, sticky="nsew")
    ctr_right.grid(row=0, column=2, sticky="ns")



    cal_frame = Frame(ctr_left, bg='blue', width=300, height=390)
    cal = wCalendar(cal_frame)
    cal_frame.grid(row=0, column=0)

    # add labels (just to indicate how to attach things)
    event_label = Label(ctr_left, text='Events goes here')
    event_label.grid(row=1, column=0)
    note_label = Label(ctr_mid, text='Notes go here')
    note_label.grid(row=1, column=0)

    folder_label = Label(ctr_right, text='Folder list')
    folder_label.grid(row=1, column=0)

    console_label = Label(btm_frame, text='console', bg='black', foreground='green')
    console_label.grid(row=1, column=0)

    status_label = Label(status_frame, text='Status Bar')
    status_label.grid(row=1, column=0)

    # populate the toolbar
    add_toolbar_button(toolbar_frame, 0, 'Home', click_button)
 

def add_toolbar_button(window, pos, txt, command):
    btn = Button(window, text=txt, command=command)
    btn.grid(column=pos, row=0)    


def click_button():
    print('button clicked')

if __name__ == "__main__":
    main()


if __name__ == '__main__':  
    main()        