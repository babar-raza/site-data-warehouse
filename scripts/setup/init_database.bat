@echo off
REM ============================================================================
REM Database Initialization Script (Windows)
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=seo_warehouse
set DB_USER=postgres
set SQL_DIR=sql

echo ========================================
echo SEO Intelligence Platform
echo Database Initialization
echo ========================================
echo.

REM Test database connection
echo Testing database connection...
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -c "SELECT 1" > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot connect to database
    exit /b 1
)
echo [OK] Database connection successful
echo.

REM Check if database exists
echo Checking if database exists...
for /f %%i in ('psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%'"') do set DB_EXISTS=%%i

if not "%DB_EXISTS%"=="1" (
    echo Creating database: %DB_NAME%
    psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d postgres -c "CREATE DATABASE %DB_NAME%;"
    echo [OK] Database created
) else (
    echo [INFO] Database already exists
)
echo.

REM Enable extensions
echo Enabling PostgreSQL extensions...
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -c "CREATE EXTENSION IF NOT EXISTS vector;" > nul 2>&1
echo [OK] Extension enabled: vector

psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" > nul 2>&1
echo [OK] Extension enabled: pg_trgm

psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" > nul 2>&1
echo [OK] Extension enabled: uuid-ossp
echo.

REM Run SQL schema files
echo Running SQL schema files...

set SQL_FILES=00_extensions.sql 01_base_schema.sql 02_gsc_schema.sql 03_ga4_schema.sql 04_session_stitching.sql 05_unified_view.sql 12_actions_schema.sql 13_content_schema.sql 14_forecasts_schema.sql 16_serp_schema.sql 17_performance_schema.sql 18_analytics_schema.sql 20_notifications_schema.sql 21_orchestration_schema.sql 22_anomaly_schema.sql

for %%f in (%SQL_FILES%) do (
    if exist "%SQL_DIR%\%%f" (
        echo   Running: %%f
        psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%SQL_DIR%\%%f" > nul 2>&1
        if errorlevel 1 (
            echo [ERROR] Failed to execute %%f
            exit /b 1
        )
        echo [OK] %%f executed successfully
    ) else (
        echo [WARN] File not found: %%f
    )
)
echo.

REM Verify installation
echo Verifying schemas...
for /f %%i in ('psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -tAc "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('gsc', 'ga4', 'base', 'serp', 'performance', 'notifications', 'orchestration', 'anomaly')"') do set SCHEMA_COUNT=%%i
echo   Found %SCHEMA_COUNT% schemas
echo [OK] All schemas created
echo.

REM Optimize database
echo Optimizing database...
psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -c "VACUUM ANALYZE;" > nul 2>&1
echo [OK] Database optimized
echo.

echo ========================================
echo Database Initialization Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Configure environment variables (.env file)
echo 2. Run data seeding: python scripts\setup\seed_data.py
echo 3. Start services: scripts\setup\start_services.bat
echo.

pause
