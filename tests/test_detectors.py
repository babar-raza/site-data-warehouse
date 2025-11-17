"""
Tests for Insight Detectors
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date
from insights_core.engine import InsightEngine
from insights_core.detectors import (
    BaseDetector,
    AnomalyDetector,
    DiagnosisDetector,
    OpportunityDetector,
)
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)


@pytest.fixture
def mock_config():
    """Create mock config"""
    return InsightsConfig(
        warehouse_dsn="postgresql://test:test@localhost:5432/test_db",
        risk_threshold_clicks_pct=-20.0,
        risk_threshold_conversions_pct=-20.0,
        opportunity_threshold_impressions_pct=50.0
    )


@pytest.fixture
def mock_repository():
    """Create mock repository"""
    return MagicMock(spec=InsightRepository)


class TestInsightEngine:
    """Test InsightEngine orchestration"""
    
    @patch('insights_core.engine.InsightRepository')
    def test_engine_initialization(self, mock_repo_class):
        """Test engine initializes with config"""
        mock_repo_class.return_value = MagicMock()
        
        engine = InsightEngine()
        
        assert engine.config is not None
        assert len(engine.detectors) == 3
        assert isinstance(engine.detectors[0], AnomalyDetector)
        assert isinstance(engine.detectors[1], DiagnosisDetector)
        assert isinstance(engine.detectors[2], OpportunityDetector)
    
    @patch('insights_core.engine.InsightRepository')
    def test_engine_refresh(self, mock_repo_class):
        """Test engine refresh runs all detectors"""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        engine = InsightEngine()
        
        # Mock detector detect methods
        for detector in engine.detectors:
            detector.detect = MagicMock(return_value=5)
        
        stats = engine.refresh()
        
        assert stats['detectors_run'] == 3
        assert stats['detectors_succeeded'] == 3
        assert stats['detectors_failed'] == 0
        assert stats['total_insights_created'] == 15
    
    @patch('insights_core.engine.InsightRepository')
    def test_engine_refresh_with_failures(self, mock_repo_class):
        """Test engine continues on detector failure"""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        engine = InsightEngine()
        
        # First detector fails, others succeed
        engine.detectors[0].detect = MagicMock(side_effect=Exception("Test error"))
        engine.detectors[1].detect = MagicMock(return_value=3)
        engine.detectors[2].detect = MagicMock(return_value=2)
        
        stats = engine.refresh()
        
        assert stats['detectors_run'] == 3
        assert stats['detectors_succeeded'] == 2
        assert stats['detectors_failed'] == 1
        assert stats['total_insights_created'] == 5
        assert len(stats['errors']) == 1
    
    @patch('insights_core.engine.InsightRepository')
    def test_get_detector_stats(self, mock_repo_class):
        """Test getting detector statistics"""
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        
        engine = InsightEngine()
        stats = engine.get_detector_stats()
        
        assert stats['total_detectors'] == 3
        assert len(stats['detectors']) == 3
        assert stats['detectors'][0]['name'] == 'AnomalyDetector'


class TestAnomalyDetector:
    """Test AnomalyDetector"""
    
    def test_analyze_row_high_severity_risk(self, mock_repository, mock_config):
        """Test detection of high severity risk (clicks and conversions down)"""
        detector = AnomalyDetector(mock_repository, mock_config)
        
        row = {
            'property': 'https://example.com/',
            'page_path': '/test-page',
            'date': date(2025, 1, 15),
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -30.0,
            'gsc_impressions': 1000,
            'gsc_impressions_change_wow': -10.0,
            'gsc_ctr': 0.05,
            'ga_conversions': 5,
            'ga_conversions_change_wow': -25.0,
        }
        
        insights = detector._analyze_row(row)
        
        # Should detect high severity risk
        assert len(insights) >= 1
        risk_insight = next((i for i in insights if i.category == InsightCategory.RISK), None)
        assert risk_insight is not None
        assert risk_insight.severity == InsightSeverity.HIGH
        assert "Traffic & Conversion Drop" in risk_insight.title
    
    def test_analyze_row_medium_severity_risk(self, mock_repository, mock_config):
        """Test detection of medium severity risk (only clicks down)"""
        detector = AnomalyDetector(mock_repository, mock_config)
        
        row = {
            'property': 'https://example.com/',
            'page_path': '/test-page',
            'date': date(2025, 1, 15),
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -25.0,
            'gsc_impressions': 1000,
            'gsc_impressions_change_wow': -5.0,
            'gsc_ctr': 0.05,
            'ga_conversions': 5,
            'ga_conversions_change_wow': 10.0,  # Conversions up
        }
        
        insights = detector._analyze_row(row)
        
        # Should detect medium severity risk
        assert len(insights) >= 1
        risk_insight = next((i for i in insights if i.category == InsightCategory.RISK), None)
        assert risk_insight is not None
        assert risk_insight.severity == InsightSeverity.MEDIUM
        assert "Traffic Drop" in risk_insight.title
    
    def test_analyze_row_opportunity(self, mock_repository, mock_config):
        """Test detection of impression spike opportunity"""
        detector = AnomalyDetector(mock_repository, mock_config)
        
        row = {
            'property': 'https://example.com/',
            'page_path': '/test-page',
            'date': date(2025, 1, 15),
            'gsc_clicks': 100,
            'gsc_clicks_change_wow': 10.0,
            'gsc_impressions': 5000,
            'gsc_impressions_change_wow': 75.0,  # Big spike
            'gsc_ctr': 0.02,
            'ga_conversions': 10,
            'ga_conversions_change_wow': 5.0,
        }
        
        insights = detector._analyze_row(row)
        
        # Should detect opportunity
        assert len(insights) >= 1
        opp_insight = next((i for i in insights if i.category == InsightCategory.OPPORTUNITY), None)
        assert opp_insight is not None
        assert "Impression Spike" in opp_insight.title
    
    @patch('insights_core.detectors.base.psycopg2.connect')
    def test_detect_with_mock_db(self, mock_connect, mock_repository, mock_config):
        """Test detect method with mocked database"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock database return
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com/',
                'page_path': '/test',
                'date': date(2025, 1, 15),
                'gsc_clicks': 50,
                'gsc_clicks_change_wow': -30.0,
                'gsc_impressions': 1000,
                'gsc_impressions_change_wow': 0,
                'gsc_ctr': 0.05,
                'ga_conversions': 5,
                'ga_conversions_change_wow': -25.0,
            }
        ]
        
        mock_repository.create.return_value = None
        
        detector = AnomalyDetector(mock_repository, mock_config)
        insights_created = detector.detect()
        
        assert insights_created >= 1
        mock_repository.create.assert_called()


