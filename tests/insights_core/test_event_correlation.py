"""
Comprehensive tests for EventCorrelationEngine

Tests the correlation of SERP ranking changes with trigger events
including content changes, algorithm updates, and technical issues.
Uses mocks to achieve high coverage without requiring external services.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, date, timedelta
import json

from insights_core.event_correlation_engine import (
    EventCorrelationEngine,
    CorrelatedEvent,
    RankingChange,
    EVENT_TYPE_CONTENT_CHANGE,
    EVENT_TYPE_ALGORITHM_UPDATE,
    EVENT_TYPE_TECHNICAL_ISSUE,
    DEFAULT_LOOKBACK_DAYS,
)

# Module paths for patching
PSYCOPG2_PATH = 'insights_core.event_correlation_engine.psycopg2'
SUBPROCESS_PATH = 'insights_core.event_correlation_engine.subprocess'


@pytest.fixture
def mock_db_dsn():
    """Mock database DSN."""
    return "postgresql://test:test@localhost:5432/test_db"


@pytest.fixture
def engine(mock_db_dsn):
    """Create EventCorrelationEngine with mock DSN."""
    return EventCorrelationEngine(db_dsn=mock_db_dsn)


@pytest.fixture
def sample_ranking_change():
    """Sample ranking change for testing."""
    return RankingChange(
        property='sc-domain:example.com',
        page_path='/blog/seo-tips/',
        query='seo tips',
        change_date=date(2025, 1, 20),
        previous_position=5,
        new_position=15,
        change_magnitude=-10
    )


@pytest.fixture
def sample_git_output():
    """Sample git log output for testing."""
    return """abc1234|2025-01-18|John Developer|Update SEO content
content/blog/seo-tips/index.md

