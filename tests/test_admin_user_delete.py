import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask, render_template
from jinja2 import ChoiceLoader, FileSystemLoader

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import utils as common_utils
from modules.admin import routes as admin_routes
from modules.notes import routes as notes_routes


class TestAdminLogs(unittest.TestCase):
    def test_sync_network_log_line_is_summarized(self):
        entry = admin_routes._parse_network_log_line(
            '2026-07-29T13:00:00Z pocket_push_finish '
            '{"path": "/api/pocket/v1/sync/upload", "item_count": 3, "ok_count": 2, '
            '"conflict_count": 1, "error_count": 0, "status_code": 200}'
        )

        self.assertTrue(admin_routes._is_sync_network_entry(entry))
        self.assertEqual(admin_routes._sync_direction(entry), "Mobile -> Desktop")
        self.assertIn("2/3 accepted", admin_routes._sync_summary(entry))
        self.assertEqual(entry["display_log_date"], "2026-07-29 22:30:00 ACST")

    def test_logs_template_renders_filters_and_blank_details(self):
        app = Flask(
            __name__,
            template_folder=os.path.join(root_folder, "templates"),
            static_folder=os.path.join(root_folder, "static"),
        )
        app.jinja_loader = ChoiceLoader(
            [
                FileSystemLoader(os.path.join(root_folder, "templates")),
                FileSystemLoader(os.path.join(root_folder, "modules", "admin", "templates")),
            ]
        )
        app.add_url_rule("/site.webmanifest", endpoint="site_webmanifest", view_func=lambda: {})
        app.add_url_rule("/search", endpoint="search_route", view_func=lambda: "")
        app.add_url_rule("/admin/", endpoint="admin.admin_mapping_route", view_func=lambda: "")
        app.add_url_rule("/admin/logs", endpoint="admin.logs_route", view_func=lambda: "")
        app.add_url_rule("/admin/logs/logger", endpoint="admin.logger_logs_route", view_func=lambda: "")

        with app.test_request_context("/admin/logs"):
            html = render_template(
                "admin_logs.html",
                active_tab="admin",
                tabs=[],
                side_tabs=[],
                content_title="Admin - Logs",
                content_html="",
                include_sync_logs=True,
                include_user_logs=True,
                limit=200,
                network_log_file="C:\\apps\\LifePIM_Prod\\src\\lp_network.log",
                log_timezone="Australia/Adelaide",
                sync_entries=[
                    {
                        "log_date": "2026-07-29T13:00:00Z",
                        "direction": "Mobile -> Desktop",
                        "event": "pocket_push_finish",
                        "summary": "1/1 accepted",
                        "details": None,
                    }
                ],
                user_entries=[
                    {
                        "id": 1,
                        "log_date": "2026-07-29T13:00:00Z",
                        "user_name": "admin",
                        "action": "edited note",
                        "entity_type": "lp_notes",
                        "entity_id": "1",
                        "context_type": "notes",
                        "context_id": None,
                        "details": None,
                    }
                ],
            )

        self.assertIn('name="sync_logs"', html)
        self.assertIn('name="user_logs"', html)
        self.assertIn("Mobile -&gt; Desktop", html)
        self.assertIn("edited note", html)


class _AnonymousCurrentUser:
    is_authenticated = False
    user_id = None


