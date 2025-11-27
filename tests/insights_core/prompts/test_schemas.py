"""
Tests for Pydantic Response Schemas
===================================
Unit tests for schema validation without LLM dependency.
"""

import pytest
from pydantic import ValidationError

from insights_core.prompts.schemas import (
    TitleOptimizationResponse,
    MetaDescriptionResponse,
    ContentExpansionResponse,
    ReadabilityResponse,
    KeywordOptimizationResponse,
    IntentDifferentiationResponse,
    RESPONSE_SCHEMAS,
    get_response_schema,
)


class TestTitleOptimizationResponse:
    """Tests for TitleOptimizationResponse schema."""

    def test_valid_response(self):
        """Test valid title response."""
        data = {
            "optimized_title": "Best Python Tutorial for Beginners 2024",
            "keyword_position": "beginning",
            "changes_made": ["Added year", "Added 'Best' power word"]
        }
        response = TitleOptimizationResponse(**data)
        assert len(response.optimized_title) <= 60
        assert response.keyword_position == "beginning"
        assert len(response.changes_made) == 2

    def test_title_minimum_length(self):
        """Test title must meet minimum length."""
        with pytest.raises(ValidationError) as exc_info:
            TitleOptimizationResponse(
                optimized_title="Short",  # Less than 10 chars
                keyword_position="beginning",
                changes_made=[]
            )
        assert "optimized_title" in str(exc_info.value)

    def test_title_maximum_length(self):
        """Test title exceeding max length is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleOptimizationResponse(
                optimized_title="A" * 70,  # Exceeds 60 chars
                keyword_position="beginning",
                changes_made=[]
            )
        assert "optimized_title" in str(exc_info.value)

    def test_quotes_stripped(self):
        """Test surrounding quotes are stripped."""
        response = TitleOptimizationResponse(
            optimized_title='"Quoted Title Here for Test"',
            keyword_position="middle",
            changes_made=[]
        )
        assert response.optimized_title == "Quoted Title Here for Test"
        assert not response.optimized_title.startswith('"')

    def test_single_quotes_stripped(self):
        """Test single quotes are stripped."""
        response = TitleOptimizationResponse(
            optimized_title="'Single Quoted Title Test'",
            keyword_position="middle",
            changes_made=[]
        )
        assert response.optimized_title == "Single Quoted Title Test"

    def test_pipe_characters_removed(self):
        """Test pipe characters are replaced with dashes."""
        response = TitleOptimizationResponse(
            optimized_title="Python Tutorial | Best Guide 2024",
            keyword_position="beginning",
            changes_made=[]
        )
        assert "|" not in response.optimized_title
        assert "-" in response.optimized_title

    def test_invalid_keyword_position(self):
        """Test invalid keyword position is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TitleOptimizationResponse(
                optimized_title="Valid Title for Testing",
                keyword_position="invalid",  # Not in Literal
                changes_made=[]
            )
        assert "keyword_position" in str(exc_info.value)

    def test_empty_changes_allowed(self):
        """Test empty changes list is allowed."""
        response = TitleOptimizationResponse(
            optimized_title="Title Without Changes Made",
            keyword_position="end",
            changes_made=[]
        )
        assert response.changes_made == []


class TestMetaDescriptionResponse:
    """Tests for MetaDescriptionResponse schema."""

    def test_valid_description(self):
        """Test valid meta description."""
        desc = "Learn Python programming from scratch with our comprehensive tutorial. Master fundamentals and build real projects. Get started today!"
        response = MetaDescriptionResponse(
            description=desc,
            includes_cta=True,
            includes_keyword=True
        )
        assert 100 <= len(response.description) <= 160

    def test_description_too_short(self):
        """Test description below minimum length."""
        with pytest.raises(ValidationError):
            MetaDescriptionResponse(
                description="Too short",  # Less than 100 chars
                includes_cta=True,
                includes_keyword=True
            )

    def test_description_too_long(self):
        """Test description exceeding maximum length."""
        with pytest.raises(ValidationError):
            MetaDescriptionResponse(
                description="A" * 200,  # Exceeds 160 chars
                includes_cta=True,
                includes_keyword=True
            )

    def test_quotes_stripped(self):
        """Test quotes are stripped from description."""
        desc = '"Learn Python programming with our guide. Build real projects and master fundamentals. Start your coding journey today!"'
        response = MetaDescriptionResponse(
            description=desc,
            includes_cta=True,
            includes_keyword=True
        )
        assert not response.description.startswith('"')


class TestContentExpansionResponse:
    """Tests for ContentExpansionResponse schema."""

    def test_valid_expansion(self):
        """Test valid content expansion."""
        response = ContentExpansionResponse(
            expanded_content="# Title\n\nExpanded content here with lots of valuable information. " * 10,
            sections_added=["## New Section 1", "### Subsection"],
            word_count_added=150
        )
        assert len(response.sections_added) >= 1
        assert response.word_count_added >= 50

    def test_sections_cleaned(self):
        """Test markdown heading markers are removed from section names."""
        response = ContentExpansionResponse(
            expanded_content="Content " * 50,
            sections_added=["## Getting Started", "### Installation Guide"],
            word_count_added=100
        )
        assert response.sections_added[0] == "Getting Started"
        assert response.sections_added[1] == "Installation Guide"

    def test_minimum_sections_required(self):
        """Test at least one section must be added."""
        with pytest.raises(ValidationError):
            ContentExpansionResponse(
                expanded_content="Content " * 50,
                sections_added=[],  # Empty list
                word_count_added=100
            )

    def test_minimum_word_count(self):
        """Test word count must be at least 50."""
        with pytest.raises(ValidationError):
            ContentExpansionResponse(
                expanded_content="Content " * 50,
                sections_added=["New Section"],
                word_count_added=10  # Below 50
            )


