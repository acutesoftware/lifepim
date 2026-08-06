from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def database_size(db_path: str | Path) -> int:
    path = Path(db_path)
    if not path.exists():
        return 0
    total = path.stat().st_size
    for suffix in ("-wal", "-shm"):
        aux = Path(str(path) + suffix)
        if aux.exists():
            total += aux.stat().st_size
    return total


def replace_database(rebuild_path: Path, target_path: Path) -> Path | None:
    backup_path = None
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        from datetime import datetime, timezone

        checkpoint = sqlite3.connect(str(target_path))
        try:
            checkpoint.execute("PRAGMA wal_checkpoint(FULL)")
        finally:
            checkpoint.close()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = target_path.with_name(f"{target_path.name}.{stamp}.bak")
        os.replace(target_path, backup_path)
    for suffix in ("-wal", "-shm"):
        aux = Path(str(target_path) + suffix)
        if aux.exists():
            os.remove(aux)
    os.replace(rebuild_path, target_path)
    return backup_path
