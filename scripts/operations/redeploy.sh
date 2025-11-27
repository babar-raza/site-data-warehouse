#!/bin/bash
# GSC Warehouse - Redeployment Script
# Updates the system without data loss

set -e

echo "=========================================="
echo "GSC Warehouse Redeployment"
echo "=========================================="
echo

# Parse options
SKIP_DATA_COLLECTION=false
SKIP_BUILD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-data-collection)
            SKIP_DATA_COLLECTION=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo
            echo "Options:"
            echo "  --skip-data-collection    Skip running data collection"
            echo "  --skip-build             Skip rebuilding Docker images"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Stop running services (but keep database and data volumes)
echo "[1/5] Stopping services..."
docker compose stop scheduler api_ingestor transformer metrics_exporter prometheus mcp insights_api startup_orchestrator 2>/dev/null || true
echo "✓ Services stopped"

# Remove old containers (but preserve volumes)
echo
echo "[2/5] Removing old containers..."
docker compose rm -f scheduler api_ingestor transformer metrics_exporter prometheus mcp insights_api startup_orchestrator 2>/dev/null || true
echo "✓ Old containers removed"

# Rebuild images if not skipped
if [ "$SKIP_BUILD" = false ]; then
    echo
    echo "[3/5] Rebuilding Docker images..."
    docker compose build --no-cache
    echo "✓ Images rebuilt"
else
    echo
    echo "[3/5] Skipping image rebuild (--skip-build)"
fi

# Start core services
echo
echo "[4/5] Starting services..."
docker compose up -d warehouse mcp

echo "Waiting for services to be ready..."
sleep 5

# Verify warehouse is healthy
max_attempts=30
for i in $(seq 1 $max_attempts); do
    if docker compose exec -T warehouse pg_isready -U gsc_user -d gsc_db > /dev/null 2>&1; then
        echo "✓ Warehouse is ready"
        break
    fi
    if [ $i -eq $max_attempts ]; then
        echo "ERROR: Warehouse failed to become ready"
        exit 1
    fi
    sleep 2
done

# Optionally run data collection
if [ "$SKIP_DATA_COLLECTION" = false ]; then
    echo
    echo "[5/5] Running data refresh..."
    
    # Run a quick data refresh (only recent days)
    export INGEST_DAYS=7
    export RUN_INITIAL_COLLECTION=true
    docker compose run --rm -e INGEST_DAYS=7 -e RUN_INITIAL_COLLECTION=true startup_orchestrator
    
    if [ $? -eq 0 ]; then
        echo "✓ Data refresh completed"
    else
        echo "WARNING: Data refresh had issues (check logs)"
    fi
else
    echo
    echo "[5/5] Skipping data collection (--skip-data-collection)"
fi

# Start scheduler
echo
echo "Starting scheduler..."
docker compose --profile scheduler up -d scheduler

echo
echo "=========================================="
echo "Redeployment Complete!"
echo "=========================================="
echo
echo "Services running:"
docker compose ps
echo
echo "Check data freshness:"
echo "  docker compose exec warehouse psql -U gsc_user -d gsc_db -c \"SELECT MAX(date) FROM gsc.fact_gsc_daily;\""
echo
echo "View logs:"
echo "  docker compose logs -f"
echo
