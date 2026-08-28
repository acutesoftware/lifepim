import os
import sqlite3
import sys
import tempfile
import unittest
from io import BytesIO
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
from common import areas as areas_mod
from common import collections as collections_mod
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
        notes_routes._NOTE_AREA_MATERIALIZED_KEYS.clear()
        notes_routes._NOTE_FOLDER_INVALID_PRUNE_DONE = False
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        for tbl in cfg.table_def:
            _create_table(self.conn, tbl)
        data.ensure_folder_schema(self.conn)
        areas_mod.ensure_areas_schema(self.conn)
        common_utils.ensure_user_log_schema(self.conn)
        tmp_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
        os.makedirs(tmp_root, exist_ok=True)
        self.tmpdir = tempfile.TemporaryDirectory(dir=tmp_root)

    def tearDown(self):
        try:
            self.tmpdir.cleanup()
        finally:
            notes_routes._NOTE_AREA_MATERIALIZED_KEYS.clear()
            notes_routes._NOTE_FOLDER_INVALID_PRUNE_DONE = False
            data.conn = self._old_conn
            self.conn.close()

    def _create_note_record(self, title, folder_path, area=""):
        created = notes_routes._create_note_file(folder_path, title, area)
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
            "area": area,
        }
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        note_id = data.add_record(self.conn, tbl["name"], tbl["col_list"], values)
        return note_id, created

    def _notes_test_app(self):
        app = Flask(__name__, template_folder=os.path.join(root_folder, "templates"))
        app.register_blueprint(notes_routes.notes_bp)

        @app.route("/search")
        def search_route():
            return ""

        @app.route("/site.webmanifest")
        def site_webmanifest():
            return {}

        app.add_url_rule(
            "/projects/assign",
            endpoint="projects.assign_project_route",
            view_func=lambda: "",
            methods=["POST"],
        )
        app.add_url_rule(
            "/projects/add",
            endpoint="projects.add_project_route",
            view_func=lambda: "",
        )
        app.add_url_rule(
            "/areas/folders/add",
            endpoint="areas.area_folder_add_route",
            view_func=lambda: "",
            methods=["POST"],
        )
        app.add_url_rule(
            "/areas/folders/<int:area_folder_id>/default",
            endpoint="areas.area_folder_set_default_route",
            view_func=lambda area_folder_id: "",
            methods=["POST"],
        )
        app.add_url_rule(
            "/areas/folders/<int:area_folder_id>/open",
            endpoint="areas.area_folder_open_route",
            view_func=lambda area_folder_id: "",
            methods=["POST"],
        )
        app.add_url_rule(
            "/areas/folders/<int:area_folder_id>/toggle",
            endpoint="areas.area_folder_toggle_route",
            view_func=lambda area_folder_id: "",
            methods=["POST"],
        )
        app.add_url_rule(
            "/areas/folders/<int:area_folder_id>/remove",
            endpoint="areas.area_folder_remove_route",
            view_func=lambda area_folder_id: "",
            methods=["POST"],
        )

        return app

    def _bump_dir_mtime(self, folder_path):
        current = os.stat(folder_path).st_mtime_ns
        os.utime(folder_path, ns=(current + 1_000_000_000, current + 1_000_000_000))

    def test_unmapped_and_filtered_notes_and_search(self):
        unmapped_dir = os.path.join(self.tmpdir.name, "unmapped")
        area_dir = os.path.join(self.tmpdir.name, "area")

        note1_id, note1 = self._create_note_record("note_creation_test_unmapped", unmapped_dir, area="")

        area_id = "area.test"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "TEST",
                "group_name": "Test",
                "area_name": "Test Area",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            area_id,
            area_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )

        note2_id, note2 = self._create_note_record("note_creation_test_filtered", area_dir, area=area_id)
        note3_id, note3 = self._create_note_record(
            "note_creation_test_typo_area",
            area_dir,
            area="cats and dogs",
        )

        cats_area_id = "cats"
        areas_mod.area_upsert(
            {
                "area_id": cats_area_id,
                "tab": "TEST",
                "group_name": "Test",
                "area_name": "Cats",
            },
            conn=self.conn,
        )
        note4_id, _ = self._create_note_record(
            "note_creation_test_exact_label_area",
            area_dir,
            area="Cats",
        )

        unmapped_notes = notes_routes._fetch_notes("unmapped")
        unmapped_ids = {n.get("id") for n in unmapped_notes}
        self.assertIn(note1_id, unmapped_ids)
        self.assertIn(note3_id, unmapped_ids)
        self.assertNotIn(note2_id, unmapped_ids)
        self.assertNotIn(note4_id, unmapped_ids)
        self.assertEqual(notes_routes._count_notes("unmapped"), len(unmapped_notes))

        filtered_notes = notes_routes._fetch_notes(area_id)
        filtered_ids = {n.get("id") for n in filtered_notes}
        self.assertIn(note2_id, filtered_ids)

        all_notes = notes_routes._fetch_notes("")
        all_ids = {n.get("id") for n in all_notes}
        self.assertIn(note3_id, all_ids)

        results = search.search_all("note_creation_test")
        note_titles = {
            r.get("title")
            for r in (results.get("primary") or []) + (results.get("secondary") or [])
            if r.get("route") == "notes"
        }
        self.assertIn(note1.get("file_name"), note_titles)
        self.assertIn(note2.get("file_name"), note_titles)
        self.assertIn(note3.get("file_name"), note_titles)

    def test_notes_area_context_resolves_display_name_to_mapped_folders(self):
        area_dir = os.path.join(self.tmpdir.name, "ue5")
        areas_mod.area_upsert(
            {
                "area_id": "area/UE5",
                "tab": "AREAS",
                "group_name": "AREAS",
                "area_name": "UE5",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            "area/UE5",
            area_dir,
            folder_role="default",
            conn=self.conn,
        )

        area_info, folders = notes_routes._area_context("UE5")
        scope_ids = notes_routes._area_scope_ids("UE5")

        self.assertEqual(area_info["area_id"], "area/UE5")
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0]["path_prefix"], os.path.abspath(area_dir))
        self.assertIn("UE5", scope_ids)
        self.assertIn("area/UE5", scope_ids)

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

    def test_note_search_index_strips_front_matter_and_uses_database_title(self):
        note_dir = os.path.join(self.tmpdir.name, "search_index_metadata")
        note_id, created = self._create_note_record("indexed note", note_dir, area="")
        with open(created["full_path"], "w", encoding="utf-8") as handle:
            handle.write("---\ntitle: File Title\nis_template: true\n---\n\nBody text")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(f"UPDATE {tbl['name']} SET title = ? WHERE id = ?", ("Database Title", note_id))
        self.conn.commit()

        note_search_index.rebuild_index(self.conn)

        row = self.conn.execute(
            "SELECT title, content_text FROM lp_note_search_index WHERE note_id = ?",
            (note_id,),
        ).fetchone()
        self.assertEqual(row["title"], "Database Title")
        self.assertEqual(row["content_text"], "\nBody text")
        self.assertNotIn("is_template", row["content_text"])

    def test_fetch_notes_does_not_read_front_matter(self):
        note_dir = os.path.join(self.tmpdir.name, "metadata_only")
        note_id, _ = self._create_note_record("metadata_only", note_dir, area="")

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
            "area": "",
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
            "area": "",
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
                "sample_lines": "12",
                "notes_per_page": "75",
            },
            self.conn,
        )

        loaded = notes_routes._note_display_settings()

        self.assertEqual(loaded["card_width_chars"], 64)
        self.assertEqual(loaded["title_font_size"], 20)
        self.assertEqual(loaded["preview_chars"], 720)
        self.assertEqual(loaded["sample_lines"], 12)
        self.assertEqual(loaded["notes_per_page"], 75)

    def test_note_sample_text_uses_first_and_last_configured_lines(self):
        note_text = "\n".join(f"line {idx}" for idx in range(1, 11))

        sample = notes_routes._sample_note_text(note_text, 3)

        self.assertIn("line 1\nline 2\nline 3", sample)
        self.assertIn("... 4 lines omitted ...", sample)
        self.assertIn("line 8\nline 9\nline 10", sample)
        self.assertNotIn("line 4", sample)

    def test_note_front_matter_block_is_extracted_for_metadata_view(self):
        text = "---\ntitle: Meta\ncolor: Blue\n---\n\nBody text"

        self.assertEqual(
            notes_routes._front_matter_block_text(text),
            "---\ntitle: Meta\ncolor: Blue\n---",
        )

    def test_set_note_color_updates_database_only(self):
        note_dir = os.path.join(self.tmpdir.name, "color_update")
        note_id, created = self._create_note_record("color update", note_dir, area="")

        notes_routes._set_note_color(note_id, "Blue")

        with open(created["full_path"], "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("color: Blue", text)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT color FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["color"], "Blue")

    def test_note_view_uses_database_metadata_not_front_matter(self):
        note_dir = os.path.join(self.tmpdir.name, "view_db_metadata")
        note_id, created = self._create_note_record("view db metadata", note_dir, area="")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(
            f"UPDATE {tbl['name']} SET title = ?, color = ?, area = ?, is_template = ?, is_important = ? WHERE id = ?",
            ("Database Title", "Green", "db/area", "true", "true", note_id),
        )
        self.conn.commit()
        with open(created["full_path"], "w", encoding="utf-8") as handle:
            handle.write("---\ntitle: File Title\ncolor: Blue\narea: file/area\nis_template: false\nis_important: false\n---\n\nBody text")

        response = self._notes_test_app().test_client().get(f"/notes/view/{note_id}?format=metadata")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Database Title", html)
        self.assertIn("db/area", html)
        self.assertIn("Template</th><td>Yes", html)
        self.assertIn("Important</th><td>Yes", html)
        self.assertNotIn("Front Matter", html)
        self.assertNotIn("File Title", html)

    def test_note_view_metadata_mode_hides_body_and_front_matter(self):
        note_dir = os.path.join(self.tmpdir.name, "metadata_view")
        note_id, created = self._create_note_record("metadata view", note_dir, area="")
        with open(created["full_path"], "w", encoding="utf-8") as handle:
            handle.write("---\ntitle: Meta View\ncolor: Blue\n---\n\nBody text")

        response = self._notes_test_app().test_client().get(f"/notes/view/{note_id}?format=metadata")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("metadata view.md", html)
        self.assertNotIn("Front Matter", html)
        self.assertNotIn("Meta View", html)
        self.assertNotIn("color: Blue", html)
        self.assertNotIn("Body text", html)

    def test_note_view_markdown_mode_shows_body_without_front_matter(self):
        note_dir = os.path.join(self.tmpdir.name, "markdown_view")
        note_id, created = self._create_note_record("markdown view", note_dir, area="")
        with open(created["full_path"], "w", encoding="utf-8") as handle:
            handle.write("---\ntitle: Markdown View\ncolor: Blue\n---\n\nBody text")

        response = self._notes_test_app().test_client().get(f"/notes/view/{note_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Body text", html)
        self.assertNotIn("title: Markdown View", html)
        self.assertNotIn("color: Blue", html)

    def test_note_view_has_popout_action(self):
        note_dir = os.path.join(self.tmpdir.name, "popout_action")
        note_id, _created = self._create_note_record("popout action", note_dir, area="")

        response = self._notes_test_app().test_client().get(f"/notes/view/{note_id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"/notes/{note_id}/popout", html)
        self.assertIn(f"lifepim-note-{note_id}", html)
        self.assertIn("Pop Out", html)

    def test_note_popout_route_renders_minimal_note_window(self):
        note_dir = os.path.join(self.tmpdir.name, "popout_view")
        note_id, created = self._create_note_record("Book Ideas", note_dir, area="")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(f"UPDATE {tbl['name']} SET color = ? WHERE id = ?", ("Blue", note_id))
        self.conn.commit()
        with open(created["full_path"], "w", encoding="utf-8") as handle:
            handle.write("---\ntitle: Book Ideas\ncolor: Blue\n---\n\n# Book Ideas\n\nSome **notes** here.")

        response = self._notes_test_app().test_client().get(f"/notes/{note_id}/popout")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>LifePIM - Book Ideas.md</title>", html)
        self.assertIn("<h1>LifePIM Note : Book Ideas</h1>", html)
        self.assertIn("style=\"--note-color: #81ecec;\"", html)
        self.assertIn('id="note-popout-view"', html)
        self.assertIn('id="note-popout-edit"', html)
        self.assertIn('id="note-popout-save"', html)
        self.assertIn('id="note-popout-close"', html)
        self.assertIn("<strong>notes</strong>", html)
        self.assertIn(f'data-save-url="/notes/api/save/{note_id}"', html)
        self.assertNotIn("title: Book Ideas", html)
        self.assertNotIn("color: Blue", html)
        self.assertNotIn('class="topbar"', html)
        self.assertNotIn('class="side-tabs"', html)
        self.assertNotIn("Open Folder", html)
        self.assertNotIn("Delete this file", html)

    def test_note_popout_save_url_uses_existing_save_endpoint(self):
        note_dir = os.path.join(self.tmpdir.name, "popout_save")
        note_id, created = self._create_note_record("popout save", note_dir, area="")
        loaded_state = notes_routes._note_file_state(created["full_path"])

        app = self._notes_test_app()
        resp = app.test_client().post(
            f"/notes/api/save/{note_id}",
            json={
                "content": "saved from popout",
                "base_mtime_ns": loaded_state["mtime_ns"],
                "base_hash": loaded_state["sha256"],
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json().get("ok"))
        with open(created["full_path"], "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "saved from popout")

    def test_note_view_inspect_mode_shows_raw_bytes_safely(self):
        note_dir = os.path.join(self.tmpdir.name, "inspect_view")
        note_id, created = self._create_note_record("inspect view", note_dir, area="")
        raw_bytes = b'<script>alert("test")</script>\nHello\xffWorld'
        with open(created["full_path"], "wb") as handle:
            handle.write(raw_bytes)

        response = self._notes_test_app().test_client().get(f"/notes/view/{note_id}?format=inspect")
        html = response.get_data(as_text=True)

        with open(created["full_path"], "rb") as handle:
            self.assertEqual(handle.read(), raw_bytes)
        self.assertEqual(response.status_code, 200)
        self.assertIn('<option value="inspect" selected>Inspect</option>', html)
        self.assertIn("&lt;script&gt;alert(&#34;test&#34;)&lt;/script&gt;", html)
        self.assertNotIn('<script>alert("test")</script>', html)
        self.assertIn("[INVALID UTF-8: FF]", html)

    def test_note_view_markdown_mode_resolves_obsidian_wiki_links_by_title(self):
        note_dir = os.path.join(self.tmpdir.name, "wiki_links")
        source_id, source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("Target Note", note_dir, area="")
        dup1_id, _dup1 = self._create_note_record("duplicate-one", note_dir, area="")
        dup2_id, _dup2 = self._create_note_record("duplicate-two", note_dir, area="")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(f"UPDATE {tbl['name']} SET title = ? WHERE id = ?", ("Duplicate", dup1_id))
        self.conn.execute(f"UPDATE {tbl['name']} SET title = ? WHERE id = ?", ("Duplicate", dup2_id))
        self.conn.commit()
        with open(source["full_path"], "w", encoding="utf-8") as handle:
            handle.write("See [[Target Note]], [[Duplicate]], and [[Missing Note]].")

        response = self._notes_test_app().test_client().get(f"/notes/view/{source_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', html)
        self.assertIn('class="wiki-link wiki-link-ambiguous"', html)
        self.assertIn("Ambiguous link: 2 notes match", html)
        self.assertIn('class="wiki-link wiki-link-broken"', html)
        self.assertIn("Broken link: no matching note", html)

    def test_wiki_search_returns_id_backed_link_syntax(self):
        note_dir = os.path.join(self.tmpdir.name, "wiki_search")
        source_id, _source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("Alpha Project Plan", note_dir, area="")

        response = self._notes_test_app().test_client().get(
            f"/notes/api/wiki-search?q=alp proj&exclude_id={source_id}"
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["results"][0]["id"], target_id)
        self.assertEqual(payload["results"][0]["wiki_link"], f"[[Alpha Project Plan|note:{target_id}]]")
        self.assertEqual(payload["results"][0]["path_wiki_link"], "[[Alpha Project Plan.md]]")
        self.assertEqual(payload["results"][0]["markdown_link"], "[Alpha Project Plan](<Alpha Project Plan.md>)")

    def test_wiki_search_returns_relative_path_wiki_link_for_child_folder_note(self):
        note_dir = os.path.join(self.tmpdir.name, "DATA", "notes", "40-Dev", "42-HOWTO")
        child_dir = os.path.join(note_dir, "42-4-misc")
        source_id, _source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("_HOWTO__SQL", child_dir, area="")

        response = self._notes_test_app().test_client().get(
            f"/notes/api/wiki-search?q=sql&exclude_id={source_id}"
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["results"][0]["id"], target_id)
        self.assertEqual(payload["results"][0]["path_wiki_link"], "[[42-4-misc/_HOWTO__SQL.md]]")
        self.assertEqual(payload["results"][0]["markdown_link"], "[_HOWTO__SQL](42-4-misc/_HOWTO__SQL.md)")

    def test_wiki_preview_renders_id_backed_links(self):
        note_dir = os.path.join(self.tmpdir.name, "wiki_preview")
        source_id, _source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("Preview Target", note_dir, area="")

        response = self._notes_test_app().test_client().post(
            f"/notes/api/wiki-preview/{source_id}",
            json={"content": f"See [[Preview Target|note:{target_id}]]."},
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', payload["html"])
        self.assertIn(">Preview Target</a>", payload["html"])

    def test_note_view_markdown_resolves_obsidian_path_link_without_md_extension(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        source_dir = os.path.join(notes_root, "70-Make", "72-PC")
        target_dir = os.path.join(notes_root, "40-Dev", "42-HOWTO", "42-7-Apps", "Orgmode")
        source_id, source = self._create_note_record("Linux_2024_manjaro", source_dir, area="")
        target_id, _target = self._create_note_record("__INDEX__ORGMODE", target_dir, area="")
        with open(source["full_path"], "w", encoding="utf-8") as handle:
            handle.write(
                "Back to [[40-Dev/42-HOWTO/42-7-Apps/Orgmode/__INDEX__ORGMODE|__INDEX__ORGMODE]]"
            )

        response = self._notes_test_app().test_client().get(f"/notes/view/{source_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', html)
        self.assertIn(">__INDEX__ORGMODE</a>", html)
        self.assertNotIn('class="wiki-link wiki-link-broken"', html)

    def test_note_view_markdown_resolves_relative_markdown_note_link(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        source_dir = os.path.join(notes_root, "40-Dev", "42-HOWTO", "42-7-Apps", "Orgmode")
        target_dir = os.path.join(source_dir, "42-4-misc")
        source_id, source = self._create_note_record("OrgMode LifePIM", source_dir, area="")
        target_id, _target = self._create_note_record("_HOWTO__SQL", target_dir, area="")
        with open(source["full_path"], "w", encoding="utf-8") as handle:
            handle.write("*HOWTO* SQL = [_HOWTO__SQL](42-4-misc/_HOWTO__SQL.md)")

        response = self._notes_test_app().test_client().get(f"/notes/view/{source_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', html)
        self.assertIn(">_HOWTO__SQL</a>", html)
        self.assertNotIn('href="42-4-misc/_HOWTO__SQL.md"', html)
        self.assertNotIn('class="note-link note-link-broken"', html)

    def test_note_view_markdown_resolves_current_relative_path_wiki_link(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        source_dir = os.path.join(notes_root, "40-Dev", "42-HOWTO", "42-7-Apps", "Orgmode")
        target_dir = os.path.join(source_dir, "42-4-misc")
        source_id, source = self._create_note_record("OrgMode LifePIM", source_dir, area="")
        target_id, _target = self._create_note_record("_HOWTO__SQL", target_dir, area="")
        with open(source["full_path"], "w", encoding="utf-8") as handle:
            handle.write("*HOWTO* SQL = [[42-4-misc/_HOWTO__SQL.md]]")

        response = self._notes_test_app().test_client().get(f"/notes/view/{source_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', html)
        self.assertIn(">42-4-misc/_HOWTO__SQL.md</a>", html)
        self.assertNotIn('class="wiki-link wiki-link-broken"', html)

    def test_note_view_markdown_resolves_parent_relative_path_wiki_link(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        source_dir = os.path.join(notes_root, "70-Make", "72-PC", "Linux")
        target_dir = os.path.join(notes_root, "60-Design", "64-GameDesign")
        source_id, source = self._create_note_record("linux note", source_dir, area="")
        target_id, _target = self._create_note_record("_INDEX__Game_Sanctuary", target_dir, area="")
        with open(source["full_path"], "w", encoding="utf-8") as handle:
            handle.write(
                "new link to index game sanctuary = [[../../../60-Design/64-GameDesign/_INDEX__Game_Sanctuary.md]]"
            )

        response = self._notes_test_app().test_client().get(f"/notes/view/{source_id}?format=markdown")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'href="/notes/view/{target_id}"', html)
        self.assertIn(">../../../60-Design/64-GameDesign/_INDEX__Game_Sanctuary.md</a>", html)
        self.assertNotIn('class="wiki-link wiki-link-broken"', html)

    def test_note_asset_route_resolves_notes_root_relative_attachment(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        note_dir = os.path.join(notes_root, "Projects")
        note_id, _created = self._create_note_record("asset note", note_dir, area="")
        attachment_dir = os.path.join(notes_root, "00-META", "08-Attachments")
        os.makedirs(attachment_dir, exist_ok=True)
        attachment_path = os.path.join(attachment_dir, "photo.png")
        with open(attachment_path, "wb") as handle:
            handle.write(b"fake image bytes")

        response = self._notes_test_app().test_client().get(
            f"/notes/asset/{note_id}/00-META/08-Attachments/photo.png"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), b"fake image bytes")

    def test_note_asset_route_resolves_bare_filename_from_legacy_image_folder(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        note_dir = os.path.join(notes_root, "Projects")
        note_id, _created = self._create_note_record("legacy asset note", note_dir, area="")
        legacy_dir = os.path.join(notes_root, "_img", "orig_lifepim")
        os.makedirs(legacy_dir, exist_ok=True)
        with open(os.path.join(legacy_dir, "bp_animal_Wolf.PNG"), "wb") as handle:
            handle.write(b"legacy image bytes")

        response = self._notes_test_app().test_client().get(
            f"/notes/asset/{note_id}/bp_animal_Wolf.PNG"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), b"legacy image bytes")

    def test_note_asset_route_prefers_current_folder_for_bare_filename(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        note_dir = os.path.join(notes_root, "Projects")
        note_id, _created = self._create_note_record("local asset note", note_dir, area="")
        attachment_dir = os.path.join(notes_root, "00-META", "08-Attachments")
        os.makedirs(attachment_dir, exist_ok=True)
        with open(os.path.join(note_dir, "photo.png"), "wb") as handle:
            handle.write(b"current folder image")
        with open(os.path.join(attachment_dir, "photo.png"), "wb") as handle:
            handle.write(b"attachment image")

        response = self._notes_test_app().test_client().get(f"/notes/asset/{note_id}/photo.png")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(), b"current folder image")

    def test_upload_note_image_saves_to_notes_root_attachment_folder(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        note_dir = os.path.join(notes_root, "Projects")
        note_id, _created = self._create_note_record("upload note", note_dir, area="")

        response = self._notes_test_app().test_client().post(
            f"/notes/api/upload-image/{note_id}",
            data={"image": (BytesIO(b"fake png bytes"), "My Photo.png")},
            content_type="multipart/form-data",
        )
        payload = response.get_json()
        saved_path = os.path.join(notes_root, "00-META", "08-Attachments", "My Photo.png")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(os.path.isfile(saved_path))
        self.assertEqual(payload["path"], "00-META/08-Attachments/My Photo.png")
        self.assertEqual(payload["markdown"], "![image](00-META/08-Attachments/My Photo.png)")

    def test_autosave_maintains_note_links_table_with_target_ids(self):
        note_dir = os.path.join(self.tmpdir.name, "wiki_save")
        source_id, source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("Saved Target", note_dir, area="")
        state = notes_routes._note_file_state(source["full_path"])

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        response = app.test_client().post(
            f"/notes/api/save/{source_id}",
            json={
                "content": f"Saved [[Saved Target|note:{target_id}]] link.",
                "base_mtime_ns": state["mtime_ns"],
                "base_hash": state["sha256"],
            },
        )
        row = self.conn.execute(
            "SELECT src_note_id, target_note_id, link_text, link_title FROM lp_note_links"
        ).fetchone()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["link_count"], 1)
        self.assertEqual(row["src_note_id"], source_id)
        self.assertEqual(row["target_note_id"], target_id)
        self.assertEqual(row["link_text"], f"[[Saved Target|note:{target_id}]]")
        self.assertEqual(row["link_title"], "Saved Target")

    def test_autosave_tracks_current_relative_path_wiki_note_links(self):
        note_dir = os.path.join(self.tmpdir.name, "DATA", "notes", "40-Dev", "42-HOWTO")
        target_dir = os.path.join(note_dir, "42-4-misc")
        source_id, source = self._create_note_record("source", note_dir, area="")
        target_id, _target = self._create_note_record("_HOWTO__SQL", target_dir, area="")
        state = notes_routes._note_file_state(source["full_path"])

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        response = app.test_client().post(
            f"/notes/api/save/{source_id}",
            json={
                "content": "[[42-4-misc/_HOWTO__SQL.md]]",
                "base_mtime_ns": state["mtime_ns"],
                "base_hash": state["sha256"],
            },
        )
        row = self.conn.execute(
            "SELECT src_note_id, target_note_id, link_text, link_title FROM lp_note_links"
        ).fetchone()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["link_count"], 1)
        self.assertEqual(row["src_note_id"], source_id)
        self.assertEqual(row["target_note_id"], target_id)
        self.assertEqual(row["link_text"], "[[42-4-misc/_HOWTO__SQL.md]]")
        self.assertEqual(row["link_title"], "42-4-misc/_HOWTO__SQL.md")

    def test_notes_table_view_uses_new_header_and_columns(self):
        note_dir = os.path.join(self.tmpdir.name, "notes_table_view")
        self._create_note_record("another table view", note_dir, area="")
        note_id, _created = self._create_note_record("table view", note_dir, area="")
        self._create_note_record("zeta table view", note_dir, area="")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(f"UPDATE {tbl['name']} SET color = ? WHERE id = ?", ("Blue", note_id))
        self.conn.commit()

        with patch.object(notes_routes, "_note_display_settings", return_value={"notes_per_page": 2}):
            response = self._notes_test_app().test_client().get("/notes/table?sort=title&dir=asc")
        html = response.get_data(as_text=True)
        note_row = html.split('data-record-title="table view.md"', 1)[1].split("</tr>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertIn("View as:", html)
        self.assertIn("Names only", html)
        self.assertIn("Sort by:", html)
        self.assertIn("Filename", html)
        self.assertIn("Controls", html)
        self.assertIn("notes-selection-root", html)
        self.assertNotIn('class="tabular-scroll"', html)
        self.assertNotIn("notes-list-results", html)
        self.assertNotIn("notes-list-page", html)
        self.assertIn('href="/notes/table?sort=title&amp;dir=desc"', html)
        self.assertIn('href="/notes/table?sort=size&amp;dir=asc"', html)
        self.assertIn('<option value="title" selected>Title</option>', html)
        self.assertIn('<option value="asc" selected>Asc</option>', html)
        self.assertRegex(html, r'</table>\s*<div class="pagination">')
        self.assertIn('class="note-list-dot"', note_row)
        self.assertNotIn(">Blue<", note_row)
        self.assertNotIn("<th>Folder ID</th>", html)

        with patch.object(notes_routes, "_note_display_settings", return_value={"notes_per_page": 10}):
            desc = self._notes_test_app().test_client().get("/notes/table?sort=title&dir=desc")
        desc_html = desc.get_data(as_text=True)
        self.assertLess(
            desc_html.index('data-record-title="zeta table view.md"'),
            desc_html.index('data-record-title="table view.md"'),
        )
        self.assertLess(
            desc_html.index('data-record-title="table view.md"'),
            desc_html.index('data-record-title="another table view.md"'),
        )

    def test_notes_names_and_preview_views_render(self):
        note_dir = os.path.join(self.tmpdir.name, "notes_other_views")
        self._create_note_record("other views", note_dir, area="")
        client = self._notes_test_app().test_client()

        names = client.get("/notes/names")
        preview = client.get("/notes/cards?mode=preview")

        self.assertEqual(names.status_code, 200)
        self.assertIn("note-names-list", names.get_data(as_text=True))
        self.assertEqual(preview.status_code, 200)
        preview_html = preview.get_data(as_text=True)
        self.assertIn("note-card", preview_html)
        self.assertIn("link-select", preview_html)

    def test_notes_sort_by_size_uses_numeric_order(self):
        note_dir = os.path.join(self.tmpdir.name, "numeric_size_sort")
        ids = []
        for title, size in (("ten", "10"), ("two", "2"), ("bad", "not-a-number")):
            note_id, _created = self._create_note_record(title, note_dir, area="")
            ids.append(note_id)
            tbl = common_utils.get_table_def("notes")
            self.conn.execute(f"UPDATE {tbl['name']} SET size = ? WHERE id = ?", (size, note_id))
        self.conn.commit()

        asc = notes_routes._fetch_notes(None, "size", "asc", include_derived=False)
        desc = notes_routes._fetch_notes(None, "size", "desc", include_derived=False)

        self.assertEqual([note["file_name"] for note in asc[:3]], ["two.md", "ten.md", "bad.md"])
        self.assertEqual([note["file_name"] for note in desc[:3]], ["ten.md", "two.md", "bad.md"])

    def test_note_folder_id_preserves_live_note_path_alias_on_update(self):
        area_id = "pers/health"
        note_dir = r"N:\duncan\LifePIM_Data\DATA\notes\10-Pers\12-Health"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "PERS",
                "group_name": "PERS",
                "area_name": "Health",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            area_id,
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
            "area": area_id,
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

        stale_filtered_notes = notes_routes._fetch_notes(area_id)
        stale_filtered_ids = {n.get("id") for n in stale_filtered_notes}
        self.assertIn(note_id, stale_filtered_ids)
        stale_derived = {n.get("id"): n.get("derived_area") for n in stale_filtered_notes}
        self.assertEqual(stale_derived[note_id], area_id)

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

        filtered_notes = notes_routes._fetch_notes(area_id)
        filtered_ids = {n.get("id") for n in filtered_notes}
        self.assertIn(note_id, filtered_ids)
        derived = {n.get("id"): n.get("derived_area") for n in filtered_notes}
        self.assertEqual(derived[note_id], area_id)

    def test_parent_area_includes_children_without_broad_leaf_leakage(self):
        root_dir = r"N:\duncan\LifePIM_Data\DATA\notes\50-Fun"
        games_dir = root_dir + r"\51-Games"
        travel_dir = root_dir + r"\56-Travel"
        areas = [
            ("fun.fun.fun", "FUN", "FUN", "Fun", root_dir),
            ("fun/games", "FUN", "FUN", "Games", games_dir),
            ("fun/sport", "FUN", "FUN", "Sport", root_dir),
            ("fun/travel", "FUN", "FUN", "Travel", root_dir),
        ]
        for area_id, tab, group_name, area_name, folder_path in areas:
            areas_mod.area_upsert(
                {
                    "area_id": area_id,
                    "tab": tab,
                    "group_name": group_name,
                    "area_name": area_name,
                },
                conn=self.conn,
            )
            areas_mod.area_folder_add(
                area_id,
                folder_path,
                folder_role="default",
                is_write_enabled=1,
                conn=self.conn,
            )

        tbl = common_utils.get_table_def("notes")

        def add_note(file_name, folder_path, area_id):
            values_map = {
                "file_name": file_name,
                "path": folder_path,
                "folder_id": "",
                "size": "1",
                "date_modified": "2026-07-09 16:38:25",
                "area": area_id,
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

    def test_note_folder_full_sync_indexes_hierarchy(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_index")
        os.makedirs(os.path.join(notes_root, "A"), exist_ok=True)
        os.makedirs(os.path.join(notes_root, "B", "C"), exist_ok=True)

        result = notes_routes.full_sync_note_folders([notes_root])

        self.assertEqual(result["folders"], 4)
        rows = {
            row["relative_path"]: row
            for row in self.conn.execute(
                "SELECT id, parent_id, relative_path, is_missing FROM lp_note_folders WHERE root_path = ?",
                (notes_routes._normalize_note_path(notes_root),),
            ).fetchall()
        }
        self.assertEqual(set(rows.keys()), {"", "A", "B", "B/C"})
        self.assertIsNone(rows[""]["parent_id"])
        self.assertEqual(rows["B/C"]["parent_id"], rows["B"]["id"])
        self.assertEqual(rows["B/C"]["is_missing"], 0)

    def test_note_folder_tree_reconciles_notes_once_for_subtree(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_single_reconcile")
        os.makedirs(os.path.join(notes_root, "A", "B"), exist_ok=True)
        calls = []
        original_sync = notes_routes._sync_note_rows

        def tracking_sync(*args, **kwargs):
            calls.append((args, kwargs))
            return original_sync(*args, **kwargs)

        with patch.object(notes_routes, "_sync_note_rows", side_effect=tracking_sync):
            notes_routes.add_note_folder_tree(notes_root, notes_root)

        self.assertEqual(len(calls), 1)
        self.assertEqual(notes_routes._normalize_note_path(calls[0][0][0]), notes_routes._normalize_note_path(notes_root))
        self.assertTrue(calls[0][1].get("recursive"))

    def test_note_folder_relative_path_handles_unrelated_windows_drives(self):
        rel_path = notes_routes._note_folder_rel_path(r"N:\Notes", r"D:\Other")

        self.assertEqual(rel_path, "")

    def test_notes_root_from_path_supports_lan_user_notes_root(self):
        root = notes_routes._notes_root_from_path(
            r"N:\duncan\LifePIM_Data\DATA\lan_users\mmob\notes\40-Dev\42-HOWTO"
        )

        self.assertEqual(root, r"N:\duncan\LifePIM_Data\DATA\lan_users\mmob\notes")

    def test_notes_root_path_derives_lan_user_notes_root(self):
        tbl = common_utils.get_table_def("notes")
        note_path = r"N:\duncan\LifePIM_Data\DATA\lan_users\mmob\notes\40-Dev"
        values_map = {
            "file_name": "lan.md",
            "path": note_path,
            "folder_id": "",
            "size": "1",
            "date_modified": "2026-01-01 00:00:00",
            "area": "",
        }
        values = [values_map.get(col, "") for col in tbl["col_list"]]
        data.add_record(self.conn, tbl["name"], tbl["col_list"], values)

        self.assertEqual(notes_routes._notes_root_path(), r"N:\duncan\LifePIM_Data\DATA\lan_users\mmob\notes")

    def test_note_folder_quick_sync_unchanged_does_not_enumerate(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_no_changes")
        os.makedirs(os.path.join(notes_root, "A"), exist_ok=True)
        notes_routes.full_sync_note_folders([notes_root])

        with patch.object(notes_routes.os, "scandir", side_effect=AssertionError("unexpected scandir")):
            result = notes_routes.check_note_folders([notes_root])

        self.assertEqual(result["dirty"], 0)
        self.assertEqual(result["refreshed"], 0)

    def test_note_folder_quick_sync_adds_new_file_from_dirty_folder(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_new_file")
        folder_a = os.path.join(notes_root, "A")
        os.makedirs(folder_a, exist_ok=True)
        notes_routes.full_sync_note_folders([notes_root])

        with open(os.path.join(folder_a, "new.md"), "w", encoding="utf-8") as handle:
            handle.write("new note")
        self._bump_dir_mtime(folder_a)
        result = notes_routes.check_note_folders([notes_root])

        self.assertEqual(result["dirty"], 1)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT file_name, path FROM {tbl['name']} WHERE file_name = ?", ("new.md",)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["path"], notes_routes._normalize_note_path(folder_a))

    def test_note_folder_quick_sync_preserves_note_id_on_same_folder_rename(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_rename")
        folder_a = os.path.join(notes_root, "A")
        os.makedirs(folder_a, exist_ok=True)
        old_path = os.path.join(folder_a, "old.md")
        with open(old_path, "w", encoding="utf-8") as handle:
            handle.write("same content")
        notes_routes.full_sync_note_folders([notes_root])
        tbl = common_utils.get_table_def("notes")
        note_id = self.conn.execute(f"SELECT id FROM {tbl['name']} WHERE file_name = ?", ("old.md",)).fetchone()["id"]

        os.rename(old_path, os.path.join(folder_a, "new.md"))
        self._bump_dir_mtime(folder_a)
        result = notes_routes.check_note_folders([notes_root])

        self.assertEqual(result["dirty"], 1)
        row = self.conn.execute(f"SELECT id, file_name FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["file_name"], "new.md")
        count = self.conn.execute(f"SELECT COUNT(1) AS cnt FROM {tbl['name']}").fetchone()["cnt"]
        self.assertEqual(count, 1)

    def test_recursive_note_sync_preserves_note_id_on_same_folder_rename(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_recursive_rename")
        folder_a = os.path.join(notes_root, "A")
        os.makedirs(folder_a, exist_ok=True)
        old_path = os.path.join(folder_a, "old.md")
        with open(old_path, "w", encoding="utf-8") as handle:
            handle.write("same content")
        notes_routes.full_sync_note_folders([notes_root])
        tbl = common_utils.get_table_def("notes")
        note_id = self.conn.execute(f"SELECT id FROM {tbl['name']} WHERE file_name = ?", ("old.md",)).fetchone()["id"]

        os.rename(old_path, os.path.join(folder_a, "new.md"))
        result = notes_routes.full_sync_note_folders([notes_root])

        self.assertEqual(result["notes"], 1)
        rows = self.conn.execute(f"SELECT id, file_name FROM {tbl['name']}").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], note_id)
        self.assertEqual(rows[0]["file_name"], "new.md")

    def test_note_folder_quick_sync_discovers_new_subtree_once(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_new_subtree")
        folder_a = os.path.join(notes_root, "A")
        os.makedirs(folder_a, exist_ok=True)
        notes_routes.full_sync_note_folders([notes_root])

        new_folder = os.path.join(folder_a, "NewFolder")
        nested = os.path.join(new_folder, "Nested")
        os.makedirs(nested, exist_ok=True)
        with open(os.path.join(new_folder, "one.md"), "w", encoding="utf-8") as handle:
            handle.write("one")
        with open(os.path.join(nested, "two.md"), "w", encoding="utf-8") as handle:
            handle.write("two")
        self._bump_dir_mtime(folder_a)
        result = notes_routes.check_note_folders([notes_root])

        self.assertEqual(result["dirty"], 1)
        rels = {
            row["relative_path"]
            for row in self.conn.execute(
                "SELECT relative_path FROM lp_note_folders WHERE root_path = ? AND is_missing = 0",
                (notes_routes._normalize_note_path(notes_root),),
            ).fetchall()
        }
        self.assertIn("A/NewFolder", rels)
        self.assertIn("A/NewFolder/Nested", rels)
        tbl = common_utils.get_table_def("notes")
        count = self.conn.execute(
            f"SELECT COUNT(1) AS cnt FROM {tbl['name']} WHERE file_name IN ('one.md', 'two.md')"
        ).fetchone()["cnt"]
        self.assertEqual(count, 2)

    def test_note_folder_quick_sync_marks_deleted_subtree_missing(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_deleted_subtree")
        folder_a = os.path.join(notes_root, "A")
        old_folder = os.path.join(folder_a, "Old")
        os.makedirs(old_folder, exist_ok=True)
        notes_routes.full_sync_note_folders([notes_root])

        os.rmdir(old_folder)
        self._bump_dir_mtime(folder_a)
        result = notes_routes.check_note_folders([notes_root])

        self.assertEqual(result["dirty"], 1)
        row = self.conn.execute(
            "SELECT is_missing FROM lp_note_folders WHERE root_path = ? AND relative_path = ?",
            (notes_routes._normalize_note_path(notes_root), "A/Old"),
        ).fetchone()
        self.assertEqual(row["is_missing"], 1)

    def test_note_folder_quick_sync_unavailable_root_is_non_destructive(self):
        notes_root = os.path.join(self.tmpdir.name, "folder_unavailable")
        os.makedirs(os.path.join(notes_root, "A"), exist_ok=True)
        notes_routes.full_sync_note_folders([notes_root])

        os.rename(notes_root, notes_root + "_offline")
        try:
            result = notes_routes.check_note_folders([notes_root])
        finally:
            os.rename(notes_root + "_offline", notes_root)

        self.assertEqual(result["checked"], 0)
        missing = self.conn.execute(
            "SELECT COUNT(1) AS cnt FROM lp_note_folders WHERE root_path = ? AND is_missing = 1",
            (notes_routes._normalize_note_path(notes_root),),
        ).fetchone()["cnt"]
        self.assertEqual(missing, 0)

    def test_notes_count_without_area_does_not_run_global_folder_check(self):
        app = self._notes_test_app()
        with app.test_request_context("/notes"):
            with patch.object(notes_routes, "check_note_folders", side_effect=AssertionError("global check")):
                with patch.object(notes_routes, "_check_note_folder_paths", side_effect=AssertionError("visible check")):
                    notes_routes._count_notes(None, None)

    def test_notes_count_with_area_checks_only_area_folder(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        area_dir = os.path.join(notes_root, "Games")
        other_dir = os.path.join(notes_root, "Other")
        os.makedirs(area_dir, exist_ok=True)
        os.makedirs(other_dir, exist_ok=True)
        areas_mod.area_upsert(
            {
                "area_id": "fun/games",
                "tab": "FUN",
                "group_name": "FUN",
                "area_name": "Games",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add("fun/games", area_dir, folder_role="default", is_write_enabled=1, conn=self.conn)
        app = self._notes_test_app()

        captured = []
        with app.test_request_context("/notes?area=fun/games"):
            with patch.object(notes_routes, "_check_note_folder_paths", side_effect=lambda paths: captured.extend(paths) or {"checked": 0, "dirty": 0, "missing": 0, "refreshed": 0, "new_subtrees": 0, "notes": 0}):
                notes_routes._count_notes("fun/games", None)

        self.assertEqual(captured, [notes_routes._normalize_note_path(area_dir)])

    def test_notes_count_with_non_note_area_folder_skips_folder_check(self):
        area_dir = os.path.join(self.tmpdir.name, "Movies")
        os.makedirs(area_dir, exist_ok=True)
        areas_mod.area_upsert(
            {
                "area_id": "media/movies",
                "tab": "MEDIA",
                "group_name": "MEDIA",
                "area_name": "Movies",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add("media/movies", area_dir, folder_role="default", is_write_enabled=1, conn=self.conn)
        app = self._notes_test_app()

        with app.test_request_context("/notes?area=media/movies"):
            with patch.object(notes_routes, "_check_note_folder_paths", side_effect=AssertionError("visible check")):
                notes_routes._count_notes("media/movies", None)

    def test_configured_note_roots_ignore_non_note_area_folders(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        area_dir = os.path.join(notes_root, "40-Dev")
        non_note_dir = os.path.join(self.tmpdir.name, "Movies")
        os.makedirs(area_dir, exist_ok=True)
        os.makedirs(non_note_dir, exist_ok=True)
        areas_mod.area_upsert(
            {
                "area_id": "dev/howto",
                "tab": "DEV",
                "group_name": "DEV",
                "area_name": "Howto",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add("dev/howto", area_dir, folder_role="default", is_write_enabled=1, conn=self.conn)
        areas_mod.area_folder_add("dev/howto", non_note_dir, folder_role="include", is_write_enabled=0, conn=self.conn)

        roots = notes_routes._configured_note_roots(create_dirs=False)

        self.assertIn(notes_routes._normalize_note_path(notes_root), roots)
        self.assertNotIn(notes_routes._normalize_note_path(non_note_dir), roots)

    def test_auto_check_prunes_invalid_folder_index_roots_without_scan(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        invalid_root = os.path.join(self.tmpdir.name, "Movies")
        os.makedirs(notes_root, exist_ok=True)
        os.makedirs(invalid_root, exist_ok=True)
        notes_routes._ensure_note_folders_schema(self.conn)
        notes_routes._upsert_note_folder_index(self.conn, notes_root, notes_root)
        notes_routes._upsert_note_folder_index(self.conn, invalid_root, invalid_root)
        self.conn.commit()

        with patch.object(notes_routes, "_check_note_folder_paths", side_effect=AssertionError("visible check")):
            result = notes_routes._auto_check_visible_note_folders(None, None)

        self.assertEqual(result["checked"], 0)
        roots = {
            row["root_path"]
            for row in self.conn.execute("SELECT DISTINCT root_path FROM lp_note_folders").fetchall()
        }
        self.assertIn(notes_routes._normalize_note_path(notes_root), roots)
        self.assertNotIn(notes_routes._normalize_note_path(invalid_root), roots)

    def test_filtered_area_header_uses_scoped_sync_label_and_fields(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        food_dir = os.path.join(notes_root, "Food")
        areas_mod.area_upsert(
            {
                "area_id": "food",
                "tab": "HOME",
                "group_name": "HOME",
                "area_name": "Food",
            },
            conn=self.conn,
        )
        self._create_note_record("recipe", food_dir, area="food")

        response = self._notes_test_app().test_client().get("/notes/table?area=food")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<input type="hidden" name="area" value="food">', html)
        self.assertIn('<button type="submit">Sync</button>', html)
        self.assertNotIn('<button type="submit">Full Sync</button>', html)

    def test_area_folder_inset_shows_detected_note_folders_without_links(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        food_dir = os.path.join(notes_root, "Food")
        areas_mod.area_upsert(
            {
                "area_id": "food",
                "tab": "HOME",
                "group_name": "HOME",
                "area_name": "Food",
            },
            conn=self.conn,
        )
        for idx in range(3):
            self._create_note_record(f"recipe {idx}", food_dir, area="food")

        response = self._notes_test_app().test_client().get("/notes/table?area=food")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Detected from notes", html)
        self.assertIn(notes_routes._normalize_note_path(food_dir), html)
        self.assertNotIn("No folders linked to this area.", html)

    def test_unfiltered_header_keeps_full_sync_label(self):
        response = self._notes_test_app().test_client().get("/notes/table")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('<button type="submit">Full Sync</button>', html)

    def test_sync_route_filtered_area_syncs_only_matching_note_folders(self):
        notes_root = os.path.join(self.tmpdir.name, "DATA", "notes")
        food_dir = os.path.join(notes_root, "Food")
        other_dir = os.path.join(notes_root, "Other")
        for idx in range(3):
            self._create_note_record(f"recipe {idx}", food_dir, area="food")
        self._create_note_record("other", other_dir, area="other")

        captured = []
        fallback_areas = []

        def fake_sync(paths, fallback_area=""):
            captured.extend(paths)
            fallback_areas.append(fallback_area)
            return {"paths": len(paths), "folders": len(paths), "notes": 3, "missing": 0}

        app = self._notes_test_app()
        with patch.object(notes_routes, "full_sync_note_folders", side_effect=AssertionError("full sync")):
            with patch.object(notes_routes, "sync_note_folders", side_effect=fake_sync):
                response = app.test_client().post(
                    "/notes/sync",
                    data={"area": "food", "next": "/notes/table?area=food"},
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(captured, [notes_routes._normalize_note_path(food_dir)])
        self.assertEqual(fallback_areas, ["food"])

    def test_sync_route_unfiltered_uses_full_sync(self):
        calls = []

        def fake_full_sync():
            calls.append(True)
            return {"roots": 1, "folders": 2, "notes": 3}

        app = self._notes_test_app()
        with patch.object(notes_routes, "sync_note_folders", side_effect=AssertionError("scoped sync")):
            with patch.object(notes_routes, "full_sync_note_folders", side_effect=fake_full_sync):
                response = app.test_client().post("/notes/sync", data={"next": "/notes/table"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(calls, [True])

    def test_notebook_available_notes_hide_missing_files_after_external_rename(self):
        note_dir = os.path.join(self.tmpdir.name, "DATA", "notes", "Notebook")
        old_id, old_created = self._create_note_record("old name", note_dir, area="")
        new_id, _new_created = self._create_note_record("new name", note_dir, area="")
        os.remove(old_created["full_path"])

        app = self._notes_test_app()
        with app.test_request_context("/notes/notebooks"):
            options = notes_routes._note_source_options(None, [], query="")

        option_ids = {option["id"] for option in options}
        self.assertNotIn(old_id, option_ids)
        self.assertIn(new_id, option_ids)

    def test_notebook_add_note_rejects_missing_file(self):
        note_dir = os.path.join(self.tmpdir.name, "DATA", "notes", "Notebook")
        note_id, created = self._create_note_record("missing notebook source", note_dir, area="")
        os.remove(created["full_path"])
        projects_mod.ensure_projects_schema(self.conn)
        collections_mod.ensure_collections_schema(self.conn)
        collection_id = collections_mod.create_collection(
            {"collection_name": "Missing Source Notebook", "collection_domain": "notes", "collection_type": "notebook"},
            conn=self.conn,
        )

        response = self._notes_test_app().test_client().post(
            "/notes/notebooks",
            data={"action": "add_note", "collection_id": str(collection_id), "note_id": str(note_id)},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        count = self.conn.execute("SELECT COUNT(1) AS cnt FROM lp_collection_item").fetchone()["cnt"]
        self.assertEqual(count, 0)

    def test_sync_note_rows_uses_area_folder_fallback_area(self):
        notes_dir = os.path.join(self.tmpdir.name, "sync_area")
        os.makedirs(notes_dir, exist_ok=True)
        note_path = os.path.join(notes_dir, "area-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("area note")

        result = notes_routes._sync_note_rows(notes_dir, fallback_area="fun/games")

        self.assertEqual(result["inserted"], 1)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT area FROM {tbl['name']} WHERE file_name = ?", ("area-note.md",)).fetchone()
        self.assertEqual(row["area"], "fun/games")

    def test_sync_note_rows_uses_area_folder_mapping_fallback(self):
        notes_root = os.path.join(self.tmpdir.name, "sync_area_root")
        area_dir = os.path.join(notes_root, "Games")
        os.makedirs(area_dir, exist_ok=True)
        note_path = os.path.join(area_dir, "mapped-note.md")
        with open(note_path, "w", encoding="utf-8") as handle:
            handle.write("mapped area note")
        areas_mod.area_upsert(
            {
                "area_id": "fun/games",
                "tab": "FUN",
                "group_name": "FUN",
                "area_name": "Games",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            "fun/games",
            area_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )

        result = notes_routes._sync_note_rows(notes_root)

        self.assertEqual(result["inserted"], 1)
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT area FROM {tbl['name']} WHERE file_name = ?", ("mapped-note.md",)).fetchone()
        self.assertEqual(row["area"], "fun/games")

    def test_materialize_note_areas_backfills_blank_area_from_mapping(self):
        area_dir = os.path.join(self.tmpdir.name, "materialize_area", "Games")
        os.makedirs(area_dir, exist_ok=True)
        areas_mod.area_upsert(
            {
                "area_id": "fun/games",
                "tab": "FUN",
                "group_name": "FUN",
                "area_name": "Games",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            "fun/games",
            area_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        tbl = common_utils.get_table_def("notes")
        values_map = {
            "file_name": "blank-area.md",
            "path": notes_routes._normalize_note_path(area_dir),
            "folder_id": "",
            "size": "1",
            "date_modified": "2026-07-09 16:38:25",
            "area": "",
        }
        note_id = data.add_record(
            self.conn,
            tbl["name"],
            tbl["col_list"],
            [values_map.get(col, "") for col in tbl["col_list"]],
        )

        result = notes_routes.materialize_note_areas(self.conn)

        self.assertEqual(result["updated"], 1)
        row = self.conn.execute(f"SELECT area FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["area"], "fun/games")
        filtered_ids = {note.get("id") for note in notes_routes._fetch_notes("fun/games")}
        self.assertIn(note_id, filtered_ids)

    def test_rename_note_updates_file_and_metadata(self):
        note_dir = os.path.join(self.tmpdir.name, "rename_note")
        note_id, created = self._create_note_record("old title", note_dir, area="pers/health")

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
        self.assertNotIn("title:", text)
        self.assertIn("# new title", text)

    def test_move_note_updates_area_folder_and_metadata(self):
        source_dir = os.path.join(self.tmpdir.name, "move_source")
        target_dir = os.path.join(self.tmpdir.name, "move_target")
        area_id = "fun/games"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "FUN",
                "group_name": "FUN",
                "area_name": "Games",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(
            area_id,
            target_dir,
            folder_role="default",
            is_write_enabled=1,
            conn=self.conn,
        )
        note_id, created = self._create_note_record("move me", source_dir, area="")

        moved_path = notes_routes._move_note_to_area(note_id, area_id)
        self.assertFalse(os.path.exists(created["full_path"]))
        self.assertTrue(os.path.exists(moved_path))
        self.assertEqual(os.path.dirname(moved_path), notes_routes._normalize_note_path(target_dir))

        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT file_name, path, area FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["file_name"], os.path.basename(moved_path))
        self.assertEqual(row["path"], notes_routes._normalize_note_path(target_dir))
        self.assertEqual(row["area"], area_id)

    def test_assign_note_area_updates_metadata_without_folder_mapping(self):
        note_dir = os.path.join(self.tmpdir.name, "assign_source")
        area_id = "make/new"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "MAKE",
                "group_name": "MAKE",
                "area_name": "New",
            },
            conn=self.conn,
        )
        note_id, created = self._create_note_record("assign me", note_dir, area="")

        ok = notes_routes._assign_note_area(note_id, area_id)

        self.assertTrue(ok)
        self.assertTrue(os.path.exists(created["full_path"]))
        tbl = common_utils.get_table_def("notes")
        row = self.conn.execute(f"SELECT file_name, path, area FROM {tbl['name']} WHERE id = ?", (note_id,)).fetchone()
        self.assertEqual(row["file_name"], "assign me.md")
        self.assertEqual(row["path"], notes_routes._normalize_note_path(note_dir))
        self.assertEqual(row["area"], area_id)
        with open(created["full_path"], "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("area: make/new", text)
        filtered_ids = {note.get("id") for note in notes_routes._fetch_notes(area_id)}
        self.assertIn(note_id, filtered_ids)

    def test_archive_delete_moves_file_and_removes_db_row(self):
        note_dir = os.path.join(self.tmpdir.name, "delete_note")
        note_id, created = self._create_note_record("delete me", note_dir, area="fun/games")

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
        note_id, _ = self._create_note_record("note_creation_test_delete", unmapped_dir, area="")

        tbl = common_utils.get_table_def("notes")
        data.delete_record(self.conn, tbl["name"], note_id)

        unmapped_notes = notes_routes._fetch_notes("unmapped")
        unmapped_ids = {n.get("id") for n in unmapped_notes}
        self.assertNotIn(note_id, unmapped_ids)

    def test_undo_restores_deleted_note(self):
        unmapped_dir = os.path.join(self.tmpdir.name, "unmapped_undo")
        note_id, _ = self._create_note_record("note_creation_test_undo", unmapped_dir, area="")

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
        note_id, created = self._create_note_record("note_creation_test_stale", note_dir, area="")
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
        note_id, created = self._create_note_record("note_creation_test_timestamp", note_dir, area="")
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

    def test_note_template_and_important_defaults_and_save_reload(self):
        note_dir = os.path.join(self.tmpdir.name, "metadata_flags")
        note_id, created = self._create_note_record("metadata flags", note_dir, area="")

        note, _tbl = notes_routes._get_note_record(note_id)
        self.assertEqual(note["is_template"], "false")
        self.assertEqual(note["is_important"], "false")
        with open(created["full_path"], "r", encoding="utf-8") as handle:
            self.assertNotEqual(handle.read().splitlines()[0], "---")

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        resp = app.test_client().post(
            f"/notes/api/save/{note_id}",
            json={
                "content": "# metadata flags\n",
                "metadata": {"is_template": True, "is_important": True},
            },
        )

        self.assertEqual(resp.status_code, 200)
        reloaded, tbl = notes_routes._get_note_record(note_id)
        self.assertEqual(reloaded["is_template"], "true")
        self.assertEqual(reloaded["is_important"], "true")
        row = self.conn.execute(
            f"SELECT is_template, is_important FROM {tbl['name']} WHERE id = ?",
            (note_id,),
        ).fetchone()
        self.assertEqual(row["is_template"], "true")
        self.assertEqual(row["is_important"], "true")
        with open(created["full_path"], "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("is_template:", text)
        self.assertNotIn("is_important:", text)

    def test_template_filter_returns_only_template_notes(self):
        note_dir = os.path.join(self.tmpdir.name, "template_filter")
        note_a_id, _ = self._create_note_record("Note A", note_dir, area="")
        note_b_id, _ = self._create_note_record("Note B", note_dir, area="")
        note_c_id, _ = self._create_note_record("Note C", note_dir, area="")
        tbl = common_utils.get_table_def("notes")
        self.conn.execute(f"UPDATE {tbl['name']} SET title = file_name")
        self.conn.execute(f"UPDATE {tbl['name']} SET is_template = 'true' WHERE id IN (?, ?)", (note_b_id, note_c_id))
        self.conn.commit()

        templates = notes_routes._fetch_notes("unmapped", "title", "asc", template_filter="templates")
        normal = notes_routes._fetch_notes("unmapped", "title", "asc")

        self.assertEqual({row["id"] for row in templates}, {note_b_id, note_c_id})
        self.assertEqual({row["id"] for row in normal}, {note_a_id})

    def test_all_areas_request_is_unfiltered_for_notes(self):
        note_dir = os.path.join(self.tmpdir.name, "all_areas_filter")
        note_id, _ = self._create_note_record("All Areas Visible", note_dir, area="family")

        normalized = notes_routes._normalize_area(common_utils.normalize_area_param("All Areas"))
        notes = notes_routes._fetch_notes(normalized, "date_modified", "desc")

        self.assertIsNone(normalized)
        self.assertIn(note_id, {row["id"] for row in notes})

    def test_render_note_template_replaces_known_variables_only(self):
        fixed = datetime(2026, 8, 20, 15, 54)

        rendered = notes_routes.render_note_template("{{date}} {{time}} {{something_else}}", now=fixed)

        self.assertEqual(rendered, "2026-08-20 15:54 {{something_else}}")

    def test_create_from_template_copies_body_and_resets_flags(self):
        note_dir = os.path.join(self.tmpdir.name, "template_copy")
        area_id = "area.templates"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "TEST",
                "group_name": "Test",
                "area_name": "Templates",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(area_id, note_dir, folder_role="default", is_write_enabled=1, conn=self.conn)
        template = notes_routes._create_note_record(
            "Journal Entry",
            area_id=area_id,
            path_prefix=note_dir,
            body_content="Date: {{date}}\nTime: {{time}}\n{{unknown}}\n",
            is_template=True,
            is_important=True,
        )
        with open(template["full_path"], "r", encoding="utf-8") as handle:
            source_before = handle.read()
        original_render = notes_routes.render_note_template

        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)
        with patch(
            "modules.notes.routes.render_note_template",
            side_effect=lambda content: original_render(content, now=datetime(2026, 8, 20, 15, 54)),
        ):
            resp = app.test_client().post(
                "/notes/api/create-from-template",
                json={
                    "template_id": template["note_id"],
                    "title": "Today",
                    "area_id": area_id,
                    "path_prefix": note_dir,
                },
            )

        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()
        self.assertNotEqual(result["note_id"], template["note_id"])
        with open(template["full_path"], "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), source_before)
        with open(result["full_path"], "r", encoding="utf-8") as handle:
            copied = handle.read()
        self.assertIn("Date: 2026-08-20", copied)
        self.assertIn("Time: 15:54", copied)
        self.assertIn("{{unknown}}", copied)
        self.assertNotIn("is_template:", copied)
        self.assertNotIn("is_important:", copied)
        new_note, _tbl = notes_routes._get_note_record(result["note_id"])
        self.assertEqual(new_note["is_template"], "false")
        self.assertEqual(new_note["is_important"], "false")

    def test_important_notes_sort_before_normal_notes(self):
        rows = [
            {"title": "Bravo", "is_important": "false"},
            {"title": "Zulu", "is_important": "true"},
            {"title": "Alpha", "is_important": "false"},
            {"title": "Charlie", "is_important": "true"},
        ]

        sorted_rows = notes_routes._sort_notes(rows, "title", "asc")

        self.assertEqual([row["title"] for row in sorted_rows], ["Charlie", "Zulu", "Alpha", "Bravo"])

    def test_create_note_api_accepts_clipboard_plain_text_content(self):
        note_dir = os.path.join(self.tmpdir.name, "clipboard_note")
        area_id = "area.clipboard"
        areas_mod.area_upsert(
            {
                "area_id": area_id,
                "tab": "TEST",
                "group_name": "Test",
                "area_name": "Clipboard",
            },
            conn=self.conn,
        )
        areas_mod.area_folder_add(area_id, note_dir, folder_role="default", is_write_enabled=1, conn=self.conn)
        app = Flask(__name__)
        app.register_blueprint(notes_routes.notes_bp)

        resp = app.test_client().post(
            "/notes/api/create-note",
            json={
                "title": "Clipboard Note",
                "area_id": area_id,
                "path_prefix": note_dir,
                "content": "plain clipboard text",
            },
        )

        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()
        with open(result["full_path"], "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("plain clipboard text", text)
        created, _tbl = notes_routes._get_note_record(result["note_id"])
        self.assertEqual(created["is_template"], "false")
        self.assertEqual(created["is_important"], "false")


if __name__ == "__main__":
    unittest.main()
