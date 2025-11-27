"""
LLM Prompt Templates for Content Optimization
==============================================
Structured prompt templates for SEO content optimization tasks.

Each prompt is designed for a specific optimization task and includes:
- Clear requirements and constraints
- Specific output format instructions
- Quality guidelines to prevent keyword stuffing

Usage:
    from insights_core.prompts import get_prompt

    prompt = get_prompt("title_optimization",
        current_title="My Page Title",
        topic="Python programming tutorials",
        keywords=["python", "tutorial", "beginner"],
        ctr=2.5,
        position=8.3
    )
"""

from typing import Any, Dict, List, Union


PROMPTS: Dict[str, str] = {
    # =========================================================================
    # TITLE OPTIMIZATION
    # =========================================================================
    "title_optimization": """You are an SEO expert. Optimize this page title for better click-through rate.

CURRENT TITLE: {current_title}
PAGE TOPIC: {topic}
TARGET KEYWORDS: {keywords}
CURRENT CTR: {ctr}%
AVERAGE POSITION: {position}

REQUIREMENTS:
- Length: 50-60 characters maximum (STRICT)
- Include primary keyword near the beginning if possible
- Make it compelling and click-worthy
- Consider search intent
- Avoid clickbait or misleading phrasing
- Use power words where appropriate (e.g., "Ultimate", "Complete", "Essential")

RESPOND WITH VALID JSON ONLY:
{{
    "optimized_title": "Your optimized title here (10-60 chars)",
    "keyword_position": "beginning" | "middle" | "end",
    "changes_made": ["change 1", "change 2"]
}}

Return ONLY the JSON object. No markdown code blocks, no explanation.""",

    # =========================================================================
    # META DESCRIPTION
    # =========================================================================
    "meta_description": """You are an SEO expert. Write an optimized meta description for this page.

PAGE TITLE: {title}
CONTENT PREVIEW: {content_preview}
TARGET KEYWORDS: {keywords}

REQUIREMENTS:
- Length: 100-160 characters (STRICT - stay within this range)
- Include a clear value proposition
- Include a call to action (e.g., "Learn more", "Discover", "Get started")
- Naturally incorporate the primary keyword
- Make it compelling for search result snippets
- Avoid keyword stuffing

RESPOND WITH VALID JSON ONLY:
{{
    "description": "Your meta description here (100-160 chars)",
    "includes_cta": true,
    "includes_keyword": true
}}

Return ONLY the JSON object. No markdown code blocks, no explanation.""",

    # =========================================================================
    # CONTENT EXPANSION
    # =========================================================================
    "content_expansion": """You are a technical content writer. Expand this content to be more comprehensive.

TITLE: {title}
CURRENT CONTENT ({word_count} words):
{content}

TARGET KEYWORDS: {keywords}
COMPETITOR AVERAGE WORD COUNT: {competitor_avg}

REQUIREMENTS:
- Add approximately {target_words} words of valuable, informative content
- Include relevant H2 and H3 subheadings (use ## and ### markdown format)
- Add practical examples, code snippets, or use cases where relevant
- Address common user questions related to the topic
- Maintain the existing writing tone and style
- Do NOT repeat existing content - only ADD new content
- Focus on providing genuine value, not fluff

RESPOND WITH VALID JSON ONLY:
{{
    "expanded_content": "The COMPLETE expanded content in markdown format",
    "sections_added": ["New Section 1", "New Section 2"],
    "word_count_added": 150
}}

Return ONLY the JSON object. No markdown code blocks wrapping the JSON.""",

    # =========================================================================
    # READABILITY IMPROVEMENT
    # =========================================================================
    "readability_improvement": """You are a content editor focused on readability. Improve the readability of this content.

CURRENT FLESCH READING EASE SCORE: {flesch_score}
TARGET AUDIENCE: {audience}

CONTENT:
{content}

REQUIREMENTS:
- Simplify complex sentences (aim for 15-20 words per sentence)
- Break up long paragraphs (max 3-4 sentences per paragraph)
- Use bullet points or numbered lists where appropriate
- Replace jargon with simpler alternatives (or explain technical terms)
- Maintain technical accuracy - do not oversimplify to the point of being incorrect
- Target Flesch Reading Ease score: 60+ (easily understood by 13-15 year olds)
- Use active voice instead of passive voice where possible

RESPOND WITH VALID JSON ONLY:
{{
    "improved_content": "The improved content with better readability",
    "changes_summary": ["Simplified sentence X", "Broke up paragraph Y"],
    "estimated_flesch_improvement": 10
}}

Return ONLY the JSON object. No markdown code blocks wrapping the JSON.""",

    # =========================================================================
    # KEYWORD OPTIMIZATION
    # =========================================================================
    "keyword_optimization": """You are an SEO specialist. Optimize this content for the target keywords naturally.

TARGET KEYWORDS: {keywords}
CURRENT KEYWORD DENSITY: {density}%

CONTENT:
{content}

REQUIREMENTS:
- Add keywords naturally where they fit contextually
- Include semantic variations and related terms (LSI keywords)
- Optimize headings to include keywords where appropriate
- Maintain natural reading flow - avoid awkward phrasing
- DO NOT keyword stuff - the content must read naturally
- Target keyword density: 1-2% (not more)
- Add keywords to the introduction and conclusion sections

RESPOND WITH VALID JSON ONLY:
{{
    "optimized_content": "The content with optimized keyword placement",
    "keywords_added": 5,
    "lsi_keywords_used": ["related term 1", "semantic variation"]
}}

Return ONLY the JSON object. No markdown code blocks wrapping the JSON.""",

    # =========================================================================
    # INTENT DIFFERENTIATION (Cannibalization Fix)
    # =========================================================================
    "intent_differentiation": """You are a content strategist. Differentiate this content to target a specific search intent.

TARGET SEARCH INTENT: {intent}

CURRENT CONTENT:
{content}

COMPETING PAGES TARGET: {competing_intents}

REQUIREMENTS:
- Sharpen focus on the specific target intent
- Remove or minimize content that overlaps with competing pages
- Add unique value that other pages don't cover
- Update headings to clearly signal the unique focus
- If intent is "informational": add explanations, guides, how-tos
- If intent is "transactional": add CTAs, comparisons, pricing info
- If intent is "navigational": add clear directions, links, resources

RESPOND WITH VALID JSON ONLY:
{{
    "differentiated_content": "The content focused on specific search intent",
    "target_intent": "informational" | "transactional" | "navigational",
    "removed_overlap": ["topic removed 1", "section minimized"],
    "unique_value_added": ["unique point 1", "unique angle 2"]
}}

Return ONLY the JSON object. No markdown code blocks wrapping the JSON.""",
}


