#!/usr/bin/env python3
"""
GA4 Data Extractor
Extracts page-level metrics from Google Analytics 4 and loads into warehouse
"""
import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_batch
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ga4.ga4_client import GA4Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WAREHOUSE_DSN = os.environ.get('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')
GA4_CREDENTIALS_PATH = os.environ.get('GA4_CREDENTIALS_PATH', '/secrets/ga4_sa.json')
CONFIG_FILE = os.environ.get('GA4_CONFIG_FILE', '/app/ingestors/ga4/config.yaml')


class GA4Extractor:
    """
    GA4 data extraction and loading
    """
    
    def __init__(self, config_path: str = None):
        """Initialize extractor"""
        self.config = self._load_config(config_path or CONFIG_FILE)
        self.warehouse_dsn = WAREHOUSE_DSN
        self.credentials_path = GA4_CREDENTIALS_PATH
        
        # Statistics
        self.stats = {
            'rows_fetched': 0,
            'rows_inserted': 0,
            'rows_updated': 0,
            'rows_failed': 0,
            'properties_processed': 0
        }
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'properties': [
                {
                    'url': 'https://example.com/',
                    'ga4_property_id': '12345678'
                }
            ],
            'extraction': {
                'default_days_back': 30,
                'rate_limit_qps': 10,
                'batch_size': 1000
            },
            'validation': {
                'min_sessions_threshold': 0,
                'max_bounce_rate': 1.0
            }
        }
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.warehouse_dsn)
    
    def get_watermark(self, property_url: str) -> datetime.date:
        """Get last extraction date for property"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT last_date
                    FROM gsc.ingest_watermarks
                    WHERE property = %s AND source_type = 'ga4'
                """, (property_url,))
                result = cur.fetchone()
            conn.close()
            
            if result and result[0]:
                return result[0]
            else:
                # Default to 30 days ago
                return datetime.now().date() - timedelta(days=30)
        except Exception as e:
            logger.error(f"Failed to get watermark: {e}")
            return datetime.now().date() - timedelta(days=30)
    
    def update_watermark(self, property_url: str, last_date: datetime.date):
        """Update watermark for property"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO gsc.ingest_watermarks 
                        (property, source_type, last_date, last_run_at, last_run_status)
                    VALUES (%s, 'ga4', %s, CURRENT_TIMESTAMP, 'success')
                    ON CONFLICT (property, source_type)
                    DO UPDATE SET
                        last_date = EXCLUDED.last_date,
                        last_run_at = EXCLUDED.last_run_at,
                        last_run_status = EXCLUDED.last_run_status
                """, (property_url, last_date))
            conn.commit()
            conn.close()
            logger.info(f"Updated watermark for {property_url}: {last_date}")
        except Exception as e:
            logger.error(f"Failed to update watermark: {e}")
    
    def upsert_data(self, property_url: str, data: List[Dict[str, Any]]):
        """Upsert data into fact_ga4_daily table"""
        if not data:
            logger.warning("No data to upsert")
            return
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                # Prepare data for batch insert
                rows = [
                    (
                        row['date'],
                        property_url,
                        row['page_path'],
                        row['sessions'],
                        row['engaged_sessions'],
                        row['engagement_rate'],
                        row['bounce_rate'],
                        row['conversions'],
                        row['conversion_rate'],
                        row['avg_session_duration'],
                        row['page_views'],
                        row['avg_time_on_page'],
                        0,  # exits (not available in this extract)
                        0.0  # exit_rate (not available in this extract)
                    )
                    for row in data
                ]
                
                # Batch upsert
                execute_batch(cur, """
                    INSERT INTO gsc.fact_ga4_daily (
                        date, property, page_path,
                        sessions, engaged_sessions, engagement_rate, bounce_rate,
                        conversions, conversion_rate, avg_session_duration,
                        page_views, avg_time_on_page, exits, exit_rate
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date, property, page_path)
                    DO UPDATE SET
                        sessions = EXCLUDED.sessions,
                        engaged_sessions = EXCLUDED.engaged_sessions,
                        engagement_rate = EXCLUDED.engagement_rate,
                        bounce_rate = EXCLUDED.bounce_rate,
                        conversions = EXCLUDED.conversions,
                        conversion_rate = EXCLUDED.conversion_rate,
                        avg_session_duration = EXCLUDED.avg_session_duration,
                        page_views = EXCLUDED.page_views,
                        avg_time_on_page = EXCLUDED.avg_time_on_page,
                        updated_at = CURRENT_TIMESTAMP
                """, rows, page_size=self.config['extraction']['batch_size'])
            
            conn.commit()
            self.stats['rows_inserted'] += len(data)
            logger.info(f"Upserted {len(data)} rows for {property_url}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to upsert data: {e}")
            self.stats['rows_failed'] += len(data)
            raise
        finally:
            conn.close()
    
    def extract_property(
        self,
        property_config: Dict[str, Any],
        start_date: datetime.date,
        end_date: datetime.date,
        dry_run: bool = False
    ):
        """Extract data for a single property"""
        property_url = property_config['url']
        property_id = property_config['ga4_property_id']
        
        logger.info("=" * 60)
        logger.info(f"Extracting GA4 data for {property_url}")
        logger.info(f"Property ID: {property_id}")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info("=" * 60)
        
        if dry_run:
            logger.info("DRY RUN - No API calls or database writes")
            return
        
        # Initialize GA4 client
        try:
            client = GA4Client(
                credentials_path=self.credentials_path,
                property_id=property_id,
                rate_limit_qps=self.config['extraction']['rate_limit_qps']
            )
            
            # Validate credentials
            if not client.validate_credentials():
                raise Exception("GA4 credentials validation failed")
            
        except Exception as e:
            logger.error(f"Failed to initialize GA4 client: {e}")
            return
        
        # Fetch data
        try:
            data = client.get_page_metrics(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            self.stats['rows_fetched'] += len(data)
            logger.info(f"Fetched {len(data)} rows from GA4 API")
            
            # Upsert into warehouse
            if data:
                self.upsert_data(property_url, data)
                
                # Update watermark
                self.update_watermark(property_url, end_date)
            
            self.stats['properties_processed'] += 1
            
        except Exception as e:
            logger.error(f"Failed to extract data for {property_url}: {e}")
    
    def extract_all(self, days_back: int = None, dry_run: bool = False):
        """Extract data for all configured properties"""
        logger.info("Starting GA4 extraction")
        
        days_back = days_back or self.config['extraction']['default_days_back']
        end_date = datetime.now().date() - timedelta(days=1)  # Yesterday
        
        for prop in self.config['properties']:
            # Get watermark for incremental extraction
            watermark = self.get_watermark(prop['url'])
            start_date = end_date - timedelta(days=days_back)
            
            # Use watermark if it's more recent
            if watermark > start_date:
                start_date = watermark + timedelta(days=1)
            
            # Skip if already up to date
            if start_date > end_date:
                logger.info(f"Property {prop['url']} is already up to date")
                continue
            
            self.extract_property(prop, start_date, end_date, dry_run)
        
        # Print statistics
        logger.info("=" * 60)
        logger.info("GA4 Extraction Complete")
        logger.info(f"Properties processed: {self.stats['properties_processed']}")
        logger.info(f"Rows fetched: {self.stats['rows_fetched']}")
        logger.info(f"Rows inserted/updated: {self.stats['rows_inserted']}")
        logger.info(f"Rows failed: {self.stats['rows_failed']}")
        logger.info("=" * 60)
    
    def validate_data(self):
        """Validate data quality in warehouse"""
        logger.info("Running data validation...")
        
        conn = self.get_db_connection()
        issues = []
        
        try:
            with conn.cursor() as cur:
                # Check 1: Duplicate records
                cur.execute("""
                    SELECT COUNT(*) as dup_count
                    FROM (
                        SELECT date, property, page_path, COUNT(*)
                        FROM gsc.fact_ga4_daily
                        GROUP BY date, property, page_path
                        HAVING COUNT(*) > 1
                    ) dups
                """)
                dup_count = cur.fetchone()[0]
                if dup_count > 0:
                    issues.append(f"Found {dup_count} duplicate records")
                
                # Check 2: Null values in critical fields
                cur.execute("""
                    SELECT COUNT(*) FROM gsc.fact_ga4_daily
                    WHERE sessions IS NULL OR page_views IS NULL
                """)
                null_count = cur.fetchone()[0]
                if null_count > 0:
                    issues.append(f"Found {null_count} rows with null critical fields")
                
                # Check 3: Data freshness
                cur.execute("""
                    SELECT property, MAX(date) as latest_date,
                           CURRENT_DATE - MAX(date) as days_behind
                    FROM gsc.fact_ga4_daily
                    GROUP BY property
                """)
                for row in cur.fetchall():
                    if row[2] > 7:
                        issues.append(f"Property {row[0]} is {row[2]} days behind")
                
                # Check 4: Invalid metric values
                cur.execute("""
                    SELECT COUNT(*) FROM gsc.fact_ga4_daily
                    WHERE engagement_rate < 0 OR engagement_rate > 1
                    OR bounce_rate < 0 OR bounce_rate > 1
                """)
                invalid_count = cur.fetchone()[0]
                if invalid_count > 0:
                    issues.append(f"Found {invalid_count} rows with invalid metric values")
        
        finally:
            conn.close()
        
        if issues:
            logger.warning(f"Data validation found {len(issues)} issues:")
            for issue in issues:
                logger.warning(f"  - {issue}")
            return False
        else:
            logger.info("Data validation passed - no issues found")
            return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='GA4 Data Extractor')
    parser.add_argument('--days', type=int, help='Number of days to extract')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without API calls')
    parser.add_argument('--validate', action='store_true', help='Run data validation only')
    parser.add_argument('--config', type=str, help='Path to config file')
    
    args = parser.parse_args()
    
    # Initialize extractor
    extractor = GA4Extractor(config_path=args.config)
    
    if args.validate:
        # Run validation only
        success = extractor.validate_data()
        return 0 if success else 1
    else:
        # Run extraction
        extractor.extract_all(days_back=args.days, dry_run=args.dry_run)
        return 0


if __name__ == '__main__':
    sys.exit(main())
