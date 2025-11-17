-- =============================================
-- DATA VALIDATION QUERIES
-- =============================================
-- Comprehensive validation for GSC data quality
-- Run before insights generation to ensure sufficient data

SET search_path TO gsc, public;

-- =============================================
-- VALIDATION 1: Data Depth
-- =============================================

-- Check date range coverage
CREATE OR REPLACE FUNCTION gsc.validate_data_depth()
RETURNS TABLE(
    property TEXT,
    source_type TEXT,
    earliest_date DATE,
    latest_date DATE,
    total_days INTEGER,
    continuous_days INTEGER,
    status TEXT,
    message TEXT
) AS $$
BEGIN
    -- GSC data depth
    RETURN QUERY
    SELECT 
        f.property::TEXT,
        'gsc'::TEXT as source_type,
        MIN(f.date) as earliest_date,
        MAX(f.date) as latest_date,
        COUNT(DISTINCT f.date)::INTEGER as total_days,
        (MAX(f.date) - MIN(f.date) + 1)::INTEGER as continuous_days,
        CASE 
            WHEN COUNT(DISTINCT f.date) >= 30 THEN 'PASS'
            WHEN COUNT(DISTINCT f.date) >= 7 THEN 'WARN'
            ELSE 'FAIL'
        END::TEXT as status,
        CASE 
            WHEN COUNT(DISTINCT f.date) >= 30 THEN 'Sufficient data for WoW and MoM'
            WHEN COUNT(DISTINCT f.date) >= 7 THEN 'Sufficient for WoW only (need 30+ for MoM)'
            ELSE 'Insufficient data (need 7+ days minimum)'
        END::TEXT as message
    FROM gsc.fact_gsc_daily f
    GROUP BY f.property;
    
    -- GA4 data depth
    RETURN QUERY
    SELECT 
        g.property::TEXT,
        'ga4'::TEXT as source_type,
        MIN(g.date) as earliest_date,
        MAX(g.date) as latest_date,
        COUNT(DISTINCT g.date)::INTEGER as total_days,
        (MAX(g.date) - MIN(g.date) + 1)::INTEGER as continuous_days,
        CASE 
            WHEN COUNT(DISTINCT g.date) >= 30 THEN 'PASS'
            WHEN COUNT(DISTINCT g.date) >= 7 THEN 'WARN'
            ELSE 'FAIL'
        END::TEXT as status,
        CASE 
            WHEN COUNT(DISTINCT g.date) >= 30 THEN 'Sufficient data for WoW and MoM'
            WHEN COUNT(DISTINCT g.date) >= 7 THEN 'Sufficient for WoW only (need 30+ for MoM)'
            ELSE 'Insufficient data (need 7+ days minimum)'
        END::TEXT as message
    FROM gsc.fact_ga4_daily g
    GROUP BY g.property;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- VALIDATION 2: Date Gaps
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_date_continuity()
RETURNS TABLE(
    property TEXT,
    source_type TEXT,
    gap_start DATE,
    gap_end DATE,
    gap_days INTEGER,
    status TEXT
) AS $$
BEGIN
    -- Find gaps in GSC data
    RETURN QUERY
    WITH date_series AS (
        SELECT 
            property,
            date,
            LEAD(date) OVER (PARTITION BY property ORDER BY date) as next_date
        FROM (
            SELECT DISTINCT property, date 
            FROM gsc.fact_gsc_daily
        ) t
    )
    SELECT 
        property::TEXT,
        'gsc'::TEXT as source_type,
        date as gap_start,
        next_date as gap_end,
        (next_date - date - 1)::INTEGER as gap_days,
        CASE 
            WHEN (next_date - date - 1) > 7 THEN 'FAIL'
            WHEN (next_date - date - 1) > 1 THEN 'WARN'
            ELSE 'PASS'
        END::TEXT as status
    FROM date_series
    WHERE next_date - date > 1;
    
    -- Find gaps in GA4 data
    RETURN QUERY
    WITH date_series AS (
        SELECT 
            property,
            date,
            LEAD(date) OVER (PARTITION BY property ORDER BY date) as next_date
        FROM (
            SELECT DISTINCT property, date 
            FROM gsc.fact_ga4_daily
        ) t
    )
    SELECT 
        property::TEXT,
        'ga4'::TEXT as source_type,
        date as gap_start,
        next_date as gap_end,
        (next_date - date - 1)::INTEGER as gap_days,
        CASE 
            WHEN (next_date - date - 1) > 7 THEN 'FAIL'
            WHEN (next_date - date - 1) > 1 THEN 'WARN'
            ELSE 'PASS'
        END::TEXT as status
    FROM date_series
    WHERE next_date - date > 1;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- VALIDATION 3: Data Quality
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_data_quality()
RETURNS TABLE(
    check_name TEXT,
    property TEXT,
    issue_count BIGINT,
    status TEXT,
    message TEXT
) AS $$
BEGIN
    -- Check for duplicate rows in GSC
    RETURN QUERY
    SELECT 
        'gsc_duplicates'::TEXT,
        property::TEXT,
        COUNT(*) as issue_count,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        CASE 
            WHEN COUNT(*) = 0 THEN 'No duplicate rows'
            ELSE 'Duplicate rows found - needs deduplication'
        END::TEXT
    FROM (
        SELECT property, date, url, query, country, device, COUNT(*) as cnt
        FROM gsc.fact_gsc_daily
        GROUP BY property, date, url, query, country, device
        HAVING COUNT(*) > 1
    ) dups
    GROUP BY property;
    
    -- Check for NULL clicks/impressions
    RETURN QUERY
    SELECT 
        'gsc_null_metrics'::TEXT,
        property::TEXT,
        COUNT(*) as issue_count,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        'Rows with NULL clicks or impressions'::TEXT
    FROM gsc.fact_gsc_daily
    WHERE clicks IS NULL OR impressions IS NULL
    GROUP BY property;
    
    -- Check for unreasonable CTR values
    RETURN QUERY
    SELECT 
        'gsc_invalid_ctr'::TEXT,
        property::TEXT,
        COUNT(*) as issue_count,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        'Rows with invalid CTR (>100 or <0)'::TEXT
    FROM gsc.fact_gsc_daily
    WHERE ctr > 100 OR ctr < 0
    GROUP BY property;
    
    -- Check for GA4 null conversions
    RETURN QUERY
    SELECT 
        'ga4_null_conversions'::TEXT,
        property::TEXT,
        COUNT(*) as issue_count,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        'Rows with NULL conversions'::TEXT
    FROM gsc.fact_ga4_daily
    WHERE conversions IS NULL
    GROUP BY property;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- VALIDATION 4: Transform Readiness
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_transform_readiness()
RETURNS TABLE(
    check_name TEXT,
    property TEXT,
    result_count BIGINT,
    expected_count BIGINT,
    status TEXT,
    message TEXT
) AS $$
BEGIN
    -- Check unified view has data
    RETURN QUERY
    SELECT 
        'unified_view_rows'::TEXT,
        property::TEXT,
        COUNT(*) as result_count,
        (SELECT COUNT(DISTINCT date) FROM gsc.fact_gsc_daily f WHERE f.property = v.property)::BIGINT as expected_count,
        CASE 
            WHEN COUNT(*) > 0 THEN 'PASS' 
            ELSE 'FAIL' 
        END::TEXT,
        'Unified view contains data'::TEXT
    FROM gsc.vw_unified_page_performance v
    GROUP BY property;
    
    -- Check WoW fields populated
    RETURN QUERY
    SELECT 
        'wow_fields_populated'::TEXT,
        property::TEXT,
        COUNT(*) FILTER (WHERE gsc_clicks_change_wow IS NOT NULL) as result_count,
        COUNT(*) as expected_count,
        CASE 
            WHEN COUNT(*) FILTER (WHERE gsc_clicks_change_wow IS NOT NULL)::FLOAT / NULLIF(COUNT(*), 0) >= 0.5 
            THEN 'PASS' 
            ELSE 'WARN' 
        END::TEXT,
        'WoW calculations populated (need 7+ days history)'::TEXT
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY property;
    
    -- Check recent data exists
    RETURN QUERY
    SELECT 
        'recent_data_7d'::TEXT,
        property::TEXT,
        COUNT(*) as result_count,
        7::BIGINT as expected_count,
        CASE 
            WHEN COUNT(*) >= 1 THEN 'PASS'
            ELSE 'FAIL'
        END::TEXT,
        'Data exists in last 7 days'::TEXT
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY property;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- VALIDATION 5: Property Coverage
-- =============================================

