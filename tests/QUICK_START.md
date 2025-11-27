# Docker Test Services - Quick Start

Fast reference for using Docker test services in the GSC Site Data Warehouse.

## Prerequisites

```bash
# Verify Docker is installed
docker --version
docker-compose --version

# Install Python test dependencies
pip install -r requirements-test.txt
# OR at minimum:
pip install pytest psycopg2-binary redis
```

## 1. Start Services

```bash
# Option A: Using docker-compose directly
docker-compose -f docker-compose.test.yml up -d

# Option B: Using Makefile
make -C tests up

# Verify services are healthy
docker-compose -f docker-compose.test.yml ps
```

## 2. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run tests requiring live services
pytest tests/ -v -m live

# Run UI tests (Grafana/Prometheus)
pytest tests/ -v -m ui

# Run specific test file
pytest tests/test_docker_services.py -v

# Run with coverage
pytest tests/ -v --cov=./ --cov-report=html
```

## 3. Verify Setup

```bash
# Quick verification (no service startup)
python tests/verify_test_setup.py

# Full verification (includes service startup)
python tests/verify_test_setup.py --full
```

## 4. Cleanup

```bash
# Stop services (keep volumes)
docker-compose -f docker-compose.test.yml down

# Stop services and remove volumes
docker-compose -f docker-compose.test.yml down -v

# Using Makefile
make -C tests clean
```

## Common Commands

### Service Management

```bash
# Start specific service
docker-compose -f docker-compose.test.yml up -d test_warehouse

# View logs
docker-compose -f docker-compose.test.yml logs -f

# View logs for specific service
docker-compose -f docker-compose.test.yml logs -f test_warehouse

# Restart services
docker-compose -f docker-compose.test.yml restart
```

### Health Checks

```bash
# Check all service health
make -C tests health

# Check PostgreSQL
docker exec test_gsc_warehouse pg_isready -U test_user -d gsc_test

# Check Redis
docker exec test_gsc_redis redis-cli ping

# Check Grafana
curl http://localhost:3001/api/health
```

### Database Access

```bash
# PostgreSQL shell
docker exec -it test_gsc_warehouse psql -U test_user -d gsc_test

# Run SQL query
docker exec test_gsc_warehouse psql -U test_user -d gsc_test -c "SELECT version()"

# Redis shell
docker exec -it test_gsc_redis redis-cli

# Redis commands
docker exec test_gsc_redis redis-cli KEYS '*'
```

## Test Service Ports

All test services use non-standard ports to avoid conflicts:

| Service    | Test Port | Production Port |
|------------|-----------|-----------------|
| PostgreSQL | 5433      | 5432            |
| Redis      | 6380      | 6379            |
| Grafana    | 3001      | 3000            |
| Prometheus | 9091      | 9090            |

## Example Test

```python
import pytest

@pytest.mark.live
def test_database(postgres_connection):
    """Test PostgreSQL connection."""
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1 AS result")
    result = cursor.fetchone()[0]
    cursor.close()
    assert result == 1

@pytest.mark.live
def test_cache(redis_client):
    """Test Redis caching."""
    redis_client.set("test_key", "test_value", ex=60)
    value = redis_client.get("test_key")
    assert value.decode() == "test_value"
```

## Configuration

Environment variables can be set in `.env.test` or directly:

```bash
# PostgreSQL
export TEST_POSTGRES_PORT=5433
export TEST_POSTGRES_DB=gsc_test
export TEST_POSTGRES_USER=test_user
export TEST_POSTGRES_PASSWORD=test_pass

# Redis
export TEST_REDIS_PORT=6380

# Grafana
export TEST_GRAFANA_PORT=3001

# Prometheus
export TEST_PROMETHEUS_PORT=9091
```

## Troubleshooting

### Services Won't Start

```bash
# Check for port conflicts
netstat -an | grep -E "5433|6380"

# View service logs
docker-compose -f docker-compose.test.yml logs test_warehouse

# Check Docker resources
docker stats
```

### Connection Refused

```bash
# Verify services are running
docker-compose -f docker-compose.test.yml ps

# Check health status
docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}'

# Wait longer for services to start
sleep 30
```

### Clean Start

```bash
# Complete cleanup
docker-compose -f docker-compose.test.yml down -v
rm -rf test-data/
docker volume prune -f

# Start fresh
docker-compose -f docker-compose.test.yml up -d
```

## Makefile Targets

All available Make targets:

```bash
make -C tests help          # Show all commands
make -C tests up            # Start services
make -C tests down          # Stop services
make -C tests restart       # Restart services
make -C tests ps            # Show status
make -C tests logs          # Show logs
make -C tests health        # Check health
make -C tests test          # Run all tests
make -C tests test-live     # Run live tests
make -C tests test-ui       # Run UI tests
make -C tests clean         # Stop and remove volumes
make -C tests clean-all     # Complete cleanup
```

## More Information

- **Detailed Guide**: [docs/testing/DOCKER_TESTING.md](../docs/testing/DOCKER_TESTING.md)
- **Fixture Documentation**: [fixtures/README.md](fixtures/README.md)
- **Example Tests**: [test_docker_services.py](test_docker_services.py)
- **Docker Compose Config**: [../docker-compose.test.yml](../docker-compose.test.yml)
