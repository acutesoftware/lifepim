-- =========================================
-- LifePIM Money Plans (Planning list)
-- =========================================

PRAGMA foreign_keys = ON;

-- -------------------------
-- Planned spend (lightweight planning list)
-- -------------------------
-- status: 'idea' | 'planned' | 'bought' | 'cancelled'
-- priority: 1..5 (1=highest)
CREATE TABLE IF NOT EXISTS lp_money_plans (
    plan_id         INTEGER PRIMARY KEY,

    item            TEXT NOT NULL,
    domain          TEXT NOT NULL DEFAULT 'General',
    estimated_cost  REAL NOT NULL CHECK(estimated_cost > 0),

    target_date     TEXT,

    priority        INTEGER NOT NULL DEFAULT 3
                    CHECK(priority BETWEEN 1 AND 5),

    status          TEXT NOT NULL DEFAULT 'planned'
                    CHECK(status IN ('idea','planned','bought','cancelled')),

    notes           TEXT,

    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_plans_status_target
ON lp_money_plans (status, target_date);

CREATE INDEX IF NOT EXISTS idx_money_plans_domain_priority
ON lp_money_plans (domain, priority);

-- Keep updated_at fresh on edits
CREATE TRIGGER IF NOT EXISTS trg_money_plans_updated
AFTER UPDATE ON lp_money_plans
FOR EACH ROW
BEGIN
    UPDATE lp_money_plans
    SET updated_at = datetime('now')
    WHERE plan_id = NEW.plan_id;
END;

-- Optional seed data (uncomment to use)
-- INSERT INTO lp_money_plans (item, domain, estimated_cost, target_date, priority, status, notes)
-- VALUES
-- ('Good knife set one day', 'Food', 200, NULL, 3, 'idea', ''),
-- ('Tyres need replacing', 'Car', 900, date('now', '+7 months'), 2, 'planned', ''),
-- ('Movies when Minecraft2 comes out', 'Events', 40, NULL, 4, 'idea', '');
