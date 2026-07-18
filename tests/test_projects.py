import os
import sqlite3
import tempfile
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import projects


class TestProjects(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        projects.ensure_projects_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_columns(self):
        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(lp_projects)").fetchall()]
        expected = [
            "owner_user_id",
            "project_id",
            "icon",
            "tab",
            "group_name",
            "project_name",
            "is_header",
            "is_system",
            "status",
            "tags",
            "sort_order",
            "pinned",
            "notes",
            "created_utc",
            "updated_utc",
        ]
        self.assertEqual(cols, expected)

        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(lp_project_folders)").fetchall()]
        expected = [
            "project_folder_id",
            "owner_user_id",
            "project_id",
            "path_prefix",
            "folder_role",
            "create_type",
            "is_write_enabled",
            "confidence",
            "tags",
            "notes",
            "sort_order",
            "is_enabled",
            "created_utc",
            "updated_utc",
        ]
        self.assertEqual(cols, expected)

    def test_default_folder_uniqueness(self):
        project_id = "pers.health"
        projects.project_upsert(
            {
                "project_id": project_id,
                "tab": "PERS",
                "group_name": "Health",
                "project_name": "Health",
            },
            conn=self.conn,
        )
        folder1 = projects.project_folder_add(
            project_id,
            r"C:\\Notes\\Health",
            folder_role="include",
            conn=self.conn,
        )
        folder2 = projects.project_folder_add(
            project_id,
            r"C:\\Notes\\Health2",
            folder_role="include",
            conn=self.conn,
        )
        projects.project_folder_set_default(project_id, folder1, conn=self.conn)
        projects.project_folder_set_default(project_id, folder2, conn=self.conn)
        rows = self.conn.execute(
            "SELECT project_folder_id, folder_role, is_write_enabled FROM lp_project_folders "
            "WHERE project_id = ? AND folder_role = 'default'",
            (project_id,),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project_folder_id"], folder2)
        self.assertEqual(rows[0]["is_write_enabled"], 1)

    def test_default_folder_get(self):
        project_id = "fun.sport"
        projects.project_upsert(
            {
                "project_id": project_id,
                "tab": "FUN",
                "group_name": "Sport",
                "project_name": "Sports",
            },
            conn=self.conn,
        )
        self.assertIsNone(projects.project_default_folder_get(project_id, conn=self.conn))
        folder_id = projects.project_folder_add(
            project_id,
            r"C:\\Notes\\Sport",
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        self.assertTrue(folder_id)
        self.assertEqual(
            projects.project_default_folder_get(project_id, conn=self.conn),
            os.path.abspath(r"C:\\Notes\\Sport"),
        )

    def test_shared_folder_allowed(self):
        projects.project_upsert(
            {
                "project_id": "proj.one",
                "tab": "WORK",
                "group_name": "One",
                "project_name": "One",
            },
            conn=self.conn,
        )
        projects.project_upsert(
            {
                "project_id": "proj.two",
                "tab": "WORK",
                "group_name": "Two",
                "project_name": "Two",
            },
            conn=self.conn,
        )
        path = r"C:\\Notes\\Shared"
        id1 = projects.project_folder_add("proj.one", path, conn=self.conn)
        id2 = projects.project_folder_add("proj.two", path, conn=self.conn)
        self.assertTrue(id1)
        self.assertTrue(id2)

    def test_project_folders_are_scoped_by_user(self):
        project_id = "pers/health"
        folder_ids = {}
        for owner_id, path in [(1, r"C:\\Users\\One\\notes\\health"), (2, r"C:\\Users\\Two\\notes\\health")]:
            projects.project_upsert(
                {
                    "project_id": project_id,
                    "tab": "PERS",
                    "group_name": "PERS",
                    "project_name": "Health",
                },
                owner_user_id=owner_id,
                conn=self.conn,
            )
            folder_ids[owner_id] = projects.project_folder_add(
                project_id,
                path,
                folder_role="default",
                is_write_enabled=1,
                owner_user_id=owner_id,
                conn=self.conn,
            )

        self.assertIn(
            r"One\notes\health".lower(),
            projects.project_default_folder_get(project_id, owner_user_id=1, conn=self.conn).lower(),
        )
        self.assertIn(
            r"Two\notes\health".lower(),
            projects.project_default_folder_get(project_id, owner_user_id=2, conn=self.conn).lower(),
        )
        self.assertEqual(
            len(projects.project_folders_list(project_id, owner_user_id=1, conn=self.conn)),
            1,
        )
        projects.project_folder_set_default(project_id, folder_ids[2], owner_user_id=1, conn=self.conn)
        self.assertIn(
            r"One\notes\health".lower(),
            projects.project_default_folder_get(project_id, owner_user_id=1, conn=self.conn).lower(),
        )
        projects.project_folder_disable(folder_ids[2], owner_user_id=1, conn=self.conn)
        row = self.conn.execute(
            "SELECT is_enabled FROM lp_project_folders WHERE project_folder_id = ?",
            (folder_ids[2],),
        ).fetchone()
        self.assertEqual(row["is_enabled"], 1)
        projects.project_folder_remove(folder_ids[2], owner_user_id=1, conn=self.conn)
        row = self.conn.execute(
            "SELECT project_folder_id FROM lp_project_folders WHERE project_folder_id = ?",
            (folder_ids[2],),
        ).fetchone()
        self.assertIsNotNone(row)

    def test_default_project_folders_for_new_user_use_user_notes_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = os.environ.get("LIFEPIM_LAN_USER_ROOT_BASE")
            os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = tmpdir
            try:
                self.conn.execute(
                    """
                    CREATE TABLE users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        display_name TEXT,
                        password_hash TEXT,
                        role TEXT,
                        is_active INTEGER
                    )
                    """
                )
                self.conn.execute(
                    "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
                    "VALUES (7, 'alice', 'Alice', 'hash', 'user', 1)"
                )
                projects.seed_default_projects_for_user(7, conn=self.conn)

                created = projects.ensure_default_project_folders_for_user(
                    7,
                    username="alice",
                    conn=self.conn,
                    create_dirs=True,
                )

                self.assertGreater(created, 0)
                default_path = projects.project_default_folder_get(
                    "home",
                    owner_user_id=7,
                    conn=self.conn,
                )
                expected_prefix = os.path.join(tmpdir, "alice", "notes")
                self.assertTrue(default_path.lower().startswith(expected_prefix.lower()))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "notes")))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "projects")))
                self.assertTrue(os.path.isdir(os.path.join(tmpdir, "alice", "lists")))
            finally:
                if old_env is None:
                    os.environ.pop("LIFEPIM_LAN_USER_ROOT_BASE", None)
                else:
                    os.environ["LIFEPIM_LAN_USER_ROOT_BASE"] = old_env

    def test_legacy_project_folders_are_claimed_for_duncan_on_migration(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, password_hash TEXT, role TEXT, is_active INTEGER)"
            )
            conn.execute(
                "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
                "VALUES (3, 'duncan', 'Duncan', 'hash', 'admin', 1)"
            )
            conn.execute(
                """
                CREATE TABLE lp_projects (
                    owner_user_id INTEGER,
                    project_id TEXT,
                    icon TEXT,
                    tab TEXT,
                    group_name TEXT,
                    project_name TEXT,
                    is_header INTEGER,
                    is_system INTEGER,
                    status TEXT,
                    tags TEXT,
                    sort_order INTEGER,
                    pinned INTEGER,
                    notes TEXT,
                    created_utc TEXT,
                    updated_utc TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO lp_projects VALUES (3, 'pers/health', '', 'PERS', 'PERS', 'Health', 0, 0, 'active', NULL, 10, 0, NULL, 'now', 'now')"
            )
            conn.execute(
                """
                CREATE TABLE lp_project_folders (
                    project_folder_id INTEGER PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    path_prefix TEXT NOT NULL,
                    folder_role TEXT NOT NULL,
                    create_type TEXT NOT NULL DEFAULT 'none',
                    is_write_enabled INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 1.0,
                    tags TEXT,
                    notes TEXT,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_utc TEXT NOT NULL,
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO lp_project_folders VALUES "
                "(11, 'pers/health', 'N:\\duncan\\LifePIM_Data\\DATA\\notes\\10-Pers\\12-Health', "
                "'default', 'none', 1, 1.0, NULL, NULL, 100, 1, 'now', 'now')"
            )

            projects.ensure_projects_schema(conn)

            row = conn.execute(
                "SELECT owner_user_id, path_prefix FROM lp_project_folders WHERE project_folder_id = 11"
            ).fetchone()
            self.assertEqual(row["owner_user_id"], 3)
            self.assertEqual(row["path_prefix"], r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health")
        finally:
            conn.close()

    def test_user_sidebar_can_be_saved_and_reset(self):
        projects.seed_default_projects_for_user(1, conn=self.conn)
        default_rows = projects.projects_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertGreater(len(default_rows), 1)

        projects.save_user_sidebar_rows(
            [
                {
                    "project_id": "All",
                    "project_name": "All Projects",
                    "icon": "*",
                    "group_name": "Projects",
                    "is_system": 1,
                },
                {
                    "project_id": "work/client",
                    "project_name": "Client",
                    "icon": "W",
                    "group_name": "WORK",
                },
            ],
            owner_user_id=1,
            conn=self.conn,
        )
        rows = projects.projects_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertEqual([row["id"] for row in rows], ["All", "work/client"])

        projects.seed_default_projects_for_user(1, conn=self.conn, replace=True)
        reset_rows = projects.projects_side_tabs(owner_user_id=1, conn=self.conn, seed=False)
        self.assertEqual(len(reset_rows), len(default_rows))

    def test_flat_legacy_sidebar_is_restored_to_default_structure(self):
        for project_id, name in [("work/job", "Job"), ("make/design", "Design")]:
            projects.project_upsert(
                {
                    "project_id": project_id,
                    "tab": "LEGACY",
                    "group_name": "Legacy",
                    "project_name": name,
                    "sort_order": 100,
                },
                owner_user_id=1,
                conn=self.conn,
            )

        count = projects.seed_default_projects_for_user(1, conn=self.conn)
        rows = projects.projects_side_tabs(owner_user_id=1, conn=self.conn, seed=False)

        self.assertGreater(count, 2)
        self.assertEqual(rows[0]["id"], "All")
        self.assertTrue(any(row["is_header"] for row in rows))
        self.assertTrue(any(row["icon"] for row in rows))
        self.assertIn("All", [row["id"] for row in rows])


if __name__ == "__main__":
    unittest.main()
