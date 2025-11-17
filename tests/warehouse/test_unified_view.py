"""
Tests for Unified Page Performance View
"""

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta
import os
import sys

# Add warehouse directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../warehouse'))

try:
    from refresh_views import ViewRefreshManager
except ImportError:
    ViewRefreshManager = None


@pytest.fixture(scope="module")
def db_connection():
    """Create database connection for tests"""
    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def db_cursor(db_connection):
    """Create database cursor for tests"""
    cursor = db_connection.cursor(cursor_factory=RealDictCursor)
    yield cursor
    cursor.close()


@pytest.fixture(scope="module")
def setup_test_data(db_cursor):
    """Setup test data in fact tables"""
    # Insert test GSC data
    test_date = date.today() - timedelta(days=1)
    
    gsc_data = [
        (test_date, 'https://example.com/', '/page1', 'test query 1', 'USA', 'DESKTOP', 100, 1000, 10.0, 5.5),
        (test_date, 'https://example.com/', '/page2', 'test query 2', 'USA', 'MOBILE', 50, 800, 6.25, 12.3),
        (test_date, 'https://example.com/', '/page3', 'test query 3', 'GBR', 'DESKTOP', 25, 500, 5.0, 8.7),
    ]
    
    for data in gsc_data:
        try:
            db_cursor.execute("""
                INSERT INTO gsc.fact_gsc_daily 
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date, property, url, query, country, device) DO NOTHING
            """, data)
        except Exception as e:
            print(f"Warning: Could not insert GSC test data: {e}")
    
    # Insert test GA4 data
    ga4_data = [
        (test_date, 'https://example.com/', '/page1', 150, 120, 0.8, 0.2, 10, 0.0667, 120.5, 180, 45.3, 30, 0.1667),
        (test_date, 'https://example.com/', '/page2', 100, 85, 0.85, 0.15, 8, 0.08, 95.2, 120, 38.1, 20, 0.1667),
        (test_date, 'https://example.com/', '/page3', 75, 60, 0.8, 0.25, 5, 0.0667, 110.3, 90, 42.7, 18, 0.2),
    ]
    
    for data in ga4_data:
        try:
            db_cursor.execute("""
                INSERT INTO gsc.fact_ga4_daily 
                (date, property, page_path, sessions, engaged_sessions, engagement_rate, 
                 bounce_rate, conversions, conversion_rate, avg_session_duration, 
                 page_views, avg_time_on_page, exits, exit_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date, property, page_path) DO NOTHING
            """, data)
        except Exception as e:
            print(f"Warning: Could not insert GA4 test data: {e}")
    
    yield
    
    # Cleanup is optional since we're using ON CONFLICT
    # In production, you might want to clean up test data


