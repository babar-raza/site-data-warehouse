#!/bin/bash
# GSC Warehouse - Collect Statistics
# Displays current warehouse statistics and metrics

set -e

echo "=========================================="
echo "GSC Warehouse Statistics"
echo "=========================================="
echo

# Check if warehouse is running
if ! docker compose ps warehouse | grep -q "Up"; then
    echo "ERROR: Warehouse is not running"
    echo "Run: docker compose up -d warehouse"
    exit 1
fi

echo "[Database Statistics]"
echo "----------------------------------------"
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "
SELECT 'Total Rows' as metric, COUNT(*)::text as value FROM gsc.fact_gsc_daily
UNION ALL SELECT 'Earliest Date', MIN(date)::text FROM gsc.fact_gsc_daily
UNION ALL SELECT 'Latest Date', MAX(date)::text FROM gsc.fact_gsc_daily
UNION ALL SELECT 'Days of Data', COUNT(DISTINCT date)::text FROM gsc.fact_gsc_daily
UNION ALL SELECT 'Properties', COUNT(DISTINCT property)::text FROM gsc.fact_gsc_daily
UNION ALL SELECT 'Database Size', pg_size_pretty(pg_database_size('gsc_db'));
" 2>/dev/null

echo
echo "[Data Freshness]"
echo "----------------------------------------"
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "
SELECT 
    property, 
    MAX(date) as latest_date, 
    CURRENT_DATE - MAX(date) as days_old,
    COUNT(*) as total_rows
FROM gsc.fact_gsc_daily
GROUP BY property
ORDER BY latest_date DESC;
" 2>/dev/null

echo
echo "[Watermarks]"
echo "----------------------------------------"
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "
SELECT 
    property, 
    source_type, 
    last_date, 
    rows_processed,
    last_run_status,
    last_run_at
FROM gsc.ingest_watermarks
ORDER BY last_run_at DESC;
" 2>/dev/null

echo
echo "[Recent Activity (Last 7 Days)]"
echo "----------------------------------------"
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "
SELECT date, COUNT(*) as rows
FROM gsc.fact_gsc_daily
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY date
ORDER BY date DESC;
" 2>/dev/null

echo
echo "[Service Status]"
echo "----------------------------------------"
docker compose ps

echo
echo "[Container Sizes]"
echo "----------------------------------------"
docker compose ps --format "table {{.Service}}\t{{.Size}}"

echo
echo "=========================================="
echo "Statistics Collection Complete"
echo "=========================================="
