-- =====================================================
-- SERP Event Correlation Schema
-- =====================================================
-- Purpose: Track ranking changes and correlate them with trigger events
-- Phase: 4
-- Dependencies: serp schema (16_serp_schema.sql)
-- =====================================================

-- =====================================================
-- RANKING CHANGE EVENTS TABLE
-- =====================================================
-- Stores ranking changes correlated with trigger events
CREATE TABLE IF NOT EXISTS serp.ranking_change_events (
    id SERIAL PRIMARY KEY,
    property VARCHAR(500) NOT NULL,
    page_path TEXT NOT NULL,
    query TEXT,
    ranking_change_date DATE NOT NULL,
    previous_position INT,
    new_position INT,
    change_magnitude INT,  -- Positive = improvement (moved up), Negative = decline (moved down)

    -- Correlated trigger event
    trigger_event_type VARCHAR(100) NOT NULL,  -- content_change, algorithm_update, technical_issue
    trigger_event_date DATE,
    trigger_event_details JSONB,
    correlation_confidence NUMERIC(3,2) CHECK (correlation_confidence >= 0 AND correlation_confidence <= 1),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraint for unique correlation per ranking change + event type
    UNIQUE(property, page_path, ranking_change_date, trigger_event_type, trigger_event_date)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_property
    ON serp.ranking_change_events(property);
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_page
    ON serp.ranking_change_events(property, page_path);
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_date
    ON serp.ranking_change_events(ranking_change_date DESC);
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_trigger_type
    ON serp.ranking_change_events(trigger_event_type);
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_confidence
    ON serp.ranking_change_events(correlation_confidence DESC);
CREATE INDEX IF NOT EXISTS idx_ranking_change_events_trigger_date
    ON serp.ranking_change_events(trigger_event_date);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION serp.update_ranking_change_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_ranking_change_events_updated_at ON serp.ranking_change_events;
CREATE TRIGGER trigger_ranking_change_events_updated_at
    BEFORE UPDATE ON serp.ranking_change_events
    FOR EACH ROW
    EXECUTE FUNCTION serp.update_ranking_change_events_updated_at();

-- =====================================================
-- ALGORITHM UPDATES TABLE
-- =====================================================
-- Stores known Google algorithm updates for correlation
CREATE TABLE IF NOT EXISTS serp.algorithm_updates (
    id SERIAL PRIMARY KEY,
    update_name VARCHAR(200) NOT NULL,
    update_date DATE NOT NULL,
    update_type VARCHAR(100),  -- core, spam, helpful_content, link_spam, etc.
    description TEXT,
    impact_level VARCHAR(50),  -- major, minor, moderate
    official_announcement_url TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(update_name, update_date)
);

-- Indexes for algorithm updates
CREATE INDEX IF NOT EXISTS idx_algorithm_updates_date
    ON serp.algorithm_updates(update_date DESC);
CREATE INDEX IF NOT EXISTS idx_algorithm_updates_type
    ON serp.algorithm_updates(update_type);

-- =====================================================
-- VIEWS
-- =====================================================

-- View: Recent ranking changes with trigger events
CREATE OR REPLACE VIEW serp.vw_ranking_changes_with_events AS
SELECT
    rce.id,
    rce.property,
    rce.page_path,
    rce.query,
    rce.ranking_change_date,
    rce.previous_position,
    rce.new_position,
    rce.change_magnitude,
    CASE
        WHEN rce.change_magnitude > 0 THEN 'improved'
        WHEN rce.change_magnitude < 0 THEN 'declined'
        ELSE 'stable'
    END AS change_direction,
    rce.trigger_event_type,
    rce.trigger_event_date,
    rce.trigger_event_details,
    rce.correlation_confidence,
    (rce.ranking_change_date - rce.trigger_event_date) AS days_between_events,
    rce.created_at
FROM serp.ranking_change_events rce
ORDER BY rce.ranking_change_date DESC, rce.correlation_confidence DESC;

COMMENT ON VIEW serp.vw_ranking_changes_with_events IS 'Ranking changes with correlated trigger events';

-- View: Correlation summary by event type
CREATE OR REPLACE VIEW serp.vw_correlation_summary AS
SELECT
    trigger_event_type,
    COUNT(*) AS total_correlations,
    AVG(correlation_confidence) AS avg_confidence,
    COUNT(*) FILTER (WHERE change_magnitude > 0) AS positive_changes,
    COUNT(*) FILTER (WHERE change_magnitude < 0) AS negative_changes,
    AVG(ABS(change_magnitude)) AS avg_position_change
FROM serp.ranking_change_events
GROUP BY trigger_event_type
ORDER BY total_correlations DESC;

COMMENT ON VIEW serp.vw_correlation_summary IS 'Summary of correlations by trigger event type';

-- View: High confidence correlations
CREATE OR REPLACE VIEW serp.vw_high_confidence_correlations AS
SELECT
    rce.*,
    CASE
        WHEN rce.change_magnitude > 0 THEN 'improved'
        WHEN rce.change_magnitude < 0 THEN 'declined'
        ELSE 'stable'
    END AS change_direction
FROM serp.ranking_change_events rce
WHERE rce.correlation_confidence >= 0.7
ORDER BY rce.ranking_change_date DESC, rce.correlation_confidence DESC;

COMMENT ON VIEW serp.vw_high_confidence_correlations IS 'Ranking changes with high confidence trigger correlations';

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to get trigger events for a page within a date range
CREATE OR REPLACE FUNCTION serp.get_trigger_events(
    p_property VARCHAR(500),
    p_page_path TEXT,
    p_start_date DATE,
    p_end_date DATE
) RETURNS TABLE (
    event_type VARCHAR(100),
    event_date DATE,
    event_details JSONB,
    confidence NUMERIC(3,2),
    change_magnitude INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        rce.trigger_event_type,
        rce.trigger_event_date,
        rce.trigger_event_details,
        rce.correlation_confidence,
        rce.change_magnitude
    FROM serp.ranking_change_events rce
    WHERE rce.property = p_property
        AND rce.page_path = p_page_path
        AND rce.ranking_change_date >= p_start_date
        AND rce.ranking_change_date <= p_end_date
    ORDER BY rce.correlation_confidence DESC, rce.ranking_change_date DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION serp.get_trigger_events IS 'Get trigger events for a page within a date range';

-- Function to get algorithm updates within a date range
CREATE OR REPLACE FUNCTION serp.get_algorithm_updates_in_range(
    p_start_date DATE,
    p_end_date DATE
) RETURNS TABLE (
    update_name VARCHAR(200),
    update_date DATE,
    update_type VARCHAR(100),
    description TEXT,
    impact_level VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        au.update_name,
        au.update_date,
        au.update_type,
        au.description,
        au.impact_level
    FROM serp.algorithm_updates au
    WHERE au.update_date >= p_start_date
        AND au.update_date <= p_end_date
    ORDER BY au.update_date DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION serp.get_algorithm_updates_in_range IS 'Get algorithm updates within a date range';

-- =====================================================
-- SAMPLE ALGORITHM UPDATES DATA
-- =====================================================
-- Insert known Google algorithm updates (uncomment to use)
/*
INSERT INTO serp.algorithm_updates (update_name, update_date, update_type, description, impact_level)
VALUES
    ('March 2024 Core Update', '2024-03-05', 'core', 'Broad core algorithm update', 'major'),
    ('November 2023 Core Update', '2023-11-02', 'core', 'Broad core algorithm update', 'major'),
    ('October 2023 Spam Update', '2023-10-04', 'spam', 'Spam-fighting algorithm update', 'moderate'),
    ('September 2023 Helpful Content Update', '2023-09-14', 'helpful_content', 'Helpful content system update', 'major'),
    ('August 2023 Core Update', '2023-08-22', 'core', 'Broad core algorithm update', 'major'),
    ('April 2023 Reviews Update', '2023-04-12', 'reviews', 'Product reviews algorithm update', 'moderate')
ON CONFLICT (update_name, update_date) DO NOTHING;
*/

-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA serp TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON serp.ranking_change_events TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON serp.algorithm_updates TO gsc_user;
GRANT USAGE, SELECT ON SEQUENCE serp.ranking_change_events_id_seq TO gsc_user;
GRANT USAGE, SELECT ON SEQUENCE serp.algorithm_updates_id_seq TO gsc_user;
GRANT SELECT ON serp.vw_ranking_changes_with_events TO gsc_user;
GRANT SELECT ON serp.vw_correlation_summary TO gsc_user;
GRANT SELECT ON serp.vw_high_confidence_correlations TO gsc_user;
GRANT EXECUTE ON FUNCTION serp.get_trigger_events TO gsc_user;
GRANT EXECUTE ON FUNCTION serp.get_algorithm_updates_in_range TO gsc_user;

COMMENT ON TABLE serp.ranking_change_events IS 'SERP ranking changes correlated with trigger events';
COMMENT ON TABLE serp.algorithm_updates IS 'Known Google algorithm updates for correlation analysis';
