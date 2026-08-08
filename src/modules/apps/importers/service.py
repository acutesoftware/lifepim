import json
import os
from urllib.parse import urlsplit, urlunsplit

from modules.apps import schema as apps_model
from .base import AppImportResult, STATUS_EXISTS, STATUS_INVALID, STATUS_NEW
from .exe_icons import get_executable_icon_value


def normalize_duplicate_value(value, *, is_url=False):
    text = (value or "").strip().strip('"').strip()
    if not text:
        return ""
    if is_url:
        parts = urlsplit(text)
        if not parts.scheme or not parts.netloc:
            return text.rstrip("/").lower()
        netloc = parts.netloc.lower()
        scheme = parts.scheme.lower()
        path = parts.path.rstrip("/")
        return urlunsplit((scheme, netloc, path, parts.query, ""))
    expanded = os.path.expandvars(os.path.expanduser(text))
    expanded = expanded.replace("/", "\\")
    normalized = os.path.normpath(expanded)
    if len(normalized) > 3:
        normalized = normalized.rstrip("\\/")
    return normalized.lower()


def candidate_duplicate_key(candidate):
    action_type = (candidate.action_type or "").upper()
    target = candidate.target or ""
    if action_type == "OPEN_URL":
        value = normalize_duplicate_value(target, is_url=True)
        return f"url:{value}" if value else ""
    value = normalize_duplicate_value(target)
    return f"path:{value}" if value else ""


def _existing_app_keys(conn, owner_user_id=None):
    apps_model.ensure_apps_schema(conn)
    owner_user_id = apps_model._owner_user_id(owner_user_id)
    keys = set()
    app_rows = conn.execute(
        "SELECT app_id, path, repository_url, website_url FROM lp_app WHERE owner_user_id IS ? AND enabled = 1",
        (owner_user_id,),
    ).fetchall()
    for row in app_rows:
        for col_name in ("path",):
            value = normalize_duplicate_value(row[col_name])
            if value:
                keys.add(f"path:{value}")
        for col_name in ("repository_url", "website_url"):
            value = normalize_duplicate_value(row[col_name], is_url=True)
            if value:
                keys.add(f"url:{value}")

    action_rows = conn.execute(
        "SELECT action_type, command FROM lp_app_action WHERE owner_user_id IS ?",
        (owner_user_id,),
    ).fetchall()
    for row in action_rows:
        action_type = (row["action_type"] or "").upper()
        if action_type == "OPEN_URL":
            value = normalize_duplicate_value(row["command"], is_url=True)
            if value:
                keys.add(f"url:{value}")
        elif action_type in {"EXECUTABLE", "OPEN_FILE", "OPEN_FOLDER", "SYSTEM_DEFAULT"}:
            value = normalize_duplicate_value(row["command"])
            if value:
                keys.add(f"path:{value}")
    return keys


def mark_candidate_duplicates(candidates, conn=None, owner_user_id=None):
    conn = apps_model._get_conn(conn)
    existing = _existing_app_keys(conn, owner_user_id=owner_user_id)
    seen = set()
    for candidate in candidates:
        if candidate.status == STATUS_INVALID:
            candidate.selected = False
            continue
        key = candidate_duplicate_key(candidate)
        if not key:
            candidate.status = STATUS_INVALID
            candidate.selected = False
            candidate.metadata["error"] = candidate.metadata.get("error") or "No launch target found."
            continue
        if key in existing or key in seen:
            candidate.status = STATUS_EXISTS
            candidate.selected = False
        else:
            candidate.status = STATUS_NEW
            seen.add(key)
    return candidates


def import_selected_candidates(candidates, conn=None, owner_user_id=None):
    conn = apps_model._get_conn(conn)
    apps_model.ensure_apps_schema(conn)
    owner_user_id = apps_model._owner_user_id(owner_user_id)
    result = AppImportResult()
    mark_candidate_duplicates(candidates, conn=conn, owner_user_id=owner_user_id)
    for candidate in candidates:
        if candidate.status == STATUS_EXISTS:
            result.skipped_existing_count += 1
            continue
        if candidate.status != STATUS_NEW or not candidate.importable:
            result.skipped_invalid_count += 1
            continue
        if not candidate.selected:
            result.skipped_unselected_count += 1
            continue
        try:
            app_id = _create_candidate_app(candidate, conn=conn, owner_user_id=owner_user_id)
            result.imported_count += 1
            result.created_app_ids.append(app_id)
        except Exception as exc:
            result.errors.append(f"{candidate.name}: {exc}")
    return result


def _create_candidate_app(candidate, conn=None, owner_user_id=None):
    now = apps_model._utc_now()
    icon = _candidate_icon(candidate)
    metadata_json = json.dumps(candidate.metadata or {}, sort_keys=True)
    description = candidate.description or _description_from_metadata(candidate.metadata)
    values = {
        "title": candidate.name,
        "kind": candidate.kind,
        "description": description,
        "icon": icon,
        "enabled": "1",
        "path": candidate.target,
        "repository_url": (candidate.metadata or {}).get("repository_url", ""),
        "website_url": candidate.target if (candidate.action_type or "").upper() == "OPEN_URL" else "",
        "comments": _comments_with_metadata(candidate, metadata_json),
        "area_ids": [candidate.area_id] if candidate.area_id else [],
        "actions": [
            {
                "action_name": candidate.action_name or "Open",
                "action_type": candidate.action_type,
                "command": candidate.target,
                "working_directory": candidate.working_directory,
                "arguments": candidate.arguments,
                "sort_order": 0,
                "is_default": 1,
            }
        ],
        "import_source": candidate.source_type,
        "import_source_path": candidate.source_path,
        "imported_date": now,
        "import_metadata": metadata_json,
    }
    return apps_model.create_app(values, conn=conn, owner_user_id=owner_user_id)


def _description_from_metadata(metadata):
    hints = metadata.get("project_hints") if metadata else None
    if hints:
        return " / ".join(hints)
    return ""


def _candidate_icon(candidate):
    icon = candidate.icon or ""
    if (candidate.action_type or "").upper() == "EXECUTABLE":
        extracted = get_executable_icon_value(candidate.target)
        if extracted:
            candidate.metadata["extracted_icon"] = extracted
            return extracted
    return icon


def _comments_with_metadata(candidate, metadata_json):
    parts = []
    if candidate.source_path:
        parts.append(f"Imported from {candidate.source_type}: {candidate.source_path}")
    if metadata_json and metadata_json != "{}":
        parts.append(f"Import metadata: {metadata_json}")
    return "\n".join(parts)