class TestUnifiedView:
    """Test cases for unified page performance view"""
    
    def test_view_exists(self, db_cursor):
        """Test that the unified view exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.views 
                WHERE table_schema = 'gsc' 
                AND table_name = 'vw_unified_page_performance'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "Unified view does not exist"
    
    def test_view_has_data(self, db_cursor, setup_test_data):
        """Test that the view returns data"""
        db_cursor.execute("""
            SELECT COUNT(*) as count 
            FROM gsc.vw_unified_page_performance
        """)
        result = db_cursor.fetchone()
        assert result['count'] > 0, "Unified view has no data"
    
    def test_view_recent_data(self, db_cursor, setup_test_data):
        """Test that the view has recent data"""
        db_cursor.execute("""
            SELECT COUNT(*) as count 
            FROM gsc.vw_unified_page_performance 
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        """)
        result = db_cursor.fetchone()
        assert result['count'] > 0, "No recent data in unified view"
    
    def test_view_columns(self, db_cursor):
        """Test that the view has all required columns"""
        required_columns = [
            'date', 'property', 'page_path',
            'clicks', 'impressions', 'ctr', 'avg_position',
            'sessions', 'engagement_rate', 'bounce_rate', 'conversions',
            'search_to_conversion_rate', 'session_conversion_rate',
            'performance_score', 'opportunity_index', 'conversion_efficiency',
            # Time-series columns
            'gsc_clicks_change_wow', 'gsc_impressions_change_wow',
            'gsc_position_change_wow', 'ga_conversions_change_wow',
            'ga_engagement_rate_change_wow',
            'gsc_clicks_7d_ago', 'gsc_impressions_7d_ago', 'ga_conversions_7d_ago',
            'gsc_clicks_7d_avg', 'gsc_impressions_7d_avg', 'ga_conversions_7d_avg'
        ]
        
        db_cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'gsc' 
            AND table_name = 'vw_unified_page_performance'
        """)
        
        columns = [row['column_name'] for row in db_cursor.fetchall()]
        
        for col in required_columns:
            assert col in columns, f"Required column '{col}' not found in view"
    
    def test_view_join_logic(self, db_cursor, setup_test_data):
        """Test that the view properly joins GSC and GA4 data"""
        test_date = date.today() - timedelta(days=1)
        
        db_cursor.execute("""
            SELECT 
                page_path,
                clicks,
                sessions,
                conversions
            FROM gsc.vw_unified_page_performance
            WHERE date = %s 
            AND property = 'https://example.com/'
            AND page_path IN ('/page1', '/page2', '/page3')
            ORDER BY page_path
        """, (test_date,))
        
        results = db_cursor.fetchall()
        assert len(results) > 0, "No joined data found"
        
        # Check that both GSC and GA4 metrics are present
        for row in results:
            assert row['clicks'] is not None and row['clicks'] >= 0
            assert row['sessions'] is not None and row['sessions'] >= 0
    
    def test_calculated_metrics(self, db_cursor, setup_test_data):
        """Test that calculated metrics are computed correctly"""
        test_date = date.today() - timedelta(days=1)
        
        db_cursor.execute("""
            SELECT 
                clicks,
                conversions,
                search_to_conversion_rate,
                sessions,
                session_conversion_rate,
                performance_score,
                opportunity_index
            FROM gsc.vw_unified_page_performance
            WHERE date = %s 
            AND property = 'https://example.com/'
            AND page_path = '/page1'
        """, (test_date,))
        
        result = db_cursor.fetchone()
        
        if result and result['clicks'] > 0:
            # Test search_to_conversion_rate
            expected_rate = round((result['conversions'] / result['clicks']) * 100, 2)
            assert abs(result['search_to_conversion_rate'] - expected_rate) < 0.1
            
            # Test that performance_score is in valid range
            assert 0 <= result['performance_score'] <= 1
    
    def test_null_handling(self, db_cursor):
        """Test that the view handles NULL values correctly"""
        db_cursor.execute("""
            SELECT COUNT(*) as count
            FROM gsc.vw_unified_page_performance
            WHERE date IS NULL 
            OR property IS NULL 
            OR page_path IS NULL
        """)
        result = db_cursor.fetchone()
        assert result['count'] == 0, "View contains rows with NULL keys"
    
    def test_ctr_range(self, db_cursor):
        """Test that CTR values are in valid range"""
        db_cursor.execute("""
            SELECT COUNT(*) as count
            FROM gsc.vw_unified_page_performance
            WHERE ctr < 0 OR ctr > 100
        """)
        result = db_cursor.fetchone()
        assert result['count'] == 0, "View contains invalid CTR values"
    
    def test_performance_score_range(self, db_cursor):
        """Test that performance_score is in valid range"""
        db_cursor.execute("""
            SELECT COUNT(*) as count
            FROM gsc.vw_unified_page_performance
            WHERE performance_score < 0 OR performance_score > 1
        """)
        result = db_cursor.fetchone()
        assert result['count'] == 0, "View contains invalid performance_score values"


