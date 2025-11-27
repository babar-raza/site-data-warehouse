"""
Tests for Action Execution API Routes
=====================================
Tests for the action execution endpoints.
"""
import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


# Import app after setting up test environment
@pytest.fixture
def mock_env():
    """Set up test environment variables."""
    with patch.dict(os.environ, {
        "WAREHOUSE_DSN": "postgresql://test:test@localhost:5432/test",
        "HUGO_CONTENT_PATH": "/test/content",
        "OLLAMA_BASE_URL": "http://localhost:11434"
    }):
        yield


@pytest.fixture
def client(mock_env):
    """Create test client."""
    from insights_api.insights_api import app
    return TestClient(app)


@pytest.fixture
def sample_action_id():
    """Generate a sample action UUID."""
    return str(uuid4())


@pytest.fixture
def sample_action_row(sample_action_id):
    """Create a sample action database row."""
    return {
        "id": sample_action_id,
        "insight_id": str(uuid4()),
        "property": "https://blog.test.com",
        "action_type": "content_update",
        "title": "Optimize page title",
        "description": "SEO title optimization",
        "priority": "high",
        "effort": "low",
        "estimated_impact": "medium",
        "status": "pending",
        "metadata": {"page_path": "/test-article/", "template_name": "title_optimization"},
        "entity_id": "/test-article/",
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None,
        "outcome": None
    }


