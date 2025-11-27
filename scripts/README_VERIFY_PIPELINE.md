# Pipeline Verification Script

## Overview

`verify_pipeline.py` is a comprehensive health check script for the SEO Intelligence Platform pipeline. It verifies data freshness, ingestion watermarks, insight generation, scheduler status, and overall pipeline health.

## Features

- **Database Connection Check**: Verifies PostgreSQL connectivity
- **Ingestion Watermark Monitoring**: Checks freshness of data ingestion for all sources (GSC, GA4, etc.)
- **Data Freshness Validation**: Ensures fact tables contain recent data
- **Insight Generation Monitoring**: Verifies insights have been generated recently
- **Scheduler Status Check**: Monitors scheduler activity and task execution
- **Table Data Validation**: Confirms critical tables contain data
- **Flexible Output Formats**: JSON or human-readable text output
- **Configurable Thresholds**: Customizable staleness detection
- **Exit Codes**: Returns 0 for healthy, 1 for unhealthy (perfect for CI/CD)

## Usage

### Basic Usage

```bash
# Run with defaults (human-readable output)
python scripts/verify_pipeline.py

# Check production environment
python scripts/verify_pipeline.py --environment production

# JSON output for scripting/monitoring
python scripts/verify_pipeline.py --format json

# Custom staleness threshold (48 hours)
python scripts/verify_pipeline.py --threshold-hours 48
```

### Command-Line Options

```
--environment ENV           Environment name (default: production or $ENVIRONMENT)
--format {json,human}       Output format (default: human)
--threshold-hours HOURS     Staleness threshold in hours (default: 36)
--insight-lookback HOURS    Hours to look back for insights (default: 24)
--dsn DSN                   Database connection string (default: $WAREHOUSE_DSN)
```

### Environment Variables

```bash
# Database connection
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/db"

# Environment
export ENVIRONMENT="production"

# Scheduler metrics file location (optional)
export SCHEDULER_METRICS_FILE="/logs/scheduler_metrics.json"
```

## Checks Performed

### 1. Database Connection
- Verifies PostgreSQL is accessible
- Returns database version information

### 2. Table Data
- Confirms critical tables contain data:
  - `gsc.fact_gsc_daily` (GSC data)
  - `gsc.insights` (Insights)
  - `gsc.ingest_watermarks` (Watermarks)
  - `analytics.fact_ga4_daily` (GA4 data - optional)

### 3. Ingestion Watermarks
- Checks all data source watermarks
- Detects stale ingestion (default: 36 hours)
- Identifies failed ingestion runs
- Reports days behind current date

**Pass Criteria:**
- All sources ran within threshold
- No failed ingestion runs

### 4. Data Freshness
- Validates GSC data is up-to-date (max 2-3 days behind)
- Checks GA4 data freshness (if configured)
- Monitors insight generation age

**Pass Criteria:**
- GSC data ≤ 2 days behind
- GA4 data ≤ 2 days behind (if configured)
- Insights ≤ threshold hours old

### 5. Insight Generation
- Confirms insights generated in last 24 hours (configurable)
- Reports breakdown by type and severity
- Shows insight status counts

**Pass Criteria:**
- At least 1 insight generated within lookback period

### 6. Scheduler Status
- Checks scheduler metrics file
- Verifies daily pipeline has run recently
- Reports hours since last run
- Falls back to audit log if metrics unavailable

**Pass Criteria:**
- Daily pipeline ran within 30 hours

## Output Formats

### Human-Readable (Default)

```
================================================================================
PIPELINE VERIFICATION REPORT
================================================================================
Timestamp: 2025-01-27T10:30:00
Environment: production
Duration: 1.23s

Overall Status: ✓ HEALTHY

Checks: 6 total
  ✓ Passed: 6
  ⚠ Warned: 0
  ✗ Failed: 0

--------------------------------------------------------------------------------
CHECK RESULTS
--------------------------------------------------------------------------------
✓ Database Connection: Database is accessible
    postgres_version: PostgreSQL 15.0
✓ Table Data: All critical tables contain data
✓ Ingestion Watermarks: All 4 ingestion sources are healthy
    total_watermarks: 4
    healthy_watermarks: 4
✓ GSC Data Freshness: GSC data is current (latest: 2025-01-26, 1 days behind)
    latest_date: 2025-01-26
    days_behind: 1
✓ Insights Freshness: Insights generated in last 12.5 hours
    total_insights: 45
✓ Scheduler Status: Scheduler is active (last daily run: 14.2 hours ago)

================================================================================
```

### JSON Format

