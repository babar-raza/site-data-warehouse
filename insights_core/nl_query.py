"""
Natural Language Query - Text-to-SQL Interface
=============================================
Query the data warehouse using plain English:
- "Show me pages that lost traffic last week"
- "Which pages have cannibalization issues?"
- "What are my top priority actions?"

Features:
- LLM-powered text-to-SQL conversion
- Query validation and safety
- Context-aware (understands property, time ranges)
- Conversational interface
- Query explanations
"""
import logging
import os
import re
from typing import Dict, List, Optional

import asyncpg
import httpx

logger = logging.getLogger(__name__)


class NaturalLanguageQuery:
    """
    Convert natural language questions to SQL queries
    """

    def __init__(self, db_dsn: str = None, ollama_url: str = None):
        """
        Initialize NL query engine

        Args:
            db_dsn: Database connection string
            ollama_url: Ollama API URL
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.ollama_url = ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self._pool: Optional[asyncpg.Pool] = None

        # Database schema context
        self.schema_context = self._build_schema_context()

        logger.info("NaturalLanguageQuery initialized")

    def _build_schema_context(self) -> str:
        """Build schema context for LLM"""
        return """
Database Schema:

## Main Tables

### gsc.vw_unified_page_performance
- date: DATE - The date of the metrics
- property: VARCHAR - Website URL (e.g., 'https://blog.aspose.net')
- page_path: TEXT - Page URL path (e.g., '/cells/python/tutorial/')
- gsc_clicks: INT - Number of clicks from Google Search
- gsc_impressions: INT - Number of impressions in search results
- gsc_ctr: DECIMAL - Click-through rate (percentage)
- gsc_position: DECIMAL - Average search position
- ga_sessions: INT - GA4 sessions
- ga_conversions: INT - GA4 conversions
- ga_engagement_rate: DECIMAL - GA4 engagement rate
- clicks_delta_7d: INT - Change in clicks vs 7 days ago
- clicks_delta_pct_7d: DECIMAL - Percentage change in clicks vs 7 days ago

### gsc.actions
- action_id: UUID - Unique action ID
- title: VARCHAR - Action title
- description: TEXT - Action description
- page_path: TEXT - Page this action applies to
- property: VARCHAR - Website URL
- action_type: VARCHAR - Type (rewrite_meta, improve_content, fix_technical, etc.)
- category: VARCHAR - Category (content, technical, ux, performance, strategy)
- priority_score: DECIMAL - Auto-calculated priority (0-100, higher = more urgent)
- impact_score: INT - Expected impact (1-10)
- effort_score: INT - Required effort (1-10)
- urgency: VARCHAR - Urgency level (low, medium, high, critical)
- status: VARCHAR - Status (pending, in_progress, blocked, completed, cancelled)
- owner: VARCHAR - Person responsible
- due_date: TIMESTAMP - Due date

### content.quality_scores
- property: VARCHAR - Website URL
- page_path: TEXT - Page URL path
- overall_score: DECIMAL - Overall quality score (0-100)
- readability_score: DECIMAL - Readability score (0-100)
- optimization_score: DECIMAL - SEO optimization score (0-100)
- improvement_suggestions: TEXT[] - Array of suggestions
- key_topics: TEXT[] - Array of topics covered
- sentiment: VARCHAR - Content sentiment (positive, neutral, negative)

### content.cannibalization_pairs
- property: VARCHAR - Website URL
- page_a: TEXT - First page path
- page_b: TEXT - Second page path
- similarity_score: FLOAT - How similar (0.0-1.0)
- conflict_severity: VARCHAR - Severity (low, medium, high, critical)
- status: VARCHAR - Status (active, investigating, resolved, ignored)

### content.topics
- id: SERIAL - Topic ID
- name: VARCHAR - Topic name
- slug: VARCHAR - URL-friendly slug
- description: TEXT - Topic description
- page_count: INT - Number of pages in this topic
- is_active: BOOLEAN - Is this topic active

