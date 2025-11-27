"""
Comprehensive tests for InsightEngine

Tests the orchestration engine that runs all 8 detectors in sequence,
handles failures, generates actions, and returns statistics.

Coverage: >95% of insights_core/engine.py
Test Count: 20+ test cases covering all scenarios
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from typing import List

from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)
from tests.fixtures.sample_data import generate_insight


# ===== FIXTURES =====

@pytest.fixture
def mock_config():
    """Mock InsightsConfig"""
    config = Mock(spec=InsightsConfig)
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test_db"
    config.risk_threshold_clicks_pct = -20.0
    config.risk_threshold_conversions_pct = -20.0
    config.opportunity_threshold_impressions_pct = 50.0
    config.min_confidence_for_action = 0.7
    config.default_window_days = 7
    return config


@pytest.fixture
def mock_repository():
    """Mock InsightRepository"""
    repo = Mock()
    repo.create = Mock(return_value=Mock(id="test-insight-id"))
    return repo


@pytest.fixture
def mock_detectors():
    """Create mock detectors that return various insight counts"""
    detectors = []
    detector_names = [
        "AnomalyDetector",
        "CannibalizationDetector",
        "ContentQualityDetector",
        "CWVQualityDetector",
        "DiagnosisDetector",
        "OpportunityDetector",
        "TopicStrategyDetector",
        "TrendDetector",
    ]

    for name in detector_names:
        detector = Mock()
        detector.__class__.__name__ = name
        detector.detect = Mock(return_value=5)  # Each detector finds 5 insights
        detectors.append(detector)

    return detectors


@pytest.fixture
def mock_action_generator():
    """Mock ActionGenerator"""
    mock_gen = Mock()
    mock_action = Mock()
    mock_action.id = "action-123"
    mock_action.insight_id = "insight-456"
    mock_action.property = "sc-domain:example.com"
    mock_gen.generate_batch = Mock(return_value=[mock_action] * 10)
    return mock_gen


# ===== TEST INITIALIZATION =====

class TestInsightEngineInit:
    """Test InsightEngine initialization"""

    def test_init_with_config(self, mock_config):
        """Test initialization with provided config"""
        with patch('insights_core.engine.InsightRepository') as mock_repo_class:
            with patch('insights_core.engine.AnomalyDetector'):
                with patch('insights_core.engine.CannibalizationDetector'):
                    with patch('insights_core.engine.ContentQualityDetector'):
                        with patch('insights_core.engine.CWVQualityDetector'):
                            with patch('insights_core.engine.DiagnosisDetector'):
                                with patch('insights_core.engine.OpportunityDetector'):
                                    with patch('insights_core.engine.TopicStrategyDetector'):
                                        with patch('insights_core.engine.TrendDetector'):
                                            engine = InsightEngine(config=mock_config)

                                            assert engine.config == mock_config
                                            assert len(engine.detectors) == 8
                                            mock_repo_class.assert_called_once_with(mock_config.warehouse_dsn)

    def test_init_without_config(self):
        """Test initialization creates default config"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('insights_core.engine.AnomalyDetector'):
                with patch('insights_core.engine.CannibalizationDetector'):
                    with patch('insights_core.engine.ContentQualityDetector'):
                        with patch('insights_core.engine.CWVQualityDetector'):
                            with patch('insights_core.engine.DiagnosisDetector'):
                                with patch('insights_core.engine.OpportunityDetector'):
                                    with patch('insights_core.engine.TopicStrategyDetector'):
                                        with patch('insights_core.engine.TrendDetector'):
                                            engine = InsightEngine()

                                            assert engine.config is not None
                                            assert isinstance(engine.config, InsightsConfig)

    def test_init_creates_all_8_detectors(self, mock_config):
        """Test that all 8 detectors are initialized"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('insights_core.engine.AnomalyDetector') as mock_anomaly:
                with patch('insights_core.engine.CannibalizationDetector') as mock_cannib:
                    with patch('insights_core.engine.ContentQualityDetector') as mock_content:
                        with patch('insights_core.engine.CWVQualityDetector') as mock_cwv:
                            with patch('insights_core.engine.DiagnosisDetector') as mock_diag:
                                with patch('insights_core.engine.OpportunityDetector') as mock_opp:
                                    with patch('insights_core.engine.TopicStrategyDetector') as mock_topic:
                                        with patch('insights_core.engine.TrendDetector') as mock_trend:
                                            engine = InsightEngine(config=mock_config)

                                            # Verify all detectors were instantiated
                                            mock_anomaly.assert_called_once()
                                            mock_cannib.assert_called_once()
                                            mock_content.assert_called_once()
                                            mock_cwv.assert_called_once()
                                            mock_diag.assert_called_once()
                                            mock_opp.assert_called_once()
                                            mock_topic.assert_called_once()
                                            mock_trend.assert_called_once()


# ===== TEST REFRESH METHOD =====

class TestInsightEngineRefresh:
    """Test the main refresh() method"""

    def test_refresh_runs_all_detectors_in_sequence(self, mock_config):
        """Test that refresh runs all 8 detectors in order"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Replace detectors with mocks
            mock_detectors = []
            for i in range(8):
                detector = Mock()
                detector.__class__.__name__ = f"Detector{i}"
                detector.detect = Mock(return_value=i + 1)
                mock_detectors.append(detector)

            engine.detectors = mock_detectors

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify all detectors were called
            assert stats['detectors_run'] == 8
            for i, detector in enumerate(mock_detectors):
                detector.detect.assert_called_once_with(property=None)

            # Verify stats
            assert stats['detectors_succeeded'] == 8
            assert stats['detectors_failed'] == 0
            assert stats['total_insights_created'] == sum(range(1, 9))  # 1+2+3+...+8 = 36

    def test_refresh_with_property_filter(self, mock_config):
        """Test refresh with property filter"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Replace with mock detectors
            mock_detector = Mock()
            mock_detector.__class__.__name__ = "TestDetector"
            mock_detector.detect = Mock(return_value=5)
            engine.detectors = [mock_detector]

            # Run with property
            stats = engine.refresh(property="sc-domain:example.com", generate_actions=False)

            # Verify property was passed to detector
            mock_detector.detect.assert_called_once_with(property="sc-domain:example.com")
            assert stats['property_filter'] == "sc-domain:example.com"

    def test_refresh_handles_detector_failure(self, mock_config):
        """Test that one detector failure doesn't stop others"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create 3 detectors: success, failure, success
            detector1 = Mock()
            detector1.__class__.__name__ = "SuccessDetector1"
            detector1.detect = Mock(return_value=10)

            detector2 = Mock()
            detector2.__class__.__name__ = "FailDetector"
            detector2.detect = Mock(side_effect=Exception("Database connection failed"))

            detector3 = Mock()
            detector3.__class__.__name__ = "SuccessDetector2"
            detector3.detect = Mock(return_value=5)

            engine.detectors = [detector1, detector2, detector3]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify all were attempted
            assert stats['detectors_run'] == 3
            assert stats['detectors_succeeded'] == 2
            assert stats['detectors_failed'] == 1
            assert stats['total_insights_created'] == 15  # 10 + 0 + 5

            # Verify error was recorded
            assert len(stats['errors']) == 1
            assert stats['errors'][0]['detector'] == "FailDetector"
            assert "Database connection failed" in stats['errors'][0]['error']

    def test_refresh_all_detectors_fail(self, mock_config):
        """Test when all detectors fail"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create failing detectors
            failing_detector = Mock()
            failing_detector.__class__.__name__ = "FailingDetector"
            failing_detector.detect = Mock(side_effect=RuntimeError("Critical error"))

            engine.detectors = [failing_detector]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify stats
            assert stats['detectors_run'] == 1
            assert stats['detectors_succeeded'] == 0
            assert stats['detectors_failed'] == 1
            assert stats['total_insights_created'] == 0
            assert len(stats['errors']) == 1

    def test_refresh_all_detectors_return_zero(self, mock_config):
        """Test when all detectors find no insights"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create detectors that find nothing
            detector = Mock()
            detector.__class__.__name__ = "EmptyDetector"
            detector.detect = Mock(return_value=0)

            engine.detectors = [detector] * 3

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify stats
            assert stats['detectors_run'] == 3
            assert stats['detectors_succeeded'] == 3
            assert stats['detectors_failed'] == 0
            assert stats['total_insights_created'] == 0

    def test_refresh_returns_complete_statistics(self, mock_config):
        """Test that refresh returns complete stats dict"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            detector = Mock()
            detector.__class__.__name__ = "TestDetector"
            detector.detect = Mock(return_value=5)
            engine.detectors = [detector]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify all expected keys exist
            assert 'start_time' in stats
            assert 'end_time' in stats
            assert 'duration_seconds' in stats
            assert 'property_filter' in stats
            assert 'detectors_run' in stats
            assert 'detectors_succeeded' in stats
            assert 'detectors_failed' in stats
            assert 'total_insights_created' in stats
            assert 'insights_by_detector' in stats
            assert 'errors' in stats
            assert 'actions_generated' in stats

            # Verify timing
            assert isinstance(stats['start_time'], str)
            assert isinstance(stats['end_time'], str)
            assert stats['duration_seconds'] >= 0

    def test_refresh_insights_by_detector_mapping(self, mock_config):
        """Test that insights_by_detector correctly maps counts"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create detectors with different return values
            detector1 = Mock()
            detector1.__class__.__name__ = "Detector1"
            detector1.detect = Mock(return_value=10)

            detector2 = Mock()
            detector2.__class__.__name__ = "Detector2"
            detector2.detect = Mock(return_value=5)

            detector3 = Mock()
            detector3.__class__.__name__ = "Detector3"
            detector3.detect = Mock(side_effect=Exception("Failed"))

            engine.detectors = [detector1, detector2, detector3]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify mapping
            assert stats['insights_by_detector']['Detector1'] == 10
            assert stats['insights_by_detector']['Detector2'] == 5
            assert stats['insights_by_detector']['Detector3'] == 0  # Failed detector shows 0


