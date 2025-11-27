#!/usr/bin/env python3
"""
Sync GSC Data to SERP Tracking Tables
======================================

One-time script to populate SERP tracking tables from existing GSC data.
Run this after GSC data collection is working.

This enables SERP position tracking WITHOUT any API keys!
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from insights_core.gsc_serp_tracker import GSCBasedSerpTracker
from dotenv import load_dotenv

load_dotenv()


async def main():
    """Main sync function"""

    print("=" * 60)
    print("GSC to SERP Data Sync")
    print("=" * 60)
    print()
    print("This script will:")
    print("1. Extract position data from your existing GSC data")
    print("2. Populate SERP tracking tables (serp.queries, serp.position_history)")
    print("3. Enable position tracking dashboards")
    print()
    print("✓ Completely FREE - no API keys needed")
    print("✓ Uses your existing GSC data")
    print("✓ No rate limits")
    print()

    # Get property URL
    property_url = os.getenv('GSC_PROPERTIES', '').split(',')[0]

    if not property_url:
        print("ERROR: GSC_PROPERTIES not set in .env file")
        print("Please set GSC_PROPERTIES=https://yourdomain.com")
        sys.exit(1)

    print(f"Property: {property_url}")
    print()

    # Configuration
    min_impressions = int(input("Minimum impressions to track (default 10): ") or "10")
    days_back = int(input("Days of history to sync (default 30): ") or "30")

    print()
    print("Starting sync...")
    print()

    tracker = GSCBasedSerpTracker()

    try:
        # Sync data
        result = await tracker.sync_positions_from_gsc(
            property_url=property_url,
            min_impressions=min_impressions,
            days_back=days_back
        )

        # Print results
        print("=" * 60)
        print("✓ Sync Complete!")
        print("=" * 60)
        print()
        print(f"Queries Synced:    {result['queries_synced']}")
        print(f"Positions Synced:  {result['positions_synced']}")
        print(f"Data Source:       {result['data_source']}")
        print()

        # Show top ranking keywords
        print("Top 10 Ranking Keywords:")
        print("-" * 60)

        top_keywords = await tracker.get_top_ranking_keywords(property_url, position_max=10, days=7)

        for i, kw in enumerate(top_keywords[:10], 1):
            print(f"{i}. Position #{kw['avg_position']:.1f}: {kw['query_text']}")
            print(f"   {kw['total_clicks']} clicks, {kw['total_impressions']} impressions")
            print()

        # Show position changes
        print("\nRecent Position Changes (last 7 days):")
        print("-" * 60)

        changes = await tracker.get_position_changes(property_url, days=7)

        if changes:
            for change in changes[:10]:
                direction = "📈" if change['position_change'] > 0 else "📉"
                print(f"{direction} {change['query_text']}")
                print(f"   {change['previous_position']:.1f} → {change['current_position']:.1f} "
                      f"({change['position_change']:+.1f})")
                print()
        else:
            print("No significant position changes detected")
            print()

        # Show opportunities
        print("\nKeyword Opportunities (Ranking 11-20):")
        print("-" * 60)

        opportunities = await tracker.get_opportunity_keywords(property_url)

        if opportunities:
            for opp in opportunities[:10]:
                print(f"Position #{opp['avg_position']:.1f}: {opp['query_text']}")
                print(f"   Potential gain: +{opp['potential_gain']} clicks/month")
                print()
        else:
            print("No opportunities found in position 11-20 range")
            print()

        print("=" * 60)
        print("Next Steps:")
        print("=" * 60)
        print()
        print("1. View SERP Position Tracking dashboard in Grafana:")
        print("   http://localhost:3000/d/serp-tracking")
        print()
        print("2. Set up automated daily sync:")
        print("   Add to Celery Beat schedule (already configured)")
        print()
        print("3. Configure alerts for position drops:")
        print("   python scripts/setup/seed_data.py")
        print()
        print("✓ SERP tracking now enabled using FREE GSC data!")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
