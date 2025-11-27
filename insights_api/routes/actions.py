"""
Action Execution API Routes
===========================
API endpoints for executing content optimization actions.

Endpoints:
- POST /api/v1/actions/{action_id}/execute - Execute a single action
- POST /api/v1/actions/execute-batch - Execute multiple actions
- GET /api/v1/actions/{action_id}/status - Get action execution status
- GET /api/v1/actions/pending - List pending actions
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor, Json

from config.hugo_config import HugoConfig
from services.hugo_content_writer import HugoContentWriter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ActionExecutionRequest(BaseModel):
    """Request model for action execution."""
    dry_run: bool = Field(False, description="If true, validate but don't execute")


class ActionExecutionResponse(BaseModel):
    """Response model for action execution."""
    success: bool
    action_id: str
    status: str
    message: str
    file_path: Optional[str] = None
    changes_made: Optional[List[str]] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class BatchExecutionRequest(BaseModel):
    """Request model for batch action execution."""
    action_ids: List[str] = Field(..., min_length=1, max_length=50)
    dry_run: bool = Field(False, description="If true, validate but don't execute")


class BatchExecutionResponse(BaseModel):
    """Response model for batch execution."""
    total: int
    successful: int
    failed: int
    results: List[ActionExecutionResponse]


class PendingAction(BaseModel):
    """Model for pending action listing."""
    id: str
    insight_id: Optional[str] = None
    property: str
    action_type: str
    title: str
    description: Optional[str] = None
    priority: str
    effort: str
    estimated_impact: str
    status: str
    created_at: datetime
    entity_id: Optional[str] = None


class ActionStatus(BaseModel):
    """Model for action status."""
    id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============================================================================
# DATABASE & SERVICE HELPERS
# ============================================================================

def get_db_connection():
    """Get database connection."""
    dsn = os.getenv('WAREHOUSE_DSN')
    if not dsn:
        raise HTTPException(status_code=500, detail="Database not configured")
    return psycopg2.connect(dsn)


def get_hugo_config() -> HugoConfig:
    """Get Hugo configuration from environment."""
    config = HugoConfig.from_env()
    if not config.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Hugo content path not configured. Set HUGO_CONTENT_PATH environment variable."
        )
    validation_error = config.validate_path()
    if validation_error:
        raise HTTPException(status_code=503, detail=validation_error)
    return config


def get_content_writer(conn) -> HugoContentWriter:
    """Create content writer instance."""
    config = get_hugo_config()
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")
    return HugoContentWriter(
        config=config,
        db_connection=conn,
        ollama_base_url=ollama_url,
        ollama_model=ollama_model
    )


def verify_action_exists(conn, action_id: str) -> Optional[Dict[str, Any]]:
    """Verify action exists and return its details."""
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, status, property, action_type, title, metadata, entity_id
                FROM gsc.actions
                WHERE id = %s
            """, (action_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to verify action {action_id}: {e}")
        return None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/{action_id}/execute", response_model=ActionExecutionResponse)
async def execute_action(
    action_id: str = Path(..., description="Action UUID to execute"),
    request: ActionExecutionRequest = ActionExecutionRequest()
):
    """
    Execute a content optimization action.

    This endpoint triggers the execution of a pending action, which will:
    1. Fetch the action details from the database
    2. Resolve the target Hugo markdown file
    3. Generate optimized content using LLM
    4. Write changes to the file
    5. Update action status to 'completed'
    6. Update linked insight status to 'actioned'

    Args:
        action_id: UUID of the action to execute
        request: Execution options (dry_run)

    Returns:
        ActionExecutionResponse with execution results

    Raises:
        HTTPException 404: Action not found
        HTTPException 409: Action already completed or in progress
        HTTPException 503: Hugo not configured or Ollama unavailable
    """
    conn = None
    try:
        # Validate UUID format
        try:
            UUID(action_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid action ID format")

        conn = get_db_connection()

        # Check action exists and status
        action = verify_action_exists(conn, action_id)
        if not action:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        if action["status"] == "completed":
            raise HTTPException(
                status_code=409,
                detail=f"Action {action_id} already completed"
            )

        if action["status"] == "in_progress":
            raise HTTPException(
                status_code=409,
                detail=f"Action {action_id} is already in progress"
            )

        # Dry run - just validate
        if request.dry_run:
            config = get_hugo_config()
            # Check if file would be resolvable
            subdomain = config.extract_subdomain(action.get("property", ""))
            metadata = action.get("metadata") or {}
            page_path = metadata.get("page_path") or action.get("entity_id", "")

            if not subdomain or not page_path:
                return ActionExecutionResponse(
                    success=False,
                    action_id=action_id,
                    status="validation_failed",
                    message="Cannot resolve file path",
                    error="Missing property subdomain or page_path"
                )

            file_path = config.get_content_file_path(subdomain, page_path)
            file_exists = os.path.exists(file_path)

            return ActionExecutionResponse(
                success=file_exists,
                action_id=action_id,
                status="validated",
                message="Dry run complete" if file_exists else "File not found",
                file_path=file_path,
                error=None if file_exists else f"File not found: {file_path}"
            )

        # Execute action
        writer = get_content_writer(conn)
        result = writer.execute_action(action_id)

        return ActionExecutionResponse(
            success=result.get("success", False),
            action_id=action_id,
            status="completed" if result.get("success") else "failed",
            message="Action executed successfully" if result.get("success") else "Action execution failed",
            file_path=result.get("file_path"),
            changes_made=result.get("changes_made"),
            error=result.get("error"),
            started_at=result.get("started_at"),
            completed_at=result.get("completed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error executing action {action_id}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.post("/execute-batch", response_model=BatchExecutionResponse)
async def execute_batch(
    request: BatchExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute multiple actions in batch.

    Executes actions sequentially and returns aggregated results.
    For large batches, consider using the scheduler for background processing.

    Args:
        request: List of action IDs and execution options

    Returns:
        BatchExecutionResponse with aggregated results

    Note:
        Limited to 50 actions per batch to prevent timeout issues.
    """
    results: List[ActionExecutionResponse] = []
    successful = 0
    failed = 0

    conn = None
    try:
        conn = get_db_connection()
        writer = get_content_writer(conn)

        for action_id in request.action_ids:
            try:
                # Validate UUID
                UUID(action_id)

                if request.dry_run:
                    action = verify_action_exists(conn, action_id)
                    if action:
                        results.append(ActionExecutionResponse(
                            success=True,
                            action_id=action_id,
                            status="validated",
                            message="Dry run passed"
                        ))
                        successful += 1
                    else:
                        results.append(ActionExecutionResponse(
                            success=False,
                            action_id=action_id,
                            status="not_found",
                            message="Action not found",
                            error=f"Action {action_id} not found"
                        ))
                        failed += 1
                else:
                    result = writer.execute_action(action_id)
                    if result.get("success"):
                        successful += 1
                    else:
                        failed += 1

                    results.append(ActionExecutionResponse(
                        success=result.get("success", False),
                        action_id=action_id,
                        status="completed" if result.get("success") else "failed",
                        message="Executed" if result.get("success") else "Failed",
                        file_path=result.get("file_path"),
                        changes_made=result.get("changes_made"),
                        error=result.get("error")
                    ))

            except ValueError:
                failed += 1
                results.append(ActionExecutionResponse(
                    success=False,
                    action_id=action_id,
                    status="invalid",
                    message="Invalid action ID format",
                    error="Invalid UUID format"
                ))
            except Exception as e:
                failed += 1
                results.append(ActionExecutionResponse(
                    success=False,
                    action_id=action_id,
                    status="error",
                    message="Execution error",
                    error=str(e)
                ))

        return BatchExecutionResponse(
            total=len(request.action_ids),
            successful=successful,
            failed=failed,
            results=results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Batch execution failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/{action_id}/status", response_model=ActionStatus)
async def get_action_status(
    action_id: str = Path(..., description="Action UUID")
):
    """
    Get the execution status of an action.

    Returns current status and outcome details if completed.

    Args:
        action_id: UUID of the action

    Returns:
        ActionStatus with current state
    """
    conn = None
    try:
        UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action ID format")

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, status, started_at, completed_at, outcome
                FROM gsc.actions
                WHERE id = %s
            """, (action_id,))
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

            return ActionStatus(
                id=str(row["id"]),
                status=row["status"],
                started_at=row.get("started_at"),
                completed_at=row.get("completed_at"),
                outcome=row.get("outcome")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting status for {action_id}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/pending", response_model=List[PendingAction])
async def list_pending_actions(
    property: Optional[str] = Query(None, description="Filter by property"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    priority: Optional[str] = Query(None, description="Filter by priority (high/medium/low)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset")
):
    """
    List pending actions available for execution.

    Returns actions with status 'pending' that can be executed.

    Args:
        property: Optional property URL filter
        action_type: Optional action type filter
        priority: Optional priority filter
        limit: Maximum results (1-200)
        offset: Pagination offset

    Returns:
        List of pending actions
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT
                    id, insight_id, property, action_type, title,
                    description, priority, effort, estimated_impact,
                    status, created_at, entity_id
                FROM gsc.actions
                WHERE status = 'pending'
            """
            params: List[Any] = []

            if property:
                query += " AND property = %s"
                params.append(property)

            if action_type:
                query += " AND action_type = %s"
                params.append(action_type)

            if priority:
                query += " AND priority = %s"
                params.append(priority)

            # Order by priority then creation date
            query += """
                ORDER BY
                    CASE priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            cur.execute(query, params)

            results = []
            for row in cur.fetchall():
                results.append(PendingAction(
                    id=str(row["id"]),
                    insight_id=str(row["insight_id"]) if row.get("insight_id") else None,
                    property=row["property"],
                    action_type=row["action_type"],
                    title=row["title"],
                    description=row.get("description"),
                    priority=row["priority"],
                    effort=row["effort"],
                    estimated_impact=row["estimated_impact"],
                    status=row["status"],
                    created_at=row["created_at"],
                    entity_id=row.get("entity_id")
                ))

            return results

    except Exception as e:
        logger.exception("Error listing pending actions")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/execution-ready")
async def check_execution_ready():
    """
    Check if the action execution system is ready.

    Validates:
    - Database connection
    - Hugo content path configuration
    - Ollama availability (optional)

    Returns status of each component.
    """
    status = {
        "ready": False,
        "database": False,
        "hugo_config": False,
        "ollama": False,
        "errors": []
    }

    # Check database
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        status["database"] = True
    except Exception as e:
        status["errors"].append(f"Database: {str(e)}")
    finally:
        if conn:
            conn.close()

    # Check Hugo config
    try:
        config = HugoConfig.from_env()
        if config.is_configured():
            validation_error = config.validate_path()
            if validation_error:
                status["errors"].append(f"Hugo: {validation_error}")
            else:
                status["hugo_config"] = True
        else:
            status["errors"].append("Hugo: HUGO_CONTENT_PATH not configured")
    except Exception as e:
        status["errors"].append(f"Hugo: {str(e)}")

    # Check Ollama (optional - warn but don't fail)
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{ollama_url}/api/tags")
            status["ollama"] = response.status_code == 200
    except Exception as e:
        status["errors"].append(f"Ollama (optional): {str(e)}")

    # Overall ready status (Ollama is optional)
    status["ready"] = status["database"] and status["hugo_config"]

    return status
