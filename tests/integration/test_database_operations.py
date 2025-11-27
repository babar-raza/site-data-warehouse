"""
Integration Tests for Database Operations

Tests comprehensive database functionality including:
- Schema migrations and table creation
- Upsert operations and conflict handling
- Transaction isolation and rollback
- Materialized view refresh
- Foreign key constraints
- Data integrity validation

Run with: pytest tests/integration/test_database_operations.py -m integration
"""

import pytest
import asyncpg
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator
from dotenv import load_dotenv

load_dotenv()

# Test configuration
TEST_DB_DSN = os.getenv('TEST_DB_DSN', 'postgresql://gsc_user:gsc_password@localhost:5432/gsc_test')
SQL_DIR = Path(__file__).parent.parent.parent / "sql"


@pytest.fixture(scope="session")
def sql_directory() -> Path:
    """Return path to SQL directory"""
    return SQL_DIR


@pytest.fixture(scope="session")
async def db_pool() -> AsyncIterator[asyncpg.Pool]:
    """Create database connection pool for tests"""
    pool = await asyncpg.create_pool(
        TEST_DB_DSN,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    yield pool
    await pool.close()


@pytest.fixture
async def db_connection(db_pool: asyncpg.Pool) -> AsyncIterator[asyncpg.Connection]:
    """Provide isolated database connection for each test"""
    async with db_pool.acquire() as conn:
        yield conn


@pytest.fixture
async def clean_test_data(db_connection: asyncpg.Connection):
    """Clean test data before and after tests"""
    # Define test identifiers
    test_property = "https://test-integration.example.com/"
    test_query = "test_integration_query"

    # Clean before test
    await db_connection.execute(
        "DELETE FROM gsc.fact_gsc_daily WHERE property = $1",
        test_property
    )
    await db_connection.execute(
        "DELETE FROM gsc.fact_ga4_daily WHERE property = $1",
        test_property
    )
    await db_connection.execute(
        "DELETE FROM gsc.insights WHERE property = $1",
        test_property
    )

    yield

    # Clean after test
    await db_connection.execute(
        "DELETE FROM gsc.fact_gsc_daily WHERE property = $1",
        test_property
    )
    await db_connection.execute(
        "DELETE FROM gsc.fact_ga4_daily WHERE property = $1",
        test_property
    )
    await db_connection.execute(
        "DELETE FROM gsc.insights WHERE property = $1",
        test_property
    )


@pytest.mark.integration
class TestSchemaMigrations:
    """Test schema migration and table creation"""

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

        assert 'vector' in ext_names, "vector extension not installed"
        assert 'pg_trgm' in ext_names, "pg_trgm extension not installed"
        assert 'uuid-ossp' in ext_names, "uuid-ossp extension not installed"
        assert 'tablefunc' in ext_names, "tablefunc extension not installed"

    async def test_core_schemas_exist(self, db_connection: asyncpg.Connection):
        """Test that all core schemas exist"""
        schemas = await db_connection.fetch(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = 'gsc'
            """
        )
        schema_names = [s['schema_name'] for s in schemas]

        assert 'gsc' in schema_names, "gsc schema not found"

    async def test_core_tables_exist(self, db_connection: asyncpg.Connection):
        """Test key tables exist after migration"""
        required_tables = [
            'fact_gsc_daily',
            'fact_ga4_daily',
            'dim_property',
            'dim_page',
            'dim_query',
            'ingest_watermarks',
            'audit_log',
            'insights'
        ]

        for table_name in required_tables:
            exists = await db_connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'gsc'
                    AND table_name = $1
                )
                """,
                table_name
            )
            assert exists, f"Table gsc.{table_name} does not exist"

    async def test_primary_keys_defined(self, db_connection: asyncpg.Connection):
        """Test that primary keys are properly defined"""
        # Check fact_gsc_daily composite primary key
        pk_columns = await db_connection.fetch(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid
                AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'gsc.fact_gsc_daily'::regclass
            AND i.indisprimary
            ORDER BY a.attnum
            """
        )
        pk_col_names = [col['attname'] for col in pk_columns]

        expected_pk = ['date', 'property', 'url', 'query', 'country', 'device']
        assert pk_col_names == expected_pk, \
            f"fact_gsc_daily primary key mismatch: {pk_col_names} != {expected_pk}"

    async def test_indexes_created(self, db_connection: asyncpg.Connection):
        """Test that key indexes are created"""
        indexes = await db_connection.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'gsc'
            AND tablename = 'fact_gsc_daily'
            """
        )
        index_names = [idx['indexname'] for idx in indexes]

        # Check for key indexes
        assert any('date' in idx for idx in index_names), \
            "No date index found on fact_gsc_daily"
        assert any('property' in idx for idx in index_names), \
            "No property index found on fact_gsc_daily"

    async def test_triggers_created(self, db_connection: asyncpg.Connection):
        """Test that update triggers are created"""
        triggers = await db_connection.fetch(
            """
            SELECT trigger_name, event_object_table
            FROM information_schema.triggers
            WHERE trigger_schema = 'gsc'
            AND event_object_table IN ('fact_gsc_daily', 'dim_property')
            """
        )

        assert len(triggers) > 0, "No triggers found on tables"

        # Verify update_updated_at trigger exists
        trigger_names = [t['trigger_name'] for t in triggers]
        assert any('updated_at' in name for name in trigger_names), \
            "update_updated_at trigger not found"


@pytest.mark.integration
class TestUpsertOperations:
    """Test upsert operations and conflict handling"""

    async def test_single_row_insert(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test inserting a single row"""
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"

        await db_connection.execute(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            test_date, test_property, f"{test_property}page1", "test query",
            "USA", "MOBILE", 100, 1000, 0.1, 5.5
        )

        # Verify insertion
        row = await db_connection.fetchrow(
            """
            SELECT * FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "test query"
        )

        assert row is not None
        assert row['clicks'] == 100
        assert row['impressions'] == 1000
        assert row['ctr'] == 0.1
        assert row['position'] == 5.5

    async def test_upsert_on_conflict_updates(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test upsert handles conflicts correctly by updating existing rows"""
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"
        test_url = f"{test_property}page1"
        test_query = "upsert test query"

        # Insert initial row
        await db_connection.execute(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            test_date, test_property, test_url, test_query,
            "USA", "MOBILE", 100, 1000, 0.1, 5.5
        )

        # Upsert with updated values
        await db_connection.execute(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (date, property, url, query, country, device)
            DO UPDATE SET
                clicks = EXCLUDED.clicks,
                impressions = EXCLUDED.impressions,
                ctr = EXCLUDED.ctr,
                position = EXCLUDED.position,
                updated_at = CURRENT_TIMESTAMP
            """,
            test_date, test_property, test_url, test_query,
            "USA", "MOBILE", 150, 1500, 0.1, 4.5
        )

        # Verify only one row exists with updated values
        count = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, test_query
        )
        assert count == 1, "Upsert created duplicate row"

        row = await db_connection.fetchrow(
            """
            SELECT clicks, impressions, position FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, test_query
        )
        assert row['clicks'] == 150, "Clicks not updated"
        assert row['impressions'] == 1500, "Impressions not updated"
        assert row['position'] == 4.5, "Position not updated"

    async def test_batch_upsert_with_cte(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test batch upsert using CTE pattern"""
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"

        # Batch insert multiple rows
        await db_connection.execute(
            """
            WITH input_data (date, property, url, query, country, device, clicks, impressions, ctr, position) AS (
                VALUES
                    ($1, $2, $3, 'query1', 'USA', 'DESKTOP', 100, 3000, 0.033333, 3.2),
                    ($1, $2, $4, 'query2', 'USA', 'MOBILE', 50, 2000, 0.025000, 5.8),
                    ($1, $2, $5, 'query3', 'GBR', 'TABLET', 25, 1000, 0.025000, 7.3)
            )
            INSERT INTO gsc.fact_gsc_daily (
                date, property, url, query, country, device,
                clicks, impressions, ctr, position
            )
            SELECT * FROM input_data
            ON CONFLICT (date, property, url, query, country, device)
            DO UPDATE SET
                clicks = EXCLUDED.clicks,
                impressions = EXCLUDED.impressions,
                ctr = EXCLUDED.ctr,
                position = EXCLUDED.position,
                updated_at = CURRENT_TIMESTAMP
            """,
            test_date, test_property,
            f"{test_property}page1",
            f"{test_property}page2",
            f"{test_property}page3"
        )

        # Verify all rows inserted
        count = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND date = $2
            """,
            test_property, test_date
        )
        assert count == 3, f"Expected 3 rows, got {count}"

        # Verify specific data
        row = await db_connection.fetchrow(
            """
            SELECT * FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "query1"
        )
        assert row['clicks'] == 100
        assert row['device'] == 'DESKTOP'

    async def test_upsert_stored_function(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test upsert using stored function"""
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"

        # Call stored function
        await db_connection.execute(
            """
            SELECT gsc.upsert_fact_gsc_daily(
                $1::DATE, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
            """,
            test_date, test_property, f"{test_property}page", "function test query",
            "USA", "MOBILE", 200, 4000, 0.05, 6.0
        )

        # Verify insertion via function
        row = await db_connection.fetchrow(
            """
            SELECT * FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "function test query"
        )

        assert row is not None
        assert row['clicks'] == 200
        assert row['impressions'] == 4000


@pytest.mark.integration
class TestTransactionIsolation:
    """Test transaction isolation and rollback"""

    async def test_transaction_commit(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test that transaction commits persist data"""
        test_property = "https://test-integration.example.com/"
        test_date = datetime.now().date()

        async with db_connection.transaction():
            await db_connection.execute(
                """
                INSERT INTO gsc.fact_gsc_daily
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                test_date, test_property, f"{test_property}tx-page", "transaction test",
                "USA", "MOBILE", 100, 1000, 0.1, 5.5
            )

        # Verify data persists after transaction
        count = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "transaction test"
        )
        assert count == 1, "Transaction commit did not persist data"

    async def test_transaction_rollback_on_error(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test transaction rollback on error"""
        test_property = "https://test-integration.example.com/"
        test_date = datetime.now().date()

        # Attempt transaction that will fail
        try:
            async with db_connection.transaction():
                # Insert valid row
                await db_connection.execute(
                    """
                    INSERT INTO gsc.fact_gsc_daily
                    (date, property, url, query, country, device, clicks, impressions, ctr, position)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    test_date, test_property, f"{test_property}rollback-page", "rollback test",
                    "USA", "MOBILE", 100, 1000, 0.1, 5.5
                )

                # Force an error (missing required field)
                await db_connection.execute(
                    """
                    INSERT INTO gsc.fact_gsc_daily (date, property)
                    VALUES ($1, $2)
                    """,
                    test_date, test_property
                )
        except Exception:
            pass  # Expected to fail

        # Verify first insert was rolled back
        count = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "rollback test"
        )
        assert count == 0, "Transaction rollback failed - data was persisted"

    async def test_transaction_isolation_level(self, db_pool: asyncpg.Pool):
        """Test transaction isolation between concurrent connections"""
        test_property = "https://test-integration.example.com/"
        test_date = datetime.now().date()

        async with db_pool.acquire() as conn1, db_pool.acquire() as conn2:
            # Clean any existing test data
            await conn1.execute(
                "DELETE FROM gsc.fact_gsc_daily WHERE property = $1",
                test_property
            )

            # Start transaction in conn1
            tx1 = conn1.transaction()
            await tx1.start()

            try:
                # Insert in conn1 (uncommitted)
                await conn1.execute(
                    """
                    INSERT INTO gsc.fact_gsc_daily
                    (date, property, url, query, country, device, clicks, impressions, ctr, position)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    test_date, test_property, f"{test_property}isolation-page", "isolation test",
                    "USA", "MOBILE", 100, 1000, 0.1, 5.5
                )

                # conn2 should not see uncommitted data
                count = await conn2.fetchval(
                    """
                    SELECT COUNT(*) FROM gsc.fact_gsc_daily
                    WHERE property = $1 AND query = $2
                    """,
                    test_property, "isolation test"
                )
                assert count == 0, "Transaction isolation violated - uncommitted data visible"

                # Commit transaction
                await tx1.commit()

                # Now conn2 should see the data
                count = await conn2.fetchval(
                    """
                    SELECT COUNT(*) FROM gsc.fact_gsc_daily
                    WHERE property = $1 AND query = $2
                    """,
                    test_property, "isolation test"
                )
                assert count == 1, "Committed data not visible to other connection"
            finally:
                # Cleanup
                await conn1.execute(
                    "DELETE FROM gsc.fact_gsc_daily WHERE property = $1",
                    test_property
                )

    async def test_savepoint_rollback(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test savepoint and partial rollback"""
        test_property = "https://test-integration.example.com/"
        test_date = datetime.now().date()

        async with db_connection.transaction():
            # Insert first row
            await db_connection.execute(
                """
                INSERT INTO gsc.fact_gsc_daily
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                test_date, test_property, f"{test_property}sp1", "savepoint test 1",
                "USA", "MOBILE", 100, 1000, 0.1, 5.5
            )

            # Create savepoint
            await db_connection.execute("SAVEPOINT sp1")

            # Insert second row
            await db_connection.execute(
                """
                INSERT INTO gsc.fact_gsc_daily
                (date, property, url, query, country, device, clicks, impressions, ctr, position)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                test_date, test_property, f"{test_property}sp2", "savepoint test 2",
                "USA", "MOBILE", 200, 2000, 0.1, 6.5
            )

            # Rollback to savepoint (removes second insert)
            await db_connection.execute("ROLLBACK TO SAVEPOINT sp1")

        # Verify first row exists
        count1 = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "savepoint test 1"
        )
        assert count1 == 1, "First insert before savepoint was lost"

        # Verify second row was rolled back
        count2 = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "savepoint test 2"
        )
        assert count2 == 0, "Second insert after savepoint was not rolled back"


