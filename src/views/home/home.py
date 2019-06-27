# home.py

from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

def build_screen_home(root):
    console_frame = Frame(root, bg='black', width=850, height=250, pady=1)
    console_frame.grid(row=0, column=0, sticky="nesw")



    txt = 'duncan@TREEBEARD:~/dev/src/python/LifePIM/src$ ls -l\ntotal 0\nduncan@TREEBEARD:~/dev/src/python/LifePIM/src$\n'
    txt += '$pwd\n~/dev/src/python/LifePIM/src/new\nls -l\ntotal 0\n$\n'
    console_label = Label(root, text=txt, bg='black', foreground='green', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")


