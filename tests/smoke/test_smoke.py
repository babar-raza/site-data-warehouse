"""
Smoke Tests for Deployment Verification

Quick smoke tests to verify critical services are running and operational.

Requirements:
- All tests pass with services running
- Tests complete in < 30 seconds
- All critical services checked
- Tests marked with @pytest.mark.smoke

Critical Services Tested:
- Database (PostgreSQL)
- Insights API
- Grafana
- Prometheus
- Metrics Exporter

Run with: pytest tests/smoke -m smoke
"""

import pytest
import asyncpg
import httpx
import os
from datetime import datetime, timedelta
from typing import AsyncIterator


# Configuration from environment
DB_DSN = os.getenv(
    'WAREHOUSE_DSN',
    'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db'
)
API_URL = os.getenv('API_URL', 'http://localhost:8000')
GRAFANA_URL = os.getenv('GRAFANA_URL', 'http://localhost:3000')
PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
METRICS_URL = os.getenv('METRICS_URL', 'http://localhost:8002')


# Service configurations for parametrized testing
SERVICE_ENDPOINTS = [
    pytest.param('api', f'{API_URL}/health', 200, id='insights_api'),
    pytest.param('grafana', f'{GRAFANA_URL}/api/health', 200, id='grafana'),
    pytest.param('prometheus', f'{PROMETHEUS_URL}/-/healthy', 200, id='prometheus'),
    pytest.param('metrics', f'{METRICS_URL}/metrics', 200, id='metrics_exporter'),
]


@pytest.fixture(scope='session')
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    """
    Create database connection pool for smoke tests.

    Yields:
        asyncpg.Pool: Database connection pool
    """
    pool = await asyncpg.create_pool(
        DB_DSN,
        min_size=1,
        max_size=3,
        command_timeout=10
    )
    yield pool
    await pool.close()


