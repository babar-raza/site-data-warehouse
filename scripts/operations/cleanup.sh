#!/bin/bash
# Cleanup Script - Stops and removes all containers, networks, and volumes
# WARNING: This will delete all data in the warehouse!

echo "========================================"
echo "GSC Data Warehouse - Cleanup"
echo "========================================"
echo ""
echo "WARNING: This will stop all services and delete all data!"
echo ""
read -p "Are you sure you want to continue? (yes/NO): " confirm
if [ "${confirm,,}" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Stopping all services..."
docker compose --profile ingestion --profile transform --profile scheduler --profile api --profile observability down

echo ""
echo "Removing volumes (this will delete all data)..."
docker compose down -v

echo ""
echo "Removing Docker images..."
docker rmi gsc-bq-extractor:latest 2>/dev/null || true
docker rmi gsc-api-ingestor:latest 2>/dev/null || true
docker rmi gsc-transformer:latest 2>/dev/null || true
docker rmi gsc-mcp-server:latest 2>/dev/null || true
docker rmi gsc-insights-api:latest 2>/dev/null || true
docker rmi gsc-scheduler:latest 2>/dev/null || true
docker rmi gsc-metrics-exporter:latest 2>/dev/null || true

echo ""
echo "Cleaning up logs..."
if [ -d "logs" ]; then
    rm -f logs/* 2>/dev/null || true
fi

echo ""
echo "========================================"
echo "Cleanup Complete!"
echo "========================================"
echo ""
echo "All containers, volumes, and images have been removed."
echo "To start fresh, run ./deploy.sh"
echo ""
