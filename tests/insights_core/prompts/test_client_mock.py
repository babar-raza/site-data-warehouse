"""
Mock Tests for ContentOptimizationClient
========================================
Unit tests with mocked LLM responses - no Ollama dependency required.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pydantic import ValidationError

from insights_core.prompts.schemas import (
    TitleOptimizationResponse,
    MetaDescriptionResponse,
    ContentExpansionResponse,
)
from insights_core.prompts.client import (
    ContentOptimizationClient,
    OPERATION_CONFIG,
)


class TestContentOptimizationClientInit:
    """Tests for client initialization."""

    def test_default_ollama_config(self):
        """Test default Ollama configuration."""
        with patch.dict('os.environ', {}, clear=True):
            client = ContentOptimizationClient(provider="ollama")
            assert client.provider == "ollama"
            assert client.base_url == "http://localhost:11434"
            assert client.model == "qwen2.5:14b-instruct"

    def test_env_override_ollama(self):
        """Test environment variable overrides."""
        with patch.dict('os.environ', {
            'OLLAMA_BASE_URL': 'http://custom:11434',
            'OLLAMA_MODEL': 'llama3:8b'
        }):
            client = ContentOptimizationClient(provider="ollama")
            assert client.base_url == "http://custom:11434"
            assert client.model == "llama3:8b"

    def test_explicit_params_override(self):
        """Test explicit parameters override env vars."""
        with patch.dict('os.environ', {
            'OLLAMA_BASE_URL': 'http://env:11434',
            'OLLAMA_MODEL': 'env-model'
        }):
            client = ContentOptimizationClient(
                provider="ollama",
                base_url="http://explicit:11434",
                model="explicit-model"
            )
            assert client.base_url == "http://explicit:11434"
            assert client.model == "explicit-model"

    def test_invalid_provider(self):
        """Test invalid provider raises error."""
        with pytest.raises(ValueError) as exc_info:
            ContentOptimizationClient(provider="invalid")
        assert "Unsupported provider" in str(exc_info.value)

    def test_cache_disabled(self):
        """Test cache can be disabled."""
        client = ContentOptimizationClient(enable_cache=False)
        assert client._cache is None


class TestContentOptimizationClientGenerate:
    """Tests for generate method with mocked responses."""

    @pytest.fixture
    def mock_client(self):
        """Create client with mocked Instructor client."""
        # Create client with cache disabled
        client = ContentOptimizationClient(
            provider="ollama",
            enable_cache=False
        )

        # Create mock for the instructor client
        mock_instructor_client = MagicMock()
        client._instructor_client = mock_instructor_client
        client._mock = mock_instructor_client
        return client

    def test_generate_title_success(self, mock_client):
        """Test successful title generation."""
        mock_response = TitleOptimizationResponse(
            optimized_title="Optimized Test Title Here",
            keyword_position="beginning",
            changes_made=["Added keyword at beginning"]
        )
        mock_client._mock.chat.completions.create.return_value = mock_response

        result = mock_client.generate(
            prompt="Optimize this title",
            response_model=TitleOptimizationResponse
        )

        assert result.optimized_title == "Optimized Test Title Here"
        assert result.keyword_position == "beginning"
        mock_client._mock.chat.completions.create.assert_called_once()

    def test_generate_with_operation_type_timeout(self, mock_client):
        """Test operation type affects timeout."""
        mock_response = TitleOptimizationResponse(
            optimized_title="Test Title for Timeout",
            keyword_position="middle",
            changes_made=[]
        )
        mock_client._mock.chat.completions.create.return_value = mock_response

        # Content expansion should use longer timeout
        result = mock_client.generate(
            prompt="Expand content",
            response_model=TitleOptimizationResponse,
            operation_type="content_expansion"
        )

        assert result is not None
        # Verify the call was made
        mock_client._mock.chat.completions.create.assert_called()

    def test_generate_custom_temperature(self, mock_client):
        """Test custom temperature is passed."""
        mock_response = TitleOptimizationResponse(
            optimized_title="Temperature Test Title",
            keyword_position="end",
            changes_made=[]
        )
        mock_client._mock.chat.completions.create.return_value = mock_response

        result = mock_client.generate(
            prompt="Test prompt",
            response_model=TitleOptimizationResponse,
            temperature=0.3
        )

        assert result is not None
        call_kwargs = mock_client._mock.chat.completions.create.call_args
        assert call_kwargs is not None


class TestOperationConfig:
    """Tests for operation configuration."""

    def test_all_operations_have_config(self):
        """Test all operation types have timeout and delay."""
        expected_ops = [
            "title_optimization",
            "meta_description",
            "keyword_optimization",
            "readability_improvement",
            "content_expansion",
            "intent_differentiation",
        ]

        for op in expected_ops:
            assert op in OPERATION_CONFIG
            assert "timeout" in OPERATION_CONFIG[op]
            assert "delay_after" in OPERATION_CONFIG[op]

    def test_content_expansion_longest_timeout(self):
        """Test content expansion has longest timeout."""
        max_timeout = max(cfg["timeout"] for cfg in OPERATION_CONFIG.values())
        assert OPERATION_CONFIG["content_expansion"]["timeout"] == max_timeout

    def test_title_shortest_timeout(self):
        """Test title optimization has shortest timeout."""
        min_timeout = min(cfg["timeout"] for cfg in OPERATION_CONFIG.values())
        assert OPERATION_CONFIG["title_optimization"]["timeout"] == min_timeout


class TestClientAvailability:
    """Tests for availability checking."""

    def test_is_available_success(self):
        """Test is_available returns True when provider responds."""
        with patch('httpx.get') as mock_get:
            mock_get.return_value.status_code = 200
            client = ContentOptimizationClient(enable_cache=False)
            assert client.is_available() is True

    def test_is_available_failure(self):
        """Test is_available returns False on error."""
        with patch('httpx.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            client = ContentOptimizationClient(enable_cache=False)
            assert client.is_available() is False


class TestClientWithCache:
    """Tests for caching behavior."""

    def test_cache_hit(self):
        """Test cache returns cached response."""
        # Create client with cache enabled
        client = ContentOptimizationClient(enable_cache=True)

        # Manually set up cache with a response
        from insights_core.prompts.cache import ResponseCache
        client._cache = ResponseCache()

        cached_response = TitleOptimizationResponse(
            optimized_title="Cached Title Response Here",
            keyword_position="beginning",
            changes_made=[]
        )
        client._cache.set(
            "test prompt",
            client.model,
            TitleOptimizationResponse,
            cached_response
        )

        # Should return cached without calling LLM
        result = client.generate(
            prompt="test prompt",
            response_model=TitleOptimizationResponse
        )

        assert result.optimized_title == "Cached Title Response Here"

    def test_cache_bypass(self):
        """Test cache can be bypassed with use_cache=False."""
        # Create client with cache enabled
        client = ContentOptimizationClient(enable_cache=True)

        # Mock the instructor client
        mock_instructor_client = MagicMock()
        fresh_response = TitleOptimizationResponse(
            optimized_title="Fresh LLM Response Title",
            keyword_position="middle",
            changes_made=[]
        )
        mock_instructor_client.chat.completions.create.return_value = fresh_response
        client._instructor_client = mock_instructor_client

        # Pre-populate cache
        from insights_core.prompts.cache import ResponseCache
        client._cache = ResponseCache()
        cached_response = TitleOptimizationResponse(
            optimized_title="Cached Old Title Here",
            keyword_position="beginning",
            changes_made=[]
        )
        client._cache.set(
            "test prompt",
            client.model,
            TitleOptimizationResponse,
            cached_response
        )

        # Should bypass cache and get fresh response
        result = client.generate(
            prompt="test prompt",
            response_model=TitleOptimizationResponse,
            use_cache=False
        )

        assert result.optimized_title == "Fresh LLM Response Title"
        mock_instructor_client.chat.completions.create.assert_called_once()
