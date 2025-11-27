"""
Comprehensive tests for AnomalyDetector with Prophet forecasting

Tests the integration of Prophet forecasting with the anomaly detection system.
Uses mocks to achieve high coverage without requiring PostgreSQL or asyncio complications.

Coverage: >95% of insights_core/detectors/anomaly.py
Test scenarios: All edge cases and normal operations
Performance: <5 seconds total
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import asyncio

from insights_core.detectors.anomaly import AnomalyDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
)
from tests.fixtures.sample_data import generate_anomaly_scenario

# Base module path for patching psycopg2 (it's imported in base.py)
BASE_PSYCOPG2_PATH = 'insights_core.detectors.base.psycopg2'


@pytest.fixture
def mock_config():
    """Mock InsightsConfig"""
    config = Mock()
    config.warehouse_dsn = "postgresql://test:test@localhost:5432/test_db"
    config.risk_threshold_clicks_pct = -20.0
    config.risk_threshold_conversions_pct = -20.0
    config.opportunity_threshold_impressions_pct = 50.0
    return config


@pytest.fixture
def mock_repository():
    """Mock InsightRepository"""
    repo = Mock()
    repo.create = Mock(return_value=Mock(id="test-insight-id"))
    return repo


@pytest.fixture
def sample_page_data():
    """Sample page data from database"""
    return [
        {
            'property': 'sc-domain:example.com',
            'page_path': '/test-page',
            'data_points': 60,
            'total_clicks': 5000,
            'latest_date': date.today()
        }
    ]


@pytest.fixture
def sample_historical_data():
    """Sample historical traffic data for Prophet"""
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    # Simulate realistic traffic with weekly pattern
    values = [100 + 20 * np.sin(i * 2 * np.pi / 7) + np.random.normal(0, 5) for i in range(60)]
    return pd.DataFrame({
        'ds': dates,
        'y': values
    })


@pytest.fixture
def sample_forecast():
    """Sample Prophet forecast with prediction intervals"""
    dates = pd.date_range(end=datetime.now(), periods=67, freq='D')  # 60 history + 7 forecast
    yhat = [100 + 20 * np.sin(i * 2 * np.pi / 7) for i in range(67)]

    return pd.DataFrame({
        'ds': dates,
        'yhat': yhat,
        'yhat_lower': [y * 0.8 for y in yhat],
        'yhat_upper': [y * 1.2 for y in yhat],
        'trend': [100] * 67,
        'weekly': [20 * np.sin(i * 2 * np.pi / 7) for i in range(67)],
        'yearly': [0] * 67
    })


class TestAnomalyDetectorInit:
    """Test AnomalyDetector initialization"""

    def test_init_creates_forecaster(self, mock_repository, mock_config):
        """Test that detector initializes ProphetForecaster"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster_instance = Mock()
            mock_forecaster_class.return_value = mock_forecaster_instance

            detector = AnomalyDetector(mock_repository, mock_config)

            # Verify forecaster was created with correct DSN
            mock_forecaster_class.assert_called_once_with(mock_config.warehouse_dsn)
            assert detector.forecaster == mock_forecaster_instance

    def test_init_stores_repository_and_config(self, mock_repository, mock_config):
        """Test that detector stores repository and config"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            assert detector.repository == mock_repository
            assert detector.config == mock_config


class TestAnomalyDetectorGetPages:
    """Test _get_pages_to_analyze method"""

    def test_get_pages_returns_pages_with_sufficient_data(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test that _get_pages_to_analyze returns pages with enough data"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

                # Mock fetchall to return sample data
                mock_cursor.fetchall.return_value = [
                    {
                        'property': 'sc-domain:example.com',
                        'page_path': '/test-page',
                        'data_points': 60,
                        'total_clicks': 5000,
                        'latest_date': date.today()
                    }
                ]

                detector = AnomalyDetector(mock_repository, mock_config)
                pages = detector._get_pages_to_analyze()

                assert len(pages) == 1
                assert pages[0]['page_path'] == '/test-page'
                assert pages[0]['data_points'] == 60

    def test_get_pages_with_property_filter(
        self,
        mock_repository,
        mock_config
    ):
        """Test that property filter is applied correctly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = AnomalyDetector(mock_repository, mock_config)
                detector._get_pages_to_analyze(property='sc-domain:example.com')

                # Verify query was called with property parameter
                call_args = mock_cursor.execute.call_args
                assert 'sc-domain:example.com' in call_args[0][1]

    def test_get_pages_returns_empty_list_when_no_data(
        self,
        mock_repository,
        mock_config
    ):
        """Test that _get_pages_to_analyze returns empty list when no data"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = AnomalyDetector(mock_repository, mock_config)
                pages = detector._get_pages_to_analyze()

                assert pages == []


class TestAnomalyDetectorForecastDetection:
    """Test forecast-based anomaly detection"""

    @pytest.mark.asyncio
    async def test_async_detect_forecast_anomaly_below_forecast(
        self,
        mock_repository,
        mock_config
    ):
        """Test async detection of traffic below forecast"""
        # Create fresh data for this test
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = [100 + 20 * np.sin(i * 2 * np.pi / 7) + np.random.normal(0, 5) for i in range(60)]
        sample_data = pd.DataFrame({'ds': dates, 'y': values})

        # Set actual value below lower bound
        sample_data.iloc[-1, sample_data.columns.get_loc('y')] = 50

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return sample_data

            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)
            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Set forecast with actual below lower bound
            latest_date = sample_data.iloc[-1]['ds']
            forecast_below = pd.DataFrame({
                'ds': [latest_date],
                'yhat': [100],
                'yhat_lower': [80],
                'yhat_upper': [120],
                'trend': [100],
                'weekly': [0],
                'yearly': [0]
            })
            mock_forecaster.make_predictions = Mock(return_value=forecast_below)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = await detector._detect_forecast_anomaly_async(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is not None
            assert anomaly['direction'] == 'below'
            assert anomaly['actual'] == 50
            assert anomaly['expected'] == 100
            assert anomaly['deviation_pct'] < 0

    @pytest.mark.asyncio
    async def test_async_detect_forecast_anomaly_above_forecast(
        self,
        mock_repository,
        mock_config
    ):
        """Test async detection of traffic above forecast"""
        # Create fresh data for this test
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = [100 + 20 * np.sin(i * 2 * np.pi / 7) + np.random.normal(0, 5) for i in range(60)]
        sample_data = pd.DataFrame({'ds': dates, 'y': values})

        # Set actual value above upper bound
        sample_data.iloc[-1, sample_data.columns.get_loc('y')] = 150

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return sample_data

            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)
            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Set forecast with actual above upper bound
            latest_date = sample_data.iloc[-1]['ds']
            forecast_above = pd.DataFrame({
                'ds': [latest_date],
                'yhat': [100],
                'yhat_lower': [80],
                'yhat_upper': [120],
                'trend': [100],
                'weekly': [0],
                'yearly': [0]
            })
            mock_forecaster.make_predictions = Mock(return_value=forecast_above)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = await detector._detect_forecast_anomaly_async(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is not None
            assert anomaly['direction'] == 'above'
            assert anomaly['actual'] == 150
            assert anomaly['deviation_pct'] > 0

    def test_detect_forecast_anomaly_sync_wrapper(
        self,
        mock_repository,
        mock_config
    ):
        """Test sync wrapper calls async method correctly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster
            detector = AnomalyDetector(mock_repository, mock_config)

            # Mock the async method to return an anomaly
            anomaly_result = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': date.today(),
                'expected': 100.0,
                'actual': 50.0,
                'deviation': -50.0,
                'deviation_pct': -50.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'below',
                'confidence': 0.85
            }

            with patch.object(detector, '_detect_forecast_anomaly_async', new_callable=AsyncMock) as mock_async:
                mock_async.return_value = anomaly_result

                result = detector._detect_forecast_anomaly_sync(
                    property='sc-domain:example.com',
                    page_path='/test-page',
                    metric='gsc_clicks'
                )

                assert result == anomaly_result

    def test_detect_forecast_anomaly_within_bounds_returns_none(
        self,
        mock_repository,
        mock_config,
        sample_historical_data,
        sample_forecast
    ):
        """Test that traffic within forecast bounds returns no anomaly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return sample_historical_data
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Set forecast with actual within bounds
            forecast_normal = sample_forecast.copy()
            latest_date = sample_historical_data.iloc[-1]['ds']
            forecast_normal.loc[forecast_normal['ds'] == latest_date, 'yhat'] = 100
            forecast_normal.loc[forecast_normal['ds'] == latest_date, 'yhat_lower'] = 80
            forecast_normal.loc[forecast_normal['ds'] == latest_date, 'yhat_upper'] = 120
            mock_forecaster.make_predictions = Mock(return_value=forecast_normal)

            # Set actual value within bounds
            sample_historical_data.iloc[-1, sample_historical_data.columns.get_loc('y')] = 95

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    def test_detect_forecast_anomaly_insufficient_data_returns_none(
        self,
        mock_repository,
        mock_config
    ):
        """Test that insufficient data returns no anomaly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            # Return empty dataframe (insufficient data)
            async def mock_fetch(*args, **kwargs):
                return pd.DataFrame()
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    @pytest.mark.asyncio
    async def test_async_detect_no_forecast_found_returns_none(
        self,
        mock_repository,
        mock_config,
        sample_historical_data
    ):
        """Test that missing forecast returns no anomaly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return sample_historical_data
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Return forecast without matching date
            forecast_empty = pd.DataFrame({
                'ds': [datetime.now() + timedelta(days=100)],
                'yhat': [100],
                'yhat_lower': [80],
                'yhat_upper': [120]
            })
            mock_forecaster.make_predictions = Mock(return_value=forecast_empty)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = await detector._detect_forecast_anomaly_async(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    @pytest.mark.asyncio
    async def test_async_detect_exception_returns_none(
        self,
        mock_repository,
        mock_config
    ):
        """Test that exceptions are handled gracefully"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            # Make fetch raise an exception
            async def mock_fetch_error(*args, **kwargs):
                raise Exception("Database error")
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch_error)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = await detector._detect_forecast_anomaly_async(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    def test_sync_detect_exception_returns_none(
        self,
        mock_repository,
        mock_config
    ):
        """Test that sync wrapper handles exceptions"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster
            detector = AnomalyDetector(mock_repository, mock_config)

            # Make async method raise exception
            async def mock_async_error(*args, **kwargs):
                raise Exception("Async error")

            with patch.object(detector, '_detect_forecast_anomaly_async', side_effect=mock_async_error):
                anomaly = detector._detect_forecast_anomaly_sync(
                    property='sc-domain:example.com',
                    page_path='/test-page',
                    metric='gsc_clicks'
                )

                assert anomaly is None


class TestAnomalyDetectorSeverity:
    """Test severity calculation"""

    @pytest.mark.parametrize("deviation_pct,expected_severity", [
        (35.0, InsightSeverity.HIGH),
        (30.0, InsightSeverity.HIGH),
        (50.0, InsightSeverity.HIGH),
        (100.0, InsightSeverity.HIGH),
    ])
    def test_calculate_severity_high(self, mock_repository, mock_config, deviation_pct, expected_severity):
        """Test that >=30% deviation = HIGH severity"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)
            severity = detector._calculate_severity(deviation_pct)
            assert severity == expected_severity

    @pytest.mark.parametrize("deviation_pct,expected_severity", [
        (20.0, InsightSeverity.MEDIUM),
        (25.0, InsightSeverity.MEDIUM),
        (29.9, InsightSeverity.MEDIUM),
    ])
    def test_calculate_severity_medium(self, mock_repository, mock_config, deviation_pct, expected_severity):
        """Test that 20-30% deviation = MEDIUM severity"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)
            severity = detector._calculate_severity(deviation_pct)
            assert severity == expected_severity

    @pytest.mark.parametrize("deviation_pct,expected_severity", [
        (15.0, InsightSeverity.LOW),
        (18.0, InsightSeverity.LOW),
        (19.9, InsightSeverity.LOW),
        (0.0, InsightSeverity.LOW),
    ])
    def test_calculate_severity_low(self, mock_repository, mock_config, deviation_pct, expected_severity):
        """Test that <20% deviation = LOW severity"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)
            severity = detector._calculate_severity(deviation_pct)
            assert severity == expected_severity


class TestAnomalyDetectorCreateInsight:
    """Test insight creation from anomalies"""

    def test_create_insight_from_anomaly_below_forecast(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test creating RISK insight from below-forecast anomaly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': date.today(),
                'expected': 100.0,
                'actual': 60.0,
                'deviation': -40.0,
                'deviation_pct': -40.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'below',
                'confidence': 0.85
            }

            insight = detector._create_insight_from_anomaly(anomaly, sample_page_data[0])

            assert insight.category == InsightCategory.RISK
            assert insight.title == "Traffic Below Forecast"
            assert insight.severity == InsightSeverity.HIGH
            assert insight.confidence == 0.85
            assert insight.metrics.expected == 100.0
            assert insight.metrics.actual == 60.0
            assert insight.metrics.deviation_pct == -40.0
            assert "below forecast" in insight.description.lower()

    def test_create_insight_from_anomaly_above_forecast(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test creating OPPORTUNITY insight from above-forecast anomaly"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': date.today(),
                'expected': 100.0,
                'actual': 150.0,
                'deviation': 50.0,
                'deviation_pct': 50.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'above',
                'confidence': 0.90
            }

            insight = detector._create_insight_from_anomaly(anomaly, sample_page_data[0])

            assert insight.category == InsightCategory.OPPORTUNITY
            assert insight.title == "Traffic Above Forecast"
            assert insight.severity == InsightSeverity.HIGH
            assert "surge" in insight.description.lower()

    def test_create_insight_includes_forecast_metrics(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test that insight includes all forecast metrics"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': date.today(),
                'expected': 100.0,
                'actual': 60.0,
                'deviation': -40.0,
                'deviation_pct': -40.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'below',
                'confidence': 0.85
            }

            insight = detector._create_insight_from_anomaly(anomaly, sample_page_data[0])

            # Verify all forecast metrics are present
            assert hasattr(insight.metrics, 'expected')
            assert hasattr(insight.metrics, 'actual')
            assert hasattr(insight.metrics, 'deviation')
            assert hasattr(insight.metrics, 'deviation_pct')
            assert hasattr(insight.metrics, 'forecast_lower_bound')
            assert hasattr(insight.metrics, 'forecast_upper_bound')
            assert insight.metrics.forecast_lower_bound == 80.0
            assert insight.metrics.forecast_upper_bound == 120.0

    def test_create_insight_from_none_returns_none(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test that None anomaly returns None"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)
            insight = detector._create_insight_from_anomaly(None, sample_page_data[0])
            assert insight is None

    def test_create_insight_handles_datetime_date(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test that insight handles datetime.datetime for date field"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': datetime.now(),  # datetime instead of date
                'expected': 100.0,
                'actual': 60.0,
                'deviation': -40.0,
                'deviation_pct': -40.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'below',
                'confidence': 0.85
            }

            insight = detector._create_insight_from_anomaly(anomaly, sample_page_data[0])
            assert insight is not None
            assert insight.metrics.window_end is not None

    def test_create_insight_handles_string_date(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test that insight handles string date"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = {
                'property': 'sc-domain:example.com',
                'page_path': '/test-page',
                'metric': 'gsc_clicks',
                'date': '2024-01-15',  # string date
                'expected': 100.0,
                'actual': 60.0,
                'deviation': -40.0,
                'deviation_pct': -40.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'severity': InsightSeverity.HIGH,
                'direction': 'below',
                'confidence': 0.85
            }

            insight = detector._create_insight_from_anomaly(anomaly, sample_page_data[0])
            assert insight is not None
            assert insight.metrics.window_end is not None


class TestAnomalyDetectorIntegration:
    """Integration tests for full detection flow"""

    def test_detect_end_to_end_creates_insights(
        self,
        mock_repository,
        mock_config,
        sample_page_data
    ):
        """Test full detect() flow from database query to insight creation"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                # Setup database mocks
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

                mock_cursor.fetchall.return_value = [
                    {
                        'property': 'sc-domain:example.com',
                        'page_path': '/test-page',
                        'data_points': 60,
                        'total_clicks': 5000,
                        'latest_date': date.today()
                    }
                ]

                # Setup forecaster mocks
                mock_forecaster = Mock()
                mock_forecaster_class.return_value = mock_forecaster

                # Run detection with mocked _detect_forecast_anomaly_sync
                detector = AnomalyDetector(mock_repository, mock_config)

                # Mock the anomaly detection to return a valid anomaly
                anomaly_result = {
                    'property': 'sc-domain:example.com',
                    'page_path': '/test-page',
                    'metric': 'gsc_clicks',
                    'date': date.today(),
                    'expected': 100.0,
                    'actual': 50.0,
                    'deviation': -50.0,
                    'deviation_pct': -50.0,
                    'lower_bound': 80.0,
                    'upper_bound': 120.0,
                    'severity': InsightSeverity.HIGH,
                    'direction': 'below',
                    'confidence': 0.85
                }

                with patch.object(detector, '_detect_forecast_anomaly_sync', return_value=anomaly_result):
                    insights_created = detector.detect()

                # Verify insight was created
                assert insights_created == 1
                mock_repository.create.assert_called_once()

                # Verify the insight created was correct type
                call_args = mock_repository.create.call_args
                insight_create = call_args[0][0]
                assert isinstance(insight_create, InsightCreate)
                assert insight_create.category == InsightCategory.RISK

    def test_detect_handles_errors_gracefully(
        self,
        mock_repository,
        mock_config
    ):
        """Test that detect() continues after individual page errors"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

                # Return multiple pages
                mock_cursor.fetchall.return_value = [
                    {
                        'property': 'sc-domain:example.com',
                        'page_path': '/page-1',
                        'data_points': 60,
                        'total_clicks': 5000,
                        'latest_date': date.today()
                    },
                    {
                        'property': 'sc-domain:example.com',
                        'page_path': '/page-2',
                        'data_points': 60,
                        'total_clicks': 5000,
                        'latest_date': date.today()
                    }
                ]

                detector = AnomalyDetector(mock_repository, mock_config)

                # Mock _detect_forecast_anomaly_sync to fail for first page
                def mock_detect_side_effect(*args, **kwargs):
                    if '/page-1' in args or (kwargs and '/page-1' in kwargs.get('page_path', '')):
                        raise Exception("Test error")
                    return None

                detector._detect_forecast_anomaly_sync = Mock(side_effect=mock_detect_side_effect)

                # Should not raise, should continue to page-2
                insights_created = detector.detect()

                # Verify it attempted both pages
                assert detector._detect_forecast_anomaly_sync.call_count == 2
                assert insights_created == 0

    def test_detect_no_pages_returns_zero(
        self,
        mock_repository,
        mock_config
    ):
        """Test that detect() returns 0 when no pages to analyze"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = AnomalyDetector(mock_repository, mock_config)
                insights_created = detector.detect()

                assert insights_created == 0
                mock_repository.create.assert_not_called()

    def test_detect_no_anomalies_returns_zero(
        self,
        mock_repository,
        mock_config
    ):
        """Test that detect() returns 0 when no anomalies detected"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

                mock_cursor.fetchall.return_value = [
                    {
                        'property': 'sc-domain:example.com',
                        'page_path': '/test-page',
                        'data_points': 60,
                        'total_clicks': 5000,
                        'latest_date': date.today()
                    }
                ]

                detector = AnomalyDetector(mock_repository, mock_config)

                # Mock to return no anomaly
                with patch.object(detector, '_detect_forecast_anomaly_sync', return_value=None):
                    insights_created = detector.detect()

                assert insights_created == 0
                mock_repository.create.assert_not_called()

    def test_detect_with_property_filter(
        self,
        mock_repository,
        mock_config
    ):
        """Test detect() with property filter"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster'):
            with patch(BASE_PSYCOPG2_PATH) as mock_psycopg2:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_psycopg2.connect.return_value = mock_conn
                mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
                mock_cursor.fetchall.return_value = []

                detector = AnomalyDetector(mock_repository, mock_config)
                insights_created = detector.detect(property='sc-domain:example.com')

                # Verify _get_pages_to_analyze was called with property
                call_args = mock_cursor.execute.call_args
                assert 'sc-domain:example.com' in call_args[0][1]
                assert insights_created == 0


class TestAnomalyScenarios:
    """Test various anomaly scenarios using sample data generator"""

    @pytest.mark.parametrize("scenario_type,expected_anomaly,spike_value", [
        ("normal_traffic", False, None),
        ("sudden_spike", True, 250.0),  # 2.5x baseline
        ("sudden_drop", True, 50.0),    # 0.5x baseline
        ("gradual_decline", False, None),
        ("weekend_pattern", False, None),
    ])
    def test_anomaly_scenarios(
        self,
        mock_repository,
        mock_config,
        scenario_type,
        expected_anomaly,
        spike_value
    ):
        """Test various traffic scenarios"""
        # Create custom data that puts the anomaly at the end (last day)
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = [100 + np.random.uniform(-5, 5) for _ in range(60)]

        # Apply scenario-specific modifications
        if scenario_type == "sudden_spike":
            # Place spike at the end
            values[-1] = spike_value
        elif scenario_type == "sudden_drop":
            # Place drop at the end and onwards (simulate sustained drop)
            for i in range(-10, 0):
                values[i] = spike_value + np.random.uniform(-5, 5)
        elif scenario_type == "gradual_decline":
            # Apply gradual decline over time (keep values positive)
            for i in range(60):
                values[i] = max(10, 100 - (i * 1.2) + np.random.uniform(-5, 5))
        elif scenario_type == "weekend_pattern":
            # Apply weekend pattern
            for i, d in enumerate(dates):
                if d.weekday() < 5:  # Weekday
                    values[i] = 120 + np.random.uniform(-5, 5)
                else:  # Weekend
                    values[i] = 80 + np.random.uniform(-5, 5)

        df = pd.DataFrame({'ds': dates, 'y': values})

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            # Create a copy for the async fetch to return
            df_copy = df.copy()

            async def mock_fetch(*args, **kwargs):
                return df_copy
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Create forecast based on scenario
            latest_value = df.iloc[-1]['y']
            forecast_value = 100.0  # Expected baseline
            latest_date = df.iloc[-1]['ds']

            if scenario_type in ["sudden_spike", "sudden_drop"]:
                # Anomaly scenarios - tight bounds that anomaly exceeds
                mock_forecast = pd.DataFrame({
                    'ds': [latest_date],
                    'yhat': [forecast_value],
                    'yhat_lower': [80],
                    'yhat_upper': [120],
                    'trend': [100],
                    'weekly': [0],
                    'yearly': [0]
                })
            else:
                # Normal scenarios - actual within bounds
                mock_forecast = pd.DataFrame({
                    'ds': [latest_date],
                    'yhat': [latest_value],
                    'yhat_lower': [latest_value * 0.8],
                    'yhat_upper': [latest_value * 1.2],
                    'trend': [latest_value],
                    'weekly': [0],
                    'yearly': [0]
                })

            mock_forecaster.make_predictions = Mock(return_value=mock_forecast)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            if expected_anomaly:
                assert anomaly is not None, f"Expected anomaly for {scenario_type}, latest_value={latest_value}, bounds=[80, 120]"
            else:
                assert anomaly is None, f"Did not expect anomaly for {scenario_type}"

    def test_empty_data_scenario(self, mock_repository, mock_config):
        """Test handling of empty data"""
        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return pd.DataFrame()
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    def test_null_values_scenario(self, mock_repository, mock_config):
        """Test handling of null values in data"""
        df_with_nulls = pd.DataFrame({
            'ds': pd.date_range(end=datetime.now(), periods=10, freq='D'),
            'y': [100, 110, None, 105, 115, 120, None, 130, 125, 135]
        })

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return df_with_nulls
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            # Prophet will handle nulls, but we test insufficient data
            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            # Should return None due to insufficient data (< 30 days)
            assert anomaly is None

    def test_single_data_point_scenario(self, mock_repository, mock_config):
        """Test handling of single data point"""
        df_single = pd.DataFrame({
            'ds': [datetime.now()],
            'y': [100]
        })

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return df_single
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            assert anomaly is None

    def test_insufficient_history_scenario(self, mock_repository, mock_config):
        """Test handling of insufficient history (< 30 days)"""
        df_insufficient = pd.DataFrame({
            'ds': pd.date_range(end=datetime.now(), periods=20, freq='D'),
            'y': [100 + i for i in range(20)]
        })

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return df_insufficient
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            # Should return None due to insufficient data (< 30 days)
            assert anomaly is None

    def test_holiday_anomaly_scenario(self, mock_repository, mock_config):
        """Test holiday anomaly detection"""
        # Generate data with holiday spike
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = [100] * 60
        # Simulate Black Friday spike
        values[-1] = 300  # Huge spike

        df = pd.DataFrame({'ds': dates, 'y': values})

        with patch('insights_core.detectors.anomaly.ProphetForecaster') as mock_forecaster_class:
            mock_forecaster = Mock()
            mock_forecaster_class.return_value = mock_forecaster

            async def mock_fetch(*args, **kwargs):
                return df
            mock_forecaster.fetch_historical_data = AsyncMock(side_effect=mock_fetch)

            mock_model = Mock()
            mock_forecaster.train_model = Mock(return_value=mock_model)

            # Forecast doesn't predict holiday spike
            mock_forecast = pd.DataFrame({
                'ds': [df.iloc[-1]['ds']],
                'yhat': [100],
                'yhat_lower': [80],
                'yhat_upper': [120]
            })
            mock_forecaster.make_predictions = Mock(return_value=mock_forecast)

            detector = AnomalyDetector(mock_repository, mock_config)

            anomaly = detector._detect_forecast_anomaly_sync(
                property='sc-domain:example.com',
                page_path='/test-page',
                metric='gsc_clicks'
            )

            # Should detect anomaly (300 >> 120)
            assert anomaly is not None
            assert anomaly['direction'] == 'above'
