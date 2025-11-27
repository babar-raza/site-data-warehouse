#!/usr/bin/env python3
"""
Pipeline Verification Script

Comprehensive health check for the SEO Intelligence Platform pipeline.
Verifies data freshness, ingestion watermarks, insight generation, and scheduler status.

Usage:
    python scripts/verify_pipeline.py [--environment ENV] [--format FORMAT] [--threshold-hours HOURS]

Examples:
    python scripts/verify_pipeline.py --environment production
    python scripts/verify_pipeline.py --format json
    python scripts/verify_pipeline.py --threshold-hours 48

Exit codes:
    0 - All checks passed (healthy)
    1 - One or more checks failed (unhealthy)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor


class PipelineVerifier:
    """Verifies pipeline health and data freshness"""

    def __init__(self, warehouse_dsn: str, environment: str = 'production'):
        """
        Initialize verifier

        Args:
            warehouse_dsn: PostgreSQL connection string
            environment: Environment name (development, staging, production)
        """
        self.warehouse_dsn = warehouse_dsn
        self.environment = environment
        self.checks = []
        self.issues = []

    def _connect(self):
        """Get database connection"""
        return psycopg2.connect(self.warehouse_dsn)

    def _add_check(self, name: str, status: str, message: str, details: Dict = None):
        """
        Add a check result

        Args:
            name: Check name
            status: 'pass', 'warn', or 'fail'
            message: Human-readable message
            details: Additional details dictionary
        """
        check = {
            'name': name,
            'status': status,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        if details:
            check['details'] = details

        self.checks.append(check)

        if status in ['fail', 'warn']:
            self.issues.append({
                'check': name,
                'severity': status,
                'message': message
            })

    def check_database_connection(self) -> bool:
        """Verify database is accessible"""
        try:
            conn = self._connect()
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
            conn.close()

            self._add_check(
                'Database Connection',
                'pass',
                'Database is accessible',
                {'postgres_version': version.split(',')[0]}
            )
            return True
        except Exception as e:
            self._add_check(
                'Database Connection',
                'fail',
                f'Cannot connect to database: {str(e)}'
            )
            return False

    def check_ingestion_watermarks(self, threshold_hours: int = 36) -> bool:
        """
        Check ingestion watermarks for all sources

        Args:
            threshold_hours: Maximum age in hours before considering stale

        Returns:
            True if all watermarks are fresh, False otherwise
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        property,
                        source_type,
                        last_date,
                        last_run_at,
                        last_run_status,
                        error_message,
                        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_run_at))/3600 as hours_since_run,
                        CURRENT_DATE - last_date as days_behind
                    FROM gsc.ingest_watermarks
                    ORDER BY last_run_at DESC NULLS LAST
                """)
                watermarks = cur.fetchall()
            conn.close()

            if not watermarks:
                self._add_check(
                    'Ingestion Watermarks',
                    'warn',
                    'No watermarks found - pipeline may not have run yet'
                )
                return False

            all_healthy = True
            stale_sources = []
            failed_sources = []

            for wm in watermarks:
                # Check if too old
                if wm['hours_since_run'] and wm['hours_since_run'] > threshold_hours:
                    stale_sources.append({
                        'property': wm['property'],
                        'source_type': wm['source_type'],
                        'hours_old': round(wm['hours_since_run'], 1),
                        'last_run': wm['last_run_at'].isoformat() if wm['last_run_at'] else None
                    })
                    all_healthy = False

                # Check for failures
                if wm['last_run_status'] == 'failed':
                    failed_sources.append({
                        'property': wm['property'],
                        'source_type': wm['source_type'],
                        'error': wm['error_message'],
                        'last_run': wm['last_run_at'].isoformat() if wm['last_run_at'] else None
                    })
                    all_healthy = False

            # Summarize results
            total_watermarks = len(watermarks)
            healthy_watermarks = total_watermarks - len(stale_sources) - len(failed_sources)

            details = {
                'total_watermarks': total_watermarks,
                'healthy_watermarks': healthy_watermarks,
                'stale_watermarks': len(stale_sources),
                'failed_watermarks': len(failed_sources),
                'threshold_hours': threshold_hours
            }

            if stale_sources:
                details['stale_sources'] = stale_sources
            if failed_sources:
                details['failed_sources'] = failed_sources

            if all_healthy:
                self._add_check(
                    'Ingestion Watermarks',
                    'pass',
                    f'All {total_watermarks} ingestion sources are healthy',
                    details
                )
            else:
                status = 'fail' if failed_sources else 'warn'
                message = f'{len(stale_sources) + len(failed_sources)}/{total_watermarks} sources have issues'
                self._add_check(
                    'Ingestion Watermarks',
                    status,
                    message,
                    details
                )

            return all_healthy

        except Exception as e:
            self._add_check(
                'Ingestion Watermarks',
                'fail',
                f'Error checking watermarks: {str(e)}'
            )
            return False

    def check_data_freshness(self, threshold_hours: int = 48) -> bool:
        """
        Check freshness of actual data in fact tables

        Args:
            threshold_hours: Maximum age in hours for data

        Returns:
            True if data is fresh, False otherwise
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check GSC data
                cur.execute("""
                    SELECT
                        MAX(date) as latest_date,
                        COUNT(DISTINCT property) as property_count,
                        COUNT(*) as row_count,
                        CURRENT_DATE - MAX(date) as days_behind
                    FROM gsc.fact_gsc_daily
                """)
                gsc_stats = cur.fetchone()

                # Check GA4 data (if exists)
                cur.execute("""
                    SELECT
                        MAX(date) as latest_date,
                        COUNT(DISTINCT property_id) as property_count,
                        COUNT(*) as row_count,
                        CURRENT_DATE - MAX(date) as days_behind
                    FROM analytics.fact_ga4_daily
                """)
                ga4_stats = cur.fetchone()

                # Check insights
                cur.execute("""
                    SELECT
                        MAX(generated_at) as latest_insight,
                        COUNT(*) as total_insights,
                        COUNT(DISTINCT insight_type) as insight_types,
                        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(generated_at)))/3600 as hours_old
                    FROM gsc.insights
                    WHERE status = 'active'
                """)
                insight_stats = cur.fetchone()

                # Check scheduler metrics (if exists)
                cur.execute("""
                    SELECT
                        process_name,
                        MAX(end_time) as last_run,
                        status,
                        EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(end_time)))/3600 as hours_old
                    FROM gsc.audit_log
                    WHERE process_name IN ('api_ingestion', 'ga4_collection', 'insights_refresh', 'daily_pipeline')
                    GROUP BY process_name, status
                    ORDER BY last_run DESC
                """)
                scheduler_stats = cur.fetchall()

            conn.close()

            # Evaluate GSC data freshness
            gsc_healthy = True
            if gsc_stats and gsc_stats['latest_date']:
                days_behind = gsc_stats['days_behind']
                if days_behind > 2:
                    gsc_healthy = False
                    status = 'fail' if days_behind > 3 else 'warn'
                    self._add_check(
                        'GSC Data Freshness',
                        status,
                        f'GSC data is {days_behind} days behind (latest: {gsc_stats["latest_date"]})',
                        {
                            'latest_date': str(gsc_stats['latest_date']),
                            'days_behind': days_behind,
                            'property_count': gsc_stats['property_count'],
                            'row_count': gsc_stats['row_count']
                        }
                    )
                else:
                    self._add_check(
                        'GSC Data Freshness',
                        'pass',
                        f'GSC data is current (latest: {gsc_stats["latest_date"]}, {days_behind} days behind)',
                        {
                            'latest_date': str(gsc_stats['latest_date']),
                            'days_behind': days_behind,
                            'property_count': gsc_stats['property_count'],
                            'row_count': gsc_stats['row_count']
                        }
                    )
            else:
                gsc_healthy = False
                self._add_check(
                    'GSC Data Freshness',
                    'fail',
                    'No GSC data found in warehouse'
                )

            # Evaluate GA4 data freshness (optional)
            ga4_healthy = True
            if ga4_stats and ga4_stats['latest_date']:
                days_behind = ga4_stats['days_behind']
                if days_behind > 2:
                    ga4_healthy = False
                    status = 'warn'  # GA4 is optional, so just warn
                    self._add_check(
                        'GA4 Data Freshness',
                        status,
                        f'GA4 data is {days_behind} days behind (latest: {ga4_stats["latest_date"]})',
                        {
                            'latest_date': str(ga4_stats['latest_date']),
                            'days_behind': days_behind,
                            'property_count': ga4_stats['property_count'],
                            'row_count': ga4_stats['row_count']
                        }
                    )
                else:
                    self._add_check(
                        'GA4 Data Freshness',
                        'pass',
                        f'GA4 data is current (latest: {ga4_stats["latest_date"]}, {days_behind} days behind)',
                        {
                            'latest_date': str(ga4_stats['latest_date']),
                            'days_behind': days_behind,
                            'property_count': ga4_stats['property_count'],
                            'row_count': ga4_stats['row_count']
                        }
                    )
            else:
                # GA4 is optional, so this is just informational
                self._add_check(
                    'GA4 Data Freshness',
                    'pass',
                    'No GA4 data (optional feature not configured)',
                    {'configured': False}
                )

            # Evaluate insights freshness
            insights_healthy = True
            if insight_stats and insight_stats['latest_insight']:
                hours_old = insight_stats['hours_old']
                if hours_old > threshold_hours:
                    insights_healthy = False
                    self._add_check(
                        'Insights Freshness',
                        'warn',
                        f'Insights are {round(hours_old, 1)} hours old (threshold: {threshold_hours}h)',
                        {
                            'latest_insight': insight_stats['latest_insight'].isoformat(),
                            'hours_old': round(hours_old, 1),
                            'total_insights': insight_stats['total_insights'],
                            'insight_types': insight_stats['insight_types']
                        }
                    )
                else:
                    self._add_check(
                        'Insights Freshness',
                        'pass',
                        f'Insights generated in last {round(hours_old, 1)} hours',
                        {
                            'latest_insight': insight_stats['latest_insight'].isoformat(),
                            'hours_old': round(hours_old, 1),
                            'total_insights': insight_stats['total_insights'],
                            'insight_types': insight_stats['insight_types']
                        }
                    )
            else:
                insights_healthy = False
                self._add_check(
                    'Insights Freshness',
                    'warn',
                    'No active insights found - insight engine may not have run'
                )

            return gsc_healthy and insights_healthy

        except Exception as e:
            self._add_check(
                'Data Freshness',
                'fail',
                f'Error checking data freshness: {str(e)}'
            )
            return False

    def check_insight_generation(self, lookback_hours: int = 24) -> bool:
        """
        Check if insights have been generated in the last N hours

        Args:
            lookback_hours: Hours to look back for insight generation

        Returns:
            True if insights were generated recently, False otherwise
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Count insights generated in last N hours
                cur.execute("""
                    SELECT
                        insight_type,
                        severity,
                        COUNT(*) as count,
                        MIN(generated_at) as first_generated,
                        MAX(generated_at) as last_generated
                    FROM gsc.insights
                    WHERE generated_at >= NOW() - INTERVAL '%s hours'
                    GROUP BY insight_type, severity
                    ORDER BY insight_type, severity
                """, (lookback_hours,))
                recent_insights = cur.fetchall()

                # Get total insight count by status
                cur.execute("""
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM gsc.insights
                    GROUP BY status
                """)
                status_counts = cur.fetchall()

            conn.close()

            if recent_insights:
                total_recent = sum(r['count'] for r in recent_insights)
                breakdown = [
                    {
                        'type': r['insight_type'],
                        'severity': r['severity'],
                        'count': r['count']
                    }
                    for r in recent_insights
                ]

                self._add_check(
                    'Insight Generation',
                    'pass',
                    f'{total_recent} insights generated in last {lookback_hours} hours',
                    {
                        'lookback_hours': lookback_hours,
                        'total_generated': total_recent,
                        'breakdown': breakdown,
                        'status_counts': [dict(r) for r in status_counts]
                    }
                )
                return True
            else:
                # Check if there are ANY insights at all
                total_insights = sum(r['count'] for r in status_counts) if status_counts else 0

                if total_insights > 0:
                    self._add_check(
                        'Insight Generation',
                        'warn',
                        f'No insights generated in last {lookback_hours} hours (total in DB: {total_insights})',
                        {
                            'lookback_hours': lookback_hours,
                            'total_generated': 0,
                            'status_counts': [dict(r) for r in status_counts]
                        }
                    )
                else:
                    self._add_check(
                        'Insight Generation',
                        'fail',
                        'No insights in database - insight engine has never run',
                        {'lookback_hours': lookback_hours}
                    )
                return False

        except Exception as e:
            self._add_check(
                'Insight Generation',
                'fail',
                f'Error checking insight generation: {str(e)}'
            )
            return False

    def check_scheduler_status(self) -> bool:
        """
        Check scheduler status from audit log and metrics file

        Returns:
            True if scheduler is healthy, False otherwise
        """
        try:
            # Check metrics file if it exists
            metrics_file = os.getenv('SCHEDULER_METRICS_FILE', '/logs/scheduler_metrics.json')
            if os.name == 'nt':
                metrics_file = 'logs/scheduler_metrics.json'

            scheduler_healthy = True

            if os.path.exists(metrics_file):
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)

                last_daily = metrics.get('last_daily_run')
                last_weekly = metrics.get('last_weekly_run')
                tasks = metrics.get('tasks', {})

                # Calculate hours since last daily run
                hours_since_daily = None
                if last_daily:
                    last_daily_dt = datetime.fromisoformat(last_daily)
                    hours_since_daily = (datetime.utcnow() - last_daily_dt).total_seconds() / 3600

                # Check if daily run is overdue (should run daily)
                if hours_since_daily and hours_since_daily > 30:  # 30 hours = more than a day
                    scheduler_healthy = False
                    status = 'fail' if hours_since_daily > 48 else 'warn'
                    self._add_check(
                        'Scheduler Status',
                        status,
                        f'Daily pipeline last ran {round(hours_since_daily, 1)} hours ago',
                        {
                            'last_daily_run': last_daily,
                            'hours_since_daily': round(hours_since_daily, 1),
                            'daily_runs_count': metrics.get('daily_runs_count', 0),
                            'weekly_runs_count': metrics.get('weekly_runs_count', 0),
                            'task_count': len(tasks)
                        }
                    )
                elif last_daily:
                    self._add_check(
                        'Scheduler Status',
                        'pass',
                        f'Scheduler is active (last daily run: {round(hours_since_daily, 1)} hours ago)',
                        {
                            'last_daily_run': last_daily,
                            'hours_since_daily': round(hours_since_daily, 1),
                            'daily_runs_count': metrics.get('daily_runs_count', 0),
                            'weekly_runs_count': metrics.get('weekly_runs_count', 0),
                            'task_count': len(tasks)
                        }
                    )
                else:
                    scheduler_healthy = False
                    self._add_check(
                        'Scheduler Status',
                        'warn',
                        'Scheduler has never run a daily pipeline',
                        {'metrics_file': metrics_file}
                    )
            else:
                # Check audit log as fallback
                conn = self._connect()
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            process_name,
                            MAX(start_time) as last_run,
                            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(start_time)))/3600 as hours_ago
                        FROM gsc.audit_log
                        WHERE process_name IN ('daily_pipeline', 'api_ingestion', 'insights_refresh')
                        GROUP BY process_name
                        ORDER BY last_run DESC
                    """)
                    recent_runs = cur.fetchall()
                conn.close()

                if recent_runs:
                    most_recent = recent_runs[0]
                    hours_ago = most_recent['hours_ago']

                    if hours_ago > 30:
                        scheduler_healthy = False
                        self._add_check(
                            'Scheduler Status',
                            'warn',
                            f'Last pipeline activity: {most_recent["process_name"]} ({round(hours_ago, 1)}h ago)',
                            {
                                'last_process': most_recent['process_name'],
                                'last_run': most_recent['last_run'].isoformat(),
                                'hours_ago': round(hours_ago, 1),
                                'note': 'Metrics file not found, using audit log'
                            }
                        )
                    else:
                        self._add_check(
                            'Scheduler Status',
                            'pass',
                            f'Recent activity: {most_recent["process_name"]} ({round(hours_ago, 1)}h ago)',
                            {
                                'last_process': most_recent['process_name'],
                                'last_run': most_recent['last_run'].isoformat(),
                                'hours_ago': round(hours_ago, 1),
                                'note': 'Metrics file not found, using audit log'
                            }
                        )
                else:
                    scheduler_healthy = False
                    self._add_check(
                        'Scheduler Status',
                        'warn',
                        'No scheduler activity found in audit log',
                        {'metrics_file': metrics_file, 'exists': False}
                    )

            return scheduler_healthy

        except Exception as e:
            self._add_check(
                'Scheduler Status',
                'fail',
                f'Error checking scheduler status: {str(e)}'
            )
            return False

    def check_table_counts(self) -> bool:
        """
        Check row counts in key tables to ensure data exists

        Returns:
            True if all tables have data, False otherwise
        """
        try:
            conn = self._connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get counts for key tables
                tables_to_check = [
                    ('gsc.fact_gsc_daily', 'GSC Daily Facts'),
                    ('gsc.insights', 'Insights'),
                    ('gsc.ingest_watermarks', 'Watermarks'),
                    ('analytics.fact_ga4_daily', 'GA4 Daily Facts'),
                ]

                table_stats = []
                all_healthy = True

                for table_name, display_name in tables_to_check:
                    try:
                        cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                        result = cur.fetchone()
                        count = result['count']

                        table_stats.append({
                            'table': display_name,
                            'row_count': count,
                            'status': 'ok' if count > 0 else 'empty'
                        })

                        # Only fail for critical tables (not GA4 which is optional)
                        if count == 0 and table_name not in ['analytics.fact_ga4_daily']:
                            all_healthy = False
                    except Exception as e:
                        # Table might not exist (e.g., GA4 tables)
                        table_stats.append({
                            'table': display_name,
                            'row_count': 0,
                            'status': 'missing',
                            'error': str(e)
                        })

            conn.close()

            empty_critical_tables = [
                t for t in table_stats
                if t['status'] == 'empty' and t['table'] != 'GA4 Daily Facts'
            ]

            if all_healthy:
                self._add_check(
                    'Table Data',
                    'pass',
                    'All critical tables contain data',
                    {'tables': table_stats}
                )
            else:
                self._add_check(
                    'Table Data',
                    'warn',
                    f'{len(empty_critical_tables)} critical tables are empty',
                    {'tables': table_stats}
                )

            return all_healthy

        except Exception as e:
            self._add_check(
                'Table Data',
                'fail',
                f'Error checking table counts: {str(e)}'
            )
            return False

    def run_all_checks(self, threshold_hours: int = 36, insight_lookback: int = 24) -> Dict[str, Any]:
        """
        Run all verification checks

        Args:
            threshold_hours: Threshold for watermark staleness
            insight_lookback: Hours to look back for insight generation

        Returns:
            Complete verification report
        """
        start_time = datetime.utcnow()

        # Run all checks
        db_ok = self.check_database_connection()

        if db_ok:
            self.check_table_counts()
            self.check_ingestion_watermarks(threshold_hours)
            self.check_data_freshness(threshold_hours)
            self.check_insight_generation(insight_lookback)
            self.check_scheduler_status()

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Count results
        passed = sum(1 for c in self.checks if c['status'] == 'pass')
        warned = sum(1 for c in self.checks if c['status'] == 'warn')
        failed = sum(1 for c in self.checks if c['status'] == 'fail')

        overall_status = 'healthy'
        if failed > 0:
            overall_status = 'unhealthy'
        elif warned > 0:
            overall_status = 'degraded'

        # Build report
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'environment': self.environment,
            'duration_seconds': round(duration, 2),
            'overall_status': overall_status,
            'summary': {
                'total_checks': len(self.checks),
                'passed': passed,
                'warned': warned,
                'failed': failed
            },
            'checks': self.checks
        }

        if self.issues:
            report['issues'] = self.issues

        return report


