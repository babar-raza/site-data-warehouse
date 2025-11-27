"""
Tests for services/alert_engine/rule_evaluator.py

Tests cover:
- Threshold rule evaluation (TASKCARD-008 Phase 1)
- All operators: >, <, =, >=, <=, between, not_between
- Alert triggering and deduplication
- Email and webhook dispatch

Dual Mode Testing:
- Mock mode (default): Uses mocked dependencies
- Live mode (TEST_MODE=live): Uses real PostgreSQL
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import os
import sys

from tests.testing_modes import is_mock_mode, is_live_mode, has_postgres


# =============================================================================
# IMPORT WITH CONDITIONAL MOCKING
# =============================================================================

# Mock psycopg2 if not available or in mock mode
if is_mock_mode():
    mock_psycopg2 = MagicMock()
    sys.modules['psycopg2'] = mock_psycopg2
    sys.modules['psycopg2.extras'] = MagicMock()

from services.alert_engine import AlertRuleEvaluator


# =============================================================================
# THRESHOLD RULE EVALUATION TESTS
# =============================================================================

class TestThresholdRuleEvaluation:
    """Tests for threshold-based rule evaluation"""

    def test_greater_than_operator_triggered(self):
        """Test > operator when condition is met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '>', 'threshold': 100}
        }
        metrics = {'gsc_clicks': 150}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_greater_than_operator_not_triggered(self):
        """Test > operator when condition is not met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '>', 'threshold': 100}
        }
        metrics = {'gsc_clicks': 50}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_less_than_operator_triggered(self):
        """Test < operator when condition is met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '<', 'threshold': -30}
        }
        metrics = {'gsc_clicks': -35}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_less_than_operator_not_triggered(self):
        """Test < operator when condition is not met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '<', 'threshold': -30}
        }
        metrics = {'gsc_clicks': -20}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_equals_operator_triggered(self):
        """Test = operator when condition is met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'status_code',
            'condition': {'operator': '=', 'threshold': 500}
        }
        metrics = {'status_code': 500}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_equals_operator_not_triggered(self):
        """Test = operator when condition is not met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'status_code',
            'condition': {'operator': '=', 'threshold': 500}
        }
        metrics = {'status_code': 200}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_greater_equal_operator_triggered(self):
        """Test >= operator when condition is met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'bounce_rate',
            'condition': {'operator': '>=', 'threshold': 0.8}
        }
        metrics = {'bounce_rate': 0.8}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_less_equal_operator_triggered(self):
        """Test <= operator when condition is met"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'score',
            'condition': {'operator': '<=', 'threshold': 50}
        }
        metrics = {'score': 50}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_between_operator_triggered(self):
        """Test between operator when value is in range"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'position',
            'condition': {'operator': 'between', 'threshold': [1, 10]}
        }
        metrics = {'position': 5}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_between_operator_not_triggered(self):
        """Test between operator when value is outside range"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'position',
            'condition': {'operator': 'between', 'threshold': [1, 10]}
        }
        metrics = {'position': 15}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_between_operator_at_boundaries(self):
        """Test between operator at boundary values (inclusive)"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'position',
            'condition': {'operator': 'between', 'threshold': [1, 10]}
        }

        # At lower boundary
        assert evaluator.evaluate_threshold_rule(rule, {'position': 1}) is True
        # At upper boundary
        assert evaluator.evaluate_threshold_rule(rule, {'position': 10}) is True

    def test_not_between_operator_triggered(self):
        """Test not_between operator when value is outside range"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'error_rate',
            'condition': {'operator': 'not_between', 'threshold': [0, 5]}
        }
        metrics = {'error_rate': 10}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_not_equal_operator_triggered(self):
        """Test != operator when values differ"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'status',
            'condition': {'operator': '!=', 'threshold': 200}
        }
        metrics = {'status': 404}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True


