# ----------------------------------------------------------------------------
# FILE: views/notes.py
# ----------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk

class NotesView(ttk.Frame):
    def __init__(self, master, services=None, **kwargs):
        super().__init__(master, **kwargs)
        # Left, mid, right panes
        paned = ttk.Panedwindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True)

        left = ttk.Frame(paned, width=200)
        paned.add(left, weight=1)
        mid = ttk.Frame(paned, width=400)
        paned.add(mid, weight=3)
        right = ttk.Frame(paned, width=150)
        paned.add(right, weight=1)

        # LH_Top - Fav Folders
        fav = ttk.LabelFrame(left, text='Fav Folders')
        fav.pack(fill='x', padx=2, pady=1)
        from config import FAV_FOLDERS
        lb = tk.Listbox(fav, height=3)
        for p in FAV_FOLDERS:
            lb.insert('end', p)
        lb.pack(fill='x')

        # LH_Mid - folders
        folders = ttk.LabelFrame(left, text='Folders')
        folders.pack(fill='both', expand=True, padx=2, pady=1)
        folders_lb = tk.Listbox(folders)
        folders_lb.pack(fill='both', expand=True)

        # LH_Lower - files
        files = ttk.LabelFrame(left, text='Files')
        files.pack(fill='x', padx=2, pady=1)
        files_lb = tk.Listbox(files, height=6)
        files_lb.pack(fill='x')

        # MidPane - editor (compact)
        editor = tk.Text(mid, wrap='word', height=20)
        editor.pack(fill='both', expand=True, padx=2, pady=2)

        # RightHandPane - stats
        stats = ttk.LabelFrame(right, text='Stats')
        stats.pack(fill='both', expand=True, padx=2, pady=1)
        self.word_count = ttk.Label(stats, text='Words: 0')
        self.word_count.pack(anchor='w', padx=2, pady=1)



"""
# notes.py

def build_screen(root):

    print('building screen_notes...')

    txt = 'welcome to notes\n'
    root.append('hello')
"""