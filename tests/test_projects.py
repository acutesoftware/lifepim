import os
import sqlite3
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
            "project_id",
            "tab",
            "group_name",
            "project_name",
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


if __name__ == "__main__":
    unittest.main()
