# Example Test Execution Output

This document shows what successful test execution looks like.

## Test Discovery

```bash
$ pytest tests/integration/test_database_operations.py --collect-only
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
rootdir: /path/to/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
collected 28 items

<Module test_database_operations.py>
  <Class TestSchemaMigrations>
    <Coroutine test_extensions_installed>
    <Coroutine test_core_schemas_exist>
    <Coroutine test_core_tables_exist>
    <Coroutine test_primary_keys_defined>
    <Coroutine test_indexes_created>
    <Coroutine test_triggers_created>
  <Class TestUpsertOperations>
    <Coroutine test_single_row_insert>
    <Coroutine test_upsert_on_conflict_updates>
    <Coroutine test_batch_upsert_with_cte>
    <Coroutine test_upsert_stored_function>
  <Class TestTransactionIsolation>
    <Coroutine test_transaction_commit>
    <Coroutine test_transaction_rollback_on_error>
    <Coroutine test_transaction_isolation_level>
    <Coroutine test_savepoint_rollback>
  <Class TestMaterializedViews>
    <Coroutine test_materialized_view_exists>
    <Coroutine test_materialized_view_refresh_functions_exist>
    <Coroutine test_materialized_view_refresh>
    <Coroutine test_materialized_view_has_indexes>
  <Class TestForeignKeyConstraints>
    <Coroutine test_insights_linked_insight_fk>
    <Coroutine test_fk_cascade_on_delete>
  <Class TestDataIntegrityConstraints>
    <Coroutine test_check_constraint_severity>
    <Coroutine test_check_constraint_confidence>
    <Coroutine test_not_null_constraints>
    <Coroutine test_unique_constraint>
  <Class TestDatabaseFunctions>
    <Coroutine test_update_updated_at_trigger>
    <Coroutine test_validation_function_insights>
  <Class TestPerformance>
    <Coroutine test_bulk_insert_performance>
    <Coroutine test_query_with_index>

========================== 28 tests collected in 1.23s ===========================
```

## Successful Test Run

```bash
$ pytest tests/integration/test_database_operations.py -m integration -v
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /path/to/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
collected 28 items

tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed PASSED [  3%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_schemas_exist PASSED [  7%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_tables_exist PASSED [ 10%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_primary_keys_defined PASSED [ 14%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_indexes_created PASSED [ 17%]
tests/integration/test_database_operations.py::TestSchemaMigrations::test_triggers_created PASSED [ 21%]
tests/integration/test_database_operations.py::TestUpsertOperations::test_single_row_insert PASSED [ 25%]
tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates PASSED [ 28%]
tests/integration/test_database_operations.py::TestUpsertOperations::test_batch_upsert_with_cte PASSED [ 32%]
tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_stored_function PASSED [ 35%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_commit PASSED [ 39%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_rollback_on_error PASSED [ 42%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_isolation_level PASSED [ 46%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_savepoint_rollback PASSED [ 50%]
tests/integration/test_database_operations.py::TestMaterializedViews::test_materialized_view_exists PASSED [ 53%]
tests/integration/test_database_operations.py::TestMaterializedViews::test_materialized_view_refresh_functions_exist PASSED [ 57%]
tests/integration/test_database_operations.py::TestMaterializedViews::test_materialized_view_refresh PASSED [ 60%]
tests/integration/test_database_operations.py::TestMaterializedViews::test_materialized_view_has_indexes PASSED [ 64%]
tests/integration/test_database_operations.py::TestForeignKeyConstraints::test_insights_linked_insight_fk PASSED [ 67%]
tests/integration/test_database_operations.py::TestForeignKeyConstraints::test_fk_cascade_on_delete PASSED [ 71%]
tests/integration/test_database_operations.py::TestDataIntegrityConstraints::test_check_constraint_severity PASSED [ 75%]
tests/integration/test_database_operations.py::TestDataIntegrityConstraints::test_check_constraint_confidence PASSED [ 78%]
tests/integration/test_database_operations.py::TestDataIntegrityConstraints::test_not_null_constraints PASSED [ 82%]
tests/integration/test_database_operations.py::TestDataIntegrityConstraints::test_unique_constraint PASSED [ 85%]
tests/integration/test_database_operations.py::TestDatabaseFunctions::test_update_updated_at_trigger PASSED [ 89%]
tests/integration/test_database_operations.py::TestDatabaseFunctions::test_validation_function_insights PASSED [ 92%]
tests/integration/test_database_operations.py::TestPerformance::test_bulk_insert_performance PASSED [ 96%]
tests/integration/test_database_operations.py::TestPerformance::test_query_with_index PASSED [100%]

============================== 28 passed in 5.42s ==============================
```

## Test Run with Verbose Output

```bash
$ pytest tests/integration/test_database_operations.py::TestUpsertOperations -v -s
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /path/to/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
collected 4 items

tests/integration/test_database_operations.py::TestUpsertOperations::test_single_row_insert
Test inserting a single row
  ✓ Row inserted successfully
  ✓ Data matches expected values
PASSED

tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates
Test upsert handles conflicts correctly by updating existing rows
  ✓ Initial row inserted: 100 clicks, 1000 impressions
  ✓ Upsert executed: 150 clicks, 1500 impressions
  ✓ Only 1 row exists (no duplicate)
  ✓ Values updated correctly
PASSED

tests/integration/test_database_operations.py::TestUpsertOperations::test_batch_upsert_with_cte
Test batch upsert using CTE pattern
  ✓ Batch of 3 rows inserted
  ✓ All rows verified in database
  ✓ Data integrity maintained
PASSED

tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_stored_function
Test upsert using stored function
  ✓ Stored function called successfully
  ✓ Data inserted via function
  ✓ Values match expected
PASSED

============================== 4 passed in 1.87s ===============================
```

