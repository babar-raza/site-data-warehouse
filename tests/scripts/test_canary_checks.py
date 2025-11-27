#!/usr/bin/env python3
"""
Tests for canary_checks.py script

These tests verify the script's structure, error handling, and basic functionality.
They do NOT require actual database or API connections (use mocks).
"""

import os
import sys
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts'))

from canary_checks import (
    EnvironmentConfig,
    CheckResult,
    CanaryReport,
    CanaryChecker
)


class TestEnvironmentConfig:
    """Tests for EnvironmentConfig"""

    def test_from_environment_production(self):
        """Test creating production config"""
        config = EnvironmentConfig.from_environment("production")
        assert config.name == "production"
        assert config.warehouse_dsn is not None
        assert config.api_url is not None
        assert config.insights_api_url is not None

    def test_from_environment_staging(self):
        """Test creating staging config"""
        config = EnvironmentConfig.from_environment("staging")
        assert config.name == "staging"
        assert config.warehouse_dsn is not None

    def test_from_environment_invalid(self):
        """Test invalid environment raises error"""
        with pytest.raises(ValueError, match="Unknown environment"):
            EnvironmentConfig.from_environment("invalid")

    def test_config_with_env_vars(self):
        """Test config reads from environment variables"""
        test_dsn = "postgresql://test:test@localhost:5432/test"
        with patch.dict(os.environ, {"WAREHOUSE_DSN": test_dsn}):
            config = EnvironmentConfig.from_environment("production")
            assert config.warehouse_dsn == test_dsn


class TestCheckResult:
    """Tests for CheckResult dataclass"""

    def test_check_result_creation(self):
        """Test creating a check result"""
        result = CheckResult(
            name="test_check",
            status="pass",
            duration_ms=123.45,
            message="Test passed"
        )
        assert result.name == "test_check"
        assert result.status == "pass"
        assert result.duration_ms == 123.45
        assert result.message == "Test passed"
        assert result.details is None
        assert result.error is None

    def test_check_result_with_details(self):
        """Test check result with details"""
        result = CheckResult(
            name="test_check",
            status="pass",
            duration_ms=100.0,
            message="Test passed",
            details={"key": "value"}
        )
        assert result.details == {"key": "value"}

    def test_check_result_with_error(self):
        """Test check result with error"""
        result = CheckResult(
            name="test_check",
            status="fail",
            duration_ms=50.0,
            message="Test failed",
            error="Connection refused"
        )
        assert result.status == "fail"
        assert result.error == "Connection refused"


