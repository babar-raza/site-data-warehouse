"""
Tests for Google Trends Client
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import time

from ingestors.trends.trends_client import (
    GoogleTrendsClient,
    RateLimiter,
    ResponseCache
)


class TestRateLimiter:
    """Test suite for RateLimiter"""

    def test_initialization(self):
        """Test rate limiter initializes correctly"""
        limiter = RateLimiter(requests_per_minute=10, burst_limit=3)
        assert limiter.requests_per_minute == 10
        assert limiter.burst_limit == 3

    def test_get_status(self):
        """Test status reporting"""
        limiter = RateLimiter(requests_per_minute=10)
        status = limiter.get_status()

        assert 'requests_in_window' in status
        assert 'limit' in status
        assert 'remaining' in status
        assert status['limit'] == 10

    def test_tracks_requests(self):
        """Test that requests are tracked"""
        limiter = RateLimiter(requests_per_minute=100)

        # Make some requests
        limiter.wait()
        limiter.wait()
        limiter.wait()

        status = limiter.get_status()
        assert status['requests_in_window'] == 3
        assert status['remaining'] == 97


class TestResponseCache:
    """Test suite for ResponseCache"""

    def test_set_and_get(self):
        """Test basic cache operations"""
        cache = ResponseCache(ttl_minutes=15)

        cache.set('key1', {'data': 'value1'})
        result = cache.get('key1')

        assert result == {'data': 'value1'}

    def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = ResponseCache()
        result = cache.get('nonexistent')
        assert result is None

    def test_clear(self):
        """Test cache clearing"""
        cache = ResponseCache()
        cache.set('key1', 'value1')
        cache.clear()

        assert cache.get('key1') is None


class TestGoogleTrendsClient:
    """Test suite for GoogleTrendsClient"""

    @pytest.fixture
    def mock_pytrends(self):
        """Create mock pytrends"""
        with patch('ingestors.trends.trends_client.TrendReq') as mock:
            yield mock

    @pytest.fixture
    def client(self):
        """Create client with mocked pytrends"""
        with patch('ingestors.trends.trends_client.GoogleTrendsClient.pytrends', new_callable=lambda: MagicMock()):
            client = GoogleTrendsClient()
            return client

    def test_initialization(self):
        """Test client initializes correctly"""
        client = GoogleTrendsClient()
        assert client.rate_limiter is not None
        assert client.cache is not None

    def test_get_rate_limit_status(self):
        """Test rate limit status reporting"""
        client = GoogleTrendsClient()
        status = client.get_rate_limit_status()

        assert 'requests_in_window' in status
        assert 'limit' in status
        assert 'remaining' in status

    def test_get_interest_over_time_empty_keywords(self):
        """Test handling of empty keywords"""
        client = GoogleTrendsClient()
        result = client.get_interest_over_time([])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_get_interest_over_time_limits_keywords(self):
        """Test that keywords are limited to 5"""
        with patch.object(GoogleTrendsClient, 'pytrends') as mock_pytrends:
            mock_pytrends.interest_over_time.return_value = pd.DataFrame()

            client = GoogleTrendsClient()
            client._pytrends = mock_pytrends

            keywords = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
            client.get_interest_over_time(keywords)

            # Check that build_payload was called with max 5 keywords
            call_args = mock_pytrends.build_payload.call_args
            assert len(call_args[0][0]) <= 5

    def test_get_interest_over_time_uses_cache(self):
        """Test that caching works"""
        client = GoogleTrendsClient()

        # Pre-populate cache
        cached_data = pd.DataFrame({'value': [1, 2, 3]})
        cache_key = f"interest_python_today 12-m_"
        client.cache.set(cache_key, cached_data)

        # Should return cached data without calling pytrends
        result = client.get_interest_over_time(['python'])

        assert result.equals(cached_data)

    def test_get_related_queries_empty_keyword(self):
        """Test handling of empty keyword"""
        client = GoogleTrendsClient()
        result = client.get_related_queries('')

        assert result == {'top': None, 'rising': None}

    def test_get_related_queries_uses_cache(self):
        """Test that related queries use cache"""
        client = GoogleTrendsClient()

        cached_data = {'top': 'cached_top', 'rising': 'cached_rising'}
        client.cache.set('related_python_', cached_data)

        result = client.get_related_queries('python')

        assert result == cached_data

    def test_get_regional_interest_empty_keywords(self):
        """Test handling of empty keywords"""
        client = GoogleTrendsClient()
        result = client.get_regional_interest([])

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_clear_cache(self):
        """Test cache clearing"""
        client = GoogleTrendsClient()
        client.cache.set('test_key', 'test_value')

        client.clear_cache()

        assert client.cache.get('test_key') is None

    def test_handles_api_error(self):
        """Test error handling for API failures"""
        with patch('pytrends.request.TrendReq') as mock_trendreq:
            mock_instance = MagicMock()
            mock_instance.interest_over_time.side_effect = Exception("API Error")
            mock_trendreq.return_value = mock_instance

            client = GoogleTrendsClient()
            client._pytrends = mock_instance
            client.config['retries'] = 1
            client.config['retry_delay'] = 0

            result = client.get_interest_over_time(['test'])

            assert isinstance(result, pd.DataFrame)
            assert result.empty

    def test_config_loading_default(self):
        """Test default config is used when no file specified"""
        client = GoogleTrendsClient()

        assert client.config['rate_limit']['requests_per_minute'] == 10
        assert client.config['cache_ttl_minutes'] == 15


class TestGoogleTrendsClientIntegration:
    """Integration tests (still using mocks, no real API calls)"""

    def test_full_workflow(self):
        """Test complete workflow with mocked API"""
        with patch('pytrends.request.TrendReq') as mock_trendreq:
            # Setup mock
            mock_instance = MagicMock()
            mock_instance.interest_over_time.return_value = pd.DataFrame({
                'python': [50, 60, 70],
                'javascript': [40, 45, 50]
            })
            mock_instance.related_queries.return_value = {
                'python': {
                    'top': pd.DataFrame({'query': ['python tutorial']}),
                    'rising': pd.DataFrame({'query': ['python 3.12']})
                }
            }
            mock_trendreq.return_value = mock_instance

            # Create client
            client = GoogleTrendsClient()
            client._pytrends = mock_instance

            # Test interest over time
            interest = client.get_interest_over_time(['python', 'javascript'])
            assert not interest.empty
            assert 'python' in interest.columns

            # Test related queries
            related = client.get_related_queries('python')
            assert related['top'] is not None

            # Verify rate limit tracking
            status = client.get_rate_limit_status()
            assert status['requests_in_window'] >= 2
