#!/usr/bin/env python3
"""
Test dispatcher and channel implementations
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from insights_core.dispatcher import InsightDispatcher
from insights_core.channels import SlackChannel, EmailChannel, JiraChannel, WebhookChannel
from insights_core.channels.base import DispatchResult
from insights_core.models import Insight, InsightCategory, InsightSeverity


@pytest.fixture
def sample_insight():
    """Create sample insight for testing"""
    return Insight(
        id='test-insight-123',
        property='test://example.com',
        category=InsightCategory.RISK,
        title='Test Traffic Drop',
        description='Traffic dropped by 50% on test page',
        severity='high',
        confidence=0.85,
        entity_id='/test/page',
        entity_type='page',
        metrics={
            'gsc_clicks': 50,
            'gsc_clicks_change_wow': -50.0,
            'ga_conversions': 5
        },
        actions=['Investigate content changes', 'Check for technical issues'],
        source='AnomalyDetector',
        generated_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=7)
    )


@pytest.fixture
def dispatcher_config():
    """Basic dispatcher configuration"""
    return {
        'dry_run': True,  # Always dry-run in tests
        'max_retries': 3,
        'retry_delays': [0.1, 0.2, 0.3],  # Short delays for testing
        'channels': {
            'slack': {
                'enabled': True,
                'webhook_url': 'https://hooks.slack.com/test',
                'channel': '#test'
            },
            'email': {
                'enabled': True,
                'smtp_host': 'localhost',
                'smtp_port': 587,
                'from_email': 'test@example.com',
                'to_emails': ['recipient@example.com']
            }
        },
        'routing_rules': {
            'risk': {
                'high': ['slack', 'email'],
                'medium': ['email'],
                'low': []
            }
        }
    }


def test_dispatcher_initialization(dispatcher_config):
    """Test dispatcher initializes correctly"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    assert dispatcher.dry_run is True
    assert dispatcher.max_retries == 3
    assert 'slack' in dispatcher.channels
    assert 'email' in dispatcher.channels


def test_dispatcher_get_target_channels(dispatcher_config, sample_insight):
    """Test routing logic determines correct channels"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # High risk should go to slack + email
    channels = dispatcher._get_target_channels(sample_insight)
    
    assert 'slack' in channels
    assert 'email' in channels
    assert len(channels) == 2


def test_dispatcher_dispatch_single_insight(dispatcher_config, sample_insight):
    """Test dispatching single insight (happy path)"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    results = dispatcher.dispatch(sample_insight)
    
    # Should dispatch to 2 channels (slack + email)
    assert len(results) == 2
    assert 'slack' in results
    assert 'email' in results
    
    # Both should succeed (dry-run)
    assert results['slack'].success is True
    assert results['email'].success is True


def test_dispatcher_dispatch_batch(dispatcher_config, sample_insight):
    """Test dispatching multiple insights"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # Create 3 test insights
    insights = [sample_insight] * 3
    
    stats = dispatcher.dispatch_batch(insights)
    
    assert stats['total_insights'] == 3
    assert stats['total_dispatches'] == 6  # 3 insights × 2 channels
    assert stats['successes'] == 6
    assert stats['failures'] == 0


def test_dispatcher_low_severity_no_dispatch(dispatcher_config, sample_insight):
    """Test low severity insights don't dispatch"""
    sample_insight.severity = 'low'
    
    dispatcher = InsightDispatcher(dispatcher_config)
    results = dispatcher.dispatch(sample_insight)
    
    # Low severity configured to dispatch nowhere
    assert len(results) == 0


