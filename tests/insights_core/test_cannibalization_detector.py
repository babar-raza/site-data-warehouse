"""
Tests for CannibalizationDetector

Comprehensive test coverage including:
- Initialization and thresholds
- Main detect method with various scenarios
- Keyword overlap detection
- Overlap score calculation
- Winner/loser identification
- Recommendation logic
- Insight creation
- URL utilities
- Summary statistics
- Edge cases and error handling

All tests use mocked database connections for deterministic, fast execution.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from insights_core.detectors.cannibalization import CannibalizationDetector
from insights_core.models import (
    InsightCreate,
    EntityType,
    InsightCategory,
    InsightSeverity,
    InsightMetrics,
    InsightStatus,
    Insight
)
from tests.fixtures.sample_data import generate_cannibalization_data, reset_seed


@pytest.fixture
def mock_config():
    """Mock InsightsConfig"""
    config = Mock()
    config.warehouse_dsn = "postgresql://test:test@localhost/test"
    return config


@pytest.fixture
def mock_repository():
    """Mock InsightRepository"""
    repository = Mock()
    # Mock create to return a valid Insight
    repository.create = Mock(return_value=Mock(spec=Insight))
    return repository


@pytest.fixture
def detector(mock_repository, mock_config):
    """Create detector with mocked dependencies"""
    with patch.object(CannibalizationDetector, '_get_db_connection'):
        detector = CannibalizationDetector(mock_repository, mock_config)
        return detector


class TestCannibalizationDetectorInit:
    """Test detector initialization"""

    def test_init_success(self, mock_repository, mock_config):
        """Test successful initialization"""
        with patch.object(CannibalizationDetector, '_get_db_connection'):
            detector = CannibalizationDetector(mock_repository, mock_config)
            assert detector.repository == mock_repository
            assert detector.config == mock_config
            assert detector.conn_string == mock_config.warehouse_dsn

    def test_thresholds_set(self, detector):
        """Test that thresholds are properly set"""
        assert detector.CANNIBALIZATION_THRESHOLD == 0.5
        assert detector.MIN_SHARED_KEYWORDS == 3
        assert detector.MIN_KEYWORD_IMPRESSIONS == 100
        assert detector.MIN_PAGE_CLICKS == 10
        assert detector.HIGH_SEVERITY_THRESHOLD == 0.8
        assert detector.MEDIUM_SEVERITY_THRESHOLD == 0.6


class TestDetect:
    """Test main detect method"""

    def test_detect_no_property(self, detector):
        """Test detect returns 0 when no property provided"""
        result = detector.detect(property=None)
        assert result == 0

    def test_detect_empty_property(self, detector):
        """Test detect returns 0 when empty property provided"""
        result = detector.detect(property='')
        assert result == 0

    def test_detect_no_overlaps(self, detector):
        """Test detect when no overlaps found"""
        with patch.object(detector, '_find_keyword_overlaps', return_value=[]):
            result = detector.detect(property='sc-domain:example.com')
            assert result == 0

    def test_detect_with_overlaps_below_threshold(self, detector):
        """Test detect when overlaps below threshold"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.3,  # Below 0.5 threshold
                'shared_keywords': ['keyword1', 'keyword2'],
                'shared_count': 2
            }
        ]

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            result = detector.detect(property='sc-domain:example.com')
            assert result == 0

    def test_detect_with_overlaps_above_threshold(self, detector):
        """Test detect when overlaps above threshold"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.7,  # Above 0.5 threshold
                'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]

        winner_loser = {
            'winner': '/page1',
            'loser': '/page2',
            'winner_stats': {'total_clicks': 100, 'avg_position': 5.0, 'ctr': 0.1},
            'loser_stats': {'total_clicks': 50, 'avg_position': 8.0, 'ctr': 0.05},
            'recommendation': 'consolidate'
        }

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=winner_loser):
                result = detector.detect(property='sc-domain:example.com')
                assert result == 1
                detector.repository.create.assert_called_once()

    def test_detect_avoids_duplicate_pairs(self, detector):
        """Test that detector processes each pair only once"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.7,
                'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            },
            {
                'page_a': '/page2',  # Same pair, reversed
                'page_b': '/page1',
                'overlap_score': 0.7,
                'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
                'shared_count': 3,
                'clicks_a': 50,
                'clicks_b': 100,
                'impressions_a': 500,
                'impressions_b': 1000
            }
        ]

        winner_loser = {
            'winner': '/page1',
            'loser': '/page2',
            'winner_stats': {'total_clicks': 100, 'avg_position': 5.0, 'ctr': 0.1},
            'loser_stats': {'total_clicks': 50, 'avg_position': 8.0, 'ctr': 0.05},
            'recommendation': 'consolidate'
        }

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=winner_loser):
                result = detector.detect(property='sc-domain:example.com')
                # Should only create 1 insight, not 2
                assert result == 1

    def test_detect_with_winner_loser_none(self, detector):
        """Test detect when winner/loser identification fails"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.7,
                'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=None):
                result = detector.detect(property='sc-domain:example.com')
                # Should not create insight when winner/loser can't be identified
                assert result == 0

    def test_detect_handles_repository_error(self, detector):
        """Test detect handles repository errors gracefully"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.7,
                'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]

        winner_loser = {
            'winner': '/page1',
            'loser': '/page2',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50},
            'recommendation': 'consolidate'
        }

        detector.repository.create.side_effect = Exception("Duplicate insight")

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=winner_loser):
                result = detector.detect(property='sc-domain:example.com')
                # Should handle error gracefully and return 0
                assert result == 0

    def test_detect_general_exception_handling(self, detector):
        """Test detect handles general exceptions"""
        with patch.object(detector, '_find_keyword_overlaps', side_effect=Exception("Database error")):
            result = detector.detect(property='sc-domain:example.com')
            assert result == 0


