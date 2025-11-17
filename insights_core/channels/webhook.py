"""
Generic webhook channel implementation
"""
import requests
from typing import Dict, Any
from datetime import datetime
from .base import Channel, DispatchResult


class WebhookChannel(Channel):
    """Generic webhook channel for dispatching insights"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('url')
        self.method = config.get('method', 'POST').upper()
        self.headers = config.get('headers', {})
        self.template = config.get('template', 'default')
    
    def validate_config(self) -> bool:
        """Validate webhook configuration"""
        if not self.enabled:
            return False
        
        if not self.url:
            self.logger.error("Webhook URL not configured")
            return False
        
        return True
    
    def format_message(self, insight: Any) -> Dict[str, Any]:
        """
        Format insight as webhook payload
        
        Args:
            insight: Insight object
            
        Returns:
            Webhook payload dict
        """
        # Default JSON payload
        payload = {
            "id": insight.id,
            "title": insight.title,
            "description": insight.description,
            "property": insight.property,
            "category": insight.category.value,
            "severity": insight.severity,
            "confidence": insight.confidence,
            "entity_id": insight.entity_id,
            "entity_type": insight.entity_type,
            "metrics": insight.metrics,
            "actions": insight.actions,
            "source": insight.source,
            "generated_at": insight.generated_at.isoformat(),
            "expires_at": insight.expires_at.isoformat() if insight.expires_at else None
        }
        
        return payload
    
    def send(self, insight: Any, **kwargs) -> DispatchResult:
        """
        Send insight to webhook
        
        Args:
            insight: Insight to send
            **kwargs: Additional parameters
            
        Returns:
            DispatchResult
        """
        start_time = datetime.utcnow()
        
        # Dry run mode
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would send webhook: {insight.title}")
            return DispatchResult(
                success=True,
                channel='webhook',
                insight_id=insight.id,
                timestamp=start_time,
                response={'dry_run': True}
            )
        
        # Validate config
        if not self.validate_config():
            return DispatchResult(
                success=False,
                channel='webhook',
                insight_id=insight.id,
                timestamp=start_time,
                error="Webhook not configured correctly"
            )
        
        try:
            # Format payload
            payload = self.format_message(insight)
            
            # Merge custom headers
            headers = {'Content-Type': 'application/json'}
            headers.update(self.headers)
            
            # Send request
            if self.method == 'POST':
                response = requests.post(
                    self.url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            elif self.method == 'PUT':
                response = requests.put(
                    self.url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {self.method}")
            
            response.raise_for_status()
            
            self.logger.info(f"Sent webhook for insight: {insight.title}")
            
            return DispatchResult(
                success=True,
                channel='webhook',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                response={'status_code': response.status_code}
            )
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send webhook: {e}")
            return DispatchResult(
                success=False,
                channel='webhook',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
        except Exception as e:
            self.logger.error(f"Unexpected error sending webhook: {e}", exc_info=True)
            return DispatchResult(
                success=False,
                channel='webhook',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
