#!/usr/bin/env python3
"""
Tests for the GSC Insights API new endpoints (page health, query trends,
directory trends, and brand/non-brand).

These tests exercise the happy paths with mocked database responses and
validate that invalid parameters result in deterministic error responses
instead of generic server errors. The FastAPI TestClient is used when
available; otherwise the tests are skipped.
"""

import pytest
import sys
import os
from unittest.mock import patch

# Ensure the insights_api package can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'insights_api'))

import insights_api as insights_module

# Determine if FastAPI is available for integration tests
try:
    from fastapi.testclient import TestClient
    if hasattr(insights_module, 'app') and insights_module.app:
        client = TestClient(insights_module.app)
        FASTAPI_AVAILABLE = True
    else:
        FASTAPI_AVAILABLE = False
        client = None
except ImportError:
    FASTAPI_AVAILABLE = False
    client = None


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestInsightsEndpoints:
    """Integration tests for Insights API new endpoints"""

    def test_page_health_happy_path(self):
        """GET /api/page-health returns expected schema and data"""
        mock_rows = [
            {
                "property": "https://example.com/",
                "page": "https://example.com/page1",
                "total_clicks": 100,
                "previous_clicks": 80,
                "clicks_wow_change_pct": 25.0,
                "total_impressions": 1000,
                "ctr_percentage": 0.1,
                "avg_position": 5.5,
                "trend_status": "IMPROVING"
            }
        ]
        with patch.object(insights_module.db, 'execute_query', return_value=mock_rows):
            response = client.get("/api/page-health", params={"property": "https://example.com/", "limit": 10, "offset": 0})
            assert response.status_code == 200
            body = response.json()
            assert "data" in body
            assert "total" in body
            assert "limit" in body
            assert "offset" in body
            assert body["total"] == len(mock_rows)
            record = body["data"][0]
            # Validate field mappings
            assert record["property"] == "https://example.com/"
            assert record["page"] == "https://example.com/page1"
            assert record["clicks_current"] == 100
            assert record["clicks_previous"] == 80
            assert record["clicks_change_pct"] == 25.0
            assert record["impressions_current"] == 1000
            assert record["avg_ctr"] == 0.1
            assert record["avg_position"] == 5.5
            assert record["health_status"] == "IMPROVING"

    def test_page_health_invalid_params(self):
        """Invalid limit or offset values trigger validation errors"""
        # Negative limit
        response = client.get("/api/page-health", params={"limit": -1})
        assert response.status_code == 422
        # Negative offset
        response = client.get("/api/page-health", params={"offset": -5})
        assert response.status_code == 422

    def test_query_trends_happy_path(self):
        """GET /api/query-trends returns mapped trend data"""
        mock_rows = [
            {
                "property": "https://example.com/",
                "query": "example term",
                "clicks_change": 50,
                "impressions_change": 500,
                "performance_category": "BIG_WINNER"
            },
            {
                "property": "https://example.com/",
                "query": "another",
                "clicks_change": -20,
                "impressions_change": -200,
                "performance_category": "LOSER"
            }
        ]
        with patch.object(insights_module.db, 'execute_query', return_value=mock_rows):
            # Without category filter
            response = client.get("/api/query-trends", params={"property": "https://example.com/", "limit": 10, "offset": 0})
            assert response.status_code == 200
            body = response.json()
            assert "data" in body and len(body["data"]) == 2
            record0 = body["data"][0]
            assert record0["category"] in ["WINNER", "LOSER", "STABLE"]
            assert record0["clicks_delta"] == mock_rows[0]["clicks_change"]
            assert record0["impressions_delta"] == mock_rows[0]["impressions_change"]
            # With category filter for winners
            response = client.get("/api/query-trends", params={"category": "winner"})
            assert response.status_code == 200
            body = response.json()
            # Only rows classified as winners should remain
            for rec in body["data"]:
                assert rec["category"] == "WINNER"

    def test_query_trends_invalid_category(self):
        """Invalid category yields 422 error"""
        response = client.get("/api/query-trends", params={"category": "unknown"})
        assert response.status_code == 422

    def test_directory_trends_happy_path(self):
        """GET /api/directory-trends returns aggregated directory data"""
        mock_rows = [
            {
                "property": "https://example.com/",
                "directory": "/blog/",
                "clicks_28d": 100,
                "impressions_28d": 1000,
                "ctr_28d_pct": 10.0,
                "avg_position_28d": 7.5,
                "max_unique_pages": 8
            }
        ]
        with patch.object(insights_module.db, 'execute_query', return_value=mock_rows):
            response = client.get("/api/directory-trends", params={"property": "https://example.com/", "min_clicks": 0, "limit": 5})
            assert response.status_code == 200
            body = response.json()
            assert "data" in body and len(body["data"]) == 1
            rec = body["data"][0]
            assert rec["total_clicks"] == 100
            assert rec["total_impressions"] == 1000
            assert rec["avg_ctr"] == 10.0
            assert rec["avg_position"] == 7.5
            assert rec["unique_pages"] == 8

    def test_directory_trends_invalid_limit(self):
        """Invalid limit triggers validation error"""
        response = client.get("/api/directory-trends", params={"limit": 0})
        assert response.status_code == 422

    def test_brand_nonbrand_happy_path(self):
        """GET /api/brand-nonbrand returns brand vs non-brand metrics"""
        mock_rows = [
            {
                "property": "https://example.com/",
                "query_type": "BRAND",
                "total_clicks": 1000,
                "total_impressions": 5000,
                "ctr_pct": 20.0,
                "unique_queries": 50
            },
            {
                "property": "https://example.com/",
                "query_type": "NON_BRAND",
                "total_clicks": 500,
                "total_impressions": 10000,
                "ctr_pct": 5.0,
                "unique_queries": 200
            }
        ]
        with patch.object(insights_module.db, 'execute_query', return_value=mock_rows):
            response = client.get("/api/brand-nonbrand", params={"property": "https://example.com/"})
            assert response.status_code == 200
            body = response.json()
            assert "data" in body and len(body["data"]) == 2
            # Validate keys
            for rec in body["data"]:
                assert set(rec.keys()) == {"property", "query_type", "total_clicks", "total_impressions", "avg_ctr", "query_count"}

    def test_brand_nonbrand_missing_property(self):
        """No property filter should still return data or empty list"""
        # Patch to return empty list to simulate no data for unspecified property
        with patch.object(insights_module.db, 'execute_query', return_value=[]):
            response = client.get("/api/brand-nonbrand")
            assert response.status_code == 200
            body = response.json()
            assert body["data"] == []