"""
Tests for LLM Prompt Templates
==============================
Tests for content optimization prompt templates.
"""
import pytest

from insights_core.prompts.content_prompts import (
    PROMPTS,
    get_prompt,
    list_prompts,
    get_prompt_requirements
)


class TestPromptsDict:
    """Test the PROMPTS dictionary structure."""

    def test_all_required_prompts_exist(self):
        """Test that all 6 required prompt types are defined."""
        required_prompts = [
            "title_optimization",
            "meta_description",
            "content_expansion",
            "readability_improvement",
            "keyword_optimization",
            "intent_differentiation"
        ]
        for prompt_type in required_prompts:
            assert prompt_type in PROMPTS, f"Missing prompt type: {prompt_type}"

    def test_prompts_are_non_empty_strings(self):
        """Test that all prompts are non-empty strings."""
        for name, template in PROMPTS.items():
            assert isinstance(template, str), f"Prompt '{name}' is not a string"
            assert len(template) > 100, f"Prompt '{name}' is too short"

    def test_prompts_have_output_format(self):
        """Test that all prompts include output format instructions."""
        for name, template in PROMPTS.items():
            assert "RESPOND WITH VALID JSON" in template, f"Prompt '{name}' missing JSON output format"

    def test_prompts_have_requirements(self):
        """Test that all prompts include requirements section."""
        for name, template in PROMPTS.items():
            assert "REQUIREMENTS" in template, f"Prompt '{name}' missing REQUIREMENTS section"


class TestGetPrompt:
    """Test the get_prompt function."""

    def test_title_optimization_prompt(self):
        """Test title optimization prompt formatting."""
        prompt = get_prompt(
            "title_optimization",
            current_title="My Old Title",
            topic="Python Programming",
            keywords=["python", "programming", "tutorial"],
            ctr=2.5,
            position=8.3
        )

        assert "My Old Title" in prompt
        assert "Python Programming" in prompt
        assert "python, programming, tutorial" in prompt
        assert "2.5" in prompt
        assert "8.3" in prompt
        assert "50-60 characters" in prompt

    def test_meta_description_prompt(self):
        """Test meta description prompt formatting."""
        prompt = get_prompt(
            "meta_description",
            title="Page Title",
            content_preview="This is a preview of the content...",
            keywords=["seo", "optimization"]
        )

        assert "Page Title" in prompt
        assert "This is a preview" in prompt
        assert "seo, optimization" in prompt
        assert "100-160" in prompt  # Updated to match schema constraints

    def test_content_expansion_prompt(self):
        """Test content expansion prompt formatting."""
        prompt = get_prompt(
            "content_expansion",
            title="Guide to Python",
            content="Introduction to Python programming...",
            word_count=200,
            keywords=["python", "guide"],
            competitor_avg=1500,
            target_words=500
        )

        assert "Guide to Python" in prompt
        assert "Introduction to Python" in prompt
        assert "200" in prompt
        assert "1500" in prompt
        assert "500" in prompt

    def test_readability_improvement_prompt(self):
        """Test readability improvement prompt formatting."""
        prompt = get_prompt(
            "readability_improvement",
            flesch_score=45.2,
            audience="software developers",
            content="Complex technical content here..."
        )

        assert "45.2" in prompt
        assert "software developers" in prompt
        assert "Complex technical content" in prompt
        assert "60+" in prompt  # Target score

    def test_keyword_optimization_prompt(self):
        """Test keyword optimization prompt formatting."""
        prompt = get_prompt(
            "keyword_optimization",
            keywords=["seo", "content", "optimization"],
            density=0.5,
            content="Content to optimize for keywords..."
        )

        assert "seo, content, optimization" in prompt
        assert "0.5" in prompt
        assert "Content to optimize" in prompt
        assert "1-2%" in prompt  # Target density

    def test_intent_differentiation_prompt(self):
        """Test intent differentiation prompt formatting."""
        prompt = get_prompt(
            "intent_differentiation",
            intent="informational",
            content="Content that needs differentiation...",
            competing_intents=["transactional", "navigational"]
        )

        assert "informational" in prompt
        assert "Content that needs differentiation" in prompt
        assert "transactional, navigational" in prompt

    def test_unknown_prompt_type_raises_value_error(self):
        """Test that unknown prompt type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_prompt("unknown_prompt_type")

        assert "Unknown prompt type" in str(exc_info.value)
        assert "unknown_prompt_type" in str(exc_info.value)
        assert "Available types" in str(exc_info.value)

    def test_missing_variable_raises_key_error(self):
        """Test that missing required variable raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_prompt(
                "title_optimization",
                current_title="Title",
                # Missing: topic, keywords, ctr, position
            )

        assert "Missing required template variable" in str(exc_info.value)

    def test_list_keywords_converted_to_string(self):
        """Test that list keywords are converted to comma-separated string."""
        prompt = get_prompt(
            "meta_description",
            title="Test",
            content_preview="Preview",
            keywords=["one", "two", "three"]
        )
        assert "one, two, three" in prompt

    def test_tuple_keywords_converted_to_string(self):
        """Test that tuple keywords are converted to comma-separated string."""
        prompt = get_prompt(
            "meta_description",
            title="Test",
            content_preview="Preview",
            keywords=("one", "two", "three")
        )
        assert "one, two, three" in prompt

    def test_single_keyword_works(self):
        """Test that single keyword as string works."""
        prompt = get_prompt(
            "meta_description",
            title="Test",
            content_preview="Preview",
            keywords="single-keyword"
        )
        assert "single-keyword" in prompt


