"""
Comprehensive tests for InsightRepository (MOCK MODE)

Tests database operations using mocks to achieve high coverage without requiring PostgreSQL.
For integration tests with real database, see tests/e2e/test_data_flow.py
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import json

from insights_core.repository import InsightRepository
from insights_core.models import (
    Insight,
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics
)


@pytest.fixture
def mock_dsn():
    """Mock database DSN"""
    return "postgresql://test:test@localhost:5432/test_db"


@pytest.fixture
def sample_insight_create():
    """Sample InsightCreate for testing"""
    return InsightCreate(
        property="sc-domain:example.com",
        entity_type=EntityType.PAGE,
        entity_id="/test-page",
        category=InsightCategory.RISK,
        title="Test Traffic Drop",
        description="Test insight for validation",
        severity=InsightSeverity.HIGH,
        confidence=0.85,
        metrics=InsightMetrics(
            gsc_clicks=100.0,
            gsc_clicks_change=-25.5,
            window_start="2024-11-01",
            window_end="2024-11-15"
        ),
        window_days=7,
        source="TestDetector"
    )


@pytest.fixture
def sample_db_row():
    """Sample database row"""
    return {
        'id': 'test-id-12345',
        'generated_at': datetime(2024, 11, 15, 12, 0),
        'property': 'sc-domain:example.com',
        'entity_type': 'page',
        'entity_id': '/test-page',
        'category': 'risk',
        'title': 'Test Traffic Drop',
        'description': 'Test insight for validation',
        'severity': 'high',
        'confidence': 0.85,
        'metrics': json.dumps({
            'gsc_clicks': 100.0,
            'gsc_clicks_change': -25.5,
            'window_start': '2024-11-01',
            'window_end': '2024-11-15'
        }),
        'window_days': 7,
        'source': 'TestDetector',
        'status': 'new',
        'linked_insight_id': None,
        'created_at': datetime(2024, 11, 15, 12, 0),
        'updated_at': datetime(2024, 11, 15, 12, 0)
    }


class TestInsightRepository:
    """Test InsightRepository"""

    def test_init_connects_to_database(self, mock_dsn):
        """Test repository initialization connects to database"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            repo = InsightRepository(mock_dsn)

            assert repo.dsn == mock_dsn
            mock_connect.assert_called_once_with(mock_dsn)
            mock_conn.close.assert_called_once()

    def test_get_connection(self, mock_dsn):
        """Test _get_connection method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn

            # Init repo (will call connect once)
            mock_connect.return_value = Mock()
            repo = InsightRepository(mock_dsn)
            mock_connect.reset_mock()

            # Now test _get_connection
            mock_connect.return_value = mock_conn
            conn = repo._get_connection()

            assert conn == mock_conn
            mock_connect.assert_called_once_with(mock_dsn)

    def test_create_insight_success(self, mock_dsn, sample_insight_create, sample_db_row):
        """Test creating a new insight"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            # Setup mocks
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row

            repo = InsightRepository(mock_dsn)
            result = repo.create(sample_insight_create)

            # Verify
            assert isinstance(result, Insight)
            assert result.title == "Test Traffic Drop"
            assert result.category == InsightCategory.RISK
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.close.assert_called()

    def test_create_insight_duplicate(self, mock_dsn, sample_insight_create, sample_db_row):
        """Test creating duplicate insight returns existing"""
        import psycopg2

        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # First call raises IntegrityError (duplicate)
            mock_cursor.execute.side_effect = [
                psycopg2.IntegrityError("duplicate key"),
                None  # Second call for get_by_id
            ]
            mock_cursor.fetchone.return_value = sample_db_row

            repo = InsightRepository(mock_dsn)
            result = repo.create(sample_insight_create)

            # Verify rollback was called and existing insight returned
            assert isinstance(result, Insight)
            mock_conn.rollback.assert_called_once()

    def test_get_by_id_found(self, mock_dsn, sample_db_row):
        """Test get_by_id returns insight when found"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row

            repo = InsightRepository(mock_dsn)
            result = repo.get_by_id("test-id-12345")

            assert isinstance(result, Insight)
            assert result.id == "test-id-12345"
            assert result.title == "Test Traffic Drop"

    def test_get_by_id_not_found(self, mock_dsn):
        """Test get_by_id returns None when not found"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None

            repo = InsightRepository(mock_dsn)
            result = repo.get_by_id("non-existent-id")

            assert result is None

    def test_update_status(self, mock_dsn, sample_db_row):
        """Test updating insight status"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Update to diagnosed status
            updated_row = sample_db_row.copy()
            updated_row['status'] = 'diagnosed'
            mock_cursor.fetchone.return_value = updated_row

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate(status=InsightStatus.DIAGNOSED)
            result = repo.update("test-id-12345", update)

            assert result.status == InsightStatus.DIAGNOSED
            mock_conn.commit.assert_called_once()

    def test_update_description(self, mock_dsn, sample_db_row):
        """Test updating insight description"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            updated_row = sample_db_row.copy()
            updated_row['description'] = "Updated description"
            mock_cursor.fetchone.return_value = updated_row

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate(description="Updated description")
            result = repo.update("test-id-12345", update)

            assert result.description == "Updated description"

    def test_update_linked_insight(self, mock_dsn, sample_db_row):
        """Test updating linked insight"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            updated_row = sample_db_row.copy()
            updated_row['linked_insight_id'] = "parent-insight-id"
            mock_cursor.fetchone.return_value = updated_row

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate(linked_insight_id="parent-insight-id")
            result = repo.update("test-id-12345", update)

            assert result.linked_insight_id == "parent-insight-id"

    def test_update_empty_returns_existing(self, mock_dsn, sample_db_row):
        """Test update with no fields returns existing insight"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate()  # Empty update
            result = repo.update("test-id-12345", update)

            # Should call get_by_id instead of UPDATE
            assert isinstance(result, Insight)

    def test_query_with_filters(self, mock_dsn, sample_db_row):
        """Test querying with multiple filters"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(
                property="sc-domain:example.com",
                category=InsightCategory.RISK,
                severity=InsightSeverity.HIGH,
                limit=50
            )

            assert len(results) == 1
            assert results[0].category == InsightCategory.RISK

    def test_query_no_filters(self, mock_dsn, sample_db_row):
        """Test querying without filters"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row, sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(limit=100)

            assert len(results) == 2

    def test_get_by_status(self, mock_dsn, sample_db_row):
        """Test get_by_status convenience method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.get_by_status(
                InsightStatus.NEW,
                property="sc-domain:example.com"
            )

            assert len(results) == 1
            assert results[0].status == InsightStatus.NEW

    def test_get_by_category(self, mock_dsn, sample_db_row):
        """Test get_by_category convenience method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.get_by_category(
                InsightCategory.RISK,
                severity=InsightSeverity.HIGH
            )

            assert len(results) == 1
            assert results[0].category == InsightCategory.RISK

    def test_get_for_entity(self, mock_dsn, sample_db_row):
        """Test get_for_entity method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.get_for_entity(
                entity_type="page",
                entity_id="/test-page",
                property="sc-domain:example.com",
                days_back=30
            )

            assert len(results) == 1
            assert results[0].entity_id == "/test-page"

    def test_query_recent(self, mock_dsn, sample_db_row):
        """Test query_recent method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query_recent(hours=24, property="sc-domain:example.com")

            assert len(results) == 1

    def test_delete_old_insights(self, mock_dsn):
        """Test deleting old insights"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.rowcount = 42

            repo = InsightRepository(mock_dsn)
            deleted = repo.delete_old_insights(days=90)

            assert deleted == 42
            mock_conn.commit.assert_called_once()

    def test_get_stats(self, mock_dsn):
        """Test get_stats method"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            stats_row = {
                'total_insights': 150,
                'unique_properties': 5,
                'risk_count': 45,
                'opportunity_count': 60,
                'new_count': 80,
                'diagnosed_count': 50,
                'high_severity_count': 30,
                'latest_insight': datetime(2024, 11, 15, 12, 0),
                'earliest_insight': datetime(2024, 10, 1, 10, 0)
            }
            mock_cursor.fetchone.return_value = stats_row

            repo = InsightRepository(mock_dsn)
            stats = repo.get_stats()

            assert stats['total_insights'] == 150
            assert stats['risk_count'] == 45
            assert stats['opportunity_count'] == 60

    def test_row_to_insight_with_string_metrics(self, mock_dsn, sample_db_row):
        """Test _row_to_insight with metrics as JSON string"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            repo = InsightRepository(mock_dsn)
            # sample_db_row already has metrics as JSON string
            insight = repo._row_to_insight(sample_db_row)

            assert isinstance(insight, Insight)
            assert isinstance(insight.metrics, InsightMetrics)
            assert insight.metrics.gsc_clicks == 100.0

    def test_row_to_insight_with_dict_metrics(self, mock_dsn, sample_db_row):
        """Test _row_to_insight with metrics as dict"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            repo = InsightRepository(mock_dsn)

            # Change metrics to dict (as it might come from PostgreSQL JSONB)
            row = sample_db_row.copy()
            row['metrics'] = {
                'gsc_clicks': 100.0,
                'gsc_clicks_change': -25.5,
                'window_start': '2024-11-01',
                'window_end': '2024-11-15'
            }

            insight = repo._row_to_insight(row)

            assert isinstance(insight, Insight)
            assert isinstance(insight.metrics, InsightMetrics)
            assert insight.metrics.gsc_clicks == 100.0

    def test_query_with_entity_type(self, mock_dsn, sample_db_row):
        """Test querying with entity_type filter"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(entity_type=EntityType.PAGE)

            assert len(results) == 1
            assert results[0].entity_type == EntityType.PAGE

    def test_query_with_offset(self, mock_dsn, sample_db_row):
        """Test querying with offset for pagination"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(limit=10, offset=20)

            assert len(results) == 1
            # Verify the SQL was called with limit and offset
            args = mock_cursor.execute.call_args[0][1]
            assert 10 in args  # limit
            assert 20 in args  # offset

    def test_query_empty_results(self, mock_dsn):
        """Test query returns empty list when no results"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            repo = InsightRepository(mock_dsn)
            results = repo.query(property="nonexistent.com")

            assert results == []
            assert len(results) == 0

    def test_query_with_status_filter(self, mock_dsn, sample_db_row):
        """Test querying with status filter"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(status=InsightStatus.NEW)

            assert len(results) == 1
            assert results[0].status == InsightStatus.NEW

    def test_query_with_all_filters(self, mock_dsn, sample_db_row):
        """Test querying with all possible filters"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query(
                property="sc-domain:example.com",
                category=InsightCategory.RISK,
                status=InsightStatus.NEW,
                severity=InsightSeverity.HIGH,
                entity_type=EntityType.PAGE,
                limit=25,
                offset=5
            )

            assert len(results) == 1
            # Verify all filters were used in the query
            call_args = mock_cursor.execute.call_args[0]
            assert len(call_args) == 2  # SQL string and values tuple
            values = call_args[1]
            assert "sc-domain:example.com" in values
            assert "risk" in values
            assert "new" in values
            assert "high" in values
            assert "page" in values
            assert 25 in values
            assert 5 in values

    def test_get_for_entity_empty_results(self, mock_dsn):
        """Test get_for_entity returns empty list when no insights found"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            repo = InsightRepository(mock_dsn)
            results = repo.get_for_entity(
                entity_type="page",
                entity_id="/nonexistent",
                property="sc-domain:example.com"
            )

            assert results == []

    def test_query_recent_empty_results(self, mock_dsn):
        """Test query_recent returns empty list when no recent insights"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            repo = InsightRepository(mock_dsn)
            results = repo.query_recent(hours=1)

            assert results == []

    def test_query_recent_with_property_filter(self, mock_dsn, sample_db_row):
        """Test query_recent with property filter"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.query_recent(hours=48, property="sc-domain:example.com")

            assert len(results) == 1
            # Verify both time filter and property filter were applied
            call_args = mock_cursor.execute.call_args[0]
            assert "sc-domain:example.com" in call_args[1]

    def test_update_not_found(self, mock_dsn):
        """Test update returns None when insight not found"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate(status=InsightStatus.DIAGNOSED)
            result = repo.update("nonexistent-id", update)

            assert result is None

    def test_update_multiple_fields(self, mock_dsn, sample_db_row):
        """Test updating multiple fields at once"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            updated_row = sample_db_row.copy()
            updated_row['status'] = 'diagnosed'
            updated_row['description'] = 'Updated description'
            updated_row['linked_insight_id'] = 'parent-id'
            mock_cursor.fetchone.return_value = updated_row

            repo = InsightRepository(mock_dsn)
            update = InsightUpdate(
                status=InsightStatus.DIAGNOSED,
                description="Updated description",
                linked_insight_id="parent-id"
            )
            result = repo.update("test-id-12345", update)

            assert result.status == InsightStatus.DIAGNOSED
            assert result.description == "Updated description"
            assert result.linked_insight_id == "parent-id"
            mock_conn.commit.assert_called_once()

    def test_get_stats_empty_database(self, mock_dsn):
        """Test get_stats returns empty dict when no data"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None

            repo = InsightRepository(mock_dsn)
            stats = repo.get_stats()

            assert stats == {}

    def test_delete_old_insights_zero_deleted(self, mock_dsn):
        """Test delete_old_insights when no insights match criteria"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.rowcount = 0

            repo = InsightRepository(mock_dsn)
            deleted = repo.delete_old_insights(days=180)

            assert deleted == 0
            mock_conn.commit.assert_called_once()

    def test_delete_old_insights_custom_days(self, mock_dsn):
        """Test delete_old_insights with custom days parameter"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.rowcount = 15

            repo = InsightRepository(mock_dsn)
            deleted = repo.delete_old_insights(days=30)

            assert deleted == 15
            # Verify the SQL uses the custom days parameter
            call_args = mock_cursor.execute.call_args[0]
            assert len(call_args) == 2  # SQL and values

    def test_get_by_status_with_limit(self, mock_dsn, sample_db_row):
        """Test get_by_status respects limit parameter"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row, sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.get_by_status(
                InsightStatus.NEW,
                limit=2
            )

            assert len(results) == 2

    def test_get_by_category_with_property_and_severity(self, mock_dsn, sample_db_row):
        """Test get_by_category with property and severity filters"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [sample_db_row]

            repo = InsightRepository(mock_dsn)
            results = repo.get_by_category(
                category=InsightCategory.RISK,
                property="sc-domain:example.com",
                severity=InsightSeverity.HIGH,
                limit=50
            )

            assert len(results) == 1
            assert results[0].category == InsightCategory.RISK
            assert results[0].severity == InsightSeverity.HIGH

    def test_connection_closed_on_error(self, mock_dsn):
        """Test connection is closed even when error occurs"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Database error")

            repo = InsightRepository(mock_dsn)

            with pytest.raises(Exception):
                repo.get_by_id("test-id")

            # Connection should be closed even on error
            mock_conn.close.assert_called()

    def test_row_to_insight_with_all_fields(self, mock_dsn):
        """Test _row_to_insight with all fields populated"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            repo = InsightRepository(mock_dsn)

            complete_row = {
                'id': 'complete-id',
                'generated_at': datetime(2024, 11, 15, 12, 0),
                'property': 'sc-domain:example.com',
                'entity_type': 'query',
                'entity_id': 'test query',
                'category': 'opportunity',
                'title': 'Growth Opportunity',
                'description': 'High potential keyword',
                'severity': 'medium',
                'confidence': 0.92,
                'metrics': json.dumps({
                    'gsc_clicks': 500.0,
                    'gsc_impressions': 5000.0,
                    'gsc_ctr': 0.1,
                    'gsc_position': 5.2,
                    'window_start': '2024-11-01',
                    'window_end': '2024-11-15'
                }),
                'window_days': 14,
                'source': 'OpportunityDetector',
                'status': 'investigating',
                'linked_insight_id': 'parent-insight',
                'created_at': datetime(2024, 11, 15, 10, 0),
                'updated_at': datetime(2024, 11, 15, 14, 0)
            }

            insight = repo._row_to_insight(complete_row)

            assert insight.id == 'complete-id'
            assert insight.entity_type == EntityType.QUERY
            assert insight.category == InsightCategory.OPPORTUNITY
            assert insight.severity == InsightSeverity.MEDIUM
            assert insight.status == InsightStatus.INVESTIGATING
            assert insight.linked_insight_id == 'parent-insight'
            assert insight.metrics.gsc_clicks == 500.0
            assert insight.metrics.gsc_impressions == 5000.0
            assert insight.created_at == datetime(2024, 11, 15, 10, 0)
            assert insight.updated_at == datetime(2024, 11, 15, 14, 0)

    def test_create_with_linked_insight_id(self, mock_dsn, sample_insight_create):
        """Test creating insight with linked_insight_id"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            returned_row = {
                'id': 'test-id',
                'generated_at': datetime(2024, 11, 15, 12, 0),
                'property': 'sc-domain:example.com',
                'entity_type': 'page',
                'entity_id': '/test-page',
                'category': 'risk',
                'title': 'Test Traffic Drop',
                'description': 'Test insight',
                'severity': 'high',
                'confidence': 0.85,
                'metrics': json.dumps({'gsc_clicks': 100.0}),
                'window_days': 7,
                'source': 'TestDetector',
                'status': 'new',
                'linked_insight_id': 'parent-id-123',
                'created_at': datetime(2024, 11, 15, 12, 0),
                'updated_at': datetime(2024, 11, 15, 12, 0)
            }
            mock_cursor.fetchone.return_value = returned_row

            # Add linked_insight_id to the insight create
            sample_insight_create.linked_insight_id = "parent-id-123"

            repo = InsightRepository(mock_dsn)
            result = repo.create(sample_insight_create)

            assert result.linked_insight_id == "parent-id-123"
            # Verify linked_insight_id was passed to the INSERT
            call_args = mock_cursor.execute.call_args[0]
            assert "parent-id-123" in call_args[1]

    def test_query_sorting_by_generated_at_desc(self, mock_dsn, sample_db_row):
        """Test query results are sorted by generated_at DESC"""
        with patch('insights_core.repository.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Create multiple rows with different timestamps
            row1 = sample_db_row.copy()
            row1['id'] = 'id-1'
            row1['generated_at'] = datetime(2024, 11, 15, 12, 0)

            row2 = sample_db_row.copy()
            row2['id'] = 'id-2'
            row2['generated_at'] = datetime(2024, 11, 16, 12, 0)

            mock_cursor.fetchall.return_value = [row2, row1]  # Newer first

            repo = InsightRepository(mock_dsn)
            results = repo.query()

            # Verify ORDER BY is in the SQL
            call_args = mock_cursor.execute.call_args[0]
            sql = call_args[0]
            assert "ORDER BY generated_at DESC" in sql

            # Results should be in order
            assert results[0].id == 'id-2'
            assert results[1].id == 'id-1'
