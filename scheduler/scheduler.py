#!/usr/bin/env python3
"""
GSC Warehouse Scheduler - API-Only Mode
Orchestrates API ingestion, transforms, insights, and maintenance tasks

Schedules:
- Daily: API ingestion, transforms, insights refresh, watermark advancement
- Weekly: Reconciliation (re-check last 7 days via API), cannibalization refresh

Version: 2.0 (Added insights refresh)
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configure logging
log_handlers = [logging.StreamHandler(sys.stdout)]
log_dir = '/logs' if os.name != 'nt' else 'logs'
log_file = os.path.join(log_dir, 'scheduler.log')

# Only add file handler if the log directory exists or can be created
try:
    os.makedirs(log_dir, exist_ok=True)
    log_handlers.append(logging.FileHandler(log_file))
except (OSError, PermissionError):
    pass  # Fall back to console only

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger(__name__)

# Configuration
WAREHOUSE_DSN = os.environ.get('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')
METRICS_FILE = os.path.join(log_dir, 'scheduler_metrics.json')

# Metrics tracking
metrics = {
    'last_daily_run': None,
    'last_weekly_run': None,
    'daily_runs_count': 0,
    'weekly_runs_count': 0,
    'last_error': None,
    'tasks': {}
}

def update_metrics(task_name, status, duration=None, error=None, extra=None):
    """Update metrics for tracking"""
    metrics['tasks'][task_name] = {
        'last_run': datetime.utcnow().isoformat(),
        'status': status,
        'duration_seconds': duration,
        'error': str(error) if error else None
    }
    
    # Add extra metrics if provided
    if extra:
        metrics['tasks'][task_name].update(extra)
    
    # Save metrics to file
    try:
        with open(METRICS_FILE, 'w') as f:
            json.dump(metrics, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save metrics: {e}")

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(WAREHOUSE_DSN)

def run_command(cmd, task_name):
    """Run a shell command and track metrics"""
    start_time = time.time()
    logger.info(f"Starting task: {task_name}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        duration = time.time() - start_time
        logger.info(f"Task {task_name} completed in {duration:.2f}s")
        logger.debug(f"Output: {result.stdout}")
        update_metrics(task_name, 'success', duration)
        return True
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        logger.error(f"Task {task_name} failed after {duration:.2f}s")
        logger.error(f"Error: {e.stderr}")
        update_metrics(task_name, 'failed', duration, e.stderr)
        metrics['last_error'] = {
            'task': task_name,
            'timestamp': datetime.utcnow().isoformat(),
            'error': e.stderr
        }
        return False
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Task {task_name} error: {e}")
        update_metrics(task_name, 'error', duration, str(e))
        return False

def check_warehouse_health():
    """Check if warehouse is healthy before running tasks"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        logger.info("Warehouse health check: OK")
        return True
    except Exception as e:
        logger.error(f"Warehouse health check failed: {e}")
        return False

def run_api_ingestion():
    """Run Search Console API ingestion"""
    if not check_warehouse_health():
        logger.warning("Skipping API ingestion - warehouse not healthy")
        return False

    return run_command(
        ['python', '/app/ingestors/api/gsc_api_ingestor.py'],
        'api_ingestion'
    )

def run_ga4_collection():
    """Run Google Analytics 4 data collection"""
    if not check_warehouse_health():
        logger.warning("Skipping GA4 collection - warehouse not healthy")
        return False

    return run_command(
        ['python', '/app/ingestors/ga4/ga4_extractor.py'],
        'ga4_collection'
    )

def run_serp_collection():
    """Run SERP position tracking"""
    if not check_warehouse_health():
        logger.warning("Skipping SERP collection - warehouse not healthy")
        return False

    # Check if API key is configured
    if not os.environ.get('SERPSTACK_API_KEY'):
        logger.warning("SERPSTACK_API_KEY not configured - skipping SERP collection")
        update_metrics('serp_collection', 'skipped', error='API key not configured')
        return True  # Return True so pipeline doesn't fail

    return run_command(
        ['python', '/app/scripts/collect_serp_data.py'],
        'serp_collection'
    )

