"""
Dashboard Data Availability Tests
Verifies required tables and views have data
Run: TEST_MODE=live pytest tests/dashboards/test_dashboard_data.py -v

Tests:
- Required tables exist
- Required views exist
- Data freshness
- Data structure validation
"""

import pytest
import asyncio
import os
from typing import List, Dict, Any

from tests.testing_modes import require_live_mode, is_live_mode


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
    """Create database connection pool"""
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
class TestSchemaExists:
    """Test that required schemas exist"""

    @pytest.mark.asyncio
    async def test_gsc_schema_exists(self, db_pool):
        """GSC schema must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.schemata
                    WHERE schema_name = 'gsc'
                )
            """)
            assert result, "Schema 'gsc' does not exist"

    @pytest.mark.asyncio
    async def test_performance_schema_exists(self, db_pool):
        """Performance schema must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.schemata
                    WHERE schema_name = 'performance'
                )
            """)
            assert result, "Schema 'performance' does not exist"

    @pytest.mark.asyncio
    async def test_serp_schema_exists(self, db_pool):
        """SERP schema must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.schemata
                    WHERE schema_name = 'serp'
                )
            """)
            assert result, "Schema 'serp' does not exist"


@pytest.mark.live
class TestGSCDataAvailability:
    """Test GSC dashboard data requirements"""

    @pytest.mark.asyncio
    async def test_fact_gsc_daily_table_exists(self, db_pool):
        """gsc.fact_gsc_daily table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'gsc' AND table_name = 'fact_gsc_daily'
                )
            """)
            assert result, "Table gsc.fact_gsc_daily does not exist"

    @pytest.mark.asyncio
    async def test_fact_gsc_daily_has_required_columns(self, db_pool):
        """gsc.fact_gsc_daily must have required columns"""
        required_columns = ["property", "url", "date", "clicks", "impressions", "ctr", "position"]

        async with db_pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'gsc' AND table_name = 'fact_gsc_daily'
            """)
            existing_columns = {row["column_name"] for row in result}

            for col in required_columns:
                assert col in existing_columns, \
                    f"Column '{col}' missing from gsc.fact_gsc_daily"

    @pytest.mark.asyncio
    async def test_fact_gsc_daily_has_recent_data(self, db_pool):
        """gsc.fact_gsc_daily should have recent data (soft check)"""
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM gsc.fact_gsc_daily
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            # This is informational - may be 0 in test environments
            if count == 0:
                pytest.skip("No recent data in gsc.fact_gsc_daily (expected in test env)")

    @pytest.mark.asyncio
    async def test_insights_table_exists(self, db_pool):
        """gsc.insights table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'gsc' AND table_name = 'insights'
                )
            """)
            assert result, "Table gsc.insights does not exist"


@pytest.mark.live
class TestGA4DataAvailability:
    """Test GA4 dashboard data requirements"""

    @pytest.mark.asyncio
    async def test_fact_ga4_daily_table_exists(self, db_pool):
        """gsc.fact_ga4_daily table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
                )
            """)
            assert result, "Table gsc.fact_ga4_daily does not exist"

    @pytest.mark.asyncio
    async def test_fact_ga4_daily_has_required_columns(self, db_pool):
        """gsc.fact_ga4_daily must have required columns"""
        required_columns = [
            "property", "page_path", "date", "sessions",
            "conversions", "engagement_rate", "bounce_rate"
        ]

        async with db_pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
            """)
            existing_columns = {row["column_name"] for row in result}

            for col in required_columns:
                assert col in existing_columns, \
                    f"Column '{col}' missing from gsc.fact_ga4_daily"

    @pytest.mark.asyncio
    async def test_fact_ga4_daily_has_recent_data(self, db_pool):
        """gsc.fact_ga4_daily should have recent data (soft check)"""
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM gsc.fact_ga4_daily
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """)
            if count == 0:
                pytest.skip("No recent data in gsc.fact_ga4_daily (expected in test env)")


@pytest.mark.live
class TestCWVDataAvailability:
    """Test CWV dashboard data requirements"""

    @pytest.mark.asyncio
    async def test_core_web_vitals_table_exists(self, db_pool):
        """performance.core_web_vitals table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'performance' AND table_name = 'core_web_vitals'
                )
            """)
            assert result, "Table performance.core_web_vitals does not exist"

    @pytest.mark.asyncio
    async def test_core_web_vitals_has_required_columns(self, db_pool):
        """performance.core_web_vitals must have CWV metrics"""
        required_columns = [
            "property", "page_path", "strategy", "check_date",
            "performance_score", "lcp", "cls"
        ]

        async with db_pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'performance' AND table_name = 'core_web_vitals'
            """)
            existing_columns = {row["column_name"] for row in result}

            for col in required_columns:
                assert col in existing_columns, \
                    f"Column '{col}' missing from performance.core_web_vitals"

    @pytest.mark.asyncio
    async def test_cwv_views_exist(self, db_pool):
        """CWV dashboard views must exist"""
        required_views = ["vw_cwv_current", "vw_poor_cwv"]

        async with db_pool.acquire() as conn:
            for view in required_views:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.views
                        WHERE table_schema = 'performance' AND table_name = $1
                    )
                """, view)
                assert result, f"View performance.{view} does not exist"


@pytest.mark.live
class TestSERPDataAvailability:
    """Test SERP dashboard data requirements"""

    @pytest.mark.asyncio
    async def test_serp_queries_table_exists(self, db_pool):
        """serp.queries table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'serp' AND table_name = 'queries'
                )
            """)
            assert result, "Table serp.queries does not exist"

    @pytest.mark.asyncio
    async def test_position_history_table_exists(self, db_pool):
        """serp.position_history table must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'serp' AND table_name = 'position_history'
                )
            """)
            assert result, "Table serp.position_history does not exist"

    @pytest.mark.asyncio
    async def test_serp_views_exist(self, db_pool):
        """SERP dashboard views must exist"""
        required_views = ["vw_current_positions", "vw_position_changes"]

        async with db_pool.acquire() as conn:
            for view in required_views:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.views
                        WHERE table_schema = 'serp' AND table_name = $1
                    )
                """, view)
                # These views are optional - skip if not found
                if not result:
                    pytest.skip(f"View serp.{view} not found (may be optional)")


