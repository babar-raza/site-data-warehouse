# Monitoring Guide

## Overview

The GSC Data Warehouse includes comprehensive monitoring via Grafana and Prometheus.

## Access Grafana

**URL:** http://localhost:3000  
**Default credentials:** admin/admin (change in production!)

## Key Dashboards

### 1. System Health Dashboard
- Service uptime
- Container resource usage
- Database connections
- Query performance

### 2. Insight Engine Dashboard
- Insights generated per day
- Detection rate by category
- Detector execution time
- Error rate

### 3. Data Pipeline Dashboard
- Ingestion rate
- Data freshness
- API quota usage
- Failed ingestions

## Metrics

### Database Metrics
```sql
-- Query performance
SELECT 
    queryid,
    query,
    calls,
    mean_exec_time,
    stddev_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'gsc'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Connection count
SELECT COUNT(*) FROM pg_stat_activity;
```

### Application Metrics
```python
# Export custom metrics
from prometheus_client import Counter, Histogram

insights_generated = Counter('insights_generated_total', 'Total insights generated')
detector_duration = Histogram('detector_execution_seconds', 'Detector execution time')

# Use in code
insights_generated.inc()
with detector_duration.time():
    detector.detect()
```

## Alerting

### Critical Alerts
1. **Database Down**
   - Trigger: Database unavailable for >1 minute
   - Action: Restart database, check logs

2. **Disk Space Critical**
   - Trigger: >90% disk usage
   - Action: Clean old data, expand disk

3. **Insight Generation Failed**
   - Trigger: No insights generated for >24 hours
   - Action: Check logs, verify data ingestion

### Warning Alerts
1. **High Query Latency**
   - Trigger: Average query time >5s
   - Action: Review slow queries, optimize indexes

2. **API Quota Near Limit**
   - Trigger: >80% quota used
   - Action: Reduce collection frequency

## Health Checks

### Manual Health Check
```bash
# Check all services
docker-compose ps

# Check database
psql $WAREHOUSE_DSN -c "SELECT 1;"

# Check insights
psql $WAREHOUSE_DSN -c "
    SELECT 
        COUNT(*) as total,
        MAX(generated_at) as latest
    FROM gsc.insights
    WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';
"
```

### Automated Health Check
```bash
#!/bin/bash
# health_check.sh

# Database
psql $WAREHOUSE_DSN -c "SELECT 1;" >/dev/null 2>&1 || echo "❌ Database down"

# Recent data
ROWS=$(psql $WAREHOUSE_DSN -t -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily WHERE date >= CURRENT_DATE - INTERVAL '1 day';")
[ $ROWS -gt 0 ] && echo "✅ Data fresh" || echo "⚠️  No recent data"

# Recent insights
INSIGHTS=$(psql $WAREHOUSE_DSN -t -c "SELECT COUNT(*) FROM gsc.insights WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';")
[ $INSIGHTS -gt 0 ] && echo "✅ Insights fresh" || echo "⚠️  No recent insights"
```

## Log Management

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f insights_engine

# Last 100 lines
docker-compose logs --tail=100
```

### Log Rotation
```yaml
# docker-compose.yml logging config
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

## Performance Tuning

### PostgreSQL
```sql
-- Increase shared buffers (25% of RAM)
ALTER SYSTEM SET shared_buffers = '2GB';

-- Increase work memory
ALTER SYSTEM SET work_mem = '64MB';

-- Enable parallel queries
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;

-- Restart required
SELECT pg_reload_conf();
```

### Application
```python
# Connection pooling
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    dsn=warehouse_dsn
)
```

## Troubleshooting

See [TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md) for detailed troubleshooting steps.
