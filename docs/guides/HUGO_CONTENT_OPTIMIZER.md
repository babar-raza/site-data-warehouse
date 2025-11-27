# Hugo Content Optimizer

The Hugo Content Optimizer is an automated system for executing SEO content optimization actions on Hugo CMS content files. It connects the Insights Engine's recommendations to actual content modifications using LLM-powered optimization.

## Overview

The system provides:

1. **Automated Execution**: Execute approved SEO actions automatically during daily pipeline runs
2. **Manual Execution**: Execute actions on-demand via CLI or API
3. **LLM-Powered Optimization**: Use Ollama for intelligent content optimization
4. **Safe Operations**: Dry-run mode, validation, and rollback support
5. **Hugo Integration**: Native support for Hugo's frontmatter and localization patterns

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Insights       │    │   Actions       │    │   Hugo          │
│  Engine         │───▶│   Database      │◀───│   Content       │
│  (Detectors)    │    │   (gsc.actions) │    │   Files         │
└─────────────────┘    └────────┬────────┘    └────────▲────────┘
                               │                       │
                       ┌───────▼───────┐              │
                       │  Hugo Content  │              │
                       │  Writer        │──────────────┘
                       │  (LLM + Write) │
                       └───────┬───────┘
                               │
                       ┌───────▼───────┐
                       │  Structured   │
                       │  LLM Client   │
                       │  (Instructor) │
                       └───────┬───────┘
                               │
                       ┌───────▼───────┐
                       │    Ollama     │
                       │    (LLM)      │
                       └───────────────┘
```

### Structured LLM Integration

The system uses **Instructor + Pydantic** for validated LLM responses:

```
┌─────────────────────────────────────────────────────────────┐
│                  ContentOptimizationClient                   │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Schemas    │  │    Cache     │  │ Rate Limiter │      │
│  │  (Pydantic)  │  │  (SHA256)    │  │ (Resource)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          Instructor (JSON Mode + Retries)            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

Key benefits:
- **Validated responses**: All LLM outputs are validated against Pydantic schemas
- **Auto-retry**: Validation errors are fed back to the LLM for self-correction
- **Caching**: Content-hash based caching prevents duplicate LLM calls
- **Rate limiting**: Adapts to available GPU/CPU resources

See [insights_core/prompts/README.md](../../insights_core/prompts/README.md) for detailed documentation.

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Hugo Content Path (required)
HUGO_CONTENT_PATH=/path/to/hugo/content

# Subdomains using file-based localization (comma-separated)
# File-based: index.md, index.es.md, index.fr.md
# Folder-based (all others): /en/page.md, /es/page.md
HUGO_FILE_LOCALIZATION_SUBDOMAINS=blog.example.com,news.example.com

# Default locale for content files
HUGO_DEFAULT_LOCALE=en

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b-instruct

# Structured prompts feature flag (disable for legacy parsing)
USE_STRUCTURED_PROMPTS=true
```

### Model Tiers

The system automatically selects the best available model:

| Tier | Models | Use Case |
|------|--------|----------|
| **Production** | qwen2.5:14b-instruct, phi4:14b | Best quality output |
| **Testing** | qwen2.5-coder:7b, mistral:latest | Fast iteration |
| **Fallback** | llama3:8b | Broad compatibility |

To override model selection:
```bash
OLLAMA_MODEL=phi4:14b  # Force specific model
```

### Localization Patterns

The system supports two Hugo localization patterns:

#### File-Based Localization

For sites in `HUGO_FILE_LOCALIZATION_SUBDOMAINS`:

```
content/
  blog.example.com/
    article/
      index.md        # English (default)
      index.es.md     # Spanish
      index.fr.md     # French
```

#### Folder-Based Localization

For all other sites:

```
content/
  main.example.com/
    en/
      article.md      # English
    es/
      article.md      # Spanish
    fr/
      article.md      # French
