from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class LoggerSourceFile:
    source_path: Path
    source_type: str
    device_id: str | None
    file_size_bytes: int
    modified_at_utc: datetime | None


@dataclass
class ImportResult:
    record_count: int = 0
    first_record_at_utc: datetime | None = None
    last_record_at_utc: datetime | None = None
    warnings: list[str] = field(default_factory=list)


class BaseLoggerImporter(Protocol):
    source_type: str

    def can_import(self, source_file: LoggerSourceFile) -> bool:
        ...

    def import_file(self, connection, ingest_file_id: int, source_file: LoggerSourceFile) -> ImportResult:
        ...


def utc_string(value: datetime | str | int | float | None) -> str | None:
    parsed = parse_utc(value)
    if not parsed:
        return None
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_utc(value: datetime | str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        number = float(value)
        if number > 10_000_000_000:
            number = number / 1000.0
        dt = datetime.fromtimestamp(number, timezone.utc)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return parse_utc(int(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d_%H-%M-%S"):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iter_json_records(path: Path):
    text_prefix = _read_prefix(path, 1).lstrip()
    if text_prefix.startswith("[") or text_prefix.startswith("{"):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, list):
            for index, item in enumerate(data):
                if isinstance(item, dict):
                    yield index, item
            return
        if isinstance(data, dict):
            for key in ("records", "samples", "events", "apps", "applications", "items", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    for index, item in enumerate(value):
                        if isinstance(item, dict):
                            yield index, item
                    return
            yield 0, data
            return
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                yield index, item


def read_csv_records(path: Path):
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|") if sample.strip() else csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        for index, row in enumerate(reader):
            yield index, {str(k or "").strip(): v for k, v in row.items()}


def pick(record: dict, *names):
    lowered = {str(key).lower(): value for key, value in record.items()}
    for name in names:
        if name in record and record.get(name) not in (None, ""):
            return record.get(name)
        value = lowered.get(str(name).lower())
        if value not in (None, ""):
            return value
    return None


def extra_json(record: dict, known: set[str]) -> str:
    extra = {key: value for key, value in record.items() if str(key).lower() not in known and value not in (None, "")}
    return json.dumps(extra, ensure_ascii=True, sort_keys=True, default=str) if extra else ""


def _read_prefix(path: Path, size: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read(size)
    except OSError:
        return ""
