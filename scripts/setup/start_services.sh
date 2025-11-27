#!/bin/bash
# ============================================================================
# Start All Services Script
# ============================================================================
# This script starts all required services for the SEO Intelligence Platform

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SEO Intelligence Platform${NC}"
echo -e "${GREEN}Starting All Services${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Function to print success
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print info
print_info() {
    echo -e "${YELLOW}➜${NC} $1"
}

# Check if services are already running
check_running() {
    SERVICE=$1
    if pgrep -f "$SERVICE" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# 1. Start Docker services (PostgreSQL, Redis, Grafana)
echo "Starting Docker services..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d postgres redis grafana
    sleep 3
    print_success "Docker services started"
else
    print_error "docker-compose not found. Please install Docker Compose."
fi
echo ""

# 2. Check PostgreSQL
echo "Checking PostgreSQL..."
if psql "${WAREHOUSE_DSN}" -c "SELECT 1" > /dev/null 2>&1; then
    print_success "PostgreSQL is ready"
else
    print_error "PostgreSQL is not responding"
    echo "Please check your database connection"
    exit 1
fi
echo ""

# 3. Check Redis
echo "Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is ready"
else
    print_error "Redis is not responding"
    exit 1
fi
echo ""

# 4. Start Celery Worker
echo "Starting Celery Worker..."
if check_running "celery worker"; then
    print_info "Celery worker already running"
else
    CONCURRENCY=${CELERY_WORKER_CONCURRENCY:-4}
    nohup celery -A services.tasks worker \
        --loglevel=info \
        --concurrency=$CONCURRENCY \
        --logfile=logs/celery-worker.log \
        --pidfile=logs/celery-worker.pid \
        > /dev/null 2>&1 &
    sleep 2
    if check_running "celery worker"; then
        print_success "Celery worker started (concurrency: $CONCURRENCY)"
    else
        print_error "Failed to start Celery worker"
    fi
fi
echo ""

# 5. Start Celery Beat
echo "Starting Celery Beat..."
if check_running "celery beat"; then
    print_info "Celery beat already running"
else
    nohup celery -A services.tasks beat \
        --loglevel=info \
        --logfile=logs/celery-beat.log \
        --pidfile=logs/celery-beat.pid \
        > /dev/null 2>&1 &
    sleep 2
    if check_running "celery beat"; then
        print_success "Celery beat started"
    else
        print_error "Failed to start Celery beat"
    fi
fi
echo ""

# 6. Start Ollama (if enabled)
if [ "${OLLAMA_ENABLED:-true}" = "true" ]; then
    echo "Starting Ollama..."
    if check_running "ollama serve"; then
        print_info "Ollama already running"
    else
        if command -v ollama &> /dev/null; then
            nohup ollama serve > logs/ollama.log 2>&1 &
            sleep 3
            if check_running "ollama serve"; then
                print_success "Ollama started"
            else
                print_error "Failed to start Ollama"
            fi
        else
            print_error "Ollama not installed. Install from: https://ollama.ai"
        fi
    fi
    echo ""
fi

# 7. Check Grafana
echo "Checking Grafana..."
GRAFANA_PORT=${GRAFANA_PORT:-3000}
if curl -s http://localhost:$GRAFANA_PORT > /dev/null; then
    print_success "Grafana is running on port $GRAFANA_PORT"
else
    print_info "Grafana may still be starting..."
fi
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Service Status${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check all services
POSTGRES_STATUS=$(psql "${WAREHOUSE_DSN}" -c "SELECT 1" > /dev/null 2>&1 && echo "✓ Running" || echo "✗ Not running")
REDIS_STATUS=$(redis-cli ping > /dev/null 2>&1 && echo "✓ Running" || echo "✗ Not running")
CELERY_WORKER_STATUS=$(check_running "celery worker" && echo "✓ Running" || echo "✗ Not running")
CELERY_BEAT_STATUS=$(check_running "celery beat" && echo "✓ Running" || echo "✗ Not running")
OLLAMA_STATUS=$(check_running "ollama serve" && echo "✓ Running" || echo "✗ Not running")
GRAFANA_STATUS=$(curl -s http://localhost:$GRAFANA_PORT > /dev/null && echo "✓ Running" || echo "✗ Not running")

echo "PostgreSQL:    $POSTGRES_STATUS"
echo "Redis:         $REDIS_STATUS"
echo "Celery Worker: $CELERY_WORKER_STATUS"
echo "Celery Beat:   $CELERY_BEAT_STATUS"
echo "Ollama:        $OLLAMA_STATUS"
echo "Grafana:       $GRAFANA_STATUS"
echo ""

echo -e "${GREEN}Access Points:${NC}"
echo "  Grafana:     http://localhost:$GRAFANA_PORT"
echo "  API:         http://localhost:${API_PORT:-8000}"
echo ""

echo -e "${GREEN}Logs:${NC}"
echo "  Celery Worker: logs/celery-worker.log"
echo "  Celery Beat:   logs/celery-beat.log"
echo "  Ollama:        logs/ollama.log"
echo ""

echo -e "${GREEN}Management Commands:${NC}"
echo "  Stop services: ./scripts/setup/stop_services.sh"
echo "  View logs:     tail -f logs/celery-worker.log"
echo "  Health check:  python scripts/setup/health_check.py"
echo ""

print_success "All services started!"
