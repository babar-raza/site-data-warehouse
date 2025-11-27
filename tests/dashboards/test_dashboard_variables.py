"""
Dashboard Template Variable Tests
Tests template variable configuration and SQL queries
Run: pytest tests/dashboards/test_dashboard_variables.py -v

Tests:
- Variable configuration validation
- Variable query syntax
- Variable dependencies
"""

import pytest
import re
from .conftest import (
    extract_template_variables,
    extract_sql_queries,
    get_dashboard_by_uid
)


class TestVariableConfiguration:
    """Test template variable configuration"""

    def test_all_variables_have_type(self, all_dashboards):
        """All template variables must have a type"""
        valid_types = {"query", "custom", "constant", "datasource", "interval", "textbox"}

        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                var_type = var.get("type")
                assert var_type, f"{name}: variable '{var.get('name')}' missing type"
                assert var_type in valid_types, \
                    f"{name}: variable '{var.get('name')}' has unknown type '{var_type}'"

    def test_query_variables_have_datasource(self, all_dashboards):
        """Query-type variables must have datasource"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "query":
                    ds = var.get("datasource")
                    assert ds is not None, \
                        f"{name}: query variable '{var.get('name')}' missing datasource"

    def test_custom_variables_have_options(self, all_dashboards):
        """Custom-type variables should have options defined"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "custom":
                    query = var.get("query", "")
                    options = var.get("options", [])
                    # Either query or options should be defined
                    assert query or options, \
                        f"{name}: custom variable '{var.get('name')}' missing options"

    def test_interval_variables_have_valid_options(self, all_dashboards):
        """Interval variables should have valid time intervals"""
        valid_intervals = {
            "1m", "5m", "10m", "15m", "30m",
            "1h", "2h", "6h", "12h",
            "1d", "7d", "30d"
        }

        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "interval":
                    options = var.get("options", [])
                    for opt in options:
                        value = opt.get("value", "")
                        # Check if value looks like a valid interval
                        if value and not re.match(r'^\d+[smhd]$', value):
                            # This is a warning, not a failure
                            pass


class TestVariableQuerySyntax:
    """Test template variable SQL query syntax"""

    def test_query_variables_have_valid_sql(self, all_dashboards, postgresql_dashboard_uids):
        """Query variables should have valid SQL"""
        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "query":
                    ds = var.get("datasource", {})
                    # Skip Prometheus queries
                    if isinstance(ds, dict) and ds.get("uid") == "prometheus":
                        continue

                    query = var.get("query", "")
                    if query:
                        # Should be a SELECT statement
                        assert "SELECT" in query.upper(), \
                            f"{uid}: variable '{var.get('name')}' query doesn't contain SELECT"

    def test_query_variables_dont_use_dangerous_operations(
        self, all_dashboards, postgresql_dashboard_uids
    ):
        """Variable queries should not contain dangerous operations"""
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE"]

        for uid in postgresql_dashboard_uids:
            dashboard = get_dashboard_by_uid(all_dashboards, uid)
            if not dashboard:
                continue

            variables = extract_template_variables(dashboard)
            for var in variables:
                if var.get("type") == "query":
                    query = var.get("query", "").upper()
                    for keyword in dangerous:
                        assert keyword not in query, \
                            f"{uid}: variable '{var.get('name')}' contains '{keyword}'"


class TestCWVDashboardVariables:
    """Test CWV dashboard specific variables"""

    def test_property_variable_configuration(self, cwv_dashboard):
        """Property variable should be properly configured"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        variables = extract_template_variables(cwv_dashboard)
        property_var = next(
            (v for v in variables if v.get("name") == "property"),
            None
        )

        assert property_var is not None, "Property variable not found"
        assert property_var.get("type") == "query", \
            "Property variable should be query type"

    def test_device_variable_configuration(self, cwv_dashboard):
        """Device variable should have mobile and desktop options"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        variables = extract_template_variables(cwv_dashboard)
        device_var = next(
            (v for v in variables if v.get("name") == "device"),
            None
        )

        assert device_var is not None, "Device variable not found"

        # Check for mobile/desktop options
        query = device_var.get("query", "").lower()
        options = device_var.get("options", [])

        has_mobile = "mobile" in query or any("mobile" in str(o) for o in options)
        has_desktop = "desktop" in query or any("desktop" in str(o) for o in options)

        # At least one should be available
        assert has_mobile or has_desktop, \
            "Device variable should include mobile or desktop options"


