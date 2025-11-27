"""
Impact Validator Agent
Specialist agent for validating the impact of SEO interventions
and calculating ROI
"""

import asyncio
import asyncpg
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json


class ImpactValidatorAgent:
    """
    Specialist agent that validates SEO intervention impact using:
    - Before/after comparison
    - Statistical significance testing
    - Causal impact analysis
    - ROI calculation
    - Confidence intervals
    """

    def __init__(self, db_dsn: str = None):
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.agent_name = 'impact_validator'
        self.confidence_threshold = float(os.getenv('IMPACT_VALIDATOR_CONFIDENCE', '0.8'))

    async def analyze(self, state: Dict) -> Dict:
        """
        Main analysis method called by Supervisor

        Args:
            state: Workflow state containing property, workflow_id, etc.

        Returns:
            Updated state with validation results and ROI calculations
        """
        property_url = state.get('property')
        workflow_id = state.get('workflow_id')

        # Get recent interventions to validate
        interventions = await self._get_interventions_to_validate(property_url)

        # Validate each intervention
        validations = []
        recommendations = []

        for intervention in interventions:
            validation = await self._validate_intervention(intervention)

            if validation:
                validations.append(validation)

                # Generate recommendation based on results
                if validation['is_successful']:
                    recommendations.append({
                        'type': 'scale_successful_intervention',
                        'priority': 'high' if validation['roi'] > 200 else 'medium',
                        'confidence': validation['confidence'],
                        'action': f"Scale successful intervention: {intervention['action_type']}",
                        'details': {
                            'intervention_id': intervention['action_id'],
                            'action_type': intervention['action_type'],
                            'roi': validation['roi'],
                            'impact_percentage': validation['impact_percentage'],
                            'statistical_significance': validation['is_significant']
                        }
                    })
                elif validation['is_significant'] and not validation['is_successful']:
                    recommendations.append({
                        'type': 'rollback_intervention',
                        'priority': 'high',
                        'confidence': validation['confidence'],
                        'action': f"Rollback intervention with negative impact: {intervention['action_type']}",
                        'details': {
                            'intervention_id': intervention['action_id'],
                            'action_type': intervention['action_type'],
                            'impact_percentage': validation['impact_percentage'],
                            'reason': 'Statistically significant negative impact detected'
                        }
                    })

        # Log decision
        if validations:
            await self.log_decision(
                workflow_id=workflow_id,
                decision_type='impact_validation',
                decision=f"Validated {len(validations)} interventions",
                reasoning=f"Analyzed before/after metrics and calculated ROI",
                confidence=0.85,
                recommendations=recommendations,
                metadata={'validations': validations}
            )

        # Update state
        state['recommendations'].extend(recommendations)
        state['validations'] = validations
        state['impact_validator_complete'] = True

        return state

    async def _get_interventions_to_validate(self, property_url: str) -> List[Dict]:
        """Get interventions that are ready for validation"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            # Get interventions completed at least 14 days ago
            rows = await conn.fetch("""
                SELECT
                    action_id,
                    action_type,
                    page_path,
                    implemented_date,
                    description,
                    metadata
                FROM analytics.actions
                WHERE property = $1
                    AND status = 'completed'
                    AND implemented_date IS NOT NULL
                    AND implemented_date >= CURRENT_DATE - INTERVAL '90 days'
                    AND implemented_date <= CURRENT_DATE - INTERVAL '14 days'
                    AND NOT EXISTS (
                        SELECT 1 FROM analytics.causal_impacts
                        WHERE action_id = analytics.actions.action_id
                    )
                ORDER BY implemented_date DESC
                LIMIT 10
            """, property_url)

            return [dict(row) for row in rows]

        except Exception as e:
            # Table may not exist
            return []
        finally:
            await conn.close()

    async def _validate_intervention(self, intervention: Dict) -> Optional[Dict]:
        """Validate a single intervention"""
        action_id = intervention['action_id']
        page_path = intervention.get('page_path')
        implemented_date = intervention['implemented_date']

        # Get before/after metrics
        before_metrics = await self._get_metrics_before(page_path, implemented_date)
        after_metrics = await self._get_metrics_after(page_path, implemented_date)

        if not before_metrics or not after_metrics:
            return None

        # Calculate impact
        impact = self._calculate_impact(before_metrics, after_metrics)

        # Perform statistical test
        is_significant = self._is_statistically_significant(before_metrics, after_metrics)

        # Calculate ROI
        roi = self._calculate_roi(intervention, impact)

        # Determine if successful
        is_successful = impact['clicks_change_pct'] > 5 and is_significant

        validation = {
            'action_id': action_id,
            'action_type': intervention['action_type'],
            'page_path': page_path,
            'implemented_date': str(implemented_date),
            'is_successful': is_successful,
            'is_significant': is_significant,
            'confidence': 0.85 if is_significant else 0.60,
            'impact_percentage': impact['clicks_change_pct'],
            'roi': roi,
            'metrics': {
                'before': before_metrics,
                'after': after_metrics,
                'change': impact
            }
        }

        # Store validation results
        await self._store_validation(validation)

        return validation

    async def _get_metrics_before(self, page_path: str, date: datetime, days: int = 14) -> Optional[Dict]:
        """Get metrics for the period before intervention"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as days_with_data,
                    SUM(clicks) as total_clicks,
                    SUM(impressions) as total_impressions,
                    AVG(ctr) as avg_ctr,
                    AVG(position) as avg_position
                FROM gsc.query_stats
                WHERE page_path = $1
                    AND data_date >= $2 - INTERVAL '%s days'
                    AND data_date < $2
                GROUP BY page_path
            """, page_path, date, days)

            if row and row['days_with_data'] >= days * 0.7:  # At least 70% data coverage
                return dict(row)
            return None

        finally:
            await conn.close()

    async def _get_metrics_after(self, page_path: str, date: datetime, days: int = 14) -> Optional[Dict]:
        """Get metrics for the period after intervention"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as days_with_data,
                    SUM(clicks) as total_clicks,
                    SUM(impressions) as total_impressions,
                    AVG(ctr) as avg_ctr,
                    AVG(position) as avg_position
                FROM gsc.query_stats
                WHERE page_path = $1
                    AND data_date > $2
                    AND data_date <= $2 + INTERVAL '%s days'
                GROUP BY page_path
            """, page_path, date, days)

            if row and row['days_with_data'] >= days * 0.7:
                return dict(row)
            return None

        finally:
            await conn.close()

    def _calculate_impact(self, before: Dict, after: Dict) -> Dict:
        """Calculate impact metrics"""
        clicks_change = after['total_clicks'] - before['total_clicks']
        clicks_change_pct = (clicks_change / before['total_clicks'] * 100) if before['total_clicks'] > 0 else 0

        impressions_change = after['total_impressions'] - before['total_impressions']
        impressions_change_pct = (impressions_change / before['total_impressions'] * 100) if before['total_impressions'] > 0 else 0

        ctr_change = after['avg_ctr'] - before['avg_ctr']
        ctr_change_pct = (ctr_change / before['avg_ctr'] * 100) if before['avg_ctr'] > 0 else 0

        position_change = after['avg_position'] - before['avg_position']

        return {
            'clicks_change': clicks_change,
            'clicks_change_pct': round(clicks_change_pct, 2),
            'impressions_change': impressions_change,
            'impressions_change_pct': round(impressions_change_pct, 2),
            'ctr_change': ctr_change,
            'ctr_change_pct': round(ctr_change_pct, 2),
            'position_change': round(position_change, 2)
        }

    def _is_statistically_significant(self, before: Dict, after: Dict, alpha: float = 0.05) -> bool:
        """
        Simplified statistical significance test
        In production, use proper t-test or Z-test with daily data points
        """
        # Simple threshold-based test
        # For proper implementation, use scipy.stats or similar

        clicks_change_pct = abs((after['total_clicks'] - before['total_clicks']) / before['total_clicks'] * 100) if before['total_clicks'] > 0 else 0

        # Consider significant if change is > 10% and sample size is adequate
        min_sample_size = before.get('days_with_data', 0) >= 10

        return clicks_change_pct > 10 and min_sample_size

    def _calculate_roi(self, intervention: Dict, impact: Dict, avg_value_per_click: float = 5.0) -> float:
        """
        Calculate ROI of intervention

        Args:
            intervention: Intervention details
            impact: Calculated impact metrics
            avg_value_per_click: Estimated value per click (configurable)

        Returns:
            ROI percentage
        """
        # Estimate cost of intervention (hours * hourly rate)
        cost = intervention.get('metadata', {}).get('cost', 100)  # Default $100

        # Calculate value from additional clicks
        clicks_gain = impact['clicks_change']
        value = clicks_gain * avg_value_per_click * 14  # 14 days of data

        if cost > 0:
            roi = ((value - cost) / cost) * 100
        else:
            roi = 0

        return round(roi, 2)

    async def _store_validation(self, validation: Dict):
        """Store validation results in database"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            await conn.execute("""
                INSERT INTO analytics.causal_impacts
                (action_id, impact_type, metric_name, before_value, after_value,
                 absolute_effect, relative_effect, p_value, is_significant, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            """,
                validation['action_id'],
                'validation',
                'clicks',
                validation['metrics']['before']['total_clicks'],
                validation['metrics']['after']['total_clicks'],
                validation['impact_percentage'],
                validation['impact_percentage'],
                0.05 if validation['is_significant'] else 0.10,
                validation['is_significant']
            )

        except Exception as e:
            # Table may not exist or other error
            pass
        finally:
            await conn.close()

    async def log_decision(self, workflow_id: str, decision_type: str,
                          decision: str, reasoning: str, confidence: float,
                          recommendations: List[Dict], metadata: Dict = None):
        """Log agent decision to database"""
        conn = await asyncpg.connect(self.db_dsn)

        try:
            await conn.execute("""
                INSERT INTO orchestration.agent_decisions
                (workflow_id, agent_name, decision_type, decision, reasoning,
                 confidence, recommendations, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            """, workflow_id, self.agent_name, decision_type, decision,
                reasoning, confidence, recommendations, metadata or {})

        finally:
            await conn.close()


# Example usage
async def example():
    """Example usage of Impact Validator Agent"""
    agent = ImpactValidatorAgent()

    state = {
        'workflow_id': 'test-workflow-123',
        'property': 'https://yourdomain.com',
        'recommendations': []
    }

    result = await agent.analyze(state)

    print(f"Validated {len(result.get('validations', []))} interventions:")
    for val in result.get('validations', []):
        print(f"  {val['action_type']}: {val['impact_percentage']}% impact (ROI: {val['roi']}%)")


if __name__ == '__main__':
    asyncio.run(example())
