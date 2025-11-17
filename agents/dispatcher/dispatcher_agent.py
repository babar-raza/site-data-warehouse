"""Dispatcher Agent - Executes approved recommendations and monitors outcomes."""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import AgentContract, AgentHealth, AgentStatus
from agents.dispatcher.execution_engine import ExecutionEngine
from agents.dispatcher.validator import Validator
from agents.dispatcher.outcome_monitor import OutcomeMonitor


class DispatcherAgent(AgentContract):
    """Agent that executes approved recommendations and monitors outcomes."""

    def __init__(
        self,
        agent_id: str,
        db_config: Dict[str, str],
        config: Optional[Dict[str, any]] = None
    ):
        """Initialize dispatcher agent.
        
        Args:
            agent_id: Unique agent identifier
            db_config: Database configuration
            config: Optional agent configuration
        """
        super().__init__(agent_id, "dispatcher", config)
        
        self.db_config = db_config
        self._pool: Optional[asyncpg.Pool] = None
        
        # Initialize components
        self._execution_engine: Optional[ExecutionEngine] = None
        self._validator: Optional[Validator] = None
        self._outcome_monitor: Optional[OutcomeMonitor] = None
        
        self._executions: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the dispatcher agent."""
        try:
            self._start_time = datetime.now()
            
            # Connect to database
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                user=self.db_config.get('user', 'gsc_user'),
                password=self.db_config.get('password', ''),
                database=self.db_config.get('database', 'gsc_warehouse'),
                min_size=2,
                max_size=10
            )
            
            # Initialize components with pool
            execution_config = self.config.get('execution', {})
            self._execution_engine = ExecutionEngine(
                self._pool,
                {
                    **execution_config,
                    'integrations': self.config.get('integrations', {})
                }
            )
            
            validation_config = self.config.get('validation', {})
            self._validator = Validator(self._pool, validation_config)
            
            monitoring_config = self.config.get('monitoring', {})
            self._outcome_monitor = OutcomeMonitor(self._pool, monitoring_config)
            
            self._set_status(AgentStatus.RUNNING)
            
            print(f"Dispatcher agent {self.agent_id} initialized successfully")
            
            return True
        
        except Exception as e:
            print(f"Error initializing dispatcher agent: {e}")
            self._set_status(AgentStatus.ERROR)
            self._increment_error_count()
            return False

    async def process(self, input_data: Dict[str, any]) -> Dict[str, any]:
        """Process execution request.
        
        Args:
            input_data: Input containing recommendation_id and operation type
            
        Returns:
            Processing results
        """
        try:
            operation = input_data.get('operation', 'execute')
            
            if operation == 'execute':
                result = await self.execute_recommendation(
                    input_data.get('recommendation_id'),
                    input_data.get('dry_run', False)
                )
            elif operation == 'validate':
                result = await self.validate_execution(
                    input_data.get('execution_id')
                )
            elif operation == 'monitor':
                result = await self.monitor_execution(
                    input_data.get('execution_id')
                )
            elif operation == 'rollback':
                result = await self.rollback_execution(
                    input_data.get('execution_id')
                )
            elif operation == 'status':
                result = await self.get_execution_status(
                    input_data.get('execution_id')
                )
            else:
                result = {
                    'success': False,
                    'message': f'Unknown operation: {operation}'
                }
            
            if result.get('success'):
                self._increment_processed_count()
            else:
                self._increment_error_count()
            
            return result
        
        except Exception as e:
            self._increment_error_count()
            return {
                'success': False,
                'message': f'Processing error: {str(e)}',
                'error': str(e)
            }

    async def execute_recommendation(
        self,
        recommendation_id: int,
        dry_run: bool = False
    ) -> Dict[str, any]:
        """Execute a recommendation.
        
        Args:
            recommendation_id: Recommendation ID to execute
            dry_run: If True, simulate execution
            
        Returns:
            Execution result
        """
        try:
            print(f"{'[DRY RUN] ' if dry_run else ''}Executing recommendation {recommendation_id}...")
            
            # Execute via execution engine
            result = await self._execution_engine.execute_recommendation(
                recommendation_id,
                dry_run
            )
            
            if not result['success']:
                return result
            
            execution_id = result.get('execution_id')
            
            # If not dry run, perform validation
            if not dry_run and self.config.get('validation', {}).get('enabled', True):
                print(f"Validating execution {execution_id}...")
                validation_result = await self._validator.validate_execution(execution_id)
                
                # Check if rollback needed
                if await self._validator.should_rollback(validation_result):
                    print(f"Validation failed, rolling back execution {execution_id}...")
                    rollback_result = await self._execution_engine.rollback_execution(execution_id)
                    
                    return {
                        'success': False,
                        'message': 'Execution failed validation and was rolled back',
                        'recommendation_id': recommendation_id,
                        'execution_id': execution_id,
                        'validation_result': validation_result,
                        'rollback_result': rollback_result
                    }
                
                # Start outcome monitoring
                print(f"Starting outcome monitoring for execution {execution_id}...")
                monitoring_result = await self._outcome_monitor.start_monitoring(execution_id)
                
                result['validation_result'] = validation_result
                result['monitoring_result'] = monitoring_result
            
            self._executions.append(result)
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Execution error: {str(e)}',
                'recommendation_id': recommendation_id,
                'error': str(e)
            }

    async def validate_execution(self, execution_id: int) -> Dict[str, any]:
        """Validate an execution.
        
        Args:
            execution_id: Execution ID to validate
            
        Returns:
            Validation result
        """
        try:
            print(f"Validating execution {execution_id}...")
            
            result = await self._validator.validate_execution(execution_id)
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Validation error: {str(e)}',
                'execution_id': execution_id,
                'error': str(e)
            }

    async def monitor_execution(self, execution_id: int) -> Dict[str, any]:
        """Monitor execution outcomes.
        
        Args:
            execution_id: Execution ID to monitor
            
        Returns:
            Monitoring result
        """
        try:
            print(f"Monitoring execution {execution_id}...")
            
            # Collect current metrics
            metrics_result = await self._outcome_monitor.collect_metrics(execution_id)
            
            if not metrics_result.get('success'):
                return metrics_result
            
            # Evaluate outcome
            evaluation_result = await self._outcome_monitor.evaluate_outcome(execution_id)
            
            # Get monitoring status
            status_result = await self._outcome_monitor.get_monitoring_status(execution_id)
            
            return {
                'success': True,
                'message': 'Monitoring data collected',
                'execution_id': execution_id,
                'metrics': metrics_result,
                'evaluation': evaluation_result,
                'status': status_result
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Monitoring error: {str(e)}',
                'execution_id': execution_id,
                'error': str(e)
            }

    async def rollback_execution(self, execution_id: int) -> Dict[str, any]:
        """Rollback an execution.
        
        Args:
            execution_id: Execution ID to rollback
            
        Returns:
            Rollback result
        """
        try:
            print(f"Rolling back execution {execution_id}...")
            
            result = await self._execution_engine.rollback_execution(execution_id)
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Rollback error: {str(e)}',
                'execution_id': execution_id,
                'error': str(e)
            }

    async def get_execution_status(self, execution_id: int) -> Dict[str, any]:
        """Get execution status.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Status information
        """
        try:
            async with self._pool.acquire() as conn:
                execution = await conn.fetchrow(
                    """
                    SELECT e.*, r.recommendation_type, r.priority
                    FROM gsc.agent_executions e
                    JOIN gsc.agent_recommendations r ON e.recommendation_id = r.id
                    WHERE e.id = $1
                    """,
                    execution_id
                )
                
                if not execution:
                    return {
                        'success': False,
                        'message': 'Execution not found'
                    }
                
                # Get monitoring status if available
                monitoring_status = None
                if execution['outcome_metrics']:
                    monitoring_status = await self._outcome_monitor.get_monitoring_status(execution_id)
                
                return {
                    'success': True,
                    'execution_id': execution_id,
                    'status': execution['status'],
                    'recommendation_id': execution['recommendation_id'],
                    'recommendation_type': execution['recommendation_type'],
                    'started_at': execution['started_at'].isoformat() if execution['started_at'] else None,
                    'completed_at': execution['completed_at'].isoformat() if execution['completed_at'] else None,
                    'dry_run': execution['dry_run'],
                    'validation_result': execution['validation_result'],
                    'outcome_metrics': execution['outcome_metrics'],
                    'monitoring_status': monitoring_status
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Status error: {str(e)}',
                'error': str(e)
            }

    async def execute_batch(
        self,
        recommendation_ids: List[int],
        dry_run: bool = False
    ) -> List[Dict[str, any]]:
        """Execute multiple recommendations.
        
        Args:
            recommendation_ids: List of recommendation IDs
            dry_run: If True, simulate execution
            
        Returns:
            List of execution results
        """
        max_concurrent = self.config.get('execution', {}).get('max_concurrent', 3)
        
        results = []
        
        # Process in batches to respect concurrency limit
        for i in range(0, len(recommendation_ids), max_concurrent):
            batch = recommendation_ids[i:i + max_concurrent]
            
            tasks = [
                self.execute_recommendation(rec_id, dry_run)
                for rec_id in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append({
                        'success': False,
                        'message': f'Exception: {str(result)}',
                        'recommendation_id': batch[j],
                        'error': str(result)
                    })
                else:
                    results.append(result)
        
        return results

    async def health_check(self) -> AgentHealth:
        """Check agent health."""
        try:
            # Check database connection
            if self._pool:
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            
            uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            
            return AgentHealth(
                agent_id=self.agent_id,
                status=self._status,
                uptime_seconds=uptime,
                last_heartbeat=datetime.now(),
                error_count=self._error_count,
                processed_count=self._processed_count,
                memory_usage_mb=0.0,
                cpu_percent=0.0,
                metadata={
                    'executions_count': len(self._executions),
                    'last_execution': self._executions[-1] if self._executions else None
                }
            )
        
        except Exception as e:
            return AgentHealth(
                agent_id=self.agent_id,
                status=AgentStatus.ERROR,
                uptime_seconds=0.0,
                last_heartbeat=datetime.now(),
                error_count=self._error_count + 1,
                processed_count=self._processed_count,
                memory_usage_mb=0.0,
                cpu_percent=0.0,
                metadata={'error': str(e)}
            )

    async def shutdown(self) -> bool:
        """Shutdown the agent."""
        try:
            self._set_status(AgentStatus.SHUTDOWN)
            
            if self._pool:
                await self._pool.close()
            
            print(f"Dispatcher agent {self.agent_id} shut down successfully")
            
            return True
        
        except Exception as e:
            print(f"Error shutting down dispatcher agent: {e}")
            return False


async def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description='Dispatcher Agent')
    parser.add_argument('--initialize', action='store_true', help='Initialize the agent')
    parser.add_argument('--execute', action='store_true', help='Execute a recommendation')
    parser.add_argument('--validate', action='store_true', help='Validate an execution')
    parser.add_argument('--monitor', action='store_true', help='Monitor an execution')
    parser.add_argument('--rollback', action='store_true', help='Rollback an execution')
    parser.add_argument('--status', action='store_true', help='Get execution status')
    parser.add_argument('--recommendation-id', type=int, help='Recommendation ID to execute')
    parser.add_argument('--execution-id', type=int, help='Execution ID')
    parser.add_argument('--dry-run', action='store_true', help='Simulate execution without changes')
    parser.add_argument('--config', type=str, help='Config file path')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config or Path(__file__).parent / 'config.yaml'
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            config = config.get('dispatcher', {})
    except Exception as e:
        print(f"Error loading config: {e}")
        config = {}
    
    # Get database configuration from environment
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'user': os.getenv('DB_USER', 'gsc_user'),
        'password': os.getenv('DB_PASSWORD', 'gsc_pass'),
        'database': os.getenv('DB_NAME', 'gsc_db')
    }
    
    # Create agent
    agent = DispatcherAgent(
        agent_id='dispatcher-001',
        db_config=db_config,
        config=config
    )
    
    try:
        # Initialize agent
        if not await agent.initialize():
            print("Failed to initialize agent")
            return 1
        
        # Execute operations
        if args.initialize:
            print("Agent initialized successfully")
            health = await agent.health_check()
            print(f"Health: {health}")
        
        elif args.execute and args.recommendation_id:
            result = await agent.execute_recommendation(
                args.recommendation_id,
                args.dry_run
            )
            print(json.dumps(result, indent=2))
        
        elif args.validate and args.execution_id:
            result = await agent.validate_execution(args.execution_id)
            print(json.dumps(result, indent=2))
        
        elif args.monitor and args.execution_id:
            result = await agent.monitor_execution(args.execution_id)
            print(json.dumps(result, indent=2))
        
        elif args.rollback and args.execution_id:
            result = await agent.rollback_execution(args.execution_id)
            print(json.dumps(result, indent=2))
        
        elif args.status and args.execution_id:
            result = await agent.get_execution_status(args.execution_id)
            print(json.dumps(result, indent=2))
        
        else:
            parser.print_help()
        
        # Shutdown
        await agent.shutdown()
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        await agent.shutdown()
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
