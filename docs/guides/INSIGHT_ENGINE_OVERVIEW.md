# Insight Engine - Current Implementation

**Document Type**: Technical Reference
**Last Updated**: 2025-01-25
**Status**: Production System Documentation

---

## Executive Summary

The Insight Engine is a sophisticated, multi-layered analytics intelligence system that automatically detects anomalies, diagnoses root causes, identifies growth opportunities, and dispatches actionable insights from SEO and analytics data sources (GSC, GA4, SERP, CWV, PageSpeed).

**Key Capabilities**:
- Automated anomaly detection using statistical and ML methods
- Root cause diagnosis with multi-source correlation
- Growth opportunity identification
- Multi-agent autonomous analysis system
- Flexible notification dispatch system
- REST API for programmatic access
- Deterministic deduplication to prevent noise

---

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
├─────────────────────────────────────────────────────────────┤
│ GSC │ GA4 │ PageSpeed │ SERP APIs │ Content Scraping       │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              UNIFIED DATA LAYER                              │
│           vw_unified_page_performance                        │
│  (FULL OUTER JOIN on date, property, page_path)             │
│  + WoW/MoM calculations + lag values                         │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              INSIGHT ENGINE CORE                             │
├─────────────────────────────────────────────────────────────┤
│  1. AnomalyDetector    → Detects statistical anomalies      │
│  2. DiagnosisDetector  → Root cause analysis                │
│  3. OpportunityDetector → Growth opportunities               │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              INSIGHT REPOSITORY                              │
│                gsc.insights table                            │
│  Deterministic ID (SHA256) prevents duplicates              │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│              DISPATCH SYSTEM                                 │
│  Slack │ Jira │ Email │ Webhook │ Custom                   │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│         USER INTERFACES & INTEGRATIONS                       │
│  REST API │ MCP Tools │ Grafana │ Custom Apps              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Sources

### 1. Google Search Console (GSC)

**Storage**: `gsc.fact_gsc_daily`
**Metrics**:
- Clicks (daily)
- Impressions (daily)
- Average position
- CTR (Click-Through Rate)

**Granularity**: Page × Query × Date

**Update Frequency**: Daily via GA4/GSC ingestion service

---

### 2. Google Analytics 4 (GA4)

**Storage**: `gsc.fact_ga4_daily`
**Metrics**:
- Sessions
- Conversions
- Engagement rate
- Bounce rate
- Average session duration

**Granularity**: Page × Date

**Update Frequency**: Daily via GA4 ingestion service

---

### 3. PageSpeed Insights (Core Web Vitals)

**Storage**: `performance.core_web_vitals`
**Metrics**:
- LCP (Largest Contentful Paint)
- FID (First Input Delay)
- CLS (Cumulative Layout Shift)
- Lighthouse Performance Score
- Lighthouse SEO Score

**Implementation**: `insights_core/cwv_monitor.py`

**Update Frequency**: Configurable (typically weekly or on-demand)

---

### 4. SERP Position Tracking

**Current Implementation**: SERPStack API (100 queries/month limit)

**Storage**: `serp.position_history`
**Metrics**:
- Ranking position by keyword
- Competitor positions
- SERP features captured

**Implementation Files**:
- `insights_core/serp_tracker.py` - Multi-API support (ValueSERP, SerpAPI, DataForSEO)
- `insights_core/gsc_serp_tracker.py` - Hybrid GSC + SERP API mode

**Supported APIs**:
- SERPStack (currently active)
- ValueSERP (configured but not active)
- SerpAPI (configured but not active)
- DataForSEO (configured but not active)

---

### 5. Content Scraping & Analysis

**Implementation**: `insights_core/content_analyzer.py`

**Extracted Data**:
- Page title
- Meta description
- H1, H2, H3 headings
- Body text content
- Content embeddings (384-dimensional vectors via sentence-transformers)

**Analysis Features**:
- Readability scoring (Flesch Reading Ease, Flesch-Kincaid Grade)
- Quality scoring via Ollama LLM
- Topic extraction
- SEO optimization checks
- Sentiment analysis

**Status**: Implementation exists but **integration with insight engine needs verification**

---

## Unified Data View

### vw_unified_page_performance

**File**: [sql/05_unified_view.sql](sql/05_unified_view.sql)

**Join Strategy**:
```sql
FULL OUTER JOIN gsc.fact_gsc_daily g
  ON ga.date = g.date
  AND ga.property = g.property
  AND ga.page_path = g.page
```

**URL Consolidation Strategy**:
- **GSC**: Provides full URL (e.g., `https://products.aspose.net/words/mail-merge/`)
- **GA4**: Provides `hostname` + `page_path` separately (needs concatenation)
- **Join Key**: Uses `page_path` (without protocol/domain for flexibility)

**Computed Metrics**:
- Week-over-Week (WoW) changes: `gsc_clicks_change_wow`, `gsc_impressions_change_wow`, `ga_conversions_change_wow`
- Month-over-Month (MoM) changes: `gsc_clicks_change_mom`, etc.
- Lagged values: `gsc_clicks_7d_ago`, `gsc_clicks_28d_ago`
- Derived flags: `is_striking_distance` (positions 11-20)

