"""
Comprehensive tests for InsightDispatcher (MOCK MODE)

Tests dispatcher routing, retry logic, and batch operations using mocks.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import time

from insights_core.dispatcher import InsightDispatcher
from insights_core.channels.base import DispatchResult


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
    insight.confidence = 0.85
    return insight


@pytest.fixture
def mock_insight_critical():
    """Create a critical risk insight"""
    insight = Mock()
    insight.id = 'insight-critical'
    insight.title = 'Critical Issue'
    insight.description = 'Critical problem detected'
    insight.category = Mock(value='risk')
    insight.severity = 'critical'
    insight.property = 'sc-domain:example.com'
    return insight


@pytest.fixture
def mock_insight_low():
    """Create a low severity insight"""
    insight = Mock()
    insight.id = 'insight-low'
    insight.title = 'Low Priority'
    insight.description = 'Low priority issue'
    insight.category = Mock(value='opportunity')
    insight.severity = 'low'
    insight.property = 'sc-domain:example.com'
    return insight


@pytest.fixture
def basic_config():
    """Basic dispatcher configuration"""
    return {
        'dry_run': True,
        'max_retries': 3,
        'retry_delays': [1, 2, 4],
        'channels': {}
    }


@pytest.fixture
def config_with_channels():
    """Configuration with multiple channels"""
    return {
        'dry_run': True,
        'max_retries': 2,
        'channels': {
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test'
            },
            'jira': {
                'enabled': True,
                'url': 'https://jira.example.com',
                'project_key': 'TEST'
            },
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.example.com',
                'from_email': 'test@example.com'
            }
        }
    }


class TestInsightDispatcherInit:
    """Test InsightDispatcher initialization"""

    def test_init_with_basic_config(self, basic_config):
        """Test initialization with basic config"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)

            assert dispatcher.config == basic_config
            assert dispatcher.dry_run is True
            assert dispatcher.max_retries == 3
            assert dispatcher.retry_delays == [1, 2, 4]
            assert len(dispatcher.channels) == 0

    def test_init_with_channels(self, config_with_channels):
        """Test initialization with channel configs"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel') as MockJira, \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(config_with_channels)

            assert len(dispatcher.channels) == 3
            assert 'slack' in dispatcher.channels
            assert 'jira' in dispatcher.channels
            assert 'email' in dispatcher.channels
            MockSlack.assert_called_once()
            MockJira.assert_called_once()
            MockEmail.assert_called_once()

    def test_init_default_routing_rules(self, basic_config):
        """Test that default routing rules are loaded"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)

            assert dispatcher.routing_rules is not None
            assert 'risk' in dispatcher.routing_rules
            assert 'opportunity' in dispatcher.routing_rules
            assert 'critical' in dispatcher.routing_rules['risk']

    def test_init_custom_routing_rules(self, basic_config):
        """Test initialization with custom routing rules"""
        custom_rules = {
            'risk': {
                'critical': ['slack', 'email'],
                'high': ['slack']
            }
        }
        config = basic_config.copy()
        config['routing_rules'] = custom_rules

        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(config)

            assert dispatcher.routing_rules == custom_rules

    def test_init_dry_run_propagates_to_channels(self, config_with_channels):
        """Test that dry_run setting propagates to channels"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(config_with_channels)

            # Check that channel configs got dry_run set
            call_args = MockSlack.call_args[0][0]
            assert call_args['dry_run'] is True

    def test_init_defaults(self):
        """Test initialization with minimal config"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher({})

            assert dispatcher.dry_run is False
            assert dispatcher.max_retries == 3
            assert len(dispatcher.retry_delays) == 3


