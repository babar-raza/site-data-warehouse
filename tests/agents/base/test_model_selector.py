"""
Test suite for OllamaModelSelector (TASKCARD-013)

Tests the intelligent model selection functionality for resource-aware
LLM execution with Ollama.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from agents.base.model_selector import (
    OllamaModelSelector,
    TaskComplexity,
    ModelRequirements,
    ModelConfig,
    MODEL_CATALOG,
    MODEL_PREFERENCES
)
from agents.base.resource_monitor import SystemResourceMonitor


class TestOllamaModelSelectorBasics:
    """Test basic OllamaModelSelector functionality"""

    def test_initialization_default(self):
        """Test selector initializes with defaults"""
        selector = OllamaModelSelector(
            available_models=['phi3:mini', 'llama3.2:3b']
        )

        assert selector.default_model == 'phi3:mini'
        assert selector.resource_monitor is not None
        assert 'phi3:mini' in selector.available_models

    def test_initialization_custom_default_model(self):
        """Test selector with custom default model"""
        selector = OllamaModelSelector(
            available_models=['llama3.1:8b'],
            default_model='llama3.1:8b'
        )

        assert selector.default_model == 'llama3.1:8b'

    def test_initialization_custom_resource_monitor(self):
        """Test selector with custom resource monitor"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        selector = OllamaModelSelector(
            resource_monitor=monitor,
            available_models=['phi3:mini']
        )

        assert selector.resource_monitor is monitor

    def test_initialization_ollama_host(self):
        """Test selector with custom Ollama host"""
        selector = OllamaModelSelector(
            available_models=['phi3:mini'],
            ollama_host='http://custom:11434'
        )

        assert selector.ollama_host == 'http://custom:11434'


class TestModelCatalog:
    """Test model catalog configuration"""

    def test_catalog_contains_required_models(self):
        """Test catalog contains all required models from taskcard"""
        required_models = ['llama3.1:70b', 'llama3.1:8b', 'llama3.2:3b', 'phi3:mini']

        for model in required_models:
            assert model in MODEL_CATALOG, f"Missing required model: {model}"

    def test_model_requirements_have_all_fields(self):
        """Test each model has complete requirements"""
        for model_name, requirements in MODEL_CATALOG.items():
            assert requirements.ram_gb > 0, f"{model_name} missing ram_gb"
            assert requirements.vram_gb >= 0, f"{model_name} invalid vram_gb"
            assert requirements.context_length > 0, f"{model_name} missing context_length"
            assert requirements.cpu_threads > 0, f"{model_name} missing cpu_threads"
            assert 1 <= requirements.quality_tier <= 4, f"{model_name} invalid quality_tier"

    def test_model_preferences_cover_all_complexities(self):
        """Test preference lists exist for all complexity levels"""
        for complexity in TaskComplexity:
            assert complexity in MODEL_PREFERENCES, f"Missing preferences for {complexity}"
            assert len(MODEL_PREFERENCES[complexity]) > 0


