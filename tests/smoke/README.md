# Smoke Tests

Quick smoke tests for deployment verification. These tests verify that critical services are running and basic functionality works after deployment.

## Purpose

Smoke tests are designed to:
- **Run quickly** (< 30 seconds total)
- **Test critical paths** only
- **Verify deployment** success
- **Catch major issues** immediately

## What is Tested

### Database Connectivity
- PostgreSQL connection
- Core schema and tables exist
- Recent data exists (< 2 days old)

### Service Health
- **Insights API** - Health endpoint and basic queries
- **Grafana** - Web interface and API accessibility
- **Prometheus** - Health endpoint and query API
- **Metrics Exporter** - Metrics endpoint

### Data Freshness
- GSC data is recent (< 7 days old)
- Insights are recent (< 48 hours old)
- Multiple properties are tracked

### End-to-End
- Complete system verification
- Database → API → Monitoring flow

## Running Smoke Tests

### Basic Usage

```bash
# Run all smoke tests
pytest tests/smoke -m smoke

# Run with verbose output
pytest tests/smoke -m smoke -v

# Run specific test class
pytest tests/smoke::TestDatabaseConnectivity -m smoke

# Run with coverage
pytest tests/smoke -m smoke --cov
```

### Quick Deployment Verification

```bash
# After deployment, run smoke tests to verify system
pytest tests/smoke -m smoke --tb=short
```

### Configuration

Smoke tests use environment variables for service URLs:

```bash
# Database
export WAREHOUSE_DSN="postgresql://user:pass@host:5432/db"

# Services
export API_URL="http://localhost:8000"
export GRAFANA_URL="http://localhost:3000"
export PROMETHEUS_URL="http://localhost:9090"
export METRICS_URL="http://localhost:8002"
```

Default values are provided for local development:
- Database: `postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db`
- API: `http://localhost:8000`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Metrics: `http://localhost:8002`

## Test Organization

### Test Classes

1. **TestDatabaseConnectivity** - Database connection and schema verification
2. **TestServiceHealth** - Service health endpoints (parametrized)
3. **TestGrafanaConnectivity** - Grafana-specific checks
4. **TestPrometheusConnectivity** - Prometheus-specific checks
5. **TestMetricsExporter** - Metrics exporter checks
6. **TestEndToEndSmoke** - Full system smoke test
7. **TestDataFreshness** - Data recency verification

### Parametrized Tests

Service health checks are parametrized for efficiency:

```python
@pytest.mark.parametrize('service_name,url,expected_status', [
    ('api', 'http://localhost:8000/api/health', 200),
    ('mcp', 'http://localhost:8001/health', 200),
    ('grafana', 'http://localhost:3000/api/health', 200),
    ('prometheus', 'http://localhost:9090/-/healthy', 200),
    ('metrics', 'http://localhost:8002/metrics', 200),
])
```

## Performance Requirements

All smoke tests must complete in **< 30 seconds** total:
- Database tests: ~5 seconds
- Service health tests: ~10 seconds
- Data freshness tests: ~5 seconds
- End-to-end test: ~10 seconds

If tests exceed this time:
1. Check network connectivity
2. Verify services are running
3. Check database query performance

## Failure Scenarios

### Database Connection Failure
```
FAILED test_database_connection - Connection refused
```
**Solution**: Verify PostgreSQL is running on correct host/port

### Service Not Reachable
```
FAILED test_service_health_endpoint[insights_api] - ConnectError
```
**Solution**: Verify service is running and accessible at expected URL

### Stale Data
```
FAILED test_recent_data_exists - No recent data found
```
**Solution**: Check data collection services (schedulers, ingestors)

### No Data
```
SKIPPED test_gsc_data_freshness - No GSC data found
```
**Solution**: This is expected on fresh installations. Run data collection.

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run Smoke Tests
  run: |
    pytest tests/smoke -m smoke --tb=short
  env:
    WAREHOUSE_DSN: ${{ secrets.DB_DSN }}
    API_URL: http://localhost:8000
```

### Docker Compose Health Checks

Wait for services before running smoke tests:

```bash
# Wait for services to be healthy
docker-compose ps

# Run smoke tests
docker-compose exec -T api pytest tests/smoke -m smoke
```

## Best Practices

1. **Keep tests fast** - Smoke tests should be quick
2. **Test critical paths only** - Don't test every feature
3. **Use meaningful assertions** - Include context in failure messages
4. **Handle timeouts gracefully** - Set appropriate timeouts (10s default)
5. **Skip when appropriate** - Skip tests if initial setup not complete

## Troubleshooting

### Tests Hang
- Check service timeouts (default: 10 seconds)
- Verify network connectivity
- Check for deadlocks in database

### Intermittent Failures
- Increase timeouts in fixtures
- Check service resource limits
- Verify data consistency

### All Tests Skip
- Check if services are running
- Verify environment variables are set
- Check database schema is initialized

## Related Documentation

- [Integration Tests](../integration/README.md) - Comprehensive integration tests
- [E2E Tests](../e2e/README.md) - End-to-end workflow tests
- [Deployment Guide](../../deployment/README.md) - Deployment procedures
- [Troubleshooting Guide](../../docs/TROUBLESHOOTING.md) - Common issues

## Maintenance

Smoke tests should be reviewed and updated when:
- New critical services are added
- Service URLs or ports change
- Core database schema changes
- New critical features are deployed

Keep smoke tests minimal and focused on deployment verification only.
