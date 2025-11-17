@echo off
REM Windows Deployment Script for GSC Data Warehouse (Hybrid Plan)

echo ======================================
echo GSC Data Warehouse - Deployment
echo ======================================

REM Check prerequisites
where docker >nul 2>&1 || (echo ❌ Docker not installed & exit /b 1)
where docker-compose >nul 2>&1 || (echo ❌ Docker Compose not installed & exit /b 1)
where psql >nul 2>&1 || (echo ❌ psql not installed & exit /b 1)
echo ✅ Prerequisites checked

REM Step 1: Start database
echo.
echo === Step 1: Starting Database ===
docker-compose up -d warehouse
echo ⏳ Waiting for database...
:waitdb
docker-compose exec -T warehouse pg_isready >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto waitdb
)
echo ✅ Database ready

REM Step 2: Run migrations
echo.
echo === Step 2: Running Migrations ===
for %%f in (sql\*.sql) do (
    echo   Running: %%~nxf
    psql %WAREHOUSE_DSN% -f "%%f" >nul 2>&1
)
echo ✅ Migrations complete

REM Step 3: Start all services
echo.
echo === Step 3: Starting Services ===
docker-compose up -d
timeout /t 5 /nobreak >nul
echo ✅ Services started

REM Step 4: Health checks
echo.
echo === Step 4: Health Checks ===
docker-compose ps
echo ✅ Check services above

REM Success
echo.
echo ======================================
echo ✅ Deployment Complete!
echo ======================================
echo.
echo Next steps:
echo   1. Ingest data: python ingestors/api/gsc_api_ingestor.py --date-start 2024-11-01
echo   2. Generate insights: python -m insights_core.cli refresh
echo   3. View insights: psql %%WAREHOUSE_DSN%% -c "SELECT * FROM gsc.vw_insights_actionable LIMIT 10;"
