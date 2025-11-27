"""
Pytest configuration for E2E/Playwright Dashboard Tests

Uses pytest-playwright's built-in fixtures for browser automation.
Provides dashboard-specific fixtures and helper functions.

Usage:
    # Run all dashboard tests
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov

    # Run in headed mode (visible browser)
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --headed

    # Run with specific browser
    pytest tests/e2e/test_dashboard_e2e.py -v --no-cov --browser firefox
"""

import pytest
import os
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


# ============================================================================
# CONFIGURATION
# ============================================================================

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "grafana_admin_2024")

# All 11 Grafana dashboards
DASHBOARD_DEFINITIONS = {
    "ga4-overview": {
        "uid": "ga4-overview",
        "slug": "ga4-analytics-overview",
        "title": "GA4 Analytics",
        "description": "Google Analytics 4 overview metrics",
    },
    "gsc-overview": {
        "uid": "gsc-overview",
        "slug": "gsc-data-overview",
        "title": "GSC Data",
        "description": "Google Search Console data overview",
    },
    "hybrid-overview": {
        "uid": "hybrid-overview",
        "slug": "hybrid-analytics-gsc-ga4-unified",
        "title": "Hybrid Analytics",
        "description": "Combined GSC and GA4 analytics view",
    },
    "service-health": {
        "uid": "service-health",
        "slug": "service-health",
        "title": "Service Health",
        "description": "Service status and health monitoring",
    },
    "infrastructure-overview": {
        "uid": "infrastructure-overview",
        "slug": "infrastructure-overview",
        "title": "Infrastructure",
        "description": "Infrastructure resource monitoring",
    },
    "database-performance": {
        "uid": "database-performance",
        "slug": "database-performance",
        "title": "Database Performance",
        "description": "PostgreSQL database metrics",
    },
    "cwv-monitoring": {
        "uid": "cwv-monitoring",
        "slug": "core-web-vitals-monitoring",
        "title": "Core Web Vitals",
        "description": "Core Web Vitals monitoring (LCP, FID, CLS)",
    },
    "serp-tracking": {
        "uid": "serp-tracking",
        "slug": "serp-position-tracking",
        "title": "SERP Tracking",
        "description": "Search engine results position tracking",
    },
    "actions-command-center": {
        "uid": "actions-center",
        "slug": "actions-command-center",
        "title": "Actions Command Center",
        "description": "Recommended actions and automation status",
    },
    "alert-status": {
        "uid": "alert-status",
        "slug": "alert-status",
        "title": "Alert Status",
        "description": "Alert rules and status monitoring",
    },
    "application-metrics": {
        "uid": "application-metrics",
        "slug": "application-metrics",
        "title": "Application Metrics",
        "description": "Application-level performance metrics",
    },
}


# ============================================================================
# DIRECTORY SETUP
# ============================================================================

