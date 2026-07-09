"""Job Creator — internal tool for ECC Solar.

Piece 1: Flask skeleton backed by SQLite; home page lists client profiles.
Piece 2: "New client" form and individual client profile pages.
Piece 3: job profiles stored under each client.
Piece 4: rules engine — job selections resolve to required licenses,
permits, and compliance items; service tickets; exportable job report.

Run it:
    python -m pip install -r requirements.txt
    python app.py
then open http://127.0.0.1:5000 in your browser.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, Response, abort, flash, g, redirect, render_template, request, url_for,
)

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "job_creator.db"

# The columns a user can fill in on the client form, in display order.
CLIENT_FIELDS = [
    "name", "phone", "mailing_address", "billing_address",
    "email", "referral_source", "notes",
]

# Fields that must not be blank, with the labels shown in error messages.
REQUIRED_CLIENT_FIELDS = {
    "name": "Client name",
    "phone": "Phone number",
    "mailing_address": "Mailing address",
    "billing_address": "Billing address",
}

# Job profile columns (products is stored as a comma-separated list).
JOB_FIELDS = [
    "job_name", "site_location", "county", "electric_loads", "utility_provider",
    "warranty_type", "cost_method", "tax_credit", "expand_option", "products",
    "pv_utility_connection", "pv_mounting_type", "pv_manufactured_house",
    "generator_utility_connection", "battery_utility_connection", "service_type",
    "property_type",
]

# Labels used on the report and anywhere a field needs a human name.
JOB_FIELD_LABELS = {
    "job_name": "Job name", "site_location": "Site location",
    "county": "County", "electric_loads": "Electric loads",
    "utility_provider": "Utility provider", "warranty_type": "Warranty type",
    "cost_method": "Cost method", "tax_credit": "Tax credit",
    "expand_option": "Expand option", "products": "Products / services",
    "pv_utility_connection": "PV — utility connection",
    "pv_mounting_type": "PV — mounting type",
    "pv_manufactured_house": "PV — manufactured house",
    "generator_utility_connection": "Generator — utility connection",
    "battery_utility_connection": "Battery bank — utility connection",
    "service_type": "Service type",
    "property_type": "Property type",
}

UTILITY_CONNECTIONS = ["Off-grid", "Grid-tie", "Backup system"]
MOUNTING_TYPES = ["Roof mounted", "Ground mount"]
SERVICE_TYPES = ["General service", "Warranty service"]
PROPERTY_TYPES = ["Residential", "Commercial"]

# Which variant fields belong to which product — used by the rule
# directory so filtering by job type also scopes its variants.
VARIANT_OWNERS = {
    "pv_utility_connection": "PV Systems",
    "pv_mounting_type": "PV Systems",
    "pv_manufactured_house": "PV Systems",
    "generator_utility_connection": "Generators",
    "battery_utility_connection": "Battery Banks",
    "service_type": "Technician Service",
}
CONNECTION_FIELDS = {
    "pv_utility_connection", "generator_utility_connection",
    "battery_utility_connection",
}

RULE_CATEGORIES = ["License", "Permit", "Compliance", "Link", "Phone", "Doc"]
CATEGORY_HEADINGS = {
    "License": "Technician licenses",
    "Permit": "Permits",
    "Compliance": "Compliance notes",
    "Link": "Links",
    "Phone": "Phone numbers",
    "Doc": "Documents",
}

# ECC's requirement rules, seeded once into the editable resource_rules
# table: (field_name, field_value, match_type, category, label, notes).
SEED_RULES = [
    # Mini Split Air Conditioners
    ("products", "Mini Split Air Conditioners", "contains", "License", "MM-2 or MM-3 Contractor License", ""),
    ("products", "Mini Split Air Conditioners", "contains", "License", "Journeyman HVAC (JH) Certificate", ""),
    ("products", "Mini Split Air Conditioners", "contains", "License", "EPA Section 608 — Type II or Universal", ""),
    ("products", "Mini Split Air Conditioners", "contains", "Permit", "Mechanical permit", ""),
    ("products", "Mini Split Air Conditioners", "contains", "Permit", "Electrical permit", ""),
    ("products", "Mini Split Air Conditioners", "contains", "Compliance", "AIM Act refrigerant (R-454B or R-32)", ""),
    ("products", "Mini Split Air Conditioners", "contains", "Compliance", "Rough-in Inspection", ""),
    ("products", "Mini Split Air Conditioners", "contains", "Compliance", "Final Inspection", ""),
    # Generators
    ("products", "Generators", "contains", "License", "EE-98 or ER-1 Electrical License", ""),
    ("products", "Generators", "contains", "Permit", "Electrical permit", ""),
    ("products", "Generators", "contains", "Compliance", "Rough-in Inspection", ""),
    ("products", "Generators", "contains", "Compliance", "Final Inspection", ""),
    # Well Pumps
    ("products", "Well Pumps", "contains", "License", "ES-10R Contractor License", ""),
    ("products", "Well Pumps", "contains", "License", "ES-10RJ Journeyman", "per tech"),
    ("products", "Well Pumps", "contains", "Permit", "Electrical permit", ""),
    ("products", "Well Pumps", "contains", "Compliance", "Electrical Inspection", ""),
    # PV Systems
    ("products", "PV Systems", "contains", "License", "EE-98 Contractor License", ""),
    ("products", "PV Systems", "contains", "License", "EE-98J Journeyman", "per tech on site"),
    ("products", "PV Systems", "contains", "Permit", "Electrical permit", ""),
    ("products", "PV Systems", "contains", "Compliance", "Full NEC 690 One-Line Package", ""),
    # Battery Banks
    ("products", "Battery Banks", "contains", "License", "EE-98 Contractor License", ""),
    ("products", "Battery Banks", "contains", "License", "EE-98J Journeyman", "per tech on site"),
    ("products", "Battery Banks", "contains", "Permit", "Electrical permit", ""),
    ("products", "Battery Banks", "contains", "Compliance", "Updated One-Line w/ ESS Disconnect", ""),
    ("products", "Battery Banks", "contains", "Compliance", "UL 9540 Equipment Listing", ""),
    ("products", "Battery Banks", "contains", "Compliance", "NEC 706 Disconnect + Labeling", ""),
    ("products", "Battery Banks", "contains", "Compliance", "Exterior Emergency Shutdown", ""),
    ("products", "Battery Banks", "contains", "Compliance", "IFC Chapter 12 / Fire Code", ""),
    ("products", "Battery Banks", "contains", "Compliance", "NFPA 855 Clearances + Spacing", ""),
    ("products", "Battery Banks", "contains", "Compliance", "Ventilation Plan", ""),
    ("products", "Battery Banks", "contains", "Compliance", "Smoke/Heat Detection (if enclosed)", ""),
]

# Batch 2 — PV Systems variant matrix (roof/ground × grid-tie/off-grid).
# Seed batches are applied once per database via the meta.seed_version key,
# so existing databases pick up new batches without duplicating rules.
SEED_RULES_V2 = [
    # All PV variants
    ("products", "PV Systems", "contains", "Compliance", "SMDTC Application", "client files"),
    ("products", "PV Systems", "contains", "Compliance", "GRT Exemption on Invoice", ""),
    # Roof mounted
    ("pv_mounting_type", "Roof mounted", "equals", "Compliance", "Rapid Shutdown (NEC 690.12)", ""),
    ("pv_mounting_type", "Roof mounted", "equals", "Compliance", "Structural Analysis / NM PE Letter", "situational"),
    ("pv_mounting_type", "Roof mounted", "equals", "Permit", "Building Permit (structural)", "if reinforcement needed"),
    ("pv_mounting_type", "Roof mounted", "equals", "Compliance", "Fire Code Roof Access Clearances", ""),
    # Roof mounted on a manufactured house
    ("pv_manufactured_house", "Yes", "equals", "Permit", "MHD Permit", "manufactured homes"),
    # Ground mount
    ("pv_mounting_type", "Ground mount", "equals", "Compliance", "Rapid Shutdown (NEC 690.12) — exception", "ground mounts typically qualify for the exception"),
    ("pv_mounting_type", "Ground mount", "equals", "Compliance", "Structural Analysis / NM PE Letter", ""),
    ("pv_mounting_type", "Ground mount", "equals", "Permit", "Building Permit (structural)", ""),
    ("pv_mounting_type", "Ground mount", "equals", "Compliance", "Underground Wiring Plan + Depths", ""),
    # Grid-tie (either mounting)
    ("pv_utility_connection", "Grid-tie", "equals", "Permit", "Utility Interconnection Application", ""),
    ("pv_utility_connection", "Grid-tie", "equals", "Compliance", "IEEE 1547-2018 Inverter Listing", ""),
    ("pv_utility_connection", "Grid-tie", "equals", "Compliance", "Lockable Load-Break Disconnect", ""),
    ("pv_utility_connection", "Grid-tie", "equals", "Compliance", "Signed Interconnection Agreement", ""),
    ("pv_utility_connection", "Grid-tie", "equals", "Compliance", "Utility Final Inspection + Anti-Island", ""),
]

# Batch 3 — backup systems follow grid-tie rules (per ECC general rule;
# specifics to be refined later, hence the note on each).
SEED_RULES_V3 = [
    ("pv_utility_connection", "Backup system", "equals", "Permit", "Utility Interconnection Application", "follows grid-tie rules for now"),
    ("pv_utility_connection", "Backup system", "equals", "Compliance", "IEEE 1547-2018 Inverter Listing", "follows grid-tie rules for now"),
    ("pv_utility_connection", "Backup system", "equals", "Compliance", "Lockable Load-Break Disconnect", "follows grid-tie rules for now"),
    ("pv_utility_connection", "Backup system", "equals", "Compliance", "Signed Interconnection Agreement", "follows grid-tie rules for now"),
    ("pv_utility_connection", "Backup system", "equals", "Compliance", "Utility Final Inspection + Anti-Island", "follows grid-tie rules for now"),
]

# Batch 4 — Battery Banks matrix (Res. Solar+Bat / Off-Grid / Grid-Tied /
# Commercial). 9-item rows carry a second AND condition. Backup system
# mirrors grid-tie per the ECC general rule (battery table has no
# standby column).
SEED_RULES_V4 = [
    ("products", "Battery Banks", "contains", "Compliance", "Fire Authority Plan Review", "situational", "property_type", "Residential", "equals"),
    ("products", "Battery Banks", "contains", "Compliance", "Fire Authority Plan Review", "likely required", "property_type", "Commercial", "equals"),
    ("products", "Battery Banks", "contains", "Compliance", "Hazard Mitigation Analysis (HMA)", "confirm with AHJ", "property_type", "Residential", "equals"),
    ("products", "Battery Banks", "contains", "Compliance", "Hazard Mitigation Analysis (HMA)", "likely required", "property_type", "Commercial", "equals"),
    ("battery_utility_connection", "Grid-tie", "equals", "Compliance", "Utility Interconnection Update", "if export"),
    ("battery_utility_connection", "Backup system", "equals", "Compliance", "Utility Interconnection Update", "if export; follows grid-tie rules for now"),
    ("battery_utility_connection", "Grid-tie", "equals", "Compliance", "NEC 705 Interconnection (multi-source)", ""),
    ("battery_utility_connection", "Backup system", "equals", "Compliance", "NEC 705 Interconnection (multi-source)", "follows grid-tie rules for now"),
    ("battery_utility_connection", "Off-grid", "equals", "Compliance", "NEC 705 Interconnection (multi-source)", "if generator coupled"),
    ("battery_utility_connection", "Grid-tie", "equals", "Compliance", "Arc Flash Label", "commercial"),
    ("battery_utility_connection", "Backup system", "equals", "Compliance", "Arc Flash Label", "commercial; follows grid-tie rules for now"),
    ("products", "Battery Banks", "contains", "Compliance", "Arc Flash Label", "", "property_type", "Commercial", "equals"),
    ("products", "Battery Banks", "contains", "Compliance", "SMDTC 20% Credit", "client files; if with solar", "products", "PV Systems", "contains"),
    ("battery_utility_connection", "Grid-tie", "equals", "Compliance", "GRT Exemption on Invoice", "confirm"),
]

# Batch 5 — Generators matrix (Off-Grid / Standby / Grid-Tied). Their
# "Standby" is our "Backup system". Note: per the table, standby
# generators do NOT get the grid-tie interconnection items — the table
# overrides the backup-follows-grid-tie general rule for generators.
SEED_RULES_V5 = [
    ("products", "Generators", "contains", "License", "LP-4/LP-5 or MM-2 Gas License", "if gas-fueled"),
    ("products", "Generators", "contains", "Compliance", "NFPA 37 Clearances", ""),
    ("generator_utility_connection", "Backup system", "equals", "Compliance", "Transfer Switch (NEC 702)", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "Transfer Switch (NEC 702)", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Permit", "Utility Interconnection Application", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "NMPRC Rule 568 Compliance", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "Utility-Accessible Lockable Disconnect", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "Signed Interconnection Agreement", ""),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "NM PE Stamp", "if >10 kVA grid-tied"),
    ("generator_utility_connection", "Grid-tie", "equals", "Compliance", "Utility Interconnection Inspection", ""),
]

SEED_BATCHES = {2: SEED_RULES_V2, 3: SEED_RULES_V3, 4: SEED_RULES_V4, 5: SEED_RULES_V5}

# One-off SQL applied alongside a batch (same once-only guarantee).
SEED_BATCH_SQL = {
    # Exterior Emergency Shutdown is residential-only per the battery
    # matrix; scope the original unconditional rule.
    4: ["UPDATE resource_rules SET field_name2 = 'property_type',"
        " field_value2 = 'Residential', match_type2 = 'equals'"
        " WHERE field_name = 'products' AND field_value = 'Battery Banks'"
        " AND label = 'Exterior Emergency Shutdown' AND field_name2 = ''"],
}

# ECC's main products/services — the multi-select on the job form.
PRODUCTS = [
    "PV Systems",
    "Generators",
    "Battery Banks",
    "Well Pumps",
    "Mini Split Air Conditioners",
    "Technician Service",
]

# Shown in the footer of every page so it's always obvious which build
# is running. Bumped with each piece.
VERSION = "Piece 4.5"

app = Flask(__name__)
# Needed for flash messages; fine as a constant for an internal single-box tool.
app.secret_key = "ecc-solar-job-creator"


@app.context_processor
def inject_version():
    return {"version": VERSION}


def get_db():
    """One database connection per request; rows behave like dicts."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_columns(db, table, columns):
    """Auto-upgrade an existing database: add any columns the table is
    missing. Lets the schema evolve piece by piece without anyone having
    to delete their job_creator.db."""
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for column in columns:
        if column not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT ''")


