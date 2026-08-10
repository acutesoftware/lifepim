import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from apps.files.inventory_db import changed_files_for_scan, connect, create_or_update_source, last_successful_scan
from apps.files.scanner import FileInventoryScanner
from modules.apps import schema as apps_model


class TestAppFileList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "files.db")
        self.root = os.path.join(self.tmp.name, "source")
        os.makedirs(self.root)
        self.conn = connect(self.db_path)
        self.source_id = create_or_update_source(self.conn, "Test Source", self.root)
        self.scanner = FileInventoryScanner(conn=self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def _write(self, rel_path, text):
        full_path = os.path.join(self.root, *rel_path.split("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return full_path

    def _file_row(self, rel_path):
        normalized = rel_path.lower()
        return self.conn.execute(
            "SELECT * FROM lp_file WHERE source_id = ? AND normalized_relative_path = ?",
            (self.source_id, normalized),
        ).fetchone()

    def _change_count(self, scan_id, change_type):
        return self.conn.execute(
            "SELECT COUNT(1) AS cnt FROM lp_file_change WHERE scan_id = ? AND change_type = ?",
            (scan_id, change_type),
        ).fetchone()["cnt"]

    def test_empty_database_scan_creates_schema_and_records_new_file(self):
        self._write("small/one.txt", "one")

        result = self.scanner.scan(self.source_id, mode="FULL")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.files_new, 1)
        row = self._file_row("small/one.txt")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "one.txt")
        self.assertEqual(row["xtn"], "txt")
        self.assertEqual(row["size"], 3)
        self.assertEqual(row["is_deleted"], 0)
        self.assertEqual(self._change_count(result.scan_id, "NEW"), 1)

    def test_changed_file_updates_same_row_and_unchanged_does_not_emit_change(self):
        target = self._write("small/one.txt", "one")
        first = self.scanner.scan(self.source_id, mode="FULL")
        file_id = self._file_row("small/one.txt")["file_id"]

        second = self.scanner.scan(self.source_id, mode="FULL")
        self.assertEqual(second.files_unchanged, 1)
        self.assertEqual(self._change_count(second.scan_id, "CHANGED"), 0)

        time.sleep(0.02)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write("one changed")
        os.utime(target, None)
        third = self.scanner.scan(self.source_id, mode="FULL")
        row = self._file_row("small/one.txt")

        self.assertEqual(row["file_id"], file_id)
        self.assertEqual(row["size"], len("one changed"))
        self.assertEqual(third.files_changed, 1)
        self.assertEqual(self._change_count(third.scan_id, "CHANGED"), 1)
        self.assertEqual(first.status, "SUCCESS")

    def test_deleted_file_is_soft_deleted_and_reactivated_with_same_file_id(self):
        target = self._write("small/one.txt", "one")
        self.scanner.scan(self.source_id, mode="FULL")
        file_id = self._file_row("small/one.txt")["file_id"]

        os.remove(target)
        deleted = self.scanner.scan(self.source_id, mode="FULL")
        row = self._file_row("small/one.txt")
        self.assertEqual(deleted.files_deleted, 1)
        self.assertEqual(row["is_deleted"], 1)
        self.assertTrue(row["deleted_at"])

        self._write("small/one.txt", "one restored")
        reactivated = self.scanner.scan(self.source_id, mode="FULL")
        row = self._file_row("small/one.txt")
        self.assertEqual(row["file_id"], file_id)
        self.assertEqual(row["is_deleted"], 0)
        self.assertEqual(row["deleted_at"] or "", "")
        self.assertEqual(reactivated.files_reactivated, 1)
        self.assertEqual(self._change_count(reactivated.scan_id, "REACTIVATED"), 1)

    def test_scoped_deletion_only_marks_files_inside_scope(self):
        a_path = self._write("FolderA/a.txt", "a")
        b_path = self._write("FolderB/b.txt", "b")
        self.scanner.scan(self.source_id, mode="FULL")

        os.remove(a_path)
        os.remove(b_path)
        result = self.scanner.scan(self.source_id, scope="FolderA", mode="SCOPED")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(self._file_row("FolderA/a.txt")["is_deleted"], 1)
        self.assertEqual(self._file_row("FolderB/b.txt")["is_deleted"], 0)

    def test_missing_source_fails_without_marking_existing_files_deleted(self):
        self._write("small/one.txt", "one")
        first = self.scanner.scan(self.source_id, mode="FULL")
        shutil.rmtree(self.root)

        failed = self.scanner.scan(self.source_id, mode="FULL")
        row = self._file_row("small/one.txt")
        last_success = last_successful_scan(self.conn, self.source_id)

        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(row["is_deleted"], 0)
        self.assertEqual(last_success["scan_id"], first.scan_id)

    def test_incremental_mode_safely_falls_back_to_reconciliation_scan(self):
        keep_path = self._write("small/keep.txt", "keep")
        delete_path = self._write("small/delete.txt", "delete")
        self.scanner.scan(self.source_id, mode="FULL")

        self._write("small/new.txt", "new")
        with open(keep_path, "w", encoding="utf-8") as handle:
            handle.write("keep changed")
        os.remove(delete_path)
        result = self.scanner.scan(self.source_id, mode="INCREMENTAL")

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.scan_mode, "INCREMENTAL")
        self.assertEqual(result.provider, "full_scan")
        self.assertEqual(result.files_new, 1)
        self.assertEqual(result.files_changed, 1)
        self.assertEqual(result.files_deleted, 1)
        changed = changed_files_for_scan(self.conn, result.scan_id, extensions=["txt"])
        self.assertEqual({row["name"] for row in changed}, {"keep.txt", "new.txt"})

    def test_seeded_apps_tab_file_inventory_action_exists(self):
        app_conn = sqlite3.connect(":memory:")
        app_conn.row_factory = sqlite3.Row
        try:
            apps_model.ensure_apps_schema(app_conn)
            app_id = apps_model.ensure_file_inventory_app(app_conn, owner_user_id=1)
            app = apps_model.app_get(app_id, conn=app_conn, owner_user_id=1)
        finally:
            app_conn.close()

        self.assertEqual(app["title"], "LifePIM File Inventory Scanner")
        action = app["actions"][0]
        self.assertEqual(action["action_name"], "Run File Scan")
        self.assertIn("source_id", action["parameter_schema_json"])


if __name__ == "__main__":
    unittest.main()