class TestReadabilityResponse:
    """Tests for ReadabilityResponse schema."""

    def test_valid_response(self):
        """Test valid readability improvement response."""
        response = ReadabilityResponse(
            improved_content="Improved content here " * 10,
            changes_summary=["Simplified complex sentence", "Broke up long paragraph"],
            estimated_flesch_improvement=15
        )
        assert len(response.changes_summary) >= 1
        assert 0 <= response.estimated_flesch_improvement <= 50

    def test_flesch_improvement_bounds(self):
        """Test flesch improvement must be 0-50."""
        with pytest.raises(ValidationError):
            ReadabilityResponse(
                improved_content="Content " * 20,
                changes_summary=["Change made"],
                estimated_flesch_improvement=60  # Exceeds max
            )

    def test_at_least_one_change_required(self):
        """Test at least one change must be summarized."""
        with pytest.raises(ValidationError):
            ReadabilityResponse(
                improved_content="Content " * 20,
                changes_summary=[],  # Empty
                estimated_flesch_improvement=10
            )


class TestKeywordOptimizationResponse:
    """Tests for KeywordOptimizationResponse schema."""

    def test_valid_response(self):
        """Test valid keyword optimization response."""
        response = KeywordOptimizationResponse(
            optimized_content="Content with keywords " * 20,
            keywords_added=5,
            lsi_keywords_used=["Python programming", "coding tutorial"]
        )
        assert response.keywords_added == 5
        assert len(response.lsi_keywords_used) == 2

    def test_keywords_added_max_limit(self):
        """Test keywords added cannot exceed 20 (to prevent stuffing)."""
        with pytest.raises(ValidationError):
            KeywordOptimizationResponse(
                optimized_content="Content " * 20,
                keywords_added=25,  # Exceeds 20
                lsi_keywords_used=[]
            )

    def test_lsi_keywords_normalized(self):
        """Test LSI keywords are normalized to lowercase."""
        response = KeywordOptimizationResponse(
            optimized_content="Content " * 20,
            keywords_added=3,
            lsi_keywords_used=["Python", "TUTORIAL", "Guide"]
        )
        assert response.lsi_keywords_used == ["python", "tutorial", "guide"]


class TestIntentDifferentiationResponse:
    """Tests for IntentDifferentiationResponse schema."""

    def test_valid_response(self):
        """Test valid intent differentiation response."""
        response = IntentDifferentiationResponse(
            differentiated_content="Informational content " * 20,
            target_intent="informational",
            removed_overlap=["pricing section", "buy now CTA"],
            unique_value_added=["step-by-step guide", "common mistakes section"]
        )
        assert response.target_intent == "informational"
        assert len(response.unique_value_added) >= 1

    def test_invalid_intent(self):
        """Test invalid intent value is rejected."""
        with pytest.raises(ValidationError):
            IntentDifferentiationResponse(
                differentiated_content="Content " * 20,
                target_intent="commercial",  # Not in allowed values
                removed_overlap=[],
                unique_value_added=["something unique"]
            )

    def test_unique_value_required(self):
        """Test at least one unique value must be added."""
        with pytest.raises(ValidationError):
            IntentDifferentiationResponse(
                differentiated_content="Content " * 20,
                target_intent="transactional",
                removed_overlap=["something"],
                unique_value_added=[]  # Empty
            )

    def test_all_intent_types(self):
        """Test all three intent types are valid."""
        for intent in ["informational", "transactional", "navigational"]:
            response = IntentDifferentiationResponse(
                differentiated_content="Content " * 20,
                target_intent=intent,
                removed_overlap=[],
                unique_value_added=["unique point"]
            )
            assert response.target_intent == intent


class TestResponseSchemas:
    """Tests for RESPONSE_SCHEMAS mapping."""

    def test_all_schemas_registered(self):
        """Test all 6 schemas are in RESPONSE_SCHEMAS."""
        expected = {
            "title_optimization",
            "meta_description",
            "content_expansion",
            "readability_improvement",
            "keyword_optimization",
            "intent_differentiation",
        }
        assert set(RESPONSE_SCHEMAS.keys()) == expected

    def test_get_response_schema_valid(self):
        """Test get_response_schema returns correct schema."""
        schema = get_response_schema("title_optimization")
        assert schema == TitleOptimizationResponse

    def test_get_response_schema_invalid(self):
        """Test get_response_schema raises for invalid type."""
        with pytest.raises(ValueError) as exc_info:
            get_response_schema("invalid_type")
        assert "Unknown prompt type" in str(exc_info.value)
