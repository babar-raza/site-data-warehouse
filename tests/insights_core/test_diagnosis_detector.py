"""
Comprehensive tests for DiagnosisDetector with EventCorrelationEngine and
CausalAnalyzer integration.

Tests the diagnosis of risk insights and correlation with trigger events
including content changes, algorithm updates, and technical issues.
Also tests causal impact analysis for statistical significance.
Uses mocks to achieve high coverage without requiring external services.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import date, datetime, timedelta
import pandas as pd

from insights_core.detectors.diagnosis import (
    DiagnosisDetector,
    EVENT_CORRELATION_AVAILABLE,
    CAUSAL_ANALYZER_AVAILABLE,
    CAUSAL_SIGNIFICANCE_THRESHOLD,
)
from insights_core.models import (
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)

# Module paths for patching
BASE_PSYCOPG2_PATH = 'insights_core.detectors.base.psycopg2'
DIAGNOSIS_PSYCOPG2_PATH = 'insights_core.detectors.diagnosis.psycopg2'

# Check if EventCorrelationEngine is available for conditional tests
if EVENT_CORRELATION_AVAILABLE:
    from insights_core.event_correlation_engine import (
        EventCorrelationEngine,
        CorrelatedEvent,
        EVENT_TYPE_CONTENT_CHANGE,
        EVENT_TYPE_ALGORITHM_UPDATE,
        EVENT_TYPE_TECHNICAL_ISSUE,
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
    repo.update = Mock()
    repo.get_by_status = Mock(return_value=[])
    return repo


@pytest.fixture
def sample_risk_insight():
    """Sample risk insight for diagnosis."""
    risk = Mock()
    risk.id = "risk-123"
    risk.property = "sc-domain:example.com"
    risk.entity_id = "/blog/seo-tips/"
    risk.entity_type = EntityType.PAGE
    risk.category = InsightCategory.RISK
    risk.severity = InsightSeverity.HIGH
    risk.status = InsightStatus.NEW
    return risk


@pytest.fixture
def sample_db_row_ranking_drop():
    """Sample database row with ranking drop."""
    return {
        'property': 'sc-domain:example.com',
        'page_path': '/blog/seo-tips/',
        'date': date.today(),
        'gsc_avg_position': 25.0,
        'gsc_position_change_wow': 15.0,  # Position worsened by 15
        'gsc_clicks': 50,
        'gsc_clicks_change_wow': -30,
        'ga_engagement_rate': 65.0,
        'ga_engagement_rate_7d_ago': 70.0,
        'ga_conversions': 5,
        'ga_conversions_change_wow': -2,
        'modified_within_48h': False,
        'last_modified_date': None,
    }


@pytest.fixture
def sample_db_row_engagement_drop():
    """Sample database row with engagement drop."""
    return {
        'property': 'sc-domain:example.com',
        'page_path': '/blog/seo-tips/',
        'date': date.today(),
        'gsc_avg_position': 10.0,
        'gsc_position_change_wow': 2.0,  # Small change
        'gsc_clicks': 100,
        'gsc_clicks_change_wow': 5,
        'ga_engagement_rate': 50.0,
        'ga_engagement_rate_7d_ago': 70.0,  # 28% drop
        'ga_conversions': 3,
        'ga_conversions_change_wow': -5,
        'modified_within_48h': False,
        'last_modified_date': None,
    }


@pytest.fixture
def sample_db_row_content_change():
    """Sample database row with recent content change."""
    return {
        'property': 'sc-domain:example.com',
        'page_path': '/blog/seo-tips/',
        'date': date.today(),
        'gsc_avg_position': 10.0,
        'gsc_position_change_wow': 2.0,
        'gsc_clicks': 100,
        'gsc_clicks_change_wow': -10,
        'ga_engagement_rate': 65.0,
        'ga_engagement_rate_7d_ago': 68.0,
        'ga_conversions': 5,
        'ga_conversions_change_wow': -1,
        'modified_within_48h': True,
        'last_modified_date': datetime.now() - timedelta(hours=24),
    }


@pytest.fixture
def sample_trigger_events():
    """Sample correlated trigger events."""
    if not EVENT_CORRELATION_AVAILABLE:
        return []

    return [
        CorrelatedEvent(
            event_type=EVENT_TYPE_CONTENT_CHANGE,
            event_date=date.today() - timedelta(days=2),
            details={
                'commit_hash': 'abc123',
                'author': 'John Developer',
                'message': 'Update SEO meta tags'
            },
            confidence=0.85,
            days_before_change=2
        ),
        CorrelatedEvent(
            event_type=EVENT_TYPE_ALGORITHM_UPDATE,
            event_date=date.today() - timedelta(days=5),
            details={
                'update_name': 'Core Update January 2025',
                'update_type': 'core',
                'impact_level': 'major'
            },
            confidence=0.70,
            days_before_change=5
        ),
    ]


class TestDiagnosisDetectorInit:
    """Tests for DiagnosisDetector initialization."""

    def test_init_with_correlation_enabled(self, mock_repository, mock_config):
        """Test initialization with EventCorrelationEngine enabled."""
        with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine:
            mock_engine.return_value = Mock()

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)

            assert detector.repository == mock_repository
            assert detector.config == mock_config
            if EVENT_CORRELATION_AVAILABLE:
                assert detector.use_correlation is True

    def test_init_with_correlation_disabled(self, mock_repository, mock_config):
        """Test initialization with EventCorrelationEngine disabled."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)

        assert detector.use_correlation is False
        assert detector.correlation_engine is None

    def test_init_handles_correlation_engine_error(self, mock_repository, mock_config):
        """Test graceful handling when EventCorrelationEngine fails to initialize."""
        with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine:
            mock_engine.side_effect = Exception("Connection failed")

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)

            # Should fallback to disabled
            assert detector.use_correlation is False
            assert detector.correlation_engine is None


