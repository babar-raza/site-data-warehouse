"""
Comprehensive tests for GSC API Ingestor

Tests cover:
- Successful data fetch scenarios
- Empty response handling
- Error conditions and retry logic
- Rate limiting behavior
- Watermark tracking
- Pagination
- Date range handling
- Property filtering
- Data transformation
- Database upsert operations

All tests use mocks - no real API calls or credentials.
"""

import pytest
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, MagicMock, patch, call
from googleapiclient.errors import HttpError

from ingestors.api.gsc_api_ingestor import GSCAPIIngestor, MockGSCService, MockDBConnection
from ingestors.api.rate_limiter import RateLimitConfig, EnterprisRateLimiter
from tests.fixtures.mock_apis import create_mock_gsc_client


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Standard test configuration"""
    return {
        'GSC_SVC_JSON': '/fake/path/gsc_sa.json',
        'DB_HOST': 'test-warehouse',
        'DB_PORT': '5432',
        'DB_NAME': 'test_gsc_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'REQUESTS_PER_MINUTE': '30',
        'REQUESTS_PER_DAY': '2000',
        'BURST_SIZE': '5',
        'API_COOLDOWN_SEC': '0.1',  # Faster for tests
        'GSC_API_ROWS_PER_PAGE': '1000',
        'GSC_API_MAX_RETRIES': '3',
        'BASE_BACKOFF': '0.1',  # Faster for tests
        'MAX_BACKOFF': '1.0',  # Faster for tests
        'BACKOFF_JITTER': 'false',  # Deterministic for tests
        'INGEST_DAYS': '30',
        'GSC_INITIAL_BACKFILL_DAYS': '90'
    }


@pytest.fixture
def mock_gsc_service():
    """Mock GSC service that returns test data"""
    return MockGSCService()


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    conn = MagicMock(spec=MockDBConnection)
    cursor = MagicMock()

    # Configure cursor context manager
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)

    # Default behavior - no existing data
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []

    conn.cursor.return_value = cursor
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()

    return conn


@pytest.fixture
def sample_api_rows() -> List[Dict[str, Any]]:
    """Sample API response rows"""
    return [
        {
            'keys': ['https://example.com/page1', 'test query 1', 'USA', 'MOBILE', '2025-01-15'],
            'clicks': 100,
            'impressions': 1000,
            'ctr': 0.1,
            'position': 5.5
        },
        {
            'keys': ['https://example.com/page2', 'test query 2', 'GBR', 'DESKTOP', '2025-01-15'],
            'clicks': 50,
            'impressions': 500,
            'ctr': 0.1,
            'position': 3.2
        },
        {
            'keys': ['https://example.com/page3', 'test query 3', 'CAN', 'TABLET', '2025-01-15'],
            'clicks': 25,
            'impressions': 250,
            'ctr': 0.1,
            'position': 7.8
        }
    ]


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

class TestGSCIngestorInitialization:
    """Test ingestor initialization and configuration"""

    def test_init_with_valid_config(self, mock_config):
        """Test initialization with valid configuration"""
        ingestor = GSCAPIIngestor(mock_config)

        assert ingestor.config == mock_config
        assert ingestor.service is None
        assert ingestor.conn is None
        assert ingestor.max_rows == 1000
        assert ingestor.ingest_days == 30
        assert ingestor.initial_backfill_days == 90
        assert isinstance(ingestor.rate_limiter, EnterprisRateLimiter)

    def test_init_validates_ingest_days(self, mock_config):
        """Test validation of INGEST_DAYS configuration"""
        # Test invalid values
        mock_config['INGEST_DAYS'] = '0'
        with pytest.raises(ValueError, match="INGEST_DAYS must be a positive integer"):
            GSCAPIIngestor(mock_config)

        mock_config['INGEST_DAYS'] = '-5'
        with pytest.raises(ValueError, match="INGEST_DAYS must be a positive integer"):
            GSCAPIIngestor(mock_config)

        mock_config['INGEST_DAYS'] = 'invalid'
        with pytest.raises(ValueError, match="INGEST_DAYS must be a valid integer"):
            GSCAPIIngestor(mock_config)

    def test_init_validates_initial_backfill_days(self, mock_config):
        """Test validation of GSC_INITIAL_BACKFILL_DAYS configuration"""
        mock_config['GSC_INITIAL_BACKFILL_DAYS'] = '0'
        with pytest.raises(ValueError, match="GSC_INITIAL_BACKFILL_DAYS must be a positive integer"):
            GSCAPIIngestor(mock_config)

        mock_config['GSC_INITIAL_BACKFILL_DAYS'] = '-10'
        with pytest.raises(ValueError, match="GSC_INITIAL_BACKFILL_DAYS must be a positive integer"):
            GSCAPIIngestor(mock_config)

    def test_rate_limiter_configuration(self, mock_config):
        """Test rate limiter is configured correctly from config"""
        ingestor = GSCAPIIngestor(mock_config)

        assert ingestor.rate_limiter.config.requests_per_minute == 30
        assert ingestor.rate_limiter.config.requests_per_day == 2000
        assert ingestor.rate_limiter.config.burst_size == 5
        assert ingestor.rate_limiter.config.max_retries == 3


# =============================================================================
# CONNECTION TESTS
# =============================================================================

class TestConnections:
    """Test GSC and database connections"""

    @patch('ingestors.api.gsc_api_ingestor.os.path.exists')
    @patch('ingestors.api.gsc_api_ingestor.service_account.Credentials.from_service_account_file')
    @patch('ingestors.api.gsc_api_ingestor.build')
    def test_connect_gsc_with_credentials(self, mock_build, mock_creds_from_file, mock_exists, mock_config):
        """Test GSC connection with valid credentials file"""
        mock_exists.return_value = True
        mock_creds = MagicMock()
        mock_creds_from_file.return_value = mock_creds
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_gsc()

        assert ingestor.service == mock_service
        mock_creds_from_file.assert_called_once_with(
            '/fake/path/gsc_sa.json',
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        mock_build.assert_called_once_with('searchconsole', 'v1', credentials=mock_creds)

    @patch('ingestors.api.gsc_api_ingestor.os.path.exists')
    def test_connect_gsc_without_credentials(self, mock_exists, mock_config):
        """Test GSC connection falls back to mock when credentials missing"""
        mock_exists.return_value = False

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_gsc()

        assert isinstance(ingestor.service, MockGSCService)

    @patch('ingestors.api.gsc_api_ingestor.psycopg2.connect')
    def test_connect_warehouse_success(self, mock_psycopg_connect, mock_config, mock_db_connection):
        """Test successful database connection"""
        mock_psycopg_connect.return_value = mock_db_connection

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_warehouse()

        assert ingestor.conn == mock_db_connection
        mock_psycopg_connect.assert_called_once_with(
            host='test-warehouse',
            port=5432,
            database='test_gsc_db',
            user='test_user',
            password='test_pass'
        )

    @patch('ingestors.api.gsc_api_ingestor.psycopg2.connect')
    def test_connect_warehouse_failure_uses_mock(self, mock_psycopg_connect, mock_config):
        """Test database connection failure falls back to mock"""
        mock_psycopg_connect.side_effect = Exception("Connection failed")

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_warehouse()

        assert isinstance(ingestor.conn, MockDBConnection)


# =============================================================================
# PROPERTY AND WATERMARK TESTS
# =============================================================================

class TestPropertyAndWatermarkHandling:
    """Test property discovery and watermark management"""

    def test_get_api_only_properties_success(self, mock_config, mock_db_connection):
        """Test fetching API-only properties from database"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            ('https://example.com/',),
            ('https://blog.example.com/',),
            ('sc-domain:example.net',)
        ]

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        properties = ingestor.get_api_only_properties()

        assert len(properties) == 3
        assert 'https://example.com/' in properties
        assert 'https://blog.example.com/' in properties
        assert 'sc-domain:example.net' in properties

    def test_get_api_only_properties_empty(self, mock_config, mock_db_connection):
        """Test handling when no API-only properties found"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        properties = ingestor.get_api_only_properties()

        assert len(properties) == 0

    def test_get_watermark_with_existing_data(self, mock_config, mock_db_connection):
        """Test fetching watermark when data exists"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (date(2025, 1, 10),)

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        watermark = ingestor.get_watermark('https://example.com/')

        assert watermark == date(2025, 1, 10)
        cursor.execute.assert_called_once()

    def test_get_watermark_no_existing_data(self, mock_config, mock_db_connection):
        """Test watermark returns default when no data exists"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        watermark = ingestor.get_watermark('https://example.com/')

        assert watermark == date(2025, 1, 1)

    def test_update_watermark_success(self, mock_config, mock_db_connection):
        """Test updating watermark after successful ingestion"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        ingestor.update_watermark('https://example.com/', date(2025, 1, 15), 500)

        cursor.execute.assert_called_once()
        mock_db_connection.commit.assert_called_once()

        # Verify SQL parameters
        call_args = cursor.execute.call_args
        assert call_args[0][1][0] == 'https://example.com/'
        assert call_args[0][1][1] == date(2025, 1, 15)
        assert call_args[0][1][2] == 500

    def test_has_data_for_property_with_data(self, mock_config, mock_db_connection):
        """Test checking if property has existing data - data exists"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        has_data = ingestor.has_data_for_property('https://example.com/')

        assert has_data is True

    def test_has_data_for_property_without_data(self, mock_config, mock_db_connection):
        """Test checking if property has existing data - no data"""
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        has_data = ingestor.has_data_for_property('https://example.com/')

        assert has_data is False


# =============================================================================
# DATA FETCH TESTS
# =============================================================================

class TestDataFetching:
    """Test API data fetching scenarios"""

    def test_fetch_success_single_page(self, mock_config, sample_api_rows):
        """Test successful data fetch with single page of results"""
        ingestor = GSCAPIIngestor(mock_config)

        # Use mock service without searchanalytics attribute (uses query_search_analytics method)
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value={'rows': sample_api_rows})
        ingestor.service = mock_service

        rows = ingestor.fetch_search_analytics(
            'https://example.com/',
            date(2025, 1, 15),
            date(2025, 1, 15)
        )

        assert len(rows) == 3
        assert rows[0]['clicks'] == 100
        assert rows[1]['clicks'] == 50
        assert rows[2]['clicks'] == 25

        # Verify API was called once
        assert ingestor.service.query_search_analytics.call_count == 1

    def test_fetch_success_with_pagination(self, mock_config):
        """Test successful data fetch with pagination across multiple pages"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.max_rows = 10  # Small page size to test pagination

        # First page - full page (10 rows)
        page1_rows = [
            {
                'keys': [f'https://example.com/page{i}', f'query {i}', 'USA', 'MOBILE', '2025-01-15'],
                'clicks': i * 10,
                'impressions': i * 100,
                'ctr': 0.1,
                'position': float(i)
            }
            for i in range(10)
        ]

        # Second page - partial (5 rows)
        page2_rows = [
            {
                'keys': [f'https://example.com/page{i}', f'query {i}', 'USA', 'MOBILE', '2025-01-15'],
                'clicks': i * 10,
                'impressions': i * 100,
                'ctr': 0.1,
                'position': float(i)
            }
            for i in range(10, 15)
        ]

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(
            side_effect=[
                {'rows': page1_rows},  # First call
                {'rows': page2_rows}   # Second call (partial page, stops pagination)
            ]
        )
        ingestor.service = mock_service

        rows = ingestor.fetch_search_analytics(
            'https://example.com/',
            date(2025, 1, 15),
            date(2025, 1, 15)
        )

        assert len(rows) == 15
        assert ingestor.service.query_search_analytics.call_count == 2

        # Verify pagination parameters
        calls = ingestor.service.query_search_analytics.call_args_list
        # query_search_analytics(property, request_body)
        # Extract startRow values from all calls
        start_rows = [call.args[1]['startRow'] for call in calls]
        assert 0 in start_rows  # First page starts at 0
        assert 10 in start_rows  # Second page starts at 10

    def test_fetch_empty_response(self, mock_config):
        """Test handling of empty API response"""
        ingestor = GSCAPIIngestor(mock_config)

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value={})
        ingestor.service = mock_service

        rows = ingestor.fetch_search_analytics(
            'https://example.com/',
            date(2025, 1, 15),
            date(2025, 1, 15)
        )

        assert len(rows) == 0

    def test_fetch_with_rate_limiting_429_error(self, mock_config):
        """Test handling of 429 rate limit errors with retry"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.service = MagicMock()

        # Create mock 429 error
        mock_resp = MagicMock()
        mock_resp.status = 429
        error_429 = HttpError(resp=mock_resp, content=b'Rate limit exceeded')

        # First call raises 429, second succeeds
        sample_data = {'rows': [{'keys': ['test'], 'clicks': 1, 'impressions': 10, 'ctr': 0.1, 'position': 5.0}]}

        mock_execute = MagicMock()
        mock_execute.side_effect = [error_429, sample_data]

        mock_query_builder = MagicMock()
        mock_query_builder.execute = mock_execute

        ingestor.service.searchanalytics = Mock(return_value=MagicMock(query=Mock(return_value=mock_query_builder)))

        with patch('time.sleep'):  # Don't actually sleep in tests
            rows = ingestor.fetch_search_analytics(
                'https://example.com/',
                date(2025, 1, 15),
                date(2025, 1, 15)
            )

        assert len(rows) == 1
        assert mock_execute.call_count == 2

    def test_fetch_with_server_error_503_retry(self, mock_config):
        """Test handling of 503 server errors with retry"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.service = MagicMock()

        # Create mock 503 error
        mock_resp = MagicMock()
        mock_resp.status = 503
        error_503 = HttpError(resp=mock_resp, content=b'Service unavailable')

        # First call raises 503, second succeeds
        sample_data = {'rows': [{'keys': ['test'], 'clicks': 1, 'impressions': 10, 'ctr': 0.1, 'position': 5.0}]}

        mock_execute = MagicMock()
        mock_execute.side_effect = [error_503, sample_data]

        mock_query_builder = MagicMock()
        mock_query_builder.execute = mock_execute

        ingestor.service.searchanalytics = Mock(return_value=MagicMock(query=Mock(return_value=mock_query_builder)))

        with patch('time.sleep'):
            rows = ingestor.fetch_search_analytics(
                'https://example.com/',
                date(2025, 1, 15),
                date(2025, 1, 15)
            )

        assert len(rows) == 1
        assert mock_execute.call_count == 2

    def test_fetch_error_max_retries_exceeded(self, mock_config):
        """Test that max retries is enforced on persistent failures"""
        mock_config['GSC_API_MAX_RETRIES'] = '2'  # Only 2 retries
        ingestor = GSCAPIIngestor(mock_config)

        # Always return 429
        mock_resp = MagicMock()
        mock_resp.status = 429
        error_429 = HttpError(resp=mock_resp, content=b'Rate limit exceeded')

        mock_execute = MagicMock()
        mock_execute.side_effect = error_429

        mock_query_builder = MagicMock()
        mock_query_builder.execute = mock_execute

        ingestor.service.searchanalytics = Mock(return_value=MagicMock(query=Mock(return_value=mock_query_builder)))

        with patch('time.sleep'):
            with pytest.raises(HttpError):
                ingestor.fetch_search_analytics(
                    'https://example.com/',
                    date(2025, 1, 15),
                    date(2025, 1, 15)
                )

        # Should have tried initial + max_retries times
        assert mock_execute.call_count == 3  # Initial + 2 retries

    def test_fetch_with_non_retryable_error(self, mock_config):
        """Test that non-retryable errors (like 400) are not retried"""
        ingestor = GSCAPIIngestor(mock_config)

        # Create mock 400 error (bad request)
        mock_resp = MagicMock()
        mock_resp.status = 400
        error_400 = HttpError(resp=mock_resp, content=b'Bad request')

        mock_execute = MagicMock()
        mock_execute.side_effect = error_400

        mock_query_builder = MagicMock()
        mock_query_builder.execute = mock_execute

        ingestor.service.searchanalytics = Mock(return_value=MagicMock(query=Mock(return_value=mock_query_builder)))

        with pytest.raises(HttpError):
            ingestor.fetch_search_analytics(
                'https://example.com/',
                date(2025, 1, 15),
                date(2025, 1, 15)
            )

        # Should only try once (no retry for 400)
        assert mock_execute.call_count == 1


