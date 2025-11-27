"""
Action Generator - Creates actionable tasks from insights

Transforms insights into concrete, actionable tasks with
clear instructions, priority, and estimated impact.

Example:
    generator = ActionGenerator()
    action = generator.generate_from_insight('insight-uuid-here')
    actions = generator.generate_batch('sc-domain:example.com')
"""
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

import psycopg2
from psycopg2.extras import RealDictCursor

from services.action_generator.templates import ActionTemplates

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """Represents an actionable task"""
    id: str
    insight_id: str
    property: str
    action_type: str
    title: str
    description: str
    instructions: List[str]
    priority: str  # 'critical', 'high', 'medium', 'low'
    effort: str  # 'low', 'medium', 'high'
    estimated_impact: Dict
    status: str  # 'pending', 'in_progress', 'completed', 'cancelled'
    assigned_to: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    outcome: Optional[Dict]

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return data


class ActionGenerator:
    """
    Generates actionable tasks from insights

    Takes insights from the insight engine and converts them
    into concrete, actionable tasks with clear instructions.

    Example:
        generator = ActionGenerator()

        # Generate action from single insight
        action = generator.generate_from_insight('insight-uuid-here')

        # Generate batch of actions
        actions = generator.generate_batch('sc-domain:example.com', limit=50)

        # Get prioritized actions
        prioritized = generator.prioritize_actions(actions)
    """

    # Priority mapping from severity
    PRIORITY_MAP = {
        'high': 'critical',
        'medium': 'high',
        'low': 'medium'
    }

    def __init__(self, db_dsn: str = None):
        """
        Initialize Action Generator

        Args:
            db_dsn: Database connection string
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.templates = ActionTemplates()
        logger.info("ActionGenerator initialized")

    def generate_from_insight(self, insight_id: str) -> Optional[Action]:
        """
        Generate action from a single insight

        Args:
            insight_id: UUID of the insight

        Returns:
            Action object or None if insight not found

        Example:
            >>> generator = ActionGenerator()
            >>> action = generator.generate_from_insight('abc-123-def')
            >>> print(action.title)
        """
        insight = self._get_insight(insight_id)
        if not insight:
            logger.warning(f"Insight not found: {insight_id}")
            return None

        # Check if action already exists for this insight
        existing = self._get_existing_action(insight_id)
        if existing:
            logger.debug(f"Action already exists for insight {insight_id}")
            return existing

        # Get appropriate template
        template = self.templates.get_for_insight(insight)

        # Create action
        action = self._create_action(insight, template)

        # Store in database
        self._store_action(action)

        logger.info(f"Generated action '{action.title}' for insight {insight_id}")
        return action

    def generate_batch(self, property: str, limit: int = 50,
                       category: str = None, severity: str = None) -> List[Action]:
        """
        Generate actions for multiple insights

        Args:
            property: Property to generate actions for
            limit: Maximum number of actions to generate
            category: Optional category filter
            severity: Optional severity filter

        Returns:
            List of generated actions

        Example:
            >>> generator = ActionGenerator()
            >>> actions = generator.generate_batch('sc-domain:example.com', limit=20)
            >>> print(f"Generated {len(actions)} actions")
        """
        insights = self._get_actionable_insights(property, limit, category, severity)
        actions = []

        for insight in insights:
            try:
                action = self.generate_from_insight(insight['id'])
                if action:
                    actions.append(action)
            except Exception as e:
                logger.error(f"Error generating action for insight {insight['id']}: {e}")

        logger.info(f"Generated {len(actions)} actions for {property}")
        return actions

    def prioritize_actions(self, actions: List[Action]) -> List[Action]:
        """
        Prioritize actions by impact and effort

        Uses a priority score based on:
        - Priority level (critical=100, high=75, medium=50, low=25)
        - Effort inverse (low=3, medium=2, high=1)
        - Estimated impact

        Args:
            actions: List of actions to prioritize

        Returns:
            Sorted list of actions (highest priority first)
        """
        def priority_score(action: Action) -> float:
            priority_weights = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
            effort_weights = {'low': 3, 'medium': 2, 'high': 1}

            priority = priority_weights.get(action.priority, 50)
            effort = effort_weights.get(action.effort, 2)

            # Factor in estimated impact
            impact = action.estimated_impact.get('traffic_potential', 0)
            impact_score = min(impact / 100, 1.0) * 50  # Max 50 points from impact

            return priority * effort + impact_score

        return sorted(actions, key=priority_score, reverse=True)

    def get_pending_actions(self, property: str, limit: int = 100) -> List[Action]:
        """
        Get pending actions for a property

        Args:
            property: Property to get actions for
            limit: Maximum number of actions

        Returns:
            List of pending actions
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT *
                FROM gsc.actions
                WHERE property = %s
                  AND status = 'pending'
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT %s
            """, (property, limit))

            return [self._row_to_action(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting pending actions: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def complete_action(self, action_id: str, outcome: Dict = None) -> bool:
        """
        Mark an action as completed

        Args:
            action_id: UUID of the action
            outcome: Optional outcome data (results, metrics, notes)

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE gsc.actions
                SET status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    outcome = %s
                WHERE id = %s
            """, (psycopg2.extras.Json(outcome) if outcome else None, action_id))

            conn.commit()
            logger.info(f"Action {action_id} marked as completed")
            return True

        except Exception as e:
            logger.error(f"Error completing action: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_insight(self, insight_id: str) -> Optional[Dict]:
        """Get insight from database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT *
                FROM gsc.insights
                WHERE id = %s
            """, (insight_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting insight: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_existing_action(self, insight_id: str) -> Optional[Action]:
        """Check if action exists for insight"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT *
                FROM gsc.actions
                WHERE insight_id = %s
                  AND status != 'cancelled'
            """, (insight_id,))

            row = cursor.fetchone()
            return self._row_to_action(row) if row else None

        except Exception as e:
            logger.error(f"Error checking existing action: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _get_actionable_insights(self, property: str, limit: int,
                                  category: str = None, severity: str = None) -> List[Dict]:
        """Get insights that don't have actions yet"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT i.*
                FROM gsc.insights i
                LEFT JOIN gsc.actions a ON i.id = a.insight_id AND a.status != 'cancelled'
                WHERE i.property = %s
                  AND i.status IN ('new', 'investigating', 'diagnosed')
                  AND a.id IS NULL
            """
            params = [property]

            if category:
                query += " AND i.category = %s"
                params.append(category)

            if severity:
                query += " AND i.severity = %s"
                params.append(severity)

            query += """
                ORDER BY
                    CASE i.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    i.generated_at DESC
                LIMIT %s
            """
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting actionable insights: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _create_action(self, insight: Dict, template: Dict) -> Action:
        """Create action from insight and template"""
        # Format template strings with insight data
        context = {
            'page_path': insight.get('entity_id', ''),
            'property': insight.get('property', ''),
            'title': insight.get('title', ''),
            'category': insight.get('category', ''),
            'severity': insight.get('severity', ''),
            **insight.get('metrics', {})
        }

        # Format instructions
        instructions = [
            instr.format(**context) if '{' in instr else instr
            for instr in template.get('instructions', [])
        ]

        # Calculate priority from severity
        priority = self.PRIORITY_MAP.get(insight.get('severity', 'medium'), 'medium')

        # Build estimated impact
        estimated_impact = template.get('estimated_impact', {}).copy()
        metrics = insight.get('metrics', {})
        if metrics:
            clicks = metrics.get('gsc_clicks', 0) or 0
            estimated_impact['traffic_potential'] = int(clicks * 0.1)  # 10% improvement estimate

        return Action(
            id=str(uuid.uuid4()),
            insight_id=insight['id'],
            property=insight['property'],
            action_type=template.get('action_type', 'general'),
            title=template.get('title_template', 'Action for {title}').format(**context),
            description=template.get('description_template', insight.get('description', '')).format(**context),
            instructions=instructions,
            priority=priority,
            effort=template.get('effort', 'medium'),
            estimated_impact=estimated_impact,
            status='pending',
            assigned_to=None,
            created_at=datetime.utcnow(),
            completed_at=None,
            outcome=None
        )

    def _store_action(self, action: Action) -> bool:
        """Store action in database"""
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(self.db_dsn)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO gsc.actions (
                    id, insight_id, property, action_type, title, description,
                    instructions, priority, effort, estimated_impact, status,
                    assigned_to, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                action.id,
                action.insight_id,
                action.property,
                action.action_type,
                action.title,
                action.description,
                psycopg2.extras.Json(action.instructions),
                action.priority,
                action.effort,
                psycopg2.extras.Json(action.estimated_impact),
                action.status,
                action.assigned_to,
                action.created_at
            ))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Error storing action: {e}")
            if conn:
                conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _row_to_action(self, row: Dict) -> Action:
        """Convert database row to Action object"""
        return Action(
            id=row['id'],
            insight_id=row.get('insight_id'),
            property=row['property'],
            action_type=row['action_type'],
            title=row['title'],
            description=row.get('description', ''),
            instructions=row.get('instructions', []),
            priority=row.get('priority', 'medium'),
            effort=row.get('effort', 'medium'),
            estimated_impact=row.get('estimated_impact', {}),
            status=row.get('status', 'pending'),
            assigned_to=row.get('assigned_to'),
            created_at=row.get('created_at', datetime.utcnow()),
            completed_at=row.get('completed_at'),
            outcome=row.get('outcome')
        )
