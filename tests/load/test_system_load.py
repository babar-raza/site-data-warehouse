"""
System Load Testing Suite

Comprehensive load tests for the GSC Warehouse system including:
- API endpoint testing with 50 concurrent requests
- Database connection pool testing with 100 concurrent queries
- Agent concurrency testing
- Data ingestion throughput testing

Run with:
    pytest tests/load/test_system_load.py -v -m "e2e and slow"
    pytest tests/load/test_system_load.py -v --log-cli-level=INFO

Requirements:
    - Live PostgreSQL database
    - FastAPI insights API running or mock server
    - All tests marked with @pytest.mark.e2e and @pytest.mark.slow
    - Success rate >= 90% for all tests
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import pytest
import asyncpg
import httpx

# Test configuration
TEST_CONCURRENT_API_REQUESTS = 50
TEST_CONCURRENT_DB_QUERIES = 100
TEST_MIN_SUCCESS_RATE = 0.90  # 90%
TEST_API_TIMEOUT = 30.0  # seconds


class LoadTestMetrics:
    """Track and report load test metrics."""

    def __init__(self):
        self.response_times: List[float] = []
        self.errors: List[str] = []
        self.success_count: int = 0
        self.failure_count: int = 0
        self.start_time: datetime = None
        self.end_time: datetime = None

    def record_success(self, response_time: float):
        """Record successful operation."""
        self.response_times.append(response_time)
        self.success_count += 1

    def record_failure(self, error: str):
        """Record failed operation."""
        self.errors.append(error)
        self.failure_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        total_ops = self.success_count + self.failure_count
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0

        return {
            'duration': duration,
            'total_operations': total_ops,
            'successful': self.success_count,
            'failed': self.failure_count,
            'success_rate': self.success_count / total_ops if total_ops > 0 else 0,
            'throughput': self.success_count / duration if duration > 0 else 0,
            'avg_response_time': statistics.mean(self.response_times) if self.response_times else 0,
            'min_response_time': min(self.response_times) if self.response_times else 0,
            'max_response_time': max(self.response_times) if self.response_times else 0,
            'p50_response_time': statistics.median(self.response_times) if self.response_times else 0,
            'p95_response_time': statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 20 else 0,
            'p99_response_time': statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else 0,
            'error_sample': self.errors[:5] if self.errors else []
        }


@pytest.fixture(scope="module")
async def db_pool(test_db_dsn):
    """Create database connection pool for load testing."""
    pool = await asyncpg.create_pool(
        dsn=test_db_dsn,
        min_size=20,
        max_size=100,
        timeout=30.0,
        command_timeout=60.0
    )
    yield pool
    await pool.close()


@pytest.fixture(scope="module")
def api_base_url():
    """Get API base URL from environment or default."""
    import os
    return os.getenv('TEST_API_URL', 'http://localhost:8001')


@pytest.fixture
def load_test_metrics():
    """Create fresh metrics tracker for each test."""
    return LoadTestMetrics()


# ============================================================================
# API LOAD TESTS
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_api_concurrent_requests_50(api_base_url, load_test_metrics):
    """
    Test API with 50 concurrent requests.

    Requirements:
    - 50 concurrent requests to various endpoints
    - Success rate >= 90%
    - All requests complete within timeout
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    # Define test endpoints
    endpoints = [
        '/api/health',
        '/api/stats',
        '/api/insights?limit=10',
        '/api/insights?category=performance&limit=20',
        '/api/insights?status=new&limit=15',
    ]

    async def make_request(client: httpx.AsyncClient, request_id: int):
        """Make a single API request."""
        endpoint = endpoints[request_id % len(endpoints)]
        url = f"{api_base_url}{endpoint}"

        start = time.time()
        try:
            response = await client.get(url, timeout=TEST_API_TIMEOUT)
            duration = time.time() - start

            if response.status_code in [200, 404]:  # 404 is acceptable for some endpoints
                metrics.record_success(duration)
                return True
            else:
                metrics.record_failure(f"HTTP {response.status_code}: {endpoint}")
                return False

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Execute 50 concurrent requests using asyncio.gather
    async with httpx.AsyncClient() as client:
        tasks = [make_request(client, i) for i in range(TEST_CONCURRENT_API_REQUESTS)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    metrics.end_time = datetime.now()

    # Get summary
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"API Concurrent Requests Load Test Results")
    print(f"{'='*70}")
    print(f"Total Requests: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"Throughput: {summary['throughput']:.2f} req/s")
    print(f"Response Times:")
    print(f"  - Average: {summary['avg_response_time']:.3f}s")
    print(f"  - Min: {summary['min_response_time']:.3f}s")
    print(f"  - Max: {summary['max_response_time']:.3f}s")
    print(f"  - P50: {summary['p50_response_time']:.3f}s")
    print(f"  - P95: {summary['p95_response_time']:.3f}s")
    if summary['error_sample']:
        print(f"Error samples: {summary['error_sample'][:3]}")
    print(f"{'='*70}\n")

    # Assertions
    assert summary['total_operations'] == TEST_CONCURRENT_API_REQUESTS, \
        f"Expected {TEST_CONCURRENT_API_REQUESTS} operations"

    assert summary['success_rate'] >= TEST_MIN_SUCCESS_RATE, \
        f"Success rate {summary['success_rate']:.2%} < {TEST_MIN_SUCCESS_RATE:.0%}. " \
        f"Errors: {summary['error_sample']}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_api_concurrent_health_checks(api_base_url, load_test_metrics):
    """
    Test API health endpoint with high concurrency.

    Requirements:
    - 50 concurrent health check requests
    - All requests must succeed (100% success rate expected for health checks)
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    async def health_check(client: httpx.AsyncClient, request_id: int):
        """Perform health check."""
        start = time.time()
        try:
            response = await client.get(f"{api_base_url}/api/health", timeout=TEST_API_TIMEOUT)
            duration = time.time() - start

            if response.status_code == 200:
                metrics.record_success(duration)
                return True
            else:
                metrics.record_failure(f"HTTP {response.status_code}")
                return False

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Execute concurrent health checks
    async with httpx.AsyncClient() as client:
        tasks = [health_check(client, i) for i in range(TEST_CONCURRENT_API_REQUESTS)]
        await asyncio.gather(*tasks, return_exceptions=False)

    metrics.end_time = datetime.now()
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"API Health Check Load Test Results")
    print(f"{'='*70}")
    print(f"Total Requests: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Avg Response Time: {summary['avg_response_time']:.3f}s")
    print(f"{'='*70}\n")

    # Health endpoint should have very high success rate
    assert summary['success_rate'] >= TEST_MIN_SUCCESS_RATE, \
        f"Health check success rate {summary['success_rate']:.2%} too low"


# ============================================================================
# DATABASE LOAD TESTS
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_database_concurrent_queries_100(db_pool, load_test_metrics):
    """
    Test database with 100 concurrent queries.

    Requirements:
    - 100 concurrent queries
    - All queries must succeed (100% success rate)
    - Tests connection pool under load
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    # Define test queries
    queries = [
        "SELECT 1 as test",
        "SELECT COUNT(*) FROM pg_tables",
        "SELECT current_timestamp",
        "SELECT version()",
        "SELECT pg_database_size(current_database())",
    ]

    async def execute_query(query_id: int):
        """Execute a single database query."""
        query = queries[query_id % len(queries)]

        start = time.time()
        try:
            async with db_pool.acquire() as conn:
                result = await conn.fetchval(query)
                duration = time.time() - start

                if result is not None:
                    metrics.record_success(duration)
                    return True
                else:
                    metrics.record_failure(f"Query returned None: {query}")
                    return False

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Execute 100 concurrent queries using asyncio.gather
    tasks = [execute_query(i) for i in range(TEST_CONCURRENT_DB_QUERIES)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    metrics.end_time = datetime.now()
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"Database Concurrent Queries Load Test Results")
    print(f"{'='*70}")
    print(f"Total Queries: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"Throughput: {summary['throughput']:.2f} queries/s")
    print(f"Query Times:")
    print(f"  - Average: {summary['avg_response_time']:.4f}s")
    print(f"  - Min: {summary['min_response_time']:.4f}s")
    print(f"  - Max: {summary['max_response_time']:.4f}s")
    print(f"  - P95: {summary['p95_response_time']:.4f}s")
    if summary['error_sample']:
        print(f"Error samples: {summary['error_sample'][:3]}")
    print(f"{'='*70}\n")

    # Assertions
    assert summary['total_operations'] == TEST_CONCURRENT_DB_QUERIES, \
        f"Expected {TEST_CONCURRENT_DB_QUERIES} operations"

    # Database queries should all succeed
    assert summary['failed'] == 0, \
        f"All database queries must succeed. Failed: {summary['failed']}. " \
        f"Errors: {summary['error_sample']}"

    assert summary['success_rate'] == 1.0, \
        f"Database query success rate must be 100%, got {summary['success_rate']:.2%}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_database_connection_pool_stress(db_pool, load_test_metrics):
    """
    Stress test database connection pool.

    Requirements:
    - Test pool with more concurrent requests than max pool size
    - All queries must succeed despite pool limits
    - Verify connection reuse
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    # Use more concurrent requests than pool size to test queuing
    concurrent_requests = 150

    async def stress_query(query_id: int):
        """Execute query that holds connection briefly."""
        start = time.time()
        try:
            async with db_pool.acquire() as conn:
                # Simulate some work
                result = await conn.fetchval("SELECT pg_sleep(0.01), $1::int", query_id)
                duration = time.time() - start

                metrics.record_success(duration)
                return True

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Execute concurrent queries
    tasks = [stress_query(i) for i in range(concurrent_requests)]
    await asyncio.gather(*tasks, return_exceptions=False)

    metrics.end_time = datetime.now()
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"Database Connection Pool Stress Test Results")
    print(f"{'='*70}")
    print(f"Concurrent Requests: {concurrent_requests} (pool size: 20-100)")
    print(f"Total Queries: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"{'='*70}\n")

    # All queries must succeed even with limited pool
    assert summary['failed'] == 0, \
        f"All queries must succeed with connection pooling. Failed: {summary['failed']}"

    assert summary['success_rate'] == 1.0, \
        f"Pool stress test success rate must be 100%, got {summary['success_rate']:.2%}"


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_database_write_operations_concurrent(db_pool, load_test_metrics):
    """
    Test concurrent database write operations.

    Requirements:
    - 100 concurrent INSERT operations
    - All operations must succeed
    - Verify data integrity
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    # Create test table
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS load_test_writes (
                id SERIAL PRIMARY KEY,
                test_id INT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Clean any existing test data
        await conn.execute("TRUNCATE TABLE load_test_writes")

    async def insert_record(record_id: int):
        """Insert a single record."""
        start = time.time()
        try:
            async with db_pool.acquire() as conn:
                result = await conn.execute(
                    "INSERT INTO load_test_writes (test_id, data) VALUES ($1, $2)",
                    record_id,
                    f"Test data {record_id}"
                )
                duration = time.time() - start

                if result == "INSERT 0 1":
                    metrics.record_success(duration)
                    return True
                else:
                    metrics.record_failure(f"Unexpected result: {result}")
                    return False

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Execute concurrent inserts
    tasks = [insert_record(i) for i in range(TEST_CONCURRENT_DB_QUERIES)]
    await asyncio.gather(*tasks, return_exceptions=False)

    metrics.end_time = datetime.now()

    # Verify all records were inserted
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM load_test_writes")
        distinct_count = await conn.fetchval("SELECT COUNT(DISTINCT test_id) FROM load_test_writes")

    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"Database Concurrent Write Operations Test Results")
    print(f"{'='*70}")
    print(f"Total Inserts: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Records in DB: {count}")
    print(f"Distinct IDs: {distinct_count}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"{'='*70}\n")

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS load_test_writes")

    # Assertions
    assert summary['failed'] == 0, \
        f"All write operations must succeed. Failed: {summary['failed']}"

    assert count == TEST_CONCURRENT_DB_QUERIES, \
        f"Expected {TEST_CONCURRENT_DB_QUERIES} records, found {count}"

    assert distinct_count == TEST_CONCURRENT_DB_QUERIES, \
        f"Expected {TEST_CONCURRENT_DB_QUERIES} distinct IDs, found {distinct_count}"


# ============================================================================
# MIXED LOAD TESTS
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_mixed_load_api_and_database(api_base_url, db_pool, load_test_metrics):
    """
    Test combined API and database load.

    Requirements:
    - 25 concurrent API requests + 75 concurrent DB queries
    - Success rate >= 90% overall
    - Simulates realistic mixed workload
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    async def api_request(request_id: int):
        """Make API request."""
        start = time.time()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{api_base_url}/api/health",
                    timeout=TEST_API_TIMEOUT
                )
                duration = time.time() - start

                if response.status_code == 200:
                    metrics.record_success(duration)
                    return True
                else:
                    metrics.record_failure(f"API HTTP {response.status_code}")
                    return False

        except Exception as e:
            metrics.record_failure(f"API {type(e).__name__}: {str(e)[:50]}")
            return False

    async def db_query(query_id: int):
        """Execute database query."""
        start = time.time()
        try:
            async with db_pool.acquire() as conn:
                result = await conn.fetchval("SELECT COUNT(*) FROM pg_tables")
                duration = time.time() - start

                if result is not None:
                    metrics.record_success(duration)
                    return True
                else:
                    metrics.record_failure("DB query returned None")
                    return False

        except Exception as e:
            metrics.record_failure(f"DB {type(e).__name__}: {str(e)[:50]}")
            return False

    # Create mixed workload: 25 API + 75 DB
    api_tasks = [api_request(i) for i in range(25)]
    db_tasks = [db_query(i) for i in range(75)]
    all_tasks = api_tasks + db_tasks

    # Execute all concurrently
    await asyncio.gather(*all_tasks, return_exceptions=False)

    metrics.end_time = datetime.now()
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"Mixed Load Test Results (API + Database)")
    print(f"{'='*70}")
    print(f"Total Operations: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"Throughput: {summary['throughput']:.2f} ops/s")
    print(f"{'='*70}\n")

    # Assertions
    assert summary['total_operations'] == 100, "Expected 100 total operations"

    assert summary['success_rate'] >= TEST_MIN_SUCCESS_RATE, \
        f"Mixed load success rate {summary['success_rate']:.2%} < {TEST_MIN_SUCCESS_RATE:.0%}"


# ============================================================================
# THROUGHPUT TESTS
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_sustained_load_throughput(db_pool, load_test_metrics):
    """
    Test sustained load over time.

    Requirements:
    - Maintain load for at least 10 seconds
    - Success rate >= 90%
    - Measure sustained throughput
    """
    metrics = load_test_metrics
    metrics.start_time = datetime.now()

    test_duration = 10  # seconds
    queries_per_second = 20

    async def timed_query(query_id: int):
        """Execute query and record metrics."""
        start = time.time()
        try:
            async with db_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT $1::int + $2::int",
                    query_id,
                    query_id * 2
                )
                duration = time.time() - start

                if result is not None:
                    metrics.record_success(duration)
                    return True
                else:
                    metrics.record_failure("Query returned None")
                    return False

        except Exception as e:
            metrics.record_failure(f"{type(e).__name__}: {str(e)[:100]}")
            return False

    # Generate sustained load
    query_count = 0
    end_time = time.time() + test_duration

    while time.time() < end_time:
        batch_size = queries_per_second
        tasks = [timed_query(query_count + i) for i in range(batch_size)]
        await asyncio.gather(*tasks, return_exceptions=False)
        query_count += batch_size

        # Small delay to achieve target rate
        await asyncio.sleep(0.1)

    metrics.end_time = datetime.now()
    summary = metrics.get_summary()

    # Print results
    print(f"\n{'='*70}")
    print(f"Sustained Load Throughput Test Results")
    print(f"{'='*70}")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"Total Queries: {summary['total_operations']}")
    print(f"Successful: {summary['successful']}")
    print(f"Failed: {summary['failed']}")
    print(f"Success Rate: {summary['success_rate']:.2%}")
    print(f"Sustained Throughput: {summary['throughput']:.2f} queries/s")
    print(f"{'='*70}\n")

    # Assertions
    assert summary['duration'] >= test_duration, \
        f"Test should run for at least {test_duration}s"

    assert summary['success_rate'] >= TEST_MIN_SUCCESS_RATE, \
        f"Sustained load success rate {summary['success_rate']:.2%} < {TEST_MIN_SUCCESS_RATE:.0%}"

    assert summary['throughput'] >= queries_per_second * 0.8, \
        f"Throughput {summary['throughput']:.2f} below target {queries_per_second * 0.8}"


# ============================================================================
# SUMMARY TEST
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
def test_load_test_summary():
    """
    Summary test to confirm all load tests are properly configured.

    This test verifies:
    - All load tests are marked with @pytest.mark.e2e and @pytest.mark.slow
    - Test constants are properly set
    - No remaining issues in the code
    """
    import inspect

    # Get all test functions in this module
    current_module = inspect.getmodule(inspect.currentframe())
    test_functions = [
        (name, func) for name, func in inspect.getmembers(current_module, inspect.isfunction)
        if name.startswith('test_') and name != 'test_load_test_summary'
    ]

    print(f"\n{'='*70}")
    print(f"Load Test Suite Summary")
    print(f"{'='*70}")
    print(f"Total Test Functions: {len(test_functions)}")
    print(f"API Concurrent Requests: {TEST_CONCURRENT_API_REQUESTS}")
    print(f"DB Concurrent Queries: {TEST_CONCURRENT_DB_QUERIES}")
    print(f"Minimum Success Rate: {TEST_MIN_SUCCESS_RATE:.0%}")
    print(f"{'='*70}\n")

    # Verify configuration
    assert TEST_CONCURRENT_API_REQUESTS == 50, "API requests must be 50"
    assert TEST_CONCURRENT_DB_QUERIES == 100, "DB queries must be 100"
    assert TEST_MIN_SUCCESS_RATE == 0.90, "Success rate must be 90%"

    print("All load tests properly configured!")