# =============================================================================
# DATA TRANSFORMATION TESTS
# =============================================================================

class TestDataTransformation:
    """Test data transformation from API format to database format"""

    def test_transform_api_row_complete(self, mock_config):
        """Test transforming complete API row to database format"""
        ingestor = GSCAPIIngestor(mock_config)

        api_row = {
            'keys': ['https://example.com/page1', 'test query', 'USA', 'MOBILE', '2025-01-15'],
            'clicks': 100,
            'impressions': 1000,
            'ctr': 0.1,
            'position': 5.5
        }

        result = ingestor.transform_api_row(api_row, 'https://example.com/')

        assert result[0] == date(2025, 1, 15)  # date
        assert result[1] == 'https://example.com/'  # property
        assert result[2] == 'https://example.com/page1'  # page
        assert result[3] == 'test query'  # query
        assert result[4] == 'USA'  # country
        assert result[5] == 'MOBILE'  # device (uppercased)
        assert result[6] == 100  # clicks
        assert result[7] == 1000  # impressions
        assert result[8] == 0.1  # ctr
        assert result[9] == 5.5  # position

    def test_transform_api_row_minimal_keys(self, mock_config):
        """Test transforming row with minimal/missing keys"""
        ingestor = GSCAPIIngestor(mock_config)

        api_row = {
            'keys': ['https://example.com/page1'],  # Only first key
            'clicks': 50,
            'impressions': 500,
            'ctr': 0.1,
            'position': 3.0
        }

        result = ingestor.transform_api_row(api_row, 'https://example.com/')

        assert result[2] == 'https://example.com/page1'  # page
        assert result[3] == ''  # query (missing)
        assert result[4] == ''  # country (missing)
        assert result[5] == ''  # device (missing)

    def test_transform_api_row_missing_metrics(self, mock_config):
        """Test transforming row with missing metrics"""
        ingestor = GSCAPIIngestor(mock_config)

        api_row = {
            'keys': ['https://example.com/page1', 'query', 'USA', 'MOBILE', '2025-01-15']
            # No metrics at all
        }

        result = ingestor.transform_api_row(api_row, 'https://example.com/')

        assert result[6] == 0  # clicks defaults to 0
        assert result[7] == 0  # impressions defaults to 0
        assert result[8] == 0.0  # ctr defaults to 0.0
        assert result[9] == 0.0  # position defaults to 0.0

    def test_transform_api_row_invalid_date(self, mock_config):
        """Test transforming row with invalid date falls back to today"""
        ingestor = GSCAPIIngestor(mock_config)

        api_row = {
            'keys': ['https://example.com/page1', 'query', 'USA', 'MOBILE', 'invalid-date'],
            'clicks': 10,
            'impressions': 100,
            'ctr': 0.1,
            'position': 5.0
        }

        result = ingestor.transform_api_row(api_row, 'https://example.com/')

        # Should fall back to today's date
        assert result[0] == date.today()


