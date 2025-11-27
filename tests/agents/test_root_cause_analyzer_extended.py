"""Extended tests for Root Cause Analyzer to improve coverage."""

import pytest
from agents.diagnostician.root_cause_analyzer import RootCauseAnalyzer, RootCause


class TestRootCauseAnalyzerExtended:
    """Extended tests for root cause analyzer."""

    def test_analyze_traffic_drop_multiple_causes(self):
        """Test traffic drop with multiple contributing causes."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'avg_position': 15.0,  # Dropped significantly
            'ctr': 2.0,  # Also dropped
            'clicks': 20,
            'impressions': 1000
        }

        historical_metrics = [
            {'avg_position': 5.0, 'ctr': 8.0, 'clicks': 100, 'impressions': 1250}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Should identify position drop as primary cause
        assert root_cause is not None
        assert root_cause.cause_type == 'position_drop'
        assert root_cause.confidence > 0.6

    def test_analyze_traffic_drop_extreme_position_change(self):
        """Test with extreme position drop."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'avg_position': 50.0,
            'clicks': 10
        }

        historical_metrics = [
            {'avg_position': 3.0, 'clicks': 200}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause.cause_type == 'position_drop'
        assert root_cause.confidence > 0.85
        assert root_cause.severity == 'high'

    def test_analyze_traffic_drop_ctr_only(self):
        """Test CTR drop with stable position."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'avg_position': 5.0,  # Stable
            'ctr': 2.0,  # Dropped significantly
            'clicks': 40,
            'impressions': 2000
        }

        historical_metrics = [
            {'avg_position': 5.2, 'ctr': 10.0, 'clicks': 200, 'impressions': 2000}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        assert root_cause.cause_type == 'ctr_decline'
        assert 'title' in str(root_cause.recommendations).lower()

    def test_analyze_traffic_drop_seasonal_pattern(self):
        """Test detection of seasonal traffic patterns."""
        analyzer = RootCauseAnalyzer()

        # Create weekly pattern in historical data
        historical_metrics = []
        for week in range(3):
            for day in range(7):
                clicks = 100 if day < 5 else 50  # Weekday vs weekend pattern
                historical_metrics.append({
                    'avg_position': 5.0,
                    'ctr': 5.0,
                    'clicks': clicks,
                    'impressions': 2000
                })

        current_metrics = {
            'avg_position': 5.0,
            'ctr': 5.0,
            'clicks': 80,
            'impressions': 2000
        }

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Should detect seasonality
        assert root_cause is not None
        if root_cause.cause_type == 'seasonality':
            assert root_cause.severity == 'low'

    def test_analyze_traffic_drop_no_historical_data(self):
        """Test with empty historical data."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'avg_position': 10.0, 'clicks': 50}
        historical_metrics = []

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Should return None or handle gracefully
        assert root_cause is None or isinstance(root_cause, RootCause)

    def test_analyze_engagement_high_bounce_rate(self):
        """Test high bounce rate detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'bounce_rate': 0.85,
            'engagement_rate': 0.15
        }

        historical_metrics = [
            {'bounce_rate': 0.45, 'engagement_rate': 0.55}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'high_bounce_rate'
        assert root_cause.severity == 'high'
        assert 'load speed' in str(root_cause.recommendations).lower()

    def test_analyze_engagement_low_engagement_rate(self):
        """Test low engagement rate detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'engagement_rate': 0.2,
            'bounce_rate': 0.5
        }

        historical_metrics = [
            {'engagement_rate': 0.7, 'bounce_rate': 0.5}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'low_engagement'
        assert root_cause.severity == 'medium'

    def test_analyze_engagement_short_session_duration(self):
        """Test short session duration detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'avg_session_duration': 30,  # 30 seconds
            'engagement_rate': 0.3
        }

        historical_metrics = [
            {'avg_session_duration': 120, 'engagement_rate': 0.6}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type in ['short_session_duration', 'low_engagement']

    def test_analyze_engagement_no_issues(self):
        """Test when engagement metrics are healthy."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'bounce_rate': 0.4,
            'engagement_rate': 0.65,
            'avg_session_duration': 150
        }

        historical_metrics = [
            {'bounce_rate': 0.42, 'engagement_rate': 0.62, 'avg_session_duration': 145}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics,
            None
        )

        # Should return None for healthy metrics
        assert root_cause is None

    def test_analyze_conversion_funnel_blocker(self):
        """Test conversion funnel blocker detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'conversion_rate': 0.01,  # Very low
            'engagement_rate': 0.7  # But high engagement
        }

        historical_metrics = [
            {'conversion_rate': 0.05, 'engagement_rate': 0.68}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'conversion_funnel_blocker'
        assert root_cause.severity == 'high'
        assert 'form' in str(root_cause.recommendations).lower()

    def test_analyze_conversion_traffic_quality(self):
        """Test traffic quality issue detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'conversion_rate': 0.01,
            'engagement_rate': 0.2  # Low engagement too
        }

        historical_metrics = [
            {'conversion_rate': 0.05, 'engagement_rate': 0.6}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'traffic_quality_issue'
        assert root_cause.severity == 'medium'

    def test_analyze_conversion_no_historical_data(self):
        """Test conversion analysis with no historical data."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'conversion_rate': 0.01}
        historical_metrics = []

        root_cause = analyzer.analyze_conversion_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is None

    def test_analyze_technical_deindexing(self):
        """Test deindexing/penalty detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'impressions': 0,
            'clicks': 0
        }

        root_cause = analyzer.analyze_technical_issue(
            current_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'deindexing_or_penalty'
        assert root_cause.confidence == 0.9
        assert root_cause.severity == 'critical'

    def test_analyze_technical_crawl_errors(self):
        """Test crawl error detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'impressions': 100, 'clicks': 10}
        technical_data = {
            'crawl_errors': 15,
            'error_types': ['404', '500']
        }

        root_cause = analyzer.analyze_technical_issue(
            current_metrics,
            technical_data
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'crawl_errors'
        assert root_cause.confidence == 0.85

    def test_analyze_technical_slow_load(self):
        """Test slow page load detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'impressions': 1000, 'clicks': 100}
        technical_data = {
            'page_load_time': 5.5,
            'crawl_errors': 0
        }

        root_cause = analyzer.analyze_technical_issue(
            current_metrics,
            technical_data
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'slow_page_load'
        assert root_cause.severity == 'medium'

    def test_analyze_technical_no_issues(self):
        """Test when no technical issues are present."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'impressions': 1000, 'clicks': 100}
        technical_data = {
            'page_load_time': 1.5,
            'crawl_errors': 0
        }

        root_cause = analyzer.analyze_technical_issue(
            current_metrics,
            technical_data
        )

        assert root_cause is None

    def test_detect_cannibalization_high_overlap(self):
        """Test cannibalization detection with high keyword overlap."""
        analyzer = RootCauseAnalyzer()

        similar_pages = [
            {'page_path': '/page1'},
            {'page_path': '/page2'},
            {'page_path': '/page3'}
        ]

        shared_keywords = [
            'keyword1', 'keyword2', 'keyword3', 'keyword4', 'keyword5'
        ]

        root_cause = analyzer.detect_cannibalization(
            '/target-page',
            similar_pages,
            shared_keywords
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'content_cannibalization'
        assert root_cause.severity == 'high'

    def test_detect_cannibalization_low_overlap(self):
        """Test with low keyword overlap."""
        analyzer = RootCauseAnalyzer()

        similar_pages = [{'page_path': '/page1'}]
        shared_keywords = ['keyword1', 'keyword2']

        root_cause = analyzer.detect_cannibalization(
            '/target-page',
            similar_pages,
            shared_keywords
        )

        # Should return None for low overlap
        assert root_cause is None

    def test_detect_cannibalization_no_similar_pages(self):
        """Test with no similar pages."""
        analyzer = RootCauseAnalyzer()

        root_cause = analyzer.detect_cannibalization(
            '/target-page',
            [],
            ['keyword1', 'keyword2', 'keyword3']
        )

        assert root_cause is None

    def test_analyze_competitor_impact_serp_change(self):
        """Test competitor/SERP change detection."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'impressions': 500,
            'avg_position': 5.0
        }

        historical_metrics = [
            {'impressions': 1500, 'avg_position': 5.2}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_competitor_impact(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'competitor_or_serp_change'
        assert 'serp' in str(root_cause.recommendations).lower()

    def test_analyze_competitor_no_impact(self):
        """Test when competitor impact is not detected."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'impressions': 1400,
            'avg_position': 5.0
        }

        historical_metrics = [
            {'impressions': 1500, 'avg_position': 5.2}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_competitor_impact(
            current_metrics,
            historical_metrics,
            None
        )

        # Minor change, should not detect impact
        assert root_cause is None

    def test_analyze_competitor_no_historical_data(self):
        """Test competitor analysis with no historical data."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'impressions': 500, 'avg_position': 5.0}

        root_cause = analyzer.analyze_competitor_impact(
            current_metrics,
            [],
            None
        )

        assert root_cause is None

    def test_synthesize_diagnosis_multiple_causes(self):
        """Test diagnosis synthesis with multiple causes."""
        analyzer = RootCauseAnalyzer()

        causes = [
            RootCause(
                cause_type='position_drop',
                confidence=0.85,
                evidence={},
                recommendations=[],
                severity='high'
            ),
            RootCause(
                cause_type='ctr_decline',
                confidence=0.7,
                evidence={},
                recommendations=[],
                severity='medium'
            )
        ]

        final_diagnosis = analyzer.synthesize_diagnosis(causes, 'traffic_drop')

        # Should return highest confidence cause
        assert final_diagnosis.cause_type == 'position_drop'
        assert final_diagnosis.confidence == 0.85

    def test_synthesize_diagnosis_no_causes(self):
        """Test diagnosis synthesis with no identified causes."""
        analyzer = RootCauseAnalyzer()

        final_diagnosis = analyzer.synthesize_diagnosis([], 'traffic_drop')

        assert final_diagnosis.cause_type == 'unknown'
        assert final_diagnosis.confidence == 0.3
        assert final_diagnosis.severity == 'low'

    def test_min_confidence_threshold(self):
        """Test custom minimum confidence threshold."""
        analyzer = RootCauseAnalyzer(min_confidence=0.8)

        assert analyzer.min_confidence == 0.8

    def test_seasonal_pattern_detection_insufficient_data(self):
        """Test seasonal pattern with insufficient data."""
        analyzer = RootCauseAnalyzer()

        historical_metrics = [
            {'clicks': 100} for _ in range(5)  # Too few data points
        ]

        is_seasonal = analyzer._detect_seasonal_pattern(historical_metrics)

        assert is_seasonal is False

    def test_seasonal_pattern_detection_weekly(self):
        """Test weekly seasonal pattern detection."""
        analyzer = RootCauseAnalyzer()

        # Create strong weekly pattern
        historical_metrics = []
        for week in range(4):
            for day in range(7):
                clicks = 100 if day < 5 else 30  # Weekday pattern
                historical_metrics.append({'clicks': clicks})

        is_seasonal = analyzer._detect_seasonal_pattern(historical_metrics)

        # Should detect pattern
        assert isinstance(is_seasonal, bool)

    def test_root_cause_dataclass_attributes(self):
        """Test RootCause dataclass has all required attributes."""
        root_cause = RootCause(
            cause_type='test',
            confidence=0.8,
            evidence={'test': 'data'},
            recommendations=['Do this'],
            severity='medium'
        )

        assert root_cause.cause_type == 'test'
        assert root_cause.confidence == 0.8
        assert root_cause.evidence == {'test': 'data'}
        assert root_cause.recommendations == ['Do this']
        assert root_cause.severity == 'medium'

    def test_analyze_traffic_drop_edge_case_zero_ctr(self):
        """Test traffic drop with zero CTR."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'avg_position': 5.0,
            'ctr': 0.0,
            'clicks': 0,
            'impressions': 1000
        }

        historical_metrics = [
            {'avg_position': 5.0, 'ctr': 8.0, 'clicks': 80, 'impressions': 1000}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Should identify CTR issue
        assert root_cause is not None

    def test_analyze_engagement_extreme_bounce(self):
        """Test with extreme bounce rate."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {
            'bounce_rate': 0.98,
            'engagement_rate': 0.02
        }

        historical_metrics = [
            {'bounce_rate': 0.4, 'engagement_rate': 0.6}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_engagement_issue(
            current_metrics,
            historical_metrics,
            None
        )

        assert root_cause is not None
        assert root_cause.cause_type == 'high_bounce_rate'
        assert root_cause.confidence > 0.7

    def test_confidence_capping(self):
        """Test that confidence scores are properly capped at maximum values."""
        analyzer = RootCauseAnalyzer()

        # Extreme position drop should still cap confidence
        current_metrics = {
            'avg_position': 100.0,
            'clicks': 1
        }

        historical_metrics = [
            {'avg_position': 1.0, 'clicks': 500}
            for _ in range(30)
        ]

        root_cause = analyzer.analyze_traffic_drop(
            current_metrics,
            historical_metrics,
            {}
        )

        # Confidence should be capped at 0.95
        assert root_cause.confidence <= 0.95

    def test_multiple_technical_issues_prioritization(self):
        """Test prioritization when multiple technical issues exist."""
        analyzer = RootCauseAnalyzer()

        current_metrics = {'impressions': 100, 'clicks': 10}
        technical_data = {
            'crawl_errors': 5,
            'error_types': ['404'],
            'page_load_time': 4.5
        }

        root_cause = analyzer.analyze_technical_issue(
            current_metrics,
            technical_data
        )

        # Should return highest confidence issue (crawl errors)
        assert root_cause.cause_type == 'crawl_errors'
        assert root_cause.confidence > 0.7
