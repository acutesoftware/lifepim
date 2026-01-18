-- assumes the basic lifepim.db has been created
-- in the config.py > DB_PATH folder
-- run this SQL below to create all tables

CREATE TABLE IF NOT EXISTS map_project_folder (
    folder_id        INTEGER NOT NULL,

    -- Derived facets (copied from the winning rule)
    tab              TEXT NOT NULL,
    grp              TEXT NOT NULL,
    project          TEXT NULL,
    tags             TEXT NOT NULL DEFAULT '',
    confidence       REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- Traceability/debug
    matched_prefix   TEXT NOT NULL,      -- the path_prefix that won
    rule_map_id      INTEGER NOT NULL,   -- map_folder_project.map_id that won

    is_primary       INTEGER NOT NULL DEFAULT 1 CHECK (is_primary IN (0,1)),
    is_enabled       INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0,1)),

    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    -- Uniqueness: one folder can have multiple facets, but prevent duplicates
    PRIMARY KEY (folder_id, tab, grp, COALESCE(project,''), is_primary),

    FOREIGN KEY (folder_id) REFERENCES dim_folder(folder_id),
    FOREIGN KEY (rule_map_id) REFERENCES map_folder_project(map_id)
);

-- Fast sidebar queries
CREATE INDEX IF NOT EXISTS ix_mpf_tab
ON map_project_folder(tab);

CREATE INDEX IF NOT EXISTS ix_mpf_grp
ON map_project_folder(grp);

CREATE INDEX IF NOT EXISTS ix_mpf_project
ON map_project_folder(project);

-- Fast joins back to folders
CREATE INDEX IF NOT EXISTS ix_mpf_folder
ON map_project_folder(folder_id);

-- Helpful for rebuilds/debug
CREATE INDEX IF NOT EXISTS ix_mpf_rule
ON map_project_folder(rule_map_id);
