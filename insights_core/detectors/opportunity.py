"""
Opportunity Detector - Finds optimization opportunities
"""
import logging
from typing import List
from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    EntityType,
    InsightMetrics,
)

logger = logging.getLogger(__name__)


class OpportunityDetector(BaseDetector):
    """
    Finds optimization opportunities

    Strategies:
    1. Striking Distance: Pages ranking 11-20 with high impressions
    2. Content Gap: High impressions, low engagement
    3. URL Consolidation: Multiple URL variations for same content
    4. Cannibalization: Multiple pages for same query (future)
    """

    def detect(self, property: str = None) -> int:
        """Find opportunities"""
        logger.info("Starting opportunity detection...")

        insights_created = 0
        insights_created += self._find_striking_distance(property)
        insights_created += self._find_content_gaps(property)
        insights_created += self._find_url_consolidation_opportunities(property)

        return insights_created
    
    def _find_striking_distance(self, property: str = None) -> int:
        """Find pages in "striking distance" (positions 11-20)"""
        conn = self._get_db_connection()
        insights_created = 0
        
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT DISTINCT ON (property, page_path)
                        property,
                        page_path,
                        date,
                        gsc_position,
                        gsc_impressions,
                        gsc_clicks,
                        gsc_ctr,
                        ga_conversions,
                        ga_engagement_rate
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                    AND gsc_position BETWEEN 11 AND 20  -- Striking distance
                    AND gsc_impressions > 100  -- High volume
                """
                
                params = []
                if property:
                    query += " AND property = %s"
                    params.append(property)
                
                query += " ORDER BY property, page_path, date DESC"
                cur.execute(query, params)
                
                rows = cur.fetchall()
            
            logger.info(f"Found {len(rows)} striking distance opportunities")
            
            for row in rows:
                row = dict(row)
                try:
                    insight = InsightCreate(
                        property=row['property'],
                        entity_type=EntityType.PAGE,
                        entity_id=row['page_path'],
                        category=InsightCategory.OPPORTUNITY,
                        title="Striking Distance Opportunity",
                        description=(
                            f"Page ranks in position {row['gsc_position']:.1f} "
                            f"with {row['gsc_impressions']} impressions. "
                            f"Small ranking improvement could yield significant traffic gains. "
                            f"Current CTR: {row['gsc_ctr']*100:.2f}%."
                        ),
                        severity=InsightSeverity.MEDIUM,
                        confidence=0.8,
                        metrics=InsightMetrics(
                            gsc_position=row['gsc_position'],
                            gsc_impressions=row['gsc_impressions'],
                            gsc_clicks=row['gsc_clicks'],
                            gsc_ctr=row['gsc_ctr'],
                            ga_conversions=row.get('ga_conversions'),
                        ),
                        window_days=7,
                        source="OpportunityDetector",
                    )
                    self.repository.create(insight)
                    insights_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create striking distance insight: {e}")
            
            return insights_created
            
        finally:
            conn.close()
    
    def _find_content_gaps(self, property: str = None) -> int:
        """Find pages with high impressions but low engagement"""
        conn = self._get_db_connection()
        insights_created = 0
        
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT DISTINCT ON (property, page_path)
                        property,
                        page_path,
                        date,
                        gsc_impressions,
                        gsc_clicks,
                        gsc_ctr,
                        ga_engagement_rate,
                        ga_sessions,
                        ga_bounce_rate
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                    AND gsc_impressions > 500  -- High visibility
                    AND ga_engagement_rate < 0.4  -- Low engagement
                    AND ga_sessions > 10  -- Has traffic
                """
                
                params = []
                if property:
                    query += " AND property = %s"
                    params.append(property)
                
                query += " ORDER BY property, page_path, date DESC"
                cur.execute(query, params)
                
                rows = cur.fetchall()
            
            logger.info(f"Found {len(rows)} content gap opportunities")
            
            for row in rows:
                row = dict(row)
                try:
                    insight = InsightCreate(
                        property=row['property'],
                        entity_type=EntityType.PAGE,
                        entity_id=row['page_path'],
                        category=InsightCategory.OPPORTUNITY,
                        title="Content Gap Opportunity",
                        description=(
                            f"Page receives {row['gsc_impressions']} impressions "
                            f"but has low engagement rate ({row['ga_engagement_rate']*100:.1f}%). "
                            f"Content may not match user intent. "
                            f"Improving content relevance could increase conversions."
                        ),
                        severity=InsightSeverity.LOW,
                        confidence=0.65,
                        metrics=InsightMetrics(
                            gsc_impressions=row['gsc_impressions'],
                            gsc_clicks=row['gsc_clicks'],
                            ga_engagement_rate=row['ga_engagement_rate'],
                            ga_sessions=row['ga_sessions'],
                            ga_bounce_rate=row.get('ga_bounce_rate'),
                        ),
                        window_days=7,
                        source="OpportunityDetector",
                    )
                    self.repository.create(insight)
                    insights_created += 1
                except Exception as e:
                    logger.warning(f"Failed to create content gap insight: {e}")

            return insights_created

        finally:
            conn.close()

    def _find_url_consolidation_opportunities(self, property: str = None) -> int:
        """Find URL consolidation opportunities using URLConsolidator"""
        insights_created = 0

        try:
            from insights_core.url_consolidator import URLConsolidator

            consolidator = URLConsolidator(db_dsn=self.conn_string)

            # Get properties to analyze
            if property:
                properties = [property]
            else:
                # Get all properties from database
                conn = self._get_db_connection()
                try:
                    from psycopg2.extras import RealDictCursor
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT DISTINCT property
                            FROM gsc.vw_unified_page_performance
                            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                        """)
                        properties = [row['property'] for row in cur.fetchall()]
                finally:
                    conn.close()

            logger.info(f"Analyzing URL consolidation for {len(properties)} properties")

            # Find candidates for each property
            for prop in properties:
                try:
                    candidates = consolidator.find_consolidation_candidates(prop, limit=25)

                    if not candidates:
                        logger.debug(f"No consolidation candidates for {prop}")
                        continue

                    # Create insights for high-priority candidates
                    for candidate in candidates:
                        # Only create insights for medium+ priority
                        if candidate.get('consolidation_score', 0) >= consolidator.MEDIUM_PRIORITY_SCORE:
                            try:
                                insight = consolidator.create_consolidation_insight(candidate, prop)
                                self.repository.create(insight)
                                insights_created += 1
                            except Exception as e:
                                logger.warning(f"Failed to create consolidation insight for {candidate.get('canonical_url')}: {e}")

                except Exception as e:
                    logger.warning(f"Error analyzing consolidation for property {prop}: {e}")

            logger.info(f"Created {insights_created} URL consolidation insights")
            return insights_created

        except ImportError as e:
            logger.error(f"URLConsolidator not available: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error in URL consolidation detection: {e}")
            return 0
