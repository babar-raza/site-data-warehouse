"""Extended tests for Impact Estimator to improve coverage."""

import pytest
from agents.strategist.impact_estimator import ImpactEstimator, ImpactEstimate


class TestImpactEstimatorExtended:
    """Extended tests for impact estimator."""

    def test_estimate_all_recommendation_types(self):
        """Test impact estimation for all recommendation types."""
        estimator = ImpactEstimator()

        recommendation_types = [
            'content_optimization',
            'internal_linking',
            'technical_fixes',
            'content_creation',
            'content_pruning',
            'ux_improvements'
        ]

        diagnosis = {
            'confidence_score': 0.7,
            'root_cause': 'position_drop',
            'severity': 'medium'
        }

        current_metrics = {
            'clicks': 70,
            'avg_position': 10.0,
            'ctr': 3.0,
            'impressions': 2000
        }

        historical_metrics = [
            {'clicks': 90, 'avg_position': 7.0}
            for _ in range(10)
        ]

        for rec_type in recommendation_types:
            estimate = estimator.estimate_impact(
                rec_type,
                diagnosis,
                current_metrics,
                historical_metrics
            )

            assert isinstance(estimate, ImpactEstimate)
            assert estimate.impact_level in ['low', 'medium', 'high']
            assert estimate.traffic_lift_pct >= 0
            assert 0 <= estimate.confidence <= 1
            assert estimate.estimated_effort_hours > 0

    def test_estimate_with_zero_current_clicks(self):
        """Test estimation with zero current clicks."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.8,
            'root_cause': 'technical_issue',
            'severity': 'high'
        }

        current_metrics = {
            'clicks': 0,
            'avg_position': 50.0,
            'ctr': 0.0,
            'impressions': 1000
        }

        historical_metrics = [
            {'clicks': 100}
            for _ in range(10)
        ]

        estimate = estimator.estimate_impact(
            'technical_fixes',
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert estimate.traffic_lift_pct > 0

    def test_estimate_with_no_historical_data(self):
        """Test estimation without historical data."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.6,
            'root_cause': 'ctr_decline',
            'severity': 'low'
        }

        current_metrics = {
            'clicks': 50,
            'ctr': 2.0
        }

        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            []
        )

        assert isinstance(estimate, ImpactEstimate)
        assert estimate.traffic_lift_pct > 0

    def test_estimate_with_improving_page(self):
        """Test estimation for page that's already improving."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.7,
            'root_cause': 'optimization_opportunity',
            'severity': 'low'
        }

        current_metrics = {
            'clicks': 110,  # Better than historical
            'avg_position': 5.0
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 7.0}
            for _ in range(10)
        ]

        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert isinstance(estimate, ImpactEstimate)
        # Should still suggest improvement even if already improving
        assert estimate.traffic_lift_pct >= 0

    def test_estimate_high_severity_diagnosis(self):
        """Test estimation with high severity diagnosis."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.9,
            'root_cause': 'deindexing',
            'severity': 'high'
        }

        current_metrics = {
            'clicks': 10,
            'impressions': 100
        }

        historical_metrics = [
            {'clicks': 500, 'impressions': 10000}
            for _ in range(10)
        ]

        estimate = estimator.estimate_impact(
            'technical_fixes',
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert estimate.impact_level == 'high'
        assert estimate.traffic_lift_pct >= 30.0

    def test_estimate_with_root_cause_alignment(self):
        """Test estimation with aligned root cause and recommendation."""
        estimator = ImpactEstimator()

        test_cases = [
            ('ctr_decline', 'content_optimization'),
            ('position_drop', 'internal_linking'),
            ('technical_issue', 'technical_fixes'),
            ('engagement_decline', 'ux_improvements')
        ]

        current_metrics = {'clicks': 50}
        historical_metrics = [{'clicks': 75} for _ in range(10)]

        for root_cause, rec_type in test_cases:
            diagnosis = {
                'confidence_score': 0.7,
                'root_cause': root_cause,
                'severity': 'medium'
            }

            estimate = estimator.estimate_impact(
                rec_type,
                diagnosis,
                current_metrics,
                historical_metrics
            )

            assert estimate.traffic_lift_pct > 0

    def test_estimate_roi_score_calculation(self):
        """Test ROI score calculation."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.8,
            'root_cause': 'ctr_decline',
            'severity': 'medium'
        }

        current_metrics = {'clicks': 50}
        historical_metrics = [{'clicks': 100} for _ in range(10)]

        # High impact, low effort should have high ROI
        estimate_high_roi = estimator.estimate_impact(
            'content_pruning',  # Low effort
            diagnosis,
            current_metrics,
            historical_metrics
        )

        # Lower impact, high effort should have lower ROI
        estimate_low_roi = estimator.estimate_impact(
            'content_creation',  # High effort
            {**diagnosis, 'confidence_score': 0.5},
            current_metrics,
            historical_metrics
        )

        assert estimate_high_roi.roi_score >= 0
        assert estimate_low_roi.roi_score >= 0

    def test_estimate_factors_included(self):
        """Test that all factors are included in estimate."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.7,
            'root_cause': 'position_drop',
            'severity': 'medium'
        }

        current_metrics = {'clicks': 50}
        historical_metrics = []

        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert 'confidence' in estimate.factors
        assert 'severity' in estimate.factors
        assert 'current_performance' in estimate.factors
        assert 'type_multiplier' in estimate.factors

    def test_categorize_impact_boundaries(self):
        """Test impact level categorization at boundaries."""
        estimator = ImpactEstimator()

        # Test at boundaries
        diagnosis_low = {'confidence_score': 0.3, 'root_cause': 'generic', 'severity': 'low'}
        diagnosis_medium = {'confidence_score': 0.5, 'root_cause': 'ctr_decline', 'severity': 'medium'}
        diagnosis_high = {'confidence_score': 0.9, 'root_cause': 'deindexing', 'severity': 'high'}

        current_metrics = {'clicks': 50, 'impressions': 1000}
        historical_metrics = [{'clicks': 100} for _ in range(10)]

        estimate_low = estimator.estimate_impact('content_pruning', diagnosis_low, current_metrics, historical_metrics)
        estimate_medium = estimator.estimate_impact('content_optimization', diagnosis_medium, current_metrics, historical_metrics)
        estimate_high = estimator.estimate_impact('technical_fixes', diagnosis_high, current_metrics, historical_metrics)

        # Verify categorization makes sense
        impact_levels = [estimate_low.impact_level, estimate_medium.impact_level, estimate_high.impact_level]
        assert all(level in ['low', 'medium', 'high'] for level in impact_levels)
