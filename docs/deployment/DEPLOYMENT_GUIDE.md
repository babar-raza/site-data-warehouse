# Deployment Guide

## Overview

This guide covers the complete deployment process for the GSC Warehouse multi-agent analytics system.

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.9 or higher
- **PostgreSQL**: 14.0 or higher
- **Memory**: Minimum 8GB RAM (16GB+ recommended for production)
- **Storage**: 100GB+ available disk space
- **Network**: Stable internet connection for API access

### Required Accounts & Credentials

1. **Google Search Console API**
   - Service account credentials (JSON file)
   - Property access permissions

2. **Google Analytics 4**
   - Service account credentials (JSON file)
   - Property access permissions
   - Property ID

3. **Database**
   - PostgreSQL superuser access for initial setup
   - Dedicated database user credentials

## Pre-Deployment Checklist

- [ ] All prerequisites met
- [ ] Credentials obtained and secured
- [ ] Target environment accessible
- [ ] Backup procedures tested
- [ ] Rollback plan documented

## Deployment Steps

### 1. Environment Setup

#### 1.1 Clone Repository

```bash
git clone <repository-url>
cd gsc-warehouse
```

#### 1.2 Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 1.3 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Database Setup

#### 2.1 Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE gsc_warehouse;
CREATE USER gsc_user WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE gsc_warehouse TO gsc_user;
\q
```

#### 2.2 Initialize Schema

```bash
# Run all SQL scripts in order
psql -U gsc_user -d gsc_warehouse -f sql/001_create_schemas.sql
psql -U gsc_user -d gsc_warehouse -f sql/002_create_tables.sql
psql -U gsc_user -d gsc_warehouse -f sql/003_create_views.sql
psql -U gsc_user -d gsc_warehouse -f sql/004_create_functions.sql
psql -U gsc_user -d gsc_warehouse -f sql/005_create_indexes.sql
```

### 3. Configuration

#### 3.1 Create Environment File

```bash
cp .env.example .env
```

#### 3.2 Configure Environment Variables

Edit `.env` with your settings:

```bash
# Database Configuration
WAREHOUSE_HOST=localhost
WAREHOUSE_PORT=5432
WAREHOUSE_USER=gsc_user
WAREHOUSE_PASSWORD=secure_password_here
WAREHOUSE_DB=gsc_warehouse
WAREHOUSE_DSN=postgresql://gsc_user:secure_password_here@localhost:5432/gsc_warehouse

# Google Search Console API
GSC_CREDENTIALS_FILE=/path/to/gsc-credentials.json
GSC_PROPERTY_URL=sc-domain:yourdomain.com

# Google Analytics 4
GA4_CREDENTIALS_FILE=/path/to/ga4-credentials.json
GA4_PROPERTY_ID=123456789

# Agent Configuration
AGENT_WATCHER_SENSITIVITY=2.5
AGENT_DIAGNOSTICIAN_THRESHOLD=0.7
AGENT_STRATEGIST_MIN_IMPACT=5.0
AGENT_DISPATCHER_MAX_PARALLEL=3

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/gsc-warehouse/app.log
```

#### 3.3 Secure Credentials

```bash
# Place credential files in secure location
mkdir -p /etc/gsc-warehouse/credentials
cp gsc-credentials.json /etc/gsc-warehouse/credentials/
cp ga4-credentials.json /etc/gsc-warehouse/credentials/
chmod 600 /etc/gsc-warehouse/credentials/*
```

### 4. Initial Data Load

#### 4.1 Validate API Access

```bash
python validate-setup.sh
```

#### 4.2 Perform Initial Ingestion

```bash
# Start with 7 days of historical data
python start-collection.sh --days 7
```

#### 4.3 Refresh Materialized Views

```bash
python warehouse/refresh_views.py --view all
```

### 5. Agent Deployment

#### 5.1 Initialize Agent Infrastructure

```bash
# Create agent data directories
mkdir -p data/messages
mkdir -p data/agent_state
mkdir -p logs/agents

# Set permissions
chmod 755 data/
chmod 755 logs/
```

#### 5.2 Test Individual Agents

```bash
# Test watcher
python agents/watcher/watcher_agent.py --test

# Test diagnostician
python agents/diagnostician/diagnostician_agent.py --test

# Test strategist
python agents/strategist/strategist_agent.py --test

# Test dispatcher
python agents/dispatcher/dispatcher_agent.py --test
```

#### 5.3 Start Agent Orchestration

```bash
# Start all agents
python bootstrap.py --mode production
```

### 6. Monitoring Setup

#### 6.1 Configure Prometheus

```bash
# Start metrics exporter
cd metrics_exporter
python exporter.py &
```

#### 6.2 Verify Metrics Endpoint

```bash
curl http://localhost:9090/metrics
```

### 7. Validation

#### 7.1 Run Integration Tests

```bash
pytest tests/e2e/ -v --tb=short
```

#### 7.2 Verify Data Flow

```bash
# Check data ingestion
psql -U gsc_user -d gsc_warehouse -c "SELECT COUNT(*) FROM gsc.search_analytics;"

# Check agent activity
psql -U gsc_user -d gsc_warehouse -c "SELECT agent_id, COUNT(*) FROM gsc.findings GROUP BY agent_id;"

# Check recommendations
psql -U gsc_user -d gsc_warehouse -c "SELECT priority, COUNT(*) FROM gsc.recommendations GROUP BY priority;"
```

#### 7.3 Health Check

```bash
./health-check.sh
```

### 8. Scheduler Setup

#### 8.1 Configure Scheduled Tasks

Edit `scheduler/schedule_config.yaml`:

```yaml
schedules:
  data_collection:
    cron: "0 */6 * * *"  # Every 6 hours
    script: start-collection.sh
  
  view_refresh:
    cron: "30 */6 * * *"  # 30 minutes after collection
    script: warehouse/refresh_views.py --view all
  
  agent_orchestration:
    cron: "0 * * * *"  # Every hour
    script: bootstrap.py --mode scheduled
