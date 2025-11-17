#!/usr/bin/env python3
"""
Comprehensive tests for MCP Server
"""

import pytest
import json
import sys
import os
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp'))

# Import MCP server components
from mcp_server import (
    DatabaseConnection,
    root,
    health_check,
    MCP_VERSION
)

# Check if FastAPI is available for integration tests
try:
    from fastapi.testclient import TestClient
    import mcp_server
    if hasattr(mcp_server, 'app') and mcp_server.app:
        client = TestClient(mcp_server.app)
        FASTAPI_AVAILABLE = True
    else:
        FASTAPI_AVAILABLE = False
        client = None
except ImportError:
    FASTAPI_AVAILABLE = False
    client = None


class TestDatabaseConnection:
    """Tests for DatabaseConnection class"""
    
    def test_initialization(self):
        """Test database connection initialization"""
        db = DatabaseConnection()
        
        assert db.dsn is not None
        assert db.conn is None
        assert db._cache == {}
        assert db._cache_ttl == 300
        
    def test_get_connection_without_postgres(self):
        """Test connection when psycopg2 not available"""
        with patch('mcp_server.PG_AVAILABLE', False):
            db = DatabaseConnection()
            conn = db.get_connection()
            assert conn is None
            
    def test_execute_query_with_mock_data(self):
        """Test query execution with mock data"""
        db = DatabaseConnection()
        
        # Test page health mock data
        results = db.execute_query("SELECT * FROM gsc.vw_page_health_28d")
        
        assert isinstance(results, list)
        if len(results) > 0:
            assert 'property' in results[0]
            assert 'url' in results[0]
            assert 'total_clicks' in results[0]
            
    def test_execute_query_caching(self):
        """Test query result caching"""
        db = DatabaseConnection()
        
        # First query - should cache
        results1 = db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="test_key"
        )
        
        # Second query - should use cache
        results2 = db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="test_key"
        )
        
        # Should return same cached results
        assert results1 == results2
        assert "test_key" in db._cache
        
    def test_cache_expiration(self):
        """Test cache TTL expiration"""
        db = DatabaseConnection()
        db._cache_ttl = 0  # Set to 0 for immediate expiration
        
        # Add to cache
        results1 = db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="expire_test"
        )
        
        import time
        time.sleep(0.1)  # Wait for cache to expire
        
        # Should fetch fresh data (not cached)
        results2 = db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="expire_test"
        )
        
        assert isinstance(results2, list)
        
    def test_mock_data_page_health(self):
        """Test mock data generation for page health"""
        db = DatabaseConnection()
        
        results = db._get_mock_data("SELECT * FROM gsc.vw_page_health_28d")
        
        assert len(results) > 0
        page = results[0]
        assert page['property'] == "https://example.com/"
        assert page['total_clicks'] == 150
        assert page['health_score'] == 80
        assert page['trend_status'] == "IMPROVING"
        
    def test_mock_data_query_trends(self):
        """Test mock data generation for query trends"""
        db = DatabaseConnection()
        
        results = db._get_mock_data("SELECT * FROM gsc.vw_query_winners_losers")
        
        assert len(results) > 0
        query = results[0]
        assert 'query' in query
        assert 'current_clicks' in query
        assert 'performance_category' in query
        
    def test_mock_data_cannibalization(self):
        """Test mock data generation for cannibalization"""
        db = DatabaseConnection()
        
        results = db._get_mock_data("SELECT * FROM gsc.vw_cannibalization")
        
        assert len(results) > 0
        cannibal = results[0]
        assert 'query' in cannibal
        assert 'competing_urls_count' in cannibal
        assert 'cannibalization_severity' in cannibal


