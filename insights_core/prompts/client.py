"""
Structured LLM Client for Content Optimization
===============================================
Uses Instructor to enforce Pydantic schemas on LLM responses with auto-retry.

Features:
- Validates responses against Pydantic schemas
- Auto-retry with validation errors fed back to LLM
- Support for multiple providers (Ollama, OpenAI)
- Configurable timeouts and retry counts
- Operation-specific configurations

Usage:
    from insights_core.prompts.client import ContentOptimizationClient
    from insights_core.prompts.schemas import TitleOptimizationResponse

    client = ContentOptimizationClient()
    response = client.generate(
        prompt=prompt,
        response_model=TitleOptimizationResponse
    )
"""

import logging
import os
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


# Operation-specific timeout and delay configurations
OPERATION_CONFIG: Dict[str, Dict[str, Any]] = {
    "title_optimization": {"timeout": 30, "delay_after": 2},
    "meta_description": {"timeout": 30, "delay_after": 2},
    "keyword_optimization": {"timeout": 45, "delay_after": 3},
    "readability_improvement": {"timeout": 60, "delay_after": 5},
    "content_expansion": {"timeout": 120, "delay_after": 10},
    "intent_differentiation": {"timeout": 90, "delay_after": 5},
}


class ContentOptimizationClient:
    """
    LLM client with structured output enforcement.

    Uses Instructor to:
    - Validate responses against Pydantic schemas
    - Auto-retry with validation errors fed back to LLM
    - Handle multiple providers (Ollama, OpenAI)
    """

    def __init__(
        self,
        provider: str = "ollama",
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        enable_cache: bool = True,
        cache_ttl_hours: int = 24
    ):
        """
        Initialize the content optimization client.

        Args:
            provider: LLM provider ("ollama" or "openai")
            base_url: Provider base URL (defaults to env var or localhost)
            model: Model name (defaults to env var or provider default)
            max_retries: Max retry attempts on validation failure
            timeout: Default request timeout in seconds
            enable_cache: Whether to enable response caching
            cache_ttl_hours: Cache TTL in hours
        """
        self.provider = provider
        self.max_retries = max_retries
        self.default_timeout = timeout

        # Set defaults from environment
        if provider == "ollama":
            self.base_url = base_url or os.environ.get(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            )
            self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-instruct")
        elif provider == "openai":
            self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
            self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Initialize provider-specific client (lazy loaded)
        self._client = None
        self._instructor_client = None

        # Initialize cache if enabled
        self._cache = None
        if enable_cache:
            try:
                from insights_core.prompts.cache import ResponseCache
                self._cache = ResponseCache(ttl_hours=cache_ttl_hours)
            except ImportError:
                logger.warning("Cache module not available, caching disabled")

    def _get_client(self):
        """Lazily initialize the Instructor client."""
        if self._instructor_client is not None:
            return self._instructor_client

        try:
            import instructor
            from openai import OpenAI

            if self.provider == "ollama":
                # Use OpenAI compatibility mode - Ollama supports OpenAI API at /v1
                api_base = self.base_url.rstrip("/")
                if not api_base.endswith("/v1"):
                    api_base = f"{api_base}/v1"
                self._client = OpenAI(
                    base_url=api_base,
                    api_key="ollama"  # Ollama doesn't need a real API key
                )
                self._instructor_client = instructor.from_openai(
                    self._client,
                    mode=instructor.Mode.JSON
                )
            elif self.provider == "openai":
                self._client = OpenAI(base_url=self.base_url)
                self._instructor_client = instructor.from_openai(
                    self._client,
                    mode=instructor.Mode.JSON
                )

            return self._instructor_client

        except ImportError as e:
            logger.error(f"Failed to import required package: {e}")
            raise RuntimeError(
                f"Missing dependency for {self.provider} provider. "
                f"Install with: pip install instructor openai"
            ) from e

    def generate(
        self,
        prompt: str,
        response_model: Type[T],
        operation_type: Optional[str] = None,
        temperature: float = 0.7,
        timeout: Optional[float] = None,
        use_cache: bool = True,
        **kwargs
    ) -> T:
        """
        Generate structured response from LLM.

        Args:
            prompt: The formatted prompt string
            response_model: Pydantic model class for response validation
            operation_type: Operation type for timeout config (optional)
            temperature: LLM temperature (0.0-1.0)
            timeout: Request timeout (overrides operation default)
            use_cache: Whether to use cache for this request
            **kwargs: Additional provider-specific arguments

        Returns:
            Validated Pydantic model instance

        Raises:
            ValidationError: If response fails validation after max_retries
            ConnectionError: If LLM provider is unavailable
        """
        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(prompt, self.model, response_model)
            if cached is not None:
                logger.debug(f"Cache hit for {response_model.__name__}")
                return cached

        # Get operation-specific timeout
        if timeout is None and operation_type and operation_type in OPERATION_CONFIG:
            timeout = OPERATION_CONFIG[operation_type]["timeout"]
        elif timeout is None:
            timeout = self.default_timeout

        client = self._get_client()

        try:
            response = client.chat.completions.create(
                model=self.model,
                response_model=response_model,
                max_retries=self.max_retries,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=kwargs.get("max_tokens", 2048),
                **{k: v for k, v in kwargs.items() if k not in ["max_tokens"]}
            )

            # Cache the result
            if use_cache and self._cache:
                self._cache.set(prompt, self.model, response_model, response)

            return response

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def generate_raw(
        self,
        prompt: str,
        temperature: float = 0.7,
        timeout: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Generate raw text response without schema validation.

        Useful for fallback or when structured output isn't needed.

        Args:
            prompt: The formatted prompt string
            temperature: LLM temperature (0.0-1.0)
            timeout: Request timeout
            **kwargs: Additional arguments

        Returns:
            Raw text response from LLM
        """
        timeout = timeout or self.default_timeout

        if self.provider == "ollama":
            from ollama import Client
            client = Client(host=self.base_url)
            response = client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": temperature}
            )
            return response["message"]["content"]

        elif self.provider == "openai":
            from openai import OpenAI
            client = OpenAI(base_url=self.base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content

        raise ValueError(f"Unsupported provider: {self.provider}")

    def is_available(self) -> bool:
        """
        Check if the LLM provider is available.

        Returns:
            True if provider is responding, False otherwise
        """
        try:
            if self.provider == "ollama":
                import httpx
                response = httpx.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0
                )
                return response.status_code == 200

            elif self.provider == "openai":
                # OpenAI health check - try to list models
                from openai import OpenAI
                client = OpenAI(base_url=self.base_url)
                client.models.list()
                return True

        except Exception as e:
            logger.debug(f"Provider availability check failed: {e}")
            return False

        return False

    def list_models(self) -> list:
        """
        List available models from the provider.

        Returns:
            List of model names
        """
        try:
            if self.provider == "ollama":
                import httpx
                response = httpx.get(
                    f"{self.base_url}/api/tags",
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]

            elif self.provider == "openai":
                from openai import OpenAI
                client = OpenAI(base_url=self.base_url)
                models = client.models.list()
                return [m.id for m in models.data]

        except Exception as e:
            logger.error(f"Failed to list models: {e}")

        return []

    def get_operation_config(self, operation_type: str) -> Dict[str, Any]:
        """
        Get timeout and delay configuration for an operation type.

        Args:
            operation_type: The operation type name

        Returns:
            Dict with 'timeout' and 'delay_after' keys
        """
        return OPERATION_CONFIG.get(
            operation_type,
            {"timeout": self.default_timeout, "delay_after": 2}
        )

    def __repr__(self) -> str:
        return (
            f"ContentOptimizationClient("
            f"provider={self.provider!r}, "
            f"model={self.model!r}, "
            f"base_url={self.base_url!r})"
        )
