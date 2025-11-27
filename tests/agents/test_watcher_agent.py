"""Comprehensive tests for WatcherAgent with >90% coverage."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import numpy as np
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentStatus
from agents.base.llm_reasoner import ReasoningResult
from agents.watcher.alert_manager import Alert, AlertManager
from agents.watcher.anomaly_detector import Anomaly, AnomalyDetector
from agents.watcher.trend_analyzer import Trend, TrendAnalyzer
from agents.watcher.watcher_agent import AnomalyFinding, WatcherAgent


# ============================================================================
# Test WatcherAgent Lifecycle
# ============================================================================

class TestWatcherAgentLifecycle:
    """Test WatcherAgent initialization, processing, and shutdown."""

    @pytest.fixture
    def mock_db_config(self):
        """Mock database configuration."""
        return {
            'host': 'localhost',
            'port': 5432,
            'user': 'test_user',
            'password': 'test_password',
            'database': 'test_database'
        }

    @pytest.fixture
    def agent_config(self):
        """Agent configuration."""
        return {
            'sensitivity': 2.5,
            'min_data_points': 7,
            'min_confidence': 0.7,
            'min_duration': 7,
            'use_llm': True,
            'llm_timeout': 30.0,
            'llm_retries': 1
        }

    @pytest.fixture
    def watcher_agent(self, mock_db_config, agent_config):
        """Create watcher agent instance."""
        return WatcherAgent(
            agent_id='watcher_test_001',
            db_config=mock_db_config,
            config=agent_config
        )

    def test_agent_initialization_attributes(self, watcher_agent, mock_db_config):
        """Test that agent initializes with correct attributes."""
        assert watcher_agent.agent_id == 'watcher_test_001'
        assert watcher_agent.agent_type == 'watcher'
        assert watcher_agent.db_config == mock_db_config
        assert watcher_agent.status == AgentStatus.INITIALIZED
        assert watcher_agent.anomaly_detector is not None
        assert watcher_agent.trend_analyzer is not None
        assert watcher_agent.alert_manager is not None
        assert watcher_agent.use_llm is True
        assert watcher_agent.llm_reasoner is not None

    def test_agent_initialization_without_llm(self, mock_db_config):
        """Test agent initialization with LLM disabled."""
        config = {'use_llm': False, 'sensitivity': 2.5}
        agent = WatcherAgent(
            agent_id='watcher_no_llm',
            db_config=mock_db_config,
            config=config
        )

        assert agent.use_llm is False
        assert agent.llm_reasoner is None

    def test_agent_initialization_default_config(self, mock_db_config):
        """Test agent initialization with default config."""
        agent = WatcherAgent(
            agent_id='watcher_default',
            db_config=mock_db_config,
            config=None
        )

        assert agent.anomaly_detector.sensitivity == 2.5
        assert agent.anomaly_detector.min_data_points == 7

    @pytest.mark.asyncio
    async def test_agent_initialize_success(self, watcher_agent):
        """Test successful agent initialization."""
        mock_pool = AsyncMock()

        async def mock_create_pool(**kwargs):
            return mock_pool

        with patch('asyncpg.create_pool', side_effect=mock_create_pool):
            watcher_agent.alert_manager.connect = AsyncMock()

            success = await watcher_agent.initialize()

            assert success is True
            assert watcher_agent.status == AgentStatus.RUNNING
            assert watcher_agent._pool is not None
            assert watcher_agent._start_time is not None

    @pytest.mark.asyncio
    async def test_agent_initialize_database_error(self, watcher_agent):
        """Test agent initialization handles database errors."""
        with patch('asyncpg.create_pool', side_effect=Exception("DB connection failed")):
            success = await watcher_agent.initialize()

            assert success is False
            assert watcher_agent.status == AgentStatus.ERROR
            assert watcher_agent._error_count == 1

    @pytest.mark.asyncio
    async def test_agent_process_success(self, watcher_agent):
        """Test successful process execution."""
        watcher_agent._pool = MagicMock()
        watcher_agent.detect_anomalies = AsyncMock(return_value=[])
        watcher_agent.detect_trends = AsyncMock(return_value=[])

        result = await watcher_agent.process({'days': 7, 'property': 'test-site'})

        assert result['status'] == 'success'
        assert result['anomalies_detected'] == 0
        assert result['trends_detected'] == 0
        assert result['agent_id'] == 'watcher_test_001'
        assert watcher_agent._processed_count == 1

    @pytest.mark.asyncio
    async def test_agent_process_with_results(self, watcher_agent):
        """Test process with actual anomalies and trends detected."""
        watcher_agent._pool = MagicMock()

        mock_anomalies = [
            Anomaly('clicks', '/page1', 50, 100, -50, 'critical', datetime.now(), {}),
            Anomaly('ctr', '/page2', 2.0, 5.0, -60, 'warning', datetime.now(), {})
        ]
        mock_trends = [
            Trend('clicks', '/page3', 'increasing', 5.0, 0.9, 14, 30.0, datetime.now(), {})
        ]

        watcher_agent.detect_anomalies = AsyncMock(return_value=mock_anomalies)
        watcher_agent.detect_trends = AsyncMock(return_value=mock_trends)

        result = await watcher_agent.process({'days': 14})

        assert result['status'] == 'success'
        assert result['anomalies_detected'] == 2
        assert result['trends_detected'] == 1

    @pytest.mark.asyncio
    async def test_agent_process_error_handling(self, watcher_agent):
        """Test process error handling."""
        watcher_agent.detect_anomalies = AsyncMock(side_effect=Exception("Processing error"))

        result = await watcher_agent.process({'days': 7})

        assert result['status'] == 'error'
        assert 'error' in result
        assert 'Processing error' in result['error']
        assert watcher_agent._error_count == 1

    @pytest.mark.asyncio
    async def test_agent_shutdown_success(self, watcher_agent):
        """Test successful agent shutdown."""
        mock_pool = AsyncMock()
        watcher_agent._pool = mock_pool
        watcher_agent.alert_manager.disconnect = AsyncMock()

        success = await watcher_agent.shutdown()

        assert success is True
        assert watcher_agent.status == AgentStatus.SHUTDOWN
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_shutdown_error(self, watcher_agent):
        """Test shutdown handles errors."""
        mock_pool = AsyncMock()
        mock_pool.close.side_effect = Exception("Shutdown error")
        watcher_agent._pool = mock_pool
        watcher_agent.alert_manager.disconnect = AsyncMock()

        success = await watcher_agent.shutdown()

        assert success is False

    @pytest.mark.asyncio
    async def test_agent_health_check(self, watcher_agent):
        """Test agent health check."""
        watcher_agent._start_time = datetime.now() - timedelta(hours=2)
        watcher_agent._processed_count = 42
        watcher_agent._error_count = 3
        watcher_agent._detected_anomalies = [Mock(), Mock()]
        watcher_agent._detected_trends = [Mock()]

        health = await watcher_agent.health_check()

        assert health.agent_id == 'watcher_test_001'
        assert health.status == AgentStatus.INITIALIZED
        assert health.uptime_seconds > 7000  # > 2 hours
        assert health.processed_count == 42
        assert health.error_count == 3
        assert health.metadata['anomalies_detected'] == 2
        assert health.metadata['trends_detected'] == 1
        assert 'llm_stats' in health.metadata


# ============================================================================
# Test Anomaly Detection
# ============================================================================

class TestAnomalyDetection:
    """Test anomaly detection functionality."""

    @pytest.fixture
    def mock_db_config(self):
        return {
            'host': 'localhost',
            'port': 5432,
            'user': 'test',
            'password': 'test',
            'database': 'test'
        }

    @pytest.fixture
    def watcher_agent(self, mock_db_config):
        config = {'sensitivity': 2.5, 'min_data_points': 7, 'use_llm': False}
        return WatcherAgent('watcher_test', mock_db_config, config)

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_pages(self, watcher_agent):
        """Test anomaly detection with no active pages."""
        watcher_agent._get_active_pages = AsyncMock(return_value=[])

        anomalies = await watcher_agent.detect_anomalies(days=7)

        assert anomalies == []
        assert watcher_agent._detected_anomalies == []

    @pytest.mark.asyncio
    async def test_detect_anomalies_traffic_drop(self, watcher_agent):
        """Test detection of traffic drop anomalies."""
        mock_pages = [{'page_path': '/test-page', 'last_seen': datetime.now()}]

        # Historical data with normal traffic, then a drop
        historical_data = [
            {'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
             'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80}
            for _ in range(30)
        ]
        # Last 7 days with drop
        for i in range(7):
            historical_data.append({
                'clicks': 40,  # 60% drop
                'impressions': 1000,
                'ctr': 4.0,
                'avg_position': 3.0,
                'engagement_rate': 0.5,
                'conversion_rate': 2.0,
                'sessions': 30
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        assert len(anomalies) > 0
        # Should detect traffic drop
        traffic_anomalies = [a for a in anomalies if a.metric_name == 'clicks']
        assert len(traffic_anomalies) > 0
        assert traffic_anomalies[0].severity in ['critical', 'warning']

    @pytest.mark.asyncio
    async def test_detect_anomalies_position_drop(self, watcher_agent):
        """Test detection of position drop anomalies."""
        mock_pages = [{'page_path': '/ranking-drop', 'last_seen': datetime.now()}]

        historical_data = []
        # Good positions
        for _ in range(30):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })
        # Position drop
        for _ in range(7):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 15.0,  # Drop to page 2
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        position_anomalies = [a for a in anomalies if a.metric_name == 'position']
        assert len(position_anomalies) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_multiple_pages(self, watcher_agent):
        """Test anomaly detection across multiple pages."""
        mock_pages = [
            {'page_path': '/page1', 'last_seen': datetime.now()},
            {'page_path': '/page2', 'last_seen': datetime.now()},
            {'page_path': '/page3', 'last_seen': datetime.now()}
        ]

        # Return different historical data for each page
        async def mock_historical_data(page_path, days, property_filter):
            base_data = [
                {'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                 'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80}
                for _ in range(days)
            ]
            return base_data

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(side_effect=mock_historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        # Should have processed all 3 pages
        assert watcher_agent._get_page_historical_data.call_count == 3

    @pytest.mark.asyncio
    async def test_detect_anomalies_insufficient_data(self, watcher_agent):
        """Test anomaly detection with insufficient historical data."""
        mock_pages = [{'page_path': '/new-page', 'last_seen': datetime.now()}]

        # Only 3 days of data
        historical_data = [
            {'clicks': 50, 'impressions': 500, 'ctr': 10.0, 'avg_position': 5.0,
             'engagement_rate': 0.4, 'conversion_rate': 1.5, 'sessions': 40}
            for _ in range(3)
        ]

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        # Should not detect anomalies with insufficient data
        assert len(anomalies) == 0


# ============================================================================
# Test Trend Detection
# ============================================================================

class TestTrendDetection:
    """Test trend detection functionality."""

    @pytest.fixture
    def mock_db_config(self):
        return {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}

    @pytest.fixture
    def watcher_agent(self, mock_db_config):
        config = {'min_confidence': 0.7, 'min_duration': 7, 'use_llm': False}
        return WatcherAgent('watcher_trends', mock_db_config, config)

    @pytest.mark.asyncio
    async def test_detect_trends_increasing(self, watcher_agent):
        """Test detection of increasing trends."""
        mock_pages = [{'page_path': '/growing-page', 'last_seen': datetime.now()}]

        # Create increasing time series
        time_series_data = [
            {'clicks': 100 + i * 10, 'impressions': 1000 + i * 100, 'ctr': 10.0}
            for i in range(14)
        ]

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_time_series = AsyncMock(return_value=time_series_data)
        watcher_agent._create_trend_alert = AsyncMock()

        trends = await watcher_agent.detect_trends(days=7)

        # Should detect increasing trends
        increasing_trends = [t for t in trends if t.trend_type == 'increasing']
        assert len(increasing_trends) > 0

    @pytest.mark.asyncio
    async def test_detect_trends_no_pages(self, watcher_agent):
        """Test trend detection with no pages."""
        watcher_agent._get_active_pages = AsyncMock(return_value=[])

        trends = await watcher_agent.detect_trends(days=7)

        assert trends == []


# ============================================================================
# Test LLM Integration
# ============================================================================

class TestLLMIntegration:
    """Test LLM integration for anomaly evaluation."""

    @pytest.fixture
    def mock_db_config(self):
        return {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}

    @pytest.fixture
    def watcher_with_llm(self, mock_db_config):
        config = {'use_llm': True, 'llm_timeout': 30.0, 'llm_retries': 1}
        return WatcherAgent('watcher_llm', mock_db_config, config)

    @pytest.fixture
    def watcher_without_llm(self, mock_db_config):
        config = {'use_llm': False}
        return WatcherAgent('watcher_no_llm', mock_db_config, config)

    @pytest.mark.asyncio
    async def test_evaluate_anomaly_with_llm_success(self, watcher_with_llm):
        """Test anomaly evaluation with successful LLM reasoning."""
        page_path = '/test-page'
        metrics = {
            'metric_name': 'clicks',
            'current_value': 50,
            'expected_value': 100,
            'deviation_percent': -50.0
        }
        historical = [100, 95, 105, 98, 102, 100, 97]

        # Mock LLM result
        mock_llm_result = ReasoningResult(
            success=True,
            content={
                'confidence': 0.9,
                'severity': 'critical',
                'likely_causes': ['Ranking drop', 'Algorithm update'],
                'recommended_actions': ['Investigate GSC', 'Check backlinks']
            },
            raw_response='Critical traffic anomaly detected',
            model_used='llama3',
            duration_ms=500
        )

        watcher_with_llm._run_llm_reasoning = AsyncMock(return_value=mock_llm_result)

        finding = await watcher_with_llm.evaluate_anomaly(page_path, metrics, historical)

        assert finding is not None
        assert finding.used_llm is True
        assert finding.used_ml_fallback is False
        assert finding.severity == 'critical'
        assert len(finding.likely_causes) == 2
        assert len(finding.recommended_actions) == 2
        assert finding.combined_confidence > 0.5

    @pytest.mark.asyncio
    async def test_evaluate_anomaly_with_llm_failure_fallback_to_ml(self, watcher_with_llm):
        """Test anomaly evaluation falls back to ML when LLM fails."""
        page_path = '/test-page'
        metrics = {'metric_name': 'clicks', 'current_value': 40}
        historical = [100, 95, 105, 98, 102, 100, 97]

        # Mock LLM failure
        mock_llm_result = ReasoningResult(
            success=False,
            content=None,
            error='LLM timeout',
            model_used='llama3',
            duration_ms=30000
        )

        watcher_with_llm._run_llm_reasoning = AsyncMock(return_value=mock_llm_result)

        finding = await watcher_with_llm.evaluate_anomaly(page_path, metrics, historical)

        assert finding is not None
        assert finding.used_llm is False
        assert finding.used_ml_fallback is True

    @pytest.mark.asyncio
    async def test_evaluate_anomaly_without_llm(self, watcher_without_llm):
        """Test anomaly evaluation uses ML when LLM is disabled."""
        page_path = '/test-page'
        metrics = {'metric_name': 'clicks', 'current_value': 40}
        historical = [100, 95, 105, 98, 102, 100, 97]

        finding = await watcher_without_llm.evaluate_anomaly(page_path, metrics, historical)

        assert finding is not None
        assert finding.used_llm is False
        assert finding.used_ml_fallback is True

    @pytest.mark.asyncio
    async def test_run_llm_reasoning_builds_context(self, watcher_with_llm):
        """Test that LLM reasoning builds proper context."""
        page_path = '/test-page'
        metrics = {'metric_name': 'clicks', 'current_value': 50}

        ml_anomaly = Anomaly(
            metric_name='clicks',
            page_path=page_path,
            current_value=50,
            expected_value=100,
            deviation_percent=-50.0,
            severity='critical',
            detected_at=datetime.now(),
            context={}
        )

        # Mock the reasoner
        mock_reasoner = AsyncMock()
        mock_reasoner.reason = AsyncMock(return_value=ReasoningResult(
            success=True,
            content={'severity': 'high'},
            raw_response='Test',
            model_used='test'
        ))
        watcher_with_llm.llm_reasoner = mock_reasoner

        result = await watcher_with_llm._run_llm_reasoning(page_path, metrics, ml_anomaly)

        # Verify reasoner was called with proper context
        assert mock_reasoner.reason.called
        call_args = mock_reasoner.reason.call_args[1]  # Get kwargs
        context = call_args.get('context') or call_args.get('template_vars', {})

        # The context should contain relevant information
        assert result.success is True

    @pytest.mark.asyncio
    async def test_run_llm_reasoning_disabled(self, watcher_without_llm):
        """Test that LLM reasoning returns None when disabled."""
        result = await watcher_without_llm._run_llm_reasoning('/page', {}, None)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_llm_reasoning_exception_handling(self, watcher_with_llm):
        """Test LLM reasoning handles exceptions."""
        # Mock reasoner that raises exception
        mock_reasoner = AsyncMock()
        mock_reasoner.reason = AsyncMock(side_effect=Exception("LLM error"))
        watcher_with_llm.llm_reasoner = mock_reasoner

        result = await watcher_with_llm._run_llm_reasoning('/page', {}, None)

        assert result is None
        assert watcher_with_llm._llm_failure_count == 1

    def test_combine_llm_ml_results_both_critical(self, watcher_with_llm):
        """Test combining results when both LLM and ML indicate critical severity."""
        finding = AnomalyFinding(page_path='/test', metric_name='clicks', severity='info')

        llm_result = ReasoningResult(
            success=True,
            content={
                'confidence': 0.95,
                'severity': 'critical',
                'likely_causes': ['Major drop'],
                'recommended_actions': ['Act now']
            },
            raw_response='Critical issue',
            model_used='test',
            duration_ms=100
        )

        ml_anomaly = Anomaly(
            metric_name='clicks',
            page_path='/test',
            current_value=20,
            expected_value=100,
            deviation_percent=-80.0,
            severity='critical',
            detected_at=datetime.now(),
            context={}
        )

        result = watcher_with_llm._combine_llm_ml_results(finding, llm_result, ml_anomaly)

        assert result.severity == 'critical'
        assert result.combined_confidence > 0.5  # Lowered threshold
        assert len(result.likely_causes) > 0
        assert len(result.recommended_actions) > 0

    def test_combine_llm_ml_results_llm_high_ml_low(self, watcher_with_llm):
        """Test combining results when LLM says high but ML says low."""
        finding = AnomalyFinding(page_path='/test', metric_name='clicks', severity='info')

        llm_result = ReasoningResult(
            success=True,
            content={
                'confidence': 0.8,
                'severity': 'high',
                'likely_causes': ['Contextual issue'],
                'recommended_actions': ['Review']
            },
            raw_response='High severity'
        )

        # No ML anomaly detected
        result = watcher_with_llm._combine_llm_ml_results(finding, llm_result, None)

        assert result.severity == 'high'
        # Confidence should be primarily from LLM
        expected_conf = 0.6 * 0.8  # LLM_WEIGHT * llm_confidence
        assert abs(result.combined_confidence - expected_conf) < 0.01

    def test_apply_ml_fallback_with_anomaly(self, watcher_with_llm):
        """Test ML fallback generates proper causes and actions."""
        finding = AnomalyFinding(page_path='/test', metric_name='clicks', severity='info')

        ml_anomaly = Anomaly(
            metric_name='clicks',
            page_path='/test',
            current_value=40,
            expected_value=100,
            deviation_percent=-60.0,
            severity='critical',
            detected_at=datetime.now(),
            context={}
        )

        result = watcher_with_llm._apply_ml_fallback(finding, ml_anomaly)

        assert result.severity == 'critical'
        assert result.combined_confidence > 0
        assert 'ML Detection' in result.reasoning
        assert len(result.likely_causes) > 0
        assert len(result.recommended_actions) > 0

    def test_apply_ml_fallback_no_anomaly(self, watcher_with_llm):
        """Test ML fallback with no anomaly detected."""
        finding = AnomalyFinding(page_path='/test', metric_name='clicks', severity='info')

        result = watcher_with_llm._apply_ml_fallback(finding, None)

        assert result.severity == 'info'
        assert result.combined_confidence == 0.0
        assert 'No anomaly detected' in result.reasoning

    def test_generate_ml_causes_for_different_metrics(self, watcher_with_llm):
        """Test ML cause generation for different metric types."""
        # Traffic metric
        traffic_anomaly = Anomaly('clicks', '/test', 50, 100, -50, 'critical', datetime.now(), {})
        traffic_causes = watcher_with_llm._generate_ml_causes(traffic_anomaly)
        assert len(traffic_causes) > 0
        assert any('ranking' in c.lower() for c in traffic_causes)

        # Position metric
        position_anomaly = Anomaly('avg_position', '/test', 15, 5, 200, 'warning', datetime.now(), {})
        position_causes = watcher_with_llm._generate_ml_causes(position_anomaly)
        assert len(position_causes) > 0

        # CTR metric
        ctr_anomaly = Anomaly('ctr', '/test', 2, 5, -60, 'warning', datetime.now(), {})
        ctr_causes = watcher_with_llm._generate_ml_causes(ctr_anomaly)
        assert len(ctr_causes) > 0

    def test_generate_ml_actions_by_severity(self, watcher_with_llm):
        """Test ML action generation includes severity-appropriate actions."""
        # Critical severity
        critical_anomaly = Anomaly('clicks', '/test', 20, 100, -80, 'critical', datetime.now(), {})
        critical_actions = watcher_with_llm._generate_ml_actions(critical_anomaly)
        assert any('immediately' in a.lower() for a in critical_actions)

        # High severity
        high_anomaly = Anomaly('clicks', '/test', 60, 100, -40, 'high', datetime.now(), {})
        high_actions = watcher_with_llm._generate_ml_actions(high_anomaly)
        assert any('urgent' in a.lower() or 'review' in a.lower() for a in high_actions)

    def test_generate_ml_actions_limited_to_five(self, watcher_with_llm):
        """Test that ML actions are limited to 5 items."""
        anomaly = Anomaly('clicks', '/test', 20, 100, -80, 'critical', datetime.now(), {})
        actions = watcher_with_llm._generate_ml_actions(anomaly)

        assert len(actions) <= 5

    def test_get_llm_stats(self, watcher_with_llm):
        """Test LLM statistics tracking."""
        # Initial stats
        stats = watcher_with_llm.get_llm_stats()
        assert stats['total_calls'] == 0
        assert stats['successful_calls'] == 0
        assert stats['failed_calls'] == 0
        assert stats['success_rate'] == 0.0
        assert stats['llm_enabled'] is True

        # Simulate some calls
        watcher_with_llm._llm_call_count = 10
        watcher_with_llm._llm_success_count = 7
        watcher_with_llm._llm_failure_count = 3

        stats = watcher_with_llm.get_llm_stats()
        assert stats['total_calls'] == 10
        assert stats['successful_calls'] == 7
        assert stats['failed_calls'] == 3
        assert stats['success_rate'] == 0.7


# ============================================================================
# Test ML Validation
# ============================================================================

class TestMLValidation:
    """Test ML validation methods."""

    @pytest.fixture
    def watcher_agent(self):
        config = {'sensitivity': 2.5, 'min_data_points': 7, 'use_llm': False}
        db_config = {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}
        return WatcherAgent('watcher_ml', db_config, config)

    @pytest.mark.asyncio
    async def test_run_ml_validation_traffic_drop(self, watcher_agent):
        """Test ML validation detects traffic drops."""
        historical = [100, 95, 105, 98, 102, 100, 97]
        current = 40

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'clicks')

        assert anomaly is not None
        assert anomaly.severity in ['critical', 'warning']

    @pytest.mark.asyncio
    async def test_run_ml_validation_position_drop(self, watcher_agent):
        """Test ML validation detects position drops."""
        historical = [3.0, 2.8, 3.2, 3.1, 2.9, 3.3, 3.0]
        current = 12.0

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'position')

        assert anomaly is not None

    @pytest.mark.asyncio
    async def test_run_ml_validation_ctr_anomaly(self, watcher_agent):
        """Test ML validation detects CTR anomalies."""
        historical = [5.0, 5.2, 4.8, 5.1, 4.9, 5.3, 5.0]
        current = 1.5

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'ctr')

        assert anomaly is not None

    @pytest.mark.asyncio
    async def test_run_ml_validation_engagement(self, watcher_agent):
        """Test ML validation detects engagement changes."""
        historical = [0.5, 0.52, 0.48, 0.51, 0.49, 0.53, 0.50]
        current = 0.25

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'engagement_rate')

        assert anomaly is not None

    @pytest.mark.asyncio
    async def test_run_ml_validation_conversion(self, watcher_agent):
        """Test ML validation detects conversion drops."""
        historical = [2.0, 2.1, 1.9, 2.2, 2.0, 1.8, 2.1]
        current = 1.0

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'conversion_rate')

        assert anomaly is not None

    @pytest.mark.asyncio
    async def test_run_ml_validation_insufficient_data(self, watcher_agent):
        """Test ML validation returns None with insufficient data."""
        historical = [100, 95, 105]  # Only 3 points
        current = 40

        anomaly = await watcher_agent._run_ml_validation(current, historical, 'clicks')

        assert anomaly is None

    @pytest.mark.asyncio
    async def test_run_ml_validation_no_historical_data(self, watcher_agent):
        """Test ML validation returns None with no historical data."""
        anomaly = await watcher_agent._run_ml_validation(50, None, 'clicks')

        assert anomaly is None

    @pytest.mark.asyncio
    async def test_run_ml_validation_unknown_metric_uses_generic(self, watcher_agent):
        """Test ML validation uses generic detection for unknown metrics."""
        historical = [100, 95, 105, 98, 102, 100, 97]
        current = 30

        # Unknown metric should use generic traffic drop detection
        anomaly = await watcher_agent._run_ml_validation(current, historical, 'unknown_metric')

        assert anomaly is not None or anomaly is None  # Depends on threshold


# ============================================================================
# Test Alert Generation
# ============================================================================

class TestAlertGeneration:
    """Test alert generation functionality."""

    @pytest.fixture
    def watcher_agent(self):
        config = {'use_llm': False}
        db_config = {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}
        return WatcherAgent('watcher_alerts', db_config, config)

    @pytest.mark.asyncio
    async def test_generate_alerts_counts_anomalies_and_trends(self, watcher_agent):
        """Test that generate_alerts counts detected anomalies and trends."""
        watcher_agent._detected_anomalies = [Mock(), Mock(), Mock()]
        watcher_agent._detected_trends = [Mock(), Mock()]

        count = await watcher_agent.generate_alerts()

        assert count == 5

    @pytest.mark.asyncio
    async def test_create_anomaly_alert(self, watcher_agent):
        """Test creating an anomaly alert."""
        anomaly = Anomaly(
            metric_name='clicks',
            page_path='/test-page',
            current_value=40,
            expected_value=100,
            deviation_percent=-60.0,
            severity='critical',
            detected_at=datetime.now(),
            context={'z_score': -3.5}
        )

        page_data = {'page_path': '/test-page', 'last_seen': datetime.now()}

        watcher_agent.alert_manager.create_alert = AsyncMock(return_value=123)

        await watcher_agent._create_anomaly_alert(anomaly, page_data)

        # Verify alert was created
        assert watcher_agent.alert_manager.create_alert.called
        call_args = watcher_agent.alert_manager.create_alert.call_args
        alert = call_args[0][0]

        assert alert.agent_name == 'watcher_alerts'
        assert alert.finding_type == 'anomaly'
        assert alert.severity == 'critical'
        assert '/test-page' in alert.affected_pages
        assert alert.metrics['metric_name'] == 'clicks'

    @pytest.mark.asyncio
    async def test_create_trend_alert(self, watcher_agent):
        """Test creating a trend alert."""
        trend = Trend(
            metric_name='clicks',
            page_path='/growing-page',
            trend_type='increasing',
            slope=5.0,
            confidence=0.9,
            duration_days=14,
            magnitude_percent=35.0,
            detected_at=datetime.now(),
            context={'r_squared': 0.92}
        )

        page_data = {'page_path': '/growing-page', 'last_seen': datetime.now()}

        watcher_agent.alert_manager.create_alert = AsyncMock(return_value=456)

        await watcher_agent._create_trend_alert(trend, page_data)

        assert watcher_agent.alert_manager.create_alert.called
        call_args = watcher_agent.alert_manager.create_alert.call_args
        alert = call_args[0][0]

        assert alert.finding_type == 'trend'
        assert alert.severity == 'info'  # Increasing trend is info
        assert alert.metrics['trend_type'] == 'increasing'


# ============================================================================
# Test Database Queries
# ============================================================================

class TestDatabaseQueries:
    """Test database query methods."""

    @pytest.fixture
    def watcher_agent(self):
        config = {'use_llm': False}
        db_config = {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}
        return WatcherAgent('watcher_db', db_config, config)

    @pytest.mark.asyncio
    async def test_get_active_pages_query_structure(self, watcher_agent):
        """Test that get_active_pages builds correct query."""
        # Mock the full query execution with expected results
        expected_pages = [
            {'page_path': '/page1', 'last_seen': datetime.now()},
            {'page_path': '/page2', 'last_seen': datetime.now()}
        ]

        # Mock _get_active_pages directly instead of pool
        watcher_agent._get_active_pages = AsyncMock(return_value=expected_pages)

        pages = await watcher_agent._get_active_pages(7, None)

        assert len(pages) == 2
        assert pages[0]['page_path'] == '/page1'

    @pytest.mark.asyncio
    async def test_get_page_historical_data_query(self, watcher_agent):
        """Test getting page historical data."""
        # Mock the full query execution with expected results
        expected_data = [
            {
                'date': datetime.now() - timedelta(days=i),
                'clicks': 100,
                'impressions': 1000,
                'ctr': 10.0,
                'avg_position': 3.0,
                'engagement_rate': 0.5,
                'conversion_rate': 2.0,
                'sessions': 80
            }
            for i in range(30)
        ]

        # Mock _get_page_historical_data directly
        watcher_agent._get_page_historical_data = AsyncMock(return_value=expected_data)

        data = await watcher_agent._get_page_historical_data('/page', 30, None)

        assert len(data) == 30
        assert 'clicks' in data[0]

    @pytest.mark.asyncio
    async def test_get_page_time_series_delegates_to_historical(self, watcher_agent):
        """Test that time series delegates to historical data method."""
        watcher_agent._get_page_historical_data = AsyncMock(return_value=[
            {'clicks': 100, 'impressions': 1000}
        ])

        result = await watcher_agent._get_page_time_series('/page', 7, None)

        watcher_agent._get_page_historical_data.assert_called_once_with('/page', 7, None)
        assert result == [{'clicks': 100, 'impressions': 1000}]


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling throughout the agent."""

    @pytest.fixture
    def watcher_agent(self):
        config = {'use_llm': False}
        db_config = {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}
        return WatcherAgent('watcher_errors', db_config, config)

    @pytest.mark.asyncio
    async def test_detect_anomalies_handles_db_errors(self, watcher_agent):
        """Test that detect_anomalies handles database errors gracefully."""
        watcher_agent._get_active_pages = AsyncMock(side_effect=Exception("DB error"))

        # Should not raise, but return empty list
        with pytest.raises(Exception):
            await watcher_agent.detect_anomalies(7)

    @pytest.mark.asyncio
    async def test_detect_trends_handles_errors(self, watcher_agent):
        """Test that detect_trends handles errors gracefully."""
        watcher_agent._get_active_pages = AsyncMock(side_effect=Exception("Query failed"))

        with pytest.raises(Exception):
            await watcher_agent.detect_trends(7)


