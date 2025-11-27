"""
Performance Optimization Agent
===============================
Specialist agent for Core Web Vitals optimization and performance improvements.

Capabilities:
- Analyze CWV metrics (LCP, FID, CLS)
- Identify performance bottlenecks
- Generate optimization recommendations
- Prioritize fixes by impact
"""
import logging
import os
from typing import Dict, List

import asyncpg

logger = logging.getLogger(__name__)


class PerformanceAgent:
    """Specialist agent for performance optimization"""

    def __init__(self, db_dsn: str = None):
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: asyncpg.Pool | None = None
        logger.info("PerformanceAgent initialized")

    async def get_pool(self) -> asyncpg.Pool:
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()

    async def analyze(self, state: Dict) -> Dict:
        """Analyze CWV performance and generate recommendations"""
        try:
            workflow_id = state['workflow_id']
            property_url = state['property']

            logger.info(f"Performance Agent analyzing: {property_url}")

            # Get poor performing pages
            poor_pages = await self._get_poor_cwv_pages(property_url)
            opportunities = await self._get_optimization_opportunities(property_url)

            recommendations = []

            # Generate recommendations for poor pages
            for page in poor_pages:
                if page['lcp'] and page['lcp'] > 2500:
                    recommendations.append({
                        'type': 'optimize_lcp',
                        'priority': 'high' if page['lcp'] > 4000 else 'medium',
                        'confidence': 0.90,
                        'estimated_impact': 'high',
                        'page_path': page['page_path'],
                        'details': {'lcp': page['lcp'], 'target': 2500},
                        'action': f"Optimize LCP for {page['page_path']} (current: {page['lcp']}ms)",
                        'reasoning': f"LCP exceeds threshold by {page['lcp'] - 2500}ms"
                    })

                if page['cls'] and page['cls'] > 0.1:
                    recommendations.append({
                        'type': 'fix_cls',
                        'priority': 'high' if page['cls'] > 0.25 else 'medium',
                        'confidence': 0.85,
                        'estimated_impact': 'high',
                        'page_path': page['page_path'],
                        'details': {'cls': page['cls'], 'target': 0.1},
                        'action': f"Fix layout shifts for {page['page_path']} (CLS: {page['cls']})",
                        'reasoning': f"CLS exceeds threshold"
                    })

            # Add top opportunities
            for opp in opportunities[:5]:
                recommendations.append({
                    'type': 'implement_opportunity',
                    'priority': 'medium',
                    'confidence': 0.75,
                    'estimated_impact': 'medium',
                    'opportunity': opp.get('opportunity_title'),
                    'savings_ms': opp.get('savings_ms'),
                    'details': opp,
                    'action': f"Implement: {opp.get('opportunity_title')}",
                    'reasoning': f"Potential savings: {opp.get('savings_ms')}ms"
                })

            await self._record_decision(workflow_id, property_url, recommendations)

            return {
                'agent': 'performance_agent',
                'status': 'completed',
                'poor_pages': len(poor_pages),
                'opportunities': len(opportunities),
                'recommendations': recommendations,
                'summary': f"Analyzed performance for {len(poor_pages)} pages, found {len(recommendations)} optimizations"
            }

        except Exception as e:
            logger.error(f"Error in performance analysis: {e}")
            return {
                'agent': 'performance_agent',
                'status': 'failed',
                'error': str(e),
                'recommendations': []
            }

    async def _get_poor_cwv_pages(self, property_url: str) -> List[Dict]:
        """Get pages with poor CWV scores"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM performance.vw_poor_cwv
                    WHERE property = $1
                    LIMIT 20
                """, property_url)
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting poor CWV pages: {e}")
            return []

    async def _get_optimization_opportunities(self, property_url: str) -> List[Dict]:
        """Get optimization opportunities from Lighthouse"""
        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        page_path,
                        jsonb_array_elements(opportunities) as opportunity
                    FROM performance.core_web_vitals
                    WHERE property = $1
                        AND check_date = (SELECT MAX(check_date) FROM performance.core_web_vitals WHERE property = $1)
                        AND opportunities IS NOT NULL
                    LIMIT 20
                """, property_url)

                opportunities = []
                for row in rows:
                    opp = row['opportunity']
                    opportunities.append({
                        'page_path': row['page_path'],
                        'opportunity_title': opp.get('title'),
                        'savings_ms': opp.get('overallSavingsMs', 0)
                    })

                return sorted(opportunities, key=lambda x: x.get('savings_ms', 0), reverse=True)
        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return []

    async def _record_decision(self, workflow_id: str, property_url: str, recommendations: List[Dict]):
        """Record decision in database"""
        try:
            pool = await self.get_pool()
            confidences = [r.get('confidence', 0.5) for r in recommendations]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO orchestration.agent_decisions (
                        workflow_id, agent_name, decision_type, decision, reasoning,
                        confidence, recommendations, priority, property
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                    workflow_id,
                    'performance_agent',
                    'analyze_cwv_performance',
                    f"Found {len(recommendations)} performance optimizations",
                    f"Analyzed CWV metrics and identified {len(recommendations)} improvements",
                    avg_confidence,
                    recommendations,
                    'high' if any(r.get('priority') == 'high' for r in recommendations) else 'medium',
                    property_url
                )
        except Exception as e:
            logger.error(f"Error recording decision: {e}")


__all__ = ['PerformanceAgent']
