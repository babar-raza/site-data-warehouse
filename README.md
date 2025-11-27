# SEO Intelligence Platform

**An enterprise-grade, AI-powered SEO analytics and automation platform that rivals commercial solutions costing $2,000-4,000/month — built entirely with free and open-source tools.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16+](https://img.shields.io/badge/PostgreSQL-16+-blue.svg)](https://www.postgresql.org/)
[![Monthly Cost](https://img.shields.io/badge/Monthly%20Cost-$0-brightgreen.svg)](.)
[![Test Coverage](https://img.shields.io/badge/tests-873%20passing-brightgreen.svg)](.)

---

## 🎯 What It Does

The SEO Intelligence Platform **autonomously monitors your SEO performance 24/7**, detects anomalies, diagnoses root causes, and generates AI-powered recommendations—all while costing **$0/month** to operate.

### Real-World Benefits

- ⚡ **Detects traffic drops** within hours (not days)
- 🤖 **AI agents analyze** 10+ data sources to find root causes
- 📊 **Unified dashboards** combine GSC + GA4 + SERP + Core Web Vitals
- 🔔 **Real-time alerts** via Slack/Email within 60 seconds
- 📈 **Forecasts traffic** with Prophet ML models
- 🎯 **Semantic search** across all your content using pgvector embeddings
- 🚀 **Auto-generates PRs** with SEO fixes via GitHub integration

---

## 🚀 Quick Start (15 Minutes)

### Prerequisites

- **PostgreSQL 16+** with `pgvector` extension
- **Python 3.11+**
- **Docker** (recommended) or manual setup
- **8GB RAM** recommended (4GB minimum)
- **Google Cloud Service Account** for GSC/GA4 ([Setup Guide](deployment/guides/GCP_SETUP_GUIDE.md))

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/site-data-warehouse
cd site-data-warehouse

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials and API keys

# 3. Start with Docker (Recommended)
docker-compose --profile core --profile insights up -d

# OR Manual Setup:
pip install -r requirements.txt
python -m playwright install chromium

# 4. Initialize database
for file in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$file"
done

# 5. Verify deployment
curl http://localhost:3000  # Grafana
curl http://localhost:8000/api/health  # Insights API
curl http://localhost:8001/health  # MCP Server
```

**Full Setup Guide**: [Quick Start](docs/QUICKSTART.md) | [Deployment Guide](docs/DEPLOYMENT.md)

---

## 💡 Key Features

### 📊 Data Collection & Integration

**Automated Ingestors:**
- ✅ **Google Search Console** - Daily ingestion of queries, pages, impressions, clicks
- ✅ **Google Analytics 4** - Session data, user behavior, conversion tracking
- ✅ **SERP Position Tracking** - Daily keyword rank monitoring via ValueSERP/SerpAPI
- ✅ **Core Web Vitals** - Performance metrics via PageSpeed Insights API
- ✅ **Content Scraping** - Headless browser (Playwright) for content analysis
- ✅ **Unified Data Warehouse** - PostgreSQL with 25 schema files, 44+ tables

**Data Retention:**
- Unlimited historical data (16+ months out of the box)
- 30+ SQL views for instant analytics
- Materialized views for performance optimization

### 🤖 AI & Machine Learning

**Multi-Agent AI System (10 Specialized Agents):**
1. **SupervisorAgent** - Workflow orchestration and emergency response
2. **WatcherAgent** - Real-time metric monitoring using statistical anomaly detection
3. **IntelligentWatcherAgent** - Advanced LangGraph-powered monitoring
4. **DiagnosticianAgent** - Root cause analysis and issue classification
5. **StrategistAgent** - Recommendation generation with ROI estimates
6. **DispatcherAgent** - Task execution and outcome monitoring
7. **SerpAnalystAgent** - Rankings analysis and competitor tracking
8. **PerformanceAgent** - Core Web Vitals optimization
9. **ContentOptimizerAgent** - AI-powered content improvements
10. **ImpactValidatorAgent** - ROI validation with causal inference

**Machine Learning Capabilities:**
- ✅ **Anomaly Detection** - 3 methods: Statistical (Z-score), ML (Isolation Forest), Forecasting (Prophet)
- ✅ **Traffic Forecasting** - Prophet time-series with seasonality detection
- ✅ **Causal Impact Analysis** - Bayesian structural time-series for ROI proof
- ✅ **Topic Clustering** - ML-based content grouping using embeddings
- ✅ **Semantic Search** - pgvector embeddings for intelligent content discovery
- ✅ **Natural Language Queries** - Ask questions in plain English, get SQL automatically
- ✅ **Content Intelligence** - Readability analysis, SEO scoring, AI recommendations

### 🔔 Alerting & Automation

**Real-Time Notification System:**
- ✅ **Slack Notifications** - Rich card formatting with actionable buttons
- ✅ **Email Alerts** - HTML templates with charts and metrics
- ✅ **Webhook Integration** - Custom endpoints for any third-party tool
- ✅ **Configurable Rules** - Custom conditions, severity levels, deduplication
- ✅ **Alert History** - Full audit trail with resolution tracking

**Automation & Orchestration:**
- ✅ **Celery Task Queue** - Distributed async processing with Redis
- ✅ **APScheduler** - Cron-based task scheduling (daily, weekly, hourly)
- ✅ **Event Streams** - Real-time event processing with Redis Streams
- ✅ **GitHub Integration** - Auto-generate pull requests for SEO fixes
- ✅ **Hugo Content Optimizer** - LLM-powered content optimization for Hugo CMS
- ✅ **Startup Orchestrator** - Automated 60-day backfill on deployment

### 📈 Visualization & Dashboards

**10 Production-Ready Grafana Dashboards:**

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

**Prometheus Metrics:**
- Container metrics via cAdvisor (CPU, memory, network)
- Database metrics via postgres_exporter (connections, queries, cache)
- Redis metrics via redis_exporter (memory, hit rate, clients)
- Custom application metrics (data freshness, collection status)
- 25+ alert rules across 5 categories (infrastructure, database, Redis, Prometheus, application)

Access dashboards at: `http://localhost:3000` (default credentials: admin/admin)

---

## 🏗️ System Architecture

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

**Architecture Details**: [System Architecture](docs/analysis/TECHNICAL_ARCHITECTURE.md) | [System Overview](docs/analysis/SYSTEM_OVERVIEW.md)

---

## 🔄 How It Works

### Layer 1: Data Collection
1. **Scheduled Ingestion** - Celery tasks collect data from GSC, GA4, SERP APIs daily
2. **Content Scraping** - Playwright extracts page content for readability analysis
3. **Performance Monitoring** - PageSpeed API tracks Core Web Vitals
4. **Startup Backfill** - Automatically fetches 60 days of historical data on first deploy

### Layer 2: Data Warehouse
1. **PostgreSQL Database** - 25 SQL schemas, 44+ tables, 30+ views
2. **Unified Data Layer** - FULL OUTER JOIN of GSC + GA4 + SERP data
3. **Materialized Views** - Pre-computed aggregations for performance
4. **Time-Series Calculations** - Week-over-week, month-over-month changes
5. **Semantic Indexing** - pgvector embeddings for content similarity

### Layer 3: Analytics & Intelligence
1. **Anomaly Detection** - 3 methods identify traffic drops, ranking losses
2. **Forecasting** - Prophet models predict future traffic with confidence intervals
3. **Root Cause Analysis** - ML algorithms correlate metrics to find causes
4. **Content Analysis** - AI evaluates readability, SEO, topic relevance
5. **Natural Language Queries** - Plain English → SQL translation via LangChain

### Layer 4: AI Agent System
1. **Watcher Agents** - Monitor 100+ metrics every hour
2. **Diagnostician** - Investigates anomalies, generates hypotheses
3. **Strategist** - Creates recommendations with impact estimates
4. **Dispatcher** - Executes approved actions, monitors outcomes
5. **Supervisor** - Coordinates workflows, handles emergencies
6. **+5 Specialized Agents** - SERP analysis, content optimization, performance, impact validation

### Layer 5: Automation & Alerting
1. **Real-Time Alerts** - Notifications within 60 seconds via Slack/Email
2. **GitHub Integration** - Auto-generates PRs with SEO fixes
3. **Event Streams** - Redis-powered real-time event processing
4. **Scheduled Tasks** - Daily/weekly/hourly automated workflows
5. **Visual Dashboards** - Grafana displays 5 live dashboards

**Learn More**: [Multi-Agent System](docs/analysis/MULTI_AGENT_SYSTEM.md) | [Insight Engine Guide](docs/analysis/INSIGHT_ENGINE_GUIDE.md) | [Dashboard Guide](docs/analysis/DASHBOARD_GUIDE.md)

---

## 🎯 Use Cases & Examples

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

## 📊 System Components

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
| **Grafana** | Visual dashboards (10 pre-built) | `http://localhost:3000` |
| **Prometheus** | Metrics collection & alerting | `http://localhost:9090` |
| **cAdvisor** | Container metrics exporter | `http://localhost:8080` |
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

## 📝 Configuration

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

## 🗄️ Database Schema

The platform uses a comprehensive PostgreSQL schema with **44+ tables** organized by domain:

### Data Tables (10 schemas)
- **gsc.*** - Google Search Console data (queries, pages, site metrics)
- **ga4.*** - Google Analytics 4 data (sessions, events, conversions)
- **serp.*** - SERP tracking (positions, competitors, history)
- **performance.*** - Core Web Vitals and performance metrics
- **content.*** - Content analysis, embeddings, topics
- **forecasts.*** - Traffic predictions and accuracy tracking
- **actions.*** - SEO interventions and outcomes
- **anomaly.*** - Detected issues and classifications
- **notifications.*** - Alert rules, history, delivery status
- **orchestration.*** - Agent state, workflows, executions

### Key Views (30+ SQL views)
- **Unified Views** - Combined GSC + GA4 + SERP data with time-series calculations
- **Performance Views** - Aggregated metrics with WoW/MoM changes
- **Analytics Functions** - SQL utilities for complex calculations
- **Materialized Views** - Pre-computed aggregations for performance

**Schema Files**: 25 SQL files (7,963 lines) in `sql/` directory
**Full Documentation**: [Unified View Guide](docs/guides/UNIFIED_VIEW_GUIDE.md) | [Schema Details](sql/)

---

## 🧪 Testing

### Test Suite Overview

**873 comprehensive tests** across 49 test files covering:

- ✅ **Unit Tests** - Individual component testing
- ✅ **Integration Tests** - Multi-component workflows
- ✅ **E2E Tests** - Full system validation
- ✅ **Agent Tests** - AI agent behavior validation
- ✅ **Load Tests** - Performance and scalability

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

## 📊 Project Statistics

| Metric | Count | Notes |
|--------|-------|-------|
| **Production Features** | 30+ | Fully tested and documented |
| **Python Files** | 167 | ~15,000 lines of Python code |
| **SQL Schema Files** | 25 | 7,963 lines of SQL |
| **Database Tables** | 44+ | Organized across 10 schemas |
| **SQL Views** | 30+ | Including materialized views |
| **AI Agents** | 10 | LangGraph-powered autonomous agents |
| **Grafana Dashboards** | 10 | Production-ready visualizations (5 SEO + 5 Infrastructure) |
| **Celery Tasks** | 20+ | Automated daily/weekly/hourly |
| **Test Functions** | 873 | Comprehensive test coverage |
| **Docker Services** | 14 | Fully orchestrated containers |
| **Notification Channels** | 3 | Slack, Email, Webhooks |
| **Monthly Cost** | **$0** | 100% free and open-source |
| **ROI** | **∞** | Infinite return on investment |

---

## 📖 Documentation

### 🚀 Getting Started
- **[Quick Start Guide](docs/QUICKSTART.md)** - Deploy in 15 minutes
- **[Setup Guide](deployment/guides/SETUP_GUIDE.md)** - Complete system setup
- **[GCP Setup](deployment/guides/GCP_SETUP_GUIDE.md)** - Google Cloud Platform configuration
- **[Development Setup](docs/guides/DEVELOPMENT.md)** - Local development environment

### 🌐 Deployment & Operations
- **[Deployment Overview](docs/DEPLOYMENT.md)** - Production deployment guide
- **[Docker Deployment](docs/deployment/DEPLOYMENT_WITH_LIMITS.md)** - Containerized deployment
- **[Resource Limits](docs/deployment/DOCKER_RESOURCE_LIMITS.md)** - Resource management
- **[Deployment Checklist](docs/DEPLOYMENT_CHECKLIST.md)** - Pre-deployment verification
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Production Guide](deployment/guides/PRODUCTION_GUIDE.md)** - Production best practices
- **[Monitoring Guide](deployment/guides/MONITORING_GUIDE.md)** - System monitoring
- **[Prometheus Dashboards Guide](docs/guides/PROMETHEUS_DASHBOARDS_GUIDE.md)** - Complete guide to infrastructure monitoring

### 🔌 Integration Guides
- **[GA4 Integration](deployment/guides/GA4_INTEGRATION.md)** - Google Analytics 4 setup
- **[GSC Integration](deployment/guides/GSC_INTEGRATION.md)** - Search Console integration
- **[MCP Integration](docs/guides/MCP_INTEGRATION.md)** - Model Context Protocol

### 🤖 AI & Analytics Features
- **[Multi-Agent System](docs/analysis/MULTI_AGENT_SYSTEM.md)** - AI agent architecture (10 agents)
- **[Insight Engine Guide](docs/analysis/INSIGHT_ENGINE_GUIDE.md)** - Analytics engine overview
- **[Hugo Content Optimizer](docs/guides/HUGO_CONTENT_OPTIMIZER.md)** - LLM-powered content optimization
- **[Dashboard Guide](docs/analysis/DASHBOARD_GUIDE.md)** - Grafana dashboard usage
- **[SERP Tracking Guide](docs/SERP_TRACKING_GUIDE.md)** - Position monitoring
- **[Detector Guide](docs/guides/DETECTOR_GUIDE.md)** - Writing custom detectors

### 📊 System Architecture
- **[System Overview](docs/analysis/SYSTEM_OVERVIEW.md)** - High-level architecture
- **[Technical Architecture](docs/analysis/TECHNICAL_ARCHITECTURE.md)** - Detailed design
- **[Architecture Patterns](docs/ARCHITECTURE_PATTERNS.md)** - Design patterns used
- **[Unified View Guide](docs/guides/UNIFIED_VIEW_GUIDE.md)** - Hybrid data layer

### 🧪 Testing & Development
- **[Testing Guide](docs/testing/TESTING.md)** - Comprehensive testing documentation
- **[E2E Test Plan](plans/E2E_TEST_PLAN.md)** - End-to-end testing strategy

### 📚 Reference
- **[API Reference](docs/api/API_REFERENCE.md)** - Complete API documentation
- **[Documentation Index](docs/INDEX.md)** - Organized guide to all documentation
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Command reference
- **[Scripts Documentation](scripts/README.md)** - Operational scripts

---

## 🗺️ Roadmap

### ✅ Completed Features (Production Ready)

- [x] Google Search Console & GA4 integration
- [x] Multi-agent AI system (10 agents)
- [x] Real-time alerting (Slack, Email, Webhooks)
- [x] 10 Grafana dashboards (5 SEO + 5 Infrastructure)
- [x] SERP position tracking
- [x] Core Web Vitals monitoring
- [x] Traffic forecasting with Prophet
- [x] Anomaly detection (3 methods)
- [x] Content analysis & recommendations
- [x] Hugo Content Optimizer (LLM-powered SEO content updates)
- [x] Semantic search with pgvector
- [x] Natural language queries
- [x] GitHub PR automation
- [x] Comprehensive test suite (873 tests)
- [x] Docker deployment with 14 services
- [x] Startup orchestrator with auto-backfill

### 🔮 Future Enhancements

- [ ] **White-label solution** - Multi-tenant support for agencies
- [ ] **Mobile app** - iOS/Android monitoring dashboard
- [ ] **Public API** - RESTful API for third-party integrations
- [ ] **Advanced ML models** - LSTM/Transformer-based forecasting
- [ ] **Competitor intelligence** - Automated competitor tracking
- [ ] **Content generation** - AI-powered content creation
- [ ] **A/B testing framework** - Built-in experimentation platform
- [ ] **Cost attribution** - Marketing spend vs. SEO ROI analysis

**Suggest Features**: [GitHub Issues](https://github.com/yourusername/site-data-warehouse/issues) | [Discussions](https://github.com/yourusername/site-data-warehouse/discussions)

---

## 🙏 Built With

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

## 📞 Support & Community

### Documentation
- **[Complete Documentation Index](docs/INDEX.md)** - All documentation organized
- **[Quick Start Guide](docs/QUICKSTART.md)** - Get running in 15 minutes
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[API Reference](docs/api/API_REFERENCE.md)** - Complete API documentation

### Community
- **[GitHub Issues](https://github.com/yourusername/site-data-warehouse/issues)** - Bug reports and feature requests
- **[GitHub Discussions](https://github.com/yourusername/site-data-warehouse/discussions)** - Q&A and community support
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community standards

### Enterprise Support
For commercial support, custom development, or consulting:
- Email: support@yourcompany.com
- Website: https://yourcompany.com

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

**Free to use commercially** - No restrictions, no attribution required (but appreciated!)

---

## 🌟 Star History

If this project helps you, please consider giving it a ⭐ on GitHub!

---

## 💰 Cost Comparison

| Feature | Commercial Solutions | This Platform |
|---------|---------------------|---------------|
| **SEO Monitoring** | $200-500/month | **$0** |
| **AI-Powered Insights** | $500-1,000/month | **$0** |
| **Custom Dashboards** | $200-400/month | **$0** |
| **Real-Time Alerts** | $100-200/month | **$0** |
| **Forecasting & ML** | $500-1,000/month | **$0** |
| **API Access** | $200-500/month | **$0** |
| **Multi-Agent System** | $1,000-2,000/month | **$0** |
| **Unlimited Properties** | $500-1,000/month | **$0** |
| **Custom Integrations** | $500+/month | **$0** |
| **Total** | **$2,000-4,000/month** | **$0/month** |
| **Annual Savings** | **-** | **$24,000-48,000** |

**ROI**: ♾️ Infinite

---

**Ready to save $24,000+/year on SEO tools?**

```bash
git clone https://github.com/yourusername/site-data-warehouse
cd site-data-warehouse
docker-compose --profile core --profile insights up -d
```

**Questions?** See [Quick Start Guide](docs/QUICKSTART.md) | [Troubleshooting](docs/TROUBLESHOOTING.md)
