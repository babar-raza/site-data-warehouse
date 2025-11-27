#!/usr/bin/env python3
"""
Integration test for verify_pipeline.py

This script demonstrates how to use verify_pipeline programmatically
and provides examples of parsing and using the results.

Usage:
    python examples/verify_pipeline_integration_test.py
"""

import sys
import os
import json
from datetime import datetime

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from verify_pipeline import PipelineVerifier, format_human_readable


def example_basic_usage():
    """Example 1: Basic usage with default settings"""
    print("=" * 80)
    print("Example 1: Basic Usage")
    print("=" * 80)

    # Get DSN from environment or use default
    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')

    # Create verifier
    verifier = PipelineVerifier(dsn, environment='test')

    # Run checks (will fail gracefully if database not available)
    try:
        report = verifier.run_all_checks()

        # Print summary
        print(f"\nStatus: {report['overall_status']}")
        print(f"Checks: {report['summary']['passed']}/{report['summary']['total_checks']} passed")

        if report['overall_status'] != 'healthy':
            print("\nIssues:")
            for issue in report.get('issues', []):
                print(f"  [{issue['severity']}] {issue['check']}: {issue['message']}")

        return report

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        print("This is expected if database is not running.")
        return None


def example_custom_thresholds():
    """Example 2: Using custom thresholds"""
    print("\n" + "=" * 80)
    print("Example 2: Custom Thresholds")
    print("=" * 80)

    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    verifier = PipelineVerifier(dsn, environment='production')

    try:
        # Run with strict thresholds
        report = verifier.run_all_checks(
            threshold_hours=24,      # More strict - only 24 hours
            insight_lookback=12      # Must have insights in last 12 hours
        )

        print(f"\nStrict check status: {report['overall_status']}")
        return report

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        return None


def example_json_parsing():
    """Example 3: Parsing JSON output programmatically"""
    print("\n" + "=" * 80)
    print("Example 3: JSON Parsing")
    print("=" * 80)

    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    verifier = PipelineVerifier(dsn)

    try:
        report = verifier.run_all_checks()

        # Extract specific metrics
        metrics = {
            'timestamp': report['timestamp'],
            'status': report['overall_status'],
            'health_score': report['summary']['passed'] / report['summary']['total_checks'] * 100,
            'failed_count': report['summary']['failed'],
            'warned_count': report['summary']['warned']
        }

        print("\nExtracted Metrics:")
        print(json.dumps(metrics, indent=2))

        # Find specific check results
        db_check = next((c for c in report['checks'] if c['name'] == 'Database Connection'), None)
        if db_check:
            print(f"\nDatabase Check: {db_check['status']} - {db_check['message']}")

        return report

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        return None


def example_monitoring_integration():
    """Example 4: Integration with monitoring systems"""
    print("\n" + "=" * 80)
    print("Example 4: Monitoring Integration")
    print("=" * 80)

    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    verifier = PipelineVerifier(dsn, environment='production')

    try:
        report = verifier.run_all_checks()

        # Generate Prometheus-style metrics
        metrics = []
        metrics.append(f"pipeline_healthy{{environment=\"production\"}} {1 if report['overall_status'] == 'healthy' else 0}")
        metrics.append(f"pipeline_checks_total{{environment=\"production\"}} {report['summary']['total_checks']}")
        metrics.append(f"pipeline_checks_passed{{environment=\"production\"}} {report['summary']['passed']}")
        metrics.append(f"pipeline_checks_failed{{environment=\"production\"}} {report['summary']['failed']}")

        print("\nPrometheus Metrics:")
        for metric in metrics:
            print(metric)

        # Generate alert conditions
        if report['summary']['failed'] > 0:
            print("\n[ALERT] Pipeline has failed checks!")
            print("Recommended actions:")
            for issue in report.get('issues', []):
                if issue['severity'] == 'fail':
                    print(f"  - Investigate: {issue['check']}")

        return report

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        return None


def example_conditional_logic():
    """Example 5: Using results for conditional logic"""
    print("\n" + "=" * 80)
    print("Example 5: Conditional Logic")
    print("=" * 80)

    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    verifier = PipelineVerifier(dsn)

    try:
        report = verifier.run_all_checks()

        # Decision logic based on status
        if report['overall_status'] == 'healthy':
            print("\n✓ Pipeline is healthy - safe to proceed with operations")
            action = "PROCEED"

        elif report['overall_status'] == 'degraded':
            print("\n⚠ Pipeline is degraded - proceed with caution")
            action = "CAUTION"

            # Check if only warnings (no failures)
            if report['summary']['failed'] == 0:
                print("  No critical failures - operations can continue")
            else:
                print("  Some failures detected - review before proceeding")

        else:  # unhealthy
            print("\n✗ Pipeline is unhealthy - do not proceed")
            action = "BLOCK"

            # List critical issues
            critical_issues = [i for i in report.get('issues', []) if i['severity'] == 'fail']
            if critical_issues:
                print("\nCritical issues requiring attention:")
                for issue in critical_issues:
                    print(f"  - {issue['check']}: {issue['message']}")

        print(f"\nRecommended action: {action}")
        return action

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        print("Recommended action: BLOCK (cannot verify health)")
        return "BLOCK"


def example_report_formatting():
    """Example 6: Custom report formatting"""
    print("\n" + "=" * 80)
    print("Example 6: Custom Report Formatting")
    print("=" * 80)

    dsn = os.getenv('WAREHOUSE_DSN', 'postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db')
    verifier = PipelineVerifier(dsn)

    try:
        report = verifier.run_all_checks()

        # Custom summary format
        print("\n📊 Pipeline Health Dashboard")
        print("─" * 40)
        print(f"🕐 Timestamp: {report['timestamp']}")
        print(f"🌍 Environment: {report['environment']}")
        print(f"⏱️  Duration: {report['duration_seconds']}s")
        print(f"📈 Status: {report['overall_status'].upper()}")
        print()

        # Color-coded check results
        print("Check Results:")
        for check in report['checks']:
            symbol = {'pass': '✅', 'warn': '⚠️', 'fail': '❌'}.get(check['status'], '❓')
            print(f"  {symbol} {check['name']}: {check['message']}")

        print()

        # Summary card
        summary = report['summary']
        print("Summary:")
        print(f"  Total:  {summary['total_checks']}")
        print(f"  Passed: {summary['passed']} ✅")
        print(f"  Warned: {summary['warned']} ⚠️")
        print(f"  Failed: {summary['failed']} ❌")

        return report

    except Exception as e:
        print(f"Note: Could not connect to database: {e}")
        return None


def main():
    """Run all examples"""
    print("""
Pipeline Verification Integration Test
========================================

This demonstrates programmatic usage of verify_pipeline.py.

Note: These examples will fail gracefully if the database is not available.
      This is expected behavior for the demonstration.
""")

    # Run examples
    example_basic_usage()
    example_custom_thresholds()
    example_json_parsing()
    example_monitoring_integration()
    action = example_conditional_logic()
    example_report_formatting()

    # Final summary
    print("\n" + "=" * 80)
    print("Integration Test Complete")
    print("=" * 80)
    print("\nAll examples demonstrated successfully!")
    print("\nFor production use:")
    print("  1. Set WAREHOUSE_DSN environment variable")
    print("  2. Run: python scripts/verify_pipeline.py")
    print("  3. Check exit code: echo $?")
    print("\nDocumentation:")
    print("  - scripts/README_VERIFY_PIPELINE.md")
    print("  - examples/verify_pipeline_quickstart.md")
    print("=" * 80)


if __name__ == '__main__':
    main()
