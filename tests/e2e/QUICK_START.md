# Dashboard E2E Tests - Quick Start

Fast guide to running Playwright-based dashboard tests.

## 1. Install Prerequisites

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Install Playwright browsers
playwright install chromium
```

## 2. Start Services

```bash
# Start all services
docker-compose up -d

# Or just Grafana + dependencies
docker-compose up -d grafana prometheus warehouse
```

## 3. Run Tests

### Quick Run (All Tests)
```bash
# Linux/Mac
./tests/e2e/run_dashboard_tests.sh

# Windows
tests\e2e\run_dashboard_tests.bat
```

### Manual Run
```bash
# All E2E tests
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"

# Specific test class
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading -v

# Specific dashboard
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_ga4_dashboard_loads -v

# With visible browser
HEADLESS=false pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

## 4. Common Issues

### Playwright Not Found
```bash
pip install playwright
playwright install
```

### Grafana Not Running
```bash
docker-compose up -d grafana
curl http://localhost:3000/api/health
```

### Authentication Failed
Check `.env` file:
```bash
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
GRAFANA_URL=http://localhost:3000
```

### Tests Failing
1. Check screenshots: `test-results/screenshots/`
2. Run in headed mode: `HEADLESS=false pytest ...`
3. Check Grafana logs: `docker logs gsc_grafana`
4. Verify data exists: Check dashboards manually in browser

## 5. Test Output

### Success
```
tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_ga4_dashboard_loads PASSED
tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_gsc_dashboard_loads PASSED
...
✓ All tests passed!
```

### Failure
```
tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_ga4_dashboard_loads FAILED
...
Screenshot saved: test-results/screenshots/ga4_errors.png
```

## 6. Configuration

Environment variables:
```bash
export GRAFANA_URL=http://localhost:3000
export GRAFANA_USER=admin
export GRAFANA_PASSWORD=admin
export HEADLESS=true
export BROWSER_TYPE=chromium
```

## 7. Dashboards Tested

- ✅ ga4-overview
- ✅ gsc-overview
- ✅ hybrid-overview
- ✅ service-health
- ✅ infrastructure-overview
- ✅ database-performance
- ✅ cwv-monitoring
- ✅ serp-tracking
- ✅ actions-command-center
- ✅ alert-status
- ✅ application-metrics

## 8. Quick Debugging

```bash
# Run with verbose output and visible browser
HEADLESS=false pytest tests/e2e/test_dashboard_e2e.py -v -s -m "e2e and ui"

# Run single test with debugging
HEADLESS=false pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_ga4_dashboard_loads -v -s

# Generate summary report
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardSummary::test_generate_dashboard_summary -v -s
```

## 9. CI/CD Integration

```yaml
# .github/workflows/dashboard-e2e.yml
- name: Run Dashboard E2E Tests
  run: |
    docker-compose up -d
    sleep 30
    pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

## 10. Next Steps

- Review full documentation: [README.md](./README.md)
- Add custom tests for your dashboards
- Configure CI/CD pipeline
- Set up scheduled test runs
- Monitor test results over time
