-- Job Creator database schema.
-- Clients: ECC Solar's intake fields (Piece 2, revised).
-- Jobs: job profiles stored under a client (Piece 3).
-- Resource rules arrive in Piece 4.

CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    mailing_address TEXT DEFAULT '',
    billing_address TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    referral_source TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id        INTEGER NOT NULL REFERENCES clients(id),
    job_name         TEXT DEFAULT '',   -- the name used in bookkeeping records
    site_location    TEXT DEFAULT '',   -- address or GPS coordinates; .kmz link planned
    county           TEXT DEFAULT '',
    electric_loads   TEXT DEFAULT '',
    utility_provider TEXT DEFAULT '',
    warranty_type    TEXT DEFAULT '',
    cost_method      TEXT DEFAULT '',
    tax_credit       TEXT DEFAULT 'No',
    expand_option    TEXT DEFAULT 'No',
    products         TEXT DEFAULT '',   -- comma-separated selections
    -- Product-specific options; blank unless the product is selected.
    pv_utility_connection        TEXT DEFAULT '',  -- Off-grid / Grid-tie / Backup system
    pv_mounting_type             TEXT DEFAULT '',  -- Roof mounted / Ground mount
    pv_manufactured_house        TEXT DEFAULT '',  -- Yes when roof mounted on a manufactured house
    generator_utility_connection TEXT DEFAULT '',  -- Off-grid / Grid-tie / Backup system
    battery_utility_connection   TEXT DEFAULT '',  -- Off-grid / Grid-tie / Backup system
    service_type     TEXT DEFAULT '',   -- General service / Warranty service
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 4: the rules engine. Each row: "when job.<field_name> matches
-- <field_value>, this job needs <label>". Categories group the output
-- (License / Permit / Compliance / Link / Phone / Doc). match_type
-- 'contains' is for list fields like products; 'equals' for single values.
-- App metadata (e.g. which rule seed batches have been applied).
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS resource_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    field_name  TEXT NOT NULL,
    field_value TEXT NOT NULL,
    match_type  TEXT NOT NULL DEFAULT 'equals',
    category    TEXT NOT NULL DEFAULT 'Compliance',
    label       TEXT NOT NULL,
    url         TEXT DEFAULT '',
    phone       TEXT DEFAULT '',
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
