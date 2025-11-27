"""
API Integration Tests for Insights API

Tests the complete API functionality including:
- Health and status endpoints
- CRUD operations for insights
- Filtering and pagination
- Query parameters
- Error handling (404, 400, 500)

All tests use httpx AsyncClient with the real FastAPI app instance.
Tests are marked with @pytest.mark.integration to run only with services.
"""

import pytest
import httpx
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator
from fastapi import status as http_status

from insights_api.insights_api import app
from insights_core.models import (
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
    InsightCreate
)
from insights_core.repository import InsightRepository


# Test constants
TEST_PROPERTY = "https://test-domain.com"
TEST_BASE_URL = "http://test"


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Provide httpx AsyncClient connected to the FastAPI app

    Yields:
        AsyncClient configured for testing the app
    """
    async with httpx.AsyncClient(app=app, base_url=TEST_BASE_URL) as client:
        yield client


@pytest.fixture
def repository() -> InsightRepository:
    """
    Provide InsightRepository for test data setup/cleanup

    Returns:
        InsightRepository instance connected to test database
    """
    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    return InsightRepository(dsn)


@pytest.fixture
async def clean_test_data(repository: InsightRepository):
    """
    Clean test data before and after each test

    Ensures clean state for testing by removing all test property insights
    """
    # Clean before test
    conn = repository._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gsc.insights WHERE property = %s", (TEST_PROPERTY,))
            conn.commit()
    finally:
        conn.close()

    yield

    # Clean after test
    conn = repository._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gsc.insights WHERE property = %s", (TEST_PROPERTY,))
            conn.commit()
    finally:
        conn.close()


@pytest.fixture
def sample_insight_data() -> dict:
    """
    Provide sample insight data for testing

    Returns:
        Dict with valid insight creation data
    """
    return {
        "property": TEST_PROPERTY,
        "entity_type": "page",
        "entity_id": "/test-page",
        "category": "risk",
        "title": "Test Risk Insight",
        "description": "Test description for integration testing",
        "severity": "high",
        "confidence": 0.85,
        "metrics": {
            "gsc_clicks": 100.0,
            "gsc_clicks_change": -25.0,
            "gsc_impressions": 1000.0,
            "gsc_impressions_change": -20.0,
            "window_start": "2024-01-01",
            "window_end": "2024-01-07"
        },
        "window_days": 7,
        "source": "integration_test"
    }


@pytest.fixture
async def create_test_insights(repository: InsightRepository, clean_test_data) -> list:
    """
    Create multiple test insights for query/filter testing

    Returns:
        List of created Insight objects
    """
    insights = []

    # Create insights with different categories, severities, and statuses
    test_data = [
        # Risk insights
        {
            "category": InsightCategory.RISK,
            "severity": InsightSeverity.HIGH,
            "entity_id": "/page-1",
            "title": "High Risk Page 1",
        },
        {
            "category": InsightCategory.RISK,
            "severity": InsightSeverity.MEDIUM,
            "entity_id": "/page-2",
            "title": "Medium Risk Page 2",
        },
        # Opportunity insights
        {
            "category": InsightCategory.OPPORTUNITY,
            "severity": InsightSeverity.HIGH,
            "entity_id": "/page-3",
            "title": "High Opportunity Page 3",
        },
        {
            "category": InsightCategory.OPPORTUNITY,
            "severity": InsightSeverity.LOW,
            "entity_id": "/page-4",
            "title": "Low Opportunity Page 4",
        },
        # Trend insights
        {
            "category": InsightCategory.TREND,
            "severity": InsightSeverity.MEDIUM,
            "entity_id": "/page-5",
            "title": "Medium Trend Page 5",
        },
    ]

    for data in test_data:
        insight_create = InsightCreate(
            property=TEST_PROPERTY,
            entity_type=EntityType.PAGE,
            entity_id=data["entity_id"],
            category=data["category"],
            title=data["title"],
            description=f"Test description for {data['title']}",
            severity=data["severity"],
            confidence=0.85,
            metrics=InsightMetrics(
                gsc_clicks=100.0,
                gsc_clicks_change=-15.0
            ),
            window_days=7,
            source="integration_test_fixture"
        )
        insight = repository.create(insight_create)
        insights.append(insight)

    return insights


class TestHealthEndpoints:
    """Test health check and status endpoints"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_endpoint_healthy(self, async_client: httpx.AsyncClient):
        """Test /api/health returns healthy status with database connection"""
        response = await async_client.get("/api/health")

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["database"] == "connected"
        assert "total_insights" in data
        assert isinstance(data["total_insights"], int)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stats_endpoint(self, async_client: httpx.AsyncClient):
        """Test /api/stats returns repository statistics"""
        response = await async_client.get("/api/stats")

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert "data" in data

        stats = data["data"]
        assert "total_insights" in stats
        assert "unique_properties" in stats
        assert "risk_count" in stats
        assert "opportunity_count" in stats
        assert "new_count" in stats
        assert "diagnosed_count" in stats
        assert "high_severity_count" in stats


