-- =============================================
-- INSIGHT AGGREGATION VIEWS
-- =============================================
-- Provides aggregated views of insights for dashboards and reporting
-- These views power the aggregation API endpoints
--
-- Views created:
-- 1. vw_insights_by_page - Insights grouped by page path
-- 2. vw_insights_by_subdomain - Insights grouped by subdomain
-- 3. vw_insights_by_category - Insights grouped by category
-- 4. vw_insights_dashboard - Dashboard summary statistics
-- 5. vw_insights_timeseries - Time series data for charting
-- 6. vw_top_issues - Top priority issues requiring attention
--
-- Migration safety: Idempotent (CREATE OR REPLACE), can run multiple times
-- =============================================

SET search_path TO gsc, public;

-- =============================================
-- VIEW 1: INSIGHTS BY PAGE
-- =============================================
-- Groups insights by individual page paths with full breakdowns

CREATE OR REPLACE VIEW gsc.vw_insights_by_page AS
SELECT
    property,
    entity_id as page_path,
    COUNT(*) as total_insights,
    COUNT(*) FILTER (WHERE category = 'risk') as risk_count,
    COUNT(*) FILTER (WHERE category = 'opportunity') as opportunity_count,
    COUNT(*) FILTER (WHERE category = 'trend') as trend_count,
    COUNT(*) FILTER (WHERE category = 'diagnosis') as diagnosis_count,
    COUNT(*) FILTER (WHERE severity = 'high') as high_severity_count,
    COUNT(*) FILTER (WHERE severity = 'medium') as medium_severity_count,
    COUNT(*) FILTER (WHERE severity = 'low') as low_severity_count,
    COUNT(*) FILTER (WHERE status = 'new') as new_count,
    COUNT(*) FILTER (WHERE status = 'actioned') as actioned_count,
    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
    MAX(generated_at) as latest_insight,
    MIN(generated_at) as earliest_insight,
    AVG(confidence) as avg_confidence
FROM gsc.insights
WHERE entity_type = 'page'
GROUP BY property, entity_id;

COMMENT ON VIEW gsc.vw_insights_by_page IS
'Aggregates insights by individual page paths. Includes counts by category, severity, and status. Used for page-level dashboards.';


-- =============================================
-- VIEW 2: INSIGHTS BY SUBDOMAIN
-- =============================================
-- Groups insights by subdomain/directory extracted from entity_id

CREATE OR REPLACE VIEW gsc.vw_insights_by_subdomain AS
SELECT
    property,
    CASE
        WHEN entity_id LIKE '/%' THEN 'root'
        ELSE SPLIT_PART(REPLACE(REPLACE(entity_id, 'https://', ''), 'http://', ''), '/', 1)
    END as subdomain,
    COUNT(*) as total_insights,
    COUNT(*) FILTER (WHERE category = 'risk') as risk_count,
    COUNT(*) FILTER (WHERE category = 'opportunity') as opportunity_count,
    COUNT(*) FILTER (WHERE category = 'trend') as trend_count,
    COUNT(*) FILTER (WHERE category = 'diagnosis') as diagnosis_count,
    COUNT(*) FILTER (WHERE severity = 'high') as high_severity_count,
    COUNT(*) FILTER (WHERE severity = 'medium') as medium_severity_count,
    COUNT(*) FILTER (WHERE severity = 'low') as low_severity_count,
    COUNT(DISTINCT entity_id) as unique_pages,
    MAX(generated_at) as latest_insight
FROM gsc.insights
WHERE entity_type IN ('page', 'directory')
GROUP BY property,
    CASE
        WHEN entity_id LIKE '/%' THEN 'root'
        ELSE SPLIT_PART(REPLACE(REPLACE(entity_id, 'https://', ''), 'http://', ''), '/', 1)
    END;

COMMENT ON VIEW gsc.vw_insights_by_subdomain IS
'Aggregates insights by subdomain or directory. Helps identify which site sections have most issues.';


-- =============================================
-- VIEW 3: INSIGHTS BY CATEGORY
-- =============================================
-- Groups insights by category (risk, opportunity, trend, diagnosis)