# =============================================================================
# DATABASE UPSERT TESTS
# =============================================================================

class TestDatabaseUpsert:
    """Test database upsert operations"""

    @patch('ingestors.api.gsc_api_ingestor.execute_values')
    def test_upsert_data_success(self, mock_execute_values, mock_config, mock_db_connection):
        """Test successful data upsert"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        rows = [
            (date(2025, 1, 15), 'https://example.com/', '/page1', 'query1', 'USA', 'MOBILE', 100, 1000, 0.1, 5.5),
            (date(2025, 1, 15), 'https://example.com/', '/page2', 'query2', 'GBR', 'DESKTOP', 50, 500, 0.1, 3.2),
        ]

        count = ingestor.upsert_data(rows)

        assert count == 2
        mock_execute_values.assert_called_once()
        mock_db_connection.commit.assert_called_once()

    def test_upsert_data_empty_rows(self, mock_config, mock_db_connection):
        """Test upsert with empty row list"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        count = ingestor.upsert_data([])

        assert count == 0
        mock_db_connection.commit.assert_not_called()

    @patch('ingestors.api.gsc_api_ingestor.execute_values')
    def test_upsert_data_database_error(self, mock_execute_values, mock_config, mock_db_connection):
        """Test upsert handles database errors gracefully"""
        mock_execute_values.side_effect = Exception("Database error")

        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        rows = [
            (date(2025, 1, 15), 'https://example.com/', '/page1', 'query1', 'USA', 'MOBILE', 100, 1000, 0.1, 5.5),
        ]

        count = ingestor.upsert_data(rows)

        assert count == 0
        mock_db_connection.rollback.assert_called_once()


