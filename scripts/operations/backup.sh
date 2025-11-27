#!/bin/bash
# GSC Warehouse - Database Backup
# Creates a compressed backup of the warehouse database

set -e

# Create backups directory
mkdir -p backups

# Generate timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backups/gsc_warehouse_${TIMESTAMP}.sql"
BACKUP_GZ="${BACKUP_FILE}.gz"

echo "=========================================="
echo "GSC Warehouse Database Backup"
echo "=========================================="
echo

# Check if warehouse is running
if ! docker compose ps warehouse | grep -q "Up"; then
    echo "ERROR: Warehouse is not running"
    echo "Run: docker compose up -d warehouse"
    exit 1
fi

echo "Creating backup: ${BACKUP_FILE}"
echo

# Stop scheduler to prevent writes during backup
echo "Stopping scheduler..."
docker compose stop scheduler >/dev/null 2>&1 || true

# Create backup
docker compose exec -T warehouse pg_dump -U gsc_user gsc_db > "${BACKUP_FILE}"

if [ $? -ne 0 ]; then
    echo "ERROR: Backup failed"
    docker compose start scheduler >/dev/null 2>&1 || true
    exit 1
fi

# Compress backup
echo "Compressing backup..."
gzip "${BACKUP_FILE}"

# Restart scheduler
docker compose start scheduler >/dev/null 2>&1 || true

echo
echo "Backup completed successfully"
echo
echo "Backup file: ${BACKUP_GZ}"
echo "Backup size: $(du -h ${BACKUP_GZ} | cut -f1)"
echo
echo "To restore this backup:"
echo "  gunzip ${BACKUP_GZ}"
echo "  docker compose exec -T warehouse psql -U gsc_user gsc_db < ${BACKUP_FILE}"
