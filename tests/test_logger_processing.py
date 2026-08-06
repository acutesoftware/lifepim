import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from logger.config import LoggerConfig
from logger.config import load_logger_config
from logger.database import connect
from logger.service import LoggerService


class TestLoggerProcessing(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.mobile_root = self.root / "mobile"
        self.aggie_root = self.root / "aggie"
        self.db_path = self.root / "lifepim_logger.db"
        self.mobile_root.mkdir()
        self.aggie_root.mkdir()
        self.config = LoggerConfig(
            database_path=self.db_path,
            mobile_source_path=self.mobile_root,
            aggie_source_path=self.aggie_root,
            session_gap_seconds=10,
            minimum_session_seconds=1,
        )
        self.service = LoggerService(self.config)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_refresh_imports_sources_and_builds_sessions(self):
        self._write_mobile_usage(samples=3)
        self._write_inventory()
        self._write_aggie_usage()

        result = self.service.refresh()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.files_imported, 3)
        self.assertEqual(result.files_failed, 0)
        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 3)
            self.assertEqual(self._count(conn, "desktop_window_sample"), 3)
            self.assertGreaterEqual(self._count(conn, "application_catalog"), 2)
            self.assertEqual(self._count(conn, "activity_session"), 2)

    def test_refresh_is_idempotent_for_unchanged_files(self):
        self._write_mobile_usage(samples=3)

        first = self.service.refresh()
        second = self.service.refresh()

        self.assertEqual(first.files_imported, 1)
        self.assertEqual(second.files_imported, 0)
        self.assertEqual(second.files_skipped, 1)
        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 3)
            self.assertEqual(self._count(conn, "activity_session"), 1)

    def test_changed_file_reimports_without_duplicate_samples(self):
        self._write_mobile_usage(samples=3)
        self.service.refresh()

        self._write_mobile_usage(samples=4)
        result = self.service.refresh()

        self.assertEqual(result.files_imported, 1)
        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 4)
            session = conn.execute("SELECT * FROM activity_session").fetchone()
            self.assertEqual(session["source_record_count"], 4)

    def test_malformed_file_is_failed_without_blocking_good_files(self):
        self._write_mobile_usage(samples=2)
        bad_dir = self.mobile_root / "phone-1" / "app_usage"
        bad_dir.mkdir(parents=True, exist_ok=True)
        (bad_dir / "bad_usage.jsonl").write_text('{"package_name":"bad.app"}\n', encoding="utf-8")

        result = self.service.refresh()

        self.assertEqual(result.files_imported, 1)
        self.assertEqual(result.files_failed, 1)
        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 2)
            failed = conn.execute("SELECT * FROM ingest_file WHERE import_status = 'failed'").fetchone()
            self.assertIn("no timestamp", failed["error_message"])

    def test_rebuild_sessions_is_deterministic(self):
        self._write_mobile_usage(samples=3)
        self.service.refresh()

        first_hashes = self._session_hashes()
        result = self.service.rebuild_sessions()
        second_hashes = self._session_hashes()

        self.assertEqual(result.sessions_created, 1)
        self.assertEqual(first_hashes, second_hashes)

    def test_rebuild_database_recreates_derived_database_from_raw_files(self):
        self._write_mobile_usage(samples=3)
        self.service.refresh()
        with closing(connect(self.db_path)) as conn:
            conn.execute("DELETE FROM mobile_app_usage_sample")
            conn.commit()
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 0)

        result = self.service.rebuild_database()

        self.assertEqual(result.status, "completed")
        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "mobile_app_usage_sample"), 3)
            self.assertEqual(self._count(conn, "activity_session"), 1)

    def test_millisecond_timestamps_are_stored_as_canonical_utc(self):
        folder = self.mobile_root / "phone-1" / "app_usage"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "usage.jsonl").write_text(
            '{"timestamp":1785894137000,"device_id":"phone-1","package_name":"example.app"}\n',
            encoding="utf-8",
        )

        self.service.refresh()

        with closing(connect(self.db_path)) as conn:
            row = conn.execute("SELECT observed_at_utc FROM mobile_app_usage_sample").fetchone()
            self.assertRegex(row["observed_at_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_mobile_logger_field_names_and_snapshot_apps_are_imported(self):
        folder = self.mobile_root / "phone-1" / "phone_usage"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "2026-08-06.jsonl").write_text(
            "\n".join(
                [
                    '{"type":"phone_usage_event","capturedAt":"2026-08-06T00:00:51.829Z","event":"screen_off"}',
                    '{"type":"app_usage_event","capturedAt":"2026-08-06T00:29:10.479Z","eventTimeMillis":1785976141269,"eventType":"activity_resumed","packageName":"com.sec.android.app.launcher","appName":"One UI Home","className":"Launcher"}',
                    '{"type":"phone_usage_snapshot","capturedAt":"2026-08-06T00:29:10.494Z","apps":[{"packageName":"com.example.app","appName":"Example","lastTimeUsedMillis":1785976142269}]}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.service.refresh()

        self.assertEqual(result.files_failed, 0)
        with closing(connect(self.db_path)) as conn:
            rows = conn.execute("SELECT package_name, application_name, event_type FROM mobile_app_usage_sample ORDER BY source_record_index").fetchall()
            self.assertEqual(len(rows), 3)
            self.assertIsNone(rows[0]["package_name"])
            self.assertEqual(rows[0]["event_type"], "screen_off")
            self.assertEqual(rows[1]["package_name"], "com.sec.android.app.launcher")
            self.assertEqual(rows[1]["application_name"], "One UI Home")
            self.assertEqual(rows[2]["package_name"], "com.example.app")

    def test_mobile_inventory_skips_status_records(self):
        folder = self.mobile_root / "phone-1" / "app_catalog"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "app_catalog.jsonl").write_text(
            '{"type":"app_catalog_started","capturedAt":"2026-08-05T04:21:00.183Z"}\n'
            '{"type":"installed_app","capturedAt":"2026-08-05T04:21:00.183Z","packageName":"ai.perplexity.app.android","appName":"Perplexity"}\n'
            '{"type":"app_catalog_finished","capturedAt":"2026-08-05T04:21:01.183Z"}\n',
            encoding="utf-8",
        )

        result = self.service.refresh()

        self.assertEqual(result.files_failed, 0)
        with closing(connect(self.db_path)) as conn:
            rows = conn.execute("SELECT package_name, application_name FROM application_catalog").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["package_name"], "ai.perplexity.app.android")

    def test_default_logger_database_path_uses_open_main_database_location(self):
        main_db = self.root / "actual_main" / "lifepim.db"
        main_db.parent.mkdir()
        conn = sqlite3.connect(main_db)
        conn.row_factory = sqlite3.Row
        try:
            config = load_logger_config(conn)
        finally:
            conn.close()

        self.assertEqual(config.database_path, main_db.parent / "lifepim_logger.db")

    def test_mobile_application_change_and_large_gap_create_new_sessions(self):
        folder = self.mobile_root / "phone-1" / "app_usage"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "usage.jsonl").write_text(
            "\n".join(
                [
                    '{"observed_at_utc":"2026-08-05T00:00:00Z","device_id":"phone-1","package_name":"app.one"}',
                    '{"observed_at_utc":"2026-08-05T00:00:01Z","device_id":"phone-1","package_name":"app.one"}',
                    '{"observed_at_utc":"2026-08-05T00:00:02Z","device_id":"phone-1","package_name":"app.two"}',
                    '{"observed_at_utc":"2026-08-05T00:00:03Z","device_id":"phone-1","package_name":"app.two"}',
                    '{"observed_at_utc":"2026-08-05T00:00:30Z","device_id":"phone-1","package_name":"app.two"}',
                    '{"observed_at_utc":"2026-08-05T00:00:31Z","device_id":"phone-1","package_name":"app.two"}',
                    '{"observed_at_utc":"2026-08-05T00:00:32Z","device_id":"phone-1","package_name":"app.two","screen_state":"off"}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        self.service.refresh()

        with closing(connect(self.db_path)) as conn:
            sessions = conn.execute("SELECT * FROM activity_session ORDER BY start_at_utc").fetchall()
            self.assertEqual(len(sessions), 3)
            self.assertEqual([row["application_identifier"] for row in sessions], ["app.one", "app.two", "app.two"])

    def test_sessions_below_minimum_duration_are_discarded(self):
        self.config = LoggerConfig(
            database_path=self.db_path,
            mobile_source_path=self.mobile_root,
            aggie_source_path=self.aggie_root,
            session_gap_seconds=10,
            minimum_session_seconds=3,
        )
        self.service = LoggerService(self.config)
        self._write_mobile_usage(samples=2)

        self.service.refresh()

        with closing(connect(self.db_path)) as conn:
            self.assertEqual(self._count(conn, "activity_session"), 0)

    def test_desktop_idle_terminates_sessions(self):
        folder = self.aggie_root / "desktop-1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "window_usage.csv").write_text(
            "observed_at_utc,device_id,process_name,application_name,window_title,is_idle\n"
            "2026-08-05T01:00:00Z,desktop-1,Code.exe,Visual Studio Code,One,0\n"
            "2026-08-05T01:00:01Z,desktop-1,Code.exe,Visual Studio Code,Two,0\n"
            "2026-08-05T01:00:02Z,desktop-1,Code.exe,Visual Studio Code,,1\n"
            "2026-08-05T01:00:03Z,desktop-1,Code.exe,Visual Studio Code,Three,0\n"
            "2026-08-05T01:00:04Z,desktop-1,Code.exe,Visual Studio Code,Four,0\n",
            encoding="utf-8",
        )

        self.service.refresh()

        with closing(connect(self.db_path)) as conn:
            sessions = conn.execute("SELECT * FROM activity_session ORDER BY start_at_utc").fetchall()
            self.assertEqual(len(sessions), 2)
            self.assertEqual(sessions[0]["application_identifier"], sessions[1]["application_identifier"])

    def _write_mobile_usage(self, samples):
        folder = self.mobile_root / "phone-1" / "app_usage"
        folder.mkdir(parents=True, exist_ok=True)
        lines = []
        for second in range(samples):
            lines.append(
                '{"observed_at_utc":"2026-08-05T00:00:%02dZ","device_id":"phone-1",'
                '"package_name":"org.telegram.messenger","application_name":"Telegram","screen_state":"on"}'
                % second
            )
        (folder / "usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_inventory(self):
        folder = self.mobile_root / "phone-1" / "app_catalog"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "inventory.json").write_text(
            '{"apps":[{"package_name":"org.telegram.messenger","application_name":"Telegram"}]}',
            encoding="utf-8",
        )

    def _write_aggie_usage(self):
        folder = self.aggie_root / "desktop-1"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "window_usage.csv").write_text(
            "observed_at_utc,device_id,process_name,application_name,window_title,is_idle\n"
            "2026-08-05T01:00:00Z,desktop-1,Code.exe,Visual Studio Code,LifePIM,0\n"
            "2026-08-05T01:00:01Z,desktop-1,Code.exe,Visual Studio Code,LifePIM tests,0\n"
            "2026-08-05T01:00:02Z,desktop-1,Code.exe,Visual Studio Code,LifePIM tests,0\n",
            encoding="utf-8",
        )

    def _session_hashes(self):
        with closing(connect(self.db_path)) as conn:
            return [
                row["session_hash"]
                for row in conn.execute("SELECT session_hash FROM activity_session ORDER BY session_hash").fetchall()
            ]

    @staticmethod
    def _count(conn: sqlite3.Connection, table_name: str) -> int:
        return int(conn.execute(f"SELECT COUNT(1) AS count FROM {table_name}").fetchone()["count"])


if __name__ == "__main__":
    unittest.main()