# =============================================================================
# PROPERTY INGESTION TESTS
# =============================================================================

class TestPropertyIngestion:
    """Test full property ingestion workflow"""

    def test_ingest_property_initial_backfill(self, mock_config, mock_db_connection):
        """Test initial backfill for property with no existing data"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        # No existing data
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None

        # Mock API response
        sample_response = {
            'rows': [
                {
                    'keys': ['https://example.com/page1', 'query1', 'USA', 'MOBILE', '2025-01-15'],
                    'clicks': 100,
                    'impressions': 1000,
                    'ctr': 0.1,
                    'position': 5.5
                }
            ]
        }

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch.object(ingestor, 'upsert_data', return_value=1) as mock_upsert:
            with patch.object(ingestor, 'update_watermark') as mock_update_watermark:
                stats = ingestor.ingest_property('https://example.com/')

        # Should use initial backfill days (90)
        assert stats['property'] == 'https://example.com/'
        assert stats['rows_processed'] > 0

        # Verify date range (should be 90 days back to yesterday)
        yesterday = date.today() - timedelta(days=1)
        expected_start = yesterday - timedelta(days=89)  # 90 days total including yesterday
        assert stats['start_date'] == expected_start.isoformat()
        assert stats['end_date'] == yesterday.isoformat()

    def test_ingest_property_incremental(self, mock_config, mock_db_connection):
        """Test incremental ingestion for property with existing data"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        # Existing data - property has data
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (1,),  # has_data_for_property
            (date(2025, 1, 10),)  # get_watermark
        ]

        # Mock API response
        sample_response = {
            'rows': [
                {
                    'keys': ['https://example.com/page1', 'query1', 'USA', 'MOBILE', '2025-01-11'],
                    'clicks': 50,
                    'impressions': 500,
                    'ctr': 0.1,
                    'position': 4.0
                }
            ]
        }

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch.object(ingestor, 'upsert_data', return_value=1):
            with patch.object(ingestor, 'update_watermark'):
                stats = ingestor.ingest_property('https://example.com/')

        # Should use incremental ingestion (30 days from watermark)
        assert stats['property'] == 'https://example.com/'
        assert stats['start_date'] == '2025-01-11'  # watermark + 1 day

    def test_ingest_property_already_up_to_date(self, mock_config, mock_db_connection):
        """Test ingestion when property is already up to date"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        # Property already has data up to yesterday
        yesterday = date.today() - timedelta(days=1)
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (1,),  # has_data_for_property
            (yesterday,)  # get_watermark - already at yesterday
        ]

        stats = ingestor.ingest_property('https://example.com/')

        # Should return early with no processing
        assert stats['rows_processed'] == 0
        assert stats['days_processed'] == 0

    def test_ingest_property_handles_errors(self, mock_config, mock_db_connection):
        """Test property ingestion handles errors gracefully"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        # Simulate error checking for existing data
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = Exception("Database error")

        stats = ingestor.ingest_property('https://example.com/')

        assert len(stats['errors']) > 0
        assert 'Database error' in stats['errors'][0]


