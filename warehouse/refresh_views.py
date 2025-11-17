#!/usr/bin/env python3
"""
Materialized View Refresh Manager
Handles refresh operations for unified page performance materialized views
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ViewRefreshManager:
    """Manages materialized view refresh operations"""
    
    AVAILABLE_VIEWS = {
        'unified_page_performance': 'mv_unified_page_performance',
        'unified_weekly': 'mv_unified_page_performance_weekly',
        'unified_monthly': 'mv_unified_page_performance_monthly',
    }
    
    def __init__(self, dsn: Optional[str] = None):
        """Initialize the refresh manager"""
        self.dsn = dsn or os.getenv('WAREHOUSE_DSN')
        if not self.dsn:
            raise ValueError("Database DSN not provided and WAREHOUSE_DSN not set")
        
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.dsn)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")
    
    def refresh_view(self, view_name: str, concurrent: bool = True) -> Dict:
        """
        Refresh a specific materialized view
        
        Args:
            view_name: Name of the view to refresh (key from AVAILABLE_VIEWS)
            concurrent: Whether to use CONCURRENTLY option (default: True)
        
        Returns:
            Dictionary with refresh results
        """
        if view_name not in self.AVAILABLE_VIEWS:
            raise ValueError(f"Unknown view: {view_name}. Available: {list(self.AVAILABLE_VIEWS.keys())}")
        
        full_view_name = f"gsc.{self.AVAILABLE_VIEWS[view_name]}"
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting refresh of {full_view_name}")
            
            # Execute refresh
            if concurrent:
                query = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {full_view_name}"
            else:
                query = f"REFRESH MATERIALIZED VIEW {full_view_name}"
            
            self.cursor.execute(query)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Get row count
            self.cursor.execute(f"SELECT COUNT(*) as count FROM {full_view_name}")
            row_count = self.cursor.fetchone()['count']
            
            result = {
                'view_name': view_name,
                'status': 'success',
                'duration': duration,
                'row_count': row_count,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            logger.info(f"Successfully refreshed {full_view_name} in {duration:.2f}s ({row_count} rows)")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = {
                'view_name': view_name,
                'status': 'failed',
                'duration': duration,
                'error': str(e),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            logger.error(f"Failed to refresh {full_view_name}: {e}")
            return result
    
    def refresh_all_views(self) -> List[Dict]:
        """Refresh all unified materialized views"""
        results = []
        
        logger.info("Starting refresh of all unified views")
        
        for view_name in self.AVAILABLE_VIEWS.keys():
            result = self.refresh_view(view_name)
            results.append(result)
        
        # Log summary
        success_count = sum(1 for r in results if r['status'] == 'success')
        total_duration = sum(r['duration'] for r in results)
        
        logger.info(f"Refresh complete: {success_count}/{len(results)} successful in {total_duration:.2f}s")
        
        return results
    
    def validate_view_quality(self) -> List[Dict]:
        """Run data quality validation checks"""
        logger.info("Running data quality validation")
        
        try:
            query = "SELECT * FROM gsc.validate_unified_view_quality()"
            self.cursor.execute(query)
            checks = self.cursor.fetchall()
            
            # Log results
            for check in checks:
                level = logging.INFO if check['check_status'] == 'PASS' else logging.WARNING
                logger.log(
                    level,
                    f"Check '{check['check_name']}': {check['check_status']} - "
                    f"{check['check_value']} ({check['check_message']})"
                )
            
            # Convert to list of dicts
            return [dict(check) for check in checks]
            
        except Exception as e:
            logger.error(f"Failed to run validation: {e}")
            return []
    
    def get_view_stats(self) -> Dict:
        """Get statistics for all materialized views"""
        stats = {}
        
        for view_name, full_name in self.AVAILABLE_VIEWS.items():
            try:
                # Get row count and last refresh time
                query = f"""
                    SELECT 
                        COUNT(*) as row_count,
                        MAX(last_refreshed) as last_refreshed,
                        MIN(date) as min_date,
                        MAX(date) as max_date
                    FROM gsc.{full_name}
                """
                self.cursor.execute(query)
                result = self.cursor.fetchone()
                
                stats[view_name] = dict(result)
                
            except Exception as e:
                logger.warning(f"Failed to get stats for {view_name}: {e}")
                stats[view_name] = {'error': str(e)}
        
        return stats
    
    def refresh_using_function(self) -> List[Dict]:
        """Use the database function to refresh all views"""
        logger.info("Refreshing views using database function")
        
        try:
            query = "SELECT * FROM gsc.refresh_all_unified_views()"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            
            # Log results
            for result in results:
                logger.info(
                    f"View '{result['view_name']}': {result['status']} "
                    f"(duration: {result['refresh_time']})"
                )
            
            return [dict(r) for r in results]
            
        except Exception as e:
            logger.error(f"Failed to refresh views using function: {e}")
            return []


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Refresh materialized views for unified page performance'
    )
    parser.add_argument(
        '--view',
        choices=list(ViewRefreshManager.AVAILABLE_VIEWS.keys()) + ['all'],
        help='Specific view to refresh (or "all" for all views)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Run data quality validation checks'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show materialized view statistics'
    )
    parser.add_argument(
        '--use-function',
        action='store_true',
        help='Use database function for refresh (slower but more reliable)'
    )
    parser.add_argument(
        '--dsn',
        help='Database connection string (default: from WAREHOUSE_DSN env var)'
    )
    
    args = parser.parse_args()
    
    # If no action specified, show help
    if not any([args.view, args.validate, args.stats]):
        parser.print_help()
        return 0
    
    # Initialize manager
    try:
        manager = ViewRefreshManager(dsn=args.dsn)
        manager.connect()
        
        exit_code = 0
        
        # Show stats
        if args.stats:
            logger.info("=== Materialized View Statistics ===")
            stats = manager.get_view_stats()
            for view_name, view_stats in stats.items():
                print(f"\n{view_name}:")
                for key, value in view_stats.items():
                    print(f"  {key}: {value}")
        
        # Refresh views
        if args.view:
            if args.use_function:
                results = manager.refresh_using_function()
            elif args.view == 'all':
                results = manager.refresh_all_views()
            else:
                result = manager.refresh_view(args.view)
                results = [result]
            
            # Check for failures
            failed = [r for r in results if r.get('status') != 'success']
            if failed:
                logger.error(f"{len(failed)} view(s) failed to refresh")
                exit_code = 1
        
        # Run validation
        if args.validate:
            logger.info("=== Data Quality Validation ===")
            checks = manager.validate_view_quality()
            
            # Check for failures
            failed_checks = [c for c in checks if c['check_status'] == 'FAIL']
            if failed_checks:
                logger.error(f"{len(failed_checks)} validation check(s) failed")
                exit_code = 1
        
        manager.close()
        return exit_code
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
