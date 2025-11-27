# Pipeline Verification Quick Start

## One-Liners

```bash
# Basic check
python scripts/verify_pipeline.py

# Production check with JSON output
python scripts/verify_pipeline.py --environment production --format json

# Strict check (24 hour threshold)
python scripts/verify_pipeline.py --threshold-hours 24

# Save to file
python scripts/verify_pipeline.py --format json > pipeline_health.json
```

## Common Use Cases

### 1. Cron Job - Hourly Health Check

```bash
# Add to crontab: crontab -e
0 * * * * cd /path/to/project && python scripts/verify_pipeline.py --format json > /var/log/pipeline_health_$(date +\%Y\%m\%d_\%H).json
```

### 2. Alert on Failure

```bash
#!/bin/bash
if ! python scripts/verify_pipeline.py; then
    echo "Pipeline health check failed at $(date)" | \
        mail -s "ALERT: Pipeline Unhealthy" ops@example.com
fi
```

### 3. Slack Integration

```bash
#!/bin/bash
RESULT=$(python scripts/verify_pipeline.py --format json)
STATUS=$(echo "$RESULT" | jq -r '.overall_status')

if [ "$STATUS" != "healthy" ]; then
    ISSUES=$(echo "$RESULT" | jq -r '.issues[] | "• \(.check): \(.message)"' | head -5)

    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-type: application/json' \
        -d "{
            \"text\": \"⚠️ Pipeline Health Alert\",
            \"attachments\": [{
                \"color\": \"danger\",
                \"text\": \"Status: $STATUS\n\nIssues:\n$ISSUES\"
            }]
        }"
fi
```

### 4. Prometheus Metrics Exporter

```bash
#!/bin/bash
# Export to Prometheus Node Exporter textfile collector
python scripts/verify_pipeline.py --format json | \
    jq -r '
        "# HELP pipeline_healthy Pipeline overall health (1=healthy, 0=unhealthy)",
        "# TYPE pipeline_healthy gauge",
        "pipeline_healthy " + (if .overall_status == "healthy" then "1" else "0" end),
        "",
        "# HELP pipeline_checks_total Total number of checks performed",
        "# TYPE pipeline_checks_total gauge",
        "pipeline_checks_total " + (.summary.total_checks | tostring),
        "",
        "# HELP pipeline_checks_failed Number of failed checks",
        "# TYPE pipeline_checks_failed gauge",
        "pipeline_checks_failed " + (.summary.failed | tostring)
    ' > /var/lib/node_exporter/textfile_collector/pipeline_health.prom
```

### 5. Pre-Deployment Check

```bash
#!/bin/bash
# In CI/CD pipeline before deployment
echo "Checking pipeline health before deployment..."
if python scripts/verify_pipeline.py --threshold-hours 24; then
    echo "✓ Pipeline healthy - proceeding with deployment"
    exit 0
else
    echo "✗ Pipeline unhealthy - blocking deployment"
    exit 1
fi
```

### 6. Docker Healthcheck

```dockerfile
# In docker-compose.yml
services:
  pipeline_monitor:
    image: python:3.11-slim
    healthcheck:
      test: ["CMD", "python", "/app/scripts/verify_pipeline.py"]
      interval: 5m
      timeout: 10s
      retries: 3
      start_period: 30s
```

### 7. Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pipeline-health-check
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: health-check
            image: seo-platform:latest
            command:
            - python
            - scripts/verify_pipeline.py
            - --format
            - json
          restartPolicy: OnFailure
```

### 8. GitHub Actions

```yaml
name: Pipeline Health Check
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install psycopg2-binary

      - name: Run health check
        env:
          WAREHOUSE_DSN: ${{ secrets.WAREHOUSE_DSN }}
        run: |
          python scripts/verify_pipeline.py --format json > health_report.json
          cat health_report.json

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: health-report
          path: health_report.json

      - name: Check status
        run: |
          STATUS=$(jq -r '.overall_status' health_report.json)
          if [ "$STATUS" != "healthy" ]; then
            echo "::error::Pipeline is $STATUS"
            exit 1
          fi
```

### 9. Grafana Alert Rule

```bash
# Query pipeline health metrics
pipeline_checks_failed{environment="production"} > 0

# Alert annotation
curl -X POST http://localhost:3000/api/annotations \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Pipeline health check failed",
    "tags": ["pipeline", "health"],
    "time": '$(date +%s000)'
  }'
```

### 10. Daily Summary Email

```bash
#!/bin/bash
# Run daily at 8 AM
REPORT=$(python scripts/verify_pipeline.py --format json)
STATUS=$(echo "$REPORT" | jq -r '.overall_status')

cat << EOF | mail -s "Daily Pipeline Health Report - $STATUS" team@example.com
Pipeline Health Report
Date: $(date)
Environment: production

Status: $STATUS

Summary:
$(echo "$REPORT" | jq -r '.summary | "Total Checks: \(.total_checks)\nPassed: \(.passed)\nWarned: \(.warned)\nFailed: \(.failed)"')

Check Details:
$(echo "$REPORT" | jq -r '.checks[] | "[\(.status | ascii_upcase)] \(.name): \(.message)"')

$(if echo "$REPORT" | jq -e '.issues' > /dev/null; then
    echo "Issues Requiring Attention:"
    echo "$REPORT" | jq -r '.issues[] | "• [\(.severity | ascii_upcase)] \(.check): \(.message)"'
fi)

Full report: https://dashboard.example.com/pipeline/health
EOF
```

## Quick Checks

```bash
# Check if database is reachable
python scripts/verify_pipeline.py --format json | jq '.checks[] | select(.name=="Database Connection")'

# Check watermark status
python scripts/verify_pipeline.py --format json | jq '.checks[] | select(.name=="Ingestion Watermarks")'

# Check data freshness
python scripts/verify_pipeline.py --format json | jq '.checks[] | select(.name | contains("Freshness"))'

# List all failed checks
python scripts/verify_pipeline.py --format json | jq '.checks[] | select(.status=="fail")'

# Get overall health as 0 or 1
python scripts/verify_pipeline.py --format json | jq -r 'if .overall_status == "healthy" then 1 else 0 end'
```

## Troubleshooting

```bash
# If database connection fails
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/db"
python scripts/verify_pipeline.py

# If checks are too strict
python scripts/verify_pipeline.py --threshold-hours 72 --insight-lookback 48

# Debug mode (see full details)
python scripts/verify_pipeline.py --format json | jq '.'

# Check specific environment
python scripts/verify_pipeline.py --environment staging --dsn "$STAGING_DSN"
```

## Best Practices

1. **Run Regularly**: At least hourly in production
2. **Set Appropriate Thresholds**: Based on your SLA
3. **Alert Strategically**: Don't alert on warnings, only failures
4. **Log Everything**: Keep JSON logs for historical analysis
5. **Integrate with Monitoring**: Feed metrics to your monitoring system
6. **Test Alerts**: Verify your alerting works before production

## Related Documentation

- Full documentation: `scripts/README_VERIFY_PIPELINE.md`
- Examples: `examples/verify_pipeline_example.sh`
- Tests: `tests/scripts/test_verify_pipeline.py`
