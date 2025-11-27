"""
Tests for Pipeline Verification Script

These tests verify the verify_pipeline.py script functionality.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts'))

from verify_pipeline import PipelineVerifier, format_human_readable


class TestPipelineVerifier:
    """Tests for PipelineVerifier class"""

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        return conn, cursor

    def test_init(self):
        """Test verifier initialization"""
        verifier = PipelineVerifier('postgresql://test', 'production')
        assert verifier.warehouse_dsn == 'postgresql://test'
        assert verifier.environment == 'production'
        assert verifier.checks == []
        assert verifier.issues == []

    def test_add_check_pass(self):
        """Test adding a passing check"""
        verifier = PipelineVerifier('postgresql://test')
        verifier._add_check(
            'Test Check',
            'pass',
            'Everything is fine',
            {'detail': 'value'}
        )

        assert len(verifier.checks) == 1
        assert verifier.checks[0]['name'] == 'Test Check'
        assert verifier.checks[0]['status'] == 'pass'
        assert verifier.checks[0]['message'] == 'Everything is fine'
        assert verifier.checks[0]['details']['detail'] == 'value'
        assert len(verifier.issues) == 0

    def test_add_check_fail(self):
        """Test adding a failing check"""
        verifier = PipelineVerifier('postgresql://test')
        verifier._add_check(
            'Test Check',
            'fail',
            'Something is broken'
        )

        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'fail'
        assert len(verifier.issues) == 1
        assert verifier.issues[0]['severity'] == 'fail'

    def test_add_check_warn(self):
        """Test adding a warning check"""
        verifier = PipelineVerifier('postgresql://test')
        verifier._add_check(
            'Test Check',
            'warn',
            'Something is concerning'
        )

        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'warn'
        assert len(verifier.issues) == 1
        assert verifier.issues[0]['severity'] == 'warn'

    @patch('verify_pipeline.psycopg2.connect')
    def test_check_database_connection_success(self, mock_connect):
        """Test successful database connection check"""
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ['PostgreSQL 15.0']
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Run test
        verifier = PipelineVerifier('postgresql://test')
        result = verifier.check_database_connection()

        assert result is True
        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'pass'
        assert 'Database is accessible' in verifier.checks[0]['message']

    @patch('verify_pipeline.psycopg2.connect')
    def test_check_database_connection_failure(self, mock_connect):
        """Test failed database connection check"""
        # Setup mock to raise exception
        mock_connect.side_effect = Exception('Connection refused')

        # Run test
        verifier = PipelineVerifier('postgresql://test')
        result = verifier.check_database_connection()

        assert result is False
        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'fail'
        assert 'Cannot connect' in verifier.checks[0]['message']

    @patch('verify_pipeline.psycopg2.connect')
    def test_check_ingestion_watermarks_healthy(self, mock_connect):
        """Test healthy watermark check"""
        # Setup mock with fresh watermarks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        recent_time = datetime.utcnow() - timedelta(hours=2)
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'source_type': 'api',
                'last_date': datetime.utcnow().date(),
                'last_run_at': recent_time,
                'last_run_status': 'success',
                'error_message': None,
                'hours_since_run': 2.0,
                'days_behind': 0
            }
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Run test
        verifier = PipelineVerifier('postgresql://test')
        result = verifier.check_ingestion_watermarks(threshold_hours=36)

        assert result is True
        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'pass'

    @patch('verify_pipeline.psycopg2.connect')
    def test_check_ingestion_watermarks_stale(self, mock_connect):
        """Test stale watermark detection"""
        # Setup mock with stale watermarks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        old_time = datetime.utcnow() - timedelta(hours=48)
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'source_type': 'api',
                'last_date': datetime.utcnow().date() - timedelta(days=2),
                'last_run_at': old_time,
                'last_run_status': 'success',
                'error_message': None,
                'hours_since_run': 48.0,
                'days_behind': 2
            }
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Run test
        verifier = PipelineVerifier('postgresql://test')
        result = verifier.check_ingestion_watermarks(threshold_hours=36)

        assert result is False
        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] in ['warn', 'fail']

    @patch('verify_pipeline.psycopg2.connect')
    def test_check_ingestion_watermarks_failed(self, mock_connect):
        """Test failed watermark detection"""
        # Setup mock with failed watermarks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        recent_time = datetime.utcnow() - timedelta(hours=2)
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'source_type': 'api',
                'last_date': datetime.utcnow().date(),
                'last_run_at': recent_time,
                'last_run_status': 'failed',
                'error_message': 'API timeout',
                'hours_since_run': 2.0,
                'days_behind': 0
            }
        ]

        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Run test
        verifier = PipelineVerifier('postgresql://test')
        result = verifier.check_ingestion_watermarks(threshold_hours=36)

        assert result is False
        assert len(verifier.checks) == 1
        assert verifier.checks[0]['status'] == 'fail'

    def test_format_human_readable(self):
        """Test human-readable report formatting"""
        report = {
            'timestamp': '2025-01-01T12:00:00',
            'environment': 'production',
            'duration_seconds': 2.5,
            'overall_status': 'healthy',
            'summary': {
                'total_checks': 5,
                'passed': 5,
                'warned': 0,
                'failed': 0
            },
            'checks': [
                {
                    'name': 'Database Connection',
                    'status': 'pass',
                    'message': 'Database is accessible',
                    'timestamp': '2025-01-01T12:00:00'
                }
            ]
        }

        output = format_human_readable(report)

        assert 'PIPELINE VERIFICATION REPORT' in output
        assert 'production' in output
        assert 'Database Connection' in output
        assert 'Database is accessible' in output
        assert 'HEALTHY' in output

    def test_format_human_readable_with_issues(self):
        """Test human-readable report with issues"""
        report = {
            'timestamp': '2025-01-01T12:00:00',
            'environment': 'production',
            'duration_seconds': 2.5,
            'overall_status': 'unhealthy',
            'summary': {
                'total_checks': 2,
                'passed': 1,
                'warned': 0,
                'failed': 1
            },
            'checks': [
                {
                    'name': 'Database Connection',
                    'status': 'pass',
                    'message': 'Database is accessible',
                    'timestamp': '2025-01-01T12:00:00'
                },
                {
                    'name': 'Data Freshness',
                    'status': 'fail',
                    'message': 'Data is stale',
                    'timestamp': '2025-01-01T12:00:01'
                }
            ],
            'issues': [
                {
                    'check': 'Data Freshness',
                    'severity': 'fail',
                    'message': 'Data is stale'
                }
            ]
        }

        output = format_human_readable(report)

        assert 'ISSUES DETECTED' in output
        assert 'Data Freshness' in output
        assert 'Data is stale' in output


class TestCLI:
    """Tests for CLI functionality"""

    @patch('verify_pipeline.PipelineVerifier')
    def test_main_json_output(self, mock_verifier_class, capsys):
        """Test JSON output format"""
        # Setup mock
        mock_verifier = MagicMock()
        mock_verifier.run_all_checks.return_value = {
            'timestamp': '2025-01-01T12:00:00',
            'environment': 'test',
            'duration_seconds': 1.0,
            'overall_status': 'healthy',
            'summary': {'total_checks': 1, 'passed': 1, 'warned': 0, 'failed': 0},
            'checks': []
        }
        mock_verifier_class.return_value = mock_verifier

        # Run test
        with patch('sys.argv', ['verify_pipeline.py', '--format', 'json']):
            with pytest.raises(SystemExit) as exc_info:
                from verify_pipeline import main
                main()

        # Verify
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert '"overall_status": "healthy"' in captured.out

    @patch('verify_pipeline.PipelineVerifier')
    def test_main_unhealthy_exit_code(self, mock_verifier_class):
        """Test exit code for unhealthy pipeline"""
        # Setup mock
        mock_verifier = MagicMock()
        mock_verifier.run_all_checks.return_value = {
            'timestamp': '2025-01-01T12:00:00',
            'environment': 'test',
            'duration_seconds': 1.0,
            'overall_status': 'unhealthy',
            'summary': {'total_checks': 1, 'passed': 0, 'warned': 0, 'failed': 1},
            'checks': []
        }
        mock_verifier_class.return_value = mock_verifier

        # Run test
        with patch('sys.argv', ['verify_pipeline.py']):
            with pytest.raises(SystemExit) as exc_info:
                from verify_pipeline import main
                main()

        # Verify
        assert exc_info.value.code == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
