"""
Mock API factories for testing.

Provides mock implementations for external APIs:
- Google Search Console API
- GA4 BetaAnalyticsDataClient
- PageSpeed Insights API
- Ollama/LLM API
- Database connection pools

All mocks return realistic response structures matching the real APIs.

For HTTP-level mocking (with the responses library), see:
- tests/integration/test_external_services.py
"""

import asyncio
import json
import random
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock
from pathlib import Path

from tests.fixtures.sample_data import (
    generate_gsc_data,
    generate_ga4_data,
    generate_cwv_metrics,
    reset_seed,
    SAMPLE_PAGES,
    SAMPLE_PROPERTIES,
    SAMPLE_QUERIES,
)


class MockGSCClient:
    """
    Mock Google Search Console API client.

    Simulates searchconsole.webmasters.search_analytics.query responses.
    """

    def __init__(self, property_url: str = "https://example.com/"):
        """
        Initialize mock GSC client.

        Args:
            property_url: Property URL to use in responses
        """
        self.property_url = property_url
        reset_seed()

    def query(
        self,
        start_date: str,
        end_date: str,
        dimensions: Optional[List[str]] = None,
        row_limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Mock query method returning GSC API response structure.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            dimensions: List of dimensions to group by
            row_limit: Maximum rows to return

        Returns:
            Mock GSC API response
        """
        reset_seed()

        if not dimensions:
            dimensions = ["page", "query"]

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Generate sample data
        num_rows = min(row_limit, 100)
        gsc_data = generate_gsc_data(
            num_rows=num_rows, start_date=start, end_date=end, property_url=self.property_url
        )

        # Format as GSC API response
        rows = []
        for data in gsc_data[:row_limit]:
            row = {
                "keys": [],
                "clicks": data["clicks"],
                "impressions": data["impressions"],
                "ctr": data["ctr"],
                "position": data["position"],
            }

            # Add dimension keys
            if "page" in dimensions:
                row["keys"].append(data["url"])
            if "query" in dimensions:
                row["keys"].append(data["query"])
            if "country" in dimensions:
                row["keys"].append(data["country"])
            if "device" in dimensions:
                row["keys"].append(data["device"])
            if "date" in dimensions:
                row["keys"].append(data["date"].isoformat())

            rows.append(row)

        return {"rows": rows, "responseAggregationType": "auto"}


class MockGA4Client:
    """
    Mock GA4 BetaAnalyticsDataClient.

    Simulates google.analytics.data_v1beta responses.
    """

    def __init__(self, property_id: str = "12345678"):
        """
        Initialize mock GA4 client.

        Args:
            property_id: GA4 property ID
        """
        self.property_id = property_id
        reset_seed()

    def run_report(self, request: Any) -> Any:
        """
        Mock run_report method.

        Args:
            request: RunReportRequest object (or mock)

        Returns:
            Mock RunReportResponse
        """
        reset_seed()

        # Extract request parameters
        try:
            start_date = request.date_ranges[0].start_date
            end_date = request.date_ranges[0].end_date
        except (AttributeError, IndexError):
            # Fallback for testing
            start_date = (date.today() - timedelta(days=7)).isoformat()
            end_date = date.today().isoformat()

        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        # Generate sample GA4 data
        ga4_data = generate_ga4_data(num_rows=50, start_date=start, end_date=end)

        # Create mock response
        response = MagicMock()
        response.rows = []

        for data in ga4_data[:100]:  # Limit to 100 rows
            row = MagicMock()

            # Dimension values (date, hostName, pagePath)
            row.dimension_values = [
                MagicMock(value=data["date"].isoformat()),
                MagicMock(value=data["property"]),
                MagicMock(value=data["page_path"]),
            ]

            # Metric values (in order from ga4_client.py)
            row.metric_values = [
                MagicMock(value=str(data["sessions"])),
                MagicMock(value=str(data["engaged_sessions"])),
                MagicMock(value=str(data["engagement_rate"])),
                MagicMock(value=str(data["bounce_rate"])),
                MagicMock(value=str(data["conversions"])),
                MagicMock(value=str(data["page_views"])),
                MagicMock(value=str(data["avg_session_duration"])),
                MagicMock(value=str(data["avg_time_on_page"] * data["page_views"])),  # userEngagementDuration
            ]

            response.rows.append(row)

        response.row_count = len(response.rows)
        return response


class MockPageSpeedClient:
    """
    Mock PageSpeed Insights API client.

    Simulates pagespeedonline.v5 responses.
    """

    def __init__(self):
        """Initialize mock PageSpeed client."""
        reset_seed()

    def runpagespeed(
        self,
        url: str,
        strategy: str = "mobile",
        category: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Mock runpagespeed method.

        Args:
            url: URL to analyze
            strategy: Strategy (mobile or desktop)
            category: Categories to analyze

        Returns:
            Mock PageSpeed Insights response
        """
        reset_seed()

        # Determine quality based on URL (for reproducible tests)
        if "poor" in url:
            assessment = "poor"
        elif "good" in url:
            assessment = "good"
        else:
            assessment = "needs_improvement"

        cwv_metrics = generate_cwv_metrics(assessment=assessment, strategy=strategy)

        # Build realistic PageSpeed Insights response
        response = {
            "id": url,
            "loadingExperience": {
                "metrics": {
                    "LARGEST_CONTENTFUL_PAINT_MS": {
                        "percentile": int(cwv_metrics["lcp"]),
                        "category": assessment.upper().replace("_", " "),
                    },
                    "FIRST_INPUT_DELAY_MS": {
                        "percentile": int(cwv_metrics["fid"]),
                        "category": assessment.upper().replace("_", " "),
                    },
                    "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                        "percentile": int(cwv_metrics["cls"] * 100),
                        "category": assessment.upper().replace("_", " "),
                    },
                }
            },
            "lighthouseResult": {
                "requestedUrl": url,
                "finalUrl": url,
                "lighthouseVersion": "10.0.0",
                "userAgent": "Mozilla/5.0 (Linux; Android 7.0; Moto G (4))",
                "fetchTime": datetime.utcnow().isoformat() + "Z",
                "categories": {
                    "performance": {
                        "id": "performance",
                        "title": "Performance",
                        "score": cwv_metrics["performance_score"] / 100,
                    },
                    "accessibility": {
                        "id": "accessibility",
                        "title": "Accessibility",
                        "score": cwv_metrics["accessibility_score"] / 100,
                    },
                    "best-practices": {
                        "id": "best-practices",
                        "title": "Best Practices",
                        "score": cwv_metrics["best_practices_score"] / 100,
                    },
                    "seo": {"id": "seo", "title": "SEO", "score": cwv_metrics["seo_score"] / 100},
                },
                "audits": {
                    "largest-contentful-paint": {
                        "id": "largest-contentful-paint",
                        "title": "Largest Contentful Paint",
                        "displayValue": f"{cwv_metrics['lcp']/1000:.1f} s",
                        "score": 1.0 if cwv_metrics["lcp"] < 2500 else 0.5,
                        "numericValue": cwv_metrics["lcp"],
                    },
                    "first-input-delay": {
                        "id": "first-input-delay",
                        "title": "First Input Delay",
                        "displayValue": f"{cwv_metrics['fid']} ms",
                        "score": 1.0 if cwv_metrics["fid"] < 100 else 0.5,
                        "numericValue": cwv_metrics["fid"],
                    },
                    "cumulative-layout-shift": {
                        "id": "cumulative-layout-shift",
                        "title": "Cumulative Layout Shift",
                        "displayValue": f"{cwv_metrics['cls']:.3f}",
                        "score": 1.0 if cwv_metrics["cls"] < 0.1 else 0.5,
                        "numericValue": cwv_metrics["cls"],
                    },
                },
            },
        }

        return response


