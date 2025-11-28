-- =====================================================
-- Monitored Pages Schema for CWV URL Discovery
-- =====================================================
-- Purpose: Track pages discovered from GSC/GA4 for CWV monitoring
-- Phase: 3
-- Dependencies: performance schema, uuid-ossp extension
-- =====================================================

-- Ensure performance schema exists
CREATE SCHEMA IF NOT EXISTS performance;

-- =====================================================
-- MONITORED PAGES TABLE
-- =====================================================
-- Stores pages to monitor for Core Web Vitals
-- URLs are auto-discovered from GSC and GA4 fact tables

CREATE TABLE IF NOT EXISTS performance.monitored_pages (
    page_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property TEXT NOT NULL,
    page_path TEXT NOT NULL,
    page_name TEXT,                              -- Optional friendly name

    -- CWV check settings
    check_mobile BOOLEAN DEFAULT true,
    check_desktop BOOLEAN DEFAULT false,         -- Desktop off by default (saves API quota)
    is_active BOOLEAN DEFAULT true,

    -- Discovery metadata
    discovery_source TEXT DEFAULT 'manual',      -- 'gsc', 'ga4', 'manual', 'gsc+ga4'
    first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Traffic metrics (cumulative from discovery runs)
    total_clicks INTEGER DEFAULT 0,              -- Cumulative clicks from GSC
    total_sessions INTEGER DEFAULT 0,            -- Cumulative sessions from GA4
    avg_position NUMERIC(10,2),                  -- Average position from GSC

    -- Priority scoring for CWV collection order
    priority_score FLOAT DEFAULT 0,              -- Higher = check first

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure unique property + page_path combination
    UNIQUE(property, page_path)
);

-- =====================================================
-- INDEXES
-- =====================================================

-- Index for active pages lookup (main query for CWV collection)
CREATE INDEX IF NOT EXISTS idx_monitored_pages_active
    ON performance.monitored_pages(is_active)
    WHERE is_active = true;

-- Index for property-based queries
CREATE INDEX IF NOT EXISTS idx_monitored_pages_property
    ON performance.monitored_pages(property);

-- Index for priority-based ordering
CREATE INDEX IF NOT EXISTS idx_monitored_pages_priority
    ON performance.monitored_pages(priority_score DESC)
    WHERE is_active = true;

-- Index for discovery source filtering
CREATE INDEX IF NOT EXISTS idx_monitored_pages_source
    ON performance.monitored_pages(discovery_source);

-- Index for stale URL detection
CREATE INDEX IF NOT EXISTS idx_monitored_pages_last_seen
    ON performance.monitored_pages(last_seen_at);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_monitored_pages_active_priority
    ON performance.monitored_pages(property, is_active, priority_score DESC);

-- =====================================================
-- DISCOVERY SYNC WATERMARKS
-- =====================================================
-- Track last sync times for incremental discovery

CREATE TABLE IF NOT EXISTS performance.discovery_watermarks (
    watermark_id SERIAL PRIMARY KEY,
    property TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('gsc', 'ga4')),
    last_sync_at TIMESTAMP,
    urls_discovered INTEGER DEFAULT 0,
    urls_updated INTEGER DEFAULT 0,
    urls_deactivated INTEGER DEFAULT 0,
    last_run_status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, source_type)
);

CREATE INDEX IF NOT EXISTS idx_discovery_watermarks_property
    ON performance.discovery_watermarks(property);

-- =====================================================
-- VIEWS
-- =====================================================

-- View: Active monitored pages with check counts
CREATE OR REPLACE VIEW performance.vw_monitored_pages_summary AS
SELECT
    property,
    COUNT(*) as total_pages,
    COUNT(*) FILTER (WHERE is_active) as active_pages,
    COUNT(*) FILTER (WHERE check_mobile AND is_active) as mobile_checks,
    COUNT(*) FILTER (WHERE check_desktop AND is_active) as desktop_checks,
    SUM(total_clicks) as total_clicks,
    SUM(total_sessions) as total_sessions,
    AVG(priority_score) as avg_priority_score,
    COUNT(*) FILTER (WHERE discovery_source = 'gsc') as from_gsc,
    COUNT(*) FILTER (WHERE discovery_source = 'ga4') as from_ga4,
    COUNT(*) FILTER (WHERE discovery_source = 'gsc+ga4') as from_both,
    COUNT(*) FILTER (WHERE discovery_source = 'manual') as from_manual,
    MIN(first_discovered_at) as earliest_discovery,
    MAX(last_seen_at) as latest_activity
FROM performance.monitored_pages
GROUP BY property;

COMMENT ON VIEW performance.vw_monitored_pages_summary IS 'Summary of monitored pages by property';

-- View: Pages needing CWV checks (prioritized)
CREATE OR REPLACE VIEW performance.vw_pages_for_cwv AS
SELECT
    mp.page_id,
    mp.property,
    mp.page_path,
    mp.page_name,
    mp.check_mobile,
    mp.check_desktop,
    mp.priority_score,
    mp.total_clicks,
    mp.total_sessions,
    mp.discovery_source,
    cwv.check_date as last_cwv_check,
    cwv.performance_score as last_performance_score
FROM performance.monitored_pages mp
LEFT JOIN LATERAL (
    SELECT check_date, performance_score
    FROM performance.core_web_vitals
    WHERE property = mp.property
      AND page_path = mp.page_path
    ORDER BY check_date DESC
    LIMIT 1
) cwv ON true
WHERE mp.is_active = true
ORDER BY mp.priority_score DESC, mp.total_clicks DESC;

