"""
Comprehensive Tests for ContentQualityDetector

Tests cover all quality checks:
- Low readability score detection
- Missing meta description detection
- Title too short detection
- Title too long detection
- Missing H1 tags detection
- Thin content detection
- Content cannibalization detection
- Good content produces no insights
- Empty data handling
- Null metrics handling
- Database error handling
- Integration with repository

Coverage target: >95%
Test cases: >10 comprehensive scenarios
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import psycopg2

from insights_core.detectors.content_quality import ContentQualityDetector
from insights_core.models import (
    InsightCreate,
    EntityType,
    InsightCategory,
    InsightSeverity
)
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
from tests.fixtures.sample_data import (
    generate_content_quality_metrics,
    SAMPLE_PROPERTIES,
    SAMPLE_PAGES
)


@pytest.fixture
def mock_config():
    """Create mock config"""
    config = Mock(spec=InsightsConfig)
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test"
    return config


@pytest.fixture
def mock_repository():
    """Create mock repository"""
    repo = Mock(spec=InsightRepository)
    repo.create = Mock(return_value=Mock())
    return repo


@pytest.fixture
def detector(mock_repository, mock_config):
    """Create detector instance with mocks"""
    with patch('insights_core.embeddings.EmbeddingGenerator'):
        detector = ContentQualityDetector(mock_repository, mock_config)
        detector.embedder = None  # Disable embedder for basic tests
        return detector


class TestContentQualityDetectorInitialization:
    """Test detector initialization"""

    def test_detector_initialization(self, mock_repository, mock_config):
        """Test detector initializes correctly"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            assert detector is not None
            assert detector.repository == mock_repository
            assert detector.config == mock_config
            assert detector.MIN_READABILITY_SCORE == 60
            assert detector.MIN_META_DESCRIPTION_LENGTH == 120
            assert detector.MIN_TITLE_LENGTH == 30
            assert detector.MAX_TITLE_LENGTH == 60
            assert detector.MIN_WORD_COUNT == 300

    def test_detector_initialization_with_embedder_success(self, mock_repository, mock_config):
        """Test detector initializes with EmbeddingGenerator successfully"""
        with patch('insights_core.embeddings.EmbeddingGenerator') as mock_embedder_class:
            mock_embedder = Mock()
            mock_embedder_class.return_value = mock_embedder

            detector = ContentQualityDetector(mock_repository, mock_config)

            assert detector.embedder is not None
            assert detector.embedder == mock_embedder
            mock_embedder_class.assert_called_once_with(db_dsn=mock_config.warehouse_dsn)

    def test_detector_initialization_handles_import_error(self, mock_repository, mock_config):
        """Test detector handles ImportError gracefully when EmbeddingGenerator unavailable"""
        with patch('insights_core.embeddings.EmbeddingGenerator', side_effect=ImportError("No module")):
            detector = ContentQualityDetector(mock_repository, mock_config)

            assert detector.embedder is None

    def test_detector_initialization_handles_general_exception(self, mock_repository, mock_config):
        """Test detector handles general exceptions during embedder initialization"""
        with patch('insights_core.embeddings.EmbeddingGenerator', side_effect=Exception("Config error")):
            detector = ContentQualityDetector(mock_repository, mock_config)

            assert detector.embedder is None


