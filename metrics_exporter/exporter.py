#!/usr/bin/env python3
"""
GSC Warehouse Metrics Exporter
Prometheus-compatible metrics exporter for warehouse health, data quality, and pipeline execution
"""
import os
import sys
import time
import logging
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import yaml
from prometheus_client import start_http_server, Gauge, Counter, Info
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG_FILE = os.environ.get('CONFIG_FILE', '/app/metrics_exporter/config.yaml')
WAREHOUSE_DSN = os.environ.get('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')
SCHEDULER_METRICS_FILE = os.environ.get('SCHEDULER_METRICS_FILE', '/logs/scheduler_metrics.json')
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9090'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '15'))

# Prometheus Metrics
warehouse_up = Gauge('gsc_warehouse_up', 'Warehouse database health status (1=up, 0=down)')
fact_table_rows = Gauge('gsc_fact_table_total_rows', 'Total rows in fact_gsc_daily table')
data_freshness_days = Gauge('gsc_data_freshness_days', 'Days since last data update', ['property'])
daily_runs_count = Counter('gsc_daily_runs_total', 'Total number of daily pipeline runs')
task_success = Gauge('gsc_task_success', 'Task success status (1=success, 0=failed)', ['task_name'])
task_duration = Gauge('gsc_task_duration_seconds', 'Task execution duration in seconds', ['task_name'])
duplicate_records = Gauge('gsc_duplicate_records', 'Number of duplicate records detected')
null_values_count = Gauge('gsc_null_values_count', 'Count of null values in critical fields', ['field'])
insights_total = Gauge('gsc_insights_total', 'Total number of insights', ['category', 'severity'])
watermark_days_behind = Gauge('gsc_watermark_days_behind', 'Days behind current date', ['property', 'source_type'])

# Info metrics
warehouse_info = Info('gsc_warehouse', 'Warehouse information')


