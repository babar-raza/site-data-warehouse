"""
Google Custom Search Engine Analyzer

Analyzes SERPs using the Google Custom Search Engine API.
Provides competitor analysis, position tracking, and SERP feature detection.

Note: Free tier allows 100 queries/day.

Example:
    analyzer = GoogleCSEAnalyzer()
    results = analyzer.search('python tutorial')
    analysis = analyzer.analyze_serp('python tutorial', 'example.com')
"""
import logging
import os
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import requests
import yaml

logger = logging.getLogger(__name__)


class QuotaTracker:
    """
    Tracks daily API quota usage

    Google CSE free tier: 100 queries/day
    """

    def __init__(self, daily_quota: int = 100):
        """
        Initialize quota tracker

        Args:
            daily_quota: Maximum queries per day
        """
        self.daily_quota = daily_quota
        self.queries_today = 0
        self.reset_date = datetime.utcnow().date()
        self.lock = Lock()

    def can_query(self) -> bool:
        """Check if we have quota remaining"""
        with self.lock:
            self._check_reset()
            return self.queries_today < self.daily_quota

    def record_query(self) -> None:
        """Record a query usage"""
        with self.lock:
            self._check_reset()
            self.queries_today += 1

    def get_remaining(self) -> int:
        """Get remaining queries for today"""
        with self.lock:
            self._check_reset()
            return max(0, self.daily_quota - self.queries_today)

    def _check_reset(self) -> None:
        """Reset counter if new day"""
        today = datetime.utcnow().date()
        if today > self.reset_date:
            self.queries_today = 0
            self.reset_date = today

    def get_status(self) -> Dict:
        """Get quota status"""
        with self.lock:
            self._check_reset()
            return {
                'daily_quota': self.daily_quota,
                'queries_today': self.queries_today,
                'remaining': self.get_remaining(),
                'reset_date': self.reset_date.isoformat()
            }