class TestFindKeywordOverlaps:
    """Test keyword overlap detection"""

    def test_find_keyword_overlaps_success(self, detector):
        """Test successful keyword overlap detection"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Mock database response - proper dict
        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'keywords_a': ['keyword1', 'keyword2', 'keyword3', 'keyword4'],
                'keywords_b': ['keyword2', 'keyword3', 'keyword4', 'keyword5'],
                'shared_keywords': ['keyword2', 'keyword3', 'keyword4'],
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            overlap = overlaps[0]
            assert overlap['page_a'] == '/page1'
            assert overlap['page_b'] == '/page2'
            assert overlap['shared_count'] == 3
            # Union: keyword1, keyword2, keyword3, keyword4, keyword5 = 5
            # Intersection: keyword2, keyword3, keyword4 = 3
            # Jaccard: 3/5 = 0.6
            assert overlap['overlap_score'] == 0.6

    def test_find_keyword_overlaps_same_keyword_multiple_pages(self, detector):
        """Test same keyword appearing on multiple pages"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Three pages competing for same keywords
        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'keywords_a': ['python tutorial', 'python guide', 'learn python'],
                'keywords_b': ['python tutorial', 'python guide', 'python basics'],
                'shared_keywords': ['python tutorial', 'python guide'],
                'clicks_a': 150,
                'clicks_b': 120,
                'impressions_a': 2000,
                'impressions_b': 1800
            },
            {
                'page_a': '/page1',
                'page_b': '/page3',
                'keywords_a': ['python tutorial', 'python guide', 'learn python'],
                'keywords_b': ['python tutorial', 'python course'],
                'shared_keywords': ['python tutorial'],
                'clicks_a': 150,
                'clicks_b': 80,
                'impressions_a': 2000,
                'impressions_b': 1000
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 2
            # Verify first overlap (page1 vs page2)
            assert overlaps[0]['shared_count'] == 2
            # Verify second overlap (page1 vs page3)
            assert overlaps[1]['shared_count'] == 1

    def test_find_keyword_overlaps_different_intent_keywords(self, detector):
        """Test pages with different intent keywords (no cannibalization)"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # No shared keywords - different intent
        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/buy-shoes',
                'page_b': '/shoe-reviews',
                'keywords_a': ['buy shoes online', 'cheap shoes', 'shoe store'],
                'keywords_b': ['shoe reviews', 'best shoes', 'shoe ratings'],
                'shared_keywords': [],
                'clicks_a': 100,
                'clicks_b': 80,
                'impressions_a': 1200,
                'impressions_b': 1000
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            # Should return empty because no shared keywords
            assert len(overlaps) == 0

    def test_find_keyword_overlaps_single_page_keyword(self, detector):
        """Test when keyword appears on only one page"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Only one page - no pairs to compare
        mock_cursor.fetchall.return_value = []
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 0

    def test_find_keyword_overlaps_high_similarity_urls(self, detector):
        """Test pages with high URL similarity"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/blog/python-tutorial',
                'page_b': '/blog/python-tutorial/',  # Trailing slash variant
                'keywords_a': ['python tutorial', 'learn python', 'python guide'],
                'keywords_b': ['python tutorial', 'learn python', 'python guide'],
                'shared_keywords': ['python tutorial', 'learn python', 'python guide'],
                'clicks_a': 100,
                'clicks_b': 95,
                'impressions_a': 1000,
                'impressions_b': 950
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            # Perfect overlap (100%)
            assert overlaps[0]['overlap_score'] == 1.0

    def test_find_keyword_overlaps_no_cannibalization(self, detector):
        """Test normal scenario with no cannibalization issues"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Minimal overlap - below threshold
        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/products/shoes',
                'page_b': '/products/boots',
                'keywords_a': ['shoes', 'sneakers', 'running shoes', 'casual shoes'],
                'keywords_b': ['boots', 'winter boots', 'hiking boots', 'shoes'],
                'shared_keywords': ['shoes'],
                'clicks_a': 200,
                'clicks_b': 150,
                'impressions_a': 2000,
                'impressions_b': 1500
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            # Low overlap score (1/7 ≈ 0.14)
            assert overlaps[0]['overlap_score'] < 0.5

    def test_find_keyword_overlaps_partial_overlap(self, detector):
        """Test partial keyword overlap scenario"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/seo-tips',
                'page_b': '/seo-guide',
                'keywords_a': ['seo tips', 'seo best practices', 'seo optimization', 'seo tricks'],
                'keywords_b': ['seo guide', 'seo best practices', 'seo optimization', 'seo tutorial'],
                'shared_keywords': ['seo best practices', 'seo optimization'],
                'clicks_a': 120,
                'clicks_b': 100,
                'impressions_a': 1500,
                'impressions_b': 1200
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            # Partial overlap: 2 shared out of 6 unique = 0.33
            overlap_score = overlaps[0]['overlap_score']
            assert 0.3 <= overlap_score <= 0.4

    def test_find_keyword_overlaps_subdomain_variants(self, detector):
        """Test subdomain URL variants"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page_a': 'https://www.example.com/guide',
                'page_b': 'https://blog.example.com/guide',
                'keywords_a': ['guide', 'tutorial', 'how to'],
                'keywords_b': ['guide', 'tutorial', 'walkthrough'],
                'shared_keywords': ['guide', 'tutorial'],
                'clicks_a': 80,
                'clicks_b': 60,
                'impressions_a': 800,
                'impressions_b': 600
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            assert overlaps[0]['page_a'] == 'https://www.example.com/guide'
            assert overlaps[0]['page_b'] == 'https://blog.example.com/guide'

    def test_find_keyword_overlaps_trailing_slash_variants(self, detector):
        """Test trailing slash URL variants"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/resources/documentation',
                'page_b': '/resources/documentation/',
                'keywords_a': ['documentation', 'docs', 'reference'],
                'keywords_b': ['documentation', 'docs', 'reference'],
                'shared_keywords': ['documentation', 'docs', 'reference'],
                'clicks_a': 150,
                'clicks_b': 148,
                'impressions_a': 1500,
                'impressions_b': 1480
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 1
            # Perfect overlap
            assert overlaps[0]['overlap_score'] == 1.0

    def test_find_keyword_overlaps_empty_data(self, detector):
        """Test with empty database result"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            assert len(overlaps) == 0

    def test_find_keyword_overlaps_null_queries(self, detector):
        """Test handling of null/None values in queries"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'keywords_a': None,
                'keywords_b': ['keyword1', 'keyword2'],
                'shared_keywords': None,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            },
            {
                'page_a': '/page3',
                'page_b': '/page4',
                'keywords_a': ['keyword1'],
                'keywords_b': None,
                'shared_keywords': [],
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')

            # Should skip rows with null data
            assert len(overlaps) == 0

    def test_find_keyword_overlaps_database_error(self, detector):
        """Test handling of database errors"""
        with patch.object(detector, '_get_db_connection', side_effect=Exception("DB Error")):
            overlaps = detector._find_keyword_overlaps('sc-domain:example.com')
            assert len(overlaps) == 0


class TestCalculateOverlapScore:
    """Test overlap score calculation"""

    def test_calculate_overlap_score_full_overlap(self, detector):
        """Test score when keywords fully overlap"""
        keywords_a = ['keyword1', 'keyword2', 'keyword3']
        keywords_b = ['keyword1', 'keyword2', 'keyword3']
        score = detector._calculate_overlap_score(keywords_a, keywords_b)
        assert score == 1.0

    def test_calculate_overlap_score_no_overlap(self, detector):
        """Test score when no overlap"""
        keywords_a = ['keyword1', 'keyword2']
        keywords_b = ['keyword3', 'keyword4']
        score = detector._calculate_overlap_score(keywords_a, keywords_b)
        assert score == 0.0

    def test_calculate_overlap_score_partial_overlap(self, detector):
        """Test score with partial overlap"""
        keywords_a = ['keyword1', 'keyword2', 'keyword3']
        keywords_b = ['keyword2', 'keyword3', 'keyword4']
        # Intersection: 2, Union: 4, Score: 0.5
        score = detector._calculate_overlap_score(keywords_a, keywords_b)
        assert score == 0.5

    def test_calculate_overlap_score_empty_lists(self, detector):
        """Test score with empty keyword lists"""
        score = detector._calculate_overlap_score([], [])
        assert score == 0.0

    def test_calculate_overlap_score_one_empty(self, detector):
        """Test score when one list is empty"""
        score = detector._calculate_overlap_score(['keyword1'], [])
        assert score == 0.0

    def test_calculate_overlap_score_duplicate_keywords(self, detector):
        """Test score with duplicate keywords in lists"""
        keywords_a = ['keyword1', 'keyword1', 'keyword2']
        keywords_b = ['keyword1', 'keyword2', 'keyword2']
        # Sets will remove duplicates: {keyword1, keyword2}
        score = detector._calculate_overlap_score(keywords_a, keywords_b)
        assert score == 1.0


class TestIdentifyWinnerLoser:
    """Test winner/loser identification"""

    def test_identify_winner_loser_clear_winner(self, detector):
        """Test when there's a clear winner"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page': '/page1',
                'total_clicks': 100,
                'total_impressions': 1000,
                'avg_position': 3.0,
                'ctr': 0.1
            },
            {
                'page': '/page2',
                'total_clicks': 10,
                'total_impressions': 500,
                'avg_position': 8.0,
                'ctr': 0.02
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            result = detector._identify_winner_loser(
                'sc-domain:example.com',
                '/page1',
                '/page2',
                ['keyword1', 'keyword2']
            )

            assert result is not None
            assert result['winner'] == '/page1'
            assert result['loser'] == '/page2'
            assert result['recommendation'] in ['redirect', 'consolidate', 'differentiate']

    def test_identify_winner_loser_too_close(self, detector):
        """Test when pages are too close to call"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page': '/page1',
                'total_clicks': 50,
                'total_impressions': 500,
                'avg_position': 5.0,
                'ctr': 0.1
            },
            {
                'page': '/page2',
                'total_clicks': 52,
                'total_impressions': 520,
                'avg_position': 5.1,
                'ctr': 0.1
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            result = detector._identify_winner_loser(
                'sc-domain:example.com',
                '/page1',
                '/page2',
                ['keyword1', 'keyword2']
            )

            assert result is not None
            assert result['winner'] is None
            assert result['loser'] is None
            assert result['recommendation'] == 'differentiate'

    def test_identify_winner_loser_missing_data(self, detector):
        """Test when data is missing for one page"""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Only one page has data
        mock_cursor.fetchall.return_value = [
            {
                'page': '/page1',
                'total_clicks': 100,
                'total_impressions': 1000,
                'avg_position': 3.0,
                'ctr': 0.1
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            result = detector._identify_winner_loser(
                'sc-domain:example.com',
                '/page1',
                '/page2',
                ['keyword1', 'keyword2']
            )

            assert result is None

    def test_identify_winner_loser_database_error(self, detector):
        """Test handling of database errors"""
        with patch.object(detector, '_get_db_connection', side_effect=Exception("DB Error")):
            result = detector._identify_winner_loser(
                'sc-domain:example.com',
                '/page1',
                '/page2',
                ['keyword1', 'keyword2']
            )
            assert result is None

    def test_identify_winner_loser_page_b_wins(self, detector):
        """Test when page B is the winner"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchall.return_value = [
            {
                'page': '/page1',
                'total_clicks': 10,
                'total_impressions': 500,
                'avg_position': 8.0,
                'ctr': 0.02
            },
            {
                'page': '/page2',
                'total_clicks': 100,
                'total_impressions': 1000,
                'avg_position': 3.0,
                'ctr': 0.1
            }
        ]
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            result = detector._identify_winner_loser(
                'sc-domain:example.com',
                '/page1',
                '/page2',
                ['keyword1', 'keyword2']
            )

            assert result is not None
            assert result['winner'] == '/page2'
            assert result['loser'] == '/page1'


