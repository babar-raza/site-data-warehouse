"""
Comprehensive tests for AgentContract base class (MOCK MODE)

Tests agent interface, status management, and health checks using mocks.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import asyncio

from agents.base.agent_contract import (
    AgentContract,
    AgentStatus,
    AgentHealth,
    AgentMetadata
)


class ConcreteAgent(AgentContract):
    """Concrete implementation for testing abstract AgentContract"""

    def __init__(self, agent_id: str, agent_type: str, config=None):
        super().__init__(agent_id, agent_type, config)
        self.initialize_called = False
        self.process_called = False
        self.shutdown_called = False

    async def initialize(self) -> bool:
        """Concrete initialize implementation"""
        self.initialize_called = True
        self._start_time = datetime.now()
        self._set_status(AgentStatus.RUNNING)
        return True

    async def process(self, input_data: dict) -> dict:
        """Concrete process implementation"""
        self.process_called = True
        self._set_status(AgentStatus.PROCESSING)

        if 'raise_error' in input_data:
            self._increment_error_count()
            raise ValueError("Processing error")

        self._increment_processed_count()
        self._set_status(AgentStatus.IDLE)

        return {
            'status': 'success',
            'processed': input_data
        }

    async def health_check(self) -> AgentHealth:
        """Concrete health_check implementation"""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()

        return AgentHealth(
            agent_id=self.agent_id,
            status=self._status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=5.0,
            metadata={}
        )

    async def shutdown(self) -> bool:
        """Concrete shutdown implementation"""
        self.shutdown_called = True
        self._set_status(AgentStatus.SHUTDOWN)
        return True


class TestAgentStatus:
    """Test AgentStatus enum"""

    def test_agent_status_values(self):
        """Test all agent status enum values"""
        assert AgentStatus.INITIALIZED.value == "initialized"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.PROCESSING.value == "processing"
        assert AgentStatus.ERROR.value == "error"
        assert AgentStatus.SHUTDOWN.value == "shutdown"

    def test_agent_status_comparison(self):
        """Test agent status comparison"""
        status1 = AgentStatus.RUNNING
        status2 = AgentStatus.RUNNING
        status3 = AgentStatus.IDLE

        assert status1 == status2
        assert status1 != status3


class TestAgentHealth:
    """Test AgentHealth dataclass"""

    def test_agent_health_creation(self):
        """Test creating AgentHealth instance"""
        now = datetime.now()
        health = AgentHealth(
            agent_id='agent-001',
            status=AgentStatus.RUNNING,
            uptime_seconds=120.5,
            last_heartbeat=now,
            error_count=2,
            processed_count=50,
            memory_usage_mb=256.0,
            cpu_percent=15.5,
            metadata={'key': 'value'}
        )

        assert health.agent_id == 'agent-001'
        assert health.status == AgentStatus.RUNNING
        assert health.uptime_seconds == 120.5
        assert health.error_count == 2
        assert health.processed_count == 50
        assert health.memory_usage_mb == 256.0
        assert health.cpu_percent == 15.5
        assert health.metadata == {'key': 'value'}

    def test_agent_health_fields(self):
        """Test all AgentHealth fields are accessible"""
        health = AgentHealth(
            agent_id='test',
            status=AgentStatus.IDLE,
            uptime_seconds=0.0,
            last_heartbeat=datetime.now(),
            error_count=0,
            processed_count=0,
            memory_usage_mb=0.0,
            cpu_percent=0.0,
            metadata={}
        )

        assert hasattr(health, 'agent_id')
        assert hasattr(health, 'status')
        assert hasattr(health, 'uptime_seconds')
        assert hasattr(health, 'last_heartbeat')
        assert hasattr(health, 'error_count')
        assert hasattr(health, 'processed_count')
        assert hasattr(health, 'memory_usage_mb')
        assert hasattr(health, 'cpu_percent')
        assert hasattr(health, 'metadata')


class TestAgentMetadata:
    """Test AgentMetadata dataclass"""

    def test_agent_metadata_creation(self):
        """Test creating AgentMetadata instance"""
        now = datetime.now()
        metadata = AgentMetadata(
            agent_id='agent-001',
            agent_type='watcher',
            version='1.0.0',
            capabilities=['detect', 'analyze'],
            dependencies=['database', 'cache'],
            config={'key': 'value'},
            created_at=now,
            updated_at=now
        )

        assert metadata.agent_id == 'agent-001'
        assert metadata.agent_type == 'watcher'
        assert metadata.version == '1.0.0'
        assert metadata.capabilities == ['detect', 'analyze']
        assert metadata.dependencies == ['database', 'cache']
        assert metadata.config == {'key': 'value'}

    def test_agent_metadata_fields(self):
        """Test all AgentMetadata fields"""
        now = datetime.now()
        metadata = AgentMetadata(
            agent_id='test',
            agent_type='test',
            version='1.0',
            capabilities=[],
            dependencies=[],
            config={},
            created_at=now,
            updated_at=now
        )

        assert hasattr(metadata, 'agent_id')
        assert hasattr(metadata, 'agent_type')
        assert hasattr(metadata, 'version')
        assert hasattr(metadata, 'capabilities')
        assert hasattr(metadata, 'dependencies')
        assert hasattr(metadata, 'config')
        assert hasattr(metadata, 'created_at')
        assert hasattr(metadata, 'updated_at')


class TestAgentContractInit:
    """Test AgentContract initialization"""

    def test_init_with_minimal_params(self):
        """Test initialization with minimal parameters"""
        agent = ConcreteAgent('agent-001', 'test')

        assert agent.agent_id == 'agent-001'
        assert agent.agent_type == 'test'
        assert agent.config == {}
        assert agent.status == AgentStatus.INITIALIZED
        assert agent._start_time is None
        assert agent._error_count == 0
        assert agent._processed_count == 0

    def test_init_with_config(self):
        """Test initialization with config"""
        config = {
            'version': '2.0.0',
            'capabilities': ['test'],
            'timeout': 30
        }
        agent = ConcreteAgent('agent-002', 'watcher', config)

        assert agent.config == config
        assert agent.config['version'] == '2.0.0'
        assert agent.config['timeout'] == 30

    def test_init_status_is_initialized(self):
        """Test initial status is INITIALIZED"""
        agent = ConcreteAgent('agent-003', 'test')
        assert agent.status == AgentStatus.INITIALIZED

    def test_init_counters_are_zero(self):
        """Test counters start at zero"""
        agent = ConcreteAgent('agent-004', 'test')
        assert agent._error_count == 0
        assert agent._processed_count == 0

    def test_init_start_time_is_none(self):
        """Test start_time is None before initialization"""
        agent = ConcreteAgent('agent-005', 'test')
        assert agent._start_time is None


class TestAgentContractInitialize:
    """Test initialize method"""

    @pytest.mark.asyncio
    async def test_initialize_returns_true(self):
        """Test initialize returns True on success"""
        agent = ConcreteAgent('agent-001', 'test')
        result = await agent.initialize()

        assert result is True
        assert agent.initialize_called is True

    @pytest.mark.asyncio
    async def test_initialize_sets_status(self):
        """Test initialize sets status to RUNNING"""
        agent = ConcreteAgent('agent-002', 'test')
        await agent.initialize()

        assert agent.status == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_initialize_sets_start_time(self):
        """Test initialize sets start_time"""
        agent = ConcreteAgent('agent-003', 'test')
        await agent.initialize()

        assert agent._start_time is not None
        assert isinstance(agent._start_time, datetime)

    @pytest.mark.asyncio
    async def test_initialize_is_async(self):
        """Test initialize is async method"""
        agent = ConcreteAgent('agent-004', 'test')
        result = agent.initialize()

        assert asyncio.iscoroutine(result)
        await result  # Clean up


class TestAgentContractProcess:
    """Test process method"""

    @pytest.mark.asyncio
    async def test_process_success(self):
        """Test successful processing"""
        agent = ConcreteAgent('agent-001', 'test')
        await agent.initialize()

        input_data = {'key': 'value'}
        result = await agent.process(input_data)

        assert result['status'] == 'success'
        assert result['processed'] == input_data
        assert agent.process_called is True

    @pytest.mark.asyncio
    async def test_process_increments_counter(self):
        """Test process increments processed counter"""
        agent = ConcreteAgent('agent-002', 'test')
        await agent.initialize()

        initial_count = agent._processed_count
        await agent.process({'data': 'test'})

        assert agent._processed_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_process_sets_status(self):
        """Test process sets status correctly"""
        agent = ConcreteAgent('agent-003', 'test')
        await agent.initialize()

        await agent.process({'data': 'test'})

        # After processing, status should be IDLE
        assert agent.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_process_with_error(self):
        """Test process handles errors"""
        agent = ConcreteAgent('agent-004', 'test')
        await agent.initialize()

        initial_errors = agent._error_count

        with pytest.raises(ValueError):
            await agent.process({'raise_error': True})

        assert agent._error_count == initial_errors + 1

    @pytest.mark.asyncio
    async def test_process_multiple_times(self):
        """Test processing multiple times"""
        agent = ConcreteAgent('agent-005', 'test')
        await agent.initialize()

        await agent.process({'data': 1})
        await agent.process({'data': 2})
        await agent.process({'data': 3})

        assert agent._processed_count == 3


class TestAgentContractHealthCheck:
    """Test health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_returns_health(self):
        """Test health_check returns AgentHealth"""
        agent = ConcreteAgent('agent-001', 'test')
        await agent.initialize()

        health = await agent.health_check()

        assert isinstance(health, AgentHealth)
        assert health.agent_id == 'agent-001'

    @pytest.mark.asyncio
    async def test_health_check_status(self):
        """Test health_check returns current status"""
        agent = ConcreteAgent('agent-002', 'test')
        await agent.initialize()

        health = await agent.health_check()
        assert health.status == AgentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_health_check_uptime(self):
        """Test health_check calculates uptime"""
        agent = ConcreteAgent('agent-003', 'test')
        await agent.initialize()

        await asyncio.sleep(0.1)  # Wait a bit
        health = await agent.health_check()

        assert health.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_health_check_counters(self):
        """Test health_check includes counters"""
        agent = ConcreteAgent('agent-004', 'test')
        await agent.initialize()

        await agent.process({'data': 'test'})
        health = await agent.health_check()

        assert health.processed_count == 1
        assert health.error_count == 0

    @pytest.mark.asyncio
    async def test_health_check_before_initialize(self):
        """Test health_check before initialization"""
        agent = ConcreteAgent('agent-005', 'test')
        health = await agent.health_check()

        assert health.uptime_seconds == 0.0
        assert health.status == AgentStatus.INITIALIZED