def5678|2025-01-15|Jane Developer|Fix title tag
content/blog/seo-tips/index.md
layouts/partials/head.html
"""


@pytest.fixture
def sample_algorithm_updates():
    """Sample algorithm updates from database."""
    return [
        {
            'update_name': 'January 2025 Core Update',
            'update_date': date(2025, 1, 17),
            'update_type': 'core',
            'description': 'Broad core algorithm update',
            'impact_level': 'major'
        },
        {
            'update_name': 'January 2025 Spam Update',
            'update_date': date(2025, 1, 14),
            'update_type': 'spam',
            'description': 'Spam-fighting update',
            'impact_level': 'moderate'
        }
    ]


@pytest.fixture
def sample_cwv_data():
    """Sample Core Web Vitals degradation data."""
    return [
        {
            'date': date(2025, 1, 16),
            'lcp_p75': 3500,
            'fid_p75': 150,
            'cls_p75': 0.15,
            'prev_lcp': 2500,
            'prev_fid': 100,
            'prev_cls': 0.10,
            'lcp_change_pct': 40.0,
            'fid_change_pct': 50.0,
            'cls_change_pct': 50.0
        }
    ]


class TestCorrelatedEvent:
    """Tests for CorrelatedEvent dataclass."""

    def test_to_dict_converts_all_fields(self):
        """Test that to_dict includes all fields."""
        event = CorrelatedEvent(
            event_type=EVENT_TYPE_CONTENT_CHANGE,
            event_date=date(2025, 1, 18),
            details={'commit_hash': 'abc123', 'author': 'John'},
            confidence=0.85,
            days_before_change=2
        )

        result = event.to_dict()

        assert result['event_type'] == EVENT_TYPE_CONTENT_CHANGE
        assert result['event_date'] == '2025-01-18'
        assert result['details']['commit_hash'] == 'abc123'
        assert result['confidence'] == 0.85
        assert result['days_before_change'] == 2

    def test_to_dict_handles_string_date(self):
        """Test to_dict when event_date is already a string."""
        event = CorrelatedEvent(
            event_type=EVENT_TYPE_ALGORITHM_UPDATE,
            event_date='2025-01-17',
            details={'update_name': 'Test Update'},
            confidence=0.75,
            days_before_change=3
        )

        result = event.to_dict()
        assert result['event_date'] == '2025-01-17'


class TestRankingChange:
    """Tests for RankingChange dataclass."""

    def test_to_dict_converts_all_fields(self, sample_ranking_change):
        """Test that to_dict includes all fields."""
        result = sample_ranking_change.to_dict()

        assert result['property'] == 'sc-domain:example.com'
        assert result['page_path'] == '/blog/seo-tips/'
        assert result['query'] == 'seo tips'
        assert result['change_date'] == '2025-01-20'
        assert result['previous_position'] == 5
        assert result['new_position'] == 15
        assert result['change_magnitude'] == -10

    def test_to_dict_handles_none_query(self):
        """Test to_dict when query is None."""
        change = RankingChange(
            property='sc-domain:example.com',
            page_path='/test/',
            query=None,
            change_date=date(2025, 1, 20),
            previous_position=10,
            new_position=20,
            change_magnitude=-10
        )

        result = change.to_dict()
        assert result['query'] is None


class TestEventCorrelationEngineInit:
    """Tests for EventCorrelationEngine initialization."""

    def test_init_with_default_values(self):
        """Test initialization with default values."""
        with patch.dict('os.environ', {'WAREHOUSE_DSN': 'postgresql://test:test@localhost/test'}):
            engine = EventCorrelationEngine()

            assert engine.db_dsn == 'postgresql://test:test@localhost/test'
            assert engine.lookback_days == DEFAULT_LOOKBACK_DAYS

    def test_init_with_custom_values(self, mock_db_dsn):
        """Test initialization with custom values."""
        engine = EventCorrelationEngine(
            db_dsn=mock_db_dsn,
            lookback_days=14,
            git_repo_path='/custom/repo'
        )

        assert engine.db_dsn == mock_db_dsn
        assert engine.lookback_days == 14
        assert engine.git_repo_path == '/custom/repo'

    def test_init_without_dsn_uses_env(self):
        """Test that init uses WAREHOUSE_DSN env var when not provided."""
        with patch.dict('os.environ', {'WAREHOUSE_DSN': 'postgresql://env:test@localhost/envdb'}):
            engine = EventCorrelationEngine()
            assert engine.db_dsn == 'postgresql://env:test@localhost/envdb'


class TestParseDate:
    """Tests for _parse_date method."""

    def test_parse_date_from_string(self, engine):
        """Test parsing date from string."""
        result = engine._parse_date('2025-01-20')
        assert result == date(2025, 1, 20)

    def test_parse_date_from_date_object(self, engine):
        """Test parsing date from date object."""
        input_date = date(2025, 1, 20)
        result = engine._parse_date(input_date)
        assert result == input_date

    def test_parse_date_from_datetime_object(self, engine):
        """Test parsing date from datetime object."""
        input_datetime = datetime(2025, 1, 20, 15, 30)
        result = engine._parse_date(input_datetime)
        assert result == date(2025, 1, 20)

    def test_parse_date_invalid_string_raises_error(self, engine):
        """Test that invalid date string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            engine._parse_date('01-20-2025')

    def test_parse_date_unsupported_type_raises_error(self, engine):
        """Test that unsupported type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported date type"):
            engine._parse_date(12345)


class TestCalculateConfidence:
    """Tests for _calculate_confidence method."""

    def test_confidence_content_change_same_day(self, engine):
        """Test confidence for content change on same day."""
        confidence = engine._calculate_confidence(EVENT_TYPE_CONTENT_CHANGE, 0)

        # Base: 0.85 * Proximity(0 days): 0.95 = 0.8075
        assert 0.80 <= confidence <= 0.82

    def test_confidence_algorithm_update_3_days(self, engine):
        """Test confidence for algorithm update 3 days before."""
        confidence = engine._calculate_confidence(EVENT_TYPE_ALGORITHM_UPDATE, 3)

        # Base: 0.75 * Proximity(3 days): 0.70 = 0.525
        assert 0.52 <= confidence <= 0.53

    def test_confidence_technical_issue_7_days(self, engine):
        """Test confidence for technical issue 7 days before."""
        confidence = engine._calculate_confidence(EVENT_TYPE_TECHNICAL_ISSUE, 7)

        # Base: 0.80 * Proximity(7 days): 0.30 = 0.24
        assert 0.23 <= confidence <= 0.25

    def test_confidence_with_additional_factors(self, engine):
        """Test confidence with additional multiplier factors."""
        additional_factors = {
            'seo_relevance': 1.1,
            'impact': 1.2
        }

        confidence = engine._calculate_confidence(
            EVENT_TYPE_CONTENT_CHANGE,
            0,
            additional_factors
        )

        # Base: 0.85 * Proximity: 0.95 * 1.1 * 1.2 = 1.065...
        # Should be clamped to 1.0
        assert confidence == 1.0

    def test_confidence_clamped_to_max_1(self, engine):
        """Test that confidence is clamped to maximum 1.0."""
        additional_factors = {'boost': 2.0}
        confidence = engine._calculate_confidence(EVENT_TYPE_CONTENT_CHANGE, 0, additional_factors)
        assert confidence <= 1.0

    def test_confidence_unknown_event_type(self, engine):
        """Test confidence for unknown event type uses default base."""
        confidence = engine._calculate_confidence('unknown_type', 0)
        # Default base: 0.5 * Proximity: 0.95 = 0.475
        assert 0.47 <= confidence <= 0.48


class TestGetGitCommits:
    """Tests for _get_git_commits method."""

    def test_get_git_commits_parses_output(self, engine, sample_git_output):
        """Test that git commits are parsed correctly."""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = sample_git_output
            mock_subprocess.run.return_value = mock_result

            events = engine._get_git_commits(
                file_path='/blog/seo-tips/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert len(events) == 2
            assert all(e.event_type == EVENT_TYPE_CONTENT_CHANGE for e in events)

            # Check first commit
            first_event = next(e for e in events if e.details['commit_hash'] == 'abc1234')
            assert first_event.details['author'] == 'John Developer'
            assert 'Update SEO content' in first_event.details['message']

    def test_get_git_commits_handles_git_not_found(self, engine):
        """Test graceful handling when git is not installed."""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_subprocess.run.side_effect = FileNotFoundError("git not found")

            events = engine._get_git_commits(
                file_path='/blog/seo-tips/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert events == []

    def test_get_git_commits_handles_timeout(self, engine):
        """Test graceful handling of git command timeout."""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            import subprocess
            mock_subprocess.run.side_effect = subprocess.TimeoutExpired("git", 30)
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            events = engine._get_git_commits(
                file_path='/blog/seo-tips/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            # Should continue with other patterns
            assert isinstance(events, list)

    def test_get_git_commits_deduplicates_by_hash(self, engine):
        """Test that duplicate commits are deduplicated by hash."""
        duplicate_output = """abc1234|2025-01-18|John|Update