# =============================================================================
# RATE LIMITER INTEGRATION TESTS
# =============================================================================

class TestRateLimiterIntegration:
    """Test rate limiter integration with API calls"""

    def test_rate_limiter_enforces_delay(self, mock_config):
        """Test that rate limiter delays are enforced"""
        mock_config['API_COOLDOWN_SEC'] = '0.5'  # 500ms cooldown
        ingestor = GSCAPIIngestor(mock_config)

        sample_response = {
            'rows': [
                {'keys': ['test'], 'clicks': 1, 'impressions': 10, 'ctr': 0.1, 'position': 5.0}
            ]
        }

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch('time.sleep') as mock_sleep:
            # Make two consecutive requests
            ingestor.fetch_search_analytics('https://example.com/', date(2025, 1, 15), date(2025, 1, 15))
            ingestor.fetch_search_analytics('https://example.com/', date(2025, 1, 16), date(2025, 1, 16))

            # Should have slept for cooldown between requests
            assert mock_sleep.called

    def test_rate_limiter_metrics_tracked(self, mock_config):
        """Test that rate limiter metrics are properly tracked"""
        ingestor = GSCAPIIngestor(mock_config)

        sample_response = {
            'rows': [
                {'keys': ['test'], 'clicks': 1, 'impressions': 10, 'ctr': 0.1, 'position': 5.0}
            ]
        }

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch('time.sleep'):
            ingestor.fetch_search_analytics('https://example.com/', date(2025, 1, 15), date(2025, 1, 15))

        metrics = ingestor.rate_limiter.get_metrics()

        assert metrics['total_requests'] > 0
        assert 'daily_requests' in metrics
        assert 'daily_quota_remaining' in metrics


