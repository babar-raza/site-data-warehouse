# Canary Checks Script

## Overview

The `canary_checks.py` script validates critical functionality of the Site Data Warehouse in staging and production environments. It performs comprehensive health checks on database connectivity, API endpoints, data freshness, and scheduler operations.

## Features

- **Database Health Checks**
  - Database connectivity validation
  - Critical table existence verification
  - Recent data ingestion monitoring
  - Data quality checks

- **API Health Checks**
  - Insights API health endpoint validation
  - API query functionality testing

- **Scheduler Checks**
  - Scheduler last run verification
  - Watermark update monitoring

- **Insights Checks**
  - Recent insight creation validation
  - Insight generation health monitoring

- **CI/CD Integration**
  - JSON output for automated parsing
  - Exit codes: 0 (pass), 1 (fail)
  - Structured result format

## Requirements

Install required dependencies:

```bash
pip install psycopg2-binary httpx
```

## Usage

### Basic Usage

```bash
# Check production environment
python scripts/canary_checks.py --environment production

# Check staging environment
python scripts/canary_checks.py --environment staging
```

### Advanced Options

```bash
# Verbose logging
python scripts/canary_checks.py --environment production --verbose

# Save JSON report to file
python scripts/canary_checks.py --environment production --output /path/to/report.json

# Short form flags
python scripts/canary_checks.py -e production -v -o report.json
```

## Environment Configuration

The script uses environment variables to configure connections:

### Production Environment

```bash
export ENVIRONMENT=production
export WAREHOUSE_DSN=postgresql://user:pass@warehouse:5432/seo_warehouse
export INSIGHTS_API_URL=http://insights-api:8001
export SCHEDULER_METRICS_FILE=/logs/scheduler_metrics.json
```

### Staging Environment

```bash
export ENVIRONMENT=staging
export WAREHOUSE_DSN_STAGING=postgresql://user:pass@warehouse-staging:5432/seo_warehouse
export INSIGHTS_API_URL_STAGING=http://insights-api-staging:8001
export SCHEDULER_METRICS_FILE_STAGING=/logs/scheduler_metrics.json
```

## Checks Performed

### 1. Database Connectivity
- **Status**: Critical
- **Validates**: PostgreSQL connection
- **Thresholds**: N/A
- **Failure Impact**: Cannot perform other checks

### 2. Critical Tables Exist
- **Status**: Critical
- **Validates**: `fact_gsc_daily`, `insights`, `ingest_watermarks`, `dim_property`
- **Thresholds**: All tables must exist
- **Failure Impact**: System not properly initialized

### 3. Recent Data Ingestion
- **Status**: Critical
- **Validates**: Latest data in `fact_gsc_daily`
- **Thresholds**: Data ≤ 3 days old
- **Failure Impact**: Data pipeline not running

### 4. Recent Insights Created
- **Status**: Warning on fail
- **Validates**: Insights generation
- **Thresholds**: Insights created in last 48 hours
- **Failure Impact**: Insight engine may be down

### 5. Insights API Health
- **Status**: Critical
- **Validates**: API `/api/health` endpoint
- **Thresholds**: Status = "healthy"
- **Failure Impact**: Cannot query insights via API

### 6. Insights API Query
- **Status**: Warning on fail
- **Validates**: API query functionality
- **Thresholds**: Successful query response
- **Failure Impact**: API may be degraded

### 7. Scheduler Last Run
- **Status**: Critical
- **Validates**: Scheduler execution
- **Thresholds**: Ran in last 36 hours
- **Failure Impact**: Data pipeline not scheduled

### 8. Data Quality Basic
- **Status**: Warning on fail
- **Validates**: No null values or negative metrics
- **Thresholds**: Zero quality issues
- **Failure Impact**: Data integrity concerns

## Output Format

### Console Output

```
2025-11-27 10:30:00 - INFO - Starting canary checks for environment: production
2025-11-27 10:30:00 - INFO - Running check: Database Connectivity
2025-11-27 10:30:01 - INFO - ✓ Database Connectivity: Database connection successful
...
======================================================================
Canary Check Summary - PRODUCTION
======================================================================
Overall Status: PASS
Checks Passed:  8/8
Checks Failed:  0/8
Checks Warned:  0/8
Duration:       1234.56ms
======================================================================
```

### JSON Output

