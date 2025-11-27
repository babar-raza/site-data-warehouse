"""
Trends Analyzer - Analyzes Google Trends data for insight generation

Uses stored trends data to:
1. Detect seasonal patterns in keywords
2. Correlate traffic changes with search interest changes
3. Identify trending opportunities
4. Provide context for diagnosis

Example:
    analyzer = TrendsAnalyzer()
    analysis = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python tutorial')
    if analysis['is_trending_up']:
        print("Keyword interest is increasing!")
"""
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class TrendsAnalyzer:
    """
    Analyzes Google Trends data for insight generation

    Provides methods to analyze trend data stored by TrendsAccumulator
    for use in DiagnosisDetector and other insight generators.

    Example:
        analyzer = TrendsAnalyzer()

        # Check if keyword is trending
        if analyzer.is_trending_up('sc-domain:example.com', 'python'):
            print("Python is trending up!")

        # Get full analysis
        analysis = analyzer.analyze_keyword_trends('sc-domain:example.com', 'python')
    """

    # Trend detection thresholds
    TREND_UP_THRESHOLD = 1.15  # 15% increase
    TREND_DOWN_THRESHOLD = 0.85  # 15% decrease
    SIGNIFICANT_CHANGE_THRESHOLD = 0.25  # 25% change

    def __init__(self, db_dsn: str = None):
        """
        Initialize Trends Analyzer

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        logger.info("TrendsAnalyzer initialized")

    def analyze_keyword_trends(self, property: str, keyword: str, days: int = 90) -> Dict:
        """
        Analyze trends for a specific keyword

        Args:
            property: GSC property
            keyword: Keyword to analyze
            days: Days of history to analyze

        Returns:
            Dict with trend analysis results
        """
        # Get trend data from database
        trend_data = self._get_trend_data(property, keyword, days)

        if not trend_data:
            return {
                'keyword': keyword,
                'property': property,
                'has_data': False,
                'message': 'No trend data available'
            }

        # Calculate metrics
        scores = [r['interest_score'] for r in trend_data if r.get('interest_score') is not None]

        if len(scores) < 7:
            return {
                'keyword': keyword,
                'property': property,
                'has_data': True,
                'insufficient_data': True,
                'data_points': len(scores)
            }

        # Split into recent vs historical
        recent_scores = scores[:len(scores)//3]
        historical_scores = scores[len(scores)//3:]

        recent_avg = statistics.mean(recent_scores) if recent_scores else 0
        historical_avg = statistics.mean(historical_scores) if historical_scores else 0

        # Detect trend direction
        change_ratio = recent_avg / historical_avg if historical_avg > 0 else 1.0

        if change_ratio >= self.TREND_UP_THRESHOLD:
            trend_direction = 'up'
        elif change_ratio <= self.TREND_DOWN_THRESHOLD:
            trend_direction = 'down'
        else:
            trend_direction = 'stable'

        # Detect seasonality (simple approach: compare to same period last year if available)
        seasonality = self._detect_seasonality(scores)

        return {
            'keyword': keyword,
            'property': property,
            'has_data': True,
            'data_points': len(scores),
            'recent_avg': round(recent_avg, 2),
            'historical_avg': round(historical_avg, 2),
            'change_ratio': round(change_ratio, 3),
            'trend_direction': trend_direction,
            'is_trending_up': trend_direction == 'up',
            'is_trending_down': trend_direction == 'down',
            'is_significant_change': abs(change_ratio - 1.0) >= self.SIGNIFICANT_CHANGE_THRESHOLD,
            'seasonality': seasonality,
            'current_score': scores[0] if scores else None,
            'max_score': max(scores),
            'min_score': min(scores),
            'volatility': round(statistics.stdev(scores), 2) if len(scores) > 1 else 0
        }

    def detect_seasonal_patterns(self, property: str, keyword: str) -> Dict:
        """
        Detect seasonal patterns in keyword interest

        Args:
            property: GSC property
            keyword: Keyword to analyze

        Returns:
            Dict with seasonality analysis
        """
        # Get longer historical data
        trend_data = self._get_trend_data(property, keyword, days=365)

        if len(trend_data) < 90:
            return {'has_seasonality': False, 'reason': 'insufficient_data'}

        # Group by month and analyze patterns
        monthly_scores = self._group_by_month(trend_data)

        if len(monthly_scores) < 6:
            return {'has_seasonality': False, 'reason': 'insufficient_months'}

        # Find peak and trough months
        avg_scores = {month: statistics.mean(scores) for month, scores in monthly_scores.items()}
        peak_month = max(avg_scores, key=avg_scores.get)
        trough_month = min(avg_scores, key=avg_scores.get)

        # Calculate seasonality strength
        peak_score = avg_scores[peak_month]
        trough_score = avg_scores[trough_month]
        seasonality_ratio = peak_score / trough_score if trough_score > 0 else 1.0

        return {
            'has_seasonality': seasonality_ratio > 1.5,
            'peak_month': peak_month,
            'trough_month': trough_month,
            'peak_score': round(peak_score, 2),
            'trough_score': round(trough_score, 2),
            'seasonality_ratio': round(seasonality_ratio, 3),
            'monthly_averages': {k: round(v, 2) for k, v in avg_scores.items()}
        }

    def correlate_with_traffic(self, property: str, keyword: str, days: int = 30) -> Dict:
        """
        Correlate trends with GSC traffic for a keyword

        Args:
            property: GSC property
            keyword: Keyword to analyze
            days: Days to analyze

        Returns:
            Dict with correlation analysis
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get trends data
            cursor.execute("""
                SELECT date, interest_score
                FROM trends.keyword_interest
                WHERE property = %s AND keyword = %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date
            """, (property, keyword, days))
            trends = {row['date']: row['interest_score'] for row in cursor.fetchall()}

            # Get GSC data
            cursor.execute("""
                SELECT date, SUM(clicks) as clicks, SUM(impressions) as impressions
                FROM gsc.search_performance
                WHERE property = %s AND query = %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY date
                ORDER BY date
            """, (property, keyword, days))
            gsc_data = {row['date']: row for row in cursor.fetchall()}

            if not trends or not gsc_data:
                return {'has_correlation': False, 'reason': 'insufficient_data'}

            # Calculate simple correlation
            common_dates = set(trends.keys()) & set(gsc_data.keys())

            if len(common_dates) < 7:
                return {'has_correlation': False, 'reason': 'insufficient_overlap'}

            trend_values = [trends[d] for d in sorted(common_dates)]
            click_values = [gsc_data[d]['clicks'] for d in sorted(common_dates)]

            # Simple correlation calculation
            correlation = self._calculate_correlation(trend_values, click_values)

            return {
                'has_correlation': True,
                'correlation': round(correlation, 3),
                'correlation_strength': self._interpret_correlation(correlation),
                'common_data_points': len(common_dates),
                'interpretation': self._interpret_trends_traffic_correlation(correlation)
            }

        except Exception as e:
            logger.error(f"Error correlating with traffic: {e}")
            return {'has_correlation': False, 'error': str(e)}

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def is_trending_up(self, property: str, keyword: str) -> bool:
        """
        Quick check if keyword is trending upward

        Args:
            property: GSC property
            keyword: Keyword to check

        Returns:
            True if trending up
        """
        analysis = self.analyze_keyword_trends(property, keyword, days=30)
        return analysis.get('is_trending_up', False)

    def get_trending_keywords(self, property: str, limit: int = 20) -> List[Dict]:
        """
        Get keywords that are currently trending up

        Args:
            property: GSC property
            limit: Maximum keywords to return

        Returns:
            List of trending keywords with scores
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get keywords with recent data
            cursor.execute("""
                WITH recent AS (
                    SELECT keyword, AVG(interest_score) as recent_avg
                    FROM trends.keyword_interest
                    WHERE property = %s
                      AND date >= CURRENT_DATE - INTERVAL '14 days'
                    GROUP BY keyword
                ),
                historical AS (
                    SELECT keyword, AVG(interest_score) as historical_avg
                    FROM trends.keyword_interest
                    WHERE property = %s
                      AND date >= CURRENT_DATE - INTERVAL '60 days'
                      AND date < CURRENT_DATE - INTERVAL '14 days'
                    GROUP BY keyword
                )
                SELECT
                    r.keyword,
                    r.recent_avg,
                    h.historical_avg,
                    r.recent_avg / NULLIF(h.historical_avg, 0) as change_ratio
                FROM recent r
                JOIN historical h ON r.keyword = h.keyword
                WHERE h.historical_avg > 10
                  AND r.recent_avg / NULLIF(h.historical_avg, 0) >= %s
                ORDER BY change_ratio DESC
                LIMIT %s
            """, (property, property, self.TREND_UP_THRESHOLD, limit))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting trending keywords: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_trend_data(self, property: str, keyword: str, days: int) -> List[Dict]:
        """Get trend data from database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT date, interest_score
                FROM trends.keyword_interest
                WHERE property = %s AND keyword = %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date DESC
            """, (property, keyword, days))

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting trend data: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _detect_seasonality(self, scores: List[int]) -> str:
        """Simple seasonality detection"""
        if len(scores) < 30:
            return 'unknown'

        # Compare first and second halves
        mid = len(scores) // 2
        first_half_avg = statistics.mean(scores[:mid])
        second_half_avg = statistics.mean(scores[mid:])

        ratio = first_half_avg / second_half_avg if second_half_avg > 0 else 1.0

        if ratio > 1.3:
            return 'declining'
        elif ratio < 0.7:
            return 'rising'
        else:
            return 'stable'

    def _group_by_month(self, trend_data: List[Dict]) -> Dict[int, List[int]]:
        """Group trend data by month"""
        monthly = {}
        for row in trend_data:
            month = row['date'].month
            if month not in monthly:
                monthly[month] = []
            if row.get('interest_score') is not None:
                monthly[month].append(row['interest_score'])
        return monthly

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))

        sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
        sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)

        denominator = (sum_sq_x * sum_sq_y) ** 0.5

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _interpret_correlation(self, correlation: float) -> str:
        """Interpret correlation strength"""
        abs_corr = abs(correlation)
        if abs_corr >= 0.7:
            return 'strong'
        elif abs_corr >= 0.4:
            return 'moderate'
        elif abs_corr >= 0.2:
            return 'weak'
        else:
            return 'negligible'

    def _interpret_trends_traffic_correlation(self, correlation: float) -> str:
        """Interpret what the correlation means"""
        if correlation >= 0.5:
            return "Traffic strongly follows search interest trends"
        elif correlation >= 0.2:
            return "Traffic shows some alignment with search interest"
        elif correlation >= -0.2:
            return "Traffic appears independent of search interest trends"
        else:
            return "Traffic moves inversely to search interest (unusual)"