def init_db():
    """Create tables if missing, upgrade older databases, and add two
    sample clients the first time so the home page isn't empty."""
    db = sqlite3.connect(DATABASE)
    db.executescript((BASE_DIR / "schema.sql").read_text())
    # Field renamed after Piece 3.1: carry existing data over.
    client_cols = {row[1] for row in db.execute("PRAGMA table_info(clients)")}
    if "street_address" in client_cols and "mailing_address" not in client_cols:
        db.execute("ALTER TABLE clients RENAME COLUMN street_address TO mailing_address")
    ensure_columns(db, "clients", CLIENT_FIELDS)
    ensure_columns(db, "jobs", JOB_FIELDS)
    ensure_columns(db, "resource_rules", ["field_name2", "field_value2", "match_type2"])
    if db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO clients"
            " (name, phone, mailing_address, billing_address, email, referral_source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Johnson Residence (sample)", "505-555-0142",
                 "4512 Juniper Rd NE, Albuquerque, NM 87111",
                 "4512 Juniper Rd NE, Albuquerque, NM 87111",
                 "mjohnson@example.com", "Google search"),
                ("Rivera Residence (sample)", "575-555-0189",
                 "902 Mesa Verde Dr, Las Cruces, NM 88011",
                 "PO Box 2210, Las Cruces, NM 88004",
                 "", "Neighbor referral — the Ortiz install"),
            ],
        )
        db.execute(
            "INSERT INTO jobs (client_id, job_name, site_location, county,"
            " electric_loads, utility_provider, warranty_type, cost_method,"
            " tax_credit, expand_option, products, pv_utility_connection,"
            " pv_mounting_type, battery_utility_connection, property_type)"
            " VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Johnson PV + Battery (sample)",
             "4512 Juniper Rd NE, Albuquerque, NM 87111", "Bernalillo County",
             "3-ton AC, well pump, shop sub-panel", "PNM",
             "Standard 10-year", "Cash", "Yes", "Yes",
             "PV Systems, Battery Banks",
             "Grid-tie", "Roof mounted", "Grid-tie", "Residential"),
        )
        db.commit()
    if db.execute("SELECT COUNT(*) FROM resource_rules").fetchone()[0] == 0:
        insert_seed_rules(db, SEED_RULES)
        db.commit()
    # Later rule batches apply exactly once per database, so existing
    # installs receive new rules without duplicates — and rules someone
    # deleted on purpose don't come back on restart.
    row = db.execute("SELECT value FROM meta WHERE key = 'seed_version'").fetchone()
    seed_version = int(row[0]) if row else 1
    for batch_number in sorted(SEED_BATCHES):
        if batch_number > seed_version:
            insert_seed_rules(db, SEED_BATCHES[batch_number])
            for statement in SEED_BATCH_SQL.get(batch_number, []):
                db.execute(statement)
            seed_version = batch_number
    db.execute(
        "INSERT INTO meta (key, value) VALUES ('seed_version', ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(seed_version),),
    )
    db.commit()
    db.close()


