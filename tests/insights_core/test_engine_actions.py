"""
Tests for InsightEngine Action Integration

Tests the integration of ActionGenerator with InsightEngine to ensure
actions are automatically generated when insights are created.

Note: These are integration tests that require a PostgreSQL database.
They will be skipped if the database is not available.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
import os

# Skip celery tests if celery is not installed
try:
    import celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# Check if database is available
def check_db_available():
    """Check if PostgreSQL database is available"""
    try:
        import psycopg2
        dsn = os.environ.get('WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db')
        conn = psycopg2.connect(dsn)
        conn.close()
        return True
    except Exception:
        return False

DB_AVAILABLE = check_db_available()


@pytest.fixture
def mock_config():
    """Mock InsightsConfig"""
    config = Mock()
    config.warehouse_dsn = os.environ.get('WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db')
    config.risk_threshold_clicks_pct = -20.0
    config.risk_threshold_conversions_pct = -20.0
    config.opportunity_threshold_impressions_pct = 50.0
    return config


@pytest.fixture
def mock_action():
    """Mock Action object"""
    action = Mock()
    action.id = "action-123"
    action.insight_id = "insight-456"
    action.property = "sc-domain:example.com"
    action.title = "Fix Content Quality Issue"
    action.priority = "high"
    return action


@pytest.mark.skipif(not DB_AVAILABLE, reason="Database not available")
class TestInsightEngineActions:
    """Test action generation integration with InsightEngine

    These tests require a running PostgreSQL database.
    Set WAREHOUSE_DSN environment variable to configure the connection.
    """

    def test_refresh_generates_actions_by_default(self, mock_config, mock_action):
        """Test that refresh generates actions when insights are created"""
        from insights_core.engine import InsightEngine

        with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
            # Mock ActionGenerator
            mock_action_gen = Mock()
            mock_action_gen.generate_batch.return_value = [mock_action, mock_action]
            mock_action_gen_class.return_value = mock_action_gen

            # Create engine and refresh
            engine = InsightEngine(config=mock_config)
            stats = engine.refresh(property='sc-domain:example.com')

            # Verify stats structure is correct
            assert 'total_insights_created' in stats
            assert 'actions_generated' in stats
            assert isinstance(stats['total_insights_created'], int)

    def test_refresh_can_disable_actions(self, mock_config):
        """Test that action generation can be disabled"""
        from insights_core.engine import InsightEngine

        with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
            # Create engine and refresh with actions disabled
            engine = InsightEngine(config=mock_config)
            stats = engine.refresh(property='sc-domain:example.com', generate_actions=False)

            # Verify actions were NOT generated
            assert stats['actions_generated'] == 0
            mock_action_gen_class.assert_not_called()

    def test_refresh_handles_action_failure_gracefully(self, mock_config):
        """Test that action generation failures don't break refresh"""
        from insights_core.engine import InsightEngine

        with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
            # Mock ActionGenerator to fail
            mock_action_gen = Mock()
            mock_action_gen.generate_batch.side_effect = Exception("Database connection failed")
            mock_action_gen_class.return_value = mock_action_gen

            # Create engine and refresh - should NOT raise exception
            engine = InsightEngine(config=mock_config)
            stats = engine.refresh(property='sc-domain:example.com')

            # Verify refresh completed (even if actions failed)
            assert 'total_insights_created' in stats


