"""Recommendation Engine - Converts diagnoses into actionable recommendations."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Recommendation:
    """Recommendation with action items."""
    
    recommendation_type: str
    action_items: Dict
    description: str
    rationale: str


class RecommendationEngine:
    """Generates recommendations from diagnoses."""
    
    def __init__(self):
        """Initialize recommendation engine."""
        self.recommendation_templates = {
            'position_drop': self._recommend_position_recovery,
            'ctr_decline': self._recommend_ctr_improvement,
            'high_bounce_rate': self._recommend_engagement_improvement,
            'low_engagement': self._recommend_engagement_improvement,
            'conversion_drop': self._recommend_conversion_optimization,
            'zero_impression': self._recommend_technical_fixes,
            'crawl_error': self._recommend_technical_fixes,
            'mobile_issue': self._recommend_mobile_optimization,
            'page_speed': self._recommend_speed_optimization,
            'cannibalization': self._recommend_content_consolidation,
            'keyword_gap': self._recommend_content_creation,
            'missing_schema': self._recommend_structured_data
        }
    
    def generate_recommendations(
        self,
        diagnosis: Dict,
        current_metrics: Dict,
        historical_metrics: List[Dict]
    ) -> List[Recommendation]:
        """Generate recommendations from diagnosis.
        
        Args:
            diagnosis: Diagnosis information
            current_metrics: Current page metrics
            historical_metrics: Historical metrics
            
        Returns:
            List of Recommendation objects
        """
        root_cause = diagnosis.get('root_cause', '')
        recommendations = []
        
        # Get specific recommendation generator
        generator = self.recommendation_templates.get(
            root_cause,
            self._recommend_generic
        )
        
        # Generate recommendations
        recs = generator(diagnosis, current_metrics, historical_metrics)
        recommendations.extend(recs)
        
        # Add supporting evidence-based recommendations
        evidence = diagnosis.get('supporting_evidence', {})
        if isinstance(evidence, dict):
            additional_recs = self._recommend_from_evidence(
                evidence,
                current_metrics
            )
            recommendations.extend(additional_recs)
        
        return recommendations
    
    def _recommend_position_recovery(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend actions for position recovery."""
        recommendations = []
        
        # Content optimization
        recommendations.append(Recommendation(
            recommendation_type='content_optimization',
            action_items={
                'title_optimization': {
                    'action': 'Optimize title tag with target keyword',
                    'priority': 'high',
                    'steps': [
                        'Research top-ranking titles for target keyword',
                        'Include primary keyword near beginning',
                        'Ensure title is compelling and under 60 characters'
                    ]
                },
                'content_refresh': {
                    'action': 'Update content with fresh information',
                    'priority': 'high',
                    'steps': [
                        'Add recent statistics and data',
                        'Update outdated information',
                        'Expand thin sections',
                        'Improve content depth and quality'
                    ]
                },
                'keyword_optimization': {
                    'action': 'Optimize keyword usage',
                    'priority': 'medium',
                    'steps': [
                        'Include primary keyword in H1',
                        'Use related keywords naturally throughout',
                        'Add semantic variations'
                    ]
                }
            },
            description='Optimize content to recover lost rankings',
            rationale='Position drops often result from content becoming outdated or competitors improving their content'
        ))
        
        # Internal linking
        recommendations.append(Recommendation(
            recommendation_type='internal_linking',
            action_items={
                'add_internal_links': {
                    'action': 'Add internal links from high-authority pages',
                    'priority': 'medium',
                    'steps': [
                        'Identify top-performing pages on similar topics',
                        'Add contextual links with relevant anchor text',
                        'Aim for 3-5 new internal links'
                    ]
                },
                'optimize_anchor_text': {
                    'action': 'Optimize existing anchor text',
                    'priority': 'low',
                    'steps': [
                        'Review current anchor text',
                        'Update generic anchors to keyword-rich',
                        'Ensure natural keyword variations'
                    ]
                }
            },
            description='Boost page authority through internal linking',
            rationale='Internal links help distribute authority and improve rankings'
        ))
        
        return recommendations
    
    def _recommend_ctr_improvement(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend CTR improvement actions."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='content_optimization',
            action_items={
                'title_rewrite': {
                    'action': 'Rewrite title for better CTR',
                    'priority': 'critical',
                    'steps': [
                        'Add power words (Guide, Complete, Best, How to)',
                        'Include numbers or current year',
                        'Create urgency or curiosity',
                        'Test multiple variations'
                    ]
                },
                'meta_description': {
                    'action': 'Optimize meta description',
                    'priority': 'high',
                    'steps': [
                        'Write compelling description with keyword',
                        'Include call-to-action',
                        'Keep under 155 characters',
                        'Highlight unique value proposition'
                    ]
                },
                'schema_markup': {
                    'action': 'Add rich snippets',
                    'priority': 'medium',
                    'steps': [
                        'Implement FAQ schema if applicable',
                        'Add review/rating schema',
                        'Use breadcrumb schema',
                        'Add article schema with author'
                    ]
                }
            },
            description='Improve click-through rate from search results',
            rationale='Better titles and meta descriptions directly improve CTR'
        ))
        
        return recommendations
    
    def _recommend_engagement_improvement(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend engagement improvement actions."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='ux_improvements',
            action_items={
                'improve_readability': {
                    'action': 'Enhance content readability',
                    'priority': 'high',
                    'steps': [
                        'Break up long paragraphs',
                        'Add subheadings every 200-300 words',
                        'Use bullet points and lists',
                        'Add relevant images and videos'
                    ]
                },
                'add_interactive_elements': {
                    'action': 'Add interactive elements',
                    'priority': 'medium',
                    'steps': [
                        'Add table of contents',
                        'Include jump links',
                        'Add interactive calculators or tools',
                        'Embed related videos'
                    ]
                },
                'optimize_cta': {
                    'action': 'Optimize calls-to-action',
                    'priority': 'medium',
                    'steps': [
                        'Add clear CTAs above the fold',
                        'Use action-oriented button text',
                        'Place CTAs at natural transition points',
                        'Test different CTA placements'
                    ]
                }
            },
            description='Reduce bounce rate and improve engagement',
            rationale='Better UX and readability keeps users on page longer'
        ))
        
        return recommendations
    
    def _recommend_conversion_optimization(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend conversion optimization actions."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='ux_improvements',
            action_items={
                'optimize_conversion_path': {
                    'action': 'Streamline conversion path',
                    'priority': 'critical',
                    'steps': [
                        'Reduce steps to conversion',
                        'Add trust signals (reviews, badges)',
                        'Improve form design',
                        'Add live chat or support options'
                    ]
                },
                'improve_value_proposition': {
                    'action': 'Strengthen value proposition',
                    'priority': 'high',
                    'steps': [
                        'Clarify benefits above the fold',
                        'Add social proof',
                        'Include customer testimonials',
                        'Highlight unique selling points'
                    ]
                }
            },
            description='Improve conversion rate',
            rationale='Streamlined conversion path and clear value proposition increase conversions'
        ))
        
        return recommendations
    
    def _recommend_technical_fixes(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend technical fixes."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='technical_fixes',
            action_items={
                'fix_indexing': {
                    'action': 'Fix indexing issues',
                    'priority': 'critical',
                    'steps': [
                        'Check robots.txt blocking',
                        'Remove noindex tags',
                        'Submit URL to Search Console',
                        'Check for server errors'
                    ]
                },
                'fix_crawl_errors': {
                    'action': 'Resolve crawl errors',
                    'priority': 'critical',
                    'steps': [
                        'Fix broken links',
                        'Resolve redirect chains',
                        'Fix 404 errors',
                        'Improve server response time'
                    ]
                }
            },
            description='Fix technical SEO issues',
            rationale='Technical issues prevent pages from ranking'
        ))
        
        return recommendations
    
    def _recommend_mobile_optimization(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend mobile optimization."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='technical_fixes',
            action_items={
                'mobile_responsive': {
                    'action': 'Improve mobile responsiveness',
                    'priority': 'high',
                    'steps': [
                        'Test on multiple devices',
                        'Fix touch targets spacing',
                        'Ensure text is readable without zooming',
                        'Remove horizontal scrolling'
                    ]
                },
                'mobile_performance': {
                    'action': 'Optimize mobile performance',
                    'priority': 'high',
                    'steps': [
                        'Reduce mobile page size',
                        'Optimize images for mobile',
                        'Minimize JavaScript',
                        'Enable AMP if applicable'
                    ]
                }
            },
            description='Optimize for mobile users',
            rationale='Mobile-first indexing prioritizes mobile performance'
        ))
        
        return recommendations
    
    def _recommend_speed_optimization(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend speed optimization."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='technical_fixes',
            action_items={
                'improve_lcp': {
                    'action': 'Improve Largest Contentful Paint',
                    'priority': 'high',
                    'steps': [
                        'Optimize images',
                        'Remove render-blocking resources',
                        'Use CDN for static assets',
                        'Implement lazy loading'
                    ]
                },
                'reduce_js': {
                    'action': 'Reduce JavaScript execution',
                    'priority': 'medium',
                    'steps': [
                        'Minimize third-party scripts',
                        'Defer non-critical JavaScript',
                        'Remove unused code',
                        'Use code splitting'
                    ]
                }
            },
            description='Improve page speed',
            rationale='Faster pages rank better and convert better'
        ))
        
        return recommendations
    
    def _recommend_content_consolidation(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend content consolidation for cannibalization."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='content_pruning',
            action_items={
                'merge_pages': {
                    'action': 'Consolidate competing pages',
                    'priority': 'high',
                    'steps': [
                        'Identify cannibalistic pages',
                        'Merge content into strongest page',
                        'Set up 301 redirects',
                        'Update internal links'
                    ]
                }
            },
            description='Fix keyword cannibalization',
            rationale='Multiple pages competing for same keyword dilutes authority'
        ))
        
        return recommendations
    
    def _recommend_content_creation(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend new content creation."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='content_creation',
            action_items={
                'create_new_content': {
                    'action': 'Create new content for keyword gap',
                    'priority': 'medium',
                    'steps': [
                        'Research keyword opportunity',
                        'Analyze competitor content',
                        'Create comprehensive content',
                        'Optimize for target keyword'
                    ]
                }
            },
            description='Create content for keyword opportunities',
            rationale='Filling keyword gaps captures additional traffic'
        ))
        
        return recommendations
    
    def _recommend_structured_data(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Recommend structured data implementation."""
        recommendations = []
        
        recommendations.append(Recommendation(
            recommendation_type='technical_fixes',
            action_items={
                'add_schema': {
                    'action': 'Implement structured data',
                    'priority': 'medium',
                    'steps': [
                        'Choose appropriate schema type',
                        'Implement JSON-LD markup',
                        'Test with Schema validator',
                        'Monitor rich results in Search Console'
                    ]
                }
            },
            description='Add structured data markup',
            rationale='Structured data enables rich snippets and better visibility'
        ))
        
        return recommendations
    
    def _recommend_from_evidence(
        self,
        evidence: Dict,
        current: Dict
    ) -> List[Recommendation]:
        """Generate recommendations from supporting evidence."""
        recommendations = []
        
        classification = evidence.get('classification', {})
        tags = classification.get('tags', [])
        
        # Check for specific issues in tags
        if 'technical' in tags and not any(
            rec for rec in recommendations
            if rec.recommendation_type == 'technical_fixes'
        ):
            recommendations.append(Recommendation(
                recommendation_type='technical_fixes',
                action_items={
                    'general_technical_audit': {
                        'action': 'Perform technical SEO audit',
                        'priority': 'medium',
                        'steps': [
                            'Check site speed',
                            'Verify mobile-friendliness',
                            'Review robots.txt and sitemap',
                            'Check for broken links'
                        ]
                    }
                },
                description='Address technical SEO issues',
                rationale='Technical issues identified in diagnosis'
            ))
        
        return recommendations
    
    def _recommend_generic(
        self,
        diagnosis: Dict,
        current: Dict,
        historical: List[Dict]
    ) -> List[Recommendation]:
        """Generate generic recommendations when root cause unclear."""
        return [
            Recommendation(
                recommendation_type='content_optimization',
                action_items={
                    'general_optimization': {
                        'action': 'General SEO optimization',
                        'priority': 'medium',
                        'steps': [
                            'Review and optimize title/meta',
                            'Improve content quality',
                            'Add internal links',
                            'Check technical issues'
                        ]
                    }
                },
                description='General SEO improvements',
                rationale='Comprehensive optimization for unclear root cause'
            )
        ]
