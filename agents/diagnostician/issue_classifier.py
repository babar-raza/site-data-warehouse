"""Issue classification for categorizing and prioritizing problems."""

from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class IssueClassification:
    """Classification of an issue."""
    category: str
    subcategory: str
    priority: str  # 'critical', 'high', 'medium', 'low'
    impact_score: float
    urgency_score: float
    tags: List[str]
    affected_metrics: List[str]


class IssueClassifier:
    """Classifies issues into categories and priorities."""

    # Issue category taxonomy
    CATEGORIES = {
        'technical_seo': [
            'indexing',
            'crawlability',
            'site_speed',
            'mobile_optimization',
            'structured_data',
            'canonical_issues'
        ],
        'content': [
            'quality',
            'relevance',
            'freshness',
            'depth',
            'cannibalization',
            'thin_content'
        ],
        'on_page': [
            'title_optimization',
            'meta_description',
            'headers',
            'internal_linking',
            'keyword_optimization'
        ],
        'user_experience': [
            'navigation',
            'design',
            'engagement',
            'bounce_rate',
            'session_duration'
        ],
        'conversion': [
            'funnel_issues',
            'cta_optimization',
            'form_optimization',
            'trust_signals'
        ],
        'external': [
            'competition',
            'algorithm_updates',
            'seasonality',
            'market_changes'
        ]
    }

    def __init__(self):
        """Initialize issue classifier."""
        pass

    def classify_issue(
        self,
        root_cause_type: str,
        metrics: Dict[str, float],
        evidence: Dict[str, any]
    ) -> IssueClassification:
        """Classify an issue based on root cause and evidence.
        
        Args:
            root_cause_type: Type of root cause identified
            metrics: Affected metrics
            evidence: Supporting evidence
            
        Returns:
            IssueClassification object
        """
        # Determine category and subcategory
        category, subcategory = self._categorize_root_cause(root_cause_type)
        
        # Calculate impact score
        impact_score = self._calculate_impact(metrics, evidence)
        
        # Calculate urgency score
        urgency_score = self._calculate_urgency(root_cause_type, metrics)
        
        # Determine priority
        priority = self._determine_priority(impact_score, urgency_score)
        
        # Generate tags
        tags = self._generate_tags(root_cause_type, category, subcategory, evidence)
        
        # Identify affected metrics
        affected_metrics = list(metrics.keys())
        
        return IssueClassification(
            category=category,
            subcategory=subcategory,
            priority=priority,
            impact_score=impact_score,
            urgency_score=urgency_score,
            tags=tags,
            affected_metrics=affected_metrics
        )

    def _categorize_root_cause(self, root_cause_type: str) -> tuple:
        """Categorize root cause into category and subcategory.
        
        Args:
            root_cause_type: Root cause type
            
        Returns:
            Tuple of (category, subcategory)
        """
        mapping = {
            'position_drop': ('on_page', 'keyword_optimization'),
            'ctr_decline': ('on_page', 'title_optimization'),
            'seasonality': ('external', 'seasonality'),
            'high_bounce_rate': ('user_experience', 'engagement'),
            'low_engagement': ('user_experience', 'engagement'),
            'short_session_duration': ('user_experience', 'engagement'),
            'conversion_funnel_blocker': ('conversion', 'funnel_issues'),
            'traffic_quality_issue': ('content', 'relevance'),
            'deindexing_or_penalty': ('technical_seo', 'indexing'),
            'crawl_errors': ('technical_seo', 'crawlability'),
            'slow_page_load': ('technical_seo', 'site_speed'),
            'content_cannibalization': ('content', 'cannibalization'),
            'competitor_or_serp_change': ('external', 'competition'),
            'unknown': ('external', 'market_changes')
        }
        
        return mapping.get(root_cause_type, ('external', 'market_changes'))

    def _calculate_impact(
        self,
        metrics: Dict[str, float],
        evidence: Dict[str, any]
    ) -> float:
        """Calculate impact score (0-10).
        
        Args:
            metrics: Affected metrics
            evidence: Supporting evidence
            
        Returns:
            Impact score
        """
        impact = 0.0
        
        # Traffic impact
        clicks = metrics.get('clicks', 0)
        if clicks > 1000:
            impact += 3.0
        elif clicks > 100:
            impact += 2.0
        elif clicks > 10:
            impact += 1.0
        
        # Drop percentage impact
        if 'deviation_percent' in evidence:
            drop_pct = evidence['deviation_percent']
            if drop_pct > 50:
                impact += 3.0
            elif drop_pct > 30:
                impact += 2.0
            elif drop_pct > 10:
                impact += 1.0
        
        # Conversion impact
        if 'conversion_rate' in metrics and metrics['conversion_rate'] > 0:
            impact += 2.0
        
        # Position impact
        if 'avg_position' in metrics:
            position = metrics['avg_position']
            if position > 10:
                impact += 1.0
            elif position <= 3:
                impact += 0.5
        
        return min(10.0, impact)

    def _calculate_urgency(
        self,
        root_cause_type: str,
        metrics: Dict[str, float]
    ) -> float:
        """Calculate urgency score (0-10).
        
        Args:
            root_cause_type: Root cause type
            metrics: Affected metrics
            
        Returns:
            Urgency score
        """
        urgency = 5.0  # Base urgency
        
        # Critical issues need immediate attention
        critical_types = [
            'deindexing_or_penalty',
            'crawl_errors',
            'conversion_funnel_blocker'
        ]
        
        if root_cause_type in critical_types:
            urgency += 4.0
        
        # High urgency for major drops
        high_urgency_types = [
            'position_drop',
            'high_bounce_rate',
            'content_cannibalization'
        ]
        
        if root_cause_type in high_urgency_types:
            urgency += 2.0
        
        # Lower urgency for external factors
        low_urgency_types = [
            'seasonality',
            'competitor_or_serp_change'
        ]
        
        if root_cause_type in low_urgency_types:
            urgency -= 2.0
        
        return max(0.0, min(10.0, urgency))

    def _determine_priority(
        self,
        impact_score: float,
        urgency_score: float
    ) -> str:
        """Determine priority level.
        
        Args:
            impact_score: Impact score
            urgency_score: Urgency score
            
        Returns:
            Priority level
        """
        # Combined score
        combined = (impact_score * 0.6) + (urgency_score * 0.4)
        
        if combined >= 8.0:
            return 'critical'
        elif combined >= 6.0:
            return 'high'
        elif combined >= 4.0:
            return 'medium'
        else:
            return 'low'

    def _generate_tags(
        self,
        root_cause_type: str,
        category: str,
        subcategory: str,
        evidence: Dict[str, any]
    ) -> List[str]:
        """Generate tags for the issue.
        
        Args:
            root_cause_type: Root cause type
            category: Issue category
            subcategory: Issue subcategory
            evidence: Supporting evidence
            
        Returns:
            List of tags
        """
        tags = [category, subcategory, root_cause_type]
        
        # Add evidence-based tags
        if 'zero_impressions' in evidence:
            tags.append('no_visibility')
        
        if 'position_drop' in evidence or 'position_change' in evidence:
            tags.append('ranking_decline')
        
        if 'bounce_rate' in evidence:
            bounce = evidence.get('current_bounce_rate', 0)
            if bounce > 0.7:
                tags.append('high_bounce')
        
        if 'engagement_rate' in evidence:
            engagement = evidence.get('current_engagement_rate', 0)
            if engagement < 0.3:
                tags.append('low_engagement')
        
        if 'seasonal' in str(evidence).lower():
            tags.append('seasonal')
        
        if 'competitor' in str(evidence).lower():
            tags.append('competitive')
        
        # Remove duplicates
        return list(set(tags))

    def prioritize_issues(
        self,
        classifications: List[IssueClassification]
    ) -> List[IssueClassification]:
        """Prioritize multiple issues.
        
        Args:
            classifications: List of issue classifications
            
        Returns:
            Sorted list by priority
        """
        # Define priority order
        priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        
        # Sort by priority then by impact score
        sorted_issues = sorted(
            classifications,
            key=lambda c: (
                priority_order.get(c.priority, 4),
                -c.impact_score,
                -c.urgency_score
            )
        )
        
        return sorted_issues

    def get_quick_wins(
        self,
        classifications: List[IssueClassification]
    ) -> List[IssueClassification]:
        """Identify quick win opportunities.
        
        Args:
            classifications: List of issue classifications
            
        Returns:
            List of quick win issues
        """
        quick_wins = []
        
        # Quick wins: high impact, low urgency, specific categories
        for classification in classifications:
            # On-page and content issues are typically quicker to fix
            if classification.category in ['on_page', 'content']:
                if classification.impact_score >= 5.0:
                    if 'title_optimization' in [classification.subcategory]:
                        quick_wins.append(classification)
                    elif 'meta_description' in [classification.subcategory]:
                        quick_wins.append(classification)
        
        return quick_wins

    def identify_dependencies(
        self,
        classifications: List[IssueClassification]
    ) -> Dict[str, List[str]]:
        """Identify dependencies between issues.
        
        Args:
            classifications: List of issue classifications
            
        Returns:
            Dict mapping issue to dependent issues
        """
        dependencies = {}
        
        # Technical SEO issues often need to be fixed first
        technical_issues = [
            c for c in classifications
            if c.category == 'technical_seo'
        ]
        
        content_issues = [
            c for c in classifications
            if c.category == 'content'
        ]
        
        # Technical issues should be fixed before content optimization
        for tech_issue in technical_issues:
            if tech_issue.priority in ['critical', 'high']:
                for content_issue in content_issues:
                    key = f"{content_issue.category}_{content_issue.subcategory}"
                    if key not in dependencies:
                        dependencies[key] = []
                    dependencies[key].append(
                        f"{tech_issue.category}_{tech_issue.subcategory}"
                    )
        
        return dependencies
