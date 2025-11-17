# Production Deployment Guide

## Pre-Production Checklist

### Security
- [ ] Change default passwords in `.env`
- [ ] Use Docker secrets for credentials
- [ ] Enable SSL for PostgreSQL
- [ ] Restrict network access (firewall rules)
- [ ] Setup backup strategy

### Performance
- [ ] Review PostgreSQL configuration (shared_buffers, work_mem)
- [ ] Setup connection pooling (PgBouncer)
- [ ] Configure autovacuum
- [ ] Enable query logging
- [ ] Setup Grafana dashboards

### Reliability
- [ ] Configure health checks
- [ ] Setup monitoring alerts
- [ ] Configure log rotation
- [ ] Test backup/restore procedures
- [ ] Document rollback procedures

## Production Architecture

```
┌─────────────────────────────────────┐
│         Load Balancer (Nginx)       │
└────────────┬────────────────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
┌─────────┐      ┌─────────┐
│ App 1   │      │ App 2   │
└────┬────┘      └────┬────┘
     │                │
     └────────┬───────┘
              │
              ▼
     ┌──────────────┐
     │ PostgreSQL   │
     │ (Primary)    │
     └──────┬───────┘
            │
     ┌──────┴───────┐
     │              │
     ▼              ▼
┌─────────┐    ┌─────────┐
│Replica 1│    │Replica 2│
└─────────┘    └─────────┘
```

## Deployment Steps

### 1. Server Setup
```bash
# Install dependencies
sudo apt update
sudo apt install -y docker.io docker-compose postgresql-client

# Create application user
sudo useradd -m -s /bin/bash gsc
sudo usermod -aG docker gsc

# Setup application directory
sudo mkdir -p /opt/gsc-warehouse
sudo chown gsc:gsc /opt/gsc-warehouse
```

### 2. Deploy Code
```bash
# As gsc user
cd /opt/gsc-warehouse
git clone <repository-url> .

# Setup environment
cp .env.template .env
# Edit .env with production values

# Setup secrets securely
sudo mkdir -p /etc/gsc-secrets
sudo cp secrets/gsc_sa.json /etc/gsc-secrets/
sudo chown gsc:gsc /etc/gsc-secrets
sudo chmod 600 /etc/gsc-secrets/*
```

### 3. Database Setup
```bash
# Start database
docker-compose up -d warehouse

# Run migrations
for script in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$script"
done

# Create backup user
psql $WAREHOUSE_DSN -c "
    CREATE ROLE backup_user WITH LOGIN PASSWORD 'backup_pass';
    GRANT SELECT ON ALL TABLES IN SCHEMA gsc TO backup_user;
"
```

### 4. Start Services
```bash
docker-compose up -d
```

### 5. Setup Monitoring
```bash
# Configure Grafana
curl -X POST http://admin:admin@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PostgreSQL",
    "type": "postgres",
    "url": "warehouse:5432",
    "database": "gsc_db",
    "user": "gsc_user",
    "secureJsonData": {"password": "gsc_pass"}
  }'
```

### 6. Setup Cron Jobs
```bash
# Edit crontab
crontab -e

# Add jobs
# Daily data collection (2 AM)
0 2 * * * cd /opt/gsc-warehouse && python ingestors/api/gsc_api_ingestor.py --auto
# Insight generation (2:30 AM)
30 2 * * * cd /opt/gsc-warehouse && python -m insights_core.cli refresh
# Agent pipeline (3 AM)
0 3 * * * cd /opt/gsc-warehouse && python agents/dispatcher/dispatcher_agent.py
# Daily backup (1 AM)
0 1 * * * /opt/gsc-warehouse/deployment/linux/backup.sh
```

## Monitoring

### Key Metrics
- Database size and growth rate
- Query response times
- Insight generation rate
- API rate limit consumption
- Docker container health
- Disk usage

### Alerting Rules
```yaml
# Prometheus alerts
groups:
  - name: gsc_alerts
    rules:
      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 1m
        
      - alert: HighQueryLatency
        expr: pg_stat_statements_mean_exec_time > 5000
        for: 5m
        
      - alert: DiskSpaceHigh
        expr: disk_usage_percent > 80
        for: 10m
```

## Backup Strategy

### Daily Backups
```bash
# Automated via cron (see above)
./deployment/linux/backup.sh
```

### Retention Policy
- Daily backups: Keep 7 days
- Weekly backups: Keep 4 weeks
- Monthly backups: Keep 12 months

### Restore Procedure
```bash
# Stop services
docker-compose down

# Restore database
gunzip -c backups/20241115_020000/database.sql.gz | \
    psql $WAREHOUSE_DSN

# Start services
docker-compose up -d
```

## Scaling Considerations

### Vertical Scaling
- Increase PostgreSQL memory (shared_buffers)
- Add more CPU cores
- Faster SSD storage

### Horizontal Scaling
- Add read replicas for queries
- Partition large tables by date
- Use connection pooling (PgBouncer)

### Data Retention
```sql
-- Archive old data
CREATE TABLE gsc.fact_gsc_daily_archive AS
SELECT * FROM gsc.fact_gsc_daily
WHERE date < CURRENT_DATE - INTERVAL '1 year';

-- Delete from main table
DELETE FROM gsc.fact_gsc_daily
WHERE date < CURRENT_DATE - INTERVAL '1 year';
```

## Security Hardening

### 1. Network Security
```bash
# Firewall rules (UFW)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 5432/tcp   # PostgreSQL (internal only)
sudo ufw enable
```

### 2. Database Security
```sql
-- Restrict database access
REVOKE CONNECT ON DATABASE gsc_db FROM PUBLIC;
GRANT CONNECT ON DATABASE gsc_db TO gsc_user;

-- Restrict schema access
REVOKE ALL ON SCHEMA gsc FROM PUBLIC;
GRANT USAGE ON SCHEMA gsc TO gsc_user;
```

### 3. Application Security
```bash
# Run containers as non-root
# Add to docker-compose.yml:
user: "1000:1000"

# Limit container resources
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
```

## Rollback Procedures

### Database Rollback
```bash
# Restore from backup
./deployment/linux/backup.sh restore <backup_date>
```

### Application Rollback
```bash
# Checkout previous version
git checkout <previous_tag>

# Redeploy
docker-compose down
docker-compose up -d --build
```

## Maintenance Windows

### Weekly Maintenance (Sunday 3 AM)
- Vacuum database
- Refresh materialized views
- Analyze tables
- Review logs
- Update statistics

```sql
-- Maintenance script
VACUUM ANALYZE gsc.fact_gsc_daily;
VACUUM ANALYZE gsc.fact_ga4_daily;
REFRESH MATERIALIZED VIEW CONCURRENTLY gsc.mv_unified_page_performance;
```

## Support Contacts

- **On-Call:** [contact info]
- **Escalation:** [contact info]
- **Documentation:** [URL]
