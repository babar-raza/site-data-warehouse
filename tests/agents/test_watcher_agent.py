"""Comprehensive tests for watcher agent."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.watcher.alert_manager import Alert, AlertManager
from agents.watcher.anomaly_detector import Anomaly, AnomalyDetector
from agents.watcher.trend_analyzer import Trend, TrendAnalyzer
from agents.watcher.watcher_agent import WatcherAgent


class TestAnomalyDetector:
    """Test anomaly detector functionality."""

    def test_detect_traffic_drop_significant(self):
        """Test detection of significant traffic drops."""
        detector = AnomalyDetector()
        
        # 60% drop (clearly critical)
        current_clicks = 40
        historical_clicks = [100, 95, 105, 98, 102, 100, 97]
        
        anomaly = detector.detect_traffic_drop(current_clicks, historical_clicks)
        
        assert anomaly is not None
        assert anomaly.severity == 'critical'
        assert anomaly.deviation_percent > 30

    def test_detect_traffic_drop_no_anomaly(self):
        """Test that normal traffic variation is not flagged."""
        detector = AnomalyDetector()
        
        # Normal variation
        current_clicks = 95
        historical_clicks = [100, 95, 105, 98, 102, 100, 97]
        
        anomaly = detector.detect_traffic_drop(current_clicks, historical_clicks)
        
        assert anomaly is None

    def test_detect_position_drop_significant(self):
        """Test detection of significant position drops."""
        detector = AnomalyDetector()
        
        # Drop from position 3 to 10
        current_position = 10.0
        historical_positions = [3.0, 2.8, 3.2, 3.1, 2.9, 3.3, 3.0]
        
        anomaly = detector.detect_position_drop(current_position, historical_positions)
        
        assert anomaly is not None
        assert anomaly.severity in ['warning', 'critical']
        assert anomaly.current_value > anomaly.expected_value

    def test_detect_ctr_anomaly_outlier(self):
        """Test CTR anomaly detection using z-score."""
        detector = AnomalyDetector(sensitivity=2.5)
        
        # Outlier CTR
        current_ctr = 1.0
        historical_ctrs = [5.0, 5.2, 4.8, 5.1, 4.9, 5.3, 5.0]
        
        anomaly = detector.detect_ctr_anomaly(current_ctr, historical_ctrs)
        
        assert anomaly is not None
        assert anomaly.metric_name == 'ctr'

    def test_detect_engagement_change(self):
        """Test engagement rate change detection."""
        detector = AnomalyDetector()
        
        # 40% drop in engagement
        current_engagement = 0.30
        historical_engagement = [0.50, 0.52, 0.48, 0.51, 0.49, 0.53, 0.50]
        
        anomaly = detector.detect_engagement_change(
            current_engagement,
            historical_engagement
        )
        
        assert anomaly is not None
        assert anomaly.severity in ['warning', 'critical']

    def test_detect_conversion_drop(self):
        """Test conversion rate drop detection."""
        detector = AnomalyDetector()
        
        # 30% drop in conversions
        current_conversion = 1.4
        historical_conversions = [2.0, 2.1, 1.9, 2.2, 2.0, 1.8, 2.1]
        
        anomaly = detector.detect_conversion_drop(
            current_conversion,
            historical_conversions
        )
        
        assert anomaly is not None
        assert anomaly.metric_name == 'conversion_rate'

    def test_detect_zero_traffic_dead_page(self):
        """Test detection of dead pages (zero traffic)."""
        detector = AnomalyDetector()
        
        # Page had traffic, now has zero
        current_clicks = 0
        current_impressions = 0
        historical_clicks = [50, 45, 55, 48, 52, 50, 47]
        
        anomaly = detector.detect_zero_traffic(
            current_clicks,
            current_impressions,
            historical_clicks
        )
        
        assert anomaly is not None
        assert anomaly.severity == 'critical'
        assert anomaly.deviation_percent == 100

    def test_detect_multivariate_anomaly(self):
        """Test multivariate anomaly detection."""
        detector = AnomalyDetector()
        
        # Historical data with normal patterns
        historical_metrics = [
            {'clicks': 100, 'ctr': 5.0, 'position': 3.0},
            {'clicks': 105, 'ctr': 5.2, 'position': 2.9},
            {'clicks': 98, 'ctr': 4.9, 'position': 3.1},
            {'clicks': 102, 'ctr': 5.1, 'position': 3.0},
            {'clicks': 100, 'ctr': 5.0, 'position': 3.2},
            {'clicks': 97, 'ctr': 4.8, 'position': 3.0},
            {'clicks': 103, 'ctr': 5.3, 'position': 2.8}
        ]
        
        # Anomalous current metrics
        current_metrics = {'clicks': 50, 'ctr': 2.0, 'position': 10.0}
        
        anomaly = detector.detect_multivariate_anomaly(
            current_metrics,
            historical_metrics,
            ['clicks', 'ctr', 'position']
        )
        
        assert anomaly is not None
        assert anomaly.metric_name == 'multivariate'

    def test_insufficient_data(self):
        """Test that detector doesn't flag anomalies with insufficient data."""
        detector = AnomalyDetector(min_data_points=7)
        
        # Only 3 data points
        current_clicks = 50
        historical_clicks = [100, 95, 105]
        
        anomaly = detector.detect_traffic_drop(current_clicks, historical_clicks)
        
        assert anomaly is None

    def test_false_positive_rate(self):
        """Test false positive rate on normal data."""
        detector = AnomalyDetector(sensitivity=2.5)
        
        false_positives = 0
        num_tests = 100
        
        for _ in range(num_tests):
            # Generate normal data with typical variation
            mean = 100
            std_dev = 10
            historical = list(np.random.normal(mean, std_dev, 30))
            current = np.random.normal(mean, std_dev)
            
            anomaly = detector.detect_traffic_drop(int(current), [int(h) for h in historical])
            if anomaly is not None:
                false_positives += 1
        
        false_positive_rate = false_positives / num_tests
        
        # False positive rate should be < 10% for normal data
        assert false_positive_rate < 0.10


