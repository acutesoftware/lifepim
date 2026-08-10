"""CLI entry point for LifePIM File Inventory scans."""

from __future__ import annotations

import argparse
import json
import os

from apps.files.inventory_db import connect, create_or_update_source, list_sources
from apps.files.scanner import scan_files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="LifePIM File Inventory scanner.")
    parser.add_argument("folder", nargs="?", default="", help="Folder to scan. This is the normal way to run the scanner.")
    parser.add_argument("--db", default="", help="File Inventory SQLite database path.")
    parser.add_argument("--source-id", type=int, default=None, help="Advanced: scan an existing configured source id.")
    parser.add_argument("--source-name", default="", help="Advanced: override the generated source name.")
    parser.add_argument("--root-path", default="", help="Folder to scan. Equivalent to positional folder.")
    parser.add_argument("--scope", default="/", help="Relative scan scope under the source root.")
    parser.add_argument("--mode", default="AUTO", choices=["AUTO", "FULL", "INCREMENTAL", "SCOPED", "auto", "full", "incremental", "scoped"])
    parser.add_argument("--list-sources", action="store_true", help="List configured sources and exit.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON result.")
    args = parser.parse_args(argv)

    conn = connect(args.db or None)
    try:
        if args.list_sources:
            rows = [dict(row) for row in list_sources(conn)]
            print(json.dumps(rows, indent=2, sort_keys=True) if args.json else rows)
            return 0
        root_path = args.root_path or args.folder
        source_id = args.source_id
        if root_path:
            source_id = create_or_update_source(
                conn,
                args.source_name or os.path.basename(os.path.normpath(root_path)) or root_path,
                root_path,
                enabled=True,
            )
        if not source_id:
            parser.error("folder path is required")
        conn.close()
        result = scan_files(source_id, scope=args.scope, mode=args.mode.upper(), db_path=args.db or None)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    payload = result.as_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"scan_id={payload['scan_id']} status={payload['status']} provider={payload['provider']} "
            f"seen={payload['files_seen']} new={payload['new']} changed={payload['changed']} "
            f"deleted={payload['deleted']} reactivated={payload['reactivated']} "
            f"unchanged={payload['unchanged']} errors={payload['errors']}"
        )
        for message in payload["error_messages"]:
            print(f"ERROR: {message}")
    return 0 if result.status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
