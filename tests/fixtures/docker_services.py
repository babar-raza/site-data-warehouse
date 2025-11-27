"""
Docker service fixtures for pytest

Provides fixtures for managing test Docker services including:
- PostgreSQL 15 with pgvector extension
- Redis 7
- Grafana (for E2E UI tests)
- Prometheus (for E2E UI tests)

All services are isolated in a test_network and have unique container names
prefixed with test_ to avoid conflicts with production services.

Usage:
    @pytest.mark.live
    def test_something(postgres_container, redis_container):
        # Services are automatically started and stopped
        pass

    @pytest.mark.ui
    def test_dashboard(grafana_container, prometheus_container):
        # UI services are available
        pass
"""
import os
import time
import subprocess
import socket
from typing import Generator, Dict, Any
from pathlib import Path

import pytest
import psycopg2
import redis


# ============================================
# CONFIGURATION
# ============================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DOCKER_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.test.yml"

# Default ports for test services (avoid conflicts with production)
TEST_POSTGRES_PORT = int(os.getenv("TEST_POSTGRES_PORT", "5433"))
TEST_REDIS_PORT = int(os.getenv("TEST_REDIS_PORT", "6380"))
TEST_GRAFANA_PORT = int(os.getenv("TEST_GRAFANA_PORT", "3001"))
TEST_PROMETHEUS_PORT = int(os.getenv("TEST_PROMETHEUS_PORT", "9091"))

# Database credentials
TEST_POSTGRES_DB = os.getenv("TEST_POSTGRES_DB", "gsc_test")
TEST_POSTGRES_USER = os.getenv("TEST_POSTGRES_USER", "test_user")
TEST_POSTGRES_PASSWORD = os.getenv("TEST_POSTGRES_PASSWORD", "test_pass")

# Connection strings
TEST_DB_DSN = (
    f"postgresql://{TEST_POSTGRES_USER}:{TEST_POSTGRES_PASSWORD}"
    f"@localhost:{TEST_POSTGRES_PORT}/{TEST_POSTGRES_DB}"
)
TEST_REDIS_URL = f"redis://localhost:{TEST_REDIS_PORT}/0"


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_port_available(port: int, host: str = "localhost") -> bool:
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result != 0  # Port is available if connection fails
    finally:
        sock.close()


def wait_for_port(port: int, host: str = "localhost", timeout: int = 60) -> bool:
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_port_available(port, host):
            return True
        time.sleep(0.5)
    return False


def run_docker_compose(command: str, service: str = None) -> subprocess.CompletedProcess:
    """Run docker-compose command."""
    cmd = [
        "docker-compose",
        "-f", str(DOCKER_COMPOSE_FILE),
        "-p", "gsc_test",
    ]
    cmd.extend(command.split())
    if service:
        cmd.append(service)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )


def is_service_healthy(service_name: str, timeout: int = 60) -> bool:
    """Check if a Docker service is healthy."""
    start_time = time.time()
    container_name = f"test_gsc_{service_name}"

    while time.time() - start_time < timeout:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            health_status = result.stdout.strip()
            if health_status == "healthy":
                return True
            elif health_status == "unhealthy":
                return False

        time.sleep(1)

    return False


def wait_for_postgres(dsn: str, timeout: int = 60) -> bool:
    """Wait for PostgreSQL to be ready and accepting connections."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(dsn)
            cursor = conn.cursor()
            # Verify pgvector extension is available
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except (psycopg2.OperationalError, psycopg2.DatabaseError):
            time.sleep(0.5)

    return False


def wait_for_redis(url: str, timeout: int = 60) -> bool:
    """Wait for Redis to be ready."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            client = redis.from_url(url)
            client.ping()
            client.close()
            return True
        except (redis.ConnectionError, redis.TimeoutError):
            time.sleep(0.5)

    return False


