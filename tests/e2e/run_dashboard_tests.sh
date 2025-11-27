#!/bin/bash
# Dashboard E2E Test Runner
# Usage: ./run_dashboard_tests.sh [options]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
GRAFANA_URL=${GRAFANA_URL:-http://localhost:3000}
GRAFANA_USER=${GRAFANA_USER:-admin}
GRAFANA_PASSWORD=${GRAFANA_PASSWORD:-admin}
HEADLESS=${HEADLESS:-true}
BROWSER_TYPE=${BROWSER_TYPE:-chromium}

# Parse command line arguments
VERBOSE=false
HEADED=false
SPECIFIC_TEST=""
BROWSER=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--headed)
            HEADED=true
            HEADLESS=false
            shift
            ;;
        -b|--browser)
            BROWSER="$2"
            shift 2
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --help)
            echo "Dashboard E2E Test Runner"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose       Verbose output"
            echo "  -h, --headed        Run with visible browser"
            echo "  -b, --browser TYPE  Browser type (chromium, firefox, webkit)"
            echo "  -t, --test NAME     Run specific test"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all tests"
            echo "  $0 -v                                 # Run with verbose output"
            echo "  $0 -h                                 # Run with visible browser"
            echo "  $0 -b firefox                         # Run with Firefox"
            echo "  $0 -t test_ga4_dashboard_loads        # Run specific test"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set browser if specified
if [ -n "$BROWSER" ]; then
    BROWSER_TYPE="$BROWSER"
fi

# Export environment variables
export GRAFANA_URL
export GRAFANA_USER
export GRAFANA_PASSWORD
export HEADLESS
export BROWSER_TYPE

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dashboard E2E Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check if playwright is installed
if ! python -c "import playwright" 2>/dev/null; then
    echo -e "${RED}❌ Playwright not installed${NC}"
    echo -e "${YELLOW}Installing Playwright...${NC}"
    pip install playwright
    playwright install "$BROWSER_TYPE"
fi

# Check if Grafana is running
echo -e "${YELLOW}Checking Grafana connection...${NC}"
if ! curl -f -s "$GRAFANA_URL/api/health" > /dev/null; then
    echo -e "${RED}❌ Cannot connect to Grafana at $GRAFANA_URL${NC}"
    echo -e "${YELLOW}Please ensure Grafana is running:${NC}"
    echo -e "  docker-compose up -d grafana"
    exit 1
fi
echo -e "${GREEN}✓ Grafana is running${NC}"

# Check if browser is installed
echo -e "${YELLOW}Checking browser installation...${NC}"
if ! playwright install "$BROWSER_TYPE" --dry-run 2>/dev/null; then
    echo -e "${YELLOW}Installing $BROWSER_TYPE browser...${NC}"
    playwright install "$BROWSER_TYPE"
fi
echo -e "${GREEN}✓ Browser $BROWSER_TYPE is installed${NC}"

echo ""
echo -e "${BLUE}Test Configuration:${NC}"
echo -e "  Grafana URL: $GRAFANA_URL"
echo -e "  Browser: $BROWSER_TYPE"
echo -e "  Headless: $HEADLESS"
if [ -n "$SPECIFIC_TEST" ]; then
    echo -e "  Specific Test: $SPECIFIC_TEST"
fi
echo ""

# Construct pytest command
PYTEST_CMD="pytest tests/e2e/test_dashboard_e2e.py"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v -s"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add markers
PYTEST_CMD="$PYTEST_CMD -m 'e2e and ui'"

# Add specific test if provided
if [ -n "$SPECIFIC_TEST" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $SPECIFIC_TEST"
fi

# Add color output
PYTEST_CMD="$PYTEST_CMD --color=yes"

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo -e "${BLUE}Command: $PYTEST_CMD${NC}"
echo ""

if eval "$PYTEST_CMD"; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    exit 0
else
    EXIT_CODE=$?
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ Some tests failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Check test output above for details${NC}"
    echo -e "${YELLOW}Screenshots saved to: test-results/screenshots/${NC}"
    exit $EXIT_CODE
fi
