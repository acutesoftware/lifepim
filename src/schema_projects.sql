-- LifePIM Projects schema reference.
-- Runtime creation and migration are implemented in src/common/projects.py.

CREATE TABLE IF NOT EXISTS lp_project_workspaces (
    project_id        INTEGER PRIMARY KEY,
    owner_user_id     INTEGER,
    name              TEXT NOT NULL,
    project_type      TEXT,
    description       TEXT,
    status            TEXT NOT NULL DEFAULT 'planned',
    start_date        TEXT,
    end_date          TEXT,
    parent_project_id INTEGER,
    icon              TEXT,
    comments          TEXT,
    sort_order        INTEGER NOT NULL DEFAULT 100,
    pinned            INTEGER NOT NULL DEFAULT 0,
    created_utc       TEXT NOT NULL,
    updated_utc       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_lp_project_workspaces_owner_status
ON lp_project_workspaces (owner_user_id, status, pinned, sort_order, name);

CREATE INDEX IF NOT EXISTS ix_lp_project_workspaces_parent
ON lp_project_workspaces (owner_user_id, parent_project_id);

CREATE TABLE IF NOT EXISTS lp_project_areas (
    project_area_id INTEGER PRIMARY KEY,
    owner_user_id   INTEGER,
    project_id      INTEGER NOT NULL,
    area_id         TEXT NOT NULL,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    created_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, project_id, area_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_project_areas_project
ON lp_project_areas (owner_user_id, project_id, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_project_areas_area
ON lp_project_areas (owner_user_id, area_id);

CREATE TABLE IF NOT EXISTS lp_project_items (
    project_item_id INTEGER PRIMARY KEY,
    owner_user_id   INTEGER,
    project_id      INTEGER NOT NULL,
    item_type       TEXT NOT NULL,
    item_id         TEXT NOT NULL,
    item_title      TEXT,
    section         TEXT,
    pinned          INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    is_primary      INTEGER NOT NULL DEFAULT 0,
    created_utc     TEXT NOT NULL,
    updated_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, project_id, item_type, item_id)
);

CREATE INDEX IF NOT EXISTS ix_lp_project_items_project
ON lp_project_items (owner_user_id, project_id, pinned, section, item_type, sort_order);

CREATE INDEX IF NOT EXISTS ix_lp_project_items_item
ON lp_project_items (owner_user_id, item_type, item_id, is_primary);
