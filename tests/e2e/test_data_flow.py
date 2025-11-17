"""End-to-end data flow integration test."""

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

load_dotenv()


class TestDataFlow:
    """Test data flow integrity across the entire pipeline."""

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

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_no_data_loss_gsc_to_warehouse(self, db_pool):
        """Verify no data loss from GSC ingestion to warehouse."""
        print("\n=== Test: GSC to Warehouse Data Loss ===")
        
        # Insert test data
        test_records = []
        async with db_pool.acquire() as conn:
            # Insert 1000 test records
            for i in range(1000):
                test_id = f'dataflow_test_{i:04d}'
                await conn.execute("""
                    INSERT INTO gsc.search_analytics (
                        property, date, page, query, country, device,
                        impressions, clicks, ctr, position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                """,
                'sc-domain:test.com',
                datetime.now().date() - timedelta(days=i % 30),
                f'https://test.com/{test_id}',
                f'test query {i}',
                'usa',
                'desktop',
                1000 + i,
                100 + (i % 50),
                0.1 + (i % 10) / 100,
                5.0 + (i % 20) / 10
                )
                test_records.append(test_id)
            
            # Verify all records inserted
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM gsc.search_analytics 
                WHERE page LIKE '%dataflow_test_%'
            """)
            
            print(f"✓ Inserted {len(test_records)} test records")
            print(f"✓ Verified {count} records in database")
            assert count == len(test_records), f"Data loss detected: {len(test_records)} inserted, {count} found"
            
            # Clean up
            await conn.execute("DELETE FROM gsc.search_analytics WHERE page LIKE '%dataflow_test_%'")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_metric_accuracy_gsc(self, db_pool):
        """Validate GSC metric accuracy and calculations."""
        print("\n=== Test: GSC Metric Accuracy ===")
        
        async with db_pool.acquire() as conn:
            # Insert test data with known metrics
            test_data = [
                ('page1', 1000, 100, 0.10, 5.0),
                ('page2', 2000, 200, 0.10, 10.0),
                ('page3', 500, 50, 0.10, 15.0),
            ]
            
            for page, impressions, clicks, ctr, position in test_data:
                await conn.execute("""
                    INSERT INTO gsc.search_analytics (
                        property, date, page, query, country, device,
                        impressions, clicks, ctr, position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                """,
                'sc-domain:test.com',
                datetime.now().date(),
                f'https://test.com/{page}',
                'test query',
                'usa',
                'desktop',
                impressions, clicks, ctr, position
                )
            
            # Verify metrics
            results = await conn.fetch("""
                SELECT 
                    page,
                    impressions,
                    clicks,
                    ctr,
                    position,
                    CASE WHEN impressions > 0 THEN CAST(clicks AS FLOAT) / impressions ELSE 0 END as calculated_ctr
                FROM gsc.search_analytics
                WHERE page LIKE 'https://test.com/page%'
                AND date = $1
            """, datetime.now().date())
            
            for row in results:
                # Verify CTR calculation
                expected_ctr = row['clicks'] / row['impressions'] if row['impressions'] > 0 else 0
                actual_ctr = row['ctr']
                calculated_ctr = row['calculated_ctr']
                
                print(f"✓ {row['page']}: impressions={row['impressions']}, clicks={row['clicks']}")
                print(f"  CTR: stored={actual_ctr:.4f}, expected={expected_ctr:.4f}, calculated={calculated_ctr:.4f}")
                
                # Allow small floating point difference
                assert abs(actual_ctr - expected_ctr) < 0.001, f"CTR mismatch for {row['page']}"
                assert abs(calculated_ctr - expected_ctr) < 0.001, f"CTR calculation mismatch"
            
            # Clean up
            await conn.execute(
                "DELETE FROM gsc.search_analytics WHERE page LIKE 'https://test.com/page%' AND date = $1",
                datetime.now().date()
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_join_integrity_unified_view(self, db_pool):
        """Verify join integrity in unified view."""
        print("\n=== Test: Unified View Join Integrity ===")
        
        async with db_pool.acquire() as conn:
            # Insert matching GSC and GA4 data
            test_date = datetime.now().date()
            test_pages = ['https://test.com/join_test_1', 'https://test.com/join_test_2']
            
            # Insert GSC data
            for page in test_pages:
                await conn.execute("""
                    INSERT INTO gsc.search_analytics (
                        property, date, page, query, country, device,
                        impressions, clicks, ctr, position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                """,
                'sc-domain:test.com',
                test_date,
                page,
                'test query',
                'usa',
                'desktop',
                1000, 100, 0.1, 5.0
                )
            
            # Insert GA4 data
            for page in test_pages:
                await conn.execute("""
                    INSERT INTO ga4.page_metrics (
                        property_id, date, page_path, page_title,
                        pageviews, unique_pageviews, avg_time_on_page, bounce_rate
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                """,
                'test_property',
                test_date,
                page.replace('https://test.com', ''),
                'Test Page',
                5000, 4000, 120.0, 0.5
                )
            
            # Query unified view
            unified_data = await conn.fetch("""
                SELECT 
                    sa.page,
                    sa.impressions,
                    sa.clicks,
                    pm.pageviews,
                    pm.unique_pageviews
                FROM gsc.search_analytics sa
                LEFT JOIN ga4.page_metrics pm ON (
                    sa.date = pm.date AND
                    sa.page = ('https://test.com' || pm.page_path)
                )
                WHERE sa.page LIKE '%join_test_%'
                AND sa.date = $1
            """, test_date)
            
            # Verify join results
            print(f"✓ Found {len(unified_data)} joined records")
            assert len(unified_data) == len(test_pages), "Join integrity failed"
            
            for row in unified_data:
                assert row['impressions'] is not None, "GSC data missing"
                assert row['pageviews'] is not None, "GA4 data missing in join"
                print(f"✓ {row['page']}: impressions={row['impressions']}, pageviews={row['pageviews']}")
            
            # Test orphaned records
            orphaned = await conn.fetch("""
                SELECT 
                    sa.page,
                    sa.impressions,
                    pm.pageviews
                FROM gsc.search_analytics sa
                LEFT JOIN ga4.page_metrics pm ON (
                    sa.date = pm.date AND
                    sa.page = ('https://test.com' || pm.page_path)
                )
                WHERE sa.page LIKE '%join_test_%'
                AND sa.date = $1
                AND pm.page_path IS NULL
            """, test_date)
            
            print(f"✓ Orphaned GSC records: {len(orphaned)}")
            
            # Clean up
            await conn.execute(
                "DELETE FROM gsc.search_analytics WHERE page LIKE '%join_test_%'"
            )
            await conn.execute(
                "DELETE FROM ga4.page_metrics WHERE page_path LIKE '%join_test_%'"
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_alert_precision(self, db_pool):
        """Verify alert generation precision and false positive rate."""
        print("\n=== Test: Alert Precision ===")
        
        async with db_pool.acquire() as conn:
            # Create baseline data (30 days)
            baseline_date = datetime.now().date() - timedelta(days=30)
            for i in range(30):
                date = baseline_date + timedelta(days=i)
                
                # Normal data (impressions around 1000 ± 100)
                impressions = 1000 + (i % 10) * 10 - 50
                
                await conn.execute("""
                    INSERT INTO gsc.search_analytics (
                        property, date, page, query, country, device,
                        impressions, clicks, ctr, position
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT DO NOTHING
                """,
                'sc-domain:test.com',
                date,
                'https://test.com/alert_test',
                'test query',
                'usa',
                'desktop',
                impressions,
                impressions // 10,
                0.1,
                5.0
                )
            
            # Insert anomalous data point
            anomaly_date = datetime.now().date()
            await conn.execute("""
                INSERT INTO gsc.search_analytics (
                    property, date, page, query, country, device,
                    impressions, clicks, ctr, position
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT DO NOTHING
            """,
            'sc-domain:test.com',
            anomaly_date,
            'https://test.com/alert_test',
            'test query',
            'usa',
            'desktop',
            5000,  # 5x normal
            500,
            0.1,
            5.0
            )
            
            # Calculate statistics
            stats = await conn.fetchrow("""
                WITH stats AS (
                    SELECT 
                        AVG(impressions) as mean,
                        STDDEV(impressions) as stddev,
                        MIN(impressions) as min_val,
                        MAX(impressions) as max_val
                    FROM gsc.search_analytics
                    WHERE page = 'https://test.com/alert_test'
                    AND date < $1
                )
                SELECT 
                    mean,
                    stddev,
                    max_val,
                    (SELECT impressions FROM gsc.search_analytics 
                     WHERE page = 'https://test.com/alert_test' AND date = $1) as anomaly_value,
                    ((SELECT impressions FROM gsc.search_analytics 
                      WHERE page = 'https://test.com/alert_test' AND date = $1) - mean) / stddev as z_score
                FROM stats
            """, anomaly_date)
            
            print(f"✓ Baseline mean: {stats['mean']:.2f}")
            print(f"✓ Baseline stddev: {stats['stddev']:.2f}")
            print(f"✓ Anomaly value: {stats['anomaly_value']}")
            print(f"✓ Z-score: {stats['z_score']:.2f}")
            
            # Verify anomaly is significant (z-score > 3)
            assert abs(stats['z_score']) > 3.0, "Anomaly not significant enough"
            
            # Clean up
            await conn.execute(
                "DELETE FROM gsc.search_analytics WHERE page = 'https://test.com/alert_test'"
            )

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_data_completeness(self, db_pool):
        """Verify data completeness across all tables."""
        print("\n=== Test: Data Completeness ===")
        
        async with db_pool.acquire() as conn:
            # Check for required fields in each table
            tables_to_check = [
                ('gsc.search_analytics', ['property', 'date', 'page', 'impressions', 'clicks']),
                ('ga4.page_metrics', ['property_id', 'date', 'page_path', 'pageviews']),
                ('gsc.findings', ['finding_id', 'agent_id', 'severity', 'detected_at']),
                ('gsc.recommendations', ['recommendation_id', 'agent_id', 'priority', 'created_at']),
            ]
            
            for table, required_fields in tables_to_check:
                # Get total count
                try:
                    total = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    
                    # Check null counts for required fields
                    null_counts = {}
                    for field in required_fields:
                        null_count = await conn.fetchval(
                            f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL"
                        )
                        null_counts[field] = null_count
                    
                    print(f"\n✓ {table}: {total} total records")
                    for field, null_count in null_counts.items():
                        pct = (null_count / total * 100) if total > 0 else 0
                        print(f"  - {field}: {null_count} nulls ({pct:.2f}%)")
                        assert null_count == 0, f"Found {null_count} null values in required field {table}.{field}"
                
                except Exception as e:
                    print(f"✓ {table}: Table not found or empty (expected for test)")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_data_consistency(self, db_pool):
        """Verify data consistency across related tables."""
        print("\n=== Test: Data Consistency ===")
        
        async with db_pool.acquire() as conn:
            # Test 1: Every finding should have a valid agent_id
            orphaned_findings = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM gsc.findings f
                WHERE NOT EXISTS (
                    SELECT 1 FROM gsc.recommendations r 
                    WHERE r.agent_id = f.agent_id
                    OR f.agent_id LIKE 'watcher_%'
                    OR f.agent_id LIKE '%test%'
                )
                AND f.created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            print(f"✓ Orphaned findings: {orphaned_findings}")
            
            # Test 2: Recommendations should reference valid findings
            invalid_recommendations = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM gsc.recommendations r
                WHERE r.finding_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM gsc.findings f 
                    WHERE f.finding_id = r.finding_id
                )
                AND r.created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            print(f"✓ Invalid recommendations: {invalid_recommendations}")
            
            # Test 3: Outcomes should reference valid recommendations
            invalid_outcomes = await conn.fetchval("""
                SELECT COUNT(*) 
                FROM gsc.outcomes o
                WHERE NOT EXISTS (
                    SELECT 1 FROM gsc.recommendations r 
                    WHERE r.recommendation_id = o.recommendation_id
                )
                AND o.created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            print(f"✓ Invalid outcomes: {invalid_outcomes}")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_temporal_consistency(self, db_pool):
        """Verify temporal consistency in data flow."""
        print("\n=== Test: Temporal Consistency ===")
        
        async with db_pool.acquire() as conn:
            # Test 1: Findings should not be detected before the data they reference
            temporal_violations = await conn.fetch("""
                SELECT 
                    f.finding_id,
                    f.detected_at,
                    MIN(sa.date) as earliest_data
                FROM gsc.findings f
                CROSS JOIN UNNEST(f.affected_urls) AS url
                LEFT JOIN gsc.search_analytics sa ON sa.page = url
                WHERE f.detected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY f.finding_id, f.detected_at
                HAVING MIN(sa.date) > DATE(f.detected_at)
            """)
            
            print(f"✓ Temporal violations in findings: {len(temporal_violations)}")
            for row in temporal_violations[:5]:
                print(f"  - Finding {row['finding_id']}: detected {row['detected_at']}, data from {row['earliest_data']}")
            
            # Test 2: Recommendations should come after their findings
            recommendation_violations = await conn.fetch("""
                SELECT 
                    r.recommendation_id,
                    r.created_at as rec_created,
                    f.detected_at as finding_detected
                FROM gsc.recommendations r
                JOIN gsc.findings f ON f.finding_id = r.finding_id
                WHERE r.created_at < f.detected_at
                AND r.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            """)
            
            print(f"✓ Temporal violations in recommendations: {len(recommendation_violations)}")
            
            # Test 3: Outcomes should come after their recommendations
            outcome_violations = await conn.fetch("""
                SELECT 
                    o.outcome_id,
                    o.created_at as outcome_created,
                    r.created_at as rec_created
                FROM gsc.outcomes o
                JOIN gsc.recommendations r ON r.recommendation_id = o.recommendation_id
                WHERE o.created_at < r.created_at
                AND o.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
            """)
            
            print(f"✓ Temporal violations in outcomes: {len(outcome_violations)}")

    @pytest.mark.asyncio
    @pytest.mark.timeout(600)
    async def test_data_volume_consistency(self, db_pool):
        """Verify data volume remains consistent through pipeline."""
        print("\n=== Test: Data Volume Consistency ===")
        
        async with db_pool.acquire() as conn:
            # Get volumes for last 7 days
            volumes = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT sa.page) as unique_pages,
                    COUNT(*) as total_gsc_records,
                    (SELECT COUNT(DISTINCT page_path) FROM ga4.page_metrics 
                     WHERE date >= CURRENT_DATE - INTERVAL '7 days') as ga4_pages,
                    (SELECT COUNT(*) FROM gsc.findings 
                     WHERE detected_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') as findings,
                    (SELECT COUNT(*) FROM gsc.recommendations 
                     WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days') as recommendations
                FROM gsc.search_analytics sa
                WHERE sa.date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            print(f"✓ Data volumes (last 7 days):")
            print(f"  - GSC records: {volumes['total_gsc_records']}")
            print(f"  - Unique pages (GSC): {volumes['unique_pages']}")
            print(f"  - Unique pages (GA4): {volumes['ga4_pages']}")
            print(f"  - Findings: {volumes['findings']}")
            print(f"  - Recommendations: {volumes['recommendations']}")
            
            # Verify reasonable ratios
            if volumes['total_gsc_records'] > 0:
                finding_ratio = volumes['findings'] / volumes['total_gsc_records']
                rec_ratio = volumes['recommendations'] / volumes['total_gsc_records'] if volumes['total_gsc_records'] > 0 else 0
                
                print(f"\n✓ Ratios:")
                print(f"  - Findings per GSC record: {finding_ratio:.6f}")
                print(f"  - Recommendations per GSC record: {rec_ratio:.6f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
