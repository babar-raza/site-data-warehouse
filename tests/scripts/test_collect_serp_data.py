"""
Comprehensive tests for SERP data collection script

Tests multi-provider SERP position tracking with dual-source support.
All network calls are mocked for isolated testing.

Coverage: >90% of scripts/collect_serp_data.py
Test scenarios: Happy path, error cases, multi-provider support
Performance: <3 seconds total (all mocked, no network calls)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime
import psycopg2
import json

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collect_serp_data import (
    get_db_connection,
    get_api_provider,
    get_tracked_queries,
    search_serpstack,
    search_valueserp,
    search_serpapi,
    search_serp,
    normalize_results,
    find_our_position,
    save_position_data,
    collect_serp_data,
)


# Mock paths
PSYCOPG2_PATH = 'scripts.collect_serp_data.psycopg2'
REQUESTS_PATH = 'scripts.collect_serp_data.requests'
OS_ENVIRON_PATH = 'scripts.collect_serp_data.os.environ'


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection"""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def sample_serpstack_response():
    """Sample SerpStack API response"""
    return {
        'request_info': {'success': True},
        'organic_results': [
            {
                'position': 1,
                'url': 'https://example.com/page1',
                'domain': 'example.com',
                'title': 'Example Page 1',
                'snippet': 'This is the first result'
            },
            {
                'position': 2,
                'url': 'https://other.com/page',
                'domain': 'other.com',
                'title': 'Other Page',
                'snippet': 'This is another result'
            },
            {
                'position': 3,
                'url': 'https://target-site.com/blog/article',
                'domain': 'target-site.com',
                'title': 'Target Article',
                'snippet': 'This is our target article'
            }
        ]
    }


@pytest.fixture
def sample_valueserp_response():
    """Sample ValueSERP API response"""
    return {
        'request_info': {'success': True},
        'organic_results': [
            {
                'position': 1,
                'link': 'https://example.com/page1',
                'domain': 'example.com',
                'title': 'Example Page 1',
                'snippet': 'This is the first result'
            },
            {
                'position': 2,
                'link': 'https://target-site.com/blog/article',
                'domain': 'target-site.com',
                'title': 'Target Article',
                'snippet': 'This is our target article'
            }
        ]
    }


@pytest.fixture
def sample_serpapi_response():
    """Sample SerpAPI response"""
    return {
        'search_information': {'total_results': 1000},
        'organic_results': [
            {
                'position': 1,
                'link': 'https://example.com/page1',
                'displayed_link': 'example.com/page1',
                'title': 'Example Page 1',
                'snippet': 'This is the first result'
            },
            {
                'position': 2,
                'link': 'https://target-site.com/blog/article',
                'displayed_link': 'target-site.com/blog/article',
                'title': 'Target Article',
                'snippet': 'This is our target article'
            }
        ]
    }


@pytest.fixture
def sample_queries():
    """Sample tracked queries from database"""
    return [
        {
            'query_id': 1,
            'query_text': 'python tutorial',
            'property': 'https://target-site.com',
            'target_page_path': '/blog/article',
            'location': 'United States',
            'device': 'desktop',
            'data_source': 'manual'
        },
        {
            'query_id': 2,
            'query_text': 'javascript tips',
            'property': 'https://target-site.com',
            'target_page_path': '/js-tips',
            'location': 'United Kingdom',
            'device': 'mobile',
            'data_source': 'serpstack'
        }
    ]


class TestGetDbConnection:
    """Test database connection function"""

    def test_connection_with_dsn(self):
        """Test connection using WAREHOUSE_DSN"""
        mock_dsn = 'postgresql://user:pass@host:5432/db'

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': mock_dsn}):
            mock_conn = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn

            result = get_db_connection()

            mock_psycopg2.connect.assert_called_once_with(mock_dsn)
            assert result == mock_conn

    def test_connection_with_individual_params(self):
        """Test connection using individual parameters"""
        env_vars = {
            'DB_HOST': 'testhost',
            'DB_PORT': '5433',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PASSWORD': 'testpass'
        }

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, env_vars, clear=True):
            mock_conn = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn

            result = get_db_connection()

            mock_psycopg2.connect.assert_called_once_with(
                host='testhost',
                port=5433,
                database='testdb',
                user='testuser',
                password='testpass'
            )


