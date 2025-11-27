# Dashboard E2E Tests - Integration Guide

How the dashboard E2E tests integrate with the overall test suite.

## Test Hierarchy

```
tests/
├── e2e/                              # End-to-end tests
│   ├── test_dashboard_e2e.py        # ✅ NEW: Dashboard E2E tests
│   ├── conftest.py                  # ✅ NEW: E2E fixtures
│   ├── test_pipeline.py             # Existing: Pipeline E2E
│   ├── test_data_flow.py            # Existing: Data flow E2E
│   └── ...
├── dashboards/                       # Dashboard-specific tests
│   ├── ui/                          # UI tests
│   │   ├── test_dashboard_load.py  # Existing: Basic loading
│   │   └── conftest.py             # Existing: UI fixtures
│   ├── test_dashboard_data.py      # Existing: Data availability
│   └── ...
└── ...
```

## Test Types

### 1. E2E Dashboard Tests (NEW)
**File**: `tests/e2e/test_dashboard_e2e.py`
**Purpose**: Comprehensive end-to-end validation of all dashboards
**When to run**: Before releases, in CI/CD, after dashboard changes

```bash
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

### 2. UI Dashboard Tests (Existing)
**Files**: `tests/dashboards/ui/test_*.py`
**Purpose**: Individual dashboard UI component testing
**When to run**: During development, for specific dashboard work

```bash
pytest tests/dashboards/ui/ -v -m ui
```

### 3. Dashboard Data Tests (Existing)
**File**: `tests/dashboards/test_dashboard_data.py`
**Purpose**: Validate data availability for dashboards
**When to run**: After data ingestion, before UI tests

```bash
pytest tests/dashboards/test_dashboard_data.py -v -m live
```

## Relationship Between Tests

```
┌─────────────────────────────────────────┐
│ Data Layer                              │
│ tests/dashboards/test_dashboard_data.py │
│ - Schema validation                     │
│ - Data availability                     │
│ - Freshness checks                      │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ UI Component Layer                      │
│ tests/dashboards/ui/test_*.py           │
│ - Individual dashboard loading          │
│ - Specific panel testing                │
│ - Dashboard interactions                │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ E2E Integration Layer (NEW)             │
│ tests/e2e/test_dashboard_e2e.py         │
│ - All dashboards together               │
│ - End-to-end workflows                  │
│ - Performance validation                │
│ - Health reporting                      │
└─────────────────────────────────────────┘
```

## Test Execution Strategy

### Development Workflow
```bash
# 1. Run fast unit tests
pytest tests/dashboards/test_dashboard_schema.py -v

# 2. Run data availability tests (requires DB)
pytest tests/dashboards/test_dashboard_data.py -v -m live

# 3. Run specific dashboard UI test
pytest tests/dashboards/ui/test_dashboard_load.py::test_ga4_dashboard_loads -v

# 4. Run full E2E suite (before commit)
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

### CI/CD Pipeline
```yaml
stages:
  - unit
  - integration
  - e2e

unit_tests:
  stage: unit
  script:
    - pytest tests/dashboards/test_dashboard_schema.py -v

integration_tests:
  stage: integration
  script:
    - docker-compose up -d
    - pytest tests/dashboards/test_dashboard_data.py -v -m live
    - pytest tests/dashboards/ui/ -v -m ui

e2e_tests:
  stage: e2e
  script:
    - docker-compose up -d
    - pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

### Pre-Release Checklist
```bash
# 1. All unit tests pass
pytest tests/dashboards/ -v --ignore=tests/dashboards/ui/

# 2. All integration tests pass
pytest tests/dashboards/ tests/integration/ -v -m live

# 3. All UI tests pass
pytest tests/dashboards/ui/ -v -m ui

# 4. All E2E tests pass
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"

# 5. Generate summary report
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardSummary -v -s
```

## Feature Comparison

| Feature | UI Tests | Data Tests | E2E Tests (NEW) |
|---------|----------|------------|-----------------|
| All 11 dashboards | Partial | N/A | ✅ Yes |
| Panel rendering | ✅ Yes | No | ✅ Yes |
| Error detection | ✅ Yes | No | ✅ Yes |
| Data validation | No | ✅ Yes | No |
| Performance tests | Limited | No | ✅ Yes |
| Screenshots | ✅ Yes | No | ✅ Yes |
| Sequential access | No | No | ✅ Yes |
| Refresh testing | No | No | ✅ Yes |
| Health summary | No | No | ✅ Yes |

## Marker Usage

```python
# E2E Dashboard Tests
@pytest.mark.e2e        # End-to-end test
@pytest.mark.ui         # Requires UI/browser
@pytest.mark.asyncio    # Async test

