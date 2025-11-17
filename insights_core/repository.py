"""
Repository for managing insights in PostgreSQL database
Handles CRUD operations and querying for insights
"""
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional
from datetime import datetime, timedelta

from insights_core.models import (
    Insight,
    InsightCreate,
    InsightUpdate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics
)


class InsightRepository:
    """Repository for insight persistence"""
    
    def __init__(self, dsn: str):
        """Initialize repository with database connection"""
        self.dsn = dsn
        # Test connection
        conn = self._get_connection()
        conn.close()
    
    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.dsn)
    
    def create(self, insight_create: InsightCreate) -> Insight:
        """
        Create a new insight or return existing if duplicate
        Uses deterministic ID to prevent duplicates
        """
        insight = insight_create.to_insight()
        
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO gsc.insights (
                        id, generated_at, property, entity_type, entity_id,
                        category, title, description, severity, confidence,
                        metrics, window_days, source, status, linked_insight_id,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING *
                """, (
                    insight.id,
                    insight.generated_at,
                    insight.property,
                    insight.entity_type.value,
                    insight.entity_id,
                    insight.category.value,
                    insight.title,
                    insight.description,
                    insight.severity.value,
                    insight.confidence,
                    json.dumps(insight.metrics.model_dump(exclude_none=True)),
                    insight.window_days,
                    insight.source,
                    insight.status.value,
                    insight_create.linked_insight_id
                ))
                row = cur.fetchone()
                conn.commit()
                return self._row_to_insight(dict(row))
        except psycopg2.IntegrityError:
            # Duplicate key - return existing insight
            conn.rollback()
            return self.get_by_id(insight.id)
        finally:
            conn.close()
    
    def get_by_id(self, insight_id: str) -> Optional[Insight]:
        """Get insight by ID"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gsc.insights WHERE id = %s
                """, (insight_id,))
                row = cur.fetchone()
                if row:
                    return self._row_to_insight(dict(row))
                return None
        finally:
            conn.close()
    
    def update(self, insight_id: str, update: InsightUpdate) -> Optional[Insight]:
        """Update an existing insight"""
        conn = self._get_connection()
        try:
            # Build update query dynamically based on provided fields
            update_fields = []
            values = []
            
            if update.status is not None:
                update_fields.append("status = %s")
                values.append(update.status.value)
            
            if update.description is not None:
                update_fields.append("description = %s")
                values.append(update.description)
            
            if update.linked_insight_id is not None:
                update_fields.append("linked_insight_id = %s")
                values.append(update.linked_insight_id)
            
            if not update_fields:
                # No fields to update
                return self.get_by_id(insight_id)
            
            # Add updated_at
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(insight_id)
            
            query = f"""
                UPDATE gsc.insights
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING *
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                row = cur.fetchone()
                conn.commit()
                if row:
                    return self._row_to_insight(dict(row))
                return None
        finally:
            conn.close()
    
    def query(
        self,
        property: Optional[str] = None,
        category: Optional[InsightCategory] = None,
        status: Optional[InsightStatus] = None,
        severity: Optional[InsightSeverity] = None,
        entity_type: Optional[EntityType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Insight]:
        """Query insights with filters"""
        conn = self._get_connection()
        try:
            where_clauses = []
            values = []
            
            if property:
                where_clauses.append("property = %s")
                values.append(property)
            
            if category:
                where_clauses.append("category = %s")
                values.append(category.value)
            
            if status:
                where_clauses.append("status = %s")
                values.append(status.value)
            
            if severity:
                where_clauses.append("severity = %s")
                values.append(severity.value)
            
            if entity_type:
                where_clauses.append("entity_type = %s")
                values.append(entity_type.value)
            
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)
            
            values.extend([limit, offset])
            
            query = f"""
                SELECT * FROM gsc.insights
                {where_sql}
                ORDER BY generated_at DESC
                LIMIT %s OFFSET %s
            """
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                rows = cur.fetchall()
                return [self._row_to_insight(dict(row)) for row in rows]
        finally:
            conn.close()
    
    def get_by_status(
        self,
        status: InsightStatus,
        property: Optional[str] = None,
        limit: int = 100
    ) -> List[Insight]:
        """Get insights by status"""
        return self.query(
            property=property,
            status=status,
            limit=limit
        )
    
    def get_by_category(
        self,
        category: InsightCategory,
        property: Optional[str] = None,
        severity: Optional[InsightSeverity] = None,
        limit: int = 100
    ) -> List[Insight]:
        """Get insights by category"""
        return self.query(
            property=property,
            category=category,
            severity=severity,
            limit=limit
        )
    
    def get_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        property: str,
        days_back: int = 90
    ) -> List[Insight]:
        """Get all insights for a specific entity"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gsc.insights
                    WHERE entity_type = %s
                        AND entity_id = %s
                        AND property = %s
                        AND generated_at >= %s
                    ORDER BY generated_at DESC
                """, (
                    entity_type,
                    entity_id,
                    property,
                    datetime.utcnow() - timedelta(days=days_back)
                ))
                rows = cur.fetchall()
                return [self._row_to_insight(dict(row)) for row in rows]
        finally:
            conn.close()
    
    def query_recent(
        self,
        hours: int = 24,
        property: Optional[str] = None
    ) -> List[Insight]:
        """Get insights generated in the last N hours"""
        conn = self._get_connection()
        try:
            where_clauses = [
                "generated_at >= %s"
            ]
            values = [datetime.utcnow() - timedelta(hours=hours)]
            
            if property:
                where_clauses.append("property = %s")
                values.append(property)
            
            where_sql = " AND ".join(where_clauses)
            
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT * FROM gsc.insights
                    WHERE {where_sql}
                    ORDER BY generated_at DESC
                """, values)
                rows = cur.fetchall()
                return [self._row_to_insight(dict(row)) for row in rows]
        finally:
            conn.close()
    
    def delete_old_insights(self, days: int = 90) -> int:
        """Delete insights older than specified days"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM gsc.insights
                    WHERE generated_at < %s
                """, (datetime.utcnow() - timedelta(days=days),))
                deleted = cur.rowcount
                conn.commit()
                return deleted
        finally:
            conn.close()
    
    def get_stats(self) -> dict:
        """Get repository statistics"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_insights,
                        COUNT(DISTINCT property) as unique_properties,
                        SUM(CASE WHEN category = 'risk' THEN 1 ELSE 0 END) as risk_count,
                        SUM(CASE WHEN category = 'opportunity' THEN 1 ELSE 0 END) as opportunity_count,
                        SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new_count,
                        SUM(CASE WHEN status = 'diagnosed' THEN 1 ELSE 0 END) as diagnosed_count,
                        SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high_severity_count,
                        MAX(generated_at) as latest_insight,
                        MIN(generated_at) as earliest_insight
                    FROM gsc.insights
                """)
                row = cur.fetchone()
                return dict(row) if row else {}
        finally:
            conn.close()
    
    def _row_to_insight(self, row: dict) -> Insight:
        """Convert database row to Insight model"""
        # Parse JSONB metrics
        if isinstance(row['metrics'], str):
            metrics_data = json.loads(row['metrics'])
        else:
            metrics_data = row['metrics']
        
        return Insight(
            id=row['id'],
            generated_at=row['generated_at'],
            property=row['property'],
            entity_type=EntityType(row['entity_type']),
            entity_id=row['entity_id'],
            category=InsightCategory(row['category']),
            title=row['title'],
            description=row['description'],
            severity=InsightSeverity(row['severity']),
            confidence=row['confidence'],
            metrics=InsightMetrics(**metrics_data),
            window_days=row['window_days'],
            source=row['source'],
            status=InsightStatus(row['status']),
            linked_insight_id=row.get('linked_insight_id'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )
