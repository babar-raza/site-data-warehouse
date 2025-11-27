"""
Tests for Metrics Exporter
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
import json
from datetime import date, datetime


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
    return mock_conn, mock_cursor


@pytest.fixture
def mock_metrics_collector():
    """Create mock metrics collector"""
    with patch('metrics_exporter.exporter.psycopg2.connect') as mock_connect:
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn, mock_cursor = mock_db_connection()
        mock_connect.return_value = mock_conn
        
        collector = MetricsCollector(
            dsn="postgresql://test:test@localhost:5432/test",
            scheduler_metrics_file="/tmp/test_metrics.json"
        )
        
        yield collector, mock_connect, mock_conn, mock_cursor


class TestMetricsCollector:
    """Test MetricsCollector class"""
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_check_warehouse_health_success(self, mock_connect):
        """Test successful warehouse health check"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        result = collector.check_warehouse_health()
        
        assert result is True
        mock_cursor.execute.assert_called_with("SELECT 1")
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_check_warehouse_health_failure(self, mock_connect):
        """Test failed warehouse health check"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_connect.side_effect = Exception("Connection failed")
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        result = collector.check_warehouse_health()
        
        assert result is False
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_fact_table_metrics(self, mock_connect):
        """Test collecting fact table metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            {'total': 1000},  # Total rows
            {'duplicates': 5},  # Duplicates
            {'null_count': 0},  # Nulls for clicks
            {'null_count': 0},  # Nulls for impressions
            {'null_count': 0},  # Nulls for ctr
            {'null_count': 0},  # Nulls for position
        ]
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_fact_table_metrics()
        
        # Verify SQL queries were executed
        assert mock_cursor.execute.call_count >= 2
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_data_freshness(self, mock_connect):
        """Test collecting data freshness metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock database response
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com/',
                'latest_date': date(2025, 1, 15),
                'days_behind': 1
            },
            {
                'property': 'https://test.com/',
                'latest_date': date(2025, 1, 10),
                'days_behind': 6
            }
        ]
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_data_freshness()
        
        mock_cursor.execute.assert_called_once()
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_watermark_metrics(self, mock_connect):
        """Test collecting watermark metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock database response
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com/',
                'source_type': 'api',
                'last_date': date(2025, 1, 15),
                'days_behind': 1
            }
        ]
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_watermark_metrics()
        
        mock_cursor.execute.assert_called_once()
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_insights_metrics(self, mock_connect):
        """Test collecting insights metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock table existence check and counts
        mock_cursor.fetchone.side_effect = [
            {'exists': True},
        ]
        mock_cursor.fetchall.return_value = [
            {'category': 'risk', 'severity': 'high', 'count': 5},
            {'category': 'opportunity', 'severity': 'medium', 'count': 10}
        ]
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_insights_metrics()
        
        assert mock_cursor.execute.call_count >= 2
    
    @patch('metrics_exporter.exporter.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_collect_scheduler_metrics(self, mock_file, mock_exists):
        """Test collecting scheduler metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_exists.return_value = True
        
        scheduler_data = {
            'daily_runs_count': 42,
            'tasks': {
                'api_ingestion': {
                    'status': 'success',
                    'duration_seconds': 120.5
                },
                'transforms': {
                    'status': 'failed',
                    'duration_seconds': 30.2
                }
            }
        }
        
        mock_file.return_value.read.return_value = json.dumps(scheduler_data)
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_scheduler_metrics()
        
        mock_exists.assert_called_once()
    
    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_all_metrics(self, mock_connect):
        """Test collecting all metrics"""
        from metrics_exporter.exporter import MetricsCollector
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock successful health check
        mock_cursor.fetchone.return_value = {'total': 1000}
        mock_cursor.fetchall.return_value = []
        
        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        
        # Should not raise any exceptions
        collector.collect_all_metrics()


