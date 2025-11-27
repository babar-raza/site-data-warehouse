-- =====================================================
-- SERP Dual Source Migration
-- =====================================================
-- Purpose: Add data_source column for dual SERP tracking (API + GSC)
-- Version: 1.0
-- Date: 2025-11-27
-- =====================================================

-- Add data_source column to serp.queries if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'serp'
        AND table_name = 'queries'
        AND column_name = 'data_source'
    ) THEN
        ALTER TABLE serp.queries
        ADD COLUMN data_source TEXT DEFAULT 'manual';

        COMMENT ON COLUMN serp.queries.data_source IS 'Source of query: manual, gsc, serpstack, valueserp, etc.';
    END IF;
END $$;

-- Add target_page_path to unique constraint if needed (for GSC sync)
-- First drop old constraint, then recreate with target_page_path
DO $$
BEGIN
    -- Check if we need to update the constraint
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'queries_property_query_text_location_device_key'
        AND conrelid = 'serp.queries'::regclass
    ) THEN
        -- Drop old constraint
        ALTER TABLE serp.queries
        DROP CONSTRAINT IF EXISTS queries_property_query_text_location_device_key;

        -- Create new constraint including target_page_path
        ALTER TABLE serp.queries
        ADD CONSTRAINT queries_property_query_text_page_device_location_key
        UNIQUE (property, query_text, target_page_path, device, location);
    END IF;
END $$;

-- Create index on data_source for filtering
CREATE INDEX IF NOT EXISTS idx_queries_data_source
ON serp.queries(data_source);

-- Create index for GSC sync queries
CREATE INDEX IF NOT EXISTS idx_queries_gsc_sync
ON serp.queries(property, data_source)
WHERE data_source = 'gsc';

-- Create index for API queries
CREATE INDEX IF NOT EXISTS idx_queries_api_sync
ON serp.queries(property, data_source)
WHERE data_source IN ('serpstack', 'valueserp', 'serpapi');

-- Update existing queries to mark as 'serpstack' if they have position_history from serpstack
UPDATE serp.queries q
SET data_source = 'serpstack'
WHERE EXISTS (
    SELECT 1 FROM serp.position_history ph
    WHERE ph.query_id = q.query_id
    AND ph.api_source = 'serpstack'
)
AND q.data_source = 'manual';

-- =====================================================
-- VIEWS UPDATE: Include data_source in views
-- =====================================================

-- Update current positions view with data_source
CREATE OR REPLACE VIEW serp.vw_current_positions AS
WITH latest_checks AS (
    SELECT DISTINCT ON (query_id)
        query_id,
        check_date,
        position,
        url,
        domain,
        title,
        serp_features,
        competitors,
        api_source
    FROM serp.position_history
    ORDER BY query_id, check_date DESC, check_timestamp DESC
),
previous_checks AS (
    SELECT DISTINCT ON (query_id)
        query_id,
        check_date as prev_check_date,
        position as prev_position
    FROM serp.position_history ph
    WHERE check_date < (SELECT MAX(check_date) FROM serp.position_history WHERE query_id = ph.query_id)
    ORDER BY query_id, check_date DESC, check_timestamp DESC
)
SELECT
    q.property,
    q.query_text,
    q.target_page_path,
    q.location,
    q.device,
    q.data_source,
    lc.check_date,
    lc.position,
    lc.url,
    lc.domain,
    lc.title,
    pc.prev_position,
    lc.position - pc.prev_position as position_change,
    pc.prev_check_date,
    CASE
        WHEN lc.position IS NULL AND pc.prev_position IS NULL THEN 'not_ranking'
        WHEN lc.position IS NULL AND pc.prev_position IS NOT NULL THEN 'dropped_out'
        WHEN lc.position IS NOT NULL AND pc.prev_position IS NULL THEN 'new_entry'
        WHEN lc.position < pc.prev_position THEN 'improved'
        WHEN lc.position > pc.prev_position THEN 'declined'
        ELSE 'stable'
    END as position_status,
    lc.serp_features,
    lc.competitors,
    lc.api_source
