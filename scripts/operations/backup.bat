@echo off
REM GSC Warehouse - Database Backup (Windows)
REM Creates a compressed backup of the warehouse database

setlocal enabledelayedexpansion

REM Create backups directory
if not exist backups mkdir backups

REM Generate timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%

set BACKUP_FILE=backups\gsc_warehouse_%TIMESTAMP%.sql
set BACKUP_GZ=%BACKUP_FILE%.gz

echo ==========================================
echo GSC Warehouse Database Backup
echo ==========================================
echo.

REM Check if warehouse is running
docker compose ps warehouse | findstr "Up" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Warehouse is not running[0m
    echo Run: docker compose up -d warehouse
    exit /b 1
)

echo Creating backup: %BACKUP_FILE%
echo.

REM Stop scheduler to prevent writes during backup
echo Stopping scheduler...
docker compose stop scheduler >nul 2>&1

REM Create backup
docker compose exec -T warehouse pg_dump -U gsc_user gsc_db > %BACKUP_FILE%

if !ERRORLEVEL! NEQ 0 (
    echo [31mERROR: Backup failed[0m
    docker compose start scheduler >nul 2>&1
    exit /b 1
)

REM Compress backup (if gzip is available)
where gzip >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo Compressing backup...
    gzip %BACKUP_FILE%
    set FINAL_FILE=%BACKUP_GZ%
) else (
    echo [33mWARNING: gzip not found, backup not compressed[0m
    set FINAL_FILE=%BACKUP_FILE%
)

REM Restart scheduler
docker compose start scheduler >nul 2>&1

echo.
echo [32mBackup completed successfully[0m
echo.
echo Backup file: %FINAL_FILE%
for %%A in ("%FINAL_FILE%") do echo Backup size: %%~zA bytes
echo.
echo To restore this backup:
echo   gunzip %FINAL_FILE% (if compressed)
echo   docker compose exec -T warehouse psql -U gsc_user gsc_db ^< backups\gsc_warehouse_%TIMESTAMP%.sql

endlocal
