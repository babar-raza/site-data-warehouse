-- Materialized Views for Unified Page Performance
-- Pre-calculated aggregations for fast query performance

SET search_path TO gsc, public;

-- Drop existing materialized views if exist
DROP MATERIALIZED VIEW IF EXISTS gsc.mv_unified_page_performance CASCADE;
DROP MATERIALIZED VIEW IF EXISTS gsc.mv_unified_page_performance_weekly CASCADE;
DROP MATERIALIZED VIEW IF EXISTS gsc.mv_unified_page_performance_monthly CASCADE;

-- =============================================
-- Daily Materialized View
-- =============================================

CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance AS
SELECT 
    date,
    property,
    page_path,
    -- Current metrics
    clicks,
    impressions,
    ctr,
    avg_position,
    sessions,
    engagement_rate,
    bounce_rate,
    conversions,
    avg_session_duration,
    page_views,
    -- Historical values
    gsc_clicks_7d_ago,
    gsc_impressions_7d_ago,
    gsc_position_7d_ago,
    ga_conversions_7d_ago,
    ga_engagement_rate_7d_ago,
    gsc_clicks_28d_ago,
    gsc_impressions_28d_ago,
    ga_conversions_28d_ago,
    -- Rolling averages
    gsc_clicks_7d_avg,
    gsc_impressions_7d_avg,
    ga_conversions_7d_avg,
    gsc_clicks_28d_avg,
    gsc_impressions_28d_avg,
    ga_conversions_28d_avg,
    -- WoW changes (NEW)
    gsc_clicks_change_wow,
    gsc_impressions_change_wow,
    gsc_position_change_wow,
    ga_conversions_change_wow,
    ga_engagement_rate_change_wow,
    -- MoM changes (NEW)
    gsc_clicks_change_mom,
    gsc_impressions_change_mom,
    ga_conversions_change_mom,
    -- Composite metrics
    search_to_conversion_rate,
    session_conversion_rate,
    performance_score,
    opportunity_index,
    conversion_efficiency,
    quality_score,
    -- Metadata
    CURRENT_TIMESTAMP as last_refreshed
FROM gsc.vw_unified_page_performance;

-- Create indexes on materialized view
CREATE INDEX idx_mv_unified_date ON gsc.mv_unified_page_performance(date DESC);
CREATE INDEX idx_mv_unified_property ON gsc.mv_unified_page_performance(property);
CREATE INDEX idx_mv_unified_page_path ON gsc.mv_unified_page_performance(page_path);
CREATE INDEX idx_mv_unified_date_property ON gsc.mv_unified_page_performance(date DESC, property);
CREATE INDEX idx_mv_unified_performance_score ON gsc.mv_unified_page_performance(performance_score DESC);
CREATE INDEX idx_mv_unified_opportunity ON gsc.mv_unified_page_performance(opportunity_index DESC) WHERE opportunity_index > 0;

-- Index on WoW changes for fast anomaly queries
CREATE INDEX idx_mv_unified_wow_clicks ON gsc.mv_unified_page_performance(gsc_clicks_change_wow) 
    WHERE gsc_clicks_change_wow IS NOT NULL;
CREATE INDEX idx_mv_unified_wow_conversions ON gsc.mv_unified_page_performance(ga_conversions_change_wow) 
    WHERE ga_conversions_change_wow IS NOT NULL;

-- =============================================
-- Weekly Aggregated Materialized View
-- =============================================

CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance_weekly AS
SELECT 
    DATE_TRUNC('week', date)::DATE as week_start,
    property,
    page_path,
    -- Aggregated GSC metrics
    SUM(clicks) as total_clicks,
    SUM(impressions) as total_impressions,
    ROUND(AVG(ctr), 2) as avg_ctr,
    ROUND(AVG(avg_position), 2) as avg_position,
    -- Aggregated GA4 metrics
    SUM(sessions) as total_sessions,
    ROUND(AVG(engagement_rate), 4) as avg_engagement_rate,
    ROUND(AVG(bounce_rate), 4) as avg_bounce_rate,
    SUM(conversions) as total_conversions,
    ROUND(AVG(avg_session_duration), 2) as avg_session_duration,
    SUM(page_views) as total_page_views,
    -- Calculated weekly metrics
    CASE 
        WHEN SUM(clicks) > 0 THEN 
            ROUND((SUM(conversions)::NUMERIC / SUM(clicks)) * 100, 2)
        ELSE 0 
    END as weekly_search_to_conversion_rate,
    ROUND(AVG(performance_score), 4) as avg_performance_score,
    ROUND(AVG(opportunity_index), 2) as avg_opportunity_index,
    COUNT(*) as days_in_week,
    CURRENT_TIMESTAMP as last_refreshed
FROM gsc.mv_unified_page_performance
GROUP BY DATE_TRUNC('week', date), property, page_path;

-- Create indexes on weekly materialized view
CREATE INDEX idx_mv_unified_weekly_week ON gsc.mv_unified_page_performance_weekly(week_start DESC);
CREATE INDEX idx_mv_unified_weekly_property ON gsc.mv_unified_page_performance_weekly(property);
CREATE INDEX idx_mv_unified_weekly_page_path ON gsc.mv_unified_page_performance_weekly(page_path);

