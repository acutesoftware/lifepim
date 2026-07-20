import os
import base64
import hashlib
import sqlite3
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common import utils as common_utils
from core import security
from modules.pocket_api.routes import (
    create_pocket_pairing_code,
    get_user_pocket_settings,
    list_pocket_devices,
    pocket_api_bp,
    revoke_pocket_device,
    set_user_default_note_folder,
)


class TestPocketApi(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        self.conn.execute(
            """
            CREATE TABLE lp_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                path TEXT,
                folder_id INTEGER,
                size TEXT,
                date_modified TEXT,
                project TEXT,
                owner_user_id INTEGER,
                visibility TEXT NOT NULL DEFAULT 'private',
                is_public INTEGER NOT NULL DEFAULT 0,
                user_name TEXT,
                rec_extract_date TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self.conn.execute(
            "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
            "VALUES (3, 'duncanmobile', 'Duncan Mobile', 'hash', 'user', 1)"
        )
        self.conn.execute(
            "INSERT INTO users(user_id, username, display_name, password_hash, role, is_active) "
            "VALUES (4, 'inactive', 'Inactive User', 'hash', 'user', 0)"
        )
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.register_blueprint(pocket_api_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            self.tmpdir.cleanup()
        finally:
            data.conn = self._old_conn
            self.conn.close()

    def _add_note(self, file_name="Shopping.md", content="# Shopping\n\n- [ ] Milk\n", owner_user_id=3, folder_path=None, project="pers"):
        folder_path = folder_path or self.tmpdir.name
        os.makedirs(folder_path, exist_ok=True)
        full_path = os.path.join(folder_path, file_name)
        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        stat = os.stat(full_path)
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": file_name,
            "path": folder_path,
            "folder_id": "",
            "size": str(stat.st_size),
            "date_modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "project": project,
            "owner_user_id": owner_user_id,
            "visibility": "private",
            "is_public": 0,
        }
        cols = list(tbl["col_list"]) + ["owner_user_id", "visibility", "is_public"]
        values = [values_map.get(col, "") for col in cols]
        return data.add_record(self.conn, tbl["name"], cols, values)

    def _register_headers(self):
        code = create_pocket_pairing_code(3)["pairing_code"]
        resp = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={
                "device_id": "android-test",
                "device_name": "Android Test",
                "platform": "android",
                "username": "duncanmobile",
                "pairing_code": code,
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        return {
            "Authorization": f"Bearer {payload['device_token']}",
            "X-LifePIM-Device-ID": payload["device_id"],
        }

    def test_username_only_registration_is_rejected(self):
        resp = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test", "username": "duncanmobile"},
        )

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "authentication_failed")
        self.assertIsNone(self.conn.execute("SELECT token_hash FROM pocket_devices").fetchone())

    def test_invalid_pairing_code_is_rejected(self):
        resp = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test", "username": "duncanmobile", "pairing_code": "WRONG-CODE"},
        )

        self.assertEqual(resp.status_code, 401)

    def test_expired_pairing_code_is_rejected(self):
        code = create_pocket_pairing_code(3)["pairing_code"]
        self.conn.execute("UPDATE pocket_pairing_codes SET expires_at = '2000-01-01T00:00:00Z'")
        self.conn.commit()

        resp = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test", "username": "duncanmobile", "pairing_code": code},
        )

        self.assertEqual(resp.status_code, 401)

    def test_reused_pairing_code_is_rejected(self):
        code = create_pocket_pairing_code(3)["pairing_code"]
        first = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test", "username": "duncanmobile", "pairing_code": code},
        )
        second = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test-2", "username": "duncanmobile", "pairing_code": code},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)

    def test_successful_pairing_creates_device_bound_to_correct_user(self):
        headers = self._register_headers()

        row = self.conn.execute("SELECT device_id, username, user_id, token_hash FROM pocket_devices").fetchone()
        self.assertEqual(row["device_id"], "android-test")
        self.assertEqual(row["username"], "duncanmobile")
        self.assertEqual(row["user_id"], 3)
        self.assertNotIn(headers["Authorization"].replace("Bearer ", ""), row["token_hash"])

    def test_password_login_creates_device_bound_to_correct_user(self):
        self.conn.execute("UPDATE users SET password_hash=? WHERE username='duncanmobile'", (security.hash_password("secret"),))
        self.conn.commit()

        resp = self.client.post(
            "/api/pocket/v1/auth/login",
            json={
                "device_id": "android-password-test",
                "device_name": "Android Password Test",
                "platform": "android",
                "username": "duncanmobile",
                "password": "secret",
            },
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        row = self.conn.execute("SELECT device_id, username, user_id, token_hash FROM pocket_devices").fetchone()
        self.assertEqual(row["device_id"], "android-password-test")
        self.assertEqual(row["username"], "duncanmobile")
        self.assertEqual(row["user_id"], 3)
        self.assertNotIn(payload["device_token"], row["token_hash"])

    def test_invalid_password_login_is_rejected(self):
        with patch("core.security.verify_password", return_value=False):
            resp = self.client.post(
                "/api/pocket/v1/auth/login",
                json={
                    "device_id": "android-password-test",
                    "username": "duncanmobile",
                    "password": "wrong",
                },
            )

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "authentication_failed")
        self.assertIsNone(self.conn.execute("SELECT token_hash FROM pocket_devices").fetchone())

    def test_inactive_users_cannot_pair(self):
        with self.assertRaises(ValueError):
            create_pocket_pairing_code(4)

    def test_registration_rate_limit_activates_after_failures(self):
        for _ in range(5):
            self.client.post(
                "/api/pocket/v1/auth/register-device",
                json={"device_id": "android-test", "username": "duncanmobile", "pairing_code": "BAD-CODE"},
            )

        resp = self.client.post(
            "/api/pocket/v1/auth/register-device",
            json={"device_id": "android-test", "username": "duncanmobile", "pairing_code": "BAD-CODE"},
        )

        self.assertEqual(resp.status_code, 429)

    def test_auth_rejects_wrong_device_id_and_revoked_device(self):
        headers = self._register_headers()
        wrong_device_headers = dict(headers)
        wrong_device_headers["X-LifePIM-Device-ID"] = "wrong-device"

        wrong = self.client.get("/api/pocket/v1/sync/manifest", headers=wrong_device_headers)
        self.assertEqual(wrong.status_code, 401)

        revoke_pocket_device("android-test", self.conn)
        revoked = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)
        self.assertEqual(revoked.status_code, 401)

    def test_manifest_requires_device_auth(self):
        resp = self.client.get("/api/pocket/v1/sync/manifest")

        self.assertEqual(resp.status_code, 401)

    def test_registered_mobile_device_is_listed_for_admin(self):
        self._register_headers()

        devices = list_pocket_devices(self.conn)

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_id"], "android-test")
        self.assertEqual(devices[0]["device_name"], "Android Test")
        self.assertEqual(devices[0]["platform"], "android")
        self.assertEqual(devices[0]["username"], "duncanmobile")
        self.assertIsNone(devices[0]["revoked_at"])

    def test_mobile_device_can_be_revoked(self):
        self._register_headers()

        self.assertTrue(revoke_pocket_device("android-test", self.conn))
        devices = list_pocket_devices(self.conn)

        self.assertIsNotNone(devices[0]["revoked_at"])

    def test_health_does_not_require_device_auth(self):
        resp = self.client.get("/api/pocket/v1/health")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "application/json")
        self.assertEqual(resp.get_json(), {"ok": True, "service": "lifepim-pocket", "version": 1})

    def test_manifest_and_item_download_return_markdown_content(self):
        self._add_note()
        headers = self._register_headers()

        manifest_resp = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)
        self.assertEqual(manifest_resp.status_code, 200)
        item = manifest_resp.get_json()["items"][0]
        self.assertEqual(item["relative_path"], "Shopping.md")
        self.assertEqual(item["kind"], "NOTE")
        self.assertEqual(item["ownership"], "DESKTOP_MASTER")
        self.assertEqual(item["project"], "pers")
        self.assertEqual(item["derived_project"], "pers")
        self.assertEqual(item["date_created"], "")
        self.assertEqual(item["date_modified"], "")
        self.assertFalse(item["important"])
        self.assertEqual(item["color"], "")
        self.assertEqual(item["title"], "")
        self.assertEqual(item["source_note_id"], "")
        self.assertEqual(item["metadata"]["project"], "pers")

        item_resp = self.client.get(f"/api/pocket/v1/items/{item['id']}", headers=headers)
        self.assertEqual(item_resp.status_code, 200)
        item_payload = item_resp.get_json()
        self.assertEqual(item_payload["kind"], "LIST")
        self.assertEqual(item_payload["content"], "# Shopping\n\n- [ ] Milk\n")

    def test_manifest_and_item_download_include_note_metadata(self):
        project_dir = os.path.join(self.tmpdir.name, "notes", "20-Biz", "22-Acute", "22-7-Support")
        self.conn.executescript(
            """
            CREATE TABLE lp_projects (
                owner_user_id INTEGER,
                project_id TEXT,
                project_name TEXT
            );
            CREATE TABLE lp_project_folders (
                owner_user_id INTEGER,
                project_id TEXT,
                path_prefix TEXT,
                folder_role TEXT,
                is_enabled INTEGER,
                sort_order INTEGER
            );
            """
        )
        self.conn.execute(
            "INSERT INTO lp_projects(owner_user_id, project_id, project_name) VALUES (3, 'work/business', 'Business')"
        )
        self.conn.execute(
            """
            INSERT INTO lp_project_folders(owner_user_id, project_id, path_prefix, folder_role, is_enabled, sort_order)
            VALUES (3, 'work/business', ?, 'default', 1, 10)
            """,
            (project_dir,),
        )
        self._add_note(
            file_name="start_a_bug_database.md",
            folder_path=project_dir,
            project="stale/project",
            content=(
                "---\n"
                "tags:\n"
                "- Business\n"
                "- colour-red\n"
                "- important\n"
                "title: \"start a bug database\"\n"
                "note_id: 1234\n"
                "date_created: \"2018-09-24 21:36:54\"\n"
                "date_updated: 2019-07-27 12:02:43\n"
                "folder: Business\n"
                "important: on\n"
                "color: red\n"
                "---\n"
                "\n"
                "this can be current support folder\n"
            ),
        )
        headers = self._register_headers()

        manifest_item = self.client.get("/api/pocket/v1/sync/manifest", headers=headers).get_json()["items"][0]
        item_payload = self.client.get(f"/api/pocket/v1/items/{manifest_item['id']}", headers=headers).get_json()

        for payload in (manifest_item, item_payload):
            self.assertEqual(payload["project"], "work/business")
            self.assertEqual(payload["derived_project"], "work/business")
            self.assertEqual(payload["title"], "start a bug database")
            self.assertEqual(payload["source_note_id"], "1234")
            self.assertEqual(payload["metadata"]["note_id"], "1234")
            self.assertEqual(payload["date_created"], "2018-09-24 21:36:54")
            self.assertEqual(payload["date_modified"], "2019-07-27 12:02:43")
            self.assertTrue(payload["important"])
            self.assertEqual(payload["color"], "red")
            self.assertEqual(payload["metadata"]["project"], "work/business")

    def test_manifest_skips_one_note_when_metadata_serialization_fails(self):
        self._add_note(file_name="bad.md", content="bad")
        self._add_note(file_name="good.md", content="good")
        headers = self._register_headers()

        from modules.pocket_api import routes as pocket_routes

        original_serialize = pocket_routes._serialize_note_item

        def fail_bad_note(note, *args, **kwargs):
            if note.get("file_name") == "bad.md":
                raise ValueError("bad metadata")
            return original_serialize(note, *args, **kwargs)

        with patch("modules.pocket_api.routes._serialize_note_item", side_effect=fail_bad_note):
            manifest_resp = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)

        self.assertEqual(manifest_resp.status_code, 200)
        payload = manifest_resp.get_json()
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["error_count"], 1)
        self.assertEqual([item["relative_path"] for item in payload["items"]], ["good.md"])
        self.assertEqual(payload["errors"][0]["note_id"], 1)
        self.assertEqual(payload["errors"][0]["error_type"], "ValueError")

    def test_manifest_tolerates_windows_encoded_note_front_matter(self):
        self._add_note(file_name="legacy-encoding.md", content="placeholder")
        note_path = os.path.join(self.tmpdir.name, "legacy-encoding.md")
        with open(note_path, "wb") as handle:
            handle.write(b"---\ntitle: Bob\x92s note\n---\nBody with dash \x97 here\n")
        headers = self._register_headers()

        manifest_resp = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)

        self.assertEqual(manifest_resp.status_code, 200)
        payload = manifest_resp.get_json()
        self.assertEqual(payload["error_count"], 0)
        self.assertEqual(payload["items"][0]["relative_path"], "legacy-encoding.md")

    def test_manifest_only_returns_notes_owned_by_mobile_user(self):
        owned_id = self._add_note(file_name="owned.md", content="owned", owner_user_id=3)
        other_id = self._add_note(file_name="other.md", content="other", owner_user_id=1)
        headers = self._register_headers()

        manifest_resp = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)

        self.assertEqual(manifest_resp.status_code, 200)
        paths = {item["relative_path"] for item in manifest_resp.get_json()["items"]}
        self.assertIn("owned.md", paths)
        self.assertNotIn("other.md", paths)
        item_ids = {item["id"] for item in manifest_resp.get_json()["items"]}
        self.assertIn(str(__import__("uuid").uuid5(__import__("uuid").UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:3:note:{owned_id}")), item_ids)
        self.assertNotIn(str(__import__("uuid").uuid5(__import__("uuid").UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:1:note:{other_id}")), item_ids)

    def test_manifest_includes_legacy_unowned_notes_for_bound_user(self):
        legacy_null_id = self._add_note(file_name="legacy-null.md", content="legacy null", owner_user_id=None)
        legacy_zero_id = self._add_note(file_name="legacy-zero.md", content="legacy zero", owner_user_id=0)
        self._add_note(file_name="other.md", content="other", owner_user_id=1)
        headers = self._register_headers()

        manifest_resp = self.client.get("/api/pocket/v1/sync/manifest", headers=headers)

        self.assertEqual(manifest_resp.status_code, 200)
        items = {item["relative_path"]: item for item in manifest_resp.get_json()["items"]}
        self.assertIn("legacy-null.md", items)
        self.assertIn("legacy-zero.md", items)
        self.assertNotIn("other.md", items)
        self.assertEqual(
            items["legacy-null.md"]["id"],
            str(uuid.uuid5(uuid.UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:3:note:{legacy_null_id}")),
        )
        self.assertEqual(
            items["legacy-zero.md"]["id"],
            str(uuid.uuid5(uuid.UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:3:note:{legacy_zero_id}")),
        )

        item_resp = self.client.get(f"/api/pocket/v1/items/{items['legacy-null.md']['id']}", headers=headers)

        self.assertEqual(item_resp.status_code, 200)
        self.assertEqual(item_resp.get_json()["content"], "legacy null")

    def test_item_download_rejects_note_owned_by_another_user(self):
        other_id = self._add_note(file_name="other.md", content="other", owner_user_id=1)
        headers = self._register_headers()
        item_id = str(__import__("uuid").uuid5(__import__("uuid").UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:1:note:{other_id}"))

        resp = self.client.get(f"/api/pocket/v1/items/{item_id}", headers=headers)

        self.assertEqual(resp.status_code, 404)

    def test_push_rejects_note_owned_by_another_user(self):
        self._add_note(file_name="owned.md", content="owned", owner_user_id=3)
        other_id = self._add_note(file_name="other.md", content="other", owner_user_id=1)
        headers = self._register_headers()
        item_id = str(__import__("uuid").uuid5(__import__("uuid").UUID("0dd8c9ea-42a1-4e9e-bcbb-5b0885df5d2f"), f"user:1:note:{other_id}"))

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={"id": item_id, "base_sha256": "ignored", "content": "takeover"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["results"][0]["created"])
        with open(os.path.join(self.tmpdir.name, "other.md"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "other")

    def test_push_updates_note_when_base_hash_matches(self):
        self._add_note()
        headers = self._register_headers()
        item = self.client.get("/api/pocket/v1/sync/manifest", headers=headers).get_json()["items"][0]

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={"id": item["id"], "base_sha256": item["sha256"], "content": "# Shopping\n\n- [x] Milk\n"},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        with open(os.path.join(self.tmpdir.name, "Shopping.md"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "# Shopping\n\n- [x] Milk\n")

    def test_push_accepts_server_item_id_and_returns_accepted(self):
        self._add_note()
        headers = self._register_headers()
        item = self.client.get("/api/pocket/v1/sync/manifest", headers=headers).get_json()["items"][0]

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "changes": [
                    {
                        "client_change_id": "change-1",
                        "server_item_id": item["id"],
                        "relative_path": "Shopping.md",
                        "base_sha256": item["sha256"],
                        "content": "# Shopping\n\n- [x] Milk\n",
                    }
                ]
            },
        )

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["accepted"][0]["client_change_id"], "change-1")
        self.assertEqual(payload["accepted"][0]["server_item_id"], item["id"])
        self.assertTrue(payload["accepted"][0]["sha256"])

    def test_push_conflict_returns_server_version_without_overwriting(self):
        self._add_note(content="desktop first")
        headers = self._register_headers()
        item = self.client.get("/api/pocket/v1/sync/manifest", headers=headers).get_json()["items"][0]
        item = self.client.get(f"/api/pocket/v1/items/{item['id']}", headers=headers).get_json()
        with open(os.path.join(self.tmpdir.name, "Shopping.md"), "w", encoding="utf-8") as handle:
            handle.write("desktop changed")

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={"id": item["id"], "base_sha256": item["sha256"], "content": "phone changed"},
        )

        self.assertEqual(resp.status_code, 409)
        payload = resp.get_json()
        self.assertTrue(payload["results"][0]["conflict"])
        self.assertEqual(payload["results"][0]["server"]["content"], "desktop changed")
        with open(os.path.join(self.tmpdir.name, "Shopping.md"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "desktop changed")

    def test_push_creates_mobile_only_note_for_bound_user(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-1",
                "relative_path": "phone note.md",
                "content": "# Phone note\n\nCreated on phone\n",
            },
        )

        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()["results"][0]
        self.assertTrue(result["ok"])
        self.assertTrue(result["created"])
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir.name, "phone note.md")))
        row = self.conn.execute("SELECT file_name, owner_user_id FROM lp_notes WHERE file_name = ?", ("phone note.md",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["owner_user_id"], 3)

    def test_push_creates_mobile_only_note_with_image_attachment(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()
        image_bytes = b"fake png bytes"

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-with-image",
                "relative_path": "image note.md",
                "content": "# Image note\n\n[img]photo.png[/img]\n",
                "attachments": [
                    {
                        "file_name": "photo.png",
                        "content_base64": base64.b64encode(image_bytes).decode("ascii"),
                        "sha256": hashlib.sha256(image_bytes).hexdigest(),
                        "modified_at": "2026-07-15T10:00:00Z",
                    }
                ],
            },
        )

        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()["results"][0]
        self.assertTrue(result["ok"])
        self.assertEqual(result["attachments_saved"], 1)
        image_path = os.path.join(self.tmpdir.name, "photo.png")
        self.assertTrue(os.path.exists(image_path))
        with open(image_path, "rb") as handle:
            self.assertEqual(handle.read(), image_bytes)

    def test_push_attachment_does_not_overwrite_newer_desktop_image(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()
        image_path = os.path.join(self.tmpdir.name, "photo.png")
        with open(image_path, "wb") as handle:
            handle.write(b"desktop newer")
        newer_ts = datetime(2026, 7, 16, tzinfo=timezone.utc).timestamp()
        os.utime(image_path, (newer_ts, newer_ts))

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-with-old-image",
                "relative_path": "old image note.md",
                "content": "# Image note\n\n[img]photo.png[/img]\n",
                "attachments": [
                    {
                        "file_name": "photo.png",
                        "content_base64": base64.b64encode(b"mobile older").decode("ascii"),
                        "modified_at": "2026-07-15T10:00:00Z",
                    }
                ],
            },
        )

        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()["results"][0]
        self.assertTrue(result["ok"])
        self.assertEqual(result["attachments_saved"], 0)
        with open(image_path, "rb") as handle:
            self.assertEqual(handle.read(), b"desktop newer")

    def test_repeated_mobile_only_push_updates_same_note_by_client_id(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()

        first = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-repeat",
                "relative_path": "repeat phone note.md",
                "content": "first version",
            },
        )
        second = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-repeat",
                "relative_path": "repeat phone note.md",
                "content": "second version",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        rows = self.conn.execute("SELECT file_name FROM lp_notes WHERE file_name LIKE 'repeat phone note%'").fetchall()
        self.assertEqual([row["file_name"] for row in rows], ["repeat phone note.md"])
        with open(os.path.join(self.tmpdir.name, "repeat phone note.md"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "second version")
        self.assertFalse(second.get_json()["results"][0].get("created", False))

    def test_repeated_mobile_only_push_updates_same_note_by_file_name_without_client_id(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()

        first = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "relative_path": "unnamed phone note.md",
                "content": "first version",
            },
        )
        second = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "relative_path": "unnamed phone note.md",
                "content": "second version",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        rows = self.conn.execute("SELECT file_name FROM lp_notes WHERE file_name LIKE 'unnamed phone note%'").fetchall()
        self.assertEqual([row["file_name"] for row in rows], ["unnamed phone note.md"])
        with open(os.path.join(self.tmpdir.name, "unnamed phone note.md"), "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "second version")

    def test_push_creates_mobile_only_note_in_configured_user_folder(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        configured_dir = os.path.join(self.tmpdir.name, "Pocket")
        set_user_default_note_folder(3, configured_dir, self.conn)
        headers = self._register_headers()

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "id": "mobile-local-configured",
                "relative_path": "configured phone note.md",
                "content": "# Configured note\n",
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["results"][0]["created"])
        self.assertTrue(os.path.exists(os.path.join(configured_dir, "configured phone note.md")))
        row = self.conn.execute("SELECT path FROM lp_notes WHERE file_name = ?", ("configured phone note.md",)).fetchone()
        self.assertEqual(row["path"], configured_dir)

    def test_user_pocket_settings_can_be_cleared(self):
        configured_dir = os.path.join(self.tmpdir.name, "Pocket")
        set_user_default_note_folder(3, configured_dir, self.conn)

        set_user_default_note_folder(3, "", self.conn)

        self.assertEqual(get_user_pocket_settings(3, self.conn)["default_note_folder"], "")

    def test_push_accepts_android_alias_payload(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={
                "uploads": [
                    {
                        "uuid": "mobile-local-2",
                        "path": "alias phone note.md",
                        "markdownContent": "# Alias note\n",
                    }
                ]
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["results"][0]["created"])
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir.name, "alias phone note.md")))

    def test_push_missing_unknown_note_content_returns_400(self):
        self._add_note(file_name="existing.md", content="existing", owner_user_id=3)
        headers = self._register_headers()

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            json={"id": "mobile-local-1", "relative_path": "phone note.md"},
        )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.get_json()["ok"])

    def test_oversized_sync_payload_is_rejected(self):
        headers = self._register_headers()
        self.app.config["LIFEPIM_POCKET_MAX_SYNC_PAYLOAD_BYTES"] = 1

        resp = self.client.post(
            "/api/pocket/v1/sync/push",
            headers=headers,
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(resp.status_code, 413)


if __name__ == "__main__":
    unittest.main()
