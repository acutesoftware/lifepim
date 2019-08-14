# notes.py

import os
from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

def build_screen(root):
    print('building screen_admin...')


    txt = 'Admin Page\n' + get_local_pc_list()

    console_label = Label(root, text=txt, bg='white', foreground='blue', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")



def get_local_pc_list():
    txt = ''
    out = os.popen('ip neigh').read().splitlines()
    for i, line in enumerate(out, start=1):
        ip = line.split(' ')[0]
        h = os.popen('host {}'.format(ip)).read()
        hostname = h.split(' ')[-1]
        txt += ip + ' ' + hostname.strip() + '\n'
    return txt
    
