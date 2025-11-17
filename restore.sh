#!/bin/bash
# GSC Warehouse - Database Restore
# Restores database from a backup file

set -e

if [ -z "$1" ]; then
    echo "Usage: restore.sh <backup-file>"
    echo
    echo "Example:"
    echo "  ./restore.sh backups/gsc_warehouse_20241113.sql"
    echo "  ./restore.sh backups/gsc_warehouse_20241113.sql.gz"
    echo
    echo "Available backups:"
    if [ -d backups ]; then
        ls -1 backups/*.sql backups/*.sql.gz 2>/dev/null || echo "  No backups found"
    else
        echo "  No backups directory found"
    fi
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "=========================================="
echo "GSC Warehouse Database Restore"
echo "=========================================="
echo
echo "WARNING: This will replace all data in the warehouse!"
echo
read -p "Are you sure you want to continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Check if warehouse is running
if ! docker compose ps warehouse | grep -q "Up"; then
    echo "ERROR: Warehouse is not running"
    echo "Run: docker compose up -d warehouse"
    exit 1
fi

echo
echo "Stopping scheduler..."
docker compose stop scheduler >/dev/null 2>&1 || true

# Check if file is compressed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Decompressing backup..."
    gunzip -k "$BACKUP_FILE"
    SQL_FILE="${BACKUP_FILE%.gz}"
else
    SQL_FILE="$BACKUP_FILE"
fi

echo "Restoring database from: $SQL_FILE"
echo

# Restore database
docker compose exec -T warehouse psql -U gsc_user gsc_db < "$SQL_FILE"

if [ $? -ne 0 ]; then
    echo "ERROR: Restore failed"
    docker compose start scheduler >/dev/null 2>&1 || true
    exit 1
fi

# Clean up decompressed file if it was compressed
if [ "$SQL_FILE" != "$BACKUP_FILE" ]; then
    rm -f "$SQL_FILE"
fi

echo
echo "Restarting scheduler..."
docker compose start scheduler >/dev/null 2>&1 || true

echo
echo "Restore completed successfully"
echo
echo "Verify data:"
echo "  docker compose exec warehouse psql -U gsc_user -d gsc_db -c \"SELECT COUNT(*) FROM gsc.fact_gsc_daily;\""
