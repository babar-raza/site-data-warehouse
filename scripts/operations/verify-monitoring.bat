@echo off
REM ============================================
REM Prometheus Monitoring Verification Script
REM ============================================
REM Verifies all monitoring components are working
REM - Prometheus
REM - Grafana
REM - Exporters (cAdvisor, PostgreSQL, Redis)
REM - Dashboards
REM - Alert Rules
REM ============================================

echo ========================================
echo Prometheus Monitoring Verification
echo ========================================
echo.

REM Colors (Windows 10+)
set GREEN=[92m
set YELLOW=[93m
set RED=[91m
set RESET=[0m
set BLUE=[94m

REM Check if Docker is running
echo %BLUE%[1/10] Checking Docker status...%RESET%
docker info >nul 2>&1
if errorlevel 1 (
    echo %RED%✗ Docker is not running%RESET%
    echo Please start Docker Desktop and try again
    exit /b 1
)
echo %GREEN%✓ Docker is running%RESET%
echo.

REM Check containers
echo %BLUE%[2/10] Checking monitoring containers...%RESET%
set CONTAINERS=gsc_prometheus gsc_grafana gsc_cadvisor gsc_postgres_exporter gsc_metrics_exporter
for %%C in (%CONTAINERS%) do (
    docker ps --filter "name=%%C" --filter "status=running" --format "{{.Names}}" | findstr /C:"%%C" >nul
    if errorlevel 1 (
        echo %RED%✗ Container %%C is not running%RESET%
    ) else (
        echo %GREEN%✓ Container %%C is running%RESET%
    )
)
echo.

REM Check Redis exporter (optional - intelligence profile)
echo %BLUE%[3/10] Checking optional containers...%RESET%
docker ps --filter "name=gsc_redis_exporter" --filter "status=running" --format "{{.Names}}" | findstr /C:"gsc_redis_exporter" >nul
if errorlevel 1 (
    echo %YELLOW%⚠ Redis exporter not running (requires intelligence profile)%RESET%
) else (
    echo %GREEN%✓ Redis exporter is running%RESET%
)
echo.

REM Check Prometheus endpoint
echo %BLUE%[4/10] Checking Prometheus endpoint...%RESET%
curl -s http://localhost:9090/-/healthy >nul 2>&1
if errorlevel 1 (
    echo %RED%✗ Prometheus endpoint not responding%RESET%
) else (
    echo %GREEN%✓ Prometheus is healthy%RESET%
)
echo.

REM Check Grafana endpoint
echo %BLUE%[5/10] Checking Grafana endpoint...%RESET%
curl -s http://localhost:3000/api/health >nul 2>&1
if errorlevel 1 (
    echo %RED%✗ Grafana endpoint not responding%RESET%
) else (
    echo %GREEN%✓ Grafana is healthy%RESET%
)
echo.

REM Check Prometheus targets
echo %BLUE%[6/10] Checking Prometheus targets...%RESET%
curl -s http://localhost:9090/api/v1/targets 2>nul | findstr /C:"\"health\":\"up\"" >nul
if errorlevel 1 (
    echo %YELLOW%⚠ Some Prometheus targets may be down%RESET%
    echo   Check: http://localhost:9090/targets
) else (
    echo %GREEN%✓ Prometheus targets are up%RESET%
)
echo.

REM Check exporter endpoints
echo %BLUE%[7/10] Checking exporter endpoints...%RESET%

REM cAdvisor
curl -s http://localhost:8080/metrics 2>nul | findstr /C:"container_cpu" >nul
if errorlevel 1 (
    echo %RED%✗ cAdvisor metrics not available%RESET%
) else (
    echo %GREEN%✓ cAdvisor metrics available%RESET%
)

REM PostgreSQL Exporter
curl -s http://localhost:9187/metrics 2>nul | findstr /C:"pg_stat" >nul
if errorlevel 1 (
    echo %RED%✗ PostgreSQL exporter metrics not available%RESET%
) else (
    echo %GREEN%✓ PostgreSQL exporter metrics available%RESET%
)

REM Redis Exporter (optional)
curl -s http://localhost:9121/metrics 2>nul | findstr /C:"redis_" >nul
if errorlevel 1 (
    echo %YELLOW%⚠ Redis exporter metrics not available (requires intelligence profile)%RESET%
) else (
    echo %GREEN%✓ Redis exporter metrics available%RESET%
)
echo.

REM Check alert rules
echo %BLUE%[8/10] Checking Prometheus alert rules...%RESET%
curl -s http://localhost:9090/api/v1/rules 2>nul | findstr /C:"\"groups\"" >nul
if errorlevel 1 (
    echo %RED%✗ Alert rules not loaded%RESET%
) else (
    echo %GREEN%✓ Alert rules loaded%RESET%
    REM Count rule groups
    curl -s http://localhost:9090/api/v1/rules 2>nul | findstr /C:"infrastructure_alerts" >nul
    if not errorlevel 1 echo   - infrastructure_alerts loaded
    curl -s http://localhost:9090/api/v1/rules 2>nul | findstr /C:"database_alerts" >nul
    if not errorlevel 1 echo   - database_alerts loaded
    curl -s http://localhost:9090/api/v1/rules 2>nul | findstr /C:"redis_alerts" >nul
    if not errorlevel 1 echo   - redis_alerts loaded
    curl -s http://localhost:9090/api/v1/rules 2>nul | findstr /C:"prometheus_alerts" >nul
    if not errorlevel 1 echo   - prometheus_alerts loaded
)
echo.

REM Check Grafana datasource
echo %BLUE%[9/10] Checking Grafana datasource...%RESET%
curl -s -u admin:admin http://localhost:3000/api/datasources 2>nul | findstr /C:"Prometheus" >nul
if errorlevel 1 (
    echo %RED%✗ Prometheus datasource not configured in Grafana%RESET%
) else (
    echo %GREEN%✓ Prometheus datasource configured%RESET%
)
echo.

REM Check dashboards
echo %BLUE%[10/10] Checking Grafana dashboards...%RESET%
set DASHBOARDS=infrastructure-overview database-performance application-metrics service-health alert-status
for %%D in (%DASHBOARDS%) do (
    if exist "grafana\provisioning\dashboards\%%D.json" (
        echo %GREEN%✓ Dashboard %%D.json exists%RESET%
    ) else (
        echo %RED%✗ Dashboard %%D.json not found%RESET%
    )
)
echo.

REM Summary
echo ========================================
echo Verification Summary
echo ========================================
echo.
echo %GREEN%Monitoring system verification complete!%RESET%
echo.
echo Next steps:
echo   1. Open Grafana: http://localhost:3000
echo   2. Login (admin/admin)
echo   3. Browse dashboards
echo   4. Check Prometheus: http://localhost:9090
echo   5. Review targets: http://localhost:9090/targets
echo   6. Review alerts: http://localhost:9090/alerts
echo.
echo Documentation:
echo   - Dashboard Guide: docs/guides/PROMETHEUS_DASHBOARDS_GUIDE.md
echo   - Deployment Guide: docs/DEPLOYMENT.md
echo   - Troubleshooting: docs/TROUBLESHOOTING.md
echo.

pause
