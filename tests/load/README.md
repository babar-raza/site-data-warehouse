# Load Testing Suite

Comprehensive load tests for the GSC Warehouse system to validate performance under concurrent load.

## Overview

The load testing suite tests the system's ability to handle:
- **50 concurrent API requests** to various endpoints
- **100 concurrent database queries** through connection pool
- **Mixed workloads** combining API and database operations
- **Sustained throughput** over time

## Test Suite

### API Load Tests

| Test | Description | Concurrency | Success Criteria |
|------|-------------|-------------|------------------|
| `test_api_concurrent_requests_50` | Test various API endpoints with 50 concurrent requests | 50 | ≥90% success rate |
| `test_api_concurrent_health_checks` | Test health endpoint under high concurrency | 50 | ≥90% success rate |

### Database Load Tests

| Test | Description | Concurrency | Success Criteria |
|------|-------------|-------------|------------------|
| `test_database_concurrent_queries_100` | Test DB with 100 concurrent SELECT queries | 100 | 100% success rate |
| `test_database_connection_pool_stress` | Stress test connection pool beyond max size | 150 | 100% success rate |
| `test_database_write_operations_concurrent` | Test 100 concurrent INSERT operations | 100 | 100% success, all data verified |

### Mixed & Throughput Tests

| Test | Description | Load Pattern | Success Criteria |
|------|-------------|--------------|------------------|
| `test_mixed_load_api_and_database` | Combined API + DB operations | 25 API + 75 DB | ≥90% success rate |
| `test_sustained_load_throughput` | Sustained load over 10 seconds | 20 queries/sec | ≥90% success, ≥80% target throughput |

### Configuration Tests

| Test | Description | Purpose |
|------|-------------|---------|
| `test_load_test_summary` | Verify test suite configuration | Ensure all constants and markers are correct |

## Requirements

### System Requirements
- **PostgreSQL database** (running and accessible)
- **FastAPI Insights API** (optional, for API tests)
- **Python 3.11+** with asyncio support
- **Required packages**: `asyncpg`, `httpx`, `pytest`, `pytest-asyncio`

### Environment Variables
```bash
# Database connection (required for DB tests)
TEST_DB_DSN=postgresql://test_user:test_pass@localhost:5432/gsc_test

# API endpoint (optional, defaults to localhost:8001)
TEST_API_URL=http://localhost:8001
```

## Running Tests

### Run All Load Tests
```bash
pytest tests/load/test_system_load.py -v -m "e2e and slow"
```

### Run with Detailed Output
```bash
pytest tests/load/test_system_load.py -v -m "e2e and slow" --log-cli-level=INFO
```

### Run Specific Test
```bash
pytest tests/load/test_system_load.py::test_api_concurrent_requests_50 -v
```

### Run Only Database Tests
```bash
pytest tests/load/test_system_load.py -v -k "database"
```

### Run Only API Tests
```bash
pytest tests/load/test_system_load.py -v -k "api"
```

## Test Configuration

Key configuration constants (defined in test file):

```python
TEST_CONCURRENT_API_REQUESTS = 50    # API concurrent requests
TEST_CONCURRENT_DB_QUERIES = 100     # DB concurrent queries
TEST_MIN_SUCCESS_RATE = 0.90         # 90% minimum success rate
TEST_API_TIMEOUT = 30.0              # API request timeout in seconds
```

## Test Markers

All tests are marked with:
- `@pytest.mark.e2e` - End-to-end integration tests
- `@pytest.mark.slow` - Long-running tests
- `@pytest.mark.asyncio` - Asynchronous test functions

## Fixtures

### `db_pool`
- **Scope**: module
- **Purpose**: Creates asyncpg connection pool (20-100 connections)
- **Cleanup**: Automatically closes pool after all tests

### `api_base_url`
- **Scope**: module
- **Purpose**: Provides API base URL from environment or default
- **Default**: `http://localhost:8001`

### `load_test_metrics`
- **Scope**: function
- **Purpose**: Fresh metrics tracker for each test
- **Metrics**: Response times, success/failure counts, throughput