def run_gsc_serp_sync():
    """
    Sync SERP position data from GSC to SERP tracking tables

    This runs AFTER GSC ingestion to populate SERP tracking tables with
    position data extracted from Google Search Console. Completely free -
    no API calls required.

    Non-blocking: failure doesn't affect rest of pipeline.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting GSC SERP sync...")
    logger.info("=" * 60)

    if not check_warehouse_health():
        logger.warning("Skipping GSC SERP sync - warehouse not healthy")
        update_metrics('gsc_serp_sync', 'skipped', error='Warehouse unhealthy')
        return False

    try:
        # Import here to avoid circular dependencies
        from insights_core.gsc_serp_tracker import sync_all_properties

        # Sync positions from GSC data for all properties
        results = sync_all_properties(min_impressions=10, days_back=7)

        # Calculate duration
        duration = time.time() - start_time

        # Calculate totals
        total_queries = sum(r.get('queries_synced', 0) for r in results if r.get('success'))
        total_positions = sum(r.get('positions_synced', 0) for r in results if r.get('success'))
        failed_count = sum(1 for r in results if not r.get('success'))

        # Log results
        logger.info("=" * 60)
        logger.info(f"GSC SERP sync completed in {duration:.2f}s")
        logger.info(f"Properties processed: {len(results)}")
        logger.info(f"Queries synced: {total_queries}")
        logger.info(f"Positions synced: {total_positions}")
        logger.info(f"Failed: {failed_count}")

        if results:
            logger.info("Breakdown by property:")
            for result in results:
                if result.get('success'):
                    logger.info(f"  {result['property']}: {result['queries_synced']} queries, "
                               f"{result['positions_synced']} positions")
                else:
                    logger.error(f"  {result['property']}: FAILED - {result.get('error', 'Unknown error')}")

        logger.info("=" * 60)

        # Update metrics
        update_metrics(
            'gsc_serp_sync',
            'success',
            duration,
            extra={
                'properties_processed': len(results),
                'queries_synced': total_queries,
                'positions_synced': total_positions,
                'failed_properties': failed_count
            }
        )

        return True

    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Failed to import GSCBasedSerpTracker: {e}")
        logger.error("Make sure insights_core.gsc_serp_tracker is installed")
        update_metrics('gsc_serp_sync', 'failed', duration, str(e))
        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"GSC SERP sync failed: {e}", exc_info=True)
        update_metrics('gsc_serp_sync', 'failed', duration, str(e))
        return False


def run_cwv_collection():
    """Run Core Web Vitals monitoring"""
    if not check_warehouse_health():
        logger.warning("Skipping CWV collection - warehouse not healthy")
        return False

    # Check if API key is configured
    if not os.environ.get('PAGESPEED_API_KEY'):
        logger.warning("PAGESPEED_API_KEY not configured - skipping CWV collection")
        update_metrics('cwv_collection', 'skipped', error='API key not configured')
        return True  # Return True so pipeline doesn't fail

    return run_command(
        ['python', '/app/scripts/collect_cwv_data.py'],
        'cwv_collection'
    )

def run_transforms():
    """Apply SQL transforms to create views"""
    if not check_warehouse_health():
        logger.warning("Skipping transforms - warehouse not healthy")
        return False

    return run_command(
        ['python', '/app/transform/apply_transforms.py'],
        'transforms'
    )

def run_trends_collection():
    """
    Run Google Trends data collection for tracked keywords

    Collects interest over time and related queries for top GSC keywords.
    Non-blocking: failure doesn't affect rest of pipeline.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting trends collection...")
    logger.info("=" * 60)

    try:
        # Import here to avoid circular dependencies
        from ingestors.trends.trends_accumulator import TrendsAccumulator

        # Initialize accumulator
        accumulator = TrendsAccumulator(db_dsn=WAREHOUSE_DSN)

        # Collect for all properties
        results = accumulator.collect_all_properties()

        # Calculate duration
        duration = time.time() - start_time

        # Calculate totals
        total_keywords = sum(r.get('keywords_collected', 0) for r in results)
        total_failed = sum(r.get('keywords_failed', 0) for r in results)
        total_related = sum(r.get('related_queries_collected', 0) for r in results)

        # Log results
        logger.info("=" * 60)
        logger.info(f"Trends collection completed in {duration:.2f}s")
        logger.info(f"Properties processed: {len(results)}")
        logger.info(f"Keywords collected: {total_keywords}")
        logger.info(f"Keywords failed: {total_failed}")
        logger.info(f"Related queries: {total_related}")

        if results:
            logger.info("Breakdown by property:")
            for result in results:
                logger.info(f"  {result['property']}: {result['keywords_collected']} keywords")

        logger.info("=" * 60)

        # Update metrics
        update_metrics(
            'trends_collection',
            'success',
            duration,
            extra={
                'properties_processed': len(results),
                'keywords_collected': total_keywords,
                'keywords_failed': total_failed,
                'related_queries_collected': total_related
            }
        )

        return True

    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Failed to import TrendsAccumulator: {e}")
        logger.error("Make sure ingestors.trends package is installed")
        update_metrics('trends_collection', 'failed', duration, str(e))
        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Trends collection failed: {e}", exc_info=True)
        update_metrics('trends_collection', 'failed', duration, str(e))
        return False

