@echo off
REM GSC Warehouse - Database Restore (Windows)
REM Restores database from a backup file

setlocal enabledelayedexpansion

if "%~1"=="" (
    echo Usage: restore.bat ^<backup-file^>
    echo.
    echo Example:
    echo   restore.bat backups\gsc_warehouse_20241113.sql
    echo   restore.bat backups\gsc_warehouse_20241113.sql.gz
    echo.
    echo Available backups:
    if exist backups (
        dir /b backups\*.sql backups\*.sql.gz 2>nul
    ) else (
        echo   No backups found
    )
    exit /b 1
)

set BACKUP_FILE=%~1

if not exist "%BACKUP_FILE%" (
    echo [31mERROR: Backup file not found: %BACKUP_FILE%[0m
    exit /b 1
)

echo ==========================================
echo GSC Warehouse Database Restore
echo ==========================================
echo.
echo [33mWARNING: This will replace all data in the warehouse![0m
echo.
set /p CONFIRM="Are you sure you want to continue? (yes/no): "
if /i not "%CONFIRM%"=="yes" (
    echo Restore cancelled
    exit /b 0
)

REM Check if warehouse is running
docker compose ps warehouse | findstr "Up" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Warehouse is not running[0m
    echo Run: docker compose up -d warehouse
    exit /b 1
)

echo.
echo Stopping scheduler...
docker compose stop scheduler >nul 2>&1

REM Check if file is compressed
echo %BACKUP_FILE% | findstr /i ".gz$" >nul
if !ERRORLEVEL! EQU 0 (
    echo Decompressing backup...
    
    where gunzip >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo [31mERROR: gunzip not found[0m
        echo Please install gzip or decompress manually
        docker compose start scheduler >nul 2>&1
        exit /b 1
    )
    
    gunzip -k "%BACKUP_FILE%"
    set SQL_FILE=%BACKUP_FILE:~0,-3%
) else (
    set SQL_FILE=%BACKUP_FILE%
)

echo Restoring database from: %SQL_FILE%
echo.

REM Restore database
docker compose exec -T warehouse psql -U gsc_user gsc_db < "%SQL_FILE%"

if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Restore failed[0m
    docker compose start scheduler >nul 2>&1
    exit /b 1
)

REM Clean up decompressed file if it was compressed
if not "%SQL_FILE%"=="%BACKUP_FILE%" (
    del "%SQL_FILE%" 2>nul
)

echo.
echo Restarting scheduler...
docker compose start scheduler >nul 2>&1

echo.
echo [32mRestore completed successfully[0m
echo.
echo Verify data:
echo   docker compose exec warehouse psql -U gsc_user -d gsc_db -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"

endlocal