## Performance Metrics

Each test reports:
- **Total operations** executed
- **Success count** and **failure count**
- **Success rate** (%)
- **Duration** (seconds)
- **Throughput** (operations/second)
- **Response time statistics**:
  - Average
  - Min/Max
  - P50 (median)
  - P95
  - P99 (when sufficient samples)
- **Error samples** (first 5 errors)

## Example Output

```
======================================================================
API Concurrent Requests Load Test Results
======================================================================
Total Requests: 50
Successful: 48
Failed: 2
Success Rate: 96.00%
Duration: 2.45s
Throughput: 19.59 req/s
Response Times:
  - Average: 0.125s
  - Min: 0.089s
  - Max: 0.234s
  - P50: 0.118s
  - P95: 0.189s
======================================================================
```

## Success Criteria

### API Tests
- **50 concurrent requests** must complete
- **≥90% success rate** required
- All requests complete within timeout (30s)

### Database Tests
- **100 concurrent queries** must complete
- **100% success rate** required (all queries must succeed)
- Connection pool must handle concurrent requests properly
- Data integrity verified for write operations

### Mixed Tests
- **100 total operations** (25 API + 75 DB)
- **≥90% success rate** overall

### Throughput Tests
- Maintain load for **≥10 seconds**
- **≥90% success rate** throughout
- **≥80% of target throughput** achieved

## Troubleshooting

### Database Connection Failures
```bash
# Check database is running
psql -h localhost -U test_user -d gsc_test

# Verify TEST_DB_DSN environment variable
echo $TEST_DB_DSN
```

### API Connection Failures
```bash
# Check API is running (Insights API on port 8000)
curl http://localhost:8000/api/health

# Or set alternative API URL
export TEST_API_URL=http://your-api-server:8000
```

### Performance Issues
- Ensure database has proper indexes
- Check connection pool limits (max_connections in PostgreSQL)
- Monitor system resources (CPU, memory, network)
- Review slow query logs

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Load Tests
  run: |
    export TEST_DB_DSN=postgresql://test_user:test_pass@localhost:5432/test_db
    pytest tests/load/test_system_load.py -v -m "e2e and slow" --junit-xml=load-test-results.xml
```

### Docker Example
```bash
# Start test services
docker-compose -f docker-compose.test.yml up -d

# Run load tests
docker-compose -f docker-compose.test.yml exec app \
  pytest tests/load/test_system_load.py -v -m "e2e and slow"

# Cleanup
docker-compose -f docker-compose.test.yml down
```

## Performance Baselines

Typical performance on reference hardware (4 CPU, 8GB RAM):

| Test | Duration | Throughput | Success Rate |
|------|----------|------------|--------------|
| API 50 concurrent | ~3s | 15-20 req/s | 95-100% |
| DB 100 concurrent | ~2s | 40-50 queries/s | 100% |
| DB pool stress (150) | ~3s | 45-55 queries/s | 100% |
| Mixed load (100 ops) | ~2s | 40-50 ops/s | 95-100% |
| Sustained 10s | ~10s | 18-22 queries/s | 98-100% |

## Maintenance

### Adding New Load Tests
1. Follow existing test pattern
2. Use `@pytest.mark.e2e` and `@pytest.mark.slow`
3. Use `@pytest.mark.asyncio` for async tests
4. Use `asyncio.gather` for concurrency
5. Record metrics with `LoadTestMetrics`
6. Assert against `TEST_MIN_SUCCESS_RATE`

### Updating Test Parameters
Edit constants at top of `test_system_load.py`:
```python
TEST_CONCURRENT_API_REQUESTS = 50  # Increase for more load
TEST_CONCURRENT_DB_QUERIES = 100   # Increase for more load
TEST_MIN_SUCCESS_RATE = 0.90       # Adjust success threshold
```

## Related Documentation

- [Testing Guide](../README.md)
- [Database Schema](../../sql/)
- [API Documentation](../../docs/API.md)
- [Performance Tuning](../../docs/PERFORMANCE.md)
