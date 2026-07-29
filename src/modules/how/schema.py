from datetime import datetime, timezone


HOW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_howto (
    howto_id              INTEGER PRIMARY KEY,
    howto_key             TEXT UNIQUE,
    title                 TEXT NOT NULL,
    area_id            TEXT,
    summary               TEXT,
    outcome               TEXT,
    check_content         TEXT,
    notes_content         TEXT,
    markdown_full_content TEXT,
    source_filepath       TEXT UNIQUE,
    source_type           TEXT NOT NULL DEFAULT 'markdown',
    status                TEXT NOT NULL DEFAULT 'draft',
    tags                  TEXT,
    estimated_minutes     INTEGER,
    difficulty            TEXT,
    last_verified         TEXT,
    source_modified       TEXT,
    parsed_at             TEXT,
    parse_status          TEXT NOT NULL DEFAULT 'NOT_PARSED',
    parse_message         TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_howto_area ON lp_howto(area_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_status ON lp_howto(status);
CREATE INDEX IF NOT EXISTS ix_lp_howto_parse_status ON lp_howto(parse_status);
CREATE INDEX IF NOT EXISTS ix_lp_howto_updated ON lp_howto(updated_at);

CREATE TABLE IF NOT EXISTS lp_howto_parts (
    part_id          INTEGER PRIMARY KEY,
    part_key         TEXT UNIQUE,
    area_id       TEXT,
    part_name        TEXT NOT NULL,
    default_unit     TEXT,
    description      TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lp_howto_part_links (
    howto_part_link_id INTEGER PRIMARY KEY,
    howto_id           INTEGER NOT NULL,
    part_id            INTEGER NOT NULL,
    item_order         INTEGER NOT NULL,
    quantity           REAL,
    unit               TEXT,
    optional           INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    source_line        INTEGER,
    FOREIGN KEY (howto_id) REFERENCES lp_howto(howto_id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES lp_howto_parts(part_id),
    UNIQUE (howto_id, item_order)
);

CREATE TABLE IF NOT EXISTS lp_howto_tools_needed (
    tool_id          INTEGER PRIMARY KEY,
    tool_key         TEXT UNIQUE,
    area_id       TEXT,
    tool_name        TEXT NOT NULL,
    description      TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lp_howto_tool_links (
    howto_tool_link_id INTEGER PRIMARY KEY,
    howto_id           INTEGER NOT NULL,
    tool_id             INTEGER NOT NULL,
    item_order          INTEGER NOT NULL,
    optional            INTEGER NOT NULL DEFAULT 0,
    notes               TEXT,
    source_line         INTEGER,
    FOREIGN KEY (howto_id) REFERENCES lp_howto(howto_id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES lp_howto_tools_needed(tool_id),
    UNIQUE (howto_id, item_order)
);

CREATE TABLE IF NOT EXISTS lp_howto_steps (
    step_id              INTEGER PRIMARY KEY,
    step_key             TEXT UNIQUE,
    area_id           TEXT,
    step_type            TEXT NOT NULL DEFAULT 'instruction',
    step_title           TEXT,
    instruction          TEXT NOT NULL,
    expected_result      TEXT,
    warning              TEXT,
    image_filepath       TEXT,
    default_optional     INTEGER NOT NULL DEFAULT 0,
    child_howto_ref      TEXT,
    child_howto_id       INTEGER,
    child_mode           TEXT DEFAULT 'linked',
    notes                TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    FOREIGN KEY (child_howto_id) REFERENCES lp_howto(howto_id)
);

CREATE TABLE IF NOT EXISTS lp_howto_step_links (
    howto_step_link_id INTEGER PRIMARY KEY,
    howto_id           INTEGER NOT NULL,
    step_id            INTEGER NOT NULL,
    step_order         INTEGER NOT NULL,
    optional_override  INTEGER,
    title_override     TEXT,
    notes_override     TEXT,
    source_line        INTEGER,
    FOREIGN KEY (howto_id) REFERENCES lp_howto(howto_id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES lp_howto_steps(step_id),
    UNIQUE (howto_id, step_order)
);

CREATE INDEX IF NOT EXISTS ix_lp_howto_part_links_howto ON lp_howto_part_links(howto_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_tool_links_howto ON lp_howto_tool_links(howto_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_step_links_howto ON lp_howto_step_links(howto_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_step_links_step ON lp_howto_step_links(step_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_steps_child ON lp_howto_steps(child_howto_id);

CREATE TABLE IF NOT EXISTS lp_howto_parse_messages (
    parse_message_id INTEGER PRIMARY KEY,
    howto_id         INTEGER,
    severity         TEXT NOT NULL,
    code             TEXT,
    message          TEXT NOT NULL,
    source_line      INTEGER,
    source_column    INTEGER,
    created_at       TEXT NOT NULL,
    FOREIGN KEY (howto_id) REFERENCES lp_howto(howto_id) ON DELETE CASCADE
);
"""


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


HOW_AREA_ID_TABLES = (
    "lp_howto",
    "lp_howto_parts",
    "lp_howto_tools_needed",
    "lp_howto_steps",
)


def _table_columns(conn, table_name):
    try:
        return {row["name"] if hasattr(row, "keys") else row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    except Exception:
        return set()


def _normalize_area_id(value):
    text = "" if value is None else str(value).strip()
    if text in {"proj", "project"}:
        return "area"
    if text.startswith("proj/"):
        return "area/" + text[5:]
    if text.startswith("project/"):
        return "area/" + text[8:]
    if text.startswith("proj."):
        return "area." + text[5:]
    if text.startswith("project."):
        return "area." + text[8:]
    return text


def _migrate_how_area_columns(conn):
    for table_name in HOW_AREA_ID_TABLES:
        columns = _table_columns(conn, table_name)
        if not columns:
            continue
        if "project_id" in columns and "area_id" not in columns:
            conn.execute(f"ALTER TABLE {table_name} RENAME COLUMN project_id TO area_id")
            columns.discard("project_id")
            columns.add("area_id")
        elif "project_id" in columns and "area_id" in columns:
            conn.execute(
                f"UPDATE {table_name} SET area_id = project_id "
                "WHERE COALESCE(area_id, '') = '' AND COALESCE(project_id, '') != ''"
            )
        if "area_id" in columns:
            rows = conn.execute(f"SELECT rowid AS migration_rowid, area_id FROM {table_name}").fetchall()
            for row in rows:
                rowid = row["migration_rowid"] if hasattr(row, "keys") else row[0]
                area_id = row["area_id"] if hasattr(row, "keys") else row[1]
                next_area_id = _normalize_area_id(area_id)
                if next_area_id != (area_id or ""):
                    conn.execute(
                        f"UPDATE {table_name} SET area_id = ? WHERE rowid = ?",
                        (next_area_id, rowid),
                    )


def ensure_how_schema(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    _migrate_how_area_columns(conn)
    conn.executescript(HOW_SCHEMA_SQL)
    _migrate_how_area_columns(conn)
    conn.commit()