class TestContentQualityChecks:
    """Test quality check methods"""

    def test_has_low_readability_detects_low_score(self, detector):
        """Test low readability detection"""
        page = {'flesch_reading_ease': 45.5}
        assert detector._has_low_readability(page) is True

    def test_has_low_readability_ignores_good_score(self, detector):
        """Test readability check ignores good scores"""
        page = {'flesch_reading_ease': 70.0}
        assert detector._has_low_readability(page) is False

    def test_has_low_readability_handles_none(self, detector):
        """Test readability check handles None gracefully"""
        page = {'flesch_reading_ease': None}
        assert detector._has_low_readability(page) is False

    def test_has_low_readability_handles_boundary(self, detector):
        """Test readability check at exact boundary"""
        page = {'flesch_reading_ease': 60.0}
        assert detector._has_low_readability(page) is False

        page = {'flesch_reading_ease': 59.9}
        assert detector._has_low_readability(page) is True

    def test_has_meta_description_issue_detects_missing(self, detector):
        """Test missing meta description detection"""
        page = {'meta_description': None}
        assert detector._has_meta_description_issue(page) is True

    def test_has_meta_description_issue_detects_short(self, detector):
        """Test short meta description detection"""
        page = {'meta_description': 'Too short'}
        assert detector._has_meta_description_issue(page) is True

    def test_has_meta_description_issue_detects_whitespace_only(self, detector):
        """Test whitespace-only meta description detection"""
        page = {'meta_description': '   '}
        assert detector._has_meta_description_issue(page) is True

    def test_has_meta_description_issue_ignores_good_meta(self, detector):
        """Test meta description check ignores good descriptions"""
        page = {'meta_description': 'A' * 125}
        assert detector._has_meta_description_issue(page) is False

    def test_has_short_title_detects_short(self, detector):
        """Test short title detection"""
        page = {'title': 'Short'}
        assert detector._has_short_title(page) is True

    def test_has_short_title_ignores_good_length(self, detector):
        """Test short title check ignores good lengths"""
        page = {'title': 'This is a properly sized title'}
        assert detector._has_short_title(page) is False

    def test_has_short_title_handles_none(self, detector):
        """Test short title check handles None"""
        page = {'title': None}
        # When title is None, _has_short_title returns False (not title and len check)
        assert not detector._has_short_title(page)

    def test_has_short_title_handles_whitespace(self, detector):
        """Test short title check handles whitespace"""
        page = {'title': '   '}
        assert detector._has_short_title(page) is True

    def test_has_long_title_detects_long(self, detector):
        """Test long title detection"""
        page = {'title': 'A' * 65}
        assert detector._has_long_title(page) is True

    def test_has_long_title_ignores_good_length(self, detector):
        """Test long title check ignores good lengths"""
        page = {'title': 'This is a properly sized title'}
        assert detector._has_long_title(page) is False

    def test_has_long_title_handles_none(self, detector):
        """Test long title check handles None"""
        page = {'title': None}
        # When title is None, _has_long_title returns False (not title and len check)
        assert not detector._has_long_title(page)

    def test_has_long_title_handles_boundary(self, detector):
        """Test long title check at exact boundary"""
        page = {'title': 'A' * 60}
        assert detector._has_long_title(page) is False

        page = {'title': 'A' * 61}
        assert detector._has_long_title(page) is True

    def test_has_missing_h1_detects_none(self, detector):
        """Test missing H1 detection with None"""
        page = {'h1_tags': None}
        assert detector._has_missing_h1(page) is True

    def test_has_missing_h1_detects_empty_array(self, detector):
        """Test missing H1 detection with empty array"""
        page = {'h1_tags': []}
        assert detector._has_missing_h1(page) is True

    def test_has_missing_h1_ignores_present_h1(self, detector):
        """Test H1 check ignores pages with H1"""
        page = {'h1_tags': ['Main Heading']}
        assert detector._has_missing_h1(page) is False

    def test_has_missing_h1_ignores_multiple_h1(self, detector):
        """Test H1 check with multiple H1 tags"""
        page = {'h1_tags': ['Heading 1', 'Heading 2']}
        assert detector._has_missing_h1(page) is False

    def test_has_thin_content_detects_thin(self, detector):
        """Test thin content detection"""
        page = {'word_count': 150}
        assert detector._has_thin_content(page) is True

    def test_has_thin_content_ignores_sufficient_content(self, detector):
        """Test thin content check ignores sufficient content"""
        page = {'word_count': 500}
        assert detector._has_thin_content(page) is False

    def test_has_thin_content_handles_none(self, detector):
        """Test thin content check handles None"""
        page = {'word_count': None}
        assert detector._has_thin_content(page) is False

    def test_has_thin_content_handles_boundary(self, detector):
        """Test thin content check at exact boundary"""
        page = {'word_count': 300}
        assert detector._has_thin_content(page) is False

        page = {'word_count': 299}
        assert detector._has_thin_content(page) is True


