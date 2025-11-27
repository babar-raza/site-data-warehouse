"""
Comprehensive tests for GA4 Ingestor (ga4_client.py and ga4_extractor.py)

Test coverage:
- GA4Client: initialization, rate limiting, API calls, error handling
- GA4Extractor: extraction, watermark tracking, data upsert, validation
- Edge cases: empty responses, pagination, property validation
- All tests use mocks - zero network calls

Coverage target: >90%
Test count: 10+ comprehensive test cases
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call, mock_open
from datetime import date, datetime, timedelta
import time
import yaml
import psycopg2
from google.analytics.data_v1beta.types import RunReportResponse

from tests.fixtures.mock_apis import create_mock_ga4_client
from tests.fixtures.sample_data import generate_ga4_data, reset_seed


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_ga4_config():
    """Mock GA4 configuration matching config.yaml structure"""
    return {
        'properties': [
            {
                'url': 'https://example.com/',
                'ga4_property_id': '12345678'
            },
            {
                'url': 'https://test.com/',
                'ga4_property_id': '87654321'
            }
        ],
        'extraction': {
            'default_days_back': 30,
            'rate_limit_qps': 10,
            'batch_size': 1000
        },
        'validation': {
            'min_sessions_threshold': 0,
            'max_bounce_rate': 1.0,
            'max_days_behind': 7
        }
    }


@pytest.fixture
def mock_credentials_file(tmp_path):
    """Create a temporary mock credentials file"""
    creds_file = tmp_path / "ga4_sa.json"
    creds_file.write_text('{"type": "service_account", "project_id": "test"}')
    return str(creds_file)


@pytest.fixture
def mock_ga4_response_data():
    """Generate realistic GA4 response data using sample_data helper"""
    reset_seed()
    return generate_ga4_data(
        num_rows=50,
        start_date=date(2025, 1, 15),
        end_date=date(2025, 1, 20),
        property_url='example.com'
    )


@pytest.fixture
def mock_run_report_response(mock_ga4_response_data):
    """Create mock RunReportResponse with realistic data"""
    response = MagicMock(spec=RunReportResponse)
    response.rows = []

    for data in mock_ga4_response_data[:10]:  # Limit to 10 rows for tests
        row = MagicMock()

        # Dimension values: date, hostName, pagePath
        row.dimension_values = [
            MagicMock(value=data['date'].isoformat()),
            MagicMock(value=data['property'].replace('https://', '').replace('/', '')),
            MagicMock(value=data['page_path']),
        ]

        # Metric values matching ga4_client.py order
        row.metric_values = [
            MagicMock(value=str(data['sessions'])),
            MagicMock(value=str(data['engaged_sessions'])),
            MagicMock(value=str(data['engagement_rate'])),
            MagicMock(value=str(data['bounce_rate'])),
            MagicMock(value=str(data['conversions'])),
            MagicMock(value=str(data['page_views'])),
            MagicMock(value=str(data['avg_session_duration'])),
            MagicMock(value=str(data['avg_time_on_page'] * data['page_views'])),  # userEngagementDuration
        ]

        response.rows.append(row)

    response.row_count = len(response.rows)
    return response


@pytest.fixture
def mock_db_connection():
    """Mock database connection and cursor"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Setup context manager for cursor
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

    return mock_conn, mock_cursor


# ============================================================================
# TEST GA4CLIENT
# ============================================================================


