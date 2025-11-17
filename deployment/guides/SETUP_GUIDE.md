# Setup Guide

## Prerequisites

### Required Software
- **Docker** 20.10+ ([Install](https://docs.docker.com/get-docker/))
- **Docker Compose** 1.29+ ([Install](https://docs.docker.com/compose/install/))
- **PostgreSQL Client** (psql) ([Install](https://www.postgresql.org/download/))
- **Python** 3.9+ ([Install](https://www.python.org/downloads/))
- **Git** ([Install](https://git-scm.com/downloads))

### Google Cloud Setup
1. Create a service account with GSC API access
2. Download JSON credentials
3. Place in `secrets/gsc_sa.json`

## Installation Steps

### 1. Clone Repository
```bash
git clone <repository-url>
cd gsc-data-warehouse
```

### 2. Create Environment File
```bash
cp .env.template .env
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
cp secrets/gsc_sa.json.template secrets/gsc_sa.json
# Edit secrets/gsc_sa.json with your credentials
```

### 4. Deploy

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

### 5. Initial Data Load
```bash
# Ingest last 30 days
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '30 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)
```

### 6. Generate Insights
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
