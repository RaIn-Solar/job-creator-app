# 🧰 Solbiz — Project Handoff (current)

**Repo:** `rain-solar/job-creator-app` (private, proprietary — see LICENSE)
**For:** ECC Solar (Rachel, rachel@eccsolar.com) — solar installer, statewide New Mexico
**Current build:** **Piece 15.1** (footer shows it plainly as "Version 15.1" — the "did my pull work?" check)
**Stack:** Flask + SQLite + Jinja templates. No JS framework. Pure Python; raw SQL (no ORM).
**Branch/workflow:** develop on `main`; bump the `VERSION` string in `app.py` each change;
commit + push after each feature so Rachel can pull (GitHub Desktop on Windows).

> Rachel is non-technical but competent. Explain the "why," give exact
> click-by-click steps, and **confirm the footer version after each update.**

## How to run
- **Dev:** `python -m pip install -r requirements.txt` then `python app.py` → http://127.0.0.1:5000
- **Desktop app (for the team):** `desktop/Build-Solbiz-Windows.bat` (built on Windows)
  produces a double-click `Solbiz.exe`; see `desktop/README-DESKTOP.md`. A known
  "exe flashes then closes" issue has its own guide: `desktop/DESKTOP_TROUBLESHOOTING_HANDOFF.md`.
- First run creates `job_creator.db` with 3 sample clients (one job each), 2 sample
  employees, sample tasks, and the full NM rule set + appliance/component catalogs.
- **Backups must include BOTH `job_creator.db` AND `uploads/`** (files live on disk).

---

# 1) Complete feature list, by page

Global chrome (`base.html`): green header with the **☀️ Solbiz** home link and a
top-right nav. Nav shows **📖 Directory · 🔌 Catalog · ⚙️ Rules · 👥 Employees ·
✅ Tasks · 🎒 Work Bag** for everyone, plus **🕗 Approvals (N) · 🧾 Log** for admins,
and the signed-in user's name (links to My account) + Log out. Every page has a
footer with the build version. Flash messages render at the top of `main`.

### Home / Clients — `/` (`index.html`)
- Lists all client profiles (name → profile, phone, mailing address, referral).
- **Search box** (clients + jobs) and a **＋ New client** button.
- **Live search preview (Piece 15):** as you type, a dropdown previews matching
  clients and jobs (via `/api/search`); Enter still runs the full search page.

### Search — `/search` (`search.html`)
- One box searches **clients** (name/address/phone/email) and **jobs**
  (name/site/county/products/client). Results link through; jobs show a status badge.

### Client profile — `/clients/<id>` (`client_detail.html`, tabbed)
- **✎ Edit client information** button (Piece 13.3).
- **Overview tab:** contact/address/referral/notes/"client since"; **Jobs** table
  (each with a **status badge**) + **＋ New job**.
- **Change note (Piece 15):** if the profile has been edited, a note shows how
  many times + last editor/date. Older values are hidden; **admins** get a
  **🔒 View change history** button (non-admins just see the note).
- **Documents tab (Piece 12):** client-level files (Contracts / Correspondence /
  Intake / Photos / Other), upload/download/delete — kept separate from job docs.

### New / Edit client — `/clients/new`, `/clients/<id>/edit` (`client_form.html`)
- All ECC intake fields. **Addresses are separate fields (Piece 15):** street /
  city / state (defaults NM) / ZIP for mailing and billing, with a "same as
  mailing address" helper that mirrors all four billing parts. The parts compose
  into the stored full-address strings used by search/roster/job pre-fill.
- Editing snapshots the outgoing values into `client_versions` (only when
  something actually changed); legacy single-line addresses drop into the street
  line so nothing is lost on first edit.

### Client change history — `/clients/<id>/history` (`client_history.html`, **admin**)
- The hidden older versions of a profile: each edit's prior values (full snapshot)
  with the changed-field labels flagged, who edited, and when. Newest first.

### Job profile — `/jobs/<id>` (`job_detail.html`, tabbed)
- Header buttons: **status picker** (Lead→Quoted→Sold→Permitting→Scheduled→Installed→Closed/Lost),
  **✎ Edit job**, **⚡ Loads & Sizing** (own page, Piece 15.1), **Process chart**,
  **← Client profile**.
- **Tabs (5):** General details · **LPC** · Materials · Documents · Tasks.
  ("LPC" is the abbreviated Licenses/Permits/Compliance tab, Piece 15.1; hover
  shows the full name.)
- **General details tab:** all job fields + **version history** (JSON snapshot per edit).
- **LPC tab (Licenses, Permits & Compliance):** requirements resolved live from the
  rules engine, grouped (Technician licenses / Permits / Compliance / Online Portals /
  Phone / Documents), each linked to its NM source + phone. **📎 filing-coverage
  badges** (N/M on file). License items show **👷 who on staff holds it** (green/amber/
  red by credential expiry) or **⚠ no one on staff holds this**. **⬇ Export report**.
- **Materials tab:** per-job material list — **fully inline-editable** rows
  (item/qty/unit/supplier/notes + Save), status dropdown, add, delete.
