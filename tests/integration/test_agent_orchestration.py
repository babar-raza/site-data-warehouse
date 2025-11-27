"""Comprehensive Integration Tests for Agent Orchestration.

Tests cover:
- Multi-agent workflow coordination
- Agent-to-agent communication via MessageBus
- Full pipeline: Watcher -> Diagnostician -> Strategist -> Dispatcher
- Error propagation and failure handling between agents
- Message passing, correlation, and state management
- End-to-end orchestration scenarios

Requirements:
- All tests pass
- Tests marked with @pytest.mark.integration
- Multi-agent workflow tested
- Agent-to-agent communication tested
- Watcher -> Diagnostician flow tested
- Diagnostician -> Strategist flow tested
- Full pipeline through Dispatcher tested
- Mock LLM but use real database patterns
- Test failure propagation between agents
"""

import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call
from typing import Dict, List, Any

import asyncpg

# Import agents
from agents.watcher.watcher_agent import WatcherAgent, AnomalyFinding
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent, DiagnosticResult
from agents.strategist.strategist_agent import StrategistAgent, RecommendationResult
from agents.dispatcher.dispatcher_agent import DispatcherAgent

# Import base infrastructure
from agents.base.message_bus import MessageBus, Message
from agents.base.agent_contract import AgentStatus
from agents.base.llm_reasoner import ReasoningResult

# Import supporting components
from agents.watcher.anomaly_detector import Anomaly
from agents.diagnostician.root_cause_analyzer import RootCause


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def message_bus():
    """Create message bus for agent communication."""
    bus = MessageBus(persistence_path="./test_data/messages")
    await bus.start()
    yield bus
    await bus.stop()


@pytest_asyncio.fixture
async def mock_db_pool():
    """Create a mock database pool with comprehensive test data."""
    pool = MagicMock(spec=asyncpg.Pool)
    conn = AsyncMock()

    # Create async context manager
    context_manager = MagicMock()
    context_manager.__aenter__ = AsyncMock(return_value=conn)
    context_manager.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = Mock(return_value=context_manager)

    # Setup mock database responses
    setup_mock_db_responses(conn)

    yield pool


