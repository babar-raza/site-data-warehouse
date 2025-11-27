"""
Model Selection Configuration
=============================
Dynamic model selection based on available Ollama models with tier-based fallback.

Tiers:
    - production: High-quality models for actual content optimization
    - testing: Faster models for development and testing
    - fallback: Broadly compatible models when preferred ones unavailable

Usage:
    from config.model_config import select_best_available_model, MODEL_TIERS

    model = select_best_available_model(tier="production")
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Model tiers based on available Ollama models
MODEL_TIERS: Dict[str, List[str]] = {
    "production": [
        "qwen2.5:14b-instruct",
        "phi4:14b",
        "qwen2.5:14b",
        "deepseek-coder-v2:16b",
    ],
    "testing": [
        "qwen2.5-coder:7b",
        "mistral:latest",
        "llama3:8b",
        "gemma2:9b",
    ],
    "fallback": [
        "llama3:8b",
        "mistral:latest",
        "qwen2.5-coder:7b",
        "llama3.2:latest",
    ],
}


def get_available_models(base_url: Optional[str] = None) -> List[str]:
    """
    Get list of models available in Ollama.

    Args:
        base_url: Ollama server URL (defaults to OLLAMA_BASE_URL env var)

    Returns:
        List of available model names
    """
    base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    try:
        import httpx
        response = httpx.get(
            f"{base_url}/api/tags",
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.warning(f"Failed to get available models: {e}")

    return []


def select_best_available_model(
    tier: str = "production",
    base_url: Optional[str] = None,
    fallback_to_lower_tiers: bool = True
) -> Optional[str]:
    """
    Select the best available model from a tier.

    Checks which models from the specified tier are actually available
    in Ollama, and returns the first (highest priority) available one.

    Args:
        tier: Model tier ("production", "testing", or "fallback")
        base_url: Ollama server URL
        fallback_to_lower_tiers: If True, try lower tiers if no models found

    Returns:
        Model name if found, None if no models available

    Example:
        >>> model = select_best_available_model("production")
        >>> print(model)
        "qwen2.5:14b-instruct"
    """
    # Check environment variable override first
    env_model = os.environ.get("OLLAMA_MODEL")
    if env_model:
        logger.debug(f"Using model from environment: {env_model}")
        return env_model

    available = get_available_models(base_url)

    if not available:
        logger.warning("No models available from Ollama")
        return MODEL_TIERS.get(tier, MODEL_TIERS["fallback"])[0]

    # Normalize available model names for comparison
    available_normalized = {m.lower(): m for m in available}

    # Try tiers in order
    tiers_to_try = [tier]
    if fallback_to_lower_tiers:
        if tier == "production":
            tiers_to_try = ["production", "testing", "fallback"]
        elif tier == "testing":
            tiers_to_try = ["testing", "fallback"]

    for try_tier in tiers_to_try:
        tier_models = MODEL_TIERS.get(try_tier, [])

        for model in tier_models:
            model_lower = model.lower()

            # Check exact match
            if model_lower in available_normalized:
                selected = available_normalized[model_lower]
                logger.info(f"Selected model '{selected}' from tier '{try_tier}'")
                return selected

            # Check partial match (e.g., "llama3:8b" matches "llama3:8b-instruct")
            for avail_lower, avail_orig in available_normalized.items():
                if avail_lower.startswith(model_lower.split(":")[0]):
                    logger.info(
                        f"Selected model '{avail_orig}' (partial match for '{model}') "
                        f"from tier '{try_tier}'"
                    )
                    return avail_orig

    # Return first from original tier as last resort
    default = MODEL_TIERS.get(tier, MODEL_TIERS["fallback"])[0]
    logger.warning(f"No available models found, defaulting to: {default}")
    return default


def get_model_tier(model_name: str) -> Optional[str]:
    """
    Determine which tier a model belongs to.

    Args:
        model_name: The model name to check

    Returns:
        Tier name or None if model not in any tier
    """
    model_lower = model_name.lower()

    for tier, models in MODEL_TIERS.items():
        for m in models:
            if m.lower() in model_lower or model_lower in m.lower():
                return tier

    return None


def is_model_available(
    model_name: str,
    base_url: Optional[str] = None
) -> bool:
    """
    Check if a specific model is available in Ollama.

    Args:
        model_name: The model name to check
        base_url: Ollama server URL

    Returns:
        True if model is available
    """
    available = get_available_models(base_url)
    model_lower = model_name.lower()

    for avail in available:
        if avail.lower() == model_lower:
            return True
        # Partial match
        if avail.lower().startswith(model_lower.split(":")[0]):
            return True

    return False


def list_available_by_tier(base_url: Optional[str] = None) -> Dict[str, List[str]]:
    """
    List available models organized by tier.

    Args:
        base_url: Ollama server URL

    Returns:
        Dict mapping tier names to lists of available models in that tier
    """
    available = get_available_models(base_url)
    available_set = {m.lower() for m in available}

    result: Dict[str, List[str]] = {}

    for tier, models in MODEL_TIERS.items():
        tier_available = []
        for model in models:
            model_base = model.lower().split(":")[0]
            for avail in available:
                if avail.lower().startswith(model_base):
                    if avail not in tier_available:
                        tier_available.append(avail)

        result[tier] = tier_available

    # Add "other" tier for models not in defined tiers
    known_bases = set()
    for models in MODEL_TIERS.values():
        for m in models:
            known_bases.add(m.lower().split(":")[0])

    other = []
    for avail in available:
        avail_base = avail.lower().split(":")[0]
        if avail_base not in known_bases:
            other.append(avail)

    if other:
        result["other"] = other

    return result
