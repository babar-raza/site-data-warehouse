# Docker Optimization Plan
**Site Data Warehouse - Comprehensive Docker Optimization Strategy**

Date: 2025-11-23
Status: Planning
Priority: High (Development Speed)

---

## 🔍 Critical Issues Identified

### 1. **MASSIVE Dependency Bloat** (Biggest Issue!)
Every container installs **ALL 182 lines** of `requirements.txt`, including:
- Heavy ML libs: Prophet, scikit-learn, sentence-transformers, spaCy
- Playwright with browser binaries (~500MB)
- Packages most services never use

**Impact**: Each service downloads ~2-3GB of packages unnecessarily

### 2. **No Local Package Caching**
Every build downloads from PyPI from scratch - no localhost caching

### 3. **No Shared Base Image**
Each Dockerfile rebuilds `python:3.11-slim` + system deps independently

### 4. **No BuildKit Optimizations**
Not using cache mounts, which would persist pip cache between builds

### 5. **Poor Layer Caching Strategy**
requirements.txt changes invalidate massive layers

---

## 🚀 Comprehensive Optimization Strategy

### **Phase 1: Split Requirements** (Highest Impact - Do First!)

Split your monolithic requirements.txt into service-specific files:

```
requirements/
├── base.txt                 # Core deps (psycopg2, sqlalchemy, pandas)
├── ingestors.txt           # Google APIs, aiofiles
├── insights.txt            # ML/AI (Prophet, sklearn, sentence-transformers)
├── api.txt                 # FastAPI, uvicorn, pydantic
├── celery.txt              # Celery, redis, ollama, langchain
├── dev.txt                 # pytest, black, flake8
└── all.txt                 # Includes all (for local dev)
```

**Example base.txt**:
```txt
# Database
psycopg2-binary>=2.9.6
sqlalchemy==2.0.36
asyncpg>=0.28.0

# Core utilities
python-dotenv>=1.0.0
pandas>=2.0.3
pyarrow>=12.0.1
pyyaml>=6.0.0
requests>=2.31.0
tenacity>=8.2.0
```

**Example ingestors.txt**:
```txt
-r base.txt

# Google Cloud dependencies
google-auth>=2.16.0
google-api-python-client>=2.100.0
google-analytics-data>=0.18.0

# Scheduling
APScheduler>=3.10.1
aiofiles>=23.0.0
```

**Example insights.txt**:
```txt
-r base.txt

# AI/ML Libraries
prophet>=1.1.5
scikit-learn>=1.3.0
sentence-transformers>=2.2.0
numpy>=1.24.0
statsmodels>=0.14.0

# Embeddings
pgvector>=0.2.0
```

**Example api.txt**:
```txt
-r base.txt

# API Framework
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
httpx>=0.25.0
```

**Example celery.txt**:
```txt
-r base.txt
-r insights.txt

# Task Queue
celery>=5.3.0
redis>=5.0.0
redis[hiredis]>=5.0.0

# LLM Integration
ollama>=0.1.0
langchain>=0.1.0
langchain-community>=0.0.10
langgraph>=0.0.20
```

**Example dev.txt**:
```txt
-r all.txt

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0

# Code Quality
black>=23.9.0
isort>=5.12.0
flake8>=6.1.0
```

**Example all.txt**:
```txt
-r base.txt
-r ingestors.txt
-r insights.txt
-r api.txt
-r celery.txt

# Content Analysis (used by multiple services)
beautifulsoup4>=4.12.0
lxml>=4.9.0
readability-lxml>=0.8.1
textstat>=0.7.3

# Additional utilities
python-frontmatter>=1.0.0
GitPython>=3.1.40
causalimpact>=0.1.1
PyGithub>=2.1.1
slack-sdk>=3.23.0
```

**Benefit**: api_ingestor goes from 2.5GB → 300MB, builds in 30s instead of 8min

---

### **Phase 2: Local Package Cache** (Quick Win!)

Create a local PyPI cache server using `devpi` or simple volume mount:

#### **Option A: Simple Volume Cache** (Fastest to implement)

Create `docker-compose.dev.yml`:
```yaml
version: '3.8'

# Override for development with local pip cache
services:
  api_ingestor:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_api_ingestor:latest
    volumes:
      - pip-cache:/root/.cache/pip

  ga4_ingestor:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_ga4_ingestor:latest
    volumes:
      - pip-cache:/root/.cache/pip

  scheduler:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_scheduler:latest
    volumes:
      - pip-cache:/root/.cache/pip

  insights_engine:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_insights_engine:latest
    volumes:
      - pip-cache:/root/.cache/pip

  insights_api:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_insights_api:latest
    volumes:
      - pip-cache:/root/.cache/pip

  celery_worker:
    build:
      args:
        BUILDKIT_INLINE_CACHE: 1
      cache_from:
        - gsc_celery_worker:latest
    volumes:
      - pip-cache:/root/.cache/pip

volumes:
  pip-cache:
    driver: local
```

#### **Option B: devpi Cache Server** (Professional)

Add to docker-compose.yml:
```yaml
  # ==========================================
  # PYPI CACHE SERVER (Development)
  # ==========================================
  pypi-cache:
    image: muccg/devpi:latest
    container_name: gsc_pypi_cache
    volumes:
      - devpi-data:/data
    ports:
      - "3141:3141"
    networks:
      - gsc_network
    profiles:
      - dev
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'

volumes:
  devpi-data:
    driver: local
```

Update Dockerfiles to use cache (development builds only):
```dockerfile
# Add ARG for conditional cache usage
ARG USE_PIP_CACHE=false
ARG PIP_INDEX_URL=https://pypi.org/simple

# Conditionally set cache
RUN if [ "$USE_PIP_CACHE" = "true" ]; then \
      export PIP_INDEX_URL=http://pypi-cache:3141/root/pypi/+simple/; \
      export PIP_TRUSTED_HOST=pypi-cache; \
    fi && \
    pip install --no-cache-dir -r /tmp/requirements.txt
```

**Benefit**: Second builds use cached packages, ~90% faster pip installs

---

### **Phase 3: Multi-Stage Builds + Shared Base**

#### **Create shared base image**

`compose/dockerfiles/Dockerfile.base`:

```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.11-slim AS base-builder

# Install system dependencies once
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install base requirements with cache mount
COPY requirements/base.txt /tmp/base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/base.txt

# -----------------------
# Production base (slim)
# -----------------------
FROM python:3.11-slim AS base-runtime

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=base-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base-builder /usr/local/bin /usr/local/bin

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
```

#### **Optimized service Dockerfile**

Example: `compose/dockerfiles/Dockerfile.api_ingestor`:

```dockerfile
# syntax=docker/dockerfile:1.4
ARG BASE_IMAGE=gsc-base:latest
FROM ${BASE_IMAGE} AS builder

# Install service-specific deps
COPY requirements/ingestors.txt /tmp/ingestors.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/ingestors.txt

# -----------------------
# Runtime
# -----------------------
FROM ${BASE_IMAGE}

# Copy service-specific packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy only needed code
COPY ingestors/api/ /app/ingestors/api/
RUN mkdir -p /report /logs

ENV PYTHONUNBUFFERED=1
ENV GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gsc_sa.json

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "/app/ingestors/api/gsc_api_ingestor.py"]
```

Example: `compose/dockerfiles/Dockerfile.insights_api`:

```dockerfile
# syntax=docker/dockerfile:1.4
ARG BASE_IMAGE=gsc-base:latest
FROM ${BASE_IMAGE} AS builder

# Install service-specific deps
COPY requirements/api.txt /tmp/api.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/api.txt

# -----------------------
# Runtime
# -----------------------
FROM ${BASE_IMAGE}

# Copy service-specific packages
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN useradd -m -u 1000 apiuser && \
    chown -R apiuser:apiuser /app

# Copy application code
COPY insights_api/ /app/insights_api/
RUN mkdir -p /logs && chown -R apiuser:apiuser /logs

# Switch to non-root user
USER apiuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "insights_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Example: `compose/dockerfiles/Dockerfile.celery`:

```dockerfile
# syntax=docker/dockerfile:1.4
ARG BASE_IMAGE=gsc-base:latest
FROM ${BASE_IMAGE} AS builder

# Install Celery + ML dependencies
COPY requirements/celery.txt /tmp/celery.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /tmp/celery.txt

