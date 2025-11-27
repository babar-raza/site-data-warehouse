# Integration Tests

This directory contains integration tests that validate database operations, schema migrations, and system integration points.

## Database Integration Tests

### `test_database_operations.py`

Comprehensive database integration tests covering:

#### Test Categories

1. **Schema Migrations** (`TestSchemaMigrations`)
   - PostgreSQL extensions installed (vector, pg_trgm, uuid-ossp, tablefunc)
   - Core schemas exist (gsc)
   - All key tables created correctly
   - Primary keys defined properly
   - Indexes created on fact tables
   - Update triggers configured

2. **Upsert Operations** (`TestUpsertOperations`)
   - Single row inserts
   - Upsert conflict handling (ON CONFLICT DO UPDATE)
   - Batch upserts using CTE pattern
   - Stored function upserts
   - Data integrity after upserts

3. **Transaction Isolation** (`TestTransactionIsolation`)
   - Transaction commits persist data
   - Transaction rollback on error
   - Isolation between concurrent connections
   - Savepoint and partial rollback

4. **Materialized Views** (`TestMaterializedViews`)
   - Materialized views exist
   - Refresh functions exist and work
   - Materialized views have proper indexes
   - View refresh without errors

5. **Foreign Key Constraints** (`TestForeignKeyConstraints`)
   - Foreign key relationships enforced
   - Cascade behavior (ON DELETE SET NULL)
   - Referential integrity maintained

6. **Data Integrity Constraints** (`TestDataIntegrityConstraints`)
   - CHECK constraints on severity, confidence
   - NOT NULL constraints enforced
   - UNIQUE constraints on primary keys
   - Valid value ranges enforced

7. **Database Functions** (`TestDatabaseFunctions`)
   - update_updated_at trigger works
   - Validation functions execute correctly

8. **Performance** (`TestPerformance`)
   - Bulk insert performance
   - Index usage in queries
   - Query plan optimization

## Prerequisites

### 1. PostgreSQL Test Database

Create a test database with required extensions:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create test database
CREATE DATABASE gsc_test;
\c gsc_test

# Create test user
CREATE USER gsc_user WITH PASSWORD 'gsc_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE gsc_test TO gsc_user;
ALTER DATABASE gsc_test OWNER TO gsc_user;

# Install extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS tablefunc;
```

### 2. Environment Variables

Set the test database connection string:

```bash
# Linux/Mac
export TEST_DB_DSN="postgresql://gsc_user:gsc_password@localhost:5432/gsc_test"

# Windows (PowerShell)
$env:TEST_DB_DSN = "postgresql://gsc_user:gsc_password@localhost:5432/gsc_test"

# Windows (CMD)
set TEST_DB_DSN=postgresql://gsc_user:gsc_password@localhost:5432/gsc_test
```

Or create a `.env` file in the project root:

```
TEST_DB_DSN=postgresql://gsc_user:gsc_password@localhost:5432/gsc_test
```

### 3. Apply Schema Migrations

Run all SQL migration files in order:

```bash
# From project root
psql $TEST_DB_DSN -f sql/00_extensions.sql
psql $TEST_DB_DSN -f sql/01_schema.sql
psql $TEST_DB_DSN -f sql/02_upsert_template.sql
psql $TEST_DB_DSN -f sql/04_ga4_schema.sql
psql $TEST_DB_DSN -f sql/05_unified_view.sql
psql $TEST_DB_DSN -f sql/06_materialized_views.sql
psql $TEST_DB_DSN -f sql/11_insights_table.sql
# ... and other schema files as needed
```

Or use the setup script if available:

```bash
./scripts/setup/init_database.sh
```

### 4. Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

Required packages:
- pytest
- pytest-asyncio
- asyncpg
- python-dotenv

## Running Tests

### Run All Integration Tests

```bash
# From project root
pytest tests/integration/test_database_operations.py -m integration -v
```

### Run Specific Test Classes

```bash
# Test schema migrations only
pytest tests/integration/test_database_operations.py::TestSchemaMigrations -v

# Test upsert operations only
pytest tests/integration/test_database_operations.py::TestUpsertOperations -v

# Test transactions only
pytest tests/integration/test_database_operations.py::TestTransactionIsolation -v
```

### Run Specific Test Methods

```bash
# Test specific functionality
pytest tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates -v
```

### Run with Output

```bash
# Show print statements and detailed output
pytest tests/integration/test_database_operations.py -m integration -v -s
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/integration/test_database_operations.py -m integration --cov=. --cov-report=html
```

## Test Fixtures

### Session-Scoped Fixtures

- `sql_directory`: Returns path to SQL directory for schema files
- `db_pool`: Creates asyncpg connection pool (shared across tests)

### Test-Scoped Fixtures

- `db_connection`: Provides isolated database connection for each test
- `clean_test_data`: Cleans test data before and after each test

## Test Data

Tests use isolated test data with:
- Test property: `https://test-integration.example.com/`
- Test queries: Prefixed with `test_integration_` or similar
- Automatic cleanup before and after each test