class MockOllamaClient:
    """
    Mock Ollama API client for LLM interactions.

    Simulates ollama.chat() and ollama.generate() responses.
    """

    def __init__(self, model: str = "llama3.2:1b"):
        """
        Initialize mock Ollama client.

        Args:
            model: Model name to simulate
        """
        self.model = model
        reset_seed()

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        format: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Mock chat method.

        Args:
            model: Model name
            messages: List of message dicts
            format: Response format (json or None)
            stream: Whether to stream response

        Returns:
            Mock Ollama chat response
        """
        reset_seed()

        # Extract user message for context-aware responses
        user_message = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")

        if format == "json":
            # Return structured JSON response
            content = self._generate_json_response(user_message)
            response_text = json.dumps(content)
        else:
            # Return text response
            response_text = self._generate_text_response(user_message)

        return {
            "model": model,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "message": {"role": "assistant", "content": response_text},
            "done": True,
            "total_duration": 1000000000,  # 1 second in nanoseconds
            "load_duration": 100000000,
            "prompt_eval_count": 50,
            "prompt_eval_duration": 500000000,
            "eval_count": 100,
            "eval_duration": 400000000,
        }

    def generate(
        self, model: str, prompt: str, format: Optional[str] = None, stream: bool = False
    ) -> Dict[str, Any]:
        """
        Mock generate method.

        Args:
            model: Model name
            prompt: Prompt text
            format: Response format
            stream: Whether to stream

        Returns:
            Mock Ollama generate response
        """
        if format == "json":
            response_text = json.dumps(self._generate_json_response(prompt))
        else:
            response_text = self._generate_text_response(prompt)

        return {
            "model": model,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "response": response_text,
            "done": True,
        }

    def _generate_text_response(self, prompt: str) -> str:
        """Generate contextual text response based on prompt."""
        prompt_lower = prompt.lower()

        if "traffic drop" in prompt_lower or "decline" in prompt_lower:
            return "The traffic drop appears to be caused by ranking position changes. I recommend analyzing recent algorithm updates and competitor content improvements."

        elif "root cause" in prompt_lower or "diagnosis" in prompt_lower:
            return "Root cause analysis suggests: 1) Position decline for key queries, 2) Algorithm update impact, 3) Seasonal trends. Confidence: High."

        elif "recommendation" in prompt_lower or "action" in prompt_lower:
            return "Recommended actions: 1) Update content with fresh data, 2) Improve internal linking, 3) Optimize for featured snippets."

        else:
            return "Based on the analysis, I recommend monitoring the situation closely and implementing targeted content improvements."

    def _generate_json_response(self, prompt: str) -> Dict[str, Any]:
        """Generate structured JSON response based on prompt."""
        prompt_lower = prompt.lower()

        if "root cause" in prompt_lower or "diagnosis" in prompt_lower:
            return {
                "cause_type": "position_drop",
                "confidence": 0.85,
                "evidence": [
                    "Average position increased from 5.2 to 12.3",
                    "CTR remained stable at 4.5%",
                    "Competitor content updated recently",
                ],
                "recommendations": [
                    "Update content with latest information",
                    "Improve internal linking structure",
                    "Add more visual content",
                ],
            }

        elif "recommendation" in prompt_lower:
            return {
                "recommendations": [
                    {
                        "action": "update_content",
                        "priority": "high",
                        "impact": "high",
                        "effort": "medium",
                    },
                    {
                        "action": "improve_internal_links",
                        "priority": "medium",
                        "impact": "medium",
                        "effort": "low",
                    },
                ],
                "estimated_impact": "20-30% traffic recovery within 2 weeks",
            }

        else:
            return {
                "analysis": "Standard analysis response",
                "confidence": 0.75,
                "findings": ["Finding 1", "Finding 2", "Finding 3"],
            }


class MockAsyncPool:
    """
    Mock async database connection pool (asyncpg).

    Provides async context manager interface for database testing.
    """

    def __init__(self, dsn: str = "postgresql://test:test@localhost/test"):
        """
        Initialize mock async pool.

        Args:
            dsn: Database DSN (not actually used)
        """
        self.dsn = dsn
        self._closed = False

    def acquire(self):
        """Acquire a connection from the pool."""
        return MockAsyncConnection()

    async def close(self):
        """Close the pool."""
        self._closed = True
        await asyncio.sleep(0)  # Simulate async operation

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class MockAsyncConnection:
    """Mock async database connection."""

    def __init__(self):
        """Initialize mock connection."""
        self._closed = False

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        Mock fetch method.

        Returns sample data based on query content.
        """
        await asyncio.sleep(0)  # Simulate async operation

        # Return different data based on query patterns
        if "fact_gsc_daily" in query:
            return generate_gsc_data(num_rows=10)
        elif "fact_ga4_daily" in query:
            return generate_ga4_data(num_rows=10)
        else:
            return []

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Mock fetchrow method."""
        results = await self.fetch(query, *args)
        return results[0] if results else None

    async def execute(self, query: str, *args) -> str:
        """Mock execute method."""
        await asyncio.sleep(0)
        return "INSERT 0 1"

    async def close(self):
        """Close connection."""
        self._closed = True
        await asyncio.sleep(0)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class MockRedisClient:
    """
    Mock Redis client for caching tests.

    Implements common Redis operations using in-memory dict.
    """

    def __init__(self):
        """Initialize mock Redis client."""
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, datetime] = {}

    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        await asyncio.sleep(0)

        # Check expiry
        if key in self._expiry and datetime.utcnow() > self._expiry[key]:
            del self._data[key]
            del self._expiry[key]
            return None

        return self._data.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set value in cache with optional expiry."""
        await asyncio.sleep(0)

        self._data[key] = value

        if ex:
            self._expiry[key] = datetime.utcnow() + timedelta(seconds=ex)

        return True

    async def delete(self, *keys: str) -> int:
        """Delete keys from cache."""
        await asyncio.sleep(0)

        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
            if key in self._expiry:
                del self._expiry[key]

        return count

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        await asyncio.sleep(0)
        return key in self._data

    async def close(self):
        """Close connection."""
        await asyncio.sleep(0)


