#!/usr/bin/python3
# coding: utf-8
# test_importer_v1.py

import csv
import os
import sqlite3
import sys
import tempfile
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from lifepim.importer import run_import, csv_source, sqlite_source


class TestImporterV1(unittest.TestCase):
    def setUp(self):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        target_handle, self.target_db = tempfile.mkstemp(prefix="lifepim_target_", suffix=".db", dir=base_dir)
        source_handle, self.source_db = tempfile.mkstemp(prefix="lifepim_source_", suffix=".db", dir=base_dir)
        csv_handle, self.contacts_csv = tempfile.mkstemp(prefix="lifepim_contacts_", suffix=".csv", dir=base_dir)
        os.close(target_handle)
        os.close(source_handle)
        os.close(csv_handle)
        self._init_target_db()
        self._init_source_db()
        self._write_contacts_csv()

    def tearDown(self):
        for path in [self.target_db, self.source_db, self.contacts_csv]:
            try:
                os.remove(path)
            except OSError:
                pass

    def _init_target_db(self):
        conn = sqlite3.connect(self.target_db)
        conn.execute(
            "CREATE TABLE lp_contacts (id INTEGER PRIMARY KEY, display_name TEXT, normalized_name TEXT)"
        )
        conn.execute(
            "CREATE TABLE lp_files (id INTEGER PRIMARY KEY, path TEXT, file_type TEXT)"
        )
        conn.execute(
            "CREATE TABLE lp_media (id INTEGER PRIMARY KEY, file_name TEXT)"
        )
        conn.commit()
        conn.close()

    def _init_source_db(self):
        conn = sqlite3.connect(self.source_db)
        conn.execute(
            "CREATE TABLE master_filelist (file_id TEXT, path TEXT, size INTEGER, mtime_utc TEXT, sha256 TEXT, type TEXT)"
        )
        conn.execute(
            "CREATE TABLE img_results (sha256 TEXT, labels_json TEXT, faces TEXT, dominant_colors TEXT)"
        )
        conn.executemany(
            "INSERT INTO master_filelist (file_id, path, size, mtime_utc, sha256, type) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("1", r"C:\\files\\a.txt", 123, "2025-01-01T00:00:00Z", "AAA", "doc"),
                ("2", r"C:\\files\\b.txt", 456, "2025-01-02T00:00:00Z", "BBB", "doc"),
            ],
        )
        conn.executemany(
            "INSERT INTO img_results (sha256, labels_json, faces, dominant_colors) VALUES (?, ?, ?, ?)",
            [
                ("AAA", "{\"labels\": [\"sample\"]}", "[]", "[]"),
            ],
        )
        conn.commit()
        conn.close()

    def _write_contacts_csv(self):
        with open(self.contacts_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ContactID", "Name", "Email", "Phone"])
            writer.writerow(["101", "Ada Lovelace", "ada@example.com", "+1-555-0101"])
            writer.writerow(["102", "Grace Hopper", "grace@example.com", "+1-555-0102"])

    def test_importer_flow(self):
        with run_import("test_run", db_path=self.target_db, progress_every=0) as run:
            run.load(
                target="contacts",
                source=csv_source(self.contacts_csv),
                mapping={
                    "source_uid": "ContactID",
                    "display_name": "Name",
                    "email": "Email",
                    "phone": "Phone",
                },
                key="source_uid",
                mode="snapshot",
                source_system="contacts_csv",
            )
            run.load(
                target="files",
                source=sqlite_source(self.source_db, sql="SELECT file_id, path, size, mtime_utc, sha256, type FROM master_filelist"),
                mapping={
                    "source_uid": "file_id",
                    "path": "path",
                    "size": "size",
                    "mtime_utc": "mtime_utc",
                    "sha256": "sha256",
                    "file_type": "type",
                },
                key="sha256",
                mode="authoritative",
                tombstone=True,
                source_system="filelistdb",
            )
            run.load(
                target="media",
                source=sqlite_source(self.source_db, sql="SELECT sha256, labels_json, faces, dominant_colors FROM img_results"),
                mapping={
                    "sha256": "sha256",
                    "labels_json": "labels_json",
                    "faces": "faces",
                    "dominant_colors": "dominant_colors",
                },
                key="sha256",
                mode="merge",
                source_system="imgclsdb",
            )

        conn = sqlite3.connect(self.target_db)
        conn.row_factory = sqlite3.Row
        status = conn.execute(
            "SELECT status FROM lp_import_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(status["status"], "success")

        contact = conn.execute(
            "SELECT entity_id, source_system, source_uid FROM lp_contacts WHERE source_uid = '101'"
        ).fetchone()
        self.assertTrue(contact["entity_id"].startswith("contact:src:contacts_csv"))

        files = conn.execute(
            "SELECT entity_id, is_deleted FROM lp_files ORDER BY entity_id"
        ).fetchall()
        self.assertEqual(len(files), 2)
        self.assertTrue(all(row["is_deleted"] == 0 for row in files))

        media = conn.execute(
            "SELECT entity_id, labels_json FROM lp_media WHERE sha256 = 'aaa'"
        ).fetchone()
        self.assertTrue(media["entity_id"].startswith("media:sha256:aaa"))
        self.assertIn("labels", media["labels_json"])
        conn.close()

        conn = sqlite3.connect(self.source_db)
        conn.execute("DELETE FROM master_filelist WHERE file_id = '2'")
        conn.commit()
        conn.close()

        with run_import("test_run_2", db_path=self.target_db, progress_every=0) as run:
            run.load(
                target="files",
                source=sqlite_source(self.source_db, sql="SELECT file_id, path, size, mtime_utc, sha256, type FROM master_filelist"),
                mapping={
                    "source_uid": "file_id",
                    "path": "path",
                    "size": "size",
                    "mtime_utc": "mtime_utc",
                    "sha256": "sha256",
                    "file_type": "type",
                },
                key="sha256",
                mode="authoritative",
                tombstone=True,
                source_system="filelistdb",
            )

        conn = sqlite3.connect(self.target_db)
        conn.row_factory = sqlite3.Row
        deleted = conn.execute(
            "SELECT COUNT(1) AS cnt FROM lp_files WHERE is_deleted = 1"
        ).fetchone()
        self.assertEqual(deleted["cnt"], 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
