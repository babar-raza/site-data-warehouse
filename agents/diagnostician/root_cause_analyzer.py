"""Root cause analysis algorithms for diagnosing SEO/traffic issues."""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class RootCause:
    """Represents an identified root cause."""
    cause_type: str
    confidence: float
    evidence: Dict[str, any]
    recommendations: List[str]
    severity: str


class RootCauseAnalyzer:
    """Analyzes anomalies and identifies root causes."""

    def __init__(self, min_confidence: float = 0.6):
        """Initialize root cause analyzer.
        
        Args:
            min_confidence: Minimum confidence threshold
        """
        self.min_confidence = min_confidence

    def analyze_traffic_drop(
        self,
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        anomaly_context: Dict[str, any]
    ) -> Optional[RootCause]:
        """Analyze traffic drop and identify root cause.
        
        Args:
            current_metrics: Current metric values
            historical_metrics: Historical metric data
            anomaly_context: Context from anomaly detection
            
        Returns:
            RootCause if identified, None otherwise
        """
        causes = []
        
        # Check for position drop
        current_position = current_metrics.get('avg_position', 100)
        historical_positions = [m.get('avg_position', 100) for m in historical_metrics]
        
        if historical_positions:
            avg_hist_pos = statistics.mean(historical_positions)
            
            if current_position > avg_hist_pos + 3:
                position_drop = current_position - avg_hist_pos
                confidence = min(0.95, 0.6 + (position_drop / 20))
                
                causes.append(RootCause(
                    cause_type='position_drop',
                    confidence=confidence,
                    evidence={
                        'current_position': current_position,
                        'historical_avg_position': avg_hist_pos,
                        'position_change': position_drop,
                        'likely_reason': 'algorithm_update_or_competition'
                    },
                    recommendations=[
                        'Review recent algorithm updates',
                        'Analyze competitor content improvements',
                        'Check for technical SEO issues',
                        'Refresh and expand content'
                    ],
                    severity='high'
                ))
        
        # Check for CTR decline
        current_ctr = current_metrics.get('ctr', 0)
        historical_ctrs = [m.get('ctr', 0) for m in historical_metrics if m.get('ctr')]
        
        if historical_ctrs:
            avg_hist_ctr = statistics.mean(historical_ctrs)
            
            if current_ctr < avg_hist_ctr * 0.7 and current_position < avg_hist_pos + 2:
                ctr_drop_pct = ((avg_hist_ctr - current_ctr) / avg_hist_ctr) * 100
                confidence = min(0.9, 0.65 + (ctr_drop_pct / 100))
                
                causes.append(RootCause(
                    cause_type='ctr_decline',
                    confidence=confidence,
                    evidence={
                        'current_ctr': current_ctr,
                        'historical_avg_ctr': avg_hist_ctr,
                        'ctr_drop_percent': ctr_drop_pct,
                        'position_stable': True,
                        'likely_reason': 'title_meta_description_issue'
                    },
                    recommendations=[
                        'Update title tag to be more compelling',
                        'Rewrite meta description with clear value prop',
                        'Add schema markup for rich snippets',
                        'Review competitor snippets for ideas'
                    ],
                    severity='medium'
                ))
        
        # Check for seasonality
        if self._detect_seasonal_pattern(historical_metrics):
            causes.append(RootCause(
                cause_type='seasonality',
                confidence=0.75,
                evidence={
                    'pattern_detected': True,
                    'likely_reason': 'seasonal_search_behavior'
                },
                recommendations=[
                    'This appears to be seasonal - monitor for recovery',
                    'Prepare content for off-season queries',
                    'Consider seasonal PPC campaigns'
                ],
                severity='low'
            ))
        
        # Return highest confidence cause
        if causes:
            causes.sort(key=lambda c: c.confidence, reverse=True)
            return causes[0]
        
        return None

    def analyze_engagement_issue(
        self,
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        page_content: Optional[Dict[str, any]] = None
    ) -> Optional[RootCause]:
        """Analyze engagement issues and identify root cause.
        
        Args:
            current_metrics: Current metric values
            historical_metrics: Historical metric data
            page_content: Optional page content analysis
            
        Returns:
            RootCause if identified, None otherwise
        """
        causes = []
        
        # Check bounce rate
        current_bounce = current_metrics.get('bounce_rate', 0)
        historical_bounce = [m.get('bounce_rate', 0) for m in historical_metrics if m.get('bounce_rate')]
        
        if historical_bounce:
            avg_hist_bounce = statistics.mean(historical_bounce)
            
            if current_bounce > avg_hist_bounce * 1.2 and current_bounce > 0.6:
                confidence = min(0.85, 0.6 + ((current_bounce - avg_hist_bounce) / avg_hist_bounce))
                
                causes.append(RootCause(
                    cause_type='high_bounce_rate',
                    confidence=confidence,
                    evidence={
                        'current_bounce_rate': current_bounce,
                        'historical_avg_bounce_rate': avg_hist_bounce,
                        'bounce_increase_percent': ((current_bounce - avg_hist_bounce) / avg_hist_bounce) * 100,
                        'likely_reasons': ['poor_content_quality', 'slow_load_time', 'bad_ux']
                    },
                    recommendations=[
                        'Improve page load speed',
                        'Review content quality and relevance',
                        'Enhance visual design and readability',
                        'Add internal links and CTAs',
                        'Check mobile experience'
                    ],
                    severity='high'
                ))
        
        # Check engagement rate
        current_engagement = current_metrics.get('engagement_rate', 0)
        historical_engagement = [m.get('engagement_rate', 0) for m in historical_metrics if m.get('engagement_rate')]
        
        if historical_engagement:
            avg_hist_engagement = statistics.mean(historical_engagement)
            
            if current_engagement < avg_hist_engagement * 0.7:
                confidence = 0.75
                
                causes.append(RootCause(
                    cause_type='low_engagement',
                    confidence=confidence,
                    evidence={
                        'current_engagement_rate': current_engagement,
                        'historical_avg_engagement_rate': avg_hist_engagement,
                        'likely_reasons': ['content_not_engaging', 'ux_issues']
                    },
                    recommendations=[
                        'Add interactive elements',
                        'Improve content depth and quality',
                        'Add videos or rich media',
                        'Simplify navigation',
                        'Add clear next steps/CTAs'
                    ],
                    severity='medium'
                ))
        
        # Check avg session duration
        current_duration = current_metrics.get('avg_session_duration', 0)
        historical_duration = [m.get('avg_session_duration', 0) for m in historical_metrics if m.get('avg_session_duration')]
        
        if historical_duration:
            avg_hist_duration = statistics.mean(historical_duration)
            
            if current_duration < avg_hist_duration * 0.6 and current_duration < 60:
                causes.append(RootCause(
                    cause_type='short_session_duration',
                    confidence=0.7,
                    evidence={
                        'current_avg_duration': current_duration,
                        'historical_avg_duration': avg_hist_duration,
                        'likely_reasons': ['content_not_matching_intent', 'poor_content']
                    },
                    recommendations=[
                        'Better align content with search intent',
                        'Improve content depth and quality',
                        'Add engaging media',
                        'Improve readability'
                    ],
                    severity='medium'
                ))
        
        if causes:
            causes.sort(key=lambda c: c.confidence, reverse=True)
            return causes[0]
        
        return None

    def analyze_conversion_issue(
        self,
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        funnel_data: Optional[Dict[str, any]] = None
    ) -> Optional[RootCause]:
        """Analyze conversion issues and identify blockers.
        
        Args:
            current_metrics: Current metric values
            historical_metrics: Historical metric data
            funnel_data: Optional funnel analysis data
            
        Returns:
            RootCause if identified, None otherwise
        """
        causes = []
        
        current_conversion = current_metrics.get('conversion_rate', 0)
        historical_conversions = [m.get('conversion_rate', 0) for m in historical_metrics if m.get('conversion_rate')]
        
        if not historical_conversions:
            return None
        
        avg_hist_conversion = statistics.mean(historical_conversions)
        
        if current_conversion < avg_hist_conversion * 0.7:
            # Check engagement to determine if it's a funnel issue
            current_engagement = current_metrics.get('engagement_rate', 0)
            
            if current_engagement > 0.5:
                # High engagement but low conversion = funnel issue
                causes.append(RootCause(
                    cause_type='conversion_funnel_blocker',
                    confidence=0.8,
                    evidence={
                        'current_conversion_rate': current_conversion,
                        'historical_avg_conversion_rate': avg_hist_conversion,
                        'engagement_rate': current_engagement,
                        'likely_reasons': ['checkout_issues', 'form_friction', 'trust_signals_missing']
                    },
                    recommendations=[
                        'Simplify conversion form/checkout',
                        'Add trust signals (reviews, security badges)',
                        'Reduce form fields',
                        'Add live chat support',
                        'Optimize CTA placement and copy'
                    ],
                    severity='high'
                ))
            else:
                # Low engagement and low conversion = traffic quality issue
                causes.append(RootCause(
                    cause_type='traffic_quality_issue',
                    confidence=0.75,
                    evidence={
                        'current_conversion_rate': current_conversion,
                        'engagement_rate': current_engagement,
                        'likely_reasons': ['wrong_audience', 'misleading_snippets']
                    },
                    recommendations=[
                        'Review search intent alignment',
                        'Update title/meta to set correct expectations',
                        'Target more qualified keywords',
                        'Add qualification content early'
                    ],
                    severity='medium'
                ))
        
        if causes:
            return causes[0]
        
        return None

    def analyze_technical_issue(
        self,
        current_metrics: Dict[str, float],
        technical_data: Optional[Dict[str, any]] = None
    ) -> Optional[RootCause]:
        """Analyze potential technical SEO issues.
        
        Args:
            current_metrics: Current metric values
            technical_data: Optional technical audit data
            
        Returns:
            RootCause if identified, None otherwise
        """
        causes = []
        
        # Check for zero traffic (deindexing)
        if current_metrics.get('impressions', 0) == 0 and current_metrics.get('clicks', 0) == 0:
            causes.append(RootCause(
                cause_type='deindexing_or_penalty',
                confidence=0.9,
                evidence={
                    'zero_impressions': True,
                    'zero_clicks': True,
                    'likely_reasons': ['manual_action', 'noindex_tag', 'robots_txt_block']
                },
                recommendations=[
                    'Check Google Search Console for manual actions',
                    'Verify page is not blocked by robots.txt',
                    'Check for noindex meta tag',
                    'Verify sitemap includes URL',
                    'Request reindexing'
                ],
                severity='critical'
            ))
        
        # Check for crawl errors from technical data
        if technical_data and technical_data.get('crawl_errors', 0) > 0:
            causes.append(RootCause(
                cause_type='crawl_errors',
                confidence=0.85,
                evidence={
                    'crawl_errors': technical_data.get('crawl_errors'),
                    'error_types': technical_data.get('error_types', [])
                },
                recommendations=[
                    'Fix crawl errors in Search Console',
                    'Check server logs for errors',
                    'Verify canonical tags',
                    'Fix broken internal links'
                ],
                severity='high'
            ))
        
        # Check for slow load times
        if technical_data and technical_data.get('page_load_time', 0) > 3:
            causes.append(RootCause(
                cause_type='slow_page_load',
                confidence=0.75,
                evidence={
                    'page_load_time': technical_data.get('page_load_time'),
                    'target_time': 2.5
                },
                recommendations=[
                    'Optimize images',
                    'Minimize JavaScript',
                    'Enable compression',
                    'Use CDN',
                    'Implement lazy loading'
                ],
                severity='medium'
            ))
        
        if causes:
            causes.sort(key=lambda c: c.confidence, reverse=True)
            return causes[0]
        
        return None

    def detect_cannibalization(
        self,
        page_path: str,
        similar_pages: List[Dict[str, any]],
        shared_keywords: List[str]
    ) -> Optional[RootCause]:
        """Detect content cannibalization issues.
        
        Args:
            page_path: Current page path
            similar_pages: List of similar pages
            shared_keywords: Keywords shared between pages
            
        Returns:
            RootCause if cannibalization detected, None otherwise
        """
        if len(similar_pages) < 2 or len(shared_keywords) < 3:
            return None
        
        # Calculate overlap percentage
        total_keywords_page = len(shared_keywords) * len(similar_pages)
        overlap_score = len(shared_keywords) / max(10, total_keywords_page) * 100
        
        if overlap_score > 30:
            confidence = min(0.9, 0.6 + (overlap_score / 100))
            
            return RootCause(
                cause_type='content_cannibalization',
                confidence=confidence,
                evidence={
                    'similar_pages_count': len(similar_pages),
                    'shared_keywords_count': len(shared_keywords),
                    'overlap_score': overlap_score,
                    'similar_pages': [p.get('page_path') for p in similar_pages]
                },
                recommendations=[
                    'Consolidate similar content into one comprehensive page',
                    'Use canonical tags to indicate preferred version',
                    'Differentiate content with unique angles',
                    '301 redirect duplicate pages to primary page',
                    'Update internal links to point to primary page'
                ],
                severity='high'
            )
        
        return None

    def analyze_competitor_impact(
        self,
        current_metrics: Dict[str, float],
        historical_metrics: List[Dict[str, float]],
        competitor_data: Optional[Dict[str, any]] = None
    ) -> Optional[RootCause]:
        """Analyze potential competitor impact.
        
        Args:
            current_metrics: Current metric values
            historical_metrics: Historical metric data
            competitor_data: Optional competitor analysis data
            
        Returns:
            RootCause if competitor impact detected, None otherwise
        """
        # Check for sudden impression loss with stable position
        current_impressions = current_metrics.get('impressions', 0)
        current_position = current_metrics.get('avg_position', 100)
        
        historical_impressions = [m.get('impressions', 0) for m in historical_metrics]
        historical_positions = [m.get('avg_position', 100) for m in historical_metrics]
        
        if not historical_impressions or not historical_positions:
            return None
        
        avg_hist_impressions = statistics.mean(historical_impressions)
        avg_hist_position = statistics.mean(historical_positions)
        
        # Impression drop > 30% but position stable = search volume change or competitor
        impression_drop_pct = ((avg_hist_impressions - current_impressions) / avg_hist_impressions) * 100
        position_change = abs(current_position - avg_hist_position)
        
        if impression_drop_pct > 30 and position_change < 2:
            return RootCause(
                cause_type='competitor_or_serp_change',
                confidence=0.7,
                evidence={
                    'impression_drop_percent': impression_drop_pct,
                    'position_stable': True,
                    'likely_reasons': ['new_serp_features', 'competitor_content', 'query_cannibalization']
                },
                recommendations=[
                    'Analyze SERP for new features (featured snippets, people also ask)',
                    'Review competitor content improvements',
                    'Check for query refinements stealing traffic',
                    'Optimize for SERP features',
                    'Create content targeting related queries'
                ],
                severity='medium'
            )
        
        return None

    def _detect_seasonal_pattern(self, historical_metrics: List[Dict[str, float]]) -> bool:
        """Detect if there's a seasonal pattern in the data.
        
        Args:
            historical_metrics: Historical metric data
            
        Returns:
            True if seasonal pattern detected, False otherwise
        """
        if len(historical_metrics) < 14:
            return False
        
        clicks = [m.get('clicks', 0) for m in historical_metrics]
        
        # Simple weekly pattern detection
        if len(clicks) >= 14:
            # Calculate autocorrelation at lag 7 (weekly)
            try:
                mean_clicks = statistics.mean(clicks)
                c0 = sum((x - mean_clicks) ** 2 for x in clicks)
                c7 = sum((clicks[i] - mean_clicks) * (clicks[i-7] - mean_clicks) for i in range(7, len(clicks)))
                
                autocorr = c7 / c0 if c0 != 0 else 0
                
                # Strong weekly pattern
                return autocorr > 0.5
            except:
                return False
        
        return False

    def synthesize_diagnosis(
        self,
        root_causes: List[RootCause],
        anomaly_type: str
    ) -> RootCause:
        """Synthesize multiple potential causes into final diagnosis.
        
        Args:
            root_causes: List of potential root causes
            anomaly_type: Type of anomaly being diagnosed
            
        Returns:
            Final diagnosis
        """
        if not root_causes:
            return RootCause(
                cause_type='unknown',
                confidence=0.3,
                evidence={'anomaly_type': anomaly_type},
                recommendations=['Monitor for patterns', 'Gather more data'],
                severity='low'
            )
        
        # Return highest confidence cause
        root_causes.sort(key=lambda c: c.confidence, reverse=True)
        return root_causes[0]