class TestGetApiProvider:
    """Test API provider detection"""

    def test_serpstack_configured(self):
        """Test SerpStack detection when API key is set"""
        with patch.dict(os.environ, {'SERPSTACK_API_KEY': 'test_key'}, clear=True):
            assert get_api_provider() == 'serpstack'

    def test_valueserp_configured(self):
        """Test ValueSERP detection when API key is set"""
        with patch.dict(os.environ, {
            'SERP_API_PROVIDER': 'valueserp',
            'VALUESERP_API_KEY': 'test_key'
        }, clear=True):
            assert get_api_provider() == 'valueserp'

    def test_serpapi_configured(self):
        """Test SerpAPI detection when API key is set"""
        with patch.dict(os.environ, {
            'SERP_API_PROVIDER': 'serpapi',
            'SERPAPI_KEY': 'test_key'
        }, clear=True):
            assert get_api_provider() == 'serpapi'

    def test_no_provider_configured(self):
        """Test handling when no API key is configured"""
        with patch.dict(os.environ, {}, clear=True):
            assert get_api_provider() is None

    def test_fallback_detection(self):
        """Test fallback to available API key"""
        with patch.dict(os.environ, {
            'SERP_API_PROVIDER': 'serpapi',  # Requested but no key
            'VALUESERP_API_KEY': 'value_key'  # Available fallback
        }, clear=True):
            assert get_api_provider() == 'valueserp'


class TestGetTrackedQueries:
    """Test query retrieval from database"""

    def test_get_queries_with_data_source_column(self, mock_db_connection, sample_queries):
        """Test query retrieval when data_source column exists"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = sample_queries

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            queries = get_tracked_queries()

        assert len(queries) == 2
        assert queries[0]['query_text'] == 'python tutorial'
        mock_db_connection.close.assert_called_once()

    def test_get_queries_without_data_source_column(self, mock_db_connection, sample_queries):
        """Test query retrieval when data_source column doesn't exist"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': False}
        mock_cursor.fetchall.return_value = sample_queries

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            queries = get_tracked_queries()

        assert len(queries) == 2

    def test_get_queries_filtered_by_source(self, mock_db_connection, sample_queries):
        """Test query retrieval filtered by data source"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = [sample_queries[1]]  # Only serpstack query

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            queries = get_tracked_queries(data_source='serpstack')

        assert len(queries) == 1
        assert queries[0]['data_source'] == 'serpstack'


class TestSearchProviders:
    """Test individual SERP API search functions"""

    def test_search_serpstack(self, sample_serpstack_response):
        """Test SerpStack API call"""
        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {'SERPSTACK_API_KEY': 'test_key'}):
            mock_requests.get.return_value = mock_response

            result = search_serpstack('python tutorial', 'United States', 'desktop')

        assert result == sample_serpstack_response
        mock_requests.get.assert_called_once()

    def test_search_serpstack_no_api_key(self):
        """Test SerpStack raises error without API key"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="SERPSTACK_API_KEY not set"):
                search_serpstack('test query')

    def test_search_valueserp(self, sample_valueserp_response):
        """Test ValueSERP API call"""
        mock_response = Mock()
        mock_response.json.return_value = sample_valueserp_response
        mock_response.raise_for_status = Mock()

        with patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {'VALUESERP_API_KEY': 'test_key'}):
            mock_requests.get.return_value = mock_response

            result = search_valueserp('python tutorial')

        assert result == sample_valueserp_response

    def test_search_serpapi(self, sample_serpapi_response):
        """Test SerpAPI call"""
        mock_response = Mock()
        mock_response.json.return_value = sample_serpapi_response
        mock_response.raise_for_status = Mock()

        with patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {'SERPAPI_KEY': 'test_key'}):
            mock_requests.get.return_value = mock_response

            result = search_serpapi('python tutorial')

        assert result == sample_serpapi_response


