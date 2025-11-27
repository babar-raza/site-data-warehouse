"""
Comprehensive tests for MessageBus (MOCK MODE)

Tests message bus pub/sub, persistence, routing, and dead letter handling using mocks.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock, mock_open
from datetime import datetime, timedelta
import asyncio
import json
from pathlib import Path

from agents.base.message_bus import (
    Message,
    MessageBus,
    MessageHandler
)


@pytest.fixture
def sample_message():
    """Create a sample message"""
    return Message(
        message_id='msg-123',
        topic='test.topic',
        sender_id='sender-001',
        payload={'data': 'test'},
        timestamp=datetime.now(),
        priority=0,
        ttl_seconds=None,
        correlation_id=None,
        metadata=None
    )


@pytest.fixture
def sample_message_dict():
    """Create sample message as dict"""
    return {
        'message_id': 'msg-456',
        'topic': 'test.other',
        'sender_id': 'sender-002',
        'payload': {'value': 123},
        'timestamp': '2024-11-15T12:00:00',
        'priority': 1,
        'ttl_seconds': 60,
        'correlation_id': 'corr-123',
        'metadata': {'key': 'value'}
    }


@pytest.fixture
def mock_persistence_path(tmp_path):
    """Create a temporary persistence path"""
    return str(tmp_path / "messages")


class TestMessage:
    """Test Message dataclass"""

    def test_message_creation(self):
        """Test creating a message"""
        now = datetime.now()
        msg = Message(
            message_id='msg-001',
            topic='test.topic',
            sender_id='sender-001',
            payload={'data': 'test'},
            timestamp=now
        )

        assert msg.message_id == 'msg-001'
        assert msg.topic == 'test.topic'
        assert msg.sender_id == 'sender-001'
        assert msg.payload == {'data': 'test'}
        assert msg.timestamp == now
        assert msg.priority == 0
        assert msg.ttl_seconds is None
        assert msg.correlation_id is None
        assert msg.metadata is None

    def test_message_with_all_fields(self):
        """Test message with all optional fields"""
        now = datetime.now()
        msg = Message(
            message_id='msg-002',
            topic='test.topic',
            sender_id='sender-002',
            payload={'key': 'value'},
            timestamp=now,
            priority=5,
            ttl_seconds=300,
            correlation_id='corr-001',
            metadata={'meta': 'data'}
        )

        assert msg.priority == 5
        assert msg.ttl_seconds == 300
        assert msg.correlation_id == 'corr-001'
        assert msg.metadata == {'meta': 'data'}

    def test_message_to_dict(self, sample_message):
        """Test converting message to dict"""
        msg_dict = sample_message.to_dict()

        assert msg_dict['message_id'] == 'msg-123'
        assert msg_dict['topic'] == 'test.topic'
        assert msg_dict['sender_id'] == 'sender-001'
        assert msg_dict['payload'] == {'data': 'test'}
        assert 'timestamp' in msg_dict
        assert isinstance(msg_dict['timestamp'], str)

    def test_message_to_dict_with_none_metadata(self):
        """Test to_dict with None metadata"""
        msg = Message(
            message_id='msg-003',
            topic='test',
            sender_id='sender',
            payload={},
            timestamp=datetime.now(),
            metadata=None
        )

        msg_dict = msg.to_dict()
        assert msg_dict['metadata'] == {}

    def test_message_from_dict(self, sample_message_dict):
        """Test creating message from dict"""
        msg = Message.from_dict(sample_message_dict)

        assert msg.message_id == 'msg-456'
        assert msg.topic == 'test.other'
        assert msg.sender_id == 'sender-002'
        assert msg.payload == {'value': 123}
        assert msg.priority == 1
        assert msg.ttl_seconds == 60
        assert msg.correlation_id == 'corr-123'
        assert msg.metadata == {'key': 'value'}

    def test_message_from_dict_timestamp_parsing(self, sample_message_dict):
        """Test timestamp is parsed correctly from dict"""
        msg = Message.from_dict(sample_message_dict)
        assert isinstance(msg.timestamp, datetime)

    def test_message_is_expired_no_ttl(self, sample_message):
        """Test is_expired returns False when no TTL"""
        assert sample_message.is_expired() is False

    def test_message_is_expired_not_expired(self):
        """Test is_expired returns False when not expired"""
        msg = Message(
            message_id='msg-004',
            topic='test',
            sender_id='sender',
            payload={},
            timestamp=datetime.now(),
            ttl_seconds=300  # 5 minutes
        )

        assert msg.is_expired() is False

    def test_message_is_expired_expired(self):
        """Test is_expired returns True when expired"""
        past_time = datetime.now() - timedelta(seconds=120)
        msg = Message(
            message_id='msg-005',
            topic='test',
            sender_id='sender',
            payload={},
            timestamp=past_time,
            ttl_seconds=60  # 1 minute
        )

        assert msg.is_expired() is True

    def test_message_roundtrip_dict(self, sample_message):
        """Test message to_dict and from_dict roundtrip"""
        msg_dict = sample_message.to_dict()
        restored = Message.from_dict(msg_dict)

        assert restored.message_id == sample_message.message_id
        assert restored.topic == sample_message.topic
        assert restored.sender_id == sample_message.sender_id
        assert restored.payload == sample_message.payload


class TestMessageBusInit:
    """Test MessageBus initialization"""

    def test_init_default_path(self):
        """Test initialization with default path"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus.persistence_path == Path("./data/messages")

    def test_init_custom_path(self, mock_persistence_path):
        """Test initialization with custom path"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus(persistence_path=mock_persistence_path)

            assert str(bus.persistence_path) == mock_persistence_path

    def test_init_creates_directory(self):
        """Test initialization creates persistence directory"""
        with patch('agents.base.message_bus.Path.mkdir') as mock_mkdir:
            bus = MessageBus()

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_init_internal_structures(self):
        """Test initialization creates internal data structures"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert hasattr(bus, '_subscribers')
            assert hasattr(bus, '_handlers')
            assert hasattr(bus, '_message_queues')
            assert hasattr(bus, '_dead_letter_queue')
            assert hasattr(bus, '_message_history')
            assert hasattr(bus, '_stats')

    def test_init_stats(self):
        """Test initialization sets stats to zero"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus._stats['published'] == 0
            assert bus._stats['delivered'] == 0
            assert bus._stats['failed'] == 0
            assert bus._stats['dead_letters'] == 0

    def test_init_not_running(self):
        """Test bus is not running after init"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus._running is False


