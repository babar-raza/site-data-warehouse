"""
Comprehensive tests for TopicStrategyDetector

Tests topic strategy detection including:
- Underrepresented topic opportunities
- Topic cannibalization diagnosis
- Entity ID format validation
- Metrics inclusion
Uses mocks to achieve high coverage without requiring external services.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import date

from insights_core.detectors.topic_strategy import (
    TopicStrategyDetector,
    TOPIC_CLUSTERER_AVAILABLE,
    OPPORTUNITY_MIN_IMPRESSIONS,
    OPPORTUNITY_MAX_PAGE_COUNT,
    CANNIBALIZATION_THRESHOLD,
)
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
)


@pytest.fixture
def mock_config():
    """Mock InsightsConfig."""
    config = Mock()
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test_db"
    return config


@pytest.fixture
def mock_repository():
    """Mock InsightRepository."""
    repo = Mock()
    repo.create = Mock(return_value=Mock(id="test-insight-id"))
    return repo


@pytest.fixture
def sample_topic_underrepresented():
    """Sample topic that's underrepresented (opportunity)."""
    return {
        'topic_id': 1,
        'name': 'Python Tutorials',
        'slug': 'python-tutorials',
        'page_count': 3,
        'avg_clicks': 500,
        'total_clicks': 1500,  # High traffic
        'avg_position': 8.5,
        'avg_ctr': 0.04,
        'avg_quality': 75.0,
    }


@pytest.fixture
def sample_topic_cannibalized():
    """Sample topic showing cannibalization."""
    return {
        'topic_id': 2,
        'name': 'SEO Best Practices',
        'slug': 'seo-best-practices',
        'page_count': 12,  # Many pages
        'avg_clicks': 20,
        'total_clicks': 240,
        'avg_position': 25.0,  # Poor position
        'avg_ctr': 0.008,  # Low CTR
        'avg_quality': 60.0,
    }


@pytest.fixture
def sample_topic_healthy():
    """Sample healthy topic (no issues)."""
    return {
        'topic_id': 3,
        'name': 'Web Development',
        'slug': 'web-development',
        'page_count': 8,
        'avg_clicks': 200,
        'total_clicks': 1600,
        'avg_position': 5.5,
        'avg_ctr': 0.06,
        'avg_quality': 85.0,
    }


class TestTopicStrategyDetectorInit:
    """Tests for TopicStrategyDetector initialization."""

    def test_init_with_topic_clustering_enabled(self, mock_repository, mock_config):
        """Test initialization with TopicClusterer enabled."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            assert detector.repository == mock_repository
            assert detector.config == mock_config
            if TOPIC_CLUSTERER_AVAILABLE:
                assert detector.use_topic_clustering is True
                mock_clusterer_class.assert_called_once()

    def test_init_with_topic_clustering_disabled(self, mock_repository, mock_config):
        """Test initialization with TopicClusterer disabled."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        assert detector.use_topic_clustering is False
        assert detector.topic_clusterer is None

    def test_init_handles_clusterer_error(self, mock_repository, mock_config):
        """Test graceful handling when TopicClusterer fails to initialize."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer_class.side_effect = Exception("Connection failed")

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            assert detector.use_topic_clustering is False
            assert detector.topic_clusterer is None


class TestTopicStrategyDetectorDetect:
    """Tests for detect() method."""

    def test_detect_requires_property(self, mock_repository, mock_config):
        """Test that detect requires a property filter."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        count = detector.detect()  # No property

        assert count == 0

    def test_detect_skips_without_clusterer(self, mock_repository, mock_config):
        """Test that detect skips when TopicClusterer not available."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        count = detector.detect(property="sc-domain:example.com")

        assert count == 0
        mock_repository.create.assert_not_called()

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_detect_handles_no_topics(self, mock_repository, mock_config):
        """Test handling when no topics found."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=[])
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 0
            mock_repository.create.assert_not_called()


@pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
class TestUnderrepresentedTopicDetection:
    """Tests for underrepresented topic (opportunity) detection."""

    def test_underrepresented_topic_creates_opportunity(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented
    ):
        """Test that underrepresented topic creates opportunity insight."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_underrepresented]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 1
            mock_repository.create.assert_called_once()

            # Verify insight created
            call_args = mock_repository.create.call_args[0][0]
            assert isinstance(call_args, InsightCreate)
            assert call_args.category == InsightCategory.OPPORTUNITY
            assert "Underrepresented" in call_args.title
            assert call_args.entity_type == EntityType.DIRECTORY

    def test_underrepresented_topic_entity_id_format(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented
    ):
        """Test that entity ID format is 'topic:{slug}'."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_underrepresented]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            detector.detect(property="sc-domain:example.com")

            call_args = mock_repository.create.call_args[0][0]
            assert call_args.entity_id == "topic:python-tutorials"

    def test_underrepresented_topic_metrics(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented
    ):
        """Test that metrics include topic, page_count, avg_impressions."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_underrepresented]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            detector.detect(property="sc-domain:example.com")

            call_args = mock_repository.create.call_args[0][0]
            metrics = call_args.metrics

            assert hasattr(metrics, 'topic')
            assert metrics.topic == 'Python Tutorials'
            assert hasattr(metrics, 'page_count')
            assert metrics.page_count == 3
            assert hasattr(metrics, 'total_clicks')
            assert metrics.total_clicks == 1500

    def test_high_page_count_not_underrepresented(
        self,
        mock_repository,
        mock_config
    ):
        """Test that topics with high page count aren't marked as underrepresented."""
        topic = {
            'topic_id': 1,
            'name': 'Test Topic',
            'slug': 'test-topic',
            'page_count': 10,  # Above threshold
            'avg_clicks': 500,
            'total_clicks': 5000,
            'avg_position': 5.0,
            'avg_ctr': 0.05,
        }

        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=[topic])
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            # This topic has many pages, so no opportunity
            # But it may have cannibalization, so we need to check
            count = detector.detect(property="sc-domain:example.com")

            # Check that no opportunity insight was created
            created_insights = [
                call[0][0] for call in mock_repository.create.call_args_list
            ]
            opportunity_insights = [
                i for i in created_insights
                if i.category == InsightCategory.OPPORTUNITY
            ]
            assert len(opportunity_insights) == 0


@pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
class TestCannibalizationDetection:
    """Tests for topic cannibalization detection."""

    def test_cannibalization_creates_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_topic_cannibalized
    ):
        """Test that cannibalized topic creates diagnosis insight."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_cannibalized]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count >= 1

            # Find the diagnosis insight
            created_insights = [
                call[0][0] for call in mock_repository.create.call_args_list
            ]
            diagnosis_insights = [
                i for i in created_insights
                if i.category == InsightCategory.DIAGNOSIS
            ]

            assert len(diagnosis_insights) == 1
            assert "Cannibalization" in diagnosis_insights[0].title

    def test_cannibalization_entity_id_format(
        self,
        mock_repository,
        mock_config,
        sample_topic_cannibalized
    ):
        """Test that cannibalization insight has correct entity ID format."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_cannibalized]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            detector.detect(property="sc-domain:example.com")

            # Find the diagnosis insight
            created_insights = [
                call[0][0] for call in mock_repository.create.call_args_list
            ]
            diagnosis_insights = [
                i for i in created_insights
                if i.category == InsightCategory.DIAGNOSIS
            ]

            assert diagnosis_insights[0].entity_id == "topic:seo-best-practices"
            assert diagnosis_insights[0].entity_type == EntityType.DIRECTORY

    def test_cannibalization_score_in_metrics(
        self,
        mock_repository,
        mock_config,
        sample_topic_cannibalized
    ):
        """Test that cannibalization score is included in metrics."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_cannibalized]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            detector.detect(property="sc-domain:example.com")

            # Find the diagnosis insight
            created_insights = [
                call[0][0] for call in mock_repository.create.call_args_list
            ]
            diagnosis_insights = [
                i for i in created_insights
                if i.category == InsightCategory.DIAGNOSIS
            ]

            metrics = diagnosis_insights[0].metrics
            assert hasattr(metrics, 'cannibalization_score')
            assert metrics.cannibalization_score > CANNIBALIZATION_THRESHOLD


class TestCannibalizationScoreCalculation:
    """Tests for cannibalization score calculation."""

    def test_few_pages_no_cannibalization(self, mock_repository, mock_config):
        """Test that topics with few pages don't get cannibalization score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic = {
            'page_count': 2,  # Below minimum
            'avg_ctr': 0.01,
            'avg_position': 25,
            'total_clicks': 50,
        }

        score = detector._calculate_cannibalization_score(topic)
        assert score == 0.0

    def test_many_pages_low_ctr_high_score(self, mock_repository, mock_config):
        """Test that many pages with low CTR results in high score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic = {
            'page_count': 15,
            'avg_ctr': 0.005,  # Very low CTR
            'avg_position': 35,  # Very poor position
            'total_clicks': 50,  # Low total clicks
            'avg_clicks': 3,
        }

        score = detector._calculate_cannibalization_score(topic)
        assert score > 0.7  # Above threshold

    def test_many_pages_good_ctr_low_score(self, mock_repository, mock_config):
        """Test that many pages with good CTR results in lower score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic = {
            'page_count': 8,
            'avg_ctr': 0.05,  # Good CTR
            'avg_position': 5,  # Good position
            'total_clicks': 1000,  # High total clicks
            'avg_clicks': 125,
        }

        score = detector._calculate_cannibalization_score(topic)
        assert score < 0.5  # Well below threshold


@pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
class TestMultipleTopics:
    """Tests for handling multiple topics."""

    def test_detect_processes_all_topics(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented,
        sample_topic_cannibalized,
        sample_topic_healthy
    ):
        """Test that detector processes all topics."""
        topics = [
            sample_topic_underrepresented,
            sample_topic_cannibalized,
            sample_topic_healthy
        ]

        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=topics)
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            # Should create at least 2 insights (1 opportunity + 1 diagnosis)
            # Healthy topic should create no insights
            assert count >= 2

    def test_healthy_topic_no_insights(
        self,
        mock_repository,
        mock_config,
        sample_topic_healthy
    ):
        """Test that healthy topic creates no insights."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_healthy]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 0
            mock_repository.create.assert_not_called()


class TestGetTopicSummary:
    """Tests for get_topic_summary() convenience method."""

    def test_summary_when_clusterer_unavailable(self, mock_repository, mock_config):
        """Test summary returns error when clusterer not available."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        result = detector.get_topic_summary("sc-domain:example.com")

        assert result['available'] is False
        assert 'error' in result

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_summary_returns_opportunities_and_risks(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented,
        sample_topic_cannibalized
    ):
        """Test summary returns opportunities and cannibalization risks."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_underrepresented, sample_topic_cannibalized]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            result = detector.get_topic_summary("sc-domain:example.com")

            assert result['available'] is True
            assert result['topics_found'] == 2
            assert result['opportunities_count'] >= 1
            assert result['cannibalization_count'] >= 1


class TestEngineIntegration:
    """Tests for integration with InsightEngine."""

    def test_detector_in_engine(self):
        """Test that TopicStrategyDetector is in engine's detectors."""
        with patch('insights_core.engine.InsightRepository'):
            with patch('insights_core.engine.InsightsConfig'):
                from insights_core.engine import InsightEngine

                # Check that TopicStrategyDetector is in the import
                from insights_core.detectors import TopicStrategyDetector
                assert TopicStrategyDetector is not None

    def test_detector_exported_from_init(self):
        """Test that TopicStrategyDetector is exported from detectors __init__."""
        from insights_core.detectors import TopicStrategyDetector
        assert TopicStrategyDetector is not None
        assert hasattr(TopicStrategyDetector, 'detect')


