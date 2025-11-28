"""
Tests for URL Discovery Sync Module

Tests URL discovery from GSC/GA4 and sync to CWV monitored pages.

Run mock tests:
    pytest tests/insights_core/test_url_discovery_sync.py -v

Run live database tests:
    LIVE_DB_TESTS=1 pytest tests/insights_core/test_url_discovery_sync.py -v
"""
import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date, timedelta

from insights_core.url_discovery_sync import (
    URLDiscoverySync,
    SyncConfig,
    SyncResult,
    DiscoveredURL,
    sync_all_properties,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_dsn():
    """Mock database DSN"""
    return "postgresql://test:test@localhost:5432/testdb"


@pytest.fixture
def default_config():
    """Default sync configuration"""
    return SyncConfig(
        min_gsc_clicks=10,
        min_ga4_sessions=5,
        lookback_days=30,
        stale_threshold_days=90,
        check_mobile=True,
        check_desktop=False,
        max_new_urls_per_run=100,
    )


@pytest.fixture
def sync(mock_db_dsn, default_config):
    """Create URLDiscoverySync instance with mocked DB"""
    return URLDiscoverySync(db_dsn=mock_db_dsn, config=default_config)


@pytest.fixture
def sample_gsc_urls():
    """Sample URLs discovered from GSC"""
    return [
        DiscoveredURL(
            property='https://example.com/',
            page_path='/blog/article-1',
            source='gsc',
            clicks=150,
            avg_position=5.2,
            last_seen_at=datetime.now() - timedelta(days=1)
        ),
        DiscoveredURL(
            property='https://example.com/',
            page_path='/products/widget',
            source='gsc',
            clicks=80,
            avg_position=8.7,
            last_seen_at=datetime.now() - timedelta(days=2)
        ),
        DiscoveredURL(
            property='https://example.com/',
            page_path='/about',
            source='gsc',
            clicks=45,
            avg_position=12.3,
            last_seen_at=datetime.now() - timedelta(days=3)
        ),
    ]


@pytest.fixture
def sample_ga4_urls():
    """Sample URLs discovered from GA4"""
    return [
        DiscoveredURL(
            property='https://example.com/',
            page_path='/blog/article-1',  # Overlaps with GSC
            source='ga4',
            sessions=200,
            last_seen_at=datetime.now() - timedelta(days=1)
        ),
        DiscoveredURL(
            property='https://example.com/',
            page_path='/contact',  # GA4 only
            source='ga4',
            sessions=75,
            last_seen_at=datetime.now() - timedelta(days=2)
        ),
        DiscoveredURL(
            property='https://example.com/',
            page_path='/pricing',  # GA4 only
            source='ga4',
            sessions=120,
            last_seen_at=datetime.now() - timedelta(days=1)
        ),
    ]


@pytest.fixture
def sample_gsc_db_rows():
    """Sample rows from GSC fact table"""
    return [
        {
            'property': 'https://example.com/',
            'url': 'https://example.com/blog/article-1',
            'total_clicks': 150,
            'total_impressions': 5000,
            'avg_position': 5.2,
            'last_seen_date': date.today() - timedelta(days=1)
        },
        {
            'property': 'https://example.com/',
            'url': 'https://example.com/products/widget',
            'total_clicks': 80,
            'total_impressions': 3000,
            'avg_position': 8.7,
            'last_seen_date': date.today() - timedelta(days=2)
        },
    ]


@pytest.fixture
def sample_ga4_db_rows():
    """Sample rows from GA4 fact table"""
    return [
        {
            'property': 'https://example.com/',
            'page_path': '/blog/article-1',
            'total_sessions': 200,
            'total_page_views': 350,
            'last_seen_date': date.today() - timedelta(days=1)
        },
        {
            'property': 'https://example.com/',
            'page_path': '/contact',
            'total_sessions': 75,
            'total_page_views': 100,
            'last_seen_date': date.today() - timedelta(days=2)
        },
    ]


# ============================================================================
# Test Configuration
# ============================================================================

class TestSyncConfig:
    """Test SyncConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = SyncConfig()
        assert config.min_gsc_clicks == 10
        assert config.min_ga4_sessions == 5
        assert config.lookback_days == 30
        assert config.stale_threshold_days == 90
        assert config.check_mobile is True
        assert config.check_desktop is False
        assert config.max_new_urls_per_run == 100

    def test_from_dict(self):
        """Test creating config from dictionary"""
        config_dict = {
            'min_gsc_clicks': 20,
            'min_ga4_sessions': 10,
            'lookback_days': 60,
            'stale_threshold_days': 180,
            'check_mobile': True,
            'check_desktop': True,
            'max_new_urls_per_run': 50,
        }
        config = SyncConfig.from_dict(config_dict)
        assert config.min_gsc_clicks == 20
        assert config.min_ga4_sessions == 10
        assert config.lookback_days == 60
        assert config.stale_threshold_days == 180
        assert config.check_desktop is True
        assert config.max_new_urls_per_run == 50

    def test_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing keys"""
        config = SyncConfig.from_dict({})
        assert config.min_gsc_clicks == 10
        assert config.min_ga4_sessions == 5


# ============================================================================
# Test URL Normalization
# ============================================================================

class TestURLNormalization:
    """Test URL normalization methods"""

    def test_normalize_page_path_full_url(self, sync):
        """Test normalizing full URL to page path"""
        result = sync.normalize_page_path('https://example.com/blog/article')
        assert result == '/blog/article'

    def test_normalize_page_path_with_trailing_slash(self, sync):
        """Test trailing slash is removed"""
        result = sync.normalize_page_path('/blog/article/')
        assert result == '/blog/article'

    def test_normalize_page_path_root(self, sync):
        """Test root path keeps its slash"""
        result = sync.normalize_page_path('/')
        assert result == '/'

    def test_normalize_page_path_lowercase(self, sync):
        """Test path is lowercased"""
        result = sync.normalize_page_path('/Blog/ARTICLE')
        assert result == '/blog/article'

    def test_normalize_page_path_without_leading_slash(self, sync):
        """Test leading slash is added"""
        result = sync.normalize_page_path('blog/article')
        assert result == '/blog/article'

    def test_normalize_page_path_empty(self, sync):
        """Test empty path returns root"""
        result = sync.normalize_page_path('')
        assert result == '/'

    def test_normalize_property_adds_trailing_slash(self, sync):
        """Test property URL gets trailing slash"""
        result = sync.normalize_property('https://example.com')
        assert result == 'https://example.com/'

    def test_normalize_property_keeps_trailing_slash(self, sync):
        """Test property URL with trailing slash is preserved"""
        result = sync.normalize_property('https://example.com/')
        assert result == 'https://example.com/'


# ============================================================================
# Test URL Merging
# ============================================================================

class TestURLMerging:
    """Test merging URLs from GSC and GA4"""

    def test_merge_no_overlap(self, sync):
        """Test merging when there's no overlap"""
        gsc_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/gsc-only', source='gsc', clicks=100),
        ]
        ga4_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/ga4-only', source='ga4', sessions=50),
        ]

        merged = sync.merge_discovered_urls(gsc_urls, ga4_urls)

        assert len(merged) == 2
        sources = {u.source for u in merged}
        assert sources == {'gsc', 'ga4'}

    def test_merge_with_overlap(self, sync, sample_gsc_urls, sample_ga4_urls):
        """Test merging when URLs overlap"""
        merged = sync.merge_discovered_urls(sample_gsc_urls, sample_ga4_urls)

        # Should have GSC only (2) + GA4 only (2) + overlap (1) = 5 total
        assert len(merged) == 5

        # Check that overlapping URL has combined source
        overlap = next(u for u in merged if u.page_path == '/blog/article-1')
        assert overlap.source == 'gsc+ga4'
        assert overlap.clicks == 150  # From GSC
        assert overlap.sessions == 200  # From GA4

    def test_merge_preserves_most_recent_last_seen(self, sync):
        """Test that most recent last_seen_at is preserved"""
        older = datetime.now() - timedelta(days=5)
        newer = datetime.now() - timedelta(days=1)

        gsc_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='gsc',
                         clicks=100, last_seen_at=older),
        ]
        ga4_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='ga4',
                         sessions=50, last_seen_at=newer),
        ]

        merged = sync.merge_discovered_urls(gsc_urls, ga4_urls)
        assert merged[0].last_seen_at == newer


