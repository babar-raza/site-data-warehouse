# Docker Setup Guide

## Quick Start

### 1. Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ installed
- 4GB+ RAM available
- 20GB+ disk space

**Verify installation:**
```bash
docker --version
docker-compose --version
```

### 2. Configuration

**Copy environment template:**
```bash
cp .env.example .env
```

**Edit `.env` with your credentials:**
```bash
# Required changes:
POSTGRES_PASSWORD=your_secure_password
GSC_PROPERTIES=sc-domain:your-site.com
GA4_PROPERTY_ID=your_property_id
GRAFANA_PASSWORD=your_grafana_password
```

**Add service account credentials:**
```bash
# Copy your GSC service account JSON
cp /path/to/your/gsc-credentials.json secrets/gsc_sa.json

# Copy your GA4 service account JSON  
cp /path/to/your/ga4-credentials.json secrets/ga4_sa.json
```

### 3. Launch

**Start core services:**
```bash
docker-compose --profile core up -d
```

**Start with insights generation:**
```bash
docker-compose --profile core --profile insights up -d
```

**Start full stack (all services):**
```bash
docker-compose --profile core --profile insights --profile api --profile observability up -d
```

### 4. Verify

**Check service health:**
```bash
docker-compose ps
```

**Expected output:**
```
NAME                STATUS              PORTS
gsc_warehouse       Up (healthy)        0.0.0.0:5432->5432/tcp
gsc_scheduler       Up                  
gsc_insights_api    Up (healthy)        0.0.0.0:8000->8000/tcp
```

**View logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f insights_engine

# Last 100 lines
docker-compose logs --tail=100 scheduler
```

---

## Service Profiles

### Core Profile (Minimum Viable)
- `warehouse`: PostgreSQL database
- `startup_orchestrator`: Initial data backfill
- `api_ingestor`: GSC API ingestion
- `ga4_ingestor`: GA4 data ingestion
- `transform`: SQL view refresh

**Use case:** Data collection only

```bash
docker-compose --profile core up -d
```

### Insights Profile (Insight Generation)
- Everything in Core +
- `insights_engine`: One-time insight generation
- `scheduler`: Daily automated jobs

**Use case:** Full pipeline with automated insights

```bash
docker-compose --profile core --profile insights up -d
```

### API Profile (Serving Layer)
- `insights_api`: REST API for insights
- `mcp`: MCP server for tools

**Use case:** Expose insights to external systems

```bash
docker-compose --profile api up -d
```

### Observability Profile (Monitoring)
- `prometheus`: Metrics collection
- `grafana`: Visualization dashboards
- `metrics_exporter`: Custom metrics

**Use case:** Production monitoring

```bash
docker-compose --profile observability up -d
```

---

## Service Dependencies

```
Startup Sequence:
1. warehouse (PostgreSQL)
   ↓ (waits for healthy)
2. startup_orchestrator (backfill data)
   ↓ (waits for completion)
3. transform (refresh views)
   ↓ (waits for completion)
4. insights_engine (generate insights)
   ↓ (waits for start)
5. scheduler (daily automation)

Parallel (no strict order):
- api_ingestor
- ga4_ingestor
- insights_api
- mcp
- prometheus/grafana
```

**Health checks ensure:**
- Database is ready before clients connect
- Data is ingested before transforms run
- Views are refreshed before insights generated

---

## Common Operations

### Start Services
```bash
# Start specific service
docker-compose start scheduler

# Start with rebuild
docker-compose up -d --build

# Start and follow logs
docker-compose up
```

### Stop Services
```bash
# Stop all
docker-compose down

# Stop and remove volumes (DESTRUCTIVE)
docker-compose down -v

# Stop specific service
docker-compose stop scheduler
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart insights_engine

# Restart and rebuild
docker-compose up -d --force-recreate --build insights_engine
```

### View Status
```bash
# Service status
docker-compose ps

# Resource usage
docker stats

# Logs
docker-compose logs -f scheduler

# Execute command in container
docker-compose exec warehouse psql -U gsc_user -d gsc_db
```

### Database Operations
```bash
# Connect to PostgreSQL
docker-compose exec warehouse psql -U gsc_user -d gsc_db

# Backup database
docker-compose exec warehouse pg_dump -U gsc_user gsc_db > backup.sql

# Restore database
docker-compose exec -T warehouse psql -U gsc_user -d gsc_db < backup.sql

# Check database health
docker-compose exec warehouse pg_isready -U gsc_user
```

---

## Troubleshooting

### Services won't start

**Check logs:**
```bash
docker-compose logs warehouse
```

**Common issues:**
- Port already in use: Change port in .env
- Volume permissions: `sudo chown -R $USER:$USER logs/`
- Missing secrets: Verify `secrets/gsc_sa.json` exists

### Database connection refused

**Verify database is healthy:**
```bash
docker-compose ps warehouse
# Should show: Up (healthy)
```

**Check connection from inside:**
```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "SELECT 1;"
```

**If unhealthy:**
```bash
# Check logs
docker-compose logs warehouse

# Restart database
docker-compose restart warehouse

