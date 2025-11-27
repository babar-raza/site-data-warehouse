# Makefile for Test Services
# Provides easy commands for managing Docker test services

.PHONY: help
help:
	@echo "Test Service Management Commands:"
	@echo ""
	@echo "Service Management:"
	@echo "  make up              Start all test services"
	@echo "  make down            Stop all test services"
	@echo "  make restart         Restart all test services"
	@echo "  make ps              Show service status"
	@echo "  make logs            Show logs from all services"
	@echo ""
	@echo "Service-Specific:"
	@echo "  make up-postgres     Start PostgreSQL only"
	@echo "  make up-redis        Start Redis only"
	@echo "  make up-ui           Start UI services (Grafana/Prometheus)"
	@echo "  make logs-postgres   Show PostgreSQL logs"
	@echo "  make logs-redis      Show Redis logs"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests with live services"
	@echo "  make test-live       Run tests requiring live services"
	@echo "  make test-ui         Run UI tests"
	@echo "  make test-e2e        Run end-to-end tests"
	@echo "  make test-services   Run Docker service tests"
	@echo ""
	@echo "Health & Validation:"
	@echo "  make health          Check service health"
	@echo "  make validate        Validate docker-compose.test.yml"
	@echo "  make ping-postgres   Test PostgreSQL connection"
	@echo "  make ping-redis      Test Redis connection"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           Stop services and remove volumes"
	@echo "  make clean-all       Remove all test data and containers"
	@echo "  make prune           Remove all unused Docker resources"

# ============================================================================
# SERVICE MANAGEMENT
# ============================================================================

.PHONY: up
up:
	@echo "Starting all test services..."
	docker-compose -f ../docker-compose.test.yml up -d
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@make health

.PHONY: down
down:
	@echo "Stopping all test services..."
	docker-compose -f ../docker-compose.test.yml down

.PHONY: restart
restart: down up

.PHONY: ps
ps:
	@echo "Test service status:"
	docker-compose -f ../docker-compose.test.yml ps

.PHONY: logs
logs:
	docker-compose -f ../docker-compose.test.yml logs -f

# ============================================================================
# SERVICE-SPECIFIC COMMANDS
# ============================================================================

.PHONY: up-postgres
up-postgres:
	@echo "Starting PostgreSQL test service..."
	docker-compose -f ../docker-compose.test.yml up -d test_warehouse

.PHONY: up-redis
up-redis:
	@echo "Starting Redis test service..."
	docker-compose -f ../docker-compose.test.yml up -d test_redis

.PHONY: up-ui
up-ui:
	@echo "Starting UI test services..."
	docker-compose -f ../docker-compose.test.yml up -d test_grafana test_prometheus

.PHONY: logs-postgres
logs-postgres:
	docker-compose -f ../docker-compose.test.yml logs -f test_warehouse

.PHONY: logs-redis
logs-redis:
	docker-compose -f ../docker-compose.test.yml logs -f test_redis

.PHONY: logs-grafana
logs-grafana:
	docker-compose -f ../docker-compose.test.yml logs -f test_grafana

.PHONY: logs-prometheus
logs-prometheus:
	docker-compose -f ../docker-compose.test.yml logs -f test_prometheus

# ============================================================================
# TESTING
# ============================================================================

.PHONY: test
test:
	@echo "Running all tests with live services..."
	pytest ../ -v

.PHONY: test-live
test-live:
	@echo "Running tests requiring live services..."
	pytest ../ -v -m live

.PHONY: test-ui
test-ui:
	@echo "Running UI tests..."
	pytest ../ -v -m ui

.PHONY: test-e2e
test-e2e:
	@echo "Running end-to-end tests..."
	pytest ../ -v -m e2e

.PHONY: test-services
test-services:
	@echo "Running Docker service tests..."
	pytest ../test_docker_services.py -v

# ============================================================================
# HEALTH & VALIDATION
# ============================================================================

.PHONY: health
health:
	@echo "Checking service health..."
	@echo ""
	@echo "PostgreSQL:"
	@docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
	@echo ""
	@echo "Redis:"
	@docker inspect test_gsc_redis --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
	@echo ""
	@echo "Grafana:"
	@docker inspect test_gsc_grafana --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"
	@echo ""
	@echo "Prometheus:"
	@docker inspect test_gsc_prometheus --format='{{.State.Health.Status}}' 2>/dev/null || echo "not running"

.PHONY: validate
validate:
	@echo "Validating docker-compose.test.yml..."
	docker-compose -f ../docker-compose.test.yml config > /dev/null
	@echo "✓ Configuration is valid"

.PHONY: ping-postgres
ping-postgres:
	@echo "Testing PostgreSQL connection..."
	@docker exec test_gsc_warehouse pg_isready -U test_user -d gsc_test

.PHONY: ping-redis
ping-redis:
	@echo "Testing Redis connection..."
	@docker exec test_gsc_redis redis-cli ping

# ============================================================================
# CLEANUP
# ============================================================================

.PHONY: clean
clean:
	@echo "Stopping services and removing volumes..."
	docker-compose -f ../docker-compose.test.yml down -v

.PHONY: clean-all
clean-all: clean
	@echo "Removing test data directories..."
	rm -rf ../test-data
	@echo "Removing test volumes..."
	docker volume rm test_gsc_pgdata 2>/dev/null || true
	docker volume rm test_gsc_redis_data 2>/dev/null || true
	docker volume rm test_gsc_grafana_data 2>/dev/null || true
	docker volume rm test_gsc_prometheus_data 2>/dev/null || true
	@echo "Removing test network..."
	docker network rm test_network 2>/dev/null || true

.PHONY: prune
prune:
	@echo "Removing all unused Docker resources..."
	@echo "WARNING: This will remove ALL unused containers, networks, and volumes!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker system prune -af --volumes; \
	fi

# ============================================================================
# DEVELOPMENT HELPERS
# ============================================================================

.PHONY: shell-postgres
shell-postgres:
	@echo "Opening PostgreSQL shell..."
	docker exec -it test_gsc_warehouse psql -U test_user -d gsc_test

.PHONY: shell-redis
shell-redis:
	@echo "Opening Redis shell..."
	docker exec -it test_gsc_redis redis-cli

.PHONY: watch-logs
watch-logs:
	@echo "Watching all service logs..."
	docker-compose -f ../docker-compose.test.yml logs -f --tail=100
