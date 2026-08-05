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
            self.assertEqual(defaults["sample_lines"], 20)
            self.assertEqual(defaults["notes_per_page"], 50)

            settings.save_note_display_settings(
                {
                    "card_width_chars": "75",
                    "title_font_size": "22",
                    "preview_chars": "900",
                    "sample_lines": "30",
                    "notes_per_page": "80",
                },
                conn,
            )
            saved = settings.get_note_display_settings(conn)
            self.assertEqual(saved["card_width_chars"], 75)
            self.assertEqual(saved["title_font_size"], 22)
            self.assertEqual(saved["preview_chars"], 900)
            self.assertEqual(saved["sample_lines"], 30)
            self.assertEqual(saved["notes_per_page"], 80)

            settings.save_note_display_settings(
                {
                    "card_width_chars": "500",
                    "title_font_size": "2",
                    "preview_chars": "bad",
                    "sample_lines": "0",
                    "notes_per_page": "0",
                },
                conn,
            )
            clamped = settings.get_note_display_settings(conn)
            self.assertEqual(clamped["card_width_chars"], 120)
            self.assertEqual(clamped["title_font_size"], 12)
            self.assertEqual(clamped["preview_chars"], 300)
            self.assertEqual(clamped["sample_lines"], 1)
            self.assertEqual(clamped["notes_per_page"], 5)
        finally:
            conn.close()

    def test_logger_raw_root_defaults_under_user_notes_root(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            notes_root = os.path.join("D:\\DATA_LLM", "users", "alice", "notes")
            conn.execute(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    file_root_path TEXT,
                    notes_root_path TEXT,
                    areas_root_path TEXT,
                    lists_root_path TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO users (user_id, username, notes_root_path) VALUES (?, ?, ?)",
                (7, "alice", notes_root),
            )
            conn.commit()

            logger_settings = settings.get_logger_settings(conn, user_id=7, username="alice")

            self.assertEqual(
                logger_settings["raw_data_root"],
                os.path.join(notes_root, "logged_data", "raw"),
            )
        finally:
            conn.close()

    def test_logger_raw_root_preserves_custom_saved_path(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            settings.save_logger_settings(
                {
                    "enabled": True,
                    "raw_data_root": r"D:\custom\logger\raw",
                    "sync_token": "secret",
                    "max_upload_mb": 10,
                    "keep_sync_logs": True,
                },
                conn,
            )

            logger_settings = settings.get_logger_settings(conn, user_id=7, username="alice")

            self.assertEqual(logger_settings["raw_data_root"], r"D:\custom\logger\raw")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