class TestGetRecommendation:
    """Test recommendation logic"""

    def test_recommendation_redirect(self, detector):
        """Test redirect recommendation for very weak loser"""
        winner_stats = {'total_clicks': 100}
        loser_stats = {'total_clicks': 5}  # 5% of winner
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation == 'redirect'

    def test_recommendation_consolidate(self, detector):
        """Test consolidate recommendation"""
        winner_stats = {'total_clicks': 100}
        loser_stats = {'total_clicks': 25}  # 25% of winner
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation == 'consolidate'

    def test_recommendation_differentiate(self, detector):
        """Test differentiate recommendation for strong loser"""
        winner_stats = {'total_clicks': 100}
        loser_stats = {'total_clicks': 80}  # 80% of winner
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation == 'differentiate'

    def test_recommendation_boundary_redirect(self, detector):
        """Test redirect at boundary (9% clicks)"""
        winner_stats = {'total_clicks': 100}
        loser_stats = {'total_clicks': 9}
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation == 'redirect'

    def test_recommendation_boundary_consolidate(self, detector):
        """Test consolidate at boundary (15% clicks)"""
        winner_stats = {'total_clicks': 100}
        loser_stats = {'total_clicks': 15}
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation == 'consolidate'

    def test_recommendation_with_zero_winner_clicks(self, detector):
        """Test recommendation with zero winner clicks"""
        winner_stats = {'total_clicks': 0}
        loser_stats = {'total_clicks': 50}
        # Should handle division by zero gracefully
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        # With default of 1 for winner_clicks, ratio is 50/1 = 50.0
        assert recommendation == 'differentiate'

    def test_recommendation_with_none_clicks(self, detector):
        """Test recommendation with None clicks"""
        winner_stats = {'total_clicks': None}
        loser_stats = {'total_clicks': None}
        # Should handle None gracefully with defaults
        recommendation = detector._get_recommendation(winner_stats, loser_stats)
        assert recommendation in ['redirect', 'consolidate', 'differentiate']


