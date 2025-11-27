"""
Resource-Aware Rate Limiter for LLM Operations
==============================================
Adaptive rate limiting based on available GPU/CPU resources.

Features:
- Detects GPU availability via CUDA environment
- Checks CPU cores and memory
- Configures concurrent limits accordingly
- Async-compatible semaphore implementation
- Requests-per-minute tracking

Usage:
    from insights_core.prompts.rate_limiter import (
        ResourceAwareRateLimiter,
        get_resource_limits
    )

    limiter = ResourceAwareRateLimiter()

    async def process_batch(items):
        for item in items:
            await limiter.acquire()
            try:
                result = await process_item(item)
            finally:
                limiter.release()
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResourceLimits:
    """Resource-based rate limits."""

    max_concurrent: int
    requests_per_minute: int
    batch_size: int
    tier: str  # "gpu", "high_cpu", "standard"


def get_resource_limits() -> ResourceLimits:
    """
    Determine rate limits based on available system resources.

    Checks for:
    - GPU availability (CUDA_VISIBLE_DEVICES or NVIDIA driver)
    - CPU core count
    - Available memory

    Returns:
        ResourceLimits with appropriate settings
    """
    try:
        import psutil
        cpu_count = psutil.cpu_count() or 4
        memory_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        # Fallback if psutil not available
        cpu_count = os.cpu_count() or 4
        memory_gb = 8  # Assume 8GB

    # Check for GPU
    has_gpu = (
        os.environ.get("CUDA_VISIBLE_DEVICES") is not None
        or os.path.exists("/dev/nvidia0")
        or os.environ.get("NVIDIA_VISIBLE_DEVICES") is not None
    )

    if has_gpu:
        logger.info("GPU detected - using high-performance limits")
        return ResourceLimits(
            max_concurrent=3,
            requests_per_minute=30,
            batch_size=10,
            tier="gpu"
        )
    elif cpu_count >= 8 and memory_gb >= 32:
        logger.info(f"High-spec CPU detected ({cpu_count} cores, {memory_gb:.1f}GB) - using medium limits")
        return ResourceLimits(
            max_concurrent=2,
            requests_per_minute=15,
            batch_size=5,
            tier="high_cpu"
        )
    else:
        logger.info(f"Standard hardware ({cpu_count} cores, {memory_gb:.1f}GB) - using conservative limits")
        return ResourceLimits(
            max_concurrent=1,
            requests_per_minute=6,
            batch_size=3,
            tier="standard"
        )


class ResourceAwareRateLimiter:
    """
    Rate limiter that adapts to available system resources.

    Provides both concurrency limiting (semaphore) and
    requests-per-minute limiting (sliding window).
    """

    def __init__(
        self,
        limits: Optional[ResourceLimits] = None,
        max_concurrent: Optional[int] = None,
        requests_per_minute: Optional[int] = None
    ):
        """
        Initialize rate limiter.

        Args:
            limits: Pre-computed ResourceLimits (auto-detected if None)
            max_concurrent: Override for max concurrent requests
            requests_per_minute: Override for RPM limit
        """
        if limits is None:
            limits = get_resource_limits()

        self._limits = limits
        self._max_concurrent = max_concurrent or limits.max_concurrent
        self._rpm_limit = requests_per_minute or limits.requests_per_minute

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._request_times: List[datetime] = []
        self._lock = asyncio.Lock()

        logger.info(
            f"Rate limiter initialized: max_concurrent={self._max_concurrent}, "
            f"rpm={self._rpm_limit}, tier={limits.tier}"
        )

    async def acquire(self) -> None:
        """
        Acquire rate limit slot, waiting if necessary.

        This method will block if:
        - Max concurrent requests reached (semaphore)
        - RPM limit reached (must wait for oldest request to expire)
        """
        # Concurrent limit
        await self._semaphore.acquire()

        # RPM limit
        async with self._lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)

            # Clean old entries
            self._request_times = [
                t for t in self._request_times if t > minute_ago
            ]

            # Check if we need to wait
            if len(self._request_times) >= self._rpm_limit:
                # Wait until oldest request expires
                oldest = self._request_times[0]
                wait_seconds = (oldest + timedelta(minutes=1) - now).total_seconds()

                if wait_seconds > 0:
                    logger.debug(f"RPM limit reached, waiting {wait_seconds:.1f}s")
                    await asyncio.sleep(wait_seconds)

                    # Clean again after waiting
                    now = datetime.now()
                    minute_ago = now - timedelta(minutes=1)
                    self._request_times = [
                        t for t in self._request_times if t > minute_ago
                    ]

            self._request_times.append(now)

    def release(self) -> None:
        """Release rate limit slot."""
        self._semaphore.release()

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False

    @property
    def limits(self) -> ResourceLimits:
        """Get current resource limits."""
        return self._limits

    @property
    def current_rpm(self) -> int:
        """Get current requests in the last minute."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        return len([t for t in self._request_times if t > minute_ago])

    @property
    def available_slots(self) -> int:
        """Get number of available concurrent slots."""
        # Note: This is approximate due to semaphore internals
        return self._max_concurrent - (self._max_concurrent - self._semaphore._value)

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "tier": self._limits.tier,
            "max_concurrent": self._max_concurrent,
            "requests_per_minute_limit": self._rpm_limit,
            "current_rpm": self.current_rpm,
            "available_slots": self.available_slots,
        }


class SyncRateLimiter:
    """
    Synchronous rate limiter for non-async code.

    Uses threading primitives instead of asyncio.
    """

    def __init__(
        self,
        limits: Optional[ResourceLimits] = None,
        max_concurrent: Optional[int] = None,
        requests_per_minute: Optional[int] = None
    ):
        """Initialize synchronous rate limiter."""
        import threading

        if limits is None:
            limits = get_resource_limits()

        self._limits = limits
        self._max_concurrent = max_concurrent or limits.max_concurrent
        self._rpm_limit = requests_per_minute or limits.requests_per_minute

        self._semaphore = threading.Semaphore(self._max_concurrent)
        self._request_times: List[datetime] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Acquire rate limit slot (blocking)."""
        import time

        self._semaphore.acquire()

        with self._lock:
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)

            self._request_times = [
                t for t in self._request_times if t > minute_ago
            ]

            if len(self._request_times) >= self._rpm_limit:
                oldest = self._request_times[0]
                wait_seconds = (oldest + timedelta(minutes=1) - now).total_seconds()

                if wait_seconds > 0:
                    time.sleep(wait_seconds)

                    now = datetime.now()
                    minute_ago = now - timedelta(minutes=1)
                    self._request_times = [
                        t for t in self._request_times if t > minute_ago
                    ]

            self._request_times.append(now)

    def release(self) -> None:
        """Release rate limit slot."""
        self._semaphore.release()

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False


# Global singleton for convenience
_default_limiter: Optional[ResourceAwareRateLimiter] = None


def get_default_limiter() -> ResourceAwareRateLimiter:
    """Get or create the default rate limiter singleton."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = ResourceAwareRateLimiter()
    return _default_limiter
