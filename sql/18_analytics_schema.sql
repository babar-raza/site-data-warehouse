-- =====================================================
-- Analytics Schema (Causal Impact Analysis)
-- =====================================================
-- Purpose: Track interventions and measure causal impact
-- Phase: 3
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- =====================================================
-- INTERVENTIONS TABLE
-- =====================================================
-- Track interventions (changes) made to pages
CREATE TABLE analytics.interventions (
    intervention_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property TEXT NOT NULL,
    page_path TEXT,  -- NULL = property-wide intervention

    -- Intervention details
    intervention_type TEXT NOT NULL,  -- content_update, technical_fix, redirect, schema_added, etc.
    intervention_date DATE NOT NULL,
    description TEXT,

    -- Context
    related_action_id UUID,  -- Link to gsc.actions if applicable
    related_pr_url TEXT,  -- Link to GitHub PR

    -- Metadata
    created_by TEXT,
    tags TEXT[],

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_interventions_property ON analytics.interventions(property);
CREATE INDEX idx_interventions_date ON analytics.interventions(intervention_date DESC);
CREATE INDEX idx_interventions_property_date ON analytics.interventions(property, intervention_date DESC);
CREATE INDEX idx_interventions_type ON analytics.interventions(intervention_type);
CREATE INDEX idx_interventions_page ON analytics.interventions(page_path);

-- Auto-update timestamp
CREATE TRIGGER update_interventions_updated_at
    BEFORE UPDATE ON analytics.interventions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE analytics.interventions IS 'Track changes/interventions made to pages';
COMMENT ON COLUMN analytics.interventions.intervention_type IS 'Type of change: content_update, technical_fix, redirect, etc.';
COMMENT ON COLUMN analytics.interventions.intervention_date IS 'Date when intervention was applied';


-- =====================================================
-- CAUSAL IMPACT TABLE
-- =====================================================
-- Store causal impact analysis results
CREATE TABLE analytics.causal_impact (
    impact_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intervention_id UUID NOT NULL REFERENCES analytics.interventions(intervention_id) ON DELETE CASCADE,

    -- Analysis parameters
    metric TEXT NOT NULL,  -- clicks, impressions, position, etc.
    pre_period_start DATE NOT NULL,
    pre_period_end DATE NOT NULL,
    post_period_start DATE NOT NULL,
    post_period_end DATE NOT NULL,

    -- Results
    absolute_effect FLOAT,  -- Actual change in metric
    relative_effect FLOAT,  -- Percentage change
    p_value FLOAT,  -- Statistical significance
    is_significant BOOLEAN,  -- p < 0.05
    confidence_level FLOAT DEFAULT 0.95,

    -- Effect bounds (95% confidence interval)
    absolute_effect_lower FLOAT,
    absolute_effect_upper FLOAT,
    relative_effect_lower FLOAT,
    relative_effect_upper FLOAT,

    -- Detailed results
    summary_data JSONB,  -- Full summary statistics
    point_predictions JSONB,  -- Daily point predictions
    cumulative_impact JSONB,  -- Cumulative impact over time

    -- Model info
    model_type TEXT DEFAULT 'bayesian_structural',
    model_params JSONB,

    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_causal_impact_intervention ON analytics.causal_impact(intervention_id);
CREATE INDEX idx_causal_impact_metric ON analytics.causal_impact(metric);
CREATE INDEX idx_causal_impact_significant ON analytics.causal_impact(is_significant) WHERE is_significant = true;
CREATE INDEX idx_causal_impact_analyzed ON analytics.causal_impact(analyzed_at DESC);

COMMENT ON TABLE analytics.causal_impact IS 'Causal impact analysis results for interventions';
COMMENT ON COLUMN analytics.causal_impact.absolute_effect IS 'Absolute change in metric (e.g., +500 clicks)';
COMMENT ON COLUMN analytics.causal_impact.relative_effect IS 'Relative change as percentage (e.g., +25%)';
COMMENT ON COLUMN analytics.causal_impact.p_value IS 'Statistical significance (p < 0.05 = significant)';
COMMENT ON COLUMN analytics.causal_impact.is_significant IS 'True if p-value < 0.05';


-- =====================================================
-- A/B TESTS TABLE (Optional - for future)
-- =====================================================
-- Track A/B tests and experiments
CREATE TABLE analytics.ab_tests (
    test_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_name TEXT NOT NULL,
    property TEXT NOT NULL,

    -- Test design
    hypothesis TEXT,
    control_group JSONB,  -- Pages in control group
    treatment_group JSONB,  -- Pages in treatment group

    -- Timeline
    start_date DATE NOT NULL,
    end_date DATE,
    status TEXT DEFAULT 'planning',  -- planning, running, completed, cancelled

    -- Results
    winner TEXT,  -- control, treatment, or inconclusive
    results JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ab_tests_property ON analytics.ab_tests(property);
CREATE INDEX idx_ab_tests_status ON analytics.ab_tests(status);
CREATE INDEX idx_ab_tests_dates ON analytics.ab_tests(start_date, end_date);

COMMENT ON TABLE analytics.ab_tests IS 'A/B testing and experimentation tracking';


-- =====================================================
-- VIEWS
-- =====================================================

-- Significant interventions
CREATE OR REPLACE VIEW analytics.vw_significant_impacts AS
SELECT
    i.intervention_id,
    i.property,
    i.page_path,
    i.intervention_type,
    i.intervention_date,
    i.description,
    ci.metric,
    ci.absolute_effect,
    ci.relative_effect,
    ci.p_value,
    ci.confidence_level,
    ci.absolute_effect_lower,
    ci.absolute_effect_upper,
    CASE
        WHEN ci.absolute_effect > 0 THEN 'positive'
        WHEN ci.absolute_effect < 0 THEN 'negative'
        ELSE 'neutral'
    END as impact_direction,
    ci.analyzed_at
FROM analytics.causal_impact ci
JOIN analytics.interventions i ON ci.intervention_id = i.intervention_id
WHERE ci.is_significant = true
ORDER BY ABS(ci.absolute_effect) DESC;

COMMENT ON VIEW analytics.vw_significant_impacts IS 'Interventions with statistically significant causal impact';


-- Recent interventions with analysis status
CREATE OR REPLACE VIEW analytics.vw_recent_interventions AS
SELECT
    i.*,
    COUNT(ci.impact_id) as analysis_count,
    MAX(ci.analyzed_at) as last_analyzed,
    BOOL_OR(ci.is_significant) as has_significant_impact,
    jsonb_agg(
        jsonb_build_object(
            'metric', ci.metric,
            'absolute_effect', ci.absolute_effect,
            'relative_effect', ci.relative_effect,
            'is_significant', ci.is_significant
        )
    ) FILTER (WHERE ci.impact_id IS NOT NULL) as impacts
FROM analytics.interventions i
LEFT JOIN analytics.causal_impact ci ON i.intervention_id = ci.intervention_id
WHERE i.intervention_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY i.intervention_id
ORDER BY i.intervention_date DESC;

COMMENT ON VIEW analytics.vw_recent_interventions IS 'Recent interventions with their analysis status';


-- Intervention ROI summary
CREATE OR REPLACE VIEW analytics.vw_intervention_roi AS
SELECT
    i.intervention_type,
    COUNT(DISTINCT i.intervention_id) as total_interventions,
    COUNT(DISTINCT ci.impact_id) FILTER (WHERE ci.is_significant = true) as significant_count,
    ROUND(100.0 * COUNT(DISTINCT ci.impact_id) FILTER (WHERE ci.is_significant = true) /
          NULLIF(COUNT(DISTINCT i.intervention_id), 0), 2) as success_rate_pct,
    AVG(ci.absolute_effect) FILTER (WHERE ci.is_significant = true AND ci.metric = 'clicks') as avg_clicks_impact,
    SUM(ci.absolute_effect) FILTER (WHERE ci.is_significant = true AND ci.metric = 'clicks') as total_clicks_impact
FROM analytics.interventions i
LEFT JOIN analytics.causal_impact ci ON i.intervention_id = ci.intervention_id
GROUP BY i.intervention_type
ORDER BY total_clicks_impact DESC NULLS LAST;

COMMENT ON VIEW analytics.vw_intervention_roi IS 'ROI summary by intervention type';


-- Best performing interventions
CREATE OR REPLACE VIEW analytics.vw_top_interventions AS
SELECT
    i.intervention_type,
    i.description,
    i.property,
    i.page_path,
    i.intervention_date,
    ci.metric,
    ci.absolute_effect,
    ci.relative_effect,
    ci.p_value,
    CASE
        WHEN ci.relative_effect > 0 AND ci.absolute_effect > 0 THEN 'win'
        WHEN ci.relative_effect < 0 AND ci.absolute_effect < 0 THEN 'loss'
        ELSE 'neutral'
    END as outcome
FROM analytics.interventions i
JOIN analytics.causal_impact ci ON i.intervention_id = ci.intervention_id
WHERE ci.is_significant = true
    AND ci.metric = 'clicks'  -- Focus on clicks
ORDER BY ci.absolute_effect DESC
LIMIT 100;

COMMENT ON VIEW analytics.vw_top_interventions IS 'Top 100 interventions by absolute clicks impact';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Function to get intervention impact summary
CREATE OR REPLACE FUNCTION analytics.get_intervention_summary(
    p_intervention_id UUID
) RETURNS TABLE (
    metric TEXT,
    absolute_effect FLOAT,
    relative_effect FLOAT,
    p_value FLOAT,
    is_significant BOOLEAN,
    confidence_interval TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.metric,
        ci.absolute_effect,
        ci.relative_effect,
        ci.p_value,
        ci.is_significant,
        FORMAT('[%s, %s]',
            ROUND(ci.absolute_effect_lower::numeric, 2),
            ROUND(ci.absolute_effect_upper::numeric, 2)
        ) as confidence_interval
    FROM analytics.causal_impact ci
    WHERE ci.intervention_id = p_intervention_id
    ORDER BY ci.metric;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.get_intervention_summary IS 'Get impact summary for an intervention';


-- Function to calculate overall intervention success rate
CREATE OR REPLACE FUNCTION analytics.calculate_success_rate(
    p_property TEXT DEFAULT NULL,
    p_days_back INT DEFAULT 365
) RETURNS TABLE (
    total_interventions BIGINT,
    analyzed_interventions BIGINT,
    significant_interventions BIGINT,
    success_rate FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH intervention_stats AS (
        SELECT
            COUNT(DISTINCT i.intervention_id) as total,
            COUNT(DISTINCT ci.intervention_id) as analyzed,
            COUNT(DISTINCT ci.intervention_id) FILTER (WHERE ci.is_significant = true) as significant
        FROM analytics.interventions i
        LEFT JOIN analytics.causal_impact ci ON i.intervention_id = ci.intervention_id
        WHERE i.intervention_date >= CURRENT_DATE - p_days_back
            AND (p_property IS NULL OR i.property = p_property)
    )
    SELECT
        total,
        analyzed,
        significant,
        CASE
            WHEN analyzed > 0 THEN ROUND(100.0 * significant / analyzed, 2)
            ELSE 0
        END
    FROM intervention_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.calculate_success_rate IS 'Calculate intervention success rate';


-- Function to get pre/post comparison
CREATE OR REPLACE FUNCTION analytics.get_pre_post_comparison(
    p_intervention_id UUID,
    p_metric TEXT DEFAULT 'clicks'
) RETURNS TABLE (
    period TEXT,
    avg_value FLOAT,
    total_value FLOAT,
    days_count INT
) AS $$
DECLARE
    v_property TEXT;
    v_page_path TEXT;
    v_intervention_date DATE;
    v_pre_start DATE;
    v_post_end DATE;
BEGIN
    -- Get intervention details
    SELECT property, page_path, intervention_date
    INTO v_property, v_page_path, v_intervention_date
    FROM analytics.interventions
    WHERE intervention_id = p_intervention_id;

    -- Calculate periods (30 days before, 30 days after)
    v_pre_start := v_intervention_date - INTERVAL '30 days';
    v_post_end := v_intervention_date + INTERVAL '30 days';

    RETURN QUERY
    SELECT
        'pre' as period,
        AVG(gsc_clicks) as avg_value,
        SUM(gsc_clicks) as total_value,
        COUNT(*)::INT as days_count
    FROM gsc.vw_unified_page_performance
    WHERE property = v_property
        AND (v_page_path IS NULL OR page_path = v_page_path)
        AND date >= v_pre_start
        AND date < v_intervention_date

    UNION ALL

    SELECT
        'post' as period,
        AVG(gsc_clicks),
        SUM(gsc_clicks),
        COUNT(*)::INT
    FROM gsc.vw_unified_page_performance
    WHERE property = v_property
        AND (v_page_path IS NULL OR page_path = v_page_path)
        AND date >= v_intervention_date
        AND date <= v_post_end;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analytics.get_pre_post_comparison IS 'Get pre/post intervention comparison';


-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA analytics TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA analytics TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA analytics TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA analytics TO gsc_user;

-- =====================================================
-- SAMPLE DATA (for testing)
-- =====================================================

-- Insert sample interventions (commented out by default)
/*
INSERT INTO analytics.interventions (property, page_path, intervention_type, intervention_date, description)
VALUES
    ('https://blog.aspose.net', '/cells/python/', 'content_update', '2025-11-01', 'Updated tutorial with new examples'),
    ('https://blog.aspose.net', '/words/python/', 'technical_fix', '2025-11-10', 'Fixed broken internal links'),
    ('https://blog.aspose.net', NULL, 'schema_added', '2025-11-15', 'Added Organization schema to all pages');
*/