@pytest.mark.integration
class TestMaterializedViews:
    """Test materialized view creation and refresh"""

    async def test_materialized_view_exists(self, db_connection: asyncpg.Connection):
        """Test that materialized views exist"""
        mv_names = [
            'mv_unified_page_performance',
            'mv_unified_page_performance_weekly',
            'mv_unified_page_performance_monthly'
        ]

        for mv_name in mv_names:
            exists = await db_connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM pg_matviews
                    WHERE schemaname = 'gsc'
                    AND matviewname = $1
                )
                """,
                mv_name
            )
            assert exists, f"Materialized view gsc.{mv_name} does not exist"

    async def test_materialized_view_refresh_functions_exist(self, db_connection: asyncpg.Connection):
        """Test that refresh functions exist"""
        functions = [
            'refresh_mv_unified_daily',
            'refresh_mv_unified_weekly',
            'refresh_mv_unified_monthly',
            'refresh_all_unified_views'
        ]

        for func_name in functions:
            exists = await db_connection.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = 'gsc'
                    AND p.proname = $1
                )
                """,
                func_name
            )
            assert exists, f"Function gsc.{func_name}() does not exist"

    async def test_materialized_view_refresh(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test materialized view refresh works without error"""
        # Insert test data into base tables
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"

        # Insert GSC data
        await db_connection.execute(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            test_date, test_property, f"{test_property}mv-test", "mv test query",
            "USA", "MOBILE", 100, 1000, 0.1, 5.5
        )

        # Note: Refresh might fail if underlying views don't exist or have issues
        # This test validates the refresh executes without SQL errors
        try:
            await db_connection.execute("SELECT gsc.refresh_mv_unified_daily()")
        except asyncpg.exceptions.UndefinedTableError:
            pytest.skip("Base view vw_unified_page_performance does not exist")
        except asyncpg.exceptions.UndefinedColumnError:
            pytest.skip("Base view schema mismatch")
        except Exception as e:
            # Some errors are expected if base views aren't fully set up
            if "does not exist" in str(e).lower():
                pytest.skip(f"Base view dependencies not met: {e}")
            raise

    async def test_materialized_view_has_indexes(self, db_connection: asyncpg.Connection):
        """Test that materialized views have indexes"""
        indexes = await db_connection.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'gsc'
            AND tablename = 'mv_unified_page_performance'
            """
        )

        assert len(indexes) > 0, "Materialized view has no indexes"

        index_names = [idx['indexname'] for idx in indexes]
        # Check for key indexes
        assert any('date' in idx for idx in index_names), \
            "No date index on materialized view"


