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

import json
import math
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from functools import wraps

from flask import (
    Flask, Response, abort, flash, g, jsonify, redirect, render_template,
    request, session, send_from_directory, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from bpmn_export import build_job_bpmn
from nm_directory import (
    COUNTIES_ALL, CORRECTIONS_V10, NEW_RULES_V10, UTILITIES_ALL,
)
from loads_seed import APPLIANCE_SEED, COMPONENT_SEED

# Code assets (schema.sql, templates) sit next to this file — except under
# a PyInstaller desktop build, where they're unpacked into sys._MEIPASS.
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
# The writable data (database + uploaded files) lives in DATA_DIR. Normally
# that's the same folder; the desktop launcher points SOLBIZ_DATA_DIR at a
# stable per-user folder so a packaged app doesn't lose data on update.
DATA_DIR = Path(os.environ.get("SOLBIZ_DATA_DIR", BASE_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE = DATA_DIR / "job_creator.db"

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

# Employee directory (Piece 8). The core fields on a person's record:
# who they are, what they do, and when they work. Their licenses and
# certifications are structured rows in employee_credentials (Piece 8.1),
# managed on the profile page.
EMPLOYEE_FIELDS = ["name", "roles", "schedule"]
# Piece 13: an employee becomes a login by gaining a username + password +
# access level. Kept off the plain-text EMPLOYEE_FIELDS above and handled
# separately so a normal profile edit never touches account data by accident.
EMPLOYEE_AUTH_FIELDS = ["username", "password_hash", "access_level"]
ACCESS_LEVELS = ["Standard", "Admin"]
PASSWORD_MIN_LEN = 6
EMPLOYEE_FIELD_LABELS = {
    "name": "Name", "roles": "Roles", "schedule": "Schedule",
}
# Columns a user fills in when adding a license/certification.
CREDENTIAL_FIELDS = ["name", "rule_label", "number", "issued", "expires", "notes"]
# A credential within this many days of its expiry date is flagged
# "expiring soon" on the employee and job pages.
EXPIRY_SOON_DAYS = 60
# ECC's roles, offered as checkboxes on the employee form (the form also
# allows free-typed extras). An employee may hold any number of these;
# they're stored comma-separated, like the job form's products.
EMPLOYEE_ROLES = [
    "General Manager", "Sales and Marketing Manager", "Operations Manager",
    "Administration Manager", "Finance Manager",
    "Research and Development Manager", "Marketing Associate",
    "Inside Sales Rep", "Outside Sales Rep", "Designer", "Inventory Manager",
    "Permit Coordinator", "Scheduling Coordinator", "Lead Installer",
    "Service Technician", "Facilities Manager", "HR Manager",
    "Administrative Assistant", "Bookkeeper", "Product Portfolio Manager",
    "Process Developer", "Software Developer", "Payroll Manager",
    "Payroll Administrator", "Installer", "Warehouse Associate",
    "Purchasing Agent",
]

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
    "Link": "Online Portals",
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

# Batch 6 — corrections per ECC: Arc Flash is commercial-only, and the
# two SMDTC rules merge into one.
SEED_RULES_V6 = [
    ("products", "PV Systems", "contains", "Compliance", "SMDTC 20% Credit Application",
     "client files; batteries qualify when paired with solar"),
]

# Batch 7 — authoritative links from the "NM Solar Contractor Website
# Reference List" (June 2026), attached to the rules they support, plus
# utility-specific interconnection links keyed on the job's utility
# provider. The source document contains no phone numbers.
_CID_LICENSING = "https://www.rld.nm.gov/construction-industries-public-works/construction-industries/"
_CID_PORTAL = "https://nmrld.my.site.com/MHD/s/"
_NEC = "https://www.nfpa.org/codes-and-standards/nfpa-70-standard-for-electrical-installations/70"
_IFC = "https://codes.iccsafe.org/content/IFC2021"
_NFPA855 = "https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=855"
_PE_BOARD = "https://www.rld.nm.gov/engineering-and-land-surveying/"
_PNM_SOLAR = "https://www.pnm.com/solar"
_PNM_INTERCONNECT = "https://www.pnm.com/interconnection"

# (label, url, optional field_name filter for labels shared across products)
RULE_LINKS = [
    ("MM-2 or MM-3 Contractor License", _CID_LICENSING, None),
    ("Journeyman HVAC (JH) Certificate", _CID_LICENSING, None),
    ("EE-98 or ER-1 Electrical License", _CID_LICENSING, None),
    ("ES-10R Contractor License", _CID_LICENSING, None),
    ("ES-10RJ Journeyman", _CID_LICENSING, None),
    ("EE-98 Contractor License", _CID_LICENSING, None),
    ("EE-98J Journeyman", _CID_LICENSING, None),
    ("LP-4/LP-5 or MM-2 Gas License", "https://www.rld.nm.gov/lp-gas/", None),
    ("EPA Section 608 — Type II or Universal", "https://www.epa.gov/section608", None),
    ("AIM Act refrigerant (R-454B or R-32)", "https://www.epa.gov/climate-hfcs-reduction", None),
    ("Mechanical permit", _CID_PORTAL, None),
    ("Electrical permit", _CID_PORTAL, None),
    ("Building Permit (structural)", _CID_PORTAL, None),
    ("Rough-in Inspection", _CID_PORTAL, None),
    ("Final Inspection", _CID_PORTAL, None),
    ("Electrical Inspection", _CID_PORTAL, None),
    ("MHD Permit", "https://www.rld.nm.gov/manufactured-housing/", None),
    ("Transfer Switch (NEC 702)", _NEC, None),
    ("NFPA 37 Clearances", "https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=37", None),
    ("Full NEC 690 One-Line Package", _NEC, None),
    ("Rapid Shutdown (NEC 690.12)", _NEC, None),
    ("Rapid Shutdown (NEC 690.12) — exception", _NEC, None),
    ("Underground Wiring Plan + Depths", _NEC, None),
    ("Updated One-Line w/ ESS Disconnect", _NEC, None),
    ("NEC 706 Disconnect + Labeling", _NEC, None),
    ("Exterior Emergency Shutdown", _NEC, None),
    ("NEC 705 Interconnection (multi-source)", _NEC, None),
    ("Arc Flash Label", _NEC, None),
    ("Structural Analysis / NM PE Letter", _PE_BOARD, None),
    ("NM PE Stamp", _PE_BOARD, None),
    ("Fire Code Roof Access Clearances", _IFC, None),
    ("IFC Chapter 12 / Fire Code", _IFC, None),
    ("Smoke/Heat Detection (if enclosed)", _IFC, None),
    ("NFPA 855 Clearances + Spacing", _NFPA855, None),
    ("Ventilation Plan", _NFPA855, None),
    ("Hazard Mitigation Analysis (HMA)", _NFPA855, None),
    ("Fire Authority Plan Review", "https://www.dhsem.nm.gov/state-fire-marshal/", None),
    ("UL 9540 Equipment Listing", "https://www.ul.com/resources/ul-9540-standard-for-energy-storage-systems-and-equipment", None),
    ("IEEE 1547-2018 Inverter Listing", "https://standards.ieee.org/ieee/1547/6341/", None),
    ("NMPRC Rule 568 Compliance", "https://www.nmprc.state.nm.us/utilities/elec.html", None),
    ("SMDTC 20% Credit Application", "https://www.emnrd.nm.gov/sed/renewable-energy/solar-market-development-tax-credit/", None),
    ("GRT Exemption on Invoice", "https://www.tax.newmexico.gov/businesses/gross-receipts-tax/", None),
    # Shared labels: PV items point at PNM's solar program, generator
    # items at PNM's general interconnection page (per the document).
    ("Utility Interconnection Application", _PNM_SOLAR, "pv_utility_connection"),
    ("Signed Interconnection Agreement", _PNM_SOLAR, "pv_utility_connection"),
    ("Lockable Load-Break Disconnect", _PNM_SOLAR, "pv_utility_connection"),
    ("Utility Final Inspection + Anti-Island", _PNM_SOLAR, "pv_utility_connection"),
    ("Utility Interconnection Application", _PNM_INTERCONNECT, "generator_utility_connection"),
    ("Signed Interconnection Agreement", _PNM_INTERCONNECT, "generator_utility_connection"),
    ("Utility-Accessible Lockable Disconnect", _PNM_INTERCONNECT, "generator_utility_connection"),
    ("Utility Interconnection Inspection", _PNM_INTERCONNECT, "generator_utility_connection"),
    ("Utility Interconnection Update", _PNM_INTERCONNECT, "battery_utility_connection"),
]


def _link_sql(label, url, field=None):
    where = f"label = '{label}'"
    if field:
        where += f" AND field_name = '{field}'"
    return f"UPDATE resource_rules SET url = '{url}' WHERE {where}"


# Utility-specific portals become Link rules keyed on the job's utility
# provider (both utilities appear in the document).
SEED_RULES_V7 = [
    ("utility_provider", "PNM", "equals", "Link",
     "PNM — Solar Interconnection & Net Metering", "", "", "", "equals"),
    ("utility_provider", "Kit Carson Electric Cooperative", "equals", "Link",
     "Kit Carson Electric Cooperative", "", "", "", "equals"),
]

# Canonical values suggested on the job form so free-typed utilities and
# counties actually match the rules below.
UTILITIES = UTILITIES_ALL

# These products share one utility-connection choice on the job form.
GRID_PRODUCTS = ["PV Systems", "Battery Banks", "Generators"]
GRID_CONNECTION_FIELDS = {
    "PV Systems": "pv_utility_connection",
    "Generators": "generator_utility_connection",
    "Battery Banks": "battery_utility_connection",
}
COUNTIES = COUNTIES_ALL

# Batch 8 — from the Utility Interconnection Forms & AHJ Building Permit
# Forms documents (June 2026): per-utility forms/contacts and quirks,
# per-county AHJ permits, and new-well drilling subcontract notes.
SEED_RULES_V8 = [
    # --- Utility contacts & forms (fire on the job's utility provider) ---
    dict(field_name="utility_provider", field_value="MSMEC", category="Link",
         label="MSMEC — Interconnection Forms Hub",
         url="https://morasanmiguel.coop/forms",
         phone="575-383-4270 / 800-421-6773",
         notes="two tiers (≤10 kW / >10 kW); customer signs; approval before construction; rebates: thernandez@morasanmiguel.coop"),
    dict(field_name="utility_provider", field_value="KCEC", category="Compliance",
         label="KCEC Solar Net-Metering Pre-Screening — required FIRST",
         url="https://kitcarson.com/solar-net-metering-pre-screening-application",
         phone="575-758-2258",
         notes="mandatory first gate before the full application; systems >25 kW: email rmartinez@kitcarson.com"),
    dict(field_name="utility_provider", field_value="KCEC", category="Link",
         label="KCEC — Net-Metering Hub & Applications",
         url="https://kitcarson.com/electric/electric-info/net-metering/",
         phone="575-758-2258",
         notes="full application after pre-screening approval; NM Interconnection Manual p.24"),
    dict(field_name="utility_provider", field_value="Springer Electric", category="Link",
         label="Springer Electric — Forms Hub",
         url="https://www.springercoop.com/service-application-and-forms",
         phone="575-483-2421 / 800-288-1353",
         notes="submit by mail (PO Box 698, Springer) or fax 575-483-2692; closed Fridays; site blocks automated access — navigate from hub"),
    dict(field_name="utility_provider", field_value="JMEC", category="Link",
         label="JMEC — Solar Applications & Requirements Packet",
         url="https://www.jemezcoop.org/sites/default/files/2025-07/solar-applications-and-requirements.pdf",
         phone="505-753-2105 / 888-755-2105",
         notes="all-in-one packet; net metering up to 30 kW, April settle-up"),
    dict(field_name="utility_provider", field_value="JMEC", category="Compliance",
         label="JMEC Letter of Compliance (electrician closeout)",
         url="https://www.jemezcoop.org/forms",
         phone="888-755-2105",
         notes="JMEC-specific: licensed electrician's letter required before written authorization"),
    dict(field_name="utility_provider", field_value="PNM", category="Compliance",
         label="PNM portal application — customer-signed, $50 fee (<100 kW)",
         url="https://www.pnm.com/interconnection",
         phone="888-342-5766",
         notes="visible-air-gap lockable disconnect required (breakers/software modes do not qualify); permanent weatherproof one-line at point of service"),
    # --- AHJ building/structural permits (fire on the job's county) ---
    dict(field_name="county", field_value="Santa Fe County", category="Permit",
         label="Santa Fe County Development Permit (PV Solar)",
         url="https://www.santafecountynm.gov/growth-management/building-development/permitpackets",
         phone="505-986-6225",
         notes="unincorporated county: required for PV even without structural work; online via geocivix; expedited ~5 days; David Ruiz 505-986-6371",
         field_name2="products", field_value2="PV Systems", match_type2="contains"),
    dict(field_name="county", field_value="Taos County", category="Permit",
         label="Taos County Solar Array Zoning Clearance — FIRST",
         url="https://www.taoscounty.org/DocumentCenter/View/1914/Solar--Building-Permit-Application",
         phone="575-737-6300",
         notes="unincorporated county: required before the building permit; call office after online submittal; $80 re-inspection fee",
         field_name2="products", field_value2="PV Systems", match_type2="contains"),
    dict(field_name="county", field_value="Taos County", category="Permit",
         label="Taos County Building Permit (after zoning clearance)",
         url="https://www.taoscounty.org/DocumentCenter/View/2927/Building-Permit-Application",
         phone="575-737-6300",
         notes="use the 2024 revision",
         field_name2="products", field_value2="PV Systems", match_type2="contains"),
    dict(field_name="county", field_value="Rio Arriba County", category="Permit",
         label="Rio Arriba County Development Permit",
         url="https://www.rio-arriba.org/Departments/Departments-Divisions/Planning-and-Zoning/Forms-and-Permit-Applications",
         phone="505-685-8000",
         notes="single form covers solar/residential; 3–5 days; site visit arranged; NMDOT access permit if state road involved"),
] + [
    dict(field_name="county", field_value=county, category="Link",
         label="CID is your AHJ — structural permits via CID portal",
         url="https://nmrld.my.site.com/MHD/s/",
         phone="505-476-4700 / 877-CID-0979",
         notes="unincorporated areas; within city limits confirm the municipal building dept (Las Vegas 505-454-1401, Raton 575-445-9551)")
    for county in ("Mora County", "San Miguel County", "Colfax County",
                   "Harding County", "Guadalupe County")
] + [
    # --- New wells: drilling is subcontracted, outside ECC scope ---
    dict(field_name="products", field_value="Well Pumps", match_type="contains",
         category="Compliance",
         label="New well? OSE well drilling permit — SUBCONTRACT",
         url="https://www.ose.nm.gov/WR/well_drilling.php",
         notes="well drilling is outside ECC scope — subcontract to an OSE-licensed driller; applies to new wells only, not pump replacement"),
    dict(field_name="products", field_value="Well Pumps", match_type="contains",
         category="Compliance",
         label="New well? NMED water quality testing — subcontracted scope",
         url="https://www.env.nm.gov/drinking-water/",
         notes="new wells only; belongs to the drilling contractor's scope"),
]

# Batch 9 — named link sources, and state-run pages preferred: NEC and
# IFC rules point at New Mexico's own code-adoption pages (NMAC) instead
# of the publishers; standards bodies (UL/IEEE/NFPA) and utility/county
# sites remain the original sources.
_NMAC_NEC = "https://www.srca.nm.gov/parts/title14/14.010.0004.htm"
_NMAC_IFC = "https://www.srca.nm.gov/parts/title10/10.025.0005.htm"

LINK_TEXTS = {
    _CID_LICENSING: "NM CID — Contractor & Journeyman Licensing",
    _CID_PORTAL: "NM CID Online Permit Portal",
    "https://www.rld.nm.gov/lp-gas/": "NM RLD — LP Gas Bureau",
    "https://www.epa.gov/section608": "EPA Section 608 Certification",
    "https://www.epa.gov/climate-hfcs-reduction": "EPA AIM Act — HFC Phasedown",
    "https://www.rld.nm.gov/manufactured-housing/": "NM Manufactured Housing Division",
    _NMAC_NEC: "NMAC 14.10.4 — NM Adoption of NEC 2020",
    _NMAC_IFC: "NMAC 10.25.5 — NM Adoption of IFC 2021",
    "https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=37": "NFPA 37 — Stationary Combustion Engines",
    _NFPA855: "NFPA 855 — Stationary Energy Storage Systems",
    _PE_BOARD: "NM PE Board — Engineering & Surveying",
    "https://www.dhsem.nm.gov/state-fire-marshal/": "NM State Fire Marshal Office",
    "https://www.ul.com/resources/ul-9540-standard-for-energy-storage-systems-and-equipment": "UL 9540 — Energy Storage Systems Standard",
    "https://standards.ieee.org/ieee/1547/6341/": "IEEE 1547-2018 Standard",
    "https://www.nmprc.state.nm.us/utilities/elec.html": "NMPRC — Electric Utility Rules (17.9.568)",
    "https://www.emnrd.nm.gov/sed/renewable-energy/solar-market-development-tax-credit/": "NM EMNRD — Solar Market Development Tax Credit",
    "https://www.tax.newmexico.gov/businesses/gross-receipts-tax/": "NM Taxation & Revenue — Gross Receipts Tax",
    _PNM_SOLAR: "PNM — Solar & Net Metering",
    _PNM_INTERCONNECT: "PNM Interconnection Portal",
    "https://www.kitcarson.com": "Kit Carson Electric Cooperative",
    "https://morasanmiguel.coop/forms": "MSMEC Forms Hub",
    "https://kitcarson.com/solar-net-metering-pre-screening-application": "KCEC Pre-Screening Application",
    "https://kitcarson.com/electric/electric-info/net-metering/": "KCEC Net-Metering Hub",
    "https://www.springercoop.com/service-application-and-forms": "Springer Electric Forms Hub",
    "https://www.jemezcoop.org/sites/default/files/2025-07/solar-applications-and-requirements.pdf": "JMEC Solar Applications Packet (PDF)",
    "https://www.jemezcoop.org/forms": "JMEC Forms Hub",
    "https://www.santafecountynm.gov/growth-management/building-development/permitpackets": "Santa Fe County Permit Packets",
    "https://www.taoscounty.org/DocumentCenter/View/1914/Solar--Building-Permit-Application": "Taos County Zoning Clearance Application (PDF)",
    "https://www.taoscounty.org/DocumentCenter/View/2927/Building-Permit-Application": "Taos County Building Permit Application (PDF)",
    "https://www.rio-arriba.org/Departments/Departments-Divisions/Planning-and-Zoning/Forms-and-Permit-Applications": "Rio Arriba County Planning & Zoning Forms",
    "https://www.ose.nm.gov/WR/well_drilling.php": "NM OSE — Well Drilling & Licensing",
    "https://www.env.nm.gov/drinking-water/": "NMED Drinking Water Bureau",
}

SEED_BATCHES = {2: SEED_RULES_V2, 3: SEED_RULES_V3, 4: SEED_RULES_V4,
                5: SEED_RULES_V5, 6: SEED_RULES_V6, 7: SEED_RULES_V7,
                8: SEED_RULES_V8, 9: [], 10: NEW_RULES_V10}

# One-off SQL applied alongside a batch (same once-only guarantee).
SEED_BATCH_SQL = {
    # Exterior Emergency Shutdown is residential-only per the battery
    # matrix; scope the original unconditional rule.
    4: ["UPDATE resource_rules SET field_name2 = 'property_type',"
        " field_value2 = 'Residential', match_type2 = 'equals'"
        " WHERE field_name = 'products' AND field_value = 'Battery Banks'"
        " AND label = 'Exterior Emergency Shutdown' AND field_name2 = ''"],
    # Residential grid-tie needs no Arc Flash Label (commercial-only
    # compound rule remains); old SMDTC rules replaced by the merged one.
    6: ["DELETE FROM resource_rules WHERE label = 'Arc Flash Label'"
        " AND field_name = 'battery_utility_connection'",
        "DELETE FROM resource_rules WHERE label = 'SMDTC Application'",
        "DELETE FROM resource_rules WHERE label = 'SMDTC 20% Credit'"],
    # Attach the June 2026 reference-list links to their rules.
    7: [_link_sql(label, url, field) for label, url, field in RULE_LINKS] + [
        _link_sql("PNM — Solar Interconnection & Net Metering", _PNM_SOLAR),
        _link_sql("Kit Carson Electric Cooperative", "https://www.kitcarson.com"),
    ],
    # The generic interconnection rules were PNM-linked but apply to all
    # six providers: point them at governing NMPRC Rule 568 instead; the
    # serving utility's own forms come from the utility_provider rules.
    # Also normalize the batch-7 utility Link rules to canonical values.
    8: [_link_sql(label, "https://www.nmprc.state.nm.us/utilities/elec.html")
        for label in ("Utility Interconnection Application",
                      "Signed Interconnection Agreement",
                      "Lockable Load-Break Disconnect",
                      "Utility-Accessible Lockable Disconnect",
                      "Utility Final Inspection + Anti-Island",
                      "Utility Interconnection Inspection",
                      "Utility Interconnection Update")] + [
        "UPDATE resource_rules SET field_value = 'KCEC', phone = '575-758-2258'"
        " WHERE label = 'Kit Carson Electric Cooperative'",
        "UPDATE resource_rules SET phone = '888-342-5766'"
        " WHERE label = 'PNM — Solar Interconnection & Net Metering'",
    ],
    # State-run code pages replace publisher links, then every known url
    # gets its display name.
    9: [f"UPDATE resource_rules SET url = '{_NMAC_NEC}' WHERE url = '{_NEC}'",
        f"UPDATE resource_rules SET url = '{_NMAC_IFC}' WHERE url = '{_IFC}'"] + [
        f"UPDATE resource_rules SET link_text = '{text}' WHERE url = '{url}'"
        for url, text in LINK_TEXTS.items()
    ],
    # July 2026 verified reference set: corrections from the Manual
    # Review Log (dead NMPRC domain, EMNRD path, phones, SMDTC tier...).
    10: CORRECTIONS_V10,
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
VERSION = "Piece 14.1"

UPLOADS_DIR = DATA_DIR / "uploads"
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "heic", "gif", "doc", "docx", "xls", "xlsx",
    "csv", "txt", "kmz", "kml", "zip", "bpmn",
}
MATERIAL_STATUSES = ["Needed", "Ordered", "Received", "Installed"]
# Piece 12: categories for client-level documents (distinct from a job's
# requirement categories — these describe the client relationship).
CLIENT_FILE_CATEGORIES = ["Contracts", "Correspondence", "Intake", "Photos", "Other"]
# Piece 12.1: job pipeline stage (surfaced as a status picker + badges).
JOB_STATUSES = ["Lead", "Quoted", "Sold", "Permitting", "Scheduled",
                "Installed", "Closed", "Lost"]
JOB_STATUS_CLASS = {
    "Lead": "neutral", "Quoted": "neutral", "Sold": "warn",
    "Permitting": "warn", "Scheduled": "warn", "Installed": "",
    "Closed": "", "Lost": "danger",
}
# Piece 10: per-job task assignment.
TASK_STATUSES = ["To do", "In progress", "Blocked", "Done"]
# Piece 10.2: when generating tasks from the process, map each BPMN lane
# (the role responsible for a step) to the employee role(s) that would own
# it, so a step can auto-assign to the person who holds that role. Lanes
# not listed (Solbiz System, Authorities (CID), Utility Company) are
# external/automated and never auto-assign.
LANE_TO_ROLES = {
    "Sales Rep": ["Outside Sales Rep", "Inside Sales Rep", "Sales and Marketing Manager"],
    "System Designer": ["Designer"],
    "Permit Coordinator": ["Permit Coordinator"],
    "Warehouse Associate": ["Warehouse Associate", "Purchasing Agent"],
    "Foreman": ["Lead Installer"],
    "Finance Department": ["Finance Manager", "Bookkeeper", "Payroll Manager"],
    "General Manager": ["General Manager"],
}
# Days between consecutive generated tasks when a target install date is
# given — a rough schedule anchored on the Site Installation step.
TASK_DUE_SPACING_DAYS = 2

# Piece 9: Electric Loads Calculator / System Sizing config (ported from
# the standalone loads_calculator.html field tool). Catalogs themselves
# live in appliance_catalog / component_catalog (seeded from loads_seed.py).
LOAD_USAGE_TYPES = ["Always-on", "Daily", "Occasional", "Seasonal"]
LOAD_ERAS = ["Modern", "Vintage"]
ROOM_TYPES = ["standard", "scenario"]
COMPONENT_CATEGORIES = [
    "Battery", "Breaker", "Breaker Panel", "Charge Controller", "Controls",
    "Electrical", "Enclosure", "Generator", "Inverter", "Monitoring",
    "Office Supplies", "Optimizer", "Pumping", "PV Module", "Racking", "Wire",
]
# system_type presets auto-fill sizing fields on the job page; system_type
# reverts to "custom" on manual edit of a preset-controlled field.
SYSTEM_TYPE_PRESETS = {
    "offgrid": {"derate_pct": 70, "autonomy_days": 3},
    "gridtie": {"derate_pct": 80, "autonomy_days": 1.5},
}
UI_MODES = ["sales", "designer"]

app = Flask(__name__, template_folder=str(BASE_DIR / "templates"))
# Needed for flash messages; fine as a constant for an internal single-box tool.
app.secret_key = "ecc-solar-job-creator"
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB per upload


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


# ------------------------------------------------------------- audit log
# Friendlier names for a few endpoints; everything else is prettified from
# the view function name (e.g. delete_component_catalog -> "Delete component
# catalog"), so new routes are logged readably without extra wiring.
ACTION_LABELS = {
    "new_client": "Create client", "new_job": "Create job",
    "edit_job": "Edit job", "add_rule": "Add rule", "delete_rule": "Delete rule",
    "new_employee": "Add employee", "edit_employee": "Edit employee",
    "delete_employee": "Delete employee", "upload_file": "Upload job document",
    "generate_tasks": "Generate tasks from process",
    "set_task_status": "Change task status", "set_task_assignee": "Reassign task",
    "set_task_due": "Change task due date", "set_ui_mode": "Change sizing view mode",
    "update_sizing": "Update system sizing",
}
# Endpoints whose POSTs are not user data changes worth logging.
AUDIT_SKIP_ENDPOINTS = set()


def _audit_action(endpoint):
    if not endpoint:
        return "Request"
    return ACTION_LABELS.get(endpoint, endpoint.replace("_", " ").capitalize())


def _audit_detail():
    """A compact JSON snapshot of the submitted fields (the 'input'),
    excluding the redirect helper and truncating long values; uploaded
    file names are noted too."""
    data = {}
    for key in request.form:
        if key == "next":
            continue
        if "password" in key.lower():
            data[key] = "***"          # never log secrets
            continue
        vals = request.form.getlist(key)
        val = vals if len(vals) > 1 else (vals[0] if vals else "")
        if isinstance(val, str) and len(val) > 300:
            val = val[:300] + "…"
        data[key] = val
    names = [f.filename for f in request.files.values() if f and f.filename]
    if names:
        data["_files"] = names
    return json.dumps(data, ensure_ascii=False)[:2000]


@app.after_request
def audit(response):
    """Record every state-changing request. Central by design: nothing a
    feature does can bypass it. Never allowed to break a real request."""
    try:
        if (request.method in ("POST", "PUT", "PATCH", "DELETE")
                and request.endpoint and request.endpoint not in AUDIT_SKIP_ENDPOINTS):
            db = get_db()
            user = current_user()
            db.execute(
                "INSERT INTO audit_log"
                " (actor, action, endpoint, method, path, entity, detail, status, ip)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user["name"] if user else "", _audit_action(request.endpoint),
                 request.endpoint,
                 request.method, request.path,
                 json.dumps(request.view_args or {}, ensure_ascii=False),
                 _audit_detail(), response.status_code, request.remote_addr or ""),
            )
            db.commit()
    except Exception:
        pass
    return response


# --------------------------------------------------------------- auth (Piece 13)
def accounts_exist():
    """True once at least one employee has a usable login. Until then the
    app runs in open mode (no login wall) so nothing locks up and setup is
    possible."""
    row = get_db().execute(
        "SELECT COUNT(*) FROM employees"
        " WHERE COALESCE(username,'') != '' AND COALESCE(password_hash,'') != ''"
    ).fetchone()
    return row[0] > 0


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute(
        "SELECT * FROM employees WHERE id = ?", (uid,)).fetchone()


def _is_admin():
    """Admin, OR open mode (no accounts yet) so the first admin can be set up."""
    if not accounts_exist():
        return True
    user = current_user()
    return user is not None and user["access_level"] == "Admin"


def admin_required(view):
    """Guard admin-only actions (editing shared data + accounts + the log)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _is_admin():
            flash("That action is limited to admin accounts.", "error")
            return redirect(url_for("home"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_auth():
    user = current_user()
    is_admin = _is_admin()
    pending = 0
    if is_admin:
        try:
            pending = get_db().execute(
                "SELECT COUNT(*) FROM field_submissions WHERE status = 'Pending'"
            ).fetchone()[0]
        except Exception:
            pending = 0
    return {"current_user": user, "login_active": accounts_exist(),
            "is_admin": is_admin, "pending_submissions": pending}


@app.before_request
def require_login():
    """Once logins are configured, every page needs one (except the login
    page itself and static files). In open mode this does nothing."""
    if not accounts_exist():
        return
    if request.endpoint in ("login", "static", None):
        return
    if current_user() is None:
        if request.path.startswith("/api/"):
            return jsonify({"error": "not signed in"}), 401
        nxt = request.path if request.method == "GET" else None
        return redirect(url_for("login", next=nxt))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM employees WHERE username = ? AND COALESCE(username,'') != ''",
            (username,)).fetchone()
        if user and user["password_hash"] and check_password_hash(
                user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Signed in as {user['name']}.")
            nxt = request.form.get("next") or ""
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("home"))
        flash("Wrong username or password.", "error")
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    flash("Signed out.")
    return redirect(url_for("login"))


@app.route("/account")
def account():
    """The signed-in user's own page: change your password (with admin
    approval) and see any pending request."""
    user = current_user()
    if user is None:
        return redirect(url_for("home"))
    pending = get_db().execute(
        "SELECT * FROM password_requests WHERE employee_id = ? AND status = 'Pending'"
        " ORDER BY id DESC LIMIT 1", (user["id"],)).fetchone()
    return render_template("account.html", user=user, pending=pending)


@app.route("/account/password", methods=["POST"])
def request_password_change():
    """Verify the current password, hash the proposed one, and queue it for
    admin approval. The new password is stored only as a hash."""
    user = current_user()
    if user is None:
        return redirect(url_for("home"))
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not user["password_hash"] or not check_password_hash(user["password_hash"], current):
        flash("Your current password is incorrect.", "error")
    elif len(new) < PASSWORD_MIN_LEN:
        flash(f"New password must be at least {PASSWORD_MIN_LEN} characters.", "error")
    elif new != confirm:
        flash("New password and confirmation don't match.", "error")
    else:
        db = get_db()
        # One pending request at a time — a new one supersedes the old.
        db.execute("DELETE FROM password_requests"
                   " WHERE employee_id = ? AND status = 'Pending'", (user["id"],))
        db.execute(
            "INSERT INTO password_requests (employee_id, new_hash) VALUES (?, ?)",
            (user["id"], generate_password_hash(new)))
        db.commit()
        flash("Password change submitted — it takes effect once an admin approves it.")
    return redirect(url_for("account"))


@app.route("/account/password/cancel", methods=["POST"])
def cancel_password_change():
    user = current_user()
    if user is None:
        return redirect(url_for("home"))
    db = get_db()
    db.execute("DELETE FROM password_requests"
               " WHERE employee_id = ? AND status = 'Pending'", (user["id"],))
    db.commit()
    flash("Password request cancelled.")
    return redirect(url_for("account"))


def ensure_columns(db, table, columns):
    """Auto-upgrade an existing database: add any columns the table is
    missing. Lets the schema evolve piece by piece without anyone having
    to delete their job_creator.db."""
    existing = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    for column in columns:
        if column not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT ''")


def init_db():
    """Create tables if missing, upgrade older databases, and add three
    sample clients (one job each) the first time so the app isn't empty."""
    db = sqlite3.connect(DATABASE)
    db.executescript((BASE_DIR / "schema.sql").read_text())
    # Field renamed after Piece 3.1: carry existing data over.
    client_cols = {row[1] for row in db.execute("PRAGMA table_info(clients)")}
    if "street_address" in client_cols and "mailing_address" not in client_cols:
        db.execute("ALTER TABLE clients RENAME COLUMN street_address TO mailing_address")
    ensure_columns(db, "clients", CLIENT_FIELDS)
    ensure_columns(db, "jobs", JOB_FIELDS + ["status"])
    # Existing jobs predate the status column; give blanks the default stage.
    db.execute("UPDATE jobs SET status = 'Lead' WHERE COALESCE(status, '') = ''")
    # Piece 14: change-tracking for task sync; seed blanks from created_at.
    ensure_columns(db, "job_tasks", ["updated_at"])
    db.execute("UPDATE job_tasks SET updated_at = COALESCE(NULLIF(created_at,''),"
               " datetime('now')) WHERE COALESCE(updated_at,'') = ''")
    ensure_columns(db, "employees", EMPLOYEE_FIELDS + EMPLOYEE_AUTH_FIELDS)
    ensure_columns(db, "resource_rules",
                   ["field_name2", "field_value2", "match_type2", "link_text"])
    if db.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO clients"
            " (name, phone, mailing_address, billing_address, email, referral_source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Johnson Residence (sample)", "575-555-0142",
                 "1247 Highway 518, Mora, NM 87732",
                 "1247 Highway 518, Mora, NM 87732",
                 "mjohnson@example.com", "Google search"),
                ("Rivera Residence (sample)", "505-555-0189",
                 "902 Mesa Verde Dr, Las Vegas, NM 87701",
                 "PO Box 2210, Las Vegas, NM 87701",
                 "", "Neighbor referral — the Ortiz install"),
                ("Sandia Ridge Winery (sample)", "505-555-0173",
                 "58 Bonanza Creek Rd, Santa Fe, NM 87508",
                 "PO Box 4415, Santa Fe, NM 87502",
                 "office@sandiaridge.example.com", "Repeat commercial client"),
            ],
        )
        # One sample job per client, chosen to show off different paths
        # through the rules engine: residential grid-tie, off-grid multi-
        # product, and a commercial install.
        db.executemany(
            "INSERT INTO jobs (client_id, job_name, site_location, county,"
            " electric_loads, utility_provider, warranty_type, cost_method,"
            " tax_credit, expand_option, products, pv_utility_connection,"
            " pv_mounting_type, pv_manufactured_house, generator_utility_connection,"
            " battery_utility_connection, service_type, property_type)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "Johnson PV + Battery (sample)",
                 "1247 Highway 518, Mora, NM 87732", "Mora County",
                 "3-ton AC, well pump, shop sub-panel", "MSMEC",
                 "Standard 10-year", "Cash", "Yes", "Yes",
                 "PV Systems, Battery Banks",
                 "Grid-tie", "Roof mounted", "", "", "Grid-tie", "", "Residential"),
                (2, "Rivera Off-Grid Cabin (sample)",
                 "902 Mesa Verde Dr, Las Vegas, NM 87701", "San Miguel County",
                 "Well pump, lighting, propane range, mini split", "Springer Electric",
                 "Standard 10-year", "Finance", "Yes", "No",
                 "PV Systems, Battery Banks, Generators",
                 "Off-grid", "Ground mount", "", "Off-grid", "Off-grid", "", "Residential"),
                (3, "Sandia Ridge Commercial PV (sample)",
                 "58 Bonanza Creek Rd, Santa Fe, NM 87508", "Santa Fe County",
                 "Winery process loads, cold storage, tasting room", "PNM",
                 "Standard 10-year", "Cash", "No", "No",
                 "PV Systems, Battery Banks",
                 "Grid-tie", "Roof mounted", "", "", "Grid-tie", "", "Commercial"),
            ],
        )
        emp1 = db.execute(
            "INSERT INTO employees (name, roles, schedule) VALUES (?, ?, ?)",
            ("Daniel Ortiz (sample)", "Lead Installer, Installer",
             "Mon–Fri 7:00 AM – 4:00 PM")).lastrowid
        emp2 = db.execute(
            "INSERT INTO employees (name, roles, schedule) VALUES (?, ?, ?)",
            ("Maria Sandoval (sample)", "Operations Manager, Administration Manager",
             "Mon–Fri 8:00 AM – 5:00 PM")).lastrowid
        db.executemany(
            "INSERT INTO employee_credentials"
            " (employee_id, name, rule_label, number, issued, expires, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (emp1, "EE-98J Journeyman", "EE-98J Journeyman", "JX-4821",
                 "2023-03-15", "2027-03-15", "per tech on site"),
                (emp1, "EPA Section 608 — Universal",
                 "EPA Section 608 — Type II or Universal", "", "2019-05-01", "", ""),
                (emp1, "OSHA 30", "", "", "2022-06-01", "", ""),
                (emp2, "NABCEP PV Associate", "", "", "2024-01-10", "", ""),
                (emp2, "First Aid / CPR", "", "", "2024-08-25", "2026-08-25", ""),
            ],
        )
        # A few sample tasks so the Tasks tab isn't empty in the demo.
        db.executemany(
            "INSERT INTO job_tasks"
            " (job_id, employee_id, title, status, due_date, notes, sort_order)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, emp1, "Pull electrical permit (MSMEC)", "In progress", "", "", 0),
                (1, emp2, "Submit SMDTC 20% credit application", "To do", "", "client files", 1),
                (1, emp1, "Schedule rough-in inspection", "To do", "", "", 2),
                (3, emp1, "Fire authority plan review — commercial ESS", "Blocked", "", "waiting on AHJ", 0),
                (3, emp2, "Order utility interconnection application (PNM)", "To do", "", "", 1),
            ],
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
    # Piece 9: appliance + component catalogs seed once, the same way the
    # sample clients above do — not via the rule-style batch system, since
    # they're reference tables of their own rather than resource_rules rows.
    if db.execute("SELECT COUNT(*) FROM appliance_catalog").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO appliance_catalog"
            " (name, category, era, low_w, high_w, avg_w, hrs_per_day,"
            "  usage_type, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            APPLIANCE_SEED,
        )
        db.commit()
    if db.execute("SELECT COUNT(*) FROM component_catalog").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO component_catalog"
            " (name, category, manufacturer, model, specs, watts, voc, vmp,"
            "  temp_coef_voc, capacity_kwh_nameplate, dod, max_input_v,"
            "  continuous_w, inverter_eff, cost, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            COMPONENT_SEED,
        )
        db.commit()
    db.close()


