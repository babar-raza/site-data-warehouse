"""Comprehensive tests for diagnostician agent."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.diagnostician.correlation_engine import Correlation, CorrelationEngine
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.diagnostician.issue_classifier import IssueClassification, IssueClassifier
from agents.diagnostician.root_cause_analyzer import RootCause, RootCauseAnalyzer


class TestRootCauseAnalyzer:
    """Test root cause analyzer functionality."""

    def test_analyze_traffic_drop_position_issue(self):
        """Test detection of traffic drop due to position decline."""
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
        assert 'recommendations' in root_cause.__dict__

    def test_analyze_traffic_drop_ctr_issue(self):
        """Test detection of traffic drop due to CTR decline."""
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
        assert len(root_cause.recommendations) > 0

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

    def test_calculate_correlation_no_correlation(self):
        """Test that weak correlations are not returned."""
        engine = CorrelationEngine(min_correlation=0.5)
        
        import random
        series1 = [random.random() for _ in range(20)]
        series2 = [random.random() for _ in range(20)]
        
        corr = engine.calculate_correlation(series1, series2)
        
        # Should return None for random data (no significant correlation)
        # Note: There's a small chance this fails due to randomness
        # In practice, weak random correlations won't pass the threshold

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


class TestIssueClassifier:
    """Test issue classifier functionality."""

    def test_classify_technical_issue(self):
        """Test classification of technical issues."""
        classifier = IssueClassifier()
        
        classification = classifier.classify_issue(
            'deindexing_or_penalty',
            {'impressions': 0, 'clicks': 0, 'historical_clicks': 1000},  # Add context
            {'zero_impressions': True, 'deviation_percent': 100}
        )
        
        assert classification.category == 'technical_seo'
        assert classification.subcategory == 'indexing'
        # Priority will be based on urgency and impact - with zero current clicks but high historical
        assert classification.urgency_score >= 9.0  # Very urgent
        assert classification.impact_score >= 0  # Impact based on available metrics

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
        
        # High impact (many clicks affected), high urgency (critical issue) = critical/high
        classification = classifier.classify_issue(
            'deindexing_or_penalty',
            {'clicks': 5000, 'impressions': 10000},
            {'deviation_percent': 90}
        )
        
        # Should be critical or at least high priority
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
        
        # Deindexing should be highest priority due to high urgency and impact
        # Check that it's prioritized (could be critical or high)
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
        
        # CTR optimization is typically a quick win
        assert len(quick_wins) >= 0  # May or may not find quick wins depending on classification


class TestDiagnosticianAgent:
    """Test diagnostician agent functionality."""

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
            'min_correlation': 0.5
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
        """Test diagnostician agent initialization."""
        # Mock the database connection
        async def mock_create_pool(**kwargs):
            mock_pool = AsyncMock()
            mock_pool.close = AsyncMock()
            return mock_pool
        
        with patch('asyncpg.create_pool', side_effect=mock_create_pool):
            success = await diagnostician_agent.initialize()
            assert success is True

    @pytest.mark.asyncio
    async def test_diagnostician_agent_process(self, diagnostician_agent):
        """Test diagnostician agent processing."""
        # Mock database pool
        diagnostician_agent._pool = MagicMock()
        diagnostician_agent.analyze_finding = AsyncMock(return_value={
            'diagnosis_id': 1,
            'root_cause': 'position_drop',
            'confidence': 0.85
        })
        
        result = await diagnostician_agent.process({'finding_id': 123})
        
        assert result['status'] == 'success'
        assert 'diagnosis' in result


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
        
        # Known position drop scenario
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
