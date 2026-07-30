import os
import sqlite3
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import areas, data, projects


class TestProjects(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        data.conn = self.conn
        areas.ensure_areas_schema(self.conn)
        projects.ensure_projects_schema(self.conn)
        for area_id, name in [
            ("home", "Home"),
            ("family", "Family"),
            ("fun/food", "Food"),
            ("fun/travel", "Travel"),
        ]:
            areas.area_upsert(
                {
                    "area_id": area_id,
                    "tab": "AREAS",
                    "group_name": "AREAS",
                    "area_name": name,
                },
                owner_user_id=1,
                conn=self.conn,
            )

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_schema_tables_are_created(self):
        workspace_cols = [row["name"] for row in self.conn.execute("PRAGMA table_info(lp_project_workspaces)").fetchall()]
        item_cols = [row["name"] for row in self.conn.execute("PRAGMA table_info(lp_project_items)").fetchall()]

        self.assertIn("project_id", workspace_cols)
        self.assertIn("comments", workspace_cols)
        self.assertIn("item_type", item_cols)
        self.assertIn("is_primary", item_cols)

    def test_project_can_link_multiple_areas_and_area_filter_matches_parent_child(self):
        project_id = projects.create_project(
            {
                "name": "Dinner Party - October",
                "status": "active",
                "area_ids": ["fun/food", "family", "home"],
            },
            owner_user_id=1,
            conn=self.conn,
        )

        project = projects.project_get(project_id, owner_user_id=1, conn=self.conn)
        self.assertEqual(set(project["area_ids"]), {"fun/food", "family", "home"})
        self.assertEqual(
            [row["project_id"] for row in projects.project_list(area_id="fun", owner_user_id=1, conn=self.conn)],
            [project_id],
        )
        self.assertEqual(
            [row["project_id"] for row in projects.project_list(area_id="fun/food", owner_user_id=1, conn=self.conn)],
            [project_id],
        )
        self.assertEqual(projects.project_list(area_id="fun/travel", owner_user_id=1, conn=self.conn), [])

    def test_project_items_are_references_and_can_belong_to_multiple_projects(self):
        dinner_id = projects.create_project(
            {"name": "Dinner Party", "status": "active", "area_ids": ["fun/food"]},
            owner_user_id=1,
            conn=self.conn,
        )
        christmas_id = projects.create_project(
            {"name": "Christmas Lunch", "status": "planned", "area_ids": ["family"]},
            owner_user_id=1,
            conn=self.conn,
        )
        self.conn.execute("CREATE TABLE lp_tasks (id INTEGER PRIMARY KEY, title TEXT, area TEXT)")
        self.conn.execute("INSERT INTO lp_tasks (id, title, area) VALUES (7, 'Roast lamb prep', 'fun/food')")

        projects.add_project_item(dinner_id, "task", "7", item_title="Roast lamb prep", owner_user_id=1, conn=self.conn)
        projects.add_project_item(christmas_id, "task", "7", item_title="Roast lamb prep", owner_user_id=1, conn=self.conn)

        self.assertEqual(len(projects.record_projects("task", "7", owner_user_id=1, conn=self.conn)), 2)
        task = self.conn.execute("SELECT title, area FROM lp_tasks WHERE id = 7").fetchone()
        self.assertEqual(dict(task), {"title": "Roast lamb prep", "area": "fun/food"})

    def test_primary_project_is_unique_for_an_item(self):
        first_id = projects.create_project({"name": "Rome 2027", "status": "active"}, owner_user_id=1, conn=self.conn)
        second_id = projects.create_project({"name": "Passport Renewal", "status": "active"}, owner_user_id=1, conn=self.conn)

        projects.add_project_item(first_id, "task", "9", item_title="Renew Passport", is_primary=1, owner_user_id=1, conn=self.conn)
        projects.add_project_item(second_id, "task", "9", item_title="Renew Passport", is_primary=1, owner_user_id=1, conn=self.conn)

        rows = projects.record_projects("task", "9", owner_user_id=1, conn=self.conn)
        primary = [row for row in rows if row["is_primary"]]
        self.assertEqual(len(primary), 1)
        self.assertEqual(primary[0]["project_id"], second_id)

    def test_record_projects_accepts_integer_record_ids(self):
        project_id = projects.create_project({"name": "Integer IDs", "status": "active"}, owner_user_id=1, conn=self.conn)
        projects.add_project_item(project_id, "note", 12, item_title="Integer note", owner_user_id=1, conn=self.conn)

        rows = projects.record_projects("note", 12, owner_user_id=1, conn=self.conn)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project_id"], project_id)


if __name__ == "__main__":
    unittest.main()
