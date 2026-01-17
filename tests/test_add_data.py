#!/usr/bin/python3
# coding: utf-8
# test_add_data.py
from datetime import date, timedelta
import os
import random
import string
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data, utils


def _rand_text(prefix):
    return f"{prefix}_{''.join(random.choice(string.ascii_lowercase) for _ in range(6))}"


def _insert_rows(tbl, rows):
    inserted_ids = []
    for row in rows:
        values = []
        for idx, col in enumerate(tbl["col_list"]):
            if idx < len(row):
                values.append(row[idx])
            else:
                values.append("")
        record_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
        inserted_ids.append(record_id)
    return inserted_ids


def _fetch_ids(tbl, ids):
    if not ids:
        return []
    placeholders = ",".join(["?"] * len(ids))
    condition = f"id IN ({placeholders})"
    rows = data.get_data(data.conn, tbl["name"], ["id"] + tbl["col_list"], condition, ids)
    return [dict(row) for row in rows]


class TestAddData(unittest.TestCase):

    def test_01_notes(self):
        tbl = utils.get_table_def("notes")
        self.assertIsNotNone(tbl)
        rows = [
            [_rand_text("note") + ".md", r"C:\\Notes", "120", "2024-01-02 10:00:00", "Dev"],
            [_rand_text("note") + ".md", r"C:\\Notes", "44", "2024-01-03 09:30:00", ""],
            [_rand_text("note") + ".md", r"C:\\Notes", "", "", "Games"],
            [_rand_text("note") + ".md", r"C:\\Notes", "", "", ""],
            [_rand_text("note") + ".md", r"C:\\Notes", "256", "2024-02-10 08:15:00", "Work"],
            [_rand_text("note") + ".md", r"C:\\Notes", "10", "2024-03-01 12:00:00", "Pers"],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_02_tasks(self):
        tbl = utils.get_table_def("tasks")
        self.assertIsNotNone(tbl)
        today = date.today()
        rows = [
            [_rand_text("task"), "Call plumber", "Home", today.isoformat(), (today + timedelta(days=2)).isoformat()],
            [_rand_text("task"), "", "Work", "", ""],
            [_rand_text("task"), "Review archive", "Work", today.isoformat(), ""],
            [_rand_text("task"), "Plan trip", "Fun", "", (today + timedelta(days=30)).isoformat()],
            [_rand_text("task"), "", "", "", ""],
            [_rand_text("task"), "Follow up", "Pers", today.isoformat(), today.isoformat()],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_03_events(self):
        tbl = utils.get_table_def("calendar")
        self.assertIsNotNone(tbl)
        today = date.today()
        rows = [
            [_rand_text("event"), "Team sync", today.isoformat() + " 09:00", "", "Work"],
            [_rand_text("event"), "Errands", (today + timedelta(days=1)).isoformat() + " 10:00", "", "Pers"],
            [_rand_text("event"), "Backup", (today + timedelta(days=30)).isoformat() + " 18:00", "", "Dev"],
            [_rand_text("event"), "", today.isoformat(), "", ""],
            [_rand_text("event"), "Lunch", today.isoformat() + " 12:00", "", "Work"],
            [_rand_text("event"), "", "", "", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_04_goals(self):
        tbl = utils.get_table_def("goals")
        self.assertIsNotNone(tbl)
        rows = [
            ["", _rand_text("goal"), "Primary goal", date.today().isoformat(), "", "Work"],
            ["", _rand_text("goal"), "", "", "", ""],
            ["", _rand_text("goal"), "Secondary", "", "", "Pers"],
            ["", _rand_text("goal"), "", "", "", "Dev"],
            ["", _rand_text("goal"), "Long term", date.today().isoformat(), "", "Work"],
            ["", _rand_text("goal"), "", "", "", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_05_how(self):
        tbl = utils.get_table_def("how")
        self.assertIsNotNone(tbl)
        rows = [
            ["", _rand_text("how"), "Process notes", "Work"],
            ["", _rand_text("how"), "", ""],
            ["", _rand_text("how"), "Checklist", "Dev"],
            ["", _rand_text("how"), "", "Pers"],
            ["", _rand_text("how"), "Template", "Work"],
            ["", _rand_text("how"), "", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_06_data(self):
        tbl = utils.get_table_def("data")
        self.assertIsNotNone(tbl)
        rows = [
            [_rand_text("data"), "Source list", "tbl_notes", "title,content,project", "Work"],
            [_rand_text("data"), "", "", "", ""],
            [_rand_text("data"), "Tracking", "tbl_tasks", "title,project", "Dev"],
            [_rand_text("data"), "", "", "", "Pers"],
            [_rand_text("data"), "Registry", "tbl_files", "", "Work"],
            [_rand_text("data"), "", "", "", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_07_files(self):
        tbl = utils.get_table_def("files")
        self.assertIsNotNone(tbl)
        rows = [
            [_rand_text("filelist"), r"C:\\", "Folder", "Work"],
            [_rand_text("filelist"), r"C:\Windows", "", ""],
            [_rand_text("filelist"), r"C:\Users", "Folder", "Pers"],
            [_rand_text("filelist"), r"C:\Temp", "", "Dev"],
            [_rand_text("filelist"), "", "", ""],
            [_rand_text("filelist"), r"C:\\", "Folder", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_08_media(self):
        tbl = utils.get_table_def("media")
        self.assertIsNotNone(tbl)
        rows = [
            ["video.mp4", r"E:\\BK_fangorn\\photo\\__Downloads\\music_videos", "video", "444", "2014-01-02", "800", "800", ""],
            ["photo_153.JPG", r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach", "image", "444", "2014-01-02", "800", "800", ""],
            ["photo_134.MOV", r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach", "video", "444", "2014-01-02", "800", "800", ""],
            ["photo_141.JPG", r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach", "image", "444", "2014-01-02", "800", "800", ""],
            ["clip_001.MOV", r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach", "video", "", "", "", "", ""],
            ["photo_001.JPG", r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach", "image", "", "", "", "", ""],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))


    def test_08_media(self):
        # 	col_list ['file_name','path', 'file_type', 'size', 'date_modified', 'width', 'length', 'project']},

        tbl = utils.get_table_def("media")
        self.assertIsNotNone(tbl)
        rows = [
            ["video_BE DEUTSCH! [Achtung! Germans on the rise!] _ NEO MAGAZIN ROYALE mit Jan Böhmermann - ZDFneo-HMQkV5cTuoY.mp4", r"E:\\BK_fangorn\\photo\\__Downloads\\music_videos", "444", "2014-01-02", "800", "800", ""],
            ["moving-to-glenelg 153.JPG", r"E:\BK_fangorn\photo\travel\Glenelg\beach", "444", "2014-01-02", "800", "800", ""],
            ["moving-to-glenelg 134.MOV", r"E:\BK_fangorn\photo\travel\Glenelg\beach", "444", "2014-01-02", "800", "800", ""],
            ["moving-to-glenelg 141.JPG", r"E:\BK_fangorn\photo\travel\Glenelg\beach", "444", "2014-01-02", "800", "800", ""],

        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))


if __name__ == '__main__':
    unittest.main()