## Failed Test Example (Setup Issue)

```bash
$ pytest tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed -v
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /path/to/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
collected 1 item

tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed FAILED [100%]

================================== FAILURES ===================================
_________________ TestSchemaMigrations.test_extensions_installed _______________

    async def test_extensions_installed(self, db_connection: asyncpg.Connection):
        """Test that required PostgreSQL extensions are installed"""
        extensions = await db_connection.fetch(
            """
            SELECT extname
            FROM pg_extension
            WHERE extname IN ('vector', 'pg_trgm', 'uuid-ossp', 'tablefunc')
            ORDER BY extname
            """
        )
        ext_names = [e['extname'] for e in extensions]

>       assert 'vector' in ext_names, "vector extension not installed"
E       AssertionError: vector extension not installed
E       assert 'vector' in ['pg_trgm', 'uuid-ossp']

tests/integration/test_database_operations.py:85: AssertionError
========================== short test summary info ============================
FAILED tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed - AssertionError: vector extension not installed
============================== 1 failed in 0.23s ===============================

HINT: Install missing extension:
  psql $TEST_DB_DSN -c "CREATE EXTENSION vector;"
```

## Test Run with Coverage Report

```bash
$ pytest tests/integration/test_database_operations.py -m integration --cov=. --cov-report=term
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /path/to/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0, cov-report=term
collected 28 items

tests/integration/test_database_operations.py ............................
                                                                      [100%]

----------- coverage: platform linux, python 3.11.0-final-0 -----------
Name                                               Stmts   Miss  Cover
----------------------------------------------------------------------
tests/integration/test_database_operations.py        425      0   100%
----------------------------------------------------------------------
TOTAL                                                425      0   100%

============================== 28 passed in 5.67s ==============================
```

## Running Specific Test Class

```bash
$ pytest tests/integration/test_database_operations.py::TestTransactionIsolation -v
```

```
============================= test session starts =============================
collected 4 items

tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_commit PASSED [ 25%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_rollback_on_error PASSED [ 50%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_isolation_level PASSED [ 75%]
tests/integration/test_database_operations.py::TestTransactionIsolation::test_savepoint_rollback PASSED [100%]

============================== 4 passed in 2.13s ===============================
```

## Running Single Test

```bash
$ pytest tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates -v
```

```
============================= test session starts =============================
collected 1 item

tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates PASSED [100%]

============================== 1 passed in 0.58s ===============================
```

## Test Summary

```bash
$ pytest tests/integration/test_database_operations.py -m integration --tb=no -q
```

```
............................                                             [100%]
28 passed in 5.12s
```

## Test Duration Report

```bash
$ pytest tests/integration/test_database_operations.py -m integration --durations=10
```

```
============================= test session starts =============================
collected 28 items

tests/integration/test_database_operations.py ............................
                                                                      [100%]

============================= slowest 10 durations =============================
0.82s call     tests/integration/test_database_operations.py::TestTransactionIsolation::test_transaction_isolation_level
0.45s call     tests/integration/test_database_operations.py::TestPerformance::test_bulk_insert_performance
0.38s call     tests/integration/test_database_operations.py::TestUpsertOperations::test_batch_upsert_with_cte
0.32s call     tests/integration/test_database_operations.py::TestMaterializedViews::test_materialized_view_refresh
0.28s call     tests/integration/test_database_operations.py::TestTransactionIsolation::test_savepoint_rollback
0.25s call     tests/integration/test_database_operations.py::TestForeignKeyConstraints::test_insights_linked_insight_fk
0.22s call     tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_tables_exist
0.18s call     tests/integration/test_database_operations.py::TestDataIntegrityConstraints::test_check_constraint_confidence
0.15s call     tests/integration/test_database_operations.py::TestUpsertOperations::test_upsert_on_conflict_updates
0.12s call     tests/integration/test_database_operations.py::TestDatabaseFunctions::test_update_updated_at_trigger

============================== 28 passed in 5.23s ==============================
```

## Parallel Test Execution

```bash
$ pytest tests/integration/test_database_operations.py -m integration -n 4
```

```
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
plugins: xdist-3.5.0, forked-1.6.0, asyncio-1.2.0, cov-7.0.0
gw0 [7] / gw1 [7] / gw2 [7] / gw3 [7]
............................                                             [100%]
============================== 28 passed in 2.85s ==============================
```

## CI/CD Output Example

```yaml
# GitHub Actions output
Run pytest tests/integration/test_database_operations.py -m integration -v
============================= test session starts =============================
platform linux -- Python 3.11.0, pytest-8.4.2, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /home/runner/work/site-data-warehouse/site-data-warehouse
configfile: pytest.ini
plugins: asyncio-1.2.0, cov-7.0.0
collected 28 items

tests/integration/test_database_operations.py::TestSchemaMigrations::test_extensions_installed ✓
tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_schemas_exist ✓
tests/integration/test_database_operations.py::TestSchemaMigrations::test_core_tables_exist ✓
...
============================== 28 passed in 5.67s ==============================

✓ All integration tests passed
```

## Key Indicators

### ✅ Healthy Test Run
- All 28 tests collected
- All tests passed
- Execution time: 5-7 seconds
- No warnings or errors
- 100% pass rate

### ⚠️ Setup Issues
- Connection refused → PostgreSQL not running
- Extension missing → Need to install extensions
- Table missing → Need to apply migrations
- Permission denied → Need to grant privileges

### ❌ Test Failures
- Assertion errors → Code or schema issues
- Timeout errors → Performance problems
- Connection errors → Database configuration issues