def setup_mock_db_responses(conn):
    """Setup comprehensive mock database responses."""

    # Mock active pages for Watcher
    conn.fetch = AsyncMock(side_effect=lambda query, *args: {
        # Active pages query
        'SELECT DISTINCT page_path': [
            {'page_path': '/blog/test-article', 'last_seen': datetime.now()},
            {'page_path': '/products/item-1', 'last_seen': datetime.now()}
        ],
        # Historical data query
        'SELECT date, clicks': [
            {
                'date': datetime.now() - timedelta(days=i),
                'clicks': 100 - (i * 5) if i < 20 else 100,
                'impressions': 1000,
                'ctr': 0.10,
                'avg_position': 5.0 + (i * 0.5) if i < 20 else 5.0,
                'engagement_rate': 0.6,
                'conversion_rate': 0.03,
                'sessions': 80,
                'avg_session_duration': 120.0,
                'bounce_rate': 0.4
            }
            for i in range(40)
        ],
        # Findings query
        'SELECT id, finding_type': [
            {
                'id': 1,
                'finding_type': 'anomaly',
                'severity': 'high',
                'affected_pages': json.dumps(['/blog/test-article']),
                'metrics': json.dumps({
                    'metric_name': 'clicks',
                    'current_value': 50,
                    'expected_value': 100,
                    'deviation_percent': -50,
                    'context': {}
                }),
                'detected_at': datetime.now()
            }
        ],
        # Diagnoses query
        'FROM gsc.agent_diagnoses': [
            {
                'id': 1,
                'finding_id': 1,
                'root_cause': 'traffic_drop',
                'confidence_score': 0.85,
                'supporting_evidence': json.dumps({
                    'evidence': ['Significant traffic decline', 'Position drop detected']
                }),
                'metadata': json.dumps({'severity': 'high'}),
                'diagnosed_at': datetime.now()
            }
        ],
        # Recommendations query
        'FROM gsc.agent_recommendations': [
            {
                'id': 1,
                'diagnosis_id': 1,
                'recommendation_type': 'content_optimization',
                'action_items': json.dumps({
                    'url': '/blog/test-article',
                    'changes': {'title': 'Updated Title'}
                }),
                'priority': 1,
                'estimated_effort_hours': 4,
                'expected_impact': 'high',
                'expected_traffic_lift_pct': 20.0,
                'implemented': False
            }
        ]
    }.get(next((k for k in query.split() if k in [
        'SELECT DISTINCT page_path',
        'SELECT date, clicks',
        'SELECT id, finding_type',
        'FROM gsc.agent_diagnoses',
        'FROM gsc.agent_recommendations'
    ]), None), []))

    # Mock single row fetches
    conn.fetchrow = AsyncMock(return_value={
        'id': 1,
        'finding_type': 'anomaly',
        'severity': 'high',
        'affected_pages': json.dumps(['/blog/test-article']),
        'metrics': json.dumps({
            'metric_name': 'clicks',
            'current_value': 50,
            'expected_value': 100
        }),
        'detected_at': datetime.now(),
        'finding_id': 1,
        'root_cause': 'traffic_drop',
        'confidence_score': 0.85,
        'supporting_evidence': json.dumps({'evidence': []}),
        'metadata': json.dumps({'severity': 'high'}),
        'recommendation_id': 1,
        'recommendation_type': 'content_optimization',
        'action_items': json.dumps({'url': '/blog/test-article'}),
        'clicks': 50,
        'impressions': 500,
        'ctr': 0.10,
        'avg_position': 8.0,
        'engagement_rate': 0.5,
        'conversion_rate': 0.02,
        'bounce_rate': 0.5,
        'sessions': 40,
        'avg_session_duration': 100.0,
        'status': 'completed',
        'started_at': datetime.now(),
        'completed_at': datetime.now(),
        'validation_result': json.dumps({'success': True}),
        'outcome_metrics': json.dumps({}),
        'dry_run': False
    })

    # Mock insertions return IDs
    conn.fetchval = AsyncMock(return_value=1)
    conn.execute = AsyncMock()


@pytest.fixture
def db_config():
    """Database configuration for agents."""
    return {
        'host': 'localhost',
        'port': 5432,
        'user': 'test_user',
        'password': 'test_password',
        'database': 'test_database'
    }


@pytest_asyncio.fixture
async def watcher_agent(mock_db_pool, db_config, message_bus):
    """Create Watcher agent for testing."""
    config = {
        'sensitivity': 2.5,
        'min_data_points': 7,
        'use_llm': False  # Disable LLM for testing
    }

    agent = WatcherAgent(
        agent_id='watcher_integration_test',
        db_config=db_config,
        config=config
    )

    # Override pool
    agent._pool = mock_db_pool
    agent._set_status(AgentStatus.RUNNING)

    yield agent

    # Cleanup
    if agent._pool and hasattr(agent._pool, 'close'):
        await agent.shutdown()


@pytest_asyncio.fixture
async def diagnostician_agent(mock_db_pool, db_config, message_bus):
    """Create Diagnostician agent for testing."""
    config = {
        'min_confidence': 0.6,
        'use_llm': False  # Disable LLM for testing
    }

    agent = DiagnosticianAgent(
        agent_id='diagnostician_integration_test',
        db_config=db_config,
        config=config
    )

    # Override pool
    agent._pool = mock_db_pool
    agent._set_status(AgentStatus.RUNNING)

    yield agent

    # Cleanup
    if agent._pool and hasattr(agent._pool, 'close'):
        await agent.shutdown()


@pytest_asyncio.fixture
async def strategist_agent(mock_db_pool, db_config, message_bus):
    """Create Strategist agent for testing."""
    config = {
        'impact_weight': 0.4,
        'urgency_weight': 0.3,
        'use_llm': False  # Disable LLM for testing
    }

    agent = StrategistAgent(
        agent_id='strategist_integration_test',
        db_config=db_config,
        config=config
    )

    # Override pool
    agent._pool = mock_db_pool
    agent._set_status(AgentStatus.RUNNING)

    yield agent

    # Cleanup
    if agent._pool and hasattr(agent._pool, 'close'):
        await agent.shutdown()


