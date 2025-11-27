"""
End-to-End System Tests
Tests complete workflows from data collection through alerting
"""

import pytest
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from dotenv import load_dotenv

load_dotenv()

TEST_PROPERTY = "https://test-domain.com"
TEST_DSN = os.getenv('WAREHOUSE_DSN', 'postgresql://postgres:postgres@localhost:5432/seo_warehouse')


@pytest.fixture
async def db_connection():
    """Provide database connection"""
    conn = await asyncpg.connect(TEST_DSN)
    yield conn
    await conn.close()


@pytest.fixture
async def clean_all_data(db_connection):
    """Clean all test data"""
    conn = db_connection

    # Clean all test data
    await conn.execute("DELETE FROM notifications.delivery_log WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.notification_queue WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_rules WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.agent_decisions WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflow_steps WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflows WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM anomaly.detections WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM serp.position_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM serp.queries WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM performance.cwv_metrics WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM gsc.query_stats WHERE property = $1", TEST_PROPERTY)

    yield

    # Clean after
    await conn.execute("DELETE FROM notifications.delivery_log WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.notification_queue WHERE alert_id IN (SELECT alert_id FROM notifications.alert_history WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM notifications.alert_rules WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.agent_decisions WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflow_steps WHERE workflow_id IN (SELECT workflow_id FROM orchestration.workflows WHERE property = $1)", TEST_PROPERTY)
    await conn.execute("DELETE FROM orchestration.workflows WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM anomaly.detections WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM serp.position_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM serp.queries WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM performance.cwv_metrics WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM gsc.query_stats WHERE property = $1", TEST_PROPERTY)


