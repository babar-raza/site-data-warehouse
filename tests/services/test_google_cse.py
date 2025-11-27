"""
Tests for Google Custom Search Engine Analyzer

All tests use mocks - no real API calls are made.
"""
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from services.serp_analyzer.google_cse import (
    GoogleCSEAnalyzer,
    QuotaTracker,
    ResponseCache
)


class TestQuotaTracker:
    """Test quota tracking functionality"""

    def test_initialization(self):
        """Test quota tracker initialization"""
        tracker = QuotaTracker(daily_quota=100)
        assert tracker.daily_quota == 100
        assert tracker.queries_today == 0
        assert tracker.reset_date == datetime.utcnow().date()

    def test_can_query_with_quota(self):
        """Test can_query returns True when quota available"""
        tracker = QuotaTracker(daily_quota=100)
        assert tracker.can_query() is True

    def test_can_query_without_quota(self):
        """Test can_query returns False when quota exhausted"""
        tracker = QuotaTracker(daily_quota=5)
        for _ in range(5):
            tracker.record_query()
        assert tracker.can_query() is False

    def test_record_query(self):
        """Test query recording"""
        tracker = QuotaTracker(daily_quota=100)
        initial = tracker.queries_today
        tracker.record_query()
        assert tracker.queries_today == initial + 1

    def test_get_remaining(self):
        """Test remaining quota calculation"""
        tracker = QuotaTracker(daily_quota=10)
        assert tracker.get_remaining() == 10

        tracker.record_query()
        assert tracker.get_remaining() == 9

        for _ in range(9):
            tracker.record_query()
        assert tracker.get_remaining() == 0

    def test_daily_reset(self):
        """Test quota resets on new day"""
        tracker = QuotaTracker(daily_quota=10)
        tracker.record_query()
        tracker.record_query()
        assert tracker.queries_today == 2

        # Simulate next day
        tracker.reset_date = (datetime.utcnow() - timedelta(days=1)).date()
        tracker._check_reset()

        assert tracker.queries_today == 0
        assert tracker.reset_date == datetime.utcnow().date()

    def test_get_status(self):
        """Test status reporting"""
        tracker = QuotaTracker(daily_quota=100)
        tracker.record_query()

        status = tracker.get_status()
        assert status['daily_quota'] == 100
        assert status['queries_today'] == 1
        assert status['remaining'] == 99
        assert 'reset_date' in status

    def test_thread_safety(self):
        """Test thread-safe operations"""
        tracker = QuotaTracker(daily_quota=100)

        # Should not raise any exceptions
        for _ in range(10):
            tracker.can_query()
            tracker.record_query()
            tracker.get_remaining()


class TestResponseCache:
    """Test response caching functionality"""

    def test_initialization(self):
        """Test cache initialization"""
        cache = ResponseCache(ttl_minutes=60)
        assert cache.ttl == timedelta(minutes=60)
        assert len(cache.cache) == 0

    def test_set_and_get(self):
        """Test setting and getting cached items"""
        cache = ResponseCache(ttl_minutes=60)
        cache.set('key1', {'data': 'value1'})

        result = cache.get('key1')
        assert result == {'data': 'value1'}

    def test_get_nonexistent(self):
        """Test getting non-existent key returns None"""
        cache = ResponseCache(ttl_minutes=60)
        result = cache.get('nonexistent')
        assert result is None

    def test_expiration(self):
        """Test cache expiration"""
        cache = ResponseCache(ttl_minutes=0.001)  # Very short TTL
        cache.set('key1', 'value1')

        # Wait for expiration
        time.sleep(0.1)

        result = cache.get('key1')
        assert result is None

    def test_clear(self):
        """Test cache clearing"""
        cache = ResponseCache(ttl_minutes=60)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')

        cache.clear()
        assert len(cache.cache) == 0
        assert cache.get('key1') is None
        assert cache.get('key2') is None

    def test_multiple_items(self):
        """Test caching multiple items"""
        cache = ResponseCache(ttl_minutes=60)
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')

        assert cache.get('key1') == 'value1'
        assert cache.get('key2') == 'value2'
        assert cache.get('key3') == 'value3'

    def test_overwrite(self):
        """Test overwriting cached items"""
        cache = ResponseCache(ttl_minutes=60)
        cache.set('key1', 'value1')
        cache.set('key1', 'value2')

        assert cache.get('key1') == 'value2'


