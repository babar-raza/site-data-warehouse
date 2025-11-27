"""
Tests for Intelligent Watcher Agent
====================================
Tests LangGraph-based intelligent monitoring agent.
"""
import os
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, List
from datetime import datetime

# Import AgentState from the correct location (base module)
from agents.base.langgraph_agent import AgentState, AgentTools
from agents.watcher.intelligent_watcher import IntelligentWatcherAgent


@pytest.fixture
def watcher():
    """Create IntelligentWatcherAgent instance (sync fixture)"""
    agent = IntelligentWatcherAgent(
        db_dsn=os.getenv('TEST_WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db'),
        ollama_url='http://localhost:11434'
    )
    return agent


@pytest.fixture
def sample_state():
    """Create sample agent state"""
    return {
        'input_data': {'property': 'https://blog.aspose.net'},
        'property': 'https://blog.aspose.net',
        'current_step': 'start',
        'iteration': 0,
        'max_iterations': 3,
        'observations': [],
        'findings': [],
        'reasoning': [],
        'queries_executed': [],
        'tools_used': [],
        'conclusion': None,
        'recommendations': [],
        'confidence': 0.0,
        'agent_name': 'IntelligentWatcher',
        'started_at': datetime.utcnow(),
        'completed_at': None
    }


@pytest.fixture
def sample_performance_data():
    """Create sample performance data from AgentTools.query_performance"""
    return [
        {
            'page_path': '/python/tutorial/',
            'gsc_clicks': 500,
            'gsc_position': 5.2,
            'clicks_delta_pct_7d': -50.0,
            'date': datetime.now().date()
        },
        {
            'page_path': '/java/guide/',
            'gsc_clicks': 300,
            'gsc_position': 8.5,
            'clicks_delta_pct_7d': 7.14,
            'date': datetime.now().date()
        }
    ]


@pytest.fixture
def sample_anomaly_data():
    """Create sample anomaly data from AgentTools.query_anomalies"""
    return [
        {
            'page_path': '/critical/page/',
            'metric_name': 'gsc_clicks',
            'severity': 'critical',
            'deviation_pct': -99.8,
            'detection_date': datetime.now().date()
        }
    ]


# =============================================
# STATE INITIALIZATION TESTS
# =============================================

def test_agent_state_structure():
    """Test AgentState TypedDict structure"""
    state: AgentState = {
        'input_data': {},
        'property': 'https://example.com',
        'current_step': 'start',
        'iteration': 0,
        'max_iterations': 5,
        'observations': ['obs1', 'obs2'],
        'findings': [{'type': 'anomaly', 'severity': 'high'}],
        'reasoning': ['reason1'],
        'queries_executed': [],
        'tools_used': [],
        'conclusion': 'Test conclusion',
        'recommendations': [{'action': 'test', 'priority': 80}],
        'confidence': 0.8,
        'agent_name': 'TestAgent',
        'started_at': datetime.utcnow(),
        'completed_at': None
    }

    assert state['property'] == 'https://example.com'
    assert len(state['observations']) == 2
    assert len(state['findings']) == 1
    assert state['conclusion'] == 'Test conclusion'


def test_create_initial_state(watcher):
    """Test initial state creation via invoke"""
    # The agent creates initial state internally in invoke()
    # We can test the _build_workflow returns a compiled graph
    assert watcher.workflow is not None
    assert watcher.agent_name == 'IntelligentWatcher'


# =============================================
# OBSERVATION NODE TESTS
# =============================================

@pytest.mark.asyncio
async def test_observe_node_with_performance_data(watcher, sample_state, sample_performance_data, sample_anomaly_data):
    """Test observation node processes performance data"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            with patch.object(AgentTools, 'query_anomalies', return_value=sample_anomaly_data):
                result_state = await watcher._observe_node(sample_state)

    assert len(result_state['observations']) > 0
    assert result_state['current_step'] == 'observe'


@pytest.mark.asyncio
async def test_observe_node_no_data(watcher, sample_state):
    """Test observation node with no performance data"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=[]):
            with patch.object(AgentTools, 'query_anomalies', return_value=[]):
                result_state = await watcher._observe_node(sample_state)

    # Should still set current_step even with no data
    assert result_state['current_step'] == 'observe'


