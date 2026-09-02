"""
run_queries.py — loads leads.csv into a local SQLite database and runs
queries.sql, printing the results. Also proves the UNIQUE constraint from
schema.sql actually blocks a duplicate insert.

Run:
    pip install pandas   (if not already installed)
    python run_queries.py

No server needed — SQLite is built into Python.
"""

import sqlite3
import pandas as pd

CSV_PATH = "leads.csv"          # put leads.csv in the same folder as this script
QUERIES_PATH = "queries.sql"

conn = sqlite3.connect(":memory:")  # in-memory DB — nothing written to disk

# --- Step 1: load the raw CSV as-is (this is "the messy CRM dump" the brief
# describes — duplicates included) into a staging table with no constraints,
# so query 2 has something to find. ---
conn.execute("CREATE TABLE lead_sources (source_id INTEGER PRIMARY KEY, source_name TEXT UNIQUE)")
conn.execute("""CREATE TABLE leads (
    lead_id TEXT PRIMARY KEY, crm_record_hash INTEGER, created_at TEXT, source_id INTEGER,
    city TEXT, area TEXT, property_type TEXT, budget_pkr_lac REAL, bedrooms INTEGER,
    first_response_minutes REAL, calls_made INTEGER, total_call_seconds INTEGER,
    whatsapp_replies INTEGER, site_visits INTEGER, agent_experience_years REAL,
    is_overseas INTEGER, referred_by_existing_client INTEGER, has_financing_approved INTEGER,
    token_amount_received_pkr REAL, converted INTEGER)""")

df = pd.read_csv(CSV_PATH)
sources = sorted(df.source.unique())
conn.executemany("INSERT INTO lead_sources (source_name) VALUES (?)", [(s,) for s in sources])
src_map = {name: sid for sid, name in conn.execute("SELECT source_id, source_name FROM lead_sources")}

rows = []
for _, r in df.iterrows():
    rows.append((
        r.lead_id, int(r.crm_record_hash), r.created_at, src_map[r.source], r.city,
        r.area if pd.notna(r.area) else None, r.property_type,
        r.budget_pkr_lac if pd.notna(r.budget_pkr_lac) else None,
        int(r.bedrooms) if pd.notna(r.bedrooms) else None,
        r.first_response_minutes if pd.notna(r.first_response_minutes) else None,
        int(r.calls_made), int(r.total_call_seconds), int(r.whatsapp_replies), int(r.site_visits),
        r.agent_experience_years if pd.notna(r.agent_experience_years) else None,
        int(r.is_overseas), int(r.referred_by_existing_client), int(r.has_financing_approved),
        r.token_amount_received_pkr, int(r.converted),
    ))
conn.executemany("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
conn.commit()
print(f"Loaded all {len(df)} raw CSV rows (duplicates included, as in the real dump).\n")

# --- Step 2: run queries.sql against this raw data ---
with open(QUERIES_PATH) as f:
    sql_text = f.read()
q1 = sql_text.split("-- 2.")[0]
q2 = "-- 2." + sql_text.split("-- 2.")[1]
q2 = q2.split("-- Prevention")[0]

print("=== Query 1: conversion rate by source (200+ leads) ===")
for row in conn.execute(q1):
    print(row)

print("\n=== Query 2: duplicate leads found in the raw data ===")
dupes = conn.execute(q2).fetchall()
print(f"{len(dupes)} duplicate groups found\n")
for row in dupes[:10]:
    print(row)
if len(dupes) > 10:
    print(f"... and {len(dupes) - 10} more")

# --- Step 3: prove the schema's UNIQUE constraint actually prevents this,
# by re-creating the real leads table (from schema.sql) and trying to insert
# one known duplicate pair into it. ---
print("\n=== Proving schema.sql's UNIQUE constraint blocks the duplicate ===")
conn2 = sqlite3.connect(":memory:")
with open("schema.sql") as f:
    conn2.executescript(f.read())
conn2.execute("INSERT INTO lead_sources (source_name) VALUES ('Facebook Ads')")

dup_hash, _, dup_ids = dupes[0]
id_a, id_b = [s.strip() for s in dup_ids.split(",")]
conn2.execute(
    "INSERT INTO leads (lead_id, crm_record_hash, created_at, source_id, city, property_type, converted) "
    "VALUES (?, ?, '2024-01-01', 1, 'Islamabad', 'Apartment', 0)",
    (id_a, dup_hash),
)
try:
    conn2.execute(
        "INSERT INTO leads (lead_id, crm_record_hash, created_at, source_id, city, property_type, converted) "
        "VALUES (?, ?, '2024-01-01', 1, 'Islamabad', 'Apartment', 0)",
        (id_b, dup_hash),
    )
    print("Unexpected: second insert succeeded (constraint not working).")
except sqlite3.IntegrityError as e:
    print(f"Second insert correctly rejected: {e}")
