# data.py - common data access functions
def query_table(name, condition):
    pass



# ---- old dummy data functions for testing ----
def get_table_list(name):
    # Demo data
    if name == "notes":
        return [["Note 1", "Content of note 1"], ["Note 2", "Another note"]]
    elif name == "tasks":
        return [["Task 1", "Pending"], ["Task 2", "Done"]]
    elif name == "calendar":
        return [["Meeting", "Tomorrow"], ["Gym", "Today"]]
    return []

from datetime import datetime

NOTES = [
    {"id": 1, "title": "First Note", "project": "General", "content": "This is a sample note.", "updated": datetime.now()},
]

def get_notes(project=None):
    if project:
        return [n for n in NOTES if n["project"] == project]
    return NOTES

def get_note_by_id(note_id):
    return next((n for n in NOTES if n["id"] == note_id), None)

def add_note(title, content, project="General"):
    new_id = max([n["id"] for n in NOTES], default=0) + 1
    note = {"id": new_id, "title": title, "content": content, "project": project, "updated": datetime.now()}
    NOTES.append(note)
    return note

def update_note(note_id, title, content):
    note = get_note_by_id(note_id)
    if note:
        note["title"] = title
        note["content"] = content
        note["updated"] = datetime.now()

def delete_note(note_id):
    global NOTES
    NOTES = [n for n in NOTES if n["id"] != note_id]
