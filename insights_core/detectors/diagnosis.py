"""
Diagnosis Detector - Analyzes existing risks to find root causes
"""
import logging
from typing import List, Optional
from insights_core.detectors.base import BaseDetector
from insights_core.models import (
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)

logger = logging.getLogger(__name__)


class DiagnosisDetector(BaseDetector):
    """
    Diagnoses existing risk insights
    
    Hypotheses:
    1. Ranking issue: Position worsened
    2. Behavior issue: Engagement rate dropped
    3. Content change: Modified within 48 hours
    """
    
    def detect(self, property: str = None) -> int:
        """Run diagnosis on existing risks"""
        logger.info("Starting diagnosis detection...")
        
        # Get all NEW risk insights
        risks = self.repository.get_by_status(
            InsightStatus.NEW,
            property=property
        )
        risks = [r for r in risks if r.category == InsightCategory.RISK]
        
        logger.info(f"Found {len(risks)} new risks to diagnose")
        
        insights_created = 0
        
        for risk in risks:
            try:
                diagnosis = self._diagnose_risk(risk)
                if diagnosis:
                    # Create diagnosis insight
                    created = self.repository.create(diagnosis)
                    insights_created += 1
                    
                    # Update original risk to diagnosed status
                    self.repository.update(
                        risk.id,
                        InsightUpdate(
                            status=InsightStatus.DIAGNOSED,
                            linked_insight_id=created.id
                        )
                    )
                    logger.info(f"Diagnosed risk {risk.id}: {diagnosis.title}")
            except Exception as e:
                logger.error(f"Failed to diagnose risk {risk.id}: {e}")
        
        return insights_created
    
    def _diagnose_risk(self, risk) -> Optional[InsightCreate]:
        """
        Diagnose a single risk insight
        
        Returns InsightCreate for diagnosis, or None if no clear diagnosis
        """
        conn = self._get_db_connection()
        
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get latest data for this page
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_unified_page_performance
                    WHERE property = %s
                    AND page_path = %s
                    AND date >= CURRENT_DATE - INTERVAL '14 days'
                    ORDER BY date DESC
                    LIMIT 1
                """, (risk.property, risk.entity_id))
                
                row = cur.fetchone()
                
                if not row:
                    return None
                
                row = dict(row)
        finally:
            conn.close()
        
        # Hypothesis 1: Ranking dropped
        position_change = row.get('gsc_position_change_wow') or 0
        if position_change > 10:  # Position worsened by >10
            return InsightCreate(
                property=risk.property,
                entity_type=EntityType.PAGE,
                entity_id=risk.entity_id,
                category=InsightCategory.DIAGNOSIS,
                title="Ranking Issue Detected",
                description=(
                    f"Root cause identified: Search ranking declined significantly. "
                    f"Average position worsened by {position_change:.1f} spots week-over-week. "
                    f"This explains the traffic drop."
                ),
                severity=risk.severity,
                confidence=0.85,
                metrics=InsightMetrics(
                    gsc_position=row.get('gsc_avg_position'),
                    gsc_position_change=position_change,
                    gsc_clicks=row.get('gsc_clicks'),
                    gsc_clicks_change=row.get('gsc_clicks_change_wow'),
                ),
                window_days=7,
                source="DiagnosisDetector",
                linked_insight_id=risk.id,
            )
        
        # Hypothesis 2: Engagement issue
        engagement_current = row.get('ga_engagement_rate') or 0
        engagement_prev = row.get('ga_engagement_rate_7d_ago') or 0
        engagement_drop = ((engagement_current - engagement_prev) / engagement_prev * 100) if engagement_prev > 0 else 0
        
        if engagement_drop < -15:  # Engagement dropped >15%
            return InsightCreate(
                property=risk.property,
                entity_type=EntityType.PAGE,
                entity_id=risk.entity_id,
                category=InsightCategory.DIAGNOSIS,
                title="Engagement Issue Detected",
                description=(
                    f"Root cause identified: User engagement declined. "
                    f"Engagement rate dropped {abs(engagement_drop):.1f}% while traffic remained stable. "
                    f"Content quality or relevance may be an issue."
                ),
                severity=risk.severity,
                confidence=0.75,
                metrics=InsightMetrics(
                    ga_engagement_rate=engagement_current,
                    ga_conversions=row.get('ga_conversions'),
                    ga_conversions_change=row.get('ga_conversions_change_wow'),
                ),
                window_days=7,
                source="DiagnosisDetector",
                linked_insight_id=risk.id,
            )
        
        # Hypothesis 3: Recent content change
        modified_within_48h = row.get('modified_within_48h', False)
        if modified_within_48h:
            last_modified = row.get('last_modified_date')
            last_modified_str = last_modified.isoformat() if last_modified else "recently"
            
            return InsightCreate(
                property=risk.property,
                entity_type=EntityType.PAGE,
                entity_id=risk.entity_id,
                category=InsightCategory.DIAGNOSIS,
                title="Recent Content Change",
                description=(
                    f"Root cause identified: Page was modified within 48 hours of traffic drop. "
                    f"Last modified: {last_modified_str}. "
                    f"Recent content changes may have impacted performance."
                ),
                severity=InsightSeverity.MEDIUM,
                confidence=0.7,
                metrics=InsightMetrics(
                    gsc_clicks=row.get('gsc_clicks'),
                    gsc_clicks_change=row.get('gsc_clicks_change_wow'),
                ),
                window_days=7,
                source="DiagnosisDetector",
                linked_insight_id=risk.id,
            )
        
        return None