def insert_seed_rules(db, rows):
    """Insert seed rows; 6-item rows are single-condition, 9-item rows
    carry a second AND condition."""
    normalized = []
    for row in rows:
        row = list(row)
        if len(row) == 6:
            row += ["", "", "equals"]
        normalized.append(row)
    db.executemany(
        "INSERT INTO resource_rules"
        " (field_name, field_value, match_type, category, label, notes,"
        "  field_name2, field_value2, match_type2)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        normalized,
    )


def condition_met(job, field, value, match_type):
    """One rule condition: the job's field equals the value
    (case-insensitive), or — for 'contains' — the value appears in the
    field's comma-separated list (used for products)."""
    if field not in job.keys():
        return False
    actual = str(job[field] or "").strip()
    if not actual:
        return False
    target = value.strip().lower()
    if match_type == "contains":
        return target in [p.strip().lower() for p in actual.split(",")]
    return actual.lower() == target


def match_rules(job, rules):
    """A rule matches when its condition holds — and, for compound rules,
    when the second condition holds too."""
    hits = []
    for rule in rules:
        if not condition_met(job, rule["field_name"], rule["field_value"],
                             rule["match_type"]):
            continue
        if rule["field_name2"] and not condition_met(
                job, rule["field_name2"], rule["field_value2"],
                rule["match_type2"] or "equals"):
            continue
        hits.append(rule)
    return hits


