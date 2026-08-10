#!/usr/bin/python3
"""Compatibility wrapper for the LifePIM File Inventory scanner.

The old FileLister CSV batch process has been replaced by ``apps.files.scan``.
This wrapper keeps existing shortcuts/scripts from failing while routing all
work to the new inventory database.
"""

from __future__ import annotations

import os
import sys


def main(argv=None) -> int:
    repo_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    if repo_src not in sys.path:
        sys.path.insert(0, repo_src)
    from apps.files.scan import main as scan_main

    return scan_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
