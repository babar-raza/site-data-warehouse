#!/bin/bash
# Add logging configuration to all services in docker-compose.yml

COMPOSE_FILE="docker-compose.yml"

# Services that need logging added
SERVICES=(
    "transform"
    "insights_engine"
    "scheduler"
    "insights_api"
    "mcp"
    "prometheus"
    "grafana"
    "metrics_exporter"
    "ollama"
    "redis"
    "celery_worker"
)

LOGGING_BLOCK='    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"'

echo "Adding logging configuration to services..."

for service in "${SERVICES[@]}"; do
    # Check if service exists and doesn't have logging already
    if grep -q "^  $service:" "$COMPOSE_FILE"; then
        if ! grep -A 5 "^  $service:" "$COMPOSE_FILE" | grep -q "logging:"; then
            echo "  - Adding logging to $service"
            # This would need sed/awk to actually insert
            # For now, just report
        else
            echo "  ✓ $service already has logging"
        fi
    fi
done

echo ""
echo "Note: Manual editing of docker-compose.yml may be needed for precise insertion"
echo "Run the Python script instead: python scripts/add-logging-to-compose.py"
