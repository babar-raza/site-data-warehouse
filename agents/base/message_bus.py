"""Inter-agent message bus with async pub/sub, persistence, and dead letter handling."""

import asyncio
import json
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

import aiofiles


@dataclass
class Message:
    """Message object for inter-agent communication."""
    message_id: str
    topic: str
    sender_id: str
    payload: Dict[str, Any]
    timestamp: datetime
    priority: int = 0
    ttl_seconds: Optional[int] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'message_id': self.message_id,
            'topic': self.topic,
            'sender_id': self.sender_id,
            'payload': self.payload,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'ttl_seconds': self.ttl_seconds,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary."""
        return cls(
            message_id=data['message_id'],
            topic=data['topic'],
            sender_id=data['sender_id'],
            payload=data['payload'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            priority=data.get('priority', 0),
            ttl_seconds=data.get('ttl_seconds'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {})
        )

    def is_expired(self) -> bool:
        """Check if message has expired based on TTL."""
        if self.ttl_seconds is None:
            return False
        expiry = self.timestamp + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry


MessageHandler = Callable[[Message], Coroutine[Any, Any, bool]]


class MessageBus:
    """Async message bus for inter-agent communication."""

    def __init__(self, persistence_path: str = "./data/messages"):
        """Initialize message bus.
        
        Args:
            persistence_path: Path to store persisted messages
        """
        self.persistence_path = Path(persistence_path)
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        
        self._subscribers: Dict[str, Set[str]] = defaultdict(set)
        self._handlers: Dict[str, MessageHandler] = {}
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(lambda: asyncio.Queue())
        self._dead_letter_queue: asyncio.Queue = asyncio.Queue()
        
        self._message_history: List[Message] = []
        self._max_history = 1000
        
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        
        self._stats = {
            'published': 0,
            'delivered': 0,
            'failed': 0,
            'dead_letters': 0
        }

    async def start(self):
        """Start message bus workers."""
        if self._running:
            return
        
        self._running = True
        
        # Start worker for each subscriber
        for subscriber_id in self._handlers:
            task = asyncio.create_task(self._process_messages(subscriber_id))
            self._worker_tasks.append(task)
        
        # Start dead letter processor
        dlq_task = asyncio.create_task(self._process_dead_letters())
        self._worker_tasks.append(dlq_task)

    async def stop(self):
        """Stop message bus workers."""
        self._running = False
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

    async def subscribe(
        self,
        subscriber_id: str,
        topic: str,
        handler: MessageHandler
    ) -> bool:
        """Subscribe to a topic.
        
        Args:
            subscriber_id: Unique identifier for subscriber
            topic: Topic to subscribe to (supports wildcards)
            handler: Async handler function for messages
            
        Returns:
            True if subscription successful
        """
        self._subscribers[topic].add(subscriber_id)
        self._handlers[subscriber_id] = handler
        
        # Start worker if bus is running and worker doesn't exist
        if self._running and not any(
            subscriber_id in str(task) for task in self._worker_tasks
        ):
            task = asyncio.create_task(self._process_messages(subscriber_id))
            self._worker_tasks.append(task)
        
        return True

    async def unsubscribe(self, subscriber_id: str, topic: str) -> bool:
        """Unsubscribe from a topic.
        
        Args:
            subscriber_id: Subscriber identifier
            topic: Topic to unsubscribe from
            
        Returns:
            True if unsubscription successful
        """
        if topic in self._subscribers:
            self._subscribers[topic].discard(subscriber_id)
            
            # Remove from all topics if no longer subscribed to any
            if not any(subscriber_id in subs for subs in self._subscribers.values()):
                if subscriber_id in self._handlers:
                    del self._handlers[subscriber_id]
        
        return True

    async def publish(
        self,
        topic: str,
        sender_id: str,
        payload: Dict[str, Any],
        priority: int = 0,
        ttl_seconds: Optional[int] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Publish a message to a topic.
        
        Args:
            topic: Topic to publish to
            sender_id: Sender identifier
            payload: Message payload
            priority: Message priority (higher = more important)
            ttl_seconds: Time to live in seconds
            correlation_id: Optional correlation ID for message chains
            metadata: Optional metadata
            
        Returns:
            Message ID
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            topic=topic,
            sender_id=sender_id,
            payload=payload,
            timestamp=datetime.now(),
            priority=priority,
            ttl_seconds=ttl_seconds,
            correlation_id=correlation_id,
            metadata=metadata
        )
        
        # Store in history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
        
        # Persist message
        await self._persist_message(message)
        
        # Route to subscribers
        await self._route_message(message)
        
        self._stats['published'] += 1
        
        return message.message_id

    async def _route_message(self, message: Message):
        """Route message to appropriate subscribers.
        
        Args:
            message: Message to route
        """
        # Check if expired
        if message.is_expired():
            await self._dead_letter_queue.put((message, "expired"))
            self._stats['dead_letters'] += 1
            return
        
        # Find matching subscribers
        subscribers = set()
        
        # Exact match
        if message.topic in self._subscribers:
            subscribers.update(self._subscribers[message.topic])
        
        # Wildcard match (simple implementation)
        for topic_pattern in self._subscribers:
            if self._topic_matches(message.topic, topic_pattern):
                subscribers.update(self._subscribers[topic_pattern])
        
        # Queue message for each subscriber
        for subscriber_id in subscribers:
            if subscriber_id in self._handlers:
                await self._message_queues[subscriber_id].put(message)

    def _topic_matches(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern.
        
        Args:
            topic: Topic to check
            pattern: Pattern to match against (supports * and #)
            
        Returns:
            True if matches
        """
        if pattern == topic:
            return True
        
        if '*' in pattern or '#' in pattern:
            # Simple wildcard matching
            pattern_parts = pattern.split('.')
            topic_parts = topic.split('.')
            
            if len(pattern_parts) != len(topic_parts) and '#' not in pattern:
                return False
            
            for p_part, t_part in zip(pattern_parts, topic_parts):
                if p_part == '#':
                    return True
                if p_part != '*' and p_part != t_part:
                    return False
            
            return True
        
        return False

    async def _process_messages(self, subscriber_id: str):
        """Process messages for a subscriber.
        
        Args:
            subscriber_id: Subscriber identifier
        """
        queue = self._message_queues[subscriber_id]
        handler = self._handlers[subscriber_id]
        
        while self._running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                
                # Check expiry again
                if message.is_expired():
                    await self._dead_letter_queue.put((message, "expired_on_delivery"))
                    self._stats['dead_letters'] += 1
                    continue
                
                # Process message
                try:
                    success = await handler(message)
                    if success:
                        self._stats['delivered'] += 1
                    else:
                        await self._dead_letter_queue.put((message, "handler_returned_false"))
                        self._stats['failed'] += 1
                except Exception as e:
                    await self._dead_letter_queue.put((message, f"handler_exception: {str(e)}"))
                    self._stats['failed'] += 1
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error in message processor for {subscriber_id}: {e}")

    async def _process_dead_letters(self):
        """Process dead letter queue."""
        while self._running:
            try:
                message, reason = await asyncio.wait_for(
                    self._dead_letter_queue.get(),
                    timeout=1.0
                )
                
                # Log dead letter
                await self._persist_dead_letter(message, reason)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error in dead letter processor: {e}")

    async def _persist_message(self, message: Message):
        """Persist message to disk.
        
        Args:
            message: Message to persist
        """
        date_str = message.timestamp.strftime("%Y%m%d")
        message_dir = self.persistence_path / date_str
        message_dir.mkdir(exist_ok=True)
        
        message_file = message_dir / f"{message.message_id}.json"
        
        try:
            async with aiofiles.open(message_file, 'w') as f:
                await f.write(json.dumps(message.to_dict(), indent=2))
        except Exception as e:
            print(f"Error persisting message {message.message_id}: {e}")

    async def _persist_dead_letter(self, message: Message, reason: str):
        """Persist dead letter message.
        
        Args:
            message: Message that failed
            reason: Reason for failure
        """
        dlq_dir = self.persistence_path / "dead_letters"
        dlq_dir.mkdir(exist_ok=True)
        
        dlq_file = dlq_dir / f"{message.message_id}.json"
        
        data = message.to_dict()
        data['dead_letter_reason'] = reason
        data['dead_letter_timestamp'] = datetime.now().isoformat()
        
        try:
            async with aiofiles.open(dlq_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error persisting dead letter {message.message_id}: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Get message bus statistics.
        
        Returns:
            Statistics dictionary
        """
        return self._stats.copy()

    def get_message_history(self, topic: Optional[str] = None, limit: int = 100) -> List[Message]:
        """Get message history.
        
        Args:
            topic: Optional topic filter
            limit: Maximum number of messages to return
            
        Returns:
            List of messages
        """
        history = self._message_history
        
        if topic:
            history = [m for m in history if m.topic == topic]
        
        return history[-limit:]


async def main():
    """Test message bus."""
    print("Testing Message Bus...")
    
    bus = MessageBus()
    
    # Test handler
    received_messages = []
    
    async def test_handler(message: Message) -> bool:
        received_messages.append(message)
        return True
    
    # Subscribe
    await bus.subscribe("agent_001", "test.topic", test_handler)
    await bus.subscribe("agent_002", "test.*", test_handler)
    print("✓ Subscribed to topics")
    
    # Start bus
    await bus.start()
    print("✓ Message bus started")
    
    # Publish messages
    msg_id1 = await bus.publish("test.topic", "sender_001", {"data": "hello"})
    msg_id2 = await bus.publish("test.other", "sender_001", {"data": "world"})
    print("✓ Published messages")
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    print(f"✓ Received {len(received_messages)} messages")
    
    # Check stats
    stats = bus.get_stats()
    print(f"✓ Stats: {stats}")
    
    # Test expired message
    await bus.publish("test.topic", "sender_001", {"data": "expired"}, ttl_seconds=0)
    await asyncio.sleep(0.1)
    
    # Stop bus
    await bus.stop()
    print("✓ Message bus stopped")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
