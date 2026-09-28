import os
import sqlite3
import unittest
from datetime import date
from flask import Flask
from werkzeug.datastructures import MultiDict

root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in os.sys.path:
    os.sys.path.append(root_folder)

from modules.calendar.services import calendar_index
from modules.calendar.services import external_events
from modules.calendar.services import school_terms
from modules.calendar import routes as calendar_routes


def memory_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class CalendarStage2Tests(unittest.TestCase):
    def test_explicit_source_list_is_not_overridden_by_legacy_event_flag(self):
        conn = memory_conn()
        original_conn = calendar_routes.data.conn
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_routes.data.conn = conn
            with Flask(__name__).test_request_context("/"):
                sources, params = calendar_routes._parse_day_sources(
                    MultiDict([("sources", "manual,recurring"), ("show_events", "1")])
                )
                self.assertEqual(sources["selected"], {"manual", "recurring"})
                self.assertNotIn("birthdays", sources["selected"])
                self.assertEqual(params["sources"], "manual,recurring")
                sources, _ = calendar_routes._parse_day_sources(MultiDict([("source_filter", "1")]))
                self.assertEqual(sources["selected"], set())
        finally:
            calendar_routes.data.conn = original_conn
            conn.close()

    def test_grouped_source_selection_is_mapped_and_restored_individually(self):
        conn = memory_conn()
        original_conn = calendar_routes.data.conn
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_routes.data.conn = conn
            with Flask(__name__).test_request_context("/"):
                sources, params = calendar_routes._parse_day_sources(
                    MultiDict(
                        [
                            ("source_filter", "1"),
                            ("source", "manual"),
                            ("source", "birthdays"),
                            ("source", "media"),
                            ("source", "external_events"),
                        ]
                    )
                )
                self.assertEqual(
                    sources["selected"],
                    {"manual", "birthdays", "media", "external_events"},
                )
                self.assertEqual(params["show_events"], "1")
                self.assertEqual(params["show_files"], "1")
                states = {group["key"]: group["state"] for group in sources["groups"]}
                self.assertEqual(
                    states,
                    {"events": "mixed", "files": "mixed", "pc_usage": "none", "external": "mixed"},
                )

                restored, _ = calendar_routes._parse_day_sources(MultiDict())
                self.assertEqual(restored["selected"], sources["selected"])
        finally:
            calendar_routes.data.conn = original_conn
            conn.close()

    def test_calendar_source_groups_preserve_requested_identifiers(self):
        groups = {key: tuple(source_keys) for key, _label, source_keys in calendar_routes.CALENDAR_SOURCE_GROUPS}
        self.assertEqual(groups["events"], ("manual", "recurring", "birthdays", "tasks"))
        self.assertEqual(groups["files"], ("audio", "media", "files"))
        self.assertEqual(groups["pc_usage"], ("usage",))
        self.assertEqual(
            groups["external"],
            ("holidays_au", "holidays_sa", "school_terms_sa", "external_events"),
        )

    def test_school_terms_are_visible_by_default(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            source = conn.execute(
                "SELECT enabled, visible_by_default FROM lp_calendar_sources "
                "WHERE source_key = 'school_terms_sa'"
            ).fetchone()
            self.assertEqual((source["enabled"], source["visible_by_default"]), (1, 1))
        finally:
            conn.close()

    def test_explicit_empty_source_selection_returns_no_items_or_stats(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.create_calendar_event(
                {"title": "Visible only with a source", "start_date": "2026-09-26"},
                conn,
            )
            visible_items = calendar_index.fetch_calendar_items_for_days(
                "2026-09-26", "2026-09-27", sources=None, conn=conn
            )
            self.assertTrue(visible_items)
            self.assertEqual(visible_items[0]["id"], str(event_id))
            self.assertIsInstance(visible_items[0]["calendar_item_id"], int)
            self.assertEqual(
                calendar_index.fetch_calendar_items_for_days(
                    "2026-09-26", "2026-09-27", sources=set(), conn=conn
                ),
                [],
            )
            self.assertEqual(
                calendar_index.fetch_calendar_day_stats(
                    "2026-09-26", "2026-09-27", sources=set(), conn=conn
                ),
                [],
            )
        finally:
            conn.close()

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
                "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, event_date TEXT, remind_date TEXT, area TEXT)"
            )
            conn.execute(
                "INSERT INTO lp_calendar_events (id, title, content, event_date, area) VALUES (7, 'Timed', '', '2026-02-03 04:05:06', 'Work')"
            )
            calendar_index.run_calendar_migration(conn)
            calendar_index.run_calendar_migration(conn)
            row = conn.execute("SELECT * FROM lp_calendar_events WHERE id = 7").fetchone()
            self.assertEqual(row["start_date"], "2026-02-03")
            self.assertEqual(row["start_time"], "04:05")
            self.assertEqual(row["area"], "Work")
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
            au_titles = {row["title"] for row in conn.execute("SELECT title FROM lp_calendar_items WHERE source_key = 'holidays_au'")}
            sa_titles = {row["title"] for row in conn.execute("SELECT title FROM lp_calendar_items WHERE source_key = 'holidays_sa'")}
            self.assertNotIn("Labour Day", au_titles)
            self.assertIn("Labour Day", sa_titles)
            self.assertIn("Easter Saturday", sa_titles)
        finally:
            conn.close()

    def test_birthday_editor_records_project_only_through_birthday_source(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.save_birthday("Duncan", "04/23", conn=conn)
            event = conn.execute("SELECT * FROM lp_calendar_events WHERE id = ?", (event_id,)).fetchone()
            self.assertEqual(event["title"], "Duncan's Birthday")
            self.assertEqual(event["event_type"], "birthday")
            self.assertEqual(event["start_date"], "2000-04-23")
            self.assertIn("FREQ=YEARLY", event["recurrence_rule"])
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items WHERE source_key = 'birthdays' AND source_record_id = ?",
                    (str(event_id),),
                ).fetchone()
            )
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items WHERE source_key = 'recurring' AND source_record_id = ?",
                    (str(event_id),),
                ).fetchone()
            )
            listed = calendar_index.fetch_birthdays(conn)
            self.assertEqual(listed[0]["name"], "Duncan")
            self.assertEqual(listed[0]["month_day"], "04/23")
            calendar_index.save_birthday("Duncan James", "05/24", event_id, conn)
            self.assertEqual(calendar_index.fetch_birthdays(conn)[0]["month_day"], "05/24")
            projected_titles = {
                row["title"]
                for row in conn.execute(
                    "SELECT title FROM lp_calendar_items WHERE source_key = 'birthdays' AND source_record_id = ?",
                    (str(event_id),),
                )
            }
            self.assertEqual(projected_titles, {"Duncan James's Birthday"})
            self.assertTrue(calendar_index.delete_birthday(event_id, conn))
            self.assertFalse(conn.execute("SELECT 1 FROM lp_calendar_events WHERE id = ?", (event_id,)).fetchone())
        finally:
            conn.close()

    def test_birthdays_project_for_the_whole_current_year(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.save_birthday("Earlier This Year", "01/15", conn=conn)
            occurrence = conn.execute(
                "SELECT title FROM lp_calendar_items "
                "WHERE source_key = 'birthdays' AND source_record_id = ? AND start_date = ?",
                (str(event_id), f"{date.today().year}-01-15"),
            ).fetchone()
            self.assertIsNotNone(occurrence)
            self.assertEqual(occurrence["title"], "Earlier This Year's Birthday")
        finally:
            conn.close()

    def test_existing_future_only_birthday_source_is_upgraded_once(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.save_birthday("Existing Birthday", "02/19", conn=conn)
            conn.execute(
                "UPDATE lp_calendar_sources SET horizon_past_days = 0, config_json = NULL "
                "WHERE source_key = 'birthdays'"
            )
            conn.execute("DELETE FROM lp_calendar_items WHERE source_key = 'birthdays'")
            calendar_index.ensure_calendar_schema(conn)
            source = conn.execute(
                "SELECT horizon_past_days, config_json FROM lp_calendar_sources WHERE source_key = 'birthdays'"
            ).fetchone()
            self.assertEqual(source["horizon_past_days"], 7300)
            self.assertIn(calendar_index.BIRTHDAY_HORIZON_MIGRATION_KEY, source["config_json"])
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items "
                    "WHERE source_key = 'birthdays' AND source_record_id = ? AND start_date = ?",
                    (str(event_id), f"{date.today().year}-02-19"),
                ).fetchone()
            )
        finally:
            conn.close()

    def test_legacy_yearly_birthday_title_is_reclassified_to_birthday_projection(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            event_id = calendar_index.create_calendar_event(
                {
                    "title": "Duncans Birthday",
                    "start_date": "2000-04-23",
                    "recurrence_rule": "FREQ=YEARLY",
                },
                conn,
            )
            calendar_index.refresh_calendar_source("recurring", conn=conn, full_rebuild=True)
            calendar_index.refresh_calendar_source("birthdays", conn=conn, full_rebuild=True)
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items WHERE source_key = 'recurring' AND source_record_id = ?",
                    (str(event_id),),
                ).fetchone()
            )
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_items WHERE source_key = 'birthdays' AND source_record_id = ?",
                    (str(event_id),),
                ).fetchone()
            )
        finally:
            conn.close()

    def test_holiday_import_replaces_only_selected_source_and_years(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_index.import_holidays("holidays_sa", 2025, 2026, conn)
            sa_2025_count = conn.execute(
                "SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'holidays_sa' AND start_date LIKE '2025-%'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO lp_calendar_items (source_id, source_key, occurrence_key, item_kind, title, "
                "start_date, end_date, projected_at) "
                "SELECT id, 'holidays_au', 'keep-au-2025', 'holiday', 'Keep AU', "
                "'2025-01-02', '2025-01-02', 'now' FROM lp_calendar_sources WHERE source_key = 'holidays_au'"
            )
            conn.execute(
                "INSERT INTO lp_calendar_items (source_id, source_key, occurrence_key, item_kind, title, "
                "start_date, end_date, projected_at) "
                "SELECT id, 'holidays_sa', 'keep-sa-2024', 'holiday', 'Keep SA prior year', "
                "'2024-01-02', '2024-01-02', 'now' FROM lp_calendar_sources WHERE source_key = 'holidays_sa'"
            )
            result = calendar_index.import_holidays("holidays_sa", 2025, 2025, conn)
            self.assertEqual(result.rows_deleted, sa_2025_count)
            imported_count = conn.execute(
                "SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'holidays_sa'"
            ).fetchone()[0]
            calendar_index.run_calendar_migration(conn)
            self.assertEqual(
                conn.execute("SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'holidays_sa'").fetchone()[0],
                imported_count,
            )
            self.assertTrue(conn.execute("SELECT 1 FROM lp_calendar_items WHERE occurrence_key = 'keep-au-2025'").fetchone())
            self.assertTrue(conn.execute("SELECT 1 FROM lp_calendar_items WHERE occurrence_key = 'keep-sa-2024'").fetchone())
            self.assertTrue(
                conn.execute("SELECT 1 FROM lp_calendar_items WHERE source_key = 'holidays_sa' AND start_date LIKE '2026-%'").fetchone()
            )
        finally:
            conn.close()

    def test_school_term_parser_reads_current_and_table_years(self):
        html = """
        <h2>Term dates for 2026</h2><ul>
          <li>Term 1 &ndash; Tuesday 27 January to Friday 10 April</li>
          <li>Term 2 &ndash; Monday 27 April to Friday 3 July</li>
          <li>Term 3 &ndash; Monday 20 July to Friday 25 September</li>
          <li>Term 4 &ndash; Monday 12 October to Friday 11 December</li>
        </ul>
        <h2>Future term dates</h2><table><tbody><tr>
          <th>2027</th><td>27 January to 9 April</td><td>26 April to 2 July</td>
          <td>19 July to 24 September</td><td>11 October to 10 December</td>
        </tr></tbody></table>
        """
        rows = school_terms.parse_school_terms(html)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["start_date"], "2026-01-27")
        self.assertEqual(rows[3]["end_date"], "2026-12-11")
        self.assertEqual(rows[4]["start_date"], "2027-01-27")

    def test_school_term_import_replaces_only_selected_years(self):
        conn = memory_conn()
        terms = [
            {
                "year": year,
                "term": term,
                "title": f"School Term {term}",
                "start_date": f"{year}-{start}",
                "end_date": f"{year}-{end}",
                "all_day": 1,
                "event_type": "school_term",
                "category": "SA School Terms",
                "area": "General",
                "status": "active",
                "source": "school_terms_sa",
            }
            for year in (2025, 2026)
            for term, (start, end) in enumerate(
                (("01-27", "04-10"), ("04-27", "07-03"), ("07-20", "09-25"), ("10-12", "12-11")),
                start=1,
            )
        ]
        events = calendar_index._school_calendar_events(terms)
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_index.import_school_terms(2025, 2026, conn, events=events)
            replacement = [event for event in events if event["year"] == 2025]
            result = calendar_index.import_school_terms(2025, 2025, conn, events=replacement)
            self.assertEqual(result.rows_deleted, 13)
            self.assertEqual(result.rows_inserted, 13)
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(1) FROM lp_calendar_items "
                    "WHERE source_key = 'school_terms_sa' AND start_date LIKE '2026-%'"
                ).fetchone()[0],
                13,
            )
            january_days = conn.execute(
                "SELECT COUNT(1) FROM lp_calendar_item_days d "
                "JOIN lp_calendar_items i ON i.id = d.calendar_item_id "
                "WHERE i.source_key = 'school_terms_sa' AND i.event_type = 'school_holiday' "
                "AND i.start_date = '2025-01-01'"
            ).fetchone()[0]
            self.assertEqual(january_days, 26)
            visible_titles = {
                row["title"]
                for row in conn.execute(
                    "SELECT title FROM lp_calendar_items WHERE source_key = 'school_terms_sa' "
                    "AND event_type = 'school_term_marker'"
                )
            }
            self.assertIn("Start of School Term 1", visible_titles)
            self.assertIn("End of School Term 4", visible_titles)
        finally:
            conn.close()

    def test_external_ics_preview_and_reimport_are_scoped_by_calendar_name(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            calendar_name, events = external_events.parse_ics(
                "BEGIN:VCALENDAR\nX-WR-CALNAME:Household\nBEGIN:VEVENT\n"
                "UID:bins-1\nDTSTART;VALUE=DATE:20260924\nDTEND;VALUE=DATE:20260925\n"
                "SUMMARY:Bins\nEND:VEVENT\nEND:VCALENDAR\n"
            )
            self.assertEqual(calendar_name, "Household")
            self.assertEqual(events[0]["start_date"], "2026-09-24")
            first = external_events.replace_external_events(events, calendar_name, conn)
            second = external_events.replace_external_events(events, calendar_name, conn)
            self.assertEqual(first["inserted"], 1)
            self.assertEqual(second["deleted"], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(1) FROM lp_calendar_items WHERE source_key = 'external_events'").fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_external_ics_expands_recurrence_and_exdates_for_selected_years(self):
        _, events = external_events.parse_ics(
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:bins-series\n"
            "DTSTART;VALUE=DATE:20260903\nDTEND;VALUE=DATE:20260904\n"
            "RRULE:FREQ=WEEKLY;INTERVAL=2\nEXDATE;VALUE=DATE:20261001\n"
            "SUMMARY:Bins\nEND:VEVENT\nEND:VCALENDAR\n",
            2026,
            2026,
        )
        dates = {event["start_date"] for event in events}
        self.assertIn("2026-09-03", dates)
        self.assertIn("2026-09-17", dates)
        self.assertNotIn("2026-10-01", dates)

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

    def test_recent_day_stats_refresh_is_bounded(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            conn.execute("CREATE TABLE lp_files (id INTEGER PRIMARY KEY, path TEXT, mtime_utc TEXT, is_deleted INTEGER)")
            conn.executemany(
                "INSERT INTO lp_files (path, mtime_utc, is_deleted) VALUES (?, ?, ?)",
                [
                    ("old.txt", "2020-01-01T10:00:00Z", 0),
                    ("recent.txt", "2026-08-06T10:00:00Z", 0),
                ],
            )
            results = calendar_index.refresh_recent_calendar_day_stats(
                ["files"],
                past_days=7,
                future_days=0,
                max_age_hours=0,
                today=date(2026, 8, 6),
                conn=conn,
            )
            self.assertEqual([result.source_key for result in results], ["files"])
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_day_stats WHERE stat_date = '2026-08-06' AND source_key = 'files'"
                ).fetchone()
            )
            self.assertFalse(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_day_stats WHERE stat_date = '2020-01-01' AND source_key = 'files'"
                ).fetchone()
            )
        finally:
            conn.close()

    def test_bounded_full_day_stats_refresh_deletes_stale_rows(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            conn.execute("CREATE TABLE lp_files (id INTEGER PRIMARY KEY, path TEXT, mtime_utc TEXT, is_deleted INTEGER)")
            conn.execute(
                "INSERT INTO lp_files (path, mtime_utc, is_deleted) VALUES (?, ?, ?)",
                ("gone.txt", "2026-08-06T10:00:00Z", 0),
            )
            calendar_index.refresh_calendar_source(
                "files",
                from_date="2026-08-01",
                to_date="2026-08-07",
                full_rebuild=True,
                conn=conn,
            )
            self.assertEqual(conn.execute("SELECT COUNT(1) FROM lp_calendar_day_stats").fetchone()[0], 1)
            conn.execute("DELETE FROM lp_files")
            calendar_index.refresh_calendar_source(
                "files",
                from_date="2026-08-01",
                to_date="2026-08-07",
                full_rebuild=True,
                conn=conn,
            )
            self.assertEqual(conn.execute("SELECT COUNT(1) FROM lp_calendar_day_stats").fetchone()[0], 0)
        finally:
            conn.close()

    def test_day_stat_baseline_prompt_clears_after_confirmed_rebuild(self):
        conn = memory_conn()
        try:
            calendar_index.ensure_calendar_schema(conn)
            conn.execute(
                "CREATE TABLE lp_media ("
                "media_id INTEGER PRIMARY KEY, path TEXT, filename TEXT, ext TEXT, "
                "media_type TEXT, size_bytes INTEGER, mtime_utc TEXT)"
            )
            conn.execute(
                "INSERT INTO lp_media (media_id, path, filename, ext, media_type, size_bytes, mtime_utc) "
                "VALUES (1, 'C:/photo.jpg', 'photo.jpg', '.jpg', 'image', 10, '2022-04-05T12:00:00Z')"
            )
            missing = calendar_index.missing_calendar_day_stat_baselines(["media"], conn=conn)
            self.assertEqual([row["source_key"] for row in missing], ["media"])
            self.assertEqual(missing[0]["min_date"], "2022-04-05")
            calendar_index.rebuild_calendar_day_stat_baselines(["media"], conn=conn)
            self.assertFalse(calendar_index.missing_calendar_day_stat_baselines(["media"], conn=conn))
            self.assertTrue(
                conn.execute(
                    "SELECT 1 FROM lp_calendar_day_stats "
                    "WHERE source_key = 'media' AND stat_date = '2022-04-05'"
                ).fetchone()
            )
            config_json = conn.execute(
                "SELECT config_json FROM lp_calendar_sources WHERE source_key = 'media'"
            ).fetchone()["config_json"]
            self.assertIn(calendar_index.STATS_BASELINE_CONFIG_KEY, config_json)
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
