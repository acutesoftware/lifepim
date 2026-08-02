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
            "lp_content_catalog_meta",
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

    def test_seeded_samples_are_not_restored_after_seed_version_is_applied(self):
        template_id = content_catalog._template_id_by_code(self.conn, "BLANK_NOTE")
        content_catalog.remove_template(template_id, conn=self.conn)

        content_catalog.ensure_content_catalog_schema(self.conn)

        self.assertIsNone(content_catalog._template_id_by_code(self.conn, "BLANK_NOTE"))

    def test_template_and_view_editor_paths_keep_one_default_per_kind(self):
        note_id = content_catalog._kind_id_by_code(self.conn, "NOTE")
        idea_template_id = content_catalog._template_id_by_code(self.conn, "IDEA_NOTE")
        recent_notes_view_id = content_catalog._view_id_by_code(self.conn, "RECENT_NOTES")
        journal_view_id = content_catalog._view_id_by_code(self.conn, "JOURNAL_TIMELINE")

        idea_template = next(row for row in content_catalog.list_templates(conn=self.conn, include_inactive=True) if row["template_id"] == idea_template_id)
        idea_template["content_kind_ids"] = [note_id]
        idea_template["default_content_kind_id"] = note_id
        content_catalog.update_template(idea_template_id, idea_template, conn=self.conn)

        journal_view = next(row for row in content_catalog.list_content_views(conn=self.conn, include_inactive=True) if row["content_view_id"] == journal_view_id)
        journal_view["content_kind_ids"] = [note_id]
        journal_view["default_content_kind_id"] = note_id
        content_catalog.update_content_view(journal_view_id, journal_view, conn=self.conn)

        template_defaults = self.conn.execute(
            "SELECT template_id FROM lp_content_kind_template WHERE content_kind_id = ? AND is_default = 1",
            (note_id,),
        ).fetchall()
        view_defaults = self.conn.execute(
            "SELECT content_view_id FROM lp_content_kind_view WHERE content_kind_id = ? AND is_default = 1",
            (note_id,),
        ).fetchall()
        self.assertEqual([row["template_id"] for row in template_defaults], [idea_template_id])
        self.assertEqual([row["content_view_id"] for row in view_defaults], [journal_view_id])
        self.assertNotEqual(recent_notes_view_id, journal_view_id)

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

    def test_pattern_list_is_not_duplicated_by_duplicate_area_rows(self):
        areas.area_upsert(
            {"area_id": "work", "tab": "AREAS", "group_name": "AREAS", "area_name": "Work Duplicate"},
            owner_user_id=99,
            conn=self.conn,
        )
        pattern_id = content_catalog.create_content_pattern(
            {
                "pattern_code": "WORK_DUPLICATE_CHECK",
                "name": "Work Duplicate Check",
                "content_kind_id": content_catalog._kind_id_by_code(self.conn, "IDEA"),
                "default_area_id": "work",
            },
            conn=self.conn,
        )

        rows = content_catalog.list_content_patterns(conn=self.conn, include_inactive=True)
        ids = [row["content_pattern_id"] for row in rows]

        self.assertEqual(ids.count(pattern_id), 1)
        self.assertEqual(len(ids), len(set(ids)))

    def test_remove_pattern_template_and_view_delete_rows_and_clear_defaults(self):
        kind_id = content_catalog._kind_id_by_code(self.conn, "IDEA")
        template_id = content_catalog.create_template(
            {
                "template_code": "REMOVE_ME_TEMPLATE",
                "name": "Remove Me Template",
                "template_type_code": "NOTE",
                "content_kind_ids": [kind_id],
                "default_content_kind_id": kind_id,
            },
            conn=self.conn,
        )
        view_id = content_catalog.create_content_view(
            {
                "view_code": "REMOVE_ME_VIEW",
                "name": "Remove Me View",
                "view_type_code": "LIST",
                "content_kind_ids": [kind_id],
                "default_content_kind_id": kind_id,
            },
            conn=self.conn,
        )
        pattern_id = content_catalog.create_content_pattern(
            {
                "pattern_code": "REMOVE_ME_PATTERN",
                "name": "Remove Me Pattern",
                "content_kind_id": kind_id,
                "default_template_id": template_id,
                "default_view_id": view_id,
            },
            conn=self.conn,
        )

        self.assertEqual(content_catalog.remove_template(template_id, conn=self.conn), {"removed": True, "deactivated": False})
        self.assertEqual(content_catalog.remove_content_view(view_id, conn=self.conn), {"removed": True, "deactivated": False})

        pattern = self.conn.execute(
            "SELECT default_template_id, default_view_id FROM lp_content_pattern WHERE content_pattern_id = ?",
            (pattern_id,),
        ).fetchone()
        self.assertIsNone(pattern["default_template_id"])
        self.assertIsNone(pattern["default_view_id"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_template WHERE template_id = ?", (template_id,)).fetchone()["cnt"],
            0,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_view WHERE content_view_id = ?", (view_id,)).fetchone()["cnt"],
            0,
        )

        self.assertEqual(content_catalog.remove_content_pattern(pattern_id, conn=self.conn), {"removed": True, "deactivated": False})
        self.assertEqual(
            self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_content_pattern WHERE content_pattern_id = ?", (pattern_id,)).fetchone()["cnt"],
            0,
        )

    def test_matrix_counts_area_tab_mappings_and_hides_roots_by_default(self):
        matrix = content_catalog.content_catalog_matrix(conn=self.conn)
        needs_object_matrix = content_catalog.content_catalog_matrix({"mapping_status_code": "NEEDS_OBJECT"}, conn=self.conn)

        self.assertGreater(matrix["totals"]["unique_kinds"], 0)
        self.assertGreaterEqual(matrix["totals"]["matrix_placements"], matrix["totals"]["unique_kinds"])
        self.assertLessEqual(matrix["totals"]["assigned_area_mappings"], matrix["totals"]["matrix_placements"])
        self.assertGreater(needs_object_matrix["totals"]["statuses"]["NEEDS_OBJECT"], 0)
        self.assertEqual(needs_object_matrix["totals"]["statuses"]["CONFIRMED"], 0)
        self.assertIn(content_catalog.UNASSIGNED_AREA_ID, [row["area_id"] for row in matrix["areas"]])
        self.assertIn(content_catalog.NO_TAB_CODE, [col["code"] for col in matrix["tabs"]])

        root_note_id = content_catalog._kind_id_by_code(self.conn, "NOTE")
        self.conn.execute(
            "INSERT OR IGNORE INTO lp_content_kind_area(content_kind_id, area_id, created_at, updated_at) "
            "VALUES (?, 'personal', 'now', 'now')",
            (root_note_id,),
        )
        self.conn.commit()
        without_roots = content_catalog.content_catalog_matrix(conn=self.conn)
        with_roots = content_catalog.content_catalog_matrix({"include_roots": "1"}, conn=self.conn)

        self.assertGreater(with_roots["totals"]["unique_kinds"], without_roots["totals"]["unique_kinds"])

    def test_matrix_uses_sidebar_visible_area_source_not_all_area_rows(self):
        areas.area_upsert(
            {
                "area_id": "home",
                "tab": "Areas",
                "group_name": "Areas",
                "area_name": "Home",
                "status": "active",
            },
            owner_user_id=99,
            conn=self.conn,
        )

        matrix = content_catalog.content_catalog_matrix(conn=self.conn)

        self.assertNotIn("home", {row["area_id"] for row in matrix["areas"]})

    def test_cell_details_are_loaded_for_area_and_tab(self):
        rows = content_catalog.content_catalog_cell_details("house", "GOALS", conn=self.conn)

        codes = {row["kind_code"] for row in rows}
        self.assertIn("REPAIR_PROJECT", codes)
        repair = next(row for row in rows if row["kind_code"] == "REPAIR_PROJECT")
        self.assertEqual(repair["default_template"]["code"], "SMALL_HOME_REPAIR")

    def test_report_coverage_groups_are_generated_from_current_catalog(self):
        report = content_catalog.content_catalog_report("coverage-gaps", conn=self.conn)

        labels = [section["label"] for section in report["sections"]]
        self.assertIn("Needs Templates", labels)
        self.assertIn("Canonical Table Does Not Exist", labels)
        self.assertIn("No Area Mapping", labels)
        self.assertTrue(any(section["items"] for section in report["sections"] if section["label"] == "Needs Objects"))

    def test_event_seed_uses_calendar_events_as_canonical_table(self):
        row = self.conn.execute("SELECT canonical_table_name FROM lp_content_kind WHERE kind_code = 'EVENT'").fetchone()

        self.assertEqual(row["canonical_table_name"], "lp_calendar_events")

    def test_report_summary_filters_can_include_root_kinds(self):
        report = content_catalog.content_catalog_report(
            "by-tab",
            filters={"mapping_status_code": "UNDECIDED", "include_roots": "1"},
            conn=self.conn,
        )

        codes = {item["kind_code"] for section in report["sections"] for item in section["items"]}
        self.assertIn("MONEY_ITEM", codes)

    def test_report_by_area_groups_items_under_tabs(self):
        report = content_catalog.content_catalog_report("by-area", conn=self.conn)

        house = next((section for section in report["sections"] if section["label"] == "House"), None)
        self.assertIsNotNone(house)
        tab_labels = {tab["label"] for tab in house["tabs"]}
        self.assertIn("GOALS", tab_labels)


if __name__ == "__main__":
    unittest.main()
