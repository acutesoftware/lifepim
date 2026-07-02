-- =========================================
-- LifePIM Money
-- =========================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lp_money_assets (
    asset_id        INTEGER PRIMARY KEY,
    asset_type      TEXT NOT NULL DEFAULT 'other',
    name            TEXT NOT NULL,
    institution     TEXT,
    current_value   REAL NOT NULL DEFAULT 0,
    purchase_value  REAL NOT NULL DEFAULT 0,
    valuation_date  TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_assets_type_name
ON lp_money_assets (asset_type, name);

CREATE TABLE IF NOT EXISTS lp_money_loans (
    loan_id                INTEGER PRIMARY KEY,
    loan_type              TEXT NOT NULL DEFAULT 'other',
    lender                 TEXT NOT NULL,
    balance                REAL NOT NULL DEFAULT 0,
    interest_rate          REAL NOT NULL DEFAULT 0,
    repayment_amount       REAL NOT NULL DEFAULT 0,
    repayment_frequency    TEXT,
    next_payment_date      TEXT,
    notes                  TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_loans_type_lender
ON lp_money_loans (loan_type, lender);

CREATE TABLE IF NOT EXISTS lp_money_income (
    income_id      INTEGER PRIMARY KEY,
    income_type    TEXT NOT NULL DEFAULT 'other',
    source         TEXT NOT NULL,
    amount         REAL NOT NULL DEFAULT 0,
    frequency      TEXT NOT NULL DEFAULT 'monthly',
    next_date      TEXT,
    taxable        INTEGER NOT NULL DEFAULT 1,
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_income_type_source
ON lp_money_income (income_type, source);

CREATE TABLE IF NOT EXISTS lp_money_bills (
    bill_id      INTEGER PRIMARY KEY,
    bill_type    TEXT NOT NULL DEFAULT 'other',
    supplier     TEXT NOT NULL,
    amount       REAL NOT NULL DEFAULT 0,
    frequency    TEXT NOT NULL DEFAULT 'monthly',
    due_date     TEXT,
    autopay      INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_bills_due_supplier
ON lp_money_bills (due_date, supplier);

CREATE TABLE IF NOT EXISTS lp_money_tax_deductions (
    deduction_id   INTEGER PRIMARY KEY,
    purchase_date  TEXT NOT NULL,
    supplier       TEXT NOT NULL,
    item           TEXT NOT NULL,
    amount         REAL NOT NULL DEFAULT 0,
    reason         TEXT NOT NULL,
    tax_year       TEXT,
    receipt_path   TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_tax_year_date
ON lp_money_tax_deductions (tax_year, purchase_date);

-- Planned purchases. This table existed before the full Money module and is
-- preserved for tests and existing data.
CREATE TABLE IF NOT EXISTS lp_money_plans (
    plan_id         INTEGER PRIMARY KEY,
    item            TEXT NOT NULL,
    domain          TEXT NOT NULL DEFAULT 'General',
    estimated_cost  REAL NOT NULL DEFAULT 0,
    target_date     TEXT,
    priority        INTEGER NOT NULL DEFAULT 3 CHECK(priority BETWEEN 1 AND 5),
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

CREATE TABLE IF NOT EXISTS lp_money_share_watchlist (
    watch_id          INTEGER PRIMARY KEY,
    symbol            TEXT NOT NULL,
    market            TEXT,
    company_name      TEXT,
    target_price      REAL NOT NULL DEFAULT 0,
    current_price     REAL NOT NULL DEFAULT 0,
    price_updated_at  TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_money_watch_symbol_market
ON lp_money_share_watchlist (symbol, market);

CREATE TABLE IF NOT EXISTS lp_money_share_trades (
    trade_id           INTEGER PRIMARY KEY,
    symbol             TEXT NOT NULL,
    market             TEXT,
    trade_date         TEXT,
    quantity           REAL NOT NULL DEFAULT 0,
    pretend_buy_price  REAL NOT NULL DEFAULT 0,
    current_price      REAL NOT NULL DEFAULT 0,
    fees               REAL NOT NULL DEFAULT 0,
    price_updated_at   TEXT,
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_money_trades_symbol_date
ON lp_money_share_trades (symbol, trade_date);

CREATE TRIGGER IF NOT EXISTS trg_money_assets_updated
AFTER UPDATE ON lp_money_assets
FOR EACH ROW BEGIN
    UPDATE lp_money_assets SET updated_at = datetime('now') WHERE asset_id = NEW.asset_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_loans_updated
AFTER UPDATE ON lp_money_loans
FOR EACH ROW BEGIN
    UPDATE lp_money_loans SET updated_at = datetime('now') WHERE loan_id = NEW.loan_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_income_updated
AFTER UPDATE ON lp_money_income
FOR EACH ROW BEGIN
    UPDATE lp_money_income SET updated_at = datetime('now') WHERE income_id = NEW.income_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_bills_updated
AFTER UPDATE ON lp_money_bills
FOR EACH ROW BEGIN
    UPDATE lp_money_bills SET updated_at = datetime('now') WHERE bill_id = NEW.bill_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_tax_updated
AFTER UPDATE ON lp_money_tax_deductions
FOR EACH ROW BEGIN
    UPDATE lp_money_tax_deductions SET updated_at = datetime('now') WHERE deduction_id = NEW.deduction_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_plans_updated
AFTER UPDATE ON lp_money_plans
FOR EACH ROW BEGIN
    UPDATE lp_money_plans SET updated_at = datetime('now') WHERE plan_id = NEW.plan_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_watch_updated
AFTER UPDATE ON lp_money_share_watchlist
FOR EACH ROW BEGIN
    UPDATE lp_money_share_watchlist SET updated_at = datetime('now') WHERE watch_id = NEW.watch_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_money_trades_updated
AFTER UPDATE ON lp_money_share_trades
FOR EACH ROW BEGIN
    UPDATE lp_money_share_trades SET updated_at = datetime('now') WHERE trade_id = NEW.trade_id;
END;