class MetricsCollector:
    """Collects metrics from warehouse database and scheduler"""
    
    def __init__(self, dsn, scheduler_metrics_file):
        self.dsn = dsn
        self.scheduler_metrics_file = scheduler_metrics_file
    
    def get_db_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(self.dsn)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return None
    
    def check_warehouse_health(self):
        """Check if warehouse is accessible"""
        try:
            conn = self.get_db_connection()
            if not conn:
                warehouse_up.set(0)
                return False
            
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            
            warehouse_up.set(1)
            logger.debug("Warehouse health check: OK")
            return True
        except Exception as e:
            logger.error(f"Warehouse health check failed: {e}")
            warehouse_up.set(0)
            return False
    
    def collect_warehouse_info(self):
        """Collect warehouse metadata"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get PostgreSQL version
                cur.execute("SELECT version()")
                pg_version = cur.fetchone()['version']
                
                # Get database size
                cur.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as db_size
                """)
                db_size = cur.fetchone()['db_size']
            
            conn.close()
            
            warehouse_info.info({
                'postgres_version': pg_version.split()[1] if pg_version else 'unknown',
                'database_size': db_size
            })
            
        except Exception as e:
            logger.error(f"Failed to collect warehouse info: {e}")
    
    def collect_fact_table_metrics(self):
        """Collect metrics about fact table"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Total rows
                cur.execute("SELECT COUNT(*) as total FROM gsc.fact_gsc_daily")
                total = cur.fetchone()['total']
                fact_table_rows.set(total)
                
                # Duplicate check
                cur.execute("""
                    SELECT COUNT(*) as duplicates
                    FROM (
                        SELECT date, property, url, query, country, device, COUNT(*)
                        FROM gsc.fact_gsc_daily
                        GROUP BY date, property, url, query, country, device
                        HAVING COUNT(*) > 1
                    ) dup
                """)
                dups = cur.fetchone()['duplicates']
                duplicate_records.set(dups)
                
                # Null value checks
                null_fields = ['clicks', 'impressions', 'ctr', 'position']
                for field in null_fields:
                    cur.execute(f"""
                        SELECT COUNT(*) as null_count
                        FROM gsc.fact_gsc_daily
                        WHERE {field} IS NULL
                    """)
                    null_count = cur.fetchone()['null_count']
                    null_values_count.labels(field=field).set(null_count)
            
            conn.close()
            logger.debug(f"Fact table metrics: {total} rows, {dups} duplicates")
            
        except Exception as e:
            logger.error(f"Failed to collect fact table metrics: {e}")
    
    def collect_data_freshness(self):
        """Collect data freshness metrics"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get latest date per property
                cur.execute("""
                    SELECT property, 
                           MAX(date) as latest_date,
                           CURRENT_DATE - MAX(date) as days_behind
                    FROM gsc.fact_gsc_daily
                    GROUP BY property
                """)
                results = cur.fetchall()
                
                for row in results:
                    days = row['days_behind'] if row['days_behind'] is not None else 999
                    data_freshness_days.labels(property=row['property']).set(days)
            
            conn.close()
            logger.debug(f"Data freshness collected for {len(results)} properties")
            
        except Exception as e:
            logger.error(f"Failed to collect data freshness: {e}")
    
    def collect_watermark_metrics(self):
        """Collect watermark metrics"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT property, source_type, last_date,
                           CURRENT_DATE - last_date as days_behind
                    FROM gsc.ingest_watermarks
                """)
                results = cur.fetchall()
                
                for row in results:
                    days = row['days_behind'] if row['days_behind'] is not None else 999
                    watermark_days_behind.labels(
                        property=row['property'],
                        source_type=row['source_type']
                    ).set(days)
            
            conn.close()
            logger.debug(f"Watermark metrics collected for {len(results)} entries")
            
        except Exception as e:
            logger.error(f"Failed to collect watermark metrics: {e}")
    
    def collect_insights_metrics(self):
        """Collect insights metrics"""
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if insights table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'gsc' AND table_name = 'insights'
                    )
                """)
                
                if not cur.fetchone()['exists']:
                    logger.debug("Insights table does not exist yet")
                    return
                
                # Get counts by category and severity
                cur.execute("""
                    SELECT category, severity, COUNT(*) as count
                    FROM gsc.insights
                    GROUP BY category, severity
                """)
                results = cur.fetchall()
                
                for row in results:
                    insights_total.labels(
                        category=row['category'],
                        severity=row['severity']
                    ).set(row['count'])
            
            conn.close()
            logger.debug(f"Insights metrics collected: {len(results)} groups")
            
        except Exception as e:
            logger.error(f"Failed to collect insights metrics: {e}")
    
    def collect_scheduler_metrics(self):
        """Collect metrics from scheduler metrics file"""
        try:
            if not os.path.exists(self.scheduler_metrics_file):
                logger.debug(f"Scheduler metrics file not found: {self.scheduler_metrics_file}")
                return
            
            with open(self.scheduler_metrics_file, 'r') as f:
                metrics = json.load(f)
            
            # Daily runs count
            if 'daily_runs_count' in metrics:
                daily_runs_count._value._value = metrics['daily_runs_count']
            
            # Task metrics
            if 'tasks' in metrics:
                for task_name, task_data in metrics['tasks'].items():
                    status = task_data.get('status', 'unknown')
                    task_success.labels(task_name=task_name).set(1 if status == 'success' else 0)
                    
                    duration = task_data.get('duration_seconds')
                    if duration is not None:
                        task_duration.labels(task_name=task_name).set(duration)
            
            logger.debug(f"Scheduler metrics collected from {self.scheduler_metrics_file}")
            
        except Exception as e:
            logger.error(f"Failed to collect scheduler metrics: {e}")
    
    def collect_all_metrics(self):
        """Collect all metrics"""
        logger.info("Collecting metrics...")
        
        # Check health first
        if not self.check_warehouse_health():
            logger.warning("Warehouse unhealthy, skipping some metrics")
            return
        
        # Collect all metrics
        self.collect_warehouse_info()
        self.collect_fact_table_metrics()
        self.collect_data_freshness()
        self.collect_watermark_metrics()
        self.collect_insights_metrics()
        self.collect_scheduler_metrics()
        
        logger.info("Metrics collection complete")


def load_config():
    """Load configuration from YAML file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"Config file not found: {CONFIG_FILE}, using defaults")
            return {}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("GSC Warehouse Metrics Exporter starting...")
    logger.info(f"Exporter port: {EXPORTER_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    logger.info("=" * 60)
    
    # Load config
    config = load_config()
    
    # Initialize collector
    collector = MetricsCollector(WAREHOUSE_DSN, SCHEDULER_METRICS_FILE)
    
    # Start HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics server started on port {EXPORTER_PORT}")
    logger.info(f"Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    
    # Initial collection
    collector.collect_all_metrics()
    
    # Periodic collection loop
    try:
        while True:
            time.sleep(SCRAPE_INTERVAL)
            collector.collect_all_metrics()
    except KeyboardInterrupt:
        logger.info("Exporter stopped by user")
    except Exception as e:
        logger.error(f"Exporter error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
