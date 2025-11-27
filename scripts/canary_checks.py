#!/usr/bin/env python3
"""
Canary Checks Script for Site Data Warehouse
Validates critical functionality in staging and production environments

Exit Codes:
    0 - All checks passed
    1 - One or more checks failed

Usage:
    python scripts/canary_checks.py --environment production
    python scripts/canary_checks.py --environment staging --verbose
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# External dependencies
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import httpx
except ImportError as e:
    print(f"ERROR: Missing required dependency: {e}")
    print("Install with: pip install psycopg2-binary httpx")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class EnvironmentConfig:
    """Configuration for different environments"""
    name: str
    warehouse_dsn: str
    api_url: str
    insights_api_url: str
    scheduler_metrics_file: str

    @classmethod
    def from_environment(cls, env_name: str) -> 'EnvironmentConfig':
        """Create config from environment variables"""
        if env_name == "production":
            return cls(
                name="production",
                warehouse_dsn=os.getenv("WAREHOUSE_DSN", "postgresql://seo_admin:change_me@warehouse:5432/seo_warehouse"),
                api_url=os.getenv("API_URL", "http://localhost:8000"),
                insights_api_url=os.getenv("INSIGHTS_API_URL", "http://localhost:8001"),
                scheduler_metrics_file=os.getenv("SCHEDULER_METRICS_FILE", "/logs/scheduler_metrics.json")
            )
        elif env_name == "staging":
            return cls(
                name="staging",
                warehouse_dsn=os.getenv("WAREHOUSE_DSN_STAGING", os.getenv("WAREHOUSE_DSN", "postgresql://seo_admin:change_me@warehouse:5432/seo_warehouse")),
                api_url=os.getenv("API_URL_STAGING", os.getenv("API_URL", "http://localhost:8000")),
                insights_api_url=os.getenv("INSIGHTS_API_URL_STAGING", os.getenv("INSIGHTS_API_URL", "http://localhost:8001")),
                scheduler_metrics_file=os.getenv("SCHEDULER_METRICS_FILE_STAGING", os.getenv("SCHEDULER_METRICS_FILE", "/logs/scheduler_metrics.json"))
            )
        else:
            raise ValueError(f"Unknown environment: {env_name}. Use 'staging' or 'production'")


# ============================================================================
# CHECK RESULT MODELS
# ============================================================================

@dataclass
class CheckResult:
    """Result of a single check"""
    name: str
    status: str  # "pass", "fail", "warn"
    duration_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class CanaryReport:
    """Overall canary check report"""
    environment: str
    timestamp: str
    overall_status: str  # "pass", "fail"
    total_checks: int
    passed: int
    failed: int
    warned: int
    duration_ms: float
    checks: List[CheckResult]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "environment": self.environment,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status,
            "summary": {
                "total_checks": self.total_checks,
                "passed": self.passed,
                "failed": self.failed,
                "warned": self.warned,
                "duration_ms": self.duration_ms
            },
            "checks": [asdict(check) for check in self.checks]
        }


# ============================================================================
# CANARY CHECKER CLASS
# ============================================================================

class CanaryChecker:
    """Performs canary checks on the site data warehouse"""

    def __init__(self, config: EnvironmentConfig, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.logger = self._setup_logger()
        self.results: List[CheckResult] = []

    def _setup_logger(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger("canary_checks")
        logger.setLevel(logging.DEBUG if self.verbose else logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)

        return logger

    def _run_check(self, name: str, check_func) -> CheckResult:
        """Run a single check and record result"""
        self.logger.info(f"Running check: {name}")
        start_time = time.time()

        try:
            result = check_func()
            duration_ms = (time.time() - start_time) * 1000

            if isinstance(result, CheckResult):
                result.duration_ms = duration_ms
                return result
            else:
                return CheckResult(
                    name=name,
                    status="pass",
                    duration_ms=duration_ms,
                    message="Check passed",
                    details=result
                )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(f"Check failed: {name} - {str(e)}")
            return CheckResult(
                name=name,
                status="fail",
                duration_ms=duration_ms,
                message="Check failed with exception",
                error=str(e)
            )

    # ========================================================================
    # DATABASE CHECKS
    # ========================================================================

    def check_database_connectivity(self) -> CheckResult:
        """Check if database is reachable and responsive"""
        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_database(), current_user")
                result = cur.fetchone()
                version = result[0]
                database = result[1]
                user = result[2]
            conn.close()

            return CheckResult(
                name="database_connectivity",
                status="pass",
                duration_ms=0,  # Will be set by _run_check
                message="Database connection successful",
                details={
                    "database": database,
                    "user": user,
                    "version": version.split(',')[0] if ',' in version else version[:50]
                }
            )
        except Exception as e:
            return CheckResult(
                name="database_connectivity",
                status="fail",
                duration_ms=0,
                message="Failed to connect to database",
                error=str(e)
            )

    def check_critical_tables_exist(self) -> CheckResult:
        """Verify critical tables exist in the database"""
        critical_tables = [
            'fact_gsc_daily',
            'ingest_watermarks',
            'insights',
            'dim_property'
        ]

        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'gsc'
                    AND table_name = ANY(%s)
                """, (critical_tables,))

                existing_tables = [row['table_name'] for row in cur.fetchall()]
            conn.close()

            missing_tables = set(critical_tables) - set(existing_tables)

            if missing_tables:
                return CheckResult(
                    name="critical_tables_exist",
                    status="fail",
                    duration_ms=0,
                    message=f"Missing critical tables: {', '.join(missing_tables)}",
                    details={
                        "expected": critical_tables,
                        "found": existing_tables,
                        "missing": list(missing_tables)
                    }
                )

            return CheckResult(
                name="critical_tables_exist",
                status="pass",
                duration_ms=0,
                message="All critical tables exist",
                details={"tables": existing_tables}
            )
        except Exception as e:
            return CheckResult(
                name="critical_tables_exist",
                status="fail",
                duration_ms=0,
                message="Failed to check tables",
                error=str(e)
            )

    def check_recent_data_ingestion(self) -> CheckResult:
        """Check if data has been ingested recently"""
        max_age_days = 3  # Data should be no older than 3 days

        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        MAX(date) as latest_date,
                        CURRENT_DATE - MAX(date) as days_old,
                        COUNT(DISTINCT property) as property_count,
                        COUNT(*) as row_count
                    FROM gsc.fact_gsc_daily
                """)
                result = cur.fetchone()
            conn.close()

            if not result or not result['latest_date']:
                return CheckResult(
                    name="recent_data_ingestion",
                    status="fail",
                    duration_ms=0,
                    message="No data found in fact_gsc_daily table"
                )

            days_old = result['days_old']

            if days_old > max_age_days:
                return CheckResult(
                    name="recent_data_ingestion",
                    status="fail",
                    duration_ms=0,
                    message=f"Latest data is {days_old} days old (threshold: {max_age_days} days)",
                    details=dict(result)
                )

            return CheckResult(
                name="recent_data_ingestion",
                status="pass",
                duration_ms=0,
                message=f"Recent data found ({days_old} days old)",
                details=dict(result)
            )
        except Exception as e:
            return CheckResult(
                name="recent_data_ingestion",
                status="fail",
                duration_ms=0,
                message="Failed to check data ingestion",
                error=str(e)
            )

    def check_recent_insights_created(self) -> CheckResult:
        """Check if insights have been created recently"""
        max_age_hours = 48  # Insights should have been created in last 48 hours

        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_insights,
                        COUNT(*) FILTER (WHERE generated_at >= NOW() - INTERVAL '24 hours') as last_24h,
                        COUNT(*) FILTER (WHERE generated_at >= NOW() - INTERVAL '48 hours') as last_48h,
                        MAX(generated_at) as latest_insight,
                        EXTRACT(EPOCH FROM (NOW() - MAX(generated_at)))/3600 as hours_since_last
                    FROM gsc.insights
                """)
                result = cur.fetchone()
            conn.close()

            if not result or result['total_insights'] == 0:
                return CheckResult(
                    name="recent_insights_created",
                    status="warn",
                    duration_ms=0,
                    message="No insights found in database (system may be new)",
                    details={"total_insights": 0}
                )

            hours_since_last = result['hours_since_last']

            if hours_since_last and hours_since_last > max_age_hours:
                return CheckResult(
                    name="recent_insights_created",
                    status="fail",
                    duration_ms=0,
                    message=f"No insights created in last {max_age_hours} hours (last: {hours_since_last:.1f}h ago)",
                    details=dict(result)
                )

            return CheckResult(
                name="recent_insights_created",
                status="pass",
                duration_ms=0,
                message=f"Recent insights found ({result['last_24h']} in last 24h)",
                details=dict(result)
            )
        except Exception as e:
            return CheckResult(
                name="recent_insights_created",
                status="warn",
                duration_ms=0,
                message="Failed to check insights (table may not exist yet)",
                error=str(e)
            )

    # ========================================================================
    # API CHECKS
    # ========================================================================

    def check_insights_api_health(self) -> CheckResult:
        """Check if Insights API health endpoint is responding"""
        try:
            health_url = f"{self.config.insights_api_url}/api/health"

            with httpx.Client(timeout=10.0) as client:
                response = client.get(health_url)

            if response.status_code != 200:
                return CheckResult(
                    name="insights_api_health",
                    status="fail",
                    duration_ms=0,
                    message=f"API returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )

            data = response.json()

            if data.get("status") != "healthy":
                return CheckResult(
                    name="insights_api_health",
                    status="fail",
                    duration_ms=0,
                    message=f"API status: {data.get('status', 'unknown')}",
                    details=data
                )

            return CheckResult(
                name="insights_api_health",
                status="pass",
                duration_ms=0,
                message="Insights API is healthy",
                details={
                    "status": data.get("status"),
                    "database": data.get("database"),
                    "total_insights": data.get("total_insights")
                }
            )
        except httpx.ConnectError:
            return CheckResult(
                name="insights_api_health",
                status="fail",
                duration_ms=0,
                message=f"Cannot connect to Insights API at {self.config.insights_api_url}",
                error="Connection refused"
            )
        except httpx.TimeoutException:
            return CheckResult(
                name="insights_api_health",
                status="fail",
                duration_ms=0,
                message="API health check timed out",
                error="Request timeout"
            )
        except Exception as e:
            return CheckResult(
                name="insights_api_health",
                status="fail",
                duration_ms=0,
                message="Failed to check API health",
                error=str(e)
            )

    def check_insights_api_query(self) -> CheckResult:
        """Check if Insights API can query data"""
        try:
            query_url = f"{self.config.insights_api_url}/api/insights?limit=1"

            with httpx.Client(timeout=10.0) as client:
                response = client.get(query_url)

            if response.status_code != 200:
                return CheckResult(
                    name="insights_api_query",
                    status="fail",
                    duration_ms=0,
                    message=f"Query returned status {response.status_code}",
                    details={"status_code": response.status_code}
                )

            data = response.json()

            if data.get("status") != "success":
                return CheckResult(
                    name="insights_api_query",
                    status="fail",
                    duration_ms=0,
                    message="Query did not return success status",
                    details=data
                )

            return CheckResult(
                name="insights_api_query",
                status="pass",
                duration_ms=0,
                message="API query successful",
                details={
                    "count": data.get("count", 0),
                    "limit": data.get("limit")
                }
            )
        except Exception as e:
            return CheckResult(
                name="insights_api_query",
                status="warn",
                duration_ms=0,
                message="Failed to query API (may not be running)",
                error=str(e)
            )

    # ========================================================================
    # SCHEDULER CHECKS
    # ========================================================================

    def check_scheduler_last_run(self) -> CheckResult:
        """Check if scheduler has run recently"""
        max_age_hours = 36  # Scheduler should run daily, allow some buffer

        try:
            # Try to read scheduler metrics file
            if not os.path.exists(self.config.scheduler_metrics_file):
                # Fall back to database check
                return self._check_scheduler_via_database(max_age_hours)

            with open(self.config.scheduler_metrics_file, 'r') as f:
                metrics = json.load(f)

            last_daily_run = metrics.get('last_daily_run')

            if not last_daily_run:
                return CheckResult(
                    name="scheduler_last_run",
                    status="warn",
                    duration_ms=0,
                    message="No daily run recorded in metrics",
                    details=metrics
                )

            last_run_time = datetime.fromisoformat(last_daily_run.replace('Z', '+00:00'))
            hours_since = (datetime.utcnow() - last_run_time.replace(tzinfo=None)).total_seconds() / 3600

            if hours_since > max_age_hours:
                return CheckResult(
                    name="scheduler_last_run",
                    status="fail",
                    duration_ms=0,
                    message=f"Scheduler last ran {hours_since:.1f} hours ago (threshold: {max_age_hours}h)",
                    details={
                        "last_daily_run": last_daily_run,
                        "hours_ago": hours_since,
                        "daily_runs_count": metrics.get('daily_runs_count')
                    }
                )

            return CheckResult(
                name="scheduler_last_run",
                status="pass",
                duration_ms=0,
                message=f"Scheduler ran {hours_since:.1f} hours ago",
                details={
                    "last_daily_run": last_daily_run,
                    "hours_ago": hours_since,
                    "daily_runs_count": metrics.get('daily_runs_count')
                }
            )
        except Exception as e:
            return CheckResult(
                name="scheduler_last_run",
                status="warn",
                duration_ms=0,
                message="Could not verify scheduler status",
                error=str(e)
            )

    def _check_scheduler_via_database(self, max_age_hours: int) -> CheckResult:
        """Fallback: Check scheduler health via database watermarks"""
        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        MAX(updated_at) as last_update,
                        EXTRACT(EPOCH FROM (NOW() - MAX(updated_at)))/3600 as hours_since
                    FROM gsc.ingest_watermarks
                """)
                result = cur.fetchone()
            conn.close()

            if not result or not result['last_update']:
                return CheckResult(
                    name="scheduler_last_run",
                    status="warn",
                    duration_ms=0,
                    message="No watermark updates found"
                )

            hours_since = result['hours_since']

            if hours_since > max_age_hours:
                return CheckResult(
                    name="scheduler_last_run",
                    status="fail",
                    duration_ms=0,
                    message=f"No ingestion in {hours_since:.1f} hours (threshold: {max_age_hours}h)",
                    details=dict(result)
                )

            return CheckResult(
                name="scheduler_last_run",
                status="pass",
                duration_ms=0,
                message=f"Recent ingestion activity ({hours_since:.1f} hours ago)",
                details=dict(result)
            )
        except Exception as e:
            return CheckResult(
                name="scheduler_last_run",
                status="warn",
                duration_ms=0,
                message="Could not verify scheduler via database",
                error=str(e)
            )

    # ========================================================================
    # DATA QUALITY CHECKS
    # ========================================================================

    def check_data_quality_basic(self) -> CheckResult:
        """Basic data quality checks on GSC data"""
        try:
            conn = psycopg2.connect(self.config.warehouse_dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check for null values in critical columns
                cur.execute("""
                    SELECT
                        COUNT(*) as total_rows,
                        COUNT(*) FILTER (WHERE property IS NULL) as null_property,
                        COUNT(*) FILTER (WHERE url IS NULL) as null_url,
                        COUNT(*) FILTER (WHERE query IS NULL) as null_query,
                        COUNT(*) FILTER (WHERE clicks < 0) as negative_clicks,
                        COUNT(*) FILTER (WHERE impressions < 0) as negative_impressions
                    FROM gsc.fact_gsc_daily
                    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                """)
                result = cur.fetchone()
            conn.close()

            issues = []
            if result['null_property'] > 0:
                issues.append(f"{result['null_property']} rows with null property")
            if result['null_url'] > 0:
                issues.append(f"{result['null_url']} rows with null URL")
            if result['null_query'] > 0:
                issues.append(f"{result['null_query']} rows with null query")
            if result['negative_clicks'] > 0:
                issues.append(f"{result['negative_clicks']} rows with negative clicks")
            if result['negative_impressions'] > 0:
                issues.append(f"{result['negative_impressions']} rows with negative impressions")

            if issues:
                return CheckResult(
                    name="data_quality_basic",
                    status="warn",
                    duration_ms=0,
                    message=f"Data quality issues found: {'; '.join(issues)}",
                    details=dict(result)
                )

            return CheckResult(
                name="data_quality_basic",
                status="pass",
                duration_ms=0,
                message="Data quality checks passed",
                details={"total_rows_checked": result['total_rows']}
            )
        except Exception as e:
            return CheckResult(
                name="data_quality_basic",
                status="warn",
                duration_ms=0,
                message="Could not perform data quality checks",
                error=str(e)
            )

    # ========================================================================
    # MAIN RUNNER
    # ========================================================================

    def run_all_checks(self) -> CanaryReport:
        """Run all canary checks and generate report"""
        self.logger.info(f"Starting canary checks for environment: {self.config.name}")
        start_time = time.time()

        # Define all checks to run
        checks = [
            ("Database Connectivity", self.check_database_connectivity),
            ("Critical Tables Exist", self.check_critical_tables_exist),
            ("Recent Data Ingestion", self.check_recent_data_ingestion),
            ("Recent Insights Created", self.check_recent_insights_created),
            ("Insights API Health", self.check_insights_api_health),
            ("Insights API Query", self.check_insights_api_query),
            ("Scheduler Last Run", self.check_scheduler_last_run),
            ("Data Quality Basic", self.check_data_quality_basic)
        ]

        # Run all checks
        for check_name, check_func in checks:
            result = self._run_check(check_name, check_func)
            self.results.append(result)

            # Log result
            if result.status == "pass":
                self.logger.info(f"✓ {check_name}: {result.message}")
            elif result.status == "warn":
                self.logger.warning(f"⚠ {check_name}: {result.message}")
            else:
                self.logger.error(f"✗ {check_name}: {result.message}")

        # Calculate summary
        total_duration = (time.time() - start_time) * 1000
        passed = sum(1 for r in self.results if r.status == "pass")
        failed = sum(1 for r in self.results if r.status == "fail")
        warned = sum(1 for r in self.results if r.status == "warn")

        # Overall status: fail if any check failed
        overall_status = "fail" if failed > 0 else "pass"

        report = CanaryReport(
            environment=self.config.name,
            timestamp=datetime.utcnow().isoformat() + "Z",
            overall_status=overall_status,
            total_checks=len(self.results),
            passed=passed,
            failed=failed,
            warned=warned,
            duration_ms=total_duration,
            checks=self.results
        )

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info(f"Canary Check Summary - {self.config.name.upper()}")
        self.logger.info("=" * 70)
        self.logger.info(f"Overall Status: {overall_status.upper()}")
        self.logger.info(f"Checks Passed:  {passed}/{len(self.results)}")
        self.logger.info(f"Checks Failed:  {failed}/{len(self.results)}")
        self.logger.info(f"Checks Warned:  {warned}/{len(self.results)}")
        self.logger.info(f"Duration:       {total_duration:.2f}ms")
        self.logger.info("=" * 70)

        return report


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run canary checks for Site Data Warehouse"
    )
    parser.add_argument(
        "--environment",
        "-e",
        choices=["staging", "production"],
        required=True,
        help="Environment to check (staging or production)"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON report to file"
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = EnvironmentConfig.from_environment(args.environment)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Run checks
    checker = CanaryChecker(config, verbose=args.verbose)
    report = checker.run_all_checks()

    # Output JSON report
    json_output = json.dumps(report.to_dict(), indent=2)

    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(json_output)
            print(f"\nJSON report written to: {args.output}")
        except Exception as e:
            print(f"ERROR: Failed to write report: {e}", file=sys.stderr)
    else:
        # Print to stdout for CI parsing
        print("\n" + "=" * 70)
        print("JSON OUTPUT (for CI parsing):")
        print("=" * 70)
        print(json_output)

    # Exit with appropriate code
    exit_code = 0 if report.overall_status == "pass" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
