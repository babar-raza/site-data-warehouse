"""
Anomaly Detector - Finds statistical anomalies in traffic
"""
import logging
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

logger = logging.getLogger(__name__)


class AnomalyDetector(BaseDetector):
    """
    Detects anomalies in GSC and GA4 metrics
    
    Rules:
    - High severity risk: Clicks down >20% AND conversions down >20%
    - Medium severity risk: Clicks down >20% OR conversions down >20%
    - Opportunity: Impressions up >50%
    """
    
    def detect(self, property: str = None) -> int:
        """Run anomaly detection"""
        logger.info("Starting anomaly detection...")
        
        # Get latest day data with week-over-week changes
        conn = self._get_db_connection()
        insights_created = 0
        
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Find pages with significant negative changes
                query = """
                    SELECT DISTINCT ON (property, page_path)
                        property,
                        page_path,
                        date,
                        gsc_clicks,
                        gsc_clicks_change_wow,
                        gsc_impressions,
                        gsc_impressions_change_wow,
                        gsc_ctr,
                        gsc_position_change_wow,
                        ga_conversions,
                        ga_conversions_change_wow,
                        ga_engagement_rate,
                        ga_engagement_rate_7d_ago
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                    AND (
                        gsc_clicks_change_wow < %s
                        OR gsc_impressions_change_wow > %s
                        OR ga_conversions_change_wow < %s
                    )
                """
                params = [
                    self.config.risk_threshold_clicks_pct,
                    self.config.opportunity_threshold_impressions_pct,
                    self.config.risk_threshold_conversions_pct,
                ]
                
                if property:
                    query += " AND property = %s"
                    params.append(property)
                
                query += " ORDER BY property, page_path, date DESC"
                
                cur.execute(query, params)
                rows = cur.fetchall()
            
            logger.info(f"Found {len(rows)} pages with anomalies")
            
            for row in rows:
                insights = self._analyze_row(dict(row))
                for insight_create in insights:
                    try:
                        self.repository.create(insight_create)
                        insights_created += 1
                    except Exception as e:
                        logger.warning(f"Failed to create insight: {e}")
            
            return insights_created
            
        finally:
            conn.close()
    
    def _analyze_row(self, row: dict) -> List[InsightCreate]:
        """Analyze a single row and generate insights"""
        insights = []
        
        clicks_change = row.get('gsc_clicks_change_wow') or 0
        conversions_change = row.get('ga_conversions_change_wow') or 0
        impressions_change = row.get('gsc_impressions_change_wow') or 0
        
        # Convert date to proper format for calculations
        row_date = row['date']
        if isinstance(row_date, str):
            row_date = datetime.fromisoformat(row_date).date()
        elif isinstance(row_date, datetime):
            row_date = row_date.date()
        
        window_start = (row_date - timedelta(days=7)).isoformat()
        window_end = row_date.isoformat()
        
        # High Severity Risk: Both clicks and conversions down significantly
        if (clicks_change < self.config.risk_threshold_clicks_pct and 
            conversions_change < self.config.risk_threshold_conversions_pct):
            
            insights.append(InsightCreate(
                property=row['property'],
                entity_type=EntityType.PAGE,
                entity_id=row['page_path'],
                category=InsightCategory.RISK,
                title="Traffic & Conversion Drop",
                description=(
                    f"Page experiencing significant decline in both traffic and conversions. "
                    f"Clicks down {abs(clicks_change):.1f}%, "
                    f"conversions down {abs(conversions_change):.1f}% week-over-week."
                ),
                severity=InsightSeverity.HIGH,
                confidence=0.9,
                metrics=InsightMetrics(
                    gsc_clicks=row.get('gsc_clicks'),
                    gsc_clicks_change=clicks_change,
                    ga_conversions=row.get('ga_conversions'),
                    ga_conversions_change=conversions_change,
                    window_start=window_start,
                    window_end=window_end,
                ),
                window_days=7,
                source="AnomalyDetector",
            ))
        
        # Medium Severity Risk: Just clicks down
        elif clicks_change < self.config.risk_threshold_clicks_pct:
            insights.append(InsightCreate(
                property=row['property'],
                entity_type=EntityType.PAGE,
                entity_id=row['page_path'],
                category=InsightCategory.RISK,
                title="Traffic Drop",
                description=(
                    f"Page traffic declined significantly. "
                    f"Clicks down {abs(clicks_change):.1f}% week-over-week."
                ),
                severity=InsightSeverity.MEDIUM,
                confidence=0.8,
                metrics=InsightMetrics(
                    gsc_clicks=row.get('gsc_clicks'),
                    gsc_clicks_change=clicks_change,
                    gsc_impressions=row.get('gsc_impressions'),
                    window_start=window_start,
                    window_end=window_end,
                ),
                window_days=7,
                source="AnomalyDetector",
            ))
        
        # Opportunity: Impressions spike
        if impressions_change > self.config.opportunity_threshold_impressions_pct:
            insights.append(InsightCreate(
                property=row['property'],
                entity_type=EntityType.PAGE,
                entity_id=row['page_path'],
                category=InsightCategory.OPPORTUNITY,
                title="Impression Spike",
                description=(
                    f"Page visibility increased dramatically. "
                    f"Impressions up {impressions_change:.1f}% week-over-week. "
                    f"Opportunity to optimize CTR and capture more traffic."
                ),
                severity=InsightSeverity.MEDIUM,
                confidence=0.75,
                metrics=InsightMetrics(
                    gsc_impressions=row.get('gsc_impressions'),
                    gsc_impressions_change=impressions_change,
                    gsc_ctr=row.get('gsc_ctr'),
                    window_start=window_start,
                    window_end=window_end,
                ),
                window_days=7,
                source="AnomalyDetector",
            ))
        
        return insights
