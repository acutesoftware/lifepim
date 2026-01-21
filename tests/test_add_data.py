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
from modules.contacts import dao as contacts_dao


def _rand_text(prefix):
    return f"{prefix}_{''.join(random.choice(string.ascii_lowercase) for _ in range(6))}"


def _rand_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, max(delta.days, 0)))


def _rand_dt(start, end):
    dt = _rand_date(start, end)
    return f"{dt.isoformat()} {random.randint(0, 23):02d}:{random.choice([0, 15, 30, 45]):02d}"


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
        projects = ["Dev", "Work", "Pers", "Games", ""]
        rows = []
        for _ in range(10):
            rows.append([
                _rand_text("note") + ".md",
                r"C:\\Notes",
                str(random.randint(1, 500)) if random.random() > 0.2 else "",
                _rand_dt(date.today() - timedelta(days=90), date.today()) if random.random() > 0.2 else "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_02_tasks(self):
        tbl = utils.get_table_def("tasks")
        self.assertIsNotNone(tbl)
        today = date.today()
        projects = ["Home", "Work", "Fun", "Pers", ""]
        rows = []
        for _ in range(10):
            start_date = _rand_date(today - timedelta(days=7), today) if random.random() > 0.2 else None
            due_date = _rand_date(today, today + timedelta(days=30)) if random.random() > 0.3 else None
            rows.append([
                _rand_text("task"),
                _rand_text("desc") if random.random() > 0.2 else "",
                random.choice(projects),
                start_date.isoformat() if start_date else "",
                due_date.isoformat() if due_date else "",
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_03_events(self):
        tbl = utils.get_table_def("calendar")
        self.assertIsNotNone(tbl)
        today = date.today()
        projects = ["Work", "Pers", "Dev", ""]
        rows = []
        for _ in range(10):
            rows.append([
                _rand_text("event"),
                _rand_text("title") if random.random() > 0.2 else "",
                _rand_dt(today, today + timedelta(days=30)) if random.random() > 0.1 else "",
                "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_04_goals(self):
        tbl = utils.get_table_def("goals")
        self.assertIsNotNone(tbl)
        projects = ["Work", "Pers", "Dev", ""]
        rows = []
        for _ in range(10):
            rows.append([
                "",
                _rand_text("goal"),
                _rand_text("desc") if random.random() > 0.3 else "",
                _rand_date(date.today() - timedelta(days=30), date.today()).isoformat() if random.random() > 0.3 else "",
                "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_05_how(self):
        tbl = utils.get_table_def("how")
        self.assertIsNotNone(tbl)
        projects = ["Work", "Dev", "Pers", ""]
        rows = []
        for _ in range(10):
            rows.append([
                "",
                _rand_text("how"),
                _rand_text("body") if random.random() > 0.3 else "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_06_data(self):
        tbl = utils.get_table_def("data")
        self.assertIsNotNone(tbl)
        tables = ["tbl_notes", "tbl_tasks", "tbl_files", "tbl_calendar", ""]
        projects = ["Work", "Dev", "Pers", ""]
        fields = ["title,content,project", "title,project", "file_name,path", ""]
        rows = []
        for _ in range(10):
            rows.append([
                _rand_text("data"),
                _rand_text("desc") if random.random() > 0.2 else "",
                random.choice(tables),
                random.choice(fields),
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_07_files(self):
        tbl = utils.get_table_def("files")
        self.assertIsNotNone(tbl)
        roots = [r"C:\\", r"C:\\Windows", r"C:\\Users", r"C:\\Temp", ""]
        projects = ["Work", "Pers", "Dev", ""]
        rows = []
        for _ in range(10):
            rows.append([
                _rand_text("filelist"),
                random.choice(roots),
                random.choice(["Folder", ""]) if random.random() > 0.2 else "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_08_media(self):
        tbl = utils.get_table_def("media")
        self.assertIsNotNone(tbl)
        paths = [
            r"E:\\BK_fangorn\\photo\\__Downloads\\music_videos",
            r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\beach",
            r"E:\\BK_fangorn\\photo\\travel\\Glenelg\\city",
        ]
        projects = ["Work", "Pers", "Dev", ""]
        file_types = {
            "video": [".mp4", ".mov"],
            "image": [".jpg", ".png"],
            "audio": [".mp3", ".wav"],
        }
        rows = []
        for _ in range(10):
            file_type = random.choice(list(file_types.keys()))
            ext = random.choice(file_types[file_type])
            rows.append([
                _rand_text("media") + ext,
                random.choice(paths),
                file_type,
                str(random.randint(10, 5000)) if random.random() > 0.2 else "",
                _rand_date(date.today() - timedelta(days=365), date.today()).isoformat() if random.random() > 0.2 else "",
                str(random.randint(320, 4000)) if file_type != "audio" and random.random() > 0.2 else "",
                str(random.randint(320, 4000)) if file_type != "audio" and random.random() > 0.2 else "",
                random.choice(projects),
            ])
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_09_places(self):
        tbl = utils.get_table_def("places")
        self.assertIsNotNone(tbl)
        rows = [
            ["Tower of London", "Historic castle in London", "", "London", "", "", "United Kingdom", "51.5081", "-0.0759"],
            ["Eiffel Tower", "Iconic Paris landmark", "", "Paris", "", "", "France", "48.8584", "2.2945"],
            ["Statue of Liberty", "Famous statue in New York Harbor", "", "New York", "", "NY", "USA", "40.6892", "-74.0445"],
            ["Great Pyramid of Giza", "Ancient pyramid in Egypt", "", "Giza", "", "", "Egypt", "29.9792", "31.1342"],
            ["Sydney Opera House", "Performing arts center in Sydney", "", "Sydney", "", "NSW", "Australia", "-33.8568", "151.2153"],
        ]
        ids = _insert_rows(tbl, rows)
        self.assertTrue(all(ids))
        fetched = _fetch_ids(tbl, ids)
        self.assertEqual(len(fetched), len(ids))

    def test_10_money_plans(self):
        conn = data._get_conn()
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_money_plans'"
        ).fetchone()
        if not table_row:
            self.skipTest("lp_money_plans not available")
        statuses = ["idea", "planned", "bought", "cancelled"]
        domains = ["Car", "fun\\events", "Gardening", "cooking", "General"]
        base_items = [
            "External HD",
            "tyres for car",
            "Movie tickets",
            "seedlings",
            "Steak Knives",
        ]
        inserted_ids = []
        for status in statuses:
            for domain in domains:
                for _ in range(2):
                    item = f"{random.choice(base_items)} {_rand_text(status)}"
                    cost = round(random.uniform(15, 1200), 2)
                    priority = random.randint(1, 5)
                    target_date = _rand_date(date.today(), date.today() + timedelta(days=365)).isoformat()
                    if random.random() > 0.7:
                        target_date = ""
                    cur = conn.execute(
                        "INSERT INTO lp_money_plans (item, domain, estimated_cost, target_date, priority, status, notes) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            item,
                            domain,
                            cost,
                            target_date,
                            priority,
                            status,
                            "",
                        ),
                    )
                    inserted_ids.append(cur.lastrowid)
        conn.commit()
        self.assertTrue(all(inserted_ids))
        placeholders = ",".join(["?"] * len(inserted_ids))
        rows = conn.execute(
            f"SELECT plan_id FROM lp_money_plans WHERE plan_id IN ({placeholders})",
            inserted_ids,
        ).fetchall()
        self.assertEqual(len(rows), len(inserted_ids))

    def test_11_contacts(self):
        conn = data._get_conn()
        table_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lp_contacts'"
        ).fetchone()
        if not table_row:
            self.skipTest("lp_contacts not available")
        contact_rows = [
            ("Ada Lovelace", [("email", "ada@example.com"), ("phone", "+1-555-0001")]),
            ("Grace Hopper", [("email", "grace@example.com"), ("org", "Navy"), ("note", "COBOL pioneer")]),
            ("Linus Torvalds", [("url", "https://example.com/linus")]),
            ("Alan Turing", []),
            ("Katherine Johnson", [("phone", "+1-555-0002"), ("address", "123 Orbit Rd"), ("email", "kat@example.com")]),
            ("Margaret Hamilton", [("email", "margaret@example.com")]),
            ("Tim Berners-Lee", [("url", "https://example.com/tim"), ("org", "W3C"), ("note", "WWW")]),
            ("Radia Perlman", [("email", "radia@example.com"), ("phone", "+1-555-0003"), ("address", "1 Bridge Way"), ("org", "DEC")]),
            ("Donald Knuth", [("address", "Stanford, CA")]),
        ]
        contact_ids = []
        fact_count = 0
        for name, facts in contact_rows:
            contact_id = contacts_dao.create_contact(name)
            self.assertIsNotNone(contact_id)
            contact_ids.append(contact_id)
            for fact_type, fact_value in facts:
                fact_id = contacts_dao.add_fact(contact_id, fact_type, fact_value, "manual")
                self.assertIsNotNone(fact_id)
                fact_count += 1
        placeholders = ",".join(["?"] * len(contact_ids))
        rows = conn.execute(
            f"SELECT contact_id FROM lp_contacts WHERE contact_id IN ({placeholders})",
            contact_ids,
        ).fetchall()
        self.assertEqual(len(rows), len(contact_ids))
        row = conn.execute(
            f"SELECT COUNT(1) AS cnt FROM lp_contact_facts WHERE contact_id IN ({placeholders})",
            contact_ids,
        ).fetchone()
        self.assertEqual(row["cnt"], fact_count)

if __name__ == '__main__':
    unittest.main()
