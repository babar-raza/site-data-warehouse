@echo off
REM GSC Warehouse - Redeployment Script (Windows)
REM Updates the system without data loss

setlocal enabledelayedexpansion

set SKIP_DATA_COLLECTION=0
set SKIP_BUILD=0

REM Parse arguments
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--skip-data-collection" (
    set SKIP_DATA_COLLECTION=1
    shift
    goto parse_args
)
if /i "%~1"=="--skip-build" (
    set SKIP_BUILD=1
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    echo Usage: redeploy.bat [options]
    echo.
    echo Options:
    echo   --skip-data-collection    Skip running data collection
    echo   --skip-build             Skip rebuilding Docker images
    echo   --help                   Show this help message
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:args_done

echo ==========================================
echo GSC Warehouse Redeployment
echo ==========================================
echo.

REM Stop running services
echo [1/5] Stopping services...
docker compose stop scheduler api_ingestor transformer metrics_exporter prometheus mcp insights_api startup_orchestrator >nul 2>&1
echo [32mServices stopped[0m

REM Remove old containers
echo.
echo [2/5] Removing old containers...
docker compose rm -f scheduler api_ingestor transformer metrics_exporter prometheus mcp insights_api startup_orchestrator >nul 2>&1
echo [32mOld containers removed[0m

REM Rebuild images if not skipped
if %SKIP_BUILD%==0 (
    echo.
    echo [3/5] Rebuilding Docker images...
    docker compose build --no-cache
    if !ERRORLEVEL! NEQ 0 (
        echo [31mERROR: Failed to rebuild images[0m
        exit /b 1
    )
    echo [32mImages rebuilt[0m
) else (
    echo.
    echo [3/5] Skipping image rebuild (--skip-build)
)

REM Start core services
echo.
echo [4/5] Starting services...
docker compose up -d warehouse mcp

echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Verify warehouse is healthy
set max_attempts=30
for /L %%i in (1,1,%max_attempts%) do (
    docker compose exec -T warehouse pg_isready -U gsc_user -d gsc_db >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        echo [32mWarehouse is ready[0m
        goto warehouse_ready
    )
    if %%i EQU %max_attempts% (
        echo [31mERROR: Warehouse failed to become ready[0m
        exit /b 1
    )
    timeout /t 2 /nobreak >nul
)

:warehouse_ready

REM Optionally run data collection
if %SKIP_DATA_COLLECTION%==0 (
    echo.
    echo [5/5] Running data refresh...
    
    REM Run a quick data refresh (only recent days)
    docker compose run --rm -e INGEST_DAYS=7 -e RUN_INITIAL_COLLECTION=true startup_orchestrator
    
    if !ERRORLEVEL! EQU 0 (
        echo [32mData refresh completed[0m
    ) else (
        echo [33mWARNING: Data refresh had issues (check logs)[0m
    )
) else (
    echo.
    echo [5/5] Skipping data collection (--skip-data-collection)
)

REM Start scheduler
echo.
echo Starting scheduler...
docker compose --profile scheduler up -d scheduler

echo.
echo ==========================================
echo Redeployment Complete!
echo ==========================================
echo.
echo Services running:
docker compose ps
echo.
echo Check data freshness:
echo   docker compose exec warehouse psql -U gsc_user -d gsc_db -c "SELECT MAX(date) FROM gsc.fact_gsc_daily;"
echo.
echo View logs:
echo   docker compose logs -f
echo.

endlocal
