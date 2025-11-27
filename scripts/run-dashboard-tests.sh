#!/bin/bash
#
# Run Playwright Dashboard Tests
#
# This script runs E2E tests for all 11 Grafana dashboards using Playwright.
# Tests verify dashboards load correctly, have no errors, and display data.
#
# Usage:
#   ./scripts/run-dashboard-tests.sh                    # Run all tests (headless)
#   ./scripts/run-dashboard-tests.sh --headed           # Run with visible browser
#   ./scripts/run-dashboard-tests.sh --browser firefox  # Use Firefox
#   ./scripts/run-dashboard-tests.sh --fast             # Skip slow tests
#   ./scripts/run-dashboard-tests.sh --report           # Generate HTML report
#
# Environment Variables:
#   GRAFANA_URL       - Grafana URL (default: http://localhost:3000)
#   GRAFANA_USER      - Grafana username (default: admin)
#   GRAFANA_PASSWORD  - Grafana password (default: admin)
#   HEADLESS          - Run headless (default: true)
#   BROWSER_TYPE      - Browser: chromium, firefox, webkit (default: chromium)
#   RECORD_VIDEO      - Record test videos (default: false)
#   TRACE_ENABLED     - Enable Playwright traces (default: false)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
HEADLESS="true"
BROWSER_TYPE="chromium"
RECORD_VIDEO="false"
TRACE_ENABLED="false"
GENERATE_REPORT="false"
FAST_MODE="false"
VERBOSE="-v"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --headed)
            HEADLESS="false"
            shift
            ;;
        --browser)
            BROWSER_TYPE="$2"
            shift 2
            ;;
        --record)
            RECORD_VIDEO="true"
            shift
            ;;
        --trace)
            TRACE_ENABLED="true"
            shift
            ;;
        --report)
            GENERATE_REPORT="true"
            shift
            ;;
        --fast)
            FAST_MODE="true"
            shift
            ;;
        --quiet)
            VERBOSE=""
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --headed           Run with visible browser window"
            echo "  --browser TYPE     Browser to use: chromium, firefox, webkit"
            echo "  --record           Record test videos"
            echo "  --trace            Enable Playwright tracing"
            echo "  --report           Generate HTML test report"
            echo "  --fast             Skip slow tests"
            echo "  --quiet            Reduce output verbosity"
            echo "  --help             Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  GRAFANA_URL        Grafana URL (default: http://localhost:3000)"
            echo "  GRAFANA_USER       Grafana username (default: admin)"
            echo "  GRAFANA_PASSWORD   Grafana password (default: admin)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Export environment variables
export HEADLESS
export BROWSER_TYPE
export RECORD_VIDEO
export TRACE_ENABLED

# Create test output directories
mkdir -p "$PROJECT_ROOT/test-results/screenshots"
mkdir -p "$PROJECT_ROOT/test-results/videos"
mkdir -p "$PROJECT_ROOT/test-results/traces"
mkdir -p "$PROJECT_ROOT/test-results/reports"

echo "=============================================="
echo "Playwright Dashboard Tests"
echo "=============================================="
echo "Browser:     $BROWSER_TYPE"
echo "Headless:    $HEADLESS"
echo "Record:      $RECORD_VIDEO"
echo "Trace:       $TRACE_ENABLED"
echo "Grafana URL: ${GRAFANA_URL:-http://localhost:3000}"
echo "=============================================="

# Check if Playwright is installed
if ! python -c "import playwright" 2>/dev/null; then
    echo ""
    echo "Installing Playwright..."
    pip install playwright pytest-playwright
    playwright install "$BROWSER_TYPE"
fi

# Build pytest command
PYTEST_CMD="python -m pytest tests/e2e/test_dashboard_e2e.py $VERBOSE --no-cov"

if [ "$FAST_MODE" = "true" ]; then
    PYTEST_CMD="$PYTEST_CMD -m 'not slow'"
fi

if [ "$GENERATE_REPORT" = "true" ]; then
    PYTEST_CMD="$PYTEST_CMD --html=test-results/reports/dashboard_report.html --self-contained-html"
fi

# Run tests
cd "$PROJECT_ROOT"
echo ""
echo "Running: $PYTEST_CMD"
echo ""

eval "$PYTEST_CMD"
TEST_EXIT_CODE=$?

# Print summary
echo ""
echo "=============================================="
echo "Test Results Summary"
echo "=============================================="

if [ -d "test-results/screenshots" ]; then
    SCREENSHOT_COUNT=$(find test-results/screenshots -name "*.png" 2>/dev/null | wc -l)
    if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
        echo "Screenshots:  $SCREENSHOT_COUNT (test-results/screenshots/)"
    fi
fi

if [ -d "test-results/videos" ] && [ "$RECORD_VIDEO" = "true" ]; then
    VIDEO_COUNT=$(find test-results/videos -name "*.webm" 2>/dev/null | wc -l)
    if [ "$VIDEO_COUNT" -gt 0 ]; then
        echo "Videos:       $VIDEO_COUNT (test-results/videos/)"
    fi
fi

if [ -f "test-results/reports/dashboard_report.html" ]; then
    echo "HTML Report:  test-results/reports/dashboard_report.html"
fi

echo "=============================================="

exit $TEST_EXIT_CODE
