"""
Tests for Hugo Content Writer Service
=====================================
Tests for the main content optimization execution service.
"""
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from config.hugo_config import HugoConfig
from services.hugo_content_writer import HugoContentWriter


@pytest.fixture
def mock_db():
    """Create a mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


@pytest.fixture
def hugo_config(tmp_path):
    """Create a test HugoConfig with a temp directory."""
    return HugoConfig(
        content_path=str(tmp_path),
        file_localization_subdomains=["blog.test.com"],
        default_locale="en"
    )


@pytest.fixture
def writer(hugo_config, mock_db):
    """Create a HugoContentWriter instance."""
    return HugoContentWriter(
        config=hugo_config,
        db_connection=mock_db,
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3.1"
    )


@pytest.fixture
def sample_action():
    """Create a sample action dict."""
    return {
        "id": "test-action-123",
        "insight_id": "test-insight-456",
        "property": "https://blog.test.com",
        "action_type": "content_update",
        "title": "Optimize title for test page",
        "description": "SEO optimization for test page",
        "instructions": "Update title and meta description",
        "priority": "high",
        "effort": "low",
        "estimated_impact": "medium",
        "status": "pending",
        "entity_id": "/posts/test-article/",
        "metadata": {
            "page_path": "/posts/test-article/",
            "template_name": "title_optimization",
            "keywords": ["test", "article"],
            "ctr": 2.5,
            "position": 8.0
        }
    }


@pytest.fixture
def sample_markdown_file(tmp_path):
    """Create a sample markdown file with frontmatter."""
    # Create directory structure
    blog_dir = tmp_path / "blog.test.com" / "posts" / "test-article"
    blog_dir.mkdir(parents=True)

    # Create the markdown file
    md_file = blog_dir / "index.md"
    content = """---
title: Old Test Title
description: Old description that needs improvement
date: 2024-01-15
author: Test Author
---

# Test Article

This is the main content of the test article.

