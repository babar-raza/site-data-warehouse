"""
LLM Reasoner Base Class for Structured LLM Interactions

Provides a base class for performing structured LLM reasoning tasks using Ollama.
Integrates with OllamaModelSelector for resource-aware model selection and
PromptTemplates for standardized prompts with schema validation.

Example usage:
    >>> from agents.base.llm_reasoner import LLMReasoner
    >>> reasoner = LLMReasoner()
    >>> result = reasoner.reason(
    ...     prompt="Analyze this traffic drop: clicks from 100 to 50",
    ...     response_format="json"
    ... )
    >>> print(result)
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union

from agents.base.model_selector import OllamaModelSelector, TaskComplexity
from agents.base.prompt_templates import PromptTemplate, PromptTemplates

logger = logging.getLogger(__name__)


class ResponseFormat(str, Enum):
    """Supported response formats for LLM reasoning."""
    JSON = "json"
    TEXT = "text"


@dataclass
class ReasoningResult:
    """Result of a reasoning operation.

    Attributes:
        success: Whether reasoning completed successfully
        content: The response content (parsed JSON dict or text string)
        raw_response: Raw LLM response text
        model_used: Name of the model used
        tokens_used: Approximate token count (if available)
        duration_ms: Time taken in milliseconds
        error: Error message if success is False
        validation_errors: List of schema validation errors (for JSON responses)
    """
    success: bool
    content: Union[Dict[str, Any], str, None]
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'success': self.success,
            'content': self.content,
            'raw_response': self.raw_response,
            'model_used': self.model_used,
            'tokens_used': self.tokens_used,
            'duration_ms': self.duration_ms,
            'error': self.error,
            'validation_errors': self.validation_errors
        }


class LLMReasoner:
    """Base class for structured LLM reasoning operations.

    Provides methods for performing LLM reasoning with:
    - Automatic model selection based on resources
    - Structured prompt management
    - JSON response parsing and validation
    - Error handling and retries
    - Timeout management

    Attributes:
        model_selector: OllamaModelSelector for choosing models
        default_timeout: Default timeout in seconds
        max_retries: Maximum retry attempts for failed calls

    Example:
        >>> reasoner = LLMReasoner()
        >>> result = reasoner.reason(
        ...     prompt="What are the causes of this traffic drop?",
        ...     response_format="json"
        ... )
        >>> if result.success:
        ...     print(result.content)
    """

    DEFAULT_TIMEOUT = 60.0
    MAX_RETRIES = 2

    def __init__(
        self,
        model_selector: Optional[OllamaModelSelector] = None,
        default_timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        ollama_host: Optional[str] = None
    ):
        """Initialize the LLMReasoner.

        Args:
            model_selector: Custom model selector. Creates new one if None.
            default_timeout: Default timeout in seconds (max 60).
            max_retries: Maximum retry attempts for failed calls.
            ollama_host: Ollama API host. Uses OLLAMA_HOST env var or localhost.
        """
        self.model_selector = model_selector or OllamaModelSelector(
            ollama_host=ollama_host
        )
        self.default_timeout = min(default_timeout, 60.0)  # Max 60 seconds
        self.max_retries = max_retries
        self.ollama_host = ollama_host or self.model_selector.ollama_host

        # Track usage stats
        self._total_calls = 0
        self._successful_calls = 0
        self._total_tokens = 0

        logger.debug(
            f"LLMReasoner initialized with timeout={self.default_timeout}s, "
            f"max_retries={self.max_retries}"
        )

    def reason(
        self,
        prompt: str,
        response_format: str = "json",
        task_complexity: str = "medium",
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        temperature: float = 0.7
    ) -> ReasoningResult:
        """Perform LLM reasoning on a prompt.

        Main method for executing LLM reasoning tasks with structured
        output handling.

        Args:
            prompt: The prompt/question to reason about
            response_format: Output format ('json' or 'text')
            task_complexity: Complexity level for model selection
                ('simple', 'medium', 'complex', 'expert')
            system_prompt: Optional system prompt override
            schema: JSON schema for validating JSON responses
            timeout: Timeout in seconds (default: 60, max: 60)
            temperature: Generation temperature (0.0-2.0)

        Returns:
            ReasoningResult with response content and metadata

        Example:
            >>> reasoner = LLMReasoner()
            >>> result = reasoner.reason(
            ...     prompt="Analyze traffic drop",
            ...     response_format="json",
            ...     task_complexity="medium"
            ... )
            >>> print(result.content)
        """
        start_time = time.time()
        self._total_calls += 1

        # Validate and normalize inputs
        try:
            fmt = ResponseFormat(response_format.lower())
        except ValueError:
            logger.warning(f"Unknown format '{response_format}', using text")
            fmt = ResponseFormat.TEXT

        timeout = min(timeout or self.default_timeout, 60.0)

        # Select model
        model = self._select_model(task_complexity)
        config = self.model_selector.get_execution_config(
            model, temperature=temperature
        )

        logger.info(f"Reasoning with model={model}, format={fmt.value}")

        # Build final prompt
        final_prompt = self._build_prompt(prompt, system_prompt, fmt)

        # Execute with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self._call_ollama(
                    model=model,
                    prompt=final_prompt,
                    config=config,
                    timeout=timeout
                )

                # Format response
                content, validation_errors = self._format_response(
                    raw_response, fmt, schema
                )

                duration_ms = int((time.time() - start_time) * 1000)

                # Track success
                self._successful_calls += 1

                result = ReasoningResult(
                    success=True,
                    content=content,
                    raw_response=raw_response,
                    model_used=model,
                    duration_ms=duration_ms,
                    validation_errors=validation_errors
                )

                logger.info(
                    f"Reasoning complete: model={model}, "
                    f"duration={duration_ms}ms, format={fmt.value}"
                )

                return result

            except TimeoutError as e:
                last_error = f"Timeout after {timeout}s"
                logger.warning(f"Attempt {attempt + 1} timed out: {e}")

            except ConnectionError as e:
                last_error = f"Connection error: {e}"
                logger.warning(f"Attempt {attempt + 1} connection failed: {e}")
                # Connection errors may benefit from a short delay
                if attempt < self.max_retries:
                    time.sleep(1.0)

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

        # All retries exhausted
        duration_ms = int((time.time() - start_time) * 1000)
        return ReasoningResult(
            success=False,
            content=None,
            error=last_error,
            model_used=model,
            duration_ms=duration_ms
        )

    def reason_with_template(
        self,
        template: Union[str, PromptTemplate],
        template_vars: Dict[str, Any],
        task_complexity: str = "medium",
        timeout: Optional[float] = None,
        temperature: float = 0.7
    ) -> ReasoningResult:
        """Perform reasoning using a predefined template.

        Args:
            template: Template name or PromptTemplate instance
            template_vars: Variables to fill in the template
            task_complexity: Complexity level for model selection
            timeout: Timeout in seconds
            temperature: Generation temperature

        Returns:
            ReasoningResult with response content

        Example:
            >>> reasoner = LLMReasoner()
            >>> result = reasoner.reason_with_template(
            ...     template="anomaly_analysis",
            ...     template_vars={
            ...         "metric_name": "clicks",
            ...         "current_value": 50,
            ...         "historical_average": 100,
            ...         "percent_change": -50.0,
            ...         "time_period": "Last 7 days",
            ...         "additional_context": ""
            ...     }
            ... )
        """
        # Get template
        if isinstance(template, str):
            prompt_template = PromptTemplates.get_template_by_name(template)
            if prompt_template is None:
                return ReasoningResult(
                    success=False,
                    content=None,
                    error=f"Unknown template: {template}"
                )
        else:
            prompt_template = template

        # Format user prompt
        try:
            user_prompt = prompt_template.format_user_prompt(**template_vars)
        except ValueError as e:
            return ReasoningResult(
                success=False,
                content=None,
                error=f"Template formatting error: {e}"
            )

        # Add JSON instruction suffix if schema present
        if prompt_template.response_schema:
            user_prompt += PromptTemplates.create_json_prompt_suffix()

        # Execute reasoning
        return self.reason(
            prompt=user_prompt,
            response_format="json" if prompt_template.response_schema else "text",
            task_complexity=task_complexity,
            system_prompt=prompt_template.system_prompt,
            schema=prompt_template.response_schema,
            timeout=timeout,
            temperature=temperature
        )

    def _select_model(self, task_complexity: str) -> str:
        """Select the best model for the task.

        Args:
            task_complexity: Complexity level

        Returns:
            Selected model name
        """
        return self.model_selector.select_best_model(
            task_complexity=task_complexity
        )

    def _build_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str],
        response_format: ResponseFormat
    ) -> str:
        """Build the final prompt for the LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            response_format: Desired response format

        Returns:
            Formatted prompt string
        """
        parts = []

        if system_prompt:
            parts.append(f"System: {system_prompt}\n")

        parts.append(prompt)

        if response_format == ResponseFormat.JSON:
            parts.append(PromptTemplates.create_json_prompt_suffix())

        return "\n".join(parts)

    def _call_ollama(
        self,
        model: str,
        prompt: str,
        config: Dict[str, Any],
        timeout: float
    ) -> str:
        """Call the Ollama API.

        Args:
            model: Model name
            prompt: Full prompt text
            config: Model execution configuration
            timeout: Request timeout in seconds

        Returns:
            Raw response text from the model

        Raises:
            TimeoutError: If request times out
            ConnectionError: If connection fails
            RuntimeError: For other API errors
        """
        try:
            import httpx

            # Build request payload
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": config.get("num_ctx", 4096),
                    "num_gpu": config.get("num_gpu", 0),
                    "num_thread": config.get("num_thread", 4),
                    "temperature": config.get("temperature", 0.7),
                }
            }

            logger.debug(f"Calling Ollama: model={model}, timeout={timeout}s")

            response = httpx.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()

            data = response.json()
            return data.get("response", "")

        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {timeout}s") from e

        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Ollama at {self.ollama_host}") from e

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama API error: {e.response.status_code}") from e

        except ImportError:
            # Fallback for when httpx is not available
            logger.warning("httpx not available, using mock response")
            return self._mock_response(prompt)

        except Exception as e:
            raise RuntimeError(f"Ollama API call failed: {e}") from e

    def _mock_response(self, prompt: str) -> str:
        """Generate a mock response when Ollama is not available.

        For testing and development without a running Ollama instance.

        Args:
            prompt: The prompt text

        Returns:
            Mock response string
        """
        if "json" in prompt.lower():
            return json.dumps({
                "severity": "medium",
                "likely_causes": ["Unable to determine - mock response"],
                "confidence": 0.5,
                "recommended_actions": ["Connect to Ollama for real analysis"],
                "reasoning": "This is a mock response for testing"
            })
        return "Mock response - Ollama not available"

    def _format_response(
        self,
        raw_response: str,
        response_format: ResponseFormat,
        schema: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """Format and validate the LLM response.

        Args:
            raw_response: Raw text from the LLM
            response_format: Expected format
            schema: Optional JSON schema for validation

        Returns:
            Tuple of (formatted_content, validation_errors)
        """
        if response_format == ResponseFormat.TEXT:
            return raw_response.strip(), []

        # Parse JSON response
        parsed, parse_errors = self._parse_json(raw_response)
        if parse_errors:
            return raw_response, parse_errors

        # Validate against schema if provided
        validation_errors = []
        if schema and parsed:
            is_valid, errors = self._validate_response(parsed, schema)
            if not is_valid:
                validation_errors = errors

        return parsed, validation_errors

    def _parse_json(self, response: str) -> tuple:
        """Parse JSON from LLM response.

        Handles common issues like markdown code blocks and leading/trailing text.

        Args:
            response: Raw response text

        Returns:
            Tuple of (parsed_dict_or_none, error_list)
        """
        text = response.strip()

        # Try direct parse first
        try:
            return json.loads(text), []
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        code_block_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
        ]

        for pattern in code_block_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return json.loads(match.group(1)), []
                except json.JSONDecodeError:
                    continue

        # Try finding JSON object in text
        json_pattern = r'\{[\s\S]*\}'
        match = re.search(json_pattern, text)
        if match:
            try:
                return json.loads(match.group(0)), []
            except json.JSONDecodeError:
                pass

        # Failed to parse
        return None, [f"Failed to parse JSON from response: {text[:100]}..."]

    def _validate_response(
        self,
        response: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> tuple:
        """Validate response against JSON schema.

        Args:
            response: Parsed response dictionary
            schema: JSON schema

        Returns:
            Tuple of (is_valid, errors_list)
        """
        return PromptTemplates.validate_response(response, schema)

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics.

        Returns:
            Dictionary with usage stats
        """
        success_rate = 0.0
        if self._total_calls > 0:
            success_rate = self._successful_calls / self._total_calls

        return {
            'total_calls': self._total_calls,
            'successful_calls': self._successful_calls,
            'success_rate': success_rate,
            'total_tokens': self._total_tokens,
        }

    def reset_stats(self):
        """Reset usage statistics."""
        self._total_calls = 0
        self._successful_calls = 0
        self._total_tokens = 0

    def estimate_complexity(self, prompt: str) -> str:
        """Estimate task complexity from prompt text.

        Args:
            prompt: Prompt text to analyze

        Returns:
            Complexity level string
        """
        return self.model_selector._estimate_complexity(prompt).value

    def is_available(self) -> bool:
        """Check if Ollama is available and responding.

        Returns:
            True if Ollama is reachable, False otherwise
        """
        try:
            import httpx

            response = httpx.get(
                f"{self.ollama_host}/api/tags",
                timeout=5.0
            )
            return response.status_code == 200

        except Exception:
            return False


