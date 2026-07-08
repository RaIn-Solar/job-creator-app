-- Job Creator database schema.
-- Piece 1: the clients table. Jobs and resource rules arrive in later pieces.

CREATE TABLE IF NOT EXISTS clients (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    contact_name    TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    street          TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    state           TEXT DEFAULT '',
    zip             TEXT DEFAULT '',
    utility_company TEXT DEFAULT '',
    hoa_name        TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
