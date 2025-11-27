# Smoke Tests - Example Output

## Successful Run Example

```bash
$ pytest tests/smoke -m smoke -v

============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: C:\Users\prora\OneDrive\Documents\GitHub\site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
asyncio: mode=Mode.AUTO
collected 20 items

tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_database_connection PASSED [  5%]
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_schema_exists PASSED [ 10%]
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_core_tables_exist PASSED [ 15%]
tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_recent_data_exists PASSED [ 20%]
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[insights_api] PASSED [ 25%]
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[grafana] PASSED [ 30%]
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[prometheus] PASSED [ 35%]
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[metrics_exporter] PASSED [ 40%]
tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_health_details PASSED [ 45%]
tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_basic_query PASSED [ 50%]
tests/smoke/test_smoke.py::TestGrafanaConnectivity::test_grafana_datasources PASSED [ 55%]
tests/smoke/test_smoke.py::TestGrafanaConnectivity::test_grafana_login_page PASSED [ 60%]
tests/smoke/test_smoke.py::TestPrometheusConnectivity::test_prometheus_targets PASSED [ 65%]
tests/smoke/test_smoke.py::TestPrometheusConnectivity::test_prometheus_query PASSED [ 70%]
tests/smoke/test_smoke.py::TestMetricsExporter::test_metrics_endpoint PASSED [ 75%]
tests/smoke/test_smoke.py::TestMetricsExporter::test_metrics_exporter_health PASSED [ 80%]
tests/smoke/test_smoke.py::TestEndToEndSmoke::test_full_system_smoke PASSED [ 85%]
tests/smoke/test_smoke.py::TestDataFreshness::test_gsc_data_freshness PASSED [ 90%]
tests/smoke/test_smoke.py::TestDataFreshness::test_insights_freshness PASSED [ 95%]
tests/smoke/test_smoke.py::TestDataFreshness::test_multiple_properties PASSED [100%]

======================== 20 passed in 24.12s ========================
```

**Result**: ✓ All systems operational, deployment successful

---

## Failure Examples

### Database Connection Failure

```bash
$ pytest tests/smoke::TestDatabaseConnectivity -m smoke

tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_database_connection FAILED

================================== FAILURES ===================================
_______ TestDatabaseConnectivity.test_database_connection ________

    @pytest.mark.asyncio
    async def test_database_connection(self, db_pool: asyncpg.Pool):
        async with db_pool.acquire() as conn:
>           result = await conn.fetchval('SELECT 1')
E           asyncpg.exceptions.ConnectionDoesNotExistError: connection is closed

tests/smoke/test_smoke.py:88: ConnectionDoesNotExistError

======================== 1 failed in 2.34s ========================
```

**Diagnosis**: Database is not running or not accessible
**Action**: Check `docker-compose ps` and verify database service

---

### Service Not Reachable

```bash
$ pytest tests/smoke::TestServiceHealth::test_service_health_endpoint -m smoke

tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[insights_api] FAILED

================================== FAILURES ===================================
____ TestServiceHealth.test_service_health_endpoint[insights_api] ____

    @pytest.mark.parametrize('service_name,url,expected_status', SERVICE_ENDPOINTS)
    async def test_service_health_endpoint(
        self,
        http_client: httpx.AsyncClient,
        service_name: str,
        url: str,
        expected_status: int
    ):
        try:
            response = await http_client.get(url, follow_redirects=True)
            assert response.status_code == expected_status
        except httpx.ConnectError as e:
>           pytest.fail(
                f"{service_name} is not reachable at {url}: {str(e)}"
            )
E           Failed: insights_api is not reachable at http://localhost:8000/api/health:
E           [Errno 111] Connection refused

tests/smoke/test_smoke.py:221: Failed

======================== 1 failed in 1.45s ========================
```

**Diagnosis**: Insights API service is not running
**Action**: Start service with `docker-compose up -d insights_api`

---

### Stale Data Warning

```bash
$ pytest tests/smoke::TestDataFreshness -m smoke

tests/smoke/test_smoke.py::TestDataFreshness::test_recent_data_exists FAILED

================================== FAILURES ===================================
_______ TestDatabaseConnectivity.test_recent_data_exists ________

    @pytest.mark.asyncio
    async def test_recent_data_exists(self, db_pool: asyncpg.Pool):
        async with db_pool.acquire() as conn:
            recent_gsc = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM gsc.fact_gsc_daily
                    WHERE date >= CURRENT_DATE - INTERVAL '2 days'
                    LIMIT 1
                )
                """
            )

            recent_insights = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM gsc.insights
                    WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '2 days'
                    LIMIT 1
                )
                """
            )

            has_recent_data = recent_gsc or recent_insights

            if not has_recent_data:
                latest_gsc = await conn.fetchval(
                    "SELECT MAX(date) FROM gsc.fact_gsc_daily"
                )
                latest_insight = await conn.fetchval(
                    "SELECT MAX(generated_at) FROM gsc.insights"
                )

>               pytest.fail(
                    f"No recent data found. "
                    f"Latest GSC data: {latest_gsc}, "
                    f"Latest insight: {latest_insight}"
                )
E               Failed: No recent data found. Latest GSC data: 2025-11-20,
E               Latest insight: 2025-11-21 08:30:45

tests/smoke/test_smoke.py:170: Failed

======================== 1 failed in 3.21s ========================
```

**Diagnosis**: Data collection hasn't run recently (GSC: 7 days old, Insights: 6 days old)
**Action**: Check schedulers - `docker-compose logs scheduler`

