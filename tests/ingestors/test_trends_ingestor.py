"""
Comprehensive Tests for Google Trends Ingestor

Tests both the GoogleTrendsClient and TrendsAccumulator with complete
coverage of all major scenarios including:
- interest_over_time
- related_queries
- empty_keywords
- rate_limiting
- graceful_failure

All tests use mocks and fixtures - NO real API calls.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, date, timedelta
import pandas as pd
import psycopg2
import time

from ingestors.trends.trends_client import (
    GoogleTrendsClient,
    RateLimiter,
    ResponseCache
)
from ingestors.trends.trends_accumulator import TrendsAccumulator


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_pytrends():
    """Create a fully mocked pytrends TrendReq instance"""
    mock = MagicMock()

    # Mock interest_over_time response
    mock.interest_over_time.return_value = pd.DataFrame({
        'python': [50, 60, 70, 65, 75],
        'javascript': [45, 55, 60, 58, 62],
        'isPartial': [False, False, False, False, True]
    }, index=pd.date_range(start='2025-01-01', periods=5, freq='W'))

    # Mock related_queries response
    mock.related_queries.return_value = {
        'python': {
            'top': pd.DataFrame({
                'query': ['python tutorial', 'learn python', 'python programming'],
                'value': [100, 90, 85]
            }),
            'rising': pd.DataFrame({
                'query': ['python 3.12', 'python ai', 'python course'],
                'value': [500, 450, 'Breakout']
            })
        }
    }

    # Mock interest_by_region response
    mock.interest_by_region.return_value = pd.DataFrame({
        'python': [100, 85, 70],
        'geoCode': ['US', 'UK', 'CA']
    }, index=['United States', 'United Kingdom', 'Canada'])

    # Mock trending_searches response
    mock.trending_searches.return_value = pd.DataFrame({
        0: ['trending topic 1', 'trending topic 2', 'trending topic 3']
    })

    return mock


@pytest.fixture
def mock_db_connection():
    """Mock database connection and cursor"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Setup context manager for cursor
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    return mock_conn, mock_cursor


@pytest.fixture
def mock_trends_client():
    """Mock GoogleTrendsClient for accumulator tests"""
    client = MagicMock()

    # Default responses
    client.get_interest_over_time.return_value = pd.DataFrame({
        'test_keyword': [50, 60, 70]
    }, index=pd.date_range(start='2025-01-01', periods=3, freq='D'))

    client.get_related_queries.return_value = {
        'top': pd.DataFrame({
            'query': ['related query 1', 'related query 2'],
            'value': [100, 90]
        }),
        'rising': pd.DataFrame({
            'query': ['rising query 1'],
            'value': [500]
        })
    }

    return client


# ============================================================================
# RateLimiter Tests
# ============================================================================

class TestRateLimiter:
    """Test suite for RateLimiter component"""

    def test_initialization(self):
        """Test rate limiter initializes with correct defaults"""
        limiter = RateLimiter(requests_per_minute=10, burst_limit=3)

        assert limiter.requests_per_minute == 10
        assert limiter.burst_limit == 3
        assert limiter.window_size == 60
        assert len(limiter.request_times) == 0

    def test_get_status_empty(self):
        """Test status reporting with no requests"""
        limiter = RateLimiter(requests_per_minute=10)
        status = limiter.get_status()

        assert status['requests_in_window'] == 0
        assert status['limit'] == 10
        assert status['remaining'] == 10
        assert status['window_size_seconds'] == 60
        assert status['burst_limit'] == 3

    def test_tracks_requests(self):
        """Test that requests are tracked correctly"""
        limiter = RateLimiter(requests_per_minute=100)

        # Make several requests
        limiter.wait()
        limiter.wait()
        limiter.wait()

        status = limiter.get_status()
        assert status['requests_in_window'] == 3
        assert status['remaining'] == 97

    def test_window_cleanup(self):
        """Test that old requests are removed from window"""
        limiter = RateLimiter(requests_per_minute=10)

        # Manually add old request (outside window)
        old_time = time.time() - 70  # 70 seconds ago
        limiter.request_times.append(old_time)

        # Add current request
        limiter.wait()

        # Old request should be cleaned up
        status = limiter.get_status()
        assert status['requests_in_window'] == 1

    def test_rate_limiting_enforced(self):
        """Test that rate limiting actually waits when limit reached"""
        limiter = RateLimiter(requests_per_minute=2, burst_limit=2)

        # Fill up the limit
        limiter.wait()
        limiter.wait()

        # This should trigger a wait
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        # Should have waited (at least a small amount)
        # Being conservative here since timing can be flaky in tests
        assert elapsed > 0.01  # At least 10ms wait