CREATE OR REPLACE VIEW gsc.vw_insights_by_category AS
SELECT
    property,
    category,
    COUNT(*) as total_insights,
    COUNT(*) FILTER (WHERE severity = 'high') as high_severity_count,
    COUNT(*) FILTER (WHERE severity = 'medium') as medium_severity_count,
    COUNT(*) FILTER (WHERE severity = 'low') as low_severity_count,
    COUNT(*) FILTER (WHERE status = 'new') as new_count,
    COUNT(*) FILTER (WHERE status = 'investigating') as investigating_count,
    COUNT(*) FILTER (WHERE status = 'diagnosed') as diagnosed_count,
    COUNT(*) FILTER (WHERE status = 'actioned') as actioned_count,
    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_count,
    COUNT(DISTINCT entity_id) as unique_entities,
    COUNT(DISTINCT source) as unique_sources,
    AVG(confidence) as avg_confidence,
    MAX(generated_at) as latest_insight,
    MIN(generated_at) as earliest_insight
FROM gsc.insights
GROUP BY property, category;

COMMENT ON VIEW gsc.vw_insights_by_category IS
'Aggregates insights by category with detailed severity and status breakdowns. Used for category-specific analysis.';


-- =============================================
-- VIEW 4: INSIGHTS DASHBOARD SUMMARY
-- =============================================
-- Comprehensive summary for dashboard overview

CREATE OR REPLACE VIEW gsc.vw_insights_dashboard AS
SELECT
    property,
    COUNT(*) as total_insights,
    COUNT(*) FILTER (WHERE category = 'risk') as total_risks,
    COUNT(*) FILTER (WHERE category = 'opportunity') as total_opportunities,
    COUNT(*) FILTER (WHERE category = 'trend') as total_trends,
    COUNT(*) FILTER (WHERE category = 'diagnosis') as total_diagnoses,
    COUNT(*) FILTER (WHERE severity = 'high') as high_severity_total,
    COUNT(*) FILTER (WHERE severity = 'high' AND status = 'new') as high_severity_new,
    COUNT(*) FILTER (WHERE status = 'new') as new_insights,
    COUNT(*) FILTER (WHERE status = 'actioned') as actioned_insights,
    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_insights,
    COUNT(DISTINCT entity_id) as unique_entities,
    ROUND(AVG(confidence)::numeric, 3) as avg_confidence,
    MAX(generated_at) as last_insight_time,
    COUNT(*) FILTER (WHERE generated_at >= CURRENT_DATE - INTERVAL '1 day') as insights_last_24h,
    COUNT(*) FILTER (WHERE generated_at >= CURRENT_DATE - INTERVAL '7 days') as insights_last_7d,
    COUNT(*) FILTER (WHERE generated_at >= CURRENT_DATE - INTERVAL '30 days') as insights_last_30d
FROM gsc.insights
GROUP BY property;

COMMENT ON VIEW gsc.vw_insights_dashboard IS
'Dashboard summary providing high-level statistics including totals, severity breakdown, and time-based metrics.';


-- =============================================
-- VIEW 5: INSIGHTS TIME SERIES
-- =============================================
-- Daily time series data for charting (last 90 days)

CREATE OR REPLACE VIEW gsc.vw_insights_timeseries AS
SELECT
    property,
    DATE_TRUNC('day', generated_at)::date as date,
    category,
    COUNT(*) as insight_count,
    COUNT(*) FILTER (WHERE severity = 'high') as high_count,
    COUNT(*) FILTER (WHERE severity = 'medium') as medium_count,
    COUNT(*) FILTER (WHERE severity = 'low') as low_count
FROM gsc.insights
WHERE generated_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY property, DATE_TRUNC('day', generated_at)::date, category
ORDER BY date DESC;

COMMENT ON VIEW gsc.vw_insights_timeseries IS
'Daily time series of insights for the last 90 days. Used for trend charts and historical analysis.';


-- =============================================
-- VIEW 6: TOP ISSUES (PRIORITY LIST)
-- =============================================
-- Top priority issues requiring attention, sorted by priority score

CREATE OR REPLACE VIEW gsc.vw_top_issues AS
SELECT
    i.id,
    i.property,
    i.entity_type,
    i.entity_id,
    i.category,
    i.title,
    i.severity,
    i.confidence,
    i.status,
    i.generated_at,
    i.source,
    -- Priority score calculation: severity weight * confidence
    CASE
        WHEN i.severity = 'high' THEN 100
        WHEN i.severity = 'medium' THEN 50
        ELSE 10
    END * i.confidence as priority_score
