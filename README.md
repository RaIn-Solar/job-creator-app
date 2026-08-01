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
- **Rules engine** (`/rules`): job selections → the licenses, permits, and
  compliance items that apply. Editable catalog of resources (links, phone
  numbers, docs). Shared requirements are **compacted** — a requirement needed
  by more than one selection (e.g. EE-98 for PV + Battery) shows once with its
  triggering selections listed beneath, instead of repeating.
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
  the **Proposal stage can't advance until loads are recorded**.
- **Materials lists** per job (status: Needed → Quoted → Ordered → Backordered →
  Received → On hand → Installed) and **document upload/storage** with
  per-requirement filing coverage. The job's **L/P/C tab** leads with **Permits**
  — each with an **inline upload slot** so the permit coordinator views the
  requirement and files the document in one place — with licenses and compliance
  collapsed below. The **Permits dashboard** shows a **permits-filed X/Y** column;
  the **Purchasing dashboard** shows a **procurement rollup** of materials by
  status across Job-Prep jobs.
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
- **Work Bag** for field crews to update task status/notes; changes flow through
  an **approval queue** before being applied to the authoritative tasks. The bag
  shows **only on-site field work** (install & inspection), **grouped by job**
  with each job's install date as the header — office/scheduling steps stay on
  the dashboards.

### People, roles & permissions
- **Employees** matched to the org chart, with first / last / optional nickname
  (duplicate-name guard on creation).
- **27 roles grouped by department**; the create-employee form groups role titles
  by department in its picker.
- **Licenses & certifications** per employee, with expiry tracking that ties into
  job requirements (a job page can show whether staff hold the licenses it needs
  and warn when a credential has lapsed).
- **Role-based "My Dashboard"** — the sign-in landing, one role view at a time
  (mode switch for people who hold multiple roles). Every section is
  **collapsible**. The **Sales** viewport shows **Active Proposals** (jobs in
  Proposal), a **Leads** worklist (prospects not yet converted, with follow-up
  actions), and My tasks. The **Installation** (Foreman) viewport lists installs
  **bucketed by date** — This week / Upcoming / In inspection · unscheduled —
  with the install date leading, and trims **My tasks** to on-site field work.
  **Client Profiles** is its own header-nav button.
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
  case-duplicate usernames.

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
- **QuickBooks export**: one-click CSV of all transactions
  (`/finance/quickbooks.csv`) whose first three columns (Date, Description,
  Amount, signed) map straight onto QuickBooks Online's import; a **Document**
  column carries the Receipt/Invoice/Bill tag. Because QuickBooks imports
  invoices (A/R), bills (A/P) and receipts through separate flows, the Finance
  dashboard also offers **per-document exports** (`?doc=Receipt|Invoice|Bill`).
- **Payroll**: employees **log their own hours** from the 🎒 Work Bag (by date,
  job, and **pay type**); supervisors **review and approve** them on the Payroll
  page before they count. The pay schema is configurable — each pay type is a
  **multiplier** on the employee's base wage (roof time…) or a **flat $/hr**
  (travel time…), **overridable per employee**. **Overtime is automatic** — hours
  over the weekly threshold of OT-eligible time earn the OT premium (no manual OT
  entry). Only **Cary (GM)** and **Lisa (Payroll Manager)** can change pay rates.
  A pay-period summary rolls up hours + dollars per person with a QuickBooks CSV
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
  bucketed by date) + a field-focused, job-grouped Work Bag.

Data lives in `job_creator.db`; uploaded documents live in `uploads/`.