```

#### 8.2 Start Scheduler

```bash
cd scheduler
python scheduler_daemon.py start
```

## Post-Deployment Tasks

### 1. Monitoring Setup

- [ ] Configure alerting thresholds
- [ ] Set up dashboard access
- [ ] Test alert notifications
- [ ] Document metric baselines

### 2. Backup Configuration

```bash
# Create backup script
./backup.sh --initial

# Schedule daily backups
crontab -e
# Add: 0 2 * * * /path/to/gsc-warehouse/backup.sh
```

### 3. Documentation

- [ ] Update runbooks with environment-specific details
- [ ] Document custom configurations
- [ ] Create team access matrix
- [ ] Record deployment date and version

### 4. Team Handoff

- [ ] Conduct walkthrough with operations team
- [ ] Provide access credentials (securely)
- [ ] Schedule follow-up check-in
- [ ] Establish escalation procedures

## Deployment Verification

### Automated Checks

```bash
# Run full validation suite
python tests/e2e/validate_production_ready.py

# Expected output:
# ✓ Database connectivity
# ✓ API credentials valid
# ✓ All agents initialized
# ✓ Data pipeline functional
# ✓ Monitoring active
```

### Manual Checks

1. **Data Ingestion**
   - Verify recent data in `gsc.search_analytics`
   - Check data freshness (< 24 hours old)

2. **Agent Activity**
   - Confirm findings generated today
   - Verify recommendations created
   - Check agent health status

3. **Performance**
   - Query response times < 1s
   - Agent processing < 5 minutes
   - No memory leaks detected

## Rollback Procedures

### Quick Rollback

```bash
# Stop all services
./stop.sh

# Restore from backup
./restore.sh --backup <backup-id>

# Restart services
./start-collection.sh
```

### Database Rollback

```bash
# Connect to database
psql -U gsc_user -d gsc_warehouse

# Drop schemas (BE CAREFUL!)
DROP SCHEMA gsc CASCADE;
DROP SCHEMA ga4 CASCADE;

# Restore from backup
pg_restore -U gsc_user -d gsc_warehouse backup_file.dump
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Escalation**: Contact DevOps team

## Deployment Checklist Summary

- [ ] Environment setup completed
- [ ] Database initialized and tested
- [ ] Configuration files updated
- [ ] Credentials secured
- [ ] Initial data load successful
- [ ] All agents deployed and running
- [ ] Monitoring configured
- [ ] Validation tests passed
- [ ] Backups configured
- [ ] Documentation updated
- [ ] Team trained
- [ ] Post-deployment review scheduled

## Version History

| Version | Date | Changes | Deployed By |
|---------|------|---------|-------------|
| 1.0.0   | TBD  | Initial deployment | - |

## Next Steps

After successful deployment:

1. Monitor system for 24-48 hours
2. Adjust agent sensitivity based on false positive rate
3. Optimize database queries if needed
4. Schedule regular maintenance windows
5. Plan for capacity expansion

---

**Document Status**: Ready for Review
**Last Updated**: 2025-01-14
**Owner**: DevOps Team
