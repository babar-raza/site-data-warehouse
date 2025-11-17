#!/usr/bin/env python3
"""
Test InsightRepository with real database
Tests CRUD operations, duplicate handling, and data integrity
"""
import os
import pytest
from datetime import datetime, timedelta
from insights_core.repository import InsightRepository
from insights_core.models import (
    InsightCreate,
    Insight,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightStatus,
    InsightMetrics,
)


@pytest.fixture(scope="module")
def repository():
    """Create repository with real database connection"""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set")
    
    repo = InsightRepository(dsn)
    
    # Clean up any test data from previous runs
    conn = repo._get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gsc.insights WHERE source LIKE 'Test%'")
    conn.commit()
    conn.close()
    
    yield repo
    
    # Cleanup after tests
    conn = repo._get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM gsc.insights WHERE source LIKE 'Test%'")
    conn.commit()
    conn.close()


def test_table_exists(repository):
    """Verify insights table was created"""
    conn = repository._get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'gsc' 
            AND table_name = 'insights'
        );
    """)
    exists = cur.fetchone()[0]
    conn.close()
    
    assert exists, "gsc.insights table should exist"


def test_table_schema(repository):
    """Verify table has all expected columns"""
    conn = repository._get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'gsc' 
        AND table_name = 'insights'
        ORDER BY ordinal_position;
    """)
    columns = [row[0] for row in cur.fetchall()]
    conn.close()
    
    expected_columns = [
        'id', 'generated_at', 'property', 'entity_type', 'entity_id',
        'category', 'title', 'description', 'severity', 'confidence',
        'metrics', 'window_days', 'source', 'status', 'linked_insight_id',
        'created_at', 'updated_at'
    ]
    
    for col in expected_columns:
        assert col in columns, f"Column '{col}' should exist in insights table"


def test_create_insight(repository):
    """Test creating a new insight (happy path)"""
    insight_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/net/aspose.words/document',
        category=InsightCategory.RISK,
        title='Traffic Drop Detected',
        description='Page experienced 45% drop in clicks over past 7 days compared to previous week.',
        severity=InsightSeverity.HIGH,
        confidence=0.87,
        metrics=InsightMetrics(
            gsc_clicks=1250.0,
            gsc_clicks_change=-45.2,
            gsc_impressions=15000.0,
            window_start='2025-11-07',
            window_end='2025-11-14'
        ),
        window_days=7,
        source='TestAnomalyDetector'
    )
    
    created = repository.create(insight_create)
    
    assert created.id is not None
    assert len(created.id) == 64  # SHA256 hex = 64 chars
    assert created.property == 'https://docs.aspose.net'
    assert created.category == InsightCategory.RISK
    assert created.severity == InsightSeverity.HIGH
    assert created.confidence == 0.87
    assert created.status == InsightStatus.NEW
    assert created.metrics.gsc_clicks == 1250.0


def test_create_duplicate_insight(repository):
    """Test creating duplicate insight returns existing (not error)"""
    insight_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/test-duplicate',
        category=InsightCategory.OPPORTUNITY,
        title='Test Duplicate',
        description='Testing duplicate detection logic.',
        severity=InsightSeverity.MEDIUM,
        confidence=0.75,
        metrics=InsightMetrics(gsc_clicks=100.0),
        window_days=7,
        source='TestDuplicateDetector'
    )
    
    # Create first time
    first = repository.create(insight_create)
    
    # Create again with same params (should return existing, not error)
    second = repository.create(insight_create)
    
    assert first.id == second.id
    assert first.generated_at == second.generated_at


def test_get_by_id(repository):
    """Test retrieving insight by ID"""
    # Create an insight
    insight_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.QUERY,
        entity_id='aspose words tutorial',
        category=InsightCategory.TREND,
        title='Rising Query',
        description='Query showing upward trend in impressions.',
        severity=InsightSeverity.LOW,
        confidence=0.65,
        metrics=InsightMetrics(gsc_impressions=5000.0),
        window_days=28,
        source='TestTrendDetector'
    )
    
    created = repository.create(insight_create)
    
    # Retrieve it
    retrieved = repository.get_by_id(created.id)
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.entity_id == 'aspose words tutorial'
    assert retrieved.category == InsightCategory.TREND


def test_get_by_id_not_found(repository):
    """Test retrieving non-existent insight returns None"""
    fake_id = '0' * 64
    result = repository.get_by_id(fake_id)
    assert result is None


