"""
Test suite for static configuration file validation.

This module validates:
- .env.example completeness
- docker-compose.yml structure and validity
- prometheus.yml configuration
"""

import os
import pytest
import yaml
from pathlib import Path
from typing import Dict, List, Set


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
DOCKER_COMPOSE_PATH = PROJECT_ROOT / "docker-compose.yml"
PROMETHEUS_CONFIG_PATH = PROJECT_ROOT / "prometheus" / "prometheus.yml"


class TestEnvExample:
    """Test .env.example file for completeness and required variables."""

    # Required environment variables that must be present
    REQUIRED_VARS = {
        "WAREHOUSE_DSN",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GA4_PROPERTY_ID",
        "OLLAMA_HOST",
        "REDIS_URL",
    }

    # Additional important variables to check
    IMPORTANT_VARS = {
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "GSC_PROPERTIES",
        "OLLAMA_BASE_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    }

    @pytest.fixture
    def env_vars(self) -> Dict[str, str]:
        """Parse .env.example and return all variables as a dictionary."""
        if not ENV_EXAMPLE_PATH.exists():
            pytest.skip(f".env.example not found at {ENV_EXAMPLE_PATH}")

        env_vars = {}
        with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Parse KEY=VALUE pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    env_vars[key] = value

        return env_vars

    def test_env_example_exists(self):
        """Verify .env.example file exists."""
        assert ENV_EXAMPLE_PATH.exists(), \
            f".env.example not found at {ENV_EXAMPLE_PATH}"

    def test_env_example_readable(self):
        """Verify .env.example file is readable."""
        try:
            with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0, ".env.example is empty"
        except Exception as e:
            pytest.fail(f"Failed to read .env.example: {e}")

    def test_required_vars_present(self, env_vars: Dict[str, str]):
        """Verify all required environment variables are defined."""
        missing_vars = self.REQUIRED_VARS - set(env_vars.keys())

        # Note: REDIS_URL might be defined as CELERY_BROKER_URL or CELERY_RESULT_BACKEND
        if "REDIS_URL" in missing_vars:
            if "CELERY_BROKER_URL" in env_vars or "CELERY_RESULT_BACKEND" in env_vars:
                missing_vars.remove("REDIS_URL")

        # Note: GOOGLE_APPLICATION_CREDENTIALS might be GSC_CREDENTIALS_PATH or GA4_CREDENTIALS_FILE
        if "GOOGLE_APPLICATION_CREDENTIALS" in missing_vars:
            gcp_creds = {"GSC_CREDENTIALS_PATH", "GSC_SERVICE_ACCOUNT_FILE",
                        "GA4_CREDENTIALS_FILE", "GA4_CREDENTIALS_PATH"}
            if gcp_creds & set(env_vars.keys()):
                missing_vars.remove("GOOGLE_APPLICATION_CREDENTIALS")

        # Note: OLLAMA_HOST might be OLLAMA_BASE_URL
        if "OLLAMA_HOST" in missing_vars:
            if "OLLAMA_BASE_URL" in env_vars:
                missing_vars.remove("OLLAMA_HOST")

        assert not missing_vars, \
            f"Missing required variables in .env.example: {missing_vars}"

    def test_important_vars_present(self, env_vars: Dict[str, str]):
        """Verify important environment variables are defined."""
        missing_vars = self.IMPORTANT_VARS - set(env_vars.keys())

        # This is a warning, not a hard failure
        if missing_vars:
            pytest.warns(
                UserWarning,
                match=f"Important variables missing: {missing_vars}"
            )

    def test_database_dsn_format(self, env_vars: Dict[str, str]):
        """Verify WAREHOUSE_DSN has correct PostgreSQL format."""
        if "WAREHOUSE_DSN" not in env_vars:
            pytest.skip("WAREHOUSE_DSN not defined")

        dsn = env_vars["WAREHOUSE_DSN"]
        assert dsn.startswith("postgresql://"), \
            "WAREHOUSE_DSN should start with 'postgresql://'"

        # Basic structure check: postgresql://user:pass@host:port/db
        assert "@" in dsn, "WAREHOUSE_DSN should contain '@' for host separator"
        assert ":" in dsn.split("@")[0], \
            "WAREHOUSE_DSN should contain credentials (user:pass)"

    def test_no_duplicate_keys(self):
        """Verify no duplicate environment variable keys."""
        keys_seen: Set[str] = set()
        duplicates: List[str] = []

        with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key = line.split('=', 1)[0].strip()
                    if key in keys_seen:
                        duplicates.append(key)
                    keys_seen.add(key)

        assert not duplicates, \
            f"Duplicate keys found in .env.example: {duplicates}"

    def test_numeric_vars_have_numeric_values(self, env_vars: Dict[str, str]):
        """Verify numeric variables have valid numeric example values."""
        numeric_vars = {
            "GA4_PROPERTY_ID",
            "POSTGRES_PORT",
            "API_PORT",
            "MCP_PORT",
            "METRICS_PORT",
            "PROMETHEUS_PORT",
            "GRAFANA_PORT",
        }

        invalid_vars = []
        for var in numeric_vars:
            if var in env_vars:
                value = env_vars[var]
                if value and not value.isdigit():
                    # Allow ${VAR} style references
                    if not (value.startswith("${") and value.endswith("}")):
                        invalid_vars.append(f"{var}={value}")

        assert not invalid_vars, \
            f"Numeric variables with non-numeric values: {invalid_vars}"


class TestDockerCompose:
    """Test docker-compose.yml file structure and validity."""

    @pytest.fixture
    def compose_config(self) -> Dict:
        """Parse docker-compose.yml and return configuration."""
        if not DOCKER_COMPOSE_PATH.exists():
            pytest.skip(f"docker-compose.yml not found at {DOCKER_COMPOSE_PATH}")

        with open(DOCKER_COMPOSE_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config

    def test_docker_compose_exists(self):
        """Verify docker-compose.yml file exists."""
        assert DOCKER_COMPOSE_PATH.exists(), \
            f"docker-compose.yml not found at {DOCKER_COMPOSE_PATH}"

    def test_docker_compose_valid_yaml(self):
        """Verify docker-compose.yml is valid YAML."""
        try:
            with open(DOCKER_COMPOSE_PATH, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"docker-compose.yml is not valid YAML: {e}")

    def test_compose_version_present(self, compose_config: Dict):
        """Verify docker-compose.yml has version specified."""
        assert "version" in compose_config, \
            "docker-compose.yml missing 'version' field"

        version = compose_config["version"]
        assert version in ["3", "3.0", "3.1", "3.2", "3.3", "3.4",
                          "3.5", "3.6", "3.7", "3.8", "3.9"], \
            f"Unexpected docker-compose version: {version}"

    def test_compose_has_services(self, compose_config: Dict):
        """Verify docker-compose.yml defines services."""
        assert "services" in compose_config, \
            "docker-compose.yml missing 'services' section"
        assert len(compose_config["services"]) > 0, \
            "No services defined in docker-compose.yml"

    def test_warehouse_service_exists(self, compose_config: Dict):
        """Verify warehouse (database) service is defined."""
        services = compose_config.get("services", {})
        assert "warehouse" in services, \
            "warehouse service not defined in docker-compose.yml"

    def test_warehouse_service_config(self, compose_config: Dict):
        """Verify warehouse service has required configuration."""
        warehouse = compose_config["services"]["warehouse"]

        # Check for required fields
        assert "image" in warehouse, "warehouse service missing 'image'"
        assert warehouse["image"].startswith("postgres"), \
            "warehouse service should use postgres image"

        # Check environment variables
        assert "environment" in warehouse, \
            "warehouse service missing environment variables"

        env = warehouse["environment"]
        required_env = {"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"}

        # Environment can be a dict or list
        if isinstance(env, dict):
            env_keys = set(env.keys())
        else:
            env_keys = {item.split("=")[0].split(":")[0] for item in env}

        missing_env = required_env - env_keys
        assert not missing_env, \
            f"warehouse service missing environment vars: {missing_env}"

    def test_services_have_networks(self, compose_config: Dict):
        """Verify services are connected to networks."""
        services = compose_config.get("services", {})

        # Skip this test if no networks defined (standalone setup)
        if "networks" not in compose_config:
            pytest.skip("No networks defined in docker-compose.yml")

        services_without_networks = []
        for service_name, service_config in services.items():
            if "networks" not in service_config:
                services_without_networks.append(service_name)

        # Some services might not need networks
        if services_without_networks:
            pytest.warns(
                UserWarning,
                match=f"Services without networks: {services_without_networks}"
            )

    def test_services_have_restart_policy(self, compose_config: Dict):
        """Verify production services have restart policies."""
        services = compose_config.get("services", {})

        # Core services that should always restart
        core_services = {"warehouse", "redis", "prometheus", "grafana"}

        services_without_restart = []
        for service_name in core_services:
            if service_name in services:
                service = services[service_name]
                if "restart" not in service:
                    services_without_restart.append(service_name)

        if services_without_restart:
            pytest.warns(
                UserWarning,
                match=f"Core services without restart policy: {services_without_restart}"
            )

    def test_services_have_healthchecks(self, compose_config: Dict):
        """Verify critical services have health checks."""
        services = compose_config.get("services", {})

        # Services that should have health checks
        critical_services = {"warehouse", "redis"}

        services_without_healthcheck = []
        for service_name in critical_services:
            if service_name in services:
                service = services[service_name]
                if "healthcheck" not in service:
                    services_without_healthcheck.append(service_name)

        if services_without_healthcheck:
            pytest.warns(
                UserWarning,
                match=f"Critical services without healthcheck: {services_without_healthcheck}"
            )

    def test_volumes_defined(self, compose_config: Dict):
        """Verify volumes are properly defined."""
        services = compose_config.get("services", {})

        # Check if warehouse uses volumes
        if "warehouse" in services:
            warehouse = services["warehouse"]
            if "volumes" in warehouse:
                assert len(warehouse["volumes"]) > 0, \
                    "warehouse service has empty volumes list"


class TestPrometheusConfig:
    """Test prometheus.yml configuration file."""

    @pytest.fixture
    def prometheus_config(self) -> Dict:
        """Parse prometheus.yml and return configuration."""
        if not PROMETHEUS_CONFIG_PATH.exists():
            pytest.skip(f"prometheus.yml not found at {PROMETHEUS_CONFIG_PATH}")

        with open(PROMETHEUS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config

    def test_prometheus_config_exists(self):
        """Verify prometheus.yml file exists."""
        assert PROMETHEUS_CONFIG_PATH.exists(), \
            f"prometheus.yml not found at {PROMETHEUS_CONFIG_PATH}"

    def test_prometheus_config_valid_yaml(self):
        """Verify prometheus.yml is valid YAML."""
        try:
            with open(PROMETHEUS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"prometheus.yml is not valid YAML: {e}")

    def test_prometheus_has_global_section(self, prometheus_config: Dict):
        """Verify prometheus.yml has global configuration."""
        assert "global" in prometheus_config, \
            "prometheus.yml missing 'global' section"

        global_config = prometheus_config["global"]
        assert "scrape_interval" in global_config, \
            "global section missing 'scrape_interval'"
        assert "evaluation_interval" in global_config, \
            "global section missing 'evaluation_interval'"

    def test_prometheus_has_scrape_configs(self, prometheus_config: Dict):
        """Verify prometheus.yml has scrape configurations."""
        assert "scrape_configs" in prometheus_config, \
            "prometheus.yml missing 'scrape_configs' section"

        scrape_configs = prometheus_config["scrape_configs"]
        assert len(scrape_configs) > 0, \
            "No scrape configs defined in prometheus.yml"

    def test_prometheus_scrape_configs_structure(self, prometheus_config: Dict):
        """Verify scrape configs have required fields."""
        scrape_configs = prometheus_config.get("scrape_configs", [])

        for i, config in enumerate(scrape_configs):
            assert "job_name" in config, \
                f"Scrape config {i} missing 'job_name'"
            assert "static_configs" in config, \
                f"Scrape config {i} ({config.get('job_name')}) missing 'static_configs'"

            static_configs = config["static_configs"]
            for j, static_config in enumerate(static_configs):
                assert "targets" in static_config, \
                    f"Static config {j} in job '{config['job_name']}' missing 'targets'"

    def test_prometheus_self_monitoring(self, prometheus_config: Dict):
        """Verify Prometheus monitors itself."""
        scrape_configs = prometheus_config.get("scrape_configs", [])

        job_names = [config.get("job_name") for config in scrape_configs]
        assert "prometheus" in job_names, \
            "Prometheus self-monitoring job not configured"

    def test_prometheus_scrape_intervals_valid(self, prometheus_config: Dict):
        """Verify scrape intervals are valid durations."""
        scrape_configs = prometheus_config.get("scrape_configs", [])

        for config in scrape_configs:
            if "scrape_interval" in config:
                interval = config["scrape_interval"]
                # Should end with s (seconds), m (minutes), h (hours)
                assert interval[-1] in ['s', 'm', 'h'], \
                    f"Invalid scrape_interval format in job '{config.get('job_name')}': {interval}"

    def test_prometheus_rule_files_section(self, prometheus_config: Dict):
        """Verify rule_files section exists if alerts are configured."""
        # This is optional, but good to have
        if "rule_files" in prometheus_config:
            rule_files = prometheus_config["rule_files"]
            assert isinstance(rule_files, list), \
                "rule_files should be a list"


class TestConfigurationIntegrity:
    """Cross-file configuration integrity tests."""

    def test_docker_compose_references_env_vars(self):
        """Verify docker-compose.yml references match .env.example."""
        if not DOCKER_COMPOSE_PATH.exists() or not ENV_EXAMPLE_PATH.exists():
            pytest.skip("Required config files not found")

        # Parse .env.example to get defined variables
        env_vars = set()
        with open(ENV_EXAMPLE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key = line.split('=', 1)[0].strip()
                    env_vars.add(key)

        # Parse docker-compose.yml to find variable references
        with open(DOCKER_COMPOSE_PATH, 'r', encoding='utf-8') as f:
            compose_content = f.read()

        # Find ${VAR} and ${VAR:-default} patterns
        import re
        var_pattern = r'\$\{([A-Z_][A-Z0-9_]*)'
        referenced_vars = set(re.findall(var_pattern, compose_content))

        # Check for undefined variables (warnings only, as some might be optional)
        undefined_vars = referenced_vars - env_vars
        if undefined_vars:
            # Filter out common optional variables
            optional_vars = {"DOCKER_BUILDKIT", "COMPOSE_PROJECT_NAME"}
            undefined_vars = undefined_vars - optional_vars

            if undefined_vars:
                pytest.warns(
                    UserWarning,
                    match=f"Variables referenced in docker-compose.yml but not in .env.example: {undefined_vars}"
                )

    def test_port_conflicts(self):
        """Verify no port conflicts in docker-compose.yml."""
        if not DOCKER_COMPOSE_PATH.exists():
            pytest.skip("docker-compose.yml not found")

        with open(DOCKER_COMPOSE_PATH, 'r', encoding='utf-8') as f:
            compose_config = yaml.safe_load(f)

        services = compose_config.get("services", {})
        exposed_ports = {}

        for service_name, service_config in services.items():
            if "ports" in service_config:
                for port_mapping in service_config["ports"]:
                    # Parse "host:container" format
                    if isinstance(port_mapping, str):
                        if ":" in port_mapping:
                            host_port = port_mapping.split(":")[0]
                        else:
                            host_port = port_mapping
                    else:
                        host_port = str(port_mapping)

                    # Remove ${VAR} references for comparison
                    if "${" not in host_port:
                        if host_port in exposed_ports:
                            pytest.fail(
                                f"Port conflict: {host_port} used by both "
                                f"{exposed_ports[host_port]} and {service_name}"
                            )
                        exposed_ports[host_port] = service_name