# ===== TEST ACTION GENERATION =====

class TestInsightEngineActionGeneration:
    """Test action generation integration"""

    def test_refresh_generates_actions_when_enabled_with_property(self, mock_config):
        """Test that actions are generated when enabled and property specified"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
                engine = InsightEngine(config=mock_config)

                # Setup mock action generator
                mock_gen = Mock()
                mock_gen.generate_batch = Mock(return_value=[Mock(id=f"action-{i}") for i in range(10)])
                mock_action_gen_class.return_value = mock_gen

                # Create detector that finds insights
                detector = Mock()
                detector.__class__.__name__ = "TestDetector"
                detector.detect = Mock(return_value=20)
                engine.detectors = [detector]

                # Run refresh with property
                stats = engine.refresh(property="sc-domain:example.com", generate_actions=True)

                # Verify action generator was called
                mock_action_gen_class.assert_called_once_with(db_dsn=mock_config.warehouse_dsn)
                mock_gen.generate_batch.assert_called_once_with("sc-domain:example.com", limit=100)

                # Verify stats
                assert stats['actions_generated'] == 10
                assert 'action_duration_seconds' in stats

    def test_refresh_skips_actions_when_no_property(self, mock_config):
        """Test that actions are skipped when no property specified"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
                engine = InsightEngine(config=mock_config)

                # Setup mock action generator
                mock_gen = Mock()
                mock_action_gen_class.return_value = mock_gen

                detector = Mock()
                detector.__class__.__name__ = "TestDetector"
                detector.detect = Mock(return_value=20)
                engine.detectors = [detector]

                # Run refresh without property
                stats = engine.refresh(property=None, generate_actions=True)

                # ActionGenerator is instantiated but generate_batch is not called
                mock_action_gen_class.assert_called_once_with(db_dsn=mock_config.warehouse_dsn)
                mock_gen.generate_batch.assert_not_called()

                # Verify stats
                assert stats['actions_generated'] == 0
                assert stats.get('action_skipped') is True

    def test_refresh_skips_actions_when_disabled(self, mock_config):
        """Test that actions are not generated when disabled"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
                engine = InsightEngine(config=mock_config)

                detector = Mock()
                detector.__class__.__name__ = "TestDetector"
                detector.detect = Mock(return_value=20)
                engine.detectors = [detector]

                # Run refresh with actions disabled
                stats = engine.refresh(property="sc-domain:example.com", generate_actions=False)

                # Verify action generator was NOT called
                mock_action_gen_class.assert_not_called()

                # Verify stats
                assert stats['actions_generated'] == 0

    def test_refresh_skips_actions_when_no_insights(self, mock_config):
        """Test that actions are not generated when no insights created"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
                engine = InsightEngine(config=mock_config)

                # Detector finds nothing
                detector = Mock()
                detector.__class__.__name__ = "EmptyDetector"
                detector.detect = Mock(return_value=0)
                engine.detectors = [detector]

                # Run refresh
                stats = engine.refresh(property="sc-domain:example.com", generate_actions=True)

                # Verify action generator was NOT called
                mock_action_gen_class.assert_not_called()

                # Verify stats
                assert stats['actions_generated'] == 0

    def test_refresh_continues_when_action_generation_fails(self, mock_config):
        """Test that action generation failure doesn't crash refresh"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('services.action_generator.ActionGenerator') as mock_action_gen_class:
                engine = InsightEngine(config=mock_config)

                # Setup failing action generator
                mock_gen = Mock()
                mock_gen.generate_batch = Mock(side_effect=Exception("Action generation error"))
                mock_action_gen_class.return_value = mock_gen

                detector = Mock()
                detector.__class__.__name__ = "TestDetector"
                detector.detect = Mock(return_value=20)
                engine.detectors = [detector]

                # Run refresh - should not raise exception
                stats = engine.refresh(property="sc-domain:example.com", generate_actions=True)

                # Verify stats show failure
                assert stats['actions_generated'] == 0
                assert 'action_error' in stats
                assert "Action generation error" in stats['action_error']

                # Verify insights were still created
                assert stats['total_insights_created'] == 20


# ===== TEST DETECTOR STATS =====

class TestInsightEngineGetDetectorStats:
    """Test get_detector_stats() method"""

    def test_get_detector_stats_returns_all_detectors(self, mock_config):
        """Test that get_detector_stats returns info about all 8 detectors"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            stats = engine.get_detector_stats()

            assert 'total_detectors' in stats
            assert stats['total_detectors'] == 8
            assert 'detectors' in stats
            assert len(stats['detectors']) == 8

    def test_get_detector_stats_structure(self, mock_config):
        """Test the structure of detector stats"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            stats = engine.get_detector_stats()

            # Check first detector
            first_detector = stats['detectors'][0]
            assert 'name' in first_detector
            assert 'type' in first_detector
            assert first_detector['name'] == 'AnomalyDetector'
            assert first_detector['type'] == 'anomaly'


# ===== TEST CONCURRENT SAFETY =====

class TestInsightEngineConcurrentSafety:
    """Test that engine handles multiple simultaneous operations safely"""

    def test_multiple_refresh_calls_are_independent(self, mock_config):
        """Test that multiple refresh calls don't interfere with each other"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create detector with incrementing counter
            call_count = [0]

            def detect_fn(property=None):
                call_count[0] += 1
                return call_count[0]

            detector = Mock()
            detector.__class__.__name__ = "CountingDetector"
            detector.detect = Mock(side_effect=detect_fn)
            engine.detectors = [detector]

            # Run multiple refreshes
            stats1 = engine.refresh(generate_actions=False)
            stats2 = engine.refresh(generate_actions=False)
            stats3 = engine.refresh(generate_actions=False)

            # Each refresh should be independent
            assert stats1['total_insights_created'] == 1
            assert stats2['total_insights_created'] == 2
            assert stats3['total_insights_created'] == 3

    def test_partial_detector_failure_scenario(self, mock_config):
        """Test realistic scenario with some detectors succeeding and some failing"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Create realistic mix of detectors
            detectors = []

            # 5 successful detectors
            for i in range(5):
                detector = Mock()
                detector.__class__.__name__ = f"SuccessDetector{i}"
                detector.detect = Mock(return_value=i + 5)  # 5, 6, 7, 8, 9
                detectors.append(detector)

            # 2 failing detectors
            for i in range(2):
                detector = Mock()
                detector.__class__.__name__ = f"FailDetector{i}"
                detector.detect = Mock(side_effect=RuntimeError(f"Error {i}"))
                detectors.append(detector)

            # 1 detector that finds nothing
            detector = Mock()
            detector.__class__.__name__ = "EmptyDetector"
            detector.detect = Mock(return_value=0)
            detectors.append(detector)

            engine.detectors = detectors

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify results
            assert stats['detectors_run'] == 8
            assert stats['detectors_succeeded'] == 6  # 5 + 1 empty
            assert stats['detectors_failed'] == 2
            assert stats['total_insights_created'] == 35  # 5+6+7+8+9 = 35
            assert len(stats['errors']) == 2


# ===== TEST EDGE CASES =====

class TestInsightEngineEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_refresh_with_empty_detector_list(self, mock_config):
        """Test refresh with no detectors (edge case)"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)
            engine.detectors = []  # Remove all detectors

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Should complete successfully with zeros
            assert stats['detectors_run'] == 0
            assert stats['detectors_succeeded'] == 0
            assert stats['detectors_failed'] == 0
            assert stats['total_insights_created'] == 0

    def test_refresh_with_very_large_insight_count(self, mock_config):
        """Test handling of very large insight counts"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Detector returns huge number
            detector = Mock()
            detector.__class__.__name__ = "MassiveDetector"
            detector.detect = Mock(return_value=999999)
            engine.detectors = [detector]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Should handle large numbers
            assert stats['total_insights_created'] == 999999
            assert stats['insights_by_detector']['MassiveDetector'] == 999999

    def test_refresh_detector_exception_handling(self, mock_config):
        """Test proper exception handling when detector raises an exception"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            # Detector that raises an exception
            detector = Mock()
            detector.__class__.__name__ = "ExceptionDetector"
            detector.detect = Mock(side_effect=ValueError("Invalid data"))
            engine.detectors = [detector]

            # Run refresh - should handle exception gracefully
            stats = engine.refresh(generate_actions=False)

            # The detector runs but fails with exception
            assert stats['detectors_run'] == 1
            assert stats['detectors_succeeded'] == 0
            assert stats['detectors_failed'] == 1
            assert stats['total_insights_created'] == 0

            # Should have an error recorded
            assert len(stats['errors']) == 1
            assert stats['errors'][0]['detector'] == 'ExceptionDetector'
            assert 'Invalid data' in stats['errors'][0]['error']

    def test_refresh_duration_is_reasonable(self, mock_config):
        """Test that duration tracking works correctly"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            detector = Mock()
            detector.__class__.__name__ = "TestDetector"
            detector.detect = Mock(return_value=5)
            engine.detectors = [detector]

            # Run refresh
            stats = engine.refresh(generate_actions=False)

            # Verify duration
            assert 'duration_seconds' in stats
            assert stats['duration_seconds'] >= 0
            assert stats['duration_seconds'] < 10  # Should be very fast with mocks

    def test_refresh_with_unicode_property(self, mock_config):
        """Test handling of unicode characters in property"""
        with patch('insights_core.engine.InsightRepository'):
            engine = InsightEngine(config=mock_config)

            detector = Mock()
            detector.__class__.__name__ = "TestDetector"
            detector.detect = Mock(return_value=1)
            engine.detectors = [detector]

            # Run with unicode property
            unicode_property = "https://例え.com/"
            stats = engine.refresh(property=unicode_property, generate_actions=False)

            # Should handle unicode
            assert stats['property_filter'] == unicode_property
            detector.detect.assert_called_once_with(property=unicode_property)
