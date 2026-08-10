"""Windows NTFS USN provider placeholder.

The provider is isolated so native USN support can be added without changing
the scanner contract. V1 falls back to a full reconciliation scan.
"""

from __future__ import annotations


class WindowsNtfsUsnProvider:
    name = "ntfs_usn"

    def is_available(self, source, checkpoint=None) -> bool:
        return False

    def get_changes_since(self, source, checkpoint):
        raise NotImplementedError("NTFS USN provider is not available in this build.")
