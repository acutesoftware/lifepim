-- =========================================
-- LifePIM Contacts
-- =========================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS lp_contacts (
    contact_id      INTEGER PRIMARY KEY,
    display_name    TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    created_utc     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_utc     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_contacts_normalized
ON lp_contacts (normalized_name);

CREATE TABLE IF NOT EXISTS lp_contact_facts (
    fact_id       INTEGER PRIMARY KEY,
    contact_id    INTEGER NOT NULL,
    fact_type     TEXT NOT NULL,
    fact_value    TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_ref    TEXT,
    confidence    REAL,
    created_utc   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES lp_contacts(contact_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contact_facts_contact
ON lp_contact_facts (contact_id);

CREATE INDEX IF NOT EXISTS idx_contact_facts_type
ON lp_contact_facts (fact_type);

CREATE TRIGGER IF NOT EXISTS trg_contacts_updated
AFTER UPDATE ON lp_contacts
FOR EACH ROW
BEGIN
    UPDATE lp_contacts
    SET updated_utc = datetime('now')
    WHERE contact_id = NEW.contact_id;
END;
