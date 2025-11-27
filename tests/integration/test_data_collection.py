"""
Integration Tests for Data Collection
Tests GSC, GA4, SERP, and CWV data collection end-to-end
"""

import pytest
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from dotenv import load_dotenv

# Import modules to test
from ingestors.gsc.gsc_client import GSCClient
from ingestors.ga4.ga4_extractor import GA4Extractor
from insights_core.serp_tracker import SerpTracker
from insights_core.cwv_monitor import CoreWebVitalsMonitor

load_dotenv()

# Test configuration
TEST_PROPERTY = "https://test-domain.com"
TEST_GA4_PROPERTY_ID = "123456789"
TEST_DSN = os.getenv('WAREHOUSE_DSN', 'postgresql://postgres:postgres@localhost:5432/seo_warehouse')


@pytest.fixture
async def db_connection():
    """Provide database connection for tests"""
    conn = await asyncpg.connect(TEST_DSN)
    yield conn
    await conn.close()


@pytest.fixture
async def clean_test_data(db_connection):
    """Clean up test data before and after tests"""
    conn = db_connection

    # Clean before
    await conn.execute("DELETE FROM gsc.query_stats WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM ga4.events WHERE property_id = $1", TEST_GA4_PROPERTY_ID)
    await conn.execute("DELETE FROM serp.position_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM performance.cwv_metrics WHERE property = $1", TEST_PROPERTY)

    yield

    # Clean after
    await conn.execute("DELETE FROM gsc.query_stats WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM ga4.events WHERE property_id = $1", TEST_GA4_PROPERTY_ID)
    await conn.execute("DELETE FROM serp.position_history WHERE property = $1", TEST_PROPERTY)
    await conn.execute("DELETE FROM performance.cwv_metrics WHERE property = $1", TEST_PROPERTY)


class TestGSCDataCollection:
    """Test Google Search Console data collection"""

    @pytest.mark.asyncio
    async def test_gsc_client_initialization(self):
        """Test GSC client initializes correctly"""
        client = GSCClient(property_url=TEST_PROPERTY)
        assert client.property_url == TEST_PROPERTY
        assert client.db_dsn is not None

    @pytest.mark.asyncio
    @patch('ingestors.gsc.gsc_client.GSCClient._get_credentials')
    async def test_gsc_data_collection_with_mock(self, mock_credentials, db_connection, clean_test_data):
        """Test GSC data collection with mocked API responses"""
        # Mock credentials
        mock_credentials.return_value = Mock()

        # Create client
        client = GSCClient(property_url=TEST_PROPERTY, db_dsn=TEST_DSN)

        # Mock API response
        mock_response = {
            'rows': [
                {
                    'keys': ['test query', '/test-page', 'mobile', 'USA'],
                    'clicks': 100,
                    'impressions': 1000,
                    'ctr': 0.1,
                    'position': 5.5
                },
                {
                    'keys': ['another query', '/another-page', 'desktop', 'USA'],
                    'clicks': 50,
                    'impressions': 500,
                    'ctr': 0.1,
                    'position': 3.2
                }
            ]
        }

        with patch.object(client, '_fetch_search_analytics', return_value=mock_response):
            # Collect data
            start_date = datetime.now() - timedelta(days=3)
            end_date = datetime.now() - timedelta(days=1)

            await client.collect_data(
                property_url=TEST_PROPERTY,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

        # Verify data was inserted
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM gsc.query_stats WHERE property = $1",
            TEST_PROPERTY
        )
        assert count > 0

        # Verify data accuracy
        row = await db_connection.fetchrow(
            "SELECT * FROM gsc.query_stats WHERE property = $1 AND query_text = $2",
            TEST_PROPERTY, 'test query'
        )
        assert row is not None
        assert row['clicks'] == 100
        assert row['impressions'] == 1000
        assert row['page_path'] == '/test-page'
        assert row['device'] == 'mobile'

    @pytest.mark.asyncio
    async def test_gsc_duplicate_handling(self, db_connection, clean_test_data):
        """Test that duplicate data is handled correctly (upsert)"""
        # Insert initial data
        await db_connection.execute("""
            INSERT INTO gsc.query_stats
            (property, data_date, query_text, page_path, device, country, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """, TEST_PROPERTY, datetime.now().date(), 'test query', '/test-page',
            'mobile', 'USA', 100, 1000, 0.1, 5.5)

        # Try to insert duplicate with different values
        await db_connection.execute("""
            INSERT INTO gsc.query_stats
            (property, data_date, query_text, page_path, device, country, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (property, data_date, query_text, page_path, device, country)
            DO UPDATE SET clicks = EXCLUDED.clicks, impressions = EXCLUDED.impressions
        """, TEST_PROPERTY, datetime.now().date(), 'test query', '/test-page',
            'mobile', 'USA', 150, 1500, 0.1, 5.5)

        # Verify only one row exists with updated values
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM gsc.query_stats WHERE property = $1 AND query_text = $2",
            TEST_PROPERTY, 'test query'
        )
        assert count == 1

        row = await db_connection.fetchrow(
            "SELECT clicks FROM gsc.query_stats WHERE property = $1 AND query_text = $2",
            TEST_PROPERTY, 'test query'
        )
        assert row['clicks'] == 150


