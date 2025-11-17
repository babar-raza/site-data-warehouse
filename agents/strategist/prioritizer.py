"""Prioritizer - Prioritizes recommendations based on multiple factors."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PrioritizationScore:
    """Prioritization score for a recommendation."""
    
    priority: int  # 1-5 (1=highest)
    score: float  # Overall score
    impact_score: float
    urgency_score: float
    effort_score: float
    roi_score: float
    ranking: int  # Overall ranking position


class Prioritizer:
    """Prioritizes recommendations using multi-factor scoring."""
    
    def __init__(
        self,
        impact_weight: float = 0.4,
        urgency_weight: float = 0.3,
        effort_weight: float = 0.2,
        roi_weight: float = 0.1
    ):
        """Initialize prioritizer.
        
        Args:
            impact_weight: Weight for impact factor
            urgency_weight: Weight for urgency factor
            effort_weight: Weight for effort factor (inverse)
            roi_weight: Weight for ROI factor
        """
        self.impact_weight = impact_weight
        self.urgency_weight = urgency_weight
        self.effort_weight = effort_weight
        self.roi_weight = roi_weight
    
    def prioritize_recommendations(
        self,
        recommendations: List[Dict],
        impact_estimates: Dict[int, any],
        diagnoses: Dict[int, Dict]
    ) -> List[PrioritizationScore]:
        """Prioritize recommendations.
        
        Args:
            recommendations: List of recommendation dictionaries
            impact_estimates: Dictionary mapping index to ImpactEstimate
            diagnoses: Dictionary mapping diagnosis_id to diagnosis data
            
        Returns:
            List of PrioritizationScore objects
        """
        scores = []
        
        for i, rec in enumerate(recommendations):
            impact_est = impact_estimates.get(i)
            diagnosis_id = rec.get('diagnosis_id')
            diagnosis = diagnoses.get(diagnosis_id, {})
            
            if not impact_est:
                continue
            
            score = self._calculate_score(rec, impact_est, diagnosis)
            scores.append((i, score))
        
        # Sort by score (descending)
        scores.sort(key=lambda x: x[1].score, reverse=True)
        
        # Assign rankings and priorities
        results = []
        for rank, (idx, score) in enumerate(scores, 1):
            score.ranking = rank
            score.priority = self._score_to_priority(score.score, rank, len(scores))
            results.append(score)
        
        return results
    
    def _calculate_score(
        self,
        recommendation: Dict,
        impact_estimate: any,
        diagnosis: Dict
    ) -> PrioritizationScore:
        """Calculate prioritization score."""
        # Impact score (0-1)
        impact_score = self._normalize_impact(impact_estimate.impact_level)
        
        # Urgency score (0-1) based on severity and confidence
        urgency_score = self._calculate_urgency(diagnosis, impact_estimate)
        
        # Effort score (0-1, inverse - lower effort = higher score)
        effort_score = self._normalize_effort(impact_estimate.estimated_effort_hours)
        
        # ROI score (0-1)
        roi_score = min(impact_estimate.roi_score / 5.0, 1.0)
        
        # Calculate weighted total
        total_score = (
            impact_score * self.impact_weight +
            urgency_score * self.urgency_weight +
            effort_score * self.effort_weight +
            roi_score * self.roi_weight
        )
        
        return PrioritizationScore(
            priority=0,  # Will be assigned later
            score=round(total_score, 3),
            impact_score=round(impact_score, 3),
            urgency_score=round(urgency_score, 3),
            effort_score=round(effort_score, 3),
            roi_score=round(roi_score, 3),
            ranking=0  # Will be assigned later
        )
    
    def _normalize_impact(self, impact_level: str) -> float:
        """Normalize impact level to score."""
        levels = {
            'high': 1.0,
            'medium': 0.6,
            'low': 0.3
        }
        return levels.get(impact_level, 0.5)
    
    def _calculate_urgency(self, diagnosis: Dict, impact_est: any) -> float:
        """Calculate urgency score."""
        # Base on severity
        severity = diagnosis.get('severity', 'medium')
        severity_scores = {
            'critical': 1.0,
            'high': 0.8,
            'medium': 0.5,
            'low': 0.3
        }
        
        severity_score = severity_scores.get(severity, 0.5)
        
        # Adjust by confidence
        confidence = diagnosis.get('confidence_score', 0.5)
        
        # Combine
        urgency = (severity_score * 0.7) + (confidence * 0.3)
        
        return min(urgency, 1.0)
    
    def _normalize_effort(self, effort_hours: int) -> float:
        """Normalize effort (inverse - lower effort = higher score)."""
        # Cap at 24 hours
        if effort_hours >= 24:
            return 0.1
        
        # Inverse scaling
        return max(0.1, 1.0 - (effort_hours / 24.0))
    
    def _score_to_priority(self, score: float, rank: int, total: int) -> int:
        """Convert score and rank to priority level (1-5)."""
        # Top 20% = Priority 1
        if rank <= max(1, int(total * 0.2)):
            return 1
        
        # Top 40% = Priority 2
        if rank <= max(1, int(total * 0.4)):
            return 2
        
        # Top 60% = Priority 3
        if rank <= max(1, int(total * 0.6)):
            return 3
        
        # Top 80% = Priority 4
        if rank <= max(1, int(total * 0.8)):
            return 4
        
        # Bottom 20% = Priority 5
        return 5
    
    def filter_by_priority(
        self,
        prioritized: List[PrioritizationScore],
        recommendations: List[Dict],
        max_priority: int = 3
    ) -> List[Dict]:
        """Filter recommendations by priority level.
        
        Args:
            prioritized: List of PrioritizationScore objects
            recommendations: Original recommendations list
            max_priority: Maximum priority to include (1-5)
            
        Returns:
            Filtered list of recommendations
        """
        filtered = []
        
        for score in prioritized:
            if score.priority <= max_priority and score.ranking < len(recommendations):
                # Find original recommendation by ranking
                for i, rec in enumerate(recommendations):
                    # Match by checking if this is the right index
                    if i == score.ranking - 1:
                        rec['priority'] = score.priority
                        rec['priority_score'] = score.score
                        filtered.append(rec)
                        break
        
        return filtered
    
    def group_by_type(
        self,
        recommendations: List[Dict],
        prioritized: List[PrioritizationScore]
    ) -> Dict[str, List[Dict]]:
        """Group recommendations by type with priority info.
        
        Args:
            recommendations: List of recommendations
            prioritized: List of PrioritizationScore objects
            
        Returns:
            Dictionary mapping type to list of recommendations
        """
        grouped = {}
        
        # Create lookup for priority scores
        score_lookup = {s.ranking - 1: s for s in prioritized}
        
        for i, rec in enumerate(recommendations):
            rec_type = rec.get('recommendation_type', 'other')
            
            # Add priority info if available
            if i in score_lookup:
                score = score_lookup[i]
                rec['priority'] = score.priority
                rec['priority_score'] = score.score
            
            if rec_type not in grouped:
                grouped[rec_type] = []
            
            grouped[rec_type].append(rec)
        
        return grouped
    
    def get_top_n(
        self,
        recommendations: List[Dict],
        prioritized: List[PrioritizationScore],
        n: int = 10
    ) -> List[Dict]:
        """Get top N recommendations.
        
        Args:
            recommendations: List of recommendations
            prioritized: List of PrioritizationScore objects
            n: Number of top recommendations to return
            
        Returns:
            List of top N recommendations
        """
        top_recs = []
        
        for score in prioritized[:n]:
            rank_idx = score.ranking - 1
            if rank_idx < len(recommendations):
                rec = recommendations[rank_idx].copy()
                rec['priority'] = score.priority
                rec['priority_score'] = score.score
                rec['ranking'] = score.ranking
                top_recs.append(rec)
        
        return top_recs
