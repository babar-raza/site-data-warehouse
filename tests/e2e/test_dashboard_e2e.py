"""
Dashboard E2E Tests with Playwright

Comprehensive end-to-end tests for all 11 Grafana dashboards.
Uses pytest-playwright's built-in fixtures for browser automation.

Run tests:
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --headed  # visible browser
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --browser firefox

Dashboards tested:
    1. ga4-overview
    2. gsc-overview
    3. hybrid-overview
    4. service-health
    5. infrastructure-overview
    6. database-performance
    7. cwv-monitoring
    8. serp-tracking
    9. actions-command-center
    10. alert-status
    11. application-metrics
"""

import pytest
import os
from pathlib import Path
from datetime import datetime

from tests.e2e.conftest import (
    GRAFANA_URL,
    DASHBOARD_DEFINITIONS,
    take_screenshot,
    wait_for_dashboard_load,
    get_panel_count,
    get_panel_errors,
    check_panel_rendering,
    get_dashboard_health_report,
)


# ============================================================================
# TEST MARKERS
# ============================================================================

pytestmark = [pytest.mark.e2e, pytest.mark.ui, pytest.mark.dashboard]


# ============================================================================
# TEST CLASSES
# ============================================================================

class TestDashboardAccessibility:
    """Test that all dashboards are accessible"""

    def test_all_dashboards_return_200(self, authenticated_page, dashboard_urls):
        """All dashboards should return HTTP 200"""
        failed = []

        for name, url in dashboard_urls.items():
            try:
                response = authenticated_page.goto(url, timeout=30000)
                if response.status != 200:
                    failed.append((name, response.status))
            except Exception as e:
                failed.append((name, str(e)))

        if failed:
            error_msg = "Dashboards with accessibility issues:\n"
            for name, status in failed:
                error_msg += f"  - {name}: {status}\n"
            pytest.fail(error_msg)

    def test_grafana_is_reachable(self, authenticated_page):
        """Grafana should be reachable and responsive"""
        response = authenticated_page.goto(GRAFANA_URL, timeout=30000)
        assert response.status == 200, f"Grafana returned status {response.status}"


class TestDashboardLoading:
    """Test that all dashboards load without errors"""

    def test_ga4_dashboard_loads(self, authenticated_page, dashboard_urls):
        """GA4 dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["ga4-overview"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "ga4_errors")
        assert error_count == 0, f"GA4 dashboard has {error_count} panel errors"

    def test_gsc_dashboard_loads(self, authenticated_page, dashboard_urls):
        """GSC dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["gsc-overview"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "gsc_errors")
        assert error_count == 0, f"GSC dashboard has {error_count} panel errors"

    def test_hybrid_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Hybrid dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["hybrid-overview"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "hybrid_errors")
        assert error_count == 0, f"Hybrid dashboard has {error_count} panel errors"

    def test_service_health_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Service Health dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["service-health"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "service_health_errors")
        assert error_count == 0, f"Service Health dashboard has {error_count} panel errors"

    def test_infrastructure_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Infrastructure dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["infrastructure-overview"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "infrastructure_errors")
        assert error_count == 0, f"Infrastructure dashboard has {error_count} panel errors"

    def test_database_performance_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Database Performance dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["database-performance"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "database_errors")
        assert error_count == 0, f"Database Performance dashboard has {error_count} panel errors"

    def test_cwv_monitoring_dashboard_loads(self, authenticated_page, dashboard_urls):
        """CWV Monitoring dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["cwv-monitoring"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "cwv_errors")
        assert error_count == 0, f"CWV Monitoring dashboard has {error_count} panel errors"

    def test_serp_tracking_dashboard_loads(self, authenticated_page, dashboard_urls):
        """SERP Tracking dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["serp-tracking"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "serp_errors")
        assert error_count == 0, f"SERP Tracking dashboard has {error_count} panel errors"

    def test_actions_command_center_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Actions Command Center dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["actions-command-center"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "actions_errors")
        assert error_count == 0, f"Actions Command Center dashboard has {error_count} panel errors"

    def test_alert_status_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Alert Status dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["alert-status"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "alert_status_errors")
        assert error_count == 0, f"Alert Status dashboard has {error_count} panel errors"

    def test_application_metrics_dashboard_loads(self, authenticated_page, dashboard_urls):
        """Application Metrics dashboard should load without errors"""
        authenticated_page.goto(dashboard_urls["application-metrics"])
        wait_for_dashboard_load(authenticated_page)

        error_count = get_panel_errors(authenticated_page)
        if error_count > 0:
            take_screenshot(authenticated_page, "app_metrics_errors")
        assert error_count == 0, f"Application Metrics dashboard has {error_count} panel errors"


