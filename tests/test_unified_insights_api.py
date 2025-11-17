#!/usr/bin/env python3
"""
Tests for the Unified Insights API
Tests the RESTful API endpoints for querying and managing insights
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add insights_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from insights_core.models import (
    Insight,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics
)

# Try to import FastAPI test client
try:
    from fastapi.testclient import TestClient
    import insights_api.insights_api as api_module
    
    # Create test client
    client = TestClient(api_module.app)
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    client = None


# ============================================================================
# TEST FIXTURES
# ============================================================================

def create_mock_insight(
    id="test_id_123",
    category=InsightCategory.RISK,
    severity=InsightSeverity.HIGH,
    status=InsightStatus.NEW
) -> Insight:
    """Create a mock insight for testing"""
    return Insight(
        id=id,
        generated_at=datetime.utcnow(),
        property="https://example.com",
        entity_type=EntityType.PAGE,
        entity_id="/test-page",
        category=category,
        title="Test Insight",
        description="Test description",
        severity=severity,
        confidence=0.9,
        metrics=InsightMetrics(
            gsc_clicks=100.0,
            gsc_clicks_change=-25.0
        ),
        window_days=7,
        source="TestDetector",
        status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def mock_repository():
    """Mock InsightRepository for tests"""
    with patch('insights_api.insights_api.repository') as mock_repo:
        yield mock_repo


# ============================================================================
# HEALTH & STATUS TESTS
# ============================================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestHealthEndpoints:
    """Tests for health and status endpoints"""
    
    def test_health_check(self, mock_repository):
        """Test health check endpoint"""
        mock_repository.get_stats.return_value = {
            'total_insights': 100,
            'unique_properties': 5
        }
        
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
        assert data['total_insights'] == 100
    
    def test_get_stats(self, mock_repository):
        """Test stats endpoint"""
        mock_stats = {
            'total_insights': 150,
            'unique_properties': 10,
            'risk_count': 50,
            'opportunity_count': 100
        }
        mock_repository.get_stats.return_value = mock_stats
        
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data'] == mock_stats


# ============================================================================
# QUERY ENDPOINT TESTS
# ============================================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestQueryEndpoints:
    """Tests for insight query endpoints"""
    
    def test_query_insights_no_filters(self, mock_repository):
        """Test querying insights without filters"""
        mock_insights = [
            create_mock_insight(id="insight_1"),
            create_mock_insight(id="insight_2")
        ]
        mock_repository.query.return_value = mock_insights
        
        response = client.get("/api/insights")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['count'] == 2
        assert len(data['data']) == 2
    
    def test_query_insights_with_filters(self, mock_repository):
        """Test querying insights with filters"""
        mock_insights = [create_mock_insight()]
        mock_repository.query.return_value = mock_insights
        
        response = client.get(
            "/api/insights",
            params={
                'property': 'https://example.com',
                'category': 'risk',
                'status': 'new',
                'limit': 50
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['count'] == 1
        
        # Verify repository was called with correct params
        mock_repository.query.assert_called_once()
        call_kwargs = mock_repository.query.call_args[1]
        assert call_kwargs['property'] == 'https://example.com'
        assert call_kwargs['category'] == InsightCategory.RISK
        assert call_kwargs['limit'] == 50
    
    def test_get_insight_by_id_found(self, mock_repository):
        """Test getting insight by ID when it exists"""
        mock_insight = create_mock_insight()
        mock_repository.get_by_id.return_value = mock_insight
        
        response = client.get("/api/insights/test_id_123")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['id'] == 'test_id_123'
    
    def test_get_insight_by_id_not_found(self, mock_repository):
        """Test getting insight by ID when it doesn't exist"""
        mock_repository.get_by_id.return_value = None
        
        response = client.get("/api/insights/nonexistent_id")
        assert response.status_code == 404
    
    def test_get_by_category(self, mock_repository):
        """Test getting insights by category"""
        mock_insights = [
            create_mock_insight(category=InsightCategory.RISK),
            create_mock_insight(category=InsightCategory.RISK, id="insight_2")
        ]
        mock_repository.get_by_category.return_value = mock_insights
        
        response = client.get("/api/insights/category/risk")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['category'] == 'risk'
        assert data['count'] == 2
    
    def test_get_by_status(self, mock_repository):
        """Test getting insights by status"""
        mock_insights = [create_mock_insight(status=InsightStatus.NEW)]
        mock_repository.get_by_status.return_value = mock_insights
        
        response = client.get("/api/insights/status/new")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['insight_status'] == 'new'
        assert data['count'] == 1
    
    def test_get_for_entity(self, mock_repository):
        """Test getting insights for a specific entity"""
        mock_insights = [create_mock_insight()]
        mock_repository.get_for_entity.return_value = mock_insights
        
        response = client.get(
            "/api/insights/entity/page/test-page",
            params={'property': 'https://example.com'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['entity_type'] == 'page'
        assert data['entity_id'] == 'test-page'


# ============================================================================
# MUTATION ENDPOINT TESTS
# ============================================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestMutationEndpoints:
    """Tests for insight mutation endpoints"""
    
    def test_update_insight(self, mock_repository):
        """Test updating an insight"""
        updated_insight = create_mock_insight(status=InsightStatus.INVESTIGATING)
        mock_repository.update.return_value = updated_insight
        
        response = client.patch(
            "/api/insights/test_id_123",
            json={'status': 'investigating'}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['status'] == 'investigating'
    
    def test_update_insight_not_found(self, mock_repository):
        """Test updating non-existent insight"""
        mock_repository.update.return_value = None
        
        response = client.patch(
            "/api/insights/nonexistent_id",
            json={'status': 'investigating'}
        )
        assert response.status_code == 404


# ============================================================================
# AGGREGATION ENDPOINT TESTS
# ============================================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAggregationEndpoints:
    """Tests for aggregation and analytics endpoints"""
    
    def test_get_recent_insights(self, mock_repository):
        """Test getting recent insights"""
        mock_insights = [
            create_mock_insight(id="recent_1"),
            create_mock_insight(id="recent_2")
        ]
        mock_repository.query_recent.return_value = mock_insights
        
        response = client.get("/api/insights/recent/24")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['hours'] == 24
        assert data['count'] == 2
        
        # Verify repository was called correctly
        mock_repository.query_recent.assert_called_once_with(
            hours=24,
            property=None
        )
    
    def test_get_actionable_insights(self, mock_repository):
        """Test getting actionable insights"""
        new_insights = [create_mock_insight(status=InsightStatus.NEW)]
        diagnosed_insights = [create_mock_insight(
            id="diagnosed_1",
            status=InsightStatus.DIAGNOSED
        )]
        
        mock_repository.get_by_status.side_effect = [
            new_insights,
            diagnosed_insights
        ]
        
        response = client.get("/api/insights/actionable")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['count'] == 2
    
    def test_get_property_summary(self, mock_repository):
        """Test getting property summary"""
        # Create mix of insights
        mock_insights = [
            create_mock_insight(
                id="risk_1",
                category=InsightCategory.RISK,
                severity=InsightSeverity.HIGH,
                status=InsightStatus.NEW
            ),
            create_mock_insight(
                id="opp_1",
                category=InsightCategory.OPPORTUNITY,
                severity=InsightSeverity.MEDIUM,
                status=InsightStatus.ACTIONED
            ),
            create_mock_insight(
                id="risk_2",
                category=InsightCategory.RISK,
                severity=InsightSeverity.LOW,
                status=InsightStatus.RESOLVED
            )
        ]
        mock_repository.query.return_value = mock_insights
        
        response = client.get("/api/insights/summary/https://example.com")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['property'] == 'https://example.com'
        
        summary = data['summary']
        assert summary['total_insights'] == 3
        assert summary['by_category']['risk'] == 2
        assert summary['by_category']['opportunity'] == 1
        assert summary['by_status']['new'] == 1
        assert summary['by_severity']['high'] == 1
        assert summary['actionable_count'] == 1  # Only NEW insights


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestErrorHandling:
    """Tests for error handling"""
    
    def test_query_with_invalid_category(self):
        """Test querying with invalid category"""
        response = client.get(
            "/api/insights",
            params={'category': 'invalid_category'}
        )
        assert response.status_code == 422  # Validation error
    
    def test_query_with_invalid_limit(self):
        """Test querying with invalid limit"""
        response = client.get(
            "/api/insights",
            params={'limit': 2000}  # Exceeds max of 1000
        )
        assert response.status_code == 422
    
    def test_repository_error_handling(self, mock_repository):
        """Test handling of repository errors"""
        mock_repository.query.side_effect = Exception("Database connection failed")
        
        response = client.get("/api/insights")
        assert response.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
