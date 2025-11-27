"""
Tests for Execute Action CLI Tool
=================================
Tests for the command-line action execution tool.
"""
import os
import sys
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.execute_action import (
    validate_action_id,
    list_pending_actions,
    execute_single_action,
    check_system_ready,
    print_pending_actions
)


class TestValidateActionId:
    """Test validate_action_id function."""

    def test_valid_uuid(self):
        """Test validation of valid UUID."""
        valid_uuid = str(uuid4())
        assert validate_action_id(valid_uuid) is True

    def test_invalid_uuid(self):
        """Test validation of invalid UUID."""
        assert validate_action_id("not-a-uuid") is False
        assert validate_action_id("") is False
        assert validate_action_id("123456") is False

    def test_uuid_with_braces(self):
        """Test validation of UUID with braces."""
        uuid_str = str(uuid4())
        # Without braces should work
        assert validate_action_id(uuid_str) is True


class TestListPendingActions:
    """Test list_pending_actions function."""

    @pytest.fixture
    def mock_env(self):
        """Set up test environment."""
        with patch.dict(os.environ, {"WAREHOUSE_DSN": "postgresql://test:test@localhost/test"}):
            yield

    def test_list_with_no_filters(self, mock_env):
        """Test listing without filters."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": str(uuid4()),
                "property": "https://test.com",
                "action_type": "content_update",
                "title": "Test Action",
                "priority": "high",
                "effort": "low",
                "estimated_impact": "medium",
                "status": "pending",
                "created_at": datetime.utcnow(),
                "entity_id": "/test/"
            }
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            results = list_pending_actions()

            assert len(results) == 1
            assert results[0]["status"] == "pending"

    def test_list_with_property_filter(self, mock_env):
        """Test listing with property filter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            results = list_pending_actions(property_filter="https://blog.test.com")

            assert len(results) == 0
            # Verify property filter was passed to query
            call_args = mock_cursor.execute.call_args
            assert "https://blog.test.com" in call_args[0][1]

    def test_list_with_priority_filter(self, mock_env):
        """Test listing with priority filter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            results = list_pending_actions(priority_filter="high")

            call_args = mock_cursor.execute.call_args
            assert "high" in call_args[0][1]


class TestExecuteSingleAction:
    """Test execute_single_action function."""

    @pytest.fixture
    def mock_env(self):
        """Set up test environment."""
        with patch.dict(os.environ, {
            "WAREHOUSE_DSN": "postgresql://test:test@localhost/test",
            "HUGO_CONTENT_PATH": "/test/content",
            "OLLAMA_BASE_URL": "http://localhost:11434"
        }):
            yield

    def test_invalid_action_id(self, mock_env):
        """Test execution with invalid action ID."""
        result = execute_single_action("invalid-uuid")

        assert result["success"] is False
        assert "Invalid action ID" in result["error"]

    def test_hugo_not_configured(self, mock_env):
        """Test when Hugo not configured."""
        with patch.dict(os.environ, {"HUGO_CONTENT_PATH": ""}, clear=False):
            valid_id = str(uuid4())
            mock_conn = MagicMock()

            with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
                with patch("scripts.execute_action.HugoConfig") as mock_config:
                    mock_config.from_env.return_value.is_configured.return_value = False

                    result = execute_single_action(valid_id)

                    assert result["success"] is False
                    assert "not configured" in result["error"]

    def test_dry_run_action_not_found(self, mock_env):
        """Test dry run when action doesn't exist."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            with patch("scripts.execute_action.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                mock_config.from_env.return_value = config_instance

                result = execute_single_action(str(uuid4()), dry_run=True)

                assert result["success"] is False
                assert "not found" in result["error"]

    def test_dry_run_success(self, mock_env):
        """Test successful dry run."""
        action_id = str(uuid4())
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "id": action_id,
            "status": "pending",
            "property": "https://blog.test.com",
            "metadata": {"page_path": "/test-article/"},
            "entity_id": "/test-article/"
        }
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            with patch("scripts.execute_action.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                config_instance.extract_subdomain.return_value = "blog.test.com"
                config_instance.get_content_file_path.return_value = "/test/content/blog.test.com/test-article/index.md"
                mock_config.from_env.return_value = config_instance

                with patch("os.path.exists", return_value=True):
                    result = execute_single_action(action_id, dry_run=True)

                    assert result["success"] is True
                    assert result["dry_run"] is True
                    assert result["file_exists"] is True

    def test_execution_success(self, mock_env):
        """Test successful execution."""
        action_id = str(uuid4())
        mock_conn = MagicMock()

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            with patch("scripts.execute_action.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                mock_config.from_env.return_value = config_instance

                with patch("scripts.execute_action.HugoContentWriter") as mock_writer:
                    mock_writer.return_value.execute_action.return_value = {
                        "success": True,
                        "action_id": action_id,
                        "changes_made": ["Title updated"]
                    }

                    result = execute_single_action(action_id)

                    assert result["success"] is True
                    assert result["changes_made"] == ["Title updated"]


class TestCheckSystemReady:
    """Test check_system_ready function."""

    @pytest.fixture
    def mock_env(self):
        """Set up test environment."""
        with patch.dict(os.environ, {
            "WAREHOUSE_DSN": "postgresql://test:test@localhost/test",
            "HUGO_CONTENT_PATH": "/test/content"
        }):
            yield

    def test_all_systems_up(self, mock_env, capsys):
        """Test when all systems are ready."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("scripts.execute_action.get_db_connection", return_value=mock_conn):
            with patch("scripts.execute_action.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                config_instance.content_path = "/test/content"
                config_instance.file_localization_subdomains = ["blog.test.com"]
                config_instance.default_locale = "en"
                mock_config.from_env.return_value = config_instance

                with patch("httpx.Client") as mock_httpx:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"models": [{"name": "llama3.1"}]}
                    mock_httpx.return_value.__enter__.return_value.get.return_value = mock_response

                    result = check_system_ready()

                    assert result is True
                    captured = capsys.readouterr()
                    assert "[OK]" in captured.out

    def test_database_down(self, mock_env, capsys):
        """Test when database is down."""
        with patch("scripts.execute_action.get_db_connection") as mock_db:
            mock_db.side_effect = Exception("Connection refused")

            with patch("scripts.execute_action.HugoConfig") as mock_config:
                config_instance = MagicMock()
                config_instance.is_configured.return_value = True
                config_instance.validate_path.return_value = None
                mock_config.from_env.return_value = config_instance

                result = check_system_ready()

                assert result is False
                captured = capsys.readouterr()
                assert "[FAIL]" in captured.out


class TestPrintPendingActions:
    """Test print_pending_actions function."""

    def test_print_empty_list(self, capsys):
        """Test printing empty action list."""
        print_pending_actions([])

        captured = capsys.readouterr()
        assert "No pending actions" in captured.out

    def test_print_actions(self, capsys):
        """Test printing action list."""
        actions = [
            {
                "id": str(uuid4()),
                "property": "https://test.com",
                "action_type": "content_update",
                "title": "Test Action",
                "priority": "high",
                "effort": "low",
                "estimated_impact": "medium",
                "entity_id": "/test/",
                "created_at": datetime.utcnow()
            }
        ]

        print_pending_actions(actions)

        captured = capsys.readouterr()
        assert "Test Action" in captured.out
        assert "HIGH" in captured.out
        assert "https://test.com" in captured.out
        assert "Total: 1" in captured.out


class TestMainCLI:
    """Test main CLI function."""

    @pytest.fixture
    def mock_env(self):
        """Set up test environment."""
        with patch.dict(os.environ, {
            "WAREHOUSE_DSN": "postgresql://test:test@localhost/test",
            "HUGO_CONTENT_PATH": "/test/content"
        }):
            yield

    def test_main_no_args(self, mock_env):
        """Test main with no arguments."""
        from scripts.execute_action import main

        with patch("sys.argv", ["execute_action.py"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_help(self, mock_env):
        """Test main with --help."""
        from scripts.execute_action import main

        with patch("sys.argv", ["execute_action.py", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_check(self, mock_env):
        """Test main with --check."""
        from scripts.execute_action import main

        with patch("sys.argv", ["execute_action.py", "--check"]):
            with patch("scripts.execute_action.check_system_ready", return_value=True):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_main_list(self, mock_env):
        """Test main with --list."""
        from scripts.execute_action import main

        with patch("sys.argv", ["execute_action.py", "--list"]):
            with patch("scripts.execute_action.list_pending_actions", return_value=[]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_main_execute_action(self, mock_env):
        """Test main with action ID."""
        from scripts.execute_action import main

        action_id = str(uuid4())

        with patch("sys.argv", ["execute_action.py", action_id]):
            with patch("scripts.execute_action.execute_single_action") as mock_execute:
                mock_execute.return_value = {"success": True, "changes_made": []}

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_main_execute_failed(self, mock_env):
        """Test main when execution fails."""
        from scripts.execute_action import main

        action_id = str(uuid4())

        with patch("sys.argv", ["execute_action.py", action_id]):
            with patch("scripts.execute_action.execute_single_action") as mock_execute:
                mock_execute.return_value = {"success": False, "error": "Test error"}

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

    def test_main_dry_run(self, mock_env):
        """Test main with --dry-run."""
        from scripts.execute_action import main

        action_id = str(uuid4())

        with patch("sys.argv", ["execute_action.py", action_id, "--dry-run"]):
            with patch("scripts.execute_action.execute_single_action") as mock_execute:
                mock_execute.return_value = {"success": True, "dry_run": True}

                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                mock_execute.assert_called_with(action_id, dry_run=True)