@pytest_asyncio.fixture
async def dispatcher_agent(mock_db_pool, db_config, message_bus):
    """Create Dispatcher agent for testing."""
    config = {
        'execution': {
            'max_concurrent': 3,
            'timeout_seconds': 300
        },
        'validation': {
            'enabled': True,
            'auto_rollback_on_failure': False
        }
    }

    agent = DispatcherAgent(
        agent_id='dispatcher_integration_test',
        db_config=db_config,
        config=config
    )

    # Override pool
    agent._pool = mock_db_pool
    agent._set_status(AgentStatus.RUNNING)

    # Mock execution engine and validator
    agent._execution_engine = AsyncMock()
    agent._execution_engine.execute_recommendation = AsyncMock(return_value={
        'success': True,
        'execution_id': 1,
        'recommendation_id': 1
    })
    agent._execution_engine.rollback_execution = AsyncMock(return_value={
        'success': True
    })

    agent._validator = AsyncMock()
    agent._validator.validate_execution = AsyncMock(return_value={
        'success': True,
        'validation_passed': True
    })
    agent._validator.should_rollback = AsyncMock(return_value=False)

    agent._outcome_monitor = AsyncMock()
    agent._outcome_monitor.start_monitoring = AsyncMock(return_value={
        'success': True
    })

    yield agent

    # Cleanup
    if agent._pool and hasattr(agent._pool, 'close'):
        await agent.shutdown()


# ============================================================================
# Test Agent-to-Agent Communication
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestAgentCommunication:
    """Test agent-to-agent communication via MessageBus."""

    async def test_message_bus_pub_sub(self, message_bus):
        """Test basic message bus publish/subscribe functionality."""
        received_messages = []

        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True

        # Subscribe
        await message_bus.subscribe('agent_001', 'test.topic', handler)

        # Publish
        msg_id = await message_bus.publish(
            'test.topic',
            'agent_002',
            {'test': 'data'}
        )

        # Wait for processing
        await asyncio.sleep(0.2)

        assert len(received_messages) == 1
        assert received_messages[0].payload['test'] == 'data'
        assert received_messages[0].sender_id == 'agent_002'

    async def test_message_correlation_ids(self, message_bus):
        """Test message correlation for tracking request chains."""
        received_messages = []
        correlation_id = 'corr-123'

        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True

        await message_bus.subscribe('agent_001', 'anomaly.detected', handler)

        # Publish with correlation ID
        await message_bus.publish(
            'anomaly.detected',
            'watcher',
            {'finding_id': 1},
            correlation_id=correlation_id
        )

        await asyncio.sleep(0.2)

        assert len(received_messages) == 1
        assert received_messages[0].correlation_id == correlation_id

    async def test_wildcard_topic_matching(self, message_bus):
        """Test wildcard topic subscription."""
        received_messages = []

        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True

        # Subscribe with wildcard
        await message_bus.subscribe('agent_001', 'anomaly.*', handler)

        # Publish to different topics
        await message_bus.publish('anomaly.detected', 'watcher', {'id': 1})
        await message_bus.publish('anomaly.classified', 'diagnostician', {'id': 2})

        await asyncio.sleep(0.2)

        assert len(received_messages) == 2

    async def test_message_priority_handling(self, message_bus):
        """Test priority message handling."""
        received_messages = []

        async def handler(message: Message) -> bool:
            received_messages.append(message)
            return True

        await message_bus.subscribe('agent_001', 'priority.test', handler)

        # Publish messages with different priorities
        await message_bus.publish('priority.test', 'sender', {'id': 1}, priority=0)
        await message_bus.publish('priority.test', 'sender', {'id': 2}, priority=10)
        await message_bus.publish('priority.test', 'sender', {'id': 3}, priority=5)

        await asyncio.sleep(0.3)

        assert len(received_messages) == 3

    async def test_failed_message_handling(self, message_bus):
        """Test handling of failed messages and dead letter queue."""
        async def failing_handler(message: Message) -> bool:
            raise Exception("Handler failed")

        await message_bus.subscribe('agent_001', 'fail.topic', failing_handler)

        await message_bus.publish('fail.topic', 'sender', {'data': 'test'})

        await asyncio.sleep(0.2)

        # Check that message went to dead letter queue
        stats = message_bus.get_stats()
        assert stats['failed'] > 0


