"""
Pydantic models for Unified Insight Engine
Defines data structures for insights, detections, and related entities
"""
import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class EntityType(str, Enum):
    """Type of entity that an insight relates to"""
    PAGE = "page"
    QUERY = "query"
    DIRECTORY = "directory"
    PROPERTY = "property"


class InsightCategory(str, Enum):
    """Category of insight"""
    RISK = "risk"              # Problem detected
    OPPORTUNITY = "opportunity"  # Growth potential
    TREND = "trend"            # Pattern analysis
    DIAGNOSIS = "diagnosis"    # Root cause


class InsightSeverity(str, Enum):
    """Severity level of insight"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InsightStatus(str, Enum):
    """Workflow status of insight"""
    NEW = "new"                    # Just created
    INVESTIGATING = "investigating"  # Being analyzed
    DIAGNOSED = "diagnosed"        # Root cause found
    ACTIONED = "actioned"          # Fix deployed
    RESOLVED = "resolved"          # Verified fixed


class InsightMetrics(BaseModel):
    """Flexible metrics container for insight data"""
    gsc_clicks: Optional[float] = None
    gsc_clicks_change: Optional[float] = None
    gsc_impressions: Optional[float] = None
    gsc_impressions_change: Optional[float] = None
    gsc_ctr: Optional[float] = None
    gsc_ctr_change: Optional[float] = None
    gsc_position: Optional[float] = None
    gsc_position_change: Optional[float] = None
    
    # Time windows for comparison
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    comparison_start: Optional[str] = None
    comparison_end: Optional[str] = None
    
    # Additional flexible fields
    class Config:
        extra = "allow"  # Allow additional fields for detector-specific metrics


class InsightBase(BaseModel):
    """Base fields for insights"""
    property: str = Field(..., max_length=500)
    entity_type: EntityType
    entity_id: str
    category: InsightCategory
    title: str = Field(..., max_length=200)
    description: str
    severity: InsightSeverity
    confidence: float = Field(..., ge=0.0, le=1.0)
    metrics: InsightMetrics
    window_days: int = Field(..., gt=0, le=365)
    source: str = Field(..., max_length=100)


class InsightCreate(InsightBase):
    """Data for creating a new insight"""
    linked_insight_id: Optional[str] = Field(None, max_length=64)
    
    def to_insight(self) -> 'Insight':
        """Convert InsightCreate to full Insight model"""
        insight_id = Insight.generate_id(
            property=self.property,
            entity_type=self.entity_type.value,
            entity_id=self.entity_id,
            category=self.category.value,
            source=self.source,
            window_days=self.window_days
        )
        
        return Insight(
            id=insight_id,
            generated_at=datetime.utcnow(),
            **self.model_dump()
        )


class InsightUpdate(BaseModel):
    """Data for updating an existing insight"""
    status: Optional[InsightStatus] = None
    description: Optional[str] = None
    linked_insight_id: Optional[str] = None
    
    class Config:
        extra = "forbid"  # Don't allow updating other fields


class Insight(InsightBase):
    """Complete insight model with system fields"""
    id: str = Field(..., max_length=64)
    generated_at: datetime
    status: InsightStatus = InsightStatus.NEW
    linked_insight_id: Optional[str] = Field(None, max_length=64)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @staticmethod
    def generate_id(
        property: str,
        entity_type: str,
        entity_id: str,
        category: str,
        source: str,
        window_days: int
    ) -> str:
        """
        Generate deterministic ID from insight components
        Prevents duplicate insights with same characteristics
        """
        components = f"{property}|{entity_type}|{entity_id}|{category}|{source}|{window_days}"
        return hashlib.sha256(components.encode('utf-8')).hexdigest()
    
    def to_db_dict(self) -> dict:
        """Convert to dict for database storage"""
        data = self.model_dump()
        # Convert enums to strings
        for key in ['entity_type', 'category', 'severity', 'status']:
            if data.get(key) and hasattr(data[key], 'value'):
                data[key] = data[key].value
        return data
    
    class Config:
        from_attributes = True


class InsightQuery(BaseModel):
    """Query parameters for searching insights"""
    property: Optional[str] = None
    category: Optional[InsightCategory] = None
    status: Optional[InsightStatus] = None
    severity: Optional[InsightSeverity] = None
    entity_type: Optional[EntityType] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
