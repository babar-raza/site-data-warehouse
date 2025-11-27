"""
Tests for scheduler.py - Content Analysis Integration

Tests verify:
- Content analysis function exists and is callable
- Content analysis is added to weekly maintenance
- Error handling works correctly
- Database queries are correct
- Integration with ContentAnalyzer
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
from datetime import datetime

# Add scheduler to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from scheduler import scheduler


class TestContentAnalysisFunction:
    """Test run_content_analysis() function"""

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_content_analysis_exists(self, mock_metrics, mock_db):
        """Test that run_content_analysis function exists"""
        assert hasattr(scheduler, 'run_content_analysis')
        assert callable(scheduler.run_content_analysis)

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_content_analysis_handles_no_pages(self, mock_metrics, mock_db):
        """Test content analysis when no pages need analysis"""
        # Mock database connection
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Run content analysis
        result = scheduler.run_content_analysis()

        # Verify it succeeded (no pages is not an error)
        assert result is True
        mock_metrics.assert_called()

        # Verify metrics show 0 pages analyzed
        call_args = mock_metrics.call_args_list[-1]
        assert call_args[0][0] == 'content_analysis'
        assert call_args[0][1] == 'success'
        assert call_args[1]['extra']['pages_analyzed'] == 0

    @patch('scheduler.scheduler.ContentAnalyzer')
    @patch('scheduler.scheduler.httpx')
    @patch('scheduler.scheduler.asyncio')
    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    @patch('scheduler.scheduler.time.sleep')
    def test_content_analysis_processes_pages(
        self, mock_sleep, mock_metrics, mock_db, mock_asyncio, mock_httpx, mock_analyzer_class
    ):
        """Test content analysis processes pages successfully"""
        # Mock database returning pages to analyze
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'page_path': '/page1',
                'total_clicks': 100,
                'last_analyzed': datetime(2020, 1, 1)
            },
            {
                'property': 'https://example.com',
                'page_path': '/page2',
                'total_clicks': 50,
                'last_analyzed': datetime(2020, 1, 1)
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Mock ContentAnalyzer
        mock_analyzer = MagicMock()
        mock_analyzer.analyze = Mock(return_value={'success': True})
        mock_analyzer.close = Mock()
        mock_analyzer_class.return_value = mock_analyzer

        # Mock asyncio.run to execute the coroutines
        def run_side_effect(coro):
            if hasattr(coro, '__name__') and 'close' in str(coro):
                return None
            return {'success': True}

        mock_asyncio.run.side_effect = run_side_effect

        # Run content analysis
        result = scheduler.run_content_analysis()

        # Verify success
        assert result is True

        # Verify metrics show 2 pages analyzed
        call_args = mock_metrics.call_args_list[-1]
        assert call_args[0][0] == 'content_analysis'
        assert call_args[0][1] == 'success'
        assert call_args[1]['extra']['pages_analyzed'] == 2
        assert call_args[1]['extra']['pages_failed'] == 0

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_content_analysis_handles_import_error(self, mock_metrics, mock_db):
        """Test content analysis handles ContentAnalyzer import error"""
        # Mock database returning pages
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'page_path': '/page1',
                'total_clicks': 100,
                'last_analyzed': datetime(2020, 1, 1)
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Mock ImportError for ContentAnalyzer
        with patch('scheduler.scheduler.ContentAnalyzer', side_effect=ImportError("Module not found")):
            result = scheduler.run_content_analysis()

        # Verify it fails gracefully
        assert result is False

        # Verify failure was logged
        call_args = mock_metrics.call_args_list[-1]
        assert call_args[0][0] == 'content_analysis'
        assert call_args[0][1] == 'failed'

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_content_analysis_handles_database_error(self, mock_metrics, mock_db):
        """Test content analysis handles database connection error"""
        # Mock database connection error
        mock_db.side_effect = Exception("Database connection failed")

        # Run content analysis
        result = scheduler.run_content_analysis()

        # Verify it fails gracefully
        assert result is False

        # Verify failure was logged
        call_args = mock_metrics.call_args_list[-1]
        assert call_args[0][0] == 'content_analysis'
        assert call_args[0][1] == 'failed'


class TestWeeklyMaintenanceIntegration:
    """Test content analysis integration with weekly maintenance"""

    def test_weekly_maintenance_includes_content_analysis(self):
        """Test that weekly_maintenance includes content analysis task"""
        # Get the weekly_maintenance function source
        import inspect
        source = inspect.getsource(scheduler.weekly_maintenance)

        # Verify content analysis is in the tasks
        assert 'Content Analysis' in source
        assert 'run_content_analysis' in source

    @patch('scheduler.scheduler.reconcile_recent_data')
    @patch('scheduler.scheduler.run_transforms')
    @patch('scheduler.scheduler.refresh_cannibalization_analysis')
    @patch('scheduler.scheduler.run_content_analysis')
    @patch('scheduler.scheduler.time.sleep')
    def test_weekly_maintenance_runs_content_analysis(
        self, mock_sleep, mock_content, mock_cann, mock_trans, mock_reconcile
    ):
        """Test that weekly maintenance actually calls content analysis"""
        # Mock all tasks to succeed
        mock_reconcile.return_value = True
        mock_trans.return_value = True
        mock_cann.return_value = True
        mock_content.return_value = True

        # Run weekly maintenance
        scheduler.weekly_maintenance()

        # Verify content analysis was called
        mock_content.assert_called_once()

    @patch('scheduler.scheduler.reconcile_recent_data')
    @patch('scheduler.scheduler.run_transforms')
    @patch('scheduler.scheduler.refresh_cannibalization_analysis')
    @patch('scheduler.scheduler.run_content_analysis')
    @patch('scheduler.scheduler.time.sleep')
    def test_weekly_maintenance_continues_if_content_analysis_fails(
        self, mock_sleep, mock_content, mock_cann, mock_trans, mock_reconcile
    ):
        """Test that weekly maintenance continues even if content analysis fails"""
        # Mock all tasks except content analysis to succeed
        mock_reconcile.return_value = True
        mock_trans.return_value = True
        mock_cann.return_value = True
        mock_content.return_value = False  # Content analysis fails

        # Run weekly maintenance (should not raise exception)
        scheduler.weekly_maintenance()

        # Verify all tasks were called despite content analysis failure
        mock_reconcile.assert_called_once()
        mock_trans.assert_called_once()
        mock_cann.assert_called_once()
        mock_content.assert_called_once()


class TestSchedulerCLI:
    """Test scheduler CLI integration"""

    def test_test_content_flag_exists(self):
        """Test that --test-content flag exists"""
        import inspect
        source = inspect.getsource(scheduler.main)

        # Verify --test-content flag is in main()
        assert '--test-content' in source
        assert 'test_content' in source

    def test_dry_run_flag_exists(self):
        """Test that --dry-run flag exists"""
        import inspect
        source = inspect.getsource(scheduler.main)

        # Verify --dry-run flag is in main()
        assert '--dry-run' in source
        assert 'dry_run' in source

    @patch('scheduler.scheduler.run_content_analysis')
    @patch('scheduler.scheduler.sys.exit')
    def test_test_content_mode(self, mock_exit, mock_content):
        """Test --test-content mode runs content analysis"""
        # Mock content analysis
        mock_content.return_value = True

        # Mock sys.argv
        with patch('sys.argv', ['scheduler.py', '--test-content']):
            try:
                scheduler.main()
            except SystemExit:
                pass

        # Verify content analysis was called
        mock_content.assert_called_once()
        mock_exit.assert_called_with(0)


class TestContentAnalysisQuery:
    """Test the SQL query used by content analysis"""

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_query_selects_top_pages(self, mock_metrics, mock_db):
        """Test that query selects top pages by clicks"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Run content analysis
        scheduler.run_content_analysis()

        # Get the SQL query that was executed
        query_call = mock_cursor.execute.call_args[0][0]

        # Verify query structure
        assert 'vw_unified_page_performance' in query_call
        assert 'gsc_clicks' in query_call
        assert 'ORDER BY' in query_call
        assert 'LIMIT' in query_call

    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    def test_query_filters_by_last_analyzed(self, mock_metrics, mock_db):
        """Test that query filters pages by last analysis date"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Run content analysis
        scheduler.run_content_analysis()

        # Get the SQL query that was executed
        query_call = mock_cursor.execute.call_args[0][0]

        # Verify query checks for stale snapshots
        assert 'content.page_snapshots' in query_call
        assert 'snapshot_date' in query_call
        assert "INTERVAL '7 days'" in query_call


class TestErrorHandling:
    """Test error handling in content analysis"""

    @patch('scheduler.scheduler.ContentAnalyzer')
    @patch('scheduler.scheduler.httpx')
    @patch('scheduler.scheduler.asyncio')
    @patch('scheduler.scheduler.get_db_connection')
    @patch('scheduler.scheduler.update_metrics')
    @patch('scheduler.scheduler.time.sleep')
    def test_handles_page_analysis_error(
        self, mock_sleep, mock_metrics, mock_db, mock_asyncio, mock_httpx, mock_analyzer_class
    ):
        """Test that errors analyzing individual pages don't stop the batch"""
        # Mock database returning multiple pages
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com',
                'page_path': '/page1',
                'total_clicks': 100,
                'last_analyzed': datetime(2020, 1, 1)
            },
            {
                'property': 'https://example.com',
                'page_path': '/page2',
                'total_clicks': 50,
                'last_analyzed': datetime(2020, 1, 1)
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_db.return_value = mock_conn

        # Mock analyzer with first page failing, second succeeding
        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        call_count = [0]

        def run_side_effect(coro):
            if hasattr(coro, '__name__') and 'close' in str(coro):
                return None
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Analysis failed for page1")
            return {'success': True}

        mock_asyncio.run.side_effect = run_side_effect

        # Run content analysis
        result = scheduler.run_content_analysis()

        # Verify it succeeded overall
        assert result is True

        # Verify metrics show 1 success, 1 failure
        call_args = mock_metrics.call_args_list[-1]
        assert call_args[1]['extra']['pages_analyzed'] == 1
        assert call_args[1]['extra']['pages_failed'] == 1
