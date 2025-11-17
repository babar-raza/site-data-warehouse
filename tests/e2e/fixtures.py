#!/usr/bin/env python3
"""
E2E Test Fixtures
Generates synthetic test data for full pipeline testing
"""
from datetime import datetime, timedelta, date
from typing import List, Dict, Tuple
import psycopg2


class TestDataGenerator:
    """Generates synthetic GSC and GA4 data for testing"""
    
    TEST_PROPERTY = "test://e2e-pipeline"
    TEST_PAGE = "/test/page/anomaly"
    TEST_QUERY = "test query e2e"
    
    @staticmethod
    def generate_gsc_data_with_anomaly(days: int = 30) -> List[Dict]:
        """
        Generate GSC data with planted anomaly
        
        Days 1-20: Stable 100 clicks/day
        Days 21-30: Drop to 50 clicks/day (-50% WoW anomaly on day 28)
        
        Returns:
            List of dicts ready for database insertion
        """
        data = []
        today = date.today()
        
        for i in range(days):
            day = today - timedelta(days=days - i - 1)
            
            # Determine clicks based on day
            if i < 20:
                clicks = 100
                impressions = 1000
            else:
                clicks = 50  # Anomaly: 50% drop
                impressions = 1000
            
            ctr = (clicks / impressions) * 100 if impressions > 0 else 0
            
            data.append({
                'date': day,
                'property': TestDataGenerator.TEST_PROPERTY,
                'url': TestDataGenerator.TEST_PAGE,
                'query': TestDataGenerator.TEST_QUERY,
                'country': 'usa',
                'device': 'DESKTOP',
                'clicks': clicks,
                'impressions': impressions,
                'ctr': round(ctr, 2),
                'position': 5.0
            })
        
        return data
    
    @staticmethod
    def generate_ga4_data_with_anomaly(days: int = 30) -> List[Dict]:
        """
        Generate GA4 data matching GSC anomaly pattern
        
        Conversions drop proportionally to clicks
        
        Returns:
            List of dicts ready for database insertion
        """
        data = []
        today = date.today()
        
        for i in range(days):
            day = today - timedelta(days=days - i - 1)
            
            # Match GSC pattern
            if i < 20:
                sessions = 80
                conversions = 10
            else:
                sessions = 40  # Anomaly: proportional drop
                conversions = 5
            
            engagement_rate = 0.75
            bounce_rate = 0.25
            
            data.append({
                'date': day,
                'property': TestDataGenerator.TEST_PROPERTY,
                'page_path': TestDataGenerator.TEST_PAGE,
                'source_medium': 'google/organic',
                'sessions': sessions,
                'engagement_rate': engagement_rate,
                'bounce_rate': bounce_rate,
                'conversions': conversions,
                'avg_session_duration': 120.0,
                'page_views': sessions + 10
            })
        
        return data
    
    @staticmethod
    def insert_gsc_data(conn, data: List[Dict]) -> int:
        """Insert GSC test data into database"""
        cur = conn.cursor()
        
        inserted = 0
        for row in data:
            cur.execute("""
                INSERT INTO gsc.fact_gsc_daily 
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES (%(date)s, %(property)s, %(url)s, %(query)s, %(country)s, %(device)s, 
                        %(clicks)s, %(impressions)s, %(ctr)s, %(position)s)
                ON CONFLICT (date, property, url, query, country, device) 
                DO UPDATE SET 
                    clicks = EXCLUDED.clicks,
                    impressions = EXCLUDED.impressions,
                    ctr = EXCLUDED.ctr,
                    position = EXCLUDED.position
            """, row)
            inserted += 1
        
        conn.commit()
        return inserted
    
    @staticmethod
    def insert_ga4_data(conn, data: List[Dict]) -> int:
        """Insert GA4 test data into database"""
        cur = conn.cursor()
        
        inserted = 0
        for row in data:
            cur.execute("""
                INSERT INTO gsc.fact_ga4_daily 
                (date, property, page_path, source_medium, sessions, engagement_rate, 
                 bounce_rate, conversions, avg_session_duration, page_views)
                VALUES (%(date)s, %(property)s, %(page_path)s, %(source_medium)s, 
                        %(sessions)s, %(engagement_rate)s, %(bounce_rate)s, %(conversions)s,
                        %(avg_session_duration)s, %(page_views)s)
                ON CONFLICT (date, property, page_path, source_medium) 
                DO UPDATE SET 
                    sessions = EXCLUDED.sessions,
                    conversions = EXCLUDED.conversions
            """, row)
            inserted += 1
        
        conn.commit()
        return inserted
    
    @staticmethod
    def cleanup_test_data(conn):
        """Remove all test data (idempotent)"""
        cur = conn.cursor()
        
        # Delete from fact tables
        cur.execute("DELETE FROM gsc.fact_gsc_daily WHERE property LIKE 'test://%'")
        gsc_deleted = cur.rowcount
        
        cur.execute("DELETE FROM gsc.fact_ga4_daily WHERE property LIKE 'test://%'")
        ga4_deleted = cur.rowcount
        
        # Delete from insights
        cur.execute("DELETE FROM gsc.insights WHERE property LIKE 'test://%'")
        insights_deleted = cur.rowcount
        
        conn.commit()
        
        return {
            'gsc_deleted': gsc_deleted,
            'ga4_deleted': ga4_deleted,
            'insights_deleted': insights_deleted
        }
    
    @staticmethod
    def verify_unified_view_has_test_data(conn) -> Dict:
        """Verify test data appears in unified view"""
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                COUNT(*) as row_count,
                COUNT(DISTINCT date) as date_count,
                COUNT(*) FILTER (WHERE gsc_clicks_change_wow IS NOT NULL) as wow_count,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM gsc.vw_unified_page_performance
            WHERE property = %s AND page_path = %s
        """, (TestDataGenerator.TEST_PROPERTY, TestDataGenerator.TEST_PAGE))
        
        result = cur.fetchone()
        
        return {
            'row_count': result[0],
            'date_count': result[1],
            'wow_count': result[2],
            'earliest_date': result[3],
            'latest_date': result[4]
        }
    
    @staticmethod
    def get_planted_anomaly_date() -> date:
        """Get the date where anomaly should be detected (day 28 of 30)"""
        today = date.today()
        return today - timedelta(days=2)  # Day 28 of 30-day window
