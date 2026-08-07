import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import config as cfg


class TestConfigOverrides(unittest.TestCase):
    def setUp(self):
        self.original_defaults = dict(cfg._CONFIG_DEFAULTS)
        self.original_cache = dict(cfg._CONFIG_OVERRIDE_CACHE)
        self.original_loaded = cfg._CONFIG_OVERRIDE_CACHE_LOADED
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        cfg._CONFIG_DEFAULTS.clear()
        cfg._CONFIG_DEFAULTS.update(self.original_defaults)
        cfg._CONFIG_OVERRIDE_CACHE.clear()
        cfg._CONFIG_OVERRIDE_CACHE.update(self.original_cache)
        cfg._CONFIG_OVERRIDE_CACHE_LOADED = self.original_loaded
        self.tmpdir.cleanup()

    def test_bootstrap_db_file_override_loads_active_database_config(self):
        root = Path(self.tmpdir.name)
        bootstrap_db = root / "bootstrap.db"
        active_db = root / "active" / "lifepim.db"
        active_db.parent.mkdir()
        cfg._CONFIG_DEFAULTS["DB_FILE"] = str(bootstrap_db)
        cfg._CONFIG_DEFAULTS["port_num"] = 9741
        cfg._CONFIG_OVERRIDE_CACHE.clear()
        cfg._CONFIG_OVERRIDE_CACHE_LOADED = False

        self._write_setting(bootstrap_db, "config.DB_FILE", str(active_db))
        self._write_setting(active_db, "config.port_num", "12345")

        cfg.refresh_config_overrides()

        self.assertEqual(cfg.DB_FILE, str(active_db))
        self.assertEqual(cfg.port_num, 12345)

    def test_saving_bootstrap_override_writes_startup_database(self):
        root = Path(self.tmpdir.name)
        bootstrap_db = root / "bootstrap.db"
        active_db = root / "active" / "lifepim.db"
        cfg._CONFIG_DEFAULTS["DB_FILE"] = str(bootstrap_db)

        cfg.save_bootstrap_config_override("DB_FILE", str(active_db))

        conn = sqlite3.connect(bootstrap_db)
        try:
            row = conn.execute("SELECT setting_value FROM sys_settings WHERE setting_key = 'config.DB_FILE'").fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], str(active_db))

    @staticmethod
    def _write_setting(db_path: Path, key: str, value: str) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sys_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'General',
                    label TEXT NOT NULL DEFAULT '',
                    updated_utc TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO sys_settings(setting_key, setting_value, category, label, updated_utc) "
                "VALUES (?, ?, 'Config', ?, '2026-08-07T00:00:00Z')",
                (key, value, key.replace("config.", "")),
            )
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