file1.md

abc1234|2025-01-18|John|Update
file2.md
"""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = duplicate_output
            mock_subprocess.run.return_value = mock_result

            events = engine._get_git_commits(
                file_path='/test/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            # Should have only 1 unique commit
            commit_hashes = [e.details['commit_hash'] for e in events]
            assert len(set(commit_hashes)) == len(commit_hashes)

    def test_get_git_commits_calculates_confidence(self, engine):
        """Test that confidence is calculated based on date proximity."""
        git_output = """abc1234|2025-01-19|John|Update content
file.md
"""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = git_output
            mock_subprocess.run.return_value = mock_result

            events = engine._get_git_commits(
                file_path='/test/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert len(events) == 1
            # 1 day before ranking change, should have high confidence
            assert events[0].days_before_change == 1
            assert events[0].confidence > 0.5

    def test_get_git_commits_boosts_seo_keywords(self, engine):
        """Test that commits with SEO keywords get confidence boost."""
        git_output = """abc1234|2025-01-18|John|Update meta description and title
file.md
"""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = git_output
            mock_subprocess.run.return_value = mock_result

            events = engine._get_git_commits(
                file_path='/test/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert len(events) == 1
            # Should have boosted confidence due to SEO keywords
            assert events[0].confidence > 0.6


class TestGetAlgorithmUpdates:
    """Tests for _get_algorithm_updates method."""

    def test_get_algorithm_updates_from_database(self, engine, sample_algorithm_updates):
        """Test fetching algorithm updates from database."""
        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = sample_algorithm_updates

            events = engine._get_algorithm_updates(
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert len(events) == 2
            assert all(e.event_type == EVENT_TYPE_ALGORITHM_UPDATE for e in events)

            # Check core update has higher confidence due to major impact
            core_update = next(e for e in events if 'Core Update' in e.details['update_name'])
            assert core_update.details['impact_level'] == 'major'

    def test_get_algorithm_updates_handles_no_dsn(self):
        """Test that method returns empty list when no DSN configured."""
        engine = EventCorrelationEngine(db_dsn=None)

        events = engine._get_algorithm_updates(
            date_range=(date(2025, 1, 13), date(2025, 1, 20))
        )

        assert events == []

    def test_get_algorithm_updates_handles_db_error(self, engine):
        """Test graceful handling of database errors."""
        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            import psycopg2
            mock_psycopg2.Error = psycopg2.Error
            mock_psycopg2.connect.side_effect = psycopg2.Error("Connection failed")

            events = engine._get_algorithm_updates(
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert events == []

    def test_get_algorithm_updates_major_impact_boosts_confidence(self, engine):
        """Test that major impact updates have boosted confidence."""
        major_update = [{
            'update_name': 'Major Core Update',
            'update_date': date(2025, 1, 19),
            'update_type': 'core',
            'description': 'Major update',
            'impact_level': 'major'
        }]

        minor_update = [{
            'update_name': 'Minor Update',
            'update_date': date(2025, 1, 19),
            'update_type': 'minor',
            'description': 'Minor update',
            'impact_level': 'minor'
        }]

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Test major update
            mock_cursor.fetchall.return_value = major_update
            major_events = engine._get_algorithm_updates(
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            # Test minor update
            mock_cursor.fetchall.return_value = minor_update
            minor_events = engine._get_algorithm_updates(
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert major_events[0].confidence > minor_events[0].confidence


class TestGetTechnicalChanges:
    """Tests for _get_technical_changes method."""

    def test_get_technical_changes_finds_cwv_degradation(self, engine, sample_cwv_data):
        """Test detection of Core Web Vitals degradation."""
        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock table existence check
            mock_cursor.fetchone.side_effect = [
                {'exists': True},  # Table exists
            ]
            mock_cursor.fetchall.side_effect = [
                sample_cwv_data,  # CWV data
                []  # Page errors (empty)
            ]

            events = engine._get_technical_changes(
                page_path='/blog/seo-tips/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20)),
                property='sc-domain:example.com'
            )

            assert len(events) >= 1
            cwv_event = next((e for e in events if e.details.get('issue_type') == 'cwv_degradation'), None)
            assert cwv_event is not None
            assert cwv_event.event_type == EVENT_TYPE_TECHNICAL_ISSUE
            assert 'LCP degraded' in str(cwv_event.details.get('issues', []))

    def test_get_technical_changes_finds_impression_drop(self, engine):
        """Test detection of sudden impression drops."""
        impression_drop_data = [{
            'date': date(2025, 1, 16),
            'impressions': 50,
            'prev_impressions': 200,
            'change_pct': -75.0
        }]

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            mock_cursor.fetchone.return_value = {'exists': False}  # No CWV table
            mock_cursor.fetchall.return_value = impression_drop_data

            events = engine._get_technical_changes(
                page_path='/blog/seo-tips/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20)),
                property='sc-domain:example.com'
            )

            assert len(events) >= 1
            drop_event = next((e for e in events if e.details.get('issue_type') == 'impression_drop'), None)
            assert drop_event is not None
            assert drop_event.details['change_pct'] == -75.0

    def test_get_technical_changes_handles_no_dsn(self):
        """Test that method returns empty list when no DSN configured."""
        engine = EventCorrelationEngine(db_dsn=None)

        events = engine._get_technical_changes(
            page_path='/test/',
            date_range=(date(2025, 1, 13), date(2025, 1, 20))
        )

        assert events == []

    def test_get_technical_changes_handles_db_error(self, engine):
        """Test graceful handling of database errors."""
        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            import psycopg2
            mock_psycopg2.Error = psycopg2.Error
            mock_psycopg2.connect.side_effect = psycopg2.Error("Connection failed")

            events = engine._get_technical_changes(
                page_path='/test/',
                date_range=(date(2025, 1, 13), date(2025, 1, 20))
            )

            assert events == []


class TestFindTriggerEvents:
    """Tests for find_trigger_events method."""

    def test_find_trigger_events_returns_all_event_types(self, engine):
        """Test that find_trigger_events returns events from all sources."""
        content_event = CorrelatedEvent(
            event_type=EVENT_TYPE_CONTENT_CHANGE,
            event_date=date(2025, 1, 18),
            details={'commit_hash': 'abc123'},
            confidence=0.85,
            days_before_change=2
        )

        algo_event = CorrelatedEvent(
            event_type=EVENT_TYPE_ALGORITHM_UPDATE,
            event_date=date(2025, 1, 17),
            details={'update_name': 'Core Update'},
            confidence=0.75,
            days_before_change=3
        )

        tech_event = CorrelatedEvent(
            event_type=EVENT_TYPE_TECHNICAL_ISSUE,
            event_date=date(2025, 1, 16),
            details={'issue_type': 'cwv_degradation'},
            confidence=0.70,
            days_before_change=4
        )

        with patch.object(engine, '_get_git_commits', return_value=[content_event]):
            with patch.object(engine, '_get_algorithm_updates', return_value=[algo_event]):
                with patch.object(engine, '_get_technical_changes', return_value=[tech_event]):
                    events = engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20'
                    )

        assert len(events) == 3
        event_types = {e.event_type for e in events}
        assert EVENT_TYPE_CONTENT_CHANGE in event_types
        assert EVENT_TYPE_ALGORITHM_UPDATE in event_types
        assert EVENT_TYPE_TECHNICAL_ISSUE in event_types

    def test_find_trigger_events_sorted_by_confidence(self, engine):
        """Test that events are sorted by confidence (highest first)."""
        events_unsorted = [
            CorrelatedEvent(EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
                          {'test': 1}, 0.60, 2),
            CorrelatedEvent(EVENT_TYPE_ALGORITHM_UPDATE, date(2025, 1, 17),
                          {'test': 2}, 0.90, 3),
            CorrelatedEvent(EVENT_TYPE_TECHNICAL_ISSUE, date(2025, 1, 16),
                          {'test': 3}, 0.75, 4),
        ]

        with patch.object(engine, '_get_git_commits', return_value=[events_unsorted[0]]):
            with patch.object(engine, '_get_algorithm_updates', return_value=[events_unsorted[1]]):
                with patch.object(engine, '_get_technical_changes', return_value=[events_unsorted[2]]):
                    events = engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20'
                    )

        confidences = [e.confidence for e in events]
        assert confidences == sorted(confidences, reverse=True)

    def test_find_trigger_events_excludes_disabled_sources(self, engine):
        """Test that event sources can be excluded."""
        content_event = CorrelatedEvent(
            EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
            {'commit_hash': 'abc123'}, 0.85, 2
        )

        with patch.object(engine, '_get_git_commits', return_value=[content_event]) as mock_git:
            with patch.object(engine, '_get_algorithm_updates', return_value=[]) as mock_algo:
                with patch.object(engine, '_get_technical_changes', return_value=[]) as mock_tech:
                    events = engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20',
                        include_content_changes=True,
                        include_algorithm_updates=False,
                        include_technical_issues=False
                    )

        mock_git.assert_called_once()
        mock_algo.assert_not_called()
        mock_tech.assert_not_called()
        assert len(events) == 1

    def test_find_trigger_events_handles_errors_gracefully(self, engine):
        """Test that errors in one source don't block others."""
        algo_event = CorrelatedEvent(
            EVENT_TYPE_ALGORITHM_UPDATE, date(2025, 1, 17),
            {'update_name': 'Core Update'}, 0.75, 3
        )

        with patch.object(engine, '_get_git_commits', side_effect=Exception("Git error")):
            with patch.object(engine, '_get_algorithm_updates', return_value=[algo_event]):
                with patch.object(engine, '_get_technical_changes', return_value=[]):
                    events = engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20'
                    )

        # Should still return algorithm update even though git failed
        assert len(events) == 1
        assert events[0].event_type == EVENT_TYPE_ALGORITHM_UPDATE

    def test_find_trigger_events_uses_correct_date_range(self, engine):
        """Test that correct 7-day lookback window is used."""
        with patch.object(engine, '_get_git_commits', return_value=[]) as mock_git:
            with patch.object(engine, '_get_algorithm_updates', return_value=[]):
                with patch.object(engine, '_get_technical_changes', return_value=[]):
                    engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20'
                    )

        # Check that _get_git_commits was called with correct date range
        call_args = mock_git.call_args
        start_date, end_date = call_args[1]['date_range']
        assert end_date == date(2025, 1, 20)
        assert start_date == date(2025, 1, 13)  # 7 days before


