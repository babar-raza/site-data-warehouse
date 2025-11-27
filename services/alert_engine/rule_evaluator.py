"""
Alert Rule Evaluator - Multi-type Rule Evaluation Engine
=========================================================
Phase 1: Threshold rules with operators: >, <, =, >=, <=, between
Phase 2: Anomaly rules using AnomalyDetector with sensitivity levels
Phase 3: Pattern rules for consecutive trends and reversals

Features:
- Evaluate threshold-based rules against current metrics
- Evaluate anomaly-based rules using statistical/ML methods
- Evaluate pattern-based rules for trend detection
- Deduplication (prevents re-alerting within configurable window)
- Alert triggering with email and webhook dispatch
- Database recording of triggered alerts
"""
import logging
import os
from datetime import datetime, timedelta, UTC
from typing import Any, Dict, List, Optional, Union
import json

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class AlertRuleEvaluator:
    """
    Evaluates alert rules against current metrics and triggers alerts.

    Phase 1: Threshold-based rules
    Operators: >, <, =, >=, <=, between, not_between

    Phase 2: Anomaly-based rules
    Uses AnomalyDetector with sensitivity levels: low, medium, high

    Phase 3: Pattern-based rules
    Patterns: consecutive_decline, consecutive_growth, trend_reversal
    """

    # Default deduplication window (24 hours)
    DEFAULT_DEDUP_WINDOW_HOURS = 24

    # Sensitivity level mapping (lower value = more sensitive)
    SENSITIVITY_LEVELS = {
        'low': 0.2,      # Less sensitive, fewer alerts
        'medium': 0.1,   # Balanced sensitivity
        'high': 0.05     # Most sensitive, more alerts
    }

    # Supported pattern types
    PATTERN_TYPES = ['consecutive_decline', 'consecutive_growth', 'trend_reversal']

    def __init__(self, db_dsn: str = None):
        """
        Initialize AlertRuleEvaluator.

        Args:
            db_dsn: Database connection string (defaults to WAREHOUSE_DSN env var)
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        logger.info("AlertRuleEvaluator initialized")

    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_dsn)

    # =========================================================================
    # THRESHOLD RULE EVALUATION
    # =========================================================================

    def evaluate_threshold_rule(
        self,
        rule: Dict,
        current_metrics: Dict
    ) -> bool:
        """
        Evaluate a threshold-based rule against current metrics.

        Args:
            rule: Rule definition with 'metric' and 'condition' keys
                  condition: {'operator': '>', 'threshold': 100}
                  For 'between': {'operator': 'between', 'threshold': [min, max]}
            current_metrics: Dict of current metric values

        Returns:
            True if rule condition is met (alert should trigger), False otherwise
        """
        metric_name = rule.get('metric')
        condition = rule.get('condition', {})

        if not metric_name or not condition:
            logger.warning(f"Invalid rule: missing metric or condition")
            return False

        current_value = current_metrics.get(metric_name)

        if current_value is None:
            logger.debug(f"Metric '{metric_name}' not found in current metrics")
            return False

        threshold = condition.get('threshold')
        operator = condition.get('operator', '>')

        if threshold is None:
            logger.warning(f"Invalid condition: missing threshold")
            return False

        return self._compare_values(current_value, operator, threshold)

    def _compare_values(
        self,
        current_value: Union[int, float],
        operator: str,
        threshold: Union[int, float, List]
    ) -> bool:
        """
        Compare current value against threshold using operator.

        Args:
            current_value: The current metric value
            operator: Comparison operator (>, <, =, >=, <=, between, not_between)
            threshold: Threshold value(s) - single value or [min, max] for between

        Returns:
            True if comparison matches
        """
        try:
            if operator == '>':
                return current_value > threshold
            elif operator == '<':
                return current_value < threshold
            elif operator == '=' or operator == '==':
                return current_value == threshold
            elif operator == '>=':
                return current_value >= threshold
            elif operator == '<=':
                return current_value <= threshold
            elif operator == '!=' or operator == '<>':
                return current_value != threshold
            elif operator == 'between':
                if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
                    logger.warning(f"'between' operator requires [min, max] threshold")
                    return False
                return threshold[0] <= current_value <= threshold[1]
            elif operator == 'not_between':
                if not isinstance(threshold, (list, tuple)) or len(threshold) != 2:
                    logger.warning(f"'not_between' operator requires [min, max] threshold")
                    return False
                return current_value < threshold[0] or current_value > threshold[1]
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except (TypeError, ValueError) as e:
            logger.error(f"Error comparing values: {e}")
            return False

    # =========================================================================
    # ANOMALY RULE EVALUATION (Phase 2)
    # =========================================================================

    def evaluate_anomaly_rule(
        self,
        rule: Dict,
        metrics_history: List[Dict]
    ) -> bool:
        """
        Evaluate an anomaly-based rule against historical metrics.

        Uses AnomalyDetector's statistical methods (Z-score, IQR) to detect
        whether the most recent metric value is anomalous compared to history.

        Args:
            rule: Rule definition with 'metric' and 'condition' keys
                  condition: {'sensitivity': 'low|medium|high'}
            metrics_history: List of historical metric dicts with 'date' and metric values

        Returns:
            True if anomaly detected (alert should trigger), False otherwise
        """
        metric_name = rule.get('metric')
        condition = rule.get('condition', {})

        if not metric_name:
            logger.warning("Invalid anomaly rule: missing metric")
            return False

        if not metrics_history or len(metrics_history) < 3:
            logger.debug(f"Insufficient history for anomaly detection (need at least 3 points)")
            return False

        # Get sensitivity level
        sensitivity_name = condition.get('sensitivity', 'medium')
        sensitivity = self.SENSITIVITY_LEVELS.get(sensitivity_name, 0.1)

        # Z-score threshold based on sensitivity (inverse relationship)
        z_threshold = self._get_z_threshold(sensitivity_name)

        try:
            # Extract metric values from history
            values = []
            for entry in metrics_history:
                val = entry.get(metric_name)
                if val is not None:
                    values.append(float(val))

            if len(values) < 3:
                logger.debug(f"Insufficient data points for metric '{metric_name}'")
                return False

            # Get latest value (to check if anomalous)
            latest_value = values[-1]
            historical_values = values[:-1]

            # Calculate Z-score
            import numpy as np
            mean = np.mean(historical_values)
            std = np.std(historical_values)

            if std == 0:
                logger.debug(f"No variance in historical data for '{metric_name}'")
                return False

            z_score = abs(latest_value - mean) / std

            # Check if anomaly
            is_anomaly = z_score > z_threshold

            if is_anomaly:
                logger.info(
                    f"Anomaly detected: {metric_name}={latest_value}, "
                    f"mean={mean:.2f}, z-score={z_score:.2f}, threshold={z_threshold}"
                )

            return bool(is_anomaly)

        except Exception as e:
            logger.error(f"Error evaluating anomaly rule: {e}")
            return False

    def _get_z_threshold(self, sensitivity: str) -> float:
        """
        Get Z-score threshold based on sensitivity level.

        Lower sensitivity = higher threshold (fewer alerts)
        Higher sensitivity = lower threshold (more alerts)

        Args:
            sensitivity: 'low', 'medium', or 'high'

        Returns:
            Z-score threshold
        """
        thresholds = {
            'low': 3.0,      # Only extreme outliers
            'medium': 2.5,   # Balanced
            'high': 2.0      # More sensitive
        }
        return thresholds.get(sensitivity, 2.5)

    def fetch_metrics_history(
        self,
        property: str,
        page_path: str = None,
        lookback_days: int = 30
    ) -> List[Dict]:
        """
        Fetch historical metrics for anomaly detection.

        Args:
            property: Property URL
            page_path: Optional page path filter
            lookback_days: Days of history to fetch

        Returns:
            List of dicts with date and metric values
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT
                    date,
                    SUM(gsc_clicks) as gsc_clicks,
                    SUM(gsc_impressions) as gsc_impressions,
                    AVG(gsc_ctr) as gsc_ctr,
                    AVG(gsc_position) as gsc_position,
                    SUM(ga4_sessions) as ga4_sessions,
                    SUM(ga4_page_views) as ga4_page_views,
                    AVG(ga4_bounce_rate) as ga4_bounce_rate
                FROM gsc.vw_unified_page_performance
                WHERE property = %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
            """
            params = [property, lookback_days]

            if page_path:
                query = query.replace(
                    "AND date >=",
                    "AND page_path = %s AND date >="
                )
                params.insert(1, page_path)

            query += " GROUP BY date ORDER BY date ASC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            # Convert to list of dicts
            return [dict(row) for row in rows] if rows else []

        except Exception as e:
            logger.error(f"Error fetching metrics history: {e}")
            return []

    # =========================================================================
    # PATTERN RULE EVALUATION (Phase 3)
    # =========================================================================

    def evaluate_pattern_rule(
        self,
        rule: Dict,
        metrics_history: List[Dict]
    ) -> bool:
        """
        Evaluate a pattern-based rule against historical metrics.

        Detects temporal patterns like consecutive decline, growth, or reversals.

        Args:
            rule: Rule definition with 'metric' and 'condition' keys
                  condition: {
                      'pattern': 'consecutive_decline|consecutive_growth|trend_reversal',
                      'duration': 3  # Number of consecutive periods
                  }
            metrics_history: List of historical metric dicts with 'date' and metric values

        Returns:
            True if pattern detected (alert should trigger), False otherwise
        """
        metric_name = rule.get('metric')
        condition = rule.get('condition', {})
        pattern_type = condition.get('pattern')
        duration = condition.get('duration', 3)

        if not metric_name:
            logger.warning("Invalid pattern rule: missing metric")
            return False

        if not pattern_type:
            logger.warning("Invalid pattern rule: missing pattern type")
            return False

        if pattern_type not in self.PATTERN_TYPES:
            logger.warning(f"Unsupported pattern type: {pattern_type}")
            return False

        if not metrics_history or len(metrics_history) < duration:
            logger.debug(f"Insufficient history for pattern detection (need at least {duration} points)")
            return False

        try:
            # Extract metric values from history (most recent 'duration' entries)
            values = []
            for entry in metrics_history:
                val = entry.get(metric_name)
                if val is not None:
                    values.append(float(val))

            if len(values) < duration:
                logger.debug(f"Insufficient data points for metric '{metric_name}'")
                return False

            # Get the last 'duration' values for pattern analysis
            recent_values = values[-duration:]

            # Evaluate the specific pattern
            if pattern_type == 'consecutive_decline':
                return self._detect_consecutive_decline(recent_values)
            elif pattern_type == 'consecutive_growth':
                return self._detect_consecutive_growth(recent_values)
            elif pattern_type == 'trend_reversal':
                # Need more data for reversal detection
                if len(values) < duration + 2:
                    logger.debug("Insufficient data for trend reversal detection")
                    return False
                return self._detect_trend_reversal(values, duration)
            else:
                return False

        except Exception as e:
            logger.error(f"Error evaluating pattern rule: {e}")
            return False

    def _detect_consecutive_decline(self, values: List[float]) -> bool:
        """
        Detect consecutive declining values.

        Args:
            values: List of metric values (ordered oldest to newest)

        Returns:
            True if each value is less than the previous one
        """
        if len(values) < 2:
            return False

        for i in range(1, len(values)):
            if values[i] >= values[i - 1]:
                return False

        logger.info(f"Consecutive decline detected: {values}")
        return True

    def _detect_consecutive_growth(self, values: List[float]) -> bool:
        """
        Detect consecutive growing values.

        Args:
            values: List of metric values (ordered oldest to newest)

        Returns:
            True if each value is greater than the previous one
        """
        if len(values) < 2:
            return False

        for i in range(1, len(values)):
            if values[i] <= values[i - 1]:
                return False

        logger.info(f"Consecutive growth detected: {values}")
        return True

    def _detect_trend_reversal(self, values: List[float], duration: int) -> bool:
        """
        Detect a trend reversal (change from decline to growth or vice versa).

        Args:
            values: List of metric values (ordered oldest to newest)
            duration: Number of periods to consider for each trend

        Returns:
            True if a reversal is detected
        """
        if len(values) < duration + 2:
            return False

        # Split into previous trend and recent trend
        # Previous trend: values before the most recent 'duration' values
        # Recent trend: the most recent 'duration' values
        prev_end = len(values) - duration
        prev_values = values[max(0, prev_end - duration):prev_end]
        recent_values = values[-duration:]

        if len(prev_values) < 2 or len(recent_values) < 2:
            return False

        # Calculate trend direction
        prev_trend = self._calculate_trend(prev_values)
        recent_trend = self._calculate_trend(recent_values)

        # Reversal is when trend direction changes
        if prev_trend == 'decline' and recent_trend == 'growth':
            logger.info(f"Trend reversal detected: decline -> growth")
            return True
        elif prev_trend == 'growth' and recent_trend == 'decline':
            logger.info(f"Trend reversal detected: growth -> decline")
            return True

        return False

    def _calculate_trend(self, values: List[float]) -> str:
        """
        Calculate the overall trend direction of values.

        Args:
            values: List of metric values

        Returns:
            'growth', 'decline', or 'stable'
        """
        if len(values) < 2:
            return 'stable'

        # Simple linear trend: compare first and last values
        first = values[0]
        last = values[-1]

        # Also check if consistently increasing/decreasing
        increases = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
        decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])

        # Determine trend based on overall change and consistency
        if last > first and increases > decreases:
            return 'growth'
        elif last < first and decreases > increases:
            return 'decline'
        else:
            return 'stable'

    # =========================================================================
    # DEDUPLICATION
    # =========================================================================

    def _is_duplicate_alert(
        self,
        rule_id: str,
        property: str = None,
        page_path: str = None,
        dedup_window_hours: int = None
    ) -> bool:
        """
        Check if an alert was recently triggered for this rule.

        Args:
            rule_id: Rule ID to check
            property: Property URL (optional)
            page_path: Page path (optional)
            dedup_window_hours: Hours to look back (default: 24)

        Returns:
            True if duplicate (alert exists within window), False otherwise
        """
        if dedup_window_hours is None:
            dedup_window_hours = self.DEFAULT_DEDUP_WINDOW_HOURS

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT COUNT(*) FROM notifications.alert_history
                WHERE rule_id = %s
                  AND triggered_at > NOW() - INTERVAL '%s hours'
                  AND status NOT IN ('resolved', 'false_positive')
            """
            params = [rule_id, dedup_window_hours]

            if property:
                query = query.replace(
                    "AND status NOT IN",
                    "AND property = %s AND status NOT IN"
                )
                params.insert(2, property)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            if count > 0:
                logger.debug(f"Duplicate alert found for rule {rule_id} within {dedup_window_hours}h")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking duplicate alert: {e}")
            return False  # Allow alert if check fails

    # =========================================================================
    # ALERT TRIGGERING
    # =========================================================================

    def trigger_alert(
        self,
        rule: Dict,
        alert_data: Dict,
        skip_dedup: bool = False
    ) -> Optional[str]:
        """
        Trigger an alert and record in database.

        Args:
            rule: Rule definition including rule_id, action, etc.
            alert_data: Alert context (property, page_path, metrics, message)
            skip_dedup: Skip deduplication check (default: False)

        Returns:
            alert_id if triggered, None if skipped/failed
        """
        rule_id = rule.get('rule_id')
        property = alert_data.get('property')
        page_path = alert_data.get('page_path')

        # Check deduplication
        if not skip_dedup:
            dedup_window = rule.get('suppression_window_minutes', self.DEFAULT_DEDUP_WINDOW_HOURS * 60) // 60
            if self._is_duplicate_alert(rule_id, property, page_path, dedup_window):
                logger.info(f"Skipping duplicate alert for rule {rule_id}")
                return None

        # Dispatch via configured channels
        action = rule.get('action', {})
        action_type = action.get('type', 'log')

        if action_type == 'email':
            self._send_email_alert(action.get('recipients', []), rule, alert_data)
        elif action_type == 'webhook':
            self._send_webhook_alert(action.get('url'), rule, alert_data)
        elif action_type == 'slack':
            self._send_slack_alert(action.get('webhook_url'), rule, alert_data)

        # Record alert in database
        alert_id = self._record_alert(rule, alert_data)

        if alert_id:
            logger.info(f"Triggered alert {alert_id} for rule {rule_id}")

        return alert_id

    def _record_alert(self, rule: Dict, alert_data: Dict) -> Optional[str]:
        """
        Record triggered alert in database.

        Args:
            rule: Rule definition
            alert_data: Alert context

        Returns:
            alert_id if recorded, None if failed
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO notifications.alert_history (
                    rule_id, rule_name, rule_type, severity,
                    property, page_path, title, message, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING alert_id
            """, (
                rule.get('rule_id'),
                rule.get('rule_name', 'Threshold Alert'),
                rule.get('rule_type', 'threshold'),
                rule.get('severity', 'medium'),
                alert_data.get('property'),
                alert_data.get('page_path'),
                alert_data.get('title', f"Alert: {rule.get('rule_name', 'Threshold exceeded')}"),
                alert_data.get('message', 'Threshold condition met'),
                json.dumps(alert_data.get('metadata', {}))
            ))

            alert_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()

            return str(alert_id)

        except Exception as e:
            logger.error(f"Error recording alert: {e}")
            return None

    # =========================================================================
    # ALERT DISPATCH (Email, Webhook, Slack)
    # =========================================================================

    def _send_email_alert(
        self,
        recipients: List[str],
        rule: Dict,
        alert_data: Dict
    ) -> bool:
        """Send alert via email."""
        if not recipients:
            logger.warning("No email recipients configured")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = os.getenv('SMTP_HOST', 'localhost')
            smtp_port = int(os.getenv('SMTP_PORT', 587))
            smtp_user = os.getenv('SMTP_USER')
            smtp_pass = os.getenv('SMTP_PASS')
            from_email = os.getenv('ALERT_FROM_EMAIL', 'alerts@example.com')

            subject = f"[{rule.get('severity', 'ALERT').upper()}] {alert_data.get('title', 'Alert Triggered')}"
            body = self._format_email_body(rule, alert_data)

            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.sendmail(from_email, recipients, msg.as_string())

            logger.info(f"Email alert sent to {recipients}")
            return True

        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
            return False

    def _send_webhook_alert(
        self,
        url: str,
        rule: Dict,
        alert_data: Dict
    ) -> bool:
        """Send alert via webhook."""
        if not url:
            logger.warning("No webhook URL configured")
            return False

        try:
            import requests

            payload = {
                'alert_type': rule.get('rule_type', 'threshold'),
                'rule_id': rule.get('rule_id'),
                'rule_name': rule.get('rule_name'),
                'severity': rule.get('severity'),
                'property': alert_data.get('property'),
                'page_path': alert_data.get('page_path'),
                'title': alert_data.get('title'),
                'message': alert_data.get('message'),
                'metrics': alert_data.get('metrics', {}),
                'triggered_at': datetime.now(UTC).isoformat()
            }

            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()

            logger.info(f"Webhook alert sent to {url}")
            return True

        except Exception as e:
            logger.error(f"Error sending webhook alert: {e}")
            return False

    def _send_slack_alert(
        self,
        webhook_url: str,
        rule: Dict,
        alert_data: Dict
    ) -> bool:
        """Send alert via Slack webhook."""
        if not webhook_url:
            logger.warning("No Slack webhook URL configured")
            return False

        try:
            import requests

            severity = rule.get('severity', 'medium')
            color = {
                'critical': '#FF0000',
                'high': '#FF6600',
                'medium': '#FFCC00',
                'low': '#00CC00'
            }.get(severity, '#CCCCCC')

            payload = {
                'attachments': [{
                    'color': color,
                    'title': alert_data.get('title', 'Alert Triggered'),
                    'text': alert_data.get('message', 'Threshold condition met'),
                    'fields': [
                        {'title': 'Rule', 'value': rule.get('rule_name'), 'short': True},
                        {'title': 'Severity', 'value': severity.upper(), 'short': True},
                        {'title': 'Property', 'value': alert_data.get('property', 'N/A'), 'short': True},
                        {'title': 'Triggered At', 'value': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'), 'short': True}
                    ],
                    'footer': 'Alert Engine',
                    'ts': int(datetime.now(UTC).timestamp())
                }]
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()

            logger.info(f"Slack alert sent")
            return True

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            return False

    def _format_email_body(self, rule: Dict, alert_data: Dict) -> str:
        """Format email body for alert."""
        return f"""
Alert Triggered
===============

Rule: {rule.get('rule_name', 'Unknown')}
Type: {rule.get('rule_type', 'threshold')}
Severity: {rule.get('severity', 'medium').upper()}

Property: {alert_data.get('property', 'N/A')}
Page: {alert_data.get('page_path', 'N/A')}

Message:
{alert_data.get('message', 'Threshold condition met')}

Metrics:
{json.dumps(alert_data.get('metrics', {}), indent=2)}

Triggered At: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}

---
Alert Engine
"""

    # =========================================================================
    # BULK EVALUATION
    # =========================================================================

    def evaluate_rules(
        self,
        rules: List[Dict],
        metrics: Dict,
        property: str = None,
        metrics_history: List[Dict] = None
    ) -> List[Dict]:
        """
        Evaluate multiple rules against metrics.

        Args:
            rules: List of rule definitions
            metrics: Current metrics dict
            property: Property URL for context
            metrics_history: Historical metrics for anomaly detection (optional)

        Returns:
            List of evaluation results
        """
        results = []

        for rule in rules:
            rule_type = rule.get('rule_type', 'threshold')
            triggered = False

            if rule_type == 'threshold':
                triggered = self.evaluate_threshold_rule(rule, metrics)
            elif rule_type == 'anomaly':
                # Phase 2: Anomaly rules
                if metrics_history:
                    triggered = self.evaluate_anomaly_rule(rule, metrics_history)
                else:
                    logger.debug(f"Skipping anomaly rule {rule.get('rule_id')}: no history provided")
            elif rule_type == 'pattern':
                # Phase 3: Pattern rules
                if metrics_history:
                    triggered = self.evaluate_pattern_rule(rule, metrics_history)
                else:
                    logger.debug(f"Skipping pattern rule {rule.get('rule_id')}: no history provided")
            else:
                logger.debug(f"Skipping unsupported rule type: {rule_type}")
                continue

            result = {
                'rule_id': rule.get('rule_id'),
                'rule_name': rule.get('rule_name'),
                'rule_type': rule_type,
                'triggered': triggered,
                'property': property
            }

            if triggered:
                alert_data = {
                    'property': property,
                    'title': f"{rule_type.capitalize()} Alert: {rule.get('rule_name')}",
                    'message': self._generate_alert_message(rule, metrics, metrics_history),
                    'metrics': metrics
                }
                alert_id = self.trigger_alert(rule, alert_data)
                result['alert_id'] = alert_id

            results.append(result)

        return results

    def _generate_alert_message(
        self,
        rule: Dict,
        metrics: Dict,
        metrics_history: List[Dict] = None
    ) -> str:
        """Generate alert message from rule and metrics."""
        metric = rule.get('metric', 'unknown')
        condition = rule.get('condition', {})
        rule_type = rule.get('rule_type', 'threshold')

        if rule_type == 'threshold':
            current_value = metrics.get(metric, 'N/A')
            return (
                f"Metric '{metric}' value {current_value} "
                f"{condition.get('operator', '?')} {condition.get('threshold', '?')}"
            )
        elif rule_type == 'anomaly':
            # Get latest value and stats for anomaly message
            if metrics_history and len(metrics_history) >= 3:
                import numpy as np
                values = [entry.get(metric) for entry in metrics_history if entry.get(metric) is not None]
                if len(values) >= 3:
                    latest = values[-1]
                    mean = np.mean(values[:-1])
                    std = np.std(values[:-1])
                    if std > 0:
                        z_score = abs(latest - mean) / std
                        return (
                            f"Anomaly detected in '{metric}': value {latest:.2f} "
                            f"(mean={mean:.2f}, z-score={z_score:.2f}, sensitivity={condition.get('sensitivity', 'medium')})"
                        )
            return f"Anomaly detected in metric '{metric}'"
        elif rule_type == 'pattern':
            # Get pattern details for message
            pattern = condition.get('pattern', 'unknown')
            duration = condition.get('duration', 3)
            if metrics_history:
                values = [entry.get(metric) for entry in metrics_history if entry.get(metric) is not None]
                if len(values) >= duration:
                    recent = values[-duration:]
                    return (
                        f"Pattern '{pattern}' detected in '{metric}' over {duration} periods: "
                        f"values={[round(v, 2) for v in recent]}"
                    )
            return f"Pattern '{pattern}' detected in metric '{metric}'"
        else:
            return f"Alert triggered for metric '{metric}'"

    # =========================================================================
    # METRICS FETCHING
    # =========================================================================

    def fetch_current_metrics(self, property: str, page_path: str = None) -> Dict:
        """
        Fetch current metrics from database for evaluation.

        Args:
            property: Property URL
            page_path: Optional page path filter

        Returns:
            Dict of current metric values
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Fetch recent metrics from unified view
            query = """
                SELECT
                    AVG(gsc_clicks) as gsc_clicks,
                    AVG(gsc_impressions) as gsc_impressions,
                    AVG(gsc_ctr) as gsc_ctr,
                    AVG(gsc_position) as gsc_position,
                    AVG(ga4_sessions) as ga4_sessions,
                    AVG(ga4_page_views) as ga4_page_views,
                    AVG(ga4_bounce_rate) as ga4_bounce_rate
                FROM gsc.vw_unified_page_performance
                WHERE property = %s
                  AND date >= CURRENT_DATE - INTERVAL '7 days'
            """
            params = [property]

            if page_path:
                query = query.replace(
                    "AND date >=",
                    "AND page_path = %s AND date >="
                )
                params.insert(1, page_path)

            cursor.execute(query, params)
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                # Convert to dict with non-None values
                return {k: v for k, v in dict(row).items() if v is not None}

            return {}

        except Exception as e:
            logger.error(f"Error fetching metrics: {e}")
            return {}
