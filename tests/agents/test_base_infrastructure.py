"""Comprehensive tests for agent base infrastructure."""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import (
    AgentContract,
    AgentHealth,
    AgentMetadata,
    AgentStatus,
)
from agents.base.agent_registry import AgentRegistry, AgentRegistration
from agents.base.message_bus import Message, MessageBus
from agents.base.state_manager import AgentState, StateManager, StateTransitionError
from agents.config import TEST_CONFIG


class TestAgent(AgentContract):
    """Test implementation of agent contract."""

    async def initialize(self) -> bool:
        """Initialize test agent."""
        self._start_time = datetime.now()
        self._set_status(AgentStatus.RUNNING)
        return True

    async def process(self, input_data: dict) -> dict:
        """Process test data."""
        self._increment_processed_count()
        return {
            "status": "processed",
            "input": input_data,
            "agent_id": self.agent_id
        }

    async def health_check(self) -> AgentHealth:
        """Return test health status."""
        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return AgentHealth(
            agent_id=self.agent_id,
            status=self.status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={}
        )

    async def shutdown(self) -> bool:
        """Shutdown test agent."""
        self._set_status(AgentStatus.SHUTDOWN)
        return True


@pytest.fixture
def state_manager():
    """Create state manager for tests."""
    manager = StateManager(storage_path=TEST_CONFIG.state_storage_path)
    yield manager
    # Cleanup
    import shutil
    if Path(TEST_CONFIG.state_storage_path).exists():
        shutil.rmtree(TEST_CONFIG.state_storage_path)


@pytest.fixture
def message_bus():
    """Create message bus for tests."""
    bus = MessageBus(persistence_path=TEST_CONFIG.message_storage_path)
    yield bus
    # Cleanup
    import shutil
    if Path(TEST_CONFIG.message_storage_path).exists():
        shutil.rmtree(TEST_CONFIG.message_storage_path)


@pytest.fixture
def agent_registry():
    """Create agent registry for tests."""
    registry = AgentRegistry(
        heartbeat_timeout_seconds=TEST_CONFIG.registry_heartbeat_timeout_seconds,
        health_check_interval_seconds=TEST_CONFIG.registry_health_check_interval_seconds,
        persistence_path=TEST_CONFIG.registry_storage_path
    )
    yield registry
    # Cleanup
    import shutil
    if Path(TEST_CONFIG.registry_storage_path).exists():
        shutil.rmtree(TEST_CONFIG.registry_storage_path)


class TestAgentContract:
    """Test agent contract implementation."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test agent initialization."""
        agent = TestAgent("test_001", "test", {"version": "1.0.0"})
        
        assert agent.agent_id == "test_001"
        assert agent.agent_type == "test"
        assert agent.status == AgentStatus.INITIALIZED
        
        success = await agent.initialize()
        assert success is True
        assert agent.status == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_agent_processing(self):
        """Test agent data processing."""
        agent = TestAgent("test_001", "test")
        await agent.initialize()
        
        result = await agent.process({"data": "test"})
        
        assert result["status"] == "processed"
        assert result["input"]["data"] == "test"
        assert result["agent_id"] == "test_001"
        assert agent._processed_count == 1

    @pytest.mark.asyncio
    async def test_agent_health_check(self):
        """Test agent health check."""
        agent = TestAgent("test_001", "test")
        await agent.initialize()
        
        health = await agent.health_check()
        
        assert health.agent_id == "test_001"
        assert health.status == AgentStatus.RUNNING
        assert health.uptime_seconds >= 0
        assert health.error_count == 0

    @pytest.mark.asyncio
    async def test_agent_metadata(self):
        """Test agent metadata."""
        agent = TestAgent("test_001", "test", {
            "version": "1.0.0",
            "capabilities": ["process", "analyze"]
        })
        
        metadata = agent.get_metadata()
        
        assert metadata.agent_id == "test_001"
        assert metadata.agent_type == "test"
        assert metadata.version == "1.0.0"
        assert "process" in metadata.capabilities

    @pytest.mark.asyncio
    async def test_agent_shutdown(self):
        """Test agent shutdown."""
        agent = TestAgent("test_001", "test")
        await agent.initialize()
        
        success = await agent.shutdown()
        
        assert success is True
        assert agent.status == AgentStatus.SHUTDOWN


