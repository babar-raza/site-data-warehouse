#!/usr/bin/env python3
"""
Test scheduler integration with InsightEngine
Tests that insights refresh runs correctly in scheduler context
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scheduler.scheduler import (
    run_insights_refresh,
    update_metrics,
    metrics
)


@pytest.fixture
def mock_insights_config():
    """Mock InsightsConfig"""
    with patch('scheduler.scheduler.InsightsConfig') as mock:
        config = Mock()
        mock.return_value = config
        yield config


@pytest.fixture
def mock_insight_engine():
    """Mock InsightEngine"""
    with patch('scheduler.scheduler.InsightEngine') as mock:
        engine = Mock()
        mock.return_value = engine
        yield engine


def test_run_insights_refresh_success(mock_insights_config, mock_insight_engine):
    """Test insights refresh succeeds (happy path)"""
    # Mock successful refresh with stats
    mock_insight_engine.refresh.return_value = {
        'start_time': '2025-11-14T10:00:00',
        'end_time': '2025-11-14T10:00:15',
        'duration_seconds': 15.0,
        'detectors_run': 3,
        'detectors_succeeded': 3,
        'detectors_failed': 0,
        'total_insights_created': 12,
        'insights_by_detector': {
            'AnomalyDetector': 8,
            'DiagnosisDetector': 2,
            'OpportunityDetector': 2
        },
        'errors': []
    }
    
    # Run insights refresh
    result = run_insights_refresh()
    
    # Verify success
    assert result is True, "Insights refresh should succeed"
    
    # Verify engine was called
    mock_insight_engine.refresh.assert_called_once()
    
    # Verify metrics were updated
    assert 'insights_refresh' in metrics['tasks']
    task_metrics = metrics['tasks']['insights_refresh']
    assert task_metrics['status'] == 'success'
    assert task_metrics['insights_created'] == 12
    assert task_metrics['detectors_run'] == 3
    assert task_metrics['detectors_succeeded'] == 3


def test_run_insights_refresh_with_errors(mock_insights_config, mock_insight_engine):
    """Test insights refresh with partial failures"""
    # Mock refresh with some detector failures
    mock_insight_engine.refresh.return_value = {
        'start_time': '2025-11-14T10:00:00',
        'end_time': '2025-11-14T10:00:20',
        'duration_seconds': 20.0,
        'detectors_run': 3,
        'detectors_succeeded': 2,
        'detectors_failed': 1,
        'total_insights_created': 8,
        'insights_by_detector': {
            'AnomalyDetector': 8,
            'DiagnosisDetector': 0,  # Failed
            'OpportunityDetector': 0
        },
        'errors': [
            {'detector': 'DiagnosisDetector', 'error': 'Database connection timeout'}
        ]
    }
    
    # Run insights refresh
    result = run_insights_refresh()
    
    # Should still return True (partial success is acceptable)
    assert result is True
    
    # Verify metrics show the failure
    task_metrics = metrics['tasks']['insights_refresh']
    assert task_metrics['detectors_failed'] == 1
    assert task_metrics['insights_created'] == 8


def test_run_insights_refresh_complete_failure(mock_insights_config):
    """Test insights refresh fails completely (failing path)"""
    # Mock engine that raises exception
    with patch('scheduler.scheduler.InsightEngine') as mock_engine_class:
        mock_engine_class.side_effect = Exception("Database connection failed")
        
        # Run insights refresh
        result = run_insights_refresh()
        
        # Should return False
        assert result is False, "Insights refresh should fail gracefully"
        
        # Verify metrics show failure
        task_metrics = metrics['tasks']['insights_refresh']
        assert task_metrics['status'] == 'failed'
        assert 'Database connection failed' in str(task_metrics['error'])


def test_run_insights_refresh_import_error():
    """Test insights refresh handles missing insights_core package (failing path)"""
    # Mock ImportError when trying to import InsightEngine
    with patch('scheduler.scheduler.InsightEngine', side_effect=ImportError("No module named 'insights_core'")):
        # Run insights refresh
        result = run_insights_refresh()
        
        # Should return False
        assert result is False
        
        # Verify metrics show import failure
        task_metrics = metrics['tasks']['insights_refresh']
        assert task_metrics['status'] == 'failed'
        assert 'insights_core' in str(task_metrics['error']).lower()


def test_insights_refresh_non_blocking():
    """Test that insights refresh failure doesn't crash scheduler"""
    # This tests the integration pattern where insights failure is logged but not fatal
    with patch('scheduler.scheduler.run_insights_refresh', return_value=False):
        # Simulate calling insights refresh in daily_job context
        # Even if it fails, should not raise exception
        try:
            result = run_insights_refresh()
            assert result is False
            # Should reach here without exception
        except Exception as e:
            pytest.fail(f"Insights refresh should not raise exception, got: {e}")


