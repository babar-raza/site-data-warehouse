"""
Example Usage of Action Generator Service

This script demonstrates how to use the ActionGenerator service
to create actionable tasks from insights.
"""
import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.action_generator import ActionGenerator, ActionTemplates


def example_basic_usage():
    """Basic usage example"""
    print("\n=== Basic Usage ===\n")

    # Initialize generator
    generator = ActionGenerator()
    print("ActionGenerator initialized")

    # Generate action from a single insight
    # In real usage, you'd get this ID from your database
    insight_id = "550e8400-e29b-41d4-a716-446655440000"
    print(f"Generating action for insight: {insight_id}")

    # Note: This requires a database connection and existing insight
    # action = generator.generate_from_insight(insight_id)
    # if action:
    #     print(f"Created action: {action.title}")
    #     print(f"Priority: {action.priority}")
    #     print(f"Effort: {action.effort}")
    #     print(f"Instructions: {len(action.instructions)} steps")


def example_batch_generation():
    """Batch generation example"""
    print("\n=== Batch Generation ===\n")

    generator = ActionGenerator()

    # Generate actions for all insights in a property
    property_name = "sc-domain:example.com"
    print(f"Generating actions for property: {property_name}")

    # Note: This requires database connection
    # actions = generator.generate_batch(property_name, limit=10)
    # print(f"Generated {len(actions)} actions")
    #
    # # Prioritize the actions
    # prioritized = generator.prioritize_actions(actions)
    # print("\nTop 3 prioritized actions:")
    # for i, action in enumerate(prioritized[:3], 1):
    #     print(f"{i}. {action.title} (Priority: {action.priority}, Effort: {action.effort})")


def example_template_exploration():
    """Explore available templates"""
    print("\n=== Template Exploration ===\n")

    templates = ActionTemplates()

    # List all templates
    template_names = templates.list_templates()
    print(f"Available templates: {len(template_names)}")

    # Show a few examples
    print("\nSample templates:")
    for name in ['seo_title_fix', 'content_expansion', 'page_speed_optimization']:
        template = templates.get_template(name)
        print(f"\n{name}:")
        print(f"  Type: {template['action_type']}")
        print(f"  Effort: {template['effort']}")
        print(f"  Steps: {len(template['instructions'])}")

    # Get templates by type
    content_templates = templates.get_templates_by_type('content_update')
    print(f"\nContent update templates: {len(content_templates)}")

    technical_templates = templates.get_templates_by_type('technical')
    print(f"Technical templates: {len(technical_templates)}")


def example_template_matching():
    """Demonstrate template matching for insights"""
    print("\n=== Template Matching ===\n")

    templates = ActionTemplates()

    # Example insights with different characteristics
    test_insights = [
        {
            'category': 'risk',
            'source': 'AnomalyDetector',
            'title': 'Traffic drop detected',
            'description': 'Significant decline in organic traffic'
        },
        {
            'category': 'opportunity',
            'source': 'ContentQualityDetector',
            'title': 'Page missing meta description',
            'description': 'This page has no meta description'
        },
        {
            'category': 'technical',
            'source': 'Unknown',
            'title': 'Core Web Vitals issue',
            'description': 'LCP exceeds 2.5 seconds'
        }
    ]

    print("Matching templates to insights:\n")
    for insight in test_insights:
        template = templates.get_for_insight(insight)
        print(f"Insight: {insight['title']}")
        print(f"  Matched template: {template['action_type']}")
        print(f"  Effort: {template['effort']}")
        print(f"  Instructions: {len(template['instructions'])} steps")
        print()


def example_action_completion():
    """Example of completing an action"""
    print("\n=== Action Completion ===\n")

    generator = ActionGenerator()

    # Complete an action with outcome
    action_id = "550e8400-e29b-41d4-a716-446655440001"
    outcome = {
        'result': 'success',
        'metrics_change': {
            'clicks_before': 100,
            'clicks_after': 150,
            'improvement_percent': 50
        },
        'notes': 'Updated meta descriptions on 5 pages. Saw immediate CTR improvement.',
        'completed_by': 'user@example.com',
        'completed_date': datetime.utcnow().isoformat()
    }

    print(f"Completing action: {action_id}")
    print(f"Outcome: {outcome['result']}")

    # Note: This requires database connection
    # success = generator.complete_action(action_id, outcome)
    # if success:
    #     print("Action marked as completed successfully")


def example_pending_actions():
    """Example of getting pending actions"""
    print("\n=== Pending Actions ===\n")

    generator = ActionGenerator()
    property_name = "sc-domain:example.com"

    print(f"Fetching pending actions for: {property_name}")

    # Note: This requires database connection
    # pending = generator.get_pending_actions(property_name, limit=5)
    # print(f"Found {len(pending)} pending actions\n")
    #
    # for action in pending:
    #     print(f"- {action.title}")
    #     print(f"  Priority: {action.priority} | Effort: {action.effort}")
    #     print(f"  Impact: {action.estimated_impact.get('traffic_potential', 'N/A')}")
    #     print()


if __name__ == '__main__':
    print("=" * 60)
    print("Action Generator Service - Usage Examples")
    print("=" * 60)

    # Run examples (database operations commented out)
    example_template_exploration()
    example_template_matching()

    print("\n" + "=" * 60)
    print("Note: Examples requiring database connections are commented out.")
    print("Set WAREHOUSE_DSN environment variable to enable full functionality.")
    print("=" * 60)