**Window Functions**:
```sql
WINDOW w_page AS (
  PARTITION BY property, page_path
  ORDER BY date
  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
```

---

## Three Sequential Detectors

### 1. AnomalyDetector

**File**: [insights_core/detectors/anomaly.py](insights_core/detectors/anomaly.py)

**Purpose**: Detect statistical anomalies in traffic and conversion metrics

**Data Source**: `gsc.vw_unified_page_performance`

**Detection Rules**:

| Condition | Category | Severity | Confidence |
|-----------|----------|----------|------------|
| Clicks ↓ >20% AND Conversions ↓ >20% | RISK | HIGH | 0.85-0.9 |
| Clicks ↓ >20% OR Conversions ↓ >20% | RISK | MEDIUM | 0.75-0.85 |
| Impressions ↑ >50% | OPPORTUNITY | MEDIUM | 0.75-0.8 |

**Configuration** (via `InsightsConfig`):
- `risk_threshold_clicks_pct = -20.0`
- `risk_threshold_conversions_pct = -20.0`
- `opportunity_threshold_impressions_pct = 50.0`

**Output Example**:
```json
{
  "category": "risk",
  "severity": "high",
  "title": "Traffic Drop Detected",
  "description": "Page '/blog/seo-tips/' experienced 35% clicks drop and 28% conversion drop",
  "confidence": 0.89,
  "metrics": {
    "gsc_clicks_change_wow": -35.2,
    "ga_conversions_change_wow": -28.1,
    "current_clicks": 450,
    "previous_clicks": 693
  }
}
```

---

### 2. DiagnosisDetector

**File**: [insights_core/detectors/diagnosis.py](insights_core/detectors/diagnosis.py)

**Purpose**: Diagnose root causes for RISK insights

**Algorithm**:
1. Fetch all `status='new'` and `category='risk'` insights
2. For each risk insight:
   - Retrieve page-level data (position, engagement, modification date)
   - Test hypotheses in order:
     - **Hypothesis 1: Ranking Issue** - Position worsened by >10 spots
     - **Hypothesis 2: Engagement Issue** - Engagement rate dropped >15%
     - **Hypothesis 3: Recent Content Change** - Page modified within 48 hours
   - Create DIAGNOSIS insight with `linked_insight_id` pointing to original RISK
   - Update original RISK status to `'diagnosed'`

**Multi-Source Analysis**:
- Position data from GSC
- Engagement data from GA4
- Content modification timestamps
- Historical baseline comparisons

**Output Example**:
```json
{
  "category": "diagnosis",
  "severity": "high",
  "title": "Root Cause: Ranking Loss",
  "description": "Page position dropped from #3 to #15 (12 spots) for primary keyword",
  "confidence": 0.82,
  "linked_insight_id": "abc123...",
  "metrics": {
    "position_change": 12,
    "previous_position": 3,
    "current_position": 15,
    "hypothesis": "ranking_issue"
  }
}
```

---

### 3. OpportunityDetector

**File**: [insights_core/detectors/opportunity.py](insights_core/detectors/opportunity.py)

**Purpose**: Identify growth and optimization opportunities

**Two Strategies**:

**Strategy 1: Striking Distance**
- Target: Pages ranking positions 11-20 with >100 impressions
- Insight: Small ranking improvement could yield significant traffic gains
- Confidence: 0.8

**Strategy 2: Content Gaps**
- Target: Pages with >500 impressions but <40% engagement rate
- Insight: Content may not match user intent
- Confidence: 0.65

**Output Example**:
```json
{
  "category": "opportunity",
  "severity": "medium",
  "title": "Striking Distance Opportunity",
  "description": "Page '/products/api/' ranks #14 with 850 impressions - small improvement could 2x traffic",
  "confidence": 0.8,
  "metrics": {
    "current_position": 14,
    "impressions": 850,
    "potential_traffic_gain": "2x-3x"
  }
}
```

---

## Database Schema

### Core Insights Table

**File**: [sql/11_insights_table.sql](sql/11_insights_table.sql)

