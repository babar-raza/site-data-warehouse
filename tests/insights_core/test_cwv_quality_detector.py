"""
Tests for CWVQualityDetector

Tests cover:
- Detector initialization with/without CoreWebVitalsMonitor
- Poor CWV detection (LCP, FID/INP, CLS)
- Good CWV creates no insights
- Metrics include required fields (metric, value, threshold, device)
- Engine integration
- Severity levels (all poor CWV should be HIGH)
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import date, datetime

from insights_core.detectors.cwv_quality import (
    CWVQualityDetector,
    LCP_POOR_THRESHOLD,
    FID_POOR_THRESHOLD,
    CLS_POOR_THRESHOLD,
    METRIC_DISPLAY_NAMES,
    CWV_MONITOR_AVAILABLE,
)
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
)

# Base module path for patching psycopg2
BASE_PSYCOPG2_PATH = 'insights_core.detectors.base.psycopg2'


@pytest.fixture
def mock_config():
    """Create mock InsightsConfig"""
    config = MagicMock()
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test_db"
    return config


@pytest.fixture
def mock_repository():
    """Create mock InsightRepository"""
    repo = MagicMock()
    repo.create = MagicMock(return_value=1)
    return repo


@pytest.fixture
def detector(mock_repository, mock_config):
    """Create CWVQualityDetector with mocked dependencies"""
    with patch.object(CWVQualityDetector, '_get_db_connection'):
        detector = CWVQualityDetector(
            repository=mock_repository,
            config=mock_config,
            use_cwv_monitor=False  # Disable CWV monitor for direct DB testing
        )
    return detector


# ===== Test Initialization =====

class TestCWVQualityDetectorInit:
    """Tests for CWVQualityDetector initialization"""

    def test_init_without_cwv_monitor(self, mock_repository, mock_config):
        """Test initialization without CoreWebVitalsMonitor"""
        with patch.object(CWVQualityDetector, '_get_db_connection'):
            detector = CWVQualityDetector(
                repository=mock_repository,
                config=mock_config,
                use_cwv_monitor=False
            )

        assert detector.repository == mock_repository
        assert detector.config == mock_config
        assert detector.use_cwv_monitor is False
        assert detector.cwv_monitor is None

    def test_init_with_cwv_monitor_available(self, mock_repository, mock_config):
        """Test initialization when CoreWebVitalsMonitor is available"""
        with patch.object(CWVQualityDetector, '_get_db_connection'):
            with patch('insights_core.detectors.cwv_quality.CWV_MONITOR_AVAILABLE', True):
                with patch('insights_core.detectors.cwv_quality.CoreWebVitalsMonitor') as mock_cwv:
                    mock_cwv.return_value = MagicMock()
                    detector = CWVQualityDetector(
                        repository=mock_repository,
                        config=mock_config,
                        use_cwv_monitor=True
                    )

        assert detector.use_cwv_monitor is True

    def test_init_cwv_monitor_fails_gracefully(self, mock_repository, mock_config):
        """Test that initialization handles CoreWebVitalsMonitor failures gracefully"""
        with patch.object(CWVQualityDetector, '_get_db_connection'):
            with patch('insights_core.detectors.cwv_quality.CWV_MONITOR_AVAILABLE', True):
                with patch('insights_core.detectors.cwv_quality.CoreWebVitalsMonitor') as mock_cwv:
                    mock_cwv.side_effect = Exception("Connection failed")
                    detector = CWVQualityDetector(
                        repository=mock_repository,
                        config=mock_config,
                        use_cwv_monitor=True
                    )

        assert detector.use_cwv_monitor is False
        assert detector.cwv_monitor is None


# ===== Test Detection =====

class TestCWVQualityDetectorDetect:
    """Tests for CWVQualityDetector.detect()"""

    def test_detect_returns_zero_when_no_data(self, detector):
        """Test detect returns 0 when no CWV data found"""
        with patch.object(detector, '_get_cwv_data', return_value=[]):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0

    def test_detect_requires_property_not_enforced(self, detector):
        """Test detect works without property (analyzes all)"""
        with patch.object(detector, '_get_cwv_data', return_value=[]):
            result = detector.detect(property=None)

        assert result == 0

    def test_detect_handles_exception_gracefully(self, detector):
        """Test detect returns 0 on exception"""
        with patch.object(detector, '_get_cwv_data', side_effect=Exception("DB error")):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0


# ===== Test Poor LCP Detection =====

class TestPoorLCPDetection:
    """Tests for poor LCP detection"""

    def test_poor_lcp_creates_risk_insight(self, detector, mock_repository):
        """Test that poor LCP creates a RISK insight"""
        poor_lcp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/slow-page',
            'strategy': 'mobile',
            'lcp': 5000,  # Poor: > 4000ms
            'fid': 50,    # Good
            'cls': 0.05,  # Good
        }]

        with patch.object(detector, '_get_cwv_data', return_value=poor_lcp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1
        mock_repository.create.assert_called_once()

        insight = mock_repository.create.call_args[0][0]
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert 'LCP' in insight.title
        assert '5000ms' in insight.title

    def test_good_lcp_creates_no_insight(self, detector, mock_repository):
        """Test that good LCP creates no insight"""
        good_lcp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/fast-page',
            'strategy': 'mobile',
            'lcp': 2000,  # Good: <= 2500ms
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=good_lcp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0
        mock_repository.create.assert_not_called()

    def test_lcp_at_threshold_creates_no_insight(self, detector, mock_repository):
        """Test that LCP exactly at poor threshold creates no insight"""
        threshold_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/borderline-page',
            'strategy': 'mobile',
            'lcp': LCP_POOR_THRESHOLD,  # Exactly at threshold
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=threshold_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0


# ===== Test Poor FID/INP Detection =====

class TestPoorFIDDetection:
    """Tests for poor FID/INP detection"""

    def test_poor_fid_creates_risk_insight(self, detector, mock_repository):
        """Test that poor FID creates a RISK insight"""
        poor_fid_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/slow-interaction',
            'strategy': 'mobile',
            'lcp': 2000,  # Good
            'fid': 400,   # Poor: > 300ms
            'inp': None,
            'cls': 0.05,  # Good
        }]

        with patch.object(detector, '_get_cwv_data', return_value=poor_fid_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1
        insight = mock_repository.create.call_args[0][0]
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert 'FID' in insight.title

    def test_poor_inp_creates_risk_insight(self, detector, mock_repository):
        """Test that poor INP creates a RISK insight (replacement for FID)"""
        poor_inp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/slow-interaction',
            'strategy': 'mobile',
            'lcp': 2000,
            'fid': None,
            'inp': 400,   # Poor: > 300ms
            'cls': 0.05,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=poor_inp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1
        insight = mock_repository.create.call_args[0][0]
        assert 'INP' in insight.title

    def test_good_fid_creates_no_insight(self, detector, mock_repository):
        """Test that good FID creates no insight"""
        good_fid_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/fast-interaction',
            'strategy': 'mobile',
            'lcp': None,
            'fid': 50,    # Good: <= 100ms
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=good_fid_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0


# ===== Test Poor CLS Detection =====

class TestPoorCLSDetection:
    """Tests for poor CLS detection"""

    def test_poor_cls_creates_risk_insight(self, detector, mock_repository):
        """Test that poor CLS creates a RISK insight"""
        poor_cls_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/unstable-page',
            'strategy': 'mobile',
            'lcp': 2000,
            'fid': 50,
            'cls': 0.5,   # Poor: > 0.25
        }]

        with patch.object(detector, '_get_cwv_data', return_value=poor_cls_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1
        insight = mock_repository.create.call_args[0][0]
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert 'CLS' in insight.title

    def test_good_cls_creates_no_insight(self, detector, mock_repository):
        """Test that good CLS creates no insight"""
        good_cls_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/stable-page',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': 0.05,  # Good: <= 0.1
        }]

        with patch.object(detector, '_get_cwv_data', return_value=good_cls_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0


# ===== Test Metrics Include Required Fields =====

class TestMetricsRequiredFields:
    """Tests that metrics include all required fields: metric, value, threshold, device"""

    def test_lcp_insight_has_required_metrics(self, detector, mock_repository):
        """Test LCP insight metrics include metric, value, threshold, device"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        metrics = insight.metrics

        # Check required fields
        assert hasattr(metrics, 'metric') or 'metric' in (metrics.dict() if hasattr(metrics, 'dict') else {})
        assert metrics.metric == 'lcp'
        assert metrics.value == 5000.0
        assert metrics.threshold == LCP_POOR_THRESHOLD
        assert metrics.device == 'mobile'

    def test_fid_insight_has_required_metrics(self, detector, mock_repository):
        """Test FID insight metrics include metric, value, threshold, device"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'desktop',
            'lcp': None,
            'fid': 400,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        metrics = insight.metrics

        assert metrics.metric == 'fid'
        assert metrics.value == 400.0
        assert metrics.threshold == FID_POOR_THRESHOLD
        assert metrics.device == 'desktop'

    def test_cls_insight_has_required_metrics(self, detector, mock_repository):
        """Test CLS insight metrics include metric, value, threshold, device"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': 0.5,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        metrics = insight.metrics

        assert metrics.metric == 'cls'
        assert metrics.value == 0.5
        assert metrics.threshold == CLS_POOR_THRESHOLD
        assert metrics.device == 'mobile'


