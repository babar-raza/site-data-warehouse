"""
Tests for Insight models
"""
import pytest
from datetime import datetime
from insights_core.models import (
    Insight,
    InsightCreate,
    InsightUpdate,
    InsightMetrics,
    EntityType,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
)


class TestInsightMetrics:
    """Test InsightMetrics model"""
    
    def test_metrics_creation(self):
        """Test basic metrics creation"""
        metrics = InsightMetrics(
            gsc_clicks=100.0,
            gsc_clicks_change=-15.5,
            gsc_impressions=5000.0
        )
        assert metrics.gsc_clicks == 100.0
        assert metrics.gsc_clicks_change == -15.5
        assert metrics.gsc_impressions == 5000.0
    
    def test_metrics_extra_fields(self):
        """Test that extra fields are allowed"""
        metrics = InsightMetrics(
            gsc_clicks=100.0,
            custom_field="custom_value",
            another_metric=999
        )
        assert metrics.gsc_clicks == 100.0
        assert metrics.model_extra.get('custom_field') == "custom_value"
        assert metrics.model_extra.get('another_metric') == 999
    
    def test_metrics_optional_fields(self):
        """Test that all fields are optional"""
        metrics = InsightMetrics()
        assert metrics.gsc_clicks is None
        assert metrics.ga_conversions is None


class TestInsight:
    """Test Insight model"""
    
    def test_insight_creation(self):
        """Test basic insight creation"""
        metrics = InsightMetrics(gsc_clicks=100.0, gsc_clicks_change=-20.0)
        insight_id = Insight.generate_id(
            property="https://example.com/",
            entity_type="page",
            entity_id="/test-page",
            category="risk",
            source="click_drop_detector",
            window_days=7
        )
        
        insight = Insight(
            id=insight_id,
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test-page",
            category=InsightCategory.RISK,
            title="Clicks dropped 20%",
            description="Page experienced significant click drop",
            severity=InsightSeverity.HIGH,
            confidence=0.85,
            metrics=metrics,
            window_days=7,
            source="click_drop_detector"
        )
        
        assert insight.id == insight_id
        assert insight.entity_type == EntityType.PAGE
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert insight.confidence == 0.85
        assert insight.status == InsightStatus.NEW
    
    def test_id_validation(self):
        """Test ID format validation"""
        metrics = InsightMetrics()
        
        # Valid SHA256 (64 chars)
        valid_id = "a" * 64
        insight = Insight(
            id=valid_id,
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.RISK,
            title="Test",
            description="Test description",
            severity=InsightSeverity.LOW,
            confidence=0.5,
            metrics=metrics,
            window_days=7,
            source="test"
        )
        assert insight.id == valid_id
        
        # Valid MD5 (32 chars)
        valid_id_md5 = "b" * 32
        insight2 = Insight(
            id=valid_id_md5,
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.RISK,
            title="Test",
            description="Test description",
            severity=InsightSeverity.LOW,
            confidence=0.5,
            metrics=metrics,
            window_days=7,
            source="test"
        )
        assert insight2.id == valid_id_md5
        
        # Invalid length
        with pytest.raises(ValueError):
            Insight(
                id="invalid",
                property="https://example.com/",
                entity_type=EntityType.PAGE,
                entity_id="/test",
                category=InsightCategory.RISK,
                title="Test",
                description="Test description",
                severity=InsightSeverity.LOW,
                confidence=0.5,
                metrics=metrics,
                window_days=7,
                source="test"
            )
    
    def test_confidence_validation(self):
        """Test confidence must be 0-1"""
        metrics = InsightMetrics()
        insight_id = "a" * 64
        
        # Valid confidence
        insight = Insight(
            id=insight_id,
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.RISK,
            title="Test",
            description="Test description",
            severity=InsightSeverity.LOW,
            confidence=0.75,
            metrics=metrics,
            window_days=7,
            source="test"
        )
        assert insight.confidence == 0.75
        
        # Invalid confidence > 1
        with pytest.raises(ValueError):
            Insight(
                id=insight_id,
                property="https://example.com/",
                entity_type=EntityType.PAGE,
                entity_id="/test",
                category=InsightCategory.RISK,
                title="Test",
                description="Test description",
                severity=InsightSeverity.LOW,
                confidence=1.5,
                metrics=metrics,
                window_days=7,
                source="test"
            )
    
    def test_generate_id_deterministic(self):
        """Test ID generation is deterministic"""
        id1 = Insight.generate_id(
            property="https://example.com/",
            entity_type="page",
            entity_id="/test-page",
            category="risk",
            source="detector",
            window_days=7
        )
        
        id2 = Insight.generate_id(
            property="https://example.com/",
            entity_type="page",
            entity_id="/test-page",
            category="risk",
            source="detector",
            window_days=7
        )
        
        assert id1 == id2
        assert len(id1) == 64  # SHA256
    
    def test_to_db_dict(self):
        """Test conversion to database dict"""
        metrics = InsightMetrics(gsc_clicks=100.0)
        insight_id = Insight.generate_id(
            property="https://example.com/",
            entity_type="page",
            entity_id="/test",
            category="risk",
            source="test",
            window_days=7
        )
        
        insight = Insight(
            id=insight_id,
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.RISK,
            title="Test",
            description="Test description",
            severity=InsightSeverity.HIGH,
            confidence=0.8,
            metrics=metrics,
            window_days=7,
            source="test"
        )
        
        db_dict = insight.to_db_dict()
        
        # Enums should be converted to strings
        assert db_dict['entity_type'] == "page"
        assert db_dict['category'] == "risk"
        assert db_dict['severity'] == "high"
        assert db_dict['status'] == "new"
        
        # Metrics should be a dict
        assert isinstance(db_dict['metrics'], dict)
        assert db_dict['metrics']['gsc_clicks'] == 100.0
    
    def test_from_db_dict(self):
        """Test creation from database dict"""
        db_dict = {
            'id': 'a' * 64,
            'generated_at': datetime.utcnow(),
            'property': 'https://example.com/',
            'entity_type': 'page',
            'entity_id': '/test',
            'category': 'risk',
            'title': 'Test',
            'description': 'Test description',
            'severity': 'high',
            'confidence': 0.8,
            'metrics': {'gsc_clicks': 100.0},
            'window_days': 7,
            'source': 'test',
            'status': 'new',
            'linked_insight_id': None,
            'created_at': None,
            'updated_at': None
        }
        
        insight = Insight.from_db_dict(db_dict)
        
        assert insight.id == 'a' * 64
        assert insight.entity_type == EntityType.PAGE
        assert insight.category == InsightCategory.RISK
        assert insight.severity == InsightSeverity.HIGH
        assert insight.metrics.gsc_clicks == 100.0


