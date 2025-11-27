"""
Google Trends Client with Rate Limiting

Provides access to Google Trends data with proper rate limiting
to avoid API bans. Uses pytrends library.

Example usage:
    client = GoogleTrendsClient()
    data = client.get_interest_over_time(['python', 'javascript'])
    print(data)
"""
import logging
import os
import time
from collections import deque
from datetime import datetime, timedelta
from functools import lru_cache
from threading import Lock
from typing import Dict, List, Optional, Any

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API requests

    Implements a sliding window rate limiter to ensure
    we don't exceed API rate limits.
    """

    def __init__(self, requests_per_minute: int = 10, burst_limit: int = 3):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Maximum requests per minute
            burst_limit: Maximum burst requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.window_size = 60  # seconds
        self.request_times: deque = deque()
        self.lock = Lock()

        logger.debug(f"RateLimiter initialized: {requests_per_minute}/min, burst={burst_limit}")

    def wait(self) -> float:
        """
        Wait if necessary to respect rate limits

        Returns:
            Seconds waited (0 if no wait needed)
        """
        with self.lock:
            now = time.time()

            # Remove old requests outside window
            while self.request_times and self.request_times[0] < now - self.window_size:
                self.request_times.popleft()

            # Check if we're at limit
            if len(self.request_times) >= self.requests_per_minute:
                # Wait until oldest request falls outside window
                wait_time = self.request_times[0] + self.window_size - now + 0.1
                if wait_time > 0:
                    logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)

            # Check burst limit (requests in last 5 seconds)
            recent = sum(1 for t in self.request_times if t > now - 5)
            if recent >= self.burst_limit:
                wait_time = 5 - (now - self.request_times[-self.burst_limit])
                if wait_time > 0:
                    logger.debug(f"Burst limited, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)

            # Record this request
            self.request_times.append(time.time())

            return 0.0

    def get_status(self) -> Dict:
        """Get current rate limit status"""
        with self.lock:
            now = time.time()
            # Remove old requests
            while self.request_times and self.request_times[0] < now - self.window_size:
                self.request_times.popleft()

            return {
                'requests_in_window': len(self.request_times),
                'limit': self.requests_per_minute,
                'remaining': max(0, self.requests_per_minute - len(self.request_times)),
                'window_size_seconds': self.window_size,
                'burst_limit': self.burst_limit
            }


class ResponseCache:
    """
    Simple TTL cache for API responses
    """

    def __init__(self, ttl_minutes: int = 15):
        """
        Initialize cache

        Args:
            ttl_minutes: Time to live in minutes
        """
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cache: Dict[str, Dict] = {}
        self.lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired"""
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if datetime.now() - item['timestamp'] < self.ttl:
                    logger.debug(f"Cache hit: {key[:50]}...")
                    return item['data']
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, data: Any) -> None:
        """Store item in cache"""
        with self.lock:
            self.cache[key] = {
                'data': data,
                'timestamp': datetime.now()
            }
            logger.debug(f"Cached: {key[:50]}...")

    def clear(self) -> None:
        """Clear all cached items"""
        with self.lock:
            self.cache.clear()


