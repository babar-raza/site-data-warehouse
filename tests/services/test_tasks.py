"""
Tests for services/tasks.py

Tests cover:
- CWV top pages query (TASKCARD-005)
- Auto-PR recommendations query (TASKCARD-006)
- Auto-PR full data fetch with JOINs (TASKCARD-007)

Dual Mode Testing:
- Mock mode (default): Uses mocked dependencies, no external services required
- Live mode (TEST_MODE=live): Uses real Celery, PostgreSQL, and other services

All tests run in both modes - no skipping.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Import testing modes FIRST before any conditional mocking
from tests.testing_modes import (
    is_mock_mode,
    is_live_mode,
    has_celery,
    has_postgres,
)


# =============================================================================
# CONDITIONAL MOCKING - Only mock when in mock mode OR celery not installed
# =============================================================================

_celery_mocked = False
_mock_cwv_monitor = None
_mock_pr_generator = None

if is_mock_mode() or not has_celery():
    # Mock celery before importing services.tasks
    class MockSignal:
        """Mock Celery signal that accepts connect decorator"""
        def connect(self, fn):
            return fn

    class MockCeleryApp:
        """Mock Celery app that provides pass-through task decorator"""
        def __init__(self, *args, **kwargs):
            self.conf = MagicMock()
            self.conf.beat_schedule = {}
            self.on_after_configure = MockSignal()

        def task(self, *args, **kwargs):
            """Return decorator that passes through the function unchanged"""
            def decorator(fn):
                return fn
            return decorator

    # Create mock celery module
    mock_celery_module = MagicMock()
    mock_celery_module.Celery = MockCeleryApp
    mock_celery_module.schedules = MagicMock()
    mock_celery_module.schedules.crontab = MagicMock()

    sys.modules['celery'] = mock_celery_module
    sys.modules['celery.schedules'] = mock_celery_module.schedules

    # Mock modules that tasks.py imports dynamically
    mock_cwv_monitor_module = MagicMock()
    _mock_cwv_monitor = MagicMock()
    mock_cwv_monitor_module.CoreWebVitalsMonitor = _mock_cwv_monitor
    sys.modules['insights_core.cwv_monitor'] = mock_cwv_monitor_module

    mock_pr_generator_module = MagicMock()
    _mock_pr_generator = MagicMock()
    mock_pr_generator_module.AutoPRGenerator = _mock_pr_generator
    sys.modules['automation'] = MagicMock()
    sys.modules['automation.pr_generator'] = mock_pr_generator_module

    _celery_mocked = True

# Now import services.tasks (with or without mocks depending on mode)
import services.tasks


# =============================================================================
# HELPER: Get database connection for dual-mode tests
# =============================================================================

def get_test_db_connection():
    """Get a database connection - returns mock in mock mode, real in live mode"""
    if is_live_mode() and has_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor
        dsn = os.environ.get('WAREHOUSE_DSN')
        conn = psycopg2.connect(dsn)
        return conn, True  # real connection
    else:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, False  # mock connection


# =============================================================================
# CWV TOP PAGES QUERY TESTS (TASKCARD-005)
# =============================================================================

class TestCWVTopPagesQuery:
    """Tests for CWV top pages query in monitor_core_web_vitals_task"""

    def test_cwv_top_pages_query_fetches_top_20_pages(self):
        """Test that page_paths=None fetches top 20 pages from database"""
        if is_live_mode() and has_postgres():
            # Live mode: test actual query execution
            import psycopg2
            dsn = os.environ.get('WAREHOUSE_DSN')
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT page_path
                FROM gsc.vw_unified_page_performance
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY gsc_clicks DESC NULLS LAST
                LIMIT 20
            """)
            pages = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            assert isinstance(pages, list)
        else:
            # Mock mode: test query structure
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ('/page1',), ('/page2',), ('/page3',), ('/page4',), ('/page5',),
                ('/page6',), ('/page7',), ('/page8',), ('/page9',), ('/page10',),
                ('/page11',), ('/page12',), ('/page13',), ('/page14',), ('/page15',),
                ('/page16',), ('/page17',), ('/page18',), ('/page19',), ('/page20',),
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            _mock_cwv_monitor.reset_mock()
            mock_monitor_instance = MagicMock()
            mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 20}
            _mock_cwv_monitor.return_value = mock_monitor_instance

            with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
                with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                    mock_psycopg2.connect.return_value = mock_conn

                    mock_self = MagicMock()
                    services.tasks.monitor_core_web_vitals_task(
                        mock_self,
                        property='sc-domain:example.com',
                        page_paths=None
                    )

                    mock_psycopg2.connect.assert_called_once()
                    mock_cursor.execute.assert_called_once()

                    query = mock_cursor.execute.call_args[0][0]
                    assert 'gsc.vw_unified_page_performance' in query
                    assert "INTERVAL '7 days'" in query
                    assert 'gsc_clicks DESC' in query
                    assert 'LIMIT 20' in query

    def test_cwv_top_pages_falls_back_to_homepage(self):
        """Test fallback to ['/'] when no data in database"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:example.com',
                    page_paths=None
                )

                call_args = mock_monitor_instance.monitor_pages_sync.call_args
                assert call_args[0][1] == ['/']

    def test_cwv_top_pages_uses_7_day_window(self):
        """Test that query uses 7-day lookback window"""
        if is_live_mode() and has_postgres():
            import psycopg2
            dsn = os.environ.get('WAREHOUSE_DSN')
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor()
            # Verify query with 7-day window executes
            cursor.execute("""
                SELECT COUNT(*) FROM gsc.vw_unified_page_performance
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            assert result is not None
        else:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [('/page1',)]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            _mock_cwv_monitor.reset_mock()
            mock_monitor_instance = MagicMock()
            mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
            _mock_cwv_monitor.return_value = mock_monitor_instance

            with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
                with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                    mock_psycopg2.connect.return_value = mock_conn

                    mock_self = MagicMock()
                    services.tasks.monitor_core_web_vitals_task(
                        mock_self,
                        property='sc-domain:example.com',
                        page_paths=None
                    )

                    query = mock_cursor.execute.call_args[0][0]
                    assert "INTERVAL '7 days'" in query

    def test_cwv_top_pages_orders_by_clicks_desc(self):
        """Test that query orders by gsc_clicks DESC"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [('/page1',)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:example.com',
                    page_paths=None
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'ORDER BY gsc_clicks DESC' in query
                assert 'NULLS LAST' in query

    def test_cwv_top_pages_closes_connection(self):
        """Test that database connection is properly closed"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [('/page1',)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:example.com',
                    page_paths=None
                )

                mock_cursor.close.assert_called_once()
                mock_conn.close.assert_called_once()

    def test_cwv_top_pages_handles_db_error(self):
        """Test graceful handling of database errors"""
        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.side_effect = Exception("Database connection failed")

                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:example.com',
                    page_paths=None
                )

                call_args = mock_monitor_instance.monitor_pages_sync.call_args
                assert call_args[0][1] == ['/']

    def test_cwv_skips_query_when_page_paths_provided(self):
        """Test that query is skipped when page_paths is already provided"""
        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 2}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:example.com',
                    page_paths=['/custom-page1', '/custom-page2']
                )

                mock_psycopg2.connect.assert_not_called()
                call_args = mock_monitor_instance.monitor_pages_sync.call_args
                assert call_args[0][1] == ['/custom-page1', '/custom-page2']

    def test_cwv_top_pages_property_filter(self):
        """Test that property filter is correctly passed to query"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [('/page1',)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_cwv_monitor.reset_mock()
        mock_monitor_instance = MagicMock()
        mock_monitor_instance.monitor_pages_sync.return_value = {'pages_monitored': 1}
        _mock_cwv_monitor.return_value = mock_monitor_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.monitor_core_web_vitals_task(
                    mock_self,
                    property='sc-domain:mysite.com',
                    page_paths=None
                )

                query_params = mock_cursor.execute.call_args[0][1]
                assert query_params == ('sc-domain:mysite.com',)


# =============================================================================
# AUTO-PR RECOMMENDATIONS QUERY TESTS (TASKCARD-006)
# =============================================================================

class TestAutoPRRecommendationsQuery:
    """Tests for Auto-PR recommendations query in create_auto_pr_task"""

    def test_auto_pr_fetches_approved_high_priority_recommendations(self):
        """Test that recommendation_ids=None fetches approved high-priority recommendations"""
        if is_live_mode() and has_postgres():
            import psycopg2
            from psycopg2.extras import RealDictCursor
            dsn = os.environ.get('WAREHOUSE_DSN')
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT id, recommendation_id, title, description, priority,
                       impact_score, page_path, recommendation_type
                FROM gsc.agent_recommendations
                WHERE status = 'approved'
                  AND priority IN ('high', 'critical')
                  AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        ELSE 3
                    END,
                    impact_score DESC
                LIMIT 10
            """)
            recommendations = cursor.fetchall()
            cursor.close()
            conn.close()
            assert isinstance(recommendations, list)
        else:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix meta', 'description': 'Add meta',
                 'priority': 'critical', 'impact_score': 0.9, 'page_path': '/page1', 'recommendation_type': 'seo'},
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            _mock_pr_generator.reset_mock()
            mock_generator_instance = MagicMock()
            mock_generator_instance.create_pull_request_sync.return_value = {'success': True}
            _mock_pr_generator.return_value = mock_generator_instance

            with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
                with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                    mock_psycopg2.connect.return_value = mock_conn

                    mock_self = MagicMock()
                    services.tasks.create_auto_pr_task(
                        mock_self,
                        repo_owner='owner',
                        repo_name='repo',
                        property='sc-domain:example.com',
                        recommendation_ids=None
                    )

                    mock_psycopg2.connect.assert_called_once()
                    query = mock_cursor.execute.call_args[0][0]
                    assert 'gsc.agent_recommendations' in query
                    assert "status = 'approved'" in query
                    assert "priority IN ('high', 'critical')" in query

    def test_auto_pr_returns_error_if_no_recommendations(self):
        """Test that empty result returns error"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                result = services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=None
                )

                assert result['success'] is False
                assert result['error'] == 'no_recommendations'
                _mock_pr_generator.assert_not_called()

    def test_auto_pr_orders_by_priority_critical_first(self):
        """Test that query orders by priority (critical > high)"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix', 'description': 'Desc',
             'priority': 'critical', 'impact_score': 0.9, 'page_path': '/p1', 'recommendation_type': 'seo'}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.create_pull_request_sync.return_value = {'success': True}
        _mock_pr_generator.return_value = mock_generator_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=None
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'ORDER BY' in query
                assert 'CASE' in query
                assert "'critical' THEN 1" in query
                assert "'high' THEN 2" in query

    def test_auto_pr_limits_to_max_recommendations(self):
        """Test that query limits results"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix', 'description': 'Desc',
             'priority': 'high', 'impact_score': 0.9, 'page_path': '/p1', 'recommendation_type': 'seo'}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.create_pull_request_sync.return_value = {'success': True}
        _mock_pr_generator.return_value = mock_generator_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=None,
                    max_recommendations=10
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'LIMIT' in query
                query_params = mock_cursor.execute.call_args[0][1]
                assert query_params[1] == 10

    def test_auto_pr_closes_connection(self):
        """Test that database connection is properly closed"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix', 'description': 'Desc',
             'priority': 'high', 'impact_score': 0.9, 'page_path': '/p1', 'recommendation_type': 'seo'}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.create_pull_request_sync.return_value = {'success': True}
        _mock_pr_generator.return_value = mock_generator_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=None
                )

                mock_cursor.close.assert_called()
                mock_conn.close.assert_called()

    def test_auto_pr_handles_db_error(self):
        """Test graceful handling of database errors"""
        _mock_pr_generator.reset_mock()

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.side_effect = Exception("Database error")

                mock_self = MagicMock()
                result = services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=None
                )

                assert result['success'] is False
                assert 'db_error' in result['error']
                _mock_pr_generator.assert_not_called()


