import os
import sqlite3
import sys
import unittest
from dataclasses import dataclass

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import search


@dataclass
class SearchUser:
    user_id: int
    role: str = "user"
    is_authenticated: bool = True


class TestSearchSecurity(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        self._old_current_search_user = search._current_search_user
        data.conn = self.conn
        self.conn.executescript(
            """
            CREATE TABLE lp_notes (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                path TEXT,
                folder_id INTEGER,
                size TEXT,
                date_modified TEXT,
                project TEXT,
                owner_user_id INTEGER,
                visibility TEXT NOT NULL DEFAULT 'private',
                show_in_blog INTEGER NOT NULL DEFAULT 0,
                is_public INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE lp_note_search_index (
                note_id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_mtime REAL,
                file_size INTEGER,
                title TEXT,
                content_text TEXT,
                indexed_at TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            "INSERT INTO lp_notes (id, file_name, path, project, owner_user_id, visibility, is_public) "
            "VALUES (1, 'user-two-private-leak.md', 'C:\\notes', 'private', 2, 'private', 0)"
        )
        self.conn.execute(
            "INSERT INTO lp_notes (id, file_name, path, project, owner_user_id, visibility, is_public) "
            "VALUES (2, 'user-one-visible.md', 'C:\\notes', 'private', 1, 'private', 0)"
        )
        self.conn.execute(
            "INSERT INTO lp_notes (id, file_name, path, project, owner_user_id, visibility, is_public) "
            "VALUES (3, 'family-visible.md', 'C:\\notes', 'shared', 2, 'family', 0)"
        )
        self.conn.execute(
            "INSERT INTO lp_note_search_index (note_id, file_path, title, content_text, indexed_at) "
            "VALUES (1, 'C:\\notes\\user-two-private-leak.md', 'user-two-private-leak.md', 'secret phrase from user two', '2026-01-01T00:00:00Z')"
        )
        self.conn.execute(
            "INSERT INTO lp_note_search_index (note_id, file_path, title, content_text, indexed_at) "
            "VALUES (2, 'C:\\notes\\user-one-visible.md', 'user-one-visible.md', 'secret phrase from user one', '2026-01-01T00:00:00Z')"
        )
        self.conn.commit()

    def tearDown(self):
        search._current_search_user = self._old_current_search_user
        data.conn = self._old_conn
        self.conn.close()

    def _search_as(self, user_id):
        search._current_search_user = lambda: SearchUser(user_id=user_id)

    def _result_titles(self, results):
        return {item["title"] for item in results["primary"] + results["secondary"]}

    def test_metadata_search_does_not_return_another_users_private_notes(self):
        self._search_as(1)

        results = search.search_all("user two private leak", route="notes")

        self.assertNotIn("user-two-private-leak.md", self._result_titles(results))

    def test_metadata_search_allows_own_and_family_visible_notes(self):
        self._search_as(1)

        own_results = search.search_all("user one visible", route="notes")
        family_results = search.search_all("family visible", route="notes")

        self.assertIn("user-one-visible.md", self._result_titles(own_results))
        self.assertIn("family-visible.md", self._result_titles(family_results))

    def test_note_content_search_does_not_return_another_users_private_notes(self):
        self._search_as(1)

        results = search.search_note_content("secret phrase from user two", route="notes")

        self.assertNotIn("user-two-private-leak.md", self._result_titles(results))

    def test_note_content_search_allows_own_notes(self):
        self._search_as(1)

        results = search.search_note_content("secret phrase from user one", route="notes")

        self.assertIn("user-one-visible.md", self._result_titles(results))


if __name__ == "__main__":
    unittest.main()