**Schema**:
```sql
CREATE TABLE IF NOT EXISTS gsc.insights (
    id VARCHAR(64) PRIMARY KEY,          -- Deterministic SHA256 hash
    generated_at TIMESTAMP NOT NULL,     -- When insight was created

    -- Entity identification
    property VARCHAR(500) NOT NULL,      -- Website URL
    entity_type VARCHAR(50),             -- page, query, directory, property
    entity_id TEXT,                      -- URL, query term, or path

    -- Classification
    category VARCHAR(50),                -- risk, opportunity, trend, diagnosis
    title VARCHAR(200),                  -- Human-readable title
    description TEXT,                    -- Full explanation
    severity VARCHAR(20),                -- low, medium, high
    confidence NUMERIC(3,2),             -- 0.0-1.0 confidence score

    -- Data storage
    metrics JSONB,                       -- Flexible detector-specific metrics
    window_days INTEGER,                 -- Analysis window (7, 28, 90 days)
    source VARCHAR(100),                 -- Which detector created it

    -- Workflow
    status VARCHAR(50),                  -- new, investigating, diagnosed, actioned, resolved
    linked_insight_id VARCHAR(64),       -- Foreign key to parent insight

    -- Audit fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Deterministic ID Generation**:
```python
# Prevents duplicate insights
insight_id = SHA256(
    f"{property}|{entity_type}|{entity_id}|{category}|{source}|{window_days}"
)
```

**Key Features**:
- Same insight generated twice = UPDATE existing (idempotent)
- Different window_days = Different ID (separate insights)
- `ON CONFLICT (id) DO UPDATE` ensures no duplicates

**Indexes**:
- `idx_insights_property` - Fast filtering by website
- `idx_insights_category` - Fast filtering by category
- `idx_insights_status` - Fast filtering by workflow status
- `idx_insights_severity` - Fast filtering by severity
- `idx_insights_entity` - Find all insights for specific page/query
- `idx_insights_metrics_gin` - JSONB search within metrics

**Views**:
- `vw_insights_actionable` - Shows NEW or DIAGNOSED insights, sorted by severity
- `vw_insights_stats` - Aggregated statistics by property/category/severity/status

---

### Related Schema Tables

| Table | Purpose | SQL File |
|-------|---------|----------|
| `gsc.agent_findings` | Findings from monitoring agents | 07_agent_findings.sql |
| `gsc.agent_diagnoses` | Root cause analyses from agents | 08_agent_diagnoses.sql |
| `gsc.agent_recommendations` | Actionable recommendations | 09_agent_recommendations.sql |
| `gsc.agent_executions` | Execution tracking and results | 10_agent_executions.sql |
| `anomaly.detections` | Anomaly detection records | 22_anomaly_schema.sql |
| `anomaly.baselines` | Statistical baselines for metrics | 22_anomaly_schema.sql |
| `intelligence.traffic_forecasts` | Prophet-based forecasts | 14_forecasts_schema.sql |
| `serp.position_history` | SERP ranking history | 16_serp_schema.sql |
| `performance.core_web_vitals` | CWV metrics over time | 17_performance_schema.sql |

---

## AI/ML Components

### Statistical & Machine Learning Methods

| Module | Technology | Purpose | Status |
|--------|-----------|---------|--------|
| `anomaly_detector.py` | Prophet + IsolationForest + Z-score | Multi-method anomaly detection | ✅ Implemented |
| `forecasting.py` | Prophet (Facebook time series) | Traffic forecasting with prediction intervals | ✅ Implemented |
| `embeddings.py` | sentence-transformers + pgvector | Content similarity & semantic search | ✅ Implemented |
| `causal_analyzer.py` | CausalImpact (Bayesian structural) | Measure true causal effect of changes | ✅ Implemented |
| `topic_clustering.py` | K-means + DBSCAN on embeddings | Auto-organize content into topics | ✅ Implemented |
| `nl_query.py` | Ollama LLM | Natural language → SQL queries | ✅ Implemented |
| `content_analyzer.py` | Ollama + readability + textstat | Content quality scoring | ✅ Implemented |
| `serp_tracker.py` | Multiple SERP APIs | Ranking position tracking | ⚠️ Partial (SERPStack only) |
| `cwv_monitor.py` | PageSpeed Insights API | Core Web Vitals monitoring | ✅ Implemented |
| `gsc_serp_tracker.py` | Hybrid GSC + SERP API | Combined ranking tracking | ⚠️ Needs activation |

### Prophet Forecasting

**File**: [insights_core/forecasting.py](insights_core/forecasting.py)

**Features**:
- Automatic seasonality detection (daily, weekly, yearly)
- Trend decomposition
- Prediction intervals (lower/upper bounds at 95% confidence)
- Holiday/special event handling
- Fewer false positives than simple Z-score methods

**Output Storage**: `intelligence.traffic_forecasts`

**Fields**:
- `forecast_value` - Predicted value
- `lower_bound`, `upper_bound` - Confidence interval
- `is_anomaly` - Flag when actual falls outside interval
- `trend_component`, `weekly_seasonal`, `yearly_seasonal` - Decomposition

### Anomaly Detection Methods

**File**: [insights_core/anomaly_detector.py](insights_core/anomaly_detector.py)

**Three Complementary Approaches**:

1. **Statistical (Z-score)**
   - Threshold: 2.5σ (99.4% confidence)
   - Fast, interpretable
   - Assumes normal distribution

2. **Isolation Forest (Scikit-learn)**
   - Multivariate anomaly detection
   - Detects subtle combinations of metric changes
   - Contamination parameter: 0.1 (10% of data as potential anomalies)

3. **Prophet Forecast-Based**
   - Compares actual vs predicted values
   - Uses confidence intervals
   - Captures seasonality and trends

**Combined Scoring**:
- Run all three methods
- Cross-validate (higher confidence when 2+ methods agree)
- Weighted average for final severity

### Embeddings & Semantic Analysis

**File**: [insights_core/embeddings.py](insights_core/embeddings.py)

**Default Model**: `sentence-transformers/all-MiniLM-L6-v2`
- 384-dimensional vectors
- CPU-friendly, fast inference
- Trained on 1B+ sentence pairs

**Optional Model**: Ollama `nomic-embed-text`
- 768-dimensional vectors
- Local processing (privacy)
- No external API dependencies

**Use Cases**:
1. Content cannibalization detection (find duplicate/similar pages)
2. Topic clustering (auto-organize content)
3. Semantic search ("find pages about X topic")
4. Content gap analysis (identify missing topics)

**Storage**: PostgreSQL `pgvector` extension

### Causal Impact Analysis

**File**: [insights_core/causal_analyzer.py](insights_core/causal_analyzer.py)

**Technology**: CausalImpact library (Bayesian structural time series)

**Purpose**: Measure true causal effect of interventions (not just correlation)

**Example Workflow**:
1. Implement content fix on Jan 15
2. Wait 14 days for data
3. Run causal impact analysis
4. Result: "+150 clicks (+12% vs expected) with 95% confidence"

**Output Metrics**:
- Absolute impact (e.g., +150 clicks)
- Relative impact (e.g., +12% vs counterfactual)
- 95% confidence interval
- Cumulative impact over time period
- P-value for statistical significance

---

## Multi-Agent System

### Agent Architecture

**Base Contract**: [agents/base/agent_contract.py](agents/base/agent_contract.py)

All agents implement:
```python
class AgentContract(ABC):
    async def initialize(self) -> bool
    async def process(self, input_data: Dict) -> Dict
    async def health_check(self) -> AgentHealth
    async def shutdown(self) -> bool