# ============================================================================
# ResponseCache Tests
# ============================================================================

class TestResponseCache:
    """Test suite for ResponseCache component"""

    def test_initialization(self):
        """Test cache initializes correctly"""
        cache = ResponseCache(ttl_minutes=15)
        assert len(cache.cache) == 0

    def test_set_and_get(self):
        """Test basic cache set/get operations"""
        cache = ResponseCache(ttl_minutes=15)

        test_data = {'key': 'value', 'number': 123}
        cache.set('test_key', test_data)

        result = cache.get('test_key')
        assert result == test_data

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = ResponseCache()
        result = cache.get('nonexistent_key')
        assert result is None

    def test_ttl_expiration(self):
        """Test that expired items are not returned"""
        cache = ResponseCache(ttl_minutes=0.001)  # Very short TTL

        cache.set('test_key', 'test_value')

        # Wait for expiration
        time.sleep(0.1)

        result = cache.get('test_key')
        assert result is None

    def test_clear(self):
        """Test cache clearing"""
        cache = ResponseCache()

        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        cache.clear()

        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.get('key3') is None


# ============================================================================
# GoogleTrendsClient Tests
# ============================================================================

class TestGoogleTrendsClient:
    """Test suite for GoogleTrendsClient"""

    def test_initialization(self):
        """Test client initializes with correct components"""
        client = GoogleTrendsClient()

        assert client.rate_limiter is not None
        assert client.cache is not None
        assert client.config is not None
        assert isinstance(client.config, dict)

    def test_default_config(self):
        """Test default configuration values"""
        client = GoogleTrendsClient()

        assert client.config['rate_limit']['requests_per_minute'] == 10
        assert client.config['rate_limit']['burst_limit'] == 3
        assert client.config['cache_ttl_minutes'] == 15
        assert client.config['language'] == 'en-US'
        assert client.config['retries'] == 3

    def test_get_rate_limit_status(self):
        """Test rate limit status reporting"""
        client = GoogleTrendsClient()
        status = client.get_rate_limit_status()

        assert 'requests_in_window' in status
        assert 'limit' in status
        assert 'remaining' in status
        assert isinstance(status['requests_in_window'], int)

    def test_clear_cache(self):
        """Test cache clearing functionality"""
        client = GoogleTrendsClient()

        # Add something to cache
        client.cache.set('test_key', 'test_value')
        assert client.cache.get('test_key') == 'test_value'

        # Clear cache
        client.clear_cache()

        assert client.cache.get('test_key') is None

    def test_get_interest_over_time_empty_keywords(self):
        """Test handling of empty keywords list"""
        client = GoogleTrendsClient()
        result = client.get_interest_over_time([])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_get_interest_over_time_limits_keywords(self, mock_pytrends):
        """Test that keywords are limited to 5 (Google Trends limit)"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            # Try to fetch 7 keywords
            keywords = ['kw1', 'kw2', 'kw3', 'kw4', 'kw5', 'kw6', 'kw7']
            client.get_interest_over_time(keywords)

            # Should only call with first 5
            call_args = mock_pytrends.build_payload.call_args[0]
            assert len(call_args[0]) == 5
            assert call_args[0] == ['kw1', 'kw2', 'kw3', 'kw4', 'kw5']

    def test_get_interest_over_time_success(self, mock_pytrends):
        """Test successful interest over time data retrieval"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_interest_over_time(['python', 'javascript'])

            assert not result.empty
            assert 'python' in result.columns
            assert 'javascript' in result.columns
            assert len(result) == 5

    def test_get_interest_over_time_uses_cache(self):
        """Test that cached data is returned without API call"""
        client = GoogleTrendsClient()

        # Pre-populate cache
        cached_data = pd.DataFrame({'python': [10, 20, 30]})
        cache_key = "interest_python_today 12-m_"
        client.cache.set(cache_key, cached_data)

        # Should return cached data
        result = client.get_interest_over_time(['python'])

        assert result.equals(cached_data)

    def test_get_interest_over_time_custom_timeframe(self, mock_pytrends):
        """Test custom timeframe parameter"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            client.get_interest_over_time(['python'], timeframe='today 3-m')

            call_args = mock_pytrends.build_payload.call_args
            assert call_args[1]['timeframe'] == 'today 3-m'

    def test_get_interest_over_time_api_error_graceful(self, mock_pytrends):
        """Test graceful failure when API errors occur"""
        mock_pytrends.interest_over_time.side_effect = Exception("API Error")

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends
            client.config['retries'] = 1
            client.config['retry_delay'] = 0

            result = client.get_interest_over_time(['python'])

            # Should return empty DataFrame on error
            assert isinstance(result, pd.DataFrame)
            assert result.empty

    def test_get_related_queries_empty_keyword(self):
        """Test handling of empty keyword"""
        client = GoogleTrendsClient()
        result = client.get_related_queries('')

        assert result == {'top': None, 'rising': None}

    def test_get_related_queries_success(self, mock_pytrends):
        """Test successful related queries retrieval"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_related_queries('python')

            assert 'top' in result
            assert 'rising' in result
            assert result['top'] is not None
            assert result['rising'] is not None

    def test_get_related_queries_uses_cache(self):
        """Test that related queries use cache"""
        client = GoogleTrendsClient()

        cached_data = {
            'top': pd.DataFrame({'query': ['cached']}),
            'rising': pd.DataFrame({'query': ['cached_rising']})
        }
        client.cache.set('related_python_', cached_data)

        result = client.get_related_queries('python')

        assert result == cached_data

    def test_get_related_queries_api_error_graceful(self, mock_pytrends):
        """Test graceful failure for related queries errors"""
        mock_pytrends.related_queries.side_effect = Exception("API Error")

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends
            client.config['retries'] = 1
            client.config['retry_delay'] = 0

            result = client.get_related_queries('python')

            assert result == {'top': None, 'rising': None}

    def test_get_regional_interest_empty_keywords(self):
        """Test handling of empty keywords for regional interest"""
        client = GoogleTrendsClient()
        result = client.get_regional_interest([])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_get_regional_interest_success(self, mock_pytrends):
        """Test successful regional interest retrieval"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_regional_interest(['python'], resolution='COUNTRY')

            assert not result.empty
            assert 'python' in result.columns

    def test_get_trending_searches_success(self, mock_pytrends):
        """Test successful trending searches retrieval"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_trending_searches(country='united_states')

            assert not result.empty
            assert len(result) == 3


