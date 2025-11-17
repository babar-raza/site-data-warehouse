"""System load testing for GSC Warehouse."""

import asyncio
import argparse
import os
import sys
import time
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import asyncpg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.watcher.watcher_agent import WatcherAgent
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.strategist.strategist_agent import StrategistAgent
from agents.dispatcher.dispatcher_agent import DispatcherAgent

load_dotenv()


class LoadTestMetrics:
    """Track and report load test metrics."""
    
    def __init__(self):
        self.response_times = []
        self.errors = []
        self.success_count = 0
        self.failure_count = 0
        self.start_time = None
        self.end_time = None
    
    def record_success(self, response_time: float):
        """Record successful operation."""
        self.response_times.append(response_time)
        self.success_count += 1
    
    def record_failure(self, error: str):
        """Record failed operation."""
        self.errors.append(error)
        self.failure_count += 1
    
    def get_summary(self) -> Dict:
        """Get metrics summary."""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        return {
            'duration': duration,
            'total_operations': self.success_count + self.failure_count,
            'successful': self.success_count,
            'failed': self.failure_count,
            'success_rate': self.success_count / (self.success_count + self.failure_count) if (self.success_count + self.failure_count) > 0 else 0,
            'throughput': self.success_count / duration if duration > 0 else 0,
            'avg_response_time': statistics.mean(self.response_times) if self.response_times else 0,
            'min_response_time': min(self.response_times) if self.response_times else 0,
            'max_response_time': max(self.response_times) if self.response_times else 0,
            'p50_response_time': statistics.median(self.response_times) if self.response_times else 0,
            'p95_response_time': statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 20 else 0,
            'p99_response_time': statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else 0,
        }


