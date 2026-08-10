"""Change classification helpers for File Inventory."""

from __future__ import annotations


def classify_change(existing, record) -> str:
    if not existing:
        return "NEW"
    if int(existing["is_deleted"] or 0):
        return "REACTIVATED"
    if int(existing["size"] or 0) != int(record.size):
        return "CHANGED"
    if (existing["date_modified"] or "") != record.date_modified:
        return "CHANGED"
    return "UNCHANGED"
