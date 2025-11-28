# GSC Data Warehouse - Deployment Guide

## Quick Start for Windows

### Prerequisites

1. **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Ensure WSL 2 backend is enabled
   - Minimum 4GB RAM allocated to Docker
   - Minimum 20GB disk space

2. **Google Cloud Service Account**
   - Create service account in Google Cloud Console
   - Grant permissions:
     - Google Search Console API access
     - Google Analytics Data API access (for GA4 integration)
   - Download JSON key file

### Step 1: Setup Credentials

1. Place your Google Cloud service account JSON file in `secrets/gsc_sa.json`
   - You can use `secrets/gsc_sa.json.template` as reference

2. Edit `.env` file with your configuration:
   ```
   GCP_PROJECT_ID=your-actual-project-id
   GSC_PROPERTY=sc-domain:yoursite.com
   GA4_PROPERTY_ID=123456789
   ```

### Step 2: Deploy

**Option A: One-Click Deployment + Data Collection**
```batch
start-collection.bat
```
This will:
- Build all Docker images
- Start all services
- Run initial data ingestion
- Start automated scheduling

**Option B: Step-by-Step Deployment**

1. Deploy infrastructure:
```batch
deploy.bat
```

2. Start data collection manually:
```batch
docker compose --profile core run --rm api_ingestor python gsc_api_ingestor.py
docker compose --profile core run --rm ga4_ingestor python ga4_ingestor.py
docker compose --profile transform run --rm transformer python apply_transforms.py
```

3. Start scheduler for automation:
```batch
docker compose --profile scheduler up -d scheduler
```

### Step 3: Verify Deployment

Run health check:
```batch
health-check.bat
```

Check running services:
```batch
docker compose ps
```

View logs:
```batch
docker compose logs -f
```

### Available Services

After deployment, the following services will be available:

| Service | URL | Description |
|---------|-----|-------------|
| Warehouse | localhost:5432 | PostgreSQL database |
| MCP Server | http://localhost:8000 | AI agent integration |
| Insights API | http://localhost:8001 | REST API for dashboards |
| Prometheus | http://localhost:9090 | Metrics collection and time-series database |
| Grafana | http://localhost:3000 | Metrics visualization dashboards |
| Metrics Exporter | http://localhost:8002 | Custom application metrics |

### Automated Schedules

The scheduler runs:
- **Daily at 07:00 UTC**: API ingestion (GSC + GA4), URL discovery, transforms, insights refresh
- **Weekly (Monday 07:00 UTC)**: Watermark reconciliation, cannibalization refresh, cleanup

### Stopping Services

To stop all services:
```batch
docker compose down
```

To stop and remove all data (WARNING: Deletes everything):
```batch
cleanup.bat
```

---

## Linux/Mac Quick Start

### Prerequisites

Same as Windows, but use native Docker installation for your platform.

### Step 1: Setup Credentials

Same as Windows - place credentials in `secrets/gsc_sa.json`

### Step 2: Deploy

**Option A: One-Click Deployment**
```bash
chmod +x *.sh
./start-collection.sh
```

**Option B: Step-by-Step**
```bash
./deploy.sh
```

### Step 3: Verify
```bash
./health-check.sh
```

---

## Troubleshooting

### Issue: "Docker is not running"
**Solution**: Start Docker Desktop and wait for it to fully initialize

### Issue: "secrets/gsc_sa.json not found"
**Solution**: 
1. Create the file from your Google Cloud service account
2. Or use the template: `secrets/gsc_sa.json.template`

### Issue: "Port already in use"
**Solution**:
- Stop other services using ports 5432, 8000, 8001, 8002, 9090, 3000
- Or modify ports in `docker-compose.yml`

### Issue: "Failed to build Docker images"
**Solution**:
1. Check internet connection
2. Increase Docker memory allocation (Docker Desktop settings)
3. Clean Docker cache: `docker system prune -a`