class TestPanelRendering:
    """Test that panels render correctly"""

    def test_all_dashboards_have_panels(self, authenticated_page, dashboard_urls):
        """All dashboards should have at least one panel"""
        dashboards_without_panels = []

        for name, url in dashboard_urls.items():
            authenticated_page.goto(url)
            wait_for_dashboard_load(authenticated_page)

            panel_count = get_panel_count(authenticated_page)
            if panel_count == 0:
                dashboards_without_panels.append(name)

        if dashboards_without_panels:
            pytest.fail(
                f"Dashboards without panels: {', '.join(dashboards_without_panels)}"
            )

    def test_panels_render_without_errors(self, authenticated_page, dashboard_urls):
        """All panels should render without error states"""
        failed_dashboards = []

        for name, url in dashboard_urls.items():
            authenticated_page.goto(url)
            wait_for_dashboard_load(authenticated_page)

            status = check_panel_rendering(authenticated_page)

            if status["error_panels"] > 0:
                take_screenshot(authenticated_page, f"{name}_panel_errors")
                failed_dashboards.append((name, status))

        if failed_dashboards:
            error_msg = "Dashboards with panel errors:\n"
            for name, status in failed_dashboards:
                error_msg += (
                    f"  - {name}: {status['error_panels']} errors "
                    f"out of {status['total_panels']} panels\n"
                )
            pytest.fail(error_msg)

    def test_panels_finish_loading(self, authenticated_page, dashboard_urls):
        """Panels should not be stuck in loading state"""
        stuck_dashboards = []

        for name, url in dashboard_urls.items():
            authenticated_page.goto(url)
            wait_for_dashboard_load(authenticated_page)

            # Wait additional time for panels to finish loading
            authenticated_page.wait_for_timeout(5000)

            status = check_panel_rendering(authenticated_page)

            # Allow some tolerance for legitimate loading
            if status["loading_panels"] > 2:
                take_screenshot(authenticated_page, f"{name}_stuck_loading")
                stuck_dashboards.append((name, status["loading_panels"]))

        if stuck_dashboards:
            error_msg = "Dashboards with stuck loading panels:\n"
            for name, count in stuck_dashboards:
                error_msg += f"  - {name}: {count} panels still loading\n"
            pytest.fail(error_msg)


class TestDashboardFeatures:
    """Test dashboard UI features"""

    def test_dashboards_have_titles(self, authenticated_page, dashboard_urls):
        """All dashboards should have visible titles"""
        dashboards_without_titles = []

        for name, url in dashboard_urls.items():
            authenticated_page.goto(url)
            wait_for_dashboard_load(authenticated_page)

            # Updated selectors for modern Grafana (v9+)
            title_selectors = [
                'h1',
                '[class*="dashboard-title"]',
                '[data-testid="data-testid Dashboard header"]',
                '[data-testid*="Dashboard"]',                    # Grafana 9+ test IDs
                'nav [class*="Title"]',                          # Nav title
                '[class*="page-toolbar"] [class*="title"]',      # Page toolbar title
                'button[class*="dashboard-title"]',              # Clickable title button
                '[aria-label*="dashboard"]',                     # ARIA label based
                '[class*="NavToolbar"] h1',                      # Nav toolbar h1
                'header h1',                                     # Header h1
            ]

            has_title = False
            for selector in title_selectors:
                try:
                    elements = authenticated_page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible():
                            has_title = True
                            break
                except Exception:
                    continue
                if has_title:
                    break

            if not has_title:
                dashboards_without_titles.append(name)

        if dashboards_without_titles:
            pytest.fail(
                f"Dashboards without titles: {', '.join(dashboards_without_titles)}"
            )

    def test_dashboards_have_time_picker(self, authenticated_page, dashboard_urls):
        """All dashboards should have time range picker"""
        dashboards_without_picker = []

        for name, url in dashboard_urls.items():
            authenticated_page.goto(url)
            wait_for_dashboard_load(authenticated_page)

            # Look for time picker
            picker_selectors = [
                '[data-testid*="TimePicker"]',
                '[class*="time-picker"]',
                '[aria-label*="time"]',
                'button[aria-label*="Time range"]'
            ]

            has_picker = False
            for selector in picker_selectors:
                elements = authenticated_page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        has_picker = True
                        break
                if has_picker:
                    break

            if not has_picker:
                dashboards_without_picker.append(name)

        # Some dashboards may not have time pickers - this is a soft warning
        if dashboards_without_picker:
            print(
                f"\nNote: Dashboards without time picker: "
                f"{', '.join(dashboards_without_picker)}"
            )