def test_dispatcher_test_routing(dispatcher_config, sample_insight):
    """Test routing decision explanation"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    routing_info = dispatcher.test_routing(sample_insight)
    
    assert routing_info['category'] == 'risk'
    assert routing_info['severity'] == 'high'
    assert 'slack' in routing_info['target_channels']
    assert 'email' in routing_info['target_channels']


def test_slack_channel_format_message(sample_insight):
    """Test Slack message formatting"""
    config = {
        'enabled': True,
        'webhook_url': 'https://hooks.slack.com/test',
        'dry_run': True
    }
    
    channel = SlackChannel(config)
    message = channel.format_message(sample_insight)
    
    assert 'text' in message
    assert 'blocks' in message
    assert 'Test Traffic Drop' in message['text']
    assert len(message['blocks']) > 0


def test_slack_channel_send_success(sample_insight):
    """Test Slack channel sends successfully (mocked)"""
    config = {
        'enabled': True,
        'webhook_url': 'https://hooks.slack.com/test',
        'dry_run': False
    }
    
    channel = SlackChannel(config)
    
    with patch('insights_core.channels.slack.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = channel.send(sample_insight)
        
        assert result.success is True
        assert result.channel == 'slack'
        mock_post.assert_called_once()


def test_slack_channel_send_failure(sample_insight):
    """Test Slack channel handles failure (failing path)"""
    config = {
        'enabled': True,
        'webhook_url': 'https://hooks.slack.com/test',
        'dry_run': False
    }
    
    channel = SlackChannel(config)
    
    with patch('insights_core.channels.slack.requests.post') as mock_post:
        mock_post.side_effect = Exception("Network error")
        
        result = channel.send(sample_insight)
        
        assert result.success is False
        assert 'Network error' in result.error


def test_email_channel_format_message(sample_insight):
    """Test email message formatting"""
    config = {
        'enabled': True,
        'smtp_host': 'localhost',
        'from_email': 'test@example.com',
        'to_emails': ['recipient@example.com'],
        'dry_run': True
    }
    
    channel = EmailChannel(config)
    message = channel.format_message(sample_insight)
    
    assert 'subject' in message
    assert 'html' in message
    assert 'Test Traffic Drop' in message['subject']
    assert '<html>' in message['html']


def test_email_channel_validate_config():
    """Test email config validation"""
    # Valid config
    config = {
        'enabled': True,
        'to_emails': ['test@example.com']
    }
    channel = EmailChannel(config)
    assert channel.validate_config() is True
    
    # Invalid config (no recipients)
    config = {
        'enabled': True,
        'to_emails': []
    }
    channel = EmailChannel(config)
    assert channel.validate_config() is False


def test_jira_channel_format_message(sample_insight):
    """Test Jira issue formatting"""
    config = {
        'enabled': True,
        'base_url': 'https://jira.example.com',
        'username': 'test',
        'api_token': 'token',
        'dry_run': True
    }
    
    channel = JiraChannel(config)
    issue = channel.format_message(sample_insight)
    
    assert 'fields' in issue
    assert issue['fields']['summary'] == 'Test Traffic Drop'
    assert issue['fields']['priority']['name'] == 'High'
    assert 'gsc-insight' in issue['fields']['labels']


def test_webhook_channel_format_message(sample_insight):
    """Test webhook payload formatting"""
    config = {
        'enabled': True,
        'url': 'https://webhook.example.com',
        'dry_run': True
    }
    
    channel = WebhookChannel(config)
    payload = channel.format_message(sample_insight)
    
    assert payload['id'] == 'test-insight-123'
    assert payload['title'] == 'Test Traffic Drop'
    assert payload['severity'] == 'high'
    assert payload['metrics']['gsc_clicks'] == 50


def test_dispatcher_retry_logic(dispatcher_config, sample_insight):
    """Test retry logic with exponential backoff"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # Mock channel that fails twice then succeeds
    mock_channel = Mock()
    mock_channel.validate_config.return_value = True
    
    call_count = [0]
    
    def side_effect_send(insight):
        call_count[0] += 1
        if call_count[0] < 3:
            return DispatchResult(
                success=False,
                channel='mock',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error='Temporary failure'
            )
        else:
            return DispatchResult(
                success=True,
                channel='mock',
                insight_id=insight.id,
                timestamp=datetime.utcnow()
            )
    
    mock_channel.send = side_effect_send
    
    result = dispatcher._send_with_retry(mock_channel, sample_insight)
    
    assert result.success is True
    assert result.retry_count == 2  # Failed twice before succeeding


def test_dispatcher_retry_exhausted(dispatcher_config, sample_insight):
    """Test all retries exhausted (failing path)"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # Mock channel that always fails
    mock_channel = Mock()
    mock_channel.validate_config.return_value = True
    mock_channel.send.return_value = DispatchResult(
        success=False,
        channel='mock',
        insight_id=sample_insight.id,
        timestamp=datetime.utcnow(),
        error='Persistent failure'
    )
    
    result = dispatcher._send_with_retry(mock_channel, sample_insight)
    
    assert result.success is False
    assert result.retry_count == 3  # Max retries


def test_dispatcher_channel_isolation(dispatcher_config, sample_insight):
    """Test that failure in one channel doesn't affect others"""
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # Make slack fail but email succeed (both in dry-run)
    with patch.object(dispatcher.channels['slack'], 'send') as mock_slack:
        mock_slack.return_value = DispatchResult(
            success=False,
            channel='slack',
            insight_id=sample_insight.id,
            timestamp=datetime.utcnow(),
            error='Slack failed'
        )
        
        results = dispatcher.dispatch(sample_insight)
        
        # Slack failed
        assert results['slack'].success is False
        
        # Email still succeeded (dry-run)
        assert results['email'].success is True


def test_dispatcher_disabled_channel(dispatcher_config, sample_insight):
    """Test disabled channels are skipped"""
    dispatcher_config['channels']['slack']['enabled'] = False
    
    dispatcher = InsightDispatcher(dispatcher_config)
    results = dispatcher.dispatch(sample_insight)
    
    # Should only dispatch to email (slack disabled)
    assert len(results) == 1
    assert 'email' in results
    assert 'slack' not in results


def test_dispatcher_invalid_channel_config(dispatcher_config, sample_insight):
    """Test invalid channel config is skipped gracefully"""
    dispatcher_config['channels']['slack']['webhook_url'] = None
    
    dispatcher = InsightDispatcher(dispatcher_config)
    
    # Slack should fail validation and be skipped
    results = dispatcher.dispatch(sample_insight)
    
    # Only email should dispatch
    assert len(results) == 1
    assert 'email' in results


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