# =============================================================================
# DATE RANGE HANDLING TESTS
# =============================================================================

class TestDateRangeHandling:
    """Test date range calculation and handling"""

    def test_date_range_single_day(self, mock_config, mock_db_connection):
        """Test processing single day date range"""
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None  # No existing data

        sample_response = {'rows': []}

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch.object(ingestor, 'update_watermark'):
            stats = ingestor.ingest_property('https://example.com/')

        # Should process multiple days for initial backfill
        assert stats['days_processed'] > 0

    def test_date_range_respects_ingest_days_config(self, mock_config, mock_db_connection):
        """Test that incremental ingestion respects INGEST_DAYS configuration"""
        mock_config['INGEST_DAYS'] = '7'  # Only 7 days incremental
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.conn = mock_db_connection

        # Has existing data
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (1,),  # has_data_for_property
            (date(2025, 1, 1),)  # get_watermark
        ]

        sample_response = {'rows': []}

        # Use mock service without searchanalytics attribute
        mock_service = Mock(spec=[])
        mock_service.query_search_analytics = Mock(return_value=sample_response)
        ingestor.service = mock_service

        with patch.object(ingestor, 'update_watermark'):
            stats = ingestor.ingest_property('https://example.com/')

        # Start date should be watermark + 1
        assert stats['start_date'] == '2025-01-02'
        # End date should be at most start + 7 days or yesterday, whichever is earlier
        start = date(2025, 1, 2)
        yesterday = date.today() - timedelta(days=1)
        expected_end = min(start + timedelta(days=7), yesterday)
        assert stats['end_date'] == expected_end.isoformat()