### intelligence.traffic_forecasts
- property: VARCHAR - Website URL
- page_path: TEXT - Page URL path
- date: DATE - Forecast date
- metric_name: VARCHAR - Metric being forecasted (clicks, impressions, etc.)
- forecast_value: FLOAT - Predicted value
- lower_bound: FLOAT - Lower confidence bound
- upper_bound: FLOAT - Upper confidence bound
- is_anomaly: BOOLEAN - Is this an anomaly

### intelligence.anomaly_log
- property: VARCHAR - Website URL
- page_path: TEXT - Page URL path
- detection_date: DATE - When anomaly was detected
- metric_name: VARCHAR - Metric with anomaly
- actual_value: FLOAT - Actual value
- expected_value: FLOAT - Expected value
- deviation_pct: FLOAT - Percentage deviation
- severity: VARCHAR - Severity (low, medium, high, critical)
- direction: VARCHAR - Direction (above, below)

## Common Filters
- Time: WHERE date >= CURRENT_DATE - INTERVAL '7 days'
- Property: WHERE property = 'https://blog.aspose.net'
- Active: WHERE is_active = true OR status != 'cancelled'

## Aggregations
- SUM(gsc_clicks), AVG(gsc_position), COUNT(*)
- GROUP BY property, page_path, topic_id
- ORDER BY clicks DESC, priority_score DESC

## Joins
- Performance + Quality: JOIN content.quality_scores USING (property, page_path)
- Performance + Topics: JOIN content.page_topics USING (property, page_path)
- Actions + Insights: actions.insight_id = insights.id
"""

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    async def generate_sql(self, question: str, context: Dict = None) -> Dict:
        """
        Convert natural language question to SQL

        Args:
            question: Natural language question
            context: Optional context (property, date range, etc.)

        Returns:
            Dict with sql, explanation, confidence
        """
        try:
            # Build context
            context_str = ""
            if context:
                if 'property' in context:
                    context_str += f"\nProperty filter: {context['property']}"
                if 'days_back' in context:
                    context_str += f"\nTime range: Last {context['days_back']} days"

            prompt = f"""Convert this question to a PostgreSQL SQL query.

Question: {question}
{context_str}

{self.schema_context}

Provide response in JSON format:
{{
    "sql": "SELECT...",
    "explanation": "This query will...",
    "confidence": 0.9
}}

