# Test Fixtures

Docker service fixtures and test utilities for the GSC Site Data Warehouse.

## Overview

This package provides pytest fixtures for managing test infrastructure:

- **Docker Services**: PostgreSQL 15 with pgvector, Redis 7, Grafana, Prometheus
- **Database Connections**: Connection pooling, transaction management, cleanup
- **Test Data**: Schema setup, data isolation, automatic cleanup
- **Service Monitoring**: Health checks, port management, service status

## Quick Start

### 1. Start Test Services

```bash
# Start all test services
docker-compose -f docker-compose.test.yml up -d

# Check service health
docker-compose -f docker-compose.test.yml ps
```

### 2. Run Tests

```bash
# Run all tests with live services
pytest tests/ -v -m live

# Run specific test file
pytest tests/test_docker_services.py -v

# Run UI tests (requires Grafana/Prometheus)
pytest tests/ -v -m ui
```

### 3. Cleanup

```bash
# Stop and remove all test services
docker-compose -f docker-compose.test.yml down -v
```

## Available Fixtures

### Service Management

#### `docker_services` (session scope)
Starts all Docker test services and ensures they're healthy.

```python
@pytest.mark.live
def test_something(docker_services):
    postgres_info = docker_services["postgres"]
    redis_info = docker_services["redis"]
```

#### `ui_services` (session scope)
Starts UI services (Grafana, Prometheus) for E2E tests.

```python
@pytest.mark.ui
def test_dashboard(ui_services):
    grafana_url = ui_services["grafana"]["url"]
```

### Individual Containers

#### `postgres_container` (session scope)
PostgreSQL 15 container with pgvector extension.

```python
@pytest.mark.live
def test_postgres(postgres_container):
    dsn = postgres_container["dsn"]
    port = postgres_container["port"]
```

#### `redis_container` (session scope)
Redis 7 container.

```python
@pytest.mark.live
def test_redis(redis_container):
    url = redis_container["url"]
    port = redis_container["port"]
```

#### `grafana_container` (session scope)
Grafana container for E2E UI tests.

```python
@pytest.mark.ui
def test_grafana(grafana_container):
    url = grafana_container["url"]
```

#### `prometheus_container` (session scope)
Prometheus container for E2E UI tests.

```python
@pytest.mark.ui
def test_prometheus(prometheus_container):
    url = prometheus_container["url"]
```

### Database Connections

#### `postgres_connection` (function scope)
PostgreSQL connection with autocommit enabled. Automatically closed after test.

```python
@pytest.mark.live
def test_query(postgres_connection):
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    cursor.close()
```

#### `postgres_cursor` (function scope)
PostgreSQL cursor. Automatically closed after test.

```python
@pytest.mark.live
def test_query(postgres_cursor):
    postgres_cursor.execute("SELECT 1")
    result = postgres_cursor.fetchone()
```

#### `redis_client` (function scope)
Redis client. Flushes database before and after each test.

```python
@pytest.mark.live
def test_cache(redis_client):
    redis_client.set("key", "value")
    assert redis_client.get("key") == b"value"
```

### Database Setup/Teardown

#### `clean_database` (function scope)
Truncates all tables before test for fresh database state.

```python
@pytest.mark.live
def test_fresh_data(postgres_connection, clean_database):
    # Database is empty at start of test
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM gsc.dim_property")
    count = cursor.fetchone()[0]
    assert count == 0
```

#### `test_schema` (function scope)
Ensures test schema exists with required extensions.

```python
@pytest.mark.live
def test_schema(postgres_connection, test_schema):
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1 FROM gsc.dim_property LIMIT 0")
    # Schema exists if query doesn't raise error
```

### Configuration

#### `test_db_dsn` (session scope)
Test database DSN string.

```python
@pytest.mark.live
def test_config(test_db_dsn):
    assert "test_user" in test_db_dsn
    assert "5433" in test_db_dsn
```

#### `test_redis_url` (session scope)
Test Redis URL string.

```python
@pytest.mark.live
def test_config(test_redis_url):
    assert "6380" in test_redis_url
```

#### `test_grafana_url` (session scope)
Test Grafana URL for E2E UI tests.

```python
@pytest.mark.ui
def test_config(test_grafana_url):
    assert test_grafana_url == "http://localhost:3001"
```

#### `test_prometheus_url` (session scope)
Test Prometheus URL for E2E UI tests.

```python
@pytest.mark.ui
def test_config(test_prometheus_url):
    assert test_prometheus_url == "http://localhost:9091"
```

### Service Info

#### `service_ports` (function scope)
Dictionary of all test service ports.

```python
@pytest.mark.live
def test_ports(service_ports):
    assert service_ports["postgres"] == 5433
    assert service_ports["redis"] == 6380
```

#### `service_health_status` (function scope)
Health status of all running test services.

```python
@pytest.mark.live
def test_health(service_health_status):
    assert service_health_status["warehouse"] is True
    assert service_health_status["redis"] is True
```

## Configuration

### Environment Variables

Test services can be configured via environment variables:

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
export TEST_GRAFANA_USER=admin
export TEST_GRAFANA_PASSWORD=admin