## Continuous Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: gsc_user
          POSTGRES_PASSWORD: gsc_password
          POSTGRES_DB: gsc_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt

      - name: Apply migrations
        run: |
          export PGPASSWORD=gsc_password
          psql -h localhost -U gsc_user -d gsc_test -f sql/00_extensions.sql
          psql -h localhost -U gsc_user -d gsc_test -f sql/01_schema.sql
          # ... apply other migrations

      - name: Run integration tests
        env:
          TEST_DB_DSN: postgresql://gsc_user:gsc_password@localhost:5432/gsc_test
        run: |
          pytest tests/integration/test_database_operations.py -m integration -v
```

## Troubleshooting

### Connection Errors

If you get connection errors:

1. Verify PostgreSQL is running: `pg_isready`
2. Check connection string is correct
3. Verify user has proper permissions
4. Check firewall allows connections to port 5432

### Extension Errors

If tests fail due to missing extensions:

```sql
-- Connect as superuser
psql -U postgres gsc_test

-- Install missing extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS tablefunc;
```

### Schema Errors

If tables don't exist:

```bash
# Apply all schema migrations
for f in sql/*.sql; do
  echo "Applying $f"
  psql $TEST_DB_DSN -f "$f"
done
```

### Permission Errors

If you get permission errors:

```sql
-- Grant all privileges to test user
GRANT ALL PRIVILEGES ON DATABASE gsc_test TO gsc_user;
GRANT ALL PRIVILEGES ON SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gsc TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA gsc TO gsc_user;
```

## Best Practices

1. **Isolation**: Each test should be isolated and not depend on other tests
2. **Cleanup**: Use fixtures to clean up test data before and after tests
3. **Transactions**: Use transactions for rollback testing
4. **Assertions**: Include clear, specific assertions with helpful error messages
5. **Coverage**: Aim for comprehensive coverage of all database operations
6. **Performance**: Monitor test execution time; optimize slow tests
7. **Documentation**: Keep test docstrings up to date

## Agent Orchestration Integration Tests

### `test_agent_orchestration.py`

Comprehensive integration tests for the multi-agent orchestration system, validating agent-to-agent communication, workflow coordination, and failure handling.

#### Test Categories

1. **Agent Communication** (`TestAgentCommunication`) - 5 tests
   - Basic publish/subscribe functionality
   - Message correlation IDs for request tracking
   - Wildcard topic matching
   - Priority message handling
   - Failed message handling and dead letter queue

2. **Watcher → Diagnostician Flow** (`TestWatcherToDiagnostician`) - 4 tests
   - Anomaly detection triggers diagnosis
   - Watcher stores findings for Diagnostician
   - Diagnostician analyzes Watcher findings
   - Diagnosis correlation with anomalies

3. **Diagnostician → Strategist Flow** (`TestDiagnosticianToStrategist`) - 3 tests
   - Diagnosis triggers recommendation generation
   - Strategist generates recommendations from diagnosis
   - Recommendation priority based on diagnosis severity

4. **Full Pipeline Through Dispatcher** (`TestFullPipeline`) - 3 tests
   - Complete pipeline: Watcher → Diagnostician → Strategist → Dispatcher
   - Dispatcher executes Strategist recommendations
   - Pipeline handles multiple recommendations

5. **Failure Propagation** (`TestFailurePropagation`) - 5 tests
   - Watcher failure stops pipeline
   - Diagnostician failure propagates to Strategist
   - Dispatcher rollback on validation failure
   - Error recovery and retry mechanisms
   - Cascading failure detection

6. **Multi-Agent Coordination** (`TestMultiAgentCoordination`) - 4 tests
   - Concurrent agent processing
   - Health monitoring during workflow
   - Message ordering preservation
   - Agent state synchronization

7. **Edge Cases** (`TestEdgeCases`) - 4 tests
   - Empty finding handling
   - Malformed message handling
   - Timeout handling
   - Agent shutdown during processing

**Total: 28 tests, all passing**

#### Running Agent Orchestration Tests

```bash
# Run all orchestration tests
pytest tests/integration/test_agent_orchestration.py -v -m integration

# Run specific test class
pytest tests/integration/test_agent_orchestration.py::TestFullPipeline -v

# Run specific test
pytest tests/integration/test_agent_orchestration.py::TestFullPipeline::test_complete_pipeline_anomaly_to_execution -v
```

#### Test Fixtures

- `message_bus`: MessageBus instance for agent communication
- `mock_db_pool`: Mock database pool with comprehensive test data
- `watcher_agent`: Watcher agent configured for testing
- `diagnostician_agent`: Diagnostician agent configured for testing
- `strategist_agent`: Strategist agent configured for testing
- `dispatcher_agent`: Dispatcher agent configured for testing

#### Mocking Strategy

- **LLM Calls**: Disabled (`use_llm=False`) for deterministic tests
- **Database**: Mocked with AsyncMock, returns realistic test data
- **External Services**: Fully mocked (execution engine, validator, outcome monitor)

#### Test Results

```
28 passed, 1 warning in 5.41s
```

All integration tests pass successfully with 100% success rate, no TODOs remaining.

## Related Documentation

- [Main Testing Guide](../README.md)
- [SQL Schema Documentation](../../sql/README.md)
- [Database Setup Guide](../../docs/deployment/DATABASE_SETUP.md)
- [PostgreSQL Best Practices](../../docs/guides/POSTGRES_BEST_PRACTICES.md)
