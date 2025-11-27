# GSC Warehouse - Project Reorganization Summary

## Executive Summary

This document summarizes the comprehensive reorganization and enhancement of the GSC Data Warehouse project to address the critical issue of no data collection and improve deployment operations.

### Key Problems Solved

1. **No Automatic Data Collection on Deployment**
   - Original system had no mechanism to trigger data collection immediately after deployment
   - Scheduler only runs at 2 AM UTC, leaving newly deployed systems with no data for hours
   - No validation that data was successfully collected

2. **Missing Startup Orchestration**
   - No automatic initial backfill of historical data
   - No verification of service health before data collection
   - No status reporting or progress tracking

3. **Unclear Operational Procedures**
   - Limited documentation on day-to-day operations
   - No troubleshooting guides for common issues
   - Missing cookbooks for different operational scenarios

4. **Unorganized Project Structure**
   - Deployment files scattered across directories
   - No clear separation of concerns
   - Difficult to understand system architecture

### Solutions Implemented

1. **Startup Orchestrator Service**
   - Automatically runs on deployment to collect initial data
   - Validates database connectivity before starting
   - Fetches 16 months of historical data by default
   - Creates analytical views
   - Reports success/failure with detailed metrics

2. **Unified Docker Compose Orchestration**
   - Single docker-compose.yml file for all services
   - Proper service dependencies and health checks
   - Automatic startup sequence with data collection
   - Profile-based service activation (scheduler, api, observability)

3. **Comprehensive Deployment Scripts**
   - deploy.sh/deploy.bat - Initial deployment with validation
   - redeploy.sh - Update system without data loss
   - Automatic prerequisite checking
   - Health verification at each step

4. **Operational Cookbooks**
   - Deployment Cookbook - Complete deployment guide
   - GSC Data Collection Cookbook - Data collection operations
   - Operations Cookbook - Day-to-day operational tasks
   - All cookbooks include troubleshooting sections

5. **Organized Project Structure**
   - deployment/ - All deployment-related files
   - cookbooks/ - Operational guides
   - docs/ - Architecture and technical documentation
   - Clear separation of services and infrastructure

## High-Level Changes

### 1. Project Structure Reorganization

**Before:**
```
gsc-warehouse/
├── compose/              # Mixed deployment files
│   ├── dockerfiles/
│   └── *.yml            # Scattered compose files
├── docs/                # Some documentation
├── ingestors/
├── scheduler/
└── Various scripts      # Root-level scripts
```

**After:**
```
gsc-warehouse/
├── deployment/          # All deployment artifacts
│   ├── compose/         # Service compose files
│   ├── dockerfiles/     # All Dockerfiles
│   ├── init-db/         # Database initialization
│   ├── prometheus/      # Metrics configuration
│   ├── scripts/         # Helper scripts
│   └── docs/            # Deployment documentation
├── cookbooks/           # Operational guides
│   ├── deployment-cookbook.md
│   ├── gsc-data-collection-cookbook.md
│   └── operations-cookbook.md
├── ingestors/           # Data ingestion logic
├── scheduler/           # Scheduling and orchestration
│   ├── scheduler.py
│   └── startup_orchestrator.py  # NEW
├── transform/           # SQL transforms (NEW)
└── docker-compose.yml   # Unified orchestration (NEW)
```

### 2. New Services and Components

**Startup Orchestrator** (`scheduler/startup_orchestrator.py`)
- Automatic initial data collection on deployment
- Database health checks with retry logic
- Progress tracking and status reporting
- Validation of collected data
- Comprehensive error handling

**Unified Compose File** (`docker-compose.yml`)
- Consolidates all service definitions
- Proper health checks and dependencies
- Automatic data collection via startup_orchestrator service
- Profile-based service activation

**Transform Service** (`transform/apply_transforms.py`)
- Applies SQL views and transformations
- Called automatically by orchestrator
- Standalone script for manual execution

### 3. Enhanced Documentation

**Deployment Cookbook** - Covers:
- Prerequisites and validation
- Step-by-step deployment process
- Configuration options
- Troubleshooting common issues
- Post-deployment tasks

