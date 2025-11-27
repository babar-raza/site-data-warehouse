#!/bin/bash
# Rollback Automation Monitor - Wrapper Script
# Starts the rollback automation with proper error handling

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PID_FILE="/tmp/rollback_automation.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Parse command line arguments
ACTION="${1:-start}"
MODE="${2:-}"

show_usage() {
    echo "Usage: $0 {start|stop|status|restart|test} [dry-run]"
    echo ""
    echo "Commands:"
    echo "  start      Start rollback monitoring"
    echo "  stop       Stop rollback monitoring"
    echo "  status     Show monitoring status"
    echo "  restart    Restart monitoring"
    echo "  test       Run test suite"
    echo ""
    echo "Options:"
    echo "  dry-run    Run in dry-run mode (no actual rollbacks)"
    echo ""
    echo "Examples:"
    echo "  $0 start          # Start monitoring"
    echo "  $0 start dry-run  # Start in dry-run mode"
    echo "  $0 test           # Run tests"
    echo "  $0 status         # Check status"
}

check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found${NC}"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: docker not found${NC}"
        exit 1
    fi

    # Check required Python modules
    python3 -c "import asyncpg, httpx" 2>/dev/null || {
        echo -e "${RED}Error: Required Python modules not found${NC}"
        echo "Install with: pip install asyncpg httpx"
        exit 1
    }

    echo -e "${GREEN}✓ All dependencies available${NC}"
}

start_monitoring() {
    local dry_run=$1

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}Rollback monitoring already running (PID: $pid)${NC}"
            exit 1
        else
            # Stale PID file
            rm -f "$PID_FILE"
        fi
    fi

    check_dependencies

    echo -e "${GREEN}Starting rollback monitoring...${NC}"

    # Build command
    local cmd="python3 $PROJECT_ROOT/scripts/rollback_automation.py"
    cmd="$cmd --log-file $LOG_DIR/rollback_automation.log"

    if [ "$dry_run" = "dry-run" ]; then
        echo -e "${YELLOW}Running in DRY-RUN mode (no actual rollbacks)${NC}"
        cmd="$cmd --dry-run"
    fi

    # Start in background
    cd "$PROJECT_ROOT"
    nohup $cmd > "$LOG_DIR/rollback_automation_console.log" 2>&1 &
    local pid=$!

    # Save PID
    echo $pid > "$PID_FILE"

    # Wait a bit and check if still running
    sleep 2
    if ps -p $pid > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Rollback monitoring started (PID: $pid)${NC}"
        echo ""
        echo "Logs:"
        echo "  Main: $LOG_DIR/rollback_automation.log"
        echo "  Console: $LOG_DIR/rollback_automation_console.log"
        echo ""
        echo "Commands:"
        echo "  View logs: tail -f $LOG_DIR/rollback_automation.log"
        echo "  Stop: $0 stop"
        echo "  Status: $0 status"
    else
        echo -e "${RED}✗ Failed to start monitoring${NC}"
        echo "Check logs: cat $LOG_DIR/rollback_automation_console.log"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_monitoring() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}Rollback monitoring not running${NC}"
        exit 0
    fi

    local pid=$(cat "$PID_FILE")

    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}Rollback monitoring not running (stale PID file)${NC}"
        rm -f "$PID_FILE"
        exit 0
    fi

    echo -e "${YELLOW}Stopping rollback monitoring (PID: $pid)...${NC}"

    # Send SIGTERM for graceful shutdown
    kill -TERM "$pid" 2>/dev/null || true

    # Wait for graceful shutdown (max 10 seconds)
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${YELLOW}Force stopping...${NC}"
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo -e "${GREEN}✓ Rollback monitoring stopped${NC}"
}

show_status() {
    if [ ! -f "$PID_FILE" ]; then
        echo -e "${YELLOW}Status: Not running${NC}"
        exit 0
    fi

    local pid=$(cat "$PID_FILE")

    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}Status: Running (PID: $pid)${NC}"
        echo ""
        echo "Process Info:"
        ps -p "$pid" -o pid,ppid,user,%cpu,%mem,etime,cmd
        echo ""
        echo "Log Files:"
        if [ -f "$LOG_DIR/rollback_automation.log" ]; then
            local log_size=$(du -h "$LOG_DIR/rollback_automation.log" | cut -f1)
            local log_lines=$(wc -l < "$LOG_DIR/rollback_automation.log")
            echo "  Main log: $LOG_DIR/rollback_automation.log ($log_size, $log_lines lines)"
        fi
        echo ""
        echo "Recent Log (last 10 lines):"
        tail -10 "$LOG_DIR/rollback_automation.log" 2>/dev/null || echo "  No logs yet"
    else
        echo -e "${YELLOW}Status: Not running (stale PID file)${NC}"
        rm -f "$PID_FILE"
        exit 1
    fi
}

run_tests() {
    echo -e "${GREEN}Running rollback automation tests...${NC}"
    echo ""

    check_dependencies

    cd "$PROJECT_ROOT"
    python3 scripts/test_rollback_automation.py
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ All tests passed${NC}"
    else
        echo ""
        echo -e "${RED}✗ Tests failed${NC}"
    fi

    exit $exit_code
}

# Main logic
case "$ACTION" in
    start)
        start_monitoring "$MODE"
        ;;
    stop)
        stop_monitoring
        ;;
    status)
        show_status
        ;;
    restart)
        stop_monitoring
        sleep 2
        start_monitoring "$MODE"
        ;;
    test)
        run_tests
        ;;
    help|--help|-h)
        show_usage
        exit 0
        ;;
    *)
        echo -e "${RED}Unknown command: $ACTION${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac
