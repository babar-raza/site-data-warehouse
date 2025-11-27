"""
GSC-Based SERP Tracking Celery Tasks
Uses existing GSC data for position tracking - completely free!
"""

import asyncio
import os
from celery import shared_task
from insights_core.gsc_serp_tracker import GSCBasedSerpTracker


@shared_task(name='sync_serp_from_gsc', bind=True, max_retries=3)
def sync_serp_from_gsc_task(self, property_url: str = 'all', min_impressions: int = 10):
    """
    Sync SERP position data from GSC to SERP tracking tables

    This task is FREE and runs without any API limits!

    Args:
        property_url: Property to sync, or 'all' for all properties
        min_impressions: Minimum impressions to track (default: 10)

    Usage:
        # Sync specific property
        celery -A services.tasks call sync_serp_from_gsc --args='["https://yourdomain.com"]'

        # Sync all properties
        celery -A services.tasks call sync_serp_from_gsc --args='["all"]'
    """
    try:
        tracker = GSCBasedSerpTracker()

        if property_url == 'all':
            # Get all properties from database
            import asyncpg
            async def get_properties():
                conn = await asyncpg.connect(os.getenv('WAREHOUSE_DSN'))
                rows = await conn.fetch("""
                    SELECT DISTINCT property FROM gsc.query_stats
                    WHERE data_date >= CURRENT_DATE - INTERVAL '7 days'
                """)
                await conn.close()
                return [row['property'] for row in rows]

            properties = asyncio.run(get_properties())
        else:
            properties = [property_url]

        results = []
        for prop in properties:
            result = asyncio.run(tracker.sync_positions_from_gsc(
                property_url=prop,
                min_impressions=min_impressions,
                days_back=30
            ))
            results.append(result)

        return {
            'success': True,
            'properties_synced': len(results),
            'total_queries': sum(r['queries_synced'] for r in results),
            'total_positions': sum(r['positions_synced'] for r in results),
            'results': results
        }

    except Exception as e:
        # Retry on failure
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@shared_task(name='detect_position_changes_gsc', bind=True)
def detect_position_changes_gsc_task(self, property_url: str, days: int = 7):
    """
    Detect position changes from GSC data and trigger alerts if needed

    Args:
        property_url: Property to check
        days: Number of days to analyze

    Usage:
        celery -A services.tasks call detect_position_changes_gsc --args='["https://yourdomain.com", 7]'
    """
    try:
        tracker = GSCBasedSerpTracker()

        # Get position changes
        changes = asyncio.run(tracker.get_position_changes(property_url, days=days))

        # Trigger alerts for significant changes
        significant_changes = [
            c for c in changes
            if abs(c['position_change']) >= 3  # 3+ position change
            and c['current_impressions'] > 100  # Has meaningful traffic
        ]

        if significant_changes:
            # You can integrate with alert manager here
            from notifications.alert_manager import AlertManager
            alert_manager = AlertManager()

            for change in significant_changes[:10]:  # Limit to top 10
                if change['position_change'] < 0:  # Position drop
                    asyncio.run(alert_manager.trigger_alert(
                        rule_id=None,  # Auto-detect rule
                        property=property_url,
                        page_path=change['page_path'],
                        title=f"Position Drop: {change['query_text']}",
                        message=f"Position dropped from {change['previous_position']:.1f} to {change['current_position']:.1f}",
                        metadata={'change': dict(change)}
                    ))

        return {
            'success': True,
            'total_changes': len(changes),
            'significant_changes': len(significant_changes),
            'alerts_triggered': len(significant_changes),
            'changes': changes[:20]  # Return top 20
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


@shared_task(name='analyze_keyword_opportunities_gsc')
def analyze_keyword_opportunities_gsc_task(property_url: str):
    """
    Analyze keyword opportunities from GSC data (ranking 11-20)

    Args:
        property_url: Property to analyze

    Usage:
        celery -A services.tasks call analyze_keyword_opportunities_gsc --args='["https://yourdomain.com"]'
    """
    try:
        tracker = GSCBasedSerpTracker()

        # Get opportunity keywords (ranking 11-20)
        opportunities = asyncio.run(tracker.get_opportunity_keywords(
            property_url,
            position_min=11,
            position_max=20,
            days=30
        ))

        # Get top ranking keywords (1-10)
        top_keywords = asyncio.run(tracker.get_top_ranking_keywords(
            property_url,
            position_max=10,
            days=30
        ))

        return {
            'success': True,
            'property': property_url,
            'opportunity_count': len(opportunities),
            'top_keywords_count': len(top_keywords),
            'total_opportunity_clicks': sum(int(o.get('potential_gain', 0)) for o in opportunities),
            'top_opportunities': opportunities[:20],
            'top_keywords': top_keywords[:20]
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


# Schedule these tasks in Celery Beat
def setup_gsc_serp_schedules(sender, **kwargs):
    """
    Setup scheduled tasks for GSC-based SERP tracking

    Add this to your Celery beat schedule:
    """
    from celery.schedules import crontab

    sender.add_periodic_task(
        crontab(hour=9, minute=0),  # Daily at 9 AM
        sync_serp_from_gsc_task.s('all', 10),
        name='Daily GSC SERP Sync'
    )

    sender.add_periodic_task(
        crontab(hour=10, minute=0),  # Daily at 10 AM
        detect_position_changes_gsc_task.s('all', 7),
        name='Daily Position Change Detection'
    )

    sender.add_periodic_task(
        crontab(hour=0, minute=0, day_of_week=1),  # Monday midnight
        analyze_keyword_opportunities_gsc_task.s('all'),
        name='Weekly Keyword Opportunity Analysis'
    )