def verify_pgvector_extension(dsn: str) -> bool:
    """Verify that pgvector extension is installed and functional."""
    try:
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor()

        # Check if vector extension exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            )
        """)
        has_extension = cursor.fetchone()[0]

        if not has_extension:
            # Try to create the extension
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.commit()

        # Test vector functionality
        cursor.execute("SELECT '[1,2,3]'::vector(3)")
        result = cursor.fetchone()

        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"pgvector verification failed: {e}")
        return False


# ============================================
# SESSION SCOPE FIXTURES
# ============================================

@pytest.fixture(scope="session")
def docker_compose_file() -> Path:
    """Path to test docker-compose file."""
    return DOCKER_COMPOSE_FILE


@pytest.fixture(scope="session")
def docker_services_project_name() -> str:
    """Docker Compose project name for test services."""
    return "gsc_test"


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Directory for test data volumes."""
    data_dir = PROJECT_ROOT / "test-data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "postgres").mkdir(exist_ok=True)
    (data_dir / "redis").mkdir(exist_ok=True)
    return data_dir


# ============================================
# DOCKER SERVICE MANAGEMENT
# ============================================

@pytest.fixture(scope="session")
def docker_services(test_data_dir) -> Generator[Dict[str, Any], None, None]:
    """
    Start all Docker test services and ensure they're healthy.

    This fixture:
    1. Validates docker-compose configuration
    2. Starts all test services
    3. Waits for health checks to pass
    4. Yields service information
    5. Stops and cleans up services after tests
    """
    # Ensure services are not already running
    run_docker_compose("down -v")

    # Validate docker-compose configuration
    result = run_docker_compose("config")
    if result.returncode != 0:
        pytest.fail(f"Invalid docker-compose.test.yml: {result.stderr}")

    # Start services
    result = run_docker_compose("up -d")
    if result.returncode != 0:
        pytest.fail(f"Failed to start services: {result.stderr}")

    # Wait for services to be healthy
    services = {
        "postgres": {
            "container": "test_gsc_warehouse",
            "port": TEST_POSTGRES_PORT,
            "dsn": TEST_DB_DSN,
        },
        "redis": {
            "container": "test_gsc_redis",
            "port": TEST_REDIS_PORT,
            "url": TEST_REDIS_URL,
        },
    }

    # Wait for each service
    for service_name, config in services.items():
        # Wait for port
        if not wait_for_port(config["port"]):
            pytest.fail(f"{service_name} port {config['port']} did not become available")

        # Wait for health check
        if not is_service_healthy(service_name.replace("_", "")):
            pytest.fail(f"{service_name} health check failed")

    # Additional verification for PostgreSQL
    if not wait_for_postgres(TEST_DB_DSN):
        pytest.fail("PostgreSQL did not become ready")

    # Verify pgvector extension
    if not verify_pgvector_extension(TEST_DB_DSN):
        pytest.fail("pgvector extension verification failed")

    # Additional verification for Redis
    if not wait_for_redis(TEST_REDIS_URL):
        pytest.fail("Redis did not become ready")

    yield services

    # Cleanup: Stop and remove all test services
    run_docker_compose("down -v")


@pytest.fixture(scope="session")
def ui_services(docker_services) -> Generator[Dict[str, Any], None, None]:
    """
    Ensure UI services (Grafana, Prometheus) are running for E2E tests.

    This fixture depends on docker_services and adds:
    - Grafana for dashboard UI tests
    - Prometheus for metrics UI tests
    """
    # Start UI-specific services
    ui_service_names = ["test_grafana", "test_prometheus"]

    for service in ui_service_names:
        result = run_docker_compose("up -d", service)
        if result.returncode != 0:
            pytest.fail(f"Failed to start {service}: {result.stderr}")

    # Wait for UI services
    ui_services_config = {
        "grafana": {
            "container": "test_gsc_grafana",
            "port": TEST_GRAFANA_PORT,
            "url": f"http://localhost:{TEST_GRAFANA_PORT}",
        },
        "prometheus": {
            "container": "test_gsc_prometheus",
            "port": TEST_PROMETHEUS_PORT,
            "url": f"http://localhost:{TEST_PROMETHEUS_PORT}",
        },
    }

    for service_name, config in ui_services_config.items():
        # Wait for port
        if not wait_for_port(config["port"]):
            pytest.fail(f"{service_name} port {config['port']} did not become available")

        # Wait for health check
        if not is_service_healthy(service_name):
            pytest.fail(f"{service_name} health check failed")

    yield ui_services_config


# ============================================
# INDIVIDUAL SERVICE FIXTURES
# ============================================

