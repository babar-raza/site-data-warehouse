#!/bin/bash
# GSC Warehouse - Manual Data Collection
# Trigger on-demand data collection

set -e

INGEST_DAYS=30

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --days)
            INGEST_DAYS="$2"
            shift 2
            ;;
        --full)
            INGEST_DAYS=480
            shift
            ;;
        --help)
            echo "Usage: manual-collection.sh [options]"
            echo
            echo "Options:"
            echo "  --days N     Collect N days of data (default: 30)"
            echo "  --full       Collect full 16 months (480 days)"
            echo "  --help       Show this help message"
            echo
            echo "Examples:"
            echo "  ./manual-collection.sh              # Collect last 30 days"
            echo "  ./manual-collection.sh --days 7     # Collect last 7 days"
            echo "  ./manual-collection.sh --full       # Collect full 16 months"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "GSC Warehouse Manual Data Collection"
echo "=========================================="
echo
echo "Collecting last $INGEST_DAYS days of data..."
echo

# Check if warehouse is running
if ! docker compose ps warehouse | grep -q "Up"; then
    echo "ERROR: Warehouse is not running"
    echo "Run: docker compose up -d warehouse"
    exit 1
fi

# Run data collection
docker compose run --rm -e INGEST_DAYS=$INGEST_DAYS -e RUN_INITIAL_COLLECTION=true startup_orchestrator

if [ $? -eq 0 ]; then
    echo
    echo "Data collection completed successfully"
    echo
    echo "Check collected data:"
    echo "  docker compose exec warehouse psql -U gsc_user -d gsc_db -c \"SELECT COUNT(*) FROM gsc.fact_gsc_daily;\""
else
    echo
    echo "Data collection failed"
    echo "Check logs: docker compose logs startup_orchestrator"
    exit 1
fi
