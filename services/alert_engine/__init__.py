"""
Alert Engine - Rule Evaluation and Alert Triggering
====================================================
Phase 1: Threshold-based rules (>, <, =, between operators)

Usage:
    from services.alert_engine import AlertRuleEvaluator

    evaluator = AlertRuleEvaluator()
    rule = {'rule_type': 'threshold', 'metric': 'gsc_clicks', 'condition': {'operator': '<', 'threshold': -30}}
    triggered = evaluator.evaluate_threshold_rule(rule, {'gsc_clicks': -35})
"""

from services.alert_engine.rule_evaluator import AlertRuleEvaluator

__all__ = ['AlertRuleEvaluator']
