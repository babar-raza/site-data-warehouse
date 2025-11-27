#!/bin/bash
# Wrapper script for running canary checks in Docker environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${ENVIRONMENT:-production}"
VERBOSE="${VERBOSE:-false}"
OUTPUT_DIR="${OUTPUT_DIR:-/reports}"

# Help message
show_help() {
    cat << EOF
Usage: run_canary_checks.sh [OPTIONS]

Run canary checks for Site Data Warehouse

Options:
    -e, --environment ENV    Environment to check (staging|production) [default: production]
    -v, --verbose           Enable verbose logging
    -o, --output DIR        Output directory for reports [default: /reports]
    -h, --help              Show this help message

Environment Variables:
    ENVIRONMENT             Environment name (staging|production)
    WAREHOUSE_DSN           PostgreSQL connection string
    INSIGHTS_API_URL        Insights API URL
    SCHEDULER_METRICS_FILE  Path to scheduler metrics file
    VERBOSE                 Enable verbose output (true|false)
    OUTPUT_DIR              Directory for output reports

Examples:
    # Run for production
    ./scripts/run_canary_checks.sh --environment production

    # Run with verbose output
    ./scripts/run_canary_checks.sh -e staging -v

    # Run in Docker
    docker-compose run --rm canary-checks

Exit Codes:
    0    All checks passed
    1    One or more checks failed
    2    Configuration error

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 2
            ;;
    esac
done

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    echo -e "${RED}ERROR: Invalid environment '$ENVIRONMENT'. Use 'staging' or 'production'${NC}"
    exit 2
fi

# Check required environment variables
if [ -z "$WAREHOUSE_DSN" ]; then
    echo -e "${YELLOW}WARNING: WAREHOUSE_DSN not set. Using default.${NC}"
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Generate output filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/canary-report-${ENVIRONMENT}-${TIMESTAMP}.json"

# Print configuration
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Canary Checks - Site Data Warehouse${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Environment:    $ENVIRONMENT"
echo "Verbose:        $VERBOSE"
echo "Output:         $OUTPUT_FILE"
echo -e "${GREEN}========================================${NC}"
echo ""

# Build command
CMD="python scripts/canary_checks.py --environment $ENVIRONMENT --output $OUTPUT_FILE"

if [ "$VERBOSE" = true ]; then
    CMD="$CMD --verbose"
fi

# Run canary checks
echo "Running canary checks..."
if eval "$CMD"; then
    EXIT_CODE=0
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ All checks passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    EXIT_CODE=1
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ✗ Some checks failed!${NC}"
    echo -e "${RED}========================================${NC}"
fi

# Create symlink to latest report
LATEST_LINK="${OUTPUT_DIR}/canary-report-${ENVIRONMENT}-latest.json"
ln -sf "$OUTPUT_FILE" "$LATEST_LINK"
echo ""
echo "Report saved to: $OUTPUT_FILE"
echo "Latest report:   $LATEST_LINK"

# If in Docker, also save to a standard location
if [ -f "/.dockerenv" ]; then
    DOCKER_OUTPUT="/logs/canary-report-latest.json"
    cp "$OUTPUT_FILE" "$DOCKER_OUTPUT" 2>/dev/null || true
fi

# Print summary from JSON
if [ -f "$OUTPUT_FILE" ]; then
    echo ""
    echo "Summary:"

    if command -v jq &> /dev/null; then
        echo "  Status:  $(jq -r '.overall_status' "$OUTPUT_FILE")"
        echo "  Passed:  $(jq -r '.summary.passed' "$OUTPUT_FILE")"
        echo "  Failed:  $(jq -r '.summary.failed' "$OUTPUT_FILE")"
        echo "  Warned:  $(jq -r '.summary.warned' "$OUTPUT_FILE")"
        echo "  Duration: $(jq -r '.summary.duration_ms' "$OUTPUT_FILE")ms"

        # Show failed checks if any
        FAILED_COUNT=$(jq -r '.summary.failed' "$OUTPUT_FILE")
        if [ "$FAILED_COUNT" -gt 0 ]; then
            echo ""
            echo -e "${RED}Failed checks:${NC}"
            jq -r '.checks[] | select(.status == "fail") | "  - \(.name): \(.message)"' "$OUTPUT_FILE"
        fi

        # Show warned checks if any
        WARNED_COUNT=$(jq -r '.summary.warned' "$OUTPUT_FILE")
        if [ "$WARNED_COUNT" -gt 0 ]; then
            echo ""
            echo -e "${YELLOW}Warned checks:${NC}"
            jq -r '.checks[] | select(.status == "warn") | "  - \(.name): \(.message)"' "$OUTPUT_FILE"
        fi
    else
        echo "  (install jq for detailed summary)"
    fi
fi

echo ""
exit $EXIT_CODE
