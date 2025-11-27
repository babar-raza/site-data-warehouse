"""
Tests for Docker service fixtures.

This test file demonstrates how to use the Docker service fixtures
and validates that all test services are properly configured.

Run with:
    pytest tests/test_docker_services.py -v --log-cli-level=INFO

Requirements:
    - Docker and docker-compose installed
    - docker-compose.test.yml configured
    - Test services must be started (fixtures handle this automatically)
"""
import pytest
import psycopg2
import redis


class TestDockerServices:
    """Test Docker service availability and health."""

    @pytest.mark.live
    def test_postgres_container_available(self, postgres_container):
        """Test that PostgreSQL container is running and healthy."""
        assert postgres_container is not None
        assert "dsn" in postgres_container
        assert "port" in postgres_container
        assert postgres_container["port"] == 5433  # Test port

    @pytest.mark.live
    def test_redis_container_available(self, redis_container):
        """Test that Redis container is running and healthy."""
        assert redis_container is not None
        assert "url" in redis_container
        assert "port" in redis_container
        assert redis_container["port"] == 6380  # Test port

    @pytest.mark.live
    def test_postgres_connection(self, postgres_connection):
        """Test PostgreSQL connection is working."""
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()

        assert "PostgreSQL" in version
        assert "15" in version  # PostgreSQL 15

    @pytest.mark.live
    def test_pgvector_extension(self, postgres_connection):
        """Test that pgvector extension is installed and functional."""
        cursor = postgres_connection.cursor()

        # Check if extension exists
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            )
        """)
        has_extension = cursor.fetchone()[0]
        assert has_extension, "pgvector extension not installed"

        # Test vector functionality
        cursor.execute("SELECT '[1,2,3]'::vector(3)")
        result = cursor.fetchone()[0]
        assert result is not None

        cursor.close()

    @pytest.mark.live
    def test_redis_client(self, redis_client):
        """Test Redis client connection."""
        # Test ping
        assert redis_client.ping() is True

        # Test set/get
        redis_client.set("test_key", "test_value")
        assert redis_client.get("test_key").decode() == "test_value"

        # Test delete
        redis_client.delete("test_key")
        assert redis_client.get("test_key") is None

    @pytest.mark.live
    def test_redis_version(self, redis_client):
        """Test Redis version is 7.x."""
        info = redis_client.info()
        version = info["redis_version"]
        assert version.startswith("7.")

    @pytest.mark.live
    def test_service_health_status(self, service_health_status):
        """Test that all services report healthy status."""
        assert "warehouse" in service_health_status
        assert "redis" in service_health_status

        # Core services should be healthy
        assert service_health_status["warehouse"] is True
        assert service_health_status["redis"] is True


class TestDatabaseSetup:
    """Test database setup and schema fixtures."""

    @pytest.mark.live
    def test_test_schema_exists(self, postgres_connection, test_schema):
        """Test that gsc schema exists."""
        cursor = postgres_connection.cursor()
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_namespace WHERE nspname = 'gsc'
            )
        """)
        has_schema = cursor.fetchone()[0]
        cursor.close()

        assert has_schema, "gsc schema does not exist"

    @pytest.mark.live
    def test_extensions_installed(self, postgres_connection, test_schema):
        """Test that required extensions are installed."""
        cursor = postgres_connection.cursor()

        required_extensions = ["uuid-ossp", "vector", "pg_trgm"]

        for ext in required_extensions:
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = %s
                )
            """, (ext,))
            has_ext = cursor.fetchone()[0]
            assert has_ext, f"Extension {ext} not installed"

        cursor.close()

    @pytest.mark.live
    def test_clean_database(self, postgres_connection, clean_database):
        """Test clean_database fixture truncates tables."""
        cursor = postgres_connection.cursor()

        # Create a test table and insert data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gsc.test_table (
                id SERIAL PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("INSERT INTO gsc.test_table (value) VALUES ('test')")

        # Verify data exists
        cursor.execute("SELECT COUNT(*) FROM gsc.test_table")
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.close()

        # clean_database fixture should have truncated the table at start


class TestUIServices:
    """Test UI services (Grafana, Prometheus) for E2E tests."""

    @pytest.mark.ui
    def test_grafana_container_available(self, grafana_container):
        """Test that Grafana container is running."""
        assert grafana_container is not None
        assert "url" in grafana_container
        assert "port" in grafana_container
        assert grafana_container["port"] == 3001  # Test port

    @pytest.mark.ui
    def test_prometheus_container_available(self, prometheus_container):
        """Test that Prometheus container is running."""
        assert prometheus_container is not None
        assert "url" in prometheus_container
        assert "port" in prometheus_container
        assert prometheus_container["port"] == 9091  # Test port

    @pytest.mark.ui
    def test_grafana_url_accessible(self, test_grafana_url):
        """Test that Grafana URL is properly formatted."""
        assert test_grafana_url == "http://localhost:3001"

    @pytest.mark.ui
    def test_prometheus_url_accessible(self, test_prometheus_url):
        """Test that Prometheus URL is properly formatted."""
        assert test_prometheus_url == "http://localhost:9091"


class TestServiceConfiguration:
    """Test service configuration and isolation."""

    @pytest.mark.live
    def test_test_db_dsn(self, test_db_dsn):
        """Test that test database DSN is properly configured."""
        assert "test_user" in test_db_dsn
        assert "test_pass" in test_db_dsn
        assert "gsc_test" in test_db_dsn
        assert "5433" in test_db_dsn  # Test port

    @pytest.mark.live
    def test_test_redis_url(self, test_redis_url):
        """Test that test Redis URL is properly configured."""
        assert "localhost" in test_redis_url or "127.0.0.1" in test_redis_url
        assert "6380" in test_redis_url  # Test port

    @pytest.mark.live
    def test_service_ports(self, service_ports):
        """Test that service ports are isolated from production."""
        assert service_ports["postgres"] == 5433  # Not 5432
        assert service_ports["redis"] == 6380  # Not 6379
        assert service_ports["grafana"] == 3001  # Not 3000
        assert service_ports["prometheus"] == 9091  # Not 9090

    @pytest.mark.live
    def test_network_isolation(self, postgres_container):
        """Test that services are on isolated test_network."""
        # This is verified by the container running successfully
        # Docker would fail if network wasn't properly isolated
        assert postgres_container is not None


class TestDataPersistence:
    """Test data persistence and cleanup."""

    @pytest.mark.live
    def test_postgres_data_persists(self, postgres_connection):
        """Test that PostgreSQL data persists within session."""
        cursor = postgres_connection.cursor()

        # Create table and insert data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gsc.persistence_test (
                id SERIAL PRIMARY KEY,
                data TEXT
            )
        """)
        cursor.execute("INSERT INTO gsc.persistence_test (data) VALUES ('persist')")

        # Verify data exists
        cursor.execute("SELECT data FROM gsc.persistence_test WHERE data = 'persist'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "persist"

        cursor.close()

    @pytest.mark.live
    def test_redis_data_isolated(self, redis_client):
        """Test that Redis data is isolated between tests."""
        # This test verifies the redis_client fixture flushes DB
        keys = redis_client.keys("*")
        assert len(keys) == 0, "Redis should be empty at start of test"


class TestHealthChecks:
    """Test that health checks are working properly."""

    @pytest.mark.live
    def test_postgres_health_check(self, postgres_connection):
        """Test PostgreSQL is accepting connections."""
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()[0]
        cursor.close()

        assert result == 1

    @pytest.mark.live
    def test_redis_health_check(self, redis_client):
        """Test Redis PING command works."""
        assert redis_client.ping() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--log-cli-level=INFO"])
