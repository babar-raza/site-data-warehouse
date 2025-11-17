"""Strategist Agent - Converts diagnoses into actionable recommendations."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.strategist.impact_estimator import ImpactEstimator
from agents.strategist.prioritizer import Prioritizer
from agents.strategist.recommendation_engine import RecommendationEngine


class StrategistAgent(AgentContract):
    """Agent that generates actionable recommendations from diagnoses."""

    def __init__(
        self,
        agent_id: str,
        db_config: Dict[str, str],
        config: Optional[Dict[str, any]] = None
    ):
        """Initialize strategist agent.
        
        Args:
            agent_id: Unique agent identifier
            db_config: Database configuration
            config: Optional agent configuration
        """
        super().__init__(agent_id, "strategist", config)
        
        self.db_config = db_config
        self._pool: Optional[asyncpg.Pool] = None
        
        # Initialize components
        self.recommendation_engine = RecommendationEngine()
        
        self.impact_estimator = ImpactEstimator()
        
        self.prioritizer = Prioritizer(
            impact_weight=config.get('impact_weight', 0.4),
            urgency_weight=config.get('urgency_weight', 0.3),
            effort_weight=config.get('effort_weight', 0.2),
            roi_weight=config.get('roi_weight', 0.1)
        )
        
        self._recommendations: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the strategist agent."""
        try:
            self._start_time = datetime.now()
            
            # Connect to database
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                user=self.db_config.get('user', 'gsc_user'),
                password=self.db_config.get('password', ''),
                database=self.db_config.get('database', 'gsc_warehouse'),
                min_size=2,
                max_size=10
            )
            
            self._set_status(AgentStatus.RUNNING)
            
            return True
        
        except Exception as e:
            print(f"Error initializing strategist agent: {e}")
            self._set_status(AgentStatus.ERROR)
            self._increment_error_count()
            return False

    async def process(self, input_data: Dict[str, any]) -> Dict[str, any]:
        """Process recommendation request.
        
        Args:
            input_data: Input containing diagnosis_id or batch parameters
            
        Returns:
            Processing results
        """
        try:
            diagnosis_id = input_data.get('diagnosis_id')
            batch_mode = input_data.get('batch', False)
            
            if diagnosis_id:
                recommendations = await self.generate_recommendations(diagnosis_id)
                self._increment_processed_count()
                
                return {
                    'status': 'success',
                    'diagnosis_id': diagnosis_id,
                    'recommendations': recommendations,
                    'agent_id': self.agent_id
                }
            elif batch_mode:
                results = await self.process_batch()
                
                return {
                    'status': 'success',
                    'processed': results['processed'],
                    'recommendations_generated': results['recommendations_generated'],
                    'agent_id': self.agent_id
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Missing diagnosis_id or batch flag',
                    'agent_id': self.agent_id
                }
        
        except Exception as e:
            self._increment_error_count()
            return {
                'status': 'error',
                'error': str(e),
                'agent_id': self.agent_id
            }

    async def generate_recommendations(
        self,
        diagnosis_id: int
    ) -> List[Dict[str, any]]:
        """Generate recommendations for a diagnosis.
        
        Args:
            diagnosis_id: Diagnosis ID to generate recommendations for
            
        Returns:
            List of recommendation dictionaries
        """
        # Get diagnosis
        diagnosis = await self._get_diagnosis(diagnosis_id)
        
        if not diagnosis:
            return []
        
        # Get metrics for the diagnosed page
        finding_id = diagnosis.get('finding_id')
        finding = await self._get_finding(finding_id)
        
        if not finding:
            return []
        
        affected_pages = json.loads(finding.get('affected_pages', '[]'))
        
        if not affected_pages:
            return []
        
        page_path = affected_pages[0]
        
        # Get current and historical metrics
        current_metrics = await self._get_page_current_metrics(page_path)
        historical_metrics = await self._get_page_historical_metrics(page_path, days=30)
        
        # Generate recommendations
        recommendations = self.recommendation_engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )
        
        # Convert to dictionaries for storage
        rec_dicts = []
        
        for rec in recommendations:
            # Estimate impact
            impact_est = self.impact_estimator.estimate_impact(
                rec.recommendation_type,
                diagnosis,
                current_metrics,
                historical_metrics
            )
            
            rec_dict = {
                'diagnosis_id': diagnosis_id,
                'recommendation_type': rec.recommendation_type,
                'action_items': rec.action_items,
                'description': rec.description,
                'rationale': rec.rationale,
                'expected_impact': impact_est.impact_level,
                'expected_traffic_lift_pct': impact_est.traffic_lift_pct,
                'estimated_effort_hours': impact_est.estimated_effort_hours,
                'roi_score': impact_est.roi_score,
                'confidence': impact_est.confidence
            }
            
            rec_dicts.append(rec_dict)
        
        # Prioritize recommendations
        impact_estimates = {
            i: self.impact_estimator.estimate_impact(
                rec.recommendation_type,
                diagnosis,
                current_metrics,
                historical_metrics
            )
            for i, rec in enumerate(recommendations)
        }
        
        prioritized = self.prioritizer.prioritize_recommendations(
            rec_dicts,
            impact_estimates,
            {diagnosis_id: diagnosis}
        )
        
        # Add priority to recommendations
        for i, score in enumerate(prioritized):
            if score.ranking - 1 < len(rec_dicts):
                rec_dicts[score.ranking - 1]['priority'] = score.priority
                rec_dicts[score.ranking - 1]['priority_score'] = score.score
        
        # Store recommendations
        stored_recs = []
        for rec_dict in rec_dicts:
            rec_id = await self._store_recommendation(rec_dict)
            rec_dict['id'] = rec_id
            stored_recs.append(rec_dict)
            
            self._recommendations.append({
                'id': rec_id,
                'diagnosis_id': diagnosis_id,
                'type': rec_dict['recommendation_type'],
                'priority': rec_dict.get('priority', 5)
            })
        
        return stored_recs

    async def prioritize_all(self) -> Dict[str, any]:
        """Prioritize all unprocessed recommendations."""
        # Get all recommendations without priority
        query = """
            SELECT r.*, d.root_cause, d.confidence_score, d.supporting_evidence
            FROM gsc.agent_recommendations r
            JOIN gsc.agent_diagnoses d ON r.diagnosis_id = d.id
            WHERE r.priority IS NULL OR r.priority = 0
            ORDER BY r.recommended_at DESC
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query)
        
        recommendations = [dict(row) for row in rows]
        
        if not recommendations:
            return {
                'status': 'success',
                'prioritized': 0
            }
        
        # Build diagnosis map
        diagnosis_map = {}
        for rec in recommendations:
            diagnosis_id = rec['diagnosis_id']
            diagnosis_map[diagnosis_id] = {
                'root_cause': rec['root_cause'],
                'confidence_score': rec['confidence_score'],
                'supporting_evidence': rec['supporting_evidence'],
                'severity': 'medium'  # Default
            }
        
        # Build impact estimates
        impact_estimates = {}
        for i, rec in enumerate(recommendations):
            # Reconstruct impact estimate from stored data
            from agents.strategist.impact_estimator import ImpactEstimate
            
            impact_estimates[i] = ImpactEstimate(
                impact_level=rec.get('expected_impact', 'medium'),
                traffic_lift_pct=float(rec.get('expected_traffic_lift_pct', 0)),
                confidence=float(rec.get('confidence_score', 0.5)),
                estimated_effort_hours=int(rec.get('estimated_effort_hours', 4)),
                roi_score=float(rec.get('roi_score', 1.0)),
                factors={}
            )
        
        # Prioritize
        prioritized = self.prioritizer.prioritize_recommendations(
            recommendations,
            impact_estimates,
            diagnosis_map
        )
        
        # Update priorities in database
        update_count = 0
        for score in prioritized:
            rec_idx = score.ranking - 1
            if rec_idx < len(recommendations):
                rec = recommendations[rec_idx]
                
                update_query = """
                    UPDATE gsc.agent_recommendations
                    SET priority = $1,
                        metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb
                    WHERE id = $3
                """
                
                metadata = {
                    'priority_score': score.score,
                    'ranking': score.ranking
                }
                
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        update_query,
                        score.priority,
                        json.dumps(metadata),
                        rec['id']
                    )
                
                update_count += 1
        
        return {
            'status': 'success',
            'prioritized': update_count
        }

    async def generate_action_plan(
        self,
        top_n: int = 10,
        max_priority: int = 3
    ) -> Dict[str, any]:
        """Generate action plan with top recommendations.
        
        Args:
            top_n: Number of top recommendations to include
            max_priority: Maximum priority level to include
            
        Returns:
            Action plan dictionary
        """
        # Get top recommendations
        query = """
            SELECT r.*, d.root_cause, d.confidence_score,
                   f.affected_pages, f.metrics
            FROM gsc.agent_recommendations r
            JOIN gsc.agent_diagnoses d ON r.diagnosis_id = d.id
            JOIN gsc.agent_findings f ON d.finding_id = f.id
            WHERE r.priority <= $1
              AND r.implemented = FALSE
            ORDER BY r.priority ASC, r.recommended_at DESC
            LIMIT $2
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, max_priority, top_n)
        
        recommendations = [dict(row) for row in rows]
        
        # Group by type
        by_type = {}
        for rec in recommendations:
            rec_type = rec['recommendation_type']
            if rec_type not in by_type:
                by_type[rec_type] = []
            by_type[rec_type].append(rec)
        
        # Calculate totals
        total_effort = sum(rec.get('estimated_effort_hours', 0) for rec in recommendations)
        avg_lift = sum(rec.get('expected_traffic_lift_pct', 0) for rec in recommendations) / len(recommendations) if recommendations else 0
        
        return {
            'total_recommendations': len(recommendations),
            'by_type': {k: len(v) for k, v in by_type.items()},
            'total_effort_hours': total_effort,
            'estimated_effort_days': round(total_effort / 8, 1),
            'average_expected_lift_pct': round(avg_lift, 2),
            'recommendations': recommendations,
            'grouped_by_type': by_type
        }

    async def process_batch(self, batch_size: int = 50) -> Dict[str, any]:
        """Process batch of unprocessed diagnoses.
        
        Args:
            batch_size: Number of diagnoses to process
            
        Returns:
            Processing results
        """
        # Get unprocessed diagnoses
        query = """
            SELECT d.id
            FROM gsc.agent_diagnoses d
            LEFT JOIN gsc.agent_recommendations r ON d.id = r.diagnosis_id
            WHERE r.id IS NULL
              AND d.processed = TRUE
            ORDER BY d.diagnosed_at DESC
            LIMIT $1
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, batch_size)
        
        diagnosis_ids = [row['id'] for row in rows]
        
        processed = 0
        recommendations_generated = 0
        
        for diagnosis_id in diagnosis_ids:
            recs = await self.generate_recommendations(diagnosis_id)
            processed += 1
            recommendations_generated += len(recs)
            self._increment_processed_count()
        
        return {
            'processed': processed,
            'recommendations_generated': recommendations_generated
        }

    async def _get_diagnosis(self, diagnosis_id: int) -> Optional[Dict]:
        """Get diagnosis by ID."""
        query = """
            SELECT *
            FROM gsc.agent_diagnoses
            WHERE id = $1
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, diagnosis_id)
        
        if row:
            result = dict(row)
            # Parse JSON fields
            if result.get('supporting_evidence'):
                result['supporting_evidence'] = json.loads(result['supporting_evidence'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            return result
        
        return None

    async def _get_finding(self, finding_id: int) -> Optional[Dict]:
        """Get finding by ID."""
        query = """
            SELECT *
            FROM gsc.agent_findings
            WHERE id = $1
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, finding_id)
        
        return dict(row) if row else None

    async def _get_page_current_metrics(self, page_path: str) -> Dict[str, float]:
        """Get current metrics for a page."""
        query = """
            SELECT clicks, impressions, ctr, avg_position,
                   engagement_rate, conversion_rate, bounce_rate,
                   sessions, avg_session_duration
            FROM gsc.mv_unified_page_performance
            WHERE page_path = $1
            ORDER BY date DESC
            LIMIT 1
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, page_path)
        
        return dict(row) if row else {}

    async def _get_page_historical_metrics(
        self,
        page_path: str,
        days: int = 30
    ) -> List[Dict[str, float]]:
        """Get historical metrics for a page."""
        query = """
            SELECT date, clicks, impressions, ctr, avg_position,
                   engagement_rate, conversion_rate, bounce_rate,
                   sessions, avg_session_duration
            FROM gsc.mv_unified_page_performance
            WHERE page_path = $1
              AND date >= CURRENT_DATE - $2
            ORDER BY date ASC
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, page_path, days)
        
        return [dict(row) for row in rows]

    async def _store_recommendation(self, recommendation: Dict) -> int:
        """Store recommendation in database."""
        query = """
            INSERT INTO gsc.agent_recommendations (
                diagnosis_id, agent_name, recommendation_type, action_items,
                priority, estimated_effort_hours, expected_impact,
                expected_traffic_lift_pct, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
        """
        
        metadata = {
            'description': recommendation.get('description', ''),
            'rationale': recommendation.get('rationale', ''),
            'roi_score': recommendation.get('roi_score', 0),
            'confidence': recommendation.get('confidence', 0)
        }
        
        async with self._pool.acquire() as conn:
            rec_id = await conn.fetchval(
                query,
                recommendation['diagnosis_id'],
                self.agent_id,
                recommendation['recommendation_type'],
                json.dumps(recommendation['action_items']),
                recommendation.get('priority', 5),
                recommendation['estimated_effort_hours'],
                recommendation['expected_impact'],
                recommendation.get('expected_traffic_lift_pct', 0),
                json.dumps(metadata)
            )
        
        return rec_id

    async def health_check(self) -> AgentHealth:
        """Check agent health."""
        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return AgentHealth(
            agent_id=self.agent_id,
            status=self.status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={
                'recommendations_generated': len(self._recommendations)
            }
        )

    async def shutdown(self) -> bool:
        """Shutdown the agent."""
        try:
            if self._pool:
                await self._pool.close()
            
            self._set_status(AgentStatus.SHUTDOWN)
            
            return True
        
        except Exception as e:
            print(f"Error shutting down: {e}")
            return False


async def main():
    """CLI for strategist agent."""
    parser = argparse.ArgumentParser(description='Strategist Agent')
    parser.add_argument('--initialize', action='store_true', help='Initialize agent')
    parser.add_argument('--diagnose', action='store_true', help='Generate recommendations for diagnosis')
    parser.add_argument('--diagnosis-id', type=int, help='Diagnosis ID')
    parser.add_argument('--prioritize', action='store_true', help='Prioritize all recommendations')
    parser.add_argument('--action-plan', action='store_true', help='Generate action plan')
    parser.add_argument('--top', type=int, default=10, help='Top N recommendations for action plan')
    parser.add_argument('--batch', action='store_true', help='Process batch of diagnoses')
    parser.add_argument('--config', default='agents/strategist/config.yaml', help='Config file')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'user': 'gsc_user',
                'password': 'changeme',
                'database': 'gsc_warehouse'
            },
            'impact_weight': 0.4,
            'urgency_weight': 0.3,
            'effort_weight': 0.2,
            'roi_weight': 0.1
        }
    
    # Create agent
    agent = StrategistAgent(
        agent_id='strategist_001',
        db_config=config.get('database', {}),
        config=config
    )
    
    if args.initialize:
        print("Initializing strategist agent...")
        success = await agent.initialize()
        if success:
            print("✓ Strategist agent initialized")
        else:
            print("✗ Failed to initialize")
            return
    
    if args.diagnose and args.diagnosis_id:
        print(f"Generating recommendations for diagnosis {args.diagnosis_id}...")
        
        if not agent._pool:
            await agent.initialize()
        
        recommendations = await agent.generate_recommendations(args.diagnosis_id)
        
        if not recommendations:
            print("✗ No recommendations generated")
        else:
            print(f"✓ Generated {len(recommendations)} recommendations")
            
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. {rec['recommendation_type'].replace('_', ' ').title()}")
                print(f"   Priority: {rec.get('priority', 'N/A')}")
                print(f"   Impact: {rec['expected_impact']}")
                print(f"   Effort: {rec['estimated_effort_hours']} hours")
                print(f"   Expected Lift: {rec['expected_traffic_lift_pct']:.1f}%")
    
    if args.prioritize:
        print("Prioritizing recommendations...")
        
        if not agent._pool:
            await agent.initialize()
        
        result = await agent.prioritize_all()
        
        print(f"✓ Prioritized {result['prioritized']} recommendations")
    
    if args.action_plan:
        print(f"Generating action plan (top {args.top})...")
        
        if not agent._pool:
            await agent.initialize()
        
        plan = await agent.generate_action_plan(top_n=args.top)
        
        print(f"✓ Action plan generated")
        print(f"\nTotal Recommendations: {plan['total_recommendations']}")
        print(f"Estimated Effort: {plan['estimated_effort_days']} days")
        print(f"Average Expected Lift: {plan['average_expected_lift_pct']:.1f}%")
        
        print(f"\nBy Type:")
        for rec_type, count in plan['by_type'].items():
            print(f"  - {rec_type.replace('_', ' ').title()}: {count}")
    
    if args.batch:
        print("Processing batch of diagnoses...")
        
        if not agent._pool:
            await agent.initialize()
        
        result = await agent.process_batch()
        
        print(f"✓ Processed {result['processed']} diagnoses")
        print(f"✓ Generated {result['recommendations_generated']} recommendations")
    
    # Shutdown
    await agent.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
