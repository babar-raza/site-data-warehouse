# SEO Intelligence Platform - Quick Reference Guide

A handy cheat sheet for common operations and commands.

---

## Table of Contents
- [Common Commands](#common-commands)
- [Database Operations](#database-operations)
- [Celery Tasks](#celery-tasks)
- [Data Collection](#data-collection)
- [Alerting](#alerting)
- [Multi-Agent Workflows](#multi-agent-workflows)
- [Grafana](#grafana)
- [Troubleshooting](#troubleshooting)
- [Python API Examples](#python-api-examples)

---

## Common Commands

### Start All Services
```bash
# Start database and Redis
docker-compose up -d postgres redis

# Start Celery worker
celery -A services.tasks worker --loglevel=info --concurrency=4 &

# Start Celery beat scheduler
celery -A services.tasks beat --loglevel=info &

# Start Grafana
docker-compose up -d grafana

# Start Ollama (local LLM)
ollama serve &
```

### Stop All Services
```bash
# Stop Celery
pkill -f "celery worker"
pkill -f "celery beat"

# Stop Docker services
docker-compose down

# Stop Ollama
pkill ollama
```

### Check Service Status
```bash
# Check Celery workers
celery -A services.tasks inspect active

# Check scheduled tasks
celery -A services.tasks inspect scheduled

# Check Redis
redis-cli ping

# Check PostgreSQL
psql -U postgres -d seo_warehouse -c "SELECT 1"

# Check Ollama
curl http://localhost:11434/api/tags
```

---

## Database Operations

### Connect to Database
```bash
psql -U postgres -d seo_warehouse
```

### Common Queries

#### Check Data Freshness
```sql
-- Latest GSC data
SELECT MAX(data_date) FROM gsc.query_stats;

-- Latest SERP checks
SELECT MAX(checked_at) FROM serp.position_history;

-- Latest CWV checks
SELECT MAX(checked_at) FROM performance.cwv_metrics;

-- Recent alerts
SELECT * FROM notifications.alert_history
ORDER BY triggered_at DESC LIMIT 10;
```

#### Performance Metrics
```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('seo_warehouse'));

-- Table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Row counts
SELECT
    schemaname,
    tablename,
    n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
```

#### Top Performing Content
```sql
-- Top 10 pages by clicks (last 30 days)
SELECT
    page_path,
    SUM(clicks) as total_clicks,
    AVG(position) as avg_position,
    SUM(impressions) as total_impressions
FROM gsc.query_stats
WHERE data_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY page_path
ORDER BY total_clicks DESC
LIMIT 10;

-- Biggest position drops (last 7 days)
SELECT
    query_text,
    property,
    target_page_path,
    position_change,
    previous_position,
    current_position
FROM serp.position_changes
WHERE checked_at >= CURRENT_DATE - INTERVAL '7 days'
    AND position_change > 3
ORDER BY position_change DESC;

-- Poor CWV pages
SELECT
    page_path,
    lcp,
    fid,
    cls,
    performance_score
FROM performance.cwv_metrics
WHERE checked_at >= CURRENT_DATE - INTERVAL '7 days'
    AND (lcp > 2500 OR fid > 100 OR cls > 0.1)
ORDER BY performance_score ASC;
```

### Database Maintenance
```bash
# Vacuum and analyze
psql -U postgres -d seo_warehouse -c "VACUUM ANALYZE;"

# Reindex
psql -U postgres -d seo_warehouse -c "REINDEX DATABASE seo_warehouse;"

# Check for bloat
psql -U postgres -d seo_warehouse -f scripts/check_bloat.sql
```

---

## Celery Tasks

### Trigger Tasks Manually
```bash
# Collect GSC data
celery -A services.tasks call collect_gsc_data --args='["https://yourdomain.com"]'

# Collect GA4 data
celery -A services.tasks call collect_ga4_data --args='["123456789"]'

# Track SERP positions
celery -A services.tasks call track_serp_positions --args='["https://yourdomain.com"]'

# Check Core Web Vitals
celery -A services.tasks call check_core_web_vitals --args='["https://yourdomain.com"]'

# Detect anomalies
celery -A services.tasks call detect_serp_anomalies --args='["https://yourdomain.com"]'

# Run multi-agent workflow
celery -A services.tasks call run_multi_agent_workflow \
  --args='["daily_analysis", "https://yourdomain.com"]'

# Process notification queue
celery -A services.tasks call process_notification_queue
```

### Monitor Tasks
```bash
# View active tasks
celery -A services.tasks inspect active

# View scheduled tasks
celery -A services.tasks inspect scheduled

# View registered tasks
celery -A services.tasks inspect registered

# View task stats
celery -A services.tasks inspect stats

# Purge all tasks
celery -A services.tasks purge
```

---

## Data Collection

### Manual Collection Scripts

#### Collect GSC Data
```python
import asyncio
from ingestors.gsc.gsc_client import GSCClient

async def collect():
    client = GSCClient()
    await client.collect_data(
        property_url="https://yourdomain.com",
        start_date="2025-01-01",
        end_date="2025-01-22"
    )

asyncio.run(collect())
```

#### Track SERP Position
```python
import asyncio
from insights_core.serp_tracker import SerpTracker

async def track():
    tracker = SerpTracker()
    result = await tracker.track_query({
        'query_text': 'your keyword',
        'property': 'https://yourdomain.com',
        'location': 'United States',
        'device': 'desktop'
    })
    print(f"Position: {result['position']}")

asyncio.run(track())
```

#### Check Core Web Vitals
```python
import asyncio
from insights_core.cwv_monitor import CoreWebVitalsMonitor

async def check():
    monitor = CoreWebVitalsMonitor()
    metrics = await monitor.fetch_page_metrics(
        url="https://yourdomain.com",
        strategy="mobile"
    )
    print(f"LCP: {metrics['lcp']}ms")
    print(f"CLS: {metrics['cls']}")
    print(f"Score: {metrics['performance_score']}")

asyncio.run(check())
```

---

## Alerting

### Create Alert Rules
```python
import asyncio
from notifications.alert_manager import AlertManager
from notifications.channels.slack_notifier import SlackNotifier

async def setup():
    manager = AlertManager()
    manager.register_notifier('slack', SlackNotifier())

    # SERP drop alert
    await manager.create_alert_rule(
        rule_name="Position Drop",
        rule_type="serp_drop",
        conditions={"position_drop": 3},
        severity="high",
        channels=["slack"],
        property="https://yourdomain.com"
    )

asyncio.run(setup())
```

### Trigger Test Alert
```python
import asyncio
from notifications.alert_manager import AlertManager

async def test():
    manager = AlertManager()

    # Get rule ID from database first
    # SELECT rule_id FROM notifications.alert_rules LIMIT 1;

    await manager.trigger_alert(
        rule_id="your-rule-id",
        property="https://yourdomain.com",
        title="Test Alert",
        message="Testing notification system"
    )

    await manager.process_notification_queue()

asyncio.run(test())
```

### Check Recent Alerts
```sql
-- Last 24 hours of alerts
SELECT
    ar.rule_name,
    ah.severity,
    ah.title,
    ah.triggered_at,
    ah.status
FROM notifications.alert_history ah
JOIN notifications.alert_rules ar ON ah.rule_id = ar.rule_id
WHERE ah.triggered_at >= NOW() - INTERVAL '24 hours'
ORDER BY ah.triggered_at DESC;

-- Alert summary by severity
SELECT
    severity,
    COUNT(*) as alert_count,
    COUNT(DISTINCT rule_id) as rules_triggered
FROM notifications.alert_history
WHERE triggered_at >= NOW() - INTERVAL '7 days'
GROUP BY severity
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END;
```

---

## Multi-Agent Workflows

### Run Workflows
```python
import asyncio
from agents.orchestration.supervisor_agent import SupervisorAgent
from agents.orchestration.serp_analyst_agent import SerpAnalystAgent
from agents.orchestration.performance_agent import PerformanceAgent

async def run_workflow():
    supervisor = SupervisorAgent()
    supervisor.register_agent('serp_analyst', SerpAnalystAgent())
    supervisor.register_agent('performance_agent', PerformanceAgent())

    result = await supervisor.run_workflow(
        workflow_type='daily_analysis',
        trigger_event={'source': 'manual'},
        property='https://yourdomain.com'
    )

    print(f"Workflow: {result['workflow_id']}")
    print(f"Recommendations: {len(result['recommendations'])}")
    for rec in result['recommendations']:
        print(f"  - [{rec['priority']}] {rec['type']}: {rec['action']}")

asyncio.run(run_workflow())
```

### Check Workflow History
```sql
-- Recent workflows
SELECT
    workflow_name,
    workflow_type,
    status,
    started_at,
    completed_at,
    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds
FROM orchestration.workflows
ORDER BY started_at DESC
LIMIT 10;

-- Agent decisions
SELECT
    w.workflow_name,
    ad.agent_name,
    ad.decision_type,
    ad.confidence,
    ad.created_at
FROM orchestration.agent_decisions ad
JOIN orchestration.workflows w ON ad.workflow_id = w.workflow_id
WHERE ad.created_at >= NOW() - INTERVAL '7 days'
ORDER BY ad.created_at DESC;
```

---

## Grafana

### Access Dashboards
```bash
# Open Grafana
open http://localhost:3000

# Default credentials
Username: admin
Password: admin
```

### Dashboard URLs
```
SERP Position Tracking:
http://localhost:3000/d/serp-tracking

Core Web Vitals:
http://localhost:3000/d/cwv-monitoring

GA4 Overview:
http://localhost:3000/d/ga4-overview

GSC Overview:
http://localhost:3000/d/gsc-overview

Hybrid Overview:
http://localhost:3000/d/hybrid-overview
```

### Custom Grafana Queries

#### Top Queries by Position Change
```sql
SELECT
    checked_at as time,
    query_text as metric,
    position_change as value
FROM serp.position_changes
WHERE $__timeFilter(checked_at)
    AND position_change > 3
ORDER BY checked_at;
```

#### CWV Trends
```sql
SELECT
    checked_at as time,
    'LCP' as metric,
    lcp as value
FROM performance.cwv_metrics
WHERE $__timeFilter(checked_at)
    AND page_path = '$page_path'
    AND device = '$device'
ORDER BY checked_at;
```

---

## Troubleshooting

### Check Logs
```bash
# Celery worker logs
tail -f /var/log/celery/worker.log

# Application logs
tail -f /var/log/seo-platform/app.log

# PostgreSQL logs
tail -f /var/log/postgresql/postgresql-16-main.log

# Redis logs
docker logs redis
```

### Common Issues

#### "No data in Grafana"
```bash
# Check if data exists
psql -U postgres -d seo_warehouse -c "SELECT COUNT(*) FROM gsc.query_stats"

# Check Grafana datasource
# Navigate to: Configuration → Data sources → PostgreSQL → Test

# Verify time range in dashboard
```

#### "Celery tasks not running"
```bash
# Check worker is alive
celery -A services.tasks inspect ping

# Check scheduled tasks
celery -A services.tasks inspect scheduled

# Restart worker
pkill -f "celery worker"
celery -A services.tasks worker --loglevel=info --concurrency=4
```

#### "API rate limit exceeded"
```bash
# Check API usage
# GSC: 1,200 queries/minute
# GA4: 10 queries/second
# ValueSERP: 100 searches/month (free tier)

# Reduce collection frequency in config
```

#### "Database connection errors"
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U postgres -c "SELECT 1"

# Check max connections
psql -U postgres -c "SHOW max_connections"
psql -U postgres -c "SELECT count(*) FROM pg_stat_activity"
```

---

## Python API Examples

### Forecasting
```python
import asyncio
from insights_core.forecasting import Forecaster

async def forecast():
    forecaster = Forecaster()
    result = await forecaster.forecast_property(
        property='https://yourdomain.com',
        days_ahead=30
    )

    print(f"Forecasted clicks: {result['forecasted_clicks']}")
    print(f"Confidence interval: {result['confidence_interval']}")

asyncio.run(forecast())
```

### Content Analysis
```python
import asyncio
from insights_core.content_analyzer import ContentAnalyzer

async def analyze():
    analyzer = ContentAnalyzer()
    result = await analyzer.analyze_page(
        url='https://yourdomain.com/page'
    )

    print(f"Readability: {result['readability_score']}")
    print(f"Word count: {result['word_count']}")
    print(f"Suggestions: {result['suggestions']}")

asyncio.run(analyze())
```

### Anomaly Detection
```python
import asyncio
from insights_core.anomaly_detector import AnomalyDetector

async def detect():
    detector = AnomalyDetector()
    anomalies = await detector.detect_serp_anomalies(
        property_url='https://yourdomain.com',
        lookback_days=30
    )

    for anomaly in anomalies:
        print(f"{anomaly['metric_type']}: {anomaly['severity']}")
        print(f"  Deviation: {anomaly['deviation_score']}")
        print(f"  Method: {anomaly['detection_method']}")

asyncio.run(detect())
```

### Natural Language Query
```python
import asyncio
from insights_core.nl_query import NLQueryEngine

async def query():
    engine = NLQueryEngine()
    result = await engine.query(
        "What are my top 10 queries by clicks in the last 30 days?"
    )

    print(result['data'])
    print(f"Explanation: {result['explanation']}")

asyncio.run(query())
```

### Topic Clustering
```python
import asyncio
from insights_core.topic_clustering import TopicClusterer

async def cluster():
    clusterer = TopicClusterer()
    clusters = await clusterer.cluster_content(
        property='https://yourdomain.com',
        n_clusters=5
    )

    for cluster in clusters:
        print(f"Cluster: {cluster['label']}")
        print(f"Pages: {len(cluster['pages'])}")

asyncio.run(cluster())
```

---

## Environment Variables Quick Reference

```bash
# Database
WAREHOUSE_DSN=postgresql://user:pass@localhost:5432/seo_warehouse

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0

# Google APIs
GSC_PROPERTIES=https://yourdomain.com
GSC_CREDENTIALS_PATH=/path/to/gsc_credentials.json
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_PATH=/path/to/ga4_credentials.json

# SERP Tracking
SERP_API_PROVIDER=valueserp
VALUESERP_API_KEY=your_key

# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

---

## Keyboard Shortcuts & Aliases

### Useful Bash Aliases
```bash
# Add to ~/.bashrc or ~/.zshrc

# SEO Platform shortcuts
alias seo-start='cd ~/seo-platform && docker-compose up -d && celery -A services.tasks worker -l info &'
alias seo-stop='pkill -f celery && cd ~/seo-platform && docker-compose down'
alias seo-logs='tail -f /var/log/seo-platform/app.log'
alias seo-db='psql -U postgres -d seo_warehouse'
alias seo-worker='celery -A services.tasks inspect active'
alias seo-tasks='celery -A services.tasks inspect scheduled'
```

---

## Performance Tips

1. **Database Indexes**: Run `ANALYZE` after large data imports
2. **Celery Concurrency**: Adjust based on CPU cores (cores * 2)
3. **Redis Memory**: Set `maxmemory-policy allkeys-lru` for cache eviction
4. **PostgreSQL**: Tune `shared_buffers` to 25% of RAM
5. **API Rate Limits**: Batch requests and add delays
6. **Grafana**: Use time-based indexes for better query performance

---

## Support

- Documentation: [docs/](../docs/)
- Issues: [GitHub Issues](https://github.com/yourusername/site-data-warehouse/issues)
- Troubleshooting: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
