"""
Cannibalization Detector - Detects keyword cannibalization issues

Goes beyond ContentQualityDetector's basic cannibalization by:
1. Analyzing ranking overlap across all keywords
2. Calculating cannibalization severity scores
3. Identifying the "winner" and "loser" pages
4. Recommending consolidation strategies

Example:
    detector = CannibalizationDetector(repository, config)
    insights_created = detector.detect('sc-domain:example.com')
"""
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightMetrics,
    EntityType,
    InsightCategory,
    InsightSeverity
)

logger = logging.getLogger(__name__)


class CannibalizationDetector(BaseDetector):
    """
    Dedicated detector for keyword cannibalization

    Cannibalization occurs when multiple pages on a site compete
    for the same keywords, potentially diluting ranking potential.

    This detector:
    1. Finds pages with significant keyword overlap
    2. Calculates a cannibalization severity score
    3. Identifies which page is "winning" and which is "losing"
    4. Provides actionable recommendations

    Example:
        >>> detector = CannibalizationDetector(repository, config)
        >>> count = detector.detect('sc-domain:example.com')
        >>> print(f"Found {count} cannibalization issues")
    """

    # Thresholds
    CANNIBALIZATION_THRESHOLD = 0.5  # 50% keyword overlap triggers detection
    MIN_SHARED_KEYWORDS = 3  # Minimum shared keywords to consider
    MIN_KEYWORD_IMPRESSIONS = 100  # Minimum impressions to consider a keyword
    MIN_PAGE_CLICKS = 10  # Minimum clicks for a page to be analyzed

    # Severity thresholds
    HIGH_SEVERITY_THRESHOLD = 0.8  # 80% overlap = high severity
    MEDIUM_SEVERITY_THRESHOLD = 0.6  # 60% overlap = medium severity

    def __init__(self, repository, config):
        """
        Initialize Cannibalization Detector

        Args:
            repository: InsightRepository for storing insights
            config: InsightsConfig with settings
        """
        super().__init__(repository, config)
        logger.info("CannibalizationDetector initialized")

    def detect(self, property: str = None) -> int:
        """
        Detect keyword cannibalization issues

        Args:
            property: Property to analyze (required)

        Returns:
            Number of insights created
        """
        if not property:
            logger.warning("Property required for cannibalization detection")
            return 0

        insights_created = 0
        logger.info(f"Starting cannibalization detection for {property}")

        try:
            # Get keyword overlaps between pages
            overlaps = self._find_keyword_overlaps(property)
            logger.info(f"Found {len(overlaps)} potential cannibalization pairs")

            # Process each overlap
            processed_pairs: Set[Tuple[str, str]] = set()

            for overlap in overlaps:
                # Avoid processing same pair twice
                pair_key = tuple(sorted([overlap['page_a'], overlap['page_b']]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                # Check if score exceeds threshold
                if overlap['overlap_score'] >= self.CANNIBALIZATION_THRESHOLD:
                    # Identify winner and loser
                    winner_loser = self._identify_winner_loser(
                        property,
                        overlap['page_a'],
                        overlap['page_b'],
                        overlap['shared_keywords']
                    )

                    if winner_loser:
                        overlap.update(winner_loser)

                        # Create insight
                        insight = self._create_cannibalization_insight(overlap, property)

                        try:
                            self.repository.create(insight)
                            insights_created += 1
                            logger.debug(f"Created insight for pages: {overlap['page_a']} vs {overlap['page_b']}")
                        except Exception as e:
                            # May already exist
                            logger.debug(f"Insight creation skipped: {e}")

            logger.info(f"Cannibalization detection complete: {insights_created} insights created")
            return insights_created

        except Exception as e:
            logger.error(f"Error in cannibalization detection: {e}", exc_info=True)
            return insights_created

    def _find_keyword_overlaps(self, property: str) -> List[Dict]:
        """
        Find pages with overlapping keywords

        Queries GSC data to find pages that rank for the same keywords.

        Returns:
            List of overlap dicts with page pairs and shared keywords
        """
        conn = None
        cursor = None
        overlaps = []

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get pages with their keywords
            cursor.execute("""
                WITH page_keywords AS (
                    SELECT
                        page,
                        ARRAY_AGG(DISTINCT query) as keywords,
                        SUM(clicks) as total_clicks,
                        SUM(impressions) as total_impressions
                    FROM gsc.search_performance
                    WHERE property = %s
                      AND date >= CURRENT_DATE - INTERVAL '30 days'
                      AND impressions >= %s
                    GROUP BY page
                    HAVING SUM(clicks) >= %s
                ),
                page_pairs AS (
                    SELECT
                        a.page as page_a,
                        b.page as page_b,
                        a.keywords as keywords_a,
                        b.keywords as keywords_b,
                        a.total_clicks as clicks_a,
                        b.total_clicks as clicks_b,
                        a.total_impressions as impressions_a,
                        b.total_impressions as impressions_b
                    FROM page_keywords a
                    CROSS JOIN page_keywords b
                    WHERE a.page < b.page
                )
                SELECT
                    page_a,
                    page_b,
                    keywords_a,
                    keywords_b,
                    clicks_a,
                    clicks_b,
                    impressions_a,
                    impressions_b,
                    (SELECT ARRAY_AGG(x) FROM UNNEST(keywords_a) x WHERE x = ANY(keywords_b)) as shared_keywords
                FROM page_pairs
                WHERE (SELECT COUNT(*) FROM UNNEST(keywords_a) x WHERE x = ANY(keywords_b)) >= %s
            """, (property, self.MIN_KEYWORD_IMPRESSIONS, self.MIN_PAGE_CLICKS, self.MIN_SHARED_KEYWORDS))

            rows = cursor.fetchall()

            for row in rows:
                shared = row['shared_keywords'] or []
                keywords_a = row['keywords_a'] or []
                keywords_b = row['keywords_b'] or []

                if not shared or not keywords_a or not keywords_b:
                    continue

                # Calculate overlap score (Jaccard-like)
                union_size = len(set(keywords_a) | set(keywords_b))
                overlap_score = len(shared) / union_size if union_size > 0 else 0

                overlaps.append({
                    'page_a': row['page_a'],
                    'page_b': row['page_b'],
                    'keywords_a': keywords_a,
                    'keywords_b': keywords_b,
                    'shared_keywords': shared,
                    'shared_count': len(shared),
                    'overlap_score': overlap_score,
                    'clicks_a': row['clicks_a'],
                    'clicks_b': row['clicks_b'],
                    'impressions_a': row['impressions_a'],
                    'impressions_b': row['impressions_b']
                })

            return overlaps

        except Exception as e:
            logger.error(f"Error finding keyword overlaps: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _calculate_overlap_score(self, keywords_a: List[str], keywords_b: List[str]) -> float:
        """
        Calculate keyword overlap score (Jaccard similarity)

        Args:
            keywords_a: Keywords for page A
            keywords_b: Keywords for page B

        Returns:
            Overlap score between 0 and 1
        """
        set_a = set(keywords_a)
        set_b = set(keywords_b)

        intersection = set_a & set_b
        union = set_a | set_b

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def _identify_winner_loser(self, property: str, page_a: str, page_b: str,
                                shared_keywords: List[str]) -> Optional[Dict]:
        """
        Identify which page is "winning" and which is "losing"

        Compares performance metrics to determine:
        - Winner: Page with better overall performance on shared keywords
        - Loser: Page that should potentially be consolidated or redirected

        Returns:
            Dict with winner/loser info, or None if can't determine
        """
        conn = None
        cursor = None

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get performance for shared keywords
            cursor.execute("""
                SELECT
                    page,
                    SUM(clicks) as total_clicks,
                    SUM(impressions) as total_impressions,
                    AVG(position) as avg_position,
                    SUM(clicks)::float / NULLIF(SUM(impressions), 0) as ctr
                FROM gsc.search_performance
                WHERE property = %s
                  AND page IN (%s, %s)
                  AND query = ANY(%s)
                  AND date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY page
            """, (property, page_a, page_b, shared_keywords))

            results = {row['page']: dict(row) for row in cursor.fetchall()}

            if page_a not in results or page_b not in results:
                return None

            stats_a = results[page_a]
            stats_b = results[page_b]

            # Calculate winner score (higher is better)
            # Factors: clicks (40%), avg_position (30% - lower is better), CTR (30%)
            def winner_score(stats: Dict) -> float:
                clicks_score = min(stats['total_clicks'] / 100, 1.0) * 40
                position_score = max(0, (10 - stats['avg_position']) / 10) * 30
                ctr_score = min((stats['ctr'] or 0) * 10, 1.0) * 30
                return clicks_score + position_score + ctr_score

            score_a = winner_score(stats_a)
            score_b = winner_score(stats_b)

            if abs(score_a - score_b) < 5:  # Too close to call
                return {
                    'winner': None,
                    'loser': None,
                    'recommendation': 'differentiate',
                    'stats_a': stats_a,
                    'stats_b': stats_b
                }

            if score_a > score_b:
                winner, loser = page_a, page_b
                winner_stats, loser_stats = stats_a, stats_b
            else:
                winner, loser = page_b, page_a
                winner_stats, loser_stats = stats_b, stats_a

            return {
                'winner': winner,
                'loser': loser,
                'winner_stats': winner_stats,
                'loser_stats': loser_stats,
                'recommendation': self._get_recommendation(winner_stats, loser_stats)
            }

        except Exception as e:
            logger.error(f"Error identifying winner/loser: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_recommendation(self, winner_stats: Dict, loser_stats: Dict) -> str:
        """
        Generate recommendation based on stats comparison
        """
        loser_clicks = loser_stats.get('total_clicks', 0) or 0
        winner_clicks = winner_stats.get('total_clicks', 0) or 1

        click_ratio = loser_clicks / winner_clicks

        if click_ratio < 0.1:
            return 'redirect'  # Loser has < 10% of winner's clicks
        elif click_ratio < 0.3:
            return 'consolidate'  # Loser has 10-30% of winner's clicks
        else:
            return 'differentiate'  # Both pages have significant traffic

    def _create_cannibalization_insight(self, overlap: Dict, property: str) -> InsightCreate:
        """
        Create detailed cannibalization insight

        Args:
            overlap: Overlap data with winner/loser info
            property: Property identifier

        Returns:
            InsightCreate object
        """
        winner = overlap.get('winner')
        loser = overlap.get('loser')
        recommendation = overlap.get('recommendation', 'review')

        # Determine severity based on overlap score
        overlap_score = overlap.get('overlap_score', 0)
        if overlap_score >= self.HIGH_SEVERITY_THRESHOLD:
            severity = InsightSeverity.HIGH
        elif overlap_score >= self.MEDIUM_SEVERITY_THRESHOLD:
            severity = InsightSeverity.MEDIUM
        else:
            severity = InsightSeverity.LOW

        # Build title
        if winner and loser:
            title = f"Keyword cannibalization: {self._shorten_path(loser)} competing with {self._shorten_path(winner)}"
        else:
            title = f"Keyword cannibalization between {self._shorten_path(overlap['page_a'])} and {self._shorten_path(overlap['page_b'])}"

        # Build description
        shared_count = overlap.get('shared_count', 0)
        shared_keywords = overlap.get('shared_keywords', [])[:5]  # First 5

        description_parts = [
            f"These pages share {shared_count} keywords ({overlap_score:.0%} overlap).",
            f"Shared keywords include: {', '.join(shared_keywords[:5])}{'...' if len(overlap.get('shared_keywords', [])) > 5 else ''}."
        ]

        if recommendation == 'redirect':
            description_parts.append(f"Recommendation: Redirect '{self._shorten_path(loser)}' to '{self._shorten_path(winner)}' and consolidate content.")
        elif recommendation == 'consolidate':
            description_parts.append(f"Recommendation: Merge content from both pages into '{self._shorten_path(winner)}' and redirect the other.")
        else:
            description_parts.append("Recommendation: Differentiate these pages by targeting distinct keywords or user intents.")

        description = ' '.join(description_parts)

        # Build metrics
        metrics = InsightMetrics(
            gsc_clicks=overlap.get('clicks_a', 0) + overlap.get('clicks_b', 0),
            gsc_impressions=overlap.get('impressions_a', 0) + overlap.get('impressions_b', 0),
        )

        # Add extra metrics
        metrics_dict = metrics.model_dump()
        metrics_dict['shared_keywords_count'] = shared_count
        metrics_dict['overlap_score'] = overlap_score
        metrics_dict['winner_page'] = winner
        metrics_dict['loser_page'] = loser
        metrics_dict['recommendation'] = recommendation
        if winner:
            metrics_dict['winner_clicks'] = overlap.get('winner_stats', {}).get('total_clicks', 0)
            metrics_dict['loser_clicks'] = overlap.get('loser_stats', {}).get('total_clicks', 0)

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=loser or overlap['page_a'],  # Use loser as primary entity
            category=InsightCategory.RISK,
            title=title,
            description=description,
            severity=severity,
            confidence=min(0.5 + overlap_score * 0.5, 0.95),  # Higher overlap = higher confidence
            metrics=InsightMetrics(**{k: v for k, v in metrics_dict.items() if k in InsightMetrics.model_fields or InsightMetrics.model_config.get('extra') == 'allow'}),
            window_days=30,
            source='CannibalizationDetector',
            linked_insight_id=None
        )

    def _shorten_path(self, url: str) -> str:
        """Shorten URL for display"""
        if not url:
            return 'unknown'

        # Extract path from full URL
        if '://' in url:
            url = url.split('://', 1)[1]
            if '/' in url:
                url = '/' + url.split('/', 1)[1]

        # Truncate if too long
        if len(url) > 50:
            return url[:47] + '...'

        return url

    def get_cannibalization_summary(self, property: str) -> Dict:
        """
        Get summary of cannibalization issues for a property

        Returns:
            Dict with summary statistics
        """
        conn = None
        cursor = None

        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_issues,
                    COUNT(*) FILTER (WHERE severity = 'high') as high_severity,
                    COUNT(*) FILTER (WHERE severity = 'medium') as medium_severity,
                    COUNT(*) FILTER (WHERE severity = 'low') as low_severity,
                    COUNT(*) FILTER (WHERE status = 'new') as new_issues,
                    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_issues
                FROM gsc.insights
                WHERE property = %s
                  AND source = 'CannibalizationDetector'
            """, (property,))

            row = cursor.fetchone()
            return dict(row) if row else {}

        except Exception as e:
            logger.error(f"Error getting cannibalization summary: {e}")
            return {}

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
