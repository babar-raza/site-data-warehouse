"""
TrendDetector - Detects gradual traffic trends using linear regression

This detector analyzes 90-day traffic patterns to identify:
- Gradual declines (slope < -0.1, R² > 0.7) → RISK insights
- Gradual growth (slope > 0.1, R² > 0.7) → OPPORTUNITY insights

Uses scipy.stats.linregress for robust trend analysis.
Skips pages with insufficient data (<30 days).

Example:
    detector = TrendDetector(repository, config)
    insights_created = detector.detect(property='sc-domain:example.com')
"""
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from scipy import stats
import numpy as np

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    EntityType,
    InsightCategory,
    InsightSeverity,
    InsightMetrics
)

logger = logging.getLogger(__name__)


class TrendDetector(BaseDetector):
    """
    Detects gradual traffic trends using linear regression

    Analyzes 90-day traffic data to find pages with statistically
    significant trends (R² > 0.7). Distinguishes between:
    - Decline: slope < -0.1 → RISK insight
    - Growth: slope > 0.1 → OPPORTUNITY insight

    Thresholds:
        - Lookback window: 90 days
        - Minimum data points: 30 days
        - Decline slope: < -0.1
        - Growth slope: > 0.1
        - R² threshold: > 0.7 (strong linear relationship)
    """

    # Thresholds
    LOOKBACK_DAYS = 90
    MIN_DATA_POINTS = 30
    DECLINE_SLOPE_THRESHOLD = -0.1
    GROWTH_SLOPE_THRESHOLD = 0.1
    R_SQUARED_THRESHOLD = 0.7

    def detect(self, property: str = None) -> int:
        """
        Run trend detection on traffic data

        Args:
            property: Optional property filter (e.g., "sc-domain:example.com")

        Returns:
            Number of insights created
        """
        logger.info("Starting TrendDetector")

        try:
            # Get 90-day traffic data
            traffic_data = self._get_traffic_data(property)

            if not traffic_data:
                logger.info(f"No traffic data found for property: {property}")
                return 0

            # Group data by page
            pages_data = self._group_by_page(traffic_data)

            logger.debug(f"Analyzing trends for {len(pages_data)} pages")

            insights_created = 0

            # Analyze each page for trends
            for (page_property, page_path), daily_traffic in pages_data.items():
                try:
                    # Skip pages with insufficient data
                    if len(daily_traffic) < self.MIN_DATA_POINTS:
                        logger.debug(f"Skipping {page_path}: only {len(daily_traffic)} data points")
                        continue

                    # Perform linear regression
                    trend_result = self._analyze_trend(daily_traffic)

                    if not trend_result:
                        continue

                    slope = trend_result['slope']
                    r_squared = trend_result['r_squared']

                    # Check if trend is statistically significant
                    if r_squared < self.R_SQUARED_THRESHOLD:
                        continue

                    # Detect decline
                    if slope < self.DECLINE_SLOPE_THRESHOLD:
                        insight = self._create_decline_insight(
                            page_property,
                            page_path,
                            trend_result
                        )
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(
                            f"Trend detected: {page_path}, decline, "
                            f"slope={slope:.4f}, r²={r_squared:.4f}"
                        )

                    # Detect growth
                    elif slope > self.GROWTH_SLOPE_THRESHOLD:
                        insight = self._create_growth_insight(
                            page_property,
                            page_path,
                            trend_result
                        )
                        self.repository.create(insight)
                        insights_created += 1
                        logger.info(
                            f"Trend detected: {page_path}, growth, "
                            f"slope={slope:.4f}, r²={r_squared:.4f}"
                        )

                except Exception as e:
                    logger.warning(f"Error analyzing trend for {page_path}: {e}")
                    continue

            logger.info(f"TrendDetector created {insights_created} insights")
            return insights_created

        except Exception as e:
            logger.error(f"Error in TrendDetector: {e}", exc_info=True)
            return 0

    def _get_traffic_data(self, property: str = None) -> List[Dict]:
        """
        Query 90-day traffic data from unified view

        Args:
            property: Optional property filter

        Returns:
            List of daily traffic records
        """
        conn = None
        try:
            conn = self._get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT
                        property,
                        page_path,
                        date,
                        COALESCE(gsc_clicks, 0) as clicks,
                        COALESCE(gsc_impressions, 0) as impressions
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                      AND date < CURRENT_DATE
                """
                params = [self.LOOKBACK_DAYS]

                if property:
                    query += " AND property = %s"
                    params.append(property)

                query += " ORDER BY property, page_path, date"

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]
        finally:
            if conn:
                conn.close()

    def _group_by_page(self, traffic_data: List[Dict]) -> Dict[tuple, List[Dict]]:
        """
        Group traffic data by (property, page_path)

        Args:
            traffic_data: List of daily traffic records

        Returns:
            Dict mapping (property, page_path) to list of daily data
        """
        pages = defaultdict(list)

        for record in traffic_data:
            key = (record['property'], record['page_path'])
            pages[key].append(record)

        return dict(pages)

    def _analyze_trend(self, daily_traffic: List[Dict]) -> Optional[Dict]:
        """
        Perform linear regression on traffic data

        Uses scipy.stats.linregress to find the trend line and R² value.

        Args:
            daily_traffic: List of daily traffic records for a single page

        Returns:
            Dict with slope, intercept, r_squared, p_value, days_analyzed
            or None if analysis fails
        """
        try:
            # Sort by date
            sorted_data = sorted(daily_traffic, key=lambda x: x['date'])

            # Create time series (days since first data point)
            dates = [rec['date'] for rec in sorted_data]
            first_date = dates[0]
            x = np.array([(date - first_date).days for date in dates])

            # Traffic values (clicks)
            y = np.array([rec['clicks'] for rec in sorted_data])

            # Perform linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            # Calculate R²
            r_squared = r_value ** 2

            return {
                'slope': float(slope),
                'intercept': float(intercept),
                'r_squared': float(r_squared),
                'p_value': float(p_value),
                'std_err': float(std_err),
                'days_analyzed': len(sorted_data),
                'first_date': first_date,
                'last_date': dates[-1],
                'initial_clicks': float(y[0]),
                'final_clicks': float(y[-1]),
                'mean_clicks': float(np.mean(y)),
                'change_percent': float(((y[-1] - y[0]) / y[0] * 100) if y[0] > 0 else 0)
            }

        except Exception as e:
            logger.warning(f"Error in linear regression: {e}")
            return None

    def _create_decline_insight(
        self,
        property: str,
        page_path: str,
        trend_result: Dict
    ) -> InsightCreate:
        """
        Create RISK insight for declining traffic trend

        Args:
            property: Property URL
            page_path: Page path
            trend_result: Trend analysis results

        Returns:
            InsightCreate object with RISK category
        """
        slope = trend_result['slope']
        r_squared = trend_result['r_squared']
        days_analyzed = trend_result['days_analyzed']
        change_percent = trend_result['change_percent']
        mean_clicks = trend_result['mean_clicks']

        # Determine severity based on slope magnitude
        if slope < -1.0:
            severity = InsightSeverity.HIGH
        elif slope < -0.5:
            severity = InsightSeverity.MEDIUM
        else:
            severity = InsightSeverity.LOW

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.RISK,
            title="Gradual Traffic Decline Detected",
            description=(
                f"Page '{page_path}' shows a statistically significant declining traffic trend. "
                f"Over the past {days_analyzed} days, traffic has declined by {abs(change_percent):.1f}% "
                f"(from {trend_result['initial_clicks']:.0f} to {trend_result['final_clicks']:.0f} clicks). "
                f"The trend shows a strong linear relationship (R²={r_squared:.2f}), "
                f"indicating a consistent downward pattern rather than random fluctuation. "
                f"Average daily clicks: {mean_clicks:.1f}. "
                f"Recommended actions: Investigate ranking changes, content freshness, "
                f"technical issues, or competitor activity that may be causing the decline."
            ),
            severity=severity,
            confidence=min(0.95, r_squared),  # Higher R² = higher confidence
            metrics=InsightMetrics(
                **{
                    'trend_slope': slope,
                    'r_squared': r_squared,
                    'days_analyzed': days_analyzed,
                    'change_percent': change_percent,
                    'mean_clicks': mean_clicks,
                    'initial_clicks': trend_result['initial_clicks'],
                    'final_clicks': trend_result['final_clicks'],
                    'p_value': trend_result['p_value'],
                    'trend_type': 'decline'
                }
            ),
            window_days=days_analyzed,
            source="TrendDetector"
        )

    def _create_growth_insight(
        self,
        property: str,
        page_path: str,
        trend_result: Dict
    ) -> InsightCreate:
        """
        Create OPPORTUNITY insight for growing traffic trend

        Args:
            property: Property URL
            page_path: Page path
            trend_result: Trend analysis results

        Returns:
            InsightCreate object with OPPORTUNITY category
        """
        slope = trend_result['slope']
        r_squared = trend_result['r_squared']
        days_analyzed = trend_result['days_analyzed']
        change_percent = trend_result['change_percent']
        mean_clicks = trend_result['mean_clicks']

        # Determine severity based on slope magnitude
        if slope > 1.0:
            severity = InsightSeverity.HIGH
        elif slope > 0.5:
            severity = InsightSeverity.MEDIUM
        else:
            severity = InsightSeverity.LOW

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=page_path,
            category=InsightCategory.OPPORTUNITY,
            title="Gradual Traffic Growth Detected",
            description=(
                f"Page '{page_path}' shows a statistically significant growing traffic trend. "
                f"Over the past {days_analyzed} days, traffic has grown by {change_percent:.1f}% "
                f"(from {trend_result['initial_clicks']:.0f} to {trend_result['final_clicks']:.0f} clicks). "
                f"The trend shows a strong linear relationship (R²={r_squared:.2f}), "
                f"indicating consistent upward momentum rather than temporary spikes. "
                f"Average daily clicks: {mean_clicks:.1f}. "
                f"Recommended actions: Double down on what's working - analyze successful keywords, "
                f"content structure, and backlinks to replicate this growth on other pages."
            ),
            severity=severity,
            confidence=min(0.95, r_squared),
            metrics=InsightMetrics(
                **{
                    'trend_slope': slope,
                    'r_squared': r_squared,
                    'days_analyzed': days_analyzed,
                    'change_percent': change_percent,
                    'mean_clicks': mean_clicks,
                    'initial_clicks': trend_result['initial_clicks'],
                    'final_clicks': trend_result['final_clicks'],
                    'p_value': trend_result['p_value'],
                    'trend_type': 'growth'
                }
            ),
            window_days=days_analyzed,
            source="TrendDetector"
        )