RULE_COLUMNS = ["field_name", "field_value", "match_type", "category", "label",
                "notes", "url", "phone", "field_name2", "field_value2",
                "match_type2", "link_text"]


def insert_seed_rules(db, rows):
    """Insert seed rows. Tuples: 6 items = single condition, 9 items =
    compound. Dicts may set any rule column (url, phone, ...)."""
    normalized = []
    for row in rows:
        if isinstance(row, dict):
            r = [row.get(c, "") for c in RULE_COLUMNS]
        else:
            row = list(row)
            if len(row) == 6:
                row += ["", "", "equals"]
            r = row[:6] + ["", ""] + row[6:]
        while len(r) < len(RULE_COLUMNS):
            r.append("")
        if not r[2]:
            r[2] = "equals"
        if not r[10]:
            r[10] = "equals"
        normalized.append(r)
    db.executemany(
        f"INSERT INTO resource_rules ({', '.join(RULE_COLUMNS)})"
        f" VALUES ({', '.join('?' * len(RULE_COLUMNS))})",
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


def credential_status(expires):
    """Classify a credential by its expiry date: returns (state, text)
    where state is expired / soon / ok / none, and text is a short label
    for display."""
    expires = (expires or "").strip()
    if not expires:
        return ("none", "no expiry")
    try:
        exp = datetime.strptime(expires, "%Y-%m-%d").date()
    except ValueError:
        return ("none", expires)
    days = (exp - datetime.now().date()).days
    if days < 0:
        return ("expired", f"expired {expires}")
    if days <= EXPIRY_SOON_DAYS:
        return ("soon", f"expires {expires} ({days} d)")
    return ("ok", f"expires {expires}")


def license_staffing():
    """For each License requirement label, the employees who hold a
    matching credential (tied via rule_label), each with its expiry state.
    Drives the 'who on staff is licensed' badges on job pages."""
    rows = get_db().execute(
        "SELECT c.rule_label, c.expires, e.name AS emp_name"
        " FROM employee_credentials c"
        " JOIN employees e ON e.id = c.employee_id"
        " WHERE c.rule_label != ''"
        " ORDER BY e.name"
    ).fetchall()
    staffing = {}
    for r in rows:
        state, _ = credential_status(r["expires"])
        staffing.setdefault(r["rule_label"], []).append(
            {"name": r["emp_name"], "state": state})
    return staffing


# ------------------------------------------------------- Piece 9: loads/sizing
def fetch_job_sizing(db, job_id):
    """One job_sizing row always exists once a job's Loads tab is opened;
    create it lazily with defaults from the schema."""
    row = db.execute("SELECT * FROM job_sizing WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        db.execute("INSERT INTO job_sizing (job_id) VALUES (?)", (job_id,))
        db.commit()
        row = db.execute("SELECT * FROM job_sizing WHERE job_id = ?", (job_id,)).fetchone()
    return row


def compute_load_totals(rooms, items):
    """Daily kWh and peak watts across every ENABLED room only — a
    disabled scenario room's items are excluded without being deleted."""
    enabled = {r["id"] for r in rooms if r["enabled"]}
    daily_kwh = 0.0
    peak_w = 0.0
    for it in items:
        if it["room_id"] not in enabled:
            continue
        w = (it["watts"] or 0) * (it["qty"] or 0)
        peak_w += w
        daily_kwh += w * (it["hrs"] or 0) / 1000.0
    return daily_kwh, peak_w


def compute_array(daily_kwh, sun_hours, derate_pct, solar_fraction_pct, panel_watts):
    """Array sizing: daily kWh (scaled by the solar fraction) divided by
    peak sun hours and the derate factor gives array kW; panel count is
    that array size divided by a single panel's wattage, rounded up."""
    derate = (derate_pct or 0) / 100.0
    frac = (solar_fraction_pct or 100) / 100.0
    if not sun_hours or sun_hours <= 0 or derate <= 0:
        return 0.0, 0
    array_kw = (daily_kwh * frac) / (sun_hours * derate)
    panel_count = math.ceil((array_kw * 1000) / panel_watts) if panel_watts else 0
    return array_kw, panel_count


def compute_battery_kwh(backup_daily_kwh, autonomy_days, dod_pct,
                         round_trip_eff_pct, inverter_eff_pct):
    """Usable backup load over the autonomy window, grossed up for
    depth-of-discharge and round-trip/inverter losses, gives the
    nameplate battery kWh needed."""
    dod = (dod_pct or 0) / 100.0
    rte = (round_trip_eff_pct or 100) / 100.0
    inv = (inverter_eff_pct or 100) / 100.0
    if dod <= 0 or rte <= 0 or inv <= 0:
        return 0.0
    return (backup_daily_kwh or 0) * (autonomy_days or 0) / dod / (rte * inv)


def compute_voc(voc_rated, temp_coef_pct, record_low_temp_f, max_input_v):
    """NEC 690.7 Method 1 cold-temperature Voc correction: correct the
    module's rated Voc to the site's record low, then divide the inverter/
    charge controller's max input voltage by that to get the longest
    allowed string length."""
    if not voc_rated or temp_coef_pct is None:
        return None, None
    tmin_c = ((record_low_temp_f or 32) - 32) * 5.0 / 9.0
    voc_corrected = voc_rated * (1 + (temp_coef_pct / 100.0) * (tmin_c - 25))
    max_modules = math.floor(max_input_v / voc_corrected) if voc_corrected > 0 and max_input_v else 0
    return voc_corrected, max_modules


@app.route("/")
def home():
    clients = get_db().execute(
        "SELECT * FROM clients ORDER BY name"
    ).fetchall()
    return render_template("index.html", clients=clients)


@app.route("/search")
def search():
    """Quick lookup across clients and jobs by name/address/phone/email/
    county."""
    q = (request.args.get("q") or "").strip()
    clients, jobs = [], []
    if q:
        like = f"%{q}%"
        db = get_db()
        clients = db.execute(
            "SELECT * FROM clients"
            " WHERE name LIKE ? OR mailing_address LIKE ? OR billing_address LIKE ?"
            " OR phone LIKE ? OR email LIKE ? ORDER BY name",
            (like, like, like, like, like)).fetchall()
        jobs = db.execute(
            "SELECT j.*, c.name AS client_name FROM jobs j"
            " JOIN clients c ON c.id = j.client_id"
            " WHERE j.job_name LIKE ? OR j.site_location LIKE ? OR j.county LIKE ?"
            " OR j.products LIKE ? OR c.name LIKE ? ORDER BY j.created_at DESC",
            (like, like, like, like, like)).fetchall()
    return render_template("search.html", q=q, clients=clients, jobs=jobs,
                           job_status_class=JOB_STATUS_CLASS)


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


@app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
def edit_client(client_id):
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if client is None:
        abort(404)
    if request.method == "POST":
        values = {f: request.form.get(f, "").strip() for f in CLIENT_FIELDS}
        missing = [label for field, label in REQUIRED_CLIENT_FIELDS.items()
                   if not values[field]]
        if missing:
            flash(f"Required: {', '.join(missing)}.", "error")
            return render_template("client_form.html", values=values,
                                   client_id=client_id), 400
        db.execute(
            f"UPDATE clients SET {', '.join(f + ' = ?' for f in CLIENT_FIELDS)}"
            " WHERE id = ?",
            [values[f] for f in CLIENT_FIELDS] + [client_id],
        )
        db.commit()
        flash(f"Client profile updated: {values['name']}")
        return redirect(url_for("client_detail", client_id=client_id))
    values = {f: client[f] for f in CLIENT_FIELDS}
    return render_template("client_form.html", values=values, client_id=client_id)


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
    files = db.execute(
        "SELECT * FROM client_files WHERE client_id = ? ORDER BY id", (client_id,)
    ).fetchall()
    return render_template("client_detail.html", client=client, jobs=jobs,
                           files=files, file_categories=CLIENT_FILE_CATEGORIES,
                           job_status_class=JOB_STATUS_CLASS)


# ---- client-level documents (contracts, correspondence, intake, photos) ---
def client_upload_dir(client_id):
    directory = UPLOADS_DIR / f"client_{client_id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@app.route("/clients/<int:client_id>/files/upload", methods=["POST"])
def upload_client_file(client_id):
    if get_db().execute("SELECT id FROM clients WHERE id = ?",
                        (client_id,)).fetchone() is None:
        abort(404)
    upload = request.files.get("document")
    if upload is None or not upload.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("client_detail", client_id=client_id, _anchor="documents"))
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash(f"File type .{extension} is not allowed.", "error")
        return redirect(url_for("client_detail", client_id=client_id, _anchor="documents"))
    category = request.form.get("category", "").strip()
    if category not in CLIENT_FILE_CATEGORIES:
        category = ""
    original = upload.filename
    stored = f"{uuid.uuid4().hex[:8]}_{secure_filename(original)}"
    upload.save(client_upload_dir(client_id) / stored)
    db = get_db()
    db.execute(
        "INSERT INTO client_files (client_id, category, stored_name, original_name)"
        " VALUES (?, ?, ?, ?)",
        (client_id, category, stored, original),
    )
    db.commit()
    flash(f"Uploaded: {original}")
    return redirect(url_for("client_detail", client_id=client_id, _anchor="documents"))


@app.route("/clients/<int:client_id>/files/<int:file_id>/download")
def download_client_file(client_id, file_id):
    record = get_db().execute(
        "SELECT * FROM client_files WHERE id = ? AND client_id = ?",
        (file_id, client_id)).fetchone()
    if record is None:
        abort(404)
    return send_from_directory(
        client_upload_dir(client_id), record["stored_name"],
        as_attachment=True, download_name=record["original_name"])


@app.route("/clients/<int:client_id>/files/<int:file_id>/delete", methods=["POST"])
def delete_client_file(client_id, file_id):
    db = get_db()
    record = db.execute(
        "SELECT * FROM client_files WHERE id = ? AND client_id = ?",
        (file_id, client_id)).fetchone()
    if record:
        (client_upload_dir(client_id) / record["stored_name"]).unlink(missing_ok=True)
        db.execute("DELETE FROM client_files WHERE id = ?", (record["id"],))
        db.commit()
        flash(f"Deleted: {record['original_name']}")
    return redirect(url_for("client_detail", client_id=client_id, _anchor="documents"))


@app.route("/clients/<int:client_id>/jobs/new", methods=["GET", "POST"])
def new_job(client_id):
    db = get_db()
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    ).fetchone()
    if client is None:
        abort(404)
    if request.method == "POST":
        values, selected, errors = read_job_form()
        if errors:
            flash(" ".join(errors), "error")
            return render_job_form(client, values, selected,
                                   existing_jobs=True), 400
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
            values["utility_connection"] = next(
                (source[f] for f in GRID_CONNECTION_FIELDS.values() if source[f]), "")
            values["job_name"] = f"Service — {source['job_name'] or 'Job #' + str(source['id'])}"
            selected = [p.strip() for p in source["products"].split(",") if p.strip()]
            if "Technician Service" not in selected:
                selected.append("Technician Service")
    return render_job_form(client, values, selected, existing_jobs=True)


