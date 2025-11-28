# GA4 Integration Implementation Plan
**Project**: Enable GA4 Data Collection for Hybrid Insight Engine
**Status**: Not Started
**Priority**: Critical (Core Functionality Missing)
**Estimated Duration**: 2-3 hours implementation + 24-48 hours data accumulation
**Risk Level**: Medium (requires database changes, service deployment)
**Created**: 2025-11-21
**Last Updated**: 2025-11-21

---

## Executive Summary

### Problem Statement
The Hybrid Insight Engine is currently running **GSC-only**, missing 50% of its advertised functionality. GA4 data collection was designed as a core component but was never activated during initial deployment.

### Business Impact
- ❌ No user behavior metrics (sessions, engagement, conversions)
- ❌ No unified GSC+GA4 correlation insights
- ❌ Limited insight detection (anomaly detector can't find conversion drops)
- ❌ Dashboard shows incomplete picture
- ❌ Cannot deliver on "Hybrid Insight Engine" value proposition

### Solution Overview
Systematically enable GA4 collection through 6 phases with validation at each step. Total implementation time: 2-3 hours + 24-48 hours for data accumulation.

---

## Current State Assessment

### ✅ What's Already Built

#### 1. Code & Configuration
- **GA4 Extractor**: `ingestors/ga4/ga4_extractor.py` (Complete)
- **GA4 Client**: `ingestors/ga4/ga4_client.py` (Complete)
- **Configuration**: `ingestors/ga4/config.yaml` (Configured for Property ID: 475105521)
- **Dockerfile**: `compose/dockerfiles/Dockerfile.ga4_ingestor` (Ready)
- **Docker Service**: Defined in `docker-compose.yml` (Requires `--profile core`)

#### 2. SQL Schema
- **GA4 Table Schema**: `sql/04_ga4_schema.sql` (Ready to apply)
  - Creates `gsc.fact_ga4_daily` table
  - 14 columns: sessions, conversions, engagement_rate, bounce_rate, etc.
  - Indexes for performance optimization

- **Unified View**: `sql/05_unified_view.sql` (Ready to apply)
  - Joins GSC + GA4 via FULL OUTER JOIN
  - 26 time-series fields (WoW, MoM calculations)
  - Enables hybrid insights

- **Materialized Views**: `sql/06_materialized_views.sql` (Optional performance optimization)

#### 3. Environment Configuration
```bash
GA4_PROPERTY_ID=475105521
GA4_CREDENTIALS_FILE=secrets/gsc_sa.json
```

### ❌ What's Missing

| Component | Status | Impact |
|-----------|--------|--------|
| GA4 Database Schema | Not Applied | Cannot store GA4 data |
| GA4 Ingestor Container | Not Running | No data collection |
| Scheduler Integration | Not Configured | No automated daily runs |
| Watermark Tracking | Not Initialized | Cannot track last collection |
| Grafana Dashboard | No GA4 Panels | Users can't see GA4 metrics |

### Data Status
- **GSC Data**: 1,258,945 rows (2024-07-28 to 2025-11-17) ✅
- **GA4 Data**: 0 rows (never collected) ❌
- **Unified View**: Not created (requires both datasets)

---

## Implementation Phases

### Phase 1: Database Schema Setup
**Duration**: 15 minutes
**Risk**: Low
**Reversibility**: Full rollback available

#### Objectives
- Create GA4 fact table to store analytics data
- Create unified view to join GSC + GA4
- Enable time-series calculations

#### Prerequisites
- PostgreSQL container running and healthy
- Database backup completed (recommended)
- No active GA4 collection processes

#### Tasks

**Task 1.1: Apply GA4 Schema**
```bash
docker exec -i gsc_warehouse psql -U gsc_user -d gsc_db < sql/04_ga4_schema.sql
```

**Expected Output:**
```
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE TRIGGER
GRANT
```

**Task 1.2: Verify Table Creation**
```sql
-- Check table exists
\dt gsc.fact_ga4_daily

-- Check structure
\d gsc.fact_ga4_daily

-- Expected columns:
-- date, property, page_path, sessions, engaged_sessions,
-- engagement_rate, bounce_rate, conversions, conversion_rate,
-- avg_session_duration, page_views, avg_time_on_page,
-- exits, exit_rate, created_at, updated_at
```

**Task 1.3: Apply Unified View**
```bash
docker exec -i gsc_warehouse psql -U gsc_user -d gsc_db < sql/05_unified_view.sql
```

**Expected Output:**
```
DROP VIEW
CREATE VIEW
```

**Task 1.4: Test Unified View**
```sql
-- Should return structure (no data yet)
SELECT * FROM gsc.vw_unified_page_performance LIMIT 1;

-- Check column count (should be ~40 columns)
SELECT COUNT(*) FROM information_schema.columns
WHERE table_name = 'vw_unified_page_performance';
```

#### Validation Checklist
- [ ] `gsc.fact_ga4_daily` table exists
- [ ] Table has PRIMARY KEY on (date, property, page_path)
- [ ] All 6 indexes created successfully
- [ ] `vw_unified_page_performance` view created
- [ ] View has both GSC and GA4 fields
- [ ] No errors in PostgreSQL logs

#### Rollback Procedure
```sql
-- If anything goes wrong:
DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;
DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;

-- Check logs for specific error:
docker logs gsc_warehouse --tail 50
```

---

### Phase 2: Verify GA4 API Access
**Duration**: 10 minutes
**Risk**: Medium (most common blocker)
**Reversibility**: N/A (read-only validation)

#### Objectives
- Confirm service account credentials are valid
- Verify GA4 API permissions are correct
- Test connectivity to GA4 property

#### Prerequisites
- `secrets/gsc_sa.json` exists and is valid JSON
- Service account has been granted access to GA4 property 475105521
- Analytics Data API enabled in GCP project

#### Tasks

**Task 2.1: Verify Credentials File**
```bash
# Check file exists and is valid JSON
cat secrets/gsc_sa.json | python -m json.tool > /dev/null && echo "Valid JSON" || echo "Invalid JSON"

# Check for required fields
cat secrets/gsc_sa.json | grep -E '(type|project_id|private_key_id|client_email)' | wc -l
# Should output: 4 or more
```

**Task 2.2: Check Service Account Email**
```bash
# Extract service account email
cat secrets/gsc_sa.json | grep "client_email" | cut -d'"' -f4
```

**Task 2.3: Verify GA4 Property Access**
Go to Google Analytics Admin Console:
1. Navigate to: https://analytics.google.com/
2. Select Property: `475105521`
3. Go to **Admin** → **Property Access Management**
4. Verify service account email from Task 2.2 is listed with "Viewer" or "Analyst" role

**Task 2.4: Test API Connection (Manual)**
```bash
# Install test dependencies
pip install google-analytics-data

# Test connection
python3 << 'EOF'
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
import os

try:
    # Initialize client
    client = BetaAnalyticsDataClient.from_service_account_json('secrets/gsc_sa.json')

    # Test query (1 day of data)
    request = RunReportRequest(
        property=f"properties/475105521",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="sessions")],
        date_ranges=[DateRange(start_date="2025-11-20", end_date="2025-11-20")],
    )

    response = client.run_report(request)
    print(f"✅ GA4 API Connection Successful!")
    print(f"   Rows returned: {len(response.rows)}")

except Exception as e:
    print(f"❌ GA4 API Connection Failed: {e}")
    print(f"\nTroubleshooting:")
    print(f"1. Check service account has 'Viewer' role on GA4 property 475105521")
    print(f"2. Verify Analytics Data API is enabled in GCP Console")
    print(f"3. Confirm credentials file is correct")
EOF
```

#### Validation Checklist
- [ ] `secrets/gsc_sa.json` is valid JSON
- [ ] Service account email identified
- [ ] Service account has access to GA4 property 475105521
- [ ] API connection test successful
- [ ] At least 1 row of data returned from test query

#### Common Issues & Fixes

**Issue 1: "Permission denied" or "Forbidden"**
```
Solution:
1. Go to GA4 Admin → Property Access Management
2. Add service account email with "Viewer" role
3. Wait 5 minutes for permissions to propagate
4. Re-run test
```

**Issue 2: "API not enabled"**
```
Solution:
1. Go to: https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com
2. Select correct GCP project
3. Click "Enable"
4. Wait 2 minutes
5. Re-run test
```

**Issue 3: "Property not found"**
```
Solution:
1. Verify property ID is correct: 475105521
2. Check property is not deleted or archived
3. Confirm service account has access to correct GA4 account
```

---

### Phase 3: Deploy GA4 Ingestor Service
**Duration**: 20 minutes
**Risk**: Low
**Reversibility**: Full (can stop container)

#### Objectives
- Build GA4 ingestor Docker image
- Start container in docker-compose stack
- Verify connectivity to database and GA4 API

#### Prerequisites
- Phase 1 completed (database schema ready)
- Phase 2 completed (API access verified)
- Docker daemon running
- No port conflicts

#### Tasks

**Task 3.1: Build GA4 Ingestor Image**
```bash
# Build the image
docker-compose build ga4_ingestor

# Verify image created
docker images | grep ga4_ingestor
```

**Expected Output:**
```
gsc-data-warehouse_ga4_ingestor   latest   abc123def456   2 minutes ago   XXX MB
```

**Task 3.2: Start GA4 Ingestor Service**
```bash
# Start with core profile
docker-compose --profile core up -d ga4_ingestor

# Verify container started
docker-compose ps | grep ga4
```

**Expected Output:**
```
gsc_ga4_ingestor   running   Up X seconds
```

**Task 3.3: Check Container Logs**
```bash
# View startup logs
docker logs gsc_ga4_ingestor --tail 50

# Follow logs for errors
docker logs gsc_ga4_ingestor -f
```

**Expected Log Output:**
```
INFO - GA4 Extractor initialized
INFO - Configuration loaded from /app/ingestors/ga4/config.yaml
INFO - Property: https://aspose.net/ (GA4 ID: 475105521)
INFO - Waiting for trigger...
```

**Task 3.4: Verify Database Connectivity**
```bash
docker exec gsc_ga4_ingestor python3 -c "
import psycopg2
import os

dsn = os.environ.get('WAREHOUSE_DSN')
print(f'Testing connection to: {dsn}')

try:
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        cur.execute('SELECT version();')
        version = cur.fetchone()
        print(f'✅ Database connection successful')
        print(f'   PostgreSQL version: {version[0][:50]}...')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
```

**Task 3.5: Verify GA4 API Connectivity from Container**
```bash
docker exec gsc_ga4_ingestor python3 -c "
from google.analytics.data_v1beta import BetaAnalyticsDataClient
import os

creds_file = os.environ.get('GA4_CREDENTIALS_FILE', '/secrets/ga4_sa.json')
property_id = os.environ.get('GA4_PROPERTY_ID')

print(f'Credentials file: {creds_file}')
print(f'Property ID: {property_id}')

try:
    client = BetaAnalyticsDataClient.from_service_account_json(creds_file)
    print(f'✅ GA4 API client initialized successfully')
except Exception as e:
    print(f'❌ GA4 API initialization failed: {e}')
"
```

#### Validation Checklist
- [ ] Docker image built successfully
- [ ] Container status: Running
- [ ] No error messages in logs
- [ ] Database connection successful
- [ ] GA4 API credentials loaded
- [ ] Container can reach warehouse on network
- [ ] Environment variables set correctly

#### Troubleshooting

**Container won't start:**
```bash
# Check detailed logs
docker logs gsc_ga4_ingestor

# Check if port is already in use
docker ps -a | grep ga4

# Restart container
docker-compose restart ga4_ingestor
```

**Network connectivity issues:**
```bash
# Verify container is on gsc_network
docker inspect gsc_ga4_ingestor | grep NetworkMode

# Test ping to warehouse
docker exec gsc_ga4_ingestor ping -c 3 warehouse

# Check DNS resolution
docker exec gsc_ga4_ingestor nslookup warehouse
```

**Credentials not found:**
```bash
# Check volume mount
docker inspect gsc_ga4_ingestor | grep -A 10 Mounts

# Verify file exists in container
docker exec gsc_ga4_ingestor ls -la /secrets/

# Check file permissions
docker exec gsc_ga4_ingestor cat /secrets/gsc_sa.json | head -5
```

---

### Phase 4: Initial Data Collection
**Duration**: 30 minutes + 24h for backfill
**Risk**: Medium
**Reversibility**: Can truncate table and restart

#### Objectives
- Execute first GA4 data extraction
- Load 7 days of historical data
- Verify data quality and completeness
- Update watermark tracking

#### Prerequisites
- Phase 3 completed (container running)
- GA4 API access confirmed
- Database schema ready
- Network connectivity verified

#### Tasks

**Task 4.1: Dry Run (Test Mode)**
```bash
# Test extraction without writing to database
docker exec gsc_ga4_ingestor python /app/ingestors/ga4/ga4_extractor.py \
  --start-date 2025-11-14 \
  --end-date 2025-11-20 \
  --dry-run

# Expected output:
# INFO - Fetching GA4 data for 2025-11-14 to 2025-11-20
# INFO - Would fetch X rows for property https://aspose.net/
# INFO - Dry run complete (no data written)
```

**Task 4.2: Extract 7-Day Historical Data**
```bash
# Actual extraction (7 days of data)
docker exec gsc_ga4_ingestor python /app/ingestors/ga4/ga4_extractor.py \
  --start-date 2025-11-14 \
  --end-date 2025-11-20

# Monitor logs
docker logs gsc_ga4_ingestor -f
```

**Expected Log Output:**
```
INFO - Starting GA4 extraction
INFO - Property: https://aspose.net/ (475105521)
INFO - Date range: 2025-11-14 to 2025-11-20 (7 days)
INFO - Fetching data from GA4 API...
INFO - API call successful: 156 rows returned
INFO - Batch 1: Inserting 156 rows...
INFO - Batch 1: Complete (156 rows inserted)
INFO - Extraction complete:
  - Rows fetched: 156
  - Rows inserted: 156
  - Rows updated: 0
  - Rows failed: 0
  - Duration: 12.3s
```

**Task 4.3: Verify Data Loaded**
```sql
-- Check row count
SELECT COUNT(*) as total_rows
FROM gsc.fact_ga4_daily;

-- Check date range
SELECT
  MIN(date) as earliest_date,
  MAX(date) as latest_date,
  COUNT(DISTINCT date) as unique_days
FROM gsc.fact_ga4_daily;

-- Check metrics summary
SELECT
  COUNT(*) as total_rows,
  SUM(sessions) as total_sessions,
  SUM(conversions) as total_conversions,
  ROUND(AVG(engagement_rate)::numeric, 4) as avg_engagement,
  ROUND(AVG(bounce_rate)::numeric, 4) as avg_bounce
FROM gsc.fact_ga4_daily;
```

**Expected Results:**
```
total_rows: 100-500 (depends on site traffic)
earliest_date: 2025-11-14
latest_date: 2025-11-20
unique_days: 7
total_sessions: > 0
avg_engagement: 0.3-0.8
avg_bounce: 0.2-0.7
```

**Task 4.4: Data Quality Validation**
```sql
-- Check for nulls in critical fields
SELECT
  COUNT(*) FILTER (WHERE sessions IS NULL) as null_sessions,
  COUNT(*) FILTER (WHERE page_path IS NULL) as null_pages,
  COUNT(*) FILTER (WHERE date IS NULL) as null_dates,
  COUNT(*) FILTER (WHERE property IS NULL) as null_property
FROM gsc.fact_ga4_daily;

-- All should be 0

-- Check for duplicates
SELECT date, property, page_path, COUNT(*) as dup_count
FROM gsc.fact_ga4_daily
GROUP BY date, property, page_path
HAVING COUNT(*) > 1;

-- Should return 0 rows

-- Validate metric ranges
SELECT
  MIN(sessions) as min_sessions,
  MAX(sessions) as max_sessions,
  MIN(bounce_rate) as min_bounce,
  MAX(bounce_rate) as max_bounce,
  MIN(engagement_rate) as min_engagement,
  MAX(engagement_rate) as max_engagement
FROM gsc.fact_ga4_daily;

-- Bounce and engagement should be between 0 and 1
-- Sessions should be >= 0
```

**Task 4.5: Test Unified View**
```sql
-- Check unified view with both GSC and GA4 data
SELECT
  COUNT(*) as total_rows,
  SUM(CASE WHEN gsc_clicks > 0 THEN 1 ELSE 0 END) as rows_with_gsc,
  SUM(CASE WHEN ga_sessions > 0 THEN 1 ELSE 0 END) as rows_with_ga4,
  SUM(CASE WHEN gsc_clicks > 0 AND ga_sessions > 0 THEN 1 ELSE 0 END) as rows_with_both
FROM gsc.vw_unified_page_performance
WHERE date >= '2025-11-14' AND date <= '2025-11-20';

-- Expected:
-- rows_with_gsc: Should be high (most GSC data available)
-- rows_with_ga4: Should be > 0
-- rows_with_both: Ideally > 0 (indicates page matching works)
```

**Task 4.6: Update Watermark**
```sql
-- Insert or update watermark for GA4
INSERT INTO gsc.ingest_watermarks (property, source_type, last_date, updated_at)
VALUES ('https://aspose.net/', 'ga4', '2025-11-20', NOW())
ON CONFLICT (property, source_type)
DO UPDATE SET
  last_date = EXCLUDED.last_date,
  updated_at = NOW();

-- Verify watermark
SELECT * FROM gsc.ingest_watermarks WHERE source_type = 'ga4';
```

#### Validation Checklist
- [ ] Dry run completed without errors
- [ ] Data extraction successful
- [ ] Row count > 0
- [ ] Date range matches (2025-11-14 to 2025-11-20)
- [ ] 7 unique days of data
- [ ] Sessions > 0 and Conversions >= 0
- [ ] No null values in critical fields
- [ ] No duplicate records
- [ ] Metric ranges valid (bounce_rate 0-1, engagement_rate 0-1)
- [ ] Unified view shows matched data
- [ ] Watermark updated correctly

#### Data Quality Acceptance Criteria

| Metric | Expected Range | Action if Out of Range |
|--------|----------------|------------------------|
| Total Rows | 50-1000 | Investigate if <10 or >5000 |
| Null Sessions | 0 | CRITICAL: Fix immediately |
| Duplicate Records | 0 | CRITICAL: Fix immediately |
| Bounce Rate | 0.0-1.0 | Investigate if outside range |
| Engagement Rate | 0.0-1.0 | Investigate if outside range |
| Avg Sessions/Day | >0 | Warning if 0 |

---

### Phase 5: Scheduler Integration
**Duration**: 15 minutes
**Risk**: Low
**Reversibility**: Can remove job from scheduler

#### Objectives
- Add GA4 collection to automated daily scheduler
- Schedule to run after GSC collection
- Implement monitoring and error handling

#### Prerequisites
- Phase 4 completed successfully
- Scheduler container running
- GA4 extractor tested and working

#### Tasks

**Task 5.1: Review Current Scheduler Configuration**
```bash
# Check current scheduler jobs
docker exec gsc_scheduler cat /app/scheduler/scheduler.py | grep -A 5 "def run_"
```

**Task 5.2: Add GA4 Collection Function**

Edit `scheduler/scheduler.py` and add:

```python
def run_ga4_collection():
    """Run GA4 data collection"""
    logger.info("Starting scheduled GA4 collection")

    cmd = [
        'docker', 'exec', 'gsc_ga4_ingestor',
        'python', '/app/ingestors/ga4/ga4_extractor.py',
        '--incremental'  # Only collect since last watermark
    ]

    return run_command(cmd, 'ga4_collection')
```

**Task 5.3: Schedule GA4 Job**

Add to scheduler initialization:

```python
# GA4 Collection - Daily at 3:00 AM (after GSC at 2:00 AM)
scheduler.add_job(
    run_ga4_collection,
    trigger=CronTrigger(hour=3, minute=0),
    id='ga4_daily_collection',
    name='GA4 Daily Collection',
    replace_existing=True
)
```

**Task 5.4: Test Scheduler Job Manually**
```bash
# Test the function directly
docker exec gsc_scheduler python -c "
import sys
sys.path.insert(0, '/app')
from scheduler.scheduler import run_ga4_collection
result = run_ga4_collection()
print(f'Test result: {result}')
"
```

**Task 5.5: Restart Scheduler**
```bash
# Restart with new configuration
docker-compose restart scheduler

# Check logs
docker logs scheduler --tail 50
```

**Expected Log Output:**
```
INFO - Scheduler initialized
INFO - Jobs scheduled:
  - gsc_daily_collection: Daily at 02:00
  - ga4_daily_collection: Daily at 03:00  # <- New job
  - weekly_reconciliation: Weekly at Sunday 04:00
INFO - Next GA4 run: 2025-11-22 03:00:00
```

**Task 5.6: Verify Job Registered**
```bash
# List all scheduled jobs
docker exec gsc_scheduler python -c "
import sys
sys.path.insert(0, '/app')
from scheduler.scheduler import scheduler
for job in scheduler.get_jobs():
    print(f'{job.id}: {job.next_run_time}')
"
```

#### Validation Checklist
- [ ] GA4 collection function added to scheduler.py
- [ ] Job scheduled for 3:00 AM daily
- [ ] Manual test run successful
- [ ] Scheduler restarted without errors
- [ ] GA4 job appears in job list
- [ ] Next run time scheduled correctly
- [ ] No scheduling conflicts

#### Monitoring Setup

**Task 5.7: Add Metrics Tracking**
```python
# In run_ga4_collection(), add metrics:
metrics['last_ga4_run'] = datetime.utcnow().isoformat()
metrics['ga4_runs_count'] = metrics.get('ga4_runs_count', 0) + 1
```

**Task 5.8: Setup Alerts (Optional)**
```bash
# Create simple health check script
cat > /app/scripts/check_ga4_health.sh << 'EOF'
#!/bin/bash
LAST_RUN=$(docker exec gsc_warehouse psql -U gsc_user -d gsc_db -t -c \
  "SELECT last_date FROM gsc.ingest_watermarks WHERE source_type='ga4';")

YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

if [[ "$LAST_RUN" < "$YESTERDAY" ]]; then
  echo "WARNING: GA4 data is stale (last run: $LAST_RUN)"
  exit 1
else
  echo "OK: GA4 data is current (last run: $LAST_RUN)"
  exit 0
fi
EOF

chmod +x /app/scripts/check_ga4_health.sh
```

---

### Phase 6: Dashboard Enhancement
**Duration**: 30 minutes
**Risk**: Low
**Reversibility**: Can revert dashboard JSON

#### Objectives
- Add GA4 metric panels to Grafana
- Create hybrid correlation visualizations
- Enable unified data insights

#### Prerequisites
- Phase 4 completed (GA4 data available)
- Grafana running and accessible
- Database datasource configured

#### Panel Designs

**Panel 1: GA4 KPIs (Top Row - Stat Panels)**

```json
{
  "id": 10,
  "title": "Total Sessions (Last 30 Days)",
  "type": "stat",
  "gridPos": {"h": 4, "w": 6, "x": 0, "y": 36},
  "targets": [{
    "datasource": {"type": "grafana-postgresql-datasource", "uid": "postgres-gsc"},
    "format": "table",
    "rawSql": "SELECT SUM(ga_sessions)::bigint as \"Total Sessions\" FROM gsc.vw_unified_page_performance WHERE date >= CURRENT_DATE - INTERVAL '30 days'",
    "refId": "A"
  }],
  "options": {
    "reduceOptions": {
      "values": false,
      "calcs": ["lastNotNull"]
    },
    "colorMode": "value",
    "graphMode": "area"
  },
  "fieldConfig": {
    "defaults": {
      "color": {"mode": "thresholds"},
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "blue", "value": null}
        ]
      }
    }
  }
}
```

Similar panels for:
- Total Conversions (Last 30 Days)
- Average Engagement Rate
- Average Bounce Rate

**Panel 2: Sessions Over Time (Time Series)**

```json
{
  "id": 11,
  "title": "Sessions Over Time",
  "type": "timeseries",
  "gridPos": {"h": 8, "w": 12, "x": 0, "y": 40},
  "targets": [{
    "datasource": {"type": "grafana-postgresql-datasource", "uid": "postgres-gsc"},
    "format": "time_series",
    "rawSql": "SELECT date AS time, SUM(ga_sessions) AS value FROM gsc.vw_unified_page_performance WHERE $__timeFilter(date) AND ga_sessions > 0 GROUP BY date ORDER BY date",
    "refId": "A"
  }],
  "fieldConfig": {
    "defaults": {
      "custom": {
        "drawStyle": "line",
        "lineInterpolation": "smooth",
        "fillOpacity": 10
      },
      "color": {"mode": "palette-classic"}
    }
  }
}
```

**Panel 3: Hybrid Correlation - Clicks vs Sessions (Scatter Plot)**

```sql
-- Query for scatter plot
SELECT
  page_path,
  SUM(gsc_clicks)::bigint as clicks,
  SUM(ga_sessions)::bigint as sessions
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
  AND gsc_clicks > 0
  AND ga_sessions > 0
GROUP BY page_path
ORDER BY clicks DESC
LIMIT 50;
```

**Panel 4: Top Converting Pages (Table)**

```sql
SELECT
  page_path,
  SUM(gsc_clicks)::bigint as clicks,
  SUM(ga_sessions)::bigint as sessions,
  SUM(ga_conversions)::bigint as conversions,
  ROUND((SUM(ga_conversions)::numeric / NULLIF(SUM(ga_sessions), 0)) * 100, 2) as conv_rate,
  ROUND(AVG(gsc_ctr)::numeric, 2) as avg_ctr,
  ROUND(AVG(gsc_position)::numeric, 1) as avg_position
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
  AND ga_sessions > 0
GROUP BY page_path
ORDER BY conversions DESC
LIMIT 20;
```

#### Implementation Tasks

**Task 6.1: Create New Dashboard (Option A - Recommended)**
```bash
# Create separate GA4 dashboard
cp grafana/provisioning/dashboards/gsc-overview.json \
   grafana/provisioning/dashboards/ga4-overview.json

# Edit ga4-overview.json:
# - Change uid to "ga4-overview"
# - Change title to "GA4 Analytics Overview"
# - Add GA4 panels from designs above
```

**Task 6.2: Update Existing Dashboard (Option B)**
```bash
# Add GA4 panels to existing dashboard
# Edit grafana/provisioning/dashboards/gsc-overview.json
# Add panels after existing ones (adjust gridPos y-coordinates)
```

**Task 6.3: Restart Grafana**
```bash
docker restart gsc_grafana

# Wait for startup
sleep 20

# Verify health
curl -u admin:admin http://localhost:3000/api/health
```

**Task 6.4: Test Dashboard**
```bash
# Open in browser
# http://localhost:3000/d/ga4-overview/ga4-analytics-overview

# Verify:
# - All panels load without errors
# - Data appears in panels
# - Time range selector works
# - Refresh button updates data
```

#### Validation Checklist
- [ ] New dashboard created or existing updated
- [ ] All GA4 panels added
- [ ] Panel queries execute without errors
- [ ] Data displays correctly
- [ ] Time range filters work
- [ ] Hybrid panels show correlation
- [ ] Grafana restarted successfully
- [ ] Dashboard accessible via URL

---

## Success Criteria

### Immediate Success (After Phase 4)
- ✅ GA4 data collection running successfully
- ✅ At least 7 days of historical data loaded (100+ rows)
- ✅ Unified view returns matched GSC+GA4 records
- ✅ No errors in container logs for 24 hours
- ✅ Watermark tracking operational
- ✅ Data quality checks pass

### Short-term Success (Week 1)
- ✅ Daily automated collection working (7/7 successful runs)
- ✅ 14+ days of GA4 data accumulated
- ✅ Grafana dashboard showing GA4 metrics with real data
- ✅ No duplicate records
- ✅ Metrics within expected ranges
- ✅ Zero data loss incidents

### Long-term Success (Month 1)
- ✅ 60+ days for meaningful trend analysis
- ✅ Hybrid insights being generated:
  - Correlated drops (GSC clicks + GA4 conversions both down)
  - Intent mismatch detection (high impressions, low conversions)
  - Conversion optimization opportunities
- ✅ Multi-agent system leveraging unified data
- ✅ Users actively utilizing hybrid dashboards
- ✅ Data quality maintained (>99.5% uptime)

---

## Risk Management

### Risk 1: API Rate Limits
**Likelihood**: Medium
**Impact**: Medium (collection delays)
**Mitigation**:
- GA4 API limit: 10 QPS (configured in config.yaml: `rate_limit_qps: 10`)
- Exponential backoff implemented in ga4_client.py
- Batch processing to minimize API calls
- Monitor for 429 errors in logs

**Detection**:
```bash
docker logs gsc_ga4_ingestor | grep "429\|rate limit\|quota"
```

**Recovery**:
- Automatic retry with backoff (built into extractor)
- If persistent, reduce `rate_limit_qps` in config.yaml
- Schedule collection during off-peak hours

---

### Risk 2: Service Account Permissions
**Likelihood**: High (most common deployment issue)
**Impact**: High (blocks all collection)
**Mitigation**:
- Test API access in Phase 2 before deployment
- Document exact permissions required
- Have GCP admin contact ready for emergency access grants

**Required Permissions**:
1. Service account must have "Viewer" or "Analyst" role on GA4 property
2. Analytics Data API must be enabled in GCP project
3. Service account JSON must be valid and not expired

**Detection**:
```bash
docker logs gsc_ga4_ingestor | grep -i "permission\|forbidden\|unauthorized"
```

**Recovery**:
1. Go to GA4 Admin → Property Access Management
2. Add service account with "Viewer" role
3. Wait 5 minutes for propagation
4. Restart ga4_ingestor container

---

### Risk 3: Data Quality Issues
**Likelihood**: Medium
**Impact**: Medium (affects insights accuracy)
**Mitigation**:
- Automated data quality checks after each collection
- Validation queries built into extractor
- Alert if metrics outside expected ranges
- Manual spot-checks for first week

**Quality Checks**:
```sql
-- Run after each collection
SELECT
  'Null Check' as check_type,
  CASE
    WHEN COUNT(*) FILTER (WHERE sessions IS NULL) = 0 THEN 'PASS'
    ELSE 'FAIL'
  END as status
FROM gsc.fact_ga4_daily
UNION ALL
SELECT
  'Duplicate Check',
  CASE
    WHEN COUNT(*) = COUNT(DISTINCT (date, property, page_path)) THEN 'PASS'
    ELSE 'FAIL'
  END
FROM gsc.fact_ga4_daily
UNION ALL
SELECT
  'Range Check',
  CASE
    WHEN MIN(bounce_rate) >= 0 AND MAX(bounce_rate) <= 1
     AND MIN(engagement_rate) >= 0 AND MAX(engagement_rate) <= 1
    THEN 'PASS'
    ELSE 'FAIL'
  END
FROM gsc.fact_ga4_daily;
```

**Recovery**:
- If data quality issues detected, truncate bad batch:
  ```sql
  DELETE FROM gsc.fact_ga4_daily WHERE created_at > NOW() - INTERVAL '1 hour';
  ```
- Fix extractor bug
- Re-run collection for affected dates

---

### Risk 4: Schema Conflicts
**Likelihood**: Low
**Impact**: High (breaks database)
**Mitigation**:
- Backup database before Phase 1
- Test schema on isolated database first (if possible)
- Have rollback SQL scripts ready
- Apply during maintenance window

**Rollback Procedure**:
```sql
-- Complete rollback
BEGIN;

DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;
DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;
DELETE FROM gsc.ingest_watermarks WHERE source_type = 'ga4';

-- Restore from backup if needed
-- pg_restore -U gsc_user -d gsc_db /path/to/backup.sql

COMMIT;
```

---

### Risk 5: Unified View Performance
**Likelihood**: Low
**Impact**: Medium (slow queries)
**Mitigation**:
- Monitor query execution time
- Create materialized view if performance degrades
- Add indexes on frequently filtered columns
- Implement query result caching

**Performance Monitoring**:
```sql
-- Check query execution time
EXPLAIN ANALYZE
SELECT * FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days';

-- If execution time > 5 seconds, create materialized view:
CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance AS
SELECT * FROM gsc.vw_unified_page_performance;

-- Refresh materialized view daily (add to scheduler)
REFRESH MATERIALIZED VIEW gsc.mv_unified_page_performance;
```

---

## Complete Rollback Plan

### Scenario 1: Rollback After Phase 1 (Database Only)
```bash
# Stop any ongoing processes
docker-compose stop ga4_ingestor

# Connect to database
docker exec -it gsc_warehouse psql -U gsc_user -d gsc_db

# Execute rollback
DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;
DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;

# Verify cleanup
\dt gsc.fact_ga4_daily
# Should return: Did not find any relation

# Exit
\q
```

---

### Scenario 2: Rollback After Phase 3 (Container + Database)
```bash
# Stop and remove GA4 container
docker-compose stop ga4_ingestor
docker-compose rm -f ga4_ingestor

# Remove database objects (same as Scenario 1)
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "
  DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;
  DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;
"

# System now in GSC-only mode
```

---

### Scenario 3: Rollback After Phase 4 (Bad Data Loaded)
```bash
# Truncate table (keeps schema)
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "
  TRUNCATE gsc.fact_ga4_daily;
  DELETE FROM gsc.ingest_watermarks WHERE source_type = 'ga4';
"

# Verify cleanup
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "
  SELECT COUNT(*) FROM gsc.fact_ga4_daily;
"
# Should return: 0

# Fix issue, then restart from Phase 4
```

---

### Scenario 4: Complete System Rollback
```bash
#!/bin/bash
# Complete rollback script

echo "Starting complete GA4 rollback..."

# 1. Stop GA4 services
echo "Stopping GA4 ingestor..."
docker-compose stop ga4_ingestor
docker-compose rm -f ga4_ingestor

# 2. Remove from scheduler
echo "Updating scheduler..."
# Edit scheduler.py to comment out GA4 job
docker-compose restart scheduler

# 3. Remove database objects
echo "Cleaning database..."
docker exec gsc_warehouse psql -U gsc_user -d gsc_db << 'EOF'
DROP TABLE IF EXISTS gsc.fact_ga4_daily CASCADE;
DROP VIEW IF EXISTS gsc.vw_unified_page_performance CASCADE;
DELETE FROM gsc.ingest_watermarks WHERE source_type = 'ga4';
EOF

# 4. Remove Grafana dashboard (optional)
echo "Removing GA4 dashboard..."
rm -f grafana/provisioning/dashboards/ga4-overview.json
docker restart gsc_grafana

# 5. Verify rollback
echo "Verifying rollback..."
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "
  SELECT
    CASE WHEN NOT EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
    ) THEN '✅ Rollback successful'
    ELSE '❌ Rollback failed - table still exists'
    END as status;
"

echo "Rollback complete. System reverted to GSC-only mode."
```

---

## Implementation Checklist

### Pre-Implementation Checklist
- [ ] **Backup Database**
  ```bash
  docker exec gsc_warehouse pg_dump -U gsc_user -d gsc_db -F c -f /tmp/backup_$(date +%Y%m%d).dump
  docker cp gsc_warehouse:/tmp/backup_$(date +%Y%m%d).dump ./backups/
  ```
- [ ] **Document Current System State**
  - GSC data row count: ___________
  - Latest GSC data date: ___________
  - Disk space available: ___________
- [ ] **Verify Prerequisites**
  - [ ] Service account credentials exist (`secrets/gsc_sa.json`)
  - [ ] Docker has at least 10GB free space
  - [ ] PostgreSQL container healthy
  - [ ] Network connectivity confirmed
- [ ] **Review GA4 API Quotas**
  - [ ] Check current usage in GCP Console
  - [ ] Verify 10 QPS limit not exceeded
- [ ] **Schedule Maintenance Window** (Optional)
  - [ ] Date: ___________
  - [ ] Time: ___________
  - [ ] Duration: 3 hours

---

### Phase 1: Database Schema
- [ ] Apply 04_ga4_schema.sql
- [ ] Verify `gsc.fact_ga4_daily` table exists
- [ ] Confirm all 6 indexes created
- [ ] Apply 05_unified_view.sql
- [ ] Test unified view query
- [ ] Check PostgreSQL logs for errors
- [ ] **Phase 1 Sign-off**: ___________ (Initials/Date)

---

### Phase 2: API Access Verification
- [ ] Verify `secrets/gsc_sa.json` is valid JSON
- [ ] Extract service account email
- [ ] Confirm service account in GA4 Property Access
- [ ] Run API connection test
- [ ] Verify at least 1 row returned from test
- [ ] Document any permission issues
- [ ] **Phase 2 Sign-off**: ___________ (Initials/Date)

---

### Phase 3: Service Deployment
- [ ] Build GA4 ingestor Docker image
- [ ] Start container with `--profile core`
- [ ] Verify container status: Running
- [ ] Check container logs (no errors)
- [ ] Test database connectivity from container
- [ ] Test GA4 API connectivity from container
- [ ] Verify environment variables correct
- [ ] **Phase 3 Sign-off**: ___________ (Initials/Date)

---

### Phase 4: Data Collection
- [ ] Run dry-run extraction (test mode)
- [ ] Execute 7-day backfill
- [ ] Verify row count > 0
- [ ] Confirm date range: 2025-11-14 to 2025-11-20
- [ ] Check 7 unique days of data
- [ ] Validate sessions > 0
- [ ] Run data quality checks (nulls, duplicates, ranges)
- [ ] Test unified view with GA4 data
- [ ] Update watermark
- [ ] **Phase 4 Sign-off**: ___________ (Initials/Date)

**Data Quality Results:**
- Total rows inserted: ___________
- Total sessions: ___________
- Total conversions: ___________
- Null check: PASS / FAIL
- Duplicate check: PASS / FAIL
- Range check: PASS / FAIL

---

### Phase 5: Scheduler Integration
- [ ] Add GA4 collection function to scheduler.py
- [ ] Schedule job for 3:00 AM daily
- [ ] Test job manually
- [ ] Restart scheduler
- [ ] Verify GA4 job in job list
- [ ] Confirm next run time scheduled
- [ ] Check no scheduling conflicts
- [ ] **Phase 5 Sign-off**: ___________ (Initials/Date)

---

### Phase 6: Dashboard Enhancement
- [ ] Create new GA4 dashboard OR update existing
- [ ] Add GA4 KPI panels (sessions, conversions, engagement, bounce)
- [ ] Add time series charts (sessions over time)
- [ ] Add hybrid correlation panels
- [ ] Add top converting pages table
- [ ] Test all panel queries
- [ ] Restart Grafana
- [ ] Verify dashboard accessible
- [ ] Test data displays correctly
- [ ] **Phase 6 Sign-off**: ___________ (Initials/Date)

---

### Post-Implementation Checklist
- [ ] **Monitor for 24 Hours**
  - [ ] Check GA4 ingestor logs hourly
  - [ ] Verify no errors in PostgreSQL logs
  - [ ] Confirm data quality maintained
- [ ] **Run Full Validation**
  ```bash
  # Run comprehensive validation
  docker exec gsc_warehouse psql -U gsc_user -d gsc_db -f /path/to/validation.sql
  ```
- [ ] **Document Issues Encountered**
  - Issue 1: ___________________________________________
  - Resolution: ________________________________________
- [ ] **Update Documentation**
  - [ ] Update README.md if needed
  - [ ] Document GA4 metrics in user guide
  - [ ] Add troubleshooting tips
- [ ] **Train Team**
  - [ ] Demo new GA4 dashboard
  - [ ] Explain hybrid insights
  - [ ] Share validation queries
- [ ] **Create Monitoring Alerts**
  - [ ] Daily data freshness check
  - [ ] Data quality validation alert
  - [ ] API quota monitoring
- [ ] **Final Sign-off**: ___________ (Initials/Date)

---

## Next Steps & Timeline

### Immediate Actions (Before Starting)
1. **Confirm Service Account Access**
   - Verify service account has Viewer role on GA4 property 475105521
   - Estimated time: 5 minutes

2. **Choose Implementation Option**
   - [ ] Option A: Implement all phases now (2-3 hours)
   - [ ] Option B: Implement on scheduled date: ___________
   - [ ] Option C: Implement 1 phase per day (6 days)

3. **Backup Database**
   ```bash
   docker exec gsc_warehouse pg_dump -U gsc_user -d gsc_db > backup_pre_ga4.sql
   ```
   - Estimated time: 5 minutes

4. **Reserve Time Block**
   - Phases 1-5: 2 hours focused time
   - Phase 6: 30 minutes
   - Total: 2.5-3 hours

---

### Week 1 Timeline (Recommended)

**Day 1: Phases 1-3 (Database + Service)**
- Pre-implementation checks (30 min)
- Phase 1: Database setup (15 min)
- Phase 2: API verification (10 min)
- Phase 3: Deploy service (20 min)
- **Milestone**: GA4 ingestor running

**Day 2: Phase 4 (Data Collection)**
- Phase 4: Initial data collection (30 min)
- Data quality validation (30 min)
- **Milestone**: 7 days of GA4 data loaded

**Day 3: Monitoring**
- Monitor automated collection
- Verify data quality maintained
- Fix any issues discovered
- **Milestone**: 24 hours of successful operation

**Day 4: Phases 5-6 (Automation + Dashboard)**
- Phase 5: Scheduler integration (15 min)
- Phase 6: Dashboard creation (30 min)
- **Milestone**: Full GA4 integration complete

**Day 5-7: Validation & Training**
- Monitor daily collections
- Validate data accuracy
- Train team on new features
- **Milestone**: GA4 system production-ready

---

### Month 1 Roadmap

**Weeks 1-2: Data Accumulation**
- Collect 14+ days of GA4 data
- Monitor data quality daily
- Fix any collection issues
- Goal: 100% uptime

**Week 3: Insights Development**
- Enable hybrid detectors (anomaly, diagnosis, opportunity)
- Test unified insights
- Verify correlation logic
- Goal: First hybrid insights generated

**Week 4: Optimization**
- Fine-tune query performance
- Create materialized views if needed
- Optimize dashboard load times
- Goal: <3s dashboard load time

---

## Support & Resources

### Documentation
- **GA4 API Documentation**: https://developers.google.com/analytics/devguides/reporting/data/v1
- **Service Account Setup**: `deployment/guides/GCP_SETUP_GUIDE.md`
- **Troubleshooting Guide**: `docs/TROUBLESHOOTING.md`
- **Architecture Overview**: `docs/ARCHITECTURE.md`

### Key Files
- **GA4 Extractor**: `ingestors/ga4/ga4_extractor.py`
- **GA4 Client**: `ingestors/ga4/ga4_client.py`
- **Configuration**: `ingestors/ga4/config.yaml`
- **Schema SQL**: `sql/04_ga4_schema.sql`
- **Unified View**: `sql/05_unified_view.sql`
- **Docker Compose**: `docker-compose.yml` (line 116-135)

### Command Reference

**Service Management**
```bash
# Start GA4 ingestor
docker-compose --profile core up -d ga4_ingestor

# Stop GA4 ingestor
docker-compose stop ga4_ingestor

# View logs
docker logs gsc_ga4_ingestor -f

# Restart service
docker-compose restart ga4_ingestor
```

**Data Collection**
```bash
# Manual collection (specific date range)
docker exec gsc_ga4_ingestor python /app/ingestors/ga4/ga4_extractor.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD

# Incremental collection (since last watermark)
docker exec gsc_ga4_ingestor python /app/ingestors/ga4/ga4_extractor.py \
  --incremental

# Dry run (test without writing)
docker exec gsc_ga4_ingestor python /app/ingestors/ga4/ga4_extractor.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --dry-run
```

**Database Queries**
```bash
# Check GA4 data count
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c \
  "SELECT COUNT(*) FROM gsc.fact_ga4_daily;"

# Check latest date
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c \
  "SELECT MAX(date) FROM gsc.fact_ga4_daily;"

# Verify unified view
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c \
  "SELECT COUNT(*) FROM gsc.vw_unified_page_performance WHERE ga_sessions > 0;"

# Check watermark
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c \
  "SELECT * FROM gsc.ingest_watermarks WHERE source_type='ga4';"
```

**Health Checks**
```bash
# Check container status
docker-compose ps | grep ga4

# Check database connection
docker exec gsc_ga4_ingestor python -c "import psycopg2; \
  psycopg2.connect('postgresql://gsc_user:gsc_pass@warehouse:5432/gsc_db')"

# Check GA4 API connection
docker exec gsc_ga4_ingestor python -c "from google.analytics.data_v1beta import BetaAnalyticsDataClient; \
  BetaAnalyticsDataClient.from_service_account_json('/secrets/gsc_sa.json')"

# View scheduler jobs
docker exec gsc_scheduler python -c "import sys; sys.path.insert(0, '/app'); \
  from scheduler.scheduler import scheduler; \
  [print(f'{j.id}: {j.next_run_time}') for j in scheduler.get_jobs()]"
```

---

## Troubleshooting Guide

### Issue 1: "Permission denied" or "403 Forbidden"
**Symptoms**: GA4 API calls fail with permission errors

**Diagnosis**:
```bash
docker logs gsc_ga4_ingestor | grep -i "permission\|forbidden\|403"
```

**Solution**:
1. Go to GA4 Admin → Property Access Management
2. Add service account email (from `secrets/gsc_sa.json`)
3. Grant "Viewer" or "Analyst" role
4. Wait 5 minutes for propagation
5. Restart container: `docker-compose restart ga4_ingestor`

---

### Issue 2: "Table does not exist"
**Symptoms**: Queries fail with "relation does not exist"

**Diagnosis**:
```bash
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "\dt gsc.fact_ga4_daily"
```

**Solution**:
```bash
# Re-apply schema
docker exec -i gsc_warehouse psql -U gsc_user -d gsc_db < sql/04_ga4_schema.sql

# Verify table created
docker exec gsc_warehouse psql -U gsc_user -d gsc_db -c "\d gsc.fact_ga4_daily"
```

---

### Issue 3: Duplicate Records
**Symptoms**: Primary key violations or duplicate data

**Diagnosis**:
```sql
SELECT date, property, page_path, COUNT(*)
FROM gsc.fact_ga4_daily
GROUP BY date, property, page_path
HAVING COUNT(*) > 1;
```

**Solution**:
```sql
-- Remove duplicates (keep first occurrence)
DELETE FROM gsc.fact_ga4_daily a
USING gsc.fact_ga4_daily b
WHERE a.ctid < b.ctid
  AND a.date = b.date
  AND a.property = b.property
  AND a.page_path = b.page_path;

-- Verify duplicates removed
SELECT COUNT(*) - COUNT(DISTINCT (date, property, page_path)) as duplicates
FROM gsc.fact_ga4_daily;
-- Should return: 0
```

---

### Issue 4: No Data in Unified View
**Symptoms**: Unified view returns 0 rows or NULL for GA4 fields

**Diagnosis**:
```sql
-- Check GA4 data exists
SELECT COUNT(*) FROM gsc.fact_ga4_daily;

-- Check date overlap with GSC
SELECT
  (SELECT MIN(date) FROM gsc.fact_ga4_daily) as ga4_min,
  (SELECT MIN(date) FROM gsc.fact_gsc_daily) as gsc_min,
  (SELECT MAX(date) FROM gsc.fact_ga4_daily) as ga4_max,
  (SELECT MAX(date) FROM gsc.fact_gsc_daily) as gsc_max;
```

**Solution**:
1. Verify GA4 data exists and has overlapping dates with GSC
2. Check page_path matching (GSC uses `url`, GA4 uses `page_path`)
3. Re-create unified view:
   ```bash
   docker exec -i gsc_warehouse psql -U gsc_user -d gsc_db < sql/05_unified_view.sql
   ```

---

### Issue 5: Slow Query Performance
**Symptoms**: Dashboard takes >10 seconds to load

**Diagnosis**:
```sql
EXPLAIN ANALYZE
SELECT * FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days';
```

**Solution**:
```sql
-- Create materialized view for better performance
CREATE MATERIALIZED VIEW gsc.mv_unified_page_performance AS
SELECT * FROM gsc.vw_unified_page_performance;

-- Create index on date
CREATE INDEX idx_mv_unified_date
ON gsc.mv_unified_page_performance(date DESC);

-- Refresh daily (add to scheduler)
REFRESH MATERIALIZED VIEW gsc.mv_unified_page_performance;
```

---

## Appendix A: Sample Queries

### Query 1: GA4 Data Quality Check
```sql
SELECT
  'Total Rows' as metric,
  COUNT(*)::text as value
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Date Range',
  MIN(date)::text || ' to ' || MAX(date)::text
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Sessions',
  SUM(sessions)::text
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Conversions',
  SUM(conversions)::text
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Avg Engagement Rate',
  ROUND(AVG(engagement_rate)::numeric, 4)::text
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Null Sessions',
  COUNT(*) FILTER (WHERE sessions IS NULL)::text
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Duplicates',
  (COUNT(*) - COUNT(DISTINCT (date, property, page_path)))::text
FROM gsc.fact_ga4_daily;
```

---

### Query 2: Hybrid Insights - Correlated Drops
```sql
-- Find pages with both GSC clicks and GA4 sessions dropping
SELECT
  page_path,
  gsc_clicks as current_clicks,
  gsc_clicks_wow as clicks_wow_pct,
  ga_sessions as current_sessions,
  ga_sessions_wow as sessions_wow_pct,
  ga_conversions as current_conversions,
  ga_conversions_wow as conversions_wow_pct
FROM gsc.vw_unified_page_performance
WHERE date = CURRENT_DATE - INTERVAL '1 day'
  AND gsc_clicks_wow < -20  -- Clicks down >20%
  AND ga_sessions_wow < -20  -- Sessions down >20%
  AND gsc_clicks > 10  -- Minimum threshold
ORDER BY ABS(gsc_clicks_wow) + ABS(ga_sessions_wow) DESC
LIMIT 20;
```

---

### Query 3: Intent Mismatch Detection
```sql
-- Find pages with high GSC impressions but low GA4 conversion rate
SELECT
  page_path,
  gsc_impressions as impressions,
  gsc_ctr as ctr,
  ga_sessions as sessions,
  ga_conversions as conversions,
  ROUND((ga_conversions::numeric / NULLIF(ga_sessions, 0)) * 100, 2) as conv_rate,
  gsc_position as avg_position
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
  AND gsc_impressions > 1000  -- High visibility
  AND ga_sessions > 50  -- Meaningful traffic
  AND (ga_conversions::numeric / NULLIF(ga_sessions, 0)) < 0.01  -- Low conversion <1%
GROUP BY page_path, gsc_impressions, gsc_ctr, ga_sessions, ga_conversions, gsc_position
ORDER BY gsc_impressions DESC
LIMIT 20;
```

---

### Query 4: Conversion Optimization Opportunities
```sql
-- Pages with good search visibility but conversion potential
SELECT
  page_path,
  SUM(gsc_impressions)::bigint as total_impressions,
  ROUND(AVG(gsc_ctr)::numeric, 4) as avg_ctr,
  SUM(ga_sessions)::bigint as total_sessions,
  SUM(ga_conversions)::bigint as total_conversions,
  ROUND((SUM(ga_conversions)::numeric / NULLIF(SUM(ga_sessions), 0)) * 100, 2) as conv_rate,
  ROUND(AVG(gsc_position)::numeric, 1) as avg_position
FROM gsc.vw_unified_page_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
  AND gsc_impressions > 500
  AND gsc_position BETWEEN 3 AND 10  -- Good but not #1
  AND ga_sessions > 20
GROUP BY page_path
HAVING (SUM(ga_conversions)::numeric / NULLIF(SUM(ga_sessions), 0)) BETWEEN 0.01 AND 0.05
ORDER BY total_impressions DESC
LIMIT 20;
```

---

## Appendix B: Validation SQL Script

Save as `validation/ga4_validation.sql`:

```sql
-- =============================================
-- GA4 Integration Validation Script
-- Run after implementation to verify success
-- =============================================

\echo '=================================='
\echo 'GA4 Integration Validation Report'
\echo '=================================='
\echo ''

-- Check 1: GA4 Table Exists
\echo '1. Checking GA4 table exists...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'gsc' AND table_name = 'fact_ga4_daily'
    ) THEN '✅ PASS: GA4 table exists'
    ELSE '❌ FAIL: GA4 table missing'
  END as result;

\echo ''

-- Check 2: Unified View Exists
\echo '2. Checking unified view exists...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM information_schema.views
      WHERE table_schema = 'gsc' AND table_name = 'vw_unified_page_performance'
    ) THEN '✅ PASS: Unified view exists'
    ELSE '❌ FAIL: Unified view missing'
  END as result;

\echo ''

-- Check 3: GA4 Data Loaded
\echo '3. Checking GA4 data loaded...'
SELECT
  CASE
    WHEN COUNT(*) > 0 THEN '✅ PASS: GA4 data exists (' || COUNT(*) || ' rows)'
    ELSE '❌ FAIL: No GA4 data'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 4: Data Quality - No Nulls
\echo '4. Checking data quality (nulls)...'
SELECT
  CASE
    WHEN COUNT(*) FILTER (WHERE sessions IS NULL OR page_path IS NULL) = 0
    THEN '✅ PASS: No null values in critical fields'
    ELSE '❌ FAIL: ' || COUNT(*) FILTER (WHERE sessions IS NULL OR page_path IS NULL) || ' null values found'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 5: Data Quality - No Duplicates
\echo '5. Checking data quality (duplicates)...'
SELECT
  CASE
    WHEN COUNT(*) = COUNT(DISTINCT (date, property, page_path))
    THEN '✅ PASS: No duplicate records'
    ELSE '❌ FAIL: ' || (COUNT(*) - COUNT(DISTINCT (date, property, page_path))) || ' duplicates found'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 6: Metric Ranges Valid
\echo '6. Checking metric ranges...'
SELECT
  CASE
    WHEN MIN(bounce_rate) >= 0 AND MAX(bounce_rate) <= 1
     AND MIN(engagement_rate) >= 0 AND MAX(engagement_rate) <= 1
     AND MIN(sessions) >= 0
    THEN '✅ PASS: All metrics within valid ranges'
    ELSE '❌ FAIL: Metrics outside expected ranges'
  END as result
FROM gsc.fact_ga4_daily;

\echo ''

-- Check 7: Watermark Exists
\echo '7. Checking watermark tracking...'
SELECT
  CASE
    WHEN EXISTS (
      SELECT 1 FROM gsc.ingest_watermarks WHERE source_type = 'ga4'
    ) THEN '✅ PASS: GA4 watermark exists (last date: ' ||
            (SELECT last_date::text FROM gsc.ingest_watermarks WHERE source_type = 'ga4') || ')'
    ELSE '❌ FAIL: GA4 watermark missing'
  END as result;

\echo ''

-- Check 8: Unified View Has Data
\echo '8. Checking unified view has GA4 data...'
SELECT
  CASE
    WHEN COUNT(*) FILTER (WHERE ga_sessions > 0) > 0
    THEN '✅ PASS: Unified view has GA4 data (' ||
         COUNT(*) FILTER (WHERE ga_sessions > 0) || ' rows with sessions)'
    ELSE '❌ FAIL: Unified view has no GA4 data'
  END as result
FROM gsc.vw_unified_page_performance;

\echo ''

-- Summary Statistics
\echo '=================================='
\echo 'Summary Statistics'
\echo '=================================='
\echo ''

SELECT
  'Total GA4 Rows' as metric,
  COUNT(*)::text as value
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Date Range',
  COALESCE(MIN(date)::text, 'N/A') || ' to ' || COALESCE(MAX(date)::text, 'N/A')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Sessions',
  COALESCE(SUM(sessions)::text, '0')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Total Conversions',
  COALESCE(SUM(conversions)::text, '0')
FROM gsc.fact_ga4_daily

UNION ALL

SELECT
  'Avg Engagement',
  COALESCE(ROUND(AVG(engagement_rate)::numeric, 4)::text, 'N/A')
FROM gsc.fact_ga4_daily;

\echo ''
\echo '=================================='
\echo 'Validation Complete'
\echo '=================================='
```

Run with:
```bash
docker exec -i gsc_warehouse psql -U gsc_user -d gsc_db < validation/ga4_validation.sql
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-21 | Claude (Sonnet 4.5) | Initial comprehensive plan created |

---

**END OF DOCUMENT**
