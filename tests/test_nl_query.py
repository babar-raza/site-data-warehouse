"""
Tests for Natural Language Query Module
========================================
Tests text-to-SQL conversion and query execution.
"""
import os
import pytest
from unittest.mock import AsyncMock, Mock, patch

from insights_core.nl_query import NaturalLanguageQuery, QueryValidator


@pytest.fixture
async def nl_query():
    """Create NaturalLanguageQuery instance"""
    nlq = NaturalLanguageQuery(
        db_dsn=os.getenv('TEST_WAREHOUSE_DSN', 'postgresql://test:test@localhost:5432/test_db'),
        ollama_url='http://localhost:11434'
    )
    yield nlq
    await nlq.close()


@pytest.fixture
def validator():
    """Create QueryValidator instance"""
    return QueryValidator()


# =============================================
# SQL GENERATION TESTS
# =============================================

@pytest.mark.asyncio
async def test_generate_sql_simple_query(nl_query):
    """Test simple query generation"""
    question = "Show me the top 10 pages by clicks"

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '''```sql
SELECT page_path, SUM(clicks) as total_clicks
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY page_path
ORDER BY total_clicks DESC
LIMIT 10;
```'''
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await nl_query.generate_sql(question)

    assert 'sql' in result
    assert 'SELECT' in result['sql'].upper()
    assert 'LIMIT 10' in result['sql'].upper()


@pytest.mark.asyncio
async def test_generate_sql_with_context(nl_query):
    """Test SQL generation with context"""
    question = "Which pages lost traffic last week?"
    context = {
        'property': 'https://blog.aspose.net',
        'time_period': 'last_week'
    }

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '''```sql
SELECT page_path, clicks, clicks_prev_period,
       clicks - clicks_prev_period as clicks_change
FROM gsc.vw_unified_page_performance
WHERE property = 'https://blog.aspose.net'
  AND date >= CURRENT_DATE - INTERVAL '7 days'
  AND clicks < clicks_prev_period
ORDER BY clicks_change ASC;
```'''
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await nl_query.generate_sql(question, context)

    assert 'sql' in result
    assert 'blog.aspose.net' in result['sql']


@pytest.mark.asyncio
async def test_generate_sql_complex_query(nl_query):
    """Test complex aggregation query"""
    question = "What is the average position by topic?"

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '''```sql
SELECT t.name as topic_name,
       AVG(v.gsc_position) as avg_position,
       COUNT(DISTINCT pt.page_path) as page_count
FROM content.topics t
JOIN content.page_topics pt ON t.id = pt.topic_id
JOIN gsc.vw_unified_page_performance v
  ON pt.property = v.property AND pt.page_path = v.page_path
WHERE v.date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY t.name
ORDER BY avg_position ASC;
```'''
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await nl_query.generate_sql(question)

    assert 'sql' in result
    assert 'JOIN' in result['sql'].upper()
    assert 'GROUP BY' in result['sql'].upper()


# =============================================
# QUERY VALIDATION TESTS
# =============================================

def test_validate_sql_select_allowed(validator):
    """Test that SELECT queries are allowed"""
    sql = "SELECT * FROM gsc.vw_unified_page_performance LIMIT 10"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is True
    assert len(validation['issues']) == 0


def test_validate_sql_insert_blocked(validator):
    """Test that INSERT queries are blocked"""
    sql = "INSERT INTO gsc.actions (title) VALUES ('test')"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is False
    assert any('INSERT' in issue for issue in validation['issues'])


def test_validate_sql_update_blocked(validator):
    """Test that UPDATE queries are blocked"""
    sql = "UPDATE gsc.actions SET status = 'completed'"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is False
    assert any('UPDATE' in issue for issue in validation['issues'])


def test_validate_sql_delete_blocked(validator):
    """Test that DELETE queries are blocked"""
    sql = "DELETE FROM gsc.actions WHERE status = 'pending'"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is False
    assert any('DELETE' in issue for issue in validation['issues'])


def test_validate_sql_drop_blocked(validator):
    """Test that DROP queries are blocked"""
    sql = "DROP TABLE gsc.actions"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is False
    assert any('DROP' in issue for issue in validation['issues'])