def read_job_form():
    """Validate and normalize a submitted job form (create or edit)."""
    values = {f: request.form.get(f, "").strip() for f in JOB_FIELDS}
    selected = request.form.getlist("products")
    values["products"] = ", ".join(p for p in PRODUCTS if p in selected)
    # One shared utility-connection choice covers PV, Battery, and
    # Generators; it lands in each selected system's own column (which
    # the rules engine matches on), blank for unselected systems.
    shared = request.form.get("utility_connection", "").strip()
    for product, field in GRID_CONNECTION_FIELDS.items():
        values[field] = shared if product in selected else ""
    values["utility_connection"] = shared  # for form re-render only
    # Product-specific options only apply when their product is selected
    # (the browser hides the sections, but never trust hidden inputs).
    if "PV Systems" not in selected:
        values["pv_mounting_type"] = ""
    if values["pv_mounting_type"] != "Roof mounted":
        values["pv_manufactured_house"] = ""
    if "Technician Service" not in selected:
        values["service_type"] = ""
    errors = []
    if not values["job_name"]:
        errors.append("Job name is required.")
    if not values["site_location"]:
        errors.append("Site location is required.")
    if not values["cost_method"]:
        errors.append("Cost method is required.")
    if not values["products"]:
        errors.append("Select at least one product/service.")
    if "Technician Service" in selected and not values["service_type"]:
        errors.append("Specify general or warranty service.")
    return values, selected, errors


