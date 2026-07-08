"""Job Creator — internal tool for ECC Solar.

Piece 1: Flask skeleton backed by SQLite. The home page lists client
profiles from the database.

Run it:
    pip install -r requirements.txt
    python app.py
then open http://localhost:5000 in your browser.
"""

import sqlite3
from pathlib import Path

from flask import Flask, g, render_template

BASE_DIR = Path(__file__).parent
DATABASE = BASE_DIR / "job_creator.db"

app = Flask(__name__)


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


def init_db():
    """Create tables if missing and add two sample clients the first time,
    so the home page has something to show before you enter real data."""
    db = sqlite3.connect(DATABASE)
    db.executescript((BASE_DIR / "schema.sql").read_text())
    if db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO clients (name, contact_name, phone, city, state, utility_company)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Johnson Residence (sample)", "Mark Johnson", "214-555-0142",
                 "Dallas", "TX", "Oncor"),
                ("Rivera Residence (sample)", "Ana Rivera", "713-555-0189",
                 "Houston", "TX", "CenterPoint Energy"),
            ],
        )
        db.commit()
    db.close()


@app.route("/")
def home():
    clients = get_db().execute(
        "SELECT * FROM clients ORDER BY name"
    ).fetchall()
    return render_template("index.html", clients=clients)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