def run_insights_refresh():
    """
    Run InsightEngine to generate insights from latest data
    
    This runs AFTER transforms to ensure insights are based on fresh data.
    Failure in insights doesn't block rest of pipeline (non-blocking).
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting insights refresh...")
    logger.info("=" * 60)
    
    try:
        # Import here to avoid circular dependencies
        from insights_core.engine import InsightEngine
        from insights_core.config import InsightsConfig
        
        # Initialize engine
        config = InsightsConfig()
        engine = InsightEngine(config)
        
        # Run all detectors
        stats = engine.refresh()
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log results
        logger.info("=" * 60)
        logger.info(f"Insights refresh completed in {duration:.2f}s")
        logger.info(f"Total insights created: {stats['total_insights_created']}")
        logger.info(f"Detectors succeeded: {stats['detectors_succeeded']}/{stats['detectors_run']}")
        
        if stats.get('insights_by_detector'):
            logger.info("Breakdown by detector:")
            for detector, count in stats['insights_by_detector'].items():
                logger.info(f"  {detector}: {count} insights")
        
        if stats.get('errors'):
            logger.warning(f"Errors encountered: {len(stats['errors'])}")
            for error in stats['errors']:
                logger.error(f"  {error['detector']}: {error['error']}")
        
        logger.info("=" * 60)
        
        # Update metrics with detailed stats
        update_metrics(
            'insights_refresh',
            'success',
            duration,
            extra={
                'insights_created': stats['total_insights_created'],
                'detectors_run': stats['detectors_run'],
                'detectors_succeeded': stats['detectors_succeeded'],
                'detectors_failed': stats['detectors_failed']
            }
        )
        
        return True
        
    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Failed to import InsightEngine: {e}")
        logger.error("Make sure insights_core package is installed")
        update_metrics('insights_refresh', 'failed', duration, str(e))
        return False
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Insights refresh failed: {e}", exc_info=True)
        update_metrics('insights_refresh', 'failed', duration, str(e))
        return False

def check_watermarks():
    """Check and log watermark status"""
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT property, source_type, last_date, 
                       CURRENT_DATE - last_date as days_behind
                FROM ingest_watermarks
                ORDER BY last_date DESC
            """)
            watermarks = cur.fetchall()
        conn.close()
        
        logger.info(f"Watermark status: {len(watermarks)} properties tracked")
        for wm in watermarks:
            logger.info(f"  {wm['property']} ({wm['source_type']}): {wm['last_date']} ({wm['days_behind']} days behind)")
        
        update_metrics('watermark_check', 'success')
        return True
    except Exception as e:
        logger.error(f"Failed to check watermarks: {e}")
        update_metrics('watermark_check', 'failed', error=str(e))
        return False

def reconcile_watermarks():
    """
    Reconcile watermarks that are ahead of actual data in fact table.

    This fixes gaps where watermarks advanced (e.g., due to GSC data delay)
    but no actual data was inserted. Resets watermarks to match the actual
    maximum date in the fact table, allowing the ingestor to retry those dates.

    Returns:
        True if reconciliation succeeded, False otherwise
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting watermark reconciliation...")
    logger.info("=" * 60)

    if not check_warehouse_health():
        logger.warning("Skipping watermark reconciliation - warehouse not healthy")
        update_metrics('watermark_reconciliation', 'skipped', error='Warehouse unhealthy')
        return False

    try:
        conn = get_db_connection()

        # First, identify watermarks that are ahead of actual data
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    w.property,
                    w.source_type,
                    w.last_date as watermark_date,
                    COALESCE(f.max_date, '2025-01-01'::date) as fact_max_date,
                    w.last_date - COALESCE(f.max_date, '2025-01-01'::date) as gap_days
                FROM gsc.ingest_watermarks w
                LEFT JOIN (
                    SELECT property, MAX(date) as max_date
                    FROM gsc.fact_gsc_daily
                    GROUP BY property
                ) f ON w.property = f.property
                WHERE w.source_type = 'api'
                  AND w.last_date > COALESCE(f.max_date, '2025-01-01'::date)
                ORDER BY gap_days DESC
            """)
            gaps = cur.fetchall()

        if not gaps:
            logger.info("No watermark gaps detected - all watermarks aligned with fact data")
            update_metrics('watermark_reconciliation', 'success', time.time() - start_time,
                          extra={'properties_reconciled': 0, 'gaps_found': 0})
            conn.close()
            return True

        logger.warning(f"Found {len(gaps)} properties with watermark gaps:")
        for gap in gaps:
            logger.warning(
                f"  {gap['property']}: watermark={gap['watermark_date']}, "
                f"fact_max={gap['fact_max_date']}, gap={gap['gap_days']} days"
            )

        # Reset watermarks to match actual data
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE gsc.ingest_watermarks w
                SET
                    last_date = COALESCE(f.max_date, '2025-01-01'::date),
                    last_run_status = 'reconciled',
                    updated_at = CURRENT_TIMESTAMP
                FROM (
                    SELECT property, MAX(date) as max_date
                    FROM gsc.fact_gsc_daily
                    GROUP BY property
                ) f
                WHERE w.property = f.property
                  AND w.source_type = 'api'
                  AND w.last_date > f.max_date
            """)
            reconciled_count = cur.rowcount
            conn.commit()

        conn.close()

        duration = time.time() - start_time

        logger.info("=" * 60)
        logger.info(f"Watermark reconciliation completed in {duration:.2f}s")
        logger.info(f"Properties reconciled: {reconciled_count}")
        logger.info("Watermarks reset to match actual fact table data")
        logger.info("Next ingestion run will retry the missing dates")
        logger.info("=" * 60)

        update_metrics(
            'watermark_reconciliation',
            'success',
            duration,
            extra={
                'properties_reconciled': reconciled_count,
                'gaps_found': len(gaps),
                'max_gap_days': max(g['gap_days'] for g in gaps) if gaps else 0
            }
        )

        return True

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Watermark reconciliation failed: {e}", exc_info=True)
        update_metrics('watermark_reconciliation', 'failed', duration, str(e))
        return False

def reconcile_recent_data():
    """Reconcile last 7 days of data (weekly maintenance) - API-only mode"""
    logger.info("Starting weekly reconciliation of last 7 days via API")
    
    # Re-run API ingestion to get fresh data for last 7 days
    if not check_warehouse_health():
        logger.warning("Skipping reconciliation - warehouse not healthy")
        return False
    
    # API ingestion will naturally refresh recent data
    api_success = run_command(
        ['python', '/app/ingestors/api/gsc_api_ingestor.py'],
        'api_reconciliation'
    )
    
    if not api_success:
        logger.error("API reconciliation failed")
        update_metrics('reconciliation', 'failed', error="API ingestion failed")
        return False
    
    # Get stats after reconciliation
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Get count of rows in last 7 days
            cur.execute("""
                SELECT COUNT(*) as row_count,
                       COUNT(DISTINCT property) as property_count,
                       MIN(date) as earliest_date,
                       MAX(date) as latest_date
                FROM fact_gsc_daily
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            stats = cur.fetchone()
        conn.close()
        
        logger.info(f"Recent data stats: {stats[0]} rows, {stats[1]} properties, {stats[2]} to {stats[3]}")
        update_metrics('reconciliation', 'success')
        return True
    except Exception as e:
        logger.error(f"Reconciliation stats failed: {e}")
        update_metrics('reconciliation', 'failed', error=str(e))
        return False

