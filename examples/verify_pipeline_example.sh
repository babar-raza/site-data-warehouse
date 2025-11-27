#!/bin/bash
#
# Pipeline Verification Examples
#
# This script demonstrates various ways to use verify_pipeline.py
# for monitoring and alerting in production environments.
#

# Set up environment
export WAREHOUSE_DSN="${WAREHOUSE_DSN:-postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db}"
export ENVIRONMENT="${ENVIRONMENT:-production}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VERIFY_SCRIPT="$PROJECT_ROOT/scripts/verify_pipeline.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=================================================="
echo "Pipeline Verification Examples"
echo "=================================================="
echo ""

# Example 1: Basic health check
echo "Example 1: Basic Health Check"
echo "------------------------------"
python "$VERIFY_SCRIPT"
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Pipeline is healthy${NC}"
else
    echo -e "${RED}✗ Pipeline has issues (exit code: $EXIT_CODE)${NC}"
fi
echo ""

# Example 2: JSON output
echo "Example 2: JSON Output"
echo "----------------------"
python "$VERIFY_SCRIPT" --format json | jq '.summary'
echo ""

# Example 3: Custom thresholds
echo "Example 3: Custom Thresholds (48 hour staleness)"
echo "-------------------------------------------------"
python "$VERIFY_SCRIPT" --threshold-hours 48 --insight-lookback 48
echo ""

# Example 4: Extract specific metrics
echo "Example 4: Extract Specific Metrics"
echo "------------------------------------"
REPORT=$(python "$VERIFY_SCRIPT" --format json)

TOTAL_CHECKS=$(echo "$REPORT" | jq -r '.summary.total_checks')
PASSED=$(echo "$REPORT" | jq -r '.summary.passed')
FAILED=$(echo "$REPORT" | jq -r '.summary.failed')
STATUS=$(echo "$REPORT" | jq -r '.overall_status')

echo "Total Checks: $TOTAL_CHECKS"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Status: $STATUS"
echo ""

# Example 5: Check for specific issues
echo "Example 5: Check for Specific Issues"
echo "-------------------------------------"
ISSUES=$(echo "$REPORT" | jq -r '.issues[]? | "\(.check): \(.message)"')
if [ -z "$ISSUES" ]; then
    echo -e "${GREEN}No issues detected${NC}"
else
    echo -e "${YELLOW}Issues found:${NC}"
    echo "$ISSUES"
fi
echo ""

# Example 6: Conditional alerting
echo "Example 6: Conditional Alerting"
echo "--------------------------------"
if python "$VERIFY_SCRIPT" --format json | jq -e '.summary.failed > 0' > /dev/null; then
    echo -e "${RED}ALERT: Pipeline has failed checks!${NC}"
    echo "Failed checks:"
    python "$VERIFY_SCRIPT" --format json | jq -r '.checks[] | select(.status=="fail") | "  - \(.name): \(.message)"'

    # Here you would send alerts (email, Slack, PagerDuty, etc.)
    # Example: echo "Pipeline failure" | mail -s "Alert" admin@example.com
else
    echo -e "${GREEN}All checks passed - no alerts needed${NC}"
fi
echo ""

# Example 7: Log to file with timestamp
echo "Example 7: Logging to File"
echo "--------------------------"
LOG_DIR="${LOG_DIR:-/tmp/pipeline_logs}"
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/pipeline_verification_${TIMESTAMP}.json"

python "$VERIFY_SCRIPT" --format json > "$LOG_FILE"
echo "Report saved to: $LOG_FILE"
echo ""

# Example 8: Generate metrics for Prometheus
echo "Example 8: Prometheus Metrics"
echo "------------------------------"
METRICS=$(python "$VERIFY_SCRIPT" --format json)

echo "# HELP pipeline_checks_total Total number of pipeline checks"
echo "# TYPE pipeline_checks_total gauge"
echo "pipeline_checks_total{environment=\"$ENVIRONMENT\"} $(echo "$METRICS" | jq '.summary.total_checks')"

echo "# HELP pipeline_checks_passed Number of passed pipeline checks"
echo "# TYPE pipeline_checks_passed gauge"
echo "pipeline_checks_passed{environment=\"$ENVIRONMENT\"} $(echo "$METRICS" | jq '.summary.passed')"

echo "# HELP pipeline_checks_failed Number of failed pipeline checks"
echo "# TYPE pipeline_checks_failed gauge"
echo "pipeline_checks_failed{environment=\"$ENVIRONMENT\"} $(echo "$METRICS" | jq '.summary.failed')"

echo "# HELP pipeline_healthy Pipeline health status (1=healthy, 0=unhealthy)"
echo "# TYPE pipeline_healthy gauge"
HEALTHY=$([ "$(echo "$METRICS" | jq -r '.overall_status')" == "healthy" ] && echo 1 || echo 0)
echo "pipeline_healthy{environment=\"$ENVIRONMENT\"} $HEALTHY"
echo ""

# Example 9: Daily summary report
echo "Example 9: Daily Summary Report"
echo "--------------------------------"
cat << EOF
Pipeline Health Summary - $(date +"%Y-%m-%d %H:%M:%S")

Environment: $ENVIRONMENT
Status: $STATUS
Checks: $TOTAL_CHECKS total ($PASSED passed, $FAILED failed)

$(python "$VERIFY_SCRIPT" --format json | jq -r '.checks[] | "[\(.status | ascii_upcase)] \(.name): \(.message)"')

EOF

# Example 10: Integration with monitoring systems
echo "Example 10: Monitoring Integration Examples"
echo "--------------------------------------------"
echo ""
echo "# Grafana Alert (using Loki)"
echo "curl -X POST http://localhost:3100/loki/api/v1/push \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"streams\":[{\"stream\":{\"job\":\"pipeline_verification\"},\"values\":[[\"$(date +%s)000000000\",\"$(python "$VERIFY_SCRIPT" --format json | jq -c .)\"]]]}'"
echo ""

echo "# DataDog (using API)"
echo "curl -X POST \"https://api.datadoghq.com/api/v1/series\" \\"
echo "  -H \"DD-API-KEY: \${DD_API_KEY}\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d @- << 'DATADOG_PAYLOAD'"
python "$VERIFY_SCRIPT" --format json | jq '{
  series: [
    {
      metric: "pipeline.health.status",
      type: "gauge",
      points: [[now, (if .overall_status == "healthy" then 1 else 0 end)]],
      tags: ["environment:" + .environment]
    },
    {
      metric: "pipeline.health.checks.total",
      type: "gauge",
      points: [[now, .summary.total_checks]],
      tags: ["environment:" + .environment]
    },
    {
      metric: "pipeline.health.checks.failed",
      type: "gauge",
      points: [[now, .summary.failed]],
      tags: ["environment:" + .environment]
    }
  ]
}'
echo "DATADOG_PAYLOAD"
echo ""

echo "# Slack Webhook"
echo "curl -X POST \$SLACK_WEBHOOK_URL \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"text\":\"Pipeline Status: $STATUS\",\"attachments\":[{\"color\":\"$([ "$STATUS" == "healthy" ] && echo "good" || echo "danger")\",\"fields\":[{\"title\":\"Checks\",\"value\":\"$PASSED/$TOTAL_CHECKS passed\",\"short\":true},{\"title\":\"Environment\",\"value\":\"$ENVIRONMENT\",\"short\":true}]}]}'"
echo ""

echo "=================================================="
echo "Examples completed!"
echo "=================================================="
