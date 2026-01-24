"""Source adapters for importer."""

from __future__ import annotations

import csv
import os
import sqlite3
from typing import Iterable, Dict, List, Optional


class Source:
    def __init__(self, kind: str, source_system: Optional[str] = None):
        self.kind = kind
        self._source_system = source_system

    @property
    def source_system(self) -> str:
        return self._source_system or ""

    def get_columns(self) -> List[str]:
        raise NotImplementedError

    def iter_rows(self) -> Iterable[Dict[str, object]]:
        raise NotImplementedError


class CsvSource(Source):
    def __init__(self, path: str, encoding: str = "utf-8", delimiter: str = ","):
        super().__init__("csv", _derive_source_system(path))
        self.path = path
        self.encoding = encoding
        self.delimiter = delimiter

    def get_columns(self) -> List[str]:
        if not self.path or not os.path.exists(self.path):
            return []
        with open(self.path, newline="", encoding=self.encoding) as handle:
            reader = csv.reader(handle, delimiter=self.delimiter)
            return next(reader, [])

    def iter_rows(self) -> Iterable[Dict[str, object]]:
        if not self.path or not os.path.exists(self.path):
            return []
        handle = open(self.path, newline="", encoding=self.encoding)
        reader = csv.DictReader(handle, delimiter=self.delimiter)

        def _generator():
            try:
                for row in reader:
                    yield row
            finally:
                handle.close()

        return _generator()


class SqliteSource(Source):
    def __init__(self, db_path: str, sql: str, params=None):
        super().__init__("sqlite", _derive_source_system(db_path))
        self.db_path = db_path
        self.sql = sql
        self.params = params or ()

    def get_columns(self) -> List[str]:
        if not self.db_path or not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(self.sql, self.params)
            return [col[0] for col in (cur.description or [])]
        finally:
            conn.close()

    def iter_rows(self) -> Iterable[Dict[str, object]]:
        if not self.db_path or not os.path.exists(self.db_path):
            return []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(self.sql, self.params)

        def _generator():
            try:
                for row in cur:
                    yield dict(row)
            finally:
                conn.close()

        return _generator()


def csv_source(path: str, *, encoding: str = "utf-8", delimiter: str = ",") -> Source:
    return CsvSource(path, encoding=encoding, delimiter=delimiter)


def sqlite_source(db_path: str, *, sql: str, params=()) -> Source:
    return SqliteSource(db_path, sql=sql, params=params)


def _derive_source_system(path: str) -> str:
    if not path:
        return ""
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return name