# UI Dashboard Tests
@pytest.mark.ui         # Requires UI/browser
@pytest.mark.asyncio    # Async test

# Data Tests
@pytest.mark.live       # Requires live database
```

## Running Combined Test Suites

```bash
# All dashboard-related tests
pytest tests/dashboards/ tests/e2e/test_dashboard_e2e.py -v

# All UI tests (existing + new E2E)
pytest -v -m ui

# All E2E tests
pytest -v -m e2e

# Full test suite
pytest tests/ -v
```

## Fixtures

### Shared Fixtures (conftest.py)
Both existing UI tests and new E2E tests share:
- `browser` - Playwright browser instance
- `context` - Browser context
- `authenticated_page` - Logged-in page
- `dashboard_urls` - Dashboard URL mapping

### E2E-Specific Fixtures
New in `tests/e2e/conftest.py`:
- Pytest hooks for result capture
- Automatic marker registration
- Test results directory setup

## Migration Path

### If upgrading from existing UI tests:

1. **Keep existing tests** - They remain useful for development
2. **Add E2E tests** - For comprehensive validation
3. **Use both** - Different purposes, complementary

```bash
# Development: Quick feedback
pytest tests/dashboards/ui/test_dashboard_load.py::test_ga4_dashboard_loads -v

# Pre-commit: Comprehensive validation
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

## Environment Setup

### Required for All Dashboard Tests
```bash
# Environment variables
export GRAFANA_URL=http://localhost:3000
export GRAFANA_USER=admin
export GRAFANA_PASSWORD=admin

# Install dependencies
pip install -r requirements-test.txt
playwright install chromium

# Start services
docker-compose up -d grafana prometheus warehouse
```

### Additional for E2E Tests
```bash
# Optional: Configure browser
export BROWSER_TYPE=chromium  # or firefox, webkit
export HEADLESS=true          # or false for debugging
```

## Troubleshooting Integration Issues

### Tests Pass Individually But Fail Together
```bash
# Clear test cache
pytest --cache-clear

# Run with fresh browser contexts
pytest --forked  # Requires pytest-forked
```

### Conflicting Fixtures
The E2E tests use their own conftest.py in the e2e directory, which:
- Doesn't conflict with existing fixtures
- Adds E2E-specific hooks
- Extends pytest configuration

### Database State Issues
```bash
# Run data tests first to ensure data availability
pytest tests/dashboards/test_dashboard_data.py -v -m live

# Then run E2E tests
pytest tests/e2e/test_dashboard_e2e.py -v -m "e2e and ui"
```

## Best Practices

1. **Layered Testing**
   - Unit tests: Fast, isolated
   - Integration tests: With database
   - UI tests: Individual dashboards
   - E2E tests: Complete workflows

2. **Test Isolation**
   - Each test gets fresh browser context
   - No shared state between tests
   - Clean up after each test

3. **Progressive Testing**
   - Run fast tests first
   - Run slow E2E tests before commit
   - Run all tests in CI/CD

4. **Debugging Strategy**
   - Start with unit tests
   - Move to integration tests
   - Use UI tests for specific issues
   - Use E2E tests for system-wide validation

## Continuous Improvement

### Adding New Dashboards
When adding a new dashboard:

1. **Create dashboard JSON**
   - Add to `grafana/provisioning/dashboards/`

2. **Add to E2E tests**
   - Update `DASHBOARDS` dict in `test_dashboard_e2e.py`
   - Add test method in `TestDashboardLoading`

3. **Run tests**
   - Verify dashboard loads
   - Check panel rendering
   - Update documentation

### Monitoring Test Health
```bash
# Generate health report
pytest tests/e2e/test_dashboard_e2e.py::TestDashboardSummary::test_generate_dashboard_summary -v -s

# Track test durations
pytest tests/e2e/test_dashboard_e2e.py --durations=10

# Monitor flaky tests
pytest tests/e2e/test_dashboard_e2e.py --count=5  # Requires pytest-repeat
```

## Support and Documentation

- Main documentation: [README.md](./README.md)
- Quick start: [QUICK_START.md](./QUICK_START.md)
- Task summary: [TASK-031-SUMMARY.md](./TASK-031-SUMMARY.md)
- This guide: [INTEGRATION.md](./INTEGRATION.md)

## Summary

The new E2E dashboard tests complement existing tests by providing:
- ✅ Comprehensive validation of all 11 dashboards
- ✅ End-to-end workflow testing
- ✅ Performance validation
- ✅ Health reporting
- ✅ Production readiness checks

Use them as the final validation step before releases and in CI/CD pipelines.
