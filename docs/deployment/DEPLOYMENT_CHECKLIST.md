# SEO Intelligence Platform - Deployment Checklist

This checklist guides you through deploying the SEO Intelligence Platform to production.

---

## Pre-Deployment Requirements

### Infrastructure
- [ ] **PostgreSQL 16+** installed and accessible
- [ ] **Redis 7+** installed and accessible
- [ ] **Python 3.11+** installed
- [ ] **Docker & Docker Compose** installed (optional but recommended)
- [ ] **Minimum 4GB RAM** available
- [ ] **10GB disk space** available

### API Keys (All Free Tier)
- [ ] **Google Search Console** - OAuth credentials or service account
- [ ] **Google Analytics 4** - API credentials
- [ ] **ValueSERP** or **SerpAPI** - API key for SERP tracking
- [ ] **GitHub Token** - Personal access token for PR automation (optional)
- [ ] **Slack Webhook URL** - For notifications (optional)
- [ ] **SMTP Credentials** - For email notifications (optional)

### DNS & Networking
- [ ] **Domain verified** in Google Search Console
- [ ] **Firewall rules** configured for PostgreSQL (5432), Redis (6379), Grafana (3000)
- [ ] **SSL certificates** ready (if exposing externally)

---

## Phase 1: Database Setup

### Step 1: Create Database
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE seo_warehouse;

# Create user (if not using postgres)
CREATE USER seo_admin WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE seo_warehouse TO seo_admin;

# Exit psql
\q
```

### Step 2: Enable Extensions
```bash
# Connect to new database
psql -U postgres -d seo_warehouse

# Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

# Verify extensions
\dx
```

**Verification Checklist:**
- [ ] Database `seo_warehouse` created
- [ ] Extension `vector` enabled
- [ ] Extension `pg_trgm` enabled
- [ ] Extension `uuid-ossp` enabled

### Step 3: Run SQL Schemas
```bash
# Navigate to project directory
cd site-data-warehouse

# Run all schemas in order
psql -U postgres -d seo_warehouse -f sql/00_extensions.sql
psql -U postgres -d seo_warehouse -f sql/01_base_schema.sql
psql -U postgres -d seo_warehouse -f sql/02_gsc_schema.sql
psql -U postgres -d seo_warehouse -f sql/03_ga4_schema.sql
psql -U postgres -d seo_warehouse -f sql/04_session_stitching.sql
psql -U postgres -d seo_warehouse -f sql/05_unified_view.sql
psql -U postgres -d seo_warehouse -f sql/12_actions_schema.sql
psql -U postgres -d seo_warehouse -f sql/13_content_schema.sql
psql -U postgres -d seo_warehouse -f sql/14_forecasts_schema.sql
psql -U postgres -d seo_warehouse -f sql/16_serp_schema.sql
psql -U postgres -d seo_warehouse -f sql/17_performance_schema.sql
psql -U postgres -d seo_warehouse -f sql/18_analytics_schema.sql
psql -U postgres -d seo_warehouse -f sql/20_notifications_schema.sql
psql -U postgres -d seo_warehouse -f sql/21_orchestration_schema.sql
psql -U postgres -d seo_warehouse -f sql/22_anomaly_schema.sql
```

**Verification:**
```sql
-- Check table count (should be 44+)
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema');

-- Verify key tables exist
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname IN ('gsc', 'ga4', 'serp', 'notifications', 'orchestration', 'anomaly')
ORDER BY schemaname, tablename;
```

**Verification Checklist:**
- [ ] All 15 SQL files executed without errors
- [ ] 44+ tables created
- [ ] All schemas exist: gsc, ga4, serp, performance, notifications, orchestration, anomaly

---

## Phase 2: Python Environment

### Step 1: Create Virtual Environment
```bash
# Create venv
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Verify installations
pip list | grep -E "(langchain|prophet|celery|asyncpg|playwright)"
```

**Verification Checklist:**
- [ ] Virtual environment created and activated
- [ ] All requirements installed without errors
- [ ] LangChain, Prophet, Celery, asyncpg installed
- [ ] Playwright browsers installed

### Step 3: Install Playwright Browsers
```bash
# Install browser binaries
playwright install chromium

