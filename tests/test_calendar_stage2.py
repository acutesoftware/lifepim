import os
import sqlite3
import unittest
from datetime import date

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from modules.calendar.services import calendar_index


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class CalendarStage2Tests(unittest.TestCase):
    def test_schema_sources_indexes_and_cascade(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            for table in [
                "lp_calendar_sources",
                "lp_calendar_events",
                "lp_calendar_items",
                "lp_calendar_item_days",
                "lp_calendar_day_stats",
            ]:
                self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", [table]).fetchone())
            indexes = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()}
            self.assertIn("idx_calendar_items_occurrence", indexes)
            event_id = calendar_index.create_calendar_event(
                {"title": "Trip", "start_date": "2026-01-01", "end_date": "2026-01-05"},
                conn,
            )
            item = conn.execute("SELECT id FROM lp_calendar_items WHERE source_record_id = ?", [str(event_id)]).fetchone()
            self.assertEqual(
                conn.execute("SELECT COUNT(1) FROM lp_calendar_item_days WHERE calendar_item_id = ?", [item["id"]]).fetchone()[0],
                5,
            )
            conn.execute("DELETE FROM lp_calendar_items WHERE id = ?", [item["id"]])
            self.assertEqual(
                conn.execute("SELECT COUNT(1) FROM lp_calendar_item_days WHERE calendar_item_id = ?", [item["id"]]).fetchone()[0],
                0,
            )
        finally:
            conn.close()

    def test_migration_backfills_legacy_dates_and_is_rerunnable(self):
        conn = memory_conn()
        try:
            conn.execute(
                "CREATE TABLE lp_calendar_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, event_date TEXT, remind_date TEXT, project TEXT)"
            )
            conn.execute(
                "INSERT INTO lp_calendar_events (id, title, content, event_date, project) VALUES (7, 'Timed', '', '2026-02-03 04:05:06', 'Work')"
            )
            calendar_index.run_calendar_migration(conn)
            calendar_index.run_calendar_migration(conn)
            row = conn.execute("SELECT * FROM lp_calendar_events WHERE id = 7").fetchone()
            self.assertEqual(row["start_date"], "2026-02-03")
            self.assertEqual(row["start_time"], "04:05")
            self.assertEqual(row["project"], "Work")
            item = conn.execute("SELECT * FROM lp_calendar_items WHERE source_key = 'manual' AND source_record_id = '7'").fetchone()
            self.assertIsNotNone(item)
            self.assertEqual(item["occurrence_key"], "manual:7")
        finally:
            conn.close()

    def test_recurring_projection_is_idempotent(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.create_calendar_event(
                {
                    "title": "Standup",
                    "start_date": "2026-07-01",
                    "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO,WE",
                    "recurrence_end_date": "2026-07-15",
                },
                conn,
            )
            calendar_index.refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
            first_count = conn.execute("SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'recurring'").fetchone()[0]
            calendar_index.refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
            second_count = conn.execute("SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'recurring'").fetchone()[0]
            keys = [
                row["occurrence_key"]
                for row in conn.execute("SELECT occurrence_key FROM lp_calendar_items WHERE source_record_id = ?", [str(event_id)])
            ]
            self.assertEqual(first_count, second_count)
            self.assertEqual(len(keys), len(set(keys)))
            self.assertIn(f"recurring:{event_id}:2026-07-01", keys)
        finally:
            conn.close()

    def test_birthday_leap_day_and_holiday_sources(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_index.create_calendar_event(
                {"title": "Leap Birthday", "start_date": "2024-02-29", "event_type": "birthday", "recurrence_rule": "FREQ=YEARLY"},
                conn,
            )
            calendar_index.refresh_calendar_source("birthdays", conn=conn, full_rebuild=True)
            self.assertTrue(
                conn.execute("SELECT 1 FROM lp_calendar_items WHERE source_key = 'birthdays' AND start_date LIKE '%-02-28'").fetchone()
            )
            calendar_index.refresh_calendar_source("holidays_au", conn=conn, full_rebuild=True)
            calendar_index.refresh_calendar_source("holidays_sa", conn=conn, full_rebuild=True)
            self.assertTrue(conn.execute("SELECT 1 FROM lp_calendar_items WHERE source_key = 'holidays_au'").fetchone())
            self.assertTrue(conn.execute("SELECT 1 FROM lp_calendar_items WHERE source_key = 'holidays_sa'").fetchone())
        finally:
            conn.close()

    def test_day_stats_upsert_is_idempotent(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            conn.execute("CREATE TABLE lp_files (id INTEGER PRIMARY KEY, path TEXT, mtime_utc TEXT, is_deleted INTEGER)")
            conn.executemany(
                "INSERT INTO lp_files (path, mtime_utc, is_deleted) VALUES (?, ?, ?)",
                [("a.txt", "2026-07-11T10:00:00Z", 0), ("b.txt", "2026-07-11T11:00:00Z", 0)],
            )
            calendar_index.rebuild_calendar_day_stats("files", conn=conn)
            calendar_index.rebuild_calendar_day_stats("files", conn=conn)
            row = conn.execute(
                "SELECT item_count FROM lp_calendar_day_stats WHERE stat_date = '2026-07-11' AND source_key = 'files' AND metric_key = 'files_modified'"
            ).fetchone()
            self.assertEqual(row["item_count"], 2)
            self.assertEqual(conn.execute("SELECT COUNT(1) FROM lp_calendar_day_stats").fetchone()[0], 1)
        finally:
            conn.close()

    def test_schema_ensure_does_not_reproject_manual_events(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.create_calendar_event({"title": "Fast", "start_date": "2026-07-11"}, conn)
            conn.execute("DELETE FROM lp_calendar_items WHERE source_key = 'manual' AND source_record_id = ?", [str(event_id)])
            conn.commit()
            calendar_index.ensure_calendar_schema(conn)
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items WHERE source_key = 'manual' AND source_record_id = ?",
                    [str(event_id)],
                ).fetchone()
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
