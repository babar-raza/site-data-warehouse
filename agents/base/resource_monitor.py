"""
System Resource Monitor for LLM-Aware Execution

Monitors system resources (RAM, CPU, GPU) to enable resource-aware LLM execution.
Prevents system overload during intensive AI operations by checking resource
availability before scheduling LLM tasks.

Example usage:
    >>> from agents.base.resource_monitor import SystemResourceMonitor
    >>> monitor = SystemResourceMonitor()
    >>> resources = monitor.get_current_resources()
    >>> print(f"RAM Free: {resources['ram_free_gb']:.2f} GB")
    >>> if not monitor.is_system_overloaded():
    ...     # Safe to run LLM task
    ...     pass
"""
import logging
import os
import platform
from dataclasses import dataclass
from typing import Dict, Any, Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ResourceThresholds:
    """Configurable resource thresholds for overload detection.

    Attributes:
        ram_usage_pct: Maximum RAM usage percentage (0-100) before overload.
        cpu_usage_pct: Maximum CPU usage percentage (0-100) before overload.
        min_ram_free_gb: Minimum free RAM in GB required for LLM tasks.
        min_vram_free_gb: Minimum free VRAM in GB required for GPU LLM tasks.
    """
    ram_usage_pct: float = 85.0
    cpu_usage_pct: float = 90.0
    min_ram_free_gb: float = 2.0
    min_vram_free_gb: float = 2.0


