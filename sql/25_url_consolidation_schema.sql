-- URL Consolidation Schema
-- Tracks consolidation candidates and history
-- Created: 2025-11-26
-- Purpose: Store consolidation opportunities and track actions taken

CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================
-- CONSOLIDATION CANDIDATES TABLE
-- =====================================================
-- Stores URLs that are candidates for consolidation
CREATE TABLE IF NOT EXISTS analytics.consolidation_candidates (
    id SERIAL PRIMARY KEY,
    property VARCHAR(255) NOT NULL,
    canonical_url VARCHAR(2000) NOT NULL,
    variation_urls JSONB NOT NULL,  -- Array of variation URLs with their metrics
    variation_count INTEGER NOT NULL,
    consolidation_score FLOAT NOT NULL,
    recommended_action VARCHAR(50), -- 'redirect_301', 'canonical_tag', 'canonical_tag_and_redirect', 'merge_content', 'monitor'
    total_clicks INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'actioned', 'dismissed', 'in_progress'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property, canonical_url)
);

-- =====================================================
-- CONSOLIDATION HISTORY TABLE
-- =====================================================
-- Tracks actions taken on consolidation candidates
CREATE TABLE IF NOT EXISTS analytics.consolidation_history (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES analytics.consolidation_candidates(id) ON DELETE CASCADE,
    action_taken VARCHAR(100) NOT NULL,  -- 'redirect_implemented', 'canonical_added', 'merged', 'dismissed'
    action_details JSONB,  -- Additional details about the action (e.g., redirect type, canonical URL used)
    performed_by VARCHAR(255),  -- User or system that performed the action
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome JSONB  -- Results of the action (e.g., traffic changes, ranking changes)
);

-- =====================================================
-- INDEXES
-- =====================================================
-- Performance indexes for common queries
CREATE INDEX IF NOT EXISTS idx_consolidation_property ON analytics.consolidation_candidates(property);
CREATE INDEX IF NOT EXISTS idx_consolidation_status ON analytics.consolidation_candidates(status);
CREATE INDEX IF NOT EXISTS idx_consolidation_score ON analytics.consolidation_candidates(consolidation_score DESC);
CREATE INDEX IF NOT EXISTS idx_consolidation_canonical ON analytics.consolidation_candidates(canonical_url);
CREATE INDEX IF NOT EXISTS idx_consolidation_updated ON analytics.consolidation_candidates(updated_at DESC);

-- Composite indexes for filtered queries
CREATE INDEX IF NOT EXISTS idx_consolidation_property_status ON analytics.consolidation_candidates(property, status);
CREATE INDEX IF NOT EXISTS idx_consolidation_property_score ON analytics.consolidation_candidates(property, consolidation_score DESC);

-- History indexes
CREATE INDEX IF NOT EXISTS idx_consolidation_history_candidate ON analytics.consolidation_history(candidate_id);
CREATE INDEX IF NOT EXISTS idx_consolidation_history_performed ON analytics.consolidation_history(performed_at DESC);
CREATE INDEX IF NOT EXISTS idx_consolidation_history_action ON analytics.consolidation_history(action_taken);

-- =====================================================
-- VIEWS
-- =====================================================

-- High priority consolidation opportunities
CREATE OR REPLACE VIEW analytics.vw_high_priority_consolidations AS
SELECT
    c.id,
    c.property,
    c.canonical_url,
    c.variation_count,
    c.consolidation_score,
    c.recommended_action,
    c.total_clicks,
    c.total_impressions,
    c.status,
    c.created_at,
    c.updated_at,
    CASE
        WHEN c.consolidation_score >= 80 THEN 'high'
        WHEN c.consolidation_score >= 50 THEN 'medium'
        ELSE 'low'
    END as priority,
    COUNT(h.id) as actions_taken
FROM analytics.consolidation_candidates c
LEFT JOIN analytics.consolidation_history h ON c.id = h.candidate_id
WHERE c.status IN ('pending', 'in_progress')
    AND c.consolidation_score >= 50
GROUP BY c.id
ORDER BY c.consolidation_score DESC, c.total_clicks DESC;

COMMENT ON VIEW analytics.vw_high_priority_consolidations IS 'Consolidation opportunities with medium to high priority scores';

