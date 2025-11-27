# END-TO-END TESTING PLAN
## Hybrid Plan Implementation (GSC + GA4 Unified Insight Engine)

**Testing Goal:** Verify the complete data pipeline from API ingestion → Unified View → Insight Detection → Output

---

## TEST SUITE STRUCTURE

### Phase 1: Infrastructure & Data Layer (Foundation)
### Phase 2: Insight Engine (Core Logic)  
### Phase 3: Multi-Agent System (Intelligence Layer)
### Phase 4: End-to-End Integration (Full Pipeline)
### Phase 5: Performance & Reliability (Production Readiness)

---

## PHASE 1: INFRASTRUCTURE & DATA LAYER

### Test 1.1: Database Schema Validation
**Objective:** Verify all tables, views, and constraints exist

```bash
# Run from project root
cd /home/claude

# 1. Check all SQL scripts execute cleanly
for script in sql/*.sql; do
    echo "Testing: $script"
    psql $WAREHOUSE_DSN -f "$script" > /tmp/test_$$.log 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ FAILED: $script"
        cat /tmp/test_$$.log
        exit 1
    fi
    echo "✅ PASSED: $script"
done

# 2. Validate unified view structure
psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"

# 3. Validate insights table
psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_insights_table();"
```

**Expected Results:**
- All SQL scripts execute without errors
- `validate_unified_view_time_series()` returns PASS for all checks
- `validate_insights_table()` returns PASS for all checks
- Views contain time-series columns: `gsc_clicks_change_wow`, `ga_conversions_change_wow`

**Acceptance Criteria:**
- [ ] All tables created: `fact_gsc_daily`, `fact_ga4_daily`, `insights`
- [ ] Unified view exists: `vw_unified_page_performance`
- [ ] Time-series calculations present (WoW, MoM changes)
- [ ] Indexes created for performance
- [ ] Validation functions return PASS

---

### Test 1.2: Data Ingestion (GSC + GA4)
**Objective:** Verify both data sources populate the warehouse

```bash
# 1. Run GSC ingestion
python ingestors/api/gsc_api_ingestor.py --date-start 2024-11-01 --date-end 2024-11-15

# 2. Verify GSC data loaded
psql $WAREHOUSE_DSN -c "
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT date) as distinct_dates,
        COUNT(DISTINCT url) as distinct_pages,
        SUM(clicks) as total_clicks
    FROM gsc.fact_gsc_daily
    WHERE date >= '2024-11-01';"

# 3. Run GA4 ingestion (if configured)
python ingestors/ga4/ga4_extractor.py

# 4. Verify GA4 data loaded
psql $WAREHOUSE_DSN -c "
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT date) as distinct_dates,
        COUNT(DISTINCT page_path) as distinct_pages,
        SUM(sessions) as total_sessions
    FROM gsc.fact_ga4_daily
    WHERE date >= '2024-11-01';"
```

**Expected Results:**
- GSC: 1000+ rows, 15 distinct dates, 100+ distinct pages
- GA4: 500+ rows if configured (optional, system works without GA4)
- No data validation errors

**Acceptance Criteria:**
- [ ] GSC data ingested for date range
- [ ] fact_gsc_daily populated with clicks, impressions, CTR
- [ ] fact_ga4_daily populated (if GA4 configured)
- [ ] No null values in required fields

---

### Test 1.3: Unified View Integration
**Objective:** Verify GSC and GA4 data properly joined

```bash
# Query unified view for recent data
psql $WAREHOUSE_DSN -c "
    SELECT 
        date,
        page_path,
        -- GSC metrics
        gsc_clicks,
        gsc_impressions,
        gsc_ctr,
        -- GA4 metrics
        ga_sessions,
        ga_conversions,
        -- Time-series calculations
        gsc_clicks_change_wow,
        ga_conversions_change_wow,
        -- Derived metrics
        opportunity_index,
        conversion_efficiency
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    ORDER BY gsc_clicks DESC
    LIMIT 10;"
```

**Expected Results:**
- All pages have both GSC and GA4 metrics (or 0 if not available)
- WoW calculations populated after 7 days of data
- Derived metrics (opportunity_index, conversion_efficiency) calculated

**Acceptance Criteria:**
- [ ] FULL OUTER JOIN works (no data loss)
- [ ] Time-series fields populated
- [ ] Zero-handling correct (COALESCE used)
- [ ] Performance acceptable (<5s for 100K rows)

---

## PHASE 2: INSIGHT ENGINE (CORE LOGIC)

### Test 2.1: Insight Models & Repository
**Objective:** Verify Pydantic models and database CRUD