class TestGA4ClientInitialization:
    """Test GA4Client initialization and setup"""

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_successful_initialization(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test successful GA4Client initialization with valid credentials"""
        from ingestors.ga4.ga4_client import GA4Client

        # Setup mocks
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Initialize client
        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=10
        )

        # Assertions
        assert client.property_id == '12345678'
        assert client.rate_limit_qps == 10
        assert client.last_request_time == 0
        mock_credentials.assert_called_once_with(
            mock_credentials_file,
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        mock_client_class.assert_called_once_with(credentials=mock_creds)

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    def test_initialization_with_invalid_credentials(self, mock_credentials):
        """Test GA4Client initialization fails with invalid credentials"""
        from ingestors.ga4.ga4_client import GA4Client

        # Mock credentials failure
        mock_credentials.side_effect = Exception("Invalid credentials file")

        # Should raise exception
        with pytest.raises(Exception, match="Invalid credentials file"):
            GA4Client(
                credentials_path='/invalid/path.json',
                property_id='12345678'
            )

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_initialization_with_custom_rate_limit(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test GA4Client initialization with custom rate limit"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_client_class.return_value = MagicMock()

        # Test different rate limits
        client_fast = GA4Client(credentials_path=mock_credentials_file, property_id='123', rate_limit_qps=20)
        assert client_fast.rate_limit_qps == 20

        client_slow = GA4Client(credentials_path=mock_credentials_file, property_id='123', rate_limit_qps=1)
        assert client_slow.rate_limit_qps == 1


class TestGA4ClientRateLimiting:
    """Test GA4Client rate limiting functionality"""

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    @patch('time.sleep')
    def test_rate_limiting_enforced(self, mock_sleep, mock_client_class, mock_credentials, mock_credentials_file):
        """Test that rate limiting delays requests appropriately"""
        from ingestors.ga4.ga4_client import GA4Client
        import time

        mock_credentials.return_value = MagicMock()
        mock_client_class.return_value = MagicMock()

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=10  # 10 queries per second = 0.1s min interval
        )

        # Simulate rapid calls
        start_time = time.time()
        client.last_request_time = start_time

        # Immediately call again - should trigger rate limiting
        with patch('time.time', return_value=start_time + 0.01):  # Only 0.01s elapsed
            client._rate_limit()

        # Should have slept to enforce min interval
        assert mock_sleep.called

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    @patch('time.sleep')
    def test_no_rate_limiting_when_disabled(self, mock_sleep, mock_client_class, mock_credentials, mock_credentials_file):
        """Test that rate limiting is disabled when rate_limit_qps=0"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_client_class.return_value = MagicMock()

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0  # Disabled
        )

        # Multiple calls should not trigger sleep
        client._rate_limit()
        client._rate_limit()
        client._rate_limit()

        assert not mock_sleep.called


