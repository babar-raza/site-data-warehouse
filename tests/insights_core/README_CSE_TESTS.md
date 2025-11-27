# DiagnosisDetector CSE Integration Tests

## Overview

This directory contains comprehensive tests for the GoogleCSE integration with DiagnosisDetector.

## Test Files

### `test_diagnosis_cse.py`

Complete test suite for CSE integration with 19 tests covering:

#### TestDiagnosisCseIntegration (9 tests)
- `test_cse_optional_loading`: Verifies lazy loading of CSE analyzer
- `test_cse_disabled_when_flag_false`: Tests CSE can be disabled via flag
- `test_graceful_degradation_without_cse`: Ensures diagnosis works without CSE
- `test_cse_initialization_failure_graceful`: Tests graceful handling of init failures
- `test_quota_check_before_cse_call`: Verifies quota checking before API calls
- `test_quota_too_low_skips_cse`: Tests CSE is skipped when quota is low
- `test_handles_cse_errors`: Tests error handling for CSE failures
- `test_handles_quota_check_errors`: Tests quota check error handling
- `test_domain_extraction_from_property`: Tests domain extraction from various property formats

#### TestCompetitorInsights (6 tests)
- `test_serp_context_enriches_diagnosis`: Verifies SERP data enriches diagnosis
- `test_competitor_insight_created`: Tests competitor data is included
- `test_serp_feature_insight_created`: Tests SERP feature detection
- `test_rich_snippet_competitor_detection`: Tests rich snippet identification
- `test_domain_not_found_in_serp`: Tests handling when domain not in SERP
- `test_no_top_query_skips_cse`: Tests CSE skipped when no query available

#### TestCseIntegrationEdgeCases (4 tests)
- `test_empty_competitors_list`: Tests empty competitor handling
- `test_missing_optional_fields`: Tests missing field handling
- `test_cse_timeout_handling`: Tests timeout error handling
- `test_multiple_serp_features`: Tests multiple SERP features

### `verify_diagnosis_cse_integration.py`

Standalone verification script that demonstrates:
- CSE availability check
- Initialization with CSE enabled/disabled
- Lazy loading behavior
- Graceful degradation
- Integration feature summary

## Running Tests

### Run All CSE Integration Tests
```bash
pytest tests/insights_core/test_diagnosis_cse.py -v
```

### Run Specific Test Class
```bash
pytest tests/insights_core/test_diagnosis_cse.py::TestDiagnosisCseIntegration -v
pytest tests/insights_core/test_diagnosis_cse.py::TestCompetitorInsights -v
pytest tests/insights_core/test_diagnosis_cse.py::TestCseIntegrationEdgeCases -v
```

### Run Specific Test
```bash
pytest tests/insights_core/test_diagnosis_cse.py::TestDiagnosisCseIntegration::test_quota_check_before_cse_call -v
```

### Run with Coverage
```bash
pytest tests/insights_core/test_diagnosis_cse.py --cov=insights_core.detectors.diagnosis --cov-report=term-missing
```

### Run Verification Script
```bash
python tests/insights_core/verify_diagnosis_cse_integration.py
```

## Test Coverage

The test suite covers:

✅ **Initialization**: CSE enabled, disabled, and error conditions
✅ **Lazy Loading**: Property-based lazy initialization
✅ **Quota Management**: Quota checking, low quota handling
✅ **Error Handling**: CSE errors, quota check errors, timeouts
✅ **SERP Data**: Position tracking, competitor analysis, SERP features
✅ **Edge Cases**: Empty data, missing fields, various property formats
✅ **Integration**: Works with existing diagnosis workflow

## Test Results

Expected output:
```
19 passed, 1 warning in ~2 seconds
```

All tests should pass. The warning is expected (pytest config timeout).

## Mocking Strategy

Tests use comprehensive mocking to avoid:
- Actual API calls to Google CSE
- Database connections
- External dependencies

Mocks include:
- `MockRepository`: For insight storage
- `MockConfig`: For configuration
- `MockCSEAnalyzer`: For CSE responses
- `MockDBConnection`: For database queries

## Test Data

Realistic test data includes:
- SERP positions (1-10)
- Competitor domains (realpython.com, tutorialspoint.com, etc.)
- SERP features (rich_snippets, thumbnails, breadcrumbs)
- Quota status (daily limit, remaining queries)
- Property formats (sc-domain:, sc-https://)

## Maintenance

When updating CSE integration:

1. **Add Tests**: Add tests for new features to appropriate test class
2. **Update Mocks**: Update mock data to reflect API changes
3. **Verify Coverage**: Ensure new code paths are tested
4. **Document Changes**: Update this README with new tests

## Related Documentation

- Main Implementation: `insights_core/detectors/diagnosis.py`
- CSE Analyzer: `services/serp_analyzer/google_cse.py`
- Implementation Doc: `docs/implementation/TASKCARD-040-CSE-INTEGRATION.md`
- Original Tests: `tests/insights_core/test_diagnosis_detector.py`