# Prometheus
export TEST_PROMETHEUS_PORT=9091
```

### Default Ports

All test services use non-standard ports to avoid conflicts:

| Service    | Production Port | Test Port |
|------------|----------------|-----------|
| PostgreSQL | 5432           | 5433      |
| Redis      | 6379           | 6380      |
| Grafana    | 3000           | 3001      |
| Prometheus | 9090           | 9091      |

## Test Markers

### `@pytest.mark.live`
Marks tests that require live Docker services (PostgreSQL, Redis).

```python
@pytest.mark.live
def test_database(postgres_connection):
    # Test requires PostgreSQL
    pass
```

Run with: `pytest -m live`

### `@pytest.mark.ui`
Marks tests that require browser/UI services (Grafana, Prometheus).

```python
@pytest.mark.ui
def test_dashboard(grafana_container):
    # Test requires Grafana UI
    pass
```

Run with: `pytest -m ui`

### `@pytest.mark.e2e`
Marks end-to-end workflow tests.

```python
@pytest.mark.e2e
def test_full_workflow(docker_services):
    # Full integration test
    pass
```

Run with: `pytest -m e2e`

## Docker Compose Structure

### Services

- **test_warehouse**: PostgreSQL 15 with pgvector extension
- **test_redis**: Redis 7 with persistence
- **test_grafana**: Grafana for dashboard testing
- **test_prometheus**: Prometheus for metrics testing
- **test_metrics_exporter**: Custom metrics exporter
- **test_postgres_exporter**: PostgreSQL metrics
- **test_redis_exporter**: Redis metrics

### Networks

All services run on isolated `test_network` (172.26.0.0/16).

### Volumes

- **test_pgdata**: PostgreSQL data (persistent)
- **test_redis_data**: Redis data (persistent)
- **test_grafana_data**: Grafana data (persistent)
- **test_prometheus_data**: Prometheus data (persistent)

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Start test services
        run: docker-compose -f docker-compose.test.yml up -d

      - name: Wait for services
        run: sleep 30

      - name: Run tests
        run: pytest tests/ -v -m live

      - name: Stop test services
        run: docker-compose -f docker-compose.test.yml down -v
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker info

# Check for port conflicts
docker-compose -f docker-compose.test.yml ps
netstat -an | grep -E "5433|6380|3001|9091"

# Check logs
docker-compose -f docker-compose.test.yml logs test_warehouse
docker-compose -f docker-compose.test.yml logs test_redis
```

### Health Checks Failing

```bash
# Check service health
docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}'
docker inspect test_gsc_redis --format='{{.State.Health.Status}}'

# View detailed logs
docker logs test_gsc_warehouse
docker logs test_gsc_redis
```

### Connection Issues

```bash
# Test PostgreSQL connection
psql postgresql://test_user:test_pass@localhost:5433/gsc_test -c "SELECT 1"

# Test Redis connection
redis-cli -p 6380 ping

# Check network connectivity
docker network inspect test_network
```

### Cleanup Issues

```bash
# Force remove all test containers
docker-compose -f docker-compose.test.yml down -v --remove-orphans

# Remove test volumes
docker volume rm test_gsc_pgdata test_gsc_redis_data

# Remove test network
docker network rm test_network

# Prune unused Docker resources
docker system prune -af --volumes
```

## Best Practices

### 1. Use Appropriate Fixtures

- Use `postgres_connection` for database queries
- Use `clean_database` when you need fresh state
- Use `test_schema` to ensure schema exists

### 2. Mark Tests Properly

```python
@pytest.mark.live  # For PostgreSQL/Redis tests
@pytest.mark.ui    # For Grafana/Prometheus tests
@pytest.mark.e2e   # For full workflow tests
@pytest.mark.slow  # For long-running tests
```

### 3. Cleanup After Tests

Fixtures handle cleanup automatically, but ensure:
- No long-running transactions
- No unclosed connections
- No orphaned test data

### 4. Isolate Test Data

Use unique identifiers for test data:

```python
import uuid

def test_something(postgres_connection):
    test_id = str(uuid.uuid4())
    cursor = postgres_connection.cursor()
    cursor.execute(
        "INSERT INTO gsc.test_table (id, data) VALUES (%s, %s)",
        (test_id, "test data")
    )
```

### 5. Use Transactions (when needed)

```python
def test_rollback(postgres_connection):
    postgres_connection.autocommit = False
    cursor = postgres_connection.cursor()

    try:
        cursor.execute("INSERT INTO ...")
        # Do something that might fail
        postgres_connection.commit()
    except Exception:
        postgres_connection.rollback()
        raise
```

## Examples

See `tests/test_docker_services.py` for complete examples of:
- Service availability tests
- Connection tests
- pgvector extension tests
- Redis functionality tests
- Schema setup tests
- Data persistence tests
- Health check tests

## Related Documentation

- [docker-compose.test.yml](../../docker-compose.test.yml) - Test service configuration
- [pytest.ini](../../pytest.ini) - Pytest configuration
- [conftest.py](../conftest.py) - Shared test configuration
- [TESTING.md](../../docs/testing/TESTING.md) - Testing guide
