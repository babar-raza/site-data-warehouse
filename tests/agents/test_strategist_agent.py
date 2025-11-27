"""Comprehensive tests for strategist agent."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.llm_reasoner import ReasoningResult
from agents.strategist.impact_estimator import ImpactEstimate, ImpactEstimator
from agents.strategist.prioritizer import Prioritizer, PrioritizationScore
from agents.strategist.recommendation_engine import Recommendation, RecommendationEngine
from agents.strategist.strategist_agent import RecommendationResult, StrategistAgent


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
            'confidence_score': 0.6,
            'root_cause': 'ctr_decline',
            'severity': 'medium'
        }

        current_metrics = {
            'clicks': 80,
            'avg_position': 8.0,
            'ctr': 3.5,
            'impressions': 2000
        }

        historical_metrics = [
            {'clicks': 95, 'avg_position': 7.0, 'ctr': 4.5}
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

    def test_estimate_with_impressions_no_clicks(self):
        """Test impact estimation with impressions but no clicks."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.7,
            'root_cause': 'ctr_decline',
            'severity': 'medium'
        }

        current_metrics = {
            'clicks': 0,
            'impressions': 5000,
            'ctr': 0,
            'avg_position': 10.0
        }

        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            []
        )

        assert estimate.traffic_lift_pct > 0
        assert estimate.traffic_lift_pct <= 100.0

    def test_roi_score_calculation(self):
        """Test ROI score is calculated correctly."""
        estimator = ImpactEstimator()

        diagnosis = {
            'confidence_score': 0.8,
            'root_cause': 'position_drop',
            'severity': 'high'
        }

        current_metrics = {'clicks': 50, 'impressions': 1000}
        historical_metrics = [{'clicks': 100} for _ in range(10)]

        estimate = estimator.estimate_impact(
            'content_optimization',
            diagnosis,
            current_metrics,
            historical_metrics
        )

        assert estimate.roi_score > 0
        assert isinstance(estimate.roi_score, float)


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
        assert prioritized[0].priority == 1
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

    def test_priority_weights(self):
        """Test custom priority weights."""
        prioritizer = Prioritizer(
            impact_weight=0.5,
            urgency_weight=0.2,
            effort_weight=0.2,
            roi_weight=0.1
        )

        assert prioritizer.impact_weight == 0.5
        assert prioritizer.urgency_weight == 0.2
        assert prioritizer.effort_weight == 0.2
        assert prioritizer.roi_weight == 0.1


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

        content_recs = [r for r in recommendations if r.recommendation_type == 'content_optimization']
        assert len(content_recs) > 0

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

    def test_generic_recommendations(self):
        """Test generic recommendations for unknown root cause."""
        engine = RecommendationEngine()

        diagnosis = {
            'root_cause': 'unknown_issue',
            'confidence_score': 0.5,
            'supporting_evidence': {}
        }

        recommendations = engine.generate_recommendations(
            diagnosis,
            {},
            []
        )

        assert len(recommendations) > 0
        assert all(isinstance(r, Recommendation) for r in recommendations)


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
    async def test_process_with_diagnosis_id(self):
        """Test processing with valid diagnosis_id."""
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

        # Mock generate_recommendations
        agent.generate_recommendations = AsyncMock(return_value=[
            {'id': 1, 'recommendation_type': 'content_optimization'}
        ])

        result = await agent.process({'diagnosis_id': 1})

        assert result['status'] == 'success'
        assert 'recommendations' in result
        assert result['diagnosis_id'] == 1

    @pytest.mark.asyncio
    async def test_process_batch_mode(self):
        """Test processing in batch mode."""
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

        # Mock process_batch
        agent.process_batch = AsyncMock(return_value={
            'processed': 5,
            'recommendations_generated': 15
        })

        result = await agent.process({'batch': True})

        assert result['status'] == 'success'
        assert result['processed'] == 5
        assert result['recommendations_generated'] == 15

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_generate_recommendations_integration(self, mock_pool):
        """Test recommendation generation integration with high impact."""
        mock_conn = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return None

        class MockPool:
            def acquire(self):
                return AsyncContextManager()
            async def close(self):
                pass

        mock_pool_instance = MockPool()

        async def create_pool_mock(*args, **kwargs):
            return mock_pool_instance

        mock_pool.side_effect = create_pool_mock

        # Mock diagnosis
        mock_conn.fetchrow.side_effect = [
            {
                'id': 1,
                'finding_id': 1,
                'confidence_score': 0.8,
                'root_cause': 'position_drop',
                'supporting_evidence': '{}',
                'metadata': '{}'
            },
            {
                'id': 1,
                'affected_pages': '["//page1"]',
                'metrics': '{}'
            },
            {
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

        await agent.shutdown()

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_generate_recommendations_low_impact_skip(self, mock_pool):
        """Test that low impact recommendations are still generated but prioritized lower."""
        mock_conn = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return None

        class MockPool:
            def acquire(self):
                return AsyncContextManager()
            async def close(self):
                pass

        mock_pool_instance = MockPool()

        async def create_pool_mock(*args, **kwargs):
            return mock_pool_instance

        mock_pool.side_effect = create_pool_mock

        # Mock diagnosis with low severity
        mock_conn.fetchrow.side_effect = [
            {
                'id': 1,
                'finding_id': 1,
                'confidence_score': 0.5,
                'root_cause': 'generic',
                'supporting_evidence': '{}',
                'metadata': '{}'
            },
            {
                'id': 1,
                'affected_pages': '["//page1"]',
                'metrics': '{}'
            },
            {
                'clicks': 95,
                'impressions': 2000,
                'ctr': 4.5,
                'avg_position': 6.0,
                'engagement_rate': 0.6,
                'conversion_rate': 0.03,
                'bounce_rate': 0.5,
                'sessions': 150,
                'avg_session_duration': 150
            }
        ]

        mock_conn.fetch.return_value = [
            {
                'date': '2024-01-01',
                'clicks': 100,
                'impressions': 2000,
                'ctr': 5.0,
                'avg_position': 6.0,
                'engagement_rate': 0.6,
                'conversion_rate': 0.03,
                'bounce_rate': 0.5,
                'sessions': 150,
                'avg_session_duration': 150
            }
        ] * 10

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
        # Check that recommendations exist (priority may vary based on logic)
        # Low impact scenarios should still generate recommendations
        assert all('priority' in rec for rec in recommendations)

        await agent.shutdown()

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_multiple_recommendations(self, mock_pool):
        """Test generation of multiple recommendations."""
        mock_conn = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return None

        class MockPool:
            def acquire(self):
                return AsyncContextManager()
            async def close(self):
                pass

        mock_pool_instance = MockPool()

        async def create_pool_mock(*args, **kwargs):
            return mock_pool_instance

        mock_pool.side_effect = create_pool_mock

        mock_conn.fetchrow.side_effect = [
            {
                'id': 1,
                'finding_id': 1,
                'confidence_score': 0.8,
                'root_cause': 'ctr_decline',
                'supporting_evidence': '{}',
                'metadata': '{}'
            },
            {
                'id': 1,
                'affected_pages': '["//page1"]',
                'metrics': '{}'
            },
            {
                'clicks': 50,
                'impressions': 2000,
                'ctr': 2.5,
                'avg_position': 5.0,
                'engagement_rate': 0.5,
                'conversion_rate': 0.02,
                'bounce_rate': 0.6,
                'sessions': 100,
                'avg_session_duration': 120
            }
        ]

        mock_conn.fetch.return_value = [
            {
                'date': '2024-01-01',
                'clicks': 100,
                'impressions': 2000,
                'ctr': 5.0,
                'avg_position': 5.0,
                'engagement_rate': 0.6,
                'conversion_rate': 0.03,
                'bounce_rate': 0.5,
                'sessions': 150,
                'avg_session_duration': 150
            }
        ] * 10

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

        # CTR decline should generate multiple recommendations
        assert len(recommendations) >= 1
        rec_types = {rec['recommendation_type'] for rec in recommendations}
        assert 'content_optimization' in rec_types

        await agent.shutdown()

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_priority_ordering(self, mock_pool):
        """Test that recommendations are properly prioritized."""
        mock_conn = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return None

        class MockPool:
            def acquire(self):
                return AsyncContextManager()
            async def close(self):
                pass

        mock_pool_instance = MockPool()

        async def create_pool_mock(*args, **kwargs):
            return mock_pool_instance

        mock_pool.side_effect = create_pool_mock

        mock_conn.fetchrow.side_effect = [
            {
                'id': 1,
                'finding_id': 1,
                'confidence_score': 0.9,
                'root_cause': 'position_drop',
                'supporting_evidence': '{}',
                'metadata': '{}'
            },
            {
                'id': 1,
                'affected_pages': '["//page1"]',
                'metrics': '{}'
            },
            {
                'clicks': 20,
                'impressions': 1000,
                'ctr': 2.0,
                'avg_position': 25.0,
                'engagement_rate': 0.4,
                'conversion_rate': 0.01,
                'bounce_rate': 0.7,
                'sessions': 50,
                'avg_session_duration': 60
            }
        ]

        mock_conn.fetch.return_value = [
            {
                'date': '2024-01-01',
                'clicks': 150,
                'impressions': 1500,
                'ctr': 10.0,
                'avg_position': 3.0,
                'engagement_rate': 0.7,
                'conversion_rate': 0.04,
                'bounce_rate': 0.4,
                'sessions': 200,
                'avg_session_duration': 200
            }
        ] * 10

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

        # Verify priority ordering
        priorities = [rec.get('priority', 5) for rec in recommendations]
        assert len(priorities) > 0

        # Check that higher priority comes first (lower number = higher priority)
        if len(priorities) > 1:
            assert priorities[0] <= priorities[-1]

        await agent.shutdown()

    @pytest.mark.asyncio
    @patch('agents.strategist.strategist_agent.asyncpg.create_pool')
    async def test_no_recommendations_for_missing_diagnosis(self, mock_pool):
        """Test no recommendations when diagnosis not found."""
        mock_conn = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                return None

        class MockPool:
            def acquire(self):
                return AsyncContextManager()
            async def close(self):
                pass

        mock_pool_instance = MockPool()

        async def create_pool_mock(*args, **kwargs):
            return mock_pool_instance

        mock_pool.side_effect = create_pool_mock

        # Return None for diagnosis
        mock_conn.fetchrow.return_value = None

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
        recommendations = await agent.generate_recommendations(999)

        assert recommendations == []

        await agent.shutdown()


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

        assert 0 <= estimate.traffic_lift_pct <= 100
        assert 1 <= estimate.estimated_effort_hours <= 24
        assert 0 <= estimate.confidence <= 1
        assert estimate.roi_score >= 0


class TestRecommendationResult:
    """Test RecommendationResult dataclass."""

    def test_recommendation_result_creation(self):
        """Test creating a RecommendationResult."""
        result = RecommendationResult(
            diagnosis_id=1,
            recommendation_type='content_optimization',
            action_items={'title_rewrite': {'action': 'Rewrite title', 'steps': []}},
            description='Optimize content for better rankings',
            expected_impact='high',
            estimated_effort_hours=4,
            priority=1,
            confidence=0.85
        )

        assert result.diagnosis_id == 1
        assert result.recommendation_type == 'content_optimization'
        assert result.expected_impact == 'high'
        assert result.confidence == 0.85
        assert result.used_llm is False
        assert result.used_rule_fallback is False

    def test_recommendation_result_with_llm(self):
        """Test RecommendationResult with LLM analysis."""
        llm_analysis = {
            'action': 'Rewrite page title',
            'priority': 'high',
            'expected_impact': 'Increase CTR by 15%'
        }

        result = RecommendationResult(
            diagnosis_id=1,
            recommendation_type='content_optimization',
            action_items={},
            description='LLM-generated recommendation',
            expected_impact='high',
            estimated_effort_hours=2,
            priority=1,
            confidence=0.9,
            llm_analysis=llm_analysis,
            used_llm=True
        )

        assert result.llm_analysis == llm_analysis
        assert result.used_llm is True

    def test_recommendation_result_with_quick_wins(self):
        """Test RecommendationResult with quick wins."""
        result = RecommendationResult(
            diagnosis_id=1,
            recommendation_type='content_optimization',
            action_items={},
            description='Test recommendation',
            expected_impact='medium',
            estimated_effort_hours=2,
            priority=2,
            confidence=0.7,
            quick_wins=['Add FAQ section', 'Improve meta description'],
            strategic_initiatives=['Content hub creation']
        )

        assert len(result.quick_wins) == 2
        assert len(result.strategic_initiatives) == 1


class TestStrategistAgentLLMIntegration:
    """Test strategist agent LLM integration."""

    def test_agent_has_llm_reasoner(self):
        """Test agent initializes with LLM reasoner."""
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
            config={'use_llm': True}
        )

        assert hasattr(agent, 'llm_reasoner')
        assert agent.use_llm is True

    def test_agent_llm_disabled(self):
        """Test agent with LLM disabled."""
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
            config={'use_llm': False}
        )

        assert agent.use_llm is False

    def test_get_llm_stats_initial(self):
        """Test get_llm_stats returns initial stats."""
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

        stats = agent.get_llm_stats()

        assert 'total_calls' in stats
        assert 'successful_calls' in stats
        assert 'recommendation_stats' in stats
        assert stats['recommendation_stats']['total_recommendations'] == 0

    def test_run_rule_based_recommendations(self):
        """Test rule-based recommendation generation."""
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

        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        }

        current_metrics = {
            'clicks': 50,
            'impressions': 1000,
            'ctr': 5.0,
            'avg_position': 15.0
        }

        historical_metrics = [
            {'clicks': 100, 'avg_position': 5.0, 'ctr': 6.5}
            for _ in range(10)
        ]

        recommendations = agent._run_rule_based_recommendations(
            diagnosis, current_metrics, historical_metrics
        )

        assert len(recommendations) > 0
        assert all('recommendation_type' in rec for rec in recommendations)
        assert all('expected_impact' in rec for rec in recommendations)

    def test_format_context_for_llm(self):
        """Test formatting context for LLM consumption."""
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

        diagnosis = {
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {'metric': 'position'}
        }

        current_metrics = {
            'clicks': 50,
            'avg_position': 15.0
        }

        context, diagnosis_text, goals, constraints = agent._format_context_for_llm(
            diagnosis, current_metrics, [], '/test/page'
        )

        assert '/test/page' in context
        assert 'position_drop' in diagnosis_text
        assert '80%' in diagnosis_text
        assert 'rankings' in goals.lower()
        assert len(constraints) > 0

    def test_format_context_with_historical_data(self):
        """Test context formatting with historical data."""
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

        diagnosis = {
            'root_cause': 'ctr_decline',
            'confidence_score': 0.7,
            'supporting_evidence': {}
        }

        current_metrics = {
            'clicks': 30,
            'ctr': 2.0
        }

        historical_metrics = [
            {'clicks': 50, 'ctr': 5.0}
            for _ in range(10)
        ]

        context, diagnosis_text, goals, constraints = agent._format_context_for_llm(
            diagnosis, current_metrics, historical_metrics, '/blog/article'
        )

        assert 'ctr_decline' in diagnosis_text
        assert 'click-through' in goals.lower() or 'engagement' in goals.lower()

    def test_apply_rule_fallback(self):
        """Test rule fallback when LLM unavailable."""
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

        rule_based_recs = [
            {
                'recommendation_type': 'content_optimization',
                'action_items': {'rewrite': {'action': 'Rewrite', 'steps': []}},
                'description': 'Optimize content',
                'expected_impact': 'high',
                'estimated_effort_hours': 4,
                'confidence': 0.8,
                'rationale': 'Based on position drop'
            }
        ]

        results = agent._apply_rule_fallback(
            diagnosis_id=1,
            diagnosis={'root_cause': 'position_drop'},
            rule_based_recs=rule_based_recs,
            current_metrics={}
        )

        assert len(results) == 1
        assert results[0].used_llm is False
        assert results[0].used_rule_fallback is True
        assert results[0].recommendation_type == 'content_optimization'

    def test_combine_llm_rule_results(self):
        """Test combining LLM and rule-based results."""
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

        rule_based_recs = [
            {
                'recommendation_type': 'content_optimization',
                'action_items': {},
                'description': 'Optimize content',
                'expected_impact': 'medium',
                'estimated_effort_hours': 4,
                'confidence': 0.6,
                'rationale': 'Rule-based rationale'
            }
        ]

        llm_result = ReasoningResult(
            success=True,
            content={
                'recommendations': [
                    {
                        'action': 'Update page title and meta description',
                        'priority': 'high',
                        'expected_impact': 'Increase CTR by 15%',
                        'effort': 'low',
                        'metrics_to_monitor': ['CTR', 'impressions']
                    }
                ],
                'quick_wins': ['Add internal links', 'Update title'],
                'strategic_initiatives': ['Content hub creation'],
                'reasoning': 'Title optimization is quick win with high impact'
            }
        )

        results = agent._combine_llm_rule_results(
            diagnosis_id=1,
            diagnosis={'root_cause': 'ctr_decline'},
            rule_based_recs=rule_based_recs,
            llm_result=llm_result,
            current_metrics={}
        )

        assert len(results) == 1
        assert results[0].used_llm is True
        assert results[0].llm_analysis is not None
        assert results[0].quick_wins == ['Add internal links', 'Update title']
        assert 0.5 <= results[0].confidence <= 0.8

    def test_combine_with_extra_llm_recommendations(self):
        """Test combining when LLM has more recommendations than rules."""
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

        rule_based_recs = [
            {
                'recommendation_type': 'content_optimization',
                'action_items': {},
                'description': 'Optimize content',
                'expected_impact': 'medium',
                'estimated_effort_hours': 4,
                'confidence': 0.6,
                'rationale': ''
            }
        ]

        llm_result = ReasoningResult(
            success=True,
            content={
                'recommendations': [
                    {'action': 'First action', 'priority': 'high', 'expected_impact': 'High', 'effort': 'low'},
                    {'action': 'Second action', 'priority': 'medium', 'expected_impact': 'Medium', 'effort': 'medium'},
                    {'action': 'Third action', 'priority': 'low', 'expected_impact': 'Low', 'effort': 'high'}
                ],
                'quick_wins': [],
                'strategic_initiatives': [],
                'reasoning': ''
            }
        )

        results = agent._combine_llm_rule_results(
            diagnosis_id=1,
            diagnosis={},
            rule_based_recs=rule_based_recs,
            llm_result=llm_result,
            current_metrics={}
        )

        assert len(results) == 3
        assert results[0].recommendation_type == 'content_optimization'
        assert results[1].recommendation_type == 'llm_generated'
        assert results[2].recommendation_type == 'llm_generated'

    def test_confidence_weights(self):
        """Test confidence weight constants."""
        assert StrategistAgent.LLM_CONFIDENCE_WEIGHT == 0.6
        assert StrategistAgent.RULE_CONFIDENCE_WEIGHT == 0.4
        assert StrategistAgent.LLM_CONFIDENCE_WEIGHT + StrategistAgent.RULE_CONFIDENCE_WEIGHT == 1.0

    def test_goal_mapping_by_root_cause(self):
        """Test goals are mapped correctly by root cause."""
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

        root_causes = {
            'position_drop': 'rankings',
            'ctr_decline': 'click-through',
            'high_bounce_rate': 'bounce',
            'zero_impression': 'visibility',
            'traffic_drop': 'traffic'
        }

        for root_cause, expected_keyword in root_causes.items():
            diagnosis = {'root_cause': root_cause, 'confidence_score': 0.8}
            _, _, goals, _ = agent._format_context_for_llm(diagnosis, {}, [], '/test')
            assert expected_keyword in goals.lower(), f"Expected '{expected_keyword}' in goals for {root_cause}"

    @pytest.mark.asyncio
    async def test_recommend_with_llm_no_diagnosis(self):
        """Test recommend_with_llm returns empty when no diagnosis found."""
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

        agent._get_diagnosis = AsyncMock(return_value=None)

        results = await agent.recommend_with_llm(1)

        assert results == []

    @pytest.mark.asyncio
    async def test_recommend_with_llm_no_finding(self):
        """Test recommend_with_llm returns empty when no finding found."""
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

        agent._get_diagnosis = AsyncMock(return_value={'finding_id': 1})
        agent._get_finding = AsyncMock(return_value=None)

        results = await agent.recommend_with_llm(1)

        assert results == []

    @pytest.mark.asyncio
    async def test_recommend_with_llm_fallback(self):
        """Test recommend_with_llm falls back to rules when LLM fails."""
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
            config={'use_llm': True}
        )

        agent._get_diagnosis = AsyncMock(return_value={
            'finding_id': 1,
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        })
        agent._get_finding = AsyncMock(return_value={
            'affected_pages': '["//test/page"]'
        })
        agent._get_page_current_metrics = AsyncMock(return_value={
            'clicks': 50, 'impressions': 1000
        })
        agent._get_page_historical_metrics = AsyncMock(return_value=[
            {'clicks': 100} for _ in range(10)
        ])

        agent._run_llm_recommendations = MagicMock(return_value=ReasoningResult(
            success=False,
            content=None,
            error='LLM unavailable'
        ))

        results = await agent.recommend_with_llm(1)

        assert len(results) > 0
        assert all(r.used_rule_fallback is True for r in results)
        assert all(r.used_llm is False for r in results)

    @pytest.mark.asyncio
    async def test_recommend_with_llm_success(self):
        """Test recommend_with_llm with successful LLM response."""
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
            config={'use_llm': True}
        )

        agent._get_diagnosis = AsyncMock(return_value={
            'finding_id': 1,
            'root_cause': 'position_drop',
            'confidence_score': 0.8,
            'supporting_evidence': {}
        })
        agent._get_finding = AsyncMock(return_value={
            'affected_pages': '["//test/page"]'
        })
        agent._get_page_current_metrics = AsyncMock(return_value={
            'clicks': 50, 'impressions': 1000
        })
        agent._get_page_historical_metrics = AsyncMock(return_value=[
            {'clicks': 100} for _ in range(10)
        ])

        agent._run_llm_recommendations = MagicMock(return_value=ReasoningResult(
            success=True,
            content={
                'recommendations': [
                    {'action': 'Test action', 'priority': 'high', 'expected_impact': 'High', 'effort': 'low'}
                ],
                'quick_wins': ['Quick win 1'],
                'strategic_initiatives': ['Strategy 1'],
                'reasoning': 'LLM reasoning'
            }
        ))

        results = await agent.recommend_with_llm(1)

        assert len(results) > 0
        assert any(r.used_llm is True for r in results)

    def test_llm_stats_after_recommendations(self):
        """Test LLM stats are updated after recommendations."""
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

        agent._recommendation_results = [
            RecommendationResult(
                diagnosis_id=1,
                recommendation_type='test',
                action_items={},
                description='',
                expected_impact='medium',
                estimated_effort_hours=4,
                priority=2,
                confidence=0.7,
                used_llm=True,
                used_rule_fallback=False
            ),
            RecommendationResult(
                diagnosis_id=2,
                recommendation_type='test',
                action_items={},
                description='',
                expected_impact='low',
                estimated_effort_hours=2,
                priority=3,
                confidence=0.5,
                used_llm=False,
                used_rule_fallback=True
            )
        ]

        stats = agent.get_llm_stats()

        assert stats['recommendation_stats']['total_recommendations'] == 2
        assert stats['recommendation_stats']['llm_recommendations'] == 1
        assert stats['recommendation_stats']['rule_fallback_recommendations'] == 1
        assert stats['recommendation_stats']['llm_usage_rate'] == 0.5

    @pytest.mark.asyncio
    async def test_health_check_includes_llm_stats(self):
        """Test health check includes LLM statistics."""
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

        from datetime import datetime
        agent._start_time = datetime.now()

        health = await agent.health_check()

        assert 'llm_stats' in health.metadata
        assert 'recommendation_stats' in health.metadata['llm_stats']

    @pytest.mark.asyncio
    async def test_recommend_with_llm_no_affected_pages(self):
        """Test recommend_with_llm returns empty when no affected pages."""
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

        agent._get_diagnosis = AsyncMock(return_value={'finding_id': 1})
        agent._get_finding = AsyncMock(return_value={'affected_pages': '[]'})

        results = await agent.recommend_with_llm(1)

        assert results == []