def test_validate_sql_semicolon_injection(validator):
    """Test protection against SQL injection with semicolons"""
    sql = "SELECT * FROM gsc.actions; DROP TABLE gsc.actions;"

    validation = validator.validate_sql(sql)

    assert validation['is_safe'] is False


def test_validate_sql_comment_injection(validator):
    """Test protection against comment-based injection"""
    sql = "SELECT * FROM gsc.actions WHERE id = 1 -- AND status = 'pending'"

    validation = validator.validate_sql(sql)

    # Should warn about comments
    assert validation['is_safe'] is True  # Still safe, but warned
    assert len(validation['warnings']) > 0


def test_validate_sql_allowed_tables(validator):
    """Test that only whitelisted tables are allowed"""
    # Allowed table
    sql1 = "SELECT * FROM gsc.vw_unified_page_performance"
    assert validator.validate_sql(sql1)['is_safe'] is True

    # Disallowed table (not in whitelist)
    sql2 = "SELECT * FROM pg_user"
    validation2 = validator.validate_sql(sql2)

    # Should issue warning about non-whitelisted table
    assert len(validation2['warnings']) > 0


def test_validate_sql_limit_check(validator):
    """Test that queries without LIMIT are warned"""
    sql = "SELECT * FROM gsc.vw_unified_page_performance"

    validation = validator.validate_sql(sql)

    # Should warn about missing LIMIT
    assert len(validation['warnings']) > 0


# =============================================
# QUERY EXECUTION TESTS
# =============================================

@pytest.mark.asyncio
async def test_execute_query_success(nl_query):
    """Test successful query execution"""
    sql = "SELECT page_path, clicks FROM gsc.vw_unified_page_performance LIMIT 5"

    with patch.object(nl_query, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {'page_path': '/page1/', 'clicks': 100},
            {'page_path': '/page2/', 'clicks': 150}
        ]

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        result = await nl_query.execute_query(sql)

    assert result['success'] is True
    assert result['row_count'] == 2
    assert len(result['data']) == 2


@pytest.mark.asyncio
async def test_execute_query_error(nl_query):
    """Test query execution with error"""
    sql = "SELECT * FROM nonexistent_table"

    with patch.object(nl_query, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = Exception("Table does not exist")

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        result = await nl_query.execute_query(sql)

    assert result['success'] is False
    assert 'error' in result


@pytest.mark.asyncio
async def test_execute_query_timeout(nl_query):
    """Test query execution timeout"""
    sql = "SELECT * FROM large_table"

    with patch.object(nl_query, 'get_pool') as mock_pool:
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = asyncio.TimeoutError()

        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        result = await nl_query.execute_query(sql, timeout=1.0)

    assert result['success'] is False
    assert 'timeout' in result['error'].lower()


# =============================================
# END-TO-END QUERY TESTS
# =============================================

@pytest.mark.asyncio
async def test_query_end_to_end_success(nl_query):
    """Test complete query workflow"""
    question = "Show me top 5 pages by clicks"

    with patch.object(nl_query, 'generate_sql') as mock_gen:
        mock_gen.return_value = {
            'sql': "SELECT page_path, SUM(clicks) as total FROM gsc.vw_unified_page_performance GROUP BY page_path ORDER BY total DESC LIMIT 5",
            'explanation': "This query aggregates clicks by page"
        }

        with patch.object(nl_query, 'validate_sql') as mock_val:
            mock_val.return_value = {'is_safe': True, 'issues': [], 'warnings': []}

            with patch.object(nl_query, 'execute_query') as mock_exec:
                mock_exec.return_value = {
                    'success': True,
                    'data': [
                        {'page_path': '/page1/', 'total': 1000},
                        {'page_path': '/page2/', 'total': 800}
                    ],
                    'row_count': 2
                }

                result = await nl_query.query(question, execute=True)

    assert result['success'] is True
    assert 'sql' in result
    assert 'data' in result
    assert len(result['data']) == 2
    assert 'answer' in result


@pytest.mark.asyncio
async def test_query_validation_failure(nl_query):
    """Test query blocked by validation"""
    question = "Delete all actions"

    with patch.object(nl_query, 'generate_sql') as mock_gen:
        mock_gen.return_value = {
            'sql': "DELETE FROM gsc.actions",
            'explanation': "This deletes all actions"
        }

        with patch.object(nl_query, 'validate_sql') as mock_val:
            mock_val.return_value = {
                'is_safe': False,
                'issues': ['DELETE operations not allowed'],
                'warnings': []
            }

            result = await nl_query.query(question, execute=True)

    assert result['success'] is False
    assert 'validation_failed' in result
    assert len(result['validation_issues']) > 0


@pytest.mark.asyncio
async def test_query_dry_run(nl_query):
    """Test query generation without execution"""
    question = "Show me pages with low quality scores"

    with patch.object(nl_query, 'generate_sql') as mock_gen:
        mock_gen.return_value = {
            'sql': "SELECT page_path, overall_score FROM content.quality_scores WHERE overall_score < 60",
            'explanation': "Finds pages with quality < 60"
        }

        with patch.object(nl_query, 'validate_sql') as mock_val:
            mock_val.return_value = {'is_safe': True, 'issues': [], 'warnings': []}

            result = await nl_query.query(question, execute=False)

    assert result['success'] is True
    assert 'sql' in result
    assert 'data' not in result  # Not executed


# =============================================
# COMMON QUERY PATTERNS
# =============================================

@pytest.mark.parametrize("question,expected_keyword", [
    ("Top 10 pages by traffic", "ORDER BY"),
    ("Pages with cannibalization", "cannibalization"),
    ("Average position by topic", "AVG"),
    ("Pages that lost traffic", "clicks_change"),
    ("Content quality below 60", "quality_scores"),
])
@pytest.mark.asyncio
async def test_common_query_patterns(nl_query, question, expected_keyword):
    """Test common query patterns"""
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': f'```sql\nSELECT * FROM table WHERE condition\n```'
        }

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await nl_query.generate_sql(question)

        # Just check that SQL was generated
        assert 'sql' in result