class TestMaterializedViews:
    """Test cases for materialized views"""
    
    def test_mv_daily_exists(self, db_cursor):
        """Test that daily materialized view exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'gsc' 
                AND matviewname = 'mv_unified_page_performance'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "Daily materialized view does not exist"
    
    def test_mv_weekly_exists(self, db_cursor):
        """Test that weekly materialized view exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'gsc' 
                AND matviewname = 'mv_unified_page_performance_weekly'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "Weekly materialized view does not exist"
    
    def test_mv_monthly_exists(self, db_cursor):
        """Test that monthly materialized view exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_matviews 
                WHERE schemaname = 'gsc' 
                AND matviewname = 'mv_unified_page_performance_monthly'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "Monthly materialized view does not exist"
    
    def test_mv_has_indexes(self, db_cursor):
        """Test that materialized view has proper indexes"""
        db_cursor.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'gsc' 
            AND tablename = 'mv_unified_page_performance'
        """)
        indexes = [row['indexname'] for row in db_cursor.fetchall()]
        assert len(indexes) > 0, "Materialized view has no indexes"
    
    def test_mv_refresh_function_exists(self, db_cursor):
        """Test that refresh functions exist"""
        functions = [
            'refresh_mv_unified_daily',
            'refresh_mv_unified_weekly',
            'refresh_mv_unified_monthly',
            'refresh_all_unified_views'
        ]
        
        for func in functions:
            db_cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'gsc' AND p.proname = %s
                )
            """, (func,))
            result = db_cursor.fetchone()
            assert result['exists'], f"Function {func} does not exist"


class TestDataQuality:
    """Test cases for data quality validation"""
    
    def test_validation_function_exists(self, db_cursor):
        """Test that validation function exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'gsc' 
                AND p.proname = 'validate_unified_view_quality'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "Validation function does not exist"
    
    def test_run_validation(self, db_cursor):
        """Test running validation checks"""
        try:
            db_cursor.execute("SELECT * FROM gsc.validate_unified_view_quality()")
            checks = db_cursor.fetchall()
            assert len(checks) > 0, "No validation checks returned"
            
            # Verify check structure
            for check in checks:
                assert 'check_name' in check
                assert 'check_status' in check
                assert 'check_value' in check
                assert 'check_message' in check
        except Exception as e:
            pytest.fail(f"Validation function failed: {e}")


class TestRefreshManager:
    """Test cases for ViewRefreshManager"""
    
    @pytest.fixture
    def manager(self):
        """Create refresh manager instance"""
        if ViewRefreshManager is None:
            pytest.skip("ViewRefreshManager not available")
        
        dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
        manager = ViewRefreshManager(dsn=dsn)
        manager.connect()
        yield manager
        manager.close()
    
    def test_manager_initialization(self, manager):
        """Test that manager initializes correctly"""
        assert manager is not None
        assert manager.conn is not None
        assert manager.cursor is not None
    
    def test_get_view_stats(self, manager):
        """Test getting view statistics"""
        stats = manager.get_view_stats()
        assert isinstance(stats, dict)
        assert len(stats) > 0
    
    def test_validate_view_quality(self, manager):
        """Test validation through manager"""
        checks = manager.validate_view_quality()
        assert isinstance(checks, list)
        assert len(checks) > 0
    
    def test_available_views(self, manager):
        """Test that all views are available"""
        for view_name in manager.AVAILABLE_VIEWS.keys():
            assert view_name in ['unified_page_performance', 'unified_weekly', 'unified_monthly']


