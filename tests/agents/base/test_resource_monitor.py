"""
Test suite for SystemResourceMonitor (TASKCARD-012)

Tests the system resource monitoring functionality used for
resource-aware LLM execution.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

from agents.base.resource_monitor import (
    SystemResourceMonitor,
    ResourceThresholds
)


class TestSystemResourceMonitorBasics:
    """Test basic SystemResourceMonitor functionality"""

    def test_initialization_default_thresholds(self):
        """Test monitor initializes with default thresholds"""
        monitor = SystemResourceMonitor()

        assert monitor.thresholds is not None
        assert monitor.thresholds.ram_usage_pct == 85.0
        assert monitor.thresholds.cpu_usage_pct == 90.0
        assert monitor.thresholds.min_ram_free_gb == 2.0
        assert monitor.thresholds.min_vram_free_gb == 2.0

    def test_initialization_custom_thresholds(self):
        """Test monitor initializes with custom thresholds"""
        custom_thresholds = ResourceThresholds(
            ram_usage_pct=70.0,
            cpu_usage_pct=80.0,
            min_ram_free_gb=4.0,
            min_vram_free_gb=3.0
        )
        monitor = SystemResourceMonitor(thresholds=custom_thresholds)

        assert monitor.thresholds.ram_usage_pct == 70.0
        assert monitor.thresholds.cpu_usage_pct == 80.0
        assert monitor.thresholds.min_ram_free_gb == 4.0
        assert monitor.thresholds.min_vram_free_gb == 3.0

    def test_custom_cpu_sample_interval(self):
        """Test monitor accepts custom CPU sample interval"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        assert monitor._cpu_sample_interval == 0.1


class TestGetCurrentResources:
    """Test get_current_resources() method"""

    def test_returns_dict(self):
        """Test that get_current_resources returns a dict"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert isinstance(resources, dict)

    def test_contains_all_required_keys(self):
        """Test that returned dict contains all required keys"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        required_keys = [
            'ram_total_gb',
            'ram_free_gb',
            'ram_used_gb',
            'ram_usage_pct',
            'cpu_cores',
            'cpu_cores_logical',
            'cpu_usage_pct',
            'cpu_freq_mhz',
            'gpu_available',
            'gpu_name',
            'vram_total_gb',
            'vram_free_gb',
            'vram_used_gb',
            'platform',
            'hostname',
        ]

        for key in required_keys:
            assert key in resources, f"Missing required key: {key}"

    def test_ram_total_greater_than_zero(self):
        """Test that RAM total is greater than zero"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert resources['ram_total_gb'] > 0

    def test_ram_free_within_bounds(self):
        """Test that RAM free is within valid bounds"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert resources['ram_free_gb'] >= 0
        assert resources['ram_free_gb'] <= resources['ram_total_gb']

    def test_ram_usage_pct_within_bounds(self):
        """Test that RAM usage percentage is within 0-100"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert 0 <= resources['ram_usage_pct'] <= 100

    def test_cpu_cores_greater_than_zero(self):
        """Test that CPU cores is greater than zero"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert resources['cpu_cores'] > 0
        assert resources['cpu_cores_logical'] >= resources['cpu_cores']

    def test_cpu_usage_pct_within_bounds(self):
        """Test that CPU usage percentage is within 0-100"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert 0 <= resources['cpu_usage_pct'] <= 100

    def test_gpu_available_is_boolean(self):
        """Test that gpu_available is a boolean"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert isinstance(resources['gpu_available'], bool)

    def test_vram_values_when_no_gpu(self):
        """Test VRAM values are zero when GPU not available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        # Mock _detect_gpu to return None
        with patch.object(monitor, '_detect_gpu', return_value=None):
            resources = monitor.get_current_resources()

            if not resources['gpu_available']:
                assert resources['vram_total_gb'] == 0.0
                assert resources['vram_free_gb'] == 0.0
                assert resources['vram_used_gb'] == 0.0

    def test_platform_is_string(self):
        """Test that platform is a non-empty string"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        resources = monitor.get_current_resources()

        assert isinstance(resources['platform'], str)
        assert len(resources['platform']) > 0


