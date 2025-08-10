# notes.py

from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

def build_screen(root):
    console_frame = Frame(root, bg='white', width=850, height=250, pady=1)
    console_frame.grid(row=0, column=0, sticky="nesw")
    print('building screen_images...')


    txt = 'Images\n'
    console_label = Label(root, text=txt, bg='white', foreground='blue', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")


