# 🧰 Solbiz — Project Handoff (current)

**Repo:** `rain-solar/job-creator-app` (private, proprietary — see LICENSE)
**For:** ECC Solar (Rachel, rachel@eccsolar.com) — solar installer, statewide New Mexico
**Current build:** **Piece 22.9** (footer shows it plainly as "Version 22.9" — the "did my pull work?" check)

**Piece 22.9 — "Team" nav dropdown (Employees + Payroll).** Employees and Payroll
now sit under a **👥 Team** `navdrop` — but only when `can_payroll` is true (so
the dropdown always has ≥2 items); users without payroll access get the plain
👥 Employees link as before. Same JS-free `<details>` pattern as Databases.

**Piece 22.8 — "Databases" nav dropdown + Inventory placeholder.** Header nav is
tidied: Client Profiles, Rules, Directory, Inventory, and Catalog now live inside
a single **🗄 Databases** dropdown (JS-free `<details class="navdrop">` +
`.navdrop-menu` CSS in base.html). New `/inventory` route → `inventory.html`, a
"coming soon" placeholder for the seed inventory DB (future designer →
procurement auto-fill). The dropdown carries the `margin-left:auto` in open mode
(previously on the Directory link). Employees/Tasks/Work Bag/Payroll/Approvals/
Log/Trash/Access stay as top-level links.

**Piece 22.7 — bolder headings on the installs & Closing panels.** "This week's
installs" and "Closing" get a heavier title (font-weight 800, 1.1rem) and a
larger tagline (0.92rem) for readability; other panels unchanged. (Structural
rework of these two tables still to come.)

**Piece 22.6 — "Ready for design" panel.** New Company-overview panel (under
Needs attention) listing the Sales→Designer hand-off queue: `gm["ready_design"]`
= Proposal jobs where `_loads_recorded()` is true (load survey captured — the
step before design) AND no Done task matching `LIKE '%finalize%design%'` (design
not finalized). Each row links to the job and to its Loads & Sizing page.

**Piece 22.5 — separate the Company-overview sub-sections.** Each of the five
sub-sections (Pipeline, Money in flight, Needs attention, This week's installs,
Closing) is now wrapped in its own `<section>` panel (`background:var(--bg)`,
border, radius, padding) so they read as distinct blocks; the count/money tiles
were given a white (`var(--card)`) fill so they pop against the panel. Shared
`panel`/`panelh`/`tile` inline-style vars set at the top of the block. Content
and column structure unchanged (installs + closing tables revisited next).

**Piece 22.4 — drop the Executive flat job list.** The generic "jobs in your
stages" section is now skipped on the Executive viewport
(`{% if s.stages and not (gm and s.name == "Executive") %}` in dashboard.html) —
it listed every active job and was redundant with the Company overview's
pipeline counts, this-week installs, and Closing worklist. Other viewports are
unchanged. (It was never an install-date window, despite the reading — it showed
all active jobs in Proposal..Closing.)

**Piece 22.3 — Executive (GM) company overview (Screen 6).** The dashboard route
builds a `gm` dict when `mode == "Executive"`: pipeline `counts` per stage
(Proposal..Closing), `money` totals (contract/collected/outstanding/expense via
`job_billing` over non-Lost jobs), `approvals` (pending field submissions),
`overdue` task count (open tasks past due on active jobs), `stalled` jobs (active
jobs whose newest `job_tasks.updated_at` is >14 days old — no-task jobs
excluded), `installs_week` (install_date in the next 7 days), and a `closing`
worklist (each Closing job's balance due = contract − collected, plus open/total
close-out steps and the next one). `dashboard.html` renders a ⭐ **Company
overview** card (tiles + tables) above the generic sections; the old standalone
Manager approvals card is suppressed when `gm` is present (folded in).

**Piece 22.2 — Loads & Sizing locks past Proposal.** Implements the 22.1 note.
`_loads_locked(job)` = job status is in `STAGE_ORDER` beyond Proposal (Lost, off
the normal order, stays editable). New `loads_unlocked` decorator (fetch_job +
lock check → flash + redirect) guards all eight loads-editing POSTs
(rooms/items/bom add+delete+toggle, sizing) — the view-only `set_ui_mode` toggle
stays open. `job_loads` passes `locked` to the template: a 🔒 lock banner shows,
the add/delete/toggle forms are hidden, and the sizing form is wrapped in a
`<fieldset disabled>` (values stay visible + greyed) with its Save button hidden.
Load survey, summary, and computed sizing outputs remain fully visible — and the
figures still surface read-only on the job General tab + in Design. Enforced both
UI-side and server-side.

