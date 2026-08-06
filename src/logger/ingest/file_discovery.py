from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from .base_importer import LoggerSourceFile


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".csv", ".tsv", ".txt"}


def discover_logger_files(mobile_source_path: Path | None = None, aggie_source_path: Path | None = None) -> list[LoggerSourceFile]:
    files: list[LoggerSourceFile] = []
    if mobile_source_path:
        files.extend(_discover_root(mobile_source_path, source_hint="mobile"))
    if aggie_source_path and (not mobile_source_path or aggie_source_path.resolve() != mobile_source_path.resolve()):
        files.extend(_discover_root(aggie_source_path, source_hint="aggie"))
    unique = {}
    for item in files:
        unique[str(item.source_path.resolve()).lower()] = item
    return sorted(unique.values(), key=lambda item: str(item.source_path).lower())


def _discover_root(root: Path, source_hint: str) -> list[LoggerSourceFile]:
    if not root or not root.exists() or not root.is_dir():
        return []
    items = []
    for current_root, _dirs, filenames in os.walk(root):
        for filename in filenames:
            path = Path(current_root) / filename
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            source_type = _source_type(path, root, source_hint)
            if not source_type:
                continue
            stat = path.stat()
            items.append(
                LoggerSourceFile(
                    source_path=path.resolve(),
                    source_type=source_type,
                    device_id=_device_id(path, root, source_hint),
                    file_size_bytes=stat.st_size,
                    modified_at_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                )
            )
    return items


def _source_type(path: Path, root: Path, source_hint: str) -> str:
    rel = path.relative_to(root).as_posix().lower()
    name = path.name.lower()
    if source_hint == "aggie" or "aggie" in rel or "window" in rel:
        return "aggie_window_usage"
    if "app_catalog" in rel or "inventory" in rel or "installed" in rel:
        return "mobile_app_inventory"
    if "phone_usage" in rel or "app_usage" in rel or "usage" in name or "application" in name:
        return "mobile_app_usage"
    return ""


def _device_id(path: Path, root: Path, source_hint: str) -> str | None:
    try:
        rel = path.relative_to(root)
        parts = rel.parts
    except ValueError:
        return None
    if source_hint == "mobile" and len(parts) >= 2:
        return parts[0]
    if source_hint == "aggie" and len(parts) >= 2:
        return parts[0]
    return None

