# Smoke Tests - Quick Start

## 1-Minute Quick Start

### Prerequisites
- Docker containers running (or services on localhost)
- PostgreSQL accessible
- Python environment with test dependencies

### Run All Smoke Tests
```bash
pytest tests/smoke -m smoke
```

### Expected Output (Success)
```
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_database_connection PASSED
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_schema_exists PASSED
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_core_tables_exist PASSED
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_recent_data_exists PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[insights_api] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[grafana] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[prometheus] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[metrics_exporter] PASSED
...

======================== 25 passed in 15.3s ========================
```

## Common Commands

### Verify Deployment
```bash
# Quick deployment verification
pytest tests/smoke -m smoke --tb=short

# With detailed output
pytest tests/smoke -m smoke -v

# Stop on first failure
pytest tests/smoke -m smoke -x
```

### Test Specific Components

```bash
# Database only
pytest tests/smoke::TestDatabaseConnectivity -m smoke

# Services only
pytest tests/smoke::TestServiceHealth -m smoke

# Data freshness only
pytest tests/smoke::TestDataFreshness -m smoke

# Full system check
pytest tests/smoke::TestEndToEndSmoke -m smoke
```

### With Custom URLs

```bash
# Production environment
WAREHOUSE_DSN="postgresql://user:pass@prod-db:5432/db" \
API_URL="https://api.production.com" \
GRAFANA_URL="https://grafana.production.com" \
PROMETHEUS_URL="https://prometheus.production.com" \
pytest tests/smoke -m smoke

# Staging environment
API_URL="http://staging:8000" \
pytest tests/smoke -m smoke
```

## Interpreting Results

### All Tests Pass ✓
```
======================== 25 passed in 15.3s ========================
```
**Action**: Deployment successful, system is operational

### Service Not Reachable ✗
```
FAILED test_service_health_endpoint[insights_api] - ConnectError
```
**Action**: Check if service is running: `docker-compose ps`

### Database Connection Failed ✗
```
FAILED test_database_connection - Connection refused
```
**Action**: Check database: `docker-compose logs warehouse`

### Stale Data ✗
```
FAILED test_recent_data_exists - No recent data found
```
**Action**: Check schedulers and ingestors are running

### Tests Skipped ⊘
```
SKIPPED [1] - No GSC data found - may be initial setup
```
**Action**: Expected on fresh install, run data collection

## Performance Benchmarks

Expected timing:
- **Database tests**: 3-5 seconds
- **Service health tests**: 8-12 seconds
- **Data freshness tests**: 3-5 seconds
- **End-to-end test**: 5-10 seconds
- **Total**: 20-30 seconds

If tests take > 30 seconds:
1. Check network latency
2. Verify service responsiveness
3. Check database query performance

## Docker Compose Integration

### Before Deployment
```bash
docker-compose down
docker-compose up -d
# Wait for services to be healthy
docker-compose ps
pytest tests/smoke -m smoke
```

### After Changes
```bash
docker-compose restart
# Wait 10 seconds for services to start
sleep 10
pytest tests/smoke -m smoke
```

### Inside Container
```bash
docker-compose exec api pytest tests/smoke -m smoke
```

## Troubleshooting

### Connection Timeout
```bash
# Increase timeout in test file or set longer timeout
pytest tests/smoke -m smoke --timeout=30
```

### Check Service Status
```bash
# Docker
docker-compose ps

# Service health
curl http://localhost:8000/api/health  # Insights API
curl http://localhost:8001/health      # MCP Server
curl http://localhost:9090/-/healthy   # Prometheus
curl http://localhost:3000/api/health  # Grafana
curl http://localhost:8002/metrics     # Metrics Exporter
```

### Check Database
```bash
# Connect to database
psql postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db

# Run quick checks
SELECT COUNT(*) FROM gsc.insights;
SELECT MAX(date) FROM gsc.fact_gsc_daily;
```

### View Logs
```bash
# Service logs
docker-compose logs --tail=50 api_ingestor
docker-compose logs --tail=50 insights_api
docker-compose logs --tail=50 scheduler

# Follow logs
docker-compose logs -f
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Smoke Tests
  run: pytest tests/smoke -m smoke --tb=short
  timeout-minutes: 2
```

### GitLab CI
```yaml
smoke_tests:
  script:
    - pytest tests/smoke -m smoke --tb=short
  timeout: 2m
```

### Jenkins
```groovy
stage('Smoke Tests') {
    steps {
        sh 'pytest tests/smoke -m smoke --tb=short'
    }
    timeout(time: 2, unit: 'MINUTES')
}
```

## Next Steps

After smoke tests pass:
1. Run integration tests: `pytest tests/integration -m integration`
2. Run E2E tests: `pytest tests/e2e -m e2e`
3. Check Grafana dashboards
4. Verify data collection is running
5. Review Prometheus metrics

## Support

For issues:
1. Check [Troubleshooting Guide](../../docs/TROUBLESHOOTING.md)
2. Review service logs
3. Verify environment variables
4. Check [README](./README.md) for detailed documentation