FROM gsc.insights i
WHERE i.status IN ('new', 'investigating')
ORDER BY priority_score DESC, generated_at DESC;

COMMENT ON VIEW gsc.vw_top_issues IS
'Top priority issues (new or investigating status) sorted by priority score (severity * confidence). Used for prioritized action lists.';


-- =============================================
-- PERFORMANCE INDEXES
-- =============================================
-- Additional indexes to optimize view queries

-- Composite index for page aggregation
CREATE INDEX IF NOT EXISTS idx_insights_property_entity ON gsc.insights(property, entity_type, entity_id);

-- Composite index for category/severity filtering
CREATE INDEX IF NOT EXISTS idx_insights_category_severity ON gsc.insights(category, severity);

-- Index for time-based queries (DESC for recent-first queries)
CREATE INDEX IF NOT EXISTS idx_insights_generated_at ON gsc.insights(generated_at DESC);

-- Index for status filtering (commonly used in top issues)
CREATE INDEX IF NOT EXISTS idx_insights_status ON gsc.insights(status);

-- Partial index for time series queries (last 90 days)
CREATE INDEX IF NOT EXISTS idx_insights_timeseries
    ON gsc.insights(generated_at, category, severity)
    WHERE generated_at >= CURRENT_DATE - INTERVAL '90 days';


-- =============================================
-- PERMISSIONS
-- =============================================

GRANT SELECT ON gsc.vw_insights_by_page TO gsc_user;
GRANT SELECT ON gsc.vw_insights_by_subdomain TO gsc_user;
GRANT SELECT ON gsc.vw_insights_by_category TO gsc_user;
GRANT SELECT ON gsc.vw_insights_dashboard TO gsc_user;
GRANT SELECT ON gsc.vw_insights_timeseries TO gsc_user;
GRANT SELECT ON gsc.vw_top_issues TO gsc_user;


-- =============================================
-- VALIDATION FUNCTION
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_aggregation_views()
RETURNS TABLE(
    view_name TEXT,
    status TEXT,
    row_count BIGINT,
    message TEXT
) AS $$
BEGIN
    -- Check view 1: by_page
    RETURN QUERY
    SELECT
        'vw_insights_by_page'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::BIGINT,
        'Insights aggregated by page'::TEXT
    FROM gsc.vw_insights_by_page;

    -- Check view 2: by_subdomain
    RETURN QUERY
    SELECT
        'vw_insights_by_subdomain'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::BIGINT,
        'Insights aggregated by subdomain'::TEXT
    FROM gsc.vw_insights_by_subdomain;

    -- Check view 3: by_category
    RETURN QUERY
    SELECT
        'vw_insights_by_category'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::BIGINT,
        'Insights aggregated by category'::TEXT
    FROM gsc.vw_insights_by_category;

    -- Check view 4: dashboard
    RETURN QUERY
    SELECT
        'vw_insights_dashboard'::TEXT,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::BIGINT,
        'Dashboard summary statistics'::TEXT
    FROM gsc.vw_insights_dashboard;

    -- Check view 5: timeseries
    RETURN QUERY
    SELECT
        'vw_insights_timeseries'::TEXT,
        'INFO'::TEXT,
        COUNT(*)::BIGINT,
        'Time series data points (last 90 days)'::TEXT
    FROM gsc.vw_insights_timeseries;

    -- Check view 6: top_issues
    RETURN QUERY
    SELECT
        'vw_top_issues'::TEXT,
        'INFO'::TEXT,
        COUNT(*)::BIGINT,
        'Top priority issues (new/investigating)'::TEXT
    FROM gsc.vw_top_issues;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION gsc.validate_aggregation_views() IS
'Validates that all aggregation views are functioning correctly and returns row counts.';

GRANT EXECUTE ON FUNCTION gsc.validate_aggregation_views() TO gsc_user;


-- =============================================
-- INITIALIZATION
-- =============================================

-- Analyze table to ensure statistics are up to date for view performance
ANALYZE gsc.insights;

-- Success notification
DO $$
BEGIN
    RAISE NOTICE '✓ Insight aggregation views created successfully';
    RAISE NOTICE '✓ Views: by_page, by_subdomain, by_category, dashboard, timeseries, top_issues';
    RAISE NOTICE '✓ Run: SELECT * FROM gsc.validate_aggregation_views() to verify';
    RAISE NOTICE '✓ Performance indexes created for optimal query performance';
END $$;
