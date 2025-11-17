"""Alert manager for storing and managing agent findings."""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg


@dataclass
class Alert:
    """Alert to be stored in database."""
    agent_name: str
    finding_type: str
    severity: str
    affected_pages: List[str]
    metrics: Dict[str, any]
    notes: Optional[str] = None
    metadata: Optional[Dict[str, any]] = None


class AlertManager:
    """Manages alerts and findings in the database."""

    def __init__(self, db_config: Dict[str, str]):
        """Initialize alert manager.
        
        Args:
            db_config: Database configuration dict
        """
        self.db_config = db_config
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Establish database connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.db_config.get('host', 'localhost'),
                port=self.db_config.get('port', 5432),
                user=self.db_config.get('user', 'gsc_user'),
                password=self.db_config.get('password', ''),
                database=self.db_config.get('database', 'gsc_warehouse'),
                min_size=2,
                max_size=10
            )

    async def disconnect(self):
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def create_alert(self, alert: Alert) -> int:
        """Create a new alert in the database.
        
        Args:
            alert: Alert to create
            
        Returns:
            Alert ID
        """
        if not self._pool:
            await self.connect()
        
        query = """
            INSERT INTO gsc.agent_findings (
                agent_name, finding_type, severity,
                affected_pages, metrics, notes, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
        """
        
        async with self._pool.acquire() as conn:
            alert_id = await conn.fetchval(
                query,
                alert.agent_name,
                alert.finding_type,
                alert.severity,
                json.dumps(alert.affected_pages),
                json.dumps(alert.metrics),
                alert.notes,
                json.dumps(alert.metadata or {})
            )
        
        return alert_id

    async def batch_create_alerts(self, alerts: List[Alert]) -> List[int]:
        """Create multiple alerts in a batch.
        
        Args:
            alerts: List of alerts to create
            
        Returns:
            List of alert IDs
        """
        if not alerts:
            return []
        
        if not self._pool:
            await self.connect()
        
        alert_ids = []
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for alert in alerts:
                    alert_id = await self.create_alert(alert)
                    alert_ids.append(alert_id)
        
        return alert_ids

    async def get_unprocessed_alerts(
        self,
        agent_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, any]]:
        """Get unprocessed alerts.
        
        Args:
            agent_name: Filter by agent name
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
        """
        if not self._pool:
            await self.connect()
        
        query = """
            SELECT id, agent_name, finding_type, severity,
                   affected_pages, metrics, detected_at, notes, metadata
            FROM gsc.agent_findings
            WHERE processed = FALSE
        """
        
        params = []
        
        if agent_name:
            query += " AND agent_name = $1"
            params.append(agent_name)
        
        query += f" ORDER BY severity DESC, detected_at DESC LIMIT ${len(params) + 1}"
        params.append(limit)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row['id'],
                'agent_name': row['agent_name'],
                'finding_type': row['finding_type'],
                'severity': row['severity'],
                'affected_pages': json.loads(row['affected_pages']) if row['affected_pages'] else [],
                'metrics': json.loads(row['metrics']) if row['metrics'] else {},
                'detected_at': row['detected_at'],
                'notes': row['notes'],
                'metadata': json.loads(row['metadata']) if row['metadata'] else {}
            })
        
        return alerts

    async def mark_processed(self, alert_ids: List[int]) -> int:
        """Mark alerts as processed.
        
        Args:
            alert_ids: List of alert IDs to mark as processed
            
        Returns:
            Number of alerts marked
        """
        if not alert_ids:
            return 0
        
        if not self._pool:
            await self.connect()
        
        query = """
            UPDATE gsc.agent_findings
            SET processed = TRUE, processed_at = CURRENT_TIMESTAMP
            WHERE id = ANY($1)
        """
        
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, alert_ids)
        
        # Extract count from result string like "UPDATE 5"
        count = int(result.split()[-1]) if result else 0
        
        return count

    async def get_alerts_by_severity(
        self,
        severity: str,
        days: int = 7
    ) -> List[Dict[str, any]]:
        """Get alerts by severity within a time period.
        
        Args:
            severity: Severity level ('critical', 'warning', 'info')
            days: Number of days to look back
            
        Returns:
            List of alert dictionaries
        """
        if not self._pool:
            await self.connect()
        
        query = """
            SELECT id, agent_name, finding_type, severity,
                   affected_pages, metrics, detected_at, processed
            FROM gsc.agent_findings
            WHERE severity = $1
              AND detected_at >= CURRENT_TIMESTAMP - $2 * INTERVAL '1 day'
            ORDER BY detected_at DESC
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, severity, days)
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row['id'],
                'agent_name': row['agent_name'],
                'finding_type': row['finding_type'],
                'severity': row['severity'],
                'affected_pages': json.loads(row['affected_pages']) if row['affected_pages'] else [],
                'metrics': json.loads(row['metrics']) if row['metrics'] else {},
                'detected_at': row['detected_at'],
                'processed': row['processed']
            })
        
        return alerts

    async def get_alert_stats(self, days: int = 7) -> Dict[str, any]:
        """Get statistics about alerts.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Statistics dictionary
        """
        if not self._pool:
            await self.connect()
        
        query = """
            SELECT 
                COUNT(*) as total_alerts,
                COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed,
                COUNT(*) FILTER (WHERE severity = 'critical') as critical_count,
                COUNT(*) FILTER (WHERE severity = 'warning') as warning_count,
                COUNT(*) FILTER (WHERE severity = 'info') as info_count,
                COUNT(DISTINCT agent_name) as active_agents,
                COUNT(DISTINCT finding_type) as finding_types
            FROM gsc.agent_findings
            WHERE detected_at >= CURRENT_TIMESTAMP - $1 * INTERVAL '1 day'
        """
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, days)
        
        return {
            'total_alerts': row['total_alerts'],
            'unprocessed': row['unprocessed'],
            'critical': row['critical_count'],
            'warning': row['warning_count'],
            'info': row['info_count'],
            'active_agents': row['active_agents'],
            'finding_types': row['finding_types'],
            'period_days': days
        }

    async def get_alerts_by_page(
        self,
        page_url: str,
        days: int = 30
    ) -> List[Dict[str, any]]:
        """Get all alerts for a specific page.
        
        Args:
            page_url: Page URL to filter by
            days: Number of days to look back
            
        Returns:
            List of alert dictionaries
        """
        if not self._pool:
            await self.connect()
        
        query = """
            SELECT id, agent_name, finding_type, severity,
                   affected_pages, metrics, detected_at, processed
            FROM gsc.agent_findings
            WHERE affected_pages::text LIKE $1
              AND detected_at >= CURRENT_TIMESTAMP - $2 * INTERVAL '1 day'
            ORDER BY detected_at DESC
        """
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, f'%{page_url}%', days)
        
        alerts = []
        for row in rows:
            alerts.append({
                'id': row['id'],
                'agent_name': row['agent_name'],
                'finding_type': row['finding_type'],
                'severity': row['severity'],
                'affected_pages': json.loads(row['affected_pages']) if row['affected_pages'] else [],
                'metrics': json.loads(row['metrics']) if row['metrics'] else {},
                'detected_at': row['detected_at'],
                'processed': row['processed']
            })
        
        return alerts

    async def delete_old_alerts(self, days: int = 90) -> int:
        """Delete old processed alerts.
        
        Args:
            days: Delete alerts older than this many days
            
        Returns:
            Number of alerts deleted
        """
        if not self._pool:
            await self.connect()
        
        query = """
            DELETE FROM gsc.agent_findings
            WHERE processed = TRUE
              AND detected_at < CURRENT_TIMESTAMP - $1 * INTERVAL '1 day'
        """
        
        async with self._pool.acquire() as conn:
            result = await conn.execute(query, days)
        
        count = int(result.split()[-1]) if result else 0
        
        return count
