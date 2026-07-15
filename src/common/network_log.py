from __future__ import annotations

import json
import os
from datetime import datetime, timezone


MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


def _log_path():
    return os.getenv("LIFEPIM_NETWORK_LOG") or os.path.join(os.getcwd(), "lp_network.log")


def _rotate_if_needed(path):
    try:
        if not os.path.exists(path) or os.path.getsize(path) < MAX_LOG_BYTES:
            return
        for idx in range(BACKUP_COUNT - 1, 0, -1):
            src = f"{path}.{idx}"
            dst = f"{path}.{idx + 1}"
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.replace(src, dst)
        first = f"{path}.1"
        if os.path.exists(first):
            os.remove(first)
        os.replace(path, first)
    except OSError:
        pass


def log_network(event, **fields):
    clean_fields = {}
    for key, value in fields.items():
        if value is None:
            continue
        if key.lower() in {"password", "token", "device_token", "authorization", "cookie", "content", "body", "markdown"}:
            clean_fields[key] = "[redacted]"
        else:
            clean_fields[key] = value
    try:
        path = _log_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _rotate_if_needed(path)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} {event} {json.dumps(clean_fields, ensure_ascii=True, default=str, sort_keys=True)}\n"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
    except Exception:
        pass


def network_log_path():
    return _log_path()
