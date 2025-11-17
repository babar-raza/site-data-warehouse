#!/usr/bin/env python3
"""
Insights API Server
RESTful API for querying and managing insights from the Unified Insight Engine
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insights_core.models import (
    Insight,
    InsightCreate,
    InsightUpdate,
    InsightQuery,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType
)
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GSC Insights API",
    description="RESTful API for querying insights from the Unified Insight Engine",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize config and repository
config = InsightsConfig()
repository: Optional[InsightRepository] = None


@app.on_event("startup")
async def startup_event():
    """Initialize repository on startup"""
    global repository
    try:
        repository = InsightRepository(config.warehouse_dsn)
        logger.info("Insights API started successfully")
        logger.info(f"Connected to: {config.warehouse_dsn.split('@')[1] if '@' in config.warehouse_dsn else 'database'}")
    except Exception as e:
        logger.error(f"Failed to initialize repository: {e}")
        raise


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        if repository:
            stats = repository.get_stats()
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": "connected",
                "total_insights": stats.get('total_insights', 0)
            }
        return {"status": "initializing"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/api/stats")
async def get_stats():
    """Get repository statistics"""
    try:
        stats = repository.get_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INSIGHT QUERY ENDPOINTS
# ============================================================================

@app.get("/api/insights")
async def query_insights(
    property: Optional[str] = Query(None, description="Filter by property"),
    category: Optional[InsightCategory] = Query(None, description="Filter by category"),
    status: Optional[InsightStatus] = Query(None, description="Filter by status"),
    severity: Optional[InsightSeverity] = Query(None, description="Filter by severity"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Query insights with filters"""
    try:
        insights = repository.query(
            property=property,
            category=category,
            status=status,
            severity=severity,
            entity_type=entity_type,
            limit=limit,
            offset=offset
        )
        
        return {
            "status": "success",
            "count": len(insights),
            "limit": limit,
            "offset": offset,
            "data": [insight.model_dump() for insight in insights]
        }
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/{insight_id}")
async def get_insight(
    insight_id: str = Path(..., description="Insight ID")
):
    """Get a specific insight by ID"""
    try:
        insight = repository.get_by_id(insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")
        
        return {
            "status": "success",
            "data": insight.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get insight {insight_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/category/{category}")
async def get_by_category(
    category: InsightCategory = Path(..., description="Insight category"),
    property: Optional[str] = Query(None, description="Filter by property"),
    severity: Optional[InsightSeverity] = Query(None, description="Filter by severity"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """Get insights by category"""
    try:
        insights = repository.get_by_category(
            category=category,
            property=property,
            severity=severity,
            limit=limit
        )
        
        return {
            "status": "success",
            "category": category.value,
            "count": len(insights),
            "data": [insight.model_dump() for insight in insights]
        }
    except Exception as e:
        logger.error(f"Failed to get insights by category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/status/{status}")
async def get_by_status(
    status: InsightStatus = Path(..., description="Insight status"),
    property: Optional[str] = Query(None, description="Filter by property"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """Get insights by status"""
    try:
        insights = repository.get_by_status(
            status=status,
            property=property,
            limit=limit
        )
        
        return {
            "status": "success",
            "insight_status": status.value,
            "count": len(insights),
            "data": [insight.model_dump() for insight in insights]
        }
    except Exception as e:
        logger.error(f"Failed to get insights by status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/entity/{entity_type}/{entity_id}")
async def get_for_entity(
    entity_type: str = Path(..., description="Entity type (page/query/directory/property)"),
    entity_id: str = Path(..., description="Entity identifier"),
    property: str = Query(..., description="Property URL"),
    days_back: int = Query(90, ge=1, le=365, description="Days to look back")
):
    """Get all insights for a specific entity"""
    try:
        insights = repository.get_for_entity(
            entity_type=entity_type,
            entity_id=entity_id,
            property=property,
            days_back=days_back
        )
        
        return {
            "status": "success",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "property": property,
            "count": len(insights),
            "data": [insight.model_dump() for insight in insights]
        }
    except Exception as e:
        logger.error(f"Failed to get insights for entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# INSIGHT MUTATION ENDPOINTS
# ============================================================================

@app.patch("/api/insights/{insight_id}")
async def update_insight(
    insight_id: str = Path(..., description="Insight ID"),
    update: InsightUpdate = ...
):
    """Update an existing insight"""
    try:
        updated_insight = repository.update(insight_id, update)
        if not updated_insight:
            raise HTTPException(status_code=404, detail=f"Insight {insight_id} not found")
        
        return {
            "status": "success",
            "message": "Insight updated",
            "data": updated_insight.model_dump()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update insight {insight_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AGGREGATION & ANALYTICS ENDPOINTS
# ============================================================================

@app.get("/api/insights/recent/{hours}")
async def get_recent_insights(
    hours: int = Path(..., ge=1, le=168, description="Hours to look back"),
    property: Optional[str] = Query(None, description="Filter by property")
):
    """Get insights generated in the last N hours"""
    try:
        insights = repository.query_recent(hours=hours, property=property)
        
        return {
            "status": "success",
            "hours": hours,
            "count": len(insights),
            "data": [insight.model_dump() for insight in insights]
        }
    except Exception as e:
        logger.error(f"Failed to get recent insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/actionable")
async def get_actionable_insights(
    property: Optional[str] = Query(None, description="Filter by property"),
    severity: Optional[InsightSeverity] = Query(None, description="Minimum severity"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """Get insights that require action (status=new or diagnosed)"""
    try:
        # Get insights with new or diagnosed status
        new_insights = repository.get_by_status(
            status=InsightStatus.NEW,
            property=property,
            limit=limit
        )
        
        diagnosed_insights = repository.get_by_status(
            status=InsightStatus.DIAGNOSED,
            property=property,
            limit=limit
        )
        
        all_actionable = new_insights + diagnosed_insights
        
        # Filter by severity if specified
        if severity:
            all_actionable = [i for i in all_actionable if i.severity == severity]
        
        # Sort by severity (high first) then by generated_at (newest first)
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        all_actionable.sort(
            key=lambda x: (severity_order.get(x.severity.value, 3), -x.generated_at.timestamp())
        )
        
        return {
            "status": "success",
            "count": len(all_actionable),
            "data": [insight.model_dump() for insight in all_actionable[:limit]]
        }
    except Exception as e:
        logger.error(f"Failed to get actionable insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/insights/summary/{property}")
async def get_property_summary(
    property: str = Path(..., description="Property URL")
):
    """Get summary statistics for a property"""
    try:
        insights = repository.query(property=property, limit=10000)
        
        # Calculate summary stats
        total = len(insights)
        by_category = {}
        by_status = {}
        by_severity = {}
        
        for insight in insights:
            # By category
            cat = insight.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            # By status
            stat = insight.status.value
            by_status[stat] = by_status.get(stat, 0) + 1
            
            # By severity
            sev = insight.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Recent insights (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent = [i for i in insights if i.generated_at >= seven_days_ago]
        
        return {
            "status": "success",
            "property": property,
            "summary": {
                "total_insights": total,
                "recent_insights_7d": len(recent),
                "by_category": by_category,
                "by_status": by_status,
                "by_severity": by_severity,
                "actionable_count": by_status.get('new', 0) + by_status.get('diagnosed', 0)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get property summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run the API server"""
    port = int(os.environ.get('API_PORT', 8001))
    host = os.environ.get('API_HOST', '0.0.0.0')
    
    logger.info(f"Starting Insights API server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