class TestGoogleCSEAnalyzer:
    """Test Google CSE Analyzer"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance with mock credentials"""
        with patch.dict(os.environ, {
            'GOOGLE_CSE_API_KEY': 'test_api_key',
            'GOOGLE_CSE_ID': 'test_cse_id'
        }):
            return GoogleCSEAnalyzer()

    @pytest.fixture
    def mock_search_response(self):
        """Mock successful search response"""
        return {
            'items': [
                {
                    'title': 'Python Tutorial - Real Python',
                    'link': 'https://realpython.com/python-tutorial',
                    'displayLink': 'realpython.com',
                    'snippet': 'Learn Python programming...',
                    'pagemap': {
                        'cse_thumbnail': [{}],
                        'metatags': [{
                            'og:title': 'Python Tutorial',
                            'og:description': 'Learn Python'
                        }]
                    }
                },
                {
                    'title': 'Python.org Official Docs',
                    'link': 'https://www.python.org/doc',
                    'displayLink': 'python.org',
                    'snippet': 'Official Python documentation...',
                },
                {
                    'title': 'W3Schools Python Tutorial',
                    'link': 'https://www.w3schools.com/python',
                    'displayLink': 'w3schools.com',
                    'snippet': 'Python tutorial for beginners...',
                    'pagemap': {
                        'breadcrumb': [{}]
                    }
                }
            ]
        }

    def test_initialization_with_env_vars(self):
        """Test initialization with environment variables"""
        with patch.dict(os.environ, {
            'GOOGLE_CSE_API_KEY': 'env_api_key',
            'GOOGLE_CSE_ID': 'env_cse_id'
        }):
            analyzer = GoogleCSEAnalyzer()
            assert analyzer.api_key == 'env_api_key'
            assert analyzer.cse_id == 'env_cse_id'

    def test_initialization_with_params(self):
        """Test initialization with explicit parameters"""
        analyzer = GoogleCSEAnalyzer(
            api_key='param_api_key',
            cse_id='param_cse_id'
        )
        assert analyzer.api_key == 'param_api_key'
        assert analyzer.cse_id == 'param_cse_id'

    def test_initialization_without_credentials(self):
        """Test initialization without credentials logs warning"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('services.serp_analyzer.google_cse.logger') as mock_logger:
                analyzer = GoogleCSEAnalyzer()
                assert mock_logger.warning.called

    def test_config_loading(self, tmp_path):
        """Test configuration file loading"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
google_cse:
  daily_quota: 50
  cache_ttl_minutes: 30
  num_results: 5
