import os
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from modules.places import local_maps


def _gpkg_linestring(points):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    header = b"GP" + bytes((0, 3)) + struct.pack("<i", 100000)
    envelope = struct.pack("<dddd", min(xs), max(xs), min(ys), max(ys))
    wkb = bytes((1,)) + struct.pack("<II", 2, len(points))
    wkb += b"".join(struct.pack("<dd", *point) for point in points)
    return header + envelope + wkb


class TestPlacesLocalMaps(unittest.TestCase):
    def test_partial_downloads_use_separate_cache_subdirectory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            self.assertEqual(local_maps.pack_path("south-australia", root).parent, root)
            self.assertEqual(local_maps.download_dir(root), root / ".downloads")

    def test_decode_geopackage_linestring(self):
        blob = _gpkg_linestring([(138.5, -34.9), (138.6, -35.0)])

        geometry = local_maps._decode_gpkg_geometry(blob)

        self.assertEqual(geometry["type"], "LineString")
        self.assertEqual(geometry["coordinates"][1], [138.6, -35.0])
        self.assertEqual(local_maps._geometry_envelope(blob), (138.5, 138.6, -35.0, -34.9))

    def test_index_and_query_local_geopackage(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.gpkg"
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE gis_osm_roads_free (fid INTEGER PRIMARY KEY, geom BLOB, fclass TEXT, name TEXT)"
            )
            conn.execute(
                "INSERT INTO gis_osm_roads_free VALUES (?, ?, ?, ?)",
                (1, _gpkg_linestring([(138.5, -34.9), (138.6, -35.0)]), "primary", "Test Road"),
            )
            conn.commit()
            conn.close()

            local_maps._ensure_spatial_indexes(path)
            with patch.object(local_maps, "installed_packs", return_value=[{"id": "sample", "bounds": []}]), patch.object(
                local_maps, "pack_path", return_value=path
            ):
                result = local_maps.query_features((138.4, -35.1, 138.7, -34.8), 1)

            self.assertEqual(len(result["roads"]), 1)
            self.assertEqual(result["roads"][0]["n"], "Test Road")


if __name__ == "__main__":
    unittest.main()
