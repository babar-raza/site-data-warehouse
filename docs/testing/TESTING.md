# Testing Guide - Site Data Warehouse

**Comprehensive testing documentation for the GSC Data Warehouse / Insight Engine**

---

## Table of Contents

1. [Overview](#overview)
2. [Dual-Mode Testing](#dual-mode-testing)
3. [Running Tests](#running-tests)
4. [Playwright Dashboard Testing](#playwright-dashboard-testing)
5. [Test Organization](#test-organization)
6. [Coverage Requirements](#coverage-requirements)
7. [Writing New Tests](#writing-new-tests)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This project implements a **dual-mode testing strategy**:

- **Mock Mode (default)**: Fast, deterministic unit tests using mocks. No external services required.
- **Live Mode (opt-in)**: Integration tests using real services (PostgreSQL, APIs) with curated sample data.

**Test Statistics:**
- **Total Tests**: 200+ comprehensive test cases
- **Core Coverage**: 55%+ overall, 95%+ on Tier 1 modules
- **Execution Time**: <5 seconds for full mock suite

---

## Dual-Mode Testing

### Mock Mode (Default)

**Purpose**: Fast, deterministic testing without external dependencies.

**Characteristics:**
- Uses `unittest.mock` extensively
- No database, API calls, or file I/O
- Runs in CI/CD pipelines
- Suitable for development workflow

**Activate:**
```bash
# Default - no environment variable needed
pytest tests/

# Or explicitly:
export TEST_MODE=mock
pytest tests/
```

**What's Mocked:**
- Database connections (psycopg2)
- HTTP requests (requests, httpx)
- File I/O operations
- External API calls (GSC, GA4)
- LLM/AI services

---

### Live Mode (Integration Testing)

**Purpose**: End-to-end validation with real services.

**Characteristics:**
- Uses actual PostgreSQL database
- May call real APIs (GSC, GA4) if credentials provided
- Uses curated sample data from `samples/`
- Suitable for pre-deployment validation

**Activate:**
```bash
export TEST_MODE=live
export WAREHOUSE_DSN="postgresql://user:pass@localhost:5432/test_db"
pytest tests/ -m live
```

**Requirements:**
- PostgreSQL 13+ running and accessible
- Test database created (see [Database Setup](#database-setup))
- Optional: GSC/GA4 credentials for API tests

**Skip Live Tests:**
Live tests are automatically skipped in mock mode:
```python
@pytest.mark.live
@require_live_mode
def test_with_real_database():
    # Only runs when TEST_MODE=live
    pass
```

---

## Running Tests

### Quick Start

```bash
# Run all mock tests (default)
pytest tests/

# Run with coverage
pytest tests/ --cov=insights_core --cov=agents --cov=ingestors

# Run specific module tests
pytest tests/insights_core/
pytest tests/agents/base/

# Run verbose with short traceback
pytest tests/ -v --tb=short

# Run and generate HTML coverage report
pytest tests/ --cov=insights_core --cov-report=html
# Open htmlcov/index.html in browser
```

### Module-Specific Tests

```bash
# Tier 1 - Core Business Logic
pytest tests/insights_core/test_engine.py -v
pytest tests/insights_core/test_models.py -v
pytest tests/insights_core/test_repository.py -v
pytest tests/insights_core/test_dispatcher.py -v
pytest tests/insights_core/test_channels.py -v
pytest tests/agents/base/test_agent_contract.py -v
pytest tests/agents/base/test_message_bus.py -v

# Tier 2 - Integration & Orchestration
pytest tests/agents/test_diagnostician_agent.py -v
pytest tests/agents/test_strategist_agent.py -v
pytest tests/agents/test_watcher_agent.py -v

# Tier 3 - E2E & Performance
pytest tests/e2e/ -v
pytest tests/load/ -v
```

### Live Mode Tests

```bash
# Setup environment
export TEST_MODE=live
export WAREHOUSE_DSN="postgresql://gsc_user:password@localhost:5432/gsc_test"

# Run only live tests
pytest tests/ -m live -v

# Run specific live test suite
pytest tests/e2e/ -v --tb=short

# Skip live tests (useful in CI)
pytest tests/ -m "not live"
```

---

## Playwright Dashboard Testing

### Overview

Playwright provides browser-based E2E testing for all 11 Grafana dashboards. Tests verify:
- Dashboards are accessible (HTTP 200)
- Panels render without errors
- Data sources are connected
- UI features work correctly (time pickers, titles)

### Installation

```bash
# Install Playwright dependencies
pip install -r requirements/playwright.txt

# Install browser (Chromium recommended)
playwright install chromium

# Or install all browsers
playwright install chromium firefox webkit
```

### Running Dashboard Tests

```bash
# Basic run (headless)
pytest tests/e2e/test_dashboard_e2e.py -v --no-cov

# With visible browser (useful for debugging)
pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --headed

# Generate HTML report
pytest tests/e2e/test_dashboard_e2e.py -v --no-cov \
    --html=test-results/reports/dashboard_report.html --self-contained-html

# Use different browser
pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --browser firefox

# Skip slow performance tests
pytest tests/e2e/test_dashboard_e2e.py -v --no-cov -m "not slow"

# Using convenience script (Windows)
scripts\run-dashboard-tests.bat --headed --report

# Using convenience script (Linux/Mac)
./scripts/run-dashboard-tests.sh --headed --report
```

### Dashboards Tested

| Dashboard | UID | Description |
|-----------|-----|-------------|
| GA4 Overview | `ga4-overview` | Google Analytics 4 metrics |
| GSC Overview | `gsc-overview` | Google Search Console data |
| Hybrid Overview | `hybrid-overview` | Combined GSC/GA4 analytics |
| Service Health | `service-health` | Service status monitoring |
| Infrastructure | `infrastructure-overview` | Resource monitoring |
| Database Performance | `database-performance` | PostgreSQL metrics |
| CWV Monitoring | `cwv-monitoring` | Core Web Vitals (LCP, FID, CLS) |
| SERP Tracking | `serp-tracking` | Search position tracking |
| Actions Command Center | `actions-command-center` | Automation status |
| Alert Status | `alert-status` | Alert rules monitoring |
| Application Metrics | `application-metrics` | App-level performance |

### Test Classes

| Class | Purpose |
|-------|---------|
| `TestDashboardAccessibility` | HTTP status codes, Grafana reachability |
| `TestDashboardLoading` | Individual dashboard panel error checks |
| `TestPanelRendering` | Panel presence, errors, loading states |
| `TestDashboardFeatures` | Titles, time pickers, UI elements |
| `TestDashboardPerformance` | Load times within thresholds |
| `TestDashboardIntegration` | Sequential access, refresh functionality |
| `TestDashboardSummary` | Health report generation |

### Configuration

**Environment Variables:**
```bash
GRAFANA_URL=http://localhost:3000      # Grafana URL (default)
GRAFANA_USER=admin                     # Username (default: admin)
GRAFANA_PASSWORD=admin                 # Password (default: admin)
HEADLESS=true                          # Run headless (default: true)
BROWSER_TYPE=chromium                  # Browser: chromium, firefox, webkit
```

**pytest.ini markers:**
```ini
markers =
    dashboard: mark test as dashboard-specific test
    playwright: mark test as requiring Playwright browser automation
    ui: mark test as requiring browser/UI
```

### Test Output

- **Screenshots**: `test-results/screenshots/` - Captured on failures
- **HTML Reports**: `test-results/reports/dashboard_report.html`
- **Console Summary**: Dashboard health status printed to console

### Writing New Dashboard Tests

```python
from tests.e2e.conftest import (
    GRAFANA_URL, DASHBOARD_DEFINITIONS,
    wait_for_dashboard_load, get_panel_errors, take_screenshot
)

class TestMyDashboard:
    def test_custom_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Test custom dashboard loads without errors."""
        authenticated_page.goto(dashboard_urls["my-dashboard"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "my_dashboard_errors")
        assert error_count == 0
```

### Troubleshooting

**Tests hang or timeout:**
- Ensure Grafana is running: `curl http://localhost:3000/api/health`
- Check credentials are correct
- Try running with `--headed` to see browser behavior

**"No browser installed" error:**
```bash
playwright install chromium
```

**Panel errors detected (expected behavior):**
- Tests detecting panel errors means dashboards have issues
- Check Grafana datasource configuration
- Verify Prometheus/PostgreSQL connections

---

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                    # pytest configuration & fixtures
├── testing_modes.py               # Dual-mode testing helpers
│
├── insights_core/                 # Core engine tests
│   ├── __init__.py
│   ├── test_engine.py             # InsightEngine orchestration
│   ├── test_models.py             # Pydantic models
│   ├── test_repository.py         # Database CRUD (mock)
│   ├── test_dispatcher.py         # Channel dispatch logic
│   ├── test_channels.py           # Base channel functionality
│   └── test_detectors.py          # Detector logic
│
├── agents/                        # Agent system tests
│   ├── base/
│   │   ├── __init__.py
│   │   ├── test_agent_contract.py  # Agent base class
│   │   └── test_message_bus.py     # Pub/sub messaging
│   ├── test_diagnostician_agent.py
│   ├── test_strategist_agent.py
│   ├── test_watcher_agent.py
│   └── test_dispatcher_agent.py
│
├── ingestors/                     # Data ingestion tests
│   ├── test_ga4_extractor.py
│   └── __init__.py
│
├── e2e/                           # End-to-end tests
│   ├── conftest.py                # Playwright fixtures & helpers
│   ├── test_dashboard_e2e.py      # Grafana dashboard tests (Playwright)
│   ├── test_pipeline.py           # Full pipeline tests
│   ├── test_data_flow.py          # Data flow validation
│   └── test_full_pipeline.py      # Complete integration
│
├── warehouse/                     # Warehouse tests
│   └── test_unified_view.py
│
├── metrics/                       # Metrics tests
│   ├── test_exporter.py
│   └── test_integration.py
│
└── load/                          # Load/performance tests
    └── test_system_load.py
```

### Test Naming Conventions

- **Test Files**: `test_<module_name>.py`
- **Test Classes**: `Test<ClassName>`
- **Test Methods**: `test_<what>_<scenario>`

**Examples:**
```python
class TestInsightRepository:
    def test_create_insight_success(self):
        """Test creating a new insight successfully"""
        pass

    def test_create_insight_duplicate(self):
        """Test handling duplicate insight creation"""
        pass
```

---

## Coverage Requirements

### Tier 1 - Core Business Logic (~100% Required)

**Modules:**
- `insights_core/engine.py` - 98% ✅
- `insights_core/models.py` - 94% ✅
- `insights_core/repository.py` - **99%** ✅
- `insights_core/dispatcher.py` - **97%** ✅
- `insights_core/detectors/*.py` - 88% ✅
- `insights_core/channels/base.py` - **94%** ✅
- `agents/base/agent_contract.py` - **94%** ✅
- `agents/base/message_bus.py` - **73%** ⚠️

**Status**: Core modules have excellent coverage. Message bus needs async worker tests for 95%+.

---

### Tier 2 - Integration & Orchestration (≥95% Target)

**Modules:**
- `insights_api/insights_api.py`
- `mcp/mcp_server.py`
- `scheduler/scheduler.py`
- `agents/diagnostician/*`
- `agents/strategist/*`
- `agents/watcher/*`

**Status**: Work in progress. Most modules have basic test coverage.

---

### Tier 3 - Operational Scripts (≥80% Target)

**Modules:**
- `insights_core/cli.py`
- `scripts/backfill_historical.py`
- `scripts/validate_data.py`

**Status**: Smoke tests needed for CLI and scripts.

---

## Writing New Tests

### Mock-Based Unit Tests

**Example: Testing a database-dependent method**

```python
from unittest.mock import Mock, patch, MagicMock

def test_create_insight_success(mock_dsn, sample_insight_create):
    """Test creating a new insight"""
    with patch('insights_core.repository.psycopg2.connect') as mock_connect:
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'id': 'test-123', ...}

        # Execute
        repo = InsightRepository(mock_dsn)
        result = repo.create(sample_insight_create)

        # Verify
        assert isinstance(result, Insight)
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
```

### Live Integration Tests

**Example: Testing with real database**

```python
import pytest
from tests.testing_modes import require_live_mode, skip_if_no_postgres

@pytest.mark.live
@skip_if_no_postgres
def test_full_pipeline_integration():
    """Test complete pipeline with real database"""
    # Load sample data
    load_samples_into_db()

    # Run insight engine
    engine = InsightEngine(config)
    stats = engine.refresh()

    # Verify structure (not exact values)
    assert stats['total_insights_created'] > 0
    assert 'AnomalyDetector' in stats['insights_by_detector']
```

### Fixtures

**Common fixtures in `conftest.py`:**

```python
@pytest.fixture
def mock_db_dsn():
    """Mock database DSN"""
    return "postgresql://test:test@localhost:5432/test_db"

@pytest.fixture
def sample_insight_create():
    """Sample InsightCreate for testing"""
    return InsightCreate(
        property="sc-domain:example.com",
        entity_type=EntityType.PAGE,
        entity_id="/test-page",
        category=InsightCategory.RISK,
        # ... more fields
    )
```

---

## Database Setup (Live Mode)

### Create Test Database

```bash
# Create test database
psql -U postgres -c "CREATE DATABASE gsc_test;"
psql -U postgres -c "CREATE USER gsc_user WITH PASSWORD 'gsc_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE gsc_test TO gsc_user;"

# Run schema migrations
export WAREHOUSE_DSN="postgresql://gsc_user:gsc_password@localhost:5432/gsc_test"
for script in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$script"
done
```

### Load Sample Data

```bash
# Load curated samples for testing
python scripts/load_samples.py --db gsc_test --samples-dir samples/
```

### Cleanup Test Data

```bash
# Truncate tables between test runs
psql $WAREHOUSE_DSN -c "TRUNCATE TABLE gsc.insights, gsc.fact_gsc_daily, gsc.fact_ga4_daily CASCADE;"
```

---

## Troubleshooting

### Common Issues

#### 1. Tests Fail with "could not translate host name 'warehouse'"

**Cause**: Repository tests trying to connect to real database.

**Solution**: Tests should be using mocks. Verify the test file imports and patches psycopg2.connect:

```python
with patch('insights_core.repository.psycopg2.connect') as mock_connect:
    # Test code here
```

---

#### 2. Live Tests Skipped

**Cause**: `TEST_MODE` not set to `live` or required services unavailable.

**Solution**:
```bash
export TEST_MODE=live
export WAREHOUSE_DSN="postgresql://..."  # Valid DSN required
pytest tests/ -m live -v
```

---

#### 3. Coverage Lower Than Expected

**Cause**: Some tests may not be running or modules not included in coverage.

**Solution**:
```bash
# Verify which tests are running
pytest tests/ --collect-only

# Check coverage configuration
cat .coveragerc

# Run coverage with specific includes
pytest tests/ --cov=insights_core --cov=agents --cov-report=term-missing
```

---

#### 4. Async Test Warnings

**Cause**: Async mocks not properly awaited.

**Solution**: Use `AsyncMock` for coroutines:

```python
from unittest.mock import AsyncMock

mock_func = AsyncMock(return_value={"result": "data"})
result = await mock_func()
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests (mock mode)
        run: |
          export TEST_MODE=mock
          pytest tests/ --cov=insights_core --cov=agents --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

---

## Best Practices

1. **Write Tests First**: TDD approach ensures testability
2. **Mock External Services**: Keep tests fast and deterministic
3. **Use Fixtures**: Reduce code duplication
4. **Test Edge Cases**: Not just happy paths
5. **Clear Assertions**: One logical assertion per test
6. **Descriptive Names**: Test names should document behavior
7. **Avoid Test Interdependence**: Each test should be independent

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [E2E Test Plan](../E2E_TEST_PLAN.md)
- [Coverage Summary](../../reports/coverage-final.txt)

---

**Last Updated**: 2025-11-27
**Test Framework**: pytest 8.4.2, pytest-playwright 0.7.2
**Python Version**: 3.9+