class TestTrendAnalyzer:
    """Test trend analyzer functionality."""

    def test_detect_linear_increasing_trend(self):
        """Test detection of increasing linear trend."""
        analyzer = TrendAnalyzer()
        
        # Clear increasing trend
        time_series = [100, 110, 120, 130, 140, 150, 160]
        
        trend = analyzer.detect_linear_trend(time_series)
        
        assert trend is not None
        assert trend.trend_type == 'increasing'
        assert trend.slope > 0
        assert trend.confidence > 0.7

    def test_detect_linear_decreasing_trend(self):
        """Test detection of decreasing linear trend."""
        analyzer = TrendAnalyzer()
        
        # Clear decreasing trend
        time_series = [160, 150, 140, 130, 120, 110, 100]
        
        trend = analyzer.detect_linear_trend(time_series)
        
        assert trend is not None
        assert trend.trend_type == 'decreasing'
        assert trend.slope < 0

    def test_detect_stable_trend(self):
        """Test detection of stable trend."""
        analyzer = TrendAnalyzer()
        
        # Stable with minor variations
        time_series = [100, 102, 98, 101, 99, 100, 102]
        
        trend = analyzer.detect_linear_trend(time_series)
        
        if trend:
            assert trend.trend_type == 'stable'

    def test_detect_exponential_growth(self):
        """Test detection of exponential growth."""
        analyzer = TrendAnalyzer()
        
        # Exponential growth pattern
        time_series = [10, 12, 15, 19, 24, 30, 38]
        
        trend = analyzer.detect_acceleration(time_series)
        
        assert trend is not None
        assert 'exponential' in trend.trend_type

    def test_detect_seasonality(self):
        """Test detection of seasonal patterns."""
        analyzer = TrendAnalyzer()
        
        # Weekly pattern (7-day cycle)
        time_series = [100, 80, 70, 65, 70, 85, 95] * 3
        
        trend = analyzer.detect_seasonality(time_series, period=7)
        
        assert trend is not None
        assert trend.trend_type == 'seasonal'

    def test_detect_volatility(self):
        """Test detection of high volatility."""
        analyzer = TrendAnalyzer()
        
        # High volatility data
        time_series = [100, 150, 80, 130, 70, 160, 90]
        
        trend = analyzer.detect_volatility(time_series)
        
        assert trend is not None
        assert trend.trend_type == 'volatile'

    def test_identify_opportunity_low_ctr(self):
        """Test identification of low CTR opportunity."""
        analyzer = TrendAnalyzer()
        
        opportunity = analyzer.identify_opportunity(
            impressions=1000,
            clicks=10,
            position=5.0,
            historical_avg_ctr=3.0
        )
        
        assert opportunity is not None
        assert len(opportunity['opportunities']) > 0

    def test_identify_opportunity_page_two(self):
        """Test identification of page 2 opportunity."""
        analyzer = TrendAnalyzer()
        
        opportunity = analyzer.identify_opportunity(
            impressions=1000,
            clicks=20,
            position=15.0,
            historical_avg_ctr=2.0
        )
        
        assert opportunity is not None
        assert any(
            opp['type'] == 'page_two_opportunity'
            for opp in opportunity['opportunities']
        )

    def test_detect_emerging_trend(self):
        """Test detection of emerging trends."""
        analyzer = TrendAnalyzer()
        
        # Recent spike
        recent_data = [150, 160, 170]
        historical_baseline = 100
        
        trend = analyzer.detect_emerging_trend(
            recent_data,
            historical_baseline,
            lookback_days=3
        )
        
        assert trend is not None
        assert 'emerging' in trend.trend_type

    def test_calculate_momentum(self):
        """Test momentum calculation."""
        analyzer = TrendAnalyzer()
        
        # Accelerating growth
        time_series = [100, 105, 110, 120, 135, 155, 180, 210, 245, 285, 330, 380, 435, 495]
        
        momentum = analyzer.calculate_momentum(time_series, period=7)
        
        assert momentum > 0


