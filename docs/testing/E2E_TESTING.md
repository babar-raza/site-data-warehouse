# End-to-End Testing Guide

## Overview

The E2E test suite validates the complete GSC Insight Engine pipeline from data ingestion through insight generation to serving.

## Test Structure

```
tests/e2e/
├── fixtures.py       # Test data generation
└── test_pipeline.py  # Main E2E test suite
```

## What Gets Tested

### Stage 1: Data Ingestion
- ✓ GSC data inserted into fact_gsc_daily
- ✓ GA4 data inserted into fact_ga4_daily
- ✓ Date ranges match expectations
- ✓ Row counts correct

### Stage 2: Transform Pipeline
- ✓ Test data appears in unified view
- ✓ WoW/MoM calculations populate correctly
- ✓ GSC and GA4 data joined properly
- ✓ Specific anomaly date has correct calculations

### Stage 3: Insight Generation
- ✓ InsightEngine runs successfully
- ✓ All detectors execute
- ✓ Planted anomaly detected
- ✓ Insight metrics match source data
- ✓ Performance within limits (<30s)

### Stage 4: Serving Layer
- ✓ Insights retrievable via Repository
- ✓ Query filters work (property, category)
- ✓ get_by_id works correctly

### Cleanup & Quality
- ✓ All test data removed
- ✓ No pollution of production tables
- ✓ Deterministic results (repeatable)

## Test Data Pattern

All test data uses `test://` prefix for isolation:

```python
PROPERTY = "test://e2e-pipeline"
PAGE = "/test/page/anomaly"
```

### Planted Anomaly

The test generates 30 days of data with a planted anomaly:

- **Days 1-20:** Stable (100 clicks/day, 10 conversions/day)
- **Days 21-30:** Drop (50 clicks/day, 5 conversions/day)
- **Expected detection:** Day 28 shows -50% WoW drop

This ensures the AnomalyDetector correctly identifies the issue.

## Running Tests

### Full E2E Suite
```bash
pytest tests/e2e/test_pipeline.py -v
```

### Single Stage
```bash
pytest tests/e2e/test_pipeline.py::test_stage3_insight_generation -v
```

### With Coverage
```bash
pytest tests/e2e/test_pipeline.py --cov=insights_core --cov-report=html
```

### Performance Test Only
```bash
pytest tests/e2e/test_pipeline.py::test_performance_within_limits -v
```

## Test Duration

- **Full suite:** ~15-20 seconds
- **Individual tests:** 1-3 seconds each
- **Performance target:** <60 seconds total

## Failure Scenarios Tested

### 1. Missing GA4 Data
Tests system resilience when GA4 ingestion fails but GSC succeeds.

**Expected behavior:**
- No crash
- Insights generated from GSC alone
- GA4 fields NULL in unified view

### 2. Detector Exception
Tests error handling when a detector raises an exception.

**Expected behavior:**
- Exception caught and logged
- Other detectors continue
- Error recorded in stats

### 3. Corrupted Data
Tests handling of invalid/malformed data in fact tables.

**Expected behavior:**
- Data validation catches issues
- Invalid rows skipped
- Process continues

## Cleanup Strategy

Test cleanup is **idempotent** and safe to run multiple times:

```python
# Removes all data with test:// prefix
TestDataGenerator.cleanup_test_data(conn)
```

Cleanup runs:
- Before test suite starts (remove stale data)
- After test suite completes (clean up)
- Can be run manually if tests crash

## Debugging Failed Tests

### Test fails at Stage 1 (Ingestion)
```bash
# Check if data was inserted
psql $WAREHOUSE_DSN -c "
    SELECT COUNT(*) 
    FROM gsc.fact_gsc_daily 
    WHERE property LIKE 'test://%';
"
```

### Test fails at Stage 2 (Transform)
```bash
# Check unified view
psql $WAREHOUSE_DSN -c "
    SELECT * 
    FROM gsc.vw_unified_page_performance 
    WHERE property LIKE 'test://%' 
    LIMIT 5;
"
```

### Test fails at Stage 3 (Insights)
```bash
# Check what insights were created
psql $WAREHOUSE_DSN -c "
    SELECT category, title, severity 
    FROM gsc.insights 
    WHERE property LIKE 'test://%';
"

# Check InsightEngine logs
tail -100 logs/scheduler.log | grep -i insight
```

### Manual Cleanup
```bash
# If tests crash and leave data behind
python3 << 'EOF'
import os
import psycopg2
from tests.e2e.fixtures import TestDataGenerator

conn = psycopg2.connect(os.environ['WAREHOUSE_DSN'])
stats = TestDataGenerator.cleanup_test_data(conn)
print(f"Cleaned up: {stats}")
conn.close()
EOF
```

## Best Practices

### 1. Isolation
- Always use `test://` prefix for test data
- Never modify production data in tests
- Each test should be independent

### 2. Determinism
- Fixed dates (relative to today)
- Stable ordering (ORDER BY in queries)
- Predictable anomalies

### 3. Performance
- Target: <60s for full suite
- Use transactions for speed
- Batch inserts where possible

### 4. Maintainability
- Clear test names (test_stage1_*, test_stage2_*)
- Descriptive assertions with messages
- Comments explaining what's being tested

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: gsc_db
          POSTGRES_USER: gsc_user
          POSTGRES_PASSWORD: gsc_pass
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup database
        run: psql $DATABASE_URL -f sql/01_schema.sql
        
      - name: Run E2E tests
        run: pytest tests/e2e/ -v
        env:
          WAREHOUSE_DSN: ${{ env.DATABASE_URL }}
```

## Troubleshooting

### "WAREHOUSE_DSN not set"
```bash
export WAREHOUSE_DSN="postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db"
```

### "No test data found in unified view"
- Check that transforms ran: `SELECT COUNT(*) FROM gsc.vw_unified_page_performance`
- Verify test data inserted: `SELECT COUNT(*) FROM gsc.fact_gsc_daily WHERE property LIKE 'test://%'`

### "Insights not created"
- Check if data has 7+ days for WoW: `SELECT COUNT(DISTINCT date) FROM gsc.fact_gsc_daily WHERE property LIKE 'test://%'`
- Verify anomaly thresholds: Default is -20% for risks, may need tuning

### "Test takes too long"
- Check database indices exist
- Use materialized views if available
- Consider running cleanup in background

## Future Enhancements

- [ ] Add load testing (1M+ rows)
- [ ] Test MCP tool integration
- [ ] Test API endpoints (requires running server)
- [ ] Test dispatcher routing
- [ ] Add data quality validation tests
- [ ] Test with multiple properties simultaneously

## Related Documentation

- **Architecture:** `docs/ARCHITECTURE.md`
- **Development:** `docs/DEVELOPMENT.md`
- **API Reference:** `docs/API_REFERENCE.md`