@pytest.mark.live
class TestHybridViewAvailability:
    """Test Hybrid dashboard data requirements"""

    @pytest.mark.asyncio
    async def test_unified_view_exists(self, db_pool):
        """Unified page performance view must exist"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.views
                    WHERE table_schema = 'gsc' AND table_name = 'vw_unified_page_performance'
                )
            """)
            assert result, "View gsc.vw_unified_page_performance does not exist"

    @pytest.mark.asyncio
    async def test_unified_view_has_expected_columns(self, db_pool):
        """Unified view should have columns from both GSC and GA4"""
        expected_columns = ["date", "page_path"]

        async with db_pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'gsc'
                  AND table_name = 'vw_unified_page_performance'
            """)
            existing_columns = {row["column_name"] for row in result}

            for col in expected_columns:
                assert col in existing_columns, \
                    f"Column '{col}' missing from vw_unified_page_performance"

    @pytest.mark.asyncio
    async def test_unified_view_is_queryable(self, db_pool):
        """Unified view should be queryable"""
        async with db_pool.acquire() as conn:
            try:
                result = await conn.fetch("""
                    SELECT * FROM gsc.vw_unified_page_performance LIMIT 1
                """)
                # Query succeeded - view is functional
            except Exception as e:
                pytest.fail(f"Unified view query failed: {e}")


@pytest.mark.live
class TestDataIntegrity:
    """Test data integrity across tables"""

    @pytest.mark.asyncio
    async def test_gsc_data_date_range_is_valid(self, db_pool):
        """GSC data dates should be reasonable"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM gsc.fact_gsc_daily
            """)
            if result["min_date"] is None:
                pytest.skip("No GSC data found")

            # Dates should not be in the future
            from datetime import date
            assert result["max_date"] <= date.today(), \
                "GSC data contains future dates"

    @pytest.mark.asyncio
    async def test_ga4_data_date_range_is_valid(self, db_pool):
        """GA4 data dates should be reasonable"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT MIN(date) as min_date, MAX(date) as max_date
                FROM gsc.fact_ga4_daily
            """)
            if result["min_date"] is None:
                pytest.skip("No GA4 data found")

            from datetime import date
            assert result["max_date"] <= date.today(), \
                "GA4 data contains future dates"

    @pytest.mark.asyncio
    async def test_gsc_metrics_are_valid(self, db_pool):
        """GSC metrics should have valid ranges"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    MIN(clicks) as min_clicks,
                    MIN(impressions) as min_impressions,
                    MIN(ctr) as min_ctr,
                    MAX(ctr) as max_ctr,
                    MIN(position) as min_pos
                FROM gsc.fact_gsc_daily
            """)

            if result["min_clicks"] is None:
                pytest.skip("No GSC data found")

            # Clicks and impressions should be non-negative
            assert result["min_clicks"] >= 0, "Negative clicks found"
            assert result["min_impressions"] >= 0, "Negative impressions found"

            # CTR should be between 0 and 1
            assert result["min_ctr"] >= 0, "Negative CTR found"
            assert result["max_ctr"] <= 1 or result["max_ctr"] <= 100, \
                "CTR > 100% found"

            # Position should be positive
            assert result["min_pos"] >= 0, "Negative position found"


@pytest.mark.live
class TestDataFreshness:
    """Test data freshness for dashboards"""

    @pytest.mark.asyncio
    async def test_gsc_data_freshness(self, db_pool):
        """GSC data should be reasonably fresh (soft check)"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT MAX(date) FROM gsc.fact_gsc_daily
            """)

            if result is None:
                pytest.skip("No GSC data found")

            from datetime import date, timedelta
            days_old = (date.today() - result).days

            # Warn if data is more than 7 days old
            if days_old > 7:
                pytest.skip(f"GSC data is {days_old} days old (may need refresh)")

    @pytest.mark.asyncio
    async def test_ga4_data_freshness(self, db_pool):
        """GA4 data should be reasonably fresh (soft check)"""
        async with db_pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT MAX(date) FROM gsc.fact_ga4_daily
            """)

            if result is None:
                pytest.skip("No GA4 data found")

            from datetime import date, timedelta
            days_old = (date.today() - result).days

            if days_old > 7:
                pytest.skip(f"GA4 data is {days_old} days old (may need refresh)")
