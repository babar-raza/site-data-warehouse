"""Strategist Agent - Converts diagnoses into actionable recommendations."""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.base.llm_reasoner import ReasoningResult, RecommendationGenerator
from agents.strategist.impact_estimator import ImpactEstimator
from agents.strategist.prioritizer import Prioritizer
from agents.strategist.recommendation_engine import RecommendationEngine


@dataclass
class RecommendationResult:
    """Combined LLM + Rule-based recommendation result."""
    diagnosis_id: int
    recommendation_type: str
    action_items: Dict[str, Any]
    description: str
    expected_impact: str
    estimated_effort_hours: int
    priority: int
    confidence: float
    llm_analysis: Optional[Dict[str, Any]] = None
    rule_based_analysis: Optional[Dict[str, Any]] = None
    rationale: str = ""
    quick_wins: List[str] = field(default_factory=list)
    strategic_initiatives: List[str] = field(default_factory=list)
    metrics_to_monitor: List[str] = field(default_factory=list)
    used_llm: bool = False
    used_rule_fallback: bool = False


class StrategistAgent(AgentContract):
    """Agent that generates actionable recommendations from diagnoses."""

    # Confidence weights for hybrid LLM + rule-based approach
    LLM_CONFIDENCE_WEIGHT = 0.6
    RULE_CONFIDENCE_WEIGHT = 0.4

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
        self._recommendation_results: List[RecommendationResult] = []

        # LLM integration
        self.use_llm = config.get('use_llm', True)
        ollama_host = config.get('ollama_host')

        self.llm_reasoner = RecommendationGenerator(
            ollama_host=ollama_host,
            default_timeout=config.get('llm_timeout', 60.0),
            max_retries=config.get('llm_max_retries', 2)
        )

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

    async def recommend_with_llm(
        self,
        diagnosis_id: int
    ) -> List[RecommendationResult]:
        """Generate recommendations using hybrid LLM + rule-based approach.

        Primary method for recommendation generation that combines LLM insights
        with rule-based analysis for robust, actionable recommendations.

        Args:
            diagnosis_id: Diagnosis ID to generate recommendations for

        Returns:
            List of RecommendationResult objects with combined analysis
        """
        # Get diagnosis and context
        diagnosis = await self._get_diagnosis(diagnosis_id)

        if not diagnosis:
            return []

        finding_id = diagnosis.get('finding_id')
        finding = await self._get_finding(finding_id)

        if not finding:
            return []

        affected_pages = json.loads(finding.get('affected_pages', '[]'))

        if not affected_pages:
            return []

        page_path = affected_pages[0]

        # Get metrics for context
        current_metrics = await self._get_page_current_metrics(page_path)
        historical_metrics = await self._get_page_historical_metrics(page_path, days=30)

        # Run rule-based recommendations
        rule_based_recs = self._run_rule_based_recommendations(
            diagnosis, current_metrics, historical_metrics
        )

        # Run LLM recommendations if enabled
        llm_result = None
        if self.use_llm:
            llm_result = self._run_llm_recommendations(
                diagnosis, current_metrics, historical_metrics, page_path
            )

        # Combine results
        if llm_result and llm_result.success:
            results = self._combine_llm_rule_results(
                diagnosis_id, diagnosis, rule_based_recs, llm_result, current_metrics
            )
        else:
            # Fallback to rule-based only
            results = self._apply_rule_fallback(
                diagnosis_id, diagnosis, rule_based_recs, current_metrics
            )

        self._recommendation_results.extend(results)
        return results

    def _run_rule_based_recommendations(
        self,
        diagnosis: Dict[str, Any],
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """Run traditional rule-based recommendation generation.

        Args:
            diagnosis: Diagnosis data
            current_metrics: Current page metrics
            historical_metrics: Historical page metrics

        Returns:
            List of rule-based recommendation dictionaries
        """
        recommendations = self.recommendation_engine.generate_recommendations(
            diagnosis,
            current_metrics,
            historical_metrics
        )

        rec_dicts = []
        for rec in recommendations:
            impact_est = self.impact_estimator.estimate_impact(
                rec.recommendation_type,
                diagnosis,
                current_metrics,
                historical_metrics
            )

            rec_dict = {
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

        return rec_dicts

    def _run_llm_recommendations(
        self,
        diagnosis: Dict[str, Any],
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        page_path: str
    ) -> Optional[ReasoningResult]:
        """Run LLM-based recommendation generation.

        Args:
            diagnosis: Diagnosis data
            current_metrics: Current page metrics
            historical_metrics: Historical page metrics
            page_path: Path of affected page

        Returns:
            ReasoningResult from LLM or None if unavailable
        """
        # Format context for LLM
        context, diagnosis_text, goals, constraints = self._format_context_for_llm(
            diagnosis, current_metrics, historical_metrics, page_path
        )

        # Generate additional info
        additional_info = ""
        if historical_metrics:
            avg_clicks = sum(m.get('clicks', 0) for m in historical_metrics) / len(historical_metrics)
            additional_info = f"\nHistorical average clicks: {avg_clicks:.0f}"

        return self.llm_reasoner.analyze(
            context=context,
            diagnosis=diagnosis_text,
            goals=goals,
            constraints=constraints,
            additional_info=additional_info
        )

    def _format_context_for_llm(
        self,
        diagnosis: Dict[str, Any],
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        page_path: str
    ) -> tuple:
        """Format diagnosis and metrics context for LLM consumption.

        Args:
            diagnosis: Diagnosis data
            current_metrics: Current page metrics
            historical_metrics: Historical page metrics
            page_path: Path of affected page

        Returns:
            Tuple of (context, diagnosis_text, goals, constraints)
        """
        # Build context string
        context_parts = [f"Page: {page_path}"]

        if current_metrics:
            metrics_str = ", ".join(
                f"{k}: {v}" for k, v in current_metrics.items()
                if v is not None and k not in ['date']
            )
            context_parts.append(f"Current metrics: {metrics_str}")

        context = ". ".join(context_parts)

        # Build diagnosis text
        root_cause = diagnosis.get('root_cause', 'Unknown')
        confidence = diagnosis.get('confidence_score', 0.5)
        evidence = diagnosis.get('supporting_evidence', {})

        diagnosis_text = f"Root cause: {root_cause} (confidence: {confidence:.0%})"
        if evidence:
            if isinstance(evidence, dict):
                evidence_str = ", ".join(f"{k}: {v}" for k, v in evidence.items())
            else:
                evidence_str = str(evidence)
            diagnosis_text += f". Evidence: {evidence_str}"

        # Determine goals based on diagnosis
        goals_map = {
            'position_drop': "Recover search rankings and organic traffic",
            'ctr_decline': "Improve click-through rate and user engagement",
            'high_bounce_rate': "Reduce bounce rate and increase engagement",
            'zero_impression': "Restore visibility in search results",
            'traffic_drop': "Recover organic traffic volume"
        }
        goals = goals_map.get(root_cause, "Improve overall SEO performance")

        # Default constraints
        constraints = "Limited engineering resources. Prioritize quick wins with high ROI."

        return context, diagnosis_text, goals, constraints

    def _combine_llm_rule_results(
        self,
        diagnosis_id: int,
        diagnosis: Dict[str, Any],
        rule_based_recs: List[Dict[str, Any]],
        llm_result: ReasoningResult,
        current_metrics: Dict[str, float]
    ) -> List[RecommendationResult]:
        """Combine LLM and rule-based recommendation results.

        Uses weighted confidence scoring: 60% LLM, 40% rule-based.

        Args:
            diagnosis_id: Diagnosis ID
            diagnosis: Diagnosis data
            rule_based_recs: Rule-based recommendations
            llm_result: LLM reasoning result
            current_metrics: Current page metrics

        Returns:
            List of combined RecommendationResult objects
        """
        results = []
        llm_content = llm_result.content if isinstance(llm_result.content, dict) else {}

        # Extract LLM recommendations
        llm_recommendations = llm_content.get('recommendations', [])
        quick_wins = llm_content.get('quick_wins', [])
        strategic_initiatives = llm_content.get('strategic_initiatives', [])
        llm_reasoning = llm_content.get('reasoning', '')

        # Map priority strings to numbers
        priority_map = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
        effort_map = {'low': 2, 'medium': 4, 'high': 8}

        # Create combined results
        for i, rule_rec in enumerate(rule_based_recs):
            # Get corresponding LLM recommendation if available
            llm_rec = llm_recommendations[i] if i < len(llm_recommendations) else None

            # Calculate combined confidence
            rule_confidence = rule_rec.get('confidence', 0.5)
            llm_confidence = 0.7 if llm_rec else 0.0  # Default LLM confidence

            if llm_rec:
                combined_confidence = (
                    self.LLM_CONFIDENCE_WEIGHT * llm_confidence +
                    self.RULE_CONFIDENCE_WEIGHT * rule_confidence
                )
            else:
                combined_confidence = rule_confidence

            # Get impact and effort from LLM or rule-based
            if llm_rec:
                expected_impact = llm_rec.get('expected_impact', rule_rec.get('expected_impact', 'medium'))
                effort_str = llm_rec.get('effort', 'medium')
                effort_hours = effort_map.get(effort_str, rule_rec.get('estimated_effort_hours', 4))
                priority_str = llm_rec.get('priority', 'medium')
                priority = priority_map.get(priority_str, 3)
                metrics_to_monitor = llm_rec.get('metrics_to_monitor', [])
            else:
                expected_impact = rule_rec.get('expected_impact', 'medium')
                effort_hours = rule_rec.get('estimated_effort_hours', 4)
                priority = 3
                metrics_to_monitor = []

            # Build combined rationale
            rationale = rule_rec.get('rationale', '')
            if llm_reasoning:
                rationale = f"{rationale}. LLM insight: {llm_reasoning}"

            result = RecommendationResult(
                diagnosis_id=diagnosis_id,
                recommendation_type=rule_rec.get('recommendation_type', 'general'),
                action_items=rule_rec.get('action_items', {}),
                description=rule_rec.get('description', ''),
                expected_impact=expected_impact,
                estimated_effort_hours=effort_hours,
                priority=priority,
                confidence=combined_confidence,
                llm_analysis=llm_rec,
                rule_based_analysis=rule_rec,
                rationale=rationale,
                quick_wins=quick_wins,
                strategic_initiatives=strategic_initiatives,
                metrics_to_monitor=metrics_to_monitor,
                used_llm=True,
                used_rule_fallback=False
            )
            results.append(result)

        # Add LLM-only recommendations not covered by rules
        for j, llm_rec in enumerate(llm_recommendations[len(rule_based_recs):]):
            priority_str = llm_rec.get('priority', 'medium')
            effort_str = llm_rec.get('effort', 'medium')

            result = RecommendationResult(
                diagnosis_id=diagnosis_id,
                recommendation_type='llm_generated',
                action_items={'llm_action': {
                    'action': llm_rec.get('action', 'Review LLM recommendation'),
                    'steps': []
                }},
                description=llm_rec.get('action', ''),
                expected_impact=llm_rec.get('expected_impact', 'medium'),
                estimated_effort_hours=effort_map.get(effort_str, 4),
                priority=priority_map.get(priority_str, 3),
                confidence=0.7,
                llm_analysis=llm_rec,
                rule_based_analysis=None,
                rationale=llm_reasoning,
                quick_wins=quick_wins,
                strategic_initiatives=strategic_initiatives,
                metrics_to_monitor=llm_rec.get('metrics_to_monitor', []),
                used_llm=True,
                used_rule_fallback=False
            )
            results.append(result)

        return results

    def _apply_rule_fallback(
        self,
        diagnosis_id: int,
        diagnosis: Dict[str, Any],
        rule_based_recs: List[Dict[str, Any]],
        current_metrics: Dict[str, float]
    ) -> List[RecommendationResult]:
        """Apply fallback to rule-based recommendations when LLM unavailable.

        Args:
            diagnosis_id: Diagnosis ID
            diagnosis: Diagnosis data
            rule_based_recs: Rule-based recommendations
            current_metrics: Current page metrics

        Returns:
            List of RecommendationResult objects from rule-based only
        """
        results = []
        priority_map = {'high': 1, 'medium': 2, 'low': 3}

        for i, rec in enumerate(rule_based_recs):
            impact_str = rec.get('expected_impact', 'medium')
            priority = priority_map.get(impact_str, 2)

            result = RecommendationResult(
                diagnosis_id=diagnosis_id,
                recommendation_type=rec.get('recommendation_type', 'general'),
                action_items=rec.get('action_items', {}),
                description=rec.get('description', ''),
                expected_impact=rec.get('expected_impact', 'medium'),
                estimated_effort_hours=rec.get('estimated_effort_hours', 4),
                priority=priority,
                confidence=rec.get('confidence', 0.5),
                llm_analysis=None,
                rule_based_analysis=rec,
                rationale=rec.get('rationale', ''),
                quick_wins=[],
                strategic_initiatives=[],
                metrics_to_monitor=[],
                used_llm=False,
                used_rule_fallback=True
            )
            results.append(result)

        return results

    def get_llm_stats(self) -> Dict[str, Any]:
        """Get LLM usage statistics.

        Returns:
            Dictionary with LLM stats including calls, success rate, etc.
        """
        stats = self.llm_reasoner.get_stats()

        # Add recommendation-specific stats
        total_results = len(self._recommendation_results)
        llm_used = sum(1 for r in self._recommendation_results if r.used_llm)
        rule_fallback = sum(1 for r in self._recommendation_results if r.used_rule_fallback)

        stats['recommendation_stats'] = {
            'total_recommendations': total_results,
            'llm_recommendations': llm_used,
            'rule_fallback_recommendations': rule_fallback,
            'llm_usage_rate': llm_used / total_results if total_results > 0 else 0.0
        }

        return stats

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

        # Get LLM stats
        llm_stats = self.get_llm_stats()

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
                'recommendations_generated': len(self._recommendations),
                'llm_stats': llm_stats
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