```

## Usage

### CLI Tool

The `execute_action.py` CLI tool provides manual action execution:

```bash
# Check system readiness
python scripts/execute_action.py --check

# List pending actions
python scripts/execute_action.py --list

# List pending actions with filters
python scripts/execute_action.py --list --property "https://blog.example.com" --priority high

# Dry-run a single action
python scripts/execute_action.py ACTION_ID --dry-run

# Execute a single action
python scripts/execute_action.py ACTION_ID

# Execute multiple actions
python scripts/execute_action.py ACTION_ID_1 ACTION_ID_2 ACTION_ID_3
```

### API Endpoints

Execute actions programmatically via the REST API:

```bash
# Check execution readiness
curl http://localhost:8000/api/v1/actions/execution-ready

# List pending actions
curl http://localhost:8000/api/v1/actions/pending

# Dry-run an action
curl -X POST http://localhost:8000/api/v1/actions/{action_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Execute an action
curl -X POST http://localhost:8000/api/v1/actions/{action_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'

# Execute batch of actions
curl -X POST http://localhost:8000/api/v1/actions/execute-batch \
  -H "Content-Type: application/json" \
  -d '{"action_ids": ["uuid1", "uuid2"], "dry_run": false}'
```

### Scheduler Integration

Actions with `status='approved'` are automatically executed during the daily pipeline:

```bash
# Test action execution in isolation
python scheduler/scheduler.py --test-actions

# View scheduled tasks (includes Content Action Execution)
python scheduler/scheduler.py --dry-run
```

The scheduler:
- Processes up to 10 approved actions per run
- Prioritizes by priority level (high > medium > low) and creation date
- Non-blocking: failures don't affect other pipeline tasks
- Logs all execution results to scheduler metrics

## Action Types

### Title Optimization (`title_optimization`)

Optimizes the page title in Hugo frontmatter for better keyword targeting and CTR.

**Input**:
- Current title from frontmatter
- Target keyword (from action metadata)
- Page content context

**Output**:
- Optimized title (max 60 characters)
- Keyword placement near the beginning

### Meta Description (`meta_description`)

Generates or improves the meta description for better search snippets.

**Input**:
- Current description (if any)
- Target keyword
- Page content summary

**Output**:
- Compelling description (max 160 characters)
- Includes call-to-action
- Natural keyword integration

### Content Expansion (`content_expansion`)

Expands thin content sections with additional valuable information.

**Input**:
- Existing content
- Target word count increase
- Topic/keyword focus

**Output**:
- Expanded content maintaining style
- Added depth and value
- SEO-friendly structure

### Readability Improvement (`readability_improvement`)

Improves content readability scores (Flesch-Kincaid).

**Input**:
- Current content
- Target reading level (grade 8)

**Output**:
- Simplified sentence structure
- Clearer language
- Maintained technical accuracy

### Keyword Optimization (`keyword_optimization`)

Optimizes keyword density and placement throughout content.

**Input**:
- Content body
- Target keyword
- Current density

**Output**:
- Natural keyword integration
- Improved semantic relevance
- Avoided keyword stuffing

### Intent Differentiation (`intent_differentiation`)

Differentiates content from competing pages to reduce cannibalization.

**Input**:
- Page content
- Competing page summaries
- Unique angle to emphasize

**Output**:
- Unique value proposition
- Differentiated content focus
- Clear intent targeting

## Action Status Workflow

```
┌─────────────┐
│   pending   │  Action generated by Insight Engine
└──────┬──────┘
       │
       ▼  (User approval required)
┌─────────────┐
│  approved   │  Ready for automatic execution
└──────┬──────┘
       │
       ▼  (Scheduler or manual trigger)
┌─────────────┐
│ in_progress │  Currently being executed
└──────┬──────┘
       │
       ├───▶ ┌─────────────┐
       │     │  completed  │  Successfully executed
       │     └─────────────┘
       │
       └───▶ ┌─────────────┐
             │   failed    │  Execution error
             └─────────────┘