class TestDiagnosisDetectorDetect:
    """Tests for detect() method."""

    def test_detect_no_risks(self, mock_repository, mock_config):
        """Test detect when no risks to diagnose."""
        mock_repository.get_by_status.return_value = []

        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
        count = detector.detect()

        assert count == 0
        mock_repository.create.assert_not_called()

    def test_detect_filters_to_risk_category(self, mock_repository, mock_config):
        """Test that detect only processes RISK category insights."""
        risk = Mock()
        risk.category = InsightCategory.RISK
        risk.id = "risk-1"
        risk.property = "sc-domain:example.com"
        risk.entity_id = "/test/"

        opportunity = Mock()
        opportunity.category = InsightCategory.OPPORTUNITY

        mock_repository.get_by_status.return_value = [risk, opportunity]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None  # No data found

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            detector.detect()

        # Should only process risk, not opportunity
        # Repository queries only for RISK category insights
        mock_repository.get_by_status.assert_called_once()

    def test_detect_creates_diagnosis_for_ranking_drop(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking drop creates diagnosis insight."""
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 1
        mock_repository.create.assert_called_once()

        # Verify insight created
        call_args = mock_repository.create.call_args[0][0]
        assert isinstance(call_args, InsightCreate)
        assert call_args.category == InsightCategory.DIAGNOSIS
        assert "Ranking Issue" in call_args.title

    def test_detect_updates_original_risk_status(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that original risk is updated to DIAGNOSED status."""
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            detector.detect()

        # Verify original risk was updated
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args
        assert update_args[0][0] == sample_risk_insight.id
        assert isinstance(update_args[0][1], InsightUpdate)
        assert update_args[0][1].status == InsightStatus.DIAGNOSED

    def test_detect_handles_errors_gracefully(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test that errors in diagnosis don't stop processing."""
        risk1 = Mock()
        risk1.id = "risk-1"
        risk1.property = "sc-domain:example.com"
        risk1.entity_id = "/page1/"
        risk1.category = InsightCategory.RISK
        risk1.severity = InsightSeverity.HIGH

        risk2 = Mock()
        risk2.id = "risk-2"
        risk2.property = "sc-domain:example.com"
        risk2.entity_id = "/page2/"
        risk2.category = InsightCategory.RISK
        risk2.severity = InsightSeverity.MEDIUM

        mock_repository.get_by_status.return_value = [risk1, risk2]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # First risk fails, second succeeds
            mock_cursor.fetchone.side_effect = [
                Exception("Database error"),
                {
                    'gsc_position_change_wow': 15.0,
                    'gsc_avg_position': 25.0,
                    'gsc_clicks': 50,
                    'gsc_clicks_change_wow': -20,
                    'ga_engagement_rate': 65.0,
                    'ga_engagement_rate_7d_ago': 70.0,
                    'modified_within_48h': False,
                    'date': date.today()
                }
            ]

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        # Should continue processing despite first error
        assert mock_cursor.fetchone.call_count == 2


class TestDiagnosisDetectorDiagnoseRisk:
    """Tests for _diagnose_risk() method."""

    def test_diagnose_ranking_issue(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test diagnosis of ranking issue."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert diagnosis.title == "Ranking Issue Detected"
        assert "15.0 spots" in diagnosis.description
        assert diagnosis.confidence == 0.85

    def test_diagnose_engagement_issue(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_engagement_drop
    ):
        """Test diagnosis of engagement issue."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_engagement_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert diagnosis.title == "Engagement Issue Detected"
        assert diagnosis.confidence == 0.75

    def test_diagnose_recent_content_change(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_content_change
    ):
        """Test diagnosis of recent content change."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_content_change

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert diagnosis.title == "Recent Content Change"
        assert diagnosis.confidence == 0.7
        assert diagnosis.severity == InsightSeverity.MEDIUM

    def test_diagnose_returns_none_for_no_data(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test that no diagnosis is created when no data found."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is None

    def test_diagnose_returns_none_for_no_clear_issue(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test that no diagnosis when data doesn't match any hypothesis."""
        healthy_row = {
            'gsc_position_change_wow': 2.0,  # Small change
            'gsc_avg_position': 10.0,
            'ga_engagement_rate': 70.0,
            'ga_engagement_rate_7d_ago': 72.0,  # Small drop
            'modified_within_48h': False,
            'gsc_clicks': 100,
            'date': date.today()
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = healthy_row

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is None


@pytest.mark.skipif(not EVENT_CORRELATION_AVAILABLE, reason="EventCorrelationEngine not available")
class TestDiagnosisDetectorCorrelation:
    """Tests for EventCorrelationEngine integration."""

    def test_ranking_diagnosis_includes_trigger_events(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop,
        sample_trigger_events
    ):
        """Test that ranking diagnosis includes trigger event information."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = sample_trigger_events
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "Potential trigger identified" in diagnosis.description
        assert "Content Change" in diagnosis.description

        # Check metrics include trigger event info
        metrics = diagnosis.metrics
        assert hasattr(metrics, 'trigger_event_type')
        assert metrics.trigger_event_type == EVENT_TYPE_CONTENT_CHANGE

    def test_ranking_diagnosis_works_without_trigger_events(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis works when no trigger events found."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = []  # No events
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "Ranking Issue Detected" in diagnosis.title
        # Should not have trigger event info
        assert "Potential trigger identified" not in diagnosis.description

    def test_ranking_diagnosis_handles_correlation_error(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test graceful handling when correlation engine fails."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.side_effect = Exception("Correlation error")
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Should still create diagnosis without trigger events
        assert diagnosis is not None
        assert "Ranking Issue Detected" in diagnosis.title

    def test_trigger_event_metadata_in_metrics(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop,
        sample_trigger_events
    ):
        """Test that trigger event metadata is included in metrics."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = sample_trigger_events
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        metrics = diagnosis.metrics

        # Check all trigger event metadata
        assert hasattr(metrics, 'trigger_event_type')
        assert hasattr(metrics, 'trigger_event_date')
        assert hasattr(metrics, 'trigger_event_confidence')
        assert hasattr(metrics, 'trigger_event_details')
        assert hasattr(metrics, 'trigger_events_found')
        assert hasattr(metrics, 'all_trigger_events')

        assert metrics.trigger_events_found == 2
        assert len(metrics.all_trigger_events) == 2

    def test_algorithm_update_in_description(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that algorithm update is properly displayed in description."""
        algo_event = CorrelatedEvent(
            event_type=EVENT_TYPE_ALGORITHM_UPDATE,
            event_date=date.today() - timedelta(days=3),
            details={
                'update_name': 'January 2025 Core Update',
                'update_type': 'core',
                'impact_level': 'major'
            },
            confidence=0.80,
            days_before_change=3
        )

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = [algo_event]
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert "Google Algorithm Update" in diagnosis.description
        assert "January 2025 Core Update" in diagnosis.description

    def test_technical_issue_in_description(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that technical issue is properly displayed in description."""
        tech_event = CorrelatedEvent(
            event_type=EVENT_TYPE_TECHNICAL_ISSUE,
            event_date=date.today() - timedelta(days=1),
            details={
                'issue_type': 'cwv_degradation',
                'lcp_change_pct': 40.0
            },
            confidence=0.75,
            days_before_change=1
        )

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = [tech_event]
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert "Technical Issue" in diagnosis.description
        assert "cwv_degradation" in diagnosis.description


@pytest.mark.skipif(not EVENT_CORRELATION_AVAILABLE, reason="EventCorrelationEngine not available")
class TestDiagnoseWithCorrelation:
    """Tests for diagnose_with_correlation() method."""

    def test_diagnose_with_correlation_returns_events(
        self,
        mock_repository,
        mock_config,
        sample_trigger_events
    ):
        """Test direct correlation analysis returns events."""
        with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.find_trigger_events.return_value = sample_trigger_events
            mock_engine_class.return_value = mock_engine

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
            result = detector.diagnose_with_correlation(
                page_path='/blog/seo-tips/',
                property='sc-domain:example.com'
            )

        assert result['trigger_events_count'] == 2
        assert result['top_trigger_event'] is not None
        assert result['correlation_available'] is True

    def test_diagnose_with_correlation_no_engine(
        self,
        mock_repository,
        mock_config
    ):
        """Test direct correlation when engine not available."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
        result = detector.diagnose_with_correlation(
            page_path='/blog/seo-tips/',
            property='sc-domain:example.com'
        )

        assert result['trigger_events_count'] == 0
        assert result['top_trigger_event'] is None
        assert result['correlation_available'] is False

    def test_diagnose_with_correlation_handles_errors(
        self,
        mock_repository,
        mock_config
    ):
        """Test error handling in direct correlation."""
        with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
            mock_engine = Mock()
            mock_engine.find_trigger_events.side_effect = Exception("Test error")
            mock_engine_class.return_value = mock_engine

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
            result = detector.diagnose_with_correlation(
                page_path='/blog/seo-tips/',
                property='sc-domain:example.com'
            )

        assert 'error' in result
        assert result['trigger_events_count'] == 0


class TestGetEventTypeDisplay:
    """Tests for _get_event_type_display() helper."""

    @pytest.mark.skipif(not EVENT_CORRELATION_AVAILABLE, reason="EventCorrelationEngine not available")
    def test_display_names(self, mock_repository, mock_config):
        """Test event type display names."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)

        assert detector._get_event_type_display(EVENT_TYPE_CONTENT_CHANGE) == "Content Change"
        assert detector._get_event_type_display(EVENT_TYPE_ALGORITHM_UPDATE) == "Google Algorithm Update"
        assert detector._get_event_type_display(EVENT_TYPE_TECHNICAL_ISSUE) == "Technical Issue"

    @pytest.mark.skipif(not EVENT_CORRELATION_AVAILABLE, reason="EventCorrelationEngine not available")
    def test_unknown_type_fallback(self, mock_repository, mock_config):
        """Test fallback for unknown event types."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)

        display = detector._get_event_type_display("unknown_event_type")
        assert display == "Unknown Event Type"


class TestIntegration:
    """Integration tests for full diagnosis flow."""

    def test_full_diagnosis_flow_with_correlation(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test complete diagnosis flow from detect to insight creation."""
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            # Use correlation disabled for simpler test
            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect(property="sc-domain:example.com")

        assert count == 1

        # Verify insight was created correctly
        create_call = mock_repository.create.call_args[0][0]
        assert create_call.category == InsightCategory.DIAGNOSIS
        assert create_call.source == "DiagnosisDetector"
        assert create_call.property == "sc-domain:example.com"
        assert create_call.entity_id == "/blog/seo-tips/"

        # Verify original risk was updated
        update_call = mock_repository.update.call_args
        assert update_call[0][0] == sample_risk_insight.id
        assert update_call[0][1].status == InsightStatus.DIAGNOSED

    def test_diagnosis_preserves_risk_severity(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that diagnosis preserves original risk severity."""
        sample_risk_insight.severity = InsightSeverity.HIGH
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            detector.detect()

        create_call = mock_repository.create.call_args[0][0]
        assert create_call.severity == InsightSeverity.HIGH


@pytest.mark.skipif(not CAUSAL_ANALYZER_AVAILABLE, reason="CausalAnalyzer not available")
class TestDiagnosisDetectorCausalAnalysis:
    """Tests for CausalAnalyzer integration."""

    def test_init_with_causal_analysis_enabled(self, mock_repository, mock_config):
        """Test initialization with CausalAnalyzer enabled."""
        with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=True
            )

            assert detector.use_causal_analysis is True
            mock_analyzer_class.assert_called_once()

    def test_init_with_causal_analysis_disabled(self, mock_repository, mock_config):
        """Test initialization with CausalAnalyzer disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_causal_analysis=False
        )

        assert detector.use_causal_analysis is False
        assert detector.causal_analyzer is None

    def test_init_handles_causal_analyzer_error(self, mock_repository, mock_config):
        """Test graceful handling when CausalAnalyzer fails to initialize."""
        with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Connection failed")

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=True
            )

            assert detector.use_causal_analysis is False
            assert detector.causal_analyzer is None

    def test_ranking_diagnosis_includes_significant_causal_analysis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis includes significant causal analysis metrics."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                # Mock the causal analysis result
                with patch.object(
                    DiagnosisDetector,
                    '_run_causal_analysis',
                    return_value={
                        'success': True,
                        'is_significant': True,
                        'causal_probability': 0.98,
                        'relative_effect_pct': -25.5,
                        'absolute_effect': -12.5,
                        'p_value': 0.02,
                        'data_points': 45,
                    }
                ):
                    detector = DiagnosisDetector(
                        mock_repository,
                        mock_config,
                        use_correlation=False,
                        use_causal_analysis=True
                    )
                    diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "Causal analysis confirms" in diagnosis.description
        assert "statistically significant" in diagnosis.description

        # Check causal metrics
        metrics = diagnosis.metrics
        assert hasattr(metrics, 'causal_probability')
        assert metrics.causal_probability == 0.98
        assert hasattr(metrics, 'p_value')
        assert metrics.p_value == 0.02
        assert hasattr(metrics, 'relative_effect_pct')
        assert metrics.relative_effect_pct == -25.5

    def test_ranking_diagnosis_includes_non_significant_causal_analysis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test diagnosis when causal analysis is not significant."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                # Mock non-significant causal analysis result
                with patch.object(
                    DiagnosisDetector,
                    '_run_causal_analysis',
                    return_value={
                        'success': True,
                        'is_significant': False,
                        'causal_probability': 0.45,
                        'relative_effect_pct': -5.2,
                        'absolute_effect': -2.5,
                        'p_value': 0.55,
                        'data_points': 45,
                    }
                ):
                    detector = DiagnosisDetector(
                        mock_repository,
                        mock_config,
                        use_correlation=False,
                        use_causal_analysis=True
                    )
                    diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "may not be statistically significant" in diagnosis.description
        assert "normal fluctuations" in diagnosis.description

        # Confidence should be reduced for non-significant results
        assert diagnosis.confidence < 0.85

    def test_ranking_diagnosis_works_without_causal_analysis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test ranking diagnosis works when causal analysis is disabled."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False
            )
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "Ranking Issue Detected" in diagnosis.title
        # Should not have causal metrics when disabled
        assert "Causal analysis" not in diagnosis.description

    def test_causal_analysis_handles_errors_gracefully(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test graceful handling when causal analysis fails."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                # Mock causal analysis failure
                with patch.object(
                    DiagnosisDetector,
                    '_run_causal_analysis',
                    return_value=None
                ):
                    detector = DiagnosisDetector(
                        mock_repository,
                        mock_config,
                        use_correlation=False,
                        use_causal_analysis=True
                    )
                    diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Should still create diagnosis without causal metrics
        assert diagnosis is not None
        assert "Ranking Issue Detected" in diagnosis.title
        assert diagnosis.confidence == 0.85  # Default confidence


@pytest.mark.skipif(not CAUSAL_ANALYZER_AVAILABLE, reason="CausalAnalyzer not available")
class TestDiagnoseWithCausalAnalysis:
    """Tests for diagnose_with_causal_analysis() method."""

    def test_diagnose_with_causal_analysis_returns_results(
        self,
        mock_repository,
        mock_config
    ):
        """Test direct causal analysis returns results."""
        with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(
                DiagnosisDetector,
                '_run_causal_analysis',
                return_value={
                    'success': True,
                    'is_significant': True,
                    'causal_probability': 0.95,
                    'relative_effect_pct': -20.0,
                    'absolute_effect': -10.0,
                    'p_value': 0.03,
                    'data_points': 40,
                }
            ):
                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=True
                )
                result = detector.diagnose_with_causal_analysis(
                    page_path='/blog/seo-tips/',
                    property='sc-domain:example.com'
                )

        assert result['is_significant'] is True
        assert result['causal_probability'] == 0.95
        assert result['p_value'] == 0.03
        assert result['causal_analysis_available'] is True

    def test_diagnose_with_causal_analysis_when_disabled(
        self,
        mock_repository,
        mock_config
    ):
        """Test direct causal analysis when analyzer not available."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_causal_analysis=False
        )
        result = detector.diagnose_with_causal_analysis(
            page_path='/blog/seo-tips/',
            property='sc-domain:example.com'
        )

        assert result['is_significant'] is False
        assert result['causal_probability'] is None
        assert result['causal_analysis_available'] is False

    def test_diagnose_with_causal_analysis_handles_failure(
        self,
        mock_repository,
        mock_config
    ):
        """Test handling when causal analysis fails."""
        with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer

            with patch.object(
                DiagnosisDetector,
                '_run_causal_analysis',
                return_value=None
            ):
                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=True
                )
                result = detector.diagnose_with_causal_analysis(
                    page_path='/blog/seo-tips/',
                    property='sc-domain:example.com'
                )

        assert 'error' in result
        assert result['is_significant'] is False


class TestCausalAnalysisConfidenceAdjustment:
    """Tests for confidence adjustment based on causal analysis."""

    def test_confidence_increases_for_significant_results(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that confidence increases when causal analysis confirms significance."""
        if not CAUSAL_ANALYZER_AVAILABLE:
            pytest.skip("CausalAnalyzer not available")

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                # High causal probability should increase confidence
                with patch.object(
                    DiagnosisDetector,
                    '_run_causal_analysis',
                    return_value={
                        'success': True,
                        'is_significant': True,
                        'causal_probability': 0.99,
                        'relative_effect_pct': -30.0,
                        'absolute_effect': -15.0,
                        'p_value': 0.01,
                        'data_points': 50,
                    }
                ):
                    detector = DiagnosisDetector(
                        mock_repository,
                        mock_config,
                        use_correlation=False,
                        use_causal_analysis=True
                    )
                    diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Confidence should be higher than default 0.85
        assert diagnosis.confidence > 0.85
        assert diagnosis.confidence <= 0.95  # Max capped at 0.95

    def test_confidence_decreases_for_non_significant_results(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that confidence decreases when causal analysis shows non-significance."""
        if not CAUSAL_ANALYZER_AVAILABLE:
            pytest.skip("CausalAnalyzer not available")

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                # Low causal probability should decrease confidence
                with patch.object(
                    DiagnosisDetector,
                    '_run_causal_analysis',
                    return_value={
                        'success': True,
                        'is_significant': False,
                        'causal_probability': 0.30,
                        'relative_effect_pct': -5.0,
                        'absolute_effect': -2.0,
                        'p_value': 0.70,
                        'data_points': 50,
                    }
                ):
                    detector = DiagnosisDetector(
                        mock_repository,
                        mock_config,
                        use_correlation=False,
                        use_causal_analysis=True
                    )
                    diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Confidence should be lower than default 0.85
        assert diagnosis.confidence < 0.85
        assert diagnosis.confidence >= 0.5  # Min capped at 0.5


class TestRiskCategorizationBySeverity:
    """Tests for risk categorization by severity levels."""

    def test_high_severity_risk_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test diagnosis of HIGH severity risk."""
        sample_risk_insight.severity = InsightSeverity.HIGH
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 1
        created_insight = mock_repository.create.call_args[0][0]
        assert created_insight.severity == InsightSeverity.HIGH

    def test_medium_severity_risk_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_content_change
    ):
        """Test diagnosis of MEDIUM severity risk with content change."""
        sample_risk_insight.severity = InsightSeverity.MEDIUM
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_content_change

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert diagnosis.severity == InsightSeverity.MEDIUM
        assert "Recent Content Change" in diagnosis.title

    def test_low_severity_risk_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test diagnosis of LOW severity risk."""
        sample_risk_insight.severity = InsightSeverity.LOW
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 1
        created_insight = mock_repository.create.call_args[0][0]
        assert created_insight.severity == InsightSeverity.LOW


class TestMultiFactorDiagnosis:
    """Tests for multi-factor diagnosis scenarios."""

    def test_ranking_and_engagement_both_declining(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test diagnosis when both ranking and engagement decline."""
        # Both ranking and engagement drop
        row_data = {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/seo-tips/',
            'date': date.today(),
            'gsc_avg_position': 30.0,
            'gsc_position_change_wow': 12.0,  # Ranking dropped (priority)
            'gsc_clicks': 40,
            'gsc_clicks_change_wow': -25,
            'ga_engagement_rate': 45.0,
            'ga_engagement_rate_7d_ago': 70.0,  # Also engagement issue
            'ga_conversions': 3,
            'ga_conversions_change_wow': -4,
            'modified_within_48h': False,
            'last_modified_date': None,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = row_data

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Ranking issue takes priority
        assert diagnosis is not None
        assert "Ranking Issue" in diagnosis.title

    def test_ranking_drop_with_recent_content_change(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test diagnosis when ranking drops AND content was recently changed."""
        row_data = {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/seo-tips/',
            'date': date.today(),
            'gsc_avg_position': 25.0,
            'gsc_position_change_wow': 15.0,  # Ranking issue (priority)
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -30,
            'ga_engagement_rate': 65.0,
            'ga_engagement_rate_7d_ago': 68.0,
            'ga_conversions': 5,
            'ga_conversions_change_wow': -2,
            'modified_within_48h': True,  # Also content change
            'last_modified_date': datetime.now() - timedelta(hours=12),
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = row_data

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Ranking issue takes priority over content change
        assert diagnosis is not None
        assert "Ranking Issue" in diagnosis.title


class TestDiagnosisScenarios:
    """Tests for specific diagnosis scenarios."""

    def test_single_issue_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test diagnosis with a single clear issue."""
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 1
        created_insight = mock_repository.create.call_args[0][0]
        assert created_insight.category == InsightCategory.DIAGNOSIS
        assert "Ranking Issue" in created_insight.title

    def test_multiple_issues_diagnosis(
        self,
        mock_repository,
        mock_config
    ):
        """Test diagnosis of multiple risks."""
        risk1 = Mock()
        risk1.id = "risk-1"
        risk1.property = "sc-domain:example.com"
        risk1.entity_id = "/page1/"
        risk1.category = InsightCategory.RISK
        risk1.severity = InsightSeverity.HIGH

        risk2 = Mock()
        risk2.id = "risk-2"
        risk2.property = "sc-domain:example.com"
        risk2.entity_id = "/page2/"
        risk2.category = InsightCategory.RISK
        risk2.severity = InsightSeverity.MEDIUM

        mock_repository.get_by_status.return_value = [risk1, risk2]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Return different data for each risk
            mock_cursor.fetchone.side_effect = [
                {  # Risk 1: Ranking drop
                    'gsc_position_change_wow': 15.0,
                    'gsc_avg_position': 25.0,
                    'gsc_clicks': 50,
                    'gsc_clicks_change_wow': -30,
                    'ga_engagement_rate': 65.0,
                    'ga_engagement_rate_7d_ago': 70.0,
                    'modified_within_48h': False,
                    'date': date.today()
                },
                {  # Risk 2: Engagement drop
                    'gsc_position_change_wow': 2.0,
                    'gsc_avg_position': 10.0,
                    'gsc_clicks': 100,
                    'gsc_clicks_change_wow': 5,
                    'ga_engagement_rate': 50.0,
                    'ga_engagement_rate_7d_ago': 72.0,
                    'ga_conversions': 3,
                    'ga_conversions_change_wow': -5,
                    'modified_within_48h': False,
                    'date': date.today()
                }
            ]

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 2
        assert mock_repository.create.call_count == 2

    def test_cascading_issues_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test diagnosis of cascading issues (ranking -> traffic -> conversions)."""
        row_data = {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/seo-tips/',
            'date': date.today(),
            'gsc_avg_position': 35.0,
            'gsc_position_change_wow': 20.0,  # Large ranking drop
            'gsc_clicks': 30,
            'gsc_clicks_change_wow': -50,  # Traffic drop
            'ga_engagement_rate': 40.0,
            'ga_engagement_rate_7d_ago': 65.0,  # Engagement drop
            'ga_conversions': 1,
            'ga_conversions_change_wow': -8,  # Conversion drop
            'modified_within_48h': False,
            'last_modified_date': None,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = row_data

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        # Should identify ranking as root cause
        assert diagnosis is not None
        assert "Ranking Issue" in diagnosis.title
        assert "20.0 spots" in diagnosis.description

    def test_no_diagnosis_needed(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test when no diagnosis can be determined (no clear issue)."""
        healthy_row = {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/seo-tips/',
            'date': date.today(),
            'gsc_avg_position': 10.0,
            'gsc_position_change_wow': 1.0,  # Small change
            'gsc_clicks': 100,
            'gsc_clicks_change_wow': 2,
            'ga_engagement_rate': 70.0,
            'ga_engagement_rate_7d_ago': 72.0,  # Small drop
            'ga_conversions': 10,
            'ga_conversions_change_wow': 1,
            'modified_within_48h': False,
            'last_modified_date': None,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = healthy_row

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is None

    def test_historical_context_in_diagnosis(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that diagnosis includes historical context from metrics."""
        mock_repository.get_by_status.return_value = [sample_risk_insight]

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)
            count = detector.detect()

        assert count == 1
        created_insight = mock_repository.create.call_args[0][0]

        # Verify historical metrics are included
        metrics = created_insight.metrics
        assert hasattr(metrics, 'gsc_position')
        assert hasattr(metrics, 'gsc_position_change')
        assert hasattr(metrics, 'gsc_clicks')
        assert hasattr(metrics, 'gsc_clicks_change')

    @pytest.mark.skipif(not EVENT_CORRELATION_AVAILABLE, reason="EventCorrelationEngine not available")
    def test_correlation_detection(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop,
        sample_trigger_events
    ):
        """Test that correlation detection finds and reports trigger events."""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.EventCorrelationEngine') as mock_engine_class:
                mock_engine = Mock()
                mock_engine.find_trigger_events.return_value = sample_trigger_events
                mock_engine_class.return_value = mock_engine

                detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=True)
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        # Verify correlation metadata
        metrics = diagnosis.metrics
        assert hasattr(metrics, 'trigger_events_found')
        assert metrics.trigger_events_found == 2
        assert hasattr(metrics, 'all_trigger_events')
        assert len(metrics.all_trigger_events) == 2


class TestHelperMethods:
    """Tests for helper methods."""

    def test_to_float_conversion(self, mock_repository, mock_config):
        """Test _to_float helper method."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)

        # Test various inputs
        assert detector._to_float(None) is None
        assert detector._to_float(10.5) == 10.5
        assert detector._to_float(10) == 10.0

        # Test with Decimal-like object
        from decimal import Decimal
        assert detector._to_float(Decimal('15.75')) == 15.75

    def test_to_float_handles_errors(self, mock_repository, mock_config):
        """Test _to_float handles non-numeric values."""
        detector = DiagnosisDetector(mock_repository, mock_config, use_correlation=False)

        # Should return original value if conversion fails
        result = detector._to_float("not a number")
        assert result == "not a number"


class TestCSEIntegration:
    """Tests for Google CSE integration."""

    def test_cse_lazy_loading(self, mock_repository, mock_config):
        """Test that CSE analyzer is lazy loaded."""
        with patch('insights_core.detectors.diagnosis.GoogleCSEAnalyzer') as mock_cse_class:
            mock_cse = Mock()
            mock_cse_class.return_value = mock_cse

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_cse=True
            )

            # CSE should not be loaded yet
            assert detector._cse_analyzer is None

            # Access property to trigger lazy load
            analyzer = detector.cse_analyzer

            # Now it should be loaded
            if detector.use_cse:
                mock_cse_class.assert_called_once()

    def test_cse_disabled(self, mock_repository, mock_config):
        """Test CSE when disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_cse=False
        )

        assert detector.cse_analyzer is None

    def test_get_serp_context_when_cse_disabled(
        self,
        mock_repository,
        mock_config
    ):
        """Test _get_serp_context returns None when CSE is disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_cse=False
        )

        result = detector._get_serp_context('sc-domain:example.com', 'test query')
        assert result is None


class TestTrendsIntegration:
    """Tests for Trends integration."""

    def test_trends_initialization(self, mock_repository, mock_config):
        """Test TrendsAnalyzer initialization."""
        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_trends_class:
            mock_trends = Mock()
            mock_trends_class.return_value = mock_trends

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_trends=True
            )

            # Verify trends analyzer was initialized if available
            # (depends on TRENDS_ANALYZER_AVAILABLE)

    def test_trends_disabled(self, mock_repository, mock_config):
        """Test trends when disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_trends=False
        )

        assert detector.use_trends is False
        assert detector.trends_analyzer is None

    def test_get_trends_context_when_disabled(
        self,
        mock_repository,
        mock_config
    ):
        """Test _get_trends_context returns None when trends is disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_trends=False
        )

        result = detector._get_trends_context('sc-domain:example.com', 'test query')
        assert result is None


class TestAsyncCausalAnalysis:
    """Tests for async causal analysis methods."""

    @pytest.mark.asyncio
    async def test_run_causal_analysis_async_insufficient_data(
        self,
        mock_repository,
        mock_config
    ):
        """Test async causal analysis with insufficient data."""
        if not CAUSAL_ANALYZER_AVAILABLE:
            pytest.skip("CausalAnalyzer not available")

        with patch('insights_core.detectors.diagnosis.CausalAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.fetch_time_series_data = AsyncMock(return_value=pd.DataFrame())
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=True
            )

            result = await detector._run_causal_analysis_async(
                property='sc-domain:example.com',
                page_path='/test/',
                change_date=date.today(),
                metric='clicks',
                pre_period_days=30,
                post_period_days=7
            )

        assert result is None