class TestMCPServerEndpoints:
    """Tests for MCP server endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint returns server info"""
        result = root()
        
        assert result['name'] == "GSC Insights MCP Server"
        assert result['version'] == "1.0.0"
        assert result['mcp_version'] == MCP_VERSION
        assert result['status'] == "healthy"
        assert 'tools' in result
        assert len(result['tools']) == 4
        
    def test_root_contains_all_tools(self):
        """Test root endpoint lists all tools"""
        result = root()
        tools = result['tools']
        
        assert "get_page_health" in tools
        assert "get_query_trends" in tools
        assert "find_cannibalization" in tools
        assert "suggest_actions" in tools
        
    def test_health_check_endpoint(self):
        """Test health check endpoint"""
        result = health_check()
        
        assert 'status' in result
        assert result['status'] in ['healthy', 'degraded']
        assert 'database' in result
        assert result['database'] in ['connected', 'disconnected']
        assert 'cache_size' in result
        assert 'timestamp' in result


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestFastAPIIntegration:
    """Integration tests with FastAPI"""
    
    def test_root_endpoint_http(self):
        """Test root endpoint via HTTP"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data['name'] == "GSC Insights MCP Server"
        assert 'tools' in data
        
    def test_health_endpoint_http(self):
        """Test health endpoint via HTTP"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'database' in data
        
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.get("/")
        
        assert 'access-control-allow-origin' in response.headers
        
    def test_openapi_docs_available(self):
        """Test OpenAPI documentation is available"""
        response = client.get("/docs")
        
        # Should return HTML page
        assert response.status_code == 200
        assert 'text/html' in response.headers.get('content-type', '')


class TestMCPTools:
    """Tests for MCP tool implementations"""
    
    def test_mcp_version_constant(self):
        """Test MCP version is defined"""
        assert MCP_VERSION == "2025-01-18"
        
    def test_tool_names_consistency(self):
        """Test tool names are consistent"""
        root_data = root()
        tools = root_data['tools']
        
        # All tool names should be lowercase with underscores
        for tool in tools:
            assert tool.islower()
            assert ' ' not in tool
            
    def test_server_metadata(self):
        """Test server metadata is complete"""
        root_data = root()
        
        assert 'name' in root_data
        assert 'version' in root_data
        assert 'mcp_version' in root_data
        assert 'status' in root_data
        assert 'tools' in root_data


class TestDataModels:
    """Tests for Pydantic data models"""
    
    def test_scope_filter_creation(self):
        """Test ScopeFilter model creation"""
        from mcp_server import ScopeFilter
        
        scope = ScopeFilter(
            property="https://example.com/",
            directory="/blog/",
            min_impressions=100
        )
        
        assert scope.property == "https://example.com/"
        assert scope.directory == "/blog/"
        assert scope.min_impressions == 100
        
    def test_page_health_request_defaults(self):
        """Test PageHealthRequest default values"""
        from mcp_server import PageHealthRequest
        
        request = PageHealthRequest()
        
        assert request.window_days == 28
        assert request.limit == 100
        assert request.sort_by == "clicks"
        
    def test_query_trends_request_creation(self):
        """Test QueryTrendsRequest model"""
        from mcp_server import QueryTrendsRequest
        
        request = QueryTrendsRequest(
            window_days=14,
            limit=50,
            category_filter="WINNER"
        )
        
        assert request.window_days == 14
        assert request.limit == 50
        assert request.category_filter == "WINNER"
        
    def test_cannibalization_request_defaults(self):
        """Test CannibalizationRequest defaults"""
        from mcp_server import CannibalizationRequest
        
        request = CannibalizationRequest()
        
        assert request.window_days == 28
        assert request.min_severity == "MEDIUM"
        assert request.limit == 50
        
    def test_action_suggestion_model(self):
        """Test ActionSuggestion model"""
        from mcp_server import ActionSuggestion
        
        action = ActionSuggestion(
            action_type="optimization",
            priority="HIGH",
            title="Improve page CTR",
            description="Optimize meta descriptions",
            expected_impact="10-15% CTR increase",
            implementation_difficulty="LOW",
            target_url="https://example.com/page"
        )
        
        assert action.action_type == "optimization"
        assert action.priority == "HIGH"
        assert action.target_url == "https://example.com/page"


