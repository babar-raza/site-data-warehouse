"""
Test script for Actions Command Center Dashboard setup
Validates SQL views and dashboard configuration
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_dashboard_json_valid():
    """Test that the dashboard JSON is valid and well-formed"""
    dashboard_path = project_root / "grafana" / "provisioning" / "dashboards" / "actions-command-center.json"

    print(f"Testing dashboard JSON at: {dashboard_path}")
    assert dashboard_path.exists(), f"Dashboard file not found: {dashboard_path}"

    with open(dashboard_path, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)

    # Validate basic structure
    assert dashboard.get('title') == 'Actions Command Center', "Dashboard title mismatch"
    assert dashboard.get('uid') == 'actions-center', "Dashboard UID mismatch"
    assert 'panels' in dashboard, "No panels defined"
    assert len(dashboard['panels']) >= 8, f"Expected at least 8 panels, got {len(dashboard['panels'])}"

    # Validate property filter variable
    assert 'templating' in dashboard, "No templating section"
    assert 'list' in dashboard['templating'], "No template variables"

    variables = dashboard['templating']['list']
    property_var = next((v for v in variables if v.get('name') == 'property'), None)
    assert property_var is not None, "Property filter variable not found"
    assert property_var.get('type') == 'query', "Property variable should be query type"

    # Validate refresh interval
    assert dashboard.get('refresh') == '5m', "Auto-refresh should be 5m"

    # Validate tags
    tags = dashboard.get('tags', [])
    assert 'actions' in tags, "Missing 'actions' tag"
    assert 'command-center' in tags, "Missing 'command-center' tag"

    print("[PASS] Dashboard JSON is valid")
    return True


def test_sql_views_file_exists():
    """Test that SQL views file exists"""
    sql_path = project_root / "sql" / "28_actions_metrics_views.sql"

    print(f"Testing SQL views file at: {sql_path}")
    assert sql_path.exists(), f"SQL views file not found: {sql_path}"

    with open(sql_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Validate key views exist
    expected_views = [
        'vw_actions_by_status',
        'vw_actions_by_priority',
        'vw_actions_timeline',
        'vw_actions_completion_rate',
        'vw_actions_by_type',
        'vw_pending_actions_summary',
        'vw_actions_by_effort',
        'vw_actions_impact_summary',
        'vw_actions_recent_activity'
    ]

    for view in expected_views:
        assert view in content, f"View {view} not found in SQL file"

    # Validate indexes
    expected_indexes = [
        'idx_actions_property_status',
        'idx_actions_property_created',
        'idx_actions_property_completed',
        'idx_actions_priority',
        'idx_actions_effort',
        'idx_actions_action_type'
    ]

    for index in expected_indexes:
        assert index in content, f"Index {index} not found in SQL file"

    print("[PASS] SQL views file is valid")
    return True


def test_dashboard_panel_queries():
    """Test that dashboard panels have valid PostgreSQL queries"""
    dashboard_path = project_root / "grafana" / "provisioning" / "dashboards" / "actions-command-center.json"

    with open(dashboard_path, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)

    panels = dashboard.get('panels', [])
    panels_with_queries = 0

    for panel in panels:
        targets = panel.get('targets', [])
        for target in targets:
            if 'rawSql' in target:
                panels_with_queries += 1
                query = target['rawSql']

                # Basic SQL validation
                assert 'gsc.actions' in query, f"Panel '{panel.get('title')}' doesn't query gsc.actions"
                assert '$property' in query or 'property' in query.lower(), \
                    f"Panel '{panel.get('title')}' doesn't use property filter"

    assert panels_with_queries > 0, "No panels with SQL queries found"
    print(f"[PASS] Found {panels_with_queries} panels with valid queries")
    return True


def test_panel_layout():
    """Test that panels have proper grid positioning"""
    dashboard_path = project_root / "grafana" / "provisioning" / "dashboards" / "actions-command-center.json"

    with open(dashboard_path, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)

    panels = dashboard.get('panels', [])

    for panel in panels:
        grid_pos = panel.get('gridPos', {})
        assert 'h' in grid_pos, f"Panel '{panel.get('title')}' missing height"
        assert 'w' in grid_pos, f"Panel '{panel.get('title')}' missing width"
        assert 'x' in grid_pos, f"Panel '{panel.get('title')}' missing x position"
        assert 'y' in grid_pos, f"Panel '{panel.get('title')}' missing y position"

        # Validate reasonable dimensions
        assert 0 <= grid_pos['x'] < 24, f"Panel '{panel.get('title')}' x position out of range"
        assert 0 < grid_pos['w'] <= 24, f"Panel '{panel.get('title')}' width out of range"
        assert grid_pos['h'] > 0, f"Panel '{panel.get('title')}' height must be positive"

    print(f"[PASS] All {len(panels)} panels have valid grid positions")
    return True


def test_documentation_exists():
    """Test that documentation file was created"""
    doc_path = project_root / "docs" / "guides" / "ACTIONS_COMMAND_CENTER.md"

    print(f"Testing documentation at: {doc_path}")
    assert doc_path.exists(), f"Documentation not found: {doc_path}"

    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Validate key sections
    assert '# Actions Command Center Dashboard' in content, "Missing main heading"
    assert '## Features' in content, "Missing features section"
    assert '## Setup Instructions' in content, "Missing setup section"
    assert '## Troubleshooting' in content, "Missing troubleshooting section"

    print("[PASS] Documentation is complete")
    return True


def test_schema_compatibility():
    """Test that views are compatible with the actions table schema"""
    sql_path = project_root / "sql" / "28_actions_metrics_views.sql"

    with open(sql_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Columns that should be referenced
    required_columns = [
        'property',
        'status',
        'priority',
        'effort',
        'action_type',
        'created_at',
        'completed_at',
        'estimated_impact'
    ]

    for column in required_columns:
        assert column in content, f"Column {column} not found in views"

    print("[PASS] SQL views are compatible with actions schema")
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing Actions Command Center Dashboard Setup")
    print("="*60 + "\n")

    tests = [
        test_dashboard_json_valid,
        test_sql_views_file_exists,
        test_dashboard_panel_queries,
        test_panel_layout,
        test_documentation_exists,
        test_schema_compatibility
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}")
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