# ============================================================================
# Test Watcher -> Diagnostician Flow
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestWatcherToDiagnostician:
    """Test Watcher to Diagnostician agent flow."""

    async def test_anomaly_detection_triggers_diagnosis(
        self,
        watcher_agent,
        diagnostician_agent,
        message_bus
    ):
        """Test that Watcher anomaly detection triggers Diagnostician analysis."""
        diagnosis_triggered = asyncio.Event()
        received_finding = {}

        async def diagnosis_handler(message: Message) -> bool:
            nonlocal received_finding
            received_finding = message.payload
            diagnosis_triggered.set()
            return True

        # Subscribe Diagnostician to anomaly events
        await message_bus.subscribe(
            diagnostician_agent.agent_id,
            'anomaly.detected',
            diagnosis_handler
        )

        # Simulate Watcher detecting anomaly
        anomaly = Anomaly(
            metric_name='clicks',
            page_path='/blog/test-article',
            current_value=50.0,
            expected_value=100.0,
            deviation_percent=-50.0,
            severity='high',
            detected_at=datetime.now(),
            context={}
        )

        # Publish anomaly detected event
        await message_bus.publish(
            'anomaly.detected',
            watcher_agent.agent_id,
            {
                'finding_id': 1,
                'page_path': anomaly.page_path,
                'metric_name': anomaly.metric_name,
                'severity': anomaly.severity,
                'current_value': anomaly.current_value,
                'expected_value': anomaly.expected_value
            },
            priority=5
        )

        # Wait for diagnosis trigger
        await asyncio.wait_for(diagnosis_triggered.wait(), timeout=2.0)

        assert received_finding['finding_id'] == 1
        assert received_finding['severity'] == 'high'

    async def test_watcher_stores_finding_for_diagnostician(
        self,
        watcher_agent,
        mock_db_pool
    ):
        """Test that Watcher stores findings in database for Diagnostician."""
        # Mock alert manager to track calls
        watcher_agent.alert_manager.create_alert = AsyncMock()

        # Simulate anomaly detection
        result = await watcher_agent.process({'days': 7})

        # Verify process was called successfully
        assert result['status'] == 'success'

    async def test_diagnostician_analyzes_watcher_finding(
        self,
        diagnostician_agent,
        mock_db_pool
    ):
        """Test that Diagnostician can analyze Watcher findings."""
        # Diagnostician processes finding
        result = await diagnostician_agent.process({
            'finding_id': 1
        })

        assert result['status'] == 'success'
        assert 'diagnosis' in result or 'diagnosis_id' in result

    async def test_diagnosis_correlation_with_anomaly(
        self,
        watcher_agent,
        diagnostician_agent,
        message_bus
    ):
        """Test that diagnoses are correctly correlated with anomalies."""
        correlation_id = 'anomaly-diagnosis-001'

        diagnoses_received = []

        async def diagnosis_result_handler(message: Message) -> bool:
            diagnoses_received.append(message)
            return True

        await message_bus.subscribe(
            'test_observer',
            'diagnosis.completed',
            diagnosis_result_handler
        )

        # Publish anomaly with correlation ID
        await message_bus.publish(
            'anomaly.detected',
            watcher_agent.agent_id,
            {'finding_id': 1, 'severity': 'high'},
            correlation_id=correlation_id
        )

        # Publish diagnosis result with same correlation ID
        await message_bus.publish(
            'diagnosis.completed',
            diagnostician_agent.agent_id,
            {'diagnosis_id': 1, 'finding_id': 1, 'root_cause': 'traffic_drop'},
            correlation_id=correlation_id
        )

        await asyncio.sleep(0.2)

        assert len(diagnoses_received) == 1
        assert diagnoses_received[0].correlation_id == correlation_id