class TestGetTargetChannels:
    """Test _get_target_channels routing logic"""

    def test_get_target_channels_critical_risk(self, basic_config, mock_insight_critical):
        """Test routing for critical risk insight"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            channels = dispatcher._get_target_channels(mock_insight_critical)

            assert 'slack' in channels
            assert 'jira' in channels
            assert 'email' in channels

    def test_get_target_channels_high_risk(self, basic_config, mock_insight):
        """Test routing for high risk insight"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            channels = dispatcher._get_target_channels(mock_insight)

            assert 'slack' in channels
            assert 'email' in channels
            assert 'jira' not in channels  # Not in high risk default rules

    def test_get_target_channels_low_severity(self, basic_config, mock_insight_low):
        """Test routing for low severity insight"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            channels = dispatcher._get_target_channels(mock_insight_low)

            assert len(channels) == 0  # Low severity goes nowhere by default

    def test_get_target_channels_unknown_category(self, basic_config):
        """Test routing for unknown category"""
        insight = Mock()
        insight.category = Mock(value='unknown_category')
        insight.severity = 'high'

        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            channels = dispatcher._get_target_channels(insight)

            assert len(channels) == 0

    def test_get_target_channels_unknown_severity(self, basic_config):
        """Test routing for unknown severity"""
        insight = Mock()
        insight.category = Mock(value='risk')
        insight.severity = 'unknown_severity'

        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            channels = dispatcher._get_target_channels(insight)

            assert len(channels) == 0


class TestDispatch:
    """Test dispatch method"""

    def test_dispatch_no_target_channels(self, basic_config, mock_insight_low):
        """Test dispatch when no channels are targeted"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            results = dispatcher.dispatch(mock_insight_low)

            assert results == {}

    def test_dispatch_channel_not_initialized(self, basic_config, mock_insight):
        """Test dispatch when target channel is not initialized"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            # Insight targets slack, but no channels initialized
            results = dispatcher.dispatch(mock_insight)

            assert len(results) == 0

    def test_dispatch_invalid_channel_config(self, config_with_channels, mock_insight):
        """Test dispatch when channel config is invalid"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel') as MockJira, \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            # Mock channel that fails validation
            mock_channel = Mock()
            mock_channel.validate_config.return_value = False
            MockSlack.return_value = mock_channel
            MockJira.return_value = Mock()
            MockEmail.return_value = Mock()

            dispatcher = InsightDispatcher(config_with_channels)
            results = dispatcher.dispatch(mock_insight)

            # Slack should be skipped due to invalid config
            assert 'slack' not in results

    def test_dispatch_success(self, config_with_channels, mock_insight):
        """Test successful dispatch to channels"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel') as MockJira, \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            # Mock successful channels
            mock_slack = Mock()
            mock_slack.validate_config.return_value = True
            mock_slack.send.return_value = DispatchResult(
                success=True,
                channel='slack',
                insight_id='insight-123',
                timestamp=datetime.now()
            )

            mock_email = Mock()
            mock_email.validate_config.return_value = True
            mock_email.send.return_value = DispatchResult(
                success=True,
                channel='email',
                insight_id='insight-123',
                timestamp=datetime.now()
            )

            MockSlack.return_value = mock_slack
            MockEmail.return_value = mock_email
            MockJira.return_value = Mock()

            dispatcher = InsightDispatcher(config_with_channels)
            results = dispatcher.dispatch(mock_insight)

            assert 'slack' in results
            assert 'email' in results
            assert results['slack'].success is True
            assert results['email'].success is True

    def test_dispatch_with_retry(self, config_with_channels, mock_insight):
        """Test dispatch with retry logic"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'), \
             patch('time.sleep'):  # Mock sleep to speed up test

            # Mock channel that fails first, then succeeds
            mock_channel = Mock()
            mock_channel.validate_config.return_value = True
            mock_channel.send.side_effect = [
                DispatchResult(
                    success=False,
                    channel='slack',
                    insight_id='insight-123',
                    timestamp=datetime.now(),
                    error='Temporary failure'
                ),
                DispatchResult(
                    success=True,
                    channel='slack',
                    insight_id='insight-123',
                    timestamp=datetime.now()
                )
            ]

            MockSlack.return_value = mock_channel

            dispatcher = InsightDispatcher(config_with_channels)
            results = dispatcher.dispatch(mock_insight)

            assert results['slack'].success is True
            assert results['slack'].retry_count == 1
            assert mock_channel.send.call_count == 2


