@echo off
REM View service logs
if "%1"=="" (
    echo Usage: logs.bat ^<service-name^>
    echo Services: warehouse, insights_engine, mcp, dispatcher
    echo Or: logs.bat all
    exit /b 1
)

if "%1"=="all" (
    docker-compose logs -f
) else (
    docker-compose logs -f %1
)
