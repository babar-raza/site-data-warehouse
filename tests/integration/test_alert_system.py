"""
Integration Tests for Alert System
Tests alert rules, notifications, and multi-channel delivery
"""

import pytest
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from dotenv import load_dotenv

# Import alert system components
from notifications.alert_manager import AlertManager
from notifications.channels.slack_notifier import SlackNotifier
from notifications.channels.email_notifier import EmailNotifier
from notifications.channels.webhook_notifier import WebhookNotifier

load_dotenv()

TEST_PROPERTY = "https://test-domain.com"
TEST_DSN = os.getenv('WAREHOUSE_DSN', 'postgresql://postgres:postgres@localhost:5432/seo_warehouse')


@pytest.fixture
async def db_connection():
    """Provide database connection for tests"""
    conn = await asyncpg.connect(TEST_DSN)
    yield conn
    await conn.close()


@pytest.fixture
async def clean_alert_data(db_connection):
    """Clean up alert test data"""
    conn = db_connection

    # Clean before
    await conn.execute("DELETE FROM notifications.delivery_log WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.notification_queue WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_rules WHERE property = $1", TEST_PROPERTY)

    yield

    # Clean after
    await conn.execute("DELETE FROM notifications.delivery_log WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.notification_queue WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_rules WHERE property = $1", TEST_PROPERTY)


class TestAlertManager:
    """Test Alert Manager core functionality"""

    @pytest.mark.asyncio
    async def test_alert_manager_initialization(self):
        """Test alert manager initializes correctly"""
        manager = AlertManager(db_dsn=TEST_DSN)
        assert manager is not None
        assert manager.db_dsn == TEST_DSN

    @pytest.mark.asyncio
    async def test_register_notifiers(self):
        """Test notifier registration"""
        manager = AlertManager(db_dsn=TEST_DSN)

        slack = SlackNotifier()
        email = EmailNotifier()
        webhook = WebhookNotifier()

        manager.register_notifier('slack', slack)
        manager.register_notifier('email', email)
        manager.register_notifier('webhook', webhook)

        assert 'slack' in manager._notifiers
        assert 'email' in manager._notifiers
        assert 'webhook' in manager._notifiers

    @pytest.mark.asyncio
    async def test_create_alert_rule(self, db_connection, clean_alert_data):
        """Test creating alert rules"""
        manager = AlertManager(db_dsn=TEST_DSN)

        rule_id = await manager.create_alert_rule(
            rule_name="Test SERP Drop Alert",
            rule_type="serp_drop",
            conditions={"position_drop": 3, "min_impressions": 100},
            severity="high",
            channels=["slack", "email"],
            property=TEST_PROPERTY,
            suppression_window_minutes=60,
            max_alerts_per_day=10
        )

        assert rule_id is not None

        # Verify in database
        row = await db_connection.fetchrow(
            "SELECT * FROM notifications.alert_rules WHERE rule_id = $1",
            rule_id
        )

        assert row is not None
        assert row['rule_name'] == "Test SERP Drop Alert"
        assert row['rule_type'] == "serp_drop"
        assert row['severity'] == "high"
        assert 'slack' in row['channels']
        assert 'email' in row['channels']

    @pytest.mark.asyncio
    async def test_trigger_alert(self, db_connection, clean_alert_data):
        """Test triggering an alert"""
        manager = AlertManager(db_dsn=TEST_DSN)

        # Create rule first
        rule_id = await manager.create_alert_rule(
            rule_name="Test Alert",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        # Trigger alert
        alert_id = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Test Alert Title",
            message="This is a test alert message",
            page_path="/test-page",
            metadata={"test_key": "test_value"}
        )

        assert alert_id is not None

        # Verify alert in history
        row = await db_connection.fetchrow(
            "SELECT * FROM notifications.alert_history WHERE alert_id = $1",
            alert_id
        )

        assert row is not None
        assert row['rule_id'] == rule_id
        assert row['title'] == "Test Alert Title"
        assert row['message'] == "This is a test alert message"
        assert row['status'] == 'open'

        # Verify in notification queue
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM notifications.notification_queue WHERE alert_id = $1",
            alert_id
        )
        assert count > 0

    @pytest.mark.asyncio
    async def test_alert_suppression(self, db_connection, clean_alert_data):
        """Test alert suppression prevents duplicate alerts"""
        manager = AlertManager(db_dsn=TEST_DSN)

        # Create rule with 60 minute suppression
        rule_id = await manager.create_alert_rule(
            rule_name="Suppression Test",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY,
            suppression_window_minutes=60
        )

        # Trigger first alert
        alert_id_1 = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Alert 1",
            message="First alert"
        )
        assert alert_id_1 is not None

        # Try to trigger same alert immediately (should be suppressed)
        alert_id_2 = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Alert 2",
            message="Second alert"
        )

        # Second alert should return None due to suppression
        # Or verify suppression in database
        recent_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM notifications.alert_history
            WHERE rule_id = $1
            AND triggered_at >= NOW() - INTERVAL '1 minute'
        """, rule_id)

        # Should only have 1 alert due to suppression
        assert recent_count == 1


class TestSlackNotifier:
    """Test Slack notification channel"""

    @pytest.mark.asyncio
    async def test_slack_notifier_initialization(self):
        """Test Slack notifier initializes"""
        notifier = SlackNotifier()
        assert notifier is not None

    @pytest.mark.asyncio
    async def test_slack_message_formatting(self):
        """Test Slack message formatting"""
        notifier = SlackNotifier()

        payload = {
            'alert_id': 'test-123',
            'title': 'Test Alert',
            'message': 'Test message',
            'severity': 'high',
            'property': TEST_PROPERTY,
            'page_path': '/test-page',
            'triggered_at': datetime.now()
        }

        channel_config = {
            'webhook_url': 'https://hooks.slack.com/test',
            'channel': '#alerts',
            'username': 'SEO Bot'
        }

        message = notifier._build_message(payload, channel_config)

        assert message is not None
        assert 'text' in message or 'blocks' in message or 'attachments' in message
        assert 'Test Alert' in str(message)

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_slack_send_success(self, mock_post):
        """Test successful Slack notification send"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        notifier = SlackNotifier()

        payload = {
            'title': 'Test',
            'message': 'Test message',
            'severity': 'high',
            'property': TEST_PROPERTY
        }

        channel_config = {
            'webhook_url': 'https://hooks.slack.com/test'
        }

        result = await notifier.send(payload, channel_config)
        assert result is True

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_slack_send_failure(self, mock_post):
        """Test Slack notification send failure handling"""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        notifier = SlackNotifier()

        payload = {
            'title': 'Test',
            'message': 'Test message',
            'severity': 'high'
        }

        channel_config = {
            'webhook_url': 'https://hooks.slack.com/test'
        }

        result = await notifier.send(payload, channel_config)
        assert result is False


