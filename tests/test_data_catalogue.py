import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + "src")
if root_folder not in sys.path:
    sys.path.append(root_folder)

try:
    import pandas  # noqa: F401
    HAS_PANDAS = True
except ModuleNotFoundError:
    HAS_PANDAS = False

if HAS_PANDAS:
    from common import data as common_data
    from modules.data import catalogue


@unittest.skipUnless(HAS_PANDAS, "pandas is required for data catalogue CSV/Excel scans")
class TestDataCatalogue(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.old_conn = common_data.conn
        common_data.conn = self.conn
        catalogue.ensure_schema(self.conn)

    def tearDown(self):
        common_data.conn = self.old_conn
        self.conn.close()
        self.tmpdir.cleanup()

    def test_csv_folder_scans_files_as_tables_and_previews_rows(self):
        folder = self.root / "statements"
        folder.mkdir()
        (folder / "bank_2025.csv").write_text("date,amount\n2025-01-01,10.50\n2025-01-02,20.00\n", encoding="utf-8")
        (folder / "bank_2026.csv").write_text("date,amount\n2026-01-01,15.00\n", encoding="utf-8")

        source_id = catalogue.save_source(
            None,
            {
                "source_name": "Bank Statements",
                "source_type": "csv_folder",
                "root_path": str(folder),
                "database_name": "statements",
                "recursive_scan": "on",
                "scan_columns": "on",
                "is_active": "on",
            },
            "DATABASE",
        )

        catalogue.scan_source(source_id)
        tables = catalogue.table_list({"source_id": str(source_id)})
        names = {table["object_name"] for table in tables}

        self.assertEqual(catalogue.source_get(source_id)["source_type"], "CSV_FOLDER")
        self.assertEqual(names, {"bank_2025.csv", "bank_2026.csv"})
        self.assertTrue(all(table["object_type"] == "CSV_TABLE" for table in tables))

        table = next(item for item in tables if item["object_name"] == "bank_2025.csv")
        columns = catalogue.object_columns(table["data_object_id"])
        preview = catalogue.preview_object_rows(table["data_object_id"], limit=100)

        self.assertEqual([column["column_name"] for column in columns], ["date", "amount"])
        self.assertEqual(preview["columns"], ["date", "amount"])
        self.assertEqual(preview["rows"][0], ["2025-01-01", "10.5"])


if __name__ == "__main__":
    unittest.main()
