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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
WAREHOUSE_DSN = os.environ.get('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')
METRICS_FILE = '/logs/scheduler_metrics.json'

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

def run_transforms():
    """Apply SQL transforms to create views"""
    if not check_warehouse_health():
        logger.warning("Skipping transforms - warehouse not healthy")
        return False
    
    return run_command(
        ['python', '/app/transform/apply_transforms.py'],
        'transforms'
    )

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

def daily_pipeline():
    """
    Run daily pipeline: API ingestion, transforms, insights (API-ONLY MODE)
    
    Sequence:
    1. API Ingestion
    2. SQL Transforms (refresh views with new data)
    3. Insights Refresh (generate insights from fresh data)
    4. Watermark Check
    
    Insights failure is non-blocking and doesn't prevent rest of pipeline.
    """
    logger.info("=" * 60)
    logger.info("Starting DAILY pipeline - API-ONLY MODE")
    logger.info("=" * 60)
    
    start_time = datetime.utcnow()
    
    # Run tasks in sequence - BQ Extraction DISABLED for API-only mode
    tasks = [
        # ('BQ Extraction', run_bq_extraction),  # DISABLED - API-only mode
        ('API Ingestion', run_api_ingestion),
        ('SQL Transforms', run_transforms),
    ]
    
    results = {}
    for task_name, task_func in tasks:
        logger.info(f"\n--- {task_name} ---")
        results[task_name] = task_func()
        time.sleep(2)  # Small delay between tasks
    
    # Run insights refresh (non-blocking - failure doesn't affect pipeline status)
    logger.info(f"\n--- Insights Refresh ---")
    insights_success = run_insights_refresh()
    if not insights_success:
        logger.error("Insights refresh failed, but continuing pipeline...")
        logger.info("Pipeline will continue - insights are non-blocking")
    results['Insights Refresh'] = insights_success
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
    critical_tasks = ['API Ingestion', 'SQL Transforms']
    critical_success = sum(1 for task in critical_tasks if results.get(task, False))
    
    logger.info("=" * 60)
    logger.info(f"DAILY pipeline completed: {sum(1 for v in results.values() if v)}/{len(results)} tasks successful")
    logger.info(f"Critical tasks: {critical_success}/{len(critical_tasks)} successful")
    logger.info(f"Duration: {duration:.2f}s")
    logger.info("=" * 60)
    
    # Return True if critical tasks succeeded (insights can fail without failing pipeline)
    return critical_success == len(critical_tasks)

def weekly_maintenance():
    """Run weekly maintenance: reconciliation and cannibalization refresh (API-ONLY MODE)"""
    logger.info("=" * 60)
    logger.info("Starting WEEKLY maintenance - API-ONLY MODE")
    logger.info("=" * 60)
    
    start_time = datetime.utcnow()
    
    tasks = [
        ('Data Reconciliation', reconcile_recent_data),
        ('SQL Transforms Refresh', run_transforms),
        ('Cannibalization Refresh', refresh_cannibalization_analysis)
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
    
    # Production scheduler
    scheduler = BlockingScheduler()
    
    # Daily pipeline at 2 AM UTC
    scheduler.add_job(
        daily_pipeline,
        CronTrigger(hour=2, minute=0),
        id='daily_pipeline',
        name='Daily Pipeline',
        replace_existing=True
    )
    
    # Weekly maintenance on Sundays at 3 AM UTC
    scheduler.add_job(
        weekly_maintenance,
        CronTrigger(day_of_week='sun', hour=3, minute=0),
        id='weekly_maintenance',
        name='Weekly Maintenance',
        replace_existing=True
    )
    
    logger.info("=" * 60)
    logger.info("GSC Warehouse Scheduler started (API-ONLY MODE)")
    logger.info("Daily pipeline: 2:00 AM UTC (ingest + transform + insights)")
    logger.info("Weekly maintenance: Sunday 3:00 AM UTC")
    logger.info("=" * 60)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")

if __name__ == '__main__':
    main()
