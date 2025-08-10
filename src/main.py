
# ----------------------------------------------------------------------------
# FILE: main.py
# ----------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk
import importlib
import sys
import os

# Ensure local package imports work when user splits files
sys.path.insert(0, os.path.abspath('.'))

from config import toolbar_definition, TABS, UI, proj_list
from services.cache_service import load_cache, save_cache

class LifePIM(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LifePIM')
        # compact sizes
        default_font = (UI['font_family'], UI['font_size'])
        self.option_add('*Font', default_font)
        self._build_menu_and_toolbar()
        self._build_main_area()
        self.cache = load_cache()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_menu_and_toolbar(self):
        # Menu
        menubar = tk.Menu(self)
        fileMenu = tk.Menu(menubar, tearoff=0)
        fileMenu.add_command(label='Exit', command=self.quit, accelerator='Ctrl+Q')
        menubar.add_cascade(label='File', menu=fileMenu)

        pimMenu = tk.Menu(menubar, tearoff=0)
        # dynamic actions from toolbar definition
        for item in toolbar_definition:
            name = item[1]
            hide_flag = None
            if len(item) >=5:
                hide_flag = item[4]
            if hide_flag == 'Y':
                continue
            pimMenu.add_command(label=name.title(), command=lambda n=name: self._open_tab_by_id(n))
        menubar.add_cascade(label='PIM', menu=pimMenu)

        self.config(menu=menubar)

        # Toolbar as a frame
        tb = ttk.Frame(self, relief='flat')
        tb.pack(side='top', fill='x')
        for item in toolbar_definition:
            icon, name, func, comment = item[0], item[1], item[2], item[3]
            hide_flag = None
            if len(item) >=5:
                hide_flag = item[4]
            if hide_flag == 'Y':
                continue
            b = ttk.Button(tb, text=icon, width=2, command=lambda n=name: self._open_tab_by_id(n))
            b.pack(side='left', padx=UI['toolbar_button_padx'], pady=UI['toolbar_button_pady'])

        # Search on right
        search_frame = ttk.Frame(tb)
        search_frame.pack(side='right')
        self.search_var = tk.StringVar()
        e = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        e.bind('<Return>', lambda e: self._do_search())
        e.pack(side='right', padx=2, pady=2)

    def _build_main_area(self):
        # Status bar at bottom
        self.statusbar = ttk.Frame(self)
        self.statusbar.pack(side='bottom', fill='x')
        self.status_left = ttk.Label(self.statusbar, text='Ready')
        self.status_left.pack(side='left')
        self.status_right = ttk.Label(self.statusbar, text='')
        self.status_right.pack(side='right')

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)
        # load tabs from TABS config
        for tab in TABS:
            try:
                module = importlib.import_module(tab['module'])
                ViewClass = getattr(module, tab['class'])
                frame = ViewClass(self.notebook, services=None)
                self.notebook.add(frame, text=tab['label'])
            except Exception as e:
                f = ttk.Frame(self.notebook)
                ttk.Label(f, text=f'Failed to load {tab.get("label")}\n{e}').pack(fill='both', expand=True)
                self.notebook.add(f, text=tab['label'])

    def _open_tab_by_id(self, idname):
        # Attempt to find tab with that id (match on label or id)
        for i in range(len(self.notebook.tabs())):
            tab_text = self.notebook.tab(i, option='text')
            if tab_text.lower() == idname.lower() or tab_text.lower().startswith(idname.lower()):
                self.notebook.select(i)
                return
        # fallback: try to open first tab
        self.notebook.select(0)

    def _do_search(self):
        q = self.search_var.get()
        self.status_left.config(text=f'Search: {q}')
        # fast cached search example - real implementation should call services
        results = []
        if hasattr(self, 'cache'):
            # naive search of cached keys
            for k in self.cache.keys():
                if q.lower() in str(k).lower():
                    results.append(k)
        print('Search results:', results)

    def _on_close(self):
        save_cache(self.cache)
        self.destroy()

if __name__ == '__main__':
    app = LifePIM()
    app.geometry('1100x700')
    app.mainloop()
    