def group_rules(matched, dedupe=True):
    """Group matched rules by category in a fixed order. On job pages,
    de-duplicate shared requirements (e.g. PV and Battery both need
    EE-98); the directory keeps every rule so each trigger is visible."""
    groups, seen = {}, set()
    for rule in matched:
        key = (rule["category"], rule["label"].strip().lower())
        if dedupe and key in seen:
            continue
        seen.add(key)
        groups.setdefault(rule["category"], []).append(rule)
    ordered = []
    for category in RULE_CATEGORIES:
        if category in groups:
            ordered.append((CATEGORY_HEADINGS.get(category, category),
                            groups.pop(category)))
    for category in sorted(groups):
        ordered.append((CATEGORY_HEADINGS.get(category, category),
                        groups[category]))
    return ordered


@app.route("/")
def home():
    clients = get_db().execute(
        "SELECT * FROM clients ORDER BY name"
    ).fetchall()
    return render_template("index.html", clients=clients)


@app.route("/clients/new", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        values = {f: request.form.get(f, "").strip() for f in CLIENT_FIELDS}
        missing = [label for field, label in REQUIRED_CLIENT_FIELDS.items()
                   if not values[field]]
        if missing:
            flash(f"Required: {', '.join(missing)}.", "error")
            return render_template("client_form.html", values=values), 400
        db = get_db()
        cur = db.execute(
            f"INSERT INTO clients ({', '.join(CLIENT_FIELDS)})"
            f" VALUES ({', '.join('?' * len(CLIENT_FIELDS))})",
            [values[f] for f in CLIENT_FIELDS],
        )
        db.commit()
        flash(f"Client profile created: {values['name']}")
        return redirect(url_for("client_detail", client_id=cur.lastrowid))
    return render_template("client_form.html", values={})


@app.route("/clients/<int:client_id>")
def client_detail(client_id):
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    ).fetchone()
    if client is None:
        abort(404)
    jobs = db.execute(
        "SELECT * FROM jobs WHERE client_id = ? ORDER BY created_at DESC",
        (client_id,),
    ).fetchall()
    return render_template("client_detail.html", client=client, jobs=jobs)


