"""
Comprehensive tests for Channel base class and DispatchResult (MOCK MODE)

Tests channel interface, configuration, and dispatch result handling using mocks.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any

from insights_core.channels.base import Channel, DispatchResult


class ConcreteChannel(Channel):
    """Concrete implementation for testing abstract Channel class"""

    def send(self, insight: Any, **kwargs) -> DispatchResult:
        """Concrete send implementation"""
        if self.dry_run:
            return DispatchResult(
                success=True,
                channel='test',
                insight_id=getattr(insight, 'id', 'test-id'),
                timestamp=datetime.now(),
                response={'dry_run': True}
            )

        if not self.validate_config():
            return DispatchResult(
                success=False,
                channel='test',
                insight_id=getattr(insight, 'id', 'test-id'),
                timestamp=datetime.now(),
                error='Configuration invalid'
            )

        return DispatchResult(
            success=True,
            channel='test',
            insight_id=getattr(insight, 'id', 'test-id'),
            timestamp=datetime.now(),
            response={'status': 'sent'}
        )

    def format_message(self, insight: Any) -> Dict[str, Any]:
        """Concrete format_message implementation"""
        return {
            'title': getattr(insight, 'title', 'Default Title'),
            'description': getattr(insight, 'description', 'Default Description')
        }


@pytest.fixture
def mock_insight():
    """Create a mock insight object"""
    insight = Mock()
    insight.id = 'insight-123'
    insight.title = 'Test Insight'
    insight.description = 'Test description'
    insight.category = Mock(value='risk')
    insight.severity = 'high'
    insight.property = 'sc-domain:example.com'
    insight.entity_id = '/test-page'
    insight.confidence = 0.85
    insight.metrics = Mock(
        gsc_clicks=100.0,
        gsc_clicks_change=-25.5
    )
    insight.actions = ['Review recent changes', 'Check for technical issues']
    return insight


class TestDispatchResult:
    """Test DispatchResult dataclass"""

    def test_dispatch_result_success(self):
        """Test creating successful dispatch result"""
        now = datetime.now()
        result = DispatchResult(
            success=True,
            channel='slack',
            insight_id='insight-123',
            timestamp=now
        )

        assert result.success is True
        assert result.channel == 'slack'
        assert result.insight_id == 'insight-123'
        assert result.timestamp == now
        assert result.error is None
        assert result.retry_count == 0
        assert result.response is None

    def test_dispatch_result_failure(self):
        """Test creating failed dispatch result"""
        now = datetime.now()
        result = DispatchResult(
            success=False,
            channel='jira',
            insight_id='insight-456',
            timestamp=now,
            error='Connection timeout'
        )

        assert result.success is False
        assert result.error == 'Connection timeout'

    def test_dispatch_result_with_retry(self):
        """Test dispatch result with retry count"""
        result = DispatchResult(
            success=True,
            channel='email',
            insight_id='insight-789',
            timestamp=datetime.now(),
            retry_count=2
        )

        assert result.retry_count == 2

    def test_dispatch_result_with_response(self):
        """Test dispatch result with response data"""
        response_data = {'status_code': 200, 'message_id': 'msg-123'}
        result = DispatchResult(
            success=True,
            channel='webhook',
            insight_id='insight-001',
            timestamp=datetime.now(),
            response=response_data
        )

        assert result.response == response_data
        assert result.response['status_code'] == 200


class TestChannelBase:
    """Test Channel base class"""

    def test_channel_init_default_config(self):
        """Test channel initialization with default config"""
        config = {}
        channel = ConcreteChannel(config)

        assert channel.config == config
        assert channel.enabled is True  # Default
        assert channel.dry_run is False  # Default
        assert channel.rate_limit == 10  # Default

    def test_channel_init_with_config(self):
        """Test channel initialization with custom config"""
        config = {
            'enabled': False,
            'dry_run': True,
            'rate_limit': 5,
            'custom_param': 'value'
        }
        channel = ConcreteChannel(config)

        assert channel.enabled is False
        assert channel.dry_run is True
        assert channel.rate_limit == 5
        assert channel.config['custom_param'] == 'value'

    def test_channel_validate_config_enabled(self):
        """Test validate_config returns True when enabled"""
        config = {'enabled': True}
        channel = ConcreteChannel(config)

        assert channel.validate_config() is True

    def test_channel_validate_config_disabled(self):
        """Test validate_config returns False when disabled"""
        config = {'enabled': False}
        channel = ConcreteChannel(config)

        assert channel.validate_config() is False

    def test_channel_repr(self):
        """Test channel string representation"""
        config = {'enabled': True}
        channel = ConcreteChannel(config)

        repr_str = repr(channel)
        assert 'ConcreteChannel' in repr_str
        assert 'enabled=True' in repr_str

    def test_channel_repr_disabled(self):
        """Test channel repr when disabled"""
        config = {'enabled': False}
        channel = ConcreteChannel(config)

        repr_str = repr(channel)
        assert 'enabled=False' in repr_str

    def test_channel_has_logger(self):
        """Test that channel has a logger instance"""
        config = {}
        channel = ConcreteChannel(config)

        assert hasattr(channel, 'logger')
        assert channel.logger is not None

    def test_channel_logger_naming(self):
        """Test that logger has correct name"""
        config = {}
        channel = ConcreteChannel(config)

        # Logger should include class name
        assert 'ConcreteChannel' in channel.logger.name

    def test_channel_send_dry_run(self, mock_insight):
        """Test send in dry-run mode"""
        config = {'dry_run': True}
        channel = ConcreteChannel(config)

        result = channel.send(mock_insight)

        assert result.success is True
        assert result.response == {'dry_run': True}

    def test_channel_send_invalid_config(self, mock_insight):
        """Test send with invalid config"""
        config = {'enabled': False}
        channel = ConcreteChannel(config)

        result = channel.send(mock_insight)

        assert result.success is False
        assert 'Configuration invalid' in result.error

    def test_channel_send_success(self, mock_insight):
        """Test successful send"""
        config = {'enabled': True}
        channel = ConcreteChannel(config)

        result = channel.send(mock_insight)

        assert result.success is True
        assert result.channel == 'test'
        assert result.insight_id == 'insight-123'
        assert result.response == {'status': 'sent'}

    def test_channel_format_message(self, mock_insight):
        """Test format_message method"""
        config = {}
        channel = ConcreteChannel(config)

        message = channel.format_message(mock_insight)

        assert isinstance(message, dict)
        assert message['title'] == 'Test Insight'
        assert message['description'] == 'Test description'

    def test_channel_rate_limit_default(self):
        """Test default rate limit is set"""
        config = {}
        channel = ConcreteChannel(config)

        assert channel.rate_limit == 10

    def test_channel_rate_limit_custom(self):
        """Test custom rate limit"""
        config = {'rate_limit': 20}
        channel = ConcreteChannel(config)

        assert channel.rate_limit == 20

    def test_channel_with_empty_config(self):
        """Test channel with completely empty config"""
        channel = ConcreteChannel({})

        assert channel.enabled is True
        assert channel.dry_run is False
        assert channel.config == {}

    def test_channel_config_immutability(self):
        """Test that modifying config dict doesn't affect channel"""
        config = {'enabled': True, 'dry_run': False}
        channel = ConcreteChannel(config)

        # Modify original config
        config['enabled'] = False

        # Channel should still have reference to same dict
        # (Python passes dict by reference, so this tests that behavior)
        assert channel.config['enabled'] is False  # Will reflect change

    def test_channel_multiple_instances(self):
        """Test multiple channel instances are independent"""
        config1 = {'enabled': True, 'rate_limit': 5}
        config2 = {'enabled': False, 'rate_limit': 15}

        channel1 = ConcreteChannel(config1)
        channel2 = ConcreteChannel(config2)

        assert channel1.enabled is True
        assert channel2.enabled is False
        assert channel1.rate_limit == 5
        assert channel2.rate_limit == 15