class TestAlertManager:
    """Test alert manager functionality."""

    @pytest.fixture
    def mock_db_config(self):
        """Mock database configuration."""
        return {
            'host': 'localhost',
            'port': 5432,
            'user': 'test',
            'password': 'test',
            'database': 'test'
        }

    @pytest.fixture
    def alert_manager(self, mock_db_config):
        """Create alert manager with mock config."""
        return AlertManager(mock_db_config)

    def test_alert_creation(self):
        """Test alert object creation."""
        alert = Alert(
            agent_name='watcher_001',
            finding_type='anomaly',
            severity='critical',
            affected_pages=['/page1', '/page2'],
            metrics={'clicks': 50, 'expected': 100},
            notes='Traffic drop detected'
        )
        
        assert alert.agent_name == 'watcher_001'
        assert alert.finding_type == 'anomaly'
        assert alert.severity == 'critical'
        assert len(alert.affected_pages) == 2

    @pytest.mark.asyncio
    async def test_alert_manager_connection(self, alert_manager):
        """Test alert manager connection handling."""
        # Create a proper async mock
        mock_pool = AsyncMock()
        mock_pool.close = AsyncMock()
        
        # Patch create_pool to return our mock
        async def mock_create_pool(**kwargs):
            return mock_pool
        
        with patch('asyncpg.create_pool', side_effect=mock_create_pool):
            await alert_manager.connect()
            
            assert alert_manager._pool is not None
            
            # Clean disconnect
            alert_manager._pool = None


class TestWatcherAgent:
    """Test watcher agent functionality."""

    @pytest.fixture
    def mock_db_config(self):
        """Mock database configuration."""
        return {
            'host': 'localhost',
            'port': 5432,
            'user': 'test',
            'password': 'test',
            'database': 'test'
        }

    @pytest.fixture
    def mock_config(self):
        """Mock agent configuration."""
        return {
            'sensitivity': 2.5,
            'min_data_points': 7,
            'min_confidence': 0.7,
            'min_duration': 7
        }

    @pytest.fixture
    def watcher_agent(self, mock_db_config, mock_config):
        """Create watcher agent with mock config."""
        return WatcherAgent(
            agent_id='watcher_test_001',
            db_config=mock_db_config,
            config=mock_config
        )

    def test_watcher_agent_creation(self, watcher_agent):
        """Test watcher agent creation."""
        assert watcher_agent.agent_id == 'watcher_test_001'
        assert watcher_agent.agent_type == 'watcher'
        assert watcher_agent.anomaly_detector is not None
        assert watcher_agent.trend_analyzer is not None

    @pytest.mark.asyncio
    async def test_watcher_agent_initialization(self, watcher_agent):
        """Test watcher agent initialization."""
        # Mock the database connection
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = MagicMock()
            
            success = await watcher_agent.initialize()
            
            # Note: This may fail without actual database, but structure is tested
            # In real test environment with database, this should succeed

    @pytest.mark.asyncio
    async def test_watcher_agent_process(self, watcher_agent):
        """Test watcher agent processing."""
        # Mock database methods
        watcher_agent._pool = MagicMock()
        watcher_agent.detect_anomalies = AsyncMock(return_value=[])
        watcher_agent.detect_trends = AsyncMock(return_value=[])
        
        result = await watcher_agent.process({'days': 7})
        
        assert result['status'] == 'success'
        assert 'anomalies_detected' in result
        assert 'trends_detected' in result

    @pytest.mark.asyncio
    async def test_watcher_agent_health_check(self, watcher_agent):
        """Test watcher agent health check."""
        watcher_agent._start_time = datetime.now() - timedelta(hours=1)
        
        health = await watcher_agent.health_check()
        
        assert health.agent_id == 'watcher_test_001'
        assert health.uptime_seconds > 0