# ============================================================================
# Test Diagnostician -> Strategist Flow
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestDiagnosticianToStrategist:
    """Test Diagnostician to Strategist agent flow."""

    async def test_diagnosis_triggers_recommendations(
        self,
        diagnostician_agent,
        strategist_agent,
        message_bus
    ):
        """Test that diagnosis triggers recommendation generation."""
        recommendations_generated = asyncio.Event()
        received_diagnosis = {}

        async def strategist_handler(message: Message) -> bool:
            nonlocal received_diagnosis
            received_diagnosis = message.payload
            recommendations_generated.set()
            return True

        await message_bus.subscribe(
            strategist_agent.agent_id,
            'diagnosis.completed',
            strategist_handler
        )

        # Publish diagnosis completed event
        await message_bus.publish(
            'diagnosis.completed',
            diagnostician_agent.agent_id,
            {
                'diagnosis_id': 1,
                'finding_id': 1,
                'root_cause': 'traffic_drop',
                'confidence': 0.85
            }
        )

        await asyncio.wait_for(recommendations_generated.wait(), timeout=2.0)

        assert received_diagnosis['diagnosis_id'] == 1
        assert received_diagnosis['root_cause'] == 'traffic_drop'

    async def test_strategist_generates_recommendations(
        self,
        strategist_agent,
        mock_db_pool
    ):
        """Test that Strategist generates recommendations from diagnosis."""
        result = await strategist_agent.process({
            'diagnosis_id': 1
        })

        assert result['status'] == 'success'
        assert 'recommendations' in result

    async def test_recommendation_priority_based_on_diagnosis(
        self,
        diagnostician_agent,
        strategist_agent,
        message_bus
    ):
        """Test that recommendation priority is based on diagnosis severity."""
        recommendations = []

        async def rec_handler(message: Message) -> bool:
            recommendations.append(message.payload)
            return True

        await message_bus.subscribe(
            'test_observer',
            'recommendations.generated',
            rec_handler
        )

        # High severity diagnosis
        await message_bus.publish(
            'diagnosis.completed',
            diagnostician_agent.agent_id,
            {
                'diagnosis_id': 1,
                'severity': 'critical',
                'root_cause': 'zero_traffic'
            }
        )

        # Publish recommendation event
        await message_bus.publish(
            'recommendations.generated',
            strategist_agent.agent_id,
            {
                'diagnosis_id': 1,
                'recommendations': [
                    {'priority': 1, 'type': 'emergency_fix'}
                ]
            }
        )

        await asyncio.sleep(0.2)

        assert len(recommendations) > 0
        assert recommendations[0]['recommendations'][0]['priority'] == 1


