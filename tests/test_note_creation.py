import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import config as cfg
from common import data
from common import search
from common import utils as common_utils
from common import projects as projects_mod
from modules.notes import routes as notes_routes
from modules.admin import routes as admin_routes


def _create_table(conn, tbl):
    col_defs = []
    for col in tbl["col_list"]:
        col_type = "TEXT"
        if "date" in col.lower():
            col_type = "TEXT"
        col_defs.append(f"{col} {col_type}")
    col_defs.extend(["user_name TEXT", "rec_extract_date TEXT"])
    sql = (
        f"CREATE TABLE IF NOT EXISTS {tbl['name']} ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        f"{', '.join(col_defs)})"
    )
    conn.execute(sql)


class TestNoteCreation(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        for tbl in cfg.table_def:
            _create_table(self.conn, tbl)
        data.ensure_folder_schema(self.conn)
        projects_mod.ensure_projects_schema(self.conn)
        common_utils.ensure_user_log_schema(self.conn)
        tmp_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
        os.makedirs(tmp_root, exist_ok=True)
        self.tmpdir = tempfile.TemporaryDirectory(dir=tmp_root)

    def tearDown(self):
        try:
            self.tmpdir.cleanup()
        finally:
            data.conn = self._old_conn
            self.conn.close()

    def _create_note_record(self, title, folder_path, project=""):
        created = notes_routes._create_note_file(folder_path, title, project)
        full_path = created["full_path"]
        size = ""
        date_modified = ""
        try:
            size = str(os.path.getsize(full_path))
            date_modified = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            pass
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": created["file_name"],
            "path": created["folder_path"],
            "folder_id": "",
            "size": size,
            "date_modified": date_modified,
            "project": project,
        }
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        note_id = data.add_record(self.conn, tbl["name"], tbl["col_list"], values)
        return note_id, created

    def test_unmapped_and_filtered_notes_and_search(self):
        unmapped_dir = os.path.join(self.tmpdir.name, "unmapped")
        project_dir = os.path.join(self.tmpdir.name, "project")

        note1_id, note1 = self._create_note_record("note_creation_test_unmapped", unmapped_dir, project="")

        project_id = "proj.test"
        projects_mod.project_upsert(
            {
                "project_id": project_id,
                "tab": "TEST",
                "group_name": "Test",
                "project_name": "Test Project",
            },
            conn=self.conn,
        )
        projects_mod.project_folder_add(
            project_id,
            project_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )

        note2_id, note2 = self._create_note_record("note_creation_test_filtered", project_dir, project=project_id)

        unmapped_notes = notes_routes._fetch_notes("unmapped")
        unmapped_ids = {n.get("id") for n in unmapped_notes}
        self.assertIn(note1_id, unmapped_ids)
        self.assertNotIn(note2_id, unmapped_ids)

        filtered_notes = notes_routes._fetch_notes(project_id)
        filtered_ids = {n.get("id") for n in filtered_notes}
        self.assertIn(note2_id, filtered_ids)

        results = search.search_all("note_creation_test")
        note_titles = {
            r.get("title")
            for r in (results.get("primary") or []) + (results.get("secondary") or [])
            if r.get("route") == "notes"
        }
        self.assertIn(note1.get("file_name"), note_titles)
        self.assertIn(note2.get("file_name"), note_titles)

    def test_delete_note_removes_from_unmapped(self):
        unmapped_dir = os.path.join(self.tmpdir.name, "unmapped_delete")
        note_id, _ = self._create_note_record("note_creation_test_delete", unmapped_dir, project="")

        tbl = common_utils.get_table_def("notes")
        data.delete_record(self.conn, tbl["name"], note_id)

        unmapped_notes = notes_routes._fetch_notes("unmapped")
        unmapped_ids = {n.get("id") for n in unmapped_notes}
        self.assertNotIn(note_id, unmapped_ids)

    def test_undo_restores_deleted_note(self):
        unmapped_dir = os.path.join(self.tmpdir.name, "unmapped_undo")
        note_id, _ = self._create_note_record("note_creation_test_undo", unmapped_dir, project="")

        tbl = common_utils.get_table_def("notes")
        data.delete_record(self.conn, tbl["name"], note_id)

        row = self.conn.execute(
            "SELECT id, action, entity_type, entity_id, before_json, after_json "
            "FROM sys_user_log WHERE action = 'delete' AND entity_type = ? AND entity_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (tbl["name"], str(note_id)),
        ).fetchone()
        self.assertIsNotNone(row)

        ok, msg = admin_routes._undo_log_entry(self.conn, dict(row))
        self.assertTrue(ok, msg)

        unmapped_notes = notes_routes._fetch_notes("unmapped")
        unmapped_ids = {n.get("id") for n in unmapped_notes}
        self.assertIn(note_id, unmapped_ids)


if __name__ == "__main__":
    unittest.main()
