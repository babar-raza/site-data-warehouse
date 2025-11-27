"""
System Health Check Script
Verifies all components of the SEO Intelligence Platform are working correctly
"""

import asyncio
import asyncpg
import redis
import httpx
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Colors for terminal output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color


class HealthChecker:
    def __init__(self):
        self.db_dsn = os.getenv('WAREHOUSE_DSN')
        self.redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        self.grafana_url = os.getenv('GRAFANA_URL', 'http://localhost:3000')
        self.ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')

        self.checks_passed = 0
        self.checks_failed = 0
        self.checks_warning = 0

    def print_success(self, message):
        print(f"{GREEN}✓{NC} {message}")
        self.checks_passed += 1

    def print_error(self, message):
        print(f"{RED}✗{NC} {message}")
        self.checks_failed += 1

    def print_warning(self, message):
        print(f"{YELLOW}!{NC} {message}")
        self.checks_warning += 1

    async def check_database(self):
        """Check PostgreSQL database"""
        print("\n1. Checking PostgreSQL Database...")

        try:
            conn = await asyncpg.connect(self.db_dsn)

            # Check connection
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                self.print_success("Database connection successful")

            # Check extensions
            extensions = await conn.fetch("""
                SELECT extname FROM pg_extension
                WHERE extname IN ('vector', 'pg_trgm', 'uuid-ossp')
            """)
            ext_names = [e['extname'] for e in extensions]

            if 'vector' in ext_names:
                self.print_success("pgvector extension enabled")
            else:
                self.print_error("pgvector extension missing")

            if 'pg_trgm' in ext_names:
                self.print_success("pg_trgm extension enabled")
            else:
                self.print_error("pg_trgm extension missing")

            # Check schemas
            schemas = await conn.fetch("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name IN ('gsc', 'ga4', 'base', 'serp', 'performance',
                                     'notifications', 'orchestration', 'anomaly')
            """)
            schema_names = [s['schema_name'] for s in schemas]

            required_schemas = ['gsc', 'ga4', 'base', 'serp', 'performance',
                              'notifications', 'orchestration', 'anomaly']
            missing_schemas = set(required_schemas) - set(schema_names)

            if not missing_schemas:
                self.print_success(f"All schemas exist ({len(schema_names)} found)")
            else:
                self.print_error(f"Missing schemas: {', '.join(missing_schemas)}")

            # Check table count
            table_count = await conn.fetchval("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            """)

            if table_count >= 40:
                self.print_success(f"Tables created ({table_count} tables)")
            else:
                self.print_warning(f"Table count lower than expected ({table_count} tables)")

            # Check data freshness
            try:
                gsc_latest = await conn.fetchval("SELECT MAX(data_date) FROM gsc.query_stats")
                if gsc_latest:
                    days_old = (datetime.now().date() - gsc_latest).days
                    if days_old <= 3:
                        self.print_success(f"GSC data is fresh (latest: {gsc_latest})")
                    else:
                        self.print_warning(f"GSC data is {days_old} days old (latest: {gsc_latest})")
                else:
                    self.print_warning("No GSC data found")
            except:
                self.print_warning("GSC schema not yet populated")

            await conn.close()

        except Exception as e:
            self.print_error(f"Database check failed: {e}")

    async def check_redis(self):
        """Check Redis"""
        print("\n2. Checking Redis...")

        try:
            # Parse Redis URL
            r = redis.from_url(self.redis_url)

            # Check connection
            if r.ping():
                self.print_success("Redis connection successful")

            # Check memory usage
            info = r.info('memory')
            used_memory_mb = info['used_memory'] / 1024 / 1024
            self.print_success(f"Redis memory usage: {used_memory_mb:.2f} MB")

            # Check key count
            key_count = r.dbsize()
            self.print_success(f"Redis keys: {key_count}")

            r.close()

        except Exception as e:
            self.print_error(f"Redis check failed: {e}")

    async def check_celery(self):
        """Check Celery workers"""
        print("\n3. Checking Celery...")

        try:
            # This would require celery library
            # For now, we'll check if tasks are defined in the database
            conn = await asyncpg.connect(self.db_dsn)

            # Check for recent workflow executions
            try:
                recent_workflows = await conn.fetchval("""
                    SELECT COUNT(*) FROM orchestration.workflows
                    WHERE started_at >= NOW() - INTERVAL '24 hours'
                """)

                if recent_workflows > 0:
                    self.print_success(f"Recent workflows executed: {recent_workflows} (last 24h)")
                else:
                    self.print_warning("No workflows executed in last 24 hours")
            except:
                self.print_warning("Orchestration schema not yet used")

            await conn.close()

            # Check if Celery processes are running
            import subprocess
            try:
                result = subprocess.run(['pgrep', '-f', 'celery worker'], capture_output=True, text=True)
                if result.returncode == 0:
                    self.print_success("Celery worker process found")
                else:
                    self.print_warning("Celery worker may not be running")
            except:
                pass  # pgrep not available on all systems

        except Exception as e:
            self.print_error(f"Celery check failed: {e}")

    async def check_grafana(self):
        """Check Grafana"""
        print("\n4. Checking Grafana...")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.grafana_url)

                if response.status_code == 200:
                    self.print_success(f"Grafana accessible at {self.grafana_url}")
                else:
                    self.print_warning(f"Grafana returned status {response.status_code}")

        except Exception as e:
            self.print_error(f"Grafana check failed: {e}")

    async def check_ollama(self):
        """Check Ollama (Local LLM)"""
        print("\n5. Checking Ollama...")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")

                if response.status_code == 200:
                    models = response.json().get('models', [])
                    if models:
                        model_names = [m['name'] for m in models]
                        self.print_success(f"Ollama running with models: {', '.join(model_names)}")
                    else:
                        self.print_warning("Ollama running but no models installed")
                else:
                    self.print_warning(f"Ollama returned status {response.status_code}")

        except Exception as e:
            self.print_warning(f"Ollama not accessible (optional service): {e}")

    async def check_api_credentials(self):
        """Check API credentials are configured"""
        print("\n6. Checking API Credentials...")

        # GSC
        if os.getenv('GSC_CREDENTIALS_PATH') or os.getenv('GSC_SERVICE_ACCOUNT_FILE'):
            cred_path = os.getenv('GSC_CREDENTIALS_PATH') or os.getenv('GSC_SERVICE_ACCOUNT_FILE')
            if os.path.exists(cred_path):
                self.print_success(f"GSC credentials file found: {cred_path}")
            else:
                self.print_error(f"GSC credentials file not found: {cred_path}")
        else:
            self.print_warning("GSC credentials path not configured")

        # GA4
        if os.getenv('GA4_CREDENTIALS_PATH') or os.getenv('GA4_CREDENTIALS_FILE'):
            cred_path = os.getenv('GA4_CREDENTIALS_PATH') or os.getenv('GA4_CREDENTIALS_FILE')
            if os.path.exists(cred_path):
                self.print_success(f"GA4 credentials file found: {cred_path}")
            else:
                self.print_error(f"GA4 credentials file not found: {cred_path}")
        else:
            self.print_warning("GA4 credentials path not configured")

        # SERP API
        if os.getenv('VALUESERP_API_KEY') or os.getenv('SERPAPI_KEY'):
            self.print_success("SERP API key configured")
        else:
            self.print_warning("SERP API key not configured")

        # Slack
        if os.getenv('SLACK_WEBHOOK_URL'):
            self.print_success("Slack webhook configured")
        else:
            self.print_warning("Slack webhook not configured")

        # Email
        if os.getenv('SMTP_HOST') or os.getenv('SENDGRID_API_KEY'):
            self.print_success("Email notifications configured")
        else:
            self.print_warning("Email notifications not configured")

    async def check_data_collection(self):
        """Check if data collection is working"""
        print("\n7. Checking Data Collection...")

        try:
            conn = await asyncpg.connect(self.db_dsn)

            # Check GSC data
            gsc_count = await conn.fetchval("SELECT COUNT(*) FROM gsc.query_stats")
            if gsc_count > 0:
                self.print_success(f"GSC data collected: {gsc_count} rows")
            else:
                self.print_warning("No GSC data collected yet")

            # Check SERP data
            try:
                serp_count = await conn.fetchval("SELECT COUNT(*) FROM serp.position_history")
                if serp_count > 0:
                    self.print_success(f"SERP data collected: {serp_count} rows")
                else:
                    self.print_warning("No SERP data collected yet")
            except:
                self.print_warning("SERP tracking not yet used")

            # Check CWV data
            try:
                cwv_count = await conn.fetchval("SELECT COUNT(*) FROM performance.cwv_metrics")
                if cwv_count > 0:
                    self.print_success(f"CWV data collected: {cwv_count} rows")
                else:
                    self.print_warning("No CWV data collected yet")
            except:
                self.print_warning("CWV monitoring not yet used")

            await conn.close()

        except Exception as e:
            self.print_error(f"Data collection check failed: {e}")

    async def run_all_checks(self):
        """Run all health checks"""
        print("========================================")
        print("SEO Intelligence Platform")
        print("System Health Check")
        print("========================================")

        await self.check_database()
        await self.check_redis()
        await self.check_celery()
        await self.check_grafana()
        await self.check_ollama()
        await self.check_api_credentials()
        await self.check_data_collection()

        # Summary
        print("\n========================================")
        print("Health Check Summary")
        print("========================================")
        print(f"{GREEN}Passed:{NC}   {self.checks_passed}")
        print(f"{YELLOW}Warnings:{NC} {self.checks_warning}")
        print(f"{RED}Failed:{NC}   {self.checks_failed}")
        print()

        if self.checks_failed == 0:
            print(f"{GREEN}System is healthy!{NC}")
            return 0
        else:
            print(f"{RED}System has {self.checks_failed} critical issues{NC}")
            return 1


async def main():
    checker = HealthChecker()
    exit_code = await checker.run_all_checks()
    sys.exit(exit_code)


if __name__ == '__main__':
    asyncio.run(main())