def render_job_form(client, values, selected, existing_jobs=False,
                    editing_job_id=None):
    jobs_on_books = []
    if existing_jobs and not editing_job_id:
        jobs_on_books = get_db().execute(
            "SELECT id, job_name FROM jobs WHERE client_id = ?",
            (client["id"],)).fetchall()
    return render_template(
        "job_form.html", client=client, values=values, selected=selected,
        products=PRODUCTS, utility_connections=UTILITY_CONNECTIONS,
        mounting_types=MOUNTING_TYPES, service_types=SERVICE_TYPES,
        utilities=UTILITIES, counties=COUNTIES,
        existing_jobs=jobs_on_books, editing_job_id=editing_job_id,
    )


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id):
    db = get_db()
    job = fetch_job(job_id)
    client = db.execute(
        "SELECT * FROM clients WHERE id = ?", (job["client_id"],)
    ).fetchone()
    if request.method == "POST":
        values, selected, errors = read_job_form()
        if errors:
            flash(" ".join(errors), "error")
            return render_job_form(client, values, selected,
                                   editing_job_id=job_id), 400
        # Keep the outgoing state for recordkeeping before overwriting.
        snapshot = {f: job[f] for f in JOB_FIELDS}
        version = db.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM job_versions"
            " WHERE job_id = ?", (job_id,)).fetchone()[0]
        db.execute(
            "INSERT INTO job_versions (job_id, version, data) VALUES (?, ?, ?)",
            (job_id, version, json.dumps(snapshot)),
        )
        db.execute(
            f"UPDATE jobs SET {', '.join(f + ' = ?' for f in JOB_FIELDS)}"
            " WHERE id = ?",
            [values[f] for f in JOB_FIELDS] + [job_id],
        )
        db.commit()
        flash(f"Job updated — the previous state was kept as version {version}.")
        return redirect(url_for("job_detail", job_id=job_id))
    values = {f: job[f] for f in JOB_FIELDS}
    values["utility_connection"] = next(
        (job[f] for f in GRID_CONNECTION_FIELDS.values() if job[f]), "")
    selected = [p.strip() for p in job["products"].split(",") if p.strip()]
    return render_job_form(client, values, selected, editing_job_id=job_id)


