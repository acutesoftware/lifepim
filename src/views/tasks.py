
# ----------------------------------------------------------------------------
# FILE: views/tasks.py
# ----------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk

class TasksView(ttk.Frame):
    def __init__(self, master, services=None, **kwargs):
        super().__init__(master, **kwargs)
        lbl = ttk.Label(self, text='Tasks List')
        lbl.pack(anchor='w')
        columns = ('id','title','project','status')
        self.tv = ttk.Treeview(self, columns=columns, show='headings', height=25)
        for c in columns:
            self.tv.heading(c, text=c)
            self.tv.column(c, width=80, anchor='w')
        self.tv.pack(fill='both', expand=True)
        # Example: Add some sample data
        sample_tasks = [
            (1, 'Buy groceries', 'Personal', 'Open'),
            (2, 'Finish report', 'Work', 'In Progress'),
            (3, 'Call plumber', 'Home', 'Done'),
        ]
        for task in sample_tasks:
            self.add_task(*task)

    def add_task(self, id, title, project, status):
        self.tv.insert('', 'end', values=(id, title, project, status))


"""
# notes.py

from tkinter import Frame, Label, Entry, Button, font
from tkinter import LEFT, RIGHT, TOP, BOTTOM

def build_screen(root):
    console_frame = Frame(root, bg='white', width=850, height=250, pady=1)
    console_frame.grid(row=0, column=0, sticky="nesw")
    print('building screen_notes...')


    txt = 'Task List\n'
    console_label = Label(root, text=txt, bg='white', foreground='blue', justify=LEFT)
    console_label.grid(row=0, column=0)
    console_entry = Entry(root,  bg='gray12', foreground='green')
    console_entry.grid(row=1, column=0, sticky="ew")


"""