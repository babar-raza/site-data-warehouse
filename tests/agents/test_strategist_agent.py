"""Comprehensive tests for strategist agent."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.strategist.impact_estimator import ImpactEstimate, ImpactEstimator
from agents.strategist.prioritizer import Prioritizer, PrioritizationScore
from agents.strategist.recommendation_engine import Recommendation, RecommendationEngine
from agents.strategist.strategist_agent import StrategistAgent


class TestImpactEstimator:
    """Test impact estimator functionality."""

    def test_estimate_high_impact(self):
        """Test estimation of high impact recommendation."""
        estimator = ImpactEstimator()
        
        diagnosis = {
            'confidence_score': 0.9,
            'root_cause': 'position_drop',
            'severity': 'high'
        }
        
        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0,
            'ctr': 3.0,
            'impressions': 1000
        }
        
        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]
        
        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert estimate.impact_level == 'high'
        assert estimate.traffic_lift_pct > 30.0
        assert estimate.confidence >= 0.8
        assert estimate.estimated_effort_hours > 0

    def test_estimate_medium_impact(self):
        """Test estimation of medium impact recommendation."""
        estimator = ImpactEstimator()
        
        diagnosis = {
            'confidence_score': 0.7,
            'root_cause': 'ctr_decline',
            'severity': 'medium'
        }
        
        current_metrics = {
            'clicks': 70,
            'avg_position': 8.0,
            'ctr': 3.5,
            'impressions': 2000
        }
        
        historical_metrics = [
            {'clicks': 90, 'avg_position': 7.0, 'ctr': 4.5}
            for _ in range(10)
        ]
        
        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert estimate.impact_level == 'medium'
        assert 10.0 <= estimate.traffic_lift_pct < 30.0
        assert estimate.estimated_effort_hours > 0

    def test_estimate_low_impact(self):
        """Test estimation of low impact recommendation."""
        estimator = ImpactEstimator()
        
        diagnosis = {
            'confidence_score': 0.5,
            'root_cause': 'generic',
            'severity': 'low'
        }
        
        current_metrics = {
            'clicks': 95,
            'avg_position': 6.0,
            'ctr': 4.5,
            'impressions': 2000
        }
        
        historical_metrics = [
            {'clicks': 100, 'avg_position': 6.0, 'ctr': 5.0}
            for _ in range(10)
        ]
        
        estimate = estimator.estimate_impact(
            'internal_linking',
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert estimate.impact_level == 'low'
        assert estimate.traffic_lift_pct < 10.0

    def test_estimate_technical_fixes(self):
        """Test estimation for technical fixes."""
        estimator = ImpactEstimator()
        
        diagnosis = {
            'confidence_score': 0.8,
            'root_cause': 'zero_impression',
            'severity': 'critical'
        }
        
        current_metrics = {
            'clicks': 0,
            'avg_position': 0,
            'ctr': 0,
            'impressions': 0
        }
        
        historical_metrics = []
        
        estimate = estimator.estimate_impact(
            'technical_fixes',
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert estimate.impact_level in ['medium', 'high']
        assert estimate.estimated_effort_hours >= 8


class TestPrioritizer:
    """Test prioritizer functionality."""

    def test_prioritize_recommendations(self):
        """Test prioritization of recommendations."""
        prioritizer = Prioritizer()
        
        recommendations = [
            {'diagnosis_id': 1, 'recommendation_type': 'content_optimization'},
            {'diagnosis_id': 2, 'recommendation_type': 'technical_fixes'},
            {'diagnosis_id': 3, 'recommendation_type': 'internal_linking'}
        ]
        
        impact_estimates = {
            0: ImpactEstimate(
                impact_level='high',
                traffic_lift_pct=40.0,
                confidence=0.9,
                estimated_effort_hours=4,
                roi_score=3.5,
                factors={}
            ),
            1: ImpactEstimate(
                impact_level='medium',
                traffic_lift_pct=20.0,
                confidence=0.7,
                estimated_effort_hours=8,
                roi_score=1.2,
                factors={}
            ),
            2: ImpactEstimate(
                impact_level='low',
                traffic_lift_pct=8.0,
                confidence=0.6,
                estimated_effort_hours=2,
                roi_score=1.5,
                factors={}
            )
        }
        
        diagnoses = {
            1: {'confidence_score': 0.9, 'severity': 'high'},
            2: {'confidence_score': 0.7, 'severity': 'medium'},
            3: {'confidence_score': 0.6, 'severity': 'low'}
        }
        
        prioritized = prioritizer.prioritize_recommendations(
            recommendations,
            impact_estimates,
            diagnoses
        )
        
        assert len(prioritized) == 3
        assert prioritized[0].priority == 1  # Highest priority
        assert prioritized[0].ranking == 1
        assert prioritized[0].score > prioritized[1].score

    def test_filter_by_priority(self):
        """Test filtering recommendations by priority."""
        prioritizer = Prioritizer()
        
        recommendations = [
            {'id': 1, 'type': 'type1'},
            {'id': 2, 'type': 'type2'},
            {'id': 3, 'type': 'type3'}
        ]
        
        prioritized = [
            PrioritizationScore(1, 0.9, 0.8, 0.9, 0.95, 3.0, 1),
            PrioritizationScore(2, 0.7, 0.6, 0.7, 0.8, 2.0, 2),
            PrioritizationScore(5, 0.3, 0.2, 0.4, 0.3, 1.0, 3)
        ]
        
        filtered = prioritizer.filter_by_priority(
            prioritized,
            recommendations,
            max_priority=2
        )
        
        assert len(filtered) == 2
        assert all(rec['priority'] <= 2 for rec in filtered)

    def test_get_top_n(self):
        """Test getting top N recommendations."""
        prioritizer = Prioritizer()
        
        recommendations = [
            {'id': i, 'type': f'type{i}'} for i in range(10)
        ]
        
        prioritized = [
            PrioritizationScore(i, 0.9 - i * 0.1, 0.8, 0.8, 0.8, 2.0, i + 1)
            for i in range(10)
        ]
        
        top_recs = prioritizer.get_top_n(recommendations, prioritized, n=5)
        
        assert len(top_recs) == 5
        assert all('priority' in rec for rec in top_recs)
        assert all('ranking' in rec for rec in top_recs)


class TestRecommendationEngine:
    """Test recommendation engine functionality."""

    def test_generate_position_recovery_recommendations(self):
        """Test generation of position recovery recommendations."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
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
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert len(recommendations) > 0
        assert any(r.recommendation_type == 'content_optimization' for r in recommendations)
        assert all(hasattr(r, 'action_items') for r in recommendations)

    def test_generate_ctr_improvement_recommendations(self):
        """Test generation of CTR improvement recommendations."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'ctr_decline',
            'confidence_score': 0.7,
            'supporting_evidence': {}
        }
        
        current_metrics = {
            'clicks': 50,
            'avg_position': 5.0,
            'ctr': 2.0
        }
        
        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 5.0}
            for _ in range(10)
        ]
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert len(recommendations) > 0
        
        # Check for title/meta optimization
        content_recs = [r for r in recommendations if r.recommendation_type == 'content_optimization']
        assert len(content_recs) > 0
        
        # Verify action items
        for rec in content_recs:
            assert 'title_rewrite' in rec.action_items or 'meta_description' in rec.action_items

    def test_generate_technical_fix_recommendations(self):
        """Test generation of technical fix recommendations."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'zero_impression',
            'confidence_score': 0.9,
            'supporting_evidence': {}
        }
        
        current_metrics = {
            'clicks': 0,
            'impressions': 0
        }
        
        historical_metrics = []
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert len(recommendations) > 0
        assert any(r.recommendation_type == 'technical_fixes' for r in recommendations)

    def test_generate_engagement_recommendations(self):
        """Test generation of engagement recommendations."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'high_bounce_rate',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        }
        
        current_metrics = {
            'bounce_rate': 0.8,
            'engagement_rate': 0.2
        }
        
        historical_metrics = [
            {'bounce_rate': 0.5, 'engagement_rate': 0.5}
            for _ in range(10)
        ]
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        assert len(recommendations) > 0
        assert any(r.recommendation_type == 'ux_improvements' for r in recommendations)

    def test_recommendation_has_required_fields(self):
        """Test that recommendations have all required fields."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'ctr_decline',
            'confidence_score': 0.7,
            'supporting_evidence': {}
        }
        
        current_metrics = {'clicks': 50, 'ctr': 2.0}
        historical_metrics = []
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        for rec in recommendations:
            assert hasattr(rec, 'recommendation_type')
            assert hasattr(rec, 'action_items')
            assert hasattr(rec, 'description')
            assert hasattr(rec, 'rationale')
            assert isinstance(rec.action_items, dict)
            assert len(rec.action_items) > 0