class TestSeverityLevels:
    """Tests for severity level assignment."""

    def test_high_opportunity_score_high_severity(self, mock_repository, mock_config):
        """Test that high opportunity score results in high severity."""
        topic = {
            'topic_id': 1,
            'name': 'High Opportunity',
            'slug': 'high-opportunity',
            'page_count': 1,  # Very few pages
            'avg_clicks': 10000,
            'total_clicks': 10000,  # Very high traffic
            'avg_position': 3.0,
            'avg_ctr': 0.08,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.severity == InsightSeverity.HIGH

    def test_medium_opportunity_score_medium_severity(self, mock_repository, mock_config):
        """Test that medium opportunity score results in medium severity."""
        # opportunity_score = (total_clicks / page_count) / OPPORTUNITY_MIN_IMPRESSIONS
        # For MEDIUM: opportunity_score > 2, so (total_clicks / page_count) > 2000
        # With page_count=1 and total_clicks=3000: score = 3000/1/1000 = 3.0 (MEDIUM)
        topic = {
            'topic_id': 1,
            'name': 'Medium Opportunity',
            'slug': 'medium-opportunity',
            'page_count': 1,
            'avg_clicks': 3000,
            'total_clicks': 3000,  # Score will be 3.0
            'avg_position': 5.0,
            'avg_ctr': 0.05,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.severity == InsightSeverity.MEDIUM

    def test_low_opportunity_score_low_severity(self, mock_repository, mock_config):
        """Test that low opportunity score results in low severity."""
        topic = {
            'topic_id': 1,
            'name': 'Low Opportunity',
            'slug': 'low-opportunity',
            'page_count': 4,
            'avg_clicks': 300,
            'total_clicks': 1200,
            'avg_position': 8.0,
            'avg_ctr': 0.03,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.severity == InsightSeverity.LOW

    def test_cannibalization_severity_based_on_score(self, mock_repository, mock_config):
        """Test that cannibalization severity matches score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # High cannibalization score
        topic_high = {
            'name': 'High Cannibalization',
            'slug': 'high-cannibalization',
            'page_count': 15,
            'avg_ctr': 0.005,
            'avg_position': 35,
            'total_clicks': 30,
            'avg_clicks': 2,
        }

        insight = detector._create_cannibalization_insight(
            topic_high,
            "sc-domain:example.com",
            0.95
        )

        assert insight.severity == InsightSeverity.HIGH

    def test_cannibalization_medium_severity(self, mock_repository, mock_config):
        """Test medium severity cannibalization."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic_medium = {
            'name': 'Medium Cannibalization',
            'slug': 'medium-cannibalization',
            'page_count': 8,
            'avg_ctr': 0.015,
            'avg_position': 22,
            'total_clicks': 100,
            'avg_clicks': 12,
        }

        insight = detector._create_cannibalization_insight(
            topic_medium,
            "sc-domain:example.com",
            0.85
        )

        assert insight.severity == InsightSeverity.MEDIUM

    def test_cannibalization_low_severity(self, mock_repository, mock_config):
        """Test low severity cannibalization."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic_low = {
            'name': 'Low Cannibalization',
            'slug': 'low-cannibalization',
            'page_count': 5,
            'avg_ctr': 0.025,
            'avg_position': 15,
            'total_clicks': 200,
            'avg_clicks': 40,
        }

        insight = detector._create_cannibalization_insight(
            topic_low,
            "sc-domain:example.com",
            0.75
        )

        assert insight.severity == InsightSeverity.LOW


class TestTopicGapScenario:
    """Tests for topic gap detection (no pages for high-demand topic)."""

    def test_topic_gap_single_page_high_traffic(self, mock_repository, mock_config):
        """Test topic gap with single page receiving high traffic."""
        topic = {
            'topic_id': 1,
            'name': 'Topic Gap Example',
            'slug': 'topic-gap-example',
            'page_count': 1,  # Only one page
            'avg_clicks': 5000,
            'total_clicks': 5000,  # Very high traffic
            'avg_position': 4.0,
            'avg_ctr': 0.06,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.category == InsightCategory.OPPORTUNITY
        assert "Underrepresented" in insight.title
        assert insight.metrics.page_count == 1
        assert insight.metrics.total_clicks == 5000


class TestTopicOverlapScenario:
    """Tests for topic overlap (cannibalization) scenarios."""

    def test_topic_overlap_many_pages_poor_performance(self, mock_repository, mock_config):
        """Test topic overlap with many pages and poor individual performance."""
        topic = {
            'topic_id': 1,
            'name': 'Topic Overlap',
            'slug': 'topic-overlap',
            'page_count': 15,  # Many pages
            'avg_clicks': 5,  # Very low per-page clicks
            'total_clicks': 75,
            'avg_position': 32.0,
            'avg_ctr': 0.005,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        score = detector._calculate_cannibalization_score(topic)
        assert score > CANNIBALIZATION_THRESHOLD

        insight = detector._create_cannibalization_insight(
            topic,
            "sc-domain:example.com",
            score
        )

        assert insight.category == InsightCategory.DIAGNOSIS
        assert "Cannibalization" in insight.title
        assert insight.metrics.page_count == 15


class TestBalancedCoverageScenario:
    """Tests for balanced topic coverage (healthy state)."""

    def test_balanced_coverage_no_insights(
        self,
        mock_repository,
        mock_config,
        sample_topic_healthy
    ):
        """Test that balanced topic coverage generates no insights."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Check no opportunity insight
        opportunity = detector._check_underrepresented_topic(
            sample_topic_healthy,
            "sc-domain:example.com"
        )
        assert opportunity is None

        # Check low cannibalization score
        score = detector._calculate_cannibalization_score(sample_topic_healthy)
        assert score < CANNIBALIZATION_THRESHOLD


class TestSingleTopicScenario:
    """Tests for single topic scenarios."""

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_single_topic_detection(
        self,
        mock_repository,
        mock_config,
        sample_topic_underrepresented
    ):
        """Test detection with a single topic."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                return_value=[sample_topic_underrepresented]
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 1
            mock_repository.create.assert_called_once()


class TestNoTopicsScenario:
    """Tests for scenarios with no topics found."""

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_empty_topics_list(self, mock_repository, mock_config):
        """Test handling of empty topics list."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=[])
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 0
            mock_repository.create.assert_not_called()

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_none_topics_result(self, mock_repository, mock_config):
        """Test handling of None topics result."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=None)
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            count = detector.detect(property="sc-domain:example.com")

            assert count == 0


class TestTopicClusteringIntegration:
    """Tests for topic clustering integration."""

    def test_topic_without_slug_uses_name(self, mock_repository, mock_config):
        """Test that topics without slug use slugified name."""
        topic = {
            'topic_id': 1,
            'name': 'Python Data Science',
            # No slug provided
            'page_count': 2,
            'avg_clicks': 1000,
            'total_clicks': 2000,
            'avg_position': 6.0,
            'avg_ctr': 0.04,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.entity_id == "topic:python-data-science"


class TestSemanticSimilarity:
    """Tests for semantic similarity in topic detection."""

    def test_similar_topics_different_slugs(self, mock_repository, mock_config):
        """Test that topics with similar content are properly identified."""
        topic1 = {
            'topic_id': 1,
            'name': 'Python Tutorial',
            'slug': 'python-tutorial',
            'page_count': 3,
            'avg_clicks': 500,
            'total_clicks': 1500,
            'avg_position': 8.0,
            'avg_ctr': 0.04,
        }

        topic2 = {
            'topic_id': 2,
            'name': 'Python Guide',
            'slug': 'python-guide',
            'page_count': 4,
            'avg_clicks': 400,
            'total_clicks': 1600,
            'avg_position': 9.0,
            'avg_ctr': 0.035,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Both should be treated independently
        insight1 = detector._check_underrepresented_topic(topic1, "sc-domain:example.com")
        insight2 = detector._check_underrepresented_topic(topic2, "sc-domain:example.com")

        # Both meet opportunity criteria
        assert insight1 is not None
        assert insight2 is not None
        # But have different entity IDs
        assert insight1.entity_id != insight2.entity_id


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_page_count(self, mock_repository, mock_config):
        """Test handling of zero page count."""
        topic = {
            'topic_id': 1,
            'name': 'Zero Pages',
            'slug': 'zero-pages',
            'page_count': 0,
            'avg_clicks': 0,
            'total_clicks': 0,
            'avg_position': 0,
            'avg_ctr': 0,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Should not create opportunity (no traffic)
        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")
        assert insight is None

        # Should not create cannibalization (below minimum pages)
        score = detector._calculate_cannibalization_score(topic)
        assert score == 0.0

    def test_exact_threshold_values(self, mock_repository, mock_config):
        """Test behavior at exact threshold boundaries."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Exactly at page count threshold
        topic_at_threshold = {
            'topic_id': 1,
            'name': 'At Threshold',
            'slug': 'at-threshold',
            'page_count': OPPORTUNITY_MAX_PAGE_COUNT,  # Exactly 5
            'avg_clicks': 300,
            'total_clicks': 1500,
            'avg_position': 7.0,
            'avg_ctr': 0.04,
        }

        # Should not create insight (needs < threshold, not <=)
        insight = detector._check_underrepresented_topic(
            topic_at_threshold,
            "sc-domain:example.com"
        )
        assert insight is None

        # Exactly at impressions threshold
        topic_exact_impressions = {
            'topic_id': 2,
            'name': 'Exact Impressions',
            'slug': 'exact-impressions',
            'page_count': 3,
            'avg_clicks': 333,
            'total_clicks': OPPORTUNITY_MIN_IMPRESSIONS,  # Exactly 1000
            'avg_position': 6.0,
            'avg_ctr': 0.04,
        }

        # Should create insight (needs >= threshold)
        insight = detector._check_underrepresented_topic(
            topic_exact_impressions,
            "sc-domain:example.com"
        )
        assert insight is not None

    def test_missing_optional_fields(self, mock_repository, mock_config):
        """Test handling of topics with missing optional fields."""
        topic = {
            'topic_id': 1,
            'name': 'Incomplete Topic',
            'slug': 'incomplete-topic',
            'page_count': 3,
            'total_clicks': 1500,
            # Missing avg_clicks, avg_position, avg_ctr, avg_quality
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Should still work with .get() defaults
        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")
        assert insight is not None

        # Cannibalization score should handle missing fields
        score = detector._calculate_cannibalization_score(topic)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_very_high_values(self, mock_repository, mock_config):
        """Test handling of very high metric values."""
        topic = {
            'topic_id': 1,
            'name': 'Very High Traffic',
            'slug': 'very-high-traffic',
            'page_count': 100,
            'avg_clicks': 100000,
            'total_clicks': 10000000,
            'avg_position': 1.0,
            'avg_ctr': 0.15,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Should handle large numbers gracefully
        score = detector._calculate_cannibalization_score(topic)
        assert 0.0 <= score <= 1.0

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_error_in_async_detection(self, mock_repository, mock_config):
        """Test error handling in async detection."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            # Should return 0 and not raise
            count = detector.detect(property="sc-domain:example.com")
            assert count == 0

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_summary_handles_error(self, mock_repository, mock_config):
        """Test that get_topic_summary handles errors gracefully."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(
                side_effect=Exception("Analysis failed")
            )
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            result = detector.get_topic_summary("sc-domain:example.com")

            assert result['available'] is True
            assert 'error' in result
            assert "Analysis failed" in result['error']

    @pytest.mark.skipif(not TOPIC_CLUSTERER_AVAILABLE, reason="TopicClusterer not available")
    def test_summary_with_empty_result(self, mock_repository, mock_config):
        """Test get_topic_summary with no topics found."""
        with patch('insights_core.detectors.topic_strategy.TopicClusterer') as mock_clusterer_class:
            mock_clusterer = Mock()
            mock_clusterer.analyze_topic_performance = AsyncMock(return_value=[])
            mock_clusterer_class.return_value = mock_clusterer

            detector = TopicStrategyDetector(
                mock_repository,
                mock_config,
                use_topic_clustering=True
            )

            result = detector.get_topic_summary("sc-domain:example.com")

            assert result['available'] is True
            assert result['topics_found'] == 0
            assert result['opportunities'] == []
            assert result['cannibalization_risks'] == []
            # Early return doesn't include count fields when empty
            assert 'opportunities_count' not in result or result.get('opportunities_count') == 0
            assert 'cannibalization_count' not in result or result.get('cannibalization_count') == 0


class TestConfidenceCalculation:
    """Tests for confidence score calculation."""

    def test_confidence_based_on_opportunity_score(self, mock_repository, mock_config):
        """Test that confidence increases with opportunity score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # High opportunity score
        topic_high = {
            'topic_id': 1,
            'name': 'High Opportunity',
            'slug': 'high-opportunity',
            'page_count': 1,
            'avg_clicks': 10000,
            'total_clicks': 10000,
            'avg_position': 3.0,
            'avg_ctr': 0.08,
        }

        # Low opportunity score
        topic_low = {
            'topic_id': 2,
            'name': 'Low Opportunity',
            'slug': 'low-opportunity',
            'page_count': 4,
            'avg_clicks': 300,
            'total_clicks': 1200,
            'avg_position': 8.0,
            'avg_ctr': 0.03,
        }

        insight_high = detector._check_underrepresented_topic(topic_high, "sc-domain:example.com")
        insight_low = detector._check_underrepresented_topic(topic_low, "sc-domain:example.com")

        assert insight_high is not None
        assert insight_low is not None
        assert insight_high.confidence > insight_low.confidence

    def test_confidence_capped_at_90_percent(self, mock_repository, mock_config):
        """Test that confidence is capped at 0.9."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Extremely high opportunity score
        topic = {
            'topic_id': 1,
            'name': 'Extreme Opportunity',
            'slug': 'extreme-opportunity',
            'page_count': 1,
            'avg_clicks': 50000,
            'total_clicks': 50000,
            'avg_position': 1.0,
            'avg_ctr': 0.15,
        }

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        assert insight.confidence <= 0.9

    def test_cannibalization_confidence_equals_score(self, mock_repository, mock_config):
        """Test that cannibalization insight confidence equals the score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        topic = {
            'name': 'Test Topic',
            'slug': 'test-topic',
            'page_count': 10,
            'avg_ctr': 0.01,
            'avg_position': 25,
            'total_clicks': 100,
            'avg_clicks': 10,
        }

        score = 0.82

        insight = detector._create_cannibalization_insight(
            topic,
            "sc-domain:example.com",
            score
        )

        assert insight.confidence == score


class TestMetricsContent:
    """Tests for insight metrics content."""

    def test_opportunity_metrics_complete(self, mock_repository, mock_config):
        """Test that opportunity insights include all relevant metrics."""
        topic = {
            'topic_id': 1,
            'name': 'Test Topic',
            'slug': 'test-topic',
            'page_count': 3,
            'avg_clicks': 500,
            'total_clicks': 1500,
            'avg_position': 7.5,
            'avg_ctr': 0.045,
            'avg_quality': 78.5,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        insight = detector._check_underrepresented_topic(topic, "sc-domain:example.com")

        assert insight is not None
        metrics = insight.metrics

        # Check all metrics are included
        assert metrics.topic == 'Test Topic'
        assert metrics.page_count == 3
        assert metrics.total_clicks == 1500
        assert metrics.avg_clicks == 500
        assert metrics.avg_position == 7.5
        assert metrics.avg_ctr == 0.045
        assert hasattr(metrics, 'opportunity_score')

    def test_cannibalization_metrics_complete(self, mock_repository, mock_config):
        """Test that cannibalization insights include all relevant metrics."""
        topic = {
            'name': 'Test Topic',
            'slug': 'test-topic',
            'page_count': 10,
            'avg_clicks': 25,
            'total_clicks': 250,
            'avg_position': 22.0,
            'avg_ctr': 0.012,
            'avg_quality': 65.0,
        }

        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        score = 0.78

        insight = detector._create_cannibalization_insight(
            topic,
            "sc-domain:example.com",
            score
        )

        metrics = insight.metrics

        # Check all metrics are included
        assert metrics.topic == 'Test Topic'
        assert metrics.page_count == 10
        assert metrics.total_clicks == 250
        assert metrics.avg_clicks == 25
        assert metrics.avg_position == 22.0
        assert metrics.avg_ctr == 0.012
        assert metrics.avg_quality == 65.0
        assert metrics.cannibalization_score == 0.78


class TestCannibalizationScoreFactors:
    """Tests for individual factors in cannibalization score calculation."""

    def test_page_count_factor(self, mock_repository, mock_config):
        """Test that page count contributes to cannibalization score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Minimum pages for cannibalization
        topic_min = {
            'page_count': 3,
            'avg_ctr': 0.05,
            'avg_position': 5,
            'total_clicks': 1000,
            'avg_clicks': 333,
        }

        # Many pages
        topic_many = {
            'page_count': 20,
            'avg_ctr': 0.05,
            'avg_position': 5,
            'total_clicks': 1000,
            'avg_clicks': 50,
        }

        score_min = detector._calculate_cannibalization_score(topic_min)
        score_many = detector._calculate_cannibalization_score(topic_many)

        # More pages should result in higher score
        assert score_many > score_min

    def test_ctr_factor(self, mock_repository, mock_config):
        """Test that CTR contributes to cannibalization score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # High CTR
        topic_high_ctr = {
            'page_count': 8,
            'avg_ctr': 0.06,
            'avg_position': 10,
            'total_clicks': 1000,
            'avg_clicks': 125,
        }

        # Low CTR
        topic_low_ctr = {
            'page_count': 8,
            'avg_ctr': 0.005,
            'avg_position': 10,
            'total_clicks': 1000,
            'avg_clicks': 125,
        }

        score_high_ctr = detector._calculate_cannibalization_score(topic_high_ctr)
        score_low_ctr = detector._calculate_cannibalization_score(topic_low_ctr)

        # Lower CTR should result in higher cannibalization score
        assert score_low_ctr > score_high_ctr

    def test_position_factor(self, mock_repository, mock_config):
        """Test that average position contributes to cannibalization score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Good position
        topic_good_pos = {
            'page_count': 8,
            'avg_ctr': 0.03,
            'avg_position': 5,
            'total_clicks': 1000,
            'avg_clicks': 125,
        }

        # Poor position
        topic_poor_pos = {
            'page_count': 8,
            'avg_ctr': 0.03,
            'avg_position': 35,
            'total_clicks': 1000,
            'avg_clicks': 125,
        }

        score_good_pos = detector._calculate_cannibalization_score(topic_good_pos)
        score_poor_pos = detector._calculate_cannibalization_score(topic_poor_pos)

        # Poorer position should result in higher cannibalization score
        assert score_poor_pos > score_good_pos

    def test_clicks_per_page_factor(self, mock_repository, mock_config):
        """Test that clicks per page contributes to cannibalization score."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # High clicks per page
        topic_high_clicks = {
            'page_count': 8,
            'avg_ctr': 0.03,
            'avg_position': 10,
            'total_clicks': 1000,
            'avg_clicks': 125,
        }

        # Low clicks per page
        topic_low_clicks = {
            'page_count': 8,
            'avg_ctr': 0.03,
            'avg_position': 10,
            'total_clicks': 40,
            'avg_clicks': 5,
        }

        score_high_clicks = detector._calculate_cannibalization_score(topic_high_clicks)
        score_low_clicks = detector._calculate_cannibalization_score(topic_low_clicks)

        # Lower clicks per page should result in higher cannibalization score
        assert score_low_clicks > score_high_clicks

    def test_score_capped_at_one(self, mock_repository, mock_config):
        """Test that cannibalization score is capped at 1.0."""
        detector = TopicStrategyDetector(
            mock_repository,
            mock_config,
            use_topic_clustering=False
        )

        # Extreme values that would exceed 1.0
        topic_extreme = {
            'page_count': 50,
            'avg_ctr': 0.001,
            'avg_position': 50,
            'total_clicks': 10,
            'avg_clicks': 0.2,
        }

        score = detector._calculate_cannibalization_score(topic_extreme)

        assert score <= 1.0