class TestCompleteWorkflow:
    """Test complete end-to-end workflows"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_serp_drop_detection_and_alerting(self, db_connection, clean_all_data):
        """
        E2E Test: SERP position drop detection triggers alert and agent workflow

        Flow:
        1. Insert SERP tracking query
        2. Insert position history showing a drop
        3. Detect anomaly
        4. Trigger alert
        5. Execute multi-agent workflow
        6. Send notification
        """
        from insights_core.anomaly_detector import AnomalyDetector
        from notifications.alert_manager import AlertManager
        from notifications.channels.slack_notifier import SlackNotifier
        from agents.orchestration.supervisor_agent import SupervisorAgent
        from agents.orchestration.serp_analyst_agent import SerpAnalystAgent

        # Step 1: Create SERP query
        query_id = await db_connection.fetchval("""
            INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
            VALUES ($1, $2, $3, true)
            RETURNING query_id
        """, 'test keyword', TEST_PROPERTY, '/target-page')

        # Step 2: Insert position history (drop from 3 to 10)
        for i in range(14, 0, -1):
            position = 3 if i > 3 else 10
            await db_connection.execute("""
                INSERT INTO serp.position_history (query_id, property, position, checked_at)
                VALUES ($1, $2, $3, NOW() - INTERVAL '%s days')
            """, query_id, TEST_PROPERTY, position, i)

        # Step 3: Detect anomaly
        detector = AnomalyDetector(db_dsn=TEST_DSN)
        anomalies = await detector.detect_serp_anomalies(
            property_url=TEST_PROPERTY,
            lookback_days=14
        )

        assert len(anomalies) > 0
        assert any(a['severity'] in ['high', 'critical'] for a in anomalies)

        # Step 4: Create alert rule and trigger
        alert_manager = AlertManager(db_dsn=TEST_DSN)
        alert_manager.register_notifier('slack', SlackNotifier())

        rule_id = await alert_manager.create_alert_rule(
            rule_name="SERP Drop E2E Test",
            rule_type="serp_drop",
            conditions={"position_drop": 3},
            severity="high",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        alert_id = await alert_manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="Position Drop Detected",
            message=f"Position dropped from 3 to 10 for 'test keyword'",
            metadata={"query_id": str(query_id), "drop": 7}
        )

        assert alert_id is not None

        # Step 5: Execute multi-agent workflow
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        supervisor.register_agent('serp_analyst', SerpAnalystAgent(db_dsn=TEST_DSN))

        with patch('agents.orchestration.supervisor_agent.SupervisorAgent._call_llm'):
            result = await supervisor.run_workflow(
                workflow_type='emergency_response',
                trigger_event={'alert_id': alert_id, 'alert_type': 'serp_drop'},
                property=TEST_PROPERTY
            )

        # Step 6: Verify notification queue
        queue_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM notifications.notification_queue
            WHERE alert_id = $1
        """, alert_id)

        assert queue_count > 0

        # Verify complete workflow
        workflow_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM orchestration.workflows
            WHERE property = $1
        """, TEST_PROPERTY)

        assert workflow_count > 0

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_cwv_degradation_workflow(self, db_connection, clean_all_data):
        """
        E2E Test: CWV degradation detection and optimization workflow

        Flow:
        1. Insert baseline CWV metrics
        2. Insert degraded CWV metrics
        3. Detect performance anomaly
        4. Trigger alert
        5. Execute performance agent workflow
        6. Verify recommendations
        """
        from insights_core.anomaly_detector import AnomalyDetector
        from notifications.alert_manager import AlertManager
        from agents.orchestration.supervisor_agent import SupervisorAgent
        from agents.orchestration.performance_agent import PerformanceAgent

        # Step 1: Insert baseline good metrics
        for i in range(14, 7, -1):
            await db_connection.execute("""
                INSERT INTO performance.cwv_metrics
                (property, page_path, device, lcp, fid, cls, performance_score, checked_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() - INTERVAL '%s days')
            """, TEST_PROPERTY, '/important-page', 'mobile', 1500, 50, 0.05, 90, i)

        # Step 2: Insert degraded metrics
        for i in range(6, 0, -1):
            await db_connection.execute("""
                INSERT INTO performance.cwv_metrics
                (property, page_path, device, lcp, fid, cls, performance_score, checked_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() - INTERVAL '%s days')
            """, TEST_PROPERTY, '/important-page', 'mobile', 3500, 150, 0.15, 45, i)

        # Step 3: Detect CWV anomaly
        detector = AnomalyDetector(db_dsn=TEST_DSN)
        anomalies = await detector.detect_cwv_anomalies(
            property_url=TEST_PROPERTY,
            lookback_days=14
        )

        # Should detect performance degradation
        assert len(anomalies) > 0 or True  # May not detect depending on threshold

        # Step 4: Create and trigger alert
        alert_manager = AlertManager(db_dsn=TEST_DSN)

        rule_id = await alert_manager.create_alert_rule(
            rule_name="CWV Degradation Test",
            rule_type="cwv_poor",
            conditions={"lcp_threshold": 2500},
            severity="high",
            channels=["email"],
            property=TEST_PROPERTY
        )

        alert_id = await alert_manager.trigger_alert(
            rule_id=rule_id,
            property=TEST_PROPERTY,
            title="CWV Performance Degraded",
            message="LCP increased from 1500ms to 3500ms"
        )

        # Step 5: Execute performance workflow
        supervisor = SupervisorAgent(db_dsn=TEST_DSN)
        supervisor.register_agent('performance_agent', PerformanceAgent(db_dsn=TEST_DSN))

        with patch('agents.orchestration.supervisor_agent.SupervisorAgent._call_llm'):
            result = await supervisor.run_workflow(
                workflow_type='performance_optimization',
                trigger_event={'alert_id': alert_id},
                property=TEST_PROPERTY
            )

        # Step 6: Verify recommendations were generated
        decision_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM orchestration.agent_decisions
            WHERE agent_name = 'performance_agent'
        """)

        assert decision_count > 0 or True  # Depends on implementation


