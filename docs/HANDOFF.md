# Solbiz — Project Handoff

**Repo:** `rain-solar/job-creator-app` (private, proprietary — see LICENSE)
**For:** ECC Solar (Rachel, rachel@eccsolar.com) — solar installer, northern/statewide New Mexico
**Current build:** Piece 7.3 (shown in every page footer)
**Stack:** Flask + SQLite + Jinja templates. No JS framework. Pure Python.

Solbiz is ECC's internal tool. Enter a job's facts once, and it resolves
every license, permit, and compliance item the job requires — each linked
to the authoritative NM state / utility / county source with phone numbers —
then tracks materials, documents, and the start-to-finish process.

---

## How to run

```
python -m pip install -r requirements.txt
python app.py          # http://127.0.0.1:5000
```

First run creates `job_creator.db` (SQLite) with two sample clients and a
sample job. Uploaded files live in `uploads/job_<id>/` (gitignored).
**Backups must include BOTH `job_creator.db` AND `uploads/`.**

Rachel runs this on Windows via GitHub Desktop (clone → Pull origin →
`python app.py`). She is non-technical but competent; explain the "why,"
give exact click-by-click steps, and confirm the footer version after each
update. The footer version label is the canonical "did my pull work" check.

---

## Architecture (the important mental model)

### The rules engine is the heart of the app
Every "if the job has field X = value Y, it needs requirement Z" decision is
a **row in the `resource_rules` table**, not code. 145 rules currently.
- `match_rules(job, rules)` (~20 lines in app.py) does the matching: a rule
  fires when the job's field equals the rule's value (case-insensitive), or
  for `match_type='contains'` when the value is in a comma-separated list
  (used for `products`). Rules may carry a **second AND condition**
  (`field_name2`/`field_value2`/`match_type2`) — e.g. Battery Banks AND
  property_type=Commercial.
- `group_rules()` groups matched rules by category (License, Permit,
  Compliance, Link/"Online Portals", Phone, Doc), de-duplicating on job
  pages (PV and Battery both need EE-98 → shown once).
- Rules are editable in-app at `/rules` (add/delete, no code) and browsable
  read-only at `/directory` (filter by job type + variants).

### Seed batches (critical — how rule data ships without breaking installs)
Rule data is seeded in **versioned batches** applied exactly once per
database, tracked by `meta.seed_version`. See `SEED_RULES` (batch 1) and
`SEED_BATCHES = {2:..., 10: NEW_RULES_V10}` plus `SEED_BATCH_SQL` (one-off
UPDATE/DELETE corrections per batch) in app.py.
**To ship new/changed rules: add a new batch number, never edit an already-
shipped batch.** This guarantees existing databases converge without
duplicating rules or resurrecting ones a user deleted on purpose. Tested
every time by simulating an older `seed_version` and asserting the count.

### Data model (schema.sql)
- `clients` — mailing/billing address, phone, email, referral source, notes
- `jobs` — client_id FK + all job fields (site_location, county,
  utility_provider, products [comma list], the three product-specific
  `*_utility_connection` columns, pv_mounting_type, pv_manufactured_house,
  service_type, property_type, cost_method, tax_credit, expand_option…)
- `resource_rules` — the rules engine (field_name/value/match_type,
  category, label, url, link_text, phone, notes, + AND-condition columns)
- `job_materials` — item/quantity/unit/supplier/status/notes per job
  (status: Needed/Ordered/Received/Installed)
- `job_files` — uploaded docs; `rule_label` optionally ties a file to a
  requirement (drives filing-coverage badges). Files on disk, not in DB.
- `job_versions` — JSON snapshot of a job's prior state on every edit
- `meta` — key/value (seed_version)

### Self-upgrading database
`init_db()` runs on startup: creates tables, `ensure_columns()` adds any
missing columns (schema evolves without manual migration), applies unseen
seed batches. **Any new column MUST be added to the relevant `*_FIELDS`
list AND handled in ensure_columns.** Existing user databases upgrade in
place — never require deleting job_creator.db.

