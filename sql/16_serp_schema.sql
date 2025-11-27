-- =====================================================
-- SERP Position Tracking Schema
-- =====================================================
-- Purpose: Track search engine ranking positions and SERP features
-- Phase: 3
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS serp;

-- =====================================================
-- QUERIES TABLE
-- =====================================================
-- Stores target keywords/queries to track
CREATE TABLE serp.queries (
    query_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_text TEXT NOT NULL,
    property TEXT NOT NULL,
    target_page_path TEXT,  -- Expected page to rank for this query
    location TEXT DEFAULT 'United States',
    language TEXT DEFAULT 'en',
    device TEXT DEFAULT 'desktop',  -- desktop or mobile
    search_engine TEXT DEFAULT 'google',
    is_active BOOLEAN DEFAULT true,
    check_frequency TEXT DEFAULT 'daily',  -- daily, weekly, monthly
    data_source TEXT DEFAULT 'manual',  -- manual, gsc, serpstack, valueserp, serpapi
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Updated constraint includes target_page_path for dual-source support
    UNIQUE(property, query_text, target_page_path, device, location)
);

-- Indexes
CREATE INDEX idx_queries_property ON serp.queries(property);
CREATE INDEX idx_queries_active ON serp.queries(is_active) WHERE is_active = true;
CREATE INDEX idx_queries_property_active ON serp.queries(property, is_active) WHERE is_active = true;
CREATE INDEX idx_queries_data_source ON serp.queries(data_source);
CREATE INDEX idx_queries_gsc_sync ON serp.queries(property, data_source) WHERE data_source = 'gsc';
CREATE INDEX idx_queries_api_sync ON serp.queries(property, data_source) WHERE data_source IN ('serpstack', 'valueserp', 'serpapi');

-- Auto-update timestamp
CREATE TRIGGER update_queries_updated_at
    BEFORE UPDATE ON serp.queries
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE serp.queries IS 'Target keywords to track in search engines';
COMMENT ON COLUMN serp.queries.query_text IS 'The search query/keyword to track';
COMMENT ON COLUMN serp.queries.target_page_path IS 'Expected page that should rank for this query';
COMMENT ON COLUMN serp.queries.check_frequency IS 'How often to check this query (daily, weekly, monthly)';


-- =====================================================
-- POSITION HISTORY TABLE
-- =====================================================
-- Stores historical position data for each query
CREATE TABLE serp.position_history (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID NOT NULL REFERENCES serp.queries(query_id) ON DELETE CASCADE,
    check_date DATE NOT NULL,
    check_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Position data
    position INT,  -- NULL if not found in top 100
    url TEXT,
    domain TEXT,
    title TEXT,
    description TEXT,

    -- SERP context
    total_results BIGINT,  -- Total search results count
    page_count INT,  -- Number of result pages checked

    -- Top competitors (top 10)
    competitors JSONB,  -- [{position: 1, domain: "example.com", url: "...", title: "..."}]

    -- SERP features present
    serp_features JSONB,  -- {featured_snippet: true, people_also_ask: true, ...}

    -- Metadata
    api_source TEXT,  -- valueserp, serpapi, scrapy, etc.
    raw_response JSONB,  -- Full API response for debugging

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(query_id, check_date, check_timestamp)
);

-- Indexes
CREATE INDEX idx_position_history_query ON serp.position_history(query_id);
CREATE INDEX idx_position_history_date ON serp.position_history(check_date DESC);
CREATE INDEX idx_position_history_query_date ON serp.position_history(query_id, check_date DESC);
CREATE INDEX idx_position_history_position ON serp.position_history(position) WHERE position IS NOT NULL;
CREATE INDEX idx_position_history_domain ON serp.position_history(domain);

COMMENT ON TABLE serp.position_history IS 'Historical SERP position data for tracked queries';
COMMENT ON COLUMN serp.position_history.position IS 'Ranking position (NULL if not in top 100)';
COMMENT ON COLUMN serp.position_history.competitors IS 'Top 10 competitors in SERP';
COMMENT ON COLUMN serp.position_history.serp_features IS 'SERP features present (featured snippet, PAA, etc.)';