def get_prompt(prompt_type: str, **kwargs: Any) -> str:
    """
    Get a formatted prompt for the specified optimization type.

    Args:
        prompt_type: Key from PROMPTS dict (e.g., "title_optimization")
        **kwargs: Variables to format into the template

    Returns:
        Formatted prompt string ready for LLM

    Raises:
        ValueError: If prompt_type is not found in PROMPTS
        KeyError: If a required template variable is missing from kwargs

    Example:
        >>> prompt = get_prompt("title_optimization",
        ...     current_title="My Title",
        ...     topic="Python tutorials",
        ...     keywords=["python", "tutorial"],
        ...     ctr=2.5,
        ...     position=8.0
        ... )
    """
    if prompt_type not in PROMPTS:
        available = ", ".join(sorted(PROMPTS.keys()))
        raise ValueError(
            f"Unknown prompt type: '{prompt_type}'. "
            f"Available types: {available}"
        )

    template = PROMPTS[prompt_type]

    # Convert list/tuple kwargs to string representation
    formatted_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, (list, tuple)):
            formatted_kwargs[key] = ", ".join(str(v) for v in value)
        else:
            formatted_kwargs[key] = value

    try:
        return template.format(**formatted_kwargs)
    except KeyError as e:
        # Extract required placeholders from template
        import re
        placeholders = set(re.findall(r'\{(\w+)\}', template))
        provided = set(formatted_kwargs.keys())
        missing = placeholders - provided
        raise KeyError(
            f"Missing required template variable(s) for '{prompt_type}': {missing}. "
            f"Required: {placeholders}, Provided: {provided}"
        ) from e


def list_prompts() -> List[str]:
    """
    List all available prompt types.

    Returns:
        List of prompt type names
    """
    return sorted(PROMPTS.keys())


def get_prompt_requirements(prompt_type: str) -> Dict[str, Any]:
    """
    Get information about a prompt type's requirements.

    Args:
        prompt_type: Key from PROMPTS dict

    Returns:
        Dict with prompt metadata and required variables

    Raises:
        ValueError: If prompt_type not found
    """
    if prompt_type not in PROMPTS:
        raise ValueError(f"Unknown prompt type: '{prompt_type}'")

    import re
    template = PROMPTS[prompt_type]
    placeholders = set(re.findall(r'\{(\w+)\}', template))

    return {
        "type": prompt_type,
        "required_variables": sorted(placeholders),
        "template_length": len(template),
    }
