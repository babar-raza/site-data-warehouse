"""
API Contract Tests

Comprehensive contract validation tests for the Insights API.
Validates JSON schemas for all endpoints to ensure API consistency.

Tests marked with @pytest.mark.e2e
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jsonschema import validate, ValidationError
from typing import Dict, Any


# ============================================================================
# JSON SCHEMAS
# ============================================================================

INSIGHT_METRICS_SCHEMA = {
    "type": "object",
    "properties": {
        "gsc_clicks": {"type": ["number", "null"]},
        "gsc_clicks_change": {"type": ["number", "null"]},
        "gsc_impressions": {"type": ["number", "null"]},
        "gsc_impressions_change": {"type": ["number", "null"]},
        "gsc_ctr": {"type": ["number", "null"]},
        "gsc_ctr_change": {"type": ["number", "null"]},
        "gsc_position": {"type": ["number", "null"]},
        "gsc_position_change": {"type": ["number", "null"]},
        "window_start": {"type": ["string", "null"]},
        "window_end": {"type": ["string", "null"]},
        "comparison_start": {"type": ["string", "null"]},
        "comparison_end": {"type": ["string", "null"]}
    },
    "additionalProperties": True  # Allow detector-specific metrics
}

INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "maxLength": 64},
        "property": {"type": "string", "maxLength": 500},
        "entity_type": {
            "type": "string",
            "enum": ["page", "query", "directory", "property"]
        },
        "entity_id": {"type": "string"},
        "category": {
            "type": "string",
            "enum": ["risk", "opportunity", "trend", "diagnosis"]
        },
        "title": {"type": "string", "maxLength": 200},
        "description": {"type": "string"},
        "severity": {
            "type": "string",
            "enum": ["low", "medium", "high"]
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "status": {
            "type": "string",
            "enum": ["new", "investigating", "diagnosed", "actioned", "resolved"]
        },
        "metrics": INSIGHT_METRICS_SCHEMA,
        "window_days": {"type": "integer", "minimum": 1, "maximum": 365},
        "source": {"type": "string", "maxLength": 100},
        "generated_at": {"type": "string", "format": "date-time"},
        "linked_insight_id": {"type": ["string", "null"], "maxLength": 64},
        "created_at": {"type": ["string", "null"], "format": "date-time"},
        "updated_at": {"type": ["string", "null"], "format": "date-time"}
    },
    "required": [
        "id", "property", "entity_type", "entity_id", "category",
        "title", "description", "severity", "confidence", "metrics",
        "window_days", "source", "generated_at", "status"
    ],
    "additionalProperties": False
}

INSIGHTS_LIST_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "count": {"type": "integer", "minimum": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
        "offset": {"type": "integer", "minimum": 0},
        "data": {
            "type": "array",
            "items": INSIGHT_SCHEMA
        }
    },
    "required": ["status", "count", "limit", "offset", "data"],
    "additionalProperties": False
}

INSIGHT_SINGLE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "data": INSIGHT_SCHEMA
    },
    "required": ["status", "data"],
    "additionalProperties": False
}

HEALTH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["healthy", "initializing", "unhealthy"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "database": {"type": "string", "enum": ["connected"]},
        "total_insights": {"type": "integer", "minimum": 0}
    },
    "required": ["status"],
    "anyOf": [
        {"required": ["status", "timestamp", "database", "total_insights"]},
        {"required": ["status"]}
    ],
    "additionalProperties": False
}

HEALTH_ERROR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["unhealthy"]},
        "error": {"type": "string"}
    },
    "required": ["status", "error"],
    "additionalProperties": False
}

ERROR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "detail": {"type": "string"}
    },
    "required": ["detail"],
    "additionalProperties": False
}

CATEGORY_LIST_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "category": {"type": "string", "enum": ["risk", "opportunity", "trend", "diagnosis"]},
        "count": {"type": "integer", "minimum": 0},
        "data": {
            "type": "array",
            "items": INSIGHT_SCHEMA
        }
    },
    "required": ["status", "category", "count", "data"],
    "additionalProperties": False
}

STATUS_LIST_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "insight_status": {
            "type": "string",
            "enum": ["new", "investigating", "diagnosed", "actioned", "resolved"]
        },
        "count": {"type": "integer", "minimum": 0},
        "data": {
            "type": "array",
            "items": INSIGHT_SCHEMA
        }
    },
    "required": ["status", "insight_status", "count", "data"],
    "additionalProperties": False
}

STATS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "data": {"type": "object"}
    },
    "required": ["status", "data"],
    "additionalProperties": False
}

UPDATE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "message": {"type": "string"},
        "data": INSIGHT_SCHEMA
    },
    "required": ["status", "message", "data"],
    "additionalProperties": False
}


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture
def sample_insight_data() -> Dict[str, Any]:
    """Sample insight data matching the Insight model"""
    return {
        "id": "abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcdef",
        "property": "sc-domain:example.com",
        "entity_type": "page",
        "entity_id": "/blog/article-1",
        "category": "risk",
        "title": "Significant traffic drop detected",
        "description": "Page experienced a 50% drop in clicks compared to previous period",
        "severity": "high",
        "confidence": 0.95,
        "status": "new",
        "metrics": {
            "gsc_clicks": 50.0,
            "gsc_clicks_change": -50.0,
            "gsc_impressions": 1000.0,
            "gsc_impressions_change": 0.0,
            "gsc_ctr": 5.0,
            "gsc_ctr_change": -2.5,
            "gsc_position": 5.5,
            "gsc_position_change": 0.5,
            "window_start": "2024-01-01",
            "window_end": "2024-01-07",
            "comparison_start": "2023-12-25",
            "comparison_end": "2023-12-31"
        },
        "window_days": 7,
        "source": "AnomalyDetector",
        "generated_at": "2024-01-15T10:30:00",
        "linked_insight_id": None,
        "created_at": "2024-01-15T10:30:00",
        "updated_at": "2024-01-15T10:30:00"
    }


@pytest.fixture
def client():
    """FastAPI test client"""
    from insights_api.insights_api import app
    return TestClient(app)


# ============================================================================
# CONTRACT TESTS - GET /api/insights
# ============================================================================

@pytest.mark.e2e
class TestGetInsightsContract:
    """Contract tests for GET /api/insights endpoint"""

    @patch('insights_api.insights_api.repository')
    def test_insights_list_schema_valid(self, mock_repo, client, sample_insight_data):
        """Test that GET /api/insights returns valid schema"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.query.return_value = [mock_insight]

        response = client.get("/api/insights?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=INSIGHTS_LIST_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert isinstance(data["count"], int)
        assert isinstance(data["limit"], int)
        assert isinstance(data["offset"], int)
        assert isinstance(data["data"], list)

    @patch('insights_api.insights_api.repository')
    def test_insights_list_empty_response(self, mock_repo, client):
        """Test insights list with no results"""
        mock_repo.query.return_value = []

        response = client.get("/api/insights")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=INSIGHTS_LIST_RESPONSE_SCHEMA)
        assert data["count"] == 0
        assert data["data"] == []

    @patch('insights_api.insights_api.repository')
    def test_insights_list_with_filters(self, mock_repo, client, sample_insight_data):
        """Test insights list with query parameters"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.query.return_value = [mock_insight]

        response = client.get(
            "/api/insights?property=sc-domain:example.com&category=risk"
            "&severity=high&status=new&limit=50&offset=10"
        )

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=INSIGHTS_LIST_RESPONSE_SCHEMA)
        assert data["limit"] == 50
        assert data["offset"] == 10

    @patch('insights_api.insights_api.repository')
    def test_insights_list_validates_insight_objects(self, mock_repo, client, sample_insight_data):
        """Test that individual insights in list match schema"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.query.return_value = [mock_insight]

        response = client.get("/api/insights")
        data = response.json()

        for insight in data["data"]:
            validate(instance=insight, schema=INSIGHT_SCHEMA)

            assert "id" in insight
            assert "property" in insight
            assert "entity_type" in insight
            assert "category" in insight
            assert "severity" in insight
            assert "confidence" in insight
            assert "status" in insight


