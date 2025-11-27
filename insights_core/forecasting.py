"""
Prophet Forecasting - ML-Based Traffic Prediction
================================================
Replaces Z-score anomaly detection with Prophet time series forecasting:
- Seasonal pattern detection (daily, weekly, yearly)
- Traffic forecasting
- Intelligent anomaly detection
- Trend analysis

Features:
- Handles seasonality automatically
- Fewer false positives
- Predicts future traffic
- Detects true anomalies vs normal fluctuations
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import asyncpg
import numpy as np
import pandas as pd
from prophet import Prophet

logger = logging.getLogger(__name__)


class ProphetForecaster:
    """
    Traffic forecasting using Facebook Prophet
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize forecaster

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("ProphetForecaster initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def fetch_historical_data(
        self,
        property: str,
        page_path: str = None,
        metric: str = 'gsc_clicks',
        days_back: int = 90
    ) -> pd.DataFrame:
        """
        Fetch historical data for forecasting

        Args:
            property: Property URL
            page_path: Optional page path (None = property level)
            metric: Metric to forecast
            days_back: Days of historical data

        Returns:
            DataFrame with ds (date) and y (value) columns
        """
        try:
            pool = await self.get_pool()

            cutoff_date = datetime.utcnow().date() - timedelta(days=days_back)

            async with pool.acquire() as conn:
                if page_path:
                    query = f"""
                        SELECT
                            date AS ds,
                            {metric} AS y
                        FROM gsc.vw_unified_page_performance
                        WHERE property = $1
                            AND page_path = $2
                            AND date >= $3
                            AND {metric} > 0
                        ORDER BY date
                    """
                    results = await conn.fetch(query, property, page_path, cutoff_date)
                else:
                    query = f"""
                        SELECT
                            date AS ds,
                            SUM({metric}) AS y
                        FROM gsc.vw_unified_page_performance
                        WHERE property = $1
                            AND date >= $2
                            AND {metric} > 0
                        GROUP BY date
                        ORDER BY date
                    """
                    results = await conn.fetch(query, property, cutoff_date)

            if not results:
                logger.warning(f"No data found for {property} {page_path or 'property-level'}")
                return pd.DataFrame()

            df = pd.DataFrame(results, columns=['ds', 'y'])
            df['ds'] = pd.to_datetime(df['ds'])

            logger.info(f"Fetched {len(df)} days of data for {property}")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()

    def train_model(
        self,
        df: pd.DataFrame,
        seasonality_mode: str = 'multiplicative',
        weekly_seasonality: bool = True,
        yearly_seasonality: bool = True
    ) -> Prophet:
        """
        Train Prophet model

        Args:
            df: DataFrame with ds and y columns
            seasonality_mode: 'additive' or 'multiplicative'
            weekly_seasonality: Include weekly seasonality
            yearly_seasonality: Include yearly seasonality

        Returns:
            Trained Prophet model
        """
        try:
            if df.empty or len(df) < 14:
                raise ValueError("Insufficient data for training (need at least 14 days)")

            model = Prophet(
                seasonality_mode=seasonality_mode,
                weekly_seasonality=weekly_seasonality,
                yearly_seasonality=yearly_seasonality if len(df) >= 365 else False,
                daily_seasonality=False,  # Usually too noisy
                changepoint_prior_scale=0.05,  # Less flexible = fewer false changepoints
                seasonality_prior_scale=10.0,  # Strong seasonality
                interval_width=0.95  # 95% confidence interval
            )

            # Add holidays (US by default, can be customized)
            model.add_country_holidays(country_name='US')

            # Suppress cmdstanpy logging
            import logging as prophet_logging
            prophet_logging.getLogger('cmdstanpy').setLevel(prophet_logging.WARNING)

            model.fit(df)

            logger.info("Prophet model trained successfully")
            return model

        except Exception as e:
            logger.error(f"Error training model: {e}")
            raise

    def make_predictions(
        self,
        model: Prophet,
        periods: int = 30
    ) -> pd.DataFrame:
        """
        Make future predictions

        Args:
            model: Trained Prophet model
            periods: Days to forecast

        Returns:
            DataFrame with predictions
        """
        try:
            future = model.make_future_dataframe(periods=periods)
            forecast = model.predict(future)

            return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper',
                           'trend', 'weekly', 'yearly']]

        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            raise

    async def store_forecasts(
        self,
        property: str,
        page_path: str,
        metric: str,
        forecast: pd.DataFrame,
        model_id: str
    ) -> int:
        """
        Store forecasts in database

        Args:
            property: Property URL
            page_path: Page path
            metric: Metric name
            forecast: Forecast DataFrame
            model_id: Model identifier

        Returns:
            Number of forecasts stored
        """
        try:
            pool = await self.get_pool()
            stored = 0

            async with pool.acquire() as conn:
                for _, row in forecast.iterrows():
                    if row['ds'] >= datetime.utcnow().date():
                        await conn.execute("""
                            INSERT INTO intelligence.traffic_forecasts (
                                property,
                                page_path,
                                date,
                                metric_name,
                                forecast_value,
                                lower_bound,
                                upper_bound,
                                trend_component,
                                weekly_seasonal,
                                yearly_seasonal,
                                model_id,
                                created_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            ON CONFLICT (property, page_path, date, metric_name, created_at)
                            DO UPDATE SET
                                forecast_value = EXCLUDED.forecast_value,
                                lower_bound = EXCLUDED.lower_bound,
                                upper_bound = EXCLUDED.upper_bound
                        """,
                            property,
                            page_path or '',
                            row['ds'].date(),
                            metric,
                            float(row['yhat']),
                            float(row['yhat_lower']),
                            float(row['yhat_upper']),
                            float(row['trend']) if 'trend' in row else None,
                            float(row['weekly']) if 'weekly' in row else None,
                            float(row['yearly']) if 'yearly' in row else None,
                            model_id,
                            datetime.utcnow()
                        )
                        stored += 1

            logger.info(f"Stored {stored} forecast records")
            return stored

        except Exception as e:
            logger.error(f"Error storing forecasts: {e}")
            return 0

    async def detect_anomalies(
        self,
        property: str,
        page_path: str = None,
        lookback_days: int = 7
    ) -> List[Dict]:
        """
        Detect anomalies by comparing actuals to forecasts

        Args:
            property: Property URL
            page_path: Optional page path
            lookback_days: Days to check

        Returns:
            List of detected anomalies
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                if page_path:
                    query = """
                        SELECT
                            f.date,
                            f.metric_name,
                            f.forecast_value,
                            f.lower_bound,
                            f.upper_bound,
                            v.gsc_clicks AS actual
                        FROM intelligence.traffic_forecasts f
                        JOIN gsc.vw_unified_page_performance v
                            ON f.property = v.property
                            AND f.page_path = v.page_path
                            AND f.date = v.date
                        WHERE f.property = $1
                            AND f.page_path = $2
                            AND f.date >= CURRENT_DATE - $3
                            AND f.date < CURRENT_DATE
                            AND v.gsc_clicks IS NOT NULL
                    """
                    results = await conn.fetch(query, property, page_path, lookback_days)
                else:
                    query = """
                        SELECT
                            f.date,
                            f.metric_name,
                            f.forecast_value,
                            f.lower_bound,
                            f.upper_bound,
                            SUM(v.gsc_clicks) AS actual
                        FROM intelligence.traffic_forecasts f
                        JOIN gsc.vw_unified_page_performance v
                            ON f.property = v.property
                            AND f.date = v.date
                        WHERE f.property = $1
                            AND f.page_path = ''
                            AND f.date >= CURRENT_DATE - $2
                            AND f.date < CURRENT_DATE
                        GROUP BY f.date, f.metric_name, f.forecast_value, f.lower_bound, f.upper_bound
                    """
                    results = await conn.fetch(query, property, lookback_days)

            anomalies = []

            for row in results:
                actual = float(row['actual'])
                forecast = float(row['forecast_value'])
                lower = float(row['lower_bound'])
                upper = float(row['upper_bound'])

                # Check if actual falls outside prediction interval
                if actual < lower or actual > upper:
                    deviation = actual - forecast
                    deviation_pct = (deviation / forecast) * 100 if forecast > 0 else 0

                    # Determine severity
                    if abs(deviation_pct) >= 50:
                        severity = 'critical'
                    elif abs(deviation_pct) >= 30:
                        severity = 'high'
                    elif abs(deviation_pct) >= 15:
                        severity = 'medium'
                    else:
                        severity = 'low'

                    anomaly = {
                        'property': property,
                        'page_path': page_path or '',
                        'date': row['date'],
                        'metric': row['metric_name'],
                        'actual': actual,
                        'forecast': forecast,
                        'deviation': deviation,
                        'deviation_pct': round(deviation_pct, 2),
                        'severity': severity,
                        'direction': 'above' if actual > upper else 'below'
                    }

                    anomalies.append(anomaly)

                    # Store in anomaly log
                    await conn.execute("""
                        INSERT INTO intelligence.anomaly_log (
                            property,
                            page_path,
                            detection_date,
                            metric_name,
                            actual_value,
                            expected_value,
                            deviation,
                            deviation_pct,
                            severity,
                            direction,
                            confidence
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (property, page_path, detection_date, metric_name)
                        DO UPDATE SET
                            deviation_pct = EXCLUDED.deviation_pct,
                            severity = EXCLUDED.severity
                    """,
                        property,
                        page_path or '',
                        row['date'],
                        row['metric_name'],
                        actual,
                        forecast,
                        deviation,
                        deviation_pct,
                        severity,
                        'above' if actual > upper else 'below',
                        0.9  # High confidence since based on Prophet
                    )

            logger.info(f"Detected {len(anomalies)} anomalies for {property}")
            return anomalies

        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return []

    async def forecast_page(
        self,
        property: str,
        page_path: str,
        days_ahead: int = 30,
        metric: str = 'gsc_clicks'
    ) -> Dict:
        """
        Generate forecast for a single page

        Args:
            property: Property URL
            page_path: Page path
            days_ahead: Days to forecast
            metric: Metric to forecast

        Returns:
            Forecast results
        """
        try:
            # Fetch data
            df = await self.fetch_historical_data(property, page_path, metric)

            if df.empty:
                return {'error': 'no_data'}

            # Train model
            model = self.train_model(df)

            # Make predictions
            forecast = self.make_predictions(model, days_ahead)

            # Calculate model performance (on training data)
            historical_predictions = forecast[forecast['ds'] < datetime.utcnow()]
            actuals = df.merge(historical_predictions, on='ds', how='inner')

            if len(actuals) > 0:
                mae = np.mean(np.abs(actuals['y'] - actuals['yhat']))
                rmse = np.sqrt(np.mean((actuals['y'] - actuals['yhat']) ** 2))
            else:
                mae = rmse = None

            # Store forecasts
            model_id = f"prophet_{property}_{page_path}_{datetime.utcnow().isoformat()}"
            stored = await self.store_forecasts(property, page_path, metric, forecast, model_id)

            return {
                'property': property,
                'page_path': page_path,
                'metric': metric,
                'days_forecasted': days_ahead,
                'records_stored': stored,
                'model_mae': round(mae, 2) if mae else None,
                'model_rmse': round(rmse, 2) if rmse else None,
                'model_id': model_id,
                'success': True
            }

        except Exception as e:
            logger.error(f"Error forecasting page: {e}")
            return {'error': str(e), 'success': False}

    async def forecast_property(
        self,
        property: str,
        days_ahead: int = 30,
        metric: str = 'gsc_clicks'
    ) -> Dict:
        """
        Generate property-level forecast

        Args:
            property: Property URL
            days_ahead: Days to forecast
            metric: Metric to forecast

        Returns:
            Forecast results
        """
        return await self.forecast_page(property, None, days_ahead, metric)

    def forecast_sync(
        self,
        property: str,
        page_path: str = None,
        days_ahead: int = 30
    ) -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.forecast_page(property, page_path, days_ahead))
