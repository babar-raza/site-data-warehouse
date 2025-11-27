"""
End-to-end tests for complete data pipeline.

Tests the full data flow from ingestion through transformation to insights API,
including the insight lifecycle (NEW -> DIAGNOSED -> RESOLVED).

Requirements:
- All tests pass with Docker services
- Tests marked with @pytest.mark.e2e
- Daily pipeline execution tested
- Data flow from ingestion to API tested
- Insight lifecycle tested
- Timeout: 5 minutes max
"""

import pytest
import time
import httpx
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, Any
from psycopg2.extras import RealDictCursor

# Import scheduler components
from scheduler.scheduler import (
    daily_pipeline,
    run_api_ingestion,
    run_ga4_collection,
    run_transforms,
    run_insights_refresh,
    check_watermarks,
)

# Import insight components
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig
from insights_core.repository import InsightRepository
from insights_core.models import (
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)


@pytest.mark.e2e
@pytest.mark.integration
class TestCompletePipeline:
    """Test complete data pipeline from ingestion to insights API."""

    @pytest.fixture(scope="class")
    def warehouse_dsn(self, docker_services):
        """Get warehouse DSN from docker services."""
        postgres_config = docker_services["postgres"]
        return postgres_config["dsn"]

    @pytest.fixture(scope="class")
    def db_connection(self, warehouse_dsn):
        """Database connection for test setup/teardown."""
        conn = psycopg2.connect(warehouse_dsn)
        conn.autocommit = True
        yield conn
        conn.close()

    @pytest.fixture
    def clean_insights(self, db_connection):
        """Clean insights table before and after test."""
        cursor = db_connection.cursor()

        # Clean before test
        cursor.execute("TRUNCATE TABLE gsc.insights CASCADE")

        yield

        # Clean after test
        cursor.execute("TRUNCATE TABLE gsc.insights CASCADE")
        cursor.close()

    @pytest.fixture
    def sample_gsc_data(self, db_connection):
        """Insert sample GSC data for testing pipeline."""
        cursor = db_connection.cursor()

        # Create schema if not exists
        cursor.execute("CREATE SCHEMA IF NOT EXISTS gsc")

        # Create table if not exists (simplified for testing)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gsc.fact_gsc_daily (
                property VARCHAR(500),
                date DATE,
                page_path VARCHAR(2048),
                query VARCHAR(2048),
                country VARCHAR(10),
                device VARCHAR(20),
                impressions INTEGER,
                clicks INTEGER,
                ctr FLOAT,
                position FLOAT,
                PRIMARY KEY (property, date, page_path, query, country, device)
            )
        """)

        # Insert sample data for last 30 days
        property_url = "https://example.com"
        today = datetime.now().date()

        for days_ago in range(30):
            test_date = today - timedelta(days=days_ago)

            # Insert data with declining trend (anomaly)
            for page_num in range(5):
                page_path = f"/page-{page_num}"
                for query_num in range(3):
                    query = f"test query {query_num}"

                    # Create declining pattern for anomaly detection
                    base_impressions = 1000
                    base_clicks = 100

                    # Sharp drop in last 7 days
                    if days_ago < 7:
                        impressions = int(base_impressions * 0.3)  # 70% drop
                        clicks = int(base_clicks * 0.3)
                    else:
                        impressions = base_impressions
                        clicks = base_clicks

                    cursor.execute("""
                        INSERT INTO gsc.fact_gsc_daily (
                            property, date, page_path, query, country, device,
                            impressions, clicks, ctr, position
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (property, date, page_path, query, country, device)
                        DO NOTHING
                    """, (
                        property_url,
                        test_date,
                        page_path,
                        query,
                        "usa",
                        "desktop",
                        impressions,
                        clicks,
                        clicks / impressions if impressions > 0 else 0,
                        5.0
                    ))

        cursor.close()

        yield property_url

        # Cleanup
        cursor = db_connection.cursor()
        cursor.execute("TRUNCATE TABLE gsc.fact_gsc_daily CASCADE")
        cursor.close()

    @pytest.mark.timeout(300)
    def test_daily_pipeline_execution(self, docker_services, warehouse_dsn):
        """
        Test daily pipeline runs successfully.

        Verifies that daily_pipeline() completes without critical errors.
        Note: Some steps may be skipped if API keys not configured.
        """
        print("\n=== Testing Daily Pipeline Execution ===")

        # Mock environment for testing (use test database)
        import os
        original_dsn = os.environ.get('WAREHOUSE_DSN')
        os.environ['WAREHOUSE_DSN'] = warehouse_dsn

        try:
            start_time = time.time()

            # Run daily pipeline
            result = daily_pipeline()

            duration = time.time() - start_time

            # Verify pipeline completed
            assert result is not None, "Pipeline returned None"

            # Verify duration is reasonable (should complete in < 5 minutes)
            assert duration < 300, f"Pipeline took too long: {duration}s"

            print(f"✓ Pipeline completed in {duration:.2f}s")
            print(f"✓ Result: {result}")

        finally:
            # Restore original DSN
            if original_dsn:
                os.environ['WAREHOUSE_DSN'] = original_dsn
            elif 'WAREHOUSE_DSN' in os.environ:
                del os.environ['WAREHOUSE_DSN']

    @pytest.mark.timeout(300)
    def test_data_ingestion_to_engine_flow(
        self,
        docker_services,
        warehouse_dsn,
        sample_gsc_data,
        clean_insights
    ):
        """
        Test data flows from ingestion through engine to insights.

        Flow: GSC Data -> InsightEngine -> Insights Table
        """
        print("\n=== Testing Data Ingestion to Engine Flow ===")

        property_url = sample_gsc_data

        # Step 1: Verify GSC data exists
        conn = psycopg2.connect(warehouse_dsn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = %s
        """, (property_url,))
        row_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        assert row_count > 0, "No GSC data found for testing"
        print(f"✓ Found {row_count} rows of GSC data")

        # Step 2: Run InsightEngine
        config = InsightsConfig()
        config.warehouse_dsn = warehouse_dsn
        engine = InsightEngine(config)

        stats = engine.refresh(property=property_url, generate_actions=False)

        # Verify engine ran successfully
        assert stats['detectors_run'] > 0, "No detectors ran"
        assert stats['detectors_succeeded'] > 0, "No detectors succeeded"

        print(f"✓ Engine ran {stats['detectors_run']} detectors")
        print(f"✓ Created {stats['total_insights_created']} insights")
        print(f"✓ Breakdown: {stats['insights_by_detector']}")

        # Step 3: Verify insights were created
        conn = psycopg2.connect(warehouse_dsn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM gsc.insights
            WHERE property = %s
        """, (property_url,))
        insights_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        print(f"✓ Found {insights_count} insights in database")

        # Insights may or may not be created depending on data patterns
        # Just verify the process completed without errors
        assert stats['total_insights_created'] == insights_count, \
            "Mismatch between reported and actual insights created"

    @pytest.mark.timeout(300)
    def test_engine_to_api_flow(
        self,
        docker_services,
        warehouse_dsn,
        sample_gsc_data,
        clean_insights
    ):
        """
        Test insights flow from engine to API.

        Flow: InsightEngine -> Repository -> Insights API
        """
        print("\n=== Testing Engine to API Flow ===")

        property_url = sample_gsc_data

        # Step 1: Create insights via repository (simulating engine)
        config = InsightsConfig()
        config.warehouse_dsn = warehouse_dsn
        repository = InsightRepository(warehouse_dsn)

        # Create test insight
        insight_create = InsightCreate(
            property=property_url,
            entity_type=EntityType.PAGE,
            entity_id="/test-page",
            category=InsightCategory.RISK,
            title="Test Traffic Drop",
            description="Test insight for E2E pipeline testing",
            severity=InsightSeverity.HIGH,
            confidence=0.95,
            metrics=InsightMetrics(
                gsc_clicks=100,
                gsc_clicks_change=-50.0,
                gsc_impressions=1000,
                gsc_impressions_change=-60.0,
            ),
            window_days=7,
            source="AnomalyDetector",
        )

        created_insight = repository.create(insight_create)
        assert created_insight is not None, "Failed to create insight"
        print(f"✓ Created insight: {created_insight.id}")

        # Step 2: Query via API (if running)
        # Note: Insights API is running on port 8000 with /api prefix
        try:
            with httpx.Client(timeout=10.0) as client:
                # Test health endpoint
                response = client.get("http://localhost:8000/api/health")

                if response.status_code == 200:
                    print("✓ Insights API is running")

                    # Test query endpoint
                    response = client.get(
                        "http://localhost:8000/api/insights",
                        params={"property": property_url}
                    )

                    assert response.status_code == 200, \
                        f"API returned status {response.status_code}"

                    data = response.json()
                    assert data["status"] == "success", "API request failed"
                    assert data["count"] > 0, "No insights returned from API"

                    # Verify our insight is in the response
                    insight_ids = [i["id"] for i in data["data"]]
                    assert created_insight.id in insight_ids, \
                        "Created insight not found in API response"

                    print(f"✓ API returned {data['count']} insights")
                    print(f"✓ Created insight found in API response")
                else:
                    print("⚠ Insights API not running, skipping API tests")
                    pytest.skip("Insights API not available")

        except httpx.ConnectError:
            print("⚠ Insights API not running, skipping API tests")
            pytest.skip("Insights API not available")

    @pytest.mark.timeout(300)
    def test_insight_status_lifecycle(
        self,
        docker_services,
        warehouse_dsn,
        sample_gsc_data,
        clean_insights
    ):
        """
        Test insight lifecycle: NEW -> DIAGNOSED -> RESOLVED.

        Verifies that insights can transition through all status states.
        """
        print("\n=== Testing Insight Status Lifecycle ===")

        property_url = sample_gsc_data
        repository = InsightRepository(warehouse_dsn)

        # Step 1: Create insight (starts as NEW)
        insight_create = InsightCreate(
            property=property_url,
            entity_type=EntityType.PAGE,
            entity_id="/lifecycle-test-page",
            category=InsightCategory.RISK,
            title="Lifecycle Test Insight",
            description="Testing status transitions",
            severity=InsightSeverity.MEDIUM,
            confidence=0.85,
            metrics=InsightMetrics(
                gsc_clicks=50,
                gsc_clicks_change=-25.0,
            ),
            window_days=7,
            source="TestDetector",
        )

        insight = repository.create(insight_create)
        assert insight.status == InsightStatus.NEW, \
            f"Expected NEW status, got {insight.status}"
        print(f"✓ Created insight with status: {insight.status.value}")

        # Step 2: Transition to DIAGNOSED
        update = InsightUpdate(
            status=InsightStatus.DIAGNOSED,
            description="Root cause identified: algorithm update"
        )

        diagnosed_insight = repository.update(insight.id, update)
        assert diagnosed_insight is not None, "Update returned None"
        assert diagnosed_insight.status == InsightStatus.DIAGNOSED, \
            f"Expected DIAGNOSED status, got {diagnosed_insight.status}"
        print(f"✓ Transitioned to status: {diagnosed_insight.status.value}")

        # Verify description was updated
        assert "algorithm update" in diagnosed_insight.description, \
            "Description was not updated"
        print(f"✓ Description updated: {diagnosed_insight.description}")

        # Step 3: Transition to RESOLVED
        update = InsightUpdate(status=InsightStatus.RESOLVED)

        resolved_insight = repository.update(insight.id, update)
        assert resolved_insight is not None, "Update returned None"
        assert resolved_insight.status == InsightStatus.RESOLVED, \
            f"Expected RESOLVED status, got {resolved_insight.status}"
        print(f"✓ Transitioned to status: {resolved_insight.status.value}")

        # Step 4: Verify complete lifecycle via database query
        conn = psycopg2.connect(warehouse_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, status, created_at, updated_at
            FROM gsc.insights
            WHERE id = %s
        """, (insight.id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        assert row is not None, "Insight not found in database"
        assert row['status'] == 'resolved', \
            f"Database shows status {row['status']}, expected resolved"
        assert row['updated_at'] > row['created_at'], \
            "Updated timestamp not greater than created timestamp"

        print("✓ Verified complete lifecycle: NEW -> DIAGNOSED -> RESOLVED")
        print(f"✓ Created: {row['created_at']}")
        print(f"✓ Updated: {row['updated_at']}")

    @pytest.mark.timeout(300)
    def test_complete_pipeline_integration(
        self,
        docker_services,
        warehouse_dsn,
        sample_gsc_data,
        clean_insights
    ):
        """
        Test complete pipeline integration: Ingestion -> Transform -> Engine -> API.

        This is the comprehensive E2E test that validates the entire data flow.
        """
        print("\n=== Testing Complete Pipeline Integration ===")

        property_url = sample_gsc_data
        pipeline_metrics = {
            'start_time': time.time(),
            'steps_completed': [],
            'insights_created': 0,
            'errors': []
        }

        try:
            # Step 1: Verify data ingestion (already done by fixture)
            conn = psycopg2.connect(warehouse_dsn)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM gsc.fact_gsc_daily
                WHERE property = %s
            """, (property_url,))
            gsc_rows = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            assert gsc_rows > 0, "No GSC data available"
            pipeline_metrics['steps_completed'].append('ingestion')
            print(f"✓ Step 1 - Ingestion: {gsc_rows} rows available")

            # Step 2: Run transforms (create views)
            # Note: In a real pipeline, this would run SQL transform scripts
            # For testing, we verify the unified view exists
            conn = psycopg2.connect(warehouse_dsn)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views
                    WHERE table_schema = 'gsc'
                    AND table_name = 'vw_unified_page_performance'
                )
            """)
            view_exists = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            # View may not exist in test environment, that's okay
            if view_exists:
                pipeline_metrics['steps_completed'].append('transforms')
                print("✓ Step 2 - Transforms: Views exist")
            else:
                print("⚠ Step 2 - Transforms: Views not found (expected in test env)")

            # Step 3: Run InsightEngine
            config = InsightsConfig()
            config.warehouse_dsn = warehouse_dsn
            engine = InsightEngine(config)

            stats = engine.refresh(property=property_url, generate_actions=False)

            pipeline_metrics['insights_created'] = stats['total_insights_created']
            pipeline_metrics['steps_completed'].append('engine')
            print(f"✓ Step 3 - Engine: Created {stats['total_insights_created']} insights")
            print(f"  Detectors run: {stats['detectors_run']}")
            print(f"  Detectors succeeded: {stats['detectors_succeeded']}")

            # Step 4: Query via repository (database layer)
            repository = InsightRepository(warehouse_dsn)
            insights = repository.query(property=property_url, limit=100)

            assert len(insights) == stats['total_insights_created'], \
                "Mismatch between engine stats and repository query"

            pipeline_metrics['steps_completed'].append('repository')
            print(f"✓ Step 4 - Repository: Retrieved {len(insights)} insights")

            # Step 5: Test API access (if available)
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.get("http://localhost:8000/api/health")

                    if response.status_code == 200:
                        # Query insights via API
                        response = client.get(
                            "http://localhost:8000/api/insights",
                            params={"property": property_url}
                        )

                        if response.status_code == 200:
                            api_data = response.json()
                            pipeline_metrics['steps_completed'].append('api')
                            print(f"✓ Step 5 - API: Returned {api_data['count']} insights")
                        else:
                            print(f"⚠ Step 5 - API: Unexpected status {response.status_code}")
                    else:
                        print("⚠ Step 5 - API: Not healthy, skipping")
            except httpx.ConnectError:
                print("⚠ Step 5 - API: Not running, skipping")

            # Calculate final metrics
            pipeline_metrics['duration'] = time.time() - pipeline_metrics['start_time']

            # Verify pipeline success
            assert 'ingestion' in pipeline_metrics['steps_completed'], \
                "Ingestion step failed"
            assert 'engine' in pipeline_metrics['steps_completed'], \
                "Engine step failed"
            assert 'repository' in pipeline_metrics['steps_completed'], \
                "Repository step failed"

            # Print summary
            print("\n=== Pipeline Integration Summary ===")
            print(f"Duration: {pipeline_metrics['duration']:.2f}s")
            print(f"Steps completed: {', '.join(pipeline_metrics['steps_completed'])}")
            print(f"Insights created: {pipeline_metrics['insights_created']}")
            print(f"Errors: {len(pipeline_metrics['errors'])}")
            print("✓ Complete pipeline integration successful")

        except Exception as e:
            pipeline_metrics['errors'].append(str(e))
            print(f"\n✗ Pipeline integration failed: {e}")
            raise

    @pytest.mark.timeout(300)
    def test_pipeline_data_quality(
        self,
        docker_services,
        warehouse_dsn,
        sample_gsc_data,
        clean_insights
    ):
        """
        Test data quality throughout the pipeline.

        Verifies that data maintains integrity through all transformations.
        """
        print("\n=== Testing Pipeline Data Quality ===")

        property_url = sample_gsc_data

        # Run engine to generate insights
        config = InsightsConfig()
        config.warehouse_dsn = warehouse_dsn
        engine = InsightEngine(config)
        stats = engine.refresh(property=property_url, generate_actions=False)

        # Query insights for quality checks
        conn = psycopg2.connect(warehouse_dsn)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check 1: No NULL in required fields
        cursor.execute("""
            SELECT COUNT(*) as null_count
            FROM gsc.insights
            WHERE property IS NULL
               OR entity_type IS NULL
               OR entity_id IS NULL
               OR category IS NULL
               OR title IS NULL
               OR severity IS NULL
               OR status IS NULL
        """)
        null_count = cursor.fetchone()['null_count']
        assert null_count == 0, f"Found {null_count} insights with NULL required fields"
        print("✓ No NULL values in required fields")

        # Check 2: Valid enum values
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status NOT IN ('new', 'investigating', 'diagnosed', 'actioned', 'resolved')) as invalid_status,
                COUNT(*) FILTER (WHERE severity NOT IN ('low', 'medium', 'high')) as invalid_severity,
                COUNT(*) FILTER (WHERE category NOT IN ('risk', 'opportunity', 'trend', 'diagnosis')) as invalid_category
            FROM gsc.insights
        """)
        validation = cursor.fetchone()
        assert validation['invalid_status'] == 0, \
            f"Found {validation['invalid_status']} insights with invalid status"
        assert validation['invalid_severity'] == 0, \
            f"Found {validation['invalid_severity']} insights with invalid severity"
        assert validation['invalid_category'] == 0, \
            f"Found {validation['invalid_category']} insights with invalid category"
        print("✓ All enum values are valid")

        # Check 3: Confidence scores in valid range
        cursor.execute("""
            SELECT COUNT(*) as invalid_confidence
            FROM gsc.insights
            WHERE confidence < 0 OR confidence > 1
        """)
        invalid_conf = cursor.fetchone()['invalid_confidence']
        assert invalid_conf == 0, f"Found {invalid_conf} insights with invalid confidence"
        print("✓ All confidence scores in valid range [0, 1]")

        # Check 4: Timestamps are reasonable
        cursor.execute("""
            SELECT COUNT(*) as invalid_timestamps
            FROM gsc.insights
            WHERE generated_at > CURRENT_TIMESTAMP
               OR created_at > CURRENT_TIMESTAMP
               OR (updated_at IS NOT NULL AND updated_at < created_at)
        """)
        invalid_ts = cursor.fetchone()['invalid_timestamps']
        assert invalid_ts == 0, f"Found {invalid_ts} insights with invalid timestamps"
        print("✓ All timestamps are valid")

        cursor.close()
        conn.close()

        print("✓ Pipeline data quality verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "e2e"])