class TestCanaryReport:
    """Tests for CanaryReport dataclass"""

    def test_canary_report_creation(self):
        """Test creating a canary report"""
        checks = [
            CheckResult("check1", "pass", 100.0, "Passed"),
            CheckResult("check2", "fail", 200.0, "Failed")
        ]

        report = CanaryReport(
            environment="production",
            timestamp="2025-11-27T10:00:00Z",
            overall_status="fail",
            total_checks=2,
            passed=1,
            failed=1,
            warned=0,
            duration_ms=300.0,
            checks=checks
        )

        assert report.environment == "production"
        assert report.total_checks == 2
        assert report.passed == 1
        assert report.failed == 1
        assert report.overall_status == "fail"

    def test_canary_report_to_dict(self):
        """Test converting report to dictionary"""
        checks = [CheckResult("check1", "pass", 100.0, "Passed")]

        report = CanaryReport(
            environment="staging",
            timestamp="2025-11-27T10:00:00Z",
            overall_status="pass",
            total_checks=1,
            passed=1,
            failed=0,
            warned=0,
            duration_ms=100.0,
            checks=checks
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert report_dict["environment"] == "staging"
        assert report_dict["overall_status"] == "pass"
        assert "summary" in report_dict
        assert "checks" in report_dict
        assert len(report_dict["checks"]) == 1

    def test_canary_report_json_serializable(self):
        """Test report can be serialized to JSON"""
        checks = [CheckResult("check1", "pass", 100.0, "Passed")]

        report = CanaryReport(
            environment="production",
            timestamp="2025-11-27T10:00:00Z",
            overall_status="pass",
            total_checks=1,
            passed=1,
            failed=0,
            warned=0,
            duration_ms=100.0,
            checks=checks
        )

        # Should not raise an exception
        json_str = json.dumps(report.to_dict())
        assert isinstance(json_str, str)
        assert "production" in json_str


class TestCanaryChecker:
    """Tests for CanaryChecker class"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing"""
        return EnvironmentConfig(
            name="test",
            warehouse_dsn="postgresql://test:test@localhost:5432/test",
            api_url="http://localhost:8000",
            insights_api_url="http://localhost:8001",
            scheduler_metrics_file="/tmp/test_metrics.json"
        )

    @pytest.fixture
    def checker(self, mock_config):
        """Create a CanaryChecker instance for testing"""
        return CanaryChecker(mock_config, verbose=False)

    def test_checker_initialization(self, checker, mock_config):
        """Test checker initializes correctly"""
        assert checker.config == mock_config
        assert checker.verbose is False
        assert checker.results == []
        assert checker.logger is not None

    def test_run_check_success(self, checker):
        """Test running a successful check"""
        def mock_check():
            return {"test": "data"}

        result = checker._run_check("test_check", mock_check)

        assert result.name == "test_check"
        assert result.status == "pass"
        assert result.duration_ms > 0
        assert result.details == {"test": "data"}

    def test_run_check_failure(self, checker):
        """Test running a failed check"""
        def mock_check():
            raise Exception("Test error")

        result = checker._run_check("test_check", mock_check)

        assert result.name == "test_check"
        assert result.status == "fail"
        assert result.error == "Test error"

    def test_run_check_with_check_result(self, checker):
        """Test running a check that returns CheckResult"""
        def mock_check():
            return CheckResult(
                name="custom_check",
                status="warn",
                duration_ms=0,
                message="Warning message"
            )

        result = checker._run_check("test_check", mock_check)

        assert result.status == "warn"
        assert result.message == "Warning message"
        assert result.duration_ms > 0  # Duration gets updated

    @patch('canary_checks.psycopg2.connect')
    def test_check_database_connectivity_success(self, mock_connect, checker):
        """Test successful database connectivity check"""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 14.5", "test_db", "test_user")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        result = checker.check_database_connectivity()

        assert result.status == "pass"
        assert "Database connection successful" in result.message
        assert result.details is not None
        assert "database" in result.details

    @patch('canary_checks.psycopg2.connect')
    def test_check_database_connectivity_failure(self, mock_connect, checker):
        """Test failed database connectivity check"""
        mock_connect.side_effect = Exception("Connection refused")

        result = checker.check_database_connectivity()

        assert result.status == "fail"
        assert "Failed to connect" in result.message
        assert result.error is not None

    @patch('canary_checks.httpx.Client')
    def test_check_insights_api_health_success(self, mock_client, checker):
        """Test successful API health check"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "database": "connected",
            "total_insights": 100
        }
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response

        result = checker.check_insights_api_health()

        assert result.status == "pass"
        assert "healthy" in result.message
        assert result.details is not None

    @patch('canary_checks.httpx.Client')
    def test_check_insights_api_health_failure(self, mock_client, checker):
        """Test failed API health check"""
        mock_client.return_value.__enter__.return_value.get.side_effect = Exception("Connection error")

        result = checker.check_insights_api_health()

        assert result.status == "fail"
        assert result.error is not None

    def test_check_scheduler_via_metrics_file(self, checker, tmp_path):
        """Test scheduler check using metrics file"""
        # Create temporary metrics file
        metrics_file = tmp_path / "scheduler_metrics.json"
        metrics = {
            "last_daily_run": (datetime.utcnow() - timedelta(hours=12)).isoformat() + "Z",
            "daily_runs_count": 10
        }
        metrics_file.write_text(json.dumps(metrics))

        checker.config.scheduler_metrics_file = str(metrics_file)

        result = checker.check_scheduler_last_run()

        assert result.status == "pass"
        assert "hours ago" in result.message

    def test_check_scheduler_old_run(self, checker, tmp_path):
        """Test scheduler check with old run"""
        # Create temporary metrics file with old timestamp
        metrics_file = tmp_path / "scheduler_metrics.json"
        metrics = {
            "last_daily_run": (datetime.utcnow() - timedelta(hours=48)).isoformat() + "Z",
            "daily_runs_count": 10
        }
        metrics_file.write_text(json.dumps(metrics))

        checker.config.scheduler_metrics_file = str(metrics_file)

        result = checker.check_scheduler_last_run()

        assert result.status == "fail"
        assert "48" in result.message

    @patch('canary_checks.psycopg2.connect')
    def test_run_all_checks(self, mock_connect, checker):
        """Test running all checks"""
        # Setup minimal mock to prevent connection errors
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock all methods to return successful results
        with patch.object(checker, 'check_database_connectivity', return_value=CheckResult("db", "pass", 10, "OK")):
            with patch.object(checker, 'check_critical_tables_exist', return_value=CheckResult("tables", "pass", 10, "OK")):
                with patch.object(checker, 'check_recent_data_ingestion', return_value=CheckResult("data", "pass", 10, "OK")):
                    with patch.object(checker, 'check_recent_insights_created', return_value=CheckResult("insights", "pass", 10, "OK")):
                        with patch.object(checker, 'check_insights_api_health', return_value=CheckResult("api", "pass", 10, "OK")):
                            with patch.object(checker, 'check_insights_api_query', return_value=CheckResult("query", "pass", 10, "OK")):
                                with patch.object(checker, 'check_scheduler_last_run', return_value=CheckResult("scheduler", "pass", 10, "OK")):
                                    with patch.object(checker, 'check_data_quality_basic', return_value=CheckResult("quality", "pass", 10, "OK")):
                                        report = checker.run_all_checks()

        assert isinstance(report, CanaryReport)
        assert report.total_checks == 8
        assert report.overall_status == "pass"
        assert len(checker.results) == 8

    @patch('canary_checks.psycopg2.connect')
    def test_run_all_checks_with_failure(self, mock_connect, checker):
        """Test running all checks with one failure"""
        # Setup minimal mock
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock with one failure
        with patch.object(checker, 'check_database_connectivity', return_value=CheckResult("db", "fail", 10, "Failed")):
            with patch.object(checker, 'check_critical_tables_exist', return_value=CheckResult("tables", "pass", 10, "OK")):
                with patch.object(checker, 'check_recent_data_ingestion', return_value=CheckResult("data", "pass", 10, "OK")):
                    with patch.object(checker, 'check_recent_insights_created', return_value=CheckResult("insights", "pass", 10, "OK")):
                        with patch.object(checker, 'check_insights_api_health', return_value=CheckResult("api", "pass", 10, "OK")):
                            with patch.object(checker, 'check_insights_api_query', return_value=CheckResult("query", "pass", 10, "OK")):
                                with patch.object(checker, 'check_scheduler_last_run', return_value=CheckResult("scheduler", "pass", 10, "OK")):
                                    with patch.object(checker, 'check_data_quality_basic', return_value=CheckResult("quality", "pass", 10, "OK")):
                                        report = checker.run_all_checks()

        assert report.overall_status == "fail"
        assert report.failed == 1
        assert report.passed == 7


class TestMainFunction:
    """Tests for main function and CLI"""

    @patch('canary_checks.CanaryChecker')
    @patch('sys.argv', ['canary_checks.py', '--environment', 'production'])
    def test_main_production(self, mock_checker_class):
        """Test main with production environment"""
        # Setup mock
        mock_checker = MagicMock()
        mock_report = CanaryReport(
            environment="production",
            timestamp="2025-11-27T10:00:00Z",
            overall_status="pass",
            total_checks=8,
            passed=8,
            failed=0,
            warned=0,
            duration_ms=1000.0,
            checks=[]
        )
        mock_checker.run_all_checks.return_value = mock_report
        mock_checker_class.return_value = mock_checker

        with pytest.raises(SystemExit) as exc_info:
            from canary_checks import main
            main()

        assert exc_info.value.code == 0

    @patch('canary_checks.CanaryChecker')
    @patch('sys.argv', ['canary_checks.py', '--environment', 'staging'])
    def test_main_staging(self, mock_checker_class):
        """Test main with staging environment"""
        mock_checker = MagicMock()
        mock_report = CanaryReport(
            environment="staging",
            timestamp="2025-11-27T10:00:00Z",
            overall_status="pass",
            total_checks=8,
            passed=8,
            failed=0,
            warned=0,
            duration_ms=1000.0,
            checks=[]
        )
        mock_checker.run_all_checks.return_value = mock_report
        mock_checker_class.return_value = mock_checker

        with pytest.raises(SystemExit) as exc_info:
            from canary_checks import main
            main()

        assert exc_info.value.code == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
