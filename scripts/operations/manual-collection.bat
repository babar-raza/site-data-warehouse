@echo off
REM GSC Warehouse - Manual Data Collection (Windows)
REM Trigger on-demand data collection

setlocal enabledelayedexpansion

set INGEST_DAYS=30

REM Parse arguments
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--days" (
    set INGEST_DAYS=%~2
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--full" (
    set INGEST_DAYS=480
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    echo Usage: manual-collection.bat [options]
    echo.
    echo Options:
    echo   --days N     Collect N days of data (default: 30)
    echo   --full       Collect full 16 months (480 days)
    echo   --help       Show this help message
    echo.
    echo Examples:
    echo   manual-collection.bat              # Collect last 30 days
    echo   manual-collection.bat --days 7     # Collect last 7 days
    echo   manual-collection.bat --full       # Collect full 16 months
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:args_done

echo ==========================================
echo GSC Warehouse Manual Data Collection
echo ==========================================
echo.
echo Collecting last %INGEST_DAYS% days of data...
echo.

REM Check if warehouse is running
docker compose ps warehouse | findstr "Up" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Warehouse is not running[0m
    echo Run: docker compose up -d warehouse
    exit /b 1
)

REM Run data collection
docker compose run --rm -e INGEST_DAYS=%INGEST_DAYS% -e RUN_INITIAL_COLLECTION=true startup_orchestrator

if !ERRORLEVEL! EQU 0 (
    echo.
    echo [32mData collection completed successfully[0m
    echo.
    echo Check collected data:
    echo   docker compose exec warehouse psql -U gsc_user -d gsc_db -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"
) else (
    echo.
    echo [31mData collection failed[0m
    echo Check logs: docker compose logs startup_orchestrator
    exit /b 1
)

endlocal
