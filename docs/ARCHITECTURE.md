# System Architecture

**Enterprise-grade SEO Intelligence Platform with 19+ Docker services, 8 data sources, and 10 database schemas**

---

## Table of Contents

- [Overview](#overview)
- [Architecture Principles](#architecture-principles)
- [System Overview Diagram](#system-overview-diagram)
- [Services (19+ Docker Containers)](#services-19-docker-containers)
- [Data Sources (8 Sources)](#data-sources-8-sources)
- [Database Architecture (10 Schemas, 44+ Tables)](#database-architecture-10-schemas-44-tables)
- [Data Flow](#data-flow)
- [Scheduler & Orchestration](#scheduler--orchestration)
- [Monitoring & Observability](#monitoring--observability)
- [Security Architecture](#security-architecture)
- [Scalability & Resource Management](#scalability--resource-management)
- [Deployment Profiles](#deployment-profiles)

---

## Overview

The SEO Intelligence Platform is a production-ready, microservices-based analytics system that processes millions of data points from 8+ sources to generate AI-powered SEO insights. Built entirely with free and open-source tools, it rivals commercial solutions costing $2,000-4,000/month.

### Key Statistics

| Metric | Value |
|--------|-------|
| **Docker Services** | 19+ containers |
| **Database Tables** | 44+ tables across 10 schemas |
| **SQL Views** | 30+ analytical views |
| **Data Sources** | 8 external APIs + file systems |
| **API Endpoints** | 50+ REST endpoints |
| **Grafana Dashboards** | 10 production dashboards |
| **Monthly Cost** | $0 (100% open-source) |

---

## Architecture Principles

### 1. Separation of Concerns
- Each service has a single, well-defined responsibility
- Clear boundaries between data ingestion, processing, and serving layers
- Microservices communicate via PostgreSQL and Redis

### 2. Idempotency
- All data operations use UPSERT (INSERT ... ON CONFLICT DO UPDATE)
- Replay-safe ingestion with watermark tracking
- Deterministic insight generation with deduplication

### 3. Observability
- Prometheus metrics for all services (8 exporters)
- Comprehensive logging to `/logs` with rotation
- 10 Grafana dashboards for real-time monitoring
- Health checks on all critical services (15s-30s intervals)

### 4. Resilience
- Automatic service restarts via Docker (`restart: unless-stopped`)
- Health-based dependency management (services wait for healthy dependencies)
- Exponential backoff for API rate limiting
- Graceful degradation (core functions work even if intelligence layer fails)

### 5. Security
- Secret management via `/secrets` volume (read-only mounts)
- Isolated Docker network (`gsc_network` bridge)
- No hardcoded credentials (all via environment variables)
- PostgreSQL password protection
- Read-only file system mounts where applicable

### 6. Scalability
- Resource limits on all containers (CPU + memory)
- Horizontal scaling ready (Celery workers, Redis)
- Materialized views for performance optimization
- pgvector HNSW indexes for fast semantic search
- Log rotation (10MB max, 3 files per service)

---

## System Overview Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DATA SOURCES (8 Sources)                           │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1. Google Search Console API  │  5. Google Trends API                        │
│ 2. Google Analytics 4 API     │  6. Hugo CMS (File System)                   │
│ 3. SERP APIs (ValueSERP)      │  7. Content Scraping (Playwright)            │
│ 4. PageSpeed Insights API     │  8. Vector Embeddings (Local Models)         │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER (6 Services)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────┐    ┌─────────────────────┐   ┌──────────────────┐ │
│  │ startup_orchestrator│───▶│   api_ingestor      │   │  ga4_ingestor    │ │
│  │ (One-time backfill) │    │   (GSC → DB)        │   │  (GA4 → DB)      │ │
│  │ 60-day historical   │    │   Daily: Last 3d    │   │  Daily sync      │ │
│  └─────────────────────┘    └─────────────────────┘   └──────────────────┘ │
│                                                                               │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      DATA LAYER (2 Services)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────────────────────────────┐    ┌────────────────────────┐ │
│  │      warehouse (PostgreSQL 14)           │    │  redis (Redis 7)       │ │
│  ├──────────────────────────────────────────┤    ├────────────────────────┤ │
│  │ • 10 Schemas (gsc, ga4, serp, content...) │    │ • Celery task queue    │ │
│  │ • 44+ Tables                             │    │ • Event streams        │ │
│  │ • 30+ Views (materialized + standard)    │    │ • Cache (512MB LRU)    │ │
│  │ • pgvector extension (embeddings)        │    │ • Pub/Sub messaging    │ │
│  │ • 2GB memory limit                       │    │ • 512MB memory limit   │ │
│  └──────────────────────────────────────────┘    └────────────────────────┘ │
│                                                                               │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER (4 Services)                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐   ┌──────────────────┐   ┌─────────────────────────┐ │
│  │  insights_engine │   │    scheduler     │   │  ollama (Local LLM)     │ │
│  │  (One-shot mode) │   │  (APScheduler)   │   │  llama3.1:8b / mistral  │ │
│  │  Generates all   │   │  Config-driven   │   │  Content analysis       │ │
│  │  insights        │   │  schedules:      │   │  8GB memory limit       │ │
│  │                  │   │  - Daily 7AM UTC │   │  GPU support optional   │ │
│  │                  │   │  - Weekly Mon    │   └─────────────────────────┘ │
│  └──────────────────┘   │  - Hourly CWV    │                               │
│                         └──────────────────┘   ┌─────────────────────────┐ │
│                                                │  celery_worker          │ │
│                                                │  Async task processing  │ │
│                                                │  4 concurrent workers   │ │
│                                                │  2GB memory limit       │ │
│                                                └─────────────────────────┘ │
│                                                                               │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                       SERVING LAYER (2 Services)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────────────────┐        ┌──────────────────────────────┐  │
│  │    insights_api              │        │    mcp (MCP Server)          │  │
│  │    REST API (Port 8000)      │        │    Port 8001                 │  │
│  ├──────────────────────────────┤        ├──────────────────────────────┤  │
│  │ • /api/insights              │        │ • Claude Desktop integration │  │
│  │ • /api/properties            │        │ • Tool-based API             │  │
│  │ • /api/pages                 │        │ • Natural language queries   │  │
│  │ • /api/actions               │        │ • Insight browsing           │  │
│  │ • /api/health                │        │ • 512MB memory limit         │  │
│  │ • 512MB memory limit         │        └──────────────────────────────┘  │
│  └──────────────────────────────┘                                           │
│                                                                               │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                  MONITORING LAYER (9 Services)                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────────┐│
│  │   prometheus     │◀──│ metrics_exporter │   │   grafana               ││
│  │   Port 9090      │   │ Port 8002        │   │   Port 3000              ││
│  │   512MB memory   │   │ Custom app metrics│   │   10 Dashboards          ││
│  └────────┬─────────┘   └──────────────────┘   │   512MB memory           ││
│           │                                     └──────────────────────────┘│
│           │ Scrapes 8 exporters:                                            │
│           ├──▶ docker_stats_exporter (Port 8003) - Windows-compatible       │
│           ├──▶ cadvisor (Port 8080) - Container metrics                     │
│           ├──▶ postgres_exporter (Port 9187) - Database metrics             │
│           ├──▶ redis_exporter (Port 9121) - Cache/queue metrics             │
│           ├──▶ metrics_exporter (Port 8002) - Application metrics           │
│           ├──▶ insights_api (/metrics endpoint)                             │
│           ├──▶ scheduler (/metrics endpoint)                                │
│           └──▶ mcp (/metrics endpoint)                                      │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Services (19+ Docker Containers)

### Data Layer (2 Services)

#### 1. warehouse (PostgreSQL 14 + pgvector)

**Image**: `postgres:14-alpine`
**Container**: `gsc_warehouse`
**Port**: 5432
**Resources**: 2GB memory, 2 CPUs

**Purpose**: Central data warehouse for all SEO data

**Key Features**:
- pgvector extension for 768-dimensional embeddings
- 10 schemas: gsc, ga4, serp, performance, content, forecasts, actions, anomaly, notifications, orchestration
- 44+ tables with composite primary keys
- 30+ SQL views (materialized + standard)
- UPSERT logic for idempotency
- Watermark tracking for incremental ingestion

**Configuration**:
```yaml
environment:
  POSTGRES_DB: gsc_db
  POSTGRES_USER: gsc_user
  POSTGRES_PASSWORD: <secret>
  POSTGRES_SHARED_BUFFERS: 512MB
  POSTGRES_WORK_MEM: 64MB
volumes:
  - pgdata:/var/lib/postgresql/data
healthcheck:
  test: pg_isready -U gsc_user -d gsc_db
  interval: 10s
  retries: 5
```

**Documentation**: [DATA_MODEL.md](DATA_MODEL.md)

---

#### 2. redis (Redis 7)

**Image**: `redis:7-alpine`
**Container**: `gsc_redis`
**Port**: 6379
**Resources**: 512MB memory, 0.5 CPUs
**Profile**: `intelligence`

**Purpose**: Message broker for Celery + real-time event streams

**Key Features**:
- Celery task queue (database 0)
- Celery result backend (database 1)
- Event streams for real-time processing
- LRU eviction policy (allkeys-lru)
- AOF persistence enabled
- 512MB memory limit

**Configuration**:
```yaml
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
healthcheck:
  test: redis-cli ping
  interval: 10s
volumes:
  - redis_data:/data
```

---

### Ingestion Layer (3 Services)

#### 3. startup_orchestrator

**Container**: `gsc_startup`
**Resources**: 1GB memory, 1 CPU
**Profile**: `core`
**Restart**: `no` (one-time execution)

**Purpose**: One-time 60-day historical data backfill on first deployment

**Responsibilities**:
- Orchestrates initial data collection
- Fetches 60 days of GSC data (configurable via `BACKFILL_DAYS`)
- Fetches 60 days of GA4 data
- Runs database initialization scripts
- Exits after completion (does not restart)

**Configuration**:
```yaml
environment:
  WAREHOUSE_DSN: postgresql://...
  BACKFILL_DAYS: 60
command: python /app/scheduler/startup_orchestrator.py
```

---

#### 4. api_ingestor (GSC Ingestor)

**Container**: `gsc_api_ingestor`
**Resources**: 512MB memory, 1 CPU
**Profile**: `core`

**Purpose**: Daily ingestion of Google Search Console data

**Responsibilities**:
- Fetches last 3 days of GSC data (default `INGEST_DAYS=3`)
- Handles multiple properties (specified in `GSC_PROPERTIES`)
- Enterprise-grade rate limiting with exponential backoff
- Watermark-based incremental ingestion
- Stores in `gsc.fact_gsc_daily` table

**Rate Limiting**:
- Token bucket algorithm
- Per-property tracking
- Respects Google API quotas (1,200 requests/minute)

**Configuration**:
```yaml
environment:
  WAREHOUSE_DSN: postgresql://...
  GSC_SVC_JSON: /secrets/gsc_sa.json
  PROPERTIES: sc-domain:example.com,sc-domain:example2.com
  GSC_INITIAL_BACKFILL_DAYS: 7
```

**Documentation**: [GSC_INTEGRATION.md](../deployment/guides/GSC_INTEGRATION.md)

---

#### 5. ga4_ingestor

**Container**: `gsc_ga4_ingestor`
**Resources**: 512MB memory, 1 CPU
**Profile**: `core`

**Purpose**: Daily ingestion of Google Analytics 4 data

**Responsibilities**:
- Fetches daily GA4 session data
- Syncs user behavior metrics
- Conversion tracking
- Event aggregation
- Stores in `ga4.fact_sessions_daily` and `ga4.fact_events_daily`

**Configuration**:
```yaml
environment:
  WAREHOUSE_DSN: postgresql://...
  GA4_CREDENTIALS_PATH: /secrets/gsc_sa.json
  GA4_PROPERTY_ID: 123456789
```

**Documentation**: [GA4_INTEGRATION.md](../deployment/guides/GA4_INTEGRATION.md)

---

### Intelligence Layer (4 Services)

#### 6. insights_engine

**Container**: `gsc_insights_engine`
**Resources**: 1GB memory, 1 CPU
**Profile**: `insights`
**Restart**: `no` (one-shot execution)

**Purpose**: Generates all SEO insights using 10+ detectors

**Detectors**:
1. Traffic Drop Detector
2. Traffic Spike Detector
3. Ranking Change Detector
4. Click-Through Rate (CTR) Detector
5. Position Change Detector
6. Cannibalization Detector
7. Content Quality Detector
8. Topic Strategy Detector
9. SERP Feature Detector
10. Performance (CWV) Detector
11. Forecasting Detector

**Insight Types**:
- RISK (traffic drops, ranking losses)
- OPPORTUNITY (CTR improvement, new keywords)
- DIAGNOSIS (root cause analysis)

**Execution**:
```bash
python -m insights_core.cli refresh-insights
```

**Documentation**: [INSIGHT_ENGINE_GUIDE.md](guides/INSIGHT_ENGINE_GUIDE.md)

---

#### 7. scheduler (APScheduler)

**Container**: `gsc_scheduler`
**Resources**: 1GB memory, 1 CPU
**Profile**: `insights`

**Purpose**: Config-driven task orchestration

**Scheduled Tasks**:

| Schedule | Tasks |
|----------|-------|
| **Daily (7:00 AM UTC)** | API ingestion, GA4 collection, URL discovery, transforms, insights refresh |
| **Weekly (Monday 7:00 AM UTC)** | Watermark reconciliation, cannibalization refresh, cleanup |
| **Hourly** | Core Web Vitals monitoring (if enabled) |

**Configuration File**: `config/scheduler_config.yaml`

**Example Schedule**:
```yaml
daily_pipeline:
  enabled: true
  schedule:
    hour: 7
    minute: 0
  tasks:
    - api_ingestion
    - ga4_collection
    - url_discovery
    - transforms
    - insights_refresh
```

**Features**:
- Timezone-aware scheduling (UTC default)
- Task dependency management
- Failure recovery with retries
- Execution history logging

**Documentation**: [Scheduler Configuration](guides/SCHEDULER_CONFIG_GUIDE.md)

---

#### 8. ollama (Local LLM)

**Image**: `ollama/ollama:latest`
**Container**: `gsc_ollama`
**Port**: 11434
**Resources**: 8GB memory, 4 CPUs (GPU optional)
**Profile**: `intelligence`

**Purpose**: Local LLM inference for content analysis and optimization

**Supported Models**:
- `llama3.1:8b` (recommended, 4.7GB)
- `mistral:latest` (alternative, 4.1GB)
- `qwen2.5-coder:7b` (code-focused, 4.7GB)
- `nomic-embed-text` (embeddings, 274MB)

**Use Cases**:
- Content quality scoring
- Improvement suggestions generation
- Topic naming for clustering
- Readability optimization
- Keyword optimization
- Intent differentiation

**GPU Support**:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

**API Endpoints**:
- `POST /api/generate` - Text generation
- `POST /api/embeddings` - Vector embeddings
- `GET /api/tags` - List models

**Documentation**: [Content Intelligence Guide](guides/CONTENT_INTELLIGENCE_GUIDE.md)

---

#### 9. celery_worker

**Container**: `gsc_celery_worker`
**Resources**: 2GB memory, 2 CPUs
**Profile**: `intelligence`

**Purpose**: Distributed async task processing

**Responsibilities**:
- Async content analysis (via Ollama)
- Bulk embedding generation
- Topic auto-clustering
- Email/Slack notifications
- Long-running data processing

**Configuration**:
```yaml
command: celery -A services.tasks worker --loglevel=info --concurrency=4
environment:
  CELERY_BROKER_URL: redis://redis:6379/0
  CELERY_RESULT_BACKEND: redis://redis:6379/1
  OLLAMA_URL: http://ollama:11434
```

**Task Types**:
- `analyze_page_content` - Content quality analysis
- `generate_embeddings` - Batch embedding generation
- `cluster_topics` - Auto-clustering
- `send_notification` - Alerts

---

### Serving Layer (2 Services)

#### 10. insights_api (REST API)

**Container**: `gsc_insights_api`
**Port**: 8000
**Resources**: 512MB memory, 1 CPU
**Profile**: `api`

**Purpose**: RESTful API for insights and data access

**Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/insights` | GET | List all insights |
| `/api/insights/{id}` | GET | Get insight details |
| `/api/properties` | GET | List tracked properties |
| `/api/pages` | GET | Page performance data |
| `/api/queries` | GET | Query performance data |
| `/api/actions` | GET/POST | SEO action tracking |
| `/api/actions/{id}/execute` | POST | Execute action |
| `/api/forecasts` | GET | Traffic forecasts |
| `/api/content/similar` | POST | Semantic search |
| `/api/topics` | GET | Topic clusters |

**Authentication**: API key (optional, configurable)

**Documentation**: [API_REFERENCE.md](api/API_REFERENCE.md)

---

#### 11. mcp (Model Context Protocol Server)

**Container**: `gsc_mcp`
**Port**: 8001
**Resources**: 512MB memory, 0.5 CPUs
**Profile**: `api`

**Purpose**: Claude Desktop integration via MCP protocol

**Features**:
- Natural language queries converted to SQL
- Tool-based API for Claude Desktop
- Insight browsing and summarization
- Action recommendation
- Real-time data access

**MCP Tools**:
- `query_insights` - Search insights
- `get_page_performance` - Page metrics
- `find_similar_content` - Semantic search
- `get_recommendations` - Action suggestions

**Configuration**:
```json
{
  "mcpServers": {
    "gsc-warehouse": {
      "command": "node",
      "args": ["http://localhost:8001"]
    }
  }
}
```

**Documentation**: [MCP_INTEGRATION.md](guides/MCP_INTEGRATION.md)

---

### Monitoring Layer (9 Services)

#### 12. prometheus

**Image**: `prom/prometheus:latest`
**Container**: `gsc_prometheus`
**Port**: 9090
**Resources**: 512MB memory, 0.5 CPUs

**Purpose**: Metrics collection and time-series database

**Scrape Targets**:
1. docker_stats_exporter (8003)
2. cadvisor (8080)
3. postgres_exporter (9187)
4. redis_exporter (9121) - if intelligence profile
5. metrics_exporter (8002)
6. insights_api (/metrics)
7. scheduler (/metrics)
8. mcp (/metrics)

**Retention**: 15 days (default)

**Alert Rules**: 25+ rules across 5 categories

**Configuration**: `prometheus/prometheus.yml`

---

#### 13. grafana

**Image**: `grafana/grafana:latest`
**Container**: `gsc_grafana`
**Port**: 3000
**Resources**: 512MB memory, 0.5 CPUs

**Purpose**: Visual dashboards and monitoring

**Dashboards (10 Total)**:

**SEO Analytics (5 Dashboards)**:
1. SERP Position Tracking
2. Core Web Vitals Monitoring
3. GA4 Analytics Overview
4. GSC Overview
5. Hybrid Analytics (GSC + GA4 + SERP)

**Infrastructure Monitoring (5 Dashboards)**:
6. Infrastructure Overview
7. Database Performance
8. Application Metrics
9. Service Health
10. Alert Status

**Default Credentials**: admin/admin (change on first login)

**Documentation**: [DASHBOARD_GUIDE.md](guides/DASHBOARD_GUIDE.md), [PROMETHEUS_DASHBOARDS_GUIDE.md](guides/PROMETHEUS_DASHBOARDS_GUIDE.md)

---

#### 14. metrics_exporter

**Container**: `gsc_metrics_exporter`
**Port**: 8002
**Resources**: 256MB memory, 0.25 CPUs

**Purpose**: Custom application metrics

**Metrics Exposed**:
- `gsc_data_freshness_seconds` - Time since last data ingestion
- `gsc_insight_count` - Total insights by type
- `gsc_property_count` - Tracked properties
- `gsc_page_count` - Pages with data
- `gsc_query_count` - Tracked queries
- `gsc_collection_status` - Ingestion health
- `gsc_api_errors_total` - API error count

---

#### 15. docker_stats_exporter

**Container**: `gsc_docker_stats_exporter`
**Port**: 8003
**Resources**: 128MB memory, 0.25 CPUs

**Purpose**: Windows-compatible container metrics (alternative to cAdvisor)

**Metrics**:
- CPU usage per container
- Memory usage/limits
- Network I/O
- Container status

**Why This Exists**: cAdvisor has limited Windows support; this provides full cross-platform compatibility.

---

#### 16. cadvisor

**Image**: `gcr.io/cadvisor/cadvisor:latest`
**Container**: `gsc_cadvisor`
**Port**: 8080
**Resources**: 256MB memory, 0.25 CPUs

**Purpose**: Container-level resource metrics (Linux-optimized)

**Metrics**:
- Per-container CPU, memory, disk, network
- Container file system usage
- Performance counters

**Note**: Primarily for Linux deployments; use docker_stats_exporter on Windows

---

#### 17. postgres_exporter

**Image**: `quay.io/prometheuscommunity/postgres-exporter:latest`
**Container**: `gsc_postgres_exporter`
**Port**: 9187
**Resources**: 128MB memory, 0.25 CPUs

**Purpose**: PostgreSQL metrics

**Metrics**:
- Active connections
- Database size
- Query performance
- Cache hit ratio
- Replication lag
- Locks and deadlocks
- Transaction counts

---

#### 18. redis_exporter

**Image**: `oliver006/redis_exporter:latest`
**Container**: `gsc_redis_exporter`
**Port**: 9121
**Resources**: 64MB memory, 0.1 CPUs
**Profile**: `intelligence`

**Purpose**: Redis cache and queue metrics

**Metrics**:
- Memory usage
- Key count
- Hit/miss ratio
- Client connections
- Command statistics
- Eviction count

---

#### 19. pypi_cache (devpi)

**Image**: `muccg/devpi:latest`
**Container**: `gsc_pypi_cache`
**Resources**: 256MB memory, 0.25 CPUs

**Purpose**: Local PyPI package caching for faster Docker builds

**Benefits**:
- Speeds up Docker builds by caching Python packages
- Reduces external network calls
- Offline build support

---

## Data Sources (8 Sources)

### 1. Google Search Console API

**Type**: REST API
**Authentication**: Service Account JSON
**Rate Limit**: 1,200 requests/minute
**Data Retention**: 16 months

**Data Collected**:
- Queries (search terms)
- Pages (URLs)
- Clicks, impressions, CTR, position
- Countries, devices, search appearance

**Tables**: `gsc.fact_gsc_daily`, `gsc.properties`, `gsc.dim_queries`, `gsc.dim_pages`

**Documentation**: [GSC_INTEGRATION.md](../deployment/guides/GSC_INTEGRATION.md)

---

### 2. Google Analytics 4 API

**Type**: REST API (Data API v1)
**Authentication**: Service Account JSON
**Rate Limit**: 25,000 tokens/day

**Data Collected**:
- Sessions (user visits)
- Events (interactions)
- Conversions (goals)
- User behavior flows
- Engagement metrics

**Tables**: `ga4.fact_sessions_daily`, `ga4.fact_events_daily`, `ga4.conversions`

**Documentation**: [GA4_INTEGRATION.md](../deployment/guides/GA4_INTEGRATION.md)

---

### 3. SERP APIs (ValueSERP/SerpAPI)

**Type**: REST API
**Authentication**: API Key
**Rate Limit**: 100 searches/month (free tier)
**Cost**: $0.002-0.01 per search

**Data Collected**:
- Keyword rankings (1-100)
- SERP features (featured snippets, PAA, etc.)
- Competitor positions
- Historical rank tracking

**Tables**: `serp.queries`, `serp.rankings`, `serp.features`

**Documentation**: [SERP_TRACKING_GUIDE.md](SERP_TRACKING_GUIDE.md)

---

### 4. PageSpeed Insights API

**Type**: REST API
**Authentication**: API Key (free)
**Rate Limit**: 25,000 requests/day

**Data Collected**:
- Core Web Vitals (LCP, FID, CLS)
- Performance scores
- Lighthouse audit results
- Mobile/desktop metrics

**Tables**: `performance.page_vitals`, `performance.lighthouse_audits`

**Documentation**: [PAGESPEED_SETUP.md](PAGESPEED_SETUP.md)

---

### 5. Google Trends

**Type**: Web Scraping
**Authentication**: None (public API)

**Data Collected**:
- Search interest over time
- Related queries
- Geographic distribution

**Tables**: `trends.search_interest`

---

### 6. Hugo CMS (File System)

**Type**: Local file system
**Path**: `/hugo_content` (configurable)

**Data Collected**:
- Markdown content files
- Front matter metadata
- File modification timestamps

**Use Case**: Content optimization with Hugo Content Optimizer

**Tables**: `content.hugo_files`

**Documentation**: [HUGO_CONTENT_OPTIMIZER.md](guides/HUGO_CONTENT_OPTIMIZER.md)

---

### 7. Content Scraping (Playwright)

**Type**: Headless browser
**Technology**: Playwright (Chromium)

**Data Collected**:
- Full page HTML
- Meta tags
- Headings (H1-H6)
- Text content
- Images, links

**Tables**: `content.page_snapshots`

**Documentation**: [CONTENT_INTELLIGENCE_GUIDE.md](guides/CONTENT_INTELLIGENCE_GUIDE.md)

---

### 8. Vector Embeddings (Local Models)

**Type**: Local model inference
**Models**: sentence-transformers (`all-MiniLM-L6-v2`) or Ollama (`nomic-embed-text`)

**Data Collected**:
- 768-dimensional embeddings
- Content similarity scores
- Semantic search results

**Tables**: `content.page_snapshots` (vector columns)

**Documentation**: [CONTENT_INTELLIGENCE_GUIDE.md](guides/CONTENT_INTELLIGENCE_GUIDE.md)

---

## Database Architecture (10 Schemas, 44+ Tables)

### Schema Organization

| Schema | Purpose | Table Count | Key Tables |
|--------|---------|-------------|------------|
| **gsc** | Google Search Console data | 8 | fact_gsc_daily, dim_queries, dim_pages |
| **ga4** | Google Analytics 4 data | 6 | fact_sessions_daily, fact_events_daily |
| **serp** | SERP tracking and rankings | 5 | queries, rankings, features |
| **performance** | Core Web Vitals & Lighthouse | 4 | page_vitals, lighthouse_audits |
| **content** | Content analysis & embeddings | 8 | page_snapshots, quality_scores, topics |
| **forecasts** | Traffic predictions | 3 | property_forecasts, accuracy_tracking |
| **actions** | SEO interventions | 4 | actions, outcomes, lift_measurements |
| **anomaly** | Issue detection | 3 | anomalies, classifications |
| **notifications** | Alerting system | 4 | rules, history, delivery_status |
| **orchestration** | Agent workflows | 5 | agent_state, workflows, executions |

**Total**: 10 schemas, 44+ tables, 30+ views

**Complete Reference**: [DATA_MODEL.md](DATA_MODEL.md)

---

### Key Table Highlights

**Fact Tables (Star Schema)**:
- `gsc.fact_gsc_daily` - 16+ months of GSC data
- `ga4.fact_sessions_daily` - User session metrics
- `serp.rankings` - Daily keyword position tracking

**Dimension Tables**:
- `gsc.dim_queries` - Query metadata
- `gsc.dim_pages` - Page metadata
- `content.topics` - Content topic clusters

**Vector Embeddings**:
- `content.page_snapshots.content_embedding vector(768)` - pgvector
- HNSW indexes for fast cosine similarity search

**Views**:
- `gsc.vw_unified_performance` - FULL OUTER JOIN of GSC + GA4 + SERP
- `content.vw_content_quality` - Latest snapshots + quality scores
- `content.vw_active_cannibalization` - Active content conflicts

---

## Data Flow

### Daily Pipeline (Automated)

```
┌──────────────────────────┐
│ 1. Scheduler Triggers    │
│    (7:00 AM UTC)         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 2. API Ingestion         │
│    • GSC: Last 3 days    │
│    • GA4: Yesterday      │
│    • SERP: Monitored     │
│      keywords            │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 3. Data Storage          │
│    • UPSERT to warehouse │
│    • Watermark update    │
│    • Audit logging       │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 4. URL Discovery         │
│    • Identify high-value │
│      pages from GSC/GA4  │
│    • Add to monitored_   │
│      pages table         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 5. Transforms            │
│    • Refresh materialized│
│      views               │
│    • Calculate WoW/MoM   │
│    • Update aggregations │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 6. Insights Generation   │
│    • Run 10+ detectors   │
│    • Classify issues     │
│    • Generate actions    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 7. Notifications         │
│    • Slack alerts (high) │
│    • Email summaries     │
│    • Webhook triggers    │
└──────────────────────────┘
```

---

### Content Intelligence Pipeline

```
┌──────────────────────────┐
│ 1. Content Scraping      │
│    (Playwright)          │
│    • Fetch HTML          │
│    • Extract text        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 2. Analysis              │
│    • Readability (Flesch)│
│    • Word count, etc.    │
│    • LLM quality scoring │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 3. Embedding Generation  │
│    • sentence-transformers│
│      or Ollama           │
│    • 768-dim vectors     │
│    • Store in pgvector   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 4. Similarity & Clustering│
│    • Find similar pages  │
│    • Detect cannibalization│
│    • Auto-cluster topics │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ 5. Insight Generation    │
│    • Quality issues      │
│    • Cannibalization     │
│    • Topic opportunities │
└──────────────────────────┘
```

---

## Scheduler & Orchestration

### Configuration-Driven Scheduling

**File**: `config/scheduler_config.yaml`

**Schedule Types**:
- **Cron**: Traditional cron expressions
- **Interval**: Fixed intervals (minutes, hours)
- **Time**: Specific daily times

**Example Configuration**:

```yaml
schedules:
  daily_pipeline:
    enabled: true
    schedule:
      hour: 7
      minute: 0
      timezone: UTC
    tasks:
      - name: api_ingestion
        module: ingestors.api.gsc_api_ingestor
        function: ingest_all_properties
        args: []
        retry: true
        max_retries: 3

      - name: ga4_collection
        module: ingestors.ga4_ingestor
        function: collect_daily_data
        depends_on: [api_ingestion]

      - name: url_discovery
        module: insights_core.url_discovery
        function: sync_monitored_pages
        depends_on: [api_ingestion, ga4_collection]

      - name: transforms
        module: transforms.refresh_views
        function: refresh_all_views
        depends_on: [url_discovery]

      - name: insights_refresh
        module: insights_core.cli
        function: refresh_insights
        depends_on: [transforms]

  weekly_maintenance:
    enabled: true
    schedule:
      day_of_week: monday
      hour: 7
      minute: 0
    tasks:
      - name: watermark_reconciliation
        module: insights_core.watermarks
        function: reconcile_all_watermarks

      - name: cannibalization_refresh
        module: insights_core.detectors.cannibalization
        function: refresh_all_properties

  hourly_cwv:
    enabled: ${HOURLY_CWV_ENABLED:-false}
    schedule:
      interval:
        hours: 1
    tasks:
      - name: cwv_monitoring
        module: insights_core.detectors.performance
        function: check_core_web_vitals
```

### Task Dependencies

Tasks can depend on other tasks completing successfully:

```yaml
tasks:
  - name: task_b
    depends_on: [task_a]  # Won't run until task_a succeeds

  - name: task_c
    depends_on: [task_a, task_b]  # Waits for both
```

### Failure Handling

- **Retries**: Automatic retry with exponential backoff
- **Max Retries**: Configurable (default: 3)
- **Failure Notifications**: Slack/email alerts on persistent failures
- **Execution Logs**: Stored in `orchestration.executions` table

---

## Monitoring & Observability

### Metrics Collection

**Prometheus Scraping**:
- Interval: 15 seconds
- Retention: 15 days
- Storage: Time-series database

**Exporter Ports**:
```
8002  metrics_exporter (app metrics)
8003  docker_stats_exporter (containers)
8080  cadvisor (containers - Linux)
9187  postgres_exporter (database)
9121  redis_exporter (cache/queue)
```

### Key Metrics

**Application Metrics**:
- `gsc_data_freshness_seconds` - Data staleness
- `gsc_insight_count{type="RISK"}` - Insight counts by type
- `gsc_api_errors_total` - API failure count
- `gsc_collection_status` - Ingestion health (0 = healthy, 1 = stale)

**Infrastructure Metrics**:
- `container_cpu_usage_seconds_total` - CPU usage
- `container_memory_usage_bytes` - Memory usage
- `pg_stat_database_numbackends` - DB connections
- `redis_connected_clients` - Redis clients

### Alerts

**25+ Alert Rules** across 5 categories:

1. **Infrastructure** (8 rules)
   - High CPU usage (> 80%)
   - High memory usage (> 90%)
   - Disk space low (< 10%)
   - Container down

2. **Database** (6 rules)
   - Too many connections (> 90)
   - Low cache hit ratio (< 90%)
   - Replication lag (> 10s)
   - Deadlock detected

3. **Redis** (4 rules)
   - Memory usage high (> 450MB)
   - Evictions detected
   - Rejected connections

4. **Prometheus** (3 rules)
   - Target down
   - Scrape failures
   - Storage full

5. **Application** (4 rules)
   - Data staleness (> 48 hours)
   - API errors (> 10/hour)
   - Insight generation failures
   - Missing properties

**Alert Destinations**:
- Slack (high/critical)
- Email (medium/high)
- Webhooks (configurable)

**Configuration**: `prometheus/alerts.yml`

---

## Security Architecture

### Secret Management

**Secrets Directory**: `/secrets` (read-only mounts)

**Required Secrets**:
- `gsc_sa.json` - Google service account JSON
- `.env` - Environment variables (not committed to Git)

**Best Practices**:
- Never commit secrets to version control
- Use `.gitignore` for `/secrets` and `.env`
- Rotate service account keys every 90 days
- Limit service account permissions (principle of least privilege)

### Network Isolation

**Docker Network**: `gsc_network` (bridge)
- Subnet: `172.25.0.0/16`
- Internal DNS resolution
- Services communicate via container names (e.g., `warehouse:5432`)

**Exposed Ports** (only these are accessible from host):
```
3000   grafana
5432   warehouse (PostgreSQL)
6379   redis
8000   insights_api
8001   mcp
8002   metrics_exporter
8003   docker_stats_exporter
8080   cadvisor
9090   prometheus
9121   redis_exporter
9187   postgres_exporter
11434  ollama
```

### Authentication

- **PostgreSQL**: Password-protected (env var: `POSTGRES_PASSWORD`)
- **Grafana**: Admin credentials (env vars: `GRAFANA_USER`, `GRAFANA_PASSWORD`)
- **APIs**: Optional API key authentication (env var: `API_KEY`)

### Volume Permissions

- `/secrets`: Read-only (`:ro`)
- `/logs`: Read-write (for log writing)
- Database volumes: Persistent, isolated

---

## Scalability & Resource Management

### Resource Limits (All Services)

| Service | Memory Limit | CPU Limit | Notes |
|---------|--------------|-----------|-------|
| warehouse | 2GB | 2.0 | Highest priority |
| ollama | 8GB | 4.0 | GPU-intensive |
| celery_worker | 2GB | 2.0 | Parallel processing |
| scheduler | 1GB | 1.0 | APScheduler overhead |
| insights_engine | 1GB | 1.0 | One-shot execution |
| api_ingestor | 512MB | 1.0 | Stable workload |
| ga4_ingestor | 512MB | 1.0 | Stable workload |
| insights_api | 512MB | 1.0 | Request-response |
| mcp | 512MB | 0.5 | Lightweight |
| redis | 512MB | 0.5 | In-memory cache |
| prometheus | 512MB | 0.5 | Time-series DB |
| grafana | 512MB | 0.5 | Dashboard rendering |
| metrics_exporter | 256MB | 0.25 | Lightweight exporter |
| docker_stats_exporter | 128MB | 0.25 | Metrics scraping |
| cadvisor | 256MB | 0.25 | Metrics collection |
| postgres_exporter | 128MB | 0.25 | Metrics scraping |
| redis_exporter | 64MB | 0.1 | Metrics scraping |
| pypi_cache | 256MB | 0.25 | Package caching |

**Total Resources** (all profiles enabled):
- Memory: ~21GB
- CPUs: ~16 cores

**Minimum Recommended**:
- 16GB RAM
- 8 CPU cores
- 50GB disk space

### Log Rotation

All services use JSON file logging driver:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

**Per-service max storage**: 30MB (10MB × 3 files)
**Total max log storage**: ~600MB (20 services × 30MB)

### Horizontal Scaling

**Scalable Services**:
- `celery_worker` - Add more workers with `docker-compose up --scale celery_worker=4`
- `insights_api` - Load balance with nginx
- `mcp` - Multiple instances possible

**Non-Scalable (Single-Instance)**:
- `warehouse` - PostgreSQL (use read replicas for scaling)
- `redis` - Single instance (use Redis Cluster for scaling)
- `scheduler` - APScheduler (only one active scheduler)

---

## Deployment Profiles

Docker Compose uses profiles to enable/disable service groups:

### Profile Combinations

**Core Only** (Minimal):
```bash
docker-compose --profile core up -d
```
Services: warehouse, api_ingestor, ga4_ingestor, startup_orchestrator
Use Case: Basic data collection only

---

**Core + Insights**:
```bash
docker-compose --profile core --profile insights up -d
```
Services: + insights_engine, scheduler
Use Case: Data collection + insight generation

---

**Core + Insights + API**:
```bash
docker-compose --profile core --profile insights --profile api up -d
```
Services: + insights_api, mcp
Use Case: Full platform with API access

---

**All Features** (Core + Insights + API + Intelligence):
```bash
docker-compose --profile core --profile insights --profile api --profile intelligence up -d
```
Services: + ollama, redis, celery_worker, redis_exporter
Use Case: Complete platform with AI/ML features

---

**Monitoring** (Always Enabled):
- prometheus, grafana, metrics_exporter
- docker_stats_exporter, cadvisor
- postgres_exporter

---

## Related Documentation

- **[Data Model](DATA_MODEL.md)** - Complete schema reference
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment
- **[Setup Guide](../deployment/guides/SETUP_GUIDE.md)** - Initial installation
- **[Insight Engine Guide](guides/INSIGHT_ENGINE_GUIDE.md)** - Insight generation
- **[Content Intelligence Guide](guides/CONTENT_INTELLIGENCE_GUIDE.md)** - AI-powered content analysis
- **[Multi-Agent System](guides/MULTI_AGENT_SYSTEM.md)** - AI agent architecture
- **[URL Discovery Guide](guides/URL_DISCOVERY_GUIDE.md)** - Automatic URL monitoring
- **[Dashboard Guide](guides/DASHBOARD_GUIDE.md)** - Grafana dashboards
- **[Prometheus Guide](guides/PROMETHEUS_DASHBOARDS_GUIDE.md)** - Infrastructure monitoring

---

**Last Updated**: 2025-11-28
**Version**: 2.0
**Author**: Complete System Documentation
