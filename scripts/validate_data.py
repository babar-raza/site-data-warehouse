#!/usr/bin/env python3
"""
Data Validation Script
Validates GSC and GA4 data quality and depth for insights generation
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict


class DataValidator:
    """Validates data quality and completeness"""
    
    def __init__(self, dsn: str):
        """Initialize validator with database connection"""
        self.dsn = dsn
        self.conn = psycopg2.connect(dsn)
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'PASS',
            'checks': [],
            'recommendations': [],
            'summary': {}
        }
    
    def run_all_validations(self) -> Dict[str, Any]:
        """
        Run all validation checks
        
        Returns:
            Validation results dict
        """
        print("=" * 60)
        print("GSC DATA VALIDATION")
        print("=" * 60)
        print()
        
        # Run SQL validations
        self._run_sql_validations()
        
        # Calculate summary
        self._calculate_summary()
        
        # Generate recommendations
        self._generate_recommendations()
        
        # Print report
        self._print_report()
        
        return self.results
    
    def _run_sql_validations(self):
        """Run all SQL validation functions"""
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT * FROM gsc.run_all_validations();")
        rows = cur.fetchall()
        
        # Group results by validation type
        by_type = defaultdict(list)
        for row in rows:
            by_type[row['validation_type']].append(dict(row))
            self.results['checks'].append(dict(row))
            
            # Track worst status
            if row['status'] == 'FAIL':
                self.results['overall_status'] = 'FAIL'
            elif row['status'] == 'WARN' and self.results['overall_status'] != 'FAIL':
                self.results['overall_status'] = 'WARN'
        
        cur.close()
    
    def _calculate_summary(self):
        """Calculate summary statistics"""
        checks = self.results['checks']
        
        self.results['summary'] = {
            'total_checks': len(checks),
            'passed': len([c for c in checks if c['status'] == 'PASS']),
            'warnings': len([c for c in checks if c['status'] == 'WARN']),
            'failed': len([c for c in checks if c['status'] == 'FAIL']),
            'properties': list(set([c['property'] for c in checks if c['property']]))
        }
    
    def _generate_recommendations(self):
        """Generate actionable recommendations based on failures"""
        checks = self.results['checks']
        
        # Check for insufficient data depth
        depth_checks = [c for c in checks if c['validation_type'] == 'data_depth']
        for check in depth_checks:
            if check['status'] in ['FAIL', 'WARN']:
                days_match = None
                if 'days' in check['details']:
                    import re
                    match = re.search(r'(\d+) days', check['details'])
                    if match:
                        days_match = int(match.group(1))
                
                if days_match and days_match < 7:
                    self.results['recommendations'].append({
                        'severity': 'critical',
                        'property': check['property'],
                        'issue': f"Only {days_match} days of data",
                        'action': f"Run backfill: python scripts/backfill_historical.py --property {check['property']} --days 60"
                    })
                elif days_match and days_match < 30:
                    self.results['recommendations'].append({
                        'severity': 'medium',
                        'property': check['property'],
                        'issue': f"Only {days_match} days of data (need 30+ for MoM)",
                        'action': f"Run backfill: python scripts/backfill_historical.py --property {check['property']} --days 30"
                    })
        
        # Check for date gaps
        gap_checks = [c for c in checks if c['validation_type'] == 'date_gaps' and c['status'] != 'PASS']
        if gap_checks:
            for check in gap_checks:
                self.results['recommendations'].append({
                    'severity': 'high' if check['status'] == 'FAIL' else 'medium',
                    'property': check['property'],
                    'issue': f"Date gap found: {check['details']}",
                    'action': "Run incremental backfill to fill gaps"
                })
        
        # Check for data quality issues
        quality_checks = [c for c in checks if c['validation_type'] == 'data_quality' and c['status'] == 'FAIL']
        for check in quality_checks:
            if 'duplicate' in check['check_name']:
                self.results['recommendations'].append({
                    'severity': 'high',
                    'property': check['property'],
                    'issue': "Duplicate rows detected",
                    'action': "Run deduplication: DELETE FROM fact_gsc_daily WHERE ctid NOT IN (SELECT MIN(ctid) FROM fact_gsc_daily GROUP BY ...)"
                })
        
        # Check for missing recent data
        recent_checks = [c for c in checks if 'recent_data' in c['check_name'] and c['status'] == 'FAIL']
        for check in recent_checks:
            self.results['recommendations'].append({
                'severity': 'critical',
                'property': check['property'],
                'issue': "No data in last 7 days",
                'action': f"Run immediate ingestion: python ingestors/api/api_ingestor.py --property {check['property']} --incremental"
            })
        
        # Check for missing GA4 data
        coverage_checks = [c for c in checks if c['validation_type'] == 'property_coverage' and 'GA4 missing' in c['details']]
        for check in coverage_checks:
            self.results['recommendations'].append({
                'severity': 'medium',
                'property': check['property'],
                'issue': "GA4 data not available",
                'action': "Configure GA4 ingestion or insights will use GSC data only"
            })
    
    def _print_report(self):
        """Print human-readable validation report"""
        summary = self.results['summary']
        
        print(f"Overall Status: {self.results['overall_status']}")
        print()
        print(f"Summary:")
        print(f"  Total Checks: {summary['total_checks']}")
        print(f"  ✓ Passed:     {summary['passed']}")
        print(f"  ⚠ Warnings:   {summary['warnings']}")
        print(f"  ✗ Failed:     {summary['failed']}")
        print()
        print(f"Properties: {', '.join(summary['properties'])}")
        print()
        
        # Group checks by type
        checks_by_type = defaultdict(list)
        for check in self.results['checks']:
            checks_by_type[check['validation_type']].append(check)
        
        # Print each validation type
        for vtype, checks in checks_by_type.items():
            print(f"{vtype.replace('_', ' ').title()}:")
            for check in checks:
                status_icon = '✓' if check['status'] == 'PASS' else '⚠' if check['status'] == 'WARN' else '✗'
                print(f"  {status_icon} [{check['property'] or 'all'}] {check['check_name']}: {check['status']}")
                if check['status'] != 'PASS':
                    print(f"      {check['details']}")
            print()
        
        # Print recommendations
        if self.results['recommendations']:
            print("=" * 60)
            print("RECOMMENDATIONS")
            print("=" * 60)
            print()
            
            # Sort by severity
            severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            sorted_recs = sorted(
                self.results['recommendations'],
                key=lambda r: severity_order.get(r['severity'], 99)
            )
            
            for i, rec in enumerate(sorted_recs, 1):
                severity_icon = '🚨' if rec['severity'] == 'critical' else '⚠️' if rec['severity'] == 'high' else 'ℹ️'
                print(f"{i}. {severity_icon} [{rec['property']}] {rec['issue']}")
                print(f"   Action: {rec['action']}")
                print()
    
    def save_json(self, filepath: str):
        """Save validation results to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"Results saved to: {filepath}")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


def main():
    """Main validation routine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate GSC data quality')
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--fail-on-error', action='store_true', 
                       help='Exit with error code if validation fails')
    args = parser.parse_args()
    
    # Get database connection
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        print("Error: WAREHOUSE_DSN environment variable not set")
        sys.exit(1)
    
    # Run validation
    validator = DataValidator(dsn)
    
    try:
        results = validator.run_all_validations()
        
        # Save JSON output
        if args.output:
            validator.save_json(args.output)
        
        # Exit with error if requested and validation failed
        if args.fail_on_error and results['overall_status'] in ['FAIL', 'WARN']:
            print()
            print("Validation failed - exiting with error code")
            sys.exit(1)
        
    finally:
        validator.close()


if __name__ == '__main__':
    main()