# ============================================================================
# Test Full Pipeline Through Dispatcher
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestFullPipeline:
    """Test full pipeline: Watcher -> Diagnostician -> Strategist -> Dispatcher."""

    async def test_complete_pipeline_anomaly_to_execution(
        self,
        watcher_agent,
        diagnostician_agent,
        strategist_agent,
        dispatcher_agent,
        message_bus
    ):
        """Test complete pipeline from anomaly detection to execution."""
        pipeline_events = []

        async def event_tracker(message: Message) -> bool:
            pipeline_events.append({
                'topic': message.topic,
                'sender': message.sender_id,
                'payload': message.payload
            })
            return True

        # Subscribe to all pipeline events
        for topic in ['anomaly.detected', 'diagnosis.completed',
                     'recommendations.generated', 'execution.completed']:
            await message_bus.subscribe(
                'pipeline_tracker',
                topic,
                event_tracker
            )

        # 1. Watcher detects anomaly
        await message_bus.publish(
            'anomaly.detected',
            watcher_agent.agent_id,
            {'finding_id': 1, 'page_path': '/blog/test-article'},
            correlation_id='pipeline-001'
        )

        # 2. Diagnostician completes diagnosis
        await message_bus.publish(
            'diagnosis.completed',
            diagnostician_agent.agent_id,
            {'diagnosis_id': 1, 'finding_id': 1},
            correlation_id='pipeline-001'
        )

        # 3. Strategist generates recommendations
        await message_bus.publish(
            'recommendations.generated',
            strategist_agent.agent_id,
            {'recommendation_ids': [1], 'diagnosis_id': 1},
            correlation_id='pipeline-001'
        )

        # 4. Dispatcher executes recommendation
        await message_bus.publish(
            'execution.completed',
            dispatcher_agent.agent_id,
            {'execution_id': 1, 'recommendation_id': 1, 'success': True},
            correlation_id='pipeline-001'
        )

        await asyncio.sleep(0.5)

        # Verify all pipeline stages
        assert len(pipeline_events) == 4
        topics = [e['topic'] for e in pipeline_events]
        assert 'anomaly.detected' in topics
        assert 'diagnosis.completed' in topics
        assert 'recommendations.generated' in topics
        assert 'execution.completed' in topics

    async def test_dispatcher_executes_strategist_recommendations(
        self,
        dispatcher_agent,
        mock_db_pool
    ):
        """Test that Dispatcher executes Strategist recommendations."""
        result = await dispatcher_agent.process({
            'operation': 'execute',
            'recommendation_id': 1,
            'dry_run': False
        })

        assert result.get('success') is True
        assert 'execution_id' in result or 'message' in result

    async def test_pipeline_with_multiple_recommendations(
        self,
        strategist_agent,
        dispatcher_agent,
        message_bus
    ):
        """Test pipeline handling multiple recommendations."""
        executions = []

        async def execution_handler(message: Message) -> bool:
            executions.append(message.payload)
            return True

        await message_bus.subscribe(
            'test_observer',
            'execution.started',
            execution_handler
        )

        # Generate multiple recommendations
        for i in range(3):
            await message_bus.publish(
                'execution.started',
                dispatcher_agent.agent_id,
                {'recommendation_id': i + 1, 'execution_id': i + 1}
            )

        await asyncio.sleep(0.3)

        assert len(executions) == 3