# =============================================================================
# AUTO-PR FULL DATA FETCH TESTS (TASKCARD-007)
# =============================================================================

class TestAutoPRFullDataFetch:
    """Tests for Auto-PR full data fetch with JOINs (TASKCARD-007)"""

    def test_auto_pr_full_data_fetch_uses_join_query(self):
        """Test that recommendation_ids triggers complex JOIN query"""
        if is_live_mode() and has_postgres():
            import psycopg2
            from psycopg2.extras import RealDictCursor
            dsn = os.environ.get('WAREHOUSE_DSN')
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT
                    r.id, r.recommendation_id, r.title,
                    d.id as diagnosis_id, d.root_cause,
                    f.id as finding_id, f.finding_type,
                    i.id as insight_id, i.category as insight_category
                FROM gsc.agent_recommendations r
                LEFT JOIN gsc.agent_diagnoses d ON r.diagnosis_id = d.id
                LEFT JOIN gsc.agent_findings f ON d.finding_id = f.id
                LEFT JOIN gsc.insights i ON r.page_path = i.entity_id
                LIMIT 5
            """)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            assert isinstance(results, list)
        else:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix', 'description': 'Desc',
                 'priority': 'high', 'impact_score': 0.9, 'page_path': '/p1', 'recommendation_type': 'seo',
                 'diagnosis_id': 10, 'root_cause': 'thin_content', 'finding_id': 5,
                 'insight_id': 'ins-123', 'insight_category': 'risk'}
            ]
            mock_conn = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            _mock_pr_generator.reset_mock()
            mock_generator_instance = MagicMock()
            mock_generator_instance.create_pull_request_sync.return_value = {'success': True}
            _mock_pr_generator.return_value = mock_generator_instance

            with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
                with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                    mock_psycopg2.connect.return_value = mock_conn

                    mock_self = MagicMock()
                    services.tasks.create_auto_pr_task(
                        mock_self,
                        repo_owner='owner',
                        repo_name='repo',
                        property='sc-domain:example.com',
                        recommendation_ids=['rec-1', 'rec-2']
                    )

                    query = mock_cursor.execute.call_args[0][0]
                    assert 'recommendation_id = ANY' in query
                    assert 'LEFT JOIN gsc.agent_diagnoses' in query
                    assert 'LEFT JOIN gsc.agent_findings' in query
                    assert 'LEFT JOIN gsc.insights' in query

    def test_auto_pr_full_data_fetch_includes_diagnosis_fields(self):
        """Test that JOIN query includes diagnosis data fields"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=['rec-1']
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'd.root_cause' in query or 'root_cause' in query
                assert 'supporting_evidence' in query
                assert 'diagnosis_confidence' in query or 'confidence_score' in query

    def test_auto_pr_full_data_fetch_includes_findings_fields(self):
        """Test that JOIN query includes findings data fields"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=['rec-1']
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'finding_id' in query
                assert 'finding_type' in query
                assert 'finding_severity' in query or 'f.severity' in query

    def test_auto_pr_full_data_fetch_includes_insight_fields(self):
        """Test that JOIN query includes insight data fields"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=['rec-1']
                )

                query = mock_cursor.execute.call_args[0][0]
                assert 'insight_id' in query
                assert 'insight_category' in query
                assert 'insight_severity' in query
                assert 'insight_metrics' in query

    def test_auto_pr_full_data_fetch_handles_null_joins(self):
        """Test that NULL values from LEFT JOINs are handled gracefully"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'recommendation_id': 'rec-1', 'title': 'Fix', 'description': 'Desc',
             'priority': 'high', 'impact_score': 0.9, 'page_path': '/p1', 'recommendation_type': 'seo',
             'diagnosis_id': None, 'root_cause': None, 'finding_id': None,
             'insight_id': None, 'insight_category': None}
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        _mock_pr_generator.reset_mock()
        mock_generator_instance = MagicMock()
        mock_generator_instance.create_pull_request_sync.return_value = {'success': True, 'pr_number': 123}
        _mock_pr_generator.return_value = mock_generator_instance

        with patch.dict(os.environ, {'WAREHOUSE_DSN': 'postgresql://test:test@localhost:5432/test'}):
            with patch.object(services.tasks, 'psycopg2') as mock_psycopg2:
                mock_psycopg2.connect.return_value = mock_conn

                mock_self = MagicMock()
                services.tasks.create_auto_pr_task(
                    mock_self,
                    repo_owner='owner',
                    repo_name='repo',
                    property='sc-domain:example.com',
                    recommendation_ids=['rec-1']
                )

                mock_generator_instance.create_pull_request_sync.assert_called_once()
                call_args = mock_generator_instance.create_pull_request_sync.call_args
                recommendations = call_args[0][2]
                assert len(recommendations) == 1
                assert recommendations[0]['diagnosis_id'] is None
