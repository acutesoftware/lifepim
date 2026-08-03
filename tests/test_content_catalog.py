import os
import sqlite3
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import areas, content_catalog


class TestContentCatalog(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        areas.ensure_areas_schema(self.conn)
        for area_id, name in [
            ("computers", "Computers"),
            ("health", "Health"),
            ("vehicles", "Vehicles"),
            ("food", "Food"),
        ]:
            areas.area_upsert(
                {"area_id": area_id, "tab": "AREAS", "group_name": "AREAS", "area_name": name},
                conn=self.conn,
            )

    def tearDown(self):
        self.conn.close()

    def _old_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE lp_content_kind (
                content_kind_id INTEGER PRIMARY KEY,
                kind_code TEXT NOT NULL UNIQUE,
                parent_content_kind_id INTEGER,
                name TEXT NOT NULL,
                plural_name TEXT,
                description TEXT,
                object_type_code TEXT NOT NULL,
                canonical_tab_code TEXT,
                canonical_table_name TEXT,
                subtype_code TEXT,
                date_behaviour_code TEXT NOT NULL DEFAULT 'NONE',
                mapping_status_code TEXT NOT NULL DEFAULT 'UNDECIDED',
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE lp_content_kind_area (
                content_kind_area_id INTEGER PRIMARY KEY,
                content_kind_id INTEGER NOT NULL,
                area_id TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                display_name_override TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (content_kind_id) REFERENCES lp_content_kind(content_kind_id),
                UNIQUE (content_kind_id, area_id)
            );
            INSERT INTO lp_content_kind
            (content_kind_id, kind_code, name, description, object_type_code, canonical_tab_code, notes, created_at, updated_at)
            VALUES
            (10, 'BACKUP_SOURCES', 'Backup sources', 'Folders included', 'FILE', 'FILES', 'Folders included', 'now', 'now'),
            (11, 'BACKUP_SCHEDULE', 'Backup schedule', 'Recurring task', 'TASK', 'GOALS', 'Run each backup set', 'now', 'now'),
            (12, 'FIRST_AREA', 'First area wins', '', 'NOTE', 'NOTES', 'Only notes', 'now', 'now');
            INSERT INTO lp_content_kind_area
            (content_kind_area_id, content_kind_id, area_id, is_default, sort_order, created_at, updated_at)
            VALUES
            (1, 10, 'vehicles', 0, 10, 'now', 'now'),
            (2, 10, 'computers', 1, 20, 'now', 'now'),
            (3, 11, 'computers', 0, 10, 'now', 'now'),
            (4, 12, 'health', 0, 20, 'now', 'now'),
            (5, 12, 'food', 0, 10, 'now', 'now');
            """
        )
        self.conn.commit()

    def _seed_rows(self):
        content_catalog.ensure_content_catalog_schema(self.conn)
        return [
            content_catalog.create_content_kind(
                {"name": "Backup sources", "area_id": "computers", "tab_code": "FILES", "comment": "Folders to back up"},
                conn=self.conn,
            ),
            content_catalog.create_content_kind(
                {"name": "Backup schedule", "area_id": "computers", "tab_code": "GOALS", "comment": "Recurring task"},
                conn=self.conn,
            ),
            content_catalog.create_content_kind(
                {"name": "Car service history", "area_id": "vehicles", "tab_code": "NOTES", "comment": "Servicing notes"},
                conn=self.conn,
            ),
            content_catalog.create_content_kind(
                {"name": "Unsorted idea", "comment": "Needs classification"},
                conn=self.conn,
            ),
        ]

    def test_empty_catalog_schema_does_not_seed_samples(self):
        content_catalog.ensure_content_catalog_schema(self.conn)

        columns = [row["name"] for row in self.conn.execute("PRAGMA table_info(lp_content_kind)").fetchall()]
        self.assertEqual(columns, ["content_kind_id", "name", "area_id", "tab_code", "comment"])
        self.assertEqual(self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind").fetchone()["cnt"], 0)

    def test_old_schema_migrates_once_and_preserves_backup_ids_area_and_comments(self):
        self._old_schema()

        content_catalog.ensure_content_catalog_schema(self.conn)
        content_catalog.ensure_content_catalog_schema(self.conn)

        rows = {row["content_kind_id"]: dict(row) for row in self.conn.execute("SELECT * FROM lp_content_kind").fetchall()}
        self.assertEqual(set(rows), {10, 11, 12})
        self.assertEqual(rows[10]["area_id"], "computers")
        self.assertEqual(rows[11]["comment"], "Recurring task\nRun each backup set")
        self.assertEqual(rows[12]["area_id"], "food")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind_legacy_v1").fetchone()["cnt"],
            3,
        )
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_create_update_search_and_summary(self):
        content_catalog.ensure_content_catalog_schema(self.conn)

        item_id = content_catalog.create_content_kind({"name": "Bone health injection"}, conn=self.conn)
        row = content_catalog.get_content_kind(item_id, conn=self.conn)
        self.assertEqual(row["name"], "Bone health injection")
        self.assertIsNone(row["area_id"])

        content_catalog.update_content_kind(
            item_id,
            {"name": "Bone health injection", "area_id": "health", "tab_code": "CALENDAR", "comment": "Six-monthly appointment"},
            conn=self.conn,
        )

        row = content_catalog.get_content_kind(item_id, conn=self.conn)
        self.assertEqual(row["area_id"], "health")
        self.assertEqual(row["tab_code"], "CALENDAR")
        self.assertEqual(content_catalog.list_content_kinds(filters={"q": "Six-monthly"}, conn=self.conn)[0]["content_kind_id"], item_id)
        self.assertEqual(content_catalog.catalog_summary(self.conn)["complete"], 1)

    def test_matrix_and_reports_group_by_area_and_tab(self):
        self._seed_rows()

        matrix = content_catalog.content_catalog_matrix(conn=self.conn)
        cell = matrix["cells"]["computers|FILES"]
        self.assertEqual(cell["total"], 1)
        self.assertEqual(cell["items"], ["Backup sources"])

        by_area = content_catalog.content_catalog_report("by-area", conn=self.conn)
        computers = next(section for section in by_area["sections"] if section["label"] == "Computers")
        tab_labels = {tab["label"] for tab in computers["tabs"]}
        self.assertIn("Files", {label.title() for label in tab_labels})
        self.assertIn("Goals / Tasks", tab_labels)

        by_tab = content_catalog.content_catalog_report("by-tab", conn=self.conn)
        files = next(section for section in by_tab["sections"] if section["label"] == "FILES")
        self.assertEqual(files["areas"][0]["label"], "Computers")

    def test_templates_views_and_patterns_still_link_by_content_kind_id(self):
        kind_id = self._seed_rows()[0]
        template_id = content_catalog.create_template(
            {"template_code": "BACKUP_NOTE", "name": "Backup Note", "template_type_code": "NOTE", "content_kind_ids": [kind_id]},
            conn=self.conn,
        )
        view_id = content_catalog.create_content_view(
            {"view_code": "BACKUP_VIEW", "name": "Backup View", "view_type_code": "LIST", "content_kind_ids": [kind_id]},
            conn=self.conn,
        )
        pattern_id = content_catalog.create_content_pattern(
            {"pattern_code": "BACKUP_PATTERN", "name": "Backup Pattern", "content_kind_id": kind_id},
            conn=self.conn,
        )

        self.assertEqual(content_catalog.list_templates(conn=self.conn, include_inactive=True)[0]["content_kinds"][0]["name"], "Backup sources")
        self.assertEqual(content_catalog.list_content_views(conn=self.conn, include_inactive=True)[0]["content_kinds"][0]["name"], "Backup sources")
        self.assertEqual(content_catalog.list_content_patterns(conn=self.conn, include_inactive=True)[0]["content_kind_name"], "Backup sources")
        self.assertTrue(template_id)
        self.assertTrue(view_id)
        self.assertTrue(pattern_id)

    def test_delete_rejects_pattern_reference_then_deletes_link_rows(self):
        kind_id = self._seed_rows()[0]
        template_id = content_catalog.create_template(
            {"template_code": "DELETE_LINK_TEMPLATE", "name": "Delete Link Template", "template_type_code": "NOTE", "content_kind_ids": [kind_id]},
            conn=self.conn,
        )
        view_id = content_catalog.create_content_view(
            {"view_code": "DELETE_LINK_VIEW", "name": "Delete Link View", "view_type_code": "LIST", "content_kind_ids": [kind_id]},
            conn=self.conn,
        )
        pattern_id = content_catalog.create_content_pattern(
            {"pattern_code": "DELETE_BLOCK_PATTERN", "name": "Delete Block Pattern", "content_kind_id": kind_id},
            conn=self.conn,
        )

        with self.assertRaises(ValueError):
            content_catalog.remove_content_kind(kind_id, conn=self.conn)

        content_catalog.remove_content_pattern(pattern_id, conn=self.conn)
        self.assertEqual(content_catalog.remove_content_kind(kind_id, conn=self.conn)["removed"], True)
        self.assertIsNone(content_catalog.get_content_kind(kind_id, conn=self.conn))
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind_template WHERE template_id = ?", (template_id,)).fetchone()["cnt"],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind_view WHERE content_view_id = ?", (view_id,)).fetchone()["cnt"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
