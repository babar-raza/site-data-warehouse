"""
Dashboard test module for Grafana dashboard validation.

This module contains tests for:
- Dashboard JSON schema validation
- SQL query validation (mock and live)
- Data availability testing
- UI integration tests with Playwright
- E2E user workflow tests

Usage:
    # Run all mock tests (fast, no database required)
    pytest tests/dashboards/ -v

    # Run live tests (requires database)
    TEST_MODE=live pytest tests/dashboards/test_dashboard_queries_live.py -v

    # Run UI tests (requires full stack)
    pytest tests/dashboards/ui/ -v -m ui
"""