class TestStrategistAgent:
    """Test strategist agent functionality."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization."""
        db_config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'test_user',
            'password': 'test_pass',
            'database': 'test_db'
        }
        
        agent = StrategistAgent(
            agent_id='test_strategist',
            db_config=db_config,
            config={}
        )
        
        assert agent.agent_id == 'test_strategist'
        assert agent.agent_type == 'strategist'
        assert agent.recommendation_engine is not None
        assert agent.impact_estimator is not None
        assert agent.prioritizer is not None

    @pytest.mark.asyncio
    async def test_process_invalid_input(self):
        """Test processing with invalid input."""
        db_config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'test_user',
            'password': 'test_pass',
            'database': 'test_db'
        }
        
        agent = StrategistAgent(
            agent_id='test_strategist',
            db_config=db_config,
            config={}
        )
        
        result = await agent.process({})
        
        assert result['status'] == 'error'
        assert 'error' in result

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_generate_recommendations_integration(self, mock_pool):
        """Test recommendation generation integration."""
        # Mock database
        mock_conn = AsyncMock()
        mock_pool_instance = AsyncMock()
        mock_pool_instance.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.return_value = mock_pool_instance
        
        # Mock diagnosis
        mock_conn.fetchrow.side_effect = [
            {  # Diagnosis
                'id': 1,
                'finding_id': 1,
                'confidence_score': 0.8,
                'root_cause': 'position_drop',
                'supporting_evidence': '{}',
                'metadata': '{}'
            },
            {  # Finding
                'id': 1,
                'affected_pages': '["//page1"]',
                'metrics': '{}'
            },
            {  # Current metrics
                'clicks': 50,
                'impressions': 1000,
                'ctr': 5.0,
                'avg_position': 15.0,
                'engagement_rate': 0.5,
                'conversion_rate': 0.02,
                'bounce_rate': 0.6,
                'sessions': 100,
                'avg_session_duration': 120
            }
        ]
        
        # Mock historical metrics
        mock_conn.fetch.return_value = [
            {
                'date': '2024-01-01',
                'clicks': 100,
                'impressions': 1500,
                'ctr': 6.5,
                'avg_position': 5.0,
                'engagement_rate': 0.6,
                'conversion_rate': 0.03,
                'bounce_rate': 0.5,
                'sessions': 150,
                'avg_session_duration': 150
            }
        ] * 10
        
        # Mock store recommendation
        mock_conn.fetchval.return_value = 1
        
        db_config = {
            'host': 'localhost',
            'port': 5432,
            'user': 'test_user',
            'password': 'test_pass',
            'database': 'test_db'
        }
        
        agent = StrategistAgent(
            agent_id='test_strategist',
            db_config=db_config,
            config={}
        )
        
        await agent.initialize()
        recommendations = await agent.generate_recommendations(1)
        
        assert len(recommendations) > 0
        assert all('recommendation_type' in rec for rec in recommendations)
        assert all('priority' in rec for rec in recommendations)
        assert all('expected_impact' in rec for rec in recommendations)


