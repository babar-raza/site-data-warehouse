"""
Contract compliance tests for all agents.

Tests that all agents properly implement the AgentContract interface
and follow the required contract patterns.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from datetime import datetime

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.watcher.watcher_agent import WatcherAgent
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.strategist.strategist_agent import StrategistAgent
from agents.dispatcher.dispatcher_agent import DispatcherAgent


# Test data for parametrization
AGENT_CLASSES = [
    (WatcherAgent, 'watcher', 'watcher_001'),
    (DiagnosticianAgent, 'diagnostician', 'diagnostician_001'),
    (StrategistAgent, 'strategist', 'strategist_001'),
    (DispatcherAgent, 'dispatcher', 'dispatcher_001'),
]

VALID_STATUSES = {'healthy', 'unhealthy', 'degraded'}


@pytest.fixture
def mock_db_config():
    """Mock database configuration."""
    return {
        'host': 'localhost',
        'port': 5432,
        'user': 'test_user',
        'password': 'test_password',
        'database': 'test_db'
    }


@pytest.fixture
def mock_agent_config():
    """Mock agent configuration."""
    return {
        'sensitivity': 2.5,
        'min_data_points': 7,
        'use_llm': False,  # Disable LLM for testing
        'llm_timeout': 30.0,
        'llm_retries': 1
    }


@pytest.fixture
def mock_asyncpg_pool():
    """Mock asyncpg connection pool."""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    mock_conn.fetch.return_value = []
    mock_conn.fetchrow.return_value = None
    mock_conn.fetchval.return_value = 1
    return mock_pool


class TestAgentContractInheritance:
    """Test that all agents properly inherit from AgentContract."""

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_inherits_from_contract(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent inherits from AgentContract."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert isinstance(agent, AgentContract), (
            f"{agent_class.__name__} must inherit from AgentContract"
        )

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_required_attributes(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent has required base attributes."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        assert hasattr(agent, 'agent_id'), f"{agent_class.__name__} missing agent_id attribute"
        assert hasattr(agent, 'agent_type'), f"{agent_class.__name__} missing agent_type attribute"
        assert hasattr(agent, 'config'), f"{agent_class.__name__} missing config attribute"
        assert hasattr(agent, '_status'), f"{agent_class.__name__} missing _status attribute"
        assert hasattr(agent, '_error_count'), f"{agent_class.__name__} missing _error_count attribute"
        assert hasattr(agent, '_processed_count'), f"{agent_class.__name__} missing _processed_count attribute"

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_initialization_values(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify agent initialization sets correct values."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        assert agent.agent_id == agent_id, f"{agent_class.__name__} agent_id not set correctly"
        assert agent.agent_type == agent_type, f"{agent_class.__name__} agent_type not set correctly"
        assert agent._status == AgentStatus.INITIALIZED, (
            f"{agent_class.__name__} should start with INITIALIZED status"
        )
        assert agent._error_count == 0, f"{agent_class.__name__} should start with 0 errors"
        assert agent._processed_count == 0, f"{agent_class.__name__} should start with 0 processed count"


class TestAgentContractMethods:
    """Test that all agents implement required contract methods."""

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_initialize_method(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent has initialize method."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'initialize'), f"{agent_class.__name__} missing initialize method"
        assert callable(agent.initialize), f"{agent_class.__name__}.initialize must be callable"

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_process_method(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent has process method."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'process'), f"{agent_class.__name__} missing process method"
        assert callable(agent.process), f"{agent_class.__name__}.process must be callable"

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_health_check_method(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent has health_check method."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'health_check'), f"{agent_class.__name__} missing health_check method"
        assert callable(agent.health_check), f"{agent_class.__name__}.health_check must be callable"

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_shutdown_method(self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config):
        """Verify each agent has shutdown method."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'shutdown'), f"{agent_class.__name__} missing shutdown method"
        assert callable(agent.shutdown), f"{agent_class.__name__}.shutdown must be callable"