# -----------------------
# Runtime
# -----------------------
FROM ${BASE_IMAGE}

# Copy all packages (Celery needs many deps)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY insights_core /app/insights_core
COPY services /app/services
COPY agents /app/agents

RUN mkdir -p /logs

ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD celery -A services.tasks inspect ping || exit 1

CMD ["celery", "-A", "services.tasks", "worker", "--loglevel=info"]
```

**Benefit**:
- Build base once, reuse for all services
- Layer caching dramatically faster
- BuildKit cache mounts persist pip cache

---

### **Phase 4: BuildKit Features**

#### Enable BuildKit in your environment

**Windows (PowerShell)**:
```powershell
$env:DOCKER_BUILDKIT=1
$env:COMPOSE_DOCKER_CLI_BUILD=1
```

**Windows (CMD)**:
```batch
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1
```

Add to your shell profile for persistence.

**Linux/macOS (.bashrc or .zshrc)**:
```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

#### Build script

`scripts/docker-build.bat`:
```batch
@echo off
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1

echo ============================================
echo Building GSC Warehouse Docker Images
echo ============================================

echo.
echo [1/2] Building shared base image...
docker build --target base-runtime -t gsc-base:latest -f compose/dockerfiles/Dockerfile.base .

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Base image build failed
    exit /b 1
)

echo.
echo [2/2] Building services in parallel...
docker compose build --parallel --progress=plain

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Service builds failed
    exit /b 1
)

echo.
echo ============================================
echo Build completed successfully!
echo ============================================
```

`scripts/docker-build.sh`:
```bash
#!/bin/bash
set -euo pipefail

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "============================================"
echo "Building GSC Warehouse Docker Images"
echo "============================================"

echo ""
echo "[1/2] Building shared base image..."
docker build --target base-runtime -t gsc-base:latest -f compose/dockerfiles/Dockerfile.base .

echo ""
echo "[2/2] Building services in parallel..."
docker compose build --parallel --progress=plain

echo ""
echo "============================================"
echo "Build completed successfully!"
echo "============================================"
```

**Features enabled**:
- `--mount=type=cache`: Persistent cache across builds
- `--mount=type=bind`: Zero-copy bind mounts
- Build parallelization
- Improved layer caching

---

### **Phase 5: Improved .dockerignore**

Update `.dockerignore`:
```dockerignore
# Git
.git
.gitignore
.github

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build
.pytest_cache
.coverage
.coveragerc

# Virtual environments
venv
env
.venv
.conda

# IDE
.vscode
.idea
*.swp
*.swo
*~
.claude

# OS
.DS_Store
Thumbs.db

# Logs & Reports
*.log
logs/*
reports/*
report/

# Secrets
secrets/*.json
secrets/*.txt
.env
.env.example

# Documentation
docs/
*.md
README*

# Tests (exclude from runtime images)
tests/
test_*.py
*_test.py
samples/

# Scripts not needed in containers
scripts/
*.bat
*.ps1
*.sh

# Plans and analysis
plans/
automation/

# Grafana & Prometheus configs (mounted as volumes)
grafana/
prometheus/

# Deployment files
deployment/
compose/
docker-compose*.yml
Dockerfile*

# Large data files
*.csv
*.parquet
*.db
*.sqlite

# Node modules (if any)
node_modules/

# Temporary files
tmp/
temp/
*.tmp
*.bak
```

**Benefit**: Smaller build context = faster uploads to Docker daemon

---

### **Phase 6: Development Optimizations**

#### docker-compose.dev.yml for fast iteration

`docker-compose.dev.yml`:

