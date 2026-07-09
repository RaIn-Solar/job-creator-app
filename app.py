"""Job Creator — internal tool for ECC Solar.

Piece 1: Flask skeleton backed by SQLite; home page lists client profiles.
Piece 2: "New client" form and individual client profile pages.
Piece 3: job profiles stored under each client.

Run it:
    python -m pip install -r requirements.txt
    python app.py
then open http://127.0.0.1:5000 in your browser.
"""

import sqlite3
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

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
]

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
VERSION = "Piece 3.2"

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
    if db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO clients"
            " (name, phone, mailing_address, billing_address, email, referral_source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Johnson Residence (sample)", "214-555-0142",
                 "4512 Bluebonnet Ln, Dallas, TX 75214",
                 "4512 Bluebonnet Ln, Dallas, TX 75214",
                 "mjohnson@example.com", "Google search"),
                ("Rivera Residence (sample)", "713-555-0189",
                 "902 Heights Blvd, Houston, TX 77008",
                 "PO Box 2210, Houston, TX 77252",
                 "", "Neighbor referral — the Ortiz install"),
            ],
        )
        db.execute(
            "INSERT INTO jobs (client_id, job_name, site_location, county,"
            " electric_loads, utility_provider, warranty_type, cost_method,"
            " tax_credit, expand_option, products) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Johnson PV + Battery (sample)",
             "4512 Bluebonnet Ln, Dallas, TX 75214", "Dallas County",
             "3-ton AC, well pump, shop sub-panel", "Oncor",
             "Standard 10-year", "Cash", "Yes", "Yes",
             "PV Systems, Battery Banks"),
        )
        db.commit()
    db.close()


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
        errors = []
        if not values["job_name"]:
            errors.append("Job name is required.")
        if not values["site_location"]:
            errors.append("Site location is required.")
        if not values["products"]:
            errors.append("Select at least one product/service.")
        if errors:
            flash(" ".join(errors), "error")
            return render_template(
                "job_form.html", client=client, values=values,
                selected=selected, products=PRODUCTS,
            ), 400
        cur = db.execute(
            f"INSERT INTO jobs (client_id, {', '.join(JOB_FIELDS)})"
            f" VALUES (?, {', '.join('?' * len(JOB_FIELDS))})",
            [client_id] + [values[f] for f in JOB_FIELDS],
        )
        db.commit()
        flash(f"Job created under {client['name']}: {values['job_name']}")
        return redirect(url_for("job_detail", job_id=cur.lastrowid))
    return render_template(
        "job_form.html", client=client,
        values={"site_location": client["mailing_address"]},
        selected=[], products=PRODUCTS,
    )


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = get_db().execute(
        "SELECT jobs.*, clients.name AS client_name"
        " FROM jobs JOIN clients ON clients.id = jobs.client_id"
        " WHERE jobs.id = ?",
        (job_id,),
    ).fetchone()
    if job is None:
        abort(404)
    return render_template("job_detail.html", job=job)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
