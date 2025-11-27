#!/bin/bash
# =============================================
# GSC WAREHOUSE - BUILD ALL IMAGES
# =============================================
# Enterprise-grade Docker image build script
# Usage:
#   ./build-images.sh [dev|prod] [--gpu] [--no-cache]
#
# Examples:
#   ./build-images.sh dev              # CPU-only builds (smaller images)
#   ./build-images.sh prod             # CPU-only production builds
#   ./build-images.sh prod --gpu       # GPU-enabled builds (for NVIDIA systems)
#   ./build-images.sh prod --no-cache  # Force rebuild without cache
#   ./build-images.sh prod --gpu --no-cache
#
# GPU vs CPU PyTorch Selection:
#   - Default (no --gpu): CPU-only PyTorch (~2.75GB insights_engine)
#   - With --gpu: CUDA 12.4 PyTorch (~10GB insights_engine)
#
# Use --gpu only if you have NVIDIA GPU with CUDA drivers installed

set -euo pipefail

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Default values
ENV_TYPE="${1:-dev}"
USE_GPU="false"
NO_CACHE_FLAG=""

# Parse arguments
shift || true
while [ $# -gt 0 ]; do
    case "$1" in
        --gpu)
            USE_GPU="true"
            ;;
        --no-cache)
            NO_CACHE_FLAG="--no-cache"
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE} GSC WAREHOUSE - DOCKER BUILD SCRIPT${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Environment: ${YELLOW}${ENV_TYPE}${NC}"
echo -e "BuildKit: ${GREEN}Enabled${NC}"
if [ "$USE_GPU" = "true" ]; then
    echo -e "PyTorch: ${YELLOW}GPU (CUDA 12.4)${NC}"
else
    echo -e "PyTorch: ${GREEN}CPU-only (smaller images)${NC}"
fi
if [ -n "$NO_CACHE_FLAG" ]; then
    echo -e "Cache: ${RED}Disabled${NC}"
fi
echo ""

# Check Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running${NC}"
    exit 1
fi

# Step 1: Build base image
echo ""
echo -e "${BLUE}[1/3] Building shared base image...${NC}"
echo ""

docker build \
    --target base-runtime \
    -t gsc-base:latest \
    -f compose/dockerfiles/Dockerfile.base \
    $NO_CACHE_FLAG \
    .

echo -e "${GREEN}✓ Base image build successful${NC}"

# Step 2: Build ML service images with GPU/CPU selection
echo ""
echo -e "${BLUE}[2/4] Building ML services (insights_engine, celery)...${NC}"
echo ""

GPU_BUILD_ARG=""
if [ "$USE_GPU" = "true" ]; then
    GPU_BUILD_ARG="--build-arg USE_GPU=true"
    echo -e "Building with ${YELLOW}GPU/CUDA support${NC}..."
else
    echo -e "Building with ${GREEN}CPU-only PyTorch${NC}..."
fi

# Build insights_engine
echo -e "${BLUE}  → Building insights_engine...${NC}"
docker build \
    --target runtime \
    $GPU_BUILD_ARG \
    -t site-data-warehouse-insights_engine:latest \
    -f compose/dockerfiles/Dockerfile.insights_engine \
    $NO_CACHE_FLAG \
    .

# Build celery worker
echo -e "${BLUE}  → Building celery worker...${NC}"
docker build \
    --target runtime \
    $GPU_BUILD_ARG \
    -t site-data-warehouse-celery:latest \
    -f compose/dockerfiles/Dockerfile.celery \
    $NO_CACHE_FLAG \
    .

echo -e "${GREEN}✓ ML services build successful${NC}"

# Step 3: Build remaining service images
echo ""
echo -e "${BLUE}[3/4] Building remaining services in parallel...${NC}"
echo ""

if [ "$ENV_TYPE" = "prod" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml build --parallel $NO_CACHE_FLAG
else
    docker compose -f docker-compose.yml -f docker-compose.dev.yml build --parallel $NO_CACHE_FLAG
fi

echo -e "${GREEN}✓ Service images build successful${NC}"

# Step 4: Show summary
echo ""
echo -e "${BLUE}[4/4] Build Summary${NC}"
echo ""

echo -e "${BLUE}Base Image:${NC}"
docker images gsc-base --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

echo ""
echo -e "${BLUE}ML Services (insights_engine, celery):${NC}"
docker images site-data-warehouse-insights_engine --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
docker images site-data-warehouse-celery --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null || true

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN} BUILD COMPLETED SUCCESSFULLY${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
if [ "$USE_GPU" = "true" ]; then
    echo -e "${YELLOW}GPU Mode:${NC} Images include CUDA 12.4 support"
    echo -e "  To run with GPU: docker run --gpus all <image>"
else
    echo -e "${GREEN}CPU Mode:${NC} Smaller images without GPU dependencies"
fi
echo ""
echo "Next steps:"
if [ "$ENV_TYPE" = "dev" ]; then
    echo "  1. Start services: docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up"
    echo "  2. View logs: docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f"
else
    echo "  1. Start services: docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile core up -d"
    echo "  2. View logs: docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f"
fi
echo "  3. Stop services: docker compose down"
echo ""
echo "To rebuild with GPU support: ./build-images.sh $ENV_TYPE --gpu"
echo ""