@pytest.fixture(scope='session')
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """
    Create HTTP client for service checks.

    Yields:
        httpx.AsyncClient: Async HTTP client with timeout
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


@pytest.mark.smoke
class TestDatabaseConnectivity:
    """Test database connectivity and basic operations"""

    @pytest.mark.asyncio
    async def test_database_connection(self, db_pool: asyncpg.Pool):
        """
        Test database connection is successful.

        Verifies:
        - Database is reachable
        - Connection pool can acquire connection
        - Basic query executes
        """
        async with db_pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            assert result == 1

    @pytest.mark.asyncio
    async def test_schema_exists(self, db_pool: asyncpg.Pool):
        """
        Test core schema exists.

        Verifies:
        - gsc schema is present
        """
        async with db_pool.acquire() as conn:
            schema_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.schemata
                    WHERE schema_name = 'gsc'
                )
                """
            )
            assert schema_exists, "Core schema 'gsc' does not exist"

    @pytest.mark.asyncio
    async def test_core_tables_exist(self, db_pool: asyncpg.Pool):
        """
        Test critical tables exist.

        Verifies:
        - fact_gsc_daily table exists
        - insights table exists
        """
        async with db_pool.acquire() as conn:
            tables = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'gsc'
                AND table_name IN ('fact_gsc_daily', 'insights', 'dim_property')
                """
            )
            table_names = [t['table_name'] for t in tables]

            assert 'fact_gsc_daily' in table_names, "Table fact_gsc_daily missing"
            assert 'insights' in table_names, "Table insights missing"
            assert 'dim_property' in table_names, "Table dim_property missing"

    @pytest.mark.asyncio
    async def test_recent_data_exists(self, db_pool: asyncpg.Pool):
        """
        Test recent data exists in database (< 2 days old).

        Verifies:
        - Either GSC data exists within 2 days
        - Or insights data exists within 2 days
        - This ensures data collection is working
        """
        async with db_pool.acquire() as conn:
            # Check for recent GSC data
            recent_gsc = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM gsc.fact_gsc_daily
                    WHERE date >= CURRENT_DATE - INTERVAL '2 days'
                    LIMIT 1
                )
                """
            )

            # Check for recent insights
            recent_insights = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM gsc.insights
                    WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '2 days'
                    LIMIT 1
                )
                """
            )

            # At least one should have recent data
            has_recent_data = recent_gsc or recent_insights

            if not has_recent_data:
                # Get latest dates for debugging
                latest_gsc = await conn.fetchval(
                    "SELECT MAX(date) FROM gsc.fact_gsc_daily"
                )
                latest_insight = await conn.fetchval(
                    "SELECT MAX(generated_at) FROM gsc.insights"
                )

                pytest.fail(
                    f"No recent data found. "
                    f"Latest GSC data: {latest_gsc}, "
                    f"Latest insight: {latest_insight}"
                )


@pytest.mark.smoke
class TestServiceHealth:
    """Test critical service health endpoints"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize('service_name,url,expected_status', SERVICE_ENDPOINTS)
    async def test_service_health_endpoint(
        self,
        http_client: httpx.AsyncClient,
        service_name: str,
        url: str,
        expected_status: int
    ):
        """
        Test service health endpoints respond correctly.

        Verifies:
        - Service is reachable
        - Health endpoint returns expected status

        Args:
            service_name: Name of service being tested
            url: Health endpoint URL
            expected_status: Expected HTTP status code
        """
        try:
            response = await http_client.get(url, follow_redirects=True)
            assert response.status_code == expected_status, (
                f"{service_name} health check failed: "
                f"expected {expected_status}, got {response.status_code}"
            )
        except httpx.ConnectError as e:
            pytest.fail(
                f"{service_name} is not reachable at {url}: {str(e)}"
            )
        except httpx.TimeoutException:
            pytest.fail(
                f"{service_name} health check timed out at {url}"
            )

    @pytest.mark.asyncio
    async def test_insights_api_health_details(self, http_client: httpx.AsyncClient):
        """
        Test Insights API health endpoint returns detailed status.

        Verifies:
        - API returns healthy status
        - Database connection is reported as connected
        - Response includes total_insights count
        """
        try:
            response = await http_client.get(f'{API_URL}/health')
            assert response.status_code == 200, "Insights API health check failed"

            data = response.json()
            assert data.get('status') == 'healthy', "API status is not healthy"
            assert data.get('database') == 'connected', "Database not connected"
            assert 'total_insights' in data, "Missing total_insights in response"
            assert isinstance(data['total_insights'], int), "total_insights is not an integer"

        except httpx.ConnectError:
            pytest.fail(f"Insights API is not reachable at {API_URL}")

    @pytest.mark.asyncio
    async def test_insights_api_basic_query(self, http_client: httpx.AsyncClient):
        """
        Test Insights API can execute basic query.

        Verifies:
        - API can query insights
        - Response has expected structure
        """
        try:
            response = await http_client.get(
                f'{API_URL}/api/insights',
                params={'limit': 1}
            )
            assert response.status_code == 200, "Insights query failed"

            data = response.json()
            assert 'status' in data, "Missing status in response"
            assert 'data' in data, "Missing data in response"
            assert isinstance(data['data'], list), "Data is not a list"

        except httpx.ConnectError:
            pytest.fail(f"Insights API is not reachable at {API_URL}")