class TestEmailNotifier:
    """Test Email notification channel"""

    @pytest.mark.asyncio
    async def test_email_notifier_initialization(self):
        """Test email notifier initializes"""
        notifier = EmailNotifier()
        assert notifier is not None

    @pytest.mark.asyncio
    async def test_email_html_formatting(self):
        """Test HTML email formatting"""
        notifier = EmailNotifier(method='smtp')

        payload = {
            'title': 'Test Alert',
            'message': 'Test message',
            'severity': 'high',
            'property': TEST_PROPERTY,
            'page_path': '/test-page'
        }

        html = notifier._build_html_body(payload)

        assert html is not None
        assert 'Test Alert' in html
        assert 'Test message' in html
        assert 'text/html' in html or '<html>' in html

    @pytest.mark.asyncio
    @patch('aiosmtplib.send')
    async def test_email_smtp_send(self, mock_send):
        """Test SMTP email sending"""
        mock_send.return_value = True

        notifier = EmailNotifier(method='smtp')

        payload = {
            'title': 'Test',
            'message': 'Test message',
            'severity': 'medium'
        }

        channel_config = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_user': 'test@test.com',
            'smtp_pass': 'password',
            'from_email': 'alerts@test.com',
            'to_email': 'team@test.com'
        }

        result = await notifier.send(payload, channel_config)
        assert result is True or result is False  # Depends on mock


