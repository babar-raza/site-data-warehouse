"""
Configuration for Insights Core
"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class InsightsConfig(BaseModel):
    """Configuration for Insight Engine"""
    
    # Database
    warehouse_dsn: str = Field(
        default_factory=lambda: os.getenv(
            'WAREHOUSE_DSN',
            'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db'
        )
    )
    
    # Detection thresholds
    risk_threshold_clicks_pct: float = -20.0  # % drop to trigger risk
    risk_threshold_conversions_pct: float = -20.0
    opportunity_threshold_impressions_pct: float = 50.0  # % increase
    
    # Confidence thresholds
    min_confidence_for_action: float = 0.7
    min_data_points_for_detection: int = 7  # Need 7 days of data
    
    # Repository settings
    max_insights_per_query: int = 100
    insights_retention_days: int = 90  # Delete old resolved insights
    
    # Window sizes
    default_window_days: int = 7
    extended_window_days: int = 28
    
    # Dispatcher settings
    dispatcher_enabled: bool = Field(
        default_factory=lambda: os.getenv('DISPATCHER_ENABLED', 'false').lower() == 'true'
    )
    dispatcher_dry_run: bool = Field(
        default_factory=lambda: os.getenv('DISPATCHER_DRY_RUN', 'false').lower() == 'true'
    )
    
    class Config:
        env_prefix = 'INSIGHTS_'
        case_sensitive = False
    
    def get_dispatcher_config(self) -> Dict[str, Any]:
        """
        Get complete dispatcher configuration
        
        Returns:
            Dict with all dispatcher settings
        """
        return {
            'enabled': self.dispatcher_enabled,
            'dry_run': self.dispatcher_dry_run,
            'max_retries': int(os.environ.get('DISPATCHER_MAX_RETRIES', '3')),
            'retry_delays': [1, 2, 4],  # seconds
            'channels': {
                'slack': self._get_slack_config(),
                'jira': self._get_jira_config(),
                'email': self._get_email_config(),
                'webhook': self._get_webhook_config()
            },
            'routing_rules': self._get_routing_rules()
        }
    
    def _get_slack_config(self) -> Dict[str, Any]:
        """Get Slack channel configuration"""
        return {
            'enabled': os.environ.get('SLACK_ENABLED', 'false').lower() == 'true',
            'webhook_url': os.environ.get('SLACK_WEBHOOK_URL'),
            'channel': os.environ.get('SLACK_CHANNEL'),  # Optional override
            'username': os.environ.get('SLACK_USERNAME', 'GSC Insights Bot'),
            'icon_emoji': os.environ.get('SLACK_ICON_EMOJI', ':mag:')
        }
    
    def _get_jira_config(self) -> Dict[str, Any]:
        """Get Jira channel configuration"""
        return {
            'enabled': os.environ.get('JIRA_ENABLED', 'false').lower() == 'true',
            'base_url': os.environ.get('JIRA_BASE_URL'),
            'username': os.environ.get('JIRA_USERNAME'),
            'api_token': os.environ.get('JIRA_API_TOKEN'),
            'project_key': os.environ.get('JIRA_PROJECT_KEY', 'SEO'),
            'issue_type': os.environ.get('JIRA_ISSUE_TYPE', 'Bug')
        }
    
    def _get_email_config(self) -> Dict[str, Any]:
        """Get email channel configuration"""
        to_emails_str = os.environ.get('EMAIL_TO_ADDRESSES', '')
        to_emails = [e.strip() for e in to_emails_str.split(',') if e.strip()]
        
        return {
            'enabled': os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true',
            'smtp_host': os.environ.get('SMTP_HOST', 'localhost'),
            'smtp_port': int(os.environ.get('SMTP_PORT', '587')),
            'smtp_user': os.environ.get('SMTP_USER'),
            'smtp_password': os.environ.get('SMTP_PASSWORD'),
            'from_email': os.environ.get('EMAIL_FROM', 'noreply@gsc-insights.local'),
            'to_emails': to_emails,
            'use_tls': os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
        }
    
    def _get_webhook_config(self) -> Dict[str, Any]:
        """Get webhook channel configuration"""
        return {
            'enabled': os.environ.get('WEBHOOK_ENABLED', 'false').lower() == 'true',
            'url': os.environ.get('WEBHOOK_URL'),
            'method': os.environ.get('WEBHOOK_METHOD', 'POST'),
            'headers': {}  # Could parse from env if needed
        }
    
    def _get_routing_rules(self) -> Dict[str, Dict[str, list]]:
        """
        Get routing rules (can be customized via env vars)
        
        Returns default rules if not overridden
        """
        # For now, return defaults
        # Could be extended to parse from JSON env var
        return {
            'risk': {
                'critical': ['slack', 'jira', 'email'],
                'high': ['slack', 'email'],
                'medium': ['email'],
                'low': []
            },
            'opportunity': {
                'critical': ['slack', 'jira'],
                'high': ['slack'],
                'medium': ['email'],
                'low': []
            },
            'diagnosis': {
                'critical': ['jira', 'email'],
                'high': ['jira'],
                'medium': ['email'],
                'low': []
            }
        }

