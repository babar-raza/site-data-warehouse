"""
Integration Tests for Multi-Agent Workflows
Tests LangGraph orchestration, agent decisions, and workflow execution
"""

import pytest
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from dotenv import load_dotenv

# Import agents to test
from agents.orchestration.supervisor_agent import SupervisorAgent
from agents.orchestration.serp_analyst_agent import SerpAnalystAgent
from agents.orchestration.performance_agent import PerformanceAgent

load_dotenv()

TEST_PROPERTY = "https://test-domain.com"
TEST_DSN = os.getenv('WAREHOUSE_DSN', 'postgresql://postgres:postgres@localhost:5432/seo_warehouse')


@pytest.fixture
async def db_connection():
    """Provide database connection for tests"""
    conn = await asyncpg.connect(TEST_DSN)
    yield conn
    await conn.close()


@pytest.fixture
async def clean_workflow_data(db_connection):
    """Clean up workflow test data"""
    conn = db_connection

    # Clean before
    await conn.execute("DELETE FROM orchestration.agent_decisions WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflow_steps WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflows WHERE property = $1", TEST_PROPERTY)

    yield

    # Clean after
    await conn.execute("DELETE FROM orchestration.agent_decisions WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflow_steps WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflows WHERE property = $1", TEST_PROPERTY)


@pytest.fixture
async def setup_test_data(db_connection):
    """Set up test data for agent analysis"""
    conn = db_connection

    # Insert SERP position drops
    query_id = await conn.fetchval("""
        INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
        VALUES ($1, $2, $3, true)
        RETURNING query_id
    """, 'test keyword', TEST_PROPERTY, '/target-page')

    # Insert position history showing a drop
    for i in range(7, 0, -1):
        position = 3 if i > 2 else 8  # Position drops from 3 to 8
        await conn.execute("""
            INSERT INTO serp.position_history (query_id, property, position, checked_at)
            VALUES ($1, $2, $3, NOW() - INTERVAL '%s days')
        """, query_id, TEST_PROPERTY, position, i)

    # Insert poor CWV data
    await conn.execute("""
        INSERT INTO performance.cwv_metrics
        (property, page_path, device, lcp, fid, cls, performance_score, checked_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
    """, TEST_PROPERTY, '/slow-page', 'mobile', 3500, 150, 0.15, 45)

    yield

    # Cleanup
    await conn.execute("DELETE FROM serp.position_history WHERE query_id = $1", query_id)
    await conn.execute("DELETE FROM serp.queries WHERE query_id = $1", query_id)
    await conn.execute("DELETE FROM performance.cwv_metrics WHERE property = $1", TEST_PROPERTY)


