#!/usr/bin/env python3
"""
GSC Warehouse Metrics Exporter
Prometheus-compatible metrics exporter for warehouse health, data quality, and pipeline execution

Exports metrics for all data ingestors:
- GSC (Google Search Console)
- GA4 (Google Analytics 4)
- SERP (Search Engine Results Position tracking)
- CWV (Core Web Vitals / PageSpeed Insights)
- CSE (Google Custom Search Engine)
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
CSE_METRICS_FILE = os.environ.get('CSE_METRICS_FILE', '/logs/cse_metrics.json')
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', '9090'))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', '15'))

# =============================================================================
# GSC (Google Search Console) Metrics
# =============================================================================
warehouse_up = Gauge('gsc_warehouse_up', 'Warehouse database health status (1=up, 0=down)')
fact_table_rows = Gauge('gsc_fact_table_total_rows', 'Total rows in fact_gsc_daily table')
data_freshness_days = Gauge('gsc_data_freshness_days', 'Days since last GSC data update', ['property'])
daily_runs_count = Counter('gsc_daily_runs_total', 'Total number of daily pipeline runs')
task_success = Gauge('gsc_task_success', 'Task success status (1=success, 0=failed)', ['task_name'])
task_duration = Gauge('gsc_task_duration_seconds', 'Task execution duration in seconds', ['task_name'])
duplicate_records = Gauge('gsc_duplicate_records', 'Number of duplicate records detected')
null_values_count = Gauge('gsc_null_values_count', 'Count of null values in critical fields', ['field'])
insights_total = Gauge('gsc_insights_total', 'Total number of insights', ['category', 'severity'])
watermark_days_behind = Gauge('gsc_watermark_days_behind', 'Days behind current date', ['property', 'source_type'])

# =============================================================================
# GA4 (Google Analytics 4) Metrics
# =============================================================================
ga4_fact_table_rows = Gauge('ga4_fact_table_total_rows', 'Total rows in fact_ga4_daily table')
ga4_data_freshness_days = Gauge('ga4_data_freshness_days', 'Days since last GA4 data update', ['property'])
ga4_ingestor_status = Gauge('ga4_ingestor_status', 'GA4 ingestor status (1=success, 0=failed)')
ga4_pages_tracked = Gauge('ga4_pages_tracked', 'Number of unique pages tracked in GA4')
ga4_total_sessions = Gauge('ga4_total_sessions_latest', 'Total sessions from latest GA4 data')

# =============================================================================
# SERP (Search Position Tracking) Metrics - Dual Source
# =============================================================================
# Total/Combined metrics
serp_queries_total = Gauge('serp_queries_total', 'Total number of SERP queries tracked')
serp_queries_active = Gauge('serp_queries_active', 'Number of active SERP queries')
serp_position_records = Gauge('serp_position_records_total', 'Total position history records')
serp_data_freshness_days = Gauge('serp_data_freshness_days', 'Days since last SERP check')
serp_ingestor_status = Gauge('serp_ingestor_status', 'SERP ingestor status (1=success, 0=failed)')
serp_avg_position = Gauge('serp_avg_position', 'Average SERP position across tracked queries')
serp_top10_count = Gauge('serp_top10_count', 'Number of queries ranking in top 10')
serp_not_ranking_count = Gauge('serp_not_ranking_count', 'Number of queries not ranking in top 100')

# Source-specific metrics (API vs GSC)
serp_queries_by_source = Gauge('serp_queries_by_source', 'SERP queries by data source', ['source'])
serp_positions_by_source = Gauge('serp_positions_by_source', 'Position records by data source', ['source'])
serp_api_queries = Gauge('serp_api_queries', 'Queries tracked via API (SerpStack/ValueSERP)')
serp_gsc_queries = Gauge('serp_gsc_queries', 'Queries tracked via GSC data (free)')
serp_api_status = Gauge('serp_api_status', 'SERP API tracking status (1=active, 0=inactive)')
serp_gsc_status = Gauge('serp_gsc_status', 'SERP GSC tracking status (1=active, 0=inactive)')

# =============================================================================
# CWV (Core Web Vitals / PageSpeed) Metrics
# =============================================================================
cwv_pages_monitored = Gauge('cwv_pages_monitored', 'Number of pages monitored for CWV')
cwv_checks_total = Gauge('cwv_checks_total', 'Total CWV check records')
cwv_data_freshness_days = Gauge('cwv_data_freshness_days', 'Days since last CWV check')
cwv_ingestor_status = Gauge('cwv_ingestor_status', 'CWV ingestor status (1=success, 0=failed)')
cwv_avg_performance_score = Gauge('cwv_avg_performance_score', 'Average Lighthouse performance score', ['strategy'])
cwv_avg_lcp = Gauge('cwv_avg_lcp_seconds', 'Average Largest Contentful Paint', ['strategy'])
cwv_avg_cls = Gauge('cwv_avg_cls', 'Average Cumulative Layout Shift', ['strategy'])
cwv_pass_rate = Gauge('cwv_pass_rate', 'Percentage of pages passing CWV assessment', ['strategy'])
cwv_poor_pages_count = Gauge('cwv_poor_pages_count', 'Number of pages with poor performance score')

# =============================================================================
# CSE (Google Custom Search Engine) Metrics
# =============================================================================
cse_queries_today = Gauge('cse_queries_today', 'CSE API queries used today')
cse_quota_remaining = Gauge('cse_quota_remaining', 'CSE API quota remaining for today')
cse_daily_quota = Gauge('cse_daily_quota', 'CSE API daily quota limit')

# =============================================================================
# Info Metrics
# =============================================================================
warehouse_info = Info('gsc_warehouse', 'Warehouse information')
ingestor_info = Info('data_ingestors', 'Data ingestor configuration information')


class MetricsCollector:
    """Collects metrics from warehouse database and scheduler for all data ingestors"""

    def __init__(self, dsn, scheduler_metrics_file, cse_metrics_file=None):
        self.dsn = dsn
        self.scheduler_metrics_file = scheduler_metrics_file
        self.cse_metrics_file = cse_metrics_file or CSE_METRICS_FILE
    
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

    # =========================================================================
    # GA4 (Google Analytics 4) Metrics Collection
    # =========================================================================
    def collect_ga4_metrics(self):
        """Collect GA4 data metrics"""
        try:
            conn = self.get_db_connection()
            if not conn:
                ga4_ingestor_status.set(0)
                return

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if GA4 table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
                    )
                """)
                if not cur.fetchone()['exists']:
                    logger.debug("GA4 table does not exist yet")
                    ga4_ingestor_status.set(0)
                    conn.close()
                    return

                # Total rows
                cur.execute("SELECT COUNT(*) as total FROM gsc.fact_ga4_daily")
                total = cur.fetchone()['total']
                ga4_fact_table_rows.set(total)

                # Unique pages tracked
                cur.execute("SELECT COUNT(DISTINCT page_path) as pages FROM gsc.fact_ga4_daily")
                pages = cur.fetchone()['pages']
                ga4_pages_tracked.set(pages)

                # Data freshness per property
                cur.execute("""
                    SELECT property,
                           MAX(date) as latest_date,
                           CURRENT_DATE - MAX(date) as days_behind
                    FROM gsc.fact_ga4_daily
                    GROUP BY property
                """)
                results = cur.fetchall()
                for row in results:
                    days = row['days_behind'] if row['days_behind'] is not None else 999
                    ga4_data_freshness_days.labels(property=row['property']).set(days)

                # Total sessions from latest date
                cur.execute("""
                    SELECT COALESCE(SUM(sessions), 0) as total_sessions
                    FROM gsc.fact_ga4_daily
                    WHERE date = (SELECT MAX(date) FROM gsc.fact_ga4_daily)
                """)
                total_sessions = cur.fetchone()['total_sessions']
                ga4_total_sessions.set(total_sessions)

                ga4_ingestor_status.set(1 if total > 0 else 0)

            conn.close()
            logger.debug(f"GA4 metrics collected: {total} rows, {pages} pages")

        except Exception as e:
            logger.error(f"Failed to collect GA4 metrics: {e}")
            ga4_ingestor_status.set(0)

    # =========================================================================
    # SERP (Search Position Tracking) Metrics Collection - Dual Source
    # =========================================================================
    def collect_serp_metrics(self):
        """Collect SERP tracking metrics from both API and GSC sources"""
        try:
            conn = self.get_db_connection()
            if not conn:
                serp_ingestor_status.set(0)
                serp_api_status.set(0)
                serp_gsc_status.set(0)
                return

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if SERP schema exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata
                        WHERE schema_name = 'serp'
                    )
                """)
                if not cur.fetchone()['exists']:
                    logger.debug("SERP schema does not exist yet")
                    serp_ingestor_status.set(0)
                    serp_api_status.set(0)
                    serp_gsc_status.set(0)
                    conn.close()
                    return

                # Check if queries table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'serp' AND table_name = 'queries'
                    )
                """)
                if not cur.fetchone()['exists']:
                    logger.debug("SERP queries table does not exist yet")
                    serp_ingestor_status.set(0)
                    serp_api_status.set(0)
                    serp_gsc_status.set(0)
                    conn.close()
                    return

                # Total queries
                cur.execute("SELECT COUNT(*) as total FROM serp.queries")
                total_queries = cur.fetchone()['total']
                serp_queries_total.set(total_queries)

                # Active queries
                cur.execute("SELECT COUNT(*) as active FROM serp.queries WHERE is_active = true")
                active_queries = cur.fetchone()['active']
                serp_queries_active.set(active_queries)

                # ===== Dual-Source Metrics =====
                # Check if data_source column exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'serp'
                        AND table_name = 'queries'
                        AND column_name = 'data_source'
                    )
                """)
                has_data_source = cur.fetchone()['exists']

                if has_data_source:
                    # Queries by data source
                    cur.execute("""
                        SELECT
                            COALESCE(data_source, 'unknown') as source,
                            COUNT(*) as count
                        FROM serp.queries
                        WHERE is_active = true
                        GROUP BY data_source
                    """)
                    source_counts = cur.fetchall()

                    api_count = 0
                    gsc_count = 0
                    for row in source_counts:
                        source = row['source']
                        count = row['count']
                        serp_queries_by_source.labels(source=source).set(count)
                        if source in ('serpstack', 'valueserp', 'serpapi', 'manual'):
                            api_count += count
                        elif source == 'gsc':
                            gsc_count += count

                    serp_api_queries.set(api_count)
                    serp_gsc_queries.set(gsc_count)

                    # Set status based on presence of data
                    serp_api_status.set(1 if api_count > 0 else 0)
                    serp_gsc_status.set(1 if gsc_count > 0 else 0)
                else:
                    # No data_source column - assume all are API-based
                    serp_api_queries.set(active_queries)
                    serp_gsc_queries.set(0)
                    serp_api_status.set(1 if active_queries > 0 else 0)
                    serp_gsc_status.set(0)

                # Check if position_history table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'serp' AND table_name = 'position_history'
                    )
                """)
                if cur.fetchone()['exists']:
                    # Total position records
                    cur.execute("SELECT COUNT(*) as total FROM serp.position_history")
                    total_records = cur.fetchone()['total']
                    serp_position_records.set(total_records)

                    # Data freshness
                    cur.execute("""
                        SELECT CURRENT_DATE - MAX(check_date) as days_behind
                        FROM serp.position_history
                    """)
                    result = cur.fetchone()
                    days = result['days_behind'] if result and result['days_behind'] is not None else 999
                    serp_data_freshness_days.set(days)

                    # Average position (excluding nulls - not ranking)
                    cur.execute("""
                        WITH latest AS (
                            SELECT DISTINCT ON (query_id) position
                            FROM serp.position_history
                            ORDER BY query_id, check_date DESC, check_timestamp DESC
                        )
                        SELECT AVG(position) as avg_pos
                        FROM latest
                        WHERE position IS NOT NULL
                    """)
                    result = cur.fetchone()
                    avg_pos = result['avg_pos'] if result and result['avg_pos'] else 0
                    serp_avg_position.set(float(avg_pos))

                    # Top 10 count
                    cur.execute("""
                        WITH latest AS (
                            SELECT DISTINCT ON (query_id) position
                            FROM serp.position_history
                            ORDER BY query_id, check_date DESC, check_timestamp DESC
                        )
                        SELECT COUNT(*) as top10
                        FROM latest
                        WHERE position IS NOT NULL AND position <= 10
                    """)
                    top10 = cur.fetchone()['top10']
                    serp_top10_count.set(top10)

                    # Not ranking count
                    cur.execute("""
                        WITH latest AS (
                            SELECT DISTINCT ON (query_id) position
                            FROM serp.position_history
                            ORDER BY query_id, check_date DESC, check_timestamp DESC
                        )
                        SELECT COUNT(*) as not_ranking
                        FROM latest
                        WHERE position IS NULL
                    """)
                    not_ranking = cur.fetchone()['not_ranking']
                    serp_not_ranking_count.set(not_ranking)

                    serp_ingestor_status.set(1 if total_records > 0 else 0)
                else:
                    serp_ingestor_status.set(0)

            conn.close()
            logger.debug(f"SERP metrics collected: {total_queries} queries, {active_queries} active")

        except Exception as e:
            logger.error(f"Failed to collect SERP metrics: {e}")
            serp_ingestor_status.set(0)

    # =========================================================================
    # CWV (Core Web Vitals) Metrics Collection
    # =========================================================================
    def collect_cwv_metrics(self):
        """Collect Core Web Vitals metrics"""
        try:
            conn = self.get_db_connection()
            if not conn:
                cwv_ingestor_status.set(0)
                return

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if performance schema exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata
                        WHERE schema_name = 'performance'
                    )
                """)
                if not cur.fetchone()['exists']:
                    logger.debug("Performance schema does not exist yet")
                    cwv_ingestor_status.set(0)
                    conn.close()
                    return

                # Check if monitored_pages table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'performance' AND table_name = 'monitored_pages'
                    )
                """)
                has_monitored_pages = cur.fetchone()['exists']

                if has_monitored_pages:
                    # Pages being monitored
                    cur.execute("""
                        SELECT COUNT(*) as monitored
                        FROM performance.monitored_pages
                        WHERE is_active = true
                    """)
                    monitored = cur.fetchone()['monitored']
                    cwv_pages_monitored.set(monitored)

                # Check if core_web_vitals table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'performance' AND table_name = 'core_web_vitals'
                    )
                """)
                if not cur.fetchone()['exists']:
                    logger.debug("CWV table does not exist yet")
                    cwv_ingestor_status.set(0)
                    conn.close()
                    return

                # Total CWV checks
                cur.execute("SELECT COUNT(*) as total FROM performance.core_web_vitals")
                total_checks = cur.fetchone()['total']
                cwv_checks_total.set(total_checks)

                # Data freshness
                cur.execute("""
                    SELECT CURRENT_DATE - MAX(check_date) as days_behind
                    FROM performance.core_web_vitals
                """)
                result = cur.fetchone()
                days = result['days_behind'] if result and result['days_behind'] is not None else 999
                cwv_data_freshness_days.set(days)

                # Metrics by strategy (mobile/desktop)
                for strategy in ['mobile', 'desktop']:
                    cur.execute("""
                        WITH latest AS (
                            SELECT DISTINCT ON (property, page_path)
                                performance_score, lcp, cls, cwv_assessment
                            FROM performance.core_web_vitals
                            WHERE strategy = %s
                            ORDER BY property, page_path, check_date DESC
                        )
                        SELECT
                            AVG(performance_score) as avg_score,
                            AVG(lcp) as avg_lcp,
                            AVG(cls) as avg_cls,
                            COUNT(*) FILTER (WHERE cwv_assessment = 'pass') as pass_count,
                            COUNT(*) as total,
                            COUNT(*) FILTER (WHERE performance_score < 50) as poor_count
                        FROM latest
                    """, (strategy,))
                    result = cur.fetchone()

                    if result and result['total'] > 0:
                        avg_score = result['avg_score'] or 0
                        avg_lcp = result['avg_lcp'] or 0
                        avg_cls = result['avg_cls'] or 0
                        pass_rate = (result['pass_count'] / result['total'] * 100) if result['total'] > 0 else 0

                        cwv_avg_performance_score.labels(strategy=strategy).set(float(avg_score))
                        cwv_avg_lcp.labels(strategy=strategy).set(float(avg_lcp))
                        cwv_avg_cls.labels(strategy=strategy).set(float(avg_cls))
                        cwv_pass_rate.labels(strategy=strategy).set(float(pass_rate))

                        if strategy == 'mobile':
                            cwv_poor_pages_count.set(result['poor_count'] or 0)

                cwv_ingestor_status.set(1 if total_checks > 0 else 0)

            conn.close()
            logger.debug(f"CWV metrics collected: {total_checks} checks")

        except Exception as e:
            logger.error(f"Failed to collect CWV metrics: {e}")
            cwv_ingestor_status.set(0)

    # =========================================================================
    # CSE (Google Custom Search Engine) Metrics Collection
    # =========================================================================
    def collect_cse_metrics(self):
        """Collect CSE quota metrics from file"""
        try:
            if not os.path.exists(self.cse_metrics_file):
                logger.debug(f"CSE metrics file not found: {self.cse_metrics_file}")
                # Set default quota values
                cse_daily_quota.set(100)  # Default free tier
                cse_queries_today.set(0)
                cse_quota_remaining.set(100)
                return

            with open(self.cse_metrics_file, 'r') as f:
                metrics = json.load(f)

            # Set metrics from file
            daily_quota = metrics.get('daily_quota', 100)
            queries_today = metrics.get('queries_today', 0)
            remaining = metrics.get('remaining', daily_quota - queries_today)

            cse_daily_quota.set(daily_quota)
            cse_queries_today.set(queries_today)
            cse_quota_remaining.set(remaining)

            logger.debug(f"CSE metrics collected: {queries_today}/{daily_quota} queries used")

        except Exception as e:
            logger.error(f"Failed to collect CSE metrics: {e}")
            # Set defaults on error
            cse_daily_quota.set(100)
            cse_queries_today.set(0)
            cse_quota_remaining.set(100)

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
        """Collect all metrics from all data ingestors"""
        logger.info("Collecting metrics from all ingestors...")

        # Check health first
        if not self.check_warehouse_health():
            logger.warning("Warehouse unhealthy, skipping database metrics")
            # Still collect file-based metrics
            self.collect_scheduler_metrics()
            self.collect_cse_metrics()
            return

        # =================================================================
        # GSC (Google Search Console) Metrics
        # =================================================================
        self.collect_warehouse_info()
        self.collect_fact_table_metrics()
        self.collect_data_freshness()
        self.collect_watermark_metrics()
        self.collect_insights_metrics()

        # =================================================================
        # GA4 (Google Analytics 4) Metrics
        # =================================================================
        self.collect_ga4_metrics()

        # =================================================================
        # SERP (Search Position Tracking) Metrics
        # =================================================================
        self.collect_serp_metrics()

        # =================================================================
        # CWV (Core Web Vitals) Metrics
        # =================================================================
        self.collect_cwv_metrics()

        # =================================================================
        # File-based Metrics (Scheduler & CSE)
        # =================================================================
        self.collect_scheduler_metrics()
        self.collect_cse_metrics()

        # Update ingestor info
        self._update_ingestor_info()

        logger.info("Metrics collection complete for all ingestors")

    def _update_ingestor_info(self):
        """Update ingestor configuration info metric"""
        try:
            ingestors_configured = []
            if os.environ.get('GSC_SVC_JSON') or os.environ.get('PROPERTIES'):
                ingestors_configured.append('gsc')
            if os.environ.get('GA4_CREDENTIALS_PATH') or os.environ.get('GA4_PROPERTY_ID'):
                ingestors_configured.append('ga4')
            if os.environ.get('SERPSTACK_API_KEY'):
                ingestors_configured.append('serp')
            if os.environ.get('PAGESPEED_API_KEY'):
                ingestors_configured.append('cwv')
            if os.environ.get('GOOGLE_CSE_API_KEY'):
                ingestors_configured.append('cse')

            ingestor_info.info({
                'configured_ingestors': ','.join(ingestors_configured) or 'none',
                'ingestor_count': str(len(ingestors_configured))
            })
        except Exception as e:
            logger.error(f"Failed to update ingestor info: {e}")


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
    logger.info("=" * 60)
    logger.info(f"Exporter port: {EXPORTER_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    logger.info("")
    logger.info("Configured Data Ingestors:")
    logger.info("  - GSC (Google Search Console)")
    logger.info("  - GA4 (Google Analytics 4)")
    logger.info("  - SERP (Search Position Tracking)")
    logger.info("  - CWV (Core Web Vitals / PageSpeed)")
    logger.info("  - CSE (Google Custom Search Engine)")
    logger.info("=" * 60)

    # Load config
    config = load_config()

    # Initialize collector with all metrics files
    collector = MetricsCollector(
        dsn=WAREHOUSE_DSN,
        scheduler_metrics_file=SCHEDULER_METRICS_FILE,
        cse_metrics_file=CSE_METRICS_FILE
    )

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