-- =============================================
-- Monthly Aggregated Materialized View
-- =============================================

CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance_monthly AS
SELECT 
    DATE_TRUNC('month', date)::DATE as month_start,
    property,
    page_path,
    -- Aggregated GSC metrics
    SUM(clicks) as total_clicks,
    SUM(impressions) as total_impressions,
    ROUND(AVG(ctr), 2) as avg_ctr,
    ROUND(AVG(avg_position), 2) as avg_position,
    -- Aggregated GA4 metrics
    SUM(sessions) as total_sessions,
    ROUND(AVG(engagement_rate), 4) as avg_engagement_rate,
    ROUND(AVG(bounce_rate), 4) as avg_bounce_rate,
    SUM(conversions) as total_conversions,
    ROUND(AVG(avg_session_duration), 2) as avg_session_duration,
    SUM(page_views) as total_page_views,
    -- Calculated monthly metrics
    CASE 
        WHEN SUM(clicks) > 0 THEN 
            ROUND((SUM(conversions)::NUMERIC / SUM(clicks)) * 100, 2)
        ELSE 0 
    END as monthly_search_to_conversion_rate,
    ROUND(AVG(performance_score), 4) as avg_performance_score,
    ROUND(AVG(opportunity_index), 2) as avg_opportunity_index,
    COUNT(*) as days_in_month,
    CURRENT_TIMESTAMP as last_refreshed
FROM gsc.mv_unified_page_performance
GROUP BY DATE_TRUNC('month', date), property, page_path;

-- Create indexes on monthly materialized view
CREATE INDEX idx_mv_unified_monthly_month ON gsc.mv_unified_page_performance_monthly(month_start DESC);
CREATE INDEX idx_mv_unified_monthly_property ON gsc.mv_unified_page_performance_monthly(property);
CREATE INDEX idx_mv_unified_monthly_page_path ON gsc.mv_unified_page_performance_monthly(page_path);

-- =============================================
-- Refresh Functions
-- =============================================

-- Function to refresh daily materialized view
CREATE OR REPLACE FUNCTION gsc.refresh_mv_unified_daily()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance;
    
    -- Update watermark
    INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status, last_run_at)
    VALUES ('mv_unified_daily', 'mv', CURRENT_DATE, 'success', CURRENT_TIMESTAMP)
    ON CONFLICT (property, source_type) 
    DO UPDATE SET 
        last_date = EXCLUDED.last_date,
        last_run_status = EXCLUDED.last_run_status,
        last_run_at = EXCLUDED.last_run_at,
        updated_at = CURRENT_TIMESTAMP;
        
    RAISE NOTICE '✓ Materialized view refreshed with time-series fields';
END;
$$ LANGUAGE plpgsql;

-- Function to refresh weekly materialized view
CREATE OR REPLACE FUNCTION gsc.refresh_mv_unified_weekly()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance_weekly;
    
    -- Update watermark
    INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status, last_run_at)
    VALUES ('mv_unified_weekly', 'mv', CURRENT_DATE, 'success', CURRENT_TIMESTAMP)
    ON CONFLICT (property, source_type) 
    DO UPDATE SET 
        last_date = EXCLUDED.last_date,
        last_run_status = EXCLUDED.last_run_status,
        last_run_at = EXCLUDED.last_run_at,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh monthly materialized view
CREATE OR REPLACE FUNCTION gsc.refresh_mv_unified_monthly()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance_monthly;
    
    -- Update watermark
    INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status, last_run_at)
    VALUES ('mv_unified_monthly', 'mv', CURRENT_DATE, 'success', CURRENT_TIMESTAMP)
    ON CONFLICT (property, source_type) 
    DO UPDATE SET 
        last_date = EXCLUDED.last_date,
        last_run_status = EXCLUDED.last_run_status,
        last_run_at = EXCLUDED.last_run_at,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh all unified materialized views
CREATE OR REPLACE FUNCTION gsc.refresh_all_unified_views()
RETURNS TABLE(view_name TEXT, status TEXT, refresh_time INTERVAL) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
BEGIN
    -- Refresh daily view
    start_time := clock_timestamp();
    BEGIN
        PERFORM gsc.refresh_mv_unified_daily();
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance';
        status := 'success';
        refresh_time := end_time - start_time;
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance';
        status := 'failed: ' || SQLERRM;
        refresh_time := end_time - start_time;
        RETURN NEXT;
    END;
    
    -- Refresh weekly view
    start_time := clock_timestamp();
    BEGIN
        PERFORM gsc.refresh_mv_unified_weekly();
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance_weekly';
        status := 'success';
        refresh_time := end_time - start_time;
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance_weekly';
        status := 'failed: ' || SQLERRM;
        refresh_time := end_time - start_time;
        RETURN NEXT;
    END;
    
    -- Refresh monthly view
    start_time := clock_timestamp();
    BEGIN
        PERFORM gsc.refresh_mv_unified_monthly();
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance_monthly';
        status := 'success';
        refresh_time := end_time - start_time;
        RETURN NEXT;
    EXCEPTION WHEN OTHERS THEN
        end_time := clock_timestamp();
        view_name := 'mv_unified_page_performance_monthly';
        status := 'failed: ' || SQLERRM;
        refresh_time := end_time - start_time;
        RETURN NEXT;
    END;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Data Quality Validation Functions
