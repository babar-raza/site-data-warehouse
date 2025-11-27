# Canary Checks - Quick Start Guide

## Installation

```bash
# Install dependencies
pip install psycopg2-binary httpx
```

## Quick Usage

### 1. Basic Check
```bash
# Check production
python scripts/canary_checks.py --environment production

# Check staging
python scripts/canary_checks.py --environment staging
```

### 2. With Verbose Output
```bash
python scripts/canary_checks.py --environment production --verbose
```

### 3. Save Report
```bash
python scripts/canary_checks.py --environment production --output report.json
```

## Environment Setup

```bash
# Required environment variables
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/database"
export INSIGHTS_API_URL="http://localhost:8001"

# Optional
export SCHEDULER_METRICS_FILE="/logs/scheduler_metrics.json"
```

## What Gets Checked

1. ✅ Database connectivity
2. ✅ Critical tables exist
3. ✅ Recent data ingestion (last 3 days)
4. ✅ Recent insights created (last 48 hours)
5. ✅ Insights API health
6. ✅ Insights API query functionality
7. ✅ Scheduler last run (last 36 hours)
8. ✅ Data quality (no nulls/negative values)

## Exit Codes

- `0` = All checks passed ✅
- `1` = One or more checks failed ❌

## Docker Usage

```bash
# One-time check
docker-compose -f compose/docker-compose.canary.yml run --rm canary-checks

# Continuous monitoring (every 6 hours)
docker-compose -f compose/docker-compose.canary.yml up canary-checks-scheduled
```

## CI/CD Integration

```yaml
# GitHub Actions
- name: Canary Checks
  run: python scripts/canary_checks.py --environment production --output report.json
```

## Parse Results

```bash
# Check status
STATUS=$(jq -r '.overall_status' report.json)

# Get failed checks
jq -r '.checks[] | select(.status == "fail") | .name' report.json

# Get summary
jq -r '.summary' report.json
```

## Troubleshooting

### Database Connection Failed
```bash
# Test connection
psql $WAREHOUSE_DSN -c "SELECT 1"

# Check if warehouse is running
docker-compose ps warehouse
```

### API Not Responding
```bash
# Test API directly (Insights API on port 8000)
curl http://localhost:8000/api/health

# Check if API is running
docker-compose ps insights_api
```

### Old Data Detected
```bash
# Check data age
psql $WAREHOUSE_DSN -c "SELECT MAX(date) FROM gsc.fact_gsc_daily"

# Run manual ingestion
python ingestors/api/gsc_api_ingestor.py
```

## Next Steps

- Read full documentation: `scripts/README_CANARY_CHECKS.md`
- View examples: `examples/canary_checks_example.sh`
- Run tests: `pytest tests/scripts/test_canary_checks.py`

## Support

For help:
```bash
python scripts/canary_checks.py --help
```
