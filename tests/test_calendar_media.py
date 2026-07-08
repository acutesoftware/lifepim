import os
import sqlite3
import unittest
from datetime import date

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from modules.calendar import routes as calendar_routes


class TestCalendarMediaPreviews(unittest.TestCase):
    def test_preview_order_samples_unique_folders_first(self):
        items = [
            {"filename": "a1.jpg", "path": r"C:\Photos\Trip\a1.jpg"},
            {"filename": "a2.jpg", "path": r"C:\Photos\Trip\a2.jpg"},
            {"filename": "b1.jpg", "path": r"C:\Photos\Family\b1.jpg"},
            {"filename": "c1.mp3", "path": r"C:\Music\Album"},
            {"filename": "b2.jpg", "path": r"C:\Photos\Family\b2.jpg"},
        ]
        for item in items:
            item["folder_key"] = calendar_routes._folder_key(item["path"])

        ordered = calendar_routes._order_calendar_media_previews(items)

        self.assertEqual([item["filename"] for item in ordered], ["a1.jpg", "b1.jpg", "c1.mp3", "a2.jpg", "b2.jpg"])

    def test_fetch_calendar_media_includes_images_videos_and_audio(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE lp_media ("
                "media_id INTEGER PRIMARY KEY, path TEXT, filename TEXT, ext TEXT, "
                "media_type TEXT, size_bytes INTEGER, mtime_utc TEXT)"
            )
            conn.execute(
                "CREATE TABLE lp_audio ("
                "id INTEGER PRIMARY KEY, file_name TEXT, path TEXT, file_type TEXT, "
                "size INTEGER, date_modified TEXT)"
            )
            conn.execute(
                "INSERT INTO lp_media (media_id, path, filename, ext, media_type, size_bytes, mtime_utc) "
                "VALUES (1, ?, 'photo.jpg', 'jpg', 'image', 10, '2026-01-02T10:00:00Z')",
                (r"C:\Photos\photo.jpg",),
            )
            conn.execute(
                "INSERT INTO lp_media (media_id, path, filename, ext, media_type, size_bytes, mtime_utc) "
                "VALUES (2, ?, 'movie.mp4', 'mp4', 'video', 20, '2026-01-02T11:00:00Z')",
                (r"C:\Movies\movie.mp4",),
            )
            conn.execute(
                "INSERT INTO lp_audio (id, file_name, path, file_type, size, date_modified) "
                "VALUES (3, 'song.mp3', ?, 'mp3', 30, '2026-01-02T12:00:00Z')",
                (r"C:\Music\Album",),
            )

            items = calendar_routes._fetch_calendar_media(conn, date(2026, 1, 2), date(2026, 1, 3))

            self.assertEqual([item["filename"] for item in items], ["photo.jpg", "movie.mp4", "song.mp3"])
            self.assertEqual([item["media_type"] for item in items], ["image", "video", "audio"])
            self.assertEqual(items[2]["audio_id"], 3)
        finally:
            conn.close()

    def test_fetch_video_media_by_event_date_maps_matching_videos(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE lp_media ("
                "media_id INTEGER PRIMARY KEY, path TEXT, filename TEXT, ext TEXT, "
                "media_type TEXT, size_bytes INTEGER, mtime_utc TEXT)"
            )
            conn.executemany(
                "INSERT INTO lp_media (media_id, path, filename, ext, media_type, size_bytes, mtime_utc) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, r"C:\Movies\one.mp4", "one.mp4", "mp4", "video", 10, "2026-01-02T10:00:00Z"),
                    (2, r"C:\Photos\photo.jpg", "photo.jpg", "jpg", "image", 10, "2026-01-02T11:00:00Z"),
                    (3, r"C:\Movies\two.mp4", "two.mp4", "mp4", "video", 10, "2026-01-03T10:00:00Z"),
                ],
            )

            videos = calendar_routes._fetch_video_media_by_event_date(
                conn,
                [{"date": "2026-01-02"}, {"date": "2026-01-04"}],
            )

            self.assertEqual([item["filename"] for item in videos["2026-01-02"]], ["one.mp4"])
            self.assertNotIn("2026-01-03", videos)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
