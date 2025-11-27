"""
Tests for Google Trends Accumulator
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, date, timedelta
import pandas as pd
import psycopg2

from ingestors.trends.trends_accumulator import TrendsAccumulator


class TestTrendsAccumulator:
    """Test suite for TrendsAccumulator"""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        return mock_conn, mock_cursor

    @pytest.fixture
    def mock_client(self):
        """Mock GoogleTrendsClient"""
        client = MagicMock()
        # Default empty responses
        client.get_interest_over_time.return_value = pd.DataFrame()
        client.get_related_queries.return_value = {'top': None, 'rising': None}
        return client

    @pytest.fixture
    def accumulator(self, mock_client):
        """Create accumulator with mocked client"""
        with patch('ingestors.trends.trends_accumulator.psycopg2.connect'):
            acc = TrendsAccumulator(
                db_dsn='test_dsn',
                client=mock_client
            )
            return acc

    def test_initialization(self):
        """Test accumulator initializes correctly"""
        mock_client = MagicMock()
        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_client)

        assert acc.db_dsn == 'test_dsn'
        assert acc.client == mock_client
        assert acc.MAX_KEYWORDS_PER_PROPERTY == 50

    def test_initialization_uses_env(self):
        """Test that accumulator uses environment variable for DSN"""
        mock_client = MagicMock()
        with patch.dict('os.environ', {'WAREHOUSE_DSN': 'env_dsn'}):
            acc = TrendsAccumulator(client=mock_client)
            assert acc.db_dsn == 'env_dsn'

    def test_get_tracked_keywords(self, accumulator, mock_db_connection):
        """Test getting tracked keywords from GSC data"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',),
            ('keyword3',)
        ]

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            keywords = accumulator._get_tracked_keywords('sc-domain:example.com')

        assert keywords == ['keyword1', 'keyword2', 'keyword3']
        assert mock_cursor.execute.called
        # Verify the query includes property and lookback period
        call_args = mock_cursor.execute.call_args[0]
        assert 'property = %s' in call_args[0]
        assert 'sc-domain:example.com' in call_args[1]

    def test_get_tracked_keywords_handles_error(self, accumulator):
        """Test error handling when getting keywords"""
        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=psycopg2.Error("DB Error")):
            keywords = accumulator._get_tracked_keywords('sc-domain:example.com')

        assert keywords == []

    def test_store_interest_data(self, accumulator, mock_db_connection):
        """Test storing interest over time data"""
        mock_conn, mock_cursor = mock_db_connection

        # Create sample data
        dates = pd.date_range(start='2025-01-01', periods=5, freq='D')
        data = pd.DataFrame({
            'test_keyword': [50, 55, 60, 65, 70]
        }, index=dates)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                rows_stored = accumulator._store_interest_data('sc-domain:example.com', 'test_keyword', data)

        assert rows_stored == 5

    def test_store_interest_data_empty_dataframe(self, accumulator):
        """Test handling of empty DataFrame"""
        empty_df = pd.DataFrame()

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect'):
            rows_stored = accumulator._store_interest_data('property', 'keyword', empty_df)

        assert rows_stored == 0

    def test_store_interest_data_handles_error(self, accumulator):
        """Test error handling when storing interest data"""
        data = pd.DataFrame({'keyword': [50]}, index=[date.today()])

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=psycopg2.Error("DB Error")):
            rows_stored = accumulator._store_interest_data('property', 'keyword', data)

        assert rows_stored == 0

    def test_store_related_queries_top(self, accumulator, mock_db_connection):
        """Test storing top related queries"""
        mock_conn, mock_cursor = mock_db_connection

        related = {
            'top': pd.DataFrame({
                'query': ['related1', 'related2'],
                'value': [100, 90]
            }),
            'rising': None
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = accumulator._store_related_queries('property', 'keyword', related)

        assert queries_stored == 2

    def test_store_related_queries_rising(self, accumulator, mock_db_connection):
        """Test storing rising related queries"""
        mock_conn, mock_cursor = mock_db_connection

        related = {
            'top': None,
            'rising': pd.DataFrame({
                'query': ['rising1', 'rising2'],
                'value': ['Breakout', 500]
            })
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = accumulator._store_related_queries('property', 'keyword', related)

        assert queries_stored == 2

    def test_store_related_queries_both(self, accumulator, mock_db_connection):
        """Test storing both top and rising queries"""
        mock_conn, mock_cursor = mock_db_connection

        related = {
            'top': pd.DataFrame({
                'query': ['top1'],
                'value': [100]
            }),
            'rising': pd.DataFrame({
                'query': ['rising1'],
                'value': [200]
            })
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = accumulator._store_related_queries('property', 'keyword', related)

        assert queries_stored == 2

    def test_store_related_queries_empty(self, accumulator):
        """Test handling of empty related queries"""
        related = {'top': None, 'rising': None}

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect'):
            queries_stored = accumulator._store_related_queries('property', 'keyword', related)

        assert queries_stored == 0

    def test_start_collection_run(self, accumulator, mock_db_connection):
        """Test starting a collection run"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (123,)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            run_id = accumulator._start_collection_run('property')

        assert run_id == 123
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert 'INSERT INTO trends.collection_runs' in call_args[0]

    def test_complete_collection_run(self, accumulator, mock_db_connection):
        """Test completing a collection run"""
        mock_conn, mock_cursor = mock_db_connection

        stats = {
            'keywords_collected': 10,
            'keywords_failed': 2,
            'related_queries_collected': 8
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            accumulator._complete_collection_run(123, 'completed', stats)

        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert 'UPDATE trends.collection_runs' in call_args[0]
        assert call_args[1] == (10, 2, 8, 'completed', None, 123)

    def test_get_all_properties(self, accumulator, mock_db_connection):
        """Test getting all properties"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            ('property1',),
            ('property2',),
            ('property3',)
        ]

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            properties = accumulator._get_all_properties()

        assert properties == ['property1', 'property2', 'property3']

    def test_collect_for_property_success(self, accumulator, mock_db_connection):
        """Test successful collection for a property"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)  # run_id
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',)
        ]

        # Mock client responses - return different data for each keyword
        def mock_get_interest(keywords, **kwargs):
            keyword = keywords[0]
            return pd.DataFrame({
                keyword: [50, 60, 70]
            }, index=pd.date_range(start='2025-01-01', periods=3))

        accumulator.client.get_interest_over_time.side_effect = mock_get_interest

        accumulator.client.get_related_queries.return_value = {
            'top': pd.DataFrame({'query': ['related1'], 'value': [100]}),
            'rising': None
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = accumulator.collect_for_property('sc-domain:example.com')

        assert stats['property'] == 'sc-domain:example.com'
        assert stats['keywords_collected'] == 2
        assert stats['keywords_failed'] == 0
        assert 'started_at' in stats
        assert 'completed_at' in stats

    def test_collect_for_property_no_keywords(self, accumulator, mock_db_connection):
        """Test collection when no keywords found"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = []  # No keywords

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            stats = accumulator.collect_for_property('sc-domain:example.com')

        assert stats['keywords_collected'] == 0
        assert stats['keywords_failed'] == 0

    def test_collect_for_property_partial_failure(self, accumulator, mock_db_connection):
        """Test collection with some keywords failing"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',)
        ]

        # First keyword succeeds, second fails
        def mock_get_interest(keywords, **kwargs):
            if keywords[0] == 'keyword1':
                return pd.DataFrame({
                    'keyword1': [50, 60]
                }, index=pd.date_range(start='2025-01-01', periods=2))
            else:
                raise Exception("API Error")

        accumulator.client.get_interest_over_time.side_effect = mock_get_interest

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = accumulator.collect_for_property('property')

        assert stats['keywords_collected'] == 1
        assert stats['keywords_failed'] == 1

    def test_collect_all_properties(self, accumulator, mock_db_connection):
        """Test collecting for all properties"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.side_effect = [
            [('property1',), ('property2',)],  # get_all_properties
            [('keyword1',)],  # keywords for property1
            [('keyword2',)]   # keywords for property2
        ]
        mock_cursor.fetchone.return_value = (1,)  # run_id

        accumulator.client.get_interest_over_time.return_value = pd.DataFrame({
            'test': [50]
        }, index=[date.today()])

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            results = accumulator.collect_all_properties()

        assert len(results) == 2
        assert results[0]['property'] == 'property1'
        assert results[1]['property'] == 'property2'

    def test_collect_all_properties_no_properties(self, accumulator, mock_db_connection):
        """Test when no properties are configured"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            results = accumulator.collect_all_properties()

        assert results == []

    def test_get_keyword_trend(self, accumulator, mock_db_connection):
        """Test getting keyword trend data"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            {
                'date': date(2025, 1, 1),
                'interest_score': 50,
                'is_partial': False,
                'collected_at': datetime(2025, 1, 1)
            },
            {
                'date': date(2025, 1, 2),
                'interest_score': 55,
                'is_partial': False,
                'collected_at': datetime(2025, 1, 2)
            }
        ]

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            trends = accumulator.get_keyword_trend('property', 'keyword', days=30)

        assert len(trends) == 2
        assert trends[0]['interest_score'] == 50
        assert trends[1]['interest_score'] == 55

    def test_get_keyword_trend_handles_error(self, accumulator):
        """Test error handling when getting trends"""
        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=psycopg2.Error("DB Error")):
            trends = accumulator.get_keyword_trend('property', 'keyword')

        assert trends == []

    def test_get_collection_health(self, accumulator, mock_db_connection):
        """Test getting collection health stats"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            {
                'property': 'property1',
                'total_runs': 10,
                'total_keywords_collected': 100,
                'total_keywords_failed': 5,
                'last_successful_run': datetime(2025, 1, 1),
                'avg_duration_seconds': 45.5
            }
        ]

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            health = accumulator.get_collection_health()

        assert len(health) == 1
        assert health[0]['property'] == 'property1'
        assert health[0]['total_runs'] == 10

    def test_get_collection_health_for_property(self, accumulator, mock_db_connection):
        """Test getting health for specific property"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            health = accumulator.get_collection_health('specific_property')

        # Verify query was called with property filter
        call_args = mock_cursor.execute.call_args[0]
        assert 'WHERE property = %s' in call_args[0]
        assert call_args[1] == ('specific_property',)