@app.route("/clients/<int:client_id>/jobs/new", methods=["GET", "POST"])
def new_job(client_id):
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    ).fetchone()
    if client is None:
        abort(404)
    if request.method == "POST":
        values = {f: request.form.get(f, "").strip() for f in JOB_FIELDS}
        selected = request.form.getlist("products")
        values["products"] = ", ".join(p for p in PRODUCTS if p in selected)
        # Product-specific options only apply when their product is selected
        # (the browser hides the sections, but never trust hidden inputs).
        if "PV Systems" not in selected:
            values["pv_utility_connection"] = ""
            values["pv_mounting_type"] = ""
        if values["pv_mounting_type"] != "Roof mounted":
            values["pv_manufactured_house"] = ""
        if "Generators" not in selected:
            values["generator_utility_connection"] = ""
        if "Battery Banks" not in selected:
            values["battery_utility_connection"] = ""
        if "Technician Service" not in selected:
            values["service_type"] = ""
        errors = []
        if not values["job_name"]:
            errors.append("Job name is required.")
        if not values["site_location"]:
            errors.append("Site location is required.")
        if not values["products"]:
            errors.append("Select at least one product/service.")
        if "Technician Service" in selected and not values["service_type"]:
            errors.append("Specify general or warranty service.")
        # The utility connection state must match across PV, Generator,
        # and Battery Bank when more than one of them is on the job.
        connections = {values[f] for f in (
            "pv_utility_connection", "generator_utility_connection",
            "battery_utility_connection") if values[f]}
        if len(connections) > 1:
            errors.append(
                "Utility connection must match across all selected products"
                f" — currently: {', '.join(sorted(connections))}.")
        if errors:
            flash(" ".join(errors), "error")
            return render_template(
                "job_form.html", client=client, values=values,
                selected=selected, products=PRODUCTS,
                utility_connections=UTILITY_CONNECTIONS,
                mounting_types=MOUNTING_TYPES,
                service_types=SERVICE_TYPES,
                existing_jobs=db.execute(
                    "SELECT id, job_name FROM jobs WHERE client_id = ?",
                    (client_id,)).fetchall(),
            ), 400
        cur = db.execute(
            f"INSERT INTO jobs (client_id, {', '.join(JOB_FIELDS)})"
            f" VALUES (?, {', '.join('?' * len(JOB_FIELDS))})",
            [client_id] + [values[f] for f in JOB_FIELDS],
        )
        db.commit()
        flash(f"Job created under {client['name']}: {values['job_name']}")
        return redirect(url_for("job_detail", job_id=cur.lastrowid))
    # For service tickets: optionally pre-fill from a job already on the
    # books for this client.
    values = {"site_location": client["mailing_address"]}
    selected = []
    prefill_id = request.args.get("prefill", type=int)
    if prefill_id:
        source = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND client_id = ?",
            (prefill_id, client_id),
        ).fetchone()
        if source:
            values = {f: source[f] for f in JOB_FIELDS}
            values["job_name"] = f"Service — {source['job_name'] or 'Job #' + str(source['id'])}"
            selected = [p.strip() for p in source["products"].split(",") if p.strip()]
            if "Technician Service" not in selected:
                selected.append("Technician Service")
    return render_template(
        "job_form.html", client=client,
        values=values,
        selected=selected, products=PRODUCTS,
        utility_connections=UTILITY_CONNECTIONS,
        mounting_types=MOUNTING_TYPES,
        service_types=SERVICE_TYPES,
        existing_jobs=db.execute(
            "SELECT id, job_name FROM jobs WHERE client_id = ?",
            (client_id,)).fetchall(),
    )