def test_update_insight_status(repository):
    """Test updating insight status"""
    # Create insight
    insight_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/test-update',
        category=InsightCategory.RISK,
        title='Test Update',
        description='Testing update functionality.',
        severity=InsightSeverity.MEDIUM,
        confidence=0.80,
        metrics=InsightMetrics(gsc_clicks=500.0),
        window_days=7,
        source='TestUpdateDetector'
    )
    
    created = repository.create(insight_create)
    assert created.status == InsightStatus.NEW
    
    # Update status
    update = InsightUpdate(status=InsightStatus.DIAGNOSED)
    updated = repository.update(created.id, update)
    
    assert updated.status == InsightStatus.DIAGNOSED
    assert updated.id == created.id
    
    # Verify in database
    retrieved = repository.get_by_id(created.id)
    assert retrieved.status == InsightStatus.DIAGNOSED


def test_query_by_property_and_category(repository):
    """Test filtering by property and category"""
    # Create multiple insights
    for i in range(3):
        insight_create = InsightCreate(
            property='https://test.aspose.net',
            entity_type=EntityType.PAGE,
            entity_id=f'/page-{i}',
            category=InsightCategory.OPPORTUNITY,
            title=f'Opportunity {i}',
            description='Test opportunity insight.',
            severity=InsightSeverity.MEDIUM,
            confidence=0.70,
            metrics=InsightMetrics(gsc_clicks=float(100 * i)),
            window_days=7,
            source='TestQueryDetector'
        )
        repository.create(insight_create)
    
    # Query them
    results = repository.query(
        property='https://test.aspose.net',
        category=InsightCategory.OPPORTUNITY
    )
    
    assert len(results) >= 3
    assert all(r.property == 'https://test.aspose.net' for r in results)
    assert all(r.category == InsightCategory.OPPORTUNITY for r in results)


def test_linked_insights(repository):
    """Test linking diagnosis to original risk"""
    # Create risk insight
    risk_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/linked-test',
        category=InsightCategory.RISK,
        title='Original Risk',
        description='Risk that will be diagnosed.',
        severity=InsightSeverity.HIGH,
        confidence=0.85,
        metrics=InsightMetrics(gsc_clicks=1000.0, gsc_clicks_change=-30.0),
        window_days=7,
        source='TestLinkDetector'
    )
    
    risk = repository.create(risk_create)
    
    # Create diagnosis linked to it
    diagnosis_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/linked-test',
        category=InsightCategory.DIAGNOSIS,
        title='Root Cause Found',
        description='Position dropped from 3 to 8.',
        severity=InsightSeverity.MEDIUM,
        confidence=0.90,
        metrics=InsightMetrics(gsc_position=8.0, gsc_position_change=5.0),
        window_days=7,
        source='TestDiagnosisDetector',
        linked_insight_id=risk.id
    )
    
    diagnosis = repository.create(diagnosis_create)
    
    assert diagnosis.linked_insight_id == risk.id
    
    # Verify we can retrieve both
    assert repository.get_by_id(risk.id) is not None
    assert repository.get_by_id(diagnosis.id) is not None


def test_validation_function(repository):
    """Test that validation function runs without error"""
    conn = repository._get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gsc.validate_insights_table();")
    results = cur.fetchall()
    conn.close()
    
    assert len(results) > 0, "Validation function should return results"
    
    # Check that no critical failures
    for row in results:
        check_status = row[1]
        if check_status == 'FAIL':
            pytest.fail(f"Validation check failed: {row[0]} - {row[3]}")


def test_confidence_constraint(repository):
    """Test that invalid confidence values are rejected (failing path)"""
    # Try confidence > 1.0 (should fail)
    insight_create = InsightCreate(
        property='https://docs.aspose.net',
        entity_type=EntityType.PAGE,
        entity_id='/invalid-confidence',
        category=InsightCategory.RISK,
        title='Invalid Confidence',
        description='This should fail validation.',
        severity=InsightSeverity.HIGH,
        confidence=1.5,  # Invalid!
        metrics=InsightMetrics(gsc_clicks=100.0),
        window_days=7,
        source='TestFailDetector'
    )
    
    with pytest.raises(Exception):  # Should fail at Pydantic validation or DB constraint
        repository.create(insight_create)


def test_indexes_exist(repository):
    """Verify critical indexes were created"""
    conn = repository._get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE schemaname = 'gsc' 
        AND tablename = 'insights';
    """)
    indexes = [row[0] for row in cur.fetchall()]
    conn.close()
    
    # Check for critical indexes
    assert any('property' in idx for idx in indexes), "Property index should exist"
    assert any('category' in idx for idx in indexes), "Category index should exist"
    assert any('status' in idx for idx in indexes), "Status index should exist"
    assert any('gin' in idx.lower() for idx in indexes), "GIN index for JSONB should exist"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
