@echo off
REM Cleanup Script - Stops and removes all containers, networks, and volumes
REM WARNING: This will delete all data in the warehouse!

setlocal enabledelayedexpansion

echo ========================================
echo GSC Data Warehouse - Cleanup
echo ========================================
echo.
echo WARNING: This will stop all services and delete all data^^!
echo.
set /p confirm="Are you sure you want to continue? (yes/NO): "
if /i not "!confirm!"=="yes" (
    echo Cleanup cancelled.
    pause
    exit /b 0
)

echo.
echo Stopping all services...
docker compose --profile ingestion --profile transform --profile scheduler --profile api --profile observability down

echo.
echo Removing volumes (this will delete all data)...
docker compose down -v

echo.
echo Removing Docker images...
docker rmi gsc-bq-extractor:latest 2>nul
docker rmi gsc-api-ingestor:latest 2>nul
docker rmi gsc-transformer:latest 2>nul
docker rmi gsc-mcp-server:latest 2>nul
docker rmi gsc-insights-api:latest 2>nul
docker rmi gsc-scheduler:latest 2>nul
docker rmi gsc-metrics-exporter:latest 2>nul

echo.
echo Cleaning up logs...
if exist "logs" (
    del /q logs\* 2>nul
)

echo.
echo ========================================
echo Cleanup Complete^^!
echo ========================================
echo.
echo All containers, volumes, and images have been removed.
echo To start fresh, run deploy.bat
echo.
pause