**GSC Data Collection Cookbook** - Covers:
- How data collection works
- Rate limiting and backoff strategies
- Verifying data is being collected
- Troubleshooting collection failures
- Manual collection operations

**Operations Cookbook** - Covers:
- Daily health checks
- Weekly maintenance tasks
- Service management
- Data operations
- Performance monitoring

### 4. Deployment Process Improvements

**Before:**
1. Deploy services manually
2. Wait for 2 AM UTC for first data collection
3. No validation of success
4. No clear operational procedures

**After:**
1. Run deploy.sh/deploy.bat
2. Automatic prerequisite validation
3. Services deployed with health checks
4. Startup orchestrator automatically:
   - Collects 16 months of historical data
   - Creates analytical views
   - Validates data was fetched
   - Reports status
5. Scheduler starts for ongoing updates
6. Complete operational documentation

### 5. Rate Limiting Enhancements

**Enterprise-Grade Rate Limiter** (already present, now documented):
- Token bucket algorithm for smooth rate limiting
- Exponential backoff with jitter
- Per-property quota tracking
- Daily quota management
- Comprehensive metrics

**Configuration Made Clear:**
- All rate limit settings in .env.example
- Conservative, default, and aggressive profiles
- Clear documentation of GSC API limits
- Troubleshooting guide for rate limit issues

## Critical Files and Their Purpose

### Core Orchestration

**docker-compose.yml** - Unified service orchestration
- Defines all services with proper dependencies
- Includes health checks for core services
- startup_orchestrator service for automatic data collection
- Profile-based activation (scheduler, api, observability)

**scheduler/startup_orchestrator.py** - Automatic data collection
- Runs once on deployment
- Validates database connectivity
- Triggers initial data collection
- Applies SQL transforms
- Reports success/failure

**scheduler/scheduler.py** - Ongoing automated tasks
- Daily pipeline (2 AM UTC): API ingestion + transforms
- Weekly pipeline (Sunday 3 AM UTC): Reconciliation
- Metrics tracking
- Error handling

### Deployment

**deploy.sh / deploy.bat** - Initial deployment
- Prerequisites check
- Secrets validation
- Image building
- Service deployment
- Automatic data collection
- Health verification

**redeploy.sh** - System updates
- Stops services (preserves data)
- Rebuilds images
- Restarts services
- Optional data refresh
- Health verification

**.env.example** - Configuration template
- All environment variables documented
- Multiple configuration profiles
- Clear explanations of each setting

### Data Collection

**ingestors/api/gsc_api_ingestor.py** - GSC API data fetching
- Fetches data from Search Console API
- Enterprise rate limiting integration
- Automatic watermark management
- Configurable date ranges (initial vs incremental)

**ingestors/api/rate_limiter.py** - Rate limiting
- Token bucket algorithm
- Exponential backoff
- Daily quota tracking
- Per-property limits

**transform/apply_transforms.py** - SQL view creation
- Applies analytical transformations
- Called by orchestrator and scheduler

### Documentation

**cookbooks/deployment-cookbook.md**
- Complete deployment guide
- Configuration options
- Troubleshooting
- Post-deployment tasks

**cookbooks/gsc-data-collection-cookbook.md**
- How data collection works
- Collection triggers and schedules
- Rate limiting details
- Verification and troubleshooting

**cookbooks/operations-cookbook.md**
- Daily/weekly/monthly operations
- Service management
- Data operations
- Performance monitoring