```yaml
version: '3.8'

# Development overrides with volume mounts for hot reload
services:
  # ==========================================
  # INGESTORS - Hot Reload
  # ==========================================
  api_ingestor:
    build:
      context: .
      dockerfile: compose/dockerfiles/Dockerfile.api_ingestor
      cache_from:
        - gsc_api_ingestor:latest
    volumes:
      - ./ingestors/api:/app/ingestors/api:ro  # Hot reload
      - pip-cache:/root/.cache/pip
    environment:
      PYTHONDONTWRITEBYTECODE: 0  # Allow bytecode for faster imports
      LOG_LEVEL: DEBUG

  ga4_ingestor:
    volumes:
      - ./ingestors/ga4:/app/ingestors/ga4:ro
      - pip-cache:/root/.cache/pip
    environment:
      LOG_LEVEL: DEBUG

  # ==========================================
  # INSIGHTS API - Hot Reload with uvicorn
  # ==========================================
  insights_api:
    build:
      cache_from:
        - gsc_insights_api:latest
    volumes:
      - ./insights_api:/app/insights_api:ro  # Hot reload
      - pip-cache:/root/.cache/pip
    command: uvicorn insights_api:app --host 0.0.0.0 --port 8000 --reload --log-level debug
    environment:
      LOG_LEVEL: DEBUG

  # ==========================================
  # SCHEDULER - Hot Reload
  # ==========================================
  scheduler:
    volumes:
      - ./scheduler:/app:ro
      - ./ingestors:/app/ingestors:ro
      - ./transform:/app/transform:ro
      - pip-cache:/root/.cache/pip
    environment:
      LOG_LEVEL: DEBUG

  # ==========================================
  # INSIGHTS ENGINE - Hot Reload
  # ==========================================
  insights_engine:
    volumes:
      - ./insights_core:/app/insights_core:ro
      - pip-cache:/root/.cache/pip
    environment:
      LOG_LEVEL: DEBUG

  # ==========================================
  # CELERY - Hot Reload with watchdog
  # ==========================================
  celery_worker:
    volumes:
      - ./insights_core:/app/insights_core:ro
      - ./services:/app/services:ro
      - ./agents:/app/agents:ro
      - pip-cache:/root/.cache/pip
    command: watchmedo auto-restart --directory=/app --pattern=*.py --recursive -- celery -A services.tasks worker --loglevel=debug --concurrency=2
    environment:
      LOG_LEVEL: DEBUG

  # ==========================================
  # PYPI CACHE SERVER (Development)
  # ==========================================
  pypi-cache:
    image: muccg/devpi:latest
    container_name: gsc_pypi_cache
    volumes:
      - devpi-data:/data
    ports:
      - "3141:3141"
    networks:
      - gsc_network
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'

volumes:
  pip-cache:
    driver: local
  devpi-data:
    driver: local
```

#### Usage

**Development with hot reload + cache**:
```bash
# Windows
scripts\docker-build.bat
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up

# Linux/macOS
./scripts/docker-build.sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile core up
```

**Production build**:
```bash
docker compose --profile core --profile insights up
```

---

### **Phase 7: Production K8s Optimizations**

#### Multi-arch builds

`docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  api_ingestor:
    build:
      platforms:
        - linux/amd64
        - linux/arm64
    image: ${REGISTRY}/gsc-api-ingestor:${VERSION}

  ga4_ingestor:
    build:
      platforms:
        - linux/amd64
        - linux/arm64
    image: ${REGISTRY}/gsc-ga4-ingestor:${VERSION}

  insights_api:
    build:
      platforms:
        - linux/amd64
        - linux/arm64
    image: ${REGISTRY}/gsc-insights-api:${VERSION}

  # Add for all services...
```

#### Registry caching for CI/CD

`.github/workflows/build.yml`:
```yaml
name: Build Docker Images

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: ${{ github.repository }}

jobs:
  build-base:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push base image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: compose/dockerfiles/Dockerfile.base
          target: base-runtime
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-base:latest
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-base:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-base:buildcache,mode=max

  build-services:
    needs: build-base
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service:
          - api_ingestor
          - ga4_ingestor
          - scheduler
          - insights_engine
          - insights_api
          - mcp
          - celery
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push ${{ matrix.service }}
        uses: docker/build-push-action@v5
        with:
          context: .
          file: compose/dockerfiles/Dockerfile.${{ matrix.service }}
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-${{ matrix.service }}:latest
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-${{ matrix.service }}:${{ github.sha }}
          cache-from: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-${{ matrix.service }}:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-${{ matrix.service }}:buildcache,mode=max
          build-args: |
            BASE_IMAGE=${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/gsc-base:latest
```

#### Kubernetes deployment optimizations

**Deployment best practices**:

1. **Image Pull Policy**:
```yaml
spec:
  containers:
    - name: api-ingestor
      image: registry.example.com/gsc-api-ingestor:v1.2.3
      imagePullPolicy: IfNotPresent  # Use cached images
```

2. **Init Containers for Migrations**:
```yaml
spec:
  initContainers:
    - name: db-migrations
      image: registry.example.com/gsc-transformer:v1.2.3
      command: ["python", "apply_transforms.py"]
      env:
        - name: WAREHOUSE_DSN
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: dsn
```

3. **Resource Requests/Limits**:
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

4. **Horizontal Pod Autoscaling**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: insights-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: insights-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

5. **Node Affinity for GPU Workloads (Ollama)**:
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: accelerator
              operator: In
              values:
                - nvidia-tesla-t4
                - nvidia-tesla-a100
```

6. **Pod Disruption Budgets**:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: insights-api-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: insights-api
```

---

## 📊 Expected Performance Gains

| Metric | Current | After Phase 1-2 | After Phase 3-4 | Savings |
|--------|---------|-----------------|-----------------|---------|
| **First build** | 15-20 min | 8-10 min | 4-6 min | **70-75%** |
| **Rebuild (code change)** | 15-20 min | 2-3 min | **10-30 sec** | **98%** |
| **Rebuild (deps change)** | 15-20 min | 5-7 min | 2-3 min | **85%** |
| **Image size (avg)** | 2.5-3 GB | 800 MB | 400-600 MB | **75-80%** |
| **Pip install time** | 8-12 min | 1-2 min | **10-20 sec** | **97%** |
| **Build context** | 200-500 MB | 50-100 MB | 20-50 MB | **90%** |

---

## 🎯 Recommended Implementation Order

### Week 1: Split requirements.txt + add local pip cache (Phases 1-2)
- **Tasks**:
  - Create requirements/ directory structure
  - Split requirements.txt into service-specific files
  - Create docker-compose.dev.yml with pip cache volume
  - Update 2-3 Dockerfiles to use split requirements
  - Test builds and measure improvements
- **Expected Impact**: Immediate 60-70% build time reduction
- **Risk**: Low - can roll back easily
- **Effort**: 4-6 hours

### Week 2: Create base image + multi-stage builds (Phase 3)
- **Tasks**:
  - Create Dockerfile.base with multi-stage build
  - Build and tag base image
  - Update all service Dockerfiles to use base image
  - Update docker-compose.yml to depend on base
  - Create build scripts
- **Expected Impact**: Reusable base for all services, 85% faster rebuilds
- **Risk**: Medium - requires testing all services
- **Effort**: 8-10 hours

### Week 3: Enable BuildKit + optimize docker-compose.dev.yml (Phases 4, 6)
- **Tasks**:
  - Enable BuildKit in environment
  - Update Dockerfiles with BuildKit syntax
  - Add cache mounts to all pip install steps
  - Create comprehensive docker-compose.dev.yml
  - Set up hot reload for development
- **Expected Impact**: Developer experience improvements, <30s rebuilds
- **Risk**: Low - BuildKit is stable
- **Effort**: 4-6 hours

### Later: Production K8s setup (Phase 7)
- **Tasks**:
  - Set up multi-arch builds
  - Configure CI/CD with registry caching
  - Create Kubernetes manifests
  - Set up HPA, PDB, resource limits
  - Test production deployment
- **Expected Impact**: Production-ready deployment
- **Risk**: Medium - requires K8s cluster
- **Effort**: 16-24 hours (can be done incrementally)

---

## 🛠️ Quick Start: Minimal Changes for Maximum Impact

If you want the **fastest wins with minimal changes**, do this first:

### Step 1: Create minimal requirements split

Create `requirements/base.txt`:
```txt
# Database
psycopg2-binary>=2.9.6
sqlalchemy==2.0.36
asyncpg>=0.28.0

# Core utilities
python-dotenv>=1.0.0
pandas>=2.0.3
pyarrow>=12.0.1
pyyaml>=6.0.0
requests>=2.31.0
tenacity>=8.2.0
```

Create `requirements/ingestors.txt`:
```txt
-r base.txt

# Google Cloud dependencies
google-auth>=2.16.0
google-api-python-client>=2.100.0
google-analytics-data>=0.18.0

# Scheduling & utilities
APScheduler>=3.10.1
aiofiles>=23.0.0
```