# Verify installation
playwright install --help
```

---

## Phase 3: Configuration

### Step 1: Create Environment File
```bash
# Copy example
cp .env.example .env

# Edit with your settings
nano .env
```

### Step 2: Configure Environment Variables

**Required Variables:**
```bash
# Database
WAREHOUSE_DSN=postgresql://seo_admin:your-password@localhost:5432/seo_warehouse

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Google Search Console
GSC_PROPERTY_URL=https://yourdomain.com
GSC_CREDENTIALS_PATH=/path/to/gsc_credentials.json

# Google Analytics 4
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_PATH=/path/to/ga4_credentials.json

# SERP Tracking
SERP_API_PROVIDER=valueserp
VALUESERP_API_KEY=your-valueserp-key
# OR
# SERPAPI_KEY=your-serpapi-key
```

**Optional Variables:**
```bash
# Notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password

# GitHub Automation
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_REPO=yourusername/your-repo

# Ollama (Local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

**Verification Checklist:**
- [ ] `.env` file created
- [ ] Database DSN configured and tested
- [ ] Redis connection configured
- [ ] GSC credentials file exists and path is correct
- [ ] GA4 credentials file exists and path is correct
- [ ] SERP API key configured
- [ ] Notification channels configured (at least one)

### Step 3: Test Database Connection
```python
# test_connection.py
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    try:
        conn = await asyncpg.connect(os.getenv('WAREHOUSE_DSN'))
        version = await conn.fetchval('SELECT version()')
        print(f"✓ Connected to PostgreSQL: {version}")

        # Test vector extension
        result = await conn.fetchval("SELECT vector_dims('[1,2,3]'::vector)")
        print(f"✓ pgvector working: dimension test = {result}")

        await conn.close()
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())
```

```bash
# Run test
python test_connection.py
```

---

## Phase 4: Services Setup

### Step 1: Start Redis
```bash
# Using Docker
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

# Or using system service
sudo systemctl start redis
sudo systemctl enable redis

# Verify
redis-cli ping
# Should return: PONG
```

**Verification Checklist:**
- [ ] Redis running on port 6379
- [ ] `redis-cli ping` returns PONG

### Step 2: Start Celery Workers
```bash
# Terminal 1: Start worker
celery -A services.tasks worker --loglevel=info --concurrency=4

# Terminal 2: Start beat scheduler
celery -A services.tasks beat --loglevel=info

# Verify workers are running
celery -A services.tasks inspect active
```

**Verification Checklist:**
- [ ] Celery worker started with 4 concurrent processes
- [ ] Celery beat scheduler started
- [ ] No error messages in worker logs
- [ ] `celery inspect active` returns worker info

### Step 3: Start Ollama (Local LLM)
```bash
# Install Ollama (if not already)
curl https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama2

# Start service
ollama serve &

# Verify
curl http://localhost:11434/api/tags
```

**Verification Checklist:**
- [ ] Ollama service running on port 11434
- [ ] Model downloaded (llama2 or your choice)
- [ ] API responding to requests

### Step 4: Start Grafana
```bash
# Using Docker Compose
docker-compose up -d grafana

# Verify
curl http://localhost:3000
```

**Default credentials:**
- Username: `admin`
- Password: `admin` (change on first login)

**Verification Checklist:**
- [ ] Grafana accessible at http://localhost:3000
- [ ] Login successful
- [ ] Changed default password
- [ ] PostgreSQL datasource configured
- [ ] 5 dashboards provisioned

---

## Phase 5: Initial Data Setup