class TestAdminUserDelete(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        self.tmpdir = tempfile.TemporaryDirectory()
        self.conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE lp_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                path TEXT,
                folder_id INTEGER,
                size TEXT,
                date_modified TEXT,
                area TEXT,
                owner_user_id INTEGER,
                user_name TEXT,
                rec_extract_date TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
            "VALUES (1, 'alice', 'Alice', 'hash', 'user', 1)"
        )
        self.conn.execute(
            "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
            "VALUES (2, 'bob', 'Bob', 'hash', 'user', 1)"
        )
        self.conn.commit()

    def tearDown(self):
        try:
            self.tmpdir.cleanup()
        finally:
            data.conn = self._old_conn
            self.conn.close()

    def _add_note(self, user_id, name, content="note"):
        folder = os.path.join(self.tmpdir.name, f"user-{user_id}")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        cur = self.conn.execute(
            "INSERT INTO lp_notes(file_name, path, owner_user_id, rec_extract_date) VALUES (?, ?, ?, 'now')",
            (name, folder, user_id),
        )
        self.conn.commit()
        return cur.lastrowid, path

    def test_delete_user_plan_counts_only_owned_note_records_and_existing_files(self):
        self._add_note(1, "alice-one.md")
        self._add_note(1, "alice-two.md")
        self._add_note(2, "bob.md")
        self.conn.execute(
            "INSERT INTO lp_notes(file_name, path, owner_user_id, rec_extract_date) VALUES (?, ?, ?, 'now')",
            ("missing.md", os.path.join(self.tmpdir.name, "missing"), 1),
        )
        self.conn.commit()

        plan = admin_routes._user_note_delete_plan(self.conn, 1)

        self.assertEqual(plan["note_record_count"], 3)
        self.assertEqual(plan["note_file_count"], 2)
        self.assertEqual(set(plan["note_ids"]), {1, 2, 4})

    def test_delete_user_removes_only_that_users_notes_and_files(self):
        _, alice_path = self._add_note(1, "alice.md")
        _, bob_path = self._add_note(2, "bob.md")

        with patch.object(admin_routes, "current_user", _AnonymousCurrentUser()):
            plan = admin_routes._delete_user_and_owned_notes(self.conn, 1)

        self.assertEqual(plan["note_record_count"], 1)
        self.assertFalse(os.path.exists(alice_path))
        self.assertTrue(os.path.exists(bob_path))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM users WHERE user_id = 1").fetchone())
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM users WHERE user_id = 2").fetchone())
        self.assertIsNone(self.conn.execute("SELECT 1 FROM lp_notes WHERE owner_user_id = 1").fetchone())
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM lp_notes WHERE owner_user_id = 2").fetchone())


class TestNotesBulkDelete(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        self.tmpdir = tempfile.TemporaryDirectory()
        self.conn.executescript(
            """
            CREATE TABLE lp_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                path TEXT,
                folder_id INTEGER,
                size TEXT,
                date_modified TEXT,
                area TEXT,
                owner_user_id INTEGER,
                user_name TEXT,
                rec_extract_date TEXT
            );
            """
        )
        common_utils.ensure_user_log_schema(self.conn)

    def tearDown(self):
        try:
            self.tmpdir.cleanup()
        finally:
            data.conn = self._old_conn
            self.conn.close()

    def _add_note(self, name):
        folder = os.path.join(self.tmpdir.name, "notes")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("note")
        cur = self.conn.execute(
            "INSERT INTO lp_notes(file_name, path, rec_extract_date) VALUES (?, ?, 'now')",
            (name, folder),
        )
        self.conn.commit()
        return cur.lastrowid, path

    def test_delete_selected_notes_uses_existing_note_delete_behavior(self):
        first_id, first_path = self._add_note("first.md")
        second_id, second_path = self._add_note("second.md")

        with self.app.test_request_context("/notes/api/delete-selected", method="POST", json={"note_ids": [first_id]}):
            with patch.object(notes_routes.security, "can_delete_note", return_value=True):
                response, status = notes_routes.delete_selected_notes_route()

        self.assertEqual(status, 200)
        payload = response.get_json()
        self.assertEqual(payload["deleted"], 1)
        self.assertEqual(payload["deleted_ids"], [first_id])
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.isdir(os.path.join(os.path.dirname(first_path), "deleted")))
        self.assertTrue(os.path.exists(second_path))
        self.assertIsNone(self.conn.execute("SELECT 1 FROM lp_notes WHERE id = ?", (first_id,)).fetchone())
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM lp_notes WHERE id = ?", (second_id,)).fetchone())


if __name__ == "__main__":
    unittest.main()