class TestPerformance:
    """Performance tests for unified view"""
    
    def test_view_query_performance(self, db_cursor):
        """Test that view queries execute in reasonable time"""
        import time
        
        start = time.time()
        db_cursor.execute("""
            SELECT COUNT(*) 
            FROM gsc.vw_unified_page_performance 
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
        """)
        duration = time.time() - start
        
        # Query should complete in less than 5 seconds
        assert duration < 5.0, f"View query too slow: {duration:.2f}s"
    
    def test_mv_query_performance(self, db_cursor):
        """Test that materialized view queries are fast"""
        import time
        
        try:
            start = time.time()
            db_cursor.execute("""
                SELECT COUNT(*) 
                FROM gsc.mv_unified_page_performance 
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            duration = time.time() - start
            
            # Materialized view should be even faster
            assert duration < 2.0, f"Materialized view query too slow: {duration:.2f}s"
        except Exception as e:
            pytest.skip(f"Materialized view not populated: {e}")




class TestTimeSeriesCalculations:
    """Test cases for time-series WoW/MoM calculations"""
    
    def test_time_series_validation_function_exists(self, db_cursor):
        """Test that time-series validation function exists"""
        db_cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'gsc' 
                AND p.proname = 'validate_unified_view_time_series'
            )
        """)
        result = db_cursor.fetchone()
        assert result['exists'], "validate_unified_view_time_series() function does not exist"
    
    def test_time_series_validation_passes(self, db_cursor):
        """Test running time-series validation checks"""
        db_cursor.execute("SELECT * FROM gsc.validate_unified_view_time_series()")
        results = db_cursor.fetchall()
        
        assert len(results) > 0, "Validation should return results"
        
        # Check for critical failures
        for row in results:
            if row['check_status'] == 'FAIL':
                # Historical depth FAIL is OK if we don't have 30 days yet
                if row['check_name'] == 'historical_depth':
                    days = int(row['check_value'])
                    if days >= 7:  # As long as we have 7+ days, WoW will work
                        continue
                pytest.fail(f"Validation check failed: {row['check_name']} - {row['check_message']}")
    
    def test_wow_calculation_accuracy(self, db_connection):
        """Test WoW percentage calculation is correct"""
        cur = db_connection.cursor()
        
        # Clean up test data
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-calculation'")
        db_connection.commit()
        
        # Insert data: day 1 = 100 clicks, day 8 = 150 clicks
        # Expected WoW: ((150 - 100) / 100) * 100 = 50%
        today = date.today()
        
        cur.execute("""
            INSERT INTO gsc.fact_gsc_daily 
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES 
            (%s, 'test://wow-calculation', '/test-page', 'test query', 'usa', 'DESKTOP', 100, 1000, 10.0, 5.0),
            (%s, 'test://wow-calculation', '/test-page', 'test query', 'usa', 'DESKTOP', 150, 1500, 10.0, 5.0)
        """, (today - timedelta(days=7), today))
        db_connection.commit()
        
        # Query unified view
        cur.execute("""
            SELECT 
                date,
                gsc_clicks,
                gsc_clicks_7d_ago,
                gsc_clicks_change_wow
            FROM gsc.vw_unified_page_performance
            WHERE property = 'test://wow-calculation'
            AND page_path = '/test-page'
            ORDER BY date DESC
            LIMIT 1
        """)
        
        result = cur.fetchone()
        
        if result:
            date_val, clicks, clicks_7d_ago, wow_change = result
            assert clicks == 150, f"Current clicks should be 150, got {clicks}"
            assert clicks_7d_ago == 100, f"7d ago clicks should be 100, got {clicks_7d_ago}"
            assert wow_change == 50.0, f"WoW change should be 50%, got {wow_change}"
        
        # Cleanup
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-calculation'")
        db_connection.commit()
        cur.close()
    
    def test_wow_null_handling(self, db_connection):
        """Test WoW returns NULL when no historical data"""
        cur = db_connection.cursor()
        
        # Clean up test data
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-null'")
        db_connection.commit()
        
        # Insert data for only 1 day (no 7d ago data)
        today = date.today()
        cur.execute("""
            INSERT INTO gsc.fact_gsc_daily 
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES 
            (%s, 'test://wow-null', '/test-page', 'test query', 'usa', 'DESKTOP', 100, 1000, 10.0, 5.0)
        """, (today,))
        db_connection.commit()
        
        # Query unified view
        cur.execute("""
            SELECT gsc_clicks_change_wow
            FROM gsc.vw_unified_page_performance
            WHERE property = 'test://wow-null'
            AND page_path = '/test-page'
            AND date = %s
        """, (today,))
        
        result = cur.fetchone()
        if result:
            wow_change = result[0]
            assert wow_change is None, f"WoW should be NULL when no 7d ago data, got {wow_change}"
        
        # Cleanup
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-null'")
        db_connection.commit()
        cur.close()
    
    def test_wow_divide_by_zero_handling(self, db_connection):
        """Test WoW handles zero 7d ago value correctly"""
        cur = db_connection.cursor()
        
        # Clean up test data
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-zero'")
        db_connection.commit()
        
        # Insert data: day 1 = 0 clicks, day 8 = 100 clicks
        # Should return 100% (or handle gracefully, not crash)
        today = date.today()
        
        cur.execute("""
            INSERT INTO gsc.fact_gsc_daily 
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES 
            (%s, 'test://wow-zero', '/test-page', 'test query', 'usa', 'DESKTOP', 0, 1000, 0.0, 5.0),
            (%s, 'test://wow-zero', '/test-page', 'test query', 'usa', 'DESKTOP', 100, 1500, 6.67, 5.0)
        """, (today - timedelta(days=7), today))
        db_connection.commit()
        
        # Query should not crash
        cur.execute("""
            SELECT gsc_clicks_change_wow
            FROM gsc.vw_unified_page_performance
            WHERE property = 'test://wow-zero'
            AND page_path = '/test-page'
            AND date = %s
        """, (today,))
        
        result = cur.fetchone()
        if result:
            wow_change = result[0]
            # Should be 100.0 (special case) or NULL, not a division error
            assert wow_change == 100.0 or wow_change is None, \
                f"WoW with zero 7d ago should be 100% or NULL, got {wow_change}"
        
        # Cleanup
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://wow-zero'")
        db_connection.commit()
        cur.close()
    
    def test_rolling_average_calculation(self, db_connection):
        """Test 7-day rolling average is correct"""
        cur = db_connection.cursor()
        
        # Clean up test data
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://rolling-avg'")
        db_connection.commit()
        
        # Insert 7 days of data: 10, 20, 30, 40, 50, 60, 70
        # 7-day avg on day 7 should be (10+20+30+40+50+60+70)/7 = 40
        today = date.today()
        clicks_values = [10, 20, 30, 40, 50, 60, 70]
        
        for i, clicks in enumerate(clicks_values):
            cur.execute("""
                INSERT INTO gsc.fact_gsc_daily 
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES 
                (%s, 'test://rolling-avg', '/test-page', 'test query', 'usa', 'DESKTOP', %s, 1000, 10.0, 5.0)
            """, (today - timedelta(days=6-i), clicks))
        db_connection.commit()
        
        # Query unified view for latest date
        cur.execute("""
            SELECT gsc_clicks_7d_avg
            FROM gsc.vw_unified_page_performance
            WHERE property = 'test://rolling-avg'
            AND page_path = '/test-page'
            AND date = %s
        """, (today,))
        
        result = cur.fetchone()
        if result:
            avg_7d = result[0]
            expected_avg = sum(clicks_values) / len(clicks_values)
            assert abs(avg_7d - expected_avg) < 0.1, \
                f"7-day avg should be ~{expected_avg}, got {avg_7d}"
        
        # Cleanup
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property = 'test://rolling-avg'")
        db_connection.commit()
        cur.close()
    
    def test_detector_can_query_view(self, db_cursor):
        """Test that AnomalyDetector query works"""
        # This is the actual query from AnomalyDetector
        db_cursor.execute("""
            SELECT DISTINCT ON (property, page_path)
                property,
                page_path,
                date,
                gsc_clicks,
                gsc_clicks_change_wow,
                gsc_impressions,
                gsc_impressions_change_wow,
                ga_conversions,
                ga_conversions_change_wow
            FROM gsc.vw_unified_page_performance
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            AND (
                gsc_clicks_change_wow < -20
                OR gsc_impressions_change_wow > 50
                OR ga_conversions_change_wow < -20
            )
            ORDER BY property, page_path, date DESC
            LIMIT 10
        """)
        
        # Should execute without error (result count doesn't matter)
        results = db_cursor.fetchall()
        assert results is not None, "Detector query should execute successfully"
    
    def test_materialized_view_compatible(self, db_cursor):
        """Test that materialized view includes new fields"""
        # Check if MV exists and has time-series columns
        db_cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'gsc' 
            AND table_name = 'mv_unified_page_performance'
            AND column_name IN ('gsc_clicks_change_wow', 'ga_conversions_change_wow')
            ORDER BY column_name
        """)
        columns = [row['column_name'] for row in db_cursor.fetchall()]
        
        # MV should exist with these columns (if it's been created)
        if len(columns) > 0:
            assert 'gsc_clicks_change_wow' in columns, "MV should include gsc_clicks_change_wow"
            assert 'ga_conversions_change_wow' in columns, "MV should include ga_conversions_change_wow"
    
    def test_helper_views_exist(self, db_cursor):
        """Test that helper views are created"""
        helper_views = ['vw_unified_page_performance_latest', 'vw_unified_anomalies']
        
        for view_name in helper_views:
            db_cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_schema = 'gsc' 
                    AND table_name = %s
                )
            """, (view_name,))
            result = db_cursor.fetchone()
            assert result['exists'], f"Helper view {view_name} does not exist"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