# ============================================================================
# CONTRACT TESTS - GET /api/insights/{id}
# ============================================================================

@pytest.mark.e2e
class TestGetInsightByIdContract:
    """Contract tests for GET /api/insights/{id} endpoint"""

    @patch('insights_api.insights_api.repository')
    def test_insight_single_schema_valid(self, mock_repo, client, sample_insight_data):
        """Test that GET /api/insights/{id} returns valid schema"""
        from insights_core.models import Insight

        insight_id = sample_insight_data["id"]
        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_id.return_value = mock_insight

        response = client.get(f"/api/insights/{insight_id}")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=INSIGHT_SINGLE_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert "data" in data
        assert data["data"]["id"] == insight_id

    @patch('insights_api.insights_api.repository')
    def test_insight_single_all_required_fields(self, mock_repo, client, sample_insight_data):
        """Test that single insight has all required fields"""
        from insights_core.models import Insight

        insight_id = sample_insight_data["id"]
        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_id.return_value = mock_insight

        response = client.get(f"/api/insights/{insight_id}")
        data = response.json()

        insight = data["data"]

        validate(instance=insight, schema=INSIGHT_SCHEMA)

        required_fields = [
            "id", "property", "entity_type", "entity_id", "category",
            "title", "description", "severity", "confidence", "metrics",
            "window_days", "source", "generated_at", "status"
        ]

        for field in required_fields:
            assert field in insight, f"Required field '{field}' missing"

    @patch('insights_api.insights_api.repository')
    def test_insight_metrics_schema(self, mock_repo, client, sample_insight_data):
        """Test that insight metrics follow schema"""
        from insights_core.models import Insight

        insight_id = sample_insight_data["id"]
        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_id.return_value = mock_insight

        response = client.get(f"/api/insights/{insight_id}")
        data = response.json()

        metrics = data["data"]["metrics"]

        validate(instance=metrics, schema=INSIGHT_METRICS_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_insight_not_found_error_schema(self, mock_repo, client):
        """Test 404 error response schema"""
        mock_repo.get_by_id.return_value = None

        response = client.get("/api/insights/nonexistent-id")

        assert response.status_code == 404
        data = response.json()

        validate(instance=data, schema=ERROR_RESPONSE_SCHEMA)
        assert "detail" in data
        assert "not found" in data["detail"].lower()


# ============================================================================
# CONTRACT TESTS - GET /api/health
# ============================================================================

@pytest.mark.e2e
class TestHealthEndpointContract:
    """Contract tests for GET /api/health endpoint"""

    @patch('insights_api.insights_api.repository')
    def test_health_healthy_schema(self, mock_repo, client):
        """Test health endpoint returns valid schema when healthy"""
        mock_repo.get_stats.return_value = {"total_insights": 100}

        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=HEALTH_RESPONSE_SCHEMA)

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["database"] == "connected"
        assert isinstance(data["total_insights"], int)
        assert data["total_insights"] >= 0

    @patch('insights_api.insights_api.repository')
    def test_health_required_fields(self, mock_repo, client):
        """Test health endpoint has all required fields"""
        mock_repo.get_stats.return_value = {"total_insights": 50}

        response = client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "database" in data
        assert "total_insights" in data

    def test_health_initializing_schema(self):
        """Test health endpoint when repository not initialized"""
        with patch('insights_api.insights_api.repository', None):
            from insights_api.insights_api import app
            client = TestClient(app)

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()

            assert "status" in data
            assert data["status"] == "initializing"

    @patch('insights_api.insights_api.repository')
    def test_health_error_schema(self, mock_repo, client):
        """Test health endpoint error response schema"""
        mock_repo.get_stats.side_effect = Exception("Database connection failed")

        response = client.get("/api/health")

        assert response.status_code == 503
        data = response.json()

        validate(instance=data, schema=HEALTH_ERROR_RESPONSE_SCHEMA)
        assert data["status"] == "unhealthy"
        assert "error" in data


