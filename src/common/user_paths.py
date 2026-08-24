import os
import re

from common import config as cfg


USER_PATH_COLUMNS = {
    "file_root_path": "TEXT",
    "notes_root_path": "TEXT",
    "areas_root_path": "TEXT",
    "lists_root_path": "TEXT",
}

_INVALID_SEGMENT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_PATH_SPLIT_RE = re.compile(r"[\\/]+")


def normalize_path(path_value):
    path_value = (path_value or "").strip().strip('"').strip()
    if not path_value:
        return ""
    if len(path_value) >= 2 and path_value[1] == ":":
        path_value = path_value[0].upper() + path_value[1:]
    path_value = _collapse_duplicate_separators(path_value)
    while _can_strip_trailing_separator(path_value):
        path_value = path_value[:-1]
    return path_value


def _collapse_duplicate_separators(path_value):
    sep = path_separator(path_value)
    if len(path_value) >= 2 and path_value[1] == ":":
        return path_value[:2] + re.sub(r"[\\/]+", lambda _match: sep, path_value[2:])
    if path_value.startswith(("\\\\", "//")):
        prefix = path_value[:2]
        return prefix + re.sub(r"[\\/]+", lambda _match: sep, path_value[2:])
    return path_value


def _can_strip_trailing_separator(path_value):
    if not path_value.endswith(("\\", "/")):
        return False
    if path_value in {"/", "\\"}:
        return False
    if len(path_value) == 3 and path_value[1] == ":" and path_value[2] in "\\/":
        return False
    return True


def path_separator(path_value):
    text = str(path_value or "")
    if "\\" in text:
        return "\\"
    if "/" in text:
        return "/"
    if len(text) >= 2 and text[1] == ":":
        return "\\"
    return os.sep


def join_path(root_path, *parts):
    root = normalize_path(root_path)
    if not root:
        return normalize_path(os.path.join(*[str(part) for part in parts if str(part or "")]))
    sep = path_separator(root)
    joined = root.rstrip("\\/")
    for part in parts:
        cleaned = str(part or "").strip().strip("\\/")
        if cleaned:
            joined += sep + cleaned
    return normalize_path(joined)


def split_path(path_value):
    path_norm = normalize_path(path_value)
    return [part for part in _PATH_SPLIT_RE.split(path_norm) if part]


def build_path_from_parts(reference_path, parts):
    parts = [part for part in parts if part]
    if not parts:
        return ""
    sep = path_separator(reference_path)
    reference = normalize_path(reference_path)
    prefix = ""
    if reference.startswith(("\\\\", "//")):
        prefix = sep * 2
    elif reference.startswith(("/", "\\")) and not (len(reference) >= 2 and reference[1] == ":"):
        prefix = sep
    built = prefix + sep.join(parts)
    if len(parts) == 1 and len(parts[0]) == 2 and parts[0][1] == ":":
        built += sep
    return normalize_path(built)


def path_key(path_value):
    return normalize_path(path_value).replace("\\", "/").rstrip("/").lower()


def path_startswith(path_value, prefix):
    path = path_key(path_value)
    base = path_key(prefix)
    return bool(base and (path == base or path.startswith(base + "/")))


def is_absolute_path(path_value):
    path_norm = normalize_path(path_value)
    if not path_norm:
        return False
    if os.path.isabs(path_norm):
        return True
    if len(path_norm) >= 3 and path_norm[1] == ":" and path_norm[2] in "\\/":
        return True
    return path_norm.startswith(("\\\\", "//"))


def table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except Exception:
        return set()
    return {row[1] for row in rows}


def ensure_user_path_columns(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if not exists:
        return
    columns = table_columns(conn, "users")
    for column_name, column_type in USER_PATH_COLUMNS.items():
        if column_name not in columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
            columns.add(column_name)
    if "projects_root_path" in columns and "areas_root_path" in columns:
        conn.execute(
            "UPDATE users SET areas_root_path = projects_root_path "
            "WHERE COALESCE(areas_root_path, '') = '' AND COALESCE(projects_root_path, '') != ''"
        )


def safe_path_segment(value, default="user"):
    text = (value or "").strip()
    text = _INVALID_SEGMENT_CHARS.sub("_", text)
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return text or default


def safe_area_folder_name(area_id, area_name=""):
    text = (area_id or area_name or "area").strip()
    text = text.replace("\\", "/").replace("/", "-").replace(".", "-")
    text = _INVALID_SEGMENT_CHARS.sub("-", text)
    text = re.sub(r"[^A-Za-z0-9._ -]+", "-", text)
    text = re.sub(r"[-\s]+", "-", text).strip(" .-_")
    return text or "area"


def default_lan_user_root_base():
    return normalize_path(
        os.getenv("LIFEPIM_LAN_USER_ROOT_BASE")
        or getattr(cfg, "LAN_USER_ROOT_BASE", r"N:\duncan\LifePIM_Data\DATA\lan_users")
    )


def default_paths_for_username(username):
    root = join_path(default_lan_user_root_base(), safe_path_segment(username))
    return paths_from_root(root)


def paths_from_root(root_path):
    root = normalize_path(root_path)
    return {
        "file_root_path": root,
        "notes_root_path": join_path(root, "notes"),
        "areas_root_path": join_path(root, "areas"),
        "lists_root_path": join_path(root, "lists"),
    }


def _notes_root_from_path(path_value):
    path_norm = normalize_path(path_value)
    parts = split_path(path_norm)
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            return build_path_from_parts(path_norm, parts[: idx + 2])
    for idx in range(len(parts) - 3):
        if (
            parts[idx].lower() == "data"
            and parts[idx + 1].lower() == "lan_users"
            and parts[idx + 3].lower() == "notes"
        ):
            return build_path_from_parts(path_norm, parts[: idx + 4])
    return ""


def _path_parent(path_value):
    path_norm = normalize_path(path_value)
    if not path_norm:
        return ""
    parts = split_path(path_norm)
    if len(parts) <= 1:
        return ""
    return build_path_from_parts(path_norm, parts[:-1])


def derive_existing_notes_root(conn, user_id=None):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lp_notes'"
    ).fetchone()
    if not exists:
        return ""
    columns = table_columns(conn, "lp_notes")
    params = []
    where = "COALESCE(path, '') != ''"
    if user_id is not None and "owner_user_id" in columns:
        where += " AND owner_user_id = ?"
        params.append(user_id)
    rows = conn.execute(
        f"SELECT path, COUNT(1) AS cnt FROM lp_notes WHERE {where} GROUP BY path",
        params,
    ).fetchall()
    root_counts = {}
    root_display = {}
    for row in rows:
        root = _notes_root_from_path(row["path"])
        if not root:
            continue
        key = root.lower()
        root_display.setdefault(key, root)
        root_counts[key] = root_counts.get(key, 0) + int(row["cnt"] or 0)
    if not root_counts:
        return ""
    best_key = max(root_counts, key=root_counts.get)
    return root_display[best_key]


