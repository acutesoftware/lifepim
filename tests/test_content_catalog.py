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
            ("personal", "Personal"),
            ("house", "House"),
            ("food", "Food"),
            ("work", "Work"),
        ]:
            areas.area_upsert(
                {"area_id": area_id, "tab": "AREAS", "group_name": "AREAS", "area_name": name},
                conn=self.conn,
            )
        content_catalog.ensure_content_catalog_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_schema_tables_exist_and_parent_child_seeded(self):
        tables = {
            row["name"]
            for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        for table_name in [
            "lp_content_kind",
            "lp_content_kind_area",
            "lp_content_pattern",
            "lp_template",
            "lp_content_kind_template",
            "lp_content_view",
            "lp_content_kind_view",
        ]:
            self.assertIn(table_name, tables)

        idea = self.conn.execute(
            "SELECT child.kind_code, parent.kind_code AS parent_code "
            "FROM lp_content_kind child JOIN lp_content_kind parent ON parent.content_kind_id = child.parent_content_kind_id "
            "WHERE child.kind_code = 'IDEA'"
        ).fetchone()
        self.assertEqual(idea["parent_code"], "NOTE")

    def test_unique_codes_are_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            content_catalog.create_template(
                {
                    "template_code": "BLANK_NOTE",
                    "name": "Duplicate",
                    "template_type_code": "NOTE",
                },
                conn=self.conn,
            )

    def test_content_kind_can_map_to_multiple_areas_and_reject_duplicates(self):
        kind_id = content_catalog.create_content_kind(
            {
                "kind_code": "TEST_KIND",
                "name": "Test Kind",
                "object_type_code": "NOTE",
                "area_ids": ["personal", "house"],
                "default_area_id": "house",
            },
            conn=self.conn,
        )

        row = content_catalog.get_content_kind(kind_id, conn=self.conn)
        self.assertEqual(set(row["area_ids"]), {"personal", "house"})
        self.assertEqual(row["default_area_id"], "house")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO lp_content_kind_area(content_kind_id, area_id, created_at, updated_at) "
                "VALUES (?, 'house', 'now', 'now')",
                (kind_id,),
            )

    def test_templates_and_views_can_be_assigned_and_have_one_default(self):
        kind_id = content_catalog._kind_id_by_code(self.conn, "REPAIR_PROJECT")
        t1 = content_catalog._template_id_by_code(self.conn, "SMALL_HOME_REPAIR")
        t2 = content_catalog._template_id_by_code(self.conn, "CAR_REPAIR")
        v1 = content_catalog._view_id_by_code(self.conn, "ACTIVE_PROJECTS")

        content_catalog.set_content_kind_templates(kind_id, [t1, t2], default_template_id=t2, conn=self.conn)
        content_catalog.mark_content_kind_template_default(kind_id, t1, conn=self.conn)
        content_catalog.set_content_kind_views(kind_id, [v1], default_view_id=v1, conn=self.conn)

        template_defaults = self.conn.execute(
            "SELECT template_id FROM lp_content_kind_template WHERE content_kind_id = ? AND is_default = 1",
            (kind_id,),
        ).fetchall()
        view_defaults = self.conn.execute(
            "SELECT content_view_id FROM lp_content_kind_view WHERE content_kind_id = ? AND is_default = 1",
            (kind_id,),
        ).fetchall()
        self.assertEqual([row["template_id"] for row in template_defaults], [t1])
        self.assertEqual([row["content_view_id"] for row in view_defaults], [v1])

    def test_seed_is_idempotent_and_does_not_overwrite_edits(self):
        note_id = content_catalog._kind_id_by_code(self.conn, "NOTE")
        self.conn.execute(
            "UPDATE lp_content_kind SET description = 'Edited description' WHERE content_kind_id = ?",
            (note_id,),
        )
        self.conn.commit()

        content_catalog.seed_content_catalog(self.conn)
        content_catalog.seed_content_catalog(self.conn)

        self.assertEqual(
            self.conn.execute("SELECT description FROM lp_content_kind WHERE kind_code = 'NOTE'").fetchone()["description"],
            "Edited description",
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_kind WHERE kind_code = 'NOTE'").fetchone()["cnt"],
            1,
        )

    def test_service_validation_and_filtering(self):
        with self.assertRaises(ValueError):
            content_catalog.create_content_kind(
                {"kind_code": "bad-code", "name": "Bad", "object_type_code": "NOTE"},
                conn=self.conn,
            )
        with self.assertRaises(ValueError):
            content_catalog.create_content_view(
                {"view_code": "BAD_JSON", "name": "Bad JSON", "view_type_code": "LIST", "view_config": "{bad"},
                conn=self.conn,
            )

        kinds = content_catalog.list_content_kinds(
            conn=self.conn,
            filters={"canonical_tab_code": "NOTES", "object_type_code": "NOTE", "mapping_status_code": "CONFIRMED"},
        )
        self.assertTrue(any(row["kind_code"] == "IDEA" for row in kinds))
        self.assertTrue(all(row["canonical_tab_code"] == "NOTES" for row in kinds))

    def test_deactivate_record(self):
        content_catalog.deactivate_content_kind(content_catalog._kind_id_by_code(self.conn, "BOOK_NOTE"), conn=self.conn)

        active_codes = {row["kind_code"] for row in content_catalog.list_content_kinds(conn=self.conn, filters={})}
        inactive_codes = {
            row["kind_code"]
            for row in content_catalog.list_content_kinds(conn=self.conn, filters={"active": "0"}, include_inactive=True)
        }
        self.assertNotIn("BOOK_NOTE", active_codes)
        self.assertIn("BOOK_NOTE", inactive_codes)


if __name__ == "__main__":
    unittest.main()
