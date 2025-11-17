@echo off
REM GSC Warehouse - Collect Statistics (Windows)
REM Displays current warehouse statistics and metrics

setlocal enabledelayedexpansion

echo ==========================================
echo GSC Warehouse Statistics
echo ==========================================
echo.

REM Check if warehouse is running
docker compose ps warehouse | findstr "Up" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Warehouse is not running[0m
    echo Run: docker compose up -d warehouse
    exit /b 1
)

echo [Database Statistics]
echo ----------------------------------------
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT 'Total Rows' as metric, COUNT(*)::text as value FROM gsc.fact_gsc_daily UNION ALL SELECT 'Earliest Date', MIN(date)::text FROM gsc.fact_gsc_daily UNION ALL SELECT 'Latest Date', MAX(date)::text FROM gsc.fact_gsc_daily UNION ALL SELECT 'Days of Data', COUNT(DISTINCT date)::text FROM gsc.fact_gsc_daily UNION ALL SELECT 'Properties', COUNT(DISTINCT property)::text FROM gsc.fact_gsc_daily UNION ALL SELECT 'Database Size', pg_size_pretty(pg_database_size('gsc_db'));" 2>nul

echo.
echo [Data Freshness]
echo ----------------------------------------
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT property, MAX(date) as latest_date, CURRENT_DATE - MAX(date) as days_old, COUNT(*) as total_rows FROM gsc.fact_gsc_daily GROUP BY property ORDER BY latest_date DESC;" 2>nul

echo.
echo [Watermarks]
echo ----------------------------------------
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT property, source_type, last_date, rows_processed, last_run_status, last_run_at FROM gsc.ingest_watermarks ORDER BY last_run_at DESC;" 2>nul

echo.
echo [Recent Activity (Last 7 Days)]
echo ----------------------------------------
docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT date, COUNT(*) as rows FROM gsc.fact_gsc_daily WHERE date >= CURRENT_DATE - INTERVAL '7 days' GROUP BY date ORDER BY date DESC;" 2>nul

echo.
echo [Service Status]
echo ----------------------------------------
docker compose ps

echo.
echo [Container Sizes]
echo ----------------------------------------
docker compose ps --format "table {{.Service}}\t{{.Size}}"

echo.
echo ==========================================
echo Statistics Collection Complete
echo ==========================================

endlocal
