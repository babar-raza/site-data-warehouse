#!/bin/bash
# Example usage of canary checks script
# Demonstrates various ways to run canary checks

set -e

echo "=================================================="
echo "  Canary Checks Usage Examples"
echo "=================================================="
echo ""

# Example 1: Basic production check
echo "Example 1: Basic production check"
echo "-----------------------------------"
echo "Command: python scripts/canary_checks.py --environment production"
echo ""
# Uncomment to run:
# python scripts/canary_checks.py --environment production
echo ""

# Example 2: Staging with verbose output
echo "Example 2: Staging with verbose output"
echo "---------------------------------------"
echo "Command: python scripts/canary_checks.py --environment staging --verbose"
echo ""
# Uncomment to run:
# python scripts/canary_checks.py --environment staging --verbose
echo ""

# Example 3: Save report to file
echo "Example 3: Save report to file"
echo "-------------------------------"
echo "Command: python scripts/canary_checks.py --environment production --output /tmp/report.json"
echo ""
# Uncomment to run:
# python scripts/canary_checks.py --environment production --output /tmp/report.json
echo ""

# Example 4: Using wrapper script
echo "Example 4: Using wrapper script"
echo "--------------------------------"
echo "Command: ./scripts/run_canary_checks.sh --environment production --verbose"
echo ""
# Uncomment to run:
# ./scripts/run_canary_checks.sh --environment production --verbose
echo ""

# Example 5: Run in Docker
echo "Example 5: Run in Docker"
echo "------------------------"
echo "Command: docker-compose -f compose/docker-compose.canary.yml run --rm canary-checks"
echo ""
# Uncomment to run:
# docker-compose -f compose/docker-compose.canary.yml run --rm canary-checks
echo ""

# Example 6: Parse JSON output in script
echo "Example 6: Parse JSON output with jq"
echo "-------------------------------------"
cat << 'EOF'
python scripts/canary_checks.py --environment production --output report.json

if [ -f report.json ]; then
    STATUS=$(jq -r '.overall_status' report.json)
    PASSED=$(jq -r '.summary.passed' report.json)
    FAILED=$(jq -r '.summary.failed' report.json)

    echo "Status: $STATUS"
    echo "Passed: $PASSED"
    echo "Failed: $FAILED"

    if [ "$STATUS" != "pass" ]; then
        echo "Failed checks:"
        jq -r '.checks[] | select(.status == "fail") | "  - \(.name): \(.message)"' report.json
        exit 1
    fi
fi
EOF
echo ""

# Example 7: Custom environment variables
echo "Example 7: Custom environment variables"
echo "----------------------------------------"
cat << 'EOF'
export WAREHOUSE_DSN="postgresql://user:pass@localhost:5432/warehouse"
export INSIGHTS_API_URL="http://localhost:8001"
export SCHEDULER_METRICS_FILE="/custom/path/metrics.json"

python scripts/canary_checks.py --environment production
EOF
echo ""

# Example 8: CI/CD integration
echo "Example 8: CI/CD integration (GitHub Actions)"
echo "----------------------------------------------"
cat << 'EOF'
# In .github/workflows/canary.yml
- name: Run canary checks
  run: |
    python scripts/canary_checks.py \
      --environment production \
      --output canary-report.json

- name: Check results
  if: always()
  run: |
    STATUS=$(jq -r '.overall_status' canary-report.json)
    if [ "$STATUS" != "pass" ]; then
      echo "::error::Canary checks failed"
      exit 1
    fi
EOF
echo ""

# Example 9: Scheduled checks with cron
echo "Example 9: Scheduled checks with cron"
echo "--------------------------------------"
cat << 'EOF'
# Add to crontab:
# Run every 6 hours
0 */6 * * * cd /path/to/repo && python scripts/canary_checks.py --environment production --output /var/log/canary/report-$(date +\%Y\%m\%d-\%H\%M).json

# Or use the wrapper:
0 */6 * * * /path/to/repo/scripts/run_canary_checks.sh -e production -o /var/log/canary
EOF
echo ""

# Example 10: Alert on failure
echo "Example 10: Alert on failure (with Slack)"
echo "------------------------------------------"
cat << 'EOF'
#!/bin/bash
python scripts/canary_checks.py --environment production --output report.json

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    # Send Slack alert
    FAILED_CHECKS=$(jq -r '.checks[] | select(.status == "fail") | .name' report.json | tr '\n' ', ')

    curl -X POST $SLACK_WEBHOOK_URL \
      -H 'Content-Type: application/json' \
      -d "{
        \"text\": \"🚨 Canary checks failed!\",
        \"blocks\": [
          {
            \"type\": \"section\",
            \"text\": {
              \"type\": \"mrkdwn\",
              \"text\": \"*Environment:* production\n*Failed checks:* $FAILED_CHECKS\"
            }
          }
        ]
      }"
fi

exit $EXIT_CODE
EOF
echo ""

echo "=================================================="
echo "  For more information, see:"
echo "  - scripts/README_CANARY_CHECKS.md"
echo "  - scripts/canary_checks.py --help"
echo "=================================================="