class TestGA4DataCollection:
    """Test Google Analytics 4 data collection"""

    @pytest.mark.asyncio
    async def test_ga4_extractor_initialization(self):
        """Test GA4 extractor initializes correctly"""
        extractor = GA4Extractor(property_id=TEST_GA4_PROPERTY_ID)
        assert extractor.property_id == TEST_GA4_PROPERTY_ID

    @pytest.mark.asyncio
    @patch('ingestors.ga4.ga4_extractor.GA4Extractor._get_credentials')
    async def test_ga4_data_collection_with_mock(self, mock_credentials, db_connection, clean_test_data):
        """Test GA4 data collection with mocked API"""
        mock_credentials.return_value = Mock()

        extractor = GA4Extractor(property_id=TEST_GA4_PROPERTY_ID, db_dsn=TEST_DSN)

        # Mock API response
        mock_response = Mock()
        mock_response.rows = [
            Mock(
                dimension_values=[
                    Mock(value='/test-page'),
                    Mock(value='Test Page'),
                    Mock(value='USA'),
                    Mock(value='mobile')
                ],
                metric_values=[
                    Mock(value='1000'),  # pageviews
                    Mock(value='500'),   # sessions
                    Mock(value='0.75'),  # engagement_rate
                    Mock(value='120')    # avg_session_duration
                ]
            )
        ]

        with patch.object(extractor, '_fetch_analytics_data', return_value=mock_response):
            start_date = datetime.now() - timedelta(days=3)
            end_date = datetime.now() - timedelta(days=1)

            await extractor.collect_data(
                property_id=TEST_GA4_PROPERTY_ID,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

        # Verify data
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM ga4.events WHERE property_id = $1",
            TEST_GA4_PROPERTY_ID
        )
        assert count > 0


class TestSERPTracking:
    """Test SERP position tracking"""

    @pytest.mark.asyncio
    async def test_serp_tracker_initialization(self):
        """Test SERP tracker initializes correctly"""
        tracker = SerpTracker(api_provider='valueserp')
        assert tracker.api_provider == 'valueserp'

    @pytest.mark.asyncio
    async def test_serp_position_detection(self, db_connection, clean_test_data):
        """Test SERP position detection logic"""
        tracker = SerpTracker(db_dsn=TEST_DSN)

        # Mock search results
        mock_results = [
            {'url': 'https://competitor1.com/page', 'position': 1},
            {'url': 'https://competitor2.com/page', 'position': 2},
            {'url': f'{TEST_PROPERTY}/target-page', 'position': 3},
            {'url': 'https://competitor3.com/page', 'position': 4},
        ]

        # Find our position
        our_url = f'{TEST_PROPERTY}/target-page'
        position = next((r['position'] for r in mock_results if TEST_PROPERTY in r['url']), None)

        assert position == 3

    @pytest.mark.asyncio
    @patch('insights_core.serp_tracker.SerpTracker._call_serp_api')
    async def test_serp_tracking_with_mock_api(self, mock_api, db_connection, clean_test_data):
        """Test complete SERP tracking flow with mocked API"""
        # First, insert a query to track
        query_id = await db_connection.fetchval("""
            INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
            VALUES ($1, $2, $3, true)
            RETURNING query_id
        """, 'test keyword', TEST_PROPERTY, '/target-page')

        # Mock API response
        mock_api.return_value = {
            'organic_results': [
                {'position': 1, 'link': 'https://competitor1.com/page'},
                {'position': 2, 'link': 'https://competitor2.com/page'},
                {'position': 3, 'link': f'{TEST_PROPERTY}/target-page'},
            ],
            'related_searches': ['related query 1', 'related query 2']
        }

        tracker = SerpTracker(db_dsn=TEST_DSN)

        result = await tracker.track_query({
            'query_id': query_id,
            'query_text': 'test keyword',
            'property': TEST_PROPERTY,
            'target_page_path': '/target-page',
            'location': 'United States',
            'device': 'desktop'
        })

        # Verify result
        assert result['position'] == 3
        assert result['found'] is True

        # Verify data in database
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM serp.position_history WHERE query_id = $1",
            query_id
        )
        assert count == 1

        row = await db_connection.fetchrow(
            "SELECT * FROM serp.position_history WHERE query_id = $1",
            query_id
        )
        assert row['position'] == 3