```bash
# Run unit tests
pytest tests/test_insight_models.py -v
pytest tests/test_insight_repository.py -v

# Manual test: Create insight programmatically
python -c "
from insights_core.repository import InsightRepository
from insights_core.models import InsightCreate, InsightCategory, InsightSeverity, EntityType, InsightMetrics
import os

repo = InsightRepository(os.environ['WAREHOUSE_DSN'])

# Create test insight
insight_create = InsightCreate(
    property='sc-domain:example.com',
    entity_type=EntityType.PAGE,
    entity_id='/test-page',
    category=InsightCategory.RISK,
    title='Test Traffic Drop',
    description='Test insight for E2E validation',
    severity=InsightSeverity.MEDIUM,
    confidence=0.85,
    metrics=InsightMetrics(
        gsc_clicks=100.0,
        gsc_clicks_change=-25.5,
        window_start='2024-11-01',
        window_end='2024-11-15'
    ),
    window_days=7,
    source='E2ETest'
)

# Insert
insight = repo.create(insight_create)
print(f'✅ Created insight: {insight.id}')

# Retrieve
retrieved = repo.get_by_id(insight.id)
assert retrieved.title == 'Test Traffic Drop', 'Title mismatch'
print(f'✅ Retrieved insight: {retrieved.title}')

# Query
results = repo.query(category=InsightCategory.RISK, limit=5)
print(f'✅ Found {len(results)} risk insights')
"
```

**Expected Results:**
- All Pydantic model validations pass
- Insight created with deterministic ID (SHA256 hash)
- CRUD operations succeed
- Duplicate prevention works (same ID = skip insert)

**Acceptance Criteria:**
- [ ] Models validate all fields correctly
- [ ] Repository connects to database
- [ ] Create/Read/Update/Delete operations work
- [ ] Duplicate detection works (deterministic IDs)
- [ ] Query filtering works (category, severity, status)

---

### Test 2.2: Detector Logic
**Objective:** Verify each detector finds correct insights

```bash
# Run detector unit tests
pytest tests/test_detectors.py -v

# Test AnomalyDetector manually
python -c "
from insights_core.detectors import AnomalyDetector
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
import os

repo = InsightRepository(os.environ['WAREHOUSE_DSN'])
config = InsightsConfig()
detector = AnomalyDetector(repo, config)

# Run detection
insights_created = detector.detect()
print(f'✅ AnomalyDetector created {insights_created} insights')
"

# Verify insights in database
psql $WAREHOUSE_DSN -c "
    SELECT 
        category,
        severity,
        COUNT(*) as count,
        AVG(confidence) as avg_confidence
    FROM gsc.insights
    WHERE source LIKE '%Detector'
    GROUP BY category, severity
    ORDER BY category, severity;"
```

**Expected Results:**
- AnomalyDetector: Finds pages with WoW drops >20%
- DiagnosisDetector: Links diagnoses to anomalies
- OpportunityDetector: Finds impression spikes >50%

**Acceptance Criteria:**
- [ ] AnomalyDetector finds traffic drops (high severity if clicks AND conversions drop)
- [ ] DiagnosisDetector creates insights with `linked_insight_id`
- [ ] OpportunityDetector finds impression spikes
- [ ] All insights read from `vw_unified_page_performance` (not GSC-only views)
- [ ] Confidence scores between 0.0 and 1.0

---

### Test 2.3: Insight Engine Orchestration
**Objective:** Verify engine runs all detectors correctly

```bash
# Test engine
pytest tests/test_insight_engine.py -v

# Run engine manually
python -c "
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig

config = InsightsConfig()
engine = InsightEngine(config)

# Run all detectors
stats = engine.refresh()

print('=== ENGINE EXECUTION STATS ===')
print(f\"Detectors run: {stats['detectors_run']}\")
print(f\"Detectors succeeded: {stats['detectors_succeeded']}\")
print(f\"Total insights: {stats['total_insights_created']}\")
print(f\"Duration: {stats['duration_seconds']:.2f}s\")
print(f\"Insights by detector:\")
for detector, count in stats['insights_by_detector'].items():
    print(f\"  - {detector}: {count}\")
"

# Verify insights created
psql $WAREHOUSE_DSN -c "
    SELECT 
        source,
        category,
        severity,
        COUNT(*) as count
    FROM gsc.insights
    WHERE generated_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    GROUP BY source, category, severity
    ORDER BY source, category, severity;"
```

**Expected Results:**
- Engine runs all 3 detectors successfully
- No detector failures
- Insights created across all categories (risk, opportunity, diagnosis)
- Execution time <30s for typical dataset

