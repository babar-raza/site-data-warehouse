#!/usr/bin/env python3
"""
Historical Data Backfill Script
Fills gaps in historical GSC and GA4 data

Optimized for direct import of ingestors (no subprocess overhead).
Falls back to subprocess if import fails.
"""
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
import psycopg2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalBackfill:
    """Backfill historical data for GSC and GA4"""
    
    def __init__(self, dsn: str):
        """Initialize backfill with database connection"""
        self.dsn = dsn
        self.conn = psycopg2.connect(dsn)
    
    def get_missing_dates(self, property: str, source: str = 'gsc') -> List[date]:
        """
        Find missing dates in data range
        
        Args:
            property: Property to check
            source: 'gsc' or 'ga4'
            
        Returns:
            List of missing dates
        """
        cur = self.conn.cursor()
        
        if source == 'gsc':
            table = 'fact_gsc_daily'
        elif source == 'ga4':
            table = 'fact_ga4_daily'
        else:
            raise ValueError(f"Unknown source: {source}")
        
        # Get date range
        cur.execute(f"""
            SELECT MIN(date), MAX(date)
            FROM gsc.{table}
            WHERE property = %s
        """, (property,))
        
        result = cur.fetchone()
        if not result[0]:
            print(f"No data found for property: {property}")
            return []
        
        min_date, max_date = result
        
        # Get all dates that exist
        cur.execute(f"""
            SELECT DISTINCT date
            FROM gsc.{table}
            WHERE property = %s
            ORDER BY date
        """, (property,))
        
        existing_dates = set(row[0] for row in cur.fetchall())
        
        # Find missing dates
        missing = []
        current = min_date
        while current <= max_date:
            if current not in existing_dates:
                missing.append(current)
            current += timedelta(days=1)
        
        cur.close()
        
        return missing
    
    def backfill_range(
        self,
        property: str,
        start_date: date,
        end_date: date,
        source: str = 'gsc',
        dry_run: bool = False
    ):
        """
        Backfill data for date range
        
        Args:
            property: Property to backfill
            start_date: Start date
            end_date: End date
            source: 'gsc' or 'ga4'
            dry_run: If True, only print what would be done
        """
        print(f"Backfilling {source.upper()} data for {property}")
        print(f"Date range: {start_date} to {end_date}")
        
        if dry_run:
            print("DRY RUN - No data will be ingested")
        
        # Calculate dates
        total_days = (end_date - start_date).days + 1
        
        print(f"Total days to backfill: {total_days}")
        print()
        
        if dry_run:
            print("Would run ingestion for each date...")
            return
        
        # Run ingestion for each date
        success_count = 0
        error_count = 0
        
        current = start_date
        while current <= end_date:
            print(f"Ingesting {current}...", end=' ')
            
            try:
                if source == 'gsc':
                    self._ingest_gsc_date(property, current)
                elif source == 'ga4':
                    self._ingest_ga4_date(property, current)
                
                print("✓")
                success_count += 1
            except Exception as e:
                print(f"✗ Error: {e}")
                error_count += 1
            
            current += timedelta(days=1)
        
        print()
        print(f"Backfill complete: {success_count} succeeded, {error_count} failed")
    
    def _ingest_gsc_date(self, property: str, ingest_date: date):
        """
        Ingest GSC data for specific date using direct import.

        Uses direct import of GSCAPIIngestor for better performance.
        Falls back to subprocess if import fails.

        Args:
            property: GSC property URL (e.g., 'sc-domain:example.com')
            ingest_date: Date to ingest data for
        """
        try:
            # Primary method: Direct import
            from ingestors.api.gsc_api_ingestor import GSCAPIIngestor

            logger.info(f"Using direct import for GSC ingestion: {property} on {ingest_date}")

            # Build config from environment
            config = self._build_gsc_config()

            # Initialize and run ingestor for single date
            ingestor = GSCAPIIngestor(config)
            ingestor.connect_gsc()
            ingestor.connect_warehouse()

            # Fetch and process data for the specific date
            api_rows = ingestor.fetch_search_analytics(
                property, ingest_date, ingest_date
            )

            if api_rows:
                # Transform and upsert
                transformed = [
                    ingestor.transform_api_row(row, property)
                    for row in api_rows
                ]
                rows_processed = ingestor.upsert_data(transformed)

                # Update watermark
                ingestor.update_watermark(property, ingest_date, rows_processed)
                logger.info(f"GSC ingestion complete: {rows_processed} rows for {ingest_date}")
            else:
                # Update watermark even if no data (to mark date as processed)
                ingestor.update_watermark(property, ingest_date, 0)
                logger.info(f"GSC ingestion complete: 0 rows for {ingest_date}")

        except ImportError as e:
            # Fallback: Use subprocess if import fails
            logger.warning(f"Direct import failed: {e}, using subprocess fallback")
            self._ingest_gsc_date_subprocess(property, ingest_date)

        except Exception as e:
            logger.error(f"GSC ingestion error: {e}")
            raise

    def _ingest_gsc_date_subprocess(self, property: str, ingest_date: date):
        """
        Fallback method: Ingest GSC data using subprocess.

        Args:
            property: GSC property URL
            ingest_date: Date to ingest data for
        """
        import subprocess

        logger.info(f"Using subprocess fallback for GSC ingestion: {property} on {ingest_date}")

        result = subprocess.run([
            sys.executable, 'ingestors/api/gsc_api_ingestor.py',
            '--property', property,
            '--start-date', ingest_date.isoformat(),
            '--end-date', ingest_date.isoformat()
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Subprocess ingestion failed: {result.stderr}")

        logger.info(f"Subprocess GSC ingestion complete for {ingest_date}")

    def _build_gsc_config(self) -> Dict[str, Any]:
        """
        Build GSC ingestor configuration from environment variables.

        Returns:
            Configuration dictionary for GSCAPIIngestor
        """
        return {
            'GSC_SVC_JSON': os.getenv('GSC_SVC_JSON', '/run/secrets/gsc_sa.json'),
            'DB_HOST': os.getenv('DB_HOST', 'warehouse'),
            'DB_PORT': os.getenv('DB_PORT', '5432'),
            'DB_NAME': os.getenv('DB_NAME', 'gsc_db'),
            'DB_USER': os.getenv('DB_USER', 'gsc_user'),
            'DB_PASSWORD': os.getenv('DB_PASSWORD', 'gsc_pass'),
            'REQUESTS_PER_MINUTE': os.getenv('REQUESTS_PER_MINUTE', '30'),
            'REQUESTS_PER_DAY': os.getenv('REQUESTS_PER_DAY', '2000'),
            'BURST_SIZE': os.getenv('BURST_SIZE', '5'),
            'API_COOLDOWN_SEC': os.getenv('API_COOLDOWN_SEC', '2'),
            'GSC_API_ROWS_PER_PAGE': os.getenv('GSC_API_ROWS_PER_PAGE', '25000'),
            'GSC_API_MAX_RETRIES': os.getenv('GSC_API_MAX_RETRIES', '5'),
            'BASE_BACKOFF': os.getenv('BASE_BACKOFF', '2.0'),
            'MAX_BACKOFF': os.getenv('MAX_BACKOFF', '300.0'),
            'BACKOFF_JITTER': os.getenv('BACKOFF_JITTER', 'true'),
            'INGEST_DAYS': '1',  # Single day for backfill
            'GSC_INITIAL_BACKFILL_DAYS': '1'  # Single day for backfill
        }
    
    def _ingest_ga4_date(self, property: str, ingest_date: date):
        """
        Ingest GA4 data for specific date using direct import.

        Uses direct import of GA4Extractor for better performance.
        Falls back to subprocess if import fails.

        Args:
            property: Property URL (e.g., 'https://example.com/')
            ingest_date: Date to ingest data for
        """
        try:
            # Primary method: Direct import
            from ingestors.ga4.ga4_extractor import GA4Extractor

            logger.info(f"Using direct import for GA4 ingestion: {property} on {ingest_date}")

            # Initialize extractor
            extractor = GA4Extractor()

            # Get GA4 property config from stored config
            property_config = self._get_ga4_property_config(property)
            if not property_config:
                raise ValueError(f"No GA4 configuration found for property: {property}")

            # Extract data for specific date
            extractor.extract_property(
                property_config=property_config,
                start_date=ingest_date,
                end_date=ingest_date
            )

            logger.info(f"GA4 ingestion complete: {extractor.stats['rows_inserted']} rows for {ingest_date}")

        except ImportError as e:
            # Fallback: Use subprocess if import fails
            logger.warning(f"Direct import failed: {e}, using subprocess fallback")
            self._ingest_ga4_date_subprocess(property, ingest_date)

        except Exception as e:
            logger.error(f"GA4 ingestion error: {e}")
            raise

    def _ingest_ga4_date_subprocess(self, property: str, ingest_date: date):
        """
        Fallback method: Ingest GA4 data using subprocess.

        Args:
            property: Property URL
            ingest_date: Date to ingest data for
        """
        import subprocess

        logger.info(f"Using subprocess fallback for GA4 ingestion: {property} on {ingest_date}")

        result = subprocess.run([
            sys.executable, 'ingestors/ga4/ga4_extractor.py',
            '--days', '1'
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Subprocess ingestion failed: {result.stderr}")

        logger.info(f"Subprocess GA4 ingestion complete for {ingest_date}")

    def _get_ga4_property_config(self, property: str) -> Optional[Dict[str, Any]]:
        """
        Get GA4 property configuration from database or config file.

        Args:
            property: Property URL

        Returns:
            Property configuration dict or None if not found
        """
        try:
            # Try to get GA4 property ID from database
            cur = self.conn.cursor()
            cur.execute("""
                SELECT ga4_property_id
                FROM gsc.dim_property
                WHERE property_url = %s OR url = %s
            """, (property, property))

            result = cur.fetchone()
            cur.close()

            if result and result[0]:
                return {
                    'url': property,
                    'ga4_property_id': result[0]
                }

            # Fallback: Try to get from environment
            ga4_property_id = os.getenv('GA4_PROPERTY_ID')
            if ga4_property_id:
                return {
                    'url': property,
                    'ga4_property_id': ga4_property_id
                }

            return None

        except Exception as e:
            logger.warning(f"Could not get GA4 config for {property}: {e}")
            # Fallback to environment
            ga4_property_id = os.getenv('GA4_PROPERTY_ID')
            if ga4_property_id:
                return {
                    'url': property,
                    'ga4_property_id': ga4_property_id
                }
            return None
    
    def fill_gaps(self, property: str, source: str = 'gsc', dry_run: bool = False):
        """
        Find and fill all date gaps
        
        Args:
            property: Property to backfill
            source: 'gsc' or 'ga4'
            dry_run: If True, only print what would be done
        """
        missing_dates = self.get_missing_dates(property, source)
        
        if not missing_dates:
            print(f"No missing dates found for {property} ({source})")
            return
        
        print(f"Found {len(missing_dates)} missing dates for {property} ({source})")
        print(f"Date ranges with gaps:")
        
        # Group consecutive dates
        gaps = []
        current_gap = [missing_dates[0]]
        
        for d in missing_dates[1:]:
            if d == current_gap[-1] + timedelta(days=1):
                current_gap.append(d)
            else:
                gaps.append((current_gap[0], current_gap[-1]))
                current_gap = [d]
        
        gaps.append((current_gap[0], current_gap[-1]))
        
        for start, end in gaps:
            days = (end - start).days + 1
            print(f"  {start} to {end} ({days} days)")
        
        print()
        
        if dry_run:
            print("DRY RUN - Would fill these gaps")
            return
        
        # Fill each gap
        for start, end in gaps:
            self.backfill_range(property, start, end, source, dry_run=False)
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main backfill routine"""
    parser = argparse.ArgumentParser(description='Backfill historical GSC/GA4 data')
    parser.add_argument('--property', required=True, help='Property to backfill')
    parser.add_argument('--source', default='gsc', choices=['gsc', 'ga4'], 
                       help='Data source to backfill')
    parser.add_argument('--days', type=int, help='Number of days to backfill from today')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--fill-gaps', action='store_true', 
                       help='Fill date gaps instead of range')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without doing it')
    args = parser.parse_args()
    
    # Get database connection
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        print("Error: WAREHOUSE_DSN environment variable not set")
        sys.exit(1)
    
    backfill = HistoricalBackfill(dsn)
    
    try:
        if args.fill_gaps:
            # Fill all gaps
            backfill.fill_gaps(args.property, args.source, args.dry_run)
        else:
            # Backfill range
            if args.days:
                end_date = date.today() - timedelta(days=1)  # Yesterday
                start_date = end_date - timedelta(days=args.days)
            elif args.start_date and args.end_date:
                start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
            else:
                print("Error: Must specify --days OR --start-date and --end-date")
                sys.exit(1)
            
            backfill.backfill_range(
                args.property,
                start_date,
                end_date,
                args.source,
                args.dry_run
            )
    
    finally:
        backfill.close()


if __name__ == '__main__':
    main()
