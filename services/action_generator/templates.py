"""
Action Templates - Templates for different action types

Provides templates that define how to convert different
insight types into actionable tasks.
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionTemplates:
    """
    Templates for generating actions from insights

    Each template defines:
    - action_type: Category of action
    - title_template: Template for action title
    - description_template: Template for action description
    - effort: Estimated effort level (low, medium, high)
    - instructions: Step-by-step instructions
    - estimated_impact: Expected impact metrics

    Example:
        templates = ActionTemplates()
        template = templates.get_template('seo_title_fix')
        template = templates.get_for_insight(insight_dict)
    """

    # Complete template definitions
    TEMPLATES = {
        # SEO Content Templates
        'seo_title_fix': {
            'action_type': 'content_update',
            'title_template': 'Optimize title for {page_path}',
            'description_template': 'The page {page_path} has a title that needs optimization. Current performance metrics indicate this page could benefit from an improved title.',
            'effort': 'low',
            'instructions': [
                'Open {page_path} in your CMS or editor',
                'Review the current title tag',
                'Ensure title is between 50-60 characters',
                'Include primary target keyword near the beginning',
                'Make the title compelling and click-worthy',
                'Avoid keyword stuffing',
                'Save and publish the changes',
                'Submit URL for re-indexing in Google Search Console'
            ],
            'estimated_impact': {
                'ctr_improvement': 0.15,
                'timeline_days': 14,
                'confidence': 0.7
            }
        },

        'meta_description_add': {
            'action_type': 'content_update',
            'title_template': 'Add meta description for {page_path}',
            'description_template': 'The page {page_path} is missing a meta description. Adding one can improve click-through rates from search results.',
            'effort': 'low',
            'instructions': [
                'Open {page_path} in your CMS or editor',
                'Add a meta description tag',
                'Write a compelling 150-160 character description',
                'Include primary keyword naturally',
                'Include a call to action when appropriate',
                'Ensure it accurately describes page content',
                'Save and publish the changes'
            ],
            'estimated_impact': {
                'ctr_improvement': 0.10,
                'timeline_days': 14,
                'confidence': 0.6
            }
        },

        'meta_description_fix': {
            'action_type': 'content_update',
            'title_template': 'Improve meta description for {page_path}',
            'description_template': 'The meta description for {page_path} could be improved for better search visibility.',
            'effort': 'low',
            'instructions': [
                'Open {page_path} in your CMS or editor',
                'Review current meta description',
                'Rewrite to be between 150-160 characters',
                'Include primary keyword naturally',
                'Add a clear value proposition',
                'Include a call to action',
                'Save and publish the changes'
            ],
            'estimated_impact': {
                'ctr_improvement': 0.08,
                'timeline_days': 14,
                'confidence': 0.5
            }
        },

        'content_expansion': {
            'action_type': 'content_update',
            'title_template': 'Expand content on {page_path}',
            'description_template': 'The page {page_path} has thin content that may be affecting its search performance. Expanding the content could improve rankings.',
            'effort': 'high',
            'instructions': [
                'Review current content on {page_path}',
                'Research related topics and questions users are searching for',
                'Add 500-1000+ words of valuable content',
                'Include relevant headings (H2, H3) for structure',
                'Add images, diagrams, or other media where appropriate',
                'Include internal links to related content',
                'Ensure content answers user intent thoroughly',
                'Proofread and publish'
            ],
            'estimated_impact': {
                'ranking_improvement': 5,
                'traffic_potential': 50,
                'timeline_days': 30,
                'confidence': 0.6
            }
        },

        # Technical SEO Templates
        'redirect_setup': {
            'action_type': 'technical',
            'title_template': 'Set up redirect for {page_path}',
            'description_template': 'A 301 redirect should be set up for {page_path} to consolidate SEO value.',
            'effort': 'low',
            'instructions': [
                'Identify the target URL to redirect to',
                'Add 301 redirect rule in your web server config or .htaccess',
                'Test the redirect works correctly',
                'Update internal links pointing to old URL',
                'Submit URL removal request in Google Search Console if needed',
                'Monitor for 404 errors in logs'
            ],
            'estimated_impact': {
                'link_equity_preserved': 0.9,
                'timeline_days': 7,
                'confidence': 0.9
            }
        },

        'canonical_fix': {
            'action_type': 'technical',
            'title_template': 'Fix canonical tag on {page_path}',
            'description_template': 'The canonical tag on {page_path} needs to be corrected to prevent duplicate content issues.',
            'effort': 'low',
            'instructions': [
                'Open {page_path} in your CMS or editor',
                'Check the current canonical tag',
                'Set canonical to the preferred version of the URL',
                'Ensure canonical URL is absolute (includes https://)',
                'Verify the canonical page exists and is indexable',
                'Save and publish the changes'
            ],
            'estimated_impact': {
                'duplicate_content_fixed': True,
                'timeline_days': 14,
                'confidence': 0.85
            }
        },

        'content_consolidation': {
            'action_type': 'content_restructure',
            'title_template': 'Consolidate duplicate content for {page_path}',
            'description_template': 'Multiple pages are competing for similar keywords. Consolidating them into {page_path} can improve overall ranking potential.',
            'effort': 'high',
            'instructions': [
                'Identify all pages targeting similar keywords',
                'Choose the best performing page as the canonical',
                'Merge unique content from other pages into the canonical',
                'Set up 301 redirects from deprecated pages',
                'Update internal links to point to the canonical page',
                'Remove deprecated pages from sitemap',
                'Request indexing of the consolidated page',
                'Monitor rankings and traffic over next 30 days'
            ],
            'estimated_impact': {
                'ranking_improvement': 3,
                'traffic_potential': 30,
                'timeline_days': 30,
                'confidence': 0.7
            }
        },

        # Performance Templates
        'page_speed_optimization': {
            'action_type': 'technical',
            'title_template': 'Optimize page speed for {page_path}',
            'description_template': 'Core Web Vitals for {page_path} need improvement to meet Google\'s standards.',
            'effort': 'medium',
            'instructions': [
                'Run PageSpeed Insights on {page_path}',
                'Identify specific issues (LCP, FID, CLS)',
                'Optimize images (compression, lazy loading, WebP format)',
                'Minimize CSS and JavaScript',
                'Enable browser caching',
                'Consider implementing CDN',
                'Re-test after changes',
                'Monitor Core Web Vitals in Search Console'
            ],
            'estimated_impact': {
                'cwv_improvement': True,
                'bounce_rate_reduction': 0.1,
                'timeline_days': 14,
                'confidence': 0.75
            }
        },

        # Keyword/Ranking Templates
        'keyword_optimization': {
            'action_type': 'content_update',
            'title_template': 'Optimize keywords on {page_path}',
            'description_template': 'The page {page_path} is ranking on page 2-3 for valuable keywords. Optimization could push it to page 1.',
            'effort': 'medium',
            'instructions': [
                'Review current keyword rankings for {page_path}',
                'Identify keywords ranking in positions 11-30',
                'Analyze competitor pages ranking in top 10',
                'Update content to better target these keywords',
                'Improve internal linking to this page',
                'Consider adding relevant structured data',
                'Update and improve the title and meta description',
                'Monitor ranking changes over next 30 days'
            ],
            'estimated_impact': {
                'ranking_improvement': 8,
                'traffic_potential': 100,
                'timeline_days': 30,
                'confidence': 0.6
            }
        },

        'cannibalization_fix': {
            'action_type': 'content_restructure',
            'title_template': 'Fix keyword cannibalization affecting {page_path}',
            'description_template': 'Multiple pages are competing for the same keywords, diluting ranking potential. Action needed to consolidate or differentiate.',
            'effort': 'high',
            'instructions': [
                'Identify all pages targeting the same keywords',
                'Analyze which page should be the primary target',
                'Option A: Merge content into one comprehensive page',
                'Option B: Differentiate pages to target different intents',
                'Update internal linking strategy',
                'Implement redirects if pages are merged',
                'Update content to clearly differentiate topics',
                'Monitor rankings for both pages/keywords'
            ],
            'estimated_impact': {
                'ranking_improvement': 5,
                'traffic_potential': 40,
                'timeline_days': 45,
                'confidence': 0.65
            }
        },

        # Link Templates
        'internal_linking': {
            'action_type': 'content_update',
            'title_template': 'Improve internal linking to {page_path}',
            'description_template': 'The page {page_path} has few internal links pointing to it, limiting its ability to rank.',
            'effort': 'medium',
            'instructions': [
                'Identify related content that could link to {page_path}',
                'Add contextual internal links from at least 5-10 relevant pages',
                'Use descriptive anchor text (not "click here")',
                'Ensure links are within main content (not just footer/sidebar)',
                'Update navigation if page is important',
                'Consider adding related posts/pages section',
                'Create pillar/cluster content structure if applicable'
            ],
            'estimated_impact': {
                'ranking_improvement': 3,
                'crawl_efficiency': 0.1,
                'timeline_days': 21,
                'confidence': 0.7
            }
        },

        # Anomaly/Issue Templates
        'traffic_drop_investigation': {
            'action_type': 'investigation',
            'title_template': 'Investigate traffic drop on {page_path}',
            'description_template': 'Significant traffic decline detected on {page_path}. Requires investigation to identify cause and remedy.',
            'effort': 'medium',
            'instructions': [
                'Check Google Search Console for any manual actions',
                'Review algorithm update timelines',
                'Analyze ranking changes for key queries',
                'Check for technical issues (crawl errors, indexing)',
                'Review recent content or site changes',
                'Compare page to competitor content',
                'Check for SERP feature changes',
                'Document findings and create remediation plan'
            ],
            'estimated_impact': {
                'traffic_recovery': True,
                'timeline_days': 30,
                'confidence': 0.5
            }
        },

        'ranking_drop_fix': {
            'action_type': 'content_update',
            'title_template': 'Address ranking decline for {page_path}',
            'description_template': 'Rankings have dropped for {page_path}. Content refresh and optimization may help recover positions.',
            'effort': 'medium',
            'instructions': [
                'Review Search Console data for the page',
                'Identify which keywords dropped in rankings',
                'Analyze top-ranking competitor pages',
                'Update and refresh content with new information',
                'Improve content comprehensiveness',
                'Check and fix any technical issues',
                'Build internal links to the page',
                'Request re-indexing after updates'
            ],
            'estimated_impact': {
                'ranking_recovery': 5,
                'timeline_days': 30,
                'confidence': 0.55
            }
        },

        # Default template
        'general_action': {
            'action_type': 'general',
            'title_template': 'Review and action: {title}',
            'description_template': '{title}',
            'effort': 'medium',
            'instructions': [
                'Review the insight details',
                'Analyze the affected page or query',
                'Determine appropriate action based on findings',
                'Implement necessary changes',
                'Monitor results'
            ],
            'estimated_impact': {
                'improvement_potential': 'varies',
                'timeline_days': 30,
                'confidence': 0.5
            }
        }
    }

    # Mapping from insight characteristics to templates
    INSIGHT_TEMPLATE_MAP = {
        # By category and source
        ('risk', 'AnomalyDetector'): 'traffic_drop_investigation',
        ('risk', 'TrendDetector'): 'ranking_drop_fix',
        ('risk', 'ContentQualityDetector'): 'content_expansion',
        ('risk', 'CWVQualityDetector'): 'page_speed_optimization',
        ('opportunity', 'OpportunityDetector'): 'keyword_optimization',
        ('opportunity', 'ContentQualityDetector'): 'meta_description_add',
        ('diagnosis', 'DiagnosisDetector'): 'traffic_drop_investigation',
        ('trend', 'TrendDetector'): 'keyword_optimization',
    }

    # Keyword-based template matching
    KEYWORD_TEMPLATE_MAP = {
        'title': 'seo_title_fix',
        'meta description': 'meta_description_add',
        'canonical': 'canonical_fix',
        'duplicate': 'content_consolidation',
        'cannibalization': 'cannibalization_fix',
        'thin content': 'content_expansion',
        'internal link': 'internal_linking',
        'core web vitals': 'page_speed_optimization',
        'cwv': 'page_speed_optimization',
        'lcp': 'page_speed_optimization',
        'redirect': 'redirect_setup',
    }

    def get_template(self, template_name: str) -> Dict:
        """
        Get a specific template by name

        Args:
            template_name: Name of the template

        Returns:
            Template dictionary

        Example:
            >>> templates = ActionTemplates()
            >>> template = templates.get_template('seo_title_fix')
            >>> print(template['effort'])
            'low'
        """
        return self.TEMPLATES.get(template_name, self.TEMPLATES['general_action'])

    def get_for_insight(self, insight: Dict) -> Dict:
        """
        Get the most appropriate template for an insight

        Args:
            insight: Insight dictionary with category, source, title, etc.

        Returns:
            Best matching template

        Example:
            >>> templates = ActionTemplates()
            >>> insight = {'category': 'risk', 'source': 'AnomalyDetector', 'title': 'Traffic drop detected'}
            >>> template = templates.get_for_insight(insight)
            >>> print(template['action_type'])
        """
        # Try exact match by category and source
        key = (insight.get('category'), insight.get('source'))
        if key in self.INSIGHT_TEMPLATE_MAP:
            template_name = self.INSIGHT_TEMPLATE_MAP[key]
            return self.TEMPLATES.get(template_name, self.TEMPLATES['general_action'])

        # Try keyword matching in title
        title_lower = insight.get('title', '').lower()
        description_lower = insight.get('description', '').lower()

        for keyword, template_name in self.KEYWORD_TEMPLATE_MAP.items():
            if keyword in title_lower or keyword in description_lower:
                return self.TEMPLATES.get(template_name, self.TEMPLATES['general_action'])

        # Default to general action
        logger.debug(f"Using general template for insight: {insight.get('title', 'unknown')}")
        return self.TEMPLATES['general_action']

    def list_templates(self) -> List[str]:
        """
        List all available template names

        Returns:
            List of template names
        """
        return list(self.TEMPLATES.keys())

    def get_templates_by_type(self, action_type: str) -> List[Dict]:
        """
        Get all templates of a specific action type

        Args:
            action_type: Type of action (content_update, technical, etc.)

        Returns:
            List of matching templates
        """
        return [
            {'name': name, **template}
            for name, template in self.TEMPLATES.items()
            if template.get('action_type') == action_type
        ]
