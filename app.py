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
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, Response, abort, flash, g, redirect, render_template, request,
    send_from_directory, url_for,
)
from werkzeug.utils import secure_filename

from bpmn_export import build_job_bpmn
from nm_directory import (
    COUNTIES_ALL, CORRECTIONS_V10, NEW_RULES_V10, UTILITIES_ALL,
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

# Employee directory (Piece 8). The core fields on a person's record:
# who they are, what they do, and when they work. Their licenses and
# certifications are structured rows in employee_credentials (Piece 8.1),
# managed on the profile page.
EMPLOYEE_FIELDS = ["name", "roles", "schedule"]
EMPLOYEE_FIELD_LABELS = {
    "name": "Name", "roles": "Roles", "schedule": "Schedule",
}
# Columns a user fills in when adding a license/certification.
CREDENTIAL_FIELDS = ["name", "rule_label", "number", "issued", "expires", "notes"]
# A credential within this many days of its expiry date is flagged
# "expiring soon" on the employee and job pages.
EXPIRY_SOON_DAYS = 60
# Common ECC crew roles, offered as checkboxes on the employee form (the
# form also allows free-typed extras). Stored comma-separated, like the
# job form's products.
EMPLOYEE_ROLES = [
    "Installer", "Electrician", "Journeyman", "HVAC Technician",
    "Well Pump Technician", "Generator Technician", "Project Manager",
    "Office / Admin", "Sales",
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
VERSION = "Piece 8.1"

UPLOADS_DIR = BASE_DIR / "uploads"
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "heic", "gif", "doc", "docx", "xls", "xlsx",
    "csv", "txt", "kmz", "kml", "zip", "bpmn",
}
MATERIAL_STATUSES = ["Needed", "Ordered", "Received", "Installed"]

app = Flask(__name__)
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
    ensure_columns(db, "employees", EMPLOYEE_FIELDS)
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
            ],
        )
        db.execute(
            "INSERT INTO jobs (client_id, job_name, site_location, county,"
            " electric_loads, utility_provider, warranty_type, cost_method,"
            " tax_credit, expand_option, products, pv_utility_connection,"
            " pv_mounting_type, battery_utility_connection, property_type)"
            " VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Johnson PV + Battery (sample)",
             "1247 Highway 518, Mora, NM 87732", "Mora County",
             "3-ton AC, well pump, shop sub-panel", "MSMEC",
             "Standard 10-year", "Cash", "Yes", "Yes",
             "PV Systems, Battery Banks",
             "Grid-tie", "Roof mounted", "Grid-tie", "Residential"),
        )
        emp1 = db.execute(
            "INSERT INTO employees (name, roles, schedule) VALUES (?, ?, ?)",
            ("Daniel Ortiz (sample)", "Electrician, Installer",
             "Mon–Fri 7:00 AM – 4:00 PM")).lastrowid
        emp2 = db.execute(
            "INSERT INTO employees (name, roles, schedule) VALUES (?, ?, ?)",
            ("Maria Sandoval (sample)", "Project Manager, Office / Admin",
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
    return render_template(
        "job_detail.html", job=job, groups=groups, versions=versions,
        materials=materials, files=files, filed_labels=filed_labels,
        coverage=coverage, requirement_groups=requirement_groups,
        material_statuses=MATERIAL_STATUSES, license_staffing=license_staffing(),
    )


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


@app.route("/jobs/<int:job_id>/materials/<int:material_id>/delete", methods=["POST"])
def delete_material(job_id, material_id):
    db = get_db()
    db.execute("DELETE FROM job_materials WHERE id = ? AND job_id = ?",
               (material_id, job_id))
    db.commit()
    return redirect(url_for("job_detail", job_id=job_id, _anchor="materials"))


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


def render_employee_form(values, employee_id=None):
    """Render the shared new/edit form, splitting stored roles back into
    the known checkbox roles and any free-typed extras."""
    stored = [r.strip() for r in (values.get("roles") or "").split(",") if r.strip()]
    selected = [r for r in stored if r in EMPLOYEE_ROLES]
    roles_other = ", ".join(r for r in stored if r not in EMPLOYEE_ROLES)
    return render_template(
        "employee_form.html", values=values, roles=EMPLOYEE_ROLES,
        selected=selected, roles_other=roles_other, employee_id=employee_id,
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


@app.route("/employees/new", methods=["GET", "POST"])
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
    return render_template(
        "employee_detail.html", employee=employee, roles=roles,
        credentials=credentials, files=files, license_labels=license_labels,
        cred_names=[c["row"]["name"] for c in credentials],
    )


@app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
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
        db.commit()
        flash(f"Employee updated: {values['name']}")
        return redirect(url_for("employee_detail", employee_id=employee_id))
    values = {f: employee[f] for f in EMPLOYEE_FIELDS}
    return render_employee_form(values, employee_id=employee_id)


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
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
    db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    db.commit()
    flash("Employee removed.")
    return redirect(url_for("employees_page"))


# ---- employee licenses & certifications (structured, with expiry) --------
@app.route("/employees/<int:employee_id>/credentials/add", methods=["POST"])
def add_credential(employee_id):
    if get_db().execute("SELECT id FROM employees WHERE id = ?",
                        (employee_id,)).fetchone() is None:
        abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("A license/certification needs a name.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id))
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
    return redirect(url_for("employee_detail", employee_id=employee_id))


@app.route("/employees/<int:employee_id>/credentials/<int:credential_id>/delete",
           methods=["POST"])
def delete_credential(employee_id, credential_id):
    db = get_db()
    db.execute("DELETE FROM employee_credentials WHERE id = ? AND employee_id = ?",
               (credential_id, employee_id))
    db.commit()
    flash("License/certification removed.")
    return redirect(url_for("employee_detail", employee_id=employee_id))


# ---- employee documents (copies of certifications, etc.) -----------------
def employee_upload_dir(employee_id):
    directory = UPLOADS_DIR / f"employee_{employee_id}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@app.route("/employees/<int:employee_id>/files/upload", methods=["POST"])
def upload_employee_file(employee_id):
    if get_db().execute("SELECT id FROM employees WHERE id = ?",
                        (employee_id,)).fetchone() is None:
        abort(404)
    upload = request.files.get("document")
    if upload is None or not upload.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id))
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        flash(f"File type .{extension} is not allowed.", "error")
        return redirect(url_for("employee_detail", employee_id=employee_id))
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
    return redirect(url_for("employee_detail", employee_id=employee_id))


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
    return redirect(url_for("employee_detail", employee_id=employee_id))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
