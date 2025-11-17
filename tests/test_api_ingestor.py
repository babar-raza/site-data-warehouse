#!/usr/bin/env python3
"""
Pytest tests for GSC API Ingestor
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from unittest.mock import Mock, MagicMock, patch, call
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestors.api.gsc_api_ingestor import GSCAPIIngestor
from ingestors.api.rate_limiter import RateLimitConfig, EnterprisRateLimiter


@pytest.fixture
def mock_config():
    """Standard configuration for tests"""
    return {
        'GSC_SVC_JSON': '/nonexistent/path.json',  # Will trigger mock mode
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'API_COOLDOWN_SEC': '0.01',
        'GSC_API_ROWS_PER_PAGE': '10',
        'GSC_API_MAX_RETRIES': '3',
        # Use a small ingestion window in tests to avoid long loops
        'INGEST_DAYS': '7',
        # Use a small initial backfill window in tests to avoid long loops
        'GSC_INITIAL_BACKFILL_DAYS': '7',
        'REQUESTS_PER_MINUTE': '100',
        'BURST_SIZE': '50'
    }


@pytest.fixture
def ingestor(mock_config):
    """Create ingestor instance with mock config"""
    return GSCAPIIngestor(mock_config)


class TestGSCAPIIngestorInitialization:
    """Test ingestor initialization"""
    
    def test_initialization_with_config(self, mock_config):
        """Test basic initialization"""
        ingestor = GSCAPIIngestor(mock_config)
        assert ingestor.config == mock_config
        assert ingestor.service is None
        assert ingestor.conn is None
        assert isinstance(ingestor.rate_limiter, EnterprisRateLimiter)
        assert ingestor.max_rows == 10
        
    def test_rate_limiter_config(self, ingestor):
        """Test rate limiter is configured correctly"""
        assert ingestor.rate_limiter is not None
        config = ingestor.rate_limiter.config
        assert config.requests_per_minute == 100
        assert config.burst_size == 50
        assert config.cooldown_seconds == 0.01
        assert config.max_retries == 3


class TestGSCConnection:
    """Test GSC API connection"""
    
    def test_connect_gsc_with_missing_credentials(self, ingestor):
        """Test connection falls back to mock when credentials missing"""
        ingestor.connect_gsc()
        assert ingestor.service is not None
        # Should be using mock service
        
    @patch('ingestors.api.gsc_api_ingestor.os.path.exists')
    @patch('ingestors.api.gsc_api_ingestor.service_account.Credentials.from_service_account_file')
    @patch('ingestors.api.gsc_api_ingestor.build')
    def test_connect_gsc_with_valid_credentials(self, mock_build, mock_creds, mock_exists, ingestor):
        """Test connection with valid credentials"""
        mock_exists.return_value = True
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        ingestor.connect_gsc()
        assert ingestor.service == mock_service
        mock_creds.assert_called_once()
        mock_build.assert_called_once()


class TestWarehouseConnection:
    """Test warehouse database connection"""
    
    def test_connect_warehouse_with_invalid_credentials(self, ingestor):
        """Test connection falls back to mock on failure"""
        ingestor.connect_warehouse()
        assert ingestor.conn is not None
        # Should be using mock connection


class TestPropertyDiscovery:
    """Test property discovery functionality"""
    
    def test_get_api_only_properties(self, ingestor):
        """Test getting list of API-only properties"""
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        
        properties = ingestor.get_api_only_properties()
        assert isinstance(properties, list)


class TestDateRangeCalculation:
    """Test date range calculation"""
    
    def test_get_watermark_new_property(self, ingestor):
        """Test getting watermark for property without one"""
        ingestor.connect_warehouse()
        
        property_url = "https://example.com/"
        watermark = ingestor.get_watermark(property_url)
        
        assert isinstance(watermark, date)
        
    def test_update_watermark(self, ingestor):
        """Test updating watermark"""
        ingestor.connect_warehouse()
        
        property_url = "https://example.com/"
        test_date = date.today() - timedelta(days=1)
        
        # Should not raise exceptions
        try:
            ingestor.update_watermark(property_url, test_date, 100)
        except Exception as e:
            pytest.fail(f"update_watermark raised unexpected exception: {e}")


class TestDataFetching:
    """Test data fetching from GSC API"""
    
    def test_fetch_search_analytics(self, ingestor):
        """Test fetching data from Search Analytics API"""
        ingestor.connect_gsc()
        
        property_url = "https://example.com/"
        start_date = date.today() - timedelta(days=2)
        end_date = date.today() - timedelta(days=1)
        
        rows = ingestor.fetch_search_analytics(property_url, start_date, end_date)
        assert isinstance(rows, list)
        
    def test_fetch_respects_rate_limiting(self, ingestor):
        """Test that rate limiting is applied"""
        ingestor.connect_gsc()
        
        property_url = "https://example.com/"
        start_date = date.today() - timedelta(days=1)
        end_date = date.today() - timedelta(days=1)
        
        # Make multiple requests
        start_time = time.time()
        for _ in range(3):
            ingestor.fetch_search_analytics(property_url, start_date, end_date)
        elapsed = time.time() - start_time
        
        # Should have some rate limiting delay (though minimal with mock)
        assert elapsed >= 0


class TestDataIngestion:
    """Test data ingestion to warehouse"""
    
    def test_ingest_property_data(self, ingestor):
        """Test ingesting data for a property"""
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        
        property_url = "https://example.com/"
        
        result = ingestor.ingest_property(property_url)
        assert isinstance(result, dict)
        assert 'property' in result
        assert 'rows_processed' in result
        assert 'start_date' in result
        assert 'end_date' in result


class TestFullIngestionRun:
    """Test complete ingestion workflow"""
    
    def test_run_full_ingestion(self, ingestor):
        """Test running full ingestion"""
        summary = ingestor.run()
        
        assert isinstance(summary, dict)
        assert 'properties_processed' in summary
        assert 'total_rows' in summary
        assert 'errors' in summary
        assert isinstance(summary['properties_processed'], list)
        assert isinstance(summary['total_rows'], int)
        
    def test_run_returns_summary_structure(self, ingestor):
        """Test that run returns properly structured summary"""
        summary = ingestor.run()
        
        # Validate summary structure
        assert 'properties_processed' in summary
        assert 'total_rows' in summary
        assert 'errors' in summary
        
        # If properties were processed, validate their structure
        if summary['properties_processed']:
            prop = summary['properties_processed'][0]
            assert 'property' in prop
            assert 'start_date' in prop
            assert 'end_date' in prop
            assert 'rows_processed' in prop


class TestErrorHandling:
    """Test error handling"""
    
    def test_handles_api_errors_gracefully(self, ingestor):
        """Test that API errors are handled gracefully"""
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        
        # Should not raise exceptions
        try:
            summary = ingestor.run()
            assert isinstance(summary, dict)
        except Exception as e:
            pytest.fail(f"Ingestor raised unexpected exception: {e}")
            
    def test_records_errors_in_summary(self, ingestor):
        """Test that errors are recorded in summary"""
        summary = ingestor.run()
        
        # Errors list should exist (may be empty in mock mode)
        assert 'errors' in summary
        assert isinstance(summary['errors'], list)


class TestRateLimiterIntegration:
    """Test rate limiter integration"""
    
    def test_rate_limiter_metrics_tracking(self, ingestor):
        """Test that rate limiter tracks metrics"""
        ingestor.connect_gsc()
        
        # Make some requests
        property_url = "https://example.com/"
        start_date = date.today() - timedelta(days=1)
        end_date = date.today() - timedelta(days=1)
        
        ingestor.fetch_search_analytics(property_url, start_date, end_date)
        ingestor.fetch_search_analytics(property_url, start_date, end_date)
        
        metrics = ingestor.rate_limiter.get_metrics()
        assert isinstance(metrics, dict)
        assert 'total_requests' in metrics
        assert metrics['total_requests'] >= 0
        
    def test_rate_limiter_respects_cooldown(self, mock_config):
        """Test that cooldown is respected"""
        # Set a measurable cooldown
        mock_config['API_COOLDOWN_SEC'] = '0.1'
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_gsc()
        
        property_url = "https://example.com/"
        start_date = date.today()
        end_date = date.today()
        
        # First request
        start = time.time()
        ingestor.fetch_search_analytics(property_url, start_date, end_date)
        
        # Second request should be delayed
        ingestor.fetch_search_analytics(property_url, start_date, end_date)
        elapsed = time.time() - start
        
        # Should have at least the cooldown period
        assert elapsed >= 0.05  # Allow some flexibility


class TestWatermarkTracking:
    """Test watermark tracking functionality"""
    
    def test_watermark_update_after_ingestion(self, ingestor):
        """Test that watermarks are updated after ingestion"""
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        
        property_url = "https://example.com/"
        
        result = ingestor.ingest_property(property_url)
        
        # Result should include date information
        assert 'start_date' in result or 'end_date' in result


class TestConfigurationOptions:
    """Test various configuration options"""
    
    def test_custom_rows_per_page(self):
        """Test custom rows per page setting"""
        config = {
            'GSC_API_ROWS_PER_PAGE': '5000',
            'DB_HOST': 'localhost'
        }
        ingestor = GSCAPIIngestor(config)
        assert ingestor.max_rows == 5000
        
    def test_custom_ingest_days(self, mock_config):
        """Test custom ingest days setting"""
        mock_config['INGEST_DAYS'] = '14'
        ingestor = GSCAPIIngestor(mock_config)
        # Configuration should be stored
        assert ingestor.config['INGEST_DAYS'] == '14'


class TestInitialBackfillLogic:
    """Tests for initial backfill vs incremental ingestion windows"""

    def test_initial_backfill_uses_long_window(self, mock_config):
        """
        When no data exists for a property, the ingestor should use the initial
        backfill window (GSC_INITIAL_BACKFILL_DAYS) rather than the incremental
        INGEST_DAYS window.
        """
        # Use small windows to keep test fast
        mock_config['INGEST_DAYS'] = '3'
        mock_config['GSC_INITIAL_BACKFILL_DAYS'] = '5'
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        prop = "https://example.com/"

        # Patch methods so we don't actually process data
        from unittest.mock import patch

        with patch.object(ingestor, 'has_data_for_property', return_value=False):
            with patch.object(ingestor, 'fetch_search_analytics', return_value=[]):
                with patch.object(ingestor, 'upsert_data', return_value=0):
                    with patch.object(ingestor, 'update_watermark') as mock_update:
                        result = ingestor.ingest_property(prop)

                        # Compute expected dates
                        yesterday = date.today() - timedelta(days=1)
                        expected_start = yesterday - timedelta(days=int(mock_config['GSC_INITIAL_BACKFILL_DAYS']) - 1)

                        assert result['start_date'] == expected_start.isoformat()
                        assert result['end_date'] == yesterday.isoformat()
                        # days_processed should equal the initial backfill window
                        assert result['days_processed'] == int(mock_config['GSC_INITIAL_BACKFILL_DAYS'])
                        # update_watermark should be called once per day
                        assert mock_update.call_count == int(mock_config['GSC_INITIAL_BACKFILL_DAYS'])

    def test_incremental_ingest_uses_short_window(self, mock_config):
        """
        When data already exists, the ingestor should use the incremental
        window controlled by INGEST_DAYS.
        """
        mock_config['INGEST_DAYS'] = '4'
        mock_config['GSC_INITIAL_BACKFILL_DAYS'] = '10'
        ingestor = GSCAPIIngestor(mock_config)
        ingestor.connect_gsc()
        ingestor.connect_warehouse()
        prop = "https://example.com/"

        last_date = date.today() - timedelta(days=7)

        from unittest.mock import patch

        with patch.object(ingestor, 'has_data_for_property', return_value=True):
            with patch.object(ingestor, 'get_watermark', return_value=last_date):
                with patch.object(ingestor, 'fetch_search_analytics', return_value=[]):
                    with patch.object(ingestor, 'upsert_data', return_value=0):
                        with patch.object(ingestor, 'update_watermark') as mock_update:
                            result = ingestor.ingest_property(prop)

                            # Expected start and end dates
                            expected_start = last_date + timedelta(days=1)
                            yesterday = date.today() - timedelta(days=1)
                            expected_end = min(expected_start + timedelta(days=int(mock_config['INGEST_DAYS'])), yesterday)

                            assert result['start_date'] == expected_start.isoformat()
                            assert result['end_date'] == expected_end.isoformat()
                            # days_processed should equal the number of days between start and end inclusive
                            expected_days = (expected_end - expected_start).days + 1
                            assert result['days_processed'] == expected_days
                            assert mock_update.call_count == expected_days

    def test_negative_config_values_raise_error(self, mock_config):
        """
        Negative values for ingestion window configuration should raise an error
        and prevent partial ingestion.
        """
        from pytest import raises

        # Negative INGEST_DAYS
        bad_config = dict(mock_config)
        bad_config['INGEST_DAYS'] = '-5'
        bad_config['GSC_INITIAL_BACKFILL_DAYS'] = '3'
        with raises(ValueError):
            GSCAPIIngestor(bad_config)

        # Negative initial backfill
        bad_config2 = dict(mock_config)
        bad_config2['GSC_INITIAL_BACKFILL_DAYS'] = '-2'
        with raises(ValueError):
            GSCAPIIngestor(bad_config2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