# ============================================================================
# CONTRACT TESTS - GET /api/stats
# ============================================================================

@pytest.mark.e2e
class TestStatsEndpointContract:
    """Contract tests for GET /api/stats endpoint"""

    @patch('insights_api.insights_api.repository')
    def test_stats_schema_valid(self, mock_repo, client):
        """Test stats endpoint returns valid schema"""
        mock_repo.get_stats.return_value = {"total_insights": 100}

        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=STATS_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert "data" in data
        assert isinstance(data["data"], dict)

    @patch('insights_api.insights_api.repository')
    def test_stats_error_schema(self, mock_repo, client):
        """Test stats endpoint error response"""
        mock_repo.get_stats.side_effect = Exception("Stats query failed")

        response = client.get("/api/stats")

        assert response.status_code == 500
        data = response.json()

        validate(instance=data, schema=ERROR_RESPONSE_SCHEMA)


# ============================================================================
# CONTRACT TESTS - GET /api/insights/category/{category}
# ============================================================================

@pytest.mark.e2e
class TestGetByCategoryContract:
    """Contract tests for GET /api/insights/category/{category}"""

    @patch('insights_api.insights_api.repository')
    def test_category_response_schema(self, mock_repo, client, sample_insight_data):
        """Test category endpoint response schema"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_category.return_value = [mock_insight]

        response = client.get("/api/insights/category/risk")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=CATEGORY_LIST_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert data["category"] == "risk"
        assert isinstance(data["count"], int)
        assert isinstance(data["data"], list)

    @patch('insights_api.insights_api.repository')
    def test_category_all_categories(self, mock_repo, client, sample_insight_data):
        """Test all valid category values"""
        from insights_core.models import Insight

        categories = ["risk", "opportunity", "trend", "diagnosis"]

        for category in categories:
            sample_data = sample_insight_data.copy()
            sample_data["category"] = category

            mock_insight = Insight(**sample_data)
            mock_repo.get_by_category.return_value = [mock_insight]

            response = client.get(f"/api/insights/category/{category}")

            assert response.status_code == 200
            data = response.json()

            validate(instance=data, schema=CATEGORY_LIST_RESPONSE_SCHEMA)
            assert data["category"] == category


# ============================================================================
# CONTRACT TESTS - GET /api/insights/status/{status}
# ============================================================================

@pytest.mark.e2e
class TestGetByStatusContract:
    """Contract tests for GET /api/insights/status/{status}"""

    @patch('insights_api.insights_api.repository')
    def test_status_response_schema(self, mock_repo, client, sample_insight_data):
        """Test status endpoint response schema"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_status.return_value = [mock_insight]

        response = client.get("/api/insights/status/new")

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=STATUS_LIST_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert data["insight_status"] == "new"
        assert isinstance(data["count"], int)
        assert isinstance(data["data"], list)

    @patch('insights_api.insights_api.repository')
    def test_status_all_statuses(self, mock_repo, client, sample_insight_data):
        """Test all valid status values"""
        from insights_core.models import Insight

        statuses = ["new", "investigating", "diagnosed", "actioned", "resolved"]

        for status in statuses:
            sample_data = sample_insight_data.copy()
            sample_data["status"] = status

            mock_insight = Insight(**sample_data)
            mock_repo.get_by_status.return_value = [mock_insight]

            response = client.get(f"/api/insights/status/{status}")

            assert response.status_code == 200
            data = response.json()

            validate(instance=data, schema=STATUS_LIST_RESPONSE_SCHEMA)
            assert data["insight_status"] == status


