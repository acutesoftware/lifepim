from datetime import datetime, timezone


HOW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lp_howto (
    howto_id              INTEGER PRIMARY KEY,
    howto_key             TEXT UNIQUE,
    title                 TEXT NOT NULL,
    project_id            TEXT,
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

CREATE INDEX IF NOT EXISTS ix_lp_howto_project ON lp_howto(project_id);
CREATE INDEX IF NOT EXISTS ix_lp_howto_status ON lp_howto(status);
CREATE INDEX IF NOT EXISTS ix_lp_howto_parse_status ON lp_howto(parse_status);
CREATE INDEX IF NOT EXISTS ix_lp_howto_updated ON lp_howto(updated_at);

CREATE TABLE IF NOT EXISTS lp_howto_parts (
    part_id          INTEGER PRIMARY KEY,
    part_key         TEXT UNIQUE,
    project_id       TEXT,
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
    project_id       TEXT,
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
    project_id           TEXT,
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


def ensure_how_schema(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(HOW_SCHEMA_SQL)
    conn.commit()
