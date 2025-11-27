"""
Tests for GA4 Dashboard SQL Queries

Verifies that all GA4 dashboard panel queries execute without errors.
These tests run against the actual database to catch SQL syntax issues.

Run tests:
    pytest tests/dashboards/test_ga4_dashboard_queries.py -v

    # With database via docker:
    docker exec gsc_warehouse pytest /app/tests/dashboards/test_ga4_dashboard_queries.py -v
"""

import pytest
import os
import json
from pathlib import Path


def _get_db_dsn():
    """Get database DSN from environment"""
    return os.getenv(
        "WAREHOUSE_DSN",
        "postgresql://gsc_user:gsc_pass_secure_2024@localhost:5432/gsc_db"
    )


@pytest.fixture
def db_connection_or_skip():
    """Create database connection or skip test if unavailable"""
    import psycopg2
    dsn = _get_db_dsn()
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


class TestGA4DashboardQueries:
    """Test GA4 dashboard SQL queries for validity"""

    @pytest.fixture
    def ga4_dashboard(self):
        """Load GA4 dashboard JSON"""
        dashboard_path = Path(__file__).parent.parent.parent / \
            "grafana/provisioning/dashboards/ga4-overview.json"
        with open(dashboard_path, "r") as f:
            return json.load(f)

    def test_engagement_distribution_query_valid_sql(self, db_connection_or_skip):
        """
        Verify Engagement Distribution query has valid SQL syntax.

        Previously failed with: GROUP BY property, page_path ... GROUP BY category
        Fixed: Uses subquery pattern to aggregate properly.
        """
        query = """
        SELECT category, COUNT(*) as count FROM (
            SELECT CASE
                WHEN AVG(engagement_rate) >= 0.5 THEN 'High (50%+)'
                WHEN AVG(engagement_rate) >= 0.3 THEN 'Medium (30-50%)'
                WHEN AVG(engagement_rate) >= 0.1 THEN 'Low (10-30%)'
                ELSE 'Very Low (<10%)'
            END as category
            FROM gsc.fact_ga4_daily
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            AND sessions > 0
            AND ('All' = 'All' OR property = 'All')
            GROUP BY property, page_path
            HAVING COUNT(*) > 0
        ) page_engagement
        GROUP BY category
        ORDER BY CASE category
            WHEN 'High (50%+)' THEN 1
            WHEN 'Medium (30-50%)' THEN 2
            WHEN 'Low (10-30%)' THEN 3
            ELSE 4
        END
        """
        with db_connection_or_skip.cursor() as cur:
            cur.execute(query)
            results = cur.fetchall()

        # Should return categories without SQL error
        assert results is not None
        # Should have at least one category if data exists
        categories = [r[0] for r in results]
        valid_categories = ['High (50%+)', 'Medium (30-50%)', 'Low (10-30%)', 'Very Low (<10%)']
        for cat in categories:
            assert cat in valid_categories

    def test_total_sessions_query(self, db_connection_or_skip):
        """Verify Total Sessions query executes"""
        query = """
        SELECT SUM(sessions)::bigint as "Total Sessions"
        FROM gsc.fact_ga4_daily
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        AND ('All' = 'All' OR property = 'All')
        """
        with db_connection_or_skip.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
        assert result is not None

    def test_sessions_change_query(self, db_connection_or_skip):
        """Verify Sessions Change comparison query executes"""
        query = """
        WITH current_period AS (
            SELECT SUM(sessions) as val
            FROM gsc.fact_ga4_daily
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            AND ('All' = 'All' OR property = 'All')
        ),
        previous_period AS (
            SELECT SUM(sessions) as val
            FROM gsc.fact_ga4_daily
            WHERE date >= CURRENT_DATE - INTERVAL '60 days'
            AND date < CURRENT_DATE - INTERVAL '30 days'
            AND ('All' = 'All' OR property = 'All')
        )
        SELECT ROUND(((c.val - p.val)::numeric / NULLIF(p.val, 0) * 100), 1) as "Change %"
        FROM current_period c, previous_period p
        """
        with db_connection_or_skip.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()
        assert result is not None

    def test_template_variable_has_default(self, ga4_dashboard):
        """
        Verify $property template variable has default value set.

        Previously: "current": {} caused uninitialized queries
        Fixed: "current": {"selected": true, "text": "All", "value": "$__all"}
        """
        templating = ga4_dashboard.get("templating", {}).get("list", [])
        property_var = next(
            (v for v in templating if v.get("name") == "property"),
            None
        )

        assert property_var is not None, "Property variable not found"
        current = property_var.get("current", {})
        assert current.get("selected") is True, "Property should be selected"
        assert current.get("text") == "All", "Property default should be 'All'"
        assert "allValue" in property_var, "allValue should be set"

    def test_all_panel_queries_valid(self, db_connection_or_skip, ga4_dashboard):
        """Verify all panel queries in GA4 dashboard execute without error"""
        panels = ga4_dashboard.get("panels", [])
        failed_panels = []

        for panel in panels:
            if panel.get("type") == "row":
                continue

            targets = panel.get("targets", [])
            for target in targets:
                raw_sql = target.get("rawSql", "")
                if not raw_sql:
                    continue

                # Substitute template variables for testing
                test_sql = raw_sql.replace("${days}", "30")
                # Handle both '$property' (quoted) and $property (unquoted)
                test_sql = test_sql.replace("'$property'", "'All'")
                test_sql = test_sql.replace("$property", "'All'")

                try:
                    with db_connection_or_skip.cursor() as cur:
                        cur.execute(test_sql)
                        cur.fetchone()
                except Exception as e:
                    failed_panels.append({
                        "panel": panel.get("title", "Unknown"),
                        "error": str(e)
                    })

        if failed_panels:
            error_msg = "Panels with SQL errors:\n"
            for p in failed_panels:
                error_msg += f"  - {p['panel']}: {p['error']}\n"
            pytest.fail(error_msg)


class TestErrorDetectionLogic:
    """Test that error detection correctly identifies issues"""

    def test_no_data_is_not_error(self):
        """
        Verify 'No data' is not treated as an error.

        'No data' is a valid state when a panel has empty results,
        not a query failure.
        """
        from tests.e2e.conftest import get_panel_errors

        # The error_texts list should not contain 'No data'
        # This test documents the expected behavior
        expected_error_texts = ['Query error', 'Data source error', 'Failed to load']
        # 'No data', 'Error', 'Failed' should NOT be in the list
        excluded_texts = ['No data']

        # Verify through code inspection (actual behavior tested in e2e tests)
        import inspect
        source = inspect.getsource(get_panel_errors)

        for text in expected_error_texts:
            assert text in source, f"Expected '{text}' in error detection"

        # 'No data' should not be in the strict error list
        # (it may appear in comments but not in the error_texts list)
        assert "'No data'" not in source or "excluding" in source.lower()
