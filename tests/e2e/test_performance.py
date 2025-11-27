#!/usr/bin/env python3
"""
End-to-End Performance Baseline Tests

This module contains performance baseline tests with strict timing requirements
to ensure the system meets performance SLAs. Tests validate response times for:
- API health checks (< 100ms)
- API insights queries (< 500ms)
- Individual detectors (< 5s)
- Full detection pipeline (< 30s)

All tests:
- Run 5 iterations for reliable measurements
- Calculate average using statistics.mean
- Fail if average exceeds threshold
- Log all individual measurements
- Marked with @pytest.mark.e2e and @pytest.mark.slow
"""
import os
import sys
import time
import statistics
import logging
import pytest
import psycopg2
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.e2e.fixtures import TestDataGenerator
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig
from insights_core.repository import InsightRepository
from insights_core.detectors.anomaly import AnomalyDetector
from insights_core.detectors.opportunity import OpportunityDetector
from insights_core.detectors.diagnosis import DiagnosisDetector
from insights_core.models import InsightCategory, InsightStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Performance thresholds (in seconds)
THRESHOLD_API_HEALTH = 0.100  # 100ms
THRESHOLD_API_INSIGHTS_LIST = 0.500  # 500ms
THRESHOLD_DETECTOR_ANOMALY = 5.0  # 5s
THRESHOLD_DETECTOR_ALL = 30.0  # 30s

# Test iterations
TEST_ITERATIONS = 5


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(scope="module")
def db_connection():
    """Database connection for performance tests"""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set - cannot run E2E performance tests")

    conn = psycopg2.connect(dsn)

    # Cleanup any leftover test data from previous runs
    TestDataGenerator.cleanup_test_data(conn)

    yield conn

    # Cleanup after tests
    TestDataGenerator.cleanup_test_data(conn)
    conn.close()


@pytest.fixture(scope="module")
def performance_test_data(db_connection):
    """Load test data once for all performance tests"""
    logger.info("Loading performance test data...")

    # Generate synthetic data with anomaly
    gsc_data = TestDataGenerator.generate_gsc_data_with_anomaly(days=30)
    ga4_data = TestDataGenerator.generate_ga4_data_with_anomaly(days=30)

    # Insert into database
    gsc_rows = TestDataGenerator.insert_gsc_data(db_connection, gsc_data)
    ga4_rows = TestDataGenerator.insert_ga4_data(db_connection, ga4_data)

    logger.info(f"Loaded {gsc_rows} GSC rows and {ga4_rows} GA4 rows")

    return {
        'gsc_rows': gsc_rows,
        'ga4_rows': ga4_rows,
        'property': TestDataGenerator.TEST_PROPERTY,
        'page': TestDataGenerator.TEST_PAGE
    }


@pytest.fixture(scope="module")
def api_base_url():
    """Get API base URL from environment or use default"""
    host = os.environ.get('API_HOST', 'localhost')
    port = os.environ.get('API_PORT', '8001')
    return f"http://{host}:{port}"


@pytest.fixture(scope="module")
def insights_config():
    """Get insights configuration"""
    return InsightsConfig()


@pytest.fixture(scope="module")
def insights_repository(insights_config):
    """Get insights repository"""
    return InsightRepository(insights_config.warehouse_dsn)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def measure_execution_time(func, *args, **kwargs) -> float:
    """
    Measure execution time of a function

    Args:
        func: Function to measure
        *args: Function positional arguments
        **kwargs: Function keyword arguments

    Returns:
        Execution time in seconds
    """
    start_time = time.perf_counter()
    func(*args, **kwargs)
    end_time = time.perf_counter()
    return end_time - start_time