# ============================================================================
# CONTRACT TESTS - PATCH /api/insights/{id}
# ============================================================================

@pytest.mark.e2e
class TestUpdateInsightContract:
    """Contract tests for PATCH /api/insights/{id}"""

    @patch('insights_api.insights_api.repository')
    def test_update_response_schema(self, mock_repo, client, sample_insight_data):
        """Test update endpoint response schema"""
        from insights_core.models import Insight

        insight_id = sample_insight_data["id"]
        mock_insight = Insight(**sample_insight_data)
        mock_repo.update.return_value = mock_insight

        update_data = {"status": "investigating"}

        response = client.patch(f"/api/insights/{insight_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()

        validate(instance=data, schema=UPDATE_RESPONSE_SCHEMA)

        assert data["status"] == "success"
        assert "message" in data
        assert "data" in data
        validate(instance=data["data"], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_update_not_found_error(self, mock_repo, client):
        """Test update endpoint 404 error schema"""
        mock_repo.update.return_value = None

        update_data = {"status": "investigating"}

        response = client.patch("/api/insights/nonexistent", json=update_data)

        assert response.status_code == 404
        data = response.json()

        validate(instance=data, schema=ERROR_RESPONSE_SCHEMA)


# ============================================================================
# CONTRACT TESTS - ERROR RESPONSES
# ============================================================================

@pytest.mark.e2e
class TestErrorResponseContracts:
    """Contract tests for error responses across all endpoints"""

    @patch('insights_api.insights_api.repository')
    def test_500_error_schema(self, mock_repo, client):
        """Test 500 error response schema"""
        mock_repo.query.side_effect = Exception("Database error")

        response = client.get("/api/insights")

        assert response.status_code == 500
        data = response.json()

        validate(instance=data, schema=ERROR_RESPONSE_SCHEMA)
        assert "detail" in data

    @patch('insights_api.insights_api.repository')
    def test_404_error_schema(self, mock_repo, client):
        """Test 404 error response schema"""
        mock_repo.get_by_id.return_value = None

        response = client.get("/api/insights/invalid-id-123")

        assert response.status_code == 404
        data = response.json()

        validate(instance=data, schema=ERROR_RESPONSE_SCHEMA)
        assert "detail" in data

    def test_422_validation_error_schema(self, client):
        """Test 422 validation error for invalid parameters"""
        response = client.get("/api/insights?severity=invalid")

        assert response.status_code == 422
        data = response.json()

        assert "detail" in data
        assert isinstance(data["detail"], list)


# ============================================================================
# CONTRACT TESTS - ENUM VALUES
# ============================================================================

@pytest.mark.e2e
class TestEnumContracts:
    """Contract tests for enum values in responses"""

    @patch('insights_api.insights_api.repository')
    def test_entity_type_enum_values(self, mock_repo, client, sample_insight_data):
        """Test that entity_type only contains valid enum values"""
        from insights_core.models import Insight

        valid_entity_types = ["page", "query", "directory", "property"]

        for entity_type in valid_entity_types:
            sample_data = sample_insight_data.copy()
            sample_data["entity_type"] = entity_type

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert data["data"][0]["entity_type"] == entity_type
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_severity_enum_values(self, mock_repo, client, sample_insight_data):
        """Test that severity only contains valid enum values"""
        from insights_core.models import Insight

        valid_severities = ["low", "medium", "high"]

        for severity in valid_severities:
            sample_data = sample_insight_data.copy()
            sample_data["severity"] = severity

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert data["data"][0]["severity"] == severity
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_category_enum_values(self, mock_repo, client, sample_insight_data):
        """Test that category only contains valid enum values"""
        from insights_core.models import Insight

        valid_categories = ["risk", "opportunity", "trend", "diagnosis"]

        for category in valid_categories:
            sample_data = sample_insight_data.copy()
            sample_data["category"] = category

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert data["data"][0]["category"] == category
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_status_enum_values(self, mock_repo, client, sample_insight_data):
        """Test that status only contains valid enum values"""
        from insights_core.models import Insight

        valid_statuses = ["new", "investigating", "diagnosed", "actioned", "resolved"]

        for status in valid_statuses:
            sample_data = sample_insight_data.copy()
            sample_data["status"] = status

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert data["data"][0]["status"] == status
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)


# ============================================================================
# CONTRACT TESTS - FIELD CONSTRAINTS
# ============================================================================

@pytest.mark.e2e
class TestFieldConstraints:
    """Contract tests for field constraints and validation"""

    @patch('insights_api.insights_api.repository')
    def test_confidence_range(self, mock_repo, client, sample_insight_data):
        """Test that confidence is between 0.0 and 1.0"""
        from insights_core.models import Insight

        for confidence in [0.0, 0.5, 0.95, 1.0]:
            sample_data = sample_insight_data.copy()
            sample_data["confidence"] = confidence

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert 0.0 <= data["data"][0]["confidence"] <= 1.0
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_window_days_range(self, mock_repo, client, sample_insight_data):
        """Test that window_days is between 1 and 365"""
        from insights_core.models import Insight

        for window_days in [1, 7, 30, 90, 365]:
            sample_data = sample_insight_data.copy()
            sample_data["window_days"] = window_days

            mock_insight = Insight(**sample_data)
            mock_repo.query.return_value = [mock_insight]

            response = client.get("/api/insights")
            data = response.json()

            assert 1 <= data["data"][0]["window_days"] <= 365
            validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_id_max_length(self, mock_repo, client, sample_insight_data):
        """Test that id field respects max length"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.get_by_id.return_value = mock_insight

        response = client.get(f"/api/insights/{sample_insight_data['id']}")
        data = response.json()

        assert len(data["data"]["id"]) <= 64
        validate(instance=data["data"], schema=INSIGHT_SCHEMA)

    @patch('insights_api.insights_api.repository')
    def test_title_max_length(self, mock_repo, client, sample_insight_data):
        """Test that title field respects max length"""
        from insights_core.models import Insight

        mock_insight = Insight(**sample_insight_data)
        mock_repo.query.return_value = [mock_insight]

        response = client.get("/api/insights")
        data = response.json()

        assert len(data["data"][0]["title"]) <= 200
        validate(instance=data["data"][0], schema=INSIGHT_SCHEMA)
