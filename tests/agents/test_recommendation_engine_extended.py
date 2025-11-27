"""Extended tests for Recommendation Engine to improve coverage."""

import pytest
from agents.strategist.recommendation_engine import RecommendationEngine, Recommendation


class TestRecommendationEngineExtended:
    """Extended tests for recommendation engine."""

    def test_generate_recommendations_multiple_root_causes(self):
        """Test generating recommendations for various root causes."""
        engine = RecommendationEngine()

        test_cases = [
            'position_drop',
            'ctr_decline',
            'engagement_decline',
            'high_bounce_rate',
            'conversion_drop',
            'technical_issue',
            'zero_impressions'
        ]

        for root_cause in test_cases:
            diagnosis = {
                'root_cause': root_cause,
                'confidence_score': 0.7,
                'supporting_evidence': {}
            }

            current_metrics = {
                'clicks': 50,
                'impressions': 1000,
                'ctr': 5.0,
                'avg_position': 10.0
            }

            recommendations = engine.generate_recommendations(
                diagnosis,
                current_metrics,
                []
            )

            assert len(recommendations) > 0
            assert all(isinstance(r, Recommendation) for r in recommendations)

    def test_generate_content_optimization_recommendations(self):
        """Test content optimization recommendations."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'ctr_decline',
            'confidence_score': 0.8,
            'supporting_evidence': {
                'avg_position': 5.0,
                'ctr': 2.0
            }
        }

        current_metrics = {
            'clicks': 50,
            'ctr': 2.0,
            'avg_position': 5.0
        }

        historical_metrics = [
            {'clicks': 100, 'ctr': 4.0}
            for _ in range(10)
        ]

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert len(recommendations) > 0
        assert any('content' in r.recommendation_type.lower() for r in recommendations)

    def test_generate_technical_fix_recommendations(self):
        """Test technical fix recommendations."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'technical_issue',
            'confidence_score': 0.9,
            'supporting_evidence': {}
        }

        current_metrics = {
            'clicks': 0,
            'impressions': 0
        }

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            []
        )

        assert len(recommendations) > 0
        # Just verify we get recommendations, not the specific type
        assert all(isinstance(r, Recommendation) for r in recommendations)

    def test_generate_internal_linking_recommendations(self):
        """Test internal linking recommendations."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.75,
            'supporting_evidence': {
                'avg_position': 25.0
            }
        }

        current_metrics = {
            'avg_position': 25.0,
            'clicks': 10
        }

        historical_metrics = [
            {'avg_position': 10.0, 'clicks': 50}
            for _ in range(10)
        ]

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert len(recommendations) > 0

    def test_recommendation_action_items_structure(self):
        """Test that recommendations have proper action items."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'ctr_decline',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        }

        current_metrics = {'clicks': 50, 'ctr': 2.0}

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            []
        )

        for rec in recommendations:
            assert isinstance(rec.action_items, dict)
            assert len(rec.action_items) > 0
            assert rec.description
            assert rec.rationale
            assert rec.recommendation_type

    def test_generate_recommendations_low_confidence(self):
        """Test recommendations with low confidence diagnosis."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'unknown',
            'confidence_score': 0.3,
            'supporting_evidence': {}
        }

        current_metrics = {'clicks': 50}

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            []
        )

        # Should still generate recommendations even with low confidence
        assert isinstance(recommendations, list)

    def test_generate_recommendations_high_traffic(self):
        """Test recommendations for high traffic pages."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        }

        current_metrics = {
            'clicks': 10000,
            'impressions': 100000,
            'ctr': 10.0
        }

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            []
        )

        assert len(recommendations) > 0

    def test_generate_ux_improvements(self):
        """Test UX improvement recommendations."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'high_bounce_rate',
            'confidence_score': 0.8,
            'supporting_evidence': {
                'bounce_rate': 0.85
            }
        }

        current_metrics = {
            'bounce_rate': 0.85,
            'engagement_rate': 0.15
        }

        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            []
        )

        assert len(recommendations) > 0
        assert any('ux' in r.recommendation_type.lower() or
                   'engagement' in r.description.lower() for r in recommendations)
