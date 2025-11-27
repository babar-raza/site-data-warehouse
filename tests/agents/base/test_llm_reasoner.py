"""
Tests for LLMReasoner and related classes.

Comprehensive test coverage for:
- LLMReasoner reasoning methods
- JSON response parsing and validation
- Model selection integration
- Error handling and retries
- Prompt template integration
- Specialized reasoners
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from agents.base.llm_reasoner import (
    LLMReasoner,
    ReasoningResult,
    ResponseFormat,
    SpecializedReasoner,
    AnomalyAnalyzer,
    DiagnosisAnalyzer,
    RecommendationGenerator,
)
from agents.base.prompt_templates import (
    PromptTemplates,
    PromptTemplate,
)
from agents.base.model_selector import OllamaModelSelector


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_model_selector():
    """Create a mock model selector."""
    selector = Mock(spec=OllamaModelSelector)
    selector.select_best_model.return_value = 'llama3.2:3b'
    selector.get_execution_config.return_value = {
        'model': 'llama3.2:3b',
        'num_ctx': 4096,
        'num_gpu': 0,
        'num_thread': 4,
        'temperature': 0.7,
    }
    selector.ollama_host = 'http://localhost:11434'
    selector._estimate_complexity.return_value = Mock(value='medium')
    return selector


@pytest.fixture
def reasoner(mock_model_selector):
    """Create a LLMReasoner with mocked model selector."""
    return LLMReasoner(
        model_selector=mock_model_selector,
        default_timeout=30.0,
        max_retries=1
    )


@pytest.fixture
def valid_json_response():
    """Valid JSON response for anomaly analysis."""
    return json.dumps({
        "severity": "high",
        "likely_causes": ["Algorithm update", "Technical issue"],
        "confidence": 0.8,
        "recommended_actions": ["Check GSC", "Review logs"],
        "reasoning": "Based on the pattern..."
    })


@pytest.fixture
def valid_diagnosis_response():
    """Valid JSON response for diagnosis."""
    return json.dumps({
        "root_cause": "Google algorithm update",
        "confidence": 0.75,
        "evidence": ["Timing matches update", "Similar pattern site-wide"],
        "contributing_factors": ["Low content quality"],
        "verification_steps": ["Check algorithm tracker"]
    })


# ============================================================================
# Test ReasoningResult
# ============================================================================

class TestReasoningResult:
    """Tests for ReasoningResult dataclass."""

    def test_successful_result(self):
        result = ReasoningResult(
            success=True,
            content={"key": "value"},
            raw_response='{"key": "value"}',
            model_used="llama3.2:3b",
            duration_ms=500
        )
        assert result.success is True
        assert result.content == {"key": "value"}
        assert result.error is None

    def test_failed_result(self):
        result = ReasoningResult(
            success=False,
            content=None,
            error="Connection failed"
        )
        assert result.success is False
        assert result.content is None
        assert result.error == "Connection failed"

    def test_to_dict(self):
        result = ReasoningResult(
            success=True,
            content={"test": 1},
            model_used="test-model",
            duration_ms=100
        )
        d = result.to_dict()
        assert d['success'] is True
        assert d['content'] == {"test": 1}
        assert d['model_used'] == "test-model"

    def test_validation_errors(self):
        result = ReasoningResult(
            success=True,
            content={"incomplete": True},
            validation_errors=["Missing required field: severity"]
        )
        assert len(result.validation_errors) == 1


# ============================================================================
# Test ResponseFormat
# ============================================================================

class TestResponseFormat:
    """Tests for ResponseFormat enum."""

    def test_json_format(self):
        assert ResponseFormat.JSON.value == "json"

    def test_text_format(self):
        assert ResponseFormat.TEXT.value == "text"

    def test_format_from_string(self):
        assert ResponseFormat("json") == ResponseFormat.JSON
        assert ResponseFormat("text") == ResponseFormat.TEXT


# ============================================================================
# Test LLMReasoner Initialization
# ============================================================================

class TestLLMReasonerInit:
    """Tests for LLMReasoner initialization."""

    def test_default_initialization(self, mock_model_selector):
        reasoner = LLMReasoner(model_selector=mock_model_selector)
        assert reasoner.default_timeout == 60.0
        assert reasoner.max_retries == 2

    def test_custom_timeout(self, mock_model_selector):
        reasoner = LLMReasoner(
            model_selector=mock_model_selector,
            default_timeout=30.0
        )
        assert reasoner.default_timeout == 30.0

    def test_timeout_capped_at_60(self, mock_model_selector):
        reasoner = LLMReasoner(
            model_selector=mock_model_selector,
            default_timeout=120.0
        )
        assert reasoner.default_timeout == 60.0

    def test_custom_retries(self, mock_model_selector):
        reasoner = LLMReasoner(
            model_selector=mock_model_selector,
            max_retries=5
        )
        assert reasoner.max_retries == 5

    def test_creates_model_selector_if_none(self):
        with patch('agents.base.llm_reasoner.OllamaModelSelector') as MockSelector:
            mock_instance = Mock()
            mock_instance.ollama_host = 'http://localhost:11434'
            MockSelector.return_value = mock_instance
            reasoner = LLMReasoner()
            MockSelector.assert_called_once()


# ============================================================================
# Test Model Selection
# ============================================================================

class TestModelSelection:
    """Tests for model selection in LLMReasoner."""

    def test_select_model_called(self, reasoner, mock_model_selector, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test prompt")
            mock_model_selector.select_best_model.assert_called_once()

    def test_select_model_with_complexity(self, reasoner, mock_model_selector, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test prompt", task_complexity="complex")
            mock_model_selector.select_best_model.assert_called_with(
                task_complexity="complex"
            )

    def test_execution_config_used(self, reasoner, mock_model_selector, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test prompt", temperature=0.5)
            mock_model_selector.get_execution_config.assert_called()


# ============================================================================
# Test JSON Parsing
# ============================================================================

class TestJSONParsing:
    """Tests for JSON response parsing."""

    def test_parse_valid_json(self, reasoner):
        response = '{"key": "value", "number": 42}'
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"key": "value", "number": 42}
        assert errors == []

    def test_parse_json_from_code_block(self, reasoner):
        response = '```json\n{"key": "value"}\n```'
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"key": "value"}
        assert errors == []

    def test_parse_json_from_generic_code_block(self, reasoner):
        response = '```\n{"key": "value"}\n```'
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"key": "value"}
        assert errors == []

    def test_parse_json_embedded_in_text(self, reasoner):
        response = 'Here is the analysis: {"result": "success"} Hope this helps!'
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"result": "success"}
        assert errors == []

    def test_parse_invalid_json(self, reasoner):
        response = 'Not valid JSON at all'
        parsed, errors = reasoner._parse_json(response)
        assert parsed is None
        assert len(errors) > 0

    def test_parse_json_with_whitespace(self, reasoner):
        response = '  \n  {"key": "value"}  \n  '
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"key": "value"}

    def test_parse_nested_json(self, reasoner):
        response = '{"outer": {"inner": [1, 2, 3]}}'
        parsed, errors = reasoner._parse_json(response)
        assert parsed == {"outer": {"inner": [1, 2, 3]}}


# ============================================================================
# Test Response Validation
# ============================================================================

class TestResponseValidation:
    """Tests for JSON schema validation."""

    def test_validate_complete_response(self, reasoner):
        response = {
            "severity": "high",
            "likely_causes": ["Cause 1"],
            "recommended_actions": ["Action 1"]
        }
        schema = PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        is_valid, errors = reasoner._validate_response(response, schema)
        assert is_valid is True
        assert errors == []

    def test_validate_missing_required_field(self, reasoner):
        response = {
            "severity": "high"
            # Missing likely_causes and recommended_actions
        }
        schema = PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        is_valid, errors = reasoner._validate_response(response, schema)
        assert is_valid is False
        assert any("likely_causes" in e for e in errors)

    def test_validate_invalid_enum_value(self, reasoner):
        response = {
            "severity": "invalid_severity",
            "likely_causes": ["Cause"],
            "recommended_actions": ["Action"]
        }
        schema = PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        is_valid, errors = reasoner._validate_response(response, schema)
        assert is_valid is False
        assert any("severity" in e for e in errors)

    def test_validate_number_out_of_range(self, reasoner):
        response = {
            "severity": "high",
            "likely_causes": ["Cause"],
            "recommended_actions": ["Action"],
            "confidence": 1.5  # Should be 0-1
        }
        schema = PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        is_valid, errors = reasoner._validate_response(response, schema)
        assert is_valid is False
        assert any("confidence" in e for e in errors)


# ============================================================================
# Test reason() Method
# ============================================================================

class TestReasonMethod:
    """Tests for the main reason() method."""

    def test_reason_returns_result(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason("Test prompt")
            assert isinstance(result, ReasoningResult)
            assert result.success is True

    def test_reason_with_json_format(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason("Test prompt", response_format="json")
            assert isinstance(result.content, dict)

    def test_reason_with_text_format(self, reasoner):
        text_response = "This is a text response"
        with patch.object(reasoner, '_call_ollama', return_value=text_response):
            result = reasoner.reason("Test prompt", response_format="text")
            assert result.content == text_response

    def test_reason_with_invalid_format_defaults_to_text(self, reasoner):
        text_response = "Response text"
        with patch.object(reasoner, '_call_ollama', return_value=text_response):
            result = reasoner.reason("Test prompt", response_format="invalid")
            assert result.success is True

    def test_reason_tracks_duration(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason("Test prompt")
            assert result.duration_ms >= 0

    def test_reason_records_model_used(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason("Test prompt")
            assert result.model_used == 'llama3.2:3b'

    def test_reason_with_custom_system_prompt(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response) as mock_call:
            reasoner.reason("Test", system_prompt="Custom system prompt")
            prompt_used = mock_call.call_args[1]['prompt']
            assert "Custom system prompt" in prompt_used


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and retries."""

    def test_handles_timeout_error(self, reasoner):
        with patch.object(reasoner, '_call_ollama', side_effect=TimeoutError("Timeout")):
            result = reasoner.reason("Test")
            assert result.success is False
            assert "Timeout" in result.error

    def test_handles_connection_error(self, reasoner):
        with patch.object(reasoner, '_call_ollama', side_effect=ConnectionError("No connection")):
            result = reasoner.reason("Test")
            assert result.success is False
            assert "connection" in result.error.lower()

    def test_retries_on_failure(self, reasoner, valid_json_response):
        call_count = 0

        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("First call fails")
            return valid_json_response

        with patch.object(reasoner, '_call_ollama', side_effect=failing_then_success):
            result = reasoner.reason("Test")
            assert result.success is True
            assert call_count == 2

    def test_respects_max_retries(self, reasoner):
        reasoner.max_retries = 2
        call_count = 0

        def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Always fails")

        with patch.object(reasoner, '_call_ollama', side_effect=always_fail):
            result = reasoner.reason("Test")
            assert result.success is False
            assert call_count == 3  # Initial + 2 retries

    def test_handles_invalid_json_response(self, reasoner):
        with patch.object(reasoner, '_call_ollama', return_value="Not JSON at all"):
            result = reasoner.reason("Test", response_format="json")
            # Should still return success but with raw response as content
            assert result.success is True
            assert "Not JSON" in str(result.content) or len(result.validation_errors) > 0