FROM serp.queries q
JOIN latest_checks lc ON q.query_id = lc.query_id
LEFT JOIN previous_checks pc ON q.query_id = pc.query_id
WHERE q.is_active = true;

COMMENT ON VIEW serp.vw_current_positions IS 'Current SERP positions with change tracking and data source';

-- Update top positions view with data_source breakdown
CREATE OR REPLACE VIEW serp.vw_top_positions AS
SELECT
    q.property,
    q.data_source,
    COUNT(*) FILTER (WHERE ph.position BETWEEN 1 AND 3) as top_3,
    COUNT(*) FILTER (WHERE ph.position BETWEEN 4 AND 10) as top_10,
    COUNT(*) FILTER (WHERE ph.position BETWEEN 11 AND 20) as top_20,
    COUNT(*) FILTER (WHERE ph.position BETWEEN 21 AND 100) as top_100,
    COUNT(*) FILTER (WHERE ph.position IS NULL) as not_ranking,
    COUNT(*) as total_queries,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ph.position <= 10) / NULLIF(COUNT(*), 0), 2) as pct_top_10
FROM serp.queries q
LEFT JOIN LATERAL (
    SELECT DISTINCT ON (query_id)
        query_id,
        position
    FROM serp.position_history
    WHERE query_id = q.query_id
    ORDER BY query_id, check_date DESC, check_timestamp DESC
) ph ON q.query_id = ph.query_id
WHERE q.is_active = true
GROUP BY q.property, q.data_source;

COMMENT ON VIEW serp.vw_top_positions IS 'Distribution of positions across ranking buckets by data source';

-- =====================================================
-- New view: Data source summary
-- =====================================================
CREATE OR REPLACE VIEW serp.vw_data_source_summary AS
SELECT
    property,
    data_source,
    COUNT(*) as total_queries,
    COUNT(*) FILTER (WHERE is_active) as active_queries,
    MIN(created_at) as first_query_added,
    MAX(updated_at) as last_updated
FROM serp.queries
GROUP BY property, data_source
ORDER BY property, data_source;

COMMENT ON VIEW serp.vw_data_source_summary IS 'Summary of SERP queries by data source';

-- =====================================================
-- New view: GSC vs API position comparison
-- =====================================================
CREATE OR REPLACE VIEW serp.vw_source_comparison AS
WITH gsc_positions AS (
    SELECT
        q.property,
        q.query_text,
        ph.position as gsc_position,
        ph.check_date as gsc_check_date
    FROM serp.queries q
    JOIN LATERAL (
        SELECT position, check_date
        FROM serp.position_history
        WHERE query_id = q.query_id
        ORDER BY check_date DESC
        LIMIT 1
    ) ph ON true
    WHERE q.data_source = 'gsc'
),
api_positions AS (
    SELECT
        q.property,
        q.query_text,
        ph.position as api_position,
        ph.check_date as api_check_date,
        q.data_source as api_source
    FROM serp.queries q
    JOIN LATERAL (
        SELECT position, check_date
        FROM serp.position_history
        WHERE query_id = q.query_id
        ORDER BY check_date DESC
        LIMIT 1
    ) ph ON true
    WHERE q.data_source IN ('serpstack', 'valueserp', 'serpapi')
)
SELECT
    COALESCE(g.property, a.property) as property,
    COALESCE(g.query_text, a.query_text) as query_text,
    g.gsc_position,
    g.gsc_check_date,
    a.api_position,
    a.api_check_date,
    a.api_source,
    a.api_position - g.gsc_position as position_difference
FROM gsc_positions g
FULL OUTER JOIN api_positions a
    ON g.property = a.property AND g.query_text = a.query_text
ORDER BY property, query_text;

COMMENT ON VIEW serp.vw_source_comparison IS 'Compare positions from GSC vs API sources';

-- =====================================================
-- Grant permissions
-- =====================================================
GRANT SELECT ON serp.vw_data_source_summary TO gsc_user;
GRANT SELECT ON serp.vw_source_comparison TO gsc_user;