class SystemLoadTester:
    """Comprehensive system load tester."""
    
    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.pool = None
    
    async def setup(self):
        """Setup database pool."""
        self.pool = await asyncpg.create_pool(
            host=self.db_config['host'],
            port=self.db_config['port'],
            user=self.db_config['user'],
            password=self.db_config['password'],
            database=self.db_config['database'],
            min_size=20,
            max_size=100
        )
        print("✓ Database pool created")
    
    async def teardown(self):
        """Cleanup resources."""
        if self.pool:
            await self.pool.close()
        print("✓ Resources cleaned up")
    
    async def load_test_data_ingestion(self, row_count: int = 1000000) -> LoadTestMetrics:
        """Load test data ingestion with 1M rows."""
        print(f"\n=== Load Test: Data Ingestion ({row_count} rows) ===")
        
        metrics = LoadTestMetrics()
        metrics.start_time = datetime.now()
        
        batch_size = 10000
        batches = row_count // batch_size
        
        for batch in range(batches):
            batch_start = time.time()
            
            try:
                async with self.pool.acquire() as conn:
                    # Prepare batch data
                    values = []
                    for i in range(batch_size):
                        record_id = batch * batch_size + i
                        values.append((
                            'sc-domain:loadtest.com',
                            datetime.now().date() - timedelta(days=record_id % 365),
                            f'https://loadtest.com/page{record_id % 1000}',
                            f'query {record_id % 100}',
                            'usa',
                            'desktop',
                            1000 + (record_id % 1000),
                            100 + (record_id % 100),
                            0.1,
                            5.0 + (record_id % 50) / 10
                        ))
                    
                    # Batch insert
                    await conn.executemany("""
                        INSERT INTO gsc.search_analytics (
                            property, date, page, query, country, device,
                            impressions, clicks, ctr, position
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT DO NOTHING
                    """, values)
                
                batch_time = time.time() - batch_start
                metrics.record_success(batch_time)
                
                if (batch + 1) % 10 == 0:
                    print(f"  Inserted batch {batch + 1}/{batches} ({(batch + 1) * batch_size} rows)")
            
            except Exception as e:
                metrics.record_failure(str(e))
                print(f"  Error in batch {batch}: {e}")
        
        metrics.end_time = datetime.now()
        
        # Verify inserted data
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.search_analytics WHERE property = 'sc-domain:loadtest.com'"
            )
            print(f"\n✓ Verified {count} records in database")
        
        return metrics
    
    async def load_test_concurrent_agents(self, agent_count: int = 100) -> LoadTestMetrics:
        """Load test with 100 concurrent agent processes."""
        print(f"\n=== Load Test: Concurrent Agents ({agent_count} agents) ===")
        
        metrics = LoadTestMetrics()
        metrics.start_time = datetime.now()
        
        # Create agents
        agents = []
        for i in range(agent_count):
            agent_type = ['watcher', 'diagnostician', 'strategist', 'dispatcher'][i % 4]
            
            if agent_type == 'watcher':
                agent = WatcherAgent(f"load_watcher_{i:03d}", self.db_config)
            elif agent_type == 'diagnostician':
                agent = DiagnosticianAgent(f"load_diag_{i:03d}", self.db_config)
            elif agent_type == 'strategist':
                agent = StrategistAgent(f"load_strat_{i:03d}", self.db_config)
            else:
                agent = DispatcherAgent(f"load_disp_{i:03d}", self.db_config)
            
            agents.append(agent)
        
        # Initialize agents
        print(f"Initializing {len(agents)} agents...")
        init_tasks = [agent.initialize() for agent in agents]
        await asyncio.gather(*init_tasks, return_exceptions=True)
        print("✓ All agents initialized")
        
        # Run agents concurrently
        print(f"Running {len(agents)} agents concurrently...")
        
        async def run_agent(agent):
            start = time.time()
            try:
                result = await agent.process({'days': 7})
                duration = time.time() - start
                
                if result.get('status') == 'success':
                    return ('success', duration)
                else:
                    return ('failure', str(result.get('error', 'Unknown error')))
            except Exception as e:
                return ('failure', str(e))
            finally:
                await agent.shutdown()
        
        # Execute all agents
        results = await asyncio.gather(*[run_agent(agent) for agent in agents], return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, tuple):
                status, data = result
                if status == 'success':
                    metrics.record_success(data)
                else:
                    metrics.record_failure(data)
            else:
                metrics.record_failure(str(result))
        
        metrics.end_time = datetime.now()
        
        return metrics
    
    async def load_test_findings_generation(self, finding_count: int = 1000) -> LoadTestMetrics:
        """Load test with 1000 findings per day."""
        print(f"\n=== Load Test: Findings Generation ({finding_count} findings) ===")
        
        metrics = LoadTestMetrics()
        metrics.start_time = datetime.now()
        
        for i in range(finding_count):
            start = time.time()
            
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO gsc.findings (
                            finding_id, agent_id, finding_type, severity,
                            title, description, affected_urls, metrics, detected_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (finding_id) DO NOTHING
                    """,
                    f'load_finding_{i:06d}',
                    'load_watcher_000',
                    ['anomaly', 'trend', 'pattern'][i % 3],
                    ['low', 'medium', 'high', 'critical'][i % 4],
                    f'Load Test Finding {i}',
                    f'Test finding description {i}',
                    [f'https://loadtest.com/page{i % 100}'],
                    {'impressions': -50 - (i % 100), 'clicks': -25 - (i % 50)},
                    datetime.now()
                    )
                
                duration = time.time() - start
                metrics.record_success(duration)
                
                if (i + 1) % 100 == 0:
                    print(f"  Generated {i + 1}/{finding_count} findings")
            
            except Exception as e:
                metrics.record_failure(str(e))
        
        metrics.end_time = datetime.now()
        
        return metrics
    
    async def load_test_recommendations_generation(self, recommendation_count: int = 500) -> LoadTestMetrics:
        """Load test with 500 recommendations per day."""
        print(f"\n=== Load Test: Recommendations Generation ({recommendation_count} recommendations) ===")
        
        metrics = LoadTestMetrics()
        metrics.start_time = datetime.now()
        
        for i in range(recommendation_count):
            start = time.time()
            
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO gsc.recommendations (
                            recommendation_id, agent_id, recommendation_type, priority,
                            title, description, action_items, estimated_impact, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (recommendation_id) DO NOTHING
                    """,
                    f'load_recommendation_{i:06d}',
                    'load_strategist_000',
                    ['optimization', 'fix', 'enhancement', 'monitoring'][i % 4],
                    ['low', 'medium', 'high', 'critical'][i % 4],
                    f'Load Test Recommendation {i}',
                    f'Test recommendation description {i}',
                    [f'Action {i}.1', f'Action {i}.2', f'Action {i}.3'],
                    {'impressions': 100 + (i % 200), 'clicks': 50 + (i % 100)},
                    datetime.now()
                    )
                
                duration = time.time() - start
                metrics.record_success(duration)
                
                if (i + 1) % 50 == 0:
                    print(f"  Generated {i + 1}/{recommendation_count} recommendations")
            
            except Exception as e:
                metrics.record_failure(str(e))
        
        metrics.end_time = datetime.now()
        
        return metrics
    
    async def load_test_query_performance(self, query_count: int = 10000) -> LoadTestMetrics:
        """Load test query performance."""
        print(f"\n=== Load Test: Query Performance ({query_count} queries) ===")
        
        metrics = LoadTestMetrics()
        metrics.start_time = datetime.now()
        
        queries = [
            "SELECT COUNT(*) FROM gsc.search_analytics WHERE date >= CURRENT_DATE - INTERVAL '7 days'",
            "SELECT page, SUM(impressions) as total_impressions FROM gsc.search_analytics WHERE date >= CURRENT_DATE - INTERVAL '30 days' GROUP BY page ORDER BY total_impressions DESC LIMIT 100",
            "SELECT * FROM gsc.findings WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' ORDER BY severity DESC",
            "SELECT r.*, f.title as finding_title FROM gsc.recommendations r LEFT JOIN gsc.findings f ON r.finding_id = f.finding_id WHERE r.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'",
            "SELECT date, SUM(impressions) as daily_impressions, SUM(clicks) as daily_clicks FROM gsc.search_analytics WHERE date >= CURRENT_DATE - INTERVAL '90 days' GROUP BY date ORDER BY date",
        ]
        
        for i in range(query_count):
            query = queries[i % len(queries)]
            start = time.time()
            
            try:
                async with self.pool.acquire() as conn:
                    await conn.fetch(query)
                
                duration = time.time() - start
                metrics.record_success(duration)
                
                if (i + 1) % 1000 == 0:
                    print(f"  Executed {i + 1}/{query_count} queries")
            
            except Exception as e:
                metrics.record_failure(str(e))
        
        metrics.end_time = datetime.now()
        
        return metrics
    
    async def cleanup_test_data(self):
        """Clean up load test data."""
        print("\n=== Cleaning up test data ===")
        
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM gsc.search_analytics WHERE property = 'sc-domain:loadtest.com'")
            await conn.execute("DELETE FROM gsc.findings WHERE finding_id LIKE 'load_finding_%'")
            await conn.execute("DELETE FROM gsc.recommendations WHERE recommendation_id LIKE 'load_recommendation_%'")
            await conn.execute("DELETE FROM gsc.outcomes WHERE outcome_id LIKE 'load_%'")
        
        print("✓ Test data cleaned up")


