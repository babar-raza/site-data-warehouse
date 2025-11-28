#!/usr/bin/env python3
"""
URL Discovery Sync CLI
======================
Discovers URLs from GSC and GA4 and syncs them to CWV monitoring.

This ensures that every URL receiving clicks (GSC) or sessions (GA4) is
automatically considered for Core Web Vitals data collection.

Usage:
    # Dry run (no changes)
    python scripts/sync_urls_to_cwv.py --dry-run

    # Sync all properties
    python scripts/sync_urls_to_cwv.py

    # Sync specific property
    python scripts/sync_urls_to_cwv.py --property https://example.com/

    # Custom thresholds
    python scripts/sync_urls_to_cwv.py --min-clicks 20 --min-sessions 10

    # Show current status
    python scripts/sync_urls_to_cwv.py --status
"""

import argparse
import logging
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insights_core.url_discovery_sync import (
    URLDiscoverySync,
    SyncConfig,
    sync_all_properties,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


def print_separator(char='=', width=60):
    """Print a separator line."""
    print(char * width)


def print_header(text):
    """Print a header with separators."""
    print_separator()
    print(text)
    print_separator()


def show_status(db_dsn: str):
    """Show current monitored pages status."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    print_header("URL Discovery Sync - Current Status")

    try:
        conn = psycopg2.connect(db_dsn)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get summary by property
            cur.execute("""
                SELECT
                    property,
                    COUNT(*) as total_pages,
                    COUNT(*) FILTER (WHERE is_active) as active_pages,
                    COUNT(*) FILTER (WHERE discovery_source = 'gsc') as from_gsc,
                    COUNT(*) FILTER (WHERE discovery_source = 'ga4') as from_ga4,
                    COUNT(*) FILTER (WHERE discovery_source = 'gsc+ga4') as from_both,
                    COUNT(*) FILTER (WHERE discovery_source = 'manual') as from_manual,
                    SUM(total_clicks) as total_clicks,
                    SUM(total_sessions) as total_sessions,
                    MAX(last_seen_at) as last_activity
                FROM performance.monitored_pages
                GROUP BY property
                ORDER BY COUNT(*) DESC
            """)
            properties = cur.fetchall()

            if not properties:
                print("\nNo monitored pages found.")
                print("Run sync to discover URLs from GSC and GA4.")
                return

            print(f"\nMonitored Pages Summary ({len(properties)} properties):\n")

            for prop in properties:
                print(f"  {prop['property']}")
                print(f"    Total: {prop['total_pages']} pages ({prop['active_pages']} active)")
                print(f"    Sources: GSC={prop['from_gsc']}, GA4={prop['from_ga4']}, "
                      f"Both={prop['from_both']}, Manual={prop['from_manual']}")
                print(f"    Traffic: {prop['total_clicks'] or 0} clicks, "
                      f"{prop['total_sessions'] or 0} sessions")
                if prop['last_activity']:
                    print(f"    Last activity: {prop['last_activity']}")
                print()

            # Get overall totals
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_active) as active,
                    COUNT(*) FILTER (WHERE check_mobile AND is_active) as mobile_checks,
                    COUNT(*) FILTER (WHERE check_desktop AND is_active) as desktop_checks
                FROM performance.monitored_pages
            """)
            totals = cur.fetchone()

            print_separator('-')
            print(f"Total: {totals['total']} pages ({totals['active']} active)")
            print(f"CWV Checks: {totals['mobile_checks']} mobile, {totals['desktop_checks']} desktop")

            # Get stale pages count
            cur.execute("""
                SELECT COUNT(*) as stale_count
                FROM performance.monitored_pages
                WHERE is_active = true
                  AND discovery_source != 'manual'
                  AND last_seen_at < CURRENT_TIMESTAMP - INTERVAL '90 days'
            """)
            stale = cur.fetchone()
            if stale['stale_count'] > 0:
                print(f"\nWarning: {stale['stale_count']} pages are stale (not seen in 90+ days)")

        conn.close()

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        sys.exit(1)

    print_separator()