class TestAgentContractShutdown:
    """Test shutdown method"""

    @pytest.mark.asyncio
    async def test_shutdown_returns_true(self):
        """Test shutdown returns True"""
        agent = ConcreteAgent('agent-001', 'test')
        await agent.initialize()

        result = await agent.shutdown()
        assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_sets_status(self):
        """Test shutdown sets status to SHUTDOWN"""
        agent = ConcreteAgent('agent-002', 'test')
        await agent.initialize()

        await agent.shutdown()
        assert agent.status == AgentStatus.SHUTDOWN

    @pytest.mark.asyncio
    async def test_shutdown_called_flag(self):
        """Test shutdown sets called flag"""
        agent = ConcreteAgent('agent-003', 'test')
        await agent.initialize()

        await agent.shutdown()
        assert agent.shutdown_called is True

    @pytest.mark.asyncio
    async def test_shutdown_before_initialize(self):
        """Test shutdown can be called before initialize"""
        agent = ConcreteAgent('agent-004', 'test')

        result = await agent.shutdown()
        assert result is True


class TestAgentContractMetadata:
    """Test get_metadata method"""

    def test_get_metadata_returns_metadata(self):
        """Test get_metadata returns AgentMetadata"""
        agent = ConcreteAgent('agent-001', 'watcher')
        metadata = agent.get_metadata()

        assert isinstance(metadata, AgentMetadata)
        assert metadata.agent_id == 'agent-001'
        assert metadata.agent_type == 'watcher'

    def test_get_metadata_with_config(self):
        """Test get_metadata includes config"""
        config = {
            'version': '2.0.0',
            'capabilities': ['detect', 'analyze'],
            'dependencies': ['database']
        }
        agent = ConcreteAgent('agent-002', 'test', config)
        metadata = agent.get_metadata()

        assert metadata.version == '2.0.0'
        assert metadata.capabilities == ['detect', 'analyze']
        assert metadata.dependencies == ['database']
        assert metadata.config == config

    def test_get_metadata_default_version(self):
        """Test get_metadata uses default version"""
        agent = ConcreteAgent('agent-003', 'test')
        metadata = agent.get_metadata()

        assert metadata.version == '1.0.0'

    def test_get_metadata_default_capabilities(self):
        """Test get_metadata uses default empty capabilities"""
        agent = ConcreteAgent('agent-004', 'test')
        metadata = agent.get_metadata()

        assert metadata.capabilities == []
        assert metadata.dependencies == []

    def test_get_metadata_timestamps(self):
        """Test get_metadata includes timestamps"""
        agent = ConcreteAgent('agent-005', 'test')
        metadata = agent.get_metadata()

        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)