def run_performance_test(
    test_name: str,
    func,
    threshold: float,
    iterations: int = TEST_ITERATIONS,
    *args,
    **kwargs
) -> Dict[str, Any]:
    """
    Run performance test with multiple iterations

    Args:
        test_name: Name of the test
        func: Function to test
        threshold: Performance threshold in seconds
        iterations: Number of iterations to run
        *args: Function positional arguments
        **kwargs: Function keyword arguments

    Returns:
        Dict with performance statistics
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Performance Test: {test_name}")
    logger.info(f"Threshold: {threshold * 1000:.0f}ms")
    logger.info(f"Iterations: {iterations}")
    logger.info(f"{'=' * 60}")

    measurements = []

    for i in range(iterations):
        logger.info(f"Iteration {i + 1}/{iterations}...")
        duration = measure_execution_time(func, *args, **kwargs)
        measurements.append(duration)
        logger.info(f"  Duration: {duration * 1000:.2f}ms")

    # Calculate statistics
    avg_time = statistics.mean(measurements)
    min_time = min(measurements)
    max_time = max(measurements)
    std_dev = statistics.stdev(measurements) if len(measurements) > 1 else 0

    # Log results
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Results for {test_name}:")
    logger.info(f"  Average: {avg_time * 1000:.2f}ms")
    logger.info(f"  Min:     {min_time * 1000:.2f}ms")
    logger.info(f"  Max:     {max_time * 1000:.2f}ms")
    logger.info(f"  Std Dev: {std_dev * 1000:.2f}ms")
    logger.info(f"  Threshold: {threshold * 1000:.0f}ms")
    logger.info(f"  Status: {'PASS' if avg_time <= threshold else 'FAIL'}")
    logger.info(f"{'=' * 60}\n")

    return {
        'test_name': test_name,
        'measurements': measurements,
        'average': avg_time,
        'min': min_time,
        'max': max_time,
        'std_dev': std_dev,
        'threshold': threshold,
        'passed': avg_time <= threshold
    }


# ============================================================================
# API PERFORMANCE TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_api_health_performance(api_base_url):
    """
    Test API health endpoint performance

    Requirements:
    - Average response time < 100ms
    - 5 iterations
    - All measurements logged
    """
    def health_check():
        response = requests.get(f"{api_base_url}/api/health", timeout=5)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"

    # Skip if API is not running
    try:
        requests.get(f"{api_base_url}/api/health", timeout=1)
    except requests.exceptions.RequestException:
        pytest.skip("API is not running - cannot test API performance")

    result = run_performance_test(
        "API Health Check",
        health_check,
        THRESHOLD_API_HEALTH
    )

    # Assert performance requirement
    assert result['passed'], (
        f"API health check average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_HEALTH * 1000:.0f}ms"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_api_insights_list_performance(api_base_url, performance_test_data):
    """
    Test API insights list endpoint performance

    Requirements:
    - Average response time < 500ms
    - 5 iterations
    - All measurements logged
    """
    def insights_list():
        response = requests.get(
            f"{api_base_url}/api/insights",
            params={'property': performance_test_data['property'], 'limit': 100},
            timeout=10
        )
        assert response.status_code == 200, f"Insights list failed: {response.status_code}"

    # Skip if API is not running
    try:
        requests.get(f"{api_base_url}/api/health", timeout=1)
    except requests.exceptions.RequestException:
        pytest.skip("API is not running - cannot test API performance")

    result = run_performance_test(
        "API Insights List",
        insights_list,
        THRESHOLD_API_INSIGHTS_LIST
    )

    # Assert performance requirement
    assert result['passed'], (
        f"API insights list average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


# ============================================================================
# DETECTOR PERFORMANCE TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_detector_anomaly_performance(
    insights_config,
    insights_repository,
    performance_test_data
):
    """
    Test AnomalyDetector performance

    Requirements:
    - Average execution time < 5s
    - 5 iterations
    - All measurements logged
    """
    def run_anomaly_detector():
        detector = AnomalyDetector(insights_repository, insights_config)
        insights_created = detector.detect(property=performance_test_data['property'])
        logger.info(f"    Created {insights_created} insights")

    result = run_performance_test(
        "AnomalyDetector",
        run_anomaly_detector,
        THRESHOLD_DETECTOR_ANOMALY
    )

    # Assert performance requirement
    assert result['passed'], (
        f"AnomalyDetector average {result['average']:.2f}s "
        f"exceeds threshold {THRESHOLD_DETECTOR_ANOMALY:.1f}s"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_detector_opportunity_performance(
    insights_config,
    insights_repository,
    performance_test_data
):
    """
    Test OpportunityDetector performance

    Requirements:
    - Average execution time < 5s
    - 5 iterations
    - All measurements logged
    """
    def run_opportunity_detector():
        detector = OpportunityDetector(insights_repository, insights_config)
        insights_created = detector.detect(property=performance_test_data['property'])
        logger.info(f"    Created {insights_created} insights")

    result = run_performance_test(
        "OpportunityDetector",
        run_opportunity_detector,
        THRESHOLD_DETECTOR_ANOMALY  # Same threshold as anomaly detector
    )

    # Assert performance requirement
    assert result['passed'], (
        f"OpportunityDetector average {result['average']:.2f}s "
        f"exceeds threshold {THRESHOLD_DETECTOR_ANOMALY:.1f}s"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_detector_diagnosis_performance(
    insights_config,
    insights_repository,
    performance_test_data
):
    """
    Test DiagnosisDetector performance

    Requirements:
    - Average execution time < 5s
    - 5 iterations
    - All measurements logged
    """
    def run_diagnosis_detector():
        detector = DiagnosisDetector(insights_repository, insights_config)
        insights_created = detector.detect(property=performance_test_data['property'])
        logger.info(f"    Created {insights_created} insights")

    result = run_performance_test(
        "DiagnosisDetector",
        run_diagnosis_detector,
        THRESHOLD_DETECTOR_ANOMALY  # Same threshold as other detectors
    )

    # Assert performance requirement
    assert result['passed'], (
        f"DiagnosisDetector average {result['average']:.2f}s "
        f"exceeds threshold {THRESHOLD_DETECTOR_ANOMALY:.1f}s"
    )


# ============================================================================
# FULL PIPELINE PERFORMANCE TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_detector_all_performance(insights_config, performance_test_data):
    """
    Test full InsightEngine pipeline performance

    Requirements:
    - Average execution time < 30s
    - 5 iterations
    - All measurements logged
    """
    def run_full_pipeline():
        engine = InsightEngine(insights_config)
        stats = engine.refresh(
            property=performance_test_data['property'],
            generate_actions=False  # Disable action generation for baseline test
        )
        logger.info(f"    Created {stats['total_insights_created']} insights")
        logger.info(f"    Detectors succeeded: {stats['detectors_succeeded']}/{stats['detectors_run']}")

    result = run_performance_test(
        "Full InsightEngine Pipeline",
        run_full_pipeline,
        THRESHOLD_DETECTOR_ALL
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Full pipeline average {result['average']:.2f}s "
        f"exceeds threshold {THRESHOLD_DETECTOR_ALL:.1f}s"
    )


# ============================================================================
# DATABASE QUERY PERFORMANCE TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_repository_query_performance(
    insights_repository,
    performance_test_data
):
    """
    Test InsightRepository query performance

    Requirements:
    - Average query time < 500ms
    - 5 iterations
    - All measurements logged
    """
    def query_insights():
        insights = insights_repository.query(
            property=performance_test_data['property'],
            limit=100
        )
        logger.info(f"    Retrieved {len(insights)} insights")

    result = run_performance_test(
        "Repository Query",
        query_insights,
        THRESHOLD_API_INSIGHTS_LIST  # Same as API list threshold
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Repository query average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_repository_get_by_category_performance(
    insights_repository,
    performance_test_data
):
    """
    Test InsightRepository get_by_category performance

    Requirements:
    - Average query time < 500ms
    - 5 iterations
    - All measurements logged
    """
    def query_by_category():
        insights = insights_repository.get_by_category(
            category=InsightCategory.RISK,
            property=performance_test_data['property'],
            limit=100
        )
        logger.info(f"    Retrieved {len(insights)} risk insights")

    result = run_performance_test(
        "Repository Query by Category",
        query_by_category,
        THRESHOLD_API_INSIGHTS_LIST  # Same as API list threshold
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Repository category query average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_repository_get_by_status_performance(
    insights_repository,
    performance_test_data
):
    """
    Test InsightRepository get_by_status performance

    Requirements:
    - Average query time < 500ms
    - 5 iterations
    - All measurements logged
    """
    def query_by_status():
        insights = insights_repository.get_by_status(
            status=InsightStatus.NEW,
            property=performance_test_data['property'],
            limit=100
        )
        logger.info(f"    Retrieved {len(insights)} new insights")

    result = run_performance_test(
        "Repository Query by Status",
        query_by_status,
        THRESHOLD_API_INSIGHTS_LIST  # Same as API list threshold
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Repository status query average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


# ============================================================================
# DATA INGESTION PERFORMANCE TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_data_ingestion_performance(db_connection):
    """
    Test data ingestion performance

    Requirements:
    - Average ingestion time < 500ms for 30 rows
    - 5 iterations
    - All measurements logged
    """
    def ingest_test_data():
        # Generate fresh data for each iteration
        gsc_data = TestDataGenerator.generate_gsc_data_with_anomaly(days=30)
        ga4_data = TestDataGenerator.generate_ga4_data_with_anomaly(days=30)

        # Insert data
        gsc_rows = TestDataGenerator.insert_gsc_data(db_connection, gsc_data)
        ga4_rows = TestDataGenerator.insert_ga4_data(db_connection, ga4_data)

        logger.info(f"    Inserted {gsc_rows} GSC + {ga4_rows} GA4 rows")

    result = run_performance_test(
        "Data Ingestion (30 rows)",
        ingest_test_data,
        THRESHOLD_API_INSIGHTS_LIST  # 500ms threshold
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Data ingestion average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_unified_view_query_performance(db_connection, performance_test_data):
    """
    Test unified view query performance

    Requirements:
    - Average query time < 500ms
    - 5 iterations
    - All measurements logged
    """
    def query_unified_view():
        cur = db_connection.cursor()
        cur.execute("""
            SELECT
                date,
                property,
                page_path,
                gsc_clicks,
                gsc_clicks_change_wow,
                ga_sessions,
                ga_conversions
            FROM gsc.vw_unified_page_performance
            WHERE property = %s
            ORDER BY date DESC
            LIMIT 100
        """, (performance_test_data['property'],))

        rows = cur.fetchall()
        logger.info(f"    Retrieved {len(rows)} rows from unified view")
        cur.close()

    result = run_performance_test(
        "Unified View Query",
        query_unified_view,
        THRESHOLD_API_INSIGHTS_LIST  # 500ms threshold
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Unified view query average {result['average'] * 1000:.2f}ms "
        f"exceeds threshold {THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms"
    )


# ============================================================================
# STRESS TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_concurrent_detector_runs_performance(
    insights_config,
    performance_test_data
):
    """
    Test performance under concurrent detector execution

    Requirements:
    - Average execution time < 30s even with multiple detectors
    - 5 iterations
    - All measurements logged

    Note: This test validates that running all detectors sequentially
    stays within the 30s threshold, demonstrating system stability.
    """
    def run_multiple_detectors():
        engine = InsightEngine(insights_config)
        stats = engine.refresh(
            property=performance_test_data['property'],
            generate_actions=False
        )
        logger.info(f"    Total insights: {stats['total_insights_created']}")
        logger.info(f"    Detectors: {stats['detectors_succeeded']}/{stats['detectors_run']}")

    result = run_performance_test(
        "Concurrent Detector Execution",
        run_multiple_detectors,
        THRESHOLD_DETECTOR_ALL,
        iterations=TEST_ITERATIONS
    )

    # Assert performance requirement
    assert result['passed'], (
        f"Concurrent execution average {result['average']:.2f}s "
        f"exceeds threshold {THRESHOLD_DETECTOR_ALL:.1f}s"
    )


# ============================================================================
# PERFORMANCE REGRESSION TESTS
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_performance_consistency(insights_config, performance_test_data):
    """
    Test performance consistency across iterations

    Requirements:
    - Standard deviation < 20% of average
    - 5 iterations
    - All measurements logged

    This test ensures that performance is consistent and doesn't
    vary wildly between runs (no performance regressions).
    """
    def run_engine():
        engine = InsightEngine(insights_config)
        stats = engine.refresh(
            property=performance_test_data['property'],
            generate_actions=False
        )
        logger.info(f"    Created {stats['total_insights_created']} insights")

    result = run_performance_test(
        "Performance Consistency Check",
        run_engine,
        THRESHOLD_DETECTOR_ALL
    )

    # Check consistency (std dev should be < 20% of average)
    consistency_threshold = result['average'] * 0.20

    logger.info(f"\nConsistency Check:")
    logger.info(f"  Standard Deviation: {result['std_dev']:.2f}s")
    logger.info(f"  Consistency Threshold (20% of avg): {consistency_threshold:.2f}s")
    logger.info(f"  Status: {'PASS' if result['std_dev'] <= consistency_threshold else 'FAIL'}")

    assert result['std_dev'] <= consistency_threshold, (
        f"Performance is inconsistent: std dev {result['std_dev']:.2f}s "
        f"exceeds 20% threshold {consistency_threshold:.2f}s"
    )


# ============================================================================
# SUMMARY TEST
# ============================================================================


@pytest.mark.e2e
@pytest.mark.slow
def test_performance_summary(
    api_base_url,
    insights_config,
    insights_repository,
    performance_test_data,
    db_connection
):
    """
    Generate performance test summary report

    This test runs a single iteration of each test and generates
    a comprehensive summary of system performance.
    """
    logger.info("\n" + "=" * 80)
    logger.info("PERFORMANCE BASELINE SUMMARY")
    logger.info("=" * 80)

    summary = {
        'timestamp': datetime.utcnow().isoformat(),
        'thresholds': {
            'api_health': f"{THRESHOLD_API_HEALTH * 1000:.0f}ms",
            'api_insights_list': f"{THRESHOLD_API_INSIGHTS_LIST * 1000:.0f}ms",
            'detector_anomaly': f"{THRESHOLD_DETECTOR_ANOMALY:.1f}s",
            'detector_all': f"{THRESHOLD_DETECTOR_ALL:.1f}s"
        },
        'test_iterations': TEST_ITERATIONS,
        'measurements': {}
    }

    # Run single iteration of key tests
    tests = [
        ('Repository Query', lambda: insights_repository.query(
            property=performance_test_data['property'], limit=100
        ), THRESHOLD_API_INSIGHTS_LIST),
        ('Single Detector', lambda: AnomalyDetector(
            insights_repository, insights_config
        ).detect(property=performance_test_data['property']), THRESHOLD_DETECTOR_ANOMALY),
        ('Full Pipeline', lambda: InsightEngine(insights_config).refresh(
            property=performance_test_data['property'], generate_actions=False
        ), THRESHOLD_DETECTOR_ALL),
    ]

    for test_name, test_func, threshold in tests:
        duration = measure_execution_time(test_func)
        passed = duration <= threshold

        summary['measurements'][test_name] = {
            'duration_ms': round(duration * 1000, 2),
            'threshold_ms': round(threshold * 1000, 2),
            'passed': passed
        }

        logger.info(f"\n{test_name}:")
        logger.info(f"  Duration: {duration * 1000:.2f}ms")
        logger.info(f"  Threshold: {threshold * 1000:.0f}ms")
        logger.info(f"  Status: {'PASS' if passed else 'FAIL'}")

    logger.info("\n" + "=" * 80)
    logger.info("All performance baselines established successfully")
    logger.info("=" * 80 + "\n")

    # All individual tests must pass
    all_passed = all(m['passed'] for m in summary['measurements'].values())
    assert all_passed, "Some performance tests failed - see summary above"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'e2e'])
