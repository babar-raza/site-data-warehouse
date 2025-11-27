# Structured LLM Prompts Module

This module provides structured LLM prompts with **Instructor + Pydantic** validation for content optimization operations.

## Architecture

```
insights_core/prompts/
├── __init__.py           # Public exports
├── schemas.py            # Pydantic response models (6 schemas)
├── content_prompts.py    # Prompt templates (6 prompts)
├── client.py             # Instructor-wrapped LLM client
├── cache.py              # Content-hash based caching
└── rate_limiter.py       # Resource-aware rate limiting
```

## Quick Start

```python
from insights_core.prompts import (
    ContentOptimizationClient,
    TitleOptimizationResponse,
    get_prompt,
)

# Initialize client
client = ContentOptimizationClient(
    provider="ollama",
    model="qwen2.5:14b-instruct"
)

# Generate structured response
prompt = get_prompt(
    "title_optimization",
    current_title="Python Tutorial",
    topic="Python programming",
    keywords=["python", "tutorial"],
    ctr=2.5,
    position=8.3
)

response = client.generate(
    prompt=prompt,
    response_model=TitleOptimizationResponse
)

# Response is validated Pydantic model
print(response.optimized_title)       # Validated 10-60 chars
print(response.keyword_position)      # "beginning" | "middle" | "end"
print(response.changes_made)          # List of changes
```

## Response Schemas

All LLM responses are validated against strict Pydantic schemas:

### TitleOptimizationResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `optimized_title` | str | 10-60 characters |
| `keyword_position` | Literal | "beginning", "middle", "end" |
| `changes_made` | List[str] | Optional list of changes |

### MetaDescriptionResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `description` | str | 100-160 characters |
| `includes_cta` | bool | Whether CTA is present |
| `includes_keyword` | bool | Whether keyword included |

### ContentExpansionResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `expanded_content` | str | min 100 characters |
| `sections_added` | List[str] | min 1 section |
| `word_count_added` | int | min 50 words |

### ReadabilityResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `improved_content` | str | Required |
| `changes_summary` | List[str] | min 1 change |
| `estimated_flesch_improvement` | int | 0-50 points |

### KeywordOptimizationResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `optimized_content` | str | Required |
| `keywords_added` | int | 0-20 max |
| `lsi_keywords_used` | List[str] | Normalized to lowercase |

### IntentDifferentiationResponse

| Field | Type | Constraints |
|-------|------|-------------|
| `differentiated_content` | str | Required |
| `target_intent` | Literal | "informational", "transactional", "navigational" |
| `removed_overlap` | List[str] | Topics removed |
| `unique_value_added` | List[str] | min 1 value |

## Configuration

### Environment Variables

```bash
# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b-instruct

# Feature flag (disable for legacy parsing)
USE_STRUCTURED_PROMPTS=true
```

### Model Selection

Models are organized in tiers with automatic fallback:

| Tier | Models | Use Case |
|------|--------|----------|
| production | qwen2.5:14b-instruct, phi4:14b | Best quality |
| testing | qwen2.5-coder:7b, mistral:latest | Fast iteration |
| fallback | llama3:8b | Broad compatibility |

```python
from config.model_config import select_best_available_model

model = select_best_available_model(tier="production")
```

### Rate Limiting

Resource-aware rate limiting adapts to your hardware:

| Hardware | Max Concurrent | RPM | Batch Size |
|----------|---------------|-----|------------|
| GPU | 3 | 30 | 10 |
| High-CPU (8+ cores, 32GB) | 2 | 15 | 5 |
| Standard | 1 | 6 | 3 |

```python
from insights_core.prompts.rate_limiter import ResourceAwareRateLimiter

limiter = ResourceAwareRateLimiter()

async with limiter:
    result = await process_item()
```

### Response Caching

Content-hash based caching prevents duplicate LLM calls:

```python
# Enabled by default
client = ContentOptimizationClient(enable_cache=True)

# Skip cache for fresh response
response = client.generate(
    prompt=prompt,
    response_model=TitleOptimizationResponse,
    use_cache=False
)
```

