import os
import sqlite3
import sys
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from common import config as cfg
from common import data
from modules.places import routes as places_routes


def _create_places_table(conn, include_new_columns=True):
    base_cols = ["name", "desc", "address_street", "suburb", "postcode", "state", "country", "gps_lat", "gps_long"]
    cols = next(tbl["col_list"] for tbl in cfg.table_def if tbl["route"] == "places") if include_new_columns else base_cols
    col_defs = ", ".join([f"{col} TEXT" for col in cols])
    conn.execute(f"CREATE TABLE lp_places (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs}, user_name TEXT, rec_extract_date TEXT)")


class TestPlaces(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = data.conn
        data.conn = self.conn

    def tearDown(self):
        data.conn = self.old_conn
        self.conn.close()

    def test_normalize_place_url_accepts_local_hosts(self):
        self.assertEqual(places_routes.normalize_place_url("example.com"), "https://example.com")
        self.assertEqual(places_routes.normalize_place_url("http://treebeard:8080"), "http://treebeard:8080")
        self.assertEqual(places_routes.normalize_place_url("http://localhost:5000/"), "http://localhost:5000/")
        self.assertEqual(places_routes.normalize_place_url("https://192.168.1.99/"), "https://192.168.1.99/")
        with self.assertRaises(ValueError):
            places_routes.normalize_place_url("not a url")

    def test_places_schema_backfills_existing_rows_as_address(self):
        _create_places_table(self.conn, include_new_columns=False)
        self.conn.execute("INSERT INTO lp_places (name, gps_lat, gps_long) VALUES ('Home', '-34.0', '138.0')")

        data.ensure_places_schema(self.conn)

        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(lp_places)").fetchall()}
        self.assertIn("place_type", cols)
        self.assertIn("url", cols)
        row = self.conn.execute("SELECT place_type FROM lp_places WHERE name = 'Home'").fetchone()
        self.assertEqual(row["place_type"], "address")

    def test_url_place_insert_is_single_table_and_normalized(self):
        _create_places_table(self.conn)
        tbl = next(tbl for tbl in cfg.table_def if tbl["route"] == "places")
        values = {col: "" for col in tbl["col_list"]}
        values.update({"name": "Example", "place_type": "url", "url": "https://example.com", "area": "Dev"})

        record_id = data.add_record(self.conn, "lp_places", tbl["col_list"], [values[col] for col in tbl["col_list"]])

        row = self.conn.execute("SELECT name, place_type, url, area FROM lp_places WHERE id = ?", (record_id,)).fetchone()
        self.assertEqual(dict(row), {"name": "Example", "place_type": "url", "url": "https://example.com", "area": "Dev"})

    def test_configured_virtual_worlds_come_from_places_settings(self):
        settings_conn = self.conn
        from common import settings

        settings.save_places_settings({"virtual_worlds": "Alrona\nWorld of Warcraft\nStardew Valley"}, settings_conn)
        _create_places_table(self.conn)

        self.assertEqual(
            places_routes._configured_virtual_worlds()[:3],
            ["Alrona", "World of Warcraft", "Stardew Valley"],
        )

    def test_geocode_address_parses_lat_lon_without_network(self):
        payload = {
            "name": "Adelaide Botanic Garden",
            "address_street": "North Terrace",
            "suburb": "Adelaide",
            "state": "SA",
            "country": "Australia",
        }
        fake_result = [
            {
                "lat": "-34.9172",
                "lon": "138.6116",
                "display_name": "Adelaide Botanic Garden, Adelaide, Australia",
                "address": {
                    "road": "North Terrace",
                    "city": "Adelaide",
                    "state": "South Australia",
                    "postcode": "5000",
                    "country": "Australia",
                },
            }
        ]

        with patch.object(places_routes, "_nominatim_json", return_value=fake_result):
            result = places_routes._geocode_address(payload)

        self.assertEqual(result["latitude"], "-34.9172")
        self.assertEqual(result["longitude"], "138.6116")
        self.assertEqual(result["suburb"], "Adelaide")

    def test_reverse_geocode_fills_blank_address_without_network(self):
        fake_result = {
            "display_name": "North Terrace, Adelaide, Australia",
            "address": {
                "road": "North Terrace",
                "city": "Adelaide",
                "state": "South Australia",
                "postcode": "5000",
                "country": "Australia",
            },
        }

        with patch.object(places_routes, "_nominatim_json", return_value=fake_result):
            result = places_routes._reverse_geocode({"gps_lat": "-34.9172", "gps_long": "138.6116"})

        self.assertEqual(result["address_street"], "North Terrace")
        self.assertEqual(result["suburb"], "Adelaide")
        self.assertEqual(result["country"], "Australia")

    def test_import_url_lines_adds_normalized_places_with_titles(self):
        _create_places_table(self.conn)
        metadata = {
            "url": "https://example.com",
            "title": "Example Domain",
            "hostname": "example.com",
        }

        with patch.object(places_routes, "_url_metadata", return_value=metadata):
            results = places_routes._import_url_lines("example.com\n", "Dev")

        self.assertEqual(results[0]["status"], "added")
        row = self.conn.execute("SELECT name, place_type, url, area FROM lp_places").fetchone()
        self.assertEqual(dict(row), {"name": "Example Domain", "place_type": "url", "url": "https://example.com", "area": "Dev"})

    def test_import_address_lines_adds_geocoded_places(self):
        _create_places_table(self.conn)
        geocode = {
            "latitude": "-34.9172",
            "longitude": "138.6116",
            "display_name": "Adelaide Botanic Garden, Adelaide, Australia",
            "address_street": "North Terrace",
            "suburb": "Adelaide",
            "state": "South Australia",
            "postcode": "5000",
            "country": "Australia",
        }

        with patch.object(places_routes, "_geocode_address", return_value=geocode):
            results = places_routes._import_address_lines("Adelaide Botanic Garden, Adelaide\n", "Garden")

        self.assertEqual(results[0]["status"], "added")
        row = self.conn.execute("SELECT place_type, gps_lat, gps_long, suburb, country, area FROM lp_places").fetchone()
        self.assertEqual(
            dict(row),
            {
                "place_type": "address",
                "gps_lat": "-34.9172",
                "gps_long": "138.6116",
                "suburb": "Adelaide",
                "country": "Australia",
                "area": "Garden",
            },
        )

    def test_rescan_url_place_updates_title(self):
        _create_places_table(self.conn)
        tbl = next(tbl for tbl in cfg.table_def if tbl["route"] == "places")
        values = {col: "" for col in tbl["col_list"]}
        values.update({"name": "Old", "place_type": "url", "url": "https://example.com"})
        place_id = data.add_record(self.conn, "lp_places", tbl["col_list"], [values[col] for col in tbl["col_list"]])
        item = dict(self.conn.execute("SELECT * FROM lp_places WHERE id = ?", (place_id,)).fetchone())

        with patch.object(
            places_routes,
            "_url_metadata",
            return_value={"url": "https://example.com", "title": "New Title", "hostname": "example.com"},
        ):
            ok, message = places_routes._rescan_place(item)

        self.assertTrue(ok)
        self.assertIn("URL", message)
        row = self.conn.execute("SELECT name FROM lp_places WHERE id = ?", (place_id,)).fetchone()
        self.assertEqual(row["name"], "New Title")


if __name__ == "__main__":
    unittest.main()