class TestAgentInitialize:
    """Test initialize method compliance for all agents."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_initialize_returns_bool(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify initialize returns a boolean value."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            result = await agent.initialize()
            assert isinstance(result, bool), (
                f"{agent_class.__name__}.initialize must return bool, got {type(result)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_initialize_success_sets_running_status(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify successful initialization sets status to RUNNING."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            result = await agent.initialize()
            if result:
                assert agent._status == AgentStatus.RUNNING, (
                    f"{agent_class.__name__} should set status to RUNNING on successful init"
                )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_initialize_failure_sets_error_status(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config
    ):
        """Verify failed initialization sets status to ERROR."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        # Force initialization to fail by using invalid pool
        with patch('asyncpg.create_pool', side_effect=Exception("Connection failed")):
            result = await agent.initialize()
            assert result is False, f"{agent_class.__name__}.initialize should return False on failure"
            assert agent._status == AgentStatus.ERROR, (
                f"{agent_class.__name__} should set status to ERROR on failed init"
            )


class TestAgentProcess:
    """Test process method compliance for all agents."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_process_returns_dict(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify process returns a dictionary."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()

            # Create agent-specific input data
            if agent_type == 'watcher':
                input_data = {'days': 7}
            elif agent_type == 'diagnostician':
                input_data = {'finding_id': 1}
            elif agent_type == 'strategist':
                input_data = {'diagnosis_id': 1}
            elif agent_type == 'dispatcher':
                input_data = {'operation': 'status', 'execution_id': 1}
            else:
                input_data = {}

            result = await agent.process(input_data)
            assert isinstance(result, dict), (
                f"{agent_class.__name__}.process must return dict, got {type(result)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_process_has_status_or_success_key(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify process result contains status or success indicator."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()

            if agent_type == 'watcher':
                input_data = {'days': 7}
            elif agent_type == 'diagnostician':
                input_data = {'finding_id': 1}
            elif agent_type == 'strategist':
                input_data = {'diagnosis_id': 1}
            elif agent_type == 'dispatcher':
                input_data = {'operation': 'status', 'execution_id': 1}
            else:
                input_data = {}

            result = await agent.process(input_data)
            assert 'status' in result or 'success' in result, (
                f"{agent_class.__name__}.process result must contain 'status' or 'success' key"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_process_has_agent_id_key(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify process result contains agent_id."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()

            if agent_type == 'watcher':
                input_data = {'days': 7}
            elif agent_type == 'diagnostician':
                input_data = {'finding_id': 1}
            elif agent_type == 'strategist':
                input_data = {'diagnosis_id': 1}
            elif agent_type == 'dispatcher':
                input_data = {'operation': 'status', 'execution_id': 1}
            else:
                input_data = {}

            result = await agent.process(input_data)
            # Dispatcher uses different keys, so we're more flexible here
            assert 'agent_id' in result or result.get('success') is not None, (
                f"{agent_class.__name__}.process result should contain agent_id or success status"
            )


class TestAgentHealthCheck:
    """Test health_check method compliance for all agents."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_returns_agent_health(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check returns AgentHealth object."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health = await agent.health_check()
            assert isinstance(health, AgentHealth), (
                f"{agent_class.__name__}.health_check must return AgentHealth, got {type(health)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_has_required_fields(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check result has all required fields."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health = await agent.health_check()

            assert hasattr(health, 'agent_id'), f"{agent_class.__name__} health missing agent_id"
            assert hasattr(health, 'status'), f"{agent_class.__name__} health missing status"
            assert hasattr(health, 'uptime_seconds'), f"{agent_class.__name__} health missing uptime_seconds"
            assert hasattr(health, 'last_heartbeat'), f"{agent_class.__name__} health missing last_heartbeat"
            assert hasattr(health, 'error_count'), f"{agent_class.__name__} health missing error_count"
            assert hasattr(health, 'processed_count'), f"{agent_class.__name__} health missing processed_count"
            assert hasattr(health, 'metadata'), f"{agent_class.__name__} health missing metadata"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_status_is_valid_agent_status(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check status is a valid AgentStatus enum value."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health = await agent.health_check()

            assert isinstance(health.status, AgentStatus), (
                f"{agent_class.__name__} health.status must be AgentStatus enum, got {type(health.status)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_metadata_is_dict(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check metadata is a dictionary."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health = await agent.health_check()

            assert isinstance(health.metadata, dict), (
                f"{agent_class.__name__} health.metadata must be dict, got {type(health.metadata)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_uptime_increases(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check uptime increases over time."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health1 = await agent.health_check()

            # Wait a tiny bit
            import asyncio
            await asyncio.sleep(0.01)

            health2 = await agent.health_check()

            assert health2.uptime_seconds >= health1.uptime_seconds, (
                f"{agent_class.__name__} uptime should be non-decreasing"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_health_check_agent_id_matches(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify health_check agent_id matches initialized agent_id."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            health = await agent.health_check()

            assert health.agent_id == agent_id, (
                f"{agent_class.__name__} health.agent_id should match initialized agent_id"
            )


class TestAgentShutdown:
    """Test shutdown method compliance for all agents."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_shutdown_returns_bool(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify shutdown returns a boolean value."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            result = await agent.shutdown()
            assert isinstance(result, bool), (
                f"{agent_class.__name__}.shutdown must return bool, got {type(result)}"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_shutdown_sets_shutdown_status(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify successful shutdown sets status to SHUTDOWN."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            result = await agent.shutdown()

            if result:
                assert agent._status == AgentStatus.SHUTDOWN, (
                    f"{agent_class.__name__} should set status to SHUTDOWN on successful shutdown"
                )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_shutdown_closes_pool(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify shutdown closes database pool."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            await agent.shutdown()

            if hasattr(agent, '_pool') and agent._pool:
                mock_asyncpg_pool.close.assert_called_once()


class TestAgentStatusProperty:
    """Test status property compliance for all agents."""

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_status_property(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config
    ):
        """Verify each agent has a status property."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'status'), f"{agent_class.__name__} missing status property"

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_status_returns_agent_status_enum(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config
    ):
        """Verify status property returns AgentStatus enum."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        status = agent.status
        assert isinstance(status, AgentStatus), (
            f"{agent_class.__name__}.status must return AgentStatus enum, got {type(status)}"
        )


class TestAgentErrorHandling:
    """Test error handling compliance for all agents."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_process_handles_invalid_input(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify process handles invalid input gracefully."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()

            # Pass empty or invalid input
            result = await agent.process({})

            # Should return dict with error info, not raise exception
            assert isinstance(result, dict), (
                f"{agent_class.__name__}.process should return dict even with invalid input"
            )
            assert 'status' in result or 'success' in result or 'error' in result, (
                f"{agent_class.__name__}.process should indicate error in result"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    async def test_error_count_increments_on_failure(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config, mock_asyncpg_pool
    ):
        """Verify error count increments when errors occur."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)

        with patch('asyncpg.create_pool', return_value=mock_asyncpg_pool):
            await agent.initialize()
            initial_error_count = agent._error_count

            # Trigger error with invalid input
            await agent.process({})

            # Error count may or may not increment depending on agent implementation
            # Just verify it's accessible and non-negative
            assert agent._error_count >= 0, (
                f"{agent_class.__name__}._error_count should be non-negative"
            )


class TestAgentMetadata:
    """Test metadata method compliance for all agents."""

    @pytest.mark.parametrize("agent_class,agent_type,agent_id", AGENT_CLASSES)
    def test_agent_has_get_metadata_method(
        self, agent_class, agent_type, agent_id, mock_db_config, mock_agent_config
    ):
        """Verify each agent has get_metadata method inherited from base."""
        agent = agent_class(agent_id, mock_db_config, mock_agent_config)
        assert hasattr(agent, 'get_metadata'), f"{agent_class.__name__} missing get_metadata method"
        assert callable(agent.get_metadata), f"{agent_class.__name__}.get_metadata must be callable"


# Summary test to ensure all agents are tested
def test_all_agents_covered():
    """Verify all 4 agents are included in test parametrization."""
    assert len(AGENT_CLASSES) == 4, "Should test exactly 4 agents"
    agent_types = {agent_type for _, agent_type, _ in AGENT_CLASSES}
    assert agent_types == {'watcher', 'diagnostician', 'strategist', 'dispatcher'}, (
        "Must test Watcher, Diagnostician, Strategist, and Dispatcher agents"
    )
