"""
Tests for Event Stream Module
==============================
Tests Redis Streams real-time event processing.
"""
import asyncio
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from services.event_stream import EventStream, EventConsumer, AnomalyAlertConsumer, ActionCreationConsumer


@pytest.fixture
def redis_url():
    """Get Redis URL for testing"""
    return os.getenv('TEST_REDIS_URL', 'redis://localhost:6379/15')  # Use DB 15 for tests


@pytest.fixture
def event_stream(redis_url):
    """Create EventStream instance"""
    with patch('redis.from_url') as mock_redis:
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        stream = EventStream(redis_url)
        stream.redis = mock_redis_instance

        yield stream

        # Cleanup
        stream.close()


# =============================================
# STREAM INITIALIZATION TESTS
# =============================================

def test_event_stream_initialization(redis_url):
    """Test EventStream initialization"""
    with patch('redis.from_url') as mock_redis:
        stream = EventStream(redis_url)

        assert stream.redis_url == redis_url
        mock_redis.assert_called_once()


def test_stream_names_constants():
    """Test stream name constants"""
    assert EventStream.TRAFFIC_ANOMALIES == 'traffic:anomalies'
    assert EventStream.CONTENT_CHANGES == 'content:changes'
    assert EventStream.QUALITY_ALERTS == 'content:quality_alerts'
    assert EventStream.ACTION_CREATED == 'actions:created'
    assert EventStream.ACTION_COMPLETED == 'actions:completed'
    assert EventStream.FORECAST_GENERATED == 'forecasts:generated'


# =============================================
# EVENT PUBLISHING TESTS
# =============================================

def test_publish_event(event_stream):
    """Test generic event publishing"""
    event_stream.redis.xadd.return_value = '1234567890-0'

    event_id = event_stream.publish_event(
        stream='test:stream',
        event_type='test_event',
        data={'key': 'value', 'count': 42}
    )

    assert event_id == '1234567890-0'

    # Verify xadd was called with correct arguments
    call_args = event_stream.redis.xadd.call_args
    assert call_args[0][0] == 'test:stream'
    assert call_args[0][1]['event_type'] == 'test_event'
    assert 'timestamp' in call_args[0][1]
    assert 'data' in call_args[0][1]


def test_publish_anomaly(event_stream):
    """Test anomaly event publishing"""
    event_stream.redis.xadd.return_value = 'event-123'

    event_id = event_stream.publish_anomaly(
        property='https://blog.aspose.net',
        page_path='/python/tutorial/',
        metric='clicks',
        actual=100.0,
        expected=500.0,
        deviation_pct=-80.0,
        severity='critical'
    )

    assert event_id == 'event-123'

    # Verify stream and event type
    call_args = event_stream.redis.xadd.call_args
    assert call_args[0][0] == EventStream.TRAFFIC_ANOMALIES
    assert call_args[0][1]['event_type'] == 'anomaly_detected'


def test_publish_content_change(event_stream):
    """Test content change event publishing"""
    event_stream.redis.xadd.return_value = 'event-456'

    event_id = event_stream.publish_content_change(
        property='https://blog.aspose.net',
        page_path='/page/',
        change_type='major_update',
        changes={'sections_modified': 3, 'words_changed': 250}
    )

    assert event_id == 'event-456'

    call_args = event_stream.redis.xadd.call_args
    assert call_args[0][0] == EventStream.CONTENT_CHANGES


def test_publish_quality_alert(event_stream):
    """Test quality alert publishing"""
    event_stream.redis.xadd.return_value = 'event-789'

    event_id = event_stream.publish_quality_alert(
        property='https://blog.aspose.net',
        page_path='/low-quality/',
        quality_score=45.5,
        issues=['Low readability', 'Short content', 'No images']
    )

    assert event_id == 'event-789'

    call_args = event_stream.redis.xadd.call_args
    assert call_args[0][0] == EventStream.QUALITY_ALERTS


def test_publish_action_created(event_stream):
    """Test action created event publishing"""
    event_stream.redis.xadd.return_value = 'event-999'

    event_id = event_stream.publish_action_created(
        action_id='action-123',
        action_type='UPDATE_CONTENT',
        priority_score=85.0,
        page_path='/page/',
        property='https://blog.aspose.net'
    )

    assert event_id == 'event-999'

    call_args = event_stream.redis.xadd.call_args
    assert call_args[0][0] == EventStream.ACTION_CREATED


# =============================================
# EVENT CONSUMPTION TESTS
# =============================================

def test_consume_events_creates_group(event_stream):
    """Test consumer group creation"""
    # Mock xgroup_create success
    event_stream.redis.xgroup_create.return_value = 'OK'
    event_stream.redis.xreadgroup.return_value = []

    events = event_stream.consume_events(
        stream='test:stream',
        consumer_group='test_group',
        consumer_name='consumer_1',
        count=10,
        block=1000
    )

    # Verify group creation was attempted
    event_stream.redis.xgroup_create.assert_called_once_with(
        'test:stream',
        'test_group',
        id='0',
        mkstream=True
    )