### Step 1: Register Properties
```python
# register_properties.py
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def register_property():
    conn = await asyncpg.connect(os.getenv('WAREHOUSE_DSN'))

    # Register your property
    property_url = "https://yourdomain.com"

    await conn.execute("""
        INSERT INTO base.properties (property_url, display_name, is_active)
        VALUES ($1, $2, true)
        ON CONFLICT (property_url) DO NOTHING
    """, property_url, "Your Site Name")

    print(f"✓ Property registered: {property_url}")
    await conn.close()

asyncio.run(register_property())
```

### Step 2: Add SERP Queries
```python
# add_serp_queries.py
import asyncio
import asyncpg
import os

async def add_queries():
    conn = await asyncpg.connect(os.getenv('WAREHOUSE_DSN'))

    queries = [
        ("your primary keyword", "/target-page-path"),
        ("your brand name", "/"),
        ("your product category", "/products"),
    ]

    property_url = "https://yourdomain.com"

    for query_text, target_path in queries:
        await conn.execute("""
            INSERT INTO serp.queries (query_text, property, target_page_path, is_active)
            VALUES ($1, $2, $3, true)
            ON CONFLICT DO NOTHING
        """, query_text, property_url, target_path)
        print(f"✓ Added query: {query_text}")

    await conn.close()

asyncio.run(add_queries())
```

### Step 3: Create Alert Rules
```python
# create_alerts.py
import asyncio
from notifications.alert_manager import AlertManager
from notifications.channels.slack_notifier import SlackNotifier

async def setup_alerts():
    manager = AlertManager()
    manager.register_notifier('slack', SlackNotifier())

    # SERP position drop alert
    await manager.create_alert_rule(
        rule_name="SERP Position Drop Alert",
        rule_type="serp_drop",
        conditions={"position_drop": 3},
        severity="high",
        channels=["slack"],
        property="https://yourdomain.com"
    )

    # Core Web Vitals alert
    await manager.create_alert_rule(
        rule_name="Poor CWV Alert",
        rule_type="cwv_poor",
        conditions={"lcp_threshold": 2500, "cls_threshold": 0.1},
        severity="medium",
        channels=["slack"],
        property="https://yourdomain.com"
    )

    print("✓ Alert rules created")

asyncio.run(setup_alerts())
```

**Verification Checklist:**
- [ ] Properties registered in database
- [ ] SERP queries added
- [ ] Alert rules created
- [ ] Verified in database: `SELECT * FROM notifications.alert_rules`

---

## Phase 6: Verification & Testing

### Step 1: Test Data Collection
```bash
# Manually trigger GSC collection
celery -A services.tasks call collect_gsc_data --args='["https://yourdomain.com"]'

# Manually trigger SERP tracking
celery -A services.tasks call track_serp_positions --args='["https://yourdomain.com"]'

# Check logs for success
```

### Step 2: Verify Database Data
```sql
-- Check GSC data
SELECT COUNT(*) FROM gsc.query_stats;

-- Check SERP data
SELECT * FROM serp.position_history ORDER BY checked_at DESC LIMIT 10;

-- Check alerts
SELECT * FROM notifications.alert_history ORDER BY triggered_at DESC LIMIT 10;
```

### Step 3: Test Grafana Dashboards
- [ ] Open http://localhost:3000
- [ ] Navigate to Dashboards → Browse
- [ ] Verify 5 dashboards exist:
  - [ ] SERP Position Tracking
  - [ ] Core Web Vitals Monitoring
  - [ ] GA4 Overview
  - [ ] GSC Overview
  - [ ] Hybrid Overview
- [ ] Select your property in filters
- [ ] Verify data appears in panels

