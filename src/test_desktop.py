#!/usr/bin/python3
# coding: utf-8
# desktop.py 


import tkinter as tk
from tkinter import ttk
from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM


def main():
    app = tk.Tk() 
    app.title('LifePIM Desktop - Testing Tkinter')
    app.geometry('750x500')


    n = ttk.Notebook(app)
    n.grid()
    tab1 = ttk.Frame(n)   # first page, which would get widgets gridded into it
    tab2 = ttk.Frame(n)   # second page
    tab3 = ttk.Frame(n)   # second page
    tab4 = ttk.Frame(n)   # second page

    tab1.grid(row=0, sticky="nsew")
    tab2.grid(row=0, sticky="nsew")
    n.add(tab1, text='Home')
    n.add(tab2, text='Calendar')
    n.add(tab2, text='Task')
    n.add(tab2, text='Notes')


    app.mainloop()



if __name__ == '__main__':  
    main()        