class SystemResourceMonitor:
    """Monitor system resources to prevent choking during LLM execution.

    This class provides methods to check system resource availability
    (RAM, CPU, GPU) and determine if the system is overloaded. It enables
    resource-aware scheduling of LLM tasks to prevent system degradation.

    Attributes:
        thresholds: Resource thresholds for overload detection.

    Example:
        >>> monitor = SystemResourceMonitor()
        >>> resources = monitor.get_current_resources()
        >>> print(f"CPU Usage: {resources['cpu_usage_pct']}%")
        >>> print(f"RAM Free: {resources['ram_free_gb']:.2f} GB")
        >>> print(f"GPU Available: {resources['gpu_available']}")

        >>> if monitor.is_system_overloaded():
        ...     print("System overloaded, deferring LLM task")
        ... else:
        ...     print("System ready for LLM task")
    """

    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        cpu_sample_interval: float = 0.5
    ):
        """Initialize the SystemResourceMonitor.

        Args:
            thresholds: Custom resource thresholds. Uses defaults if None.
            cpu_sample_interval: Seconds to sample CPU usage (default 0.5).
                Lower values are faster but less accurate.
        """
        self.thresholds = thresholds or ResourceThresholds()
        self._cpu_sample_interval = cpu_sample_interval
        self._last_resources: Optional[Dict[str, Any]] = None

        logger.debug(
            f"SystemResourceMonitor initialized with thresholds: "
            f"RAM={self.thresholds.ram_usage_pct}%, "
            f"CPU={self.thresholds.cpu_usage_pct}%"
        )

    def get_current_resources(self) -> Dict[str, Any]:
        """Get current system resource availability.

        Collects real-time information about RAM, CPU, and GPU resources.
        GPU detection requires PyTorch with CUDA support; if unavailable,
        GPU fields will show as unavailable.

        Returns:
            Dict containing:
                - ram_total_gb: Total RAM in gigabytes
                - ram_free_gb: Available RAM in gigabytes
                - ram_used_gb: Used RAM in gigabytes
                - ram_usage_pct: RAM usage as percentage (0-100)
                - cpu_cores: Number of physical CPU cores
                - cpu_cores_logical: Number of logical CPU cores
                - cpu_usage_pct: Current CPU usage percentage (0-100)
                - cpu_freq_mhz: Current CPU frequency in MHz (if available)
                - gpu_available: Boolean indicating GPU availability
                - gpu_name: GPU device name (if available)
                - vram_total_gb: Total GPU VRAM in gigabytes (if available)
                - vram_free_gb: Free GPU VRAM in gigabytes (if available)
                - vram_used_gb: Used GPU VRAM in gigabytes (if available)
                - platform: Operating system platform
                - hostname: Machine hostname

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> resources = monitor.get_current_resources()
            >>> print(f"RAM: {resources['ram_free_gb']:.1f}/{resources['ram_total_gb']:.1f} GB")
            RAM: 8.5/16.0 GB
        """
        # RAM information
        ram = psutil.virtual_memory()
        ram_total_gb = ram.total / (1024 ** 3)
        ram_free_gb = ram.available / (1024 ** 3)
        ram_used_gb = ram.used / (1024 ** 3)

        # CPU information
        cpu_cores = psutil.cpu_count(logical=False) or 1
        cpu_cores_logical = psutil.cpu_count(logical=True) or 1
        cpu_usage_pct = psutil.cpu_percent(interval=self._cpu_sample_interval)

        # CPU frequency (may not be available on all systems)
        cpu_freq_mhz = None
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_freq_mhz = freq.current
        except Exception:
            pass

        # GPU information (optional - requires torch with CUDA)
        gpu_available = False
        gpu_name = None
        vram_total_gb = 0.0
        vram_free_gb = 0.0
        vram_used_gb = 0.0

        gpu_info = self._detect_gpu()
        if gpu_info:
            gpu_available = True
            gpu_name = gpu_info.get('name')
            vram_total_gb = gpu_info.get('vram_total_gb', 0.0)
            vram_free_gb = gpu_info.get('vram_free_gb', 0.0)
            vram_used_gb = gpu_info.get('vram_used_gb', 0.0)

        resources = {
            'ram_total_gb': ram_total_gb,
            'ram_free_gb': ram_free_gb,
            'ram_used_gb': ram_used_gb,
            'ram_usage_pct': ram.percent,
            'cpu_cores': cpu_cores,
            'cpu_cores_logical': cpu_cores_logical,
            'cpu_usage_pct': cpu_usage_pct,
            'cpu_freq_mhz': cpu_freq_mhz,
            'gpu_available': gpu_available,
            'gpu_name': gpu_name,
            'vram_total_gb': vram_total_gb,
            'vram_free_gb': vram_free_gb,
            'vram_used_gb': vram_used_gb,
            'platform': platform.system(),
            'hostname': platform.node(),
        }

        # Cache for subsequent calls
        self._last_resources = resources

        logger.debug(
            f"Resources: RAM {ram_free_gb:.1f}/{ram_total_gb:.1f} GB free, "
            f"CPU {cpu_usage_pct:.1f}%, GPU={'yes' if gpu_available else 'no'}"
        )

        return resources

    def _detect_gpu(self) -> Optional[Dict[str, Any]]:
        """Detect GPU availability and VRAM.

        Attempts to detect NVIDIA GPU using PyTorch CUDA support.
        Falls back gracefully if torch is not available.

        Returns:
            Dict with GPU info if available, None otherwise.
        """
        try:
            import torch

            if not torch.cuda.is_available():
                logger.debug("CUDA not available")
                return None

            # Get GPU device info
            device_count = torch.cuda.device_count()
            if device_count == 0:
                return None

            # Use first GPU
            device_id = 0
            gpu_name = torch.cuda.get_device_name(device_id)

            # Get VRAM info
            vram_free, vram_total = torch.cuda.mem_get_info(device_id)
            vram_total_gb = vram_total / (1024 ** 3)
            vram_free_gb = vram_free / (1024 ** 3)
            vram_used_gb = vram_total_gb - vram_free_gb

            logger.info(
                f"GPU detected: {gpu_name} with "
                f"{vram_free_gb:.1f}/{vram_total_gb:.1f} GB VRAM free"
            )

            return {
                'name': gpu_name,
                'device_id': device_id,
                'device_count': device_count,
                'vram_total_gb': vram_total_gb,
                'vram_free_gb': vram_free_gb,
                'vram_used_gb': vram_used_gb,
            }

        except ImportError:
            logger.debug("torch not available, GPU detection skipped")
            return None
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
            return None

    def is_system_overloaded(self) -> bool:
        """Check if system is currently overloaded.

        Evaluates current resource usage against configured thresholds.
        Returns True if any threshold is exceeded, indicating the system
        should not accept additional LLM workloads.

        Returns:
            True if system is overloaded, False if resources are available.

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> if monitor.is_system_overloaded():
            ...     print("Deferring LLM task - system overloaded")
            ... else:
            ...     print("System ready for LLM task")
        """
        resources = self.get_current_resources()

        # Check RAM usage percentage
        if resources['ram_usage_pct'] > self.thresholds.ram_usage_pct:
            logger.warning(
                f"System RAM usage high ({resources['ram_usage_pct']:.1f}% > "
                f"{self.thresholds.ram_usage_pct}%), deferring LLM task"
            )
            return True

        # Check minimum free RAM
        if resources['ram_free_gb'] < self.thresholds.min_ram_free_gb:
            logger.warning(
                f"System RAM low ({resources['ram_free_gb']:.1f} GB < "
                f"{self.thresholds.min_ram_free_gb} GB), deferring LLM task"
            )
            return True

        # Check CPU usage percentage
        if resources['cpu_usage_pct'] > self.thresholds.cpu_usage_pct:
            logger.warning(
                f"System CPU usage high ({resources['cpu_usage_pct']:.1f}% > "
                f"{self.thresholds.cpu_usage_pct}%), deferring LLM task"
            )
            return True

        logger.debug("System resources available for LLM task")
        return False

    def is_gpu_available_for_llm(self, min_vram_gb: Optional[float] = None) -> bool:
        """Check if GPU has enough VRAM for LLM task.

        Args:
            min_vram_gb: Minimum VRAM required. Uses threshold default if None.

        Returns:
            True if GPU is available with sufficient VRAM, False otherwise.

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> if monitor.is_gpu_available_for_llm(min_vram_gb=4.0):
            ...     print("GPU available for large model")
            ... else:
            ...     print("Using CPU or smaller model")
        """
        resources = self.get_current_resources()

        if not resources['gpu_available']:
            logger.debug("No GPU available")
            return False

        min_vram = min_vram_gb or self.thresholds.min_vram_free_gb

        if resources['vram_free_gb'] < min_vram:
            logger.warning(
                f"GPU VRAM low ({resources['vram_free_gb']:.1f} GB < "
                f"{min_vram} GB), using CPU fallback"
            )
            return False

        logger.debug(
            f"GPU available with {resources['vram_free_gb']:.1f} GB VRAM free"
        )
        return True

    def get_recommended_model_size(self) -> str:
        """Get recommended LLM model size based on available resources.

        Analyzes system resources and recommends an appropriate model size
        for local LLM inference (e.g., with Ollama).

        Returns:
            Recommended model size string: 'large', 'medium', 'small', or 'tiny'.

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> model_size = monitor.get_recommended_model_size()
            >>> print(f"Recommended model: {model_size}")
            Recommended model: medium
        """
        resources = self.get_current_resources()

        # GPU-based recommendations
        if resources['gpu_available']:
            vram_free = resources['vram_free_gb']

            if vram_free >= 12:
                return 'large'  # e.g., llama2:13b, codellama:13b
            elif vram_free >= 8:
                return 'medium'  # e.g., llama2:7b, mistral
            elif vram_free >= 4:
                return 'small'  # e.g., phi-2, gemma:2b
            else:
                return 'tiny'  # e.g., tinyllama

        # CPU-based recommendations (based on RAM)
        ram_free = resources['ram_free_gb']

        if ram_free >= 16:
            return 'medium'  # Can run 7B models on CPU
        elif ram_free >= 8:
            return 'small'  # 2-3B models
        else:
            return 'tiny'  # Very small models only

    def wait_for_resources(
        self,
        timeout_seconds: float = 60.0,
        check_interval: float = 5.0
    ) -> bool:
        """Wait for system resources to become available.

        Polls system resources until they fall below thresholds or timeout.
        Useful for queuing LLM tasks during high-load periods.

        Args:
            timeout_seconds: Maximum time to wait in seconds.
            check_interval: Time between resource checks in seconds.

        Returns:
            True if resources became available, False if timeout reached.

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> if monitor.wait_for_resources(timeout_seconds=30):
            ...     # Run LLM task
            ...     pass
            ... else:
            ...     print("Timeout waiting for resources")
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if not self.is_system_overloaded():
                logger.info("System resources available")
                return True

            logger.debug(
                f"Waiting for resources... "
                f"({time.time() - start_time:.1f}s elapsed)"
            )
            time.sleep(check_interval)

        logger.warning(
            f"Timeout ({timeout_seconds}s) waiting for system resources"
        )
        return False

    def get_resource_summary(self) -> str:
        """Get human-readable summary of system resources.

        Returns:
            Formatted string summarizing system resources.

        Example:
            >>> monitor = SystemResourceMonitor()
            >>> print(monitor.get_resource_summary())
            System Resources:
              RAM: 8.5/16.0 GB (53% used)
              CPU: 4 cores @ 45% usage
              GPU: NVIDIA RTX 3080 (6.2/10.0 GB VRAM free)
        """
        resources = self.get_current_resources()

        lines = ["System Resources:"]

        # RAM
        lines.append(
            f"  RAM: {resources['ram_free_gb']:.1f}/{resources['ram_total_gb']:.1f} GB "
            f"({resources['ram_usage_pct']:.0f}% used)"
        )

        # CPU
        cpu_info = f"  CPU: {resources['cpu_cores']} cores @ {resources['cpu_usage_pct']:.0f}% usage"
        if resources['cpu_freq_mhz']:
            cpu_info += f" ({resources['cpu_freq_mhz']:.0f} MHz)"
        lines.append(cpu_info)

        # GPU
        if resources['gpu_available']:
            lines.append(
                f"  GPU: {resources['gpu_name']} "
                f"({resources['vram_free_gb']:.1f}/{resources['vram_total_gb']:.1f} GB VRAM free)"
            )
        else:
            lines.append("  GPU: Not available")

        # Status
        is_overloaded = self.is_system_overloaded()
        status = "OVERLOADED" if is_overloaded else "OK"
        lines.append(f"  Status: {status}")

        return "\n".join(lines)