class TestCreateCannibalizationInsight:
    """Test insight creation"""

    def test_create_insight_high_severity(self, detector):
        """Test creating high severity insight"""
        overlap = {
            'page_a': '/blog/python-tutorial',
            'page_b': '/guides/python-guide',
            'overlap_score': 0.85,  # High severity
            'shared_count': 10,
            'shared_keywords': ['python', 'tutorial', 'guide', 'beginner', 'learning'],
            'clicks_a': 100,
            'clicks_b': 50,
            'impressions_a': 1000,
            'impressions_b': 500,
            'winner': '/blog/python-tutorial',
            'loser': '/guides/python-guide',
            'recommendation': 'consolidate',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.entity_type == EntityType.PAGE
        assert insight.entity_id == '/guides/python-guide'  # Loser is entity
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert insight.confidence >= 0.5
        assert insight.window_days == 30
        assert insight.source == 'CannibalizationDetector'
        assert 'merge' in insight.description.lower() or 'consolidate' in insight.description.lower()

    def test_create_insight_medium_severity(self, detector):
        """Test creating medium severity insight"""
        overlap = {
            'page_a': '/page1',
            'page_b': '/page2',
            'overlap_score': 0.65,  # Medium severity
            'shared_count': 5,
            'shared_keywords': ['keyword1', 'keyword2', 'keyword3', 'keyword4', 'keyword5'],
            'clicks_a': 100,
            'clicks_b': 50,
            'impressions_a': 1000,
            'impressions_b': 500,
            'winner': '/page1',
            'loser': '/page2',
            'recommendation': 'consolidate',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        assert insight.severity == InsightSeverity.MEDIUM

    def test_create_insight_low_severity(self, detector):
        """Test creating low severity insight"""
        overlap = {
            'page_a': '/page1',
            'page_b': '/page2',
            'overlap_score': 0.55,  # Low severity
            'shared_count': 3,
            'shared_keywords': ['keyword1', 'keyword2', 'keyword3'],
            'clicks_a': 100,
            'clicks_b': 50,
            'impressions_a': 1000,
            'impressions_b': 500,
            'winner': '/page1',
            'loser': '/page2',
            'recommendation': 'differentiate',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        assert insight.severity == InsightSeverity.LOW

    def test_create_insight_no_winner(self, detector):
        """Test creating insight when no clear winner"""
        overlap = {
            'page_a': '/page1',
            'page_b': '/page2',
            'overlap_score': 0.7,
            'shared_count': 5,
            'shared_keywords': ['keyword1', 'keyword2', 'keyword3', 'keyword4', 'keyword5'],
            'clicks_a': 100,
            'clicks_b': 95,
            'impressions_a': 1000,
            'impressions_b': 950,
            'winner': None,
            'loser': None,
            'recommendation': 'differentiate',
            'stats_a': {'total_clicks': 100},
            'stats_b': {'total_clicks': 95}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        assert insight.entity_id == '/page1'  # Falls back to page_a
        assert 'differentiate' in insight.description.lower()

    def test_create_insight_redirect_recommendation(self, detector):
        """Test creating insight with redirect recommendation"""
        overlap = {
            'page_a': '/page1',
            'page_b': '/page2',
            'overlap_score': 0.75,
            'shared_count': 5,
            'shared_keywords': ['keyword1', 'keyword2', 'keyword3', 'keyword4', 'keyword5'],
            'clicks_a': 100,
            'clicks_b': 5,
            'impressions_a': 1000,
            'impressions_b': 100,
            'winner': '/page1',
            'loser': '/page2',
            'recommendation': 'redirect',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 5}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        assert 'redirect' in insight.description.lower()

    def test_create_insight_many_shared_keywords(self, detector):
        """Test creating insight with many shared keywords (truncation)"""
        shared_keywords = [f'keyword{i}' for i in range(20)]
        overlap = {
            'page_a': '/page1',
            'page_b': '/page2',
            'overlap_score': 0.9,
            'shared_count': 20,
            'shared_keywords': shared_keywords,
            'clicks_a': 100,
            'clicks_b': 50,
            'impressions_a': 1000,
            'impressions_b': 500,
            'winner': '/page1',
            'loser': '/page2',
            'recommendation': 'consolidate',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50}
        }

        insight = detector._create_cannibalization_insight(overlap, 'sc-domain:example.com')

        # Should include ellipsis for truncated keywords
        assert '...' in insight.description


class TestShortenPath:
    """Test URL shortening utility"""

    def test_shorten_path_short_url(self, detector):
        """Test with already short URL"""
        result = detector._shorten_path('/blog/article')
        assert result == '/blog/article'

    def test_shorten_path_long_url(self, detector):
        """Test with long URL"""
        long_url = '/blog/this-is-a-very-long-article-title-that-exceeds-fifty-characters'
        result = detector._shorten_path(long_url)
        assert len(result) == 50
        assert result.endswith('...')

    def test_shorten_path_full_url(self, detector):
        """Test with full URL including protocol"""
        result = detector._shorten_path('https://example.com/blog/article')
        assert result == '/blog/article'

    def test_shorten_path_none(self, detector):
        """Test with None value"""
        result = detector._shorten_path(None)
        assert result == 'unknown'

    def test_shorten_path_empty_string(self, detector):
        """Test with empty string"""
        result = detector._shorten_path('')
        assert result == 'unknown'

    def test_shorten_path_exactly_50_chars(self, detector):
        """Test with URL exactly 50 characters"""
        url = '/blog/' + 'a' * 44  # Total 50 chars
        result = detector._shorten_path(url)
        assert result == url  # Should not truncate

    def test_shorten_path_http_protocol(self, detector):
        """Test with http protocol"""
        result = detector._shorten_path('http://example.com/page')
        assert result == '/page'


class TestGetCannibalizationSummary:
    """Test summary statistics"""

    def test_get_summary_success(self, detector):
        """Test successful summary retrieval"""
        mock_conn = Mock()
        mock_cursor = Mock()

        mock_cursor.fetchone.return_value = {
            'total_issues': 10,
            'high_severity': 2,
            'medium_severity': 5,
            'low_severity': 3,
            'new_issues': 7,
            'resolved_issues': 3
        }
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            summary = detector.get_cannibalization_summary('sc-domain:example.com')

            assert summary['total_issues'] == 10
            assert summary['high_severity'] == 2
            assert summary['medium_severity'] == 5
            assert summary['low_severity'] == 3
            assert summary['new_issues'] == 7
            assert summary['resolved_issues'] == 3

    def test_get_summary_no_data(self, detector):
        """Test summary when no data exists"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.close = Mock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(detector, '_get_db_connection', return_value=mock_conn):
            summary = detector.get_cannibalization_summary('sc-domain:example.com')
            assert summary == {}

    def test_get_summary_database_error(self, detector):
        """Test summary with database error"""
        with patch.object(detector, '_get_db_connection', side_effect=Exception("DB Error")):
            summary = detector.get_cannibalization_summary('sc-domain:example.com')
            assert summary == {}


class TestIntegration:
    """Integration tests"""

    def test_end_to_end_detection(self, detector):
        """Test complete detection flow"""
        # Mock data for full flow
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.75,
                'shared_keywords': ['kw1', 'kw2', 'kw3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 20,
                'impressions_a': 1000,
                'impressions_b': 500
            }
        ]

        winner_loser = {
            'winner': '/page1',
            'loser': '/page2',
            'winner_stats': {'total_clicks': 100, 'avg_position': 5.0, 'ctr': 0.1},
            'loser_stats': {'total_clicks': 20, 'avg_position': 10.0, 'ctr': 0.04},
            'recommendation': 'redirect'
        }

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=winner_loser):
                result = detector.detect(property='sc-domain:example.com')

                # Verify flow completed
                assert result == 1
                assert detector.repository.create.called

                # Verify insight structure
                call_args = detector.repository.create.call_args[0][0]
                assert isinstance(call_args, InsightCreate)
                assert call_args.category == InsightCategory.RISK
                assert call_args.entity_type == EntityType.PAGE

    def test_multiple_overlaps_detection(self, detector):
        """Test detection with multiple overlap pairs"""
        overlaps = [
            {
                'page_a': '/page1',
                'page_b': '/page2',
                'overlap_score': 0.75,
                'shared_keywords': ['kw1', 'kw2', 'kw3'],
                'shared_count': 3,
                'clicks_a': 100,
                'clicks_b': 50,
                'impressions_a': 1000,
                'impressions_b': 500
            },
            {
                'page_a': '/page3',
                'page_b': '/page4',
                'overlap_score': 0.80,
                'shared_keywords': ['kw4', 'kw5', 'kw6'],
                'shared_count': 3,
                'clicks_a': 150,
                'clicks_b': 60,
                'impressions_a': 1500,
                'impressions_b': 600
            }
        ]

        winner_loser = {
            'winner': '/page1',
            'loser': '/page2',
            'winner_stats': {'total_clicks': 100},
            'loser_stats': {'total_clicks': 50},
            'recommendation': 'consolidate'
        }

        with patch.object(detector, '_find_keyword_overlaps', return_value=overlaps):
            with patch.object(detector, '_identify_winner_loser', return_value=winner_loser):
                result = detector.detect(property='sc-domain:example.com')

                # Should create 2 insights
                assert result == 2
                assert detector.repository.create.call_count == 2
