#!/usr/bin/env python3
"""
End-to-End Pipeline Test
Tests complete data flow: Ingest → Transform → Detect → Serve

This test validates that the entire system works together correctly.
"""
import os
import sys
import pytest
import psycopg2
from datetime import datetime, timedelta
import time

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tests.e2e.fixtures import TestDataGenerator
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig
from insights_core.repository import InsightRepository
from insights_core.models import InsightCategory, InsightSeverity


@pytest.fixture(scope="module")
def db_connection():
    """Database connection for E2E tests"""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set - cannot run E2E tests")
    
    conn = psycopg2.connect(dsn)
    
    # Cleanup any leftover test data from previous runs
    TestDataGenerator.cleanup_test_data(conn)
    
    yield conn
    
    # Cleanup after tests
    TestDataGenerator.cleanup_test_data(conn)
    conn.close()


@pytest.fixture(scope="module")
def test_data_loaded(db_connection):
    """Load test data once for all tests"""
    # Generate synthetic data
    gsc_data = TestDataGenerator.generate_gsc_data_with_anomaly(days=30)
    ga4_data = TestDataGenerator.generate_ga4_data_with_anomaly(days=30)
    
    # Insert into database
    gsc_rows = TestDataGenerator.insert_gsc_data(db_connection, gsc_data)
    ga4_rows = TestDataGenerator.insert_ga4_data(db_connection, ga4_data)
    
    return {
        'gsc_rows': gsc_rows,
        'ga4_rows': ga4_rows,
        'property': TestDataGenerator.TEST_PROPERTY,
        'page': TestDataGenerator.TEST_PAGE
    }


def test_stage1_data_ingestion(db_connection, test_data_loaded):
    """
    STAGE 1: Verify data was ingested correctly
    
    Tests:
    - GSC data inserted (30 rows)
    - GA4 data inserted (30 rows)
    - Data has correct date range
    """
    cur = db_connection.cursor()
    
    # Verify GSC data
    cur.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM gsc.fact_gsc_daily
        WHERE property = %s
    """, (test_data_loaded['property'],))
    
    gsc_count, gsc_min_date, gsc_max_date = cur.fetchone()
    
    assert gsc_count == 30, f"Expected 30 GSC rows, got {gsc_count}"
    assert gsc_min_date is not None, "GSC min date should not be NULL"
    assert gsc_max_date is not None, "GSC max date should not be NULL"
    
    # Verify date range is ~30 days
    date_diff = (gsc_max_date - gsc_min_date).days
    assert date_diff == 29, f"Expected 29-day range, got {date_diff}"
    
    # Verify GA4 data
    cur.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM gsc.fact_ga4_daily
        WHERE property = %s
    """, (test_data_loaded['property'],))
    
    ga4_count, ga4_min_date, ga4_max_date = cur.fetchone()
    
    assert ga4_count == 30, f"Expected 30 GA4 rows, got {ga4_count}"
    assert ga4_min_date == gsc_min_date, "GA4 and GSC date ranges should match"
    assert ga4_max_date == gsc_max_date, "GA4 and GSC date ranges should match"
    
    print(f"✓ Stage 1: Ingested {gsc_count} GSC + {ga4_count} GA4 rows")


def test_stage2_unified_view_transform(db_connection, test_data_loaded):
    """
    STAGE 2: Verify unified view shows test data
    
    Tests:
    - Test data appears in vw_unified_page_performance
    - WoW calculations populated
    - Data joined correctly (GSC + GA4)
    """
    stats = TestDataGenerator.verify_unified_view_has_test_data(db_connection)
    
    assert stats['row_count'] == 30, f"Expected 30 rows in unified view, got {stats['row_count']}"
    assert stats['date_count'] == 30, f"Expected 30 distinct dates, got {stats['date_count']}"
    
    # WoW calculations should be populated for days 8+ (need 7 days history)
    assert stats['wow_count'] >= 22, f"Expected 22+ WoW values, got {stats['wow_count']}"
    
    # Verify specific WoW calculation on anomaly date
    cur = db_connection.cursor()
    anomaly_date = TestDataGenerator.get_planted_anomaly_date()
    
    cur.execute("""
        SELECT 
            gsc_clicks,
            gsc_clicks_7d_ago,
            gsc_clicks_change_wow,
            ga_conversions,
            ga_conversions_7d_ago,
            ga_conversions_change_wow
        FROM gsc.vw_unified_page_performance
        WHERE property = %s 
        AND page_path = %s
        AND date = %s
    """, (test_data_loaded['property'], test_data_loaded['page'], anomaly_date))
    
    result = cur.fetchone()
    
    if result:
        clicks, clicks_7d, clicks_wow, conv, conv_7d, conv_wow = result
        
        # Day 28: clicks=50, 7d ago (day 21)=50, WoW should be 0% (transition day)
        # But day 21 was first drop day, so 7d ago (day 14) was 100
        # So WoW = ((50 - 100) / 100) * 100 = -50%
        assert clicks == 50, f"Expected 50 clicks on anomaly date, got {clicks}"
        assert clicks_7d == 100, f"Expected 100 clicks 7d ago, got {clicks_7d}"
        assert clicks_wow == -50.0, f"Expected -50% WoW, got {clicks_wow}"
        
        print(f"✓ Stage 2: WoW calculation correct: {clicks_wow}%")
    else:
        pytest.fail("No data found for anomaly date in unified view")


