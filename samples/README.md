# Test Samples

This directory contains curated sample data for **live mode testing**.

---

## Purpose

- Support end-to-end testing with realistic (but minimal) data
- Enable validation without requiring full production datasets
- Provide consistent test fixtures for integration scenarios

---

## Structure

- `gsc_sample_data.csv` - Sample GSC metrics (30 days, 10 pages)
- `ga4_sample_data.csv` - Sample GA4 metrics (30 days, 10 pages)
- `sample_insights.json` - Expected insights from sample data
- `test_scenario_*.sql` - SQL scripts to seed test database

---

## Usage

### Mock Mode (default)
Tests use synthetic data generated in test fixtures. Samples are **not used**.

```bash
# Mock mode - default behavior
pytest tests/
```

### Live Mode
Live mode uses actual database and sample data for integration testing.

```bash
export TEST_MODE=live
export WAREHOUSE_DSN="postgresql://user:pass@localhost:5432/test_db"
pytest tests/e2e/ -v --tb=short
```

**Tests will:**
1. Load samples into test database
2. Run actual system components
3. Validate outputs against expected results

---

## Data Characteristics

Sample data is designed to trigger:
- **At least 1 anomaly** - Traffic drop >20% (tests AnomalyDetector)
- **At least 1 opportunity** - Impression spike >50% (tests OpportunityDetector)
- **At least 1 diagnosis** - Ranking issue (tests DiagnosisDetector)

This ensures detectors have something to find during validation.

---

## Related Documentation

- **[Testing Guide](../docs/testing/TESTING.md)** - Comprehensive testing documentation
- **[E2E Test Plan](../docs/E2E_TEST_PLAN.md)** - End-to-end testing guide
- **[Main README](../README.md)** - Project overview

---

**Last Updated**: 2025-11-21