@pytest.mark.asyncio
async def test_observe_node_detects_anomalies(watcher, sample_state, sample_performance_data, sample_anomaly_data):
    """Test observation node adds findings from anomaly data"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            with patch.object(AgentTools, 'query_anomalies', return_value=sample_anomaly_data):
                result_state = await watcher._observe_node(sample_state)

    # Should have findings from anomaly data
    assert len(result_state['findings']) > 0
    assert any(f.get('type') == 'anomaly' for f in result_state['findings'])


# =============================================
# REASONING NODE TESTS
# =============================================

@pytest.mark.asyncio
async def test_reason_node_calls_llm(watcher, sample_state):
    """Test reasoning node calls LLM"""
    state_with_observations = sample_state.copy()
    state_with_observations['observations'] = [
        "Page /python/tutorial/ lost 50% traffic (500 clicks)",
        "Position dropped from 3.1 to 5.2"
    ]
    state_with_observations['findings'] = [
        {
            'type': 'traffic_drop',
            'page': '/python/tutorial/',
            'severity': 'high',
        }
    ]

    with patch.object(watcher, '_call_llm', return_value="Analysis: Traffic drop detected due to ranking loss."):
        result_state = await watcher._reason_node(state_with_observations)

    assert len(result_state['reasoning']) > 0
    assert result_state['current_step'] == 'reason'
    assert 'llm_reasoning' in result_state['tools_used']


@pytest.mark.asyncio
async def test_reason_node_no_findings(watcher, sample_state):
    """Test reasoning node with no findings"""
    state_with_obs = sample_state.copy()
    state_with_obs['observations'] = ["Traffic is stable across all pages"]

    with patch.object(watcher, '_call_llm', return_value="Everything looks normal. No issues detected."):
        result_state = await watcher._reason_node(state_with_obs)

    assert len(result_state['reasoning']) > 0


# =============================================
# ACTION NODE TESTS
# =============================================

@pytest.mark.asyncio
async def test_act_node_investigates_high_severity_findings(watcher, sample_state, sample_performance_data):
    """Test action node investigates high severity findings"""
    state_with_findings = sample_state.copy()
    state_with_findings['findings'] = [
        {'type': 'anomaly', 'page': '/critical/page/', 'severity': 'high'}
    ]

    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            result_state = await watcher._act_node(state_with_findings)

    assert result_state['current_step'] == 'act'
    assert result_state['iteration'] == 1
    assert 'sql_query' in result_state['tools_used']


# =============================================
# DECISION NODE TESTS
# =============================================

@pytest.mark.asyncio
async def test_decide_node_forms_conclusion(watcher, sample_state):
    """Test decision node forms conclusion"""
    state_with_reasoning = sample_state.copy()
    state_with_reasoning['reasoning'] = [
        "Traffic drop due to ranking loss",
        "Competitor analysis needed",
    ]
    state_with_reasoning['findings'] = [
        {'type': 'traffic_drop', 'page': '/page/', 'severity': 'high'}
    ]

    mock_response = """
Conclusion: Traffic drop detected on /page/ requires immediate attention.

Recommendations:
1. [Update content to improve relevance]
2. [Check technical issues]
3. [Analyze competitors]

Confidence: 0.85
"""
    with patch.object(watcher, '_call_llm', return_value=mock_response):
        result_state = await watcher._decide_node(state_with_reasoning)

    assert result_state['conclusion'] is not None
    assert result_state['current_step'] == 'decide'
    assert len(result_state['recommendations']) > 0


# =============================================
# WORKFLOW TESTS
# =============================================

def test_build_workflow(watcher):
    """Test workflow graph construction"""
    # The workflow is built in __init__ and compiled
    assert watcher.workflow is not None


@pytest.mark.asyncio
async def test_analyze_property_success(watcher, sample_performance_data, sample_anomaly_data):
    """Test complete analyze_property workflow"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.execute = AsyncMock()

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            with patch.object(AgentTools, 'query_anomalies', return_value=sample_anomaly_data):
                with patch.object(watcher, '_call_llm', return_value="Analysis complete. Recommendation: Monitor traffic."):
                    result = await watcher.analyze_property('https://blog.aspose.net')

    assert 'success' in result
    assert 'findings' in result or 'error' in result