class SpecializedReasoner(LLMReasoner):
    """Base class for specialized reasoning tasks.

    Provides a foundation for building domain-specific reasoners
    with predefined templates and configurations.

    Example:
        >>> class AnomalyReasoner(SpecializedReasoner):
        ...     def __init__(self):
        ...         super().__init__(
        ...             default_template="anomaly_analysis",
        ...             default_complexity="medium"
        ...         )
    """

    def __init__(
        self,
        default_template: str,
        default_complexity: str = "medium",
        **kwargs
    ):
        """Initialize specialized reasoner.

        Args:
            default_template: Default template name to use
            default_complexity: Default task complexity
            **kwargs: Additional arguments for LLMReasoner
        """
        super().__init__(**kwargs)
        self.default_template = default_template
        self.default_complexity = default_complexity

    def analyze(self, **template_vars) -> ReasoningResult:
        """Perform analysis using the default template.

        Args:
            **template_vars: Variables for the template

        Returns:
            ReasoningResult from reasoning
        """
        return self.reason_with_template(
            template=self.default_template,
            template_vars=template_vars,
            task_complexity=self.default_complexity
        )


class AnomalyAnalyzer(SpecializedReasoner):
    """Specialized reasoner for anomaly analysis.

    Example:
        >>> analyzer = AnomalyAnalyzer()
        >>> result = analyzer.analyze(
        ...     metric_name="clicks",
        ...     current_value=50,
        ...     historical_average=100,
        ...     percent_change=-50.0,
        ...     time_period="Last 7 days",
        ...     additional_context=""
        ... )
    """

    def __init__(self, **kwargs):
        super().__init__(
            default_template="anomaly_analysis",
            default_complexity="medium",
            **kwargs
        )


class DiagnosisAnalyzer(SpecializedReasoner):
    """Specialized reasoner for root cause diagnosis.

    Example:
        >>> analyzer = DiagnosisAnalyzer()
        >>> result = analyzer.analyze(
        ...     issue_description="Traffic dropped 40%",
        ...     symptoms="Lower impressions, Decreased CTR",
        ...     timeline="Last 7 days",
        ...     affected_pages="Blog section",
        ...     additional_data=""
        ... )
    """

    def __init__(self, **kwargs):
        super().__init__(
            default_template="diagnosis",
            default_complexity="complex",
            **kwargs
        )


class RecommendationGenerator(SpecializedReasoner):
    """Specialized reasoner for generating recommendations.

    Example:
        >>> generator = RecommendationGenerator()
        >>> result = generator.analyze(
        ...     context="E-commerce site",
        ...     diagnosis="Content quality issues",
        ...     goals="Increase organic traffic",
        ...     constraints="Limited budget",
        ...     additional_info=""
        ... )
    """

    def __init__(self, **kwargs):
        super().__init__(
            default_template="recommendation",
            default_complexity="complex",
            **kwargs
        )
