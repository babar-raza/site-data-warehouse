"""
Testing modes helper - Controls mock vs live test execution.

Environment Variables:
    TEST_MODE: "mock" (default) or "live"

Usage:
    from tests.testing_modes import is_live_mode, require_live_mode

    @pytest.mark.live
    @require_live_mode
    def test_with_real_database():
        # Only runs when TEST_MODE=live
        pass
"""

import os
import pytest
from functools import wraps

def get_test_mode() -> str:
    """Get current test mode from environment."""
    return os.environ.get('TEST_MODE', 'mock').lower()

def is_live_mode() -> bool:
    """Check if tests should run in live mode."""
    return get_test_mode() == 'live'

def is_mock_mode() -> bool:
    """Check if tests should run in mock mode."""
    return get_test_mode() == 'mock'

def require_live_mode(func):
    """Decorator to skip test if not in live mode."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_live_mode():
            pytest.skip("Skipped: TEST_MODE != 'live'")
        return func(*args, **kwargs)
    return wrapper

def require_mock_mode(func):
    """Decorator to skip test if not in mock mode."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_mock_mode():
            pytest.skip("Skipped: TEST_MODE != 'mock'")
        return func(*args, **kwargs)
    return wrapper

# Service availability checks
def has_postgres() -> bool:
    """Check if PostgreSQL is available."""
    if not is_live_mode():
        return False
    dsn = os.environ.get('WAREHOUSE_DSN', '')
    return bool(dsn and 'postgresql' in dsn)

def has_gsc_credentials() -> bool:
    """Check if GSC credentials are available."""
    if not is_live_mode():
        return False
    return bool(os.environ.get('GSC_SA_PATH'))

def has_ga4_credentials() -> bool:
    """Check if GA4 credentials are available."""
    if not is_live_mode():
        return False
    return bool(os.environ.get('GA4_CREDENTIALS_PATH'))

def skip_if_no_postgres(func):
    """Skip test if PostgreSQL is not available."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_postgres():
            pytest.skip("Skipped: PostgreSQL not available")
        return func(*args, **kwargs)
    return wrapper

def skip_if_no_gsc(func):
    """Skip test if GSC credentials not available."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_gsc_credentials():
            pytest.skip("Skipped: GSC credentials not available")
        return func(*args, **kwargs)
    return wrapper

def skip_if_no_ga4(func):
    """Skip test if GA4 credentials not available."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_ga4_credentials():
            pytest.skip("Skipped: GA4 credentials not available")
        return func(*args, **kwargs)
    return wrapper


def has_celery() -> bool:
    """Check if Celery is available."""
    try:
        import celery
        return True
    except ImportError:
        return False


def has_redis() -> bool:
    """Check if Redis is available and accessible."""
    if not is_live_mode():
        return False
    try:
        import redis
        broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        r = redis.from_url(broker_url)
        r.ping()
        return True
    except Exception:
        return False


def skip_if_no_celery(func):
    """Skip test if Celery is not installed."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_celery():
            pytest.skip("Skipped: Celery not installed")
        return func(*args, **kwargs)
    return wrapper


def skip_if_no_redis(func):
    """Skip test if Redis is not available."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not has_redis():
            pytest.skip("Skipped: Redis not available")
        return func(*args, **kwargs)
    return wrapper
