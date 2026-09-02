-- queries.sql

-- 1. Conversion rate by lead source, sources with 200+ leads only, best first.
SELECT
    ls.source_name,
    COUNT(*)                                                   AS total_leads,
    SUM(l.converted)                                           AS converted_leads,
    ROUND(100.0 * SUM(l.converted) / COUNT(*), 2)              AS conversion_rate_pct
FROM leads l
JOIN lead_sources ls ON ls.source_id = l.source_id
GROUP BY ls.source_name
HAVING COUNT(*) >= 200
ORDER BY conversion_rate_pct DESC;


-- 2. Find duplicate leads: same underlying enquiry (crm_record_hash) entered
--    more than once under a different lead_id. In this dataset that's the
--    "same lead entered twice by different agents" case: 160 pairs, 320 rows,
--    always same timestamp/details, only lead_id differs (a "-B" suffix).
SELECT
    crm_record_hash,
    COUNT(*)                       AS times_entered,
    GROUP_CONCAT(lead_id, ', ')    AS lead_ids
FROM leads
GROUP BY crm_record_hash
HAVING COUNT(*) > 1
ORDER BY times_entered DESC;

-- Prevention at the schema level: crm_record_hash has a UNIQUE constraint
-- on `leads` (see schema.sql). If the CRM computed that hash at intake
-- (e.g. from phone number + normalized name, or however it currently does),
-- a second agent entering the same lead would hit a unique-constraint
-- violation (or an `INSERT ... ON CONFLICT (crm_record_hash) DO NOTHING`
-- would silently no-op) instead of creating a second row.