class TestInsightCRUD:
    """Test CRUD operations for insights"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_and_read_insight(
        self,
        async_client: httpx.AsyncClient,
        repository: InsightRepository,
        sample_insight_data: dict,
        clean_test_data
    ):
        """Test creating an insight via repository and reading it via API"""
        # Create insight using repository
        insight_create = InsightCreate(**sample_insight_data)
        created_insight = repository.create(insight_create)

        # Read via API
        response = await async_client.get(f"/api/insights/{created_insight.id}")

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["data"]["id"] == created_insight.id
        assert data["data"]["title"] == sample_insight_data["title"]
        assert data["data"]["category"] == sample_insight_data["category"]
        assert data["data"]["severity"] == sample_insight_data["severity"]
        assert data["data"]["status"] == "new"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_insight_not_found(self, async_client: httpx.AsyncClient):
        """Test getting non-existent insight returns 404"""
        fake_id = "0" * 64  # Valid format but doesn't exist
        response = await async_client.get(f"/api/insights/{fake_id}")

        assert response.status_code == http_status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_insight_status(
        self,
        async_client: httpx.AsyncClient,
        repository: InsightRepository,
        sample_insight_data: dict,
        clean_test_data
    ):
        """Test updating insight status via API"""
        # Create insight
        insight_create = InsightCreate(**sample_insight_data)
        created_insight = repository.create(insight_create)

        # Update status
        update_data = {
            "status": "investigating"
        }
        response = await async_client.patch(
            f"/api/insights/{created_insight.id}",
            json=update_data
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["message"] == "Insight updated"
        assert data["data"]["status"] == "investigating"
        assert data["data"]["id"] == created_insight.id

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_insight_description(
        self,
        async_client: httpx.AsyncClient,
        repository: InsightRepository,
        sample_insight_data: dict,
        clean_test_data
    ):
        """Test updating insight description via API"""
        # Create insight
        insight_create = InsightCreate(**sample_insight_data)
        created_insight = repository.create(insight_create)

        # Update description
        new_description = "Updated description with more details"
        update_data = {
            "description": new_description
        }
        response = await async_client.patch(
            f"/api/insights/{created_insight.id}",
            json=update_data
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["data"]["description"] == new_description

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_update_nonexistent_insight(self, async_client: httpx.AsyncClient):
        """Test updating non-existent insight returns 404"""
        fake_id = "0" * 64
        update_data = {"status": "investigating"}

        response = await async_client.patch(
            f"/api/insights/{fake_id}",
            json=update_data
        )

        assert response.status_code == http_status.HTTP_404_NOT_FOUND


class TestInsightQuerying:
    """Test insight query endpoints with filters and pagination"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_all_insights(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test querying all insights without filters"""
        response = await async_client.get("/api/insights")

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert "count" in data
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_filter_by_category(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test filtering insights by category"""
        # Query for risk insights
        response = await async_client.get(
            "/api/insights",
            params={"category": "risk", "property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["count"] == 2  # We created 2 risk insights

        # Verify all returned insights are risk category
        for insight in data["data"]:
            assert insight["category"] == "risk"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_filter_by_status(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test filtering insights by status"""
        response = await async_client.get(
            "/api/insights",
            params={"status": "new", "property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        # All fixtures start as 'new' status
        assert data["count"] == 5

        for insight in data["data"]:
            assert insight["status"] == "new"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_filter_by_severity(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test filtering insights by severity"""
        response = await async_client.get(
            "/api/insights",
            params={"severity": "high", "property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["count"] == 2  # 2 high severity insights

        for insight in data["data"]:
            assert insight["severity"] == "high"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multiple_filters(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test combining multiple filters"""
        response = await async_client.get(
            "/api/insights",
            params={
                "property": TEST_PROPERTY,
                "category": "risk",
                "severity": "high"
            }
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["count"] == 1  # Only 1 high-severity risk

        insight = data["data"][0]
        assert insight["category"] == "risk"
        assert insight["severity"] == "high"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pagination_limit(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test pagination with limit parameter"""
        response = await async_client.get(
            "/api/insights",
            params={"property": TEST_PROPERTY, "limit": 2}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["count"] == 2
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert len(data["data"]) == 2

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pagination_offset(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test pagination with offset parameter"""
        # Get first page
        response1 = await async_client.get(
            "/api/insights",
            params={"property": TEST_PROPERTY, "limit": 2, "offset": 0}
        )
        data1 = response1.json()

        # Get second page
        response2 = await async_client.get(
            "/api/insights",
            params={"property": TEST_PROPERTY, "limit": 2, "offset": 2}
        )
        data2 = response2.json()

        assert response1.status_code == http_status.HTTP_200_OK
        assert response2.status_code == http_status.HTTP_200_OK

        # Verify different results
        ids_page1 = {i["id"] for i in data1["data"]}
        ids_page2 = {i["id"] for i in data2["data"]}
        assert len(ids_page1.intersection(ids_page2)) == 0  # No overlap

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_limit_validation(self, async_client: httpx.AsyncClient):
        """Test limit parameter validation (max 1000)"""
        # Test limit too high
        response = await async_client.get(
            "/api/insights",
            params={"limit": 2000}
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_offset_validation(self, async_client: httpx.AsyncClient):
        """Test offset parameter validation (non-negative)"""
        response = await async_client.get(
            "/api/insights",
            params={"offset": -1}
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCategoryEndpoints:
    """Test category-specific endpoints"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_by_category_endpoint(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/category/{category} endpoint"""
        response = await async_client.get(
            "/api/insights/category/opportunity",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["category"] == "opportunity"
        assert data["count"] == 2  # 2 opportunity insights

        for insight in data["data"]:
            assert insight["category"] == "opportunity"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_by_category_with_severity_filter(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test category endpoint with severity filter"""
        response = await async_client.get(
            "/api/insights/category/opportunity",
            params={"property": TEST_PROPERTY, "severity": "high"}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["count"] == 1  # Only 1 high-severity opportunity
        assert data["data"][0]["severity"] == "high"


class TestStatusEndpoints:
    """Test status-specific endpoints"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_by_status_endpoint(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/status/{status} endpoint"""
        response = await async_client.get(
            "/api/insights/status/new",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["insight_status"] == "new"
        assert data["count"] == 5  # All test insights start as 'new'

        for insight in data["data"]:
            assert insight["status"] == "new"


class TestEntityEndpoints:
    """Test entity-specific endpoints"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_for_entity(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/entity/{entity_type}/{entity_id} endpoint"""
        response = await async_client.get(
            "/api/insights/entity/page//page-1",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["entity_type"] == "page"
        assert data["entity_id"] == "/page-1"
        assert data["count"] == 1

        insight = data["data"][0]
        assert insight["entity_id"] == "/page-1"


class TestAggregationEndpoints:
    """Test aggregation and analytics endpoints"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_recent_insights(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/recent/{hours} endpoint"""
        response = await async_client.get(
            "/api/insights/recent/24",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["hours"] == 24
        assert "count" in data
        assert "data" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_actionable_insights(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/actionable endpoint"""
        response = await async_client.get(
            "/api/insights/actionable",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["count"] == 5  # All test insights are 'new' (actionable)

        # Verify sorted by severity (high first)
        insights = data["data"]
        if len(insights) >= 2:
            severity_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(insights) - 1):
                curr_sev = severity_order.get(insights[i]["severity"], 3)
                next_sev = severity_order.get(insights[i + 1]["severity"], 3)
                assert curr_sev <= next_sev

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_property_summary(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test /api/insights/summary/{property} endpoint"""
        response = await async_client.get(
            f"/api/insights/summary/{TEST_PROPERTY}"
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "success"
        assert data["property"] == TEST_PROPERTY

        summary = data["summary"]
        assert summary["total_insights"] == 5
        assert "by_category" in summary
        assert "by_status" in summary
        assert "by_severity" in summary
        assert "recent_insights_7d" in summary
        assert "actionable_count" in summary

        # Verify category breakdown
        assert summary["by_category"]["risk"] == 2
        assert summary["by_category"]["opportunity"] == 2
        assert summary["by_category"]["trend"] == 1


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_category_value(self, async_client: httpx.AsyncClient):
        """Test 422 error for invalid category enum value"""
        response = await async_client.get(
            "/api/insights",
            params={"category": "invalid_category"}
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_severity_value(self, async_client: httpx.AsyncClient):
        """Test 422 error for invalid severity enum value"""
        response = await async_client.get(
            "/api/insights",
            params={"severity": "invalid_severity"}
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_status_value(self, async_client: httpx.AsyncClient):
        """Test 422 error for invalid status enum value"""
        response = await async_client.get(
            "/api/insights",
            params={"status": "invalid_status"}
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_update_data(
        self,
        async_client: httpx.AsyncClient,
        repository: InsightRepository,
        sample_insight_data: dict,
        clean_test_data
    ):
        """Test 400/422 error for invalid update data"""
        # Create insight
        insight_create = InsightCreate(**sample_insight_data)
        created_insight = repository.create(insight_create)

        # Try to update with invalid status
        update_data = {"status": "invalid_status"}
        response = await async_client.patch(
            f"/api/insights/{created_insight.id}",
            json=update_data
        )

        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_recent_hours_range(self, async_client: httpx.AsyncClient):
        """Test 422 error for hours outside valid range (1-168)"""
        # Test hours too high
        response = await async_client.get("/api/insights/recent/200")
        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test hours too low
        response = await async_client.get("/api/insights/recent/0")
        assert response.status_code == http_status.HTTP_422_UNPROCESSABLE_ENTITY


class TestResponseFormats:
    """Test response format consistency"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_success_response_format(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test all successful responses have consistent format"""
        response = await async_client.get(
            "/api/insights",
            params={"property": TEST_PROPERTY}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        # Standard success format
        assert "status" in data
        assert data["status"] == "success"
        assert "data" in data or "count" in data

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_insight_data_structure(
        self,
        async_client: httpx.AsyncClient,
        create_test_insights
    ):
        """Test insight objects have all required fields"""
        response = await async_client.get(
            "/api/insights",
            params={"property": TEST_PROPERTY, "limit": 1}
        )

        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        insight = data["data"][0]

        # Verify all required fields present
        required_fields = [
            "id", "generated_at", "property", "entity_type", "entity_id",
            "category", "title", "description", "severity", "confidence",
            "metrics", "window_days", "source", "status"
        ]

        for field in required_fields:
            assert field in insight, f"Missing required field: {field}"

        # Verify metrics structure
        assert isinstance(insight["metrics"], dict)

        # Verify enum values
        assert insight["category"] in ["risk", "opportunity", "trend", "diagnosis"]
        assert insight["severity"] in ["low", "medium", "high"]
        assert insight["status"] in ["new", "investigating", "diagnosed", "actioned", "resolved"]
        assert insight["entity_type"] in ["page", "query", "directory", "property"]


class TestFullCRUDFlow:
    """Test complete CRUD workflow from start to finish"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_insight_lifecycle(
        self,
        async_client: httpx.AsyncClient,
        repository: InsightRepository,
        sample_insight_data: dict,
        clean_test_data
    ):
        """
        Test complete lifecycle: create -> read -> update -> verify

        This test validates the full CRUD flow in a realistic scenario
        """
        # Step 1: Create insight
        insight_create = InsightCreate(**sample_insight_data)
        created_insight = repository.create(insight_create)

        assert created_insight is not None
        assert created_insight.id is not None
        insight_id = created_insight.id

        # Step 2: Read insight - verify initial state
        response = await async_client.get(f"/api/insights/{insight_id}")
        assert response.status_code == http_status.HTTP_200_OK
        data = response.json()

        assert data["data"]["status"] == "new"
        assert data["data"]["title"] == sample_insight_data["title"]

        # Step 3: Update to investigating status
        update_data = {"status": "investigating"}
        response = await async_client.patch(
            f"/api/insights/{insight_id}",
            json=update_data
        )
        assert response.status_code == http_status.HTTP_200_OK

        # Step 4: Verify update
        response = await async_client.get(f"/api/insights/{insight_id}")
        data = response.json()
        assert data["data"]["status"] == "investigating"

        # Step 5: Update to diagnosed with linked insight
        update_data = {
            "status": "diagnosed",
            "description": "Root cause identified: Server response time increased"
        }
        response = await async_client.patch(
            f"/api/insights/{insight_id}",
            json=update_data
        )
        assert response.status_code == http_status.HTTP_200_OK

        # Step 6: Final verification
        response = await async_client.get(f"/api/insights/{insight_id}")
        data = response.json()

        assert data["data"]["status"] == "diagnosed"
        assert "Root cause identified" in data["data"]["description"]

        # Step 7: Verify it appears in actionable insights
        response = await async_client.get(
            "/api/insights/actionable",
            params={"property": TEST_PROPERTY}
        )
        data = response.json()

        # Find our insight in actionable list
        insight_ids = [i["id"] for i in data["data"]]
        assert insight_id in insight_ids