# ============================================================================
# Test Template Integration
# ============================================================================

class TestTemplateIntegration:
    """Tests for prompt template integration."""

    def test_reason_with_template_by_name(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason_with_template(
                template="anomaly_analysis",
                template_vars={
                    "metric_name": "clicks",
                    "current_value": 50,
                    "historical_average": 100,
                    "percent_change": -50.0,
                    "time_period": "Last 7 days",
                    "additional_context": ""
                }
            )
            assert result.success is True

    def test_reason_with_template_object(self, reasoner, valid_json_response):
        template = PromptTemplates.get_anomaly_analysis_template()
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            result = reasoner.reason_with_template(
                template=template,
                template_vars={
                    "metric_name": "clicks",
                    "current_value": 50,
                    "historical_average": 100,
                    "percent_change": -50.0,
                    "time_period": "Last 7 days",
                    "additional_context": ""
                }
            )
            assert result.success is True

    def test_reason_with_unknown_template(self, reasoner):
        result = reasoner.reason_with_template(
            template="unknown_template",
            template_vars={}
        )
        assert result.success is False
        assert "Unknown template" in result.error

    def test_reason_with_missing_template_vars(self, reasoner):
        result = reasoner.reason_with_template(
            template="anomaly_analysis",
            template_vars={"metric_name": "clicks"}  # Missing other required vars
        )
        assert result.success is False
        assert "Missing" in result.error or "error" in result.error.lower()


# ============================================================================
# Test Stats Tracking
# ============================================================================

class TestStatsTracking:
    """Tests for usage statistics tracking."""

    def test_tracks_total_calls(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test 1")
            reasoner.reason("Test 2")
            stats = reasoner.get_stats()
            assert stats['total_calls'] == 2

    def test_tracks_successful_calls(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test 1")
        with patch.object(reasoner, '_call_ollama', side_effect=TimeoutError()):
            reasoner.reason("Test 2")
        stats = reasoner.get_stats()
        assert stats['successful_calls'] == 1

    def test_calculates_success_rate(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test 1")
            reasoner.reason("Test 2")
        stats = reasoner.get_stats()
        assert stats['success_rate'] == 1.0

    def test_reset_stats(self, reasoner, valid_json_response):
        with patch.object(reasoner, '_call_ollama', return_value=valid_json_response):
            reasoner.reason("Test")
        reasoner.reset_stats()
        stats = reasoner.get_stats()
        assert stats['total_calls'] == 0


# ============================================================================
# Test Helper Methods
# ============================================================================

class TestHelperMethods:
    """Tests for helper methods."""

    def test_estimate_complexity(self, reasoner):
        complexity = reasoner.estimate_complexity("Analyze this complex data")
        assert complexity == "medium"  # Mocked

    def test_is_available_when_ollama_up(self, reasoner):
        mock_response = Mock()
        mock_response.status_code = 200
        with patch('httpx.get', return_value=mock_response):
            assert reasoner.is_available() is True

    def test_is_available_when_ollama_down(self, reasoner):
        with patch('httpx.get', side_effect=Exception("Connection refused")):
            assert reasoner.is_available() is False

    def test_build_prompt_adds_json_suffix(self, reasoner):
        prompt = reasoner._build_prompt(
            "Test prompt",
            None,
            ResponseFormat.JSON
        )
        assert "JSON" in prompt

    def test_build_prompt_includes_system_prompt(self, reasoner):
        prompt = reasoner._build_prompt(
            "Test prompt",
            "System instructions",
            ResponseFormat.TEXT
        )
        assert "System instructions" in prompt


# ============================================================================
# Test Specialized Reasoners
# ============================================================================

class TestSpecializedReasoners:
    """Tests for specialized reasoner classes."""

    def test_specialized_reasoner_init(self, mock_model_selector):
        class TestReasoner(SpecializedReasoner):
            pass

        reasoner = TestReasoner(
            default_template="anomaly_analysis",
            default_complexity="high",
            model_selector=mock_model_selector
        )
        assert reasoner.default_template == "anomaly_analysis"
        assert reasoner.default_complexity == "high"

    def test_anomaly_analyzer_uses_correct_template(self, mock_model_selector, valid_json_response):
        analyzer = AnomalyAnalyzer(model_selector=mock_model_selector)
        assert analyzer.default_template == "anomaly_analysis"
        assert analyzer.default_complexity == "medium"

    def test_diagnosis_analyzer_uses_correct_template(self, mock_model_selector):
        analyzer = DiagnosisAnalyzer(model_selector=mock_model_selector)
        assert analyzer.default_template == "diagnosis"
        assert analyzer.default_complexity == "complex"

    def test_recommendation_generator_uses_correct_template(self, mock_model_selector):
        generator = RecommendationGenerator(model_selector=mock_model_selector)
        assert generator.default_template == "recommendation"
        assert generator.default_complexity == "complex"

    def test_specialized_analyze_method(self, mock_model_selector, valid_json_response):
        analyzer = AnomalyAnalyzer(model_selector=mock_model_selector)
        with patch.object(analyzer, '_call_ollama', return_value=valid_json_response):
            result = analyzer.analyze(
                metric_name="clicks",
                current_value=50,
                historical_average=100,
                percent_change=-50.0,
                time_period="Last 7 days",
                additional_context=""
            )
            assert result.success is True


# ============================================================================
# Test Ollama API Call
# ============================================================================

class TestOllamaAPICall:
    """Tests for Ollama API integration."""

    def test_call_ollama_success(self, reasoner):
        mock_response = Mock()
        mock_response.json.return_value = {"response": "Test response"}
        mock_response.raise_for_status = Mock()

        with patch('httpx.post', return_value=mock_response):
            result = reasoner._call_ollama(
                model="test-model",
                prompt="Test prompt",
                config={"num_ctx": 4096},
                timeout=30.0
            )
            assert result == "Test response"

    def test_call_ollama_timeout(self, reasoner):
        import httpx
        with patch('httpx.post', side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(TimeoutError):
                reasoner._call_ollama(
                    model="test-model",
                    prompt="Test",
                    config={},
                    timeout=1.0
                )

    def test_call_ollama_connection_error(self, reasoner):
        import httpx
        with patch('httpx.post', side_effect=httpx.ConnectError("Connection refused")):
            with pytest.raises(ConnectionError):
                reasoner._call_ollama(
                    model="test-model",
                    prompt="Test",
                    config={},
                    timeout=1.0
                )

    def test_mock_response_for_json(self, reasoner):
        response = reasoner._mock_response("Please respond in JSON format")
        parsed = json.loads(response)
        assert "severity" in parsed

    def test_mock_response_for_text(self, reasoner):
        response = reasoner._mock_response("Simple text prompt")
        assert "Mock response" in response


# ============================================================================
# Test Format Response
# ============================================================================

class TestFormatResponse:
    """Tests for response formatting."""

    def test_format_text_response(self, reasoner):
        content, errors = reasoner._format_response(
            "Simple text response",
            ResponseFormat.TEXT
        )
        assert content == "Simple text response"
        assert errors == []

    def test_format_json_response_valid(self, reasoner):
        content, errors = reasoner._format_response(
            '{"key": "value"}',
            ResponseFormat.JSON
        )
        assert content == {"key": "value"}
        assert errors == []

    def test_format_json_response_with_schema(self, reasoner):
        response = json.dumps({
            "severity": "high",
            "likely_causes": ["Test"],
            "recommended_actions": ["Test action"]
        })
        content, errors = reasoner._format_response(
            response,
            ResponseFormat.JSON,
            schema=PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        )
        assert content is not None
        assert len(errors) == 0

    def test_format_json_response_invalid_schema(self, reasoner):
        response = json.dumps({
            "severity": "invalid"  # Missing required fields
        })
        content, errors = reasoner._format_response(
            response,
            ResponseFormat.JSON,
            schema=PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        )
        assert len(errors) > 0


# ============================================================================
# Test Prompt Templates Integration
# ============================================================================

class TestPromptTemplatesIntegration:
    """Tests for prompt templates integration with reasoner."""

    def test_get_anomaly_template(self):
        template = PromptTemplates.get_anomaly_analysis_template()
        assert template.name == "anomaly_analysis"
        assert "metric_name" in template.required_placeholders

    def test_get_diagnosis_template(self):
        template = PromptTemplates.get_diagnosis_template()
        assert template.name == "diagnosis"
        assert "issue_description" in template.required_placeholders

    def test_get_recommendation_template(self):
        template = PromptTemplates.get_recommendation_template()
        assert template.name == "recommendation"
        assert "context" in template.required_placeholders

    def test_get_content_analysis_template(self):
        template = PromptTemplates.get_content_analysis_template()
        assert template.name == "content_analysis"

    def test_list_available_templates(self):
        templates = PromptTemplates.list_available_templates()
        assert "anomaly_analysis" in templates
        assert "diagnosis" in templates
        assert "recommendation" in templates
        assert "content_analysis" in templates

    def test_get_template_by_name(self):
        template = PromptTemplates.get_template_by_name("diagnosis")
        assert template is not None
        assert template.name == "diagnosis"

    def test_get_unknown_template_returns_none(self):
        template = PromptTemplates.get_template_by_name("unknown")
        assert template is None

    def test_format_user_prompt(self):
        template = PromptTemplates.get_anomaly_analysis_template()
        prompt = template.format_user_prompt(
            metric_name="clicks",
            current_value=50,
            historical_average=100,
            percent_change=-50.0,
            time_period="Last 7 days",
            additional_context=""
        )
        assert "clicks" in prompt
        assert "50" in prompt

    def test_format_prompt_missing_placeholder(self):
        template = PromptTemplates.get_anomaly_analysis_template()
        with pytest.raises(ValueError):
            template.format_user_prompt(metric_name="clicks")  # Missing other required

    def test_validate_response_method(self):
        valid, errors = PromptTemplates.validate_response(
            {"severity": "high", "likely_causes": ["Test"], "recommended_actions": ["Action"]},
            PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
        )
        assert valid is True

    def test_create_json_prompt_suffix(self):
        suffix = PromptTemplates.create_json_prompt_suffix()
        assert "JSON" in suffix

    def test_get_schema_for_template(self):
        schema = PromptTemplates.get_schema_for_template("anomaly_analysis")
        assert schema is not None
        assert "properties" in schema
