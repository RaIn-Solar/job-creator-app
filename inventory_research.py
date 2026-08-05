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

RESEARCH_VERSION = 3

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
    'Battery||Absolyte||100G17': {"specs": {"Voltage": 2.0}, "flags": 'Capacity incomplete — Voltage and/or Ah missing; needs a datasheet lookup.'},
    'Battery||BYD||BYD-HVL-3': {"specs": {"Capacity": 12.0, "Voltage": 350.0, "AH Rating": 80.0}, "flags": 'CAPACITY set to 12.0 kWh (manufacturer rating from description). NOTE: Voltage x Ah = 28.0 kWh differs >20% — check the 350.0V/80.0Ah entries.'},
    'Battery||C&D Technologies||AES 100LC17 - 48V 4 per cell': {"specs": {"Voltage": 48.0}, "flags": 'Capacity incomplete — Voltage and/or Ah missing; needs a datasheet lookup.'},
    'Battery||C&D Technologies||AES 100LC33 - 24volt-3 cell per module': {"specs": {"Capacity": 44.0, "Voltage": 24.0, "AH Rating": 1834.0}, "flags": 'CAPACITY CORRECTED to 44.0 kWh (manufacturer rating; sheet had 0.8).'},
    'Battery||C&D Technologies||AES 100LC33 - 48volt-4 cell per module': {"specs": {"Capacity": 88.032, "Voltage": 48.0, "AH Rating": 1834.0}, "flags": 'CAPACITY CORRECTED to 88.032 kWh (nameplate = 48.0V x 1834.0Ah / 1000; sheet had 70.43).'},
    'Battery||CALB||CA180FI Lithium LifePO4': {"specs": {"Capacity": 0.576, "Voltage": 3.2, "AH Rating": 180.0}, "flags": 'CAPACITY CORRECTED to 0.576 kWh (nameplate = 3.2V x 180.0Ah / 1000; sheet had 0.52).'},
    'Battery||Continental||CBEV-24-DT': {"specs": {"AH Rating": 85.0}, "flags": 'Capacity incomplete — Voltage and/or Ah missing; needs a datasheet lookup.'},
    'Battery||Continental||CBEV-L16-903-DT': {"specs": {"Capacity": 2.34, "Voltage": 6.0, "AH Rating": 390.0}, "flags": 'CAPACITY CORRECTED to 2.34 kWh (nameplate = 6.0V x 390.0Ah / 1000; sheet had 1.87).'},
    'Battery||Continental||Golf Cart CBEV-GC2-DT': {"specs": {"Capacity": 0.44, "Voltage": 2.0, "AH Rating": 220.0}, "flags": 'CAPACITY CORRECTED to 0.44 kWh (nameplate = 2.0V x 220.0Ah / 1000; sheet had 1.3).'},
    'Battery||Full River||DC250-6 6v 250 AH, GC-2, AGM': {"specs": {"Capacity": 1.5, "Voltage": 6.0, "AH Rating": 250.0}, "flags": 'CAPACITY CORRECTED to 1.5 kWh (nameplate = 6.0V x 250.0Ah / 1000; sheet had 0.8).'},
    'Battery||Home Grid||Compact Series': {"specs": {"Capacity": 5.12, "Voltage": 48.0, "AH Rating": 106.0}, "flags": 'CAPACITY CORRECTED to 5.12 kWh (manufacturer rating; sheet had 0.8).'},
    'Battery||Home Grid||HG-FS48100-15OSJ1': {"specs": {"Capacity": 4.3, "Voltage": 48.0, "AH Rating": 100.0}, "flags": 'CAPACITY CORRECTED to 4.3 kWh (manufacturer rating; sheet had 0.8).'},
    "Battery||O'Reilly's or equivalent||Battery": {"flags": 'Capacity incomplete — Voltage and/or Ah missing; needs a datasheet lookup.'},
    'Battery||Precision||PR110-DC+HT': {"specs": {"Capacity": 1.32, "Voltage": 12.0, "AH Rating": 110.0}, "flags": 'CAPACITY CORRECTED to 1.32 kWh (nameplate = 12.0V x 110.0Ah / 1000; sheet had None).'},
    'Battery||SimpliPhi||Ampliphi-3.8-48': {"specs": {"Capacity": 3.8, "Voltage": 48.0, "AH Rating": 75.0}, "flags": 'CAPACITY CORRECTED to 3.8 kWh (manufacturer rating; sheet had 3.0).'},
    'Battery||SOK Battery||S24V100': {"specs": {"Capacity": 2.4, "Voltage": 24.0, "AH Rating": 100.0}, "flags": 'CAPACITY CORRECTED to 2.4 kWh (nameplate = 24.0V x 100.0Ah / 1000; sheet had 2400.0).'},
    'Battery||Trojan||L16RE-2V': {"specs": {"Capacity": 2.22, "Voltage": 2.0, "AH Rating": 1110.0}, "flags": 'CAPACITY CORRECTED to 2.22 kWh (nameplate = 2.0V x 1110.0Ah / 1000; sheet had 2220.0).'},
    'Battery||US Battery||USL16, 12V 385ah': {"specs": {"Capacity": 4.62, "Voltage": 12.0, "AH Rating": 385.0}, "flags": 'CAPACITY CORRECTED to 4.62 kWh (nameplate = 12.0V x 385.0Ah / 1000; sheet had None).'},
    'Battery||US Battery||USL16HCL, 6V, 420ah': {"specs": {"Capacity": 2.52, "Voltage": 6.0, "AH Rating": 420.0}, "flags": 'CAPACITY CORRECTED to 2.52 kWh (nameplate = 6.0V x 420.0Ah / 1000; sheet had None).'},
    # --- Inverter sheet — string-inverter specs + battery/accessory flags ---
    'Inverter||Sol-Ark||Sol-Ark SA-15k-P, HARDENED': {"specs": {"Pout Rated (kW)": 15, "Vin Max": 500, "Vin Min": 175}, "manual_url": 'https://www.sol-ark.com/wp-content/uploads/2024/06/SK150-0001-002-15K-2P-N-EN-Datasheet.pdf', "flags": 'Verified: 15kW out, 19.5kW PV max, 3 MPPT 175-425V, Voc max 500V. Datasheet-cited.'},
    'Inverter||SMA||SB7.0-1SP-US-41': {"specs": {"Pout Rated (kW)": 7, "Vin Max": 600, "Vin Min": 100}, "manual_url": 'https://s3.amazonaws.com/ecodirect_docs/SMA/Sunny-Boy-US-series/SB3.0-7.7-US-DUS163317W.pdf', "flags": 'Verified: SMA Sunny Boy US, max DC 600V.'},
    'Inverter||SMA||SB7.001SP-US-40': {"specs": {"Pout Rated (kW)": 7, "Vin Max": 600, "Vin Min": 100}, "manual_url": 'https://s3.amazonaws.com/ecodirect_docs/SMA/Sunny-Boy-US-series/SB3.0-7.7-US-DUS163317W.pdf', "flags": 'Verified: SMA Sunny Boy US, max DC 600V (older -40 rev).'},
    'Inverter||SMA||SBSE3.8-US-50 - Hybrid': {"specs": {"Pout Rated (kW)": 3.8, "Vin Max": 600}, "manual_url": 'https://s3.amazonaws.com/ecodirect_docs/SMA/Sunny-Boy-US-series/SB3.0-7.7-US-DUS163317W.pdf', "flags": 'SB Smart Energy hybrid; 600V max DC (US standard) - verify against SBSE datasheet.'},
    'Inverter||SMA||SBSE4.8-US-50 - Hybrid': {"specs": {"Pout Rated (kW)": 4.8, "Vin Max": 600}, "manual_url": 'https://s3.amazonaws.com/ecodirect_docs/SMA/Sunny-Boy-US-series/SB3.0-7.7-US-DUS163317W.pdf', "flags": 'SB Smart Energy hybrid; 600V max DC (US standard) - verify against SBSE datasheet.'},
    'Inverter||SMA||SBSE5.8-US-50 - Hybrid': {"specs": {"Pout Rated (kW)": 5.8, "Vin Max": 600}, "manual_url": 'https://s3.amazonaws.com/ecodirect_docs/SMA/Sunny-Boy-US-series/SB3.0-7.7-US-DUS163317W.pdf', "flags": 'SB Smart Energy hybrid; 600V max DC (US standard) - verify against SBSE datasheet.'},
    'Inverter||GoodWe||GoodWGW5000-MS-US30 - Tigo': {"specs": {"Pout Rated (kW)": 5.0, "Vin Max": 600, "Vin Min": 165}, "manual_url": 'https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_MS-US_Datasheet-EN.pdf', "flags": 'Verified: GoodWe MS-US, max PV 600V.'},
    'Inverter||GoodWe||GoodWGW6000-MS-US30 - Tigo': {"specs": {"Pout Rated (kW)": 6.0, "Vin Max": 600, "Vin Min": 165}, "manual_url": 'https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_MS-US_Datasheet-EN.pdf', "flags": 'Verified: GoodWe MS-US, max PV 600V.'},
    'Inverter||GoodWe||GoodWGW7700-MS-US30 - Tigo': {"specs": {"Pout Rated (kW)": 7.7, "Vin Max": 600, "Vin Min": 165}, "manual_url": 'https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_MS-US_Datasheet-EN.pdf', "flags": 'Verified: GoodWe MS-US, max PV 600V.'},
    'Inverter||GoodWe||GoodWGW9600-MS-US30 - Tigo': {"specs": {"Pout Rated (kW)": 9.6, "Vin Max": 600, "Vin Min": 165}, "manual_url": 'https://en.goodwe.com/Ftp/EN/Downloads/Datasheet/GW_MS-US_Datasheet-EN.pdf', "flags": 'Verified: GoodWe MS-US, max PV 600V.'},
    'Inverter||Solis||1P9K-4G-US': {"specs": {"Pout Rated (kW)": 9, "Vin Max": 600, "Vin Min": 100}, "manual_url": 'https://www.invertersupply.com/media/data/Datasheet_Solis-1P9K-4G-US.pdf', "flags": 'Verified: Solis 1P9K-4G-US, max DC 600V, 4 MPPT.'},
    'Inverter||Magnum||MPSL175-30D': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Outback Power||GS4048A-01': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||EVO-1212F': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||EVO-1224F': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||EVO-1224F-HW': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||EVO-2212': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||EVO-2224': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Samlex||PST-2000-12': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
    'Inverter||Schneider Electric||Breaker Kit for Conext XW+PDP #RNW865121501': {"flags": 'NOT AN INVERTER — accessory (PDP / connection kit / breaker kit). Recategorize to Electrical.'},
    'Inverter||Schneider Electric||XW Connection kit for Inverter 2 (RNW865102002': {"flags": 'NOT AN INVERTER — accessory (PDP / connection kit / breaker kit). Recategorize to Electrical.'},
    'Inverter||Schneider Electric||XW+ mini Power Distribution Panel RNW865101301': {"flags": 'NOT AN INVERTER — accessory (PDP / connection kit / breaker kit). Recategorize to Electrical.'},
    'Inverter||Schneider Electric||XW+ POWER DISTIBUTION PANEL (RNW865101501)': {"flags": 'NOT AN INVERTER — accessory (PDP / connection kit / breaker kit). Recategorize to Electrical.'},
    'Inverter||Victron||MultiPlus 12V/2000/80A/120V': {"flags": 'Battery-based inverter/charger — no PV MPPT; PV Vin Max n/a (DC input = battery voltage).'},
}
