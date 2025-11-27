"""
Webhook Notifier
================
Send notifications via generic HTTP webhooks.

Supports:
- Custom webhook URLs
- Custom headers (authorization, etc.)
- Payload templating
- Retry logic
- PagerDuty, Discord, MS Teams formats
"""
import asyncio
import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """
    Send notifications via HTTP webhooks
    """

    def __init__(self):
        """Initialize Webhook notifier"""
        logger.info("WebhookNotifier initialized")

    async def send(
        self,
        payload: Dict,
        channel_config: Dict
    ) -> bool:
        """
        Send webhook notification

        Args:
            payload: Alert payload
            channel_config: Webhook configuration (url, headers, format)

        Returns:
            True if sent successfully
        """
        try:
            webhook_url = channel_config.get('url')

            if not webhook_url:
                logger.error("No webhook URL configured")
                return False

            # Get webhook format
            webhook_format = channel_config.get('format', 'generic')

            # Build payload based on format
            if webhook_format == 'pagerduty':
                webhook_payload = self._build_pagerduty_payload(payload, channel_config)
            elif webhook_format == 'discord':
                webhook_payload = self._build_discord_payload(payload)
            elif webhook_format == 'teams':
                webhook_payload = self._build_teams_payload(payload)
            else:  # generic
                webhook_payload = self._build_generic_payload(payload)

            # Get headers
            headers = channel_config.get('headers', {})
            headers.setdefault('Content-Type', 'application/json')

            # Send webhook
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=webhook_payload,
                    headers=headers
                )

            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook sent successfully: {webhook_format}")
                return True
            else:
                logger.error(f"Webhook error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending webhook: {e}")
            return False

    def _build_generic_payload(self, payload: Dict) -> Dict:
        """Build generic webhook payload"""
        return {
            'alert_id': payload.get('alert_id'),
            'title': payload.get('title'),
            'message': payload.get('message'),
            'severity': payload.get('severity'),
            'property': payload.get('property'),
            'metadata': payload.get('metadata', {}),
            'timestamp': payload.get('timestamp')
        }

    def _build_pagerduty_payload(
        self,
        payload: Dict,
        config: Dict
    ) -> Dict:
        """
        Build PagerDuty Events API v2 payload

        Docs: https://developer.pagerduty.com/docs/ZG9jOjExMDI5NTgw-events-api-v2-overview
        """
        routing_key = config.get('routing_key', config.get('integration_key'))

        if not routing_key:
            logger.warning("No PagerDuty routing_key configured")

        severity_map = {
            'low': 'info',
            'medium': 'warning',
            'high': 'error',
            'critical': 'critical'
        }

        severity = payload.get('severity', 'medium')

        return {
            'routing_key': routing_key,
            'event_action': 'trigger',
            'payload': {
                'summary': payload.get('title', 'SEO Alert'),
                'source': payload.get('property', 'seo-platform'),
                'severity': severity_map.get(severity, 'warning'),
                'custom_details': {
                    'message': payload.get('message'),
                    'metadata': payload.get('metadata', {})
                }
            },
            'dedup_key': payload.get('alert_id', ''),
            'links': [
                {
                    'href': payload.get('property', ''),
                    'text': 'View Property'
                }
            ]
        }

    def _build_discord_payload(self, payload: Dict) -> Dict:
        """
        Build Discord webhook payload

        Docs: https://discord.com/developers/docs/resources/webhook
        """
        severity_colors = {
            'low': 3066993,      # Green
            'medium': 16776960,  # Orange
            'high': 16711680,    # Red
            'critical': 9109504  # Dark Red
        }

        severity = payload.get('severity', 'medium')
        color = severity_colors.get(severity, 8421504)

        return {
            'embeds': [
                {
                    'title': payload.get('title', 'SEO Alert'),
                    'description': payload.get('message', ''),
                    'color': color,
                    'fields': [
                        {
                            'name': 'Property',
                            'value': payload.get('property', 'N/A'),
                            'inline': True
                        },
                        {
                            'name': 'Severity',
                            'value': severity.upper(),
                            'inline': True
                        }
                    ],
                    'footer': {
                        'text': 'SEO Intelligence Platform'
                    },
                    'timestamp': payload.get('timestamp')
                }
            ]
        }

    def _build_teams_payload(self, payload: Dict) -> Dict:
        """
        Build Microsoft Teams webhook payload

        Docs: https://docs.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/connectors-using
        """
        severity_colors = {
            'low': '36a64f',
            'medium': 'ff9900',
            'high': 'ff0000',
            'critical': '8b0000'
        }

        severity = payload.get('severity', 'medium')
        color = severity_colors.get(severity, '808080')

        return {
            '@type': 'MessageCard',
            '@context': 'https://schema.org/extensions',
            'summary': payload.get('title', 'SEO Alert'),
            'themeColor': color,
            'title': payload.get('title', 'SEO Alert'),
            'sections': [
                {
                    'activityTitle': f"**Severity**: {severity.upper()}",
                    'activitySubtitle': payload.get('property', ''),
                    'text': payload.get('message', ''),
                    'facts': [
                        {
                            'name': key,
                            'value': str(value)
                        }
                        for key, value in payload.get('metadata', {}).items()
                    ]
                }
            ],
            'potentialAction': [
                {
                    '@type': 'OpenUri',
                    'name': 'View Property',
                    'targets': [
                        {
                            'os': 'default',
                            'uri': payload.get('property', '')
                        }
                    ]
                }
            ]
        }

    async def send_test_webhook(
        self,
        webhook_url: str,
        webhook_format: str = 'generic',
        headers: Dict = None
    ) -> bool:
        """
        Send a test webhook

        Args:
            webhook_url: Webhook URL
            webhook_format: Format (generic, pagerduty, discord, teams)
            headers: Optional headers

        Returns:
            True if sent successfully
        """
        payload = {
            'alert_id': 'test-123',
            'title': 'Test Webhook',
            'message': 'This is a test notification from the SEO Intelligence Platform.',
            'severity': 'low',
            'property': 'https://example.com',
            'metadata': {},
            'timestamp': '2025-11-22T00:00:00Z'
        }

        config = {
            'url': webhook_url,
            'format': webhook_format,
            'headers': headers or {}
        }

        return await self.send(payload, config)


# Synchronous wrapper
def send_webhook_notification_sync(payload: Dict, config: Dict) -> bool:
    """Synchronous wrapper for sending webhook notifications"""
    notifier = WebhookNotifier()
    return asyncio.run(notifier.send(payload, config))


__all__ = ['WebhookNotifier']
