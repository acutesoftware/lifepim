import os
import sqlite3
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import areas, collections, data, projects
import etl_folder_mapping as folder_etl


class TestCollections(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        data.conn = self.conn
        self.conn.execute(
            "CREATE TABLE lp_notes (id INTEGER PRIMARY KEY, file_name TEXT, path TEXT, area TEXT, owner_user_id INTEGER, rec_extract_date TEXT)"
        )
        self.conn.execute("INSERT INTO lp_notes(id, file_name, path, area, owner_user_id, rec_extract_date) VALUES (1, 'Rome.md', 'notes', 'fun/travel', 1, 'now')")
        self.conn.execute("INSERT INTO lp_notes(id, file_name, path, area, owner_user_id, rec_extract_date) VALUES (2, 'Food.md', 'notes', 'fun/food', 1, 'now')")
        areas.ensure_areas_schema(self.conn)
        projects.ensure_projects_schema(self.conn)
        collections.ensure_collections_schema(self.conn)
        self.conn.executescript(folder_etl.DDL_CREATE_NO_FK)
        for area_id, name in [("fun", "Fun"), ("fun/travel", "Travel"), ("family", "Family")]:
            areas.area_upsert(
                {"area_id": area_id, "tab": "AREAS", "group_name": "AREAS", "area_name": name},
                owner_user_id=1,
                conn=self.conn,
            )

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_schema_tables_are_created(self):
        collection_cols = [row["name"] for row in self.conn.execute("PRAGMA table_info(lp_collection)").fetchall()]
        item_cols = [row["name"] for row in self.conn.execute("PRAGMA table_info(lp_collection_item)").fetchall()]

        self.assertIn("collection_domain", collection_cols)
        self.assertIn("visibility", collection_cols)
        self.assertIn("parent_collection_item_id", item_cols)
        self.assertIn("child_collection_id", item_cols)

    def test_lifecycle_archive_restore_and_delete_preserves_notes(self):
        collection_id = collections.create_collection(
            {
                "collection_name": "Rome Research",
                "collection_domain": "notes",
                "collection_type": "notebook",
                "description": "Trip notes",
                "area_ids": ["fun/travel", "family"],
            },
            owner_user_id=1,
            conn=self.conn,
        )
        collections.add_item_to_collection(collection_id, "note", 1, owner_user_id=1, conn=self.conn)

        collections.archive_collection(collection_id, owner_user_id=1, conn=self.conn)
        self.assertEqual(collections.get_collection(collection_id, owner_user_id=1, conn=self.conn)["status"], "archived")
        collections.restore_collection(collection_id, owner_user_id=1, conn=self.conn)
        self.assertEqual(collections.get_collection(collection_id, owner_user_id=1, conn=self.conn)["status"], "active")

        collections.delete_collection(collection_id, owner_user_id=1, conn=self.conn)
        self.assertIsNone(collections.get_collection(collection_id, owner_user_id=1, conn=self.conn))
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM lp_notes WHERE id = 1").fetchone())
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_collection_item").fetchone()[0], 0)

    def test_item_membership_ordering_headings_and_duplicates(self):
        collection_id = collections.create_collection(
            {"collection_name": "Manual", "collection_domain": "notes", "collection_type": "book"},
            owner_user_id=1,
            conn=self.conn,
        )
        heading = collections.add_heading_to_collection(collection_id, "Introduction", owner_user_id=1, conn=self.conn)
        first = collections.add_item_to_collection(collection_id, "note", 1, owner_user_id=1, conn=self.conn)
        second = collections.add_item_to_collection(collection_id, "note", 2, owner_user_id=1, conn=self.conn)
        duplicate = collections.add_item_to_collection(collection_id, "note", 1, owner_user_id=1, conn=self.conn)

        self.assertFalse(duplicate["created"])
        self.assertEqual(duplicate["collection_item_id"], first["collection_item_id"])

        collections.move_collection_item(second["collection_item_id"], direction="up", owner_user_id=1, conn=self.conn)
        items = collections.get_collection_items(collection_id, owner_user_id=1, conn=self.conn)
        self.assertEqual([item["collection_item_id"] for item in items], [heading["collection_item_id"], second["collection_item_id"], first["collection_item_id"]])
        self.assertEqual(items[0]["entry_kind"], "heading")
        self.assertEqual(items[0]["display_title"], "Introduction")

    def test_area_and_project_filters_are_explicit_relationships(self):
        project_id = projects.create_project(
            {"name": "Rome 2027", "status": "active", "area_ids": ["fun/travel"]},
            owner_user_id=1,
            conn=self.conn,
        )
        collection_id = collections.create_collection(
            {
                "collection_name": "Rome Research",
                "collection_domain": "notes",
                "collection_type": "notebook",
                "area_ids": ["fun/travel", "family"],
                "project_ids": [project_id],
            },
            owner_user_id=1,
            conn=self.conn,
        )
        collections.add_item_to_collection(collection_id, "note", 1, owner_user_id=1, conn=self.conn)

        self.assertEqual(
            [row["collection_id"] for row in collections.get_collection_list(domain="notes", area_id="fun", owner_user_id=1, conn=self.conn)],
            [collection_id],
        )
        self.assertEqual(
            [row["collection_id"] for row in collections.get_collection_list(domain="notes", project_id=project_id, owner_user_id=1, conn=self.conn)],
            [collection_id],
        )
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_project_items").fetchone()[0], 0)

    def test_nested_collection_cycle_is_rejected(self):
        parent_id = collections.create_collection(
            {"collection_name": "Book", "collection_domain": "notes", "collection_type": "book"},
            owner_user_id=1,
            conn=self.conn,
        )
        child_id = collections.create_collection(
            {"collection_name": "Chapter", "collection_domain": "notes", "collection_type": "notebook"},
            owner_user_id=1,
            conn=self.conn,
        )

        collections.add_collection_to_collection(parent_id, child_id, owner_user_id=1, conn=self.conn)

        with self.assertRaises(ValueError):
            collections.add_collection_to_collection(child_id, parent_id, owner_user_id=1, conn=self.conn)

    def test_notes_route_renders_notebooks_view(self):
        from app import app

        data.conn = self.conn
        self.conn.execute(
            "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
            "VALUES (1, 'alice', 'Alice', 'hash', 'user', 1)"
        )
        collections.create_collection(
            {"collection_name": "Route Notebook", "collection_domain": "notes", "collection_type": "notebook"},
            owner_user_id=1,
            conn=self.conn,
        )
        app.config["TESTING"] = True
        with app.test_client() as client:
            with client.session_transaction() as session:
                session["_user_id"] = "1"
                session["_fresh"] = True
            response = client.get("/notes/notebooks")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Route Notebook", response.data)
        self.assertIn(b"Available Notes", response.data)


if __name__ == "__main__":
    unittest.main()