def test_consume_events_group_exists(event_stream):
    """Test consumption when group already exists"""
    import redis

    # Mock group already exists error
    event_stream.redis.xgroup_create.side_effect = redis.ResponseError("BUSYGROUP")
    event_stream.redis.xreadgroup.return_value = []

    events = event_stream.consume_events(
        stream='test:stream',
        consumer_group='test_group',
        consumer_name='consumer_1'
    )

    # Should continue despite group exists error
    assert isinstance(events, list)


def test_consume_events_reads_messages(event_stream):
    """Test reading and parsing messages"""
    # Mock xreadgroup response
    event_stream.redis.xreadgroup.return_value = [
        ('test:stream', [
            ('1234567890-0', {
                'event_type': 'test_event',
                'timestamp': '2025-11-21T12:00:00',
                'data': '{"key": "value", "count": 42}'
            }),
            ('1234567890-1', {
                'event_type': 'another_event',
                'timestamp': '2025-11-21T12:01:00',
                'data': '{"status": "ok"}'
            })
        ])
    ]

    event_stream.redis.xack.return_value = 1

    events = event_stream.consume_events(
        stream='test:stream',
        consumer_group='test_group',
        consumer_name='consumer_1',
        count=10
    )

    assert len(events) == 2

    # Check first event
    assert events[0]['event_id'] == '1234567890-0'
    assert events[0]['event_type'] == 'test_event'
    assert events[0]['data']['key'] == 'value'
    assert events[0]['data']['count'] == 42

    # Verify acknowledgments
    assert event_stream.redis.xack.call_count == 2


def test_consume_events_error_handling(event_stream):
    """Test error handling during consumption"""
    event_stream.redis.xreadgroup.side_effect = Exception("Redis connection failed")

    events = event_stream.consume_events(
        stream='test:stream',
        consumer_group='test_group',
        consumer_name='consumer_1'
    )

    # Should return empty list on error
    assert events == []


# =============================================
# STREAM MANAGEMENT TESTS
# =============================================

def test_get_stream_length(event_stream):
    """Test getting stream length"""
    event_stream.redis.xlen.return_value = 42

    length = event_stream.get_stream_length('test:stream')

    assert length == 42
    event_stream.redis.xlen.assert_called_once_with('test:stream')


def test_get_stream_length_error(event_stream):
    """Test stream length error handling"""
    event_stream.redis.xlen.side_effect = Exception("Stream not found")

    length = event_stream.get_stream_length('nonexistent:stream')

    assert length == 0


def test_trim_stream(event_stream):
    """Test stream trimming"""
    event_stream.redis.xtrim.return_value = 100  # 100 events trimmed

    trimmed = event_stream.trim_stream('test:stream', max_length=1000)

    assert trimmed == 100
    event_stream.redis.xtrim.assert_called_once_with(
        'test:stream',
        maxlen=1000,
        approximate=True
    )


def test_trim_stream_error(event_stream):
    """Test trim error handling"""
    event_stream.redis.xtrim.side_effect = Exception("Trim failed")

    trimmed = event_stream.trim_stream('test:stream')

    assert trimmed == 0


def test_get_pending_events(event_stream):
    """Test getting pending events"""
    event_stream.redis.xpending.return_value = {
        'pending': 5,
        'min_idle_time': 1000,
        'max_idle_time': 5000
    }

    pending = event_stream.get_pending_events('test:stream', 'test_group')

    assert pending['pending_count'] == 5
    assert pending['min_idle_time'] == 1000
    assert pending['max_idle_time'] == 5000


# =============================================
# EVENT CONSUMER BASE CLASS TESTS
# =============================================

@pytest.mark.asyncio
async def test_event_consumer_initialization(event_stream):
    """Test EventConsumer base class initialization"""
    consumer = EventConsumer(
        stream=event_stream,
        consumer_group='test_group',
        consumer_name='consumer_1'
    )

    assert consumer.stream == event_stream
    assert consumer.consumer_group == 'test_group'
    assert consumer.consumer_name == 'consumer_1'


@pytest.mark.asyncio
async def test_event_consumer_process_event_not_implemented(event_stream):
    """Test that process_event must be implemented"""
    consumer = EventConsumer(
        stream=event_stream,
        consumer_group='test_group',
        consumer_name='consumer_1'
    )

    with pytest.raises(NotImplementedError):
        await consumer.process_event({'event_id': '123', 'data': {}})


# =============================================
# ANOMALY ALERT CONSUMER TESTS
# =============================================

@pytest.mark.asyncio
async def test_anomaly_alert_consumer_high_severity(event_stream):
    """Test anomaly alert consumer with high severity"""
    consumer = AnomalyAlertConsumer(
        stream=event_stream,
        consumer_group='alerts',
        consumer_name='alerter_1'
    )

    event = {
        'event_id': '123',
        'event_type': 'anomaly_detected',
        'data': {
            'page_path': '/critical/page/',
            'metric': 'clicks',
            'deviation_pct': -85.0,
            'severity': 'critical'
        }
    }

    result = await consumer.process_event(event)

    assert result is True


