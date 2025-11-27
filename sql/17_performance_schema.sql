-- =====================================================
-- Performance Monitoring Schema (Core Web Vitals)
-- =====================================================
-- Purpose: Track Core Web Vitals and Lighthouse scores from PageSpeed Insights
-- Phase: 3
-- Dependencies: uuid-ossp extension
-- =====================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS performance;

-- =====================================================
-- CORE WEB VITALS TABLE
-- =====================================================
-- Stores Core Web Vitals metrics from PageSpeed Insights API
CREATE TABLE performance.core_web_vitals (
    cwv_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property TEXT NOT NULL,
    page_path TEXT NOT NULL,
    check_date DATE NOT NULL,
    strategy TEXT NOT NULL CHECK (strategy IN ('mobile', 'desktop')),

    -- Core Web Vitals (field data if available, otherwise lab data)
    lcp FLOAT,  -- Largest Contentful Paint (ms) - Good: <2500, Needs Improvement: 2500-4000, Poor: >4000
    fid FLOAT,  -- First Input Delay (ms) - Good: <100, Needs Improvement: 100-300, Poor: >300
    cls FLOAT,  -- Cumulative Layout Shift (score) - Good: <0.1, Needs Improvement: 0.1-0.25, Poor: >0.25
    fcp FLOAT,  -- First Contentful Paint (ms) - Good: <1800, Needs Improvement: 1800-3000, Poor: >3000
    inp FLOAT,  -- Interaction to Next Paint (ms) - Good: <200, Needs Improvement: 200-500, Poor: >500
    ttfb FLOAT,  -- Time to First Byte (ms) - Good: <800, Needs Improvement: 800-1800, Poor: >1800

    -- Lab-only metrics
    tti FLOAT,  -- Time to Interactive (ms)
    tbt FLOAT,  -- Total Blocking Time (ms)
    speed_index FLOAT,  -- Speed Index

    -- Lighthouse category scores (0-100)
    performance_score INT CHECK (performance_score BETWEEN 0 AND 100),
    accessibility_score INT CHECK (accessibility_score BETWEEN 0 AND 100),
    best_practices_score INT CHECK (best_practices_score BETWEEN 0 AND 100),
    seo_score INT CHECK (seo_score BETWEEN 0 AND 100),
    pwa_score INT CHECK (pwa_score BETWEEN 0 AND 100),

    -- CWV assessment
    cwv_assessment TEXT,  -- 'pass', 'needs_improvement', 'fail', or NULL if insufficient data

    -- Optimization opportunities
    opportunities JSONB,  -- Array of opportunities with potential savings
    diagnostics JSONB,  -- Detailed diagnostic information
    audits JSONB,  -- All audit results

    -- Metadata
    lighthouse_version TEXT,
    user_agent TEXT,
    fetch_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Raw response
    raw_response JSONB,  -- Full PageSpeed Insights response

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(property, page_path, check_date, strategy)
);

-- Indexes
CREATE INDEX idx_cwv_property ON performance.core_web_vitals(property);
CREATE INDEX idx_cwv_date ON performance.core_web_vitals(check_date DESC);
CREATE INDEX idx_cwv_property_date ON performance.core_web_vitals(property, check_date DESC);
CREATE INDEX idx_cwv_strategy ON performance.core_web_vitals(strategy);
CREATE INDEX idx_cwv_performance_score ON performance.core_web_vitals(performance_score);
CREATE INDEX idx_cwv_lcp ON performance.core_web_vitals(lcp) WHERE lcp IS NOT NULL;
CREATE INDEX idx_cwv_cls ON performance.core_web_vitals(cls) WHERE cls IS NOT NULL;
CREATE INDEX idx_cwv_assessment ON performance.core_web_vitals(cwv_assessment) WHERE cwv_assessment IS NOT NULL;

