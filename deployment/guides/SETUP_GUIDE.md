# Setup Guide

## Prerequisites

### Required Software
- **Docker** 20.10+ ([Install](https://docs.docker.com/get-docker/))
- **Docker Compose** 1.29+ ([Install](https://docs.docker.com/compose/install/))
- **PostgreSQL Client** (psql) ([Install](https://www.postgresql.org/download/))
- **Python** 3.9+ ([Install](https://www.python.org/downloads/))
- **Git** ([Install](https://git-scm.com/downloads))

### Optional (for GPU Acceleration)
- **NVIDIA GPU** with CUDA support
- **NVIDIA Driver** 525.60+
- **NVIDIA Container Toolkit** ([Install](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html))

### Google Cloud Setup

**Complete Guide:** See [GCP_SETUP_GUIDE.md](GCP_SETUP_GUIDE.md) for detailed step-by-step instructions.

**Quick Summary:**
1. Create Google Cloud Project
2. Enable APIs:
   - Google Search Console API
   - Google Analytics Data API
3. Create service account with appropriate IAM roles
4. Download JSON credentials
5. Add service account to:
   - Google Search Console properties (Full access)
   - Google Analytics 4 properties (Viewer access)
6. Place credentials in `secrets/gsc_sa.json`

**Need help?** Follow the comprehensive [GCP Setup Guide](GCP_SETUP_GUIDE.md) which includes:
- Detailed screenshots and instructions
- IAM role configuration
- GSC and GA4 integration steps
- Troubleshooting common issues
- Security best practices

## Installation Steps

### 1. Clone Repository
```bash
git clone <repository-url>
cd gsc-data-warehouse
```

### 2. Create Environment File
```bash
cp .env.example .env
# Edit .env with your settings
```

Required variables:
```bash
WAREHOUSE_DSN=postgresql://gsc_user:your_password@localhost:5432/gsc_db
GSC_SA_PATH=secrets/gsc_sa.json
GSC_PROPERTY=sc-domain:example.com
```

### 3. Setup Secrets
```bash
mkdir -p secrets
# Place your Google service account JSON file in secrets/gsc_sa.json
# Download the JSON from Google Cloud Console (see GCP Setup Guide)
```

### 4. Build Docker Images

The project supports **GPU/CPU PyTorch selection** to optimize image sizes.

**CPU-only build (recommended for most users):**
```bash
# Linux/macOS
./scripts/build-images.sh dev

# Windows
scripts\build-images.bat dev
```

**GPU build (for NVIDIA GPU systems):**
```bash
# Linux/macOS
./scripts/build-images.sh prod --gpu

# Windows
scripts\build-images.bat prod --gpu
```

| Build Type | insights_engine Size | Best For |
|------------|---------------------|----------|
| CPU (default) | 2.75 GB | Most deployments |
| GPU | 9.99 GB | NVIDIA GPU systems |

> **Note:** See [DOCKER_BUILD_GUIDE.md](DOCKER_BUILD_GUIDE.md) for detailed build options.

### 5. Deploy

**Linux:**
```bash
cd deployment/linux
./deploy.sh
```

**Windows:**
```cmd
cd deployment\windows
deploy.bat
```

### 6. Initial Data Load
```bash
# Ingest last 30 days
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '30 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)
```

### 7. Generate Insights
```bash
python -m insights_core.cli refresh
```

## Verification

### Check Services
```bash
docker-compose ps
```

All services should show "Up" status.

### Check Database
```sql
psql $WAREHOUSE_DSN -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"
```

Should return >0 rows.

### Check Insights
```sql
psql $WAREHOUSE_DSN -c "SELECT COUNT(*) FROM gsc.insights;"
```

## Troubleshooting

See [TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for common issues.