class TestInsightCreation:
    """Test insight creation methods"""

    def test_create_readability_insight(self, detector):
        """Test low readability insight creation"""
        page = {
            'page_path': '/test-page',
            'flesch_reading_ease': 45.2,
            'word_count': 850
        }

        insight = detector._create_readability_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.property == 'sc-domain:example.com'
        assert insight.entity_type == EntityType.PAGE
        assert insight.entity_id == '/test-page'
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Low Readability Score"
        assert '45.2' in insight.description
        assert insight.severity == InsightSeverity.HIGH
        assert insight.confidence == 0.85
        assert insight.source == "ContentQualityDetector"
        assert insight.window_days == 30
        assert hasattr(insight.metrics, '__pydantic_extra__')
        assert insight.metrics.__pydantic_extra__['flesch_reading_ease'] == 45.2
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'low_readability'

    def test_create_meta_description_insight(self, detector):
        """Test missing meta description insight creation"""
        page = {
            'page_path': '/test-page',
            'meta_description': ''
        }

        insight = detector._create_meta_description_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.entity_id == '/test-page'
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Missing or Short Meta Description"
        assert 'no meta description' in insight.description
        assert insight.severity == InsightSeverity.MEDIUM
        assert insight.confidence == 0.9
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'missing_meta_description'

    def test_create_meta_description_insight_short(self, detector):
        """Test short meta description insight creation"""
        page = {
            'page_path': '/test-page',
            'meta_description': 'A short description'
        }

        insight = detector._create_meta_description_insight(page, 'sc-domain:example.com')

        # The description length should match what's actually in the page
        desc_length = len(page['meta_description'].strip())
        assert str(desc_length) in insight.description or 'short meta description' in insight.description
        assert insight.metrics.__pydantic_extra__['meta_description_length'] == desc_length

    def test_create_short_title_insight(self, detector):
        """Test short title insight creation"""
        page = {
            'page_path': '/test-page',
            'title': 'Short'
        }

        insight = detector._create_short_title_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Title Too Short"
        assert 'Short' in insight.description
        assert insight.severity == InsightSeverity.MEDIUM
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'title_too_short'

    def test_create_long_title_insight(self, detector):
        """Test long title insight creation"""
        page = {
            'page_path': '/test-page',
            'title': 'A' * 70
        }

        insight = detector._create_long_title_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Title Too Long"
        assert '70 chars' in insight.description
        assert insight.severity == InsightSeverity.MEDIUM
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'title_too_long'

    def test_create_long_title_insight_truncates_description(self, detector):
        """Test long title insight truncates very long titles in description"""
        page = {
            'page_path': '/test-page',
            'title': 'A' * 100  # Very long title
        }

        insight = detector._create_long_title_insight(page, 'sc-domain:example.com')

        # Description should truncate title to 80 chars + '...'
        assert '...' in insight.description

    def test_create_missing_h1_insight(self, detector):
        """Test missing H1 insight creation"""
        page = {
            'page_path': '/test-page'
        }

        insight = detector._create_missing_h1_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Missing H1 Tag"
        assert 'missing an H1 tag' in insight.description
        assert insight.severity == InsightSeverity.MEDIUM
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'missing_h1'

    def test_create_thin_content_insight(self, detector):
        """Test thin content insight creation"""
        page = {
            'page_path': '/test-page',
            'word_count': 150
        }

        insight = detector._create_thin_content_insight(page, 'sc-domain:example.com')

        assert isinstance(insight, InsightCreate)
        assert insight.category == InsightCategory.RISK
        assert insight.title == "Thin Content"
        assert '150 words' in insight.description
        assert insight.severity == InsightSeverity.HIGH
        assert insight.metrics.__pydantic_extra__['issue_type'] == 'thin_content'