class TestThresholdRuleEdgeCases:
    """Tests for edge cases in threshold evaluation"""

    def test_missing_metric_returns_false(self):
        """Test that missing metric returns False"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'nonexistent_metric',
            'condition': {'operator': '>', 'threshold': 100}
        }
        metrics = {'gsc_clicks': 150}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_missing_condition_returns_false(self):
        """Test that missing condition returns False"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks'
        }
        metrics = {'gsc_clicks': 150}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_missing_threshold_returns_false(self):
        """Test that missing threshold returns False"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '>'}
        }
        metrics = {'gsc_clicks': 150}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_unknown_operator_returns_false(self):
        """Test that unknown operator returns False"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'gsc_clicks',
            'condition': {'operator': '~', 'threshold': 100}
        }
        metrics = {'gsc_clicks': 150}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_between_with_invalid_threshold_returns_false(self):
        """Test between operator with non-array threshold"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'position',
            'condition': {'operator': 'between', 'threshold': 5}  # Should be [min, max]
        }
        metrics = {'position': 5}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is False

    def test_float_comparison(self):
        """Test comparison with float values"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'ctr',
            'condition': {'operator': '<', 'threshold': 0.05}
        }
        metrics = {'ctr': 0.03}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True

    def test_negative_values(self):
        """Test comparison with negative values"""
        evaluator = AlertRuleEvaluator()
        rule = {
            'rule_type': 'threshold',
            'metric': 'change_pct',
            'condition': {'operator': '<', 'threshold': -20}
        }
        metrics = {'change_pct': -25}

        result = evaluator.evaluate_threshold_rule(rule, metrics)
        assert result is True


# =============================================================================
# ALERT TRIGGERING TESTS
# =============================================================================

class TestAlertTriggering:
    """Tests for alert triggering functionality"""

    def test_trigger_alert_records_to_database(self):
        """Test that triggered alerts are recorded in database"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'test-rule-001',
            'rule_name': 'Test Rule',
            'rule_type': 'threshold',
            'severity': 'high',
            'action': {'type': 'log'}
        }
        alert_data = {
            'property': 'sc-domain:example.com',
            'title': 'Test Alert',
            'message': 'Test message',
            'metrics': {'clicks': 100}
        }

        with patch.object(evaluator, '_get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ['alert-123']
            mock_conn.return_value.cursor.return_value = mock_cursor

            with patch.object(evaluator, '_is_duplicate_alert', return_value=False):
                alert_id = evaluator.trigger_alert(rule, alert_data)

                # Verify INSERT was called
                mock_cursor.execute.assert_called()
                assert 'INSERT INTO notifications.alert_history' in mock_cursor.execute.call_args[0][0]

    def test_trigger_alert_skips_duplicate(self):
        """Test that duplicate alerts are skipped"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'test-rule-001',
            'rule_name': 'Test Rule',
            'suppression_window_minutes': 60
        }
        alert_data = {'property': 'sc-domain:example.com'}

        with patch.object(evaluator, '_is_duplicate_alert', return_value=True):
            alert_id = evaluator.trigger_alert(rule, alert_data)
            assert alert_id is None