@app.route("/jobs/<int:job_id>/versions/<int:version>")
def job_version(job_id, version):
    job = fetch_job(job_id)
    row = get_db().execute(
        "SELECT * FROM job_versions WHERE job_id = ? AND version = ?",
        (job_id, version),
    ).fetchone()
    if row is None:
        abort(404)
    data = json.loads(row["data"])
    rules = get_db().execute("SELECT * FROM resource_rules").fetchall()
    groups = group_rules(match_rules(data, rules))
    return render_template(
        "job_version.html", job=job, version=row, data=data,
        groups=groups, field_labels=JOB_FIELD_LABELS, job_fields=JOB_FIELDS,
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
    db = get_db()
    rules = db.execute("SELECT * FROM resource_rules").fetchall()
    groups = group_rules(match_rules(job, rules))
    versions = db.execute(
        "SELECT version, saved_at FROM job_versions WHERE job_id = ?"
        " ORDER BY version DESC", (job_id,)
    ).fetchall()
    materials = db.execute(
        "SELECT * FROM job_materials WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    files = db.execute(
        "SELECT * FROM job_files WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    filed_labels = {f["rule_label"] for f in files if f["rule_label"]}
    # Filing coverage per category: how many requirements have a document.
    coverage = {
        heading: sum(1 for r in items if r["label"] in filed_labels)
        for heading, items in groups
    }
    # Filing dropdown, sectioned: generic types first, then the job's
    # requirements grouped by their category headings.
    requirement_groups = [
        (heading, sorted({r["label"] for r in items}))
        for heading, items in groups
    ]

    # Piece 9: Loads & Sizing tab.
    rooms = db.execute(
        "SELECT * FROM job_load_rooms WHERE job_id = ? ORDER BY sort_order, id",
        (job_id,),
    ).fetchall()
    load_items = db.execute(
        "SELECT * FROM job_load_items WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    items_by_room = {}
    for it in load_items:
        items_by_room.setdefault(it["room_id"], []).append(it)
    sizing = fetch_job_sizing(db, job_id)
    bom = db.execute(
        "SELECT * FROM job_bom WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    appliances = db.execute(
        "SELECT * FROM appliance_catalog ORDER BY category, name"
    ).fetchall()
    components = db.execute(
        "SELECT * FROM component_catalog ORDER BY category, name"
    ).fetchall()
    appliances_by_category = {}
    for a in appliances:
        appliances_by_category.setdefault(a["category"] or "Other", []).append(a)
    components_by_category = {}
    for c in components:
        components_by_category.setdefault(c["category"] or "Other", []).append(c)

    daily_kwh, peak_w = compute_load_totals(rooms, load_items)
    array_kw, panel_count = compute_array(
        daily_kwh, sizing["sun_hours"], sizing["derate_pct"],
        sizing["solar_fraction_pct"], sizing["panel_watts"],
    )
    battery_kwh_needed = compute_battery_kwh(
        sizing["backup_daily_kwh"], sizing["autonomy_days"], sizing["dod_pct"],
        sizing["round_trip_eff_pct"], sizing["inverter_eff_pct"],
    )
    selected_battery = None
    battery_units_needed = None
    if sizing["selected_battery_id"]:
        selected_battery = db.execute(
            "SELECT * FROM component_catalog WHERE id = ?",
            (sizing["selected_battery_id"],),
        ).fetchone()
        if selected_battery and selected_battery["capacity_kwh_nameplate"]:
            battery_units_needed = math.ceil(
                battery_kwh_needed / selected_battery["capacity_kwh_nameplate"]
            )
    selected_pv_module = None
    voc_corrected = max_modules = None
    if sizing["selected_pv_module_id"]:
        selected_pv_module = db.execute(
            "SELECT * FROM component_catalog WHERE id = ?",
            (sizing["selected_pv_module_id"],),
        ).fetchone()
        if selected_pv_module:
            voc_corrected, max_modules = compute_voc(
                selected_pv_module["voc"], selected_pv_module["temp_coef_voc"],
                sizing["record_low_temp_f"], sizing["max_input_v"],
            )
    bom_total = sum((b["qty"] or 0) * (b["unit_cost"] or 0) for b in bom)

    # Piece 10: tasks for this job, plus the crew list for the assignee
    # picker. Assignee name comes along via a LEFT JOIN so unassigned tasks
    # (employee_id NULL) still show.
    tasks = db.execute(
        "SELECT t.*, e.name AS assignee_name FROM job_tasks t"
        " LEFT JOIN employees e ON e.id = t.employee_id"
        " WHERE t.job_id = ? ORDER BY t.sort_order, t.id", (job_id,)
    ).fetchall()
    employees = db.execute("SELECT id, name FROM employees ORDER BY name").fetchall()

    return render_template(
        "job_detail.html", job=job, groups=groups, versions=versions,
        materials=materials, files=files, filed_labels=filed_labels,
        coverage=coverage, requirement_groups=requirement_groups,
        material_statuses=MATERIAL_STATUSES, license_staffing=license_staffing(),
        tasks=tasks, employees=employees, task_statuses=TASK_STATUSES,
        job_statuses=JOB_STATUSES, job_status_class=JOB_STATUS_CLASS,
        today=datetime.now().strftime("%Y-%m-%d"),
        rooms=rooms, items_by_room=items_by_room, sizing=sizing, bom=bom,
        bom_total=bom_total, appliances_by_category=appliances_by_category,
        components_by_category=components_by_category,
        component_categories=COMPONENT_CATEGORIES,
        load_usage_types=LOAD_USAGE_TYPES, load_eras=LOAD_ERAS,
        daily_kwh=daily_kwh, peak_w=peak_w, array_kw=array_kw,
        panel_count=panel_count, battery_kwh_needed=battery_kwh_needed,
        selected_battery=selected_battery, battery_units_needed=battery_units_needed,
        selected_pv_module=selected_pv_module, voc_corrected=voc_corrected,
        max_modules=max_modules,
    )


def _float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ------------------------------------------------------------ loads & sizing
@app.route("/jobs/<int:job_id>/loads/rooms/add", methods=["POST"])
def add_load_room(job_id):
    fetch_job(job_id)
    name = request.form.get("name", "").strip()
    room_type = request.form.get("room_type", "standard")
    if room_type not in ROOM_TYPES:
        room_type = "standard"
    if not name:
        flash("Room name is required.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))
    db = get_db()
    next_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM job_load_rooms WHERE job_id = ?",
        (job_id,),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO job_load_rooms (job_id, name, room_type, sort_order)"
        " VALUES (?, ?, ?, ?)",
        (job_id, name, room_type, next_order),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/rooms/<int:room_id>/toggle", methods=["POST"])
def toggle_load_room(job_id, room_id):
    db = get_db()
    db.execute(
        "UPDATE job_load_rooms SET enabled = 1 - enabled WHERE id = ? AND job_id = ?",
        (room_id, job_id),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/rooms/<int:room_id>/delete", methods=["POST"])
def delete_load_room(job_id, room_id):
    db = get_db()
    db.execute("DELETE FROM job_load_items WHERE room_id = ? AND job_id = ?",
               (room_id, job_id))
    db.execute("DELETE FROM job_load_rooms WHERE id = ? AND job_id = ?",
               (room_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/items/add", methods=["POST"])
def add_load_item(job_id):
    fetch_job(job_id)
    db = get_db()
    room_id = request.form.get("room_id", type=int)
    room = db.execute(
        "SELECT * FROM job_load_rooms WHERE id = ? AND job_id = ?", (room_id, job_id)
    ).fetchone()
    if not room:
        flash("Pick a room before adding an appliance.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))

    catalog_id = request.form.get("catalog_id", type=int)
    if catalog_id:
        appliance = db.execute(
            "SELECT * FROM appliance_catalog WHERE id = ?", (catalog_id,)
        ).fetchone()
        if not appliance:
            flash("Appliance not found in the catalog.", "error")
            return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))
        name = appliance["name"]
        watts = appliance["avg_w"]
        hrs = appliance["hrs_per_day"]
        usage_type = appliance["usage_type"]
    else:
        name = request.form.get("custom_name", "").strip()
        watts = _float(request.form.get("custom_watts"))
        hrs = _float(request.form.get("custom_hrs"))
        usage_type = request.form.get("custom_usage_type", "").strip()
        if not name:
            flash("Give the custom appliance a name.", "error")
            return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))

    qty = _float(request.form.get("qty"), 1) or 1
    # Allow overriding hrs/day from the form even for a catalog pick.
    hrs_override = request.form.get("hrs")
    if hrs_override not in (None, ""):
        hrs = _float(hrs_override, hrs)

    db.execute(
        "INSERT INTO job_load_items"
        " (job_id, room_id, appliance, watts, qty, hrs, usage_type)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, room_id, name, watts, qty, hrs, usage_type),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/items/<int:item_id>/delete", methods=["POST"])
def delete_load_item(job_id, item_id):
    db = get_db()
    db.execute("DELETE FROM job_load_items WHERE id = ? AND job_id = ?",
               (item_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/bom/add", methods=["POST"])
def add_bom_item(job_id):
    fetch_job(job_id)
    db = get_db()
    component_id = request.form.get("component_id", type=int)
    qty = _float(request.form.get("qty"), 1) or 1
    notes = request.form.get("notes", "").strip()
    if component_id:
        comp = db.execute(
            "SELECT * FROM component_catalog WHERE id = ?", (component_id,)
        ).fetchone()
        if not comp:
            flash("Component not found in the catalog.", "error")
            return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))
        # Adding the same component again increments quantity instead of
        # creating a duplicate row.
        existing = db.execute(
            "SELECT * FROM job_bom WHERE job_id = ? AND component_id = ?",
            (job_id, component_id),
        ).fetchone()
        if existing:
            db.execute("UPDATE job_bom SET qty = qty + ? WHERE id = ?",
                       (qty, existing["id"]))
        else:
            db.execute(
                "INSERT INTO job_bom"
                " (job_id, component_id, component_name, category, qty,"
                "  unit_cost, notes)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, component_id, comp["name"], comp["category"], qty,
                 comp["cost"], notes),
            )
    else:
        name = request.form.get("custom_name", "").strip()
        category = request.form.get("custom_category", "").strip()
        cost = request.form.get("custom_cost")
        if not name:
            flash("Give the custom component a name.", "error")
            return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))
        db.execute(
            "INSERT INTO job_bom"
            " (job_id, component_id, component_name, category, qty,"
            "  unit_cost, notes)"
            " VALUES (?, NULL, ?, ?, ?, ?, ?)",
            (job_id, name, category, qty, _float(cost, None) if cost else None, notes),
        )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/bom/<int:bom_id>/delete", methods=["POST"])
def delete_bom_item(job_id, bom_id):
    db = get_db()
    db.execute("DELETE FROM job_bom WHERE id = ? AND job_id = ?", (bom_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/sizing", methods=["POST"])
def update_sizing(job_id):
    fetch_job(job_id)
    db = get_db()
    fetch_job_sizing(db, job_id)  # ensure the row exists

    ui_mode = request.form.get("ui_mode", "designer")
    if ui_mode not in UI_MODES:
        ui_mode = "designer"
    system_type = request.form.get("system_type", "custom")
    if system_type not in ("offgrid", "gridtie", "custom"):
        system_type = "custom"

    derate_pct = _float(request.form.get("derate_pct"), 75)
    autonomy_days = _float(request.form.get("autonomy_days"), 2)
    # A preset system type overrides derate/autonomy with its fixed values,
    # mirroring the standalone tool's auto-fill-then-revert-on-edit behavior.
    if system_type in SYSTEM_TYPE_PRESETS:
        preset = SYSTEM_TYPE_PRESETS[system_type]
        derate_pct = preset["derate_pct"]
        autonomy_days = preset["autonomy_days"]

    selected_battery_id = request.form.get("selected_battery_id", type=int) or None
    selected_pv_module_id = request.form.get("selected_pv_module_id", type=int) or None

    db.execute(
        "UPDATE job_sizing SET ui_mode = ?, system_type = ?, sun_hours = ?,"
        " derate_pct = ?, autonomy_days = ?, solar_fraction_pct = ?,"
        " panel_watts = ?, dod_pct = ?, round_trip_eff_pct = ?,"
        " inverter_eff_pct = ?, max_input_v = ?, record_low_temp_f = ?,"
        " backup_daily_kwh = ?, selected_battery_id = ?, selected_pv_module_id = ?,"
        " updated_at = datetime('now')"
        " WHERE job_id = ?",
        (
            ui_mode, system_type,
            _float(request.form.get("sun_hours"), 5.5),
            derate_pct, autonomy_days,
            _float(request.form.get("solar_fraction_pct"), 100),
            _float(request.form.get("panel_watts"), 400),
            _float(request.form.get("dod_pct"), 80),
            _float(request.form.get("round_trip_eff_pct"), 92),
            _float(request.form.get("inverter_eff_pct"), 96),
            _float(request.form.get("max_input_v"), 600),
            _float(request.form.get("record_low_temp_f"), 5),
            _float(request.form.get("backup_daily_kwh"), 0),
            selected_battery_id, selected_pv_module_id, job_id,
        ),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


@app.route("/jobs/<int:job_id>/loads/mode", methods=["POST"])
def set_ui_mode(job_id):
    fetch_job(job_id)
    db = get_db()
    fetch_job_sizing(db, job_id)  # ensure the row exists
    ui_mode = request.form.get("ui_mode", "designer")
    if ui_mode not in UI_MODES:
        ui_mode = "designer"
    db.execute("UPDATE job_sizing SET ui_mode = ? WHERE job_id = ?",
               (ui_mode, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="loads"))


# ------------------------------------------------------------------ catalog
@app.route("/catalog")
def catalog_page():
    db = get_db()
    appliances = db.execute(
        "SELECT * FROM appliance_catalog ORDER BY category, name"
    ).fetchall()
    components = db.execute(
        "SELECT * FROM component_catalog ORDER BY category, name"
    ).fetchall()
    appliance_categories = sorted({a["category"] for a in appliances if a["category"]})
    return render_template(
        "catalog.html", appliances=appliances, components=components,
        appliance_categories=appliance_categories,
        component_categories=COMPONENT_CATEGORIES, load_eras=LOAD_ERAS,
        load_usage_types=LOAD_USAGE_TYPES,
    )


@app.route("/catalog/appliances/add", methods=["POST"])
@admin_required
def add_appliance_catalog():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Appliance name is required.", "error")
        return redirect(url_for("catalog_page"))
    db = get_db()
    db.execute(
        "INSERT INTO appliance_catalog"
        " (name, category, era, low_w, high_w, avg_w, hrs_per_day, usage_type, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name, request.form.get("category", "").strip(),
            request.form.get("era", "").strip(),
            _float(request.form.get("low_w"), 0),
            _float(request.form.get("high_w"), 0),
            _float(request.form.get("avg_w"), 0),
            _float(request.form.get("hrs_per_day"), 0),
            request.form.get("usage_type", "").strip(),
            request.form.get("notes", "").strip(),
        ),
    )
    db.commit()
    flash(f"Added {name} to the appliance catalog.")
    return redirect(url_for("catalog_page"))


@app.route("/catalog/appliances/<int:appliance_id>/delete", methods=["POST"])
@admin_required
def delete_appliance_catalog(appliance_id):
    db = get_db()
    db.execute("DELETE FROM appliance_catalog WHERE id = ?", (appliance_id,))
    db.commit()
    return redirect(url_for("catalog_page"))


@app.route("/catalog/components/add", methods=["POST"])
@admin_required
def add_component_catalog():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Component name is required.", "error")
        return redirect(url_for("catalog_page"))

    def opt_float(field):
        val = request.form.get(field)
        return _float(val, None) if val not in (None, "") else None

    db = get_db()
    db.execute(
        "INSERT INTO component_catalog"
        " (name, category, manufacturer, model, specs, watts, voc, vmp,"
        "  temp_coef_voc, capacity_kwh_nameplate, dod, max_input_v,"
        "  continuous_w, inverter_eff, cost, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name, request.form.get("category", "").strip(),
            request.form.get("manufacturer", "").strip(),
            request.form.get("model", "").strip(),
            request.form.get("specs", "").strip(),
            opt_float("watts"), opt_float("voc"), opt_float("vmp"),
            opt_float("temp_coef_voc"), opt_float("capacity_kwh_nameplate"),
            opt_float("dod"), opt_float("max_input_v"), opt_float("continuous_w"),
            opt_float("inverter_eff"), opt_float("cost"),
            request.form.get("notes", "").strip(),
        ),
    )
    db.commit()
    flash(f"Added {name} to the component catalog.")
    return redirect(url_for("catalog_page"))


@app.route("/catalog/components/<int:component_id>/delete", methods=["POST"])
@admin_required
def delete_component_catalog(component_id):
    db = get_db()
    # job_bom.component_id and job_sizing.selected_battery_id /
    # selected_pv_module_id all reference this table, and foreign_keys is ON
    # (get_db()) — deleting a component still in use would otherwise fail
    # with an IntegrityError. job_bom already snapshots name/category/cost
    # at add-time, so clearing the link there just detaches history from a
    # since-removed catalog entry rather than losing any data.
    db.execute("UPDATE job_bom SET component_id = NULL WHERE component_id = ?",
               (component_id,))
    db.execute(
        "UPDATE job_sizing SET selected_battery_id = NULL"
        " WHERE selected_battery_id = ?", (component_id,))
    db.execute(
        "UPDATE job_sizing SET selected_pv_module_id = NULL"
        " WHERE selected_pv_module_id = ?", (component_id,))
    db.execute("DELETE FROM component_catalog WHERE id = ?", (component_id,))
    db.commit()
    return redirect(url_for("catalog_page"))


@app.route("/jobs/<int:job_id>/status", methods=["POST"])
def set_job_status(job_id):
    fetch_job(job_id)
    status = request.form.get("status", "")
    if status in JOB_STATUSES:
        db = get_db()
        db.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        db.commit()
    return redirect(url_for("job_detail", job_id=job_id))


# ---------------------------------------------------------------- materials
@app.route("/jobs/<int:job_id>/materials/add", methods=["POST"])
def add_material(job_id):
    fetch_job(job_id)
    item = request.form.get("item", "").strip()
    if not item:
        flash("Material item name is required.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))
    db = get_db()
    db.execute(
        "INSERT INTO job_materials (job_id, item, quantity, unit, supplier, notes)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, item,
         request.form.get("quantity", "").strip(),
         request.form.get("unit", "").strip(),
         request.form.get("supplier", "").strip(),
         request.form.get("notes", "").strip()),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))


@app.route("/jobs/<int:job_id>/materials/<int:material_id>/status", methods=["POST"])
def update_material_status(job_id, material_id):
    status = request.form.get("status", "")
    if status in MATERIAL_STATUSES:
        db = get_db()
        db.execute(
            "UPDATE job_materials SET status = ? WHERE id = ? AND job_id = ?",
            (status, material_id, job_id),
        )
        db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))


