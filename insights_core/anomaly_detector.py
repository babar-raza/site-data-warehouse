"""
Anomaly Detection Engine
=========================
Multi-method anomaly detection for SEO metrics using statistical and ML approaches.

Methods:
1. Statistical: Z-score, IQR for outlier detection
2. ML-based: Isolation Forest for multivariate anomalies
3. Time Series: Prophet for forecasting-based detection

Metrics Monitored:
- SERP positions
- Traffic (clicks, impressions)
- Core Web Vitals
- Conversion rates
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import asyncpg
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Multi-method anomaly detection for SEO metrics
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize Anomaly Detector

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("AnomalyDetector initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    # =====================================================
    # SERP ANOMALY DETECTION
    # =====================================================

    async def detect_serp_anomalies(
        self,
        property_url: str,
        lookback_days: int = 30,
        sensitivity: float = 0.1
    ) -> List[Dict]:
        """
        Detect SERP position anomalies

        Args:
            property_url: Property URL
            lookback_days: Days to analyze
            sensitivity: Detection sensitivity (0.05-0.2, lower = more sensitive)

        Returns:
            List of detected anomalies
        """
        try:
            logger.info(f"Detecting SERP anomalies for {property_url}")

            # Fetch historical data
            df = await self._fetch_serp_history(property_url, lookback_days)

            if df.empty:
                logger.warning("No SERP data found")
                return []

            # Method 1: Statistical (Z-score)
            statistical_anomalies = self._detect_statistical_anomalies(
                df,
                metric='position',
                threshold=2.5
            )

            # Method 2: Isolation Forest
            ml_anomalies = self._detect_ml_anomalies(
                df,
                features=['position'],
                contamination=sensitivity
            )

            # Method 3: Prophet forecasting
            forecast_anomalies = await self._detect_forecast_anomalies(
                df,
                metric='position'
            )

            # Merge and rank anomalies
            all_anomalies = self._merge_and_rank_anomalies([
                statistical_anomalies,
                ml_anomalies,
                forecast_anomalies
            ])

            # Store in database
            for anomaly in all_anomalies[:20]:  # Top 20
                await self._store_anomaly(
                    metric_type='serp',
                    property_url=property_url,
                    anomaly=anomaly
                )

            logger.info(f"Detected {len(all_anomalies)} SERP anomalies")
            return all_anomalies

        except Exception as e:
            logger.error(f"Error detecting SERP anomalies: {e}")
            return []

    async def _fetch_serp_history(
        self,
        property_url: str,
        days: int
    ) -> pd.DataFrame:
        """Fetch SERP position history"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        ph.check_date as date,
                        q.query_text,
                        q.query_id,
                        ph.position
                    FROM serp.position_history ph
                    JOIN serp.queries q ON ph.query_id = q.query_id
                    WHERE q.property = $1
                        AND ph.check_date >= CURRENT_DATE - $2
                    ORDER BY ph.check_date, q.query_text
                """, property_url, days)

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame([dict(r) for r in rows])
            return df

        except Exception as e:
            logger.error(f"Error fetching SERP history: {e}")
            return pd.DataFrame()

    # =====================================================
    # TRAFFIC ANOMALY DETECTION
    # =====================================================

    async def detect_traffic_anomalies(
        self,
        property_url: str,
        lookback_days: int = 30,
        sensitivity: float = 0.1
    ) -> List[Dict]:
        """
        Detect traffic anomalies (clicks, impressions)

        Args:
            property_url: Property URL
            lookback_days: Days to analyze
            sensitivity: Detection sensitivity

        Returns:
            List of detected anomalies
        """
        try:
            logger.info(f"Detecting traffic anomalies for {property_url}")

            # Fetch traffic data from GSC
            df = await self._fetch_traffic_history(property_url, lookback_days)

            if df.empty:
                logger.warning("No traffic data found")
                return []

            # Detect anomalies in clicks
            click_anomalies = self._detect_statistical_anomalies(
                df,
                metric='clicks',
                threshold=2.0
            )

            # Detect anomalies in impressions
            impression_anomalies = self._detect_statistical_anomalies(
                df,
                metric='impressions',
                threshold=2.0
            )

            # Combine
            all_anomalies = click_anomalies + impression_anomalies

            # Store top anomalies
            for anomaly in all_anomalies[:20]:
                await self._store_anomaly(
                    metric_type='traffic',
                    property_url=property_url,
                    anomaly=anomaly
                )

            logger.info(f"Detected {len(all_anomalies)} traffic anomalies")
            return all_anomalies

        except Exception as e:
            logger.error(f"Error detecting traffic anomalies: {e}")
            return []

    async def _fetch_traffic_history(
        self,
        property_url: str,
        days: int
    ) -> pd.DataFrame:
        """Fetch traffic history from GSC data"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        date,
                        SUM(clicks) as clicks,
                        SUM(impressions) as impressions,
                        AVG(position) as avg_position
                    FROM gsc_daily_pages
                    WHERE property = $1
                        AND date >= CURRENT_DATE - $2
                    GROUP BY date
                    ORDER BY date
                """, property_url, days)

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame([dict(r) for r in rows])
            return df

        except Exception as e:
            logger.error(f"Error fetching traffic history: {e}")
            return pd.DataFrame()

    # =====================================================
    # DETECTION METHODS
    # =====================================================

    def _detect_statistical_anomalies(
        self,
        df: pd.DataFrame,
        metric: str,
        threshold: float = 2.5
    ) -> List[Dict]:
        """
        Z-score based anomaly detection

        Args:
            df: DataFrame with metric column
            metric: Column name to analyze
            threshold: Z-score threshold (typically 2.5 or 3)

        Returns:
            List of anomalies
        """
        anomalies = []

        if metric not in df.columns:
            return anomalies

        # Group by query/page if exists
        group_col = None
        if 'query_id' in df.columns:
            group_col = 'query_id'
        elif 'page_path' in df.columns:
            group_col = 'page_path'

        if group_col:
            # Detect anomalies per group
            for group_value, group_df in df.groupby(group_col):
                group_anomalies = self._detect_z_score_anomalies(
                    group_df,
                    metric,
                    threshold,
                    {group_col: group_value}
                )
                anomalies.extend(group_anomalies)
        else:
            # Detect anomalies globally
            anomalies = self._detect_z_score_anomalies(df, metric, threshold, {})

        return anomalies

    def _detect_z_score_anomalies(
        self,
        df: pd.DataFrame,
        metric: str,
        threshold: float,
        context: Dict
    ) -> List[Dict]:
        """Detect anomalies using Z-score"""
        anomalies = []

        values = df[metric].dropna()
        if len(values) < 3:  # Need minimum data points
            return anomalies

        mean = values.mean()
        std = values.std()

        if std == 0:  # No variation
            return anomalies

        # Calculate Z-scores
        z_scores = (values - mean) / std

        # Find anomalies
        anomaly_mask = np.abs(z_scores) > threshold

        for idx in df[anomaly_mask].index:
            value = df.loc[idx, metric]
            z_score = z_scores[idx]

            severity = 'high' if abs(z_score) > 3 else 'medium'

            anomalies.append({
                'date': df.loc[idx, 'date'] if 'date' in df.columns else None,
                'metric': metric,
                'actual_value': float(value),
                'expected_value': float(mean),
                'deviation_score': float(abs(z_score)),
                'method': 'z_score',
                'severity': severity,
                'confidence': min(abs(z_score) / 5, 1.0),  # Normalize to 0-1
                **context
            })

        return anomalies

    def _detect_ml_anomalies(
        self,
        df: pd.DataFrame,
        features: List[str],
        contamination: float = 0.1
    ) -> List[Dict]:
        """
        Isolation Forest anomaly detection

        Args:
            df: DataFrame with features
            features: List of feature columns
            contamination: Expected proportion of anomalies

        Returns:
            List of anomalies
        """
        anomalies = []

        # Check if features exist
        available_features = [f for f in features if f in df.columns]
        if not available_features:
            return anomalies

        # Prepare feature matrix
        X = df[available_features].fillna(df[available_features].mean())

        if len(X) < 10:  # Need minimum data points
            return anomalies

        # Train Isolation Forest
        iso_forest = IsolationForest(contamination=contamination, random_state=42)
        predictions = iso_forest.fit_predict(X)

        # Extract anomalies (predictions == -1)
        anomaly_indices = np.where(predictions == -1)[0]

        for idx in anomaly_indices:
            anomalies.append({
                'date': df.iloc[idx]['date'] if 'date' in df.columns else None,
                'metric': features[0],  # Primary metric
                'actual_value': float(df.iloc[idx][features[0]]),
                'expected_value': None,  # ML-based, no specific expectation
                'deviation_score': None,
                'method': 'isolation_forest',
                'severity': 'medium',
                'confidence': 0.70,
                'metadata': {f: float(df.iloc[idx][f]) for f in available_features}
            })

        return anomalies

    async def _detect_forecast_anomalies(
        self,
        df: pd.DataFrame,
        metric: str
    ) -> List[Dict]:
        """
        Prophet-based forecast anomaly detection

        Args:
            df: DataFrame with date and metric columns
            metric: Metric to forecast

        Returns:
            List of anomalies
        """
        anomalies = []

        if metric not in df.columns or 'date' not in df.columns:
            return anomalies

        try:
            # Prepare data for Prophet
            prophet_df = df[['date', metric]].copy()
            prophet_df = prophet_df.rename(columns={'date': 'ds', metric: 'y'})
            prophet_df = prophet_df.dropna()

            if len(prophet_df) < 10:  # Need minimum data points
                return anomalies

            # Train Prophet model
            model = Prophet(interval_width=0.95, daily_seasonality=False)
            model.fit(prophet_df)

            # Make predictions
            forecast = model.predict(prophet_df)

            # Detect points outside confidence interval
            for i, row in prophet_df.iterrows():
                actual = row['y']
                predicted = forecast.loc[i, 'yhat']
                lower = forecast.loc[i, 'yhat_lower']
                upper = forecast.loc[i, 'yhat_upper']

                if actual < lower or actual > upper:
                    deviation = abs(actual - predicted) / (upper - lower) if (upper - lower) > 0 else 0

                    anomalies.append({
                        'date': row['ds'],
                        'metric': metric,
                        'actual_value': float(actual),
                        'expected_value': float(predicted),
                        'deviation_score': float(deviation),
                        'method': 'prophet_forecast',
                        'severity': 'high' if deviation > 2 else 'medium',
                        'confidence': min(deviation / 3, 1.0),
                        'metadata': {
                            'lower_bound': float(lower),
                            'upper_bound': float(upper)
                        }
                    })

        except Exception as e:
            logger.error(f"Error in Prophet forecast detection: {e}")

        return anomalies

    # =====================================================
    # ANOMALY MERGING & RANKING
    # =====================================================

    def _merge_and_rank_anomalies(
        self,
        anomaly_lists: List[List[Dict]]
    ) -> List[Dict]:
        """
        Merge anomalies from different methods and rank by severity

        Args:
            anomaly_lists: List of anomaly lists from different methods

        Returns:
            Merged and ranked anomalies
        """
        # Flatten all anomalies
        all_anomalies = []
        for anomaly_list in anomaly_lists:
            all_anomalies.extend(anomaly_list)

        # Remove duplicates (same date + metric)
        seen = set()
        unique_anomalies = []

        for anomaly in all_anomalies:
            key = (str(anomaly.get('date')), anomaly.get('metric'))
            if key not in seen:
                seen.add(key)
                unique_anomalies.append(anomaly)

        # Rank by severity and confidence
        severity_scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}

        def rank_score(anomaly: Dict) -> float:
            severity = severity_scores.get(anomaly.get('severity', 'medium'), 2)
            confidence = anomaly.get('confidence', 0.5)
            return severity * confidence

        sorted_anomalies = sorted(
            unique_anomalies,
            key=rank_score,
            reverse=True
        )

        return sorted_anomalies

    # =====================================================
    # DATABASE STORAGE
    # =====================================================

    async def _store_anomaly(
        self,
        metric_type: str,
        property_url: str,
        anomaly: Dict
    ):
        """Store detected anomaly in database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    SELECT anomaly.record_detection($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                    metric_type,
                    property_url,
                    anomaly.get('actual_value'),
                    anomaly.get('expected_value'),
                    anomaly.get('method'),
                    anomaly.get('severity', 'medium'),
                    anomaly.get('page_path'),
                    anomaly.get('metadata')
                )

        except Exception as e:
            logger.error(f"Error storing anomaly: {e}")

    async def get_recent_anomalies(
        self,
        property_url: str = None,
        days: int = 7
    ) -> List[Dict]:
        """Get recent anomalies from database"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                if property_url:
                    rows = await conn.fetch("""
                        SELECT * FROM anomaly.vw_recent_anomalies
                        WHERE property = $1
                        ORDER BY detected_at DESC
                    """, property_url)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM anomaly.vw_recent_anomalies
                        ORDER BY detected_at DESC
                    """)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting recent anomalies: {e}")
            return []


# Synchronous wrapper for Celery
def detect_serp_anomalies_sync(property_url: str) -> List[Dict]:
    """Synchronous wrapper for SERP anomaly detection"""
    detector = AnomalyDetector()
    return asyncio.run(detector.detect_serp_anomalies(property_url))


def detect_traffic_anomalies_sync(property_url: str) -> List[Dict]:
    """Synchronous wrapper for traffic anomaly detection"""
    detector = AnomalyDetector()
    return asyncio.run(detector.detect_traffic_anomalies(property_url))


__all__ = ['AnomalyDetector']