class TestDeduplication:
    """Tests for alert deduplication"""

    def test_is_duplicate_within_window(self):
        """Test duplicate detection within time window"""
        evaluator = AlertRuleEvaluator()

        with patch.object(evaluator, '_get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [1]  # Count = 1 (duplicate exists)
            mock_conn.return_value.cursor.return_value = mock_cursor

            result = evaluator._is_duplicate_alert('rule-123', 'sc-domain:example.com', dedup_window_hours=24)
            assert result is True

    def test_is_not_duplicate_outside_window(self):
        """Test no duplicate outside time window"""
        evaluator = AlertRuleEvaluator()

        with patch.object(evaluator, '_get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [0]  # Count = 0 (no duplicate)
            mock_conn.return_value.cursor.return_value = mock_cursor

            result = evaluator._is_duplicate_alert('rule-123', 'sc-domain:example.com', dedup_window_hours=24)
            assert result is False


# =============================================================================
# ALERT DISPATCH TESTS
# =============================================================================

class TestAlertDispatch:
    """Tests for alert dispatch (email, webhook, slack)"""

    def test_send_webhook_alert(self):
        """Test webhook alert dispatch"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'test-rule-001',
            'rule_name': 'Test Rule',
            'severity': 'high'
        }
        alert_data = {
            'property': 'sc-domain:example.com',
            'title': 'Test Alert',
            'message': 'Test message'
        }

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = evaluator._send_webhook_alert('https://webhook.example.com', rule, alert_data)

            mock_post.assert_called_once()
            assert result is True

    def test_send_webhook_alert_no_url(self):
        """Test webhook alert with no URL returns False"""
        evaluator = AlertRuleEvaluator()

        result = evaluator._send_webhook_alert(None, {}, {})
        assert result is False

    def test_send_slack_alert(self):
        """Test Slack alert dispatch"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'test-rule-001',
            'rule_name': 'Test Rule',
            'severity': 'critical'
        }
        alert_data = {
            'property': 'sc-domain:example.com',
            'title': 'Critical Alert',
            'message': 'Something went wrong'
        }

        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            result = evaluator._send_slack_alert('https://hooks.slack.com/xxx', rule, alert_data)

            mock_post.assert_called_once()
            # Verify Slack payload structure
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'attachments' in payload
            assert result is True

    def test_send_email_alert_no_recipients(self):
        """Test email alert with no recipients returns False"""
        evaluator = AlertRuleEvaluator()

        result = evaluator._send_email_alert([], {}, {})
        assert result is False


# =============================================================================
# BULK EVALUATION TESTS
# =============================================================================

class TestBulkEvaluation:
    """Tests for evaluating multiple rules"""

    def test_evaluate_multiple_rules(self):
        """Test evaluating multiple rules at once"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'rule-1',
                'rule_name': 'Clicks Drop',
                'rule_type': 'threshold',
                'metric': 'gsc_clicks',
                'condition': {'operator': '<', 'threshold': 50}
            },
            {
                'rule_id': 'rule-2',
                'rule_name': 'High Bounce Rate',
                'rule_type': 'threshold',
                'metric': 'bounce_rate',
                'condition': {'operator': '>', 'threshold': 0.8}
            }
        ]
        metrics = {'gsc_clicks': 30, 'bounce_rate': 0.5}

        with patch.object(evaluator, 'trigger_alert', return_value='alert-123'):
            results = evaluator.evaluate_rules(rules, metrics, property='sc-domain:test.com')

            assert len(results) == 2
            # First rule should trigger (30 < 50)
            assert results[0]['triggered'] is True
            # Second rule should not trigger (0.5 is not > 0.8)
            assert results[1]['triggered'] is False

    def test_skip_unsupported_rule_types(self):
        """Test that unsupported rule types are skipped"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'rule-1',
                'rule_name': 'Composite Rule',
                'rule_type': 'composite',  # Not supported
                'metric': 'gsc_clicks'
            },
            {
                'rule_id': 'rule-2',
                'rule_name': 'Threshold Rule',
                'rule_type': 'threshold',
                'metric': 'gsc_clicks',
                'condition': {'operator': '>', 'threshold': 100}
            }
        ]
        metrics = {'gsc_clicks': 150}

        with patch.object(evaluator, 'trigger_alert', return_value='alert-123'):
            results = evaluator.evaluate_rules(rules, metrics)

            # Only threshold rule should be evaluated (composite not supported)
            assert len(results) == 1
            assert results[0]['rule_id'] == 'rule-2'


# =============================================================================
# ANOMALY RULE TESTS (Phase 2)
# =============================================================================