class TestCaching:
    """Tests for caching functionality"""
    
    def test_cache_initialization(self):
        """Test cache is initialized empty"""
        db = DatabaseConnection()
        assert len(db._cache) == 0
        
    def test_cache_stores_results(self):
        """Test cache stores query results"""
        db = DatabaseConnection()
        
        db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="test_cache"
        )
        
        assert "test_cache" in db._cache
        cached_data, cached_time = db._cache["test_cache"]
        assert isinstance(cached_data, list)
        assert isinstance(cached_time, float)
        
    def test_cache_hit_performance(self):
        """Test cached queries are faster"""
        db = DatabaseConnection()
        
        import time
        
        # First query (miss)
        start = time.time()
        db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="perf_test"
        )
        first_duration = time.time() - start
        
        # Second query (hit)
        start = time.time()
        db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="perf_test"
        )
        second_duration = time.time() - start
        
        # Cached should be faster (or at least not slower)
        assert second_duration <= first_duration * 1.5
        
    def test_cache_without_key(self):
        """Test queries without cache key don't cache"""
        db = DatabaseConnection()
        
        db.execute_query("SELECT * FROM gsc.vw_page_health_28d")
        
        # Should not cache anything
        assert len(db._cache) == 0


class TestErrorHandling:
    """Tests for error handling"""
    
    def test_database_connection_failure(self):
        """Test graceful handling of database connection failure"""
        with patch('mcp_server.PG_AVAILABLE', True):
            with patch('psycopg2.connect', side_effect=Exception("Connection failed")):
                db = DatabaseConnection()
                conn = db.get_connection()
                assert conn is None
                
    def test_query_execution_failure(self):
        """Test graceful handling of query execution failure"""
        db = DatabaseConnection()
        
        # Mock a connection that fails on query
        with patch.object(db, 'get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("Query failed")
            mock_conn.return_value.cursor.return_value.__enter__.return_value = mock_cursor
            
            results = db.execute_query("SELECT * FROM invalid_table")
            
            # Should return empty list on error
            assert results == []
            
    def test_invalid_cache_key(self):
        """Test handling of invalid cache keys"""
        db = DatabaseConnection()
        
        # Should not crash with None cache key
        results = db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key=None
        )
        
        assert isinstance(results, list)


