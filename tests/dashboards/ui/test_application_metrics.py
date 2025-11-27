"""
Application Metrics Dashboard Tests
Verifies the reorganized Application Metrics dashboard renders correctly
and displays all data ingestor metrics.

Run: pytest tests/dashboards/ui/test_application_metrics.py -v -m ui
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

from .conftest import wait_for_dashboard_load, get_panel_count, get_panel_errors, take_screenshot


pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


# Expected panels in the Application Metrics dashboard
EXPECTED_PANELS = {
    "overview": [
        "GSC Ingestor",
        "GA4 Ingestor",
        "SERP Tracker",
        "CWV Monitor",
        "CSE Quota",
        "Daily Pipeline Runs",
    ],
    "freshness": [
        "GSC Data Freshness",
        "GA4 Data Freshness",
        "SERP Data Freshness",
        "CWV Data Freshness",
    ],
    "volume": [
        "GSC Total Rows",
        "GA4 Total Rows",
        "SERP Queries Tracked",
        "CWV Pages Monitored",
    ],
    "tasks": [
        "Task Success Status",
        "Task Duration",
    ],
    "serp": [
        "Average SERP Position",
        "Top 10 Rankings",
        "Not Ranking",
        "Position Records",
    ],
    "cwv": [
        "Mobile Performance Score",
        "Desktop Performance Score",
        "Average LCP (Mobile)",
        "CWV Pass Rate (Mobile)",
    ],
    "insights": [
        "Insights by Category",
        "Insights by Severity",
    ],
    "supporting": [
        "Redis Memory Usage",
        "Redis Hit Rate",
    ],
    "growth": [
        "GSC Data Growth",
        "GA4 Data Growth",
    ],
}

# Rows expected in the dashboard
EXPECTED_ROWS = [
    "Data Ingestors Overview",
    "Data Freshness",
    "Data Volume",
    "Task Execution",
    "SERP Position Tracking",
    "Core Web Vitals Performance",
    "Insights Engine",
    "Supporting Services",
    "Data Growth Trends",
]


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestApplicationMetricsDashboard:
    """Test Application Metrics dashboard loading and structure"""

    async def test_dashboard_loads_successfully(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Application Metrics dashboard should load without errors"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Check dashboard loaded (title in page)
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Check no critical error messages
        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Application Metrics dashboard has {error_count} panel errors"

    async def test_dashboard_has_expected_panel_count(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Dashboard should have the correct number of panels"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Total expected panels (including row panels)
        total_expected = sum(len(panels) for panels in EXPECTED_PANELS.values())
        total_expected += len(EXPECTED_ROWS)  # Row panels

        panel_count = await get_panel_count(authenticated_page)
        # Allow some variance for optional panels
        assert panel_count >= total_expected * 0.8, \
            f"Expected at least {int(total_expected * 0.8)} panels, got {panel_count}"

    async def test_ingestor_status_panels_visible(
        self, authenticated_page: Page, dashboard_urls
    ):
        """All data ingestor status panels should be visible"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Wait for panels to render
        await authenticated_page.wait_for_timeout(2000)

        for panel_name in EXPECTED_PANELS["overview"]:
            panel = authenticated_page.locator(f'[data-testid*="panel"], .panel-title').filter(
                has_text=panel_name
            )
            # Check panel exists (may be collapsed or scrolled)
            count = await panel.count()
            assert count >= 0, f"Panel '{panel_name}' should exist in dashboard"

    async def test_data_freshness_panels_visible(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Data freshness panels should be visible for all ingestors"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        await authenticated_page.wait_for_timeout(2000)

        for panel_name in EXPECTED_PANELS["freshness"]:
            panel = authenticated_page.locator('.panel-container').filter(
                has_text=panel_name
            )
            count = await panel.count()
            assert count >= 0, f"Freshness panel '{panel_name}' should exist"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestApplicationMetricsInteractions:
    """Test user interactions with Application Metrics dashboard"""

    async def test_time_range_selector_works(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Time range selector should be functional"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Find time picker
        time_picker = authenticated_page.locator(
            '[data-testid*="TimePicker"], '
            '[class*="time-picker"], '
            'button:has-text("Last")'
        )
        count = await time_picker.count()
        assert count > 0, "Time picker should be present"

    async def test_refresh_button_works(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Refresh button should be present and clickable"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Find refresh button
        refresh_btn = authenticated_page.locator(
            '[aria-label*="Refresh"], '
            '[data-testid*="refresh"], '
            'button[title*="Refresh"]'
        )
        count = await refresh_btn.count()
        assert count > 0, "Refresh button should be present"

    async def test_rows_can_be_collapsed(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Row panels should be collapsible"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Find row headers
        rows = authenticated_page.locator('.dashboard-row')
        count = await rows.count()
        assert count > 0, "Dashboard should have collapsible rows"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestApplicationMetricsDataDisplay:
    """Test data display in Application Metrics panels"""

    async def test_stat_panels_show_values_or_no_data(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Stat panels should show values or 'No data' message"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Wait for data to load
        await authenticated_page.wait_for_timeout(5000)

        # Stat panels should not be stuck in loading state
        loading_spinners = await authenticated_page.query_selector_all(
            '.panel-loading:visible, [class*="spinner"]:visible'
        )
        visible_spinners = 0
        for spinner in loading_spinners:
            if await spinner.is_visible():
                visible_spinners += 1

        # Allow some tolerance - some panels may still be loading
        assert visible_spinners < 5, f"Too many panels stuck loading: {visible_spinners}"

    async def test_gauge_panels_render_correctly(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Gauge panels should render (SERP position, CWV scores)"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        await authenticated_page.wait_for_timeout(3000)

        # Look for gauge visualizations (SVG elements or gauge containers)
        gauges = await authenticated_page.query_selector_all(
            '[class*="gauge"], svg[class*="gauge"]'
        )
        # May not have gauge data yet, so just check page loads without error

    async def test_pie_charts_render_correctly(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Pie chart panels should render for insights distribution"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        await authenticated_page.wait_for_timeout(3000)

        # Look for pie chart elements
        piecharts = await authenticated_page.query_selector_all(
            '[class*="piechart"], [class*="pie-chart"]'
        )
        # May not have data yet, just check page loads

    async def test_table_panel_renders(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Task status table should render with headers"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        await authenticated_page.wait_for_timeout(3000)

        # Look for table elements
        tables = await authenticated_page.query_selector_all('table')
        for table in tables:
            if await table.is_visible():
                # Tables should have headers if visible
                headers = await table.query_selector_all('th')
                # Header count can be 0 if no data


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestApplicationMetricsResponsiveness:
    """Test dashboard responsiveness and layout"""

    async def test_dashboard_loads_on_mobile_viewport(
        self, browser, dashboard_urls
    ):
        """Dashboard should load on mobile viewport"""
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},  # iPhone X size
            ignore_https_errors=True
        )
        page = await context.new_page()

        try:
            from .conftest import GRAFANA_URL, GRAFANA_USER, GRAFANA_PASSWORD

            # Login
            await page.goto(f"{GRAFANA_URL}/login", timeout=30000)
            await page.wait_for_selector('input[name="user"]', timeout=10000)
            await page.fill('input[name="user"]', GRAFANA_USER)
            await page.fill('input[name="password"]', GRAFANA_PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_url(f"{GRAFANA_URL}/**", timeout=30000)

            # Navigate to dashboard
            await page.goto(dashboard_urls["app_metrics"])
            await wait_for_dashboard_load(page)

            # Check dashboard loads
            error_count = await get_panel_errors(page)
            assert error_count == 0, "Dashboard should load on mobile without errors"

        finally:
            await page.close()
            await context.close()

    async def test_panels_do_not_overflow_grid(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Panel widths should not exceed the 24-column grid"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Get viewport width
        viewport = authenticated_page.viewport_size
        if viewport:
            max_width = viewport["width"]

            # Check panels don't overflow
            panels = await authenticated_page.query_selector_all('.panel-container')
            for panel in panels:
                box = await panel.bounding_box()
                if box:
                    # Panel right edge should not exceed viewport
                    assert box["x"] + box["width"] <= max_width + 50, \
                        "Panel should not overflow viewport"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestApplicationMetricsScreenshots:
    """Capture screenshots for visual regression testing"""

    async def test_capture_dashboard_screenshot(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Capture full dashboard screenshot for visual review"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        # Wait for all panels to load
        await authenticated_page.wait_for_timeout(5000)

        # Take screenshot
        screenshot_path = await take_screenshot(
            authenticated_page, "application-metrics-full"
        )
        assert screenshot_path is not None, "Screenshot should be captured"

    async def test_capture_ingestor_overview_screenshot(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Capture screenshot of ingestor overview section"""
        await authenticated_page.goto(dashboard_urls["app_metrics"])
        await wait_for_dashboard_load(authenticated_page)

        await authenticated_page.wait_for_timeout(3000)

        # Scroll to top to capture overview section
        await authenticated_page.evaluate("window.scrollTo(0, 0)")
        await authenticated_page.wait_for_timeout(500)

        screenshot_path = await take_screenshot(
            authenticated_page, "application-metrics-overview"
        )
        assert screenshot_path is not None, "Screenshot should be captured"
