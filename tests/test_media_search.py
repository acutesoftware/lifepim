import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import urlparse, parse_qs

from flask import Flask

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import data
from common.media_schema import ensure_media_schema
from modules.media import routes as media_routes


class TestMediaSearch(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        ensure_media_schema(self.conn)

    def tearDown(self):
        data.conn = self._old_conn
        self.conn.close()

    def _insert_media(self, filename, ext, media_type="image", path=None):
        path = path or os.path.join("C:\\photos", filename)
        self.conn.execute(
            "INSERT INTO lp_media "
            "(path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (path, filename, ext, media_type, 100, "2026-01-01T00:00:00Z", None, filename),
        )
        self.conn.commit()

    def _search_filenames(self, query):
        joins, where, params = media_routes._build_media_filters(
            "all",
            None,
            None,
            False,
            "",
            [],
            media_routes.parse_search_terms(query),
            None,
        )
        rows = media_routes._fetch_media(self.conn, joins, where, params, "filename")
        return [row["filename"] for row in rows]

    def test_unquoted_words_must_all_match_anywhere_in_media_record(self):
        self._insert_media("glenelg_walk.jpg", "jpg")
        self._insert_media("glenelg_sunset.jpg", "jpg")
        self._insert_media("walk_beach.png", "png")

        self.assertEqual(self._search_filenames("glenelg walk"), ["glenelg_walk.jpg"])

    def test_unquoted_words_can_match_different_media_fields(self):
        self._insert_media("glenelg_walk.jpg", "jpg")
        self._insert_media("glenelg_sunset.jpg", "jpg")
        self._insert_media("walk_beach.png", "png")

        self.assertEqual(
            self._search_filenames("JPG glenelg"),
            ["glenelg_sunset.jpg", "glenelg_walk.jpg"],
        )

    def test_quoted_words_still_search_as_a_phrase(self):
        self._insert_media("glenelg_walk.jpg", "jpg")
        self._insert_media("glenelg walk.jpg", "jpg")

        self.assertEqual(self._search_filenames('"glenelg walk"'), ["glenelg walk.jpg"])

    def test_timeline_years_support_search_terms(self):
        self._insert_media("christmas_2023.jpg", "jpg", path="C:\\photos\\2023\\christmas_2023.jpg")

        joins, where, params = media_routes._build_media_filters(
            "all",
            None,
            None,
            False,
            "",
            [],
            media_routes.parse_search_terms("christmas 2023"),
            None,
        )
        years = media_routes._fetch_timeline_years(self.conn, joins, where, params)

        self.assertEqual(years, [{"yr": "2026", "cnt": 1}])

    def test_media_player_filter_keeps_audio_files_only(self):
        self._insert_media("song_one.mp3", "mp3", media_type="audio", path="C:\\music\\song_one.mp3")
        self._insert_media("song_two.m4a", ".m4a", media_type="file", path="C:\\music\\song_two.m4a")
        self._insert_media("photo.jpg", "jpg", media_type="image", path="C:\\photos\\photo.jpg")
        self._insert_media("clip.mp4", "mp4", media_type="video", path="C:\\videos\\clip.mp4")

        joins, where, params = media_routes._build_media_filters(
            "all",
            None,
            None,
            False,
            "",
            [],
            [],
            None,
        )
        media_routes._add_audio_media_filter(where, params)
        rows = media_routes._fetch_media(self.conn, joins, where, params, "filename")

        self.assertEqual([row["filename"] for row in rows], ["song_one.mp3", "song_two.m4a"])


class TestMediaExplorerPagination(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        self._old_schema_ready = media_routes._MEDIA_SCHEMA_READY
        data.conn = self.conn
        media_routes._MEDIA_SCHEMA_READY = False
        ensure_media_schema(self.conn)

        template_folder = os.path.join(root_folder, "templates")
        self.app = Flask(__name__, template_folder=template_folder)
        self.app.register_blueprint(media_routes.media_bp)
        self.app.add_url_rule("/settings", endpoint="admin.settings_route", view_func=lambda: "")
        self.app.add_url_rule("/help", endpoint="help_route", view_func=lambda: "")
        self.app.add_url_rule("/history", endpoint="admin.user_history_route", view_func=lambda: "")
        self.app.add_url_rule("/search", endpoint="search_route", view_func=lambda: "")
        self.app.config["TESTING"] = True

    def tearDown(self):
        data.conn = self._old_conn
        media_routes._MEDIA_SCHEMA_READY = self._old_schema_ready
        self.conn.close()

    def _insert_media(self, filename, taken_utc, ext="jpg", media_type="image"):
        cur = self.conn.execute(
            "INSERT INTO lp_media "
            "(path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (os.path.join("C:\\photos", filename), filename, ext, media_type, 100, taken_utc, None, filename),
        )
        media_id = cur.lastrowid
        self.conn.execute(
            "INSERT INTO lp_media_meta (media_id, taken_utc) VALUES (?, ?)",
            (media_id, taken_utc),
        )
        return media_id

    def _insert_event(self, media_id, start_utc):
        cur = self.conn.execute(
            "INSERT INTO lp_events (title, start_utc, end_utc, event_source, created_utc) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"Event {media_id}", start_utc, start_utc, "test", start_utc),
        )
        event_id = cur.lastrowid
        self.conn.execute(
            "INSERT INTO lp_event_items (event_id, media_id, confidence) VALUES (?, ?, ?)",
            (event_id, media_id, 1.0),
        )
        return event_id

    def _add_event_item(self, event_id, media_id):
        self.conn.execute(
            "INSERT OR IGNORE INTO lp_event_items (event_id, media_id, confidence) VALUES (?, ?, ?)",
            (event_id, media_id, 1.0),
        )

    def test_item_pagination_uses_item_page_not_sidebar_event_page(self):
        base = datetime(2026, 1, 1, 12, 0, 0)
        for idx in range(55):
            stamp = (base + timedelta(minutes=idx)).strftime("%Y-%m-%dT%H:%M:%SZ")
            media_id = self._insert_media(f"photo_{idx:03}.jpg", stamp)
            self._insert_event(media_id, stamp)
        self.conn.commit()

        with self.app.test_client() as client:
            response = client.get("/media/?view=all&view_mode=filmstrip&sort=taken_desc&group=month&nav_event_page=2")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("page=2", html)

        after_items = html.split('<form class="media-actions-form"', 1)[1]
        item_page_links = []
        for part in after_items.split('href="')[1:]:
            href = unescape(part.split('"', 1)[0])
            if parse_qs(urlparse(href).query).get("page") == ["2"]:
                item_page_links.append(href)

        self.assertTrue(item_page_links)

    def test_filtered_event_does_not_show_sidebar_event_pagination_under_items(self):
        base = datetime(2026, 1, 1, 12, 0, 0)
        selected_event_id = None
        for idx in range(55):
            stamp = (base + timedelta(minutes=idx)).strftime("%Y-%m-%dT%H:%M:%SZ")
            media_id = self._insert_media(f"photo_{idx:03}.jpg", stamp)
            event_id = self._insert_event(media_id, stamp)
            if idx == 0:
                selected_event_id = event_id
            elif idx < 5:
                self._add_event_item(selected_event_id, media_id)
        self.conn.commit()

        with self.app.test_client() as client:
            response = client.get(
                f"/media/?view=events&event_id={selected_event_id}&view_mode=filmstrip"
                "&sort=taken_desc&group=month&nav_event_page=2"
            )

        self.assertEqual(response.status_code, 200)
        after_items = response.get_data(as_text=True).split('<form class="media-actions-form"', 1)[1]

        self.assertNotIn('<div style="margin:8px 0;">', after_items)

    def test_video_thumbnails_do_not_preload_media_files(self):
        stamp = datetime(2026, 1, 1, 12, 0, 0).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._insert_media("clip.mp4", stamp, ext="mp4", media_type="video")
        self.conn.commit()

        with self.app.test_client() as client:
            response = client.get("/media/?view=all&media_type=video&view_mode=filmstrip")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("media-video-thumb", html)
        self.assertIn('preload="none"', html)
        self.assertNotIn('<video muted preload="metadata">', html)


if __name__ == "__main__":
    unittest.main()