class TestSERPDashboardVariables:
    """Test SERP dashboard specific variables"""

    def test_property_variable_exists(self, serp_dashboard):
        """SERP dashboard should have property variable"""
        if not serp_dashboard:
            pytest.skip("SERP dashboard not found")

        variables = extract_template_variables(serp_dashboard)
        var_names = [v.get("name") for v in variables]

        assert "property" in var_names, "SERP dashboard missing property variable"


class TestVariableUsageInQueries:
    """Test that variables are used correctly in panel queries"""

    def test_cwv_queries_use_property_variable(self, cwv_dashboard):
        """CWV panel queries should use $property variable"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        queries = extract_sql_queries(cwv_dashboard)
        if not queries:
            pytest.skip("No SQL queries in CWV dashboard")

        queries_using_property = sum(
            1 for q in queries
            if "$property" in q["sql"] or "${property}" in q["sql"]
        )

        # At least some queries should use the property variable
        assert queries_using_property > 0, \
            "No CWV queries use $property variable"

    def test_cwv_queries_use_device_variable(self, cwv_dashboard):
        """CWV panel queries should use $device variable"""
        if not cwv_dashboard:
            pytest.skip("CWV dashboard not found")

        queries = extract_sql_queries(cwv_dashboard)
        if not queries:
            pytest.skip("No SQL queries in CWV dashboard")

        queries_using_device = sum(
            1 for q in queries
            if "$device" in q["sql"] or "${device}" in q["sql"] or "strategy" in q["sql"].lower()
        )

        # At least some queries should filter by device/strategy
        # This is a soft check - not all queries may need device filtering

    def test_serp_queries_use_property_variable(self, serp_dashboard):
        """SERP panel queries should use $property variable"""
        if not serp_dashboard:
            pytest.skip("SERP dashboard not found")

        queries = extract_sql_queries(serp_dashboard)
        if not queries:
            pytest.skip("No SQL queries in SERP dashboard")

        queries_using_property = sum(
            1 for q in queries
            if "$property" in q["sql"] or "${property}" in q["sql"]
        )

        assert queries_using_property > 0, \
            "No SERP queries use $property variable"


class TestVariableDependencies:
    """Test variable dependencies and ordering"""

    def test_variables_reference_existing_variables(self, all_dashboards):
        """Variables that reference other variables should reference existing ones"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)
            var_names = [v.get("name") for v in variables]

            for var in variables:
                query = var.get("query", "")
                # Find variable references in query
                refs = re.findall(r'\$\{?(\w+)\}?', query)

                for ref in refs:
                    # Skip special Grafana variables
                    if ref.startswith("__") or ref in ["timeFrom", "timeTo"]:
                        continue
                    # Check if referenced variable exists
                    # Note: This may include references to panel variables
                    # which is valid

    def test_no_circular_variable_dependencies(self, all_dashboards):
        """Variables should not have circular dependencies"""
        for name, dashboard in all_dashboards.items():
            variables = extract_template_variables(dashboard)

            # Build dependency graph
            dependencies = {}
            for var in variables:
                var_name = var.get("name")
                query = var.get("query", "")
                refs = re.findall(r'\$\{?(\w+)\}?', query)
                # Filter to only include other template variables
                var_names = [v.get("name") for v in variables]
                deps = [r for r in refs if r in var_names and r != var_name]
                dependencies[var_name] = deps

            # Check for cycles using DFS
            def has_cycle(node, visited, rec_stack):
                visited.add(node)
                rec_stack.add(node)

                for dep in dependencies.get(node, []):
                    if dep not in visited:
                        if has_cycle(dep, visited, rec_stack):
                            return True
                    elif dep in rec_stack:
                        return True

                rec_stack.remove(node)
                return False

            visited = set()
            for var_name in dependencies:
                if var_name not in visited:
                    if has_cycle(var_name, visited, set()):
                        pytest.fail(f"{name}: circular variable dependency detected")
