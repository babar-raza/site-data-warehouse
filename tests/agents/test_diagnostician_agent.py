"""Comprehensive tests for DiagnosticianAgent.

This module tests all aspects of the DiagnosticianAgent including:
- Root cause analysis
- Correlation engine
- Issue classification
- LLM integration
- Rule-based fallback
- Hybrid diagnosis approach
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.diagnostician.correlation_engine import Correlation, CorrelationEngine
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent, DiagnosticResult
from agents.diagnostician.issue_classifier import IssueClassification, IssueClassifier
from agents.diagnostician.root_cause_analyzer import RootCause, RootCauseAnalyzer
from agents.base.llm_reasoner import ReasoningResult


# ============================================================================
# RootCauseAnalyzer Tests
# ============================================================================

class TestRootCauseAnalyzer:
    """Test root cause analyzer functionality."""

    def test_single_root_cause_position_drop(self):
        """Test detection of single root cause: position drop."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'position_drop'
        assert root_cause.confidence > 0.6
        assert len(root_cause.recommendations) > 0
        assert root_cause.severity == 'high'

    def test_single_root_cause_ctr_decline(self):
        """Test detection of single root cause: CTR decline."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'clicks': 50,
            'avg_position': 5.0,
            'ctr': 2.0
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'ctr_decline'
        assert root_cause.confidence >= 0.65
        assert len(root_cause.recommendations) > 0
        assert root_cause.severity == 'medium'

    def test_multiple_root_causes_prioritization(self):
        """Test identification and prioritization of multiple root causes."""
        analyzer = RootCauseAnalyzer()

        # Scenario with both position drop AND CTR decline
        current_metrics = {
            'clicks': 30,
            'avg_position': 15.0,  # Significant position drop
            'ctr': 2.0,  # Significant CTR decline
            'impressions': 1000
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0, 'impressions': 2000}
            for _ in range(10)
        ]

        # The analyzer should identify position drop as higher priority
        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause is not None
        # Should return the highest confidence cause (position_drop has higher confidence)
        assert root_cause.cause_type in ['position_drop', 'ctr_decline']
        assert root_cause.confidence >= 0.6

    def test_no_diagnosis_insufficient_data(self):
        """Test scenario where no diagnosis can be made due to insufficient data."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'clicks': 100,
            'avg_position': 5.0,
            'ctr': 5.0
        }

        # Empty historical data
        historical_metrics = []

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Should return None when no historical data
        assert root_cause is None

    def test_no_diagnosis_no_significant_change(self):
        """Test scenario where metrics are stable with no significant issues."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'clicks': 100,
            'avg_position': 5.0,
            'ctr': 5.0
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # No significant changes detected
        assert root_cause is None

    def test_cascading_issues_engagement_to_conversion(self):
        """Test detection of cascading issues: engagement affects conversion."""
        analyzer = RootCauseAnalyzer()

        # High bounce rate causing low engagement causing low conversion
        current_metrics = {
            'bounce_rate': 0.8,
            'engagement_rate': 0.2,
            'conversion_rate': 0.3,
            'avg_session_duration': 30
        }

        historical_metrics = [
            {
                'bounce_rate': 0.5,
                'engagement_rate': 0.6,
                'conversion_rate': 2.0,
                'avg_session_duration': 120
            }
            for _ in range(10)
        ]

        # First, detect engagement issue
        engagement_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics
        )

        assert engagement_cause is not None
        assert engagement_cause.cause_type == 'high_bounce_rate'
        assert engagement_cause.severity == 'high'

        # Then detect conversion issue
        conversion_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics
        )

        assert conversion_cause is not None
        # Low engagement should lead to traffic quality issue diagnosis
        assert conversion_cause.cause_type == 'traffic_quality_issue'

    def test_analyze_engagement_high_bounce(self):
        """Test detection of high bounce rate issues."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'bounce_rate': 0.8,
            'engagement_rate': 0.2
        }

        historical_metrics = [
            {'bounce_rate': 0.5, 'engagement_rate': 0.5}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'high_bounce_rate'
        assert root_cause.severity == 'high'
        assert root_cause.confidence >= 0.6

    def test_analyze_engagement_low_engagement(self):
        """Test detection of low engagement rate."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'engagement_rate': 0.2,
            'avg_session_duration': 30
        }

        historical_metrics = [
            {'engagement_rate': 0.6, 'avg_session_duration': 120}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics
        )

        assert root_cause is not None
        assert 'engagement' in root_cause.cause_type.lower()

    def test_analyze_conversion_funnel_blocker(self):
        """Test detection of conversion funnel issues."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'conversion_rate': 0.5,
            'engagement_rate': 0.7  # High engagement but low conversion
        }

        historical_metrics = [
            {'conversion_rate': 2.0, 'engagement_rate': 0.7}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'conversion_funnel_blocker'
        assert root_cause.severity == 'high'
        assert root_cause.confidence == 0.8

    def test_analyze_conversion_traffic_quality(self):
        """Test detection of traffic quality issues."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'conversion_rate': 0.5,
            'engagement_rate': 0.3  # Low engagement and low conversion
        }

        historical_metrics = [
            {'conversion_rate': 2.0, 'engagement_rate': 0.6}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'traffic_quality_issue'
        assert root_cause.confidence == 0.75

    def test_analyze_technical_deindexing(self):
        """Test detection of deindexing or penalty."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'impressions': 0,
            'clicks': 0
        }

        root_cause = analyzer.analyze_technical_issue(current_metrics)

        assert root_cause is not None
        assert root_cause.cause_type == 'deindexing_or_penalty'
        assert root_cause.severity == 'critical'
        assert root_cause.confidence >= 0.9

    def test_detect_cannibalization(self):
        """Test content cannibalization detection."""
        analyzer = RootCauseAnalyzer()

        page_path = '/main-page'
        similar_pages = [
            {'page_path': '/similar-1'},
            {'page_path': '/similar-2'},
            {'page_path': '/similar-3'}
        ]
        shared_keywords = ['keyword1', 'keyword2', 'keyword3', 'keyword4', 'keyword5']

        root_cause = analyzer.detect_cannibalization(
            page_path,
            similar_pages,
            shared_keywords
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'content_cannibalization'
        assert len(root_cause.recommendations) > 0
        assert root_cause.confidence > 0.6

    def test_analyze_competitor_impact(self):
        """Test competitor impact analysis."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'impressions': 500,
            'avg_position': 5.0
        }

        historical_metrics = [
            {'impressions': 1000, 'avg_position': 5.0}
            for _ in range(10)
        ]

        root_cause = analyzer.analyze_competitor_impact(
            current_metrics,
            historical_metrics
        )

        assert root_cause is not None
        assert 'competitor' in root_cause.cause_type.lower()
        assert root_cause.confidence == 0.7


# ============================================================================
# CorrelationEngine Tests
# ============================================================================

class TestCorrelationEngine:
    """Test correlation engine functionality."""

    def test_calculate_correlation_strong_positive(self):
        """Test calculation of strong positive correlation."""
        engine = CorrelationEngine()

        series1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        series2 = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]

        corr = engine.calculate_correlation(series1, series2)

        assert corr is not None
        assert corr.correlation_coefficient > 0.9
        assert corr.direction == 'positive'
        assert corr.strength == 'strong'

    def test_calculate_correlation_strong_negative(self):
        """Test calculation of strong negative correlation."""
        engine = CorrelationEngine()

        series1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        series2 = [20, 18, 16, 14, 12, 10, 8, 6, 4, 2]

        corr = engine.calculate_correlation(series1, series2)

        assert corr is not None
        assert corr.correlation_coefficient < -0.9
        assert corr.direction == 'negative'
        assert corr.strength == 'strong'

    def test_find_correlations(self):
        """Test finding correlations between multiple metrics."""
        engine = CorrelationEngine()

        metric_data = {
            'clicks': [10, 15, 20, 25, 30],
            'impressions': [100, 150, 200, 250, 300],
            'ctr': [10, 10, 10, 10, 10]  # Constant
        }

        correlations = engine.find_correlations(metric_data)

        # Should find correlation between clicks and impressions
        assert len(correlations) >= 1

        # Find the clicks-impressions correlation
        clicks_impressions = [c for c in correlations if
                             'clicks' in [c.metric1, c.metric2] and
                             'impressions' in [c.metric1, c.metric2]]

        assert len(clicks_impressions) > 0
        assert clicks_impressions[0].strength in ['strong', 'moderate']

    def test_detect_leading_indicator(self):
        """Test detection of leading indicators."""
        engine = CorrelationEngine()

        # Create lagged relationship (leading predicts lagging after 2 days)
        leading_series = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        lagging_series = [0, 0, 1, 2, 3, 4, 5, 6, 7, 8]  # Lags by 2

        result = engine.detect_leading_indicator(leading_series, lagging_series, max_lag=5)

        assert result is not None
        lag, correlation = result
        assert lag >= 1  # Should detect some lag
        assert abs(correlation) > 0.5

    def test_analyze_metric_impact(self):
        """Test metric impact analysis."""
        engine = CorrelationEngine()

        # Position worsens, clicks drop
        independent = [3, 3, 3, 8, 8, 8]  # Position gets worse
        dependent = [100, 100, 100, 50, 50, 50]  # Clicks drop

        impact = engine.analyze_metric_impact(independent, dependent, change_threshold=0.3)

        assert impact is not None
        assert impact['impact_count'] > 0
        assert 'average_impact_ratio' in impact


# ============================================================================
# IssueClassifier Tests
# ============================================================================

class TestIssueClassifier:
    """Test issue classifier functionality."""

    def test_classify_technical_issue(self):
        """Test classification of technical issues."""
        classifier = IssueClassifier()

        classification = classifier.classify_issue(
            'deindexing_or_penalty',
            {'impressions': 0, 'clicks': 5000},  # High clicks to increase impact
            {'zero_impressions': True, 'deviation_percent': 100}
        )

        assert classification.category == 'technical_seo'
        assert classification.subcategory == 'indexing'
        assert classification.urgency_score >= 9.0
        # Priority can be critical, high, or medium depending on combined score
        assert classification.priority in ['critical', 'high', 'medium']

    def test_classify_content_issue(self):
        """Test classification of content issues."""
        classifier = IssueClassifier()

        classification = classifier.classify_issue(
            'content_cannibalization',
            {'clicks': 500},
            {'similar_pages_count': 5}
        )

        assert classification.category == 'content'
        assert classification.subcategory == 'cannibalization'
        assert len(classification.tags) > 0

    def test_classify_onpage_issue(self):
        """Test classification of on-page issues."""
        classifier = IssueClassifier()

        classification = classifier.classify_issue(
            'ctr_decline',
            {'ctr': 2.0, 'clicks': 200},
            {'ctr_drop_percent': 40}
        )

        assert classification.category == 'on_page'
        assert classification.subcategory == 'title_optimization'

    def test_priority_calculation(self):
        """Test priority calculation based on impact and urgency."""
        classifier = IssueClassifier()

        classification = classifier.classify_issue(
            'deindexing_or_penalty',
            {'clicks': 5000, 'impressions': 10000},
            {'deviation_percent': 90}
        )

        assert classification.priority in ['critical', 'high']
        assert classification.impact_score > 5.0

    def test_prioritize_issues(self):
        """Test prioritization of multiple issues."""
        classifier = IssueClassifier()

        classifications = [
            classifier.classify_issue('seasonality', {'clicks': 100}, {'deviation_percent': 20}),
            classifier.classify_issue('deindexing_or_penalty', {'clicks': 1000, 'impressions': 2000}, {'deviation_percent': 100}),
            classifier.classify_issue('ctr_decline', {'clicks': 500}, {'deviation_percent': 40})
        ]

        prioritized = classifier.prioritize_issues(classifications)

        # Deindexing should be highest priority
        assert prioritized[0].category == 'technical_seo' or prioritized[0].urgency_score >= 8.0

    def test_identify_quick_wins(self):
        """Test identification of quick win opportunities."""
        classifier = IssueClassifier()

        classifications = [
            classifier.classify_issue('ctr_decline', {'clicks': 1000}, {'deviation_percent': 40}),
            classifier.classify_issue('slow_page_load', {'clicks': 500}, {}),
            classifier.classify_issue('seasonality', {'clicks': 100}, {})
        ]

        quick_wins = classifier.get_quick_wins(classifications)

        # May or may not find quick wins
        assert isinstance(quick_wins, list)


# ============================================================================
# DiagnosticianAgent Tests
# ============================================================================

class TestDiagnosticianAgent:
    """Test DiagnosticianAgent core functionality."""

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
            'min_confidence': 0.6,
            'min_correlation': 0.5,
            'use_llm': False  # Disable LLM for basic tests
        }

    @pytest.fixture
    def diagnostician_agent(self, mock_db_config, mock_config):
        """Create diagnostician agent with mock config."""
        return DiagnosticianAgent(
            agent_id='diagnostician_test_001',
            db_config=mock_db_config,
            config=mock_config
        )

    def test_diagnostician_agent_creation(self, diagnostician_agent):
        """Test diagnostician agent creation."""
        assert diagnostician_agent.agent_id == 'diagnostician_test_001'
        assert diagnostician_agent.agent_type == 'diagnostician'
        assert diagnostician_agent.root_cause_analyzer is not None
        assert diagnostician_agent.correlation_engine is not None
        assert diagnostician_agent.issue_classifier is not None

    @pytest.mark.asyncio
    async def test_diagnostician_agent_initialization(self, diagnostician_agent):
        """Test diagnostician agent initialization with mocked database."""
        async def mock_create_pool(**kwargs):
            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            return mock_pool

        with patch('asyncpg.create_pool', side_effect=mock_create_pool):
            success = await diagnostician_agent.initialize()
            assert success is True

    @pytest.mark.asyncio
    async def test_diagnostician_agent_process_finding(self, diagnostician_agent):
        """Test diagnostician agent processing a finding."""
        diagnostician_agent._pool = MagicMock()
        diagnostician_agent.analyze_finding = AsyncMock(return_value={
            'diagnosis_id': 1,
            'root_cause': 'position_drop',
            'confidence': 0.85
        })

        result = await diagnostician_agent.process({'finding_id': 123})

        assert result['status'] == 'success'
        assert 'diagnosis' in result
        assert result['diagnosis']['root_cause'] == 'position_drop'

    @pytest.mark.asyncio
    async def test_diagnostician_agent_process_page_path(self, diagnostician_agent):
        """Test diagnostician agent processing a page path report."""
        diagnostician_agent._pool = MagicMock()
        diagnostician_agent.generate_report = AsyncMock(return_value={
            'page_path': '/test-page',
            'findings_analyzed': 3,
            'diagnoses_generated': 3
        })

        result = await diagnostician_agent.process({'page_path': '/test-page'})

        assert result['status'] == 'success'
        assert 'report' in result
        assert result['report']['page_path'] == '/test-page'

    @pytest.mark.asyncio
    async def test_diagnostician_agent_process_missing_params(self, diagnostician_agent):
        """Test diagnostician agent with missing parameters."""
        result = await diagnostician_agent.process({})

        assert result['status'] == 'error'
        assert 'Missing finding_id or page_path' in result['error']


# ============================================================================
# LLM Integration Tests
# ============================================================================

class TestDiagnosticianAgentLLMIntegration:
    """Test LLM integration in DiagnosticianAgent."""

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
    def config_with_llm(self):
        """Configuration with LLM enabled."""
        return {
            'min_confidence': 0.6,
            'min_correlation': 0.5,
            'use_llm': True,
            'llm_timeout': 30.0,
            'llm_retries': 1
        }

    @pytest.fixture
    def config_without_llm(self):
        """Configuration with LLM disabled."""
        return {
            'min_confidence': 0.6,
            'min_correlation': 0.5,
            'use_llm': False
        }

    @pytest.fixture
    def diagnostician_with_llm(self, mock_db_config, config_with_llm):
        """Create diagnostician agent with LLM enabled."""
        return DiagnosticianAgent(
            agent_id='diagnostician_llm_test',
            db_config=mock_db_config,
            config=config_with_llm
        )

    @pytest.fixture
    def diagnostician_without_llm(self, mock_db_config, config_without_llm):
        """Create diagnostician agent with LLM disabled."""
        return DiagnosticianAgent(
            agent_id='diagnostician_no_llm_test',
            db_config=mock_db_config,
            config=config_without_llm
        )

    def test_llm_reasoning_initialization(self, diagnostician_with_llm):
        """Test that LLM components are initialized when enabled."""
        assert diagnostician_with_llm.use_llm is True
        assert diagnostician_with_llm.llm_reasoner is not None
        assert diagnostician_with_llm._llm_call_count == 0
        assert diagnostician_with_llm._llm_success_count == 0
        assert diagnostician_with_llm._llm_failure_count == 0

    def test_llm_disabled_no_initialization(self, diagnostician_without_llm):
        """Test that LLM components are not initialized when disabled."""
        assert diagnostician_without_llm.use_llm is False
        assert diagnostician_without_llm.llm_reasoner is None

    def test_confidence_weights(self, diagnostician_with_llm):
        """Test that confidence weights are set correctly."""
        assert diagnostician_with_llm.LLM_CONFIDENCE_WEIGHT == 0.6
        assert diagnostician_with_llm.RULE_CONFIDENCE_WEIGHT == 0.4
        total_weight = diagnostician_with_llm.LLM_CONFIDENCE_WEIGHT + diagnostician_with_llm.RULE_CONFIDENCE_WEIGHT
        assert total_weight == 1.0

    def test_get_llm_stats_initial(self, diagnostician_with_llm):
        """Test initial LLM stats."""
        stats = diagnostician_with_llm.get_llm_stats()

        assert stats['total_calls'] == 0
        assert stats['successful_calls'] == 0
        assert stats['failed_calls'] == 0
        assert stats['success_rate'] == 0.0
        assert stats['llm_enabled'] is True
        assert stats['diagnostic_results_count'] == 0

    def test_get_llm_stats_disabled(self, diagnostician_without_llm):
        """Test LLM stats when LLM is disabled."""
        stats = diagnostician_without_llm.get_llm_stats()
        assert stats['llm_enabled'] is False

    @pytest.mark.asyncio
    async def test_rule_based_fallback_traffic(self, diagnostician_with_llm):
        """Test rule-based analysis for traffic issues."""
        finding = {
            'finding_type': 'anomaly',
            'metrics': json.dumps({'metric_name': 'clicks'})
        }
        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0
        }
        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        root_cause = await diagnostician_with_llm._run_rule_based_analysis(
            finding, current_metrics, historical_metrics
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'position_drop'

    @pytest.mark.asyncio
    async def test_rule_based_fallback_engagement(self, diagnostician_with_llm):
        """Test rule-based analysis for engagement issues."""
        finding = {
            'finding_type': 'anomaly',
            'metrics': json.dumps({'metric_name': 'engagement_rate'})
        }
        current_metrics = {
            'bounce_rate': 0.8,
            'engagement_rate': 0.2
        }
        historical_metrics = [
            {'bounce_rate': 0.5, 'engagement_rate': 0.5}
            for _ in range(10)
        ]

        root_cause = await diagnostician_with_llm._run_rule_based_analysis(
            finding, current_metrics, historical_metrics
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'high_bounce_rate'

    @pytest.mark.asyncio
    async def test_llm_diagnosis_disabled(self, diagnostician_without_llm):
        """Test that LLM diagnosis returns None when disabled."""
        finding = {'finding_type': 'anomaly', 'metrics': '{}', 'affected_pages': '[]'}

        result = await diagnostician_without_llm._run_llm_diagnosis(
            finding, {}, [], [], None
        )

        assert result is None

    def test_combine_llm_rule_results(self, diagnostician_with_llm):
        """Test combining LLM and rule-based results."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='unknown',
            confidence=0.0,
            severity='info'
        )

        llm_result = ReasoningResult(
            success=True,
            content={
                'confidence': 0.9,
                'root_cause': 'content_quality_decline',
                'severity': 'high',
                'evidence': ['Traffic dropped'],
                'recommendations': ['Update content']
            },
            raw_response='LLM analysis result'
        )

        rule_analysis = RootCause(
            cause_type='position_drop',
            confidence=0.75,
            severity='warning',
            evidence=['Position moved from 5 to 15'],
            recommendations=['Review content']
        )

        combined = diagnostician_with_llm._combine_llm_rule_results(
            result, llm_result, rule_analysis
        )

        assert combined.root_cause == 'content_quality_decline'  # LLM is primary
        assert combined.confidence > 0.5  # Combined confidence
        assert combined.severity == 'high'  # Higher severity wins

    def test_combine_llm_rule_results_llm_only(self, diagnostician_with_llm):
        """Test combining results when only LLM provides analysis."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='unknown',
            confidence=0.0,
            severity='info'
        )

        llm_result = ReasoningResult(
            success=True,
            content={
                'confidence': 0.85,
                'diagnosis': 'competitor_impact',
                'severity': 'medium'
            },
            raw_response='LLM analysis'
        )

        combined = diagnostician_with_llm._combine_llm_rule_results(
            result, llm_result, None
        )

        assert combined.root_cause == 'competitor_impact'
        expected_confidence = 0.6 * 0.85  # LLM_WEIGHT * LLM_confidence
        assert abs(combined.confidence - expected_confidence) < 0.01

    def test_apply_rule_fallback_with_analysis(self, diagnostician_with_llm):
        """Test rule fallback when rule-based analysis is available."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='unknown',
            confidence=0.0,
            severity='info'
        )

        rule_analysis = RootCause(
            cause_type='ctr_decline',
            confidence=0.8,
            severity='warning',
            evidence=['CTR dropped significantly from 5% to 2%'],
            recommendations=['Optimize meta descriptions']
        )

        fallback = diagnostician_with_llm._apply_rule_fallback(result, rule_analysis)

        assert fallback.root_cause == 'ctr_decline'
        assert fallback.confidence == 0.8
        assert fallback.severity == 'warning'
        assert 'Rule-based diagnosis' in fallback.reasoning

    def test_apply_rule_fallback_no_analysis(self, diagnostician_with_llm):
        """Test rule fallback when no rule-based analysis is available."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='unknown',
            confidence=0.0,
            severity='info'
        )

        fallback = diagnostician_with_llm._apply_rule_fallback(result, None)

        assert fallback.root_cause == 'unknown'
        assert fallback.confidence == 0.0
        assert 'Unable to determine' in fallback.reasoning

    def test_format_evidence_for_llm(self, diagnostician_with_llm):
        """Test evidence formatting for LLM."""
        finding = {'finding_type': 'anomaly', 'metrics': '{}'}
        current_metrics = {'clicks': 30, 'ctr': 1.5}
        historical_metrics = [
            {'clicks': 100, 'ctr': 5.0}
            for _ in range(10)
        ]

        rule_analysis = RootCause(
            cause_type='position_drop',
            confidence=0.8,
            severity='high',
            evidence=['Position worsened significantly'],
            recommendations=['Review content']
        )

        evidence = diagnostician_with_llm._format_evidence_for_llm(
            finding, current_metrics, historical_metrics, [], rule_analysis
        )

        assert 'symptoms' in evidence
        assert 'Clicks down' in evidence['symptoms'] or 'CTR down' in evidence['symptoms']
        assert 'Rule-based analysis suggests' in evidence['symptoms']

    @pytest.mark.asyncio
    async def test_diagnose_with_llm_fallback(self, diagnostician_without_llm):
        """Test diagnose_with_llm falls back to rule-based when LLM is disabled."""
        finding = {
            'finding_type': 'anomaly',
            'metrics': json.dumps({'metric_name': 'clicks'}),
            'affected_pages': '[]'
        }
        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0
        }
        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        result = await diagnostician_without_llm.diagnose_with_llm(
            finding_id=123,
            finding=finding,
            current_metrics=current_metrics,
            historical_metrics=historical_metrics,
            correlations=[]
        )

        assert result is not None
        assert result.used_llm is False
        assert result.used_rule_fallback is True
        assert result.finding_id == 123

    @pytest.mark.asyncio
    async def test_diagnose_with_llm_tracks_results(self, diagnostician_without_llm):
        """Test that diagnose_with_llm tracks diagnostic results."""
        finding = {
            'finding_type': 'anomaly',
            'metrics': json.dumps({'metric_name': 'clicks'}),
            'affected_pages': '[]'
        }
        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0
        }
        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]

        initial_count = len(diagnostician_without_llm._diagnostic_results)

        await diagnostician_without_llm.diagnose_with_llm(
            finding_id=123,
            finding=finding,
            current_metrics=current_metrics,
            historical_metrics=historical_metrics,
            correlations=[]
        )

        assert len(diagnostician_without_llm._diagnostic_results) == initial_count + 1

    @pytest.mark.asyncio
    async def test_health_check_includes_llm_stats(self, diagnostician_with_llm):
        """Test that health check includes LLM stats."""
        from datetime import datetime, timedelta
        diagnostician_with_llm._start_time = datetime.now() - timedelta(hours=1)

        health = await diagnostician_with_llm.health_check()

        assert 'llm_stats' in health.metadata
        assert 'diagnostic_results' in health.metadata
        assert health.metadata['llm_stats']['llm_enabled'] is True


# ============================================================================
# DiagnosticResult Dataclass Tests
# ============================================================================

class TestDiagnosticResult:
    """Test DiagnosticResult dataclass."""

    def test_diagnostic_result_creation(self):
        """Test creating a DiagnosticResult with default values."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='position_drop',
            confidence=0.85,
            severity='high'
        )

        assert result.finding_id == 123
        assert result.root_cause == 'position_drop'
        assert result.confidence == 0.85
        assert result.severity == 'high'
        assert result.llm_analysis is None
        assert result.rule_based_analysis is None
        assert result.evidence == []
        assert result.recommendations == []
        assert result.used_llm is False
        assert result.used_rule_fallback is False

    def test_diagnostic_result_with_llm_analysis(self):
        """Test creating a DiagnosticResult with LLM analysis."""
        result = DiagnosticResult(
            finding_id=123,
            root_cause='content_quality_decline',
            confidence=0.92,
            severity='high',
            llm_analysis={'root_cause': 'content_quality_decline', 'confidence': 0.95},
            evidence=['Traffic down 40%', 'CTR dropped significantly'],
            recommendations=['Update content', 'Improve meta descriptions'],
            reasoning='LLM analysis indicates content quality issues',
            used_llm=True
        )

        assert result.used_llm is True
        assert result.confidence == 0.92
        assert len(result.evidence) == 2
        assert 'Update content' in result.recommendations

    def test_diagnostic_result_with_rule_analysis(self):
        """Test creating a DiagnosticResult with rule-based analysis."""
        rule_cause = RootCause(
            cause_type='position_drop',
            confidence=0.75,
            severity='warning',
            evidence=['Position moved from 5 to 15'],
            recommendations=['Review content quality']
        )

        result = DiagnosticResult(
            finding_id=456,
            root_cause='position_drop',
            confidence=0.75,
            severity='warning',
            rule_based_analysis=rule_cause,
            used_rule_fallback=True
        )

        assert result.rule_based_analysis is not None
        assert result.rule_based_analysis.cause_type == 'position_drop'
        assert result.used_rule_fallback is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for diagnostician system."""

    def test_end_to_end_traffic_drop_diagnosis(self):
        """Test complete diagnosis flow for traffic drop."""
        # Analyze root cause
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0,
            'impressions': 1000
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0, 'impressions': 2000}
            for _ in range(15)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause is not None

        # Classify issue
        classifier = IssueClassifier()
        classification = classifier.classify_issue(
            root_cause.cause_type,
            current_metrics,
            root_cause.evidence
        )

        assert classification is not None
        assert classification.priority in ['critical', 'high', 'medium', 'low']

        # Analyze correlations
        engine = CorrelationEngine()
        metric_data = {
            'clicks': [m['clicks'] for m in historical_metrics],
            'position': [m['avg_position'] for m in historical_metrics]
        }

        correlations = engine.find_correlations(metric_data)

        # Verify complete diagnosis
        assert root_cause.confidence >= 0.6
        assert len(root_cause.recommendations) > 0
        assert classification.impact_score > 0

    def test_diagnosis_accuracy(self):
        """Test diagnostic accuracy on known issues."""
        analyzer = RootCauseAnalyzer()

        # Known scenarios
        scenarios = [
            {
                'current': {'clicks': 50, 'avg_position': 15.0},
                'historical': [{'clicks': 100, 'avg_position': 5.0}] * 10,
                'expected_cause': 'position_drop'
            },
            {
                'current': {'conversion_rate': 0.5, 'engagement_rate': 0.7},
                'historical': [{'conversion_rate': 2.0, 'engagement_rate': 0.7}] * 10,
                'expected_cause': 'conversion_funnel_blocker'
            },
            {
                'current': {'impressions': 0, 'clicks': 0},
                'historical': [{'impressions': 1000, 'clicks': 100}] * 10,
                'expected_cause': 'deindexing_or_penalty'
            }
        ]

        correct = 0
        for scenario in scenarios:
            if scenario['expected_cause'] == 'deindexing_or_penalty':
                root_cause = analyzer.analyze_technical_issue(scenario['current'])
            elif scenario['expected_cause'] == 'conversion_funnel_blocker':
                root_cause = analyzer.analyze_conversion_issue(
                    scenario['current'],
                    scenario['historical']
                )
            else:
                root_cause = analyzer.analyze_traffic_drop(
                    scenario['current'],
                    scenario['historical'],
                    {}
                )

            if root_cause and root_cause.cause_type == scenario['expected_cause']:
                correct += 1

        accuracy = correct / len(scenarios)

        # Should correctly diagnose at least 2 out of 3
        assert accuracy >= 0.66


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
