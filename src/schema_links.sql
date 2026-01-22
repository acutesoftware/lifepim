-- =========================================
-- LifePIM Links
-- =========================================

CREATE TABLE IF NOT EXISTS lp_links (
    link_id INTEGER PRIMARY KEY,
    src_type TEXT NOT NULL,
    src_id TEXT NOT NULL,
    dst_type TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    link_type TEXT NOT NULL,
    label TEXT,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_utc TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'ui',
    context_type TEXT,
    context_id TEXT,
    UNIQUE (src_type, src_id, dst_type, dst_id, link_type)
);