class TestSupervisorAgent:
    """Test Supervisor Agent orchestration"""

    @pytest.mark.asyncio
    async def test_supervisor_initialization(self):
        """Test supervisor agent initializes correctly"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        assert supervisor is not None
        assert supervisor.db_dsn == TEST_DSN

    @pytest.mark.asyncio
    async def test_supervisor_agent_registration(self):
        """Test supervisor can register specialist agents"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)

        serp_analyst = SerpAnalystAgent(db_dsn=TEST_DSN)
        performance_agent = PerformanceAgent(db_dsn=TEST_DSN)

        supervisor.register_agent('serp_analyst', serp_analyst)
        supervisor.register_agent('performance_agent', performance_agent)

        assert 'serp_analyst' in supervisor.agents
        assert 'performance_agent' in supervisor.agents

    @pytest.mark.asyncio
    async def test_workflow_creation(self, db_connection, clean_workflow_data):
        """Test workflow is created in database"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)

        workflow_id = await supervisor.start_workflow(
            workflow_name='Test Daily Analysis',
            workflow_type='daily_analysis',
            property=TEST_PROPERTY,
            trigger_event={'source': 'test'}
        )

        assert workflow_id is not None

        # Verify in database
        row = await db_connection.fetchrow(
            "SELECT * FROM orchestration.workflows WHERE workflow_id = $1",
            workflow_id
        )

        assert row is not None
        assert row['workflow_name'] == 'Test Daily Analysis'
        assert row['workflow_type'] == 'daily_analysis'
        assert row['property'] == TEST_PROPERTY
        assert row['status'] == 'running'

    @pytest.mark.asyncio
    async def test_workflow_completion(self, db_connection, clean_workflow_data):
        """Test workflow can be completed"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)

        workflow_id = await supervisor.start_workflow(
            workflow_name='Test Workflow',
            workflow_type='test',
            property=TEST_PROPERTY
        )

        # Complete workflow
        await supervisor.complete_workflow(
            workflow_id=workflow_id,
            status='completed',
            final_state={'result': 'success'}
        )

        # Verify status
        row = await db_connection.fetchrow(
            "SELECT status, completed_at FROM orchestration.workflows WHERE workflow_id = $1",
            workflow_id
        )

        assert row['status'] == 'completed'
        assert row['completed_at'] is not None

    @pytest.mark.asyncio
    @patch('agents.orchestration.supervisor_agent.SupervisorAgent.build_workflow_graph')
    async def test_supervisor_workflow_execution(self, mock_graph, db_connection, clean_workflow_data):
        """Test supervisor executes workflow"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        supervisor.register_agent('serp_analyst', SerpAnalystAgent(db_dsn=TEST_DSN))

        # Mock LangGraph execution
        mock_compiled_graph = AsyncMock()
        mock_compiled_graph.ainvoke = AsyncMock(return_value={
            'workflow_id': 'test-123',
            'recommendations': [
                {'type': 'test', 'action': 'test action', 'priority': 'high'}
            ],
            'status': 'completed'
        })
        mock_graph.return_value.compile.return_value = mock_compiled_graph

        result = await supervisor.run_workflow(
            workflow_type='daily_analysis',
            trigger_event={'source': 'test'},
            property=TEST_PROPERTY
        )

        assert result['success'] is True
        assert 'recommendations' in result
        assert len(result['recommendations']) > 0


class TestSerpAnalystAgent:
    """Test SERP Analyst Agent"""

    @pytest.mark.asyncio
    async def test_serp_analyst_initialization(self):
        """Test SERP analyst initializes correctly"""
        agent = SerpAnalystAgent(db_dsn=TEST_DSN)
        assert agent is not None

    @pytest.mark.asyncio
    async def test_position_change_detection(self, db_connection, setup_test_data):
        """Test agent detects position changes"""
        agent = SerpAnalystAgent(db_dsn=TEST_DSN)

        position_changes = await agent._get_position_changes(TEST_PROPERTY, days=7)

        assert len(position_changes) > 0
        # Should detect the drop from 3 to 8
        has_drop = any(change['position_drop'] >= 3 for change in position_changes)
        assert has_drop is True

    @pytest.mark.asyncio
    async def test_serp_analyst_recommendations(self, db_connection, setup_test_data, clean_workflow_data):
        """Test SERP analyst generates recommendations"""
        agent = SerpAnalystAgent(db_dsn=TEST_DSN)

        # Create workflow context
        workflow_id = await db_connection.fetchval("""
            INSERT INTO orchestration.workflows
            (workflow_name, workflow_type, property, status)
            VALUES ($1, $2, $3, $4)
            RETURNING workflow_id
        """, 'Test', 'test', TEST_PROPERTY, 'running')

        state = {
            'workflow_id': workflow_id,
            'property': TEST_PROPERTY,
            'recommendations': []
        }

        result = await agent.analyze(state)

        assert 'recommendations' in result
        assert len(result['recommendations']) > 0

        # Should recommend addressing position drop
        has_position_drop_rec = any(
            'position_drop' in rec['type'].lower()
            for rec in result['recommendations']
        )
        assert has_position_drop_rec is True

    @pytest.mark.asyncio
    async def test_serp_analyst_decision_logging(self, db_connection, setup_test_data, clean_workflow_data):
        """Test SERP analyst logs decisions to database"""
        agent = SerpAnalystAgent(db_dsn=TEST_DSN)

        workflow_id = await db_connection.fetchval("""
            INSERT INTO orchestration.workflows
            (workflow_name, workflow_type, property, status)
            VALUES ($1, $2, $3, $4)
            RETURNING workflow_id
        """, 'Test', 'test', TEST_PROPERTY, 'running')

        await agent.log_decision(
            workflow_id=workflow_id,
            decision_type='position_analysis',
            decision='Detected significant position drop',
            reasoning='Position dropped from 3 to 8 for high-value query',
            confidence=0.9,
            recommendations=[{'type': 'address_drop', 'action': 'Review content'}]
        )

        # Verify logged
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM orchestration.agent_decisions WHERE workflow_id = $1",
            workflow_id
        )
        assert count == 1

        row = await db_connection.fetchrow(
            "SELECT * FROM orchestration.agent_decisions WHERE workflow_id = $1",
            workflow_id
        )
        assert row['agent_name'] == 'serp_analyst'
        assert row['confidence'] == 0.9


class TestPerformanceAgent:
    """Test Performance Agent"""

    @pytest.mark.asyncio
    async def test_performance_agent_initialization(self):
        """Test performance agent initializes correctly"""
        agent = PerformanceAgent(db_dsn=TEST_DSN)
        assert agent is not None

    @pytest.mark.asyncio
    async def test_poor_cwv_detection(self, db_connection, setup_test_data):
        """Test agent detects poor CWV pages"""
        agent = PerformanceAgent(db_dsn=TEST_DSN)

        poor_pages = await agent._get_poor_cwv_pages(TEST_PROPERTY)

        assert len(poor_pages) > 0
        # Should find the slow page we inserted
        has_slow_page = any(page['page_path'] == '/slow-page' for page in poor_pages)
        assert has_slow_page is True

    @pytest.mark.asyncio
    async def test_performance_recommendations(self, db_connection, setup_test_data, clean_workflow_data):
        """Test performance agent generates optimization recommendations"""
        agent = PerformanceAgent(db_dsn=TEST_DSN)

        workflow_id = await db_connection.fetchval("""
            INSERT INTO orchestration.workflows
            (workflow_name, workflow_type, property, status)
            VALUES ($1, $2, $3, $4)
            RETURNING workflow_id
        """, 'Test', 'test', TEST_PROPERTY, 'running')

        state = {
            'workflow_id': workflow_id,
            'property': TEST_PROPERTY,
            'recommendations': []
        }

        result = await agent.analyze(state)

        assert 'recommendations' in result
        assert len(result['recommendations']) > 0

        # Should recommend LCP optimization
        has_lcp_rec = any(
            'lcp' in rec['type'].lower() or 'performance' in rec['type'].lower()
            for rec in result['recommendations']
        )
        assert has_lcp_rec is True


class TestWorkflowOrchestration:
    """Test end-to-end workflow orchestration"""

    @pytest.mark.asyncio
    async def test_daily_analysis_workflow(self, db_connection, setup_test_data, clean_workflow_data):
        """Test complete daily analysis workflow"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        supervisor.register_agent('serp_analyst', SerpAnalystAgent(db_dsn=TEST_DSN))
        supervisor.register_agent('performance_agent', PerformanceAgent(db_dsn=TEST_DSN))

        # Mock Ollama/LLM calls
        with patch('agents.orchestration.supervisor_agent.SupervisorAgent._call_llm') as mock_llm:
            mock_llm.return_value = "Proceed with SERP analysis"

            result = await supervisor.run_workflow(
                workflow_type='daily_analysis',
                trigger_event={'source': 'test'},
                property=TEST_PROPERTY
            )

        assert result is not None
        assert 'workflow_id' in result or 'success' in result

    @pytest.mark.asyncio
    async def test_emergency_response_workflow(self, db_connection, setup_test_data, clean_workflow_data):
        """Test emergency response workflow triggered by critical alert"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        supervisor.register_agent('serp_analyst', SerpAnalystAgent(db_dsn=TEST_DSN))
        supervisor.register_agent('performance_agent', PerformanceAgent(db_dsn=TEST_DSN))

        # Simulate critical alert trigger
        trigger_event = {
            'alert_type': 'serp_drop',
            'severity': 'critical',
            'query_text': 'test keyword',
            'position_drop': 5
        }

        with patch('agents.orchestration.supervisor_agent.SupervisorAgent._call_llm') as mock_llm:
            mock_llm.return_value = "Emergency analysis required"

            result = await supervisor.run_workflow(
                workflow_type='emergency_response',
                trigger_event=trigger_event,
                property=TEST_PROPERTY
            )

        assert result is not None

    @pytest.mark.asyncio
    async def test_workflow_step_tracking(self, db_connection, clean_workflow_data):
        """Test that workflow steps are tracked in database"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)

        workflow_id = await supervisor.start_workflow(
            workflow_name='Test Step Tracking',
            workflow_type='test',
            property=TEST_PROPERTY
        )

        # Log a step
        await db_connection.execute("""
            INSERT INTO orchestration.workflow_steps
            (workflow_id, step_name, step_type, status)
            VALUES ($1, $2, $3, $4)
        """, workflow_id, 'analyze', 'agent_call', 'completed')

        # Verify step logged
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM orchestration.workflow_steps WHERE workflow_id = $1",
            workflow_id
        )
        assert count == 1


