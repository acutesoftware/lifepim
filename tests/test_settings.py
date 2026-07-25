import os
import sqlite3
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import settings


class TestSettingsSchema(unittest.TestCase):
    def setUp(self):
        settings._SCHEMA_READY_CONN_IDS.clear()

    def tearDown(self):
        settings._SCHEMA_READY_CONN_IDS.clear()

    def test_old_settings_table_gets_missing_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE sys_settings ("
                "setting_key TEXT PRIMARY KEY, "
                "setting_value TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "INSERT INTO sys_settings (setting_key, setting_value) VALUES (?, ?)",
                ("general.freeze_headers", "1"),
            )
            conn.commit()

            self.assertTrue(settings.get_general_settings(conn)["freeze_headers"])
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(sys_settings)").fetchall()}
            self.assertIn("category", cols)
            self.assertIn("label", cols)
            self.assertIn("updated_utc", cols)
        finally:
            conn.close()

    def test_get_setting_supports_tuple_rows(self):
        conn = sqlite3.connect(":memory:")
        try:
            self.assertEqual(settings.get_setting("general.freeze_headers", "0", conn), "0")
            settings.set_setting("general.freeze_headers", "1", conn=conn)
            self.assertEqual(settings.get_setting("general.freeze_headers", "0", conn), "1")
        finally:
            conn.close()

    def test_calendar_thumbnail_settings_are_clamped_and_preserved(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            settings.save_calendar_view_settings(
                {
                    "events": True,
                    "files": True,
                    "usage": False,
                    "thumbnail_size": "large",
                    "thumbnail_limit": "30",
                },
                conn,
            )
            saved = settings.get_calendar_view_settings(conn)
            self.assertEqual(saved["thumbnail_size"], "large")
            self.assertEqual(saved["thumbnail_limit"], 20)

            settings.save_calendar_view_settings({"events": False, "files": True, "usage": False}, conn)
            saved = settings.get_calendar_view_settings(conn)
            self.assertEqual(saved["thumbnail_size"], "large")
            self.assertEqual(saved["thumbnail_limit"], 20)
        finally:
            conn.close()

    def test_note_display_settings_are_saved_and_clamped(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            defaults = settings.get_note_display_settings(conn)
            self.assertEqual(defaults["card_width_chars"], 50)
            self.assertEqual(defaults["title_font_size"], 18)
            self.assertEqual(defaults["preview_chars"], 300)
            self.assertEqual(defaults["notes_per_page"], 50)

            settings.save_note_display_settings(
                {
                    "card_width_chars": "75",
                    "title_font_size": "22",
                    "preview_chars": "900",
                    "notes_per_page": "80",
                },
                conn,
            )
            saved = settings.get_note_display_settings(conn)
            self.assertEqual(saved["card_width_chars"], 75)
            self.assertEqual(saved["title_font_size"], 22)
            self.assertEqual(saved["preview_chars"], 900)
            self.assertEqual(saved["notes_per_page"], 80)

            settings.save_note_display_settings(
                {
                    "card_width_chars": "500",
                    "title_font_size": "2",
                    "preview_chars": "bad",
                    "notes_per_page": "0",
                },
                conn,
            )
            clamped = settings.get_note_display_settings(conn)
            self.assertEqual(clamped["card_width_chars"], 120)
            self.assertEqual(clamped["title_font_size"], 12)
            self.assertEqual(clamped["preview_chars"], 300)
            self.assertEqual(clamped["notes_per_page"], 5)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
