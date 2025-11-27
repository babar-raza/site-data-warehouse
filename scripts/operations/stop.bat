@echo off
REM Stop all running services without removing data

echo ========================================
echo Stopping GSC Data Warehouse Services
echo ========================================
echo.

echo Stopping all services...
docker compose --profile ingestion --profile transform --profile scheduler --profile api --profile observability down

echo.
echo ========================================
echo Services Stopped
echo ========================================
echo.
echo All services have been stopped.
echo Data in volumes is preserved.
echo.
echo To start again: deploy.bat or start-collection.bat
echo To remove all data: cleanup.bat
echo.
pause
