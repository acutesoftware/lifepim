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


if __name__ == "__main__":
    unittest.main()