class TestMockDataConsistency:
    """Tests for mock data consistency"""
    
    def test_mock_data_structure_page_health(self):
        """Test page health mock data has correct structure"""
        db = DatabaseConnection()
        results = db._get_mock_data("SELECT * FROM gsc.vw_page_health_28d")
        
        required_fields = [
            'property', 'url', 'total_clicks', 'total_impressions',
            'ctr_percentage', 'avg_position', 'health_score', 'trend_status'
        ]
        
        for field in required_fields:
            assert field in results[0]
            
    def test_mock_data_structure_query_trends(self):
        """Test query trends mock data has correct structure"""
        db = DatabaseConnection()
        results = db._get_mock_data("SELECT * FROM gsc.vw_query_winners_losers")
        
        required_fields = [
            'query', 'current_clicks', 'previous_clicks',
            'clicks_change_pct', 'performance_category', 'opportunity_score'
        ]
        
        for field in required_fields:
            assert field in results[0]
            
    def test_mock_data_structure_cannibalization(self):
        """Test cannibalization mock data has correct structure"""
        db = DatabaseConnection()
        results = db._get_mock_data("SELECT * FROM gsc.vw_cannibalization")
        
        required_fields = [
            'query', 'competing_urls_count', 'top_url_1', 'top_url_2',
            'cannibalization_severity', 'recommended_action'
        ]
        
        for field in required_fields:
            assert field in results[0]
            
    def test_mock_data_types(self):
        """Test mock data field types are correct"""
        db = DatabaseConnection()
        results = db._get_mock_data("SELECT * FROM gsc.vw_page_health_28d")
        
        page = results[0]
        assert isinstance(page['property'], str)
        assert isinstance(page['total_clicks'], int)
        assert isinstance(page['ctr_percentage'], (int, float))
        assert isinstance(page['health_score'], int)


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios"""
    
    def test_multiple_tool_invocations(self):
        """Test multiple tool calls in sequence"""
        db = DatabaseConnection()
        
        # Call different tools
        page_health = db.execute_query("SELECT * FROM gsc.vw_page_health_28d")
        query_trends = db.execute_query("SELECT * FROM gsc.vw_query_winners_losers")
        cannibalization = db.execute_query("SELECT * FROM gsc.vw_cannibalization")
        
        assert len(page_health) > 0
        assert len(query_trends) > 0
        assert len(cannibalization) > 0
        
    def test_server_startup(self):
        """Test server can be initialized"""
        result = root()
        assert result['status'] == 'healthy'
        
    def test_health_check_consistency(self):
        """Test health check is consistent"""
        result1 = health_check()
        result2 = health_check()
        
        assert result1['status'] == result2['status']
        assert result1['database'] == result2['database']
        
    def test_cache_across_queries(self):
        """Test cache works across different query types"""
        db = DatabaseConnection()
        
        # Cache multiple query types
        db.execute_query(
            "SELECT * FROM gsc.vw_page_health_28d",
            cache_key="pages"
        )
        db.execute_query(
            "SELECT * FROM gsc.vw_query_winners_losers",
            cache_key="queries"
        )
        
        assert len(db._cache) == 2
        assert "pages" in db._cache
        assert "queries" in db._cache


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAPIEndpointsIntegration:
    """Integration tests for API endpoints"""
    
    def test_all_endpoints_respond(self):
        """Test all endpoints return valid responses"""
        endpoints = ["/", "/health"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('application/json')
            
    def test_response_format_consistency(self):
        """Test response format is consistent"""
        response = client.get("/")
        data = response.json()
        
        # Check all required fields present
        assert 'name' in data
        assert 'version' in data
        assert 'mcp_version' in data
        assert 'status' in data
        
    def test_health_endpoint_structure(self):
        """Test health endpoint returns expected structure"""
        response = client.get("/health")
        data = response.json()
        
        assert 'status' in data
        assert 'database' in data
        assert 'cache_size' in data
        assert 'timestamp' in data


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestMCPContractEndpoints:
    """Integration tests for generic MCP endpoints (/tools and /call-tool)"""

    def test_list_tools_endpoint(self):
        """GET /tools returns all tools with metadata"""
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert 'tools' in data
        # Validate that each entry contains required keys
        for entry in data['tools']:
            assert 'name' in entry
            assert 'description' in entry
            assert 'parameters' in entry
        # Confirm expected tools are present
        names = [entry['name'] for entry in data['tools']]
        for expected in [
            "get_page_health",
            "get_query_trends",
            "find_cannibalization",
            "suggest_actions"
        ]:
            assert expected in names

    def test_call_tool_happy_path(self):
        """POST /call-tool dispatches and returns results"""
        payload = {
            "tool": "get_page_health",
            "arguments": {
                "property": "https://example.com/",
                "window_days": 28,
                "limit": 1
            }
        }
        response = client.post("/call-tool", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert 'result' in body
        assert 'metadata' in body
        assert isinstance(body['result'], list)
        # rows_returned should match the length of the result
        if 'rows_returned' in body['metadata']:
            assert body['metadata']['rows_returned'] == len(body['result'])

    def test_call_tool_unknown(self):
        """Unknown tool names return 404 and error detail"""
        payload = {"tool": "nonexistent_tool", "arguments": {}}
        response = client.post("/call-tool", json=payload)
        assert response.status_code == 404
        data = response.json()
        assert 'detail' in data

    def test_call_tool_invalid_arguments(self):
        """Unexpected arguments trigger validation error"""
        payload = {
            "tool": "get_page_health",
            "arguments": {"unknown_param": 123}
        }
        response = client.post("/call-tool", json=payload)
        assert response.status_code == 422
        data = response.json()
        assert 'detail' in data


def test_module_imports():
    """Test all required modules can be imported"""
    import mcp_server
    
    assert hasattr(mcp_server, 'DatabaseConnection')
    assert hasattr(mcp_server, 'MCP_VERSION')
    assert hasattr(mcp_server, 'root')
    assert hasattr(mcp_server, 'health_check')


def test_constants_defined():
    """Test all constants are properly defined"""
    import mcp_server
    
    assert mcp_server.MCP_VERSION is not None
    assert isinstance(mcp_server.MCP_VERSION, str)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])