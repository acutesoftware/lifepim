#!/usr/bin/python3
# coding: utf-8
# test_links.py

import os
import sqlite3
import sys
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import links


class TestLinkDecisionLogic(unittest.TestCase):
    def test_context_table_defaults(self):
        context_src = {
            "task_detail": "task",
            "note_detail": "note",
            "event_detail": "event",
            "file_detail": "file",
            "person_detail": "person",
            "place_detail": "place",
            "email_detail": "email",
        }
        dst_by_category = {
            "task": "task",
            "person": "person",
            "file": "file",
            "place": "place",
            "email": "email",
            "else": "note",
        }
        for context_type, defaults in links.CONTEXT_DEFAULTS.items():
            src_type = context_src.get(context_type, "note")
            for category, expected in defaults.items():
                dst_type = dst_by_category[category]
                with self.subTest(context_type=context_type, category=category):
                    actual = links.default_link_type(context_type, src_type, dst_type)
                    self.assertEqual(actual, expected)

    def test_fallback_table(self):
        cases = [
            ("note", "file", "attachment"),
            ("task", "task", "depends_on"),
            ("task", "person", "assigned_to"),
            ("event", "place", "located_at"),
            ("note", "email", "emails"),
            ("email", "note", "emails"),
            ("note", "person", "mentions"),
            ("place", "note", "related"),
        ]
        for src_type, dst_type, expected in cases:
            with self.subTest(src_type=src_type, dst_type=dst_type):
                actual = links.default_link_type("link_picker", src_type, dst_type)
                self.assertEqual(actual, expected)

    def test_mention_override(self):
        actual = links.resolve_link_type("editor_mention", "note", "task")
        self.assertEqual(actual, "mentions")


class TestAllowedLinkTypes(unittest.TestCase):
    def test_depends_on_only_for_tasks(self):
        allowed = set(links.allowed_link_types("task", "task"))
        self.assertIn("depends_on", allowed)
        self.assertNotIn("depends_on", set(links.allowed_link_types("note", "task")))

    def test_assigned_to_only_from_tasks_to_people(self):
        allowed = set(links.allowed_link_types("task", "person"))
        self.assertIn("assigned_to", allowed)
        self.assertNotIn("assigned_to", set(links.allowed_link_types("note", "person")))

    def test_located_at_rules(self):
        self.assertIn("located_at", set(links.allowed_link_types("event", "place")))
        self.assertNotIn("located_at", set(links.allowed_link_types("note", "place")))

    def test_calls_rules(self):
        self.assertIn("calls", set(links.allowed_link_types("person", "person")))
        self.assertIn("calls", set(links.allowed_link_types("task", "person")))
        self.assertNotIn("calls", set(links.allowed_link_types("note", "person")))

    def test_emails_rules(self):
        self.assertIn("emails", set(links.allowed_link_types("person", "person")))
        self.assertIn("emails", set(links.allowed_link_types("email", "note")))
        self.assertNotIn("emails", set(links.allowed_link_types("task", "note")))

    def test_attachment_rules(self):
        self.assertIn("attachment", set(links.allowed_link_types("note", "file")))
        self.assertIn("attachment", set(links.allowed_link_types("file", "note")))
        self.assertNotIn("attachment", set(links.allowed_link_types("note", "person")))

    def test_mentions_and_about_rules(self):
        self.assertIn("mentions", set(links.allowed_link_types("note", "person")))
        self.assertIn("mentions", set(links.allowed_link_types("task", "file")))
        self.assertNotIn("mentions", set(links.allowed_link_types("file", "person")))
        self.assertIn("about", set(links.allowed_link_types("note", "person")))
        self.assertIn("about", set(links.allowed_link_types("event", "person")))
        self.assertNotIn("about", set(links.allowed_link_types("task", "person")))


class TestLinkCreateDedupe(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        links.ensure_links_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_dedupe_on_create(self):
        payload = {
            "src_type": "note",
            "src_id": "1",
            "dst_type": "task",
            "dst_id": "2",
            "link_type": "related",
            "context_type": "link_picker",
        }
        first = links.create_link(self.conn, payload)
        self.assertTrue(first["created"])
        self.assertFalse(first["duplicate"])
        self.assertIsNotNone(first["link_id"])

        second = links.create_link(self.conn, payload)
        self.assertFalse(second["created"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["link_id"], first["link_id"])

        stored = links.get_link(self.conn, first["link_id"])
        self.assertEqual(stored["src_type"], "note")
        self.assertEqual(stored["dst_type"], "task")
        self.assertEqual(stored["link_type"], "related")
        self.assertEqual(stored["sort_order"], 100)


if __name__ == "__main__":
    unittest.main()
