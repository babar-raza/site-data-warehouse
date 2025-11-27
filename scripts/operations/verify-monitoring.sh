#!/bin/bash

# ============================================
# Prometheus Monitoring Verification Script
# ============================================
# Verifies all monitoring components are working
# - Prometheus
# - Grafana
# - Exporters (cAdvisor, PostgreSQL, Redis)
# - Dashboards
# - Alert Rules
# ============================================

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Prometheus Monitoring Verification"
echo "========================================"
echo ""

# Check if Docker is running
echo -e "${BLUE}[1/10] Checking Docker status...${NC}"
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    echo "Please start Docker and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Check containers
echo -e "${BLUE}[2/10] Checking monitoring containers...${NC}"
CONTAINERS="gsc_prometheus gsc_grafana gsc_cadvisor gsc_postgres_exporter gsc_metrics_exporter"
for container in $CONTAINERS; do
    if docker ps --filter "name=$container" --filter "status=running" --format "{{.Names}}" | grep -q "$container"; then
        echo -e "${GREEN}✓ Container $container is running${NC}"
    else
        echo -e "${RED}✗ Container $container is not running${NC}"
    fi
done
echo ""

# Check Redis exporter (optional - intelligence profile)
echo -e "${BLUE}[3/10] Checking optional containers...${NC}"
if docker ps --filter "name=gsc_redis_exporter" --filter "status=running" --format "{{.Names}}" | grep -q "gsc_redis_exporter"; then
    echo -e "${GREEN}✓ Redis exporter is running${NC}"
else
    echo -e "${YELLOW}⚠ Redis exporter not running (requires intelligence profile)${NC}"
fi
echo ""

# Check Prometheus endpoint
echo -e "${BLUE}[4/10] Checking Prometheus endpoint...${NC}"
if curl -s http://localhost:9090/-/healthy >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Prometheus is healthy${NC}"
else
    echo -e "${RED}✗ Prometheus endpoint not responding${NC}"
fi
echo ""

# Check Grafana endpoint
echo -e "${BLUE}[5/10] Checking Grafana endpoint...${NC}"
if curl -s http://localhost:3000/api/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Grafana is healthy${NC}"
else
    echo -e "${RED}✗ Grafana endpoint not responding${NC}"
fi
echo ""

# Check Prometheus targets
echo -e "${BLUE}[6/10] Checking Prometheus targets...${NC}"
if curl -s http://localhost:9090/api/v1/targets 2>/dev/null | grep -q '"health":"up"'; then
    echo -e "${GREEN}✓ Prometheus targets are up${NC}"
else
    echo -e "${YELLOW}⚠ Some Prometheus targets may be down${NC}"
    echo "   Check: http://localhost:9090/targets"
fi
echo ""

# Check exporter endpoints
echo -e "${BLUE}[7/10] Checking exporter endpoints...${NC}"

# cAdvisor
if curl -s http://localhost:8080/metrics 2>/dev/null | grep -q "container_cpu"; then
    echo -e "${GREEN}✓ cAdvisor metrics available${NC}"
else
    echo -e "${RED}✗ cAdvisor metrics not available${NC}"
fi

# PostgreSQL Exporter
if curl -s http://localhost:9187/metrics 2>/dev/null | grep -q "pg_stat"; then
    echo -e "${GREEN}✓ PostgreSQL exporter metrics available${NC}"
else
    echo -e "${RED}✗ PostgreSQL exporter metrics not available${NC}"
fi

# Redis Exporter (optional)
if curl -s http://localhost:9121/metrics 2>/dev/null | grep -q "redis_"; then
    echo -e "${GREEN}✓ Redis exporter metrics available${NC}"
else
    echo -e "${YELLOW}⚠ Redis exporter metrics not available (requires intelligence profile)${NC}"
fi
echo ""

# Check alert rules
echo -e "${BLUE}[8/10] Checking Prometheus alert rules...${NC}"
if curl -s http://localhost:9090/api/v1/rules 2>/dev/null | grep -q '"groups"'; then
    echo -e "${GREEN}✓ Alert rules loaded${NC}"
    # Count rule groups
    curl -s http://localhost:9090/api/v1/rules 2>/dev/null | grep -q "infrastructure_alerts" && echo "   - infrastructure_alerts loaded"
    curl -s http://localhost:9090/api/v1/rules 2>/dev/null | grep -q "database_alerts" && echo "   - database_alerts loaded"
    curl -s http://localhost:9090/api/v1/rules 2>/dev/null | grep -q "redis_alerts" && echo "   - redis_alerts loaded"
    curl -s http://localhost:9090/api/v1/rules 2>/dev/null | grep -q "prometheus_alerts" && echo "   - prometheus_alerts loaded"
else
    echo -e "${RED}✗ Alert rules not loaded${NC}"
fi
echo ""

# Check Grafana datasource
echo -e "${BLUE}[9/10] Checking Grafana datasource...${NC}"
if curl -s -u admin:admin http://localhost:3000/api/datasources 2>/dev/null | grep -q "Prometheus"; then
    echo -e "${GREEN}✓ Prometheus datasource configured${NC}"
else
    echo -e "${RED}✗ Prometheus datasource not configured in Grafana${NC}"
fi
echo ""

# Check dashboards
echo -e "${BLUE}[10/10] Checking Grafana dashboards...${NC}"
DASHBOARDS="infrastructure-overview database-performance application-metrics service-health alert-status"
for dashboard in $DASHBOARDS; do
    if [ -f "grafana/provisioning/dashboards/${dashboard}.json" ]; then
        echo -e "${GREEN}✓ Dashboard ${dashboard}.json exists${NC}"
    else
        echo -e "${RED}✗ Dashboard ${dashboard}.json not found${NC}"
    fi
done
echo ""

# Summary
echo "========================================"
echo "Verification Summary"
echo "========================================"
echo ""
echo -e "${GREEN}Monitoring system verification complete!${NC}"
echo ""
echo "Next steps:"
echo "   1. Open Grafana: http://localhost:3000"
echo "   2. Login (admin/admin)"
echo "   3. Browse dashboards"
echo "   4. Check Prometheus: http://localhost:9090"
echo "   5. Review targets: http://localhost:9090/targets"
echo "   6. Review alerts: http://localhost:9090/alerts"
echo ""
echo "Documentation:"
echo "   - Dashboard Guide: docs/guides/PROMETHEUS_DASHBOARDS_GUIDE.md"
echo "   - Deployment Guide: docs/DEPLOYMENT.md"
echo "   - Troubleshooting: docs/TROUBLESHOOTING.md"
echo ""