@app.route("/jobs/<int:job_id>/materials/<int:material_id>/edit", methods=["POST"])
def edit_material(job_id, material_id):
    item = request.form.get("item", "").strip()
    if not item:
        flash("Material item name is required.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))
    db = get_db()
    db.execute(
        "UPDATE job_materials SET item = ?, quantity = ?, unit = ?, supplier = ?,"
        " notes = ? WHERE id = ? AND job_id = ?",
        (item, request.form.get("quantity", "").strip(),
         request.form.get("unit", "").strip(),
         request.form.get("supplier", "").strip(),
         request.form.get("notes", "").strip(), material_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))


@app.route("/jobs/<int:job_id>/materials/<int:material_id>/delete", methods=["POST"])
def delete_material(job_id, material_id):
    db = get_db()
    db.execute("DELETE FROM job_materials WHERE id = ? AND job_id = ?",
               (material_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))


# -------------------------------------------------------------------- tasks
def _task_assignee(job_id):
    """Read and validate an employee_id from the form: blank means
    unassigned, a real employee id is kept, anything else is rejected."""
    raw = request.form.get("employee_id", "").strip()
    if not raw:
        return None
    emp = get_db().execute(
        "SELECT id FROM employees WHERE id = ?", (raw,)).fetchone()
    return emp["id"] if emp else None


@app.route("/jobs/<int:job_id>/tasks/add", methods=["POST"])
def add_task(job_id):
    fetch_job(job_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash("A task needs a title.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))
    status = request.form.get("status", "To do")
    if status not in TASK_STATUSES:
        status = "To do"
    db = get_db()
    next_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM job_tasks WHERE job_id = ?",
        (job_id,)).fetchone()[0]
    db.execute(
        "INSERT INTO job_tasks"
        " (job_id, employee_id, title, status, due_date, notes, sort_order,"
        "  completed_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
        (job_id, _task_assignee(job_id), title, status,
         request.form.get("due_date", "").strip(),
         request.form.get("notes", "").strip(), next_order,
         datetime.now().strftime("%Y-%m-%d") if status == "Done" else ""),
    )
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


def _auto_assignee(lane, employees):
    """The employee who should own a step in this lane — but only when the
    match is unambiguous (exactly one employee holds a role mapped to the
    lane). Zero or several matches → left unassigned for a human to pick."""
    wanted = {r.lower() for r in LANE_TO_ROLES.get(lane, [])}
    if not wanted:
        return None
    matches = [e for e in employees
               if any(r.strip().lower() in wanted
                      for r in (e["roles"] or "").split(","))]
    return matches[0]["id"] if len(matches) == 1 else None


@app.route("/jobs/<int:job_id>/tasks/generate", methods=["POST"])
def generate_tasks(job_id):
    """Pre-load a job's task list from its process: run the same per-job
    BPMN the Process chart uses, then turn each workflow step (skipping
    start/end events and gateways) into a To-do task, in order. Each step
    auto-assigns to the employee whose role matches its lane (when
    unambiguous), and — if a target install date is given — gets a due date
    spaced around the Site Installation step. Skips steps already on the
    list, so it's safe to re-run after the job's fields change."""
    job = fetch_job(job_id)
    db = get_db()
    rules = db.execute("SELECT * FROM resource_rules").fetchall()
    _xml, details = build_job_bpmn(job, match_rules(job, rules))
    employees = db.execute("SELECT id, roles FROM employees").fetchall()

    # Actionable workflow steps in order (no start/end events or gateways).
    task_steps = [
        s for s in sorted(details.values(), key=lambda d: d["order"])
        if not (s["kind"].endswith("Event") or s["kind"].endswith("Gateway"))
        and (s["name"] or "").strip()
    ]
    # Optional schedule anchored on Site Installation.
    base_date = None
    raw_install = request.form.get("install_date", "").strip()
    if raw_install:
        try:
            base_date = datetime.strptime(raw_install, "%Y-%m-%d").date()
        except ValueError:
            base_date = None
    install_idx = next((i for i, s in enumerate(task_steps)
                        if s["name"].strip().lower().startswith("site installation")),
                       None)

    existing = {r["title"].strip().lower() for r in db.execute(
        "SELECT title FROM job_tasks WHERE job_id = ?", (job_id,)).fetchall()}
    base = db.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM job_tasks WHERE job_id = ?",
        (job_id,)).fetchone()[0]
    added = assigned = scheduled = 0
    for pos, step in enumerate(task_steps):
        title = step["name"].strip()
        if title.lower() in existing:
            continue
        note = f"Process step · {step['lane']}" if step.get("lane") else "Process step"
        assignee = _auto_assignee(step["lane"], employees)
        due = ""
        if base_date is not None and install_idx is not None:
            offset = (pos - install_idx) * TASK_DUE_SPACING_DAYS
            due = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO job_tasks"
            " (job_id, employee_id, title, status, due_date, notes, sort_order,"
            "  updated_at)"
            " VALUES (?, ?, ?, 'To do', ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))",
            (job_id, assignee, title, due, note, base + added))
        existing.add(title.lower())
        added += 1
        if assignee:
            assigned += 1
        if due:
            scheduled += 1
    db.commit()
    if added:
        extra = []
        if assigned:
            extra.append(f"{assigned} auto-assigned by role")
        if scheduled:
            extra.append(f"due dates set around {raw_install}")
        detail = f" ({'; '.join(extra)})" if extra else ""
        flash(f"Added {added} task{'s' if added != 1 else ''} from the job's process{detail}.")
    else:
        flash("No new tasks — the process steps are already on the list.")
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/jobs/<int:job_id>/tasks/<int:task_id>/status", methods=["POST"])
def set_task_status(job_id, task_id):
    status = request.form.get("status", "")
    if status in TASK_STATUSES:
        db = get_db()
        # Stamp (or clear) the completion date as the task enters/leaves Done.
        completed = datetime.now().strftime("%Y-%m-%d") if status == "Done" else ""
        db.execute(
            "UPDATE job_tasks SET status = ?, completed_at = ?,"
            " updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ? AND job_id = ?",
            (status, completed, task_id, job_id))
        db.commit()
    # A dashboard passes ?next= so the status change returns there; only
    # same-site relative paths are honored.
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/jobs/<int:job_id>/tasks/<int:task_id>/assign", methods=["POST"])
def set_task_assignee(job_id, task_id):
    db = get_db()
    db.execute("UPDATE job_tasks SET employee_id = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"
               " WHERE id = ? AND job_id = ?",
               (_task_assignee(job_id), task_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/jobs/<int:job_id>/tasks/<int:task_id>/due", methods=["POST"])
def set_task_due(job_id, task_id):
    db = get_db()
    db.execute("UPDATE job_tasks SET due_date = ?, updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now')"
               " WHERE id = ? AND job_id = ?",
               (request.form.get("due_date", "").strip(), task_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/jobs/<int:job_id>/tasks/<int:task_id>/edit", methods=["POST"])
def edit_task(job_id, task_id):
    title = request.form.get("title", "").strip()
    if not title:
        flash("A task needs a title.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))
    db = get_db()
    db.execute("UPDATE job_tasks SET title = ?, notes = ?,"
               " updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ? AND job_id = ?",
               (title, request.form.get("notes", "").strip(), task_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/jobs/<int:job_id>/tasks/<int:task_id>/delete", methods=["POST"])
def delete_task(job_id, task_id):
    db = get_db()
    db.execute("DELETE FROM job_tasks WHERE id = ? AND job_id = ?",
               (task_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="tasks"))


@app.route("/tasks")
def tasks_dashboard():
    """Cross-job task board: every task in one place, filterable to one
    person (or the unassigned pile) and to open vs. all. The home for
    'what am I supposed to be doing' across every job."""
    db = get_db()
    employees = db.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
    who = request.args.get("employee", "")   # "" (all) / "unassigned" / an id
    show = request.args.get("show", "open")  # open / all
    sql = ("SELECT t.*, j.job_name, j.id AS job_id, c.name AS client_name,"
           " e.name AS assignee_name FROM job_tasks t"
           " JOIN jobs j ON j.id = t.job_id"
           " JOIN clients c ON c.id = j.client_id"
           " LEFT JOIN employees e ON e.id = t.employee_id WHERE 1 = 1")
    params = []
    if who == "unassigned":
        sql += " AND t.employee_id IS NULL"
    elif who.isdigit():
        sql += " AND t.employee_id = ?"
        params.append(int(who))
    if show == "open":
        sql += " AND t.status != 'Done'"
    # Open first, then soonest due (blank dues last), then by job.
    sql += (" ORDER BY (t.status = 'Done'), (t.due_date = ''), t.due_date,"
            " j.id, t.sort_order, t.id")
    tasks = db.execute(sql, params).fetchall()
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    today = datetime.now().strftime("%Y-%m-%d")
    overdue = sum(1 for t in tasks
                  if t["due_date"] and t["due_date"] < today and t["status"] != "Done")
    return render_template(
        "tasks.html", tasks=tasks, employees=employees, who=who, show=show,
        task_statuses=TASK_STATUSES, counts=counts, overdue=overdue, today=today)


# ------------------------------------------- Piece 14: Work Bag (offline sync)
def _my_tasks_rows(db, employee_id):
    return db.execute(
        "SELECT t.id, t.title, t.status, t.due_date, t.notes, t.updated_at,"
        " j.id AS job_id, j.job_name, c.name AS client_name"
        " FROM job_tasks t JOIN jobs j ON j.id = t.job_id"
        " JOIN clients c ON c.id = j.client_id"
        " WHERE t.employee_id = ?"
        " ORDER BY (t.status = 'Done'), (t.due_date = ''), t.due_date, t.id",
        (employee_id,)).fetchall()


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@app.route("/work-bag")
def work_bag():
    """The Work Bag: an offline-capable page holding the signed-in worker's
    field tasks. Task data and submission happen in the browser via the /api
    endpoints, so it keeps working through a dropped connection."""
    return render_template("work_bag.html", task_statuses=TASK_STATUSES,
                           today=datetime.now().strftime("%Y-%m-%d"))


@app.route("/api/my-tasks")
def api_my_tasks():
    """The worker's assigned tasks, their still-pending field edits, and a
    short submission history — as JSON for the Work Bag."""
    user = current_user()
    if user is None:
        return jsonify({"error": "not signed in"}), 401
    db = get_db()
    rows = _my_tasks_rows(db, user["id"])
    pend = db.execute(
        "SELECT i.task_id, i.new_status, i.new_notes"
        " FROM field_submission_items i"
        " JOIN field_submissions s ON s.id = i.submission_id"
        " WHERE s.employee_id = ? AND s.status = 'Pending'", (user["id"],)).fetchall()
    subs = db.execute(
        "SELECT id, work_date, reported_hours, approved_hours, status, submitted_at,"
        " reviewed_at FROM field_submissions WHERE employee_id = ?"
        " ORDER BY id DESC LIMIT 8", (user["id"],)).fetchall()
    return jsonify({
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "user": user["name"],
        "tasks": [dict(r) for r in rows],
        "pending_items": [dict(r) for r in pend],
        "submissions": [dict(r) for r in subs],
    })


@app.route("/api/work-bag/submit", methods=["POST"])
def api_work_bag_submit():
    """Save the worker's completed field work as a PENDING submission — a
    copy in the database that does NOT change the authoritative task data or
    count as hours until a manager approves it."""
    user = current_user()
    if user is None:
        return jsonify({"error": "not signed in"}), 401
    payload = request.get_json(silent=True) or {}
    db = get_db()
    # Keep only edits to the worker's own tasks; snapshot title for review.
    valid = []
    for ch in payload.get("changes", []) or []:
        row = db.execute(
            "SELECT * FROM job_tasks WHERE id = ? AND employee_id = ?",
            (ch.get("id"), user["id"])).fetchone()
        if row is None:
            continue
        status = ch.get("status", row["status"])
        if status not in TASK_STATUSES:
            status = row["status"]
        valid.append((row["id"], row["title"], status,
                      ch.get("notes", row["notes"]), ch.get("base_updated_at") or ""))
    reported_hours = _to_float(payload.get("reported_hours"))
    if not valid and reported_hours is None:
        return jsonify({"error": "nothing to submit"}), 400
    cur = db.execute(
        "INSERT INTO field_submissions (employee_id, work_date, reported_hours, note)"
        " VALUES (?, ?, ?, ?)",
        (user["id"], (payload.get("work_date") or "").strip(), reported_hours,
         (payload.get("note") or "").strip()))
    sub_id = cur.lastrowid
    for task_id, title, status, notes, base in valid:
        db.execute(
            "INSERT INTO field_submission_items"
            " (submission_id, task_id, task_title, new_status, new_notes, base_updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (sub_id, task_id, title, status, notes, base))
    db.commit()
    return jsonify({"submission_id": sub_id, "status": "Pending",
                    "items": len(valid)})


@app.route("/submissions")
@admin_required
def submissions_page():
    """Manager review of field-work submissions: confirm hours and approve
    (applies the task changes + logs hours) or reject."""
    db = get_db()
    show = request.args.get("show", "pending")
    where = "WHERE s.status = 'Pending'" if show == "pending" else ""
    subs = db.execute(
        "SELECT s.*, e.name AS emp_name FROM field_submissions s"
        " JOIN employees e ON e.id = s.employee_id"
        f" {where} ORDER BY (s.status='Pending') DESC, s.id DESC LIMIT 100"
    ).fetchall()
    items_by_sub = {}
    ids = [s["id"] for s in subs]
    if ids:
        q = ("SELECT * FROM field_submission_items WHERE submission_id IN (%s)"
             " ORDER BY id" % ",".join("?" * len(ids)))
        for it in db.execute(q, ids).fetchall():
            items_by_sub.setdefault(it["submission_id"], []).append(it)
    return render_template("submissions.html", subs=subs, items_by_sub=items_by_sub,
                           show=show)


@app.route("/submissions/<int:sub_id>/approve", methods=["POST"])
@admin_required
def approve_submission(sub_id):
    db = get_db()
    sub = db.execute(
        "SELECT * FROM field_submissions WHERE id = ? AND status = 'Pending'",
        (sub_id,)).fetchone()
    if sub is None:
        flash("Submission not found or already reviewed.", "error")
        return redirect(url_for("submissions_page"))
    approved_hours = _to_float(request.form.get("approved_hours"))
    if approved_hours is None:
        approved_hours = sub["reported_hours"]
    # Now — and only now — apply the field edits to the authoritative tasks.
    for it in db.execute(
            "SELECT * FROM field_submission_items WHERE submission_id = ?",
            (sub_id,)).fetchall():
        row = db.execute("SELECT * FROM job_tasks WHERE id = ?",
                         (it["task_id"],)).fetchone()
        if row is None:
            continue
        status = it["new_status"] if it["new_status"] in TASK_STATUSES else row["status"]
        completed = datetime.now().strftime("%Y-%m-%d") if status == "Done" else ""
        db.execute(
            "UPDATE job_tasks SET status = ?, notes = ?, completed_at = ?,"
            " updated_at = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = ?",
            (status, it["new_notes"], completed, it["task_id"]))
    who = current_user()
    db.execute(
        "UPDATE field_submissions SET status = 'Approved', approved_hours = ?,"
        " reviewed_by = ?, reviewed_at = datetime('now') WHERE id = ?",
        (approved_hours, who["name"] if who else "", sub_id))
    db.commit()
    flash("Submission approved — task changes applied and hours logged.")
    return redirect(url_for("submissions_page"))


@app.route("/submissions/<int:sub_id>/reject", methods=["POST"])
@admin_required
def reject_submission(sub_id):
    who = current_user()
    db = get_db()
    db.execute(
        "UPDATE field_submissions SET status = 'Rejected', reviewed_by = ?,"
        " reviewed_at = datetime('now') WHERE id = ? AND status = 'Pending'",
        (who["name"] if who else "", sub_id))
    db.commit()
    flash("Submission rejected — no changes were applied.")
    return redirect(url_for("submissions_page"))


# -------------------------------------------------------------------- files
def job_upload_dir(job_id):
    directory = UPLOADS_DIR / f"job_{job_id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@app.route("/jobs/<int:job_id>/files/upload", methods=["POST"])
def upload_file(job_id):
    fetch_job(job_id)
    upload = request.files.get("document")
    if upload is None or not upload.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="documents"))
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash(f"File type .{extension} is not allowed.", "error")
        return redirect(url_for("job_detail", job_id=job_id, _anchor="documents"))
    original = upload.filename
    stored = f"{uuid.uuid4().hex[:8]}_{secure_filename(original)}"
    upload.save(job_upload_dir(job_id) / stored)
    db = get_db()
    db.execute(
        "INSERT INTO job_files (job_id, rule_label, stored_name, original_name)"
        " VALUES (?, ?, ?, ?)",
        (job_id, request.form.get("rule_label", "").strip(), stored, original),
    )
    db.commit()
    flash(f"Uploaded: {original}")
    return redirect(url_for("job_detail", job_id=job_id, _anchor="documents"))


@app.route("/jobs/<int:job_id>/files/<int:file_id>/download")
def download_file(job_id, file_id):
    record = get_db().execute(
        "SELECT * FROM job_files WHERE id = ? AND job_id = ?",
        (file_id, job_id),
    ).fetchone()
    if record is None:
        abort(404)
    return send_from_directory(
        job_upload_dir(job_id), record["stored_name"], as_attachment=True,
        download_name=record["original_name"],
    )


@app.route("/jobs/<int:job_id>/files/<int:file_id>/delete", methods=["POST"])
def delete_file(job_id, file_id):
    db = get_db()
    record = db.execute(
        "SELECT * FROM job_files WHERE id = ? AND job_id = ?",
        (file_id, job_id),
    ).fetchone()
    if record:
        (job_upload_dir(job_id) / record["stored_name"]).unlink(missing_ok=True)
        db.execute("DELETE FROM job_files WHERE id = ?", (record["id"],))
        db.commit()
        flash(f"Deleted: {record['original_name']}")
    return redirect(url_for("job_detail", job_id=job_id, _anchor="documents"))


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
        lines += ["", f"{heading.upper()} ({len(items)} ITEM{'S' if len(items) != 1 else ''})", "-" * 64]
        for rule in items:
            entry = f"[ ] {rule['label']}"
            if rule["notes"]:
                entry += f"  ({rule['notes']})"
            lines.append(entry)
            if rule["url"]:
                source = rule["link_text"] or ""
                lines.append(f"      {source + ': ' if source else 'link:  '}{rule['url']}")
            if rule["phone"]:
                lines.append(f"      phone: {rule['phone']}")
    if not groups:
        lines += ["", "No license/permit/compliance requirements matched."]
    materials = get_db().execute(
        "SELECT * FROM job_materials WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    if materials:
        lines += ["", f"MATERIAL LIST ({len(materials)} ITEMS)", "-" * 64]
        for m in materials:
            entry = f"[{m['status']:>9}] {m['item']}"
            if m["quantity"]:
                entry += f" — {m['quantity']} {m['unit']}".rstrip()
            if m["supplier"]:
                entry += f" ({m['supplier']})"
            lines.append(entry)
    files = get_db().execute(
        "SELECT * FROM job_files WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    if files:
        lines += ["", f"DOCUMENTS ON FILE ({len(files)})", "-" * 64]
        for f in files:
            entry = f"- {f['original_name']} ({f['uploaded_at'][:10]})"
            if f["rule_label"]:
                entry += f" -> {f['rule_label']}"
            lines.append(entry)
    lines.append("")
    return Response(
        "\n".join(lines),
        mimetype="text/plain",
        headers={"Content-Disposition":
                 f"attachment; filename=job_{job_id}_report.txt"},
    )


@app.route("/jobs/<int:job_id>/bpmn")
def job_bpmn(job_id):
    """Download this job's process as a BPMN 2.0 file: the master
    pipeline instantiated with the job's resolved permits and variables."""
    job = fetch_job(job_id)
    rules = get_db().execute("SELECT * FROM resource_rules").fetchall()
    materials, files, materials_note, docs_note = job_progress_extras(job_id)
    xml, _details = build_job_bpmn(job, match_rules(job, rules),
                                   materials_note, docs_note)
    return Response(
        xml, mimetype="application/xml",
        headers={"Content-Disposition":
                 f"attachment; filename=job_{job_id}_process.bpmn"},
    )


def job_progress_extras(job_id):
    """Materials and documents for a job, plus one-line summaries used
    as annotations in the exported BPMN."""
    db = get_db()
    materials = db.execute(
        "SELECT * FROM job_materials WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    files = db.execute(
        "SELECT * FROM job_files WHERE job_id = ? ORDER BY id", (job_id,)
    ).fetchall()
    materials_note = ""
    if materials:
        counts = {}
        for m in materials:
            counts[m["status"]] = counts.get(m["status"], 0) + 1
        breakdown = ", ".join(f"{n} {s}" for s, n in counts.items())
        materials_note = f"Materials: {len(materials)} items — {breakdown}"
    docs_note = ""
    if files:
        covered = len({f["rule_label"] for f in files if f["rule_label"]})
        docs_note = (f"Documents on file: {len(files)}"
                     + (f" ({covered} requirements covered)" if covered else ""))
    return materials, files, materials_note, docs_note


@app.route("/jobs/<int:job_id>/bpmn/view")
def job_bpmn_view(job_id):
    job = fetch_job(job_id)
    rules = get_db().execute("SELECT * FROM resource_rules").fetchall()
    materials, files, materials_note, docs_note = job_progress_extras(job_id)
    _xml, details = build_job_bpmn(job, match_rules(job, rules),
                                   materials_note, docs_note)
    steps = sorted(details.values(), key=lambda d: d["order"])
    files_by_label = {}
    for f in files:
        if f["rule_label"]:
            files_by_label.setdefault(f["rule_label"], []).append(f)
    material_counts = {}
    for m in materials:
        material_counts[m["status"]] = material_counts.get(m["status"], 0) + 1
    return render_template(
        "bpmn_view.html", job=job, steps=steps,
        files_by_label=files_by_label, materials=materials,
        material_counts=material_counts,
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
@admin_required
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
        "  field_name2, field_value2, match_type2, link_text)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (field_name, field_value,
         "contains" if field_name == "products" else "equals",
         request.form.get("category", "Compliance"),
         label,
         request.form.get("url", "").strip(),
         request.form.get("phone", "").strip(),
         request.form.get("notes", "").strip(),
         field_name2, field_value2,
         "contains" if field_name2 == "products" else "equals",
         request.form.get("link_text", "").strip()),
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
@admin_required
def delete_rule(rule_id):
    db = get_db()
    db.execute("DELETE FROM resource_rules WHERE id = ?", (rule_id,))
    db.commit()
    flash("Rule deleted.")
    return redirect(url_for("rules_page",
                            from_job=request.form.get("from_job") or None))


# ---------------------------------------------------------------- employees
def read_employee_form():
    """Validate and normalize a submitted employee form (create or edit).
    Roles come in as checkboxes plus an optional free-typed 'other' field;
    both are folded into one comma-separated list."""
    values = {f: request.form.get(f, "").strip() for f in EMPLOYEE_FIELDS}
    selected = request.form.getlist("roles")
    roles = [r for r in EMPLOYEE_ROLES if r in selected]
    for extra in request.form.get("roles_other", "").split(","):
        extra = extra.strip()
        if extra and extra not in roles:
            roles.append(extra)
    values["roles"] = ", ".join(roles)
    errors = []
    if not values["name"]:
        errors.append("Employee name is required.")
    return values, errors


def render_employee_form(values, employee_id=None, username="", access_level=""):
    """Render the shared new/edit form, splitting stored roles back into
    the known checkbox roles and any free-typed extras."""
    stored = [r.strip() for r in (values.get("roles") or "").split(",") if r.strip()]
    selected = [r for r in stored if r in EMPLOYEE_ROLES]
    roles_other = ", ".join(r for r in stored if r not in EMPLOYEE_ROLES)
    return render_template(
        "employee_form.html", values=values, roles=EMPLOYEE_ROLES,
        selected=selected, roles_other=roles_other, employee_id=employee_id,
        username=username, access_level=access_level, access_levels=ACCESS_LEVELS,
    )


@app.route("/employees")
def employees_page():
    db = get_db()
    employees = db.execute("SELECT * FROM employees ORDER BY name").fetchall()
    # Per-employee credential tally, with expiry warnings, for the list.
    summary = {}
    for c in db.execute(
            "SELECT employee_id, expires FROM employee_credentials").fetchall():
        s = summary.setdefault(c["employee_id"],
                               {"count": 0, "expired": 0, "soon": 0})
        s["count"] += 1
        state, _ = credential_status(c["expires"])
        if state == "expired":
            s["expired"] += 1
        elif state == "soon":
            s["soon"] += 1
    return render_template("employees.html", employees=employees, summary=summary)


@app.route("/accounts")
@admin_required
def accounts_page():
    """Admin roster of who can sign in and at what level, the employees
    who don't have a login yet, and any pending password-change requests."""
    db = get_db()
    employees = db.execute(
        "SELECT id, name, username, access_level, COALESCE(password_hash,'') AS pw"
        " FROM employees ORDER BY name").fetchall()
    with_login = [e for e in employees if (e["username"] or "")]
    without_login = [e for e in employees if not (e["username"] or "")]
    admin_count = sum(1 for e in with_login if e["access_level"] == "Admin")
    pending = db.execute(
        "SELECT pr.*, e.name AS emp_name, e.username FROM password_requests pr"
        " JOIN employees e ON e.id = pr.employee_id"
        " WHERE pr.status = 'Pending' ORDER BY pr.requested_at").fetchall()
    return render_template("accounts.html", with_login=with_login,
                           without_login=without_login, admin_count=admin_count,
                           pending=pending)


@app.route("/accounts/password-requests/<int:req_id>/approve", methods=["POST"])
@admin_required
def approve_password_change(req_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM password_requests WHERE id = ? AND status = 'Pending'",
        (req_id,)).fetchone()
    if req:
        db.execute("UPDATE employees SET password_hash = ? WHERE id = ?",
                   (req["new_hash"], req["employee_id"]))
        who = current_user()
        db.execute(
            "UPDATE password_requests SET status = 'Approved',"
            " resolved_at = datetime('now'), resolved_by = ? WHERE id = ?",
            (who["name"] if who else "", req_id))
        db.commit()
        flash("Password change approved and applied.")
    return redirect(url_for("accounts_page"))


@app.route("/accounts/password-requests/<int:req_id>/reject", methods=["POST"])
@admin_required
def reject_password_change(req_id):
    db = get_db()
    who = current_user()
    db.execute(
        "UPDATE password_requests SET status = 'Rejected',"
        " resolved_at = datetime('now'), resolved_by = ?"
        " WHERE id = ? AND status = 'Pending'",
        (who["name"] if who else "", req_id))
    db.commit()
    flash("Password change rejected.")
    return redirect(url_for("accounts_page"))


def _apply_employee_auth(db, employee_id):
    """Set or clear this employee's login from the form's Login & access
    fields. A blank/None level or blank username removes the login; the
    password hash is rewritten only when a new password is supplied, so
    editing other fields never disturbs an existing password. Guards against
    leaving accounts configured with no admin (which would lock everyone out
    of admin functions)."""
    level = request.form.get("access_level", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    setting_login = level in ACCESS_LEVELS and bool(username)

    if setting_login:
        clash = db.execute(
            "SELECT id FROM employees WHERE username = ? AND id != ?",
            (username, employee_id)).fetchone()
        if clash:
            flash(f"Username “{username}” is already taken — login unchanged.", "error")
            return

    existing_hash = db.execute(
        "SELECT COALESCE(password_hash,'') FROM employees WHERE id = ?",
        (employee_id,)).fetchone()[0]
    this_usable = setting_login and (bool(password) or bool(existing_hash))
    this_admin = this_usable and level == "Admin"
    other_accounts = db.execute(
        "SELECT COUNT(*) FROM employees WHERE id != ?"
        " AND COALESCE(username,'') != '' AND COALESCE(password_hash,'') != ''",
        (employee_id,)).fetchone()[0]
    other_admins = db.execute(
        "SELECT COUNT(*) FROM employees WHERE id != ? AND access_level = 'Admin'"
        " AND COALESCE(username,'') != '' AND COALESCE(password_hash,'') != ''",
        (employee_id,)).fetchone()[0]
    total_accounts = other_accounts + (1 if this_usable else 0)
    total_admins = other_admins + (1 if this_admin else 0)
    if total_accounts > 0 and total_admins == 0:
        flash("Keep at least one admin account — or remove every login to go"
              " back to open access. Login unchanged.", "error")
        return

    if setting_login:
        db.execute("UPDATE employees SET username = ?, access_level = ? WHERE id = ?",
                   (username, level, employee_id))
        if password:
            db.execute("UPDATE employees SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(password), employee_id))
        elif not existing_hash:
            flash("Login saved — set a password to activate it.", "error")
    else:
        db.execute(
            "UPDATE employees SET username = '', password_hash = '', access_level = ''"
            " WHERE id = ?", (employee_id,))


@app.route("/employees/new", methods=["GET", "POST"])
@admin_required
def new_employee():
    if request.method == "POST":
        values, errors = read_employee_form()
        if errors:
            flash(" ".join(errors), "error")
            return render_employee_form(values), 400
        db = get_db()
        cur = db.execute(
            f"INSERT INTO employees ({', '.join(EMPLOYEE_FIELDS)})"
            f" VALUES ({', '.join('?' * len(EMPLOYEE_FIELDS))})",
            [values[f] for f in EMPLOYEE_FIELDS],
        )
        _apply_employee_auth(db, cur.lastrowid)
        db.commit()
        flash(f"Employee added: {values['name']}")
        return redirect(url_for("employee_detail", employee_id=cur.lastrowid))
    return render_employee_form({})


@app.route("/employees/<int:employee_id>")
def employee_detail(employee_id):
    db = get_db()
    employee = db.execute(
        "SELECT * FROM employees WHERE id = ?", (employee_id,)
    ).fetchone()
    if employee is None:
        abort(404)
    roles = [r.strip() for r in (employee["roles"] or "").split(",") if r.strip()]
    files = db.execute(
        "SELECT * FROM employee_files WHERE employee_id = ? ORDER BY id",
        (employee_id,)
    ).fetchall()
    documented = {f["credential_name"] for f in files if f["credential_name"]}
    credentials = []
    for c in db.execute(
            "SELECT * FROM employee_credentials WHERE employee_id = ?"
            " ORDER BY name", (employee_id,)).fetchall():
        state, text = credential_status(c["expires"])
        credentials.append({"row": c, "state": state, "status_text": text,
                            "documented": c["name"] in documented})
    # License requirement labels, for the "satisfies requirement" dropdown.
    license_labels = [r["label"] for r in db.execute(
        "SELECT DISTINCT label FROM resource_rules WHERE category = 'License'"
        " ORDER BY label").fetchall()]
    # Piece 10: everything assigned to this person, across all jobs. Open
    # (not-Done) tasks first, then by due date, so what's pending is on top.
    assigned_tasks = db.execute(
        "SELECT t.*, j.job_name, j.id AS job_id, c.name AS client_name"
        " FROM job_tasks t"
        " JOIN jobs j ON j.id = t.job_id"
        " JOIN clients c ON c.id = j.client_id"
        " WHERE t.employee_id = ?"
        " ORDER BY (t.status = 'Done'), (t.due_date = ''), t.due_date, t.id",
        (employee_id,)).fetchall()
    return render_template(
        "employee_detail.html", employee=employee, roles=roles,
        credentials=credentials, files=files, license_labels=license_labels,
        cred_names=[c["row"]["name"] for c in credentials],
        assigned_tasks=assigned_tasks, task_statuses=TASK_STATUSES,
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_employee(employee_id):
    db = get_db()
    employee = db.execute(
        "SELECT * FROM employees WHERE id = ?", (employee_id,)
    ).fetchone()
    if employee is None:
        abort(404)
    if request.method == "POST":
        values, errors = read_employee_form()
        if errors:
            flash(" ".join(errors), "error")
            return render_employee_form(values, employee_id=employee_id), 400
        db.execute(
            f"UPDATE employees SET {', '.join(f + ' = ?' for f in EMPLOYEE_FIELDS)}"
            " WHERE id = ?",
            [values[f] for f in EMPLOYEE_FIELDS] + [employee_id],
        )
        _apply_employee_auth(db, employee_id)
        db.commit()
        flash(f"Employee updated: {values['name']}")
        return redirect(url_for("employee_detail", employee_id=employee_id))
    values = {f: employee[f] for f in EMPLOYEE_FIELDS}
    return render_employee_form(
        values, employee_id=employee_id,
        username=employee["username"] or "",
        access_level=employee["access_level"] or "")


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
@admin_required
def delete_employee(employee_id):
    db = get_db()
    # Remove the person's credentials and document records, and their files
    # on disk, so nothing is orphaned.
    for record in db.execute(
            "SELECT stored_name FROM employee_files WHERE employee_id = ?",
            (employee_id,)).fetchall():
        (employee_upload_dir(employee_id) / record["stored_name"]).unlink(missing_ok=True)
    db.execute("DELETE FROM employee_files WHERE employee_id = ?", (employee_id,))
    db.execute("DELETE FROM employee_credentials WHERE employee_id = ?", (employee_id,))
    # Tasks belong to the job, not the person — unassign rather than delete
    # them (and keep the FK happy, since foreign_keys is ON).
    db.execute("UPDATE job_tasks SET employee_id = NULL WHERE employee_id = ?",
               (employee_id,))
    db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    db.commit()
    flash("Employee removed.")
    return redirect(url_for("employees_page"))


# ---- employee licenses & certifications (structured, with expiry) --------
@app.route("/employees/<int:employee_id>/credentials/add", methods=["POST"])
@admin_required
def add_credential(employee_id):
    if get_db().execute("SELECT id FROM employees WHERE id = ?",
                        (employee_id,)).fetchone() is None:
        abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("A license/certification needs a name.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="licenses"))
    db = get_db()
    db.execute(
        "INSERT INTO employee_credentials"
        " (employee_id, name, rule_label, number, issued, expires, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (employee_id, name,
         request.form.get("rule_label", "").strip(),
         request.form.get("number", "").strip(),
         request.form.get("issued", "").strip(),
         request.form.get("expires", "").strip(),
         request.form.get("notes", "").strip()),
    )
    db.commit()
    flash(f"Added license/certification: {name}")
    return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="licenses"))


@app.route("/employees/<int:employee_id>/credentials/<int:credential_id>/delete",
           methods=["POST"])
@admin_required
def delete_credential(employee_id, credential_id):
    db = get_db()
    db.execute("DELETE FROM employee_credentials WHERE id = ? AND employee_id = ?",
               (credential_id, employee_id))
    db.commit()
    flash("License/certification removed.")
    return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="licenses"))


# ---- employee documents (copies of certifications, etc.) -----------------
def employee_upload_dir(employee_id):
    directory = UPLOADS_DIR / f"employee_{employee_id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@app.route("/employees/<int:employee_id>/files/upload", methods=["POST"])
@admin_required
def upload_employee_file(employee_id):
    if get_db().execute("SELECT id FROM employees WHERE id = ?",
                        (employee_id,)).fetchone() is None:
        abort(404)
    upload = request.files.get("document")
    if upload is None or not upload.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="documents"))
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash(f"File type .{extension} is not allowed.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="documents"))
    original = upload.filename
    stored = f"{uuid.uuid4().hex[:8]}_{secure_filename(original)}"
    upload.save(employee_upload_dir(employee_id) / stored)
    db = get_db()
    db.execute(
        "INSERT INTO employee_files"
        " (employee_id, credential_name, stored_name, original_name)"
        " VALUES (?, ?, ?, ?)",
        (employee_id, request.form.get("credential_name", "").strip(),
         stored, original),
    )
    db.commit()
    flash(f"Uploaded: {original}")
    return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="documents"))


@app.route("/employees/<int:employee_id>/files/<int:file_id>/download")
def download_employee_file(employee_id, file_id):
    record = get_db().execute(
        "SELECT * FROM employee_files WHERE id = ? AND employee_id = ?",
        (file_id, employee_id)).fetchone()
    if record is None:
        abort(404)
    return send_from_directory(
        employee_upload_dir(employee_id), record["stored_name"],
        as_attachment=True, download_name=record["original_name"])


@app.route("/employees/<int:employee_id>/files/<int:file_id>/delete",
           methods=["POST"])
@admin_required
def delete_employee_file(employee_id, file_id):
    db = get_db()
    record = db.execute(
        "SELECT * FROM employee_files WHERE id = ? AND employee_id = ?",
        (file_id, employee_id)).fetchone()
    if record:
        (employee_upload_dir(employee_id) / record["stored_name"]).unlink(missing_ok=True)
        db.execute("DELETE FROM employee_files WHERE id = ?", (record["id"],))
        db.commit()
        flash(f"Deleted: {record['original_name']}")
    return redirect(url_for("employee_detail", employee_id=employee_id, _anchor="documents"))


@app.route("/audit")
@admin_required
def audit_log_page():
    """Read-only view of the system audit log, newest first, filterable by
    action. Admin-oriented — will sit behind role access once logins land."""
    db = get_db()
    action = request.args.get("action", "")
    sql = "SELECT * FROM audit_log"
    params = []
    if action:
        sql += " WHERE action = ?"
        params.append(action)
    sql += " ORDER BY id DESC LIMIT 300"
    entries = []
    for e in db.execute(sql, params).fetchall():
        try:
            entity = json.loads(e["entity"] or "{}")
        except ValueError:
            entity = {}
        try:
            detail = json.loads(e["detail"] or "{}")
        except ValueError:
            detail = {}
        entries.append({
            "ts": e["ts"], "actor": e["actor"], "action": e["action"],
            "path": e["path"], "status": e["status"], "ip": e["ip"],
            "entity": entity, "detail": detail,
        })
    actions = [r["action"] for r in db.execute(
        "SELECT DISTINCT action FROM audit_log ORDER BY action").fetchall()]
    total = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    return render_template("audit.html", entries=entries, actions=actions,
                           action=action, total=total)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