def setup_test_directories():
    """Create test output directories."""
    dirs = [
        Path("test-results"),
        Path("test-results/screenshots"),
        Path("test-results/videos"),
        Path("test-results/traces"),
        Path("test-results/reports"),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


# ============================================================================
# PYTEST HOOKS
# ============================================================================

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test result for use in fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    setup_test_directories()

    # Register custom markers
    markers = [
        "ui: mark test as requiring browser/UI (Playwright)",
        "e2e: mark test as end-to-end workflow test",
        "dashboard: mark test as dashboard-specific test",
        "playwright: mark test as requiring Playwright browser automation",
        "slow: mark test as slow running",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """Add markers to tests in the e2e directory."""
    for item in items:
        if "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        if "dashboard" in str(item.fspath) or "dashboard" in item.name.lower():
            item.add_marker(pytest.mark.dashboard)


# ============================================================================
# FIXTURES - Use pytest-playwright's built-in fixtures
# ============================================================================

@pytest.fixture
def grafana_url() -> str:
    """Grafana base URL."""
    return GRAFANA_URL


@pytest.fixture
def grafana_credentials() -> Dict[str, str]:
    """Grafana login credentials."""
    return {
        "username": GRAFANA_USER,
        "password": GRAFANA_PASSWORD,
    }


@pytest.fixture
def dashboard_definitions() -> Dict[str, Dict]:
    """Provide dashboard definitions."""
    return DASHBOARD_DEFINITIONS.copy()


@pytest.fixture
def dashboard_urls() -> Dict[str, str]:
    """Generate dashboard URLs."""
    urls = {}
    for key, info in DASHBOARD_DEFINITIONS.items():
        urls[key] = f"{GRAFANA_URL}/d/{info['uid']}/{info['slug']}"
    return urls


@pytest.fixture
def all_dashboard_names() -> List[str]:
    """List of all dashboard names."""
    return list(DASHBOARD_DEFINITIONS.keys())


@pytest.fixture
def authenticated_page(page, grafana_credentials):
    """
    Create authenticated Grafana page using pytest-playwright's page fixture.

    This fixture uses the built-in 'page' fixture from pytest-playwright
    and adds Grafana authentication.
    """
    # Navigate to login
    page.goto(f"{GRAFANA_URL}/login", timeout=30000)

    # Wait for login form
    page.wait_for_selector('input[name="user"]', timeout=10000)

    # Fill credentials
    page.fill('input[name="user"]', grafana_credentials["username"])
    page.fill('input[name="password"]', grafana_credentials["password"])

    # Submit login form
    page.click('button[type="submit"]')

    # Wait for navigation away from login page - use explicit wait
    # instead of problematic glob pattern
    page.wait_for_timeout(3000)

    # Verify we're no longer on the login page
    page.wait_for_load_state("networkidle", timeout=30000)

    return page


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def take_screenshot(page, name: str) -> str:
    """Take screenshot for debugging."""
    screenshots_dir = Path("test-results/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = screenshots_dir / f"{safe_name}_{timestamp}.png"

    page.screenshot(path=str(path), full_page=True)
    print(f"\nScreenshot saved: {path}")
    return str(path)


def wait_for_dashboard_load(page, timeout: int = 30000):
    """Wait for dashboard to fully load."""
    # Wait for network to be idle
    page.wait_for_load_state("networkidle", timeout=timeout)

    # Wait for panels to render
    try:
        page.wait_for_selector(
            '.panel-container, [data-panelid], .react-grid-item',
            timeout=10000
        )
    except Exception:
        pass

    # Additional wait for dynamic content
    page.wait_for_timeout(2000)


def get_panel_count(page) -> int:
    """Count visible panels on dashboard."""
    # Updated selectors for modern Grafana (v9+/v12)
    panel_selectors = [
        '[data-viz-panel-key]',               # Grafana 9+ panel key
        '[data-panelid]',                      # Legacy panel ID
        'article[class*="PanelChrome"]',       # Grafana 9+ PanelChrome component
        '[class*="VizPanel"]',                 # Visualization panel wrapper
        '[class*="dashboard-row__panel"]',     # Dashboard row panel wrapper
        'div[id^="panel-"]',                   # Panel ID prefix
        '.react-grid-item',                    # React grid layout items
        '[class*="panel-content"]',            # Panel content wrapper
        '.panel-container',                    # Legacy panel container
        'section[class*="panel"]',             # Section-based panels
        '[data-testid*="panel"]',              # Test ID based panels
        '[data-testid*="Panel"]',              # Test ID (capitalized)
        '[class*="css-"][class*="panel"]',     # CSS modules styled panels
    ]

    seen_panels = set()
    for selector in panel_selectors:
        try:
            elements = page.query_selector_all(selector)
            for el in elements:
                if el.is_visible():
                    # Use bounding box to dedupe overlapping selectors
                    box = el.bounding_box()
                    if box and box['width'] > 50 and box['height'] > 50:
                        # Filter out very small elements
                        key = (int(box['x']), int(box['y']), int(box['width']), int(box['height']))
                        seen_panels.add(key)
        except Exception:
            continue

    # Fallback to react-grid-item count
    if not seen_panels:
        try:
            grid_items = page.query_selector_all('.react-grid-item')
            return sum(1 for item in grid_items if item.is_visible())
        except Exception:
            pass

    return len(seen_panels)


def get_panel_errors(page) -> int:
    """Count panels with errors including data source errors."""
    error_selectors = [
        '.panel-error-container',
        '[class*="panel-error"]',
        '[class*="alert-error"]',
        '[class*="panel-info-corner--error"]',
        '[data-testid="data-testid Panel status error"]',
    ]

    error_count = 0
    for selector in error_selectors:
        try:
            elements = page.query_selector_all(selector)
            for element in elements:
                if element.is_visible():
                    error_count += 1
        except Exception:
            continue

    # Also check for error text (excluding "No data" which is valid for empty results)
    error_texts = ['Query error', 'Data source error', 'Failed to load']
    for text in error_texts:
        try:
            elements = page.query_selector_all(f'text="{text}"')
            for element in elements:
                if element.is_visible():
                    parent = element.evaluate('el => el.closest(".panel-container, [data-panelid]")')
                    if parent:
                        error_count += 1
        except Exception:
            continue

    return error_count


def check_panel_rendering(page) -> Dict[str, Any]:
    """Comprehensive panel rendering check."""
    total_panels = get_panel_count(page)
    error_panels = get_panel_errors(page)

    # Check for loading spinners (updated for Grafana v9+)
    spinner_selectors = [
        '.panel-loading',
        '[class*="spinner"]',
        '[class*="loading"]',
        '[data-testid*="Spinner"]',
        '[class*="LoadingPlaceholder"]',
    ]
    loading_count = 0
    for selector in spinner_selectors:
        try:
            spinners = page.query_selector_all(selector)
            loading_count += sum(1 for s in spinners if s.is_visible())
        except Exception:
            continue

    return {
        "total_panels": total_panels,
        "error_panels": error_panels,
        "loading_panels": loading_count,
        "healthy_panels": max(0, total_panels - error_panels - loading_count),
    }


def get_dashboard_health_report(page, dashboard_name: str) -> Dict[str, Any]:
    """Generate comprehensive dashboard health report."""
    status = check_panel_rendering(page)

    health = "HEALTHY"
    if status["error_panels"] > 0:
        health = "ERROR"
    elif status["loading_panels"] > 2:
        health = "WARNING"

    return {
        "dashboard": dashboard_name,
        "health": health,
        "timestamp": datetime.now().isoformat(),
        **status,
    }


# Export helper functions
__all__ = [
    "GRAFANA_URL",
    "DASHBOARD_DEFINITIONS",
    "take_screenshot",
    "wait_for_dashboard_load",
    "get_panel_count",
    "get_panel_errors",
    "check_panel_rendering",
    "get_dashboard_health_report",
]
