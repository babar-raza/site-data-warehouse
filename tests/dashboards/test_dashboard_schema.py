"""
Dashboard JSON Schema Validation Tests
Mode: Mock (no database required)
Run: pytest tests/dashboards/test_dashboard_schema.py -v

Tests:
- Dashboard presence and completeness
- Panel structure validation
- Datasource configuration
- Template variable configuration
"""

import pytest
from .conftest import (
    extract_all_panels,
    extract_template_variables,
    get_dashboard_by_uid
)


class TestDashboardSchemaValidation:
    """Validate dashboard JSON structure and required fields"""

    def test_all_expected_dashboards_exist(self, dashboard_uids, all_dashboards):
        """Verify all expected dashboards are present"""
        loaded_uids = [d.get("uid") for d in all_dashboards.values()]
        missing = []
        for uid in dashboard_uids:
            if uid not in loaded_uids:
                missing.append(uid)
        assert not missing, f"Missing dashboards: {missing}"

    def test_dashboards_have_required_fields(self, all_dashboards):
        """Each dashboard must have essential fields"""
        required_fields = ["title", "uid", "panels", "schemaVersion"]

        for name, dashboard in all_dashboards.items():
            for field in required_fields:
                assert field in dashboard, f"{name}: missing required field '{field}'"

    def test_dashboards_have_valid_schema_version(self, all_dashboards):
        """Schema version should be a positive integer"""
        for name, dashboard in all_dashboards.items():
            schema_version = dashboard.get("schemaVersion")
            assert isinstance(schema_version, int), \
                f"{name}: schemaVersion should be integer, got {type(schema_version)}"
            assert schema_version > 0, \
                f"{name}: schemaVersion should be positive, got {schema_version}"

    def test_dashboards_have_valid_uid(self, all_dashboards):
        """Dashboard UIDs should be non-empty strings"""
        for name, dashboard in all_dashboards.items():
            uid = dashboard.get("uid")
            assert isinstance(uid, str) and uid, \
                f"{name}: uid should be non-empty string"

    def test_dashboard_uids_are_unique(self, all_dashboards):
        """All dashboard UIDs must be unique"""
        uids = [d.get("uid") for d in all_dashboards.values()]
        duplicates = [uid for uid in uids if uids.count(uid) > 1]
        assert not duplicates, f"Duplicate UIDs found: {set(duplicates)}"


class TestPanelStructure:
    """Validate panel structure within dashboards"""

    def test_panels_have_required_fields(self, all_dashboards):
        """Each panel must have id, title, type, and gridPos"""
        required_fields = ["id", "type", "gridPos"]

        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                for field in required_fields:
                    assert field in panel, \
                        f"{name}: panel '{panel.get('title', 'Untitled')}' missing '{field}'"

    def test_panel_types_are_valid(self, all_dashboards):
        """Panel types must be recognized Grafana types"""
        valid_types = {
            "stat", "gauge", "timeseries", "table",
            "piechart", "bargauge", "barchart", "graph",
            "text", "row", "heatmap", "logs", "nodeGraph",
            "news", "alertlist", "dashlist", "histogram"
        }

        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                panel_type = panel.get("type")
                assert panel_type in valid_types, \
                    f"{name}: panel '{panel.get('title')}' has unrecognized type '{panel_type}'"

    def test_panel_ids_are_unique(self, all_dashboards):
        """Panel IDs must be unique within each dashboard"""
        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            panel_ids = [p.get("id") for p in panels]
            duplicates = [pid for pid in panel_ids if panel_ids.count(pid) > 1]
            assert not duplicates, \
                f"{name}: duplicate panel IDs found: {set(duplicates)}"

    def test_panel_ids_are_positive_integers(self, all_dashboards):
        """Panel IDs should be positive integers"""
        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                panel_id = panel.get("id")
                assert isinstance(panel_id, int) and panel_id > 0, \
                    f"{name}: panel '{panel.get('title')}' has invalid id: {panel_id}"

    def test_grid_positions_are_valid(self, all_dashboards):
        """Panel grid positions should have valid x, y, w, h values"""
        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                grid_pos = panel.get("gridPos", {})
                # Check all required gridPos fields
                for field in ["x", "y", "w", "h"]:
                    assert field in grid_pos, \
                        f"{name}: panel '{panel.get('title')}' gridPos missing '{field}'"
                    value = grid_pos[field]
                    assert isinstance(value, (int, float)) and value >= 0, \
                        f"{name}: panel '{panel.get('title')}' gridPos.{field} invalid: {value}"

    def test_panel_widths_within_bounds(self, all_dashboards):
        """Panel widths should be within Grafana's 24-column grid"""
        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                grid_pos = panel.get("gridPos", {})
                x = grid_pos.get("x", 0)
                w = grid_pos.get("w", 0)
                assert x + w <= 24, \
                    f"{name}: panel '{panel.get('title')}' exceeds grid width (x={x}, w={w})"