Cache keys are SHA256 hashes of (prompt + model + schema).

## Operation Timeouts

Each operation type has specific timeout and delay settings:

| Operation | Timeout | Delay After |
|-----------|---------|-------------|
| title_optimization | 30s | 2s |
| meta_description | 30s | 2s |
| keyword_optimization | 45s | 3s |
| readability_improvement | 60s | 5s |
| content_expansion | 120s | 10s |
| intent_differentiation | 90s | 5s |

## Testing

### Mock Tests (No Ollama Required)

```bash
# Run all mock tests
pytest tests/insights_core/prompts/test_schemas.py -v
pytest tests/insights_core/prompts/test_client_mock.py -v
pytest tests/insights_core/prompts/test_content_prompts.py -v
```

### Live Ollama Tests

```bash
# Requires running Ollama instance
TEST_MODE=ollama pytest tests/insights_core/prompts/test_client_ollama.py -v
```

## Adding New Optimization Types

To add a new optimization type:

1. **Add Schema** (`schemas.py`):

```python
class NewOptimizationResponse(BaseModel):
    """Response schema for new optimization."""
    result: str = Field(..., min_length=10)
    changes: List[str] = Field(default_factory=list)
```

2. **Add Prompt** (`content_prompts.py`):

```python
PROMPTS["new_optimization"] = """You are an expert...

RESPOND WITH VALID JSON ONLY:
{{
    "result": "...",
    "changes": ["..."]
}}
"""
```

3. **Update RESPONSE_SCHEMAS** (`schemas.py`):

```python
RESPONSE_SCHEMAS["new_optimization"] = NewOptimizationResponse
```

4. **Add OPERATION_CONFIG** (`client.py`):

```python
OPERATION_CONFIG["new_optimization"] = {"timeout": 45, "delay_after": 3}
```

5. **Add Tests** - Both schema validation and mock client tests

## Troubleshooting

### ValidationError After Max Retries

**Problem**: LLM consistently returns invalid JSON

**Solutions**:
1. Lower temperature (`temperature=0.5`)
2. Increase max_retries (`max_retries=3`)
3. Use a larger model (14B+ recommended)
4. Check prompt clarity - add explicit examples

### Ollama Connection Refused

**Problem**: `ConnectionRefusedError` when creating client

**Solutions**:
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Or with Docker
docker-compose up ollama
```

### Cache Not Working

**Problem**: Same prompt returns different results

**Solutions**:
1. Verify cache is enabled: `ContentOptimizationClient(enable_cache=True)`
2. Check prompt is identical (whitespace matters)
3. Cache TTL may have expired (default 24h)

### Rate Limit Exceeded

**Problem**: Requests being throttled unexpectedly

**Solutions**:
```python
# Check current limits
from insights_core.prompts.rate_limiter import get_resource_limits
print(get_resource_limits())

# Override limits
limiter = ResourceAwareRateLimiter(
    max_concurrent=5,
    requests_per_minute=60
)
```

## API Reference

### ContentOptimizationClient

```python
class ContentOptimizationClient:
    def __init__(
        self,
        provider: str = "ollama",        # "ollama" or "openai"
        base_url: str = None,            # Provider URL
        model: str = None,               # Model name
        max_retries: int = 2,            # Validation retries
        timeout: float = 60.0,           # Request timeout
        enable_cache: bool = True,       # Enable response cache
        cache_ttl_hours: int = 24        # Cache TTL
    ): ...

    def generate(
        self,
        prompt: str,                     # Formatted prompt
        response_model: Type[T],         # Pydantic model class
        temperature: float = 0.7,        # LLM temperature
        operation_type: str = None,      # For operation-specific timeout
        use_cache: bool = True           # Use cached response
    ) -> T: ...

    def is_available(self) -> bool: ...
```

### get_prompt

```python
def get_prompt(prompt_type: str, **kwargs) -> str:
    """
    Get formatted prompt string.

    Args:
        prompt_type: One of the 6 optimization types
        **kwargs: Template variables

    Returns:
        Formatted prompt string ready for LLM
    """
```

---

*Module Version: 1.0.0*
*Last Updated: November 2025*
