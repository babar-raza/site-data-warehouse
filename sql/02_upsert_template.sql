-- =============================================
-- UPSERT TEMPLATE FOR FACT_GSC_DAILY
-- =============================================
-- This template demonstrates the PostgreSQL UPSERT pattern
-- using INSERT ... ON CONFLICT ... DO UPDATE

-- Single row UPSERT example:
INSERT INTO gsc.fact_gsc_daily (
    date,
    property,
    url,
    query,
    country,
    device,
    clicks,
    impressions,
    ctr,
    position
) VALUES (
    '2025-01-31',                    -- date
    'https://example.com/',           -- property
    'https://example.com/page.html',  -- url
    'search query example',           -- query
    'USA',                           -- country
    'MOBILE',                        -- device
    150,                             -- clicks
    5000,                            -- impressions
    0.030000,                        -- ctr (3%)
    4.50                             -- position
)
ON CONFLICT (date, property, url, query, country, device)
DO UPDATE SET
    clicks = EXCLUDED.clicks,
    impressions = EXCLUDED.impressions,
    ctr = EXCLUDED.ctr,
    position = EXCLUDED.position,
    updated_at = CURRENT_TIMESTAMP
WHERE (
    fact_gsc_daily.clicks != EXCLUDED.clicks OR
    fact_gsc_daily.impressions != EXCLUDED.impressions OR
    fact_gsc_daily.ctr != EXCLUDED.ctr OR
    fact_gsc_daily.position != EXCLUDED.position
);

-- =============================================
-- BATCH UPSERT WITH CTE
-- =============================================
-- For better performance with multiple rows

WITH input_data (date, property, url, query, country, device, clicks, impressions, ctr, position) AS (
    VALUES
        ('2025-01-31'::DATE, 'https://example.com/', 'https://example.com/page1.html', 'query 1', 'USA', 'DESKTOP', 100, 3000, 0.033333, 3.2),
        ('2025-01-31'::DATE, 'https://example.com/', 'https://example.com/page2.html', 'query 2', 'USA', 'MOBILE', 50, 2000, 0.025000, 5.8),
        ('2025-01-31'::DATE, 'https://example.com/', 'https://example.com/page3.html', 'query 3', 'GBR', 'TABLET', 25, 1000, 0.025000, 7.3)
)
INSERT INTO gsc.fact_gsc_daily (
    date, property, url, query, country, device,
    clicks, impressions, ctr, position
)
SELECT * FROM input_data
ON CONFLICT (date, property, url, query, country, device)
DO UPDATE SET
    clicks = EXCLUDED.clicks,
    impressions = EXCLUDED.impressions,
    ctr = EXCLUDED.ctr,
    position = EXCLUDED.position,
    updated_at = CURRENT_TIMESTAMP;

-- =============================================
-- USING THE STORED FUNCTION
-- =============================================
-- Call the upsert function created in the schema

SELECT gsc.upsert_fact_gsc_daily(
    '2025-01-31'::DATE,
    'https://example.com/',
    'https://example.com/page.html',
    'search query',
    'USA',
    'MOBILE',
    150,
    5000,
    0.030000,
    4.50
);

-- =============================================
-- PYTHON PSYCOPG2 TEMPLATE
-- =============================================
/*
Python example using psycopg2:

import psycopg2
from psycopg2.extras import execute_values

def upsert_gsc_data(conn, data_rows):
    """
    Upsert GSC data using PostgreSQL ON CONFLICT
    
    Args:
        conn: psycopg2 connection
        data_rows: list of tuples (date, property, url, query, country, device, clicks, impressions, ctr, position)
    """
    query = """
        INSERT INTO gsc.fact_gsc_daily (
            date, property, url, query, country, device,
            clicks, impressions, ctr, position
        ) VALUES %s
        ON CONFLICT (date, property, url, query, country, device)
        DO UPDATE SET
            clicks = EXCLUDED.clicks,
            impressions = EXCLUDED.impressions,
            ctr = EXCLUDED.ctr,
            position = EXCLUDED.position,
            updated_at = CURRENT_TIMESTAMP
    """
    
    with conn.cursor() as cur:
        execute_values(cur, query, data_rows)
        conn.commit()
        return cur.rowcount
*/

-- =============================================
-- PERFORMANCE TIPS
-- =============================================
/*
1. For large batches (>1000 rows), consider:
   - Using COPY for initial load, then UPSERT for updates
   - Batching UPSERTs in transactions of 1000-5000 rows
   - Temporarily disabling indexes during bulk loads

2. Monitor performance with:
   EXPLAIN (ANALYZE, BUFFERS) <your_upsert_query>;

3. Ensure statistics are up to date:
   ANALYZE gsc.fact_gsc_daily;

4. Consider partitioning fact_gsc_daily by date for very large datasets
*/