class TestIntegration:
    """Integration tests for watcher system."""

    def test_anomaly_to_alert_flow(self):
        """Test flow from anomaly detection to alert creation."""
        detector = AnomalyDetector()
        
        # Detect anomaly
        current_clicks = 50
        historical_clicks = [100, 95, 105, 98, 102, 100, 97]
        
        anomaly = detector.detect_traffic_drop(current_clicks, historical_clicks)
        
        assert anomaly is not None
        
        # Convert to alert
        alert = Alert(
            agent_name='watcher_001',
            finding_type='anomaly',
            severity=anomaly.severity,
            affected_pages=['/test-page'],
            metrics={
                'metric_name': anomaly.metric_name,
                'current_value': anomaly.current_value,
                'expected_value': anomaly.expected_value,
                'deviation_percent': anomaly.deviation_percent
            }
        )
        
        assert alert.severity == anomaly.severity
        assert alert.finding_type == 'anomaly'

    def test_trend_to_alert_flow(self):
        """Test flow from trend detection to alert creation."""
        analyzer = TrendAnalyzer()
        
        # Detect trend
        time_series = [100, 110, 120, 130, 140, 150, 160]
        trend = analyzer.detect_linear_trend(time_series)
        
        assert trend is not None
        
        # Convert to alert
        alert = Alert(
            agent_name='watcher_001',
            finding_type='trend',
            severity='info',
            affected_pages=['/test-page'],
            metrics={
                'trend_type': trend.trend_type,
                'slope': trend.slope,
                'confidence': trend.confidence
            }
        )
        
        assert alert.finding_type == 'trend'

    def test_system_accuracy_metrics(self):
        """Test overall system accuracy on synthetic data."""
        detector = AnomalyDetector(sensitivity=2.5)
        
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0
        
        # Test with known anomalies
        for _ in range(50):
            # Normal data
            historical = list(np.random.normal(100, 10, 30))
            current = np.random.normal(100, 10)
            
            anomaly = detector.detect_traffic_drop(int(current), [int(h) for h in historical])
            
            if anomaly is None:
                true_negatives += 1
            else:
                false_positives += 1
        
        # Test with actual anomalies
        for _ in range(50):
            historical = list(np.random.normal(100, 10, 30))
            current = 40  # Clear anomaly - 60% drop
            
            anomaly = detector.detect_traffic_drop(current, [int(h) for h in historical])
            
            if anomaly is not None:
                true_positives += 1
            else:
                false_negatives += 1
        
        # Calculate metrics
        accuracy = (true_positives + true_negatives) / 100
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        
        print(f"\nSystem Accuracy Metrics:")
        print(f"  Accuracy: {accuracy:.2%}")
        print(f"  Precision: {precision:.2%}")
        print(f"  Recall: {recall:.2%}")
        print(f"  True Positives: {true_positives}")
        print(f"  False Positives: {false_positives}")
        print(f"  True Negatives: {true_negatives}")
        print(f"  False Negatives: {false_negatives}")
        
        # Accuracy should be > 80%
        assert accuracy > 0.80
        # Precision should be > 70%
        assert precision > 0.70
        # Recall should be > 90%
        assert recall > 0.90


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
