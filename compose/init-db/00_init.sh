#!/bin/bash
# This script is automatically run by Postgres Docker container on first startup

echo "Initializing GSC Warehouse Database..."

# The POSTGRES_USER and POSTGRES_DB are already set by Docker environment
# Just need to run our schema creation

# Copy SQL files to a temp location (optional, for logging)
cp /docker-entrypoint-initdb.d/*.sql /tmp/ 2>/dev/null || true

echo "Database initialization complete!"
