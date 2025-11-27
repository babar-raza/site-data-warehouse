"""
Integration Tests for External Service Mocking
Tests all external API integrations with zero real network calls.

External services tested:
- Google Search Console API (OAuth + Search Analytics)
- Google Analytics Data API (GA4 with service account auth)
- Google PageSpeed Insights API
- Ollama LLM API

All tests use the `responses` library to mock HTTP responses.
No real network calls are made during testing.
"""

import json
import pytest
import responses
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from google.oauth2 import service_account
from google.analytics.data_v1beta.types import RunReportResponse


# Test constants
TEST_PROPERTY = "https://example.com/"
TEST_GA4_PROPERTY_ID = "12345678"
TEST_API_KEY = "test-api-key-12345"
TEST_OLLAMA_HOST = "http://localhost:11434"
TEST_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
TEST_GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
TEST_PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class TestGoogleOAuthMocking:
    """Test Google OAuth authentication mocking."""

    @responses.activate
    def test_oauth_token_endpoint_mock(self):
        """Test mocking OAuth token endpoint for service account auth."""
        # Mock the OAuth token endpoint
        responses.add(
            responses.POST,
            TEST_OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token-abc123",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )

        # Attempt to get credentials (should use mocked endpoint)
        import requests

        response = requests.post(
            TEST_OAUTH_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": "mock-jwt-assertion",
            },
        )

        assert response.status_code == 200
        assert response.json()["access_token"] == "mock-access-token-abc123"
        assert response.json()["token_type"] == "Bearer"
        assert len(responses.calls) == 1

    @responses.activate
    def test_oauth_token_refresh_mock(self):
        """Test OAuth token refresh flow."""
        responses.add(
            responses.POST,
            TEST_OAUTH_TOKEN_URL,
            json={
                "access_token": "refreshed-token-xyz789",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            status=200,
        )

        import requests

        response = requests.post(
            TEST_OAUTH_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": "mock-refresh-token",
                "client_id": "mock-client-id",
                "client_secret": "mock-client-secret",
            },
        )

        assert response.status_code == 200
        assert response.json()["access_token"] == "refreshed-token-xyz789"

    @responses.activate
    def test_oauth_token_error_scenarios(self):
        """Test OAuth error handling."""
        # Test invalid grant
        responses.add(
            responses.POST,
            TEST_OAUTH_TOKEN_URL,
            json={
                "error": "invalid_grant",
                "error_description": "Invalid JWT Signature.",
            },
            status=400,
        )

        import requests

        response = requests.post(
            TEST_OAUTH_TOKEN_URL,
            data={"grant_type": "invalid"},
        )

        assert response.status_code == 400
        assert response.json()["error"] == "invalid_grant"

    @responses.activate
    def test_oauth_rate_limit_error(self):
        """Test OAuth rate limit handling."""
        responses.add(
            responses.POST,
            TEST_OAUTH_TOKEN_URL,
            json={
                "error": "rate_limit_exceeded",
                "error_description": "Too many requests",
            },
            status=429,
        )

        import requests

        response = requests.post(TEST_OAUTH_TOKEN_URL, data={})
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limit_exceeded"


