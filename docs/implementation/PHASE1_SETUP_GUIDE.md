# Phase 1 Setup Guide

## Overview

This guide walks you through setting up the Phase 1 enhancements for the GSC Data Warehouse, transforming it from a basic analytics system into an AI-powered content intelligence platform.

**Phase 1 Includes:**
- ✅ Actions Layer (task tracking from insights)
- ✅ pgvector (semantic search and content clustering)
- ✅ Ollama (local LLM for content analysis)
- ✅ Prophet (ML-based traffic forecasting)
- ✅ Hugo Content Sync (static site integration)

**Cost:** $0/month (all free/open-source)

---

## Prerequisites

### System Requirements

- **OS:** Linux, macOS, or Windows (with WSL2)
- **RAM:** 8GB minimum, 16GB recommended (for Ollama)
- **Disk:** 20GB free space
- **Docker:** 20.10+
- **Docker Compose:** 2.0+

### Optional: GPU Support

If you have an NVIDIA GPU:
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

Then uncomment the GPU section in `docker-compose.yml` for the Ollama service.

---

## Step 1: Database Setup

### Enable pgvector Extension

```bash
# Run extension setup
docker-compose exec warehouse psql -U gsc_user -d gsc_db -f /app/sql/00_extensions.sql
```

This enables:
- **vector** - for embeddings and semantic search
- **pg_trgm** - for fuzzy text matching
- **uuid-ossp** - for UUID generation
- **tablefunc** - for advanced analytics

### Create New Schemas

```bash
# Create actions, content, and intelligence schemas
docker-compose exec warehouse psql -U gsc_user -d gsc_db -f /app/sql/12_actions_schema.sql
docker-compose exec warehouse psql -U gsc_user -d gsc_db -f /app/sql/13_content_schema.sql
docker-compose exec warehouse psql -U gsc_user -d gsc_db -f /app/sql/14_forecasts_schema.sql
```

**What This Creates:**
- `gsc.actions` - Actionable tasks from insights
- `content.page_snapshots` - Content with embeddings
- `content.topics` - Content clusters/topics
- `content.cannibalization_pairs` - Duplicate content detection
- `intelligence.traffic_forecasts` - Prophet predictions
- `intelligence.anomaly_log` - ML-detected anomalies

---

## Step 2: Update Dependencies

```bash
# Install new Python packages
pip install -r requirements.txt

# Note: This includes:
# - prophet (forecasting)
# - ollama (LLM client)
# - sentence-transformers (embeddings)
# - langchain (LLM orchestration)
# - beautifulsoup4, textstat, readability-lxml (content analysis)
# - python-frontmatter, GitPython (Hugo sync)
# - celery, redis (async tasks)
```

---

## Step 3: Start Intelligence Services

### Option A: Using Docker Compose

```bash
# Start all services including intelligence layer
docker-compose --profile core --profile insights --profile intelligence up -d

# This starts:
# - warehouse (PostgreSQL)
# - ollama (local LLM)
# - redis (task queue)
# - celery_worker (async processing)
# - insights_engine, insights_api
# - prometheus, grafana
```

### Option B: Individual Services

```bash
# Start Ollama
docker-compose up -d ollama

# Pull Ollama models (first time only)
docker-compose exec ollama ollama pull llama3.1:8b
docker-compose exec ollama ollama pull nomic-embed-text

# Start Redis
docker-compose up -d redis

# Start Celery workers
docker-compose up -d celery_worker
```

---

## Step 4: Verify Installation

### Check Services

```bash
# Check all services are running
docker-compose ps

# Should show:
# - gsc_warehouse (healthy)
# - gsc_ollama (healthy)
# - gsc_redis (healthy)
# - gsc_celery_worker (running)
```

### Test Ollama

```bash
# Test Ollama API
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Say hello",
  "stream": false
}'

# Should return JSON with response
```

### Test pgvector

```bash
# Test vector extension
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
"

# Should show: vector | 0.5.0 (or similar)
```

### Test Database Schemas

```bash
# Verify new tables exist
docker-compose exec warehouse psql -U gsc_user -d gsc_db -c "
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname IN ('content', 'intelligence')
ORDER BY schemaname, tablename;
"

# Should show:
# content | page_snapshots
# content | topics
# content | cannibalization_pairs
# intelligence | traffic_forecasts
# intelligence | anomaly_log
# etc.
```

---

## Step 5: Initial Data Population

### Generate First Embeddings

```python
from insights_core.embeddings import EmbeddingGenerator

generator = EmbeddingGenerator()

# Generate embeddings for all existing pages
result = generator.generate_for_property('https://blog.aspose.net')

print(f"Generated {result['embeddings_created']} embeddings")
```

### Run First Forecast

```python
from insights_core.forecasting import ProphetForecaster

forecaster = ProphetForecaster()

# Generate 30-day forecast
result = forecaster.forecast_sync(
    property='https://blog.aspose.net',
    days_ahead=30
)

print(f"Created {result['records_stored']} forecast records")
```

### Analyze Content

