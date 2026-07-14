import os
import sqlite3
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import data
from modules.audio import routes as audio_routes


class TestAudioPlayerCurrentList(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._old_conn = data.conn
        data.conn = self.conn
        self.conn.execute(
            "CREATE TABLE lp_audio ("
            "id INTEGER PRIMARY KEY, file_name TEXT, path TEXT, folder_id TEXT, file_type TEXT, size TEXT, "
            "date_modified TEXT, duration TEXT, artist TEXT, album TEXT, song TEXT, project TEXT, "
            "user_name TEXT, rec_extract_date TEXT)"
        )
        for audio_id, name in [(1, "one.mp3"), (2, "two.mp3"), (3, "three.mp3")]:
            self.conn.execute(
                "INSERT INTO lp_audio (id, file_name, path, file_type, song) VALUES (?, ?, 'C:\\\\audio', 'mp3', ?)",
                (audio_id, name, name),
            )
        self.conn.commit()

    def tearDown(self):
        data.conn = self._old_conn
        self.conn.close()

    def test_parse_audio_ids_dedupes_and_ignores_invalid_values(self):
        self.assertEqual(audio_routes._parse_audio_ids("3, bad, 2, 3, 1"), [3, 2, 1])

    def test_fetch_audio_by_ids_preserves_current_display_order(self):
        items = audio_routes._fetch_audio_by_ids([3, 1, 2])
        self.assertEqual([item["id"] for item in items], [3, 1, 2])
        self.assertEqual([item["file_name"] for item in items], ["three.mp3", "one.mp3", "two.mp3"])


if __name__ == "__main__":
    unittest.main()