# If corrupted, recreate (DESTRUCTIVE)
docker-compose down -v
docker-compose up -d warehouse
```

### Insights not generating

**Check insights engine logs:**
```bash
docker-compose logs insights_engine
```

**Verify data exists:**
```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "
  SELECT COUNT(*) FROM gsc.fact_gsc_daily;
"
```

**Run manually:**
```bash
docker-compose run --rm insights_engine python -m insights_core.cli refresh-insights
```

### High memory usage

**Check resource usage:**
```bash
docker stats
```

**Adjust limits in docker-compose.yml:**
```yaml
deploy:
  resources:
    limits:
      memory: 512M  # Reduce if needed
```

**Restart with new limits:**
```bash
docker-compose up -d --force-recreate
```

### Slow performance

**Check database queries:**
```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "
  SELECT * FROM pg_stat_activity WHERE state = 'active';
"
```

**Optimize database:**
```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "VACUUM ANALYZE;"
```

---

## Production Deployment

### Security Hardening

**1. Change default passwords:**
```bash
# In .env
POSTGRES_PASSWORD=$(openssl rand -base64 32)
GRAFANA_PASSWORD=$(openssl rand -base64 32)
```

**2. Use Docker secrets (not .env):**
```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  warehouse:
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
```

**3. Restrict network access:**
```yaml
ports:
  - "127.0.0.1:5432:5432"  # Only localhost
```

**4. Enable TLS:**
```yaml
volumes:
  - ./certs/server.crt:/var/lib/postgresql/server.crt:ro
  - ./certs/server.key:/var/lib/postgresql/server.key:ro
command: 
  - -c
  - ssl=on
```

### Monitoring Setup

**1. Start observability stack:**
```bash
docker-compose --profile observability up -d
```

**2. Access Grafana:**
```
URL: http://localhost:3000
User: admin
Password: (from .env GRAFANA_PASSWORD)
```

**3. Configure Prometheus data source:**
- Add data source: Prometheus
- URL: http://prometheus:9090
- Save & Test

**4. Import dashboards:**
- Use provided dashboard JSONs in `grafana/dashboards/`

### Backup Strategy

**Automated daily backups:**
```bash
# Add to crontab
0 2 * * * docker-compose exec -T warehouse pg_dump -U gsc_user gsc_db | gzip > /backups/gsc_$(date +\%Y\%m\%d).sql.gz
```

**Retention policy:**
```bash
# Keep last 30 days
find /backups -name "gsc_*.sql.gz" -mtime +30 -delete
```

### Resource Planning

**Minimum requirements:**
- CPU: 2 cores
- RAM: 4GB
- Disk: 20GB

**Recommended for production:**
- CPU: 4 cores
- RAM: 8GB
- Disk: 100GB (with growth headroom)

**Scale up:**
```yaml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '4.0'
```

---

## Development Workflow

### Local Development

**Mount source code:**
```yaml
# In docker-compose.override.yml
services:
  insights_engine:
    volumes:
      - ./insights_core:/app/insights_core:ro
```

**Hot reload:**
```bash
docker-compose restart insights_engine
```

### Testing

**Run tests in container:**
```bash
# All tests
docker-compose run --rm insights_engine pytest

# Specific test
docker-compose run --rm insights_engine pytest tests/test_engine.py -v

# With coverage
docker-compose run --rm insights_engine pytest --cov=insights_core
```

### Debugging

**Interactive shell:**
```bash
docker-compose exec insights_engine /bin/bash
```

**Python REPL:**
```bash
docker-compose exec insights_engine python
>>> from insights_core.engine import InsightEngine
>>> engine = InsightEngine()
```

---

## Appendix

### Environment Variables Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| POSTGRES_DB | gsc_db | Yes | Database name |
| POSTGRES_USER | gsc_user | Yes | Database user |
| POSTGRES_PASSWORD | - | Yes | Database password |
| GSC_PROPERTIES | - | Yes | Comma-separated GSC properties |
| GA4_PROPERTY_ID | - | Yes | GA4 property ID |
| BACKFILL_DAYS | 60 | No | Days to backfill on startup |
| API_PORT | 8000 | No | Insights API port |
| RISK_THRESHOLD_CLICKS_PCT | -20 | No | Risk detection threshold |

### Port Reference

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Database |
| Insights API | 8000 | REST API |
| MCP Server | 8001 | MCP tools |
| Metrics Exporter | 8002 | Custom metrics |
| Grafana | 3000 | Dashboards |
| Prometheus | 9090 | Metrics DB |

### Volume Reference

| Volume | Mount Point | Purpose |
|--------|-------------|---------|
| pgdata | /var/lib/postgresql/data | Database storage |
| logs | /logs | Shared logs |
| secrets | /secrets | Credentials (read-only) |
| prometheus_data | /prometheus | Prometheus TSDB |
| grafana_data | /var/lib/grafana | Grafana config |

---

## Support

**Check documentation:**
- Architecture: `docs/ARCHITECTURE.md`
- API Reference: `docs/API_REFERENCE.md`
- Troubleshooting: `docs/deployment/TROUBLESHOOTING.md`

**Common commands:**
```bash
# Health check
docker-compose ps

# View logs
docker-compose logs -f

# Restart all
docker-compose restart

# Clean slate (DESTRUCTIVE)
docker-compose down -v
docker-compose up -d --build
```