class TestStoreCorrelation:
    """Tests for store_correlation method."""

    def test_store_correlation_inserts_record(self, engine, sample_ranking_change):
        """Test that correlation is stored in database."""
        event = CorrelatedEvent(
            event_type=EVENT_TYPE_CONTENT_CHANGE,
            event_date=date(2025, 1, 18),
            details={'commit_hash': 'abc123', 'author': 'John'},
            confidence=0.85,
            days_before_change=2
        )

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {'id': 123}
            mock_psycopg2.extras = MagicMock()

            record_id = engine.store_correlation(sample_ranking_change, event)

            assert record_id == 123
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()

    def test_store_correlation_handles_no_dsn(self, sample_ranking_change):
        """Test that method returns None when no DSN configured."""
        engine = EventCorrelationEngine(db_dsn=None)

        event = CorrelatedEvent(
            EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
            {'commit_hash': 'abc123'}, 0.85, 2
        )

        result = engine.store_correlation(sample_ranking_change, event)
        assert result is None

    def test_store_correlation_handles_db_error(self, engine, sample_ranking_change):
        """Test graceful handling of database errors."""
        event = CorrelatedEvent(
            EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
            {'commit_hash': 'abc123'}, 0.85, 2
        )

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            import psycopg2
            mock_psycopg2.Error = psycopg2.Error
            mock_psycopg2.connect.side_effect = psycopg2.Error("Connection failed")

            result = engine.store_correlation(sample_ranking_change, event)

            assert result is None


