#!/usr/bin/env python3
"""
GSC Warehouse Startup Orchestrator
Automatically triggers initial data collection on system deployment

This service runs once on startup to:
1. Verify database connectivity
2. Check if initial data collection is needed
3. Run API ingestion if this is first deployment or data is stale
4. Apply SQL transforms to create analytical views
5. Validate data was successfully collected
6. Report status and metrics

This ensures data collection starts immediately on deployment,
not waiting for the next scheduled run at 2 AM UTC.
"""

import os
import sys
import time
import logging
import subprocess
import psycopg2
from datetime import datetime, date, timezone, timedelta
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/logs/startup_orchestrator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def get_db_password() -> str:
    """Read database password from secrets file"""
    password_file = os.environ.get('DB_PASSWORD_FILE', '/run/secrets/db_password')
    try:
        with open(password_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Password file not found at {password_file}, using default")
        return os.environ.get('DB_PASSWORD', 'gsc_pass')

def wait_for_database(max_attempts: int = 30, delay: int = 2) -> bool:
    """Wait for database to be ready"""
    logger.info("Waiting for database to be ready...")
    
    db_config = {
        'host': os.environ.get('DB_HOST', 'warehouse'),
        'port': int(os.environ.get('DB_PORT', 5432)),
        'database': os.environ.get('DB_NAME', 'gsc_db'),
        'user': os.environ.get('DB_USER', 'gsc_user'),
        'password': get_db_password()
    }
    
    for attempt in range(1, max_attempts + 1):
        try:
            conn = psycopg2.connect(**db_config)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            logger.info(f"Database is ready (attempt {attempt}/{max_attempts})")
            return True
        except Exception as e:
            logger.debug(f"Database not ready yet (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    
    logger.error("Database failed to become ready")
    return False

def check_data_status() -> Dict[str, Any]:
    """Check current data status in the warehouse"""
    logger.info("Checking current data status...")
    
    db_config = {
        'host': os.environ.get('DB_HOST', 'warehouse'),
        'port': int(os.environ.get('DB_PORT', 5432)),
        'database': os.environ.get('DB_NAME', 'gsc_db'),
        'user': os.environ.get('DB_USER', 'gsc_user'),
        'password': get_db_password()
    }
    
    try:
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            # Check if fact table has data
            cur.execute("SELECT COUNT(*) FROM gsc.fact_gsc_daily")
            total_rows = cur.fetchone()[0]
            
            # Check latest date
            cur.execute("SELECT MAX(date) FROM gsc.fact_gsc_daily")
            latest_date = cur.fetchone()[0]
            
            # Check properties
            cur.execute("SELECT COUNT(*) FROM gsc.dim_property WHERE api_only = true")
            api_only_properties = cur.fetchone()[0]
            
            # Check watermarks
            cur.execute("""
                SELECT property, last_date, rows_processed, last_run_status
                FROM gsc.ingest_watermarks
                WHERE source_type = 'api'
                ORDER BY last_date DESC
            """)
            watermarks = cur.fetchall()
            
        conn.close()
        
        status = {
            'total_rows': total_rows,
            'latest_date': latest_date,
            'api_only_properties': api_only_properties,
            'watermarks': watermarks,
            'needs_initial_collection': total_rows == 0 or latest_date is None,
            'data_freshness_days': (date.today() - latest_date).days if latest_date else None
        }
        
        logger.info(f"Data status: {total_rows} rows, latest: {latest_date}, properties: {api_only_properties}")
        return status
        
    except Exception as e:
        logger.error(f"Failed to check data status: {e}")
        return {
            'total_rows': 0,
            'needs_initial_collection': True,
            'error': str(e)
        }

def run_api_ingestion() -> bool:
    """Run API ingestion to collect GSC data"""
    logger.info("=" * 60)
    logger.info("Starting API Ingestion")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    try:
        # Run the API ingestor
        result = subprocess.run(
            ['python', '/app/ingestors/api/gsc_api_ingestor.py'],
            capture_output=True,
            text=True,
            check=True,
            timeout=3600  # 1 hour timeout
        )
        
        duration = time.time() - start_time
        logger.info(f"API ingestion completed successfully in {duration:.2f}s")
        logger.debug(f"Output: {result.stdout}")
        
        return True
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f"API ingestion timed out after {duration:.2f}s")
        return False
        
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        logger.error(f"API ingestion failed after {duration:.2f}s")
        logger.error(f"Error output: {e.stderr}")
        return False
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API ingestion error after {duration:.2f}s: {e}")
        return False

def run_transforms() -> bool:
    """Apply SQL transforms to create analytical views"""
    logger.info("=" * 60)
    logger.info("Applying SQL Transforms")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    try:
        # Check if transform script exists
        transform_script = '/app/transform/apply_transforms.py'
        if not os.path.exists(transform_script):
            logger.warning(f"Transform script not found at {transform_script}, skipping transforms")
            return True
        
        result = subprocess.run(
            ['python', transform_script],
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5 minute timeout
        )
        
        duration = time.time() - start_time
        logger.info(f"SQL transforms completed successfully in {duration:.2f}s")
        logger.debug(f"Output: {result.stdout}")
        
        return True
        
    except FileNotFoundError:
        logger.warning("Transform script not found, skipping transforms")
        return True
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f"Transforms timed out after {duration:.2f}s")
        return False
        
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        logger.error(f"Transforms failed after {duration:.2f}s")
        logger.error(f"Error output: {e.stderr}")
        return False
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Transforms error after {duration:.2f}s: {e}")
        return False