-- =====================================================
-- SERP FEATURES TABLE
-- =====================================================
-- Detailed tracking of SERP features
CREATE TABLE serp.serp_features (
    feature_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_id UUID NOT NULL REFERENCES serp.queries(query_id) ON DELETE CASCADE,
    check_date DATE NOT NULL,
    feature_type TEXT NOT NULL,  -- featured_snippet, people_also_ask, video, image, knowledge_panel, etc.
    owner_domain TEXT,  -- Who owns this feature (e.g., which domain has the featured snippet)
    owner_url TEXT,
    content JSONB,  -- Feature-specific content
    position INT,  -- Position in SERP where feature appears
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(query_id, check_date, feature_type, owner_domain)
);

-- Indexes
CREATE INDEX idx_serp_features_query ON serp.serp_features(query_id);
CREATE INDEX idx_serp_features_date ON serp.serp_features(check_date DESC);
CREATE INDEX idx_serp_features_type ON serp.serp_features(feature_type);
CREATE INDEX idx_serp_features_owner ON serp.serp_features(owner_domain);

COMMENT ON TABLE serp.serp_features IS 'Detailed tracking of SERP features (featured snippets, PAA, etc.)';
COMMENT ON COLUMN serp.serp_features.feature_type IS 'Type of SERP feature';
COMMENT ON COLUMN serp.serp_features.owner_domain IS 'Domain that owns the feature';


-- =====================================================
-- VIEWS
-- =====================================================

-- Current positions with change tracking and data source
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


