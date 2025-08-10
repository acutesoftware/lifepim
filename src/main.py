
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

from config import toolbar_definition, TABS, UI, proj_list, style_name
import config as cfg


from services.cache_service import load_cache, save_cache

class LifePIM(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LifePIM')
        if style_name == 'clam':
            # Set modern Style
            style = ttk.Style(self)
            style.theme_use('alt')  # clam but Try 'vista' or 'alt' if you prefer
            style.configure('TNotebook.Tab',
                padding=[8, 2],
                font=('Segoe UI', 10),
                background='#f0f0f0',
                foreground='#333333',
            )
            style.map('TNotebook.Tab',
                background=[('selected', '#e0e0e0')],
                foreground=[('selected', '#0078d7')],
            )        
            default_font = (UI['font_family'], UI['font_size'])
            self.option_add('*Font', default_font)

        elif style_name == 'dark':
            # Dark mode Style
            style = ttk.Style(self)
            style.theme_use('clam')
            dark_bg = '#23272e'
            dark_fg = '#e0e0e0'
            accent = '#0078d7'
            tab_selected_bg = '#2d323b'
            tab_selected_fg = '#ffffff'

            style.configure('.', background=dark_bg, foreground=dark_fg)
            style.configure('TNotebook', background=dark_bg, borderwidth=0)
            style.configure('TNotebook.Tab',
                padding=[8, 2],
                font=('Segoe UI', 10),
                background=dark_bg,
                foreground=dark_fg,
            )
            style.map('TNotebook.Tab',
                background=[('selected', tab_selected_bg)],
                foreground=[('selected', accent)],
            )
            style.configure('TFrame', background=dark_bg)
            style.configure('TLabel', background=dark_bg, foreground=dark_fg)
            style.configure('TButton', background=dark_bg, foreground=dark_fg)
            style.map('TButton',
                background=[('active', '#333a45')],
                foreground=[('active', accent)],
            )
            style.configure('TEntry', fieldbackground='#181b20', foreground=dark_fg)
            style.configure('TMenubutton', background=dark_bg, foreground=dark_fg)
            style.configure('TMenu', background=dark_bg, foreground=dark_fg)

            # compact sizes
            default_font = (UI['font_family'], UI['font_size'])
            self.option_add('*Font', default_font)
            self.option_add('*Background', dark_bg)
            self.option_add('*Foreground', dark_fg)
            self.option_add('*Entry.Background', '#181b20')
            self.option_add('*Entry.Foreground', dark_fg)
        else:
            # compact sizes
            default_font = (UI['font_family'], UI['font_size'])
            self.option_add('*Font', default_font)


        # Force large text for icons (if you want colour - connvert to PNG)
        style.configure('TNotebook.Tab',
        padding=[8, 4],
        font=(cfg.tab_font_name, cfg.tab_font_size, cfg.tab_font_bold),  # Larger font, emoji-friendly
        background='#f0f0f0',
        foreground='#333333',
        )

        #self._build_toolbar()
        self._build_main_area()
        self.cache = load_cache()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_toolbar(self):


        # Toolbar as a frame
        tb = ttk.Frame(self, relief='flat')
        tb.pack(side='top', fill='x')

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

        # Search on right side of status bar
        search_frame = ttk.Frame(self.statusbar)
        search_frame.pack(side='right', padx=2, pady=2)
        search_label = ttk.Label(search_frame, text='Search ')
        search_label.pack(side='left')
        self.search_var = tk.StringVar()
        e = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        e.bind('<Return>', lambda e: self._do_search())
        e.pack(side='left')

        self.status_right = ttk.Label(self.statusbar, text='')
        self.status_right.pack(side='right')

        # Notebook (tabs) - pack directly into self, not a top_row frame
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side='top', fill='both', expand=True, padx=(0, 10))
        self._tab_tooltips = {}

        # load tabs from TABS config
        for tab in TABS:
            try:
                module = importlib.import_module(tab['module'])
                ViewClass = getattr(module, tab['class'])
                frame = ViewClass(self.notebook, services=None)
                self.notebook.add(frame, text=tab.get('icon', ''))
                self._tab_tooltips[frame] = tab['label']
            except Exception as e:
                f = ttk.Frame(self.notebook)
                ttk.Label(f, text=f"Failed to load {tab.get('label')}:\n{e}").pack(fill='both', expand=True)
                self.notebook.add(f, text=tab.get('icon', ''))
                self._tab_tooltips[f] = tab['label']

        # Bind mouse motion for tooltips
        self.notebook.bind('<Motion>', self._on_tab_hover)
        self._tooltip = None
        

    def _on_tab_hover(self, event):
        # Show tooltip with label when hovering over a tab
        x, y = event.x, event.y
        elem = self.notebook.identify(x, y)
        tab_index = self.notebook.index(f"@{x},{y}") if elem == 'label' else None
        if tab_index is not None:
            frame = self.notebook.nametowidget(self.notebook.tabs()[tab_index])
            label = self._tab_tooltips.get(frame, '')
            if label:
                if not self._tooltip:
                    self._tooltip = tk.Toplevel(self)
                    self._tooltip.wm_overrideredirect(True)
                    self._tooltip.wm_geometry(f"+{self.winfo_pointerx()+10}+{self.winfo_pointery()+10}")
                    l = tk.Label(self._tooltip, text=label, background="#222", foreground="#fff", borderwidth=1, relief="solid", font=("Segoe UI", 9))
                    l.pack()
                else:
                    self._tooltip.wm_geometry(f"+{self.winfo_pointerx()+10}+{self.winfo_pointery()+10}")
            else:
                self._hide_tooltip()
        else:
            self._hide_tooltip()

    def _hide_tooltip(self):
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None


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