- **Documents tab:** upload/download/delete job files, optionally filed under a
  requirement (drives the coverage badges).
- **Tasks tab (Piece 10):** per-job tasks — inline-editable title/notes (Save),
  inline assignee/status/due (auto-save), overdue flag, add, delete. **⚙ Generate
  from process** (with optional install date) auto-creates the job's process-step
  checklist, auto-assigned by role and due-dated around the install.

### Loads & Sizing — `/jobs/<id>/loads` (`job_loads.html`, Piece 9; own page since 15.1)
- Reached from the **⚡ Loads & Sizing** button on the job header. Sales/Designer
  mode toggle; room-nested load survey (from the appliance catalog or custom);
  live daily-kWh/peak summary; **System Sizing** (off-grid/grid-tie presets → array
  kW/panel count, battery kWh/units, NEC 690.7 cold-temp Voc string sizing);
  **Components / bill of materials**.

### New / Edit job — `/clients/<id>/jobs/new`, `/jobs/<id>/edit` (`job_form.html`)
- All product/variant fields; service-ticket pre-fill from an existing job.

### Process chart — `/jobs/<id>/bpmn/view` (`bpmn_view.html`) + `/jobs/<id>/bpmn` download
- Per-job process as an ordered step list; downloadable BPMN 2.0 (bpmn.io/Camunda).

### Job report — `/jobs/<id>/report` — plain-text checklist download.
### Job version — `/jobs/<id>/versions/<v>` (`job_version.html`) — a prior snapshot + its resolved requirements.

### Rule directory — `/directory` (`directory.html`) — read-only, filterable rule browser (everyone).
### Rules manager — `/rules` (`rules.html`) — add/delete rules (**admin**); read-only for others.
### Catalog — `/catalog` (`catalog.html`) — appliance (379) + component (62) reference tables, add/delete (**admin**).

### Employees — `/employees` (`employees.html`)
- Roster with roles, credential tally + expiry warnings, schedule. **admin:**
  **🔑 Accounts** and **＋ New employee** buttons.

### Employee profile — `/employees/<id>` (`employee_detail.html`, tabbed)
- **Details** (roles, schedule); **Tasks** (assigned across all jobs); **Licenses &
  Certifications** (structured rows w/ expiry badges, "satisfies requirement" link,
  "copy on file"); **Documents** (credential copies). Edit/Delete + all add/delete
  controls are **admin-only**.

### New / Edit employee — `/employees/new`, `/employees/<id>/edit` (`employee_form.html`)
- Name, role checkboxes (27 ECC roles) + "other", schedule, and a **Login & access**
  section (admin): username, password, access level (Standard/Admin).

### Accounts — `/accounts` (`accounts.html`, **admin**)
- Who can sign in + access level + password-set status; employees without a login;
  and **⏳ Pending password changes** (approve/reject self-service requests).

### Task board — `/tasks` (`tasks.html`)
- Every task across all jobs; filter by person/unassigned and open/all; status tally +
  overdue count; inline status change; link to **🎒 My Work Bag**.

### Work Bag — `/work-bag` (`work_bag.html`) — the offline field page (Piece 14)
- The signed-in worker's assigned tasks, editable **offline** (saved in the browser);
  online/offline indicator; **Submit completed work** (work date + hours + note) →
  creates a **pending submission** for manager approval; tasks show "awaiting
  approval"; recent-submissions history. (No service worker yet — see limitations.)

### Field work approvals — `/submissions` (`submissions.html`, **admin**)
- Review Work Bag submissions: worker, work date, reported hours, note, the task
  changes; **confirm hours** then **Approve** (applies task changes + logs hours as
  authoritative) or **Reject** (applies nothing). Pending/All toggle.

### Audit log — `/audit` (`audit.html`, **admin**) — every state-changing request
(who/what/when/details/result), filterable by action. Passwords are redacted.

### My account — `/account` (`account.html`) — the signed-in user's page: **🎒 Work Bag**
link and **Change password** (submits for admin approval).

### Login — `/login` (`login.html`) — appears once at least one account exists.

---

# 2) Callouts already in the UI / code

**Access & accounts**
- Open-mode banner (until the first account exists): *"🔓 No logins set up. Anyone can
  access everything…"* with a link to Accounts.
- Last-admin safeguard: changing accounts can't leave the system with accounts but no
  admin — *"Keep at least one admin account — or remove every login to go back to open
  access."*
- Password self-service is admin-approved; the account page notes *"Forgot your
  password and can't sign in? An admin can reset it directly from your employee profile."*

**Work Bag / offline / approvals**
- Work Bag: *"Keep this page open while you're offline"* (reflects the no-service-worker
  limitation) and *"held for your manager to approve before it counts."*
- Approvals: *"Nothing here counts in the system until you approve it."*

