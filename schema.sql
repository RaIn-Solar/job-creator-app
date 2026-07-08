-- Job Creator database schema.
-- Clients: ECC Solar's intake fields (Piece 2, revised).
-- Jobs and resource rules arrive in later pieces.

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