class TestMessageBusSubscribe:
    """Test subscribe method"""

    @pytest.mark.asyncio
    async def test_subscribe_success(self):
        """Test subscribing to a topic"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            result = await bus.subscribe('agent-001', 'test.topic', handler)

            assert result is True
            assert 'agent-001' in bus._subscribers['test.topic']
            assert 'agent-001' in bus._handlers

    @pytest.mark.asyncio
    async def test_subscribe_multiple_subscribers(self):
        """Test multiple subscribers to same topic"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler1(msg: Message) -> bool:
                return True

            async def handler2(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.topic', handler1)
            await bus.subscribe('agent-002', 'test.topic', handler2)

            assert 'agent-001' in bus._subscribers['test.topic']
            assert 'agent-002' in bus._subscribers['test.topic']

    @pytest.mark.asyncio
    async def test_subscribe_wildcard_topic(self):
        """Test subscribing to wildcard topic"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            result = await bus.subscribe('agent-001', 'test.*', handler)

            assert result is True
            assert 'agent-001' in bus._subscribers['test.*']

    @pytest.mark.asyncio
    async def test_subscribe_starts_worker_when_running(self):
        """Test subscribe starts worker if bus is running"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch('asyncio.create_task') as mock_create_task:

            bus = MessageBus()
            bus._running = True

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.topic', handler)

            # Worker task should be created
            assert mock_create_task.called


class TestMessageBusUnsubscribe:
    """Test unsubscribe method"""

    @pytest.mark.asyncio
    async def test_unsubscribe_success(self):
        """Test unsubscribing from a topic"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.topic', handler)
            result = await bus.unsubscribe('agent-001', 'test.topic')

            assert result is True
            assert 'agent-001' not in bus._subscribers['test.topic']

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self):
        """Test unsubscribe removes handler when no more subscriptions"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.topic', handler)
            await bus.unsubscribe('agent-001', 'test.topic')

            assert 'agent-001' not in bus._handlers

    @pytest.mark.asyncio
    async def test_unsubscribe_keeps_handler_for_other_topics(self):
        """Test unsubscribe keeps handler if subscribed to other topics"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'topic1', handler)
            await bus.subscribe('agent-001', 'topic2', handler)
            await bus.unsubscribe('agent-001', 'topic1')

            # Handler should still exist for topic2
            assert 'agent-001' in bus._handlers
            assert 'agent-001' in bus._subscribers['topic2']

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_topic(self):
        """Test unsubscribing from non-existent topic"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            result = await bus.unsubscribe('agent-001', 'nonexistent')

            assert result is True  # Should not raise error


class TestMessageBusPublish:
    """Test publish method"""

    @pytest.mark.asyncio
    async def test_publish_creates_message(self):
        """Test publish creates a message"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            msg_id = await bus.publish(
                topic='test.topic',
                sender_id='sender-001',
                payload={'data': 'test'}
            )

            assert msg_id is not None
            assert len(bus._message_history) == 1

    @pytest.mark.asyncio
    async def test_publish_with_all_params(self):
        """Test publish with all optional parameters"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            msg_id = await bus.publish(
                topic='test.topic',
                sender_id='sender-001',
                payload={'data': 'test'},
                priority=5,
                ttl_seconds=300,
                correlation_id='corr-123',
                metadata={'key': 'value'}
            )

            assert msg_id is not None
            msg = bus._message_history[0]
            assert msg.priority == 5
            assert msg.ttl_seconds == 300
            assert msg.correlation_id == 'corr-123'

    @pytest.mark.asyncio
    async def test_publish_increments_stats(self):
        """Test publish increments published counter"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()
            initial_count = bus._stats['published']

            await bus.publish('test.topic', 'sender-001', {'data': 'test'})

            assert bus._stats['published'] == initial_count + 1

    @pytest.mark.asyncio
    async def test_publish_persists_message(self):
        """Test publish persists message"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock) as mock_persist, \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            await bus.publish('test.topic', 'sender-001', {'data': 'test'})

            mock_persist.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_routes_message(self):
        """Test publish routes message"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock) as mock_route:

            bus = MessageBus()

            await bus.publish('test.topic', 'sender-001', {'data': 'test'})

            mock_route.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_limits_history(self):
        """Test publish limits message history"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()
            bus._max_history = 10

            # Publish more than max
            for i in range(15):
                await bus.publish('test.topic', 'sender', {'id': i})

            assert len(bus._message_history) == 10