class TestDetectionLogic:
    """Test main detection logic"""

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_thin_content_scenario(self, mock_connect, detector, mock_repository):
        """Test detector creates insight for thin content"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/thin-page',
                'title': 'This is a properly sized SEO friendly title',
                'meta_description': 'A' * 125,
                'h1_tags': ['Main Heading'],
                'word_count': 150,  # Thin content
                'flesch_reading_ease': 70.0,
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 1
        assert mock_repository.create.call_count == 1
        insight_arg = mock_repository.create.call_args[0][0]
        assert insight_arg.title == "Thin Content"

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_high_bounce_rate_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with high bounce rate content (multiple issues)"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/bounce-page',
                'title': 'Short',  # Too short
                'meta_description': None,  # Missing
                'h1_tags': [],  # Missing H1
                'word_count': 500,  # Sufficient
                'flesch_reading_ease': 45.0,  # Low readability
                'flesch_kincaid_grade': 15.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # Should create 4 insights: readability, meta, title, H1
        assert insights_created == 4
        assert mock_repository.create.call_count == 4

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_low_engagement_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with low engagement content"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/engagement-page',
                'title': 'A' * 65,  # Too long
                'meta_description': 'A' * 125,
                'h1_tags': ['Heading'],
                'word_count': 200,  # Thin
                'flesch_reading_ease': 70.0,
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # Should create 2 insights: long title, thin content
        assert insights_created == 2
        assert mock_repository.create.call_count == 2

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_stale_content_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with stale content (missing meta)"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/stale-page',
                'title': 'This is a properly sized SEO friendly title',
                'meta_description': 'Short meta',  # Too short
                'h1_tags': ['Heading'],
                'word_count': 800,
                'flesch_reading_ease': 70.0,
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # Should create 1 insight: short meta description
        assert insights_created == 1
        assert mock_repository.create.call_count == 1
        insight_arg = mock_repository.create.call_args[0][0]
        assert insight_arg.title == "Missing or Short Meta Description"

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_missing_meta_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with missing meta description only"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/meta-page',
                'title': 'This is a properly sized SEO friendly title',
                'meta_description': None,  # Missing
                'h1_tags': ['Heading'],
                'word_count': 800,
                'flesch_reading_ease': 70.0,
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 1
        insight_arg = mock_repository.create.call_args[0][0]
        assert "no meta description" in insight_arg.description

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_duplicate_content_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with duplicate pages (multiple pages with same issues)"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/page-1',
                'title': 'Short',
                'meta_description': None,
                'h1_tags': [],
                'word_count': 150,
                'flesch_reading_ease': 40.0,
                'flesch_kincaid_grade': 18.0,
                'snapshot_date': datetime.now()
            },
            {
                'property': 'sc-domain:example.com',
                'page_path': '/page-2',
                'title': 'Short',
                'meta_description': None,
                'h1_tags': [],
                'word_count': 150,
                'flesch_reading_ease': 40.0,
                'flesch_kincaid_grade': 18.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # 2 pages x 5 issues each = 10 insights
        assert insights_created == 10
        assert mock_repository.create.call_count == 10

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_good_quality_scenario(self, mock_connect, detector, mock_repository):
        """Test detector creates no insights when content is good"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/good-page',
                'title': 'This is a properly sized SEO friendly title',
                'meta_description': 'A' * 125,  # Good length
                'h1_tags': ['Main Heading'],  # Has H1
                'word_count': 800,  # Sufficient content
                'flesch_reading_ease': 70.0,  # Good readability
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 0
        assert mock_repository.create.call_count == 0

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_mixed_quality_scenario(self, mock_connect, detector, mock_repository):
        """Test detector with mixed quality pages"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/good-page',
                'title': 'This is a properly sized SEO friendly title',
                'meta_description': 'A' * 125,
                'h1_tags': ['Main Heading'],
                'word_count': 800,
                'flesch_reading_ease': 70.0,
                'flesch_kincaid_grade': 8.0,
                'snapshot_date': datetime.now()
            },
            {
                'property': 'sc-domain:example.com',
                'page_path': '/bad-page',
                'title': 'Bad',
                'meta_description': None,
                'h1_tags': [],
                'word_count': 100,
                'flesch_reading_ease': 30.0,
                'flesch_kincaid_grade': 18.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # Only bad page should generate insights (5 issues)
        assert insights_created == 5
        assert mock_repository.create.call_count == 5

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_empty_data_scenario(self, mock_connect, detector, mock_repository):
        """Test detector handles missing data without crashing"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:nonexistent.com')

        assert insights_created == 0
        assert mock_repository.create.call_count == 0

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_null_metrics_scenario(self, mock_connect, detector, mock_repository):
        """Test detector handles null metrics gracefully"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/null-page',
                'title': None,  # Null title
                'meta_description': None,  # Null meta
                'h1_tags': None,  # Null H1
                'word_count': None,  # Null word count
                'flesch_reading_ease': None,  # Null readability
                'flesch_kincaid_grade': None,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        # Should create insights for missing meta and H1 only
        assert insights_created == 2
        assert mock_repository.create.call_count == 2

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_handles_database_error_gracefully(self, mock_connect, detector, mock_repository):
        """Test detector handles database errors without crashing"""
        mock_connect.side_effect = psycopg2.Error("Database connection failed")

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 0
        assert mock_repository.create.call_count == 0

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_handles_general_exception_gracefully(self, mock_connect, detector, mock_repository):
        """Test detector handles general exceptions without crashing"""
        mock_connect.side_effect = Exception("Unexpected error")

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 0
        assert mock_repository.create.call_count == 0

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_with_property_filter(self, mock_connect, detector):
        """Test detector queries with property filter"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        detector.detect(property='sc-domain:example.com')

        query_call = mock_cursor.execute.call_args
        assert query_call is not None
        assert 'property = %s' in query_call[0][0]
        assert 'sc-domain:example.com' in query_call[0][1]

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_detect_without_property_filter(self, mock_connect, detector):
        """Test detector queries without property filter"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        detector.detect()

        query_call = mock_cursor.execute.call_args
        assert query_call is not None
        sql = query_call[0][0]
        params = query_call[0][1]

        assert 'AND property = %s' not in sql
        assert len(params) == 0

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_get_content_data_handles_psycopg2_error(self, mock_connect, detector):
        """Test _get_content_data handles psycopg2 errors gracefully"""
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        result = detector._get_content_data()

        assert result == []

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_get_content_data_handles_general_exception(self, mock_connect, detector):
        """Test _get_content_data handles general exceptions gracefully"""
        mock_connect.side_effect = Exception("Unexpected error")

        result = detector._get_content_data()

        assert result == []


class TestIntegrationWithRepository:
    """Test integration with InsightRepository"""

    @patch('insights_core.detectors.content_quality.psycopg2.connect')
    def test_insights_saved_via_repository(self, mock_connect, detector, mock_repository):
        """Test insights are properly saved via repository.create()"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/test',
                'title': 'Short',
                'meta_description': None,
                'h1_tags': [],
                'word_count': 100,
                'flesch_reading_ease': 30.0,
                'flesch_kincaid_grade': 18.0,
                'snapshot_date': datetime.now()
            }
        ]
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        insights_created = detector.detect(property='sc-domain:example.com')

        assert insights_created == 5
        assert mock_repository.create.call_count == 5

        for call in mock_repository.create.call_args_list:
            assert isinstance(call[0][0], InsightCreate)


