"""
Comprehensive tests for TrendsAnalyzer and its integration with DiagnosisDetector

Tests the trends analysis functionality and its integration into diagnosis insights.
Uses mocks to achieve high coverage without requiring external services.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime, timedelta
from typing import Dict, List

# Try importing TrendsAnalyzer
try:
    from insights_core.trends_analyzer import TrendsAnalyzer
    TRENDS_ANALYZER_AVAILABLE = True
except ImportError:
    TRENDS_ANALYZER_AVAILABLE = False

# Module paths for patching
TRENDS_PSYCOPG2_PATH = 'insights_core.trends_analyzer.psycopg2'


def create_mock_trend_data(days: int = 30, trend: str = 'stable') -> List[Dict]:
    """
    Create mock trend data for testing

    Args:
        days: Number of days of data
        trend: Trend pattern ('stable', 'up', 'down', 'seasonal')

    Returns:
        List of trend data dictionaries (newest first, matching DB ORDER BY date DESC)
    """
    data = []
    base_score = 50

    # Generate data in reverse order (newest first, like the DB query)
    for i in range(days):
        # i=0 is today, i=days-1 is oldest
        days_ago = i
        score = base_score

        if trend == 'up':
            # Increasing trend over time (older = lower, newer = higher)
            # So newest (i=0) should have highest score
            score = base_score + ((days - i) * 1.5)
        elif trend == 'down':
            # Decreasing trend over time (older = higher, newer = lower)
            # So newest (i=0) should have lowest score
            score = base_score - ((days - i) * 1.5)
        elif trend == 'seasonal':
            # Seasonal pattern (monthly cycle)
            import math
            score = base_score + 20 * math.sin((days - i) / 30 * 2 * math.pi)

        data.append({
            'date': date.today() - timedelta(days=days_ago),
            'interest_score': int(max(0, min(100, score)))
        })

    return data


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestTrendsAnalyzerInit:
    """Tests for TrendsAnalyzer initialization."""

    def test_init_with_default_dsn(self):
        """Test initialization with default DSN from environment."""
        with patch('insights_core.trends_analyzer.os.getenv') as mock_getenv:
            mock_getenv.return_value = "postgresql://test:test@localhost:5432/test_db"

            analyzer = TrendsAnalyzer()

            assert analyzer.db_dsn == "postgresql://test:test@localhost:5432/test_db"
            mock_getenv.assert_called_once_with('WAREHOUSE_DSN')

    def test_init_with_explicit_dsn(self):
        """Test initialization with explicit DSN."""
        dsn = "postgresql://custom:custom@localhost:5432/custom_db"
        analyzer = TrendsAnalyzer(db_dsn=dsn)

        assert analyzer.db_dsn == dsn


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestAnalyzeKeywordTrends:
    """Tests for analyze_keyword_trends() method."""

    def test_analyze_no_data_available(self):
        """Test analysis when no trend data exists."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is False
        assert result['message'] == 'No trend data available'
        assert result['keyword'] == 'python'

    def test_analyze_insufficient_data(self):
        """Test analysis with insufficient data points."""
        mock_data = create_mock_trend_data(days=5)
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is True
        assert result['insufficient_data'] is True
        assert result['data_points'] == 5

    def test_analyze_stable_trend(self):
        """Test analysis of stable trend."""
        mock_data = create_mock_trend_data(days=30, trend='stable')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is True
        assert result['trend_direction'] == 'stable'
        assert result['is_trending_up'] is False
        assert result['is_trending_down'] is False

    def test_analyze_upward_trend(self):
        """Test analysis of upward trend."""
        mock_data = create_mock_trend_data(days=30, trend='up')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is True
        assert result['trend_direction'] == 'up'
        assert result['is_trending_up'] is True
        assert result['is_trending_down'] is False
        assert result['change_ratio'] >= analyzer.TREND_UP_THRESHOLD

    def test_analyze_downward_trend(self):
        """Test analysis of downward trend."""
        mock_data = create_mock_trend_data(days=30, trend='down')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is True
        assert result['trend_direction'] == 'down'
        assert result['is_trending_up'] is False
        assert result['is_trending_down'] is True
        assert result['change_ratio'] <= analyzer.TREND_DOWN_THRESHOLD

    def test_analyze_includes_all_metrics(self):
        """Test that analysis includes all expected metrics."""
        mock_data = create_mock_trend_data(days=30, trend='stable')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        # Check all expected keys are present
        expected_keys = [
            'keyword', 'property', 'has_data', 'data_points',
            'recent_avg', 'historical_avg', 'change_ratio',
            'trend_direction', 'is_trending_up', 'is_trending_down',
            'is_significant_change', 'seasonality', 'current_score',
            'max_score', 'min_score', 'volatility'
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_analyze_handles_database_error(self):
        """Test graceful handling of database errors."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Database connection failed")

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')

        assert result['has_data'] is False


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestIsTrendingUp:
    """Tests for is_trending_up() method."""

    def test_is_trending_up_true(self):
        """Test detecting upward trend."""
        mock_data = create_mock_trend_data(days=30, trend='up')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.is_trending_up('sc-domain:example.com', 'python')

        assert result is True

    def test_is_trending_up_false(self):
        """Test detecting non-upward trend."""
        mock_data = create_mock_trend_data(days=30, trend='stable')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.is_trending_up('sc-domain:example.com', 'python')

        assert result is False


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestGetTrendingKeywords:
    """Tests for get_trending_keywords() method."""

    def test_get_trending_keywords_returns_list(self):
        """Test getting list of trending keywords."""
        mock_results = [
            {'keyword': 'python', 'recent_avg': 80.0, 'historical_avg': 60.0, 'change_ratio': 1.33},
            {'keyword': 'django', 'recent_avg': 70.0, 'historical_avg': 50.0, 'change_ratio': 1.40},
        ]

        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.close.return_value = None
            mock_cursor.fetchall.return_value = mock_results
            mock_cursor.close.return_value = None

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.get_trending_keywords('sc-domain:example.com', limit=10)

        assert len(result) == 2
        assert result[0]['keyword'] == 'python'
        assert result[1]['keyword'] == 'django'

    def test_get_trending_keywords_handles_error(self):
        """Test error handling when getting trending keywords."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Database error")

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.get_trending_keywords('sc-domain:example.com')

        assert result == []


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestCorrelateWithTraffic:
    """Tests for correlate_with_traffic() method."""

    def test_correlate_with_sufficient_data(self):
        """Test correlation with sufficient overlapping data."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.close.return_value = None
            mock_cursor.close.return_value = None

            # Mock trends and GSC data
            mock_dates = [date.today() - timedelta(days=i) for i in range(10)]
            trend_results = [{'date': d, 'interest_score': 50 + i * 5} for i, d in enumerate(mock_dates)]
            gsc_results = [{'date': d, 'clicks': 100 + i * 10, 'impressions': 1000} for i, d in enumerate(mock_dates)]

            mock_cursor.fetchall.side_effect = [trend_results, gsc_results]

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.correlate_with_traffic('sc-domain:example.com', 'python', days=30)

        assert result['has_correlation'] is True
        assert 'correlation' in result
        assert 'correlation_strength' in result
        assert result['common_data_points'] == 10

    def test_correlate_insufficient_data(self):
        """Test correlation with insufficient data."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.close.return_value = None
            mock_cursor.close.return_value = None

            # Only 3 overlapping dates
            mock_dates = [date.today() - timedelta(days=i) for i in range(3)]
            trend_results = [{'date': d, 'interest_score': 50} for d in mock_dates]
            gsc_results = [{'date': d, 'clicks': 100, 'impressions': 1000} for d in mock_dates]

            mock_cursor.fetchall.side_effect = [trend_results, gsc_results]

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.correlate_with_traffic('sc-domain:example.com', 'python', days=30)

        assert result['has_correlation'] is False
        assert result['reason'] == 'insufficient_overlap'

    def test_correlate_handles_error(self):
        """Test error handling in correlation."""
        with patch(TRENDS_PSYCOPG2_PATH) as mock_psycopg2:
            mock_psycopg2.connect.side_effect = Exception("Database error")

            analyzer = TrendsAnalyzer(db_dsn="test_dsn")
            result = analyzer.correlate_with_traffic('sc-domain:example.com', 'python')

        assert result['has_correlation'] is False
        assert 'error' in result


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestDetectSeasonalPatterns:
    """Tests for detect_seasonal_patterns() method."""

    def test_detect_seasonality_insufficient_data(self):
        """Test seasonality detection with insufficient data."""
        mock_data = create_mock_trend_data(days=60)
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.detect_seasonal_patterns('sc-domain:example.com', 'python')

        assert result['has_seasonality'] is False
        assert result['reason'] == 'insufficient_data'

    def test_detect_seasonality_with_seasonal_pattern(self):
        """Test detecting seasonal patterns."""
        mock_data = create_mock_trend_data(days=365, trend='seasonal')
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        with patch.object(analyzer, '_get_trend_data', return_value=mock_data):
            result = analyzer.detect_seasonal_patterns('sc-domain:example.com', 'python')

        # Seasonal pattern should be detected
        assert 'has_seasonality' in result
        if result['has_seasonality']:
            assert 'peak_month' in result
            assert 'trough_month' in result
            assert 'seasonality_ratio' in result


