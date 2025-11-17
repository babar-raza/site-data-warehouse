#!/usr/bin/env python3
"""
Enterprise-Grade Rate Limiter for Google Search Console API
Implements token bucket algorithm with exponential backoff and monitoring
"""

import time
import threading
import logging
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    requests_per_minute: int = 30  # Conservative limit
    requests_per_day: int = 2000  # GSC API quota
    burst_size: int = 5  # Allow small bursts
    cooldown_seconds: float = 2.0  # Minimum time between requests
    max_retries: int = 5  # Maximum retry attempts
    base_backoff: float = 2.0  # Base backoff in seconds
    max_backoff: float = 300.0  # Maximum backoff (5 minutes)
    jitter: bool = True  # Add randomness to backoff


class TokenBucket:
    """Thread-safe token bucket for rate limiting"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket
        
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
        
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens consumed successfully, False otherwise
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
            
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
        
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate time to wait for tokens to be available"""
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class EnterprisRateLimiter:
    """
    Enterprise-grade rate limiter with multiple strategies:
    - Token bucket for smooth rate limiting
    - Per-property limits
    - Daily quotas
    - Exponential backoff with jitter
    - Request tracking and metrics
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter with configuration"""
        self.config = config or RateLimitConfig()
        
        # Token buckets for different time windows
        self.minute_bucket = TokenBucket(
            capacity=self.config.requests_per_minute,
            refill_rate=self.config.requests_per_minute / 60.0
        )
        
        self.burst_bucket = TokenBucket(
            capacity=self.config.burst_size,
            refill_rate=self.config.burst_size / 10.0  # Refill burst over 10 seconds
        )
        
        # Per-property tracking
        self.property_requests: Dict[str, int] = defaultdict(int)
        self.property_last_request: Dict[str, float] = {}
        self.daily_requests = 0
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
        
        # Backoff tracking
        self.consecutive_failures = 0
        self.backoff_until: Optional[float] = None
        
        # Metrics
        self.total_requests = 0
        self.total_throttled = 0
        self.total_retries = 0
        self.lock = threading.Lock()
        
        logger.info(f"Rate limiter initialized: {self.config.requests_per_minute} req/min, "
                   f"{self.config.requests_per_day} req/day")
        
    def acquire(self, property_url: str) -> float:
        """
        Acquire permission to make a request
        
        Args:
            property_url: GSC property URL
            
        Returns:
            Time to wait before making request (0.0 if immediate)
        """
        with self.lock:
            # Check if in backoff period
            if self.backoff_until and time.time() < self.backoff_until:
                wait_time = self.backoff_until - time.time()
                logger.debug(f"In backoff period, wait {wait_time:.2f}s")
                return wait_time
                
            # Reset daily quota if needed
            if datetime.now() >= self.daily_reset_time:
                self.daily_requests = 0
                self.daily_reset_time = datetime.now().replace(
                    hour=0, minute=0, second=0
                ) + timedelta(days=1)
                logger.info("Daily quota reset")
                
            # Check daily quota
            if self.daily_requests >= self.config.requests_per_day:
                logger.warning(f"Daily quota exceeded: {self.daily_requests}/{self.config.requests_per_day}")
                # Wait until tomorrow
                time_until_reset = (self.daily_reset_time - datetime.now()).total_seconds()
                return max(0, time_until_reset)
                
            # Check per-property cooldown
            if property_url in self.property_last_request:
                time_since_last = time.time() - self.property_last_request[property_url]
                if time_since_last < self.config.cooldown_seconds:
                    wait_time = self.config.cooldown_seconds - time_since_last
                    return wait_time
                    
            # Try to consume from token buckets
            minute_wait = self.minute_bucket.wait_time()
            burst_wait = self.burst_bucket.wait_time()
            wait_time = max(minute_wait, burst_wait)
            
            if wait_time > 0:
                self.total_throttled += 1
                logger.debug(f"Rate limited, wait {wait_time:.2f}s")
                return wait_time
                
            # Consume tokens
            self.minute_bucket.consume()
            self.burst_bucket.consume()
            
            # Update tracking
            self.property_last_request[property_url] = time.time()
            self.property_requests[property_url] += 1
            self.daily_requests += 1
            self.total_requests += 1
            
            return 0.0
            
    def record_success(self):
        """Record successful request"""
        with self.lock:
            self.consecutive_failures = 0
            self.backoff_until = None
            
    def record_failure(self, is_rate_limit: bool = False):
        """
        Record failed request and apply backoff
        
        Args:
            is_rate_limit: Whether failure was due to rate limiting
        """
        with self.lock:
            self.consecutive_failures += 1
            self.total_retries += 1
            
            if is_rate_limit:
                # Apply exponential backoff
                backoff = min(
                    self.config.base_backoff * (2 ** self.consecutive_failures),
                    self.config.max_backoff
                )
                
                # Add jitter if enabled
                if self.config.jitter:
                    import random
                    jitter = random.uniform(0, backoff * 0.1)
                    backoff += jitter
                    
                self.backoff_until = time.time() + backoff
                logger.warning(f"Rate limit hit, backing off for {backoff:.2f}s "
                             f"(attempt {self.consecutive_failures})")
                             
    def get_backoff_time(self) -> float:
        """
        Calculate exponential backoff time
        
        Returns:
            Backoff duration in seconds
        """
        if self.consecutive_failures == 0:
            return 0.0
            
        backoff = min(
            self.config.base_backoff * (2 ** (self.consecutive_failures - 1)),
            self.config.max_backoff
        )
        
        if self.config.jitter:
            import random
            jitter = random.uniform(0, backoff * 0.1)
            backoff += jitter
            
        return backoff
        
    def should_retry(self) -> bool:
        """Check if should retry after failure"""
        return self.consecutive_failures < self.config.max_retries
        
    def get_metrics(self) -> Dict[str, any]:
        """Get rate limiter metrics"""
        with self.lock:
            return {
                'total_requests': self.total_requests,
                'total_throttled': self.total_throttled,
                'total_retries': self.total_retries,
                'daily_requests': self.daily_requests,
                'daily_quota_remaining': self.config.requests_per_day - self.daily_requests,
                'consecutive_failures': self.consecutive_failures,
                'in_backoff': self.backoff_until is not None and time.time() < self.backoff_until,
                'properties_tracked': len(self.property_requests),
                'throttle_rate': self.total_throttled / max(1, self.total_requests)
            }
            
    def reset_backoff(self):
        """Reset backoff state (use with caution)"""
        with self.lock:
            self.consecutive_failures = 0
            self.backoff_until = None
            logger.info("Backoff state reset")