-- Consolidation candidates with action history
CREATE OR REPLACE VIEW analytics.vw_consolidation_with_history AS
SELECT
    c.id,
    c.property,
    c.canonical_url,
    c.variation_count,
    c.consolidation_score,
    c.recommended_action,
    c.total_clicks,
    c.total_impressions,
    c.status,
    c.created_at,
    c.updated_at,
    jsonb_agg(
        jsonb_build_object(
            'action_taken', h.action_taken,
            'performed_by', h.performed_by,
            'performed_at', h.performed_at,
            'outcome', h.outcome
        ) ORDER BY h.performed_at DESC
    ) FILTER (WHERE h.id IS NOT NULL) as action_history
FROM analytics.consolidation_candidates c
LEFT JOIN analytics.consolidation_history h ON c.id = h.candidate_id
GROUP BY c.id
ORDER BY c.updated_at DESC;

COMMENT ON VIEW analytics.vw_consolidation_with_history IS 'Consolidation candidates with their complete action history';

-- Consolidation performance summary by property
CREATE OR REPLACE VIEW analytics.vw_consolidation_summary_by_property AS
SELECT
    property,
    COUNT(*) as total_candidates,
    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
    SUM(CASE WHEN status = 'actioned' THEN 1 ELSE 0 END) as actioned_count,
    SUM(CASE WHEN status = 'dismissed' THEN 1 ELSE 0 END) as dismissed_count,
    SUM(CASE WHEN consolidation_score >= 80 THEN 1 ELSE 0 END) as high_priority_count,
    SUM(CASE WHEN consolidation_score >= 50 AND consolidation_score < 80 THEN 1 ELSE 0 END) as medium_priority_count,
    AVG(consolidation_score) as avg_consolidation_score,
    SUM(total_clicks) as total_affected_clicks,
    SUM(total_impressions) as total_affected_impressions,
    SUM(variation_count) as total_variations,
    MAX(updated_at) as last_updated
FROM analytics.consolidation_candidates
GROUP BY property
ORDER BY total_affected_clicks DESC;

COMMENT ON VIEW analytics.vw_consolidation_summary_by_property IS 'Summary statistics of consolidation candidates by property';

-- Recent consolidation actions
CREATE OR REPLACE VIEW analytics.vw_recent_consolidation_actions AS
SELECT
    h.id,
    h.candidate_id,
    c.property,
    c.canonical_url,
    c.variation_count,
    h.action_taken,
    h.action_details,
    h.performed_by,
    h.performed_at,
    h.outcome,
    c.total_clicks as candidate_clicks,
    c.total_impressions as candidate_impressions
FROM analytics.consolidation_history h
JOIN analytics.consolidation_candidates c ON h.candidate_id = c.id
WHERE h.performed_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY h.performed_at DESC
LIMIT 100;

