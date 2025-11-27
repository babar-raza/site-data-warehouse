#!/bin/bash
# Docker Deployment Script with Resource Limits
# Deploys containers with proper resource constraints

set -e

echo "=========================================="
echo "Docker Deployment with Resource Limits"
echo "=========================================="
echo ""

# Configuration
PROFILE="${1:-core}"
REBUILD="${2:-false}"

echo "Profile: $PROFILE"
echo "Rebuild: $REBUILD"
echo ""

# Stop existing containers
echo "1. Stopping existing containers..."
docker-compose down

# Clean up old containers/images if rebuilding
if [ "$REBUILD" = "rebuild" ]; then
    echo "2. Removing old images..."
    docker-compose rm -f
    docker image prune -f
fi

# Build images
echo "3. Building images..."
docker-compose build --parallel

# Start services with resource limits
echo "4. Starting services with profile: $PROFILE..."
docker-compose --profile $PROFILE up -d

# Wait for health checks
echo ""
echo "5. Waiting for services to be healthy..."
sleep 10

# Show status
echo ""
echo "=========================================="
echo "Deployment Status"
echo "=========================================="
docker-compose ps

# Show resource usage
echo ""
echo "=========================================="
echo "Container Resource Usage"
echo "=========================================="
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "To view logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo "To cleanup: ./scripts/docker-cleanup.sh"
