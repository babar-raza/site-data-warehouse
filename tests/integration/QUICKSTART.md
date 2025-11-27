# Database Integration Tests - Quick Start

## TL;DR

```bash
# 1. Set up test database
createdb gsc_test
psql gsc_test -c "CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;"

# 2. Apply migrations
psql gsc_test -f sql/00_extensions.sql
psql gsc_test -f sql/01_schema.sql
psql gsc_test -f sql/04_ga4_schema.sql
psql gsc_test -f sql/11_insights_table.sql

# 3. Set environment variable
export TEST_DB_DSN="postgresql://gsc_user:gsc_password@localhost:5432/gsc_test"

# 4. Run tests
pytest tests/integration/test_database_operations.py -m integration -v
```

## What Gets Tested

### 28 Comprehensive Tests Covering:

1. **Schema Migrations** (6 tests)
   - Extensions installed correctly
   - Schemas and tables exist
   - Primary keys and indexes created
   - Triggers configured

2. **Upsert Operations** (4 tests)
   - Single and batch inserts
   - Conflict resolution
   - Stored function upserts

3. **Transactions** (4 tests)
   - Commit/rollback behavior
   - Isolation between connections
   - Savepoints

4. **Materialized Views** (4 tests)
   - View existence
   - Refresh functions
   - Index optimization

5. **Foreign Keys** (2 tests)
   - Constraint enforcement
   - Cascade behavior

6. **Data Integrity** (4 tests)
   - CHECK constraints
   - NOT NULL enforcement
   - UNIQUE constraints

7. **Database Functions** (2 tests)
   - Trigger functionality
   - Validation functions

8. **Performance** (2 tests)
   - Bulk operations
   - Index usage

## Quick Commands

```bash
# Run all integration tests
pytest tests/integration/test_database_operations.py -m integration

# Run specific test class
pytest tests/integration/test_database_operations.py::TestUpsertOperations -v

# Run single test
pytest tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates -v

# Show detailed output
pytest tests/integration/test_database_operations.py -m integration -v -s

# Run without coverage (faster)
pytest tests/integration/test_database_operations.py -m integration --no-cov
```

## Prerequisites Checklist

- [ ] PostgreSQL 14+ running
- [ ] Test database created (`gsc_test`)
- [ ] Required extensions installed (vector, pg_trgm, uuid-ossp, tablefunc)
- [ ] Schema migrations applied (sql/*.sql files)
- [ ] TEST_DB_DSN environment variable set
- [ ] Python packages installed (pytest, pytest-asyncio, asyncpg)

## Common Issues

### "Connection refused"
```bash
# Check PostgreSQL is running
pg_isready

# Start PostgreSQL if needed
sudo systemctl start postgresql  # Linux
brew services start postgresql   # Mac
net start postgresql-x64-14      # Windows
```

### "Extension does not exist"
```sql
-- Connect as superuser
psql -U postgres gsc_test

-- Install missing extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS tablefunc;
```

### "Table does not exist"
```bash
# Apply schema migrations in order
for f in sql/*.sql; do
  psql $TEST_DB_DSN -f "$f"
done
```

### "Permission denied"
```sql
-- Grant permissions to test user
GRANT ALL PRIVILEGES ON DATABASE gsc_test TO gsc_user;
GRANT ALL PRIVILEGES ON SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gsc TO gsc_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gsc TO gsc_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA gsc TO gsc_user;
```

## Test Output

Successful test run will show:
```
============================= test session starts ==============================
collected 28 items

tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed PASSED [  3%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_schemas_exist PASSED [  7%]
...
============================== 28 passed in 5.23s ===============================
```

## Next Steps

After tests pass:
1. Review [README.md](./README.md) for detailed documentation
2. Integrate into CI/CD pipeline
3. Add custom tests for your specific requirements
4. Set up continuous monitoring

## Need Help?

- Full documentation: [README.md](./README.md)
- Database setup: `../../docs/deployment/DATABASE_SETUP.md`
- PostgreSQL guide: `../../docs/guides/POSTGRES_BEST_PRACTICES.md`
- Report issues: GitHub Issues
