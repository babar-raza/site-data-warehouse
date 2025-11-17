#!/usr/bin/env python3
"""
Historical Data Backfill Script
Fills gaps in historical GSC and GA4 data
"""
import os
import sys
import argparse
from datetime import datetime, timedelta, date
from typing import List, Optional
import psycopg2


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
    
    def _ingest_gsc_date(self, property: str, date: date):
        """
        Ingest GSC data for specific date
        
        NOTE: This is a placeholder - actual implementation would call
        the API ingestor or similar
        """
        # TODO: Call actual ingestor
        # For now, just a placeholder
        import subprocess
        
        result = subprocess.run([
            'python', 'ingestors/api/api_ingestor.py',
            '--property', property,
            '--start-date', date.isoformat(),
            '--end-date', date.isoformat()
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Ingestion failed: {result.stderr}")
    
    def _ingest_ga4_date(self, property: str, date: date):
        """
        Ingest GA4 data for specific date
        
        NOTE: This is a placeholder
        """
        # TODO: Call actual ingestor
        import subprocess
        
        result = subprocess.run([
            'python', 'ingestors/ga4/ga4_ingestor.py',
            '--property', property,
            '--start-date', date.isoformat(),
            '--end-date', date.isoformat()
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Ingestion failed: {result.stderr}")
    
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
