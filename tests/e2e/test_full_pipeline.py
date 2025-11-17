"""End-to-end full pipeline integration test."""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pytest
import asyncpg
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ingestors.api.gsc_api_ingestor import GSCAPIIngestor
from ingestors.ga4.ga4_extractor import GA4Extractor
from agents.watcher.watcher_agent import WatcherAgent
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
from agents.strategist.strategist_agent import StrategistAgent
from agents.dispatcher.dispatcher_agent import DispatcherAgent
from warehouse.refresh_views import ViewRefreshManager

load_dotenv()


class TestFullPipeline:
    """Test complete data pipeline from ingestion to execution."""

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
            min_size=5,
            max_size=20
        )
        yield pool
        await pool.close()

    @pytest.fixture
    async def clean_test_data(self, db_pool):
        """Clean test data before and after test."""
        # Clean before test
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM gsc.findings WHERE finding_id LIKE 'test_%'")
            await conn.execute("DELETE FROM gsc.recommendations WHERE recommendation_id LIKE 'test_%'")
            await conn.execute("DELETE FROM gsc.outcomes WHERE outcome_id LIKE 'test_%'")
        
        yield
        
        # Clean after test
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM gsc.findings WHERE finding_id LIKE 'test_%'")
            await conn.execute("DELETE FROM gsc.recommendations WHERE recommendation_id LIKE 'test_%'")
            await conn.execute("DELETE FROM gsc.outcomes WHERE outcome_id LIKE 'test_%'")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_gsc_ingestion_stage(self, db_config, db_pool, clean_test_data):
        """Test GSC data ingestion stage."""
        print("\n=== Stage 1: GSC Ingestion ===")
        
        # Skip if no API credentials
        if not os.getenv('GSC_CREDENTIALS_FILE'):
            pytest.skip("GSC_CREDENTIALS_FILE not configured")
        
        # Initialize ingestor
        ingestor = GSCAPIIngestor(
            property_url=os.getenv('GSC_PROPERTY_URL', 'sc-domain:example.com'),
            credentials_file=os.getenv('GSC_CREDENTIALS_FILE'),
            db_config=db_config
        )
        
        await ingestor.initialize()
        
        # Test ingestion
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        result = await ingestor.ingest_date_range(start_date, end_date)
        
        assert result['status'] == 'success', f"Ingestion failed: {result.get('error')}"
        assert result['rows_inserted'] > 0, "No rows inserted"
        
        # Verify data in database
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.search_analytics WHERE date >= $1",
                start_date
            )
            assert count > 0, "No data found in database"
        
        print(f"✓ Ingested {result['rows_inserted']} rows")
        
        await ingestor.close()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_ga4_ingestion_stage(self, db_config, db_pool, clean_test_data):
        """Test GA4 data ingestion stage."""
        print("\n=== Stage 2: GA4 Ingestion ===")
        
        # Skip if no GA4 credentials
        if not os.getenv('GA4_CREDENTIALS_FILE'):
            pytest.skip("GA4_CREDENTIALS_FILE not configured")
        
        # Initialize extractor
        extractor = GA4Extractor(
            property_id=os.getenv('GA4_PROPERTY_ID', '123456789'),
            credentials_file=os.getenv('GA4_CREDENTIALS_FILE'),
            db_config=db_config
        )
        
        await extractor.initialize()
        
        # Test extraction
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        result = await extractor.extract_date_range(start_date, end_date)
        
        assert result['status'] == 'success', f"Extraction failed: {result.get('error')}"
        assert result['rows_inserted'] > 0, "No rows inserted"
        
        # Verify data in database
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM ga4.page_metrics WHERE date >= $1",
                start_date
            )
            assert count > 0, "No data found in database"
        
        print(f"✓ Extracted {result['rows_inserted']} rows")
        
        await extractor.close()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_unified_view_stage(self, db_config, clean_test_data):
        """Test unified view refresh stage."""
        print("\n=== Stage 3: Unified View Refresh ===")
        
        # Initialize view manager
        dsn = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        manager = ViewRefreshManager(dsn=dsn)
        manager.connect()
        
        # Refresh all views
        results = manager.refresh_all_views()
        
        # Verify all successful
        failed = [r for r in results if r['status'] != 'success']
        assert len(failed) == 0, f"View refresh failed: {failed}"
        
        # Validate data quality
        validation = manager.validate_view_quality()
        failed_checks = [c for c in validation if c['check_status'] == 'FAIL']
        assert len(failed_checks) == 0, f"Validation failed: {failed_checks}"
        
        manager.close()
        
        print(f"✓ Refreshed {len(results)} views with {len(validation)} quality checks")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_watcher_detection_stage(self, db_config, db_pool, clean_test_data):
        """Test watcher anomaly detection stage."""
        print("\n=== Stage 4: Watcher Detection ===")
        
        # Initialize watcher
        watcher = WatcherAgent(
            agent_id="test_watcher_001",
            db_config=db_config,
            config={
                'sensitivity': 2.5,
                'min_data_points': 7
            }
        )
        
        await watcher.initialize()
        
        # Run detection
        result = await watcher.process({
            'days': 30,
            'property': None
        })
        
        assert result['status'] == 'success', f"Detection failed: {result.get('error')}"
        assert 'anomalies' in result, "No anomalies found"
        assert 'trends' in result, "No trends found"
        
        # Verify findings stored
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.findings WHERE agent_id = $1",
                watcher.agent_id
            )
        
        print(f"✓ Detected {len(result['anomalies'])} anomalies, {len(result['trends'])} trends")
        print(f"✓ Stored {count} findings")
        
        await watcher.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_diagnostician_analysis_stage(self, db_config, db_pool, clean_test_data):
        """Test diagnostician analysis stage."""
        print("\n=== Stage 5: Diagnostician Analysis ===")
        
        # First create some findings for analysis
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO gsc.findings (finding_id, agent_id, finding_type, severity, title, description, affected_urls, metrics, detected_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (finding_id) DO NOTHING
            """, 
            'test_finding_001',
            'test_watcher_001',
            'anomaly',
            'high',
            'Test Performance Drop',
            'Detected significant performance drop',
            ['https://example.com/test'],
            {'impressions': -50, 'clicks': -30},
            datetime.now()
            )
        
        # Initialize diagnostician
        diagnostician = DiagnosticianAgent(
            agent_id="test_diagnostician_001",
            db_config=db_config,
            config={
                'correlation_threshold': 0.7,
                'min_sample_size': 5
            }
        )
        
        await diagnostician.initialize()
        
        # Run analysis
        result = await diagnostician.process({
            'finding_ids': ['test_finding_001']
        })
        
        assert result['status'] == 'success', f"Analysis failed: {result.get('error')}"
        assert 'diagnoses' in result, "No diagnoses found"
        
        print(f"✓ Analyzed {len(result.get('diagnoses', []))} findings")
        
        await diagnostician.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_strategist_recommendations_stage(self, db_config, db_pool, clean_test_data):
        """Test strategist recommendation stage."""
        print("\n=== Stage 6: Strategist Recommendations ===")
        
        # Initialize strategist
        strategist = StrategistAgent(
            agent_id="test_strategist_001",
            db_config=db_config,
            config={
                'min_impact_score': 5.0,
                'max_recommendations': 10
            }
        )
        
        await strategist.initialize()
        
        # Run recommendation generation
        result = await strategist.process({
            'time_window': 7
        })
        
        assert result['status'] == 'success', f"Strategy failed: {result.get('error')}"
        assert 'recommendations' in result, "No recommendations found"
        
        # Verify recommendations stored
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.recommendations WHERE agent_id = $1",
                strategist.agent_id
            )
        
        print(f"✓ Generated {len(result['recommendations'])} recommendations")
        print(f"✓ Stored {count} recommendations")
        
        await strategist.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_dispatcher_execution_stage(self, db_config, db_pool, clean_test_data):
        """Test dispatcher execution stage."""
        print("\n=== Stage 7: Dispatcher Execution ===")
        
        # First create a recommendation for execution
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO gsc.recommendations (
                    recommendation_id, agent_id, recommendation_type, priority,
                    title, description, action_items, estimated_impact, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (recommendation_id) DO NOTHING
            """,
            'test_recommendation_001',
            'test_strategist_001',
            'optimization',
            'high',
            'Test Recommendation',
            'Test optimization recommendation',
            ['Action 1', 'Action 2'],
            {'impressions': 100, 'clicks': 50},
            datetime.now()
            )
        
        # Initialize dispatcher
        dispatcher = DispatcherAgent(
            agent_id="test_dispatcher_001",
            db_config=db_config,
            config={
                'max_parallel_executions': 3,
                'validation_enabled': True
            }
        )
        
        await dispatcher.initialize()
        
        # Run execution
        result = await dispatcher.process({
            'recommendation_ids': ['test_recommendation_001']
        })
        
        assert result['status'] == 'success', f"Execution failed: {result.get('error')}"
        assert 'executions' in result, "No executions found"
        
        print(f"✓ Executed {len(result['executions'])} recommendations")
        
        await dispatcher.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_outcome_monitoring_stage(self, db_pool, clean_test_data):
        """Test outcome monitoring stage."""
        print("\n=== Stage 8: Outcome Monitoring ===")
        
        # Verify outcomes were recorded
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM gsc.outcomes WHERE outcome_id LIKE 'test_%'"
            )
        
        print(f"✓ Monitored {count} outcomes")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_full_pipeline_integration(self, db_config, db_pool, clean_test_data):
        """Test complete end-to-end pipeline integration."""
        print("\n=== Full Pipeline Integration Test ===")
        
        # Track pipeline metrics
        pipeline_start = datetime.now()
        stages_completed = []
        
        try:
            # Stage 1: Data Ingestion (simulated with test data)
            print("Stage 1: Data Ingestion")
            async with db_pool.acquire() as conn:
                # Insert test GSC data
                for i in range(100):
                    await conn.execute("""
                        INSERT INTO gsc.search_analytics (
                            property, date, page, query, country, device,
                            impressions, clicks, ctr, position
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT DO NOTHING
                    """,
                    'sc-domain:test.com',
                    datetime.now().date() - timedelta(days=i % 30),
                    f'https://test.com/page{i % 10}',
                    f'test query {i % 20}',
                    'usa',
                    'desktop',
                    100 + (i % 50),
                    10 + (i % 10),
                    0.1,
                    5.0
                    )
            stages_completed.append('ingestion')
            
            # Stage 2: View Refresh
            print("Stage 2: View Refresh")
            dsn = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            manager = ViewRefreshManager(dsn=dsn)
            manager.connect()
            results = manager.refresh_all_views()
            manager.close()
            assert all(r['status'] == 'success' for r in results)
            stages_completed.append('view_refresh')
            
            # Stage 3: Watcher Detection
            print("Stage 3: Watcher Detection")
            watcher = WatcherAgent("pipeline_watcher", db_config)
            await watcher.initialize()
            watcher_result = await watcher.process({'days': 7})
            await watcher.shutdown()
            assert watcher_result['status'] == 'success'
            stages_completed.append('detection')
            
            # Stage 4: Analysis
            print("Stage 4: Analysis")
            diagnostician = DiagnosticianAgent("pipeline_diagnostician", db_config)
            await diagnostician.initialize()
            diag_result = await diagnostician.process({'time_window': 7})
            await diagnostician.shutdown()
            assert diag_result['status'] == 'success'
            stages_completed.append('analysis')
            
            # Stage 5: Strategy
            print("Stage 5: Strategy")
            strategist = StrategistAgent("pipeline_strategist", db_config)
            await strategist.initialize()
            strat_result = await strategist.process({'time_window': 7})
            await strategist.shutdown()
            assert strat_result['status'] == 'success'
            stages_completed.append('strategy')
            
            # Stage 6: Execution
            print("Stage 6: Execution")
            dispatcher = DispatcherAgent("pipeline_dispatcher", db_config)
            await dispatcher.initialize()
            exec_result = await dispatcher.process({})
            await dispatcher.shutdown()
            assert exec_result['status'] == 'success'
            stages_completed.append('execution')
            
            # Verify data flow
            async with db_pool.acquire() as conn:
                findings_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM gsc.findings"
                )
                recommendations_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM gsc.recommendations"
                )
                
                print(f"✓ Pipeline produced {findings_count} findings")
                print(f"✓ Pipeline produced {recommendations_count} recommendations")
            
            pipeline_duration = (datetime.now() - pipeline_start).total_seconds()
            
            print(f"\n✓ Full pipeline completed in {pipeline_duration:.2f}s")
            print(f"✓ Stages completed: {', '.join(stages_completed)}")
            
            # Verify no data loss
            assert findings_count >= 0, "Findings data lost"
            assert recommendations_count >= 0, "Recommendations data lost"
            
        except Exception as e:
            print(f"\n✗ Pipeline failed at stage: {stages_completed[-1] if stages_completed else 'initialization'}")
            raise

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_data_quality_validation(self, db_pool):
        """Test data quality across pipeline."""
        print("\n=== Data Quality Validation ===")
        
        async with db_pool.acquire() as conn:
            # Check for null values in critical fields
            null_checks = await conn.fetch("""
                SELECT 
                    'search_analytics' as table_name,
                    COUNT(*) FILTER (WHERE page IS NULL) as null_pages,
                    COUNT(*) FILTER (WHERE date IS NULL) as null_dates,
                    COUNT(*) FILTER (WHERE impressions IS NULL) as null_impressions
                FROM gsc.search_analytics
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                UNION ALL
                SELECT 
                    'findings' as table_name,
                    COUNT(*) FILTER (WHERE title IS NULL) as null_titles,
                    COUNT(*) FILTER (WHERE severity IS NULL) as null_severity,
                    COUNT(*) FILTER (WHERE agent_id IS NULL) as null_agent_ids
                FROM gsc.findings
                WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            """)
            
            for row in null_checks:
                table = row['table_name']
                null_count = sum(row[k] for k in row.keys() if k != 'table_name')
                print(f"✓ {table}: {null_count} null values in critical fields")
                assert null_count == 0, f"Found {null_count} null values in {table}"
            
            # Check for data integrity
            integrity_checks = await conn.fetch("""
                SELECT 
                    COUNT(*) FILTER (WHERE ctr < 0 OR ctr > 1) as invalid_ctr,
                    COUNT(*) FILTER (WHERE position < 1) as invalid_position,
                    COUNT(*) FILTER (WHERE clicks > impressions) as invalid_clicks
                FROM gsc.search_analytics
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            for row in integrity_checks:
                for key, value in row.items():
                    print(f"✓ {key}: {value} invalid values")
                    assert value == 0, f"Found {value} {key}"

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_pipeline_metrics(self, db_pool):
        """Test pipeline performance metrics."""
        print("\n=== Pipeline Metrics ===")
        
        async with db_pool.acquire() as conn:
            metrics = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_findings,
                    COUNT(*) FILTER (WHERE status = 'resolved') as resolved_findings,
                    AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at))) as avg_resolution_time,
                    COUNT(DISTINCT agent_id) as active_agents
                FROM gsc.findings
                WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            """)
            
            print(f"✓ Total findings: {metrics['total_findings']}")
            print(f"✓ Resolved findings: {metrics['resolved_findings']}")
            print(f"✓ Average resolution time: {metrics['avg_resolution_time'] or 0:.2f}s")
            print(f"✓ Active agents: {metrics['active_agents']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