### Step 4: Test Notifications
```python
# test_notifications.py
import asyncio
from notifications.alert_manager import AlertManager
from notifications.channels.slack_notifier import SlackNotifier

async def test():
    manager = AlertManager()
    manager.register_notifier('slack', SlackNotifier())

    # Trigger test alert
    alert_id = await manager.trigger_alert(
        rule_id="your-rule-id",  # Get from DB
        property="https://yourdomain.com",
        title="Test Alert",
        message="This is a test alert to verify notifications are working",
        metadata={"test": True}
    )

    print(f"✓ Alert triggered: {alert_id}")

    # Process queue
    await manager.process_notification_queue()
    print("✓ Notification sent")

asyncio.run(test())
```

### Step 5: Test Multi-Agent System
```python
# test_agents.py
import asyncio
from agents.orchestration.supervisor_agent import SupervisorAgent
from agents.orchestration.serp_analyst_agent import SerpAnalystAgent
from agents.orchestration.performance_agent import PerformanceAgent

async def test():
    supervisor = SupervisorAgent()
    supervisor.register_agent('serp_analyst', SerpAnalystAgent())
    supervisor.register_agent('performance_agent', PerformanceAgent())

    result = await supervisor.run_workflow(
        workflow_type='daily_analysis',
        trigger_event={'source': 'manual_test'},
        property='https://yourdomain.com'
    )

    print("✓ Workflow completed")
    print(f"Recommendations: {len(result['recommendations'])}")
    for rec in result['recommendations'][:3]:
        print(f"  - {rec['type']}: {rec['action']}")

asyncio.run(test())
```

**Verification Checklist:**
- [ ] Manual data collection tasks complete successfully
- [ ] Data visible in database
- [ ] Grafana dashboards showing data
- [ ] Test notification received (Slack/Email)
- [ ] Multi-agent workflow completes without errors

---

## Phase 7: Production Hardening

### Step 1: Security
- [ ] Change all default passwords (PostgreSQL, Grafana, Redis)
- [ ] Enable PostgreSQL SSL connections
- [ ] Configure Redis password authentication
- [ ] Use secrets manager for API keys (not .env in production)
- [ ] Enable firewall rules (allow only necessary ports)
- [ ] Set up fail2ban for SSH protection

### Step 2: Monitoring
- [ ] Set up PostgreSQL monitoring (pg_stat_statements)
- [ ] Configure Redis monitoring
- [ ] Set up log aggregation (consider ELK stack or Loki)
- [ ] Create uptime monitoring for all services
- [ ] Configure disk space alerts
- [ ] Set up backup monitoring

### Step 3: Backups
```bash
# Database backup script
#!/bin/bash
BACKUP_DIR="/backups/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

pg_dump -U postgres seo_warehouse | gzip > "$BACKUP_DIR/seo_warehouse_$TIMESTAMP.sql.gz"

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

- [ ] Daily database backups configured
- [ ] Backup restoration tested
- [ ] Redis persistence enabled (RDB or AOF)
- [ ] Backup retention policy defined (30 days recommended)
- [ ] Offsite backup storage configured

### Step 4: Performance Optimization
```sql
-- Create indexes for common queries
CREATE INDEX CONCURRENTLY idx_gsc_query_stats_date
ON gsc.query_stats(data_date DESC);

CREATE INDEX CONCURRENTLY idx_serp_position_checked
ON serp.position_history(checked_at DESC);

CREATE INDEX CONCURRENTLY idx_notifications_triggered
ON notifications.alert_history(triggered_at DESC);

-- Analyze tables
ANALYZE gsc.query_stats;
ANALYZE serp.position_history;
ANALYZE notifications.alert_history;
```

- [ ] Database indexes created
- [ ] PostgreSQL autovacuum configured
- [ ] Celery worker concurrency optimized (based on CPU cores)
- [ ] Redis maxmemory policy set
- [ ] Connection pooling configured

### Step 5: Process Management
```bash
# Create systemd service for Celery worker
# /etc/systemd/system/celery-worker.service

[Unit]
Description=Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=seo_user
Group=seo_user
WorkingDirectory=/opt/seo-platform
Environment="PATH=/opt/seo-platform/venv/bin"
ExecStart=/opt/seo-platform/venv/bin/celery -A services.tasks worker \
  --loglevel=info --concurrency=4 --pidfile=/var/run/celery-worker.pid
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

