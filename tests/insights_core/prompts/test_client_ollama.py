"""
Live Ollama Integration Tests
=============================
Integration tests that run against actual Ollama instance.
Skip if Ollama is not available.

Run with: TEST_MODE=ollama pytest tests/insights_core/prompts/test_client_ollama.py -v
"""

import os
import pytest

from insights_core.prompts.client import ContentOptimizationClient
from insights_core.prompts.schemas import (
    TitleOptimizationResponse,
    MetaDescriptionResponse,
    ContentExpansionResponse,
    ReadabilityResponse,
    KeywordOptimizationResponse,
    IntentDifferentiationResponse,
)
from insights_core.prompts.content_prompts import get_prompt


# Skip entire module if not in ollama test mode
pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_MODE") != "ollama",
    reason="Live Ollama tests require TEST_MODE=ollama"
)


@pytest.fixture(scope="module")
def ollama_client():
    """Create real Ollama client, skip if unavailable."""
    client = ContentOptimizationClient(
        provider="ollama",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),  # Use smaller model for tests
        max_retries=2,
        enable_cache=False  # Disable cache for testing
    )

    if not client.is_available():
        pytest.skip("Ollama not available")

    return client


class TestTitleOptimizationLive:
    """Live tests for title optimization."""

    def test_optimize_title_real(self, ollama_client):
        """Test real title optimization with Ollama."""
        prompt = get_prompt(
            "title_optimization",
            current_title="Python Tutorial",
            topic="Python programming for beginners",
            keywords=["python", "tutorial", "beginner"],
            ctr=2.5,
            position=8.3
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=TitleOptimizationResponse,
            operation_type="title_optimization",
            temperature=0.7
        )

        # Validate response structure
        assert isinstance(response, TitleOptimizationResponse)
        assert 10 <= len(response.optimized_title) <= 60
        assert response.keyword_position in ["beginning", "middle", "end"]

        # Validate content quality - should be different from original
        assert response.optimized_title.lower() != "python tutorial"

    def test_optimize_title_with_long_input(self, ollama_client):
        """Test title optimization handles long existing titles."""
        prompt = get_prompt(
            "title_optimization",
            current_title="A Very Long Existing Title That Needs to Be Shortened and Optimized for SEO and Search Engines",
            topic="SEO optimization best practices",
            keywords=["SEO", "optimization", "best practices"],
            ctr=1.0,
            position=15.0
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=TitleOptimizationResponse,
            operation_type="title_optimization"
        )

        # Must respect max length constraint
        assert len(response.optimized_title) <= 60


class TestMetaDescriptionLive:
    """Live tests for meta description generation."""

    def test_generate_meta_description(self, ollama_client):
        """Test real meta description generation."""
        prompt = get_prompt(
            "meta_description",
            title="Complete Python Tutorial for Beginners",
            content_preview="Learn Python programming from scratch. This comprehensive guide covers variables, functions, loops, and more. Perfect for absolute beginners with no prior coding experience.",
            keywords=["python", "tutorial", "beginners", "programming"]
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=MetaDescriptionResponse,
            operation_type="meta_description"
        )

        assert isinstance(response, MetaDescriptionResponse)
        assert 100 <= len(response.description) <= 160
        assert isinstance(response.includes_cta, bool)
        assert isinstance(response.includes_keyword, bool)


class TestContentExpansionLive:
    """Live tests for content expansion."""

    @pytest.mark.slow
    def test_expand_thin_content(self, ollama_client):
        """Test content expansion with real LLM."""
        prompt = get_prompt(
            "content_expansion",
            title="Python Variables",
            word_count=50,
            content="Python variables store data. You create them with assignment. Variables can hold different types of data including numbers and text.",
            keywords=["python", "variables", "data types"],
            competitor_avg=500,
            target_words=200
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=ContentExpansionResponse,
            operation_type="content_expansion",
            temperature=0.8  # More creative for content
        )

        assert isinstance(response, ContentExpansionResponse)
        assert len(response.expanded_content) > 100
        assert len(response.sections_added) >= 1
        assert response.word_count_added >= 50


class TestReadabilityLive:
    """Live tests for readability improvement."""

    def test_improve_readability(self, ollama_client):
        """Test readability improvement with real LLM."""
        complex_content = """
        The implementation of asynchronous programming paradigms in Python necessitates
        a comprehensive understanding of coroutines, event loops, and the async/await
        syntax that was introduced in Python 3.5, which fundamentally transformed the
        way concurrent operations are handled in the language.
        """

        prompt = get_prompt(
            "readability_improvement",
            flesch_score=35,
            audience="general developers",
            content=complex_content
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=ReadabilityResponse,
            operation_type="readability_improvement"
        )

        assert isinstance(response, ReadabilityResponse)
        assert len(response.improved_content) > 50
        assert len(response.changes_summary) >= 1
        assert 0 <= response.estimated_flesch_improvement <= 50


class TestKeywordOptimizationLive:
    """Live tests for keyword optimization."""

    def test_optimize_keywords(self, ollama_client):
        """Test keyword optimization with real LLM."""
        content = """
        Learning to code can open many doors. This guide will help you get started
        with your programming journey. We'll cover the basics and help you build
        your first projects.
        """

        prompt = get_prompt(
            "keyword_optimization",
            keywords=["python programming", "learn coding", "beginner tutorial"],
            density=0.5,
            content=content
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=KeywordOptimizationResponse,
            operation_type="keyword_optimization"
        )

        assert isinstance(response, KeywordOptimizationResponse)
        assert len(response.optimized_content) > 50
        assert 0 <= response.keywords_added <= 20


class TestIntentDifferentiationLive:
    """Live tests for intent differentiation."""

    def test_differentiate_intent(self, ollama_client):
        """Test intent differentiation with real LLM."""
        content = """
        Python is a great programming language. You can buy Python courses online.
        Here's how to install Python. Python pricing varies by course provider.
        Learn Python basics in this tutorial.
        """

        prompt = get_prompt(
            "intent_differentiation",
            intent="informational",
            content=content,
            competing_intents=["transactional (buying courses)", "navigational (installation)"]
        )

        response = ollama_client.generate(
            prompt=prompt,
            response_model=IntentDifferentiationResponse,
            operation_type="intent_differentiation"
        )

        assert isinstance(response, IntentDifferentiationResponse)
        assert response.target_intent == "informational"
        assert len(response.unique_value_added) >= 1


class TestRetryBehavior:
    """Test retry behavior with edge cases."""

    def test_handles_minimal_input(self, ollama_client):
        """Test client handles minimal inputs gracefully."""
        prompt = get_prompt(
            "title_optimization",
            current_title="Test",
            topic="testing",
            keywords=["test"],
            ctr=0,
            position=0
        )

        # Should still return valid response
        response = ollama_client.generate(
            prompt=prompt,
            response_model=TitleOptimizationResponse
        )
        assert isinstance(response, TitleOptimizationResponse)
        assert len(response.optimized_title) >= 10


class TestModelSelection:
    """Test model selection functionality."""

    def test_list_models(self, ollama_client):
        """Test listing available models."""
        models = ollama_client.list_models()
        assert isinstance(models, list)
        # Should have at least one model available
        assert len(models) > 0

    def test_client_repr(self, ollama_client):
        """Test client string representation."""
        repr_str = repr(ollama_client)
        assert "ContentOptimizationClient" in repr_str
        assert "ollama" in repr_str
