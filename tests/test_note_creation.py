import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import config as cfg
from common import data
from common import note_search_index
from common import settings
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
        notes_routes._NOTE_PROJECT_MATERIALIZED_KEYS.clear()
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
            notes_routes._NOTE_PROJECT_MATERIALIZED_KEYS.clear()
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

    def test_note_card_preview_uses_body_color_and_markdown(self):
        note_dir = os.path.join(self.tmpdir.name, "card_preview")
        os.makedirs(note_dir, exist_ok=True)
        note_path = os.path.join(note_dir, "card.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                "title: Card Preview\n"
                "color: Blue\n"
                "---\n"
                "# Card Preview\n\n"
                "This is **bold** preview text.\n"
                "Second line."
            )
        note = {
            "id": 42,
            "file_name": "card.md",
            "path": notes_routes._normalize_note_path(note_dir),
            "title": "Card Preview",
            "color": "Blue",
        }
        notes_routes._apply_note_display_fields(note)
        note_search_index.ensure_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO lp_note_search_index
            (note_id, file_path, file_mtime, file_size, title, content_text, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                42,
                note_path,
                1.0,
                10,
                "Card Preview",
                "---\n"
                "title: Card Preview\n"
                "color: Blue\n"
                "---\n"
                "# Card Preview\n\n"
                "This is **bold** preview text.\n"
                "Second line.",
                "2026-01-01T00:00:00Z",
            ),
        )

        with patch("modules.notes.routes._read_note_file", side_effect=AssertionError("card list must not read note files")):
            notes_routes._prepare_note_card_previews([note], max_chars=80)

        self.assertEqual(note["list_color_style"], "#81ecec")
        self.assertNotIn("title: Card Preview", note["preview_text"])
        self.assertNotIn("# Card Preview", note["preview_text"])
        self.assertIn("This is **bold** preview text.", note["preview_text"])
        self.assertIn("<strong>bold</strong>", note["preview_html"])

    def test_note_card_grid_preview_skips_markdown_rendering(self):
        note = {"id": 43, "file_name": "grid.md", "path": self.tmpdir.name, "title": "Grid", "color": ""}
        note_search_index.ensure_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO lp_note_search_index
            (note_id, file_path, file_mtime, file_size, title, content_text, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (43, "", 1.0, 10, "Grid", "This is **raw** text.", "2026-01-01T00:00:00Z"),
        )

        with patch("modules.notes.routes.markdown_utils.render_markdown") as render_markdown:
            notes_routes._prepare_note_card_previews([note], max_chars=80, render_html=False)

        render_markdown.assert_not_called()
        self.assertEqual(note["preview_text"], "This is **raw** text.")
        self.assertEqual(note["preview_html"], "")

    def test_note_card_preview_escapes_raw_html(self):
        note = {"id": 44, "file_name": "unsafe.md", "path": self.tmpdir.name, "title": "Unsafe", "color": ""}
        note_search_index.ensure_schema(self.conn)
        self.conn.execute(
            """
            INSERT INTO lp_note_search_index
            (note_id, file_path, file_mtime, file_size, title, content_text, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (44, "", 1.0, 10, "Unsafe", '<div class="loose">Loose **bold** text', "2026-01-01T00:00:00Z"),
        )

        notes_routes._prepare_note_card_previews([note], max_chars=120, render_html=True)

        self.assertNotIn("<div", note["preview_html"])
        self.assertIn("&lt;div", note["preview_html"])
        self.assertIn("<strong>bold</strong>", note["preview_html"])

    def test_fetch_notes_does_not_read_front_matter(self):
        note_dir = os.path.join(self.tmpdir.name, "metadata_only")
        note_id, _ = self._create_note_record("metadata_only", note_dir, project="")

        with patch(
            "modules.notes.routes._read_note_front_matter",
            side_effect=AssertionError("list fetch must not read note files"),
        ):
            notes = notes_routes._fetch_notes("unmapped")

        self.assertIn(note_id, {note.get("id") for note in notes})

    def test_refresh_note_color_metadata_backfills_blank_color_from_file(self):
        note_dir = os.path.join(self.tmpdir.name, "color_refresh")
        os.makedirs(note_dir, exist_ok=True)
        note_path = os.path.join(note_dir, "red-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write(
                "---\n"
                "title: Red Note\n"
                "color: Red\n"
                "---\n"
                "Red body\n"
            )
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": "red-note.md",
            "path": notes_routes._normalize_note_path(note_dir),
            "folder_id": "",
            "size": str(os.path.getsize(note_path)),
            "title": "Red Note",
            "color": "",
            "date_modified": "2026-07-09 16:38:25",
            "project": "",
        }
        note_id = data.add_record(
            self.conn,
            tbl["name"],
            tbl["col_list"],
            [values_map.get(col, "") for col in tbl["col_list"]],
        )

        result = notes_routes.refresh_note_color_metadata(self.conn)

        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["updated"], 1)
        row = self.conn.execute(f"SELECT color FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["color"], "Red")
        fetched = {note.get("id"): note for note in notes_routes._fetch_notes("unmapped")}
        self.assertEqual(fetched[note_id]["list_color_style"], notes_routes.NOTE_COLOR_NAMES["red"])

    def test_refresh_note_color_metadata_keeps_existing_color_by_default(self):
        note_dir = os.path.join(self.tmpdir.name, "color_refresh_existing")
        os.makedirs(note_dir, exist_ok=True)
        note_path = os.path.join(note_dir, "red-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("---\ncolor: Red\n---\nRed body\n")
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": "red-note.md",
            "path": notes_routes._normalize_note_path(note_dir),
            "folder_id": "",
            "size": str(os.path.getsize(note_path)),
            "title": "Red Note",
            "color": "Blue",
            "date_modified": "2026-07-09 16:38:25",
            "project": "",
        }
        note_id = data.add_record(
            self.conn,
            tbl["name"],
            tbl["col_list"],
            [values_map.get(col, "") for col in tbl["col_list"]],
        )

        result = notes_routes.refresh_note_color_metadata(self.conn)

        self.assertEqual(result["scanned"], 0)
        self.assertEqual(result["updated"], 0)
        row = self.conn.execute(f"SELECT color FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["color"], "Blue")

    def test_note_preview_text_uses_mobile_requested_limit(self):
        self.assertEqual(notes_routes.NOTES_PER_PAGE, 50)
        self.assertEqual(notes_routes.NOTE_CARD_MAX_CHARS, 50)
        self.assertEqual(notes_routes.NOTE_CARD_TITLE_FONT_SIZE, 18)
        self.assertEqual(notes_routes.NOTE_CARD_PREVIEW_CHARS, 300)
        self.assertEqual(notes_routes._preview_text("abcdef", 3), "abc")
        self.assertEqual(
            notes_routes._note_body_text("---\r\ntitle: X\r\n---\r\nBody", "x.md", "X"),
            "Body",
        )

    def test_note_display_settings_are_loaded_from_database(self):
        settings.save_note_display_settings(
            {
                "card_width_chars": "64",
                "title_font_size": "20",
                "preview_chars": "720",
                "notes_per_page": "75",
            },
            self.conn,
        )

        loaded = notes_routes._note_display_settings()

        self.assertEqual(loaded["card_width_chars"], 64)
        self.assertEqual(loaded["title_font_size"], 20)
        self.assertEqual(loaded["preview_chars"], 720)
        self.assertEqual(loaded["notes_per_page"], 75)

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

        def add_note(file_name, folder_path, project_id):
            values_map = {
                "file_name": file_name,
                "path": folder_path,
                "folder_id": "",
                "size": "1",
                "date_modified": "2026-07-09 16:38:25",
                "project": project_id,
            }
            values = [values_map.get(col, "") for col in tbl["col_list"]]
            return data.add_record(self.conn, tbl["name"], tbl["col_list"], values)

        root_note_id = add_note("fun_root.md", root_dir, "fun.fun.fun")
        games_note_id = add_note("games.md", games_dir, "fun/games")
        travel_note_id = add_note("travel.md", travel_dir, "fun/travel")

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

    def test_sync_note_rows_is_idempotent_and_counts_missing(self):
        notes_dir = os.path.join(self.tmpdir.name, "sync_notes")
        os.makedirs(notes_dir, exist_ok=True)
        note_path = os.path.join(notes_dir, "external.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("first")

        result = notes_routes._sync_note_rows(notes_dir)
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["updated"], 0)

        tbl = common_utils.get_table_def("notes")
        rows = self.conn.execute(f"SELECT id, file_name, path, size FROM {tbl['name']}").fetchall()
        self.assertEqual(len(rows), 1)
        note_id = rows[0]["id"]
        self.assertEqual(rows[0]["file_name"], "external.md")

        result = notes_routes._sync_note_rows(notes_dir)
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 0)
        count = self.conn.execute(f"SELECT COUNT(1) AS cnt FROM {tbl['name']}").fetchone()["cnt"]
        self.assertEqual(count, 1)

        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("first plus more")
        result = notes_routes._sync_note_rows(notes_dir)
        self.assertEqual(result["updated"], 1)
        row = self.conn.execute(f"SELECT size FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["size"], str(os.path.getsize(note_path)))

        second_path = os.path.join(notes_dir, "second.md")
        with open(second_path, "w", encoding="utf-8") as handle:
            handle.write("second")
        os.remove(note_path)
        result = notes_routes._sync_note_rows(notes_dir)
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["missing"], 1)
        count = self.conn.execute(f"SELECT COUNT(1) AS cnt FROM {tbl['name']}").fetchone()["cnt"]
        self.assertEqual(count, 2)

    def test_sync_note_rows_uses_project_folder_fallback_project(self):
        notes_dir = os.path.join(self.tmpdir.name, "sync_project")
        os.makedirs(notes_dir, exist_ok=True)
        note_path = os.path.join(notes_dir, "project-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("project note")

        result = notes_routes._sync_note_rows(notes_dir, fallback_project="fun/games")

        self.assertEqual(result["inserted"], 1)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT project FROM {tbl['name']} WHERE file_name = ?", ("project-note.md",)).fetchone()
        self.assertEqual(row["project"], "fun/games")

    def test_sync_note_rows_uses_project_folder_mapping_fallback(self):
        notes_root = os.path.join(self.tmpdir.name, "sync_project_root")
        project_dir = os.path.join(notes_root, "Games")
        os.makedirs(project_dir, exist_ok=True)
        note_path = os.path.join(project_dir, "mapped-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("mapped project note")
        projects_mod.project_upsert(
            {
                "project_id": "fun/games",
                "tab": "FUN",
                "group_name": "FUN",
                "project_name": "Games",
            },
            conn=self.conn,
        )
        projects_mod.project_folder_add(
            "fun/games",
            project_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )

        result = notes_routes._sync_note_rows(notes_root)

        self.assertEqual(result["inserted"], 1)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT project FROM {tbl['name']} WHERE file_name = ?", ("mapped-note.md",)).fetchone()
        self.assertEqual(row["project"], "fun/games")

    def test_materialize_note_projects_backfills_blank_project_from_mapping(self):
        project_dir = os.path.join(self.tmpdir.name, "materialize_project", "Games")
        os.makedirs(project_dir, exist_ok=True)
        projects_mod.project_upsert(
            {
                "project_id": "fun/games",
                "tab": "FUN",
                "group_name": "FUN",
                "project_name": "Games",
            },
            conn=self.conn,
        )
        projects_mod.project_folder_add(
            "fun/games",
            project_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": "blank-project.md",
            "path": notes_routes._normalize_note_path(project_dir),
            "folder_id": "",
            "size": "1",
            "date_modified": "2026-07-09 16:38:25",
            "project": "",
        }
        note_id = data.add_record(
            self.conn,
            tbl["name"],
            tbl["col_list"],
            [values_map.get(col, "") for col in tbl["col_list"]],
        )

        result = notes_routes.materialize_note_projects(self.conn)

        self.assertEqual(result["updated"], 1)
        row = self.conn.execute(f"SELECT project FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["project"], "fun/games")
        filtered_ids = {note.get("id") for note in notes_routes._fetch_notes("fun/games")}
        self.assertIn(note_id, filtered_ids)

    def test_rename_note_updates_file_and_metadata(self):
        note_dir = os.path.join(self.tmpdir.name, "rename_note")
        note_id, created = self._create_note_record("old title", note_dir, project="pers/health")

        new_file_name = notes_routes._rename_note(note_id, "new title")
        self.assertEqual(new_file_name, "new title.md")
        self.assertFalse(os.path.exists(created["full_path"]))
        new_path = os.path.join(note_dir, "new title.md")
        self.assertTrue(os.path.exists(new_path))

        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT file_name, path FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["file_name"], "new title.md")
        self.assertEqual(row["path"], notes_routes._normalize_note_path(note_dir))
        with open(new_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn('title: "new title"', text)
        self.assertIn("# new title", text)

    def test_move_note_updates_project_folder_and_metadata(self):
        source_dir = os.path.join(self.tmpdir.name, "move_source")
        target_dir = os.path.join(self.tmpdir.name, "move_target")
        project_id = "fun/games"
        projects_mod.project_upsert(
            {
                "project_id": project_id,
                "tab": "FUN",
                "group_name": "FUN",
                "project_name": "Games",
            },
            conn=self.conn,
        )
        projects_mod.project_folder_add(
            project_id,
            target_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        note_id, created = self._create_note_record("move me", source_dir, project="")

        moved_path = notes_routes._move_note_to_project(note_id, project_id)
        self.assertFalse(os.path.exists(created["full_path"]))
        self.assertTrue(os.path.exists(moved_path))
        self.assertEqual(os.path.dirname(moved_path), notes_routes._normalize_note_path(target_dir))

        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT file_name, path, project FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["file_name"], os.path.basename(moved_path))
        self.assertEqual(row["path"], notes_routes._normalize_note_path(target_dir))
        self.assertEqual(row["project"], project_id)

    def test_archive_delete_moves_file_and_removes_db_row(self):
        note_dir = os.path.join(self.tmpdir.name, "delete_note")
        note_id, created = self._create_note_record("delete me", note_dir, project="fun/games")

        archived_path = notes_routes._archive_and_delete_note(note_id)
        self.assertFalse(os.path.exists(created["full_path"]))
        self.assertTrue(os.path.exists(archived_path))
        self.assertEqual(os.path.dirname(archived_path), os.path.join(notes_routes._normalize_note_path(note_dir), "deleted"))
        self.assertTrue(os.path.basename(archived_path).startswith("games__delete_me_"))

        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT id FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertIsNone(row)

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
