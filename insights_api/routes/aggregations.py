"""
Insight Aggregation API Routes

Provides endpoints for aggregated insight data:
- /api/v1/insights/aggregations/by-page
- /api/v1/insights/aggregations/by-subdomain
- /api/v1/insights/aggregations/by-category
- /api/v1/insights/aggregations/dashboard
- /api/v1/insights/aggregations/timeseries
- /api/v1/insights/aggregations/top-issues

These endpoints leverage the database views created in sql/24_insight_aggregation_views.sql
for efficient aggregation queries.
"""
import logging
import os
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/insights/aggregations", tags=["aggregations"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class PageAggregation(BaseModel):
    """Aggregation by page"""
    property: str
    page_path: str
    total_insights: int
    risk_count: int
    opportunity_count: int
    trend_count: int
    diagnosis_count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    new_count: int
    actioned_count: int
    resolved_count: int
    latest_insight: Optional[datetime] = None
    earliest_insight: Optional[datetime] = None
    avg_confidence: Optional[float] = None


class SubdomainAggregation(BaseModel):
    """Aggregation by subdomain"""
    property: str
    subdomain: str
    total_insights: int
    risk_count: int
    opportunity_count: int
    trend_count: int
    diagnosis_count: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    unique_pages: int
    latest_insight: Optional[datetime] = None


class CategoryAggregation(BaseModel):
    """Aggregation by category"""
    property: str
    category: str
    total_insights: int
    high_severity_count: int
    medium_severity_count: int
    low_severity_count: int
    new_count: int
    investigating_count: int
    diagnosed_count: int
    actioned_count: int
    resolved_count: int
    unique_entities: int
    unique_sources: int
    avg_confidence: Optional[float] = None
    latest_insight: Optional[datetime] = None
    earliest_insight: Optional[datetime] = None


class DashboardSummary(BaseModel):
    """Dashboard summary data"""
    property: str
    total_insights: int
    total_risks: int
    total_opportunities: int
    total_trends: int
    total_diagnoses: int
    high_severity_total: int
    high_severity_new: int
    new_insights: int
    actioned_insights: int
    resolved_insights: int
    unique_entities: int
    avg_confidence: Optional[float] = None
    last_insight_time: Optional[datetime] = None
    insights_last_24h: int
    insights_last_7d: int
    insights_last_30d: int


class TimeseriesPoint(BaseModel):
    """Time series data point"""
    property: str
    date: str
    category: str
    insight_count: int
    high_count: int
    medium_count: int
    low_count: int


class TopIssue(BaseModel):
    """Top issue item"""
    id: str
    property: str
    entity_type: str
    entity_id: str
    category: str
    title: str
    severity: str
    confidence: float
    status: str
    generated_at: datetime
    source: str
    priority_score: float


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """
    Get database connection using WAREHOUSE_DSN environment variable

    Returns:
        psycopg2.connection: Database connection

    Raises:
        HTTPException: If DSN not configured
    """
    dsn = os.getenv('WAREHOUSE_DSN')
    if not dsn:
        raise HTTPException(status_code=500, detail="Database not configured")
    return psycopg2.connect(dsn)


# ============================================================================
# ENDPOINT HANDLERS
# ============================================================================

@router.get("/by-page", response_model=List[PageAggregation])
async def get_insights_by_page(
    property: str = Query(..., description="Property to filter by"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset")
):
    """
    Get insights aggregated by page path

    Returns counts of insights grouped by individual page paths,
    with breakdowns by category, severity, and status.

    Args:
        property: Property URL to filter by (required)
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        List[PageAggregation]: List of page-level aggregations

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM gsc.vw_insights_by_page
                WHERE property = %s
                ORDER BY total_insights DESC
                LIMIT %s OFFSET %s
            """, (property, limit, offset))

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in by-page aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()


@router.get("/by-subdomain", response_model=List[SubdomainAggregation])
async def get_insights_by_subdomain(
    property: Optional[str] = Query(None, description="Property to filter by"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset")
):
    """
    Get insights aggregated by subdomain

    Groups insights by subdomain extracted from entity_id,
    useful for understanding which parts of the site have issues.

    Args:
        property: Optional property URL to filter by
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        List[SubdomainAggregation]: List of subdomain-level aggregations

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if property:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_by_subdomain
                    WHERE property = %s
                    ORDER BY total_insights DESC
                    LIMIT %s OFFSET %s
                """, (property, limit, offset))
            else:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_by_subdomain
                    ORDER BY total_insights DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in by-subdomain aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()


