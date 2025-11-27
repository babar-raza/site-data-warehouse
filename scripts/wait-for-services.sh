#!/bin/bash

# ============================================================================
# Service Wait Script - Unix/Linux/macOS
# ============================================================================
# Wait for all critical services to be healthy before proceeding
#
# Usage:
#   ./wait-for-services.sh [--timeout SECONDS] [--verbose]
#
# Options:
#   --timeout SECONDS   Maximum time to wait (default: 120)
#   --verbose          Show detailed status information
#   --help             Display this help message
#
# Exit Codes:
#   0 - All services healthy
#   1 - Timeout reached or service check failed
#
# Services Monitored:
#   - PostgreSQL (port 5432)
#   - Redis (port 6379, optional)
#   - Insights API (port 8000)
#   - Grafana (port 3000)
#   - Prometheus (port 9090)
# ============================================================================

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default timeout in seconds
TIMEOUT=120

# Verbose output flag
VERBOSE=false

# Service configuration
POSTGRES_HOST="${DB_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-gsc_user}"
POSTGRES_DB="${POSTGRES_DB:-gsc_db}"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

API_HOST="${API_HOST:-localhost}"
API_PORT="${API_PORT:-8000}"

GRAFANA_HOST="${GRAFANA_HOST:-localhost}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"

PROMETHEUS_HOST="${PROMETHEUS_HOST:-localhost}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# Print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "\033[0;36m[INFO]\033[0m $message"
            ;;
        "SUCCESS")
            echo -e "\033[0;32m[SUCCESS]\033[0m $message"
            ;;
        "WAITING")
            echo -e "\033[0;33m[WAITING]\033[0m $message"
            ;;
        "ERROR")
            echo -e "\033[0;31m[ERROR]\033[0m $message"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# Print verbose message
verbose() {
    if [ "$VERBOSE" = true ]; then
        print_status "INFO" "$1"
    fi
}

# Display help message
show_help() {
    cat << EOF
Service Wait Script - Unix/Linux/macOS

Wait for all critical services to be healthy before proceeding.

Usage:
    $0 [OPTIONS]

Options:
    --timeout SECONDS   Maximum time to wait in seconds (default: 120)
    --verbose          Show detailed status information
    --help             Display this help message

Environment Variables:
    DB_HOST            PostgreSQL host (default: localhost)
    POSTGRES_PORT      PostgreSQL port (default: 5432)
    POSTGRES_USER      PostgreSQL user (default: gsc_user)
    POSTGRES_DB        PostgreSQL database (default: gsc_db)
    REDIS_HOST         Redis host (default: localhost)
    REDIS_PORT         Redis port (default: 6379)
    API_HOST           API host (default: localhost)
    API_PORT           API port (default: 8000)
    GRAFANA_HOST       Grafana host (default: localhost)
    GRAFANA_PORT       Grafana port (default: 3000)
    PROMETHEUS_HOST    Prometheus host (default: localhost)
    PROMETHEUS_PORT    Prometheus port (default: 9090)

Exit Codes:
    0                  All services healthy
    1                  Timeout reached or service check failed

Examples:
    # Wait with default timeout (120s)
    $0

    # Wait with custom timeout
    $0 --timeout 60

    # Wait with verbose output
    $0 --verbose --timeout 180

EOF
}

# ============================================================================
# SERVICE CHECK FUNCTIONS
# ============================================================================

# Check if port is open
check_port() {
    local host=$1
    local port=$2

    # Try using nc (netcat) first
    if command -v nc >/dev/null 2>&1; then
        nc -z -w1 "$host" "$port" >/dev/null 2>&1
        return $?
    fi

    # Fallback to bash TCP check
    timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null
    return $?
}

# Check PostgreSQL health
check_postgres() {
    verbose "Checking PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."

    # First check if port is open
    if ! check_port "$POSTGRES_HOST" "$POSTGRES_PORT"; then
        verbose "PostgreSQL port not reachable"
        return 1
    fi

    # Try to connect using psql if available
    if command -v psql >/dev/null 2>&1; then
        PGPASSWORD="${POSTGRES_PASSWORD:-gsc_pass}" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" \
            -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" >/dev/null 2>&1
        return $?
    fi

    # If psql not available, port check is sufficient
    return 0
}

# Check Redis health (optional)
check_redis() {
    verbose "Checking Redis at $REDIS_HOST:$REDIS_PORT..."

    # Check if port is open
    if ! check_port "$REDIS_HOST" "$REDIS_PORT"; then
        verbose "Redis port not reachable (optional service)"
        return 0  # Redis is optional, don't fail
    fi

    # Try to ping Redis if redis-cli is available
    if command -v redis-cli >/dev/null 2>&1; then
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1
        local result=$?
        if [ $result -eq 0 ]; then
            return 0
        else
            verbose "Redis ping failed (optional service)"
            return 0  # Redis is optional
        fi
    fi

    return 0
}

# Check API health
check_api() {
    verbose "Checking Insights API at $API_HOST:$API_PORT..."

    # Check if port is open
    if ! check_port "$API_HOST" "$API_PORT"; then
        verbose "API port not reachable"
        return 1
    fi

    # Try health endpoint using curl
    if command -v curl >/dev/null 2>&1; then
        local response=$(curl -s -f -m 5 "http://$API_HOST:$API_PORT/health" 2>/dev/null)
        if [ $? -eq 0 ]; then
            verbose "API health check passed"
            return 0
        else
            verbose "API health endpoint not responding"
            return 1
        fi
    fi

    # Fallback to wget
    if command -v wget >/dev/null 2>&1; then
        wget -q -O- -T5 "http://$API_HOST:$API_PORT/health" >/dev/null 2>&1
        return $?
    fi

    # If neither curl nor wget, port check is sufficient
    return 0
}