```

**Agent Lifecycle**:
```
INITIALIZED → RUNNING → PROCESSING → IDLE → SHUTDOWN
                ↓
              ERROR (with auto-recovery)
```

**Health Monitoring**:
- Status tracking (operational state)
- Uptime seconds
- Last heartbeat timestamp
- Error count (total errors encountered)
- Processed count (total items handled)
- Memory usage (MB)
- CPU usage (percentage)

### Four Core Agents

**1. Watcher Agent**

**File**: [agents/watcher/watcher_agent.py](agents/watcher/watcher_agent.py)

**Role**: Continuous monitoring and anomaly detection

**Components**:
- `AnomalyDetector` - Statistical anomaly detection
- `TrendAnalyzer` - Identify multi-day trends
- `AlertManager` - Create and manage alerts

**Trigger Conditions**:
- Scheduled (periodic checks)
- On-demand (manual trigger)
- Event-driven (data update webhook)

**Output**: Alert objects, trend reports, findings stored in `gsc.agent_findings`

---

**2. Diagnostician Agent**

**File**: [agents/diagnostician/diagnostician_agent.py](agents/diagnostician/diagnostician_agent.py)

**Role**: Root cause analysis for detected anomalies

**Components**:
- `RootCauseAnalyzer` - Hypothesis testing framework
- `CorrelationEngine` - Multi-metric correlation analysis
- `IssueClassifier` - Categorize issues by type

**Trigger**: On alert/finding from Watcher Agent

**Output**: Diagnosis insights with confidence scores, stored in `gsc.agent_diagnoses`

**Analysis Methods**:
- Statistical correlation analysis
- Time-series causality testing
- Multi-source data triangulation
- Historical pattern matching

---

**3. Strategist Agent**

**File**: [agents/strategist/strategist_agent.py](agents/strategist/strategist_agent.py)

**Role**: Generate actionable recommendations

**Components**:
- `RecommendationEngine` - Create specific action items
- `ImpactEstimator` - Estimate ROI and traffic impact
- `Prioritizer` - Score and rank recommendations

**Trigger**: On diagnosis from Diagnostician Agent

**Output**: Ranked action items with impact estimates, stored in `gsc.agent_recommendations`

**Recommendation Types**:
- Content optimization (update title, meta, headings)
- Technical fixes (improve CWV, fix broken links)
- Link building (identify backlink opportunities)
- Content creation (fill content gaps)
- SERP optimization (improve featured snippet capture)

---

**4. Dispatcher Agent**

**File**: [agents/dispatcher/dispatcher_agent.py](agents/dispatcher/dispatcher_agent.py)

**Role**: Execute approved recommendations

**Components**:
- `ExecutionEngine` - Run automated actions
- `Validator` - Pre-execution validation and safety checks
- `OutcomeMonitor` - Track results and measure impact

**Trigger**: On approved recommendation (requires human approval flag)

**Output**: Execution results, impact validation, stored in `gsc.agent_executions`

**Execution Capabilities**:
- API calls to content management systems
- Database updates
- File system operations (with safety checks)
- Webhook notifications
- Third-party service integrations

---

### Orchestration Layer

**Supervisor Agent**: [agents/orchestration/supervisor_agent.py](agents/orchestration/supervisor_agent.py)

**Responsibilities**:
- Coordinate multi-agent workflows
- Manage agent lifecycle (start, stop, restart)
- Handle failures and retries
- Load balancing across agents
- Event routing and message passing

**LangGraph Integration**:
- State-based workflow orchestration
- DAG (Directed Acyclic Graph) execution
- Parallel execution where possible
- Conditional branching based on results
- Error handling and recovery strategies

**Specialist Agents** (for advanced analysis):
- `SerpAnalystAgent` - SERP ranking and competitor analysis
- `PerformanceAgent` - Core Web Vitals optimization
- `ContentOptimizerAgent` - Content quality improvement
- `ImpactValidatorAgent` - ROI validation and A/B testing

---

## Dispatcher & Notification System

### InsightDispatcher

**File**: [insights_core/dispatcher.py](insights_core/dispatcher.py)

**Routing Rules**: `category + severity → channels`

**Default Configuration**:
```python
DEFAULT_ROUTING_RULES = {
    'risk': {
        'high': ['slack', 'email'],      # Immediate notification
        'medium': ['email'],              # Email digest
        'low': []                         # No notification
    },
    'opportunity': {
        'high': ['slack'],                # Slack notification
        'medium': ['email'],              # Email digest
        'low': []
    },
    'diagnosis': {
        'high': ['jira'],                 # Create issue ticket
        'medium': ['email'],              # Email notification
        'low': []
    }
}
```

**Key Features**:
- Pluggable channel architecture (easy to add new channels)
- Retry logic with exponential backoff (1s, 2s, 4s, 8s)
- Dry-run mode for testing
- Rate limiting to prevent spam
- Batch processing for efficiency

**Methods**:
- `dispatch(insight)` - Send single insight
- `dispatch_batch(insights)` - Send multiple insights efficiently
- `dispatch_recent_insights(hours)` - Dispatch all NEW insights from last N hours
- `test_routing(insight)` - Verify routing without sending

### Channel Implementations

**1. Slack Channel** ([insights_core/channels/slack.py](insights_core/channels/slack.py))
- Rich Slack blocks with colors
- Severity-based color coding (red=high, yellow=medium, blue=low)
- Formatted sections with fields
- Click for more details link

**2. Jira Channel** ([insights_core/channels/jira.py](insights_core/channels/jira.py))
- Auto-create issue tickets
- Labels: category, severity, property
- Links related issues over time
- Automatic assignee routing

**3. Email Channel** ([insights_core/channels/email.py](insights_core/channels/email.py))
- HTML email templates
- Configurable recipients per property
- Digest mode (batch multiple insights)
- Plain-text fallback

**4. Webhook Channel** ([insights_core/channels/webhook.py](insights_core/channels/webhook.py))
- JSON payload with full insight data
- Custom integration points
- Retry-safe (idempotent)
- Signature verification

**5. Base Channel Interface** ([insights_core/channels/base.py](insights_core/channels/base.py))
```python
class Channel(ABC):
    @abstractmethod
    def send(self, insight: Insight) -> DispatchResult

    @abstractmethod
    def format_message(self, insight: Insight) -> Any

    @abstractmethod
    def validate_config(self) -> bool
