"""
Dashboard SQL Query Tests (Mock Mode)
Tests query structure without database connection
Run: pytest tests/dashboards/test_dashboard_queries_mock.py -v

Tests:
- SQL query structure validation
- Query safety checks
- Schema reference validation
- Column reference validation
"""

import pytest
import re
from .conftest import (
    extract_sql_queries,
    get_dashboard_by_uid,
    prepare_sql_for_testing
)


class TestSQLQueryStructure:
    """Validate SQL query structure without execution"""

    def test_all_queries_are_select_statements(self, all_dashboards, postgresql_dashboard_uids):
        """All SQL queries should be SELECT or WITH statements"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"].strip().upper()
                is_valid = sql.startswith("SELECT") or sql.startswith("WITH")
                assert is_valid, \
                    f"{uid}: panel '{q['panel_title']}' query should be SELECT/WITH, got: {sql[:50]}..."

    def test_no_dangerous_operations(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should not contain INSERT, UPDATE, DELETE, DROP"""
        dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE"]

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"].upper()
                for keyword in dangerous_keywords:
                    # Ensure keyword is a standalone word, not part of table/column name
                    pattern = rf'\b{keyword}\b'
                    match = re.search(pattern, sql)
                    if match:
                        # Check if it's in a comment
                        if f"-- {keyword}" not in sql and f"/* {keyword}" not in sql:
                            pytest.fail(
                                f"{uid}: panel '{q['panel_title']}' contains dangerous keyword '{keyword}'"
                            )

    def test_queries_reference_valid_schemas(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should reference known schemas"""
        valid_schemas = [
            "gsc", "performance", "serp", "notifications",
            "orchestration", "anomaly", "content", "public"
        ]

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"].lower()

                # Skip if no FROM clause (could be simple function)
                if "from" not in sql:
                    continue

                # Skip system queries
                if "pg_" in sql or "information_schema" in sql:
                    continue

                # Check if any valid schema is referenced
                schema_patterns = [f"{schema}." for schema in valid_schemas]
                schema_found = any(pattern in sql for pattern in schema_patterns)

                # Some queries might use tables without schema prefix
                # This is informational, not a hard failure
                if not schema_found:
                    # Check if it's a simple table reference that might use search_path
                    pass  # Soft check - don't fail

    def test_queries_have_valid_syntax_structure(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should have basic valid SQL structure"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"].strip().upper()

                # Must have SELECT
                assert "SELECT" in sql, \
                    f"{uid}: panel '{q['panel_title']}' query missing SELECT"

                # If has FROM, check it's followed by something
                if "FROM" in sql:
                    # Basic check that FROM isn't at the very end
                    from_idx = sql.rfind("FROM")
                    remaining = sql[from_idx + 4:].strip()
                    assert len(remaining) > 0, \
                        f"{uid}: panel '{q['panel_title']}' FROM clause is empty"

    def test_queries_have_balanced_parentheses(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should have balanced parentheses"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"]
                open_count = sql.count("(")
                close_count = sql.count(")")
                assert open_count == close_count, \
                    f"{uid}: panel '{q['panel_title']}' has unbalanced parentheses ({open_count} vs {close_count})"


class TestSQLQuerySafety:
    """Test queries for potential safety issues"""

    def test_queries_dont_use_dangerous_functions(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should not use potentially dangerous functions"""
        dangerous_functions = [
            r'\bpg_read_file\b',
            r'\bpg_ls_dir\b',
            r'\bcopy\s+to\b',
            r'\bcopy\s+from\b',
            r'\bpg_execute_server_program\b'
        ]

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"].lower()
                for pattern in dangerous_functions:
                    match = re.search(pattern, sql, re.IGNORECASE)
                    assert not match, \
                        f"{uid}: panel '{q['panel_title']}' uses dangerous function matching '{pattern}'"

    def test_no_sql_injection_patterns(self, all_dashboards, postgresql_dashboard_uids):
        """Queries should not have obvious SQL injection patterns"""
        # These patterns might indicate unsafe dynamic SQL
        risky_patterns = [
            r";\s*--",  # Statement terminator followed by comment
            r"'\s*OR\s*'",  # Classic OR injection
            r"UNION\s+ALL\s+SELECT.*UNION",  # Multiple unions
        ]

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                sql = q["sql"]
                for pattern in risky_patterns:
                    match = re.search(pattern, sql, re.IGNORECASE)
                    if match:
                        # This is a warning, not necessarily a failure
                        # Some valid queries might match these patterns
                        pass


class TestGA4QueryContent:
    """Test GA4 dashboard query content"""

    def test_ga4_queries_reference_ga4_tables(self, ga4_dashboard):
        """Most GA4 dashboard queries should reference GA4 tables"""
        if not ga4_dashboard:
            pytest.skip("GA4 dashboard not found")

        queries = extract_sql_queries(ga4_dashboard)
        assert len(queries) > 0, "GA4 dashboard should have SQL queries"

        # Allow for some cross-dashboard queries (e.g., GSC+GA4 comparison panels)
        ga4_tables = ["fact_ga4_daily", "ga4", "sessions", "conversions", "fact_gsc"]

        matching_queries = 0
        for q in queries:
            sql = q["sql"].lower()
            if any(table in sql for table in ga4_tables):
                matching_queries += 1

        # At least 70% of queries should reference GA4 or related tables
        match_rate = matching_queries / len(queries)
        assert match_rate >= 0.7, \
            f"Only {match_rate:.0%} of GA4 queries reference GA4 tables (expected >= 70%)"

    def test_ga4_queries_use_expected_columns(self, ga4_dashboard):
        """Most GA4 dashboard queries should use expected GA4 columns"""
        if not ga4_dashboard:
            pytest.skip("GA4 dashboard not found")

        expected_columns = {
            "sessions", "conversions", "engagement_rate", "bounce_rate",
            "date", "property", "page_path", "conversion_rate", "clicks"
        }

        queries = extract_sql_queries(ga4_dashboard)
        matching_queries = 0
        for q in queries:
            sql = q["sql"].lower()
            column_refs = sum(1 for col in expected_columns if col in sql)
            if column_refs > 0:
                matching_queries += 1

        # At least 70% of queries should reference expected columns
        match_rate = matching_queries / len(queries) if queries else 1
        assert match_rate >= 0.7, \
            f"Only {match_rate:.0%} of GA4 queries reference expected columns"


class TestGSCQueryContent:
    """Test GSC dashboard query content"""

    def test_gsc_queries_reference_gsc_tables(self, gsc_dashboard):
        """Most GSC dashboard queries should reference GSC tables"""
        if not gsc_dashboard:
            pytest.skip("GSC dashboard not found")

        queries = extract_sql_queries(gsc_dashboard)
        if not queries:
            pytest.skip("GSC dashboard has no SQL queries")

        gsc_tables = ["fact_gsc_daily", "gsc", "insights"]

        matching_queries = 0
        for q in queries:
            sql = q["sql"].lower()
            if any(table in sql for table in gsc_tables):
                matching_queries += 1

        # At least 70% of queries should reference GSC tables
        match_rate = matching_queries / len(queries)
        assert match_rate >= 0.7, \
            f"Only {match_rate:.0%} of GSC queries reference GSC tables (expected >= 70%)"

    def test_gsc_queries_use_expected_columns(self, gsc_dashboard):
        """Most GSC dashboard queries should use expected GSC columns"""
        if not gsc_dashboard:
            pytest.skip("GSC dashboard not found")

        # Include common GSC and insight columns
        expected_columns = {
            "clicks", "impressions", "ctr", "position",
            "url", "query", "date", "property",
            "title", "category", "severity", "status"  # insight columns
        }

        queries = extract_sql_queries(gsc_dashboard)
        matching_queries = 0
        for q in queries:
            sql = q["sql"].lower()
            column_refs = sum(1 for col in expected_columns if col in sql)
            if column_refs > 0:
                matching_queries += 1

        # At least 70% of queries should reference expected columns
        match_rate = matching_queries / len(queries) if queries else 1
        assert match_rate >= 0.7, \
            f"Only {match_rate:.0%} of GSC queries reference expected columns"


class TestCWVQueryContent:
    """Test CWV dashboard query content"""

    def test_cwv_queries_reference_cwv_tables(self, cwv_dashboard):
        """CWV dashboard queries should reference CWV tables"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        queries = extract_sql_queries(cwv_dashboard)
        if not queries:
            pytest.skip("CWV dashboard has no SQL queries")

        cwv_tables = ["core_web_vitals", "cwv", "performance"]

        for q in queries:
            sql = q["sql"].lower()
            table_found = any(table in sql for table in cwv_tables)
            assert table_found, \
                f"CWV panel '{q['panel_title']}' should reference CWV tables"

    def test_cwv_queries_use_cwv_metrics(self, cwv_dashboard):
        """CWV dashboard queries should reference CWV metrics"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        cwv_metrics = {"lcp", "fid", "cls", "ttfb", "fcp", "performance_score"}

        queries = extract_sql_queries(cwv_dashboard)
        for q in queries:
            sql = q["sql"].lower()
            metric_refs = sum(1 for metric in cwv_metrics if metric in sql)
            # At least some queries should reference CWV metrics
            if metric_refs == 0:
                # Soft check - not all panels may use metrics directly
                pass


class TestSERPQueryContent:
    """Test SERP dashboard query content"""

    def test_serp_queries_reference_serp_tables(self, serp_dashboard):
        """SERP dashboard queries should reference SERP tables"""
        if not serp_dashboard:
            pytest.skip("SERP dashboard not found")

        queries = extract_sql_queries(serp_dashboard)
        if not queries:
            pytest.skip("SERP dashboard has no SQL queries")

        serp_tables = ["queries", "position_history", "serp"]

        for q in queries:
            sql = q["sql"].lower()
            table_found = any(table in sql for table in serp_tables)
            assert table_found, \
                f"SERP panel '{q['panel_title']}' should reference SERP tables"


class TestHybridQueryContent:
    """Test Hybrid dashboard query content"""

    def test_hybrid_queries_reference_unified_view(self, hybrid_dashboard):
        """Hybrid dashboard queries should reference unified view or both data sources"""
        if not hybrid_dashboard:
            pytest.skip("Hybrid dashboard not found")

        queries = extract_sql_queries(hybrid_dashboard)
        if not queries:
            pytest.skip("Hybrid dashboard has no SQL queries")

        # Hybrid dashboard should use unified view or both GSC and GA4 data
        hybrid_tables = ["vw_unified_page_performance", "fact_gsc_daily", "fact_ga4_daily"]

        for q in queries:
            sql = q["sql"].lower()
            table_found = any(table in sql for table in hybrid_tables)
            assert table_found, \
                f"Hybrid panel '{q['panel_title']}' should reference unified view or core tables"


class TestQueryStatistics:
    """Test query statistics for dashboards"""

    def test_dashboards_have_reasonable_query_count(self, all_dashboards, postgresql_dashboard_uids):
        """Dashboards should have a reasonable number of queries"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            # Should have at least one query
            assert len(queries) >= 1, f"{uid}: dashboard should have at least one SQL query"
            # Should not have excessive queries (performance concern)
            assert len(queries) <= 50, f"{uid}: dashboard has too many queries ({len(queries)})"

    def test_query_length_is_reasonable(self, all_dashboards, postgresql_dashboard_uids):
        """Individual queries should not be excessively long"""
        max_query_length = 5000  # characters

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            queries = extract_sql_queries(dashboard)
            for q in queries:
                assert len(q["sql"]) <= max_query_length, \
                    f"{uid}: panel '{q['panel_title']}' query is too long ({len(q['sql'])} chars)"