class TestFindAndStoreCorrelations:
    """Tests for find_and_store_correlations method."""

    def test_find_and_store_correlations_stores_all_events(self, engine, sample_ranking_change):
        """Test that all found events are stored."""
        events = [
            CorrelatedEvent(EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
                          {'commit_hash': 'abc123'}, 0.85, 2),
            CorrelatedEvent(EVENT_TYPE_ALGORITHM_UPDATE, date(2025, 1, 17),
                          {'update_name': 'Core Update'}, 0.75, 3),
        ]

        with patch.object(engine, 'find_trigger_events', return_value=events):
            with patch.object(engine, 'store_correlation', side_effect=[1, 2]) as mock_store:
                stored_ids = engine.find_and_store_correlations(sample_ranking_change)

        assert stored_ids == [1, 2]
        assert mock_store.call_count == 2

    def test_find_and_store_correlations_handles_partial_failure(self, engine, sample_ranking_change):
        """Test that partial storage failures are handled."""
        events = [
            CorrelatedEvent(EVENT_TYPE_CONTENT_CHANGE, date(2025, 1, 18),
                          {'commit_hash': 'abc123'}, 0.85, 2),
            CorrelatedEvent(EVENT_TYPE_ALGORITHM_UPDATE, date(2025, 1, 17),
                          {'update_name': 'Core Update'}, 0.75, 3),
        ]

        # First store succeeds, second returns None
        with patch.object(engine, 'find_trigger_events', return_value=events):
            with patch.object(engine, 'store_correlation', side_effect=[1, None]):
                stored_ids = engine.find_and_store_correlations(sample_ranking_change)

        assert stored_ids == [1]  # Only successful ID