# ============================================================================
# Test Priority Scoring
# ============================================================================

class TestPriorityScoring:
    """Test priority score calculation"""

    def test_high_traffic_gets_high_score(self, sync):
        """Test that high traffic URLs get high priority scores"""
        high_traffic = DiscoveredURL(
            property='https://a.com/',
            page_path='/popular',
            source='gsc+ga4',
            clicks=5000,
            sessions=3000,
            avg_position=3.0,
            last_seen_at=datetime.now()
        )
        low_traffic = DiscoveredURL(
            property='https://a.com/',
            page_path='/unpopular',
            source='gsc',
            clicks=5,
            sessions=0,
            avg_position=50.0,
            last_seen_at=datetime.now() - timedelta(days=60)
        )

        high_score = sync.calculate_priority_score(high_traffic)
        low_score = sync.calculate_priority_score(low_traffic)

        assert high_score > low_score
        assert high_score > 0.5
        assert low_score < 0.3

    def test_score_is_bounded(self, sync):
        """Test that score is between 0 and 1"""
        url = DiscoveredURL(
            property='https://a.com/',
            page_path='/page',
            source='gsc',
            clicks=100000,  # Very high
            sessions=50000,
            avg_position=1.0,  # Best position
            last_seen_at=datetime.now()
        )
        score = sync.calculate_priority_score(url)
        assert 0 <= score <= 1

    def test_recent_activity_increases_score(self, sync):
        """Test that recent activity increases score"""
        recent = DiscoveredURL(
            property='https://a.com/',
            page_path='/recent',
            source='gsc',
            clicks=100,
            last_seen_at=datetime.now()
        )
        old = DiscoveredURL(
            property='https://a.com/',
            page_path='/old',
            source='gsc',
            clicks=100,
            last_seen_at=datetime.now() - timedelta(days=80)
        )

        recent_score = sync.calculate_priority_score(recent)
        old_score = sync.calculate_priority_score(old)

        assert recent_score > old_score