class TestExecuteAction:
    """Test POST /api/v1/actions/{action_id}/execute endpoint."""

    def test_invalid_action_id_format(self, client):
        """Test rejection of invalid UUID format."""
        response = client.post("/api/v1/actions/invalid-uuid/execute")
        assert response.status_code == 400
        assert "Invalid action ID" in response.json()["detail"]

    def test_action_not_found(self, client, mock_env):
        """Test 404 when action doesn't exist."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            action_id = str(uuid4())
            response = client.post(f"/api/v1/actions/{action_id}/execute")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_action_already_completed(self, client, sample_action_row):
        """Test 409 when action already completed."""
        sample_action_row["status"] = "completed"

        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.post(f"/api/v1/actions/{sample_action_row['id']}/execute")

            assert response.status_code == 409
            assert "already completed" in response.json()["detail"]

    def test_action_in_progress(self, client, sample_action_row):
        """Test 409 when action is in progress."""
        sample_action_row["status"] = "in_progress"

        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.post(f"/api/v1/actions/{sample_action_row['id']}/execute")

            assert response.status_code == 409
            assert "in progress" in response.json()["detail"]

    def test_dry_run_validation(self, client, sample_action_row):
        """Test dry run validates without executing."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            with patch("insights_api.routes.actions.HugoConfig") as mock_config_class:
                mock_config = MagicMock()
                mock_config.is_configured.return_value = True
                mock_config.validate_path.return_value = None
                mock_config.extract_subdomain.return_value = "blog.test.com"
                mock_config.get_content_file_path.return_value = "/test/content/blog.test.com/test-article/index.md"
                mock_config_class.from_env.return_value = mock_config

                with patch("os.path.exists", return_value=False):
                    response = client.post(
                        f"/api/v1/actions/{sample_action_row['id']}/execute",
                        json={"dry_run": True}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "validated"
                    assert data["success"] is False  # File doesn't exist


class TestExecuteBatch:
    """Test POST /api/v1/actions/execute-batch endpoint."""

    def test_batch_empty_list(self, client):
        """Test rejection of empty action list."""
        response = client.post(
            "/api/v1/actions/execute-batch",
            json={"action_ids": []}
        )
        assert response.status_code == 422  # Validation error

    def test_batch_too_many_actions(self, client):
        """Test rejection of too many actions."""
        action_ids = [str(uuid4()) for _ in range(51)]
        response = client.post(
            "/api/v1/actions/execute-batch",
            json={"action_ids": action_ids}
        )
        assert response.status_code == 422

    def test_batch_dry_run(self, client, sample_action_row):
        """Test batch dry run."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            with patch("insights_api.routes.actions.get_hugo_config"):
                with patch("insights_api.routes.actions.HugoContentWriter"):
                    response = client.post(
                        "/api/v1/actions/execute-batch",
                        json={
                            "action_ids": [sample_action_row["id"]],
                            "dry_run": True
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["total"] == 1
                    assert data["successful"] == 1
                    assert data["failed"] == 0


class TestGetActionStatus:
    """Test GET /api/v1/actions/{action_id}/status endpoint."""

    def test_invalid_action_id(self, client):
        """Test rejection of invalid UUID."""
        response = client.get("/api/v1/actions/not-a-uuid/status")
        assert response.status_code == 400

    def test_action_not_found(self, client):
        """Test 404 for non-existent action."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            action_id = str(uuid4())
            response = client.get(f"/api/v1/actions/{action_id}/status")

            assert response.status_code == 404

    def test_get_status_success(self, client, sample_action_row):
        """Test successful status retrieval."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get(f"/api/v1/actions/{sample_action_row['id']}/status")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == sample_action_row["id"]
            assert data["status"] == "pending"


class TestListPendingActions:
    """Test GET /api/v1/actions/pending endpoint."""

    def test_list_pending_default(self, client, sample_action_row):
        """Test listing pending actions with defaults."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [sample_action_row]
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get("/api/v1/actions/pending")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "pending"

    def test_list_pending_with_filters(self, client, sample_action_row):
        """Test listing with property and priority filters."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [sample_action_row]
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get(
                "/api/v1/actions/pending",
                params={
                    "property": "https://blog.test.com",
                    "priority": "high",
                    "limit": 10
                }
            )

            assert response.status_code == 200

    def test_list_pending_empty(self, client):
        """Test empty results."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get("/api/v1/actions/pending")

            assert response.status_code == 200
            assert response.json() == []


class TestExecutionReady:
    """Test GET /api/v1/actions/execution-ready endpoint."""

    def test_all_services_down(self, client):
        """Test when all services are unavailable."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_db.side_effect = Exception("DB connection failed")

            with patch("insights_api.routes.actions.HugoConfig") as mock_config:
                mock_config.from_env.side_effect = Exception("Config error")

                response = client.get("/api/v1/actions/execution-ready")

                assert response.status_code == 200
                data = response.json()
                assert data["ready"] is False
                assert len(data["errors"]) > 0

    def test_database_ready(self, client):
        """Test when database is ready."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            with patch("insights_api.routes.actions.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                mock_config.from_env.return_value = config_instance

                with patch("httpx.Client") as mock_httpx:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_httpx.return_value.__enter__.return_value.get.return_value = mock_response

                    response = client.get("/api/v1/actions/execution-ready")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["database"] is True
                    assert data["hugo_config"] is True


class TestRequestModels:
    """Test request/response model validation."""

    def test_execute_request_defaults(self, client, sample_action_row):
        """Test default values in execute request."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            with patch("insights_api.routes.actions.get_content_writer") as mock_writer:
                mock_writer.return_value.execute_action.return_value = {
                    "success": True,
                    "changes_made": []
                }

                response = client.post(
                    f"/api/v1/actions/{sample_action_row['id']}/execute",
                    json={}  # Empty body should use defaults
                )

                # Should not fail validation
                assert response.status_code in [200, 503]  # 503 if Hugo not configured

    def test_batch_request_validation(self, client):
        """Test batch request validation."""
        # Invalid - not a list
        response = client.post(
            "/api/v1/actions/execute-batch",
            json={"action_ids": "not-a-list"}
        )
        assert response.status_code == 422

        # Invalid - wrong type in list
        response = client.post(
            "/api/v1/actions/execute-batch",
            json={"action_ids": [123, 456]}
        )
        # Should still work as they'll be converted to strings
        # The UUID validation happens later


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_database_error(self, client, sample_action_id):
        """Test handling of database errors."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_db.side_effect = Exception("Connection refused")

            response = client.get(f"/api/v1/actions/{sample_action_id}/status")

            assert response.status_code in [400, 500]  # 400 if UUID invalid, 500 if DB error

    def test_hugo_not_configured(self, client, sample_action_row):
        """Test handling when Hugo is not configured."""
        with patch("insights_api.routes.actions.get_db_connection") as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = sample_action_row
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_db.return_value = mock_conn

            with patch("insights_api.routes.actions.get_hugo_config") as mock_config:
                from fastapi import HTTPException
                mock_config.side_effect = HTTPException(
                    status_code=503,
                    detail="Hugo not configured"
                )

                response = client.post(
                    f"/api/v1/actions/{sample_action_row['id']}/execute"
                )

                assert response.status_code == 503