class TestStateManager:
    """Test state manager functionality."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, state_manager):
        """Test agent state initialization."""
        success = await state_manager.initialize_agent(
            "agent_001",
            {"counter": 0}
        )
        
        assert success is True
        
        state = await state_manager.get_state("agent_001")
        assert state == AgentState.CREATED
        
        data = await state_manager.get_state_data("agent_001")
        assert data["counter"] == 0

    @pytest.mark.asyncio
    async def test_state_transitions(self, state_manager):
        """Test valid state transitions."""
        await state_manager.initialize_agent("agent_001")
        
        # Valid transition sequence
        await state_manager.transition("agent_001", AgentState.INITIALIZING)
        await state_manager.transition("agent_001", AgentState.READY)
        await state_manager.transition("agent_001", AgentState.ACTIVE)
        
        state = await state_manager.get_state("agent_001")
        assert state == AgentState.ACTIVE

    @pytest.mark.asyncio
    async def test_invalid_state_transition(self, state_manager):
        """Test invalid state transition is rejected."""
        await state_manager.initialize_agent("agent_001")
        
        with pytest.raises(StateTransitionError):
            await state_manager.transition("agent_001", AgentState.TERMINATED)

    @pytest.mark.asyncio
    async def test_state_data_update(self, state_manager):
        """Test state data updates."""
        await state_manager.initialize_agent("agent_001", {"counter": 0})
        
        await state_manager.update_state_data("agent_001", {"counter": 5})
        
        data = await state_manager.get_state_data("agent_001")
        assert data["counter"] == 5

    @pytest.mark.asyncio
    async def test_state_history(self, state_manager):
        """Test state history tracking."""
        await state_manager.initialize_agent("agent_001")
        
        await state_manager.transition("agent_001", AgentState.INITIALIZING)
        await state_manager.transition("agent_001", AgentState.READY)
        
        history = await state_manager.get_history("agent_001")
        
        assert len(history) >= 3
        assert history[0].state == AgentState.CREATED
        assert history[-1].state == AgentState.READY

    @pytest.mark.asyncio
    async def test_state_recovery(self, state_manager):
        """Test state recovery from persistence."""
        await state_manager.initialize_agent("agent_001", {"important": "data"})
        await state_manager.transition("agent_001", AgentState.INITIALIZING)
        
        # Create new manager instance
        manager2 = StateManager(storage_path=TEST_CONFIG.state_storage_path)
        success = await manager2.recover_agent("agent_001")
        
        assert success is True
        
        state = await manager2.get_state("agent_001")
        data = await manager2.get_state_data("agent_001")
        
        assert state == AgentState.INITIALIZING
        assert data["important"] == "data"


class TestMessageBus:
    """Test message bus functionality."""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self, message_bus):
        """Test basic publish/subscribe."""
        received_messages = []
        
        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True
        
        await message_bus.subscribe("agent_001", "test.topic", handler)
        await message_bus.start()
        
        msg_id = await message_bus.publish(
            "test.topic",
            "sender_001",
            {"data": "hello"}
        )
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        assert len(received_messages) == 1
        assert received_messages[0].topic == "test.topic"
        assert received_messages[0].payload["data"] == "hello"
        
        await message_bus.stop()

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, message_bus):
        """Test wildcard topic subscriptions."""
        received_messages = []
        
        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True
        
        await message_bus.subscribe("agent_001", "test.*", handler)
        await message_bus.start()
        
        await message_bus.publish("test.topic1", "sender", {"data": "msg1"})
        await message_bus.publish("test.topic2", "sender", {"data": "msg2"})
        await message_bus.publish("other.topic", "sender", {"data": "msg3"})
        
        await asyncio.sleep(0.2)
        
        assert len(received_messages) == 2
        
        await message_bus.stop()

    @pytest.mark.asyncio
    async def test_message_priority(self, message_bus):
        """Test message priority handling."""
        received_order = []
        
        async def handler(message: Message) -> bool:
            received_order.append(message.priority)
            return True
        
        await message_bus.subscribe("agent_001", "test.topic", handler)
        await message_bus.start()
        
        # Publish with different priorities
        await message_bus.publish("test.topic", "sender", {"n": 1}, priority=1)
        await message_bus.publish("test.topic", "sender", {"n": 2}, priority=5)
        await message_bus.publish("test.topic", "sender", {"n": 3}, priority=3)
        
        await asyncio.sleep(0.2)
        
        assert len(received_order) == 3
        
        await message_bus.stop()

    @pytest.mark.asyncio
    async def test_message_expiry(self, message_bus):
        """Test message TTL and expiry."""
        received_messages = []
        
        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True
        
        await message_bus.subscribe("agent_001", "test.topic", handler)
        await message_bus.start()
        
        # Publish expired message
        await message_bus.publish(
            "test.topic",
            "sender",
            {"data": "expired"},
            ttl_seconds=0
        )
        
        await asyncio.sleep(0.2)
        
        # Should not receive expired message
        assert len(received_messages) == 0
        
        stats = message_bus.get_stats()
        assert stats['dead_letters'] > 0
        
        await message_bus.stop()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, message_bus):
        """Test message delivery to multiple subscribers."""
        received_1 = []
        received_2 = []
        
        async def handler1(message: Message) -> bool:
            received_1.append(message)
            return True
        
        async def handler2(message: Message) -> bool:
            received_2.append(message)
            return True
        
        await message_bus.subscribe("agent_001", "test.topic", handler1)
        await message_bus.subscribe("agent_002", "test.topic", handler2)
        await message_bus.start()
        
        await message_bus.publish("test.topic", "sender", {"data": "broadcast"})
        
        await asyncio.sleep(0.2)
        
        assert len(received_1) == 1
        assert len(received_2) == 1
        
        await message_bus.stop()


class TestAgentRegistry:
    """Test agent registry functionality."""

    @pytest.mark.asyncio
    async def test_agent_registration(self, agent_registry):
        """Test agent registration."""
        await agent_registry.start()
        
        metadata = AgentMetadata(
            agent_id="agent_001",
            agent_type="worker",
            version="1.0.0",
            capabilities=["process"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        success = await agent_registry.register("agent_001", "worker", metadata)
        
        assert success is True
        
        registration = await agent_registry.get_agent("agent_001")
        assert registration is not None
        assert registration.agent_id == "agent_001"
        
        await agent_registry.stop()

    @pytest.mark.asyncio
    async def test_agent_discovery(self, agent_registry):
        """Test agent discovery."""
        await agent_registry.start()
        
        # Register multiple agents
        for i in range(3):
            metadata = AgentMetadata(
                agent_id=f"agent_{i:03d}",
                agent_type="worker",
                version="1.0.0",
                capabilities=["process", "analyze"],
                dependencies=[],
                config={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            await agent_registry.register(f"agent_{i:03d}", "worker", metadata)
        
        # Discover by type
        agents = await agent_registry.discover(agent_type="worker")
        assert len(agents) == 3
        
        # Discover by capability
        agents = await agent_registry.discover(capability="analyze")
        assert len(agents) == 3
        
        await agent_registry.stop()

    @pytest.mark.asyncio
    async def test_agent_heartbeat(self, agent_registry):
        """Test agent heartbeat tracking."""
        await agent_registry.start()
        
        metadata = AgentMetadata(
            agent_id="agent_001",
            agent_type="worker",
            version="1.0.0",
            capabilities=[],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await agent_registry.register("agent_001", "worker", metadata)
        
        health = AgentHealth(
            agent_id="agent_001",
            status=AgentStatus.RUNNING,
            uptime_seconds=100.0,
            last_heartbeat=datetime.now(),
            error_count=0,
            processed_count=10,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={}
        )
        
        success = await agent_registry.heartbeat("agent_001", health)
        assert success is True
        
        registration = await agent_registry.get_agent("agent_001")
        assert registration.health is not None
        assert registration.health.processed_count == 10
        
        await agent_registry.stop()

    @pytest.mark.asyncio
    async def test_agent_selection(self, agent_registry):
        """Test agent selection for task assignment."""
        await agent_registry.start()
        
        # Register agents with different loads
        for i in range(3):
            metadata = AgentMetadata(
                agent_id=f"agent_{i:03d}",
                agent_type="worker",
                version="1.0.0",
                capabilities=["process"],
                dependencies=[],
                config={},
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            await agent_registry.register(f"agent_{i:03d}", "worker", metadata)
            
            health = AgentHealth(
                agent_id=f"agent_{i:03d}",
                status=AgentStatus.IDLE,
                uptime_seconds=100.0,
                last_heartbeat=datetime.now(),
                error_count=0,
                processed_count=i * 10,  # Different loads
                memory_usage_mb=100.0,
                cpu_percent=10.0,
                metadata={}
            )
            
            await agent_registry.heartbeat(f"agent_{i:03d}", health)
        
        # Select agent (should pick least loaded)
        selected = await agent_registry.select_agent(
            agent_type="worker",
            capability="process",
            load_balance=True
        )
        
        assert selected == "agent_000"  # Lowest processed count
        
        await agent_registry.stop()

    @pytest.mark.asyncio
    async def test_failover_agent(self, agent_registry):
        """Test failover agent selection."""
        await agent_registry.start()
        
        # Register primary agent
        metadata1 = AgentMetadata(
            agent_id="agent_primary",
            agent_type="worker",
            version="1.0.0",
            capabilities=["process", "special"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        await agent_registry.register("agent_primary", "worker", metadata1)
        
        # Register failover agent
        metadata2 = AgentMetadata(
            agent_id="agent_backup",
            agent_type="worker",
            version="1.0.0",
            capabilities=["process", "special"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        await agent_registry.register("agent_backup", "worker", metadata2)
        
        health = AgentHealth(
            agent_id="agent_backup",
            status=AgentStatus.IDLE,
            uptime_seconds=100.0,
            last_heartbeat=datetime.now(),
            error_count=0,
            processed_count=0,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={}
        )
        await agent_registry.heartbeat("agent_backup", health)
        
        # Get failover for primary
        failover = await agent_registry.get_failover_agent("agent_primary")
        
        assert failover == "agent_backup"
        
        await agent_registry.stop()


class TestIntegration:
    """Integration tests for complete system."""

    @pytest.mark.asyncio
    async def test_full_agent_lifecycle(self, state_manager, message_bus, agent_registry):
        """Test complete agent lifecycle."""
        # Initialize systems
        await message_bus.start()
        await agent_registry.start()
        
        # Create and initialize agent
        agent = TestAgent("agent_001", "worker", {
            "version": "1.0.0",
            "capabilities": ["process"]
        })
        
        await agent.initialize()
        
        # Register with state manager
        await state_manager.initialize_agent(agent.agent_id, {"status": "initialized"})
        await state_manager.transition(agent.agent_id, AgentState.INITIALIZING)
        await state_manager.transition(agent.agent_id, AgentState.READY)
        
        # Register with registry
        metadata = agent.get_metadata()
        await agent_registry.register(agent.agent_id, agent.agent_type, metadata)
        
        # Subscribe to messages
        processed_messages = []
        
        async def message_handler(message: Message) -> bool:
            result = await agent.process(message.payload)
            processed_messages.append(result)
            return True
        
        await message_bus.subscribe(agent.agent_id, "task.*", message_handler)
        
        # Publish task
        await message_bus.publish(
            "task.process",
            "controller",
            {"data": "test_data"}
        )
        
        # Wait for processing
        await asyncio.sleep(0.3)
        
        # Verify processing
        assert len(processed_messages) == 1
        assert processed_messages[0]["status"] == "processed"
        
        # Send heartbeat
        health = await agent.health_check()
        await agent_registry.heartbeat(agent.agent_id, health)
        
        # Verify health
        registration = await agent_registry.get_agent(agent.agent_id)
        assert registration.health.processed_count == 1
        
        # Shutdown
        await agent.shutdown()
        await state_manager.transition(agent.agent_id, AgentState.SHUTTING_DOWN)
        await state_manager.transition(agent.agent_id, AgentState.TERMINATED)
        
        # Cleanup
        await message_bus.stop()
        await agent_registry.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