class TestListPrompts:
    """Test the list_prompts function."""

    def test_returns_list(self):
        """Test that list_prompts returns a list."""
        result = list_prompts()
        assert isinstance(result, list)

    def test_returns_all_prompts(self):
        """Test that all prompts are listed."""
        result = list_prompts()
        assert len(result) == len(PROMPTS)

    def test_list_is_sorted(self):
        """Test that the list is alphabetically sorted."""
        result = list_prompts()
        assert result == sorted(result)


class TestGetPromptRequirements:
    """Test the get_prompt_requirements function."""

    def test_returns_dict(self):
        """Test that requirements are returned as a dict."""
        result = get_prompt_requirements("title_optimization")
        assert isinstance(result, dict)

    def test_includes_type(self):
        """Test that result includes prompt type."""
        result = get_prompt_requirements("title_optimization")
        assert result["type"] == "title_optimization"

    def test_includes_required_variables(self):
        """Test that result includes required variables."""
        result = get_prompt_requirements("title_optimization")
        assert "required_variables" in result
        assert isinstance(result["required_variables"], list)
        assert "current_title" in result["required_variables"]
        assert "topic" in result["required_variables"]

    def test_includes_template_length(self):
        """Test that result includes template length."""
        result = get_prompt_requirements("title_optimization")
        assert "template_length" in result
        assert result["template_length"] > 0

    def test_unknown_type_raises_value_error(self):
        """Test that unknown type raises ValueError."""
        with pytest.raises(ValueError):
            get_prompt_requirements("unknown_type")


class TestPromptQuality:
    """Test prompt quality and content guidelines."""

    def test_title_prompt_has_length_constraint(self):
        """Test title prompt specifies character length."""
        assert "50-60" in PROMPTS["title_optimization"]

    def test_meta_description_has_length_constraint(self):
        """Test meta description prompt specifies character length."""
        assert "100-160" in PROMPTS["meta_description"]  # Updated to match schema

    def test_keyword_prompt_warns_against_stuffing(self):
        """Test keyword prompt warns against keyword stuffing."""
        prompt = PROMPTS["keyword_optimization"]
        assert "stuff" in prompt.lower() or "natural" in prompt.lower()

    def test_prompts_specify_output_format(self):
        """Test all prompts specify clear output format."""
        for name, template in PROMPTS.items():
            assert "Return" in template or "OUTPUT" in template, \
                f"Prompt '{name}' should specify output format"

    def test_content_expansion_requests_markdown(self):
        """Test content expansion prompt requests markdown format."""
        prompt = PROMPTS["content_expansion"]
        assert "markdown" in prompt.lower() or "##" in prompt


class TestPromptDeterminism:
    """Test that prompts are deterministic."""

    def test_same_inputs_produce_same_output(self):
        """Test that same inputs always produce same formatted prompt."""
        kwargs = {
            "current_title": "Test Title",
            "topic": "Testing",
            "keywords": ["test", "unit"],
            "ctr": 5.0,
            "position": 3.0
        }

        prompt1 = get_prompt("title_optimization", **kwargs)
        prompt2 = get_prompt("title_optimization", **kwargs)

        assert prompt1 == prompt2

    def test_different_inputs_produce_different_outputs(self):
        """Test that different inputs produce different prompts."""
        prompt1 = get_prompt(
            "meta_description",
            title="Title A",
            content_preview="Preview A",
            keywords=["a"]
        )

        prompt2 = get_prompt(
            "meta_description",
            title="Title B",
            content_preview="Preview B",
            keywords=["b"]
        )

        assert prompt1 != prompt2