class TestDataSourceConfiguration:
    """Validate datasource configuration"""

    def test_data_panels_have_datasource(self, all_dashboards):
        """All data panels must have datasource configured"""
        non_data_types = {"row", "text"}

        for name, dashboard in all_dashboards.items():
            panels = extract_all_panels(dashboard)
            for panel in panels:
                if panel.get("type") in non_data_types:
                    continue

                targets = panel.get("targets", [])
                if not targets:
                    continue  # Some panels use fieldConfig

                # Datasource can be at panel level or target level
                panel_ds = panel.get("datasource")

                for target in targets:
                    target_ds = target.get("datasource")
                    # Either panel or target should have datasource
                    has_datasource = panel_ds is not None or target_ds is not None
                    assert has_datasource, \
                        f"{name}: panel '{panel.get('title')}' missing datasource"

    def test_postgresql_dashboards_use_correct_datasource(
        self, all_dashboards, postgresql_dashboard_uids
    ):
        """PostgreSQL dashboards should use postgres-gsc datasource"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            panels = extract_all_panels(dashboard)
            for panel in panels:
                if panel.get("type") in ["row", "text"]:
                    continue

                for target in panel.get("targets", []):
                    ds = target.get("datasource", {})
                    if isinstance(ds, dict) and ds.get("type"):
                        # Allow both postgres-gsc and grafana-postgresql-datasource
                        ds_uid = ds.get("uid", "")
                        assert ds_uid == "postgres-gsc", \
                            f"{uid}: panel '{panel.get('title')}' should use postgres-gsc, got {ds_uid}"

    def test_prometheus_dashboards_use_correct_datasource(
        self, all_dashboards, prometheus_dashboard_uids
    ):
        """Prometheus dashboards should use prometheus datasource"""
        for uid in prometheus_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            panels = extract_all_panels(dashboard)
            for panel in panels:
                if panel.get("type") in ["row", "text"]:
                    continue

                for target in panel.get("targets", []):
                    ds = target.get("datasource", {})
                    if isinstance(ds, dict) and ds.get("type"):
                        ds_uid = ds.get("uid", "")
                        assert ds_uid == "prometheus", \
                            f"{uid}: panel '{panel.get('title')}' should use prometheus, got {ds_uid}"


class TestTemplateVariables:
    """Validate template variable configuration"""

    def test_cwv_dashboard_has_required_variables(self, cwv_dashboard):
        """CWV dashboard must have property and device variables"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        variables = extract_template_variables(cwv_dashboard)
        var_names = [v.get("name") for v in variables]

        assert "property" in var_names, "CWV dashboard missing 'property' variable"
        assert "device" in var_names, "CWV dashboard missing 'device' variable"

    def test_serp_dashboard_has_required_variables(self, serp_dashboard):
        """SERP dashboard must have property variable"""
        if not serp_dashboard:
            pytest.skip("SERP dashboard not found")

        variables = extract_template_variables(serp_dashboard)
        var_names = [v.get("name") for v in variables]

        assert "property" in var_names, "SERP dashboard missing 'property' variable"

    def test_query_type_variables_have_valid_query(self, all_dashboards):
        """Template variables of type 'query' should have SQL query"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "query":
                    query = var.get("query", "")
                    # Skip if it's a Prometheus query
                    ds = var.get("datasource", {})
                    if isinstance(ds, dict) and ds.get("uid") == "prometheus":
                        continue

                    assert query, \
                        f"{name}: variable '{var.get('name')}' has empty query"

    def test_variables_have_names(self, all_dashboards):
        """All template variables must have names"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                var_name = var.get("name")
                assert var_name and isinstance(var_name, str), \
                    f"{name}: template variable missing name"

    def test_variable_names_are_unique(self, all_dashboards):
        """Template variable names must be unique within each dashboard"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            var_names = [v.get("name") for v in variables]
            duplicates = [vn for vn in var_names if var_names.count(vn) > 1]
            assert not duplicates, \
                f"{name}: duplicate variable names found: {set(duplicates)}"


class TestDashboardMetadata:
    """Validate dashboard metadata configuration"""

    def test_dashboards_have_titles(self, all_dashboards):
        """All dashboards must have non-empty titles"""
        for name, dashboard in all_dashboards.items():
            title = dashboard.get("title")
            assert title and isinstance(title, str), \
                f"{name}: dashboard missing or invalid title"

    def test_dashboards_have_time_configuration(self, all_dashboards):
        """Dashboards should have time range configuration"""
        for name, dashboard in all_dashboards.items():
            time_config = dashboard.get("time")
            if time_config:
                assert "from" in time_config, f"{name}: time config missing 'from'"
                assert "to" in time_config, f"{name}: time config missing 'to'"

    def test_dashboards_have_valid_refresh_interval(self, all_dashboards):
        """Dashboard refresh intervals should be valid if set"""
        valid_intervals = {
            "", "5s", "10s", "30s", "1m", "5m", "15m", "30m",
            "1h", "2h", "1d", False, None
        }

        for name, dashboard in all_dashboards.items():
            refresh = dashboard.get("refresh")
            # Some dashboards may not have refresh set
            if refresh is not None and refresh not in valid_intervals:
                # Check if it matches the pattern
                import re
                if not re.match(r'^\d+[smhd]$', str(refresh)):
                    pytest.fail(f"{name}: invalid refresh interval '{refresh}'")