class TestCannibalizationDetection:
    """Test cannibalization detection with embeddings"""

    def test_embedder_initialized_in_init(self, mock_repository, mock_config):
        """Test that EmbeddingGenerator is initialized in __init__"""
        with patch('insights_core.embeddings.EmbeddingGenerator') as mock_embedder_class:
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder_class.assert_called_once_with(db_dsn=mock_config.warehouse_dsn)
            assert detector.embedder is not None

    def test_cannibalization_detection_with_high_similarity_and_query_overlap(
        self, mock_repository, mock_config
    ):
        """Test cannibalization creates insight when similarity >0.8 and shared keywords >5"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder = MagicMock()
            async def mock_find_cannibalization(prop, similarity_threshold):
                return [
                    {
                        'page_a': '/page1',
                        'page_b': '/page2',
                        'similarity': 0.85,
                        'title_a': 'Page 1',
                        'title_b': 'Page 2'
                    }
                ]
            mock_embedder.find_cannibalization = mock_find_cannibalization
            detector.embedder = mock_embedder

            with patch.object(detector, '_get_shared_keywords_count', return_value=8):
                insights_created = detector._detect_cannibalization('sc-domain:example.com')

            assert insights_created == 1
            mock_repository.create.assert_called_once()

            insight_arg = mock_repository.create.call_args[0][0]
            assert insight_arg.title == "Content Cannibalization Detected"
            assert insight_arg.category == InsightCategory.DIAGNOSIS
            assert insight_arg.severity == InsightSeverity.MEDIUM
            assert insight_arg.entity_id == '/page1'
            assert insight_arg.metrics.__pydantic_extra__['similar_page'] == '/page2'
            assert insight_arg.metrics.__pydantic_extra__['similarity'] == 0.85
            assert insight_arg.metrics.__pydantic_extra__['shared_keywords'] == 8

    def test_cannibalization_no_insight_below_similarity_threshold(
        self, mock_repository, mock_config
    ):
        """Test no cannibalization insight when similarity < 0.8"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder = MagicMock()
            async def mock_find_cannibalization(prop, similarity_threshold):
                return []
            mock_embedder.find_cannibalization = mock_find_cannibalization
            detector.embedder = mock_embedder

            insights_created = detector._detect_cannibalization('sc-domain:example.com')

            assert insights_created == 0
            mock_repository.create.assert_not_called()

    def test_cannibalization_no_insight_below_query_overlap_threshold(
        self, mock_repository, mock_config
    ):
        """Test no cannibalization insight when shared keywords < 5"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder = MagicMock()
            async def mock_find_cannibalization(prop, similarity_threshold):
                return [
                    {
                        'page_a': '/page1',
                        'page_b': '/page2',
                        'similarity': 0.85,
                        'title_a': 'Page 1',
                        'title_b': 'Page 2'
                    }
                ]
            mock_embedder.find_cannibalization = mock_find_cannibalization
            detector.embedder = mock_embedder

            with patch.object(detector, '_get_shared_keywords_count', return_value=3):
                insights_created = detector._detect_cannibalization('sc-domain:example.com')

            assert insights_created == 0
            mock_repository.create.assert_not_called()

    def test_cannibalization_handles_exception_in_pair_processing(
        self, mock_repository, mock_config
    ):
        """Test cannibalization detection handles exceptions in pair processing"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder = MagicMock()
            async def mock_find_cannibalization(prop, similarity_threshold):
                return [
                    {
                        'page_a': '/page1',
                        'page_b': '/page2',
                        'similarity': 0.85,
                        'title_a': 'Page 1',
                        'title_b': 'Page 2'
                    }
                ]
            mock_embedder.find_cannibalization = mock_find_cannibalization
            detector.embedder = mock_embedder

            with patch.object(detector, '_get_shared_keywords_count', side_effect=Exception("DB error")):
                insights_created = detector._detect_cannibalization('sc-domain:example.com')

            # Should handle exception and return 0
            assert insights_created == 0

    def test_cannibalization_handles_general_exception(
        self, mock_repository, mock_config
    ):
        """Test cannibalization detection handles general exceptions"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_embedder = MagicMock()
            async def mock_find_cannibalization(prop, similarity_threshold):
                raise Exception("Embedder error")
            mock_embedder.find_cannibalization = mock_find_cannibalization
            detector.embedder = mock_embedder

            insights_created = detector._detect_cannibalization('sc-domain:example.com')

            assert insights_created == 0

    def test_get_shared_keywords_count(self, mock_repository, mock_config):
        """Test _get_shared_keywords_count queries database correctly"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (7,)
            mock_cursor.__enter__ = Mock(return_value=mock_cursor)
            mock_cursor.__exit__ = Mock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor

            with patch.object(detector, '_get_db_connection', return_value=mock_conn):
                count = detector._get_shared_keywords_count(
                    'sc-domain:example.com',
                    '/page1',
                    '/page2'
                )

            assert count == 7

            query_call = mock_cursor.execute.call_args
            assert 'fact_gsc_daily' in query_call[0][0]
            assert 'INNER JOIN' in query_call[0][0]
            assert query_call[0][1] == ('sc-domain:example.com', '/page1', 'sc-domain:example.com', '/page2')

    def test_get_shared_keywords_count_handles_exception(self, mock_repository, mock_config):
        """Test _get_shared_keywords_count handles exceptions gracefully"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            with patch.object(detector, '_get_db_connection', side_effect=Exception("DB error")):
                count = detector._get_shared_keywords_count(
                    'sc-domain:example.com',
                    '/page1',
                    '/page2'
                )

            assert count == 0

    def test_cannibalization_metrics_include_all_required_fields(
        self, mock_repository, mock_config
    ):
        """Test cannibalization insight includes all required metrics"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)

            insight = detector._create_cannibalization_insight(
                'sc-domain:example.com',
                '/page-a',
                '/page-b',
                0.87,
                10
            )

            assert insight.metrics.__pydantic_extra__['similar_page'] == '/page-b'
            assert insight.metrics.__pydantic_extra__['similarity'] == 0.87
            assert insight.metrics.__pydantic_extra__['shared_keywords'] == 10
            assert 'recommendation' in insight.metrics.__pydantic_extra__
            assert insight.metrics.__pydantic_extra__['issue_type'] == 'content_cannibalization'

    def test_cannibalization_skipped_if_embedder_not_available(
        self, mock_repository, mock_config
    ):
        """Test cannibalization detection gracefully skips if embedder unavailable"""
        with patch('insights_core.embeddings.EmbeddingGenerator', side_effect=ImportError()):
            detector = ContentQualityDetector(mock_repository, mock_config)

            assert detector.embedder is None

            with patch('insights_core.detectors.content_quality.psycopg2.connect'):
                with patch.object(detector, '_get_content_data', return_value=[]):
                    insights = detector.detect('sc-domain:example.com')

            assert insights == 0

    def test_detect_calls_cannibalization_when_property_provided(
        self, mock_repository, mock_config
    ):
        """Test detect() calls cannibalization detection when property is provided"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)
            detector.embedder = MagicMock()

            with patch.object(detector, '_get_content_data', return_value=[]):
                with patch.object(detector, '_detect_cannibalization', return_value=2) as mock_cann:
                    insights = detector.detect('sc-domain:example.com')

                    mock_cann.assert_called_once_with('sc-domain:example.com')
                    assert insights == 2

    def test_detect_skips_cannibalization_when_no_property(
        self, mock_repository, mock_config
    ):
        """Test detect() skips cannibalization when no property is provided"""
        with patch('insights_core.embeddings.EmbeddingGenerator'):
            detector = ContentQualityDetector(mock_repository, mock_config)
            detector.embedder = MagicMock()

            with patch.object(detector, '_get_content_data', return_value=[]):
                with patch.object(detector, '_detect_cannibalization', return_value=2) as mock_cann:
                    insights = detector.detect()  # No property

                    mock_cann.assert_not_called()
                    assert insights == 0
