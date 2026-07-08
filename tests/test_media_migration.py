import os
import sqlite3
import tempfile
import unittest

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from common import media_migration
from common.media_schema import ensure_media_schema


class TestMediaMigration(unittest.TestCase):
    def _filelist_db(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        conn = sqlite3.connect(handle.name)
        conn.execute(
            "CREATE TABLE u_image_files ("
            "filepath TEXT, image_size INTEGER, basename TEXT, path TEXT, folder_name TEXT, "
            "file_path TEXT, filelist_size INTEGER, modified TEXT, created TEXT, file_type TEXT, "
            "is_user TEXT, is_processed TEXT, owner TEXT, hash TEXT, width INTEGER, height INTEGER, "
            "format TEXT, lat TEXT, lon TEXT, cam_make TEXT, cam_model TEXT, exif_datetime TEXT, "
            "cam_date_digitized TEXT, thumb_sha1 TEXT, phash TEXT, ahash TEXT)"
        )
        conn.execute(
            "INSERT INTO u_image_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\photos\a.jpg",
                123,
                "a.jpg",
                r"E:\photos",
                "Photos",
                r"E:\photos\a.jpg",
                124,
                "2023-12-31T01:02:03.456",
                "2023-12-30T01:02:03.456",
                "jpg",
                "Y",
                "Y",
                "unknown",
                "filehash",
                640,
                480,
                "JPEG",
                "-34.1",
                "138.6",
                "Canon",
                "R5",
                "2024:01:02 03:04:05",
                "",
                "sha1",
                "",
                "",
            ),
        )
        conn.execute(
            "INSERT INTO u_image_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\other\b.jpg",
                999,
                "b.jpg",
                r"E:\other",
                "Other",
                r"E:\other\b.jpg",
                999,
                "2023-01-01T00:00:00",
                "2023-01-01T00:00:00",
                "jpg",
                "Y",
                "Y",
                "unknown",
                "",
                1,
                1,
                "JPEG",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ),
        )
        conn.execute("CREATE TABLE filelist_output (file_path TEXT, folder_name TEXT, modified TEXT, created TEXT, file_type TEXT, hash TEXT)")
        conn.execute(
            "CREATE TABLE fl_video ("
            "filepath TEXT, duration INTEGER, width INTEGER, height INTEGER, file_size INTEGER, "
            "title TEXT, frame_rate REAL, size INTEGER, basename TEXT, path TEXT)"
        )
        conn.execute(
            "INSERT INTO fl_video VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\movies\movie.mp4",
                120.5,
                1920,
                1080,
                1000,
                "Movie",
                24.0,
                1000,
                "movie.mp4",
                r"E:\movies",
            ),
        )
        conn.execute(
            "INSERT INTO filelist_output VALUES (?, ?, ?, ?, ?, ?)",
            (r"E:\movies\movie.mp4", "Movies", "2022-01-02T03:04:05", "2022-01-01T03:04:05", "mp4", "videohash"),
        )
        conn.execute(
            "INSERT INTO fl_video VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\other\clip.mp4",
                1.0,
                320,
                240,
                10,
                "Clip",
                30.0,
                10,
                "clip.mp4",
                r"E:\other",
            ),
        )
        conn.execute(
            "INSERT INTO filelist_output VALUES (?, ?, ?, ?, ?, ?)",
            (r"E:\other\clip.mp4", "Other", "2022-01-02T03:04:05", "2022-01-01T03:04:05", "mp4", ""),
        )
        conn.execute(
            "CREATE TABLE fl_audio ("
            "filepath TEXT, size INTEGER, basename TEXT, path TEXT, title TEXT, artist TEXT, album TEXT, "
            "genre TEXT, tracknumber INTEGER, date TEXT, duration REAL, bitrate INTEGER, channels INTEGER, samplerate INTEGER)"
        )
        conn.execute(
            "INSERT INTO fl_audio VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\other\noise.wav",
                999,
                "noise.wav",
                r"E:\other",
                "Noise",
                "",
                "",
                "",
                1,
                "",
                1.0,
                128000,
                2,
                44100,
            ),
        )
        conn.execute("INSERT INTO filelist_output VALUES (?, ?, ?, ?, ?, ?)", (r"E:\other\noise.wav", "Other", "", "", "wav", ""))
        conn.execute(
            "INSERT INTO fl_audio VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                r"E:\music\song.mp3",
                456,
                "song.mp3",
                r"E:\music",
                "Song",
                "Artist",
                "Album",
                "Rock",
                1,
                "2020",
                1.0,
                128000,
                2,
                44100,
            ),
        )
        conn.execute("INSERT INTO filelist_output VALUES (?, ?, ?, ?, ?, ?)", (r"E:\music\song.mp3", "Music", "", "", "mp3", ""))
        conn.commit()
        conn.close()
        return handle.name

    def _target_conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        ensure_media_schema(conn)
        conn.execute(
            "CREATE TABLE lp_audio ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, path TEXT, folder_id TEXT, "
            "file_type TEXT, size TEXT, date_modified TEXT, artist TEXT, album TEXT, song TEXT, "
            "project TEXT, user_name TEXT, rec_extract_date TEXT)"
        )
        conn.execute("CREATE TABLE lp_audio_playlist_items (playlist_item_id INTEGER PRIMARY KEY, audio_id INTEGER)")
        return conn

    def test_migrate_images_from_filelist(self):
        source_path = self._filelist_db()
        conn = self._target_conn()
        try:
            result = media_migration.migrate_images_from_filelist(source_path, r"WHERE folder_name IN ('Photos', 'Movies')", conn)
            self.assertEqual(result["inserted"], 1)
            self.assertEqual(result["video_inserted"], 1)
            self.assertEqual(result["total_inserted"], 2)
            image = conn.execute("SELECT * FROM lp_media WHERE media_type = 'image'").fetchone()
            self.assertEqual(image["path"], r"E:\photos\a.jpg")
            self.assertEqual(image["filename"], "a.jpg")
            self.assertEqual(image["media_type"], "image")
            self.assertEqual(image["size_bytes"], 124)
            self.assertEqual(image["mtime_utc"], "2023-12-31T01:02:03Z")
            self.assertEqual(image["ctime_utc"], "2023-12-30T01:02:03Z")
            self.assertEqual(image["hash"], "filehash")
            meta = conn.execute("SELECT * FROM lp_media_meta WHERE media_id = ?", (image["media_id"],)).fetchone()
            self.assertEqual(meta["taken_utc"], "2024-01-02T03:04:05Z")
            self.assertEqual(meta["width"], 640)
            video = conn.execute("SELECT * FROM lp_media WHERE media_type = 'video'").fetchone()
            self.assertEqual(video["path"], r"E:\movies\movie.mp4")
            self.assertEqual(video["filename"], "movie.mp4")
            self.assertEqual(video["size_bytes"], 1000)
            self.assertEqual(video["mtime_utc"], "2022-01-02T03:04:05Z")
            self.assertEqual(video["ctime_utc"], "2022-01-01T03:04:05Z")
            self.assertEqual(video["hash"], "videohash")
            video_meta = conn.execute("SELECT * FROM lp_media_meta WHERE media_id = ?", (video["media_id"],)).fetchone()
            self.assertEqual(video_meta["width"], 1920)
            self.assertEqual(video_meta["height"], 1080)
            self.assertEqual(video_meta["duration_sec"], 120.5)
            self.assertEqual(video_meta["fps"], 24.0)
        finally:
            conn.close()
            os.unlink(source_path)

    def test_migrate_audio_from_filelist(self):
        source_path = self._filelist_db()
        conn = self._target_conn()
        try:
            result = media_migration.migrate_audio_from_filelist(source_path, r"WHERE folder_name = 'Music'", conn)
            self.assertEqual(result["inserted"], 1)
            row = conn.execute("SELECT * FROM lp_audio").fetchone()
            self.assertEqual(row["file_name"], "song.mp3")
            self.assertEqual(row["path"], r"E:\music")
            self.assertEqual(row["file_type"], "mp3")
            self.assertEqual(row["artist"], "Artist")
            self.assertEqual(row["album"], "Album")
            self.assertEqual(row["song"], "Song")
        finally:
            conn.close()
            os.unlink(source_path)

    def test_where_clause_must_start_with_where(self):
        source_path = self._filelist_db()
        conn = self._target_conn()
        try:
            with self.assertRaises(ValueError):
                media_migration.migrate_images_from_filelist(source_path, "ORDER BY path", conn)
        finally:
            conn.close()
            os.unlink(source_path)


if __name__ == "__main__":
    unittest.main()
