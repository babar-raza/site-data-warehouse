@echo off
REM Health Check Script - Checks status of all services

setlocal enabledelayedexpansion

echo ========================================
echo GSC Data Warehouse - Health Check
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running
    pause
    exit /b 1
)

echo [Docker] Running ✓
echo.

echo Checking container status...
echo.
docker compose ps

echo.
echo ----------------------------------------
echo Service Health Checks
echo ----------------------------------------
echo.

REM Check Warehouse
echo Checking Warehouse (PostgreSQL)...
docker compose exec -T warehouse pg_isready -U gsc_user -d gsc_db >nul 2>&1
if errorlevel 1 (
    echo   [WAREHOUSE] ❌ Not responding
) else (
    echo   [WAREHOUSE] ✓ Healthy
)

REM Check Insights API
echo Checking Insights API...
curl -s -f http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 (
    echo   [INSIGHTS API] ⚠ Not running or not healthy ^(optional service^)
) else (
    echo   [INSIGHTS API] ✓ Healthy
)

REM Check MCP Server
echo Checking MCP Server...
curl -s -f http://localhost:8001/health >nul 2>&1
if errorlevel 1 (
    echo   [MCP SERVER] ❌ Not responding
) else (
    echo   [MCP SERVER] ✓ Healthy
)

REM Check Metrics Exporter
echo Checking Metrics Exporter...
curl -s -f http://localhost:9090/health >nul 2>&1
if errorlevel 1 (
    echo   [METRICS] ⚠ Not running or not healthy ^(optional service^)
) else (
    echo   [METRICS] ✓ Healthy
)

REM Check Prometheus
echo Checking Prometheus...
curl -s -f http://localhost:9090/-/healthy >nul 2>&1
if errorlevel 1 (
    echo   [PROMETHEUS] ❌ Not responding
) else (
    echo   [PROMETHEUS] ✓ Healthy
)

REM Check Grafana
echo Checking Grafana...
curl -s -f http://localhost:3000/api/health >nul 2>&1
if errorlevel 1 (
    echo   [GRAFANA] ❌ Not responding
) else (
    echo   [GRAFANA] ✓ Healthy
)

echo.
echo ----------------------------------------
echo Data Warehouse Statistics
echo ----------------------------------------
echo.

docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'gsc' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;" 2>nul

echo.
echo ----------------------------------------
echo Recent Logs (last 50 lines)
echo ----------------------------------------
echo.
docker compose logs --tail=50

echo.
echo Health check complete.
echo.
pause