@pytest.mark.skipif(not TRENDS_ANALYZER_AVAILABLE, reason="TrendsAnalyzer not available")
class TestCorrelationCalculation:
    """Tests for correlation calculation methods."""

    def test_calculate_correlation_perfect_positive(self):
        """Test perfect positive correlation."""
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]

        correlation = analyzer._calculate_correlation(x, y)

        assert correlation > 0.99  # Nearly perfect positive

    def test_calculate_correlation_perfect_negative(self):
        """Test perfect negative correlation."""
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")
        x = [1, 2, 3, 4, 5]
        y = [10, 8, 6, 4, 2]

        correlation = analyzer._calculate_correlation(x, y)

        assert correlation < -0.99  # Nearly perfect negative

    def test_calculate_correlation_no_correlation(self):
        """Test no correlation."""
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")
        x = [1, 2, 3, 4, 5]
        y = [5, 5, 5, 5, 5]  # Constant values

        correlation = analyzer._calculate_correlation(x, y)

        assert correlation == 0.0

    def test_interpret_correlation_strength(self):
        """Test correlation strength interpretation."""
        analyzer = TrendsAnalyzer(db_dsn="test_dsn")

        assert analyzer._interpret_correlation(0.8) == 'strong'
        assert analyzer._interpret_correlation(0.5) == 'moderate'
        assert analyzer._interpret_correlation(0.3) == 'weak'
        assert analyzer._interpret_correlation(0.1) == 'negligible'
        assert analyzer._interpret_correlation(-0.8) == 'strong'