@router.get("/by-category", response_model=List[CategoryAggregation])
async def get_insights_by_category(
    property: Optional[str] = Query(None, description="Property to filter by"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset")
):
    """
    Get insights aggregated by category

    Groups insights by category (risk, opportunity, trend, diagnosis)
    with detailed breakdowns of severity and status.

    Args:
        property: Optional property URL to filter by
        limit: Maximum number of results to return (1-1000, default 100)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        List[CategoryAggregation]: List of category-level aggregations

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if property:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_by_category
                    WHERE property = %s
                    ORDER BY total_insights DESC
                    LIMIT %s OFFSET %s
                """, (property, limit, offset))
            else:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_by_category
                    ORDER BY total_insights DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in by-category aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()


@router.get("/dashboard", response_model=List[DashboardSummary])
async def get_dashboard_summary(
    property: Optional[str] = Query(None, description="Property to filter by")
):
    """
    Get dashboard summary statistics

    Returns comprehensive summary including totals, severity breakdown,
    status distribution, and time-based metrics.

    Args:
        property: Optional property URL to filter by. If not provided,
                 returns summaries for all properties.

    Returns:
        List[DashboardSummary]: List of dashboard summaries (one per property)

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if property:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_dashboard
                    WHERE property = %s
                """, (property,))
            else:
                cur.execute("""
                    SELECT *
                    FROM gsc.vw_insights_dashboard
                    ORDER BY total_insights DESC
                """)

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in dashboard aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()


@router.get("/timeseries", response_model=List[TimeseriesPoint])
async def get_timeseries(
    property: str = Query(..., description="Property to filter by"),
    days: int = Query(30, ge=1, le=90, description="Days of history"),
    category: Optional[str] = Query(None, description="Category filter")
):
    """
    Get time series data for charting

    Returns daily insight counts by category for the specified period.

    Args:
        property: Property URL to filter by (required)
        days: Number of days of history to return (1-90, default 30)
        category: Optional category filter (risk, opportunity, trend, diagnosis)

    Returns:
        List[TimeseriesPoint]: List of daily data points

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if category:
                cur.execute("""
                    SELECT
                        property,
                        date::text,
                        category,
                        insight_count,
                        high_count,
                        medium_count,
                        low_count
                    FROM gsc.vw_insights_timeseries
                    WHERE property = %s
                      AND category = %s
                      AND date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY date DESC
                """, (property, category, days))
            else:
                cur.execute("""
                    SELECT
                        property,
                        date::text,
                        category,
                        insight_count,
                        high_count,
                        medium_count,
                        low_count
                    FROM gsc.vw_insights_timeseries
                    WHERE property = %s
                      AND date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY date DESC, category
                """, (property, days))

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in timeseries aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()


@router.get("/top-issues", response_model=List[TopIssue])
async def get_top_issues(
    property: str = Query(..., description="Property to filter by"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    category: Optional[str] = Query(None, description="Category filter"),
    severity: Optional[str] = Query(None, description="Severity filter")
):
    """
    Get top priority issues

    Returns issues sorted by priority score (severity * confidence),
    filtered to new and investigating status.

    Args:
        property: Property URL to filter by (required)
        limit: Maximum number of results to return (1-100, default 20)
        category: Optional category filter (risk, opportunity, trend, diagnosis)
        severity: Optional severity filter (low, medium, high)

    Returns:
        List[TopIssue]: List of top priority issues

    Raises:
        HTTPException: If database error occurs
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT *
                FROM gsc.vw_top_issues
                WHERE property = %s
            """
            params = [property]

            if category:
                query += " AND category = %s"
                params.append(category)

            if severity:
                query += " AND severity = %s"
                params.append(severity)

            query += " LIMIT %s"
            params.append(limit)

            cur.execute(query, params)

            results = [dict(row) for row in cur.fetchall()]
            return results

    except psycopg2.Error as e:
        logger.error(f"Database error in top-issues aggregation: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        if conn:
            conn.close()