```

---

## REST API

### Insights API Endpoints

**File**: [insights_api/insights_api.py](insights_api/insights_api.py)

**Base URL**: `/api`

**Endpoints**:

| Endpoint | Method | Description | Query Parameters |
|----------|--------|-------------|------------------|
| `/api/health` | GET | Health check + insight count | None |
| `/api/stats` | GET | Repository statistics | `property` (optional) |
| `/api/insights` | GET | Query insights with filters | See table below |
| `/api/insights/{insight_id}` | GET | Get specific insight by ID | None |
| `/api/insights/category/{category}` | GET | Filter by category | `property`, `severity`, `limit`, `offset` |
| `/api/insights/status/{status}` | GET | Filter by workflow status | `property`, `limit`, `offset` |
| `/api/insights/severity/{severity}` | GET | Filter by severity level | `property`, `limit`, `offset` |

**Query Parameters for `/api/insights`**:

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `property` | string | Website URL | `https://example.com` |
| `category` | string | Insight category | `risk`, `opportunity`, `diagnosis` |
| `status` | string | Workflow status | `new`, `investigating`, `diagnosed`, `actioned`, `resolved` |
| `severity` | string | Severity level | `low`, `medium`, `high` |
| `entity_type` | string | Entity type | `page`, `query`, `directory`, `property` |
| `limit` | integer | Results per page (max 1000) | `50` |
| `offset` | integer | Pagination offset | `0` |

**Response Format**:
```json
{
    "status": "success",
    "count": 42,
    "limit": 100,
    "offset": 0,
    "data": [
        {
            "id": "abc123def456...",
            "generated_at": "2025-01-15T08:30:00Z",
            "property": "https://example.com",
            "entity_type": "page",
            "entity_id": "/blog/seo-tips/",
            "category": "risk",
            "title": "Traffic Drop Detected",
            "description": "Page experienced significant traffic decline...",
            "severity": "high",
            "confidence": 0.89,
            "metrics": {
                "gsc_clicks_change_wow": -35.2,
                "ga_conversions_change_wow": -28.1
            },
            "window_days": 7,
            "source": "AnomalyDetector",
            "status": "new",
            "linked_insight_id": null,
            "created_at": "2025-01-15T08:30:00Z",
            "updated_at": "2025-01-15T08:30:00Z"
        }
    ]
}
```

**Available Categories**:
- `risk` - Problems detected (traffic drops, ranking losses, conversion declines)
- `opportunity` - Growth potential (striking distance, content gaps)
- `diagnosis` - Root cause analysis (linked to risk insights)
- `trend` - Pattern analysis (currently not generated by default detectors, reserved for future use)

---

## Configuration

### InsightsConfig

**File**: [insights_core/config.py](insights_core/config.py)

**Configuration Sources** (in priority order):
1. Environment variables
2. Configuration file (`.env` or custom)
3. Hardcoded defaults

**Key Settings**:

```python
class InsightsConfig:
    # Database
    warehouse_dsn: str  # PostgreSQL connection string

    # Detection thresholds
    risk_threshold_clicks_pct: float = -20.0           # % drop to trigger risk
    risk_threshold_conversions_pct: float = -20.0      # % conversion drop
    opportunity_threshold_impressions_pct: float = 50.0  # % impression increase

    # Confidence & quality
    min_confidence_for_action: float = 0.7             # Minimum confidence to act
    min_data_points_for_detection: int = 7             # Need 7 days minimum

    # Retention
    insights_retention_days: int = 90                  # Delete old insights

    # Scheduler
    scheduler_enabled: bool = True                     # Enable automatic runs
    scheduler_cron: str = "0 2 * * *"                 # Daily at 2 AM UTC

    # Dispatcher
    dispatcher_enabled: bool = False                   # Enable notifications
    dispatcher_dry_run: bool = False                   # Test mode
    dispatcher_rate_limit: int = 100                   # Max dispatches/hour
```

**Environment Variables**:
```bash
# Database
WAREHOUSE_DSN=postgresql://user:pass@localhost:5432/gsc_warehouse

# Detection thresholds
RISK_THRESHOLD_CLICKS_PCT=-20.0
RISK_THRESHOLD_CONVERSIONS_PCT=-20.0
OPPORTUNITY_THRESHOLD_IMPRESSIONS_PCT=50.0

# Scheduler
SCHEDULER_ENABLED=true
SCHEDULER_CRON="0 2 * * *"

# Dispatcher
DISPATCHER_ENABLED=false
DISPATCHER_DRY_RUN=false

# Channel configs
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
JIRA_API_URL=https://your-domain.atlassian.net
JIRA_API_TOKEN=your-token
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

---

## Execution Workflow

### Daily Automated Run

**Trigger**: Cron scheduler at 2 AM UTC (configurable via `SCHEDULER_CRON`)

**Workflow**:
```
1. InsightEngine.refresh()
   ├─ Query vw_unified_page_performance (last 7 days)
   │
   ├─ AnomalyDetector.detect()
   │  ├─ Find pages: clicks↓20%, impressions↑50%, conversions↓20%
   │  ├─ Generate InsightCreate objects
   │  ├─ Call InsightRepository.create() for each
   │  └─ Return count (e.g., "Created 42 insights")
   │
   ├─ DiagnosisDetector.detect()
   │  ├─ Query: SELECT * FROM gsc.insights WHERE status='new' AND category='risk'
   │  ├─ For each risk:
   │  │  ├─ Fetch page data (position, engagement, modification)
   │  │  ├─ Test 3 hypotheses (ranking, engagement, content)
   │  │  ├─ Create diagnosis with linked_insight_id=risk.id
   │  │  └─ Update risk status → 'diagnosed'
   │  └─ Return count (e.g., "Created 28 diagnoses")
   │
   └─ OpportunityDetector.detect()
      ├─ Find striking distance pages (positions 11-20)
      ├─ Find content gaps (>500 impressions, <40% engagement)
      ├─ Generate opportunity insights
      └─ Return count (e.g., "Created 15 opportunities")

2. InsightDispatcher.dispatch_recent_insights()
   ├─ Query: SELECT * WHERE generated_at >= NOW() - 24h AND status='new'
   ├─ For each insight:
   │  ├─ Determine routing: category + severity → channels
   │  ├─ Send to Slack (if high severity risk/opportunity)
   │  ├─ Send to Email (if medium severity)
   │  ├─ Send to Jira (if high severity diagnosis)
   │  └─ Record dispatch result
   └─ Return summary (e.g., "Dispatched 85 insights to 3 channels")

3. Return execution statistics:
   {
     "duration_seconds": 12.4,
     "total_insights_created": 85,
     "insights_by_detector": {
       "AnomalyDetector": 42,
       "DiagnosisDetector": 28,
       "OpportunityDetector": 15
     },
     "errors": []
   }
