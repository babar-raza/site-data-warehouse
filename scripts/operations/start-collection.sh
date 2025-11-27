#!/bin/bash
# Quick Start Script - Runs complete data collection pipeline
# This script starts all services and initiates data collection

set -e

echo "========================================"
echo "GSC Data Warehouse - Quick Start"
echo "========================================"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker."
    exit 1
fi

echo "Step 1: Starting core services..."
docker compose up -d warehouse mcp
echo "Waiting for services to be ready..."
sleep 20

echo ""
echo "Step 2: Running BigQuery extraction..."
docker compose --profile ingestion run --rm bq_extractor python bq_extractor.py || echo "WARNING: BigQuery extraction had issues. Check logs."

echo ""
echo "Step 3: Running API ingestion..."
docker compose --profile ingestion run --rm api_ingestor python gsc_api_ingestor.py || echo "WARNING: API ingestion had issues. Check logs."

echo ""
echo "Step 4: Applying transforms..."
docker compose --profile transform run --rm transformer python apply_transforms.py || echo "WARNING: Transform application had issues. Check logs."

echo ""
echo "Step 5: Starting continuous services..."
docker compose --profile scheduler up -d scheduler
docker compose --profile api up -d insights_api
# Note: Prometheus, Grafana, and metrics_exporter start automatically with docker-compose up

echo ""
echo "========================================"
echo "Pipeline is now running!"
echo "========================================"
echo ""
echo "Services available:"
echo "  - Warehouse: localhost:5432"
echo "  - MCP Server: localhost:8000"
echo "  - Insights API: localhost:8001"
echo "  - Prometheus: localhost:9090"
echo "  - Grafana: localhost:3000"
echo "  - Metrics Exporter: localhost:8002"
echo ""
echo "The scheduler will now run:"
echo "  - Daily ingestion at 02:00 UTC"
echo "  - Weekly reconciliation on Sundays at 03:00 UTC"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop: docker compose down"
echo ""
