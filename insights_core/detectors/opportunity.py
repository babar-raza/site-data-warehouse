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
    3. Cannibalization: Multiple pages for same query (future)
    """
    
    def detect(self, property: str = None) -> int:
        """Find opportunities"""
        logger.info("Starting opportunity detection...")
        
        insights_created = 0
        insights_created += self._find_striking_distance(property)
        insights_created += self._find_content_gaps(property)
        
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
                        gsc_avg_position,
                        gsc_impressions,
                        gsc_clicks,
                        gsc_ctr,
                        ga_conversions,
                        ga_engagement_rate
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                    AND is_striking_distance = TRUE
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
                            f"Page ranks in position {row['gsc_avg_position']:.1f} "
                            f"with {row['gsc_impressions']} impressions. "
                            f"Small ranking improvement could yield significant traffic gains. "
                            f"Current CTR: {row['gsc_ctr']*100:.2f}%."
                        ),
                        severity=InsightSeverity.MEDIUM,
                        confidence=0.8,
                        metrics=InsightMetrics(
                            gsc_position=row['gsc_avg_position'],
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
