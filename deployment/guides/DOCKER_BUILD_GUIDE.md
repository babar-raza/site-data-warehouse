# Docker Build Guide

## Overview

This guide covers building Docker images for the Site Data Warehouse project, including **GPU vs CPU PyTorch selection** for ML services.

## Quick Start

### Build All Images (Recommended)

**Linux/macOS:**
```bash
# CPU-only (smaller images, default)
./scripts/build-images.sh dev

# GPU-enabled (for NVIDIA systems)
./scripts/build-images.sh prod --gpu
```

**Windows:**
```cmd
REM CPU-only (smaller images, default)
scripts\build-images.bat dev

REM GPU-enabled (for NVIDIA systems)
scripts\build-images.bat prod --gpu
```

---

## GPU vs CPU PyTorch Selection

The project supports **configurable PyTorch builds** to optimize image sizes based on your hardware.

### Image Size Comparison

| Service | CPU Build | GPU Build | Reduction |
|---------|-----------|-----------|-----------|
| insights_engine | **2.75 GB** | 9.99 GB | 72% smaller |
| celery_worker | ~3 GB | ~10 GB | 70% smaller |

### When to Use Each

| Scenario | Recommendation |
|----------|----------------|
| No NVIDIA GPU | Use CPU build (default) |
| NVIDIA GPU with CUDA drivers | Use GPU build (`--gpu`) |
| CI/CD pipelines | Use CPU build (smaller, faster) |
| Production ML inference | Use GPU build with `--gpus all` |
| Development/testing | Use CPU build (faster builds) |

---

## Build Scripts

### Full Build Script

The `build-images.sh` / `build-images.bat` scripts handle the complete build process:

```bash
./scripts/build-images.sh [dev|prod] [--gpu] [--no-cache]
```

**Arguments:**
- `dev` - Development builds with hot reload support
- `prod` - Production builds with security hardening
- `--gpu` - Enable GPU/CUDA support for ML services
- `--no-cache` - Force rebuild without Docker cache

**Examples:**
```bash
# Development build, CPU-only (fastest)
./scripts/build-images.sh dev

# Production build, CPU-only
./scripts/build-images.sh prod

# Production build with GPU support
./scripts/build-images.sh prod --gpu

# Force rebuild production with GPU
./scripts/build-images.sh prod --gpu --no-cache
```

---

## Manual Build Commands

### Base Image

All service images depend on the shared base image:

```bash
docker build \
    --target base-runtime \
    -t gsc-base:latest \
    -f compose/dockerfiles/Dockerfile.base \
    .
```

### ML Services (insights_engine, celery)

**CPU-only build (smaller, ~2.75 GB):**
```bash
docker build \
    --target runtime \
    -t site-data-warehouse-insights_engine:latest \
    -f compose/dockerfiles/Dockerfile.insights_engine \
    .

docker build \
    --target runtime \
    -t site-data-warehouse-celery:latest \
    -f compose/dockerfiles/Dockerfile.celery \
    .
```

**GPU build with CUDA 12.4 (~10 GB):**
```bash
docker build \
    --build-arg USE_GPU=true \
    --target runtime \
    -t site-data-warehouse-insights_engine:gpu \
    -f compose/dockerfiles/Dockerfile.insights_engine \
    .

docker build \
    --build-arg USE_GPU=true \
    --target runtime \
    -t site-data-warehouse-celery:gpu \
    -f compose/dockerfiles/Dockerfile.celery \
    .
```

**GPU build with specific CUDA version:**
```bash
docker build \
    --build-arg USE_GPU=true \
    --build-arg CUDA_VERSION=11.8 \
    --target runtime \
    -t site-data-warehouse-insights_engine:gpu-cuda118 \
    -f compose/dockerfiles/Dockerfile.insights_engine \
    .
```

### Other Services

```bash
# API Ingestor
docker build \
    --target runtime \
    -t site-data-warehouse-api_ingestor:latest \
    -f compose/dockerfiles/Dockerfile.api_ingestor \
    .

# GA4 Ingestor
docker build \
    --target runtime \
    -t site-data-warehouse-ga4_ingestor:latest \
    -f compose/dockerfiles/Dockerfile.ga4_ingestor \
    .

# Insights API
docker build \
    --target runtime \
    -t site-data-warehouse-insights_api:latest \
    -f compose/dockerfiles/Dockerfile.insights_api \
    .

# Scheduler
docker build \
    --target runtime \
    -t site-data-warehouse-scheduler:latest \
    -f compose/dockerfiles/Dockerfile.scheduler \
    .
```

---

## Running GPU Containers

After building with GPU support, run containers with NVIDIA GPU access:

```bash
# Run with GPU support
docker run --gpus all site-data-warehouse-insights_engine:gpu

# Run with specific GPU
docker run --gpus '"device=0"' site-data-warehouse-insights_engine:gpu

# Docker Compose with GPU
# Add to docker-compose.yml service:
#   deploy:
#     resources:
#       reservations:
#         devices:
#           - driver: nvidia
#             count: 1
#             capabilities: [gpu]
```

---

## Verification

### Verify CPU Build

```bash
docker run --rm site-data-warehouse-insights_engine:latest python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
# Should show: CUDA available: False
"
```

### Verify GPU Build

```bash
docker run --rm site-data-warehouse-insights_engine:gpu python -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA compiled: {torch.version.cuda}')
print(f'CUDA available: {torch.cuda.is_available()}')
# Should show: CUDA compiled: 12.4
"

# With GPU access:
docker run --gpus all --rm site-data-warehouse-insights_engine:gpu python -c "
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'GPU device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')
"
```

---

## Build Targets

Each Dockerfile supports multiple build targets:

| Target | Purpose | Use Case |
|--------|---------|----------|
| `builder` | Build stage with compilers | Internal only |
| `runtime` | Production image | Default for all deployments |
| `development` | Dev image with hot reload | Local development |

**Build for development:**
```bash
docker build \
    --target development \
    -t site-data-warehouse-insights_engine:dev \
    -f compose/dockerfiles/Dockerfile.insights_engine \
    .
```

---

## Troubleshooting

### Build Fails: "gsc-base:latest not found"

Build the base image first:
```bash
docker build --target base-runtime -t gsc-base:latest -f compose/dockerfiles/Dockerfile.base .
```

### GPU Build Too Large

If you don't need GPU acceleration, use CPU builds (default):
```bash
./scripts/build-images.sh prod  # No --gpu flag
```

### CUDA Version Mismatch

Specify a different CUDA version:
```bash
docker build \
    --build-arg USE_GPU=true \
    --build-arg CUDA_VERSION=11.8 \
    ...
```

### Container Can't Access GPU

1. Install NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
2. Run with `--gpus all` flag
3. Verify GPU drivers: `nvidia-smi`

---

## Image Size Reference

| Image | CPU Size | GPU Size |
|-------|----------|----------|
| gsc-base | 828 MB | 828 MB |
| insights_engine | 2.75 GB | 9.99 GB |
| celery_worker | ~3 GB | ~10 GB |
| api_ingestor | ~985 MB | ~985 MB |
| ga4_ingestor | ~985 MB | ~985 MB |
| insights_api | ~861 MB | ~861 MB |
| scheduler | ~993 MB | ~993 MB |
| metrics_exporter | ~838 MB | ~838 MB |

---

## Related Documentation

- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Initial project setup
- [PRODUCTION_GUIDE.md](PRODUCTION_GUIDE.md) - Production deployment
- [../../reports/docker_optimization.md](../../reports/docker_optimization.md) - Detailed optimization analysis