def create_mock_gsc_client(property_url: str = "https://example.com/") -> MockGSCClient:
    """
    Factory function to create a mock GSC client.

    Args:
        property_url: Property URL for the client

    Returns:
        MockGSCClient instance
    """
    return MockGSCClient(property_url=property_url)


def create_mock_ga4_client(property_id: str = "12345678") -> MockGA4Client:
    """
    Factory function to create a mock GA4 client.

    Args:
        property_id: GA4 property ID

    Returns:
        MockGA4Client instance
    """
    return MockGA4Client(property_id=property_id)


def create_mock_pagespeed_client() -> MockPageSpeedClient:
    """
    Factory function to create a mock PageSpeed client.

    Returns:
        MockPageSpeedClient instance
    """
    return MockPageSpeedClient()


def create_mock_ollama_client(model: str = "llama3.2:1b") -> MockOllamaClient:
    """
    Factory function to create a mock Ollama client.

    Args:
        model: Model name

    Returns:
        MockOllamaClient instance
    """
    return MockOllamaClient(model=model)


def create_mock_db_pool(dsn: str = "postgresql://test:test@localhost/test") -> MockAsyncPool:
    """
    Factory function to create a mock async database pool.

    Args:
        dsn: Database DSN

    Returns:
        MockAsyncPool instance
    """
    return MockAsyncPool(dsn=dsn)


