"""
Slack channel implementation
"""
import requests
from typing import Dict, Any
from datetime import datetime
from .base import Channel, DispatchResult


class SlackChannel(Channel):
    """Slack webhook channel for dispatching insights"""
    
    SEVERITY_EMOJIS = {
        'critical': '🚨',
        'high': '⚠️',
        'medium': '⚡',
        'low': 'ℹ️'
    }
    
    SEVERITY_COLORS = {
        'critical': '#FF0000',
        'high': '#FF6B00',
        'medium': '#FFB800',
        'low': '#36A64F'
    }
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('webhook_url')
        self.channel = config.get('channel')
        self.username = config.get('username', 'GSC Insights Bot')
        self.icon_emoji = config.get('icon_emoji', ':mag:')
    
    def validate_config(self) -> bool:
        """Validate Slack configuration"""
        if not self.enabled:
            return False
        
        if not self.webhook_url:
            self.logger.error("Slack webhook_url not configured")
            return False
        
        return True
    
    def format_message(self, insight: Any) -> Dict[str, Any]:
        """
        Format insight as Slack message with blocks
        
        Args:
            insight: Insight object
            
        Returns:
            Slack message payload
        """
        emoji = self.SEVERITY_EMOJIS.get(insight.severity, 'ℹ️')
        color = self.SEVERITY_COLORS.get(insight.severity, '#36A64F')
        
        # Build main text
        text = f"{emoji} *{insight.severity.upper()}*: {insight.title}"
        
        # Build rich blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {insight.title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Property:*\n{insight.property}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{insight.severity.upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{insight.category.value}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Confidence:*\n{int(insight.confidence * 100)}%"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": insight.description
                }
            }
        ]
        
        # Add entity link if it's a page
        if insight.entity_id and insight.entity_id.startswith('/'):
            # Extract domain from property (e.g., sc-domain:docs.aspose.net -> docs.aspose.net)
            domain = insight.property.replace('sc-domain:', '')
            page_url = f"https://{domain}{insight.entity_id}"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Page:* <{page_url}|{insight.entity_id}>"
                }
            })
        
        # Add metrics if available
        if insight.metrics:
            metrics_text = self._format_metrics(insight.metrics)
            if metrics_text:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Metrics:*\n{metrics_text}"
                    }
                })
        
        # Add action button
        if insight.actions:
            action_text = "\n".join([f"• {action}" for action in insight.actions])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recommended Actions:*\n{action_text}"
                }
            })
        
        # Build final payload
        payload = {
            "text": text,
            "blocks": blocks,
            "username": self.username,
            "icon_emoji": self.icon_emoji
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        return payload
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics dict as readable string"""
        lines = []
        
        # Common metric keys
        metric_labels = {
            'gsc_clicks': 'Clicks',
            'gsc_clicks_change_wow': 'Clicks Change (WoW)',
            'gsc_impressions': 'Impressions',
            'gsc_impressions_change_wow': 'Impressions Change (WoW)',
            'ga_conversions': 'Conversions',
            'ga_conversions_change_wow': 'Conversions Change (WoW)',
            'gsc_position': 'Position',
            'gsc_position_change_wow': 'Position Change (WoW)'
        }
        
        for key, label in metric_labels.items():
            if key in metrics:
                value = metrics[key]
                
                # Format percentage changes
                if 'change' in key:
                    emoji = '📉' if value < 0 else '📈' if value > 0 else '➡️'
                    lines.append(f"{emoji} {label}: {value:+.1f}%")
                else:
                    lines.append(f"• {label}: {value:,.0f}" if isinstance(value, (int, float)) else f"• {label}: {value}")
        
        return "\n".join(lines)
    
    def send(self, insight: Any, **kwargs) -> DispatchResult:
        """
        Send insight to Slack webhook
        
        Args:
            insight: Insight to send
            **kwargs: Additional parameters
            
        Returns:
            DispatchResult
        """
        start_time = datetime.utcnow()
        
        # Dry run mode
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would send to Slack: {insight.title}")
            return DispatchResult(
                success=True,
                channel='slack',
                insight_id=insight.id,
                timestamp=start_time,
                response={'dry_run': True}
            )
        
        # Validate config
        if not self.validate_config():
            return DispatchResult(
                success=False,
                channel='slack',
                insight_id=insight.id,
                timestamp=start_time,
                error="Slack not configured correctly"
            )
        
        try:
            # Format message
            payload = self.format_message(insight)
            
            # Send to webhook
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            
            self.logger.info(f"Sent insight to Slack: {insight.title}")
            
            return DispatchResult(
                success=True,
                channel='slack',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                response={'status_code': response.status_code}
            )
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send to Slack: {e}")
            return DispatchResult(
                success=False,
                channel='slack',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
        except Exception as e:
            self.logger.error(f"Unexpected error sending to Slack: {e}", exc_info=True)
            return DispatchResult(
                success=False,
                channel='slack',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
