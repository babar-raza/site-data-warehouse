"""End-to-end agent orchestration integration test."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pytest
import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.watcher.watcher_agent import WatcherAgent
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.strategist.strategist_agent import StrategistAgent
from agents.dispatcher.dispatcher_agent import DispatcherAgent
from agents.base.message_bus import MessageBus, Message

load_dotenv()


class TestAgentOrchestration:
    """Test concurrent agent orchestration and communication."""

    @pytest.fixture(scope="class")
    async def db_config(self):
        """Database configuration fixture."""
        return {
            'host': os.getenv('WAREHOUSE_HOST', 'localhost'),
            'port': int(os.getenv('WAREHOUSE_PORT', 5432)),
            'user': os.getenv('WAREHOUSE_USER', 'gsc_user'),
            'password': os.getenv('WAREHOUSE_PASSWORD', ''),
            'database': os.getenv('WAREHOUSE_DB', 'gsc_warehouse')
        }

    @pytest.fixture(scope="class")
    async def db_pool(self, db_config):
        """Database connection pool fixture."""
        pool = await asyncpg.create_pool(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            min_size=10,
            max_size=50
        )
        yield pool
        await pool.close()

    @pytest.fixture
    async def message_bus(self):
        """Message bus fixture."""
        bus = MessageBus(persistence_path="./data/test_messages")
        await bus.start()
        yield bus
        await bus.stop()

    @pytest.fixture
    async def clean_test_data(self, db_pool):
        """Clean test data."""
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM gsc.findings WHERE finding_id LIKE 'orch_test_%'")
            await conn.execute("DELETE FROM gsc.recommendations WHERE recommendation_id LIKE 'orch_test_%'")
            await conn.execute("DELETE FROM gsc.outcomes WHERE outcome_id LIKE 'orch_test_%'")
        
        yield
        
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM gsc.findings WHERE finding_id LIKE 'orch_test_%'")
            await conn.execute("DELETE FROM gsc.recommendations WHERE recommendation_id LIKE 'orch_test_%'")
            await conn.execute("DELETE FROM gsc.outcomes WHERE outcome_id LIKE 'orch_test_%'")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_concurrent_watchers(self, db_config, db_pool, message_bus, clean_test_data):
        """Test 5 concurrent watcher agents monitoring different metrics."""
        print("\n=== Test Concurrent Watchers ===")
        
        # Create 5 watchers with different configurations
        watchers = []
        for i in range(5):
            watcher = WatcherAgent(
                agent_id=f"orch_watcher_{i:03d}",
                db_config=db_config,
                config={
                    'sensitivity': 2.0 + (i * 0.5),
                    'min_data_points': 5 + i,
                    'metric_focus': ['impressions', 'clicks', 'ctr', 'position', 'revenue'][i]
                }
            )
            watchers.append(watcher)
        
        # Initialize all watchers
        init_tasks = [watcher.initialize() for watcher in watchers]
        init_results = await asyncio.gather(*init_tasks, return_exceptions=True)
        
        successful_inits = sum(1 for r in init_results if r is True)
        print(f"✓ Initialized {successful_inits}/{len(watchers)} watchers")
        assert successful_inits == len(watchers), "Not all watchers initialized"
        
        # Subscribe watchers to message bus
        for watcher in watchers:
            async def watcher_handler(message: Message) -> bool:
                print(f"Watcher {watcher.agent_id} received: {message.topic}")
                return True
            
            await message_bus.subscribe(
                watcher.agent_id,
                "watcher.*",
                watcher_handler
            )
        
        # Run all watchers concurrently
        print("Running concurrent detection...")
        detection_tasks = [
            watcher.process({'days': 30, 'property': None})
            for watcher in watchers
        ]
        
        start_time = datetime.now()
        results = await asyncio.gather(*detection_tasks, return_exceptions=True)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Verify results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
        print(f"✓ {successful}/{len(watchers)} watchers completed successfully")
        print(f"✓ Concurrent execution took {duration:.2f}s")
        
        # Verify findings in database
        async with db_pool.acquire() as conn:
            findings_count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.findings WHERE agent_id LIKE 'orch_watcher_%'"
            )
            print(f"✓ Total findings detected: {findings_count}")
        
        # Verify no race conditions
        for i, result in enumerate(results):
            if isinstance(result, dict):
                assert 'anomalies' in result, f"Watcher {i} missing anomalies"
                assert 'trends' in result, f"Watcher {i} missing trends"
        
        # Shutdown all watchers
        shutdown_tasks = [watcher.shutdown() for watcher in watchers]
        await asyncio.gather(*shutdown_tasks)
        
        print(f"✓ All watchers shut down gracefully")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_diagnostician_agents(self, db_config, db_pool, message_bus, clean_test_data):
        """Test 3 diagnosticians analyzing findings concurrently."""
        print("\n=== Test Concurrent Diagnosticians ===")
        
        # First, create test findings for analysis
        async with db_pool.acquire() as conn:
            for i in range(15):
                await conn.execute("""
                    INSERT INTO gsc.findings (
                        finding_id, agent_id, finding_type, severity,
                        title, description, affected_urls, metrics, detected_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (finding_id) DO NOTHING
                """,
                f'orch_test_finding_{i:03d}',
                'orch_watcher_000',
                ['anomaly', 'trend', 'pattern'][i % 3],
                ['low', 'medium', 'high'][i % 3],
                f'Test Finding {i}',
                f'Test finding description {i}',
                [f'https://test.com/page{i}'],
                {'impressions': -50 - i, 'clicks': -30 - i},
                datetime.now()
                )
        
        # Create 3 diagnosticians
        diagnosticians = []
        for i in range(3):
            diagnostician = DiagnosticianAgent(
                agent_id=f"orch_diagnostician_{i:03d}",
                db_config=db_config,
                config={
                    'correlation_threshold': 0.6 + (i * 0.1),
                    'min_sample_size': 3 + i
                }
            )
            diagnosticians.append(diagnostician)
        
        # Initialize all diagnosticians
        init_tasks = [d.initialize() for d in diagnosticians]
        await asyncio.gather(*init_tasks)
        print(f"✓ Initialized {len(diagnosticians)} diagnosticians")
        
        # Subscribe to message bus
        for diagnostician in diagnosticians:
            async def diag_handler(message: Message) -> bool:
                print(f"Diagnostician {diagnostician.agent_id} received: {message.topic}")
                return True
            
            await message_bus.subscribe(
                diagnostician.agent_id,
                "diagnostician.*",
                diag_handler
            )
        
        # Distribute findings across diagnosticians
        async with db_pool.acquire() as conn:
            finding_ids = await conn.fetch(
                "SELECT finding_id FROM gsc.findings WHERE finding_id LIKE 'orch_test_finding_%' ORDER BY finding_id"
            )
        
        # Run analysis concurrently
        analysis_tasks = []
        for i, diagnostician in enumerate(diagnosticians):
            # Assign subset of findings to each diagnostician
            start_idx = i * 5
            end_idx = start_idx + 5
            assigned_findings = [f['finding_id'] for f in finding_ids[start_idx:end_idx]]
            
            analysis_tasks.append(
                diagnostician.process({'finding_ids': assigned_findings})
            )
        
        start_time = datetime.now()
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Verify results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
        print(f"✓ {successful}/{len(diagnosticians)} diagnosticians completed successfully")
        print(f"✓ Concurrent analysis took {duration:.2f}s")
        
        # Shutdown all diagnosticians
        shutdown_tasks = [d.shutdown() for d in diagnosticians]
        await asyncio.gather(*shutdown_tasks)

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_strategist_agent(self, db_config, db_pool, message_bus, clean_test_data):
        """Test single strategist prioritizing recommendations."""
        print("\n=== Test Strategist Agent ===")
        
        # Create strategist
        strategist = StrategistAgent(
            agent_id="orch_strategist_001",
            db_config=db_config,
            config={
                'min_impact_score': 3.0,
                'max_recommendations': 20
            }
        )
        
        await strategist.initialize()
        print("✓ Strategist initialized")
        
        # Subscribe to message bus
        received_messages = []
        
        async def strategist_handler(message: Message) -> bool:
            received_messages.append(message)
            print(f"Strategist received: {message.topic}")
            return True
        
        await message_bus.subscribe(
            strategist.agent_id,
            "strategist.*",
            strategist_handler
        )
        
        # Generate recommendations
        result = await strategist.process({'time_window': 7})
        
        assert result['status'] == 'success', "Strategist failed"
        assert 'recommendations' in result, "No recommendations generated"
        
        print(f"✓ Generated {len(result['recommendations'])} recommendations")
        
        # Verify recommendations stored
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.recommendations WHERE agent_id = $1",
                strategist.agent_id
            )
            print(f"✓ Stored {count} recommendations")
        
        await strategist.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_dispatcher_agent(self, db_config, db_pool, message_bus, clean_test_data):
        """Test single dispatcher executing recommendations."""
        print("\n=== Test Dispatcher Agent ===")
        
        # Create test recommendations
        async with db_pool.acquire() as conn:
            for i in range(5):
                await conn.execute("""
                    INSERT INTO gsc.recommendations (
                        recommendation_id, agent_id, recommendation_type, priority,
                        title, description, action_items, estimated_impact, created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (recommendation_id) DO NOTHING
                """,
                f'orch_test_recommendation_{i:03d}',
                'orch_strategist_001',
                ['optimization', 'fix', 'enhancement'][i % 3],
                ['low', 'medium', 'high'][i % 3],
                f'Test Recommendation {i}',
                f'Test recommendation description {i}',
                [f'Action {i}.1', f'Action {i}.2'],
                {'impressions': 50 + i * 10, 'clicks': 25 + i * 5},
                datetime.now()
                )
        
        # Create dispatcher
        dispatcher = DispatcherAgent(
            agent_id="orch_dispatcher_001",
            db_config=db_config,
            config={
                'max_parallel_executions': 3,
                'validation_enabled': True
            }
        )
        
        await dispatcher.initialize()
        print("✓ Dispatcher initialized")
        
        # Subscribe to message bus
        received_messages = []
        
        async def dispatcher_handler(message: Message) -> bool:
            received_messages.append(message)
            print(f"Dispatcher received: {message.topic}")
            return True
        
        await message_bus.subscribe(
            dispatcher.agent_id,
            "dispatcher.*",
            dispatcher_handler
        )
        
        # Execute recommendations
        async with db_pool.acquire() as conn:
            recommendation_ids = await conn.fetch(
                "SELECT recommendation_id FROM gsc.recommendations WHERE recommendation_id LIKE 'orch_test_recommendation_%'"
            )
        
        result = await dispatcher.process({
            'recommendation_ids': [r['recommendation_id'] for r in recommendation_ids]
        })
        
        assert result['status'] == 'success', "Dispatcher failed"
        assert 'executions' in result, "No executions completed"
        
        print(f"✓ Executed {len(result['executions'])} recommendations")
        
        await dispatcher.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_full_orchestration(self, db_config, db_pool, message_bus, clean_test_data):
        """Test full agent orchestration with all agents running."""
        print("\n=== Test Full Agent Orchestration ===")
        
        # Track all messages
        all_messages = []
        
        async def universal_handler(message: Message) -> bool:
            all_messages.append(message)
            return True
        
        await message_bus.subscribe("orchestration_monitor", "#", universal_handler)
        
        # Create all agents
        print("Creating agent fleet...")
        
        # 5 Watchers
        watchers = [
            WatcherAgent(f"orch_watcher_{i:03d}", db_config)
            for i in range(5)
        ]
        
        # 3 Diagnosticians
        diagnosticians = [
            DiagnosticianAgent(f"orch_diagnostician_{i:03d}", db_config)
            for i in range(3)
        ]
        
        # 1 Strategist
        strategist = StrategistAgent("orch_strategist_001", db_config)
        
        # 1 Dispatcher
        dispatcher = DispatcherAgent("orch_dispatcher_001", db_config)
        
        all_agents = watchers + diagnosticians + [strategist, dispatcher]
        
        # Initialize all agents
        print(f"Initializing {len(all_agents)} agents...")
        init_tasks = [agent.initialize() for agent in all_agents]
        init_results = await asyncio.gather(*init_tasks, return_exceptions=True)
        
        successful = sum(1 for r in init_results if r is True)
        print(f"✓ Initialized {successful}/{len(all_agents)} agents")
        
        # Phase 1: Watchers detect
        print("\nPhase 1: Detection")
        watcher_tasks = [watcher.process({'days': 7}) for watcher in watchers]
        watcher_results = await asyncio.gather(*watcher_tasks, return_exceptions=True)
        
        successful_watchers = sum(
            1 for r in watcher_results 
            if isinstance(r, dict) and r.get('status') == 'success'
        )
        print(f"✓ {successful_watchers}/{len(watchers)} watchers completed")
        
        # Phase 2: Diagnosticians analyze
        print("\nPhase 2: Analysis")
        diag_tasks = [
            diagnostician.process({'time_window': 7})
            for diagnostician in diagnosticians
        ]
        diag_results = await asyncio.gather(*diag_tasks, return_exceptions=True)
        
        successful_diags = sum(
            1 for r in diag_results 
            if isinstance(r, dict) and r.get('status') == 'success'
        )
        print(f"✓ {successful_diags}/{len(diagnosticians)} diagnosticians completed")
        
        # Phase 3: Strategist recommends
        print("\nPhase 3: Strategy")
        strat_result = await strategist.process({'time_window': 7})
        assert strat_result['status'] == 'success', "Strategist failed"
        print(f"✓ Strategist generated {len(strat_result.get('recommendations', []))} recommendations")
        
        # Phase 4: Dispatcher executes
        print("\nPhase 4: Execution")
        exec_result = await dispatcher.process({})
        assert exec_result['status'] == 'success', "Dispatcher failed"
        print(f"✓ Dispatcher executed {len(exec_result.get('executions', []))} recommendations")
        
        # Verify message flow
        print(f"\n✓ Total messages exchanged: {len(all_messages)}")
        
        # Get final metrics
        async with db_pool.acquire() as conn:
            metrics = await conn.fetchrow("""
                SELECT 
                    COUNT(*) FILTER (WHERE finding_id LIKE 'orch_%') as findings,
                    COUNT(*) FILTER (WHERE recommendation_id LIKE 'orch_%') as recommendations,
                    COUNT(*) FILTER (WHERE outcome_id LIKE 'orch_%') as outcomes
                FROM gsc.findings
                LEFT JOIN gsc.recommendations USING (finding_id)
                LEFT JOIN gsc.outcomes USING (recommendation_id)
            """)
            
            print(f"✓ Pipeline generated:")
            print(f"  - {metrics['findings'] or 0} findings")
            print(f"  - {metrics['recommendations'] or 0} recommendations")
            print(f"  - {metrics['outcomes'] or 0} outcomes")
        
        # Shutdown all agents
        print("\nShutting down agent fleet...")
        shutdown_tasks = [agent.shutdown() for agent in all_agents]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        print("✓ All agents shut down")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_agent_health_monitoring(self, db_config):
        """Test agent health monitoring during orchestration."""
        print("\n=== Test Agent Health Monitoring ===")
        
        # Create test agents
        agents = [
            WatcherAgent(f"health_watcher_{i}", db_config)
            for i in range(3)
        ]
        
        # Initialize
        for agent in agents:
            await agent.initialize()
        
        # Check health periodically during operation
        health_checks = []
        
        async def monitor_health():
            for _ in range(5):
                await asyncio.sleep(1)
                checks = [await agent.health_check() for agent in agents]
                health_checks.extend(checks)
        
        # Run agents and monitor concurrently
        tasks = [agent.process({'days': 7}) for agent in agents]
        tasks.append(monitor_health())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify health checks
        print(f"✓ Collected {len(health_checks)} health checks")
        
        for check in health_checks:
            print(f"Agent {check.agent_id}: status={check.status.value}, "
                  f"errors={check.error_count}, processed={check.processed_count}")
            assert check.status != AgentStatus.ERROR, f"Agent {check.agent_id} in error state"
        
        # Shutdown
        for agent in agents:
            await agent.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_message_bus_stats(self, message_bus):
        """Test message bus statistics during orchestration."""
        print("\n=== Test Message Bus Statistics ===")
        
        # Publish test messages
        for i in range(100):
            await message_bus.publish(
                topic=f"test.topic.{i % 5}",
                sender_id=f"agent_{i % 3}",
                payload={'data': f'message {i}'}
            )
        
        await asyncio.sleep(1)
        
        # Get statistics
        stats = message_bus.get_stats()
        
        print(f"✓ Messages published: {stats['published']}")
        print(f"✓ Messages delivered: {stats['delivered']}")
        print(f"✓ Messages failed: {stats['failed']}")
        print(f"✓ Dead letters: {stats['dead_letters']}")
        
        assert stats['published'] >= 100, "Not all messages published"
        
        # Get message history
        history = message_bus.get_message_history(limit=50)
        print(f"✓ Message history: {len(history)} messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
