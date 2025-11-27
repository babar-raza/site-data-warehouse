"""
Shared fixture utilities and helpers for pytest configuration.

Provides utilities for:
- Time freezing/manipulation
- Database connection mocking
- Common test assertions
- Path handling (Windows-compatible)
- Test data cleanup

Usage in conftest.py:
    >>> from tests.fixtures.conftest_helpers import freeze_time, temp_db_connection
    >>> @pytest.fixture
    >>> def frozen_time():
    >>>     with freeze_time('2025-01-15 10:00:00'):
    >>>         yield
"""

import asyncio
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional
from unittest.mock import MagicMock, Mock, patch

import psycopg2
from psycopg2.extras import RealDictCursor


class FrozenTime:
    """
    Context manager for freezing time during tests.

    Patches datetime.now(), datetime.utcnow(), and date.today() by replacing
    the datetime module in target modules.
    """

    def __init__(self, frozen_datetime: datetime):
        """
        Initialize frozen time.

        Args:
            frozen_datetime: The datetime to freeze at
        """
        self.frozen_datetime = frozen_datetime
        self._patches = []

    def __enter__(self):
        """Enter context and apply patches."""
        # Create mock datetime class that returns frozen time
        class MockDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return self.frozen_datetime

            @classmethod
            def utcnow(cls):
                return self.frozen_datetime

        # Create mock date class
        class MockDate:
            @staticmethod
            def today():
                return self.frozen_datetime.date()

        # Store the mocks so they can be updated by tick()
        self._mock_datetime = MockDateTime
        self._mock_date = MockDate

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and remove patches."""
        # Patches are removed automatically when using with statement
        pass

    def tick(self, **kwargs):
        """
        Advance frozen time by a timedelta.

        Args:
            **kwargs: Arguments to pass to timedelta (days, hours, minutes, etc.)
        """
        self.frozen_datetime += timedelta(**kwargs)

    def get_now(self) -> datetime:
        """Get the current frozen time."""
        return self.frozen_datetime

    def get_today(self):
        """Get the current frozen date."""
        return self.frozen_datetime.date()


@contextmanager
def freeze_time(frozen_datetime: str) -> Generator[FrozenTime, None, None]:
    """
    Context manager to freeze time during tests.

    Note: This is a simplified implementation that provides a FrozenTime object
    but does not actually patch the datetime module globally. For tests that need
    global time freezing, use the freezegun library or manual mocking.

    Args:
        frozen_datetime: Datetime string in ISO format or simple format

    Yields:
        FrozenTime instance with get_now() and tick() methods

    Example:
        >>> with freeze_time('2025-01-15 10:00:00') as frozen:
        >>>     now1 = frozen.get_now()
        >>>     frozen.tick(hours=1)
        >>>     now2 = frozen.get_now()
        >>>     assert now2 > now1
    """
    # Parse datetime string
    try:
        dt = datetime.fromisoformat(frozen_datetime)
    except ValueError:
        # Try simple format
        dt = datetime.strptime(frozen_datetime, "%Y-%m-%d %H:%M:%S")

    frozen = FrozenTime(dt)
    with frozen:
        yield frozen


class MockDBConnection:
    """
    Mock database connection for testing without real database.

    Implements psycopg2-like interface with in-memory storage.
    """

    def __init__(self, dsn: str = "postgresql://test:test@localhost/test"):
        """
        Initialize mock connection.

        Args:
            dsn: Database DSN (not actually used)
        """
        self.dsn = dsn
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._closed = False

    def cursor(self, cursor_factory=None):
        """Get a cursor."""
        return MockDBCursor(self._data, cursor_factory=cursor_factory)

    def commit(self):
        """Commit transaction (no-op)."""
        pass

    def rollback(self):
        """Rollback transaction (no-op)."""
        pass

    def close(self):
        """Close connection."""
        self._closed = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def set_table_data(self, table_name: str, data: List[Dict[str, Any]]):
        """
        Set data for a table.

        Args:
            table_name: Name of the table
            data: List of row dicts
        """
        self._data[table_name] = data


class MockDBCursor:
    """Mock database cursor."""

    def __init__(self, data: Dict[str, List[Dict[str, Any]]], cursor_factory=None):
        """
        Initialize mock cursor.

        Args:
            data: Reference to connection's data dict
            cursor_factory: Cursor factory (e.g., RealDictCursor)
        """
        self._data = data
        self._results = []
        self._cursor_factory = cursor_factory
        self._rowcount = 0

    def execute(self, query: str, params: Optional[tuple] = None):
        """
        Execute a query.

        Args:
            query: SQL query
            params: Query parameters
        """
        query_lower = query.lower()

        # Extract table name from query
        table_name = None
        if "from " in query_lower:
            parts = query_lower.split("from ")[1].split()
            if parts:
                table_name = parts[0].strip()

        # Mock SELECT queries
        if query_lower.startswith("select"):
            if table_name and table_name in self._data:
                self._results = self._data[table_name].copy()
            else:
                self._results = []

        # Mock INSERT/UPDATE/DELETE
        elif any(q in query_lower for q in ["insert", "update", "delete"]):
            self._rowcount = 1
            self._results = []

        else:
            self._results = []

    def fetchall(self) -> List[Any]:
        """Fetch all results."""
        if self._cursor_factory == RealDictCursor:
            return self._results
        else:
            # Convert dicts to tuples
            return [tuple(row.values()) for row in self._results]

    def fetchone(self) -> Optional[Any]:
        """Fetch one result."""
        if not self._results:
            return None

        if self._cursor_factory == RealDictCursor:
            return self._results[0]
        else:
            return tuple(self._results[0].values())

    def fetchmany(self, size: int = 1) -> List[Any]:
        """Fetch multiple results."""
        results = self._results[:size]
        if self._cursor_factory == RealDictCursor:
            return results
        else:
            return [tuple(row.values()) for row in results]

    def close(self):
        """Close cursor."""
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    @property
    def rowcount(self) -> int:
        """Get row count."""
        return self._rowcount


@contextmanager
def temp_db_connection(
    table_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> Generator[MockDBConnection, None, None]:
    """
    Create a temporary mock database connection for testing.

    Args:
        table_data: Optional dict of table_name -> list of row dicts

    Yields:
        MockDBConnection instance

    Example:
        >>> with temp_db_connection({'users': [{'id': 1, 'name': 'Alice'}]}) as conn:
        >>>     cursor = conn.cursor()
        >>>     cursor.execute('SELECT * FROM users')
        >>>     assert cursor.fetchone() == (1, 'Alice')
    """
    conn = MockDBConnection()

    if table_data:
        for table_name, data in table_data.items():
            conn.set_table_data(table_name, data)

    try:
        yield conn
    finally:
        conn.close()


def get_temp_dir() -> Path:
    """
    Get a temporary directory for test files.

    Returns Windows-compatible temp directory path.

    Returns:
        Path to temporary directory
    """
    temp_path = Path(tempfile.gettempdir()) / "site-data-warehouse-tests"
    temp_path.mkdir(exist_ok=True)
    return temp_path


def clean_temp_dir():
    """
    Clean up temporary test directory.

    Removes all files in the test temp directory.
    """
    temp_path = get_temp_dir()
    if temp_path.exists():
        for file in temp_path.iterdir():
            if file.is_file():
                file.unlink()


def normalize_path(path: str) -> Path:
    """
    Normalize a path for cross-platform compatibility.

    Converts forward slashes to backslashes on Windows.

    Args:
        path: Path string

    Returns:
        Normalized Path object
    """
    return Path(path)


def create_temp_file(filename: str, content: str = "") -> Path:
    """
    Create a temporary file for testing.

    Args:
        filename: Name of the file
        content: Content to write to file

    Returns:
        Path to created file
    """
    temp_dir = get_temp_dir()
    file_path = temp_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def assert_dict_contains(actual: Dict[str, Any], expected: Dict[str, Any]):
    """
    Assert that actual dict contains all keys/values from expected dict.

    Args:
        actual: Actual dictionary
        expected: Expected dictionary (subset)

    Raises:
        AssertionError: If expected keys/values not in actual
    """
    for key, value in expected.items():
        assert key in actual, f"Key '{key}' not found in actual dict"
        assert actual[key] == value, f"Value mismatch for key '{key}': {actual[key]} != {value}"


def assert_lists_equal_ignore_order(actual: List[Any], expected: List[Any]):
    """
    Assert that two lists contain the same elements, ignoring order.

    Args:
        actual: Actual list
        expected: Expected list

    Raises:
        AssertionError: If lists don't match
    """
    assert len(actual) == len(expected), f"List lengths differ: {len(actual)} != {len(expected)}"
    assert sorted(actual) == sorted(expected), "Lists don't match (ignoring order)"


def assert_datetime_close(
    actual: datetime, expected: datetime, tolerance_seconds: int = 5
):
    """
    Assert that two datetimes are close to each other.

    Useful for testing timestamps that may differ slightly due to execution time.

    Args:
        actual: Actual datetime
        expected: Expected datetime
        tolerance_seconds: Acceptable difference in seconds

    Raises:
        AssertionError: If datetimes differ by more than tolerance
    """
    diff = abs((actual - expected).total_seconds())
    assert (
        diff <= tolerance_seconds
    ), f"Datetimes differ by {diff}s (tolerance: {tolerance_seconds}s)"


def wait_for_condition(
    condition: Callable[[], bool], timeout_seconds: int = 5, check_interval: float = 0.1
) -> bool:
    """
    Wait for a condition to become true.

    Useful for testing async operations or polling.

    Args:
        condition: Callable that returns bool
        timeout_seconds: Maximum time to wait
        check_interval: How often to check condition

    Returns:
        True if condition became true, False if timeout

    Example:
        >>> counter = 0
        >>> def increment():
        >>>     global counter
        >>>     counter += 1
        >>> threading.Timer(0.5, increment).start()
        >>> assert wait_for_condition(lambda: counter > 0, timeout_seconds=2)
    """
    import time

    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if condition():
            return True
        time.sleep(check_interval)
    return False


async def wait_for_async_condition(
    condition: Callable[[], bool], timeout_seconds: int = 5, check_interval: float = 0.1
) -> bool:
    """
    Async version of wait_for_condition.

    Args:
        condition: Callable that returns bool
        timeout_seconds: Maximum time to wait
        check_interval: How often to check condition

    Returns:
        True if condition became true, False if timeout
    """
    import asyncio

    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout_seconds:
        if condition():
            return True
        await asyncio.sleep(check_interval)
    return False


def mock_env_vars(**env_vars) -> contextmanager:
    """
    Context manager to temporarily set environment variables.

    Args:
        **env_vars: Key-value pairs of environment variables

    Example:
        >>> with mock_env_vars(TEST_VAR='test_value'):
        >>>     assert os.getenv('TEST_VAR') == 'test_value'
        >>> assert os.getenv('TEST_VAR') is None
    """

    @contextmanager
    def _mock_env():
        old_env = {}
        for key, value in env_vars.items():
            old_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            yield
        finally:
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

    return _mock_env()


class EventCapture:
    """
    Utility for capturing events during tests.

    Useful for verifying that certain functions were called with specific arguments.
    """

    def __init__(self):
        """Initialize event capture."""
        self.events: List[Dict[str, Any]] = []

    def capture(self, event_name: str, **kwargs):
        """
        Capture an event.

        Args:
            event_name: Name of the event
            **kwargs: Event data
        """
        self.events.append({"name": event_name, "data": kwargs, "timestamp": datetime.utcnow()})

    def get_events(self, event_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get captured events.

        Args:
            event_name: Optional filter by event name

        Returns:
            List of event dicts
        """
        if event_name:
            return [e for e in self.events if e["name"] == event_name]
        return self.events

    def count(self, event_name: Optional[str] = None) -> int:
        """
        Count captured events.

        Args:
            event_name: Optional filter by event name

        Returns:
            Event count
        """
        return len(self.get_events(event_name))

    def clear(self):
        """Clear all captured events."""
        self.events.clear()

    def assert_event_occurred(self, event_name: str, count: Optional[int] = None):
        """
        Assert that an event occurred.

        Args:
            event_name: Event name to check
            count: Optional expected count

        Raises:
            AssertionError: If event didn't occur or count mismatch
        """
        events = self.get_events(event_name)
        if count is not None:
            assert len(events) == count, f"Expected {count} '{event_name}' events, got {len(events)}"
        else:
            assert len(events) > 0, f"Event '{event_name}' did not occur"


def create_mock_logger() -> Mock:
    """
    Create a mock logger for testing.

    Returns:
        Mock logger with info, warning, error, debug methods
    """
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    return logger


def assert_no_errors_logged(mock_logger: Mock):
    """
    Assert that no errors were logged.

    Args:
        mock_logger: Mock logger instance

    Raises:
        AssertionError: If errors were logged
    """
    assert mock_logger.error.call_count == 0, "Errors were logged when none expected"


def get_call_args_list(mock_obj: Mock, method: str = "call") -> List[tuple]:
    """
    Get list of call arguments for a mock.

    Args:
        mock_obj: Mock object
        method: Method name (default: 'call')

    Returns:
        List of tuples with call arguments
    """
    if method == "call":
        return [call[0] for call in mock_obj.call_args_list]
    else:
        return [call[0] for call in getattr(mock_obj, method).call_args_list]
