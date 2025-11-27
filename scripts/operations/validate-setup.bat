@echo off
REM Pre-deployment validation script
REM Checks prerequisites before running deployment

setlocal enabledelayedexpansion

echo ========================================
echo Pre-Deployment Validation
echo ========================================
echo.

set "errors=0"
set "warnings=0"

REM Check 1: Docker
echo [1/8] Checking Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo   ❌ Docker not found or not in PATH
    set /a errors+=1
) else (
    docker --version
    echo   ✓ Docker is installed
)
echo.

REM Check 2: Docker running
echo [2/8] Checking if Docker is running...
docker info >nul 2>&1
if errorlevel 1 (
    echo   ❌ Docker is not running - Please start Docker Desktop
    set /a errors+=1
) else (
    echo   ✓ Docker is running
)
echo.

REM Check 3: Docker Compose
echo [3/8] Checking Docker Compose...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo   ❌ Docker Compose not found
    set /a errors+=1
) else (
    docker compose version
    echo   ✓ Docker Compose is available
)
echo.

REM Check 4: Required files
echo [4/8] Checking required files...
set "missing=0"

if not exist "docker-compose.yml" (
    echo   ❌ docker-compose.yml not found
    set /a missing+=1
)

if not exist "requirements.txt" (
    echo   ❌ requirements.txt not found
    set /a missing+=1
)

if not exist ".env" (
    echo   ⚠ .env not found - will be created from .env.example
    set /a warnings+=1
)

if !missing! gtr 0 (
    echo   ❌ Missing !missing! required file^(s^)
    set /a errors+=1
) else (
    echo   ✓ All required files present
)
echo.

REM Check 5: Secrets
echo [5/8] Checking secrets...
if not exist "secrets\gsc_sa.json" (
    echo   ⚠ secrets\gsc_sa.json not found
    echo     You will need to add this file with your GCP credentials
    set /a warnings+=1
) else (
    echo   ✓ secrets\gsc_sa.json exists
)

if not exist "secrets\db_password.txt" (
    echo   ⚠ secrets\db_password.txt not found
    echo     Default password will be used
    set /a warnings+=1
) else (
    echo   ✓ secrets\db_password.txt exists
)
echo.

REM Check 6: Directories
echo [6/8] Checking directory structure...
if not exist "compose\dockerfiles" (
    echo   ❌ Missing dockerfiles directory
    set /a errors+=1
)

if not exist "ingestors" (
    echo   ❌ Missing ingestors directory
    set /a errors+=1
)

if not exist "sql" (
    echo   ❌ Missing sql directory
    set /a errors+=1
)

if !errors! equ 0 (
    echo   ✓ Directory structure is valid
)
echo.

REM Check 7: Docker resources
echo [7/8] Checking Docker resources...
docker info | findstr "Memory" >nul 2>&1
if errorlevel 1 (
    echo   ⚠ Unable to check Docker memory allocation
    set /a warnings+=1
) else (
    echo   ✓ Docker resources available
)
echo.

REM Check 8: Network connectivity
echo [8/8] Checking network connectivity...
ping -n 1 8.8.8.8 >nul 2>&1
if errorlevel 1 (
    echo   ⚠ No internet connectivity detected
    echo     Required for downloading Docker images
    set /a warnings+=1
) else (
    echo   ✓ Internet connectivity available
)
echo.

REM Summary
echo ========================================
echo Validation Summary
echo ========================================
echo.

if !errors! equ 0 (
    if !warnings! equ 0 (
        echo All checks passed^^! Ready to deploy.
        echo.
        echo Run: deploy.bat
    ) else (
        echo !warnings! warning^(s^) found
        echo.
        echo You can proceed with deployment, but you may need to:
        echo   - Add secrets\gsc_sa.json with your GCP credentials
        echo   - Configure .env with your project settings
        echo.
        echo Run: deploy.bat
    )
) else (
    echo !errors! error^(s^) found
    echo.
    echo Please fix the errors above before deploying.
    echo.
)

if !warnings! gtr 0 (
    echo.
    echo Warnings:
    echo   - Missing secrets will use placeholders (won't connect to real data)
    echo   - Missing .env will be created from .env.example
    echo.
)

pause