class TestAgentPerformance:
    """Test agent performance tracking"""

    @pytest.mark.asyncio
    async def test_agent_performance_logging(self, db_connection):
        """Test agent performance metrics are logged"""
        # Insert performance metric
        await db_connection.execute("""
            INSERT INTO orchestration.agent_performance
            (agent_name, metric_type, metric_value, recorded_at)
            VALUES ($1, $2, $3, NOW())
        """, 'serp_analyst', 'execution_time', 2.5)

        # Verify
        row = await db_connection.fetchrow("""
            SELECT * FROM orchestration.agent_performance
            WHERE agent_name = 'serp_analyst'
            ORDER BY recorded_at DESC
            LIMIT 1
        """)

        assert row is not None
        assert row['metric_type'] == 'execution_time'
        assert row['metric_value'] == 2.5

        # Cleanup
        await db_connection.execute("""
            DELETE FROM orchestration.agent_performance
            WHERE agent_name = 'serp_analyst'
        """)

    @pytest.mark.asyncio
    async def test_agent_feedback_system(self, db_connection):
        """Test agent feedback/learning system"""
        workflow_id = await db_connection.fetchval("""
            INSERT INTO orchestration.workflows
            (workflow_name, workflow_type, property, status)
            VALUES ($1, $2, $3, $4)
            RETURNING workflow_id
        """, 'Test Feedback', 'test', TEST_PROPERTY, 'completed')

        decision_id = await db_connection.fetchval("""
            INSERT INTO orchestration.agent_decisions
            (workflow_id, agent_name, decision_type, decision, confidence)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING decision_id
        """, workflow_id, 'serp_analyst', 'test', 'test decision', 0.8)

        # Add feedback
        await db_connection.execute("""
            INSERT INTO orchestration.agent_feedback
            (decision_id, feedback_type, feedback_score, notes)
            VALUES ($1, $2, $3, $4)
        """, decision_id, 'accuracy', 0.9, 'Good recommendation')

        # Verify
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM orchestration.agent_feedback WHERE decision_id = $1",
            decision_id
        )
        assert count == 1

        # Cleanup
        await db_connection.execute("DELETE FROM orchestration.agent_feedback WHERE decision_id = $1", decision_id)
        await db_connection.execute("DELETE FROM orchestration.agent_decisions WHERE decision_id = $1", decision_id)
        await db_connection.execute("DELETE FROM orchestration.workflows WHERE workflow_id = $1", workflow_id)


class TestStateManagement:
    """Test workflow state management"""

    @pytest.mark.asyncio
    async def test_state_persistence(self, db_connection, clean_workflow_data):
        """Test workflow state is persisted correctly"""
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)

        workflow_id = await supervisor.start_workflow(
            workflow_name='Test State',
            workflow_type='test',
            property=TEST_PROPERTY
        )

        # Update state
        test_state = {
            'current_step': 'analysis',
            'data_collected': True,
            'findings': ['finding1', 'finding2']
        }

        await db_connection.execute("""
            UPDATE orchestration.workflows
            SET state = $1
            WHERE workflow_id = $2
        """, test_state, workflow_id)

        # Retrieve and verify
        row = await db_connection.fetchrow(
            "SELECT state FROM orchestration.workflows WHERE workflow_id = $1",
            workflow_id
        )

        assert row['state'] == test_state
        assert row['state']['current_step'] == 'analysis'
        assert row['state']['data_collected'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
