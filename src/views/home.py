# ----------------------------------------------------------------------------
# FILE: views/home.py
# ----------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk

class HomeView(ttk.Frame):
    def __init__(self, master, services=None, **kwargs):
        super().__init__(master, **kwargs)
        lbl = ttk.Label(self, text='LifePIM Overview', anchor='w')
        lbl.pack(fill='x', padx=2, pady=2)
        # Add a dense grid of summary widgets
        grid = ttk.Frame(self)
        grid.pack(fill='both', expand=True)
        for i in range(3):
            for j in range(3):
                f = ttk.Frame(grid, borderwidth=1, relief='solid')
                f.grid(row=i, column=j, sticky='nsew', padx=1, pady=1)
                ttk.Label(f, text=f'Summary {i},{j}').pack(anchor='w', padx=2, pady=2)
        for i in range(3):
            grid.columnconfigure(i, weight=1)
        for i in range(3):
            grid.rowconfigure(i, weight=1)




"""
# home.py

from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM


def build_screen(root):
    console_frame = Frame(root, bg='black', width=850, height=250, pady=1)
    console_frame.grid(row=0, column=0, sticky="nesw")

    print('building screen_HOME...')

    txt = 'Welcome to LifePIM Desktop\n\n\nduncan@TREEBEARD:~/dev/src/python/LifePIM/src$ ls -l\ntotal 0\nduncan@TREEBEARD:~/dev/src/python/LifePIM/src$\n'
    txt += '$pwd\n~/dev/src/python/LifePIM/src/new\nls -l\ntotal 0\n$\n'
    console_label = Label(root, text=txt, bg='black', foreground='green', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")


"""