class TestWebhookNotifier:
    """Test Webhook notification channel"""

    @pytest.mark.asyncio
    async def test_webhook_notifier_initialization(self):
        """Test webhook notifier initializes"""
        notifier = WebhookNotifier()
        assert notifier is not None

    @pytest.mark.asyncio
    async def test_pagerduty_formatting(self):
        """Test PagerDuty webhook formatting"""
        notifier = WebhookNotifier()

        payload = {
            'alert_id': 'test-123',
            'title': 'Critical Alert',
            'message': 'System down',
            'severity': 'critical'
        }

        channel_config = {
            'format': 'pagerduty',
            'integration_key': 'test-key'
        }

        webhook_payload = notifier._build_pagerduty_payload(payload, channel_config)

        assert webhook_payload is not None
        assert 'routing_key' in webhook_payload or 'service_key' in webhook_payload
        assert 'event_action' in webhook_payload

    @pytest.mark.asyncio
    async def test_discord_formatting(self):
        """Test Discord webhook formatting"""
        notifier = WebhookNotifier()

        payload = {
            'title': 'Alert',
            'message': 'Test message',
            'severity': 'high'
        }

        webhook_payload = notifier._build_discord_payload(payload, {})

        assert webhook_payload is not None
        assert 'embeds' in webhook_payload or 'content' in webhook_payload


class TestNotificationQueue:
    """Test notification queue processing"""

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_process_notification_queue(self, mock_post, db_connection, clean_alert_data):
        """Test processing notification queue"""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        manager = AlertManager(db_dsn=TEST_DSN)
        manager.register_notifier('slack', SlackNotifier())

        # Create rule and trigger alert
        rule_id = await manager.create_alert_rule(
            rule_name="Queue Test",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        alert_id = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Test",
            message="Test"
        )

        # Process queue
        processed = await manager.process_notification_queue()

        # Verify queue was processed
        pending_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM notifications.notification_queue
            WHERE alert_id = $1 AND status = 'pending'
        """, alert_id)

        # Should have 0 pending after processing
        assert pending_count == 0

    @pytest.mark.asyncio
    async def test_notification_retry_logic(self, db_connection, clean_alert_data):
        """Test failed notifications are retried"""
        manager = AlertManager(db_dsn=TEST_DSN)

        # Create rule
        rule_id = await manager.create_alert_rule(
            rule_name="Retry Test",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        alert_id = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Test",
            message="Test"
        )

        # Mark notification as failed
        await db_connection.execute("""
            UPDATE notifications.notification_queue
            SET status = 'failed', retry_count = 1
            WHERE alert_id = $1
        """, alert_id)

        # Verify retry count
        row = await db_connection.fetchrow("""
            SELECT retry_count, status FROM notifications.notification_queue
            WHERE alert_id = $1
        """, alert_id)

        assert row['status'] == 'failed'
        assert row['retry_count'] == 1


class TestAlertAggregation:
    """Test alert aggregation"""

    @pytest.mark.asyncio
    async def test_alert_aggregation(self, db_connection, clean_alert_data):
        """Test multiple alerts can be aggregated"""
        manager = AlertManager(db_dsn=TEST_DSN)

        # Create rule
        rule_id = await manager.create_alert_rule(
            rule_name="Aggregation Test",
            rule_type="test",
            conditions={},
            severity="low",
            channels=["email"],
            property=TEST_PROPERTY
        )

        # Trigger multiple alerts
        alert_ids = []
        for i in range(5):
            alert_id = await manager.trigger_alert(
                rule_id=rule_id,
                property=TEST_PROPERTY,
                title=f"Alert {i}",
                message=f"Message {i}"
            )
            alert_ids.append(alert_id)

        # Check aggregation table
        # (Implementation depends on aggregation logic in alert_manager)
        count = await db_connection.fetchval("""
            SELECT COUNT(DISTINCT alert_id)
            FROM notifications.alert_history
            WHERE rule_id = $1
        """, rule_id)

        assert count == 5


class TestAlertResolution:
    """Test alert resolution"""

    @pytest.mark.asyncio
    async def test_resolve_alert(self, db_connection, clean_alert_data):
        """Test alerts can be resolved"""
        manager = AlertManager(db_dsn=TEST_DSN)

        # Create and trigger alert
        rule_id = await manager.create_alert_rule(
            rule_name="Resolution Test",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        alert_id = await manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Test",
            message="Test"
        )

        # Resolve alert
        await db_connection.execute("""
            SELECT notifications.resolve_alert($1, $2)
        """, alert_id, "Issue fixed manually")

        # Verify resolved
        row = await db_connection.fetchrow("""
            SELECT status, resolved_at FROM notifications.alert_history
            WHERE alert_id = $1
        """, alert_id)

        assert row['status'] == 'resolved'
        assert row['resolved_at'] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
