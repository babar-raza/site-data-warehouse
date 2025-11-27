#!/bin/bash
# API-Only Deployment - No BigQuery Required

echo "========================================"
echo "GSC Warehouse - API-Only Deployment"
echo "========================================"
echo ""
echo "This deployment uses Search Console API only."
echo "No billing or BigQuery required."
echo ""

# Validate
./validate-setup.sh

echo ""
echo "Starting deployment..."
echo ""

# Build and start core services
docker compose build
docker compose up -d warehouse mcp

echo "Waiting for services..."
sleep 20

echo ""
echo "Running API ingestion (this may take 15-30 minutes for 16 months of data)..."
docker compose --profile ingestion run --rm api_ingestor python gsc_api_ingestor.py

echo ""
echo "Applying transforms..."
docker compose --profile transform run --rm transformer python apply_transforms.py

echo ""
echo "Starting scheduler (API ingestion will run daily at 02:00 UTC)..."
docker compose --profile scheduler up -d scheduler

echo ""
echo "Starting optional services..."
docker compose --profile api up -d insights_api
docker compose --profile observability up -d metrics_exporter prometheus

echo ""
echo "========================================"
echo "API-Only Deployment Complete!"
echo "========================================"
echo ""
echo "Services running:"
echo "  - Warehouse: localhost:5432"
echo "  - MCP Server: localhost:8000"
echo "  - Insights API: localhost:8001"
echo "  - Metrics: localhost:9090"
echo "  - Prometheus: localhost:9091"
echo ""
echo "Data collection: Last 16 months via API"
echo "Schedule: Daily updates at 02:00 UTC"
echo ""
