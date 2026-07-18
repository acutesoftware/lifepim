import os
import re

from common import config as cfg


USER_PATH_COLUMNS = {
    "file_root_path": "TEXT",
    "notes_root_path": "TEXT",
    "projects_root_path": "TEXT",
    "lists_root_path": "TEXT",
}

_INVALID_SEGMENT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def normalize_path(path_value):
    path_value = (path_value or "").strip().strip('"').strip()
    if not path_value:
        return ""
    path_value = path_value.replace("/", "\\")
    if len(path_value) >= 2 and path_value[1] == ":":
        path_value = path_value[0].upper() + path_value[1:]
    if len(path_value) > 3 and path_value.endswith("\\"):
        path_value = path_value.rstrip("\\")
    return path_value


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


def safe_path_segment(value, default="user"):
    text = (value or "").strip()
    text = _INVALID_SEGMENT_CHARS.sub("_", text)
    text = re.sub(r"\s+", "_", text).strip(" ._")
    return text or default


def safe_project_folder_name(project_id, project_name=""):
    text = (project_id or project_name or "project").strip()
    text = text.replace("\\", "/").replace("/", "-").replace(".", "-")
    text = _INVALID_SEGMENT_CHARS.sub("-", text)
    text = re.sub(r"[^A-Za-z0-9._ -]+", "-", text)
    text = re.sub(r"[-\s]+", "-", text).strip(" .-_")
    return text or "project"


def default_lan_user_root_base():
    return normalize_path(
        os.getenv("LIFEPIM_LAN_USER_ROOT_BASE")
        or getattr(cfg, "LAN_USER_ROOT_BASE", r"N:\duncan\LifePIM_Data\DATA\lan_users")
    )


def default_paths_for_username(username):
    root = os.path.join(default_lan_user_root_base(), safe_path_segment(username))
    return paths_from_root(root)


def paths_from_root(root_path):
    root = normalize_path(root_path)
    return {
        "file_root_path": root,
        "notes_root_path": normalize_path(os.path.join(root, "notes")),
        "projects_root_path": normalize_path(os.path.join(root, "projects")),
        "lists_root_path": normalize_path(os.path.join(root, "lists")),
    }


def _notes_root_from_path(path_value):
    path_norm = normalize_path(path_value)
    parts = [part for part in path_norm.split("\\") if part]
    for idx in range(len(parts) - 1):
        if parts[idx].lower() == "data" and parts[idx + 1].lower() == "notes":
            return "\\".join(parts[: idx + 2])
    return ""


def _path_parent(path_value):
    path_norm = normalize_path(path_value)
    if not path_norm:
        return ""
    parts = path_norm.split("\\")
    if len(parts) <= 1:
        return ""
    return "\\".join(parts[:-1])


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
            "projects_root_path": normalize_path(os.path.join(root, "projects")),
            "lists_root_path": normalize_path(os.path.join(root, "lists")),
        }
    data_root = normalize_path(getattr(cfg, "data_folder", ""))
    if data_root:
        return paths_from_root(data_root)
    user_root = normalize_path(getattr(cfg, "user_folder", ""))
    return paths_from_root(os.path.join(user_root, "DATA") if user_root else "")


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
        "projects_root_path = ?",
        "lists_root_path = ?",
    ]
    values = [
        paths.get("file_root_path") or "",
        paths.get("notes_root_path") or "",
        paths.get("projects_root_path") or "",
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
        "projects_root_path = ?",
        "lists_root_path = ?",
    ]
    values = [
        normalized.get("file_root_path") or "",
        normalized.get("notes_root_path") or "",
        normalized.get("projects_root_path") or "",
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
        "SELECT user_id, username, file_root_path, notes_root_path, projects_root_path, lists_root_path "
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