# ===== Test Multiple Poor Metrics =====

class TestMultiplePoorMetrics:
    """Tests for pages with multiple poor metrics"""

    def test_page_with_all_poor_metrics_creates_three_insights(self, detector, mock_repository):
        """Test that a page with all poor CWV metrics creates 3 separate insights"""
        all_poor_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/terrible-page',
            'strategy': 'mobile',
            'lcp': 5000,   # Poor
            'fid': 400,    # Poor
            'cls': 0.5,    # Poor
        }]

        with patch.object(detector, '_get_cwv_data', return_value=all_poor_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 3
        assert mock_repository.create.call_count == 3

    def test_multiple_pages_with_issues(self, detector, mock_repository):
        """Test detection across multiple pages"""
        multi_page_data = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/page1',
                'strategy': 'mobile',
                'lcp': 5000,  # Poor
                'fid': None,
                'cls': None,
            },
            {
                'property': 'sc-domain:example.com',
                'page_path': '/page2',
                'strategy': 'mobile',
                'lcp': None,
                'fid': None,
                'cls': 0.5,   # Poor
            },
            {
                'property': 'sc-domain:example.com',
                'page_path': '/page3',
                'strategy': 'mobile',
                'lcp': 2000,  # Good
                'fid': 50,    # Good
                'cls': 0.05,  # Good
            },
        ]

        with patch.object(detector, '_get_cwv_data', return_value=multi_page_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 2  # Only page1 and page2 have issues


# ===== Test Device Strategy =====

class TestDeviceStrategy:
    """Tests for different device strategies"""

    def test_mobile_strategy_in_insight(self, detector, mock_repository):
        """Test that mobile strategy is correctly recorded"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.device == 'mobile'
        assert 'mobile' in insight.description

    def test_desktop_strategy_in_insight(self, detector, mock_repository):
        """Test that desktop strategy is correctly recorded"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'desktop',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.device == 'desktop'
        assert 'desktop' in insight.description


# ===== Test CWV Summary =====

class TestGetCWVSummary:
    """Tests for get_cwv_summary() method"""

    def test_summary_with_no_data(self, detector):
        """Test summary returns empty counts when no data"""
        with patch.object(detector, '_get_cwv_data', return_value=[]):
            summary = detector.get_cwv_summary("sc-domain:example.com")

        assert summary['available'] is True
        assert summary['pages_analyzed'] == 0
        assert summary['poor_lcp_count'] == 0
        assert summary['poor_fid_count'] == 0
        assert summary['poor_cls_count'] == 0

    def test_summary_with_mixed_data(self, detector):
        """Test summary correctly counts poor metrics"""
        data = [
            {'page_path': '/p1', 'strategy': 'mobile', 'lcp': 5000, 'fid': None, 'cls': None, 'inp': None},
            {'page_path': '/p2', 'strategy': 'mobile', 'lcp': 5500, 'fid': 400, 'cls': None, 'inp': None},
            {'page_path': '/p3', 'strategy': 'mobile', 'lcp': 2000, 'fid': 50, 'cls': 0.5, 'inp': None},
            {'page_path': '/p4', 'strategy': 'mobile', 'lcp': 2000, 'fid': 50, 'cls': 0.05, 'inp': None},
        ]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            summary = detector.get_cwv_summary("sc-domain:example.com")

        assert summary['pages_analyzed'] == 4
        assert summary['poor_lcp_count'] == 2  # p1, p2
        assert summary['poor_fid_count'] == 1  # p2
        assert summary['poor_cls_count'] == 1  # p3
        assert summary['total_issues'] == 4

    def test_summary_handles_errors_gracefully(self, detector):
        """Test summary returns error info on exception"""
        with patch.object(detector, '_get_cwv_data', side_effect=Exception("DB error")):
            summary = detector.get_cwv_summary("sc-domain:example.com")

        assert summary['available'] is True
        assert 'error' in summary


# ===== Test Engine Integration =====

class TestEngineIntegration:
    """Tests for engine integration"""

    def test_cwv_quality_detector_in_engine_detectors(self):
        """Test that CWVQualityDetector is in engine's detector list"""
        with patch('insights_core.engine.InsightRepository'):
            with patch('insights_core.engine.InsightsConfig') as mock_config:
                mock_config.return_value.warehouse_dsn = "postgresql://test:test@localhost/test"

                from insights_core.engine import InsightEngine
                engine = InsightEngine()

                detector_names = [d.__class__.__name__ for d in engine.detectors]
                assert 'CWVQualityDetector' in detector_names

    def test_cwv_quality_detector_export(self):
        """Test that CWVQualityDetector is exported from detectors module"""
        from insights_core.detectors import CWVQualityDetector as ImportedDetector
        from insights_core.detectors.cwv_quality import CWVQualityDetector as DirectDetector

        assert ImportedDetector is DirectDetector


# ===== Test Severity Levels =====

class TestSeverityLevels:
    """Tests for insight severity levels"""

    def test_all_poor_cwv_insights_are_high_severity(self, detector, mock_repository):
        """Test that all poor CWV insights have HIGH severity"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,  # Poor
            'fid': 400,   # Poor
            'cls': 0.5,   # Poor
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        # All 3 insights should be HIGH severity
        for call in mock_repository.create.call_args_list:
            insight = call[0][0]
            assert insight.severity == InsightSeverity.HIGH


# ===== Test Insight Details =====

class TestInsightDetails:
    """Tests for insight content details"""

    def test_insight_entity_type_is_page(self, detector, mock_repository):
        """Test that insights use EntityType.PAGE"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.entity_type == EntityType.PAGE

    def test_insight_entity_id_is_page_path(self, detector, mock_repository):
        """Test that entity_id is the page_path"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/blog/my-article',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.entity_id == '/blog/my-article'

    def test_insight_source_is_cwv_quality_detector(self, detector, mock_repository):
        """Test that source is CWVQualityDetector"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.source == "CWVQualityDetector"

    def test_insight_category_is_risk(self, detector, mock_repository):
        """Test that all CWV insights have RISK category"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.category == InsightCategory.RISK


# ===== Test Null Value Handling =====

class TestNullValueHandling:
    """Tests for handling null/None CWV values"""

    def test_null_lcp_does_not_create_insight(self, detector, mock_repository):
        """Test that null LCP doesn't create insight"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0

    def test_partial_null_values(self, detector, mock_repository):
        """Test handling of partial null values"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,   # Poor
            'fid': None,   # Null - no insight
            'cls': None,   # Null - no insight
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # Only LCP insight


# ===== Test Thresholds =====

class TestThresholds:
    """Tests for threshold constants"""

    def test_lcp_threshold_is_4000(self):
        """Test LCP poor threshold is 4000ms"""
        assert LCP_POOR_THRESHOLD == 4000

    def test_fid_threshold_is_300(self):
        """Test FID poor threshold is 300ms"""
        assert FID_POOR_THRESHOLD == 300

    def test_cls_threshold_is_025(self):
        """Test CLS poor threshold is 0.25"""
        assert CLS_POOR_THRESHOLD == 0.25

    def test_metric_display_names_exist(self):
        """Test that display names are defined for all metrics"""
        assert 'lcp' in METRIC_DISPLAY_NAMES
        assert 'fid' in METRIC_DISPLAY_NAMES
        assert 'inp' in METRIC_DISPLAY_NAMES
        assert 'cls' in METRIC_DISPLAY_NAMES


# ===== Test Comprehensive Scenarios =====

class TestComprehensiveScenarios:
    """Tests for comprehensive real-world scenarios"""

    def test_all_good_metrics_creates_no_insights(self, detector, mock_repository):
        """Test that page with all good CWV metrics creates no insights"""
        all_good_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/excellent-page',
            'strategy': 'mobile',
            'lcp': 2000,   # Good: < 2500ms
            'fid': 80,     # Good: < 100ms
            'inp': 150,    # Good: < 200ms
            'cls': 0.08,   # Good: < 0.1
        }]

        with patch.object(detector, '_get_cwv_data', return_value=all_good_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0
        mock_repository.create.assert_not_called()

    def test_all_poor_metrics_creates_three_insights(self, detector, mock_repository):
        """Test that page with all poor CWV metrics creates exactly 3 insights"""
        all_poor_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/terrible-page',
            'strategy': 'mobile',
            'lcp': 6000,   # Poor: > 4000ms
            'fid': 400,    # Poor: > 300ms
            'inp': None,   # FID is used when both exist
            'cls': 0.5,    # Poor: > 0.25
        }]

        with patch.object(detector, '_get_cwv_data', return_value=all_poor_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 3
        assert mock_repository.create.call_count == 3

        # Verify each metric created an insight
        insights = [call[0][0] for call in mock_repository.create.call_args_list]
        metrics_detected = [insight.metrics.metric for insight in insights]
        assert 'lcp' in metrics_detected
        assert 'fid' in metrics_detected
        assert 'cls' in metrics_detected

    def test_mixed_good_and_poor_metrics(self, detector, mock_repository):
        """Test page with mixed good and poor metrics"""
        mixed_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/mixed-page',
            'strategy': 'mobile',
            'lcp': 2000,   # Good
            'fid': 400,    # Poor
            'cls': 0.5,    # Poor
        }]

        with patch.object(detector, '_get_cwv_data', return_value=mixed_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 2  # Only FID and CLS are poor

        # Verify correct insights were created
        insights = [call[0][0] for call in mock_repository.create.call_args_list]
        metrics_detected = [insight.metrics.metric for insight in insights]
        assert 'lcp' not in metrics_detected  # LCP was good
        assert 'fid' in metrics_detected
        assert 'cls' in metrics_detected

    def test_missing_lcp_only_checks_other_metrics(self, detector, mock_repository):
        """Test that missing LCP doesn't create insight but checks other metrics"""
        missing_lcp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/no-lcp-page',
            'strategy': 'mobile',
            'lcp': None,   # Missing
            'fid': 400,    # Poor
            'cls': 0.05,   # Good
        }]

        with patch.object(detector, '_get_cwv_data', return_value=missing_lcp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # Only FID insight created

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.metric == 'fid'

    def test_missing_cls_only_checks_other_metrics(self, detector, mock_repository):
        """Test that missing CLS doesn't create insight but checks other metrics"""
        missing_cls_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/no-cls-page',
            'strategy': 'mobile',
            'lcp': 5000,   # Poor
            'fid': 50,     # Good
            'cls': None,   # Missing
        }]

        with patch.object(detector, '_get_cwv_data', return_value=missing_cls_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # Only LCP insight created

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.metric == 'lcp'

    def test_empty_data_array_returns_zero(self, detector, mock_repository):
        """Test that empty data array returns 0 insights"""
        with patch.object(detector, '_get_cwv_data', return_value=[]):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0
        mock_repository.create.assert_not_called()

    def test_mobile_vs_desktop_separate_insights(self, detector, mock_repository):
        """Test that same page with different devices creates separate insights"""
        mobile_and_desktop_data = [
            {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'strategy': 'mobile',
                'lcp': 5000,  # Poor on mobile
                'fid': None,
                'cls': None,
            },
            {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'strategy': 'desktop',
                'lcp': 5500,  # Poor on desktop
                'fid': None,
                'cls': None,
            },
        ]

        with patch.object(detector, '_get_cwv_data', return_value=mobile_and_desktop_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 2  # One for mobile, one for desktop

        # Verify both devices are represented
        insights = [call[0][0] for call in mock_repository.create.call_args_list]
        devices = [insight.metrics.device for insight in insights]
        assert 'mobile' in devices
        assert 'desktop' in devices

    def test_historical_regression_detected(self, detector, mock_repository):
        """Test detection of performance regression over time"""
        # Simulating a page that was good but now has poor LCP
        regression_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/regressed-page',
            'strategy': 'mobile',
            'lcp': 4500,   # Now poor (was good before)
            'fid': 50,     # Still good
            'cls': 0.05,   # Still good
        }]

        with patch.object(detector, '_get_cwv_data', return_value=regression_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # LCP regression detected

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.metric == 'lcp'
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH


# ===== Test INP-Specific Scenarios =====

class TestINPMetric:
    """Tests specific to INP (Interaction to Next Paint) metric"""

    def test_inp_used_when_fid_missing(self, detector, mock_repository):
        """Test that INP is used when FID is not available"""
        inp_only_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/inp-page',
            'strategy': 'mobile',
            'lcp': 2000,
            'fid': None,   # FID not available
            'inp': 400,    # Poor INP
            'cls': 0.05,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=inp_only_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1

        insight = mock_repository.create.call_args[0][0]
        assert insight.metrics.metric == 'inp'
        assert 'INP' in insight.title

    def test_fid_preferred_over_inp_when_both_present(self, detector, mock_repository):
        """Test that FID value is used but labeled as INP when both are available"""
        both_fid_inp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/both-metrics',
            'strategy': 'mobile',
            'lcp': 2000,
            'fid': 400,    # Poor FID (value used)
            'inp': 400,    # Poor INP (name used)
            'cls': 0.05,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=both_fid_inp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1

        insight = mock_repository.create.call_args[0][0]
        # When both exist, FID value is used but metric is labeled as INP
        assert insight.metrics.metric == 'inp'
        assert insight.metrics.value == 400

    def test_good_inp_creates_no_insight(self, detector, mock_repository):
        """Test that good INP creates no insight"""
        good_inp_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/good-inp',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'inp': 150,    # Good: < 200ms
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=good_inp_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0


# ===== Test Edge Cases =====

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_lcp_exactly_at_good_threshold(self, detector, mock_repository):
        """Test LCP exactly at good threshold (2500ms)"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 2500,   # Exactly at good threshold
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0  # Still considered good

    def test_cls_exactly_at_good_threshold(self, detector, mock_repository):
        """Test CLS exactly at good threshold (0.1)"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': 0.1,    # Exactly at good threshold
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0  # Still considered good

    def test_lcp_just_above_poor_threshold(self, detector, mock_repository):
        """Test LCP just above poor threshold (4001ms)"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 4001,   # Just above poor threshold
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # Should create insight

    def test_cls_just_above_poor_threshold(self, detector, mock_repository):
        """Test CLS just above poor threshold (0.26)"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': 0.26,   # Just above poor threshold
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 1  # Should create insight

    def test_zero_values_create_no_insights(self, detector, mock_repository):
        """Test that zero values for metrics create no insights"""
        zero_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 0,      # Zero (invalid but shouldn't crash)
            'fid': 0,
            'cls': 0,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=zero_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 0  # All are below thresholds

    def test_extremely_high_values(self, detector, mock_repository):
        """Test handling of extremely high CWV values"""
        extreme_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 50000,   # Extremely high
            'fid': 10000,   # Extremely high
            'cls': 5.0,     # Extremely high
        }]

        with patch.object(detector, '_get_cwv_data', return_value=extreme_data):
            result = detector.detect(property="sc-domain:example.com")

        assert result == 3  # All should create insights

        # Verify insights were created
        insights = [call[0][0] for call in mock_repository.create.call_args_list]
        assert len(insights) == 3

    def test_negative_values_handled_safely(self, detector, mock_repository):
        """Test that negative values (invalid data) are handled safely"""
        negative_data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': -100,    # Invalid negative value
            'fid': -50,     # Invalid negative value
            'cls': -0.1,    # Invalid negative value
        }]

        with patch.object(detector, '_get_cwv_data', return_value=negative_data):
            # Should not crash
            result = detector.detect(property="sc-domain:example.com")

        # Negative values are less than thresholds, so no insights
        assert result == 0

    def test_multiple_properties_in_single_detection(self, detector, mock_repository):
        """Test detection across multiple properties when no filter"""
        multi_property_data = [
            {
                'property': 'sc-domain:site1.com',
                'page_path': '/page1',
                'strategy': 'mobile',
                'lcp': 5000,  # Poor
                'fid': None,
                'cls': None,
            },
            {
                'property': 'sc-domain:site2.com',
                'page_path': '/page2',
                'strategy': 'mobile',
                'lcp': 5000,  # Poor
                'fid': None,
                'cls': None,
            },
        ]

        with patch.object(detector, '_get_cwv_data', return_value=multi_property_data):
            result = detector.detect()  # No property filter

        assert result == 2  # One insight per property