**Acceptance Criteria:**
- [ ] All detectors execute without errors
- [ ] Stats returned with counts and timing
- [ ] Insights persisted to database
- [ ] Deterministic IDs prevent duplicates

---

## PHASE 3: MULTI-AGENT SYSTEM

### Test 3.1: Agent Infrastructure
**Objective:** Verify message bus and state management

```bash
# Run agent tests
pytest tests/agents/test_message_bus.py -v
pytest tests/agents/test_state_manager.py -v

# Test message bus
python -c "
from agents.base.message_bus import MessageBus
from agents.base.agent_contract import AgentMessage, MessageType

bus = MessageBus()

# Subscribe handler
def handle_finding(msg):
    print(f'📨 Received: {msg.type} from {msg.source_agent}')

bus.subscribe(MessageType.FINDING, handle_finding)

# Publish message
msg = AgentMessage(
    type=MessageType.FINDING,
    source_agent='test_agent',
    payload={'test': 'data'},
    correlation_id='test-123'
)
bus.publish(msg)
print('✅ Message bus working')
"
```

**Acceptance Criteria:**
- [ ] Message bus publishes/subscribes correctly
- [ ] State manager persists agent state
- [ ] Agent registry tracks agents
- [ ] Message types defined (FINDING, DIAGNOSIS, RECOMMENDATION)

---

### Test 3.2: Individual Agents
**Objective:** Test each agent independently

```bash
# Test Watcher Agent
pytest tests/agents/test_watcher.py -v
python -c "
from agents.watcher.watcher_agent import WatcherAgent
agent = WatcherAgent()
agent.run()
print('✅ Watcher agent executed')
"

# Test Diagnostician Agent  
pytest tests/agents/test_diagnostician.py -v
python -c "
from agents.diagnostician.diagnostician_agent import DiagnosticianAgent
agent = DiagnosticianAgent()
agent.run()
print('✅ Diagnostician agent executed')
"

# Test Strategist Agent
pytest tests/agents/test_strategist.py -v
python -c "
from agents.strategist.strategist_agent import StrategistAgent
agent = StrategistAgent()
agent.run()
print('✅ Strategist agent executed')
"
```

**Expected Results:**
- Watcher: Monitors data quality, generates findings
- Diagnostician: Analyzes findings, produces diagnoses
- Strategist: Creates recommendations from diagnoses

**Acceptance Criteria:**
- [ ] Each agent runs without errors
- [ ] Agents read/write correct database tables
- [ ] Agents publish messages to message bus

---

### Test 3.3: Agent Orchestration
**Objective:** Test Dispatcher coordinating agents

```bash
# Test dispatcher
pytest tests/agents/test_dispatcher.py -v

# Run full agent pipeline
python -c "
from agents.dispatcher.dispatcher_agent import DispatcherAgent

dispatcher = DispatcherAgent()
result = dispatcher.run_pipeline()

print('=== AGENT PIPELINE RESULTS ===')
print(f\"Findings: {result['findings_count']}\")
print(f\"Diagnoses: {result['diagnoses_count']}\")
print(f\"Recommendations: {result['recommendations_count']}\")
print(f\"Duration: {result['duration_seconds']:.2f}s\")
"

# Verify agent outputs
psql $WAREHOUSE_DSN -c "
    SELECT 
        'findings' as type,
        COUNT(*) as count
    FROM gsc.agent_findings
    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    UNION ALL
    SELECT 
        'diagnoses' as type,
        COUNT(*) as count
    FROM gsc.agent_diagnoses
    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    UNION ALL
    SELECT 
        'recommendations' as type,
        COUNT(*) as count
    FROM gsc.agent_recommendations
    WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour';"
```

**Acceptance Criteria:**
- [ ] Dispatcher runs agents in correct order
- [ ] Message bus routes messages correctly
- [ ] State persisted between agent runs
- [ ] Pipeline completes end-to-end

---

## PHASE 4: END-TO-END INTEGRATION

### Test 4.1: Full Pipeline Test
**Objective:** Verify complete data flow from ingestion to insights