def create_mock_redis_client() -> MockRedisClient:
    """
    Factory function to create a mock Redis client.

    Returns:
        MockRedisClient instance
    """
    return MockRedisClient()


# ============================================================================
# Helpers for responses library (HTTP-level mocking)
# ============================================================================


def create_gsc_api_response(
    num_rows: int = 10,
    start_date: str = "2025-01-15",
    property_url: str = "https://example.com/"
) -> Dict[str, Any]:
    """
    Create a realistic GSC API response for use with responses library.

    Args:
        num_rows: Number of data rows to include
        start_date: Date string for the data
        property_url: Property URL for the response

    Returns:
        Dictionary matching GSC API response structure
    """
    reset_seed()
    gsc_data = generate_gsc_data(
        num_rows=num_rows,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
        end_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
        property_url=property_url
    )

    rows = []
    for data in gsc_data:
        rows.append({
            "keys": [data["url"], data["query"], data["country"], data["device"], start_date],
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "ctr": data["ctr"],
            "position": data["position"],
        })

    return {"rows": rows, "responseAggregationType": "auto"}


def create_pagespeed_api_response(
    url: str,
    strategy: str = "mobile",
    assessment: str = "needs_improvement"
) -> Dict[str, Any]:
    """
    Create a realistic PageSpeed Insights API response for use with responses library.

    Args:
        url: URL being analyzed
        strategy: 'mobile' or 'desktop'
        assessment: 'good', 'needs_improvement', or 'poor'

    Returns:
        Dictionary matching PageSpeed Insights API response structure
    """
    reset_seed()
    cwv_metrics = generate_cwv_metrics(assessment=assessment, strategy=strategy)

    return {
        "id": url,
        "loadingExperience": {
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {
                    "percentile": int(cwv_metrics["lcp"]),
                    "category": assessment.upper().replace("_", " "),
                },
                "FIRST_INPUT_DELAY_MS": {
                    "percentile": int(cwv_metrics["fid"]),
                    "category": assessment.upper().replace("_", " "),
                },
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                    "percentile": int(cwv_metrics["cls"] * 100),
                    "category": assessment.upper().replace("_", " "),
                },
            }
        },
        "lighthouseResult": {
            "requestedUrl": url,
            "finalUrl": url,
            "lighthouseVersion": "10.0.0",
            "userAgent": "Mozilla/5.0 (Linux; Android 7.0; Moto G (4))",
            "fetchTime": datetime.utcnow().isoformat() + "Z",
            "categories": {
                "performance": {
                    "id": "performance",
                    "title": "Performance",
                    "score": cwv_metrics["performance_score"] / 100,
                },
                "accessibility": {
                    "id": "accessibility",
                    "title": "Accessibility",
                    "score": cwv_metrics["accessibility_score"] / 100,
                },
                "best-practices": {
                    "id": "best-practices",
                    "title": "Best Practices",
                    "score": cwv_metrics["best_practices_score"] / 100,
                },
                "seo": {"id": "seo", "title": "SEO", "score": cwv_metrics["seo_score"] / 100},
            },
            "audits": {
                "largest-contentful-paint": {
                    "id": "largest-contentful-paint",
                    "title": "Largest Contentful Paint",
                    "displayValue": f"{cwv_metrics['lcp']/1000:.1f} s",
                    "score": 1.0 if cwv_metrics["lcp"] < 2500 else 0.5,
                    "numericValue": cwv_metrics["lcp"],
                },
                "cumulative-layout-shift": {
                    "id": "cumulative-layout-shift",
                    "title": "Cumulative Layout Shift",
                    "displayValue": f"{cwv_metrics['cls']:.3f}",
                    "score": 1.0 if cwv_metrics["cls"] < 0.1 else 0.5,
                    "numericValue": cwv_metrics["cls"],
                },
            },
        },
    }


def create_ollama_api_response(
    model: str = "llama3.2:1b",
    prompt: str = "",
    response_text: Optional[str] = None,
    format_json: bool = False
) -> Dict[str, Any]:
    """
    Create a realistic Ollama API response for use with responses library.

    Args:
        model: Model name
        prompt: Input prompt (used to generate contextual response)
        response_text: Optional custom response text
        format_json: Whether to format response as JSON

    Returns:
        Dictionary matching Ollama API response structure
    """
    if response_text is None:
        if format_json:
            response_text = json.dumps({
                "analysis": "Standard analysis response",
                "confidence": 0.75,
                "findings": ["Finding 1", "Finding 2", "Finding 3"],
            })
        else:
            response_text = "Based on the analysis, I recommend monitoring the situation closely."

    return {
        "model": model,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "response": response_text,
        "done": True,
        "context": [],
        "total_duration": 1000000000,
        "load_duration": 100000000,
        "prompt_eval_count": 50,
        "prompt_eval_duration": 500000000,
        "eval_count": 100,
        "eval_duration": 400000000,
    }
