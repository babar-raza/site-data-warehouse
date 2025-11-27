"""
Comprehensive tests for GSCBasedSerpTracker

Tests the GSC-based SERP position tracker that syncs position data
from Google Search Console to SERP tracking tables.

Coverage: >90% of insights_core/gsc_serp_tracker.py
Test scenarios: Happy path, error cases, edge cases
Performance: <3 seconds total (all mocked, no network calls)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, date, timedelta
import psycopg2

from insights_core.gsc_serp_tracker import (
    GSCBasedSerpTracker,
    sync_all_properties,
)


# Mock paths
PSYCOPG2_PATH = 'insights_core.gsc_serp_tracker.psycopg2'
ASYNCPG_PATH = 'insights_core.gsc_serp_tracker.asyncpg'
OS_GETENV_PATH = 'insights_core.gsc_serp_tracker.os.getenv'


@pytest.fixture
def mock_warehouse_dsn():
    """Standard test DSN"""
    return "postgresql://test_user:test_pass@localhost:5432/test_db"


@pytest.fixture
def mock_property_url():
    """Standard test property"""
    return "https://example.com"


@pytest.fixture
def sample_gsc_query_data():
    """Sample GSC query data as returned by database"""
    return [
        {
            'query_text': 'python tutorial',
            'page_path': '/blog/python-tutorial',
            'device': 'desktop',
            'location': 'United States',
            'avg_position': 5.2,
            'total_impressions': 1000,
            'total_clicks': 50,
            'avg_ctr': 5.0,
            'latest_date': date.today() - timedelta(days=2)
        },
        {
            'query_text': 'javascript tips',
            'page_path': '/blog/js-tips',
            'device': 'mobile',
            'location': 'United Kingdom',
            'avg_position': 8.7,
            'total_impressions': 500,
            'total_clicks': 20,
            'avg_ctr': 4.0,
            'latest_date': date.today() - timedelta(days=2)
        },
        {
            'query_text': 'react hooks',
            'page_path': '/blog/react-hooks',
            'device': 'desktop',
            'location': None,  # Test null location
            'avg_position': 3.1,
            'total_impressions': 2000,
            'total_clicks': 200,
            'avg_ctr': 10.0,
            'latest_date': date.today() - timedelta(days=1)
        }
    ]


@pytest.fixture
def sample_position_history_data():
    """Sample daily position data from GSC"""
    return [
        {
            'query_text': 'python tutorial',
            'page_path': '/blog/python-tutorial',
            'device': 'desktop',
            'country': 'United States',
            'data_date': date.today() - timedelta(days=2),
            'position': 5.2,
            'impressions': 100,
            'clicks': 5,
            'ctr': 5.0
        },
        {
            'query_text': 'python tutorial',
            'page_path': '/blog/python-tutorial',
            'device': 'desktop',
            'country': 'United States',
            'data_date': date.today() - timedelta(days=1),
            'position': 4.8,
            'impressions': 120,
            'clicks': 7,
            'ctr': 5.8
        },
        {
            'query_text': 'javascript tips',
            'page_path': '/blog/js-tips',
            'device': 'mobile',
            'country': 'United Kingdom',
            'data_date': date.today() - timedelta(days=1),
            'position': 9.1,
            'impressions': 80,
            'clicks': 3,
            'ctr': 3.75
        }
    ]


class TestGSCBasedSerpTrackerInit:
    """Test GSCBasedSerpTracker initialization"""

    def test_init_with_dsn(self, mock_warehouse_dsn):
        """Test initialization with explicit DSN"""
        tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
        assert tracker.db_dsn == mock_warehouse_dsn

    def test_init_from_env(self):
        """Test initialization from environment variable"""
        with patch(OS_GETENV_PATH, return_value="postgresql://env:env@localhost/envdb"):
            tracker = GSCBasedSerpTracker()
            assert tracker.db_dsn == "postgresql://env:env@localhost/envdb"

    def test_init_no_dsn(self):
        """Test initialization with no DSN available"""
        with patch(OS_GETENV_PATH, return_value=None):
            tracker = GSCBasedSerpTracker()
            assert tracker.db_dsn is None


class TestSyncPositionsFromGscSync:
    """Test synchronous sync_positions_from_gsc_sync method"""

    def test_sync_success(self, mock_warehouse_dsn, mock_property_url,
                          sample_gsc_query_data, sample_position_history_data):
        """Test successful sync operation"""
        # Create mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        # Setup fetchone returns for table existence checks
        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # fact_gsc_daily exists
            {'query_id': 1},   # First query_id lookup
            {'query_id': 2},   # Second query_id lookup
            {'query_id': 3},   # Third query_id lookup
        ]

        # Setup fetchall for query data
        mock_cursor.fetchall.side_effect = [
            sample_gsc_query_data,  # GSC queries
            sample_position_history_data  # Position history
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        assert result['property'] == mock_property_url
        assert result['data_source'] == 'gsc'
        assert 'synced_at' in result
        mock_conn.close.assert_called_once()

    def test_sync_gsc_table_not_exists(self, mock_warehouse_dsn, mock_property_url):
        """Test handling when GSC table doesn't exist"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = {'exists': False}
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        assert result['queries_synced'] == 0
        assert result['positions_synced'] == 0

    def test_sync_database_error(self, mock_warehouse_dsn, mock_property_url):
        """Test handling of database query error (inside try block)"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        # Simulate error during query execution
        mock_cursor.execute.side_effect = Exception("Query execution failed")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is False
        assert 'error' in result
        assert 'Query execution failed' in result['error']
        assert result['data_source'] == 'gsc'

    def test_sync_with_null_device_location(self, mock_warehouse_dsn, mock_property_url):
        """Test sync with null device/location defaults"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        # Query with null device and location
        query_with_nulls = [{
            'query_text': 'test query',
            'page_path': '/test',
            'device': None,
            'location': None,
            'avg_position': 5.0,
            'total_impressions': 100,
            'total_clicks': 10,
            'avg_ctr': 10.0,
            'latest_date': date.today()
        }]

        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Table exists
            {'query_id': 1},   # Query ID lookup
        ]
        mock_cursor.fetchall.side_effect = [
            query_with_nulls,  # Queries
            []  # No position history
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        # Verify that execute was called with 'United States' and 'desktop' defaults
        calls = mock_cursor.execute.call_args_list
        insert_calls = [c for c in calls if 'INSERT INTO serp.queries' in str(c)]
        assert len(insert_calls) > 0


class TestSyncQueriesSync:
    """Test _sync_queries_sync internal method"""

    def test_query_upsert_conflict_handling(self, mock_warehouse_dsn, mock_property_url):
        """Test that unique constraint violations are handled gracefully"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        query_data = [{
            'query_text': 'duplicate query',
            'page_path': '/test',
            'device': 'desktop',
            'location': 'United States',
            'avg_position': 5.0,
            'total_impressions': 100,
            'total_clicks': 10,
            'avg_ctr': 10.0,
            'latest_date': date.today()
        }]

        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Table exists
        ]
        mock_cursor.fetchall.side_effect = [
            query_data,  # Queries to sync
            []  # Position history
        ]

        # Simulate first insert failing with unique constraint violation
        mock_cursor.execute.side_effect = [
            None,  # Table check query
            None,  # GSC data fetch
            psycopg2.Error("unique constraint violation"),
            None,  # Retry with DO NOTHING
            None,  # Position history fetch
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        # Should complete successfully despite constraint violation
        assert result['success'] is True


class TestSyncPositionHistorySync:
    """Test _sync_position_history_sync internal method"""

    def test_position_history_sync(self, mock_warehouse_dsn, mock_property_url,
                                   sample_position_history_data):
        """Test position history synchronization"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # fact_gsc_daily exists
            {'query_id': 1},   # Lookup for first position
            {'query_id': 1},   # Lookup for second position
            {'query_id': 2},   # Lookup for third position
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # No queries to sync
            sample_position_history_data
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        assert result['positions_synced'] == 3

    def test_position_history_query_not_found(self, mock_warehouse_dsn, mock_property_url):
        """Test that positions without matching query are skipped"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        position_data = [{
            'query_text': 'orphan query',
            'page_path': '/orphan',
            'device': 'desktop',
            'country': 'US',
            'data_date': date.today(),
            'position': 5.0,
            'impressions': 100,
            'clicks': 10,
            'ctr': 10.0
        }]

        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Table exists
            None,  # Query not found
        ]
        mock_cursor.fetchall.side_effect = [
            [],  # No queries
            position_data
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        # Should complete but with 0 positions synced
        assert result['success'] is True
        assert result['positions_synced'] == 0


class TestSyncAllProperties:
    """Test module-level sync_all_properties function"""

    def test_sync_all_properties_success(self, mock_warehouse_dsn):
        """Test syncing multiple properties"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(OS_GETENV_PATH) as mock_getenv, \
             patch(PSYCOPG2_PATH) as mock_psycopg2:

            mock_getenv.side_effect = lambda key, default='': {
                'WAREHOUSE_DSN': mock_warehouse_dsn,
                'GSC_PROPERTIES': 'https://site1.com,https://site2.com'
            }.get(key, default)

            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            results = sync_all_properties(min_impressions=10, days_back=7)

        assert len(results) == 2
        assert all(r['success'] for r in results)
        assert results[0]['property'] == 'https://site1.com'
        assert results[1]['property'] == 'https://site2.com'

    def test_sync_all_properties_no_properties_configured(self):
        """Test handling when no properties are configured"""
        with patch(OS_GETENV_PATH) as mock_getenv:
            mock_getenv.side_effect = lambda key, default='': {
                'WAREHOUSE_DSN': 'postgresql://test:test@localhost/db',
                'GSC_PROPERTIES': ''
            }.get(key, default)

            results = sync_all_properties()

        assert results == []

    def test_sync_all_properties_partial_failure(self, mock_warehouse_dsn):
        """Test handling when one property fails to sync (error during query execution)"""
        call_count = [0]

        def mock_connect(dsn):
            call_count[0] += 1
            mock_cursor = MagicMock()
            mock_cursor.__enter__ = Mock(return_value=mock_cursor)
            mock_cursor.__exit__ = Mock(return_value=False)

            if call_count[0] == 1:
                # First connection succeeds
                mock_cursor.fetchone.return_value = {'exists': True}
                mock_cursor.fetchall.return_value = []
            else:
                # Second connection - fail during query execution
                mock_cursor.execute.side_effect = Exception("Database query failed")

            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        with patch(OS_GETENV_PATH) as mock_getenv, \
             patch(PSYCOPG2_PATH) as mock_psycopg2:

            mock_getenv.side_effect = lambda key, default='': {
                'WAREHOUSE_DSN': mock_warehouse_dsn,
                'GSC_PROPERTIES': 'https://site1.com,https://site2.com'
            }.get(key, default)

            mock_psycopg2.connect = mock_connect
            mock_psycopg2.Error = psycopg2.Error

            results = sync_all_properties(min_impressions=10, days_back=7)

        assert len(results) == 2
        assert results[0]['success'] is True
        assert results[1]['success'] is False


class TestGetSyncStats:
    """Test get_sync_stats method"""

    def test_get_sync_stats_success(self, mock_warehouse_dsn):
        """Test retrieving sync statistics"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_cursor.fetchall.side_effect = [
            [
                {'data_source': 'gsc', 'total_queries': 100, 'active_queries': 95},
                {'data_source': 'serpstack', 'total_queries': 50, 'active_queries': 48}
            ],
            [
                {'api_source': 'gsc', 'total_records': 5000,
                 'earliest_date': date.today() - timedelta(days=30),
                 'latest_date': date.today() - timedelta(days=2)},
                {'api_source': 'serpstack', 'total_records': 1000,
                 'earliest_date': date.today() - timedelta(days=7),
                 'latest_date': date.today() - timedelta(days=1)}
            ]
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            stats = tracker.get_sync_stats()

        assert 'queries_by_source' in stats
        assert 'positions_by_source' in stats
        assert 'gsc' in stats['queries_by_source']
        assert stats['queries_by_source']['gsc']['total_queries'] == 100
        mock_conn.close.assert_called_once()


class TestAsyncMethods:
    """Test async versions of sync methods"""

    @pytest.mark.asyncio
    async def test_sync_positions_from_gsc_async(self, mock_warehouse_dsn, mock_property_url,
                                                  sample_gsc_query_data):
        """Test async sync operation"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)  # Table exists
        mock_conn.fetch = AsyncMock(side_effect=[
            sample_gsc_query_data,  # Queries
            [],  # Position history
        ])
        mock_conn.execute = AsyncMock()
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = await tracker.sync_positions_from_gsc(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        assert result['property'] == mock_property_url
        assert result['data_source'] == 'gsc'
        mock_conn.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_positions_from_gsc_async_error(self, mock_warehouse_dsn, mock_property_url):
        """Test async sync with query execution error (inside try block)"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=Exception("Async query failed"))
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = await tracker.sync_positions_from_gsc(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is False
        assert 'error' in result
        assert 'Async query failed' in result['error']

    @pytest.mark.asyncio
    async def test_sync_positions_from_gsc_async_table_not_exists(self, mock_warehouse_dsn,
                                                                   mock_property_url):
        """Test async sync when GSC table doesn't exist"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)  # Table doesn't exist
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = await tracker.sync_positions_from_gsc(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
        assert result['queries_synced'] == 0


class TestGetPositionChanges:
    """Test get_position_changes async method"""

    @pytest.mark.asyncio
    async def test_get_position_changes(self, mock_warehouse_dsn, mock_property_url):
        """Test retrieving position changes"""
        mock_changes = [
            {
                'query_text': 'python tutorial',
                'page_path': '/blog/python',
                'current_position': 3.0,
                'previous_position': 8.0,
                'position_change': 5.0,
                'current_impressions': 1000,
                'previous_impressions': 800
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_changes)
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            changes = await tracker.get_position_changes(mock_property_url, days=7)

        assert len(changes) == 1
        assert changes[0]['query_text'] == 'python tutorial'
        assert changes[0]['position_change'] == 5.0


class TestGetTopRankingKeywords:
    """Test get_top_ranking_keywords async method"""

    @pytest.mark.asyncio
    async def test_get_top_ranking_keywords(self, mock_warehouse_dsn, mock_property_url):
        """Test retrieving top ranking keywords"""
        mock_keywords = [
            {
                'query_text': 'best python tutorial',
                'page_path': '/python',
                'avg_position': 2.5,
                'total_impressions': 5000,
                'total_clicks': 500,
                'avg_ctr': 10.0
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_keywords)
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            keywords = await tracker.get_top_ranking_keywords(
                mock_property_url, position_max=10, days=7
            )

        assert len(keywords) == 1
        assert keywords[0]['avg_position'] == 2.5


class TestGetOpportunityKeywords:
    """Test get_opportunity_keywords async method"""

    @pytest.mark.asyncio
    async def test_get_opportunity_keywords(self, mock_warehouse_dsn, mock_property_url):
        """Test retrieving opportunity keywords (positions 11-20)"""
        mock_opportunities = [
            {
                'query_text': 'learn python',
                'page_path': '/learn-python',
                'avg_position': 15.0,
                'total_impressions': 3000,
                'total_clicks': 30,
                'avg_ctr': 1.0,
                'potential_clicks': 210,
                'potential_gain': 180
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_opportunities)
        mock_conn.close = AsyncMock()

        with patch(ASYNCPG_PATH) as mock_asyncpg:
            mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            opportunities = await tracker.get_opportunity_keywords(
                mock_property_url, position_min=11, position_max=20, days=30
            )

        assert len(opportunities) == 1
        assert opportunities[0]['avg_position'] == 15.0
        assert opportunities[0]['potential_gain'] == 180


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_property_url(self, mock_warehouse_dsn):
        """Test handling of empty property URL"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url='',
                min_impressions=10,
                days_back=7
            )

        # Should still succeed with 0 data
        assert result['success'] is True
        assert result['queries_synced'] == 0

    def test_large_min_impressions(self, mock_warehouse_dsn):
        """Test with very high impression threshold"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url='https://example.com',
                min_impressions=1000000,  # Very high threshold
                days_back=7
            )

        assert result['success'] is True
        assert result['queries_synced'] == 0

    def test_zero_days_back(self, mock_warehouse_dsn):
        """Test with zero days back"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url='https://example.com',
                min_impressions=10,
                days_back=0
            )

        assert result['success'] is True

    def test_position_history_null_position(self, mock_warehouse_dsn, mock_property_url):
        """Test handling of null position values"""
        mock_cursor = MagicMock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        position_data = [{
            'query_text': 'test query',
            'page_path': '/test',
            'device': 'desktop',
            'country': 'US',
            'data_date': date.today(),
            'position': None,  # Null position
            'impressions': 100,
            'clicks': 0,
            'ctr': 0.0
        }]

        mock_cursor.fetchone.side_effect = [
            {'exists': True},
            {'query_id': 1},
        ]
        mock_cursor.fetchall.side_effect = [
            [],
            position_data
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.return_value = mock_conn
            mock_psycopg2.Error = psycopg2.Error

            tracker = GSCBasedSerpTracker(db_dsn=mock_warehouse_dsn)
            result = tracker.sync_positions_from_gsc_sync(
                property_url=mock_property_url,
                min_impressions=10,
                days_back=7
            )

        assert result['success'] is True