- [ ] Systemd services created for Celery worker and beat
- [ ] Services set to auto-start on boot
- [ ] Log rotation configured
- [ ] Process monitoring configured (monit or supervisord)

---

## Phase 8: Documentation

### Step 1: Internal Documentation
- [ ] Document your specific alert rules
- [ ] Document custom SERP queries
- [ ] Document property URLs and credentials locations
- [ ] Create runbook for common operations
- [ ] Document backup restoration procedure

### Step 2: Team Training
- [ ] Train team on Grafana dashboard usage
- [ ] Document how to add new SERP queries
- [ ] Document how to create custom alert rules
- [ ] Create FAQ for common issues
- [ ] Document escalation procedures

---

## Phase 9: Go-Live

### Pre-Launch Checklist
- [ ] All services running and healthy
- [ ] Data collection working (GSC, GA4, SERP)
- [ ] Notifications tested and working
- [ ] Dashboards accessible and showing data
- [ ] Backups configured and tested
- [ ] Monitoring and alerting configured
- [ ] Team trained on system usage
- [ ] Runbook created for operations
- [ ] Emergency contacts documented

### Launch Day
1. [ ] Final backup of all systems
2. [ ] Enable all scheduled Celery tasks
3. [ ] Verify first scheduled run completes successfully
4. [ ] Monitor logs for 24 hours
5. [ ] Verify notifications are being sent
6. [ ] Check dashboard data freshness
7. [ ] Document any issues encountered

### Post-Launch (First Week)
- [ ] Daily review of error logs
- [ ] Verify all scheduled tasks running
- [ ] Confirm notifications received for real issues
- [ ] Check disk space trends
- [ ] Review agent recommendations quality
- [ ] Gather team feedback
- [ ] Document lessons learned

---

## Troubleshooting

### Common Issues

**Database Connection Errors:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection from command line
psql -U postgres -d seo_warehouse -c "SELECT 1"

# Check firewall
sudo ufw status
```

**Celery Tasks Not Running:**
```bash
# Check worker is running
celery -A services.tasks inspect active

# Check beat scheduler
celery -A services.tasks inspect scheduled

# Restart services
pkill -f "celery worker"
celery -A services.tasks worker --loglevel=info --concurrency=4 &
```

**No Data in Grafana:**
```bash
# Check data exists in database
psql -U postgres -d seo_warehouse -c "SELECT COUNT(*) FROM gsc.query_stats"

# Check Grafana datasource
# Grafana UI → Configuration → Data sources → PostgreSQL → Test
```

**API Rate Limits:**
- GSC: 1,200 queries/minute - reduce collection frequency if hitting limits
- GA4: 10 queries/second - add delays between requests
- ValueSERP: Varies by plan - monitor usage in dashboard

### Support Resources
- Full documentation: [docs/](docs/)
- Troubleshooting guide: [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- GitHub issues: [Report issues](https://github.com/yourusername/site-data-warehouse/issues)

---

## Success Criteria

Your deployment is successful when:
- ✅ All services running without errors for 24 hours
- ✅ Data collecting automatically on schedule
- ✅ Grafana dashboards showing current data
- ✅ Notifications received for test alerts
- ✅ Multi-agent workflows completing successfully
- ✅ Backups running and verified
- ✅ Team trained and using the platform
- ✅ Zero monthly infrastructure costs

---

**Next Steps:**
- Review [docs/QUICKSTART.md](QUICKSTART.md) for feature tutorials
- Explore [docs/guides/DASHBOARD_GUIDE.md](../guides/DASHBOARD_GUIDE.md) for dashboard usage
- Read [docs/guides/MULTI_AGENT_SYSTEM.md](../guides/MULTI_AGENT_SYSTEM.md) for AI agent workflows