### Issue: "API ingestion fails"
**Solution**:
1. Verify service account permissions in Google Cloud Console
2. Check `.env` file has correct GSC_PROPERTY and GA4_PROPERTY_ID
3. Verify `secrets/gsc_sa.json` is valid JSON
4. Ensure service account is added to GSC properties and GA4 properties

### Issue: "Warehouse connection refused"
**Solution**:
- Wait 20-30 seconds for PostgreSQL to fully initialize
- Check logs: `docker compose logs warehouse`

---

## Advanced Configuration

### Custom Database Password

Edit `secrets/db_password.txt` before deployment

### Custom API Limits

Edit `.env` file:
```
GSC_API_ROWS_PER_PAGE=25000
GSC_API_MAX_RETRIES=3
API_COOLDOWN_SEC=2
```

### Custom Ingestion Windows

Two environment variables control how much history the API ingestor will pull:

- **`GSC_INITIAL_BACKFILL_DAYS`** – The number of days of history to ingest on the very first run for each property when no data exists in the warehouse.  It defaults to **480** (approximately 16 months) to take advantage of the maximum look‑back window allowed by the Search Console API.
- **`INGEST_DAYS`** – The number of days to ingest on subsequent incremental runs.  It defaults to **30** to provide a rolling window of fresh data without reprocessing the entire history.

To customize these values, edit your `.env` file or pass them directly as environment variables:
```
GSC_INITIAL_BACKFILL_DAYS=480  # initial backfill (~16 months)
INGEST_DAYS=30                # incremental window
MAX_ROWS=100000               # maximum rows processed per run
```

---

## Data Collection Modes

### Mode 1: One-Time Manual Collection
```batch
docker compose --profile core up api_ingestor ga4_ingestor
```

### Mode 2: Automated Scheduled Collection
```batch
docker compose --profile scheduler up -d scheduler
```

### Mode 3: Continuous Real-Time Streaming
Not yet implemented (roadmap v2.0)

---

## Monitoring and Observability

**Note**: Prometheus and Grafana are now always enabled and start automatically with `docker-compose up -d`

### View Metrics
```batch
# Access Prometheus
start http://localhost:9090

# Access Grafana dashboards
start http://localhost:3000

# Query metrics endpoint
curl http://localhost:8002/metrics
```

### Key Metrics
- `gsc_warehouse_up` - Database status
- `gsc_fact_table_total_rows` - Total rows in warehouse
- `gsc_data_freshness_days` - Days since last data
- `gsc_task_*_success` - Task success counters
- `gsc_task_*_duration_seconds` - Task duration

---

## Backup and Restore

### Backup Database
```batch
docker compose exec warehouse pg_dump -U gsc_user gsc_db > backup.sql
```

### Restore Database
```batch
docker compose exec -T warehouse psql -U gsc_user gsc_db < backup.sql
```

---

## Upgrading

### Pull Latest Changes
```batch
git pull origin main
```

### Rebuild Images
```batch
docker compose build --no-cache
```

### Restart Services
```batch
docker compose down
docker compose up -d
```

---

## Security Best Practices

1. **Never commit secrets**
   - Add `secrets/gsc_sa.json` to `.gitignore`
   - Rotate service account keys regularly

2. **Network isolation**
   - Services run on isolated Docker network
   - Only expose necessary ports

3. **Access control**
   - Use strong database passwords
   - Implement IP whitelisting if exposing to internet

4. **Monitoring**
   - Enable Prometheus alerting
   - Set up log aggregation

---

## Support

For issues, questions, or contributions:
- Check [Main README](../README.md) for detailed documentation
- Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Review logs: `docker compose logs`
- Run health check: `health-check.bat` or `./health-check.sh`

---

## Related Documentation

- **[Main README](../README.md)** - Project overview and quick start
- **[Quick Start Guide](QUICKSTART.md)** - 15-minute deployment
- **[Deployment Scripts](../deployment/README.md)** - Automated deployment
- **[Secrets Setup](../secrets/README.md)** - Credential management
- **[Architecture Guide](ARCHITECTURE.md)** - System design
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues

---

**Status**: Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-11-21
