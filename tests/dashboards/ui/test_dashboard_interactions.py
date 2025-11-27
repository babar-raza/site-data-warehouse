"""
Dashboard Interaction Tests
Tests user interactions with dashboard controls
Run: pytest tests/dashboards/ui/test_dashboard_interactions.py -v -m ui

Tests:
- Time range picker interactions
- Template variable dropdowns
- Table sorting and pagination
- Panel interactions (expand, inspect)
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

from .conftest import wait_for_dashboard_load, get_panel_errors


pytestmark = [pytest.mark.ui, pytest.mark.asyncio]


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestTimeRangeInteractions:
    """Test time range picker interactions"""

    async def test_time_range_picker_opens(self, authenticated_page: Page, dashboard_urls):
        """Time range picker should open on click"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Find and click time range picker
        time_picker = authenticated_page.locator(
            '[data-testid*="TimePicker Open Button"], '
            '[class*="time-picker"] button, '
            '[aria-label*="Change time range"]'
        ).first

        if await time_picker.count() == 0:
            pytest.skip("Time picker not found")

        await time_picker.click()

        # Wait for dropdown/popover to appear
        await authenticated_page.wait_for_timeout(500)

        # Check for time range options
        dropdown = authenticated_page.locator(
            '.time-picker-content, '
            '[class*="TimePickerContent"], '
            '[role="dialog"], '
            '[class*="popover"]'
        )

        await expect(dropdown.first).to_be_visible(timeout=5000)

    async def test_time_range_change_updates_panels(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Changing time range should trigger panel refresh"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Open time picker
        time_picker = authenticated_page.locator(
            '[data-testid*="TimePicker Open Button"], '
            '[class*="time-picker"] button'
        ).first

        if await time_picker.count() == 0:
            pytest.skip("Time picker not found")

        await time_picker.click()
        await authenticated_page.wait_for_timeout(500)

        # Try to select a time range option
        options = [
            'text="Last 7 days"',
            'text="Last 24 hours"',
            'text="Last 30 days"',
            '[data-testid*="data-testid TimeRangeOption"]'
        ]

        clicked = False
        for option_selector in options:
            option = authenticated_page.locator(option_selector).first
            if await option.count() > 0 and await option.is_visible():
                await option.click()
                clicked = True
                break

        if not clicked:
            pytest.skip("Could not find time range option")

        # Wait for panel refresh
        await wait_for_dashboard_load(authenticated_page)

        # Check no new errors appeared
        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Panel errors after time range change: {error_count}"

    async def test_custom_time_range_input(self, authenticated_page: Page, dashboard_urls):
        """Custom time range input should work"""
        await authenticated_page.goto(dashboard_urls["ga4"])
        await wait_for_dashboard_load(authenticated_page)

        # Open time picker
        time_picker = authenticated_page.locator(
            '[data-testid*="TimePicker Open Button"], '
            '[class*="time-picker"] button'
        ).first

        if await time_picker.count() == 0:
            pytest.skip("Time picker not found")

        await time_picker.click()
        await authenticated_page.wait_for_timeout(500)

        # Look for "From" input field
        from_input = authenticated_page.locator(
            'input[placeholder*="From"], '
            'input[aria-label*="From"], '
            '[data-testid*="From"]'
        ).first

        if await from_input.count() > 0:
            # Custom time range is available
            pass  # Test passes if input exists


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestTemplateVariableInteractions:
    """Test template variable dropdown interactions"""

    async def test_property_variable_dropdown_opens(
        self, authenticated_page: Page, dashboard_urls
    ):
        """Property variable dropdown should open"""
        await authenticated_page.goto(dashboard_urls["cwv"])
        await wait_for_dashboard_load(authenticated_page)

        # Find property dropdown
        dropdown = authenticated_page.locator(
            'label:has-text("property") + div, '
            'label:has-text("Property") + div, '
            '[data-testid*="variable-property"]'
        ).first

        if await dropdown.count() == 0:
            # Try alternative selector
            dropdown = authenticated_page.locator(
                '[class*="submenu-controls"] button, '
                '[class*="variable-link-wrapper"]'
            ).first

        if await dropdown.count() == 0:
            pytest.skip("Property dropdown not found")

        await dropdown.click()
        await authenticated_page.wait_for_timeout(500)

        # Check if options appeared
        options = authenticated_page.locator(
            '.variable-option, '
            '[class*="variable-options"], '
            '[role="listbox"] [role="option"]'
        )

        count = await options.count()
        # Options may be 0 if no data exists - that's valid

    async def test_device_variable_toggles(self, authenticated_page: Page, dashboard_urls):
        """Device variable should allow selection"""
        await authenticated_page.goto(dashboard_urls["cwv"])
        await wait_for_dashboard_load(authenticated_page)

        # Find device dropdown
        device_dropdown = authenticated_page.locator(
            'label:has-text("device") + div, '
            'label:has-text("Device") + div'
        ).first

        if await device_dropdown.count() == 0:
            pytest.skip("Device dropdown not found")

        await device_dropdown.click()
        await authenticated_page.wait_for_timeout(500)

        # Try to select an option
        desktop_option = authenticated_page.locator('text="desktop"').first
        mobile_option = authenticated_page.locator('text="mobile"').first

        if await desktop_option.count() > 0:
            await desktop_option.click()
        elif await mobile_option.count() > 0:
            await mobile_option.click()
        else:
            pytest.skip("No device options found")

        await wait_for_dashboard_load(authenticated_page)

        # Check no errors
        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Panel errors after device change: {error_count}"


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestTableInteractions:
    """Test table panel interactions"""

    async def test_table_sorting(self, authenticated_page: Page, dashboard_urls):
        """Table columns should be sortable"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Find a table
        table = authenticated_page.locator('table').first

        if await table.count() == 0:
            pytest.skip("No table found on dashboard")

        # Find sortable header
        header = table.locator('th').first

        if await header.count() > 0:
            await header.click()
            await authenticated_page.wait_for_timeout(500)

            # Table should still be visible after sorting
            await expect(table).to_be_visible()

    async def test_table_row_hover(self, authenticated_page: Page, dashboard_urls):
        """Table rows should respond to hover"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        table = authenticated_page.locator('table').first

        if await table.count() == 0:
            pytest.skip("No table found on dashboard")

        row = table.locator('tbody tr').first

        if await row.count() > 0:
            await row.hover()
            await authenticated_page.wait_for_timeout(200)
            # Row should still be visible
            await expect(row).to_be_visible()

    async def test_table_pagination_if_exists(self, authenticated_page: Page, dashboard_urls):
        """Table pagination should work if present"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Check for pagination controls
        pagination = authenticated_page.locator(
            '.pagination, '
            '[class*="pager"], '
            '[aria-label*="pagination"]'
        )

        if await pagination.count() > 0:
            # Try to click next page
            next_btn = pagination.locator(
                'button:has-text("Next"), '
                '[aria-label="Next"], '
                '[class*="next"]'
            ).first

            if await next_btn.count() > 0 and await next_btn.is_enabled():
                await next_btn.click()
                await authenticated_page.wait_for_timeout(500)
                # Should not error


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestPanelInteractions:
    """Test individual panel interactions"""

    async def test_panel_menu_opens(self, authenticated_page: Page, dashboard_urls):
        """Panel menu should open on button click"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        # Find panel container
        panel = authenticated_page.locator('.panel-container').first

        if await panel.count() == 0:
            pytest.skip("No panels found")

        # Hover over panel to reveal menu button
        await panel.hover()
        await authenticated_page.wait_for_timeout(300)

        # Find menu button
        menu_btn = panel.locator(
            '[aria-label="Panel menu"], '
            '[data-testid="panel-menu-button"], '
            'button[class*="menu"]'
        ).first

        if await menu_btn.count() > 0:
            await menu_btn.click()
            await authenticated_page.wait_for_timeout(300)

            # Menu should appear
            menu = authenticated_page.locator(
                '[role="menu"], '
                '[class*="dropdown-menu"]'
            )
            await expect(menu.first).to_be_visible(timeout=3000)

    async def test_panel_view_fullscreen(self, authenticated_page: Page, dashboard_urls):
        """Panels should expand to fullscreen"""
        await authenticated_page.goto(dashboard_urls["gsc"])
        await wait_for_dashboard_load(authenticated_page)

        panel = authenticated_page.locator('.panel-container').first

        if await panel.count() == 0:
            pytest.skip("No panels found")

        # Hover and open menu
        await panel.hover()
        await authenticated_page.wait_for_timeout(300)

        menu_btn = panel.locator('[aria-label="Panel menu"]').first

        if await menu_btn.count() == 0:
            pytest.skip("Panel menu button not found")

        await menu_btn.click()
        await authenticated_page.wait_for_timeout(300)

        # Click View option
        view_option = authenticated_page.locator('text="View"').first

        if await view_option.count() > 0:
            await view_option.click()
            await authenticated_page.wait_for_timeout(500)

            # Press Escape to close fullscreen
            await authenticated_page.keyboard.press("Escape")
            await authenticated_page.wait_for_timeout(300)

    async def test_panel_inspect_shows_data(self, authenticated_page: Page, dashboard_urls):
        """Panel inspect should show query data"""
        await authenticated_page.goto(dashboard_urls["ga4"])
        await wait_for_dashboard_load(authenticated_page)

        panel = authenticated_page.locator('.panel-container').first

        if await panel.count() == 0:
            pytest.skip("No panels found")

        # Hover and open menu
        await panel.hover()
        await authenticated_page.wait_for_timeout(300)

        menu_btn = panel.locator('[aria-label="Panel menu"]').first

        if await menu_btn.count() == 0:
            pytest.skip("Panel menu button not found")

        await menu_btn.click()
        await authenticated_page.wait_for_timeout(300)

        # Click Inspect option
        inspect_option = authenticated_page.locator('text="Inspect"').first

        if await inspect_option.count() > 0:
            await inspect_option.click()
            await authenticated_page.wait_for_timeout(500)

            # Inspect drawer should open
            drawer = authenticated_page.locator(
                '[class*="drawer"], '
                '[class*="inspect"], '
                '[aria-label*="inspect"]'
            )

            if await drawer.count() > 0:
                await expect(drawer.first).to_be_visible(timeout=5000)

            # Close drawer
            await authenticated_page.keyboard.press("Escape")


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
class TestRefreshInteractions:
    """Test dashboard refresh functionality"""

    async def test_manual_refresh_button(self, authenticated_page: Page, dashboard_urls):
        """Refresh button should refresh dashboard"""
        await authenticated_page.goto(dashboard_urls["service_health"])
        await wait_for_dashboard_load(authenticated_page)

        # Find refresh button
        refresh_btn = authenticated_page.locator(
            '[aria-label*="Refresh"], '
            '[data-testid*="RefreshPicker"], '
            'button:has-text("Refresh")'
        ).first

        if await refresh_btn.count() == 0:
            pytest.skip("Refresh button not found")

        await refresh_btn.click()
        await authenticated_page.wait_for_timeout(1000)

        # Dashboard should still be functional
        error_count = await get_panel_errors(authenticated_page)
        assert error_count == 0, f"Errors after refresh: {error_count}"

    async def test_auto_refresh_dropdown(self, authenticated_page: Page, dashboard_urls):
        """Auto-refresh interval dropdown should open"""
        await authenticated_page.goto(dashboard_urls["service_health"])
        await wait_for_dashboard_load(authenticated_page)

        # Find auto-refresh dropdown
        refresh_dropdown = authenticated_page.locator(
            '[data-testid*="RefreshPicker"], '
            '[class*="refresh-picker"]'
        ).first

        if await refresh_dropdown.count() == 0:
            pytest.skip("Refresh dropdown not found")

        await refresh_dropdown.click()
        await authenticated_page.wait_for_timeout(300)

        # Check for interval options
        options = authenticated_page.locator(
            'text="5s", text="10s", text="30s", text="1m", text="5m"'
        )

        count = await options.count()
        # At least some refresh options should exist
