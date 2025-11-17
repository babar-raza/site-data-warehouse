@echo off
REM Backup database
set BACKUP_DIR=backups\%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set BACKUP_DIR=%BACKUP_DIR: =0%
mkdir %BACKUP_DIR%

echo Creating backup...
docker-compose exec -T warehouse pg_dump -U gsc_user gsc_db | gzip > "%BACKUP_DIR%\database.sql.gz"
echo ✅ Backup created: %BACKUP_DIR%\database.sql.gz