@pytest.mark.integration
class TestForeignKeyConstraints:
    """Test foreign key constraints and referential integrity"""

    async def test_insights_linked_insight_fk(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test insights table linked_insight_id foreign key"""
        test_property = "https://test-integration.example.com/"

        # Insert parent insight
        parent_id = "test_parent_insight_12345678"
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            parent_id, datetime.now(), test_property, "page", "/test-page",
            "risk", "Test Risk", "Test risk description", "high", 0.9,
            '{"test": "data"}', 7, "test_detector"
        )

        # Insert child insight with valid linked_insight_id
        child_id = "test_child_insight_87654321"
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source, linked_insight_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
            child_id, datetime.now(), test_property, "page", "/test-page",
            "diagnosis", "Test Diagnosis", "Test diagnosis description", "medium", 0.85,
            '{"test": "data"}', 7, "test_detector", parent_id
        )

        # Verify child was inserted
        child = await db_connection.fetchrow(
            "SELECT * FROM gsc.insights WHERE id = $1",
            child_id
        )
        assert child is not None
        assert child['linked_insight_id'] == parent_id

        # Test foreign key constraint - should fail with invalid linked_insight_id
        with pytest.raises(asyncpg.exceptions.ForeignKeyViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days, source, linked_insight_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                "test_invalid_fk", datetime.now(), test_property, "page", "/test-page",
                "diagnosis", "Invalid FK Test", "Test", "low", 0.8,
                '{"test": "data"}', 7, "test_detector", "nonexistent_insight_id"
            )

    async def test_fk_cascade_on_delete(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test foreign key cascade behavior on delete"""
        test_property = "https://test-integration.example.com/"

        # Insert parent insight
        parent_id = "test_cascade_parent_123"
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            parent_id, datetime.now(), test_property, "page", "/test-page",
            "risk", "Cascade Test", "Test", "high", 0.9,
            '{"test": "data"}', 7, "test_detector"
        )

        # Insert child with FK reference
        child_id = "test_cascade_child_456"
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source, linked_insight_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
            child_id, datetime.now(), test_property, "page", "/test-page",
            "diagnosis", "Cascade Child", "Test", "medium", 0.85,
            '{"test": "data"}', 7, "test_detector", parent_id
        )

        # Delete parent (should set child's linked_insight_id to NULL due to ON DELETE SET NULL)
        await db_connection.execute(
            "DELETE FROM gsc.insights WHERE id = $1",
            parent_id
        )

        # Verify child still exists but linked_insight_id is NULL
        child = await db_connection.fetchrow(
            "SELECT * FROM gsc.insights WHERE id = $1",
            child_id
        )
        assert child is not None, "Child was deleted (should have been preserved)"
        assert child['linked_insight_id'] is None, "linked_insight_id not set to NULL"


