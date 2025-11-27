"""
Ollama Model Selector for Resource-Aware LLM Execution

Provides intelligent model selection based on system resources and task complexity.
Integrates with SystemResourceMonitor to ensure optimal model performance without
system overload.

Example usage:
    >>> from agents.base.model_selector import OllamaModelSelector
    >>> selector = OllamaModelSelector()
    >>> model = selector.select_best_model(task_complexity='medium')
    >>> print(f"Selected: {model}")
    >>> config = selector.get_execution_config(model)
    >>> print(f"Config: {config}")
"""
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

from agents.base.resource_monitor import SystemResourceMonitor, ResourceThresholds

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels for model selection.

    Attributes:
        SIMPLE: Basic tasks like classification, simple Q&A (small models ok)
        MEDIUM: Standard tasks like summarization, analysis (medium models)
        COMPLEX: Advanced tasks like reasoning, code generation (larger models)
        EXPERT: Expert-level tasks requiring maximum capability (largest models)
    """
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class ModelRequirements:
    """Resource requirements for running a specific model.

    Attributes:
        ram_gb: Minimum RAM required in gigabytes
        vram_gb: Minimum VRAM required for GPU execution (0 for CPU-only)
        context_length: Default context window size
        cpu_threads: Recommended CPU threads
        quality_tier: Quality tier (1=highest, 4=lowest)
    """
    ram_gb: float
    vram_gb: float
    context_length: int
    cpu_threads: int
    quality_tier: int


@dataclass
class ModelConfig:
    """Complete configuration for model execution.

    Attributes:
        model: Model name/tag for Ollama
        num_ctx: Context window size
        num_gpu: Number of GPU layers (-1 for all, 0 for none)
        num_thread: Number of CPU threads to use
        use_gpu: Whether GPU acceleration is enabled
        temperature: Generation temperature (0.0-2.0)
        top_p: Top-p sampling parameter
        top_k: Top-k sampling parameter
    """
    model: str
    num_ctx: int
    num_gpu: int
    num_thread: int
    use_gpu: bool
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Ollama API.

        Returns:
            Dictionary suitable for Ollama API options.
        """
        return {
            'model': self.model,
            'num_ctx': self.num_ctx,
            'num_gpu': self.num_gpu,
            'num_thread': self.num_thread,
            'use_gpu': self.use_gpu,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'top_k': self.top_k,
        }


# Model catalog with resource requirements
# Ordered by preference (larger/better models first)
MODEL_CATALOG: Dict[str, ModelRequirements] = {
    # Large models (70B parameter class)
    'llama3.1:70b': ModelRequirements(
        ram_gb=48.0, vram_gb=40.0, context_length=128000,
        cpu_threads=16, quality_tier=1
    ),
    'qwen2.5:72b': ModelRequirements(
        ram_gb=48.0, vram_gb=40.0, context_length=128000,
        cpu_threads=16, quality_tier=1
    ),

    # Medium-large models (13B-34B parameter class)
    'codellama:34b': ModelRequirements(
        ram_gb=24.0, vram_gb=20.0, context_length=16384,
        cpu_threads=12, quality_tier=2
    ),
    'llama3.1:8b': ModelRequirements(
        ram_gb=8.0, vram_gb=6.0, context_length=128000,
        cpu_threads=8, quality_tier=2
    ),
    'mistral:7b': ModelRequirements(
        ram_gb=8.0, vram_gb=6.0, context_length=32768,
        cpu_threads=8, quality_tier=2
    ),
    'qwen2.5:7b': ModelRequirements(
        ram_gb=8.0, vram_gb=6.0, context_length=128000,
        cpu_threads=8, quality_tier=2
    ),

    # Small models (3B-7B parameter class)
    'llama3.2:3b': ModelRequirements(
        ram_gb=4.0, vram_gb=3.0, context_length=128000,
        cpu_threads=4, quality_tier=3
    ),
    'phi3:medium': ModelRequirements(
        ram_gb=8.0, vram_gb=6.0, context_length=128000,
        cpu_threads=6, quality_tier=3
    ),
    'gemma2:2b': ModelRequirements(
        ram_gb=4.0, vram_gb=2.0, context_length=8192,
        cpu_threads=4, quality_tier=3
    ),

    # Tiny models (1B-2B parameter class)
    'phi3:mini': ModelRequirements(
        ram_gb=4.0, vram_gb=2.0, context_length=128000,
        cpu_threads=4, quality_tier=4
    ),
    'tinyllama:1.1b': ModelRequirements(
        ram_gb=2.0, vram_gb=1.0, context_length=2048,
        cpu_threads=2, quality_tier=4
    ),
    'qwen2.5:0.5b': ModelRequirements(
        ram_gb=1.0, vram_gb=0.5, context_length=32768,
        cpu_threads=2, quality_tier=4
    ),
}