class TestInsightCreate:
    """Test InsightCreate model"""
    
    def test_insight_create(self):
        """Test creating InsightCreate"""
        metrics = InsightMetrics(gsc_clicks=100.0)
        
        create = InsightCreate(
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.OPPORTUNITY,
            title="Test opportunity",
            description="Test description",
            severity=InsightSeverity.MEDIUM,
            confidence=0.7,
            metrics=metrics,
            window_days=7,
            source="test_detector"
        )
        
        assert create.property == "https://example.com/"
        assert create.entity_type == EntityType.PAGE
        assert create.status == InsightStatus.NEW
    
    def test_to_insight(self):
        """Test conversion to full Insight"""
        metrics = InsightMetrics(gsc_clicks=100.0)
        
        create = InsightCreate(
            property="https://example.com/",
            entity_type=EntityType.PAGE,
            entity_id="/test",
            category=InsightCategory.RISK,
            title="Test",
            description="Test description",
            severity=InsightSeverity.LOW,
            confidence=0.5,
            metrics=metrics,
            window_days=7,
            source="detector"
        )
        
        insight = create.to_insight()
        
        # Should have generated ID
        assert len(insight.id) == 64
        assert insight.property == create.property
        assert insight.entity_type == create.entity_type
        assert insight.title == create.title
        
        # Same inputs should generate same ID
        insight2 = create.to_insight()
        assert insight.id == insight2.id


class TestInsightUpdate:
    """Test InsightUpdate model"""
    
    def test_update_status(self):
        """Test updating status"""
        update = InsightUpdate(status=InsightStatus.INVESTIGATING)
        assert update.status == InsightStatus.INVESTIGATING
    
    def test_update_description(self):
        """Test updating description"""
        update = InsightUpdate(description="Updated description")
        assert update.description == "Updated description"
    
    def test_update_linked_insight(self):
        """Test updating linked insight"""
        update = InsightUpdate(linked_insight_id="abc123")
        assert update.linked_insight_id == "abc123"
    
    def test_update_forbids_extra_fields(self):
        """Test that extra fields are forbidden"""
        with pytest.raises(ValueError):
            InsightUpdate(status=InsightStatus.RESOLVED, invalid_field="value")
    
    def test_update_empty(self):
        """Test empty update is valid"""
        update = InsightUpdate()
        assert update.status is None
        assert update.linked_insight_id is None
        assert update.description is None


class TestEnums:
    """Test enum definitions"""
    
    def test_entity_type_values(self):
        """Test EntityType enum values"""
        assert EntityType.PAGE.value == "page"
        assert EntityType.QUERY.value == "query"
        assert EntityType.DIRECTORY.value == "directory"
        assert EntityType.PROPERTY.value == "property"
    
    def test_insight_category_values(self):
        """Test InsightCategory enum values"""
        assert InsightCategory.RISK.value == "risk"
        assert InsightCategory.OPPORTUNITY.value == "opportunity"
        assert InsightCategory.TREND.value == "trend"
        assert InsightCategory.DIAGNOSIS.value == "diagnosis"
    
    def test_insight_severity_values(self):
        """Test InsightSeverity enum values"""
        assert InsightSeverity.LOW.value == "low"
        assert InsightSeverity.MEDIUM.value == "medium"
        assert InsightSeverity.HIGH.value == "high"
    
    def test_insight_status_values(self):
        """Test InsightStatus enum values"""
        assert InsightStatus.NEW.value == "new"
        assert InsightStatus.INVESTIGATING.value == "investigating"
        assert InsightStatus.DIAGNOSED.value == "diagnosed"
        assert InsightStatus.ACTIONED.value == "actioned"
        assert InsightStatus.RESOLVED.value == "resolved"
