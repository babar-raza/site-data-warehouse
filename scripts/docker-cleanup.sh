#!/bin/bash
# Docker Cleanup Script
# Removes unused containers, images, volumes, and build cache
# to prevent massive storage growth

set -e

echo "=========================================="
echo "Docker Cleanup Script"
echo "=========================================="
echo ""

# Stop and remove all containers
echo "1. Stopping all containers..."
docker-compose down --remove-orphans || true

# Remove stopped containers
echo "2. Removing stopped containers..."
docker container prune -f

# Remove dangling images
echo "3. Removing dangling images..."
docker image prune -f

# Remove unused volumes (WARNING: This removes ALL unused volumes)
echo "4. Removing unused volumes..."
read -p "Remove unused volumes? This may delete data! (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker volume prune -f
    echo "  ✓ Volumes cleaned"
else
    echo "  ✗ Skipped volume cleanup"
fi

# Remove build cache (keeps last 24 hours)
echo "5. Removing old build cache..."
docker builder prune -f --filter "until=24h"

# Remove networks
echo "6. Removing unused networks..."
docker network prune -f

# Show current usage
echo ""
echo "=========================================="
echo "Current Docker Disk Usage"
echo "=========================================="
docker system df

# Advanced cleanup (optional)
echo ""
read -p "Run aggressive cleanup? This removes ALL unused data! (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Running aggressive cleanup..."
    docker system prune -a -f --volumes
    echo "  ✓ Aggressive cleanup complete"
fi

echo ""
echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
docker system df
