# SEO Intelligence Platform

An AI-powered SEO analytics and automation platform built with free and open-source tools.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16+](https://img.shields.io/badge/PostgreSQL-16+-blue.svg)](https://www.postgresql.org/)
[![Test Coverage](https://img.shields.io/badge/tests-873%20passing-brightgreen.svg)](.)

---

## Problem Statement

SEO monitoring and analysis typically requires multiple disparate tools, manual data correlation, and reactive responses to traffic changes. By the time issues are identified through standard analytics dashboards, significant traffic and revenue may already be lost. Additionally, root cause analysis requires manual investigation across multiple data sources (Search Console, Analytics, SERP rankings, performance metrics), making it time-consuming and error-prone.

## Solution Overview

This platform implements a **5-layer architecture** that automates the entire SEO intelligence workflow:

1. **Data Collection Layer** - Automated daily ingestion from 6+ sources (GSC, GA4, SERP APIs, PageSpeed, content scraping) with watermark-based tracking and idempotent operations
2. **Data Warehouse Layer** - PostgreSQL with 10 schemas, 44+ tables, and a central unified view (`vw_unified_page_performance`) that FULL OUTER JOINs GSC + GA4 + SERP data with week-over-week and month-over-month calculations
3. **Intelligence Layer** - Hybrid LLM+ML approach combining statistical analysis, machine learning (Isolation Forest), forecasting (Prophet), and local LLM reasoning (Ollama) for context-aware anomaly detection
4. **Multi-Agent AI Layer** - 10 specialized AI agents orchestrated via LangGraph workflows that investigate issues, generate recommendations, execute fixes, and validate outcomes using causal inference
5. **Alerting & Monitoring Layer** - Real-time notifications via Slack/Email, 11 Grafana dashboards, Prometheus metrics with 25+ alert rules, and comprehensive observability

## Key Capabilities

**Detection & Analysis:**
- **Hybrid LLM+ML Anomaly Detection**: Combines local LLM reasoning (60%) with statistical validation (40%) - detects traffic drops >30%, position drops >5, CTR anomalies >2 SD
- **Multi-Method Validation**: Z-score analysis, Isolation Forest ML, and Prophet forecasting with 95% confidence intervals
- **Root Cause Analysis**: Automatic investigation of deployment correlation, directory-wide patterns, algorithm updates, and competitor movements
- **Content Intelligence**: Semantic search via pgvector (768-dim embeddings), cannibalization detection, quality scoring, readability analysis

**Automation & Actions:**
- **10 Specialized AI Agents**: SupervisorAgent orchestrates workflows, WatcherAgent monitors 24/7, DiagnosticianAgent investigates, StrategistAgent recommends, DispatcherAgent executes
- **Automated Daily Pipeline**: Ingestion (6:30 AM) → URL Discovery → Transforms → Detection → Insights → Notifications (7:30 AM) - fully automated
- **Priority-Based Recommendations**: Calculates (Impact/Effort) × Confidence scores, categorizes as quick/proper/strategic fixes
- **Execution with Validation**: Pre-checks, rollback snapshots, automated PR generation via GitHub, 30-day outcome monitoring with Bayesian causal inference

**Data & Visibility:**
- **Unified Data View**: `vw_unified_page_performance` FULL OUTER JOINs GSC + GA4 + SERP with WoW/MoM calculations, rolling averages (7d/28d)
- **11 Grafana Dashboards**: 5 SEO (SERP, CWV, GA4, GSC, Hybrid) + 5 Infrastructure (CPU, DB, Redis, Health, Alerts) + 1 Actions Command Center
- **Real-Time Alerting**: Slack/Email with severity-based routing, 24-hour deduplication, delivery tracking, configurable alert rules

---

## Quick Start

### Prerequisites

- PostgreSQL 16+ with `pgvector` extension
- Python 3.11+
- Docker (recommended) or manual setup
- 8GB RAM recommended (4GB minimum)
- Google Cloud Service Account for GSC/GA4 ([Setup Guide](deployment/guides/GCP_SETUP_GUIDE.md))

### Installation

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your credentials and API keys

# 2. Start with Docker (Recommended)
docker-compose --profile core --profile insights up -d

# OR Manual Setup:
pip install -r requirements.txt
python -m playwright install chromium

# 3. Initialize database
for file in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$file"
done

# 4. Verify deployment
curl http://localhost:3000  # Grafana
curl http://localhost:8000/api/health  # Insights API
curl http://localhost:8001/health  # MCP Server
```

**Full Setup Guide**: [Quick Start](docs/QUICKSTART.md) | [Deployment Guide](docs/DEPLOYMENT.md)

---

## System Features

### Data Collection & Integration

**Automated Ingestors:**
- Google Search Console - Daily ingestion of queries, pages, impressions, clicks
- Google Analytics 4 - Session data, user behavior, conversion tracking
- SERP Position Tracking - Daily keyword rank monitoring via ValueSERP/SerpAPI
- Core Web Vitals - Performance metrics via PageSpeed Insights API
- Content Scraping - Headless browser (Playwright) for content analysis
- Unified Data Warehouse - PostgreSQL with 35 schema files, 44+ tables

**Data Retention:**
- Unlimited historical data (16+ months out of the box)
- 30+ SQL views for instant analytics
- Materialized views for performance optimization

### AI & Machine Learning

**Multi-Agent AI System (10 Specialized Agents):**

The platform uses a **hybrid LLM + ML approach** where local LLMs (Ollama) provide context and reasoning while traditional ML provides statistical validation. This ensures reliability even when LLMs are unavailable.

1. **SupervisorAgent** - Orchestrates multi-agent workflows using LangGraph state machines. Coordinates emergency response, daily analysis, optimization campaigns, and impact validation workflows
2. **WatcherAgent** - 24/7 monitoring with hybrid detection: LLM reasoning (60% weight) for contextual analysis + ML validation (40% weight) with Z-scores, traffic drops >30%, position drops >5, CTR anomalies
3. **IntelligentWatcherAgent** - Advanced LangGraph-powered pattern recognition with multi-step reasoning workflows and adaptive sensitivity based on historical context
4. **DiagnosticianAgent** - Investigates anomalies using hypothesis generation, correlation analysis (directory-wide, deployment timing, algorithm updates), and root cause ranking by probability
5. **StrategistAgent** - Generates tiered recommendations (quick/proper/strategic fixes), estimates impact (traffic gain, conversion lift, revenue), and calculates priority scores: (Impact/Effort) × Confidence
6. **DispatcherAgent** - Executes approved recommendations via WordPress/GitHub/Cloudflare APIs with pre-validation, rollback capability, and 30-day outcome monitoring
7. **SerpAnalystAgent** - Tracks keyword positions, identifies ranking opportunities, monitors SERP features, and analyzes competitor movements
8. **PerformanceAgent** - Optimizes Core Web Vitals (LCP <2.5s, FID <100ms, CLS <0.1) using Lighthouse audits and generates performance improvement recommendations
9. **ContentOptimizerAgent** - AI-powered content analysis using Ollama for quality scoring, readability metrics, SEO suggestions, and topic extraction
10. **ImpactValidatorAgent** - Validates SEO interventions using Bayesian causal inference, measures traffic lift with statistical significance, calculates ROI, and updates agent learning

**Machine Learning Capabilities:**
- Anomaly Detection - 3 methods: Statistical (Z-score), ML (Isolation Forest), Forecasting (Prophet)
- Traffic Forecasting - Prophet time-series with seasonality detection
- Causal Impact Analysis - Bayesian structural time-series for impact validation
- Topic Clustering - ML-based content grouping using embeddings
- Semantic Search - pgvector embeddings for content discovery
- Natural Language Queries - Plain English to SQL translation
- Content Intelligence - Readability analysis, SEO scoring, AI recommendations

### Alerting & Automation

**Notification System:**
- Slack Notifications - Rich card formatting with actionable buttons
- Email Alerts - HTML templates with charts and metrics
- Webhook Integration - Custom endpoints for third-party integrations
- Configurable Rules - Custom conditions, severity levels, deduplication
- Alert History - Full audit trail with resolution tracking

**Automation & Orchestration:**
- Celery Task Queue - Distributed async processing with Redis
- APScheduler - Cron-based task scheduling (daily, weekly, hourly)
- Event Streams - Real-time event processing with Redis Streams
- GitHub Integration - Automated pull request generation for SEO fixes
- Hugo Content Optimizer - LLM-powered content optimization for Hugo CMS
- Startup Orchestrator - Automated 60-day backfill on deployment

### Visualization & Dashboards

**11 Grafana Dashboards:**

*SEO Analytics (5 Dashboards):*
1. **SERP Position Tracking** - Keyword rankings, trends, competitor analysis
2. **Core Web Vitals Monitoring** - LCP, FID, CLS performance tracking
3. **GA4 Analytics Overview** - Sessions, conversions, engagement metrics
4. **GSC Overview** - Search Console clicks, impressions, CTR, position
5. **Hybrid Analytics** - Unified GSC + GA4 + SERP view with funnel analysis

*Infrastructure Monitoring (5 Dashboards):*
6. **Infrastructure Overview** - Container CPU, memory, network, disk I/O
7. **Database Performance** - PostgreSQL connections, queries, cache hit ratio
8. **Application Metrics** - Custom metrics, Redis cache, data freshness
9. **Service Health** - Real-time service status and health checks
10. **Alert Status** - Active alerts, alert history, monitoring system health

*Actions & Automation (1 Dashboard):*
11. **Actions Command Center** - SEO action tracking, execution status, outcomes

**Prometheus Metrics:**
- Container metrics via custom Docker Stats Exporter (CPU, memory, network, disk I/O)
- Database metrics via postgres_exporter (connections, queries, cache)
- Redis metrics via redis_exporter (memory, hit rate, clients)
- Custom application metrics (data freshness, collection status)
- 25+ alert rules across 5 categories (infrastructure, database, Redis, Prometheus, application)

**Note**: Uses a custom Windows-compatible Docker Stats Exporter instead of cAdvisor for better compatibility with Docker Desktop

Access dashboards at: `http://localhost:3000`

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              SEO Intelligence Platform                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Data Sources │───▶│  Analytics   │───▶│  Automation  │      │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤      │
│  │ • GSC API    │    │ • Prophet ML │    │ • Celery     │      │
│  │ • GA4 API    │    │ • ML Models  │    │ • Redis      │      │
│  │ • SERP API   │    │ • LangGraph  │    │ • APScheduler│      │
│  │ • PageSpeed  │    │ • pgvector   │    │ • GitHub API │      │
│  │ • Playwright │    │ • Embeddings │    │ • Playwright │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  AI Agents   │───▶│  Monitoring  │───▶│Notifications │      │
│  ├──────────────┤    ├──────────────┤    ├──────────────┤      │
│  │ • Supervisor │    │ • SERP Track │    │ • Slack      │      │
│  │ • Watcher    │    │ • CWV Monitor│    │ • Email      │      │
│  │ • Diagnostics│    │ • Anomaly Det│    │ • Webhooks   │      │
│  │ • Strategist │    │ • Forecasting│    │ • GitHub PRs │      │
│  │ • Dispatcher │    │ • Event Stream│   │              │      │
│  │ • +5 more    │    │              │    │              │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                   │
│         PostgreSQL 16 + pgvector + Redis + Ollama               │
│         Prometheus + Grafana + Celery + APScheduler             │
└─────────────────────────────────────────────────────────────────┘
```

**Architecture Details**: [System Architecture](docs/ARCHITECTURE.md) | [Data Model Reference](docs/DATA_MODEL.md)

---

## How It Works

### Daily Automated Pipeline (7:00 AM UTC)

The platform runs a fully automated workflow every morning:

```
1. DATA INGESTION (6:30-7:00 AM)
   ├─ GSC API: Last 3 days of data (idempotent UPSERT)
   ├─ GA4 API: Yesterday's sessions and conversions
   ├─ SERP APIs: Position tracking for monitored keywords
   ├─ PageSpeed API: Core Web Vitals for prioritized pages
   ├─ Content Scraper: New/updated pages via Playwright
   └─ Watermark Tracking: Records progress for each source

2. URL DISCOVERY (7:00 AM)
   ├─ Identify high-value pages from GSC/GA4 data
   ├─ Calculate priority scores (traffic × engagement × conversion)
   └─ Add to performance.monitored_pages for CWV tracking

3. DATA TRANSFORMS (7:05 AM)
   ├─ Refresh materialized views
   ├─ Calculate week-over-week changes
   ├─ Update rolling averages (7d, 28d)
   └─ Regenerate vw_unified_page_performance

4. ANOMALY DETECTION (7:10 AM)
   ├─ WatcherAgent: Scan 100+ metrics with hybrid LLM+ML
   ├─ Statistical tests: Z-scores, traffic drops >30%
   ├─ Position drops: >5 positions on important keywords
   ├─ CTR anomalies: >2 standard deviations
   └─ Store in anomaly.detected_anomalies

5. INSIGHT GENERATION (7:15 AM)
   ├─ Run 10+ specialized detectors in parallel:
   │  • Traffic Drop Detector
   │  • SERP Position Detector
   │  • CTR Anomaly Detector
   │  • Content Quality Detector
   │  • Cannibalization Detector
   │  • CWV Quality Detector
   │  • Trend Opportunity Detector
   │  • Topic Strategy Detector
   ├─ Deduplicate using SHA256 hashing
   └─ Store in gsc.insights with severity scoring

6. MULTI-AGENT WORKFLOW (7:20 AM, if high-severity anomalies)
   ├─ SupervisorAgent: Initiates emergency response workflow
   ├─ DiagnosticianAgent: Root cause analysis
   ├─ StrategistAgent: Generate recommendations with ROI
   └─ Results stored for human review

7. NOTIFICATIONS (7:30 AM)
   ├─ High severity → Slack alert (immediate)
   ├─ Medium severity → Email summary (daily digest)
   ├─ Alert deduplication (24-hour window)
   └─ Delivery tracking in notifications.alert_history
```

### The Central Unified View

**`gsc.vw_unified_page_performance`** is the heart of the system:

```sql
SELECT
  -- Identifiers
  property_url, page_path, date,

  -- GSC metrics (organic search)
  gsc_clicks, gsc_impressions, gsc_ctr, gsc_position,

  -- GA4 metrics (user behavior)
  ga4_sessions, ga4_engaged_sessions, ga4_conversions,

  -- SERP metrics (rankings)
  serp_position, serp_url, serp_title,

  -- Time-series calculations
  clicks_wow_change, clicks_wow_pct,    -- Week-over-week
  clicks_mom_change, clicks_mom_pct,    -- Month-over-month
  clicks_7d_avg, clicks_28d_avg,        -- Rolling averages

  -- Quality indicators
  has_featured_snippet, serp_features,
  content_quality_score, readability_score

FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - 90
ORDER BY date DESC, gsc_clicks DESC;
```

This single view powers:
- All Grafana dashboards
- Anomaly detection algorithms
- Agent analysis workflows
- API endpoints
- Natural language queries

### Multi-Agent Workflow Example

**Emergency Response** (traffic drop detected):

```
1. WatcherAgent detects -45% traffic drop on /blog/post
2. SupervisorAgent initiates emergency_response workflow
3. DiagnosticianAgent investigates:
   ├─ Check deployment history (git log)
   ├─ Correlate with directory-wide patterns
   ├─ Check algorithm update calendar
   ├─ Analyze competitor movements
   └─ Generate hypotheses ranked by probability

4. StrategistAgent creates recommendations:
   ├─ Quick Fix: Restore old meta title (Impact: +15%, Effort: 1h)
   ├─ Proper Fix: Rewrite content (Impact: +35%, Effort: 8h)
   └─ Priority Score: Quick Fix = 15, Proper Fix = 4.4

5. Human reviews and approves Quick Fix

6. DispatcherAgent executes:
   ├─ Pre-validation checks
   ├─ Create rollback snapshot
   ├─ Update meta title via GitHub PR
   ├─ Post-validation
   └─ Start 30-day outcome monitoring

7. ImpactValidatorAgent (after 7 days):
   ├─ Causal impact analysis (Bayesian)
   ├─ Actual lift: +12% (vs predicted +15%)
   ├─ Statistical significance: p=0.02
   └─ Update StrategistAgent learning
```

**Learn More**: [Multi-Agent System](docs/guides/MULTI_AGENT_SYSTEM.md) | [Insight Engine Guide](docs/guides/INSIGHT_ENGINE_GUIDE.md) | [Dashboard Guide](docs/guides/DASHBOARD_GUIDE.md)

---

## Use Cases & Examples

### 1. Automated 24/7 Monitoring

The platform runs continuously without human intervention:

```python
# Runs automatically every hour
from agents.watcher.watcher_agent import WatcherAgent

agent = WatcherAgent()
findings = await agent.detect_anomalies(
    property='https://yourdomain.com',
    lookback_days=7
)
# Auto-sends Slack alert if traffic drop > 20%
```

### 2. Content Optimization

```python
from insights_core.content_analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()
analysis = await analyzer.analyze_page(
    url='https://yoursite.com/blog/post'
)

print(f"Readability Score: {analysis['readability_score']}/100")
print(f"SEO Score: {analysis['seo_score']}/100")
print(f"Suggestions: {len(analysis['suggestions'])}")
# Output: AI-generated recommendations for improvement
```

### 3. Traffic Forecasting

```python
from insights_core.forecasting import Forecaster

forecaster = Forecaster()
forecast = await forecaster.forecast_property(
    property='https://yourdomain.com',
    days_ahead=30,
    include_confidence=True
)

print(f"Expected clicks in 30 days: {forecast['predicted_clicks']}")
print(f"Confidence interval: {forecast['lower_bound']} - {forecast['upper_bound']}")
```

### 4. Anomaly Detection

```python
from insights_core.anomaly_detector import AnomalyDetector

detector = AnomalyDetector()
anomalies = await detector.detect_serp_anomalies(
    property_url='https://yourdomain.com',
    methods=['statistical', 'ml', 'forecasting']
)

for anomaly in anomalies:
    print(f"{anomaly['type']}: {anomaly['page']} lost {anomaly['clicks_lost']} clicks")
    # Automatically creates insights and sends alerts
```

### 5. Natural Language Queries

```python
from insights_core.nl_query import NaturalLanguageQueryEngine

nl_engine = NaturalLanguageQueryEngine()
result = await nl_engine.query(
    "Which pages lost the most traffic last week?"
)

print(result['sql'])  # Generated SQL query
print(result['data'])  # Query results
```

### 6. Multi-Agent Workflow

```python
from agents.orchestration.supervisor_agent import SupervisorAgent

supervisor = SupervisorAgent()
result = await supervisor.run_workflow(
    workflow_type='emergency_response',
    trigger_event={
        'alert_type': 'traffic_drop',
        'severity': 'high',
        'property': 'https://yourdomain.com'
    }
)

print(f"Root Cause: {result['diagnosis']['root_cause']}")
print(f"Recommendations: {len(result['recommendations'])}")
print(f"Auto-generated PR: {result['github_pr_url']}")
```

---

## System Components

### Core Infrastructure

| Component | Purpose | Status |
|-----------|---------|--------|
| **PostgreSQL 16+** | Primary data warehouse with pgvector extension | ✅ Production |
| **Redis** | Message broker for Celery + Event streams | ✅ Production |
| **Celery** | Distributed task queue for async processing | ✅ Production |
| **Ollama** | Local LLM for AI agents (free, no API keys needed) | ✅ Production |
| **Docker** | Container orchestration (14 services) | ✅ Production |
| **Prometheus** | Metrics collection and time-series database | ✅ Production |
| **Grafana** | Visual dashboards and monitoring | ✅ Production |

### Data Ingestors

| Component | Purpose | Configuration |
|-----------|---------|---------------|
| **GSC Ingestor** | Google Search Console data collection | Service account JSON required |
| **GA4 Ingestor** | Google Analytics 4 data collection | Service account JSON required |
| **SERP Tracker** | Search position monitoring | ValueSERP/SerpAPI key (free tier: 100 searches/month) |
| **PageSpeed API** | Core Web Vitals monitoring | Google API key (free) |
| **Content Scraper** | Headless browser for content analysis | Playwright (auto-install) |

### Analytics Engines

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Prophet** | Time-series forecasting with seasonality | Meta's Prophet ML library |
| **scikit-learn** | ML models (anomaly detection, clustering) | Isolation Forest, DBSCAN |
| **pgvector** | Semantic search via embeddings | PostgreSQL extension |
| **LangChain/LangGraph** | AI agent framework | State-based agent orchestration |
| **Ollama** | Local LLM inference | qwen2.5-coder:7b recommended |

### Monitoring & Observability

| Component | Purpose | Access URL |
|-----------|---------|-----------|
| **Grafana** | Visual dashboards (11 pre-built) | `http://localhost:3000` |
| **Prometheus** | Metrics collection & alerting | `http://localhost:9090` |
| **Docker Stats Exporter** | Container metrics (Windows-compatible) | `http://localhost:8003/metrics` |
| **PostgreSQL Exporter** | Database metrics exporter | `http://localhost:9187/metrics` |
| **Redis Exporter** | Cache metrics exporter | `http://localhost:9121/metrics` |
| **Metrics Exporter** | Custom application metrics | `http://localhost:8002/metrics` |
| **Insights API** | RESTful API for insights | `http://localhost:8000` |
| **MCP Server** | Model Context Protocol server | `http://localhost:8001` |

### Notification Channels

| Channel | Purpose | Configuration |
|---------|---------|---------------|
| **Slack** | Real-time alerts with rich formatting | Webhook URL in .env |
| **Email** | HTML emails with charts | SMTP credentials in .env |
| **Webhooks** | Custom HTTP integrations | Endpoint URL in .env |

---

## Configuration

### Required Environment Variables

```bash
# === CORE DATABASE ===
WAREHOUSE_DSN=postgresql://user:pass@localhost:5432/seo_warehouse

# === REDIS & CELERY ===
CELERY_BROKER_URL=redis://localhost:6379/0
REDIS_URL=redis://localhost:6379/1

# === OLLAMA (AI FEATURES) ===
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b  # or llama2, mistral, etc.

# === GOOGLE SEARCH CONSOLE ===
GSC_SA_PATH=./secrets/gsc_sa.json
GSC_PROPERTY=sc-domain:yoursite.com

# === GOOGLE ANALYTICS 4 ===
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_PATH=./secrets/ga4_credentials.json

# === SERP TRACKING (Optional) ===
VALUESERP_API_KEY=your-key  # Free tier: 100 searches/month
# OR
SERPAPI_KEY=your-key

# === NOTIFICATIONS (Optional but Recommended) ===
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# === GITHUB AUTOMATION (Optional) ===
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_REPO=username/repo

# === SYSTEM CONFIGURATION ===
LOG_LEVEL=INFO
BACKFILL_DAYS=60  # Historical data on first run
INGEST_DAYS=3  # Daily ingestion lookback
```

**Full Configuration Guide**: [.env.example](.env.example) | [Setup Guide](deployment/guides/SETUP_GUIDE.md)

---

## Database Schema

The platform uses a comprehensive PostgreSQL schema with **35 SQL files, 44+ tables, 30+ views** organized into 10 schemas:

### Core Schemas

**gsc (12 tables)** - Search Console & Analytics
- `fact_gsc_daily` - GSC metrics (millions of rows, partitioned by date)
- `fact_ga4_daily` - GA4 sessions and conversions
- `insights` - Canonical insights with SHA256 deduplication
- `actions` - SEO tasks with full SDLC tracking
- `dim_property`, `dim_page`, `dim_query` - Dimension tables
- `ingest_watermarks` - Ingestion progress tracking
- `audit_log` - Complete change history

**content (6 tables)** - Content Intelligence
- `page_snapshots` - HTML content + pgvector embeddings (768-dim)
- `topics` - Hierarchical topic taxonomy
- `page_topics` - Many-to-many page-topic mapping
- `quality_scores` - AI-generated quality assessments
- `cannibalization_pairs` - Content conflict detection
- `content_changes` - Version history with SHA256 hashing

**serp (3 tables)** - Position Tracking
- `queries` - Target keywords with monitoring config
- `position_history` - Time-series rankings (GSC + API sources)
- `serp_features` - Featured snippets, PAA, image pack tracking

**performance (2 tables)** - Core Web Vitals
- `core_web_vitals` - LCP, FID, CLS, FCP, INP, TTFB metrics
- `monitored_pages` - Auto-discovered high-value pages with priority scores

**forecasts (2 tables)** - ML Predictions
- `traffic_forecasts` - Prophet predictions with 95% confidence intervals
- `accuracy_tracking` - Forecast validation and model performance

**actions (4 tables)** - SEO Interventions
- `actions` - Actionable recommendations with priority scoring
- `outcomes` - Execution results with pre/post snapshots
- `lift_measurements` - Causal impact analysis (Bayesian)
- `action_metrics` - Aggregated effectiveness by type

**notifications (3 tables)** - Alerting
- `alert_rules` - Configurable conditions with severity levels
- `alert_history` - Delivery log with deduplication (24h window)
- `notification_queue` - Pending alerts with retry logic

**orchestration (4 tables)** - Multi-Agent
- `agent_executions` - Workflow run history
- `workflow_steps` - Step-level logging with duration tracking
- `agent_state` - Persistent state across restarts (JSON)
- `workflow_definitions` - Reusable workflow templates

**anomaly (1 table)** - Detection
- `detected_anomalies` - ML-flagged issues with confidence scores

**trends (3 tables)** - Google Trends Integration
- `keyword_interest` - Search interest over time (0-100 scale)
- `related_queries` - Rising and top related keywords
- `collection_runs` - Monitoring cadence tracking

### The Star of the Show: vw_unified_page_performance ⭐

This is the **central analytical view** that powers the entire platform:

```sql
-- Full OUTER JOIN of GSC + GA4 + SERP
-- Time-series calculations (WoW, MoM, rolling averages)
-- Quality indicators (content scores, CWV, SERP features)
-- 90-day window by default

SELECT * FROM gsc.vw_unified_page_performance
WHERE property_url = 'https://yoursite.com'
  AND date >= CURRENT_DATE - 90
ORDER BY gsc_clicks DESC;
```

**Powers:**
- All 11 Grafana dashboards
- Anomaly detection (WatcherAgent, IntelligentWatcherAgent)
- Agent workflows (Diagnostician, Strategist)
- API endpoints (`/api/pages`, `/api/insights`)
- Natural language queries
- Forecasting models

**Schema Files**: 35 SQL files in `sql/` directory
**Full Documentation**: [Unified View Guide](docs/guides/UNIFIED_VIEW_GUIDE.md) | [Data Model Reference](docs/DATA_MODEL.md)

---

## Testing

### Test Suite Overview

873 comprehensive tests across 49 test files covering:

- Unit Tests - Individual component testing
- Integration Tests - Multi-component workflows
- E2E Tests - Full system validation
- Agent Tests - AI agent behavior validation
- Load Tests - Performance and scalability

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test suites
pytest tests/agents/ -v                    # Agent tests (10 agents)
pytest tests/insights_core/ -v             # Analytics tests
pytest tests/integration/ -v               # Integration tests
pytest tests/e2e/ -v                       # End-to-end tests

# Test modes
export TEST_MODE=mock      # Mock external APIs (fast)
export TEST_MODE=live      # Use real services (requires setup)
export TEST_MODE=ollama    # Test with local Ollama LLM

# Generate coverage report
pytest --cov=. --cov-report=html
# View at: htmlcov/index.html
```

**Testing Documentation**: [Testing Guide](docs/testing/TESTING.md) | [E2E Test Plan](plans/E2E_TEST_PLAN.md)

---

## Project Statistics

| Metric | Count | Notes |
|--------|-------|-------|
| **Production Features** | 30+ | Fully tested and documented |
| **Python Files** | 167 | ~15,000 lines of Python code |
| **SQL Schema Files** | 35 | Comprehensive database schema |
| **Database Tables** | 44+ | Organized across 10 schemas |
| **SQL Views** | 30+ | Including materialized views |
| **AI Agents** | 10 | LangGraph-powered autonomous agents |
| **Grafana Dashboards** | 11 | Production-ready visualizations (5 SEO + 5 Infrastructure + 1 Actions) |
| **Celery Tasks** | 20+ | Automated daily/weekly/hourly |
| **Test Functions** | 873 | Comprehensive test coverage |
| **Docker Services** | 14 | Fully orchestrated containers |
| **Notification Channels** | 3 | Slack, Email, Webhooks |

---

## Documentation

### Getting Started
- [Quick Start Guide](docs/QUICKSTART.md) - Initial deployment
- [Setup Guide](deployment/guides/SETUP_GUIDE.md) - Complete system setup
- [GCP Setup](deployment/guides/GCP_SETUP_GUIDE.md) - Google Cloud Platform configuration
- [Development Setup](docs/guides/DEVELOPMENT.md) - Local development environment

### Deployment & Operations
- [Deployment Overview](docs/DEPLOYMENT.md) - Production deployment guide
- [Docker Deployment](docs/deployment/DEPLOYMENT_WITH_LIMITS.md) - Containerized deployment
- [Resource Limits](docs/deployment/DOCKER_RESOURCE_LIMITS.md) - Resource management
- [Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md) - Pre-deployment verification
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Production Guide](deployment/guides/PRODUCTION_GUIDE.md) - Production best practices
- [Monitoring Guide](deployment/guides/MONITORING_GUIDE.md) - System monitoring
- [Prometheus Dashboards Guide](docs/guides/PROMETHEUS_DASHBOARDS_GUIDE.md) - Infrastructure monitoring guide

### Integration Guides
- [GA4 Integration](deployment/guides/GA4_INTEGRATION.md) - Google Analytics 4 setup
- [GSC Integration](deployment/guides/GSC_INTEGRATION.md) - Search Console integration
- [MCP Integration](docs/guides/MCP_INTEGRATION.md) - Model Context Protocol

### AI & Analytics Features
- [Multi-Agent System](docs/guides/MULTI_AGENT_SYSTEM.md) - AI agent architecture (10 agents)
- [Insight Engine Guide](docs/guides/INSIGHT_ENGINE_GUIDE.md) - Analytics engine overview
- [Hugo Content Optimizer](docs/guides/HUGO_CONTENT_OPTIMIZER.md) - LLM-powered content optimization
- [Dashboard Guide](docs/guides/DASHBOARD_GUIDE.md) - Grafana dashboard usage
- [SERP Tracking Guide](docs/SERP_TRACKING_GUIDE.md) - Position monitoring
- [Detector Guide](docs/guides/DETECTOR_GUIDE.md) - Writing custom detectors
- [URL Discovery Guide](docs/guides/URL_DISCOVERY_GUIDE.md) - Automatic URL discovery and monitoring

### System Architecture & Data Model
- [System Architecture](docs/ARCHITECTURE.md) - Complete system architecture
- [Data Model Reference](docs/DATA_MODEL.md) - Complete schema reference (44+ tables)
- [Architecture Patterns](docs/ARCHITECTURE_PATTERNS.md) - Design patterns used
- [Unified View Guide](docs/guides/UNIFIED_VIEW_GUIDE.md) - Hybrid data layer

### Testing & Development
- [Testing Guide](docs/testing/TESTING.md) - Comprehensive testing documentation
- [E2E Test Plan](plans/E2E_TEST_PLAN.md) - End-to-end testing strategy

### Reference
- [API Reference](docs/api/API_REFERENCE.md) - Complete API documentation
- [Documentation Index](docs/INDEX.md) - Organized guide to all documentation
- [Quick Reference](docs/QUICK_REFERENCE.md) - Command reference
- [Scripts Documentation](scripts/README.md) - Operational scripts

---

## Production Readiness

### Tested Features ✅

These features are production-ready with comprehensive testing and real-world validation:

**Data Infrastructure:**
- Idempotent data ingestion with watermark tracking
- UPSERT operations throughout (no duplicate data)
- Graceful error handling and retry logic
- Comprehensive audit logging
- Automatic schema migrations

**Analytics & Detection:**
- Hybrid LLM+ML anomaly detection with fallback
- Multi-method validation (statistical, ML, forecasting)
- SHA256-based insight deduplication
- Confidence scoring for all detections
- Historical baseline comparison

**Automation & Reliability:**
- State persistence across restarts
- Workflow resumption after failures
- Resource limits and monitoring
- Health checks on all services
- Rollback capability for changes

**Observability:**
- 11 Grafana dashboards
- 25+ Prometheus alert rules
- 8 metrics exporters
- Comprehensive logging
- End-to-end tracing

### Experimental Features ⚠️

These features are functional but require additional validation:

- **Hugo Content Optimizer**: LLM-powered content suggestions work well but require human review before publication
- **GitHub PR Generation**: Automated PR creation is implemented but needs approval workflows
- **Natural Language Queries**: Text-to-SQL translation is basic and needs refinement for complex queries

### Not Implemented ❌

- Multi-tenant/white-label support
- LSTM/Transformer forecasting models
- Automated content generation (analysis only)
- Built-in A/B testing framework

---

## Who Should Use This

### Ideal For ✅

- **Medium to large websites** (10,000+ pages, 100K+ monthly organic traffic)
- **Content-heavy sites** needing cannibalization detection and quality monitoring
- **E-commerce sites** with SEO focus and conversion tracking
- **Digital agencies** managing multiple client properties
- **Engineering teams** comfortable with Python, PostgreSQL, Docker
- **Companies** wanting to replace expensive SaaS tools ($2K-4K/month) with owned infrastructure

### Not Suitable For ❌

- **Small websites** (<1,000 pages) - the system is overkill
- **Sites without API access** - requires GSC and GA4 API permissions
- **Non-technical teams** - requires DevOps knowledge for deployment and maintenance
- **Ultra-tight budgets** - while software is free, hosting costs $100-200/month minimum
- **Instant setup needs** - initial deployment and configuration takes 2-4 hours

### Technical Requirements

**Minimum:**
- 4GB RAM, 2 CPU cores, 50GB storage
- Basic PostgreSQL and Docker knowledge
- API access to GSC and GA4
- 5-10 hours/month for maintenance

**Recommended:**
- 8GB RAM, 4 CPU cores, 100GB SSD storage
- Experience with Python, SQL, and Docker
- DevOps familiarity (monitoring, alerting)
- Dedicated infrastructure (not shared hosting)

---

## Roadmap

### Completed Features

- [x] Google Search Console & GA4 integration
- [x] Multi-agent AI system (10 agents)
- [x] Real-time alerting (Slack, Email, Webhooks)
- [x] 11 Grafana dashboards (5 SEO + 5 Infrastructure + 1 Actions)
- [x] SERP position tracking
- [x] Core Web Vitals monitoring
- [x] Traffic forecasting with Prophet
- [x] Anomaly detection (3 methods)
- [x] Content analysis & recommendations
- [x] Experimental: Hugo Content Optimizer (LLM-powered SEO content updates)
- [x] Semantic search with pgvector
- [x] Natural language queries
- [x] GitHub PR automation
- [x] Comprehensive test suite (873 tests)
- [x] Docker deployment with 14 services
- [x] Startup orchestrator with auto-backfill

### Future Enhancements

- [ ] **White-label solution** - Multi-tenant support for agencies
- [ ] **Advanced ML models** - LSTM/Transformer-based forecasting
- [ ] **Competitor intelligence** - Automated competitor tracking
- [ ] **Content generation** - AI-powered content creation
- [ ] **A/B testing framework** - Built-in experimentation platform
- [ ] **Cost attribution** - Marketing spend vs. SEO ROI analysis

---

## Built With

Open-source technologies powering this platform:

- **[PostgreSQL](https://www.postgresql.org/)** + **[pgvector](https://github.com/pgvector/pgvector)** - Data warehouse with vector search
- **[LangChain](https://github.com/langchain-ai/langchain)** + **[LangGraph](https://github.com/langchain-ai/langgraph)** - AI agent framework
- **[Prophet](https://facebook.github.io/prophet/)** - Time-series forecasting by Meta
- **[Celery](https://docs.celeryq.dev/)** + **[Redis](https://redis.io/)** - Distributed task processing
- **[Grafana](https://grafana.com/)** + **[Prometheus](https://prometheus.io/)** - Monitoring and visualization
- **[Ollama](https://ollama.ai/)** - Local LLM inference (no API keys required)
- **[scikit-learn](https://scikit-learn.org/)** - Machine learning algorithms
- **[Playwright](https://playwright.dev/)** - Headless browser automation
- **[APScheduler](https://apscheduler.readthedocs.io/)** - Python job scheduling
- **[Docker](https://www.docker.com/)** - Container orchestration

---

## Realistic Expectations

This platform is a **sophisticated, production-grade system** that requires technical expertise to deploy and maintain. While it can replace expensive commercial tools, there are important considerations:

**Time Investment:**
- Initial deployment: 2-4 hours (Docker setup, API configuration, schema initialization)
- Learning curve: 1-2 weeks to understand the architecture and workflows
- Monthly maintenance: 5-10 hours (monitoring, updates, troubleshooting)

**What You Get:**
- Complete data ownership (no vendor lock-in)
- Unlimited historical data retention
- Full customization capability
- Learning opportunity for modern ML/AI systems
- No recurring software licensing fees

**What You Don't Get:**
- Point-and-click GUI configuration
- 24/7 vendor support
- Plug-and-play setup
- Automatic updates and maintenance
- Guaranteed uptime SLAs

This system is ideal for technically-oriented teams who want full control over their SEO intelligence infrastructure and are willing to invest time in deployment and maintenance.
