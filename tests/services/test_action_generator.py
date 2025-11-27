"""
Tests for Action Generator Service

Comprehensive tests with mocks - no real database calls.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import uuid

from services.action_generator.generator import ActionGenerator, Action
from services.action_generator.templates import ActionTemplates


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('psycopg2.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor


@pytest.fixture
def generator():
    """Create ActionGenerator instance"""
    with patch.dict('os.environ', {'WAREHOUSE_DSN': 'postgresql://test'}):
        return ActionGenerator()


@pytest.fixture
def sample_insight():
    """Sample insight for testing"""
    return {
        'id': str(uuid.uuid4()),
        'property': 'sc-domain:example.com',
        'entity_type': 'page',
        'entity_id': '/blog/seo-tips',
        'category': 'risk',
        'source': 'AnomalyDetector',
        'title': 'Traffic drop detected',
        'description': 'Significant traffic decline on this page',
        'severity': 'high',
        'status': 'new',
        'metrics': {
            'gsc_clicks': 1000,
            'gsc_impressions': 10000,
            'gsc_ctr': 0.1
        },
        'generated_at': datetime.utcnow()
    }


class TestActionTemplates:
    """Test ActionTemplates class"""

    def test_get_template_by_name(self):
        """Test getting template by name"""
        templates = ActionTemplates()
        template = templates.get_template('seo_title_fix')

        assert template is not None
        assert template['action_type'] == 'content_update'
        assert template['effort'] == 'low'
        assert 'instructions' in template
        assert len(template['instructions']) > 0

    def test_get_template_unknown_returns_general(self):
        """Test that unknown template returns general action"""
        templates = ActionTemplates()
        template = templates.get_template('nonexistent_template')

        assert template is not None
        assert template['action_type'] == 'general'

    def test_get_for_insight_by_category_source(self):
        """Test template selection by category and source"""
        templates = ActionTemplates()
        insight = {
            'category': 'risk',
            'source': 'AnomalyDetector',
            'title': 'Test',
            'description': 'Test'
        }

        template = templates.get_for_insight(insight)
        assert template['action_type'] == 'investigation'

    def test_get_for_insight_by_keyword_title(self):
        """Test template selection by keyword in title"""
        templates = ActionTemplates()
        insight = {
            'category': 'other',
            'source': 'Unknown',
            'title': 'Fix canonical tag issue',
            'description': 'Canonical needs updating'
        }

        template = templates.get_for_insight(insight)
        assert template['action_type'] == 'technical'

    def test_get_for_insight_by_keyword_description(self):
        """Test template selection by keyword in description"""
        templates = ActionTemplates()
        insight = {
            'category': 'other',
            'source': 'Unknown',
            'title': 'Page issue',
            'description': 'Core Web Vitals need improvement'
        }

        template = templates.get_for_insight(insight)
        assert template['action_type'] == 'technical'

    def test_get_for_insight_defaults_to_general(self):
        """Test that unmatched insights get general template"""
        templates = ActionTemplates()
        insight = {
            'category': 'unknown',
            'source': 'Unknown',
            'title': 'Some random issue',
            'description': 'Something happened'
        }

        template = templates.get_for_insight(insight)
        assert template['action_type'] == 'general'

    def test_list_templates(self):
        """Test listing all templates"""
        templates = ActionTemplates()
        template_names = templates.list_templates()

        assert isinstance(template_names, list)
        assert len(template_names) > 0
        assert 'seo_title_fix' in template_names
        assert 'general_action' in template_names

    def test_get_templates_by_type(self):
        """Test filtering templates by type"""
        templates = ActionTemplates()
        content_templates = templates.get_templates_by_type('content_update')

        assert isinstance(content_templates, list)
        assert len(content_templates) > 0
        for template in content_templates:
            assert template['action_type'] == 'content_update'
            assert 'name' in template

    def test_all_templates_have_required_fields(self):
        """Test that all templates have required fields"""
        templates = ActionTemplates()
        required_fields = ['action_type', 'title_template', 'description_template',
                          'effort', 'instructions', 'estimated_impact']

        for name in templates.list_templates():
            template = templates.get_template(name)
            for field in required_fields:
                assert field in template, f"Template {name} missing {field}"

    def test_template_instructions_are_list(self):
        """Test that all template instructions are lists"""
        templates = ActionTemplates()
        for name in templates.list_templates():
            template = templates.get_template(name)
            assert isinstance(template['instructions'], list)
            assert len(template['instructions']) > 0


class TestAction:
    """Test Action dataclass"""

    def test_action_to_dict(self):
        """Test converting Action to dictionary"""
        action = Action(
            id=str(uuid.uuid4()),
            insight_id=str(uuid.uuid4()),
            property='sc-domain:example.com',
            action_type='content_update',
            title='Test Action',
            description='Test description',
            instructions=['Step 1', 'Step 2'],
            priority='high',
            effort='medium',
            estimated_impact={'traffic_potential': 50},
            status='pending',
            assigned_to=None,
            created_at=datetime.utcnow(),
            completed_at=None,
            outcome=None
        )

        result = action.to_dict()
        assert isinstance(result, dict)
        assert result['id'] == action.id
        assert result['title'] == 'Test Action'
        assert isinstance(result['created_at'], str)  # Should be ISO format


class TestActionGenerator:
    """Test ActionGenerator class"""

    def test_initialization(self, generator):
        """Test ActionGenerator initialization"""
        assert generator is not None
        assert isinstance(generator.templates, ActionTemplates)
        assert generator.db_dsn is not None

    def test_priority_mapping(self, generator):
        """Test severity to priority mapping"""
        assert generator.PRIORITY_MAP['high'] == 'critical'
        assert generator.PRIORITY_MAP['medium'] == 'high'
        assert generator.PRIORITY_MAP['low'] == 'medium'

    def test_generate_from_insight_not_found(self, generator, mock_db_connection):
        """Test generating action from non-existent insight"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchone.return_value = None

        action = generator.generate_from_insight('nonexistent-id')
        assert action is None

    def test_generate_from_insight_existing_action(self, generator, mock_db_connection, sample_insight):
        """Test that existing actions are returned"""
        mock_conn, mock_cursor = mock_db_connection

        # First call returns insight, second call returns existing action
        existing_action_row = {
            'id': str(uuid.uuid4()),
            'insight_id': sample_insight['id'],
            'property': sample_insight['property'],
            'action_type': 'investigation',
            'title': 'Existing Action',
            'description': 'Already exists',
            'instructions': ['Step 1'],
            'priority': 'critical',
            'effort': 'medium',
            'estimated_impact': {},
            'status': 'pending',
            'assigned_to': None,
            'created_at': datetime.utcnow(),
            'completed_at': None,
            'outcome': None
        }

        mock_cursor.fetchone.side_effect = [sample_insight, existing_action_row]

        action = generator.generate_from_insight(sample_insight['id'])
        assert action is not None
        assert action.title == 'Existing Action'

    def test_generate_from_insight_creates_new(self, generator, mock_db_connection, sample_insight):
        """Test creating new action from insight"""
        mock_conn, mock_cursor = mock_db_connection

        # First call returns insight, second returns no existing action
        mock_cursor.fetchone.side_effect = [sample_insight, None]

        action = generator.generate_from_insight(sample_insight['id'])
        assert action is not None
        assert action.insight_id == sample_insight['id']
        assert action.property == sample_insight['property']
        assert action.status == 'pending'
        assert action.priority == 'critical'  # high severity -> critical priority
        assert len(action.instructions) > 0

    def test_generate_batch(self, generator, mock_db_connection, sample_insight):
        """Test batch action generation"""
        mock_conn, mock_cursor = mock_db_connection

        # Return multiple insights without actions
        insights = [
            {**sample_insight, 'id': str(uuid.uuid4())}
            for _ in range(3)
        ]
        mock_cursor.fetchall.return_value = insights

        # For each insight, return the insight then None (no existing action)
        mock_cursor.fetchone.side_effect = [
            insights[0], None,
            insights[1], None,
            insights[2], None
        ]

        actions = generator.generate_batch('sc-domain:example.com', limit=10)
        assert len(actions) == 3
        for action in actions:
            assert isinstance(action, Action)
            assert action.status == 'pending'

    def test_generate_batch_with_filters(self, generator, mock_db_connection, sample_insight):
        """Test batch generation with category and severity filters"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        actions = generator.generate_batch(
            'sc-domain:example.com',
            limit=10,
            category='risk',
            severity='high'
        )

        assert len(actions) == 0
        # Verify query was called with filters
        assert mock_cursor.execute.called

    def test_prioritize_actions(self, generator):
        """Test action prioritization"""
        actions = [
            Action(
                id=str(uuid.uuid4()),
                insight_id=str(uuid.uuid4()),
                property='sc-domain:example.com',
                action_type='content_update',
                title='Low Priority',
                description='',
                instructions=[],
                priority='low',
                effort='high',
                estimated_impact={'traffic_potential': 10},
                status='pending',
                assigned_to=None,
                created_at=datetime.utcnow(),
                completed_at=None,
                outcome=None
            ),
            Action(
                id=str(uuid.uuid4()),
                insight_id=str(uuid.uuid4()),
                property='sc-domain:example.com',
                action_type='technical',
                title='High Priority',
                description='',
                instructions=[],
                priority='critical',
                effort='low',
                estimated_impact={'traffic_potential': 100},
                status='pending',
                assigned_to=None,
                created_at=datetime.utcnow(),
                completed_at=None,
                outcome=None
            )
        ]

        prioritized = generator.prioritize_actions(actions)
        assert len(prioritized) == 2
        assert prioritized[0].title == 'High Priority'
        assert prioritized[1].title == 'Low Priority'

    def test_get_pending_actions(self, generator, mock_db_connection):
        """Test getting pending actions"""
        mock_conn, mock_cursor = mock_db_connection

        pending_action = {
            'id': str(uuid.uuid4()),
            'insight_id': str(uuid.uuid4()),
            'property': 'sc-domain:example.com',
            'action_type': 'content_update',
            'title': 'Pending Action',
            'description': '',
            'instructions': ['Step 1'],
            'priority': 'high',
            'effort': 'medium',
            'estimated_impact': {},
            'status': 'pending',
            'assigned_to': None,
            'created_at': datetime.utcnow(),
            'completed_at': None,
            'outcome': None
        }

        mock_cursor.fetchall.return_value = [pending_action]

        actions = generator.get_pending_actions('sc-domain:example.com', limit=10)
        assert len(actions) == 1
        assert actions[0].title == 'Pending Action'
        assert actions[0].status == 'pending'

    def test_complete_action(self, generator, mock_db_connection):
        """Test completing an action"""
        mock_conn, mock_cursor = mock_db_connection

        action_id = str(uuid.uuid4())
        outcome = {
            'result': 'success',
            'metrics_change': {
                'clicks': 100,
                'impressions': 1000
            },
            'notes': 'Action completed successfully'
        }

        result = generator.complete_action(action_id, outcome)
        assert result is True
        assert mock_cursor.execute.called
        assert mock_conn.commit.called

    def test_complete_action_without_outcome(self, generator, mock_db_connection):
        """Test completing action without outcome data"""
        mock_conn, mock_cursor = mock_db_connection

        action_id = str(uuid.uuid4())
        result = generator.complete_action(action_id)
        assert result is True

    def test_complete_action_error_handling(self, generator, mock_db_connection):
        """Test error handling when completing action"""
        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.execute.side_effect = Exception("Database error")

        result = generator.complete_action(str(uuid.uuid4()))
        assert result is False
        assert mock_conn.rollback.called

    def test_create_action_formats_instructions(self, generator, sample_insight):
        """Test that action creation formats instruction templates"""
        template = {
            'action_type': 'content_update',
            'title_template': 'Fix {page_path}',
            'description_template': 'Update {page_path} on {property}',
            'instructions': [
                'Open {page_path} in editor',
                'Make changes',
                'Save and publish'
            ],
            'effort': 'low',
            'estimated_impact': {'ctr_improvement': 0.1}
        }

        action = generator._create_action(sample_insight, template)
        assert '/blog/seo-tips' in action.title
        assert '/blog/seo-tips' in action.description
        assert '/blog/seo-tips' in action.instructions[0]
        assert 'Make changes' in action.instructions[1]

    def test_create_action_calculates_priority(self, generator, sample_insight):
        """Test priority calculation from severity"""
        template = {
            'action_type': 'general',
            'title_template': 'Test',
            'description_template': 'Test',
            'instructions': [],
            'effort': 'medium',
            'estimated_impact': {}
        }

        # Test high severity -> critical priority
        sample_insight['severity'] = 'high'
        action = generator._create_action(sample_insight, template)
        assert action.priority == 'critical'

        # Test medium severity -> high priority
        sample_insight['severity'] = 'medium'
        action = generator._create_action(sample_insight, template)
        assert action.priority == 'high'

        # Test low severity -> medium priority
        sample_insight['severity'] = 'low'
        action = generator._create_action(sample_insight, template)
        assert action.priority == 'medium'

    def test_create_action_estimates_traffic_potential(self, generator, sample_insight):
        """Test traffic potential estimation"""
        template = {
            'action_type': 'general',
            'title_template': 'Test',
            'description_template': 'Test',
            'instructions': [],
            'effort': 'medium',
            'estimated_impact': {'base': 'value'}
        }

        action = generator._create_action(sample_insight, template)
        # Should calculate 10% of current clicks
        assert action.estimated_impact['traffic_potential'] == 100  # 10% of 1000

    def test_row_to_action_conversion(self, generator):
        """Test converting database row to Action object"""
        row = {
            'id': str(uuid.uuid4()),
            'insight_id': str(uuid.uuid4()),
            'property': 'sc-domain:example.com',
            'action_type': 'content_update',
            'title': 'Test Action',
            'description': 'Test description',
            'instructions': ['Step 1', 'Step 2'],
            'priority': 'high',
            'effort': 'medium',
            'estimated_impact': {'traffic_potential': 50},
            'status': 'pending',
            'assigned_to': 'user@example.com',
            'created_at': datetime.utcnow(),
            'completed_at': None,
            'outcome': None
        }

        action = generator._row_to_action(row)
        assert isinstance(action, Action)
        assert action.id == row['id']
        assert action.title == row['title']
        assert action.assigned_to == row['assigned_to']


class TestIntegration:
    """Integration tests for end-to-end workflows"""

    def test_full_action_generation_workflow(self, generator, mock_db_connection, sample_insight):
        """Test complete workflow from insight to action"""
        mock_conn, mock_cursor = mock_db_connection

        # Setup: insight exists, no existing action
        mock_cursor.fetchone.side_effect = [sample_insight, None]

        # Generate action
        action = generator.generate_from_insight(sample_insight['id'])

        # Verify action was created correctly
        assert action is not None
        assert action.insight_id == sample_insight['id']
        assert action.status == 'pending'
        assert action.priority == 'critical'
        assert len(action.instructions) > 0

        # Verify database calls were made
        assert mock_cursor.execute.called
        assert mock_conn.commit.called

    def test_batch_generation_with_prioritization(self, generator, mock_db_connection, sample_insight):
        """Test batch generation with subsequent prioritization"""
        mock_conn, mock_cursor = mock_db_connection

        # Create insights with different severities
        insights = [
            {**sample_insight, 'id': str(uuid.uuid4()), 'severity': 'low'},
            {**sample_insight, 'id': str(uuid.uuid4()), 'severity': 'high'},
            {**sample_insight, 'id': str(uuid.uuid4()), 'severity': 'medium'}
        ]
        mock_cursor.fetchall.return_value = insights

        # Setup responses for each insight
        mock_cursor.fetchone.side_effect = [
            insights[0], None,
            insights[1], None,
            insights[2], None
        ]

        # Generate batch
        actions = generator.generate_batch('sc-domain:example.com', limit=10)
        assert len(actions) == 3

        # Prioritize
        prioritized = generator.prioritize_actions(actions)
        assert len(prioritized) == 3
        # High severity should be first (critical priority)
        assert prioritized[0].priority == 'critical'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
