"""
LLM Prompt Templates for Content Optimization
==============================================
Provides structured prompts for various content optimization tasks
using local LLM (Ollama) with Pydantic schema validation.

Modules:
    content_prompts: Prompt templates for each optimization type
    schemas: Pydantic response models for structured LLM outputs
    client: Instructor-wrapped LLM client for structured outputs
    cache: Response caching with content-hash keys
    rate_limiter: Resource-aware rate limiting
"""

from insights_core.prompts.content_prompts import PROMPTS, get_prompt
from insights_core.prompts.schemas import (
    TitleOptimizationResponse,
    MetaDescriptionResponse,
    ContentExpansionResponse,
    ReadabilityResponse,
    KeywordOptimizationResponse,
    IntentDifferentiationResponse,
    RESPONSE_SCHEMAS,
    get_response_schema,
)
from insights_core.prompts.client import (
    ContentOptimizationClient,
    OPERATION_CONFIG,
)
from insights_core.prompts.cache import ResponseCache
from insights_core.prompts.rate_limiter import (
    ResourceAwareRateLimiter,
    SyncRateLimiter,
    ResourceLimits,
    get_resource_limits,
    get_default_limiter,
)

__all__ = [
    # Templates
    'PROMPTS',
    'get_prompt',
    # Schemas
    'TitleOptimizationResponse',
    'MetaDescriptionResponse',
    'ContentExpansionResponse',
    'ReadabilityResponse',
    'KeywordOptimizationResponse',
    'IntentDifferentiationResponse',
    'RESPONSE_SCHEMAS',
    'get_response_schema',
    # Client
    'ContentOptimizationClient',
    'OPERATION_CONFIG',
    # Cache
    'ResponseCache',
    # Rate Limiter
    'ResourceAwareRateLimiter',
    'SyncRateLimiter',
    'ResourceLimits',
    'get_resource_limits',
    'get_default_limiter',
]