COMMENT ON VIEW analytics.vw_recent_consolidation_actions IS 'Recent consolidation actions taken in the last 30 days';

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to mark candidate as actioned
CREATE OR REPLACE FUNCTION analytics.mark_consolidation_actioned(
    p_candidate_id INTEGER,
    p_action_taken VARCHAR(100),
    p_action_details JSONB DEFAULT NULL,
    p_performed_by VARCHAR(255) DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_success BOOLEAN := FALSE;
BEGIN
    -- Update candidate status
    UPDATE analytics.consolidation_candidates
    SET status = 'actioned',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_candidate_id;

    -- Insert history record
    INSERT INTO analytics.consolidation_history (
        candidate_id,
        action_taken,
        action_details,
        performed_by
    ) VALUES (
        p_candidate_id,
        p_action_taken,
        p_action_details,
        p_performed_by
    );

    v_success := FOUND;
    RETURN v_success;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.mark_consolidation_actioned IS 'Mark a consolidation candidate as actioned and record the action in history';

-- Function to dismiss candidate
CREATE OR REPLACE FUNCTION analytics.dismiss_consolidation_candidate(
    p_candidate_id INTEGER,
    p_reason VARCHAR(255) DEFAULT NULL,
    p_performed_by VARCHAR(255) DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_success BOOLEAN := FALSE;
BEGIN
    -- Update candidate status
    UPDATE analytics.consolidation_candidates
    SET status = 'dismissed',
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_candidate_id;

    -- Insert history record
    INSERT INTO analytics.consolidation_history (
        candidate_id,
        action_taken,
        action_details,
        performed_by
    ) VALUES (
        p_candidate_id,
        'dismissed',
        jsonb_build_object('reason', p_reason),
        p_performed_by
    );

    v_success := FOUND;
    RETURN v_success;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.dismiss_consolidation_candidate IS 'Dismiss a consolidation candidate with optional reason';

-- Function to get consolidation candidates for a property
CREATE OR REPLACE FUNCTION analytics.get_consolidation_candidates(
    p_property VARCHAR(255),
    p_status VARCHAR(50) DEFAULT NULL,
    p_min_score FLOAT DEFAULT 0,
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    id INTEGER,
    canonical_url VARCHAR(2000),
    variation_count INTEGER,
    consolidation_score FLOAT,
    recommended_action VARCHAR(50),
    total_clicks INTEGER,
    total_impressions INTEGER,
    status VARCHAR(50),
    priority TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.canonical_url,
        c.variation_count,
        c.consolidation_score,
        c.recommended_action,
        c.total_clicks,
        c.total_impressions,
        c.status,
        CASE
            WHEN c.consolidation_score >= 80 THEN 'high'::TEXT
            WHEN c.consolidation_score >= 50 THEN 'medium'::TEXT
            ELSE 'low'::TEXT
        END as priority
    FROM analytics.consolidation_candidates c
    WHERE c.property = p_property
        AND (p_status IS NULL OR c.status = p_status)
        AND c.consolidation_score >= p_min_score
    ORDER BY c.consolidation_score DESC, c.total_clicks DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.get_consolidation_candidates IS 'Get consolidation candidates for a property with optional filters';

-- Function to track consolidation outcome
CREATE OR REPLACE FUNCTION analytics.track_consolidation_outcome(
    p_candidate_id INTEGER,
    p_outcome JSONB
) RETURNS BOOLEAN AS $$
DECLARE
    v_success BOOLEAN := FALSE;
BEGIN
    -- Update the most recent history record with outcome
    UPDATE analytics.consolidation_history
    SET outcome = p_outcome
    WHERE candidate_id = p_candidate_id
        AND id = (
            SELECT id
            FROM analytics.consolidation_history
            WHERE candidate_id = p_candidate_id
            ORDER BY performed_at DESC
            LIMIT 1
        );

    v_success := FOUND;
    RETURN v_success;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.track_consolidation_outcome IS 'Update the outcome of the most recent consolidation action';

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION analytics.update_consolidation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_consolidation_candidates_update ON analytics.consolidation_candidates;
CREATE TRIGGER trg_consolidation_candidates_update
    BEFORE UPDATE ON analytics.consolidation_candidates
    FOR EACH ROW
    EXECUTE FUNCTION analytics.update_consolidation_timestamp();

-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA analytics TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics.consolidation_candidates TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON analytics.consolidation_history TO gsc_user;
GRANT USAGE, SELECT ON SEQUENCE analytics.consolidation_candidates_id_seq TO gsc_user;
GRANT USAGE, SELECT ON SEQUENCE analytics.consolidation_history_id_seq TO gsc_user;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA analytics TO gsc_user;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE analytics.consolidation_candidates IS 'Stores URL consolidation opportunities with scoring and recommendations';
COMMENT ON TABLE analytics.consolidation_history IS 'Tracks actions taken on consolidation candidates';

COMMENT ON COLUMN analytics.consolidation_candidates.property IS 'Property identifier (e.g., sc-domain:example.com)';
COMMENT ON COLUMN analytics.consolidation_candidates.canonical_url IS 'The canonical URL that variations should consolidate to';
COMMENT ON COLUMN analytics.consolidation_candidates.variation_urls IS 'JSONB array of variation URLs with their performance metrics';
COMMENT ON COLUMN analytics.consolidation_candidates.variation_count IS 'Number of URL variations found';
COMMENT ON COLUMN analytics.consolidation_candidates.consolidation_score IS 'Priority score (0-100) for consolidation';
COMMENT ON COLUMN analytics.consolidation_candidates.recommended_action IS 'Recommended consolidation strategy';
COMMENT ON COLUMN analytics.consolidation_candidates.status IS 'Current status: pending, in_progress, actioned, dismissed';

COMMENT ON COLUMN analytics.consolidation_history.action_taken IS 'Type of action: redirect_implemented, canonical_added, merged, dismissed';
COMMENT ON COLUMN analytics.consolidation_history.action_details IS 'JSONB details about the action taken';
COMMENT ON COLUMN analytics.consolidation_history.outcome IS 'JSONB results of the action (traffic/ranking changes)';
