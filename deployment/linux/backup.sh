#!/bin/bash
# Backup database
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "Creating backup..."
docker-compose exec -T warehouse pg_dump -U gsc_user gsc_db | gzip > "$BACKUP_DIR/database.sql.gz"
echo "✅ Backup created: $BACKUP_DIR/database.sql.gz"
