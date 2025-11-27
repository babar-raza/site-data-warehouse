# E2E Tests

End-to-end tests for the SEO Intelligence Platform.

## Dashboard E2E Tests

Comprehensive Playwright-based tests for all Grafana dashboards.

### Prerequisites

1. **Install Playwright**:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Start Services**:
   ```bash
   docker-compose up -d
   ```

3. **Set Environment Variables** (optional):
   ```bash
   export GRAFANA_URL=http://localhost:3000
   export GRAFANA_USER=admin
   export GRAFANA_PASSWORD=admin
   export HEADLESS=true
   export BROWSER_TYPE=chromium
   ```

### Running Tests

#### Run All Dashboard E2E Tests
```bash
pytest tests/e2e/test_dashboard_e2e.py -v -m e2e -m ui
```

#### Run Specific Test Classes
```bash
# Test dashboard accessibility
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardAccessibility -v

# Test dashboard loading
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading -v

# Test panel rendering
pytest tests/e2e/test_dashboard_e2e.py::TestPanelRendering -v

# Test dashboard features
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardFeatures -v

# Test performance
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardPerformance -v

# Generate summary report
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardSummary -v
```

#### Run Specific Dashboard Tests
```bash
# Test GA4 dashboard
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_ga4_dashboard_loads -v

# Test GSC dashboard
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_gsc_dashboard_loads -v

# Test Actions Command Center
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardLoading::test_actions_command_center_dashboard_loads -v
```

#### Run in Headed Mode (with browser visible)
```bash
HEADLESS=false pytest tests/e2e/test_dashboard_e2e.py -v -m e2e -m ui
```

#### Run with Different Browser
```bash
# Firefox
BROWSER_TYPE=firefox pytest tests/e2e/test_dashboard_e2e.py -v

# WebKit (Safari)
BROWSER_TYPE=webkit pytest tests/e2e/test_dashboard_e2e.py -v
```

#### Run with Verbose Output
```bash
pytest tests/e2e/test_dashboard_e2e.py -v -s -m e2e -m ui
```

### Dashboards Tested

The test suite covers all 11 dashboards:

1. **ga4-overview** - GA4 Analytics Overview
2. **gsc-overview** - Google Search Console Data Overview
3. **hybrid-overview** - Hybrid Analytics (GSC + GA4 Unified)
4. **service-health** - Service Health Monitoring
5. **infrastructure-overview** - Infrastructure Overview
6. **database-performance** - Database Performance Metrics
7. **cwv-monitoring** - Core Web Vitals Monitoring
8. **serp-tracking** - SERP Position Tracking
9. **actions-command-center** - Actions Command Center
10. **alert-status** - Alert Status Dashboard
11. **application-metrics** - Application Metrics

### Test Classes

#### TestDashboardAccessibility
- Verifies all dashboards return HTTP 200
- Checks Grafana is reachable

#### TestDashboardLoading
- Tests each dashboard loads without errors
- Verifies titles are visible
- Checks for panel errors
- Takes screenshots on failure

#### TestPanelRendering
- Verifies all dashboards have panels
- Checks panels render without errors
- Ensures panels finish loading (not stuck)

#### TestDashboardFeatures
- Verifies dashboard titles are present
- Checks time range pickers exist

#### TestDashboardPerformance
- Tests dashboards load within timeout
- Monitors loading times

#### TestDashboardIntegration
- Tests sequential access to all dashboards
- Tests dashboard refresh functionality

#### TestDashboardSummary
- Generates comprehensive health report
- Provides summary of all dashboard statuses

### Test Results

#### Screenshots
Screenshots are automatically captured on test failures:
- Location: `test-results/screenshots/`
- Naming: `{dashboard_name}_{failure_type}.png`

#### Videos
When running in non-headless mode, videos are recorded:
- Location: `test-results/videos/`

### Troubleshooting

#### Playwright Not Installed
```bash
pip install playwright
playwright install
```

#### Grafana Not Running
```bash
docker-compose up -d grafana
# Wait for Grafana to start
docker logs gsc_grafana
```

#### Authentication Failures
1. Check Grafana credentials in `.env`:
   ```bash
   GRAFANA_USER=admin
   GRAFANA_PASSWORD=admin
   ```

2. Verify Grafana is accessible:
   ```bash
   curl http://localhost:3000/api/health
   ```

#### Dashboard Load Failures
1. Check dashboard exists in Grafana
2. Verify database has data
3. Check Prometheus is running
4. Review screenshots in `test-results/screenshots/`

#### Panel Errors
1. Review dashboard queries in Grafana UI
2. Check database schema and tables exist
3. Verify data is being ingested
4. Check Prometheus datasource configuration

### CI/CD Integration

#### GitHub Actions Example
```yaml
name: Dashboard E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
          playwright install chromium

      - name: Start services
        run: docker-compose up -d

      - name: Wait for Grafana
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:3000/api/health; do sleep 2; done'

      - name: Run E2E tests
        run: |
          pytest tests/e2e/test_dashboard_e2e.py -v -m e2e -m ui

      - name: Upload screenshots on failure
        if: failure()
        uses: actions/upload-artifact@v2
        with:
          name: test-screenshots
          path: test-results/screenshots/
```

### Best Practices

1. **Run tests against running Grafana instance**
2. **Use headless mode for CI/CD**
3. **Review screenshots on failures**
4. **Keep dashboards and tests in sync**
5. **Test in multiple browsers if possible**
6. **Monitor test execution times**
7. **Update dashboard URLs if UIDs change**

### Extending Tests

To add tests for a new dashboard:

1. **Add dashboard definition** in `DASHBOARDS` dict:
   ```python
   "new-dashboard": {
       "uid": "new-dashboard-uid",
       "slug": "new-dashboard-slug",
       "title": "New Dashboard Title",
   }
   ```

2. **Add load test** in `TestDashboardLoading`:
   ```python
   async def test_new_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
       """New dashboard should load without errors"""
       await authenticated_page.goto(dashboard_urls["new-dashboard"])
       await wait_for_dashboard_load(authenticated_page)

       title = authenticated_page.locator('h1, [class*="dashboard-title"]')
       await expect(title.first).to_be_visible(timeout=10000)

       error_count = await get_panel_errors(authenticated_page)
       if error_count > 0:
           await take_screenshot(authenticated_page, "new_dashboard_errors")
       assert error_count == 0, f"New dashboard has {error_count} panel errors"
   ```

3. **Run tests** to verify new dashboard works.

### Performance Metrics

Typical dashboard load times (with data):
- **GA4 Overview**: 2-5 seconds
- **GSC Overview**: 2-5 seconds
- **Hybrid Overview**: 3-7 seconds
- **Service Health**: 1-3 seconds
- **Infrastructure**: 2-4 seconds
- **Database Performance**: 2-4 seconds
- **CWV Monitoring**: 3-6 seconds
- **SERP Tracking**: 3-6 seconds
- **Actions Command Center**: 4-8 seconds
- **Alert Status**: 1-3 seconds
- **Application Metrics**: 2-4 seconds

### Support

For issues or questions:
1. Check test output and screenshots
2. Review Grafana logs: `docker logs gsc_grafana`
3. Verify database connectivity
4. Check Prometheus health
5. Review dashboard JSON files in `grafana/provisioning/dashboards/`