---

### Fresh Installation (Skip)

```bash
$ pytest tests/smoke::TestDataFreshness::test_gsc_data_freshness -m smoke

tests/smoke/test_smoke.py::TestDataFreshness::test_gsc_data_freshness SKIPPED

=========================== skipped test summary ===========================
SKIPPED [1] tests/smoke/test_smoke.py:470: No GSC data found - may be initial setup

======================== 1 skipped in 2.01s ========================
```

**Status**: Expected on fresh installation
**Action**: Run data collection, then re-test

---

### Timeout Error

```bash
$ pytest tests/smoke::TestServiceHealth -m smoke

tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_health_details FAILED

================================== FAILURES ===================================
____ TestServiceHealth.test_insights_api_health_details ____

    @pytest.mark.asyncio
    async def test_insights_api_health_details(self, http_client: httpx.AsyncClient):
        try:
            response = await http_client.get(f'{API_URL}/health')
        except httpx.TimeoutException:
>           pytest.fail(
                f"insights_api health check timed out at {API_URL}/health"
            )
E           Failed: insights_api health check timed out at http://localhost:8000/api/health

tests/smoke/test_smoke.py:256: Failed

======================== 1 failed in 10.34s ========================
```

**Diagnosis**: Service is slow to respond (> 10 second timeout)
**Action**: Check service resource usage and database performance

---

## Quick Start Run

```bash
$ pytest tests/smoke -m smoke --tb=short

============================= test session starts =============================
collected 20 items

tests/smoke/test_smoke.py ....................                          [100%]

======================== 20 passed in 23.87s ========================
```

**Result**: ✓ Quick verification complete, all systems operational

---

## Verbose Run with Detailed Output

```bash
$ pytest tests/smoke -m smoke -vv

============================= test session starts =============================
collected 20 items

tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_database_connection
    Test database connection is successful.

    Verifies:
    - Database is reachable
    - Connection pool can acquire connection
    - Basic query executes
PASSED [ 5%]

tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_schema_exists
    Test core schema exists.

    Verifies:
    - gsc schema is present
PASSED [ 10%]

tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_core_tables_exist
    Test critical tables exist.

    Verifies:
    - fact_gsc_daily table exists
    - insights table exists
PASSED [ 15%]

[... continued for all 20 tests ...]

======================== 20 passed in 25.43s ========================
```

---

## Stop on First Failure

```bash
$ pytest tests/smoke -m smoke -x

============================= test session starts =============================
collected 20 items

tests/smoke/test_smoke.py ....F

================================== FAILURES ===================================
[... failure details ...]

!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!
======================== 1 failed, 4 passed in 8.21s ========================
```

**Use Case**: Fast failure detection, stop immediately when issue found

---

## Select Tests by Class

```bash
$ pytest tests/smoke::TestServiceHealth -m smoke

============================= test session starts =============================
collected 6 items

tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[insights_api] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[grafana] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[prometheus] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[metrics_exporter] PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_health_details PASSED
tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_basic_query PASSED

======================== 6 passed in 12.34s ========================
```

**Use Case**: Test only service health endpoints

---

## Docker Container Execution

```bash
$ docker-compose exec api pytest tests/smoke -m smoke

============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
collected 20 items

tests/smoke/test_smoke.py ....................                          [100%]

======================== 20 passed in 22.76s ========================
```

**Use Case**: Run tests inside container with container network

---

## CI/CD Output (GitHub Actions)

```yaml
Run pytest tests/smoke -m smoke --tb=short
  pytest tests/smoke -m smoke --tb=short
  shell: /usr/bin/bash -e {0}
  env:
    WAREHOUSE_DSN: postgresql://user:pass@db:5432/warehouse
    API_URL: http://insights_api:8000

============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
collected 20 items

tests/smoke/test_smoke.py ....................                          [100%]

======================== 20 passed in 21.45s ========================

✓ Smoke Tests - 20 tests passed in 21.45s
```

---

## Performance Timing

```bash
$ pytest tests/smoke -m smoke --durations=10

============================= test session starts =============================
collected 20 items

tests/smoke/test_smoke.py ....................                          [100%]

======================== slowest 10 durations ========================
4.23s call     tests/smoke/test_smoke.py::TestEndToEndSmoke::test_full_system_smoke
3.12s call     tests/smoke/test_smoke.py::TestServiceHealth::test_insights_api_basic_query
2.87s call     tests/smoke/test_smoke.py::TestDatabaseConnectivity::test_recent_data_exists
2.45s call     tests/smoke/test_smoke.py::TestDataFreshness::test_gsc_data_freshness
2.34s call     tests/smoke/test_smoke.py::TestDataFreshness::test_insights_freshness
1.98s call     tests/smoke/test_smoke.py::TestPrometheusConnectivity::test_prometheus_query
1.76s call     tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[insights_api]
1.65s call     tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[grafana]
1.54s call     tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[prometheus]
1.43s call     tests/smoke/test_smoke.py::TestServiceHealth::test_service_health_endpoint[metrics_exporter]

======================== 20 passed in 24.37s ========================
```

**Analysis**: All tests complete well under timeout limits

---

## Summary Statistics

### All Passing
```
======================== 20 passed in 24.12s ========================
```

### With Failures
```
======================== 15 passed, 5 failed in 18.45s ========================
```

### With Skips
```
======================== 18 passed, 2 skipped in 22.01s ========================
```

### Mixed
```
======================== 12 passed, 5 failed, 3 skipped in 16.78s ========================
```
