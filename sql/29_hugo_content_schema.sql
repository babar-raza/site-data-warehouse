-- Hugo Content Tracking Schema
-- Tracks Hugo CMS content changes and correlates with SEO performance

-- Create content schema if not exists
CREATE SCHEMA IF NOT EXISTS content;

-- Hugo Pages Table
-- Tracks all content pages from Hugo CMS
CREATE TABLE IF NOT EXISTS content.hugo_pages (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    page_path VARCHAR(1024) NOT NULL,
    title TEXT,
    content_hash VARCHAR(16) NOT NULL,
    word_count INTEGER,
    last_modified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    UNIQUE(property, page_path)
);

-- Hugo Changes Table
-- Tracks all content changes over time
CREATE TABLE IF NOT EXISTS content.hugo_changes (
    id SERIAL PRIMARY KEY,
    page_id INTEGER NOT NULL REFERENCES content.hugo_pages(id) ON DELETE CASCADE,
    change_type VARCHAR(20) NOT NULL CHECK (change_type IN ('created', 'updated', 'deleted')),
    old_hash VARCHAR(16),
    new_hash VARCHAR(16),
    word_count_change INTEGER,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_hugo_pages_property ON content.hugo_pages(property);
CREATE INDEX IF NOT EXISTS idx_hugo_pages_path ON content.hugo_pages(page_path);
CREATE INDEX IF NOT EXISTS idx_hugo_pages_deleted ON content.hugo_pages(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_hugo_pages_synced ON content.hugo_pages(synced_at);

CREATE INDEX IF NOT EXISTS idx_hugo_changes_page ON content.hugo_changes(page_id);
CREATE INDEX IF NOT EXISTS idx_hugo_changes_date ON content.hugo_changes(changed_at);
CREATE INDEX IF NOT EXISTS idx_hugo_changes_type ON content.hugo_changes(change_type);

-- Comments for Documentation
COMMENT ON TABLE content.hugo_pages IS 'Tracks all content pages from Hugo CMS with metadata and change detection';
COMMENT ON TABLE content.hugo_changes IS 'Audit log of all content changes with before/after hashes';

COMMENT ON COLUMN content.hugo_pages.property IS 'GSC property identifier for correlation';
COMMENT ON COLUMN content.hugo_pages.page_path IS 'URL path of the page (e.g., /blog/article)';
COMMENT ON COLUMN content.hugo_pages.content_hash IS 'SHA256 hash (first 16 chars) for change detection';
COMMENT ON COLUMN content.hugo_pages.word_count IS 'Total word count excluding front matter';
COMMENT ON COLUMN content.hugo_pages.last_modified IS 'Last modification time from git or filesystem';
COMMENT ON COLUMN content.hugo_pages.deleted_at IS 'Soft delete timestamp';

COMMENT ON COLUMN content.hugo_changes.change_type IS 'Type of change: created, updated, or deleted';
COMMENT ON COLUMN content.hugo_changes.old_hash IS 'Content hash before change';
COMMENT ON COLUMN content.hugo_changes.new_hash IS 'Content hash after change';
COMMENT ON COLUMN content.hugo_changes.word_count_change IS 'Delta in word count (can be negative)';

-- View: Recent Content Changes
-- Shows recent changes with page details
CREATE OR REPLACE VIEW content.recent_hugo_changes AS
SELECT
    p.property,
    p.page_path,
    p.title,
    c.change_type,
    c.changed_at,
    c.word_count_change,
    p.word_count as current_word_count
FROM content.hugo_changes c
JOIN content.hugo_pages p ON c.page_id = p.id
WHERE c.changed_at >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY c.changed_at DESC;

-- View: Content Performance Correlation
-- Correlates content changes with GSC performance (last 30 days)
CREATE OR REPLACE VIEW content.content_performance_correlation AS
WITH change_dates AS (
    SELECT
        p.property,
        p.page_path,
        c.change_type,
        c.changed_at::date as change_date,
        c.word_count_change
    FROM content.hugo_changes c
    JOIN content.hugo_pages p ON c.page_id = p.id
    WHERE c.changed_at >= CURRENT_DATE - INTERVAL '30 days'
),
performance_before AS (
    SELECT
        cd.property,
        cd.page_path,
        cd.change_date,
        cd.change_type,
        cd.word_count_change,
        AVG(sp.clicks) as avg_clicks_before,
        AVG(sp.impressions) as avg_impressions_before,
        AVG(sp.position) as avg_position_before
    FROM change_dates cd
    LEFT JOIN gsc.search_performance sp ON
        sp.property = cd.property
        AND sp.page LIKE '%' || cd.page_path || '%'
        AND sp.date BETWEEN cd.change_date - INTERVAL '7 days' AND cd.change_date - INTERVAL '1 day'
    GROUP BY cd.property, cd.page_path, cd.change_date, cd.change_type, cd.word_count_change
),
performance_after AS (
    SELECT
        cd.property,
        cd.page_path,
        cd.change_date,
        AVG(sp.clicks) as avg_clicks_after,
        AVG(sp.impressions) as avg_impressions_after,
        AVG(sp.position) as avg_position_after
    FROM change_dates cd
    LEFT JOIN gsc.search_performance sp ON
        sp.property = cd.property
        AND sp.page LIKE '%' || cd.page_path || '%'
        AND sp.date BETWEEN cd.change_date + INTERVAL '1 day' AND cd.change_date + INTERVAL '30 days'
    GROUP BY cd.property, cd.page_path, cd.change_date
)
SELECT
    pb.property,
    pb.page_path,
    pb.change_date,
    pb.change_type,
    pb.word_count_change,
    pb.avg_clicks_before,
    pa.avg_clicks_after,
    CASE
        WHEN pb.avg_clicks_before > 0 THEN
            ROUND(((pa.avg_clicks_after - pb.avg_clicks_before) / pb.avg_clicks_before * 100)::numeric, 2)
        ELSE NULL
    END as clicks_change_pct,
    pb.avg_position_before,
    pa.avg_position_after,
    ROUND((pb.avg_position_before - pa.avg_position_after)::numeric, 2) as position_improvement
FROM performance_before pb
JOIN performance_after pa ON
    pb.property = pa.property
    AND pb.page_path = pa.page_path
    AND pb.change_date = pa.change_date
ORDER BY pb.change_date DESC;

-- View: Active Content Summary
-- Summary statistics for active content
CREATE OR REPLACE VIEW content.active_content_summary AS
SELECT
    property,
    COUNT(*) as total_pages,
    SUM(word_count) as total_words,
    AVG(word_count) as avg_words_per_page,
    MAX(last_modified) as latest_update,
    COUNT(CASE WHEN last_modified >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as updated_last_30_days,
    COUNT(CASE WHEN last_modified >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as updated_last_7_days
FROM content.hugo_pages
WHERE deleted_at IS NULL
GROUP BY property;

-- Function: Get Content Impact Score
-- Calculates impact score for content changes based on performance correlation
CREATE OR REPLACE FUNCTION content.get_content_impact_score(
    p_page_path VARCHAR,
    p_property VARCHAR
) RETURNS TABLE (
    impact_score NUMERIC,
    impact_level VARCHAR,
    total_changes INTEGER,
    positive_changes INTEGER,
    avg_clicks_change NUMERIC,
    avg_position_change NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH change_impacts AS (
        SELECT
            COALESCE(clicks_change_pct, 0) as clicks_change,
            COALESCE(position_improvement, 0) as position_change
        FROM content.content_performance_correlation
        WHERE page_path = p_page_path
          AND property = p_property
    )
    SELECT
        -- Impact score: weighted average of clicks and position improvements
        ROUND((AVG(clicks_change) * 0.7 + AVG(position_change) * 30 * 0.3)::numeric, 2) as impact_score,
        CASE
            WHEN AVG(clicks_change) > 20 THEN 'high_positive'
            WHEN AVG(clicks_change) > 5 THEN 'moderate_positive'
            WHEN AVG(clicks_change) > -5 THEN 'neutral'
            WHEN AVG(clicks_change) > -20 THEN 'moderate_negative'
            ELSE 'high_negative'
        END as impact_level,
        COUNT(*)::integer as total_changes,
        COUNT(CASE WHEN clicks_change > 0 THEN 1 END)::integer as positive_changes,
        ROUND(AVG(clicks_change)::numeric, 2) as avg_clicks_change,
        ROUND(AVG(position_change)::numeric, 2) as avg_position_change
    FROM change_impacts
    WHERE clicks_change IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Function: Get Pages Needing Update
-- Identifies pages that haven't been updated recently and have declining performance
CREATE OR REPLACE FUNCTION content.get_pages_needing_update(
    p_property VARCHAR,
    p_days_since_update INTEGER DEFAULT 90,
    p_performance_threshold NUMERIC DEFAULT -10.0
) RETURNS TABLE (
    page_path VARCHAR,
    title TEXT,
    days_since_update INTEGER,
    word_count INTEGER,
    avg_position NUMERIC,
    avg_clicks NUMERIC,
    performance_trend NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    WITH page_performance AS (
        SELECT
            sp.page,
            AVG(sp.position) as avg_pos,
            AVG(sp.clicks) as avg_clk,
            -- Calculate trend: recent 7 days vs previous 7 days
            (
                AVG(CASE WHEN sp.date >= CURRENT_DATE - INTERVAL '7 days' THEN sp.clicks END) -
                AVG(CASE WHEN sp.date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN sp.clicks END)
            ) / NULLIF(AVG(CASE WHEN sp.date BETWEEN CURRENT_DATE - INTERVAL '14 days' AND CURRENT_DATE - INTERVAL '8 days' THEN sp.clicks END), 0) * 100 as trend
        FROM gsc.search_performance sp
        WHERE sp.property = p_property
          AND sp.date >= CURRENT_DATE - INTERVAL '14 days'
        GROUP BY sp.page
    )
    SELECT
        hp.page_path,
        hp.title,
        (CURRENT_DATE - hp.last_modified::date)::integer as days_since_update,
        hp.word_count,
        ROUND(pp.avg_pos::numeric, 2) as avg_position,
        ROUND(pp.avg_clk::numeric, 2) as avg_clicks,
        ROUND(COALESCE(pp.trend, 0)::numeric, 2) as performance_trend
    FROM content.hugo_pages hp
    LEFT JOIN page_performance pp ON pp.page LIKE '%' || hp.page_path || '%'
    WHERE hp.property = p_property
      AND hp.deleted_at IS NULL
      AND (CURRENT_DATE - hp.last_modified::date) > p_days_since_update
      AND COALESCE(pp.trend, 0) < p_performance_threshold
    ORDER BY performance_trend ASC, days_since_update DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT USAGE ON SCHEMA content TO PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA content TO PUBLIC;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA content TO PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA content TO PUBLIC;
