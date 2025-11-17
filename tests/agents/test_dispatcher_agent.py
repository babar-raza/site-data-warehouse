"""Tests for Dispatcher Agent."""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

import asyncpg

from agents.dispatcher.dispatcher_agent import DispatcherAgent
from agents.dispatcher.execution_engine import ExecutionEngine
from agents.dispatcher.validator import Validator, ContentValidationRule, PRValidationRule
from agents.dispatcher.outcome_monitor import OutcomeMonitor


@pytest.fixture
async def db_pool():
    """Create a mock database pool."""
    pool = AsyncMock(spec=asyncpg.Pool)
    
    # Mock connection
    conn = AsyncMock()
    pool.acquire = AsyncMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=None)
    ))
    
    # Setup default responses
    conn.fetchrow = AsyncMock(return_value={
        'id': 1,
        'recommendation_id': 789,
        'recommendation_type': 'content_optimization',
        'action_items': json.dumps({
            'url': 'https://example.com/page',
            'changes': {'title': 'New Title', 'meta_description': 'New Description'}
        }),
        'implemented': False,
        'expected_impact': 'high',
        'expected_traffic_lift_pct': 10.0,
        'diagnosis_id': 1,
        'issue_type': 'content_quality',
        'affected_urls': json.dumps(['https://example.com/page']),
        'execution_type': 'content_update',
        'status': 'completed',
        'execution_details': json.dumps({
            'url': 'https://example.com/page',
            'changes': {'title': 'New Title'}
        }),
        'started_at': datetime.now(),
        'completed_at': datetime.now(),
        'validation_result': json.dumps({'success': True}),
        'outcome_metrics': json.dumps({
            'monitoring_started_at': datetime.now().isoformat(),
            'monitoring_end_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'urls_monitored': ['https://example.com/page'],
            'baseline_metrics': {},
            'daily_metrics': []
        }),
        'dry_run': False
    })
    
    conn.fetchval = AsyncMock(return_value=101)
    conn.execute = AsyncMock()
    
    return pool


@pytest.fixture
def dispatcher_config():
    """Create dispatcher configuration."""
    return {
        'execution': {
            'max_concurrent': 3,
            'timeout_seconds': 300,
            'retry_attempts': 3
        },
        'validation': {
            'enabled': True,
            'auto_rollback_on_failure': True
        },
        'monitoring': {
            'outcome_monitoring_days': 30,
            'metrics_collection_interval_hours': 24,
            'performance_threshold': {
                'min_traffic_lift_pct': 5.0,
                'min_ctr_improvement_pct': 2.0
            }
        },
        'integrations': {
            'content_api': {'enabled': False},
            'github': {'enabled': True, 'base_url': 'https://api.github.com'},
            'notifications': {
                'email': {'enabled': False},
                'slack': {'enabled': False}
            }
        }
    }


@pytest.fixture
async def dispatcher_agent(db_pool, dispatcher_config):
    """Create a dispatcher agent instance."""
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'user': 'test_user',
        'password': 'test_pass',
        'database': 'test_db'
    }
    
    agent = DispatcherAgent(
        agent_id='dispatcher-test',
        db_config=db_config,
        config=dispatcher_config
    )
    
    # Mock the pool creation
    agent._pool = db_pool
    agent._execution_engine = ExecutionEngine(db_pool, {
        **dispatcher_config['execution'],
        'integrations': dispatcher_config['integrations']
    })
    agent._validator = Validator(db_pool, dispatcher_config['validation'])
    agent._outcome_monitor = OutcomeMonitor(db_pool, dispatcher_config['monitoring'])
    agent._set_status(agent.status)
    agent._start_time = datetime.now()
    
    return agent