# Model preference order (best to worst for each complexity level)
MODEL_PREFERENCES: Dict[TaskComplexity, List[str]] = {
    TaskComplexity.EXPERT: [
        'llama3.1:70b', 'qwen2.5:72b', 'codellama:34b',
        'llama3.1:8b', 'qwen2.5:7b', 'mistral:7b',
        'phi3:medium', 'llama3.2:3b', 'gemma2:2b',
        'phi3:mini', 'tinyllama:1.1b', 'qwen2.5:0.5b'
    ],
    TaskComplexity.COMPLEX: [
        'llama3.1:8b', 'qwen2.5:7b', 'mistral:7b',
        'codellama:34b', 'phi3:medium', 'llama3.2:3b',
        'gemma2:2b', 'phi3:mini', 'tinyllama:1.1b', 'qwen2.5:0.5b'
    ],
    TaskComplexity.MEDIUM: [
        'llama3.2:3b', 'phi3:medium', 'gemma2:2b',
        'llama3.1:8b', 'qwen2.5:7b', 'mistral:7b',
        'phi3:mini', 'tinyllama:1.1b', 'qwen2.5:0.5b'
    ],
    TaskComplexity.SIMPLE: [
        'phi3:mini', 'tinyllama:1.1b', 'qwen2.5:0.5b',
        'llama3.2:3b', 'gemma2:2b', 'phi3:medium'
    ],
}