def test_stage3_insight_generation(db_connection, test_data_loaded):
    """
    STAGE 3: Run InsightEngine and verify insights created
    
    Tests:
    - InsightEngine runs successfully
    - At least one insight created
    - Anomaly detected (we planted a -50% drop)
    - Insight metrics match source data
    """
    # Initialize InsightEngine
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    # Run detection
    start_time = time.time()
    stats = engine.refresh(property=test_data_loaded['property'])
    duration = time.time() - start_time
    
    # Verify engine ran successfully
    assert stats['detectors_run'] == 3, "Should run 3 detectors"
    assert stats['detectors_failed'] == 0, "No detectors should fail"
    assert duration < 30, f"Insights should generate in <30s, took {duration:.1f}s"
    
    # Verify at least one insight was created
    assert stats['total_insights_created'] >= 1, \
        f"Expected at least 1 insight from planted anomaly, got {stats['total_insights_created']}"
    
    print(f"✓ Stage 3: Generated {stats['total_insights_created']} insights in {duration:.1f}s")
    
    # Verify the specific anomaly was detected
    cur = db_connection.cursor()
    cur.execute("""
        SELECT 
            id,
            category,
            title,
            severity,
            confidence,
            metrics
        FROM gsc.insights
        WHERE property = %s
        AND entity_id = %s
        AND category = 'risk'
        ORDER BY generated_at DESC
        LIMIT 1
    """, (test_data_loaded['property'], test_data_loaded['page']))
    
    insight = cur.fetchone()
    
    assert insight is not None, "Should have created risk insight for planted anomaly"
    
    insight_id, category, title, severity, confidence, metrics = insight
    
    assert category == 'risk', f"Expected risk category, got {category}"
    assert severity in ['medium', 'high'], f"Expected medium/high severity for -50% drop, got {severity}"
    assert confidence >= 0.7, f"Expected high confidence, got {confidence}"
    
    # Verify metrics match the anomaly
    import json
    metrics_dict = json.loads(metrics) if isinstance(metrics, str) else metrics
    
    # Should have captured the drop
    assert 'gsc_clicks_change' in metrics_dict or 'gsc_clicks_change_wow' in str(metrics_dict), \
        "Insight metrics should include click change"
    
    print(f"✓ Stage 3: Anomaly detected - {title} ({severity})")


def test_stage4_insight_retrieval(db_connection, test_data_loaded):
    """
    STAGE 4: Verify insights can be retrieved via Repository
    
    Tests:
    - Repository can query insights
    - Filters work (by property, category)
    - Data matches what was created
    """
    # Initialize repository
    dsn = os.environ['WAREHOUSE_DSN']
    repo = InsightRepository(dsn)
    
    # Query insights for test property
    insights = repo.query(
        property=test_data_loaded['property'],
        category=InsightCategory.RISK
    )
    
    assert len(insights) >= 1, f"Expected at least 1 risk insight, got {len(insights)}"
    
    # Verify insight structure
    first_insight = insights[0]
    
    assert first_insight.property == test_data_loaded['property']
    assert first_insight.category == InsightCategory.RISK
    assert first_insight.entity_id == test_data_loaded['page']
    assert first_insight.confidence >= 0.5
    
    print(f"✓ Stage 4: Retrieved {len(insights)} insights via Repository")
    
    # Verify get_by_id works
    insight_by_id = repo.get_by_id(first_insight.id)
    
    assert insight_by_id is not None, "Should retrieve insight by ID"
    assert insight_by_id.id == first_insight.id, "IDs should match"