class TestDispatcherAgent:
    """Test suite for DispatcherAgent."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, dispatcher_agent):
        """Test agent initialization."""
        assert dispatcher_agent.agent_id == 'dispatcher-test'
        assert dispatcher_agent.agent_type == 'dispatcher'
        assert dispatcher_agent._pool is not None
        assert dispatcher_agent._execution_engine is not None
        assert dispatcher_agent._validator is not None
        assert dispatcher_agent._outcome_monitor is not None
    
    @pytest.mark.asyncio
    async def test_execute_recommendation_dry_run(self, dispatcher_agent, db_pool):
        """Test dry run execution."""
        result = await dispatcher_agent.execute_recommendation(
            recommendation_id=789,
            dry_run=True
        )
        
        assert result['success'] is True
        assert result['dry_run'] is True
        assert 'execution_id' in result
        assert 'DRY RUN' in result.get('message', '') or result.get('details', {}).get('dry_run') is True
    
    @pytest.mark.asyncio
    async def test_execute_recommendation_actual(self, dispatcher_agent, db_pool):
        """Test actual execution."""
        result = await dispatcher_agent.execute_recommendation(
            recommendation_id=789,
            dry_run=False
        )
        
        assert 'execution_id' in result
        assert result['recommendation_id'] == 789
        assert result['dry_run'] is False
    
    @pytest.mark.asyncio
    async def test_validate_execution(self, dispatcher_agent, db_pool):
        """Test execution validation."""
        result = await dispatcher_agent.validate_execution(execution_id=101)
        
        assert 'execution_id' in result
        assert 'success' in result
        assert 'validations' in result
    
    @pytest.mark.asyncio
    async def test_monitor_execution(self, dispatcher_agent, db_pool):
        """Test execution monitoring."""
        result = await dispatcher_agent.monitor_execution(execution_id=101)
        
        assert 'execution_id' in result
        assert 'metrics' in result or 'status' in result
    
    @pytest.mark.asyncio
    async def test_rollback_execution(self, dispatcher_agent, db_pool):
        """Test execution rollback."""
        result = await dispatcher_agent.rollback_execution(execution_id=101)
        
        assert 'success' in result
        assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_get_execution_status(self, dispatcher_agent, db_pool):
        """Test getting execution status."""
        result = await dispatcher_agent.get_execution_status(execution_id=101)
        
        assert result['success'] is True
        assert result['execution_id'] == 101
        assert 'status' in result
    
    @pytest.mark.asyncio
    async def test_execute_batch(self, dispatcher_agent, db_pool):
        """Test batch execution."""
        recommendation_ids = [789, 790, 791]
        
        results = await dispatcher_agent.execute_batch(
            recommendation_ids=recommendation_ids,
            dry_run=True
        )
        
        assert len(results) == len(recommendation_ids)
        for result in results:
            assert 'success' in result
            assert 'recommendation_id' in result
    
    @pytest.mark.asyncio
    async def test_health_check(self, dispatcher_agent):
        """Test health check."""
        health = await dispatcher_agent.health_check()
        
        assert health.agent_id == 'dispatcher-test'
        assert health.status is not None
        assert health.uptime_seconds >= 0
        assert health.error_count >= 0
        assert health.processed_count >= 0
    
    @pytest.mark.asyncio
    async def test_process_execute_operation(self, dispatcher_agent, db_pool):
        """Test process method with execute operation."""
        result = await dispatcher_agent.process({
            'operation': 'execute',
            'recommendation_id': 789,
            'dry_run': True
        })
        
        assert 'success' in result
    
    @pytest.mark.asyncio
    async def test_process_validate_operation(self, dispatcher_agent, db_pool):
        """Test process method with validate operation."""
        result = await dispatcher_agent.process({
            'operation': 'validate',
            'execution_id': 101
        })
        
        assert 'success' in result
    
    @pytest.mark.asyncio
    async def test_process_monitor_operation(self, dispatcher_agent, db_pool):
        """Test process method with monitor operation."""
        result = await dispatcher_agent.process({
            'operation': 'monitor',
            'execution_id': 101
        })
        
        assert 'execution_id' in result or 'message' in result


class TestExecutionEngine:
    """Test suite for ExecutionEngine."""
    
    @pytest.mark.asyncio
    async def test_execute_content_update_dry_run(self, db_pool, dispatcher_config):
        """Test content update dry run."""
        engine = ExecutionEngine(db_pool, {
            **dispatcher_config['execution'],
            'integrations': dispatcher_config['integrations']
        })
        
        action_items = {
            'url': 'https://example.com/page',
            'changes': {'title': 'New Title'}
        }
        
        result = await engine._execute_content_update(action_items, dry_run=True)
        
        assert result['success'] is True
        assert 'DRY RUN' in result['message']
        assert result['details']['dry_run'] is True
    
    @pytest.mark.asyncio
    async def test_execute_technical_fix_dry_run(self, db_pool, dispatcher_config):
        """Test technical fix dry run."""
        engine = ExecutionEngine(db_pool, {
            **dispatcher_config['execution'],
            'integrations': dispatcher_config['integrations']
        })
        
        action_items = {
            'fix_type': 'broken_links',
            'files': ['page1.html', 'page2.html']
        }
        
        result = await engine._execute_technical_fix(action_items, dry_run=True)
        
        assert result['success'] is True
        assert 'DRY RUN' in result['message']
    
    @pytest.mark.asyncio
    async def test_rollback_execution(self, db_pool, dispatcher_config):
        """Test execution rollback."""
        engine = ExecutionEngine(db_pool, {
            **dispatcher_config['execution'],
            'integrations': dispatcher_config['integrations']
        })
        
        result = await engine.rollback_execution(execution_id=101)
        
        assert 'success' in result
        assert 'message' in result


class TestValidator:
    """Test suite for Validator."""
    
    @pytest.mark.asyncio
    async def test_validate_execution(self, db_pool, dispatcher_config):
        """Test execution validation."""
        validator = Validator(db_pool, dispatcher_config['validation'])
        
        result = await validator.validate_execution(execution_id=101)
        
        assert 'execution_id' in result
        assert 'success' in result
        assert 'validations' in result
    
    @pytest.mark.asyncio
    async def test_content_validation_rule(self, db_pool):
        """Test content validation rule."""
        rule = ContentValidationRule('test', 'content', {})
        
        execution_details = {
            'url': 'https://example.com',
            'changes': {'title': 'Test Title'}
        }
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.text = '<html><title>Test Title</title></html>'
            
            result = await rule.validate(execution_details, db_pool)
            
            assert 'success' in result
            assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_pr_validation_rule(self, db_pool):
        """Test PR validation rule."""
        rule = PRValidationRule('test', 'pr', {})
        
        execution_details = {
            'pr_url': 'https://github.com/org/repo/pull/123',
            'pr_id': 123
        }
        
        result = await rule.validate(execution_details, db_pool)
        
        assert 'success' in result
        assert 'message' in result
    
    @pytest.mark.asyncio
    async def test_should_rollback(self, db_pool, dispatcher_config):
        """Test rollback decision."""
        validator = Validator(db_pool, dispatcher_config['validation'])
        
        # Successful validation - should not rollback
        result = await validator.should_rollback({'success': True})
        assert result is False
        
        # Failed validation - should rollback
        result = await validator.should_rollback({'success': False})
        assert result is True


class TestOutcomeMonitor:
    """Test suite for OutcomeMonitor."""
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, db_pool, dispatcher_config):
        """Test starting monitoring."""
        monitor = OutcomeMonitor(db_pool, dispatcher_config['monitoring'])
        
        result = await monitor.start_monitoring(execution_id=101)
        
        assert 'success' in result
        assert 'execution_id' in result
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, db_pool, dispatcher_config):
        """Test collecting metrics."""
        monitor = OutcomeMonitor(db_pool, dispatcher_config['monitoring'])
        
        result = await monitor.collect_metrics(execution_id=101)
        
        assert 'success' in result
    
    @pytest.mark.asyncio
    async def test_evaluate_outcome(self, db_pool, dispatcher_config):
        """Test outcome evaluation."""
        monitor = OutcomeMonitor(db_pool, dispatcher_config['monitoring'])
        
        result = await monitor.evaluate_outcome(execution_id=101)
        
        assert 'success' in result
    
    @pytest.mark.asyncio
    async def test_get_monitoring_status(self, db_pool, dispatcher_config):
        """Test getting monitoring status."""
        monitor = OutcomeMonitor(db_pool, dispatcher_config['monitoring'])
        
        result = await monitor.get_monitoring_status(execution_id=101)
        
        assert 'success' in result or 'message' in result
    
    def test_calculate_improvements(self, dispatcher_config):
        """Test improvement calculation."""
        monitor = OutcomeMonitor(None, dispatcher_config['monitoring'])
        
        baseline = {
            'https://example.com/page': {
                'clicks': 100,
                'impressions': 1000,
                'ctr': 0.1,
                'position': 5.0
            }
        }
        
        current = {
            'https://example.com/page': {
                'clicks': 120,
                'impressions': 1100,
                'ctr': 0.11,
                'position': 4.5
            }
        }
        
        improvements = monitor._calculate_improvements(baseline, current)
        
        assert 'https://example.com/page' in improvements
        assert improvements['https://example.com/page']['clicks_improvement_pct'] == 20.0
        assert 'aggregate' in improvements


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