```json
{
  "timestamp": "2025-01-27T10:30:00",
  "environment": "production",
  "duration_seconds": 1.23,
  "overall_status": "healthy",
  "summary": {
    "total_checks": 6,
    "passed": 6,
    "warned": 0,
    "failed": 0
  },
  "checks": [
    {
      "name": "Database Connection",
      "status": "pass",
      "message": "Database is accessible",
      "timestamp": "2025-01-27T10:30:00",
      "details": {
        "postgres_version": "PostgreSQL 15.0"
      }
    }
  ]
}
```

## Exit Codes

- **0**: Pipeline is healthy (all checks passed or only warnings)
- **1**: Pipeline is unhealthy (one or more checks failed)

## Integration Examples

### Cron Job

```bash
# Check pipeline health every hour
0 * * * * /path/to/verify_pipeline.py --format json > /var/log/pipeline_health.json

# Alert on failure
0 * * * * /path/to/verify_pipeline.py || echo "Pipeline unhealthy!" | mail -s "Alert" admin@example.com
```

### CI/CD Pipeline

```yaml
# GitHub Actions
- name: Verify Pipeline Health
  run: |
    python scripts/verify_pipeline.py --environment production

# Exit code determines if build passes
```

### Monitoring Integration

```bash
# Prometheus/Grafana
python scripts/verify_pipeline.py --format json | jq '.summary.failed' > /metrics/pipeline_failed_checks.txt

# DataDog/NewRelic
python scripts/verify_pipeline.py --format json | curl -X POST https://api.datadoghq.com/api/v1/series \
  -H "DD-API-KEY: ${DD_API_KEY}" \
  -d @-
```

### Slack Notifications

```bash
#!/bin/bash
# Send to Slack if unhealthy
if ! python scripts/verify_pipeline.py; then
  python scripts/verify_pipeline.py --format json | \
    jq -r '.issues[] | "\(.check): \(.message)"' | \
    xargs -I {} curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Pipeline Issue: {}"}' \
      "$SLACK_WEBHOOK_URL"
fi
```

## Troubleshooting

### Database Connection Fails

```bash
# Check if database is running
docker ps | grep warehouse

# Test connection manually
psql "$WAREHOUSE_DSN"

# Verify credentials
echo $WAREHOUSE_DSN
```

### Stale Watermarks

```bash
# Check scheduler logs
docker logs scheduler

# Check scheduler metrics
cat /logs/scheduler_metrics.json

# Manually run ingestion
python ingestors/api/gsc_api_ingestor.py
```

### No Insights Generated

```bash
# Check insight engine logs
docker logs insights_engine

# Manually run insights
python scheduler/scheduler.py --test-insights

# Verify data exists
psql $WAREHOUSE_DSN -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily WHERE date >= CURRENT_DATE - 7"
```

### Scheduler Not Running

```bash
# Check scheduler container
docker ps -a | grep scheduler

# Check scheduler logs
docker logs scheduler

# Start scheduler
docker-compose up -d scheduler
```

## Customization

### Custom Thresholds

Edit thresholds in the script or pass as arguments:

```python
# In the script
DEFAULT_WATERMARK_THRESHOLD = 36  # hours
DEFAULT_INSIGHT_LOOKBACK = 24     # hours
GSC_MAX_DAYS_BEHIND = 2          # days
```

### Additional Checks

Add custom checks by extending the `PipelineVerifier` class:

```python
def check_custom_metric(self) -> bool:
    """Custom health check"""
    try:
        # Your check logic here
        conn = self._connect()
        # ... perform check

        self._add_check(
            'Custom Metric',
            'pass',
            'Custom check passed',
            {'detail': 'value'}
        )
        return True
    except Exception as e:
        self._add_check(
            'Custom Metric',
            'fail',
            f'Custom check failed: {str(e)}'
        )
        return False
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/scripts/test_verify_pipeline.py -v

# Run specific test
pytest tests/scripts/test_verify_pipeline.py::TestPipelineVerifier::test_check_database_connection_success -v

# With coverage
pytest tests/scripts/test_verify_pipeline.py --cov=scripts.verify_pipeline --cov-report=html
```

## Best Practices

1. **Run Regularly**: Schedule hourly or daily checks
2. **Monitor Trends**: Track metrics over time to identify patterns
3. **Set Alerts**: Configure notifications for failures
4. **Custom Thresholds**: Adjust based on your SLA requirements
5. **Log Results**: Store results for historical analysis
6. **Automate Actions**: Trigger remediation on failures

## Related Scripts

- `scripts/operations/health-check.sh` - Quick health check
- `scheduler/scheduler.py` - Pipeline scheduler
- `scripts/backfill_historical.py` - Historical data backfill

## Support

For issues or questions:
- Check logs: `docker logs <service>`
- Review metrics: `cat /logs/scheduler_metrics.json`
- Inspect database: `psql $WAREHOUSE_DSN`
- See TROUBLESHOOTING.md for common issues
