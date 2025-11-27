@echo off
REM Quick deployment script for Windows
REM Deploys Docker containers with resource limits

echo ==========================================
echo Docker Deployment with Resource Limits
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

echo Docker is running...
echo.

REM Get deployment profile
set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=core

echo Deployment Profile: %PROFILE%
echo.

REM Stop existing containers
echo [1/5] Stopping existing containers...
docker-compose down
echo.

REM Optional cleanup
set /p CLEANUP="Run cleanup? (y/N): "
if /i "%CLEANUP%"=="y" (
    echo [2/5] Cleaning up old containers and images...
    docker container prune -f
    docker image prune -f
    echo.
) else (
    echo [2/5] Skipping cleanup
    echo.
)

REM Build images
echo [3/5] Building images...
docker-compose build --parallel
if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)
echo.

REM Deploy
echo [4/5] Deploying services with profile: %PROFILE%
docker-compose --profile %PROFILE% up -d
if errorlevel 1 (
    echo ERROR: Deployment failed!
    pause
    exit /b 1
)
echo.

REM Wait for services
echo [5/5] Waiting for services to start...
timeout /t 10 /nobreak >nul
echo.

REM Show status
echo ==========================================
echo Deployment Status
echo ==========================================
docker-compose ps
echo.

echo ==========================================
echo Resource Usage
echo ==========================================
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
echo.

echo ==========================================
echo Deployment Complete!
echo ==========================================
echo.
echo View logs: docker-compose logs -f
echo Stop services: docker-compose down
echo Check status: docker-compose ps
echo.
pause
