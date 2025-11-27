"""Dashboard test fixtures and utilities"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


# Path to Grafana dashboards
DASHBOARD_DIR = Path(__file__).parent.parent.parent / "grafana" / "provisioning" / "dashboards"


@pytest.fixture(scope="session")
def all_dashboards() -> Dict[str, Any]:
    """Load all dashboard JSON files"""
    dashboards = {}
    for file in DASHBOARD_DIR.glob("*.json"):
        with open(file, encoding='utf-8') as f:
            dashboards[file.stem] = json.load(f)
    return dashboards


@pytest.fixture(scope="session")
def dashboard_uids() -> List[str]:
    """Expected dashboard UIDs"""
    return [
        "ga4-overview",
        "gsc-overview",
        "service-health",
        "cwv-monitoring",
        "serp-tracking",
        "alert-status",
        "hybrid-overview",
        "application-metrics",
        "database-performance",
        "infrastructure-overview"
    ]


@pytest.fixture(scope="session")
def postgresql_dashboard_uids() -> List[str]:
    """Dashboard UIDs that use PostgreSQL datasource"""
    return [
        "ga4-overview",
        "gsc-overview",
        "cwv-monitoring",
        "serp-tracking",
        "hybrid-overview"
    ]


@pytest.fixture(scope="session")
def prometheus_dashboard_uids() -> List[str]:
    """Dashboard UIDs that use Prometheus datasource"""
    return [
        "service-health",
        "alert-status",
        "application-metrics",
        "database-performance",
        "infrastructure-overview"
    ]


@pytest.fixture
def ga4_dashboard(all_dashboards) -> Dict[str, Any]:
    """GA4 Analytics dashboard"""
    return all_dashboards.get("ga4-overview", {})


@pytest.fixture
def gsc_dashboard(all_dashboards) -> Dict[str, Any]:
    """GSC Overview dashboard"""
    return all_dashboards.get("gsc-overview", {})


@pytest.fixture
def cwv_dashboard(all_dashboards) -> Dict[str, Any]:
    """Core Web Vitals dashboard"""
    return all_dashboards.get("cwv-monitoring", {})


@pytest.fixture
def serp_dashboard(all_dashboards) -> Dict[str, Any]:
    """SERP Tracking dashboard"""
    return all_dashboards.get("serp-tracking", {})


@pytest.fixture
def hybrid_dashboard(all_dashboards) -> Dict[str, Any]:
    """Hybrid Analytics dashboard"""
    return all_dashboards.get("hybrid-overview", {})


@pytest.fixture
def service_health_dashboard(all_dashboards) -> Dict[str, Any]:
    """Service Health dashboard"""
    return all_dashboards.get("service-health", {})


@pytest.fixture
def alert_status_dashboard(all_dashboards) -> Dict[str, Any]:
    """Alert Status dashboard"""
    return all_dashboards.get("alert-status", {})


@pytest.fixture
def application_metrics_dashboard(all_dashboards) -> Dict[str, Any]:
    """Application Metrics dashboard"""
    return all_dashboards.get("application-metrics", {})


def extract_sql_queries(dashboard: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract all SQL queries from dashboard panels.

    Args:
        dashboard: Dashboard JSON dictionary

    Returns:
        List of query dictionaries with panel_id, panel_title, sql, ref_id
    """
    queries = []
    for panel in dashboard.get("panels", []):
        # Handle collapsed rows (may contain nested panels)
        if panel.get("type") == "row" and "panels" in panel:
            for nested_panel in panel.get("panels", []):
                queries.extend(_extract_panel_queries(nested_panel))
        else:
            queries.extend(_extract_panel_queries(panel))
    return queries


def _extract_panel_queries(panel: Dict[str, Any]) -> List[Dict[str, str]]:
    """Extract SQL queries from a single panel."""
    queries = []
    for target in panel.get("targets", []):
        if "rawSql" in target:
            queries.append({
                "panel_id": panel.get("id"),
                "panel_title": panel.get("title", "Untitled"),
                "panel_type": panel.get("type"),
                "sql": target["rawSql"],
                "ref_id": target.get("refId", "A"),
                "datasource": target.get("datasource", {})
            })
    return queries


def extract_template_variables(dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract template variables from dashboard.

    Args:
        dashboard: Dashboard JSON dictionary

    Returns:
        List of template variable configurations
    """
    return dashboard.get("templating", {}).get("list", [])


def extract_all_panels(dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract all panels including those nested in rows.

    Args:
        dashboard: Dashboard JSON dictionary

    Returns:
        Flat list of all panels
    """
    panels = []
    for panel in dashboard.get("panels", []):
        panels.append(panel)
        # Handle collapsed rows with nested panels
        if panel.get("type") == "row" and "panels" in panel:
            panels.extend(panel.get("panels", []))
    return panels


def get_dashboard_by_uid(all_dashboards: Dict[str, Any], uid: str) -> Optional[Dict[str, Any]]:
    """
    Get a dashboard by its UID.

    Args:
        all_dashboards: Dictionary of all loaded dashboards
        uid: Dashboard UID to find

    Returns:
        Dashboard dictionary or None if not found
    """
    for dashboard in all_dashboards.values():
        if dashboard.get("uid") == uid:
            return dashboard
    return None


def prepare_sql_for_testing(sql: str) -> str:
    """
    Prepare SQL query for testing by replacing Grafana macros with test values.

    Args:
        sql: Raw SQL query with Grafana macros

    Returns:
        SQL query with macros replaced
    """
    replacements = [
        # Time filter macros
        ("$__timeFilter(date)", "date >= CURRENT_DATE - INTERVAL '30 days'"),
        ("$__timeFilter(check_date)", "check_date >= CURRENT_DATE - INTERVAL '30 days'"),
        ("$__timeFilter(ph.check_date)", "ph.check_date >= CURRENT_DATE - INTERVAL '30 days'"),
        ("$__timeFilter(created_at)", "created_at >= CURRENT_DATE - INTERVAL '30 days'"),
        # Time range macros
        ("$__timeFrom()", "CURRENT_DATE - INTERVAL '30 days'"),
        ("$__timeTo()", "CURRENT_DATE"),
        # Variable placeholders (test values)
        ("$property", "'https://test-domain.com'"),
        ("${property}", "'https://test-domain.com'"),
        ("$device", "'mobile'"),
        ("${device}", "'mobile'"),
        ("$interval", "'1 day'"),
        ("${interval}", "'1 day'"),
    ]

    result = sql
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def count_dashboard_panels(dashboard: Dict[str, Any]) -> int:
    """Count total panels in a dashboard including nested ones."""
    return len(extract_all_panels(dashboard))


def count_dashboard_queries(dashboard: Dict[str, Any]) -> int:
    """Count total SQL queries in a dashboard."""
    return len(extract_sql_queries(dashboard))