def refresh_cannibalization_analysis():
    """Refresh cannibalization analysis (weekly)"""
    logger.info("Refreshing cannibalization analysis")

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Could create a materialized view refresh here
            # For now, just validate the view exists
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.views
                WHERE table_name = 'vw_query_winners_losers_28d_vs_prev'
            """)
            exists = cur.fetchone()[0]
        conn.close()

        if exists:
            logger.info("Cannibalization view validated")
            update_metrics('cannibalization_refresh', 'success')
            return True
        else:
            logger.warning("Cannibalization view not found")
            update_metrics('cannibalization_refresh', 'warning', error="View not found")
            return False
    except Exception as e:
        logger.error(f"Cannibalization refresh failed: {e}")
        update_metrics('cannibalization_refresh', 'failed', error=str(e))
        return False

def run_hugo_sync():
    """
    Sync Hugo content to database (daily)

    Tracks content changes from Hugo CMS and correlates with performance data.
    Helps identify how content updates affect search performance.
    Non-blocking: failure doesn't affect rest of pipeline.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting Hugo content sync...")
    logger.info("=" * 60)

    # Check if Hugo path is configured
    hugo_path = os.environ.get('HUGO_CONTENT_PATH')

    if not hugo_path:
        logger.info("HUGO_CONTENT_PATH not configured - skipping Hugo sync")
        update_metrics('hugo_sync', 'skipped', time.time() - start_time,
                      error='Hugo path not configured')
        return True  # Return True so pipeline doesn't fail

    try:
        # Import HugoContentTracker
        try:
            from services.hugo_sync import HugoContentTracker
        except ImportError as e:
            logger.error(f"Failed to import HugoContentTracker: {e}")
            logger.error("Hugo sync requires services.hugo_sync package")
            update_metrics('hugo_sync', 'failed', time.time() - start_time, str(e))
            return False

        # Initialize tracker
        tracker = HugoContentTracker(hugo_path)

        # Perform sync
        logger.info(f"Syncing Hugo content from: {hugo_path}")
        stats = tracker.sync()

        duration = time.time() - start_time

        # Log results
        logger.info("=" * 60)
        logger.info(f"Hugo sync completed in {duration:.2f}s")
        logger.info(f"Created: {stats.get('created', 0)}")
        logger.info(f"Updated: {stats.get('updated', 0)}")
        logger.info(f"Deleted: {stats.get('deleted', 0)}")
        logger.info(f"Unchanged: {stats.get('unchanged', 0)}")

        if stats.get('errors', 0) > 0:
            logger.warning(f"Errors: {stats['errors']}")

        logger.info("=" * 60)

        # Update metrics
        update_metrics(
            'hugo_sync',
            'success',
            duration,
            extra={
                'created': stats.get('created', 0),
                'updated': stats.get('updated', 0),
                'deleted': stats.get('deleted', 0),
                'unchanged': stats.get('unchanged', 0),
                'errors': stats.get('errors', 0)
            }
        )

        return True

    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Import error in Hugo sync: {e}")
        logger.error("Make sure services.hugo_sync package is installed")
        update_metrics('hugo_sync', 'failed', duration, str(e))
        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Hugo sync failed: {e}", exc_info=True)
        update_metrics('hugo_sync', 'failed', duration, str(e))
        return False

