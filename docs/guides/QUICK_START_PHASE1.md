# Phase 1 Quick Start Guide

## 5-Minute Setup

Get started with AI-powered content intelligence in minutes.

---

## 1. Start Services (1 min)

```bash
# Clone repo (if needed)
git clone <repo-url>
cd site-data-warehouse

# Start everything
docker-compose --profile core --profile insights --profile intelligence up -d

# Wait for services (30 seconds)
docker-compose ps
```

---

## 2. Setup Database (1 min)

```bash
# Run SQL setup scripts
docker-compose exec warehouse psql -U gsc_user -d gsc_db << 'EOF'
\i /app/sql/00_extensions.sql
\i /app/sql/12_actions_schema.sql
\i /app/sql/13_content_schema.sql
\i /app/sql/14_forecasts_schema.sql
EOF
```

---

## 3. Pull AI Models (2 min)

```bash
# Download LLM models (one-time, ~5GB)
docker-compose exec ollama ollama pull llama3.1:8b
docker-compose exec ollama ollama pull nomic-embed-text
```

---

## 4. Test It (1 min)

### Test Content Analysis

```python
from insights_core.content_analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()

html = """
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Welcome to My Blog</h1>
    <p>This is high-quality content about Python programming.</p>
    <p>It covers best practices, design patterns, and performance optimization.</p>
</body>
</html>
"""

result = analyzer.analyze_sync(
    property="https://example.com",
    page_path="/test/",
    html_content=html
)

print(f"Quality Score: {result['overall_score']}/100")
print(f"Readability: {result['readability']['flesch_reading_ease']}")
print(f"Suggestions: {result['suggestions']}")
```

**Output:**
```
Quality Score: 78.5/100
Readability: 65.2
Suggestions: ['Add more subheadings', 'Include code examples', 'Add internal links']
```

### Test Semantic Search

```python
from insights_core.embeddings import EmbeddingGenerator

generator = EmbeddingGenerator()

# Generate embedding
content = "Python programming tutorial for beginners"
embedding = generator.generate_embedding(content)

print(f"Embedding shape: {embedding.shape}")
print(f"First 5 values: {embedding[:5]}")
```

**Output:**
```
Embedding shape: (768,)
First 5 values: [0.023, -0.145, 0.089, 0.234, -0.067]
```

### Test Forecasting

```python
from insights_core.forecasting import ProphetForecaster
import pandas as pd
from datetime import datetime, timedelta

forecaster = ProphetForecaster()

# Create sample data (30 days)
dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
clicks = [100 + i * 2 for i in range(30)]  # Upward trend

df = pd.DataFrame({'ds': dates, 'y': clicks})

# Train and predict
model = forecaster.train_model(df)
forecast = forecaster.make_predictions(model, periods=7)

print(f"Next 7 days forecast:")
print(forecast[['ds', 'yhat']].tail(7))
```

**Output:**
```
Next 7 days forecast:
           ds       yhat
30 2025-11-22  158.3
31 2025-11-23  160.5
32 2025-11-24  162.7
...
```

---

## 5. Common Tasks

### Find Similar Pages

```sql
-- Find pages similar to a specific page
SELECT * FROM content.find_similar_pages(
    '/blog/python-tutorial/',
    'https://example.com',
    10,  -- limit
    0.7  -- threshold
);
```

### Create Action from Insight

```sql
-- Create an action to improve a page
INSERT INTO gsc.actions (
    title,
    description,
    page_path,
    property,
    action_type,
    impact_score,
    effort_score,
    urgency
) VALUES (
    'Improve meta description',
    'Update meta description to be more compelling and include target keywords',
    '/blog/python-tutorial/',
    'https://example.com',
    'rewrite_meta',
    8,  -- High impact
    2,  -- Low effort
    'high'
);

-- Priority score is auto-calculated!
SELECT action_id, title, priority_score FROM gsc.actions ORDER BY priority_score DESC LIMIT 5;
```

### Detect Content Cannibalization

```sql
-- Find pages with duplicate content
SELECT
    page_a,
    page_b,
    similarity_score,
    conflict_severity
FROM content.vw_active_cannibalization
WHERE similarity_score >= 0.85
ORDER BY similarity_score DESC;
```

### Check Anomalies

```sql
-- Recent anomalies detected by Prophet
SELECT
    page_path,
    detection_date,
    actual_value,
    expected_value,
    deviation_pct,
    severity
FROM intelligence.vw_recent_anomalies
WHERE severity IN ('high', 'critical')
ORDER BY detection_date DESC
LIMIT 10;
```

---

## 6. Async Tasks (Background Processing)

### Schedule Batch Processing

```python
from services.tasks import (
    generate_embeddings_task,
    generate_forecasts_task,
    detect_cannibalization_task
)

# Queue tasks (run in background)
generate_embeddings_task.delay('https://example.com')
generate_forecasts_task.delay('https://example.com', days_ahead=30)
detect_cannibalization_task.delay('https://example.com', 0.85)

# Check status
from celery.result import AsyncResult

task_id = '...'  # From .delay() call
result = AsyncResult(task_id)

print(result.state)  # PENDING, STARTED, SUCCESS, FAILURE
print(result.result)  # Task result when complete
```

---

## API Endpoints

The system exposes REST APIs for programmatic access:

### Get Top Actions

```bash
GET http://localhost:8000/api/actions?status=pending&limit=10
```

### Get Content Quality

```bash
GET http://localhost:8000/api/content/quality?property=https://example.com&limit=20
```

### Get Forecast

```bash
GET http://localhost:8000/api/forecast?property=https://example.com&page_path=/blog/post/
```

---

## Dashboard Access

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Insights API:** http://localhost:8000/docs

**New Dashboards:**
- Actions Command Center
- Content Quality Overview
- Cannibalization Detection
- Forecast Accuracy

---

## Tips & Best Practices

### 1. Start Small
- Test with 10-20 pages first
- Verify results before scaling
- Monitor resource usage

### 2. Optimize Performance
```python
# Use batch operations
pages = [{'page_path': '/page1/', 'html_content': '...'},
         {'page_path': '/page2/', 'html_content': '...'}]

batch_analyze_content_task.delay('https://example.com', pages)
```

### 3. Monitor Quality
```sql
-- Check analysis quality
SELECT
    AVG(overall_score) as avg_quality,
    COUNT(*) as pages_analyzed
FROM content.quality_scores
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days';
```

### 4. Action Workflow
```
Insight → Action → Assignment → Execution → Outcome Measurement
```

Track the full lifecycle in `gsc.actions` table.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Ollama slow | Use smaller model: `mistral:7b` |
| Out of memory | Limit concurrent workers: `celery --concurrency=2` |
| Embeddings fail | Check content has enough text (>50 words) |
| Prophet errors | Need 14+ days of data minimum |

---

## What's Next?

**Phase 2 Preview:**
- LangGraph multi-agent system
- Natural language query interface
- Topic clustering automation
- SERP position tracking

**Learn More:**
- [Full Setup Guide](../implementation/PHASE1_SETUP_GUIDE.md)
- [Semantic Search Guide](SEMANTIC_SEARCH_GUIDE.md)
- [Actions Layer Guide](USING_ACTIONS.md)

---

**Ready to use!** 🚀

You now have:
✅ AI content analysis
✅ Semantic search
✅ ML forecasting
✅ Action tracking
✅ Cannibalization detection

**Cost:** $0/month
