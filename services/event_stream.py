"""
Event Stream - Real-Time Event Processing with Redis Streams
============================================================
Enables real-time event-driven architecture:
- Instant anomaly alerts (<1 second)
- Live dashboard updates
- Event-driven workflows
- Decoupled services

Uses Redis Streams (lighter than Kafka, perfect for this scale)
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

logger = logging.getLogger(__name__)


class EventStream:
    """
    Redis Streams wrapper for event publishing and consumption
    """

    # Stream names
    TRAFFIC_ANOMALIES = 'traffic:anomalies'
    CONTENT_CHANGES = 'content:changes'
    QUALITY_ALERTS = 'content:quality_alerts'
    ACTION_CREATED = 'actions:created'
    ACTION_COMPLETED = 'actions:completed'
    FORECAST_GENERATED = 'forecasts:generated'

    def __init__(self, redis_url: str = None):
        """
        Initialize event stream

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')

        # Connect to Redis
        self.redis = redis.from_url(
            self.redis_url,
            decode_responses=True  # Auto-decode to strings
        )

        logger.info(f"EventStream connected to {self.redis_url}")

    def publish_event(
        self,
        stream: str,
        event_type: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Publish an event to a stream

        Args:
            stream: Stream name
            event_type: Type of event
            data: Event data

        Returns:
            Event ID
        """
        try:
            # Add metadata
            event = {
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': json.dumps(data)
            }

            # Publish to stream
            event_id = self.redis.xadd(stream, event)

            logger.info(f"Published {event_type} to {stream}: {event_id}")
            return event_id

        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            raise

    def publish_anomaly(
        self,
        property: str,
        page_path: str,
        metric: str,
        actual: float,
        expected: float,
        deviation_pct: float,
        severity: str
    ) -> str:
        """
        Publish traffic anomaly event

        Args:
            property: Property URL
            page_path: Page path
            metric: Metric name
            actual: Actual value
            expected: Expected value
            deviation_pct: Deviation percentage
            severity: Severity level

        Returns:
            Event ID
        """
        return self.publish_event(
            self.TRAFFIC_ANOMALIES,
            'anomaly_detected',
            {
                'property': property,
                'page_path': page_path,
                'metric': metric,
                'actual': actual,
                'expected': expected,
                'deviation_pct': deviation_pct,
                'severity': severity
            }
        )

    def publish_content_change(
        self,
        property: str,
        page_path: str,
        change_type: str,
        changes: Dict[str, Any]
    ) -> str:
        """
        Publish content change event

        Args:
            property: Property URL
            page_path: Page path
            change_type: Type of change
            changes: Change details

        Returns:
            Event ID
        """
        return self.publish_event(
            self.CONTENT_CHANGES,
            'content_changed',
            {
                'property': property,
                'page_path': page_path,
                'change_type': change_type,
                'changes': changes
            }
        )

    def publish_quality_alert(
        self,
        property: str,
        page_path: str,
        quality_score: float,
        issues: List[str]
    ) -> str:
        """
        Publish content quality alert

        Args:
            property: Property URL
            page_path: Page path
            quality_score: Quality score
            issues: List of issues

        Returns:
            Event ID
        """
        return self.publish_event(
            self.QUALITY_ALERTS,
            'quality_alert',
            {
                'property': property,
                'page_path': page_path,
                'quality_score': quality_score,
                'issues': issues
            }
        )

    def publish_action_created(
        self,
        action_id: str,
        action_type: str,
        priority_score: float,
        page_path: str,
        property: str
    ) -> str:
        """
        Publish action created event

        Args:
            action_id: Action ID
            action_type: Action type
            priority_score: Priority score
            page_path: Page path
            property: Property URL

        Returns:
            Event ID
        """
        return self.publish_event(
            self.ACTION_CREATED,
            'action_created',
            {
                'action_id': action_id,
                'action_type': action_type,
                'priority_score': priority_score,
                'page_path': page_path,
                'property': property
            }
        )

    def consume_events(
        self,
        stream: str,
        consumer_group: str,
        consumer_name: str,
        count: int = 10,
        block: int = 1000
    ) -> List[Dict]:
        """
        Consume events from a stream

        Args:
            stream: Stream name
            consumer_group: Consumer group name
            consumer_name: Consumer name
            count: Max events to read
            block: Block time in milliseconds

        Returns:
            List of events
        """
        try:
            # Create consumer group if not exists
            try:
                self.redis.xgroup_create(
                    stream,
                    consumer_group,
                    id='0',
                    mkstream=True
                )
            except redis.ResponseError as e:
                # Group already exists
                pass

            # Read events
            events = self.redis.xreadgroup(
                consumer_group,
                consumer_name,
                {stream: '>'},
                count=count,
                block=block
            )

            parsed_events = []

            for stream_name, messages in events:
                for message_id, message_data in messages:
                    # Parse event
                    event = {
                        'event_id': message_id,
                        'stream': stream_name,
                        'event_type': message_data.get('event_type'),
                        'timestamp': message_data.get('timestamp'),
                        'data': json.loads(message_data.get('data', '{}'))
                    }
                    parsed_events.append(event)

                    # Acknowledge event
                    self.redis.xack(stream, consumer_group, message_id)

            return parsed_events

        except Exception as e:
            logger.error(f"Error consuming events: {e}")
            return []

    def get_stream_length(self, stream: str) -> int:
        """Get number of events in stream"""
        try:
            return self.redis.xlen(stream)
        except Exception as e:
            logger.error(f"Error getting stream length: {e}")
            return 0

    def trim_stream(self, stream: str, max_length: int = 10000) -> int:
        """
        Trim stream to max length (keep recent events)

        Args:
            stream: Stream name
            max_length: Maximum length

        Returns:
            Number of events trimmed
        """
        try:
            return self.redis.xtrim(stream, maxlen=max_length, approximate=True)
        except Exception as e:
            logger.error(f"Error trimming stream: {e}")
            return 0

    def get_pending_events(
        self,
        stream: str,
        consumer_group: str
    ) -> List[Dict]:
        """
        Get pending (unacknowledged) events

        Args:
            stream: Stream name
            consumer_group: Consumer group

        Returns:
            List of pending events
        """
        try:
            pending = self.redis.xpending(stream, consumer_group)

            return {
                'pending_count': pending['pending'],
                'min_idle_time': pending['min_idle_time'],
                'max_idle_time': pending['max_idle_time']
            }

        except Exception as e:
            logger.error(f"Error getting pending events: {e}")
            return {}

    def close(self):
        """Close Redis connection"""
        self.redis.close()


class EventConsumer:
    """
    Base class for event consumers
    """

    def __init__(
        self,
        stream: EventStream,
        consumer_group: str,
        consumer_name: str
    ):
        """
        Initialize event consumer

        Args:
            stream: EventStream instance
            consumer_group: Consumer group name
            consumer_name: Consumer name
        """
        self.stream = stream
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name

        logger.info(f"EventConsumer {consumer_name} initialized for group {consumer_group}")

    async def process_event(self, event: Dict) -> bool:
        """
        Process a single event

        Override in subclasses

        Args:
            event: Event data

        Returns:
            True if processed successfully
        """
        raise NotImplementedError("Subclasses must implement process_event")

    async def run(self, streams: List[str], stop_after: int = None):
        """
        Run consumer loop

        Args:
            streams: List of streams to consume from
            stop_after: Stop after processing N events (None = run forever)
        """
        processed = 0

        logger.info(f"Starting consumer for streams: {streams}")

        while True:
            for stream_name in streams:
                # Consume events
                events = self.stream.consume_events(
                    stream_name,
                    self.consumer_group,
                    self.consumer_name,
                    count=10,
                    block=1000
                )

                # Process each event
                for event in events:
                    try:
                        success = await self.process_event(event)

                        if success:
                            processed += 1
                            logger.info(f"Processed event {event['event_id']}")
                        else:
                            logger.warning(f"Failed to process event {event['event_id']}")

                    except Exception as e:
                        logger.error(f"Error processing event {event['event_id']}: {e}")

                    # Check if should stop
                    if stop_after and processed >= stop_after:
                        logger.info(f"Processed {processed} events, stopping")
                        return

            # Small delay to avoid tight loop
            if not events:
                import asyncio
                await asyncio.sleep(0.1)


# Example consumer implementations
class AnomalyAlertConsumer(EventConsumer):
    """
    Consumer that sends alerts for traffic anomalies
    """

    async def process_event(self, event: Dict) -> bool:
        """Process anomaly event and send alert"""
        try:
            data = event['data']

            # Check severity
            severity = data.get('severity')

            if severity in ['high', 'critical']:
                # Send alert (implement your alert mechanism)
                logger.warning(
                    f"ALERT: {data['page_path']} - {data['metric']} "
                    f"deviation: {data['deviation_pct']:.1f}% ({severity})"
                )

                # Could send to:
                # - Slack
                # - Email
                # - PagerDuty
                # - SMS
                # etc.

            return True

        except Exception as e:
            logger.error(f"Error in anomaly alert consumer: {e}")
            return False


class ActionCreationConsumer(EventConsumer):
    """
    Consumer that creates actions from anomalies
    """

    async def process_event(self, event: Dict) -> bool:
        """Process anomaly and create action"""
        try:
            data = event['data']

            # Create action in database
            # (This would integrate with the actions system)

            logger.info(f"Created action for {data['page_path']}")
            return True

        except Exception as e:
            logger.error(f"Error in action creation consumer: {e}")
            return False