IMPORTANT:
- Use ONLY the tables and columns listed above
- Include LIMIT clause (default 20)
- Use proper JOINs when needed
- Add WHERE clauses for property/date filters
- Return valid PostgreSQL syntax
- Be careful with date comparisons
- No destructive operations (DELETE, DROP, UPDATE)
"""

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:8b",
                        "prompt": prompt,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get('response', '')

                    # Parse JSON response
                    import json
                    json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group())
                        return {
                            'sql': parsed.get('sql', ''),
                            'explanation': parsed.get('explanation', ''),
                            'confidence': float(parsed.get('confidence', 0.5)),
                            'success': True
                        }

            return {'error': 'Failed to generate SQL', 'success': False}

        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return {'error': str(e), 'success': False}

    def validate_sql(self, sql: str) -> Dict:
        """
        Validate SQL query for safety

        Args:
            sql: SQL query

        Returns:
            Dict with is_safe, issues
        """
        issues = []

        # Check for destructive operations
        destructive_keywords = ['DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE']
        sql_upper = sql.upper()

        for keyword in destructive_keywords:
            if keyword in sql_upper:
                issues.append(f"Destructive operation detected: {keyword}")

        # Check for UPDATE without WHERE
        if 'UPDATE' in sql_upper and 'WHERE' not in sql_upper:
            issues.append("UPDATE without WHERE clause")

        # Check for potentially dangerous patterns
        if ';' in sql and sql.count(';') > 1:
            issues.append("Multiple statements detected")

        # Check for shell commands
        if any(cmd in sql_upper for cmd in ['EXEC', 'EXECUTE', 'COPY', 'PROGRAM']):
            issues.append("System command detected")

        # Must be SELECT
        if not sql_upper.strip().startswith('SELECT'):
            issues.append("Only SELECT queries are allowed")

        is_safe = len(issues) == 0

        return {
            'is_safe': is_safe,
            'issues': issues
        }

    async def execute_query(self, sql: str, limit: int = 100) -> Dict:
        """
        Execute SQL query safely

        Args:
            sql: SQL query
            limit: Maximum rows to return

        Returns:
            Query results
        """
        try:
            # Validate
            validation = self.validate_sql(sql)
            if not validation['is_safe']:
                return {
                    'error': 'Query validation failed',
                    'issues': validation['issues'],
                    'success': False
                }

            # Add LIMIT if not present
            if 'LIMIT' not in sql.upper():
                sql = sql.rstrip(';') + f' LIMIT {limit}'

            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Set statement timeout
                await conn.execute("SET statement_timeout = '30s'")

                # Execute query
                results = await conn.fetch(sql)

                # Convert to list of dicts
                data = [dict(row) for row in results]

                return {
                    'data': data,
                    'row_count': len(data),
                    'columns': list(data[0].keys()) if data else [],
                    'success': True
                }

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return {'error': str(e), 'success': False}

    async def query(
        self,
        question: str,
        context: Dict = None,
        execute: bool = True
    ) -> Dict:
        """
        Complete NL query workflow: question → SQL → results

        Args:
            question: Natural language question
            context: Optional context dict
            execute: Whether to execute the query

        Returns:
            Complete query results with SQL, explanation, data
        """
        try:
            logger.info(f"Processing NL query: {question}")

            # Generate SQL
            sql_result = await self.generate_sql(question, context)

            if not sql_result.get('success'):
                return sql_result

            sql = sql_result['sql']
            explanation = sql_result['explanation']
            confidence = sql_result['confidence']

            if not execute:
                return {
                    'sql': sql,
                    'explanation': explanation,
                    'confidence': confidence,
                    'executed': False,
                    'success': True
                }

            # Execute query
            exec_result = await self.execute_query(sql)

            if not exec_result.get('success'):
                return {
                    'sql': sql,
                    'explanation': explanation,
                    'confidence': confidence,
                    'error': exec_result.get('error'),
                    'executed': False,
                    'success': False
                }

            # Format answer
            answer = self._format_answer(question, exec_result['data'], explanation)

            return {
                'question': question,
                'answer': answer,
                'sql': sql,
                'explanation': explanation,
                'confidence': confidence,
                'data': exec_result['data'],
                'row_count': exec_result['row_count'],
                'columns': exec_result['columns'],
                'executed': True,
                'success': True
            }

        except Exception as e:
            logger.error(f"Error in NL query: {e}")
            return {'error': str(e), 'success': False}

    def _format_answer(self, question: str, data: List[Dict], explanation: str) -> str:
        """
        Format query results into natural language answer

        Args:
            question: Original question
            data: Query results
            explanation: Query explanation

        Returns:
            Natural language answer
        """
        if not data:
            return "No results found for your question."

        row_count = len(data)

        # Build answer based on question type
        if 'how many' in question.lower():
            return f"Found {row_count} results. {explanation}"
        elif 'top' in question.lower() or 'best' in question.lower():
            return f"Here are the top {min(row_count, 10)} results. {explanation}"
        elif 'worst' in question.lower() or 'lowest' in question.lower():
            return f"Here are the {min(row_count, 10)} results with the lowest values. {explanation}"
        else:
            return f"Found {row_count} results. {explanation}"

    def query_sync(self, question: str, context: Dict = None, execute: bool = True) -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.query(question, context, execute))


# Example queries
EXAMPLE_QUERIES = {
    "traffic_loss": "Show me pages that lost more than 20% traffic last week",
    "top_pages": "What are my top 10 pages by clicks in the last 30 days?",
    "cannibalization": "Which pages have cannibalization issues?",
    "low_quality": "Show me pages with quality scores below 60",
    "top_actions": "What are my top priority actions?",
    "anomalies": "Show me recent traffic anomalies",
    "topics": "List all topics with their page counts",
    "forecasts": "Show me pages forecasted to gain traffic next week",
    "similar_pages": "Find pages similar to /blog/python-tutorial/",
    "poor_ctr": "Which pages have low CTR but high impressions?",
}