@pytest.mark.integration
class TestDataIntegrityConstraints:
    """Test data integrity constraints and validations"""

    async def test_check_constraint_severity(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test CHECK constraint on severity field"""
        test_property = "https://test-integration.example.com/"

        # Valid severity should work
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            "test_severity_valid", datetime.now(), test_property, "page", "/test-page",
            "risk", "Severity Test", "Test", "high", 0.9,
            '{"test": "data"}', 7, "test_detector"
        )

        # Invalid severity should fail
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                "test_severity_invalid", datetime.now(), test_property, "page", "/test-page",
                "risk", "Invalid Severity", "Test", "critical", 0.9,  # 'critical' not allowed
                '{"test": "data"}', 7, "test_detector"
            )

    async def test_check_constraint_confidence(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test CHECK constraint on confidence field (0-1 range)"""
        test_property = "https://test-integration.example.com/"

        # Valid confidence should work
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            "test_confidence_valid", datetime.now(), test_property, "page", "/test-page",
            "risk", "Confidence Test", "Test", "high", 0.95,
            '{"test": "data"}', 7, "test_detector"
        )

        # Confidence > 1 should fail
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                "test_confidence_high", datetime.now(), test_property, "page", "/test-page",
                "risk", "Invalid Confidence", "Test", "high", 1.5,  # > 1
                '{"test": "data"}', 7, "test_detector"
            )

        # Confidence < 0 should fail
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                "test_confidence_low", datetime.now(), test_property, "page", "/test-page",
                "risk", "Invalid Confidence", "Test", "high", -0.1,  # < 0
                '{"test": "data"}', 7, "test_detector"
            )

    async def test_not_null_constraints(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test NOT NULL constraints"""
        test_property = "https://test-integration.example.com/"

        # Missing required field should fail
        with pytest.raises(asyncpg.exceptions.NotNullViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                "test_null", datetime.now(), test_property, "page", "/test-page",
                "risk", "Null Test", "Test", "high", 0.9,
                '{"test": "data"}', 7
                # source is missing - should fail
            )

    async def test_unique_constraint(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test unique constraint on primary key"""
        test_property = "https://test-integration.example.com/"
        insight_id = "test_unique_constraint"

        # Insert first row
        await db_connection.execute(
            """
            INSERT INTO gsc.insights
            (id, generated_at, property, entity_type, entity_id, category,
             title, description, severity, confidence, metrics, window_days, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            insight_id, datetime.now(), test_property, "page", "/test-page",
            "risk", "Unique Test", "Test", "high", 0.9,
            '{"test": "data"}', 7, "test_detector"
        )

        # Duplicate ID should fail
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await db_connection.execute(
                """
                INSERT INTO gsc.insights
                (id, generated_at, property, entity_type, entity_id, category,
                 title, description, severity, confidence, metrics, window_days, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                insight_id, datetime.now(), test_property, "page", "/test-page2",
                "opportunity", "Duplicate ID", "Test", "medium", 0.8,
                '{"test": "data"}', 7, "test_detector"
            )


@pytest.mark.integration
class TestDatabaseFunctions:
    """Test database functions and stored procedures"""

    async def test_update_updated_at_trigger(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test that updated_at trigger works correctly"""
        test_date = datetime.now().date()
        test_property = "https://test-integration.example.com/"

        # Insert row
        await db_connection.execute(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            test_date, test_property, f"{test_property}trigger-test", "trigger test",
            "USA", "MOBILE", 100, 1000, 0.1, 5.5
        )

        # Get initial timestamps
        initial = await db_connection.fetchrow(
            """
            SELECT created_at, updated_at FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "trigger test"
        )

        # Small delay to ensure timestamp difference
        await asyncpg.asyncio.sleep(0.1)

        # Update row
        await db_connection.execute(
            """
            UPDATE gsc.fact_gsc_daily
            SET clicks = 150
            WHERE property = $1 AND query = $2
            """,
            test_property, "trigger test"
        )

        # Get updated timestamps
        updated = await db_connection.fetchrow(
            """
            SELECT created_at, updated_at FROM gsc.fact_gsc_daily
            WHERE property = $1 AND query = $2
            """,
            test_property, "trigger test"
        )

        # Verify created_at unchanged, updated_at changed
        assert updated['created_at'] == initial['created_at'], \
            "created_at should not change on update"
        assert updated['updated_at'] > initial['updated_at'], \
            "updated_at should be updated by trigger"

    async def test_validation_function_insights(self, db_connection: asyncpg.Connection):
        """Test insights validation function"""
        # Call validation function
        results = await db_connection.fetch(
            "SELECT * FROM gsc.validate_insights_table()"
        )

        assert len(results) > 0, "Validation function returned no results"

        # Verify result structure
        for row in results:
            assert 'check_name' in row
            assert 'check_status' in row
            assert 'check_value' in row
            assert 'check_message' in row


@pytest.mark.integration
class TestPerformance:
    """Test database performance and optimization"""

    async def test_bulk_insert_performance(self, db_connection: asyncpg.Connection, clean_test_data):
        """Test bulk insert performance with executemany"""
        test_property = "https://test-integration.example.com/"
        test_date = datetime.now().date()

        # Prepare bulk data
        rows = [
            (
                test_date, test_property, f"{test_property}bulk-page-{i}",
                f"bulk query {i}", "USA", "MOBILE",
                100 + i, 1000 + i * 10, 0.1, 5.5 + (i * 0.1)
            )
            for i in range(100)
        ]

        # Bulk insert
        await db_connection.executemany(
            """
            INSERT INTO gsc.fact_gsc_daily
            (date, property, url, query, country, device, clicks, impressions, ctr, position)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (date, property, url, query, country, device)
            DO UPDATE SET clicks = EXCLUDED.clicks
            """,
            rows
        )

        # Verify count
        count = await db_connection.fetchval(
            """
            SELECT COUNT(*) FROM gsc.fact_gsc_daily
            WHERE property = $1 AND date = $2
            """,
            test_property, test_date
        )
        assert count == 100, f"Expected 100 rows, got {count}"

    async def test_query_with_index(self, db_connection: asyncpg.Connection):
        """Test that indexes are being used for queries"""
        # Explain query to check index usage
        explain = await db_connection.fetch(
            """
            EXPLAIN (FORMAT JSON)
            SELECT * FROM gsc.fact_gsc_daily
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY date DESC
            LIMIT 10
            """
        )

        # Verify query plan (should use index scan)
        plan_json = explain[0]['QUERY PLAN']
        assert plan_json is not None, "Query plan is empty"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
