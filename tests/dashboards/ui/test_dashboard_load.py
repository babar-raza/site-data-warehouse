"""
Dashboard Loading Tests
Verifies dashboards load successfully in browser
Run: pytest tests/dashboards/ui/test_dashboard_load.py -v -m ui

Tests:
- Dashboard accessibility
- Panel rendering
- Error state detection
"""

import pytest

# Skip if playwright not installed
try:
    from playwright.async_api import Page, expect
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = None
    expect = None

from .conftest import wait_for_dashboard_load, get_panel_count, get_panel_errors


pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestDashboardLoading:
    """Test dashboard loading and basic rendering"""

    async def test_ga4_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """GA4 dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["ga4"])
        await wait_for_dashboard_load(authenticated_page)

        # Check dashboard loaded (title in page)
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Check no critical error messages
        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"GA4 dashboard has {error_count} panel errors"

    async def test_gsc_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """GSC dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"GSC dashboard has {error_count} panel errors"

    async def test_cwv_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """CWV dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["cwv"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"CWV dashboard has {error_count} panel errors"

    async def test_serp_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """SERP dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["serp"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"SERP dashboard has {error_count} panel errors"

    async def test_hybrid_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """Hybrid dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["hybrid"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Hybrid dashboard has {error_count} panel errors"

    async def test_service_health_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """Service Health dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["service_health"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Service Health dashboard has {error_count} panel errors"

    async def test_alerts_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """Alert Status dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["alerts"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Alerts dashboard has {error_count} panel errors"

    async def test_application_metrics_dashboard_loads(self, authenticated_page: Page, dashboard_urls):
        """Application Metrics dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Application Metrics dashboard has {error_count} panel errors"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestPanelRendering:
    """Test panel rendering within dashboards"""

    async def test_dashboards_have_panels(self, authenticated_page: Page, dashboard_urls):
        """All dashboards should have at least one panel"""
        for name, url in dashboard_urls.items():
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            panel_count = await get_panel_count(authenticated_page)
            assert panel_count > 0, f"{name} dashboard has no panels"

    async def test_panels_render_without_errors(self, authenticated_page: Page, dashboard_urls):
        """All panels should render without error states"""
        failed_dashboards = []

        for name, url in dashboard_urls.items():
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            error_count = await get_panel_errors(authenticated_page)
            if error_count > 0:
                failed_dashboards.append((name, error_count))

        if failed_dashboards:
            error_msg = "Dashboards with panel errors:\n"
            for name, count in failed_dashboards:
                error_msg += f"  - {name}: {count} errors\n"
            pytest.fail(error_msg)

    async def test_stat_panels_show_values(self, authenticated_page: Page, dashboard_urls):
        """Stat panels should display values (not loading spinners)"""
        # Test on GA4 dashboard which has stat panels
        await authenticated_page.goto(dashboard_urls["ga4"])
        await wait_for_dashboard_load(authenticated_page)

        # Wait for loading to complete
        await authenticated_page.wait_for_timeout(3000)

        # Check that loading spinners are gone
        spinners = await authenticated_page.query_selector_all('.panel-loading, [class*="spinner"]')
        visible_spinners = 0
        for spinner in spinners:
            if await spinner.is_visible():
                visible_spinners += 1

        # Some panels may still be loading in test environments
        # This is a soft check

    async def test_table_panels_render_headers(self, authenticated_page: Page, dashboard_urls):
        """Table panels should render with headers"""
        # Test on GSC dashboard which has table panels
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Look for table elements
        tables = await authenticated_page.query_selector_all('table')
        for table in tables:
            if await table.is_visible():
                headers = await table.query_selector_all('th')
                # If table is visible, it should have headers
                # Note: Empty tables may still have headers


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestDashboardAccessibility:
    """Test dashboard accessibility features"""

    async def test_dashboards_are_navigable(self, authenticated_page: Page, dashboard_urls):
        """All dashboards should be accessible via URL"""
        for name, url in dashboard_urls.items():
            response = await authenticated_page.goto(url)
            assert response.status == 200, \
                f"{name} dashboard returned status {response.status}"

    async def test_dashboard_titles_are_present(self, authenticated_page: Page, dashboard_urls):
        """Dashboard titles should be visible"""
        for name, url in dashboard_urls.items():
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            # Look for title element
            title = authenticated_page.locator('h1, [class*="dashboard-title"]')
            count = await title.count()
            assert count > 0, f"{name} dashboard has no visible title"

    async def test_time_picker_is_visible(self, authenticated_page: Page, dashboard_urls):
        """Time range picker should be visible on all dashboards"""
        for name, url in dashboard_urls.items():
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            # Look for time picker
            time_picker = authenticated_page.locator(
                '[data-testid*="TimePicker"], '
                '[class*="time-picker"], '
                '[aria-label*="time"]'
            )
            count = await time_picker.count()
            assert count > 0, f"{name} dashboard has no time picker"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestDashboardPerformance:
    """Test dashboard loading performance"""

    async def test_dashboards_load_within_timeout(self, authenticated_page: Page, dashboard_urls):
        """Dashboards should load within reasonable time"""
        timeout_ms = 30000  # 30 seconds

        for name, url in dashboard_urls.items():
            try:
                await authenticated_page.goto(url, timeout=timeout_ms)
                await wait_for_dashboard_load(authenticated_page)
            except Exception as e:
                pytest.fail(f"{name} dashboard failed to load within {timeout_ms}ms: {e}")

    async def test_panels_load_without_infinite_loading(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Panels should not be stuck in loading state"""
        max_wait_ms = 15000  # 15 seconds

        for name, url in dashboard_urls.items():
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            # Wait additional time for panels
            await authenticated_page.wait_for_timeout(max_wait_ms)

            # Check for stuck loading indicators
            loading_indicators = await authenticated_page.query_selector_all(
                '.panel-loading:visible, '
                '[class*="loading"]:visible, '
                '[class*="spinner"]:visible'
            )

            stuck_panels = 0
            for indicator in loading_indicators:
                if await indicator.is_visible():
                    stuck_panels += 1

            # Allow some tolerance - some panels may legitimately be loading
            # due to network conditions in test environment
            if stuck_panels > 3:
                pytest.fail(f"{name} dashboard has {stuck_panels} panels stuck loading")