```bash
#!/bin/bash
# Full E2E pipeline test

echo "=== PHASE 4.1: FULL PIPELINE TEST ==="

# Step 1: Ingest fresh data
echo "Step 1: Ingesting data..."
python ingestors/api/gsc_api_ingestor.py --date-start $(date -d '30 days ago' +%Y-%m-%d) --date-end $(date +%Y-%m-%d)

# Step 2: Refresh transforms
echo "Step 2: Refreshing transformed views..."
python warehouse/refresh_views.py

# Step 3: Run Insight Engine
echo "Step 3: Running Insight Engine..."
python -m insights_core.cli refresh

# Step 4: Run Multi-Agent System
echo "Step 4: Running agent pipeline..."
python agents/dispatcher/dispatcher_agent.py --mode full

# Step 5: Verify outputs
echo "Step 5: Verifying outputs..."
psql $WAREHOUSE_DSN -c "
    SELECT 
        'gsc_data' as source,
        COUNT(DISTINCT date) as days,
        COUNT(*) as rows,
        MAX(date) as latest_date
    FROM gsc.fact_gsc_daily
    UNION ALL
    SELECT 
        'unified_view' as source,
        COUNT(DISTINCT date) as days,
        COUNT(*) as rows,
        MAX(date) as latest_date
    FROM gsc.vw_unified_page_performance
    UNION ALL
    SELECT 
        'insights' as source,
        COUNT(DISTINCT DATE(generated_at)) as days,
        COUNT(*) as rows,
        MAX(generated_at)::date as latest_date
    FROM gsc.insights
    UNION ALL
    SELECT 
        'agent_findings' as source,
        COUNT(DISTINCT DATE(created_at)) as days,
        COUNT(*) as rows,
        MAX(created_at)::date as latest_date
    FROM gsc.agent_findings;"

echo "✅ Full pipeline test complete!"
```

**Expected Results:**
- Data flows through all stages without errors
- Each component produces expected outputs
- Timing: Full pipeline <5 minutes for 30 days of data

**Acceptance Criteria:**
- [ ] Data ingested successfully
- [ ] Unified view updated
- [ ] Insights generated (anomalies, diagnoses, opportunities)
- [ ] Agents produced findings, diagnoses, recommendations
- [ ] No broken foreign keys or orphaned records

---

### Test 4.2: MCP Interface Test
**Objective:** Verify MCP server exposes insights correctly

```bash
# Start MCP server
python mcp/mcp_server.py &
MCP_PID=$!
sleep 5

# Test MCP tools
python -c "
import requests
import json

# Test health endpoint (MCP server runs on port 8001)
response = requests.get('http://localhost:8001/health')
assert response.status_code == 200, 'Health check failed'
print('✅ MCP server health check passed')

# Test get_insights tool (if MCP supports direct HTTP)
# Note: MCP is typically used via Claude, this is for basic connectivity
print('✅ MCP server running on port 8001')
"

# Kill MCP server
kill $MCP_PID
```

**Acceptance Criteria:**
- [ ] MCP server starts without errors
- [ ] Health endpoint responds
- [ ] Claude can query insights via MCP tools

---

## PHASE 5: PERFORMANCE & RELIABILITY

### Test 5.1: Performance Benchmarks
**Objective:** Ensure system meets performance requirements

```bash
# Benchmark unified view query
psql $WAREHOUSE_DSN -c "\timing on" -c "
    SELECT COUNT(*)
    FROM gsc.vw_unified_page_performance
    WHERE date >= CURRENT_DATE - INTERVAL '30 days';"

# Benchmark insight detection
time python -m insights_core.cli refresh

# Benchmark agent pipeline
time python agents/dispatcher/dispatcher_agent.py --mode full
```

**Performance Targets:**
- Unified view query (30 days): <2s for 100K rows
- Insight detection: <30s for full refresh
- Agent pipeline: <60s for full execution

**Acceptance Criteria:**
- [ ] Queries complete within target times
- [ ] No memory leaks
- [ ] CPU usage reasonable (<80%)

---

### Test 5.2: Error Handling & Recovery
**Objective:** Verify system handles failures gracefully

```bash
# Test database connection failure
echo "Testing connection resilience..."
python -c "
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig

# Use invalid DSN
try:
    config = InsightsConfig(warehouse_dsn='postgresql://invalid:invalid@invalid:5432/invalid')
    engine = InsightEngine(config)
    engine.refresh()
except Exception as e:
    print(f'✅ Correctly handled connection error: {type(e).__name__}')
"

# Test partial data
psql $WAREHOUSE_DSN -c "
    -- Simulate missing GA4 data
    DELETE FROM gsc.fact_ga4_daily WHERE date = CURRENT_DATE;
    
    -- Verify unified view still works (FULL OUTER JOIN)
    SELECT COUNT(*) FROM gsc.vw_unified_page_performance WHERE date = CURRENT_DATE;
"
```

**Acceptance Criteria:**
- [ ] Connection failures handled gracefully
- [ ] Missing GA4 data doesn't break pipeline
- [ ] Retry logic works
- [ ] Errors logged properly

