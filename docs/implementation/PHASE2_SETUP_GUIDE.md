# Phase 2 Setup Guide - Intelligence & Orchestration

**Version**: 1.0
**Date**: 2025-11-21
**Phase**: Intelligence & Orchestration
**Prerequisites**: Phase 1 Complete

---

## Overview

Phase 2 upgrades the system from reactive analytics to **proactive intelligent orchestration** using:
- **LangGraph** - Stateful AI agent workflows with reasoning
- **Natural Language Queries** - Ask questions in plain English (text-to-SQL)
- **Topic Clustering** - Automatic content organization
- **Redis Streams** - Real-time event processing
- **Content Scraping** - Automated monitoring with change detection

**Time to Complete**: 1-2 hours
**Difficulty**: Intermediate to Advanced

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Service Deployment](#service-deployment)
6. [Testing](#testing)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)

---

## Prerequisites

### Phase 1 Must Be Complete

Ensure Phase 1 is fully operational:
```bash
# Check Phase 1 services are running
docker-compose ps

# Should see:
# - gsc_warehouse (PostgreSQL)
# - gsc_ollama (LLM server)
# - gsc_redis (Message broker)
# - gsc_celery_worker (Task queue)
# - gsc_api (FastAPI)
# - gsc_grafana (Dashboards)
# - gsc_prometheus (Metrics)
```

### System Requirements

- **RAM**: 12GB minimum (16GB recommended)
  - Ollama (LLM): 4-8GB
  - PostgreSQL: 2GB
  - Redis: 512MB
  - Celery workers: 1GB
  - Playwright: 2GB

- **Disk**: 10GB free space
  - Playwright browser binaries: ~500MB
  - Docker images: ~2GB
  - Data storage: varies

- **OS**: Linux, macOS, or Windows with WSL2

---

## Installation

### 1. Install Phase 2 Python Dependencies

```bash
# Navigate to project root
cd site-data-warehouse

# Install Phase 2 packages
pip install -r requirements.txt

# Verify installations
python -c "import langgraph; print('LangGraph OK')"
python -c "import playwright; print('Playwright OK')"
python -c "from PIL import Image; print('Pillow OK')"
python -c "import Levenshtein; print('Levenshtein OK')"
```

### 2. Install Playwright Browsers

Playwright requires browser binaries:

```bash
# Install Chromium (headless)
playwright install chromium

# Install dependencies (Linux only)
# Ubuntu/Debian:
playwright install-deps chromium

# Verify installation
playwright --version
```

### 3. Install Additional Ollama Models

Phase 2 benefits from additional models:

```bash
# Pull smaller, faster model for quick queries
docker-compose exec ollama ollama pull mistral:7b

# Already have llama3.1:8b from Phase 1
# Already have nomic-embed-text from Phase 1

# Verify models
docker-compose exec ollama ollama list
```

---

## Configuration

### 1. Environment Variables

Update your `.env` file:

```bash
# Phase 2 Environment Variables

# Redis Streams (already configured in Phase 1)
REDIS_URL=redis://redis:6379/0

# Celery (already configured in Phase 1)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Ollama (already configured in Phase 1)
OLLAMA_URL=http://ollama:11434

# Phase 2 Specific
# LangGraph model selection
LANGGRAPH_MODEL=llama3.1:8b

# Natural Language Query
NLQ_MODEL=llama3.1:8b
NLQ_MAX_RESULTS=100

# Topic Clustering
CLUSTERING_MIN_CLUSTERS=5
CLUSTERING_MAX_CLUSTERS=20

# Content Scraper
SCRAPER_TIMEOUT=30
SCRAPER_HEADLESS=true
SCRAPER_MAX_CONCURRENT=3

# Real-time Events
REDIS_STREAM_RETENTION=10000  # Keep last 10K events
```

### 2. Ollama Configuration

For better performance, configure Ollama memory:

```bash
# docker-compose.yml - already configured, but verify:
services:
  ollama:
    environment:
      - OLLAMA_NUM_PARALLEL=4  # Parallel requests
      - OLLAMA_MAX_LOADED_MODELS=2  # Keep 2 models in memory
```

---

## Database Setup

Phase 2 uses existing Phase 1 schemas but adds new features.

### 1. Verify Phase 1 Schemas Exist

```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "\dn"

# Should see:
# - gsc
# - content
# - intelligence
# - public
```

### 2. Check Required Tables

```bash
docker-compose exec warehouse psql -U gsc_user -d gsc_db << EOF
-- Check Phase 1 tables needed by Phase 2
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname IN ('content', 'intelligence', 'gsc')
ORDER BY schemaname, tablename;
EOF
```

Required tables:
- `content.page_snapshots` (for scraper)
- `content.topics` (for clustering)
- `content.page_topics` (for clustering)
- `content.content_changes` (for scraper)
- `intelligence.traffic_forecasts` (for agents)
- `gsc.actions` (for agents)

### 3. Create Indexes for Phase 2 Performance

```sql
-- Run these in PostgreSQL
docker-compose exec warehouse psql -U gsc_user -d gsc_db << 'EOF'

-- Topic clustering performance
CREATE INDEX IF NOT EXISTS idx_page_snapshots_property_embedding
ON content.page_snapshots(property)
WHERE content_embedding IS NOT NULL;

-- NL Query performance
CREATE INDEX IF NOT EXISTS idx_unified_performance_date_property
ON gsc.vw_unified_page_performance(date, property);

-- Event stream integration
CREATE INDEX IF NOT EXISTS idx_actions_created_at
ON gsc.actions(created_at DESC);

-- Content changes for scraper
CREATE INDEX IF NOT EXISTS idx_content_changes_detected_at
ON content.content_changes(detected_at DESC);

ANALYZE content.page_snapshots;
ANALYZE content.topics;
ANALYZE gsc.actions;

EOF
```

---

## Service Deployment

### 1. Update Docker Compose (Already Complete)

Phase 2 uses existing services from Phase 1. Verify they're running:

```bash
docker-compose --profile core --profile insights --profile intelligence up -d

# Check health
docker-compose ps
docker-compose logs -f celery_worker
```

### 2. Restart Celery Workers

Celery workers need to reload to pick up Phase 2 tasks:

```bash
# Restart workers
docker-compose restart celery_worker

# Verify Phase 2 tasks are registered
docker-compose exec celery_worker celery -A services.tasks inspect registered | grep -E "auto_cluster|nl_query|intelligent_watcher|monitor_content"

# Should see:
# - services.tasks.auto_cluster_topics_task
# - services.tasks.natural_language_query_task
# - services.tasks.run_intelligent_watcher_task
# - services.tasks.monitor_content_changes_task
```

### 3. Verify Redis Streams

```bash
# Test Redis Streams
docker-compose exec redis redis-cli

# In Redis CLI:
XINFO STREAM traffic:anomalies
XINFO STREAM content:changes

# Exit: Ctrl+D
```

---

## Testing

### 1. Run Phase 2 Unit Tests

```bash
# Run all Phase 2 tests
pytest tests/test_topic_clustering.py -v
pytest tests/test_nl_query.py -v
pytest tests/agents/test_intelligent_watcher.py -v
pytest tests/test_event_stream.py -v
pytest tests/test_content_scraper.py -v

# Run all at once
pytest tests/ -v -k "topic_clustering or nl_query or intelligent_watcher or event_stream or content_scraper"
```

### 2. Integration Tests

Enable integration tests (requires running services):

```bash
# Set environment variable
export RUN_INTEGRATION_TESTS=1

# Run integration tests
pytest tests/ -v -m integration

# Clean up test data
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "DELETE FROM content.topics WHERE name LIKE 'Test%';"
```

### 3. Quick Smoke Test

```bash
# Test each Phase 2 feature
python << 'EOF'
import asyncio
from insights_core.topic_clustering import TopicClusterer
from insights_core.nl_query import NaturalLanguageQuery
from agents.watcher.intelligent_watcher import IntelligentWatcherAgent
from services.event_stream import EventStream
from services.content_scraper import ContentScraper

async def smoke_test():
    print("Testing Topic Clustering...")
    clusterer = TopicClusterer()
    await clusterer.close()
    print("✓ Topic Clustering OK")

    print("Testing NL Query...")
    nlq = NaturalLanguageQuery()
    await nlq.close()
    print("✓ NL Query OK")

    print("Testing Intelligent Watcher...")
    watcher = IntelligentWatcherAgent()
    await watcher.close()
    print("✓ Intelligent Watcher OK")

    print("Testing Event Stream...")
    stream = EventStream()
    stream.close()
    print("✓ Event Stream OK")

    print("Testing Content Scraper...")
    scraper = ContentScraper()
    await scraper.close()
    print("✓ Content Scraper OK")

    print("\n✅ All Phase 2 modules initialized successfully!")

asyncio.run(smoke_test())
EOF
```

---

## Usage Examples

### 1. Topic Clustering

```python
from insights_core.topic_clustering import TopicClusterer
import asyncio

async def cluster_content():
    clusterer = TopicClusterer()

    # Auto-cluster content (detects optimal number of topics)
    result = await clusterer.auto_cluster_property(
        property='https://blog.aspose.net',
        n_clusters=None  # Auto-detect
    )

    print(f"Created {result['topics_created']} topics")
    print(f"Organized {result['pages_clustered']} pages")

    # View topic performance
    for topic in result['topic_performance']:
        print(f"\n{topic['name']}:")
        print(f"  Pages: {topic['page_count']}")
        print(f"  Avg Clicks: {topic['avg_clicks']}")
        print(f"  Avg Position: {topic['avg_position']}")

    await clusterer.close()

asyncio.run(cluster_content())
```

### 2. Natural Language Queries

```python
from insights_core.nl_query import NaturalLanguageQuery
import asyncio

async def ask_questions():
    nlq = NaturalLanguageQuery()

    questions = [
        "Show me the top 10 pages by clicks last month",
        "Which pages lost traffic last week?",
        "What pages have quality scores below 60?",
        "Show me pages with cannibalization issues"
    ]

    for question in questions:
        print(f"\nQ: {question}")

        result = await nlq.query(question, execute=True)

        if result['success']:
            print(f"SQL: {result['sql']}")
            print(f"Rows: {result['row_count']}")
            print(f"Answer: {result['answer']}")
        else:
            print(f"Error: {result.get('error', 'Unknown')}")

    await nlq.close()

asyncio.run(ask_questions())
```

### 3. Intelligent Watcher Agent

```python
from agents.watcher.intelligent_watcher import IntelligentWatcherAgent
import asyncio

async def monitor_traffic():
    watcher = IntelligentWatcherAgent()

    # Analyze property for anomalies
    result = await watcher.analyze_property('https://blog.aspose.net')

    print(f"Observations: {len(result['observations'])}")
    for obs in result['observations'][:5]:
        print(f"  - {obs}")

    print(f"\nFindings: {len(result['findings'])}")
    for finding in result['findings']:
        print(f"  - {finding['type']}: {finding['severity']}")

    print(f"\nRecommendations: {len(result['recommendations'])}")
    for rec in result['recommendations'][:5]:
        print(f"  - [{rec['priority']}] {rec['title']}")

    await watcher.close()

asyncio.run(monitor_traffic())
```

### 4. Real-Time Event Streaming

```python
from services.event_stream import EventStream

# Publisher
stream = EventStream()

# Publish anomaly
event_id = stream.publish_anomaly(
    property='https://blog.aspose.net',
    page_path='/python/tutorial/',
    metric='clicks',
    actual=100.0,
    expected=500.0,
    deviation_pct=-80.0,
    severity='critical'
)

print(f"Published event: {event_id}")

# Consumer
events = stream.consume_events(
    stream=EventStream.TRAFFIC_ANOMALIES,
    consumer_group='alert_handlers',
    consumer_name='handler_1',
    count=10
)

for event in events:
    print(f"Event: {event['event_type']}")
    print(f"Data: {event['data']}")

stream.close()
```

### 5. Content Scraping & Monitoring

```python
from services.content_scraper import ContentScraper
import asyncio

async def monitor_pages():
    scraper = ContentScraper()

    # Scrape and detect changes
    result = await scraper.scrape_and_compare(
        property='https://blog.aspose.net',
        page_path='/cells/python/tutorial/'
    )

    if result['success']:
        if result.get('first_scrape'):
            print("First scrape - baseline established")
        elif result.get('changed'):
            print(f"Changes detected: {result['change_type']}")
            print(f"Change score: {result['change_score']:.1f}%")
            print(f"Modified: {', '.join(result['changes'])}")
        else:
            print("No changes detected")

    # Monitor multiple pages
    pages = ['/page1/', '/page2/', '/page3/']
    monitor_result = await scraper.monitor_property(
        'https://blog.aspose.net',
        page_paths=pages
    )

    print(f"\nMonitored: {monitor_result['pages_monitored']} pages")
    print(f"Changes: {monitor_result['changes_detected']}")

    await scraper.close()

asyncio.run(monitor_pages())
```

### 6. Scheduled Tasks (Celery)

```python
from services.tasks import (
    auto_cluster_topics_task,
    natural_language_query_task,
    run_intelligent_watcher_task,
    monitor_content_changes_task
)

# Queue tasks for background execution
auto_cluster_topics_task.delay('https://blog.aspose.net')
run_intelligent_watcher_task.delay('https://blog.aspose.net')
monitor_content_changes_task.delay('https://blog.aspose.net')

# Execute NL query
result = natural_language_query_task.delay(
    "Show me pages that lost traffic",
    context={'property': 'https://blog.aspose.net'}
)

# Wait for result
print(result.get(timeout=30))
```

---

## Troubleshooting

### Common Issues

#### 1. LangGraph Agent Fails

**Symptom**: Agent workflows timeout or fail

**Solutions**:
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check model is loaded
docker-compose exec ollama ollama list

# Test LLM directly
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Say hello",
  "stream": false
}'

# Switch to faster model
# In .env: LANGGRAPH_MODEL=mistral:7b
docker-compose restart celery_worker
```

#### 2. Natural Language Query Returns Unsafe SQL

**Symptom**: Query validation fails

**Solutions**:
- Check query contains only SELECT
- Ensure tables are in whitelist
- Add LIMIT clause

```python
from insights_core.nl_query import QueryValidator

validator = QueryValidator()
result = validator.validate_sql("YOUR SQL HERE")
print(result)
```

#### 3. Topic Clustering Produces Too Many/Few Topics

**Symptom**: Topics are too granular or too broad

**Solutions**:
```bash
# Adjust cluster range in .env
CLUSTERING_MIN_CLUSTERS=8
CLUSTERING_MAX_CLUSTERS=15

# Or specify explicitly
python << 'EOF'
from insights_core.topic_clustering import TopicClusterer
import asyncio

async def recluster():
    clusterer = TopicClusterer()
    result = await clusterer.auto_cluster_property(
        property='https://blog.aspose.net',
        n_clusters=12  # Force 12 topics
    )
    await clusterer.close()

asyncio.run(recluster())
EOF
```

#### 4. Playwright Browser Fails

**Symptom**: Content scraper cannot launch browser

**Solutions**:
```bash
# Reinstall browsers
playwright install chromium
playwright install-deps

# Test browser
python << 'EOF'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://example.com')
    print(f"Title: {page.title()}")
    browser.close()
EOF

# On Linux, install system dependencies
sudo apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2
```

#### 5. Redis Streams Events Not Consumed

**Symptom**: Events published but not processed

**Solutions**:
```bash
# Check Redis Streams
docker-compose exec redis redis-cli XINFO STREAM traffic:anomalies

# Check consumer groups
docker-compose exec redis redis-cli XINFO GROUPS traffic:anomalies

# Check pending events
docker-compose exec redis redis-cli XPENDING traffic:anomalies alert_handlers

# Reset consumer group (DANGER: loses position)
docker-compose exec redis redis-cli XGROUP DESTROY traffic:anomalies alert_handlers
docker-compose exec redis redis-cli XGROUP CREATE traffic:anomalies alert_handlers 0
```

#### 6. High Memory Usage

**Symptom**: System runs out of memory

**Solutions**:
```bash
# Monitor memory
docker stats

# Reduce Ollama memory
# In docker-compose.yml:
services:
  ollama:
    mem_limit: 6g

# Use smaller model
LANGGRAPH_MODEL=mistral:7b

# Reduce concurrent scrapers
SCRAPER_MAX_CONCURRENT=1

# Limit Celery workers
docker-compose exec celery_worker celery -A services.tasks control pool_shrink 2
```

---

## Performance Tuning

### 1. Ollama Optimization

```bash
# docker-compose.yml
services:
  ollama:
    environment:
      - OLLAMA_NUM_PARALLEL=4  # Increase for more concurrent requests
      - OLLAMA_MAX_LOADED_MODELS=2  # Keep 2 models in memory
      - OLLAMA_KEEP_ALIVE=24h  # Keep models loaded longer
```

### 2. Database Query Optimization

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM content.page_snapshots WHERE property = 'https://blog.aspose.net';

-- Update statistics
ANALYZE content.page_snapshots;
ANALYZE content.topics;
ANALYZE gsc.actions;

-- Vacuum if needed
VACUUM ANALYZE;
```

### 3. Redis Tuning

```bash
# docker-compose.yml
services:
  redis:
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

### 4. Celery Worker Scaling

```bash
# Increase workers
docker-compose up -d --scale celery_worker=4

# Adjust concurrency
docker-compose exec celery_worker celery -A services.tasks control pool_grow 2
```

### 5. Playwright Performance

```python
# In services/content_scraper.py, adjust:
browser = await playwright.chromium.launch(
    headless=True,
    args=[
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--disable-setuid-sandbox',
        '--no-sandbox'
    ]
)

# Reduce screenshot quality
await page.screenshot(quality=50, type='jpeg')
```

---

## Monitoring & Observability

### 1. Check Phase 2 Task Status

```bash
# Celery Flower (if enabled)
open http://localhost:5555

# Check active tasks
docker-compose exec celery_worker celery -A services.tasks inspect active

# Check scheduled tasks
docker-compose exec celery_worker celery -A services.tasks inspect scheduled
```

### 2. Monitor Redis Streams

```bash
# Stream lengths
docker-compose exec redis redis-cli XLEN traffic:anomalies
docker-compose exec redis redis-cli XLEN content:changes

# Consumer lag
docker-compose exec redis redis-cli XINFO GROUPS traffic:anomalies
```

### 3. Database Monitoring

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Slow queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds';

-- Table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname IN ('content', 'intelligence', 'gsc')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Next Steps

### 1. Run First Analysis

```bash
# Generate embeddings for existing content
python << 'EOF'
from services.tasks import generate_embeddings_task
generate_embeddings_task.delay('https://blog.aspose.net')
EOF

# Cluster content into topics
python << 'EOF'
from services.tasks import auto_cluster_topics_task
auto_cluster_topics_task.delay('https://blog.aspose.net')
EOF

# Run intelligent watcher
python << 'EOF'
from services.tasks import run_intelligent_watcher_task
run_intelligent_watcher_task.delay('https://blog.aspose.net')
EOF
```

### 2. Set Up Monitoring

- Configure alerts for critical anomalies
- Set up dashboards for topic performance
- Monitor content changes

### 3. Move to Phase 3

Phase 3 will add:
- SERP position tracking (ValueSERP API)
- Core Web Vitals monitoring (PageSpeed Insights)
- Causal impact analysis (statistical testing)
- Auto PR generation (GitHub integration)

---

## Support

- **Documentation**: `/docs/`
- **Issues**: GitHub Issues
- **Tests**: `/tests/` - Run with `pytest -v`

---

**Phase 2 Setup Complete!** 🎉

You now have:
- ✅ Intelligent LangGraph agents with reasoning
- ✅ Natural language query interface
- ✅ Automatic topic clustering
- ✅ Real-time event processing
- ✅ Automated content monitoring

**Cost**: Still $0/month (100% free/open-source)
