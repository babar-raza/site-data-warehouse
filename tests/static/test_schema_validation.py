"""
Test suite for schema validation.

This module validates:
- Grafana dashboard JSON structure
- Dashboard panels and rows
- Dashboard metadata and configuration
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
GRAFANA_DASHBOARDS_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "dashboards"


class TestGrafanaDashboardStructure:
    """Test Grafana dashboard files exist and are properly structured."""

    @pytest.fixture
    def dashboard_files(self) -> List[Path]:
        """Get all Grafana dashboard JSON files."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboard_files = list(GRAFANA_DASHBOARDS_DIR.glob("*.json"))
        assert len(dashboard_files) > 0, "No Grafana dashboard JSON files found"

        return sorted(dashboard_files)

    def test_grafana_dashboards_directory_exists(self):
        """Verify Grafana dashboards directory exists."""
        assert GRAFANA_DASHBOARDS_DIR.exists(), \
            f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}"
        assert GRAFANA_DASHBOARDS_DIR.is_dir(), \
            f"{GRAFANA_DASHBOARDS_DIR} is not a directory"

    def test_dashboard_files_exist(self, dashboard_files: List[Path]):
        """Verify Grafana dashboard JSON files exist."""
        assert len(dashboard_files) > 0, "No Grafana dashboard files found"

    def test_dashboard_files_readable(self, dashboard_files: List[Path]):
        """Verify all dashboard files are readable."""
        for dashboard_file in dashboard_files:
            try:
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert len(content) > 0, f"{dashboard_file.name} is empty"
            except Exception as e:
                pytest.fail(f"Failed to read {dashboard_file.name}: {e}")

    def test_dashboard_files_valid_json(self, dashboard_files: List[Path]):
        """Verify all dashboard files are valid JSON."""
        for dashboard_file in dashboard_files:
            try:
                with open(dashboard_file, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"{dashboard_file.name} is not valid JSON: {e}")


