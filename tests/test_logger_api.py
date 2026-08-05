import io
import hashlib
import os
import sqlite3
import sys
import tempfile
import unittest

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import settings
from modules.logger_api.routes import logger_api_bp, logger_raw_root


class TestLoggerApi(unittest.TestCase):
    def setUp(self):
        settings._SCHEMA_READY_CONN_IDS.clear()
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        data.conn = self.conn
        self.tmpdir = tempfile.TemporaryDirectory()
        settings.save_logger_settings(
            {
                "enabled": True,
                "raw_data_root": self.tmpdir.name,
                "sync_token": "logger-secret",
                "max_upload_mb": 1,
                "keep_sync_logs": True,
            },
            self.conn,
        )
        self.app = Flask(__name__)
        self.app.register_blueprint(logger_api_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()
        self.tmpdir.cleanup()
        settings._SCHEMA_READY_CONN_IDS.clear()

    def headers(self, token="logger-secret"):
        return {
            "Authorization": f"Bearer {token}",
            "X-LifePIM-Logger-Device-ID": "7167e119-716a-41dd-93d3-bb1c1b44797a",
            "X-LifePIM-Logger-Device-Name": "Duncan A22",
        }

    def upload(self, relative_path="movement/2026-08-05.jsonl", content=b'{"ok":true}\n'):
        return self.client.post(
            "/api/logger/v1/upload",
            headers=self.headers(),
            data={
                "device_id": "7167e119-716a-41dd-93d3-bb1c1b44797a",
                "device_name": "Duncan A22",
                "relative_path": relative_path,
                "log_type": relative_path.split("/", 1)[0],
                "file_date": "2026-08-05",
                "file_size": str(len(content)),
                "last_modified": "1785894137000",
                "sync_run_uuid": "sync-run-1",
                "file": (io.BytesIO(content), os.path.basename(relative_path)),
            },
            content_type="multipart/form-data",
        )

    def test_status_requires_bearer_token(self):
        self.assertEqual(self.client.get("/api/logger/v1/status").status_code, 401)
        self.assertEqual(self.client.get("/api/logger/v1/status", headers=self.headers("bad")).status_code, 401)

        resp = self.client.get("/api/logger/v1/status", headers=self.headers())

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "lifepim-logger-sync")

    def test_status_accepts_pocket_device_token_from_password_login_flow(self):
        self.conn.execute(
            """
            CREATE TABLE pocket_devices (
                device_id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                device_name TEXT,
                platform TEXT,
                username TEXT,
                user_id INTEGER,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT,
                last_ip TEXT,
                user_agent TEXT
            )
            """
        )
        self.conn.execute(
            """
            INSERT INTO pocket_devices
            (device_id, token_hash, device_name, platform, username, user_id, created_at, last_seen_at)
            VALUES (?, ?, 'Duncan A22', 'android-logger', 'duncan', 1, '2026-08-05T00:00:00Z', '2026-08-05T00:00:00Z')
            """,
            (
                "pocket-device-id",
                hashlib.sha256(b"pocket-token").hexdigest(),
            ),
        )
        self.conn.commit()

        resp = self.client.get(
            "/api/logger/v1/status",
            headers={
                "Authorization": "Bearer pocket-token",
                "X-LifePIM-Logger-Device-ID": "pocket-device-id",
                "X-LifePIM-Logger-Device-Name": "Duncan A22",
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ok")

    def test_upload_stores_file_under_safe_device_folder_and_records_metadata(self):
        resp = self.upload()

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["stored"])
        stored_path = os.path.join(logger_raw_root(), "duncan-a22", "movement", "2026-08-05.jsonl")
        self.assertTrue(os.path.exists(stored_path))
        with open(stored_path, "rb") as handle:
            self.assertEqual(handle.read(), b'{"ok":true}\n')

        device = self.conn.execute("SELECT * FROM lp_logger_device").fetchone()
        self.assertEqual(device["device_folder"], "duncan-a22")
        file_row = self.conn.execute("SELECT * FROM lp_logger_sync_file").fetchone()
        self.assertEqual(file_row["relative_path"], "movement/2026-08-05.jsonl")
        self.assertEqual(file_row["status"], "stored")

    def test_repeated_upload_replaces_existing_file(self):
        first = self.upload(content=b"first\n")
        second = self.upload(content=b"second\n")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        stored_path = os.path.join(logger_raw_root(), "duncan-a22", "movement", "2026-08-05.jsonl")
        with open(stored_path, "rb") as handle:
            self.assertEqual(handle.read(), b"second\n")
        statuses = [
            row["status"]
            for row in self.conn.execute("SELECT status FROM lp_logger_sync_file ORDER BY logger_sync_file_id").fetchall()
        ]
        self.assertEqual(statuses, ["stored", "replaced"])

    def test_upload_rejects_traversal_and_bad_categories(self):
        traversal = self.upload("../2026-08-05.jsonl")
        bad_category = self.upload("other/2026-08-05.jsonl")
        bad_extension = self.upload("movement/2026-08-05.txt")

        self.assertEqual(traversal.status_code, 400)
        self.assertEqual(bad_category.status_code, 400)
        self.assertEqual(bad_extension.status_code, 400)
        self.assertEqual(os.listdir(self.tmpdir.name), [])


if __name__ == "__main__":
    unittest.main()