COMMENT ON VIEW performance.vw_pages_for_cwv IS 'Active pages for CWV collection, prioritized by score';

-- View: Stale pages (not seen recently)
CREATE OR REPLACE VIEW performance.vw_stale_monitored_pages AS
SELECT
    page_id,
    property,
    page_path,
    discovery_source,
    last_seen_at,
    CURRENT_TIMESTAMP - last_seen_at as time_since_seen,
    total_clicks,
    total_sessions,
    is_active
FROM performance.monitored_pages
WHERE last_seen_at < CURRENT_TIMESTAMP - INTERVAL '90 days'
ORDER BY last_seen_at ASC;

COMMENT ON VIEW performance.vw_stale_monitored_pages IS 'Pages not seen in GSC/GA4 data for over 90 days';

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function: Calculate priority score for a page
CREATE OR REPLACE FUNCTION performance.calculate_priority_score(
    p_clicks INTEGER,
    p_sessions INTEGER,
    p_avg_position NUMERIC,
    p_last_seen_at TIMESTAMP
) RETURNS FLOAT AS $$
DECLARE
    v_click_score FLOAT;
    v_session_score FLOAT;
    v_position_score FLOAT;
    v_recency_score FLOAT;
    v_days_since_seen INTEGER;
BEGIN
    -- Normalize clicks (log scale, max at 10000)
    v_click_score := LEAST(1.0, LOG(GREATEST(p_clicks, 1) + 1) / LOG(10001));

    -- Normalize sessions (log scale, max at 5000)
    v_session_score := LEAST(1.0, LOG(GREATEST(p_sessions, 1) + 1) / LOG(5001));

    -- Position score (better position = higher score, positions 1-10 are best)
    IF p_avg_position IS NOT NULL AND p_avg_position > 0 THEN
        v_position_score := GREATEST(0, 1.0 - (p_avg_position - 1) / 100);
    ELSE
        v_position_score := 0.5; -- Default for unknown position
    END IF;

    -- Recency score (seen in last 7 days = 1.0, decays over 90 days)
    v_days_since_seen := EXTRACT(DAY FROM CURRENT_TIMESTAMP - COALESCE(p_last_seen_at, CURRENT_TIMESTAMP));
    v_recency_score := GREATEST(0, 1.0 - (v_days_since_seen::FLOAT / 90));

    -- Weighted combination
    RETURN (
        0.40 * v_click_score +
        0.25 * v_session_score +
        0.20 * v_position_score +
        0.15 * v_recency_score
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION performance.calculate_priority_score IS
'Calculate priority score for CWV monitoring based on traffic, position, and recency';

-- Function: Update trigger for updated_at
CREATE OR REPLACE FUNCTION performance.update_monitored_pages_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update trigger
DROP TRIGGER IF EXISTS update_monitored_pages_updated_at ON performance.monitored_pages;
CREATE TRIGGER update_monitored_pages_updated_at
    BEFORE UPDATE ON performance.monitored_pages
    FOR EACH ROW EXECUTE FUNCTION performance.update_monitored_pages_timestamp();

DROP TRIGGER IF EXISTS update_discovery_watermarks_updated_at ON performance.discovery_watermarks;
CREATE TRIGGER update_discovery_watermarks_updated_at
    BEFORE UPDATE ON performance.discovery_watermarks
    FOR EACH ROW EXECUTE FUNCTION performance.update_monitored_pages_timestamp();

-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA performance TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON performance.monitored_pages TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON performance.discovery_watermarks TO gsc_user;
GRANT SELECT ON performance.vw_monitored_pages_summary TO gsc_user;
GRANT SELECT ON performance.vw_pages_for_cwv TO gsc_user;
GRANT SELECT ON performance.vw_stale_monitored_pages TO gsc_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA performance TO gsc_user;
GRANT EXECUTE ON FUNCTION performance.calculate_priority_score TO gsc_user;

-- =====================================================
-- MIGRATION: Handle existing data
-- =====================================================

-- If monitored_pages already exists with different schema, add missing columns
DO $$
BEGIN
    -- Add discovery_source if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'discovery_source'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN discovery_source TEXT DEFAULT 'manual';
    END IF;

    -- Add first_discovered_at if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'first_discovered_at'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;

    -- Add last_seen_at if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'last_seen_at'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    END IF;

    -- Add total_clicks if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'total_clicks'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN total_clicks INTEGER DEFAULT 0;
    END IF;

    -- Add total_sessions if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'total_sessions'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN total_sessions INTEGER DEFAULT 0;
    END IF;

    -- Add avg_position if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'avg_position'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN avg_position NUMERIC(10,2);
    END IF;

    -- Add priority_score if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'performance'
        AND table_name = 'monitored_pages'
        AND column_name = 'priority_score'
    ) THEN
        ALTER TABLE performance.monitored_pages
        ADD COLUMN priority_score FLOAT DEFAULT 0;
    END IF;
END $$;

-- Update existing manual entries to have proper discovery_source
UPDATE performance.monitored_pages
SET discovery_source = 'manual'
WHERE discovery_source IS NULL;

-- =====================================================
-- STATISTICS
-- =====================================================

ANALYZE performance.monitored_pages;
ANALYZE performance.discovery_watermarks;
