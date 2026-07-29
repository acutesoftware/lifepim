-- LifePIM Areas schema reference.
-- Runtime creation and migration are implemented in src/common/areas.py.

CREATE TABLE IF NOT EXISTS lp_areas (
    owner_user_id   INTEGER,
    area_id         TEXT NOT NULL,
    icon            TEXT,
    tab             TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    area_name       TEXT NOT NULL,
    is_header       INTEGER NOT NULL DEFAULT 0,
    is_system       INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'active',
    tags            TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    pinned          INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_utc     TEXT NOT NULL,
    updated_utc     TEXT NOT NULL,
    UNIQUE (owner_user_id, area_id)
);

CREATE INDEX IF NOT EXISTS idx_lp_areas_tab_group
ON lp_areas (owner_user_id, tab, group_name, sort_order, area_name);

CREATE INDEX IF NOT EXISTS idx_lp_areas_status
ON lp_areas (owner_user_id, status);

CREATE TABLE IF NOT EXISTS lp_area_folders (
    area_folder_id     INTEGER PRIMARY KEY,
    owner_user_id      INTEGER,
    area_id            TEXT NOT NULL,
    path_prefix        TEXT NOT NULL,
    folder_role        TEXT NOT NULL,
    create_type        TEXT NOT NULL DEFAULT 'none',
    is_write_enabled   INTEGER NOT NULL DEFAULT 0,
    confidence         REAL NOT NULL DEFAULT 1.0,
    tags               TEXT,
    notes              TEXT,
    sort_order         INTEGER NOT NULL DEFAULT 100,
    is_enabled         INTEGER NOT NULL DEFAULT 1,
    created_utc        TEXT NOT NULL,
    updated_utc        TEXT NOT NULL,
    UNIQUE (owner_user_id, area_id, path_prefix)
);

CREATE INDEX IF NOT EXISTS idx_lp_area_folders_area
ON lp_area_folders (owner_user_id, area_id, folder_role, sort_order);

CREATE INDEX IF NOT EXISTS idx_lp_area_folders_path
ON lp_area_folders (path_prefix);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lp_area_default_folder
ON lp_area_folders (owner_user_id, area_id)
WHERE folder_role = 'default' AND is_enabled = 1;
