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

from data.processes import ProcessService
from common import settings
from logger.database import connect


class TestDataProcesses(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.source = self.root / "incoming"
        self.source.mkdir()
        self.logger_db = self.root / "logger.sqlite"
        self.main_conn = sqlite3.connect(self.root / "main.sqlite")
        self.main_conn.row_factory = sqlite3.Row
        self.service = ProcessService(self.main_conn)
        self.process = self.service.get_default_logger_process()
        self.service.update_process(
            self.process["process_id"],
            {
                "process_name": self.process["process_name"],
                "description": self.process.get("description") or "",
                "is_enabled": True,
                "configuration": {
                    "source_folder": str(self.source),
                    "database_path": str(self.logger_db),
                    "file_pattern": "*.json",
                    "include_subfolders": True,
                    "duplicate_detection": "metadata_and_hash",
                    "allow_unknown_record_types": True,
                },
            },
        )
        self.process = self.service.get_default_logger_process()

    def tearDown(self):
        self.main_conn.close()
        self.tmpdir.cleanup()

    def test_registry_resolves_logger_handler_and_seed_process(self):
        self.assertEqual(self.process["process_type"], "logger_json_import")
        self.assertTrue(self.process["handler_available"])

    def test_preview_does_not_create_logger_database(self):
        self._write_usage_file()

        result = self.service.preview_process(self.process["process_id"])

        self.assertEqual(result.status, "success")
        self.assertEqual(result.files_found, 1)
        self.assertFalse(self.logger_db.exists())
        runs = self.service.list_runs(process_id=self.process["process_id"])
        self.assertEqual(runs[0]["run_mode"], "preview")

    def test_incremental_import_writes_raw_records_and_skips_duplicate_rerun(self):
        self._write_usage_file()

        first = self.service.run_process(self.process["process_id"])
        second = self.service.run_process(self.process["process_id"])

        self.assertEqual(first.status, "success")
        self.assertEqual(first.files_processed, 1)
        self.assertEqual(second.files_skipped, 1)
        with closing(connect(self.logger_db)) as conn:
            self.assertEqual(self._count(conn, "raw_logger_record"), 2)
            self.assertEqual(self._count(conn, "raw_mobile_app_usage"), 2)

    def test_incremental_import_matches_jsonl_when_pattern_contains_multiple_extensions(self):
        self.service.update_process(
            self.process["process_id"],
            {
                "process_name": self.process["process_name"],
                "description": self.process.get("description") or "",
                "is_enabled": True,
                "configuration": {"file_pattern": "*.json;*.jsonl"},
            },
        )
        (self.source / "app_usage.jsonl").write_text(
            '{"type":"app_usage_event","capturedAt":"2026-08-06T00:00:00Z","packageName":"example.one"}\n',
            encoding="utf-8",
        )

        result = self.service.run_process(self.process["process_id"])

        self.assertEqual(result.status, "success")
        self.assertEqual(result.files_processed, 1)
        with closing(connect(self.logger_db)) as conn:
            self.assertEqual(self._count(conn, "raw_mobile_app_usage"), 1)

    def test_default_logger_process_uses_logger_raw_data_root_when_source_is_blank(self):
        raw_root = self.root / "synced" / "raw"
        settings.save_logger_settings(
            {
                "enabled": True,
                "raw_data_root": str(raw_root),
                "sync_token": None,
                "max_upload_mb": 50,
                "keep_sync_logs": True,
            },
            self.main_conn,
        )
        self.service.update_process(
            self.process["process_id"],
            {
                "process_name": self.process["process_name"],
                "description": self.process.get("description") or "",
                "is_enabled": True,
                "configuration": {"source_folder": "", "file_pattern": "*.json"},
            },
        )

        process = self.service.get_default_logger_process()

        self.assertEqual(process["configuration"]["source_folder"], str(raw_root))
        self.assertEqual(process["configuration"]["file_pattern"], "*.json;*.jsonl")

    def test_unknown_record_is_retained_with_warning(self):
        (self.source / "unknown.json").write_text('{"type":"something_new","capturedAt":"2026-08-06T01:00:00Z"}', encoding="utf-8")

        result = self.service.run_process(self.process["process_id"])

        self.assertEqual(result.status, "warning")
        with closing(connect(self.logger_db)) as conn:
            self.assertEqual(self._count(conn, "raw_unknown_record"), 1)

    def test_rebuild_replaces_logger_database_and_keeps_run_history(self):
        self._write_usage_file()
        self.service.run_process(self.process["process_id"])
        with closing(connect(self.logger_db)) as conn:
            conn.execute("DELETE FROM raw_mobile_app_usage")
            conn.execute("DELETE FROM raw_logger_record")
            conn.commit()
            self.assertEqual(self._count(conn, "raw_logger_record"), 0)

        result = self.service.rebuild_process(self.process["process_id"])

        self.assertEqual(result.status, "success")
        with closing(connect(self.logger_db)) as conn:
            self.assertEqual(self._count(conn, "raw_logger_record"), 2)
        modes = [run["run_mode"] for run in self.service.list_runs(process_id=self.process["process_id"])]
        self.assertIn("rebuild", modes)
        self.assertIn("incremental", modes)

    def _write_usage_file(self):
        (self.source / "app_usage.json").write_text(
            "["
            '{"type":"app_usage_event","capturedAt":"2026-08-06T00:00:00Z","packageName":"example.one","appName":"One"},'
            '{"type":"app_usage_event","capturedAt":"2026-08-06T00:00:01Z","packageName":"example.two","appName":"Two"}'
            "]",
            encoding="utf-8",
        )

    @staticmethod
    def _count(conn, table_name):
        return int(conn.execute(f"SELECT COUNT(1) AS count FROM {table_name}").fetchone()["count"])


if __name__ == "__main__":
    unittest.main()