CREATE OR REPLACE FUNCTION gsc.validate_property_coverage()
RETURNS TABLE(
    property TEXT,
    has_gsc BOOLEAN,
    has_ga4 BOOLEAN,
    gsc_pages INTEGER,
    ga4_pages INTEGER,
    status TEXT,
    message TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH gsc_props AS (
        SELECT DISTINCT property FROM gsc.fact_gsc_daily
    ),
    ga4_props AS (
        SELECT DISTINCT property FROM gsc.fact_ga4_daily
    ),
    all_props AS (
        SELECT property FROM gsc_props
        UNION
        SELECT property FROM ga4_props
    )
    SELECT 
        p.property::TEXT,
        EXISTS(SELECT 1 FROM gsc_props g WHERE g.property = p.property) as has_gsc,
        EXISTS(SELECT 1 FROM ga4_props ga WHERE ga.property = p.property) as has_ga4,
        COALESCE((SELECT COUNT(DISTINCT url) FROM gsc.fact_gsc_daily WHERE property = p.property), 0)::INTEGER as gsc_pages,
        COALESCE((SELECT COUNT(DISTINCT page_path) FROM gsc.fact_ga4_daily WHERE property = p.property), 0)::INTEGER as ga4_pages,
        CASE 
            WHEN EXISTS(SELECT 1 FROM gsc_props g WHERE g.property = p.property) 
                AND EXISTS(SELECT 1 FROM ga4_props ga WHERE ga.property = p.property)
            THEN 'PASS'
            WHEN EXISTS(SELECT 1 FROM gsc_props g WHERE g.property = p.property)
            THEN 'WARN'
            ELSE 'FAIL'
        END::TEXT as status,
        CASE 
            WHEN EXISTS(SELECT 1 FROM gsc_props g WHERE g.property = p.property) 
                AND EXISTS(SELECT 1 FROM ga4_props ga WHERE ga.property = p.property)
            THEN 'Both GSC and GA4 data available'
            WHEN EXISTS(SELECT 1 FROM gsc_props g WHERE g.property = p.property)
            THEN 'Only GSC data available (GA4 missing)'
            ELSE 'No data available'
        END::TEXT as message
    FROM all_props p;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- MASTER VALIDATION FUNCTION
-- =============================================

CREATE OR REPLACE FUNCTION gsc.run_all_validations()
RETURNS TABLE(
    validation_type TEXT,
    check_name TEXT,
    property TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Data depth
    RETURN QUERY
    SELECT 
        'data_depth'::TEXT,
        source_type::TEXT as check_name,
        d.property,
        d.status,
        format('%s days (%s to %s): %s', 
            d.total_days, 
            d.earliest_date::TEXT, 
            d.latest_date::TEXT, 
            d.message) as details
    FROM gsc.validate_data_depth() d;
    
    -- Date continuity
    RETURN QUERY
    SELECT 
        'date_gaps'::TEXT,
        c.source_type::TEXT as check_name,
        c.property,
        c.status,
        format('Gap of %s days (%s to %s)', 
            c.gap_days, 
            c.gap_start::TEXT, 
            c.gap_end::TEXT) as details
    FROM gsc.validate_date_continuity() c;
    
    -- Data quality
    RETURN QUERY
    SELECT 
        'data_quality'::TEXT,
        q.check_name,
        q.property,
        q.status,
        format('%s: %s issues - %s', q.check_name, q.issue_count, q.message) as details
    FROM gsc.validate_data_quality() q;
    
    -- Transform readiness
    RETURN QUERY
    SELECT 
        'transform_readiness'::TEXT,
        t.check_name,
        t.property,
        t.status,
        format('%s: %s/%s - %s', 
            t.check_name, 
            t.result_count, 
            t.expected_count, 
            t.message) as details
    FROM gsc.validate_transform_readiness() t;
    
    -- Property coverage
    RETURN QUERY
    SELECT 
        'property_coverage'::TEXT,
        'coverage'::TEXT as check_name,
        p.property,
        p.status,
        format('GSC: %s (%s pages), GA4: %s (%s pages) - %s',
            p.has_gsc,
            p.gsc_pages,
            p.has_ga4,
            p.ga4_pages,
            p.message) as details
    FROM gsc.validate_property_coverage() p;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- PERMISSIONS
-- =============================================

GRANT EXECUTE ON FUNCTION gsc.validate_data_depth() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_date_continuity() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_data_quality() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_transform_readiness() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.validate_property_coverage() TO gsc_user;
GRANT EXECUTE ON FUNCTION gsc.run_all_validations() TO gsc_user;

-- =============================================
-- USAGE EXAMPLES
-- =============================================

COMMENT ON FUNCTION gsc.run_all_validations() IS 
'Run all data validation checks and return comprehensive report.
Usage: SELECT * FROM gsc.run_all_validations();';