class TestGetHighConfidenceCorrelations:
    """Tests for get_high_confidence_correlations method."""

    def test_get_high_confidence_correlations_filters_by_confidence(self, engine):
        """Test that only high-confidence correlations are returned."""
        db_records = [
            {'id': 1, 'correlation_confidence': 0.85, 'page_path': '/test1/'},
            {'id': 2, 'correlation_confidence': 0.75, 'page_path': '/test2/'},
        ]

        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = db_records

            results = engine.get_high_confidence_correlations(min_confidence=0.7)

            assert len(results) == 2
            mock_cursor.execute.assert_called_once()
            # Verify query includes confidence filter
            query = mock_cursor.execute.call_args[0][0]
            assert 'correlation_confidence' in query

    def test_get_high_confidence_correlations_filters_by_property(self, engine):
        """Test that property filter is applied."""
        with patch(PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            engine.get_high_confidence_correlations(
                property='sc-domain:example.com',
                min_confidence=0.7
            )

            # Verify query includes property filter
            call_args = mock_cursor.execute.call_args
            params = call_args[0][1]
            assert 'sc-domain:example.com' in params

    def test_get_high_confidence_correlations_handles_no_dsn(self):
        """Test that method returns empty list when no DSN configured."""
        engine = EventCorrelationEngine(db_dsn=None)
        results = engine.get_high_confidence_correlations()
        assert results == []


class TestIntegration:
    """Integration tests for full correlation flow."""

    def test_full_correlation_flow(self, engine, sample_ranking_change, sample_git_output, sample_algorithm_updates):
        """Test complete flow from finding to storing correlations."""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = sample_git_output
            mock_subprocess.run.return_value = mock_result

            with patch(PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value.__enter__.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

                # Algorithm updates query
                mock_cursor.fetchall.side_effect = [
                    sample_algorithm_updates,  # Algorithm updates
                    [],  # CWV data (empty)
                    [],  # Page errors (empty)
                ]
                mock_cursor.fetchone.side_effect = [
                    {'exists': False},  # No CWV table
                ]

                events = engine.find_trigger_events(
                    page_path='/blog/seo-tips/',
                    ranking_change_date=sample_ranking_change.change_date,
                    property=sample_ranking_change.property
                )

                # Should have found events from multiple sources
                assert len(events) > 0

    def test_engine_handles_empty_results(self, engine):
        """Test that engine handles case with no correlated events."""
        with patch.object(engine, '_get_git_commits', return_value=[]):
            with patch.object(engine, '_get_algorithm_updates', return_value=[]):
                with patch.object(engine, '_get_technical_changes', return_value=[]):
                    events = engine.find_trigger_events(
                        page_path='/blog/seo-tips/',
                        ranking_change_date='2025-01-20'
                    )

        assert events == []

    def test_engine_works_without_database(self):
        """Test that engine works for git commits even without database."""
        engine = EventCorrelationEngine(db_dsn=None)

        git_output = """abc1234|2025-01-18|John|Update content
file.md
"""
        with patch(SUBPROCESS_PATH) as mock_subprocess:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = git_output
            mock_subprocess.run.return_value = mock_result

            events = engine.find_trigger_events(
                page_path='/test/',
                ranking_change_date='2025-01-20',
                include_algorithm_updates=False,
                include_technical_issues=False
            )

        assert len(events) == 1
        assert events[0].event_type == EVENT_TYPE_CONTENT_CHANGE
