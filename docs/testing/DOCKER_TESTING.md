# Docker Test Services Guide

Complete guide for using Docker-based test services in the GSC Site Data Warehouse.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Usage](#usage)
- [Available Fixtures](#available-fixtures)
- [Writing Tests](#writing-tests)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Overview

The test infrastructure provides isolated Docker services for integration testing:

- **PostgreSQL 15** with pgvector extension for vector similarity search
- **Redis 7** for caching and task queue testing
- **Grafana** for E2E dashboard UI testing
- **Prometheus** for metrics and monitoring testing

All services run on isolated ports and networks to prevent conflicts with production.

## Quick Start

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
docker --version  # Should be 20.10+
docker-compose --version  # Should be 1.29+

# Install Python test dependencies
pip install -r requirements-test.txt
```

### 2. Start Test Services

```bash
# Start all services
docker-compose -f docker-compose.test.yml up -d

# Check service health
docker-compose -f docker-compose.test.yml ps

# View logs
docker-compose -f docker-compose.test.yml logs -f
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run tests requiring live services
pytest tests/ -v -m live

# Run UI tests
pytest tests/ -v -m ui

# Run specific test file
pytest tests/test_docker_services.py -v
```

### 4. Cleanup

```bash
# Stop and remove services
docker-compose -f docker-compose.test.yml down -v
```

## Architecture

### Service Isolation

All test services are isolated from production:

| Service    | Production      | Test                |
|------------|-----------------|---------------------|
| PostgreSQL | localhost:5432  | localhost:5433      |
| Redis      | localhost:6379  | localhost:6380      |
| Grafana    | localhost:3000  | localhost:3001      |
| Prometheus | localhost:9090  | localhost:9091      |

### Network Architecture

```
┌─────────────────────────────────────────┐
│         test_network (172.26.0.0/16)    │
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │  PostgreSQL  │  │    Redis     │   │
│  │     15       │  │      7       │   │
│  │  (pgvector)  │  │   (cache)    │   │
│  └──────────────┘  └──────────────┘   │
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │   Grafana    │  │  Prometheus  │   │
│  │  (UI tests)  │  │  (metrics)   │   │
│  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────┘
         │                    │
         │                    │
         ▼                    ▼
    Host Ports          Test Fixtures
    (5433, 6380)       (pytest fixtures)
```

### Container Naming

All test containers are prefixed with `test_` to avoid conflicts:

- `test_gsc_warehouse` - PostgreSQL
- `test_gsc_redis` - Redis
- `test_gsc_grafana` - Grafana
- `test_gsc_prometheus` - Prometheus

### Volume Management

Test data is stored in named volumes:

- `test_gsc_pgdata` - PostgreSQL data
- `test_gsc_redis_data` - Redis data
- `test_gsc_grafana_data` - Grafana configuration
- `test_gsc_prometheus_data` - Prometheus metrics

## Configuration

### Environment Variables

Create a `.env.test` file or set environment variables:

```bash
# PostgreSQL
TEST_POSTGRES_DB=gsc_test
TEST_POSTGRES_USER=test_user
TEST_POSTGRES_PASSWORD=test_pass
TEST_POSTGRES_PORT=5433

# Redis
TEST_REDIS_PORT=6380

# Grafana
TEST_GRAFANA_PORT=3001
TEST_GRAFANA_USER=admin
TEST_GRAFANA_PASSWORD=admin

# Prometheus
TEST_PROMETHEUS_PORT=9091
```

### Docker Compose

The `docker-compose.test.yml` file defines all test services. Key features:

- **Health checks**: All services have health checks configured
- **Resource limits**: Memory and CPU limits prevent resource exhaustion
- **Logging**: JSON logging with rotation (5MB max, 2 files)
- **Restart policy**: Services restart unless stopped explicitly
- **Init scripts**: PostgreSQL runs initialization SQL on startup

### Pytest Configuration

Test markers are defined in `conftest.py`:

```python
# pytest.ini or conftest.py
markers:
    live: Tests requiring live Docker services
    ui: Tests requiring UI services (Grafana/Prometheus)
    e2e: End-to-end integration tests
    slow: Long-running tests
```

## Usage

### Using Makefile (Recommended)

```bash
# Start services
make -C tests up

# Check health
make -C tests health

# Run tests
make -C tests test-live

# View logs
make -C tests logs

# Cleanup
make -C tests clean
```

### Manual Commands

```bash
# Start specific service
docker-compose -f docker-compose.test.yml up -d test_warehouse

# Check service health
docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}'

# View service logs
docker-compose -f docker-compose.test.yml logs test_warehouse

# Execute commands in container
docker exec test_gsc_warehouse psql -U test_user -d gsc_test -c "SELECT 1"

# Stop specific service
docker-compose -f docker-compose.test.yml stop test_warehouse
```

## Available Fixtures

### Session-Scoped Fixtures

These fixtures are created once per test session:

```python
@pytest.fixture(scope="session")
def docker_services():
    """Start all Docker services"""
    # Starts: PostgreSQL, Redis
    # Waits for health checks
    # Yields service info
    # Cleanup on session end

@pytest.fixture(scope="session")
def ui_services():
    """Start UI services"""
    # Starts: Grafana, Prometheus
    # Requires docker_services
    # Yields service info

@pytest.fixture(scope="session")
def postgres_container():
    """PostgreSQL container info"""
    # Returns: {dsn, port, container}

@pytest.fixture(scope="session")
def redis_container():
    """Redis container info"""
    # Returns: {url, port, container}
```

### Function-Scoped Fixtures

These fixtures are created for each test:

```python
@pytest.fixture
def postgres_connection():
    """PostgreSQL connection with autocommit"""
    # Creates connection
    # Yields connection
    # Auto-closes after test

@pytest.fixture
def postgres_cursor():
    """PostgreSQL cursor"""
    # Creates cursor
    # Yields cursor
    # Auto-closes after test

@pytest.fixture
def redis_client():
    """Redis client with auto-flush"""
    # Creates client
    # Flushes DB before test
    # Yields client
    # Flushes DB after test
    # Auto-closes client

@pytest.fixture
def clean_database():
    """Truncate all tables"""
    # Truncates all tables before test
    # Yields
    # Optional cleanup after test
```

## Writing Tests

### Basic Test Structure

```python
import pytest

@pytest.mark.live
def test_database_query(postgres_connection):
    """Test PostgreSQL query execution."""
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1 AS result")
    result = cursor.fetchone()[0]
    cursor.close()

    assert result == 1
```

### Testing with Clean Database

```python
@pytest.mark.live
def test_insert_data(postgres_connection, clean_database):
    """Test data insertion with clean state."""
    cursor = postgres_connection.cursor()

    # Database is empty at start
    cursor.execute("SELECT COUNT(*) FROM gsc.dim_property")
    assert cursor.fetchone()[0] == 0

    # Insert test data
    cursor.execute("""
        INSERT INTO gsc.dim_property (property_url, property_type)
        VALUES (%s, %s)
    """, ("https://example.com", "URL_PREFIX"))

    # Verify insertion
    cursor.execute("SELECT COUNT(*) FROM gsc.dim_property")
    assert cursor.fetchone()[0] == 1

    cursor.close()
```

### Testing Redis

```python
@pytest.mark.live
def test_redis_caching(redis_client):
    """Test Redis caching operations."""
    # Set value
    redis_client.set("test_key", "test_value", ex=60)

    # Get value
    value = redis_client.get("test_key")
    assert value.decode() == "test_value"

    # Check TTL
    ttl = redis_client.ttl("test_key")
    assert 0 < ttl <= 60

    # Delete key
    redis_client.delete("test_key")
    assert redis_client.get("test_key") is None
```

### Testing pgvector Extension

```python
@pytest.mark.live
def test_pgvector_functionality(postgres_connection):
    """Test vector similarity operations."""
    cursor = postgres_connection.cursor()

    # Create test table with vector column
    cursor.execute("""
        CREATE TEMP TABLE test_vectors (
            id SERIAL PRIMARY KEY,
            embedding vector(3)
        )
    """)

    # Insert vectors
    cursor.execute("""
        INSERT INTO test_vectors (embedding) VALUES
        ('[1,2,3]'::vector),
        ('[4,5,6]'::vector),
        ('[1,2,4]'::vector)
    """)

    # Find similar vectors (cosine distance)
    cursor.execute("""
        SELECT id, embedding <=> '[1,2,3]'::vector AS distance
        FROM test_vectors
        ORDER BY distance
        LIMIT 3
    """)

    results = cursor.fetchall()
    assert len(results) == 3
    assert results[0][1] == 0.0  # Exact match

    cursor.close()
```

### UI Testing with Grafana

```python
@pytest.mark.ui
def test_grafana_api(test_grafana_url):
    """Test Grafana API availability."""
    import requests

    # Test health endpoint
    response = requests.get(f"{test_grafana_url}/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"

    # Test datasources endpoint
    response = requests.get(
        f"{test_grafana_url}/api/datasources",
        auth=("admin", "admin")
    )
    assert response.status_code == 200
```

### E2E Testing

```python
@pytest.mark.e2e
def test_full_workflow(postgres_connection, redis_client):
    """Test complete data workflow."""
    cursor = postgres_connection.cursor()

    # 1. Insert data
    cursor.execute("""
        INSERT INTO gsc.dim_property (property_url, property_type)
        VALUES (%s, %s)
        RETURNING property_id
    """, ("https://example.com", "URL_PREFIX"))
    property_id = cursor.fetchone()[0]

    # 2. Cache property_id
    redis_client.set(f"property:{property_id}", "cached")

    # 3. Verify cache
    cached = redis_client.get(f"property:{property_id}")
    assert cached.decode() == "cached"

    # 4. Query database
    cursor.execute("""
        SELECT property_url FROM gsc.dim_property
        WHERE property_id = %s
    """, (property_id,))
    url = cursor.fetchone()[0]

    assert url == "https://example.com"

    cursor.close()
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Integration Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Start test services
        run: docker-compose -f docker-compose.test.yml up -d

      - name: Wait for services
        run: |
          sleep 30
          docker-compose -f docker-compose.test.yml ps

      - name: Check service health
        run: |
          docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}'
          docker inspect test_gsc_redis --format='{{.State.Health.Status}}'

      - name: Run tests
        run: pytest tests/ -v -m live --cov=./ --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

      - name: Stop services
        if: always()
        run: docker-compose -f docker-compose.test.yml down -v
```

### GitLab CI

```yaml
test:
  image: python:3.10
  services:
    - docker:dind
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
  before_script:
    - pip install -r requirements.txt
    - pip install -r requirements-test.txt
    - docker-compose -f docker-compose.test.yml up -d
    - sleep 30
  script:
    - pytest tests/ -v -m live
  after_script:
    - docker-compose -f docker-compose.test.yml down -v
```

## Troubleshooting

### Services Won't Start

**Problem**: Services fail to start or become unhealthy.

**Solutions**:

```bash
# Check Docker daemon
docker info

# Check for port conflicts
netstat -an | grep -E "5433|6380|3001|9091"

# View service logs
docker-compose -f docker-compose.test.yml logs test_warehouse

# Check disk space
df -h

# Check Docker resources
docker stats
```

### Connection Refused

**Problem**: Tests can't connect to services.

**Solutions**:

```bash
# Verify services are running
docker-compose -f docker-compose.test.yml ps

# Check health status
docker inspect test_gsc_warehouse --format='{{.State.Health.Status}}'

# Test connection manually
psql postgresql://test_user:test_pass@localhost:5433/gsc_test -c "SELECT 1"
redis-cli -p 6380 ping

# Check network connectivity
docker network inspect test_network
```

### Health Checks Failing

**Problem**: Services start but health checks fail.

**Solutions**:

```bash
# View detailed logs
docker logs test_gsc_warehouse

# Check health check command
docker inspect test_gsc_warehouse --format='{{.State.Health}}'

# Manually run health check
docker exec test_gsc_warehouse pg_isready -U test_user -d gsc_test

# Increase health check timeout in docker-compose.test.yml
healthcheck:
  timeout: 10s  # Increase from 5s
  start_period: 30s  # Increase from 20s
```

### pgvector Extension Missing

**Problem**: Tests fail with "type 'vector' does not exist".

**Solutions**:

```bash
# Verify image
docker-compose -f docker-compose.test.yml config | grep image

# Should be: pgvector/pgvector:pg15

# Recreate container
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d test_warehouse

# Verify extension in database
docker exec test_gsc_warehouse psql -U test_user -d gsc_test \
  -c "SELECT * FROM pg_extension WHERE extname='vector'"
```

### Volume Permissions

**Problem**: Permission denied when accessing volumes.

**Solutions**:

```bash
# Fix permissions (Linux/Mac)
sudo chown -R $USER:$USER test-data/

# On Windows with WSL2
# Ensure volumes are in WSL2 filesystem, not Windows filesystem

# Alternative: Use named volumes instead of bind mounts
# Edit docker-compose.test.yml volumes section
```

### Tests Hang or Timeout

**Problem**: Tests hang or timeout waiting for services.

**Solutions**:

```python
# Increase timeout in fixtures
def wait_for_postgres(dsn: str, timeout: int = 120):  # Increase from 60
    # ...

# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run tests with verbose output
pytest tests/ -v -s --log-cli-level=DEBUG
```

### Cleanup Issues

**Problem**: Resources not cleaned up after tests.

**Solutions**:

```bash
# Force cleanup
docker-compose -f docker-compose.test.yml down -v --remove-orphans

# Remove dangling volumes
docker volume prune -f

# Remove test network
docker network rm test_network

# Nuclear option: Clean all Docker resources
docker system prune -af --volumes
```

## Best Practices

### 1. Always Use Fixtures

```python
# ❌ Bad: Manual connection management
def test_query():
    conn = psycopg2.connect(TEST_DB_DSN)
    # ...
    conn.close()

# ✅ Good: Use fixtures
def test_query(postgres_connection):
    # Connection auto-managed
```

### 2. Mark Tests Appropriately

```python
# ✅ Good: Clear markers
@pytest.mark.live
@pytest.mark.slow
def test_bulk_insert(postgres_connection):
    # ...
```

### 3. Isolate Test Data

```python
# ❌ Bad: Hardcoded IDs
def test_query(postgres_connection):
    cursor.execute("INSERT INTO ... VALUES (1, 'data')")

# ✅ Good: Unique IDs
def test_query(postgres_connection):
    import uuid
    test_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO ... VALUES (%s, 'data')", (test_id,))
```

### 4. Clean Up After Tests

```python
# ✅ Good: Use clean_database fixture
@pytest.mark.live
def test_with_clean_state(postgres_connection, clean_database):
    # Database is clean at start
    # ...
```

### 5. Use Transactions for Rollback

```python
# ✅ Good: Transaction isolation
def test_rollback(postgres_connection):
    postgres_connection.autocommit = False
    try:
        # Test operations
        postgres_connection.commit()
    except:
        postgres_connection.rollback()
        raise
```

## Performance Tips

### 1. Use Session-Scoped Fixtures

```python
# Fixtures with scope="session" are created once
# Use for expensive setup operations
```

### 2. Minimize Database Operations

```python
# ❌ Slow: Many small queries
for i in range(1000):
    cursor.execute("INSERT INTO ...")

# ✅ Fast: Batch insert
cursor.executemany("INSERT INTO ...", data_rows)
```

### 3. Use Redis for Test Data Caching

```python
@pytest.fixture(scope="session")
def test_data(redis_client):
    """Cache expensive test data in Redis."""
    data = redis_client.get("test_data")
    if not data:
        data = generate_expensive_test_data()
        redis_client.set("test_data", data, ex=3600)
    return data
```

### 4. Parallel Test Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest tests/ -n auto
```

## Related Documentation

- [docker-compose.test.yml](../../docker-compose.test.yml) - Service configuration
- [tests/fixtures/docker_services.py](../../tests/fixtures/docker_services.py) - Fixture implementation
- [tests/fixtures/README.md](../../tests/fixtures/README.md) - Fixture documentation
- [pytest.ini](../../pytest.ini) - Pytest configuration
- [.env.test](../../.env.test) - Test environment variables
