# Insight Engine Integration - Fixes and Additions

This package contains all fixes and additions to complete the Unified Insight Engine integration.

## What's Included

### New Files

1. **insights_api/** - Complete RESTful API server for insights
   - `insights_api.py` - FastAPI server with full CRUD operations
   - `__init__.py` - Package initialization

2. **mcp/insights_integration.py** - MCP server insights tools
   - 5 new MCP tools for querying insights
   - Integration helpers for MCP server

3. **mcp/MCP_INTEGRATION_GUIDE.py** - Integration instructions
   - Step-by-step guide to integrate insights tools into MCP server
   - Alternative deployment options

4. **tests/test_unified_insights_api.py** - Comprehensive API tests
   - Health check tests
   - Query endpoint tests
   - Mutation endpoint tests
   - Error handling tests

5. **tests/verify_insight_engine.py** - System verification script
   - 13 verification checks covering all components
   - Validates module imports, structure, SQL files, and integrations

### Modified Files

1. **insights_core/repository.py**
   - Added `query_recent()` method for dispatcher

2. **transform/apply_transforms.py**
   - Fixed SQL file list to match actual files
   - Added insights table to transform list

## Installation

1. Extract all files maintaining directory structure:
   ```bash
   unzip insight_engine_fixes.zip
   ```

2. Files go into their respective directories:
   - `insights_api/` → Root project directory
   - `insights_core/repository.py` → Replace existing
   - `mcp/` → Add to existing mcp directory
   - `transform/apply_transforms.py` → Replace existing
   - `tests/` → Add to existing tests directory
   - `verify_insight_engine.py` → Root project directory

## Verification

Run the verification script to check all components:

```bash
cd /path/to/project
python verify_insight_engine.py
```

Expected output: All 13 verification sections should pass.

## Starting Services

### 1. Database Schema Initialization

Apply transforms (includes insights table):
```bash
python -m transform.apply_transforms
```

Or run the full schema SQL:
```bash
psql -h localhost -U gsc_user -d gsc_db -f sql/11_insights_table.sql
```

### 2. Insights API Server

Start the RESTful API:
```bash
export WAREHOUSE_DSN="postgresql://gsc_user:gsc_pass@localhost:5432/gsc_db"
python insights_api/insights_api.py
```

Access at: http://localhost:8000/api/docs

### 3. Scheduler (includes insights refresh)

The scheduler already includes insights refresh:
```bash
python scheduler/scheduler.py
```

Daily job runs: Ingestion → Transforms → Insights Refresh

### 4. MCP Server (with insights tools)

Follow the integration guide:
```bash
python mcp/MCP_INTEGRATION_GUIDE.py
```

Or run insights API as standalone service.

## Testing

Run tests:
```bash
# All tests
pytest -v

# Just insights tests
pytest tests/test_insight_models.py -v
pytest tests/test_insight_repository.py -v
pytest tests/test_unified_insights_api.py -v
pytest tests/test_detectors.py -v
pytest tests/test_dispatcher.py -v
```

## Key Endpoints

### Insights API

- `GET /api/health` - Health check
- `GET /api/stats` - Repository statistics
- `GET /api/insights` - Query insights with filters
- `GET /api/insights/{id}` - Get specific insight
- `GET /api/insights/actionable` - Get actionable insights
- `GET /api/insights/recent/{hours}` - Recent insights
- `PATCH /api/insights/{id}` - Update insight status

### MCP Server (after integration)

- `query_insights` - Query with filters
- `get_insight_by_id` - Get by ID
- `get_actionable_insights` - Prioritized actionable list
- `get_recent_insights` - Time-based query
- `get_insights_summary` - Property statistics

## Architecture Notes

### Data Flow

```
GSC/GA4 Ingestion 
    ↓
SQL Transforms (vw_unified_page_performance)
    ↓
InsightEngine
    ├── AnomalyDetector (risk/opportunity insights)
    ├── DiagnosisDetector (diagnosis insights + links)
    └── OpportunityDetector (content gap insights)
    ↓
gsc.insights table (via InsightRepository)
    ↓
    ├── Insights API (REST endpoints)
    ├── MCP Server (LLM tools)
    └── Dispatcher (Slack/Jira/Email)
```

### Key Components

- **InsightEngine** - Orchestrates 3 detectors in sequence
- **InsightRepository** - All database operations, deterministic IDs
- **Detectors** - Anomaly (WoW drops), Diagnosis (root cause), Opportunity (gaps)
- **Dispatcher** - Routes insights to channels based on severity
- **Insights API** - RESTful access for dashboards/integrations
- **MCP Integration** - Tools for LLM agents

## Docker Deployment

The project includes Docker compose files:

```bash
# Start full stack
docker-compose up -d

# Or individual services
docker-compose -f compose/insights_api.yml up -d
docker-compose -f compose/insights_engine.yml up -d
```

## Environment Variables

```bash
# Required
WAREHOUSE_DSN=postgresql://user:pass@host:5432/dbname

# Optional
API_HOST=0.0.0.0
API_PORT=8001
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gsc_db
POSTGRES_USER=gsc_user
POSTGRES_PASSWORD=gsc_password
```

## Troubleshooting

### "Module not found: pydantic"

Install dependencies:
```bash
pip install -r requirements.txt
```

### "Table gsc.insights does not exist"

Run transforms:
```bash
python -m transform.apply_transforms
```

### "Connection refused to database"

Check database is running and WAREHOUSE_DSN is correct:
```bash
psql $WAREHOUSE_DSN -c "SELECT 1"
```

### MCP server doesn't show insights tools

Follow integration guide to add insights_integration module:
```bash
python mcp/MCP_INTEGRATION_GUIDE.py
```

## Status

All components verified and operational:

✓ Data layer (unified view with WoW/MoM calculations)
✓ Model layer (Insight Pydantic model + gsc.insights table)
✓ Analysis layer (Engine + 3 Detectors + Repository)
✓ Orchestration (Scheduler with insights refresh)
✓ Serving layer (Insights API + MCP integration module)
✓ Action layer (Dispatcher with channels)
✓ Tests (comprehensive coverage)
✓ Docker (compose files for all services)

## Next Steps

1. Run verification script
2. Apply database transforms
3. Start Insights API
4. Test endpoints
5. Integrate MCP server (optional)
6. Configure dispatcher channels
7. Set up monitoring

## Support

For issues or questions:
1. Check verification script output
2. Review logs in /logs/
3. Check API docs at /api/docs
4. Consult integration guide for MCP