---

### Test 5.3: Data Quality Validation
**Objective:** Verify data quality checks work

```bash
# Run validation scripts
python scripts/validate_data.py

# Check for anomalies in unified view
psql $WAREHOUSE_DSN -c "
    SELECT * FROM gsc.validate_unified_view_time_series()
    WHERE check_status NOT IN ('PASS', 'INFO');"
```

**Acceptance Criteria:**
- [ ] Validation functions return PASS
- [ ] No extreme outliers (>1000% changes)
- [ ] No orphaned records
- [ ] Date ranges consistent

---

## TEST EXECUTION CHECKLIST

### Pre-Test Setup
- [ ] PostgreSQL running and accessible
- [ ] Environment variables set (WAREHOUSE_DSN, GSC_SA credentials)
- [ ] Fresh database (or run migration scripts)
- [ ] Python dependencies installed (`pip install -r requirements.txt`)
- [ ] Docker running (for containerized tests)

### Test Execution Order
1. **Phase 1:** Infrastructure & Data Layer (30 min)
2. **Phase 2:** Insight Engine (20 min)
3. **Phase 3:** Multi-Agent System (20 min)
4. **Phase 4:** End-to-End Integration (30 min)
5. **Phase 5:** Performance & Reliability (20 min)

**Total Time:** ~2 hours for complete E2E test suite

### Post-Test Validation
- [ ] All tests passed
- [ ] Logs reviewed for warnings/errors
- [ ] Database in consistent state
- [ ] No resource leaks (memory, connections)
- [ ] Performance metrics acceptable

---

## AUTOMATED TEST RUNNER

```bash
#!/bin/bash
# run_e2e_tests.sh - Execute complete E2E test suite

set -e  # Exit on any error

echo "======================================"
echo "E2E TEST SUITE - HYBRID PLAN"
echo "======================================"

# Phase 1
echo -e "\n=== PHASE 1: Infrastructure & Data Layer ==="
pytest tests/test_data_validation.py -v
bash tests/e2e/test_data_ingestion.sh

# Phase 2
echo -e "\n=== PHASE 2: Insight Engine ==="
pytest tests/test_insight_models.py tests/test_insight_repository.py tests/test_detectors.py -v
python -m insights_core.cli refresh

# Phase 3
echo -e "\n=== PHASE 3: Multi-Agent System ==="
pytest tests/agents/ -v
python agents/dispatcher/dispatcher_agent.py --mode full

# Phase 4
echo -e "\n=== PHASE 4: End-to-End Integration ==="
bash tests/e2e/test_full_pipeline.sh

# Phase 5
echo -e "\n=== PHASE 5: Performance & Reliability ==="
bash tests/e2e/test_performance.sh

echo -e "\n======================================"
echo "✅ ALL E2E TESTS PASSED!"
echo "======================================"
```

---

## TROUBLESHOOTING

### Common Issues

**Issue:** Unified view returns no data
- **Check:** Run `SELECT COUNT(*) FROM gsc.fact_gsc_daily;`
- **Fix:** Ingest data with `python ingestors/api/gsc_api_ingestor.py`

**Issue:** WoW calculations are NULL
- **Check:** `SELECT COUNT(DISTINCT date) FROM gsc.fact_gsc_daily;`
- **Fix:** Need 7+ days of data for WoW, 28+ days for MoM

**Issue:** Detectors create no insights
- **Check:** `SELECT * FROM gsc.vw_unified_anomalies;`
- **Fix:** May be no anomalies in data (expected if traffic stable)

**Issue:** Agent pipeline fails
- **Check:** `SELECT * FROM gsc.agent_executions ORDER BY started_at DESC LIMIT 5;`
- **Fix:** Review error logs, check database permissions

---

## SUCCESS CRITERIA

### The Hybrid Plan is E2E validated when:

✅ **Data Layer**
- Unified view joins GSC + GA4 correctly
- Time-series calculations work (WoW, MoM)
- Performance acceptable

✅ **Insight Engine**
- All detectors read from unified view (not GSC-only)
- Insights stored in `gsc.insights` table
- Duplicate prevention works

✅ **Multi-Agent System**
- Agents communicate via message bus
- Pipeline executes end-to-end
- Findings → Diagnoses → Recommendations flow

✅ **Integration**
- Full pipeline works: Ingestion → Unified View → Insights → Agents
- MCP interface exposes insights
- Performance meets targets

✅ **Production Readiness**
- Error handling robust
- Data quality validated
- Logging comprehensive
- Documentation complete

---

**End of E2E Testing Plan**