class TestAnomalyRuleEvaluation:
    """Tests for anomaly-based rule evaluation"""

    def test_anomaly_rule_triggers_on_anomaly(self):
        """Test anomaly rule triggers when z-score exceeds threshold"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-001',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'medium'}
        }

        # Historical data with stable values around 100
        # Last value is an extreme anomaly (500)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 102},
            {'date': '2024-01-03', 'gsc_clicks': 98},
            {'date': '2024-01-04', 'gsc_clicks': 101},
            {'date': '2024-01-05', 'gsc_clicks': 99},
            {'date': '2024-01-06', 'gsc_clicks': 500},  # Anomaly!
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        assert result is True

    def test_anomaly_rule_not_triggered_on_normal_data(self):
        """Test anomaly rule doesn't trigger on normal variation"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-002',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'medium'}
        }

        # All values within normal range
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 102},
            {'date': '2024-01-03', 'gsc_clicks': 98},
            {'date': '2024-01-04', 'gsc_clicks': 101},
            {'date': '2024-01-05', 'gsc_clicks': 99},
            {'date': '2024-01-06', 'gsc_clicks': 103},  # Normal variation
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        assert result is False

    def test_anomaly_rule_low_sensitivity(self):
        """Test low sensitivity requires more extreme anomalies"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-003',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'low'}  # z-threshold = 3.0
        }

        # Mean=100, std=7.07, value 118 gives z-score ~2.55 (below 3.0 threshold)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 90},
            {'date': '2024-01-02', 'gsc_clicks': 110},
            {'date': '2024-01-03', 'gsc_clicks': 95},
            {'date': '2024-01-04', 'gsc_clicks': 105},
            {'date': '2024-01-05', 'gsc_clicks': 100},
            {'date': '2024-01-06', 'gsc_clicks': 118},  # z-score ~2.55 (below 3.0 threshold)
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        # Low sensitivity means z-threshold=3.0, value 118 has z-score ~2.55
        assert result is False

    def test_anomaly_rule_high_sensitivity(self):
        """Test high sensitivity triggers on smaller deviations"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-004',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'high'}  # z-threshold = 2.0
        }

        # Data with higher variance - value 125 gives z-score ~2.5
        # Mean ~100, std ~7.9, value=125 gives z-score ~3.1
        # This should trigger with high sensitivity (z-threshold=2.0)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 90},
            {'date': '2024-01-02', 'gsc_clicks': 110},
            {'date': '2024-01-03', 'gsc_clicks': 95},
            {'date': '2024-01-04', 'gsc_clicks': 105},
            {'date': '2024-01-05', 'gsc_clicks': 100},
            {'date': '2024-01-06', 'gsc_clicks': 125},  # z-score ~2.5 (above 2.0 threshold)
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        assert result is True

    def test_anomaly_rule_insufficient_data(self):
        """Test anomaly rule returns False with insufficient data"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-005',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'medium'}
        }

        # Only 2 data points - insufficient
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 500},
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        assert result is False

    def test_anomaly_rule_missing_metric(self):
        """Test anomaly rule returns False when metric not in history"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-006',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'unknown_metric',
            'condition': {'sensitivity': 'medium'}
        }

        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 102},
            {'date': '2024-01-03', 'gsc_clicks': 98},
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        assert result is False

    def test_anomaly_rule_zero_variance(self):
        """Test anomaly rule handles zero variance data"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'anomaly-007',
            'rule_name': 'Click Anomaly',
            'rule_type': 'anomaly',
            'metric': 'gsc_clicks',
            'condition': {'sensitivity': 'medium'}
        }

        # All historical values the same (zero variance)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 100},
            {'date': '2024-01-03', 'gsc_clicks': 100},
            {'date': '2024-01-04', 'gsc_clicks': 100},
            {'date': '2024-01-05', 'gsc_clicks': 150},
        ]

        result = evaluator.evaluate_anomaly_rule(rule, metrics_history)
        # Zero variance in history, can't compute z-score
        assert result is False


class TestAnomalyRuleSensitivity:
    """Tests for sensitivity level mappings"""

    def test_sensitivity_mapping_low(self):
        """Test low sensitivity maps to 0.2"""
        evaluator = AlertRuleEvaluator()
        assert evaluator.SENSITIVITY_LEVELS['low'] == 0.2

    def test_sensitivity_mapping_medium(self):
        """Test medium sensitivity maps to 0.1"""
        evaluator = AlertRuleEvaluator()
        assert evaluator.SENSITIVITY_LEVELS['medium'] == 0.1

    def test_sensitivity_mapping_high(self):
        """Test high sensitivity maps to 0.05"""
        evaluator = AlertRuleEvaluator()
        assert evaluator.SENSITIVITY_LEVELS['high'] == 0.05

    def test_z_threshold_low(self):
        """Test low sensitivity z-threshold is 3.0"""
        evaluator = AlertRuleEvaluator()
        assert evaluator._get_z_threshold('low') == 3.0

    def test_z_threshold_medium(self):
        """Test medium sensitivity z-threshold is 2.5"""
        evaluator = AlertRuleEvaluator()
        assert evaluator._get_z_threshold('medium') == 2.5

    def test_z_threshold_high(self):
        """Test high sensitivity z-threshold is 2.0"""
        evaluator = AlertRuleEvaluator()
        assert evaluator._get_z_threshold('high') == 2.0

    def test_z_threshold_default(self):
        """Test unknown sensitivity defaults to 2.5"""
        evaluator = AlertRuleEvaluator()
        assert evaluator._get_z_threshold('unknown') == 2.5


class TestAnomalyBulkEvaluation:
    """Tests for bulk evaluation with anomaly rules"""

    def test_evaluate_mixed_rules(self):
        """Test evaluating both threshold and anomaly rules together"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'threshold-001',
                'rule_name': 'Click Threshold',
                'rule_type': 'threshold',
                'metric': 'gsc_clicks',
                'condition': {'operator': '<', 'threshold': 50}
            },
            {
                'rule_id': 'anomaly-001',
                'rule_name': 'Click Anomaly',
                'rule_type': 'anomaly',
                'metric': 'gsc_clicks',
                'condition': {'sensitivity': 'medium'}
            }
        ]

        # Current metrics for threshold evaluation
        metrics = {'gsc_clicks': 30}

        # Historical data for anomaly evaluation
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 102},
            {'date': '2024-01-03', 'gsc_clicks': 98},
            {'date': '2024-01-04', 'gsc_clicks': 101},
            {'date': '2024-01-05', 'gsc_clicks': 99},
            {'date': '2024-01-06', 'gsc_clicks': 30},  # Also an anomaly (big drop)
        ]

        with patch.object(evaluator, 'trigger_alert', return_value='alert-123'):
            results = evaluator.evaluate_rules(
                rules, metrics,
                property='sc-domain:test.com',
                metrics_history=metrics_history
            )

            assert len(results) == 2
            # Threshold rule: 30 < 50 = True
            assert results[0]['triggered'] is True
            assert results[0]['rule_type'] == 'threshold'
            # Anomaly rule: 30 is way below mean of ~100 = True
            assert results[1]['triggered'] is True
            assert results[1]['rule_type'] == 'anomaly'

    def test_anomaly_rule_skipped_without_history(self):
        """Test anomaly rules are skipped when no history provided"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'anomaly-001',
                'rule_name': 'Click Anomaly',
                'rule_type': 'anomaly',
                'metric': 'gsc_clicks',
                'condition': {'sensitivity': 'medium'}
            }
        ]

        metrics = {'gsc_clicks': 30}

        # No history provided
        results = evaluator.evaluate_rules(rules, metrics)

        # Anomaly rule should still be evaluated but not triggered
        assert len(results) == 1
        assert results[0]['triggered'] is False


# =============================================================================
# PATTERN RULE TESTS (Phase 3)
# =============================================================================

class TestPatternRuleEvaluation:
    """Tests for pattern-based rule evaluation"""

    def test_consecutive_decline_detected(self):
        """Test consecutive decline pattern detection"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-001',
            'rule_name': 'Click Decline',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_decline', 'duration': 3}
        }

        # Clear declining pattern
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is True

    def test_consecutive_decline_not_detected(self):
        """Test consecutive decline not triggered on non-declining data"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-002',
            'rule_name': 'Click Decline',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_decline', 'duration': 3}
        }

        # Not consistently declining - has an increase
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 95},  # Increase breaks pattern
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_consecutive_growth_detected(self):
        """Test consecutive growth pattern detection"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-003',
            'rule_name': 'Click Growth',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_growth', 'duration': 4}
        }

        # Clear growth pattern
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 110},
            {'date': '2024-01-03', 'gsc_clicks': 120},
            {'date': '2024-01-04', 'gsc_clicks': 130},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is True

    def test_consecutive_growth_not_detected(self):
        """Test consecutive growth not triggered on non-growing data"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-004',
            'rule_name': 'Click Growth',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_growth', 'duration': 3}
        }

        # Not consistently growing
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 110},
            {'date': '2024-01-03', 'gsc_clicks': 105},  # Decrease breaks pattern
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_trend_reversal_decline_to_growth(self):
        """Test trend reversal from decline to growth"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-005',
            'rule_name': 'Trend Reversal',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'trend_reversal', 'duration': 3}
        }

        # Decline followed by growth
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
            {'date': '2024-01-04', 'gsc_clicks': 85},
            {'date': '2024-01-05', 'gsc_clicks': 95},
            {'date': '2024-01-06', 'gsc_clicks': 110},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is True

    def test_trend_reversal_growth_to_decline(self):
        """Test trend reversal from growth to decline"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-006',
            'rule_name': 'Trend Reversal',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'trend_reversal', 'duration': 3}
        }

        # Growth followed by decline
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 80},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 100},
            {'date': '2024-01-04', 'gsc_clicks': 95},
            {'date': '2024-01-05', 'gsc_clicks': 85},
            {'date': '2024-01-06', 'gsc_clicks': 75},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is True

    def test_trend_reversal_no_reversal(self):
        """Test trend reversal not triggered when no reversal"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-007',
            'rule_name': 'Trend Reversal',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'trend_reversal', 'duration': 3}
        }

        # Consistent growth - no reversal
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 80},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 100},
            {'date': '2024-01-04', 'gsc_clicks': 110},
            {'date': '2024-01-05', 'gsc_clicks': 120},
            {'date': '2024-01-06', 'gsc_clicks': 130},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False


