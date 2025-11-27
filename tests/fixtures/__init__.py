"""
Shared test fixtures and utilities for site-data-warehouse tests.

This package provides:
- sample_data: Generators for realistic test data matching production schema
- mock_apis: Mock factories for external APIs (GSC, GA4, PageSpeed, Ollama)
- conftest_helpers: Shared utilities for test setup and assertions
- docker_services: Docker container fixtures for integration testing

All fixtures use deterministic data generation with random.seed(42) for
reproducible tests.
"""

from tests.fixtures import sample_data, mock_apis, conftest_helpers

# Docker service fixtures (optional, only imported when needed)
try:
    from tests.fixtures.docker_services import (
        # Service management
        docker_services,
        ui_services,

        # Individual containers
        postgres_container,
        redis_container,
        grafana_container,
        prometheus_container,

        # Database connections
        postgres_connection,
        postgres_cursor,
        redis_client,

        # Database setup/teardown
        clean_database,
        test_schema,

        # Configuration
        test_db_dsn,
        test_redis_url,
        test_grafana_url,
        test_prometheus_url,

        # Service info
        service_ports,
        service_health_status,
    )

    __all__ = [
        "sample_data",
        "mock_apis",
        "conftest_helpers",
        # Docker services
        "docker_services",
        "ui_services",
        "postgres_container",
        "redis_container",
        "grafana_container",
        "prometheus_container",
        "postgres_connection",
        "postgres_cursor",
        "redis_client",
        "clean_database",
        "test_schema",
        "test_db_dsn",
        "test_redis_url",
        "test_grafana_url",
        "test_prometheus_url",
        "service_ports",
        "service_health_status",
    ]
except ImportError:
    # Docker fixtures not available (missing dependencies)
    __all__ = [
        "sample_data",
        "mock_apis",
        "conftest_helpers",
    ]
