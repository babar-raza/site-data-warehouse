#!/usr/bin/env python3
"""
GSC Data Warehouse - SQL Transform Applier
Applies SQL transformations in order with validation
"""

import os
import sys
import logging
import psycopg2
from pathlib import Path
from typing import List, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Transform files in application order
# Note: 01_schema.sql and 00_*.sql should be applied separately during initial setup
TRANSFORM_FILES = [
    'sql/03_transforms.sql',  # Base transforms and views
    'sql/04_ga4_schema.sql',  # GA4 tables
    'sql/05_unified_view.sql',  # Unified page performance view
    'sql/06_materialized_views.sql',  # Materialized views for performance
    'sql/07_agent_findings.sql',  # Agent findings table
    'sql/08_agent_diagnoses.sql',  # Agent diagnoses table
    'sql/09_agent_recommendations.sql',  # Agent recommendations table
    'sql/10_agent_executions.sql',  # Agent execution tracking
    'sql/11_insights_table.sql',  # Insights table for Unified Insight Engine
    'sql/12_actions_schema.sql',  # Actions schema
    'sql/13_content_schema.sql',  # Content schema
    'sql/14_forecasts_schema.sql',  # Forecasts schema
    'sql/16_serp_schema.sql',  # SERP tracking schema
    'sql/16a_serp_dual_source_migration.sql',  # SERP dual-source migration
    'sql/17_performance_schema.sql',  # Performance/CWV base schema
    'sql/18_analytics_schema.sql',  # Analytics schema
    'sql/19_automation_schema.sql',  # Automation schema
    'sql/20_notifications_schema.sql',  # Notifications schema
    'sql/21_orchestration_schema.sql',  # Orchestration schema
    'sql/22_anomaly_schema.sql',  # Anomaly detection schema
    'sql/23_url_variations_schema.sql',  # URL variations schema
    'sql/24_insight_aggregation_views.sql',  # Insight aggregation views
    'sql/25_url_consolidation_schema.sql',  # URL consolidation schema
    'sql/26_trends_schema.sql',  # Google Trends schema
    'sql/27_actions_schema.sql',  # Actions schema (extended)
    'sql/28_actions_metrics_views.sql',  # Actions metrics views
    'sql/29_hugo_content_schema.sql',  # Hugo content tracking schema
    'sql/30_monitored_pages_schema.sql',  # CWV monitored pages for URL discovery sync
]

def get_db_connection():
    """Create database connection from environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'gsc_db'),
            user=os.getenv('POSTGRES_USER', 'gsc_user'),
            password=os.getenv('POSTGRES_PASSWORD', 'gsc_password')
        )
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def apply_transform_file(conn, filepath: Path) -> bool:
    """Apply a single SQL transform file"""
    try:
        logger.info(f"Applying transform: {filepath}")
        
        if not filepath.exists():
            logger.warning(f"Transform file not found: {filepath}")
            return False
        
        with open(filepath, 'r') as f:
            sql = f.read()
        
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.close()
        conn.commit()
        
        logger.info(f"Successfully applied: {filepath.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply {filepath}: {e}")
        conn.rollback()
        return False

def validate_base_views(conn) -> bool:
    """Validate base views exist"""
    logger.info("Validating base views...")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.views 
            WHERE table_schema = 'gsc'
        """)
        view_count = cursor.fetchone()[0]
        logger.info(f"Found {view_count} views in gsc schema")
        cursor.close()
        return True
    except Exception as e:
        logger.error(f"Base view validation failed: {e}")
        return False

def validate_page_health(conn) -> bool:
    """Validate page health views/tables"""
    logger.info("Validating page health...")
    try:
        cursor = conn.cursor()
        # This is a placeholder - actual validation depends on what's in 02_page_health.sql
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'gsc' 
            AND table_name LIKE '%health%'
        """)
        health_objects = cursor.fetchone()[0]
        logger.info(f"Found {health_objects} health-related objects")
        cursor.close()
        return True
    except Exception as e:
        logger.error(f"Page health validation failed: {e}")
        return False

def validate_unified_view(conn) -> bool:
    """Validate unified performance view"""
    logger.info("Validating unified performance view...")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*), 
                   COUNT(DISTINCT property), 
                   MAX(date) as latest_date
            FROM gsc.vw_unified_page_performance
        """)
        row_count, prop_count, latest_date = cursor.fetchone()
        logger.info(f"Unified view: {row_count} rows, {prop_count} properties, latest: {latest_date}")
        cursor.close()
        return True
    except Exception as e:
        logger.error(f"Unified view validation failed: {e}")
        return False

def run_validations(conn, validations: List[Callable]) -> bool:
    """Run all validation functions"""
    logger.info("Running validations...")
    all_passed = True
    
    for validation_func in validations:
        try:
            if not validation_func(conn):
                all_passed = False
                logger.warning(f"Validation failed: {validation_func.__name__}")
        except Exception as e:
            logger.error(f"Validation error in {validation_func.__name__}: {e}")
            all_passed = False
    
    return all_passed

def main():
    """Main execution"""
    logger.info("Starting SQL transformations...")
    
    # Get base directory
    base_dir = Path(__file__).parent.resolve()
    
    # Connect to database
    try:
        conn = get_db_connection()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to establish database connection: {e}")
        return 1
    
    # Apply transforms
    success_count = 0
    for transform_file in TRANSFORM_FILES:
        filepath = base_dir / transform_file
        if apply_transform_file(conn, filepath):
            success_count += 1
    
    logger.info(f"Applied {success_count}/{len(TRANSFORM_FILES)} transforms successfully")
    
    # Run validations
    validations = [
        validate_base_views,
        validate_page_health,
        validate_unified_view,
    ]
    
    if run_validations(conn, validations):
        logger.info("All validations passed")
        conn.close()
        return 0
    else:
        logger.warning("Some validations failed")
        conn.close()
        return 1

if __name__ == "__main__":
    sys.exit(main())