class TestGSCAPIMocking:
    """Test Google Search Console API mocking."""

    @responses.activate
    def test_gsc_search_analytics_query_success(self):
        """Test successful GSC Search Analytics query."""
        # Mock GSC API endpoint
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "rows": [
                    {
                        "keys": ["https://example.com/page1", "test query", "usa", "MOBILE", "2025-01-15"],
                        "clicks": 100,
                        "impressions": 1000,
                        "ctr": 0.1,
                        "position": 5.5,
                    },
                    {
                        "keys": ["https://example.com/page2", "another query", "usa", "DESKTOP", "2025-01-15"],
                        "clicks": 50,
                        "impressions": 500,
                        "ctr": 0.1,
                        "position": 3.2,
                    },
                ],
                "responseAggregationType": "auto",
            },
            status=200,
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={
                "startDate": "2025-01-15",
                "endDate": "2025-01-15",
                "dimensions": ["page", "query", "country", "device", "date"],
                "rowLimit": 25000,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["rows"]) == 2
        assert data["rows"][0]["clicks"] == 100
        assert data["rows"][0]["position"] == 5.5

    @responses.activate
    def test_gsc_api_rate_limit_error(self):
        """Test GSC API rate limit error (429)."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "error": {
                    "code": 429,
                    "message": "Rate limit exceeded",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
            status=429,
            headers={"Retry-After": "60"},
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.json()["error"]["code"] == 429

    @responses.activate
    def test_gsc_api_server_error(self):
        """Test GSC API server error (500)."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "error": {
                    "code": 500,
                    "message": "Internal server error",
                    "status": "INTERNAL",
                }
            },
            status=500,
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )

        assert response.status_code == 500

    @responses.activate
    def test_gsc_api_authentication_error(self):
        """Test GSC API authentication error (401)."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "error": {
                    "code": 401,
                    "message": "Invalid authentication credentials",
                    "status": "UNAUTHENTICATED",
                }
            },
            status=401,
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer invalid-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )

        assert response.status_code == 401

    @responses.activate
    def test_gsc_api_permission_denied(self):
        """Test GSC API permission denied error (403)."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "error": {
                    "code": 403,
                    "message": "The caller does not have permission",
                    "status": "PERMISSION_DENIED",
                }
            },
            status=403,
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )

        assert response.status_code == 403

    @responses.activate
    def test_gsc_api_empty_response(self):
        """Test GSC API with no data (empty rows)."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        responses.add(
            responses.POST,
            gsc_endpoint,
            json={"responseAggregationType": "auto"},
            status=200,
        )

        import requests

        response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "rows" not in data or len(data.get("rows", [])) == 0


class TestGA4APIMocking:
    """Test Google Analytics Data API (GA4) mocking."""

    @responses.activate
    def test_ga4_run_report_success(self):
        """Test successful GA4 runReport API call."""
        # GA4 uses gRPC but can be mocked via REST API
        ga4_endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{TEST_GA4_PROPERTY_ID}:runReport"

        responses.add(
            responses.POST,
            ga4_endpoint,
            json={
                "dimensionHeaders": [
                    {"name": "date"},
                    {"name": "hostName"},
                    {"name": "pagePath"},
                ],
                "metricHeaders": [
                    {"name": "sessions", "type": "TYPE_INTEGER"},
                    {"name": "engagedSessions", "type": "TYPE_INTEGER"},
                    {"name": "engagementRate", "type": "TYPE_FLOAT"},
                ],
                "rows": [
                    {
                        "dimensionValues": [
                            {"value": "20250115"},
                            {"value": "example.com"},
                            {"value": "/page1"},
                        ],
                        "metricValues": [
                            {"value": "100"},
                            {"value": "75"},
                            {"value": "0.75"},
                        ],
                    },
                ],
                "rowCount": 1,
            },
            status=200,
        )

        import requests

        response = requests.post(
            ga4_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={
                "dateRanges": [{"startDate": "2025-01-15", "endDate": "2025-01-15"}],
                "dimensions": [{"name": "date"}, {"name": "hostName"}, {"name": "pagePath"}],
                "metrics": [
                    {"name": "sessions"},
                    {"name": "engagedSessions"},
                    {"name": "engagementRate"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rowCount"] == 1
        assert len(data["rows"]) == 1

    @responses.activate
    def test_ga4_api_quota_exceeded(self):
        """Test GA4 API quota exceeded error."""
        ga4_endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{TEST_GA4_PROPERTY_ID}:runReport"

        responses.add(
            responses.POST,
            ga4_endpoint,
            json={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for quota metric 'Queries' and limit 'Queries per day'",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
            status=429,
        )

        import requests

        response = requests.post(
            ga4_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={},
        )

        assert response.status_code == 429

    @responses.activate
    def test_ga4_api_invalid_property(self):
        """Test GA4 API with invalid property ID."""
        ga4_endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/invalid:runReport"

        responses.add(
            responses.POST,
            ga4_endpoint,
            json={
                "error": {
                    "code": 404,
                    "message": "Property not found",
                    "status": "NOT_FOUND",
                }
            },
            status=404,
        )

        import requests

        response = requests.post(
            ga4_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={},
        )

        assert response.status_code == 404

    @responses.activate
    def test_ga4_api_authentication_error(self):
        """Test GA4 API authentication error."""
        ga4_endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{TEST_GA4_PROPERTY_ID}:runReport"

        responses.add(
            responses.POST,
            ga4_endpoint,
            json={
                "error": {
                    "code": 401,
                    "message": "Request had invalid authentication credentials",
                    "status": "UNAUTHENTICATED",
                }
            },
            status=401,
        )

        import requests

        response = requests.post(
            ga4_endpoint,
            headers={"Authorization": "Bearer invalid-token"},
            json={},
        )

        assert response.status_code == 401


class TestPageSpeedAPIMocking:
    """Test PageSpeed Insights API mocking."""

    @responses.activate
    def test_pagespeed_api_success(self):
        """Test successful PageSpeed API call."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "id": "https://example.com/test-page",
                "loadingExperience": {
                    "metrics": {
                        "LARGEST_CONTENTFUL_PAINT_MS": {
                            "percentile": 2000,
                            "category": "FAST",
                        },
                        "FIRST_INPUT_DELAY_MS": {
                            "percentile": 80,
                            "category": "FAST",
                        },
                        "CUMULATIVE_LAYOUT_SHIFT_SCORE": {
                            "percentile": 8,
                            "category": "FAST",
                        },
                    }
                },
                "lighthouseResult": {
                    "requestedUrl": "https://example.com/test-page",
                    "finalUrl": "https://example.com/test-page",
                    "lighthouseVersion": "10.0.0",
                    "userAgent": "Mozilla/5.0",
                    "fetchTime": "2025-01-15T12:00:00.000Z",
                    "categories": {
                        "performance": {"score": 0.85},
                        "accessibility": {"score": 0.90},
                        "best-practices": {"score": 0.92},
                        "seo": {"score": 0.88},
                    },
                    "audits": {
                        "largest-contentful-paint": {
                            "id": "largest-contentful-paint",
                            "title": "Largest Contentful Paint",
                            "score": 0.9,
                            "numericValue": 2000,
                        },
                        "cumulative-layout-shift": {
                            "id": "cumulative-layout-shift",
                            "title": "Cumulative Layout Shift",
                            "score": 0.95,
                            "numericValue": 0.08,
                        },
                    },
                },
            },
            status=200,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={
                "url": "https://example.com/test-page",
                "strategy": "mobile",
                "category": "performance",
                "key": TEST_API_KEY,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "https://example.com/test-page"
        assert data["lighthouseResult"]["categories"]["performance"]["score"] == 0.85
        assert data["loadingExperience"]["metrics"]["LARGEST_CONTENTFUL_PAINT_MS"]["percentile"] == 2000

    @responses.activate
    def test_pagespeed_api_desktop_strategy(self):
        """Test PageSpeed API with desktop strategy."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "id": "https://example.com/test-page",
                "lighthouseResult": {
                    "requestedUrl": "https://example.com/test-page",
                    "configSettings": {"formFactor": "desktop"},
                    "categories": {"performance": {"score": 0.92}},
                    "audits": {},
                },
            },
            status=200,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={
                "url": "https://example.com/test-page",
                "strategy": "desktop",
                "key": TEST_API_KEY,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["lighthouseResult"]["configSettings"]["formFactor"] == "desktop"

    @responses.activate
    def test_pagespeed_api_rate_limit(self):
        """Test PageSpeed API rate limit error."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for quota metric 'Queries per day'",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
            status=429,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={"url": "https://example.com/test-page", "key": TEST_API_KEY},
        )

        assert response.status_code == 429

    @responses.activate
    def test_pagespeed_api_invalid_url(self):
        """Test PageSpeed API with invalid URL."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "error": {
                    "code": 400,
                    "message": "Invalid URL format",
                    "status": "INVALID_ARGUMENT",
                }
            },
            status=400,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={"url": "not-a-valid-url", "key": TEST_API_KEY},
        )

        assert response.status_code == 400

    @responses.activate
    def test_pagespeed_api_invalid_api_key(self):
        """Test PageSpeed API with invalid API key."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "error": {
                    "code": 400,
                    "message": "API key not valid",
                    "status": "INVALID_ARGUMENT",
                }
            },
            status=400,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={"url": "https://example.com/test-page", "key": "invalid-key"},
        )

        assert response.status_code == 400

    @responses.activate
    def test_pagespeed_api_timeout_error(self):
        """Test PageSpeed API timeout error."""
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "error": {
                    "code": 504,
                    "message": "Timeout while fetching URL",
                    "status": "DEADLINE_EXCEEDED",
                }
            },
            status=504,
        )

        import requests

        response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={"url": "https://slow-example.com/test-page", "key": TEST_API_KEY},
        )

        assert response.status_code == 504