class TestMessageBusRouting:
    """Test message routing logic"""

    @pytest.mark.asyncio
    async def test_route_message_to_subscriber(self):
        """Test routing message to exact subscriber"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.topic', handler)

            msg = Message(
                message_id='msg-001',
                topic='test.topic',
                sender_id='sender',
                payload={},
                timestamp=datetime.now()
            )

            await bus._route_message(msg)

            # Message should be in queue
            assert not bus._message_queues['agent-001'].empty()

    @pytest.mark.asyncio
    async def test_route_message_wildcard(self):
        """Test routing with wildcard subscription"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            async def handler(msg: Message) -> bool:
                return True

            await bus.subscribe('agent-001', 'test.*', handler)

            msg = Message(
                message_id='msg-001',
                topic='test.anything',
                sender_id='sender',
                payload={},
                timestamp=datetime.now()
            )

            await bus._route_message(msg)

            assert not bus._message_queues['agent-001'].empty()

    @pytest.mark.asyncio
    async def test_route_expired_message(self):
        """Test routing expired message goes to DLQ"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            past_time = datetime.now() - timedelta(seconds=120)
            msg = Message(
                message_id='msg-expired',
                topic='test.topic',
                sender_id='sender',
                payload={},
                timestamp=past_time,
                ttl_seconds=60
            )

            await bus._route_message(msg)

            # Should be in DLQ
            assert not bus._dead_letter_queue.empty()
            assert bus._stats['dead_letters'] == 1

    def test_topic_matches_exact(self):
        """Test exact topic matching"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus._topic_matches('test.topic', 'test.topic') is True
            assert bus._topic_matches('test.topic', 'other.topic') is False

    def test_topic_matches_wildcard_star(self):
        """Test wildcard * matching"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus._topic_matches('test.topic', 'test.*') is True
            assert bus._topic_matches('test.anything', 'test.*') is True
            assert bus._topic_matches('other.topic', 'test.*') is False

    def test_topic_matches_wildcard_hash(self):
        """Test wildcard # matching"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            assert bus._topic_matches('test.topic.sub', 'test.#') is True
            assert bus._topic_matches('test.anything', 'test.#') is True


class TestMessageBusStartStop:
    """Test start and stop methods"""

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Test start sets running flag"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            await bus.start()

            assert bus._running is True

    @pytest.mark.asyncio
    async def test_start_creates_dlq_worker(self):
        """Test start creates DLQ worker"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch('asyncio.create_task') as mock_create_task:

            bus = MessageBus()

            await bus.start()

            # DLQ worker should be created
            assert mock_create_task.called

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """Test start is idempotent"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            await bus.start()
            initial_tasks = len(bus._worker_tasks)

            await bus.start()  # Second start

            # Should not create duplicate tasks
            assert len(bus._worker_tasks) == initial_tasks

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """Test stop clears running flag"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            await bus.start()
            await bus.stop()

            assert bus._running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """Test stop cancels worker tasks"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            await bus.start()
            initial_tasks = bus._worker_tasks.copy()

            await bus.stop()

            # All tasks should be cancelled
            for task in initial_tasks:
                assert task.cancelled() or task.done()