def fetch_job(job_id):
    job = get_db().execute(
        "SELECT jobs.*, clients.name AS client_name"
        " FROM jobs JOIN clients ON clients.id = jobs.client_id"
        " WHERE jobs.id = ?",
        (job_id,),
    ).fetchone()
    if job is None:
        abort(404)
    return job


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = fetch_job(job_id)
    rules = get_db().execute("SELECT * FROM resource_rules").fetchall()
    groups = group_rules(match_rules(job, rules))
    return render_template("job_detail.html", job=job, groups=groups)


@app.route("/jobs/<int:job_id>/report")
def job_report(job_id):
    """Download a plain-text checklist report of the job's selections and
    every license, permit, and compliance item they resolve to."""
    job = fetch_job(job_id)
    rules = get_db().execute("SELECT * FROM resource_rules").fetchall()
    groups = group_rules(match_rules(job, rules))

    lines = [
        f"JOB REPORT — {job['job_name'] or 'Job #' + str(job['id'])}",
        f"Client: {job['client_name']}",
        f"Created: {job['created_at']}   Report generated: {datetime.now():%Y-%m-%d %H:%M}",
        "=" * 64,
        "",
        "JOB DETAILS",
        "-" * 64,
    ]
    for field in JOB_FIELDS:
        value = str(job[field] or "").strip()
        if value:
            lines.append(f"{JOB_FIELD_LABELS[field] + ':':34}{value}")
    for heading, items in groups:
        lines += ["", heading.upper(), "-" * 64]
        for rule in items:
            entry = f"[ ] {rule['label']}"
            if rule["notes"]:
                entry += f"  ({rule['notes']})"
            lines.append(entry)
            if rule["url"]:
                lines.append(f"      link:  {rule['url']}")
            if rule["phone"]:
                lines.append(f"      phone: {rule['phone']}")
    if not groups:
        lines += ["", "No license/permit/compliance requirements matched."]
    lines.append("")
    return Response(
        "\n".join(lines),
        mimetype="text/plain",
        headers={"Content-Disposition":
                 f"attachment; filename=job_{job_id}_report.txt"},
    )


