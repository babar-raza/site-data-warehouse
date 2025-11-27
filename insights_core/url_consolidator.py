"""
URL Consolidator - Detects and recommends URL consolidations

Uses URL parser to find pages with duplicate content or URL variations
that should be consolidated for better SEO performance.

Example:
    consolidator = URLConsolidator()
    candidates = consolidator.find_consolidation_candidates('sc-domain:example.com')
    for candidate in candidates:
        print(f"{candidate['canonical_url']} - {candidate['variation_count']} variations")
"""
import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import RealDictCursor

from insights_core.url_parser import URLParser
from insights_core.models import InsightCreate, InsightMetrics, EntityType, InsightCategory, InsightSeverity

logger = logging.getLogger(__name__)


class URLConsolidator:
    """
    Detects and recommends URL consolidations

    Analyzes URL variations and performance data to identify
    pages that should be consolidated for better SEO.

    Example:
        consolidator = URLConsolidator()
        candidates = consolidator.find_consolidation_candidates('sc-domain:example.com')
    """

    # Scoring weights
    TRAFFIC_WEIGHT = 0.4
    RANKING_WEIGHT = 0.3
    FRESHNESS_WEIGHT = 0.15
    VARIATION_WEIGHT = 0.15

    # Thresholds
    MIN_COMBINED_CLICKS = 10
    MIN_VARIATION_COUNT = 2
    HIGH_PRIORITY_SCORE = 80
    MEDIUM_PRIORITY_SCORE = 50

    def __init__(self, db_dsn: str = None):
        """
        Initialize URL Consolidator

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.url_parser = URLParser(db_dsn=self.db_dsn)
        logger.info("URLConsolidator initialized")

    def find_consolidation_candidates(self, property: str, limit: int = 100) -> List[Dict]:
        """
        Find URLs that should be consolidated

        Args:
            property: Property to analyze
            limit: Maximum candidates to return

        Returns:
            List of consolidation candidates with scores and recommendations
        """
        conn = None
        cursor = None
        candidates = []

        try:
            if not self.db_dsn:
                logger.warning("No database connection configured")
                return candidates

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Get consolidation candidates from variations table
            cursor.execute("""
                SELECT
                    v.property,
                    v.canonical_url,
                    v.variation_count,
                    v.variation_types,
                    v.total_occurrences,
                    v.first_seen,
                    v.last_seen,
                    v.variations
                FROM analytics.vw_url_consolidation_candidates v
                WHERE v.property = %s
                    AND v.variation_count >= %s
                ORDER BY v.variation_count DESC, v.total_occurrences DESC
                LIMIT %s
            """, (property, self.MIN_VARIATION_COUNT, limit))

            rows = cursor.fetchall()
            logger.info(f"Found {len(rows)} initial consolidation candidates for {property}")

            # Enrich each candidate with performance data and scoring
            for row in rows:
                try:
                    candidate = self._enrich_candidate(dict(row), cursor)
                    if candidate:
                        candidates.append(candidate)
                except Exception as e:
                    logger.warning(f"Error enriching candidate {row['canonical_url']}: {e}")

            # Sort by consolidation score
            candidates.sort(key=lambda x: x.get('consolidation_score', 0), reverse=True)

            logger.info(f"Returning {len(candidates)} enriched consolidation candidates")
            return candidates

        except Exception as e:
            logger.error(f"Error finding consolidation candidates: {e}")
            return candidates

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _enrich_candidate(self, candidate: Dict, cursor) -> Optional[Dict]:
        """
        Enrich candidate with performance data and calculate scores

        Args:
            candidate: Base candidate data from variations table
            cursor: Database cursor for queries

        Returns:
            Enriched candidate dict or None if insufficient data
        """
        canonical_url = candidate['canonical_url']
        property = candidate['property']
        variations = candidate.get('variations', [])

        # Get performance data for canonical URL and its variations
        all_urls = [canonical_url] + list(variations)

        cursor.execute("""
            SELECT
                page_path,
                SUM(gsc_clicks) as total_clicks,
                SUM(gsc_impressions) as total_impressions,
                AVG(gsc_avg_position) as avg_position,
                AVG(gsc_ctr) as avg_ctr,
                COUNT(DISTINCT date) as days_with_data
            FROM gsc.vw_unified_page_performance
            WHERE property = %s
                AND page_path = ANY(%s)
                AND date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY page_path
        """, (property, all_urls))

        perf_rows = cursor.fetchall()

        if not perf_rows:
            logger.debug(f"No performance data for {canonical_url}, skipping")
            return None

        # Aggregate performance across all variations
        total_clicks = sum(row['total_clicks'] or 0 for row in perf_rows)
        total_impressions = sum(row['total_impressions'] or 0 for row in perf_rows)

        if total_clicks < self.MIN_COMBINED_CLICKS:
            logger.debug(f"Insufficient clicks ({total_clicks}) for {canonical_url}, skipping")
            return None

        # Calculate metrics for each URL
        url_metrics = []
        for row in perf_rows:
            url_metrics.append({
                'url': row['page_path'],
                'clicks': row['total_clicks'] or 0,
                'impressions': row['total_impressions'] or 0,
                'position': row['avg_position'] or 100,
                'ctr': row['avg_ctr'] or 0,
                'days_with_data': row['days_with_data'] or 0
            })

        # Calculate consolidation score
        consolidation_score = self.calculate_consolidation_score({
            'variation_count': candidate['variation_count'],
            'total_clicks': total_clicks,
            'total_impressions': total_impressions,
            'url_metrics': url_metrics,
            'last_seen': candidate['last_seen'],
            'variation_types': candidate.get('variation_types', [])
        })

        # Recommend which URL should be canonical
        canonical_recommendation = self.recommend_canonical({
            'canonical_url': canonical_url,
            'url_metrics': url_metrics,
            'variation_types': candidate.get('variation_types', [])
        })

        # Determine recommended action
        recommended_action = self._determine_action(
            candidate.get('variation_types', []),
            consolidation_score
        )

        # Determine severity based on score
        if consolidation_score >= self.HIGH_PRIORITY_SCORE:
            severity = 'high'
        elif consolidation_score >= self.MEDIUM_PRIORITY_SCORE:
            severity = 'medium'
        else:
            severity = 'low'

        # Build enriched candidate
        enriched = {
            **candidate,
            'consolidation_score': consolidation_score,
            'total_clicks': total_clicks,
            'total_impressions': total_impressions,
            'url_metrics': url_metrics,
            'recommended_canonical': canonical_recommendation['url'],
            'canonical_reason': canonical_recommendation['reason'],
            'recommended_action': recommended_action,
            'severity': severity,
            'potential_impact': self._estimate_impact(url_metrics, recommended_action)
        }

        return enriched

    def calculate_consolidation_score(self, url_group: Dict) -> float:
        """
        Calculate consolidation priority score

        Higher scores indicate higher priority for consolidation.

        Args:
            url_group: Dict with canonical URL and variations data

        Returns:
            Score between 0-100
        """
        try:
            variation_count = url_group.get('variation_count', 0)
            total_clicks = url_group.get('total_clicks', 0)
            total_impressions = url_group.get('total_impressions', 0)
            url_metrics = url_group.get('url_metrics', [])
            last_seen = url_group.get('last_seen', datetime.now())

            # Traffic score (0-100): Higher traffic = higher priority
            traffic_score = min(100, (total_clicks / 100) * 50 + (total_impressions / 10000) * 50)

            # Ranking score (0-100): Better rankings = higher priority
            # (consolidating well-ranking pages is more valuable)
            if url_metrics:
                avg_position = sum(m.get('position', 100) for m in url_metrics) / len(url_metrics)
                ranking_score = max(0, 100 - avg_position)
            else:
                ranking_score = 0

            # Freshness score (0-100): Recent activity = higher priority
            if isinstance(last_seen, datetime):
                days_since = (datetime.now() - last_seen).days
            else:
                days_since = (datetime.now() - datetime.fromisoformat(str(last_seen).replace('Z', '+00:00'))).days

            freshness_score = max(0, 100 - (days_since * 2))

            # Variation score (0-100): More variations = higher priority
            variation_score = min(100, (variation_count / 10) * 100)

            # Weighted total
            total_score = (
                traffic_score * self.TRAFFIC_WEIGHT +
                ranking_score * self.RANKING_WEIGHT +
                freshness_score * self.FRESHNESS_WEIGHT +
                variation_score * self.VARIATION_WEIGHT
            )

            return round(total_score, 2)

        except Exception as e:
            logger.warning(f"Error calculating consolidation score: {e}")
            return 0.0

    def recommend_canonical(self, url_group: Dict) -> Dict:
        """
        Recommend which URL should be the canonical

        Args:
            url_group: Dict with all URL variations and their metrics

        Returns:
            Dict with recommended canonical and reasoning
        """
        canonical_url = url_group.get('canonical_url')
        url_metrics = url_group.get('url_metrics', [])
        variation_types = url_group.get('variation_types', [])

        if not url_metrics:
            return {
                'url': canonical_url,
                'reason': 'No performance data available, using normalized canonical'
            }

        # Score each URL
        scored_urls = []
        for metric in url_metrics:
            url = metric['url']

            # Scoring factors
            clicks_score = metric.get('clicks', 0) * 0.4
            impressions_score = (metric.get('impressions', 0) / 100) * 0.2
            position_score = max(0, 100 - metric.get('position', 100)) * 0.3

            # URL structure score: prefer clean URLs
            structure_score = 0
            if url == canonical_url:
                structure_score = 10  # Prefer the already-canonical URL
            if '?' not in url:
                structure_score += 5  # Prefer no query params
            if '#' not in url:
                structure_score += 3  # Prefer no fragments
            if not url.endswith('/') or url == '/':
                structure_score += 2  # Prefer no trailing slash (except root)

            structure_score *= 0.1

            total_score = clicks_score + impressions_score + position_score + structure_score

            scored_urls.append({
                'url': url,
                'score': total_score,
                'clicks': metric.get('clicks', 0),
                'impressions': metric.get('impressions', 0),
                'position': metric.get('position', 100)
            })

        # Sort by score
        scored_urls.sort(key=lambda x: x['score'], reverse=True)
        best_url = scored_urls[0]

        # Generate reasoning
        if best_url['url'] == canonical_url:
            reason = f"Current canonical URL has best performance ({best_url['clicks']} clicks)"
        else:
            reason = (
                f"Variation has better performance ({best_url['clicks']} clicks vs "
                f"{next((u['clicks'] for u in scored_urls if u['url'] == canonical_url), 0)} clicks)"
            )

        return {
            'url': best_url['url'],
            'reason': reason,
            'score': best_url['score']
        }

    def _determine_action(self, variation_types: List[str], score: float) -> str:
        """
        Determine recommended consolidation action

        Args:
            variation_types: Types of variations present
            score: Consolidation priority score

        Returns:
            Recommended action string
        """
        if not variation_types:
            return 'monitor'

        # High priority actions
        if score >= self.HIGH_PRIORITY_SCORE:
            if 'query_param' in variation_types:
                return 'canonical_tag_and_redirect'
            elif 'trailing_slash' in variation_types:
                return 'redirect_301'
            elif 'case' in variation_types:
                return 'redirect_301'
            elif 'protocol' in variation_types:
                return 'redirect_301'
            else:
                return 'canonical_tag'

        # Medium priority
        elif score >= self.MEDIUM_PRIORITY_SCORE:
            if 'query_param' in variation_types:
                return 'canonical_tag'
            elif 'trailing_slash' in variation_types or 'case' in variation_types:
                return 'redirect_301'
            else:
                return 'canonical_tag'

        # Low priority
        else:
            return 'canonical_tag'

    def _estimate_impact(self, url_metrics: List[Dict], action: str) -> str:
        """
        Estimate potential impact of consolidation

        Args:
            url_metrics: Performance metrics for URLs
            action: Recommended action

        Returns:
            Impact estimate string
        """
        if not url_metrics:
            return "Unknown impact - insufficient data"

        total_clicks = sum(m.get('clicks', 0) for m in url_metrics)

        # Estimate improvement based on consolidation
        if action in ['redirect_301', 'canonical_tag_and_redirect']:
            # Consolidating via redirects typically preserves most value
            estimated_improvement = "5-15% increase in ranking power"
        elif action == 'canonical_tag':
            # Canonical tags help but less impact than redirects
            estimated_improvement = "3-10% increase in ranking power"
        else:
            estimated_improvement = "Minimal immediate impact, prevents future dilution"

        return f"{estimated_improvement} (currently {total_clicks} clicks/month across variations)"

    def create_consolidation_insight(self, candidate: Dict, property: str) -> InsightCreate:
        """
        Create insight for a consolidation candidate

        Args:
            candidate: Consolidation candidate data
            property: Property identifier

        Returns:
            InsightCreate object
        """
        canonical_url = candidate['canonical_url']
        variation_count = candidate['variation_count']
        consolidation_score = candidate.get('consolidation_score', 0)
        recommended_action = candidate.get('recommended_action', 'canonical_tag')
        total_clicks = candidate.get('total_clicks', 0)
        total_impressions = candidate.get('total_impressions', 0)

        # Map severity
        severity_map = {
            'high': InsightSeverity.HIGH,
            'medium': InsightSeverity.MEDIUM,
            'low': InsightSeverity.LOW
        }
        severity = severity_map.get(candidate.get('severity', 'low'), InsightSeverity.LOW)

        # Build description
        variation_types = candidate.get('variation_types', [])
        variation_types_str = ', '.join(variation_types) if variation_types else 'multiple types'

        description = (
            f"URL consolidation opportunity detected for {canonical_url}. "
            f"Found {variation_count} variations ({variation_types_str}) that should be consolidated. "
            f"Combined performance: {total_clicks} clicks and {total_impressions} impressions in last 30 days. "
            f"Recommended action: {recommended_action.replace('_', ' ')}. "
            f"{candidate.get('potential_impact', '')} "
            f"Recommended canonical: {candidate.get('recommended_canonical', canonical_url)} - "
            f"{candidate.get('canonical_reason', '')}"
        )

        # Determine confidence based on data quality
        url_metrics = candidate.get('url_metrics', [])
        if url_metrics and total_clicks > 50:
            confidence = 0.85
        elif url_metrics and total_clicks > 10:
            confidence = 0.75
        else:
            confidence = 0.65

        return InsightCreate(
            property=property,
            entity_type=EntityType.PAGE,
            entity_id=canonical_url,
            category=InsightCategory.OPPORTUNITY,
            title=f"URL Consolidation Opportunity ({variation_count} variations)",
            description=description,
            severity=severity,
            confidence=confidence,
            metrics=InsightMetrics(
                gsc_clicks=float(total_clicks) if total_clicks else None,
                gsc_impressions=float(total_impressions) if total_impressions else None,
                variation_count=variation_count,
                consolidation_score=consolidation_score,
                recommended_action=recommended_action,
                variation_types=variation_types
            ),
            window_days=30,
            source="URLConsolidator"
        )

    def detect_consolidation_opportunities(self, property: str) -> int:
        """
        Run consolidation detection and create insights

        Args:
            property: Property to analyze

        Returns:
            Number of insights created
        """
        logger.info(f"Starting consolidation detection for {property}")

        try:
            # Find candidates
            candidates = self.find_consolidation_candidates(property, limit=50)

            if not candidates:
                logger.info(f"No consolidation candidates found for {property}")
                return 0

            # Store candidates in database
            stored_count = 0
            for candidate in candidates:
                if self.store_candidate(candidate):
                    stored_count += 1

            logger.info(f"Stored {stored_count} consolidation candidates in database")
            return stored_count

        except Exception as e:
            logger.error(f"Error in consolidation detection: {e}")
            return 0

    def store_candidate(self, candidate: Dict) -> bool:
        """
        Store consolidation candidate in database

        Args:
            candidate: Candidate data to store

        Returns:
            True if stored successfully
        """
        conn = None
        cursor = None

        try:
            if not self.db_dsn:
                logger.warning("No database connection configured")
                return False

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            # Prepare variation URLs as JSONB
            url_metrics = candidate.get('url_metrics', [])
            variation_urls = [
                {
                    'url': m['url'],
                    'clicks': m.get('clicks', 0),
                    'impressions': m.get('impressions', 0),
                    'position': m.get('position', 100)
                }
                for m in url_metrics
            ]

            cursor.execute("""
                INSERT INTO analytics.consolidation_candidates (
                    property,
                    canonical_url,
                    variation_urls,
                    variation_count,
                    consolidation_score,
                    recommended_action,
                    total_clicks,
                    total_impressions,
                    status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (property, canonical_url)
                DO UPDATE SET
                    variation_urls = EXCLUDED.variation_urls,
                    variation_count = EXCLUDED.variation_count,
                    consolidation_score = EXCLUDED.consolidation_score,
                    recommended_action = EXCLUDED.recommended_action,
                    total_clicks = EXCLUDED.total_clicks,
                    total_impressions = EXCLUDED.total_impressions,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                candidate['property'],
                candidate['canonical_url'],
                psycopg2.extras.Json(variation_urls),
                candidate['variation_count'],
                candidate.get('consolidation_score', 0),
                candidate.get('recommended_action', 'canonical_tag'),
                candidate.get('total_clicks', 0),
                candidate.get('total_impressions', 0),
                'pending'
            ))

            conn.commit()
            logger.debug(f"Stored consolidation candidate: {candidate['canonical_url']}")
            return True

        except Exception as e:
            logger.error(f"Error storing consolidation candidate: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_consolidation_history(self, property: str) -> List[Dict]:
        """
        Get history of consolidation actions

        Args:
            property: Property to query

        Returns:
            List of consolidation history records
        """
        conn = None
        cursor = None
        history = []

        try:
            if not self.db_dsn:
                logger.warning("No database connection configured")
                return history

            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT
                    c.canonical_url,
                    c.variation_count,
                    c.consolidation_score,
                    c.recommended_action,
                    c.status,
                    c.created_at,
                    c.updated_at,
                    h.action_taken,
                    h.action_details,
                    h.performed_by,
                    h.performed_at,
                    h.outcome
                FROM analytics.consolidation_candidates c
                LEFT JOIN analytics.consolidation_history h
                    ON c.id = h.candidate_id
                WHERE c.property = %s
                ORDER BY c.consolidation_score DESC, c.updated_at DESC
                LIMIT 100
            """, (property,))

            rows = cursor.fetchall()
            history = [dict(row) for row in rows]

            logger.info(f"Retrieved {len(history)} consolidation history records for {property}")
            return history

        except Exception as e:
            logger.error(f"Error retrieving consolidation history: {e}")
            return history

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