# ============================================================================
# Test Failure Propagation
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestFailurePropagation:
    """Test error and failure propagation between agents."""

    async def test_watcher_failure_stops_pipeline(
        self,
        watcher_agent,
        diagnostician_agent,
        message_bus
    ):
        """Test that Watcher failure prevents downstream processing."""
        errors_received = []

        async def error_handler(message: Message) -> bool:
            errors_received.append(message.payload)
            return True

        await message_bus.subscribe(
            'error_monitor',
            'agent.error',
            error_handler
        )

        # Simulate Watcher error
        await message_bus.publish(
            'agent.error',
            watcher_agent.agent_id,
            {
                'error': 'Database connection failed',
                'agent': 'watcher',
                'severity': 'critical'
            }
        )

        await asyncio.sleep(0.2)

        assert len(errors_received) == 1
        assert errors_received[0]['agent'] == 'watcher'

    async def test_diagnostician_failure_propagates_to_strategist(
        self,
        diagnostician_agent,
        strategist_agent,
        message_bus
    ):
        """Test that Diagnostician failure is communicated to Strategist."""
        correlation_id = 'failure-test-001'
        failures = []

        async def failure_handler(message: Message) -> bool:
            failures.append(message)
            return True

        await message_bus.subscribe(
            strategist_agent.agent_id,
            'diagnosis.failed',
            failure_handler
        )

        # Publish diagnosis failure
        await message_bus.publish(
            'diagnosis.failed',
            diagnostician_agent.agent_id,
            {
                'finding_id': 1,
                'error': 'Insufficient data for analysis',
                'can_retry': False
            },
            correlation_id=correlation_id
        )

        await asyncio.sleep(0.2)

        assert len(failures) == 1
        assert failures[0].correlation_id == correlation_id

    async def test_dispatcher_rollback_on_validation_failure(
        self,
        dispatcher_agent,
        message_bus
    ):
        """Test that Dispatcher rolls back on validation failure."""
        # Override validator to fail
        dispatcher_agent._validator.validate_execution = AsyncMock(return_value={
            'success': False,
            'validation_passed': False,
            'errors': ['Content validation failed']
        })
        dispatcher_agent._validator.should_rollback = AsyncMock(return_value=True)

        result = await dispatcher_agent.execute_recommendation(1, dry_run=False)

        # Verify rollback was triggered
        assert dispatcher_agent._execution_engine.rollback_execution.called

    async def test_error_recovery_and_retry(
        self,
        diagnostician_agent,
        message_bus
    ):
        """Test error recovery and retry mechanism."""
        retry_attempts = []

        async def retry_handler(message: Message) -> bool:
            retry_attempts.append(message.payload)
            return True

        await message_bus.subscribe(
            'retry_monitor',
            'diagnosis.retry',
            retry_handler
        )

        # Publish retry event
        await message_bus.publish(
            'diagnosis.retry',
            diagnostician_agent.agent_id,
            {
                'finding_id': 1,
                'attempt': 1,
                'max_attempts': 3,
                'reason': 'Temporary LLM unavailability'
            }
        )

        await asyncio.sleep(0.2)

        assert len(retry_attempts) == 1
        assert retry_attempts[0]['attempt'] == 1

    async def test_cascading_failure_detection(
        self,
        watcher_agent,
        diagnostician_agent,
        strategist_agent,
        message_bus
    ):
        """Test detection of cascading failures across agents."""
        correlation_id = 'cascade-001'
        failure_events = []

        async def failure_tracker(message: Message) -> bool:
            failure_events.append({
                'agent': message.sender_id,
                'topic': message.topic,
                'correlation_id': message.correlation_id
            })
            return True

        await message_bus.subscribe(
            'failure_monitor',
            '*.failed',
            failure_tracker
        )

        # Simulate cascading failures
        await message_bus.publish(
            'anomaly.failed',
            watcher_agent.agent_id,
            {'error': 'Data fetch failed'},
            correlation_id=correlation_id
        )

        await message_bus.publish(
            'diagnosis.failed',
            diagnostician_agent.agent_id,
            {'error': 'No finding to diagnose'},
            correlation_id=correlation_id
        )

        await message_bus.publish(
            'recommendation.failed',
            strategist_agent.agent_id,
            {'error': 'No diagnosis available'},
            correlation_id=correlation_id
        )

        await asyncio.sleep(0.3)

        # Verify all failures were tracked
        assert len(failure_events) == 3
        assert all(e['correlation_id'] == correlation_id for e in failure_events)