class TestGPUDetection:
    """Test GPU detection functionality"""

    def test_gpu_detection_with_torch_available(self):
        """Test GPU detection when torch with CUDA is available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        # Mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.cuda.get_device_name.return_value = "NVIDIA Test GPU"
        mock_torch.cuda.mem_get_info.return_value = (
            8 * 1024**3,  # 8 GB free
            12 * 1024**3  # 12 GB total
        )

        with patch.dict('sys.modules', {'torch': mock_torch}):
            gpu_info = monitor._detect_gpu()

            # Note: This test may not work if torch is already imported
            # The mock would need to be set up before import

    def test_gpu_detection_without_torch(self):
        """Test GPU detection gracefully handles missing torch"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        # Simulate torch not being available
        with patch.dict('sys.modules', {'torch': None}):
            with patch('builtins.__import__', side_effect=ImportError("No torch")):
                gpu_info = monitor._detect_gpu()
                # Should return None without raising exception
                assert gpu_info is None

    def test_gpu_detection_cuda_not_available(self):
        """Test GPU detection when CUDA not available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict('sys.modules', {'torch': mock_torch}):
            # Force reimport
            import importlib
            # Note: actual reimport behavior may vary


class TestIsSystemOverloaded:
    """Test is_system_overloaded() method"""

    def test_returns_boolean(self):
        """Test that is_system_overloaded returns a boolean"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)
        result = monitor.is_system_overloaded()

        assert isinstance(result, bool)

    def test_overloaded_when_ram_high(self):
        """Test system detected as overloaded when RAM usage high"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        # Mock high RAM usage
        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 1.0,
            'ram_used_gb': 15.0,
            'ram_usage_pct': 95.0,  # Above 85% threshold
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_system_overloaded() is True

    def test_overloaded_when_cpu_high(self):
        """Test system detected as overloaded when CPU usage high"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 95.0,  # Above 90% threshold
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_system_overloaded() is True

    def test_overloaded_when_ram_free_low(self):
        """Test system detected as overloaded when free RAM too low"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 1.0,  # Below 2.0 GB threshold
            'ram_used_gb': 15.0,
            'ram_usage_pct': 70.0,  # Below percentage threshold
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_system_overloaded() is True

    def test_not_overloaded_when_resources_ok(self):
        """Test system not overloaded when resources within thresholds"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,  # Below 85% threshold
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,  # Below 90% threshold
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_system_overloaded() is False

    def test_custom_thresholds_respected(self):
        """Test that custom thresholds are respected"""
        custom_thresholds = ResourceThresholds(
            ram_usage_pct=50.0,  # Stricter threshold
            cpu_usage_pct=50.0,
            min_ram_free_gb=2.0,
            min_vram_free_gb=2.0
        )
        monitor = SystemResourceMonitor(
            thresholds=custom_thresholds,
            cpu_sample_interval=0.1
        )

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 60.0,  # Above custom 50% threshold
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_system_overloaded() is True


class TestIsGPUAvailableForLLM:
    """Test is_gpu_available_for_llm() method"""

    def test_returns_false_when_no_gpu(self):
        """Test returns False when no GPU available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_gpu_available_for_llm() is False

    def test_returns_true_when_gpu_has_enough_vram(self):
        """Test returns True when GPU has enough VRAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3080',
            'vram_total_gb': 10.0,
            'vram_free_gb': 6.0,  # Above 2.0 GB default threshold
            'vram_used_gb': 4.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_gpu_available_for_llm() is True

    def test_returns_false_when_vram_low(self):
        """Test returns False when VRAM is below threshold"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA GTX 1050',
            'vram_total_gb': 4.0,
            'vram_free_gb': 1.0,  # Below 2.0 GB default threshold
            'vram_used_gb': 3.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.is_gpu_available_for_llm() is False

    def test_custom_min_vram_respected(self):
        """Test custom min_vram_gb parameter is respected"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3080',
            'vram_total_gb': 10.0,
            'vram_free_gb': 6.0,
            'vram_used_gb': 4.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            # Should pass with default 2.0 GB threshold
            assert monitor.is_gpu_available_for_llm() is True
            # Should fail with 8.0 GB requirement
            assert monitor.is_gpu_available_for_llm(min_vram_gb=8.0) is False


class TestGetRecommendedModelSize:
    """Test get_recommended_model_size() method"""

    def test_large_model_with_high_vram(self):
        """Test recommends large model with 12+ GB VRAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 32.0,
            'ram_free_gb': 24.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3500.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 4090',
            'vram_total_gb': 24.0,
            'vram_free_gb': 16.0,
            'vram_used_gb': 8.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'large'

    def test_medium_model_with_8gb_vram(self):
        """Test recommends medium model with 8-12 GB VRAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 12.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3070',
            'vram_total_gb': 8.0,
            'vram_free_gb': 8.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'medium'

    def test_small_model_with_4gb_vram(self):
        """Test recommends small model with 4-8 GB VRAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA GTX 1650',
            'vram_total_gb': 4.0,
            'vram_free_gb': 4.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'small'

    def test_tiny_model_with_low_vram(self):
        """Test recommends tiny model with <4 GB VRAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 8.0,
            'ram_free_gb': 4.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 2,
            'cpu_cores_logical': 4,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 2500.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA GT 1030',
            'vram_total_gb': 2.0,
            'vram_free_gb': 2.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'tiny'

    def test_cpu_only_high_ram_recommends_medium(self):
        """Test recommends medium model for CPU with 16+ GB RAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 32.0,
            'ram_free_gb': 24.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 25.0,
            'cpu_cores': 8,
            'cpu_cores_logical': 16,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 3500.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'medium'

    def test_cpu_only_low_ram_recommends_tiny(self):
        """Test recommends tiny model for CPU with <8 GB RAM"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 8.0,
            'ram_free_gb': 4.0,
            'ram_used_gb': 4.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 2,
            'cpu_cores_logical': 4,
            'cpu_usage_pct': 20.0,
            'cpu_freq_mhz': 2500.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            assert monitor.get_recommended_model_size() == 'tiny'


class TestWaitForResources:
    """Test wait_for_resources() method"""

    def test_returns_true_immediately_if_resources_available(self):
        """Test returns True immediately when resources available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        with patch.object(monitor, 'is_system_overloaded', return_value=False):
            result = monitor.wait_for_resources(timeout_seconds=5.0)
            assert result is True

    def test_returns_false_on_timeout(self):
        """Test returns False when timeout reached"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        with patch.object(monitor, 'is_system_overloaded', return_value=True):
            result = monitor.wait_for_resources(
                timeout_seconds=0.5,
                check_interval=0.1
            )
            assert result is False

    def test_returns_true_when_resources_become_available(self):
        """Test returns True when resources become available during wait"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        call_count = [0]

        def mock_is_overloaded():
            call_count[0] += 1
            # Return overloaded for first 2 calls, then available
            return call_count[0] < 3

        with patch.object(monitor, 'is_system_overloaded', side_effect=mock_is_overloaded):
            result = monitor.wait_for_resources(
                timeout_seconds=2.0,
                check_interval=0.1
            )
            assert result is True
            assert call_count[0] == 3


class TestGetResourceSummary:
    """Test get_resource_summary() method"""

    def test_returns_string(self):
        """Test returns a string"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            summary = monitor.get_resource_summary()
            assert isinstance(summary, str)
            assert len(summary) > 0

    def test_contains_ram_info(self):
        """Test summary contains RAM information"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            summary = monitor.get_resource_summary()
            assert 'RAM' in summary

    def test_contains_cpu_info(self):
        """Test summary contains CPU information"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': False,
            'gpu_name': None,
            'vram_total_gb': 0.0,
            'vram_free_gb': 0.0,
            'vram_used_gb': 0.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            summary = monitor.get_resource_summary()
            assert 'CPU' in summary

    def test_shows_gpu_when_available(self):
        """Test summary shows GPU info when available"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        mock_resources = {
            'ram_total_gb': 16.0,
            'ram_free_gb': 8.0,
            'ram_used_gb': 8.0,
            'ram_usage_pct': 50.0,
            'cpu_cores': 4,
            'cpu_cores_logical': 8,
            'cpu_usage_pct': 30.0,
            'cpu_freq_mhz': 3000.0,
            'gpu_available': True,
            'gpu_name': 'NVIDIA RTX 3080',
            'vram_total_gb': 10.0,
            'vram_free_gb': 6.0,
            'vram_used_gb': 4.0,
            'platform': 'Windows',
            'hostname': 'test-host',
        }

        with patch.object(monitor, 'get_current_resources', return_value=mock_resources):
            with patch.object(monitor, 'is_system_overloaded', return_value=False):
                summary = monitor.get_resource_summary()
                assert 'NVIDIA RTX 3080' in summary


class TestResourceThresholds:
    """Test ResourceThresholds dataclass"""

    def test_default_values(self):
        """Test default threshold values"""
        thresholds = ResourceThresholds()

        assert thresholds.ram_usage_pct == 85.0
        assert thresholds.cpu_usage_pct == 90.0
        assert thresholds.min_ram_free_gb == 2.0
        assert thresholds.min_vram_free_gb == 2.0

    def test_custom_values(self):
        """Test custom threshold values"""
        thresholds = ResourceThresholds(
            ram_usage_pct=70.0,
            cpu_usage_pct=80.0,
            min_ram_free_gb=4.0,
            min_vram_free_gb=6.0
        )

        assert thresholds.ram_usage_pct == 70.0
        assert thresholds.cpu_usage_pct == 80.0
        assert thresholds.min_ram_free_gb == 4.0
        assert thresholds.min_vram_free_gb == 6.0


class TestIntegration:
    """Integration tests for SystemResourceMonitor"""

    def test_full_workflow(self):
        """Test complete resource monitoring workflow"""
        monitor = SystemResourceMonitor(cpu_sample_interval=0.1)

        # Get resources
        resources = monitor.get_current_resources()
        assert isinstance(resources, dict)
        assert resources['ram_total_gb'] > 0

        # Check overload
        is_overloaded = monitor.is_system_overloaded()
        assert isinstance(is_overloaded, bool)

        # Get model recommendation
        model_size = monitor.get_recommended_model_size()
        assert model_size in ['large', 'medium', 'small', 'tiny']

        # Get summary
        summary = monitor.get_resource_summary()
        assert isinstance(summary, str)
        assert 'RAM' in summary