def test_cleanup_no_pollution(db_connection):
    """
    Verify cleanup removes all test data (no pollution)
    
    Tests:
    - All test data removed from fact tables
    - All test insights removed
    - No test data in unified view
    """
    cleanup_stats = TestDataGenerator.cleanup_test_data(db_connection)
    
    # Should have deleted data
    assert cleanup_stats['gsc_deleted'] >= 0, "GSC cleanup should run"
    assert cleanup_stats['ga4_deleted'] >= 0, "GA4 cleanup should run"
    assert cleanup_stats['insights_deleted'] >= 0, "Insights cleanup should run"
    
    # Verify no test data remains
    cur = db_connection.cursor()
    
    cur.execute("SELECT COUNT(*) FROM gsc.fact_gsc_daily WHERE property LIKE 'test://%'")
    assert cur.fetchone()[0] == 0, "No test GSC data should remain"
    
    cur.execute("SELECT COUNT(*) FROM gsc.fact_ga4_daily WHERE property LIKE 'test://%'")
    assert cur.fetchone()[0] == 0, "No test GA4 data should remain"
    
    cur.execute("SELECT COUNT(*) FROM gsc.insights WHERE property LIKE 'test://%'")
    assert cur.fetchone()[0] == 0, "No test insights should remain"
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM gsc.vw_unified_page_performance 
        WHERE property LIKE 'test://%'
    """)
    assert cur.fetchone()[0] == 0, "No test data in unified view"
    
    print("✓ Cleanup: All test data removed")


def test_failure_scenario_missing_ga4_data(db_connection):
    """
    FAILURE SCENARIO 1: Missing GA4 data
    
    Tests:
    - System handles missing GA4 gracefully
    - Insights still generated from GSC alone
    - No crashes or exceptions
    """
    # Setup: Insert only GSC data (no GA4)
    property_partial = "test://partial-data"
    page_partial = "/test/partial"
    
    gsc_data = [{
        'date': datetime.now().date() - timedelta(days=i),
        'property': property_partial,
        'url': page_partial,
        'query': 'test query',
        'country': 'usa',
        'device': 'DESKTOP',
        'clicks': 100 - i,  # Declining trend
        'impressions': 1000,
        'ctr': (100 - i) / 10,
        'position': 5.0
    } for i in range(10)]
    
    TestDataGenerator.insert_gsc_data(db_connection, gsc_data)
    
    # Run InsightEngine
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    try:
        stats = engine.refresh(property=property_partial)
        assert stats['detectors_failed'] == 0, "Should handle missing GA4 gracefully"
        print("✓ Failure Scenario 1: Handled missing GA4 data")
    except Exception as e:
        pytest.fail(f"Should not crash with missing GA4 data: {e}")
    finally:
        # Cleanup
        cur = db_connection.cursor()
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = %s", (property_partial,))
        cur.execute("DELETE FROM gsc.insights WHERE property = %s", (property_partial,))
        db_connection.commit()


def test_failure_scenario_detector_exception(db_connection, monkeypatch):
    """
    FAILURE SCENARIO 2: Detector raises exception
    
    Tests:
    - InsightEngine handles detector failures
    - Other detectors still run
    - Error tracked in stats
    """
    from insights_core.detectors.anomaly import AnomalyDetector
    
    # Monkeypatch detect method to raise exception
    original_detect = AnomalyDetector.detect
    
    def failing_detect(self, property=None):
        raise Exception("Simulated detector failure")
    
    monkeypatch.setattr(AnomalyDetector, 'detect', failing_detect)
    
    # Run InsightEngine
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    try:
        stats = engine.refresh()
        
        # Should have 1 failed detector
        assert stats['detectors_failed'] == 1, "Should track detector failure"
        assert len(stats['errors']) == 1, "Should record error"
        assert 'AnomalyDetector' in stats['errors'][0]['detector']
        
        print("✓ Failure Scenario 2: Handled detector exception gracefully")
        
    finally:
        # Restore original method
        monkeypatch.setattr(AnomalyDetector, 'detect', original_detect)


def test_performance_within_limits(db_connection, test_data_loaded):
    """
    Performance test: Verify pipeline runs within time limits
    
    Tests:
    - Full refresh completes in <30s
    - Individual stages have reasonable timing
    """
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    start_time = time.time()
    stats = engine.refresh(property=test_data_loaded['property'])
    duration = time.time() - start_time
    
    assert duration < 30, f"Full refresh should complete in <30s, took {duration:.1f}s"
    
    # Check individual detector timings (if available in stats)
    if 'duration_seconds' in stats:
        assert stats['duration_seconds'] < 30, "Duration tracking should match"
    
    print(f"✓ Performance: Full pipeline in {duration:.1f}s")


def test_deterministic_results(db_connection, test_data_loaded):
    """
    Verify pipeline produces deterministic results
    
    Tests:
    - Running twice produces same insights
    - Insight IDs are deterministic (same hash)
    """
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    # First run
    stats1 = engine.refresh(property=test_data_loaded['property'])
    
    # Get insight IDs
    cur = db_connection.cursor()
    cur.execute("""
        SELECT id, category, entity_id
        FROM gsc.insights
        WHERE property = %s
        ORDER BY id
    """, (test_data_loaded['property'],))
    
    insights1 = cur.fetchall()
    
    # Second run (should be idempotent due to deterministic IDs)
    stats2 = engine.refresh(property=test_data_loaded['property'])
    
    cur.execute("""
        SELECT id, category, entity_id
        FROM gsc.insights
        WHERE property = %s
        ORDER BY id
    """, (test_data_loaded['property'],))
    
    insights2 = cur.fetchall()
    
    # Should have same insights (deterministic IDs prevent duplicates)
    assert len(insights1) == len(insights2), "Should produce same number of insights"
    
    # IDs should match (deterministic hashing)
    ids1 = [i[0] for i in insights1]
    ids2 = [i[0] for i in insights2]
    assert ids1 == ids2, "Insight IDs should be deterministic"
    
    print("✓ Deterministic: Pipeline produces consistent results")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