class TestSelectBestModel:
    """Test select_best_model() method"""

    @pytest.fixture
    def mock_resources_high(self):
        """Mock high resource availability"""
        return {
            'ram_total_gb': 64.0,
            'ram_free_gb': 48.0,
            'ram_used_gb': 16.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 16,
            'cpu_cores_logical': 32,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3500.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 4090',
            'vram_total_gb': 24.0,
            'vram_free_gb': 20.0,
            'vram_used_gb': 4.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

    @pytest.fixture
    def mock_resources_medium(self):
        """Mock medium resource availability"""
        return {
            'ram_total_gb': 16.0,
            'ram_free_gb': 10.0,
            'ram_used_gb': 6.0,
            'ram_usage_pct': 37.5,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3060',
            'vram_total_gb': 8.0,
            'vram_free_gb': 6.0,
            'vram_used_gb': 2.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

    @pytest.fixture
    def mock_resources_low(self):
        """Mock low resource availability"""
        return {
            'ram_total_gb': 8.0,
            'ram_free_gb': 4.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 40.0,
            'cpu_freq_mhz': 2500.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

    def test_returns_string(self, mock_resources_medium):
        """Test select_best_model returns a string"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_medium

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']
        )

        result = selector.select_best_model(task_complexity='medium')
        assert isinstance(result, str)

    def test_prefers_larger_model_with_high_resources(self, mock_resources_high):
        """Test larger models preferred when resources available"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_high

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:70b', 'llama3.1:8b', 'llama3.2:3b', 'phi3:mini']
        )

        result = selector.select_best_model(task_complexity='expert')
        # With 48GB RAM and 20GB VRAM, should select larger model
        # (70b needs 48GB RAM, 40GB VRAM - might not fit)
        # Should fallback to 8b which fits
        assert result in ['llama3.1:70b', 'llama3.1:8b']

    def test_falls_back_to_smaller_model_with_low_resources(self, mock_resources_low):
        """Test smaller models selected when resources limited"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_low

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'llama3.2:3b', 'phi3:mini', 'tinyllama:1.1b']
        )

        result = selector.select_best_model(task_complexity='medium')
        # With 4GB free RAM (3.2GB with margin), should select small model
        assert result in ['phi3:mini', 'tinyllama:1.1b', 'llama3.2:3b']

    def test_respects_task_complexity(self, mock_resources_medium):
        """Test different complexity levels affect selection"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_medium

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']
        )

        # Simple tasks prefer smaller models
        simple_result = selector.select_best_model(task_complexity='simple')
        # Complex tasks prefer larger models
        complex_result = selector.select_best_model(task_complexity='complex')

        # Both should be valid models
        assert simple_result in ['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']
        assert complex_result in ['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']

    def test_returns_default_when_no_suitable_model(self):
        """Test returns default model when none suitable"""
        mock_resources = {
            'ram_total_gb': 2.0,
            'ram_free_gb': 0.5,  # Very low
            'ram_used_gb': 1.5,
            'ram_usage_pct': 75.0,
            'cpu_cores': 2,
            'cpu_cores_logical': 4,
            'cpu_usage_pct': 80.0,
            'cpu_freq_mhz': 2000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:70b'],  # Only large model available
            default_model='phi3:mini'
        )

        result = selector.select_best_model(task_complexity='simple')
        assert result == 'phi3:mini'

    def test_handles_unknown_complexity(self, mock_resources_medium):
        """Test handles unknown complexity level gracefully"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_medium

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.2:3b', 'phi3:mini']
        )

        result = selector.select_best_model(task_complexity='unknown')
        assert result in ['llama3.2:3b', 'phi3:mini']


class TestCanRunModel:
    """Test _can_run_model() method"""

    @pytest.fixture
    def selector(self):
        """Create selector with mocked monitor"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        return OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'phi3:mini']
        )

    def test_returns_false_for_unavailable_model(self, selector):
        """Test returns False for model not in available list"""
        resources = {'gpu_available': False, 'ram_free_gb': 16.0}

        result = selector._can_run_model(
            'nonexistent:model',
            resources,
            4096,
            True
        )

        assert result is False

    def test_returns_false_for_insufficient_context(self, selector):
        """Test returns False when context requirement exceeds model capability"""
        resources = {'gpu_available': False, 'ram_free_gb': 16.0, 'vram_free_gb': 0.0}

        # tinyllama has 2048 context
        selector._available_models.add('tinyllama:1.1b')

        result = selector._can_run_model(
            'tinyllama:1.1b',
            resources,
            10000,  # Requires more than 2048
            True
        )

        assert result is False

    def test_returns_true_with_sufficient_gpu(self, selector):
        """Test returns True when GPU has sufficient VRAM"""
        resources = {
            'gpu_available': True,
            'vram_free_gb': 10.0,
            'ram_free_gb': 16.0
        }

        result = selector._can_run_model(
            'llama3.1:8b',  # Needs 6GB VRAM
            resources,
            4096,
            True
        )

        assert result is True

    def test_returns_true_with_sufficient_ram_no_gpu(self, selector):
        """Test returns True when RAM sufficient and no GPU"""
        resources = {
            'gpu_available': False,
            'vram_free_gb': 0.0,
            'ram_free_gb': 16.0
        }

        result = selector._can_run_model(
            'llama3.1:8b',  # Needs 8GB RAM
            resources,
            4096,
            False
        )

        assert result is True


