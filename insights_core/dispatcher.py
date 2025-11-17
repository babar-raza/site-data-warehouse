"""
Insight Dispatcher - Routes insights to appropriate channels
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from insights_core.channels import (
    Channel,
    DispatchResult,
    SlackChannel,
    JiraChannel,
    EmailChannel,
    WebhookChannel
)

logger = logging.getLogger(__name__)


class InsightDispatcher:
    """
    Routes insights to configured channels based on rules
    
    Features:
    - Pluggable channel system
    - Configurable routing rules
    - Retry logic with exponential backoff
    - Dry-run mode for testing
    """
    
    # Default routing rules
    DEFAULT_ROUTING_RULES = {
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
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize dispatcher with configuration
        
        Args:
            config: Dispatcher configuration including channel settings
        """
        self.config = config
        self.dry_run = config.get('dry_run', False)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delays = config.get('retry_delays', [1, 2, 4])  # seconds
        
        # Load routing rules
        self.routing_rules = config.get('routing_rules', self.DEFAULT_ROUTING_RULES)
        
        # Initialize channels
        self.channels = self._initialize_channels(config.get('channels', {}))
        
        logger.info(f"Initialized dispatcher with {len(self.channels)} channels (dry_run={self.dry_run})")
    
    def _initialize_channels(self, channel_configs: Dict[str, Any]) -> Dict[str, Channel]:
        """Initialize all configured channels"""
        channels = {}
        
        # Slack
        if 'slack' in channel_configs:
            slack_config = channel_configs['slack']
            slack_config['dry_run'] = self.dry_run
            channels['slack'] = SlackChannel(slack_config)
        
        # Jira
        if 'jira' in channel_configs:
            jira_config = channel_configs['jira']
            jira_config['dry_run'] = self.dry_run
            channels['jira'] = JiraChannel(jira_config)
        
        # Email
        if 'email' in channel_configs:
            email_config = channel_configs['email']
            email_config['dry_run'] = self.dry_run
            channels['email'] = EmailChannel(email_config)
        
        # Webhook
        if 'webhook' in channel_configs:
            webhook_config = channel_configs['webhook']
            webhook_config['dry_run'] = self.dry_run
            channels['webhook'] = WebhookChannel(webhook_config)
        
        return channels
    
    def dispatch(self, insight: Any) -> Dict[str, DispatchResult]:
        """
        Dispatch a single insight to appropriate channels
        
        Args:
            insight: Insight to dispatch
            
        Returns:
            Dict mapping channel names to DispatchResult
        """
        # Determine target channels based on rules
        target_channels = self._get_target_channels(insight)
        
        if not target_channels:
            logger.info(f"No channels configured for insight: {insight.title} ({insight.category.value}/{insight.severity})")
            return {}
        
        logger.info(f"Dispatching insight '{insight.title}' to channels: {target_channels}")
        
        # Dispatch to each channel
        results = {}
        for channel_name in target_channels:
            if channel_name not in self.channels:
                logger.warning(f"Channel '{channel_name}' not initialized, skipping")
                continue
            
            channel = self.channels[channel_name]
            
            # Validate channel config
            if not channel.validate_config():
                logger.warning(f"Channel '{channel_name}' config invalid, skipping")
                continue
            
            # Send with retry logic
            result = self._send_with_retry(channel, insight)
            results[channel_name] = result
        
        return results
    
    def dispatch_batch(self, insights: List[Any]) -> Dict[str, Any]:
        """
        Dispatch multiple insights
        
        Args:
            insights: List of insights to dispatch
            
        Returns:
            Summary statistics
        """
        logger.info(f"Dispatching batch of {len(insights)} insights")
        
        start_time = time.time()
        
        all_results = []
        successes = 0
        failures = 0
        
        for insight in insights:
            results = self.dispatch(insight)
            all_results.extend(results.values())
            
            # Count successes/failures
            for result in results.values():
                if result.success:
                    successes += 1
                else:
                    failures += 1
        
        duration = time.time() - start_time
        
        stats = {
            'total_insights': len(insights),
            'total_dispatches': len(all_results),
            'successes': successes,
            'failures': failures,
            'duration_seconds': duration,
            'results': all_results
        }
        
        logger.info(f"Batch dispatch complete: {successes} successes, {failures} failures in {duration:.2f}s")
        
        return stats
    
    def _get_target_channels(self, insight: Any) -> List[str]:
        """
        Determine which channels to dispatch to based on routing rules
        
        Args:
            insight: Insight to route
            
        Returns:
            List of channel names
        """
        category = insight.category.value
        severity = insight.severity
        
        # Look up routing rules
        if category not in self.routing_rules:
            logger.warning(f"No routing rules for category: {category}")
            return []
        
        if severity not in self.routing_rules[category]:
            logger.warning(f"No routing rules for {category}/{severity}")
            return []
        
        return self.routing_rules[category][severity]
    
    def _send_with_retry(self, channel: Channel, insight: Any) -> DispatchResult:
        """
        Send insight with retry logic
        
        Args:
            channel: Channel to send to
            insight: Insight to send
            
        Returns:
            DispatchResult
        """
        last_result = None
        
        for attempt in range(self.max_retries + 1):
            # Send
            result = channel.send(insight)
            result.retry_count = attempt
            
            # Success
            if result.success:
                if attempt > 0:
                    logger.info(f"Retry succeeded on attempt {attempt + 1} for {channel}")
                return result
            
            # Failure
            last_result = result
            logger.warning(f"Dispatch failed on attempt {attempt + 1}/{self.max_retries + 1}: {result.error}")
            
            # Don't retry on last attempt
            if attempt < self.max_retries:
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
        
        # All retries exhausted
        logger.error(f"All {self.max_retries} retries exhausted for {channel}")
        return last_result
    
    def dispatch_recent_insights(
        self,
        repository: Any,
        hours: int = 24,
        property: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dispatch all insights generated in the last N hours
        
        Args:
            repository: InsightRepository instance
            hours: Hours to look back
            property: Optional property filter
            
        Returns:
            Dispatch statistics
        """
        # Query recent insights
        insights = repository.query_recent(hours=hours, property=property)
        
        logger.info(f"Found {len(insights)} insights from last {hours} hours")
        
        if not insights:
            return {
                'total_insights': 0,
                'total_dispatches': 0,
                'successes': 0,
                'failures': 0
            }
        
        # Dispatch batch
        return self.dispatch_batch(insights)
    
    def test_routing(self, insight: Any) -> Dict[str, Any]:
        """
        Test routing without actually sending (always dry-run)
        
        Args:
            insight: Insight to test routing for
            
        Returns:
            Routing decision and reasoning
        """
        target_channels = self._get_target_channels(insight)
        
        return {
            'insight_id': insight.id,
            'insight_title': insight.title,
            'category': insight.category.value,
            'severity': insight.severity,
            'target_channels': target_channels,
            'routing_rule': self.routing_rules.get(insight.category.value, {}).get(insight.severity, []),
            'available_channels': list(self.channels.keys()),
            'configured_channels': [name for name, ch in self.channels.items() if ch.validate_config()]
        }
