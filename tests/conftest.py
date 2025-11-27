"""
Pytest configuration and shared fixtures
"""
import pytest
import os
from pathlib import Path

# Load .env from project root for all tests (override=True to ensure fresh values)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring live services (PostgreSQL, APIs, etc.)"
    )
    config.addinivalue_line(
        "markers",
        "ui: mark test as requiring browser/UI (Playwright)"
    )
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end workflow test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test requiring running services"
    )
    config.addinivalue_line(
        "markers",
        "smoke: mark test as smoke test for deployment verification (fast, < 30s)"
    )


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