-- =============================================

-- Function to validate unified view data quality
CREATE OR REPLACE FUNCTION gsc.validate_unified_view_quality()
RETURNS TABLE(
    check_name TEXT,
    check_status TEXT,
    check_value TEXT,
    check_message TEXT
) AS $$
BEGIN
    -- Check 1: Row count consistency
    RETURN QUERY
    SELECT 
        'row_count'::TEXT as check_name,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END::TEXT as check_status,
        COUNT(*)::TEXT as check_value,
        'Rows in unified view'::TEXT as check_message
    FROM gsc.vw_unified_page_performance;
    
    -- Check 2: Recent data availability (last 7 days)
    RETURN QUERY
    SELECT 
        'recent_data'::TEXT as check_name,
        CASE WHEN COUNT(*) > 0 THEN 'PASS' ELSE 'FAIL' END::TEXT as check_status,
        COUNT(*)::TEXT as check_value,
        'Rows in last 7 days'::TEXT as check_message
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days';
    
    -- Check 3: Null property check
    RETURN QUERY
    SELECT 
        'null_properties'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT as check_status,
        COUNT(*)::TEXT as check_value,
        'Rows with null properties'::TEXT as check_message
    FROM gsc.vw_unified_page_performance
    WHERE property IS NULL;
    
    -- Check 4: Invalid CTR check
    RETURN QUERY
    SELECT 
        'invalid_ctr'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT as check_status,
        COUNT(*)::TEXT as check_value,
        'Rows with CTR > 100'::TEXT as check_message
    FROM gsc.vw_unified_page_performance
    WHERE ctr > 100;
    
    -- Check 5: Performance score range check
    RETURN QUERY
    SELECT 
        'performance_score_range'::TEXT as check_name,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT as check_status,
        COUNT(*)::TEXT as check_value,
        'Rows with performance_score outside 0-1 range'::TEXT as check_message
    FROM gsc.vw_unified_page_performance
    WHERE performance_score < 0 OR performance_score > 1;
    
    -- Check 6: Materialized view freshness (should be refreshed today)
    RETURN QUERY
    SELECT 
        'mv_freshness'::TEXT as check_name,
        CASE 
            WHEN MAX(last_refreshed)::DATE = CURRENT_DATE THEN 'PASS'
            WHEN MAX(last_refreshed)::DATE = CURRENT_DATE - 1 THEN 'WARN'
            ELSE 'FAIL'
        END::TEXT as check_status,
        MAX(last_refreshed)::TEXT as check_value,
        'Last materialized view refresh'::TEXT as check_message
    FROM gsc.mv_unified_page_performance;
    
    -- Check 7: Join completeness (both GSC and GA4 data present)
    RETURN QUERY
    SELECT 
        'join_completeness'::TEXT as check_name,
        CASE 
            WHEN COUNT(*) FILTER (WHERE clicks > 0 AND sessions > 0)::NUMERIC / NULLIF(COUNT(*), 0) > 0.5 
            THEN 'PASS' 
            ELSE 'WARN' 
        END::TEXT as check_status,
        ROUND(COUNT(*) FILTER (WHERE clicks > 0 AND sessions > 0)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2)::TEXT || '%' as check_value,
        'Percentage of rows with both GSC and GA4 data'::TEXT as check_message
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON gsc.mv_unified_page_performance TO gsc_user;
GRANT SELECT ON gsc.mv_unified_page_performance_weekly TO gsc_user;
GRANT SELECT ON gsc.mv_unified_page_performance_monthly TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.refresh_mv_unified_daily() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.refresh_mv_unified_weekly() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.refresh_mv_unified_monthly() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.refresh_all_unified_views() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_unified_view_quality() TO gsc_user;

-- Create initial watermark entries for materialized views
INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, last_run_status)
VALUES 
    ('mv_unified_daily', 'mv', CURRENT_DATE, 'pending'),
    ('mv_unified_weekly', 'mv', CURRENT_DATE, 'pending'),
    ('mv_unified_monthly', 'mv', CURRENT_DATE, 'pending')
ON CONFLICT (property, source_type) DO NOTHING;

-- Analyze tables for query optimization
ANALYZE gsc.mv_unified_page_performance;
ANALYZE gsc.mv_unified_page_performance_weekly;
ANALYZE gsc.mv_unified_page_performance_monthly;

-- Add comments for documentation
COMMENT ON MATERIALIZED VIEW gsc.mv_unified_page_performance IS 'Materialized cache of unified view with time-series calculations. Refresh daily after data ingestion.';
COMMENT ON MATERIALIZED VIEW gsc.mv_unified_page_performance_weekly IS 'Weekly aggregated materialized view of unified page performance metrics';
COMMENT ON MATERIALIZED VIEW gsc.mv_unified_page_performance_monthly IS 'Monthly aggregated materialized view of unified page performance metrics';
