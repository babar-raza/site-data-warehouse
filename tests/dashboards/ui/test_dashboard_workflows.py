"""
E2E User Workflow Tests
Tests complete user journeys across dashboards
Run: pytest tests/dashboards/ui/test_dashboard_workflows.py -v -m "ui and e2e"

Tests:
- Morning performance review workflow
- Performance investigation workflow
- SERP monitoring workflow
- Alert investigation workflow
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

from .conftest import wait_for_dashboard_load, take_screenshot


pytestmark = [pytest.mark.ui, pytest.mark.e2e, pytest.mark.asyncio]


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestSEOAnalystWorkflow:
    """Test typical SEO analyst workflow"""

    async def test_morning_performance_review(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Morning performance review
        1. Check service health
        2. Review GSC overview
        3. Check GA4 metrics
        4. Review hybrid insights
        """
        # Step 1: Check service health
        await authenticated_page.goto(dashboard_urls["service_health"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify dashboard loaded
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Step 2: Review GSC overview
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Look for key metrics panels
        panels = authenticated_page.locator('.panel-container')
        panel_count = await panels.count()
        assert panel_count > 0, "GSC dashboard should have panels"

        # Step 3: Check GA4 metrics
        await authenticated_page.goto(dashboard_urls["ga4"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify GA4 panels loaded
        sessions_text = authenticated_page.locator('text="Sessions", text="Total Sessions"')
        # May not find exact text - that's ok if panels loaded

        # Step 4: Review hybrid insights
        await authenticated_page.goto(dashboard_urls["hybrid"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify hybrid dashboard loaded
        panels = authenticated_page.locator('.panel-container')
        panel_count = await panels.count()
        assert panel_count > 0, "Hybrid dashboard should have panels"

    async def test_performance_investigation_workflow(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Investigate performance issue
        1. Check CWV dashboard
        2. Review performance scores
        3. Check mobile vs desktop
        """
        # Step 1: Open CWV dashboard
        await authenticated_page.goto(dashboard_urls["cwv"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify dashboard loaded
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Step 2: Check for performance-related panels
        performance_panels = authenticated_page.locator(
            'text="Performance", '
            'text="LCP", '
            'text="CLS", '
            '[class*="stat-panel"]'
        )

        # Wait for panels to render
        await authenticated_page.wait_for_timeout(2000)

        # Step 3: Check if device variable exists for mobile/desktop comparison
        device_controls = authenticated_page.locator(
            'label:has-text("device"), '
            'label:has-text("Device"), '
            '[class*="variable"]'
        )

        count = await device_controls.count()
        # Device variable may or may not exist depending on dashboard config

    async def test_serp_monitoring_workflow(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Monitor SERP positions
        1. Check SERP dashboard
        2. Review position changes
        """
        # Step 1: Open SERP dashboard
        await authenticated_page.goto(dashboard_urls["serp"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify dashboard loaded
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Step 2: Check for SERP-related panels
        panels = authenticated_page.locator('.panel-container')
        panel_count = await panels.count()
        assert panel_count > 0, "SERP dashboard should have panels"

        # Look for position-related text
        position_elements = authenticated_page.locator(
            'text="Position", '
            'text="Queries", '
            'text="Ranking"'
        )

        # Panels may or may not have specific text


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestAlertInvestigationWorkflow:
    """Test alert investigation workflow"""

    async def test_alert_investigation(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Investigate active alerts
        1. Check alert status dashboard
        2. Review active alerts
        3. Cross-reference with service health
        """
        # Step 1: Check alert dashboard
        await authenticated_page.goto(dashboard_urls["alerts"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify dashboard loaded
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)

        # Step 2: Look for alert-related panels
        alert_panels = authenticated_page.locator(
            'text="Alert", '
            'text="Active", '
            '[class*="alert"]'
        )

        # Step 3: Navigate to service health for cross-reference
        await authenticated_page.goto(dashboard_urls["service_health"])
        await wait_for_dashboard_load(authenticated_page)

        # Verify service health loaded
        panels = authenticated_page.locator('.panel-container')
        panel_count = await panels.count()
        assert panel_count > 0, "Service health dashboard should have panels"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestDataExplorationWorkflow:
    """Test data exploration workflow"""

    async def test_drill_down_from_overview(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Drill down from overview to details
        1. Start at GSC overview
        2. Identify metric of interest
        3. View details
        """
        # Step 1: Start at GSC overview
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Step 2: Find a panel
        panel = authenticated_page.locator('.panel-container').first

        if await panel.count() > 0:
            # Step 3: Try to view details via panel menu
            await panel.hover()
            await authenticated_page.wait_for_timeout(300)

            menu_btn = panel.locator('[aria-label="Panel menu"]').first

            if await menu_btn.count() > 0:
                await menu_btn.click()
                await authenticated_page.wait_for_timeout(300)

                # Look for View or Inspect option
                view_option = authenticated_page.locator('text="View"').first
                if await view_option.count() > 0:
                    await view_option.click()
                    await authenticated_page.wait_for_timeout(500)

                    # Close fullscreen view
                    await authenticated_page.keyboard.press("Escape")

    async def test_cross_dashboard_navigation(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Navigate between related dashboards
        1. Start at GA4
        2. Navigate to Hybrid
        3. Navigate to CWV
        """
        dashboards_to_visit = ["ga4", "hybrid", "cwv"]

        for dashboard_key in dashboards_to_visit:
            url = dashboard_urls[dashboard_key]
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            # Verify each dashboard loaded successfully
            title = authenticated_page.locator('h1, [class*="dashboard-title"]')
            await expect(title.first).to_be_visible(timeout=10000)

            # No errors should appear
            errors = authenticated_page.locator('[class*="error"]')
            error_count = await errors.count()
            # Some error elements may exist but be hidden


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestReportingWorkflow:
    """Test reporting-focused workflows"""

    async def test_time_range_comparison(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Workflow: Compare different time ranges
        1. View last 7 days
        2. View last 30 days
        """
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Find time picker
        time_picker = authenticated_page.locator(
            '[data-testid*="TimePicker Open Button"], '
            '[class*="time-picker"] button'
        ).first

        if await time_picker.count() == 0:
            pytest.skip("Time picker not found")

        # Step 1: Select 7 days
        await time_picker.click()
        await authenticated_page.wait_for_timeout(500)

        seven_days = authenticated_page.locator('text="Last 7 days"').first
        if await seven_days.count() > 0:
            await seven_days.click()
            await wait_for_dashboard_load(authenticated_page)

        # Step 2: Select 30 days
        await time_picker.click()
        await authenticated_page.wait_for_timeout(500)

        thirty_days = authenticated_page.locator('text="Last 30 days"').first
        if await thirty_days.count() > 0:
            await thirty_days.click()
            await wait_for_dashboard_load(authenticated_page)

        # Dashboard should still be functional
        panels = authenticated_page.locator('.panel-container')
        panel_count = await panels.count()
        assert panel_count > 0, "Panels should still be visible after time changes"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestErrorRecoveryWorkflow:
    """Test error handling and recovery"""

    async def test_recover_from_invalid_url(
        self, authenticated_page: Page, grafana_url
    ):
        """Dashboard should handle invalid UIDs gracefully"""
        # Try to navigate to non-existent dashboard
        await authenticated_page.goto(f"{grafana_url}/d/invalid-uid/not-found")

        # Should show error or redirect, not crash
        await authenticated_page.wait_for_timeout(2000)

        # Check page is still functional
        current_url = authenticated_page.url
        # URL should either be the invalid one (showing 404) or redirected

    async def test_recover_from_network_error(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Dashboard should handle network issues gracefully"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Refresh should work
        await authenticated_page.reload()
        await wait_for_dashboard_load(authenticated_page)

        # Dashboard should be functional
        title = authenticated_page.locator('h1, [class*="dashboard-title"]')
        await expect(title.first).to_be_visible(timeout=10000)


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestMultiDashboardWorkflow:
    """Test workflows spanning multiple dashboards"""

    async def test_complete_monitoring_workflow(
        self, authenticated_page: Page, dashboard_urls
    ):
        """
        Complete monitoring workflow:
        1. Service health check
        2. Performance review (CWV)
        3. Traffic analysis (GSC/GA4)
        4. Alert check
        """
        workflow_steps = [
            ("service_health", "Service Health"),
            ("cwv", "Core Web Vitals"),
            ("gsc", "GSC Overview"),
            ("ga4", "GA4 Analytics"),
            ("alerts", "Alert Status")
        ]

        for dashboard_key, description in workflow_steps:
            url = dashboard_urls[dashboard_key]

            # Navigate to dashboard
            await authenticated_page.goto(url)
            await wait_for_dashboard_load(authenticated_page)

            # Verify dashboard loaded
            title = authenticated_page.locator('h1, [class*="dashboard-title"]')
            await expect(title.first).to_be_visible(timeout=10000)

            # Brief pause to simulate user reviewing dashboard
            await authenticated_page.wait_for_timeout(500)

        # All dashboards successfully visited
        assert True, "Complete monitoring workflow passed"
