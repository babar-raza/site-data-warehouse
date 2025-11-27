-- ==============================================
-- GA4 Integration Validation Script
-- Run after implementation to verify success
-- ==============================================

\echo '=================================='
\echo 'GA4 Integration Validation Report'
\echo '=================================='
\echo ''

-- Check 1: GA4 Table Exists
\echo '1. Checking GA4 table exists...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
    ) THEN '[PASS] GA4 table exists'
    ELSE '[FAIL] GA4 table missing'
  END as result;

\echo ''

-- Check 2: Unified View Exists
\echo '2. Checking unified view exists...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.views
      WHERE table_schema = 'gsc' AND table_name = 'vw_unified_page_performance'
    ) THEN '[PASS] Unified view exists'
    ELSE '[FAIL] Unified view missing'
  END as result;

\echo ''

-- Check 3: GA4 Data Loaded
\echo '3. Checking GA4 data loaded...'
SELECT
  CASE
    WHEN COUNT(*) > 0 THEN '[PASS] GA4 data exists (' || COUNT(*) || ' rows)'
    ELSE '[FAIL] No GA4 data'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 4: Data Quality - No Nulls
\echo '4. Checking data quality (nulls)...'
SELECT
  CASE
    WHEN COUNT(*) FILTER (WHERE sessions IS NULL OR page_path IS NULL) = 0
    THEN '[PASS] No null values in critical fields'
    ELSE '[FAIL] ' || COUNT(*) FILTER (WHERE sessions IS NULL OR page_path IS NULL) || ' null values found'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 5: Data Quality - No Duplicates
\echo '5. Checking data quality (duplicates)...'
SELECT
  CASE
    WHEN COUNT(*) = COUNT(DISTINCT (date, property, page_path))
    THEN '[PASS] No duplicate records'
    ELSE '[FAIL] ' || (COUNT(*) - COUNT(DISTINCT (date, property, page_path))) || ' duplicates found'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 6: Metric Ranges Valid
\echo '6. Checking metric ranges...'
SELECT
  CASE
    WHEN MIN(bounce_rate) >= 0 AND MAX(bounce_rate) <= 1
     AND MIN(engagement_rate) >= 0 AND MAX(engagement_rate) <= 1
     AND MIN(sessions) >= 0
    THEN '[PASS] All metrics within valid ranges'
    ELSE '[FAIL] Metrics outside expected ranges'
  END as result
FROM gsc.fact_ga4_daily
WHERE sessions > 0;  -- Only check rows with data

\echo ''

-- Check 7: Watermark Exists
\echo '7. Checking watermark tracking...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM gsc.ingest_watermarks WHERE source_type = 'ga4'
    ) THEN '[PASS] GA4 watermark exists (last date: ' ||
            (SELECT last_date::text FROM gsc.ingest_watermarks WHERE source_type = 'ga4') || ')'
    ELSE '[FAIL] GA4 watermark missing'
  END as result;

\echo ''

-- Check 8: Unified View Has Data
\echo '8. Checking unified view has GA4 data...'
SELECT
  CASE
    WHEN COUNT(*) FILTER (WHERE ga_sessions > 0) > 0
    THEN '[PASS] Unified view has GA4 data (' ||
         COUNT(*) FILTER (WHERE ga_sessions > 0) || ' rows with sessions)'
    ELSE '[FAIL] Unified view has no GA4 data'
  END as result
FROM gsc.vw_unified_page_performance;

\echo ''

-- Summary Statistics
\echo '=================================='
\echo 'Summary Statistics'
\echo '=================================='
\echo ''

SELECT
  'Total GA4 Rows' as metric,
  COUNT(*)::text as value
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Date Range',
  COALESCE(MIN(date)::text, 'N/A') || ' to ' || COALESCE(MAX(date)::text, 'N/A')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Sessions',
  COALESCE(SUM(sessions)::text, '0')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Conversions',
  COALESCE(SUM(conversions)::text, '0')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Avg Engagement',
  COALESCE(ROUND(AVG(engagement_rate)::numeric, 4)::text, 'N/A')
FROM gsc.fact_ga4_daily
WHERE sessions > 0;

\echo ''
\echo '=================================='
\echo 'Validation Complete'
\echo '=================================='
