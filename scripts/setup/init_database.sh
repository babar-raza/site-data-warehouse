#!/bin/bash
# ============================================================================
# Database Initialization Script
# ============================================================================
# This script initializes the PostgreSQL database with all required schemas
# Run this after creating the database

set -e  # Exit on error

# Colors for output
RED='\033[0:31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-seo_warehouse}"
DB_USER="${POSTGRES_USER:-postgres}"
SQL_DIR="sql"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SEO Intelligence Platform${NC}"
echo -e "${GREEN}Database Initialization${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Function to print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    print_error "psql command not found. Please install PostgreSQL client tools."
    exit 1
fi

print_success "PostgreSQL client found"

# Test database connection
echo ""
echo "Testing database connection..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "SELECT 1" > /dev/null 2>&1; then
    print_success "Database connection successful"
else
    print_error "Cannot connect to database. Please check your credentials."
    exit 1
fi

# Create database if it doesn't exist
echo ""
echo "Checking if database exists..."
DB_EXISTS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")

if [ "$DB_EXISTS" != "1" ]; then
    echo "Creating database: $DB_NAME"
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"
    print_success "Database created: $DB_NAME"
else
    print_warning "Database already exists: $DB_NAME"
fi

# Enable extensions
echo ""
echo "Enabling PostgreSQL extensions..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
print_success "Extension enabled: vector"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
print_success "Extension enabled: pg_trgm"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
print_success "Extension enabled: uuid-ossp"

# Run SQL schema files in order
echo ""
echo "Running SQL schema files..."

SQL_FILES=(
    "00_extensions.sql"
    "01_base_schema.sql"
    "02_gsc_schema.sql"
    "03_ga4_schema.sql"
    "04_session_stitching.sql"
    "05_unified_view.sql"
    "12_actions_schema.sql"
    "13_content_schema.sql"
    "14_forecasts_schema.sql"
    "16_serp_schema.sql"
    "17_performance_schema.sql"
    "18_analytics_schema.sql"
    "20_notifications_schema.sql"
    "21_orchestration_schema.sql"
    "22_anomaly_schema.sql"
)

for sql_file in "${SQL_FILES[@]}"; do
    if [ -f "$SQL_DIR/$sql_file" ]; then
        echo "  Running: $sql_file"
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_DIR/$sql_file" > /dev/null 2>&1; then
            print_success "$sql_file executed successfully"
        else
            print_error "Failed to execute $sql_file"
            exit 1
        fi
    else
        print_warning "File not found: $SQL_DIR/$sql_file (skipping)"
    fi
done

# Verify schemas
echo ""
echo "Verifying schemas..."
SCHEMA_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "
    SELECT COUNT(*) FROM information_schema.schemata
    WHERE schema_name IN ('gsc', 'ga4', 'base', 'serp', 'performance', 'notifications', 'orchestration', 'anomaly')
")

echo "  Found $SCHEMA_COUNT schemas"
if [ "$SCHEMA_COUNT" -ge "8" ]; then
    print_success "All required schemas created"
else
    print_warning "Some schemas may be missing (found $SCHEMA_COUNT, expected 8+)"
fi

# Verify tables
echo ""
echo "Verifying tables..."
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
")

echo "  Found $TABLE_COUNT tables"
if [ "$TABLE_COUNT" -ge "40" ]; then
    print_success "Tables created successfully"
else
    print_warning "Table count lower than expected (found $TABLE_COUNT, expected 40+)"
fi

# Run VACUUM ANALYZE
echo ""
echo "Optimizing database..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "VACUUM ANALYZE;" > /dev/null 2>&1
print_success "Database optimized"

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Database Initialization Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "Schemas: $SCHEMA_COUNT"
echo "Tables: $TABLE_COUNT"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "1. Configure environment variables (.env file)"
echo "2. Run data seeding script: ./scripts/setup/seed_data.py"
echo "3. Start services: ./scripts/setup/start_services.sh"
echo ""
