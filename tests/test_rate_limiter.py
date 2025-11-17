#!/usr/bin/env python3
"""
Comprehensive tests for enterprise rate limiter
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestors', 'api'))

from rate_limiter import (
    TokenBucket, 
    EnterprisRateLimiter, 
    RateLimitConfig
)


class TestTokenBucket:
    """Tests for TokenBucket class"""
    
    def test_initialization(self):
        """Test token bucket initialization"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.capacity == 10
        assert bucket.tokens == 10
        assert bucket.refill_rate == 1.0
        
    def test_consume_success(self):
        """Test successful token consumption"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.consume(3) is True
        assert abs(bucket.tokens - 2) < 0.01  # Allow small time-based drift
        
    def test_consume_failure(self):
        """Test token consumption failure when insufficient tokens"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.consume(8)
        assert bucket.consume(5) is False
        assert abs(bucket.tokens - 2) < 0.01  # Tokens not consumed on failure, allow drift
        
    def test_refill(self):
        """Test token refill over time"""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        bucket.consume(10)  # Empty bucket
        
        time.sleep(0.5)  # Wait 0.5 seconds
        bucket._refill()
        
        # Should have ~5 tokens after 0.5 seconds at 10 tokens/sec
        assert 4 <= bucket.tokens <= 6
        
    def test_wait_time(self):
        """Test wait time calculation"""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        bucket.consume(10)  # Empty bucket
        
        # Need 5 tokens at 1 token/sec = 5 seconds wait
        wait = bucket.wait_time(5)
        assert 4.5 <= wait <= 5.5
        
    def test_thread_safety(self):
        """Test thread-safe token consumption"""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        results = []
        
        def consume_tokens():
            for _ in range(10):
                result = bucket.consume(1)
                results.append(result)
                
        threads = [threading.Thread(target=consume_tokens) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # 50 attempts, bucket has 100 capacity, all should succeed
        assert all(results)


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = RateLimitConfig()
        assert config.requests_per_minute == 30
        assert config.requests_per_day == 2000
        assert config.burst_size == 5
        assert config.cooldown_seconds == 2.0
        assert config.max_retries == 5
        assert config.base_backoff == 2.0
        assert config.max_backoff == 300.0
        assert config.jitter is True
        
    def test_custom_config(self):
        """Test custom configuration"""
        config = RateLimitConfig(
            requests_per_minute=50,
            requests_per_day=3000,
            burst_size=10,
            jitter=False
        )
        assert config.requests_per_minute == 50
        assert config.requests_per_day == 3000
        assert config.burst_size == 10
        assert config.jitter is False


class TestEnterprisRateLimiter:
    """Tests for EnterprisRateLimiter class"""
    
    def test_initialization(self):
        """Test rate limiter initialization"""
        config = RateLimitConfig(requests_per_minute=30)
        limiter = EnterprisRateLimiter(config)
        
        assert limiter.config.requests_per_minute == 30
        assert limiter.total_requests == 0
        assert limiter.daily_requests == 0
        assert limiter.consecutive_failures == 0
        
    def test_acquire_immediate(self):
        """Test immediate request acquisition"""
        limiter = EnterprisRateLimiter()
        wait_time = limiter.acquire("https://example.com/")
        
        assert wait_time == 0.0
        assert limiter.total_requests == 1
        assert limiter.daily_requests == 1
        
    def test_acquire_with_cooldown(self):
        """Test cooldown between requests"""
        config = RateLimitConfig(cooldown_seconds=1.0)
        limiter = EnterprisRateLimiter(config)
        
        # First request
        wait1 = limiter.acquire("https://example.com/")
        assert wait1 == 0.0
        
        # Second request immediately after - should wait
        wait2 = limiter.acquire("https://example.com/")
        assert 0.8 <= wait2 <= 1.2
        
    def test_per_property_tracking(self):
        """Test per-property rate limiting"""
        limiter = EnterprisRateLimiter()
        
        # Different properties should not interfere
        wait1 = limiter.acquire("https://example1.com/")
        wait2 = limiter.acquire("https://example2.com/")
        
        assert wait1 == 0.0
        assert wait2 == 0.0
        assert "https://example1.com/" in limiter.property_requests
        assert "https://example2.com/" in limiter.property_requests
        
    def test_daily_quota_enforcement(self):
        """Test daily quota enforcement"""
        config = RateLimitConfig(
            requests_per_day=10,
            requests_per_minute=100,  # High limit to avoid per-minute throttling
            burst_size=100,  # High burst to allow all requests through
            cooldown_seconds=0.0  # No cooldown for testing
        )
        limiter = EnterprisRateLimiter(config)
        
        # Make 10 requests
        for i in range(10):
            wait = limiter.acquire(f"https://example{i}.com/")
            if wait > 0:
                time.sleep(wait)
            
        assert limiter.daily_requests == 10
        
        # Next request should hit quota limit
        wait = limiter.acquire("https://example.com/")
        assert wait > 0  # Should wait until tomorrow
        
    def test_record_success(self):
        """Test recording successful requests"""
        limiter = EnterprisRateLimiter()
        limiter.consecutive_failures = 3
        limiter.backoff_until = time.time() + 10
        
        limiter.record_success()
        
        assert limiter.consecutive_failures == 0
        assert limiter.backoff_until is None
        
    def test_record_failure_with_backoff(self):
        """Test exponential backoff on failures"""
        config = RateLimitConfig(base_backoff=1.0, jitter=False)
        limiter = EnterprisRateLimiter(config)
        
        # First failure
        limiter.record_failure(is_rate_limit=True)
        assert limiter.consecutive_failures == 1
        backoff1 = limiter.get_backoff_time()
        
        # Second failure
        limiter.record_failure(is_rate_limit=True)
        assert limiter.consecutive_failures == 2
        backoff2 = limiter.get_backoff_time()
        
        # Backoff should increase exponentially
        assert backoff2 > backoff1
        
    def test_backoff_with_jitter(self):
        """Test backoff with jitter adds randomness"""
        config = RateLimitConfig(base_backoff=2.0, jitter=True)
        limiter = EnterprisRateLimiter(config)
        
        limiter.consecutive_failures = 2
        
        # Get multiple backoff times
        backoffs = [limiter.get_backoff_time() for _ in range(10)]
        
        # Should have variation due to jitter
        assert len(set(backoffs)) > 1
        
    def test_max_backoff_limit(self):
        """Test backoff doesn't exceed maximum"""
        config = RateLimitConfig(base_backoff=2.0, max_backoff=10.0, jitter=False)
        limiter = EnterprisRateLimiter(config)
        
        # Many failures
        limiter.consecutive_failures = 100
        
        backoff = limiter.get_backoff_time()
        assert backoff <= 10.0
        
    def test_should_retry(self):
        """Test retry decision logic"""
        config = RateLimitConfig(max_retries=3)
        limiter = EnterprisRateLimiter(config)
        
        assert limiter.should_retry() is True
        
        limiter.consecutive_failures = 2
        assert limiter.should_retry() is True
        
        limiter.consecutive_failures = 3
        assert limiter.should_retry() is False
        
    def test_get_metrics(self):
        """Test metrics collection"""
        limiter = EnterprisRateLimiter()
        
        # Make some requests
        limiter.acquire("https://example1.com/")
        limiter.acquire("https://example2.com/")
        limiter.record_success()
        
        metrics = limiter.get_metrics()
        
        assert metrics['total_requests'] == 2
        assert metrics['daily_requests'] == 2
        assert metrics['consecutive_failures'] == 0
        assert metrics['properties_tracked'] == 2
        assert 'throttle_rate' in metrics
        
    def test_reset_backoff(self):
        """Test manual backoff reset"""
        limiter = EnterprisRateLimiter()
        limiter.consecutive_failures = 5
        limiter.backoff_until = time.time() + 100
        
        limiter.reset_backoff()
        
        assert limiter.consecutive_failures == 0
        assert limiter.backoff_until is None
        
    def test_backoff_period_blocking(self):
        """Test that backoff period blocks requests"""
        config = RateLimitConfig(base_backoff=1.0, jitter=False)
        limiter = EnterprisRateLimiter(config)
        
        # Trigger backoff
        limiter.record_failure(is_rate_limit=True)
        
        # Should wait during backoff
        wait = limiter.acquire("https://example.com/")
        assert wait > 0
        
    def test_concurrent_access(self):
        """Test thread-safe concurrent access"""
        config = RateLimitConfig(
            requests_per_minute=100,  # High limit for concurrent testing
            burst_size=100,  # High burst to allow all requests through
            cooldown_seconds=0.0  # No cooldown for testing
        )
        limiter = EnterprisRateLimiter(config)
        results = []
        
        def make_requests():
            for i in range(10):
                wait = limiter.acquire(f"https://example{i}.com/")
                if wait > 0:
                    time.sleep(wait)
                results.append(wait >= 0)
                
        threads = [threading.Thread(target=make_requests) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # All should succeed
        assert all(results)
        assert limiter.total_requests == 30


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios"""
    
    def test_gradual_load_increase(self):
        """Test rate limiter under gradually increasing load"""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_size=10
        )
        limiter = EnterprisRateLimiter(config)
        
        # Simulate gradual load increase
        for batch in range(5):
            for i in range(batch * 2):
                wait = limiter.acquire(f"https://example{i}.com/")
                if wait > 0:
                    time.sleep(wait)
                    
        metrics = limiter.get_metrics()
        assert metrics['total_requests'] > 0
        assert metrics['throttle_rate'] < 0.2  # < 20% throttled
        
    def test_burst_handling(self):
        """Test burst traffic handling"""
        config = RateLimitConfig(
            burst_size=5,
            requests_per_minute=60,  # Allow enough for the test
            cooldown_seconds=0.0  # No cooldown to test burst behavior
        )
        limiter = EnterprisRateLimiter(config)
        
        # Quick burst of requests
        burst_requests = []
        for i in range(10):
            wait = limiter.acquire("https://example.com/")
            burst_requests.append(wait)
            
        # First few should be immediate (burst allowed)
        assert sum(1 for w in burst_requests[:5] if w == 0) >= 3
        
        # Later requests should be throttled
        assert sum(1 for w in burst_requests[5:] if w > 0) >= 2
        
    def test_recovery_after_failures(self):
        """Test recovery after consecutive failures"""
        limiter = EnterprisRateLimiter()
        
        # Simulate failures
        for _ in range(3):
            limiter.record_failure(is_rate_limit=True)
            
        assert limiter.consecutive_failures == 3
        
        # Simulate success
        limiter.record_success()
        
        assert limiter.consecutive_failures == 0
        
        # Should be able to make requests normally
        wait = limiter.acquire("https://example.com/")
        assert wait >= 0


def test_rate_limiter_config_from_env():
    """Test rate limiter configuration from environment variables"""
    config = RateLimitConfig(
        requests_per_minute=int(os.getenv('REQUESTS_PER_MINUTE', '30')),
        requests_per_day=int(os.getenv('REQUESTS_PER_DAY', '2000'))
    )
    
    assert config.requests_per_minute > 0
    assert config.requests_per_day > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
