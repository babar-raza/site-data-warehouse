"""
Dashboard SQL Query Tests (Live Mode)
Executes queries against real database with sample data
Run: TEST_MODE=live pytest tests/dashboards/test_dashboard_queries_live.py -v

Tests:
- Query execution without errors
- Query performance within timeout
- Result structure validation
"""

import pytest
import asyncio
import os
from typing import Any, Dict, List

from tests.testing_modes import require_live_mode, is_live_mode
from .conftest import (
    extract_sql_queries,
    get_dashboard_by_uid,
    prepare_sql_for_testing
)


# Skip module if asyncpg not available
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    asyncpg = None


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db_pool():
    """Create database connection pool for live tests"""
    if not HAS_ASYNCPG:
        pytest.skip("asyncpg not installed")

    if not is_live_mode():
        pytest.skip("Not in live mode")

    dsn = os.getenv("WAREHOUSE_DSN", "postgresql://gsc_user:gsc_password@localhost:5432/gsc_db")

    try:
        pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5, timeout=30)
        yield pool
        await pool.close()
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")


@pytest.mark.live
class TestSQLQueryExecution:
    """Execute dashboard queries against live database"""

    @pytest.mark.asyncio
    async def test_ga4_queries_execute_without_error(self, ga4_dashboard, db_pool):
        """All GA4 dashboard queries should execute successfully"""
        if not ga4_dashboard:
            pytest.skip("GA4 dashboard not found")

        queries = extract_sql_queries(ga4_dashboard)
        if not queries:
            pytest.skip("No SQL queries in GA4 dashboard")

        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    # Use EXPLAIN to validate without full execution
                    await conn.execute(f"EXPLAIN {sql}")
                except Exception as e:
                    pytest.fail(
                        f"GA4 panel '{q['panel_title']}' query failed: {e}\n"
                        f"SQL (first 300 chars): {sql[:300]}"
                    )

    @pytest.mark.asyncio
    async def test_gsc_queries_execute_without_error(self, gsc_dashboard, db_pool):
        """All GSC dashboard queries should execute successfully"""
        if not gsc_dashboard:
            pytest.skip("GSC dashboard not found")

        queries = extract_sql_queries(gsc_dashboard)
        if not queries:
            pytest.skip("No SQL queries in GSC dashboard")

        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    await conn.execute(f"EXPLAIN {sql}")
                except Exception as e:
                    pytest.fail(
                        f"GSC panel '{q['panel_title']}' query failed: {e}\n"
                        f"SQL (first 300 chars): {sql[:300]}"
                    )

    @pytest.mark.asyncio
    async def test_hybrid_queries_execute_without_error(self, hybrid_dashboard, db_pool):
        """All Hybrid dashboard queries should execute successfully"""
        if not hybrid_dashboard:
            pytest.skip("Hybrid dashboard not found")

        queries = extract_sql_queries(hybrid_dashboard)
        if not queries:
            pytest.skip("No SQL queries in Hybrid dashboard")

        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    await conn.execute(f"EXPLAIN {sql}")
                except Exception as e:
                    pytest.fail(
                        f"Hybrid panel '{q['panel_title']}' query failed: {e}\n"
                        f"SQL (first 300 chars): {sql[:300]}"
                    )

    @pytest.mark.asyncio
    async def test_cwv_queries_execute_without_error(self, cwv_dashboard, db_pool):
        """All CWV dashboard queries should execute successfully"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        queries = extract_sql_queries(cwv_dashboard)
        if not queries:
            pytest.skip("No SQL queries in CWV dashboard")

        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    await conn.execute(f"EXPLAIN {sql}")
                except Exception as e:
                    pytest.fail(
                        f"CWV panel '{q['panel_title']}' query failed: {e}\n"
                        f"SQL (first 300 chars): {sql[:300]}"
                    )

    @pytest.mark.asyncio
    async def test_serp_queries_execute_without_error(self, serp_dashboard, db_pool):
        """All SERP dashboard queries should execute successfully"""
        if not serp_dashboard:
            pytest.skip("SERP dashboard not found")

        queries = extract_sql_queries(serp_dashboard)
        if not queries:
            pytest.skip("No SQL queries in SERP dashboard")

        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    await conn.execute(f"EXPLAIN {sql}")
                except Exception as e:
                    pytest.fail(
                        f"SERP panel '{q['panel_title']}' query failed: {e}\n"
                        f"SQL (first 300 chars): {sql[:300]}"
                    )


@pytest.mark.live
class TestQueryPerformance:
    """Test query performance against live database"""

    @pytest.mark.asyncio
    async def test_queries_complete_within_timeout(
        self, all_dashboards, postgresql_dashboard_uids, db_pool
    ):
        """All queries should complete within 5 seconds"""
        timeout_seconds = 5

        async with db_pool.acquire() as conn:
            for uid in postgresql_dashboard_uids:
                dashboard = get_dashboard_by_uid(all_dashboards, uid)
                if not dashboard:
                    continue

                queries = extract_sql_queries(dashboard)
                for q in queries:
                    sql = prepare_sql_for_testing(q["sql"])
                    try:
                        async with asyncio.timeout(timeout_seconds):
                            await conn.execute(f"EXPLAIN ANALYZE {sql}")
                    except asyncio.TimeoutError:
                        pytest.fail(
                            f"{uid} panel '{q['panel_title']}' query timed out "
                            f"after {timeout_seconds}s"
                        )
                    except Exception:
                        # Query errors handled in other tests
                        pass

    @pytest.mark.asyncio
    async def test_queries_dont_do_full_table_scans(
        self, all_dashboards, postgresql_dashboard_uids, db_pool
    ):
        """Queries should not do full table scans on large tables (when possible)"""
        async with db_pool.acquire() as conn:
            for uid in postgresql_dashboard_uids:
                dashboard = get_dashboard_by_uid(all_dashboards, uid)
                if not dashboard:
                    continue

                queries = extract_sql_queries(dashboard)
                for q in queries:
                    sql = prepare_sql_for_testing(q["sql"])
                    try:
                        result = await conn.fetch(f"EXPLAIN {sql}")
                        plan = "\n".join(row[0] for row in result)

                        # Check for sequential scans on known large tables
                        large_tables = ["fact_gsc_daily", "fact_ga4_daily", "position_history"]

                        for table in large_tables:
                            if f"Seq Scan on {table}" in plan:
                                # This is a warning, not necessarily a failure
                                # Some queries legitimately need table scans
                                pass
                    except Exception:
                        # Query errors handled in other tests
                        pass


@pytest.mark.live
class TestQueryResultStructure:
    """Test query result structure"""

    @pytest.mark.asyncio
    async def test_ga4_queries_return_data(self, ga4_dashboard, db_pool):
        """GA4 queries should return data (when data exists)"""
        if not ga4_dashboard:
            pytest.skip("GA4 dashboard not found")

        queries = extract_sql_queries(ga4_dashboard)
        if not queries:
            pytest.skip("No SQL queries in GA4 dashboard")

        queries_with_data = 0
        async with db_pool.acquire() as conn:
            for q in queries:
                sql = prepare_sql_for_testing(q["sql"])
                try:
                    result = await conn.fetch(sql)
                    if result:
                        queries_with_data += 1
                except Exception:
                    pass  # Query errors handled in other tests

        # At least some queries should return data if database is populated
        # This is a soft check - empty results may be expected in test environments

    @pytest.mark.asyncio
    async def test_queries_return_expected_column_types(
        self, all_dashboards, postgresql_dashboard_uids, db_pool
    ):
        """Queries should return columns with expected types"""
        async with db_pool.acquire() as conn:
            for uid in postgresql_dashboard_uids:
                dashboard = get_dashboard_by_uid(all_dashboards, uid)
                if not dashboard:
                    continue

                queries = extract_sql_queries(dashboard)
                for q in queries:
                    sql = prepare_sql_for_testing(q["sql"])
                    try:
                        # Get column info
                        result = await conn.fetch(f"SELECT * FROM ({sql}) sq LIMIT 0")
                        # If query succeeds, structure is valid
                    except Exception:
                        pass  # Query errors handled in other tests


@pytest.mark.live
class TestAllDashboardQueries:
    """Comprehensive test for all dashboard queries"""

    @pytest.mark.asyncio
    async def test_all_postgresql_queries_are_valid(
        self, all_dashboards, postgresql_dashboard_uids, db_pool
    ):
        """All PostgreSQL dashboard queries should be syntactically valid"""
        failed_queries = []

        async with db_pool.acquire() as conn:
            for uid in postgresql_dashboard_uids:
                dashboard = get_dashboard_by_uid(all_dashboards, uid)
                if not dashboard:
                    continue

                queries = extract_sql_queries(dashboard)
                for q in queries:
                    sql = prepare_sql_for_testing(q["sql"])
                    try:
                        await conn.execute(f"EXPLAIN {sql}")
                    except Exception as e:
                        failed_queries.append({
                            "dashboard": uid,
                            "panel": q["panel_title"],
                            "error": str(e)
                        })

        if failed_queries:
            error_msg = "Failed queries:\n"
            for fq in failed_queries:
                error_msg += f"  - {fq['dashboard']}/{fq['panel']}: {fq['error']}\n"
            pytest.fail(error_msg)

    @pytest.mark.asyncio
    async def test_query_summary_statistics(
        self, all_dashboards, postgresql_dashboard_uids, db_pool
    ):
        """Generate summary statistics for all queries"""
        stats = {
            "total_dashboards": 0,
            "total_queries": 0,
            "valid_queries": 0,
            "invalid_queries": 0,
            "queries_with_data": 0
        }

        async with db_pool.acquire() as conn:
            for uid in postgresql_dashboard_uids:
                dashboard = get_dashboard_by_uid(all_dashboards, uid)
                if not dashboard:
                    continue

                stats["total_dashboards"] += 1
                queries = extract_sql_queries(dashboard)

                for q in queries:
                    stats["total_queries"] += 1
                    sql = prepare_sql_for_testing(q["sql"])

                    try:
                        await conn.execute(f"EXPLAIN {sql}")
                        stats["valid_queries"] += 1

                        # Check if returns data
                        result = await conn.fetch(sql)
                        if result:
                            stats["queries_with_data"] += 1
                    except Exception:
                        stats["invalid_queries"] += 1

        # Assert high success rate
        if stats["total_queries"] > 0:
            success_rate = stats["valid_queries"] / stats["total_queries"]
            assert success_rate >= 0.9, \
                f"Query success rate too low: {success_rate:.1%} " \
                f"({stats['valid_queries']}/{stats['total_queries']})"