def format_human_readable(report: Dict[str, Any]) -> str:
    """
    Format report as human-readable text

    Args:
        report: Verification report dictionary

    Returns:
        Formatted text output
    """
    lines = []
    lines.append("=" * 80)
    lines.append("PIPELINE VERIFICATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Timestamp: {report['timestamp']}")
    lines.append(f"Environment: {report['environment']}")
    lines.append(f"Duration: {report['duration_seconds']}s")
    lines.append("")

    # Overall status
    status = report['overall_status']
    status_symbols = {
        'healthy': '✓',
        'degraded': '⚠',
        'unhealthy': '✗'
    }
    status_colors = {
        'healthy': '\033[92m',  # Green
        'degraded': '\033[93m',  # Yellow
        'unhealthy': '\033[91m'  # Red
    }
    reset_color = '\033[0m'

    symbol = status_symbols.get(status, '?')
    color = status_colors.get(status, '')

    lines.append(f"Overall Status: {color}{symbol} {status.upper()}{reset_color}")
    lines.append("")

    # Summary
    summary = report['summary']
    lines.append(f"Checks: {summary['total_checks']} total")
    lines.append(f"  ✓ Passed: {summary['passed']}")
    lines.append(f"  ⚠ Warned: {summary['warned']}")
    lines.append(f"  ✗ Failed: {summary['failed']}")
    lines.append("")

    # Individual checks
    lines.append("-" * 80)
    lines.append("CHECK RESULTS")
    lines.append("-" * 80)

    for check in report['checks']:
        status_sym = {
            'pass': '✓',
            'warn': '⚠',
            'fail': '✗'
        }.get(check['status'], '?')

        status_col = {
            'pass': '\033[92m',
            'warn': '\033[93m',
            'fail': '\033[91m'
        }.get(check['status'], '')

        lines.append(f"{status_col}{status_sym}{reset_color} {check['name']}: {check['message']}")

        # Add details if present
        if 'details' in check:
            details = check['details']
            for key, value in details.items():
                if isinstance(value, (list, dict)):
                    continue  # Skip complex structures in human-readable
                lines.append(f"    {key}: {value}")

    lines.append("")

    # Issues summary
    if 'issues' in report and report['issues']:
        lines.append("-" * 80)
        lines.append("ISSUES DETECTED")
        lines.append("-" * 80)
        for issue in report['issues']:
            severity_sym = '⚠' if issue['severity'] == 'warn' else '✗'
            lines.append(f"{severity_sym} [{issue['severity'].upper()}] {issue['check']}: {issue['message']}")
        lines.append("")

    lines.append("=" * 80)

    return '\n'.join(lines)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Verify SEO Intelligence Platform pipeline health',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/verify_pipeline.py --environment production
  python scripts/verify_pipeline.py --format json
  python scripts/verify_pipeline.py --threshold-hours 48

