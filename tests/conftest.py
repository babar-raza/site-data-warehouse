"""
Pytest configuration and shared fixtures
"""
import pytest
import os


@pytest.fixture(scope="session")
def test_db_dsn():
    """Test database DSN"""
    return os.getenv(
        'TEST_DB_DSN',
        'postgresql://gsc_user:gsc_password@localhost:5432/gsc_test'
    )


@pytest.fixture(scope="session")
def mock_db_dsn():
    """Mock database DSN for unit tests without real DB"""
    return "postgresql://test:test@localhost:5432/test_db"