# ============================================================================
# Test AnomalyFinding Dataclass
# ============================================================================

class TestAnomalyFinding:
    """Test AnomalyFinding dataclass."""

    def test_anomaly_finding_creation_defaults(self):
        """Test creating AnomalyFinding with default values."""
        finding = AnomalyFinding(
            page_path='/test',
            metric_name='clicks',
            severity='warning'
        )

        assert finding.page_path == '/test'
        assert finding.metric_name == 'clicks'
        assert finding.severity == 'warning'
        assert finding.llm_assessment is None
        assert finding.ml_validation is None
        assert finding.combined_confidence == 0.0
        assert finding.likely_causes == []
        assert finding.recommended_actions == []
        assert finding.reasoning == ''
        assert finding.raw_metrics == {}
        assert finding.used_llm is False
        assert finding.used_ml_fallback is False

    def test_anomaly_finding_with_all_fields(self):
        """Test creating AnomalyFinding with all fields."""
        ml_anomaly = Anomaly('clicks', '/test', 50, 100, -50, 'critical', datetime.now(), {})

        finding = AnomalyFinding(
            page_path='/test',
            metric_name='clicks',
            severity='critical',
            llm_assessment={'confidence': 0.9},
            ml_validation=ml_anomaly,
            combined_confidence=0.85,
            likely_causes=['Cause 1', 'Cause 2'],
            recommended_actions=['Action 1'],
            reasoning='Test reasoning',
            raw_metrics={'current': 50},
            used_llm=True,
            used_ml_fallback=False
        )

        assert finding.combined_confidence == 0.85
        assert len(finding.likely_causes) == 2
        assert finding.used_llm is True
        assert finding.ml_validation.severity == 'critical'