```json
{
  "environment": "production",
  "timestamp": "2025-11-27T10:30:00.000000Z",
  "overall_status": "pass",
  "summary": {
    "total_checks": 8,
    "passed": 8,
    "failed": 0,
    "warned": 0,
    "duration_ms": 1234.56
  },
  "checks": [
    {
      "name": "database_connectivity",
      "status": "pass",
      "duration_ms": 45.23,
      "message": "Database connection successful",
      "details": {
        "database": "seo_warehouse",
        "user": "seo_admin",
        "version": "PostgreSQL 14.5"
      },
      "error": null
    },
    ...
  ]
}
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Canary Checks

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  canary-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install psycopg2-binary httpx

      - name: Run canary checks
        env:
          WAREHOUSE_DSN: ${{ secrets.WAREHOUSE_DSN }}
          INSIGHTS_API_URL: ${{ secrets.INSIGHTS_API_URL }}
        run: |
          python scripts/canary_checks.py \
            --environment production \
            --output canary-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: canary-report
          path: canary-report.json
```

### Docker Compose Example

```yaml
services:
  canary-checks:
    build: .
    command: python scripts/canary_checks.py --environment production
    environment:
      - WAREHOUSE_DSN=${WAREHOUSE_DSN}
      - INSIGHTS_API_URL=${INSIGHTS_API_URL}
    depends_on:
      - warehouse
      - insights-api
```

## Exit Codes

- **0**: All checks passed
- **1**: One or more checks failed

## Thresholds and Tolerances

| Check | Threshold | Tolerance |
|-------|-----------|-----------|
| Data Age | 3 days | Hard limit |
| Insight Age | 48 hours | Hard limit |
| Scheduler Age | 36 hours | Hard limit (daily + buffer) |
| Data Quality | 0 issues | Warning only |
| API Response | 10 seconds | Timeout |

## Troubleshooting

### Database Connection Failed

```bash
# Check database is running
docker-compose ps warehouse

# Check connection string
echo $WAREHOUSE_DSN

# Test connection manually
psql $WAREHOUSE_DSN -c "SELECT 1"
```

### API Not Responding

```bash
# Check API is running
docker-compose ps insights_api

# Check API health directly (Insights API on port 8000)
curl http://localhost:8000/api/health

# Check API logs
docker-compose logs insights_api
```

### Old Data Detected

```bash
# Check scheduler logs
docker-compose logs scheduler

# Check last ingestion
psql $WAREHOUSE_DSN -c "SELECT MAX(date) FROM gsc.fact_gsc_daily"

# Trigger manual ingestion
python ingestors/api/gsc_api_ingestor.py
```

### No Recent Insights

```bash
# Check insight engine logs
docker-compose logs insights-engine

# Run insight engine manually
python scheduler/scheduler.py --test-insights

# Check insight count
psql $WAREHOUSE_DSN -c "SELECT COUNT(*) FROM gsc.insights WHERE generated_at >= NOW() - INTERVAL '48 hours'"
```

## Development

### Running Tests

```bash
# Syntax check
python -m py_compile scripts/canary_checks.py

# Help output
python scripts/canary_checks.py --help

# Dry run (requires environment setup)
python scripts/canary_checks.py --environment staging --verbose
```

### Adding New Checks

1. Create a new method in `CanaryChecker` class:
   ```python
   def check_new_feature(self) -> CheckResult:
       """Check if new feature is working"""
       try:
           # Perform check
           return CheckResult(
               name="new_feature",
               status="pass",
               duration_ms=0,
               message="Feature working correctly"
           )
       except Exception as e:
           return CheckResult(
               name="new_feature",
               status="fail",
               duration_ms=0,
               message="Feature check failed",
               error=str(e)
           )
   ```

2. Add to `checks` list in `run_all_checks()`:
   ```python
   checks = [
       ...,
       ("New Feature Check", self.check_new_feature)
   ]
   ```

## Best Practices

1. **Run regularly**: Schedule canary checks every 6-12 hours
2. **Monitor trends**: Track check duration over time
3. **Alert on failures**: Integrate with monitoring systems
4. **Review warnings**: Investigate warnings before they become failures
5. **Update thresholds**: Adjust based on operational experience
6. **Version reports**: Keep historical reports for analysis

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review troubleshooting section above
- Check system status: `docker-compose ps`
- Verify environment variables: `env | grep -E "(WAREHOUSE|API|SCHEDULER)"`

## License

Part of the Site Data Warehouse project.