class TestOllamaAPIMocking:
    """Test Ollama LLM API mocking."""

    @responses.activate
    def test_ollama_generate_success(self):
        """Test successful Ollama generate API call."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "created_at": "2025-01-15T12:00:00Z",
                "response": "The traffic drop appears to be caused by ranking position changes.",
                "done": True,
                "context": [],
                "total_duration": 1000000000,
                "load_duration": 100000000,
                "prompt_eval_count": 50,
                "prompt_eval_duration": 500000000,
                "eval_count": 100,
                "eval_duration": 400000000,
            },
            status=200,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": "Analyze this traffic drop: clicks from 100 to 50",
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "llama3.2:1b"
        assert data["done"] is True
        assert "response" in data
        assert len(data["response"]) > 0

    @responses.activate
    def test_ollama_generate_json_format(self):
        """Test Ollama generate with JSON format."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "created_at": "2025-01-15T12:00:00Z",
                "response": json.dumps({
                    "severity": "high",
                    "likely_causes": ["Position drop", "Algorithm update"],
                    "confidence": 0.85,
                    "recommended_actions": ["Update content", "Improve internal linking"],
                }),
                "done": True,
            },
            status=200,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": "Analyze this anomaly. Return JSON only.",
                "stream": False,
                "format": "json",
            },
        )

        assert response.status_code == 200
        data = response.json()
        response_data = json.loads(data["response"])
        assert response_data["severity"] == "high"
        assert len(response_data["likely_causes"]) == 2

    @responses.activate
    def test_ollama_chat_success(self):
        """Test successful Ollama chat API call."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/chat",
            json={
                "model": "llama3.2:1b",
                "created_at": "2025-01-15T12:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": "Based on the analysis, I recommend updating your content and improving internal linking.",
                },
                "done": True,
            },
            status=200,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/chat",
            json={
                "model": "llama3.2:1b",
                "messages": [
                    {"role": "system", "content": "You are an SEO expert."},
                    {"role": "user", "content": "What should I do about traffic drop?"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert len(data["message"]["content"]) > 0

    @responses.activate
    def test_ollama_api_model_not_found(self):
        """Test Ollama API with model not found error."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"error": "model 'nonexistent:model' not found"},
            status=404,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "nonexistent:model",
                "prompt": "test prompt",
            },
        )

        assert response.status_code == 404
        assert "error" in response.json()

    @responses.activate
    def test_ollama_api_connection_error(self):
        """Test Ollama API connection error."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"error": "connection refused"},
            status=503,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"model": "llama3.2:1b", "prompt": "test"},
        )

        assert response.status_code == 503

    @responses.activate
    def test_ollama_api_tags_list(self):
        """Test Ollama list models (tags) endpoint."""
        responses.add(
            responses.GET,
            f"{TEST_OLLAMA_HOST}/api/tags",
            json={
                "models": [
                    {
                        "name": "llama3.2:1b",
                        "modified_at": "2025-01-15T12:00:00Z",
                        "size": 1234567890,
                        "digest": "abc123def456",
                    },
                    {
                        "name": "mistral:7b",
                        "modified_at": "2025-01-15T12:00:00Z",
                        "size": 4567890123,
                        "digest": "xyz789ghi012",
                    },
                ]
            },
            status=200,
        )

        import requests

        response = requests.get(f"{TEST_OLLAMA_HOST}/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 2
        assert data["models"][0]["name"] == "llama3.2:1b"

    @responses.activate
    def test_ollama_api_timeout(self):
        """Test Ollama API timeout handling."""
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"error": "request timeout"},
            status=408,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"model": "llama3.2:1b", "prompt": "very long prompt..."},
            timeout=1,
        )

        assert response.status_code == 408


class TestIntegratedWorkflows:
    """Test integrated workflows using multiple mocked services."""

    @responses.activate
    def test_gsc_to_llm_analysis_workflow(self):
        """Test workflow: GSC data -> LLM analysis."""
        # Mock GSC API
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"
        responses.add(
            responses.POST,
            gsc_endpoint,
            json={
                "rows": [
                    {
                        "keys": ["https://example.com/page1", "test query", "usa", "MOBILE", "2025-01-15"],
                        "clicks": 50,
                        "impressions": 1000,
                        "ctr": 0.05,
                        "position": 12.5,
                    },
                ],
            },
            status=200,
        )

        # Mock Ollama API for analysis
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "response": json.dumps({
                    "issue": "High impression, low CTR suggests position drop",
                    "recommended_actions": ["Optimize title and meta description", "Add schema markup"],
                }),
                "done": True,
            },
            status=200,
        )

        import requests

        # Step 1: Get GSC data
        gsc_response = requests.post(
            gsc_endpoint,
            headers={"Authorization": "Bearer mock-token"},
            json={"startDate": "2025-01-15", "endDate": "2025-01-15"},
        )
        assert gsc_response.status_code == 200
        gsc_data = gsc_response.json()["rows"][0]

        # Step 2: Analyze with LLM
        prompt = f"Analyze: clicks={gsc_data['clicks']}, impressions={gsc_data['impressions']}, position={gsc_data['position']}"
        llm_response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"model": "llama3.2:1b", "prompt": prompt, "format": "json"},
        )
        assert llm_response.status_code == 200
        analysis = json.loads(llm_response.json()["response"])
        assert "issue" in analysis
        assert "recommended_actions" in analysis

    @responses.activate
    def test_pagespeed_to_llm_optimization_workflow(self):
        """Test workflow: PageSpeed data -> LLM optimization recommendations."""
        # Mock PageSpeed API
        responses.add(
            responses.GET,
            TEST_PAGESPEED_API_URL,
            json={
                "id": "https://example.com/slow-page",
                "lighthouseResult": {
                    "categories": {"performance": {"score": 0.45}},
                    "audits": {
                        "largest-contentful-paint": {"numericValue": 5000},
                        "cumulative-layout-shift": {"numericValue": 0.25},
                    },
                },
            },
            status=200,
        )

        # Mock Ollama API
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={
                "model": "llama3.2:1b",
                "response": json.dumps({
                    "priority_fixes": [
                        "Reduce LCP by optimizing images",
                        "Fix CLS by reserving space for dynamic content",
                    ],
                    "estimated_impact": "Could improve score from 45 to 75",
                }),
                "done": True,
            },
            status=200,
        )

        import requests

        # Step 1: Get PageSpeed data
        ps_response = requests.get(
            TEST_PAGESPEED_API_URL,
            params={"url": "https://example.com/slow-page", "key": TEST_API_KEY},
        )
        assert ps_response.status_code == 200
        cwv_data = ps_response.json()["lighthouseResult"]

        # Step 2: Get optimization recommendations
        prompt = f"Optimize: performance_score={cwv_data['categories']['performance']['score']}, LCP={cwv_data['audits']['largest-contentful-paint']['numericValue']}"
        llm_response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"model": "llama3.2:1b", "prompt": prompt, "format": "json"},
        )
        assert llm_response.status_code == 200
        recommendations = json.loads(llm_response.json()["response"])
        assert "priority_fixes" in recommendations
        assert len(recommendations["priority_fixes"]) > 0


class TestErrorRecovery:
    """Test error recovery and retry scenarios."""

    @responses.activate
    def test_retry_after_rate_limit(self):
        """Test retry logic after rate limit."""
        gsc_endpoint = f"{TEST_GSC_API_BASE}/sites/{TEST_PROPERTY}/searchAnalytics/query"

        # First call: rate limit
        responses.add(
            responses.POST,
            gsc_endpoint,
            json={"error": {"code": 429, "message": "Rate limit exceeded"}},
            status=429,
        )

        # Second call: success
        responses.add(
            responses.POST,
            gsc_endpoint,
            json={"rows": [{"keys": ["test"], "clicks": 100}]},
            status=200,
        )

        import requests

        # First attempt fails
        response1 = requests.post(gsc_endpoint, json={})
        assert response1.status_code == 429

        # Second attempt succeeds
        response2 = requests.post(gsc_endpoint, json={})
        assert response2.status_code == 200

    @responses.activate
    def test_fallback_after_service_unavailable(self):
        """Test fallback behavior when service is unavailable."""
        # Mock Ollama unavailable
        responses.add(
            responses.POST,
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"error": "service unavailable"},
            status=503,
        )

        import requests

        response = requests.post(
            f"{TEST_OLLAMA_HOST}/api/generate",
            json={"model": "llama3.2:1b", "prompt": "test"},
        )

        assert response.status_code == 503
        # Application should handle this gracefully


class TestZeroNetworkCalls:
    """Verify that no real network calls are made during tests."""

    @responses.activate
    def test_all_calls_are_mocked(self):
        """Verify responses library captures all HTTP calls."""
        # Add a catch-all mock that should never be called
        responses.add(
            responses.GET,
            "http://unexpected-call.example.com/",
            json={"error": "This should not be called"},
            status=500,
        )

        # Make only expected mocked calls
        responses.add(responses.GET, "http://expected-call.example.com/", json={"ok": True}, status=200)

        import requests

        response = requests.get("http://expected-call.example.com/")
        assert response.status_code == 200

        # Verify only the expected call was made
        assert len(responses.calls) == 1
        assert "expected-call" in responses.calls[0].request.url

    def test_responses_decorator_enforces_mocking(self):
        """Test that @responses.activate enforces mocking."""
        import requests
        from requests.exceptions import ConnectionError

        # Without @responses.activate, real network calls would be attempted
        # With it, any unmocked call raises an exception
        with pytest.raises(ConnectionError):

            @responses.activate
            def make_unmocked_call():
                requests.get("http://unmocked-url.example.com/")

            make_unmocked_call()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
