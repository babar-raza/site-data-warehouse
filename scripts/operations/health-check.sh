#!/bin/bash
# Health Check Script - Checks status of all services

echo "========================================"
echo "GSC Data Warehouse - Health Check"
echo "========================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running"
    exit 1
fi

echo "[Docker] Running ✓"
echo ""

echo "Checking container status..."
echo ""
docker compose ps

echo ""
echo "----------------------------------------"
echo "Service Health Checks"
echo "----------------------------------------"
echo ""

# Check Warehouse
echo "Checking Warehouse (PostgreSQL)..."
if docker compose exec -T warehouse pg_isready -U gsc_user -d gsc_db > /dev/null 2>&1; then
    echo "  [WAREHOUSE] ✓ Healthy"
else
    echo "  [WAREHOUSE] ❌ Not responding"
fi

# Check Insights API
echo "Checking Insights API..."
if curl -s -f http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  [INSIGHTS API] ✓ Healthy"
else
    echo "  [INSIGHTS API] ⚠ Not running or not healthy (optional service)"
fi

# Check MCP Server
echo "Checking MCP Server..."
if curl -s -f http://localhost:8001/health > /dev/null 2>&1; then
    echo "  [MCP SERVER] ✓ Healthy"
else
    echo "  [MCP SERVER] ❌ Not responding"
fi

# Check Metrics Exporter
echo "Checking Metrics Exporter..."
if curl -s -f http://localhost:9090/health > /dev/null 2>&1; then
    echo "  [METRICS] ✓ Healthy"
else
    echo "  [METRICS] ⚠ Not running or not healthy (optional service)"
fi

# Check Prometheus
echo "Checking Prometheus..."
if curl -s -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "  [PROMETHEUS] ✓ Healthy"
else
    echo "  [PROMETHEUS] ❌ Not responding"
fi

# Check Grafana
echo "Checking Grafana..."
if curl -s -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "  [GRAFANA] ✓ Healthy"
else
    echo "  [GRAFANA] ❌ Not responding"
fi

echo ""
echo "----------------------------------------"
echo "Data Warehouse Statistics"
echo "----------------------------------------"
echo ""

docker compose exec -T warehouse psql -U gsc_user -d gsc_db -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'gsc' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;" 2>/dev/null || echo "Unable to fetch database statistics"

echo ""
echo "----------------------------------------"
echo "Recent Logs (last 50 lines)"
echo "----------------------------------------"
echo ""
docker compose logs --tail=50

echo ""
echo "Health check complete."
echo ""
