import os
import sqlite3
import sys
import unittest

from flask import Flask, render_template


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.append(SRC)

from common import data
from modules.contacts import dao
from modules.contacts.routes import contacts_bp


class TestContactsBulkDelete(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        with open(os.path.join(SRC, "schema_contacts.sql"), encoding="utf-8") as handle:
            self.conn.executescript(handle.read())
        self.old_conn = data.conn
        data.conn = self.conn

        self.app = Flask(__name__, template_folder=os.path.join(SRC, "templates"))
        self.app.register_blueprint(contacts_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_delete_selected_contacts_deletes_only_valid_requested_contacts(self):
        first_id = dao.create_contact("First Contact")
        second_id = dao.create_contact("Second Contact")
        untouched_id = dao.create_contact("Untouched Contact")
        dao.add_fact(first_id, "email", "first@example.com", "manual")

        response = self.client.post(
            "/contacts/api/delete-selected",
            json={"contact_ids": [str(first_id), second_id, first_id, "invalid", 99999]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"deleted": 2, "deleted_ids": [first_id, second_id]},
        )
        self.assertIsNone(dao.get_contact(first_id))
        self.assertIsNone(dao.get_contact(second_id))
        self.assertIsNotNone(dao.get_contact(untouched_id))
        fact = self.conn.execute(
            "SELECT 1 FROM lp_contact_facts WHERE contact_id = ?",
            (first_id,),
        ).fetchone()
        self.assertIsNone(fact)

    def test_delete_selected_contacts_with_no_valid_ids_is_a_noop(self):
        contact_id = dao.create_contact("Keep Contact")

        response = self.client.post(
            "/contacts/api/delete-selected",
            json={"contact_ids": ["invalid", None]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"deleted": 0, "deleted_ids": []})
        self.assertIsNotNone(dao.get_contact(contact_id))

    def test_contacts_selected_menu_includes_delete_action(self):
        with self.app.test_request_context():
            markup = render_template(
                "widgets/links_bulk_toolbar.html",
                link_list_type="person",
                link_list_context_id="contacts_list",
                link_table_id="contacts-table",
            )

        self.assertIn('<option value="delete">Delete Selected contacts</option>', markup)


if __name__ == "__main__":
    unittest.main()