def run_sync(
    db_dsn: str,
    property: str = None,
    dry_run: bool = False,
    min_clicks: int = 10,
    min_sessions: int = 5,
    lookback_days: int = 30,
    max_new_urls: int = 100
):
    """Run URL discovery and sync."""
    mode = "DRY RUN" if dry_run else "LIVE"
    print_header(f"URL Discovery Sync - {mode}")

    print(f"\nConfiguration:")
    print(f"  Min GSC clicks: {min_clicks}")
    print(f"  Min GA4 sessions: {min_sessions}")
    print(f"  Lookback days: {lookback_days}")
    print(f"  Max new URLs per run: {max_new_urls}")
    if property:
        print(f"  Property filter: {property}")
    print()

    config = SyncConfig(
        min_gsc_clicks=min_clicks,
        min_ga4_sessions=min_sessions,
        lookback_days=lookback_days,
        max_new_urls_per_run=max_new_urls,
    )

    sync = URLDiscoverySync(db_dsn=db_dsn, config=config)

    try:
        if property:
            # Sync single property
            result = sync.sync(property=property, dry_run=dry_run)
            results = [result]
        else:
            # Sync all properties
            results = sync.sync_all_properties(dry_run=dry_run)

        # Print results
        print_separator('-')
        print("\nResults by Property:\n")

        total_discovered = 0
        total_new = 0
        total_updated = 0
        total_deactivated = 0
        total_errors = 0

        for result in results:
            status = "OK" if result.success else "FAILED"
            print(f"  [{status}] {result.property}")

            if result.success:
                print(f"    Discovered: {result.urls_discovered} URLs")
                if result.details:
                    print(f"      - GSC only: {result.details.get('urls_from_gsc_only', 0)}")
                    print(f"      - GA4 only: {result.details.get('urls_from_ga4_only', 0)}")
                    print(f"      - Both sources: {result.details.get('urls_from_both', 0)}")
                print(f"    New: {result.urls_new}")
                print(f"    Updated: {result.urls_updated}")
                print(f"    Deactivated: {result.urls_deactivated}")
                if result.details.get('urls_skipped', 0) > 0:
                    print(f"    Skipped (limit reached): {result.details['urls_skipped']}")

                total_discovered += result.urls_discovered
                total_new += result.urls_new
                total_updated += result.urls_updated
                total_deactivated += result.urls_deactivated
            else:
                print(f"    Error: {result.error}")
                total_errors += 1

            print()

        # Print totals
        print_separator('-')
        print("\nSummary:")
        print(f"  Properties processed: {len(results)}")
        print(f"  Total URLs discovered: {total_discovered}")
        print(f"  New URLs added: {total_new}")
        print(f"  Existing URLs updated: {total_updated}")
        print(f"  Stale URLs deactivated: {total_deactivated}")
        if total_errors > 0:
            print(f"  Errors: {total_errors}")

        if dry_run:
            print("\n  [DRY RUN] No changes were made to the database.")

        total_duration = sum(r.duration_seconds for r in results)
        print(f"\nTotal duration: {total_duration:.2f}s")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)
    finally:
        sync.close()

    print_separator()

    # Exit with error if any failures
    if total_errors > 0:
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='URL Discovery Sync - Discover URLs from GSC/GA4 for CWV monitoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run              # Preview changes without committing
  %(prog)s                        # Sync all properties
  %(prog)s --property https://example.com/
  %(prog)s --min-clicks 20 --min-sessions 10
  %(prog)s --status               # Show current monitored pages status
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing to database'
    )

    parser.add_argument(
        '--property',
        type=str,
        help='Filter by specific property URL'
    )

    parser.add_argument(
        '--min-clicks',
        type=int,
        default=10,
        help='Minimum GSC clicks threshold (default: 10)'
    )

    parser.add_argument(
        '--min-sessions',
        type=int,
        default=5,
        help='Minimum GA4 sessions threshold (default: 5)'
    )

    parser.add_argument(
        '--lookback-days',
        type=int,
        default=30,
        help='Days to look back for activity (default: 30)'
    )

    parser.add_argument(
        '--max-new-urls',
        type=int,
        default=100,
        help='Maximum new URLs to add per run (default: 100)'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current monitored pages status'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get database DSN
    db_dsn = os.environ.get('WAREHOUSE_DSN')
    if not db_dsn:
        # Try to construct from individual vars
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'gsc_db')
        db_user = os.environ.get('DB_USER', 'gsc_user')
        db_pass = os.environ.get('DB_PASSWORD', 'gsc_pass_secure_2024')
        db_dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    # Run appropriate command
    if args.status:
        show_status(db_dsn)
    else:
        run_sync(
            db_dsn=db_dsn,
            property=args.property,
            dry_run=args.dry_run,
            min_clicks=args.min_clicks,
            min_sessions=args.min_sessions,
            lookback_days=args.lookback_days,
            max_new_urls=args.max_new_urls,
        )


if __name__ == '__main__':
    main()