# ===== Test Insight Content Quality =====

class TestInsightContentQuality:
    """Tests for quality and completeness of insight content"""

    def test_lcp_insight_contains_actionable_recommendations(self, detector, mock_repository):
        """Test LCP insight includes actionable recommendations"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        description = insight.description.lower()

        # Should contain actionable recommendations
        assert any(word in description for word in ['optimize', 'consider', 'improve', 'reduce'])
        # Should mention what LCP measures
        assert 'largest content' in description or 'lcp' in description

    def test_cls_insight_contains_visual_stability_context(self, detector, mock_repository):
        """Test CLS insight explains visual stability"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': None,
            'fid': None,
            'cls': 0.5,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        description = insight.description.lower()

        # Should explain visual stability
        assert any(word in description for word in ['visual', 'stability', 'shift', 'layout'])

    def test_insight_metrics_excess_percent_calculated(self, detector, mock_repository):
        """Test that excess_percent is calculated in metrics"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 8000,  # 100% above threshold of 4000
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]

        assert hasattr(insight.metrics, 'excess_percent')
        # 8000 is 100% above 4000 threshold
        assert insight.metrics.excess_percent == 100.0

    def test_insight_confidence_is_high(self, detector, mock_repository):
        """Test that CWV insights have high confidence (0.95)"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.confidence == 0.95  # High confidence for objective measurement

    def test_insight_window_days_is_seven(self, detector, mock_repository):
        """Test that insights use 7-day window"""
        data = [{
            'property': 'sc-domain:example.com',
            'page_path': '/test',
            'strategy': 'mobile',
            'lcp': 5000,
            'fid': None,
            'cls': None,
        }]

        with patch.object(detector, '_get_cwv_data', return_value=data):
            detector.detect(property="sc-domain:example.com")

        insight = mock_repository.create.call_args[0][0]
        assert insight.window_days == 7


# ===== Test Database Query =====

class TestDatabaseQuery:
    """Tests for _get_cwv_data database queries"""

    def test_get_cwv_data_queries_last_7_days(self, detector):
        """Test that _get_cwv_data queries last 7 days by default"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            detector._get_cwv_data()

            # Verify query contains 7 days interval
            call_args = mock_cursor.execute.call_args
            query = call_args[0][0]
            assert "7 days" in query or "INTERVAL '7 days'" in query

    def test_get_cwv_data_with_property_filter(self, detector):
        """Test that property filter is applied to query"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            detector._get_cwv_data(property='sc-domain:example.com')

            # Verify property was passed to query
            call_args = mock_cursor.execute.call_args
            params = call_args[0][1]
            assert 'sc-domain:example.com' in params

    def test_get_cwv_data_handles_db_errors_gracefully(self, detector):
        """Test that database errors are handled gracefully"""
        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("DB connection failed")

            # Should return empty list, not crash
            result = detector._get_cwv_data()

            assert result == []