**Piece 22.1 — "Packing list" rename.** The Work Bag materials list is now
labelled **📦 Packing list** (was "Load list") to avoid confusion with the
electrical **Loads & Sizing** tool.

**Piece 22.0 — Work Bag packing list.** `/api/my-tasks` returns
`materials_by_job` (item/quantity/unit/status for every job on the board); the
Work Bag JS renders a collapsible **📦 Packing list** under each job banner,
colour-coded by readiness via `matClass()` (Backordered→danger, Needed/Quoted→
warn, On hand/Received→green). Cached in `localStorage` (LS_MATS) so it works
offline. Lets installers pack the truck before leaving.

**Piece 21.9 — Work Bag field notes.** New `job_notes` table (job_id, note,
author, `created_at` default `datetime('now')` — the same clock as
`audit_log.ts`); each note is independently timestamped. `POST /work-bag/notes`
adds one (job + text required), `POST /work-bag/notes/<id>/delete` removes it
(author-scoped). A standard **📝 Job notes** card in `work_bag.html` (job picker +
textarea + the author's recent notes); the job's notes render newest-first as a
**📝 Field notes** card on the job_detail General tab (`job_notes` passed from the
route) so the office can read them later.

**Piece 21.8 — photo capture on every photo-requiring step.** `_is_photo_step`
now matches `PHOTO_STEP_KEYWORDS = ("photo", "picture", "site visit", "site
installation", "install walkthrough", "doc tube", "meter set", "re-inspect")`
instead of just "photo"/"picture", so the Work Bag camera button covers the
whole set of BPMN steps that need pictures: Site Visit, Site Installation, Crew
Install Walkthrough, Doc Tube and Pictures, Correct & Re-inspect, Meter set, and
Photograph Final Inspection Sticker. Keywords are deliberately specific
("install walkthrough"/"re-inspect" not bare "walkthrough"/"inspect") so the
Sales *Final Client Walkthrough* and the *Final CID Inspection* don't get a
camera they don't need. Retroactive — no schema/data change, purely detection.

**Piece 21.7 — Work Bag photo capture.** Any task whose title matches
`_is_photo_step()` ("photo"/"picture") grows a 📷 button in the Work Bag that
opens `work_bag_photos.html` (`GET/POST /work-bag/tasks/<id>/photos`) — a
phone-camera page (`<input accept="image/*" capture="environment" multiple>`,
auto-submits on pick). Uploads are stored as `job_files` tagged
`rule_label = FIELD_PHOTO_LABEL` ("Field Photo") + `task_id` (new TEXT column;
schema.sql + `ensure_columns`), image extensions only (`PHOTO_EXTENSIONS`).
New inline server route `GET /jobs/<job>/files/<id>/view` (as_attachment=False)
backs thumbnails; `/api/my-tasks` attaches `is_photo_step`, `photos_url` and a
`photos` list per task so the bag shows a live thumbnail strip. Field crews can
delete their own shots via `POST /work-bag/photos/<id>/delete` (scoped to
FIELD_PHOTO_LABEL, so it can't touch requirement docs — those stay GM-only).

**Piece 21.6 — Foreman / Installation viewport (Screen 5).** `FIELD_STAGES =
{"Installation", "Inspections"}`. Dashboard route: when `mode == "Installation"`
it builds `install_buckets` (This week / Upcoming / In inspection·unscheduled)
from the Installation section's jobs by parsing `install_date` against today,
and trims `my_tasks` to `FIELD_STAGES` (drops office steps like Set Installation
Date). `dashboard.html` renders the Installation section as three date-bucketed
tables (Install date · Client · Job · Progress) instead of the flat table.
Work Bag: `_my_tasks_rows` now also selects `pipeline_status`, `install_date`
and orders by install_date; `work_bag.html` JS filters to `FIELD_STAGES` and
clusters tasks **by job** under a header showing job · client · 🔧 install date
(office/scheduling tasks no longer clutter the crew's bag).

**Piece 21.5 — Receipts / invoices / bills.** New `doc_type` column on
`job_transactions` (`DOC_TYPES = ["Receipt", "Invoice", "Bill"]`; schema.sql
CREATE + `ensure_columns` upgrade for existing DBs; blank = plain ledger note).
`add_transaction` captures & validates it. Billing tab (`job_detail.html`) gains
a **Document** selector on the add form — picking one nudges Type/Status via
`txnDoc()` JS defaults (Invoice→Income/Outstanding, Bill→Expense/Outstanding,
Receipt→Expense/Paid, all still editable), a **Doc** column in the ledger table,
and a **paperwork-on-file** tally (`billing["docs"]` = per-type count+amount from
`job_billing`). `quickbooks_export` adds a **Document** column and an optional
`?doc=Receipt|Invoice|Bill` filter (validated; filename suffixed, e.g.
`solbiz_quickbooks_bills.csv`); the Finance dashboard Payments section links the
three per-document exports beside the full export. Rationale: QuickBooks imports
invoices (A/R), bills (A/P) and receipts through separate flows.

**Piece 21.4 — Permits/Warehouse viewport.** Permits dashboard jobs table gains a
**Permits X/Y** column (`permits_by_job` from `job_permit_coverage`, shown when
`s.name == "Permits"`). Purchasing dashboard gains a **Procurement** rollup
(`procurement`, material counts per status per Job-Prep job; Needed/Quoted/
Backordered highlighted) — placeholder for the future designer→inventory-sheet
auto-fill. `MATERIAL_STATUSES` expanded to Needed/Quoted/Ordered/Backordered/
Received/On hand/Installed. Job **L/P/C tab** reordered: Permits (+ portals/
phones) first and open, with an **inline per-permit file-upload slot** (merges
the requirement with filing); **Technician Licenses + Compliance collapsed at the
bottom** (Lead Installer owns those, not the Permit Coordinator).

**Piece 21.3 — payroll: self-log + approval + auto-OT + rate lock.** Employees
log their own hours from the Work Bag (`/work-bag/hours`, status Pending);
supervisors approve on the Payroll page (`approve_time_entry`/`reject_time_entry`)
— only Approved entries count in `payroll_summary`. Auto-overtime: `pay_types`
gains `ot_eligible`; per employee per ISO week, hours over the threshold earn the
OT premium (`ot_h × base × (mult−1)`). OT threshold + multiplier live in `meta`
(`_meta_get/_meta_set`, `ot_rules`), editable in Pay settings. The manual
"Overtime" pay type is gone from the seed; existing DBs set it/PTO/Holiday to
`ot_eligible=0`. `time_entries` gains `status/approved_by/approved_at` (existing
rows migrated to Approved). Rate editing (Pay settings + all save routes) gated
by `pay_rates_required` = `_can_edit_pay_rates` (GM or "Payroll Manager" role =
Cary + Lisa; exposed as `can_edit_pay_rates`). Payroll view stays
`payroll_required` (Finance/Admin/GM).

**Piece 21.2 — Payroll / hour tracking.** Tables `pay_types` (name, method
[multiplier/flat], value, sort, active), `pay_rates` (per-employee per-type
override), `time_entries` (employee, date, job, pay type, hours). Employee
`base_wage` column (ensure_columns, TEXT — coerce with `_to_float`). Pay math:
multiplier type → base_wage × value; flat type → value; per-employee override
beats the type default. `payroll_summary(db, start, end)` rolls up hours/$ per
employee per type. Pages: `/payroll` (period summary + log-hours form + entries)
and `/payroll/settings` (pay types + per-employee wages/overrides), gated by
`payroll_required` (`_can_payroll` = GM/Admin/Finance; exposed to templates as
`can_payroll` for the header link). `/payroll/quickbooks.csv` exports the period
as negative expense lines. Seeded pay types have placeholder values — ECC sets
real numbers in Pay settings.

**Piece 21.1:** login no longer treats the bare root "/" (Client Profiles) as a
post-login `next`, so everyone reliably lands on their own dashboard; real deep
links are still honored.
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
🏠 My Dashboard · ✅ Tasks · 🎒 Work Bag** for signed-in users, plus **🕗 Approvals (N) · 🧾 Log** for admins,
and the signed-in user's name (links to My account) + Log out. Every page has a
footer with the build version. Flash messages render at the top of `main`.

### My Dashboard — `/dashboard` (`dashboard.html`, Piece 19) — the sign-in landing
- Role-based home. Login redirects here. A person **belongs to a department** if they
  hold one of its roles (`DASHBOARD_DEPARTMENTS` / `user_departments`); the dashboard
  **stacks a section per department** they're in, plus a top **✅ My tasks** list
  (their open assigned tasks, stage-tagged) and — for Sales — **follow-ups due**, and
  — for Executive/GM — a **field-work approvals** callout.
- **Mode switch** (only if multi-department): **All** or focus on one department;
  the choice persists in the session, and **★ Make this my default** saves it to
  `employees.dashboard_mode` (the person's "working role"). Cary (holds every role)
  is seeded to default to **Design**; the GM keeps the full overview when in All.
- Each department section lists the **jobs currently in the stages that department
  works** (Permits → Job Prep/Inspections, Finance → Job Prep/Installation/Closing, …).
- Only active with logins on (needs a signed-in user). "All clients" link → Home.

### Home / Clients — `/` (`index.html`)
- Lists all client profiles (name → profile, phone, mailing address, referral);
  active **Leads** carry a "Lead" badge.
- **Search box** (clients + jobs) and a **＋ New client** button; admins see a
  **❄ Cold leads (N)** button.
- **Live search preview (Piece 15):** as you type, a dropdown previews matching
  clients and jobs (via `/api/search`); Enter still runs the full search page.
- **🔔 Follow-ups due (Piece 16):** leads on the 7-day / 2-week / 1-month cadence
  whose follow-up is due/overdue, each with **Enter job details** (convert),
  **✓ Logged**, and **❄ Cold** actions.

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
- All ECC intake fields, plus an **assigned sales rep** (Piece 16). **Addresses
  are separate fields (Piece 15):** street /
  city / state (defaults NM) / ZIP for mailing and billing, with a "same as
  mailing address" helper that mirrors all four billing parts. The parts compose
  into the stored full-address strings used by search/roster/job pre-fill.
- Editing snapshots the outgoing values into `client_versions` (only when
  something actually changed); legacy single-line addresses drop into the street
  line so nothing is lost on first edit.

### Client change history — `/clients/<id>/history` (`client_history.html`, **admin**)
- The hidden older versions of a profile: each edit's prior values (full snapshot)
  with the changed-field labels flagged, who edited, and when. Newest first.

### Cold leads — `/cold-leads` (`cold_leads.html`, **admin**, Piece 16)
- Leads marked cold, moved out of the active client list into a separate table.
  Rows older than **182 days (~6 months)** are flagged **purge?**; nothing
  auto-deletes. Actions: **↩ Restore** (back to active leads) / **✕ Delete**.

### Lead lifecycle (Piece 16, cross-cutting)
- Clients carry a `lead_status`: **Lead** (new prospect, in the follow-up cadence)
  → **Converted** (first job created) or moved to **Cold** (separate `cold_leads`
  table). An **assigned sales rep** owns the follow-ups. Follow-ups are generated
  on demand (home + task board load) at 7/14/30 days after creation; creating a
  job converts the lead and closes its open follow-ups.

### Job profile — `/jobs/<id>` (`job_detail.html`, tabbed)
- Header buttons: **status picker** (Piece 16: Proposal→Job Prep→Installation→Inspections→Closing→Complete, or Lost),
  **✎ Edit job**, **⚡ Loads & Sizing** (own page, Piece 15.1), **Process chart**,
  **← Client profile**.
- **Pipeline stage panel (Piece 18 / 18.1):** shows the current stage's **owning
  department** and the **head of each staffing function** (resolved live via
  `best_assignee_for_lane` from `STATUS_OWNERSHIP`), the **exit criteria**, a
  **stage-tasks progress** count (this stage's own tasks done / total), and an
  **✓ Advance to <next>** button (green when ready; a warned override otherwise).
  In **Job Prep** it also shows **permits filed (N/M)** + an **install-date** control;
  setting the install date once all permits are filed **auto-advances to Installation**.
  Every transition is soft-gated (`stage_info` → `ready`/`pending`, `next_stage`): the
  manual picker and the button both work, but advancing early flashes what's pending.
- **Standardized step→stage tagging (Piece 18.1):** each BPMN step carries a
  `pipeline_status` (`bpmn_export.STEP_STATUS`), so generated tasks are tagged by
  stage (`job_tasks.pipeline_status`) and each stage gates on *its own* tasks being
  Done. A one-time migration (`tag_tasks_by_stage`, `meta.tasks_stage_tagged`)
  back-fills existing tasks from title keywords (`TITLE_STATUS_KEYWORDS`).
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
  checklist, **auto-assigned to the most sensible role-holder** and due-dated around
  the install.
- **Role-based assignment (Piece 17.2):** `best_assignee_for_lane` maps a step's
  BPMN lane (via `LANE_TO_ROLES`) to the best person — preferring a real (non-demo),
  non-GM specialist with the fewest roles. A one-time migration (`assign_tasks_by_role`,
  `meta.tasks_role_assigned`) back-filled existing tasks: lane from the task's note,
  or inferred from title keywords (`TITLE_LANE_KEYWORDS`) for hand-added ones. It
  leaves tasks already assigned to real staff alone. Provisional — to be standardized.

### Calendar export (.ics) — Piece 20.0
- **`/calendar/my.ics`** (dashboard → *📅 Add my dates to calendar*): the signed-in
  person's task **due dates** + **install dates** for their jobs, as an all-day
  `.ics` calendar. In open mode exports everything.
- **`/jobs/<id>/calendar.ics`** (job header → *📅 Calendar*): that job's due dates +
  install date.
- Hand-rolled RFC-5545 builder (`build_ics`, no new deps); **stable UIDs**
  (`solbiz-task-<id>` / `solbiz-install-<id>`) so re-importing updates instead of
  duplicating. Import in Google Calendar via Settings → Import & export. Deliberately
  a **one-time import** for the desktop app; live two-way sync / availability waits
  for the hosted version + Workspace OAuth (see next steps).

### Finance viewport: billing ledger + QuickBooks — Piece 21.0
- New `job_transactions` table (schema.sql) + `jobs.contract_amount`
  (ensure_columns, TEXT affinity — coerce with `_to_float`). Constants
  `TXN_KINDS`, `TXN_STATUSES`, `INCOME_CATEGORIES`, `EXPENSE_CATEGORIES`,
  `PAYMENT_METHODS`. Helper `job_billing(db, job_id, contract)` → collected /
  outstanding / invoiced / uninvoiced / expense / net rollup + raw txns.
- Routes: `set_contract`, `add_transaction`, `toggle_transaction_paid`,
  `delete_transaction`, and `quickbooks_export` (`/finance/quickbooks.csv` —
  Date/Description/Amount first, signed +income/−expense, then detail columns).
- Job detail: **💵 Billing tab** (contract total, summary tiles, transaction
  table with paid toggle, add-transaction form with JS-swapped income/expense
  categories). Route passes `billing` + the txn constants.
- Finance dashboard: **Payments table** (all non-Lost jobs: contract / collected
  / outstanding / expenses / net + totals row + QuickBooks export button), gated
  on `show_payments = "Finance" in shown`. "jobs in your stages" progress column
  moved to the **rightmost** position for non-Proposal sections.

### Designer viewport + job-page overhaul — Piece 20.9
- **Dashboard:** Active Proposals gains a **Loads** column (✅/⬜ from
  `_loads_recorded`, via `loads_by_job`) so the Designer sees which proposals
  have loads recorded; Designer still sees all pending proposals.
- **Job detail restructure:** header is now job name → progress bar → a buttons
  row (status, Edit job, Process chart, Calendar, Client profile). **Loads &
  Sizing moved into the pipeline-stage panel**, next to the electric-loads
  indicator (prominent in Proposal, secondary elsewhere). **LPC tab renamed
  L/P/C.** General-details tab now surfaces the **saved load-survey summary**
  (daily kWh / peak W from `compute_load_totals`, `load_has_survey`).
- **Documents tab:** one **upload slot per needed file** — `STANDARD_JOB_DOCS`
  (Signed Contract, Site Photos, Design/One-Line, Site Plan) + the job's
  document-worthy requirements (Permit/Compliance/Doc only — licenses, portals,
  phones excluded). Each slot shows filed/needed status + filed files; an
  "Other documents" catch-all remains. Route passes `doc_sections`,
  `files_by_label`, `other_files`. (Per-slot format restrictions: TODO later.)
- **Loads & Sizing:** Load survey, Summary, System sizing are now collapsible
  `<details class="card sect">`. The load survey (job_load_rooms/items) already
  persists per job, so Sales' walkthrough numbers flow into the Designer's
  sizing math automatically.

### Sales dashboard tuning #2 — Piece 20.8
- Mode switch: **"All" removed** — always one role at a time. Route default mode
  is now `depts[0]` (no All view); `shown = [mode]`.
- Proposal-only jobs section reads **"Active Proposals"**; columns reordered to
  **Progress · Client (smaller) · Job · Install date**.
- **Client Profiles** dashboard section replaced by a **Leads** table (the
  landing-page follow-up/leads table): active `lead_status='Lead'` clients with
  their next open follow-up + rep + actions (Enter job details / ✓ Logged /
  ❄ Cold). Gated to the Sales viewport (`show_leads = "Sales" in shown`). The
  old separate "follow-ups due" card is folded into this. `mark_cold` now honors
  a `next` param so the action returns to the dashboard.

### Dashboard viewport pass #1 (Sales) — Piece 20.7
Working through each role's viewport in job-flow order; Sales first.
- Header nav gains a **🗂 Client Profiles** button (→ home). "All clients" button
  removed from the dashboard toolbar; **Make this my default** removed (route
  `set_dashboard_default` left in place, just unlinked).
- Dashboard sections are now **collapsible** (`<details class="card sect">` +
  `.sect` summary CSS in base.html). Reordered: department jobs → follow-ups →
  manager → **Client Profiles** → **My tasks (moved to the bottom)**.
- New **Client Profiles** list on the dashboard (`client_profiles` from the
  `dashboard` route): clients with a job in one of the viewer's stages, plus
  fresh leads (no job) when Proposal is in-scope. A client drops off once all
  their jobs move past the viewer's stages — so a Sales rep stops seeing a client
  once their job passes Proposal. Filter is stage-driven, so it generalizes to
  other roles as we tune their viewports.
- Sign-in already lands on the role dashboard (`login` → `dashboard`).

### BPMN process refinement, stage by stage — Piece 20.6
Reworked the per-job process in `bpmn_export.py` (reviewed against the maximal
job: commercial, all 6 products, roof/manufactured, grid-tie, Santa Fe + JMEC).
- **Proposal** now ends at the signed contract: `collect` renamed *Client Intake
  & Questionnaire* (old `quest` node removed/merged); new `loads` step *Record
  Electric Loads / Load Calculation* (Sales Rep) after the site visit; `contract`
  + `dep50` moved into Proposal (STEP_STATUS updated). Matches the loads gate and
  the "Sales signs the contract" exit criteria.
- **Job Prep**: the `solbiz` serviceTask stays on the chart but is excluded from
  generated tasks (generate_tasks now skips `serviceTask`). New conditional
  `finance` step *Confirm financing / rebate paperwork* (Finance) on a parallel
  branch when financed OR tax_credit=Yes OR grid-tied.
- **Installation**: `walkthrough` → *Crew Install Walkthrough*; `monitoring`
  (*Set up Monitoring*) only added when PV or Battery is on the job.
- **Inspections**: **meter-set moved to after the CID inspection passes** (real
  interconnection order) — the Yes branch is now meterset (grid-tie) → JMEC LoC
  (JMEC) → sticker; `fix` → *Correct & Re-inspect*; sticker → *Photograph Final
  Inspection Sticker*.
- **Closing**: *Sales Walkthrough* → *Final Client Walkthrough (Sales)*; *Client
  Review* → *Client Review & Sign-off*; end → *Close Out & Submit Final Paperwork*.

### Electric loads → proposal step, not creation — Piece 20.5
- `electric_loads` removed from the **new-job** form (shown only when
  `editing_job_id`); the create form carries a note pointing to Loads & Sizing.
  Column and JOB_FIELDS unchanged — new jobs just post it empty.
- New Proposal-stage gate: `_loads_recorded(db, job)` is True when the
  structured Loads & Sizing worksheet has items (job_load_items) OR the
  free-text `electric_loads` summary is filled. `stage_info` adds `loads_ok`,
  puts "electric loads not recorded" in `pending`, and folds it into `ready`
  for Proposal — so the Advance button warns until loads are in. Stage panel
  shows a "⬜ Electric loads recorded · Record loads" indicator linking to the
  loads page. Existing jobs that already have a loads summary pass the gate.

### County → utility auto-matching — Piece 20.4
- `COUNTY_UTILITIES` in `nm_directory.py` (from doc 03's verified "Utility by
  County" table, canonical UTILITIES_ALL names, all 33 counties). Passed to the
  job form as `county_utilities_json` + `utilities_json`.
- `job_form.html`: the utility field is now a `<select>` filtered by county via
  JS — single serving utility auto-selects, multiple are all listed to pick
  from, and a **Manual override** button toggles to the full statewide list.
  Editing preserves a saved out-of-map value (`data-current`). `N/A` always
  available (off-grid / no utility); the field is intentionally kept for
  off-grid jobs since the meter ties to the provider. No schema change — still
  posts the `utility_provider` field.

### Rules display: compaction + verification callouts — Piece 20.3
- `group_rules(matched, dedupe=True)` now collapses a shared requirement into
  one entry carrying `instances` (the triggering selections, e.g. PV + Battery)
  and `alert_kind`/`alert_text` (from `_rule_alert()` scanning the note for
  ⚠ verify/unverified/confirm). Entries are dicts now, not Rows — drop-in for
  templates. Shown on the job LPC tab, the rule directory, and the text report.
  Instances only render when >1; `_instance_label()` builds the bullet text.
- Verification chips + a legend (`.flag`, `.verify-legend`, `ul.instances` CSS
  in base.html). Directory page carries the legend at top.
- **Data reconciliation (nm_directory `CORRECTIONS_V11`, seed batch 11):** the
  V10 batch had carried ~a dozen county in-city phones from doc 04's "could not
  verify" list; V11 replaces them with doc 02's verified-body numbers (Clovis,
  Fort Sumner, Artesia, Grant/Planning, McKinley Navajo codes 928-871-6380,
  Cloudcroft, Moriarty/Estancia, Clayton, Belen/Los Lunas, Lincoln, San Juan)
  and promotes items docs 01-03 now show verified (Continental Divide domain,
  Gallup city-hall line, KCEC hub). Keyed on (label, field_value); applies to
  existing beta DBs via the batch-SQL migration. Uploaded .docx == the repo's
  `docs/reference/*.md`, so no other values changed.

### Per-job progress widget — Piece 20.2
- `build_job_progress(db, job)` → dict with the ordered pipeline `stages`
  (each `done` / `current` / `upcoming` / `skip`), an overall `pct`, and the
  single `next_label`/`next_who` (lowest-sort_order not-Done task, else "Move
  to <next stage>"). Lost = all `skip`; Complete = all `done`, 100%.
- Rendered by the `job_progress(p, compact=false)` macro in
  `templates/_widgets.html` — a segmented bar (one segment per stage) with the
  current stage striped/highlighted and a "▶ Next: …" caption. CSS lives in
  `base.html` (`.jobprog*`). `compact=true` drops segment labels for table rows.
- Wired into **job_detail** (full, in its own card under the header),
  **client_detail** (compact, in the job list), and the **dashboard** (compact,
  in each department's job rows). Routes pass `progress` / `progress_by_job`.

### Default task deadlines — Piece 20.1
- Every task generated for a job now gets a **default deadline of 7 days after the
  previous step** (`TASK_DEFAULT_LEAD_DAYS = 7`). With nothing completed yet, the
  first generated step is due 7 days out, the next 7 days after that, and so on —
  a simple weekly cadence so no task is left without a date.
- When a step is marked **Done**, the next still-open step (lowest `sort_order`
  among not-Done tasks) is **re-defaulted to 7 days after that completion**
  (`_redefault_next_due`). Wired into both completion paths: the job page
  (`set_task_status`) and field-work approvals (`approve_submission`).
- Rough on purpose — meant to be tightened by hand per job. Setting a target
  **install date** at generation still uses the tighter install-anchored spacing
  (`TASK_DUE_SPACING_DAYS`) instead of the 7-day default.

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
- **First name (required) / Last name / Nickname (Piece 19.3):** these compose the
  stored `name` ("First Last"); the nickname shows in quotes on the roster/profile.
  Creating an employee whose composed name already exists is **blocked** with a
  "different person? — add anyway" confirm checkbox, to stop accidental duplicates.
  Legacy single-name records split their `name` into the first/last fields on edit.
- **Remove employee (offboarding, Piece 19.4, admin):** the profile's **Remove
  employee** button opens a confirm page (`employee_remove.html`) that requires a
  **reason** (captured in the audit log). On confirm it **unassigns their tasks**,
  clears their sales-rep / follow-up assignments, removes their login / access grants
  / licenses / documents, then sends them to the **Trash** (GM can restore or purge).
  **Blocked** if they have field-work submissions on record (protects approved hours).
  Gated by `employees.manage` (so Admins can offboard — permanent purge stays GM-only).
- **Role checkboxes grouped by department** (Piece 16.1): 27 ECC roles in
  six collapsible department groups (Executive / Sales & Marketing / Operations /
  Administration / Finance / R&D) — a group opens automatically when it holds a
  selected role. Plus an "other" free-text field, schedule, and a **Login & access**
  section (admin): username, password, access level (Standard/Admin).
- `ROLE_DEPARTMENTS` in `app.py` is the source of truth; `EMPLOYEE_ROLES` (the flat
  list used for validation) is derived from it so the two never drift.
- **Org-chart team seeded (Piece 16.1):** ECC's real team (Cary, Will, Rachel,
  Louie, Trish, Si, Lisa, Vanessa, Brady) with their multi-role assignments is
  seeded once per DB via a `meta.org_team_seeded` flag (`seed_org_team`), skipping
  anyone already present — so existing installs get them without duplicates. The two
  "(sample)" employees remain for the credential/expiry demo; delete them for a clean
  roster.

### Accounts — `/accounts` (`accounts.html`, **admin**)
- Who can sign in + access level + password-set status; employees without a login;
  and **⏳ Pending password changes** (approve/reject self-service requests).

### Access console — `/access` (`access.html`, **GM only**, Piece 17)
- The General Manager grants individual tools to people who sign in, each with an
  optional **expiry date** (temporary access lapses on its own). GMs show "Full
  access"; Admin rows note "Admin already has this" (except Delete). One save form
  per person writes `permission_grants`.

### Access model (Piece 17, cross-cutting)
- **GM = anyone holding the "General Manager" role** (`_has_gm_role`) — unfettered
  access + the console + (delegatable) delete. **Admin** keeps every tool below GM
  **except Delete**. **Standard** gets only granted tools. Central check is
  `has_permission(perm)`; `admin_required` maps each gated view to a permission via
  `VIEW_PERMISSION`, and templates gate UI with `can('<perm>')`. Permissions catalog
  lives in `PERMISSIONS`; grants (with expiry) in `permission_grants`.
- **Deletion & trash (Piece 17.1, done):** every UI delete now requires the **delete**
  permission (`@delete_required`) → runs an **in-use check** (blocks with an error
  listing what references it) → otherwise **soft-deletes to the `trash` table** (full
  original row as JSON + origin table + a "found in" label). The `TRASH_REGISTRY`
  defines each entity's label / found-in / in-use rules (+ file path for uploads).
  Restore re-inserts the row to its origin table (original id preserved when free);
  **permanent purge is GM-only** (`gm_required`) and unlinks any on-disk file. Delete
  buttons are hidden unless `can('delete')`.

### Trash — `/trash` (`trash.html`, delete-permission holders; purge = GM only)
- Deleted items with what they were and where they lived; **↩ Restore** or (GM only)
  **🗑 Delete permanently**. In-use items never reach here — they're blocked at delete
  time. Cold-lead purge is also delete-gated (its own graveyard, not the trash).

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
- **Tables (27):** clients, client_versions, lead_followups, cold_leads, permission_grants, trash, jobs,
  job_versions, job_materials, job_files, job_tasks, resource_rules, meta,
  employees, employee_credentials, employee_files, client_files,
  appliance_catalog, component_catalog, job_load_rooms, job_load_items, job_bom,
  job_sizing, password_requests, field_submissions, field_submission_items,
  audit_log.

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
- **No client/job delete** (intentional — would cascade). Cold leads (job-less)
  *can* be deleted from the admin cold-leads page.
- **BPMN process is still hard-coded** in `bpmn_export.py`. Piece 16 redefined the
  *status phases* (Leads/Proposal/Job Prep/Installation/Inspections/Closing) and the
  lead lifecycle, but **editing the BPMN step contents and reassigning role lanes
  by department is deferred** — the agreed next workflow task. Roles/permissions
  overhaul is also still pending.
- **Follow-ups generate on page load** (home + task board), not via a background
  scheduler — fine for an always-someone's-logged-in tool; revisit if that changes.
- Suggested next: **BPMN step/role restructure**; **hours summary / timesheet** from
  approved submissions; rule edit; the service worker.