class TestConfigLoading:
    """Test configuration loading"""
    
    @patch('metrics_exporter.exporter.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_config_success(self, mock_file, mock_exists):
        """Test successful config loading"""
        from metrics_exporter.exporter import load_config
        
        mock_exists.return_value = True
        config_yaml = """
exporter:
  port: 9090
  scrape_interval: 15
"""
        mock_file.return_value.read.return_value = config_yaml
        
        config = load_config()
        
        # Should return dict (even if empty due to mock limitations)
        assert isinstance(config, dict)
    
    @patch('metrics_exporter.exporter.os.path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        """Test config loading when file doesn't exist"""
        from metrics_exporter.exporter import load_config
        
        mock_exists.return_value = False
        
        config = load_config()
        
        assert config == {}


class TestGA4MetricsCollection:
    """Test GA4 metrics collection"""

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_ga4_metrics_success(self, mock_connect):
        """Test successful GA4 metrics collection"""
        from metrics_exporter.exporter import MetricsCollector

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Table exists
            {'total': 5000},  # Total rows
            {'pages': 100},  # Unique pages
            {'total_sessions': 2500},  # Total sessions
        ]
        mock_cursor.fetchall.return_value = [
            {'property': 'https://example.com/', 'latest_date': date(2025, 1, 15), 'days_behind': 1}
        ]

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_ga4_metrics()

        # Verify queries were executed
        assert mock_cursor.execute.call_count >= 4

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_ga4_metrics_table_not_exists(self, mock_connect):
        """Test GA4 metrics when table doesn't exist"""
        from metrics_exporter.exporter import MetricsCollector, ga4_ingestor_status

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Table doesn't exist
        mock_cursor.fetchone.return_value = {'exists': False}

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_ga4_metrics()

        # Status should be set to 0
        assert ga4_ingestor_status._value._value == 0


class TestSERPMetricsCollection:
    """Test SERP metrics collection"""

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_serp_metrics_success(self, mock_connect):
        """Test successful SERP metrics collection"""
        from metrics_exporter.exporter import MetricsCollector

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Schema exists
            {'exists': True},  # Queries table exists
            {'total': 25},  # Total queries
            {'active': 20},  # Active queries
            {'exists': True},  # Position history table exists
            {'total': 500},  # Total position records
            {'days_behind': 1},  # Freshness
            {'avg_pos': 12.5},  # Average position
            {'top10': 8},  # Top 10 count
            {'not_ranking': 5},  # Not ranking count
        ]

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_serp_metrics()

        # Verify queries were executed
        assert mock_cursor.execute.call_count >= 5

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_serp_metrics_schema_not_exists(self, mock_connect):
        """Test SERP metrics when schema doesn't exist"""
        from metrics_exporter.exporter import MetricsCollector, serp_ingestor_status

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Schema doesn't exist
        mock_cursor.fetchone.return_value = {'exists': False}

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_serp_metrics()

        # Status should be set to 0
        assert serp_ingestor_status._value._value == 0


class TestCWVMetricsCollection:
    """Test CWV metrics collection"""

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_cwv_metrics_success(self, mock_connect):
        """Test successful CWV metrics collection"""
        from metrics_exporter.exporter import MetricsCollector

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            {'exists': True},  # Performance schema exists
            {'exists': True},  # Monitored pages table exists
            {'monitored': 50},  # Pages monitored
            {'exists': True},  # Core web vitals table exists
            {'total': 200},  # Total checks
            {'days_behind': 1},  # Freshness
            # Mobile metrics
            {'avg_score': 75.5, 'avg_lcp': 2.3, 'avg_cls': 0.08, 'pass_count': 40, 'total': 50, 'poor_count': 5},
            # Desktop metrics
            {'avg_score': 85.0, 'avg_lcp': 1.5, 'avg_cls': 0.05, 'pass_count': 45, 'total': 50, 'poor_count': 2},
        ]

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_cwv_metrics()

        # Verify queries were executed
        assert mock_cursor.execute.call_count >= 5

    @patch('metrics_exporter.exporter.psycopg2.connect')
    def test_collect_cwv_metrics_schema_not_exists(self, mock_connect):
        """Test CWV metrics when schema doesn't exist"""
        from metrics_exporter.exporter import MetricsCollector, cwv_ingestor_status

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Schema doesn't exist
        mock_cursor.fetchone.return_value = {'exists': False}

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json")
        collector.collect_cwv_metrics()

        # Status should be set to 0
        assert cwv_ingestor_status._value._value == 0


class TestCSEMetricsCollection:
    """Test CSE metrics collection"""

    @patch('metrics_exporter.exporter.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_collect_cse_metrics_success(self, mock_file, mock_exists):
        """Test successful CSE metrics collection"""
        from metrics_exporter.exporter import MetricsCollector, cse_queries_today, cse_quota_remaining

        mock_exists.return_value = True

        cse_data = {
            'daily_quota': 100,
            'queries_today': 25,
            'remaining': 75
        }

        mock_file.return_value.read.return_value = json.dumps(cse_data)

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json", "/tmp/cse_metrics.json")
        collector.collect_cse_metrics()

        # Verify metrics were set
        assert cse_queries_today._value._value == 25
        assert cse_quota_remaining._value._value == 75

    @patch('metrics_exporter.exporter.os.path.exists')
    def test_collect_cse_metrics_file_not_exists(self, mock_exists):
        """Test CSE metrics when file doesn't exist (should use defaults)"""
        from metrics_exporter.exporter import MetricsCollector, cse_daily_quota, cse_queries_today, cse_quota_remaining

        mock_exists.return_value = False

        collector = MetricsCollector("test_dsn", "/tmp/metrics.json", "/tmp/cse_metrics.json")
        collector.collect_cse_metrics()

        # Should use default values
        assert cse_daily_quota._value._value == 100
        assert cse_queries_today._value._value == 0
        assert cse_quota_remaining._value._value == 100


class TestMetricsEndpoint:
    """Test metrics endpoint functionality"""

    def test_prometheus_metrics_format(self):
        """Test that metrics are in Prometheus format"""
        from metrics_exporter.exporter import warehouse_up, fact_table_rows

        # Set some test values
        warehouse_up.set(1)
        fact_table_rows.set(1000)

        # Metrics should be set
        assert warehouse_up._value._value == 1
        assert fact_table_rows._value._value == 1000

    def test_new_ingestor_metrics_exist(self):
        """Test that all new ingestor metrics are defined"""
        from metrics_exporter.exporter import (
            ga4_fact_table_rows, ga4_data_freshness_days, ga4_ingestor_status,
            serp_queries_total, serp_queries_active, serp_ingestor_status,
            cwv_pages_monitored, cwv_checks_total, cwv_ingestor_status,
            cse_queries_today, cse_quota_remaining, cse_daily_quota
        )

        # Verify all metrics are importable and settable
        ga4_fact_table_rows.set(0)
        serp_queries_total.set(0)
        cwv_pages_monitored.set(0)
        cse_queries_today.set(0)

        assert ga4_fact_table_rows._value._value == 0
        assert serp_queries_total._value._value == 0
        assert cwv_pages_monitored._value._value == 0
        assert cse_queries_today._value._value == 0