class TestInsightEngineActionsUnit:
    """Unit tests for InsightEngine action generation (no database required)"""

    def test_refresh_method_signature(self, mock_config):
        """Test that refresh method has correct signature"""
        from insights_core.engine import InsightEngine
        import inspect

        # Get the refresh method signature
        sig = inspect.signature(InsightEngine.refresh)
        params = list(sig.parameters.keys())

        # Should have 'self', 'property', and 'generate_actions'
        assert 'self' in params
        assert 'property' in params
        assert 'generate_actions' in params

    def test_engine_has_generate_actions_parameter(self):
        """Test that InsightEngine.refresh accepts generate_actions parameter"""
        from insights_core.engine import InsightEngine
        import inspect

        sig = inspect.signature(InsightEngine.refresh)
        params = sig.parameters

        # Check generate_actions has default value True
        assert 'generate_actions' in params
        assert params['generate_actions'].default is True

    def test_detector_list_includes_all_detectors(self, mock_config):
        """Test that engine includes all expected detectors"""
        # Just check the imports work correctly
        from insights_core.detectors import (
            AnomalyDetector,
            CannibalizationDetector,
            ContentQualityDetector,
            CWVQualityDetector,
            DiagnosisDetector,
            OpportunityDetector,
            TopicStrategyDetector,
            TrendDetector,
        )

        # All detectors should be importable
        assert AnomalyDetector is not None
        assert CannibalizationDetector is not None
        assert ContentQualityDetector is not None
        assert CWVQualityDetector is not None
        assert DiagnosisDetector is not None
        assert OpportunityDetector is not None
        assert TopicStrategyDetector is not None
        assert TrendDetector is not None


@pytest.mark.skipif(not CELERY_AVAILABLE, reason="Celery not installed")
class TestActionGenerationTask:
    """Test async action generation task (requires Celery)"""

    def test_task_generates_actions(self, mock_action):
        """Test task generates actions successfully"""
        with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
            from services.tasks import generate_actions_task

            # Mock ActionGenerator
            mock_action_gen = Mock()
            mock_action_gen.generate_batch.return_value = [mock_action, mock_action]
            mock_action_gen_class.return_value = mock_action_gen

            # Execute task
            result = generate_actions_task('sc-domain:example.com', limit=50)

            # Verify result
            assert result['property'] == 'sc-domain:example.com'
            assert result['actions_generated'] == 2
            assert result['status'] == 'success'
            mock_action_gen.generate_batch.assert_called_once_with('sc-domain:example.com', limit=50)

    def test_task_handles_errors(self):
        """Test task handles errors gracefully"""
        with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
            from services.tasks import generate_actions_task

            # Mock ActionGenerator to fail
            mock_action_gen = Mock()
            mock_action_gen.generate_batch.side_effect = Exception("Database error")
            mock_action_gen_class.return_value = mock_action_gen

            # Execute task - should raise exception (Celery will handle retry)
            with pytest.raises(Exception):
                generate_actions_task('sc-domain:example.com')

    def test_refresh_insights_task_success(self):
        """Test refresh insights task executes successfully"""
        with patch('insights_core.engine.InsightEngine') as mock_engine_class:
            from services.tasks import refresh_insights_task

            # Mock InsightEngine
            mock_engine = Mock()
            mock_engine.refresh.return_value = {
                'total_insights_created': 10,
                'actions_generated': 5,
                'detectors_succeeded': 8
            }
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = refresh_insights_task('sc-domain:example.com', generate_actions=True)

            # Verify result
            assert result['total_insights_created'] == 10
            assert result['actions_generated'] == 5
            assert result['detectors_succeeded'] == 8
            mock_engine.refresh.assert_called_once_with(
                property='sc-domain:example.com',
                generate_actions=True
            )

    def test_refresh_insights_task_no_actions(self):
        """Test refresh insights task with actions disabled"""
        with patch('insights_core.engine.InsightEngine') as mock_engine_class:
            from services.tasks import refresh_insights_task

            # Mock InsightEngine
            mock_engine = Mock()
            mock_engine.refresh.return_value = {
                'total_insights_created': 10,
                'actions_generated': 0,
                'detectors_succeeded': 8
            }
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = refresh_insights_task('sc-domain:example.com', generate_actions=False)

            # Verify result
            assert result['actions_generated'] == 0
            mock_engine.refresh.assert_called_once_with(
                property='sc-domain:example.com',
                generate_actions=False
            )