class TestAgentContractStatusProperty:
    """Test status property"""

    def test_status_property_getter(self):
        """Test status property returns current status"""
        agent = ConcreteAgent('agent-001', 'test')

        assert agent.status == AgentStatus.INITIALIZED

    @pytest.mark.asyncio
    async def test_status_changes_with_operations(self):
        """Test status changes with operations"""
        agent = ConcreteAgent('agent-002', 'test')

        assert agent.status == AgentStatus.INITIALIZED

        await agent.initialize()
        assert agent.status == AgentStatus.RUNNING

        await agent.shutdown()
        assert agent.status == AgentStatus.SHUTDOWN


class TestAgentContractInternalMethods:
    """Test internal/protected methods"""

    def test_set_status(self):
        """Test _set_status method"""
        agent = ConcreteAgent('agent-001', 'test')

        agent._set_status(AgentStatus.RUNNING)
        assert agent.status == AgentStatus.RUNNING

        agent._set_status(AgentStatus.ERROR)
        assert agent.status == AgentStatus.ERROR

    def test_increment_error_count(self):
        """Test _increment_error_count method"""
        agent = ConcreteAgent('agent-002', 'test')

        initial = agent._error_count
        agent._increment_error_count()
        assert agent._error_count == initial + 1

        agent._increment_error_count()
        agent._increment_error_count()
        assert agent._error_count == initial + 3

    def test_increment_processed_count(self):
        """Test _increment_processed_count method"""
        agent = ConcreteAgent('agent-003', 'test')

        initial = agent._processed_count
        agent._increment_processed_count()
        assert agent._processed_count == initial + 1

        agent._increment_processed_count()
        assert agent._processed_count == initial + 2


class TestAgentContractEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_multiple_initializations(self):
        """Test calling initialize multiple times"""
        agent = ConcreteAgent('agent-001', 'test')

        result1 = await agent.initialize()
        result2 = await agent.initialize()

        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_process_before_initialize(self):
        """Test process can be called before initialize"""
        agent = ConcreteAgent('agent-002', 'test')

        # Should not raise error
        result = await agent.process({'data': 'test'})
        assert result['status'] == 'success'

    @pytest.mark.asyncio
    async def test_multiple_shutdowns(self):
        """Test calling shutdown multiple times"""
        agent = ConcreteAgent('agent-003', 'test')
        await agent.initialize()

        result1 = await agent.shutdown()
        result2 = await agent.shutdown()

        assert result1 is True
        assert result2 is True

    def test_agent_with_none_config(self):
        """Test agent with None config"""
        agent = ConcreteAgent('agent-004', 'test', None)
        assert agent.config == {}

    def test_agent_with_empty_string_id(self):
        """Test agent with empty string ID"""
        agent = ConcreteAgent('', 'test')
        assert agent.agent_id == ''

    @pytest.mark.asyncio
    async def test_concurrent_processing(self):
        """Test concurrent process calls"""
        agent = ConcreteAgent('agent-005', 'test')
        await agent.initialize()

        # Process multiple items concurrently
        results = await asyncio.gather(
            agent.process({'id': 1}),
            agent.process({'id': 2}),
            agent.process({'id': 3})
        )

        assert len(results) == 3
        assert agent._processed_count == 3

    def test_metadata_called_multiple_times(self):
        """Test get_metadata can be called multiple times"""
        agent = ConcreteAgent('agent-006', 'test')

        metadata1 = agent.get_metadata()
        metadata2 = agent.get_metadata()

        assert metadata1.agent_id == metadata2.agent_id
        # Note: timestamps will be different
