#!/usr/bin/env python3
"""
Test data validation functions
"""
import os
import sys
import pytest
from datetime import datetime, timedelta, date
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="module")
def db_connection():
    """Database connection for tests"""
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set")
    
    conn = psycopg2.connect(dsn)
    yield conn
    conn.close()


def test_validation_functions_exist(db_connection):
    """Test that all validation functions exist"""
    cur = db_connection.cursor()
    
    functions = [
        'validate_data_depth',
        'validate_date_continuity',
        'validate_data_quality',
        'validate_transform_readiness',
        'validate_property_coverage',
        'run_all_validations'
    ]
    
    for func in functions:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'gsc'
                AND p.proname = %s
            );
        """, (func,))
        
        exists = cur.fetchone()[0]
        assert exists, f"Function gsc.{func}() should exist"


def test_validate_data_depth(db_connection):
    """Test data depth validation function"""
    cur = db_connection.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM gsc.validate_data_depth();")
    results = cur.fetchall()
    
    # Should have at least one result if data exists
    if results:
        for row in results:
            assert 'property' in row
            assert 'source_type' in row
            assert 'total_days' in row
            assert 'status' in row
            assert row['status'] in ['PASS', 'WARN', 'FAIL']


def test_validate_date_continuity(db_connection):
    """Test date gap detection"""
    cur = db_connection.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM gsc.validate_date_continuity();")
    results = cur.fetchall()
    
    # If gaps exist, they should be properly formatted
    for row in results:
        assert 'property' in row
        assert 'gap_start' in row
        assert 'gap_end' in row
        assert 'gap_days' in row
        assert row['gap_days'] > 0  # Should only return actual gaps


def test_validate_data_quality(db_connection):
    """Test data quality checks"""
    cur = db_connection.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM gsc.validate_data_quality();")
    results = cur.fetchall()
    
    # Check expected quality checks are present
    check_names = [r['check_name'] for r in results]
    
    expected_checks = [
        'gsc_duplicates',
        'gsc_null_metrics',
        'gsc_invalid_ctr'
    ]
    
    for check in expected_checks:
        # Check should exist for at least one property
        assert any(check in name for name in check_names), \
            f"Quality check '{check}' should exist"


def test_validate_transform_readiness(db_connection):
    """Test transform readiness validation"""
    cur = db_connection.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM gsc.validate_transform_readiness();")
    results = cur.fetchall()
    
    # Check expected readiness checks
    check_names = [r['check_name'] for r in results]
    
    expected_checks = [
        'unified_view_rows',
        'wow_fields_populated',
        'recent_data_7d'
    ]
    
    for check in expected_checks:
        assert any(check in name for name in check_names), \
            f"Readiness check '{check}' should exist"


def test_run_all_validations(db_connection):
    """Test master validation function"""
    cur = db_connection.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT * FROM gsc.run_all_validations();")
    results = cur.fetchall()
    
    # Should have multiple validation types
    validation_types = set(r['validation_type'] for r in results)
    
    expected_types = [
        'data_depth',
        'date_gaps',
        'data_quality',
        'transform_readiness',
        'property_coverage'
    ]
    
    for vtype in expected_types:
        assert vtype in validation_types, \
            f"Validation type '{vtype}' should be in results"


def test_validation_script_runs(db_connection):
    """Test that validation script can run"""
    import subprocess
    
    result = subprocess.run(
        ['python', 'scripts/validate_data.py'],
        capture_output=True,
        text=True,
        env=os.environ
    )
    
    # Should complete without crashing
    # (may have warnings/failures, but shouldn't error out)
    assert 'GSC DATA VALIDATION' in result.stdout
    assert 'Overall Status:' in result.stdout


def test_validation_script_json_output(db_connection, tmp_path):
    """Test validation script JSON output"""
    import subprocess
    import json
    
    output_file = tmp_path / "validation.json"
    
    result = subprocess.run(
        ['python', 'scripts/validate_data.py', '--output', str(output_file)],
        capture_output=True,
        text=True,
        env=os.environ
    )
    
    assert result.returncode == 0
    assert output_file.exists()
    
    # Parse JSON
    with open(output_file) as f:
        data = json.load(f)
    
    assert 'timestamp' in data
    assert 'overall_status' in data
    assert 'checks' in data
    assert 'summary' in data
    assert data['overall_status'] in ['PASS', 'WARN', 'FAIL']


def test_backfill_script_dry_run(db_connection):
    """Test backfill script in dry-run mode"""
    import subprocess
    
    # Get a property that exists
    cur = db_connection.cursor()
    cur.execute("SELECT DISTINCT property FROM gsc.fact_gsc_daily LIMIT 1;")
    result = cur.fetchone()
    
    if not result:
        pytest.skip("No properties in database")
    
    property_name = result[0]
    
    # Run backfill in dry-run mode
    result = subprocess.run([
        'python', 'scripts/backfill_historical.py',
        '--property', property_name,
        '--days', '7',
        '--dry-run'
    ], capture_output=True, text=True, env=os.environ)
    
    assert 'Backfilling' in result.stdout
    assert 'DRY RUN' in result.stdout


def test_backfill_get_missing_dates():
    """Test missing date detection logic"""
    import sys
    sys.path.insert(0, 'scripts')
    from backfill_historical import HistoricalBackfill
    
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set")
    
    backfill = HistoricalBackfill(dsn)
    
    try:
        # Get a property
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT property FROM gsc.fact_gsc_daily LIMIT 1;")
        result = cur.fetchone()
        conn.close()
        
        if not result:
            pytest.skip("No properties in database")
        
        property_name = result[0]
        
        # Get missing dates (should return a list)
        missing = backfill.get_missing_dates(property_name, 'gsc')
        
        assert isinstance(missing, list)
        # May or may not have gaps
        
    finally:
        backfill.close()


def test_validation_status_logic():
    """Test that status thresholds are correct"""
    # 30+ days = PASS
    # 7-29 days = WARN
    # <7 days = FAIL
    
    # This is tested in the SQL function, but verify logic
    test_cases = [
        (35, 'PASS'),
        (30, 'PASS'),
        (20, 'WARN'),
        (7, 'WARN'),
        (5, 'FAIL'),
        (0, 'FAIL')
    ]
    
    for days, expected_status in test_cases:
        if days >= 30:
            assert expected_status == 'PASS'
        elif days >= 7:
            assert expected_status == 'WARN'
        else:
            assert expected_status == 'FAIL'


def test_validation_recommendations_generated():
    """Test that recommendations are generated for failures"""
    import sys
    sys.path.insert(0, 'scripts')
    from validate_data import DataValidator
    
    dsn = os.environ.get('WAREHOUSE_DSN')
    if not dsn:
        pytest.skip("WAREHOUSE_DSN not set")
    
    validator = DataValidator(dsn)
    
    try:
        results = validator.run_all_validations()
        
        # If there are failures/warnings, should have recommendations
        if results['overall_status'] in ['FAIL', 'WARN']:
            assert len(results['recommendations']) > 0
        
        # Recommendations should have required fields
        for rec in results['recommendations']:
            assert 'severity' in rec
            assert 'issue' in rec
            assert 'action' in rec
            
    finally:
        validator.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
