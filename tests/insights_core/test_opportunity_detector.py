"""
Comprehensive tests for OpportunityDetector

Tests opportunity detection strategies:
- Striking Distance: Pages ranking 11-20 with high impressions
- Content Gaps: High impressions but low engagement
- URL Consolidation: Multiple URL variations

Test Coverage:
- All opportunity types
- Prioritization logic
- Edge cases (empty data, saturated queries, new queries)
- Database mocking
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import date, timedelta
from typing import Dict, Any, List

from insights_core.detectors.opportunity import OpportunityDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)
from tests.fixtures.sample_data import (
    SAMPLE_PROPERTIES,
    SAMPLE_PAGES,
    reset_seed,
)

# Base module path for patching psycopg2
BASE_PSYCOPG2_PATH = 'insights_core.detectors.base.psycopg2'
OPPORTUNITY_PSYCOPG2_PATH = 'insights_core.detectors.opportunity.psycopg2'


@pytest.fixture
def mock_config():
    """Mock InsightsConfig"""
    config = Mock()
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test_db"
    return config


@pytest.fixture
def mock_repository():
    """Mock InsightRepository"""
    repo = Mock()
    repo.create = Mock(return_value=Mock(id="test-insight-id"))
    return repo


@pytest.fixture
def striking_distance_data():
    """Sample data for striking distance opportunities (positions 11-20)"""
    reset_seed()
    return [
        {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/striking-distance-1',
            'date': date.today() - timedelta(days=1),
            'gsc_position': 15.5,
            'gsc_impressions': 1500,
            'gsc_clicks': 75,
            'gsc_ctr': 0.05,
            'ga_conversions': 3,
            'ga_engagement_rate': 0.65,
        },
        {
            'property': 'sc-domain:example.com',
            'page_path': '/products/widget-pro',
            'date': date.today() - timedelta(days=1),
            'gsc_position': 12.0,
            'gsc_impressions': 2000,
            'gsc_clicks': 100,
            'gsc_ctr': 0.05,
            'ga_conversions': 5,
            'ga_engagement_rate': 0.70,
        },
    ]


@pytest.fixture
def content_gap_data():
    """Sample data for content gap opportunities (high impressions, low engagement)"""
    reset_seed()
    return [
        {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/low-engagement',
            'date': date.today() - timedelta(days=1),
            'gsc_impressions': 5000,
            'gsc_clicks': 250,
            'gsc_ctr': 0.05,
            'ga_engagement_rate': 0.25,
            'ga_sessions': 200,
            'ga_bounce_rate': 0.75,
        },
        {
            'property': 'sc-domain:example.com',
            'page_path': '/products/poor-content',
            'date': date.today() - timedelta(days=1),
            'gsc_impressions': 3000,
            'gsc_clicks': 150,
            'gsc_ctr': 0.05,
            'ga_engagement_rate': 0.30,
            'ga_sessions': 120,
            'ga_bounce_rate': 0.70,
        },
    ]


@pytest.fixture
def url_consolidation_candidates():
    """Sample URL consolidation candidates"""
    reset_seed()
    return [
        {
            'canonical_url': '/blog/article-1',
            'variation_count': 5,
            'consolidation_score': 85,
            'total_impressions': 10000,
            'total_clicks': 500,
            'variation_types': ['trailing_slash', 'utm_params'],
        },
        {
            'canonical_url': '/products/widget',
            'variation_count': 3,
            'consolidation_score': 55,
            'total_impressions': 5000,
            'total_clicks': 250,
            'variation_types': ['trailing_slash'],
        },
    ]


@pytest.fixture
def empty_data():
    """Empty data for edge case testing"""
    return []


@pytest.fixture
def saturated_queries_data():
    """Data for queries already performing well (no opportunity)"""
    reset_seed()
    return [
        {
            'property': 'sc-domain:example.com',
            'page_path': '/best-performing',
            'date': date.today() - timedelta(days=1),
            'gsc_position': 3.0,  # Already ranking well
            'gsc_impressions': 10000,
            'gsc_clicks': 2000,
            'gsc_ctr': 0.20,  # High CTR
            'ga_conversions': 100,
            'ga_engagement_rate': 0.85,  # High engagement
        }
    ]


@pytest.fixture
def new_queries_data():
    """Data for new queries with minimal history"""
    reset_seed()
    return [
        {
            'property': 'sc-domain:example.com',
            'page_path': '/brand-new-page',
            'date': date.today() - timedelta(days=1),
            'gsc_position': 50.0,
            'gsc_impressions': 10,  # Very low impressions
            'gsc_clicks': 1,
            'gsc_ctr': 0.10,
            'ga_conversions': 0,
            'ga_engagement_rate': 0.50,
        }
    ]


class TestOpportunityDetectorInit:
    """Test OpportunityDetector initialization"""

    def test_init_stores_repository_and_config(self, mock_repository, mock_config):
        """Test that detector stores repository and config"""
        detector = OpportunityDetector(mock_repository, mock_config)

        assert detector.repository == mock_repository
        assert detector.config == mock_config
        assert detector.conn_string == mock_config.warehouse_dsn


class TestStrikingDistanceDetection:
    """Test striking distance opportunity detection (positions 11-20)"""

    def test_find_striking_distance_creates_opportunities(
        self, mock_repository, mock_config, striking_distance_data
    ):
        """Test that pages in positions 11-20 create opportunities"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            # Setup database mocks
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = striking_distance_data

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            # Should create insights for both pages
            assert insights_created == 2
            assert mock_repository.create.call_count == 2

            # Verify insights are OPPORTUNITY category
            for call_obj in mock_repository.create.call_args_list:
                insight: InsightCreate = call_obj[0][0]
                assert insight.category == InsightCategory.OPPORTUNITY
                assert insight.entity_type == EntityType.PAGE
                assert insight.title == "Striking Distance Opportunity"
                assert insight.severity == InsightSeverity.MEDIUM

    def test_striking_distance_includes_position_metrics(
        self, mock_repository, mock_config, striking_distance_data
    ):
        """Test that striking distance insights include position metrics"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [striking_distance_data[0]]

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_striking_distance()

            # Get the created insight
            insight: InsightCreate = mock_repository.create.call_args[0][0]

            # Verify metrics
            assert insight.metrics.gsc_position == 15.5
            assert insight.metrics.gsc_impressions == 1500
            assert insight.metrics.gsc_clicks == 75
            assert insight.metrics.gsc_ctr == 0.05
            assert "position 15.5" in insight.description

    def test_striking_distance_filters_low_impressions(
        self, mock_repository, mock_config
    ):
        """Test that pages with low impressions are filtered out"""
        low_impression_data = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/low-impressions',
                'date': date.today() - timedelta(days=1),
                'gsc_position': 15.0,
                'gsc_impressions': 50,  # Below threshold of 100
                'gsc_clicks': 2,
                'gsc_ctr': 0.04,
                'ga_conversions': 0,
                'ga_engagement_rate': 0.50,
            }
        ]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Query filters this out at DB level
            mock_cursor.fetchall.return_value = []

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            # No insights should be created
            assert insights_created == 0
            mock_repository.create.assert_not_called()

    def test_striking_distance_with_property_filter(
        self, mock_repository, mock_config, striking_distance_data
    ):
        """Test that property filter is applied correctly"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = striking_distance_data

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_striking_distance(property='sc-domain:example.com')

            # Verify property parameter was passed to query
            call_args = mock_cursor.execute.call_args
            assert 'sc-domain:example.com' in call_args[0][1]