def validate_data_collected() -> Dict[str, Any]:
    """Validate that data was actually collected"""
    logger.info("Validating data collection...")
    
    status = check_data_status()
    
    if status['total_rows'] > 0:
        logger.info(f"✓ Data collection successful: {status['total_rows']} rows collected")
        logger.info(f"✓ Latest data: {status['latest_date']}")
        if status['data_freshness_days'] is not None:
            logger.info(f"✓ Data freshness: {status['data_freshness_days']} days old")
        return {'success': True, 'status': status}
    else:
        logger.warning("✗ No data collected - please check logs for errors")
        return {'success': False, 'status': status}

def write_status_report(summary: Dict[str, Any]) -> None:
    """Write status report to file"""
    try:
        report_dir = "/report/startup"
        os.makedirs(report_dir, exist_ok=True)
        
        import json
        with open(f"{report_dir}/orchestrator_status.json", "w") as f:
            json.dump({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'summary': summary
            }, f, indent=2, default=str)
        
        logger.info(f"Status report written to {report_dir}/orchestrator_status.json")
    except Exception as e:
        logger.error(f"Failed to write status report: {e}")

def main():
    """Main orchestration logic"""
    logger.info("=" * 60)
    logger.info("GSC Warehouse Startup Orchestrator")
    logger.info("=" * 60)
    
    start_time = datetime.now(timezone.utc)
    summary = {
        'start_time': start_time.isoformat(),
        'steps': [],
        'success': False
    }
    
    try:
        # Step 1: Wait for database
        logger.info("\n[1/5] Waiting for database...")
        if not wait_for_database():
            logger.error("Database is not available, aborting")
            summary['error'] = 'Database unavailable'
            write_status_report(summary)
            return 1
        summary['steps'].append({'step': 'database_ready', 'status': 'success'})
        
        # Step 2: Check current data status
        logger.info("\n[2/5] Checking data status...")
        initial_status = check_data_status()
        summary['initial_status'] = initial_status
        
        # Decide if we need to run collection
        run_collection = os.environ.get('RUN_INITIAL_COLLECTION', 'true').lower() == 'true'
        
        if not run_collection:
            logger.info("Initial collection disabled by configuration, skipping")
            summary['steps'].append({'step': 'collection_check', 'status': 'skipped'})
            summary['success'] = True
            write_status_report(summary)
            return 0
        
        if initial_status.get('needs_initial_collection'):
            logger.info("Initial data collection needed (no data in warehouse)")
        elif initial_status.get('data_freshness_days', 0) > 1:
            logger.info(f"Data is {initial_status['data_freshness_days']} days old, running refresh")
        else:
            logger.info("Data is fresh, but running collection to ensure up-to-date")
        
        # Step 3: Run API ingestion
        logger.info("\n[3/5] Running API ingestion...")
        ingestion_success = run_api_ingestion()
        summary['steps'].append({
            'step': 'api_ingestion',
            'status': 'success' if ingestion_success else 'failed'
        })
        
        if not ingestion_success:
            logger.warning("API ingestion failed, but continuing with transforms")
        
        # Step 4: Run transforms
        logger.info("\n[4/5] Running SQL transforms...")
        transform_success = run_transforms()
        summary['steps'].append({
            'step': 'transforms',
            'status': 'success' if transform_success else 'failed'
        })
        
        # Step 5: Validate and report
        logger.info("\n[5/5] Validating data collection...")
        validation = validate_data_collected()
        summary['final_status'] = validation['status']
        summary['steps'].append({
            'step': 'validation',
            'status': 'success' if validation['success'] else 'warning'
        })
        
        # Determine overall success
        summary['success'] = validation['success'] and ingestion_success
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        summary['error'] = str(e)
        summary['success'] = False
    
    finally:
        end_time = datetime.now(timezone.utc)
        summary['end_time'] = end_time.isoformat()
        summary['duration_seconds'] = (end_time - start_time).total_seconds()
        
        # Write final report
        write_status_report(summary)
        
        # Log summary
        logger.info("=" * 60)
        logger.info("Startup Orchestration Complete")
        logger.info("=" * 60)
        logger.info(f"Duration: {summary['duration_seconds']:.2f}s")
        logger.info(f"Success: {summary['success']}")
        if summary.get('final_status'):
            logger.info(f"Total rows: {summary['final_status']['total_rows']}")
            logger.info(f"Latest date: {summary['final_status']['latest_date']}")
        logger.info("=" * 60)
    
    # Return success code
    return 0 if summary['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