def legacy_paths_for_user(conn, user_id=None):
    notes_root = derive_existing_notes_root(conn, user_id=user_id)
    if not notes_root and user_id is not None:
        notes_root = derive_existing_notes_root(conn, user_id=None)
    if notes_root:
        root = _path_parent(notes_root)
        return {
            "file_root_path": root,
            "notes_root_path": notes_root,
            "areas_root_path": join_path(root, "areas"),
            "lists_root_path": join_path(root, "lists"),
        }
    data_root = normalize_path(getattr(cfg, "data_folder", ""))
    if data_root:
        return paths_from_root(data_root)
    user_root = normalize_path(getattr(cfg, "user_folder", ""))
    return paths_from_root(join_path(user_root, "DATA") if user_root else "")


def _row_paths(row):
    if not row:
        return {}
    paths = {}
    for column_name in USER_PATH_COLUMNS:
        value = normalize_path(row[column_name] if column_name in row.keys() else "")
        if value:
            paths[column_name] = value
    return paths


def get_user_paths(conn, user_id):
    ensure_user_path_columns(conn)
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return _row_paths(row)


def initialize_user_paths(
    conn,
    user_id,
    username,
    *,
    preserve_existing=False,
    create_dirs=False,
    force=False,
):
    ensure_user_path_columns(conn)
    if not force:
        existing = get_user_paths(conn, user_id)
        if all(existing.get(column_name) for column_name in USER_PATH_COLUMNS):
            return existing
    paths = (
        legacy_paths_for_user(conn, user_id=user_id)
        if preserve_existing
        else default_paths_for_username(username)
    )
    if create_dirs:
        for path_value in paths.values():
            if path_value:
                os.makedirs(path_value, exist_ok=True)
    columns = table_columns(conn, "users")
    set_clause = [
        "file_root_path = ?",
        "notes_root_path = ?",
        "areas_root_path = ?",
        "lists_root_path = ?",
    ]
    values = [
        paths.get("file_root_path") or "",
        paths.get("notes_root_path") or "",
        paths.get("areas_root_path") or "",
        paths.get("lists_root_path") or "",
    ]
    if "modified_at" in columns:
        set_clause.append("modified_at = CURRENT_TIMESTAMP")
    conn.execute(
        f"UPDATE users SET {', '.join(set_clause)} WHERE user_id = ?",
        values + [user_id],
    )
    return paths


def set_user_paths(conn, user_id, paths, *, create_dirs=False):
    ensure_user_path_columns(conn)
    normalized = {}
    for column_name in USER_PATH_COLUMNS:
        normalized[column_name] = normalize_path((paths or {}).get(column_name) or "")
    if create_dirs:
        for path_value in normalized.values():
            if path_value:
                os.makedirs(path_value, exist_ok=True)
    columns = table_columns(conn, "users")
    set_clause = [
        "file_root_path = ?",
        "notes_root_path = ?",
        "areas_root_path = ?",
        "lists_root_path = ?",
    ]
    values = [
        normalized.get("file_root_path") or "",
        normalized.get("notes_root_path") or "",
        normalized.get("areas_root_path") or "",
        normalized.get("lists_root_path") or "",
    ]
    if "modified_at" in columns:
        set_clause.append("modified_at = CURRENT_TIMESTAMP")
    conn.execute(
        f"UPDATE users SET {', '.join(set_clause)} WHERE user_id = ?",
        values + [user_id],
    )
    return normalized


def get_or_create_user_paths(conn, user_id, username=None, *, create_dirs=False):
    ensure_user_path_columns(conn)
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return {}
    paths = _row_paths(row)
    if all(paths.get(column_name) for column_name in USER_PATH_COLUMNS):
        return paths
    username = username or row["username"]
    preserve_existing = (username or "").strip().lower() == "duncan"
    return initialize_user_paths(
        conn,
        user_id,
        username,
        preserve_existing=preserve_existing,
        create_dirs=create_dirs,
        force=False,
    )


def backfill_duncan_user_paths(conn):
    ensure_user_path_columns(conn)
    rows = conn.execute(
        "SELECT user_id, username, file_root_path, notes_root_path, areas_root_path, lists_root_path "
        "FROM users WHERE lower(username) = 'duncan'"
    ).fetchall()
    for row in rows:
        paths = _row_paths(row)
        if all(paths.get(column_name) for column_name in USER_PATH_COLUMNS):
            continue
        initialize_user_paths(
            conn,
            row["user_id"],
            row["username"],
            preserve_existing=True,
            create_dirs=False,
            force=False,
        )
