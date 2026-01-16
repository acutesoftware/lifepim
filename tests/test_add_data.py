#!/usr/bin/python3
# coding: utf-8
# test_area_data.py
from datetime import date, timedelta
import os
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data, utils


class TestAddData(unittest.TestCase):

    def test_01_add_data(self):
        notes_tbl = utils.get_table_def("notes")
        tasks_tbl = utils.get_table_def("tasks")
        events_tbl = utils.get_table_def("calendar")

        self.assertIsNotNone(notes_tbl)
        self.assertIsNotNone(tasks_tbl)
        self.assertIsNotNone(events_tbl)

        # add 3 notes with dummy data
        note_rows = [
            ["howto - python", "Tips and snippets", "Dev"],
            ["journal", "Daily notes", "Pers"],
            ["ideas for game", "Gameplay loops and mechanics", "Games"],
        ]
        for row in note_rows:
            note_id = data.add_record(data.conn, notes_tbl["name"], notes_tbl["col_list"], row)
            self.assertIsNotNone(note_id)

        # add 3 tasks - different due dates
        today = date.today()
        task_rows = [
            ["fix plumbing", "Call plumber and schedule", "Home", today.isoformat(), (today + timedelta(days=2)).isoformat()],
            ["check files", "Review archive structure", "Work", today.isoformat(), (today + timedelta(days=7)).isoformat()],
            ["plan trip", "Draft itinerary", "Fun", today.isoformat(), (today + timedelta(days=30)).isoformat()],
        ]
        for row in task_rows:
            task_id = data.add_record(data.conn, tasks_tbl["name"], tasks_tbl["col_list"], row)
            self.assertIsNotNone(task_id)

        # add 3 calendar events
        event_rows = [
            ["9am meeting", "Team sync", today.isoformat() + " 09:00", "", "Work"],
            ["go to town", "Errands", (today + timedelta(days=1)).isoformat() + " 10:00", "", "Pers"],
            ["run backup", "Monthly backup", (today + timedelta(days=30)).isoformat() + " 18:00", "", "Dev"],
        ]
        for row in event_rows:
            event_id = data.add_record(data.conn, events_tbl["name"], events_tbl["col_list"], row)
            self.assertIsNotNone(event_id)


if __name__ == '__main__':
    unittest.main()