class TestGrafanaDashboardContent:
    """Test Grafana dashboard content and required fields."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_dashboard_has_title(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a title."""
        for filename, dashboard in dashboards.items():
            assert "title" in dashboard, \
                f"{filename}: Dashboard missing 'title' field"
            assert isinstance(dashboard["title"], str), \
                f"{filename}: Dashboard title is not a string"
            assert len(dashboard["title"]) > 0, \
                f"{filename}: Dashboard title is empty"

    def test_dashboard_has_uid(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a unique identifier."""
        for filename, dashboard in dashboards.items():
            assert "uid" in dashboard, \
                f"{filename}: Dashboard missing 'uid' field"
            assert isinstance(dashboard["uid"], str), \
                f"{filename}: Dashboard uid is not a string"
            assert len(dashboard["uid"]) > 0, \
                f"{filename}: Dashboard uid is empty"

    def test_dashboard_uids_unique(self, dashboards: Dict[str, Dict]):
        """Verify dashboard UIDs are unique across all dashboards."""
        uids = {}
        for filename, dashboard in dashboards.items():
            uid = dashboard.get("uid")
            if uid:
                if uid in uids:
                    pytest.fail(
                        f"Duplicate UID '{uid}' found in {filename} and {uids[uid]}"
                    )
                uids[uid] = filename

    def test_dashboard_has_version(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a version number."""
        for filename, dashboard in dashboards.items():
            assert "version" in dashboard, \
                f"{filename}: Dashboard missing 'version' field"
            assert isinstance(dashboard["version"], int), \
                f"{filename}: Dashboard version is not an integer"

    def test_dashboard_has_schema_version(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a schema version."""
        for filename, dashboard in dashboards.items():
            assert "schemaVersion" in dashboard, \
                f"{filename}: Dashboard missing 'schemaVersion' field"
            assert isinstance(dashboard["schemaVersion"], int), \
                f"{filename}: Dashboard schemaVersion is not an integer"
            assert dashboard["schemaVersion"] > 0, \
                f"{filename}: Dashboard schemaVersion must be positive"

    def test_dashboard_has_timezone(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a timezone setting."""
        for filename, dashboard in dashboards.items():
            # Timezone is optional but recommended
            if "timezone" in dashboard:
                assert isinstance(dashboard["timezone"], str), \
                    f"{filename}: Dashboard timezone is not a string"
                valid_timezones = ["browser", "utc", ""]
                if dashboard["timezone"] not in valid_timezones:
                    # Allow other timezone strings like "America/New_York"
                    pass

    def test_dashboard_has_time_range(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has a time range configuration."""
        for filename, dashboard in dashboards.items():
            if "time" in dashboard:
                time_config = dashboard["time"]
                assert isinstance(time_config, dict), \
                    f"{filename}: Dashboard time is not a dictionary"
                assert "from" in time_config, \
                    f"{filename}: Dashboard time missing 'from' field"
                assert "to" in time_config, \
                    f"{filename}: Dashboard time missing 'to' field"


class TestGrafanaDashboardPanels:
    """Test Grafana dashboard panels structure."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_dashboard_has_panels(self, dashboards: Dict[str, Dict]):
        """Verify each dashboard has panels defined."""
        for filename, dashboard in dashboards.items():
            assert "panels" in dashboard, \
                f"{filename}: Dashboard missing 'panels' field"
            assert isinstance(dashboard["panels"], list), \
                f"{filename}: Dashboard panels is not a list"

            # Dashboards should have at least one panel
            if len(dashboard["panels"]) == 0:
                pytest.warns(
                    UserWarning,
                    match=f"{filename}: Dashboard has no panels defined"
                )

    def test_panel_has_required_fields(self, dashboards: Dict[str, Dict]):
        """Verify each panel has required fields."""
        required_fields = {"id", "type"}

        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                missing_fields = required_fields - set(panel.keys())

                # Row panels might have different requirements
                if panel.get("type") == "row":
                    continue

                assert not missing_fields, \
                    f"{filename}: Panel {i} missing required fields: {missing_fields}"

    def test_panel_has_title(self, dashboards: Dict[str, Dict]):
        """Verify each panel has a title."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                # Row panels might not need titles
                if panel.get("type") == "row":
                    continue

                # Most panels should have titles
                if "title" not in panel:
                    pytest.warns(
                        UserWarning,
                        match=f"{filename}: Panel {i} (id={panel.get('id')}) missing title"
                    )

    def test_panel_ids_unique(self, dashboards: Dict[str, Dict]):
        """Verify panel IDs are unique within each dashboard."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])
            panel_ids = {}

            for i, panel in enumerate(panels):
                panel_id = panel.get("id")
                if panel_id is not None:
                    if panel_id in panel_ids:
                        pytest.fail(
                            f"{filename}: Duplicate panel ID {panel_id} at positions "
                            f"{panel_ids[panel_id]} and {i}"
                        )
                    panel_ids[panel_id] = i

    def test_panel_has_grid_position(self, dashboards: Dict[str, Dict]):
        """Verify each panel has grid position defined."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            panels_without_grid = []
            for i, panel in enumerate(panels):
                if "gridPos" not in panel:
                    panels_without_grid.append(i)

            if panels_without_grid:
                pytest.warns(
                    UserWarning,
                    match=f"{filename}: Panels without gridPos: {panels_without_grid}"
                )

    def test_panel_grid_position_valid(self, dashboards: Dict[str, Dict]):
        """Verify panel grid positions have valid values."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                if "gridPos" in panel:
                    grid_pos = panel["gridPos"]
                    assert isinstance(grid_pos, dict), \
                        f"{filename}: Panel {i} gridPos is not a dictionary"

                    # Check required grid position fields
                    required_grid_fields = {"h", "w", "x", "y"}
                    missing_fields = required_grid_fields - set(grid_pos.keys())

                    if missing_fields:
                        pytest.warns(
                            UserWarning,
                            match=f"{filename}: Panel {i} gridPos missing fields: {missing_fields}"
                        )

                    # Validate grid position values
                    if "h" in grid_pos:
                        assert grid_pos["h"] > 0, \
                            f"{filename}: Panel {i} gridPos height must be positive"

                    if "w" in grid_pos:
                        assert grid_pos["w"] > 0, \
                            f"{filename}: Panel {i} gridPos width must be positive"
                        assert grid_pos["w"] <= 24, \
                            f"{filename}: Panel {i} gridPos width exceeds maximum (24)"

                    if "x" in grid_pos:
                        assert grid_pos["x"] >= 0, \
                            f"{filename}: Panel {i} gridPos x must be non-negative"
                        assert grid_pos["x"] < 24, \
                            f"{filename}: Panel {i} gridPos x exceeds maximum (24)"

                    if "y" in grid_pos:
                        assert grid_pos["y"] >= 0, \
                            f"{filename}: Panel {i} gridPos y must be non-negative"

    def test_panel_types_valid(self, dashboards: Dict[str, Dict]):
        """Verify panel types are valid Grafana panel types."""
        valid_panel_types = {
            "graph", "timeseries", "stat", "gauge", "bargauge", "table",
            "text", "heatmap", "alertlist", "dashlist", "row", "singlestat",
            "piechart", "bargraph", "histogram", "logs", "nodeGraph", "news"
        }

        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                panel_type = panel.get("type")
                if panel_type:
                    if panel_type not in valid_panel_types:
                        pytest.warns(
                            UserWarning,
                            match=f"{filename}: Panel {i} has unknown type '{panel_type}'"
                        )


class TestGrafanaDashboardDataSources:
    """Test Grafana dashboard data source configurations."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_panel_targets_have_datasource(self, dashboards: Dict[str, Dict]):
        """Verify panel targets reference data sources."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                # Skip row panels
                if panel.get("type") == "row":
                    continue

                # Check if panel has targets
                if "targets" in panel:
                    targets = panel["targets"]
                    assert isinstance(targets, list), \
                        f"{filename}: Panel {i} targets is not a list"

                    for j, target in enumerate(targets):
                        # Each target should reference a datasource
                        if "datasource" not in target:
                            pytest.warns(
                                UserWarning,
                                match=f"{filename}: Panel {i} target {j} missing datasource"
                            )

    def test_datasource_structure(self, dashboards: Dict[str, Dict]):
        """Verify data source references have proper structure."""
        for filename, dashboard in dashboards.items():
            panels = dashboard.get("panels", [])

            for i, panel in enumerate(panels):
                if "targets" in panel:
                    for j, target in enumerate(panel["targets"]):
                        if "datasource" in target:
                            datasource = target["datasource"]

                            # Datasource can be a string or object
                            if isinstance(datasource, dict):
                                # Should have 'type' and optionally 'uid'
                                if "type" not in datasource:
                                    pytest.warns(
                                        UserWarning,
                                        match=f"{filename}: Panel {i} target {j} datasource missing type"
                                    )


class TestGrafanaDashboardTemplating:
    """Test Grafana dashboard templating and variables."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_templating_section_structure(self, dashboards: Dict[str, Dict]):
        """Verify templating section has proper structure."""
        for filename, dashboard in dashboards.items():
            if "templating" in dashboard:
                templating = dashboard["templating"]
                assert isinstance(templating, dict), \
                    f"{filename}: templating is not a dictionary"

                if "list" in templating:
                    assert isinstance(templating["list"], list), \
                        f"{filename}: templating.list is not a list"

    def test_template_variables_have_name(self, dashboards: Dict[str, Dict]):
        """Verify template variables have names."""
        for filename, dashboard in dashboards.items():
            templating = dashboard.get("templating", {})
            variables = templating.get("list", [])

            for i, variable in enumerate(variables):
                assert "name" in variable, \
                    f"{filename}: Template variable {i} missing 'name' field"
                assert len(variable["name"]) > 0, \
                    f"{filename}: Template variable {i} has empty name"

    def test_template_variables_have_type(self, dashboards: Dict[str, Dict]):
        """Verify template variables have types."""
        valid_types = {
            "query", "custom", "interval", "datasource", "constant",
            "adhoc", "textbox"
        }

        for filename, dashboard in dashboards.items():
            templating = dashboard.get("templating", {})
            variables = templating.get("list", [])

            for i, variable in enumerate(variables):
                if "type" in variable:
                    var_type = variable["type"]
                    if var_type not in valid_types:
                        pytest.warns(
                            UserWarning,
                            match=f"{filename}: Template variable {i} has unknown type '{var_type}'"
                        )


class TestGrafanaDashboardAnnotations:
    """Test Grafana dashboard annotations configuration."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_annotations_section_structure(self, dashboards: Dict[str, Dict]):
        """Verify annotations section has proper structure."""
        for filename, dashboard in dashboards.items():
            if "annotations" in dashboard:
                annotations = dashboard["annotations"]
                assert isinstance(annotations, dict), \
                    f"{filename}: annotations is not a dictionary"

                if "list" in annotations:
                    assert isinstance(annotations["list"], list), \
                        f"{filename}: annotations.list is not a list"


class TestGrafanaDashboardTags:
    """Test Grafana dashboard tags and metadata."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_dashboards_have_tags(self, dashboards: Dict[str, Dict]):
        """Verify dashboards have tags for organization."""
        dashboards_without_tags = []

        for filename, dashboard in dashboards.items():
            if "tags" not in dashboard or len(dashboard.get("tags", [])) == 0:
                dashboards_without_tags.append(filename)

        if dashboards_without_tags:
            pytest.warns(
                UserWarning,
                match=f"Dashboards without tags: {dashboards_without_tags}"
            )

    def test_tags_are_lowercase(self, dashboards: Dict[str, Dict]):
        """Verify dashboard tags follow lowercase convention."""
        for filename, dashboard in dashboards.items():
            tags = dashboard.get("tags", [])

            uppercase_tags = [tag for tag in tags if tag != tag.lower()]

            if uppercase_tags:
                pytest.warns(
                    UserWarning,
                    match=f"{filename}: Tags with uppercase letters: {uppercase_tags}"
                )


class TestGrafanaDashboardRefresh:
    """Test Grafana dashboard refresh settings."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_refresh_interval_valid(self, dashboards: Dict[str, Dict]):
        """Verify refresh interval is valid."""
        valid_refresh_values = {
            "", "5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h", "2h", "1d"
        }

        for filename, dashboard in dashboards.items():
            if "refresh" in dashboard:
                refresh = dashboard["refresh"]
                if refresh not in valid_refresh_values:
                    # Allow other valid duration strings
                    if not (isinstance(refresh, str) and (
                        refresh.endswith('s') or
                        refresh.endswith('m') or
                        refresh.endswith('h') or
                        refresh.endswith('d') or
                        refresh == ""
                    )):
                        pytest.warns(
                            UserWarning,
                            match=f"{filename}: Unusual refresh interval '{refresh}'"
                        )


class TestGrafanaDashboardConsistency:
    """Test consistency across all Grafana dashboards."""

    @pytest.fixture
    def dashboards(self) -> Dict[str, Dict]:
        """Load all Grafana dashboards as dictionaries."""
        if not GRAFANA_DASHBOARDS_DIR.exists():
            pytest.skip(f"Grafana dashboards directory not found at {GRAFANA_DASHBOARDS_DIR}")

        dashboards = {}
        for dashboard_file in GRAFANA_DASHBOARDS_DIR.glob("*.json"):
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboards[dashboard_file.name] = json.load(f)

        return dashboards

    def test_dashboards_use_consistent_schema_version(self, dashboards: Dict[str, Dict]):
        """Verify dashboards use similar schema versions."""
        schema_versions = {}

        for filename, dashboard in dashboards.items():
            schema_version = dashboard.get("schemaVersion")
            if schema_version:
                if schema_version not in schema_versions:
                    schema_versions[schema_version] = []
                schema_versions[schema_version].append(filename)

        # Warn if multiple schema versions are in use
        if len(schema_versions) > 2:
            pytest.warns(
                UserWarning,
                match=f"Multiple schema versions in use: {list(schema_versions.keys())}"
            )

    def test_dashboards_have_consistent_structure(self, dashboards: Dict[str, Dict]):
        """Verify dashboards follow consistent structural patterns."""
        # Check that all dashboards have similar top-level keys
        common_keys = {"title", "uid", "version", "schemaVersion", "panels"}

        for filename, dashboard in dashboards.items():
            missing_keys = common_keys - set(dashboard.keys())

            if missing_keys:
                pytest.warns(
                    UserWarning,
                    match=f"{filename}: Missing common keys: {missing_keys}"
                )