-- Position trends over time
CREATE OR REPLACE VIEW serp.vw_position_trends AS
SELECT
    q.property,
    q.query_text,
    q.location,
    q.device,
    ph.check_date,
    ph.position,
    ph.url,
    ph.domain,
    AVG(ph.position) OVER (
        PARTITION BY ph.query_id
        ORDER BY ph.check_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as position_7day_avg,
    AVG(ph.position) OVER (
        PARTITION BY ph.query_id
        ORDER BY ph.check_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as position_30day_avg,
    FIRST_VALUE(ph.position) OVER (
        PARTITION BY ph.query_id
        ORDER BY ph.check_date
    ) as first_position,
    ph.position - FIRST_VALUE(ph.position) OVER (
        PARTITION BY ph.query_id
        ORDER BY ph.check_date
    ) as position_change_from_start
FROM serp.position_history ph
JOIN serp.queries q ON ph.query_id = q.query_id
WHERE q.is_active = true
    AND ph.position IS NOT NULL
ORDER BY q.property, q.query_text, ph.check_date DESC;

COMMENT ON VIEW serp.vw_position_trends IS 'Position trends with moving averages';


-- Biggest gainers and losers
CREATE OR REPLACE VIEW serp.vw_position_changes AS
WITH current_pos AS (
    SELECT DISTINCT ON (query_id)
        query_id,
        position as current_position,
        check_date
    FROM serp.position_history
    ORDER BY query_id, check_date DESC, check_timestamp DESC
),
week_ago AS (
    SELECT DISTINCT ON (query_id)
        query_id,
        position as week_ago_position
    FROM serp.position_history
    WHERE check_date >= CURRENT_DATE - INTERVAL '8 days'
        AND check_date < CURRENT_DATE - INTERVAL '6 days'
    ORDER BY query_id, check_date DESC
)
SELECT
    q.property,
    q.query_text,
    q.target_page_path,
    q.location,
    q.device,
    cp.current_position,
    wa.week_ago_position,
    wa.week_ago_position - cp.current_position as position_gain,  -- Positive = improvement
    CASE
        WHEN cp.current_position IS NULL THEN 'not_ranking'
        WHEN wa.week_ago_position IS NULL THEN 'new_ranking'
        WHEN wa.week_ago_position - cp.current_position > 0 THEN 'improved'
        WHEN wa.week_ago_position - cp.current_position < 0 THEN 'declined'
        ELSE 'stable'
    END as change_status,
    cp.check_date as latest_check
FROM serp.queries q
LEFT JOIN current_pos cp ON q.query_id = cp.query_id
LEFT JOIN week_ago wa ON q.query_id = wa.query_id
WHERE q.is_active = true
ORDER BY position_gain DESC NULLS LAST;

COMMENT ON VIEW serp.vw_position_changes IS 'Week-over-week position changes (gainers and losers)';


-- SERP feature summary
CREATE OR REPLACE VIEW serp.vw_serp_feature_summary AS
SELECT
    q.property,
    q.query_text,
    q.location,
    sf.check_date,
    sf.feature_type,
    sf.owner_domain,
    sf.owner_url,
    CASE
        WHEN sf.owner_domain = SUBSTRING(q.property FROM '://([^/]+)')
            THEN true
        ELSE false
    END as we_own_feature
FROM serp.serp_features sf
JOIN serp.queries q ON sf.query_id = q.query_id
WHERE q.is_active = true
ORDER BY sf.check_date DESC, q.query_text;

COMMENT ON VIEW serp.vw_serp_feature_summary IS 'Summary of SERP features and ownership';


-- Top 10 positions summary with data source breakdown
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


-- Data source summary view
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


-- GSC vs API position comparison view
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
-- FUNCTIONS
-- =====================================================

-- Function to get position change for a query
CREATE OR REPLACE FUNCTION serp.get_position_change(
    p_query_id UUID,
    p_days_back INT DEFAULT 7
) RETURNS TABLE (
    current_position INT,
    previous_position INT,
    position_change INT,
    days_between INT
) AS $$
BEGIN
    RETURN QUERY
    WITH current AS (
        SELECT DISTINCT ON (query_id)
            position as curr_pos,
            check_date as curr_date
        FROM serp.position_history
        WHERE query_id = p_query_id
        ORDER BY query_id, check_date DESC, check_timestamp DESC
    ),
    previous AS (
        SELECT DISTINCT ON (query_id)
            position as prev_pos,
            check_date as prev_date
        FROM serp.position_history
        WHERE query_id = p_query_id
            AND check_date <= CURRENT_DATE - p_days_back
        ORDER BY query_id, check_date DESC, check_timestamp DESC
    )
    SELECT
        c.curr_pos,
        p.prev_pos,
        p.prev_pos - c.curr_pos,  -- Positive = improvement
        (c.curr_date - p.prev_date)::INT
    FROM current c
    CROSS JOIN previous p;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION serp.get_position_change IS 'Get position change for a query over specified days';


-- Function to get competitor rankings for a query
CREATE OR REPLACE FUNCTION serp.get_competitor_history(
    p_query_id UUID,
    p_days_back INT DEFAULT 30
) RETURNS TABLE (
    check_date DATE,
    domain TEXT,
    position INT,
    url TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ph.check_date,
        jsonb_array_elements(ph.competitors)->>'domain' as domain,
        (jsonb_array_elements(ph.competitors)->>'position')::INT as position,
        jsonb_array_elements(ph.competitors)->>'url' as url
    FROM serp.position_history ph
    WHERE ph.query_id = p_query_id
        AND ph.check_date >= CURRENT_DATE - p_days_back
        AND ph.competitors IS NOT NULL
    ORDER BY ph.check_date DESC, position ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION serp.get_competitor_history IS 'Get competitor ranking history for a query';


-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA serp TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA serp TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA serp TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA serp TO gsc_user;

-- Grant permissions on all views (including dual-source views)
GRANT SELECT ON serp.vw_current_positions TO gsc_user;
GRANT SELECT ON serp.vw_position_trends TO gsc_user;
GRANT SELECT ON serp.vw_position_changes TO gsc_user;
GRANT SELECT ON serp.vw_serp_feature_summary TO gsc_user;
GRANT SELECT ON serp.vw_top_positions TO gsc_user;
GRANT SELECT ON serp.vw_data_source_summary TO gsc_user;
GRANT SELECT ON serp.vw_source_comparison TO gsc_user;

-- =====================================================
-- SAMPLE DATA (for testing)
-- =====================================================

-- Insert sample queries (commented out by default)
/*
INSERT INTO serp.queries (property, query_text, target_page_path, location, device)
VALUES
    ('https://blog.aspose.net', 'python excel automation', '/cells/python/', 'United States', 'desktop'),
    ('https://blog.aspose.net', 'convert word to pdf python', '/words/python/', 'United States', 'desktop'),
    ('https://blog.aspose.net', 'pdf merge python', '/pdf/python/', 'United States', 'desktop');
*/