# ============================================================================
# Test GSC URL Discovery (Mocked)
# ============================================================================

class TestGSCDiscovery:
    """Test GSC URL discovery with mocked database"""

    @patch('psycopg2.connect')
    def test_discover_gsc_urls_success(self, mock_connect, sync, sample_gsc_db_rows):
        """Test successful GSC URL discovery"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = sample_gsc_db_rows

        urls = sync.discover_gsc_urls()

        assert len(urls) == 2
        assert all(u.source == 'gsc' for u in urls)
        assert urls[0].clicks == 150
        mock_cursor.execute.assert_called_once()

    @patch('psycopg2.connect')
    def test_discover_gsc_urls_with_property_filter(self, mock_connect, sync, sample_gsc_db_rows):
        """Test GSC discovery with property filter"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = sample_gsc_db_rows

        urls = sync.discover_gsc_urls(property='https://example.com/')

        # Verify property was included in query
        call_args = mock_cursor.execute.call_args
        assert 'https://example.com/' in call_args[0][1]

    @patch('psycopg2.connect')
    def test_discover_gsc_urls_empty_result(self, mock_connect, sync):
        """Test GSC discovery with no results"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = []

        urls = sync.discover_gsc_urls()

        assert len(urls) == 0


# ============================================================================
# Test GA4 URL Discovery (Mocked)
# ============================================================================

class TestGA4Discovery:
    """Test GA4 URL discovery with mocked database"""

    @patch('psycopg2.connect')
    def test_discover_ga4_urls_success(self, mock_connect, sync, sample_ga4_db_rows):
        """Test successful GA4 URL discovery"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = sample_ga4_db_rows

        urls = sync.discover_ga4_urls()

        assert len(urls) == 2
        assert all(u.source == 'ga4' for u in urls)
        assert urls[0].sessions == 200

    @patch('psycopg2.connect')
    def test_discover_ga4_urls_empty_result(self, mock_connect, sync):
        """Test GA4 discovery with no results"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchall.return_value = []

        urls = sync.discover_ga4_urls()

        assert len(urls) == 0


# ============================================================================
# Test Sync to Monitored Pages (Mocked)
# ============================================================================

class TestSyncToMonitoredPages:
    """Test syncing to monitored_pages table"""

    @patch('psycopg2.connect')
    def test_sync_new_urls(self, mock_connect, sync, sample_gsc_urls):
        """Test syncing new URLs"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Simulate no existing URLs
        mock_cursor.fetchone.return_value = None

        stats = sync.sync_to_monitored_pages(sample_gsc_urls, dry_run=False)

        assert stats['urls_new'] == 3
        assert stats['urls_updated'] == 0
        mock_conn.commit.assert_called_once()

    @patch('psycopg2.connect')
    def test_sync_existing_urls(self, mock_connect, sync, sample_gsc_urls):
        """Test syncing existing URLs (update)"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

        # Simulate existing URL
        mock_cursor.fetchone.return_value = {
            'page_id': 'uuid-123',
            'discovery_source': 'gsc',
            'total_clicks': 50,
            'total_sessions': 0
        }

        stats = sync.sync_to_monitored_pages(sample_gsc_urls, dry_run=False)

        assert stats['urls_updated'] == 3
        assert stats['urls_new'] == 0

    @patch('psycopg2.connect')
    def test_sync_dry_run_no_commit(self, mock_connect, sync, sample_gsc_urls):
        """Test dry run doesn't commit"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = None

        stats = sync.sync_to_monitored_pages(sample_gsc_urls, dry_run=True)

        mock_conn.commit.assert_not_called()
        mock_conn.rollback.assert_called_once()

    @patch('psycopg2.connect')
    def test_sync_respects_max_new_urls_limit(self, mock_connect, sync):
        """Test that max_new_urls_per_run is respected"""
        sync.config.max_new_urls_per_run = 2

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = None

        # Try to sync 5 URLs with limit of 2
        urls = [
            DiscoveredURL(property='https://a.com/', page_path=f'/page{i}', source='gsc', clicks=100)
            for i in range(5)
        ]

        stats = sync.sync_to_monitored_pages(urls, dry_run=False)

        assert stats['urls_new'] == 2
        assert stats['urls_skipped'] == 3

    def test_sync_empty_urls(self, sync):
        """Test syncing empty URL list"""
        stats = sync.sync_to_monitored_pages([], dry_run=False)

        assert stats['urls_processed'] == 0
        assert stats['urls_new'] == 0
        assert stats['urls_updated'] == 0


