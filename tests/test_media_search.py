import os
import sqlite3
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
