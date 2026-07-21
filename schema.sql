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
    property_type    TEXT DEFAULT 'Residential',  -- Residential / Commercial
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 4: the rules engine. Each row: "when job.<field_name> matches
-- <field_value>, this job needs <label>". Categories group the output
-- (License / Permit / Compliance / Link / Phone / Doc). match_type
-- 'contains' is for list fields like products; 'equals' for single values.
-- Prior states of edited jobs, kept for recordkeeping. data is a JSON
-- snapshot of every job field at the moment it was replaced.
CREATE TABLE IF NOT EXISTS job_versions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id   INTEGER NOT NULL REFERENCES jobs(id),
    version  INTEGER NOT NULL,
    data     TEXT NOT NULL,
    saved_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 7: material list per job.
CREATE TABLE IF NOT EXISTS job_materials (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id),
    item       TEXT NOT NULL,
    quantity   TEXT DEFAULT '',
    unit       TEXT DEFAULT '',
    supplier   TEXT DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'Needed',  -- Needed/Ordered/Received/Installed
    notes      TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 7: uploaded documents per job; optionally tied to a requirement
-- label so the requirements panel can show filing coverage.
CREATE TABLE IF NOT EXISTS job_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES jobs(id),
    rule_label    TEXT DEFAULT '',   -- requirement this document satisfies
    stored_name   TEXT NOT NULL,     -- name on disk (uploads/job_<id>/)
    original_name TEXT NOT NULL,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- App metadata (e.g. which rule seed batches have been applied).
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Piece 8: the employee directory. ECC's crew, kept separate from
-- clients/jobs. Each row records who the person is (name), what they do
-- (roles — comma-separated selections), the licenses and certifications
-- they hold, and their working schedule.
CREATE TABLE IF NOT EXISTS employees (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    roles                   TEXT DEFAULT '',   -- comma-separated selections
    licenses_certifications TEXT DEFAULT '',   -- legacy free-text (Piece 8.0)
    schedule                TEXT DEFAULT '',
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 8.1: each license/certification an employee holds as its own row,
-- so expiry can be tracked and flagged. rule_label optionally ties the
-- credential to a License requirement in resource_rules, which lets a job
-- page show whether someone on staff holds the licenses it requires.
CREATE TABLE IF NOT EXISTS employee_credentials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    name        TEXT NOT NULL,
    rule_label  TEXT DEFAULT '',   -- License requirement this satisfies
    number      TEXT DEFAULT '',
    issued      TEXT DEFAULT '',   -- YYYY-MM-DD
    expires     TEXT DEFAULT '',   -- YYYY-MM-DD; blank = no expiry
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Piece 8.1: uploaded copies of an employee's credentials/documents;
-- optionally tied to one credential by name. Files live on disk in
-- uploads/employee_<id>/, not in the database.
CREATE TABLE IF NOT EXISTS employee_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    credential_name TEXT DEFAULT '',   -- credential this documents (optional)
    stored_name     TEXT NOT NULL,     -- name on disk
    original_name   TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL DEFAULT (datetime('now'))
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
    -- Optional second condition (AND): e.g. products includes Battery Banks
    -- AND property_type is Commercial.
    field_name2  TEXT DEFAULT '',
    field_value2 TEXT DEFAULT '',
    match_type2  TEXT DEFAULT 'equals',
    link_text    TEXT DEFAULT '',      -- display name for the url

    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