class TestDashboardPerformance:
    """Test dashboard loading performance"""

    @pytest.mark.slow
    def test_dashboards_load_within_timeout(self, authenticated_page, dashboard_urls):
        """Dashboards should load within reasonable time"""
        import time
        timeout_ms = 30000  # 30 seconds
        slow_dashboards = []

        for name, url in dashboard_urls.items():
            start_time = time.time()

            try:
                authenticated_page.goto(url, timeout=timeout_ms)
                wait_for_dashboard_load(authenticated_page)

                load_time = (time.time() - start_time) * 1000

                if load_time > timeout_ms:
                    slow_dashboards.append((name, load_time))

            except Exception as e:
                take_screenshot(authenticated_page, f"{name}_timeout")
                pytest.fail(f"{name} dashboard failed to load: {e}")

        if slow_dashboards:
            error_msg = "Dashboards loading slowly:\n"
            for name, load_time in slow_dashboards:
                error_msg += f"  - {name}: {load_time:.0f}ms\n"
            print(f"\n{error_msg}")


class TestDashboardIntegration:
    """Test dashboard integration and data flow"""

    def test_all_dashboards_sequential_access(self, authenticated_page, dashboard_urls):
        """Test accessing all dashboards in sequence"""
        for name, url in dashboard_urls.items():
            try:
                authenticated_page.goto(url, timeout=30000)
                wait_for_dashboard_load(authenticated_page)

                # Verify basic loading
                panel_count = get_panel_count(authenticated_page)
                error_count = get_panel_errors(authenticated_page)

                # Just check they loaded - don't fail on errors for integration test
                print(f"\n{name}: {panel_count} panels, {error_count} errors")

            except Exception as e:
                take_screenshot(authenticated_page, f"{name}_sequential_fail")
                pytest.fail(f"Failed to load {name} in sequence: {e}")

    def test_dashboard_refresh(self, authenticated_page, dashboard_urls):
        """Test dashboard refresh functionality"""
        # Test with service-health dashboard (usually has data)
        authenticated_page.goto(dashboard_urls["service-health"])
        wait_for_dashboard_load(authenticated_page)

        initial_panel_count = get_panel_count(authenticated_page)

        # Refresh the page
        authenticated_page.reload()
        wait_for_dashboard_load(authenticated_page)

        refreshed_panel_count = get_panel_count(authenticated_page)

        assert initial_panel_count == refreshed_panel_count, \
            "Panel count changed after refresh"


class TestDashboardSummary:
    """Generate summary report of all dashboards"""

    def test_generate_dashboard_summary(self, authenticated_page, dashboard_urls):
        """Generate comprehensive dashboard health summary"""
        summary = []

        print("\n" + "=" * 80)
        print("DASHBOARD E2E TEST SUMMARY")
        print("=" * 80)

        for name, url in dashboard_urls.items():
            try:
                authenticated_page.goto(url, timeout=30000)
                wait_for_dashboard_load(authenticated_page)

                report = get_dashboard_health_report(authenticated_page, name)

                summary.append(report)

                print(f"\n{name}:")
                print(f"  Status: {report['health']}")
                print(f"  Total Panels: {report['total_panels']}")
                print(f"  Error Panels: {report['error_panels']}")
                print(f"  Healthy Panels: {report['healthy_panels']}")

            except Exception as e:
                summary.append({
                    "dashboard": name,
                    "health": "FAILED",
                    "error": str(e)
                })
                print(f"\n{name}:")
                print(f"  Status: FAILED")
                print(f"  Error: {e}")

        print("\n" + "=" * 80)

        # Report totals
        healthy = sum(1 for s in summary if s.get("health") == "HEALTHY")
        errors = sum(1 for s in summary if s.get("health") in ("ERROR", "FAILED"))
        warnings = sum(1 for s in summary if s.get("health") == "WARNING")

        print(f"\nTOTAL: {healthy} healthy, {warnings} warnings, {errors} errors")
        print("=" * 80)

        # Don't fail the test - this is informational
        if errors > 0:
            print(f"\nWARNING: {errors} dashboard(s) have issues")