**Rules engine / NM data (point-of-use warnings carried into rule `notes`)**
- Verification flags from the July 2026 Manual Review Log surface as "verify" notes
  (e.g., unverified utility domains/contacts, *"verify per project,"* *"verify current
  terms"*).
- Tax-credit / incentive caution in rule notes: SMDTC tier *"not confirmed — do not
  quote until verified with EMNRD"*; federal ITC note *"25D EXPIRED for expenditures
  after 12/31/2025 … consult a tax professional."*
- Situational rules carry qualifiers (*"if reinforcement needed," "confirm with AHJ,"
  "situational," "per tech on site"*).

**Loads & sizing**
- Sizing method note: NEC 690.7 cold-temp Voc + peak-sun-hour method, *"northern New
  Mexico design values — confirm against the specific site."*
- Component prices are planning estimates, not quotes (a few specs are engineering
  estimates — spot-check before a stamped design). Sales/Designer mode is labeled a
  *"view toggle, not access control."*

**Client change history (Piece 15)**
- Profile note: *"This profile has been changed N times…"* — for non-admins,
  *"Earlier information is hidden; an admin can review it."* The old values live
  only on the admin-only history page.

**Data / migration**
- Employee profile shows any pre-Piece-8.1 free-text credentials under *"Earlier
  free-text entry (from before structured tracking)"* with a nudge to re-enter as rows.
- Service tickets render the install pipeline provisionally with a caveat annotation
  in the BPMN.

**Desktop packaging** (`desktop/README-DESKTOP.md`)
- Expected Windows SmartScreen warning ("More info → Run anyway"); antivirus may flag
  an unsigned exe; the whole `Solbiz` folder (with `_internal`) must travel together;
  backups must include `job_creator.db` + `uploads/`.

---

# 3) Architecture essentials

- **Rules engine is data, not code.** Each row in `resource_rules` says "when job
  field X = value Y, the job needs Z (category License/Permit/Compliance/Link/Phone/
  Doc)." Rules may carry a second AND condition. `match_rules`/`group_rules` in
  `app.py` resolve them; editable in-app at `/rules`, browsable at `/directory`.
- **Seed batches** ship rule data in versioned batches applied once per DB (tracked by
  `meta.seed_version`). `SEED_RULES` (batch 1), `SEED_BATCHES` (2–10, with 10 =
  `NEW_RULES_V10` from `nm_directory.py`), and `SEED_BATCH_SQL` (one-off corrections).
  **Never edit a shipped batch — add a new number.** 145 rules at seed_version 10.
- **Self-upgrading DB:** `init_db()` runs `schema.sql` (all `CREATE TABLE IF NOT
  EXISTS`), `ensure_columns()` adds missing columns, and applies unseen batches — so
  existing databases upgrade in place. **Never require deleting `job_creator.db`.**
- **Auth (Piece 13):** logins live on the `employees` table (username/password_hash/
  access_level). Login is OFF until the first account exists (open mode). A
  `before_request` wall enforces login when active (401 JSON for `/api/*`);
  `@admin_required` guards shared-data + account + approval + audit routes. Admin vs
  Standard; passwords via werkzeug hashing.
- **Audit (Piece 11):** an `after_request` hook logs every POST/PUT/PATCH/DELETE
  centrally (actor once logged in; passwords redacted).
- **Work Bag / offline (Piece 14):** `job_tasks.updated_at` (ms) tracks changes;
  `/api/my-tasks` pulls, `/api/work-bag/submit` records a **pending** `field_submissions`
  (+ `field_submission_items`) copy without touching authoritative data; admin approval
  applies items to `job_tasks` and logs `approved_hours`. Client offline state is in
  `localStorage`.
- **Key files:** `app.py` (~2900 lines: config, routes, rules engine, auth, audit,
  sync); `nm_directory.py` (NM utility/AHJ data = batch 10 + pick-lists);
  `loads_seed.py` (379 appliances + 62 components); `bpmn_export.py`;
  `templates/` (Jinja; `base.html` holds styling + tab CSS + nav);
  `docs/reference/00–04*.md` (verified July-2026 NM permit/AHJ/utility source set).
- **Tables (23):** clients, client_versions, jobs, job_versions, job_materials,
  job_files, job_tasks, resource_rules, meta, employees, employee_credentials,
  employee_files, client_files, appliance_catalog, component_catalog,
  job_load_rooms, job_load_items, job_bom, job_sizing, password_requests,
  field_submissions, field_submission_items, audit_log.

# 4) Working conventions
- Bump `VERSION` in `app.py` per change; verify with a running server (curl + Playwright
  via bundled Chromium at `/opt/pw-browsers`) before committing.
- Test the seed-batch upgrade path on any rule change (simulate an older seed_version).
- Commit + push after each feature. Kill stray servers with `fuser -k 5000/tcp`.

# 5) Known limitations / deferred / next steps
- **No service worker yet** — Work Bag survives a dropped connection while open, but
  cold-starting the app fully offline needs a service worker (deliberately deferred as a
  support-risk item to field-test carefully). This is the natural next offline step.
- **"Manager" = Admin** for approvals; a specific manager→worker relationship is a
  future add.
- **Add/delete-only records** (rules, catalog, credentials, load items, BOM, rooms) have
  no in-place edit — re-add loses nothing there, but edit can be added on request.
- **No client/job delete** (intentional — would cascade).
- Suggested next: **hours summary / timesheet** from approved submissions; rule edit;
  the service worker.
