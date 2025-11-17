"""Impact Estimator - Estimates expected impact of recommendations."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ImpactEstimate:
    """Impact estimate for a recommendation."""
    
    impact_level: str  # 'low', 'medium', 'high'
    traffic_lift_pct: float  # Expected traffic lift percentage
    confidence: float  # Confidence in estimate (0-1)
    estimated_effort_hours: int  # Effort required
    roi_score: float  # Return on investment score
    factors: Dict[str, float]  # Contributing factors


class ImpactEstimator:
    """Estimates impact of recommendations based on diagnosis and metrics."""
    
    def __init__(self):
        """Initialize impact estimator."""
        # Impact multipliers by recommendation type
        self.type_multipliers = {
            'content_optimization': 1.5,
            'internal_linking': 1.2,
            'technical_fixes': 2.0,
            'content_creation': 1.8,
            'content_pruning': 1.3,
            'ux_improvements': 1.4
        }
        
        # Effort estimates (hours) by recommendation type
        self.effort_estimates = {
            'content_optimization': 4,
            'internal_linking': 2,
            'technical_fixes': 8,
            'content_creation': 12,
            'content_pruning': 1,
            'ux_improvements': 6
        }
    
    def estimate_impact(
        self,
        recommendation_type: str,
        diagnosis: Dict,
        current_metrics: Dict,
        historical_metrics: List[Dict]
    ) -> ImpactEstimate:
        """Estimate impact of a recommendation.
        
        Args:
            recommendation_type: Type of recommendation
            diagnosis: Diagnosis information
            current_metrics: Current page metrics
            historical_metrics: Historical metrics
            
        Returns:
            ImpactEstimate object
        """
        confidence_score = diagnosis.get('confidence_score', 0.5)
        root_cause = diagnosis.get('root_cause', '')
        
        # Calculate base impact
        base_impact = self._calculate_base_impact(
            recommendation_type,
            root_cause,
            current_metrics,
            historical_metrics
        )
        
        # Apply confidence multiplier
        adjusted_impact = base_impact * confidence_score
        
        # Calculate traffic lift
        traffic_lift = self._estimate_traffic_lift(
            adjusted_impact,
            current_metrics,
            historical_metrics
        )
        
        # Determine impact level
        impact_level = self._categorize_impact(traffic_lift)
        
        # Calculate effort
        effort = self._estimate_effort(
            recommendation_type,
            diagnosis,
            current_metrics
        )
        
        # Calculate ROI score
        roi_score = (traffic_lift / 10.0) / (effort / 4.0) if effort > 0 else 0
        
        # Gather contributing factors
        factors = {
            'confidence': confidence_score,
            'severity': self._severity_score(diagnosis.get('severity', 'medium')),
            'current_performance': self._performance_score(current_metrics),
            'type_multiplier': self.type_multipliers.get(recommendation_type, 1.0)
        }
        
        return ImpactEstimate(
            impact_level=impact_level,
            traffic_lift_pct=round(traffic_lift, 2),
            confidence=round(confidence_score, 2),
            estimated_effort_hours=effort,
            roi_score=round(roi_score, 2),
            factors=factors
        )
    
    def _calculate_base_impact(
        self,
        rec_type: str,
        root_cause: str,
        current: Dict,
        historical: List[Dict]
    ) -> float:
        """Calculate base impact score."""
        # Start with type multiplier
        impact = self.type_multipliers.get(rec_type, 1.0)
        
        # Adjust based on root cause alignment
        if rec_type == 'content_optimization':
            if 'ctr' in root_cause.lower() or 'meta' in root_cause.lower():
                impact *= 1.5
            if 'engagement' in root_cause.lower():
                impact *= 1.3
        
        elif rec_type == 'technical_fixes':
            if 'zero_impression' in root_cause.lower() or 'crawl' in root_cause.lower():
                impact *= 1.8
            if 'mobile' in root_cause.lower() or 'speed' in root_cause.lower():
                impact *= 1.5
        
        elif rec_type == 'internal_linking':
            if 'position' in root_cause.lower() or 'authority' in root_cause.lower():
                impact *= 1.4
        
        # Adjust based on performance gap
        if historical:
            avg_clicks = sum(h.get('clicks', 0) for h in historical) / len(historical)
            current_clicks = current.get('clicks', 0)
            
            if avg_clicks > 0:
                performance_gap = (avg_clicks - current_clicks) / avg_clicks
                impact *= (1 + performance_gap)
        
        return impact
    
    def _estimate_traffic_lift(
        self,
        impact_score: float,
        current: Dict,
        historical: List[Dict]
    ) -> float:
        """Estimate traffic lift percentage."""
        if not historical:
            return impact_score * 10.0
        
        # Calculate historical average
        avg_clicks = sum(h.get('clicks', 0) for h in historical) / len(historical)
        current_clicks = current.get('clicks', 0)
        
        if current_clicks == 0:
            # If zero clicks, estimate based on impressions and impact
            impressions = current.get('impressions', 0)
            if impressions > 0:
                potential_clicks = impressions * 0.03 * impact_score
                return min(potential_clicks / 10, 100.0)
            return min(impact_score * 15.0, 100.0)
        
        # Calculate potential lift
        max_recovery = avg_clicks - current_clicks
        if max_recovery > 0:
            lift_pct = (max_recovery * impact_score / current_clicks) * 100
            return min(lift_pct, 100.0)
        
        # For improving pages, estimate smaller lift
        return min(impact_score * 8.0, 50.0)
    
    def _categorize_impact(self, traffic_lift: float) -> str:
        """Categorize impact level."""
        if traffic_lift >= 30.0:
            return 'high'
        elif traffic_lift >= 10.0:
            return 'medium'
        else:
            return 'low'
    
    def _estimate_effort(
        self,
        rec_type: str,
        diagnosis: Dict,
        current: Dict
    ) -> int:
        """Estimate effort in hours."""
        base_effort = self.effort_estimates.get(rec_type, 4)
        
        # Adjust based on complexity
        evidence = diagnosis.get('supporting_evidence', {})
        
        if isinstance(evidence, dict):
            classification = evidence.get('classification', {})
            if classification.get('priority') == 1:
                # High priority might need more thorough work
                base_effort = int(base_effort * 1.3)
        
        # Adjust for content size (if available)
        if rec_type in ['content_optimization', 'content_creation']:
            # Assume more content = more effort
            clicks = current.get('clicks', 0)
            if clicks > 1000:
                base_effort = int(base_effort * 1.5)
            elif clicks > 100:
                base_effort = int(base_effort * 1.2)
        
        return max(1, base_effort)
    
    def _severity_score(self, severity: str) -> float:
        """Convert severity to score."""
        scores = {
            'critical': 1.0,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }
        return scores.get(severity, 0.6)
    
    def _performance_score(self, metrics: Dict) -> float:
        """Calculate performance score from metrics."""
        ctr = metrics.get('ctr', 0)
        position = metrics.get('avg_position', 50)
        
        # Better CTR and position = higher score
        ctr_score = min(ctr / 5.0, 1.0)  # Normalize to max 5% CTR
        position_score = max(0, (50 - position) / 50)  # Top position = 1.0
        
        return (ctr_score + position_score) / 2
    
    def estimate_bulk_impact(
        self,
        recommendations: List[Dict],
        diagnosis_map: Dict[int, Dict],
        metrics_map: Dict[int, Dict]
    ) -> Dict[int, ImpactEstimate]:
        """Estimate impact for multiple recommendations.
        
        Args:
            recommendations: List of recommendation dicts
            diagnosis_map: Map of diagnosis_id to diagnosis data
            metrics_map: Map of diagnosis_id to metrics
            
        Returns:
            Dictionary mapping recommendation to ImpactEstimate
        """
        estimates = {}
        
        for i, rec in enumerate(recommendations):
            diagnosis_id = rec.get('diagnosis_id')
            diagnosis = diagnosis_map.get(diagnosis_id, {})
            metrics = metrics_map.get(diagnosis_id, {})
            
            current = metrics.get('current', {})
            historical = metrics.get('historical', [])
            
            estimate = self.estimate_impact(
                rec.get('recommendation_type', 'content_optimization'),
                diagnosis,
                current,
                historical
            )
            
            estimates[i] = estimate
        
        return estimates