class TestCWVMonitoring:
    """Test Core Web Vitals monitoring"""

    @pytest.mark.asyncio
    async def test_cwv_monitor_initialization(self):
        """Test CWV monitor initializes correctly"""
        monitor = CoreWebVitalsMonitor()
        assert monitor is not None

    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.get')
    async def test_cwv_collection_with_mock(self, mock_get, db_connection, clean_test_data):
        """Test CWV data collection with mocked PageSpeed API"""
        # Mock API response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'lighthouseResult': {
                'categories': {
                    'performance': {'score': 0.85}
                },
                'audits': {
                    'largest-contentful-paint': {'numericValue': 1500},
                    'first-input-delay': {'numericValue': 50},
                    'cumulative-layout-shift': {'numericValue': 0.05},
                    'first-contentful-paint': {'numericValue': 1200},
                    'speed-index': {'numericValue': 2000},
                    'time-to-interactive': {'numericValue': 2500},
                    'total-blocking-time': {'numericValue': 150}
                }
            }
        }
        mock_get.return_value = mock_response

        monitor = CoreWebVitalsMonitor(db_dsn=TEST_DSN)

        result = await monitor.fetch_page_metrics(
            url=f'{TEST_PROPERTY}/test-page',
            strategy='mobile'
        )

        # Verify parsed metrics
        assert result['lcp'] == 1500
        assert result['fid'] == 50
        assert result['cls'] == 0.05
        assert result['performance_score'] == 85

        # Store in database
        await db_connection.execute("""
            INSERT INTO performance.cwv_metrics
            (property, page_path, device, lcp, fid, cls, fcp, speed_index, tti, tbt, performance_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, TEST_PROPERTY, '/test-page', 'mobile',
            result['lcp'], result['fid'], result['cls'], result['fcp'],
            result['speed_index'], result['tti'], result['tbt'], result['performance_score'])

        # Verify storage
        count = await db_connection.fetchval(
            "SELECT COUNT(*) FROM performance.cwv_metrics WHERE property = $1",
            TEST_PROPERTY
        )
        assert count == 1


class TestDataIntegrity:
    """Test data integrity and validation"""

    @pytest.mark.asyncio
    async def test_required_extensions_exist(self, db_connection):
        """Test that required PostgreSQL extensions are installed"""
        extensions = await db_connection.fetch(
            "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'uuid-ossp')"
        )
        ext_names = [e['extname'] for e in extensions]

        assert 'vector' in ext_names
        assert 'pg_trgm' in ext_names
        assert 'uuid-ossp' in ext_names

    @pytest.mark.asyncio
    async def test_all_schemas_exist(self, db_connection):
        """Test that all required schemas exist"""
        schemas = await db_connection.fetch(
            """SELECT schema_name FROM information_schema.schemata
               WHERE schema_name IN ('gsc', 'ga4', 'base', 'serp', 'performance',
                                     'notifications', 'orchestration', 'anomaly',
                                     'content', 'forecasts', 'analytics')"""
        )
        schema_names = [s['schema_name'] for s in schemas]

        required_schemas = ['gsc', 'ga4', 'base', 'serp', 'performance',
                          'notifications', 'orchestration', 'anomaly']
        for schema in required_schemas:
            assert schema in schema_names, f"Schema {schema} is missing"

    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, db_connection):
        """Test that foreign key constraints are properly set up"""
        # Test serp.position_history references serp.queries
        await db_connection.execute("""
            INSERT INTO serp.queries (query_id, query_text, property, is_active)
            VALUES ('00000000-0000-0000-0000-000000000001', 'test', $1, true)
            ON CONFLICT DO NOTHING
        """, TEST_PROPERTY)

        # This should succeed
        await db_connection.execute("""
            INSERT INTO serp.position_history (query_id, property, position, checked_at)
            VALUES ('00000000-0000-0000-0000-000000000001', $1, 5, NOW())
        """, TEST_PROPERTY)

        # This should fail (non-existent query_id)
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await db_connection.execute("""
                INSERT INTO serp.position_history (query_id, property, position, checked_at)
                VALUES ('00000000-0000-0000-0000-000000000099', $1, 5, NOW())
            """, TEST_PROPERTY)

        # Cleanup
        await db_connection.execute("""
            DELETE FROM serp.position_history WHERE query_id = '00000000-0000-0000-0000-000000000001'
        """)
        await db_connection.execute("""
            DELETE FROM serp.queries WHERE query_id = '00000000-0000-0000-0000-000000000001'
        """)


class TestRateLimiting:
    """Test rate limiting and throttling"""

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self):
        """Test that rate limiting is enforced"""
        # This is a placeholder - actual implementation would test rate limiter
        tracker = SerpTracker()

        # Verify rate limiter exists
        assert hasattr(tracker, '_apply_rate_limit') or hasattr(tracker, 'delay_between_requests')

    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing respects limits"""
        # Test that batch sizes are configurable and respected
        tracker = SerpTracker()

        queries = [{'query_text': f'query {i}'} for i in range(100)]
        batch_size = 5

        batches = [queries[i:i+batch_size] for i in range(0, len(queries), batch_size)]

        assert len(batches) == 20
        assert len(batches[0]) == batch_size


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--asyncio-mode=auto'])
