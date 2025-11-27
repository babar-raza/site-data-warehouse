"""
SERP Analyst Agent
==================
Specialist agent for analyzing SERP positions, competitor movements,
and search visibility trends.

Capabilities:
- Detect ranking changes and trends
- Analyze competitor movements
- Identify opportunities for ranking improvements
- Recommend content updates based on SERP features
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List

import asyncpg

logger = logging.getLogger(__name__)


class SerpAnalystAgent:
    """
    Specialist agent for SERP analysis and recommendations
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize SERP Analyst Agent

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: asyncpg.Pool | None = None

        logger.info("SerpAnalystAgent initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def analyze(self, state: Dict) -> Dict:
        """
        Analyze SERP data and generate recommendations

        Args:
            state: Workflow state with property, page_path, etc.

        Returns:
            Analysis result with recommendations
        """
        try:
            workflow_id = state['workflow_id']
            property_url = state['property']
            page_path = state.get('page_path')

            logger.info(f"SERP Analyst analyzing property: {property_url}")

            # Get recent SERP data
            position_changes = await self._get_position_changes(property_url, days=7)
            competitor_movements = await self._analyze_competitors(property_url)
            serp_features = await self._analyze_serp_features(property_url)

            # Generate recommendations
            recommendations = []

            # Check for position drops
            for change in position_changes:
                if change['position_drop'] >= 3:
                    recommendations.append({
                        'type': 'address_position_drop',
                        'priority': 'high' if change['position_drop'] >= 5 else 'medium',
                        'confidence': 0.85,
                        'estimated_impact': 'high',
                        'query': change['query_text'],
                        'details': {
                            'old_position': change['old_position'],
                            'new_position': change['new_position'],
                            'drop': change['position_drop']
                        },
                        'action': f"Review and update content for '{change['query_text']}' to regain ranking",
                        'reasoning': f"Position dropped from {change['old_position']} to {change['new_position']} (-{change['position_drop']})"
                    })

            # Check for competitor gains
            for competitor in competitor_movements:
                if competitor['gained_positions'] >= 2:
                    recommendations.append({
                        'type': 'counter_competitor',
                        'priority': 'medium',
                        'confidence': 0.75,
                        'estimated_impact': 'medium',
                        'competitor_domain': competitor['domain'],
                        'details': competitor,
                        'action': f"Analyze {competitor['domain']}'s content improvements",
                        'reasoning': f"Competitor gained {competitor['gained_positions']} positions in last 7 days"
                    })

            # Check for SERP feature opportunities
            for feature in serp_features:
                if not feature['we_have_feature'] and feature['feature_type'] in ['featured_snippet', 'people_also_ask']:
                    recommendations.append({
                        'type': 'capture_serp_feature',
                        'priority': 'high',
                        'confidence': 0.70,
                        'estimated_impact': 'high',
                        'feature_type': feature['feature_type'],
                        'query': feature['query_text'],
                        'details': feature,
                        'action': f"Optimize content to win {feature['feature_type']} for '{feature['query_text']}'",
                        'reasoning': f"SERP feature opportunity: {feature['feature_type']} not currently owned"
                    })

            # Record decision in database
            await self._record_decision(
                workflow_id,
                property_url,
                recommendations
            )

            return {
                'agent': 'serp_analyst',
                'status': 'completed',
                'position_changes': len(position_changes),
                'competitor_movements': len(competitor_movements),
                'serp_features': len(serp_features),
                'recommendations': recommendations,
                'summary': f"Analyzed {len(position_changes)} position changes, found {len(recommendations)} opportunities"
            }

        except Exception as e:
            logger.error(f"Error in SERP analysis: {e}")
            return {
                'agent': 'serp_analyst',
                'status': 'failed',
                'error': str(e),
                'recommendations': []
            }

    async def _get_position_changes(
        self,
        property_url: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Get SERP position changes for the property

        Args:
            property_url: Property URL
            days: Number of days to look back

        Returns:
            List of position changes
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    WITH current_positions AS (
                        SELECT DISTINCT ON (ph.query_id)
                            q.query_text,
                            ph.position as current_position,
                            ph.check_date
                        FROM serp.position_history ph
                        JOIN serp.queries q ON ph.query_id = q.query_id
                        WHERE q.property = $1
                            AND ph.check_date >= CURRENT_DATE - $2
                        ORDER BY ph.query_id, ph.check_date DESC
                    ),
                    previous_positions AS (
                        SELECT DISTINCT ON (ph.query_id)
                            q.query_text,
                            ph.position as previous_position
                        FROM serp.position_history ph
                        JOIN serp.queries q ON ph.query_id = q.query_id
                        WHERE q.property = $1
                            AND ph.check_date < (CURRENT_DATE - $2)
                            AND ph.check_date >= (CURRENT_DATE - $2 * 2)
                        ORDER BY ph.query_id, ph.check_date DESC
                    )
                    SELECT
                        c.query_text,
                        p.previous_position as old_position,
                        c.current_position as new_position,
                        c.current_position - p.previous_position as position_drop
                    FROM current_positions c
                    JOIN previous_positions p ON c.query_text = p.query_text
                    WHERE c.current_position > p.previous_position  -- Position got worse (higher number)
                    ORDER BY position_drop DESC
                    LIMIT 20
                """, property_url, days)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting position changes: {e}")
            return []

    async def _analyze_competitors(
        self,
        property_url: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Analyze competitor movements

        Args:
            property_url: Property URL
            days: Number of days to look back

        Returns:
            List of competitor movements
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    WITH competitor_positions AS (
                        SELECT
                            domain,
                            AVG(position) FILTER (WHERE check_date >= CURRENT_DATE - $2) as current_avg_position,
                            AVG(position) FILTER (WHERE check_date < CURRENT_DATE - $2 AND check_date >= CURRENT_DATE - $2 * 2) as previous_avg_position,
                            COUNT(*) as appearances
                        FROM serp.position_history ph
                        JOIN serp.queries q ON ph.query_id = q.query_id
                        WHERE q.property = $1
                            AND ph.domain != $1
                            AND ph.check_date >= CURRENT_DATE - $2 * 2
                        GROUP BY domain
                        HAVING COUNT(*) >= 3  -- Must appear in at least 3 queries
                    )
                    SELECT
                        domain,
                        previous_avg_position as old_avg_position,
                        current_avg_position as new_avg_position,
                        previous_avg_position - current_avg_position as gained_positions,
                        appearances
                    FROM competitor_positions
                    WHERE previous_avg_position > current_avg_position  -- Competitor improved
                    ORDER BY gained_positions DESC
                    LIMIT 10
                """, property_url, days)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error analyzing competitors: {e}")
            return []

    async def _analyze_serp_features(
        self,
        property_url: str,
        days: int = 7
    ) -> List[Dict]:
        """
        Analyze SERP features

        Args:
            property_url: Property URL
            days: Number of days to look back

        Returns:
            List of SERP feature opportunities
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    WITH our_domain AS (
                        SELECT regexp_replace($1, '^https?://', '') as domain
                    )
                    SELECT
                        q.query_text,
                        sf.feature_type,
                        sf.featured_domain,
                        CASE WHEN sf.featured_domain = (SELECT domain FROM our_domain) THEN true ELSE false END as we_have_feature,
                        sf.check_date
                    FROM serp.serp_features sf
                    JOIN serp.queries q ON sf.query_id = q.query_id
                    WHERE q.property = $1
                        AND sf.check_date >= CURRENT_DATE - $2
                        AND sf.feature_type IN ('featured_snippet', 'people_also_ask', 'local_pack')
                    ORDER BY sf.check_date DESC
                    LIMIT 50
                """, property_url, days)

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error analyzing SERP features: {e}")
            return []

    async def _record_decision(
        self,
        workflow_id: str,
        property_url: str,
        recommendations: List[Dict]
    ):
        """Record agent decision in database"""
        try:
            pool = await self.get_pool()

            # Calculate overall confidence
            confidences = [r.get('confidence', 0.5) for r in recommendations]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestration.agent_decisions (
                        workflow_id,
                        agent_name,
                        decision_type,
                        decision,
                        reasoning,
                        confidence,
                        recommendations,
                        priority,
                        property
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    workflow_id,
                    'serp_analyst',
                    'analyze_serp_performance',
                    f"Found {len(recommendations)} SERP opportunities",
                    f"Analyzed rankings and identified {len(recommendations)} actionable recommendations",
                    avg_confidence,
                    recommendations,
                    'high' if any(r.get('priority') == 'high' for r in recommendations) else 'medium',
                    property_url
                )

            logger.info(f"Recorded SERP analyst decision for workflow: {workflow_id}")

        except Exception as e:
            logger.error(f"Error recording decision: {e}")


__all__ = ['SerpAnalystAgent']