class TestMessageBusStats:
    """Test get_stats method"""

    def test_get_stats_returns_dict(self):
        """Test get_stats returns dictionary"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            stats = bus.get_stats()

            assert isinstance(stats, dict)

    def test_get_stats_keys(self):
        """Test get_stats has correct keys"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            stats = bus.get_stats()

            assert 'published' in stats
            assert 'delivered' in stats
            assert 'failed' in stats
            assert 'dead_letters' in stats

    def test_get_stats_returns_copy(self):
        """Test get_stats returns a copy"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            stats = bus.get_stats()
            stats['published'] = 999

            # Original should not be modified
            assert bus._stats['published'] == 0


class TestMessageBusHistory:
    """Test get_message_history method"""

    @pytest.mark.asyncio
    async def test_get_message_history_empty(self):
        """Test get_message_history when empty"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            history = bus.get_message_history()

            assert history == []

    @pytest.mark.asyncio
    async def test_get_message_history_returns_messages(self):
        """Test get_message_history returns messages"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            await bus.publish('test.topic', 'sender', {'id': 1})
            await bus.publish('test.topic', 'sender', {'id': 2})

            history = bus.get_message_history()

            assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_message_history_with_topic_filter(self):
        """Test get_message_history with topic filter"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            await bus.publish('topic1', 'sender', {'data': 1})
            await bus.publish('topic2', 'sender', {'data': 2})
            await bus.publish('topic1', 'sender', {'data': 3})

            history = bus.get_message_history(topic='topic1')

            assert len(history) == 2
            assert all(m.topic == 'topic1' for m in history)

    @pytest.mark.asyncio
    async def test_get_message_history_with_limit(self):
        """Test get_message_history respects limit"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            for i in range(10):
                await bus.publish('test.topic', 'sender', {'id': i})

            history = bus.get_message_history(limit=5)

            assert len(history) == 5


class TestMessageBusPersistence:
    """Test persistence methods"""

    @pytest.mark.asyncio
    async def test_persist_message_creates_file(self):
        """Test _persist_message creates file"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch('aiofiles.open', new_callable=mock_open) as mock_file:

            bus = MessageBus()

            msg = Message(
                message_id='msg-001',
                topic='test',
                sender_id='sender',
                payload={},
                timestamp=datetime.now()
            )

            await bus._persist_message(msg)

            # Should attempt to open file
            mock_file.assert_called()

    @pytest.mark.asyncio
    async def test_persist_dead_letter_creates_file(self):
        """Test _persist_dead_letter creates file"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch('aiofiles.open', new_callable=mock_open) as mock_file:

            bus = MessageBus()

            msg = Message(
                message_id='msg-002',
                topic='test',
                sender_id='sender',
                payload={},
                timestamp=datetime.now()
            )

            await bus._persist_dead_letter(msg, 'test reason')

            # Should attempt to open file
            mock_file.assert_called()


class TestMessageBusEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_publish_with_empty_payload(self):
        """Test publishing with empty payload"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            msg_id = await bus.publish('test.topic', 'sender', {})

            assert msg_id is not None

    @pytest.mark.asyncio
    async def test_subscribe_with_none_handler(self):
        """Test subscribe with None handler"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            # Should not raise error
            result = await bus.subscribe('agent-001', 'test.topic', None)
            assert result is True

    @pytest.mark.asyncio
    async def test_multiple_publishes_rapid(self):
        """Test multiple rapid publishes"""
        with patch('agents.base.message_bus.Path.mkdir'), \
             patch.object(MessageBus, '_persist_message', new_callable=AsyncMock), \
             patch.object(MessageBus, '_route_message', new_callable=AsyncMock):

            bus = MessageBus()

            # Publish many messages rapidly
            tasks = [
                bus.publish(f'topic.{i}', 'sender', {'id': i})
                for i in range(20)
            ]

            msg_ids = await asyncio.gather(*tasks)

            assert len(msg_ids) == 20
            assert all(mid is not None for mid in msg_ids)

    @pytest.mark.asyncio
    async def test_unsubscribe_without_subscribe(self):
        """Test unsubscribe without prior subscribe"""
        with patch('agents.base.message_bus.Path.mkdir'):
            bus = MessageBus()

            result = await bus.unsubscribe('agent-999', 'test.topic')

            assert result is True  # Should not error