# ============================================================================
# Test Stale URL Deactivation (Mocked)
# ============================================================================

class TestStaleDeactivation:
    """Test deactivating stale URLs"""

    @patch('psycopg2.connect')
    def test_deactivate_stale_urls(self, mock_connect, sync):
        """Test deactivating stale URLs"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.rowcount = 5

        count = sync.deactivate_stale_urls(stale_days=90, dry_run=False)

        assert count == 5
        mock_conn.commit.assert_called_once()

    @patch('psycopg2.connect')
    def test_deactivate_stale_urls_dry_run(self, mock_connect, sync):
        """Test dry run counts but doesn't deactivate"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_cursor.fetchone.return_value = (3,)  # Count query result

        count = sync.deactivate_stale_urls(stale_days=90, dry_run=True)

        assert count == 3
        mock_conn.commit.assert_not_called()


# ============================================================================
# Test Full Sync (Mocked)
# ============================================================================

class TestFullSync:
    """Test full sync operation"""

    @patch.object(URLDiscoverySync, 'discover_gsc_urls')
    @patch.object(URLDiscoverySync, 'discover_ga4_urls')
    @patch.object(URLDiscoverySync, 'sync_to_monitored_pages')
    @patch.object(URLDiscoverySync, 'deactivate_stale_urls')
    def test_full_sync_success(
        self,
        mock_deactivate,
        mock_sync_pages,
        mock_ga4,
        mock_gsc,
        sync,
        sample_gsc_urls,
        sample_ga4_urls
    ):
        """Test full sync operation succeeds"""
        mock_gsc.return_value = sample_gsc_urls
        mock_ga4.return_value = sample_ga4_urls
        mock_sync_pages.return_value = {'urls_new': 3, 'urls_updated': 2, 'urls_skipped': 0}
        mock_deactivate.return_value = 1

        result = sync.sync(property='https://example.com/', dry_run=False)

        assert result.success is True
        assert result.urls_discovered == 5  # 3 GSC + 2 GA4 unique
        assert result.urls_new == 3
        assert result.urls_updated == 2
        assert result.urls_deactivated == 1
        assert result.error is None

    @patch.object(URLDiscoverySync, 'discover_gsc_urls')
    def test_sync_handles_gsc_error(self, mock_gsc, sync):
        """Test sync handles GSC discovery error"""
        mock_gsc.side_effect = Exception("Database connection failed")

        result = sync.sync(property='https://example.com/')

        assert result.success is False
        assert "Database connection failed" in result.error


# ============================================================================
# Test SyncResult
# ============================================================================

class TestSyncResult:
    """Test SyncResult dataclass"""

    def test_sync_result_defaults(self):
        """Test SyncResult default values"""
        result = SyncResult(success=True, property='https://a.com/')

        assert result.urls_discovered == 0
        assert result.urls_new == 0
        assert result.urls_updated == 0
        assert result.urls_deactivated == 0
        assert result.duration_seconds == 0.0
        assert result.error is None
        assert result.details == {}


# ============================================================================
# Test Convenience Function
# ============================================================================