class TestDiagnosisDetector:
    """Test DiagnosisDetector"""
    
    @patch('insights_core.detectors.base.psycopg2.connect')
    def test_diagnose_ranking_issue(self, mock_connect, mock_repository, mock_config):
        """Test diagnosis of ranking issue"""
        # Setup mock DB connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock database return with position drop
        mock_cursor.fetchone.return_value = {
            'property': 'https://example.com/',
            'page_path': '/test',
            'date': date(2025, 1, 15),
            'gsc_avg_position': 25.0,
            'gsc_position_change_wow': 15.0,  # Position worsened
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -20.0,
            'ga_engagement_rate': 0.5,
            'ga_engagement_rate_7d_ago': 0.5,
            'modified_within_48h': False,
        }
        
        # Create mock risk insight
        from insights_core.models import Insight
        mock_risk = Insight(
            id='a' * 64,
            property='https://example.com/',
            entity_type=EntityType.PAGE,
            entity_id='/test',
            category=InsightCategory.RISK,
            title='Traffic Drop',
            description='Test',
            severity=InsightSeverity.HIGH,
            confidence=0.8,
            metrics=InsightMetrics(),
            window_days=7,
            source='test'
        )
        
        detector = DiagnosisDetector(mock_repository, mock_config)
        diagnosis = detector._diagnose_risk(mock_risk)
        
        assert diagnosis is not None
        assert diagnosis.category == InsightCategory.DIAGNOSIS
        assert "Ranking Issue" in diagnosis.title
    
    @patch('insights_core.detectors.base.psycopg2.connect')
    def test_detect_with_no_risks(self, mock_connect, mock_repository, mock_config):
        """Test detect when no risks to diagnose"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # No risks to diagnose
        mock_repository.get_by_status.return_value = []
        
        detector = DiagnosisDetector(mock_repository, mock_config)
        insights_created = detector.detect()
        
        assert insights_created == 0


class TestOpportunityDetector:
    """Test OpportunityDetector"""
    
    @patch('insights_core.detectors.base.psycopg2.connect')
    def test_find_striking_distance(self, mock_connect, mock_repository, mock_config):
        """Test finding striking distance opportunities"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock striking distance pages
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com/',
                'page_path': '/test',
                'date': date(2025, 1, 15),
                'gsc_avg_position': 15.0,
                'gsc_impressions': 1000,
                'gsc_clicks': 50,
                'gsc_ctr': 0.05,
                'ga_conversions': 5,
                'ga_engagement_rate': 0.6,
            }
        ]
        
        mock_repository.create.return_value = None
        
        detector = OpportunityDetector(mock_repository, mock_config)
        insights_created = detector._find_striking_distance()
        
        assert insights_created >= 1
        mock_repository.create.assert_called()
        
        # Verify the insight created
        call_args = mock_repository.create.call_args[0][0]
        assert call_args.category == InsightCategory.OPPORTUNITY
        assert "Striking Distance" in call_args.title
    
    @patch('insights_core.detectors.base.psycopg2.connect')
    def test_find_content_gaps(self, mock_connect, mock_repository, mock_config):
        """Test finding content gap opportunities"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Mock pages with high impressions but low engagement
        mock_cursor.fetchall.return_value = [
            {
                'property': 'https://example.com/',
                'page_path': '/test',
                'date': date(2025, 1, 15),
                'gsc_impressions': 1000,
                'gsc_clicks': 100,
                'gsc_ctr': 0.1,
                'ga_engagement_rate': 0.3,  # Low engagement
                'ga_sessions': 50,
                'ga_bounce_rate': 0.7,
            }
        ]
        
        mock_repository.create.return_value = None
        
        detector = OpportunityDetector(mock_repository, mock_config)
        insights_created = detector._find_content_gaps()
        
        assert insights_created >= 1
        mock_repository.create.assert_called()
        
        # Verify the insight created
        call_args = mock_repository.create.call_args[0][0]
        assert call_args.category == InsightCategory.OPPORTUNITY
        assert "Content Gap" in call_args.title


class TestBaseDetector:
    """Test BaseDetector base class"""
    
    def test_base_detector_abstract(self, mock_repository, mock_config):
        """Test that BaseDetector cannot be instantiated"""
        with pytest.raises(TypeError):
            BaseDetector(mock_repository, mock_config)
    
    def test_detector_initialization(self, mock_repository, mock_config):
        """Test detector initialization through concrete class"""
        detector = AnomalyDetector(mock_repository, mock_config)
        
        assert detector.repository == mock_repository
        assert detector.config == mock_config
        assert detector.conn_string == mock_config.warehouse_dsn