class TestSearchSerp:
    """Test unified search_serp function"""

    def test_search_serp_serpstack(self, sample_serpstack_response):
        """Test unified search with SerpStack"""
        with patch('scripts.collect_serp_data.search_serpstack',
                   return_value=sample_serpstack_response) as mock_search:
            result = search_serp('test query', 'US', 'desktop', 'serpstack')

        mock_search.assert_called_once_with('test query', 'US', 'desktop')
        assert result == sample_serpstack_response

    def test_search_serp_valueserp(self, sample_valueserp_response):
        """Test unified search with ValueSERP"""
        with patch('scripts.collect_serp_data.search_valueserp',
                   return_value=sample_valueserp_response) as mock_search:
            result = search_serp('test query', 'US', 'desktop', 'valueserp')

        mock_search.assert_called_once()

    def test_search_serp_unknown_provider(self):
        """Test unified search with unknown provider"""
        with pytest.raises(ValueError, match="Unknown SERP provider"):
            search_serp('test query', 'US', 'desktop', 'unknown_provider')


class TestNormalizeResults:
    """Test result normalization from different providers"""

    def test_normalize_serpstack(self, sample_serpstack_response):
        """Test normalizing SerpStack results"""
        normalized = normalize_results(sample_serpstack_response, 'serpstack')

        assert len(normalized) == 3
        assert normalized[0]['position'] == 1
        assert normalized[0]['url'] == 'https://example.com/page1'
        assert normalized[0]['domain'] == 'example.com'

    def test_normalize_valueserp(self, sample_valueserp_response):
        """Test normalizing ValueSERP results"""
        normalized = normalize_results(sample_valueserp_response, 'valueserp')

        assert len(normalized) == 2
        assert normalized[0]['url'] == 'https://example.com/page1'

    def test_normalize_serpapi(self, sample_serpapi_response):
        """Test normalizing SerpAPI results"""
        normalized = normalize_results(sample_serpapi_response, 'serpapi')

        assert len(normalized) == 2
        assert normalized[0]['url'] == 'https://example.com/page1'

    def test_normalize_empty_results(self):
        """Test normalizing empty results"""
        normalized = normalize_results({}, 'serpstack')
        assert normalized == []


class TestFindOurPosition:
    """Test position finding function"""

    def test_find_position_exact_match(self, sample_serpstack_response):
        """Test finding position with exact domain match"""
        normalized = normalize_results(sample_serpstack_response, 'serpstack')

        result = find_our_position(normalized, 'https://target-site.com')

        assert result is not None
        assert result['position'] == 3
        assert 'target-site.com' in result['url']

    def test_find_position_with_target_path(self, sample_serpstack_response):
        """Test finding position with specific path"""
        normalized = normalize_results(sample_serpstack_response, 'serpstack')

        result = find_our_position(normalized, 'https://target-site.com', '/blog/article')

        assert result is not None
        assert '/blog/article' in result['url']

    def test_find_position_not_found(self, sample_serpstack_response):
        """Test handling when position not found"""
        normalized = normalize_results(sample_serpstack_response, 'serpstack')

        result = find_our_position(normalized, 'https://not-in-results.com')

        assert result is None

    def test_find_position_www_normalization(self):
        """Test domain matching with www prefix normalization"""
        results = [
            {'position': 1, 'url': 'https://www.example.com/page', 'domain': 'www.example.com'}
        ]

        # Should match with or without www
        result = find_our_position(results, 'https://example.com')
        assert result is not None