class TestSendWithRetry:
    """Test _send_with_retry method"""

    def test_send_with_retry_immediate_success(self, basic_config, mock_insight):
        """Test send succeeds on first attempt"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_channel = Mock()
            mock_channel.send.return_value = DispatchResult(
                success=True,
                channel='test',
                insight_id='insight-123',
                timestamp=datetime.now()
            )

            dispatcher = InsightDispatcher(basic_config)
            result = dispatcher._send_with_retry(mock_channel, mock_insight)

            assert result.success is True
            assert result.retry_count == 0
            assert mock_channel.send.call_count == 1

    def test_send_with_retry_all_attempts_fail(self, basic_config, mock_insight):
        """Test all retry attempts fail"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'), \
             patch('time.sleep'):

            mock_channel = Mock()
            mock_channel.send.return_value = DispatchResult(
                success=False,
                channel='test',
                insight_id='insight-123',
                timestamp=datetime.now(),
                error='Persistent failure'
            )

            dispatcher = InsightDispatcher(basic_config)
            result = dispatcher._send_with_retry(mock_channel, mock_insight)

            assert result.success is False
            assert mock_channel.send.call_count == 4  # 1 initial + 3 retries

    def test_send_with_retry_succeeds_on_second_attempt(self, basic_config, mock_insight):
        """Test send succeeds on second attempt"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'), \
             patch('time.sleep') as mock_sleep:

            mock_channel = Mock()
            mock_channel.send.side_effect = [
                DispatchResult(
                    success=False,
                    channel='test',
                    insight_id='insight-123',
                    timestamp=datetime.now(),
                    error='First attempt failed'
                ),
                DispatchResult(
                    success=True,
                    channel='test',
                    insight_id='insight-123',
                    timestamp=datetime.now()
                )
            ]

            dispatcher = InsightDispatcher(basic_config)
            result = dispatcher._send_with_retry(mock_channel, mock_insight)

            assert result.success is True
            assert result.retry_count == 1
            assert mock_channel.send.call_count == 2
            mock_sleep.assert_called_once_with(1)  # First retry delay


class TestDispatchBatch:
    """Test dispatch_batch method"""

    def test_dispatch_batch_empty_list(self, basic_config):
        """Test dispatching empty batch"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            stats = dispatcher.dispatch_batch([])

            assert stats['total_insights'] == 0
            assert stats['total_dispatches'] == 0
            assert stats['successes'] == 0
            assert stats['failures'] == 0

    def test_dispatch_batch_single_insight(self, config_with_channels, mock_insight):
        """Test dispatching batch with single insight"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_slack = Mock()
            mock_slack.validate_config.return_value = True
            mock_slack.send.return_value = DispatchResult(
                success=True, channel='slack',
                insight_id='insight-123', timestamp=datetime.now()
            )

            mock_email = Mock()
            mock_email.validate_config.return_value = True
            mock_email.send.return_value = DispatchResult(
                success=True, channel='email',
                insight_id='insight-123', timestamp=datetime.now()
            )

            MockSlack.return_value = mock_slack
            MockEmail.return_value = mock_email

            dispatcher = InsightDispatcher(config_with_channels)
            stats = dispatcher.dispatch_batch([mock_insight])

            assert stats['total_insights'] == 1
            assert stats['successes'] == 2  # slack + email
            assert stats['failures'] == 0
            assert 'duration_seconds' in stats

    def test_dispatch_batch_multiple_insights(self, config_with_channels, mock_insight, mock_insight_critical):
        """Test dispatching batch with multiple insights"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel') as MockJira, \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_slack = Mock()
            mock_slack.validate_config.return_value = True
            mock_slack.send.return_value = DispatchResult(
                success=True, channel='slack',
                insight_id='test', timestamp=datetime.now()
            )

            mock_jira = Mock()
            mock_jira.validate_config.return_value = True
            mock_jira.send.return_value = DispatchResult(
                success=True, channel='jira',
                insight_id='test', timestamp=datetime.now()
            )

            mock_email = Mock()
            mock_email.validate_config.return_value = True
            mock_email.send.return_value = DispatchResult(
                success=True, channel='email',
                insight_id='test', timestamp=datetime.now()
            )

            MockSlack.return_value = mock_slack
            MockJira.return_value = mock_jira
            MockEmail.return_value = mock_email

            dispatcher = InsightDispatcher(config_with_channels)
            stats = dispatcher.dispatch_batch([mock_insight, mock_insight_critical])

            assert stats['total_insights'] == 2
            assert stats['successes'] > 0

    def test_dispatch_batch_with_failures(self, config_with_channels, mock_insight):
        """Test batch dispatch with some failures"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_slack = Mock()
            mock_slack.validate_config.return_value = True
            mock_slack.send.return_value = DispatchResult(
                success=False, channel='slack',
                insight_id='insight-123', timestamp=datetime.now(),
                error='Failed to send'
            )

            mock_email = Mock()
            mock_email.validate_config.return_value = True
            mock_email.send.return_value = DispatchResult(
                success=True, channel='email',
                insight_id='insight-123', timestamp=datetime.now()
            )

            MockSlack.return_value = mock_slack
            MockEmail.return_value = mock_email

            dispatcher = InsightDispatcher(config_with_channels)
            stats = dispatcher.dispatch_batch([mock_insight])

            assert stats['successes'] == 1
            assert stats['failures'] == 1


class TestDispatchRecentInsights:
    """Test dispatch_recent_insights method"""

    def test_dispatch_recent_insights_no_insights(self, basic_config):
        """Test dispatching recent when no insights found"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_repo = Mock()
            mock_repo.query_recent.return_value = []

            dispatcher = InsightDispatcher(basic_config)
            stats = dispatcher.dispatch_recent_insights(mock_repo, hours=24)

            assert stats['total_insights'] == 0
            mock_repo.query_recent.assert_called_once_with(hours=24, property=None)

    def test_dispatch_recent_insights_with_property_filter(self, basic_config):
        """Test dispatching recent with property filter"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_repo = Mock()
            mock_repo.query_recent.return_value = []

            dispatcher = InsightDispatcher(basic_config)
            dispatcher.dispatch_recent_insights(
                mock_repo,
                hours=48,
                property='sc-domain:example.com'
            )

            mock_repo.query_recent.assert_called_once_with(
                hours=48,
                property='sc-domain:example.com'
            )

    def test_dispatch_recent_insights_with_results(self, config_with_channels, mock_insight):
        """Test dispatching recent insights with results"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_slack = Mock()
            mock_slack.validate_config.return_value = True
            mock_slack.send.return_value = DispatchResult(
                success=True, channel='slack',
                insight_id='insight-123', timestamp=datetime.now()
            )

            mock_email = Mock()
            mock_email.validate_config.return_value = True
            mock_email.send.return_value = DispatchResult(
                success=True, channel='email',
                insight_id='insight-123', timestamp=datetime.now()
            )

            MockSlack.return_value = mock_slack
            MockEmail.return_value = mock_email

            mock_repo = Mock()
            mock_repo.query_recent.return_value = [mock_insight]

            dispatcher = InsightDispatcher(config_with_channels)
            stats = dispatcher.dispatch_recent_insights(mock_repo, hours=24)

            assert stats['total_insights'] == 1
            assert stats['successes'] > 0