# =============================================
# ERROR HANDLING TESTS
# =============================================

@pytest.mark.asyncio
async def test_generate_sql_llm_failure(nl_query):
    """Test handling of LLM failure"""
    question = "Show me data"

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 500

        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

        result = await nl_query.generate_sql(question)

    assert 'error' in result


@pytest.mark.asyncio
async def test_query_empty_question(nl_query):
    """Test handling of empty question"""
    result = await nl_query.query("", execute=False)

    assert result['success'] is False


@pytest.mark.asyncio
async def test_query_invalid_context(nl_query):
    """Test handling of invalid context"""
    question = "Show me data"
    context = {"invalid_key": "value"}

    # Should still work, just ignore invalid context
    with patch.object(nl_query, 'generate_sql') as mock_gen:
        mock_gen.return_value = {'sql': 'SELECT 1', 'explanation': 'test'}

        with patch.object(nl_query, 'validate_sql') as mock_val:
            mock_val.return_value = {'is_safe': True, 'issues': [], 'warnings': []}

            result = await nl_query.query(question, context, execute=False)

    assert result['success'] is True


# =============================================
# SYNC WRAPPER TESTS
# =============================================

def test_query_sync(nl_query):
    """Test synchronous wrapper"""
    with patch.object(nl_query, 'generate_sql') as mock_gen:
        mock_gen.return_value = {'sql': 'SELECT 1', 'explanation': 'test'}

        with patch.object(nl_query, 'validate_sql') as mock_val:
            mock_val.return_value = {'is_safe': True, 'issues': [], 'warnings': []}

            with patch.object(nl_query, 'execute_query') as mock_exec:
                mock_exec.return_value = {'success': True, 'data': [], 'row_count': 0}

                result = nl_query.query_sync("Test question", execute=True)

    assert result['success'] is True


# =============================================
# INTEGRATION TESTS
# =============================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_query_execution():
    """Integration test with real database"""
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        pytest.skip("Integration tests not enabled")

    nlq = NaturalLanguageQuery()

    try:
        # Test simple query
        result = await nlq.query(
            "Show me the top 5 pages by clicks in the last 30 days",
            execute=True
        )

        assert result['success'] is True
        assert 'data' in result

    finally:
        await nlq.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
