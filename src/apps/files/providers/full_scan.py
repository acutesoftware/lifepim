"""Recursive filesystem reconciliation provider."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from apps.files.scan_models import FileRecord


class FullScanProvider:
    name = "full_scan"

    def __init__(self):
        self.errors = []

    def iter_files(self, root_path: str, scope: str = "/"):
        self.errors = []
        scan_root = scoped_root(root_path, scope)
        for dir_path, dir_names, file_names in os.walk(scan_root, onerror=self._on_walk_error):
            dir_names[:] = [name for name in dir_names if name not in {".git", "__pycache__", "node_modules"}]
            for file_name in file_names:
                full_path = os.path.join(dir_path, file_name)
                try:
                    yield record_from_path(root_path, full_path)
                except OSError as exc:
                    self.errors.append(f"{full_path}: {exc}")

    def _on_walk_error(self, exc):
        self.errors.append(str(exc))


def scoped_root(root_path: str, scope: str = "/") -> str:
    root_path = os.path.abspath(root_path)
    scope_norm = normalize_scope(scope)
    if not scope_norm:
        return root_path
    candidate = os.path.abspath(os.path.join(root_path, scope_norm))
    root_cmp = os.path.normcase(root_path)
    candidate_cmp = os.path.normcase(candidate)
    if candidate_cmp != root_cmp and not candidate_cmp.startswith(root_cmp + os.sep):
        raise ValueError("Scope escapes source root.")
    return candidate


def normalize_scope(scope: str) -> str:
    text = (scope or "/").strip().strip('"').replace("\\", "/")
    if text in {"", "/", "."}:
        return ""
    text = text.strip("/")
    return os.path.normpath(text.replace("/", os.sep))


def record_from_path(root_path: str, full_path: str) -> FileRecord:
    full_path = os.path.abspath(full_path)
    root_path = os.path.abspath(root_path)
    stat = os.stat(full_path)
    rel = os.path.relpath(full_path, root_path).replace("\\", "/")
    parent = os.path.dirname(rel).replace("\\", "/")
    if parent == ".":
        parent = ""
    name = os.path.basename(full_path)
    xtn = os.path.splitext(name)[1].lower().lstrip(".")
    return FileRecord(
        fullfilename=full_path,
        path=os.path.dirname(full_path),
        xtn=xtn,
        name=name,
        date_modified=_timestamp_utc(stat.st_mtime),
        date_created=_timestamp_utc(stat.st_ctime),
        date_accessed=_timestamp_utc(stat.st_atime),
        size=int(stat.st_size),
        relative_path=rel,
        parent_relative_path=parent,
        normalized_relative_path=normalize_identity_path(rel),
        normalized_path=normalize_identity_path(full_path),
    )


def normalize_identity_path(path_value: str) -> str:
    return path_value.replace("\\", "/").strip("/").lower()


def _timestamp_utc(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
