#!/usr/bin/python3
# coding: utf-8
# importer.py - CSV import helpers

import csv
import os
import tempfile

from werkzeug.exceptions import RequestEntityTooLarge

from common import config as cfg
from common import data

tmp_dir = os.path.join(cfg.user_folder, 'tmp_imports')
MAX_IMPORT_BYTES = int(os.getenv("LIFEPIM_MAX_IMPORT_BYTES", str(20 * 1024 * 1024)))
MAX_IMPORT_ROWS = int(os.getenv("LIFEPIM_MAX_IMPORT_ROWS", "100000"))
MAX_PREVIEW_ROWS = int(os.getenv("LIFEPIM_MAX_IMPORT_PREVIEW_ROWS", "500"))
MAX_CSV_FIELD_BYTES = int(os.getenv("LIFEPIM_MAX_CSV_FIELD_BYTES", str(1024 * 1024)))
csv.field_size_limit(MAX_CSV_FIELD_BYTES)

TOKEN_VALUES = {
    "curr_area_selected": "",
}


def set_token(name, value):
    TOKEN_VALUES[name] = value or ""


def _resolve_value(mapping_value, row):
    if mapping_value is None:
        return ""
    if isinstance(mapping_value, str):
        if mapping_value.strip().upper() == "NULL" or mapping_value.strip() == "":
            return ""
        if mapping_value.startswith("{") and mapping_value.endswith("}"):
            token_name = mapping_value[1:-1]
            return TOKEN_VALUES.get(token_name, "")
        if mapping_value in row:
            return row.get(mapping_value, "")
        return mapping_value
    return ""


def save_upload(file_storage, suffix=".csv"):
    if file_storage is None or file_storage.filename == "":
        return ""
    os.makedirs(tmp_dir, exist_ok=True)
    if not suffix.startswith(".") or any(char not in ".abcdefghijklmnopqrstuvwxyz0123456789" for char in suffix):
        suffix = ".dat"
    handle, path = tempfile.mkstemp(prefix="import_", suffix=suffix, dir=tmp_dir)
    os.close(handle)
    file_storage.save(path)
    if os.path.getsize(path) > MAX_IMPORT_BYTES:
        os.remove(path)
        raise RequestEntityTooLarge(
            description=f"Import file exceeds the {MAX_IMPORT_BYTES // (1024 * 1024)} MiB limit."
        )
    return path


def is_saved_upload(path, suffix=None):
    """Return True only for an existing file created in the import temp folder."""
    if not path:
        return False
    try:
        resolved = os.path.realpath(path)
        root = os.path.realpath(tmp_dir)
        if os.path.commonpath([resolved, root]) != root or not os.path.isfile(resolved):
            return False
    except (OSError, ValueError):
        return False
    return not suffix or resolved.lower().endswith(suffix.lower())


def preview_table_import(lp_tbl_name, csv_file_name, csv_cols_to_map):
    """Return the target rows produced by a CSV mapping without changing the database."""
    if not is_saved_upload(csv_file_name, ".csv"):
        raise ValueError("Please load the CSV file again.")
    tbl = next((t for t in cfg.table_def if t["name"] == lp_tbl_name), None)
    if not tbl:
        raise ValueError(f"Unknown table: {lp_tbl_name}")
    if len(csv_cols_to_map) != len(tbl["col_list"]):
        raise ValueError("csv_cols_to_map length must match table column list")
    preview = []
    with open(csv_file_name, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_number, row in enumerate(reader, 1):
            if row_number > MAX_PREVIEW_ROWS:
                break
            preview.append(
                {column: _resolve_value(mapping, row) for column, mapping in zip(tbl["col_list"], csv_cols_to_map)}
            )
    return preview


def read_csv_headers(csv_file_name):
    if not csv_file_name or not os.path.exists(csv_file_name):
        return []
    with open(csv_file_name, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        return next(reader, [])


def import_to_table(lp_tbl_name, csv_file_name, csv_cols_to_map):
    """
    Import rows from CSV into an lp_* table.

    :param lp_tbl_name: target table name in config.table_def
    :param csv_file_name: path to CSV file
    :param csv_cols_to_map: list of CSV column names or constants for each table column
    """
    if not os.path.exists(csv_file_name):
        raise FileNotFoundError(csv_file_name)
    tbl = next((t for t in cfg.table_def if t["name"] == lp_tbl_name), None)
    if not tbl:
        raise ValueError(f"Unknown table: {lp_tbl_name}")
    if len(csv_cols_to_map) != len(tbl["col_list"]):
        raise ValueError("csv_cols_to_map length must match table column list")

    inserted = 0
    with open(csv_file_name, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row_number, row in enumerate(reader, 1):
            if row_number > MAX_IMPORT_ROWS:
                raise ValueError(f"Import exceeds the {MAX_IMPORT_ROWS} row limit.")
            values = []
            for mapping_value in csv_cols_to_map:
                values.append(_resolve_value(mapping_value, row))
            record_id = data.add_record(data.conn, tbl["name"], tbl["col_list"], values)
            if record_id:
                inserted += 1
    return inserted
