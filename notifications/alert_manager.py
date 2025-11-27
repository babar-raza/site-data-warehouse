"""
Alert Manager - Central Orchestration for Notifications
========================================================
Manages alert rules, triggers, and notification delivery.

Features:
- Rule-based alerting
- Multi-channel notifications (Slack, Email, Webhook)
- Alert suppression and rate limiting
- Alert aggregation to prevent spam
- Delivery retry logic
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Central alert management and notification orchestration
    """

    def __init__(self, db_dsn: str = None):
        """
        Initialize Alert Manager

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self._pool: Optional[asyncpg.Pool] = None
        self._notifiers = {}  # Will be populated with channel notifiers

        logger.info("AlertManager initialized")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def register_notifier(self, channel_type: str, notifier):
        """
        Register a notification channel

        Args:
            channel_type: Channel type (slack, email, webhook, sms)
            notifier: Notifier instance with send() method
        """
        self._notifiers[channel_type] = notifier
        logger.info(f"Registered notifier for channel: {channel_type}")

    # =====================================================
    # ALERT RULE MANAGEMENT
    # =====================================================

    async def create_alert_rule(
        self,
        rule_name: str,
        rule_type: str,
        conditions: Dict,
        severity: str = 'medium',
        channels: List[str] = None,
        property: str = None,
        page_path: str = None,
        channel_config: Dict = None,
        suppression_window_minutes: int = 60,
        max_alerts_per_day: int = 10
    ) -> str:
        """
        Create a new alert rule

        Args:
            rule_name: Descriptive name for the rule
            rule_type: Type of alert (serp_drop, cwv_violation, traffic_anomaly, etc.)
            conditions: JSONB conditions that trigger the alert
            severity: Alert severity (low, medium, high, critical)
            channels: List of notification channels
            property: Property URL (optional, NULL = all properties)
            page_path: Page path (optional, NULL = all pages)
            channel_config: Channel-specific configuration
            suppression_window_minutes: Minutes before re-alerting
            max_alerts_per_day: Maximum alerts per day for this rule

        Returns:
            rule_id: UUID of created rule
        """
        if channels is None:
            channels = ['slack']

        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                rule_id = await conn.fetchval("""
                    INSERT INTO notifications.alert_rules (
                        rule_name,
                        rule_type,
                        property,
                        page_path,
                        conditions,
                        severity,
                        channels,
                        channel_config,
                        suppression_window_minutes,
                        max_alerts_per_day,
                        is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    RETURNING rule_id
                """,
                    rule_name,
                    rule_type,
                    property,
                    page_path,
                    conditions,
                    severity,
                    channels,
                    channel_config,
                    suppression_window_minutes,
                    max_alerts_per_day,
                    True
                )

            logger.info(f"Created alert rule: {rule_name} ({rule_id})")
            return str(rule_id)

        except Exception as e:
            logger.error(f"Error creating alert rule: {e}")
            raise

    async def get_alert_rules(
        self,
        rule_type: str = None,
        is_active: bool = True
    ) -> List[Dict]:
        """
        Get alert rules

        Args:
            rule_type: Filter by rule type (optional)
            is_active: Filter by active status

        Returns:
            List of alert rules
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                query = """
                    SELECT *
                    FROM notifications.alert_rules
                    WHERE is_active = $1
                """
                params = [is_active]

                if rule_type:
                    query += " AND rule_type = $2"
                    params.append(rule_type)

                query += " ORDER BY created_at DESC"

                rules = await conn.fetch(query, *params)

            return [dict(rule) for rule in rules]

        except Exception as e:
            logger.error(f"Error fetching alert rules: {e}")
            return []

    async def update_alert_rule(
        self,
        rule_id: str,
        **kwargs
    ) -> bool:
        """
        Update an alert rule

        Args:
            rule_id: Rule ID to update
            **kwargs: Fields to update

        Returns:
            True if updated successfully
        """
        try:
            pool = await self.get_pool()

            # Build dynamic UPDATE query
            set_clauses = []
            params = []
            param_num = 1

            for key, value in kwargs.items():
                if key in ['rule_name', 'conditions', 'severity', 'channels',
                          'channel_config', 'is_active', 'suppression_window_minutes',
                          'max_alerts_per_day']:
                    set_clauses.append(f"{key} = ${param_num}")
                    params.append(value)
                    param_num += 1

            if not set_clauses:
                logger.warning("No valid fields to update")
                return False

            params.append(rule_id)
            query = f"""
                UPDATE notifications.alert_rules
                SET {', '.join(set_clauses)}
                WHERE rule_id = ${param_num}
            """

            async with pool.acquire() as conn:
                result = await conn.execute(query, *params)

            logger.info(f"Updated alert rule: {rule_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating alert rule: {e}")
            return False

    async def delete_alert_rule(self, rule_id: str) -> bool:
        """
        Soft delete (deactivate) an alert rule

        Args:
            rule_id: Rule ID to delete

        Returns:
            True if deleted successfully
        """
        return await self.update_alert_rule(rule_id, is_active=False)

    # =====================================================
    # ALERT TRIGGERING
    # =====================================================

    async def trigger_alert(
        self,
        rule_id: str,
        property: str,
        title: str,
        message: str,
        page_path: str = None,
        metadata: Dict = None
    ) -> Optional[str]:
        """
        Trigger an alert from a rule

        Uses database function for suppression logic and queue management

        Args:
            rule_id: Alert rule ID
            property: Property URL
            title: Alert title
            message: Alert message
            page_path: Page path (optional)
            metadata: Additional metadata (optional)

        Returns:
            alert_id if created, None if suppressed/failed
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                alert_id = await conn.fetchval("""
                    SELECT notifications.trigger_alert($1, $2, $3, $4, $5, $6)
                """,
                    rule_id,
                    property,
                    page_path,
                    title,
                    message,
                    metadata
                )

            if alert_id:
                logger.info(f"Alert triggered: {title} ({alert_id})")
                # Process notification queue immediately
                await self.process_notification_queue()
                return str(alert_id)
            else:
                logger.debug(f"Alert suppressed: {title}")
                return None

        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
            return None

    async def check_and_trigger_serp_drop(
        self,
        query_id: str,
        property: str,
        query_text: str,
        old_position: int,
        new_position: int
    ) -> Optional[str]:
        """
        Check SERP position drop and trigger alert if threshold exceeded

        Args:
            query_id: Query ID
            property: Property URL
            query_text: Search query text
            old_position: Previous position
            new_position: Current position

        Returns:
            alert_id if triggered
        """
        position_drop = new_position - old_position

        if position_drop <= 0:
            # Position improved or stayed same
            return None

        # Find matching rules
        rules = await self.get_alert_rules(rule_type='serp_drop')

        for rule in rules:
            # Check if rule applies to this property
            if rule['property'] and rule['property'] != property:
                continue

            # Check threshold
            threshold = rule['conditions'].get('position_drop', 3)

            if position_drop >= threshold:
                title = f"🔻 SERP Position Drop: {query_text}"
                message = f"""
**Query**: {query_text}
**Property**: {property}
**Position Change**: {old_position} → {new_position} (-{position_drop})
**Threshold**: {threshold}

This is a significant position drop that may require attention.
                """.strip()

                metadata = {
                    'query_id': query_id,
                    'query_text': query_text,
                    'old_position': old_position,
                    'new_position': new_position,
                    'position_drop': position_drop
                }

                return await self.trigger_alert(
                    rule_id=str(rule['rule_id']),
                    property=property,
                    title=title,
                    message=message,
                    metadata=metadata
                )

        return None

    async def check_and_trigger_cwv_violation(
        self,
        property: str,
        page_path: str,
        lcp: float,
        cls: float,
        performance_score: int
    ) -> Optional[str]:
        """
        Check Core Web Vitals and trigger alert if budget violated

        Args:
            property: Property URL
            page_path: Page path
            lcp: Largest Contentful Paint (ms)
            cls: Cumulative Layout Shift
            performance_score: Lighthouse performance score

        Returns:
            alert_id if triggered
        """
        rules = await self.get_alert_rules(rule_type='cwv_violation')

        for rule in rules:
            # Check if rule applies
            if rule['property'] and rule['property'] != property:
                continue

            conditions = rule['conditions']
            violations = []

            # Check LCP
            if lcp and 'lcp_max' in conditions:
                if lcp > conditions['lcp_max']:
                    violations.append(f"LCP: {lcp}ms (max: {conditions['lcp_max']}ms)")

            # Check CLS
            if cls and 'cls_max' in conditions:
                if cls > conditions['cls_max']:
                    violations.append(f"CLS: {cls} (max: {conditions['cls_max']})")

            # Check performance score
            if performance_score and 'performance_score_min' in conditions:
                if performance_score < conditions['performance_score_min']:
                    violations.append(f"Performance Score: {performance_score} (min: {conditions['performance_score_min']})")

            if violations:
                title = f"⚠️ Core Web Vitals Violation: {page_path}"
                message = f"""
**Page**: {page_path}
**Property**: {property}

**Violations**:
{chr(10).join(f'• {v}' for v in violations)}

**Current Metrics**:
• LCP: {lcp}ms
• CLS: {cls}
• Performance Score: {performance_score}

Please review and optimize this page.
                """.strip()

                metadata = {
                    'page_path': page_path,
                    'lcp': lcp,
                    'cls': cls,
                    'performance_score': performance_score,
                    'violations': violations
                }

                return await self.trigger_alert(
                    rule_id=str(rule['rule_id']),
                    property=property,
                    title=title,
                    message=message,
                    page_path=page_path,
                    metadata=metadata
                )

        return None

    # =====================================================
    # NOTIFICATION DELIVERY
    # =====================================================

    async def process_notification_queue(self, max_batch: int = 100):
        """
        Process pending notifications in the queue

        Args:
            max_batch: Maximum notifications to process
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # Get pending notifications
                pending = await conn.fetch("""
                    SELECT * FROM notifications.get_pending_notifications()
                """)

            if not pending:
                logger.debug("No pending notifications")
                return

            logger.info(f"Processing {len(pending)} pending notifications")

            for notif in pending:
                await self._send_notification(
                    queue_id=str(notif['queue_id']),
                    alert_id=str(notif['alert_id']),
                    channel_type=notif['channel_type'],
                    channel_config=notif['channel_config'],
                    payload=notif['payload'],
                    attempts=notif['attempts']
                )

        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")

    async def _send_notification(
        self,
        queue_id: str,
        alert_id: str,
        channel_type: str,
        channel_config: Dict,
        payload: Dict,
        attempts: int
    ):
        """
        Send a single notification

        Args:
            queue_id: Queue entry ID
            alert_id: Alert ID
            channel_type: Notification channel
            channel_config: Channel configuration
            payload: Message payload
            attempts: Current attempt count
        """
        pool = await self.get_pool()

        try:
            # Get notifier for this channel
            notifier = self._notifiers.get(channel_type)

            if not notifier:
                logger.warning(f"No notifier registered for channel: {channel_type}")
                await self._mark_notification_failed(
                    queue_id,
                    alert_id,
                    channel_type,
                    f"No notifier for {channel_type}"
                )
                return

            # Update status to 'sending'
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE notifications.notification_queue
                    SET status = 'sending', attempts = attempts + 1
                    WHERE queue_id = $1
                """, queue_id)

            # Send notification
            success = await notifier.send(payload, channel_config)

            if success:
                # Mark as sent
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE notifications.notification_queue
                        SET status = 'sent', sent_at = NOW()
                        WHERE queue_id = $1
                    """, queue_id)

                    # Update alert history
                    await conn.execute("""
                        UPDATE notifications.alert_history
                        SET channels_sent = array_append(
                            COALESCE(channels_sent, ARRAY[]::TEXT[]),
                            $2
                        )
                        WHERE alert_id = $1
                    """, alert_id, channel_type)

                logger.info(f"Notification sent via {channel_type}: {alert_id}")
            else:
                await self._mark_notification_failed(
                    queue_id,
                    alert_id,
                    channel_type,
                    "Send failed"
                )

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            await self._mark_notification_failed(
                queue_id,
                alert_id,
                channel_type,
                str(e)
            )

    async def _mark_notification_failed(
        self,
        queue_id: str,
        alert_id: str,
        channel_type: str,
        error: str
    ):
        """Mark notification as failed and schedule retry"""
        pool = await self.get_pool()

        async with pool.acquire() as conn:
            # Update queue entry
            await conn.execute("""
                UPDATE notifications.notification_queue
                SET
                    status = 'failed',
                    last_error = $2,
                    next_attempt_at = NOW() + INTERVAL '5 minutes'
                WHERE queue_id = $1
            """, queue_id, error)

            # Update alert history
            await conn.execute("""
                UPDATE notifications.alert_history
                SET channels_failed = array_append(
                    COALESCE(channels_failed, ARRAY[]::TEXT[]),
                    $2
                )
                WHERE alert_id = $1
            """, alert_id, channel_type)

    # =====================================================
    # ALERT RESOLUTION
    # =====================================================

    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_notes: str = None,
        is_false_positive: bool = False
    ) -> bool:
        """
        Resolve an alert

        Args:
            alert_id: Alert ID
            resolved_by: User resolving the alert
            resolution_notes: Optional notes
            is_false_positive: Mark as false positive

        Returns:
            True if resolved successfully
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                await conn.execute("""
                    SELECT notifications.resolve_alert($1, $2, $3, $4)
                """,
                    alert_id,
                    resolved_by,
                    resolution_notes,
                    is_false_positive
                )

            logger.info(f"Alert resolved: {alert_id}")
            return True

        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False

    async def get_active_alerts(self) -> List[Dict]:
        """Get all active (unresolved) alerts"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                alerts = await conn.fetch("""
                    SELECT * FROM notifications.vw_active_alerts
                    ORDER BY triggered_at DESC
                """)

            return [dict(alert) for alert in alerts]

        except Exception as e:
            logger.error(f"Error fetching active alerts: {e}")
            return []

    async def get_alert_stats(self) -> Dict:
        """Get alert system statistics"""
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT * FROM notifications.vw_alert_health
                """)

            return dict(stats) if stats else {}

        except Exception as e:
            logger.error(f"Error fetching alert stats: {e}")
            return {}

    # =====================================================
    # SUPPRESSION MANAGEMENT
    # =====================================================

    async def create_suppression(
        self,
        suppression_name: str,
        start_time: datetime,
        end_time: datetime,
        reason: str,
        rule_id: str = None,
        property: str = None,
        alert_type: str = None,
        created_by: str = None
    ) -> str:
        """
        Create an alert suppression window

        Args:
            suppression_name: Name for this suppression
            start_time: Start of suppression window
            end_time: End of suppression window
            reason: Reason for suppression
            rule_id: Specific rule to suppress (optional)
            property: Specific property to suppress (optional)
            alert_type: Specific alert type to suppress (optional)
            created_by: User creating suppression

        Returns:
            suppression_id
        """
        try:
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                suppression_id = await conn.fetchval("""
                    INSERT INTO notifications.suppressions (
                        suppression_name,
                        rule_id,
                        property,
                        alert_type,
                        start_time,
                        end_time,
                        reason,
                        created_by,
                        is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING suppression_id
                """,
                    suppression_name,
                    rule_id,
                    property,
                    alert_type,
                    start_time,
                    end_time,
                    reason,
                    created_by,
                    True
                )

            logger.info(f"Created suppression: {suppression_name} ({suppression_id})")
            return str(suppression_id)

        except Exception as e:
            logger.error(f"Error creating suppression: {e}")
            raise


# Synchronous wrapper for Celery
def process_notification_queue_sync():
    """Synchronous wrapper for notification queue processing"""
    manager = AlertManager()
    return asyncio.run(manager.process_notification_queue())


__all__ = ['AlertManager']