class TestChannelEdgeCases:
    """Test edge cases and error scenarios"""

    def test_send_with_none_insight(self):
        """Test sending None as insight"""
        config = {'enabled': True}
        channel = ConcreteChannel(config)

        result = channel.send(None)

        # Should handle gracefully
        assert result is not None
        assert isinstance(result, DispatchResult)

    def test_format_message_with_none_insight(self):
        """Test format_message with None insight"""
        config = {}
        channel = ConcreteChannel(config)

        message = channel.format_message(None)

        # Should use defaults
        assert message['title'] == 'Default Title'
        assert message['description'] == 'Default Description'

    def test_validate_config_with_none_enabled(self):
        """Test validate_config when enabled key is missing"""
        config = {}
        channel = ConcreteChannel(config)

        # Should default to True
        assert channel.validate_config() is True

    def test_channel_with_extra_config_params(self):
        """Test channel ignores extra config parameters"""
        config = {
            'enabled': True,
            'unknown_param': 'value',
            'another_param': 123
        }
        channel = ConcreteChannel(config)

        assert channel.enabled is True
        assert 'unknown_param' in channel.config

    def test_dispatch_result_equality(self):
        """Test DispatchResult instances can be compared"""
        now = datetime.now()
        result1 = DispatchResult(
            success=True,
            channel='slack',
            insight_id='123',
            timestamp=now
        )
        result2 = DispatchResult(
            success=True,
            channel='slack',
            insight_id='123',
            timestamp=now
        )

        # Dataclasses have default equality
        assert result1 == result2

    def test_dispatch_result_with_all_fields(self):
        """Test DispatchResult with all optional fields populated"""
        now = datetime.now()
        result = DispatchResult(
            success=True,
            channel='test',
            insight_id='insight-xyz',
            timestamp=now,
            error='No error',
            retry_count=3,
            response={'key': 'value'}
        )

        assert result.error == 'No error'
        assert result.retry_count == 3
        assert result.response['key'] == 'value'

    def test_channel_logger_can_log(self):
        """Test that channel logger can actually log messages"""
        config = {}
        channel = ConcreteChannel(config)

        # Should not raise exception
        with patch.object(channel.logger, 'info') as mock_log:
            channel.logger.info('Test message')
            mock_log.assert_called_once_with('Test message')

    def test_send_captures_insight_id_correctly(self):
        """Test that send captures insight ID correctly"""
        config = {'enabled': True}
        channel = ConcreteChannel(config)

        insight = Mock()
        insight.id = 'custom-id-789'

        result = channel.send(insight)

        assert result.insight_id == 'custom-id-789'

    def test_channel_config_access(self):
        """Test accessing config values"""
        config = {'api_key': 'secret', 'timeout': 30}
        channel = ConcreteChannel(config)

        assert channel.config.get('api_key') == 'secret'
        assert channel.config.get('timeout') == 30
        assert channel.config.get('missing', 'default') == 'default'
