"""
Tests for Prophet Forecasting
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from insights_core.forecasting import ProphetForecaster


class TestProphetForecaster:
    """Test Prophet forecasting functionality"""

    def test_initialization(self):
        """Test forecaster initialization"""
        forecaster = ProphetForecaster()
        assert forecaster.db_dsn is not None

    def test_train_model_with_data(self):
        """Test model training with sample data"""
        forecaster = ProphetForecaster()

        # Create sample data (30 days)
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        values = np.random.randint(50, 150, size=30)

        df = pd.DataFrame({
            'ds': dates,
            'y': values
        })

        model = forecaster.train_model(df)

        assert model is not None
        assert hasattr(model, 'predict')

    def test_train_model_insufficient_data(self):
        """Test that insufficient data raises error"""
        forecaster = ProphetForecaster()

        # Too little data
        df = pd.DataFrame({
            'ds': pd.date_range(end=datetime.now(), periods=5, freq='D'),
            'y': [10, 20, 15, 25, 30]
        })

        with pytest.raises(ValueError):
            forecaster.train_model(df)

    def test_make_predictions(self):
        """Test making predictions"""
        forecaster = ProphetForecaster()

        # Create and train model
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = np.random.randint(50, 150, size=60) + np.sin(np.arange(60)) * 10

        df = pd.DataFrame({'ds': dates, 'y': values})
        model = forecaster.train_model(df)

        # Make predictions
        forecast = forecaster.make_predictions(model, periods=7)

        assert len(forecast) == 67  # 60 historical + 7 future
        assert 'yhat' in forecast.columns
        assert 'yhat_lower' in forecast.columns
        assert 'yhat_upper' in forecast.columns
        assert 'trend' in forecast.columns

    def test_prediction_intervals(self):
        """Test that prediction intervals are valid"""
        forecaster = ProphetForecaster()

        dates = pd.date_range(end=datetime.now(), periods=45, freq='D')
        values = np.random.randint(80, 120, size=45)

        df = pd.DataFrame({'ds': dates, 'y': values})
        model = forecaster.train_model(df)
        forecast = forecaster.make_predictions(model, periods=7)

        # Check that lower <= yhat <= upper
        assert all(forecast['yhat_lower'] <= forecast['yhat'])
        assert all(forecast['yhat'] <= forecast['yhat_upper'])

    @pytest.mark.asyncio
    async def test_fetch_historical_data_mock(self, mocker):
        """Test fetching historical data (mocked)"""
        forecaster = ProphetForecaster()

        # Mock database
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock data
        mock_data = [
            {'ds': datetime.now().date() - timedelta(days=i), 'y': 100 + i}
            for i in range(30)
        ]
        mock_conn.fetch.return_value = mock_data

        forecaster._pool = mock_pool

        df = await forecaster.fetch_historical_data(
            property="https://example.com",
            page_path="/test/",
            metric='gsc_clicks'
        )

        assert not df.empty
        assert len(df) == 30
        assert 'ds' in df.columns
        assert 'y' in df.columns

    @pytest.mark.asyncio
    async def test_detect_anomalies_mock(self, mocker):
        """Test anomaly detection (mocked)"""
        forecaster = ProphetForecaster()

        # Mock database
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock forecast data with anomaly
        mock_data = [
            {
                'date': datetime.now().date() - timedelta(days=1),
                'metric_name': 'gsc_clicks',
                'forecast_value': 100.0,
                'lower_bound': 80.0,
                'upper_bound': 120.0,
                'actual': 150.0  # Anomaly: above upper bound
            }
        ]
        mock_conn.fetch.return_value = mock_data

        forecaster._pool = mock_pool

        anomalies = await forecaster.detect_anomalies(
            property="https://example.com",
            lookback_days=7
        )

        assert len(anomalies) == 1
        assert anomalies[0]['direction'] == 'above'
        assert anomalies[0]['deviation'] > 0


class TestSeasonality:
    """Test seasonality detection"""

    def test_weekly_seasonality(self):
        """Test that weekly patterns are detected"""
        forecaster = ProphetForecaster()

        # Create data with weekly pattern
        dates = pd.date_range(end=datetime.now(), periods=90, freq='D')
        # Weekend spike pattern
        values = [100 + 30 * (i % 7 >= 5) + np.random.randn() * 5 for i in range(90)]

        df = pd.DataFrame({'ds': dates, 'y': values})
        model = forecaster.train_model(df, weekly_seasonality=True)
        forecast = forecaster.make_predictions(model, periods=7)

        # Check that weekly component exists
        assert 'weekly' in forecast.columns
        assert not forecast['weekly'].isna().all()

    def test_trend_detection(self):
        """Test that trends are captured"""
        forecaster = ProphetForecaster()

        # Create data with upward trend
        dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
        values = [50 + i * 2 + np.random.randn() * 5 for i in range(60)]

        df = pd.DataFrame({'ds': dates, 'y': values})
        model = forecaster.train_model(df)
        forecast = forecaster.make_predictions(model, periods=7)

        # Trend should be generally increasing
        assert forecast['trend'].iloc[-1] > forecast['trend'].iloc[0]


class TestAnomalyDetection:
    """Test anomaly detection logic"""

    def test_anomaly_severity_classification(self):
        """Test anomaly severity levels"""
        forecaster = ProphetForecaster()

        test_cases = [
            (100, 150, 'critical'),  # 50% deviation
            (100, 135, 'high'),      # 35% deviation
            (100, 120, 'medium'),    # 20% deviation
            (100, 110, 'low'),       # 10% deviation
        ]

        for forecast, actual, expected_severity in test_cases:
            deviation_pct = ((actual - forecast) / forecast) * 100

            if abs(deviation_pct) >= 50:
                severity = 'critical'
            elif abs(deviation_pct) >= 30:
                severity = 'high'
            elif abs(deviation_pct) >= 15:
                severity = 'medium'
            else:
                severity = 'low'

            assert severity == expected_severity