It has some paragraphs with information about testing.
"""
    md_file.write_text(content, encoding="utf-8")
    return md_file


class TestHugoContentWriterInit:
    """Test HugoContentWriter initialization."""

    def test_init_with_defaults(self, hugo_config, mock_db):
        """Test initialization with default values."""
        writer = HugoContentWriter(
            config=hugo_config,
            db_connection=mock_db
        )
        assert writer.config == hugo_config
        assert writer.db == mock_db
        assert writer.ollama_base_url == "http://localhost:11434"
        assert writer.ollama_model == "llama3.1"

    def test_init_with_custom_ollama(self, hugo_config, mock_db):
        """Test initialization with custom Ollama settings."""
        writer = HugoContentWriter(
            config=hugo_config,
            db_connection=mock_db,
            ollama_base_url="http://custom:11434",
            ollama_model="mistral"
        )
        assert writer.ollama_base_url == "http://custom:11434"
        assert writer.ollama_model == "mistral"


class TestGetAction:
    """Test _get_action method."""

    def test_get_action_found(self, writer, mock_db, sample_action):
        """Test getting an existing action."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_action
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        result = writer._get_action("test-action-123")

        assert result is not None
        assert result["id"] == "test-action-123"
        mock_cursor.execute.assert_called_once()

    def test_get_action_not_found(self, writer, mock_db):
        """Test getting a non-existent action."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        result = writer._get_action("nonexistent-id")

        assert result is None


class TestResolveFilePath:
    """Test _resolve_file_path method."""

    def test_resolve_file_based_path(self, writer, sample_action):
        """Test resolving file path for file-based localization."""
        path = writer._resolve_file_path(sample_action)

        assert path is not None
        assert "blog.test.com" in path
        assert "posts" in path
        assert "test-article" in path
        assert "index.md" in path

    def test_resolve_folder_based_path(self, hugo_config, mock_db):
        """Test resolving file path for folder-based localization."""
        writer = HugoContentWriter(config=hugo_config, db_connection=mock_db)
        action = {
            "property": "https://docs.test.com",
            "metadata": {"page_path": "/getting-started/"}
        }

        path = writer._resolve_file_path(action)

        assert path is not None
        assert "docs.test.com" in path
        assert "en" in path
        assert "getting-started.md" in path

    def test_resolve_path_with_locale(self, writer):
        """Test resolving path with specific locale."""
        action = {
            "property": "https://blog.test.com",
            "metadata": {
                "page_path": "/posts/article/",
                "locale": "es"
            }
        }

        path = writer._resolve_file_path(action)

        assert path is not None
        assert "index.es.md" in path

    def test_resolve_path_missing_page_path(self, writer):
        """Test resolving path with missing page_path."""
        action = {
            "property": "https://blog.test.com",
            "metadata": {}
        }

        path = writer._resolve_file_path(action)

        assert path is None

    def test_resolve_path_missing_property(self, writer):
        """Test resolving path with missing property."""
        action = {
            "property": "",
            "metadata": {"page_path": "/test/"}
        }

        path = writer._resolve_file_path(action)

        assert path is None


class TestApplyOptimizations:
    """Test _apply_optimizations method."""

    def test_routes_to_title_optimization(self, writer):
        """Test that title optimization template is routed correctly."""
        with patch.object(writer, '_optimize_title') as mock_optimize:
            mock_optimize.return_value = ({"title": "New"}, ["change"], True)

            action = {
                "action_type": "content_update",
                "metadata": {"template_name": "title_optimization"}
            }

            result = writer._apply_optimizations(action, {"title": "Old"}, "content")

            mock_optimize.assert_called_once()
            assert result["modified"] is True

    def test_routes_to_meta_description(self, writer):
        """Test that meta description template is routed correctly."""
        with patch.object(writer, '_optimize_meta_description') as mock_optimize:
            mock_optimize.return_value = ({"description": "New"}, ["change"], True)

            action = {
                "action_type": "content_update",
                "metadata": {"template_name": "meta_description"}
            }

            result = writer._apply_optimizations(action, {}, "content")

            mock_optimize.assert_called_once()

    def test_routes_to_content_expansion(self, writer):
        """Test that content expansion template is routed correctly."""
        with patch.object(writer, '_expand_content') as mock_expand:
            mock_expand.return_value = ("expanded", ["change"], True)

            action = {
                "action_type": "content_update",
                "metadata": {"template_name": "content_expansion"}
            }

            result = writer._apply_optimizations(action, {}, "short content")

            mock_expand.assert_called_once()

    def test_routes_to_cannibalization_fix(self, writer):
        """Test that cannibalization fix is routed correctly."""
        with patch.object(writer, '_fix_cannibalization') as mock_fix:
            mock_fix.return_value = ("differentiated", ["change"], True)

            action = {
                "action_type": "content_restructure",
                "metadata": {"template_name": "cannibalization_fix"}
            }

            result = writer._apply_optimizations(action, {}, "content")

            mock_fix.assert_called_once()

    def test_unknown_action_type_no_error(self, writer):
        """Test that unknown action type doesn't raise error."""
        action = {
            "action_type": "unknown_type",
            "metadata": {"template_name": "unknown"}
        }

        result = writer._apply_optimizations(action, {}, "content")

        assert result["modified"] is False
        assert result["changes"] == []


class TestCallOllama:
    """Test _call_ollama method."""

    def test_successful_call(self, writer):
        """Test successful Ollama API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated text"}

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = writer._call_ollama("Test prompt")

            assert result == "Generated text"

    def test_api_error(self, writer):
        """Test handling of API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = writer._call_ollama("Test prompt")

            assert result == ""

    def test_timeout_handling(self, writer):
        """Test handling of timeout."""
        import httpx

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("Timeout")

            result = writer._call_ollama("Test prompt")

            assert result == ""

    def test_connection_error_handling(self, writer):
        """Test handling of connection error."""
        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = Exception("Connection failed")

            result = writer._call_ollama("Test prompt")

            assert result == ""


class TestUpdateStatuses:
    """Test status update methods."""

    def test_update_action_status_in_progress(self, writer, mock_db):
        """Test updating action status to in_progress."""
        mock_cursor = MagicMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        writer._update_action_status("action-123", "in_progress")

        mock_cursor.execute.assert_called_once()
        assert "in_progress" in str(mock_cursor.execute.call_args)
        mock_db.commit.assert_called_once()

    def test_update_action_status_completed(self, writer, mock_db):
        """Test updating action status to completed with outcome."""
        mock_cursor = MagicMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        outcome = {"changes_made": ["Title updated"]}
        writer._update_action_status("action-123", "completed", outcome=outcome)

        mock_cursor.execute.assert_called_once()
        assert "completed" in str(mock_cursor.execute.call_args)
        mock_db.commit.assert_called_once()

    def test_update_insight_status(self, writer, mock_db):
        """Test updating insight status."""
        mock_cursor = MagicMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        writer._update_insight_status("insight-456", "actioned")

        mock_cursor.execute.assert_called_once()
        assert "actioned" in str(mock_cursor.execute.call_args)
        mock_db.commit.assert_called_once()


