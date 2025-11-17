"""
Tests for GA4 Extractor
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import date, datetime, timedelta
import yaml


@pytest.fixture
def mock_ga4_config():
    """Mock GA4 configuration"""
    return {
        'properties': [
            {
                'url': 'https://example.com/',
                'ga4_property_id': '12345678'
            }
        ],
        'extraction': {
            'default_days_back': 30,
            'rate_limit_qps': 10,
            'batch_size': 1000
        },
        'validation': {
            'min_sessions_threshold': 0,
            'max_bounce_rate': 1.0
        }
    }


@pytest.fixture
def mock_ga4_response():
    """Mock GA4 API response data"""
    return [
        {
            'date': '2025-01-15',
            'page_path': '/test-page',
            'sessions': 100,
            'engaged_sessions': 80,
            'engagement_rate': 0.8,
            'bounce_rate': 0.2,
            'conversions': 5,
            'conversion_rate': 0.05,
            'avg_session_duration': 120.5,
            'page_views': 150,
            'avg_time_on_page': 90.0
        },
        {
            'date': '2025-01-16',
            'page_path': '/test-page',
            'sessions': 120,
            'engaged_sessions': 95,
            'engagement_rate': 0.79,
            'bounce_rate': 0.21,
            'conversions': 6,
            'conversion_rate': 0.05,
            'avg_session_duration': 115.0,
            'page_views': 180,
            'avg_time_on_page': 85.0
        }
    ]


class TestGA4Client:
    """Test GA4Client class"""
    
    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_client_initialization(self, mock_client_class, mock_credentials):
        """Test GA4Client initialization"""
        from ingestors.ga4.ga4_client import GA4Client
        
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        client = GA4Client(
            credentials_path='/fake/path/sa.json',
            property_id='12345678',
            rate_limit_qps=10
        )
        
        assert client.property_id == '12345678'
        assert client.rate_limit_qps == 10
        mock_credentials.assert_called_once()
    
    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    @patch('time.sleep')
    def test_rate_limiting(self, mock_sleep, mock_client_class, mock_credentials):
        """Test rate limiting functionality"""
        from ingestors.ga4.ga4_client import GA4Client
        
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        client = GA4Client(
            credentials_path='/fake/path/sa.json',
            property_id='12345678',
            rate_limit_qps=2  # 2 queries per second
        )
        
        # Make two requests quickly
        client._rate_limit()
        client._rate_limit()
        
        # Should have slept to enforce rate limit
        assert mock_sleep.called
    
    @patch('ingestors.ga4.ga4_client.service_account.Credentials.from_service_account_file')
    @patch('ingestors.ga4.ga4_client.BetaAnalyticsDataClient')
    def test_get_page_metrics(self, mock_client_class, mock_credentials, mock_ga4_response):
        """Test getting page metrics"""
        from ingestors.ga4.ga4_client import GA4Client
        
        mock_creds = MagicMock()
        mock_credentials.return_value = mock_creds
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.rows = []
        
        # Create mock rows
        for data in mock_ga4_response:
            mock_row = MagicMock()
            mock_row.dimension_values = [
                MagicMock(value=data['date']),
                MagicMock(value=data['page_path'])
            ]
            mock_row.metric_values = [
                MagicMock(value=str(data['sessions'])),
                MagicMock(value=str(data['engaged_sessions'])),
                MagicMock(value=str(data['engagement_rate'])),
                MagicMock(value=str(data['bounce_rate'])),
                MagicMock(value=str(data['conversions'])),
                MagicMock(value=str(data['page_views'])),
                MagicMock(value=str(data['avg_session_duration'])),
                MagicMock(value=str(data['avg_time_on_page'] * data['page_views']))
            ]
            mock_response.rows.append(mock_row)
        
        mock_client.run_report.return_value = mock_response
        
        client = GA4Client(
            credentials_path='/fake/path/sa.json',
            property_id='12345678'
        )
        
        # Call get_page_metrics
        result = client.get_page_metrics('2025-01-15', '2025-01-16')
        
        assert len(result) == 2
        assert result[0]['sessions'] == 100
        assert result[0]['page_path'] == '/test-page'


class TestGA4Extractor:
    """Test GA4Extractor class"""
    
    @patch('ingestors.ga4.ga4_extractor.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_config(self, mock_file, mock_exists, mock_ga4_config):
        """Test configuration loading"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = yaml.dump(mock_ga4_config)
        
        extractor = GA4Extractor(config_path='/fake/config.yaml')
        
        assert 'properties' in extractor.config
        assert len(extractor.config['properties']) > 0
    
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_get_watermark(self, mock_connect):
        """Test getting watermark"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock watermark response
        mock_cursor.fetchone.return_value = (date(2025, 1, 10),)
        
        extractor = GA4Extractor()
        watermark = extractor.get_watermark('https://example.com/')
        
        assert watermark == date(2025, 1, 10)
        mock_cursor.execute.assert_called_once()
    
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_update_watermark(self, mock_connect):
        """Test updating watermark"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        extractor = GA4Extractor()
        extractor.update_watermark('https://example.com/', date(2025, 1, 15))
        
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    @patch('ingestors.ga4.ga4_extractor.execute_batch')
    def test_upsert_data(self, mock_execute_batch, mock_connect, mock_ga4_response):
        """Test data upsert"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        extractor = GA4Extractor()
        extractor.upsert_data('https://example.com/', mock_ga4_response)
        
        mock_execute_batch.assert_called_once()
        mock_conn.commit.assert_called_once()
        assert extractor.stats['rows_inserted'] == 2
    
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_validate_data(self, mock_connect):
        """Test data validation"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock validation queries - all passing
        mock_cursor.fetchone.side_effect = [
            (0,),  # No duplicates
            (0,),  # No nulls
            (0,),  # No invalid values
        ]
        mock_cursor.fetchall.return_value = [
            ('https://example.com/', date(2025, 1, 15), 1)  # Fresh data
        ]
        
        extractor = GA4Extractor()
        result = extractor.validate_data()
        
        assert result is True
    
    @patch('ingestors.ga4.ga4_extractor.GA4Client')
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_extract_property_dry_run(self, mock_connect, mock_client_class):
        """Test property extraction in dry run mode"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        extractor = GA4Extractor()
        
        property_config = {
            'url': 'https://example.com/',
            'ga4_property_id': '12345678'
        }
        
        # Dry run should not make API calls
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
    def test_extract_property(self, mock_connect, mock_client_class, mock_ga4_response):
        """Test property extraction"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock GA4 client
        mock_client = MagicMock()
        mock_client.validate_credentials.return_value = True
        mock_client.get_page_metrics.return_value = mock_ga4_response
        mock_client_class.return_value = mock_client
        
        extractor = GA4Extractor()
        
        property_config = {
            'url': 'https://example.com/',
            'ga4_property_id': '12345678'
        }
        
        extractor.extract_property(
            property_config,
            date(2025, 1, 15),
            date(2025, 1, 16),
            dry_run=False
        )
        
        assert extractor.stats['rows_fetched'] == 2
        assert extractor.stats['properties_processed'] == 1


class TestConfigurationValidation:
    """Test configuration validation"""
    
    def test_default_config(self):
        """Test default configuration"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        extractor = GA4Extractor(config_path='/nonexistent/config.yaml')
        
        assert 'properties' in extractor.config
        assert 'extraction' in extractor.config
        assert 'validation' in extractor.config


class TestDataQuality:
    """Test data quality checks"""
    
    @patch('ingestors.ga4.ga4_extractor.psycopg2.connect')
    def test_detect_duplicates(self, mock_connect):
        """Test duplicate detection"""
        from ingestors.ga4.ga4_extractor import GA4Extractor
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock duplicate detection
        mock_cursor.fetchone.side_effect = [
            (5,),  # 5 duplicates found
            (0,),  # No nulls
            (0,),  # No invalid values
        ]
        mock_cursor.fetchall.return_value = []
        
        extractor = GA4Extractor()
        result = extractor.validate_data()
        
        # Should fail due to duplicates
        assert result is False
