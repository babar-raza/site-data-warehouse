"""Playwright fixtures for UI testing"""

import pytest
import os
from typing import Dict

# Skip if playwright not installed
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    async_playwright = None
    Browser = None
    Page = None
    BrowserContext = None


# Configuration from environment
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")


def pytest_configure(config):
    """Configure pytest for UI tests"""
    config.addinivalue_line(
        "markers",
        "ui: mark test as requiring browser/UI (Playwright)"
    )
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end workflow test"
    )


@pytest.fixture(scope="session")
def browser_type():
    """Browser type to use for testing"""
    return os.getenv("BROWSER_TYPE", "chromium")


@pytest.fixture(scope="session")
def headless():
    """Whether to run browser in headless mode"""
    return os.getenv("HEADLESS", "true").lower() == "true"


@pytest.fixture(scope="session")
async def browser(browser_type, headless):
    """Launch browser for UI tests"""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")

    async with async_playwright() as p:
        browser_launcher = getattr(p, browser_type)
        browser = await browser_launcher.launch(headless=headless)
        yield browser
        await browser.close()


@pytest.fixture(scope="function")
async def context(browser: Browser):
    """Create new browser context for each test"""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True
    )
    yield context
    await context.close()


@pytest.fixture(scope="function")
async def page(context: BrowserContext) -> Page:
    """Create new page for each test"""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")

    page = await context.new_page()
    yield page
    await page.close()


@pytest.fixture(scope="function")
async def authenticated_page(context: BrowserContext) -> Page:
    """Create authenticated Grafana page"""
    if not HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")

    page = await context.new_page()

    try:
        # Navigate to login
        await page.goto(f"{GRAFANA_URL}/login", timeout=30000)

        # Wait for login form
        await page.wait_for_selector('input[name="user"]', timeout=10000)

        # Fill credentials
        await page.fill('input[name="user"]', GRAFANA_USER)
        await page.fill('input[name="password"]', GRAFANA_PASSWORD)

        # Submit login form
        await page.click('button[type="submit"]')

        # Wait for navigation away from login page
        await page.wait_for_url(f"{GRAFANA_URL}/**", timeout=30000)

        yield page

    except Exception as e:
        pytest.skip(f"Could not authenticate with Grafana: {e}")
    finally:
        await page.close()


@pytest.fixture
def dashboard_urls() -> Dict[str, str]:
    """Dashboard URLs for testing"""
    return {
        "ga4": f"{GRAFANA_URL}/d/ga4-overview/ga4-analytics-overview",
        "gsc": f"{GRAFANA_URL}/d/gsc-overview/gsc-data-overview",
        "cwv": f"{GRAFANA_URL}/d/cwv-monitoring/core-web-vitals-monitoring",
        "serp": f"{GRAFANA_URL}/d/serp-tracking/serp-position-tracking",
        "hybrid": f"{GRAFANA_URL}/d/hybrid-overview/hybrid-analytics-gsc-ga4-unified",
        "service_health": f"{GRAFANA_URL}/d/service-health/service-health",
        "alerts": f"{GRAFANA_URL}/d/alert-status/alert-status",
        "app_metrics": f"{GRAFANA_URL}/d/application-metrics/application-metrics",
        "db_performance": f"{GRAFANA_URL}/d/database-performance/database-performance",
        "infrastructure": f"{GRAFANA_URL}/d/infrastructure-overview/infrastructure-overview"
    }


@pytest.fixture
def grafana_url() -> str:
    """Base Grafana URL"""
    return GRAFANA_URL


async def wait_for_dashboard_load(page: Page, timeout: int = 30000):
    """
    Wait for dashboard to fully load.

    Args:
        page: Playwright page object
        timeout: Maximum wait time in milliseconds
    """
    # Wait for network to be idle
    await page.wait_for_load_state("networkidle", timeout=timeout)

    # Wait for panels to render (look for panel containers)
    try:
        await page.wait_for_selector('.panel-container', timeout=10000)
    except Exception:
        # Some dashboards may not have panels yet
        pass

    # Additional wait for dynamic content
    await page.wait_for_timeout(1000)


async def get_panel_count(page: Page) -> int:
    """
    Count visible panels on dashboard.

    Args:
        page: Playwright page object

    Returns:
        Number of visible panels
    """
    panels = await page.query_selector_all('.panel-container')
    return len(panels)


async def get_panel_errors(page: Page) -> int:
    """
    Count panels with errors.

    Args:
        page: Playwright page object

    Returns:
        Number of panels with error states
    """
    errors = await page.query_selector_all('.panel-error-container, [class*="error"]')
    return len(errors)


async def take_screenshot(page: Page, name: str):
    """
    Take screenshot for debugging.

    Args:
        page: Playwright page object
        name: Screenshot name (without extension)
    """
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    path = os.path.join(screenshots_dir, f"{name}.png")
    await page.screenshot(path=path, full_page=True)
    return path