# Check Grafana health
check_grafana() {
    verbose "Checking Grafana at $GRAFANA_HOST:$GRAFANA_PORT..."

    # Check if port is open
    if ! check_port "$GRAFANA_HOST" "$GRAFANA_PORT"; then
        verbose "Grafana port not reachable"
        return 1
    fi

    # Try API endpoint using curl
    if command -v curl >/dev/null 2>&1; then
        local response=$(curl -s -f -m 5 "http://$GRAFANA_HOST:$GRAFANA_PORT/api/health" 2>/dev/null)
        if [ $? -eq 0 ]; then
            verbose "Grafana health check passed"
            return 0
        fi
    fi

    # Fallback to checking root endpoint
    if command -v curl >/dev/null 2>&1; then
        curl -s -f -m 5 "http://$GRAFANA_HOST:$GRAFANA_PORT/" >/dev/null 2>&1
        return $?
    fi

    # If curl not available, port check is sufficient
    return 0
}

# Check Prometheus health
check_prometheus() {
    verbose "Checking Prometheus at $PROMETHEUS_HOST:$PROMETHEUS_PORT..."

    # Check if port is open
    if ! check_port "$PROMETHEUS_HOST" "$PROMETHEUS_PORT"; then
        verbose "Prometheus port not reachable"
        return 1
    fi

    # Try health endpoint using curl
    if command -v curl >/dev/null 2>&1; then
        local response=$(curl -s -f -m 5 "http://$PROMETHEUS_HOST:$PROMETHEUS_PORT/-/healthy" 2>/dev/null)
        if [ $? -eq 0 ]; then
            verbose "Prometheus health check passed"
            return 0
        fi
    fi

    # Fallback to checking root endpoint
    if command -v curl >/dev/null 2>&1; then
        curl -s -f -m 5 "http://$PROMETHEUS_HOST:$PROMETHEUS_PORT/" >/dev/null 2>&1
        return $?
    fi

    # If curl not available, port check is sufficient
    return 0
}

# Check all services
check_all_services() {
    local all_healthy=true

    # PostgreSQL (required)
    if check_postgres; then
        verbose "PostgreSQL: HEALTHY"
    else
        print_status "WAITING" "PostgreSQL not ready"
        all_healthy=false
    fi

    # Redis (optional)
    check_redis

    # API (required)
    if check_api; then
        verbose "Insights API: HEALTHY"
    else
        print_status "WAITING" "Insights API not ready"
        all_healthy=false
    fi

    # Grafana (required)
    if check_grafana; then
        verbose "Grafana: HEALTHY"
    else
        print_status "WAITING" "Grafana not ready"
        all_healthy=false
    fi

    # Prometheus (required)
    if check_prometheus; then
        verbose "Prometheus: HEALTHY"
    else
        print_status "WAITING" "Prometheus not ready"
        all_healthy=false
    fi

    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# MAIN LOGIC
# ============================================================================

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate timeout
if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]]; then
    print_status "ERROR" "Invalid timeout value: $TIMEOUT"
    exit 1
fi

# Display startup message
print_status "INFO" "Waiting for services to be healthy (timeout: ${TIMEOUT}s)..."
echo ""

# Wait for services with timeout
START_TIME=$(date +%s)
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    if check_all_services; then
        echo ""
        print_status "SUCCESS" "All services are healthy!"
        echo ""

        # Display service status
        echo "Service Status:"
        echo "  PostgreSQL  : http://$POSTGRES_HOST:$POSTGRES_PORT"
        echo "  Insights API: http://$API_HOST:$API_PORT"
        echo "  Grafana     : http://$GRAFANA_HOST:$GRAFANA_PORT"
        echo "  Prometheus  : http://$PROMETHEUS_HOST:$PROMETHEUS_PORT"
        if check_port "$REDIS_HOST" "$REDIS_PORT"; then
            echo "  Redis       : $REDIS_HOST:$REDIS_PORT"
        fi
        echo ""

        exit 0
    fi

    # Wait before next check
    sleep 2

    # Update elapsed time
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    # Show progress every 10 seconds
    if [ $((ELAPSED % 10)) -eq 0 ] && [ $ELAPSED -gt 0 ]; then
        print_status "INFO" "Still waiting... (${ELAPSED}s elapsed, $((TIMEOUT - ELAPSED))s remaining)"
    fi
done

# Timeout reached
echo ""
print_status "ERROR" "Timeout reached after ${TIMEOUT}s"
echo ""
echo "Service status:"

# Final status check
if check_port "$POSTGRES_HOST" "$POSTGRES_PORT"; then
    echo "  PostgreSQL  : REACHABLE"
else
    echo "  PostgreSQL  : NOT REACHABLE"
fi

if check_port "$API_HOST" "$API_PORT"; then
    echo "  Insights API: REACHABLE"
else
    echo "  Insights API: NOT REACHABLE"
fi

if check_port "$GRAFANA_HOST" "$GRAFANA_PORT"; then
    echo "  Grafana     : REACHABLE"
else
    echo "  Grafana     : NOT REACHABLE"
fi

if check_port "$PROMETHEUS_HOST" "$PROMETHEUS_PORT"; then
    echo "  Prometheus  : REACHABLE"
else
    echo "  Prometheus  : NOT REACHABLE"
fi

echo ""
echo "Troubleshooting:"
echo "  1. Check if services are running: docker-compose ps"
echo "  2. Check service logs: docker-compose logs [service-name]"
echo "  3. Verify environment variables are set correctly"
echo "  4. Ensure ports are not blocked by firewall"
echo ""

exit 1
