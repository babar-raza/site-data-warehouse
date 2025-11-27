"""
Action Generator Service

Generates actionable tasks from insights.
"""
from services.action_generator.generator import ActionGenerator
from services.action_generator.templates import ActionTemplates

__all__ = ["ActionGenerator", "ActionTemplates"]
