"""
Slack Notifier
==============
Send rich notifications to Slack via webhooks.

Features:
- Webhook-based messaging (no OAuth required)
- Rich formatting with blocks
- Severity-based colors
- Action buttons
- Thread support
"""
import asyncio
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Send notifications to Slack via webhooks
    """

    SEVERITY_COLORS = {
        'low': '#36a64f',      # Green
        'medium': '#ff9900',   # Orange
        'high': '#ff0000',     # Red
        'critical': '#8b0000'  # Dark Red
    }

    SEVERITY_EMOJIS = {
        'low': ':information_source:',
        'medium': ':warning:',
        'high': ':rotating_light:',
        'critical': ':fire:'
    }

    def __init__(self, default_webhook_url: str = None):
        """
        Initialize Slack notifier

        Args:
            default_webhook_url: Default webhook URL if not provided in config
        """
        self.default_webhook_url = default_webhook_url
        logger.info("SlackNotifier initialized")

    async def send(
        self,
        payload: Dict,
        channel_config: Dict
    ) -> bool:
        """
        Send notification to Slack

        Args:
            payload: Alert payload with title, message, severity, etc.
            channel_config: Slack configuration (webhook_url, channel, etc.)

        Returns:
            True if sent successfully
        """
        try:
            # Get webhook URL
            webhook_url = channel_config.get('webhook_url', self.default_webhook_url)

            if not webhook_url:
                logger.error("No Slack webhook URL configured")
                return False

            # Build Slack message
            slack_message = self._build_message(payload, channel_config)

            # Send to Slack
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=slack_message)

            if response.status_code == 200:
                logger.info(f"Slack notification sent: {payload.get('title')}")
                return True
            else:
                logger.error(f"Slack API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
            return False

    def _build_message(
        self,
        payload: Dict,
        config: Dict
    ) -> Dict:
        """
        Build Slack message with rich formatting

        Args:
            payload: Alert payload
            config: Channel configuration

        Returns:
            Slack message dict
        """
        title = payload.get('title', 'SEO Alert')
        message = payload.get('message', '')
        severity = payload.get('severity', 'medium')
        property_url = payload.get('property', '')
        metadata = payload.get('metadata', {})
        alert_id = payload.get('alert_id', '')

        # Get color and emoji for severity
        color = self.SEVERITY_COLORS.get(severity, '#808080')
        emoji = self.SEVERITY_EMOJIS.get(severity, ':bell:')

        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        # Add metadata as context
        if metadata:
            context_elements = []

            # Add property
            if property_url:
                context_elements.append({
                    "type": "mrkdwn",
                    "text": f"*Property:* {property_url}"
                })

            # Add severity
            context_elements.append({
                "type": "mrkdwn",
                "text": f"*Severity:* {severity.upper()}"
            })

            if context_elements:
                blocks.append({
                    "type": "context",
                    "elements": context_elements
                })

        # Add action buttons
        actions = []

        if alert_id:
            # Resolve button (would need backend endpoint)
            actions.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "✓ Resolve",
                    "emoji": True
                },
                "value": f"resolve_{alert_id}",
                "action_id": f"resolve_{alert_id}",
                "style": "primary"
            })

            # False positive button
            actions.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "False Positive",
                    "emoji": True
                },
                "value": f"false_positive_{alert_id}",
                "action_id": f"false_positive_{alert_id}",
                "style": "danger"
            })

        if actions:
            blocks.append({
                "type": "actions",
                "elements": actions
            })

        # Build final message
        slack_message = {
            "blocks": blocks,
            "attachments": [
                {
                    "color": color,
                    "fallback": title,
                    "footer": "SEO Intelligence Platform",
                    "ts": int(payload.get('timestamp', 0)) or None
                }
            ]
        }

        # Add channel override if specified
        if config.get('channel'):
            slack_message['channel'] = config['channel']

        return slack_message

    async def send_simple(
        self,
        webhook_url: str,
        text: str,
        channel: str = None
    ) -> bool:
        """
        Send a simple text message to Slack

        Args:
            webhook_url: Slack webhook URL
            text: Message text
            channel: Channel to post to (optional)

        Returns:
            True if sent successfully
        """
        try:
            message = {"text": text}

            if channel:
                message['channel'] = channel

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=message)

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Error sending simple Slack message: {e}")
            return False

    async def send_test_notification(
        self,
        webhook_url: str,
        channel: str = None
    ) -> bool:
        """
        Send a test notification

        Args:
            webhook_url: Slack webhook URL
            channel: Channel to post to (optional)

        Returns:
            True if sent successfully
        """
        payload = {
            'title': 'Test Alert',
            'message': 'This is a test notification from the SEO Intelligence Platform.',
            'severity': 'low',
            'property': 'https://example.com',
            'metadata': {}
        }

        config = {'webhook_url': webhook_url}
        if channel:
            config['channel'] = channel

        return await self.send(payload, config)


# Synchronous wrapper
def send_slack_notification_sync(payload: Dict, config: Dict) -> bool:
    """Synchronous wrapper for sending Slack notifications"""
    notifier = SlackNotifier()
    return asyncio.run(notifier.send(payload, config))


__all__ = ['SlackNotifier']
