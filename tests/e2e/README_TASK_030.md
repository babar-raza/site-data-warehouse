# TASK-030: Full Pipeline E2E Tests

## Overview

Complete end-to-end tests for the data pipeline, validating:
- Daily pipeline execution
- Data flow from ingestion to API
- Insight lifecycle (NEW → DIAGNOSED → RESOLVED)

## Test File

**Location:** `tests/e2e/test_complete_pipeline.py`
**Lines:** 659
**Tests:** 6
**Markers:** `@pytest.mark.e2e`, `@pytest.mark.integration`

## Tests Included

### 1. test_daily_pipeline_execution
**Purpose:** Validate daily_pipeline() completes successfully
**Duration:** < 5 minutes
**Flow:** Execute scheduler.daily_pipeline()
```python
@pytest.mark.timeout(300)
def test_daily_pipeline_execution(self, docker_services, warehouse_dsn)
```

### 2. test_data_ingestion_to_engine_flow
**Purpose:** Test data flow from GSC to InsightEngine
**Flow:** GSC Data → InsightEngine → Insights Table
```python
@pytest.mark.timeout(300)
def test_data_ingestion_to_engine_flow(
    self, docker_services, warehouse_dsn, sample_gsc_data, clean_insights
)
```

### 3. test_engine_to_api_flow
**Purpose:** Test insights flow from engine to API
**Flow:** InsightEngine → Repository → Insights API
```python
@pytest.mark.timeout(300)
def test_engine_to_api_flow(
    self, docker_services, warehouse_dsn, sample_gsc_data, clean_insights
)
```

### 4. test_insight_status_lifecycle
**Purpose:** Validate complete insight lifecycle
**Flow:** NEW → DIAGNOSED → RESOLVED
```python
@pytest.mark.timeout(300)
def test_insight_status_lifecycle(
    self, docker_services, warehouse_dsn, sample_gsc_data, clean_insights
)
```

### 5. test_complete_pipeline_integration
**Purpose:** Comprehensive end-to-end integration test
**Flow:** Ingestion → Transform → Engine → Repository → API
```python
@pytest.mark.timeout(300)
def test_complete_pipeline_integration(
    self, docker_services, warehouse_dsn, sample_gsc_data, clean_insights
)
```

### 6. test_pipeline_data_quality
**Purpose:** Validate data quality throughout pipeline
**Checks:**
- No NULL values in required fields
- Valid enum values
- Confidence scores in [0, 1]
- Valid timestamps
```python
@pytest.mark.timeout(300)
def test_pipeline_data_quality(
    self, docker_services, warehouse_dsn, sample_gsc_data, clean_insights
)
```

## Fixtures

### warehouse_dsn (class-scoped)
Provides test database connection string from docker_services

### db_connection (class-scoped)
PostgreSQL connection with autocommit enabled

### clean_insights (function-scoped)
Truncates insights table before and after each test

### sample_gsc_data (function-scoped)
Creates realistic GSC data with:
- 30 days of data
- 5 pages × 3 queries per page
- Declining pattern in last 7 days (for anomaly detection)
- Returns property URL for testing

## Running Tests

### Run all E2E tests:
```bash
pytest tests/e2e/test_complete_pipeline.py -v
```

### Run specific test:
```bash
pytest tests/e2e/test_complete_pipeline.py::TestCompletePipeline::test_insight_status_lifecycle -v
```

### Run with markers:
```bash
# Run all e2e tests
pytest -m e2e -v

# Run all integration tests
pytest -m integration -v
```

### Run with output:
```bash
pytest tests/e2e/test_complete_pipeline.py -v -s
```

### Run with coverage:
```bash
pytest tests/e2e/test_complete_pipeline.py --cov=insights_core --cov=scheduler
```

## Requirements Compliance

| Requirement | Status | Notes |
|------------|--------|-------|
| Tests pass with Docker services | ✓ | Uses docker_services fixture |
| Tests marked @pytest.mark.e2e | ✓ | All 6 tests marked |
| Daily pipeline execution tested | ✓ | test_daily_pipeline_execution |
| Data flow tested | ✓ | test_data_ingestion_to_engine_flow |
| Insight lifecycle tested | ✓ | test_insight_status_lifecycle |
| Timeout: 5 minutes max | ✓ | @pytest.mark.timeout(300) |

## Data Flow Diagram

```
┌─────────────────┐
│  GSC Raw Data   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ InsightEngine   │
│ (all detectors) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Repository     │
│ (create/update) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Database      │
│ gsc.insights    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Insights API   │
│  REST Queries   │
└─────────────────┘
```

## Insight Lifecycle Flow

```
┌──────────────┐
│ Created      │  status: NEW
│ Insight      │  confidence: 0.85
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Updated      │  status: DIAGNOSED
│ (repo.update)│  description: "Root cause identified..."
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Resolved     │  status: RESOLVED
│ (repo.update)│  updated_at > created_at
└──────────────┘
```

## Sample Test Output

```
=== Testing Complete Pipeline Integration ===
✓ Step 1 - Ingestion: 450 rows available
✓ Step 2 - Transforms: Views exist
✓ Step 3 - Engine: Created 3 insights
  Detectors run: 8
  Detectors succeeded: 8
✓ Step 4 - Repository: Retrieved 3 insights
✓ Step 5 - API: Returned 3 insights

=== Pipeline Integration Summary ===
Duration: 12.34s
Steps completed: ingestion, transforms, engine, repository, api
Insights created: 3
Errors: 0
✓ Complete pipeline integration successful
```

## Expected Results

### All Tests Pass
- ✓ Daily pipeline executes within 5 minutes
- ✓ Data flows through all pipeline stages
- ✓ Insights created and stored correctly
- ✓ Lifecycle transitions work properly
- ✓ Data quality maintained throughout
- ✓ API returns correct data (if available)

### Graceful Degradation
- If Insights API not running → API tests skip gracefully
- If API keys not configured → Pipeline steps skip appropriately
- Tests continue and validate what's available

## Troubleshooting

### Test Failures

**Database connection errors:**
```bash
# Ensure Docker services are running
docker-compose -f docker-compose.test.yml up -d
```

**Import errors:**
```bash
# Install test dependencies
pip install -r requirements-test.txt
```

**Timeout errors:**
```bash
# Increase timeout or run tests individually
pytest tests/e2e/test_complete_pipeline.py::TestCompletePipeline::test_insight_status_lifecycle -v
```

### Common Issues

1. **Port conflicts:** Ensure test ports (5433, 6380) are available
2. **Missing fixtures:** Ensure docker_services.py is in tests/fixtures/
3. **Schema issues:** Tests create necessary tables in setup

## Integration with CI/CD

```yaml
# .github/workflows/e2e-tests.yml
- name: Run E2E Tests
  run: |
    docker-compose -f docker-compose.test.yml up -d
    pytest tests/e2e/test_complete_pipeline.py -v -m e2e
    docker-compose -f docker-compose.test.yml down
```

## Next Steps

After these tests pass, consider:
1. Adding GA4 ingestion flow tests
2. Testing SERP and CWV collection
3. Testing content analysis pipeline
4. Adding performance benchmarks
5. Testing error recovery scenarios

## Support

For questions or issues with these tests:
1. Check test output for detailed error messages
2. Review TASK-030-SUMMARY.md for implementation details
3. Examine test_complete_pipeline.py for test logic
4. Verify Docker services are healthy
