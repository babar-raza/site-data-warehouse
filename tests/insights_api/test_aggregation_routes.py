"""
Tests for Insight Aggregation API Routes

Comprehensive test suite for the aggregation endpoints using mocks
to avoid requiring a real database connection.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from fastapi.testclient import TestClient
import psycopg2


class TestAggregationRoutes:
    """Test suite for aggregation API routes"""

    @pytest.fixture
    def mock_db_rows(self):
        """Sample database rows for testing all endpoints"""
        return {
            'by_page': [
                {
                    'property': 'sc-domain:example.com',
                    'page_path': '/blog/article-1',
                    'total_insights': 5,
                    'risk_count': 2,
                    'opportunity_count': 2,
                    'trend_count': 1,
                    'diagnosis_count': 0,
                    'high_severity_count': 1,
                    'medium_severity_count': 3,
                    'low_severity_count': 1,
                    'new_count': 3,
                    'actioned_count': 1,
                    'resolved_count': 1,
                    'latest_insight': datetime(2024, 1, 15, 10, 0, 0),
                    'earliest_insight': datetime(2024, 1, 1, 10, 0, 0),
                    'avg_confidence': 0.85
                },
                {
                    'property': 'sc-domain:example.com',
                    'page_path': '/products/item-1',
                    'total_insights': 3,
                    'risk_count': 1,
                    'opportunity_count': 2,
                    'trend_count': 0,
                    'diagnosis_count': 0,
                    'high_severity_count': 0,
                    'medium_severity_count': 2,
                    'low_severity_count': 1,
                    'new_count': 2,
                    'actioned_count': 1,
                    'resolved_count': 0,
                    'latest_insight': datetime(2024, 1, 14, 10, 0, 0),
                    'earliest_insight': datetime(2024, 1, 5, 10, 0, 0),
                    'avg_confidence': 0.75
                }
            ],
            'by_subdomain': [
                {
                    'property': 'sc-domain:example.com',
                    'subdomain': 'blog',
                    'total_insights': 15,
                    'risk_count': 5,
                    'opportunity_count': 8,
                    'trend_count': 2,
                    'diagnosis_count': 0,
                    'high_severity_count': 3,
                    'medium_severity_count': 8,
                    'low_severity_count': 4,
                    'unique_pages': 10,
                    'latest_insight': datetime(2024, 1, 15, 10, 0, 0)
                },
                {
                    'property': 'sc-domain:example.com',
                    'subdomain': 'products',
                    'total_insights': 8,
                    'risk_count': 3,
                    'opportunity_count': 4,
                    'trend_count': 1,
                    'diagnosis_count': 0,
                    'high_severity_count': 1,
                    'medium_severity_count': 5,
                    'low_severity_count': 2,
                    'unique_pages': 5,
                    'latest_insight': datetime(2024, 1, 14, 10, 0, 0)
                }
            ],
            'by_category': [
                {
                    'property': 'sc-domain:example.com',
                    'category': 'risk',
                    'total_insights': 20,
                    'high_severity_count': 5,
                    'medium_severity_count': 10,
                    'low_severity_count': 5,
                    'new_count': 10,
                    'investigating_count': 5,
                    'diagnosed_count': 2,
                    'actioned_count': 2,
                    'resolved_count': 1,
                    'unique_entities': 15,
                    'unique_sources': 3,
                    'avg_confidence': 0.82,
                    'latest_insight': datetime(2024, 1, 15, 10, 0, 0),
                    'earliest_insight': datetime(2024, 1, 1, 10, 0, 0)
                },
                {
                    'property': 'sc-domain:example.com',
                    'category': 'opportunity',
                    'total_insights': 30,
                    'high_severity_count': 8,
                    'medium_severity_count': 15,
                    'low_severity_count': 7,
                    'new_count': 15,
                    'investigating_count': 8,
                    'diagnosed_count': 3,
                    'actioned_count': 3,
                    'resolved_count': 1,
                    'unique_entities': 20,
                    'unique_sources': 4,
                    'avg_confidence': 0.78,
                    'latest_insight': datetime(2024, 1, 15, 10, 0, 0),
                    'earliest_insight': datetime(2024, 1, 1, 10, 0, 0)
                }
            ],
            'dashboard': [
                {
                    'property': 'sc-domain:example.com',
                    'total_insights': 100,
                    'total_risks': 30,
                    'total_opportunities': 40,
                    'total_trends': 20,
                    'total_diagnoses': 10,
                    'high_severity_total': 15,
                    'high_severity_new': 5,
                    'new_insights': 25,
                    'actioned_insights': 30,
                    'resolved_insights': 20,
                    'unique_entities': 50,
                    'avg_confidence': 0.78,
                    'last_insight_time': datetime(2024, 1, 15, 10, 0, 0),
                    'insights_last_24h': 10,
                    'insights_last_7d': 35,
                    'insights_last_30d': 80
                }
            ],
            'timeseries': [
                {
                    'property': 'sc-domain:example.com',
                    'date': '2024-01-15',
                    'category': 'risk',
                    'insight_count': 5,
                    'high_count': 2,
                    'medium_count': 2,
                    'low_count': 1
                },
                {
                    'property': 'sc-domain:example.com',
                    'date': '2024-01-15',
                    'category': 'opportunity',
                    'insight_count': 8,
                    'high_count': 3,
                    'medium_count': 3,
                    'low_count': 2
                },
                {
                    'property': 'sc-domain:example.com',
                    'date': '2024-01-14',
                    'category': 'risk',
                    'insight_count': 3,
                    'high_count': 1,
                    'medium_count': 1,
                    'low_count': 1
                }
            ],
            'top_issues': [
                {
                    'id': 'abc123',
                    'property': 'sc-domain:example.com',
                    'entity_type': 'page',
                    'entity_id': '/blog/article-1',
                    'category': 'risk',
                    'title': 'Significant traffic drop detected',
                    'severity': 'high',
                    'confidence': 0.95,
                    'status': 'new',
                    'generated_at': datetime(2024, 1, 15, 10, 0, 0),
                    'source': 'AnomalyDetector',
                    'priority_score': 95.0
                },
                {
                    'id': 'def456',
                    'property': 'sc-domain:example.com',
                    'entity_type': 'page',
                    'entity_id': '/products/item-1',
                    'category': 'risk',
                    'title': 'CTR decline observed',
                    'severity': 'medium',
                    'confidence': 0.82,
                    'status': 'investigating',
                    'generated_at': datetime(2024, 1, 14, 10, 0, 0),
                    'source': 'TrendDetector',
                    'priority_score': 41.0
                }
            ]
        }

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_insights_by_page(self, mock_get_conn, mock_db_rows):
        """Test by-page endpoint returns correct data"""
        # Setup mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['by_page']

        # Import and test
        from insights_api.routes.aggregations import get_insights_by_page
        import asyncio

        result = asyncio.run(get_insights_by_page(
            property='sc-domain:example.com',
            limit=100,
            offset=0
        ))

        # Assertions
        assert len(result) == 2
        assert result[0]['page_path'] == '/blog/article-1'
        assert result[0]['total_insights'] == 5
        assert result[0]['risk_count'] == 2
        assert result[0]['high_severity_count'] == 1
        assert result[1]['page_path'] == '/products/item-1'

        # Verify cursor execute was called with correct query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert 'vw_insights_by_page' in call_args[0][0]
        assert call_args[0][1] == ('sc-domain:example.com', 100, 0)

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_insights_by_subdomain(self, mock_get_conn, mock_db_rows):
        """Test by-subdomain endpoint returns correct data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['by_subdomain']

        from insights_api.routes.aggregations import get_insights_by_subdomain
        import asyncio

        result = asyncio.run(get_insights_by_subdomain(
            property='sc-domain:example.com',
            limit=100,
            offset=0
        ))

        assert len(result) == 2
        assert result[0]['subdomain'] == 'blog'
        assert result[0]['unique_pages'] == 10
        assert result[0]['total_insights'] == 15
        assert result[1]['subdomain'] == 'products'

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_insights_by_subdomain_no_property_filter(self, mock_get_conn, mock_db_rows):
        """Test by-subdomain endpoint without property filter"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['by_subdomain']

        from insights_api.routes.aggregations import get_insights_by_subdomain
        import asyncio

        result = asyncio.run(get_insights_by_subdomain(
            property=None,
            limit=50,
            offset=0
        ))

        assert len(result) == 2
        # Verify the query doesn't include property filter
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1] == (50, 0)  # Only limit and offset

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_insights_by_category(self, mock_get_conn, mock_db_rows):
        """Test by-category endpoint returns correct data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['by_category']

        from insights_api.routes.aggregations import get_insights_by_category
        import asyncio

        result = asyncio.run(get_insights_by_category(
            property='sc-domain:example.com',
            limit=100,
            offset=0
        ))

        assert len(result) == 2
        assert result[0]['category'] == 'risk'
        assert result[0]['total_insights'] == 20
        assert result[0]['unique_entities'] == 15
        assert result[1]['category'] == 'opportunity'
        assert result[1]['total_insights'] == 30

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_dashboard_summary(self, mock_get_conn, mock_db_rows):
        """Test dashboard endpoint returns correct data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['dashboard']

        from insights_api.routes.aggregations import get_dashboard_summary
        import asyncio

        result = asyncio.run(get_dashboard_summary(property='sc-domain:example.com'))

        assert len(result) == 1
        assert result[0]['total_insights'] == 100
        assert result[0]['total_risks'] == 30
        assert result[0]['total_opportunities'] == 40
        assert result[0]['insights_last_7d'] == 35
        assert result[0]['high_severity_new'] == 5

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_dashboard_summary_all_properties(self, mock_get_conn, mock_db_rows):
        """Test dashboard endpoint without property filter"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['dashboard']

        from insights_api.routes.aggregations import get_dashboard_summary
        import asyncio

        result = asyncio.run(get_dashboard_summary(property=None))

        assert len(result) == 1
        # Verify no WHERE clause in query
        call_args = mock_cursor.execute.call_args
        assert 'ORDER BY total_insights DESC' in call_args[0][0]

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_timeseries(self, mock_get_conn, mock_db_rows):
        """Test timeseries endpoint returns correct data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['timeseries']

        from insights_api.routes.aggregations import get_timeseries
        import asyncio

        result = asyncio.run(get_timeseries(
            property='sc-domain:example.com',
            days=30,
            category=None
        ))

        assert len(result) == 3
        assert result[0]['date'] == '2024-01-15'
        assert result[0]['category'] == 'risk'
        assert result[0]['insight_count'] == 5
        assert result[1]['category'] == 'opportunity'

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_timeseries_with_category_filter(self, mock_get_conn, mock_db_rows):
        """Test timeseries endpoint with category filter"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [mock_db_rows['timeseries'][0]]

        from insights_api.routes.aggregations import get_timeseries
        import asyncio

        result = asyncio.run(get_timeseries(
            property='sc-domain:example.com',
            days=7,
            category='risk'
        ))

        assert len(result) == 1
        assert result[0]['category'] == 'risk'

        # Verify category filter in query
        call_args = mock_cursor.execute.call_args
        assert call_args[0][1] == ('sc-domain:example.com', 'risk', 7)

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_top_issues(self, mock_get_conn, mock_db_rows):
        """Test top-issues endpoint returns correct data"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = mock_db_rows['top_issues']

        from insights_api.routes.aggregations import get_top_issues
        import asyncio

        result = asyncio.run(get_top_issues(
            property='sc-domain:example.com',
            limit=20,
            category=None,
            severity=None
        ))

        assert len(result) == 2
        assert result[0]['id'] == 'abc123'
        assert result[0]['severity'] == 'high'
        assert result[0]['priority_score'] == 95.0
        assert result[1]['id'] == 'def456'
        assert result[1]['severity'] == 'medium'

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_get_top_issues_with_filters(self, mock_get_conn, mock_db_rows):
        """Test top-issues endpoint with category and severity filters"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [mock_db_rows['top_issues'][0]]

        from insights_api.routes.aggregations import get_top_issues
        import asyncio

        result = asyncio.run(get_top_issues(
            property='sc-domain:example.com',
            limit=10,
            category='risk',
            severity='high'
        ))

        assert len(result) == 1
        assert result[0]['severity'] == 'high'
        assert result[0]['category'] == 'risk'

        # Verify filters in query
        call_args = mock_cursor.execute.call_args
        assert 'category = %s' in call_args[0][0]
        assert 'severity = %s' in call_args[0][0]
        assert call_args[0][1] == ['sc-domain:example.com', 'risk', 'high', 10]

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_handles_database_error(self, mock_get_conn):
        """Test error handling for database errors"""
        mock_get_conn.side_effect = psycopg2.Error("Connection failed")

        from insights_api.routes.aggregations import get_insights_by_page
        from fastapi import HTTPException
        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_insights_by_page(
                property='sc-domain:example.com',
                limit=100,
                offset=0
            ))

        assert exc_info.value.status_code == 500
        assert "Database error" in str(exc_info.value.detail)

    @patch('insights_api.routes.aggregations.os.getenv')
    def test_handles_missing_dsn(self, mock_getenv):
        """Test error handling when DSN not configured"""
        mock_getenv.return_value = None

        from insights_api.routes.aggregations import get_db_connection
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_db_connection()

        assert exc_info.value.status_code == 500
        assert "not configured" in exc_info.value.detail

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_connection_cleanup(self, mock_get_conn):
        """Test that database connections are properly closed"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        from insights_api.routes.aggregations import get_insights_by_page
        import asyncio

        asyncio.run(get_insights_by_page(
            property='sc-domain:example.com',
            limit=100,
            offset=0
        ))

        # Verify connection was closed
        mock_conn.close.assert_called_once()

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_connection_cleanup_on_error(self, mock_get_conn):
        """Test that connections are closed even when errors occur"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.side_effect = psycopg2.Error("Query failed")

        from insights_api.routes.aggregations import get_insights_by_page
        from fastapi import HTTPException
        import asyncio

        with pytest.raises(HTTPException):
            asyncio.run(get_insights_by_page(
                property='sc-domain:example.com',
                limit=100,
                offset=0
            ))

        # Verify connection was still closed
        mock_conn.close.assert_called_once()

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_pagination_parameters(self, mock_get_conn, mock_db_rows):
        """Test that pagination parameters are correctly passed to queries"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        from insights_api.routes.aggregations import get_insights_by_page
        import asyncio

        asyncio.run(get_insights_by_page(
            property='sc-domain:example.com',
            limit=50,
            offset=100
        ))

        call_args = mock_cursor.execute.call_args
        assert call_args[0][1] == ('sc-domain:example.com', 50, 100)

    @patch('insights_api.routes.aggregations.get_db_connection')
    def test_empty_results(self, mock_get_conn):
        """Test handling of empty result sets"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []

        from insights_api.routes.aggregations import get_insights_by_page
        import asyncio

        result = asyncio.run(get_insights_by_page(
            property='sc-domain:example.com',
            limit=100,
            offset=0
        ))

        assert result == []
        assert isinstance(result, list)
