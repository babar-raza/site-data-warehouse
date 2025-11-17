# GSC Data Warehouse - Hybrid Insight Engine
**Unified Analytics Platform combining Google Search Console & Google Analytics 4**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 13+](https://img.shields.io/badge/postgresql-13+-blue.svg)](https://www.postgresql.org/)

---

## 🎯 Overview

This is a production-ready **Hybrid Insight Engine** that implements the "ultimate sustainable plan" by combining:
- **Data Strategy:** Unified view joining GSC + GA4 metrics into a single golden table
- **Architecture:** Robust insight engine with detector pattern, repository persistence, and multi-agent intelligence

### What Makes This "Hybrid"?

Traditional approaches suffer from data silos:
- **GSC-only systems** can't see conversion data or user behavior
- **GA4-only systems** miss search visibility and ranking data

Our Hybrid Plan **fuses both** into `vw_unified_page_performance`, enabling insights like:
- 🔴 "Page lost 45% clicks AND 30% conversions week-over-week" (correlated drop)
- 🟡 "High GSC impressions but terrible GA4 conversion rate" (intent mismatch)
- 🟢 "Impression spike +80% — opportunity to optimize CTR" (growth potential)

---

## 🏗️ Architecture

### The Three Pillars

```
┌─────────────────────────────────────────────────────────┐
│              1. UNIFIED DATA LAYER                      │
│  vw_unified_page_performance (GSC ⊕ GA4)               │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │ GSC Metrics  │◄───►│ GA4 Metrics  │                  │
│  │ • Clicks     │    │ • Sessions    │                  │
│  │ • Impress.   │    │ • Conversions │                  │
│  │ • Position   │    │ • Engagement  │                  │
│  └──────────────┘    └──────────────┘                  │
│         ▼                    ▼                           │
│  ┌─────────────────────────────────────┐                │
│  │ Time-Series Calculations            │                │
│  │ • Week-over-Week (WoW) changes      │                │
│  │ • Month-over-Month (MoM) trends     │                │
│  │ • Rolling 7/28-day averages         │                │
│  │ • Opportunity index, quality scores │                │
│  └─────────────────────────────────────┘                │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌────────────┐ ┌──────────┐ ┌─────────────┐
│ Anomaly    │ │Diagnosis │ │ Opportunity │
│ Detector   │ │ Detector │ │  Detector   │
└─────┬──────┘ └─────┬────┘ └──────┬──────┘
      │              │              │
      └──────────────┼──────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│         2. INSIGHT ENGINE (Repository Pattern)          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ InsightRepository (gsc.insights table)           │   │
│  │ • Deterministic IDs (prevents duplicates)        │   │
│  │ • Status workflow (new → investigating → fixed)  │   │
│  │ • Category: risk, opportunity, diagnosis, trend  │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌──────────┐  ┌────────────┐  ┌──────────────┐
│ Watcher  │  │Diagnostician│  │  Strategist  │
│  Agent   │  │   Agent     │  │    Agent     │
└─────┬────┘  └──────┬─────┘  └──────┬───────┘
      │              │                │
      └──────────────┼────────────────┘
                     ▼
┌─────────────────────────────────────────────────────────┐
│         3. MULTI-AGENT INTELLIGENCE LAYER               │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │ Message Bus  │◄──►│ State Manager│                  │
│  └──────────────┘    └──────────────┘                  │
│  Findings → Diagnoses → Recommendations                 │
└─────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### 🔍 Unified Analytics
- **GSC + GA4 fusion** in single view for holistic insights
- **Time-series analysis** with WoW/MoM percentage changes
- **Zero data loss** via FULL OUTER JOIN (handles missing GA4)
- **Fast queries** optimized with materialized views and indexes

### 🎯 Intelligent Detection
- **AnomalyDetector:** Finds correlated drops (clicks + conversions)
- **DiagnosisDetector:** Root cause analysis (e.g., "drop after CMS update")
- **OpportunityDetector:** Growth potential (impression spikes, low CTR pages)
- **Hybrid rules:** Leverages both GSC and GA4 in detection logic

### 🤖 Multi-Agent System
- **WatcherAgent:** Monitors data quality and collection status
- **DiagnosticianAgent:** Deep-dive analysis with hypothesis testing
- **StrategistAgent:** Generates actionable recommendations
- **DispatcherAgent:** Orchestrates agent pipeline with message bus

### 📊 Production-Ready
- **Idempotent operations:** Safe to re-run without side effects
- **Comprehensive logging:** Structured logs with correlation IDs
- **Health checks:** All services monitored with auto-restart
- **Docker Compose:** Single-command deployment

---

## 🚀 Quick Start

### Prerequisites
- **PostgreSQL 13+** (database)
- **Python 3.9+** (runtime)
- **Docker & Docker Compose** (containerization)
- **Google Cloud Service Account** with GSC API access
- **(Optional)** GA4 API credentials

### 1. Clone & Setup
```bash
git clone <repository-url>
cd gsc-data-warehouse

# Install dependencies
pip install -r requirements.txt

# Setup secrets (see deployment/SETUP_GUIDE.md)
cp secrets/gsc_sa.json.template secrets/gsc_sa.json
# Edit secrets/gsc_sa.json with your credentials
```

### 2. Database Setup
```bash
# Start PostgreSQL (via Docker)
docker-compose up -d warehouse

# Run schema migrations
for script in sql/*.sql; do
    psql $WAREHOUSE_DSN -f "$script"
done

# Verify setup
psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"
```

### 3. Initial Data Load
```bash
# Ingest GSC data (last 30 days)
python ingestors/api/gsc_api_ingestor.py \
    --date-start $(date -d '30 days ago' +%Y-%m-%d) \
    --date-end $(date +%Y-%m-%d)

# (Optional) Ingest GA4 data
python ingestors/ga4/ga4_extractor.py

# Refresh analytical views
python warehouse/refresh_views.py
```

### 4. Generate Insights
```bash
# Run Insight Engine
python -m insights_core.cli refresh

# View generated insights
psql $WAREHOUSE_DSN -c "
    SELECT 
        category,
        severity,
        title,
        description
    FROM gsc.vw_insights_actionable
    ORDER BY severity, generated_at DESC
    LIMIT 10;"
```

### 5. Start Services
```bash
# Start all services
docker-compose up -d

# Verify health
docker-compose ps

# View logs
docker-compose logs -f insights_engine
```

---

## 📁 Project Structure

```
gsc-data-warehouse/
├── sql/                          # Database schemas
│   ├── 01_schema.sql            # GSC tables
│   ├── 04_ga4_schema.sql        # GA4 tables  
│   ├── 05_unified_view.sql      # ⭐ Hybrid unified view
│   ├── 06_materialized_views.sql # Performance optimizations
│   └── 11_insights_table.sql    # Insights storage
│
├── insights_core/                # ⭐ Insight Engine (Hybrid)
│   ├── engine.py                # Main orchestrator
│   ├── models.py                # Pydantic models (Insight, etc.)
│   ├── repository.py            # Database CRUD
│   ├── config.py                # Configuration
│   ├── detectors/               # Detection modules
│   │   ├── anomaly.py           # Finds GSC+GA4 anomalies
│   │   ├── diagnosis.py         # Root cause analysis
│   │   └── opportunity.py       # Growth opportunities
│   └── channels/                # Output channels
│       ├── slack.py             # Slack notifications
│       └── webhook.py           # Custom webhooks
│
├── agents/                       # Multi-Agent System
│   ├── watcher/                 # Data monitoring
│   ├── diagnostician/           # Analysis
│   ├── strategist/              # Recommendations
│   ├── dispatcher/              # Orchestration
│   └── base/                    # Shared infrastructure
│       ├── message_bus.py       # Agent communication
│       └── state_manager.py     # Persistence
│
├── ingestors/                    # Data Collection
│   ├── api/                     # GSC ingestion
│   │   ├── gsc_api_ingestor.py  # Main GSC collector
│   │   └── rate_limiter.py      # API rate limiting
│   └── ga4/                     # GA4 ingestion
│       └── ga4_extractor.py     # GA4 data collector
│
├── mcp/                          # Model Context Protocol
│   └── mcp_server.py            # Claude interface
│
├── tests/                        # Test Suite
│   ├── e2e/                     # End-to-end tests
│   ├── agents/                  # Agent tests
│   ├── test_detectors.py        # Detector tests
│   └── test_insight_repository.py # Repository tests
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md          # System architecture
│   ├── API_REFERENCE.md         # API documentation
│   ├── DEPLOYMENT.md            # Deployment guide
│   └── deployment/              # Deployment runbooks
│
├── deployment/                   # ⭐ Deployment Scripts
│   ├── windows/                 # Windows deployment
│   └── linux/                   # Linux deployment
│
├── docker-compose.yml           # Service orchestration
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

**⭐ = Core Hybrid Plan components**

---

## 🎓 Usage Examples

### Query Unified View
```python
# Get pages with correlated drops (hybrid insight)
SELECT 
    page_path,
    gsc_clicks,
    gsc_clicks_change_wow,
    ga_conversions,
    ga_conversions_change_wow,
    opportunity_index
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
    AND gsc_clicks_change_wow < -20  -- GSC drop
    AND ga_conversions_change_wow < -20  -- GA4 drop
ORDER BY gsc_clicks_change_wow;
```

### Programmatic Insight Detection
```python
from insights_core.engine import InsightEngine
from insights_core.config import InsightsConfig

# Initialize engine
config = InsightsConfig()
engine = InsightEngine(config)

# Run all detectors
stats = engine.refresh(property='sc-domain:example.com')

print(f"Created {stats['total_insights_created']} insights")
print(f"Breakdown: {stats['insights_by_detector']}")
```

### Query Insights via MCP
```python
# Claude Desktop can query via MCP server
# Tools available:
# - get_insights: Query insights by filters
# - get_insight_by_id: Retrieve specific insight
# - update_insight_status: Mark as investigating/resolved
```

---

## 🧪 Testing

### Run Test Suite
```bash
# Unit tests
pytest tests/ -v

# Detector tests (verify hybrid logic)
pytest tests/test_detectors.py -v

# E2E tests (full pipeline)
bash tests/e2e/run_e2e_tests.sh

# Performance benchmarks
bash tests/e2e/test_performance.sh
```

### Manual Testing
```bash
# Verify unified view
psql $WAREHOUSE_DSN -c "SELECT * FROM gsc.validate_unified_view_time_series();"

# Test insight creation
python -c "
from insights_core.detectors import AnomalyDetector
from insights_core.repository import InsightRepository
from insights_core.config import InsightsConfig
import os

repo = InsightRepository(os.environ['WAREHOUSE_DSN'])
config = InsightsConfig()
detector = AnomalyDetector(repo, config)
count = detector.detect()
print(f'Created {count} insights')
"
```

See [`E2E_TEST_PLAN.md`](E2E_TEST_PLAN.md) for comprehensive testing guide.

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System architecture and design |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | API endpoints and schemas |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Deployment instructions |
| [`docs/UNIFIED_VIEW_GUIDE.md`](docs/UNIFIED_VIEW_GUIDE.md) | Unified view deep-dive |
| [`docs/DETECTOR_GUIDE.md`](docs/DETECTOR_GUIDE.md) | Writing custom detectors |
| [`E2E_TEST_PLAN.md`](E2E_TEST_PLAN.md) | End-to-end testing guide |

---

## 🔧 Configuration

### Environment Variables
```bash
# Database
export WAREHOUSE_DSN="postgresql://gsc_user:password@localhost:5432/gsc_db"

# GSC API
export GSC_SA_PATH="/path/to/gsc_sa.json"
export GSC_PROPERTY="sc-domain:example.com"

# GA4 (Optional)
export GA4_PROPERTY_ID="123456789"
export GA4_CREDENTIALS_PATH="/path/to/ga4_credentials.json"

# Insight Engine
export INSIGHTS_RISK_THRESHOLD=-20      # Clicks drop % threshold
export INSIGHTS_OPPORTUNITY_THRESHOLD=50 # Impressions spike % threshold
```

### Detector Thresholds
Customize in `insights_core/config.py`:
```python
class InsightsConfig:
    risk_threshold_clicks_pct: float = -20  # Traffic drop %
    risk_threshold_conversions_pct: float = -20  # Conversion drop %
    opportunity_threshold_impressions_pct: float = 50  # Impression spike %
```

---

## 🐛 Troubleshooting

### Unified View Returns No Data
```bash
# Check if GSC data exists
psql $WAREHOUSE_DSN -c "SELECT COUNT(*) FROM gsc.fact_gsc_daily;"

# If zero, ingest data
python ingestors/api/gsc_api_ingestor.py --date-start 2024-11-01 --date-end 2024-11-15
```

### WoW Calculations Are NULL
- **Cause:** Need 7+ days of data for week-over-week
- **Solution:** Backfill historical data
```bash
python scripts/backfill_historical.py --days 30
```

### Detectors Create No Insights
- **Expected behavior** if traffic is stable (no anomalies)
- **Check for anomalies:**
```sql
SELECT COUNT(*) FROM gsc.vw_unified_anomalies;
```

### Agent Pipeline Fails
- **Check logs:** `docker-compose logs dispatcher`
- **Verify database permissions:** `GRANT ALL ON SCHEMA gsc TO gsc_user;`
- **Review agent execution history:**
```sql
SELECT * FROM gsc.agent_executions ORDER BY started_at DESC LIMIT 5;
```

---

## 🚦 Deployment

### Production Deployment
See [`deployment/PRODUCTION_GUIDE.md`](deployment/PRODUCTION_GUIDE.md)

Quick deploy:
```bash
# Linux
./deployment/linux/deploy.sh

# Windows
deployment\windows\deploy.bat
```

### Monitoring
```bash
# View service status
docker-compose ps

# Check health endpoints
curl http://localhost:8000/health  # MCP server
curl http://localhost:8001/health  # Insights API (if enabled)

# View Grafana dashboards
open http://localhost:3000  # Default: admin/admin
```

---

## 🤝 Contributing

### Adding a New Detector
```python
# insights_core/detectors/my_detector.py
from insights_core.detectors.base import BaseDetector
from insights_core.models import InsightCreate, InsightCategory

class MyDetector(BaseDetector):
    def detect(self, property: str = None) -> int:
        # 1. Query vw_unified_page_performance
        conn = self._get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM gsc.vw_unified_page_performance
            WHERE <your conditions>
        """)
        rows = cur.fetchall()
        
        # 2. Analyze rows and create insights
        insights_created = 0
        for row in rows:
            insight = InsightCreate(
                property=row['property'],
                entity_type=EntityType.PAGE,
                entity_id=row['page_path'],
                category=InsightCategory.OPPORTUNITY,
                title="Your Title",
                description="Your description",
                severity=InsightSeverity.MEDIUM,
                confidence=0.8,
                metrics=InsightMetrics(...),
                window_days=7,
                source="MyDetector"
            )
            self.repository.create(insight)
            insights_created += 1
        
        return insights_created
```

Register in `insights_core/engine.py`:
```python
from insights_core.detectors.my_detector import MyDetector

self.detectors = [
    AnomalyDetector(self.repository, self.config),
    DiagnosisDetector(self.repository, self.config),
    OpportunityDetector(self.repository, self.config),
    MyDetector(self.repository, self.config),  # ← Add here
]
```

---

## 📊 Performance

### Benchmarks (100K rows)
- **Unified view query (30 days):** <2s
- **Insight detection (full refresh):** <30s
- **Agent pipeline (full execution):** <60s

### Scalability
- **Tested up to:** 10M rows in `fact_gsc_daily`
- **Materialized views:** Refresh in <5 minutes
- **Partitioning:** Date-based partitions recommended for >1 year data

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file

---

## 🙏 Acknowledgments

Built using:
- **PostgreSQL** - Rock-solid data warehouse
- **Pydantic** - Data validation
- **Docker** - Containerization
- **FastAPI** - API framework (if using REST API)
- **Google APIs** - GSC & GA4 data sources

**Inspired by:** The need for holistic SEO + conversion analytics in a single platform.

---

## 📞 Support

- **Documentation:** [`docs/`](docs/)
- **Issues:** GitHub Issues (if applicable)
- **Testing:** See [`E2E_TEST_PLAN.md`](E2E_TEST_PLAN.md)

---

**Ready to deploy?** See [`deployment/QUICKSTART.md`](deployment/QUICKSTART.md)

**Need help?** Check [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