# ============================================================================
# TrendsAccumulator Tests
# ============================================================================

class TestTrendsAccumulator:
    """Test suite for TrendsAccumulator"""

    def test_initialization(self, mock_trends_client):
        """Test accumulator initializes correctly"""
        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        assert acc.db_dsn == 'test_dsn'
        assert acc.client == mock_trends_client
        assert acc.MAX_KEYWORDS_PER_PROPERTY == 50
        assert acc.MIN_CLICKS_THRESHOLD == 10
        assert acc.DAYS_LOOKBACK == 30

    def test_initialization_uses_env(self, mock_trends_client):
        """Test that accumulator uses environment variable for DSN"""
        with patch.dict('os.environ', {'WAREHOUSE_DSN': 'env_dsn'}):
            acc = TrendsAccumulator(client=mock_trends_client)
            assert acc.db_dsn == 'env_dsn'

    def test_get_tracked_keywords(self, mock_trends_client, mock_db_connection):
        """Test getting tracked keywords from GSC data"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = [
            ('python programming',),
            ('javascript tutorial',),
            ('web development',)
        ]

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            keywords = acc._get_tracked_keywords('sc-domain:example.com')

        assert keywords == ['python programming', 'javascript tutorial', 'web development']
        assert mock_cursor.execute.called

        # Verify query parameters
        call_args = mock_cursor.execute.call_args[0]
        assert 'property = %s' in call_args[0]
        assert 'sc-domain:example.com' in call_args[1]

    def test_get_tracked_keywords_handles_error(self, mock_trends_client):
        """Test error handling when getting keywords"""
        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=psycopg2.Error("DB Error")):
            keywords = acc._get_tracked_keywords('sc-domain:example.com')

        assert keywords == []

    def test_store_interest_data(self, mock_trends_client, mock_db_connection):
        """Test storing interest over time data"""
        mock_conn, mock_cursor = mock_db_connection

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        # Create sample data
        dates = pd.date_range(start='2025-01-01', periods=5, freq='D')
        data = pd.DataFrame({
            'python': [50, 55, 60, 65, 70]
        }, index=dates)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values') as mock_execute:
                rows_stored = acc._store_interest_data('sc-domain:example.com', 'python', data)

        assert rows_stored == 5
        assert mock_execute.called

    def test_store_interest_data_empty_dataframe(self, mock_trends_client):
        """Test handling of empty DataFrame"""
        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        empty_df = pd.DataFrame()

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect'):
            rows_stored = acc._store_interest_data('property', 'keyword', empty_df)

        assert rows_stored == 0

    def test_store_interest_data_handles_nan(self, mock_trends_client, mock_db_connection):
        """Test that NaN values are properly skipped"""
        mock_conn, mock_cursor = mock_db_connection

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        # Create data with NaN
        dates = pd.date_range(start='2025-01-01', periods=3, freq='D')
        data = pd.DataFrame({
            'keyword': [50, float('nan'), 70]
        }, index=dates)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                rows_stored = acc._store_interest_data('property', 'keyword', data)

        # Should only store 2 rows (skipping NaN)
        assert rows_stored == 2

    def test_store_related_queries_top_only(self, mock_trends_client, mock_db_connection):
        """Test storing only top related queries"""
        mock_conn, mock_cursor = mock_db_connection

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        related = {
            'top': pd.DataFrame({
                'query': ['query1', 'query2', 'query3'],
                'value': [100, 90, 80]
            }),
            'rising': None
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = acc._store_related_queries('property', 'keyword', related)

        assert queries_stored == 3

    def test_store_related_queries_rising_only(self, mock_trends_client, mock_db_connection):
        """Test storing only rising related queries"""
        mock_conn, mock_cursor = mock_db_connection

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        related = {
            'top': None,
            'rising': pd.DataFrame({
                'query': ['rising1', 'rising2'],
                'value': [500, 'Breakout']
            })
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = acc._store_related_queries('property', 'keyword', related)

        assert queries_stored == 2

    def test_store_related_queries_both(self, mock_trends_client, mock_db_connection):
        """Test storing both top and rising queries"""
        mock_conn, mock_cursor = mock_db_connection

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        related = {
            'top': pd.DataFrame({
                'query': ['top1', 'top2'],
                'value': [100, 90]
            }),
            'rising': pd.DataFrame({
                'query': ['rising1'],
                'value': [500]
            })
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                queries_stored = acc._store_related_queries('property', 'keyword', related)

        assert queries_stored == 3

    def test_store_related_queries_empty(self, mock_trends_client):
        """Test handling of empty related queries"""
        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        related = {'top': None, 'rising': None}

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect'):
            queries_stored = acc._store_related_queries('property', 'keyword', related)

        assert queries_stored == 0

    def test_collect_for_property_success(self, mock_trends_client, mock_db_connection):
        """Test successful collection for a property"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)  # run_id
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',)
        ]

        # Setup client to return different data for each keyword
        def mock_get_interest(keywords, **kwargs):
            keyword = keywords[0]
            return pd.DataFrame({
                keyword: [50, 60, 70]
            }, index=pd.date_range(start='2025-01-01', periods=3))

        mock_trends_client.get_interest_over_time.side_effect = mock_get_interest

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = acc.collect_for_property('sc-domain:example.com')

        assert stats['property'] == 'sc-domain:example.com'
        assert stats['keywords_collected'] == 2
        assert stats['keywords_failed'] == 0
        assert 'started_at' in stats
        assert 'completed_at' in stats

    def test_collect_for_property_no_keywords(self, mock_trends_client, mock_db_connection):
        """Test collection when no keywords found"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = []  # No keywords

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            stats = acc.collect_for_property('sc-domain:example.com')

        assert stats['keywords_collected'] == 0
        assert stats['keywords_failed'] == 0

    def test_collect_for_property_partial_failure(self, mock_trends_client, mock_db_connection):
        """Test collection with some keywords failing"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',),
            ('keyword3',)
        ]

        # First succeeds, second fails, third succeeds
        def mock_get_interest(keywords, **kwargs):
            keyword = keywords[0]
            if keyword == 'keyword2':
                raise Exception("API Error")
            return pd.DataFrame({
                keyword: [50, 60]
            }, index=pd.date_range(start='2025-01-01', periods=2))

        mock_trends_client.get_interest_over_time.side_effect = mock_get_interest

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = acc.collect_for_property('property')

        assert stats['keywords_collected'] == 2
        assert stats['keywords_failed'] == 1

    def test_collect_all_properties(self, mock_trends_client, mock_db_connection):
        """Test collecting for all properties"""
        mock_conn, mock_cursor = mock_db_connection

        # Mock responses for different DB calls
        mock_cursor.fetchall.side_effect = [
            [('property1',), ('property2',)],  # get_all_properties
            [('keyword1',)],  # keywords for property1
            [('keyword2',)]   # keywords for property2
        ]
        mock_cursor.fetchone.return_value = (1,)  # run_id

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                results = acc.collect_all_properties()

        assert len(results) == 2
        assert results[0]['property'] == 'property1'
        assert results[1]['property'] == 'property2'

    def test_get_keyword_trend(self, mock_trends_client, mock_db_connection):
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
                'interest_score': 60,
                'is_partial': False,
                'collected_at': datetime(2025, 1, 2)
            }
        ]

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            trends = acc.get_keyword_trend('property', 'keyword', days=30)

        assert len(trends) == 2
        assert trends[0]['interest_score'] == 50
        assert trends[1]['interest_score'] == 60