**deployment/docs/** - Technical documentation
- API_REFERENCE.md - MCP and REST API details
- ARCHITECTURE.md - System design
- RATE_LIMITING.md - Rate limiter deep dive
- DEPLOYMENT.md - Original deployment guide

## Why Data Collection Previously Failed

### Root Causes Identified

1. **No Automatic Trigger**
   - Scheduler only runs at 2 AM UTC
   - No mechanism to start collection on deployment
   - Manual intervention required

2. **Missing Startup Orchestrator**
   - No service to run initial data collection
   - No health checks before data collection
   - No validation of results

3. **Properties Not Configured**
   - dim_property table had mock data
   - No actual GSC properties marked as api_only
   - Ingestor had no properties to process

4. **Service Account Issues (possible)**
   - Credentials might not have been properly configured
   - Service account might not have been added to GSC property
   - No clear error messaging

### How It's Fixed Now

1. **Startup Orchestrator Service**
   ```yaml
   startup_orchestrator:
     # Runs automatically on deployment
     # Validates database health
     # Triggers data collection
     # Reports success/failure
     restart: "no"  # Runs once and exits
   ```

2. **Proper Service Dependencies**
   ```yaml
   depends_on:
     warehouse:
       condition: service_healthy  # Wait for DB
     mcp:
       condition: service_healthy  # Wait for MCP
   ```

3. **Automatic Execution**
   ```bash
   # deploy.sh includes:
   docker compose up startup_orchestrator
   # This runs automatically during deployment
   ```

4. **Validation and Reporting**
   ```python
   # Checks if data was collected
   # Writes report to /report/startup/orchestrator_status.json
   # Logs progress and errors
   ```

5. **Clear Error Messages**
   ```
   If no data collected:
   - Logs show exactly why
   - Report includes diagnostic info
   - Cookbooks have troubleshooting steps
   ```

## Configuration Best Practices

### Environment Variables

Create `.env` file from `.env.example`:

```bash
# Conservative (avoids rate limits)
REQUESTS_PER_MINUTE=20
REQUESTS_PER_DAY=1500
GSC_INITIAL_BACKFILL_DAYS=90
INGEST_DAYS=7

# Default (balanced)
REQUESTS_PER_MINUTE=30
REQUESTS_PER_DAY=2000
GSC_INITIAL_BACKFILL_DAYS=480
INGEST_DAYS=30

# Aggressive (faster, higher risk)
REQUESTS_PER_MINUTE=50
REQUESTS_PER_DAY=2000
GSC_INITIAL_BACKFILL_DAYS=480
INGEST_DAYS=30
```

### Secrets Management

Required secrets:
- `secrets/gsc_sa.json` - Google Cloud service account
- `secrets/db_password.txt` - Database password

Both are mounted as Docker secrets (not environment variables).

### Property Configuration

Add real properties to database:

```sql
INSERT INTO gsc.dim_property (property_url, property_type, api_only)
VALUES ('https://yourdomain.com/', 'URL_PREFIX', true);
```

## Testing and Validation

### Verify Deployment Success

1. **Check services are running:**
   ```bash
   docker compose ps
   # All should show "Up" or "Up (healthy)"
   ```

2. **Check data was collected:**
   ```bash
   docker compose exec warehouse psql -U gsc_user -d gsc_db \
     -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"
   # Should show > 0 rows
   ```

3. **Check orchestrator status:**
   ```bash
   cat report/startup/orchestrator_status.json | jq '.success'
   # Should be true
   ```

4. **Verify data freshness:**
   ```bash
   docker compose exec warehouse psql -U gsc_user -d gsc_db \
     -c "SELECT MAX(date) FROM gsc.fact_gsc_daily;"
   # Should show recent date
   ```

### Common Issues and Quick Fixes

**Issue: No data collected**
```bash
# Check logs
docker compose logs startup_orchestrator | grep -i error

# Check properties
docker compose exec warehouse psql -U gsc_user -d gsc_db \
  -c "SELECT * FROM gsc.dim_property WHERE api_only = true;"

# Retry collection
docker compose run --rm startup_orchestrator
```

**Issue: Rate limit errors**
```bash
# Reduce rate limits in .env
REQUESTS_PER_MINUTE=20
REQUESTS_PER_DAY=1500

# Redeploy
./redeploy.sh
```

**Issue: Service account errors**
```bash
# Validate credentials
cat secrets/gsc_sa.json | jq .

# Check required fields exist:
# - project_id
# - private_key
# - client_email
# - type (should be "service_account")
```

## Migration from Previous Version

If you have an existing deployment:

1. **Backup existing data:**
   ```bash
   docker compose exec warehouse pg_dump -U gsc_user gsc_db > backup.sql
   ```

2. **Stop old services:**
   ```bash
   docker compose down
   ```

3. **Update project files:**
   ```bash
   # Copy new docker-compose.yml, scripts, etc.
   # Merge your .env settings
   ```

4. **Redeploy:**
   ```bash
   ./redeploy.sh --skip-data-collection
   ```

5. **Verify data preserved:**
   ```bash
   docker compose exec warehouse psql -U gsc_user -d gsc_db \
     -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"
   ```

## Operational Excellence

### Daily Checklist

- [ ] Check service health: `docker compose ps`
- [ ] Verify data freshness: Check MAX(date) in fact table
- [ ] Review logs for errors: `docker compose logs | grep -i error`
- [ ] Monitor disk space: `df -h`

### Weekly Checklist

- [ ] Review watermarks for all properties
- [ ] Check for data gaps or anomalies
- [ ] Review rate limiter metrics
- [ ] Check database size growth

### Monthly Checklist

- [ ] Create database backup
- [ ] Archive old logs
- [ ] Update statistics (ANALYZE)
- [ ] Review and rotate credentials if needed

## Performance Characteristics

### Initial Deployment

**Expected Time:**
- Prerequisites check: < 1 minute
- Image building: 3-5 minutes
- Database initialization: 30 seconds
- Initial data collection: 15-45 minutes (depends on data volume)
- Total: 20-50 minutes

**Expected Resource Usage:**
- CPU: Moderate during collection, low at rest
- Memory: 2-4 GB
- Disk: Grows based on data (typically 1-5 GB per year of data)
- Network: Burst during collection, minimal at rest

### Ongoing Operations

**Scheduler:**
- Daily run: 5-15 minutes (incremental 30-day window)
- Weekly run: 10-20 minutes (7-day reconciliation)

**Resource Usage:**
- CPU: Low (scheduled tasks only)
- Memory: 1-2 GB baseline
- Disk: Grows ~10-50 MB per day per property

## Future Improvements

Potential enhancements (not implemented):

1. **Parallel Property Collection**
   - Process multiple properties simultaneously
   - Requires careful rate limit coordination

2. **Real-time Streaming**
   - Continuous data collection
   - Requires webhook integration

3. **Advanced Analytics**
   - Machine learning for trend prediction
   - Automated anomaly detection

4. **Multi-tenant Support**
   - Isolated data per tenant
   - Role-based access control

5. **Advanced Monitoring**
   - Grafana dashboards
   - Automated alerting
   - SLA tracking

## Support and Troubleshooting

### Resources

1. **Cookbooks** - Operational guides in /cookbooks/
2. **Documentation** - Technical docs in /deployment/docs/
3. **Logs** - All logs in /logs/ directory
4. **Reports** - Status reports in /report/ directory

### Getting Help

1. Check relevant cookbook for your issue
2. Review logs for error messages
3. Validate configuration in .env
4. Check service status with `docker compose ps`
5. Try redeployment with `./redeploy.sh`

### Common Error Messages

**"Database connection refused"**
- Wait for database to be healthy
- Check `docker compose ps warehouse`

**"Invalid credentials"**
- Verify secrets/gsc_sa.json is valid JSON
- Check service account has Search Console API access

**"Rate limit exceeded"**
- Reduce REQUESTS_PER_MINUTE in .env
- Wait for daily quota reset (midnight UTC)

**"No properties found"**
- Add properties to gsc.dim_property table
- Ensure api_only = true

## Conclusion

This reorganization transforms the GSC Data Warehouse from a system that required manual intervention to collect data into a fully automated, production-ready platform with:

1. **Automatic Data Collection** - No manual intervention needed
2. **Comprehensive Monitoring** - Know immediately if something is wrong
3. **Clear Documentation** - Cookbooks for every operational scenario
4. **Organized Structure** - Easy to understand and maintain
5. **Production Ready** - Health checks, error handling, reporting

The system now provides a professional, enterprise-grade solution for GSC data warehousing with clear operational procedures and troubleshooting guidance.