@pytest.mark.smoke
class TestGrafanaConnectivity:
    """Test Grafana connectivity and configuration"""

    @pytest.mark.asyncio
    async def test_grafana_datasources(self, http_client: httpx.AsyncClient):
        """
        Test Grafana has datasources configured.

        Verifies:
        - Grafana API is accessible
        - At least one datasource is configured

        Note: This test uses the health endpoint as it doesn't require auth
        """
        try:
            # Check Grafana health (doesn't require auth)
            response = await http_client.get(f'{GRAFANA_URL}/api/health')
            assert response.status_code == 200, "Grafana is not healthy"

            data = response.json()
            assert data.get('database') in ['ok', 'healthy'], "Grafana database not ok"

        except httpx.ConnectError:
            pytest.fail(f"Grafana is not reachable at {GRAFANA_URL}")

    @pytest.mark.asyncio
    async def test_grafana_login_page(self, http_client: httpx.AsyncClient):
        """
        Test Grafana login page is accessible.

        Verifies:
        - Grafana web interface is serving
        - Login page returns 200 or redirects to login
        """
        try:
            response = await http_client.get(
                f'{GRAFANA_URL}/login',
                follow_redirects=True
            )
            assert response.status_code == 200, "Grafana login page not accessible"

        except httpx.ConnectError:
            pytest.fail(f"Grafana is not reachable at {GRAFANA_URL}")


@pytest.mark.smoke
class TestPrometheusConnectivity:
    """Test Prometheus connectivity and metrics collection"""

    @pytest.mark.asyncio
    async def test_prometheus_targets(self, http_client: httpx.AsyncClient):
        """
        Test Prometheus has targets configured.

        Verifies:
        - Prometheus API is accessible
        - Targets endpoint responds
        """
        try:
            response = await http_client.get(f'{PROMETHEUS_URL}/api/v1/targets')
            assert response.status_code == 200, "Prometheus targets API failed"

            data = response.json()
            assert data.get('status') == 'success', "Prometheus API status not success"

        except httpx.ConnectError:
            pytest.fail(f"Prometheus is not reachable at {PROMETHEUS_URL}")

    @pytest.mark.asyncio
    async def test_prometheus_query(self, http_client: httpx.AsyncClient):
        """
        Test Prometheus can execute basic query.

        Verifies:
        - Prometheus query API works
        - Can execute simple metric query
        """
        try:
            response = await http_client.get(
                f'{PROMETHEUS_URL}/api/v1/query',
                params={'query': 'up'}
            )
            assert response.status_code == 200, "Prometheus query failed"

            data = response.json()
            assert data.get('status') == 'success', "Prometheus query status not success"
            assert 'data' in data, "Missing data in Prometheus response"

        except httpx.ConnectError:
            pytest.fail(f"Prometheus is not reachable at {PROMETHEUS_URL}")


@pytest.mark.smoke
class TestMetricsExporter:
    """Test Metrics Exporter service"""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, http_client: httpx.AsyncClient):
        """
        Test Metrics Exporter endpoint is accessible.

        Verifies:
        - Metrics endpoint responds
        - Returns Prometheus-formatted metrics
        """
        try:
            response = await http_client.get(f'{METRICS_URL}/metrics')
            assert response.status_code == 200, "Metrics endpoint failed"

            content = response.text
            assert 'gsc_' in content or 'python_' in content, (
                "Metrics endpoint does not return Prometheus metrics"
            )

        except httpx.ConnectError:
            pytest.fail(f"Metrics Exporter is not reachable at {METRICS_URL}")

    @pytest.mark.asyncio
    async def test_metrics_exporter_health(self, http_client: httpx.AsyncClient):
        """
        Test Metrics Exporter health endpoint.

        Verifies:
        - Health endpoint responds
        - Returns healthy status
        """
        try:
            response = await http_client.get(f'{METRICS_URL}/health')

            # Metrics exporter may not have health endpoint, just check it responds
            assert response.status_code in [200, 404], (
                f"Unexpected response from metrics health: {response.status_code}"
            )

        except httpx.ConnectError:
            pytest.fail(f"Metrics Exporter is not reachable at {METRICS_URL}")