@app.route("/rules")
def rules_page():
    db = get_db()
    rules = db.execute(
        "SELECT * FROM resource_rules"
        " ORDER BY field_name, field_value, category, label"
    ).fetchall()
    # When reached from a job page, offer a way back to that job.
    from_job = None
    from_job_id = request.args.get("from_job", type=int)
    if from_job_id:
        from_job = db.execute(
            "SELECT id, job_name FROM jobs WHERE id = ?", (from_job_id,)
        ).fetchone()
    return render_template(
        "rules.html", rules=rules, from_job=from_job,
        job_fields=[f for f in JOB_FIELDS if f != "job_name"],
        field_labels=JOB_FIELD_LABELS, categories=RULE_CATEGORIES,
    )


@app.route("/rules/new", methods=["POST"])
def add_rule():
    field_name = request.form.get("field_name", "").strip()
    field_value = request.form.get("field_value", "").strip()
    label = request.form.get("label", "").strip()
    from_job = request.form.get("from_job") or None
    field_name2 = request.form.get("field_name2", "").strip()
    field_value2 = request.form.get("field_value2", "").strip()
    if field_name not in JOB_FIELDS or not field_value or not label:
        flash("A rule needs a job field, a value to match, and a label.", "error")
        return redirect(url_for("rules_page", from_job=from_job))
    if field_name2 and (field_name2 not in JOB_FIELDS or not field_value2):
        flash("The second condition needs both a field and a value.", "error")
        return redirect(url_for("rules_page", from_job=from_job))
    db = get_db()
    db.execute(
        "INSERT INTO resource_rules"
        " (field_name, field_value, match_type, category, label, url, phone, notes,"
        "  field_name2, field_value2, match_type2)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (field_name, field_value,
         "contains" if field_name == "products" else "equals",
         request.form.get("category", "Compliance"),
         label,
         request.form.get("url", "").strip(),
         request.form.get("phone", "").strip(),
         request.form.get("notes", "").strip(),
         field_name2, field_value2,
         "contains" if field_name2 == "products" else "equals"),
    )
    db.commit()
    flash(f"Rule added: {label}")
    return redirect(url_for("rules_page", from_job=from_job))