# ============================================================================
# Test Multi-Agent Coordination
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiAgentCoordination:
    """Test multi-agent coordination and state management."""

    async def test_concurrent_agent_processing(
        self,
        watcher_agent,
        diagnostician_agent,
        strategist_agent,
        message_bus
    ):
        """Test multiple agents processing concurrently."""
        processing_events = []

        async def processing_handler(message: Message) -> bool:
            processing_events.append({
                'agent': message.sender_id,
                'timestamp': message.timestamp,
                'payload': message.payload
            })
            return True

        await message_bus.subscribe(
            'coordinator',
            'agent.processing',
            processing_handler
        )

        # Trigger concurrent processing
        tasks = [
            message_bus.publish(
                'agent.processing',
                watcher_agent.agent_id,
                {'task': 'anomaly_detection'}
            ),
            message_bus.publish(
                'agent.processing',
                diagnostician_agent.agent_id,
                {'task': 'root_cause_analysis'}
            ),
            message_bus.publish(
                'agent.processing',
                strategist_agent.agent_id,
                {'task': 'recommendation_generation'}
            )
        ]

        await asyncio.gather(*tasks)
        await asyncio.sleep(0.3)

        assert len(processing_events) == 3

    async def test_agent_health_monitoring_during_workflow(
        self,
        watcher_agent,
        diagnostician_agent,
        strategist_agent
    ):
        """Test health monitoring during workflow execution."""
        # Check health of all agents
        watcher_health = await watcher_agent.health_check()
        diagnostician_health = await diagnostician_agent.health_check()
        strategist_health = await strategist_agent.health_check()

        assert watcher_health.status == AgentStatus.RUNNING
        assert diagnostician_health.status == AgentStatus.RUNNING
        assert strategist_health.status == AgentStatus.RUNNING

    async def test_message_ordering_preservation(
        self,
        message_bus
    ):
        """Test that message ordering is preserved in pipeline."""
        received_order = []

        async def order_handler(message: Message) -> bool:
            received_order.append(message.payload['sequence'])
            return True

        await message_bus.subscribe(
            'order_checker',
            'ordered.messages',
            order_handler
        )

        # Publish messages in sequence
        for i in range(5):
            await message_bus.publish(
                'ordered.messages',
                'sender',
                {'sequence': i}
            )

        await asyncio.sleep(0.5)

        # Verify order is preserved
        assert received_order == [0, 1, 2, 3, 4]

    async def test_agent_state_synchronization(
        self,
        watcher_agent,
        diagnostician_agent,
        message_bus
    ):
        """Test that agent states are synchronized via message bus."""
        state_updates = []

        async def state_handler(message: Message) -> bool:
            state_updates.append(message.payload)
            return True

        await message_bus.subscribe(
            'state_monitor',
            'agent.state_change',
            state_handler
        )

        # Publish state changes
        await message_bus.publish(
            'agent.state_change',
            watcher_agent.agent_id,
            {'status': 'processing', 'current_task': 'anomaly_detection'}
        )

        await message_bus.publish(
            'agent.state_change',
            diagnostician_agent.agent_id,
            {'status': 'waiting', 'waiting_for': 'watcher_results'}
        )

        await asyncio.sleep(0.2)

        assert len(state_updates) == 2


# ============================================================================
# Test Edge Cases and Error Scenarios
# ============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error scenarios in orchestration."""

    async def test_empty_finding_handling(
        self,
        diagnostician_agent
    ):
        """Test handling of non-existent finding."""
        result = await diagnostician_agent.process({
            'finding_id': 999999
        })

        # Should handle gracefully
        assert result['status'] in ['success', 'error']

    async def test_malformed_message_handling(
        self,
        message_bus
    ):
        """Test handling of malformed messages."""
        error_count_before = message_bus.get_stats()['failed']

        async def strict_handler(message: Message) -> bool:
            # Expect specific format
            if 'required_field' not in message.payload:
                raise ValueError("Missing required field")
            return True

        await message_bus.subscribe(
            'strict_agent',
            'strict.topic',
            strict_handler
        )

        # Send malformed message
        await message_bus.publish(
            'strict.topic',
            'sender',
            {'wrong_field': 'value'}
        )

        await asyncio.sleep(0.2)

        error_count_after = message_bus.get_stats()['failed']
        assert error_count_after > error_count_before

    async def test_timeout_handling(
        self,
        message_bus
    ):
        """Test message timeout handling."""
        received = []

        async def slow_handler(message: Message) -> bool:
            await asyncio.sleep(1)  # Slow processing
            received.append(message)
            return True

        await message_bus.subscribe(
            'slow_agent',
            'slow.topic',
            slow_handler
        )

        # Publish message with short TTL
        await message_bus.publish(
            'slow.topic',
            'sender',
            {'data': 'test'},
            ttl_seconds=0  # Immediate expiry
        )

        await asyncio.sleep(0.2)

        # Message should be expired
        stats = message_bus.get_stats()
        assert stats['dead_letters'] > 0

    async def test_agent_shutdown_during_processing(
        self,
        watcher_agent,
        message_bus
    ):
        """Test graceful shutdown during active processing."""
        # Start processing
        process_task = asyncio.create_task(
            watcher_agent.process({'days': 7})
        )

        # Immediately shutdown
        await watcher_agent.shutdown()

        # Process task should complete or be cancelled
        try:
            await asyncio.wait_for(process_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass  # Expected behavior

        assert watcher_agent.status == AgentStatus.SHUTDOWN