### Step 2: Update ONE Dockerfile

Update `compose/dockerfiles/Dockerfile.api_ingestor`:
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install minimal deps
COPY requirements/base.txt /tmp/base.txt
COPY requirements/ingestors.txt /tmp/ingestors.txt
RUN pip install --no-cache-dir -r /tmp/ingestors.txt

COPY ingestors/api/ /app/ingestors/api/
RUN mkdir -p /report /logs

ENV PYTHONUNBUFFERED=1
ENV GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gsc_sa.json

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "/app/ingestors/api/gsc_api_ingestor.py"]
```

### Step 3: Test the build

```bash
# Windows
docker build -t test-api-ingestor -f compose\dockerfiles\Dockerfile.api_ingestor .

# Linux/macOS
docker build -t test-api-ingestor -f compose/dockerfiles/Dockerfile.api_ingestor .
```

**Expected result**: Build completes in 1-2 minutes instead of 8-12 minutes, image size ~300MB instead of 2.5GB.

---

## 📋 Service-to-Requirements Mapping

| Service | Dockerfile | Requirements Files | Notes |
|---------|------------|-------------------|-------|
| warehouse | postgres:14-alpine | N/A | Pre-built image |
| startup_orchestrator | Dockerfile.scheduler | base.txt, ingestors.txt | Runs backfill |
| api_ingestor | Dockerfile.api_ingestor | base.txt, ingestors.txt | GSC API client |
| ga4_ingestor | Dockerfile.ga4_ingestor | base.txt, ingestors.txt | GA4 API client |
| transform | Dockerfile.transformer | base.txt | SQL runner only |
| insights_engine | Dockerfile.insights_engine | base.txt, insights.txt | ML/AI heavy |
| scheduler | Dockerfile.scheduler | base.txt, ingestors.txt | APScheduler |
| insights_api | Dockerfile.insights_api | base.txt, api.txt | FastAPI |
| mcp | Dockerfile.mcp | base.txt, api.txt | MCP server |
| metrics_exporter | Dockerfile.metrics | base.txt, api.txt | Flask metrics |
| celery_worker | Dockerfile.celery | base.txt, celery.txt | Full ML stack |
| prometheus | prom/prometheus | N/A | Pre-built image |
| grafana | grafana/grafana | N/A | Pre-built image |
| ollama | ollama/ollama | N/A | Pre-built image |
| redis | redis:7-alpine | N/A | Pre-built image |

---

## 🔧 Additional Optimization Opportunities

### 1. Pre-download heavy ML models
For containers using sentence-transformers or spaCy:

```dockerfile
# In Dockerfile.celery or Dockerfile.insights_engine
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"
```

This bakes models into the image, avoiding runtime downloads.

### 2. Use Alpine where possible
Consider `python:3.11-alpine` for smaller base images (but beware of compilation issues with numpy/scipy).

### 3. Distroless for production
For maximum security and minimal size:

```dockerfile
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
```

### 4. Layer squashing for final images
```bash
docker build --squash -t gsc-api-ingestor:latest .
```

Reduces layer count, can improve pull performance.

### 5. Implement health check endpoints
Instead of trivial health checks, implement proper endpoints:

```python
# In insights_api
@app.get("/health")
async def health():
    # Check DB connection
    # Check Redis if applicable
    return {"status": "healthy"}
```

---

## 📝 Next Steps

1. **Review this plan** with the team
2. **Choose implementation approach**:
   - Quick wins (Phase 1-2 only)
   - Full optimization (All phases)
   - Custom hybrid approach
3. **Allocate time** for implementation
4. **Set up monitoring** to measure improvements
5. **Document learnings** for future reference

---

## 🔗 References

- [Docker BuildKit Documentation](https://docs.docker.com/build/buildkit/)
- [Multi-stage Build Best Practices](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose Best Practices](https://docs.docker.com/compose/production/)
- [Python Docker Best Practices](https://pythonspeed.com/docker/)
- [Kubernetes Production Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

---

**Status**: Ready for Implementation
**Owner**: Development Team
**Last Updated**: 2025-11-23
