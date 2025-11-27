@echo off
REM Docker Cleanup Script for Windows
REM Removes unused containers, images, volumes, and build cache
REM to prevent massive storage growth

echo ==========================================
echo Docker Cleanup Script
echo ==========================================
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Stop and remove all containers
echo [1/6] Stopping all containers...
docker-compose down --remove-orphans
echo.

REM Remove stopped containers
echo [2/6] Removing stopped containers...
docker container prune -f
echo.

REM Remove dangling images
echo [3/6] Removing dangling images...
docker image prune -f
echo.

REM Remove unused volumes (with confirmation)
echo [4/6] Removing unused volumes...
set /p CONFIRM="Remove unused volumes? This may delete data! (y/N): "
if /i "%CONFIRM%"=="y" (
    docker volume prune -f
    echo   [OK] Volumes cleaned
) else (
    echo   [SKIP] Volume cleanup skipped
)
echo.

REM Remove build cache (keeps last 24 hours)
echo [5/6] Removing old build cache...
docker builder prune -f --filter "until=24h"
echo.

REM Remove networks
echo [6/6] Removing unused networks...
docker network prune -f
echo.

REM Show current usage
echo ==========================================
echo Current Docker Disk Usage
echo ==========================================
docker system df
echo.

REM Advanced cleanup (optional)
set /p AGGRESSIVE="Run aggressive cleanup? This removes ALL unused data! (y/N): "
if /i "%AGGRESSIVE%"=="y" (
    echo Running aggressive cleanup...
    docker system prune -a -f --volumes
    echo   [OK] Aggressive cleanup complete
    echo.
)

echo ==========================================
echo Cleanup Complete!
echo ==========================================
docker system df
echo.
pause
