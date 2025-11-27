"""
Content Optimizer Agent
Specialist agent for content quality analysis and optimization recommendations
"""

import asyncio
import asyncpg
import os
from typing import Dict, List, Any
from datetime import datetime, timedelta


class ContentOptimizerAgent:
    """
    Specialist agent that analyzes content quality and provides
    optimization recommendations based on:
    - Readability scores
    - Keyword optimization
    - Content gaps
    - Engagement metrics
    - Semantic relevance
    """

    def __init__(self, db_dsn: str = None):
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.agent_name = 'content_optimizer'
        self.confidence_threshold = float(os.getenv('CONTENT_OPTIMIZER_CONFIDENCE', '0.7'))

    async def analyze(self, state: Dict) -> Dict:
        """
        Main analysis method called by Supervisor

        Args:
            state: Workflow state containing property, workflow_id, etc.

        Returns:
            Updated state with content optimization recommendations
        """
        property_url = state.get('property')
        workflow_id = state.get('workflow_id')

        # Get content quality issues
        poor_content = await self._get_poor_quality_content(property_url)

        # Get underperforming content
        underperforming = await self._get_underperforming_content(property_url)

        # Get content gaps
        content_gaps = await self._identify_content_gaps(property_url)

        # Get keyword optimization opportunities
        keyword_opps = await self._get_keyword_opportunities(property_url)

        # Generate recommendations
        recommendations = []

        # Poor quality content
        for content in poor_content:
            recommendations.append({
                'type': 'improve_content_quality',
                'priority': 'high',
                'confidence': 0.85,
                'page_path': content['page_path'],
                'action': f"Improve content quality for '{content['page_path']}'",
                'details': {
                    'readability_score': content.get('readability_score'),
                    'word_count': content.get('word_count'),
                    'issues': self._diagnose_quality_issues(content)
                }
            })

        # Underperforming content with traffic
        for page in underperforming:
            if page['impressions'] > 100:  # Has visibility but poor CTR
                recommendations.append({
                    'type': 'optimize_for_ctr',
                    'priority': 'medium',
                    'confidence': 0.75,
                    'page_path': page['page_path'],
                    'action': f"Optimize title/meta for '{page['page_path']}' to improve CTR",
                    'details': {
                        'current_ctr': page['ctr'],
                        'impressions': page['impressions'],
                        'avg_position': page['avg_position']
                    }
                })

        # Content gaps
        for gap in content_gaps:
            recommendations.append({
                'type': 'fill_content_gap',
                'priority': 'medium',
                'confidence': 0.70,
                'action': f"Create content targeting '{gap['topic']}'",
                'details': {
                    'topic': gap['topic'],
                    'search_volume': gap.get('search_volume'),
                    'related_queries': gap.get('related_queries', [])
                }
            })

        # Keyword opportunities
        for opp in keyword_opps[:5]:  # Top 5 opportunities
            recommendations.append({
                'type': 'optimize_for_keyword',
                'priority': 'medium' if opp['position'] <= 15 else 'low',
                'confidence': 0.80,
                'page_path': opp['page_path'],
                'action': f"Optimize '{opp['page_path']}' for '{opp['query_text']}'",
                'details': {
                    'query': opp['query_text'],
                    'current_position': opp['position'],
                    'impressions': opp['impressions'],
                    'potential_gain': self._estimate_traffic_gain(opp)
                }
            })

        # Log decision
        if recommendations:
            await self.log_decision(
                workflow_id=workflow_id,
                decision_type='content_optimization',
                decision=f"Identified {len(recommendations)} content optimization opportunities",
                reasoning=f"Analyzed content quality, performance, and keyword opportunities",
                confidence=0.80,
                recommendations=recommendations
            )

        # Update state
        state['recommendations'].extend(recommendations)
        state['content_optimizer_complete'] = True

        return state

    async def _get_poor_quality_content(self, property_url: str) -> List[Dict]:
        """Get content with poor quality scores"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            rows = await conn.fetch("""
                SELECT
                    ca.page_path,
                    ca.readability_score,
                    ca.word_count,
                    ca.analyzed_at,
                    COALESCE(SUM(qs.impressions), 0) as impressions
                FROM content.content_analysis ca
                LEFT JOIN gsc.query_stats qs ON ca.page_path = qs.page_path
                    AND qs.data_date >= CURRENT_DATE - INTERVAL '30 days'
                WHERE ca.property = $1
                    AND ca.readability_score < 60
                    AND ca.analyzed_at >= CURRENT_DATE - INTERVAL '90 days'
                GROUP BY ca.page_path, ca.readability_score, ca.word_count, ca.analyzed_at
                HAVING COALESCE(SUM(qs.impressions), 0) > 100
                ORDER BY ca.readability_score ASC
                LIMIT 10
            """, property_url)

            return [dict(row) for row in rows]

        except Exception as e:
            # Table may not exist yet
            return []
        finally:
            await conn.close()

    async def _get_underperforming_content(self, property_url: str) -> List[Dict]:
        """Get content with low CTR despite high impressions"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            rows = await conn.fetch("""
                SELECT
                    page_path,
                    AVG(ctr) as ctr,
                    SUM(impressions) as impressions,
                    SUM(clicks) as clicks,
                    AVG(position) as avg_position
                FROM gsc.query_stats
                WHERE property = $1
                    AND data_date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY page_path
                HAVING SUM(impressions) > 1000
                    AND AVG(ctr) < 0.03
                ORDER BY SUM(impressions) DESC
                LIMIT 10
            """, property_url)

            return [dict(row) for row in rows]

        finally:
            await conn.close()

    async def _identify_content_gaps(self, property_url: str) -> List[Dict]:
        """Identify content gaps based on query data"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            # Find queries with high impressions but no dedicated page
            rows = await conn.fetch("""
                WITH query_aggregates AS (
                    SELECT
                        query_text,
                        SUM(impressions) as total_impressions,
                        AVG(position) as avg_position,
                        COUNT(DISTINCT page_path) as page_count
                    FROM gsc.query_stats
                    WHERE property = $1
                        AND data_date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY query_text
                )
                SELECT
                    query_text as topic,
                    total_impressions as search_volume,
                    avg_position,
                    page_count
                FROM query_aggregates
                WHERE total_impressions > 500
                    AND avg_position > 10
                    AND page_count <= 2
                ORDER BY total_impressions DESC
                LIMIT 5
            """, property_url)

            return [dict(row) for row in rows]

        finally:
            await conn.close()

    async def _get_keyword_opportunities(self, property_url: str) -> List[Dict]:
        """Get keyword optimization opportunities (ranking 11-20)"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            rows = await conn.fetch("""
                SELECT
                    query_text,
                    page_path,
                    AVG(position) as position,
                    SUM(impressions) as impressions,
                    SUM(clicks) as clicks,
                    AVG(ctr) as ctr
                FROM gsc.query_stats
                WHERE property = $1
                    AND data_date >= CURRENT_DATE - INTERVAL '30 days'
                    AND position BETWEEN 11 AND 20
                GROUP BY query_text, page_path
                HAVING SUM(impressions) > 100
                ORDER BY SUM(impressions) DESC, AVG(position) ASC
                LIMIT 20
            """, property_url)

            return [dict(row) for row in rows]

        finally:
            await conn.close()

    def _diagnose_quality_issues(self, content: Dict) -> List[str]:
        """Diagnose specific content quality issues"""
        issues = []

        readability = content.get('readability_score', 0)
        word_count = content.get('word_count', 0)

        if readability < 30:
            issues.append("Very low readability - content is too complex")
        elif readability < 50:
            issues.append("Low readability - simplify language")

        if word_count < 300:
            issues.append("Thin content - expand to at least 500 words")
        elif word_count < 500:
            issues.append("Content could be more comprehensive")

        return issues

    def _estimate_traffic_gain(self, opportunity: Dict) -> int:
        """Estimate potential traffic gain from optimization"""
        current_position = opportunity['position']
        impressions = opportunity['impressions']

        # Estimate position improvement (conservative: +3 positions)
        target_position = max(1, current_position - 3)

        # CTR curve (approximate)
        ctr_by_position = {
            1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.07,
            6: 0.05, 7: 0.04, 8: 0.03, 9: 0.03, 10: 0.02,
            11: 0.02, 12: 0.02, 13: 0.01, 14: 0.01, 15: 0.01
        }

        current_ctr = ctr_by_position.get(int(current_position), 0.01)
        target_ctr = ctr_by_position.get(int(target_position), current_ctr)

        current_clicks = impressions * current_ctr
        potential_clicks = impressions * target_ctr

        return int(potential_clicks - current_clicks)

    async def log_decision(self, workflow_id: str, decision_type: str,
                          decision: str, reasoning: str, confidence: float,
                          recommendations: List[Dict]):
        """Log agent decision to database"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            await conn.execute("""
                INSERT INTO orchestration.agent_decisions
                (workflow_id, agent_name, decision_type, decision, reasoning,
                 confidence, recommendations, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, workflow_id, self.agent_name, decision_type, decision,
                reasoning, confidence, recommendations)

        finally:
            await conn.close()


# Example usage
async def example():
    """Example usage of Content Optimizer Agent"""
    agent = ContentOptimizerAgent()

    state = {
        'workflow_id': 'test-workflow-123',
        'property': 'https://yourdomain.com',
        'recommendations': []
    }

    result = await agent.analyze(state)

    print(f"Generated {len(result['recommendations'])} recommendations:")
    for rec in result['recommendations']:
        print(f"  [{rec['priority']}] {rec['type']}: {rec['action']}")


if __name__ == '__main__':
    asyncio.run(example())