Exit codes:
  0 = All checks passed (healthy)
  1 = One or more checks failed (unhealthy)
        """
    )

    parser.add_argument(
        '--environment',
        default=os.getenv('ENVIRONMENT', 'production'),
        help='Environment name (default: production or $ENVIRONMENT)'
    )

    parser.add_argument(
        '--format',
        choices=['json', 'human'],
        default='human',
        help='Output format (default: human)'
    )

    parser.add_argument(
        '--threshold-hours',
        type=int,
        default=36,
        help='Staleness threshold in hours for watermarks and data (default: 36)'
    )

    parser.add_argument(
        '--insight-lookback',
        type=int,
        default=24,
        help='Hours to look back for insight generation (default: 24)'
    )

    parser.add_argument(
        '--dsn',
        default=os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db'),
        help='Database connection string (default: $WAREHOUSE_DSN)'
    )

    args = parser.parse_args()

    # Create verifier
    verifier = PipelineVerifier(args.dsn, args.environment)

    # Run verification
    report = verifier.run_all_checks(args.threshold_hours, args.insight_lookback)

    # Output report
    if args.format == 'json':
        print(json.dumps(report, indent=2))
    else:
        print(format_human_readable(report))

    # Exit with appropriate code
    if report['overall_status'] == 'healthy':
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