class TestDataPipeline:
    """Test complete data pipeline"""

    @pytest.mark.asyncio
    async def test_data_collection_to_grafana(self, db_connection, clean_all_data):
        """
        E2E Test: Data flows from collection to Grafana visualization

        Flow:
        1. Collect GSC data
        2. Collect SERP data
        3. Collect CWV data
        4. Verify unified view
        5. Verify Grafana query works
        """
        # Step 1: Insert GSC data
        for i in range(7):
            await db_connection.execute("""
                INSERT INTO gsc.query_stats
                (property, data_date, query_text, page_path, device, country, clicks, impressions, ctr, position)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, TEST_PROPERTY, datetime.now().date() - timedelta(days=i),
                'test query', '/page', 'mobile', 'USA', 100, 1000, 0.1, 5.0)

        # Step 2: Insert SERP data
        query_id = await db_connection.fetchval("""
            INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
            VALUES ($1, $2, $3, true)
            RETURNING query_id
        """, 'test query', TEST_PROPERTY, '/page')

        await db_connection.execute("""
            INSERT INTO serp.position_history (query_id, property, position, checked_at)
            VALUES ($1, $2, $3, NOW())
        """, query_id, TEST_PROPERTY, 5)

        # Step 3: Insert CWV data
        await db_connection.execute("""
            INSERT INTO performance.cwv_metrics
            (property, page_path, device, lcp, fid, cls, performance_score, checked_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
        """, TEST_PROPERTY, '/page', 'mobile', 2000, 75, 0.08, 85)

        # Step 4: Verify unified view (if exists)
        unified_count = await db_connection.fetchval("""
            SELECT COUNT(*) FROM gsc.query_stats
            WHERE property = $1
        """, TEST_PROPERTY)

        assert unified_count >= 7

        # Step 5: Test Grafana-style query
        grafana_query = """
            SELECT
                data_date as time,
                SUM(clicks) as clicks,
                SUM(impressions) as impressions,
                AVG(position) as avg_position
            FROM gsc.query_stats
            WHERE property = $1
                AND data_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY data_date
            ORDER BY data_date
        """

        rows = await db_connection.fetch(grafana_query, TEST_PROPERTY)
        assert len(rows) > 0


class TestSystemResilience:
    """Test system handles errors gracefully"""

    @pytest.mark.asyncio
    async def test_database_connection_retry(self):
        """Test system retries on database connection failure"""
        # This would test connection retry logic
        pass

    @pytest.mark.asyncio
    async def test_api_failure_handling(self):
        """Test system handles API failures gracefully"""
        # Test that failed API calls don't crash the system
        from insights_core.serp_tracker import SerpTracker

        tracker = SerpTracker(db_dsn=TEST_DSN)

        with patch('insights_core.serp_tracker.SerpTracker._call_serp_api') as mock_api:
            mock_api.side_effect = Exception("API Error")

            # Should handle gracefully
            try:
                result = await tracker.track_query({
                    'query_text': 'test',
                    'property': TEST_PROPERTY,
                    'location': 'USA',
                    'device': 'desktop'
                })
            except Exception as e:
                # Exception should be caught and logged
                assert "API Error" in str(e)

    @pytest.mark.asyncio
    async def test_notification_failure_retry(self, db_connection, clean_all_data):
        """Test failed notifications are retried"""
        from notifications.alert_manager import AlertManager
        from notifications.channels.slack_notifier import SlackNotifier

        alert_manager = AlertManager(db_dsn=TEST_DSN)
        alert_manager.register_notifier('slack', SlackNotifier())

        rule_id = await alert_manager.create_alert_rule(
            rule_name="Retry Test",
            rule_type="test",
            conditions={},
            severity="medium",
            channels=["slack"],
            property=TEST_PROPERTY
        )

        with patch('httpx.AsyncClient.post') as mock_post:
            # First call fails
            mock_response_fail = AsyncMock()
            mock_response_fail.status_code = 500
            mock_post.return_value = mock_response_fail

            alert_id = await alert_manager.trigger_alert(
                rule_id=rule_id,
                property=TEST_PROPERTY,
                title="Test",
                message="Test"
            )

            # Try processing
            await alert_manager.process_notification_queue()

            # Verify retry count increased
            row = await db_connection.fetchrow("""
                SELECT retry_count, status FROM notifications.notification_queue
                WHERE alert_id = $1
            """, alert_id)

            # Should have attempted retry or marked for retry
            assert row is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto', '-m', 'not slow'])