class TestGetExecutionConfig:
    """Test get_execution_config() method"""

    @pytest.fixture
    def mock_resources_gpu(self):
        """Mock resources with GPU"""
        return {
            'ram_total_gb': 32.0,
            'ram_free_gb': 24.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3500.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3080',
            'vram_total_gb': 10.0,
            'vram_free_gb': 8.0,
            'vram_used_gb': 2.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

    @pytest.fixture
    def mock_resources_cpu_only(self):
        """Mock resources without GPU"""
        return {
            'ram_total_gb': 16.0,
            'ram_free_gb': 12.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

    def test_returns_dict(self, mock_resources_gpu):
        """Test returns a dictionary"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b')
        assert isinstance(result, dict)

    def test_contains_required_keys(self, mock_resources_gpu):
        """Test config contains all required keys"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b')

        required_keys = ['model', 'num_ctx', 'num_gpu', 'num_thread', 'use_gpu']
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_gpu_config_when_gpu_available(self, mock_resources_gpu):
        """Test GPU configuration when GPU available"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b')

        assert result['use_gpu'] is True
        assert result['num_gpu'] != 0

    def test_cpu_config_when_no_gpu(self, mock_resources_cpu_only):
        """Test CPU configuration when no GPU"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_cpu_only

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b')

        assert result['use_gpu'] is False
        assert result['num_gpu'] == 0

    def test_force_cpu_overrides_gpu(self, mock_resources_gpu):
        """Test force_cpu parameter forces CPU execution"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b', force_cpu=True)

        assert result['use_gpu'] is False
        assert result['num_gpu'] == 0

    def test_context_size_override(self, mock_resources_gpu):
        """Test custom context size"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b', context_size=16384)

        assert result['num_ctx'] == 16384

    def test_temperature_setting(self, mock_resources_gpu):
        """Test temperature parameter"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_gpu

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b', temperature=0.5)

        assert result['temperature'] == 0.5

    def test_thread_count_respects_cpu_cores(self, mock_resources_cpu_only):
        """Test thread count is bounded by CPU cores"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = mock_resources_cpu_only

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_execution_config('llama3.1:8b')

        assert result['num_thread'] <= mock_resources_cpu_only['cpu_cores']


class TestGetModelRequirements:
    """Test _get_model_requirements() method"""

    def test_returns_known_model_requirements(self):
        """Test returns requirements for known model"""
        selector = OllamaModelSelector(available_models=['llama3.1:8b'])

        result = selector._get_model_requirements('llama3.1:8b')

        assert result is not None
        assert result.ram_gb == 8.0
        assert result.vram_gb == 6.0

    def test_matches_base_name(self):
        """Test matches model by base name"""
        selector = OllamaModelSelector(available_models=['llama3.1:latest'])

        # Should match llama3.1:8b requirements
        result = selector._get_model_requirements('llama3.1:latest')

        assert result is not None

    def test_estimates_unknown_model(self):
        """Test estimates requirements for unknown model"""
        selector = OllamaModelSelector(available_models=['custom:7b'])

        result = selector._get_model_requirements('custom:7b')

        assert result is not None
        # Should estimate based on 7b in name
        assert result.ram_gb == 8.0


class TestEstimateRequirements:
    """Test _estimate_requirements() method"""

    def test_estimates_70b_model(self):
        """Test estimates 70B model requirements"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_requirements('custom:70b')

        assert result.ram_gb >= 40.0
        assert result.quality_tier == 1

    def test_estimates_7b_model(self):
        """Test estimates 7B model requirements"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_requirements('custom:7b')

        assert 4.0 <= result.ram_gb <= 16.0
        assert result.quality_tier in [2, 3]

    def test_estimates_mini_model(self):
        """Test estimates mini model requirements"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_requirements('custom:mini')

        assert result.ram_gb <= 4.0
        assert result.quality_tier == 4


class TestModelConfig:
    """Test ModelConfig dataclass"""

    def test_to_dict(self):
        """Test to_dict method"""
        config = ModelConfig(
            model='llama3.1:8b',
            num_ctx=8192,
            num_gpu=-1,
            num_thread=8,
            use_gpu=True,
            temperature=0.7
        )

        result = config.to_dict()

        assert result['model'] == 'llama3.1:8b'
        assert result['num_ctx'] == 8192
        assert result['num_gpu'] == -1
        assert result['num_thread'] == 8
        assert result['use_gpu'] is True
        assert result['temperature'] == 0.7


class TestTaskComplexity:
    """Test TaskComplexity enum"""

    def test_all_values(self):
        """Test all complexity levels exist"""
        assert TaskComplexity.SIMPLE.value == 'simple'
        assert TaskComplexity.MEDIUM.value == 'medium'
        assert TaskComplexity.COMPLEX.value == 'complex'
        assert TaskComplexity.EXPERT.value == 'expert'

    def test_from_string(self):
        """Test creating from string"""
        assert TaskComplexity('simple') == TaskComplexity.SIMPLE
        assert TaskComplexity('medium') == TaskComplexity.MEDIUM


class TestGetModelInfo:
    """Test get_model_info() method"""

    def test_returns_dict(self):
        """Test returns dictionary"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_free_gb': 16.0, 'gpu_available': False, 'vram_free_gb': 0.0,
            'cpu_cores': 8, 'cpu_cores_logical': 16
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        result = selector.get_model_info('llama3.1:8b')

        assert isinstance(result, dict)
        assert 'name' in result
        assert 'available' in result
        assert 'requirements' in result
        assert 'can_run' in result

    def test_available_status(self):
        """Test available status is correct"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_free_gb': 16.0, 'gpu_available': False, 'vram_free_gb': 0.0,
            'cpu_cores': 8, 'cpu_cores_logical': 16
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b']
        )

        available_info = selector.get_model_info('llama3.1:8b')
        unavailable_info = selector.get_model_info('nonexistent:model')

        assert available_info['available'] is True
        assert unavailable_info['available'] is False


class TestListRunnableModels:
    """Test list_runnable_models() method"""

    def test_returns_list(self):
        """Test returns list"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_free_gb': 16.0, 'gpu_available': False, 'vram_free_gb': 0.0,
            'cpu_cores': 8, 'cpu_cores_logical': 16
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'phi3:mini']
        )

        result = selector.list_runnable_models()

        assert isinstance(result, list)

    def test_filters_by_resources(self):
        """Test filters models by available resources"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_free_gb': 3.0,  # Low RAM
            'gpu_available': False,
            'vram_free_gb': 0.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:70b', 'llama3.1:8b', 'phi3:mini']
        )

        result = selector.list_runnable_models()

        # Should not include large models
        model_names = [m['name'] for m in result]
        assert 'llama3.1:70b' not in model_names


class TestGetRecommendation:
    """Test get_recommendation() method"""

    def test_returns_complete_recommendation(self):
        """Test returns complete recommendation dict"""
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 12.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'phi3:mini']
        )

        result = selector.get_recommendation(
            task_description="Analyze code",
            required_context=4096
        )

        assert 'selected_model' in result
        assert 'estimated_complexity' in result
        assert 'execution_config' in result
        assert 'alternatives' in result
        assert 'resources' in result


class TestEstimateComplexity:
    """Test _estimate_complexity() method"""

    def test_expert_keywords(self):
        """Test expert keywords trigger EXPERT complexity"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_complexity("Complex multi-step reasoning task")

        assert result in [TaskComplexity.EXPERT, TaskComplexity.COMPLEX]

    def test_complex_keywords(self):
        """Test complex keywords trigger COMPLEX complexity"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_complexity("Generate code for the feature")

        assert result == TaskComplexity.COMPLEX

    def test_simple_keywords(self):
        """Test simple keywords trigger SIMPLE complexity"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_complexity("Simple classification task")

        assert result == TaskComplexity.SIMPLE

    def test_default_to_medium(self):
        """Test defaults to MEDIUM for neutral descriptions"""
        selector = OllamaModelSelector(available_models=[])

        result = selector._estimate_complexity("Process the data")

        assert result == TaskComplexity.MEDIUM


class TestIntegration:
    """Integration tests for OllamaModelSelector"""

    def test_full_workflow(self):
        """Test complete model selection workflow"""
        # Create selector with mocked resource monitor
        mock_monitor = Mock(spec=SystemResourceMonitor)
        mock_monitor.get_current_resources.return_value = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 12.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3060',
            'vram_total_gb': 8.0,
            'vram_free_gb': 6.0,
            'vram_used_gb': 2.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        selector = OllamaModelSelector(
            resource_monitor=mock_monitor,
            available_models=['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']
        )

        # Select model
        model = selector.select_best_model(task_complexity='medium')
        assert model in ['llama3.1:8b', 'llama3.2:3b', 'phi3:mini']

        # Get config
        config = selector.get_execution_config(model)
        assert 'model' in config
        assert 'num_ctx' in config

        # Get recommendation
        rec = selector.get_recommendation(
            task_description="Analyze this code",
            required_context=8192
        )
        assert 'selected_model' in rec
        assert 'execution_config' in rec
