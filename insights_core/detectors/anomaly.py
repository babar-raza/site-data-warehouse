"""
Anomaly Detector - Finds statistical anomalies in traffic using Prophet forecasting

This detector uses Facebook Prophet for time series forecasting to identify
true anomalies versus normal seasonal fluctuations. Prophet automatically
handles:
- Weekly seasonality (weekday vs weekend patterns)
- Yearly seasonality (seasonal trends)
- Holiday effects
- Trend changes

This approach provides more accurate anomaly detection with fewer false
positives compared to simple statistical methods like Z-score.
"""
import logging
import asyncio
from typing import List
from datetime import datetime, timedelta, date
from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)
from insights_core.forecasting import ProphetForecaster

logger = logging.getLogger(__name__)


class AnomalyDetector(BaseDetector):
    """
    Detects anomalies in GSC metrics using Prophet forecasting

    Detection Process:
    1. Fetch historical data for each page (90 days)
    2. Train Prophet model on historical patterns
    3. Generate forecasts for recent days
    4. Compare actual vs forecast to detect anomalies

    Severity Levels:
    - HIGH: >30% deviation from forecast
    - MEDIUM: >20% deviation from forecast
    - LOW: >15% deviation from forecast

    Example Insight:
        {
            "title": "Traffic Below Forecast",
            "description": "Page traffic is 35.2% below forecast. Expected 150 clicks, actual 97.",
            "severity": "high",
            "metrics": {
                "expected": 150,
                "actual": 97,
                "deviation_pct": -35.2,
                "lower_bound": 120,
                "upper_bound": 180
            }
        }
    """

    def __init__(self, repository, config):
        """
        Initialize AnomalyDetector with Prophet forecasting

        Args:
            repository: InsightRepository for persisting insights
            config: InsightsConfig with thresholds and settings
        """
        super().__init__(repository, config)
        # Initialize Prophet forecaster with warehouse DSN
        self.forecaster = ProphetForecaster(config.warehouse_dsn)
        logger.info("AnomalyDetector initialized with Prophet forecasting")

    def detect(self, property: str = None) -> int:
        """
        Run anomaly detection using Prophet forecasting

        Args:
            property: Optional property filter (None = all properties)

        Returns:
            Number of insights created
        """
        logger.info("Starting Prophet-based anomaly detection...")

        # Get pages to analyze
        pages = self._get_pages_to_analyze(property)
        logger.info(f"Analyzing {len(pages)} pages for anomalies")

        insights_created = 0

        for page_data in pages:
            try:
                # Detect forecast anomaly for this page
                anomaly = self._detect_forecast_anomaly_sync(
                    property=page_data['property'],
                    page_path=page_data['page_path'],
                    metric='gsc_clicks'
                )

                if anomaly:
                    # Create insight from anomaly
                    insight_create = self._create_insight_from_anomaly(
                        anomaly,
                        page_data
                    )

                    if insight_create:
                        self.repository.create(insight_create)
                        insights_created += 1
                        logger.info(
                            f"Created anomaly insight for {page_data['page_path']}: "
                            f"{anomaly['deviation_pct']:.1f}% deviation"
                        )

            except Exception as e:
                logger.warning(
                    f"Failed to analyze {page_data['page_path']}: {e}",
                    exc_info=True
                )
                continue

        logger.info(f"AnomalyDetector created {insights_created} insights")
        return insights_created

    def _get_pages_to_analyze(self, property: str = None) -> List[dict]:
        """
        Get pages with sufficient data for forecasting

        Args:
            property: Optional property filter

        Returns:
            List of page data dicts with property, page_path, recent clicks
        """
        conn = self._get_db_connection()
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get pages with at least 30 days of data and minimum traffic
                query = """
                    SELECT
                        property,
                        page_path,
                        COUNT(*) as data_points,
                        SUM(gsc_clicks) as total_clicks,
                        MAX(date) as latest_date
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '90 days'
                        AND gsc_clicks > 0
                """
                params = []

                if property:
                    query += " AND property = %s"
                    params.append(property)

                query += """
                    GROUP BY property, page_path
                    HAVING COUNT(*) >= 30 AND SUM(gsc_clicks) >= 100
                    ORDER BY SUM(gsc_clicks) DESC
                    LIMIT 50
                """

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def _detect_forecast_anomaly_sync(
        self,
        property: str,
        page_path: str,
        metric: str = 'gsc_clicks'
    ) -> dict:
        """
        Synchronous wrapper for async forecast anomaly detection

        This method bridges the sync detector interface with the async
        Prophet forecaster by using asyncio.run().

        Args:
            property: Property URL
            page_path: Page path
            metric: Metric to analyze (default: gsc_clicks)

        Returns:
            Anomaly dict with expected, actual, deviation, severity, or None
        """
        try:
            # Run async detection in sync context
            return asyncio.run(
                self._detect_forecast_anomaly_async(property, page_path, metric)
            )
        except Exception as e:
            logger.error(f"Error in forecast anomaly detection: {e}")
            return None

    async def _detect_forecast_anomaly_async(
        self,
        property: str,
        page_path: str,
        metric: str
    ) -> dict:
        """
        Async implementation of forecast anomaly detection

        Process:
        1. Fetch historical data (90 days)
        2. Train Prophet model
        3. Generate forecast for recent period
        4. Compare latest actual vs forecast
        5. Return anomaly if outside confidence interval

        Args:
            property: Property URL
            page_path: Page path
            metric: Metric to analyze

        Returns:
            Anomaly dict or None if no anomaly detected
        """
        try:
            # Fetch historical data
            df = await self.forecaster.fetch_historical_data(
                property=property,
                page_path=page_path,
                metric=metric,
                days_back=90
            )

            if df.empty or len(df) < 30:
                logger.debug(f"Insufficient data for {page_path}: {len(df)} days")
                return None

            # Train Prophet model
            model = self.forecaster.train_model(df)

            # Generate forecast for historical period (to compare with actuals)
            forecast = self.forecaster.make_predictions(model, periods=7)

            # Get latest actual value
            latest_actual = df.iloc[-1]
            latest_date = latest_actual['ds']
            actual_value = float(latest_actual['y'])

            # Find corresponding forecast
            forecast_row = forecast[forecast['ds'] == latest_date]

            if forecast_row.empty:
                logger.debug(f"No forecast found for {latest_date}")
                return None

            forecast_row = forecast_row.iloc[0]
            expected_value = float(forecast_row['yhat'])
            lower_bound = float(forecast_row['yhat_lower'])
            upper_bound = float(forecast_row['yhat_upper'])

            # Check if actual is outside prediction interval
            if actual_value < lower_bound or actual_value > upper_bound:
                deviation = actual_value - expected_value
                deviation_pct = (deviation / expected_value * 100) if expected_value > 0 else 0

                # Calculate severity based on deviation percentage
                severity = self._calculate_severity(abs(deviation_pct))

                # Determine direction
                direction = 'above' if actual_value > upper_bound else 'below'

                # Calculate confidence based on how far outside interval
                if direction == 'below':
                    confidence = min(0.95, 0.7 + (lower_bound - actual_value) / lower_bound * 0.25)
                else:
                    confidence = min(0.95, 0.7 + (actual_value - upper_bound) / upper_bound * 0.25)

                logger.info(
                    f"Anomaly detected for {page_path}: "
                    f"expected {expected_value:.0f}, actual {actual_value:.0f} "
                    f"({deviation_pct:+.1f}%)"
                )

                return {
                    'property': property,
                    'page_path': page_path,
                    'metric': metric,
                    'date': latest_date.date() if hasattr(latest_date, 'date') else latest_date,
                    'expected': expected_value,
                    'actual': actual_value,
                    'deviation': deviation,
                    'deviation_pct': round(deviation_pct, 2),
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                    'severity': severity,
                    'direction': direction,
                    'confidence': round(confidence, 2)
                }

            # No anomaly detected
            return None

        except Exception as e:
            logger.error(f"Error in async forecast anomaly detection: {e}")
            return None

    def _calculate_severity(self, deviation_pct: float) -> InsightSeverity:
        """
        Calculate severity based on deviation percentage

        Args:
            deviation_pct: Absolute deviation percentage

        Returns:
            InsightSeverity (HIGH, MEDIUM, or LOW)
        """
        if deviation_pct >= 30:
            return InsightSeverity.HIGH
        elif deviation_pct >= 20:
            return InsightSeverity.MEDIUM
        else:
            return InsightSeverity.LOW

    def _create_insight_from_anomaly(
        self,
        anomaly: dict,
        page_data: dict
    ) -> InsightCreate:
        """
        Create InsightCreate object from anomaly detection result

        Args:
            anomaly: Anomaly detection result dict
            page_data: Page data from database

        Returns:
            InsightCreate object or None
        """
        if not anomaly:
            return None

        direction = anomaly['direction']
        deviation_pct = anomaly['deviation_pct']

        # Determine category based on direction
        if direction == 'below':
            category = InsightCategory.RISK
            title = "Traffic Below Forecast"
            description = (
                f"Page traffic is {abs(deviation_pct):.1f}% below forecast. "
                f"Expected {anomaly['expected']:.0f} clicks, "
                f"actual {anomaly['actual']:.0f} clicks. "
                f"This indicates a significant decline beyond normal seasonal variation."
            )
        else:
            category = InsightCategory.OPPORTUNITY
            title = "Traffic Above Forecast"
            description = (
                f"Page traffic is {deviation_pct:.1f}% above forecast. "
                f"Expected {anomaly['expected']:.0f} clicks, "
                f"actual {anomaly['actual']:.0f} clicks. "
                f"This surge may indicate new ranking improvements or trending content."
            )

        # Calculate window for context
        anomaly_date = anomaly['date']
        if isinstance(anomaly_date, str):
            anomaly_date = datetime.fromisoformat(anomaly_date).date()
        elif isinstance(anomaly_date, datetime):
            anomaly_date = anomaly_date.date()

        window_start = (anomaly_date - timedelta(days=7)).isoformat()
        window_end = anomaly_date.isoformat()

        return InsightCreate(
            property=anomaly['property'],
            entity_type=EntityType.PAGE,
            entity_id=anomaly['page_path'],
            category=category,
            title=title,
            description=description,
            severity=anomaly['severity'],
            confidence=anomaly['confidence'],
            metrics=InsightMetrics(
                expected=anomaly['expected'],
                actual=anomaly['actual'],
                deviation=anomaly['deviation'],
                deviation_pct=anomaly['deviation_pct'],
                forecast_lower_bound=anomaly['lower_bound'],
                forecast_upper_bound=anomaly['upper_bound'],
                window_start=window_start,
                window_end=window_end,
            ),
            window_days=7,
            source="AnomalyDetector",
        )