class ResponseCache:
    """
    Simple TTL cache for search results
    """

    def __init__(self, ttl_minutes: int = 60):
        """
        Initialize cache

        Args:
            ttl_minutes: Time to live in minutes (default 1 hour)
        """
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cache: Dict[str, Dict] = {}
        self.lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired"""
        with self.lock:
            if key in self.cache:
                item = self.cache[key]
                if datetime.utcnow() - item['timestamp'] < self.ttl:
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
                'timestamp': datetime.utcnow()
            }

    def clear(self) -> None:
        """Clear all cached items"""
        with self.lock:
            self.cache.clear()


class GoogleCSEAnalyzer:
    """
    Analyzes SERPs using Google Custom Search Engine API

    Provides:
    - Search result retrieval
    - Position tracking for target domains
    - Competitor extraction
    - SERP feature detection

    Free tier: 100 queries/day

    Example:
        analyzer = GoogleCSEAnalyzer()

        # Execute search
        results = analyzer.search('python tutorial')

        # Analyze SERP for a domain
        analysis = analyzer.analyze_serp('python tutorial', 'example.com')
        print(f"Position: {analysis['target_position']}")
        print(f"Competitors: {len(analysis['competitors'])}")

        # Check quota
        status = analyzer.get_quota_status()
        print(f"Remaining queries: {status['remaining']}")
    """

    CSE_API_URL = 'https://www.googleapis.com/customsearch/v1'

    DEFAULT_CONFIG = {
        'daily_quota': 100,
        'requests_per_second': 1,
        'cache_ttl_minutes': 60,
        'num_results': 10,
        'language': 'en',
        'country': 'us',
        'retries': 3,
        'retry_delay': 2
    }

    def __init__(self, api_key: str = None, cse_id: str = None, config_path: str = None):
        """
        Initialize Google CSE Analyzer

        Args:
            api_key: Google API key (or set GOOGLE_CSE_API_KEY env var)
            cse_id: Custom Search Engine ID (or set GOOGLE_CSE_ID env var)
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)

        self.api_key = api_key or os.getenv('GOOGLE_CSE_API_KEY')
        self.cse_id = cse_id or os.getenv('GOOGLE_CSE_ID')

        if not self.api_key:
            logger.warning("No API key configured - CSE searches will fail")
        if not self.cse_id:
            logger.warning("No CSE ID configured - CSE searches will fail")

        # Initialize quota tracker
        self.quota = QuotaTracker(
            daily_quota=self.config.get('daily_quota', 100)
        )

        # Initialize cache
        self.cache = ResponseCache(
            ttl_minutes=self.config.get('cache_ttl_minutes', 60)
        )

        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 1.0 / self.config.get('requests_per_second', 1)
        self.rate_lock = Lock()

        logger.info("GoogleCSEAnalyzer initialized")

    def _load_config(self, config_path: str = None) -> Dict:
        """Load configuration from file or use defaults"""
        config = self.DEFAULT_CONFIG.copy()

        if config_path:
            try:
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config and 'google_cse' in file_config:
                        config.update(file_config['google_cse'])
            except Exception as e:
                logger.warning(f"Could not load config from {config_path}: {e}")

        # Check standard location
        standard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'google_cse_config.yaml'
        )
        if os.path.exists(standard_path) and not config_path:
            try:
                with open(standard_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config and 'google_cse' in file_config:
                        config.update(file_config['google_cse'])
            except Exception as e:
                logger.warning(f"Could not load config from {standard_path}: {e}")

        return config

    def search(self, query: str, num_results: int = None,
               start: int = 1, language: str = None, country: str = None) -> List[Dict]:
        """
        Execute search and return results

        Args:
            query: Search query
            num_results: Number of results (default from config, max 10)
            start: Starting result index (1-based)
            language: Language code (e.g., 'en')
            country: Country code (e.g., 'us')

        Returns:
            List of search result dictionaries

        Example:
            >>> analyzer = GoogleCSEAnalyzer()
            >>> results = analyzer.search('python tutorial', num_results=10)
            >>> for r in results:
            ...     print(f"{r['position']}: {r['title']}")
        """
        if not self.api_key or not self.cse_id:
            logger.error("API key or CSE ID not configured")
            return []

        num_results = min(num_results or self.config.get('num_results', 10), 10)
        language = language or self.config.get('language', 'en')
        country = country or self.config.get('country', 'us')

        # Check cache
        cache_key = f"search_{query}_{num_results}_{start}_{language}_{country}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Check quota
        if not self.quota.can_query():
            logger.warning("Daily quota exceeded")
            return []

        # Apply rate limiting
        self._wait_for_rate_limit()

        # Build request parameters
        params = {
            'key': self.api_key,
            'cx': self.cse_id,
            'q': query,
            'num': num_results,
            'start': start,
            'lr': f'lang_{language}',
            'gl': country
        }

        # Execute request with retries
        retries = self.config.get('retries', 3)
        retry_delay = self.config.get('retry_delay', 2)

        for attempt in range(retries):
            try:
                response = requests.get(self.CSE_API_URL, params=params, timeout=30)
                self.quota.record_query()

                if response.status_code == 200:
                    data = response.json()
                    results = self._parse_results(data, start)
                    self.cache.set(cache_key, results)
                    logger.info(f"Search '{query}' returned {len(results)} results")
                    return results

                elif response.status_code == 429:
                    logger.warning("Rate limited, waiting before retry...")
                    time.sleep(retry_delay * (attempt + 1))

                else:
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    return []

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(retry_delay * (attempt + 1))

        logger.error(f"Failed to search after {retries} attempts")
        return []

    def analyze_serp(self, query: str, target_domain: str,
                     num_results: int = 10) -> Dict:
        """
        Analyze SERP for target domain

        Args:
            query: Search query to analyze
            target_domain: Domain to track position for
            num_results: Number of results to analyze

        Returns:
            Dict with SERP analysis including position, competitors, features

        Example:
            >>> analyzer = GoogleCSEAnalyzer()
            >>> analysis = analyzer.analyze_serp('python tutorial', 'realpython.com')
            >>> print(f"Position: {analysis['target_position']}")
            >>> print(f"Competitors: {analysis['competitors'][:3]}")
        """
        results = self.search(query, num_results=num_results)

        analysis = {
            'query': query,
            'target_domain': target_domain,
            'target_position': self._find_position(results, target_domain),
            'target_result': self._find_result(results, target_domain),
            'competitors': self._extract_competitors(results, target_domain),
            'serp_features': self._detect_features(results),
            'total_results': len(results),
            'analyzed_at': datetime.utcnow().isoformat()
        }

        # Add domain distribution
        analysis['domain_distribution'] = self._analyze_domain_distribution(results)

        return analysis

    def batch_analyze(self, queries: List[str], target_domain: str) -> List[Dict]:
        """
        Analyze multiple queries for a domain

        Args:
            queries: List of search queries
            target_domain: Domain to track

        Returns:
            List of SERP analyses
        """
        results = []

        for query in queries:
            # Check quota before each query
            if not self.quota.can_query():
                logger.warning(f"Quota exhausted after {len(results)} queries")
                break

            analysis = self.analyze_serp(query, target_domain)
            results.append(analysis)

        return results

    def get_quota_status(self) -> Dict:
        """
        Get current quota status

        Returns:
            Dict with quota information
        """
        return self.quota.get_status()

    def clear_cache(self) -> None:
        """Clear the response cache"""
        self.cache.clear()
        logger.info("Cache cleared")

    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits"""
        with self.rate_lock:
            now = time.time()
            elapsed = now - self.last_request_time

            if elapsed < self.request_interval:
                sleep_time = self.request_interval - elapsed
                time.sleep(sleep_time)

            self.last_request_time = time.time()

    def _parse_results(self, data: Dict, start_index: int) -> List[Dict]:
        """Parse API response into result list"""
        results = []

        items = data.get('items', [])
        for i, item in enumerate(items):
            result = {
                'position': start_index + i,
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'display_link': item.get('displayLink', ''),
                'snippet': item.get('snippet', ''),
                'domain': self._extract_domain(item.get('link', '')),
                'has_rich_snippet': 'pagemap' in item,
            }

            # Extract additional metadata if available
            if 'pagemap' in item:
                pagemap = item['pagemap']

                # Check for various rich snippets
                result['has_thumbnail'] = 'cse_thumbnail' in pagemap
                result['has_rating'] = 'aggregaterating' in pagemap
                result['has_breadcrumbs'] = 'breadcrumb' in pagemap

                # Extract meta info
                if 'metatags' in pagemap and pagemap['metatags']:
                    meta = pagemap['metatags'][0]
                    result['og_title'] = meta.get('og:title')
                    result['og_description'] = meta.get('og:description')

            results.append(result)

        return results

    def _find_position(self, results: List[Dict], domain: str) -> Optional[int]:
        """
        Find position of domain in results

        Args:
            results: Search results
            domain: Domain to find

        Returns:
            Position (1-indexed) or None if not found
        """
        domain_lower = domain.lower().replace('www.', '')

        for result in results:
            result_domain = result.get('domain', '').lower().replace('www.', '')
            if domain_lower in result_domain or result_domain in domain_lower:
                return result['position']

        return None

    def _find_result(self, results: List[Dict], domain: str) -> Optional[Dict]:
        """Find the result for a domain"""
        domain_lower = domain.lower().replace('www.', '')

        for result in results:
            result_domain = result.get('domain', '').lower().replace('www.', '')
            if domain_lower in result_domain or result_domain in domain_lower:
                return result

        return None

    def _extract_competitors(self, results: List[Dict],
                             exclude_domain: str) -> List[Dict]:
        """
        Extract competitor information

        Args:
            results: Search results
            exclude_domain: Domain to exclude (target domain)

        Returns:
            List of competitor dicts
        """
        exclude_lower = exclude_domain.lower().replace('www.', '')
        competitors = []

        for result in results:
            result_domain = result.get('domain', '').lower().replace('www.', '')

            if exclude_lower not in result_domain and result_domain not in exclude_lower:
                competitors.append({
                    'domain': result.get('domain'),
                    'position': result['position'],
                    'title': result.get('title'),
                    'link': result.get('link'),
                    'has_rich_snippet': result.get('has_rich_snippet', False)
                })

        return competitors

    def _detect_features(self, results: List[Dict]) -> List[str]:
        """
        Detect SERP features present in results

        Args:
            results: Search results

        Returns:
            List of detected feature names
        """
        features = set()

        for result in results:
            if result.get('has_rich_snippet'):
                features.add('rich_snippets')
            if result.get('has_thumbnail'):
                features.add('thumbnails')
            if result.get('has_rating'):
                features.add('ratings')
            if result.get('has_breadcrumbs'):
                features.add('breadcrumbs')

        # Note: CSE doesn't directly expose all SERP features
        # like featured snippets, knowledge panels, etc.

        return list(features)

    def _analyze_domain_distribution(self, results: List[Dict]) -> Dict[str, int]:
        """Analyze domain distribution in results"""
        distribution = {}

        for result in results:
            domain = result.get('domain', 'unknown')
            distribution[domain] = distribution.get(domain, 0) + 1

        return distribution

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return ''