COMMENT ON TABLE performance.core_web_vitals IS 'Core Web Vitals metrics from PageSpeed Insights API';
COMMENT ON COLUMN performance.core_web_vitals.lcp IS 'Largest Contentful Paint (ms) - Good: <2500';
COMMENT ON COLUMN performance.core_web_vitals.fid IS 'First Input Delay (ms) - Good: <100';
COMMENT ON COLUMN performance.core_web_vitals.cls IS 'Cumulative Layout Shift (score) - Good: <0.1';
COMMENT ON COLUMN performance.core_web_vitals.cwv_assessment IS 'Overall CWV assessment: pass, needs_improvement, fail';


-- =====================================================
-- PERFORMANCE BUDGETS TABLE
-- =====================================================
-- Define performance budgets and thresholds for pages
CREATE TABLE performance.budgets (
    budget_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property TEXT NOT NULL,
    page_path_pattern TEXT,  -- Glob pattern or specific path
    strategy TEXT CHECK (strategy IN ('mobile', 'desktop', 'both')),

    -- Budget thresholds
    max_lcp INT,  -- Maximum acceptable LCP (ms)
    max_cls FLOAT,  -- Maximum acceptable CLS
    min_performance_score INT,  -- Minimum Lighthouse performance score

    -- Alerts
    alert_on_failure BOOLEAN DEFAULT true,
    alert_recipients TEXT[],

    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_budgets_property ON performance.budgets(property);
CREATE INDEX idx_budgets_active ON performance.budgets(is_active) WHERE is_active = true;

COMMENT ON TABLE performance.budgets IS 'Performance budgets and alert thresholds';


-- =====================================================
-- PERFORMANCE ALERTS TABLE
-- =====================================================
-- Track performance budget violations
CREATE TABLE performance.alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    budget_id UUID REFERENCES performance.budgets(budget_id),
    cwv_id UUID REFERENCES performance.core_web_vitals(cwv_id),

    property TEXT NOT NULL,
    page_path TEXT NOT NULL,
    check_date DATE NOT NULL,
    strategy TEXT NOT NULL,

    -- Violation details
    violation_type TEXT NOT NULL,  -- lcp, cls, performance_score, etc.
    threshold_value FLOAT,  -- What was the threshold
    actual_value FLOAT,  -- What was the actual value
    severity TEXT,  -- low, medium, high

    -- Status
    status TEXT DEFAULT 'open',  -- open, investigating, resolved
    resolved_at TIMESTAMP,
    resolution_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_property ON performance.alerts(property);
CREATE INDEX idx_alerts_date ON performance.alerts(check_date DESC);
CREATE INDEX idx_alerts_status ON performance.alerts(status) WHERE status = 'open';

COMMENT ON TABLE performance.alerts IS 'Performance budget violation alerts';


-- =====================================================
-- VIEWS
-- =====================================================

-- Current CWV scores with trends
CREATE OR REPLACE VIEW performance.vw_cwv_current AS
WITH latest AS (
    SELECT DISTINCT ON (property, page_path, strategy)
        *
    FROM performance.core_web_vitals
    ORDER BY property, page_path, strategy, check_date DESC
),
previous AS (
    SELECT DISTINCT ON (property, page_path, strategy)
        property,
        page_path,
        strategy,
        check_date as prev_check_date,
        performance_score as prev_performance_score,
        lcp as prev_lcp,
        cls as prev_cls
    FROM performance.core_web_vitals cwv
    WHERE check_date < (
        SELECT MAX(check_date)
        FROM performance.core_web_vitals
        WHERE property = cwv.property
            AND page_path = cwv.page_path
            AND strategy = cwv.strategy
    )
    ORDER BY property, page_path, strategy, check_date DESC
)
SELECT
    l.property,
    l.page_path,
    l.strategy,
    l.check_date,
    l.performance_score,
    l.lcp,
    l.fid,
    l.cls,
    l.fcp,
    l.ttfb,
    l.cwv_assessment,
    p.prev_performance_score,
    l.performance_score - p.prev_performance_score as score_change,
    p.prev_lcp,
    l.lcp - p.prev_lcp as lcp_change,
    p.prev_cls,
    l.cls - p.prev_cls as cls_change,
    p.prev_check_date,
    l.opportunities,
    l.fetch_time
FROM latest l
LEFT JOIN previous p
    ON l.property = p.property
    AND l.page_path = p.page_path
    AND l.strategy = p.strategy;

COMMENT ON VIEW performance.vw_cwv_current IS 'Current CWV scores with change tracking';


-- Poor performing pages
CREATE OR REPLACE VIEW performance.vw_poor_cwv AS
SELECT
    property,
    page_path,
    strategy,
    check_date,
    performance_score,
    lcp,
    fid,
    cls,
    cwv_assessment,
    CASE
        WHEN performance_score < 50 THEN 'poor'
        WHEN performance_score BETWEEN 50 AND 89 THEN 'needs_improvement'
        ELSE 'good'
    END as performance_category,
    CASE
        WHEN lcp > 4000 THEN 'poor'
        WHEN lcp > 2500 THEN 'needs_improvement'
        ELSE 'good'
    END as lcp_category,
    CASE
        WHEN cls > 0.25 THEN 'poor'
        WHEN cls > 0.1 THEN 'needs_improvement'
        ELSE 'good'
    END as cls_category
FROM performance.core_web_vitals
WHERE check_date = (SELECT MAX(check_date) FROM performance.core_web_vitals)
    AND (
        performance_score < 90
        OR lcp > 2500
        OR cls > 0.1
        OR fid > 100
    )
ORDER BY performance_score ASC, lcp DESC;

COMMENT ON VIEW performance.vw_poor_cwv IS 'Pages with poor Core Web Vitals scores';


-- CWV trends over time
CREATE OR REPLACE VIEW performance.vw_cwv_trends AS
SELECT
    property,
    page_path,
    strategy,
    check_date,
    performance_score,
    lcp,
    cls,
    AVG(performance_score) OVER (
        PARTITION BY property, page_path, strategy
        ORDER BY check_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as performance_score_7day_avg,
    AVG(lcp) OVER (
        PARTITION BY property, page_path, strategy
        ORDER BY check_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as lcp_7day_avg,
    AVG(cls) OVER (
        PARTITION BY property, page_path, strategy
        ORDER BY check_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as cls_7day_avg
FROM performance.core_web_vitals
WHERE check_date >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY property, page_path, strategy, check_date DESC;

COMMENT ON VIEW performance.vw_cwv_trends IS 'CWV trends with moving averages';


-- Performance summary by property
CREATE OR REPLACE VIEW performance.vw_performance_summary AS
WITH latest AS (
    SELECT DISTINCT ON (property, page_path, strategy)
        property,
        page_path,
        strategy,
        performance_score,
        lcp,
        cls,
        cwv_assessment
    FROM performance.core_web_vitals
    ORDER BY property, page_path, strategy, check_date DESC
)
SELECT
    property,
    strategy,
    COUNT(*) as pages_monitored,
    ROUND(AVG(performance_score), 2) as avg_performance_score,
    ROUND(AVG(lcp), 0) as avg_lcp,
    ROUND(AVG(cls), 3) as avg_cls,
    COUNT(*) FILTER (WHERE performance_score >= 90) as good_pages,
    COUNT(*) FILTER (WHERE performance_score BETWEEN 50 AND 89) as needs_improvement_pages,
    COUNT(*) FILTER (WHERE performance_score < 50) as poor_pages,
    ROUND(100.0 * COUNT(*) FILTER (WHERE performance_score >= 90) / NULLIF(COUNT(*), 0), 2) as pct_good,
    COUNT(*) FILTER (WHERE cwv_assessment = 'pass') as cwv_pass_count,
    ROUND(100.0 * COUNT(*) FILTER (WHERE cwv_assessment = 'pass') / NULLIF(COUNT(*), 0), 2) as cwv_pass_rate
FROM latest
GROUP BY property, strategy;

COMMENT ON VIEW performance.vw_performance_summary IS 'Performance summary by property and strategy';


-- Top opportunities across all pages
CREATE OR REPLACE VIEW performance.vw_top_opportunities AS
SELECT
    property,
    page_path,
    strategy,
    check_date,
    jsonb_array_elements(opportunities) as opportunity
FROM performance.core_web_vitals
WHERE check_date = (SELECT MAX(check_date) FROM performance.core_web_vitals)
    AND opportunities IS NOT NULL
ORDER BY
    (jsonb_array_elements(opportunities)->>'overallSavingsMs')::FLOAT DESC NULLS LAST
LIMIT 100;

COMMENT ON VIEW performance.vw_top_opportunities IS 'Top optimization opportunities sorted by potential savings';


-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Calculate CWV assessment
CREATE OR REPLACE FUNCTION performance.calculate_cwv_assessment(
    p_lcp FLOAT,
    p_fid FLOAT,
    p_cls FLOAT
) RETURNS TEXT AS $$
BEGIN
    -- Need all three metrics to assess
    IF p_lcp IS NULL OR p_fid IS NULL OR p_cls IS NULL THEN
        RETURN NULL;
    END IF;

    -- All three must be "good" for overall pass
    IF p_lcp <= 2500 AND p_fid <= 100 AND p_cls <= 0.1 THEN
        RETURN 'pass';
    END IF;

    -- If any metric is "poor", overall is fail
    IF p_lcp > 4000 OR p_fid > 300 OR p_cls > 0.25 THEN
        RETURN 'fail';
    END IF;

    -- Otherwise needs improvement
    RETURN 'needs_improvement';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION performance.calculate_cwv_assessment IS 'Calculate overall CWV assessment from individual metrics';


-- Get CWV improvements
CREATE OR REPLACE FUNCTION performance.get_cwv_improvements(
    p_property TEXT,
    p_days_back INT DEFAULT 30
) RETURNS TABLE (
    page_path TEXT,
    strategy TEXT,
    old_score INT,
    new_score INT,
    score_improvement INT,
    old_lcp FLOAT,
    new_lcp FLOAT,
    lcp_improvement FLOAT
) AS $$
BEGIN
    RETURN QUERY
    WITH current AS (
        SELECT DISTINCT ON (property, page_path, strategy)
            property,
            page_path as curr_page,
            strategy as curr_strategy,
            performance_score as curr_score,
            lcp as curr_lcp,
            check_date
        FROM performance.core_web_vitals
        WHERE property = p_property
        ORDER BY property, page_path, strategy, check_date DESC
    ),
    past AS (
        SELECT DISTINCT ON (property, page_path, strategy)
            property,
            page_path as past_page,
            strategy as past_strategy,
            performance_score as past_score,
            lcp as past_lcp
        FROM performance.core_web_vitals
        WHERE property = p_property
            AND check_date <= CURRENT_DATE - p_days_back
        ORDER BY property, page_path, strategy, check_date DESC
    )
    SELECT
        c.curr_page,
        c.curr_strategy,
        p.past_score,
        c.curr_score,
        c.curr_score - p.past_score,
        p.past_lcp,
        c.curr_lcp,
        p.past_lcp - c.curr_lcp  -- Positive = improvement (lower is better)
    FROM current c
    JOIN past p
        ON c.property = p.property
        AND c.curr_page = p.past_page
        AND c.curr_strategy = p.past_strategy
    WHERE c.curr_score > p.past_score  -- Only improvements
    ORDER BY (c.curr_score - p.past_score) DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION performance.get_cwv_improvements IS 'Get pages with CWV score improvements over time';


-- =====================================================
-- GRANTS
-- =====================================================

-- Grant permissions to gsc_user
GRANT USAGE ON SCHEMA performance TO gsc_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA performance TO gsc_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA performance TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA performance TO gsc_user;

-- =====================================================
-- SAMPLE DATA (for testing)
-- =====================================================

-- Insert sample budget (commented out by default)
/*
INSERT INTO performance.budgets (property, page_path_pattern, strategy, max_lcp, max_cls, min_performance_score)
VALUES
    ('https://blog.aspose.net', '/*', 'both', 2500, 0.1, 90);
*/
