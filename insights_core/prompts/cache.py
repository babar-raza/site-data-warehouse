"""
Content-Hash Based Response Cache
=================================
Caching for LLM responses to speed up repeated requests without duplication.

Features:
- SHA256 hash of (prompt + model + schema) as cache key
- TTL-based expiration to allow content refresh
- LRU eviction when at capacity
- Stores validated Pydantic objects, not raw strings
- Thread-safe operations

Usage:
    from insights_core.prompts.cache import ResponseCache

    cache = ResponseCache(ttl_hours=24, max_entries=1000)

    # Check cache
    cached = cache.get(prompt, model, TitleOptimizationResponse)
    if cached:
        return cached

    # Generate and cache
    response = llm.generate(prompt)
    cache.set(prompt, model, TitleOptimizationResponse, response)
"""

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""

    response: BaseModel
    cached_at: datetime
    model: str
    schema_name: str
    hit_count: int = 0


class ResponseCache:
    """
    Content-hash based cache for LLM responses.

    Key features:
    - Uses SHA256 hash of (prompt + model + schema) as cache key
    - TTL-based expiration to allow content refresh
    - Stores validated Pydantic objects, not raw strings
    - No duplication: same input always returns cached result
    - Thread-safe with lock protection
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        max_entries: int = 1000
    ):
        """
        Initialize response cache.

        Args:
            ttl_hours: Time-to-live for cache entries in hours
            max_entries: Maximum number of entries before LRU eviction
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = timedelta(hours=ttl_hours)
        self._max_entries = max_entries
        self._lock = threading.RLock()

        # Statistics
        self._hits = 0
        self._misses = 0

        logger.debug(f"ResponseCache initialized: ttl={ttl_hours}h, max={max_entries}")

    def _make_key(
        self,
        prompt: str,
        model: str,
        schema: Type[BaseModel]
    ) -> str:
        """
        Generate cache key from prompt, model, and schema.

        The key is a SHA256 hash of the combined content to ensure:
        - Same input always produces same key
        - Different inputs produce different keys
        - Key size is fixed regardless of prompt length

        Args:
            prompt: The prompt string
            model: Model name
            schema: Pydantic schema class

        Returns:
            SHA256 hex digest as cache key
        """
        content = json.dumps({
            "prompt": prompt,
            "model": model,
            "schema": schema.__name__,
            "schema_fields": sorted(schema.model_fields.keys())
        }, sort_keys=True)

        return hashlib.sha256(content.encode()).hexdigest()

    def get(
        self,
        prompt: str,
        model: str,
        schema: Type[T]
    ) -> Optional[T]:
        """
        Get cached response if valid.

        Args:
            prompt: The prompt string
            model: Model name
            schema: Expected response schema

        Returns:
            Cached response if valid and not expired, None otherwise
        """
        key = self._make_key(prompt, model, schema)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if datetime.now() - entry.cached_at > self._ttl:
                del self._cache[key]
                self._misses += 1
                logger.debug(f"Cache entry expired: {schema.__name__}")
                return None

            # Verify schema matches
            if entry.schema_name != schema.__name__:
                self._misses += 1
                return None

            # Update hit count and return
            entry.hit_count += 1
            self._hits += 1
            logger.debug(f"Cache hit: {schema.__name__} (hits: {entry.hit_count})")

            return entry.response  # type: ignore

    def set(
        self,
        prompt: str,
        model: str,
        schema: Type[BaseModel],
        response: BaseModel
    ) -> None:
        """
        Cache a validated response.

        Args:
            prompt: The prompt string
            model: Model name
            schema: Response schema class
            response: Validated response to cache
        """
        key = self._make_key(prompt, model, schema)

        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self._max_entries:
                self._evict_oldest()

            self._cache[key] = CacheEntry(
                response=response,
                cached_at=datetime.now(),
                model=model,
                schema_name=schema.__name__,
                hit_count=0
            )

            logger.debug(f"Cached response: {schema.__name__} (total: {len(self._cache)})")

    def _evict_oldest(self) -> None:
        """Evict the oldest cache entry (LRU)."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].cached_at
        )
        del self._cache[oldest_key]
        logger.debug(f"Evicted oldest cache entry (capacity: {self._max_entries})")

    def invalidate(
        self,
        prompt: str,
        model: str,
        schema: Type[BaseModel]
    ) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            prompt: The prompt string
            model: Model name
            schema: Response schema class

        Returns:
            True if entry was found and removed, False otherwise
        """
        key = self._make_key(prompt, model, schema)

        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Invalidated cache entry: {schema.__name__}")
                return True
            return False

    def invalidate_by_schema(self, schema: Type[BaseModel]) -> int:
        """
        Invalidate all entries for a specific schema.

        Useful when a schema changes and cached responses may be invalid.

        Args:
            schema: Response schema class

        Returns:
            Number of entries removed
        """
        schema_name = schema.__name__

        with self._lock:
            keys_to_remove = [
                k for k, v in self._cache.items()
                if v.schema_name == schema_name
            ]

            for key in keys_to_remove:
                del self._cache[key]

            logger.info(f"Invalidated {len(keys_to_remove)} entries for {schema_name}")
            return len(keys_to_remove)

    def invalidate_by_model(self, model: str) -> int:
        """
        Invalidate all entries for a specific model.

        Useful when switching models and cached responses should be refreshed.

        Args:
            model: Model name

        Returns:
            Number of entries removed
        """
        with self._lock:
            keys_to_remove = [
                k for k, v in self._cache.items()
                if v.model == model
            ]

            for key in keys_to_remove:
                del self._cache[key]

            logger.info(f"Invalidated {len(keys_to_remove)} entries for model {model}")
            return len(keys_to_remove)

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info(f"Cache cleared: {count} entries removed")
            return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Can be called periodically to free memory.

        Returns:
            Number of entries removed
        """
        now = datetime.now()

        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if now - v.cached_at > self._ttl
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache metrics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0

            # Group by schema
            by_schema: Dict[str, int] = {}
            for entry in self._cache.values():
                by_schema[entry.schema_name] = by_schema.get(entry.schema_name, 0) + 1

            return {
                "entries": len(self._cache),
                "max_entries": self._max_entries,
                "ttl_hours": self._ttl.total_seconds() / 3600,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "by_schema": by_schema,
            }

    def __len__(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in cache."""
        return key in self._cache

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"ResponseCache(entries={stats['entries']}, "
            f"hit_rate={stats['hit_rate_percent']}%)"
        )