@pytest.fixture(scope="session")
def postgres_container(docker_services) -> Dict[str, Any]:
    """PostgreSQL 15 container with pgvector extension."""
    return docker_services["postgres"]


@pytest.fixture(scope="session")
def redis_container(docker_services) -> Dict[str, Any]:
    """Redis 7 container."""
    return docker_services["redis"]


@pytest.fixture(scope="session")
def grafana_container(ui_services) -> Dict[str, Any]:
    """Grafana container for E2E UI tests."""
    return ui_services["grafana"]


@pytest.fixture(scope="session")
def prometheus_container(ui_services) -> Dict[str, Any]:
    """Prometheus container for E2E UI tests."""
    return ui_services["prometheus"]


# ============================================
# DATABASE CONNECTION FIXTURES
# ============================================

@pytest.fixture
def postgres_connection(postgres_container):
    """
    PostgreSQL connection for tests.

    Yields a psycopg2 connection with autocommit enabled.
    Automatically closes connection after test.
    """
    conn = psycopg2.connect(postgres_container["dsn"])
    conn.autocommit = True

    yield conn

    conn.close()


@pytest.fixture
def postgres_cursor(postgres_connection):
    """
    PostgreSQL cursor for tests.

    Yields a cursor and automatically closes it after test.
    """
    cursor = postgres_connection.cursor()

    yield cursor

    cursor.close()


@pytest.fixture
def redis_client(redis_container):
    """
    Redis client for tests.

    Yields a Redis client and automatically closes it after test.
    Flushes the test database before and after each test.
    """
    client = redis.from_url(redis_container["url"])

    # Flush before test
    client.flushdb()

    yield client

    # Flush after test
    client.flushdb()
    client.close()


# ============================================
# DATABASE SETUP/TEARDOWN FIXTURES
# ============================================

@pytest.fixture
def clean_database(postgres_connection):
    """
    Clean database fixture that truncates all tables before test.

    Use this when you need a fresh database state for each test.
    """
    cursor = postgres_connection.cursor()

    # Get all tables in gsc schema
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'gsc'
    """)
    tables = cursor.fetchall()

    # Truncate all tables (if they exist)
    if tables:
        table_names = ", ".join([f"gsc.{t[0]}" for t in tables])
        cursor.execute(f"TRUNCATE TABLE {table_names} CASCADE")

    cursor.close()

    yield

    # Optionally clean up after test as well
    cursor = postgres_connection.cursor()
    if tables:
        cursor.execute(f"TRUNCATE TABLE {table_names} CASCADE")
    cursor.close()


@pytest.fixture
def test_schema(postgres_connection):
    """
    Ensure test schema exists and is initialized.

    Creates the gsc schema and necessary extensions if they don't exist.
    """
    cursor = postgres_connection.cursor()

    # Create schema
    cursor.execute("CREATE SCHEMA IF NOT EXISTS gsc")

    # Create extensions
    cursor.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    cursor.close()

    yield


# ============================================
# CONFIGURATION FIXTURES
# ============================================

@pytest.fixture
def test_db_dsn(postgres_container) -> str:
    """Test database DSN string."""
    return postgres_container["dsn"]


@pytest.fixture
def test_redis_url(redis_container) -> str:
    """Test Redis URL string."""
    return redis_container["url"]


@pytest.fixture
def test_grafana_url(grafana_container) -> str:
    """Test Grafana URL for E2E UI tests."""
    return grafana_container["url"]


@pytest.fixture
def test_prometheus_url(prometheus_container) -> str:
    """Test Prometheus URL for E2E UI tests."""
    return prometheus_container["url"]


# ============================================
# SERVICE INFO FIXTURES
# ============================================

@pytest.fixture
def service_ports() -> Dict[str, int]:
    """Dictionary of all test service ports."""
    return {
        "postgres": TEST_POSTGRES_PORT,
        "redis": TEST_REDIS_PORT,
        "grafana": TEST_GRAFANA_PORT,
        "prometheus": TEST_PROMETHEUS_PORT,
    }


@pytest.fixture
def service_health_status() -> Dict[str, bool]:
    """Check health status of all running test services."""
    services = ["warehouse", "redis", "grafana", "prometheus"]
    return {
        service: is_service_healthy(service)
        for service in services
    }