# ============================================================================
# Integration Tests
# ============================================================================

class TestTrendsIngestorIntegration:
    """Integration tests for complete workflows"""

    def test_full_workflow_with_rate_limiting(self, mock_pytrends):
        """Test complete workflow including rate limiting"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            # Make multiple requests
            client.get_interest_over_time(['python'])
            client.get_related_queries('python')
            client.get_interest_over_time(['javascript'])

            # Verify rate limiting tracked all requests
            status = client.get_rate_limit_status()
            assert status['requests_in_window'] == 3
            assert status['remaining'] == 7

    def test_client_and_accumulator_integration(self, mock_pytrends, mock_db_connection):
        """Test integration between client and accumulator"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [('python',)]

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            acc = TrendsAccumulator(db_dsn='test_dsn', client=client)

            with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
                with patch('ingestors.trends.trends_accumulator.execute_values'):
                    stats = acc.collect_for_property('sc-domain:example.com')

            assert stats['keywords_collected'] == 1
            assert stats['related_queries_collected'] == 1

    def test_error_recovery_workflow(self, mock_trends_client, mock_db_connection):
        """Test that system recovers gracefully from errors"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.fetchall.return_value = [
            ('keyword1',),
            ('keyword2',),
            ('keyword3',)
        ]

        # Simulate intermittent failures
        call_count = 0
        def mock_get_interest(keywords, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call fails
                raise Exception("Temporary API error")
            return pd.DataFrame({
                keywords[0]: [50, 60]
            }, index=pd.date_range(start='2025-01-01', periods=2))

        mock_trends_client.get_interest_over_time.side_effect = mock_get_interest

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                stats = acc.collect_for_property('property')

        # Should have 2 successes and 1 failure
        assert stats['keywords_collected'] == 2
        assert stats['keywords_failed'] == 1

    def test_caching_reduces_api_calls(self, mock_pytrends):
        """Test that caching reduces redundant API calls"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            # First call - should hit API
            result1 = client.get_interest_over_time(['python'])
            assert mock_pytrends.build_payload.call_count == 1

            # Second call with same params - should use cache
            result2 = client.get_interest_over_time(['python'])
            assert mock_pytrends.build_payload.call_count == 1  # No additional call

            # Results should be identical
            assert result1.equals(result2)

    def test_retry_logic_with_exponential_backoff(self, mock_pytrends):
        """Test that retry logic works with exponential backoff"""
        # First two calls fail, third succeeds
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return pd.DataFrame({'python': [50, 60, 70]},
                              index=pd.date_range(start='2025-01-01', periods=3))

        mock_pytrends.interest_over_time.side_effect = side_effect

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends
            client.config['retries'] = 3
            client.config['retry_delay'] = 0  # No delay for testing

            result = client.get_interest_over_time(['python'])

            assert not result.empty
            assert call_count == 3  # Tried 3 times

    def test_config_file_loading(self):
        """Test loading configuration from file"""
        import tempfile
        import yaml

        config_data = {
            'google_trends': {
                'rate_limit': {
                    'requests_per_minute': 20,
                    'burst_limit': 5
                },
                'cache_ttl_minutes': 30
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            client = GoogleTrendsClient(config_path=config_path)
            assert client.config['rate_limit']['requests_per_minute'] == 20
            assert client.config['rate_limit']['burst_limit'] == 5
            assert client.config['cache_ttl_minutes'] == 30
        finally:
            import os
            os.unlink(config_path)

    def test_regional_interest_with_error(self, mock_pytrends):
        """Test regional interest with API error"""
        mock_pytrends.interest_by_region.side_effect = Exception("API Error")

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends
            client.config['retries'] = 1
            client.config['retry_delay'] = 0

            result = client.get_regional_interest(['python'])

            assert isinstance(result, pd.DataFrame)
            assert result.empty

    def test_trending_searches_with_error(self, mock_pytrends):
        """Test trending searches with API error"""
        mock_pytrends.trending_searches.side_effect = Exception("API Error")

        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_trending_searches('united_states')

            assert isinstance(result, pd.DataFrame)
            assert result.empty

    def test_accumulator_complete_failure(self, mock_trends_client, mock_db_connection):
        """Test collection run that completely fails"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = (1,)  # run_id

        # Make connect work for run_id but fail on getting keywords
        call_count = 0
        def connect_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:  # Fail after first call (run_id)
                raise Exception("Database connection failed")
            return mock_conn

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=connect_side_effect):
            acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)
            stats = acc.collect_for_property('property')

            # Should still return stats even with error
            assert stats['keywords_collected'] == 0

    def test_get_all_properties_error(self, mock_trends_client):
        """Test error handling in get_all_properties"""
        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=Exception("DB Error")):
            acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)
            properties = acc._get_all_properties()

            assert properties == []

    def test_collect_all_properties_with_one_failure(self, mock_trends_client, mock_db_connection):
        """Test collecting all properties when one property fails"""
        mock_conn, mock_cursor = mock_db_connection

        # Setup different responses for each property collection
        call_count = 0
        def fetchall_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # get_all_properties
                return [('property1',), ('property2',)]
            elif call_count == 2:  # property1 keywords
                return [('keyword1',)]
            elif call_count == 3:  # property2 keywords
                return [('keyword2',)]
            return []

        mock_cursor.fetchall.side_effect = fetchall_side_effect

        # Make second collection fail
        run_id_count = 0
        def fetchone_side_effect(*args, **kwargs):
            nonlocal run_id_count
            run_id_count += 1
            if run_id_count > 1:
                raise Exception("Run start failed")
            return (1,)

        mock_cursor.fetchone.side_effect = fetchone_side_effect

        acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect', return_value=mock_conn):
            with patch('ingestors.trends.trends_accumulator.execute_values'):
                results = acc.collect_all_properties()

        # Should have results for both properties
        assert len(results) == 2
        assert results[0]['property'] == 'property1'
        assert results[1]['property'] == 'property2'

    def test_store_interest_data_with_db_error(self, mock_trends_client):
        """Test database error during interest data storage"""
        data = pd.DataFrame({
            'keyword': [50, 60]
        }, index=pd.date_range(start='2025-01-01', periods=2))

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=Exception("DB Error")):
            acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)
            rows_stored = acc._store_interest_data('property', 'keyword', data)

        assert rows_stored == 0

    def test_store_related_queries_with_db_error(self, mock_trends_client):
        """Test database error during related queries storage"""
        related = {
            'top': pd.DataFrame({'query': ['test'], 'value': [100]}),
            'rising': None
        }

        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=Exception("DB Error")):
            acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)
            queries_stored = acc._store_related_queries('property', 'keyword', related)

        assert queries_stored == 0

    def test_get_collection_health_with_error(self, mock_trends_client):
        """Test error handling in get_collection_health"""
        with patch('ingestors.trends.trends_accumulator.psycopg2.connect',
                   side_effect=Exception("DB Error")):
            acc = TrendsAccumulator(db_dsn='test_dsn', client=mock_trends_client)
            health = acc.get_collection_health()

        assert health == []

    def test_burst_limiting(self):
        """Test that burst limiting prevents too many requests in short time"""
        limiter = RateLimiter(requests_per_minute=100, burst_limit=2)

        # Make burst_limit requests quickly
        limiter.wait()
        limiter.wait()

        # Next request should be rate limited
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start

        # Should have waited (being conservative with timing)
        assert elapsed > 0.01

    def test_interest_over_time_with_geo_filter(self, mock_pytrends):
        """Test interest over time with geographic filtering"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_interest_over_time(['python'], geo='US')

            # Verify geo parameter was passed
            call_args = mock_pytrends.build_payload.call_args
            assert call_args[1]['geo'] == 'US'

    def test_related_queries_with_geo_filter(self, mock_pytrends):
        """Test related queries with geographic filtering"""
        with patch('pytrends.request.TrendReq', return_value=mock_pytrends):
            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            result = client.get_related_queries('python', geo='US')

            # Verify geo parameter was passed
            call_args = mock_pytrends.build_payload.call_args
            assert call_args[1]['geo'] == 'US'