# Tests for DiagnosisDetector integration
try:
    from insights_core.detectors.diagnosis import DiagnosisDetector, TRENDS_ANALYZER_AVAILABLE as DIAG_TRENDS_AVAILABLE
    from insights_core.models import (
        InsightCreate,
        InsightCategory,
        InsightSeverity,
        InsightStatus,
        EntityType,
    )
    DIAGNOSIS_AVAILABLE = True
except ImportError:
    DIAGNOSIS_AVAILABLE = False

BASE_PSYCOPG2_PATH = 'insights_core.detectors.base.psycopg2'


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
        'gsc_position_change_wow': 15.0,
        'gsc_clicks': 50,
        'gsc_clicks_change_wow': -30,
        'ga_engagement_rate': 65.0,
        'ga_engagement_rate_7d_ago': 70.0,
        'ga_conversions': 5,
        'ga_conversions_change_wow': -2,
        'modified_within_48h': False,
        'last_modified_date': None,
        'top_query': 'seo tips',
    }


@pytest.mark.skipif(not DIAGNOSIS_AVAILABLE or not DIAG_TRENDS_AVAILABLE, reason="DiagnosisDetector or TrendsAnalyzer not available")
class TestDiagnosisDetectorTrendsIntegration:
    """Tests for TrendsAnalyzer integration with DiagnosisDetector."""

    def test_init_with_trends_enabled(self, mock_repository, mock_config):
        """Test initialization with TrendsAnalyzer enabled."""
        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False,
                use_cse=False,
                use_trends=True
            )

            assert detector.use_trends is True
            mock_analyzer_class.assert_called_once()

    def test_init_with_trends_disabled(self, mock_repository, mock_config):
        """Test initialization with TrendsAnalyzer disabled."""
        detector = DiagnosisDetector(
            mock_repository,
            mock_config,
            use_correlation=False,
            use_causal_analysis=False,
            use_cse=False,
            use_trends=False
        )

        assert detector.use_trends is False
        assert detector.trends_analyzer is None

    def test_init_handles_trends_analyzer_error(self, mock_repository, mock_config):
        """Test graceful handling when TrendsAnalyzer fails to initialize."""
        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
            mock_analyzer_class.side_effect = Exception("Connection failed")

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False,
                use_cse=False,
                use_trends=True
            )

            assert detector.use_trends is False
            assert detector.trends_analyzer is None

    def test_get_trends_context_returns_analysis(self, mock_repository, mock_config):
        """Test getting trends context for a keyword."""
        mock_analysis = {
            'has_data': True,
            'trend_direction': 'up',
            'change_ratio': 1.25,
            'recent_avg': 60.0,
            'historical_avg': 48.0,
        }

        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze_keyword_trends.return_value = mock_analysis
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False,
                use_cse=False,
                use_trends=True
            )

            result = detector._get_trends_context('sc-domain:example.com', 'python')

        assert result == mock_analysis
        mock_analyzer.analyze_keyword_trends.assert_called_once_with(
            property='sc-domain:example.com',
            keyword='python',
            days=90
        )

    def test_get_trends_context_handles_no_data(self, mock_repository, mock_config):
        """Test trends context when no data available."""
        mock_analysis = {'has_data': False}

        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze_keyword_trends.return_value = mock_analysis
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False,
                use_cse=False,
                use_trends=True
            )

            result = detector._get_trends_context('sc-domain:example.com', 'python')

        assert result is None

    def test_get_trends_context_handles_error(self, mock_repository, mock_config):
        """Test trends context error handling."""
        with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
            mock_analyzer = Mock()
            mock_analyzer.analyze_keyword_trends.side_effect = Exception("Analysis error")
            mock_analyzer_class.return_value = mock_analyzer

            detector = DiagnosisDetector(
                mock_repository,
                mock_config,
                use_correlation=False,
                use_causal_analysis=False,
                use_cse=False,
                use_trends=True
            )

            result = detector._get_trends_context('sc-domain:example.com', 'python')

        assert result is None

    def test_ranking_diagnosis_includes_declining_trends(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis includes declining trends context."""
        mock_trends = {
            'has_data': True,
            'trend_direction': 'down',
            'change_ratio': 0.75,
            'recent_avg': 45.0,
            'historical_avg': 60.0,
            'volatility': 5.2,
            'current_score': 43,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.analyze_keyword_trends.return_value = mock_trends
                mock_analyzer_class.return_value = mock_analyzer

                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=False,
                    use_cse=False,
                    use_trends=True
                )
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "declining trends" in diagnosis.description
        assert "reduced demand" in diagnosis.description

        # Check trends metrics
        metrics = diagnosis.metrics
        assert hasattr(metrics, 'trends_direction')
        assert metrics.trends_direction == 'down'
        assert hasattr(metrics, 'trends_change_ratio')
        assert metrics.trends_change_ratio == 0.75

    def test_ranking_diagnosis_includes_rising_trends(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis includes rising trends context."""
        mock_trends = {
            'has_data': True,
            'trend_direction': 'up',
            'change_ratio': 1.30,
            'recent_avg': 78.0,
            'historical_avg': 60.0,
            'volatility': 8.1,
            'current_score': 82,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.analyze_keyword_trends.return_value = mock_trends
                mock_analyzer_class.return_value = mock_analyzer

                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=False,
                    use_cse=False,
                    use_trends=True
                )
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "trending upward" in diagnosis.description
        assert "content or technical issue" in diagnosis.description

    def test_ranking_diagnosis_includes_stable_trends(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis includes stable trends context."""
        mock_trends = {
            'has_data': True,
            'trend_direction': 'stable',
            'change_ratio': 1.05,
            'recent_avg': 63.0,
            'historical_avg': 60.0,
            'volatility': 3.2,
            'current_score': 61,
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = sample_db_row_ranking_drop

            with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.analyze_keyword_trends.return_value = mock_trends
                mock_analyzer_class.return_value = mock_analyzer

                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=False,
                    use_cse=False,
                    use_trends=True
                )
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "remains stable" in diagnosis.description
        assert "not demand-related" in diagnosis.description

    def test_ranking_diagnosis_works_without_trends(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight,
        sample_db_row_ranking_drop
    ):
        """Test that ranking diagnosis works when trends is disabled."""
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
                use_causal_analysis=False,
                use_cse=False,
                use_trends=False
            )
            diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        assert "Ranking Issue Detected" in diagnosis.title
        # Should not have trends context when disabled
        assert "Search interest" not in diagnosis.description

    def test_ranking_diagnosis_works_without_top_query(
        self,
        mock_repository,
        mock_config,
        sample_risk_insight
    ):
        """Test diagnosis works when top_query is not available."""
        db_row_no_query = {
            'property': 'sc-domain:example.com',
            'page_path': '/blog/seo-tips/',
            'date': date.today(),
            'gsc_avg_position': 25.0,
            'gsc_position_change_wow': 15.0,
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -30,
            'top_query': None,  # No top query
        }

        with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_psycopg2.connect.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cursor.fetchone.return_value = db_row_no_query

            with patch('insights_core.detectors.diagnosis.TrendsAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer_class.return_value = mock_analyzer

                detector = DiagnosisDetector(
                    mock_repository,
                    mock_config,
                    use_correlation=False,
                    use_causal_analysis=False,
                    use_cse=False,
                    use_trends=True
                )
                diagnosis = detector._diagnose_risk(sample_risk_insight)

        assert diagnosis is not None
        # Trends analyzer should not be called when no top_query
        mock_analyzer.analyze_keyword_trends.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