def run_content_action_execution():
    """
    Execute approved content optimization actions (daily)

    Processes pending actions with status='approved' (pre-approved by user)
    and executes them using the HugoContentWriter service.

    Actions must be explicitly approved before they can be auto-executed.
    Non-blocking: failure doesn't affect rest of pipeline.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting content action execution...")
    logger.info("=" * 60)

    # Check if Hugo path is configured
    hugo_path = os.environ.get('HUGO_CONTENT_PATH')
    if not hugo_path:
        logger.info("HUGO_CONTENT_PATH not configured - skipping action execution")
        update_metrics('content_action_execution', 'skipped', time.time() - start_time,
                      error='Hugo path not configured')
        return True  # Return True so pipeline doesn't fail

    try:
        # Import required modules
        from config.hugo_config import HugoConfig
        from services.hugo_content_writer import HugoContentWriter

        # Get approved pending actions
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get actions with status='approved' (explicitly approved for auto-execution)
            cur.execute("""
                SELECT id, property, action_type, title, priority
                FROM gsc.actions
                WHERE status = 'approved'
                ORDER BY
                    CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    created_at ASC
                LIMIT 10
            """)
            actions_to_execute = cur.fetchall()

        if not actions_to_execute:
            logger.info("No approved actions to execute at this time")
            update_metrics('content_action_execution', 'success', time.time() - start_time,
                          extra={'actions_executed': 0, 'actions_failed': 0})
            conn.close()
            return True

        logger.info(f"Found {len(actions_to_execute)} approved actions to execute")

        # Initialize writer
        config = HugoConfig.from_env()

        if not config.is_configured():
            logger.error("Hugo config invalid - skipping action execution")
            update_metrics('content_action_execution', 'failed', time.time() - start_time,
                          error='Hugo config invalid')
            conn.close()
            return False

        validation_error = config.validate_path()
        if validation_error:
            logger.error(f"Hugo path validation failed: {validation_error}")
            update_metrics('content_action_execution', 'failed', time.time() - start_time,
                          error=validation_error)
            conn.close()
            return False

        ollama_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        ollama_model = os.environ.get('OLLAMA_MODEL', 'llama3.1')

        writer = HugoContentWriter(
            config=config,
            db_connection=conn,
            ollama_base_url=ollama_url,
            ollama_model=ollama_model
        )

        # Execute actions
        actions_executed = 0
        actions_failed = 0

        for action in actions_to_execute:
            action_id = str(action['id'])
            try:
                logger.info(f"Executing action: {action['title']} ({action_id})")
                result = writer.execute_action(action_id)

                if result.get('success'):
                    actions_executed += 1
                    logger.info(f"  [SUCCESS] {action['title']}")
                    if result.get('changes_made'):
                        for change in result['changes_made']:
                            logger.info(f"    - {change}")
                else:
                    actions_failed += 1
                    logger.error(f"  [FAILED] {action['title']}: {result.get('error')}")

            except Exception as e:
                actions_failed += 1
                logger.error(f"  [ERROR] {action['title']}: {e}")
                continue

            # Small delay between actions
            time.sleep(2)

        conn.close()

        duration = time.time() - start_time

        logger.info("=" * 60)
        logger.info(f"Content action execution completed in {duration:.2f}s")
        logger.info(f"Actions executed: {actions_executed}")
        logger.info(f"Actions failed: {actions_failed}")
        logger.info("=" * 60)

        update_metrics(
            'content_action_execution',
            'success',
            duration,
            extra={
                'actions_executed': actions_executed,
                'actions_failed': actions_failed,
                'total_actions': len(actions_to_execute)
            }
        )

        return True

    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Import error in content action execution: {e}")
        logger.error("Make sure config and services packages are installed")
        update_metrics('content_action_execution', 'failed', duration, str(e))
        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Content action execution failed: {e}", exc_info=True)
        update_metrics('content_action_execution', 'failed', duration, str(e))
        return False


def run_content_analysis():
    """
    Run content analysis for pages that need quality assessment (weekly)

    Analyzes content using ContentAnalyzer to populate content.page_snapshots
    with flesch_reading_ease, word_count, and other quality metrics needed by
    ContentQualityDetector.

    Targets pages with recent traffic but missing content analysis data.
    Non-blocking: failure doesn't affect rest of pipeline.
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting content analysis...")
    logger.info("=" * 60)

    try:
        # Get pages that need analysis (top pages by clicks, missing recent snapshots)
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                WITH top_pages AS (
                    SELECT
                        property,
                        page_path,
                        SUM(gsc_clicks) as total_clicks
                    FROM gsc.vw_unified_page_performance
                    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY property, page_path
                    HAVING SUM(gsc_clicks) > 10
                    ORDER BY SUM(gsc_clicks) DESC
                    LIMIT 100
                )
                SELECT
                    t.property,
                    t.page_path,
                    t.total_clicks,
                    COALESCE(s.snapshot_date, '1900-01-01'::date) as last_analyzed
                FROM top_pages t
                LEFT JOIN LATERAL (
                    SELECT snapshot_date
                    FROM content.page_snapshots
                    WHERE property = t.property
                      AND page_path = t.page_path
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                ) s ON true
                WHERE COALESCE(s.snapshot_date, '1900-01-01'::date) < CURRENT_DATE - INTERVAL '7 days'
                ORDER BY t.total_clicks DESC
                LIMIT 50
            """)
            pages_to_analyze = cur.fetchall()
        conn.close()

        if not pages_to_analyze:
            logger.info("No pages need content analysis at this time")
            update_metrics('content_analysis', 'success', time.time() - start_time,
                          extra={'pages_analyzed': 0})
            return True

        logger.info(f"Found {len(pages_to_analyze)} pages needing content analysis")

        # Import ContentAnalyzer
        try:
            from insights_core.content_analyzer import ContentAnalyzer
        except ImportError as e:
            logger.error(f"Failed to import ContentAnalyzer: {e}")
            logger.error("Content analysis requires insights_core package")
            update_metrics('content_analysis', 'failed', time.time() - start_time, str(e))
            return False

        # Initialize analyzer
        analyzer = ContentAnalyzer(db_dsn=WAREHOUSE_DSN)

        # Analyze each page
        pages_analyzed = 0
        pages_failed = 0

        for page in pages_to_analyze:
            try:
                property_url = page['property']
                page_path = page['page_path']
                full_url = f"{property_url}{page_path}"

                logger.info(f"Analyzing: {full_url}")

                # Fetch HTML and analyze
                import httpx
                import asyncio

                async def fetch_and_analyze():
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        response = await client.get(full_url)
                        html_content = response.text
                        return await analyzer.analyze(property_url, page_path, html_content)

                # Run async analysis
                result = asyncio.run(fetch_and_analyze())

                if result.get('success'):
                    pages_analyzed += 1
                    logger.info(f"Successfully analyzed {full_url}")
                else:
                    pages_failed += 1
                    logger.warning(f"Analysis failed for {full_url}: {result.get('error')}")

                # Small delay to avoid overwhelming target servers
                time.sleep(1)

            except Exception as e:
                pages_failed += 1
                logger.error(f"Error analyzing {page.get('page_path', 'unknown')}: {e}")
                continue

        # Close analyzer connections
        import asyncio
        asyncio.run(analyzer.close())

        duration = time.time() - start_time

        logger.info("=" * 60)
        logger.info(f"Content analysis completed in {duration:.2f}s")
        logger.info(f"Pages analyzed: {pages_analyzed}")
        logger.info(f"Pages failed: {pages_failed}")
        logger.info("=" * 60)

        update_metrics(
            'content_analysis',
            'success',
            duration,
            extra={
                'pages_analyzed': pages_analyzed,
                'pages_failed': pages_failed,
                'total_pages': len(pages_to_analyze)
            }
        )

        return True

    except ImportError as e:
        duration = time.time() - start_time
        logger.error(f"Import error in content analysis: {e}")
        logger.error("Make sure insights_core and required dependencies are installed")
        update_metrics('content_analysis', 'failed', duration, str(e))
        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Content analysis failed: {e}", exc_info=True)
        update_metrics('content_analysis', 'failed', duration, str(e))
        return False

def daily_pipeline():
    """
    Run daily pipeline: API ingestion, transforms, insights (API-ONLY MODE)

    Sequence:
    1. API Ingestion (GSC data)
    2. GA4 Collection
    3. SERP Collection (API-based - SerpStack/ValueSERP/SerpAPI)
    4. GSC SERP Sync (free position tracking from GSC data)
    5. CWV Collection
    6. SQL Transforms (refresh views with new data)
    7. Insights Refresh (generate insights from fresh data)
    8. Hugo Sync (track content changes)
    9. Content Action Execution
    10. Trends Collection (collect Google Trends data)
    11. Watermark Check

    Insights, Hugo sync, GSC SERP sync, and Trends collection failures are non-blocking.
    """
    logger.info("=" * 60)
    logger.info("Starting DAILY pipeline - API-ONLY MODE")
    logger.info("=" * 60)

    start_time = datetime.utcnow()

    # Run tasks in sequence - BQ Extraction DISABLED for API-only mode
    tasks = [
        # ('BQ Extraction', run_bq_extraction),  # DISABLED - API-only mode
        ('API Ingestion', run_api_ingestion),
        ('GA4 Collection', run_ga4_collection),
        ('SERP Collection', run_serp_collection),
        ('CWV Collection', run_cwv_collection),
        ('SQL Transforms', run_transforms),
    ]

    results = {}
    for task_name, task_func in tasks:
        logger.info(f"\n--- {task_name} ---")
        results[task_name] = task_func()
        time.sleep(2)  # Small delay between tasks

    # Run GSC SERP sync (non-blocking - syncs position data from GSC)
    # This runs AFTER GSC ingestion to use fresh GSC data
    logger.info(f"\n--- GSC SERP Sync ---")
    gsc_serp_success = run_gsc_serp_sync()
    if not gsc_serp_success:
        logger.error("GSC SERP sync failed, but continuing pipeline...")
        logger.info("Pipeline will continue - GSC SERP sync is non-blocking")
    results['GSC SERP Sync'] = gsc_serp_success
    time.sleep(2)

    # Run insights refresh (non-blocking - failure doesn't affect pipeline status)
    logger.info(f"\n--- Insights Refresh ---")
    insights_success = run_insights_refresh()
    if not insights_success:
        logger.error("Insights refresh failed, but continuing pipeline...")
        logger.info("Pipeline will continue - insights are non-blocking")
    results['Insights Refresh'] = insights_success
    time.sleep(2)

    # Run Hugo sync (non-blocking - failure doesn't affect pipeline status)
    logger.info(f"\n--- Hugo Content Sync ---")
    hugo_success = run_hugo_sync()
    if not hugo_success:
        logger.error("Hugo sync failed, but continuing pipeline...")
        logger.info("Pipeline will continue - Hugo sync is non-blocking")
    results['Hugo Sync'] = hugo_success
    time.sleep(2)

    # Run content action execution (non-blocking - processes approved actions)
    logger.info(f"\n--- Content Action Execution ---")
    action_success = run_content_action_execution()
    if not action_success:
        logger.error("Content action execution failed, but continuing pipeline...")
        logger.info("Pipeline will continue - action execution is non-blocking")
    results['Content Action Execution'] = action_success
    time.sleep(2)

    # Run Trends collection (non-blocking - failure doesn't affect pipeline status)
    logger.info(f"\n--- Trends Collection ---")
    trends_success = run_trends_collection()
    if not trends_success:
        logger.error("Trends collection failed, but continuing pipeline...")
        logger.info("Pipeline will continue - trends collection is non-blocking")
    results['Trends Collection'] = trends_success
    time.sleep(2)

    # Watermark check
    logger.info(f"\n--- Watermark Check ---")
    results['Watermark Check'] = check_watermarks()
    
    # Update metrics
    metrics['last_daily_run'] = datetime.utcnow().isoformat()
    metrics['daily_runs_count'] += 1
    
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    # Count critical tasks only (not insights, not watermark check)
    # Note: SERP and CWV are non-critical (they gracefully skip if API keys not configured)
    critical_tasks = ['API Ingestion', 'GA4 Collection', 'SQL Transforms']
    critical_success = sum(1 for task in critical_tasks if results.get(task, False))
    
    logger.info("=" * 60)
    logger.info(f"DAILY pipeline completed: {sum(1 for v in results.values() if v)}/{len(results)} tasks successful")
    logger.info(f"Critical tasks: {critical_success}/{len(critical_tasks)} successful")
    logger.info(f"Duration: {duration:.2f}s")
    logger.info("=" * 60)
    
    # Return True if critical tasks succeeded (insights can fail without failing pipeline)
    return critical_success == len(critical_tasks)

def weekly_maintenance():
    """Run weekly maintenance: watermark reconciliation, data reconciliation, cannibalization, content analysis (API-ONLY MODE)"""
    logger.info("=" * 60)
    logger.info("Starting WEEKLY maintenance - API-ONLY MODE")
    logger.info("=" * 60)

    start_time = datetime.utcnow()

    tasks = [
        # Watermark reconciliation runs FIRST to reset any watermarks that are
        # ahead of actual data (due to GSC data delay). This allows Data Reconciliation
        # to fetch the missing dates.
        ('Watermark Reconciliation', reconcile_watermarks),
        ('Data Reconciliation', reconcile_recent_data),
        ('SQL Transforms Refresh', run_transforms),
        ('Cannibalization Refresh', refresh_cannibalization_analysis),
        ('Content Analysis', run_content_analysis)
    ]

    results = {}
    for task_name, task_func in tasks:
        logger.info(f"\n--- {task_name} ---")
        results[task_name] = task_func()
        time.sleep(2)
    
    metrics['last_weekly_run'] = datetime.utcnow().isoformat()
    metrics['weekly_runs_count'] += 1
    
    end_time = datetime.utcnow()
    duration = (end_time - start_time).total_seconds()
    
    success_count = sum(1 for v in results.values() if v)
    logger.info("=" * 60)
    logger.info(f"WEEKLY maintenance completed: {success_count}/{len(tasks)} tasks successful")
    logger.info(f"Duration: {duration:.2f}s")
    logger.info("=" * 60)

def main():
    """Main scheduler entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='GSC Warehouse Scheduler')
    parser.add_argument('--test-daily', action='store_true',
                       help='Run daily job once and exit (for testing)')
    parser.add_argument('--test-insights', action='store_true',
                       help='Run only insights refresh and exit (for testing)')
    parser.add_argument('--test-content', action='store_true',
                       help='Run only content analysis and exit (for testing)')
    parser.add_argument('--test-hugo', action='store_true',
                       help='Run only Hugo sync and exit (for testing)')
    parser.add_argument('--test-trends', action='store_true',
                       help='Run only trends collection and exit (for testing)')
    parser.add_argument('--test-actions', action='store_true',
                       help='Run only content action execution and exit (for testing)')
    parser.add_argument('--test-watermark-reconciliation', action='store_true',
                       help='Run only watermark reconciliation and exit (for testing)')
    parser.add_argument('--test-gsc-serp', action='store_true',
                       help='Run only GSC SERP sync and exit (for testing)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show scheduled jobs without starting scheduler')
    args = parser.parse_args()

    # Test modes
    if args.test_daily:
        logger.info("TEST MODE: Running daily job once")
        success = daily_pipeline()
        sys.exit(0 if success else 1)

    if args.test_insights:
        logger.info("TEST MODE: Running insights refresh only")
        success = run_insights_refresh()
        sys.exit(0 if success else 1)

    if args.test_content:
        logger.info("TEST MODE: Running content analysis only")
        success = run_content_analysis()
        sys.exit(0 if success else 1)

    if args.test_hugo:
        logger.info("TEST MODE: Running Hugo sync only")
        success = run_hugo_sync()
        sys.exit(0 if success else 1)

    if args.test_trends:
        logger.info("TEST MODE: Running trends collection only")
        success = run_trends_collection()
        sys.exit(0 if success else 1)

    if args.test_actions:
        logger.info("TEST MODE: Running content action execution only")
        success = run_content_action_execution()
        sys.exit(0 if success else 1)

    if args.test_watermark_reconciliation:
        logger.info("TEST MODE: Running watermark reconciliation only")
        success = reconcile_watermarks()
        sys.exit(0 if success else 1)

    if args.test_gsc_serp:
        logger.info("TEST MODE: Running GSC SERP sync only")
        success = run_gsc_serp_sync()
        sys.exit(0 if success else 1)

    # Production scheduler
    scheduler = BlockingScheduler()
    
    # Daily pipeline at 7 AM UTC (12 PM Pakistan Standard Time, UTC+5)
    scheduler.add_job(
        daily_pipeline,
        CronTrigger(hour=7, minute=0),
        id='daily_pipeline',
        name='Daily Pipeline',
        replace_existing=True
    )
    
    # Weekly maintenance on Mondays at 7 AM UTC (12 PM PKT)
    scheduler.add_job(
        weekly_maintenance,
        CronTrigger(day_of_week='mon', hour=7, minute=0),
        id='weekly_maintenance',
        name='Weekly Maintenance',
        replace_existing=True
    )

    # Insights refresh 4 times daily (every 6 hours)
    # Q1: 1:00 AM UTC, Q2: 7:00 AM UTC (in daily pipeline), Q3: 1:00 PM UTC, Q4: 7:00 PM UTC
    for hour in [1, 13, 19]:  # 7:00 AM is covered by daily pipeline
        scheduler.add_job(
            run_insights_refresh,
            CronTrigger(hour=hour, minute=0),
            id=f'insights_refresh_{hour:02d}',
            name=f'Insights Refresh ({hour:02d}:00 UTC)',
            replace_existing=True
        )
    
    # Dry run mode - show jobs and exit
    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE - Scheduled Jobs")
        logger.info("=" * 60)
        logger.info("Daily pipeline (7:00 AM UTC / 12:00 PM PKT):")
        logger.info("  - API Ingestion (GSC)")
        logger.info("  - GA4 Collection")
        logger.info("  - SERP Collection (API-based: SerpStack/ValueSERP/SerpAPI)")
        logger.info("  - CWV Collection")
        logger.info("  - SQL Transforms")
        logger.info("  - GSC SERP Sync (free position tracking from GSC data)")
        logger.info("  - Insights Refresh")
        logger.info("  - Hugo Content Sync")
        logger.info("  - Content Action Execution (processes approved actions)")
        logger.info("  - Trends Collection")
        logger.info("  - Watermark Check")
        logger.info("")
        logger.info("Weekly maintenance (Monday 7:00 AM UTC / 12:00 PM PKT):")
        logger.info("  - Watermark Reconciliation (fixes gaps where watermarks ahead of data)")
        logger.info("  - Data Reconciliation")
        logger.info("  - SQL Transforms Refresh")
        logger.info("  - Cannibalization Refresh")
        logger.info("  - Content Analysis")
        logger.info("=" * 60)
        sys.exit(0)

    logger.info("=" * 60)
    logger.info("GSC Warehouse Scheduler started (API-ONLY MODE)")
    logger.info("Daily pipeline: 7:00 AM UTC / 12:00 PM PKT (GSC + GA4 + SERP API + GSC SERP + CWV + transforms + insights)")
    logger.info("SERP Tracking: Dual-source (API: SerpStack/ValueSERP + Free: GSC-based)")
    logger.info("Insights refresh: 4x daily at 1:00, 7:00, 13:00, 19:00 UTC")
    logger.info("Weekly maintenance: Monday 7:00 AM UTC / 12:00 PM PKT (reconciliation + cannibalization + content analysis)")
    logger.info("=" * 60)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")

if __name__ == '__main__':
    main()