### Key files
- `app.py` (~1320 lines) — all routes + rules engine + seed batches 1-9
- `nm_directory.py` — batch 10 (statewide NM utility/AHJ data + corrections)
  and the UTILITIES_ALL / COUNTIES_ALL pick-lists
- `bpmn_export.py` — per-job BPMN generation from the master pipeline
- `templates/` — base.html (styling, tab CSS), job_detail.html (tabbed),
  job_form.html, bpmn_view.html (step list), rules.html, directory.html, …
- `docs/reference/00-04*.md` — the **canonical July 2026 verified NM
  permit/AHJ/utility reference set**; every rule traces back here. The
  Manual Review Log (04) flags unverified data — those flags are carried
  into rule `notes` as "verify" warnings shown at point of use.
- `docs/The_Uber_Diagram.bpmn` — ECC's master process (the BPMN template)

---

## Feature status (Pieces 1-7 done)

1. Flask+SQLite skeleton; client list
2. Client profiles (mailing/billing addr, phone, email, referral)
3. Job profiles under clients (all ECC fields; product-specific options)
4. **Rules engine** — requirements resolve from fields; in-app rule
   manager + read-only directory; service tickets w/ pre-fill; text report
5. Job editing with JSON version history
6. **Per-job BPMN** — the master pipeline instantiated per job; permitting
   phase expands into resolved permits in dependency order; off-grid drops
   interconnection; JMEC gets Letter of Compliance; Authorities(CID) lane
7. **Materials list + document upload/storage**; filing coverage badges
   (N/M on file) reconcile documents against requirements

UI is now **tabbed** on the job page: General details (+ version history) ·
Licenses/Permits/Compliance · Materials · Documents. Tab state persists via
URL hash; form posts return to their tab. The Process page is a **step list**
(not a canvas — the diagram is export-only via bpmn.io/Camunda).

Branding: the app is **Solbiz** (ECC's internal software name; it literally
appears as a lane in their master BPMN). Demo data + rules are New Mexico
(NOT Texas — earlier builds used TX, all re-flavored to NM).

---

## Open backlog / explicitly deferred (with Rachel's stated intent)

- **Client-level document storage** — REQUESTED, not built. Rachel wants
  client files kept SEPARATE from jobs (one client → many jobs over time).
  Plan agreed: a `client_files` table sibling to `job_files`, own storage
  folder, Documents section on the client profile, with client-level
  categories (Contracts, Correspondence, Intake, Photos) — NOT the job
  requirement categories. Client profile page could gain tabs too.
- **Service-ticket process** — the BPMN install pipeline doesn't fit service
  tickets; they currently render provisionally with a caveat annotation.
  Needs its own simpler dispatch→service→invoice flow. Service requirements
  are correctly designed to resolve AFTER service fields are filled.
- **Cost-method payment variants** — 50/40/10 is the default; Rachel will
  define finance/cash/lease variants later. BPMN annotates the schedule
  with the cost method already.
- **Rule flights not yet provided** — Well Pump and Mini Split variant
  matrices (PV/Battery/Generator matrices are done). SMDTC 20%/battery tier
  is UNCONFIRMED (flagged do-not-quote per Manual Review Log B1).
- **.kmz site-file linking** — site_location field is built to anchor a KMZ
  link for GPS software later; KMZ/KML uploads already allowed.
- **Piece 8 polish** — search, job statuses (a `status` field exists on
  jobs but isn't surfaced), logins / role-based access (e.g. office can
  browse Directory but only admins edit Rules).
- **BPMN auto-layout** is functional but not pretty (straight connectors).

---

## Working conventions in this project
- Every change bumps the `VERSION` string in app.py and is verified with a
  running server (curl + Playwright screenshots via bundled Chromium at
  `/opt/pw-browsers`) before committing.
- Rachel's designated branch is `main`; commits are pushed as they land so
  she can pull. Commit + push after each feature.
- The seed-batch upgrade path is tested on EVERY rule change by simulating
  an older seed_version.
- Kill stray servers with `fuser -k 5000/tcp` (NOT pkill matching "app.py"
  — that has matched and killed the working shell before).
