"""Piece 23.3: web-research overrides for the seed inventory, applied on top of
inventory_seed.py. Each entry corrects/completes specs, attaches datasheet
(manual_url) and purchase (purchase_url) links, records a web-verified price
where one can be fetched, sets Active/Discontinued, and carries a human-readable
flag. Bumping RESEARCH_VERSION re-applies the whole set on next launch.

Ground rules honored here:
- Never overwrite ECC's quoted Cost — web prices go in web_price only.
- Never fabricate: unverifiable prices/URLs are left blank and flagged.
- Wholesale-only vendors (ABC Supply, Greentech, BayWa, Fortune) rarely have a
  public per-item page, so purchase_url points at the best public retail listing
  for that exact item, flagged as reference (not necessarily the listed vendor).

Key format: "Category||Make||Model" (exactly as seeded).
"""

RESEARCH_VERSION = 1

RESEARCH = {
    # --- PV sheet — calibration batch -------------------------------------
    "PV Module||Canadian Solar||CS6P 260W Module": {
        "specs": {"Vmp": 30.4, "Imp": 8.56, "Voc": 37.5, "Isc": 9.12},
        "manual_url": "https://s3.amazonaws.com/ecodirect_docs/CANADIAN/"
                      "canadian-solar-cs6p-m-250-260-all-black-data-sheet-151231.pdf",
        "status": "Discontinued",
        "flags": "SPEC CORRECTION — sheet had Vmp 17 / Imp 5.0 / Voc 20 / Isc 5.1 "
                 "(incorrect); CS6P-260P datasheet: Vmp 30.4 / Imp 8.56 / Voc 37.5 "
                 "/ Isc 9.12. Legacy poly module.",
    },
    "PV Module||ET||ET 250": {
        "specs": {"Vmp": 30.34, "Imp": 8.24, "Voc": 37.47, "Isc": 8.76},
        "manual_url": "https://www.solaris-shop.com/"
                      "et-solar-et-p660250wb-250w-poly-solar-panel/",
        "status": "Discontinued",
        "flags": "SPECS COMPLETED from ET-P660250 datasheet (sheet had wattage "
                 "only). Full model likely ET-P660250(WB). Legacy poly module.",
    },
    "PV Module||Canadian Solar||CS7N-710TB-AG": {
        "manual_url": "https://static.csisolar.com/wp-content/uploads/sites/3/2024/"
                      "03/29101600/CS-Datasheet-TOPBiHiKu7-TOPCon_CS7N-TB-AG_"
                      "v1.61_F43M_J5_NA.pdf",
        "purchase_url": "https://a1solarstore.com/canadian-solar-710w-solar-panel-"
                        "132-cells-bifacial-cs7n-tb-ag-710-commercial-496-panels-"
                        "per-container.html",
        "status": "Active",
        "flags": "VERIFY Voc — sheet Voc 48.3 / Vmp 40.4 vs current datasheet STC "
                 "Voc 45.7 / Vmp 38.1 / Isc 14.99 / Imp 14.06 (front-side). Use "
                 "front-side STC for cold-temp string sizing. Retail listing shown "
                 "(A1 SolarStore); listed vendor N. AZ Wind & Sun also stocks it. "
                 "Price on request.",
    },
    "PV Module||Mission Solar||MSE410HTOB": {
        "manual_url": "https://www.solarelectricsupply.com/"
                      "mission-solar-410w-mse410ht0b-residential-solar-module",
        "purchase_url": "https://www.solarelectricsupply.com/"
                        "mission-solar-410w-mse410ht0b-residential-solar-module",
        "status": "Active",
        "flags": "Listed vendor ABC Supply is wholesale (no public per-item page); "
                 "retail listing shown for reference (Solar Electric Supply). "
                 "US-made (San Antonio, TX). Price on request — retail sites block "
                 "automated price fetch.",
    },
}
