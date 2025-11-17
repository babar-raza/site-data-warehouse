#!/usr/bin/env python3
"""Validate production readiness."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import asyncpg
from dotenv import load_dotenv

load_dotenv()


class ProductionValidator:
    """Validates production readiness."""
    
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def check(self, name: str, condition: bool, details: str = ""):
        """Record a check result."""
        if condition:
            self.passed.append((name, details))
            print(f"✓ {name}")
            if details:
                print(f"  {details}")
        else:
            self.failed.append((name, details))
            print(f"✗ {name}")
            if details:
                print(f"  {details}")
    
    def warn(self, name: str, details: str = ""):
        """Record a warning."""
        self.warnings.append((name, details))
        print(f"⚠ {name}")
        if details:
            print(f"  {details}")
    
    async def validate_database(self) -> bool:
        """Validate database connectivity and configuration."""
        print("\n=== Database Validation ===")
        
        try:
            db_config = {
                'host': os.getenv('WAREHOUSE_HOST', 'localhost'),
                'port': int(os.getenv('WAREHOUSE_PORT', 5432)),
                'user': os.getenv('WAREHOUSE_USER', 'gsc_user'),
                'password': os.getenv('WAREHOUSE_PASSWORD', ''),
                'database': os.getenv('WAREHOUSE_DB', 'gsc_warehouse')
            }
            
            pool = await asyncpg.create_pool(
                host=db_config['host'],
                port=db_config['port'],
                user=db_config['user'],
                password=db_config['password'],
                database=db_config['database'],
                min_size=1,
                max_size=5
            )
            
            async with pool.acquire() as conn:
                # Check connectivity
                result = await conn.fetchval("SELECT 1")
                self.check("Database connectivity", result == 1)
                
                # Check schemas
                schemas = await conn.fetch("""
                    SELECT schema_name FROM information_schema.schemata
                    WHERE schema_name IN ('gsc', 'ga4')
                """)
                self.check("Required schemas exist", len(schemas) == 2,
                          f"Found: {', '.join([s['schema_name'] for s in schemas])}")
                
                # Check tables
                tables = await conn.fetch("""
                    SELECT schemaname, tablename
                    FROM pg_tables
                    WHERE schemaname IN ('gsc', 'ga4')
                """)
                self.check("Tables created", len(tables) >= 6,
                          f"Found {len(tables)} tables")
                
                # Check views
                views = await conn.fetch("""
                    SELECT schemaname, viewname
                    FROM pg_views
                    WHERE schemaname = 'gsc'
                    AND viewname LIKE 'mv_%'
                """)
                self.check("Materialized views exist", len(views) >= 3,
                          f"Found {len(views)} views")
                
                # Check indexes
                indexes = await conn.fetch("""
                    SELECT schemaname, tablename, COUNT(*) as index_count
                    FROM pg_indexes
                    WHERE schemaname IN ('gsc', 'ga4')
                    GROUP BY schemaname, tablename
                    HAVING COUNT(*) > 0
                """)
                self.check("Indexes created", len(indexes) >= 4,
                          f"Found indexes on {len(indexes)} tables")
                
                # Check data exists
                gsc_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM gsc.search_analytics"
                )
                self.check("GSC data exists", gsc_count > 0,
                          f"{gsc_count} rows")
                
                # Check connection pool
                pool_status = await conn.fetch("""
                    SELECT count(*), state
                    FROM pg_stat_activity
                    WHERE datname = $1
                    GROUP BY state
                """, db_config['database'])
                
                total_conns = sum(row['count'] for row in pool_status)
                self.check("Connection pool size reasonable", total_conns < 100,
                          f"{total_conns} active connections")
            
            await pool.close()
            return len(self.failed) == 0
            
        except Exception as e:
            self.check("Database validation", False, str(e))
            return False
    
    def validate_configuration(self) -> bool:
        """Validate configuration files and environment."""
        print("\n=== Configuration Validation ===")
        
        # Check environment variables
        required_vars = [
            'WAREHOUSE_HOST',
            'WAREHOUSE_PORT',
            'WAREHOUSE_USER',
            'WAREHOUSE_PASSWORD',
            'WAREHOUSE_DB',
            'WAREHOUSE_DSN'
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            self.check(f"Environment variable {var}", value is not None,
                      f"Value: {'[SET]' if value else '[NOT SET]'}")
        
        # Check credential files
        gsc_creds = os.getenv('GSC_CREDENTIALS_FILE')
        if gsc_creds:
            self.check("GSC credentials file exists",
                      Path(gsc_creds).exists(),
                      gsc_creds)
        else:
            self.warn("GSC credentials not configured",
                     "API ingestion will not work")
        
        ga4_creds = os.getenv('GA4_CREDENTIALS_FILE')
        if ga4_creds:
            self.check("GA4 credentials file exists",
                      Path(ga4_creds).exists(),
                      ga4_creds)
        else:
            self.warn("GA4 credentials not configured",
                     "GA4 data will not sync")
        
        return len(self.failed) == 0
    
    def validate_file_structure(self) -> bool:
        """Validate required files and directories exist."""
        print("\n=== File Structure Validation ===")
        
        required_dirs = [
            'agents',
            'ingestors',
            'warehouse',
            'tests',
            'tests/e2e',
            'tests/load',
            'docs',
            'docs/deployment',
            'docs/runbooks',
            'sql',
            'logs'
        ]
        
        for dir_path in required_dirs:
            exists = Path(dir_path).exists()
            self.check(f"Directory {dir_path}", exists)
        
        required_files = [
            'requirements.txt',
            '.env',
            'bootstrap.py',
            'health-check.sh',
            'start-collection.sh',
            'tests/e2e/test_full_pipeline.py',
            'tests/e2e/test_agent_orchestration.py',
            'tests/e2e/test_data_flow.py',
            'tests/load/test_system_load.py',
            'docs/deployment/DEPLOYMENT_GUIDE.md',
            'docs/deployment/PRODUCTION_CHECKLIST.md',
            'docs/deployment/TROUBLESHOOTING.md',
            'docs/runbooks/DAILY_OPERATIONS.md',
            'docs/runbooks/INCIDENT_RESPONSE.md'
        ]
        
        for file_path in required_files:
            exists = Path(file_path).exists()
            self.check(f"File {file_path}", exists)
        
        return len(self.failed) == 0
    
    def validate_dependencies(self) -> bool:
        """Validate Python dependencies are installed."""
        print("\n=== Dependencies Validation ===")
        
        required_packages = [
            'asyncpg',
            'asyncio',
            'pytest',
            'psycopg2',
            'sqlalchemy',
            'pandas',
            'aiofiles',
            'dotenv',
            'requests'
        ]
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
                self.check(f"Package {package}", True)
            except ImportError:
                self.check(f"Package {package}", False,
                          f"Run: pip install {package}")
        
        return len(self.failed) == 0
    
    async def validate_agents(self) -> bool:
        """Validate agent configurations."""
        print("\n=== Agent Validation ===")
        
        agent_files = [
            'agents/watcher/watcher_agent.py',
            'agents/diagnostician/diagnostician_agent.py',
            'agents/strategist/strategist_agent.py',
            'agents/dispatcher/dispatcher_agent.py'
        ]
        
        for agent_file in agent_files:
            exists = Path(agent_file).exists()
            self.check(f"Agent file {agent_file}", exists)
        
        # Check agent data directories
        data_dirs = [
            'data/messages',
            'data/agent_state'
        ]
        
        for dir_path in data_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            self.check(f"Agent directory {dir_path}", True)
        
        return len(self.failed) == 0
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        total = len(self.passed) + len(self.failed) + len(self.warnings)
        
        print(f"\nTotal Checks: {total}")
        print(f"✓ Passed: {len(self.passed)}")
        print(f"✗ Failed: {len(self.failed)}")
        print(f"⚠ Warnings: {len(self.warnings)}")
        
        if self.failed:
            print("\n⚠ FAILED CHECKS:")
            for name, details in self.failed:
                print(f"  ✗ {name}")
                if details:
                    print(f"    {details}")
        
        if self.warnings:
            print("\n⚠ WARNINGS:")
            for name, details in self.warnings:
                print(f"  ⚠ {name}")
                if details:
                    print(f"    {details}")
        
        print("\n" + "=" * 80)
        
        if len(self.failed) == 0:
            print("✓ SYSTEM IS PRODUCTION READY")
            print("=" * 80)
            return 0
        else:
            print("✗ SYSTEM IS NOT PRODUCTION READY")
            print("Please fix the failed checks before deployment.")
            print("=" * 80)
            return 1


async def main():
    """Main validation function."""
    print("=" * 80)
    print("PRODUCTION READINESS VALIDATION")
    print("=" * 80)
    
    validator = ProductionValidator()
    
    # Run all validations
    await validator.validate_database()
    validator.validate_configuration()
    validator.validate_file_structure()
    validator.validate_dependencies()
    await validator.validate_agents()
    
    # Print summary and exit
    exit_code = validator.print_summary()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