# =============================================
# LLM INTEGRATION TESTS
# =============================================

@pytest.mark.asyncio
async def test_call_llm_success(watcher):
    """Test LLM call success"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'response': 'This is the LLM response'}
        mock_client.post.return_value = mock_response

        response = await watcher._call_llm("Test prompt")

    assert response == 'This is the LLM response'


@pytest.mark.asyncio
async def test_call_llm_failure(watcher):
    """Test LLM call failure handling"""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = Mock()
        mock_response.status_code = 500
        mock_client.post.return_value = mock_response

        response = await watcher._call_llm("Test prompt")

    assert 'error' in response.lower() or 'Error' in response


# =============================================
# DATABASE CONNECTION TESTS
# =============================================

@pytest.mark.asyncio
async def test_get_pool_creates_pool(watcher):
    """Test get_pool creates connection pool"""
    with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        pool = await watcher.get_pool()

        mock_create_pool.assert_called_once()
        assert pool == mock_pool


@pytest.mark.asyncio
async def test_close_closes_pool(watcher):
    """Test close method closes pool"""
    mock_pool = AsyncMock()
    watcher._pool = mock_pool

    await watcher.close()

    mock_pool.close.assert_called_once()


# =============================================
# ERROR HANDLING TESTS
# =============================================

@pytest.mark.asyncio
async def test_analyze_property_handles_db_error(watcher):
    """Test handling of database error"""
    with patch.object(watcher, 'get_pool', side_effect=Exception("Database connection failed")):
        result = await watcher.analyze_property('https://example.com')

    assert result.get('success') is False or 'error' in result


@pytest.mark.asyncio
async def test_analyze_property_handles_llm_error(watcher, sample_performance_data):
    """Test handling of LLM error during analysis"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            with patch.object(AgentTools, 'query_anomalies', return_value=[]):
                with patch.object(watcher, '_call_llm', side_effect=Exception("LLM service unavailable")):
                    result = await watcher.analyze_property('https://example.com')

    # Should handle error gracefully
    assert 'success' in result or 'error' in result


# =============================================
# SYNC WRAPPER TESTS
# =============================================

def test_analyze_property_sync(watcher, sample_performance_data):
    """Test synchronous wrapper"""
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.execute = AsyncMock()

    with patch.object(watcher, 'get_pool', return_value=mock_pool):
        with patch.object(AgentTools, 'query_performance', return_value=sample_performance_data):
            with patch.object(AgentTools, 'query_anomalies', return_value=[]):
                with patch.object(watcher, '_call_llm', return_value="Test LLM response"):
                    result = watcher.analyze_property_sync('https://example.com')

    assert 'success' in result or 'error' in result


# =============================================
# STORE RESULTS TESTS
# =============================================

@pytest.mark.asyncio
async def test_store_results_success(watcher):
    """Test storing results in database"""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    # Create a proper async context manager mock for pool.acquire()
    class MockAcquireContext:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *args):
            pass

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = MockAcquireContext()

    result = {
        'success': True,
        'findings': [
            {'type': 'anomaly', 'page': '/test/', 'severity': 'high'}
        ],
        'confidence': 0.85,
        'iterations': 2
    }

    # get_pool is async, so we need to make the mock return the pool when awaited
    async def mock_get_pool():
        return mock_pool

    with patch.object(watcher, 'get_pool', mock_get_pool):
        await watcher._store_results('https://example.com', result)

    # Should have called execute at least once for agent_executions
    assert mock_conn.execute.called


# =============================================
# INTEGRATION TESTS
# =============================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_analysis():
    """Integration test with real database and LLM"""
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    agent = IntelligentWatcherAgent()

    try:
        result = await agent.analyze_property('https://blog.aspose.net')

        assert 'success' in result
        assert isinstance(result.get('findings', []), list)

    finally:
        await agent.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