class OllamaModelSelector:
    """Intelligent model selector for Ollama-based LLM execution.

    Selects the best available model based on:
    - System resources (RAM, VRAM, CPU cores)
    - Task complexity requirements
    - Model availability
    - Quality/performance tradeoffs

    Uses SystemResourceMonitor to ensure safe execution without
    overloading the system.

    Attributes:
        resource_monitor: System resource monitor instance
        available_models: Set of models confirmed available on system
        default_model: Fallback model when selection fails

    Example:
        >>> selector = OllamaModelSelector()
        >>> model = selector.select_best_model(task_complexity='medium')
        >>> print(f"Selected: {model}")
        Selected: llama3.2:3b

        >>> config = selector.get_execution_config(model)
        >>> print(config)
        {'model': 'llama3.2:3b', 'num_ctx': 8192, ...}
    """

    DEFAULT_MODEL = 'phi3:mini'
    FALLBACK_MODEL = 'tinyllama:1.1b'

    def __init__(
        self,
        resource_monitor: Optional[SystemResourceMonitor] = None,
        available_models: Optional[List[str]] = None,
        default_model: Optional[str] = None,
        ollama_host: Optional[str] = None
    ):
        """Initialize the OllamaModelSelector.

        Args:
            resource_monitor: Custom resource monitor. Creates new one if None.
            available_models: Pre-specified list of available models.
                If None, will attempt to query Ollama.
            default_model: Default model to use. Uses DEFAULT_MODEL if None.
            ollama_host: Ollama API host. Uses OLLAMA_HOST env var or localhost.
        """
        self.resource_monitor = resource_monitor or SystemResourceMonitor(
            cpu_sample_interval=0.1
        )
        self._available_models = set(available_models) if available_models else None
        self.default_model = default_model or self.DEFAULT_MODEL
        self.ollama_host = ollama_host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')

        logger.debug(
            f"OllamaModelSelector initialized with default={self.default_model}, "
            f"host={self.ollama_host}"
        )

    @property
    def available_models(self) -> set:
        """Get set of available models.

        Lazily fetches from Ollama API if not already cached.

        Returns:
            Set of available model names.
        """
        if self._available_models is None:
            self._available_models = self._fetch_available_models()
        return self._available_models

    def _fetch_available_models(self) -> set:
        """Fetch available models from Ollama API.

        Returns:
            Set of available model names.
        """
        try:
            import httpx

            response = httpx.get(
                f"{self.ollama_host}/api/tags",
                timeout=10.0
            )
            response.raise_for_status()

            data = response.json()
            models = {m['name'] for m in data.get('models', [])}

            logger.info(f"Found {len(models)} models from Ollama: {models}")
            return models

        except ImportError:
            logger.warning("httpx not available, using default model list")
            return set(MODEL_CATALOG.keys())

        except Exception as e:
            logger.warning(f"Failed to fetch models from Ollama: {e}")
            # Return all catalog models as potentially available
            return set(MODEL_CATALOG.keys())

    def refresh_available_models(self) -> set:
        """Refresh the list of available models from Ollama.

        Returns:
            Updated set of available model names.
        """
        self._available_models = self._fetch_available_models()
        return self._available_models

    def select_best_model(
        self,
        task_complexity: str = 'medium',
        required_context: int = 4096,
        prefer_gpu: bool = True
    ) -> str:
        """Select the best available model based on resources and requirements.

        Evaluates available models against current system resources and
        task requirements, returning the best suitable model.

        Args:
            task_complexity: Task complexity level ('simple', 'medium',
                'complex', 'expert'). Higher complexity prefers larger models.
            required_context: Minimum context window size needed.
            prefer_gpu: Whether to prefer GPU-capable models.

        Returns:
            Name of the selected model (e.g., 'llama3.1:8b').

        Example:
            >>> selector = OllamaModelSelector()
            >>> model = selector.select_best_model(task_complexity='complex')
            >>> print(model)
            llama3.1:8b
        """
        # Normalize complexity
        try:
            complexity = TaskComplexity(task_complexity.lower())
        except ValueError:
            logger.warning(f"Unknown complexity '{task_complexity}', using MEDIUM")
            complexity = TaskComplexity.MEDIUM

        # Get current resources
        resources = self.resource_monitor.get_current_resources()

        logger.debug(
            f"Selecting model for complexity={complexity.value}, "
            f"context={required_context}, prefer_gpu={prefer_gpu}"
        )
        logger.debug(
            f"Resources: RAM={resources['ram_free_gb']:.1f}GB, "
            f"GPU={resources['gpu_available']}, "
            f"VRAM={resources['vram_free_gb']:.1f}GB"
        )

        # Get preference order for complexity
        preference_order = MODEL_PREFERENCES.get(
            complexity,
            MODEL_PREFERENCES[TaskComplexity.MEDIUM]
        )

        # Try models in preference order
        for model_name in preference_order:
            if self._can_run_model(
                model_name,
                resources,
                required_context,
                prefer_gpu
            ):
                logger.info(f"Selected model: {model_name}")
                return model_name

        # Fallback to default
        logger.warning(
            f"No suitable model found, falling back to {self.default_model}"
        )
        return self.default_model

    def _can_run_model(
        self,
        model_name: str,
        resources: Dict[str, Any],
        required_context: int,
        prefer_gpu: bool
    ) -> bool:
        """Check if a model can run with current resources.

        Args:
            model_name: Model name to check.
            resources: Current system resources from SystemResourceMonitor.
            required_context: Minimum context window needed.
            prefer_gpu: Whether GPU is preferred.

        Returns:
            True if model can run, False otherwise.
        """
        # Check if model is available
        if model_name not in self.available_models:
            logger.debug(f"Model {model_name} not available")
            return False

        # Get model requirements
        requirements = self._get_model_requirements(model_name)
        if requirements is None:
            logger.debug(f"No requirements for {model_name}")
            return False

        # Check context window
        if requirements.context_length < required_context:
            logger.debug(
                f"Model {model_name} context {requirements.context_length} "
                f"< required {required_context}"
            )
            return False

        # Check GPU resources
        if prefer_gpu and resources['gpu_available']:
            if resources['vram_free_gb'] >= requirements.vram_gb:
                logger.debug(f"Model {model_name} can run on GPU")
                return True
            else:
                logger.debug(
                    f"Model {model_name} needs {requirements.vram_gb}GB VRAM, "
                    f"only {resources['vram_free_gb']:.1f}GB available"
                )

        # Check CPU/RAM resources
        # Apply safety margin (80% of free RAM)
        available_ram = resources['ram_free_gb'] * 0.8

        if available_ram >= requirements.ram_gb:
            logger.debug(f"Model {model_name} can run on CPU")
            return True

        logger.debug(
            f"Model {model_name} needs {requirements.ram_gb}GB RAM, "
            f"only {available_ram:.1f}GB available (with margin)"
        )
        return False

    def _get_model_requirements(self, model_name: str) -> Optional[ModelRequirements]:
        """Get resource requirements for a model.

        Args:
            model_name: Model name/tag.

        Returns:
            ModelRequirements or None if unknown model.
        """
        # Direct lookup
        if model_name in MODEL_CATALOG:
            return MODEL_CATALOG[model_name]

        # Try without version tag
        base_name = model_name.split(':')[0]
        for catalog_name, requirements in MODEL_CATALOG.items():
            if catalog_name.startswith(base_name):
                return requirements

        # Estimate based on model name patterns
        return self._estimate_requirements(model_name)

    def _estimate_requirements(self, model_name: str) -> Optional[ModelRequirements]:
        """Estimate requirements for unknown models based on naming patterns.

        Args:
            model_name: Model name to estimate requirements for.

        Returns:
            Estimated ModelRequirements or None.
        """
        name_lower = model_name.lower()

        # Pattern-based estimation
        if any(x in name_lower for x in ['70b', '72b', '65b']):
            return ModelRequirements(
                ram_gb=48.0, vram_gb=40.0, context_length=8192,
                cpu_threads=16, quality_tier=1
            )
        elif any(x in name_lower for x in ['34b', '33b', '30b']):
            return ModelRequirements(
                ram_gb=24.0, vram_gb=20.0, context_length=8192,
                cpu_threads=12, quality_tier=2
            )
        elif any(x in name_lower for x in ['13b', '14b', '8b', '7b']):
            return ModelRequirements(
                ram_gb=8.0, vram_gb=6.0, context_length=8192,
                cpu_threads=8, quality_tier=2
            )
        elif any(x in name_lower for x in ['3b', '2b', '1b']):
            return ModelRequirements(
                ram_gb=4.0, vram_gb=2.0, context_length=4096,
                cpu_threads=4, quality_tier=3
            )
        elif any(x in name_lower for x in ['mini', 'tiny', 'small']):
            return ModelRequirements(
                ram_gb=2.0, vram_gb=1.0, context_length=2048,
                cpu_threads=2, quality_tier=4
            )

        # Default for unknown models
        logger.debug(f"Using default requirements for unknown model: {model_name}")
        return ModelRequirements(
            ram_gb=8.0, vram_gb=6.0, context_length=4096,
            cpu_threads=4, quality_tier=3
        )

    def get_execution_config(
        self,
        model_name: str,
        context_size: Optional[int] = None,
        temperature: float = 0.7,
        force_cpu: bool = False
    ) -> Dict[str, Any]:
        """Get execution configuration for a model.

        Creates an optimized configuration based on model requirements
        and current system resources.

        Args:
            model_name: Model name/tag to configure.
            context_size: Override context window size. Uses model default if None.
            temperature: Generation temperature (0.0-2.0).
            force_cpu: Force CPU execution even if GPU available.

        Returns:
            Dictionary with execution configuration suitable for Ollama.

        Example:
            >>> selector = OllamaModelSelector()
            >>> config = selector.get_execution_config('llama3.1:8b')
            >>> print(config)
            {'model': 'llama3.1:8b', 'num_ctx': 8192, 'num_gpu': 35, ...}
        """
        resources = self.resource_monitor.get_current_resources()
        requirements = self._get_model_requirements(model_name)

        # Default requirements if unknown model
        if requirements is None:
            requirements = ModelRequirements(
                ram_gb=8.0, vram_gb=6.0, context_length=4096,
                cpu_threads=4, quality_tier=3
            )

        # Determine context size
        if context_size is None:
            # Use smaller of model max and 8192 for efficiency
            context_size = min(requirements.context_length, 8192)

        # Determine GPU usage
        use_gpu = False
        num_gpu = 0

        if not force_cpu and resources['gpu_available']:
            if resources['vram_free_gb'] >= requirements.vram_gb:
                use_gpu = True
                # Use all GPU layers when sufficient VRAM
                num_gpu = -1
            elif resources['vram_free_gb'] >= requirements.vram_gb * 0.5:
                # Partial GPU offload
                use_gpu = True
                num_gpu = int(35 * (resources['vram_free_gb'] / requirements.vram_gb))

        # Determine thread count
        num_threads = min(
            requirements.cpu_threads,
            resources['cpu_cores'],
            resources['cpu_cores_logical']
        )

        config = ModelConfig(
            model=model_name,
            num_ctx=context_size,
            num_gpu=num_gpu,
            num_thread=num_threads,
            use_gpu=use_gpu,
            temperature=temperature
        )

        logger.info(
            f"Execution config for {model_name}: "
            f"ctx={context_size}, gpu={num_gpu}, threads={num_threads}"
        )

        return config.to_dict()

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get detailed information about a model.

        Args:
            model_name: Model name/tag.

        Returns:
            Dictionary with model information.
        """
        requirements = self._get_model_requirements(model_name)
        is_available = model_name in self.available_models

        info = {
            'name': model_name,
            'available': is_available,
            'requirements': None,
            'can_run': False,
            'execution_mode': None
        }

        if requirements:
            info['requirements'] = {
                'ram_gb': requirements.ram_gb,
                'vram_gb': requirements.vram_gb,
                'context_length': requirements.context_length,
                'cpu_threads': requirements.cpu_threads,
                'quality_tier': requirements.quality_tier
            }

            resources = self.resource_monitor.get_current_resources()
            info['can_run'] = self._can_run_model(
                model_name, resources, 4096, True
            )

            if info['can_run']:
                if resources['gpu_available'] and resources['vram_free_gb'] >= requirements.vram_gb:
                    info['execution_mode'] = 'gpu'
                else:
                    info['execution_mode'] = 'cpu'

        return info

    def list_runnable_models(
        self,
        task_complexity: str = 'medium'
    ) -> List[Dict[str, Any]]:
        """List all models that can run with current resources.

        Args:
            task_complexity: Filter by complexity level.

        Returns:
            List of model info dictionaries, sorted by preference.
        """
        try:
            complexity = TaskComplexity(task_complexity.lower())
        except ValueError:
            complexity = TaskComplexity.MEDIUM

        preference_order = MODEL_PREFERENCES.get(
            complexity,
            MODEL_PREFERENCES[TaskComplexity.MEDIUM]
        )

        resources = self.resource_monitor.get_current_resources()
        runnable = []

        for model_name in preference_order:
            if self._can_run_model(model_name, resources, 4096, True):
                info = self.get_model_info(model_name)
                runnable.append(info)

        return runnable

    def get_recommendation(
        self,
        task_description: str = "",
        required_context: int = 4096
    ) -> Dict[str, Any]:
        """Get a complete recommendation for model selection.

        Analyzes the task and resources to provide a comprehensive
        recommendation including model, configuration, and alternatives.

        Args:
            task_description: Description of the task (used for complexity estimation).
            required_context: Required context window size.

        Returns:
            Dictionary with recommendation details.

        Example:
            >>> selector = OllamaModelSelector()
            >>> rec = selector.get_recommendation(
            ...     task_description="Analyze code quality",
            ...     required_context=8192
            ... )
            >>> print(rec['selected_model'])
            llama3.1:8b
        """
        # Estimate complexity from description
        complexity = self._estimate_complexity(task_description)

        # Select model
        selected = self.select_best_model(
            task_complexity=complexity.value,
            required_context=required_context
        )

        # Get config
        config = self.get_execution_config(selected)

        # Get alternatives
        alternatives = self.list_runnable_models(complexity.value)[:3]

        return {
            'selected_model': selected,
            'estimated_complexity': complexity.value,
            'execution_config': config,
            'alternatives': [m['name'] for m in alternatives if m['name'] != selected],
            'resources': self.resource_monitor.get_current_resources()
        }

    def _estimate_complexity(self, task_description: str) -> TaskComplexity:
        """Estimate task complexity from description.

        Args:
            task_description: Task description text.

        Returns:
            Estimated TaskComplexity level.
        """
        desc_lower = task_description.lower()

        # Keywords for complexity estimation
        expert_keywords = ['reason', 'complex', 'expert', 'advanced', 'multi-step']
        complex_keywords = ['analyze', 'code', 'generate', 'write', 'create']
        simple_keywords = ['classify', 'extract', 'simple', 'basic', 'quick']

        if any(kw in desc_lower for kw in expert_keywords):
            return TaskComplexity.EXPERT
        elif any(kw in desc_lower for kw in complex_keywords):
            return TaskComplexity.COMPLEX
        elif any(kw in desc_lower for kw in simple_keywords):
            return TaskComplexity.SIMPLE

        return TaskComplexity.MEDIUM
