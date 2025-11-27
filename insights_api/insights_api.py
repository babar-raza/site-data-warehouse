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
from fastapi.responses import JSONResponse, HTMLResponse
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

# Include modular routers
from insights_api.routes import aggregations_router, actions_router
app.include_router(aggregations_router)
app.include_router(actions_router)

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
# INDEX & NAVIGATION
# ============================================================================

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Site Data Warehouse</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { color: #888; font-size: 1.1rem; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.3s ease;
            text-decoration: none;
            color: inherit;
            display: block;
        }
        .card:hover {
            transform: translateY(-4px);
            background: rgba(255,255,255,0.1);
            border-color: #00d9ff;
            box-shadow: 0 8px 32px rgba(0, 217, 255, 0.2);
        }
        .card h3 {
            font-size: 1.25rem;
            margin-bottom: 0.5rem;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .card p { color: #888; font-size: 0.9rem; line-height: 1.5; }
        .card .port {
            display: inline-block;
            background: rgba(0, 217, 255, 0.2);
            color: #00d9ff;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-family: monospace;
            margin-left: auto;
        }
        .section-title {
            font-size: 1rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 1rem;
            padding-left: 0.5rem;
            border-left: 3px solid #00d9ff;
        }
        .status {
            margin-top: 2rem;
            padding: 1rem;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid rgba(0, 255, 136, 0.3);
            border-radius: 8px;
            text-align: center;
        }
        .status.loading { background: rgba(255, 200, 0, 0.1); border-color: rgba(255, 200, 0, 0.3); }
        .status.error { background: rgba(255, 100, 100, 0.1); border-color: rgba(255, 100, 100, 0.3); }
        footer {
            text-align: center;
            margin-top: 3rem;
            color: #555;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Site Data Warehouse</h1>
            <p class="subtitle">GSC & GA4 Analytics Platform</p>
        </header>

        <h2 class="section-title">API & Documentation</h2>
        <div class="grid">
            <a href="/api/docs" class="card">
                <h3>📖 API Documentation <span class="port">:8000</span></h3>
                <p>Interactive Swagger UI for exploring and testing the Insights API endpoints.</p>
            </a>
            <a href="/api/redoc" class="card">
                <h3>📚 ReDoc <span class="port">:8000</span></h3>
                <p>Alternative API documentation with a clean, readable format.</p>
            </a>
            <a href="/api/health" class="card">
                <h3>💚 Health Check <span class="port">:8000</span></h3>
                <p>API health status and database connection verification.</p>
            </a>
            <a href="/api/stats" class="card">
                <h3>📈 API Stats <span class="port">:8000</span></h3>
                <p>Repository statistics including total insights and categories.</p>
            </a>
        </div>

        <h2 class="section-title">Monitoring & Dashboards</h2>
        <div class="grid">
            <a href="http://localhost:3000" class="card" target="_blank">
                <h3>📊 Grafana <span class="port">:3000</span></h3>
                <p>Visualization dashboards for GSC metrics, GA4 data, and system performance.</p>
            </a>
            <a href="http://localhost:9090" class="card" target="_blank">
                <h3>🔥 Prometheus <span class="port">:9090</span></h3>
                <p>Metrics collection and alerting. Query and explore time-series data.</p>
            </a>
            <a href="http://localhost:8080" class="card" target="_blank">
                <h3>🐳 cAdvisor <span class="port">:8080</span></h3>
                <p>Container resource usage and performance monitoring.</p>
            </a>
        </div>

        <h2 class="section-title">Services</h2>
        <div class="grid">
            <a href="http://localhost:8001/docs" class="card" target="_blank">
                <h3>🔌 MCP Server <span class="port">:8001</span></h3>
                <p>Model Context Protocol server for AI-powered analytics queries.</p>
            </a>
            <a href="http://localhost:8002/metrics" class="card" target="_blank">
                <h3>📏 Metrics Exporter <span class="port">:8002</span></h3>
                <p>Custom application metrics in Prometheus format.</p>
            </a>
            <a href="http://localhost:9121/metrics" class="card" target="_blank">
                <h3>🔴 Redis Exporter <span class="port">:9121</span></h3>
                <p>Redis metrics for monitoring cache performance.</p>
            </a>
            <a href="http://localhost:9187/metrics" class="card" target="_blank">
                <h3>🐘 Postgres Exporter <span class="port">:9187</span></h3>
                <p>PostgreSQL database metrics and performance stats.</p>
            </a>
        </div>

        <div class="status" id="status">
            Checking system status...
        </div>

        <footer>
            Site Data Warehouse v1.0 &bull; GSC & GA4 Analytics Platform
        </footer>
    </div>

    <script>
        async function checkHealth() {
            const statusEl = document.getElementById('status');
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                if (data.status === 'healthy') {
                    statusEl.className = 'status';
                    statusEl.innerHTML = `✅ System Healthy &bull; Database Connected &bull; ${data.total_insights || 0} Total Insights`;
                } else {
                    statusEl.className = 'status loading';
                    statusEl.innerHTML = '⏳ System Initializing...';
                }
            } catch (e) {
                statusEl.className = 'status error';
                statusEl.innerHTML = '❌ Unable to connect to API';
            }
        }
        checkHealth();
        setInterval(checkHealth, 30000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """Render the system index page"""
    return INDEX_HTML


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
