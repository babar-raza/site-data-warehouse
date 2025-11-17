"""
CLI interface for Insight Engine
"""
import sys
import argparse
import logging
from datetime import datetime

from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig
from insights_core.repository import InsightRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_refresh(args):
    """Refresh insights by running all detectors"""
    config = InsightsConfig()
    engine = InsightEngine(config)
    
    logger.info(f"Starting insights refresh for property: {args.property or 'ALL'}")
    stats = engine.refresh(property=args.property)
    
    print("\n" + "=" * 60)
    print("INSIGHT ENGINE RESULTS")
    print("=" * 60)
    print(f"Total insights created: {stats['total_insights_created']}")
    print(f"Detectors succeeded: {stats['detectors_succeeded']}/{stats['detectors_run']}")
    print(f"Duration: {stats['duration_seconds']:.2f}s")
    
    if stats['insights_by_detector']:
        print("\nInsights by detector:")
        for detector, count in stats['insights_by_detector'].items():
            print(f"  {detector}: {count}")
    
    if stats['errors']:
        print("\nErrors:")
        for error in stats['errors']:
            print(f"  {error['detector']}: {error['error']}")
    
    print("=" * 60)
    
    return 0 if stats['detectors_failed'] == 0 else 1


def cmd_stats(args):
    """Show insight statistics"""
    config = InsightsConfig()
    repo = InsightRepository(config.warehouse_dsn)
    
    stats = repo.get_stats()
    
    print("\n" + "=" * 60)
    print("INSIGHT STATISTICS")
    print("=" * 60)
    print(f"Total insights: {stats['total_insights']}")
    print(f"Unique properties: {stats['unique_properties']}")
    print(f"\nBy category:")
    print(f"  Risks: {stats['risk_count']}")
    print(f"  Opportunities: {stats['opportunity_count']}")
    print(f"\nBy status:")
    print(f"  New: {stats['new_count']}")
    print(f"  Diagnosed: {stats['diagnosed_count']}")
    print(f"\nSeverity:")
    print(f"  High: {stats['high_severity_count']}")
    print(f"\nTime range:")
    print(f"  Earliest: {stats['earliest_insight']}")
    print(f"  Latest: {stats['latest_insight']}")
    print("=" * 60)
    
    return 0


def cmd_cleanup(args):
    """Delete old resolved insights"""
    config = InsightsConfig()
    repo = InsightRepository(config.warehouse_dsn)
    
    deleted = repo.delete_old_insights(days=args.days)
    print(f"Deleted {deleted} insights older than {args.days} days")
    
    return 0


def cmd_dispatch(args):
    """Dispatch recent insights to configured channels"""
    from insights_core.dispatcher import InsightDispatcher
    
    config = InsightsConfig()
    
    # Add dry_run flag from args
    dispatcher_config = config.get_dispatcher_config()
    dispatcher_config['dry_run'] = args.dry_run
    
    dispatcher = InsightDispatcher(dispatcher_config)
    repo = InsightRepository(config.warehouse_dsn)
    
    stats = dispatcher.dispatch_recent_insights(repo, hours=args.hours, property=args.property)
    
    print("\n" + "=" * 60)
    print("DISPATCH SUMMARY")
    print("=" * 60)
    print(f"Insights processed: {stats['total_insights']}")
    print(f"Total dispatches: {stats['total_dispatches']}")
    print(f"Successes: {stats['successes']}")
    print(f"Failures: {stats['failures']}")
    print(f"Duration: {stats.get('duration_seconds', 0):.2f}s")
    
    if args.dry_run:
        print("\n[DRY RUN MODE - No actual messages sent]")
    
    print("=" * 60)
    
    return 0 if stats['failures'] == 0 else 1


def main():
    parser = argparse.ArgumentParser(description='Insight Engine CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # refresh-insights command
    refresh_parser = subparsers.add_parser('refresh-insights', help='Run all detectors')
    refresh_parser.add_argument('--property', type=str, help='Filter by property')
    refresh_parser.set_defaults(func=cmd_refresh)
    
    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show insight statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    # cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Delete old insights')
    cleanup_parser.add_argument('--days', type=int, default=90, help='Delete insights older than N days')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # dispatch-insights command
    dispatch_parser = subparsers.add_parser('dispatch-insights', help='Dispatch insights to channels')
    dispatch_parser.add_argument('--property', type=str, help='Filter by property')
    dispatch_parser.add_argument('--hours', type=int, default=24, help='Hours to look back')
    dispatch_parser.add_argument('--dry-run', action='store_true', help='Test routing without sending')
    dispatch_parser.set_defaults(func=cmd_dispatch)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except Exception as e:
        logger.error(f"Command failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