""")

        analyzer = GoogleCSEAnalyzer(config_path=str(config_file))
        assert analyzer.config['daily_quota'] == 50
        assert analyzer.config['cache_ttl_minutes'] == 30
        assert analyzer.config['num_results'] == 5

    def test_search_without_credentials(self):
        """Test search fails gracefully without credentials"""
        analyzer = GoogleCSEAnalyzer(api_key=None, cse_id=None)
        results = analyzer.search('test query')
        assert results == []

    @patch('requests.get')
    def test_search_success(self, mock_get, analyzer, mock_search_response):
        """Test successful search"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        results = analyzer.search('python tutorial')

        assert len(results) == 3
        assert results[0]['title'] == 'Python Tutorial - Real Python'
        assert results[0]['domain'] == 'realpython.com'
        assert results[0]['position'] == 1
        assert results[1]['position'] == 2
        assert results[2]['position'] == 3

    @patch('requests.get')
    def test_search_with_cache(self, mock_get, analyzer, mock_search_response):
        """Test search uses cache on second call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        # First call - should hit API
        results1 = analyzer.search('python tutorial')
        assert mock_get.call_count == 1

        # Second call - should use cache
        results2 = analyzer.search('python tutorial')
        assert mock_get.call_count == 1  # No additional API call
        assert results1 == results2

    @patch('requests.get')
    def test_search_quota_exceeded(self, mock_get, analyzer):
        """Test search respects quota limits"""
        # Exhaust quota
        analyzer.quota.queries_today = analyzer.quota.daily_quota

        results = analyzer.search('test query')

        assert results == []
        assert not mock_get.called

    @patch('requests.get')
    def test_search_api_error(self, mock_get, analyzer):
        """Test search handles API errors"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = 'Forbidden'
        mock_get.return_value = mock_response

        results = analyzer.search('test query')
        assert results == []

    @patch('requests.get')
    def test_search_rate_limiting(self, mock_get, analyzer):
        """Test search handles rate limiting (429)"""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429

        mock_get.return_value = mock_response_429

        with patch('time.sleep'):  # Don't actually sleep in tests
            results = analyzer.search('test query')

        assert results == []
        assert mock_get.call_count == analyzer.config['retries']

    @patch('requests.get')
    def test_search_retry_logic(self, mock_get, analyzer, mock_search_response):
        """Test search retries on failure then succeeds"""
        mock_response_error = Mock()
        mock_response_error.status_code = 500

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = mock_search_response

        # Fail twice, then succeed
        mock_get.side_effect = [
            Exception("Network error"),
            mock_response_error,
            mock_response_success
        ]

        with patch('time.sleep'):  # Don't actually sleep
            results = analyzer.search('test query')

        assert len(results) == 3
        assert mock_get.call_count == 3

    @patch('requests.get')
    def test_search_parameters(self, mock_get, analyzer, mock_search_response):
        """Test search passes correct parameters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        analyzer.search(
            'test query',
            num_results=5,
            start=11,
            language='es',
            country='mx'
        )

        call_args = mock_get.call_args
        params = call_args[1]['params']

        assert params['q'] == 'test query'
        assert params['num'] == 5
        assert params['start'] == 11
        assert params['lr'] == 'lang_es'
        assert params['gl'] == 'mx'

    @patch('requests.get')
    def test_analyze_serp(self, mock_get, analyzer, mock_search_response):
        """Test SERP analysis"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        analysis = analyzer.analyze_serp('python tutorial', 'realpython.com')

        assert analysis['query'] == 'python tutorial'
        assert analysis['target_domain'] == 'realpython.com'
        assert analysis['target_position'] == 1
        assert analysis['target_result'] is not None
        assert analysis['target_result']['title'] == 'Python Tutorial - Real Python'
        assert len(analysis['competitors']) == 2
        assert analysis['total_results'] == 3
        assert 'analyzed_at' in analysis

    @patch('requests.get')
    def test_analyze_serp_not_found(self, mock_get, analyzer, mock_search_response):
        """Test SERP analysis when target domain not found"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        analysis = analyzer.analyze_serp('python tutorial', 'example.com')

        assert analysis['target_position'] is None
        assert analysis['target_result'] is None
        assert len(analysis['competitors']) == 3  # All are competitors

    @patch('requests.get')
    def test_batch_analyze(self, mock_get, analyzer, mock_search_response):
        """Test batch analysis of multiple queries"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        queries = ['python tutorial', 'python basics', 'learn python']
        results = analyzer.batch_analyze(queries, 'realpython.com')

        assert len(results) == 3
        assert all('query' in r for r in results)
        assert all(r['target_domain'] == 'realpython.com' for r in results)

    @patch('requests.get')
    def test_batch_analyze_quota_limit(self, mock_get, analyzer, mock_search_response):
        """Test batch analysis stops when quota exceeded"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        # Set quota to allow only 2 queries
        analyzer.quota.queries_today = analyzer.quota.daily_quota - 2

        queries = ['query1', 'query2', 'query3', 'query4']
        results = analyzer.batch_analyze(queries, 'example.com')

        assert len(results) == 2

    def test_get_quota_status(self, analyzer):
        """Test quota status reporting"""
        status = analyzer.get_quota_status()

        assert 'daily_quota' in status
        assert 'queries_today' in status
        assert 'remaining' in status
        assert 'reset_date' in status

    def test_clear_cache(self, analyzer):
        """Test cache clearing"""
        analyzer.cache.set('test_key', 'test_value')
        assert analyzer.cache.get('test_key') == 'test_value'

        analyzer.clear_cache()
        assert analyzer.cache.get('test_key') is None

    def test_parse_results(self, analyzer, mock_search_response):
        """Test result parsing"""
        results = analyzer._parse_results(mock_search_response, start_index=1)

        assert len(results) == 3

        # First result with rich snippet
        assert results[0]['position'] == 1
        assert results[0]['title'] == 'Python Tutorial - Real Python'
        assert results[0]['domain'] == 'realpython.com'
        assert results[0]['has_rich_snippet'] is True
        assert results[0]['has_thumbnail'] is True
        assert results[0]['og_title'] == 'Python Tutorial'

        # Second result without rich snippet
        assert results[1]['position'] == 2
        assert results[1]['has_rich_snippet'] is False

        # Third result with breadcrumbs
        assert results[2]['has_breadcrumbs'] is True

    def test_find_position(self, analyzer):
        """Test domain position finding"""
        results = [
            {'domain': 'example.com', 'position': 1},
            {'domain': 'test.org', 'position': 2},
            {'domain': 'sample.net', 'position': 3}
        ]

        assert analyzer._find_position(results, 'example.com') == 1
        assert analyzer._find_position(results, 'test.org') == 2
        assert analyzer._find_position(results, 'notfound.com') is None

    def test_find_position_case_insensitive(self, analyzer):
        """Test domain position finding is case-insensitive"""
        results = [
            {'domain': 'Example.COM', 'position': 1}
        ]

        assert analyzer._find_position(results, 'example.com') == 1
        assert analyzer._find_position(results, 'EXAMPLE.COM') == 1

    def test_find_position_ignores_www(self, analyzer):
        """Test domain position finding ignores www"""
        results = [
            {'domain': 'www.example.com', 'position': 1}
        ]

        assert analyzer._find_position(results, 'example.com') == 1

    def test_find_result(self, analyzer):
        """Test finding result for domain"""
        results = [
            {'domain': 'example.com', 'position': 1, 'title': 'Example'},
            {'domain': 'test.org', 'position': 2, 'title': 'Test'}
        ]

        result = analyzer._find_result(results, 'example.com')
        assert result is not None
        assert result['title'] == 'Example'

        result = analyzer._find_result(results, 'notfound.com')
        assert result is None

    def test_extract_competitors(self, analyzer):
        """Test competitor extraction"""
        results = [
            {'domain': 'example.com', 'position': 1, 'title': 'Example', 'link': 'http://example.com', 'has_rich_snippet': True},
            {'domain': 'competitor1.com', 'position': 2, 'title': 'Competitor 1', 'link': 'http://competitor1.com', 'has_rich_snippet': False},
            {'domain': 'competitor2.org', 'position': 3, 'title': 'Competitor 2', 'link': 'http://competitor2.org', 'has_rich_snippet': True}
        ]

        competitors = analyzer._extract_competitors(results, 'example.com')

        assert len(competitors) == 2
        assert competitors[0]['domain'] == 'competitor1.com'
        assert competitors[0]['position'] == 2
        assert competitors[1]['domain'] == 'competitor2.org'
        assert competitors[1]['position'] == 3

    def test_detect_features(self, analyzer):
        """Test SERP feature detection"""
        results = [
            {
                'has_rich_snippet': True,
                'has_thumbnail': True,
                'has_rating': False,
                'has_breadcrumbs': False
            },
            {
                'has_rich_snippet': True,
                'has_thumbnail': False,
                'has_rating': True,
                'has_breadcrumbs': True
            }
        ]

        features = analyzer._detect_features(results)

        assert 'rich_snippets' in features
        assert 'thumbnails' in features
        assert 'ratings' in features
        assert 'breadcrumbs' in features

    def test_analyze_domain_distribution(self, analyzer):
        """Test domain distribution analysis"""
        results = [
            {'domain': 'example.com'},
            {'domain': 'test.org'},
            {'domain': 'example.com'},
            {'domain': 'sample.net'},
            {'domain': 'example.com'}
        ]

        distribution = analyzer._analyze_domain_distribution(results)

        assert distribution['example.com'] == 3
        assert distribution['test.org'] == 1
        assert distribution['sample.net'] == 1

    def test_extract_domain(self, analyzer):
        """Test domain extraction from URLs"""
        assert analyzer._extract_domain('https://www.example.com/path') == 'www.example.com'
        assert analyzer._extract_domain('http://test.org') == 'test.org'
        assert analyzer._extract_domain('https://sub.domain.com/page?param=value') == 'sub.domain.com'

    def test_extract_domain_invalid(self, analyzer):
        """Test domain extraction from invalid URLs"""
        assert analyzer._extract_domain('invalid url') == ''
        assert analyzer._extract_domain('') == ''

    def test_rate_limiting(self, analyzer):
        """Test rate limiting behavior"""
        # Set a very slow rate
        analyzer.request_interval = 0.1

        start_time = time.time()
        analyzer._wait_for_rate_limit()
        analyzer._wait_for_rate_limit()
        elapsed = time.time() - start_time

        # Should have waited at least request_interval
        assert elapsed >= 0.1

    @patch('requests.get')
    def test_quota_recording(self, mock_get, analyzer, mock_search_response):
        """Test that quota is recorded after API calls"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response
        mock_get.return_value = mock_response

        initial_queries = analyzer.quota.queries_today

        analyzer.search('test query')

        assert analyzer.quota.queries_today == initial_queries + 1

    @patch('requests.get')
    def test_search_timeout(self, mock_get, analyzer):
        """Test search with timeout parameter"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_get.return_value = mock_response

        analyzer.search('test query')

        # Verify timeout was passed to requests
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs['timeout'] == 30


class TestIntegration:
    """Integration tests for the complete workflow"""

    @patch('requests.get')
    def test_complete_analysis_workflow(self, mock_get):
        """Test complete SERP analysis workflow"""
        with patch.dict(os.environ, {
            'GOOGLE_CSE_API_KEY': 'test_key',
            'GOOGLE_CSE_ID': 'test_id'
        }):
            analyzer = GoogleCSEAnalyzer()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'items': [
                    {
                        'title': 'Target Site',
                        'link': 'https://target.com/page',
                        'displayLink': 'target.com',
                        'snippet': 'Target content',
                        'pagemap': {'cse_thumbnail': [{}]}
                    },
                    {
                        'title': 'Competitor 1',
                        'link': 'https://comp1.com/page',
                        'displayLink': 'comp1.com',
                        'snippet': 'Competitor content'
                    }
                ]
            }
            mock_get.return_value = mock_response

            # Execute analysis
            analysis = analyzer.analyze_serp('test query', 'target.com')

            # Verify results
            assert analysis['target_position'] == 1
            assert analysis['target_result']['title'] == 'Target Site'
            assert len(analysis['competitors']) == 1
            assert analysis['competitors'][0]['domain'] == 'comp1.com'
            assert 'thumbnails' in analysis['serp_features']

            # Verify quota was tracked
            status = analyzer.get_quota_status()
            assert status['queries_today'] == 1
            assert status['remaining'] == 99

    @patch('requests.get')
    def test_caching_across_calls(self, mock_get):
        """Test that caching works across multiple calls"""
        with patch.dict(os.environ, {
            'GOOGLE_CSE_API_KEY': 'test_key',
            'GOOGLE_CSE_ID': 'test_id'
        }):
            analyzer = GoogleCSEAnalyzer()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'items': []}
            mock_get.return_value = mock_response

            # First call
            analyzer.search('test query')
            assert mock_get.call_count == 1

            # Second call - should use cache
            analyzer.search('test query')
            assert mock_get.call_count == 1

            # Different query - should call API
            analyzer.search('different query')
            assert mock_get.call_count == 2