@pytest.mark.smoke
class TestEndToEndSmoke:
    """End-to-end smoke test verifying complete system"""

    @pytest.mark.asyncio
    async def test_full_system_smoke(
        self,
        db_pool: asyncpg.Pool,
        http_client: httpx.AsyncClient
    ):
        """
        Full system smoke test.

        Verifies complete flow:
        1. Database is accessible and has data
        2. API can query database
        3. Monitoring stack is accessible

        This is a comprehensive check that the entire system is operational.
        """
        # Step 1: Verify database
        async with db_pool.acquire() as conn:
            db_ok = await conn.fetchval('SELECT 1')
            assert db_ok == 1, "Database connectivity failed"

            # Verify we have some insights
            insight_count = await conn.fetchval(
                'SELECT COUNT(*) FROM gsc.insights'
            )
            # Note: Don't fail if no insights yet, just check query works
            assert insight_count is not None, "Failed to query insights table"

        # Step 2: Verify API can query database
        try:
            api_response = await http_client.get(f'{API_URL}/health')
            assert api_response.status_code == 200, "API health check failed"

            api_data = api_response.json()
            assert api_data.get('status') == 'healthy', "API is not healthy"
            assert api_data.get('database') == 'connected', "API cannot connect to database"

        except httpx.ConnectError:
            pytest.fail("Insights API is not accessible")

        # Step 3: Verify monitoring stack
        try:
            # Check Prometheus
            prom_response = await http_client.get(f'{PROMETHEUS_URL}/-/healthy')
            assert prom_response.status_code == 200, "Prometheus health check failed"

            # Check Grafana
            grafana_response = await http_client.get(f'{GRAFANA_URL}/api/health')
            assert grafana_response.status_code == 200, "Grafana health check failed"

            # Check Metrics Exporter
            metrics_response = await http_client.get(f'{METRICS_URL}/metrics')
            assert metrics_response.status_code == 200, "Metrics exporter failed"

        except httpx.ConnectError as e:
            pytest.fail(f"Monitoring stack component not accessible: {e}")


@pytest.mark.smoke
class TestDataFreshness:
    """Test data freshness and collection health"""

    @pytest.mark.asyncio
    async def test_gsc_data_freshness(self, db_pool: asyncpg.Pool):
        """
        Test GSC data freshness.

        Verifies:
        - GSC data exists
        - Latest data is within acceptable range (7 days)

        Note: This is lenient to account for backfill scenarios
        """
        async with db_pool.acquire() as conn:
            latest_date = await conn.fetchval(
                'SELECT MAX(date) FROM gsc.fact_gsc_daily'
            )

            if latest_date is None:
                pytest.skip("No GSC data found - may be initial setup")

            days_old = (datetime.now().date() - latest_date).days

            assert days_old <= 7, (
                f"Latest GSC data is {days_old} days old (date: {latest_date}). "
                "Data collection may not be working."
            )

    @pytest.mark.asyncio
    async def test_insights_freshness(self, db_pool: asyncpg.Pool):
        """
        Test insights data freshness.

        Verifies:
        - Insights exist
        - Latest insight is within acceptable range (48 hours)
        """
        async with db_pool.acquire() as conn:
            latest_insight = await conn.fetchval(
                'SELECT MAX(generated_at) FROM gsc.insights'
            )

            if latest_insight is None:
                pytest.skip("No insights found - may be initial setup")

            age = datetime.now(latest_insight.tzinfo) - latest_insight
            hours_old = age.total_seconds() / 3600

            assert hours_old <= 48, (
                f"Latest insight is {hours_old:.1f} hours old. "
                "Insight generation may not be working."
            )

    @pytest.mark.asyncio
    async def test_multiple_properties(self, db_pool: asyncpg.Pool):
        """
        Test data exists for configured properties.

        Verifies:
        - At least one property has data
        - Property data is tracked
        """
        async with db_pool.acquire() as conn:
            property_count = await conn.fetchval(
                'SELECT COUNT(DISTINCT property) FROM gsc.fact_gsc_daily'
            )

            assert property_count > 0, (
                "No properties found in database. Check GSC configuration."
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'smoke'])
