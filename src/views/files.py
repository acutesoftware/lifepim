import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class FileView(ttk.Frame):
    def __init__(self, master, services=None, **kwargs):
        super().__init__(master, **kwargs)
        paned = ttk.Panedwindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # --- Left: Folder Tree ---
        left = ttk.Frame(paned, width=250)
        paned.add(left, weight=1)

        # Folder tree vertical scrollbar
        folder_scroll = ttk.Scrollbar(left, orient='vertical')
        folder_scroll.pack(side='right', fill='y')

        self.folder_tree = ttk.Treeview(left, show='tree', yscrollcommand=folder_scroll.set)
        self.folder_tree.pack(side='left', fill='both', expand=True, padx=2, pady=2)
        folder_scroll.config(command=self.folder_tree.yview)

        self.folder_tree.bind('<<TreeviewOpen>>', self.on_treeview_open)
        self.folder_tree.bind('<<TreeviewClose>>', self.on_treeview_close)
        self.folder_tree.bind('<<TreeviewSelect>>', self.on_folder_select)

        self.populate_folder_tree()

        # --- Middle: File List ---
        mid = ttk.Frame(paned, width=500)
        paned.add(mid, weight=3)
        files_frame = ttk.LabelFrame(mid, text='Files')
        files_frame.pack(fill='both', expand=True, padx=2, pady=2)

        # File list vertical scrollbar
        file_scroll = ttk.Scrollbar(files_frame, orient='vertical')
        file_scroll.pack(side='right', fill='y')

        self.file_list = ttk.Treeview(
            files_frame, columns=('name', 'size', 'type'), show='tree headings', yscrollcommand=file_scroll.set
        )
        self.file_list.heading('name', text='Name')
        self.file_list.heading('size', text='Size')
        self.file_list.heading('type', text='Type')
        self.file_list.column('name', width=250, anchor='w')
        self.file_list.column('size', width=80, anchor='e')
        self.file_list.column('type', width=80, anchor='w')
        self.file_list.pack(side='left', fill='both', expand=True)
        file_scroll.config(command=self.file_list.yview)

        # --- Right: Metadata (optional) ---
        right = ttk.Frame(paned, width=150)
        paned.add(right, weight=1)
        stats = ttk.LabelFrame(right, text='Metadata')
        stats.pack(fill='both', expand=True, padx=2, pady=1)
        self.word_count = ttk.Label(stats, text='Size: 0')
        self.word_count.pack(anchor='w', padx=2, pady=1)

    def populate_folder_tree(self):
        if os.name == 'nt':
            import string
            drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
            for drive in drives:
                node = self.folder_tree.insert(
                    '', 'end', text="📁 " + drive, values=[drive], open=False)
                if self.has_subfolders(drive):
                    self.folder_tree.insert(node, 'end')  # dummy child for expand arrow
        else:
            node = self.folder_tree.insert(
                '', 'end', text="📁 /", values=['/'], open=False)
            if self.has_subfolders('/'):
                self.folder_tree.insert(node, 'end')  # dummy child

    def on_treeview_open(self, event):
        node = self.folder_tree.focus()
        path = self.folder_tree.item(node, 'values')[0]
        label = self.folder_tree.item(node, 'text')
        # Always replace first two chars with open folder emoji
        if label.startswith("📁 ") or label.startswith("📂 "):
            self.folder_tree.item(node, text="📂 " + label[2:])
        else:
            self.folder_tree.item(node, text="📂 " + label)
        # Only populate if the first child is a dummy (no values)
        children = self.folder_tree.get_children(node)
        if children:
            first_child = children[0]
            if not self.folder_tree.item(first_child, 'values'):
                self.folder_tree.delete(first_child)
                self.insert_subfolders(node, path)

    def on_treeview_close(self, event):
        node = self.folder_tree.focus()
        label = self.folder_tree.item(node, 'text')
        if label.startswith("📁 ") or label.startswith("📂 "):
            self.folder_tree.item(node, text="📁 " + label[2:])
        else:
            self.folder_tree.item(node, text="📁 " + label)

    def insert_subfolders(self, parent, path):
        try:
            subfolders = []
            for name in os.listdir(path):
                fullpath = os.path.join(path, name)
                if os.path.isdir(fullpath):
                    subfolders.append((name, fullpath))
            subfolders.sort()
            for name, fullpath in subfolders:
                try:
                    node = self.folder_tree.insert(
                        parent, 'end', text="📁 " + name, values=[fullpath], open=False)
                    if self.has_subfolders(fullpath):
                        self.folder_tree.insert(node, 'end')  # dummy child for expand arrow
                except Exception:
                    continue
        except Exception as e:
            print('cant insert subfolders:', e)

    def has_subfolders(self, path):
        try:
            for name in os.listdir(path):
                if os.path.isdir(os.path.join(path, name)):
                    return True
        except Exception:
            return False
        return False

    def on_folder_select(self, event):
        selected = self.folder_tree.selection()
        if not selected:
            return
        node = selected[0]
        path = self.folder_tree.item(node, 'values')[0]
        self.list_files(path)

    def list_files(self, folder):
        self.file_list.delete(*self.file_list.get_children())
        try:
            for name in os.listdir(folder):
                fullpath = os.path.join(folder, name)
                if os.path.isfile(fullpath):
                    size = os.path.getsize(fullpath)
                    ext = os.path.splitext(name)[1][1:].upper()
                    self.file_list.insert(
                        '', 'end', text="📄",  # file emoji
                        values=(name, self.format_size(size), ext))
        except Exception as e:
            messagebox.showerror("Error", f"Cannot list files in {folder}\n{e}")

    def format_size(self, size):
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0:
                return f"{size:.0f} {unit}"
            size /= 1024.0
        return f"{size:.0f} PB"