class TestPatternRuleEdgeCases:
    """Tests for pattern rule edge cases"""

    def test_pattern_rule_missing_metric(self):
        """Test pattern rule returns False when metric missing"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-001',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'condition': {'pattern': 'consecutive_decline', 'duration': 3}
        }

        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_pattern_rule_missing_pattern_type(self):
        """Test pattern rule returns False when pattern type missing"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-002',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'duration': 3}  # Missing pattern
        }

        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_pattern_rule_unsupported_pattern(self):
        """Test pattern rule returns False for unsupported pattern"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-003',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'unknown_pattern', 'duration': 3}
        }

        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_pattern_rule_insufficient_data(self):
        """Test pattern rule returns False with insufficient data"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-004',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_decline', 'duration': 5}
        }

        # Only 3 data points, need 5
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False

    def test_pattern_rule_default_duration(self):
        """Test pattern rule uses default duration of 3"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-005',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_decline'}  # No duration specified
        }

        # Exactly 3 declining values (default duration)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 90},
            {'date': '2024-01-03', 'gsc_clicks': 80},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is True

    def test_pattern_rule_flat_values(self):
        """Test pattern rule returns False for flat/stable values"""
        evaluator = AlertRuleEvaluator()

        rule = {
            'rule_id': 'pattern-edge-006',
            'rule_name': 'Test',
            'rule_type': 'pattern',
            'metric': 'gsc_clicks',
            'condition': {'pattern': 'consecutive_decline', 'duration': 3}
        }

        # Same values - not a decline
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 100},
            {'date': '2024-01-03', 'gsc_clicks': 100},
        ]

        result = evaluator.evaluate_pattern_rule(rule, metrics_history)
        assert result is False


class TestPatternBulkEvaluation:
    """Tests for bulk evaluation with pattern rules"""

    def test_evaluate_all_three_phases(self):
        """Test evaluating threshold, anomaly, and pattern rules together"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'threshold-001',
                'rule_name': 'Click Threshold',
                'rule_type': 'threshold',
                'metric': 'gsc_clicks',
                'condition': {'operator': '<', 'threshold': 50}
            },
            {
                'rule_id': 'anomaly-001',
                'rule_name': 'Click Anomaly',
                'rule_type': 'anomaly',
                'metric': 'gsc_clicks',
                'condition': {'sensitivity': 'high'}  # High sensitivity (z-threshold=2.0)
            },
            {
                'rule_id': 'pattern-001',
                'rule_name': 'Click Decline',
                'rule_type': 'pattern',
                'metric': 'gsc_clicks',
                'condition': {'pattern': 'consecutive_decline', 'duration': 3}
            }
        ]

        # Current metrics for threshold
        metrics = {'gsc_clicks': 30}

        # Historical data: stable baseline (~100) then sudden drop to 30
        # Mean of first 5 values = 100, std ~1.4, value 30 gives z-score ~50 (>>2.0)
        metrics_history = [
            {'date': '2024-01-01', 'gsc_clicks': 100},
            {'date': '2024-01-02', 'gsc_clicks': 102},
            {'date': '2024-01-03', 'gsc_clicks': 98},
            {'date': '2024-01-04', 'gsc_clicks': 101},
            {'date': '2024-01-05', 'gsc_clicks': 99},
            {'date': '2024-01-06', 'gsc_clicks': 30},  # Clear anomaly - z-score ~50
        ]

        with patch.object(evaluator, 'trigger_alert', return_value='alert-123'):
            results = evaluator.evaluate_rules(
                rules, metrics,
                property='sc-domain:test.com',
                metrics_history=metrics_history
            )

            assert len(results) == 3
            # Threshold: 30 < 50 = True
            assert results[0]['triggered'] is True
            assert results[0]['rule_type'] == 'threshold'
            # Anomaly: 30 is way below mean 100 with z-score ~50 = True
            assert results[1]['triggered'] is True
            assert results[1]['rule_type'] == 'anomaly'
            # Pattern: Last 3 values [101, 99, 30] - 99 < 101 and 30 < 99 = True
            assert results[2]['triggered'] is True
            assert results[2]['rule_type'] == 'pattern'

    def test_pattern_rule_skipped_without_history(self):
        """Test pattern rules are skipped when no history provided"""
        evaluator = AlertRuleEvaluator()

        rules = [
            {
                'rule_id': 'pattern-001',
                'rule_name': 'Click Decline',
                'rule_type': 'pattern',
                'metric': 'gsc_clicks',
                'condition': {'pattern': 'consecutive_decline', 'duration': 3}
            }
        ]

        metrics = {'gsc_clicks': 30}

        # No history provided
        results = evaluator.evaluate_rules(rules, metrics)

        # Pattern rule should still be evaluated but not triggered
        assert len(results) == 1
        assert results[0]['triggered'] is False