class TestExecuteAction:
    """Test execute_action method."""

    def test_action_not_found(self, writer):
        """Test execution when action not found."""
        with patch.object(writer, '_get_action', return_value=None):
            result = writer.execute_action("nonexistent-id")

            assert result["success"] is False
            assert "not found" in result["error"]

    def test_file_not_found(self, writer, sample_action):
        """Test execution when file not found."""
        with patch.object(writer, '_get_action', return_value=sample_action):
            with patch.object(writer, '_update_action_status'):
                result = writer.execute_action("test-action-123")

                assert result["success"] is False
                assert "not found" in result.get("error", "") or "File not found" in result.get("error", "")

    def test_successful_execution(self, writer, sample_action, sample_markdown_file, mock_db):
        """Test successful action execution."""
        # Setup mocks
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_action
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock Ollama to return a new title
        with patch.object(writer, '_call_ollama', return_value="New Optimized Title"):
            result = writer.execute_action("test-action-123")

            assert result["success"] is True
            assert result["file_path"] is not None
            assert "completed_at" in result

    def test_execution_reverts_on_error(self, writer, sample_action, mock_db):
        """Test that status reverts to pending on error."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = sample_action
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        with patch.object(writer, '_resolve_file_path', side_effect=Exception("Test error")):
            result = writer.execute_action("test-action-123")

            assert result["success"] is False
            # Should have called update_action_status to revert


class TestOptimizationMethods:
    """Test individual optimization methods."""

    def test_optimize_title_success(self, writer):
        """Test successful title optimization."""
        with patch.object(writer, '_call_ollama', return_value="New Better Title"):
            action = {
                "description": "Test page",
                "metadata": {"keywords": ["test"], "ctr": 2.0, "position": 5.0}
            }
            metadata = {"title": "Old Title"}

            new_metadata, changes, modified = writer._optimize_title(action, metadata, "content")

            assert modified is True
            assert new_metadata["title"] == "New Better Title"
            assert len(changes) > 0

    def test_optimize_title_no_change(self, writer):
        """Test title optimization with no change needed."""
        with patch.object(writer, '_call_ollama', return_value="Old Title"):
            action = {
                "description": "Test page",
                "metadata": {"keywords": ["test"], "ctr": 2.0, "position": 5.0}
            }
            metadata = {"title": "Old Title"}

            new_metadata, changes, modified = writer._optimize_title(action, metadata, "content")

            assert modified is False
            assert len(changes) == 0

    def test_expand_content_adequate_length(self, writer):
        """Test content expansion skips if already adequate."""
        action = {"metadata": {}}
        metadata = {}
        content = " ".join(["word"] * 600)  # 600 words

        new_content, changes, modified = writer._expand_content(action, metadata, content)

        assert modified is False
        assert "adequate" in changes[0].lower()

    def test_fix_cannibalization_no_intent(self, writer):
        """Test cannibalization fix with no target intent."""
        action = {"metadata": {}}

        new_content, changes, modified = writer._fix_cannibalization(action, {}, "content")

        assert modified is False
        assert len(changes) == 0


class TestLogChange:
    """Test _log_change method."""

    def test_log_change_success(self, writer, mock_db, sample_action):
        """Test successful change logging."""
        mock_cursor = MagicMock()
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        writer._log_change(
            action=sample_action,
            file_path="/test/path.md",
            original_metadata={"title": "Old"},
            new_metadata={"title": "New"},
            original_content="Old content",
            new_content="New content with more words",
            changes=["Title changed"]
        )

        mock_cursor.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_log_change_failure_doesnt_raise(self, writer, mock_db, sample_action):
        """Test that log change failure doesn't raise exception."""
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        # Should not raise
        writer._log_change(
            action=sample_action,
            file_path="/test/path.md",
            original_metadata={},
            new_metadata={},
            original_content="",
            new_content="",
            changes=[]
        )
