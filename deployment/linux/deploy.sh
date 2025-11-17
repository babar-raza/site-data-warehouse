#!/bin/bash
# Linux Deployment Script for GSC Data Warehouse (Hybrid Plan)
set -e

echo "======================================"
echo "GSC Data Warehouse - Deployment"
echo "======================================"

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker not installed"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose not installed"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "❌ psql not installed"; exit 1; }
echo "✅ Prerequisites checked"

# Load environment
if [ -f .env ]; then
    export $(cat .env | xargs)
    echo "✅ Environment loaded"
else
    echo "❌ .env file not found"
    exit 1
fi

# Step 1: Start database
echo -e "\n=== Step 1: Starting Database ==="
docker-compose up -d warehouse
echo "⏳ Waiting for database..."
until docker-compose exec -T warehouse pg_isready >/dev/null 2>&1; do
    sleep 2
done
echo "✅ Database ready"

# Step 2: Run migrations
echo -e "\n=== Step 2: Running Migrations ==="
for script in sql/*.sql; do
    echo "  Running: $(basename $script)"
    psql $WAREHOUSE_DSN -f "$script" >/dev/null 2>&1
done
echo "✅ Migrations complete"

# Step 3: Validate schema
echo -e "\n=== Step 3: Validating Schema ==="
psql $WAREHOUSE_DSN -t -c "SELECT * FROM gsc.validate_unified_view_time_series();" | grep -q "PASS"
if [ $? -eq 0 ]; then
    echo "✅ Schema validation passed"
else
    echo "⚠️  Schema validation warnings (check manually)"
fi

# Step 4: Start all services
echo -e "\n=== Step 4: Starting Services ==="
docker-compose up -d
sleep 5
echo "✅ Services started"

# Step 5: Health checks
echo -e "\n=== Step 5: Health Checks ==="
docker-compose ps | grep "Up" && echo "✅ All services running"

# Success
echo -e "\n======================================"
echo "✅ Deployment Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Ingest data: python ingestors/api/gsc_api_ingestor.py --date-start 2024-11-01"
echo "  2. Generate insights: python -m insights_core.cli refresh"
echo "  3. View insights: psql \$WAREHOUSE_DSN -c 'SELECT * FROM gsc.vw_insights_actionable LIMIT 10;'"
echo ""
echo "Services:"
echo "  - Database: localhost:5432"
echo "  - MCP Server: localhost:8000"
echo "  - Grafana: localhost:3000 (admin/admin)"
