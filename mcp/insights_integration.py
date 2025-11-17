#!/usr/bin/env python3
"""
MCP Server - Insights Integration Module
Adds insights query tools to the MCP server

This module should be imported by mcp_server.py to add insights functionality
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Try to import insights_core
try:
    from insights_core.repository import InsightRepository
    from insights_core.config import InsightsConfig
    from insights_core.models import InsightCategory, InsightStatus, InsightSeverity
    INSIGHTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"insights_core not available: {e}")
    INSIGHTS_AVAILABLE = False


# ============================================================================
# REQUEST MODELS
# ============================================================================

class InsightsQueryRequest(BaseModel):
    """Request model for querying insights"""
    property: Optional[str] = Field(None, description="Filter by property URL")
    category: Optional[str] = Field(None, description="Filter by category (risk/opportunity/trend/diagnosis)")
    status: Optional[str] = Field(None, description="Filter by status (new/investigating/diagnosed/actioned/resolved)")
    severity: Optional[str] = Field(None, description="Filter by severity (low/medium/high)")
    limit: int = Field(100, ge=1, le=1000, description="Max results to return")


class InsightByIdRequest(BaseModel):
    """Request model for getting insight by ID"""
    insight_id: str = Field(..., description="Insight ID (SHA256 hash)")


class ActionableInsightsRequest(BaseModel):
    """Request model for getting actionable insights"""
    property: Optional[str] = Field(None, description="Filter by property URL")
    severity: Optional[str] = Field(None, description="Minimum severity filter")
    limit: int = Field(100, ge=1, le=1000, description="Max results to return")


# ============================================================================
# INSIGHTS TOOLS
# ============================================================================

def get_insights_tool_schemas() -> Dict[str, Dict]:
    """Return tool schemas for insights"""
    return {
        "query_insights": {
            "description": "Query insights from the Unified Insight Engine with filters",
            "input": InsightsQueryRequest.model_json_schema(),
            "output": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                    "insights": {"type": "array"}
                }
            },
            "examples": [
                {
                    "name": "Get all high severity risks",
                    "input": {
                        "category": "risk",
                        "severity": "high",
                        "limit": 20
                    }
                },
                {
                    "name": "Get new insights for a property",
                    "input": {
                        "property": "https://docs.aspose.com",
                        "status": "new",
                        "limit": 50
                    }
                }
            ]
        },
        "get_insight_by_id": {
            "description": "Get a specific insight by its ID",
            "input": InsightByIdRequest.model_json_schema(),
            "output": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "insight": {"type": "object"}
                }
            }
        },
        "get_actionable_insights": {
            "description": "Get insights that require action (status=new or diagnosed), sorted by priority",
            "input": ActionableInsightsRequest.model_json_schema(),
            "output": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                    "insights": {"type": "array"}
                }
            },
            "examples": [
                {
                    "name": "Get all actionable high severity insights",
                    "input": {
                        "severity": "high",
                        "limit": 10
                    }
                }
            ]
        },
        "get_recent_insights": {
            "description": "Get insights generated in the last N hours",
            "input": {
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Hours to look back",
                        "minimum": 1,
                        "maximum": 168,
                        "default": 24
                    },
                    "property": {
                        "type": "string",
                        "description": "Optional property filter"
                    }
                },
                "required": ["hours"]
            },
            "output": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "count": {"type": "integer"},
                    "insights": {"type": "array"}
                }
            }
        },
        "get_insights_summary": {
            "description": "Get summary statistics for a property's insights",
            "input": {
                "type": "object",
                "properties": {
                    "property": {
                        "type": "string",
                        "description": "Property URL",
                        "required": True
                    }
                },
                "required": ["property"]
            },
            "output": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "property": {"type": "string"},
                    "summary": {"type": "object"}
                }
            }
        }
    }


def call_insights_tool(tool_name: str, params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """
    Execute an insights tool call
    
    Args:
        tool_name: Name of the tool to call
        params: Tool parameters
        repository: InsightRepository instance
        
    Returns:
        Tool execution result
    """
    try:
        if tool_name == "query_insights":
            return _query_insights(params, repository)
        elif tool_name == "get_insight_by_id":
            return _get_insight_by_id(params, repository)
        elif tool_name == "get_actionable_insights":
            return _get_actionable_insights(params, repository)
        elif tool_name == "get_recent_insights":
            return _get_recent_insights(params, repository)
        elif tool_name == "get_insights_summary":
            return _get_insights_summary(params, repository)
        else:
            return {
                "status": "error",
                "error": f"Unknown insights tool: {tool_name}"
            }
    except Exception as e:
        logger.error(f"Error executing {tool_name}: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

def _query_insights(params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """Query insights with filters"""
    # Parse enum params
    category = InsightCategory(params['category']) if params.get('category') else None
    status = InsightStatus(params['status']) if params.get('status') else None
    severity = InsightSeverity(params['severity']) if params.get('severity') else None
    
    insights = repository.query(
        property=params.get('property'),
        category=category,
        status=status,
        severity=severity,
        limit=params.get('limit', 100)
    )
    
    return {
        "status": "success",
        "count": len(insights),
        "insights": [insight.model_dump() for insight in insights]
    }


def _get_insight_by_id(params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """Get insight by ID"""
    insight = repository.get_by_id(params['insight_id'])
    
    if not insight:
        return {
            "status": "error",
            "error": f"Insight not found: {params['insight_id']}"
        }
    
    return {
        "status": "success",
        "insight": insight.model_dump()
    }


def _get_actionable_insights(params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """Get actionable insights"""
    property_filter = params.get('property')
    limit = params.get('limit', 100)
    
    # Get new and diagnosed insights
    new_insights = repository.get_by_status(
        status=InsightStatus.NEW,
        property=property_filter,
        limit=limit
    )
    
    diagnosed_insights = repository.get_by_status(
        status=InsightStatus.DIAGNOSED,
        property=property_filter,
        limit=limit
    )
    
    all_actionable = new_insights + diagnosed_insights
    
    # Filter by severity if specified
    if params.get('severity'):
        severity = InsightSeverity(params['severity'])
        all_actionable = [i for i in all_actionable if i.severity == severity]
    
    # Sort by severity (high first) then by generated_at (newest first)
    severity_order = {'high': 0, 'medium': 1, 'low': 2}
    all_actionable.sort(
        key=lambda x: (severity_order.get(x.severity.value, 3), -x.generated_at.timestamp())
    )
    
    return {
        "status": "success",
        "count": len(all_actionable),
        "insights": [insight.model_dump() for insight in all_actionable[:limit]]
    }


def _get_recent_insights(params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """Get recent insights"""
    insights = repository.query_recent(
        hours=params.get('hours', 24),
        property=params.get('property')
    )
    
    return {
        "status": "success",
        "count": len(insights),
        "insights": [insight.model_dump() for insight in insights]
    }


def _get_insights_summary(params: Dict[str, Any], repository: InsightRepository) -> Dict[str, Any]:
    """Get insights summary for a property"""
    property_url = params['property']
    insights = repository.query(property=property_url, limit=10000)
    
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
        "property": property_url,
        "summary": {
            "total_insights": total,
            "recent_insights_7d": len(recent),
            "by_category": by_category,
            "by_status": by_status,
            "by_severity": by_severity,
            "actionable_count": by_status.get('new', 0) + by_status.get('diagnosed', 0)
        }
    }


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def initialize_insights_integration(warehouse_dsn: str) -> Optional[InsightRepository]:
    """
    Initialize insights repository for MCP server
    
    Args:
        warehouse_dsn: Database connection string
        
    Returns:
        InsightRepository instance or None if unavailable
    """
    if not INSIGHTS_AVAILABLE:
        logger.warning("Insights integration not available - insights_core not installed")
        return None
    
    try:
        config = InsightsConfig()
        config.warehouse_dsn = warehouse_dsn
        repository = InsightRepository(warehouse_dsn)
        logger.info("Insights integration initialized successfully")
        return repository
    except Exception as e:
        logger.error(f"Failed to initialize insights integration: {e}")
        return None