```

---

## Single-Source vs Multi-Source Insights

### Single-Source Insights

**Examples**:
- ✅ **GSC Only**: "Clicks down 25% for page X"
- ✅ **GA4 Only**: "Conversion rate dropped from 3.2% to 1.8%"
- ✅ **PageSpeed Only**: "LCP degraded from 1.2s to 2.8s"
- ✅ **SERP Only**: "Ranking dropped from #3 to #8"

**Characteristics**:
- Fast to detect (single data source query)
- Clear signal
- May lack context for root cause

### Multi-Source Insights (Most Valuable)

**Examples**:
- ⭐ **GSC + GA4**: "Traffic drop (GSC) + Engagement drop (GA4) = Content quality issue"
- ⭐ **GSC + GSC**: "Impressions up (GSC) + CTR down (GSC) = Meta tag issue"
- ⭐ **GSC + GA4 + Content**: "Ranking drop + No content change + High engagement = Algorithm update"
- ⭐ **CWV + GSC**: "CWV degradation + Traffic drop = Performance issue impacting SEO"

**Characteristics**:
- Higher confidence (cross-validated across sources)
- Better context for root cause
- More actionable (specific fix identified)

**How It Works**:
- `vw_unified_page_performance` provides unified view of GSC + GA4
- `DiagnosisDetector` queries multiple data sources for context
- Hypothesis testing uses multi-source evidence
- Confidence scoring increases with multi-source validation

---

## Current Limitations & Known Issues

### 1. SERP Tracking Limitations
- **Issue**: SERPStack provides only 100 queries/month
- **Impact**: Cannot track all important keywords continuously
- **Workaround**: GSC provides position data (but limited to top 1000 queries)
- **Status**: ⚠️ Needs enhancement

### 2. Content Analysis Integration
- **Issue**: Content analyzer exists but not fully integrated with insight engine
- **Impact**: Missing content-based insights (readability issues, quality problems)
- **Status**: ⚠️ Needs verification and activation

### 3. Notification Channels
- **Issue**: Multiple channels implemented but may not all be needed
- **Impact**: Configuration overhead
- **Status**: ⚠️ Needs prioritization

### 4. Scheduler Timezone
- **Issue**: Currently set to 2 AM UTC
- **Impact**: May not align with business timezone (Pakistan = UTC+5)
- **Status**: ⚠️ Needs configuration update

### 5. URL Consolidation Strategy
- **Issue**: GA4 provides hostname + page_path separately, GSC provides full URL
- **Impact**: Join complexity, potential for mismatches
- **Status**: ✅ Working but needs review for edge cases

### 6. Real-Time Detection
- **Issue**: Currently batch-based (daily runs)
- **Impact**: Delayed detection of critical issues
- **Status**: ⚠️ Future enhancement needed for real-time streaming

### 7. Agent Logic Maturity
- **Issue**: Agents exist but logic depth varies
- **Impact**: May miss subtle patterns or complex relationships
- **Status**: ⚠️ Needs testing and refinement

---

## Performance Characteristics

### Query Performance
- **Unified View Query**: ~2-5 seconds for 7-day window, single property
- **Anomaly Detection**: ~5-10 seconds for 1000 pages
- **Diagnosis Detection**: ~10-20 seconds (depends on number of risks)
- **Full Refresh**: ~30-60 seconds for typical site

### Data Volume Capacity
- **Tested**: Up to 100,000 pages per property
- **Expected**: Can scale to 1M+ pages with proper indexing
- **Bottleneck**: JSONB queries on metrics field

### Insight Volume
- **Typical**: 50-150 insights/day for active site
- **Peak**: Up to 500 insights/day during major algorithm updates
- **Storage**: ~1MB per 1000 insights

---

## Security & Privacy

### Data Access
- **Database**: PostgreSQL with user authentication
- **API**: No authentication currently implemented ⚠️
- **Recommendation**: Add API key or OAuth for production

### Sensitive Data
- **No PII**: System does not store user-level data
- **Aggregated Only**: All metrics are page-level or higher
- **Content**: Page content stored for analysis (public pages only)

### API Security
- **CORS**: Not configured ⚠️
- **Rate Limiting**: Implemented in dispatcher, not in API ⚠️
- **Recommendation**: Add rate limiting middleware for production

---

## Monitoring & Observability

### Grafana Dashboards

**Available Dashboards**:
- `application-metrics.json` - Insight engine execution metrics
- `service-health.json` - Service availability and health
- `alert-status.json` - Alert status and dispatch tracking
- `hybrid-overview.json` - Combined GSC + GA4 overview

**Metrics Tracked**:
- Insight creation count by detector
- Detection execution duration
- Dispatch success/failure rates
- API request rates and latencies
- Database query performance

### Prometheus Metrics

**File**: [prometheus/prometheus.yml](prometheus/prometheus.yml)

**Scraped Metrics**:
- `insight_engine_refresh_duration_seconds` - Execution time
- `insight_engine_insights_created_total` - Count by detector
- `insight_engine_dispatch_success_total` - Successful dispatches
- `insight_engine_dispatch_failure_total` - Failed dispatches
- `insight_engine_detector_errors_total` - Detector errors

### Health Checks

**Endpoint**: `GET /api/health`

**Response**:
```json
{
    "status": "healthy",
    "timestamp": "2025-01-15T10:30:00Z",
    "insight_count": 1247,
    "services": {
        "database": "connected",
        "insight_engine": "running",
        "dispatcher": "enabled"
    }
}
```

---

## Testing

### Unit Tests

**Directory**: [tests/insights_core/](tests/insights_core/)

**Coverage**:
- ✅ Detector logic
- ✅ Repository CRUD operations
- ✅ Insight model validation
- ✅ Configuration loading
- ⚠️ Dispatcher channels (partial)
- ⚠️ Agent logic (partial)

### Integration Tests

**Directory**: [tests/integration/](tests/integration/)

**Coverage**:
- ✅ Database integration
- ✅ API endpoints
- ⚠️ End-to-end workflow (partial)
- ⚠️ Multi-agent orchestration (minimal)

### E2E Tests

**File**: [tests/e2e/e2e_test_enhanced.py](tests/e2e/e2e_test_enhanced.py)

**Coverage**:
- Data ingestion → Insight generation → Dispatch
- Full workflow validation
- Performance benchmarking

---

## Deployment

### Docker Services

**File**: [docker-compose.yml](docker-compose.yml)

**Relevant Services**:
- `insights_engine` - Main insight engine service
- `insights_api` - REST API service
- `scheduler` - Cron-based task scheduler
- `postgres` - Database
- `prometheus` - Metrics collection
- `grafana` - Dashboards

**Startup**:
```bash
docker-compose up -d insights_engine insights_api
```

### Configuration Management

**Environment Files**:
- `.env` - Main configuration (development)
- `.env.production.template` - Production template

**Required Variables**:
```bash
WAREHOUSE_DSN=postgresql://...
SCHEDULER_CRON="0 2 * * *"
DISPATCHER_ENABLED=true
```

---

## Summary Statistics

### Implementation Completeness

| Component | Status | Notes |
|-----------|--------|-------|
| **Data Sources** | | |
| ├─ GSC | ✅ Complete | Daily ingestion active |
| ├─ GA4 | ✅ Complete | Daily ingestion active |
| ├─ PageSpeed/CWV | ✅ Complete | On-demand collection |
| ├─ SERP APIs | ⚠️ Partial | SERPStack only, 100/month limit |
| └─ Content Scraping | ⚠️ Needs verification | Module exists, integration unclear |
| **Detectors** | | |
| ├─ AnomalyDetector | ✅ Complete | Statistical detection working |
| ├─ DiagnosisDetector | ✅ Complete | Root cause analysis working |
| └─ OpportunityDetector | ✅ Complete | Growth opportunities working |
| **AI/ML Components** | | |
| ├─ Prophet Forecasting | ✅ Complete | Time series forecasting |
| ├─ Anomaly Detection | ✅ Complete | Multi-method approach |
| ├─ Embeddings | ✅ Complete | Content similarity |
| ├─ Causal Analysis | ✅ Complete | Impact measurement |
| └─ NL Query | ✅ Complete | Ollama integration |
| **Agents** | | |
| ├─ Watcher | ⚠️ Needs testing | Implementation exists |
| ├─ Diagnostician | ⚠️ Needs testing | Implementation exists |
| ├─ Strategist | ⚠️ Needs testing | Implementation exists |
| └─ Dispatcher | ⚠️ Needs testing | Implementation exists |
| **Dispatch Channels** | | |
| ├─ Slack | ✅ Complete | But may not be needed |
| ├─ Jira | ✅ Complete | But may not be needed |
| ├─ Email | ✅ Complete | But may not be needed |
| └─ Webhook | ✅ Complete | Preferred for custom integration |
| **API** | | |
| └─ REST API | ✅ Complete | All endpoints working |
| **Database** | | |
| └─ Schemas | ✅ Complete | All tables created |
| **Monitoring** | | |
| ├─ Prometheus | ✅ Complete | Metrics collection active |
| └─ Grafana | ✅ Complete | Dashboards available |

### Code Statistics

- **Total Insight Engine Files**: 45+
- **Lines of Code**: ~15,000 (insight engine only)
- **Database Tables**: 25+ (insights + related)
- **AI/ML Modules**: 10
- **Agents**: 4 core + 4 specialist
- **API Endpoints**: 7
- **Dispatch Channels**: 5

---

## References

### Key Files

**Core Engine**:
- [insights_core/engine.py](insights_core/engine.py) - Main orchestrator
- [insights_core/models.py](insights_core/models.py) - Data models
- [insights_core/repository.py](insights_core/repository.py) - Database layer
- [insights_core/config.py](insights_core/config.py) - Configuration

**Detectors**:
- [insights_core/detectors/anomaly.py](insights_core/detectors/anomaly.py)
- [insights_core/detectors/diagnosis.py](insights_core/detectors/diagnosis.py)
- [insights_core/detectors/opportunity.py](insights_core/detectors/opportunity.py)

**AI/ML**:
- [insights_core/anomaly_detector.py](insights_core/anomaly_detector.py)
- [insights_core/forecasting.py](insights_core/forecasting.py)
- [insights_core/embeddings.py](insights_core/embeddings.py)
- [insights_core/causal_analyzer.py](insights_core/causal_analyzer.py)
- [insights_core/content_analyzer.py](insights_core/content_analyzer.py)

**API**:
- [insights_api/insights_api.py](insights_api/insights_api.py)

**Database**:
- [sql/05_unified_view.sql](sql/05_unified_view.sql)
- [sql/11_insights_table.sql](sql/11_insights_table.sql)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-25
**Next Review**: As system evolves per living plan
