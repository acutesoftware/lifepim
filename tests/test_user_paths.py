import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import projects
from common import user_paths
from core import security
from modules.admin import routes as admin_routes
from modules.notes import routes as notes_routes


class TestUserPaths(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn

    def tearDown(self):
        data.conn = self._old_conn
        self.conn.close()

    def test_create_user_creates_isolated_file_roots_and_simple_project_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                security.ensure_security_schema(self.conn)
                projects.ensure_projects_schema(self.conn)

                user_id = security.create_user("alice", "Alice", "password", role="user", is_active=True)

                row = self.conn.execute(
                    "SELECT file_root_path, notes_root_path, projects_root_path, lists_root_path "
                    "FROM users WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                expected_root = os.path.join(tmpdir, "alice")
                self.assertTrue(row["file_root_path"].lower().startswith(expected_root.lower()))
                self.assertTrue(os.path.isdir(row["notes_root_path"]))
                self.assertTrue(os.path.isdir(row["projects_root_path"]))
                self.assertTrue(os.path.isdir(row["lists_root_path"]))
                project_ids = {
                    row["project_id"]
                    for row in self.conn.execute(
                        "SELECT project_id FROM lp_projects WHERE owner_user_id = ?",
                        (user_id,),
                    ).fetchall()
                }
                self.assertEqual(project_ids, {"home", "work", "family", "fun"})
                self.assertEqual(
                    self.conn.execute(
                        "SELECT COUNT(1) AS cnt FROM lp_project_folders WHERE owner_user_id = ?",
                        (user_id,),
                    ).fetchone()["cnt"],
                    0,
                )
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_create_user_accepts_overridden_file_roots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            security.ensure_security_schema(self.conn)
            projects.ensure_projects_schema(self.conn)
            custom_paths = user_paths.paths_from_root(os.path.join(tmpdir, "custom-alice"))

            user_id = security.create_user(
                "alice",
                "Alice",
                "password",
                role="user",
                is_active=True,
                file_paths=custom_paths,
            )

            row = self.conn.execute(
                "SELECT file_root_path, notes_root_path, projects_root_path, lists_root_path "
                "FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            self.assertEqual(row["file_root_path"], custom_paths["file_root_path"])
            self.assertEqual(row["notes_root_path"], custom_paths["notes_root_path"])
            self.assertTrue(os.path.isdir(custom_paths["notes_root_path"]))
            self.assertEqual(
                self.conn.execute(
                    "SELECT COUNT(1) AS cnt FROM lp_project_folders WHERE owner_user_id = ?",
                    (user_id,),
                ).fetchone()["cnt"],
                0,
            )

    def test_admin_submitted_default_username_segment_resolves_to_new_username(self):
        app = Flask(__name__)
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                submitted_root = os.path.join(tmpdir, "username")
                with app.test_request_context(
                    "/admin/users/new",
                    method="POST",
                    data={
                        "username": "alice",
                        "file_root_path": submitted_root,
                        "notes_root_path": os.path.join(submitted_root, "notes"),
                        "projects_root_path": os.path.join(submitted_root, "projects"),
                        "lists_root_path": os.path.join(submitted_root, "lists"),
                    },
                ):
                    paths = admin_routes._default_or_submitted_user_paths("alice")

                self.assertEqual(paths["file_root_path"], os.path.join(tmpdir, "alice"))
                self.assertEqual(paths["notes_root_path"], os.path.join(tmpdir, "alice", "notes"))
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_duncan_paths_fall_back_to_existing_unowned_notes_root(self):
        security.ensure_security_schema(self.conn)
        self.conn.execute(
            """
            CREATE TABLE lp_notes (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                path TEXT,
                owner_user_id INTEGER
            )
            """
        )
        self.conn.execute(
            "INSERT INTO lp_notes(id, file_name, path, owner_user_id) VALUES (?, ?, ?, NULL)",
            (1, "legacy.md", r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers"),
        )

        user_id = security.create_user("duncan", "Duncan", "password", role="admin", is_active=True)

        row = self.conn.execute(
            "SELECT file_root_path, notes_root_path FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        self.assertEqual(row["file_root_path"], r"N:\duncan\LifePIM_Data\DATA")
        self.assertEqual(row["notes_root_path"], r"N:\duncan\LifePIM_Data\DATA\notes")

    def test_notes_root_path_falls_back_to_current_user_notes_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                self.conn.execute(
                    """
                    CREATE TABLE lp_notes (
                        id INTEGER PRIMARY KEY,
                        file_name TEXT,
                        path TEXT,
                        folder_id TEXT,
                        size TEXT,
                        date_modified TEXT,
                        project TEXT,
                        owner_user_id INTEGER,
                        visibility TEXT DEFAULT 'private',
                        is_public INTEGER DEFAULT 0
                    )
                    """
                )
                self.conn.execute(
                    """
                    CREATE TABLE dim_folder (
                        folder_id INTEGER PRIMARY KEY,
                        folder_path TEXT
                    )
                    """
                )
                security.ensure_security_schema(self.conn)
                projects.ensure_projects_schema(self.conn)
                user_id = security.create_user("alice", "Alice", "password", role="user", is_active=True)
                fake_user = type(
                    "FakeUser",
                    (),
                    {"is_authenticated": True, "user_id": user_id, "username": "alice"},
                )()

                with patch("modules.notes.routes.current_user", fake_user):
                    notes_root = notes_routes._notes_root_path()

                self.assertEqual(notes_root, os.path.join(tmpdir, "alice", "notes"))
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_non_duncan_note_create_uses_notes_root_without_project_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                security.ensure_security_schema(self.conn)
                projects.ensure_projects_schema(self.conn)
                self.conn.execute(
                    """
                    CREATE TABLE lp_notes (
                        id INTEGER PRIMARY KEY,
                        file_name TEXT,
                        path TEXT,
                        folder_id TEXT,
                        size TEXT,
                        date_modified TEXT,
                        project TEXT,
                        owner_user_id INTEGER,
                        visibility TEXT DEFAULT 'private',
                        is_public INTEGER DEFAULT 0
                    )
                    """
                )
                user_id = security.create_user("alice", "Alice", "password", role="user", is_active=True)
                fake_user = type(
                    "FakeUser",
                    (),
                    {"is_authenticated": True, "user_id": user_id, "username": "alice"},
                )()

                with patch("modules.notes.routes.current_user", fake_user):
                    folder, project_id = notes_routes._note_create_target_folder("home")

                self.assertEqual(folder, os.path.join(tmpdir, "alice", "notes"))
                self.assertEqual(project_id, "home")
                self.assertTrue(os.path.isdir(folder))
                self.assertFalse(os.path.isdir(os.path.join(tmpdir, "alice", "notes", "home")))
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_duncan_note_create_requires_project_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            security.ensure_security_schema(self.conn)
            projects.ensure_projects_schema(self.conn)
            user_id = security.create_user(
                "duncan",
                "Duncan",
                "password",
                role="admin",
                is_active=True,
                file_paths={
                    "file_root_path": tmpdir,
                    "notes_root_path": os.path.join(tmpdir, "notes"),
                    "projects_root_path": os.path.join(tmpdir, "projects"),
                    "lists_root_path": os.path.join(tmpdir, "lists"),
                },
            )
            projects.project_upsert(
                {
                    "project_id": "home",
                    "tab": "HOME",
                    "group_name": "HOME",
                    "project_name": "Home",
                },
                owner_user_id=user_id,
                conn=self.conn,
            )
            fake_user = type(
                "FakeUser",
                (),
                {"is_authenticated": True, "user_id": user_id, "username": "duncan"},
            )()

            with patch("modules.notes.routes.current_user", fake_user):
                with self.assertRaises(ValueError):
                    notes_routes._note_create_target_folder("home")


if __name__ == "__main__":
    unittest.main()