class TestTestRouting:
    """Test test_routing method"""

    def test_test_routing_critical_risk(self, config_with_channels, mock_insight_critical):
        """Test routing analysis for critical risk"""
        with patch('insights_core.dispatcher.SlackChannel') as MockSlack, \
             patch('insights_core.dispatcher.JiraChannel') as MockJira, \
             patch('insights_core.dispatcher.EmailChannel') as MockEmail, \
             patch('insights_core.dispatcher.WebhookChannel'):

            mock_channel = Mock()
            mock_channel.validate_config.return_value = True
            MockSlack.return_value = mock_channel
            MockJira.return_value = mock_channel
            MockEmail.return_value = mock_channel

            dispatcher = InsightDispatcher(config_with_channels)
            result = dispatcher.test_routing(mock_insight_critical)

            assert result['insight_id'] == 'insight-critical'
            assert result['category'] == 'risk'
            assert result['severity'] == 'critical'
            assert 'slack' in result['target_channels']
            assert 'jira' in result['target_channels']
            assert 'email' in result['target_channels']
            assert 'available_channels' in result
            assert 'configured_channels' in result

    def test_test_routing_structure(self, basic_config, mock_insight):
        """Test structure of routing test result"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            result = dispatcher.test_routing(mock_insight)

            assert 'insight_id' in result
            assert 'insight_title' in result
            assert 'category' in result
            assert 'severity' in result
            assert 'target_channels' in result
            assert 'routing_rule' in result
            assert 'available_channels' in result
            assert 'configured_channels' in result

    def test_test_routing_low_severity(self, basic_config, mock_insight_low):
        """Test routing for low severity insight"""
        with patch('insights_core.dispatcher.SlackChannel'), \
             patch('insights_core.dispatcher.JiraChannel'), \
             patch('insights_core.dispatcher.EmailChannel'), \
             patch('insights_core.dispatcher.WebhookChannel'):

            dispatcher = InsightDispatcher(basic_config)
            result = dispatcher.test_routing(mock_insight_low)

            assert len(result['target_channels']) == 0  # Low severity goes nowhere
