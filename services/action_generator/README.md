# Action Generator Service

The Action Generator Service transforms insights into concrete, actionable tasks with clear instructions, priorities, and estimated impact.

## Overview

This service bridges the gap between insight detection and action implementation by:
- Converting insights into structured action items
- Providing step-by-step instructions for each action
- Estimating effort and impact
- Prioritizing actions by value and urgency
- Tracking action outcomes

## Components

### 1. ActionGenerator (`generator.py`)
The main service class that generates and manages actions.

**Key Features:**
- Generate actions from individual insights
- Batch generate actions for entire properties
- Prioritize actions by impact/effort ratio
- Track action completion and outcomes
- Support for various action types

**Usage:**
```python
from services.action_generator import ActionGenerator

# Initialize
generator = ActionGenerator()

# Generate from single insight
action = generator.generate_from_insight('insight-uuid-123')

# Batch generate
actions = generator.generate_batch('sc-domain:example.com', limit=50)

# Prioritize
prioritized = generator.prioritize_actions(actions)

# Get pending actions
pending = generator.get_pending_actions('sc-domain:example.com')

# Complete action
generator.complete_action('action-uuid-456', outcome={
    'result': 'success',
    'metrics_change': {'clicks': 150},
    'notes': 'Meta descriptions updated'
})
```

### 2. ActionTemplates (`templates.py`)
Template system for converting different insight types into appropriate actions.

**Available Templates:**
- **SEO Content**: `seo_title_fix`, `meta_description_add`, `content_expansion`
- **Technical SEO**: `redirect_setup`, `canonical_fix`, `page_speed_optimization`
- **Keyword/Ranking**: `keyword_optimization`, `cannibalization_fix`
- **Links**: `internal_linking`
- **Investigations**: `traffic_drop_investigation`, `ranking_drop_fix`

**Template Matching:**
Templates are automatically selected based on:
1. Insight category and source
2. Keywords in title/description
3. Default fallback to general action

**Usage:**
```python
from services.action_generator import ActionTemplates

templates = ActionTemplates()

# Get specific template
template = templates.get_template('seo_title_fix')

# Get template for insight
template = templates.get_for_insight(insight_dict)

# List all templates
template_names = templates.list_templates()

# Filter by type
content_templates = templates.get_templates_by_type('content_update')
```

### 3. Action Dataclass
Represents a structured action item.

**Fields:**
- `id`: Unique identifier
- `insight_id`: Reference to source insight
- `property`: GSC property
- `action_type`: Category (content_update, technical, etc.)
- `title`: Action title
- `description`: Detailed description
- `instructions`: Step-by-step list
- `priority`: critical, high, medium, low
- `effort`: low, medium, high
- `estimated_impact`: Expected improvements
- `status`: pending, in_progress, completed, cancelled
- `assigned_to`: Person responsible
- `created_at`, `completed_at`: Timestamps
- `outcome`: Results after completion

## Database Schema

The `gsc.actions` table stores all action items:

```sql
CREATE TABLE gsc.actions (
    id UUID PRIMARY KEY,
    insight_id UUID REFERENCES gsc.insights(id),
    property TEXT NOT NULL,
    action_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    instructions JSONB,
    priority TEXT NOT NULL,
    effort TEXT NOT NULL,
    estimated_impact JSONB,
    status TEXT NOT NULL DEFAULT 'pending',
    assigned_to TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    outcome JSONB,
    metadata JSONB
);
```

**Indexes:** Optimized for querying by property, status, priority, and combinations.

## Priority Calculation

Actions are prioritized using a scoring algorithm:

```
score = (priority_weight × effort_inverse) + impact_score

Where:
- priority_weight: critical=100, high=75, medium=50, low=25
- effort_inverse: low=3, medium=2, high=1
- impact_score: Based on traffic_potential (max 50 points)
```

This favors high-priority, low-effort actions with significant impact.

## Action Types

### content_update
Updates to page content, meta tags, or on-page elements.
- Examples: Title optimization, meta descriptions, content expansion
- Typical effort: Low to High
- Impact: CTR improvement, ranking gains

### technical
Technical SEO fixes and improvements.
- Examples: Redirects, canonicals, page speed optimization
- Typical effort: Low to Medium
- Impact: Indexing, crawling, user experience

### content_restructure
Major content reorganization or consolidation.
- Examples: Content consolidation, cannibalization fixes
- Typical effort: High
- Impact: Ranking improvements, reduced competition

### investigation
Research and analysis tasks.
- Examples: Traffic drop investigation, ranking analysis
- Typical effort: Medium
- Impact: Identifies root causes for remediation

### general
Catch-all for actions that don't fit other categories.

## Workflow

1. **Detection**: Insight engine detects issues/opportunities
2. **Generation**: ActionGenerator creates actionable task
3. **Prioritization**: Actions sorted by impact/effort
4. **Assignment**: Actions assigned to team members
5. **Execution**: Instructions followed step-by-step
6. **Completion**: Results tracked in outcome field
7. **Analysis**: Success metrics inform future actions

## Configuration

Set database connection via environment variable:
```bash
export WAREHOUSE_DSN="postgresql://user:pass@localhost:5432/seo_warehouse"
```

## Testing

Comprehensive test suite with mocked database operations:
```bash
pytest tests/services/test_action_generator.py -v
```

**Test Coverage:**
- Template selection and matching
- Action generation from insights
- Batch generation and filtering
- Priority calculation
- Action completion tracking
- Error handling
- Integration workflows

## Examples

See `examples/action_generator_usage.py` for detailed usage examples:
```bash
python examples/action_generator_usage.py
```

## Extension

### Adding New Templates

1. Add template to `TEMPLATES` dict in `templates.py`:
```python
'my_new_template': {
    'action_type': 'content_update',
    'title_template': 'Fix {page_path}',
    'description_template': 'Details...',
    'effort': 'medium',
    'instructions': ['Step 1', 'Step 2', ...],
    'estimated_impact': {'metric': value}
}
```

2. Add mapping in `INSIGHT_TEMPLATE_MAP` or `KEYWORD_TEMPLATE_MAP`:
```python
INSIGHT_TEMPLATE_MAP[('category', 'source')] = 'my_new_template'
# or
KEYWORD_TEMPLATE_MAP['keyword'] = 'my_new_template'
```

### Custom Priority Logic

Override `prioritize_actions` method in subclass:
```python
class CustomActionGenerator(ActionGenerator):
    def prioritize_actions(self, actions):
        # Custom sorting logic
        return sorted(actions, key=my_custom_score, reverse=True)
```

## Best Practices

1. **Clear Instructions**: Each action should have 5-10 specific steps
2. **Realistic Estimates**: Base effort/impact on historical data
3. **Track Outcomes**: Always record results for continuous improvement
4. **Avoid Duplication**: Check for existing actions before creating
5. **Batch Processing**: Generate actions in batches for efficiency
6. **Regular Review**: Prioritize and assign actions systematically

## Dependencies

- `psycopg2`: PostgreSQL database adapter
- `python-dotenv`: Environment variable management (optional)

## Limitations

- Requires pre-existing insights in database
- Templates are static (not ML-based)
- Impact estimates are heuristic-based
- No automatic execution of actions

## Future Enhancements

- ML-based template selection
- Automated action execution for simple tasks
- Integration with task management systems
- Historical outcome analysis for better estimates
- A/B testing framework for action effectiveness
- Automated follow-up actions based on outcomes

## License

Part of the Site Data Warehouse project.