class TestRecommendationQuality:
    """Test recommendation quality and completeness."""

    def test_recommendations_have_actionable_steps(self):
        """Test that recommendations include actionable steps."""
        engine = RecommendationEngine()
        
        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        }
        
        recommendations = engine.generate_recommendations(
            diagnosis,
            {'clicks': 50},
            []
        )
        
        for rec in recommendations:
            for action_key, action_data in rec.action_items.items():
                assert 'action' in action_data
                assert 'steps' in action_data
                assert isinstance(action_data['steps'], list)
                assert len(action_data['steps']) > 0

    def test_prioritization_considers_multiple_factors(self):
        """Test that prioritization uses all factors."""
        prioritizer = Prioritizer(
            impact_weight=0.4,
            urgency_weight=0.3,
            effort_weight=0.2,
            roi_weight=0.1
        )
        
        recommendations = [{'diagnosis_id': 1, 'recommendation_type': 'test'}]
        
        impact_estimates = {
            0: ImpactEstimate(
                impact_level='high',
                traffic_lift_pct=40.0,
                confidence=0.9,
                estimated_effort_hours=4,
                roi_score=3.5,
                factors={}
            )
        }
        
        diagnoses = {1: {'confidence_score': 0.9, 'severity': 'high'}}
        
        prioritized = prioritizer.prioritize_recommendations(
            recommendations,
            impact_estimates,
            diagnoses
        )
        
        score = prioritized[0]
        
        # Verify all scores are calculated
        assert score.impact_score > 0
        assert score.urgency_score > 0
        assert score.effort_score > 0
        assert score.roi_score > 0
        assert score.score > 0

    def test_impact_estimation_realistic_ranges(self):
        """Test that impact estimates are in realistic ranges."""
        estimator = ImpactEstimator()
        
        diagnosis = {
            'confidence_score': 0.8,
            'root_cause': 'position_drop',
            'severity': 'high'
        }
        
        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            {'clicks': 50, 'impressions': 1000},
            [{'clicks': 100} for _ in range(10)]
        )
        
        # Traffic lift should be reasonable (0-100%)
        assert 0 <= estimate.traffic_lift_pct <= 100
        
        # Effort should be reasonable (1-24 hours typically)
        assert 1 <= estimate.estimated_effort_hours <= 24
        
        # Confidence should be between 0 and 1
        assert 0 <= estimate.confidence <= 1
        
        # ROI should be positive
        assert estimate.roi_score >= 0