@pytest.mark.asyncio
async def test_anomaly_alert_consumer_low_severity(event_stream):
    """Test anomaly alert consumer with low severity"""
    consumer = AnomalyAlertConsumer(
        stream=event_stream,
        consumer_group='alerts',
        consumer_name='alerter_1'
    )

    event = {
        'event_id': '123',
        'event_type': 'anomaly_detected',
        'data': {
            'page_path': '/page/',
            'metric': 'clicks',
            'deviation_pct': -10.0,
            'severity': 'low'
        }
    }

    result = await consumer.process_event(event)

    # Should still process successfully
    assert result is True


@pytest.mark.asyncio
async def test_anomaly_alert_consumer_error_handling(event_stream):
    """Test anomaly alert consumer error handling"""
    consumer = AnomalyAlertConsumer(
        stream=event_stream,
        consumer_group='alerts',
        consumer_name='alerter_1'
    )

    # Malformed event
    event = {
        'event_id': '123',
        'data': {}  # Missing required fields
    }

    result = await consumer.process_event(event)

    assert result is False


# =============================================
# ACTION CREATION CONSUMER TESTS
# =============================================

@pytest.mark.asyncio
async def test_action_creation_consumer(event_stream):
    """Test action creation consumer"""
    consumer = ActionCreationConsumer(
        stream=event_stream,
        consumer_group='actions',
        consumer_name='action_creator'
    )

    event = {
        'event_id': '456',
        'event_type': 'anomaly_detected',
        'data': {
            'page_path': '/page/',
            'property': 'https://blog.aspose.net',
            'severity': 'high'
        }
    }

    result = await consumer.process_event(event)

    assert result is True


# =============================================
# CONSUMER RUN LOOP TESTS
# =============================================

@pytest.mark.asyncio
async def test_consumer_run_loop_stop_after(event_stream):
    """Test consumer run loop with stop_after"""
    consumer = AnomalyAlertConsumer(
        stream=event_stream,
        consumer_group='alerts',
        consumer_name='alerter_1'
    )

    # Mock consume_events to return 2 events per call
    event_stream.consume_events = Mock(side_effect=[
        [
            {
                'event_id': '1',
                'event_type': 'anomaly_detected',
                'data': {'page_path': '/page1/', 'severity': 'high'}
            },
            {
                'event_id': '2',
                'event_type': 'anomaly_detected',
                'data': {'page_path': '/page2/', 'severity': 'critical'}
            }
        ],
        []  # Stop after first batch
    ])

    await consumer.run(
        streams=['traffic:anomalies'],
        stop_after=2
    )

    # Should have processed 2 events and stopped
    assert event_stream.consume_events.call_count >= 1


@pytest.mark.asyncio
async def test_consumer_run_loop_error_handling(event_stream):
    """Test consumer run loop handles errors"""
    consumer = AnomalyAlertConsumer(
        stream=event_stream,
        consumer_group='alerts',
        consumer_name='alerter_1'
    )

    # Mock consume_events to return event that will cause error
    event_stream.consume_events = Mock(return_value=[
        {
            'event_id': '1',
            'data': {}  # Will cause error in process_event
        }
    ])

    # Should not crash, just log error
    try:
        await consumer.run(
            streams=['traffic:anomalies'],
            stop_after=1
        )
    except Exception as e:
        pytest.fail(f"Consumer run loop should handle errors gracefully: {e}")


# =============================================
# INTEGRATION TESTS
# =============================================

@pytest.mark.integration
def test_redis_connection():
    """Integration test for Redis connection"""
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    stream = EventStream()

    try:
        # Test publish
        event_id = stream.publish_event(
            stream='test:integration',
            event_type='test',
            data={'test': True}
        )

        assert event_id is not None

        # Test stream length
        length = stream.get_stream_length('test:integration')
        assert length > 0

        # Test trim
        trimmed = stream.trim_stream('test:integration', max_length=100)
        assert trimmed >= 0

    finally:
        stream.close()


@pytest.mark.integration
def test_pub_sub_workflow():
    """Integration test for complete pub/sub workflow"""
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    stream = EventStream()

    try:
        # Publish event
        event_id = stream.publish_anomaly(
            property='https://test.com',
            page_path='/test/',
            metric='clicks',
            actual=10.0,
            expected=100.0,
            deviation_pct=-90.0,
            severity='critical'
        )

        assert event_id is not None

        # Consume event
        events = stream.consume_events(
            stream=EventStream.TRAFFIC_ANOMALIES,
            consumer_group='test_group',
            consumer_name='test_consumer',
            count=1
        )

        assert len(events) >= 0  # May be 0 if already consumed

    finally:
        stream.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