def test_metrics_tracked_correctly(mock_insights_config, mock_insight_engine):
    """Test that all metrics are tracked correctly"""
    mock_insight_engine.refresh.return_value = {
        'start_time': '2025-11-14T10:00:00',
        'end_time': '2025-11-14T10:00:10',
        'duration_seconds': 10.0,
        'detectors_run': 3,
        'detectors_succeeded': 3,
        'detectors_failed': 0,
        'total_insights_created': 5,
        'insights_by_detector': {
            'AnomalyDetector': 3,
            'DiagnosisDetector': 1,
            'OpportunityDetector': 1
        },
        'errors': []
    }
    
    # Run insights refresh
    run_insights_refresh()
    
    # Verify all expected metrics are present
    task_metrics = metrics['tasks']['insights_refresh']
    
    required_fields = [
        'last_run',
        'status',
        'duration_seconds',
        'error',
        'insights_created',
        'detectors_run',
        'detectors_succeeded',
        'detectors_failed'
    ]
    
    for field in required_fields:
        assert field in task_metrics, f"Metric '{field}' should be tracked"


def test_insights_run_after_transforms():
    """Test that insights refresh is called AFTER transforms in daily job sequence"""
    # This is more of an integration test - verify order in scheduler.py
    # We're testing the design, not implementation here
    
    # Read scheduler.py and verify order
    scheduler_path = os.path.join(os.path.dirname(__file__), '..', 'scheduler', 'scheduler.py')
    with open(scheduler_path, 'r') as f:
        content = f.read()
    
    # Find position of run_transforms() call in daily_pipeline
    transforms_pos = content.find('run_transforms()')
    insights_pos = content.find('run_insights_refresh()')
    
    # Verify insights comes after transforms
    assert transforms_pos > 0, "run_transforms() should exist in scheduler"
    assert insights_pos > 0, "run_insights_refresh() should exist in scheduler"
    assert insights_pos > transforms_pos, "run_insights_refresh() should be called AFTER run_transforms()"


@pytest.mark.skipif(not os.environ.get('WAREHOUSE_DSN'), reason="WAREHOUSE_DSN not set")
def test_insights_refresh_integration():
    """Integration test: Run actual insights refresh (requires real database)"""
    # This test runs the actual function with real InsightEngine
    # Only runs if WAREHOUSE_DSN is set
    
    result = run_insights_refresh()
    
    # Should succeed or fail gracefully
    assert isinstance(result, bool), "Should return boolean"
    
    # Check metrics were updated
    assert 'insights_refresh' in metrics['tasks']
    
    # Check metrics file was written
    import json
    metrics_file = '/logs/scheduler_metrics.json'
    if os.path.exists(metrics_file):
        with open(metrics_file, 'r') as f:
            saved_metrics = json.load(f)
        assert 'insights_refresh' in saved_metrics['tasks']


def test_update_metrics_with_extra():
    """Test update_metrics handles extra fields correctly"""
    # Update metrics with extra fields
    update_metrics(
        'test_task',
        'success',
        duration=10.5,
        extra={
            'custom_field_1': 'value1',
            'custom_field_2': 42
        }
    )
    
    # Verify extra fields were added
    task_metrics = metrics['tasks']['test_task']
    assert task_metrics['status'] == 'success'
    assert task_metrics['duration_seconds'] == 10.5
    assert task_metrics['custom_field_1'] == 'value1'
    assert task_metrics['custom_field_2'] == 42


def test_insights_metrics_format():
    """Test that insights metrics match expected format"""
    with patch('scheduler.scheduler.InsightEngine') as mock_engine:
        mock_instance = Mock()
        mock_engine.return_value = mock_instance
        
        mock_instance.refresh.return_value = {
            'start_time': '2025-11-14T10:00:00',
            'end_time': '2025-11-14T10:00:10',
            'duration_seconds': 10.0,
            'detectors_run': 3,
            'detectors_succeeded': 3,
            'detectors_failed': 0,
            'total_insights_created': 5,
            'insights_by_detector': {},
            'errors': []
        }
        
        with patch('scheduler.scheduler.InsightsConfig'):
            result = run_insights_refresh()
        
        assert result is True
        
        # Verify metrics structure matches scheduler_metrics.json schema
        task_metrics = metrics['tasks']['insights_refresh']
        assert 'last_run' in task_metrics
        assert 'status' in task_metrics
        assert 'duration_seconds' in task_metrics
        assert 'insights_created' in task_metrics
        assert 'detectors_run' in task_metrics
        assert 'detectors_succeeded' in task_metrics
        assert 'detectors_failed' in task_metrics


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
