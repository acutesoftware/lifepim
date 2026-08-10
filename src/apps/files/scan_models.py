"""Data models for the File Inventory scanner."""

from __future__ import annotations

from dataclasses import dataclass, field


SCAN_MODES = {"AUTO", "FULL", "INCREMENTAL", "SCOPED"}
SCAN_STATUSES = {"RUNNING", "SUCCESS", "FAILED", "CANCELLED"}
CHANGE_TYPES = {"NEW", "CHANGED", "DELETED", "REACTIVATED"}


@dataclass(frozen=True)
class FileSource:
    source_id: int
    name: str
    root_path: str
    enabled: bool = True
    provider_checkpoint: str = ""


@dataclass(frozen=True)
class FileRecord:
    fullfilename: str
    path: str
    xtn: str
    name: str
    date_modified: str
    date_created: str
    date_accessed: str
    size: int
    relative_path: str
    parent_relative_path: str
    normalized_relative_path: str
    normalized_path: str


@dataclass
class ScanResult:
    scan_id: int | None
    source_id: int
    scope: str
    requested_mode: str
    scan_mode: str
    status: str = "RUNNING"
    provider: str = ""
    files_seen: int = 0
    files_new: int = 0
    files_changed: int = 0
    files_unchanged: int = 0
    files_deleted: int = 0
    files_reactivated: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "source_id": self.source_id,
            "scope": self.scope,
            "requested_mode": self.requested_mode,
            "scan_mode": self.scan_mode,
            "status": self.status,
            "provider": self.provider,
            "files_seen": self.files_seen,
            "new": self.files_new,
            "changed": self.files_changed,
            "deleted": self.files_deleted,
            "reactivated": self.files_reactivated,
            "unchanged": self.files_unchanged,
            "errors": self.errors,
            "error_messages": list(self.error_messages),
        }
