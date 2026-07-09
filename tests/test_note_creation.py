import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

from flask import Flask

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

    def test_note_folder_id_preserves_live_note_path_alias_on_update(self):
        project_id = "pers/health"
        note_dir = r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health"
        projects_mod.project_upsert(
            {
                "project_id": project_id,
                "tab": "PERS",
                "group_name": "PERS",
                "project_name": "Health",
            },
            conn=self.conn,
        )
        projects_mod.project_folder_add(
            project_id,
            note_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )

        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": "new note in health.md",
            "path": note_dir,
            "folder_id": "",
            "size": "160",
            "date_modified": "2026-07-09 16:38:25",
            "project": project_id,
        }
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        note_id = data.add_record(self.conn, tbl["name"], tbl["col_list"], values)
        self.assertTrue(note_id)

        alias_dir = r"E:\BK_fangorn\user\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health"
        self.conn.execute("INSERT INTO dim_folder(folder_path) VALUES (?)", (alias_dir,))
        alias_folder_id = self.conn.execute(
            "SELECT folder_id FROM dim_folder WHERE folder_path = ?",
            (alias_dir,),
        ).fetchone()["folder_id"]
        self.conn.execute("UPDATE lp_notes SET folder_id = ? WHERE id = ?", (alias_folder_id, note_id))
        self.conn.commit()

        stale_filtered_notes = notes_routes._fetch_notes(project_id)
        stale_filtered_ids = {n.get("id") for n in stale_filtered_notes}
        self.assertIn(note_id, stale_filtered_ids)
        stale_derived = {n.get("id"): n.get("derived_project") for n in stale_filtered_notes}
        self.assertEqual(stale_derived[note_id], project_id)

        values_map["size"] = "161"
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        self.assertTrue(data.update_record(self.conn, tbl["name"], note_id, tbl["col_list"], values))

        row = self.conn.execute(
            "SELECT t.folder_id, df.folder_path "
            "FROM lp_notes t LEFT JOIN dim_folder df ON df.folder_id = t.folder_id "
            "WHERE t.id = ?",
            (note_id,),
        ).fetchone()
        self.assertEqual(row["folder_path"], note_dir)

        filtered_notes = notes_routes._fetch_notes(project_id)
        filtered_ids = {n.get("id") for n in filtered_notes}
        self.assertIn(note_id, filtered_ids)
        derived = {n.get("id"): n.get("derived_project") for n in filtered_notes}
        self.assertEqual(derived[note_id], project_id)

    def test_parent_project_includes_children_without_broad_leaf_leakage(self):
        root_dir = r"N:\duncan\LifePIM_Data\DATA\notes\50-Fun"
        games_dir = root_dir + r"\51-Games"
        travel_dir = root_dir + r"\56-Travel"
        projects = [
            ("fun.fun.fun", "FUN", "FUN", "Fun", root_dir),
            ("fun/games", "FUN", "FUN", "Games", games_dir),
            ("fun/sport", "FUN", "FUN", "Sport", root_dir),
            ("fun/travel", "FUN", "FUN", "Travel", root_dir),
        ]
        for project_id, tab, group_name, project_name, folder_path in projects:
            projects_mod.project_upsert(
                {
                    "project_id": project_id,
                    "tab": tab,
                    "group_name": group_name,
                    "project_name": project_name,
                },
                conn=self.conn,
            )
            projects_mod.project_folder_add(
                project_id,
                folder_path,
                folder_role="default",
                is_write_enabled=1,
                conn=self.conn,
            )

        tbl = common_utils.get_table_def("notes")

        def add_note(file_name, folder_path):
            values_map = {
                "file_name": file_name,
                "path": folder_path,
                "folder_id": "",
                "size": "1",
                "date_modified": "2026-07-09 16:38:25",
                "project": "",
            }
            values = [values_map.get(col, "") for col in tbl["col_list"]]
            return data.add_record(self.conn, tbl["name"], tbl["col_list"], values)

        root_note_id = add_note("fun_root.md", root_dir)
        games_note_id = add_note("games.md", games_dir)
        travel_note_id = add_note("travel.md", travel_dir)

        parent_ids = {n.get("id") for n in notes_routes._fetch_notes("fun")}
        self.assertIn(root_note_id, parent_ids)
        self.assertIn(games_note_id, parent_ids)
        self.assertIn(travel_note_id, parent_ids)

        games_ids = {n.get("id") for n in notes_routes._fetch_notes("fun/games")}
        self.assertNotIn(root_note_id, games_ids)
        self.assertIn(games_note_id, games_ids)
        self.assertNotIn(travel_note_id, games_ids)

        travel_ids = {n.get("id") for n in notes_routes._fetch_notes("fun/travel")}
        self.assertNotIn(root_note_id, travel_ids)
        self.assertNotIn(games_note_id, travel_ids)
        self.assertIn(travel_note_id, travel_ids)

        sport_ids = {n.get("id") for n in notes_routes._fetch_notes("fun/sport")}
        self.assertNotIn(root_note_id, sport_ids)
        self.assertNotIn(games_note_id, sport_ids)
        self.assertNotIn(travel_note_id, sport_ids)

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

    def test_autosave_rejects_stale_note_file(self):
        note_dir = os.path.join(self.tmpdir.name, "stale_save")
        note_id, created = self._create_note_record("note_creation_test_stale", note_dir, project="")
        full_path = created["full_path"]
        loaded_state = notes_routes._note_file_state(full_path)
        self.assertIsNotNone(loaded_state)

        with open(full_path, "w", encoding="utf-8") as handle:
            handle.write("changed elsewhere")
        bumped_ns = int(loaded_state["mtime_ns"]) + 1_000_000_000
        os.utime(full_path, ns=(bumped_ns, bumped_ns))

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        resp = app.test_client().post(
            f"/notes/api/save/{note_id}",
            json={
                "content": "browser edit",
                "base_mtime_ns": loaded_state["mtime_ns"],
                "base_hash": loaded_state["sha256"],
            },
        )

        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.get_json().get("conflict"))
        with open(full_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "changed elsewhere")

    def test_autosave_allows_timestamp_only_change(self):
        note_dir = os.path.join(self.tmpdir.name, "timestamp_only_save")
        note_id, created = self._create_note_record("note_creation_test_timestamp", note_dir, project="")
        full_path = created["full_path"]
        loaded_state = notes_routes._note_file_state(full_path)
        self.assertIsNotNone(loaded_state)

        bumped_ns = int(loaded_state["mtime_ns"]) + 1_000_000_000
        os.utime(full_path, ns=(bumped_ns, bumped_ns))

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        resp = app.test_client().post(
            f"/notes/api/save/{note_id}",
            json={
                "content": "browser edit after timestamp drift",
                "base_mtime_ns": loaded_state["mtime_ns"],
                "base_hash": loaded_state["sha256"],
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get("ok"))
        with open(full_path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "browser edit after timestamp drift")


if __name__ == "__main__":
    unittest.main()
