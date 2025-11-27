"""
Pydantic Response Schemas for Content Optimization
===================================================
Strict response models for LLM outputs, ensuring structured and validated responses.

Each schema corresponds to a specific optimization task and enforces:
- Field constraints (min/max length, allowed values)
- Custom validators for edge cases
- Clear documentation for each field

Usage:
    from insights_core.prompts.schemas import TitleOptimizationResponse

    # Instructor will validate LLM output against this schema
    response = client.generate(
        prompt=prompt,
        response_model=TitleOptimizationResponse
    )
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class TitleOptimizationResponse(BaseModel):
    """
    Response schema for title optimization.

    Validates that the optimized title meets SEO requirements:
    - Length: 10-60 characters
    - Keyword position tracked
    - Changes documented
    """

    optimized_title: str = Field(
        ...,
        min_length=10,
        max_length=60,
        description="SEO-optimized title, 10-60 characters"
    )
    keyword_position: Literal["beginning", "middle", "end"] = Field(
        ...,
        description="Where primary keyword is placed in title"
    )
    changes_made: List[str] = Field(
        default_factory=list,
        description="List of specific changes made to the title"
    )

    @field_validator('optimized_title', mode='before')
    @classmethod
    def strip_quotes(cls, v: str) -> str:
        """Strip surrounding quotes if present."""
        if isinstance(v, str):
            return v.strip().strip('"\'')
        return v

    @field_validator('optimized_title')
    @classmethod
    def no_pipe_characters(cls, v: str) -> str:
        """Remove pipe characters commonly added by LLMs."""
        return v.replace('|', '-').strip()


class MetaDescriptionResponse(BaseModel):
    """
    Response schema for meta description optimization.

    Validates that the meta description meets SEO requirements:
    - Length: 100-160 characters
    - Includes CTA indicator
    - Keyword inclusion tracked
    """

    description: str = Field(
        ...,
        min_length=100,
        max_length=160,
        description="Meta description, 100-160 characters"
    )
    includes_cta: bool = Field(
        ...,
        description="Whether description includes call-to-action"
    )
    includes_keyword: bool = Field(
        ...,
        description="Whether primary keyword is naturally included"
    )

    @field_validator('description', mode='before')
    @classmethod
    def strip_quotes(cls, v: str) -> str:
        """Strip surrounding quotes if present."""
        if isinstance(v, str):
            return v.strip().strip('"\'')
        return v


class ContentExpansionResponse(BaseModel):
    """
    Response schema for content expansion.

    Validates that expanded content meets requirements:
    - Minimum content length
    - At least one section added
    - Word count tracked
    """

    expanded_content: str = Field(
        ...,
        min_length=100,
        description="Full expanded content in markdown format"
    )
    sections_added: List[str] = Field(
        ...,
        min_length=1,
        description="List of new section headings added (H2/H3)"
    )
    word_count_added: int = Field(
        ...,
        ge=50,
        description="Approximate words added to the content"
    )

    @field_validator('sections_added')
    @classmethod
    def clean_section_headings(cls, v: List[str]) -> List[str]:
        """Remove markdown heading markers from section names."""
        return [s.lstrip('#').strip() for s in v]


class ReadabilityResponse(BaseModel):
    """
    Response schema for readability improvement.

    Validates that readability improvements are documented:
    - Improved content returned
    - Changes summarized
    - Estimated improvement tracked
    """

    improved_content: str = Field(
        ...,
        min_length=50,
        description="Content with improved readability"
    )
    changes_summary: List[str] = Field(
        ...,
        min_length=1,
        description="Summary of readability changes made"
    )
    estimated_flesch_improvement: int = Field(
        ...,
        ge=0,
        le=50,
        description="Estimated Flesch score improvement points (0-50)"
    )


class KeywordOptimizationResponse(BaseModel):
    """
    Response schema for keyword optimization.

    Validates that keyword optimization is balanced:
    - Content returned with keywords
    - Number of keywords added tracked
    - LSI keywords documented
    """

    optimized_content: str = Field(
        ...,
        min_length=50,
        description="Content with optimized keyword placement"
    )
    keywords_added: int = Field(
        ...,
        ge=0,
        le=20,
        description="Number of keyword instances added (max 20 to prevent stuffing)"
    )
    lsi_keywords_used: List[str] = Field(
        default_factory=list,
        description="LSI/semantic keywords incorporated"
    )

    @field_validator('lsi_keywords_used')
    @classmethod
    def lowercase_keywords(cls, v: List[str]) -> List[str]:
        """Normalize LSI keywords to lowercase."""
        return [kw.lower().strip() for kw in v]


class IntentDifferentiationResponse(BaseModel):
    """
    Response schema for intent differentiation (cannibalization fix).

    Validates that content is properly differentiated:
    - Content focused on specific intent
    - Target intent identified
    - Overlap removed and unique value added
    """

    differentiated_content: str = Field(
        ...,
        min_length=50,
        description="Content focused on specific search intent"
    )
    target_intent: Literal["informational", "transactional", "navigational"] = Field(
        ...,
        description="The search intent this content now targets"
    )
    removed_overlap: List[str] = Field(
        default_factory=list,
        description="Topics/sections removed to reduce overlap with competing pages"
    )
    unique_value_added: List[str] = Field(
        ...,
        min_length=1,
        description="Unique value propositions added to differentiate content"
    )


# Type alias for all response types
ResponseType = (
    TitleOptimizationResponse
    | MetaDescriptionResponse
    | ContentExpansionResponse
    | ReadabilityResponse
    | KeywordOptimizationResponse
    | IntentDifferentiationResponse
)

# Mapping from prompt type to response schema
RESPONSE_SCHEMAS = {
    "title_optimization": TitleOptimizationResponse,
    "meta_description": MetaDescriptionResponse,
    "content_expansion": ContentExpansionResponse,
    "readability_improvement": ReadabilityResponse,
    "keyword_optimization": KeywordOptimizationResponse,
    "intent_differentiation": IntentDifferentiationResponse,
}


def get_response_schema(prompt_type: str) -> type[BaseModel]:
    """
    Get the response schema for a given prompt type.

    Args:
        prompt_type: Key from RESPONSE_SCHEMAS dict

    Returns:
        Pydantic model class for the response

    Raises:
        ValueError: If prompt_type is not found
    """
    if prompt_type not in RESPONSE_SCHEMAS:
        available = ", ".join(sorted(RESPONSE_SCHEMAS.keys()))
        raise ValueError(
            f"Unknown prompt type: '{prompt_type}'. "
            f"Available types: {available}"
        )
    return RESPONSE_SCHEMAS[prompt_type]