class TestPatternTypes:
    """Tests for supported pattern types constant"""

    def test_pattern_types_constant(self):
        """Test PATTERN_TYPES constant has expected values"""
        evaluator = AlertRuleEvaluator()
        assert 'consecutive_decline' in evaluator.PATTERN_TYPES
        assert 'consecutive_growth' in evaluator.PATTERN_TYPES
        assert 'trend_reversal' in evaluator.PATTERN_TYPES
        assert len(evaluator.PATTERN_TYPES) == 3


# =============================================================================
# LIVE MODE TESTS
# =============================================================================

class TestAlertEngineLive:
    """Live mode tests for alert engine - requires PostgreSQL"""

    def test_fetch_current_metrics(self):
        """Test fetching current metrics from database"""
        if is_live_mode() and has_postgres():
            import psycopg2
            evaluator = AlertRuleEvaluator()

            # This will use real database
            metrics = evaluator.fetch_current_metrics('sc-domain:example.com')
            assert isinstance(metrics, dict)
        else:
            # Mock mode
            evaluator = AlertRuleEvaluator()

            with patch.object(evaluator, '_get_connection') as mock_conn:
                mock_cursor = MagicMock()
                mock_cursor.fetchone.return_value = {
                    'gsc_clicks': 100,
                    'gsc_impressions': 1000,
                    'gsc_ctr': 0.1
                }
                mock_conn.return_value.cursor.return_value = mock_cursor

                metrics = evaluator.fetch_current_metrics('sc-domain:example.com')
                assert isinstance(metrics, dict)