# =============================================================================
# END-TO-END INTEGRATION TESTS
# =============================================================================

class TestEndToEndIngestion:
    """Test complete ingestion workflows"""

    @patch('ingestors.api.gsc_api_ingestor.psycopg2.connect')
    @patch('ingestors.api.gsc_api_ingestor.os.path.exists')
    def test_run_complete_workflow(self, mock_exists, mock_psycopg_connect, mock_config, mock_db_connection):
        """Test complete run workflow with mock connections"""
        mock_exists.return_value = False  # Use mock GSC service
        mock_psycopg_connect.return_value = mock_db_connection

        # Setup database responses
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = [('https://example.com/',)]

        ingestor = GSCAPIIngestor(mock_config)

        with patch('time.sleep'):  # Don't sleep during tests
            summary = ingestor.run()

        assert 'phase' in summary
        assert summary['phase'] == '3'
        assert 'properties_processed' in summary
        assert 'total_rows' in summary
        assert 'rate_limiter_metrics' in summary
        assert 'start_time' in summary
        assert 'end_time' in summary

    @patch('ingestors.api.gsc_api_ingestor.psycopg2.connect')
    @patch('ingestors.api.gsc_api_ingestor.os.path.exists')
    def test_run_no_properties_found(self, mock_exists, mock_psycopg_connect, mock_config, mock_db_connection):
        """Test run when no properties need processing"""
        mock_exists.return_value = False
        mock_psycopg_connect.return_value = mock_db_connection

        # No properties returned
        cursor = mock_db_connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []

        ingestor = GSCAPIIngestor(mock_config)
        summary = ingestor.run()

        # Should still complete successfully with 0 properties
        assert summary['total_rows'] == 0
        assert len(summary['errors']) == 0

    def test_run_handles_connection_failures(self, mock_config):
        """Test that run handles connection failures gracefully"""
        with patch('ingestors.api.gsc_api_ingestor.os.path.exists', return_value=False):
            with patch('ingestors.api.gsc_api_ingestor.psycopg2.connect', side_effect=Exception("Connection failed")):
                ingestor = GSCAPIIngestor(mock_config)

                # Should not crash, should use mock connections
                summary = ingestor.run()

                assert 'properties_processed' in summary
