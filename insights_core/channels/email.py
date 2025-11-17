"""
Email channel implementation
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from datetime import datetime
from .base import Channel, DispatchResult


class EmailChannel(Channel):
    """SMTP email channel for dispatching insights"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_host = config.get('smtp_host', 'localhost')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_user = config.get('smtp_user')
        self.smtp_password = config.get('smtp_password')
        self.from_email = config.get('from_email', 'noreply@gsc-insights.local')
        self.to_emails = config.get('to_emails', [])
        self.use_tls = config.get('use_tls', True)
    
    def validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.enabled:
            return False
        
        if not self.to_emails:
            self.logger.error("No recipient emails configured")
            return False
        
        return True
    
    def format_message(self, insight: Any) -> Dict[str, Any]:
        """
        Format insight as HTML email
        
        Args:
            insight: Insight object
            
        Returns:
            Dict with subject and HTML body
        """
        # Subject line
        severity_prefix = {
            'critical': '🚨 CRITICAL',
            'high': '⚠️ HIGH',
            'medium': '⚡ MEDIUM',
            'low': 'ℹ️ LOW'
        }.get(insight.severity, 'INFO')
        
        subject = f"{severity_prefix}: {insight.title}"
        
        # HTML body
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: {self._get_severity_color(insight.severity)}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .metrics {{ background-color: #f5f5f5; padding: 15px; border-left: 4px solid {self._get_severity_color(insight.severity)}; margin: 20px 0; }}
                .actions {{ background-color: #e8f5e9; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                .footer {{ padding: 20px; background-color: #f5f5f5; font-size: 12px; color: #666; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{insight.title}</h1>
                <p><strong>Severity:</strong> {insight.severity.upper()} | <strong>Confidence:</strong> {int(insight.confidence * 100)}%</p>
            </div>
            
            <div class="content">
                <h2>Description</h2>
                <p>{insight.description}</p>
                
                <h2>Details</h2>
                <table>
                    <tr>
                        <th>Property</th>
                        <td>{insight.property}</td>
                    </tr>
                    <tr>
                        <th>Category</th>
                        <td>{insight.category.value}</td>
                    </tr>
                    <tr>
                        <th>Entity</th>
                        <td>{insight.entity_id or 'N/A'}</td>
                    </tr>
                    <tr>
                        <th>Generated At</th>
                        <td>{insight.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                    </tr>
                </table>
                
                {self._format_metrics_html(insight.metrics) if insight.metrics else ''}
                
                {self._format_actions_html(insight.actions) if insight.actions else ''}
            </div>
            
            <div class="footer">
                <p>This is an automated message from GSC Insight Engine.</p>
                <p>Source: {insight.source}</p>
            </div>
        </body>
        </html>
        """
        
        return {
            'subject': subject,
            'html': html
        }
    
    def _get_severity_color(self, severity: str) -> str:
        """Get HTML color for severity"""
        colors = {
            'critical': '#d32f2f',
            'high': '#f57c00',
            'medium': '#fbc02d',
            'low': '#388e3c'
        }
        return colors.get(severity, '#757575')
    
    def _format_metrics_html(self, metrics: Dict[str, Any]) -> str:
        """Format metrics as HTML table"""
        if not metrics:
            return ''
        
        rows = []
        for key, value in metrics.items():
            # Clean up key name
            label = key.replace('_', ' ').title()
            
            # Format value
            if isinstance(value, float):
                if 'change' in key.lower():
                    formatted = f"{value:+.1f}%"
                else:
                    formatted = f"{value:,.2f}"
            elif isinstance(value, int):
                formatted = f"{value:,}"
            else:
                formatted = str(value)
            
            rows.append(f"<tr><th>{label}</th><td>{formatted}</td></tr>")
        
        return f"""
        <div class="metrics">
            <h2>Metrics</h2>
            <table>
                {''.join(rows)}
            </table>
        </div>
        """
    
    def _format_actions_html(self, actions: list) -> str:
        """Format recommended actions as HTML list"""
        if not actions:
            return ''
        
        action_items = ''.join([f"<li>{action}</li>" for action in actions])
        
        return f"""
        <div class="actions">
            <h2>Recommended Actions</h2>
            <ul>
                {action_items}
            </ul>
        </div>
        """
    
    def send(self, insight: Any, **kwargs) -> DispatchResult:
        """
        Send insight via email
        
        Args:
            insight: Insight to send
            **kwargs: Additional parameters
            
        Returns:
            DispatchResult
        """
        start_time = datetime.utcnow()
        
        # Dry run mode
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would send email: {insight.title}")
            return DispatchResult(
                success=True,
                channel='email',
                insight_id=insight.id,
                timestamp=start_time,
                response={'dry_run': True}
            )
        
        # Validate config
        if not self.validate_config():
            return DispatchResult(
                success=False,
                channel='email',
                insight_id=insight.id,
                timestamp=start_time,
                error="Email not configured correctly"
            )
        
        try:
            # Format message
            message_data = self.format_message(insight)
            
            # Create MIME message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = message_data['subject']
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            
            # Attach HTML part
            html_part = MIMEText(message_data['html'], 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                
                server.send_message(msg)
            
            self.logger.info(f"Sent insight email: {insight.title}")
            
            return DispatchResult(
                success=True,
                channel='email',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                response={'recipients': self.to_emails}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}", exc_info=True)
            return DispatchResult(
                success=False,
                channel='email',
                insight_id=insight.id,
                timestamp=datetime.utcnow(),
                error=str(e)
            )
