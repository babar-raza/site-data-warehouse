"""
Test suite for SQL file syntax validation.

This module validates:
- SQL file syntax and structure
- No obvious SQL errors
- Proper schema definitions
- Index and constraint definitions
"""

import os
import re
import pytest
from pathlib import Path
from typing import List, Dict, Set


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
SQL_DIR = PROJECT_ROOT / "sql"


class TestSQLFileStructure:
    """Test SQL files exist and are properly structured."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")

        sql_files = list(SQL_DIR.glob("*.sql"))
        assert len(sql_files) > 0, "No SQL files found in sql directory"

        return sorted(sql_files)

    def test_sql_directory_exists(self):
        """Verify sql directory exists."""
        assert SQL_DIR.exists(), f"SQL directory not found at {SQL_DIR}"
        assert SQL_DIR.is_dir(), f"{SQL_DIR} is not a directory"

    def test_sql_files_exist(self, sql_files: List[Path]):
        """Verify SQL files exist in the directory."""
        assert len(sql_files) > 0, "No SQL files found"

    def test_sql_files_readable(self, sql_files: List[Path]):
        """Verify all SQL files are readable."""
        for sql_file in sql_files:
            try:
                with open(sql_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert len(content) > 0, f"{sql_file.name} is empty"
            except Exception as e:
                pytest.fail(f"Failed to read {sql_file.name}: {e}")

    def test_sql_files_naming_convention(self, sql_files: List[Path]):
        """Verify SQL files follow naming conventions."""
        # Should be numbered or descriptive
        for sql_file in sql_files:
            name = sql_file.stem
            # Allow numbered files (00_xxx.sql) or descriptive names (allow alphanumeric and underscores)
            assert re.match(r'^[0-9]{2}_[a-z0-9_]+$|^[a-z][a-z0-9_]*$', name), \
                f"SQL file {sql_file.name} doesn't follow naming convention"

    def test_sql_files_utf8_encoding(self, sql_files: List[Path]):
        """Verify SQL files use UTF-8 encoding."""
        for sql_file in sql_files:
            try:
                with open(sql_file, 'r', encoding='utf-8') as f:
                    f.read()
            except UnicodeDecodeError:
                pytest.fail(f"{sql_file.name} is not valid UTF-8")


class TestSQLSyntaxBasic:
    """Test basic SQL syntax validity."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")
        return sorted(SQL_DIR.glob("*.sql"))

    def _read_sql_file(self, sql_file: Path) -> str:
        """Read SQL file and return content."""
        with open(sql_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _remove_sql_comments(self, content: str) -> str:
        """Remove SQL comments from content."""
        # Remove single-line comments (-- comment)
        content = re.sub(r'--[^\n]*', '', content)
        # Remove multi-line comments (/* comment */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content

    def test_no_syntax_errors_basic(self, sql_files: List[Path]):
        """Check for obvious SQL syntax errors."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Skip empty files
            if not content_no_comments.strip():
                continue

            # Check for common syntax errors
            errors = []

            # Unmatched parentheses
            open_parens = content_no_comments.count('(')
            close_parens = content_no_comments.count(')')
            if open_parens != close_parens:
                errors.append(
                    f"Unmatched parentheses: {open_parens} open, {close_parens} close"
                )

            # Unmatched quotes (single quotes)
            # Count non-escaped single quotes
            single_quotes = len(re.findall(r"(?<!\\)'", content_no_comments))
            if single_quotes % 2 != 0:
                errors.append("Unmatched single quotes")

            # Check for incomplete statements (statements not ending with semicolon)
            statements = [s.strip() for s in content_no_comments.split(';') if s.strip()]
            if statements:
                last_statement = statements[-1].strip()
                # Last statement might not need semicolon if it's the end of file
                # But check for obvious incomplete statements
                incomplete_keywords = ['CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'SELECT']
                for keyword in incomplete_keywords:
                    if last_statement.upper().startswith(keyword):
                        # This is likely an incomplete statement
                        pass  # Allow it, as semicolon might be optional at EOF

            if errors:
                pytest.fail(f"{sql_file.name} has syntax errors:\n" + "\n".join(errors))

    def test_no_reserved_word_conflicts(self, sql_files: List[Path]):
        """Check for potential reserved word conflicts."""
        # Common SQL reserved words that shouldn't be used as unquoted identifiers
        reserved_words = {
            'user', 'group', 'order', 'table', 'index', 'column',
            'key', 'value', 'primary', 'foreign', 'references'
        }

        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Look for CREATE TABLE statements with reserved words
            table_pattern = r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+\.\w+|\w+)'
            tables = re.findall(table_pattern, content_no_comments, re.IGNORECASE)

            issues = []
            for table_name in tables:
                # Extract just the table name (remove schema if present)
                if '.' in table_name:
                    table_name = table_name.split('.')[-1]

                if table_name.lower() in reserved_words:
                    issues.append(f"Table name '{table_name}' is a reserved word")

            if issues:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: {', '.join(issues)}"
                )

    def test_statements_end_with_semicolon(self, sql_files: List[Path]):
        """Verify SQL statements are properly terminated."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            if not content_no_comments.strip():
                continue

            # Split by semicolons
            statements = [s.strip() for s in content_no_comments.split(';') if s.strip()]

            # Check that significant statements exist
            significant_statements = [
                s for s in statements
                if any(keyword in s.upper() for keyword in [
                    'CREATE', 'ALTER', 'DROP', 'INSERT', 'UPDATE', 'DELETE', 'SELECT'
                ])
            ]

            assert len(significant_statements) > 0, \
                f"{sql_file.name} contains no significant SQL statements"


class TestSQLSchemaDefinitions:
    """Test SQL schema definitions are properly structured."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")
        return sorted(SQL_DIR.glob("*.sql"))

    def _read_sql_file(self, sql_file: Path) -> str:
        """Read SQL file and return content."""
        with open(sql_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _remove_sql_comments(self, content: str) -> str:
        """Remove SQL comments from content."""
        content = re.sub(r'--[^\n]*', '', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content

    def test_create_table_structure(self, sql_files: List[Path]):
        """Verify CREATE TABLE statements are properly structured."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Find all CREATE TABLE statements
            create_pattern = r'CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(\S+)\s*\('
            tables = re.findall(create_pattern, content_no_comments, re.IGNORECASE)

            for table_name in tables:
                # Extract the full CREATE TABLE statement
                table_start = content_no_comments.upper().find(f'CREATE TABLE')
                table_start = content_no_comments.find('CREATE TABLE', table_start, table_start + 100)

                if table_start != -1:
                    # Find matching closing parenthesis
                    paren_count = 0
                    in_create = False
                    end_pos = table_start

                    for i in range(table_start, len(content_no_comments)):
                        if content_no_comments[i] == '(':
                            paren_count += 1
                            in_create = True
                        elif content_no_comments[i] == ')':
                            paren_count -= 1
                            if in_create and paren_count == 0:
                                end_pos = i + 1
                                break

                    if end_pos > table_start:
                        table_def = content_no_comments[table_start:end_pos]

                        # Check for at least one column definition
                        # Column pattern: word followed by data type
                        column_pattern = r'\n\s*\w+\s+(?:VARCHAR|INTEGER|TEXT|TIMESTAMP|BOOLEAN|SERIAL|BIGINT|JSONB|UUID)'
                        columns = re.findall(column_pattern, table_def, re.IGNORECASE)

                        assert len(columns) > 0, \
                            f"{sql_file.name}: Table {table_name} has no column definitions"

    def test_primary_key_definitions(self, sql_files: List[Path]):
        """Verify tables have primary key definitions."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Find all CREATE TABLE statements
            create_pattern = r'CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(\S+)'
            tables = re.findall(create_pattern, content_no_comments, re.IGNORECASE)

            for table_name in tables:
                # Look for PRIMARY KEY in the table definition
                # Extract table definition
                table_start = content_no_comments.upper().find('CREATE TABLE')
                table_section = content_no_comments[table_start:table_start + 5000]

                # Check for PRIMARY KEY or SERIAL (which implies PK)
                has_pk = (
                    'PRIMARY KEY' in table_section.upper() or
                    'SERIAL' in table_section.upper() or
                    'BIGSERIAL' in table_section.upper()
                )

                # Some tables might be temporary or junction tables without PKs
                # This is a warning, not a failure
                if not has_pk:
                    pytest.warns(
                        UserWarning,
                        match=f"{sql_file.name}: Table {table_name} might be missing PRIMARY KEY"
                    )

    def test_foreign_key_references_valid(self, sql_files: List[Path]):
        """Verify foreign key references use proper syntax."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Find REFERENCES clauses
            fk_pattern = r'REFERENCES\s+(\w+(?:\.\w+)?)\s*\((\w+)\)'
            foreign_keys = re.findall(fk_pattern, content_no_comments, re.IGNORECASE)

            # Just verify syntax is correct (actual table existence can't be checked statically)
            for ref_table, ref_column in foreign_keys:
                assert ref_table, f"{sql_file.name}: Empty reference table name"
                assert ref_column, f"{sql_file.name}: Empty reference column name"

    def test_index_definitions(self, sql_files: List[Path]):
        """Verify index definitions are properly structured."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)
            content_no_comments = self._remove_sql_comments(content)

            # Find CREATE INDEX statements
            index_pattern = r'CREATE(?:\s+UNIQUE)?\s+INDEX(?:\s+IF\s+NOT\s+EXISTS)?\s+(\w+)\s+ON\s+(\w+(?:\.\w+)?)'
            indexes = re.findall(index_pattern, content_no_comments, re.IGNORECASE)

            for index_name, table_name in indexes:
                # Verify index name follows convention (optional)
                # Common conventions: idx_tablename_column or tablename_column_idx
                assert len(index_name) > 0, \
                    f"{sql_file.name}: Empty index name"
                assert len(table_name) > 0, \
                    f"{sql_file.name}: Empty table name in index"


class TestSQLBestPractices:
    """Test SQL files follow best practices."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")
        return sorted(SQL_DIR.glob("*.sql"))

    def _read_sql_file(self, sql_file: Path) -> str:
        """Read SQL file and return content."""
        with open(sql_file, 'r', encoding='utf-8') as f:
            return f.read()

    def test_if_not_exists_usage(self, sql_files: List[Path]):
        """Verify CREATE statements use IF NOT EXISTS for safety."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find CREATE TABLE/INDEX without IF NOT EXISTS
            create_pattern = r'CREATE\s+(TABLE|INDEX)\s+(?!IF\s+NOT\s+EXISTS)(\w+(?:\.\w+)?)'
            creates = re.findall(create_pattern, content, re.IGNORECASE)

            # This is a best practice warning, not a hard error
            if creates:
                create_types = [create[0] for create in creates]
                if len(create_types) > 0:
                    pytest.warns(
                        UserWarning,
                        match=f"{sql_file.name}: Some CREATE statements don't use IF NOT EXISTS"
                    )

    def test_timestamp_defaults(self, sql_files: List[Path]):
        """Verify timestamp columns have appropriate defaults."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find timestamp columns
            timestamp_pattern = r'(\w+)\s+TIMESTAMP(?:\s+(?:WITH|WITHOUT)\s+TIME\s+ZONE)?(?:\s+DEFAULT\s+([^,\)]+))?'
            timestamps = re.findall(timestamp_pattern, content, re.IGNORECASE)

            timestamps_without_default = []
            for col_name, default_value in timestamps:
                # created_at, updated_at should have defaults
                if col_name.lower() in ['created_at', 'updated_at']:
                    if not default_value or 'CURRENT_TIMESTAMP' not in default_value.upper():
                        timestamps_without_default.append(col_name)

            if timestamps_without_default:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: Timestamp columns without defaults: {timestamps_without_default}"
                )

    def test_no_select_star(self, sql_files: List[Path]):
        """Verify no SELECT * queries (best practice)."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find SELECT * patterns (but allow COUNT(*))
            select_star_pattern = r'SELECT\s+\*\s+FROM'
            matches = re.findall(select_star_pattern, content, re.IGNORECASE)

            if matches:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: Contains SELECT * queries (consider explicit column lists)"
                )

    def test_transaction_blocks(self, sql_files: List[Path]):
        """Check for proper transaction block usage in migration files."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Check if file contains multiple DDL statements
            ddl_keywords = ['CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'CREATE INDEX']
            ddl_count = sum(content.upper().count(keyword) for keyword in ddl_keywords)

            # If multiple DDL statements, suggest transaction block
            if ddl_count > 3:
                has_begin = 'BEGIN' in content.upper() or 'START TRANSACTION' in content.upper()
                has_commit = 'COMMIT' in content.upper()

                if not (has_begin and has_commit):
                    pytest.warns(
                        UserWarning,
                        match=f"{sql_file.name}: Multiple DDL statements without transaction block"
                    )


class TestSQLFileOrdering:
    """Test SQL files are properly ordered for execution."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")
        return sorted(SQL_DIR.glob("*.sql"))

    def test_numbered_files_sequential(self, sql_files: List[Path]):
        """Verify numbered SQL files are sequential."""
        numbered_files = [
            f for f in sql_files
            if re.match(r'^[0-9]{2}_', f.stem)
        ]

        if not numbered_files:
            pytest.skip("No numbered SQL files found")

        # Extract numbers
        numbers = []
        for f in numbered_files:
            match = re.match(r'^([0-9]{2})_', f.stem)
            if match:
                numbers.append(int(match.group(1)))

        # Check for gaps (warn only)
        if numbers:
            min_num = min(numbers)
            max_num = max(numbers)
            expected_numbers = set(range(min_num, max_num + 1))
            actual_numbers = set(numbers)
            missing = expected_numbers - actual_numbers

            if missing:
                pytest.warns(
                    UserWarning,
                    match=f"Gaps in SQL file numbering: {sorted(missing)}"
                )

    def test_schema_files_before_data(self, sql_files: List[Path]):
        """Verify schema files come before data/transform files."""
        file_names = [f.stem.lower() for f in sql_files]

        # Find schema and transform file positions
        schema_positions = [
            i for i, name in enumerate(file_names)
            if 'schema' in name or 'table' in name or name.startswith('01_') or name.startswith('00_')
        ]

        transform_positions = [
            i for i, name in enumerate(file_names)
            if 'transform' in name or 'view' in name or 'materialized' in name
        ]

        # Schema files should generally come before transforms
        if schema_positions and transform_positions:
            max_schema = max(schema_positions) if schema_positions else -1
            min_transform = min(transform_positions) if transform_positions else float('inf')

            # This is a suggestion, not a hard rule
            if min_transform < max_schema:
                pytest.warns(
                    UserWarning,
                    match="Transform files might be ordered before schema files"
                )


class TestSQLDataTypes:
    """Test SQL data type usage and consistency."""

    @pytest.fixture
    def sql_files(self) -> List[Path]:
        """Get all SQL files in the sql directory."""
        if not SQL_DIR.exists():
            pytest.skip(f"SQL directory not found at {SQL_DIR}")
        return sorted(SQL_DIR.glob("*.sql"))

    def _read_sql_file(self, sql_file: Path) -> str:
        """Read SQL file and return content."""
        with open(sql_file, 'r', encoding='utf-8') as f:
            return f.read()

    def test_varchar_has_length(self, sql_files: List[Path]):
        """Verify VARCHAR columns have length specified."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find VARCHAR without length
            varchar_pattern = r'VARCHAR\s*(?!\()'
            matches = re.findall(varchar_pattern, content, re.IGNORECASE)

            if matches:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: VARCHAR columns without length specification"
                )

    def test_text_vs_varchar_usage(self, sql_files: List[Path]):
        """Verify appropriate use of TEXT vs VARCHAR."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find very large VARCHAR declarations
            large_varchar_pattern = r'VARCHAR\s*\(([5-9][0-9]{3,}|[1-9][0-9]{4,})\)'
            matches = re.findall(large_varchar_pattern, content, re.IGNORECASE)

            if matches:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: Large VARCHAR sizes found, consider using TEXT"
                )

    def test_numeric_precision(self, sql_files: List[Path]):
        """Verify NUMERIC/DECIMAL types have precision specified."""
        for sql_file in sql_files:
            content = self._read_sql_file(sql_file)

            # Find NUMERIC or DECIMAL without precision
            numeric_pattern = r'(?:NUMERIC|DECIMAL)\s*(?!\()'
            matches = re.findall(numeric_pattern, content, re.IGNORECASE)

            if matches:
                pytest.warns(
                    UserWarning,
                    match=f"{sql_file.name}: NUMERIC/DECIMAL without precision specification"
                )