```python
from insights_core.content_analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()

# Analyze a page
html = "<html>...</html>"  # Your page HTML
result = analyzer.analyze_sync(
    property='https://blog.aspose.net',
    page_path='/cells/net/add-pivot-table-in-existing-excel-worksheet/',
    html_content=html
)

print(f"Quality score: {result['overall_score']}")
```

---

## Step 6: Setup Scheduled Tasks

### Using Celery Beat (Recommended)

Create `celerybeat-schedule.py`:

```python
from celery.schedules import crontab

# Add to your Celery configuration
CELERYBEAT_SCHEDULE = {
    'daily-forecasts': {
        'task': 'generate_forecasts',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'args': ('https://blog.aspose.net',)
    },
    'weekly-embeddings': {
        'task': 'generate_embeddings',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Sunday 1 AM
        'args': ('https://blog.aspose.net',)
    },
    'weekly-cannibalization': {
        'task': 'detect_cannibalization',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
        'args': ('https://blog.aspose.net', 0.85)
    }
}
```

### Manual Trigger

```bash
# Trigger tasks manually
docker-compose exec celery_worker celery -A services.tasks call generate_forecasts --args='["https://blog.aspose.net"]'
```

---

## Step 7: Hugo Integration (Optional)

If you have Hugo sites:

```python
from services.hugo_sync import HugoContentSync

# Initialize sync
syncer = HugoContentSync(
    hugo_repo_path='/path/to/your/hugo/site',
    property='https://blog.aspose.net'
)

# Sync all content
result = syncer.sync_sync()

print(f"Synced {result['synced_count']} Hugo pages")

# Link to GSC data
link_result = syncer.link_to_gsc()
print(f"Linked {link_result['linked_pages']} pages to GSC")
```

---

## Configuration

### Environment Variables

Add to `.env`:

```bash
# Ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_PORT=11434

# Redis
REDIS_PORT=6379
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Optional: GPU support for Ollama
# OLLAMA_GPU_ENABLED=true
```

### Ollama Models

Available models:
- `llama3.1:8b` - General purpose (4.7GB)
- `mistral-nemo` - Fast and accurate (5.3GB)
- `nomic-embed-text` - Embeddings only (274MB)

To change models, edit `insights_core/content_analyzer.py`:
```python
def __init__(self, model: str = 'mistral-nemo'):  # Change here
```

---

## Troubleshooting

### Ollama Won't Start

```bash
# Check logs
docker-compose logs ollama

# Common issues:
# 1. Port already in use
lsof -i :11434
# Kill conflicting process

# 2. Insufficient memory
# Reduce Docker memory limits in docker-compose.yml
```

### pgvector Installation Failed

```bash
# Install manually
docker-compose exec warehouse sh -c "
apt-get update && apt-get install -y postgresql-14-pgvector
"

# Then restart
docker-compose restart warehouse
```

### Celery Workers Not Processing

```bash
# Check worker status
docker-compose exec celery_worker celery -A services.tasks inspect active

# Check queue
docker-compose exec celery_worker celery -A services.tasks inspect stats

# Restart workers
docker-compose restart celery_worker
```

### Prophet Model Training Slow

Prophet can be slow on first run. To speed up:

1. Reduce training data:
```python
forecaster.fetch_historical_data(days_back=30)  # Instead of 90
```

2. Disable yearly seasonality for short datasets:
```python
model = forecaster.train_model(df, yearly_seasonality=False)
```

---

## Performance Optimization

### Embeddings

```python
# Batch process for better performance
from services.tasks import generate_embeddings_task

# Process in background
task = generate_embeddings_task.delay('https://blog.aspose.net')

# Check status
print(task.state)  # PENDING, STARTED, SUCCESS, FAILURE
```

### Forecasting

```python
# Cache forecasts (valid for 24 hours)
# Don't regenerate unless data changed

# Check last forecast date
SELECT MAX(created_at) FROM intelligence.traffic_forecasts;
```

### Content Analysis

```python
# Only analyze changed pages
# Check content_hash before reanalyzing

SELECT page_path, content_hash
FROM content.page_snapshots
WHERE analyzed_at < CURRENT_DATE - INTERVAL '7 days';
```

---

## Next Steps

1. **Explore Semantic Search** - [SEMANTIC_SEARCH_GUIDE.md](SEMANTIC_SEARCH_GUIDE.md)
2. **Use Actions Layer** - [ACTIONS_GUIDE.md](ACTIONS_GUIDE.md)
3. **Configure Dashboards** - [DASHBOARD_GUIDE.md](../analysis/DASHBOARD_GUIDE.md)
4. **Integrate Hugo** - [HUGO_INTEGRATION.md](../deployment/guides/HUGO_INTEGRATION.md)

---

## Support

- **Documentation:** `/docs/`
- **Issues:** `/reports/`
- **Tests:** `pytest tests/`
- **Logs:** `docker-compose logs [service]`

**Phase 1 Complete!** 🎉

You now have:
- AI-powered content analysis
- Semantic search and clustering
- ML-based forecasting
- Actionable insights tracking
- Hugo integration

**Total Cost:** $0/month (all free/open-source)