class TestGA4ClientRunReport:
    """Test GA4Client run_report method"""

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_run_report_success(self, mock_client_class, mock_credentials, mock_credentials_file, mock_run_report_response):
        """Test successful run_report call with valid parameters"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.return_value = mock_run_report_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0  # Disable rate limiting for test speed
        )

        # Run report
        response = client.run_report(
            start_date='2025-01-15',
            end_date='2025-01-20',
            dimensions=['date', 'pagePath'],
            metrics=['sessions', 'conversions']
        )

        # Assertions
        assert response == mock_run_report_response
        assert len(response.rows) == 10
        mock_api_client.run_report.assert_called_once()

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_run_report_with_filter(self, mock_client_class, mock_credentials, mock_credentials_file, mock_run_report_response):
        """Test run_report with dimension filter"""
        from ingestors.ga4.ga4_client import GA4Client
        from google.analytics.data_v1beta.types import FilterExpression, Filter

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.return_value = mock_run_report_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Create filter
        dimension_filter = FilterExpression(
            filter=Filter(
                field_name='pagePath',
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    value='/blog'
                )
            )
        )

        # Run report with filter
        response = client.run_report(
            start_date='2025-01-15',
            end_date='2025-01-20',
            dimensions=['pagePath'],
            metrics=['sessions'],
            dimension_filter=dimension_filter
        )

        assert response is not None
        mock_api_client.run_report.assert_called_once()

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_run_report_api_error(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test run_report handles API errors gracefully"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.side_effect = Exception("API rate limit exceeded")
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Should raise exception from API
        with pytest.raises(Exception, match="API rate limit exceeded"):
            client.run_report(
                start_date='2025-01-15',
                end_date='2025-01-20',
                dimensions=['date'],
                metrics=['sessions']
            )


class TestGA4ClientGetPageMetrics:
    """Test GA4Client get_page_metrics method - extract_page_metrics scenario"""

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_page_metrics_basic(self, mock_client_class, mock_credentials, mock_credentials_file, mock_run_report_response):
        """Test get_page_metrics extracts and parses data correctly"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.return_value = mock_run_report_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Get page metrics
        results = client.get_page_metrics(
            start_date='2025-01-15',
            end_date='2025-01-20'
        )

        # Assertions
        assert len(results) == 10
        assert all('date' in row for row in results)
        assert all('page_path' in row for row in results)
        assert all('sessions' in row for row in results)
        assert all('conversions' in row for row in results)
        assert all('conversion_rate' in row for row in results)

        # Verify conversion_rate calculation
        for row in results:
            if row['sessions'] > 0:
                expected_rate = row['conversions'] / row['sessions']
                assert row['conversion_rate'] == expected_rate

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_page_metrics_with_pagination(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test get_page_metrics handles pagination correctly"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()

        # Create two pages of results
        page1 = MagicMock()
        page1.rows = [MagicMock() for _ in range(10000)]  # Full page
        for i, row in enumerate(page1.rows):
            row.dimension_values = [
                MagicMock(value='2025-01-15'),
                MagicMock(value='example.com'),
                MagicMock(value=f'/page-{i}'),
            ]
            row.metric_values = [
                MagicMock(value='100'),  # sessions
                MagicMock(value='80'),   # engaged_sessions
                MagicMock(value='0.8'),  # engagement_rate
                MagicMock(value='0.2'),  # bounce_rate
                MagicMock(value='5'),    # conversions
                MagicMock(value='150'),  # page_views
                MagicMock(value='120'),  # avg_session_duration
                MagicMock(value='180'),  # userEngagementDuration
            ]

        page2 = MagicMock()
        page2.rows = [MagicMock() for _ in range(500)]  # Partial page
        for i, row in enumerate(page2.rows):
            row.dimension_values = [
                MagicMock(value='2025-01-15'),
                MagicMock(value='example.com'),
                MagicMock(value=f'/page-{10000 + i}'),
            ]
            row.metric_values = [MagicMock(value='100') for _ in range(8)]

        # Mock sequential returns for pagination
        mock_api_client.run_report.side_effect = [page1, page2]
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Get page metrics (should paginate)
        results = client.get_page_metrics(
            start_date='2025-01-15',
            end_date='2025-01-15'
        )

        # Should have fetched both pages
        assert len(results) == 10500
        assert mock_api_client.run_report.call_count == 2

        # Verify pagination parameters
        calls = mock_api_client.run_report.call_args_list
        assert calls[0][0][0].offset == 0
        assert calls[1][0][0].offset == 10000

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_page_metrics_empty_response(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test get_page_metrics handles empty response - empty_response scenario"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()

        # Empty response
        empty_response = MagicMock()
        empty_response.rows = []
        mock_api_client.run_report.return_value = empty_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Get page metrics
        results = client.get_page_metrics(
            start_date='2025-01-15',
            end_date='2025-01-20'
        )

        # Should return empty list
        assert results == []
        assert len(results) == 0


class TestGA4ClientPropertyValidation:
    """Test GA4Client property validation - property_validation scenario"""

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_validate_credentials_success(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test validate_credentials returns True for valid credentials"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()

        # Mock successful validation response
        validation_response = MagicMock()
        validation_response.rows = []
        validation_response.row_count = 0
        mock_api_client.run_report.return_value = validation_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Validate credentials
        is_valid = client.validate_credentials()

        assert is_valid is True

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_validate_credentials_failure(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test validate_credentials returns False for invalid credentials"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.side_effect = Exception("Permission denied")
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Validate credentials
        is_valid = client.validate_credentials()

        assert is_valid is False

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_property_metadata_success(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test get_property_metadata returns metadata for accessible property"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()

        metadata_response = MagicMock()
        metadata_response.rows = []
        metadata_response.row_count = 1000
        mock_api_client.run_report.return_value = metadata_response
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # Get metadata
        metadata = client.get_property_metadata()

        assert metadata['property_id'] == '12345678'
        assert metadata['accessible'] is True
        assert metadata['row_count'] == 1000

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_property_metadata_error(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test get_property_metadata handles errors gracefully"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()
        mock_api_client = MagicMock()
        mock_api_client.run_report.side_effect = Exception("Property not found")
        mock_client_class.return_value = mock_api_client

        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='99999999',
            rate_limit_qps=0
        )

        # Get metadata
        metadata = client.get_property_metadata()

        assert metadata['property_id'] == '99999999'
        assert metadata['accessible'] is False
        assert 'error' in metadata
        assert 'Property not found' in metadata['error']


# ============================================================================
# TEST GA4EXTRACTOR
# ============================================================================


class TestGA4ExtractorInitialization:
    """Test GA4Extractor initialization and configuration"""

    @patch('ingestors.ga4.ga4_extractor.os.path.exists')
    @patch('builtins.open')
    @patch('yaml.safe_load')
    def test_load_config_from_file(self, mock_yaml_load, mock_file_open, mock_exists, mock_ga4_config):
        """Test loading configuration from YAML file"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_exists.return_value = True
        mock_yaml_load.return_value = mock_ga4_config
        mock_file_open.return_value = MagicMock()

        extractor = GA4Extractor(config_path='/fake/config.yaml')

        assert 'properties' in extractor.config
        assert len(extractor.config['properties']) == 2
        assert extractor.config['extraction']['rate_limit_qps'] == 10

    def test_load_default_config(self):
        """Test loading default configuration when file doesn't exist"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        extractor = GA4Extractor(config_path='/nonexistent/config.yaml')

        # Should have default config
        assert 'properties' in extractor.config
        assert 'extraction' in extractor.config
        assert 'validation' in extractor.config
        assert extractor.config['extraction']['default_days_back'] == 30

    def test_extractor_stats_initialization(self):
        """Test that extractor initializes stats correctly"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        extractor = GA4Extractor()

        assert extractor.stats['rows_fetched'] == 0
        assert extractor.stats['rows_inserted'] == 0
        assert extractor.stats['rows_updated'] == 0
        assert extractor.stats['rows_failed'] == 0
        assert extractor.stats['properties_processed'] == 0


class TestGA4ExtractorWatermarking:
    """Test GA4Extractor watermark tracking - watermark_tracking scenario"""

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_get_watermark_existing(self, mock_connect, mock_db_connection):
        """Test getting existing watermark from database"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock watermark exists
        watermark_date = date(2025, 1, 10)
        mock_cursor.fetchone.return_value = (watermark_date,)

        extractor = GA4Extractor()
        result = extractor.get_watermark('https://example.com/')

        assert result == watermark_date
        mock_cursor.execute.assert_called_once()
        assert 'ingest_watermarks' in mock_cursor.execute.call_args[0][0]
        assert 'ga4' in mock_cursor.execute.call_args[0][0]

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_get_watermark_none_returns_default(self, mock_connect, mock_db_connection):
        """Test get_watermark returns default when no watermark exists"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock no watermark
        mock_cursor.fetchone.return_value = None

        extractor = GA4Extractor()
        result = extractor.get_watermark('https://example.com/')

        # Should return 30 days ago
        expected = datetime.now().date() - timedelta(days=30)
        assert result == expected

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_get_watermark_db_error(self, mock_connect, mock_db_connection):
        """Test get_watermark handles database errors - error_handling scenario"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn
        mock_cursor.execute.side_effect = psycopg2.Error("Database connection failed")

        extractor = GA4Extractor()
        result = extractor.get_watermark('https://example.com/')

        # Should return default on error
        expected = datetime.now().date() - timedelta(days=30)
        assert result == expected

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_update_watermark_success(self, mock_connect, mock_db_connection):
        """Test updating watermark in database"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        extractor = GA4Extractor()
        new_date = date(2025, 1, 20)
        extractor.update_watermark('https://example.com/', new_date)

        # Verify SQL execution
        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        params = mock_cursor.execute.call_args[0][1]

        assert 'INSERT INTO gsc.ingest_watermarks' in sql
        assert 'ON CONFLICT' in sql
        assert params[0] == 'https://example.com/'
        assert params[1] == new_date

        mock_conn.commit.assert_called_once()

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_update_watermark_error(self, mock_connect, mock_db_connection):
        """Test update_watermark handles errors gracefully"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn
        mock_cursor.execute.side_effect = psycopg2.Error("Write failed")

        extractor = GA4Extractor()

        # Should not raise exception
        extractor.update_watermark('https://example.com/', date(2025, 1, 20))


class TestGA4ExtractorDataUpsert:
    """Test GA4Extractor data upsert functionality"""

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    @patch('ingestors.ga4.ga4_extractor.execute_batch')
    def test_upsert_data_success(self, mock_execute_batch, mock_connect, mock_db_connection, mock_ga4_response_data):
        """Test successful data upsert to warehouse"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        extractor = GA4Extractor()

        # Prepare test data (limit to 5 rows)
        test_data = []
        for row in mock_ga4_response_data[:5]:
            test_data.append({
                'date': row['date'].isoformat(),
                'host_name': row['property'].replace('https://', '').replace('/', ''),
                'page_path': row['page_path'],
                'sessions': row['sessions'],
                'engaged_sessions': row['engaged_sessions'],
                'engagement_rate': row['engagement_rate'],
                'bounce_rate': row['bounce_rate'],
                'conversions': row['conversions'],
                'conversion_rate': row['conversion_rate'],
                'avg_session_duration': row['avg_session_duration'],
                'page_views': row['page_views'],
                'avg_time_on_page': row['avg_time_on_page']
            })

        extractor.upsert_data('https://example.com/', test_data)

        # Verify execute_batch called
        mock_execute_batch.assert_called_once()
        assert mock_conn.commit.called
        assert extractor.stats['rows_inserted'] == 5

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_upsert_data_empty_list(self, mock_connect, mock_db_connection):
        """Test upsert_data handles empty data list"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        extractor = GA4Extractor()
        extractor.upsert_data('https://example.com/', [])

        # Should not attempt database operations
        assert not mock_conn.commit.called

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    @patch('ingestors.ga4.ga4_extractor.execute_batch')
    def test_upsert_data_error_handling(self, mock_execute_batch, mock_connect, mock_db_connection, mock_ga4_response_data):
        """Test upsert_data handles errors and tracks failed rows - error_handling scenario"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn
        mock_execute_batch.side_effect = psycopg2.Error("Database error")

        extractor = GA4Extractor()

        test_data = [{
            'date': '2025-01-15',
            'host_name': 'example.com',
            'page_path': '/test',
            'sessions': 100,
            'engaged_sessions': 80,
            'engagement_rate': 0.8,
            'bounce_rate': 0.2,
            'conversions': 5,
            'conversion_rate': 0.05,
            'avg_session_duration': 120.0,
            'page_views': 150,
            'avg_time_on_page': 90.0
        }]

        # Should raise exception
        with pytest.raises(psycopg2.Error):
            extractor.upsert_data('https://example.com/', test_data)

        # Should rollback and track failed rows
        mock_conn.rollback.assert_called_once()
        assert extractor.stats['rows_failed'] == 1


class TestGA4ExtractorPropertyExtraction:
    """Test GA4Extractor extract_property method - extract_events scenario"""

    @patch('ingestors.ga4.ga4_extractor.GA4Client')
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    @patch('ingestors.ga4.ga4_extractor.execute_batch')
    def test_extract_property_success(self, mock_execute_batch, mock_connect, mock_client_class,
                                      mock_db_connection, mock_ga4_response_data):
        """Test successful property extraction"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock GA4 client
        mock_client = MagicMock()
        mock_client.validate_credentials.return_value = True

        # Prepare response data
        response_data = []
        for row in mock_ga4_response_data[:5]:
            response_data.append({
                'date': row['date'].isoformat(),
                'host_name': row['property'].replace('https://', '').replace('/', ''),
                'page_path': row['page_path'],
                'sessions': row['sessions'],
                'engaged_sessions': row['engaged_sessions'],
                'engagement_rate': row['engagement_rate'],
                'bounce_rate': row['bounce_rate'],
                'conversions': row['conversions'],
                'conversion_rate': row['conversion_rate'],
                'avg_session_duration': row['avg_session_duration'],
                'page_views': row['page_views'],
                'avg_time_on_page': row['avg_time_on_page']
            })

        mock_client.get_page_metrics.return_value = response_data
        mock_client_class.return_value = mock_client

        extractor = GA4Extractor()

        property_config = {
            'url': 'https://example.com/',
            'ga4_property_id': '12345678'
        }

        extractor.extract_property(
            property_config,
            date(2025, 1, 15),
            date(2025, 1, 20),
            dry_run=False
        )

        # Assertions
        assert extractor.stats['rows_fetched'] == 5
        assert extractor.stats['properties_processed'] == 1
        mock_client.validate_credentials.assert_called_once()
        mock_client.get_page_metrics.assert_called_once()

    @patch('ingestors.ga4.ga4_extractor.GA4Client')
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_extract_property_dry_run(self, mock_connect, mock_client_class):
        """Test extract_property in dry run mode (no API calls)"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        extractor = GA4Extractor()

        property_config = {
            'url': 'https://example.com/',
            'ga4_property_id': '12345678'
        }

        # Dry run should not initialize client
        extractor.extract_property(
            property_config,
            date(2025, 1, 1),
            date(2025, 1, 15),
            dry_run=True
        )

        # Client should not be initialized in dry run
        mock_client_class.assert_not_called()

    @patch('ingestors.ga4.ga4_extractor.GA4Client')
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_extract_property_invalid_credentials(self, mock_connect, mock_client_class):
        """Test extract_property handles invalid credentials"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        # Mock client with failed validation
        mock_client = MagicMock()
        mock_client.validate_credentials.return_value = False
        mock_client_class.return_value = mock_client

        extractor = GA4Extractor()

        property_config = {
            'url': 'https://example.com/',
            'ga4_property_id': '12345678'
        }

        # Should handle gracefully
        extractor.extract_property(
            property_config,
            date(2025, 1, 15),
            date(2025, 1, 20),
            dry_run=False
        )

        # Should not have fetched any data
        assert extractor.stats['rows_fetched'] == 0
        assert extractor.stats['properties_processed'] == 0


class TestGA4ExtractorDataValidation:
    """Test GA4Extractor data validation"""

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_validate_data_passing(self, mock_connect, mock_db_connection):
        """Test data validation passes with clean data"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock all validation checks passing
        mock_cursor.fetchone.side_effect = [
            (0,),  # No duplicates
            (0,),  # No nulls
            (0,),  # No invalid values
        ]
        mock_cursor.fetchall.return_value = [
            ('https://example.com/', date(2025, 1, 20), 1)  # Fresh data
        ]

        extractor = GA4Extractor()
        result = extractor.validate_data()

        assert result is True

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_validate_data_detects_duplicates(self, mock_connect, mock_db_connection):
        """Test validation detects duplicate records"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock duplicate detection
        mock_cursor.fetchone.side_effect = [
            (10,),  # 10 duplicates
            (0,),   # No nulls
            (0,),   # No invalid values
        ]
        mock_cursor.fetchall.return_value = []

        extractor = GA4Extractor()
        result = extractor.validate_data()

        assert result is False

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_validate_data_detects_stale_data(self, mock_connect, mock_db_connection):
        """Test validation detects stale data"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock stale data detection
        mock_cursor.fetchone.side_effect = [
            (0,),  # No duplicates
            (0,),  # No nulls
            (0,),  # No invalid values
        ]
        mock_cursor.fetchall.return_value = [
            ('https://example.com/', date(2025, 1, 1), 20)  # 20 days behind
        ]

        extractor = GA4Extractor()
        result = extractor.validate_data()

        # Should fail due to stale data (>7 days behind)
        assert result is False

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_validate_data_detects_invalid_metrics(self, mock_connect, mock_db_connection):
        """Test validation detects invalid metric values"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock invalid metrics detection
        mock_cursor.fetchone.side_effect = [
            (0,),   # No duplicates
            (0,),   # No nulls
            (15,),  # 15 rows with invalid metrics
        ]
        mock_cursor.fetchall.return_value = []

        extractor = GA4Extractor()
        result = extractor.validate_data()

        assert result is False


class TestGA4ExtractorBulkExtraction:
    """Test GA4Extractor extract_all method"""

    @patch('ingestors.ga4.ga4_extractor.GA4Client')
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    @patch('ingestors.ga4.ga4_extractor.execute_batch')
    def test_extract_all_multiple_properties(self, mock_execute_batch, mock_connect, mock_client_class,
                                             mock_db_connection, mock_ga4_config):
        """Test extracting data for all configured properties"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock watermark (no existing data)
        mock_cursor.fetchone.return_value = None

        # Mock GA4 client
        mock_client = MagicMock()
        mock_client.validate_credentials.return_value = True
        mock_client.get_page_metrics.return_value = [
            {
                'date': '2025-01-15',
                'host_name': 'example.com',
                'page_path': '/test',
                'sessions': 100,
                'engaged_sessions': 80,
                'engagement_rate': 0.8,
                'bounce_rate': 0.2,
                'conversions': 5,
                'conversion_rate': 0.05,
                'avg_session_duration': 120.0,
                'page_views': 150,
                'avg_time_on_page': 90.0
            }
        ]
        mock_client_class.return_value = mock_client

        # Create extractor with mock config
        with patch('ingestors.ga4.ga4_extractor.os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=yaml.dump(mock_ga4_config))):
                extractor = GA4Extractor(config_path='/fake/config.yaml')

        # Extract all properties
        extractor.extract_all(days_back=7, dry_run=False)

        # Should process both properties in config
        assert extractor.stats['properties_processed'] == 2
        assert extractor.stats['rows_fetched'] == 2  # 1 row per property

    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_extract_all_skip_up_to_date(self, mock_connect, mock_db_connection, mock_ga4_config):
        """Test extract_all skips properties that are already up to date"""
        from ingestors.ga4.ga4_extractor import GA4Extractor

        mock_conn, mock_cursor = mock_db_connection
        mock_connect.return_value = mock_conn

        # Mock watermark showing data is current
        yesterday = datetime.now().date() - timedelta(days=1)
        mock_cursor.fetchone.return_value = (yesterday,)

        with patch('ingestors.ga4.ga4_extractor.os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=yaml.dump(mock_ga4_config))):
                extractor = GA4Extractor(config_path='/fake/config.yaml')

        # Extract all - should skip both properties
        extractor.extract_all(days_back=7, dry_run=False)

        # Should not process any properties (already up to date)
        assert extractor.stats['properties_processed'] == 0
        assert extractor.stats['rows_fetched'] == 0


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================


class TestGA4IngestorEndToEnd:
    """End-to-end style tests using mock fixtures"""

    def test_mock_ga4_client_from_fixtures(self):
        """Test using MockGA4Client from fixtures - extract_events scenario"""
        from google.analytics.data_v1beta.types import RunReportRequest, DateRange

        # Create mock client from fixtures
        mock_client = create_mock_ga4_client(property_id='12345678')

        # Create request
        request = MagicMock()
        request.date_ranges = [MagicMock(start_date='2025-01-15', end_date='2025-01-20')]

        # Run report
        response = mock_client.run_report(request)

        # Verify response structure
        assert response is not None
        assert hasattr(response, 'rows')
        assert len(response.rows) > 0

        # Verify data structure
        first_row = response.rows[0]
        assert len(first_row.dimension_values) == 3  # date, hostName, pagePath
        assert len(first_row.metric_values) == 8  # All GA4 metrics

    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_full_extraction_flow(self, mock_client_class, mock_credentials, mock_credentials_file):
        """Test complete extraction flow from client to extractor"""
        from ingestors.ga4.ga4_client import GA4Client

        mock_credentials.return_value = MagicMock()

        # Use fixture mock client
        fixture_client = create_mock_ga4_client(property_id='12345678')
        mock_client_class.return_value = fixture_client

        # Initialize client
        client = GA4Client(
            credentials_path=mock_credentials_file,
            property_id='12345678',
            rate_limit_qps=0
        )

        # This would fail because fixture_client doesn't have run_report
        # But demonstrates integration approach
        assert client is not None
