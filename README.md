# ☀️ Solbiz

**Solbiz** — ECC Solar's internal operations tool. Build client profiles, create
job profiles under each client, and automatically surface the right resources
(licenses, permits, compliance items, links, phone numbers, docs) based on each
job's fields — then run the whole job through a standardized, role-based pipeline.

**Proprietary software — see [LICENSE](LICENSE). Do not distribute.**

Built for ECC Solar (New Mexico, statewide). Flask + SQLite + Jinja templates,
pure Python, raw SQL (no ORM, no JS framework). Runs from source or as a
packaged desktop app. Offline-capable; the database upgrades itself on launch.

---

## How to run it (every time)

1. Open a terminal in this folder.
2. First time only, install the one dependency:

   ```
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```
   python app.py
   ```

4. Open your browser to **http://localhost:5000**

To stop the app, press `Ctrl+C` in the terminal. Your data lives in
`job_creator.db` (created automatically on first run). Delete that file to start
over with a fresh database. **Back up `job_creator.db` *and* the `uploads/`
folder together** — the documents on disk are referenced from the database.

The build number shows plainly in the page footer ("Version N") so beta testers
can confirm a pull/update took effect.

---

## Features & capabilities

> This list is the running record of everything the software does and is kept
> current with each update. When a capability is added or changed, it is logged
> here.

### Clients & leads
- **Client profiles** with separated address fields (street / city / state / ZIP
  for both mailing and billing) to cut down on typos.
- **Live search preview** on the landing page — matches appear as you type.
- **Lead pipeline**: client-level lead status (Lead / Converted / Cold), an
  assigned sales rep, conversion tracking, and a **cold-leads** list.
- **Lead follow-ups**: scheduled follow-up milestones with due dates, surfaced
  on the dashboard and flagged when overdue.
- **Edit history**: editing a client saves the prior version; changed data is
  hidden with a note that it changed — only an admin can request the older info.
- **Client document storage** with categories.

### Jobs
- **Job profiles** stored under each client, with full field capture.
- **Rules engine** — job selections → the licenses, permits, and compliance
  items that apply, across two pages:
  - **Rules Editor** (`/rules`): the editable catalog of resources (links, phone
    numbers, docs, accepted file formats). Grouped by category.
  - **L/P/C Directory** (`/directory`): a read-only lookup filtered by job type.
    Shared requirements are **consolidated** — a requirement needed by more than
    one selection (e.g. EE-98 for PV + Battery) shows **once** with every
    triggering scenario listed beneath, instead of repeating. Compliance rules
    can also carry the **verbatim source text** (the exact code wording), shown
    above the shorthand + source link, above the scenarios it applies to.
- **Verbatim source text** is an editable per-rule field for capturing the exact
  wording from the code/source, surfaced on the L/P/C Directory.
- **Verification callouts**: requirements sourced from the NM reference set that
  couldn't be fully confirmed carry a visible **⚠ Verify / ⚠ Unverified** chip,
  with a legend, so field staff know what to confirm before relying on it.
- **NM reference data** (statewide licensing, all 33 counties' AHJ contacts,
  every utility's interconnection contacts) is kept reconciled against the
  verified July 2026 reference set.
- **County → utility auto-matching**: picking a county on the job form filters
  the utility-provider dropdown to the providers that serve it (verified doc-03
  table). If one utility serves the county it's auto-selected; if several do,
  they're all listed so you pick the one on the customer's bill. A **Manual
  override** button opens the full statewide list for non-standard cases. The
  utility field is kept even for off-grid jobs (the meter/account ties to it).
- **Job edit history / versioning** for recordkeeping.
- **Per-job BPMN process charts**: an in-app viewer plus `.bpmn` export, with
  each step tagged by pipeline status.
- **Loads & Sizing** (`/jobs/<id>/loads`): electrical loads and system sizing on
  its own page. Electric loads are **not** entered at job creation (they aren't
  known until the walkthrough) — they're recorded here during the proposal, and
  the **Proposal stage can't advance until loads are recorded**. It's a
  **Proposal-phase tool**: once the contract is signed (the job moves past
  Proposal) the editor **locks** — the recorded figures stay visible here and in
  Design, but no one edits them (enforced in the UI and on the server).
  - **Sales / Designer view modes** default per viewer from their department
    (Design → Designer, Sales → Sales) and are togglable per session.
  - **Room-aware appliance picker**: each survey room has a "type" (Kitchen,
    Garage…) so its picker defaults to that room's appliances, with a search box
    over the whole catalog and a **Custom** toggle for off-catalog items.
  - **Appliance-era tags** are colour-coded — 🟢 Modern / 🟠 Vintage.
  - **Component auto-suggest**: once the survey is recorded, Designer mode reads
    the live inventory specs and proposes the components that fit — **PV modules**
    (by nameplate watts), **batteries** (by usable kWh), and the **inverter** (by
    rated power) — ranked with a Recommended pick plus alternates, each one-click
    addable to the bill of materials at the sized quantity.
- **Calculator Catalog** (🗄 Databases → Calculator Catalog): the appliance +
  component reference data that drives the load survey and the BOM/sizing picker;
  editing it applies everywhere immediately.
- **Materials lists** per job (status: Needed → Quoted → Ordered → Backordered →
  Received → On hand → Installed) and **document upload/storage** with
  per-requirement filing coverage. The job's **L/P/C tab** leads with **Permits**
  — each with an **inline upload slot** so the permit coordinator views the
  requirement and files the document in one place — with licenses and compliance
  collapsed below. The **Permits dashboard** shows a **permits-filed X/Y** column;
  the **Purchasing dashboard** shows a **procurement rollup** of materials by
  status across Job-Prep jobs.
- **Per-slot upload formats**: a document slot can restrict its accepted file
  types (e.g. a permit slot to PDF), enforced on upload.
- **Auto-renamed uploads**: every uploaded file is renamed to a self-describing
  `Name_What_Date` scheme for recordkeeping (job docs, client files, employee
  files, and field photos each get their own pattern); the friendly name is what
  shows and downloads, while the on-disk name stays collision-safe.
- **In-place editing** for the add/delete-only records (rules, appliance &
  component catalog, credentials, load items/rooms, BOM lines) — an ✎ edit
  pre-fills the record to save back over the original.
- **Exportable job report**.

### Pipeline, tasks & scheduling
- **Standardized pipeline**: Proposal → Job Prep → Installation → Inspections →
  Closing → Complete (plus Lost). Each stage is **owned by a department** with
  defined exit criteria; Job Prep is gated by prerequisites (all permits filed +
  an install date set — setting the install date auto-advances the job).
- **Per-job progress widget** — a segmented progress bar (one per job) that shows
  at a glance where the job sits in the pipeline, with the **next step called
  out**. Appears on the dashboard, client pages, and each job's header.
- **Task generation** from a job's process, with each step auto-assigned to the
  role-holder responsible for it.
- **Default task deadlines**: every generated task defaults to **7 days after the
  previous step** (a weekly cadence); when a step is marked Done, the next open
  step is re-defaulted to 7 days after that completion. Hand-editable per job.
- **Calendar export (.ics)**: download your task due dates + install dates
  (`/calendar/my.ics`) or a single job's dates (`/jobs/<id>/calendar.ics`) and
  import into Google Calendar (or Outlook/Apple). Stable IDs so re-importing
  updates events instead of duplicating.
- **Work Bag** for field crews — an offline-capable field tool that shows **only
  on-site field work** (install & inspection); office/scheduling steps stay on the
  dashboards. It opens on a **jobs landing** that lists just the jobs in the
  crew's bag (name, client, install date, open-task count); tapping a job opens
  its **own page** with that job's tasks, plus hours, receipts, and notes pinned
  to it.
- **Submit-as-done with time by pay type**: instead of a status dropdown, each
  task has a single **✓ Submit as done** (and a **⚠ Can't finish** → Blocked).
  Submitting captures **the time it took, split by pay type** (e.g. 8 h regular +
  1 h travel + 2 h roof) shown live on a **colour-coded timeline**. It flows
  through **two sign-offs**: the supervisor approves the task (marking it Done and
  posting the split hours as **pending payroll** by pay type), then Finance
  approves the hours on the payroll page. All edits are saved on-device and submit
  when back online.
- **Job photos from the field**: every pipeline step that requires photos — the
  site visit, the install itself, the crew walkthrough, doc tube, the meter set,
  and re-inspection of corrections — is completed on its **own dedicated screen**:
  a 3-step **take / review / submit** flow (phone camera, thumbnail review, then
  submit with notes and the time it took). Submitting requires at least one photo,
  marks the task done for approval, and returns to the job's Work Bag page. Photos
  save to the job and appear on the job record; crews can remove their own shots.
- **Packing list**: each job in the Work Bag carries a collapsible **📦 Packing
  list** of its materials (item, qty, status) — colour-coded by readiness (on
  hand / received vs. still-needed vs. backordered) — so installers can pack the
  truck before they leave. (Named "Packing", not "Load", to keep it distinct
  from the electrical **Loads & Sizing** tool.)
- **Field notes**: a standard **📝 Job notes** box in the Work Bag lets crews jot
  free-form notes about a job (access details, on-site changes, callbacks). Each
  note is **individually timestamped** (the same clock as the audit log) with the
  author, and surfaces on the job's record for the office to read later.
- **Field receipts**: crews snap a receipt photo and log the date, total, vendor,
  reference, and expense category from the Work Bag; it's filed on the job and
  recorded as a **paid expense** for bookkeeping.
- **Grouped task board**: the cross-job task board and the dashboard's **My
  Tasks** are **grouped under each job** (a banner per job with its tasks as
  bullets beneath) so everything for a job reads at a glance.
- **Offline cold-start (service worker)**: the app caches visited pages and
  serves them — or an offline page — without a signal, so the Work Bag works in
  the field even on a fresh load.
- **Background scheduler**: lead follow-up generation runs off the request path
  on a daemon timer, so it keeps working while the app sits unattended.

### People, roles & permissions
- **Employees** matched to the org chart, with first / last / optional nickname
  (duplicate-name guard on creation).
- **27 roles grouped by department**; the create-employee form groups role titles
  by department in its picker.
- **Licenses & certifications** per employee, with expiry tracking that ties into
  job requirements (a job page can show whether staff hold the licenses it needs
  and warn when a credential has lapsed).
- **Role-based "My Dashboard"** — the sign-in landing, one role view at a time
  (mode switch for people who hold multiple roles); each person's **default view
  is remembered** (e.g. the GM defaults to the Executive overview). Every section
  is **collapsible**. The **Sales** viewport shows **Active Proposals** (jobs in
  Proposal), a **Leads** worklist (prospects not yet converted, with follow-up
  actions), and My tasks. The **Installation** (Foreman) viewport lists installs
  **bucketed by date** — This week / Upcoming / In inspection · unscheduled —
  with the install date leading, and trims **My tasks** to on-site field work.
  The **Executive** (GM) viewport opens with a **Company overview**: pipeline
  counts by stage, money-in-flight tiles (contract / collected / outstanding /
  expenses across active jobs), an attention row (approvals waiting, overdue
  tasks, stalled jobs), a **Ready-for-design** queue (Proposal jobs whose load
  survey is captured but design isn't finalized — the Sales→Designer hand-off),
  this week's installs, and a **Closing worklist** (each job's balance due and
  remaining close-out steps). Each sub-section sits in its own panel.
- **Inventory database** (🗄 Databases → Inventory): ECC's stock of components
  seeded from the inventory workbook — **439 items across 15 categories** (PV,
  inverters, batteries, charge controllers, racking, …) with per-category specs, a
  canonical **~52-vendor** supplier list (names normalized from the workbook's
  typo'd entries), plus a standard **tool kit** (priced with big-box listings) and
  a **vehicles / heavy-equipment** list (each vehicle has a shop **nickname**). The
  table is editable in-app; item specs feed the Loads & Sizing calculator, and a
  `web_price` sits alongside the quoted `Cost` so a price check never overwrites
  your number. Battery, inverter, and PV spec data is research-calibrated, with
  product-page **purchase URLs** on current-install gear.
- **Stock ledger & stale-stock notice**: every stock change (received / used /
  count / adjust) flows through a single ledger that keeps each item's on-hand
  balance; items that go unused past a threshold surface a **stale-stock** notice
  on the Designer's dashboard.
- **Barcode / asset registry**: generate and print **Code 128** labels, register
  serial numbers for **consumables** (hardware, components) and **non-consumables**
  (tools, PPE, trucks), and **scan** them in/out — including **phone-camera
  scanning** — to load a job's truck (two installers can load the same job from
  their own phones). Only the **Warehouse Manager** can mint new tags; loading a
  job needs no special permission.
- **Nav grouping**: the reference/data pages — **Client Profiles, Rules Editor,
  L/P/C Directory, Inventory, Calculator Catalog** — are consolidated under a
  single **🗄 Databases** dropdown in the header; **Employees + Payroll** sit under
  a **👥 Team** dropdown; and **Log / Trash / Access** sit under a **🔧 Admin**
  dropdown.
  Each grouped dropdown shows only the items the user may reach and collapses to a
  plain link when only one applies. Keeps the top bar tidy.
- **Permissions**: the General Manager (identified by the GM role) has unfettered
  access and can grant individuals access to specific tools/functions **with an
  expiration date**. Admin tier sits below GM; granular grants everywhere else.
- **Deletion & trash**: deletes are GM-only (delegatable), prompt before
  deleting, and are **blocked with an error if the data is in use** elsewhere.
  Deleted items go to a **trash can** for review; permanent purge stays GM-only.
- **Employee offboarding**: admins can remove an employee with a confirm prompt
  that requires a reason for the audit log.
- **Logins**: per-user accounts with hashed passwords. **Usernames are
  case-insensitive** (passwords stay case-sensitive); the Accounts page scans for
  case-duplicate usernames. Sessions **auto-log-out after 12 hours of
  inactivity** (a sliding window that renews on each request).

### Finance & billing
- **Per-job billing ledger** (💵 Billing tab): set the contract total and record
  every **income** (deposits, invoices, rebates) and **expense** (materials,
  permits, labor, subs) with a dollar amount, date, category, party, reference,
  method, and paid/outstanding status.
- **Receipts, invoices & bills**: each ledger entry can be tagged with the
  **source document** behind it — **Receipt** (proof of a payment made),
  **Invoice** (money billed to a customer, A/R), or **Bill** (money a vendor
  billed us, A/P). Picking one auto-sets the usual accounting flow (Invoice →
  Income/Outstanding, Bill → Expense/Outstanding, Receipt → Expense/Paid, all
  still editable). The Billing tab shows a **paperwork-on-file** tally (count +
  total for each type).
- **Payments table** on the Finance dashboard: every active job with Contract /
  Collected / Outstanding / Expenses / Net and a grand-total row.
- **QuickBooks export**: a CSV whose first three columns (Date, Description,
  Amount, signed) map straight onto QuickBooks Online's import; a **Document**
  column carries the Receipt/Invoice/Bill tag, and (because QuickBooks imports
  invoices (A/R), bills (A/P) and receipts through separate flows) it can be
  filtered per document type. The export buttons live on **each job's Billing
  tab** — scoped to that job — with a company-wide export still available.
- **Customer invoice generation (50 / 40 / 10)**: from the Billing tab, generate
  the progress-billing invoices straight from the contract + BOM — **Deposit 50%**
  at signing, **Progress 40%**, **Final 10%** — where any materials added to the
  BOM after the deposit are billed on top (split across the Progress/Final
  invoices, with the Final trued-up). Each invoice records as an Income/Invoice
  line (so it flows into the billing rollup and mark-paid) and prints a clean
  **customer copy**: the ECC remit-to block, the 50/40/10 schedule, the amount
  due, and the equipment (BOM) list **without per-item pricing**. A **NM
  gross-receipts-tax** line is included — a per-job rate (defaulting to 0% for the
  solar deduction), citing **NMSA 7-9-112** when exempt. The **50/40/10 pay-scheme
  callout** also shows on the Sales and Finance dashboards so both explain it the
  same way.
- **Payroll**: employees **log their own hours** from the 🎒 Work Bag (by date,
  job, and **pay type** — usually captured right on the task they finished);
  supervisors **review and approve** them before they count. The pay schema is
  configurable — each pay type is a **multiplier** on the employee's base wage
  (roof time…) or a **flat $/hr** (travel time…), **overridable per employee**.
  **Overtime is automatic** — hours over the weekly threshold of OT-eligible time
  earn the OT premium (no manual OT entry). Only **Cary (GM)** and **Lisa (Payroll
  Manager)** can change pay rates.
- **Pay periods run Sunday → Saturday** (the default period is the most recent
  full week), overridable by date range.
- **Leave can't earn overtime**: approving vacation/PTO/sick time that would take
  an employee past the weekly cap is **blocked** unless the GM overrides it on the
  approval form (worked hours still earn OT normally).
- **Payroll reminder**: the Finance dashboard shows a **Tuesday–Thursday** nudge
  to run payroll each week until the period's hours are **confirmed and exported**.
- **Timesheets**: a per-employee, printable/CSV timesheet view of logged hours
  (a read-only lens on the same time data; payroll approval/export is unchanged).
- A pay-period summary rolls up hours + dollars per person with a QuickBooks CSV
  export.

### Records & audit
- **Audit log** of all changes (create/update/delete), with password fields
  redacted and never logged in plaintext.
- **NM directory** of authorities/utilities baked in for quick reference.

---

## Build history (high level)

- **Pieces 1–7** — Flask + SQLite skeleton; clients & jobs; rules engine;
  resource catalog; job versioning; per-job BPMN; materials & document filing.
- **Piece 8+** — search, statuses, logins, and service-ticket refinement.
- **Pieces 9–15** — desktop packaging & versioned footer; live search preview;
  split address fields; client edit history; Loads & Sizing as its own page.
- **Pieces 16–19** — org-chart staffing; roles/permissions (GM grants with
  expiry, Admin tier); trash + in-use checks; task→role assignment; standardized
  department-owned pipeline; role-based dashboards with a mode switch;
  case-insensitive usernames; first/last/nickname; employee offboarding.
- **Piece 20** — calendar (.ics) export; default 7-day task deadlines with a
  completion cascade; per-job pipeline progress widget.
- **Piece 21** — Finance viewport: per-job billing ledger, Payments dashboard,
  QuickBooks CSV; payroll (self-logged hours, approvals, configurable pay types,
  auto-overtime); permits/warehouse tuning; **receipts/invoices/bills** tagging
  feeding the QuickBooks reports; **Foreman/Installation viewport** (installs
  bucketed by date) + a field-focused, job-grouped Work Bag with **on-site photo
  capture** on photo steps, a **packing list**, and **timestamped field
  notes**.
- **Piece 22** — Work Bag packing list; Loads & Sizing **locks past Proposal**;
  **Executive (GM) company overview** (pipeline counts, money-in-flight tiles,
  attention row, Ready-for-design queue, this-week's installs, Closing worklist);
  **Databases / Team / Admin** nav dropdowns.
- **Piece 23** — **Inventory database** (439 items with specs, ~52 canonical
  vendors, tool kit, vehicles), in-app management + table redesign; battery /
  inverter / PV spec research calibration; vendor & make standardization; purchase
  URLs on current-install gear.
- **Piece 24** — inventory cleanup + Tools/Vehicles edit UI; **stock-usage ledger
  + stale-stock notice**; BPMN lanes aligned to real departments + a
  roles/permissions overhaul; **12-hour sliding auto-logout**; **offline service
  worker** (cold-start).
- **Piece 25** — **in-place editing** of add/delete-only records; **timesheets**;
  per-slot document-format restrictions; **background scheduler** for follow-up
  generation; **auto-renamed uploads** (`Name_What_Date`).
- **Piece 26** — **barcode / asset registry** (generate/print/scan, phone camera,
  crew truck-loading); Work Bag **receipt capture**; **grouped task board**; Loads
  survey tweaks + colour-coded appliance eras; **component auto-suggest** from
  inventory specs; **payroll reminder** + **leave-can't-earn-OT** rule + grouped
  My Tasks; **L/P/C Directory** consolidation + verbatim source text; Rules Editor
  / L/P/C Directory renames; GM defaults to the Executive overview.
- **Piece 27** — Calculator Catalog rename; **sample seed data removed** for a
  clean production database; **Sunday→Saturday pay periods**; QuickBooks exports
  moved to **per-job Billing**; **50/40/10 customer invoice generation** + **NM
  gross-receipts-tax** line + ECC remit-to + pay-scheme callouts; **Work Bag split**
  into a jobs landing + per-job page; **per-task Submit-as-done** with time by pay
  type + timeline.
- **Piece 28** — **photo steps** completed on their own take / review / submit
  screen (with the time capture), returning to the job's Work Bag when submitted.

Data lives in `job_creator.db`; uploaded documents live in `uploads/`.
