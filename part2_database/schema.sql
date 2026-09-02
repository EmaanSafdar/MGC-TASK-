-- schema.sql
-- MGC leads — minimal schema for the leads.csv dump.
--
-- Design decisions:
-- 1. One core table (`leads`) is enough. City/area/property_type/source are
--    attributes of a single lead event, not independent entities with their
--    own lifecycle here — normalizing them into separate tables would add
--    joins without solving any actual problem in this dataset. The one
--    exception is `source`: it's a small, fixed, reused set of values, so it
--    gets its own lookup table (`lead_sources`) to prevent typos/variants
--    ("Facebook Ads" vs "facebook ads" vs "FB Ads") and to make the
--    conversion-by-source query cheap and correct.
-- 2. `crm_record_hash` is the real identity of "this lead enquiry" (it's
--    identical across the duplicate pairs found in the data — same person,
--    same timestamp, same everything except lead_id). It gets a UNIQUE
--    constraint: that's what actually stops the "same lead entered twice by
--    two agents" problem at the database level (see queries.sql).
-- 3. `lead_id` stays the primary key because it's what the CRM and agents
--    already use to reference a record — but it is NOT the field that
--    proves uniqueness of the underlying enquiry.

CREATE TABLE lead_sources (
    source_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL UNIQUE
);

CREATE TABLE leads (
    lead_id                        TEXT PRIMARY KEY,
    crm_record_hash                INTEGER NOT NULL UNIQUE,   -- true identity of the enquiry; blocks duplicate entry
    created_at                     TEXT NOT NULL,              -- ISO datetime
    source_id                      INTEGER NOT NULL REFERENCES lead_sources(source_id),
    city                           TEXT NOT NULL,
    area                           TEXT,                       -- ~5% missing in source data
    property_type                  TEXT NOT NULL,
    budget_pkr_lac                 REAL,                       -- ~3% missing
    bedrooms                       INTEGER,                    -- ~40% missing (commercial units have none)
    first_response_minutes         REAL,                       -- ~2% missing
    calls_made                     INTEGER NOT NULL DEFAULT 0,
    total_call_seconds             INTEGER NOT NULL DEFAULT 0,
    whatsapp_replies               INTEGER NOT NULL DEFAULT 0,
    site_visits                    INTEGER NOT NULL DEFAULT 0,
    agent_experience_years         REAL,                       -- ~4% missing
    is_overseas                    INTEGER NOT NULL DEFAULT 0, -- boolean 0/1
    referred_by_existing_client    INTEGER NOT NULL DEFAULT 0, -- boolean 0/1
    has_financing_approved         INTEGER NOT NULL DEFAULT 0, -- boolean 0/1
    token_amount_received_pkr      REAL NOT NULL DEFAULT 0,
    converted                      INTEGER NOT NULL DEFAULT 0  -- boolean 0/1, the label
);

CREATE INDEX idx_leads_source     ON leads(source_id);
CREATE INDEX idx_leads_created_at ON leads(created_at);
CREATE INDEX idx_leads_converted  ON leads(converted);
