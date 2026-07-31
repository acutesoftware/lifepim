import os
import sqlite3
import sys
import unittest

from flask import Flask


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import areas, collections, data, projects
from common.media_schema import ensure_media_schema
from common.utils import format_duration_friendly, format_duration_label
from modules.audio import routes as audio_routes
from modules.media import routes as media_routes


def _register_layout_stubs(app):
    app.add_url_rule("/settings", endpoint="admin.settings_route", view_func=lambda: "")
    app.add_url_rule("/help", endpoint="help_route", view_func=lambda: "")
    app.add_url_rule("/history", endpoint="admin.user_history_route", view_func=lambda: "")
    app.add_url_rule("/search", endpoint="search_route", view_func=lambda: "")
    app.add_url_rule("/site.webmanifest", endpoint="site_webmanifest", view_func=lambda: "")


class TestMediaAudioCollections(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        self.old_media_ready = media_routes._MEDIA_SCHEMA_READY
        data.conn = self.conn
        media_routes._MEDIA_SCHEMA_READY = False
        ensure_media_schema(self.conn)
        self.conn.execute(
            "CREATE TABLE lp_audio ("
            "id INTEGER PRIMARY KEY, file_name TEXT, path TEXT, folder_id TEXT, file_type TEXT, size TEXT, "
            "date_modified TEXT, duration TEXT, artist TEXT, album TEXT, song TEXT, area TEXT, "
            "user_name TEXT, rec_extract_date TEXT)"
        )
        areas.ensure_areas_schema(self.conn)
        projects.ensure_projects_schema(self.conn)
        collections.ensure_collections_schema(self.conn)
        self.conn.execute(
            "INSERT INTO lp_media(media_id, path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
            "VALUES (1, 'C:\\\\photos\\\\one.jpg', 'one.jpg', 'jpg', 'image', 100, '2026-01-01T00:00:00Z', '', 'one')"
        )
        self.conn.execute(
            "INSERT INTO lp_media(media_id, path, filename, ext, media_type, size_bytes, mtime_utc, ctime_utc, hash) "
            "VALUES (2, 'C:\\\\videos\\\\clip.mp4', 'clip.mp4', 'mp4', 'video', 100, '2026-01-02T00:00:00Z', '', 'clip')"
        )
        self.conn.execute(
            "INSERT INTO lp_audio(id, file_name, path, file_type, artist, album, song, area) "
            "VALUES (1, 'one.mp3', 'C:\\\\audio', 'mp3', 'Artist', 'Album', 'One', '')"
        )
        self.conn.execute(
            "INSERT INTO lp_audio(id, file_name, path, file_type, artist, album, song, area) "
            "VALUES (2, 'two.mp3', 'C:\\\\audio', 'mp3', 'Artist', 'Album', 'Two', '')"
        )
        self.conn.commit()

    def tearDown(self):
        data.conn = self.old_conn
        media_routes._MEDIA_SCHEMA_READY = self.old_media_ready
        self.conn.close()

    def _media_app(self):
        app = Flask(__name__, template_folder=os.path.join(root_folder, "templates"))
        app.jinja_env.filters["duration_friendly"] = format_duration_friendly
        app.jinja_env.filters["duration_label"] = format_duration_label
        app.register_blueprint(media_routes.media_bp)
        _register_layout_stubs(app)
        app.config["TESTING"] = True
        return app

    def _audio_app(self):
        app = Flask(__name__, template_folder=os.path.join(root_folder, "templates"))
        app.jinja_env.filters["duration_friendly"] = format_duration_friendly
        app.jinja_env.filters["duration_label"] = format_duration_label
        app.register_blueprint(audio_routes.audio_bp)
        _register_layout_stubs(app)
        app.config["TESTING"] = True
        return app

    def test_media_album_route_renders_collection_thumbnails_and_preserves_sources(self):
        album_id = collections.create_collection(
            {"collection_name": "Dinner Photos", "collection_domain": "media", "collection_type": "album"},
            conn=self.conn,
        )
        collections.add_item_to_collection(album_id, "media", 1, conn=self.conn)
        collections.add_item_to_collection(album_id, "media", 2, conn=self.conn)

        response = self._media_app().test_client().get(f"/media/albums?collection_id={album_id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Dinner Photos", html)
        self.assertIn("/media/file/1", html)
        self.assertIn("<video", html)
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_media").fetchone()[0], 2)

    def test_audio_playlist_route_renders_player_link_and_preserves_sources(self):
        playlist_id = collections.create_collection(
            {"collection_name": "Road Mix", "collection_domain": "audio", "collection_type": "playlist"},
            conn=self.conn,
        )
        collections.add_item_to_collection(playlist_id, "audio", 2, conn=self.conn)
        collections.add_item_to_collection(playlist_id, "audio", 1, conn=self.conn)

        response = self._audio_app().test_client().get(f"/audio/playlists?collection_id={playlist_id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Road Mix", html)
        self.assertIn("/audio/player?ids=2,1", html)
        self.assertIn("/audio/file/2", html)
        self.assertEqual(self.conn.execute("SELECT COUNT(1) FROM lp_audio").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