@app.route("/directory")
def rule_directory():
    """Read-only, browsable view of every rule, filterable by job type
    and by the product variants. No editing happens here."""
    product = request.args.get("product", "")
    connection = request.args.get("connection", "")
    mounting = request.args.get("mounting", "")
    manufactured = request.args.get("manufactured", "")
    service = request.args.get("service", "")
    property_type = request.args.get("property", "")

    def value_ok(field, value):
        """One condition against the variant filters."""
        value = value.strip().lower()
        if connection and field in CONNECTION_FIELDS and value != connection.lower():
            return False
        if mounting and field == "pv_mounting_type" and value != mounting.lower():
            return False
        if manufactured and field == "pv_manufactured_house" and value != manufactured.lower():
            return False
        if service and field == "service_type" and value != service.lower():
            return False
        if property_type and field == "property_type" and value != property_type.lower():
            return False
        return True

    def visible(rule):
        conditions = [(rule["field_name"], rule["field_value"])]
        if rule["field_name2"]:
            conditions.append((rule["field_name2"], rule["field_value2"]))
        if not all(value_ok(f, v) for f, v in conditions):
            return False
        if product:
            # At least one condition must tie the rule to the chosen
            # job type (its product row or one of its variant fields).
            tied = any(
                (f == "products" and v.strip().lower() == product.lower())
                or (f in VARIANT_OWNERS and VARIANT_OWNERS[f] == product)
                for f, v in conditions)
            if not tied:
                return False
        return True

    rules = [r for r in get_db().execute(
        "SELECT * FROM resource_rules ORDER BY category, label"
    ).fetchall() if visible(r)]
    groups = group_rules(rules, dedupe=False)
    total = sum(len(items) for _, items in groups)
    return render_template(
        "directory.html", groups=groups, total=total,
        field_labels=JOB_FIELD_LABELS,
        products=PRODUCTS, utility_connections=UTILITY_CONNECTIONS,
        mounting_types=MOUNTING_TYPES, service_types=SERVICE_TYPES,
        property_types=PROPERTY_TYPES,
        filters={"product": product, "connection": connection,
                 "mounting": mounting, "manufactured": manufactured,
                 "service": service, "property": property_type},
        filtering=any([product, connection, mounting, manufactured,
                       service, property_type]),
    )


@app.route("/rules/<int:rule_id>/delete", methods=["POST"])
def delete_rule(rule_id):
    db = get_db()
    db.execute("DELETE FROM resource_rules WHERE id = ?", (rule_id,))
    db.commit()
    flash("Rule deleted.")
    return redirect(url_for("rules_page",
                            from_job=request.form.get("from_job") or None))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