class GoogleTrendsClient:
    """
    Google Trends API client with rate limiting and caching

    Uses pytrends library to fetch Google Trends data with
    built-in rate limiting to avoid API bans.

    Example:
        client = GoogleTrendsClient()

        # Get interest over time
        data = client.get_interest_over_time(['python', 'javascript'])

        # Get related queries
        related = client.get_related_queries('machine learning')

        # Check rate limit status
        status = client.get_rate_limit_status()
    """

    DEFAULT_CONFIG = {
        'rate_limit': {
            'requests_per_minute': 10,
            'burst_limit': 3
        },
        'timeframes': {
            'default': 'today 12-m',
            'short': 'today 3-m',
            'long': 'today 5-y'
        },
        'cache_ttl_minutes': 15,
        'language': 'en-US',
        'timezone': 360,
        'retries': 3,
        'retry_delay': 5
    }

    def __init__(self, config_path: str = None):
        """
        Initialize Google Trends client

        Args:
            config_path: Path to configuration file (optional)
        """
        self.config = self._load_config(config_path)

        # Initialize rate limiter
        rate_config = self.config.get('rate_limit', {})
        self.rate_limiter = RateLimiter(
            requests_per_minute=rate_config.get('requests_per_minute', 10),
            burst_limit=rate_config.get('burst_limit', 3)
        )

        # Initialize cache
        self.cache = ResponseCache(
            ttl_minutes=self.config.get('cache_ttl_minutes', 15)
        )

        # Initialize pytrends (lazy load)
        self._pytrends = None

        logger.info("GoogleTrendsClient initialized")

    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration from file or use defaults"""
        config = self.DEFAULT_CONFIG.copy()

        if config_path:
            try:
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config and 'google_trends' in file_config:
                        config.update(file_config['google_trends'])
                        logger.info(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Could not load config from {config_path}: {e}")

        # Also check for config in standard location
        standard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'trends_config.yaml'
        )
        if os.path.exists(standard_path) and not config_path:
            try:
                with open(standard_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config and 'google_trends' in file_config:
                        config.update(file_config['google_trends'])
                        logger.info(f"Loaded config from {standard_path}")
            except Exception as e:
                logger.warning(f"Could not load config from {standard_path}: {e}")

        return config

    @property
    def pytrends(self):
        """Lazy-load pytrends instance"""
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq
                self._pytrends = TrendReq(
                    hl=self.config.get('language', 'en-US'),
                    tz=self.config.get('timezone', 360)
                )
            except ImportError:
                logger.error("pytrends not installed. Install with: pip install pytrends")
                raise ImportError("pytrends library required")
        return self._pytrends

    def get_interest_over_time(
        self,
        keywords: List[str],
        timeframe: str = None,
        geo: str = ''
    ) -> pd.DataFrame:
        """
        Fetch interest over time for keywords

        Args:
            keywords: List of keywords (max 5)
            timeframe: Time range (default: 'today 12-m')
            geo: Geographic region (default: worldwide)

        Returns:
            DataFrame with interest over time data

        Example:
            >>> client = GoogleTrendsClient()
            >>> df = client.get_interest_over_time(['python', 'javascript'])
            >>> print(df.head())
        """
        if not keywords:
            return pd.DataFrame()

        # Limit to 5 keywords (Google Trends limit)
        keywords = keywords[:5]
        timeframe = timeframe or self.config['timeframes']['default']

        # Check cache
        cache_key = f"interest_{','.join(sorted(keywords))}_{timeframe}_{geo}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Apply rate limiting
        self.rate_limiter.wait()

        # Fetch data with retries
        retries = self.config.get('retries', 3)
        retry_delay = self.config.get('retry_delay', 5)

        for attempt in range(retries):
            try:
                self.pytrends.build_payload(
                    keywords,
                    timeframe=timeframe,
                    geo=geo
                )
                data = self.pytrends.interest_over_time()

                # Cache result
                self.cache.set(cache_key, data)

                logger.info(f"Fetched interest over time for {keywords}")
                return data

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch interest over time: {e}")
                    return pd.DataFrame()

    def get_related_queries(self, keyword: str, geo: str = '') -> Dict:
        """
        Fetch related queries for a keyword

        Args:
            keyword: Single keyword to analyze
            geo: Geographic region (default: worldwide)

        Returns:
            Dict with 'top' and 'rising' related queries

        Example:
            >>> client = GoogleTrendsClient()
            >>> related = client.get_related_queries('python')
            >>> print(related['top'])
        """
        if not keyword:
            return {'top': None, 'rising': None}

        # Check cache
        cache_key = f"related_{keyword}_{geo}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Apply rate limiting
        self.rate_limiter.wait()

        retries = self.config.get('retries', 3)
        retry_delay = self.config.get('retry_delay', 5)

        for attempt in range(retries):
            try:
                self.pytrends.build_payload([keyword], geo=geo)
                data = self.pytrends.related_queries()

                result = {
                    'top': data.get(keyword, {}).get('top'),
                    'rising': data.get(keyword, {}).get('rising')
                }

                # Cache result
                self.cache.set(cache_key, result)

                logger.info(f"Fetched related queries for '{keyword}'")
                return result

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch related queries: {e}")
                    return {'top': None, 'rising': None}

    def get_regional_interest(
        self,
        keywords: List[str],
        resolution: str = 'COUNTRY',
        geo: str = ''
    ) -> pd.DataFrame:
        """
        Fetch regional interest breakdown

        Args:
            keywords: List of keywords (max 5)
            resolution: 'COUNTRY', 'REGION', 'CITY', 'DMA'
            geo: Geographic region (default: worldwide)

        Returns:
            DataFrame with regional interest data

        Example:
            >>> client = GoogleTrendsClient()
            >>> df = client.get_regional_interest(['python'], resolution='COUNTRY')
            >>> print(df.head())
        """
        if not keywords:
            return pd.DataFrame()

        keywords = keywords[:5]

        # Check cache
        cache_key = f"regional_{','.join(sorted(keywords))}_{resolution}_{geo}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Apply rate limiting
        self.rate_limiter.wait()

        retries = self.config.get('retries', 3)
        retry_delay = self.config.get('retry_delay', 5)

        for attempt in range(retries):
            try:
                self.pytrends.build_payload(keywords, geo=geo)
                data = self.pytrends.interest_by_region(
                    resolution=resolution,
                    inc_low_vol=True,
                    inc_geo_code=True
                )

                # Cache result
                self.cache.set(cache_key, data)

                logger.info(f"Fetched regional interest for {keywords}")
                return data

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch regional interest: {e}")
                    return pd.DataFrame()

    def get_trending_searches(self, country: str = 'united_states') -> pd.DataFrame:
        """
        Get daily trending searches for a country

        Args:
            country: Country name (e.g., 'united_states', 'united_kingdom')

        Returns:
            DataFrame with trending searches
        """
        # Check cache
        cache_key = f"trending_{country}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Apply rate limiting
        self.rate_limiter.wait()

        try:
            data = self.pytrends.trending_searches(pn=country)
            self.cache.set(cache_key, data)
            logger.info(f"Fetched trending searches for {country}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch trending searches: {e}")
            return pd.DataFrame()

    def get_rate_limit_status(self) -> Dict:
        """
        Get current rate limit status

        Returns:
            Dict with rate limit information
        """
        return self.rate_limiter.get_status()

    def clear_cache(self) -> None:
        """Clear the response cache"""
        self.cache.clear()
        logger.info("Cache cleared")