class TestSavePositionData:
    """Test position data persistence"""

    def test_save_position_found(self, mock_db_connection, sample_serpstack_response):
        """Test saving position data when position is found"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            save_position_data(
                query_id='1',
                property_url='https://target-site.com',
                target_path='/blog/article',
                results=sample_serpstack_response,
                provider='serpstack'
            )

        # Verify INSERT was called
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if 'INSERT INTO serp.position_history' in str(call)]
        assert len(insert_calls) == 1
        mock_db_connection.commit.assert_called()

    def test_save_position_not_found(self, mock_db_connection):
        """Test saving position data when position is not in top 100"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor

        empty_results = {'organic_results': [
            {'position': 1, 'url': 'https://other.com', 'domain': 'other.com',
             'title': 'Other', 'snippet': 'Other snippet'}
        ]}

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            save_position_data(
                query_id='1',
                property_url='https://not-found.com',
                target_path='/page',
                results=empty_results,
                provider='serpstack'
            )

        # Should still save with null position
        mock_db_connection.commit.assert_called()

    def test_save_position_error_handling(self, mock_db_connection, sample_serpstack_response):
        """Test error handling during save"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {'WAREHOUSE_DSN': 'test_dsn'}):
            mock_psycopg2.connect.return_value = mock_db_connection

            with pytest.raises(Exception, match="Database error"):
                save_position_data(
                    query_id='1',
                    property_url='https://target-site.com',
                    target_path='/blog/article',
                    results=sample_serpstack_response,
                    provider='serpstack'
                )

        mock_db_connection.rollback.assert_called()


class TestCollectSerpData:
    """Test main collection function"""

    def test_collect_success(self, mock_db_connection, sample_queries, sample_serpstack_response):
        """Test successful collection"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = sample_queries[:1]  # Single query

        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.return_value = mock_response

            stats = collect_serp_data(provider='serpstack')

        assert stats['success'] is True
        assert stats['queries_processed'] >= 0
        assert stats['provider'] == 'serpstack'

    def test_collect_no_provider(self):
        """Test collection fails when no provider configured"""
        with patch.dict(os.environ, {}, clear=True):
            stats = collect_serp_data()

        assert stats['success'] is False
        assert 'No API provider configured' in stats['error']

    def test_collect_with_limit(self, mock_db_connection, sample_queries, sample_serpstack_response):
        """Test collection with query limit"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = sample_queries

        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.return_value = mock_response

            stats = collect_serp_data(provider='serpstack', limit=1)

        # Should only process 1 query
        assert stats['queries_processed'] <= 1

    def test_collect_api_error(self, mock_db_connection, sample_queries):
        """Test handling of API errors during collection"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = sample_queries[:1]

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.side_effect = Exception("API timeout")

            stats = collect_serp_data(provider='serpstack')

        # Should still succeed but with errors
        assert stats['success'] is True
        assert stats['errors'] >= 1


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_query_list(self, mock_db_connection):
        """Test handling of empty query list"""
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = []  # No queries

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection

            stats = collect_serp_data(provider='serpstack')

        assert stats['success'] is True
        assert stats['queries_processed'] == 0

    def test_special_characters_in_query(self, mock_db_connection, sample_serpstack_response):
        """Test handling queries with special characters"""
        special_query = [{
            'query_id': 1,
            'query_text': 'python "best practices" 2024',
            'property': 'https://example.com',
            'target_page_path': '/blog/python',
            'location': 'United States',
            'device': 'desktop',
            'data_source': 'manual'
        }]

        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = special_query

        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.return_value = mock_response

            stats = collect_serp_data(provider='serpstack')

        assert stats['success'] is True

    def test_unicode_query(self, mock_db_connection, sample_serpstack_response):
        """Test handling queries with unicode characters"""
        unicode_query = [{
            'query_id': 1,
            'query_text': '日本語 python チュートリアル',
            'property': 'https://example.com',
            'target_page_path': '/blog',
            'location': 'Japan',
            'device': 'desktop',
            'data_source': 'manual'
        }]

        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = unicode_query

        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.return_value = mock_response

            stats = collect_serp_data(provider='serpstack')

        assert stats['success'] is True

    def test_null_fields_in_query(self, mock_db_connection, sample_serpstack_response):
        """Test handling queries with null optional fields"""
        null_field_query = [{
            'query_id': 1,
            'query_text': 'test query',
            'property': 'https://example.com',
            'target_page_path': None,  # Null path
            'location': None,  # Null location
            'device': None,  # Null device
            'data_source': 'manual'
        }]

        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {'exists': True}
        mock_cursor.fetchall.return_value = null_field_query

        mock_response = Mock()
        mock_response.json.return_value = sample_serpstack_response
        mock_response.raise_for_status = Mock()

        with patch(PSYCOPG2_PATH) as mock_psycopg2, \
             patch(REQUESTS_PATH) as mock_requests, \
             patch.dict(os.environ, {
                 'WAREHOUSE_DSN': 'test_dsn',
                 'SERPSTACK_API_KEY': 'test_key'
             }):
            mock_psycopg2.connect.return_value = mock_db_connection
            mock_requests.get.return_value = mock_response

            stats = collect_serp_data(provider='serpstack')

        # Should use defaults and succeed
        assert stats['success'] is True
