#!/usr/bin/python3
# coding: utf-8
# data.py - common data access functions

from datetime import datetime


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





################ DUMMY FUNCTIONS FOR NOTES (to be removed) ################

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


################ DUMMY FUNCTIONS FOR CALENDAR (to be removed) ################

CAL_EVENTS = [
    {
        "id": 1,
        "title": "Team Check-in",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "09:00",
        "detail": "Weekly sync",
        "project": "Work",
        "updated": datetime.now(),
    },
    {
        "id": 2,
        "title": "Gym",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": "18:30",
        "detail": "Strength session",
        "project": "Health",
        "updated": datetime.now(),
    },
]


def _calendar_match_project(project, event_project):
    if not project or project in ("any", "spacer"):
        return True
    return (event_project or "").lower() == project.lower()


def get_calendar_events(year=None, month=None, project=None):
    events = [e for e in CAL_EVENTS if _calendar_match_project(project, e.get("project"))]
    if year and month:
        prefix = f"{year:04d}-{month:02d}"
        events = [e for e in events if e.get("date", "").startswith(prefix)]
    return sorted(events, key=lambda e: (e.get("date", ""), e.get("time", ""), e.get("id", 0)))


def get_calendar_event_by_id(event_id):
    return next((e for e in CAL_EVENTS if e["id"] == event_id), None)


def add_calendar_event(title, date_str, time_str="", detail="", project="General"):
    new_id = max([e["id"] for e in CAL_EVENTS], default=0) + 1
    event = {
        "id": new_id,
        "title": title,
        "date": date_str,
        "time": time_str,
        "detail": detail,
        "project": project or "General",
        "updated": datetime.now(),
    }
    CAL_EVENTS.append(event)
    return event


def update_calendar_event(event_id, title, date_str, time_str, detail, project):
    event = get_calendar_event_by_id(event_id)
    if event:
        event["title"] = title
        event["date"] = date_str
        event["time"] = time_str
        event["detail"] = detail
        event["project"] = project or "General"
        event["updated"] = datetime.now()


def delete_calendar_event(event_id):
    global CAL_EVENTS
    CAL_EVENTS = [e for e in CAL_EVENTS if e["id"] != event_id]