async def main():
    """Main load test execution."""
    parser = argparse.ArgumentParser(description='GSC Warehouse Load Testing')
    parser.add_argument('--duration', type=int, default=3600, help='Test duration in seconds')
    parser.add_argument('--skip-cleanup', action='store_true', help='Skip cleanup after tests')
    parser.add_argument('--test', choices=['all', 'ingestion', 'agents', 'findings', 'recommendations', 'queries'],
                       default='all', help='Specific test to run')
    
    args = parser.parse_args()
    
    # Database configuration
    db_config = {
        'host': os.getenv('WAREHOUSE_HOST', 'localhost'),
        'port': int(os.getenv('WAREHOUSE_PORT', 5432)),
        'user': os.getenv('WAREHOUSE_USER', 'gsc_user'),
        'password': os.getenv('WAREHOUSE_PASSWORD', ''),
        'database': os.getenv('WAREHOUSE_DB', 'gsc_warehouse')
    }
    
    print("=" * 80)
    print("GSC WAREHOUSE LOAD TESTING")
    print("=" * 80)
    print(f"Duration: {args.duration}s")
    print(f"Test: {args.test}")
    print()
    
    # Initialize tester
    tester = SystemLoadTester(db_config)
    await tester.setup()
    
    test_start = datetime.now()
    all_metrics = {}
    
    try:
        # Run tests based on selection
        if args.test in ['all', 'ingestion']:
            metrics = await tester.load_test_data_ingestion(row_count=1000000)
            all_metrics['ingestion'] = metrics.get_summary()
        
        if args.test in ['all', 'agents']:
            metrics = await tester.load_test_concurrent_agents(agent_count=100)
            all_metrics['agents'] = metrics.get_summary()
        
        if args.test in ['all', 'findings']:
            metrics = await tester.load_test_findings_generation(finding_count=1000)
            all_metrics['findings'] = metrics.get_summary()
        
        if args.test in ['all', 'recommendations']:
            metrics = await tester.load_test_recommendations_generation(recommendation_count=500)
            all_metrics['recommendations'] = metrics.get_summary()
        
        if args.test in ['all', 'queries']:
            metrics = await tester.load_test_query_performance(query_count=10000)
            all_metrics['queries'] = metrics.get_summary()
        
        # Print summary
        print("\n" + "=" * 80)
        print("LOAD TEST SUMMARY")
        print("=" * 80)
        
        test_duration = (datetime.now() - test_start).total_seconds()
        print(f"Total test duration: {test_duration:.2f}s")
        print()
        
        for test_name, metrics in all_metrics.items():
            print(f"\n{test_name.upper()}:")
            print(f"  Duration: {metrics['duration']:.2f}s")
            print(f"  Total operations: {metrics['total_operations']}")
            print(f"  Successful: {metrics['successful']}")
            print(f"  Failed: {metrics['failed']}")
            print(f"  Success rate: {metrics['success_rate']:.2%}")
            print(f"  Throughput: {metrics['throughput']:.2f} ops/s")
            print(f"  Response times:")
            print(f"    - Average: {metrics['avg_response_time']:.4f}s")
            print(f"    - Min: {metrics['min_response_time']:.4f}s")
            print(f"    - Max: {metrics['max_response_time']:.4f}s")
            print(f"    - P50: {metrics['p50_response_time']:.4f}s")
            print(f"    - P95: {metrics['p95_response_time']:.4f}s")
            print(f"    - P99: {metrics['p99_response_time']:.4f}s")
        
        print("\n" + "=" * 80)
        print("✓ All load tests completed successfully")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n✗ Load test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if not args.skip_cleanup:
            await tester.cleanup_test_data()
        
        await tester.teardown()


if __name__ == "__main__":
    asyncio.run(main())