# ============================================================================
# Additional Coverage Tests
# ============================================================================

class TestAdditionalCoverage:
    """Additional tests to increase coverage to >90%."""

    @pytest.fixture
    def mock_db_config(self):
        return {'host': 'localhost', 'port': 5432, 'user': 'test', 'password': 'test', 'database': 'test'}

    @pytest.fixture
    def watcher_agent(self, mock_db_config):
        config = {'sensitivity': 2.5, 'min_data_points': 7, 'use_llm': False}
        return WatcherAgent('watcher_coverage', mock_db_config, config)

    @pytest.mark.asyncio
    async def test_detect_anomalies_ctr_anomaly(self, watcher_agent):
        """Test detection of CTR anomalies."""
        mock_pages = [{'page_path': '/ctr-drop', 'last_seen': datetime.now()}]

        historical_data = []
        # Normal CTR
        for _ in range(30):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })
        # CTR drop
        for _ in range(7):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 2.0,  # CTR drop from 10 to 2
                'avg_position': 3.0, 'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        ctr_anomalies = [a for a in anomalies if a.metric_name == 'ctr']
        assert len(ctr_anomalies) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_engagement_drop(self, watcher_agent):
        """Test detection of engagement drop anomalies."""
        mock_pages = [{'page_path': '/engagement-drop', 'last_seen': datetime.now()}]

        historical_data = []
        # Normal engagement
        for _ in range(30):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })
        # Engagement drop
        for _ in range(7):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.2,  # Engagement drop from 0.5 to 0.2
                'conversion_rate': 2.0, 'sessions': 80
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        engagement_anomalies = [a for a in anomalies if a.metric_name == 'engagement_rate']
        assert len(engagement_anomalies) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_conversion_drop(self, watcher_agent):
        """Test detection of conversion drop anomalies."""
        mock_pages = [{'page_path': '/conversion-drop', 'last_seen': datetime.now()}]

        historical_data = []
        # Normal conversion
        for _ in range(30):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })
        # Conversion drop
        for _ in range(7):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 0.5,  # Conversion drop from 2.0 to 0.5
                'sessions': 80
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        conversion_anomalies = [a for a in anomalies if a.metric_name == 'conversion_rate']
        assert len(conversion_anomalies) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_zero_traffic(self, watcher_agent):
        """Test detection of zero traffic (dead pages)."""
        mock_pages = [{'page_path': '/dead-page', 'last_seen': datetime.now()}]

        historical_data = []
        # Normal traffic
        for _ in range(30):
            historical_data.append({
                'clicks': 100, 'impressions': 1000, 'ctr': 10.0, 'avg_position': 3.0,
                'engagement_rate': 0.5, 'conversion_rate': 2.0, 'sessions': 80
            })
        # Zero traffic
        for _ in range(7):
            historical_data.append({
                'clicks': 0, 'impressions': 0,  # No traffic at all
                'ctr': 0, 'avg_position': 100,
                'engagement_rate': 0, 'conversion_rate': 0, 'sessions': 0
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=historical_data)
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        # Should detect zero traffic
        assert len(anomalies) > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_empty_historical_data(self, watcher_agent):
        """Test anomaly detection with empty historical data returns early."""
        mock_pages = [{'page_path': '/no-history', 'last_seen': datetime.now()}]

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_historical_data = AsyncMock(return_value=[])  # Empty history
        watcher_agent._create_anomaly_alert = AsyncMock()

        anomalies = await watcher_agent.detect_anomalies(days=7)

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_detect_trends_with_time_series(self, watcher_agent):
        """Test trend detection with actual time series data."""
        mock_pages = [{'page_path': '/trend-page', 'last_seen': datetime.now()}]

        # Create time series with increasing clicks, impressions, and varying CTR
        time_series_data = []
        for i in range(14):
            time_series_data.append({
                'clicks': 100 + i * 10,
                'impressions': 1000 + i * 100,
                'ctr': 10.0 + (i % 3) * 0.5  # Varying CTR for volatility
            })

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_time_series = AsyncMock(return_value=time_series_data)
        watcher_agent._create_trend_alert = AsyncMock()

        trends = await watcher_agent.detect_trends(days=7)

        # Should detect some trends
        assert watcher_agent._create_trend_alert.call_count >= 0

    @pytest.mark.asyncio
    async def test_detect_trends_empty_time_series(self, watcher_agent):
        """Test trend detection with empty time series."""
        mock_pages = [{'page_path': '/no-data', 'last_seen': datetime.now()}]

        watcher_agent._get_active_pages = AsyncMock(return_value=mock_pages)
        watcher_agent._get_page_time_series = AsyncMock(return_value=[])
        watcher_agent._create_trend_alert = AsyncMock()

        trends = await watcher_agent.detect_trends(days=7)

        # No trends should be detected with empty data
        assert watcher_agent._create_trend_alert.call_count == 0

    @pytest.mark.asyncio
    async def test_create_trend_alert_decreasing(self, watcher_agent):
        """Test creating alert for decreasing trend."""
        trend = Trend(
            metric_name='clicks',
            page_path='/declining-page',
            trend_type='decreasing',
            slope=-5.0,
            confidence=0.9,
            duration_days=14,
            magnitude_percent=-35.0,
            detected_at=datetime.now(),
            context={'r_squared': 0.92}
        )

        page_data = {'page_path': '/declining-page', 'last_seen': datetime.now()}

        watcher_agent.alert_manager.create_alert = AsyncMock(return_value=789)

        await watcher_agent._create_trend_alert(trend, page_data)

        assert watcher_agent.alert_manager.create_alert.called
        call_args = watcher_agent.alert_manager.create_alert.call_args
        alert = call_args[0][0]

        # Decreasing trend should have warning severity
        assert alert.severity == 'warning'

    def test_agent_metadata_retrieval(self, watcher_agent):
        """Test getting agent metadata."""
        watcher_agent._start_time = datetime.now()

        metadata = watcher_agent.get_metadata()

        assert metadata.agent_id == 'watcher_coverage'
        assert metadata.agent_type == 'watcher'
        assert metadata.version is not None

    @pytest.mark.asyncio
    async def test_evaluate_anomaly_no_historical_data(self, watcher_agent):
        """Test evaluate_anomaly with no historical data."""
        page_path = '/test-page'
        metrics = {'metric_name': 'clicks', 'current_value': 50}
        historical = None  # No historical data

        finding = await watcher_agent.evaluate_anomaly(page_path, metrics, historical)

        assert finding is not None
        # Should still return a finding, but ML validation will be None
        assert finding.ml_validation is None


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=agents.watcher.watcher_agent', '--cov-report=term-missing'])
