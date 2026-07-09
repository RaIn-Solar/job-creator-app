-- Job Creator database schema.
-- Clients: ECC Solar's intake fields (Piece 2, revised).
-- Jobs: job profiles stored under a client (Piece 3).
-- Resource rules arrive in Piece 4.

CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    street_address  TEXT DEFAULT '',
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
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