class TestTrendsAccumulatorIntegration:
    """Integration-style tests"""

    def test_full_collection_workflow(self):
        """Test complete collection workflow with mocks"""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.get_interest_over_time.return_value = pd.DataFrame({
            'python': [50, 60, 70]
        }, index=pd.date_range(start='2025-01-01', periods=3))

        mock_client.get_related_queries.return_value = {
            'top': pd.DataFrame({'query': ['python tutorial'], 'value': [100]}),
            'rising': pd.DataFrame({'query': ['python 3.12'], 'value': [500]})
        }

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Mock database responses
        mock_cursor.fetchone.return_value = (1,)  # run_id
        mock_cursor.fetchall.return_value = [('python',)]

        accumulator = TrendsAccumulator(db_dsn='test_dsn', client=mock_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = accumulator.collect_for_property('sc-domain:example.com')

        # Verify results
        assert stats['property'] == 'sc-domain:example.com'
        assert stats['keywords_collected'] == 1
        assert stats['keywords_failed'] == 0
        assert stats['related_queries_collected'] == 1

        # Verify client was called correctly
        mock_client.get_interest_over_time.assert_called_once()
        mock_client.get_related_queries.assert_called_once()

    def test_idempotent_collection(self):
        """Test that re-running collection is idempotent"""
        mock_client = MagicMock()
        mock_client.get_interest_over_time.return_value = pd.DataFrame({
            'keyword': [50]
        }, index=[date.today()])

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [('keyword',)]

        accumulator = TrendsAccumulator(db_dsn='test_dsn', client=mock_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values') as mock_execute:
                # Run collection twice
                stats1 = accumulator.collect_for_property('property')
                stats2 = accumulator.collect_for_property('property')

        # Both should succeed
        assert stats1['keywords_collected'] == 1
        assert stats2['keywords_collected'] == 1

        # Verify execute_values was called (idempotent upserts)
        assert mock_execute.called