class TestConvenienceFunction:
    """Test sync_all_properties convenience function"""

    @patch.object(URLDiscoverySync, 'sync_all_properties')
    @patch.object(URLDiscoverySync, 'close')
    def test_sync_all_properties_function(self, mock_close, mock_sync):
        """Test sync_all_properties convenience function"""
        mock_sync.return_value = [
            SyncResult(success=True, property='https://a.com/', urls_discovered=10)
        ]

        results = sync_all_properties(
            db_dsn='postgresql://test:test@localhost/test',
            config={'min_gsc_clicks': 20},
            dry_run=True
        )

        assert len(results) == 1
        mock_close.assert_called_once()


# ============================================================================
# Live Database Tests (Optional)
# ============================================================================

@pytest.mark.skipif(
    not os.environ.get('LIVE_DB_TESTS'),
    reason="Live database tests disabled. Set LIVE_DB_TESTS=1 to enable."
)
class TestLiveDatabase:
    """
    Live database integration tests.

    These tests require a real database connection and are skipped by default.
    Set LIVE_DB_TESTS=1 to enable them.
    """

    @pytest.fixture
    def live_sync(self):
        """Create sync with live database connection"""
        db_dsn = os.environ.get('WAREHOUSE_DSN')
        if not db_dsn:
            pytest.skip("WAREHOUSE_DSN not set")
        return URLDiscoverySync(db_dsn=db_dsn)

    def test_live_discover_gsc_urls(self, live_sync):
        """Test GSC URL discovery against real database"""
        urls = live_sync.discover_gsc_urls(min_clicks=1, lookback_days=7)

        # Should return list (may be empty if no data)
        assert isinstance(urls, list)
        for url in urls:
            assert url.source == 'gsc'
            assert url.property is not None
            assert url.page_path is not None

    def test_live_discover_ga4_urls(self, live_sync):
        """Test GA4 URL discovery against real database"""
        urls = live_sync.discover_ga4_urls(min_sessions=1, lookback_days=7)

        assert isinstance(urls, list)
        for url in urls:
            assert url.source == 'ga4'
            assert url.property is not None
            assert url.page_path is not None

    def test_live_full_sync_dry_run(self, live_sync):
        """Test full sync in dry-run mode against real database"""
        result = live_sync.sync(dry_run=True)

        assert result.success is True
        assert result.duration_seconds > 0
        # Dry run should not modify anything
        assert result.error is None

    def test_live_get_properties(self, live_sync):
        """Test getting properties from real database"""
        properties = live_sync.get_properties()

        assert isinstance(properties, list)
        # Properties should be strings
        for prop in properties:
            assert isinstance(prop, str)


# ============================================================================
# Regression Tests
# ============================================================================

class TestRegressionCases:
    """Test edge cases and regression scenarios"""

    def test_url_with_query_params_normalized(self, sync):
        """Test URLs with query params are normalized correctly"""
        result = sync.normalize_page_path('/page?utm_source=google&utm_medium=cpc')
        # Query params should be preserved in path for now
        assert result.startswith('/page')

    def test_url_with_fragment_preserved(self, sync):
        """Test URLs with fragments"""
        result = sync.normalize_page_path('/page#section')
        assert result == '/page#section'

    def test_property_with_port_number(self, sync):
        """Test property URL with port number"""
        result = sync.normalize_property('https://example.com:8080')
        assert result == 'https://example.com:8080/'

    def test_merge_handles_none_last_seen(self, sync):
        """Test merge handles None last_seen_at gracefully"""
        gsc_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='gsc',
                         clicks=100, last_seen_at=None),
        ]
        ga4_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='ga4',
                         sessions=50, last_seen_at=datetime.now()),
        ]

        merged = sync.merge_discovered_urls(gsc_urls, ga4_urls)
        assert len(merged) == 1
        assert merged[0].last_seen_at is not None

    def test_priority_score_with_none_values(self, sync):
        """Test priority calculation with None values"""
        url = DiscoveredURL(
            property='https://a.com/',
            page_path='/page',
            source='gsc',
            clicks=0,
            sessions=0,
            avg_position=None,
            last_seen_at=None
        )
        score = sync.calculate_priority_score(url)
        assert 0 <= score <= 1

    def test_discovery_source_upgrade_logic(self, sync):
        """Test that discovery_source is properly upgraded"""
        # Manual -> gsc should become gsc
        # gsc -> ga4 should become gsc+ga4
        # gsc+ga4 should stay gsc+ga4

        gsc_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='gsc', clicks=100),
        ]
        ga4_urls = [
            DiscoveredURL(property='https://a.com/', page_path='/page', source='ga4', sessions=50),
        ]

        merged = sync.merge_discovered_urls(gsc_urls, ga4_urls)
        assert merged[0].source == 'gsc+ga4'