```

### Approval Process

Actions require explicit approval before automatic execution:

```sql
-- Approve a single action
UPDATE gsc.actions SET status = 'approved' WHERE id = 'action-uuid';

-- Approve all high-priority actions for a property
UPDATE gsc.actions
SET status = 'approved'
WHERE property = 'https://blog.example.com'
  AND priority = 'high'
  AND status = 'pending';
```

Or use the Actions Command Center dashboard in Grafana to approve actions via UI.

## Troubleshooting

### Common Issues

#### Hugo Path Not Configured

```
Error: Hugo content path not configured
```

**Solution**: Set `HUGO_CONTENT_PATH` in `.env`:
```bash
HUGO_CONTENT_PATH=/path/to/hugo/content
```

#### Ollama Not Available

```
Error: Ollama server not responding
```

**Solution**: Ensure Ollama is running:
```bash
# Start Ollama
ollama serve

# Or via Docker
docker-compose up ollama
```

#### Content File Not Found

```
Error: Content file not found: /path/to/file.md
```

**Solution**: Verify:
1. Hugo content path is correct
2. Page path matches file structure
3. Localization pattern is correct for the subdomain

#### Action Already Completed

```
Error: Action already completed
```

**Solution**: Actions can only be executed once. Create a new action if re-execution is needed.

### Validation Errors

The system validates before execution:

1. **Action exists** in database
2. **Status is valid** (pending or approved)
3. **Hugo is configured** and path exists
4. **Content file exists** at resolved path
5. **Ollama is available** for LLM operations

Use dry-run mode to validate without making changes:

```bash
python scripts/execute_action.py ACTION_ID --dry-run
```

### Structured Prompts Validation

#### ValidationError After Retries

```
Error: ValidationError - optimized_title must be 10-60 characters
```

**Solution**: The LLM is returning invalid output. Try:
1. Lower temperature: Use `temperature=0.5` for more predictable output
2. Use larger model: 14B+ models produce better JSON
3. Check prompt: Ensure JSON format is clear in the prompt

#### Fallback to Legacy Mode

If structured prompts cause issues:

```bash
# Disable structured prompts
USE_STRUCTURED_PROMPTS=false
```

The system will fall back to legacy text parsing.

## Testing

### Unit Tests

```bash
# Run all Hugo Content Optimizer tests
pytest tests/config/test_hugo_config.py -v
pytest tests/insights_core/prompts/test_content_prompts.py -v
pytest tests/services/test_hugo_content_writer.py -v
pytest tests/insights_api/routes/test_actions.py -v
pytest tests/scripts/test_execute_action.py -v
```

### Structured Prompts Tests

```bash
# Schema validation tests (no Ollama required)
pytest tests/insights_core/prompts/test_schemas.py -v

# Mock client tests (no Ollama required)
pytest tests/insights_core/prompts/test_client_mock.py -v

# Live Ollama integration tests (requires running Ollama)
TEST_MODE=ollama pytest tests/insights_core/prompts/test_client_ollama.py -v
```

### Integration Testing

```bash
# Test scheduler integration
python scheduler/scheduler.py --test-actions

# Test API endpoint
curl http://localhost:8000/api/v1/actions/execution-ready
```

## Security Considerations

1. **Path Validation**: All file paths are validated against the configured Hugo content path
2. **No Arbitrary Execution**: Only predefined action types with specific templates are supported
3. **Approval Required**: Actions require explicit approval for automatic execution
4. **Audit Trail**: All executions are logged with timestamps and outcomes
5. **Dry-Run Mode**: Always test with dry-run before live execution

## Related Documentation

- [API Reference - Action Execution API](../api/API_REFERENCE.md#action-execution-api)
- [Insight Engine Guide](INSIGHT_ENGINE_GUIDE.md)
- [Actions Command Center](ACTIONS_COMMAND_CENTER.md)
- [Development Guide](DEVELOPMENT.md)

---

*Last Updated: November 2025*