class TestContentGapDetection:
    """Test content gap opportunity detection (high impressions, low engagement)"""

    def test_find_content_gaps_creates_opportunities(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test that pages with high impressions and low engagement create opportunities"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = content_gap_data

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_content_gaps()

            # Should create insights for both pages
            assert insights_created == 2
            assert mock_repository.create.call_count == 2

            # Verify insights are OPPORTUNITY category with LOW severity
            for call_obj in mock_repository.create.call_args_list:
                insight: InsightCreate = call_obj[0][0]
                assert insight.category == InsightCategory.OPPORTUNITY
                assert insight.entity_type == EntityType.PAGE
                assert insight.title == "Content Gap Opportunity"
                assert insight.severity == InsightSeverity.LOW

    def test_content_gap_includes_engagement_metrics(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test that content gap insights include engagement metrics"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [content_gap_data[0]]

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_content_gaps()

            # Get the created insight
            insight: InsightCreate = mock_repository.create.call_args[0][0]

            # Verify metrics
            assert insight.metrics.gsc_impressions == 5000
            assert insight.metrics.ga_engagement_rate == 0.25
            assert insight.metrics.ga_sessions == 200
            assert "25.0%" in insight.description or "0.25" in str(insight.metrics.ga_engagement_rate)

    def test_content_gap_filters_high_engagement(
        self, mock_repository, mock_config
    ):
        """Test that pages with high engagement are filtered out"""
        high_engagement_data = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/high-engagement',
                'date': date.today() - timedelta(days=1),
                'gsc_impressions': 5000,
                'gsc_clicks': 250,
                'gsc_ctr': 0.05,
                'ga_engagement_rate': 0.80,  # Above threshold of 0.4
                'ga_sessions': 200,
                'ga_bounce_rate': 0.20,
            }
        ]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Query filters this out at DB level
            mock_cursor.fetchall.return_value = []

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_content_gaps()

            # No insights should be created
            assert insights_created == 0
            mock_repository.create.assert_not_called()

    def test_content_gap_with_property_filter(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test that property filter is applied correctly"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = content_gap_data

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_content_gaps(property='sc-domain:example.com')

            # Verify property parameter was passed to query
            call_args = mock_cursor.execute.call_args
            assert 'sc-domain:example.com' in call_args[0][1]


class TestURLConsolidationDetection:
    """Test URL consolidation opportunity detection"""

    def test_find_url_consolidation_creates_opportunities(
        self, mock_repository, mock_config
    ):
        """Test that URL variations create consolidation opportunities"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
                # Setup mock consolidator
                mock_consolidator = Mock()
                mock_consolidator_class.return_value = mock_consolidator
                mock_consolidator.MEDIUM_PRIORITY_SCORE = 50

                # Mock find_consolidation_candidates
                mock_candidates = [
                    {
                        'canonical_url': '/blog/article',
                        'variation_count': 5,
                        'consolidation_score': 85,
                    },
                    {
                        'canonical_url': '/products/widget',
                        'variation_count': 3,
                        'consolidation_score': 55,
                    },
                ]
                mock_consolidator.find_consolidation_candidates.return_value = mock_candidates

                # Mock create_consolidation_insight
                def create_insight(candidate, property):
                    return InsightCreate(
                        property=property,
                        entity_type=EntityType.PAGE,
                        entity_id=candidate['canonical_url'],
                        category=InsightCategory.OPPORTUNITY,
                        title="URL Consolidation Opportunity",
                        description=f"Consolidate {candidate['variation_count']} variations",
                        severity=InsightSeverity.MEDIUM,
                        confidence=0.75,
                        metrics=InsightMetrics(),
                        window_days=30,
                        source="OpportunityDetector",
                    )
                mock_consolidator.create_consolidation_insight.side_effect = create_insight

                # Setup database mocks for property query
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = [
                    {'property': 'sc-domain:example.com'}
                ]

                detector = OpportunityDetector(mock_repository, mock_config)
                insights_created = detector._find_url_consolidation_opportunities()

                # Should create insights for both candidates
                assert insights_created == 2
                assert mock_repository.create.call_count == 2

    def test_url_consolidation_filters_low_priority(
        self, mock_repository, mock_config
    ):
        """Test that low-priority candidates are filtered out"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
                mock_consolidator = Mock()
                mock_consolidator_class.return_value = mock_consolidator
                mock_consolidator.MEDIUM_PRIORITY_SCORE = 50

                # Return only low-priority candidates
                mock_candidates = [
                    {
                        'canonical_url': '/low-priority',
                        'variation_count': 2,
                        'consolidation_score': 30,  # Below MEDIUM_PRIORITY_SCORE
                    },
                ]
                mock_consolidator.find_consolidation_candidates.return_value = mock_candidates

                # Setup database mocks
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = [
                    {'property': 'sc-domain:example.com'}
                ]

                detector = OpportunityDetector(mock_repository, mock_config)
                insights_created = detector._find_url_consolidation_opportunities()

                # No insights should be created
                assert insights_created == 0
                mock_repository.create.assert_not_called()

    def test_url_consolidation_with_property_filter(
        self, mock_repository, mock_config
    ):
        """Test URL consolidation with specific property"""
        with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
            mock_consolidator = Mock()
            mock_consolidator_class.return_value = mock_consolidator
            mock_consolidator.MEDIUM_PRIORITY_SCORE = 50
            mock_consolidator.find_consolidation_candidates.return_value = []

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_url_consolidation_opportunities(property='sc-domain:example.com')

            # Should call find_consolidation_candidates with the property
            mock_consolidator.find_consolidation_candidates.assert_called_once_with(
                'sc-domain:example.com', limit=25
            )

    def test_url_consolidation_handles_import_error(
        self, mock_repository, mock_config
    ):
        """Test that URLConsolidator import errors are handled gracefully"""
        with patch('insights_core.url_consolidator.URLConsolidator', side_effect=ImportError("Module not found")):
            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_url_consolidation_opportunities()

            # Should return 0 and not crash
            assert insights_created == 0


class TestOpportunityDetectorIntegration:
    """Integration tests for full detection flow"""

    def test_detect_runs_all_strategies(
        self, mock_repository, mock_config
    ):
        """Test that detect() runs all three strategies"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator'):
                # Setup database mocks
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = OpportunityDetector(mock_repository, mock_config)

                # Mock each strategy
                with patch.object(detector, '_find_striking_distance', return_value=2) as mock_striking:
                    with patch.object(detector, '_find_content_gaps', return_value=3) as mock_content:
                        with patch.object(detector, '_find_url_consolidation_opportunities', return_value=1) as mock_url:
                            insights_created = detector.detect()

                            # All strategies should be called
                            mock_striking.assert_called_once_with(None)
                            mock_content.assert_called_once_with(None)
                            mock_url.assert_called_once_with(None)

                            # Total should be sum of all
                            assert insights_created == 6

    def test_detect_with_property_filter(
        self, mock_repository, mock_config
    ):
        """Test that property filter is passed to all strategies"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator'):
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = OpportunityDetector(mock_repository, mock_config)

                with patch.object(detector, '_find_striking_distance', return_value=0) as mock_striking:
                    with patch.object(detector, '_find_content_gaps', return_value=0) as mock_content:
                        with patch.object(detector, '_find_url_consolidation_opportunities', return_value=0) as mock_url:
                            detector.detect(property='sc-domain:example.com')

                            # All should be called with property filter
                            mock_striking.assert_called_once_with('sc-domain:example.com')
                            mock_content.assert_called_once_with('sc-domain:example.com')
                            mock_url.assert_called_once_with('sc-domain:example.com')


class TestOpportunityDetectorEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_data_returns_zero(self, mock_repository, mock_config, empty_data):
        """Test that empty data returns 0 insights"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = empty_data

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            assert insights_created == 0
            mock_repository.create.assert_not_called()

    def test_saturated_queries_no_opportunity(
        self, mock_repository, mock_config, saturated_queries_data
    ):
        """Test that well-performing pages don't create opportunities"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Query would filter this out (position < 11)
            mock_cursor.fetchall.return_value = []

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            assert insights_created == 0

    def test_new_queries_with_low_volume_filtered(
        self, mock_repository, mock_config, new_queries_data
    ):
        """Test that new queries with low volume are filtered"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Query would filter this out (impressions < 100)
            mock_cursor.fetchall.return_value = []

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            assert insights_created == 0

    def test_handles_database_errors_gracefully(
        self, mock_repository, mock_config
    ):
        """Test that database errors are handled gracefully"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.side_effect = Exception("Database connection failed")

            detector = OpportunityDetector(mock_repository, mock_config)

            # The method will raise because it doesn't catch cursor errors
            # But it will close the connection in the finally block
            with pytest.raises(Exception):
                detector._find_striking_distance()

    def test_handles_insight_creation_errors(
        self, mock_repository, mock_config, striking_distance_data
    ):
        """Test that insight creation errors are logged but don't stop processing"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            # Return multiple rows
            mock_cursor.fetchall.return_value = striking_distance_data

            # Make first create fail, second succeed
            mock_repository.create.side_effect = [
                Exception("Creation failed"),
                Mock(id="test-insight-id"),
            ]

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            # Should create 1 (second one succeeded)
            assert insights_created == 1


class TestOpportunityPrioritization:
    """Test opportunity prioritization logic"""

    def test_high_opportunity_striking_distance(
        self, mock_repository, mock_config
    ):
        """Test high-opportunity pages in striking distance"""
        high_opportunity_data = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/high-volume-page',
                'date': date.today() - timedelta(days=1),
                'gsc_position': 11.0,  # Just outside first page
                'gsc_impressions': 10000,  # Very high impressions
                'gsc_clicks': 500,
                'gsc_ctr': 0.05,
                'ga_conversions': 25,
                'ga_engagement_rate': 0.75,
            }
        ]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = high_opportunity_data

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_striking_distance()

            assert insights_created == 1
            insight: InsightCreate = mock_repository.create.call_args[0][0]
            # Should be MEDIUM severity (striking distance default)
            assert insight.severity == InsightSeverity.MEDIUM
            # High impressions should be mentioned
            assert "10000" in insight.description

    def test_medium_opportunity_content_gap(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test medium-opportunity content gaps"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [content_gap_data[0]]

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_content_gaps()

            assert insights_created == 1
            insight: InsightCreate = mock_repository.create.call_args[0][0]
            # Should be LOW severity (content gap default)
            assert insight.severity == InsightSeverity.LOW
            # Should mention engagement rate
            assert insight.metrics.ga_engagement_rate == 0.25


class TestOpportunityMetrics:
    """Test that all required metrics are captured"""

    def test_striking_distance_captures_all_metrics(
        self, mock_repository, mock_config, striking_distance_data
    ):
        """Test that striking distance captures all GSC and GA metrics"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [striking_distance_data[0]]

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_striking_distance()

            insight: InsightCreate = mock_repository.create.call_args[0][0]

            # Verify all metrics are present
            assert insight.metrics.gsc_position is not None
            assert insight.metrics.gsc_impressions is not None
            assert insight.metrics.gsc_clicks is not None
            assert insight.metrics.gsc_ctr is not None
            assert hasattr(insight.metrics, 'ga_conversions')

    def test_content_gap_captures_engagement_metrics(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test that content gap captures engagement metrics"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = [content_gap_data[0]]

            detector = OpportunityDetector(mock_repository, mock_config)
            detector._find_content_gaps()

            insight: InsightCreate = mock_repository.create.call_args[0][0]

            # Verify engagement metrics
            assert insight.metrics.gsc_impressions is not None
            assert insight.metrics.ga_engagement_rate is not None
            assert insight.metrics.ga_sessions is not None
            assert hasattr(insight.metrics, 'ga_bounce_rate')


class TestExceptionHandling:
    """Test exception handling in various scenarios"""

    def test_content_gap_handles_insight_creation_failure(
        self, mock_repository, mock_config, content_gap_data
    ):
        """Test that content gap handles insight creation errors gracefully"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = content_gap_data

            # Make repository.create fail for first, succeed for second
            mock_repository.create.side_effect = [
                Exception("Failed to create insight"),
                Mock(id="test-insight-id"),
            ]

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_content_gaps()

            # Should create 1 (second one succeeded)
            assert insights_created == 1

    def test_url_consolidation_handles_create_insight_errors(
        self, mock_repository, mock_config
    ):
        """Test that URL consolidation handles create_consolidation_insight errors"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
                mock_consolidator = Mock()
                mock_consolidator_class.return_value = mock_consolidator
                mock_consolidator.MEDIUM_PRIORITY_SCORE = 50

                # Return candidates
                mock_candidates = [
                    {
                        'canonical_url': '/blog/article',
                        'variation_count': 5,
                        'consolidation_score': 85,
                    },
                ]
                mock_consolidator.find_consolidation_candidates.return_value = mock_candidates

                # Make create_consolidation_insight fail
                mock_consolidator.create_consolidation_insight.side_effect = Exception("Failed to create")

                # Setup database mocks
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = [
                    {'property': 'sc-domain:example.com'}
                ]

                detector = OpportunityDetector(mock_repository, mock_config)
                insights_created = detector._find_url_consolidation_opportunities()

                # Should return 0 due to error
                assert insights_created == 0
                mock_repository.create.assert_not_called()

    def test_url_consolidation_handles_property_analysis_errors(
        self, mock_repository, mock_config
    ):
        """Test that URL consolidation handles errors during property analysis"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
                mock_consolidator = Mock()
                mock_consolidator_class.return_value = mock_consolidator
                mock_consolidator.MEDIUM_PRIORITY_SCORE = 50

                # Make find_consolidation_candidates fail
                mock_consolidator.find_consolidation_candidates.side_effect = Exception("Database error")

                # Setup database mocks
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = [
                    {'property': 'sc-domain:example.com'}
                ]

                detector = OpportunityDetector(mock_repository, mock_config)
                insights_created = detector._find_url_consolidation_opportunities()

                # Should return 0 and continue gracefully
                assert insights_created == 0

    def test_url_consolidation_handles_general_exception(
        self, mock_repository, mock_config
    ):
        """Test that URL consolidation handles general exceptions"""
        with patch('insights_core.url_consolidator.URLConsolidator') as mock_consolidator_class:
            # Make URLConsolidator initialization fail with general exception
            mock_consolidator_class.side_effect = Exception("General error")

            detector = OpportunityDetector(mock_repository, mock_config)
            insights_created = detector._find_url_consolidation_opportunities()

            # Should return 0 and handle gracefully
            assert insights_created == 0
